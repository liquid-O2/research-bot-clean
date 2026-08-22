"""Frozen public contracts for the Entry V2 goal-bound tabular recovery.

This module is deliberately label-free.  Teacher values and realized outcomes
live in separate artifacts and cannot be represented by
``PortfolioDecisionState`` or ``CausalFeatureSchema``.  The split is a trust
boundary, not a naming convention.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import math
from functools import lru_cache
import re
from types import MappingProxyType
from typing import Final, Mapping, Sequence

import numpy as np

from . import common as C


CONTRACT_SCHEMA: Final = "QRE2TABRECOVERY1"
POLICY_ACTIONS: Final = ("ENTER", "DEFER", "PASS")
ACTIVE_WATCH_KEYS: Final = tuple(
    (asset, side) for asset in C.ASSETS for side in (-1, 1))
VALUE_SCALE_USD: Final = 600.0
COMPONENT_STACK_NAMES: Final = (
    "stack_current_q20", "stack_current_q50", "stack_current_q80",
    "stack_continuation_q20", "stack_continuation_q50",
    "stack_continuation_q80", "stack_wall_probability",
    "stack_adverse_q90", "stack_occupancy_q50", "stack_occupancy_q90",
)
REGIME_FEATURE_NAMES: Final = (
    "portfolio_regime_low", "portfolio_regime_mid",
    "portfolio_regime_high", "portfolio_regime_unknown",
)
REAL_SEEDS: Final = (20260820, 20260821, 20260822, 20260823, 20260824)
SHUFFLE_SEEDS: Final = (20261820, 20261821, 20261822, 20261823, 20261824)
BASE_TRAINING_OFFSETS_SEC: Final = tuple(
    list(range(0, 61, 5)) + list(range(70, 301, 10)))

# ``future`` is intentionally not forbidden: QRF4 forward-volatility is a
# causal forecast available at the decision clock.  Only teacher/outcome
# semantics are refused.
_FORBIDDEN_MODEL_FIELD = re.compile(
    r"(^|_)(teacher|oracle|outcome|certificate|cert|q_enter|q_defer|"
    r"q_pass|action_regret|optimal_action|current_entry_usd|"
    r"continuation_target|mfe|mae|wall_hit|wall_outcome|exit_ts|"
    r"phase_close_pnl|realized_pnl)(_|$)", re.IGNORECASE)


class RecoveryRefusal(RuntimeError):
    """A recovery chronology, causality, schema, or economic law failed."""


@lru_cache(maxsize=32)
def _lawful_state_feature_names(names:tuple[str,...])->bool:
    """Memoized roster law: the every-second walk revalidates one unchanged
    1,764-name schema for every live row, and the set+regex scan is ~2ms per
    row — the single largest walk cost.  Same accept/reject set."""

    return (len(names)==len(set(names))
            and not any(_FORBIDDEN_MODEL_FIELD.search(name) for name in names))


class DecisionAction(str, Enum):
    ENTER = "ENTER"
    DEFER = "DEFER"
    PASS = "PASS"


@dataclass(frozen=True, slots=True)
class RecoveryChronology:
    """The sole development/calibration/forward chronology for this lane."""

    burned: tuple[int, int] = (20210531, 20220630)
    oof_blocks: tuple[tuple[str, int, int], ...] = (
        ("E3", 20220701, 20221231),
        ("E4", 20230101, 20230630),
        ("E5", 20230701, 20231231),
        ("E6", 20240101, 20240630),
    )
    platt: tuple[int, int] = (20240701, 20240930)
    threshold: tuple[int, int] = (20241001, 20241231)
    forward: tuple[int, int] = (20250101, 20250630)
    rehearsals: tuple[tuple[str, tuple[int, int], tuple[int, int],
                             tuple[int, int], tuple[int, int]], ...] = (
        ("E1R", (20210531, 20210709), (20210712, 20210720),
         (20210721, 20210806), (20210809, 20210831)),
        ("E2R", (20210531, 20210813), (20210816, 20210825),
         (20210826, 20210920), (20210921, 20210930)),
    )
    component_folds: tuple[tuple[str, int, int, int, int, int, int], ...] = (
        ("BURN_E2_STACK", 20210531, 20210930, 20211001, 20211231,
         20220101, 20220630),
        ("E3", 20210531, 20220331, 20220401, 20220630,
         20220701, 20221231),
        ("E4", 20210531, 20220930, 20221001, 20221231,
         20230101, 20230630),
        ("E5", 20210531, 20230331, 20230401, 20230630,
         20230701, 20231231),
        ("E6", 20210531, 20230930, 20231001, 20231231,
         20240101, 20240630),
        ("FROZEN_Q3_E8", 20210531, 20240331, 20240401, 20240630,
         20240701, 20250630),
    )
    action_folds: tuple[tuple[str, int, int, int, int, int, int], ...] = (
        ("E3", 20220101, 20220331, 20220401, 20220630,
         20220701, 20221231),
        ("E4", 20220101, 20220930, 20221001, 20221231,
         20230101, 20230630),
        ("E5", 20220101, 20230331, 20230401, 20230630,
         20230701, 20231231),
        ("E6", 20220101, 20230930, 20231001, 20231231,
         20240101, 20240630),
        ("FROZEN_Q3_E8", 20220101, 20240331, 20240401, 20240630,
         20240701, 20250630),
    )

    def __post_init__(self) -> None:
        windows = (self.burned,
                   *((lo, hi) for _name, lo, hi in self.oof_blocks),
                   self.platt, self.threshold, self.forward)
        if (tuple(name for name, _lo, _hi in self.oof_blocks)
                != ("E3", "E4", "E5", "E6")
                or any(lo > hi for lo, hi in windows)
                or any(windows[index][1] >= windows[index + 1][0]
                       for index in range(len(windows) - 1))
                or windows[-1][1] >= C.HOLDOUT_START_D8):
            raise RecoveryRefusal("tabular recovery chronology is invalid/sealed")
        if tuple(row[0] for row in self.rehearsals) != ("E1R", "E2R"):
            raise RecoveryRefusal("fit-only rehearsal chronology names drifted")
        for name, fit, platt, threshold, forward in self.rehearsals:
            rehearsal_windows = (fit, platt, threshold, forward)
            if (any(lo > hi or hi >= C.HOLDOUT_START_D8
                    for lo, hi in rehearsal_windows)
                    or any(rehearsal_windows[index][1]
                           >= rehearsal_windows[index + 1][0]
                           for index in range(3))):
                raise RecoveryRefusal(
                    f"fit-only rehearsal chronology is invalid: {name}")
        expected_component=("BURN_E2_STACK","E3","E4","E5","E6",
                            "FROZEN_Q3_E8")
        expected_action=("E3","E4","E5","E6","FROZEN_Q3_E8")
        if (tuple(row[0] for row in self.component_folds)!=expected_component
                or tuple(row[0] for row in self.action_folds)!=expected_action):
            raise RecoveryRefusal("chronological fit fold names drifted")
        for row in self.component_folds+self.action_folds:
            _name,train_lo,train_hi,val_lo,val_hi,score_lo,score_hi=row
            if not (train_lo<=train_hi<val_lo<=val_hi<score_lo<=score_hi
                    <C.HOLDOUT_START_D8):
                raise RecoveryRefusal("chronological fit fold overlaps/seal")

    def role(self, day: int) -> str:
        day = int(day)
        C.guard_date(day)
        if self.burned[0] <= day <= self.burned[1]:
            return "BURNED"
        for name, lo, hi in self.oof_blocks:
            if lo <= day <= hi:
                return name
        if self.platt[0] <= day <= self.platt[1]:
            return "PLATT"
        if self.threshold[0] <= day <= self.threshold[1]:
            return "THRESHOLD"
        if self.forward[0] <= day <= self.forward[1]:
            return "FORWARD"
        return "WARMUP"

    def rehearsal_window(self, name: str, role: str) -> tuple[int, int]:
        roles = ("FIT", "PLATT", "THRESHOLD", "FORWARD")
        try:
            row = {value[0]: value for value in self.rehearsals}[
                str(name).upper()]
            return tuple(row[roles.index(str(role).upper()) + 1])
        except (KeyError, ValueError) as exc:
            raise RecoveryRefusal("unknown rehearsal stage/role") from exc

    def fit_fold(self, kind:str, name:str)->tuple[int,int,int,int,int,int]:
        rows={"COMPONENT":self.component_folds,"ACTION":self.action_folds}
        try:
            row={value[0]:value for value in rows[str(kind).upper()]}[
                str(name).upper()]
        except KeyError as exc:
            raise RecoveryRefusal("unknown chronological fit fold") from exc
        return tuple(map(int,row[1:]))

    @property
    def receipt_sha256(self) -> str:
        return C.object_sha256({"schema": "QRE2TABCHRON1", **asdict(self)})


@dataclass(frozen=True, slots=True)
class RecoveryConfig:
    """Pre-registered learner, clock, controls, and economic gates."""

    workers: int = C.MAX_CPU_WORKERS
    max_delay_sec: int = 300
    dormant_max_delay_sec: int = 600
    continuation_horizon_sec: int = 120
    depth: int = 7
    learning_rate: float = 0.04
    max_iterations: int = 1_500
    l2_leaf_reg: float = 12.0
    early_stopping_rounds: int = 100
    real_seeds: tuple[int, ...] = REAL_SEEDS
    shuffle_seeds: tuple[int, ...] = SHUFFLE_SEEDS
    threshold_quantiles: int = 21
    minimum_portfolio_day_usd: float = C.RECOVERY_MIN_PORTFOLIO_DAY_USD
    target_portfolio_day_usd: float = C.RECOVERY_TARGET_PORTFOLIO_DAY_USD
    minimum_ceiling_capture: float = C.RECOVERY_MIN_CEILING_CAPTURE
    target_ceiling_capture: float = C.RECOVERY_TARGET_CEILING_CAPTURE
    minimum_conversion_retention: float = C.RECOVERY_MIN_CONVERSION_RETENTION
    minimum_usd_per_trade: float = C.MIN_EXPECTANCY_USD
    maximum_drawdown_usd: float = C.TARGET_MDD_USD
    minimum_trades: int = C.MIN_TRADES
    minimum_asset_day_coverage_fraction: float = 1.0 / 3.0
    admission_minimum_current_q20_usd: float = 0.0
    admission_maximum_wall_probability: float = 0.50
    admission_maximum_adverse_q90_usd: float = C.WALL_USD
    rollout_relabel_rounds: int = 2

    def __post_init__(self) -> None:
        if (self.workers != 16 or self.workers != C.MAX_CPU_WORKERS
                or self.max_delay_sec != 300
                or self.dormant_max_delay_sec != 600
                or self.continuation_horizon_sec != 120
                or self.depth != 7 or self.learning_rate != 0.04
                or self.max_iterations != 1_500 or self.l2_leaf_reg != 12.0
                or self.early_stopping_rounds != 100
                or self.real_seeds != REAL_SEEDS
                or self.shuffle_seeds != SHUFFLE_SEEDS
                or len(set(self.real_seeds + self.shuffle_seeds)) != 10
                or self.threshold_quantiles != 21
                or self.minimum_portfolio_day_usd != 3_000.0
                or self.target_portfolio_day_usd != 6_000.0
                or self.minimum_ceiling_capture != 0.80
                or self.target_ceiling_capture != 0.90
                or self.minimum_conversion_retention != 0.90
                or self.minimum_usd_per_trade != 600.0
                or self.maximum_drawdown_usd != 1_000.0
                or self.minimum_trades < 1
                or not 0 < self.minimum_asset_day_coverage_fraction <= 1
                or self.admission_minimum_current_q20_usd != 0.0
                or self.admission_maximum_wall_probability != 0.50
                or self.admission_maximum_adverse_q90_usd != C.WALL_USD
                or self.rollout_relabel_rounds != 2):
            raise RecoveryRefusal("tabular recovery configuration drifted")

    @property
    def receipt_sha256(self) -> str:
        return C.object_sha256({"schema": "QRE2TABCONFIG1", **asdict(self)})


@dataclass(frozen=True, slots=True)
class CausalFeatureSchema:
    names: tuple[str, ...]
    source_schema_sha256: str
    removed_constants: tuple[str, ...] = ()
    removed_duplicates: tuple[tuple[str, str], ...] = ()
    removed_proven_leaks: tuple[str, ...] = ()
    relation_source_features:tuple[str,...]=()

    def __post_init__(self) -> None:
        names = tuple(map(str, self.names))
        duplicate_kept = tuple(pair[0] for pair in self.removed_duplicates
                               if len(pair) == 2)
        duplicate_removed = tuple(pair[1] for pair in self.removed_duplicates
                                  if len(pair) == 2)
        removed = (self.removed_constants + duplicate_removed
                   + self.removed_proven_leaks)
        relation=tuple(map(str,self.relation_source_features))
        derived=tuple(name for name in names if name.startswith("relation_"))
        if (not names or len(names) != len(set(names))
                or any(len(pair) != 2 or not pair[0] or not pair[1]
                       or pair[0] == pair[1]
                       for pair in self.removed_duplicates)
                or any(not name or _FORBIDDEN_MODEL_FIELD.search(name)
                       for name in names)
                or any(name in names for name in removed)
                or any(name not in names for name in duplicate_kept)
                or len(relation)!=len(set(relation)) or any(not name for name in relation)
                or any(name in names for name in relation)
                or bool(relation)!=bool(derived)
                or any(not any(name.startswith(f"relation_{source}_")
                               for source in relation) for name in derived)
                or any(not any(name.startswith(f"relation_{source}_")
                               for name in derived) for source in relation)
                or not _is_sha(self.source_schema_sha256)):
            raise RecoveryRefusal("causal feature schema contains teacher/leak drift")

    @property
    def receipt_sha256(self) -> str:
        return C.object_sha256({"schema": "QRE2TABFEATURESCHEMA2", **asdict(self)})

    def validate_matrix(self, matrix: np.ndarray) -> None:
        values = np.asarray(matrix)
        if (values.ndim != 2 or values.shape[1] != len(self.names)
                or not np.all(np.isfinite(values))):
            raise RecoveryRefusal("causal feature matrix differs from frozen schema")


@dataclass(frozen=True, slots=True)
class ComponentPredictions:
    current_q20_usd: float
    current_q50_usd: float
    current_q80_usd: float
    continuation_q20_usd: float
    continuation_q50_usd: float
    continuation_q80_usd: float
    wall_probability: float
    enter_probability: float
    mae_q90_usd: float
    occupancy_q50_sec: float
    occupancy_q90_sec: float
    enter_regret: float
    defer_regret: float
    pass_regret: float
    lower_action_advantage_usd: float
    incremental_dollars_usd: float

    def __post_init__(self) -> None:
        values = tuple(float(value) for value in asdict(self).values())
        if (any(not math.isfinite(value) for value in values)
                or not 0 <= self.wall_probability <= 1
                or not 0 <= self.enter_probability <= 1
                or min(self.mae_q90_usd, self.occupancy_q50_sec,
                       self.occupancy_q90_sec, self.enter_regret,
                       self.defer_regret, self.pass_regret) < 0
                or self.current_q20_usd > self.current_q50_usd
                or self.current_q50_usd > self.current_q80_usd
                or self.continuation_q20_usd > self.continuation_q50_usd
                or self.continuation_q50_usd > self.continuation_q80_usd
                or self.occupancy_q50_sec > self.occupancy_q90_sec):
            raise RecoveryRefusal("component predictions are malformed")


@dataclass(frozen=True, slots=True)
class OpenPositionState:
    asset: str
    series_id: str
    entry_ts_ns: int
    open_until_ts_ns: int

    def __post_init__(self) -> None:
        if (self.asset not in C.ASSETS or not self.series_id
                or int(self.entry_ts_ns) <= 0
                or int(self.open_until_ts_ns) < int(self.entry_ts_ns)):
            raise RecoveryRefusal("open-position state is malformed")


@dataclass(frozen=True, slots=True)
class PortfolioDecisionState:
    """Everything the fixed online policy may know for one watch snapshot."""

    candidate_id: str
    series_id: str
    asset: str
    trading_day: int
    side: int
    snapshot_ts_ns: int
    watch_expiry_ts_ns: int
    feature_names: tuple[str, ...]
    causal_features: tuple[float, ...]
    components: ComponentPredictions
    entries_used: int
    open_positions: tuple[OpenPositionState, ...]
    active_watches_by_asset_side: tuple[int, int, int, int, int, int]
    phase: str
    qrf4_regime: str

    def __post_init__(self) -> None:
        if (not self.candidate_id or not self.series_id
                or self.asset not in C.ASSETS or self.side not in (-1, 1)
                or int(self.snapshot_ts_ns) <= 0
                or int(self.watch_expiry_ts_ns) < int(self.snapshot_ts_ns)
                or len(self.feature_names) != len(self.causal_features)
                or not _lawful_state_feature_names(tuple(self.feature_names))
                or not all(map(math.isfinite, self.causal_features))
                or not 0 <= int(self.entries_used)
                       <= C.MAX_ENTRIES_PORTFOLIO_DAY
                or len(self.active_watches_by_asset_side) != len(ACTIVE_WATCH_KEYS)
                or any(int(value) < 0
                       for value in self.active_watches_by_asset_side)
                or not self.phase
                or self.qrf4_regime not in {"LOW", "MID", "HIGH", "UNKNOWN"}):
            raise RecoveryRefusal("portfolio decision state is malformed/leaking")
        C.guard_date(int(self.trading_day))
        if len({position.asset for position in self.open_positions}) \
                != len(self.open_positions):
            raise RecoveryRefusal("portfolio state has two positions in one asset")

    @property
    def asset_occupied(self) -> bool:
        return any(position.asset == self.asset
                   and position.open_until_ts_ns >= self.snapshot_ts_ns
                   for position in self.open_positions)


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    action: DecisionAction
    incremental_dollars_usd: float
    lower_action_advantage_usd: float
    reason: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "action", DecisionAction(self.action))
        if (not math.isfinite(float(self.incremental_dollars_usd))
                or not math.isfinite(float(self.lower_action_advantage_usd))
                or not self.reason):
            raise RecoveryRefusal("policy decision is malformed")


@dataclass(frozen=True, slots=True)
class EconomicGateResult:
    portfolio_days: int
    active_portfolio_days: int
    eligible_asset_days: int
    covered_asset_days: int
    trades: int
    total_pnl_usd: float
    usd_per_active_portfolio_day: float
    usd_per_trade: float
    max_drawdown_usd: float
    exact_ceiling_usd: float
    ceiling_capture: float
    laws_pass: bool
    floor_pass: bool
    target_pass: bool
    reasons: tuple[str, ...]
    # RAIL-0 ladder receipt (design/RAIL0_LADDER_GATE_SPEC.md L1/L2): the rung
    # each asset was judged against, and the $/trade preference as a report.
    ladder: Mapping[str, Mapping[str, float | bool]]
    usd_per_trade_by_asset: Mapping[str, float]
    receipt_sha256: str


def recovery_lane_registry() -> Mapping[str, object]:
    """Name authoritative and quarantined paths without deleting evidence."""

    core = {
        "schema": "QRE2TABLANES1",
        "authoritative_lane": "FULL_UNIVERSE_EXACT_TEACHER_TABULAR_POLICY",
        "candidate_generation": "UNCHANGED_G1_ALL_PRE_H2",
        "authoritative_worker_count": 16,
        "authoritative_decision": "CHRONOLOGICAL_ENTER_DEFER_PASS",
        "quarantined_non_authoritative": (
            "WHOLE_DAY_ORDINAL_TOP3",
            "SPARSE_GRID_CEILINGS",
            "HINDSIGHT_TOPK_OR_CUTOFF_HEADLINES",
            "CANDIDATE_LOCAL_DIRECT_UTILITY",
            "FULL_DAY_CENTERING_OR_FUTURE_RELATIVE_NORMALIZATION",
            "WITHDRAWN_CONFIRMATION_ENTRY_LANE",
            "SINGLE_SEED_PROMOTION",
        ),
        "neural_escalation_allowed": False,
        "gex_dependency_allowed": False,
        "h2_open_count": 0,
    }
    return MappingProxyType({**core, "receipt_sha256": C.object_sha256(core)})


def fit_only_recovery_chronology(name:str,
        active_fit_days:Sequence[int])->RecoveryChronology:
    """Build the deterministic internal OOF folds for E1R or E2R.

    The public FIT/PLATT/THRESHOLD/FORWARD walls remain those in
    ``RecoveryChronology.rehearsals``.  Nine non-overlapping, data-bearing FIT
    bins provide strictly prior component stacks and action stacks; the final
    folds score every post-FIT role with one unchanged model.
    """

    base=RecoveryChronology();fit=base.rehearsal_window(name,"FIT")
    platt=base.rehearsal_window(name,"PLATT")
    threshold=base.rehearsal_window(name,"THRESHOLD")
    forward=base.rehearsal_window(name,"FORWARD")
    days=tuple(sorted(set(map(int,active_fit_days))))
    if (len(days)<9 or any(not fit[0]<=day<=fit[1] for day in days)
            or days[0]!=min(days) or days[-1]!=max(days)):
        raise RecoveryRefusal("fit-only chronology lacks nine active FIT bins")
    raw=np.array_split(np.asarray(days,np.int64),9)
    if any(not len(row) for row in raw):
        raise RecoveryRefusal("fit-only chronology has an empty OOF bin")
    bins=tuple((int(row[0]),int(row[-1])) for row in raw)
    if any(bins[index][1]>=bins[index+1][0] for index in range(8)):
        raise RecoveryRefusal("fit-only OOF bins overlap")
    b=bins
    component=(
        ("BURN_E2_STACK",b[0][0],b[0][1],b[1][0],b[1][1],b[2][0],b[2][1]),
        ("E3",b[0][0],b[1][1],b[2][0],b[2][1],b[3][0],b[3][1]),
        ("E4",b[0][0],b[2][1],b[3][0],b[3][1],b[4][0],b[4][1]),
        ("E5",b[0][0],b[3][1],b[4][0],b[4][1],b[5][0],b[5][1]),
        ("E6",b[0][0],b[4][1],b[5][0],b[5][1],b[6][0],b[8][1]),
        ("FROZEN_Q3_E8",b[0][0],b[6][1],b[7][0],b[8][1],
         platt[0],forward[1]),
    )
    action=(
        ("E3",b[2][0],b[2][1],b[3][0],b[3][1],b[4][0],b[4][1]),
        ("E4",b[2][0],b[3][1],b[4][0],b[4][1],b[5][0],b[5][1]),
        ("E5",b[2][0],b[4][1],b[5][0],b[5][1],b[6][0],b[6][1]),
        ("E6",b[2][0],b[5][1],b[6][0],b[6][1],b[7][0],b[8][1]),
        ("FROZEN_Q3_E8",b[2][0],b[6][1],b[7][0],b[8][1],
         platt[0],forward[1]),
    )
    result=RecoveryChronology(burned=(fit[0],b[1][1]),
        oof_blocks=(("E3",*b[2]),("E4",*b[3]),("E5",*b[4]),
                    ("E6",b[5][0],fit[1])),
        platt=platt,threshold=threshold,forward=forward,
        rehearsals=base.rehearsals,component_folds=component,
        action_folds=action)
    result.__post_init__();return result


@lru_cache(maxsize=64)
def _validated_model_feature_names(names: tuple[str, ...]) -> tuple[str, ...]:
    values = tuple(map(str, names))
    if (not values or len(values) != len(set(values))
            or any(not name or _FORBIDDEN_MODEL_FIELD.search(name)
                   for name in values)):
        raise RecoveryRefusal("model feature roster contains teacher/outcome fields")
    return values


def validate_model_feature_names(names: Sequence[str]) -> tuple[str, ...]:
    # The every-second walks revalidate one unchanged 1,764-name roster up
    # to three times per timestamp; the set+regex scan is ~2ms per call.
    # lru_cache never caches raised exceptions, so a malformed roster still
    # refuses on every call.
    return _validated_model_feature_names(tuple(names))


def _is_sha(value: object) -> bool:
    return (isinstance(value, str) and len(value) == 64
            and all(char in "0123456789abcdef" for char in value))


def sha256_row_array(value: str, rows: int) -> np.ndarray:
    """Repeat a SHA-256 receipt without NumPy's scalar-string truncation.

    ``np.full(rows, value, str)`` uses NumPy's default ``<U1`` dtype and
    silently truncates every 64-character receipt to one character.  Keep all
    row-level provenance construction behind this exact-width boundary.
    """

    count = int(rows)
    if not _is_sha(value) or count < 0:
        raise RecoveryRefusal("row receipt array input is malformed")
    result = np.full(count, value, dtype="<U64")
    if result.shape != (count,) or any(not _is_sha(str(item)) for item in result):
        raise RecoveryRefusal("row receipt array was truncated")
    return result


__all__ = [
    "ACTIVE_WATCH_KEYS", "BASE_TRAINING_OFFSETS_SEC", "COMPONENT_STACK_NAMES",
    "CONTRACT_SCHEMA",
    "ComponentPredictions", "DecisionAction", "EconomicGateResult",
    "OpenPositionState", "POLICY_ACTIONS", "PolicyDecision",
    "PortfolioDecisionState", "REAL_SEEDS", "RecoveryChronology",
    "RecoveryConfig", "RecoveryRefusal", "REGIME_FEATURE_NAMES",
    "SHUFFLE_SEEDS", "VALUE_SCALE_USD",
    "fit_only_recovery_chronology","recovery_lane_registry",
    "sha256_row_array","validate_model_feature_names",
]
