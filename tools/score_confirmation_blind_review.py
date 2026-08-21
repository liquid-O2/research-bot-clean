#!/usr/bin/env python3
"""Reveal and strictly score a hash-chained confirmation blind review."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np

from entry_v2 import common as C
from entry_v2.confirmation import ConfirmationRefusal
from entry_v2.confirmation_stopping import ACTION_NAMES


NANOS_PER_SECOND = 1_000_000_000


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root", type=Path,
        default=Path("/workspace/artifacts/entry_v2/confirmation/"
                     "blind_raw_review_v1"))
    return parser.parse_args()


def _json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text())
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ConfirmationRefusal(f"cannot read blind review input: {path}") from exc
    if not isinstance(value, dict):
        raise ConfirmationRefusal("blind review input is not an object")
    return value


def _verify_receipt(value: dict[str, object], schema: str) -> None:
    core = {key: item for key, item in value.items()
            if key != "receipt_sha256"}
    if (value.get("schema") != schema
            or value.get("receipt_sha256") != C.object_sha256(core)):
        raise ConfirmationRefusal(f"{schema} receipt differs")


def _next_30_delta(case: dict[str, object], checkpoint: int) -> float:
    path = Path(str(case["causal_npz_path"]))
    if C.file_sha256(path) != case["causal_npz_sha256"]:
        raise ConfirmationRefusal("blind causal NPZ hash differs")
    with np.load(path, allow_pickle=False) as payload:
        seconds = np.asarray(payload["second_start_ts_ns"], np.int64)
        displacement = np.asarray(
            payload["aligned_mid_from_formation_usd"], np.float64)
        timestamp = int(case["checkpoints"][checkpoint]["snapshot_ts_ns"])

        def last_before(boundary: int) -> int:
            indices = np.flatnonzero(
                seconds + NANOS_PER_SECOND <= boundary)
            if not len(indices):
                raise ConfirmationRefusal("blind causal interval is absent")
            return int(indices[-1])

        before = last_before(timestamp)
        after = last_before(timestamp + 30 * NANOS_PER_SECOND)
        result = float(displacement[after] - displacement[before])
    if not np.isfinite(result):
        raise ConfirmationRefusal("blind next-30 displacement is not finite")
    return result


def main() -> int:
    args = _arguments()
    root = args.root.resolve()
    manifest = _json(root / "blind_manifest.json")
    _verify_receipt(manifest, "QRE2CONFBLINDREVIEW1")
    if (manifest.get("forward_open_count") != 0
            or manifest.get("h2_open_count") != 0
            or manifest.get("outcome_destruction_roster_unchanged") is not True):
        raise ConfirmationRefusal("blind manifest safety contract differs")
    cases = tuple(manifest.get("cases", ()))
    by_case = {str(row["case_id"]): row for row in cases}
    if len(by_case) != len(cases) or not cases:
        raise ConfirmationRefusal("blind manifest cases are empty/duplicated")

    rounds = (
        (0, root / "precommit_round_000.json"),
        (30, root / "precommit_round_030.json"),
        (60, root / "precommit_round_060.json"),
        (120, root / "precommit_round_120.json"),
    )
    active = set(by_case)
    terminal: dict[str, tuple[int, int, str, str]] = {}
    prior_hash = None
    precommit_hashes = []
    nominal_ages = tuple(map(int, manifest["watch_ages_seconds"]))
    for age, path in rounds:
        value = _json(path)
        digest = C.file_sha256(path)
        if (value.get("schema") != "QRE2CONFBLINDPRECOMMIT1"
                or int(value.get("round_watch_age_sec", -1)) != age
                or value.get("oracle_reports_opened") is not False
                or (prior_hash is not None
                    and value.get("prior_round_sha256") != prior_hash)):
            raise ConfirmationRefusal("blind precommit chain differs")
        decisions = tuple(value.get("decisions", ()))
        decision_ids = {str(row["case_id"]) for row in decisions}
        if decision_ids != active or len(decision_ids) != len(decisions):
            raise ConfirmationRefusal("blind round does not cover active cases")
        try:
            checkpoint = nominal_ages.index(age)
        except ValueError as exc:
            raise ConfirmationRefusal("blind round age has no checkpoint") from exc
        next_active = set()
        for row in decisions:
            case_id = str(row["case_id"])
            action = str(row["action"])
            if action == "WAIT":
                next_active.add(case_id)
            elif action in {"ENTER", "PASS"}:
                prediction = str(row.get("next_30s_prediction", ""))
                if not prediction:
                    raise ConfirmationRefusal(
                        "terminal blind action lacks next-30 prediction")
                terminal[case_id] = (checkpoint, age, action, prediction)
            else:
                raise ConfirmationRefusal("blind action is unknown")
        active = next_active
        prior_hash = digest
        precommit_hashes.append(digest)
    if active or set(terminal) != set(by_case):
        raise ConfirmationRefusal("blind review has unterminated cases")

    rows = []
    for case_id, case in by_case.items():
        report_path = Path(str(case["sealed_oracle_report_path"]))
        report = _json(report_path)
        _verify_receipt(report, "QRE2CONFRAWDOSSIER2")
        if (report.get("series_id") != case.get("series_id")
                or report.get("category") != "BLIND_HASH_SAMPLE"):
            raise ConfirmationRefusal("blind reveal identity differs")
        points = tuple(report.get("decision_points", ()))
        if len(points) != len(case["checkpoints"]):
            raise ConfirmationRefusal("blind reveal checkpoints differ")
        checkpoint, age, action, prediction = terminal[case_id]
        chosen = points[checkpoint]
        formation = points[0]
        q_enter = float(chosen["q_enter_usd"])
        q_wait = float(chosen["q_wait_usd"])
        q_optimal_start = max(
            0.0, float(formation["q_enter_usd"]),
            float(formation["q_wait_usd"]))
        reward = q_enter if action == "ENTER" else 0.0
        next_30_delta = _next_30_delta(case, checkpoint)
        if prediction.startswith("FAVORABLE"):
            prediction_correct = next_30_delta > 0.0
        elif prediction == "NOT_FAVORABLE":
            prediction_correct = next_30_delta <= 0.0
        else:
            raise ConfirmationRefusal("terminal direction prediction is unknown")
        oracle_action = ACTION_NAMES[int(chosen["optimal_action"])]
        rows.append({
            "case_id": case_id, "asset": str(case["asset"]),
            "side": int(case["side"]), "action": action,
            "watch_age_sec": age, "candidate_local_reward_usd": reward,
            "chosen_q_enter_usd": q_enter,
            "chosen_q_wait_usd": q_wait,
            "chosen_oracle_action": oracle_action,
            "terminal_action_matches_oracle": action == oracle_action,
            "formation_q_optimal_usd": q_optimal_start,
            "formation_goal_opportunity": q_optimal_start >= 600.0,
            "candidate_local_regret_usd": q_optimal_start - reward,
            "next_30_prediction": prediction,
            "next_30_aligned_delta_usd": next_30_delta,
            "next_30_prediction_correct": bool(prediction_correct),
            "chosen_mfe_usd": float(chosen["mfe_usd"]),
            "chosen_mae_usd": float(chosen["mae_usd"]),
            "chosen_wall_hit": bool(chosen["wall_hit"]),
        })

    reward = sum(float(row["candidate_local_reward_usd"]) for row in rows)
    ceiling = sum(float(row["formation_q_optimal_usd"]) for row in rows)
    entries = [row for row in rows if row["action"] == "ENTER"]
    no_opportunity = [row for row in rows
                      if row["formation_q_optimal_usd"] <= 0.0]
    positive_opportunity = [row for row in rows
                            if row["formation_q_optimal_usd"] > 0.0]
    summary = {
        "case_count": len(rows),
        "terminal_action_oracle_accuracy": sum(
            row["terminal_action_matches_oracle"] for row in rows) / len(rows),
        "next_30_direction_accuracy": sum(
            row["next_30_prediction_correct"] for row in rows) / len(rows),
        "entry_count": len(entries),
        "entry_winner_count": sum(
            row["candidate_local_reward_usd"] > 0.0 for row in entries),
        "entry_wall_count": sum(row["chosen_wall_hit"] for row in entries),
        "candidate_local_reward_usd": reward,
        "candidate_local_oracle_ceiling_usd": ceiling,
        "candidate_local_capture": None if ceiling <= 0 else reward / ceiling,
        "candidate_local_regret_usd": ceiling - reward,
        "formation_goal_opportunity_count": sum(
            row["formation_goal_opportunity"] for row in rows),
        "zero_opportunity_count": len(no_opportunity),
        "zero_opportunity_passed": sum(
            row["action"] == "PASS" for row in no_opportunity),
        "positive_opportunity_count": len(positive_opportunity),
        "positive_opportunity_entered": sum(
            row["action"] == "ENTER" for row in positive_opportunity),
        "by_asset": {
            asset: {
                "cases": sum(row["asset"] == asset for row in rows),
                "entries": sum(row["asset"] == asset
                               and row["action"] == "ENTER" for row in rows),
                "candidate_local_reward_usd": sum(
                    row["candidate_local_reward_usd"] for row in rows
                    if row["asset"] == asset),
            } for asset in C.ASSETS
        },
    }
    core = {
        "schema": "QRE2CONFBLINDREVEAL1",
        "manifest_receipt_sha256": manifest["receipt_sha256"],
        "precommit_sha256": precommit_hashes,
        "summary": summary, "cases": rows,
        "candidate_local_diagnostic_only": True,
        "portfolio_economics_executed": False,
        "forward_open_count": 0, "h2_open_count": 0,
    }
    artifact = {**core, "receipt_sha256": C.object_sha256(core)}
    output = root / "reveal_score.json"
    if output.exists():
        raise ConfirmationRefusal("blind reveal score already exists")
    C.atomic_json(output, artifact)
    print(json.dumps({
        "receipt_sha256": artifact["receipt_sha256"],
        "summary": summary,
        "portfolio_economics_executed": False,
        "forward_open_count": 0, "h2_open_count": 0,
    }, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({
            "event": "BLIND_REVEAL_REFUSED", "type": type(exc).__name__,
            "reason": str(exc),
        }, sort_keys=True), file=sys.stderr, flush=True)
        raise
