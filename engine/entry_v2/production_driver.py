#!/usr/bin/env python3
"""Restartable pre-H2 Entry V2 campaign orchestration.

This module owns sequencing only.  Native substrate/context construction and
model construction are explicit injected production dependencies, which keeps
the driver testable without adding a second implementation of either plane.
"""

from __future__ import annotations

from dataclasses import dataclass
import csv
import gc
import json
import os
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Mapping, Sequence

from . import common as C
from . import source_manifest as SM
from .campaign import (
    CampaignResult, build_oof_campaign, require_neural_sufficiency_adoption,
    verify_campaign_receipt,
)
from .corpus import EntryCorpus
from .fold_store import load_fold, release_fold, save_fold
from .folds import DEVELOPMENT_FOLDS, FoldSpec, build_ladder
from .policy import ModelInputBinding, entry_gate_contract
from .train import (
    ARM_FULL_PREFIX, ARM_NAMES, ARM_PER_ASSET_STATIC, ARM_POOLED_STATIC,
    CandidateOraclePreflightRefusal, EntryLearningSystem, PolicyFactory,
    FOLD_OOF_SCHEMA, THRESHOLD_FUNNEL_SCHEMA, TrainingConfig, fold_result_arms,
    fold_training_identity,
    candidate_oracle_preflight, threshold_candidate_law,
    validate_selected_policy_training_receipt,
    run_fold_oof, run_shuffled_control_oof,
)


RUN_SCHEMA = "entry-v2-pre-h2-run-v2"
FROZEN_SHUFFLE_SEED = 20260816
DEFAULT_RUN_PARENT = C.CACHE_ROOT
INVALID_MARKER = C.CACHE_ROOT / "NON_AUTHORITATIVE.json"
DELETION_MANIFEST = C.PROVENANCE_ROOT / "invalid_cache_deletion_manifest.tsv"
DELETION_RECEIPT = C.PROVENANCE_ROOT / "invalid_cache_deletion.receipt.json"


@dataclass(frozen=True)
class CorpusStage:
    corpus: EntryCorpus
    history: Mapping[str, Any]


@dataclass(frozen=True)
class DriverRuntime:
    cpp_wave: Callable[[str, Path, Path, int, int], Mapping[str, Any]]
    context_corpus: Callable[[Path], CorpusStage]
    system_factory: Callable[[], EntryLearningSystem]
    config: TrainingConfig = TrainingConfig()
    policy_factory: PolicyFactory | None = None
    # Mandatory for selected-winner E4--E8.  The control name lets the target
    # provider construct the exact recipient-fixed shuffled atlas twin rather
    # than accidentally training the null on real selected-objective targets.
    winner_system_factory: Callable[[Any, FoldSpec, str, int | None], EntryLearningSystem] | None = None
    winner_policy_kind: str | None = None


@dataclass(frozen=True)
class DriverPlan:
    run_root: Path
    source_manifest: Path = SM.MANIFEST_PATH
    input_list_root: Path = SM.INPUT_LIST_ROOT
    shuffle_seed: int = FROZEN_SHUFFLE_SEED
    prebuilt_substrate_root: Path | None = None
    neural_acceptance_receipt: Path | None = None
    neural_e1_receipt: Path | None = None
    neural_e2_receipt: Path | None = None
    neural_e3_receipt: Path | None = None
    neural_winner_adoption_receipt: Path | None = None
    neural_winner_bundle: Path | None = None
    neural_winner_integration_receipt: Path | None = None
    adopted_primary_e3_fold: Path | None = None

    def payload(self) -> dict[str, Any]:
        return {
            "schema": RUN_SCHEMA,
            "run_root": str(self.run_root.resolve()),
            "source_manifest": str(self.source_manifest.resolve()),
            "input_list_root": str(self.input_list_root.resolve()),
            "start_d8": 20210101,
            "end_d8_exclusive": C.HOLDOUT_START_D8,
            "folds": list(DEVELOPMENT_FOLDS),
            "shuffle_seed": int(self.shuffle_seed),
            "prebuilt_substrate_root": (
                str(Path(self.prebuilt_substrate_root).resolve())
                if self.prebuilt_substrate_root is not None else None
            ),
            "campaign_arms": [
                "pooled_static_gbt", "per_asset_static_gbt", "full_prefix_model"
            ],
            "arrival_stage": False,
            "h2_permit": False,
            "neural_acceptance_receipt": (
                str(self.neural_acceptance_receipt.resolve())
                if self.neural_acceptance_receipt is not None else None
            ),
            "neural_stage_receipts": [
                str(path.resolve()) if path is not None else None for path in
                (self.neural_e1_receipt, self.neural_e2_receipt,
                 self.neural_e3_receipt, self.neural_winner_adoption_receipt)
            ],
            "neural_winner_bundle": (
                str(self.neural_winner_bundle.resolve())
                if self.neural_winner_bundle is not None else None
            ),
            "neural_winner_integration_receipt": (
                str(self.neural_winner_integration_receipt.resolve())
                if self.neural_winner_integration_receipt is not None else None
            ),
            "adopted_primary_e3_fold": (
                str(self.adopted_primary_e3_fold.resolve())
                if self.adopted_primary_e3_fold is not None else None
            ),
        }


