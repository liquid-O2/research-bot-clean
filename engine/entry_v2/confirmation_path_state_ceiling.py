"""Exact CatBoost acceptance ceiling with Oracle timing only.

The learned score decides which candidates are accepted.  Every accepted
candidate is forced to trade at its best fully observed delayed row, including
when that best row loses money.  Oracle timing therefore cannot silently turn
a bad acceptance decision into a pass.  This is a nondeployable model ceiling,
not threshold selection.
"""

from __future__ import annotations

from typing import Final, Mapping, Sequence

import numpy as np

from . import common as C
from .confirmation import ConfirmationDataset, ConfirmationRefusal
from .confirmation_acceptance_mechanism import asset_day_groups
from .confirmation_dynamic_hurdle_policy import (
    _arrival, _evaluation_summary, _sparse_schedule_ceiling,
)
from .confirmation_fixed_horizon import fixed_horizon_target, ordered_series_groups
from .confirmation_path_state import PathStateLandmark
from .confirmation_stopping import OracleActionLedger
from .contracts import SessionRef
from .replay import replay


SCHEMA: Final = "QRE2CONFPATHSTATECEILING2"


def _oracle_time_rows(
    conditional: ConfirmationDataset, ledger: OracleActionLedger,
    landmark: PathStateLandmark,
) -> Mapping[str, int]:
    horizon = fixed_horizon_target(
        conditional, ledger, landmark.target.horizon_sec)
    series = np.asarray(conditional.series_id, str)
    timestamp = np.asarray(conditional.snapshot_ts_ns, np.int64)
    q_enter = np.asarray(ledger.q_enter_usd, np.float64)
    landmark_time = {str(key): int(value) for key, value in zip(
        landmark.dataset.series_id, landmark.dataset.snapshot_ts_ns)}
    target_value = {str(key): float(value) for key, value in zip(
        landmark.dataset.series_id, landmark.target.value_usd)}
    target_time = {str(key): int(value) for key, value in zip(
        landmark.dataset.series_id, landmark.target.best_snapshot_ts_ns)}
    result = {}
    for ordered in ordered_series_groups(series, timestamp):
        key = str(series[ordered[0]])
        if key not in landmark_time:
            continue
        eligible = ordered[
            (timestamp[ordered] >= landmark_time[key])
            & np.asarray(horizon.eligible[ordered], bool)]
        if not len(eligible):
            raise ConfirmationRefusal("path-state ceiling action is censored")
        chosen = int(eligible[int(np.argmax(q_enter[eligible]))])
        if (abs(float(q_enter[chosen]) - target_value[key]) > 1e-7
                or int(timestamp[chosen]) != target_time[key]):
            raise ConfirmationRefusal("path-state ceiling target/action differs")
        result[key] = chosen
    if set(result) != set(landmark_time):
        raise ConfirmationRefusal("path-state ceiling action roster differs")
    return result


def _topk_series(
    landmark: PathStateLandmark, score: np.ndarray,
    roster: Sequence[str], topk: int,
) -> tuple[str, ...]:
    values = np.asarray(score, np.float64)
    if (values.shape != (len(landmark.dataset.features),)
            or not np.all(np.isfinite(values)) or not 1 <= topk <= 12):
        raise ConfirmationRefusal("path-state ceiling score differs")
    wanted = set(map(str, roster)); series = np.asarray(
        landmark.dataset.series_id, str)
    mask = np.isin(series, tuple(wanted))
    if set(series[mask].tolist()) != wanted:
        raise ConfirmationRefusal("path-state ceiling learned roster differs")
    groups = asset_day_groups(landmark.dataset); selected = []
    for group in sorted(set(groups[mask].tolist())):
        local = np.flatnonzero(mask & (groups == group))
        order = local[np.lexsort((series[local], -values[local]))]
        selected.extend(series[order[:topk]].tolist())
    return tuple(sorted(set(map(str, selected))))


