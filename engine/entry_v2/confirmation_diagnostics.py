"""Cheap economic falsifiers for the tabular confirmation lane.

These checks diagnose formulation, representation, and generalization.  They
do not replace the authoritative E1r/E2r production-path rehearsal.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import math
from types import MappingProxyType
from typing import Iterable, Mapping, Sequence

import numpy as np

from . import common as C
from .capacity_contract import (
    CapacityEligibility, FitOnlyGoalRecovery, ThresholdFeasibility,
    capacity_eligibility, capacity_regime_from_oracle, fit_only_goal_recovery,
    threshold_feasibility,
)
from .confirmation import (
    ConfirmationDataset, ConfirmationOpportunitySet, ConfirmationRefusal,
)
from .confirmation_model import ConfirmationModel, ConfirmationPredictions
from .confirmation_policy import (
    ConfirmationPolicy, DelayedCandidateCeiling,
    confirmation_series_time_order, exact_delayed_candidate_ceiling,
    replay_confirmation,
)
from .contracts import EntryEvaluation, SessionRef


DIAGNOSTIC_SCHEMA = "QRE2CONFDIAG1"


def registered_feature_sets(
    feature_names: Sequence[str],
) -> Mapping[str, np.ndarray]:
    """Frozen nested tabular representations used by the learning curve.

    The small sets separate native candidate context from confirmation state;
    ``MAX_W300`` adds every causal raw-stream statistic whose lookback is no
    longer than the permitted five-minute confirmation horizon.
    """

    names = tuple(map(str, feature_names))
    if not names or len(names) != len(set(names)):
        raise ConfirmationRefusal("feature-set source schema is empty/duplicated")
    formation = np.asarray([
        name.startswith("asset_") or name in {
            "side", "phase_index", "candidate_count"}
        or name.startswith("formation_")
        or name.startswith("spread_prior_")
        or name.startswith("fast_open_")
        or name.startswith("rung_")
        or name.startswith("disc_auction_")
        or name.startswith("disc_memory_")
        or name.startswith("disc_fvol_")
        or name.startswith("disc_regime_")
        or name.startswith("disc_target_")
        or name.startswith("disc_origin_")
        or name.startswith("disc_prior_")
        or name.startswith("ctx_")
        for name in names], bool)
    clock = formation | np.isin(names, (
        "min_alert_age_sec", "max_alert_age_sec", "phase_remaining_sec"))
    current_book = clock | np.isin(names, (
        "current_spread_usd", "current_cost_usd", "current_bid_size",
        "current_ask_size", "current_size_imbalance",
        "current_count_imbalance"))
    reclaim = current_book | np.asarray([
        name.startswith("aligned_from_formation_") for name in names], bool)
    level_state = reclaim | np.asarray([
        name.startswith("disc_level_")
        or name.startswith("disc_current_")
        or name.startswith("disc_state_")
        or name.startswith("disc_evt_")
        or name.startswith("disc_eclock_")
        or name.startswith("disc_tclock_")
        or name.startswith("disc_vclock_")
        or name.startswith("disc_tape_")
        or name.startswith("disc_test_")
        or name.startswith("disc_quote_")
        or name.startswith("disc_behavior_")
        or name.startswith("disc_ib_")
        or name.startswith("disc_footprint_")
        or name.startswith("disc_mhi_")
        or name.startswith("disc_absorption_")
        or name.startswith("disc_path_")
        or name in {"disc_level_association_destroyed",
                    "disc_fill_coupling_destroyed"}
        for name in names], bool)
    max_w300 = level_state.copy()
    allowed_windows = {"w1", "w5", "w15", "w30", "w60", "w120", "w300"}
    for index, name in enumerate(names):
        if name.split("_", 1)[0] in allowed_windows:
            max_w300[index] = True
    max_plus_episode = max_w300 | np.asarray([
        name.startswith("episode_") for name in names], bool)
    max_plus_ordered = max_plus_episode | np.asarray([
        name.startswith("ord_") for name in names], bool)
    masks = {
        "FORMATION_ONLY": formation,
        "PLUS_CLOCK": clock,
        "PLUS_CURRENT_BOOK": current_book,
        "PLUS_RECLAIM": reclaim,
        "PLUS_LEVEL_STATE": level_state,
        "MAX_W300": max_w300,
        "MAX_PLUS_EPISODE": max_plus_episode,
        "MAX_PLUS_ORDERED": max_plus_ordered,
        "FULL": np.ones(len(names), bool),
    }
    counts = [int(mask.sum()) for mask in masks.values()]
    if (any(count <= 0 for count in counts)
            or counts != sorted(counts)
            or any(mask.shape != (len(names),) for mask in masks.values())):
        raise ConfirmationRefusal("registered feature sets are not nested/valid")
    return MappingProxyType(masks)


def registered_policy_grid(max_delay_sec: int = 300) -> tuple[ConfirmationPolicy, ...]:
    """Small fixed grid; threshold discovery never invents cutoffs post-result."""

    if max_delay_sec not in (300, 600):
        raise ConfirmationRefusal("policy grid expiry must be 300 or 600 seconds")
    rows = []
    for expected in (0.0, 300.0, 600.0, 900.0):
        for lower in (-600.0, -300.0, 0.0, 300.0):
            # Goal-grade outcomes are sparse (roughly 8--16% in the initial
            # development census), so calibrated probabilities are not
            # expected to cross a generic 0.5 classification cutoff.  Economic
            # feasibility below remains unchanged and decides admissibility.
            for goal in (0.05, 0.10, 0.15, 0.20, 0.25, 0.30):
                for wall in (0.05, 0.10, 0.15, 0.25, 0.35):
                    rows.append(ConfirmationPolicy(
                        expected, lower, goal, wall,
                        max_mae_q90_usd=900.0,
                        min_alert_age_sec=0.0,
                        max_alert_age_sec=float(max_delay_sec)))
    # Explicit confirmation deferrals.  Keep the original age-zero grid and
    # add a smaller nested score grid at later causal ages; this tests the
    # user's wait-for-confirmation rule without multiplying every weak tail
    # combination sevenfold.
    for minimum_age in (15.0, 30.0, 60.0, 120.0, 180.0, 240.0):
        for expected in (0.0, 300.0, 600.0):
            for lower in (-600.0, -300.0, 0.0):
                for goal in (0.05, 0.10, 0.20, 0.30):
                    for wall in (0.05, 0.10, 0.20, 0.35):
                        rows.append(ConfirmationPolicy(
                            expected, lower, goal, wall,
                            max_mae_q90_usd=900.0,
                            min_alert_age_sec=minimum_age,
                            max_alert_age_sec=float(max_delay_sec)))
    return tuple(rows)


@dataclass(frozen=True, slots=True)
class PolicyScorecard:
    policy: ConfirmationPolicy
    total_pnl_usd: float | None
    usd_per_asset_day: float | None
    trades: int
    days_with_trades: int
    max_drawdown_usd: float | None
    feasible: bool
    reasons: tuple[str, ...]
    receipt_sha256: str


@dataclass(frozen=True, slots=True)
class PolicySelection:
    selected: ConfirmationPolicy
    selected_evaluation: EntryEvaluation
    feasible_scorecards: tuple[PolicyScorecard, ...]
    all_scorecards: tuple[PolicyScorecard, ...]
    receipt_sha256: str


@dataclass(frozen=True, slots=True)
class PolicyGridEvaluation:
    """Complete threshold evidence, including a typed all-failed result."""

    status: str
    selected: ConfirmationPolicy | None
    selected_evaluation: EntryEvaluation | None
    feasible_scorecards: tuple[PolicyScorecard, ...]
    all_scorecards: tuple[PolicyScorecard, ...]
    receipt_sha256: str

    def __post_init__(self) -> None:
        selected = self.status == "SELECTED"
        if (self.status not in {"SELECTED", "NO_FEASIBLE_THRESHOLD"}
                or selected != (self.selected is not None)
                or selected != (self.selected_evaluation is not None)
                or selected != bool(self.feasible_scorecards)
                or not self.all_scorecards):
            raise ConfirmationRefusal("policy grid result is malformed")


def _days_with_trades(evaluation: EntryEvaluation) -> int:
    return sum(row.trades > 0 for row in evaluation.asset_day_results)


def score_confirmation_policies(
    dataset: ConfirmationDataset,
    predictions: ConfirmationPredictions,
    *, expected_sessions: Iterable[SessionRef],
    policies: Sequence[ConfirmationPolicy] | None = None,
) -> PolicyGridEvaluation:
    """Score the whole fixed grid and preserve evidence when all policies fail."""

    sessions = tuple(expected_sessions)
    if not sessions:
        raise ConfirmationRefusal("threshold selection denominator is empty")
    grid = tuple(policies or registered_policy_grid(dataset.max_delay_sec))
    if not grid or len({row.receipt_sha256 for row in grid}) != len(grid):
        raise ConfirmationRefusal("threshold grid is empty or duplicated")
    scorecards: list[PolicyScorecard] = []
    evaluations: dict[str, EntryEvaluation] = {}
    series_order = confirmation_series_time_order(dataset)
    for policy in grid:
        try:
            evaluation = replay_confirmation(
                dataset, predictions, policy, expected_sessions=sessions,
                series_time_order=series_order)
        except ConfirmationRefusal as exc:
            card = PolicyScorecard(
                policy, None, None, 0, 0, None, False, (str(exc),),
                C.object_sha256({"schema": DIAGNOSTIC_SCHEMA,
                                 "policy": policy.receipt_sha256,
                                 "reasons": (str(exc),)}))
            scorecards.append(card)
            continue
        days = _days_with_trades(evaluation)
        feasibility = threshold_feasibility(
            trades=evaluation.trades, usd_per_trade=evaluation.usd_per_trade,
            max_drawdown_usd=evaluation.max_drawdown_usd,
            days_with_trades=days, eligible_days=evaluation.asset_days)
        card = PolicyScorecard(
            policy, evaluation.total_pnl_usd, evaluation.usd_per_asset_day,
            evaluation.trades, days, evaluation.max_drawdown_usd,
            feasibility.feasible, feasibility.reasons,
            C.object_sha256({
                "schema": DIAGNOSTIC_SCHEMA,
                "policy": policy.receipt_sha256,
                "total_pnl_usd": evaluation.total_pnl_usd,
                "usd_per_asset_day": evaluation.usd_per_asset_day,
                "trades": evaluation.trades,
                "days_with_trades": days,
                "max_drawdown_usd": evaluation.max_drawdown_usd,
                "threshold_feasibility": feasibility.receipt_sha256,
            }))
        scorecards.append(card); evaluations[policy.receipt_sha256] = evaluation
    feasible = tuple(row for row in scorecards if row.feasible)
    best = (None if not feasible else min(feasible, key=lambda row: (
        -float(row.total_pnl_usd), float(row.max_drawdown_usd),
        row.policy.receipt_sha256)))
    selection_receipt = C.object_sha256({
        "schema": "QRE2CONFPOLSEL1",
        "dataset": dataset.representation_sha256,
        "model": predictions.model_hash,
        "grid": tuple(row.policy.receipt_sha256 for row in scorecards),
        "scorecards": tuple(row.receipt_sha256 for row in scorecards),
        "status": "SELECTED" if best is not None else "NO_FEASIBLE_THRESHOLD",
        "selected": None if best is None else best.policy.receipt_sha256,
    })
    return PolicyGridEvaluation(
        "SELECTED" if best is not None else "NO_FEASIBLE_THRESHOLD",
        None if best is None else best.policy,
        None if best is None else evaluations[best.policy.receipt_sha256],
        feasible, tuple(scorecards), selection_receipt)


def select_confirmation_policy(
    dataset: ConfirmationDataset,
    predictions: ConfirmationPredictions,
    *, expected_sessions: Iterable[SessionRef],
    policies: Sequence[ConfirmationPolicy] | None = None,
) -> PolicySelection:
    """Select only among policies clearing the absolute capacity laws."""

    scored = score_confirmation_policies(
        dataset, predictions, expected_sessions=expected_sessions,
        policies=policies)
    if scored.status != "SELECTED":
        raise ConfirmationRefusal("no registered confirmation policy clears threshold laws")
    assert scored.selected is not None and scored.selected_evaluation is not None
    return PolicySelection(
        scored.selected, scored.selected_evaluation,
        scored.feasible_scorecards, scored.all_scorecards,
        scored.receipt_sha256)


@dataclass(frozen=True, slots=True)
class BlockDiagnostic:
    block_name: str
    evaluation: EntryEvaluation
    ceiling: DelayedCandidateCeiling
    threshold_feasibility: ThresholdFeasibility
    capacity_eligibility: CapacityEligibility
    goal_recovery: FitOnlyGoalRecovery
    portfolio_days: int
    usd_per_portfolio_day: float
    result_band: str
    receipt_sha256: str


def _result_band(usd_per_portfolio_day: float) -> str:
    if usd_per_portfolio_day < 3_000.0:
        return "FAIL_BELOW_3000"
    if usd_per_portfolio_day < 6_000.0:
        return "VIABLE_3000_TO_5999"
    if usd_per_portfolio_day < 7_000.0:
        return "TARGET_6000_TO_6999"
    if usd_per_portfolio_day <= 8_000.0:
        return "STRETCH_7000_TO_8000"
    return "ABOVE_STRETCH"


def evaluate_confirmation_block(
    block_name: str,
    model: ConfirmationModel,
    replay_dataset: ConfirmationDataset,
    policy: ConfirmationPolicy,
    *, expected_sessions: Iterable[SessionRef],
    exact_universe: ConfirmationOpportunitySet | None = None,
    exact_ceiling: DelayedCandidateCeiling | None = None,
) -> BlockDiagnostic:
    """Measure learned economics and recovery against the exact same universe."""

    if not block_name:
        raise ConfirmationRefusal("diagnostic block needs a name")
    sessions = tuple(expected_sessions)
    prediction = model.predict(replay_dataset)
    evaluation = replay_confirmation(
        replay_dataset, prediction, policy, expected_sessions=sessions)
    if exact_universe is not None and exact_ceiling is not None:
        raise ConfirmationRefusal(
            "diagnostic cannot receive both exact universe and ceiling")
    universe = replay_dataset if exact_universe is None else exact_universe
    if exact_universe is not None:
        exact_universe.validate()
        if (exact_universe.max_delay_sec != replay_dataset.max_delay_sec
                or set(exact_universe.candidate_id)
                != set(replay_dataset.candidate_id)
                or set(zip(exact_universe.asset, exact_universe.day))
                != set(zip(replay_dataset.asset, replay_dataset.day))):
            raise ConfirmationRefusal(
                "learned replay and exact opportunity universes differ")
    ceiling = (exact_ceiling if exact_ceiling is not None else
               exact_delayed_candidate_ceiling(
                   universe, expected_sessions=sessions))
    if (ceiling.evaluation.asset_days != evaluation.asset_days
            or ceiling.evaluation.total_pnl_usd <= 0):
        raise ConfirmationRefusal(
            "learned replay and exact ceiling denominators differ")
    days_with_trades = _days_with_trades(evaluation)
    feasibility = threshold_feasibility(
        trades=evaluation.trades, usd_per_trade=evaluation.usd_per_trade,
        max_drawdown_usd=evaluation.max_drawdown_usd,
        days_with_trades=days_with_trades, eligible_days=evaluation.asset_days)
    eligibility = capacity_eligibility({
        "included_trading_days": evaluation.asset_days,
        "trades": evaluation.trades,
        "usd_per_asset_day": evaluation.usd_per_asset_day,
        "usd_per_trade": evaluation.usd_per_trade,
        "oracle_usd_per_asset_day": ceiling.evaluation.usd_per_asset_day,
        "oracle_capture": evaluation.total_pnl_usd
                          / ceiling.evaluation.total_pnl_usd,
        "chronological_max_drawdown_usd": evaluation.max_drawdown_usd,
        "days_with_trades": days_with_trades,
        "capacity_regime": capacity_regime_from_oracle(
            ceiling.evaluation.usd_per_asset_day),
    })
    recovery = fit_only_goal_recovery(
        total_pnl_usd=evaluation.total_pnl_usd,
        usd_per_asset_day=evaluation.usd_per_asset_day,
        chronological_max_drawdown_usd=evaluation.max_drawdown_usd,
        included_trading_days=evaluation.asset_days,
        oracle_total_pnl_usd=ceiling.evaluation.total_pnl_usd,
        oracle_usd_per_asset_day=ceiling.evaluation.usd_per_asset_day,
        ceiling_receipt_sha256=ceiling.receipt_sha256,
    )
    portfolio_days = len({session.trading_day for session in sessions})
    if portfolio_days <= 0:
        raise ConfirmationRefusal("diagnostic portfolio-day denominator is empty")
    per_portfolio_day = evaluation.total_pnl_usd / portfolio_days
    receipt = C.object_sha256({
        "schema": DIAGNOSTIC_SCHEMA, "block": block_name,
        "dataset": replay_dataset.representation_sha256,
        "exact_universe": (universe.representation_sha256
                           if exact_ceiling is None else None),
        "model": model.model_hash, "policy": policy.receipt_sha256,
        "learned_total": evaluation.total_pnl_usd,
        "ceiling": ceiling.receipt_sha256,
        "threshold": feasibility.receipt_sha256,
        "capacity": eligibility.receipt_sha256,
        "recovery": recovery.receipt_sha256,
        "portfolio_days": portfolio_days,
        "usd_per_portfolio_day": per_portfolio_day,
        "result_band": _result_band(per_portfolio_day),
    })
    return BlockDiagnostic(
        block_name, evaluation, ceiling, feasibility, eligibility, recovery,
        portfolio_days, per_portfolio_day, _result_band(per_portfolio_day), receipt)


def shuffle_confirmation_targets(
    dataset: ConfirmationDataset, seed: int,
) -> ConfirmationDataset:
    """Recipient-fixed, series-level target shuffle for the null learner."""

    dataset.validate()
    rng = np.random.default_rng(int(seed))
    series = np.asarray(dataset.series_id, str)
    assets = np.asarray(dataset.asset, str)
    target_fields = ("cert_close_usd", "mfe_usd", "mae_usd", "wall_hit")
    shuffled = {name: np.asarray(getattr(dataset, name)).copy()
                for name in target_fields}
    mapping: list[tuple[str, str]] = []
    for asset in sorted(set(assets)):
        recipients = sorted(set(series[assets == asset]))
        if len(recipients) < 2:
            raise ConfirmationRefusal(
                f"shuffle control needs at least two {asset} series")
        order = np.asarray(recipients, object)
        offset = int(rng.integers(1, len(order)))
        donors = np.roll(order[rng.permutation(len(order))], offset)
        # Repair accidental fixed points deterministically with a cyclic shift.
        if any(a == b for a, b in zip(order, donors)):
            donors = np.roll(order, offset)
        for recipient, donor in zip(order.tolist(), donors.tolist()):
            r_idx = np.flatnonzero(series == recipient)
            d_idx = np.flatnonzero(series == donor)
            r_idx = r_idx[np.argsort(dataset.snapshot_ts_ns[r_idx])]
            d_idx = d_idx[np.argsort(dataset.snapshot_ts_ns[d_idx])]
            donor_position = np.rint(np.linspace(
                0, len(d_idx) - 1, len(r_idx))).astype(np.int64)
            for name in target_fields:
                shuffled[name][r_idx] = np.asarray(
                    getattr(dataset, name))[d_idx[donor_position]]
            mapping.append((recipient, donor))
    receipt = C.object_sha256({
        "schema": "QRE2CONFSHUF1", "source": dataset.representation_sha256,
        "seed": int(seed), "mapping": mapping,
    })
    result = replace(
        dataset, **shuffled,
        source_receipts=dataset.source_receipts + (receipt,))
    result.validate()
    return result


def registered_feature_ablations(
    feature_names: Sequence[str],
) -> Mapping[str, np.ndarray]:
    """Masks that remove one interpretable discretion family at a time."""

    names = np.asarray(tuple(feature_names), str)
    tokens = MappingProxyType({
        "formation_reclaim": ("from_formation", "excursion"),
        "aggressive_flow": ("trade_flow", "flow_fraction", "buy_volume",
                            "sell_volume", "price_per_aligned_volume"),
        "absorption": ("absorption", "through_ask", "through_bid"),
        "defense_retreat": ("reload", "retreat", "book_size_change"),
        "path_shape": ("path_variation", "path_efficiency",
                       "mid_direction_balance"),
        "auction_location": ("disc_auction_",),
        "initial_balance": ("disc_ib_",),
        "level_memory": ("disc_memory_",),
        "price_local_control": ("disc_level_", "disc_current_"),
        "confirmation_state": ("disc_state_",),
        "forward_vol_state": ("disc_fvol_",),
        "event_micro_timing": ("disc_evt_", "disc_mhi_"),
        "adaptive_clocks": ("disc_eclock_", "disc_tclock_",
                            "disc_vclock_", "disc_tape_"),
        "repeated_test_state": ("disc_test_",),
        "best_quote_state": ("disc_quote_",),
        "behavior_interactions": ("disc_behavior_",),
        "footprint_shape": ("disc_footprint_",),
        "origin_reaction": ("disc_origin_",),
        "target_path": ("disc_target_",),
        "ordered_paths": ("disc_path_",),
        "regime_state": ("disc_regime_",),
        "prior_session_memory": ("disc_prior_",),
        "slow_context": ("ctx_",),
        "negative_control_markers": (
            "association_destroyed", "coupling_destroyed"),
    })
    output = {}
    for family, needles in tokens.items():
        keep = np.asarray([not any(token in name for token in needles)
                           for name in names], bool)
        if keep.all() and family in {
                "auction_location", "level_memory", "price_local_control",
                "confirmation_state", "forward_vol_state",
                "event_micro_timing", "footprint_shape", "origin_reaction",
                "target_path", "prior_session_memory", "initial_balance",
                "adaptive_clocks", "repeated_test_state", "best_quote_state",
                "behavior_interactions", "ordered_paths", "regime_state",
                "slow_context", "negative_control_markers"}:
            # Legacy cached/synthetic schemas predate these registered
            # families.  New production-path datasets must expose them, while
            # old regression fixtures remain loadable.
            continue
        if keep.all() or not keep.any():
            raise ConfirmationRefusal(f"feature ablation {family} is ineffective")
        output[family] = keep
    return MappingProxyType(output)


__all__ = [
    "BlockDiagnostic", "PolicyGridEvaluation", "PolicyScorecard", "PolicySelection",
    "evaluate_confirmation_block", "registered_feature_ablations",
    "registered_feature_sets", "registered_policy_grid",
    "score_confirmation_policies",
    "select_confirmation_policy",
    "shuffle_confirmation_targets",
]
