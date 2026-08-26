"""Failure-branch measurements and the precommitted selector."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

from . import common as C
from .tabular_recovery_contracts import RecoveryConfig, RecoveryRefusal


FAILURE_BRANCHES: Final = (
    "PRIMARY_PASS", "PAIRWISE_ACTION", "HISTOGRAM_LEARNERS",
    "CAUSAL_RELATION_ENCODING", "REGRET_WEIGHTED_IMITATION",
    "STATE_CONDITIONED_CALIBRATION", "CAUSAL_TRAILING_EXPERTS",
    "EXTEND_TO_600",
)

@dataclass(frozen=True,slots=True)
class FailureMeasurements:
    training_teacher_capture:float
    raw_oof_floor_pass:bool
    weakest_real_above_shuffle:bool
    value_ordering_transfers:bool
    action_conversion_retention:float
    calibration_threshold_floor_pass:bool
    conversion_retention:float
    consecutive_era_reversal:bool
    five_minute_incremental_ceiling_fraction:float

    def __post_init__(self)->None:
        values=(self.training_teacher_capture,self.action_conversion_retention,
                self.conversion_retention)
        if (any(not math.isfinite(value) for value in values)
                or not math.isfinite(
                    self.five_minute_incremental_ceiling_fraction)
                or self.five_minute_incremental_ceiling_fraction<0):
            raise RecoveryRefusal("failure-ladder measurements are malformed")


@dataclass(frozen=True,slots=True)
class FailureBranchDecision:
    branch:str
    reason:str
    measurements_receipt_sha256:str
    goal_lowered:bool
    terminal_null_allowed:bool
    receipt_sha256:str

    def __post_init__(self)->None:
        core={"schema":"QRE2TABFAILUREBRANCH1","branch":self.branch,
              "reason":self.reason,
              "measurements":self.measurements_receipt_sha256,
              "goal_lowered":self.goal_lowered,
              "terminal_null_allowed":self.terminal_null_allowed}
        if (self.branch not in FAILURE_BRANCHES or not self.reason
                or self.goal_lowered or self.terminal_null_allowed
                or C.object_sha256(core)!=self.receipt_sha256):
            raise RecoveryRefusal("failure-ladder branch receipt differs")


def select_failure_branch(measured:FailureMeasurements,* ,
                          config:RecoveryConfig)->FailureBranchDecision:
    """Select the single precommitted implementation branch from evidence."""

    measured.__post_init__();config.__post_init__()
    measurement_core={"schema":"QRE2TABFAILUREMEASURE1",**{
        name:getattr(measured,name) for name in measured.__dataclass_fields__}}
    measurement_receipt=C.object_sha256(measurement_core)
    if measured.five_minute_incremental_ceiling_fraction>.10:
        branch,reason="EXTEND_TO_600","FIVE_MINUTE_RIGHT_CENSOR_TRIGGER"
    elif measured.training_teacher_capture<config.target_ceiling_capture:
        branch,reason="HISTOGRAM_LEARNERS","TRAINING_TEACHER_CAPTURE_BELOW_90_PERCENT"
    elif not measured.raw_oof_floor_pass:
        if not measured.weakest_real_above_shuffle:
            branch,reason=("CAUSAL_RELATION_ENCODING",
                "OOF_APPROACHES_MATCHED_SHUFFLE")
        else:
            branch,reason=("PAIRWISE_ACTION",
                "RAW_CATBOOST_CEILING_BELOW_FLOOR_WITH_TRAINING_CAPTURE")
    elif (measured.value_ordering_transfers
          and measured.action_conversion_retention
              <config.minimum_conversion_retention):
        branch,reason=("REGRET_WEIGHTED_IMITATION",
            "ENTER_DEFER_PASS_CONVERSION_LOST_ECONOMICS")
    elif (not measured.calibration_threshold_floor_pass
          or measured.conversion_retention<config.minimum_conversion_retention):
        branch,reason=("STATE_CONDITIONED_CALIBRATION",
            "RAW_SCORE_PASSES_BUT_MAPPER_OR_THRESHOLD_FAILS")
    elif measured.consecutive_era_reversal:
        branch,reason=("CAUSAL_TRAILING_EXPERTS",
            "CONSECUTIVE_ERA_EFFECT_REVERSAL")
    else:
        branch,reason="PRIMARY_PASS","ALL_REGISTERED_BOUNDARIES_PASS"
    core={"schema":"QRE2TABFAILUREBRANCH1","branch":branch,"reason":reason,
          "measurements":measurement_receipt,"goal_lowered":False,
          "terminal_null_allowed":False}
    result=FailureBranchDecision(branch,reason,measurement_receipt,False,False,
                                 C.object_sha256(core))
    result.__post_init__();return result

