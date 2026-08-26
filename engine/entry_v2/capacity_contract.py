"""Single canonical capacity/economics authority for Entry V2."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping
import math

from . import common as C

SCHEMA = "entry-v2-capacity-authority-v2"
DENOMINATOR = "included_trading_days"
FIT_ONLY_MIN_ORACLE_CAPTURE = 0.80


@dataclass(frozen=True)
class ThresholdFeasibility:
    trades: int
    usd_per_trade: float
    max_drawdown_usd: float
    days_with_trades: int
    eligible_days: int
    minimum_days_with_trades: int
    feasible: bool
    reasons: tuple[str, ...]
    receipt_sha256: str


@dataclass(frozen=True)
class CapacityEligibility:
    capacity_regime: str
    required_floor_usd: float | None
    threshold_feasibility_sha256: str
    eligible: bool
    reasons: tuple[str, ...]
    receipt_sha256: str


@dataclass(frozen=True)
class FitOnlyGoalRecovery:
    capacity_regime: str
    required_floor_usd: float
    oracle_capture: float
    minimum_oracle_capture: float
    #: R1: the EXACT candidate-ceiling receipt this recovery was measured
    #: against.  Without it a receipt could not be reconciled to the ceiling
    #: whose denominator produced its capture number.
    ceiling_receipt_sha256: str
    eligible: bool
    reasons: tuple[str, ...]
    receipt_sha256: str


def _exact_integer(value: object, name: str) -> int:
    if isinstance(value, bool):
        raise C.EntryV2Refusal(f"{name} must be an exact integer")
    try:
        result = int(value)
        numeric = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise C.EntryV2Refusal(f"{name} must be an exact integer") from exc
    if not math.isfinite(numeric) or numeric != result:
        raise C.EntryV2Refusal(f"{name} must be an exact integer")
    return result


def threshold_feasibility(
    *, trades: int, usd_per_trade: float, max_drawdown_usd: float,
    days_with_trades: int, eligible_days: int,
) -> ThresholdFeasibility:
    """Evaluate the one canonical A-013 replay-feasibility law."""
    try:
        trades = _exact_integer(trades, "trades")
        days_with_trades = _exact_integer(days_with_trades, "days_with_trades")
        eligible_days = _exact_integer(eligible_days, "eligible_days")
        usd_per_trade = float(usd_per_trade)
        max_drawdown_usd = float(max_drawdown_usd)
    except (TypeError, ValueError) as exc:
        raise C.EntryV2Refusal("threshold feasibility inputs are invalid") from exc
    if (trades < 0 or eligible_days <= 0 or days_with_trades < 0
            or days_with_trades > eligible_days or days_with_trades > trades
            or not math.isfinite(usd_per_trade)
            or not math.isfinite(max_drawdown_usd) or max_drawdown_usd < 0):
        raise C.EntryV2Refusal("threshold feasibility inputs are invalid")
    minimum_days = math.ceil(eligible_days / 3)
    reasons = []
    if trades < C.MIN_TRADES:
        reasons.append("TRADES_BELOW_MINIMUM")
    if usd_per_trade < C.MIN_EXPECTANCY_USD:
        reasons.append("USD_PER_TRADE_BELOW_MINIMUM")
    if max_drawdown_usd > C.TARGET_MDD_USD:
        reasons.append("MAX_DRAWDOWN_ABOVE_LIMIT")
    if trades == 0:
        # V4: an empty book reports max_drawdown_usd == 0.0.  That is an
        # UNMEASURED drawdown, not a passing one, so it may never be read as
        # satisfying the MDD law.
        reasons.append("MAX_DRAWDOWN_UNMEASURED_EMPTY_BOOK")
    if days_with_trades < minimum_days:
        reasons.append("TRADE_DAY_COVERAGE_BELOW_MINIMUM")
    core = {
        "schema": "entry-v2-threshold-feasibility-v1", "trades": trades,
        "usd_per_trade": usd_per_trade,
        "max_drawdown_usd": max_drawdown_usd,
        "days_with_trades": days_with_trades, "eligible_days": eligible_days,
        "minimum_days_with_trades": minimum_days,
        "minimum_trades": C.MIN_TRADES,
        "minimum_usd_per_trade": C.MIN_EXPECTANCY_USD,
        "maximum_drawdown_usd": C.TARGET_MDD_USD,
        "max_drawdown_measured": trades > 0,
        "feasible": not reasons, "reasons": reasons,
    }
    receipt = C.object_sha256(core)
    return ThresholdFeasibility(
        trades, usd_per_trade, max_drawdown_usd, days_with_trades,
        eligible_days, minimum_days, not reasons, tuple(reasons), receipt)


def capacity_eligibility(row: Mapping[str, Any]) -> CapacityEligibility:
    """Return typed goal reasons without rejecting a measured economic FAIL."""
    try:
        days_raw = row["included_trading_days"]; trades_raw = row["trades"]
        per_day = float(row["usd_per_asset_day"])
        per_trade = float(row["usd_per_trade"])
        oracle_day = float(row["oracle_usd_per_asset_day"])
        capture = float(row["oracle_capture"])
        mdd = float(row["chronological_max_drawdown_usd"])
        days_with_trades_raw = row["days_with_trades"]
        regime = str(row["capacity_regime"])
    except (KeyError, TypeError, ValueError) as exc:
        raise C.EntryV2Refusal("capacity eligibility row is incomplete") from exc
    feasibility = threshold_feasibility(
        trades=trades_raw, usd_per_trade=per_trade, max_drawdown_usd=mdd,
        days_with_trades=days_with_trades_raw, eligible_days=days_raw)
    reasons = list(feasibility.reasons)
    derived: str | None = None; floor: float | None = None
    if (not math.isfinite(oracle_day)
            or oracle_day < C.LOW_CAPACITY_ASSET_DAY_FLOOR_USD):
        reasons.append("ORACLE_BELOW_MINIMUM_CAPACITY")
    else:
        derived = capacity_regime_from_oracle(oracle_day)
        floor = required_floor_usd(derived)
        if regime != derived:
            reasons.append("CAPACITY_REGIME_DIFFERS_FROM_ORACLE")
        if not math.isfinite(per_day) or per_day < floor:
            reasons.append("USD_PER_ASSET_DAY_BELOW_CAPACITY_FLOOR")
    if not math.isfinite(capture) or not 0.0 <= capture <= 1.0:
        reasons.append("ORACLE_CAPTURE_OUTSIDE_UNIT_INTERVAL")
    if derived == "LOW" and not mdd < C.LOW_CAPACITY_MAX_DRAWDOWN_USD:
        reasons.append("LOW_CAPACITY_MDD_NOT_BELOW_LIMIT")
    core = {
        "schema": "entry-v2-capacity-eligibility-v1", "capacity_regime": regime,
        "derived_capacity_regime": derived, "required_floor_usd": floor,
        "threshold_feasibility_sha256": feasibility.receipt_sha256,
        "eligible": not reasons, "reasons": reasons,
        "low_capacity_max_drawdown_usd": C.LOW_CAPACITY_MAX_DRAWDOWN_USD,
    }
    return CapacityEligibility(
        regime, floor, feasibility.receipt_sha256, not reasons, tuple(reasons),
        C.object_sha256(core))


def fit_only_goal_recovery(
    *, total_pnl_usd: float, usd_per_asset_day: float,
    chronological_max_drawdown_usd: float, included_trading_days: int,
    oracle_total_pnl_usd: float, oracle_usd_per_asset_day: float,
    ceiling_receipt_sha256: str,
) -> FitOnlyGoalRecovery:
    """Apply the prelaunch economic-confidence law to one replay block.

    This is deliberately stricter than threshold feasibility.  A path cannot
    authorize paid held work merely by producing ten sparse profitable trades:
    it must also recover most of the exact candidate ceiling and clear the
    capacity-adjusted absolute floor on the same untouched denominator.
    """
    days = _exact_integer(included_trading_days, "included_trading_days")
    try:
        total = float(total_pnl_usd)
        per_day = float(usd_per_asset_day)
        mdd = float(chronological_max_drawdown_usd)
        oracle_total = float(oracle_total_pnl_usd)
        oracle_day = float(oracle_usd_per_asset_day)
    except (TypeError, ValueError, OverflowError) as exc:
        raise C.EntryV2Refusal("fit-only goal recovery inputs are invalid") from exc
    if (days <= 0 or not all(math.isfinite(value) for value in
            (total, per_day, mdd, oracle_total, oracle_day))
            or mdd < 0.0 or oracle_total <= 0.0 or oracle_day <= 0.0
            or total / days != per_day or oracle_total / days != oracle_day):
        raise C.EntryV2Refusal("fit-only goal recovery inputs do not reconcile")
    if not _sha(ceiling_receipt_sha256):
        raise C.EntryV2Refusal(
            "fit-only goal recovery must bind its exact candidate-ceiling receipt")
    regime = capacity_regime_from_oracle(oracle_day)
    floor = required_floor_usd(regime)
    capture = total / oracle_total
    reasons: list[str] = []
    if per_day < floor:
        reasons.append("USD_PER_ASSET_DAY_BELOW_CAPACITY_FLOOR")
    if capture < FIT_ONLY_MIN_ORACLE_CAPTURE:
        reasons.append("ORACLE_CAPTURE_BELOW_PRELAUNCH_FLOOR")
    # Ruling 21 (2026-08-19, adjudicates the R-B2 / capacity-contract
    # conflict measured live: prophet NKD capture 1.0536): the GOAL-GRADE
    # ceiling counts only >=$600 candidates, while a lawful replay also
    # collects sub-$600 winners — goal-grade capture may therefore exceed
    # 1.0 and is REPORTED unbounded (it is the ruling-11 gate ratio, not an
    # anomaly cap). The arithmetic-impossibility law lives on the
    # EXACT-OFFER ceiling at the replay layer (nothing may beat the
    # unfiltered DP optimum), where R-B2 already enforces it.
    if regime == "LOW" and not mdd < C.LOW_CAPACITY_MAX_DRAWDOWN_USD:
        reasons.append("LOW_CAPACITY_MDD_NOT_BELOW_LIMIT")
    core = {
        "schema": "entry-v2-fit-only-goal-recovery-v1",
        "capacity_regime": regime,
        "required_floor_usd": floor,
        "included_trading_days": days,
        "total_pnl_usd": total,
        "usd_per_asset_day": per_day,
        "chronological_max_drawdown_usd": mdd,
        "oracle_total_pnl_usd": oracle_total,
        "oracle_usd_per_asset_day": oracle_day,
        "oracle_capture": capture,
        "minimum_oracle_capture": FIT_ONLY_MIN_ORACLE_CAPTURE,
        "ceiling_receipt_sha256": str(ceiling_receipt_sha256),
        "eligible": not reasons,
        "reasons": reasons,
    }
    return FitOnlyGoalRecovery(
        regime, floor, capture, FIT_ONLY_MIN_ORACLE_CAPTURE,
        str(ceiling_receipt_sha256), not reasons,
        tuple(reasons), C.object_sha256(core))


def capacity_regime_from_oracle(value: float) -> str:
    value = float(value)
    if not math.isfinite(value) or value < C.LOW_CAPACITY_ASSET_DAY_FLOOR_USD:
        raise C.EntryV2Refusal("oracle does not support the minimum capacity regime")
    if value >= C.TARGET_ASSET_DAY_USD:
        return "FULL"
    if value >= C.WEAK_ASSET_DAY_FLOOR_USD:
        return "WEAK"
    return "LOW"


def required_floor_usd(regime: str) -> float:
    try:
        return {"FULL": C.TARGET_ASSET_DAY_USD,
                "WEAK": C.WEAK_ASSET_DAY_FLOOR_USD,
                "LOW": C.LOW_CAPACITY_ASSET_DAY_FLOOR_USD}[str(regime)]
    except KeyError as exc:
        raise C.EntryV2Refusal("unknown capacity regime") from exc


def _sha(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(
        char in "0123456789abcdef" for char in value
    )


__all__ = ["SCHEMA", "DENOMINATOR", "FIT_ONLY_MIN_ORACLE_CAPTURE",
           "CapacityEligibility", "FitOnlyGoalRecovery",
           "ThresholdFeasibility", "capacity_eligibility",
           "capacity_regime_from_oracle", "required_floor_usd",
           "fit_only_goal_recovery", "threshold_feasibility"]