def _scorecards(
    conditional: ConfirmationDataset, landmark: PathStateLandmark,
    score: np.ndarray, roster: Sequence[str], action_rows: Mapping[str, int],
    sessions: Sequence[SessionRef], *, arm: str, evaluation_scope: str,
) -> Mapping[str, object]:
    cards = []
    q_by_series = {str(key): float(value) for key, value in zip(
        landmark.dataset.series_id, landmark.target.value_usd)}
    series = np.asarray(landmark.dataset.series_id, str)
    values = np.asarray(score, np.float64)

    def price(selected: Sequence[str], **parameters: object) \
            -> Mapping[str, object]:
        selected = tuple(sorted(set(map(str, selected))))
        arrivals = tuple(_arrival(
            conditional, action_rows[key],
            model_hash=f"path-state-ceiling-{arm.lower()}",
            expected_pnl_usd=q_by_series[key],
            pnl_q20_usd=q_by_series[key],
            goal_probability=float(q_by_series[key] >= 600.0),
            wall_probability=float(q_by_series[key] <= -900.0),
            mae_q90_usd=float(conditional.mae_usd[action_rows[key]]),
        ) for key in selected)
        evaluation = replay(arrivals, expected_sessions=sessions)
        card = {
            **parameters, "accepted_candidates": len(selected),
            "evaluation": _evaluation_summary(evaluation, sessions),
        }
        return {**card, "receipt_sha256": C.object_sha256(card)}

    for topk in range(1, 13):
        selected = _topk_series(landmark, score, roster, topk)
        cards.append(price(
            selected, selection_family="FIXED_TOPK_PER_ASSET_DAY",
            topk_per_asset_day=topk))

    # This is the nondeployable CatBoost score ceiling: it asks whether any
    # global cutoff in the learned score can separate economic candidates.
    # Every selected false positive remains a forced trade in exact replay.
    wanted = set(map(str, roster))
    local = np.flatnonzero(np.isin(series, tuple(wanted)))
    order = local[np.lexsort((series[local], -values[local]))]
    for accepted_count in range(1, len(order) + 1):
        cutoff = float(values[order[accepted_count - 1]])
        if (accepted_count < len(order)
                and values[order[accepted_count]] == cutoff):
            continue
        cards.append(price(
            series[order[:accepted_count]],
            selection_family="GLOBAL_SCORE_CUTOFF_CEILING",
            score_cutoff=cutoff))
    selected = min(cards, key=lambda row: (
        -float(row["evaluation"]["total_pnl_usd"]),
        int(row["accepted_candidates"]),
        str(row["selection_family"])))
    core = {
        "arm": arm,
        "selection_scope": f"{evaluation_scope}_MODEL_CEILING_NOT_DEPLOYABLE",
        "selected": selected, "scorecards": tuple(cards),
    }
    return {**core, "receipt_sha256": C.object_sha256(core)}


def run_path_state_acceptance_ceiling(
    conditional: ConfirmationDataset, ledger: OracleActionLedger,
    landmark: PathStateLandmark, sessions: Sequence[SessionRef], *,
    roster: Sequence[str], real_score: np.ndarray,
    control_score: np.ndarray, evaluation_scope: str = "PLATT_UNTOUCHED",
) -> Mapping[str, object]:
    """Measure learned candidate selection with losses and exact replay."""

    conditional.validate(); ledger.validate(); landmark.validate(conditional)
    if evaluation_scope not in {"FIT_CHRONOLOGICAL_OOF", "PLATT_UNTOUCHED"}:
        raise ConfirmationRefusal("path-state ceiling scope differs")
    if (ledger.source_representation_sha256
            != conditional.representation_sha256
            or not sessions or len(set(sessions)) != len(tuple(sessions))):
        raise ConfirmationRefusal("path-state ceiling source identity differs")
    action_rows = _oracle_time_rows(conditional, ledger, landmark)
    oracle_score = np.asarray(landmark.target.value_usd, np.float64)
    arms = {
        "REAL": _scorecards(
            conditional, landmark, real_score, roster, action_rows, sessions,
            arm="REAL", evaluation_scope=evaluation_scope),
        "CONTROL": _scorecards(
            conditional, landmark, control_score, roster, action_rows,
            sessions, arm="CONTROL", evaluation_scope=evaluation_scope),
        "ORACLE": _scorecards(
            conditional, landmark, oracle_score, roster, action_rows,
            sessions, arm="ORACLE", evaluation_scope=evaluation_scope),
    }
    roster_mask = np.isin(np.asarray(conditional.series_id, str),
                          tuple(map(str, roster)))
    roster_dataset = conditional.subset(roster_mask)
    frozen_ceiling = _sparse_schedule_ceiling(roster_dataset, sessions)
    denominator = float(
        frozen_ceiling["evaluation"]["total_pnl_usd"])
    for name, arm in tuple(arms.items()):
        capture = (0.0 if denominator <= 0 else
                   float(arm["selected"]["evaluation"]["total_pnl_usd"])
                   / denominator)
        core = {key: value for key, value in arm.items()
                if key != "receipt_sha256"}
        core["capture_of_frozen_sparse_roster_ceiling"] = capture
        arms[name] = {**core, "receipt_sha256": C.object_sha256(core)}
    real_capture = float(
        arms["REAL"]["capture_of_frozen_sparse_roster_ceiling"])
    control_capture = float(
        arms["CONTROL"]["capture_of_frozen_sparse_roster_ceiling"])
    core = {
        "schema": SCHEMA,
        "scope": "CATBOOST_ACCEPTANCE_WITH_ORACLE_TIMING_MODEL_CEILING",
        "evaluation_scope": evaluation_scope,
        "forced_trade_for_every_accepted_candidate": True,
        "oracle_timing_can_pass_candidate": False,
        "landmark_delay_sec": landmark.landmark_delay_sec,
        "target_horizon_sec": landmark.target.horizon_sec,
        "frozen_sparse_roster_ceiling": frozen_ceiling,
        "arms": arms,
        "real_capture": real_capture,
        "control_capture": control_capture,
        "real_gain_over_control": real_capture - control_capture,
        "passes_80_percent": real_capture >= .80,
        "selection_is_deployable": False,
        "threshold_open_count": 0, "forward_open_count": 0,
        "h2_open_count": 0,
    }
    return {**core, "receipt_sha256": C.object_sha256(core)}


__all__ = [
    "SCHEMA", "run_path_state_acceptance_ceiling",
]