@dataclass(frozen=True)
class DriverResult:
    campaign: CampaignResult
    corpus: EntryCorpus
    folds: tuple[FoldSpec, ...]
    primary_paths: tuple[Path, ...]
    shuffled_paths: tuple[Path, ...]
    history: Mapping[str, Any]
    oracle_preflight: Mapping[str, Any]
    audit_report: Mapping[str, Any]


def _write_once(path: Path, value: Mapping[str, Any]) -> None:
    raw = C.canonical_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(path, "xb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError:
        if path.read_bytes() != raw:
            raise C.EntryV2Refusal(f"immutable stage receipt differs: {path}")


def _guard_run_root(plan: DriverPlan) -> Path:
    root = C.assert_workspace_output(plan.run_root)
    C.guard_payload(root)
    default = DEFAULT_RUN_PARENT.resolve()
    try:
        root.relative_to(default)
        under_default = True
    except ValueError:
        under_default = root == default
    if under_default and (INVALID_MARKER.exists() or DELETION_MANIFEST.exists()):
        raise C.EntryV2Refusal(
            "default Entry V2 root is quarantined by NON_AUTHORITATIVE/exact "
            "deletion inventory; use a new immutable run root"
        )
    root.mkdir(parents=True, exist_ok=True)
    _write_once(root / "run.json", plan.payload())
    return root


def _authorize_prebuilt_substrate(plan: DriverPlan) -> tuple[Path, Mapping[str, Any]]:
    """Adopt only the exact post-deletion rebuilt root, never the deleted bytes."""

    if plan.prebuilt_substrate_root is None:
        raise C.EntryV2Refusal("prebuilt substrate root was not declared")
    declared_root = Path(plan.prebuilt_substrate_root)
    if declared_root.is_symlink():
        raise C.EntryV2Refusal("prebuilt substrate root cannot be a symlink")
    root = declared_root.resolve()
    expected_root = C.CACHE_ROOT.resolve()
    if root != expected_root or not root.is_dir():
        raise C.EntryV2Refusal(
            "prebuilt substrate must be the exact rebuilt Entry V2 cache root"
        )
    if INVALID_MARKER.exists():
        raise C.EntryV2Refusal("prebuilt substrate still carries NON_AUTHORITATIVE")
    if not DELETION_MANIFEST.is_file() or not DELETION_RECEIPT.is_file():
        raise C.EntryV2Refusal("prebuilt substrate lacks the frozen deletion transition")
    try:
        deletion = json.loads(DELETION_RECEIPT.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise C.EntryV2Refusal("invalid executed deletion receipt") from exc
    manifest_sha = C.file_sha256(DELETION_MANIFEST)
    if (
        deletion.get("schema") != "entry-v2-invalid-cache-deletion-receipt-v1"
        or deletion.get("status") != "EXECUTED"
        or Path(str(deletion.get("deleted_root", ""))).resolve() != root
        or deletion.get("deletion_manifest_sha256") != manifest_sha
        or deletion.get("exact_inventory_matched_before_delete") is not True
        or deletion.get("target_absent_after_delete") is not True
    ):
        raise C.EntryV2Refusal(
            "prebuilt substrate deletion receipt does not authorize this rebuild"
        )
    header: dict[str, str] = {}
    try:
        for line in DELETION_MANIFEST.read_text().splitlines():
            if line.startswith("entry_type\t"):
                break
            key, value = line.split("\t", 1)
            header[key] = value
        counts_match = (
            int(header["expected_directory_count"])
                == int(deletion["deleted_directory_count"])
            and int(header["expected_file_count"])
                == int(deletion["deleted_file_count"])
            and int(header["expected_total_file_bytes"])
                == int(deletion["deleted_total_file_bytes"])
        )
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise C.EntryV2Refusal("invalid frozen deletion manifest header") from exc
    if (
        header.get("schema") != "entry-v2-invalid-cache-deletion-manifest-v1"
        or header.get("action") != "DELETE_EXACT_TREE"
        or Path(header.get("delete_root", "")).resolve() != root
        or not counts_match
    ):
        raise C.EntryV2Refusal(
            "executed deletion receipt differs from the frozen deletion manifest"
        )
    adoption = {
        "schema": "entry-v2-prebuilt-substrate-adoption-v1",
        "substrate_root": str(root),
        "deletion_manifest_sha256": manifest_sha,
        "deletion_receipt_sha256": C.file_sha256(DELETION_RECEIPT),
        "deleted_file_count": int(deletion["deleted_file_count"]),
        "deleted_total_file_bytes": int(deletion["deleted_total_file_bytes"]),
        "non_authoritative_marker_absent": True,
    }
    return root, MappingProxyType(adoption)


def _cpp_stage(plan: DriverPlan, runtime: DriverRuntime, root: Path) -> Path:
    receipt_path = root / "stages" / "cpp_waves.json"
    if plan.prebuilt_substrate_root is not None:
        substrate, adoption = _authorize_prebuilt_substrate(plan)
        value = {
            "schema": "entry-v2-cpp-waves-v1",
            "passed": True,
            "mode": "ADOPT_EXECUTED_REBUILD",
            "prebuilt_substrate": dict(adoption),
            "waves": [],
        }
        _write_once(receipt_path, value)
        return substrate
    if receipt_path.exists():
        value = json.loads(receipt_path.read_text())
        if value.get("schema") != "entry-v2-cpp-waves-v1" or not value.get("passed"):
            raise C.EntryV2Refusal("persisted C++ wave receipt is not passing")
        return root / "substrate"
    rows = []
    output = root / "substrate"
    for asset in C.ASSETS:
        result = dict(runtime.cpp_wave(
            asset, plan.input_list_root / f"{asset}.tsv", output,
            20210101, C.HOLDOUT_START_D8,
        ))
        if result.get("passed") is not True:
            raise C.EntryV2Refusal(f"{asset}: C++ wave did not pass")
        if int(result.get("end_d8_exclusive", 0)) != C.HOLDOUT_START_D8:
            raise C.EntryV2Refusal(f"{asset}: C++ wave boundary differs")
        rows.append({"asset": asset, **result})
    _write_once(receipt_path, {
        "schema": "entry-v2-cpp-waves-v1", "passed": True, "waves": rows,
    })
    return output


def _folds(corpus: EntryCorpus) -> tuple[FoldSpec, ...]:
    sessions = tuple(corpus.replay.expected_sessions)
    days = {session.trading_day for session in sessions}
    if any(
        not C.is_denominator_day(session.asset, session.trading_day)
        for session in sessions
    ):
        raise C.EntryV2Refusal("corpus denominator is not trading-day clean")
    result = build_ladder(days)
    if tuple(fold.test_era for fold in result) != DEVELOPMENT_FOLDS:
        raise C.EntryV2Refusal("driver ladder differs from E3-E8")
    return result


def _persist_folds(
    root: Path, runtime: DriverRuntime, corpus: EntryCorpus,
    folds: Sequence[FoldSpec], shuffle_seed: int, *, winner_bundle: Any | None = None,
    adopted_primary_e3_fold: Path | None = None,
) -> tuple[tuple[Path, ...], tuple[Path, ...]]:
    primary_paths: list[Path] = []
    shuffled_paths: list[Path] = []
    for fold in folds:
        primary = root / "folds" / fold.test_era / "primary"
        shuffled = root / "folds" / fold.test_era / "shuffled"
        if winner_bundle is not None and runtime.winner_system_factory is None:
            raise C.EntryV2Refusal(
                "selected winner has no exact fold training/target-provider factory"
            )
        if winner_bundle is not None and runtime.winner_policy_kind != str(
                winner_bundle.architecture["decision_head_kind"]):
            raise C.EntryV2Refusal(
                "selected winner decision head has no matching production policy adapter"
            )
        if winner_bundle is not None and runtime.policy_factory is None:
            raise C.EntryV2Refusal(
                "selected winner has no exact direct/CatBoost policy adapter"
            )
        if winner_bundle is not None:
            expected_policy_name = (
                "entry_v2_selected_direct_policy_factory"
                if runtime.winner_policy_kind == "direct_neural"
                else "entry_v2_selected_catboost_policy_factory"
            )
            if (getattr(runtime.winner_system_factory, "__name__", "")
                    != "entry_v2_selected_winner_system_factory"
                    or getattr(runtime.policy_factory, "__name__", "")
                    != expected_policy_name):
                raise C.EntryV2Refusal(
                    "selected winner factories are not named production adapters"
                )
        if winner_bundle is not None and fold.test_era == "E3":
            if adopted_primary_e3_fold is None:
                raise C.EntryV2Refusal(
                    "selected winner lacks the held standard primary E3 fold"
                )
            adopted = Path(adopted_primary_e3_fold).resolve()
            if not adopted.is_dir() or adopted == primary.resolve():
                raise C.EntryV2Refusal("held primary E3 fold path is absent/invalid")
            probe = load_fold(adopted)
            try:
                _validate_fold_adoption(probe, corpus, shuffled=False,
                                        winner_bundle=winner_bundle,
                                        fold_store_sha256=
                                            probe.store_aggregate_sha256)
                if probe.fold != "E3":
                    raise C.EntryV2Refusal("held primary fold is not E3")
                _persist_policy_gate_diagnostic(root, probe)
            finally:
                release_fold(probe)
                del probe
            primary = adopted
        elif not primary.exists():
            primary_system = (runtime.system_factory() if winner_bundle is None else
                runtime.winner_system_factory(winner_bundle, fold, "PROPHET", None))
            result = run_fold_oof(
                primary_system, corpus.sessions, corpus.teacher, fold,
                corpus.replay, corpus.model_input_binding, runtime.config,
                runtime.policy_factory,
            )
            try:
                _validate_fold_adoption(result, corpus, shuffled=False,
                                        winner_bundle=winner_bundle)
                save_fold(primary, result)
                _persist_policy_gate_diagnostic(root, result)
            finally:
                release_fold(result)
                del result
        else:
            probe = load_fold(primary)
            try:
                _validate_fold_adoption(probe, corpus, shuffled=False,
                                        winner_bundle=winner_bundle)
                _persist_policy_gate_diagnostic(root, probe)
            finally:
                release_fold(probe)
                del probe
        if not shuffled.exists():
            shuffled_system = (runtime.system_factory() if winner_bundle is None else
                runtime.winner_system_factory(
                    winner_bundle, fold, f"SHUFFLED_{int(shuffle_seed)}", int(shuffle_seed)
                ))
            result = run_shuffled_control_oof(
                shuffled_system, corpus.sessions, corpus.teacher, fold,
                corpus.replay, int(shuffle_seed), corpus.model_input_binding,
                runtime.config, runtime.policy_factory,
            )
            try:
                _validate_fold_adoption(result, corpus, shuffled=True,
                                        winner_bundle=winner_bundle)
                save_fold(shuffled, result)
            finally:
                release_fold(result)
                del result
        else:
            probe = load_fold(shuffled)
            try:
                _validate_fold_adoption(probe, corpus, shuffled=True,
                                        winner_bundle=winner_bundle)
            finally:
                release_fold(probe)
                del probe
        primary_paths.append(primary)
        shuffled_paths.append(shuffled)
        gc.collect()
    return tuple(primary_paths), tuple(shuffled_paths)


def _validate_fold_adoption(
    result: Any, corpus: EntryCorpus, *, shuffled: bool,
    winner_bundle: Any | None = None,
    fold_store_sha256: str | None = None,
) -> None:
    """Reject stale persisted semantics before primary use or null execution."""

    receipt = result.receipt
    if receipt.get("schema") != FOLD_OOF_SCHEMA:
        raise C.EntryV2Refusal(f"{result.fold}: stale fold schema refuses adoption")
    if receipt.get("entry_gate_contract") != entry_gate_contract():
        raise C.EntryV2Refusal(f"{result.fold}: decision gate contract differs")
    if receipt.get("threshold_candidate_law") != threshold_candidate_law():
        raise C.EntryV2Refusal(f"{result.fold}: threshold-candidate law differs")
    if receipt.get("threshold_funnel_schema") != THRESHOLD_FUNNEL_SCHEMA:
        raise C.EntryV2Refusal(f"{result.fold}: threshold funnel schema differs")
    winner = receipt.get("winner_adoption")
    held_e3 = winner_bundle is not None and result.fold == "E3"
    try:
        binding = ModelInputBinding.from_mapping(receipt["model_input_binding"])
        loaded_binding = fold_training_identity(result).model_input_binding
    except (KeyError, AttributeError, TypeError) as exc:
        raise C.EntryV2Refusal(
            f"{result.fold}: loaded fold model input binding is missing"
        ) from exc
    exact_current = binding == corpus.model_input_binding
    exact_e3_prefix = False
    if held_e3 and binding.input_contract_sha256 \
            == corpus.model_input_binding.input_contract_sha256:
        try:
            parts = corpus.receipt["corpus_window"]["window_chain"]["parts"]
            exact_e3_prefix = (
                len(parts) == 2
                and int(parts[0]["maximum_d8"]) == 20221230
                and parts[0]["receipt_sha256"]
                    == binding.corpus_receipt_sha256
            )
        except (KeyError, TypeError, ValueError):
            exact_e3_prefix = False
    if (binding != loaded_binding
            or not (exact_current or exact_e3_prefix)):
        raise C.EntryV2Refusal(
            f"{result.fold}: loaded fold model input binding differs from corpus"
        )
    if winner_bundle is not None:
        expected_selection = C.object_sha256(dict(winner_bundle.selection))
        if (not isinstance(winner, Mapping)
                or winner.get("legacy_full_prefix") is not False
                or fold_result_arms(result) != (ARM_FULL_PREFIX,)
                or winner.get("arm") != winner_bundle.arm
                or winner.get("objective_sha256")
                    != winner_bundle.selection["selected_objective_sha256"]
                or winner.get("decision_head_kind")
                    != winner_bundle.architecture["decision_head_kind"]
                or not isinstance(winner.get("target_row_manifest_sha256"), str)
                or not isinstance(winner.get("target_control_sha256"), str)
                or len(winner["target_control_sha256"]) != 64):
            raise C.EntryV2Refusal(
                f"{result.fold}: fold did not train the selected winner bundle"
            )
        if winner_bundle.arm != "C0":
            target_receipt = winner.get("target_control_receipt")
            if (not isinstance(target_receipt, Mapping)
                    or target_receipt.get("target_control_sha256")
                        != winner["target_control_sha256"]
                    or not all(isinstance(winner.get(key), str)
                               and len(winner[key]) == 64 for key in (
                                   "fit_day_manifest_sha256",
                                   "target_candidate_manifest_sha256",
                                   "fit_context_sha256"))):
                raise C.EntryV2Refusal(
                    f"{result.fold}: selected fold-causal target receipt differs"
                )
        if held_e3:
            if (fold_store_sha256 != winner_bundle.primary_e3_fold_sha256
                    or winner.get("bundle_sha256") is not None
                    or winner.get("e2_frozen_selection_sha256")
                        != expected_selection):
                raise C.EntryV2Refusal(
                    "E3: held fold/adoption identity is cyclic or differs"
                )
        elif winner.get("bundle_sha256") != winner_bundle.bundle_sha256:
            raise C.EntryV2Refusal(
                f"{result.fold}: fold bundle identity differs"
            )
        dispatch = receipt.get("policy_factory_dispatch")
        expected_selected_factory = (
            "entry_v2_selected_direct_policy_factory"
            if winner_bundle.architecture["decision_head_kind"] == "direct_neural"
            else "entry_v2_selected_catboost_policy_factory"
        )
        if (not isinstance(dispatch, Mapping)
                or tuple(dispatch) != (ARM_FULL_PREFIX,)
                or dispatch.get(ARM_FULL_PREFIX) != expected_selected_factory):
            raise C.EntryV2Refusal(
                f"{result.fold}: selected-only policy dispatch differs"
            )
        policy_training = receipt.get("selected_policy_training")
        if not isinstance(policy_training, Mapping):
            raise C.EntryV2Refusal(
                f"{result.fold}: selected policy training evidence is missing"
            )
        try:
            validate_selected_policy_training_receipt(
                policy_training,
                decision_head_kind=str(winner_bundle.architecture[
                    "decision_head_kind"
                ]),
                fit_days=tuple(int(day) for day in policy_training["fit_days"]),
                calibration_days=tuple(
                    int(day) for day in policy_training["calibration_days"]
                ),
                selection_days=tuple(
                    int(day) for day in policy_training["selection_days"]
                ),
            )
            chronology = receipt["prequential"]
            chronology_valid = bool(
                max(policy_training["fit_days"]) == int(receipt["fit_max_d8"])
                and list(policy_training["calibration_days"])
                    == list(chronology["calibration_days"])
                and list(policy_training["selection_days"])
                    == list(chronology["threshold_selection_days"])
                and chronology.get("selected_policy_chronology_law")
                    == "entry-v2-selected-train-only-policy-v1"
                and chronology.get(
                    "selected_policy_fit_excludes_all_inner_labels"
                ) is True
            )
        except (KeyError, TypeError, ValueError):
            chronology_valid = False
        if not chronology_valid:
            raise C.EntryV2Refusal(
                f"{result.fold}: selected policy chronology differs"
            )
    null = receipt.get("null_control")
    if shuffled:
        try:
            control = str(result.control_name)
            null_valid = bool(
                isinstance(null, Mapping)
                and control.startswith("SHUFFLED_")
                and null.get("schema") == "entry-v2-stage-asset-day-shuffle-v2"
                and int(null["seed"]) == int(control.removeprefix("SHUFFLED_"))
                and int(null["selected_labels"]) > 0
                and int(null["within_asset_day_rows"]) >= 0
                and int(null["stage_asset_fallback_rows"]) >= 0
                and null.get("preserved_marginals") == (
                    "stage,asset,action_loss_mask; asset/day/mask where size>=2"
                )
                and null.get("action_loss_mask") == "RECIPIENT_FIXED"
            )
        except (KeyError, TypeError, ValueError):
            null_valid = False
        if not null_valid:
            raise C.EntryV2Refusal(f"{result.fold}: shuffled null-v2 law differs")
    elif null != {"schema": "entry-v2-positive-control-v1", "control": "PROPHET"}:
        raise C.EntryV2Refusal(f"{result.fold}: positive-control law differs")


def _persist_policy_gate_diagnostic(
    root: Path, result: Any,
) -> Mapping[str, Any]:
    """Persist and enforce the primary-fold gate before any null is run."""

    receipt = dict(result.receipt)
    contract = receipt.get("entry_gate_contract")
    if contract != entry_gate_contract():
        raise C.EntryV2Refusal(
            f"{result.fold}: stale/wrong entry gate fold refuses adoption"
        )
    if receipt.get("threshold_candidate_law") != threshold_candidate_law():
        raise C.EntryV2Refusal(f"{result.fold}: threshold-candidate law differs")
    if receipt.get("threshold_funnel_schema") != THRESHOLD_FUNNEL_SCHEMA:
        raise C.EntryV2Refusal(f"{result.fold}: threshold funnel schema differs")
    learned = receipt.get("arm_thresholds")
    truth = receipt.get("truth_inner_thresholds_usd")
    if not isinstance(learned, Mapping) or not isinstance(truth, Mapping):
        raise C.EntryV2Refusal(
            f"{result.fold}: policy threshold receipts are missing"
        )

    assets: dict[str, Any] = {}
    first_failed: str | None = None

    def compact_funnel(rows: Any) -> Mapping[str, Any]:
        if not isinstance(rows, (list, tuple)) or not rows:
            raise ValueError("threshold funnel is empty")
        reasons: dict[str, int] = {}
        for row in rows:
            reason = str(row["reason"])
            reasons[reason] = reasons.get(reason, 0) + 1
        return {
            "threshold_candidates": len(rows),
            "candidate_count": int(rows[0]["candidate_count"]),
            "action_pass_min": min(int(row["action_pass"]) for row in rows),
            "action_pass_max": max(int(row["action_pass"]) for row in rows),
            "replay_trades_max": max(int(row["replay_trades"]) for row in rows),
            "feasible_thresholds": sum(bool(row["feasible"]) for row in rows),
            "reason_counts": reasons,
        }

    arms = fold_result_arms(result)
    for asset in C.ASSETS:
        try:
            truth_feasible = int(truth[asset]["feasible_thresholds"])
            arm_feasible = {
                arm: int(learned[arm][asset]["feasible_thresholds"])
                for arm in arms
            }
            arm_selected = {
                arm: {
                    "threshold": float(learned[arm][asset]["threshold"]),
                    "feasible_thresholds": arm_feasible[arm],
                    "trades": int(learned[arm][asset]["trades"]),
                    "usd_per_trade": float(
                        learned[arm][asset]["usd_per_trade"]
                    ),
                    "usd_per_asset_day": float(
                        learned[arm][asset]["usd_per_asset_day"]
                    ),
                    "chronological_mdd_usd": float(
                        learned[arm][asset]["max_drawdown_usd"]
                    ),
                    "threshold_funnel": compact_funnel(
                        learned[arm][asset]["funnel"]
                    ),
                }
                for arm in arms
            }
        except (KeyError, TypeError, ValueError) as exc:
            raise C.EntryV2Refusal(
                f"{result.fold}/{asset}: invalid policy threshold receipt"
            ) from exc
        learned_pass = any(value > 0 for value in arm_feasible.values())
        truth_pass = truth_feasible > 0
        assets[asset] = {
            "truth_control_feasible_thresholds": truth_feasible,
            "truth_control_passed": truth_pass,
            "truth_threshold_funnel": compact_funnel(truth[asset]["funnel"]),
            "learned_arms": arm_selected,
            "at_least_one_learned_arm_passed": learned_pass,
            "passed": truth_pass and learned_pass,
        }
        if first_failed is None and not truth_pass:
            first_failed = f"TRUTH_NO_FEASIBLE_THRESHOLD:{asset}"
        elif first_failed is None and not learned_pass:
            first_failed = f"POLICY_NO_FEASIBLE_THRESHOLD:{asset}"

    declared_boundary = receipt.get("decision_contract", {}).get(
        "first_failed_boundary"
    )
    learned_boundary = next(
        (
            f"POLICY_NO_FEASIBLE_THRESHOLD:{asset}"
            for asset in C.ASSETS
            if not assets[asset]["at_least_one_learned_arm_passed"]
        ),
        None,
    )
    if declared_boundary != learned_boundary:
        raise C.EntryV2Refusal(
            f"{result.fold}: first failed policy boundary receipt differs"
        )
    payload: dict[str, Any] = {
        "schema": "entry-v2-primary-policy-gate-diagnostic-v1",
        "fold": str(result.fold),
        "entry_gate_contract_schema": contract["schema"],
        "requirements": {
            "truth_control_feasible_each_asset": True,
            "at_least_one_learned_arm_feasible_each_asset": True,
        },
        "assets": assets,
        "passed": first_failed is None,
        "first_failed_boundary": first_failed,
    }
    payload["sha256"] = C.object_sha256(payload)
    path = root / "stages" / "policy_gate" / f"{result.fold}.json"
    _write_once(path, payload)
    if not payload["passed"]:
        raise C.EntryV2Refusal(
            f"{first_failed}; primary policy diagnostic persisted at {path}"
        )
    return MappingProxyType(payload)


def _persist_oracle_preflight(
    root: Path, corpus: EntryCorpus, folds: Sequence[FoldSpec]
) -> Mapping[str, Any]:
    """Publish exact candidate headroom before any system/optimizer is created."""

    rows: list[dict[str, Any]] = []
    first_failed: str | None = None
    for fold in folds:
        try:
            evidence = candidate_oracle_preflight(
                corpus.sessions, corpus.teacher, corpus.replay, fold.test_days
            )
        except CandidateOraclePreflightRefusal as exc:
            evidence = exc.evidence
            first_failed = fold.test_era
        rows.append({"fold": fold.test_era, "evidence": dict(evidence)})
        if first_failed is not None:
            break
    payload: dict[str, Any] = {
        "schema": "entry-v2-candidate-oracle-ladder-preflight-v4",
        "passed": first_failed is None and len(rows) == len(folds),
        "acceptance_law": (
            "oracle_usd_per_asset_day >= LOW_CAPACITY_ASSET_DAY_FLOOR_USD"
        ),
        "acceptance_floor_usd_per_asset_day":
            C.LOW_CAPACITY_ASSET_DAY_FLOOR_USD,
        "normal_floor_usd_per_asset_day": C.WEAK_ASSET_DAY_FLOOR_USD,
        "risk_exception_contract": (
            "learned era usd_per_asset_day >= LOW_CAPACITY_ASSET_DAY_FLOOR_USD "
            "and chronological max_drawdown_usd < LOW_CAPACITY_MAX_DRAWDOWN_USD"
        ),
        "risk_exception_max_drawdown_usd": C.LOW_CAPACITY_MAX_DRAWDOWN_USD,
        "optimization_goal_usd_per_asset_day": C.TARGET_ASSET_DAY_USD,
        "optimization_target": "full_total_pnl_usd",
        "values_clipped_to_acceptance_floor": False,
        "expected_folds": list(DEVELOPMENT_FOLDS),
        "folds": rows,
        "first_failed_fold": first_failed,
    }
    payload["receipt_sha256"] = C.object_sha256(payload)
    path = root / "stages" / "candidate_oracle_preflight.json"
    _write_once(path, payload)
    if not payload["passed"]:
        raise C.EntryV2Refusal(
            "candidate/oracle ladder preflight failed before optimizer creation; "
            f"evidence persisted at {path}"
        )
    return MappingProxyType(payload)


def run_pre_h2_campaign(plan: DriverPlan, runtime: DriverRuntime) -> DriverResult:
    """Run/resume exactly substrate -> corpus -> E3..E8 -> common campaign."""
    if int(plan.shuffle_seed) != FROZEN_SHUFFLE_SEED:
        raise C.EntryV2Refusal(
            f"production shuffle seed is frozen at {FROZEN_SHUFFLE_SEED}"
        )
    if any(path is None for path in (
            plan.neural_acceptance_receipt, plan.neural_e1_receipt,
            plan.neural_e2_receipt, plan.neural_e3_receipt,
            plan.neural_winner_adoption_receipt, plan.neural_winner_bundle,
            plan.neural_winner_integration_receipt,
            plan.adopted_primary_e3_fold)):
        raise C.EntryV2Refusal(
            "legacy E3-E8 campaign is blocked until fit-only neural acceptance"
        )
    neural_adoption = require_neural_sufficiency_adoption(
        plan.neural_acceptance_receipt, plan.neural_e1_receipt,
        plan.neural_e2_receipt, plan.neural_e3_receipt,
        plan.neural_winner_adoption_receipt,
        plan.neural_winner_bundle,
        plan.neural_winner_integration_receipt,
    )
    root = _guard_run_root(plan)
    SM.load(plan.source_manifest, require_ready=True)
    substrate_root = _cpp_stage(plan, runtime, root)
    stage = runtime.context_corpus(substrate_root)
    corpus = stage.corpus
    if corpus.receipt.get("final_exam_permit") is not False:
        raise C.EntryV2Refusal("driver corpus is not ordinary development data")
    _write_once(root / "stages" / "corpus.json", dict(corpus.receipt))
    from .neural_winner_artifact import load_winner_bundle
    winner_bundle = load_winner_bundle(
        plan.neural_winner_bundle,
        expected_adoption_sha256=neural_adoption["winner_adoption_sha256"],
        expected_binding=corpus.model_input_binding,
    )
    if winner_bundle.bundle_sha256 != neural_adoption["winner_bundle_sha256"]:
        raise C.EntryV2Refusal("winner bundle differs after corpus binding")
    folds = _folds(corpus)
    oracle_preflight = _persist_oracle_preflight(root, corpus, folds)
    primary_paths, shuffled_paths = _persist_folds(
        root, runtime, corpus, folds, plan.shuffle_seed, winner_bundle=winner_bundle,
        adopted_primary_e3_fold=plan.adopted_primary_e3_fold,
    )

    # Training systems have been dropped.  Load only CPU OOF summaries for the
    # adopted-winner union (legacy stores may still contain three arms), then
    # release them after campaign creation.
    primary = tuple(load_fold(path) for path in primary_paths)
    shuffled = tuple(load_fold(path) for path in shuffled_paths)
    preflight_by_fold = {
        row["fold"]: row["evidence"] for row in oracle_preflight["folds"]
    }
    for result in (*primary, *shuffled):
        if dict(result.receipt.get("candidate_oracle_preflight", {})) != dict(
            preflight_by_fold.get(result.fold, {})
        ):
            raise C.EntryV2Refusal(
                f"{result.fold}: fold preflight differs from persisted pre-optimizer evidence"
            )
    campaign = build_oof_campaign(
        primary,
        raw_prefix_fidelity=corpus.raw_prefix_fidelity,
        teacher_alignment=corpus.teacher_alignment,
        shuffled_folds=shuffled,
    )
    if not verify_campaign_receipt(campaign.receipt):
        raise C.EntryV2Refusal("driver built an invalid campaign receipt")
    campaign_path = root / "stages" / "campaign.json"
    corpus_path = root / "stages" / "corpus.json"
    _write_once(campaign_path, dict(campaign.receipt))
    from .audit import (
        ProductionAuditInputs, build_production_manifest,
        production_audit_hooks, run_audit, write_report,
    )
    history = dict(stage.history)
    history["neural_sufficiency_acceptance"] = dict(neural_adoption)
    audit_manifest = build_production_manifest(
        plan.source_manifest, corpus_path, campaign_path, folds, history,
    )
    _write_once(root / "stages" / "audit_manifest.json", audit_manifest)
    audit_report = run_audit(
        manifest=audit_manifest,
        hooks=production_audit_hooks(ProductionAuditInputs(
            corpus, campaign, primary, shuffled, folds, plan.shuffle_seed
        )),
    )
    acceptance_path = root / "stages" / "acceptance.json"
    if acceptance_path.exists():
        existing = json.loads(acceptance_path.read_text())
        if existing.get("receipt_sha256") != audit_report.get("receipt_sha256"):
            raise C.EntryV2Refusal("immutable acceptance receipt differs on restart")
        audit_report = existing
    else:
        write_report(audit_report, acceptance_path)
    if not audit_report["payload"]["passed"]:
        raise C.EntryV2Refusal("consolidated production audit did not pass")
    for value in (*primary, *shuffled):
        release_fold(value)
    return DriverResult(
        campaign, corpus, folds, primary_paths, shuffled_paths,
        MappingProxyType(history), oracle_preflight,
        MappingProxyType(dict(audit_report)),
    )


def prepare_invalid_cache_deletion(
    acceptance_receipt: Path,
    *,
    deletion_manifest: Path = DELETION_MANIFEST,
) -> Mapping[str, Any]:
    """Validate the frozen exact transition; never delete any path here."""
    acceptance = json.loads(acceptance_receipt.read_text())
    if not (acceptance.get("passed") is True
            or acceptance.get("payload", {}).get("passed") is True):
        raise C.EntryV2Refusal("cache deletion requires a passing production acceptance")
    raw = deletion_manifest.read_bytes()
    lines = raw.decode().splitlines()
    header: dict[str, str] = {}
    index = 0
    while index < len(lines) and not lines[index].startswith("entry_type\t"):
        key, value = lines[index].split("\t", 1)
        header[key] = value
        index += 1
    if (header.get("schema") != "entry-v2-invalid-cache-deletion-manifest-v1"
            or header.get("status") != "NOT_EXECUTED_APPROVAL_REQUIRED"
            or Path(header.get("delete_root", "")) != C.CACHE_ROOT):
        raise C.EntryV2Refusal("frozen deletion manifest identity differs")
    reader = csv.DictReader(lines[index:], delimiter="\t")
    rows = list(reader)
    files = [row for row in rows if row["entry_type"] == "F"]
    directories = [row for row in rows if row["entry_type"] == "D"]
    if (len(files), len(directories), sum(int(row["size_bytes"]) for row in files)) != (
        int(header["expected_file_count"]), int(header["expected_directory_count"]),
        int(header["expected_total_file_bytes"]),
    ):
        raise C.EntryV2Refusal("frozen deletion inventory counts differ")
    root = C.CACHE_ROOT.resolve()
    for row in rows:
        path = Path(row["absolute_path"])
        try:
            path.resolve(strict=False).relative_to(root)
        except ValueError as exc:
            raise C.EntryV2Refusal("deletion inventory escapes quarantined root") from exc
    return {
        "schema": "entry-v2-invalid-cache-deletion-transition-v1",
        "status": "VERIFIED_NOT_EXECUTED",
        "delete_root": str(root),
        "deletion_manifest_sha256": C.file_sha256(deletion_manifest),
        "expected_file_count": len(files),
        "expected_total_file_bytes": sum(int(row["size_bytes"]) for row in files),
    }


__all__ = [
    "CorpusStage", "DriverPlan", "DriverResult", "DriverRuntime",
    "FROZEN_SHUFFLE_SEED",
    "_authorize_prebuilt_substrate",
    "prepare_invalid_cache_deletion", "run_pre_h2_campaign",
]
