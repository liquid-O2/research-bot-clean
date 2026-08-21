#!/usr/bin/env python3
"""Publish PLATT raw-event dossiers for the action-aligned policy failure."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from catboost import CatBoostRanker
import numpy as np

from entry_v2 import common as C
from entry_v2.confirmation_dossier import (
    DossierSelection, materialize_raw_dossiers,
)
from entry_v2.confirmation_fixed_horizon import (
    fixed_horizon_target, ordered_series_groups,
)
from entry_v2.confirmation_lawful_policy import (
    _candidate_topk, _stop_matrix, causal_first_crossings,
)
from entry_v2.confirmation_lawful_value_model import lawful_value_rank_scores
from entry_v2.confirmation_dynamic_hurdle_policy import _evaluation_summary
from entry_v2.confirmation_model import ConfirmationPredictions
from entry_v2.confirmation_policy import _arrival, _solve_day
from entry_v2.replay import replay

from run_confirmation_dynamic_hurdle import (
    _learned_fit_gate, _load_rank_models,
)
from run_confirmation_fixed_horizon import _load_roles
from run_confirmation_lawful_policy import _load_candidate_models


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-root", type=Path,
        default=Path("/workspace/artifacts/cache/port/entry_v2"))
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
        "--policy-audit", type=Path,
        default=Path(
            "/workspace/artifacts/entry_v2/confirmation/v9_qrf4/"
            "e1r_lawful_policy_ceiling_v1.json"))
    parser.add_argument(
        "--stop-model-dir", type=Path,
        default=Path(
            "/workspace/artifacts/entry_v2/confirmation/v9_qrf4/"
            "e1r_lawful_policy_ceiling_v1_models"))
    parser.add_argument(
        "--output", type=Path,
        default=Path(
            "/workspace/artifacts/entry_v2/confirmation/v9_qrf4/"
            "lawful_policy_raw_dossiers_v1"))
    parser.add_argument("--per-category", type=int, default=3)
    return parser.parse_args()


def _json(path: Path, schema: str) -> dict:
    value = json.loads(path.read_text()); core = dict(value)
    receipt = str(core.pop("receipt_sha256"))
    if value.get("schema") != schema or C.object_sha256(core) != receipt:
        raise ValueError(f"dossier input identity differs: {path}")
    return value


def _pick(
    indices: np.ndarray, dataset, *, limit: int, descending: np.ndarray,
    used: set[str],
) -> list[int]:
    ordered = indices[np.argsort(-descending[indices], kind="stable")]
    result = []
    # First pass is asset-balanced; the second fills any remaining slots.
    for asset in C.ASSETS:
        for index in ordered:
            series = str(dataset.series_id[index])
            if str(dataset.asset[index]) == asset and series not in used:
                result.append(int(index)); used.add(series); break
    for index in ordered:
        series = str(dataset.series_id[index])
        if series not in used:
            result.append(int(index)); used.add(series)
        if len(result) >= limit:
            break
    return result[:limit]


def main() -> int:
    args = _arguments()
    if args.output.exists():
        raise FileExistsError(f"raw dossier output exists: {args.output}")
    fixed_audit = _json(
        args.fixed_horizon_audit, "QRE2CONFFIXEDHORIZONAUDIT1")
    candidate_audit = _json(
        args.candidate_rank_audit, "QRE2CONFLAWFULVALUERANKAUDIT1")
    policy_audit = _json(
        args.policy_audit, "QRE2CONFLAWFULPOLICYCEILINGAUDIT1")
    (conditional, ledgers, fixed, sessions,
     conditional_manifest, _capacity_manifest) = _load_roles(
         args.conditional_root, args.capacity_root)
    old_rank, _old_control, _old_manifest = _load_rank_models(
        args.rank_model_dir, conditional_manifest)
    dataset, ledger = _learned_fit_gate(
        conditional["PLATT"], ledgers["PLATT"], fixed["PLATT"],
        rank_model=old_rank, capacity=12)
    base_roster = tuple(sorted(set(np.asarray(dataset.series_id, str).tolist())))

    candidate_models = _load_candidate_models(
        candidate_audit, args.candidate_model_dir)
    candidate_score, _candidate_control = lawful_value_rank_scores(
        candidate_models, fixed["PLATT"],
        selected_transform=candidate_audit["selected_feature_transform"])
    selected_policy = policy_audit["result"]["arms"]["REAL_REAL"][
        "selected_with_capture"]
    roster = _candidate_topk(
        fixed["PLATT"], base_roster, candidate_score,
        int(selected_policy["candidate_topk_per_asset_day"]))
    stop_row = policy_audit["stopping_models"]["real"]
    stop_path = args.stop_model_dir / stop_row["path"]
    if C.file_sha256(stop_path) != stop_row["file_sha256"]:
        raise ValueError("raw dossier stopping model differs")
    stop_model = CatBoostRanker(); stop_model.load_model(stop_path, format="cbm")
    stop_transform = fixed_audit["result"]["horizons"]["120"][
        "selected_feature_transform"]
    stop_matrix, _ = _stop_matrix(dataset, stop_transform)
    stop_score = np.asarray(stop_model.predict(stop_matrix), np.float64)
    target = fixed_horizon_target(dataset, ledger, 120)
    triggers = causal_first_crossings(
        dataset, target, stop_score, roster,
        minimum_delay_sec=int(selected_policy["minimum_delay_sec"]),
        stop_delta_threshold=float(selected_policy["stop_delta_threshold"]))
    score_by_series = {str(series): float(score) for series, score in zip(
        fixed["PLATT"].series_id, candidate_score)}
    arrivals = tuple(_arrival(
        dataset, int(index), model_hash="lawful-policy-real-real-dossier",
        expected_pnl_usd=score_by_series[str(dataset.series_id[index])],
        pnl_q20_usd=score_by_series[str(dataset.series_id[index])],
        goal_probability=1.0, wall_probability=0.0, mae_q90_usd=0.0,
    ) for index in triggers)
    evaluation = replay(arrivals, expected_sessions=sessions["PLATT"])
    executed_ids = {row.candidate_id for row in evaluation.trade_results}
    executed = np.asarray([index for index in triggers
                           if str(dataset.opportunity_id[index]) in executed_ids],
                          np.int64)
    if evaluation.trades != len(executed):
        raise ValueError("raw dossier replay trigger identity differs")

    # Exact action-family schedule and per-candidate marginal contribution.
    q_enter = np.asarray(ledger.q_enter_usd, np.float64)
    series = np.asarray(dataset.series_id, str)
    days = np.asarray(dataset.day, np.int64)
    action_by_series = {}; action_rows = []
    for group in ordered_series_groups(series, dataset.snapshot_ts_ns):
        admissible = (target.eligible[group]
                      & (target.stop_utility_usd[group] >= 0.0)
                      & (q_enter[group] > 0.0))
        if not admissible.any():
            continue
        rows = group[np.flatnonzero(admissible)]
        chosen = int(rows[int(np.argmax(q_enter[rows]))])
        action_by_series[str(series[chosen])] = chosen
        action_rows.append(chosen)
    action_rows = np.asarray(action_rows, np.int64)
    marginal = np.zeros(len(dataset.features), np.float64)
    schedule_rows = []
    for day in sorted(set(days[action_rows].tolist())):
        local = action_rows[days[action_rows] == day]
        chosen, cents = _solve_day(dataset, local)
        schedule_rows.extend(chosen.tolist())
        for index in chosen:
            _, without = _solve_day(dataset, local[local != index])
            marginal[index] = (cents - without) / 100.0
    schedule_rows = np.asarray(schedule_rows, np.int64)

    pnl = np.asarray(dataset.cert_close_usd, np.float64)
    q_wait = np.asarray(ledger.q_wait_usd, np.float64)
    losses_no_later = executed[(pnl[executed] < 0.0)
                               & (q_wait[executed] < 600.0)]
    losses_later = executed[(pnl[executed] < 0.0)
                            & (q_wait[executed] >= 600.0)]
    winners = executed[pnl[executed] >= 600.0]
    executed_series = set(series[executed].tolist())
    missed = schedule_rows[(marginal[schedule_rows] > 0.0)
                           & ~np.isin(series[schedule_rows],
                                     tuple(executed_series))]
    used: set[str] = set(); selected = []
    category_rows = (
        ("MODEL_LOSS_NO_LATER_GOAL", losses_no_later, -pnl),
        ("MODEL_LOSS_LATER_GOAL", losses_later, -pnl),
        ("MODEL_GOAL_WINNER", winners, pnl),
        ("MISSED_ORACLE_GOAL_ENTER", missed, marginal),
    )
    trigger_by_series = {str(series[index]): int(index) for index in triggers}
    for category, indices, priority in category_rows:
        for index in _pick(
                np.asarray(indices, np.int64), dataset,
                limit=args.per_category, descending=np.asarray(priority),
                used=used):
            candidate = str(series[index])
            anchor = (action_by_series[candidate]
                      if category == "MISSED_ORACLE_GOAL_ENTER" else index)
            decisions = [int(anchor)]
            other = (trigger_by_series.get(candidate)
                     if category == "MISSED_ORACLE_GOAL_ENTER"
                     else action_by_series.get(candidate))
            if other is not None and int(other) != int(anchor):
                decisions.append(int(other))
            row = DossierSelection(
                category=category, anchor_index=int(anchor),
                decision_indices=tuple(decisions))
            row.validate(dataset); selected.append(row)
    if not selected:
        raise ValueError("raw dossier selection is empty")

    # Keep only the two audited feature transforms in readable decision rows;
    # the NPZ always contains the complete raw event slice.
    columns = sorted(set(
        int(row["source_column"])
        for row in candidate_audit["selected_feature_transform"]
    ) | set(int(row["source_column"]) for row in stop_transform))
    mask = np.zeros(len(dataset.feature_names), bool); mask[columns] = True
    model_dataset = dataset.select_features(mask)
    stop_min = float(np.min(stop_score)); stop_max = float(np.max(stop_score))
    stop_probability = ((stop_score - stop_min) / (stop_max - stop_min)
                        if stop_max > stop_min else np.zeros(len(stop_score)))
    path_candidate_score = np.asarray([
        score_by_series[str(value)] for value in dataset.series_id], np.float64)
    predictions = ConfirmationPredictions(
        opportunity_id=np.asarray(dataset.opportunity_id, str).copy(),
        expected_pnl_usd=path_candidate_score,
        pnl_q20_usd=path_candidate_score.copy(),
        goal_probability=stop_probability,
        wall_probability=np.zeros(len(stop_score), np.float64),
        mae_q90_usd=np.zeros(len(stop_score), np.float64),
        model_hash="LAWFUL_POLICY_RAW_DOSSIER",
    )
    reports = materialize_raw_dossiers(
        dataset, model_dataset, predictions, ledger, tuple(selected),
        source_root=args.source_root, output_directory=args.output)
    category_counts = {
        category: sum(row.category == category for row in selected)
        for category, _indices, _priority in category_rows
    }
    core = {
        "schema": "QRE2CONFLAWFULPOLICYRAWDOSSIERAUDIT1",
        "policy_audit_receipt_sha256": policy_audit["receipt_sha256"],
        "fixed_horizon_audit_receipt_sha256": fixed_audit["receipt_sha256"],
        "candidate_rank_audit_receipt_sha256": candidate_audit["receipt_sha256"],
        "reproduced_real_real_economics": _evaluation_summary(
            evaluation, sessions["PLATT"]),
        "trigger_count": len(triggers), "executed_trades": evaluation.trades,
        "category_counts": category_counts,
        "dossier_count": len(reports),
        "dossier_receipts": tuple(row["receipt_sha256"] for row in reports),
        "model_feature_count": len(model_dataset.feature_names),
        "raw_events_complete_within_each_dossier_window": True,
        "threshold_open_count": 0, "forward_open_count": 0,
        "h2_open_count": 0,
    }
    artifact = {**core, "receipt_sha256": C.object_sha256(core)}
    C.atomic_json(args.output / "audit_report.json", artifact)
    print(json.dumps(artifact, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({
            "event": "LAWFUL_POLICY_RAW_DOSSIER_REFUSED",
            "type": type(exc).__name__, "reason": str(exc),
        }, sort_keys=True), flush=True)
        raise
