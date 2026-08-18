"""Fail-closed orchestration for the Entry V2 neural-sufficiency diagnostic.

This module owns no learner implementation.  It makes the exact implementations
prove competence on fit-only data, freezes that proof, and only then permits a
held-forward stage callback to run.  Injected callbacks keep the orchestration
mechanically testable; production mode additionally pins their public names.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import Any, Callable, Mapping, Sequence

from .capacity_contract import (
    FIT_ONLY_MIN_ORACLE_CAPTURE, SCHEMA as CAPACITY_SCHEMA,
    capacity_regime_from_oracle as canonical_capacity_regime,
    validate_capacity_document,
)


ASSETS = ("HG", "NKD", "SI")
MINIMUM_HOST_GIB = 320.0
DEVELOPMENT_WALL = 20250630
ACCEPTANCE_FIT_END = 20210930


class NeuralSufficiencyRefusal(RuntimeError):
    pass


class RunnerMode(str, Enum):
    PREHELD_FIT_ONLY_ACCEPTANCE = "preheld-fit-only-acceptance"
    E1 = "E1"
    E2 = "E2"
    E3 = "E3"


MODE_MAX_DAY = {
    RunnerMode.PREHELD_FIT_ONLY_ACCEPTANCE: ACCEPTANCE_FIT_END,
    RunnerMode.E1: 20211231,
    RunnerMode.E2: 20220630,
    RunnerMode.E3: 20221230,
}


ARM_COMPONENTS = tuple(f"arm_{name}" for name in ("C0", "C1", "L0", "L1", "M1"))
ACCEPTANCE_COMPONENTS = (
    "one_load", "raw_fidelity", *ARM_COMPONENTS, "atlas_probe_loss",
    "direct_head", "catboost", "mapper", "calibration", "threshold",
    "canonical_replay", "fit_ledger", "finalize",
)
HELD_COMPONENT = {
    RunnerMode.E1: "execute_e1",
    RunnerMode.E2: "execute_e2",
    RunnerMode.E3: "execute_e3",
}
PRODUCTION_CALLBACK_NAMES = {
    name: f"entry_v2_production_{name}" for name in (*ACCEPTANCE_COMPONENTS,
                                                     *HELD_COMPONENT.values())
}


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          allow_nan=False).encode()
    except (TypeError, ValueError) as error:
        raise NeuralSufficiencyRefusal("receipt is not canonical JSON") from error


def _is_sha(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def capacity_regime_from_oracle(oracle_usd_per_asset_day: float) -> str:
    """Derive the immutable capacity stratum; callers cannot choose a floor."""
    try:
        return canonical_capacity_regime(float(oracle_usd_per_asset_day))
    except Exception as exc:
        raise NeuralSufficiencyRefusal(str(exc)) from exc


def np_isfinite(value: float) -> bool:
    # Avoid importing a numerical runtime in the orchestration-only module.
    return value == value and value not in (float("inf"), float("-inf"))


@dataclass(frozen=True)
class RunContext:
    observed_max_day: int
    opened_through_day: int
    source_paths: tuple[str, ...]
    available_host_gib: float
    corpus_sha256: str
    chronology_sha256: str
    one_load_id: str


@dataclass(frozen=True)
class GateEvidence:
    component: str
    passed: bool
    production_exact: bool
    fit_only: bool
    maximum_day: int
    artifact_sha256: str
    details: Mapping[str, Any]


@dataclass(frozen=True)
class AcceptanceReceipt:
    schema: str
    mode: str
    status: str
    fit_end_day: int
    corpus_sha256: str
    chronology_sha256: str
    one_load_id: str
    callback_manifest_sha256: str
    component_artifacts: Mapping[str, str]
    evidence_sha256: str
    diagnostic_evidence_sha256: str
    acceptance_sha256: str


@dataclass(frozen=True)
class StageReceipt:
    schema: str
    mode: str
    status: str
    maximum_day: int
    acceptance_sha256: str
    prior_stage_sha256: str
    corpus_sha256: str
    chronology_sha256: str
    stage_artifact_sha256: str
    callback_manifest_sha256: str
    frozen_selection: Mapping[str, str]
    economics_sha256: str
    diagnostic_evidence_sha256: str
    stage_sha256: str


@dataclass(frozen=True)
class WinnerAdoptionReceipt:
    schema: str
    status: str
    acceptance_sha256: str
    e1_stage_sha256: str
    e2_stage_sha256: str
    e3_stage_sha256: str
    frozen_selection: Mapping[str, str]
    e3_economics_sha256: str
    diagnostic_evidence_sha256: str
    integration_ready: bool
    adoption_sha256: str


Backend = Callable[[RunContext], GateEvidence]


def _actual_available_gib() -> float:
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return float(line.split()[1]) / (1024.0 * 1024.0)
    raise NeuralSufficiencyRefusal("MemAvailable is unavailable")


def _validate_context(mode: RunnerMode, context: RunContext, *, production: bool) -> None:
    # A single cache may contain the complete pre-H2 development corpus.  Row
    # visibility is enforced per component below, not falsely represented as
    # physically unopened bytes here.
    if (context.observed_max_day > DEVELOPMENT_WALL
            or context.opened_through_day > DEVELOPMENT_WALL):
        raise NeuralSufficiencyRefusal("mode chronology or sealed 2025H2 wall was crossed")
    def sealed_payload(path: str) -> bool:
        name = Path(path).name.lower()
        components = tuple(part.lower() for part in Path(path).parts)
        return ("2025h2" in components or "2025h2" in name
                or re.search(r"(?:^|[^0-9])2026(?:0[1-9]|1[0-2])(?:[0-3][0-9])(?:[^0-9]|$)",
                             name) is not None)
    if any(sealed_payload(path) for path in context.source_paths):
        raise NeuralSufficiencyRefusal("sealed H2/2026 source was named before open")
    available = _actual_available_gib() if production else float(context.available_host_gib)
    if available < MINIMUM_HOST_GIB:
        raise NeuralSufficiencyRefusal("startup requires at least 320 GiB available host memory")
    if not (_is_sha(context.corpus_sha256) and _is_sha(context.chronology_sha256)
            and context.one_load_id):
        raise NeuralSufficiencyRefusal("context identities are incomplete")


def _callback_manifest(names: Sequence[str], backends: Mapping[str, Backend], *,
                       production: bool) -> str:
    if set(backends) != set(names):
        raise NeuralSufficiencyRefusal("callback set differs from the exact stage contract")
    manifest = []
    for name in names:
        callback = backends[name]
        if not callable(callback):
            raise NeuralSufficiencyRefusal(f"{name} callback is not callable")
        callback_name = getattr(callback, "__name__", "")
        if production and callback_name != PRODUCTION_CALLBACK_NAMES[name]:
            raise NeuralSufficiencyRefusal(f"{name} is not bound to its named production callback")
        manifest.append((name, callback_name))
    return _sha(_canonical(manifest))


def _call(name: str, callback: Backend, context: RunContext, *,
          maximum_day: int, require_fit_only: bool) -> GateEvidence:
    evidence = callback(context)
    if type(evidence) is not GateEvidence or evidence.component != name:
        raise NeuralSufficiencyRefusal(f"{name} returned a weak substitute receipt")
    if (not evidence.passed or not evidence.production_exact
            or evidence.maximum_day > maximum_day or not _is_sha(evidence.artifact_sha256)):
        raise NeuralSufficiencyRefusal(f"{name} did not prove exact competence")
    if require_fit_only and not evidence.fit_only:
        raise NeuralSufficiencyRefusal(f"{name} rehearsal is not fit-only")
    if (evidence.details.get("_visible_max_day") != evidence.maximum_day
            or not _is_sha(evidence.details.get("_frozen_row_manifest_sha256"))):
        raise NeuralSufficiencyRefusal(f"{name} lacks its immutable visible-row manifest")
    _canonical(dict(evidence.details))
    return evidence


def _require(details: Mapping[str, Any], keys: Sequence[str], component: str) -> None:
    if any(details.get(key) is not True for key in keys):
        raise NeuralSufficiencyRefusal(f"{component} is missing an exact acceptance invariant")


def _validate_acceptance_evidence(evidence: Mapping[str, GateEvidence], context: RunContext) -> None:
    one_load = evidence["one_load"].details
    _require(one_load, ("one_corpus_build", "one_session_cache",
                        "disk_backed_session_cache", "four_worker_preload",
                        "sequential_gpu", "catboost_not_overlapped", "atomic_boundaries"), "one_load")
    effective_memory = one_load.get("effective_memory_available_bytes")
    cache_capacity = one_load.get("array_cache_capacity_bytes")
    if (type(effective_memory) is not int or type(cache_capacity) is not int
            or one_load.get("one_load_id") != context.one_load_id
            or one_load.get("h2_open_count") != 0
            or one_load.get("candidate_suffix_rows_visited") != 0
            or effective_memory < 128 * 1024 ** 3
            or cache_capacity < 192 * 1024 ** 3):
        raise NeuralSufficiencyRefusal("one-load resource receipt differs")

    raw = evidence["raw_fidelity"].details
    _require(raw, ("left_searchsorted", "equal_time_excluded", "prefix_hashes_exact",
                   "all_21_raw_fields", "before_equal_after_pack", "causal_oracle_pass",
                   "raw_summary_learner_pass", "initial_book_trust_exact",
                   "snapshot_seed_exact", "adjacent_phase_exact"), "raw_fidelity")

    for component in ARM_COMPONENTS:
        arm = evidence[component].details
        _require(arm, ("all_routes_gradient", "suffix_bit_identical",
                       "reconstruction_pass", "balanced_oracle_overfit",
                       "shared_head_exact", "real_fit_only_rehearsal",
                       "time_band_routing", "no_retrain_occlusion"), component)
        if (arm.get("continuous_mae", 1.0) > 1e-3
                or arm.get("categorical_accuracy") != 1.0
                or arm.get("minimum_auroc", 0.0) < .995
                or arm.get("minimum_ap", 0.0) < .995
                or arm.get("maximum_bce", 1.0) > .02
                or arm.get("assets") != list(ASSETS)):
            raise NeuralSufficiencyRefusal(f"{component} competence thresholds failed")

    atlas = evidence["atlas_probe_loss"].details
    _require(atlas, ("all_44_registered", "all_losses_numeric_gradient",
                     "real_beyond_recipient_fixed_twin", "support_typed",
                     "materialization_end_to_end"), "atlas_probe_loss")
    if atlas.get("registered_e1_slots") != 90 or atlas.get("maximum_through_e2") != 98:
        raise NeuralSufficiencyRefusal("atlas fit law differs from 90/98")

    direct = evidence["direct_head"].details
    catboost = evidence["catboost"].details
    _require(direct, ("balanced_oracle_overfit", "every_head_gradient", "identical_representation"),
             "direct_head")
    _require(catboost, ("balanced_oracle_overfit", "singleton_action_classifier",
                        "deterministic_cpu"), "catboost")
    if (catboost.get("pairlogit_group_semantics") != "asset-day-phase"
            or catboost.get("equal_timestamp_claim") is not False
            or set(catboost.get("pair_group_count_by_asset", {})) != set(ASSETS)
            or min(catboost["pair_group_count_by_asset"].values()) < 40
            or set(catboost.get("pair_accuracy_by_asset", {})) != set(ASSETS)
            or any(value is None for value in
                   catboost["pair_accuracy_by_asset"].values())
            or not _is_sha(catboost.get("pair_row_manifest_sha256"))
            or set(catboost.get("pair_manifest_sha256_by_asset", {})) != set(ASSETS)
            or any(not _is_sha(value) for value in
                   catboost["pair_manifest_sha256_by_asset"].values())):
        raise NeuralSufficiencyRefusal(
            "CatBoost competence lacks measured all-asset PairLogit depth")
    if (direct.get("representation_sha256") != catboost.get("representation_sha256")
            or not _is_sha(direct.get("representation_sha256"))):
        raise NeuralSufficiencyRefusal("direct head and CatBoost did not use identical representations")

    mapper = evidence["mapper"].details
    calibration = evidence["calibration"].details
    threshold = evidence["threshold"].details
    replay = evidence["canonical_replay"].details
    _require(mapper, ("a004_mask_exact", "fit_only", "positive_skill"), "mapper")
    _require(calibration, ("positive_slope", "chronological", "fit_disjoint"), "calibration")
    _require(threshold, ("chronological", "calibration_disjoint", "no_held_labels",
                         "canonical_fast_sweep", "selected_threshold_parity"), "threshold")
    _require(replay, ("canonical_parity", "equal_time_ties", "occupancy_caps_cost_wall",
                      "full_denominator", "mdd_exact", "fit_only_end_to_end",
                      "teacher_isolation_exact"), "canonical_replay")
    partitions = {
        "fit": tuple(mapper.get("row_ids", ())),
        "calibration": tuple(calibration.get("row_ids", ())),
        "threshold": tuple(threshold.get("row_ids", ())),
    }
    if any(not rows or len(set(rows)) != len(rows) for rows in partitions.values()):
        raise NeuralSufficiencyRefusal("mapper/calibration/threshold partitions are incomplete")
    if any(set(partitions[a]) & set(partitions[b]) for a, b in
           (("fit", "calibration"), ("fit", "threshold"), ("calibration", "threshold"))):
        raise NeuralSufficiencyRefusal("mapper/calibration/threshold partitions overlap")
    competence_manifests = {evidence[name].details.get("candidate_manifest_sha256")
                            for name in ("direct_head", "catboost")}
    policy_manifests = {evidence[name].details.get("candidate_manifest_sha256")
                        for name in ("mapper", "calibration", "threshold",
                                     "canonical_replay")}
    if (len(competence_manifests) != 1
            or not _is_sha(next(iter(competence_manifests)))
            or len(policy_manifests) != 1
            or not _is_sha(next(iter(policy_manifests)))
            or competence_manifests == policy_manifests):
        raise NeuralSufficiencyRefusal(
            "competence/full-policy candidate manifests are not independently frozen")

    ledger = evidence["fit_ledger"].details
    _require(ledger, ("all_fits_counted", "competence_separate"), "fit_ledger")
    if (ledger.get("e1_registered_slots") != 90
            or ledger.get("through_e2_optimizer_fits", 99) > 98
            or ledger.get("discarded_competence_fits", 0) < 1):
        raise NeuralSufficiencyRefusal("global fit ledger violates 90/98 accounting")
    finalizer = evidence["finalize"].details
    _require(finalizer, ("all_components_complete", "fit_only_boundary_frozen",
                         "one_load_retained_for_held", "immutable_chain_complete",
                         "restart_payload_complete"), "finalize")
    if (finalizer.get("restartable_boundaries") is not False
            or finalizer.get("m8_reload_proof_sha256") is not None):
        raise NeuralSufficiencyRefusal(
            "fit-only boundary pretends it was already reloaded")
    if finalizer.get("one_load_id") != context.one_load_id:
        raise NeuralSufficiencyRefusal("finalizer closed a different one-load execution")
    rehearsal = finalizer.get("held_rehearsal")
    if (not isinstance(rehearsal, Mapping)
            or rehearsal.get("schema") != "entry-v2-fit-only-held-rehearsal-v1"
            or rehearsal.get("status") not in {
                "PASS", "NO_FIT_ONLY_DEPLOYABLE_DEPTH"}
            or rehearsal.get("minimum_oracle_capture")
                != FIT_ONLY_MIN_ORACLE_CAPTURE
            or rehearsal.get("fit_only_max_d8") != 20210930
            or rehearsal.get("no_held_labels") is not True
            or type(rehearsal.get("held_launch_permitted")) is not bool
            or (rehearsal.get("status") == "PASS") !=
                rehearsal.get("held_launch_permitted")
            or not _is_sha(rehearsal.get("source_tree_sha256"))
            or not _is_sha(rehearsal.get("receipt_sha256"))):
        raise NeuralSufficiencyRefusal("fit-only held rehearsal receipt differs")
    g7 = rehearsal.get("g7")
    arm_matrix = rehearsal.get("e2r", {}).get("arm_head_matrix", {}) \
        if isinstance(rehearsal.get("e2r"), Mapping) else {}
    selected_path = (arm_matrix.get("winner")
                     or arm_matrix.get("diagnostic_path"))
    expected_learner_objective = (
        "A0_CURRENT_GROUPING"
        if isinstance(selected_path, str) and selected_path.startswith("C0:")
        else arm_matrix.get("selected_objective"))
    expected_goal_receipts = {
        f"{stage}.{role}.{asset}"
        for stage in ("E1r", "E2r")
        for role in ("THRESHOLD", "FORWARD")
        for asset in ASSETS
    }
    if (not isinstance(g7, Mapping)
            or g7.get("single_real_path") != selected_path
            or not isinstance(selected_path, str) or ":" not in selected_path
            or g7.get("selected_arm") != selected_path.split(":", 1)[0]
            or g7.get("selected_head") != selected_path.split(":", 1)[1]
            or arm_matrix.get("selected_learner_objective")
                != expected_learner_objective
            or g7.get("selected_objective")
                != arm_matrix.get("selected_learner_objective")
            or not _is_sha(g7.get("learner_law_sha256"))
            or not _is_sha(g7.get("e1r_checkpoint_sha256"))
            or not _is_sha(g7.get("e2r_checkpoint_sha256"))
            or g7.get("e1r_checkpoint_sha256") == g7.get("e2r_checkpoint_sha256")
            or g7.get("e1r_fit_wall") != 20210709
            or g7.get("e2r_fit_wall") != 20210813
            or g7.get("same_full_learner_independent_fits") is not True
            or type(g7.get("all_asset_in_sample")) is not bool
            or type(g7.get("all_asset_disjoint_forward")) is not bool
            or g7.get("candidate_ceiling_all_blocks") is not True
            or g7.get("twins_counted") is not False
            or g7.get("minimum_oracle_capture")
                != FIT_ONLY_MIN_ORACLE_CAPTURE
            or type(g7.get("goal_recovery_all_blocks")) is not bool
            or set(g7.get("goal_recovery_receipts", {}))
                != expected_goal_receipts
            or any(not _is_sha(value) for value in
                   g7.get("goal_recovery_receipts", {}).values())
            or set(g7.get("candidate_ceiling_receipts", {})) != {
                "E1r.THRESHOLD", "E1r.FORWARD", "E2r.THRESHOLD", "E2r.FORWARD"}
            or any(not _is_sha(value) for value in
                   g7.get("candidate_ceiling_receipts", {}).values())):
        raise NeuralSufficiencyRefusal("G7 fit-only depth rehearsal differs")
    if rehearsal["status"] == "PASS" and not (
            g7["all_asset_in_sample"] and g7["all_asset_disjoint_forward"]
            and g7["goal_recovery_all_blocks"]):
        raise NeuralSufficiencyRefusal("fit-only PASS lacks all-asset feasibility")


def _atomic_immutable_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise NeuralSufficiencyRefusal("immutable stage receipt already exists")
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(_canonical(payload)); stream.flush(); os.fsync(stream.fileno())
        os.chmod(temporary, 0o444)
        # link is no-replace; replace/rename would silently overwrite a receipt.
        os.link(temporary, path)
        os.unlink(temporary)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _acceptance_payload(receipt: AcceptanceReceipt) -> dict[str, Any]:
    value = asdict(receipt); value.pop("acceptance_sha256")
    return value


def load_acceptance_receipt(
    path: str | Path, *, allow_diagnostic_fail: bool = False,
) -> AcceptanceReceipt:
    target = Path(path)
    if not target.is_file() or stat.S_IMODE(target.stat().st_mode) & 0o222:
        raise NeuralSufficiencyRefusal("acceptance receipt is absent or mutable")
    try:
        receipt = AcceptanceReceipt(**json.loads(target.read_text()))
    except Exception as error:
        raise NeuralSufficiencyRefusal("acceptance receipt cannot be decoded") from error
    allowed_status = ({"PASS", "NO_FIT_ONLY_DEPLOYABLE_DEPTH"}
                      if allow_diagnostic_fail else {"PASS"})
    if (receipt.schema != "entry-v2-fit-only-acceptance-v2"
            or receipt.mode != RunnerMode.PREHELD_FIT_ONLY_ACCEPTANCE.value
            or receipt.status not in allowed_status
            or receipt.fit_end_day != ACCEPTANCE_FIT_END
            or set(receipt.component_artifacts) != set(ACCEPTANCE_COMPONENTS)
            or any(not _is_sha(x) for x in receipt.component_artifacts.values())
            or not _is_sha(receipt.diagnostic_evidence_sha256)
            or _sha(_canonical(_acceptance_payload(receipt))) != receipt.acceptance_sha256):
        raise NeuralSufficiencyRefusal("fit-only acceptance receipt is incomplete or altered")
    return receipt


def load_stage_receipt(path: str | Path) -> StageReceipt:
    target = Path(path)
    if not target.is_file() or stat.S_IMODE(target.stat().st_mode) & 0o222:
        raise NeuralSufficiencyRefusal("stage receipt is absent or mutable")
    try:
        receipt = StageReceipt(**json.loads(target.read_text()))
    except Exception as error:
        raise NeuralSufficiencyRefusal("stage receipt cannot be decoded") from error
    value = asdict(receipt); declared = value.pop("stage_sha256")
    valid_status = (receipt.status == "PASS"
                    or (receipt.mode == "E3" and receipt.status == "FAIL"))
    if (receipt.schema != "entry-v2-neural-sufficiency-stage-v2"
            or not valid_status
            or not _is_sha(receipt.diagnostic_evidence_sha256)
            or _sha(_canonical(value)) != declared):
        raise NeuralSufficiencyRefusal("stage receipt is incomplete or altered")
    return receipt


def adopt_e3_winner(*, acceptance_receipt_path: str | Path,
                    e1_receipt_path: str | Path, e2_receipt_path: str | Path,
                    e3_receipt_path: str | Path, output_path: str | Path
                    ) -> WinnerAdoptionReceipt:
    acceptance = load_acceptance_receipt(acceptance_receipt_path)
    e1, e2, e3 = (load_stage_receipt(path) for path in
                  (e1_receipt_path, e2_receipt_path, e3_receipt_path))
    if ((e1.mode, e2.mode, e3.mode) != ("E1", "E2", "E3")
            or any(row.acceptance_sha256 != acceptance.acceptance_sha256
                   for row in (e1, e2, e3))
            or any(row.diagnostic_evidence_sha256
                   != acceptance.diagnostic_evidence_sha256
                   for row in (e1, e2, e3))
            or e2.prior_stage_sha256 != e1.stage_sha256
            or e3.prior_stage_sha256 != e2.stage_sha256
            or e3.status != "PASS"
            or not e2.frozen_selection
            or not _is_sha(e2.economics_sha256) or not _is_sha(e3.economics_sha256)
            or dict(e3.frozen_selection) != dict(e2.frozen_selection)):
        raise NeuralSufficiencyRefusal("winner adoption chain is incomplete or changed")
    base = WinnerAdoptionReceipt(
        "entry-v2-neural-winner-adoption-v2", "PENDING_INTEGRATION",
        acceptance.acceptance_sha256,
        e1.stage_sha256, e2.stage_sha256, e3.stage_sha256,
        dict(e3.frozen_selection), e3.economics_sha256,
        acceptance.diagnostic_evidence_sha256, False, "",
    )
    value = asdict(base); value.pop("adoption_sha256")
    receipt = WinnerAdoptionReceipt(**value, adoption_sha256=_sha(_canonical(value)))
    _atomic_immutable_json(Path(output_path), asdict(receipt))
    return receipt


def load_winner_adoption(path: str | Path) -> WinnerAdoptionReceipt:
    target = Path(path)
    if not target.is_file() or stat.S_IMODE(target.stat().st_mode) & 0o222:
        raise NeuralSufficiencyRefusal("winner adoption receipt is absent or mutable")
    try:
        receipt = WinnerAdoptionReceipt(**json.loads(target.read_text()))
    except Exception as error:
        raise NeuralSufficiencyRefusal("winner adoption cannot be decoded") from error
    value = asdict(receipt); declared = value.pop("adoption_sha256")
    if (receipt.schema != "entry-v2-neural-winner-adoption-v2"
            or receipt.status != "PENDING_INTEGRATION" or receipt.integration_ready is not False
            or _sha(_canonical(value)) != declared
            or not _is_sha(receipt.diagnostic_evidence_sha256)
            or any(not _is_sha(x) for x in receipt.frozen_selection.values())):
        raise NeuralSufficiencyRefusal("winner adoption is incomplete or altered")
    return receipt


def run_neural_sufficiency(
    mode: RunnerMode | str, context: RunContext, backends: Mapping[str, Backend], *,
    output_path: str | Path, acceptance_receipt_path: str | Path | None = None,
    prior_stage_receipt_path: str | Path | None = None,
    production: bool = False,
) -> AcceptanceReceipt | StageReceipt:
    mode = RunnerMode(mode)
    _validate_context(mode, context, production=production)
    target = Path(output_path)
    if mode is RunnerMode.PREHELD_FIT_ONLY_ACCEPTANCE:
        if acceptance_receipt_path is not None:
            raise NeuralSufficiencyRefusal("acceptance mode cannot consume an earlier acceptance")
        callback_hash = _callback_manifest(ACCEPTANCE_COMPONENTS, backends,
                                           production=production)
        evidence = {name: _call(name, backends[name], context,
                                maximum_day=ACCEPTANCE_FIT_END,
                                require_fit_only=True)
                    for name in ACCEPTANCE_COMPONENTS}
        _validate_acceptance_evidence(evidence, context)
        evidence_payload = {name: asdict(value) for name, value in evidence.items()}
        diagnostic_evidence_sha256 = evidence["finalize"].details.get(
            "diagnostic_evidence_sha256")
        if not _is_sha(diagnostic_evidence_sha256):
            if production:
                raise NeuralSufficiencyRefusal(
                    "finalizer lacks immutable diagnostic evidence")
            diagnostic_evidence_sha256 = evidence["finalize"].artifact_sha256
        rehearsal = evidence["finalize"].details["held_rehearsal"]
        acceptance_status = str(rehearsal["status"])
        base = AcceptanceReceipt(
            "entry-v2-fit-only-acceptance-v2", mode.value, acceptance_status,
            ACCEPTANCE_FIT_END, context.corpus_sha256, context.chronology_sha256,
            context.one_load_id, callback_hash,
            {name: value.artifact_sha256 for name, value in evidence.items()},
            _sha(_canonical(evidence_payload)), diagnostic_evidence_sha256, "",
        )
        receipt = AcceptanceReceipt(**_acceptance_payload(base),
                                    acceptance_sha256=_sha(_canonical(_acceptance_payload(base))))
        _atomic_immutable_json(target, asdict(receipt))
        return receipt

    if acceptance_receipt_path is None:
        raise NeuralSufficiencyRefusal("held-forward mode requires fit-only acceptance")
    acceptance = load_acceptance_receipt(acceptance_receipt_path)
    if (acceptance.corpus_sha256 != context.corpus_sha256
            or acceptance.chronology_sha256 != context.chronology_sha256
            or acceptance.one_load_id != context.one_load_id):
        raise NeuralSufficiencyRefusal("held-forward context differs from accepted fit-only context")
    name = HELD_COMPONENT[mode]
    prior_sha = acceptance.acceptance_sha256
    if mode in (RunnerMode.E2, RunnerMode.E3):
        if prior_stage_receipt_path is None:
            raise NeuralSufficiencyRefusal(f"{mode.value} requires its prior immutable stage")
        prior = load_stage_receipt(prior_stage_receipt_path)
        expected_prior = "E1" if mode is RunnerMode.E2 else "E2"
        if (prior.mode != expected_prior
                or prior.acceptance_sha256 != acceptance.acceptance_sha256):
            raise NeuralSufficiencyRefusal("held stage chain is discontinuous")
        prior_sha = prior.stage_sha256
    callback_hash = _callback_manifest((name,), backends, production=production)
    evidence = _call(name, backends[name], context,
                     maximum_day=MODE_MAX_DAY[mode], require_fit_only=False)
    if evidence.maximum_day != MODE_MAX_DAY[mode]:
        raise NeuralSufficiencyRefusal("held stage did not cover its exact chronology")
    details = evidence.details
    diagnostic_evidence_sha256 = details.get("diagnostic_evidence_sha256")
    if diagnostic_evidence_sha256 is None and not production:
        diagnostic_evidence_sha256 = acceptance.diagnostic_evidence_sha256
    if diagnostic_evidence_sha256 != acceptance.diagnostic_evidence_sha256:
        raise NeuralSufficiencyRefusal(
            "held stage diagnostic evidence differs from acceptance")
    _require(details, ("frozen_inputs", "frozen_objective", "frozen_thresholds",
                       "canonical_replay", "no_h2_open"), name)
    if details.get("acceptance_sha256") != acceptance.acceptance_sha256:
        raise NeuralSufficiencyRefusal("held stage did not consume the accepted boundary")
    if mode in (RunnerMode.E2, RunnerMode.E3) and details.get("prior_stage_sha256") != prior_sha:
        raise NeuralSufficiencyRefusal("held callback did not consume its prior stage")
    selection: dict[str, str] = {}
    economics_sha256 = ""
    held_status = "PASS"
    if mode in (RunnerMode.E2, RunnerMode.E3):
        if mode is RunnerMode.E3:
            held_status = str(details.get("held_status", ""))
            if held_status not in {"PASS", "FAIL"}:
                raise NeuralSufficiencyRefusal("E3 lacks typed PASS/FAIL status")
            reasons = details.get("held_reasons_by_asset")
            if (not isinstance(reasons, Mapping) or set(reasons) != set(ASSETS)
                    or (held_status == "PASS" and any(reasons.values()))
                    or (held_status == "FAIL" and not any(reasons.values()))):
                raise NeuralSufficiencyRefusal("E3 typed status/reasons differ")
        selection = {key: str(details.get(key, "")) for key in (
            "selected_arm_sha256", "selected_objective_sha256",
            "calibrator_sha256", "thresholds_sha256",
            "capacity_authority_sha256")}
        if any(not _is_sha(value) for value in selection.values()):
            raise NeuralSufficiencyRefusal("held stage lacks frozen winner selection hashes")
        if mode is RunnerMode.E3 and selection != dict(prior.frozen_selection):
            raise NeuralSufficiencyRefusal("E3 changed the E2-frozen winner")
        economics = details.get("economics")
        if not isinstance(economics, Mapping) or set(economics) != set(("HG", "NKD", "SI")):
            raise NeuralSufficiencyRefusal("held winner lacks exact per-asset economics")
        authority_hashes: set[str] = set()
        for asset in ("HG", "NKD", "SI"):
            row = economics[asset]
            if not isinstance(row, Mapping):
                raise NeuralSufficiencyRefusal("held economics row is invalid")
            try:
                regime = str(row["capacity_regime"])
                days = int(row["included_trading_days"]); trades = int(row["trades"])
                total = float(row["total_pnl_usd"])
                per_trade = float(row["usd_per_trade"])
                per_day = float(row["usd_per_asset_day"])
                drawdown = float(row["chronological_max_drawdown_usd"])
                drawdown_p90 = float(row["drawdown_p90_usd"])
                replay_hash = row["replay_receipt_sha256"]
                authority_hash = row["capacity_authority_sha256"]
                oracle_total = float(row["oracle_total_pnl_usd"])
                oracle_per_day = float(row["oracle_usd_per_asset_day"])
                oracle_capture = float(row["oracle_capture"])
                oracle_replay_hash = row["oracle_replay_receipt_sha256"]
            except (KeyError, TypeError, ValueError) as error:
                raise NeuralSufficiencyRefusal("held economics schema is incomplete") from error
            derived_regime = capacity_regime_from_oracle(oracle_per_day)
            floor_pass = ((derived_regime == "FULL" and per_day >= 2000.0)
                          or (regime == "WEAK" and per_day >= 1500.0)
                          or (regime == "LOW" and per_day >= 1000.0 and drawdown < 500.0))
            exact_policy_money = (
                np_isfinite(total) and np_isfinite(per_trade) and np_isfinite(per_day)
                and abs(per_day - total / days) <= 1e-9
                and ((trades > 0 and abs(per_trade - total / trades) <= 1e-9)
                     or (trades == 0 and total == 0.0 and per_trade == 0.0))
            ) if days > 0 and trades >= 0 else False
            exact_oracle_money = (
                np_isfinite(oracle_total) and np_isfinite(oracle_per_day)
                and abs(oracle_per_day - oracle_total / days) <= 1e-9
            ) if days > 0 else False
            goal_required = mode is RunnerMode.E2 or held_status == "PASS"
            goal_miss = (trades < 10 or per_trade < 600.0 or not floor_pass)
            if (days < 1 or trades < 0
                    or not np_isfinite(drawdown) or drawdown < 0
                    or not np_isfinite(drawdown_p90) or drawdown_p90 < 0
                    or not np_isfinite(oracle_capture)
                    or (goal_required and not 0.0 <= oracle_capture <= 1.0)
                    or regime != derived_regime or (goal_required and goal_miss)
                    or not exact_policy_money or not exact_oracle_money
                    or not _is_sha(replay_hash) or not _is_sha(oracle_replay_hash)
                    or not _is_sha(authority_hash)
                    or row.get("asset_day_denominator") != "included_trading_days"
                    or row.get("values_clipped") is not False):
                raise NeuralSufficiencyRefusal(f"{asset} held economics missed the frozen goal law")
            authority_hashes.add(authority_hash)
        if len(authority_hashes) != 1:
            raise NeuralSufficiencyRefusal("held capacity authority differs across assets")
        declared_authority = next(iter(authority_hashes))
        # The authority digest is over the exact unclipped capacity document
        # before its digest is copied into each asset row.  Recompute it here;
        # a callback-supplied 64-character string is not capacity evidence.
        authority_document = {"schema": CAPACITY_SCHEMA,
            "values_clipped": False,
            "asset_day_denominator": "included_trading_days",
            "per_asset": {asset: {
                key: value for key, value in dict(economics[asset]).items()
                if key != "capacity_authority_sha256"
            } for asset in ASSETS}}
        if _sha(_canonical(authority_document)) != declared_authority:
            raise NeuralSufficiencyRefusal("held capacity authority is not reproducible")
        # E2 freezes its capacity payload as part of the deployed winner.  E3
        # retains that selection identity but must publish a new authority from
        # its own held replay/oracle surface.
        if (mode is RunnerMode.E2 and
                selection["capacity_authority_sha256"] != declared_authority):
            raise NeuralSufficiencyRefusal(
                "E2 capacity authority differs from the frozen selection")
        try:
            validate_capacity_document(
                authority_document,
                require_goal=(mode is RunnerMode.E2 or held_status == "PASS"))
        except Exception as exc:
            raise NeuralSufficiencyRefusal("held capacity document differs") from exc
        economics_sha256 = _sha(_canonical(economics))
    if mode is RunnerMode.E3:
        _require(details, ("report_only", "no_selection_mutation"), name)
    base = StageReceipt("entry-v2-neural-sufficiency-stage-v2", mode.value, held_status,
                        MODE_MAX_DAY[mode], acceptance.acceptance_sha256, prior_sha,
                        context.corpus_sha256, context.chronology_sha256,
                        evidence.artifact_sha256, callback_hash, selection,
                        economics_sha256, acceptance.diagnostic_evidence_sha256, "")
    value = asdict(base); value.pop("stage_sha256")
    receipt = StageReceipt(**value, stage_sha256=_sha(_canonical(value)))
    _atomic_immutable_json(target, asdict(receipt))
    return receipt


__all__ = [
    "ACCEPTANCE_COMPONENTS", "ACCEPTANCE_FIT_END", "ARM_COMPONENTS", "AcceptanceReceipt",
    "GateEvidence", "MINIMUM_HOST_GIB", "MODE_MAX_DAY", "NeuralSufficiencyRefusal",
    "PRODUCTION_CALLBACK_NAMES", "RunContext", "RunnerMode", "StageReceipt",
    "load_acceptance_receipt", "run_neural_sufficiency",
    "load_stage_receipt", "WinnerAdoptionReceipt", "adopt_e3_winner",
    "load_winner_adoption",
    "capacity_regime_from_oracle",
]
