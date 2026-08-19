"""Measured held-stage selection engine for Entry V2.

The engine contains no data loader and no synthetic success path.  Every E1
and E2 decision is computed from candidate/day-level measurements produced by
the live one-open resource owner.  E3 is report-only and may only bind a
standard, already measured :class:`FoldOOFResult` to the E2-frozen winner.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Sequence

import numpy as np

from . import common as C
from .atlas_statistics import (
    PairedObservationRecord, SupportKind, SupportState, hierarchical_holm,
    nonredundant_finalists, paired_day_cluster_records,
    romano_wolf_lower_bounds, support_gate, through_e2_fit_count,
)
from .capacity_contract import (
    FIT_ONLY_MIN_ORACLE_CAPTURE, SCHEMA as CAPACITY_SCHEMA,
    capacity_eligibility, validate_capacity_document,
)
from .causal_label_atlas import CellAvailability, PROBE_REGISTRY
from .diagnostic_inputs import fit_only_rehearsal_windows
from .fold_store import load_fold, save_fold
from .neural_sufficiency_production import ExactComponentExecution
from .neural_sufficiency_runner import capacity_regime_from_oracle
from .neural_winner_artifact import required_payloads_for_head
from .train import ARM_FULL_PREFIX, FoldOOFResult, SelectedWinnerFoldResult


ASSETS = ("HG", "NKD", "SI")
ARMS = ("C0", "C1", "L0", "L1", "M1")
DECISIONS = ("direct_neural", "catboost")
MODE_END = {"E1": 20211231, "E2": 20220630, "E3": 20221230}


def execute_fit_only_rehearsal(
    *, e1r: Mapping[str, Any], e2r: Mapping[str, Any],
    g7: Mapping[str, Any], source_tree_sha256: str,
) -> Mapping[str, Any]:
    """Typed producer→engine E1r/E2r transition behind the Sep-2021 wall."""
    chronology = {
        stage: {f"{role.lower()}_days": bounds for role, bounds in
                fit_only_rehearsal_windows(stage).items()}
        for stage in ("E1r", "E2r")
    }
    typed_path_statuses = {
        "ELIGIBLE", "NO_FEASIBLE_THRESHOLD", "NO_FEASIBLE_FORWARD",
    }
    for name, stage in (("E1r", e1r), ("E2r", e2r)):
        if (not isinstance(stage, Mapping)
                or stage.get("status") not in typed_path_statuses
                or not _is_sha(stage.get("mapper"))
                or not _is_sha(stage.get("calibrator"))
                or not _is_sha(stage.get("weight_receipt"))
                or not _is_sha(stage.get("path_receipt_sha256"))
                or set(stage.get("thresholds", {})) != set(ASSETS)
                or set(stage.get("parity", {})) != set(ASSETS)
                or not all(stage["parity"].values())
                or type(stage.get("threshold_feasible")) is not bool
                or type(stage.get("forward_feasible")) is not bool):
            raise HeldStageRefusal(f"{name} fit-only rehearsal transition differs")
        expected_status = (
            "NO_FEASIBLE_THRESHOLD"
            if not stage["threshold_feasible"]
            else "NO_FEASIBLE_FORWARD"
            if not stage["forward_feasible"]
            else "ELIGIBLE"
        )
        if stage["status"] != expected_status:
            raise HeldStageRefusal(
                f"{name} fit-only status/feasibility reconciliation differs"
            )
        threshold_goal = stage.get("threshold_goal_recovery")
        forward_goal = stage.get("forward_goal_recovery")
        forward_feasibility = stage.get("forward_feasibility")
        if (stage.get("minimum_oracle_capture") != FIT_ONLY_MIN_ORACLE_CAPTURE
                or not isinstance(threshold_goal, Mapping)
                or not isinstance(forward_goal, Mapping)
                or not isinstance(forward_feasibility, Mapping)
                or set(threshold_goal) != set(ASSETS)
                or set(forward_goal) != set(ASSETS)
                or set(forward_feasibility) != set(ASSETS)):
            raise HeldStageRefusal(f"{name} goal-recovery surface differs")
        for asset in ASSETS:
            threshold_row = threshold_goal[asset]
            forward_row = forward_goal[asset]
            forward_gate = forward_feasibility[asset]
            if (not isinstance(threshold_row, Mapping)
                    or not isinstance(forward_row, Mapping)
                    or not isinstance(forward_gate, Mapping)
                    or type(threshold_row.get("eligible")) is not bool
                    or type(forward_row.get("eligible")) is not bool
                    or type(forward_gate.get("feasible")) is not bool
                    or threshold_row.get("minimum_oracle_capture")
                        != FIT_ONLY_MIN_ORACLE_CAPTURE
                    or forward_row.get("minimum_oracle_capture")
                        != FIT_ONLY_MIN_ORACLE_CAPTURE
                    or not _is_sha(threshold_row.get("receipt_sha256"))
                    or not _is_sha(forward_row.get("receipt_sha256"))
                    or not _is_sha(forward_gate.get(
                        "goal_recovery_receipt_sha256"))
                    or forward_gate["goal_recovery_receipt_sha256"]
                        != forward_row["receipt_sha256"]):
                raise HeldStageRefusal(
                    f"{name}/{asset} goal-recovery evidence differs")
        if (stage["threshold_feasible"]
                != all(bool(threshold_goal[a]["eligible"]) for a in ASSETS)
                or stage["forward_feasible"]
                != all(bool(forward_feasibility[a]["feasible"])
                       for a in ASSETS)):
            raise HeldStageRefusal(
                f"{name} goal-recovery booleans do not reproduce measurements")
        roles: dict[str, set[int]] = {}
        for field, (lower, upper) in chronology[name].items():
            raw_days = stage.get(field)
            if (not isinstance(raw_days, (tuple, list)) or not raw_days
                    or any(type(day) is not int or not lower <= day <= upper
                           for day in raw_days)
                    or tuple(sorted(set(raw_days))) != tuple(raw_days)):
                raise HeldStageRefusal(
                    f"{name} {field} differs from its frozen chronology")
            roles[field] = set(raw_days)
        role_names = tuple(roles)
        if any(roles[left] & roles[right] for index, left in enumerate(role_names)
               for right in role_names[index + 1:]):
            raise HeldStageRefusal(f"{name} fit-only chronology roles overlap")
    screen = e1r.get("probe_screen")
    if (not isinstance(screen, Mapping)
            or screen.get("schema") != "entry-v2-fit-only-e1r-measured-v1"
            or screen.get("status") not in {
                "ELIGIBLE", "NO_SIGNIFICANT_OBJECTIVE"}
            or screen.get("fit_only_max_d8") != 20210930
            or screen.get("optimizer_fit_count", 91) > 90
            or set(screen.get("ledger", {})) != {spec.probe_id for spec in PROBE_REGISTRY}
            or not screen.get("finalists")
            or not _is_sha(screen.get("receipt_sha256"))):
        raise HeldStageRefusal("E1r full-population measured atlas differs")
    declared_states = {item.value for item in CellAvailability}
    if any(not isinstance(row, Mapping)
           or row.get("status") not in declared_states
           for row in screen["ledger"].values()):
        raise HeldStageRefusal("E1r atlas ledger has an untyped probe state")
    matrix = e2r.get("arm_head_matrix")
    expected_matrix = {f"{arm}:{kind}" for arm in ARMS for kind in DECISIONS}
    if (not isinstance(matrix, Mapping)
            or matrix.get("schema") != "entry-v2-fit-only-e2r-measured-v1"
            or matrix.get("status") not in {
                "ELIGIBLE", "NO_FIT_ONLY_DEPLOYABLE_DEPTH"}
            or set(matrix.get("matrix", {})) != expected_matrix
            or matrix.get("diagnostic_path") not in expected_matrix
            or not _is_sha(matrix.get("objective_freeze_receipt_sha256"))
            or not _is_sha(matrix.get("receipt_sha256"))):
        raise HeldStageRefusal("E2r full-population five-arm/two-head matrix differs")
    if any(not isinstance(row, Mapping) or row.get("status") not in {
            "ELIGIBLE", "NO_FEASIBLE_THRESHOLD", "NO_FEASIBLE_FORWARD"}
           for row in matrix["matrix"].values()):
        raise HeldStageRefusal("E2r matrix has an untyped loser")
    deployable = matrix["status"] == "ELIGIBLE"
    if (deployable and (matrix.get("winner") not in expected_matrix
            or matrix.get("objective_status") != "ELIGIBLE"
            or matrix["matrix"][matrix["winner"]].get("status") != "ELIGIBLE")
            or (not deployable and matrix.get("winner") is not None)):
        raise HeldStageRefusal("E2r deployable status/winner differs")
    ceiling = g7.get("candidate_ceiling_receipts")
    selected_path = matrix.get("winner") or matrix.get("diagnostic_path")
    selected_arm, selected_head = (selected_path.split(":", 1)
                                   if isinstance(selected_path, str)
                                   and ":" in selected_path else (None, None))
    expected_learner_objective = (
        "A0_CURRENT_GROUPING" if selected_arm == "C0"
        else matrix.get("selected_objective"))
    if (not _is_sha(source_tree_sha256)
            or g7.get("single_real_path") != selected_path
            or selected_arm not in ARMS or selected_head not in DECISIONS
            or g7.get("selected_arm") != selected_arm
            or g7.get("selected_head") != selected_head
            or matrix.get("selected_learner_objective")
                != expected_learner_objective
            or g7.get("selected_objective")
                != matrix.get("selected_learner_objective")
            or not _is_sha(g7.get("learner_law_sha256"))
            or not _is_sha(g7.get("e1r_checkpoint_sha256"))
            or not _is_sha(g7.get("e2r_checkpoint_sha256"))
            or g7.get("e1r_checkpoint_sha256") == g7.get("e2r_checkpoint_sha256")
            or g7.get("e1r_fit_wall")
                != fit_only_rehearsal_windows("E1r")["FIT"][1]
            or g7.get("e2r_fit_wall")
                != fit_only_rehearsal_windows("E2r")["FIT"][1]
            or g7.get("same_full_learner_independent_fits") is not True
            or type(g7.get("all_asset_in_sample")) is not bool
            or type(g7.get("all_asset_disjoint_forward")) is not bool
            or g7.get("candidate_ceiling_all_blocks") is not True
            or not isinstance(ceiling, Mapping)
            or set(ceiling) != {
                "E1r.THRESHOLD", "E1r.FORWARD",
                "E2r.THRESHOLD", "E2r.FORWARD"}
            or any(not _is_sha(value) for value in ceiling.values())
            or g7.get("twins_counted") is not False):
        raise HeldStageRefusal("G7 fit-only rehearsal transition differs")
    goal_receipts = g7.get("goal_recovery_receipts")
    expected_goal_receipts = {
        f"{stage}.{role}.{asset}"
        for stage in ("E1r", "E2r")
        for role in ("THRESHOLD", "FORWARD")
        for asset in ASSETS
    }
    measured_goal_receipts = {
        f"{stage_name}.{role}.{asset}": transition[field][asset][
            "receipt_sha256"]
        for stage_name, transition in (("E1r", e1r), ("E2r", e2r))
        for role, field in (("THRESHOLD", "threshold_goal_recovery"),
                            ("FORWARD", "forward_goal_recovery"))
        for asset in ASSETS
    }
    if (g7.get("minimum_oracle_capture") != FIT_ONLY_MIN_ORACLE_CAPTURE
            or type(g7.get("goal_recovery_all_blocks")) is not bool
            or not isinstance(goal_receipts, Mapping)
            or set(goal_receipts) != expected_goal_receipts
            or any(not _is_sha(value) for value in goal_receipts.values())
            or dict(goal_receipts) != measured_goal_receipts
            or g7["goal_recovery_all_blocks"] != bool(
                g7["all_asset_in_sample"]
                and g7["all_asset_disjoint_forward"])):
        raise HeldStageRefusal("G7 goal-recovery authority differs")
    rehearsal_pass = bool(
        deployable
        and g7["all_asset_in_sample"]
        and g7["all_asset_disjoint_forward"]
        and g7["goal_recovery_all_blocks"]
        and e1r["status"] == "ELIGIBLE"
        and e2r["status"] == "ELIGIBLE"
    )
    if rehearsal_pass != (matrix.get("winner") is not None):
        raise HeldStageRefusal("fit-only PASS/winner reconciliation differs")
    result = {"schema": "entry-v2-fit-only-held-rehearsal-v1",
        "status": ("PASS" if rehearsal_pass
                   else "NO_FIT_ONLY_DEPLOYABLE_DEPTH"),
        "held_launch_permitted": rehearsal_pass,
        "first_failed_layer": (None if rehearsal_pass
            else ("OBJECTIVE_SCREEN" if screen.get("status") != "ELIGIBLE"
                  else "OBJECTIVE_REFIT" if
                       matrix.get("objective_status") != "ELIGIBLE"
                  else "POLICY_ECONOMICS")),
        "diagnostic_path": matrix.get("diagnostic_path"),
        "minimum_oracle_capture": FIT_ONLY_MIN_ORACLE_CAPTURE,
        "fit_only_max_d8": 20210930, "no_held_labels": True,
        "source_tree_sha256": source_tree_sha256,
        "e1r": dict(e1r), "e2r": dict(e2r), "g7": dict(g7)}
    result["receipt_sha256"] = _sha(result)
    return MappingProxyType(result)


class HeldStageRefusal(RuntimeError):
    pass


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(C.canonical_json_value(value), sort_keys=True,
                          separators=(",", ":"), allow_nan=False).encode()
    except (TypeError, ValueError) as exc:
        raise HeldStageRefusal("held-stage artifact is not canonical") from exc


def _sha(value: object) -> str:
    return hashlib.sha256(value if isinstance(value, bytes) else _canonical(value)).hexdigest()


def _is_sha(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(
        char in "0123456789abcdef" for char in value)


@dataclass(frozen=True)
class ProbeSupportInputs:
    kind: SupportKind
    asset: np.ndarray
    valid: np.ndarray
    values: np.ndarray | None = None
    required_levels: tuple[int, ...] = ()
    group_id: np.ndarray | None = None
    day: np.ndarray | None = None
    decision_ts: np.ndarray | None = None
    #: Cross-lane item 24: a finite RIGHT-CENSORED value is not an observation.
    #: ``support_gate`` requires this for the CONTINUOUS family.
    censored: np.ndarray | None = None
    at_risk: np.ndarray | None = None
    #: Corpus-receipt selected-horizon start wall (item 28); never a literal.
    selected_horizon_start_d8: int | None = None

    def validate_fit_slice(self) -> None:
        """Prove every support plane is physically confined to E1 FIT rows."""
        asset = np.asarray(self.asset)
        valid = np.asarray(self.valid)
        if asset.ndim != 1 or not len(asset) or valid.shape != asset.shape:
            raise HeldStageRefusal("E1 support asset/valid arrays are misaligned")
        if self.day is None:
            raise HeldStageRefusal("E1 support is missing its physical fit-day slice")
        day = np.asarray(self.day)
        if day.shape != asset.shape:
            raise HeldStageRefusal("E1 support day array is misaligned")
        try:
            numeric_day = day.astype(np.int64)
        except (TypeError, ValueError) as exc:
            raise HeldStageRefusal("E1 support day array is not numeric") from exc
        if np.any(numeric_day > 20210930):
            raise HeldStageRefusal("E1 support census crossed its fit boundary")
        # Cross-lane item 28: the upper wall was checked but not the lower one,
        # so a pre-start row could sit inside an "E1 FIT" support census.  The
        # wall is the corpus-receipt selected-horizon start day, never a literal.
        start_d8 = self.selected_horizon_start_d8
        if start_d8 is None:
            raise HeldStageRefusal(
                "E1 support slice lacks its selected-horizon start wall")
        if np.any(numeric_day < int(start_d8)):
            raise HeldStageRefusal(
                "E1 support census precedes the selected-horizon start wall")
        for name in ("values", "group_id", "decision_ts", "censored", "at_risk"):
            value = getattr(self, name)
            if value is not None and np.asarray(value).shape != asset.shape:
                raise HeldStageRefusal(f"E1 support {name} array is misaligned")

    def measure(self):
        return support_gate(
            self.kind, asset=self.asset, valid=self.valid, values=self.values,
            required_levels=self.required_levels or None, group_id=self.group_id,
            day=self.day, decision_ts=self.decision_ts, censored=self.censored,
        )


@dataclass(frozen=True)
class MeasuredProbeScreen:
    probe_id: str
    family_id: str
    arm: str
    decision_kind: str
    records: tuple[PairedObservationRecord, ...]
    support: ProbeSupportInputs
    target_vector: np.ndarray
    real_checkpoint_sha256: str
    twin_checkpoint_sha256: str
    row_manifest_sha256: str
    calibration_days: tuple[int, ...]
    path_receipts: Mapping[str, str]
    additional_support: tuple[ProbeSupportInputs, ...] = ()
    availability: CellAvailability = CellAvailability.MATERIALIZED
    path_availability: str = "MATERIALIZED"

    def __post_init__(self) -> None:
        try:
            availability = CellAvailability(self.availability)
        except (TypeError, ValueError) as exc:
            raise HeldStageRefusal("E1 availability is not a canonical atlas state") from exc
        object.__setattr__(self, "availability", availability)

    def validate(self) -> None:
        registered = {spec.probe_id for spec in PROBE_REGISTRY}
        supports = (self.support, *self.additional_support)
        for support in supports:
            support.validate_fit_slice()
        if self.availability is not CellAvailability.MATERIALIZED:
            if (self.probe_id not in registered
                    or self.records or self.path_receipts):
                raise HeldStageRefusal("typed unavailable E1 ledger row is invalid")
            return
        if self.path_availability not in {
                "MATERIALIZED", "UNAVAILABLE_NO_FEASIBLE_THRESHOLD"}:
            raise HeldStageRefusal("E1 path availability is invalid")
        target = np.asarray(self.target_vector, np.float64)
        if (self.probe_id not in registered or not self.family_id
                or self.arm != "SHARED_PRETEXT"
                or self.decision_kind != "shallow_probe"
                or not self.records or target.ndim != 1 or not len(target)
                or not np.all(np.isfinite(target))
                or any(not _is_sha(value) for value in (
                    self.real_checkpoint_sha256, self.twin_checkpoint_sha256,
                    self.row_manifest_sha256))
                or set(self.path_receipts) != {"real_funnel", "twin_funnel"}
                or any(not _is_sha(value) for value in self.path_receipts.values())
                or len(self.calibration_days) != 7
                or not all(20211001 <= day <= 20211029 for day in self.calibration_days)):
            raise HeldStageRefusal("E1 measured probe screen is incomplete")
        record_days = np.asarray([int(row.day) for row in self.records])
        if record_days.min() < 20211101 or record_days.max() > 20211231:
            raise HeldStageRefusal("E1 paired screen is not held-forward")


@dataclass(frozen=True)
class E1ScreenResult:
    finalists: tuple[str, ...]
    screen_by_probe: Mapping[str, MeasuredProbeScreen]
    paired_receipts: Mapping[str, str]
    support_receipts: Mapping[str, str]
    holm_receipt_sha256: str
    finalist_receipt_sha256: str
    artifact_sha256: str


def execute_e1_screen(rows: Sequence[MeasuredProbeScreen]) -> E1ScreenResult:
    measured = tuple(rows)
    expected = {spec.probe_id for spec in PROBE_REGISTRY}
    if (len({row.probe_id for row in measured}) != len(measured)
            or {row.probe_id for row in measured} != expected):
        raise HeldStageRefusal("E1 ledger must contain every registered probe exactly once")
    paired = {}; p_values = {}; family = {}; supported = {}
    paired_states: dict[str, str] = {}
    support_receipts = {}
    optimizer_fits = 2
    for row in measured:
        row.validate()
        if row.availability is not CellAvailability.MATERIALIZED:
            support_receipts[row.probe_id] = _sha(
                {"availability": row.availability.value})
            continue
        optimizer_fits += 2
        decisions = tuple(
            item.measure() for item in (row.support, *row.additional_support))
        support_receipts[row.probe_id] = _sha(
            {"support": [decision.receipt_sha256 for decision in decisions],
             "path_availability": row.path_availability})
        if any(decision.state is SupportState.UNAVAILABLE_LOW_SUPPORT
               for decision in decisions) or row.path_availability != "MATERIALIZED":
            continue
        test = paired_day_cluster_records(row.records)
        paired[row.probe_id] = test.receipt_sha256
        # Cross-lane item 25: hand the RESULT OBJECT to Holm.  A typed state
        # (DEGENERATE_ZERO_VARIANCE / UNAVAILABLE_LOW_SUPPORT) carries no
        # numeric p-value and is skipped explicitly rather than being certified.
        p_values[row.probe_id] = test
        paired_states[row.probe_id] = str(
            test.state.value if hasattr(test.state, "value") else test.state)
        family[row.probe_id] = row.family_id
        supported[row.probe_id] = row
    if not supported:
        raise HeldStageRefusal("E1 has no support-qualified objective")
    if optimizer_fits > 90:
        raise HeldStageRefusal("E1 exceeded two-pretext plus 88-probe fit budget")
    holm = hierarchical_holm(p_values, family)
    if not holm.surviving_probes:
        raise HeldStageRefusal("E1 hierarchical Holm selected no objective")
    ordered = sorted(holm.surviving_probes, key=lambda probe: (
        holm.probe_p_values[probe], probe))
    targets = [supported[probe].target_vector for probe in ordered]
    if len({len(value) for value in targets}) != 1:
        raise HeldStageRefusal("E1 target vectors are not row-aligned")
    matrix = np.stack(targets)
    correlation = np.eye(len(matrix)) if len(matrix) == 1 else np.corrcoef(matrix)
    if not np.all(np.isfinite(correlation)):
        raise HeldStageRefusal("E1 target correlation is degenerate")
    target_hashes = {probe: _sha(np.ascontiguousarray(
        supported[probe].target_vector).tobytes()) for probe in ordered}
    finalists = nonredundant_finalists(
        ordered, target_correlation=correlation, target_hashes=target_hashes,
        maximum=4,
    )
    if not finalists.finalists:
        raise HeldStageRefusal("E1 produced no nonredundant finalist")
    payload = {"supported": sorted(supported), "paired": paired,
               "paired_states": dict(sorted(paired_states.items())),
               "support": support_receipts, "holm": holm.receipt_sha256,
               # Cross-lane item 25: typed exclusions stay in the ledger.
               "holm_excluded_probes": list(holm.excluded_probes),
               "holm_excluded_probe_states": dict(holm.excluded_probe_states),
               "finalists": finalists.receipt_sha256,
               "registry_count": len(expected), "optimizer_fit_count": optimizer_fits}
    return E1ScreenResult(
        finalists.finalists,
        MappingProxyType({row.probe_id: row for row in measured}),
        MappingProxyType(paired),
        MappingProxyType(support_receipts), holm.receipt_sha256,
        finalists.receipt_sha256, _sha(payload),
    )


@dataclass(frozen=True)
class AssetEconomics:
    capacity_regime: str
    included_trading_days: int
    trades: int
    total_pnl_usd: float
    usd_per_trade: float
    usd_per_asset_day: float
    chronological_max_drawdown_usd: float
    drawdown_p90_usd: float
    oracle_total_pnl_usd: float
    oracle_usd_per_asset_day: float
    oracle_capture: float
    replay_receipt_sha256: str
    oracle_replay_receipt_sha256: str
    capacity_authority_sha256: str
    days_with_trades: int
    threshold_feasibility_sha256: str
    capacity_eligibility_sha256: str
    eligibility: str

    def __post_init__(self) -> None:
        total = float(self.total_pnl_usd)
        if (self.included_trading_days <= 0 or self.trades <= 0
                or not np.isfinite(total)
                or not _is_sha(self.replay_receipt_sha256)
                or not _is_sha(self.oracle_replay_receipt_sha256)
                or not _is_sha(self.capacity_authority_sha256)
                or self.days_with_trades < 0
                or not _is_sha(self.threshold_feasibility_sha256)
                or not _is_sha(self.capacity_eligibility_sha256)
                or self.eligibility != "ELIGIBLE"
                or float(self.chronological_max_drawdown_usd) < 0
                or float(self.drawdown_p90_usd) < 0
                # Ruling 21: goal-grade capture may lawfully exceed 1.0
                # (unfiltered replay vs the >=$600-filtered ceiling); the
                # arithmetic-impossibility law binds the exact-offer layer.
                or not 0.0 <= float(self.oracle_capture)
                or abs(total / self.included_trading_days
                       - float(self.usd_per_asset_day)) > 1e-9
                or abs(total / self.trades - float(self.usd_per_trade)) > 1e-9
                or abs(float(self.oracle_total_pnl_usd) / self.included_trading_days
                       - float(self.oracle_usd_per_asset_day)) > 1e-9):
            raise HeldStageRefusal("asset economics does not reconcile to canonical replay totals")

    def canonical(self) -> Mapping[str, Any]:
        return {"capacity_regime": self.capacity_regime,
                "included_trading_days": self.included_trading_days,
                "trades": self.trades, "total_pnl_usd": self.total_pnl_usd,
                "usd_per_trade": self.usd_per_trade,
                "usd_per_asset_day": self.usd_per_asset_day,
                "chronological_max_drawdown_usd": self.chronological_max_drawdown_usd,
                "drawdown_p90_usd": self.drawdown_p90_usd,
                "oracle_total_pnl_usd": self.oracle_total_pnl_usd,
                "oracle_usd_per_asset_day": self.oracle_usd_per_asset_day,
                "oracle_capture": self.oracle_capture,
                "replay_receipt_sha256": self.replay_receipt_sha256,
                "oracle_replay_receipt_sha256": self.oracle_replay_receipt_sha256,
                "capacity_authority_sha256": self.capacity_authority_sha256,
                "days_with_trades": self.days_with_trades,
                "threshold_feasibility_sha256": self.threshold_feasibility_sha256,
                "capacity_eligibility_sha256": self.capacity_eligibility_sha256,
                "eligibility": self.eligibility,
                "asset_day_denominator": "included_trading_days",
                "values_clipped": False}


@dataclass(frozen=True)
class MeasuredFinalistConfirmation:
    probe_id: str
    arm: str
    decision_kind: str
    aligned_days: tuple[int, ...]
    effect_by_asset: Mapping[str, np.ndarray]
    capture_effect_by_asset: Mapping[str, np.ndarray]
    economics: Mapping[str, AssetEconomics]
    selected_arm_sha256: str
    selected_objective_sha256: str
    calibrator_sha256: str
    thresholds_sha256: str
    capacity_authority_sha256: str
    mapper_sha256: str
    real_checkpoint_sha256: str
    twin_checkpoint_sha256: str
    parameter_count: int
    runtime_seconds: float
    fit_days: tuple[int, ...]
    calibration_days: tuple[int, ...]
    selection_days: tuple[int, ...]
    status: str = "ELIGIBLE"
    rejection_reason_by_asset: Mapping[str, str] | None = None
    funnel_receipt_by_asset: Mapping[str, str] | None = None
    platt_days: tuple[int, ...] = ()
    threshold_development_days: tuple[int, ...] = ()

    def validate(self, expected_probe: str) -> None:
        if (self.probe_id != expected_probe or self.arm not in ARMS
                or self.decision_kind not in DECISIONS or len(self.aligned_days) < 2
                or set(self.effect_by_asset) != set(ASSETS)
                or set(self.capture_effect_by_asset) != set(ASSETS)
                or (self.status == "ELIGIBLE" and set(self.economics) != set(ASSETS))
                or self.parameter_count <= 0 or self.runtime_seconds <= 0
                or not self.fit_days or max(self.fit_days) > 20220311
                or not self.calibration_days
                or not all(20220314 <= day <= 20220609 for day in self.calibration_days)
                or not self.selection_days
                or not all(20220610 <= day <= 20220630 for day in self.selection_days)
                or tuple(self.aligned_days) != tuple(self.selection_days)
                or any(not _is_sha(value) for value in (
                    self.selected_arm_sha256, self.selected_objective_sha256,
                    self.calibrator_sha256, self.thresholds_sha256,
                    self.capacity_authority_sha256, self.mapper_sha256,
                    self.real_checkpoint_sha256, self.twin_checkpoint_sha256))):
            raise HeldStageRefusal("E2 finalist confirmation is incomplete")
        if (not self.platt_days or not self.threshold_development_days
                or not all(20220314 <= day <= 20220427 for day in self.platt_days)
                or not all(20220428 <= day <= 20220609
                           for day in self.threshold_development_days)
                or set(self.platt_days) & set(self.threshold_development_days)
                or set(self.calibration_days) !=
                   set((*self.platt_days, *self.threshold_development_days))):
            raise HeldStageRefusal("E2 A-013 Platt/threshold chronology is invalid")
        if self.status not in {"ELIGIBLE", "NO_FEASIBLE_THRESHOLD"}:
            raise HeldStageRefusal("E2 confirmation status is unknown")
        if self.status == "NO_FEASIBLE_THRESHOLD" and (
                self.economics or set(self.rejection_reason_by_asset or {}) != set(ASSETS)
                or set(self.funnel_receipt_by_asset or {}) != set(ASSETS)
                or any(not _is_sha(value) for value in
                       (self.funnel_receipt_by_asset or {}).values())):
            raise HeldStageRefusal("typed E2 loser lacks exact all-asset funnel evidence")
        n = len(self.aligned_days)
        if any(np.asarray(self.effect_by_asset[a]).shape != (n,)
               or np.asarray(self.capture_effect_by_asset[a]).shape != (n,)
               for a in ASSETS):
            raise HeldStageRefusal("E2 finalist day effects are misaligned")


@dataclass(frozen=True)
class FrozenWinnerSelection:
    confirmation: MeasuredFinalistConfirmation
    romano_wolf_receipt_sha256: str
    lower_dollars_by_asset: Mapping[str, float]
    lower_capture_by_asset: Mapping[str, float]
    economics: Mapping[str, Mapping[str, Any]]
    selection_hashes: Mapping[str, str]
    objective_freeze_receipt_sha256: str
    artifact_sha256: str


def execute_e2_freeze(e1: E1ScreenResult,
                      confirmations: Sequence[MeasuredFinalistConfirmation],
                      objective_freeze_receipt_sha256: str,
                      ) -> FrozenWinnerSelection:
    measured = tuple(confirmations)
    keys = [(row.probe_id, row.arm, row.decision_kind) for row in measured]
    non_c0_probes = {row.probe_id for row in measured if row.arm != "C0"}
    expected_matrix = {(arm, decision) for arm in ARMS for decision in DECISIONS}
    if (not _is_sha(objective_freeze_receipt_sha256)
            or len(non_c0_probes) != 1
            or not non_c0_probes.issubset(set(e1.finalists))
            or any(row.probe_id != "A0_CURRENT_GROUPING"
                   for row in measured if row.arm == "C0")
            or {(row.arm, row.decision_kind) for row in measured} != expected_matrix
            or len(keys) != len(set(keys))
            or len(measured) != len(ARMS) * len(DECISIONS)
            or tuple((row.arm, row.decision_kind) for row in measured) !=
               tuple((arm, decision) for arm in ARMS for decision in DECISIONS)):
        raise HeldStageRefusal("E2 confirmations differ from frozen E1 finalists")
    through_e2_fit_count(len(e1.finalists))
    ids = []; assets = []; columns = []
    for row in measured:
        row.validate(row.probe_id)
        for asset in ASSETS:
            ids.append(f"{row.probe_id}:{row.arm}:{row.decision_kind}:{asset}")
            assets.append(asset)
            columns.append(np.asarray(row.effect_by_asset[asset], np.float64))
    effects = np.stack(columns, axis=1)
    rw = romano_wolf_lower_bounds(
        effects, hypothesis_ids=ids, hypothesis_assets=assets,
        hypothesis_families=[f"{row.probe_id}:{row.arm}:{row.decision_kind}"
                             for row in measured for _asset in ASSETS])
    capture_effects = np.stack([
        np.asarray(row.capture_effect_by_asset[asset], np.float64)
        for row in measured for asset in ASSETS
    ], axis=1)
    capture_rw = romano_wolf_lower_bounds(
        capture_effects, hypothesis_ids=ids, hypothesis_assets=assets,
        hypothesis_families=[f"{row.probe_id}:{row.arm}:{row.decision_kind}"
                             for row in measured for _asset in ASSETS])
    eligible = []
    for i, row in enumerate(measured):
        probe = row.probe_id
        dollar_lower = {asset: float(rw.simultaneous_lower_bounds[i * 3 + j])
                        for j, asset in enumerate(ASSETS)}
        capture_lower = {asset: float(capture_rw.simultaneous_lower_bounds[i * 3 + j])
                         for j, asset in enumerate(ASSETS)}
        # Cross-lane item 29: zero-variance hypotheses stay inside the same
        # 30-column family, but the statistics kernel now gives them a -inf
        # lower bound and marks them ineligible -- a deterministic column
        # carries no sampling evidence and may never be certified.
        window = slice(i * 3, i * 3 + 3)
        if not (np.all(np.asarray(rw.eligible_mask, bool)[window])
                and np.all(np.asarray(capture_rw.eligible_mask, bool)[window])):
            continue
        if (min(dollar_lower.values()) <= 0
                or min(capture_lower.values()) <= 0):
            continue
        if row.status != "ELIGIBLE":
            continue
        economics = {asset: row.economics[asset].canonical() for asset in ASSETS}
        capacity_hashes = {value["capacity_authority_sha256"] for value in economics.values()}
        if capacity_hashes != {row.capacity_authority_sha256}:
            raise HeldStageRefusal("E2 capacity authority differs across assets")
        capacity_document = {
            "schema": CAPACITY_SCHEMA,
            "values_clipped": False,
            "asset_day_denominator": "included_trading_days",
            "per_asset": {
                asset: {
                    key: value for key, value in economics[asset].items()
                    if key != "capacity_authority_sha256"
                }
                for asset in ASSETS
            },
        }
        try:
            validate_capacity_document(capacity_document, require_goal=True)
        except Exception as exc:
            raise HeldStageRefusal(
                f"{probe} capacity economics do not reproduce the shared law"
            ) from exc
        if _sha(capacity_document) != row.capacity_authority_sha256:
            raise HeldStageRefusal(
                f"{probe} capacity authority bytes are not reproducible"
            )
        for asset, value in economics.items():
            regime = capacity_regime_from_oracle(float(value["oracle_usd_per_asset_day"]))
            floor = ((regime == "FULL" and value["usd_per_asset_day"] >= 2000.0)
                     or (regime == "WEAK" and value["usd_per_asset_day"] >= 1500.0)
                     or (regime == "LOW" and value["usd_per_asset_day"] >= 1000.0
                         and value["chronological_max_drawdown_usd"] < 500.0))
            if (value["capacity_regime"] != regime or value["trades"] < 10
                    or value["usd_per_trade"] < 600.0 or not floor
                    or not _is_sha(value["replay_receipt_sha256"])):
                raise HeldStageRefusal(f"{probe}/{asset} misses canonical economics law")
        total_selection_pnl = float(sum(
            economics[a]["total_pnl_usd"] for a in ASSETS
        ))
        worst_mdd = float(max(economics[a]["chronological_max_drawdown_usd"] for a in ASSETS))
        # Runtime and host timing are non-semantic.  After the simultaneous
        # statistical/economic criteria, A-013 permits only lower deployed
        # parameter count and then the frozen registry probe id.
        key = (min(dollar_lower.values()), min(capture_lower.values()),
               total_selection_pnl, -worst_mdd, -row.parameter_count)
        identity = f"{probe}:{row.arm}:{row.decision_kind}"
        eligible.append((key, identity, row, dollar_lower, capture_lower, economics))
    if not eligible:
        raise HeldStageRefusal("E2 has no all-asset Romano-Wolf/economic survivor")
    best_key = max(item[0] for item in eligible)
    tied = [item for item in eligible if item[0] == best_key]
    _, _, winner, lower, capture, economics = min(
        tied, key=lambda item: (item[2].probe_id,
                                ARMS.index(item[2].arm),
                                DECISIONS.index(item[2].decision_kind)))
    selection = MappingProxyType({
        "selected_arm_sha256": winner.selected_arm_sha256,
        "selected_objective_sha256": winner.selected_objective_sha256,
        "calibrator_sha256": winner.calibrator_sha256,
        "thresholds_sha256": winner.thresholds_sha256,
        "capacity_authority_sha256": winner.capacity_authority_sha256,
    })
    combined_rw = _sha({"dollars": rw.receipt_sha256,
                        "capture": capture_rw.receipt_sha256})
    artifact = _sha({"e1": e1.artifact_sha256, "romano_wolf": combined_rw,
                     "objective_freeze": objective_freeze_receipt_sha256,
                     "selection": dict(selection), "economics": economics,
                     "selection_law":
                         "min-dollar-lb,min-capture-lb,total-pnl,-worst-mdd,-params,probe-id-v1"})
    return FrozenWinnerSelection(winner, combined_rw,
                                 MappingProxyType(lower), MappingProxyType(capture),
                                 MappingProxyType(economics), selection,
                                 objective_freeze_receipt_sha256, artifact)


@dataclass(frozen=True)
class HeldWinnerArtifacts:
    bundle_payloads: Mapping[str, bytes]
    primary_e3: SelectedWinnerFoldResult
    objective_probe_id: str
    policy_kind: str
    policy_factory: Any
    target_row_manifest_sha256: str

    def validate(self, winner: FrozenWinnerSelection) -> None:
        required_payloads = required_payloads_for_head(self.policy_kind)
        if set(self.bundle_payloads) != set(required_payloads):
            raise HeldStageRefusal("winner bundle payload set is incomplete")
        if any(not isinstance(value, bytes) or not value for value in self.bundle_payloads.values()):
            raise HeldStageRefusal("winner bundle contains an empty/nonbyte payload")
        if (not isinstance(self.primary_e3, SelectedWinnerFoldResult)
                or tuple(self.primary_e3.arm_evaluations) != (ARM_FULL_PREFIX,)
                or self.primary_e3.fold != "E3" or self.primary_e3.control_name != "PROPHET"
                or self.objective_probe_id != winner.confirmation.probe_id
                or self.policy_kind != winner.confirmation.decision_kind
                or self.policy_kind not in DECISIONS or not callable(self.policy_factory)
                or not _is_sha(self.target_row_manifest_sha256)):
            raise HeldStageRefusal("primary E3 fold differs from the frozen winner")
        expected = {
            "selected_arm_sha256": _sha(self.bundle_payloads["arm.json"]),
            "selected_objective_sha256": _sha(self.bundle_payloads["objective.json"]),
            "calibrator_sha256": _sha(self.bundle_payloads["calibrator.json"]),
            "thresholds_sha256": _sha(self.bundle_payloads["thresholds.json"]),
            "capacity_authority_sha256": _sha(self.bundle_payloads["capacity.json"]),
        }
        if expected != dict(winner.selection_hashes):
            raise HeldStageRefusal("winner payload bytes differ from E2 selection hashes")
        if _sha(self.bundle_payloads["mapper.json"]) != winner.confirmation.mapper_sha256:
            raise HeldStageRefusal("winner mapper bytes differ from E2 freeze")
        primary_winner = self.primary_e3.receipt.get("winner_adoption")
        if (not isinstance(primary_winner, Mapping)
                or primary_winner.get("legacy_full_prefix") is not False
                or primary_winner.get("bundle_sha256") is not None
                or primary_winner.get("arm") != winner.confirmation.arm
                or primary_winner.get("objective_sha256")
                    != winner.confirmation.selected_objective_sha256
                or primary_winner.get("decision_head_kind") != self.policy_kind
                or primary_winner.get("target_row_manifest_sha256")
                    != self.target_row_manifest_sha256
                or primary_winner.get("e2_frozen_selection_sha256")
                    != _sha(dict(winner.selection_hashes))
                or not _is_sha(primary_winner.get("target_control_sha256"))):
            raise HeldStageRefusal(
                "primary E3 receipt does not bind the acyclic E2 selection/target law"
            )
        for name in required_payloads:
            if name.endswith(".json"):
                try:
                    parsed = json.loads(self.bundle_payloads[name])
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise HeldStageRefusal(f"{name} is not JSON") from exc
                native_catboost = (name.startswith("catboost-")
                                   and name.split("-")[-1][:-5] in ASSETS)
                if (not isinstance(parsed, dict) or not parsed
                        or (not native_catboost and ("schema" not in parsed
                            or _canonical(parsed) != self.bundle_payloads[name]))):
                    raise HeldStageRefusal(f"{name} is not canonical schema-bearing JSON")
        objective = json.loads(self.bundle_payloads["objective.json"])
        row_manifest = json.loads(self.bundle_payloads["row-manifest.json"])
        if (objective.get("target_row_manifest_sha256") != self.target_row_manifest_sha256
                or row_manifest.get("target_row_manifest_sha256") !=
                self.target_row_manifest_sha256):
            raise HeldStageRefusal("bundle target-row manifest identity differs")


def _e3_economics(artifacts: HeldWinnerArtifacts
                  ) -> tuple[Mapping[str, Mapping[str, Any]], str,
                             Mapping[str, tuple[str, ...]]]:
    """Derive the held E3 capacity surface from the measured fold itself.

    E2 freezes the deployable policy bytes.  It cannot supply E3 economics: the
    E3 policy replay and the clean >=$600 candidate ceiling are both held data
    and must be read from the selected-only E3 report.
    """
    fold = artifacts.primary_e3
    try:
        policy_evaluation = fold.arm_evaluations[ARM_FULL_PREFIX]
        policy = {row.asset: row for row in policy_evaluation.by_asset}
        ceiling = {row.asset: row for row in fold.candidate_ceiling.evaluation.by_asset}
        preflight = fold.receipt["candidate_oracle_preflight"]
        oracle = preflight["per_asset"]
        thresholds = fold.arm_thresholds[ARM_FULL_PREFIX]
    except (KeyError, TypeError, AttributeError) as exc:
        raise HeldStageRefusal("held E3 lacks replay/oracle economics") from exc
    if (preflight.get("schema") != "entry-v2-candidate-oracle-preflight-v5"
            or preflight.get("passed") is not True
            or preflight.get("values_clipped_to_acceptance_floor") is not False
            or fold.candidate_ceiling.schedule_sha256
                != preflight.get("schedule_sha256")
            or set(policy) != set(ASSETS) or set(ceiling) != set(ASSETS)
            or set(oracle) != set(ASSETS)
            or set(thresholds) != set(ASSETS)):
        raise HeldStageRefusal("held E3 replay/oracle surface differs")
    rows: dict[str, dict[str, Any]] = {}
    for asset in ASSETS:
        learned = policy[asset]; upper = oracle[asset]
        try:
            days = int(upper["asset_days"])
            oracle_total = float(upper["total_pnl_usd"])
            oracle_per_day = float(upper["usd_per_asset_day"])
            oracle_replay = str(upper["oracle_replay_receipt_sha256"])
        except (KeyError, TypeError, ValueError) as exc:
            raise HeldStageRefusal(f"{asset} held E3 oracle row is incomplete") from exc
        upper_eval = ceiling[asset]
        if (learned.asset_days != days or upper_eval.asset_days != days
                or float(upper_eval.total_pnl_usd) != oracle_total
                or float(upper_eval.usd_per_asset_day) != oracle_per_day
                or days <= 0 or oracle_total <= 0):
            raise HeldStageRefusal(f"{asset} held E3 denominators/oracle differ")
        replay_receipt = _sha({
            "schema": "entry-v2-held-e3-policy-replay-v1",
            "fold": fold.fold, "asset": asset,
            "threshold": float(thresholds[asset]),
            "evaluation": asdict(learned),
            "target_control_sha256": fold.selected_identity[
                "target_control_sha256"],
        })
        days_with_trades = sum(row.asset == asset and row.trades > 0
                               for row in policy_evaluation.asset_day_results)
        rows[asset] = {
            "capacity_regime": capacity_regime_from_oracle(oracle_per_day),
            "included_trading_days": days,
            "trades": int(learned.trades),
            "total_pnl_usd": float(learned.total_pnl_usd),
            "usd_per_trade": float(learned.usd_per_trade),
            "usd_per_asset_day": float(learned.usd_per_asset_day),
            "chronological_max_drawdown_usd": float(learned.max_drawdown_usd),
            "drawdown_p90_usd": float(learned.drawdown_p90_usd),
            "oracle_total_pnl_usd": oracle_total,
            "oracle_usd_per_asset_day": oracle_per_day,
            "oracle_capture": float(learned.total_pnl_usd) / oracle_total,
            "replay_receipt_sha256": replay_receipt,
            "oracle_replay_receipt_sha256": oracle_replay,
            "days_with_trades": days_with_trades,
            "asset_day_denominator": "included_trading_days",
            "values_clipped": False,
        }
        eligibility = capacity_eligibility(rows[asset])
        rows[asset]["threshold_feasibility_sha256"] = (
            eligibility.threshold_feasibility_sha256)
        rows[asset]["required_floor_usd"] = eligibility.required_floor_usd
        rows[asset]["capacity_eligibility_sha256"] = eligibility.receipt_sha256
        rows[asset]["eligibility"] = (
            "ELIGIBLE" if eligibility.eligible else "INELIGIBLE")
        rows[asset]["eligibility_reasons"] = list(eligibility.reasons)
    document = {"schema": CAPACITY_SCHEMA, "values_clipped": False,
                "asset_day_denominator": "included_trading_days",
                "per_asset": rows}
    reasons = {asset: tuple(rows[asset]["eligibility_reasons"]) for asset in ASSETS}
    status = "PASS" if all(not value for value in reasons.values()) else "FAIL"
    try:
        validate_capacity_document(document, require_goal=(status == "PASS"))
    except Exception as exc:
        raise HeldStageRefusal("held E3 capacity document differs") from exc
    authority = _sha(document)
    economics = MappingProxyType({asset: {
        **rows[asset], "capacity_authority_sha256": authority,
    } for asset in ASSETS})
    return economics, status, MappingProxyType(reasons)


class ExactHeldStageEngine:
    """Stateful E1→E2→E3 engine; each transition is immutable and one-shot."""

    def __init__(self, artifact_root: Path) -> None:
        self.root = Path(artifact_root).resolve()
        self.e1: E1ScreenResult | None = None
        self.e2: FrozenWinnerSelection | None = None
        self.artifacts: HeldWinnerArtifacts | None = None
        self.acceptance_sha256: str | None = None
        self.e1_stage_sha256: str | None = None
        self.e2_stage_sha256: str | None = None

    @staticmethod
    def _execution(mode: str, artifact: str, details: Mapping[str, Any]) -> ExactComponentExecution:
        verified = _is_sha(artifact) and bool(details)
        return ExactComponentExecution(f"execute_{mode.lower()}", verified, not verified,
                                       MODE_END[mode], artifact, artifact, details)

    def execute_e1(self, acceptance_sha256: str,
                   screens: Sequence[MeasuredProbeScreen]) -> ExactComponentExecution:
        if self.e1 is not None or not _is_sha(acceptance_sha256):
            raise HeldStageRefusal("E1 transition or acceptance identity is invalid")
        self.e1 = execute_e1_screen(screens); self.acceptance_sha256 = acceptance_sha256
        measured = bool(self.e1.screen_by_probe and self.e1.paired_receipts)
        details = {"frozen_inputs": measured,
                   "frozen_objective": bool(self.e1.finalists),
                   "frozen_thresholds": all(
                       row.availability is not CellAvailability.MATERIALIZED
                       or bool(row.path_receipts)
                       for row in self.e1.screen_by_probe.values()),
                   "canonical_replay": all(
                       row.availability is not CellAvailability.MATERIALIZED
                       or bool(row.path_receipts)
                       for row in self.e1.screen_by_probe.values()),
                   "no_h2_open": max(MODE_END["E1"], 0) < 20250701,
                   "acceptance_sha256": acceptance_sha256,
                   "finalists": list(self.e1.finalists),
                   "holm_receipt_sha256": self.e1.holm_receipt_sha256}
        result = self._execution("E1", self.e1.artifact_sha256, details)
        self.e1_stage_sha256 = result.result_artifact_sha256
        return result

    def execute_e2(self, acceptance_sha256: str, prior_stage_sha256: str,
                   confirmations: Sequence[MeasuredFinalistConfirmation],
                   objective_freeze_receipt_sha256: str,
                   ) -> ExactComponentExecution:
        if (self.e1 is None or self.e2 is not None
                or acceptance_sha256 != self.acceptance_sha256
                or not _is_sha(prior_stage_sha256)):
            raise HeldStageRefusal("E2 chain identity differs")
        self.e2 = execute_e2_freeze(
            self.e1, confirmations, objective_freeze_receipt_sha256)
        details = {"frozen_inputs": bool(self.e2.selection_hashes),
                   "frozen_objective": _is_sha(
                       self.e2.selection_hashes["selected_objective_sha256"]),
                   "frozen_thresholds": _is_sha(
                       self.e2.selection_hashes["thresholds_sha256"]),
                   "canonical_replay": all(_is_sha(value["replay_receipt_sha256"])
                       for value in self.e2.economics.values()),
                   "no_h2_open": MODE_END["E2"] < 20250701,
                   "acceptance_sha256": acceptance_sha256,
                   "prior_stage_sha256": prior_stage_sha256,
                   **dict(self.e2.selection_hashes),
                   "economics": dict(self.e2.economics),
                   "romano_wolf_sha256": self.e2.romano_wolf_receipt_sha256}
        details["objective_freeze_receipt_sha256"] = objective_freeze_receipt_sha256
        result = self._execution("E2", self.e2.artifact_sha256, details)
        self.e2_stage_sha256 = result.result_artifact_sha256
        return result

    def execute_e3(self, acceptance_sha256: str, prior_stage_sha256: str,
                   artifacts: HeldWinnerArtifacts) -> ExactComponentExecution:
        if (self.e2 is None or self.artifacts is not None
                or acceptance_sha256 != self.acceptance_sha256
                or not _is_sha(prior_stage_sha256)):
            raise HeldStageRefusal("E3 chain identity differs")
        artifacts.validate(self.e2); self.artifacts = artifacts
        receipt = dict(artifacts.primary_e3.receipt)
        frozen = dict(self.e2.selection_hashes)
        expected = {"selected_arm_sha256", "selected_objective_sha256",
                    "calibrator_sha256", "thresholds_sha256",
                    "capacity_authority_sha256"}
        if set(frozen) != expected:
            raise HeldStageRefusal("E3 frozen selection schema differs")
        economics, held_status, held_reasons = _e3_economics(artifacts)
        artifact = _sha({"e2": self.e2.artifact_sha256, "fold_receipt": receipt,
                         "bundle_files": {k: _sha(v) for k, v in
                                          artifacts.bundle_payloads.items()},
                         "economics": dict(economics)})
        return self._execution("E3", artifact, {
            "frozen_inputs": bool(receipt),
            "frozen_objective": receipt.get("objective_sha256")
                == frozen["selected_objective_sha256"],
            "frozen_thresholds": _is_sha(frozen["thresholds_sha256"]),
            "canonical_replay": bool(artifacts.primary_e3.arm_evaluations),
            "no_h2_open": MODE_END["E3"] < 20250701,
            "acceptance_sha256": acceptance_sha256,
            "prior_stage_sha256": prior_stage_sha256, **frozen,
            "economics": dict(economics),
            "held_status": held_status,
            # Execution details cross an immutable JSON boundary.  Emit the
            # canonical JSON array representation before publication so a
            # strict crash-resume recomputation is byte/type identical.
            "held_reasons_by_asset": {
                asset: list(reasons)
                for asset, reasons in held_reasons.items()
            },
            "report_only": receipt.get("fold") == "E3",
            "no_selection_mutation": receipt.get("e2_frozen_selection_sha256")
                == _sha(dict(frozen)),
            "primary_e3_receipt_sha256": _sha(receipt),
        })

    def export_bundle_payloads(self) -> Mapping[str, bytes]:
        if self.artifacts is None:
            raise HeldStageRefusal("real E3 has not produced winner payloads")
        return MappingProxyType(dict(self.artifacts.bundle_payloads))

    def export_primary_e3(self) -> Path:
        if self.artifacts is None:
            raise HeldStageRefusal("real E3 has not produced a primary fold")
        path = self.root / "primary-e3-fold"
        save_fold(path, self.artifacts.primary_e3)
        loaded = load_fold(path)
        if loaded.fold != "E3" or loaded.control_name != "PROPHET":
            raise HeldStageRefusal("persisted primary E3 fold failed load canary")
        return path


__all__ = ["AssetEconomics", "E1ScreenResult", "ExactHeldStageEngine",
           "FrozenWinnerSelection", "HeldStageRefusal", "HeldWinnerArtifacts",
           "MeasuredFinalistConfirmation", "MeasuredProbeScreen",
           "ProbeSupportInputs", "execute_e1_screen", "execute_e2_freeze"]
