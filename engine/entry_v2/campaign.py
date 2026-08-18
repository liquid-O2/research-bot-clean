#!/usr/bin/env python3
"""Exact E3..E8 OOF campaign union and promotion receipt.

This module does not fit, tune, or reinterpret a fold.  It verifies the frozen
``FoldOOFResult`` surfaces, proves their test populations are disjoint, rebinds
their fold-local score hashes to one campaign family, and invokes the same
arrival replay on the union.  Production construction requires independent
raw-prefix and teacher-join evidence; a fold result is not allowed to attest to
its own upstream fidelity.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import math
import os
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from . import common as C
from .capacity_contract import capacity_regime_from_oracle, required_floor_usd
from .contracts import (
    AssetDayRegime,
    AssetEvaluation,
    EntryEvaluation,
    EntryScore,
    SessionRef,
)
from .policy import ModelInputBinding, entry_decision_gate, entry_gate_contract
from .replay import (
    CandidateCeiling,
    ScoredArrival,
    candidate_ceiling,
    replay,
)
from .train import (
    ARM_FULL_PREFIX,
    ARM_NAMES,
    FOLD_OOF_SCHEMA,
    SelectedWinnerFoldResult,
    fold_result_arms,
    fold_training_identity,
    THRESHOLD_FUNNEL_SCHEMA,
    FoldOOFResult,
    threshold_candidate_law,
)


CAMPAIGN_SCHEMA = "entry-v2-oof-campaign-v4"
EXPECTED_FOLDS = tuple(f"E{index}" for index in range(3, 9))


def _sha(value: Any, name: str) -> str:
    text = str(value)
    if len(text) != 64 or any(char not in "0123456789abcdef" for char in text):
        raise C.EntryV2Refusal(f"invalid {name} sha256")
    return text


@dataclass(frozen=True, slots=True)
class RawPrefixFidelityEvidence:
    expected_events: int
    observed_events: int
    mismatched_events: int
    source_receipt_sha256: str
    pack_receipt_sha256: str

    def validate(self) -> None:
        expected, observed, mismatched = (
            int(self.expected_events), int(self.observed_events),
            int(self.mismatched_events),
        )
        if expected <= 0 or observed < 0 or mismatched < 0:
            raise C.EntryV2Refusal("invalid raw-prefix fidelity counts")
        if mismatched > min(expected, observed):
            raise C.EntryV2Refusal("raw-prefix mismatch count exceeds population")
        if mismatched < abs(expected - observed):
            raise C.EntryV2Refusal(
                "raw-prefix mismatch count omits missing/extra events"
            )
        _sha(self.source_receipt_sha256, "raw source receipt")
        _sha(self.pack_receipt_sha256, "event-pack receipt")

    @property
    def passed(self) -> bool:
        return (self.expected_events == self.observed_events
                and self.mismatched_events == 0)


@dataclass(frozen=True, slots=True)
class TeacherAlignmentEvidence:
    expected_candidates: int
    matched_candidates: int
    mismatched_candidates: int
    teacher_receipt_sha256: str
    join_receipt_sha256: str

    def validate(self) -> None:
        expected, matched, mismatched = (
            int(self.expected_candidates), int(self.matched_candidates),
            int(self.mismatched_candidates),
        )
        if expected <= 0 or matched < 0 or mismatched < 0:
            raise C.EntryV2Refusal("invalid teacher-alignment counts")
        if matched + mismatched != expected:
            raise C.EntryV2Refusal(
                "teacher matched+mismatched does not equal expected candidates"
            )
        _sha(self.teacher_receipt_sha256, "teacher receipt")
        _sha(self.join_receipt_sha256, "teacher join receipt")

    @property
    def passed(self) -> bool:
        return (self.matched_candidates == self.expected_candidates
                and self.mismatched_candidates == 0)


@dataclass(frozen=True, slots=True)
class CampaignResult:
    model_family_hash: str
    arm_evaluations: Mapping[str, EntryEvaluation]
    truth_evaluation: EntryEvaluation
    shuffled_arm_evaluations: Mapping[str, EntryEvaluation] | None
    candidate_ceiling: CandidateCeiling
    receipt: Mapping[str, Any]

    @property
    def learned_evaluation(self) -> EntryEvaluation:
        return self.arm_evaluations[ARM_FULL_PREFIX]


def _array_hash(named: Mapping[str, np.ndarray]) -> str:
    digest = hashlib.sha256()
    for name, value in sorted(named.items()):
        array = np.ascontiguousarray(value)
        digest.update(name.encode())
        digest.update(str(array.shape).encode())
        digest.update(str(array.dtype).encode())
        digest.update(array.tobytes())
    return digest.hexdigest()


def _fold_array_hash(result: FoldOOFResult) -> str:
    arrays: dict[str, np.ndarray] = {
        "full_prefix_embedding": np.asarray(result.embeddings),
        "static_summary": np.asarray(result.static_features),
    }
    arrays.update({
        f"{arm}:{name}": np.asarray(value)
        for arm, scores in result.arm_score_arrays.items()
        for name, value in scores.items()
    })
    return _array_hash(arrays)


def _same_payload(left: ScoredArrival, right: ScoredArrival) -> bool:
    return left.example == right.example and left.outcome == right.outcome


def _evaluation_equal(left: EntryEvaluation, right: EntryEvaluation,
                      name: str) -> None:
    if left != right:
        raise C.EntryV2Refusal(f"fold {name} cached evaluation differs from replay")


def _receipt_thresholds(
    receipt: Mapping[str, Any], key: str, fold: str
) -> dict[str, float]:
    raw = receipt.get(key)
    if not isinstance(raw, Mapping) or set(raw) != set(C.ASSETS):
        raise C.EntryV2Refusal(f"{fold}: receipt {key} lacks SI/HG/NKD")
    out: dict[str, float] = {}
    for asset in C.ASSETS:
        row = raw[asset]
        if (
            not isinstance(row, Mapping)
            or "threshold" not in row
            or "asset_days" not in row
            or "usd_per_asset_day" not in row
        ):
            raise C.EntryV2Refusal(
                f"{fold}: receipt {key}/{asset} lacks asset-day threshold evidence"
            )
        value = float(row["threshold"])
        dollars = float(row["usd_per_asset_day"])
        if (
            not math.isfinite(value)
            or not math.isfinite(dollars)
            or int(row["asset_days"]) <= 0
        ):
            raise C.EntryV2Refusal(
                f"{fold}: receipt {key}/{asset} threshold evidence is invalid"
            )
        out[asset] = value
    return out


def _validate_fold(result: FoldOOFResult, *, shuffled: bool) -> dict[str, Any]:
    fold = str(result.fold)
    if fold not in EXPECTED_FOLDS:
        raise C.EntryV2Refusal(f"unexpected campaign fold: {fold}")
    receipt = dict(result.receipt)
    required_receipt = {
        "schema", "fold", "training_receipt_sha256", "normalizer_sha256",
        "test_min_d8", "test_max_d8", "test_candidate_sha256",
        "arrays_sha256", "assets", "training_control", "entry_gate_contract",
        "candidate_oracle_preflight", "model_input_binding", "sha256",
        "arms", "arm_thresholds", "prequential", "static_summary_schema",
        "test_days_declared", "regime_declarations", "null_control",
        "threshold_candidate_law", "threshold_funnel_schema",
        "action_supervision_census",
    }
    if not required_receipt.issubset(receipt):
        raise C.EntryV2Refusal(
            f"{fold}: fold receipt fields missing: {sorted(required_receipt-set(receipt))}"
        )
    if receipt["schema"] != FOLD_OOF_SCHEMA or receipt["fold"] != fold:
        raise C.EntryV2Refusal(f"{fold}: fold receipt identity mismatch")
    declared = _sha(receipt.pop("sha256"), f"{fold} fold receipt")
    if C.object_sha256(receipt) != declared:
        raise C.EntryV2Refusal(f"{fold}: fold receipt hash mismatch")
    receipt["sha256"] = declared
    binding = ModelInputBinding.from_mapping(receipt["model_input_binding"])
    if set(receipt["assets"]) != set(C.ASSETS):
        raise C.EntryV2Refusal(f"{fold}: fold receipt lacks SI/HG/NKD")
    arms = fold_result_arms(result)
    if tuple(receipt["arms"]) != arms:
        raise C.EntryV2Refusal(f"{fold}: campaign arm roster differs from result kind")
    prequential = receipt["prequential"]
    try:
        blocks = tuple(
            tuple(int(day) for day in block)
            for block in prequential["blocks"]
        )
        calibration_days = tuple(int(day) for day in prequential["calibration_days"])
        selection_days = tuple(
            int(day) for day in prequential["threshold_selection_days"]
        )
        prequential_valid = bool(
            len(blocks) >= 2
            and calibration_days == tuple(
                day for block in blocks[:-1] for day in block
            )
            and selection_days == blocks[-1]
            and not set(calibration_days).intersection(selection_days)
            and max(calibration_days) < min(selection_days)
            and int(receipt["fit_max_d8"]) < min(calibration_days)
            and max(selection_days) < int(receipt["test_min_d8"])
            and prequential["calibration_and_selection_predictions_disjoint"] is True
            and prequential["test_predictions_never_used_for_calibration_or_selection"] is True
        )
    except (KeyError, TypeError, ValueError):
        prequential_valid = False
    if not prequential_valid:
        raise C.EntryV2Refusal(f"{fold}: prequential calibration contract differs")
    control = str(result.control_name)
    if receipt["training_control"] != control:
        raise C.EntryV2Refusal(f"{fold}: control name differs from receipt")
    if receipt["entry_gate_contract"] != entry_gate_contract():
        raise C.EntryV2Refusal(f"{fold}: decision gate contract differs")
    if receipt["threshold_candidate_law"] != threshold_candidate_law():
        raise C.EntryV2Refusal(f"{fold}: threshold-candidate law differs")
    if receipt["threshold_funnel_schema"] != THRESHOLD_FUNNEL_SCHEMA:
        raise C.EntryV2Refusal(f"{fold}: threshold funnel schema differs")
    census = receipt["action_supervision_census"]
    if (
        not isinstance(census, Mapping)
        or census.get("schema") != "entry-v2-action-supervision-census-v1"
        or census.get("passed") is not True
        or not isinstance(census.get("per_asset"), Mapping)
        or set(census["per_asset"]) != set(C.ASSETS)
    ):
        raise C.EntryV2Refusal(f"{fold}: action-supervision census differs")
    preflight = receipt["candidate_oracle_preflight"]
    valid_preflight = isinstance(preflight, Mapping)
    try:
        per_asset_preflight = preflight["per_asset"]
        valid_preflight = bool(
            valid_preflight
            and preflight.get("schema")
                == "entry-v2-candidate-oracle-preflight-v5"
            and preflight.get("acceptance_law")
                == "oracle_usd_per_asset_day >= LOW_CAPACITY_ASSET_DAY_FLOOR_USD"
            and float(preflight.get("acceptance_floor_usd_per_asset_day"))
                == C.LOW_CAPACITY_ASSET_DAY_FLOOR_USD
            and float(preflight.get("normal_floor_usd_per_asset_day"))
                == C.WEAK_ASSET_DAY_FLOOR_USD
            and preflight.get("risk_exception_contract") == (
                "learned era usd_per_asset_day >= LOW_CAPACITY_ASSET_DAY_FLOOR_USD "
                "and chronological max_drawdown_usd < LOW_CAPACITY_MAX_DRAWDOWN_USD"
            )
            and float(preflight.get("risk_exception_max_drawdown_usd"))
                == C.LOW_CAPACITY_MAX_DRAWDOWN_USD
            and float(preflight.get("optimization_goal_usd_per_asset_day"))
                == C.TARGET_ASSET_DAY_USD
            and preflight.get("optimization_target") == "full_total_pnl_usd"
            and preflight.get("values_clipped_to_acceptance_floor") is False
            and preflight.get("passed") is True
            and len(_sha(preflight.get("schedule_sha256"),
                         f"{fold} oracle preflight schedule")) == 64
            and isinstance(per_asset_preflight, Mapping)
            and set(per_asset_preflight) == set(C.ASSETS)
        )
        for asset in C.ASSETS:
            row = per_asset_preflight[asset]
            days = int(row["asset_days"])
            total = float(row["total_pnl_usd"])
            per_day = float(row["usd_per_asset_day"])
            capture = float(row["oracle_capture"])
            floor = float(row["acceptance_floor_usd_per_asset_day"])
            normal_floor = float(row["normal_floor_usd_per_asset_day"])
            goal = float(row["optimization_goal_usd_per_asset_day"])
            floor_headroom = float(
                row["acceptance_floor_headroom_usd_per_asset_day"])
            normal_headroom = float(
                row["normal_floor_headroom_usd_per_asset_day"])
            goal_headroom = float(row["goal_headroom_usd_per_asset_day"])
            valid_preflight = bool(
                valid_preflight
                and days > 0
                and math.isfinite(total)
                and math.isfinite(per_day)
                and total / days == per_day
                and floor == C.LOW_CAPACITY_ASSET_DAY_FLOOR_USD
                and normal_floor == C.WEAK_ASSET_DAY_FLOOR_USD
                and goal == C.TARGET_ASSET_DAY_USD
                and floor_headroom == per_day - floor
                and normal_headroom == per_day - normal_floor
                and goal_headroom == per_day - goal
                and bool(row.get("risk_exception_required"))
                    == (per_day < C.WEAK_ASSET_DAY_FLOOR_USD)
                and row.get("passed") is True
                and per_day >= C.LOW_CAPACITY_ASSET_DAY_FLOOR_USD
                and len(_sha(row.get("oracle_replay_receipt_sha256"),
                             f"{fold}/{asset} oracle replay")) == 64
                and capture == 1.0
            )
    except (KeyError, TypeError, ValueError, C.EntryV2Refusal):
        valid_preflight = False
    if not valid_preflight:
        raise C.EntryV2Refusal(f"{fold}: candidate/oracle preflight differs")
    if shuffled:
        if not control.startswith("SHUFFLED_"):
            raise C.EntryV2Refusal(f"{fold}: supplied null is not shuffled")
        null_control = receipt["null_control"]
        try:
            null_valid = bool(
                isinstance(null_control, Mapping)
                and null_control.get("schema")
                    == "entry-v2-stage-asset-day-shuffle-v2"
                and int(null_control["seed"]) == int(control.removeprefix("SHUFFLED_"))
                and int(null_control["selected_labels"]) > 0
                and int(null_control["within_asset_day_rows"]) >= 0
                and int(null_control["stage_asset_fallback_rows"]) >= 0
                and null_control.get("preserved_marginals")
                    == (
                        "stage,asset,action_loss_mask; "
                        "asset/day/mask where size>=2"
                    )
                and null_control.get("action_loss_mask") == "RECIPIENT_FIXED"
            )
        except (KeyError, TypeError, ValueError):
            null_valid = False
        if not null_valid:
            raise C.EntryV2Refusal(f"{fold}: shuffled-control contract differs")
    elif control != "PROPHET":
        raise C.EntryV2Refusal(f"{fold}: production fold is not PROPHET-trained")
    elif receipt["null_control"] != {
        "schema": "entry-v2-positive-control-v1", "control": "PROPHET"
    }:
        raise C.EntryV2Refusal(f"{fold}: positive-control contract differs")

    candidate_ids = tuple(result.candidate_ids)
    rows = len(candidate_ids)
    if rows == 0 or len(set(candidate_ids)) != rows:
        raise C.EntryV2Refusal(f"{fold}: empty or duplicate candidate output")
    assets = tuple(str(asset) for asset in result.assets)
    days = np.asarray(result.days)
    if (len(assets) != rows or days.shape != (rows,)
            or np.asarray(result.embeddings).shape[0] != rows):
        raise C.EntryV2Refusal(f"{fold}: candidate arrays are misaligned")
    if not np.issubdtype(days.dtype, np.integer):
        raise C.EntryV2Refusal(f"{fold}: candidate days are not integer d8 values")
    if set(assets) != set(C.ASSETS):
        raise C.EntryV2Refusal(f"{fold}: candidate rows do not contain all assets")
    if (set(result.arm_score_arrays) != set(arms)
            or set(result.arm_entry_scores) != set(arms)
            or set(result.arm_arrivals) != set(arms)
            or set(result.arm_thresholds) != set(arms)
            or set(result.arm_evaluations) != set(arms)):
        raise C.EntryV2Refusal(f"{fold}: result arm maps differ from its roster")
    for arm, score_arrays in result.arm_score_arrays.items():
        for value in score_arrays.values():
            if np.asarray(value).shape[0] != rows:
                raise C.EntryV2Refusal(
                    f"{fold}/{arm}: score array is misaligned"
                )
    score_sets = tuple(
        (result.arm_entry_scores[arm], result.arm_arrivals[arm], arm)
        for arm in arms
    ) + ((result.truth_scores, result.truth_arrivals, "truth"),)
    for scores, arrivals, label in score_sets:
        if len(scores) != rows or len(arrivals) != rows:
            raise C.EntryV2Refusal(f"{fold}: {label} rows are misaligned")
        if tuple(score.candidate_id for score in scores) != candidate_ids:
            raise C.EntryV2Refusal(f"{fold}: {label} score order differs")
        if tuple(row.score for row in arrivals) != tuple(scores):
            raise C.EntryV2Refusal(f"{fold}: {label} arrival score differs")
        if tuple(row.example.candidate_id for row in arrivals) != candidate_ids:
            raise C.EntryV2Refusal(f"{fold}: {label} arrival order differs")
    for index in range(rows):
        truth = result.truth_arrivals[index]
        if any(
            not _same_payload(result.arm_arrivals[arm][index], truth)
            for arm in arms
        ):
            raise C.EntryV2Refusal(
                f"{fold}: input/outcome differs across campaign arms"
            )

    sessions = tuple(result.expected_sessions)
    if not sessions or len(sessions) != len(set(sessions)):
        raise C.EntryV2Refusal(f"{fold}: empty or duplicate session denominator")
    by_day: dict[int, set[str]] = {}
    for session in sessions:
        C.guard_date(session.trading_day)
        if not C.is_denominator_day(session.asset, session.trading_day):
            raise C.EntryV2Refusal(
                f"{fold}: denominator contains a QRE2CAL1-excluded asset-day"
            )
        by_day.setdefault(session.trading_day, set()).add(session.asset)
    try:
        declared_days = tuple(int(day) for day in receipt["test_days_declared"])
    except (TypeError, ValueError):
        raise C.EntryV2Refusal(f"{fold}: declared test calendar is invalid")
    if (not declared_days or declared_days != tuple(sorted(set(declared_days)))
            or set(declared_days) != set(by_day)):
        raise C.EntryV2Refusal(
            f"{fold}: denominator differs from the declared test calendar"
        )
    incomplete: dict[int, list[str]] = {}
    for day, assets_on_day in by_day.items():
        expected_assets = {
            asset for asset in C.ASSETS
            if C.is_denominator_day(asset, day)
        }
        if assets_on_day != expected_assets:
            incomplete[day] = sorted(expected_assets - assets_on_day)
    if incomplete:
        raise C.EntryV2Refusal(
            f"{fold}: denominator omits declared eligible asset-days: "
            f"{list(incomplete.items())[:3]}"
        )

    try:
        receipt_regimes = tuple(sorted(
            AssetDayRegime(
                str(row["asset"]), int(row["trading_day"]),
                str(row["regime"]), int(row["availability_ts_ns"]),
            )
            for row in receipt["regime_declarations"]
        ))
    except (KeyError, TypeError, ValueError):
        raise C.EntryV2Refusal(f"{fold}: asset-day regime declarations are invalid")
    result_regimes = tuple(sorted(result.regime_declarations))
    expected_regime_keys = {
        (asset, day) for day in declared_days for asset in C.ASSETS
        if C.is_denominator_day(asset, day)
    }
    if (receipt_regimes != result_regimes
            or len(result_regimes) != len(expected_regime_keys)
            or {(row.asset, row.trading_day) for row in result_regimes}
                != expected_regime_keys):
        raise C.EntryV2Refusal(
            f"{fold}: causal weak-regime representation is unresolved"
        )

    expected = set(sessions)
    for row, asset, day in zip(result.scored_arrivals, assets, days.tolist()):
        if row.example.asset != asset or row.example.trading_day != int(day):
            raise C.EntryV2Refusal(f"{fold}: public candidate metadata differs")
        C.guard_date(int(day))
        if row.example.session not in expected:
            raise C.EntryV2Refusal(f"{fold}: candidate absent from denominator")
    era = {name: (lo, hi) for name, lo, hi in C.ERAS}[fold]
    if any(not era[0] <= day <= era[1] for day in by_day):
        raise C.EntryV2Refusal(f"{fold}: output day lies outside its named era")
    if (int(receipt["test_min_d8"]) != min(by_day)
            or int(receipt["test_max_d8"]) != max(by_day)):
        raise C.EntryV2Refusal(f"{fold}: receipt test range differs from denominator")
    if C.object_sha256(list(candidate_ids)) != receipt["test_candidate_sha256"]:
        raise C.EntryV2Refusal(f"{fold}: candidate population hash mismatch")
    _sha(receipt["arrays_sha256"], f"{fold} arrays")
    arrays_recomputed = True
    if _fold_array_hash(result) != receipt["arrays_sha256"]:
        raise C.EntryV2Refusal(f"{fold}: fold array hash mismatch")
    training_identity = fold_training_identity(result)
    if training_identity.training_receipt_sha256 != receipt["training_receipt_sha256"]:
        raise C.EntryV2Refusal(f"{fold}: training trace hash mismatch")
    if training_identity.normalizer_sha256 != receipt["normalizer_sha256"]:
        raise C.EntryV2Refusal(f"{fold}: normalizer hash mismatch")
    if training_identity.model_input_binding != binding:
        raise C.EntryV2Refusal(f"{fold}: model input binding differs")
    for thresholds, name in tuple(
        (result.arm_thresholds[arm], arm) for arm in arms
    ) + ((result.truth_thresholds_usd, "truth"),):
        if set(thresholds) != set(C.ASSETS) or any(
            not math.isfinite(float(value)) for value in thresholds.values()
        ):
            raise C.EntryV2Refusal(f"{fold}: {name} thresholds are incomplete")
    raw_arm_thresholds = receipt["arm_thresholds"]
    if (not isinstance(raw_arm_thresholds, Mapping)
            or tuple(raw_arm_thresholds) != arms):
        raise C.EntryV2Refusal(f"{fold}: arm threshold table differs")
    declared_thresholds = tuple(
        (_receipt_thresholds({"rows": raw_arm_thresholds[arm]}, "rows", fold),
         result.arm_thresholds[arm], arm)
        for arm in arms
    ) + ((
        _receipt_thresholds(receipt, "truth_inner_thresholds_usd", fold),
        result.truth_thresholds_usd,
        "truth",
    ),)
    for declared_threshold, actual_threshold, name in declared_thresholds:
        if any(declared_threshold[asset] != float(actual_threshold[asset])
               for asset in C.ASSETS):
            raise C.EntryV2Refusal(
                f"{fold}: {name} thresholds differ from fold receipt"
            )

    required_scores = {
        "action_p", "top3_p", "wall_p_upper", "expected_value_raw",
        "expected_value_lower", "expected_value_upper", "mae_q90",
    }
    for arm in arms:
        arrays = result.arm_score_arrays[arm]
        if not required_scores.issubset(arrays):
            raise C.EntryV2Refusal(f"{fold}/{arm}: score surface is incomplete")
        for index, asset in enumerate(assets):
            score = result.arm_entry_scores[arm][index]
            expected = {
                "priority_score": float(arrays["action_p"][index]),
                "take_probability": float(arrays["action_p"][index]),
                "expected_pnl_usd": float(arrays["expected_value_raw"][index]),
                "expected_pnl_lower_usd":
                    float(arrays["expected_value_lower"][index]),
                "top3_probability": float(arrays["top3_p"][index]),
                "mae_p90_usd": max(0.0, float(arrays["mae_q90"][index])),
                "wall_probability": float(arrays["wall_p_upper"][index]),
                "enter": bool(entry_decision_gate(
                    float(arrays["action_p"][index]),
                    float(result.arm_thresholds[arm][asset]),
                    float(arrays["expected_value_lower"][index]),
                    max(0.0, float(arrays["mae_q90"][index])),
                    float(arrays["wall_p_upper"][index]),
                    expected_pnl_upper_usd=float(
                        arrays["expected_value_upper"][index]
                    ),
                )),
            }
            if any(getattr(score, key) != value for key, value in expected.items()):
                raise C.EntryV2Refusal(
                    f"{fold}/{arm}: EntryScore was reinterpreted"
                )
    for index, asset in enumerate(assets):
        truth = result.truth_scores[index]
        if truth.enter != (
            bool(truth.take_probability)
            and truth.expected_pnl_usd
                >= float(result.truth_thresholds_usd[asset])
        ):
            raise C.EntryV2Refusal(f"{fold}: truth threshold/score mismatch")

    for arm in arms:
        _evaluation_equal(
            replay(result.arm_arrivals[arm], expected_sessions=sessions),
            result.arm_evaluations[arm], f"{fold}/{arm}",
        )
    _evaluation_equal(
        replay(result.truth_arrivals, expected_sessions=sessions),
        result.truth_evaluation, f"{fold}/truth",
    )
    ceiling = candidate_ceiling(result.truth_arrivals, expected_sessions=sessions)
    if ceiling != result.candidate_ceiling:
        raise C.EntryV2Refusal(f"{fold}: cached candidate ceiling differs")
    return {
        "fold": fold,
        "receipt_sha256": declared,
        "candidate_ids": candidate_ids,
        "candidate_days": frozenset(int(day) for day in days.tolist()),
        "session_days": frozenset(by_day),
        "sessions": frozenset(sessions),
        "regime_declarations": result_regimes,
        "arrays_recomputed": arrays_recomputed,
        "model_input_binding": binding,
        "arms": arms,
    }


def _rebind(rows: Iterable[ScoredArrival], model_hash: str) -> tuple[ScoredArrival, ...]:
    return tuple(ScoredArrival(
        row.example, replace(row.score, model_hash=model_hash), row.outcome
    ) for row in rows)


def _arrival_hash(rows: Sequence[ScoredArrival]) -> str:
    return C.object_sha256([{
        "candidate_id": row.example.candidate_id,
        "asset": row.example.asset,
        "trading_day": row.example.trading_day,
        "session_id": row.example.session_id,
        "decision_ts_ns": row.example.decision_ts_ns,
        "lineage_hash": row.example.lineage_hash,
        "prefix_source_hash": row.example.raw_prefix_ref.source_hash,
        "prefix_event_count": row.example.raw_prefix_ref.event_count,
        "model_hash": row.score.model_hash,
        "priority_score": row.score.priority_score,
        "take_probability": row.score.take_probability,
        "expected_pnl_usd": row.score.expected_pnl_usd,
        "expected_pnl_lower_usd": row.score.expected_pnl_lower_usd,
        "top3_probability": row.score.top3_probability,
        "mae_p90_usd": row.score.mae_p90_usd,
        "wall_probability": row.score.wall_probability,
        "enter": row.score.enter,
        "close_ts_ns": row.outcome.close_ts_ns,
        "close_pnl_usd": row.outcome.close_pnl_usd,
        "phase_close_ts_ns": row.outcome.phase_close_ts_ns,
        "phase_close_pnl_usd": row.outcome.phase_close_pnl_usd,
        "wall_hit_ts_ns": row.outcome.wall_hit_ts_ns,
        "wall_pnl_usd": row.outcome.wall_pnl_usd,
    } for row in rows])


def _asset_map(evaluation: EntryEvaluation) -> dict[str, AssetEvaluation]:
    out = {row.asset: row for row in evaluation.by_asset}
    if set(out) != set(C.ASSETS):
        raise C.EntryV2Refusal("campaign evaluation lacks SI/HG/NKD")
    return out


def _capture(value: AssetEvaluation, ceiling: AssetEvaluation) -> float:
    if ceiling.total_pnl_usd <= 0.0:
        return 0.0
    result = value.total_pnl_usd / ceiling.total_pnl_usd
    if result > 1.0:
        raise C.EntryV2Refusal("replay exceeds exact candidate ceiling")
    return float(result)


def _usd_per_asset_day(value: AssetEvaluation) -> float:
    if value.asset_days <= 0:
        raise C.EntryV2Refusal("campaign asset-day denominator is empty")
    if value.usd_per_asset_day != value.total_pnl_usd / value.asset_days:
        raise C.EntryV2Refusal("campaign asset-day metric is internally inconsistent")
    return value.usd_per_asset_day


_BOOTSTRAP_DRAWS = 2_000
_BOOTSTRAP_SEED = MappingProxyType({"SI": 17_201, "HG": 17_203, "NKD": 17_207})


def _asset_day_diagnostics(
    evaluation: EntryEvaluation,
    asset: str,
    regimes: Mapping[tuple[str, int], AssetDayRegime],
) -> dict[str, Any]:
    rows = tuple(sorted(
        (row for row in evaluation.asset_day_results if row.asset == asset),
        key=lambda row: row.trading_day,
    ))
    if not rows:
        raise C.EntryV2Refusal(f"{asset}: no asset-day diagnostics denominator")
    keys = {(asset, row.trading_day) for row in rows}
    if not keys.issubset(regimes):
        return {
            "resolved": False,
            "reason": "missing causal session-open regime declaration",
        }

    pnl = np.asarray([row.pnl_usd for row in rows], dtype=np.float64)
    positive = np.sort(np.maximum(pnl, 0.0))[::-1]
    positive_total = float(positive.sum())
    top_count = max(1, int(math.ceil(0.10 * len(positive))))
    concentration = {
        "positive_pnl_top_day_share": (
            float(positive[0] / positive_total) if positive_total > 0.0 else 0.0
        ),
        "positive_pnl_top_10pct_days_share": (
            float(positive[:top_count].sum() / positive_total)
            if positive_total > 0.0 else 0.0
        ),
        "top_10pct_day_count": top_count,
    }

    if len(pnl) == 1:
        ci_low = ci_high = float(pnl[0])
    else:
        rng = np.random.Generator(np.random.PCG64(_BOOTSTRAP_SEED[asset]))
        indexes = rng.integers(
            0, len(pnl), size=(_BOOTSTRAP_DRAWS, len(pnl)), endpoint=False
        )
        means = pnl[indexes].mean(axis=1)
        ci_low, ci_high = (
            float(value) for value in np.quantile(
                means, (0.025, 0.975), method="linear"
            )
        )

    weak_rows = tuple(
        row for row in rows if regimes[(asset, row.trading_day)].weak
    )
    unknown_rows = tuple(
        row for row in rows if not regimes[(asset, row.trading_day)].known
    )
    weak_usd = (
        sum(row.pnl_usd for row in weak_rows) / len(weak_rows)
        if weak_rows else None
    )

    latencies: list[int] = []
    censored = 0
    for index, row in enumerate(rows):
        weak = regimes[(asset, row.trading_day)].weak
        previous_weak = (
            index > 0 and regimes[(asset, rows[index - 1].trading_day)].weak
        )
        if not weak or previous_weak:
            continue
        found: int | None = None
        cursor = index
        while (cursor < len(rows)
               and regimes[(asset, rows[cursor].trading_day)].weak):
            if rows[cursor].pnl_usd > 0.0:
                found = cursor - index
                break
            cursor += 1
        if found is None:
            censored += 1
        else:
            latencies.append(found)

    return {
        "resolved": bool(weak_rows),
        "worst_asset_day_usd": float(pnl.min()),
        "zero_asset_days": sum(row.trades == 0 for row in rows),
        "zero_asset_day_rate": sum(row.trades == 0 for row in rows) / len(rows),
        "concentration": concentration,
        "day_clustered_mean_ci95_usd": {
            "lower": ci_low,
            "upper": ci_high,
            "draws": _BOOTSTRAP_DRAWS,
            "cluster": "trading_day",
        },
        "weak_regime": {
            "definition": "causal QRE2 SESSION regime_tag == LOW at session open",
            "asset_days": len(weak_rows),
            "usd_per_asset_day": weak_usd,
            "floor_usd_per_asset_day": C.WEAK_ASSET_DAY_FLOOR_USD,
            "passed": bool(
                weak_usd is not None
                and weak_usd >= C.WEAK_ASSET_DAY_FLOOR_USD
            ),
        },
        "unknown_regime": {
            "definition": (
                "typed UNKNOWN when no causal session-open LOW/MID/HIGH "
                "declaration is available; never imputed"
            ),
            "asset_days": len(unknown_rows),
            "usd_per_asset_day": (
                sum(row.pnl_usd for row in unknown_rows) / len(unknown_rows)
                if unknown_rows else None
            ),
        },
        "adaptation_latency": {
            "law": (
                "eligible asset-days from each LOW-regime run start to first "
                "strictly-positive asset-day; unresolved runs are censored"
            ),
            "observed_runs": len(latencies),
            "censored_runs": censored,
            "latencies_asset_days": latencies,
            "median_asset_days": (
                float(np.median(latencies)) if latencies else None
            ),
            "max_asset_days": max(latencies) if latencies else None,
        },
    }


def _metrics(
    arms: Mapping[str, EntryEvaluation],
    truth: EntryEvaluation,
    ceiling: CandidateCeiling,
    shuffled_arms: Mapping[str, EntryEvaluation] | None,
    regimes: Sequence[AssetDayRegime],
) -> dict[str, dict[str, Any]]:
    arm_names = tuple(arms)
    if (not arm_names or ARM_FULL_PREFIX not in arm_names
            or set(arm_names) != set(arms)):
        raise C.EntryV2Refusal("campaign metric input has an invalid arm roster")
    arms_by = {arm: _asset_map(value) for arm, value in arms.items()}
    truth_by = _asset_map(truth)
    ceiling_by = _asset_map(ceiling.evaluation)
    shuffled_by = (
        {arm: _asset_map(value) for arm, value in shuffled_arms.items()}
        if shuffled_arms is not None else None
    )
    regime_map = {(row.asset, row.trading_day): row for row in regimes}
    if len(regime_map) != len(regimes):
        raise C.EntryV2Refusal("campaign regime declarations are duplicated")
    out: dict[str, dict[str, Any]] = {}
    for asset in C.ASSETS:
        positive, upper = truth_by[asset], ceiling_by[asset]
        arm_metrics: dict[str, dict[str, float | int | None]] = {}
        for arm in arm_names:
            value = arms_by[arm][asset]
            null_value = (
                _usd_per_asset_day(shuffled_by[arm][asset])
                if shuffled_by is not None else None
            )
            arm_metrics[arm] = {
                "trades": value.trades,
                "usd_per_asset_day": _usd_per_asset_day(value),
                "usd_per_trade": value.usd_per_trade,
                "max_drawdown_usd": value.max_drawdown_usd,
                "drawdown_p90_usd": value.drawdown_p90_usd,
                "candidate_oracle_capture": _capture(value, upper),
                "shuffled_usd_per_asset_day": null_value,
                "lift_over_shuffled_usd_per_asset_day": (
                    _usd_per_asset_day(value) - null_value
                    if null_value is not None else None
                ),
                **_asset_day_diagnostics(arms[arm], asset, regime_map),
            }
        out[asset] = {
            "asset_days": arms_by[ARM_FULL_PREFIX][asset].asset_days,
            "arms": arm_metrics,
            "candidate_ceiling_usd_per_asset_day": _usd_per_asset_day(upper),
            "truth_usd_per_asset_day": _usd_per_asset_day(positive),
        }
    return out


def _era_policy_gate(
    folds: Sequence[FoldOOFResult],
) -> dict[str, dict[str, Any]]:
    """Evaluate every OOF era under the normal/low-capacity risk law."""
    out: dict[str, dict[str, Any]] = {asset: {} for asset in C.ASSETS}
    for result in folds:
        by_asset = _asset_map(result.arm_evaluations[ARM_FULL_PREFIX])
        ceiling_by_asset = _asset_map(result.candidate_ceiling.evaluation)
        preflight = result.receipt["candidate_oracle_preflight"]
        for asset in C.ASSETS:
            evaluation = by_asset[asset]
            per_day = _usd_per_asset_day(evaluation)
            drawdown = float(evaluation.max_drawdown_usd)
            oracle = float(preflight["per_asset"][asset]["usd_per_asset_day"])
            regime = _oracle_capacity_regime(oracle)
            floor = required_floor_usd(regime)
            floor_pass = per_day >= floor
            risk_pass = (drawdown < C.LOW_CAPACITY_MAX_DRAWDOWN_USD
                         if regime == "LOW" else True)
            capture = _capture(evaluation, ceiling_by_asset[asset])
            economics_pass = bool(
                evaluation.trades >= 10
                and evaluation.usd_per_trade >= C.MIN_EXPECTANCY_USD
                and math.isfinite(float(evaluation.drawdown_p90_usd))
                and 0.0 <= capture <= 1.0
            )
            capacity_receipt = C.object_sha256({
                "schema": "entry-v2-era-capacity-regime-v1",
                "fold": result.fold, "asset": asset,
                "oracle_usd_per_asset_day": oracle,
                "capacity_regime": regime, "required_floor": floor,
                "oracle_schedule_sha256": preflight["schedule_sha256"],
                "oracle_replay_receipt_sha256":
                    preflight["per_asset"][asset]["oracle_replay_receipt_sha256"],
            })
            out[asset][result.fold] = {
                "usd_per_asset_day": per_day,
                "chronological_max_drawdown_usd": drawdown,
                "oracle_usd_per_asset_day": oracle,
                "capacity_regime": regime,
                "capacity_authority_sha256": capacity_receipt,
                "required_floor_usd_per_asset_day": floor,
                "normal_floor_usd_per_asset_day":
                    C.WEAK_ASSET_DAY_FLOOR_USD,
                "low_capacity_floor_usd_per_asset_day":
                    C.LOW_CAPACITY_ASSET_DAY_FLOOR_USD,
                "risk_exception_max_drawdown_usd":
                    C.LOW_CAPACITY_MAX_DRAWDOWN_USD,
                "usd_per_trade": evaluation.usd_per_trade,
                "drawdown_p90_usd": evaluation.drawdown_p90_usd,
                "oracle_capture": capture,
                "values_clipped": False,
                "floor_pass": floor_pass,
                "risk_pass": risk_pass,
                "economics_pass": economics_pass,
                "passed": floor_pass and risk_pass and economics_pass,
            }
    if any(set(rows) != set(EXPECTED_FOLDS) for rows in out.values()):
        raise C.EntryV2Refusal("era policy gate is incomplete")
    return out


def _oracle_capacity_regime(oracle_usd_per_asset_day: float) -> str:
    return capacity_regime_from_oracle(oracle_usd_per_asset_day)


def _bottlenecks(
    metrics: Mapping[str, Mapping[str, Any]],
    raw: RawPrefixFidelityEvidence | None,
    teacher: TeacherAlignmentEvidence | None,
    shuffled_present: bool,
) -> dict[str, Any]:
    candidate_pass = all(
        all(float(row["oracle_usd_per_asset_day"])
            >= C.LOW_CAPACITY_ASSET_DAY_FLOOR_USD
            for row in metrics[asset]["era_gate"].values())
        for asset in C.ASSETS
    )
    candidate = {
        "resolved": True,
        "passed": candidate_pass,
        "evidence_type": "EXACT_CANDIDATE_ORACLE",
        "per_asset": {
            asset: {
                "usd_per_asset_day":
                    metrics[asset]["candidate_ceiling_usd_per_asset_day"],
                "capacity_regimes": {
                    fold: row["capacity_regime"]
                    for fold, row in metrics[asset]["era_gate"].items()
                },
                "capacity_authority_sha256": C.object_sha256({
                    fold: row["capacity_authority_sha256"]
                    for fold, row in metrics[asset]["era_gate"].items()
                }),
                "passed": all(row["oracle_usd_per_asset_day"]
                              >= C.LOW_CAPACITY_ASSET_DAY_FLOOR_USD
                              for row in metrics[asset]["era_gate"].values()),
            }
            for asset in C.ASSETS
        },
    }
    raw_boundary: dict[str, Any] = {
        "resolved": raw is not None,
        "passed": bool(raw is not None and raw.passed),
        "evidence_type": "EXACT_PREFIX_HASH_COUNT",
        "matched_events": (
            min(raw.expected_events, raw.observed_events) - raw.mismatched_events
            if raw is not None else 0
        ),
        "mismatched_events": raw.mismatched_events if raw is not None else 0,
    }
    if raw is not None:
        raw_boundary.update({
            "expected_events": raw.expected_events,
            "observed_events": raw.observed_events,
            "source_receipt_sha256": raw.source_receipt_sha256,
            "pack_receipt_sha256": raw.pack_receipt_sha256,
        })
    teacher_boundary: dict[str, Any] = {
        "resolved": teacher is not None,
        "passed": bool(teacher is not None and teacher.passed),
        "evidence_type": "EXACT_LABEL_JOIN",
        "matched_candidates": teacher.matched_candidates if teacher is not None else 0,
        "mismatched_candidates": (
            teacher.mismatched_candidates if teacher is not None else 0
        ),
    }
    if teacher is not None:
        teacher_boundary.update({
            "expected_candidates": teacher.expected_candidates,
            "teacher_receipt_sha256": teacher.teacher_receipt_sha256,
            "join_receipt_sha256": teacher.join_receipt_sha256,
        })
    # ``audit.py`` consumes this narrow boundary adapter under its historical
    # key names.  The value is the predetermined full-prefix arm; the campaign
    # receipt above remains the authoritative, explicitly named three-arm map.
    representation_metrics = {
        asset: {
            "direct_usd_per_asset_day":
                metrics[asset]["arms"][ARM_FULL_PREFIX]["usd_per_asset_day"],
            "shuffled_usd_per_asset_day":
                metrics[asset]["arms"][ARM_FULL_PREFIX]
                ["shuffled_usd_per_asset_day"],
            "arrival_oracle_capture":
                metrics[asset]["arms"][ARM_FULL_PREFIX]
                ["candidate_oracle_capture"],
            "direct_vs_shuffled_lift_usd_per_asset_day":
                metrics[asset]["arms"][ARM_FULL_PREFIX]
                ["lift_over_shuffled_usd_per_asset_day"],
            "shuffled_null_ceiling_usd_per_asset_day":
                C.SHUFFLED_NULL_CEILING_ASSET_DAY_USD,
        }
        for asset in C.ASSETS
    }
    representation_pass = shuffled_present and all(
        float(representation_metrics[asset]["direct_usd_per_asset_day"])
        > max(0.0, float(representation_metrics[asset]
                         ["shuffled_usd_per_asset_day"]))
        and 0.0 < float(representation_metrics[asset]
                        ["arrival_oracle_capture"]) <= 1.0
        and all(
            float(metrics[asset]["arms"][arm]["shuffled_usd_per_asset_day"])
                <= C.SHUFFLED_NULL_CEILING_ASSET_DAY_USD
            for arm in metrics[asset]["arms"]
        )
        for asset in C.ASSETS
    )
    representation = {
        "resolved": shuffled_present,
        "passed": representation_pass,
        "evidence_type": "EXACT_DIRECT_HEAD_OOF_REPLAY_DOLLARS",
        "per_asset": representation_metrics,
        "diagnostics": {},
    }
    oof_metrics = {
        asset: {**metrics[asset]["arms"][ARM_FULL_PREFIX],
                "era_capacity_gate": metrics[asset]["era_gate"]}
        for asset in C.ASSETS
    }
    policy_pass = shuffled_present and all(
        float(oof_metrics[asset]["usd_per_trade"]) >= C.MIN_EXPECTANCY_USD
        and float(oof_metrics[asset]["max_drawdown_usd"]) <= C.TARGET_MDD_USD
        and float(oof_metrics[asset]["usd_per_asset_day"])
            > max(0.0, float(oof_metrics[asset]["shuffled_usd_per_asset_day"]))
        and float(oof_metrics[asset]["shuffled_usd_per_asset_day"])
            <= C.SHUFFLED_NULL_CEILING_ASSET_DAY_USD
        and bool(oof_metrics[asset].get("resolved", False))
        and bool(oof_metrics[asset]["weak_regime"]["passed"])
        and all(bool(row["passed"])
                for row in metrics[asset]["era_gate"].values())
        for asset in C.ASSETS
    )
    exact_metrics = {
        asset: {
            **oof_metrics[asset],
            "candidate_oracle_capture": oof_metrics[asset]["candidate_oracle_capture"],
        }
        for asset in C.ASSETS
    }
    exact_pass = policy_pass and all(
        float(exact_metrics[asset]["candidate_oracle_capture"]) >= 0.90
        for asset in C.ASSETS
    )
    return {
        "candidate_ceiling": candidate,
        "raw_prefix_fidelity": raw_boundary,
        "teacher_alignment": teacher_boundary,
        "representation_learnability": representation,
        "oof_policy": {
            "resolved": shuffled_present,
            "passed": policy_pass,
            "evidence_type": "EXACT_GBT_OOF_REPLAY_DOLLARS",
            "per_asset": oof_metrics,
            "diagnostics": {},
        },
        "exact_replay": {
            "resolved": True,
            "passed": exact_pass,
            "evidence_type": "EXACT_ARRIVAL_REPLAY_DOLLARS_AND_ORACLE_CAPTURE",
            "per_asset": exact_metrics,
        },
    }


def build_oof_campaign(
    folds: Sequence[FoldOOFResult],
    *,
    raw_prefix_fidelity: RawPrefixFidelityEvidence | None,
    teacher_alignment: TeacherAlignmentEvidence | None,
    shuffled_folds: Sequence[FoldOOFResult] | None,
    diagnostic: bool = False,
) -> CampaignResult:
    """Verify and union the six E3-E8 development folds exactly once."""
    if not diagnostic and (
        raw_prefix_fidelity is None or teacher_alignment is None
        or shuffled_folds is None
    ):
        raise C.EntryV2Refusal(
            "production campaign requires raw-prefix, teacher, and shuffled evidence"
        )
    if raw_prefix_fidelity is not None:
        raw_prefix_fidelity.validate()
    if teacher_alignment is not None:
        teacher_alignment.validate()
    if not diagnostic and (
        not raw_prefix_fidelity.passed or not teacher_alignment.passed
    ):
        raise C.EntryV2Refusal(
            "production campaign requires passing raw-prefix and teacher evidence"
        )
    primary = tuple(folds)
    if len(primary) != len(EXPECTED_FOLDS):
        raise C.EntryV2Refusal("campaign requires exactly six OOF folds")
    if {result.fold for result in primary} != set(EXPECTED_FOLDS):
        raise C.EntryV2Refusal("campaign must contain E3..E8 exactly once")
    primary = tuple(sorted(primary, key=lambda result: int(result.fold[1:])))
    verified = tuple(_validate_fold(result, shuffled=False) for result in primary)
    arm_rosters = {tuple(item["arms"]) for item in verified}
    if len(arm_rosters) != 1:
        raise C.EntryV2Refusal("campaign mixes selected and legacy arm rosters")
    arms = next(iter(arm_rosters))
    binding_hashes = {
        item["model_input_binding"].binding_sha256 for item in verified
    }
    if len(binding_hashes) != 1:
        raise C.EntryV2Refusal("campaign folds use different model input bindings")
    model_input_binding = verified[0]["model_input_binding"]

    seen_days: set[int] = set()
    seen_candidates: set[str] = set()
    seen_sessions: set[SessionRef] = set()
    seen_regimes: dict[tuple[str, int], AssetDayRegime] = {}
    for item in verified:
        if seen_days.intersection(item["session_days"]):
            raise C.EntryV2Refusal("campaign folds reuse a test day")
        if seen_candidates.intersection(item["candidate_ids"]):
            raise C.EntryV2Refusal("campaign folds reuse a candidate")
        if seen_sessions.intersection(item["sessions"]):
            raise C.EntryV2Refusal("campaign folds reuse a session")
        seen_days.update(item["session_days"])
        seen_candidates.update(item["candidate_ids"])
        seen_sessions.update(item["sessions"])
        for row in item["regime_declarations"]:
            key = (row.asset, row.trading_day)
            if key in seen_regimes:
                raise C.EntryV2Refusal("campaign folds reuse an asset-day regime")
            seen_regimes[key] = row
    if teacher_alignment is not None and (
        not teacher_alignment.passed
        or teacher_alignment.expected_candidates < len(seen_candidates)
    ):
        raise C.EntryV2Refusal(
            "teacher evidence does not cover the campaign candidate subset"
        )

    shuffled: tuple[FoldOOFResult, ...] | None = None
    shuffled_verified: tuple[dict[str, Any], ...] = ()
    if shuffled_folds is not None:
        shuffled = tuple(shuffled_folds)
        if (len(shuffled) != len(EXPECTED_FOLDS)
                or {result.fold for result in shuffled} != set(EXPECTED_FOLDS)):
            raise C.EntryV2Refusal("shuffled control must contain E3..E8 exactly once")
        shuffled = tuple(sorted(shuffled, key=lambda result: int(result.fold[1:])))
        if len({result.control_name for result in shuffled}) != 1:
            raise C.EntryV2Refusal(
                "shuffled folds must use one campaign control identity"
            )
        shuffled_verified = tuple(
            _validate_fold(result, shuffled=True) for result in shuffled
        )
        if any(
            item["model_input_binding"] != model_input_binding
            for item in shuffled_verified
        ):
            raise C.EntryV2Refusal(
                "shuffled campaign model input binding differs"
            )
        if any(tuple(item["arms"]) != arms for item in shuffled_verified):
            raise C.EntryV2Refusal(
                "shuffled campaign arm roster differs from adopted winner"
            )
        for base, null, base_check, null_check in zip(
            primary, shuffled, verified, shuffled_verified
        ):
            if (base_check["candidate_ids"] != null_check["candidate_ids"]
                    or base_check["sessions"] != null_check["sessions"]
                    or base_check["regime_declarations"]
                        != null_check["regime_declarations"]
                    or not np.array_equal(base.days, null.days)
                    or base.assets != null.assets):
                raise C.EntryV2Refusal(
                    f"{base.fold}: shuffled control population differs"
                )
            for exact, control in zip(base.truth_arrivals, null.truth_arrivals):
                if not _same_payload(exact, control):
                    raise C.EntryV2Refusal(
                        f"{base.fold}: shuffled control changed truth population"
                    )

    family_payload = {
        "schema": "entry-v2-campaign-model-family-v4",
        "arms": list(arms),
        "model_input_binding": model_input_binding.as_dict(),
        "fold_receipts": {item["fold"]: item["receipt_sha256"]
                          for item in verified},
        "shuffled_fold_receipts": {
            item["fold"]: item["receipt_sha256"] for item in shuffled_verified
        },
    }
    family_digest = C.object_sha256(family_payload)
    model_family_hash = f"entry-v2-campaign:{family_digest}"
    arm_rows = {
        arm: _rebind(
            (row for result in primary for row in result.arm_arrivals[arm]),
            model_family_hash + ":" + arm,
        )
        for arm in arms
    }
    truth_rows = _rebind(
        (row for result in primary for row in result.truth_arrivals),
        model_family_hash + ":truth",
    )
    sessions = tuple(sorted(seen_sessions))
    arm_evaluations = {
        arm: replay(rows, expected_sessions=sessions)
        for arm, rows in arm_rows.items()
    }
    truth_eval = replay(truth_rows, expected_sessions=sessions)
    union_ceiling = candidate_ceiling(truth_rows, expected_sessions=sessions)
    fold_ceiling_ids = tuple(sorted(
        candidate_id for result in primary
        for candidate_id in result.candidate_ceiling.selected_candidate_ids
    ))
    if union_ceiling.selected_candidate_ids != fold_ceiling_ids:
        raise C.EntryV2Refusal("union ceiling differs across disjoint fold days")

    shuffled_arm_evaluations: dict[str, EntryEvaluation] | None = None
    shuffled_arm_rows: dict[str, tuple[ScoredArrival, ...]] = {}
    if shuffled is not None:
        shuffled_arm_rows = {
            arm: _rebind(
                (row for result in shuffled for row in result.arm_arrivals[arm]),
                model_family_hash + ":shuffled:" + arm,
            )
            for arm in arms
        }
        shuffled_arm_evaluations = {
            arm: replay(rows, expected_sessions=sessions)
            for arm, rows in shuffled_arm_rows.items()
        }
    metrics = _metrics(
        arm_evaluations, truth_eval, union_ceiling, shuffled_arm_evaluations,
        tuple(sorted(seen_regimes.values())),
    )
    era_gate = _era_policy_gate(primary)
    for asset in C.ASSETS:
        metrics[asset]["era_gate"] = era_gate[asset]
    boundaries = _bottlenecks(
        metrics, raw_prefix_fidelity, teacher_alignment,
        shuffled_arm_evaluations is not None,
    )
    if diagnostic:
        # Audit promotion is derived solely from this ordered boundary chain.
        # A diagnostic receipt may carry exact metrics, but it must remain
        # impossible to promote if it is later passed to the production audit.
        boundaries["exact_replay"]["resolved"] = False
        boundaries["exact_replay"]["passed"] = False
        boundaries["exact_replay"]["diagnostic_reason"] = (
            "diagnostic campaign is intentionally non-promotional"
        )
    goal_assets = {
        asset: {
            "usd_per_asset_day_pass":
                all(bool(row["passed"])
                    for row in metrics[asset]["era_gate"].values()),
            "usd_per_trade_pass":
                float(metrics[asset]["arms"][ARM_FULL_PREFIX]["usd_per_trade"])
                    >= C.MIN_EXPECTANCY_USD,
            "max_drawdown_pass":
                float(metrics[asset]["arms"][ARM_FULL_PREFIX]
                      ["max_drawdown_usd"]) <= C.TARGET_MDD_USD,
            "weak_regime_pass": bool(
                metrics[asset]["arms"][ARM_FULL_PREFIX].get("resolved", False)
                and metrics[asset]["arms"][ARM_FULL_PREFIX]
                    ["weak_regime"]["passed"]
            ),
            "era_capacity_risk_pass": all(
                bool(row["passed"])
                for row in metrics[asset]["era_gate"].values()
            ),
            "shuffled_null_pass": bool(
                shuffled_arm_evaluations is not None
                and all(
                    float(metrics[asset]["arms"][arm]
                          ["shuffled_usd_per_asset_day"])
                        <= C.SHUFFLED_NULL_CEILING_ASSET_DAY_USD
                    for arm in arms
                )
            ),
            "capture_pass":
                float(metrics[asset]["arms"][ARM_FULL_PREFIX]
                      ["candidate_oracle_capture"]) >= 0.90,
        }
        for asset in C.ASSETS
    }
    for values in goal_assets.values():
        values["passed"] = all(values.values())
    goal_pass = all(bool(values["passed"]) for values in goal_assets.values())
    promotion_ready = (not diagnostic and goal_pass
                       and all(bool(row["resolved"] and row["passed"])
                               for row in boundaries.values()))
    if not diagnostic and not promotion_ready:
        failed = next(
            (name for name, row in boundaries.items()
             if not bool(row["resolved"] and row["passed"])),
            "goal_gate",
        )
        raise C.EntryV2Refusal(
            f"production campaign failed exact promotion boundary: {failed}; "
            "rebuild with diagnostic=True to emit non-promotional evidence"
        )
    receipt: dict[str, Any] = {
        "schema": CAMPAIGN_SCHEMA,
        "kind": "DIAGNOSTIC" if diagnostic else "PRODUCTION",
        "scope": {
            "folds": list(EXPECTED_FOLDS),
            "max_trading_day": max(seen_days),
            "holdout_start_d8": C.HOLDOUT_START_D8,
            "h2_permits_accepted": False,
            "asset_days": len({
                (session.asset, session.trading_day) for session in sessions
            }),
            "candidates": len(seen_candidates),
        },
        "model_family_hash": model_family_hash,
        "model_family_payload": family_payload,
        "model_family_payload_sha256": family_digest,
        "model_input_binding": model_input_binding.as_dict(),
        "fold_results": [{
            "name": item["fold"],
            "receipt_sha256": item["receipt_sha256"],
            "test_days": sorted(item["session_days"]),
            "candidate_sha256": C.object_sha256(list(item["candidate_ids"])),
            "denominator_roster_sha256": C.object_sha256([
                [session.asset, session.trading_day, session.session_id]
                for session in sorted(item["sessions"])
            ]),
            "arm_thresholds": {
                arm: dict(primary[index].arm_thresholds[arm])
                for arm in arms
            },
            "truth_thresholds_usd": dict(primary[index].truth_thresholds_usd),
            "arrays_sha256_recomputed": bool(item["arrays_recomputed"]),
        } for index, item in enumerate(verified)],
        "input_sha256": {
            "arm_arrivals": {
                arm: _arrival_hash(arm_rows[arm]) for arm in arms
            },
            "truth_arrivals": _arrival_hash(truth_rows),
            "shuffled_arm_arrivals": (
                {arm: _arrival_hash(shuffled_arm_rows[arm])
                 for arm in arms}
                if shuffled_arm_rows else None
            ),
            "denominator_roster": C.object_sha256([
                [session.asset, session.trading_day, session.session_id]
                for session in sessions
            ]),
        },
        "candidate_ceiling": {
            "schedule_sha256": union_ceiling.schedule_sha256,
            "selected_candidate_sha256": C.object_sha256(
                list(union_ceiling.selected_candidate_ids)
            ),
        },
        "per_asset": metrics,
        "bottleneck_boundaries": boundaries,
        "goal_gate": {
            "thresholds": {
                "usd_per_asset_day_min":
                    C.TARGET_ASSET_DAY_USD,
                "usd_per_trade_min": C.MIN_EXPECTANCY_USD,
                "chronological_per_asset_max_drawdown_usd_max":
                    C.TARGET_MDD_USD,
                "drawdown_p90_usd": "diagnostic_only",
                "weak_regime_usd_per_asset_day_min":
                    C.WEAK_ASSET_DAY_FLOOR_USD,
                "low_capacity_era_usd_per_asset_day_min":
                    C.LOW_CAPACITY_ASSET_DAY_FLOOR_USD,
                "low_capacity_era_chronological_max_drawdown_usd_strictly_less_than":
                    C.LOW_CAPACITY_MAX_DRAWDOWN_USD,
                "shuffled_null_usd_per_asset_day_max":
                    C.SHUFFLED_NULL_CEILING_ASSET_DAY_USD,
                "candidate_ceiling_capture_min": 0.90,
            },
            "per_asset": goal_assets,
            "passed": goal_pass,
        },
        "promotion_ready": promotion_ready,
    }
    receipt["receipt_sha256"] = C.object_sha256(receipt)
    return CampaignResult(
        model_family_hash,
        MappingProxyType(arm_evaluations),
        truth_eval,
        (MappingProxyType(shuffled_arm_evaluations)
         if shuffled_arm_evaluations is not None else None),
        union_ceiling,
        MappingProxyType(receipt),
    )


def verify_campaign_receipt(receipt: Mapping[str, Any]) -> bool:
    if receipt.get("schema") != CAMPAIGN_SCHEMA:
        return False
    body = dict(receipt)
    declared = body.pop("receipt_sha256", None)
    try:
        family = body["model_family_payload"]
        binding = ModelInputBinding.from_mapping(body["model_input_binding"])
        family_binding = ModelInputBinding.from_mapping(
            family["model_input_binding"]
        )
        if family_binding != binding:
            return False
        family_digest = C.object_sha256(family)
        return (
            _sha(declared, "campaign receipt") == C.object_sha256(body)
            and _sha(body["model_family_payload_sha256"], "model family")
            == family_digest
            and body["model_family_hash"]
            == f"entry-v2-campaign:{family_digest}"
        )
    except (C.EntryV2Refusal, KeyError, TypeError):
        return False


def require_neural_sufficiency_adoption(
    acceptance_path: os.PathLike[str] | str, e1_path: os.PathLike[str] | str,
    e2_path: os.PathLike[str] | str, e3_path: os.PathLike[str] | str,
    adoption_path: os.PathLike[str] | str,
    winner_bundle_path: os.PathLike[str] | str,
    integration_path: os.PathLike[str] | str,
) -> Mapping[str, Any]:
    """Mandatory bridge from fit-only neural acceptance to legacy OOF adoption."""
    from .neural_sufficiency_runner import (
        load_acceptance_receipt, load_stage_receipt, load_winner_adoption,
    )
    from .neural_winner_artifact import load_winner_bundle, load_winner_integration
    try:
        receipt = load_acceptance_receipt(acceptance_path)
        e1, e2, e3 = (load_stage_receipt(path) for path in (e1_path, e2_path, e3_path))
        adoption = load_winner_adoption(adoption_path)
        bundle = load_winner_bundle(
            winner_bundle_path, expected_adoption_sha256=adoption.adoption_sha256
        )
        integration = load_winner_integration(integration_path)
    except Exception as error:
        raise C.EntryV2Refusal(
            "old campaign/legacy probes are blocked without fit-only neural acceptance"
        ) from error
    if ("threshold" not in receipt.component_artifacts
            or "canonical_replay" not in receipt.component_artifacts
            or "finalize" not in receipt.component_artifacts):
        raise C.EntryV2Refusal("neural acceptance lacks frozen selection/replay/finalizer")
    if ((e1.mode, e2.mode, e3.mode) != ("E1", "E2", "E3")
            or e1.acceptance_sha256 != receipt.acceptance_sha256
            or any(stage.diagnostic_evidence_sha256
                   != receipt.diagnostic_evidence_sha256
                   for stage in (e1, e2, e3))
            or e2.prior_stage_sha256 != e1.stage_sha256
            or e3.prior_stage_sha256 != e2.stage_sha256
            or adoption.acceptance_sha256 != receipt.acceptance_sha256
            or adoption.e1_stage_sha256 != e1.stage_sha256
            or adoption.e2_stage_sha256 != e2.stage_sha256
            or adoption.e3_stage_sha256 != e3.stage_sha256
            or adoption.diagnostic_evidence_sha256
                != receipt.diagnostic_evidence_sha256
            or dict(adoption.frozen_selection) != dict(e3.frozen_selection)):
        raise C.EntryV2Refusal("neural acceptance/E1/E2/E3/winner chain differs")
    if (adoption.integration_ready
            or integration.pending_adoption_sha256 != adoption.adoption_sha256
            or integration.winner_bundle_sha256 != bundle.bundle_sha256
            or dict(integration.frozen_selection) != dict(adoption.frozen_selection)):
        raise C.EntryV2Refusal(
            "selected neural winner lacks the immutable READY integration transition"
        )
    return MappingProxyType({
        "schema": receipt.schema, "acceptance_sha256": receipt.acceptance_sha256,
        "diagnostic_evidence_sha256": receipt.diagnostic_evidence_sha256,
        "corpus_sha256": receipt.corpus_sha256,
        "chronology_sha256": receipt.chronology_sha256,
        "threshold_artifact_sha256": receipt.component_artifacts["threshold"],
        "replay_artifact_sha256": receipt.component_artifacts["canonical_replay"],
        "e1_stage_sha256": e1.stage_sha256, "e2_stage_sha256": e2.stage_sha256,
        "e3_stage_sha256": e3.stage_sha256,
        "winner_adoption_sha256": adoption.adoption_sha256,
        "winner_bundle_sha256": bundle.bundle_sha256,
        "winner_integration_sha256": integration.integration_sha256,
        "winner_arm": bundle.arm,
        "winner_objective_sha256": bundle.selection["selected_objective_sha256"],
        "e2_frozen_selection_sha256": C.object_sha256(dict(e2.frozen_selection)),
        "primary_e3_fold_sha256": bundle.primary_e3_fold_sha256,
        "winner_target_row_manifest_sha256":
            bundle.objective["target_row_manifest_sha256"],
        "capacity_authority_sha256": bundle.files["capacity.json"],
        "target_provider_factory_sha256":
            integration.target_provider_factory_sha256,
        "receipt_only_adoption": False,
        "frozen_selection": dict(adoption.frozen_selection),
        "legacy_ranking_probe_adopted": False,
        "legacy_representation_probe_adopted": False,
    })


def write_campaign_receipt(
    result: CampaignResult, path: os.PathLike[str] | str
) -> str:
    if not verify_campaign_receipt(result.receipt):
        raise C.EntryV2Refusal("refusing to write an invalid campaign receipt")
    target = C.assert_workspace_output(path)
    C.guard_payload(target)
    return C.atomic_json(target, dict(result.receipt))
