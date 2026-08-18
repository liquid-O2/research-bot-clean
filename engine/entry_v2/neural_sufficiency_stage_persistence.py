"""Atomic, fail-closed persistence for measured E1 -> E2 -> E3 boundaries.

The store never fits or selects.  It snapshots the public held-stage object and
the exact numerical bytes exported by the live resource owner, then restores a
new :class:`ExactHeldStageEngine` after a process crash.  E3 delegates its
large numerical fold to the existing exact fold store.
"""
from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
from types import MappingProxyType
from typing import Any, Callable, Mapping, Sequence

import numpy as np

from . import common as C
from .capacity_contract import validate_capacity_document
from .atlas_statistics import PairedObservationRecord, SupportKind, SupportState
from .causal_label_atlas import PROBE_REGISTRY, shuffled_probe_for
from .capacity_contract import FIT_ONLY_MIN_ORACLE_CAPTURE
from .fold_store import load_fold, save_fold
from .neural_sufficiency_production import ExactComponentExecution
from .neural_sufficiency_stage_engine import (
    AssetEconomics, E1ScreenResult, ExactHeldStageEngine,
    FrozenWinnerSelection, HeldStageRefusal, HeldWinnerArtifacts,
    MeasuredFinalistConfirmation, MeasuredProbeScreen, ProbeSupportInputs,
)
from .neural_winner_artifact import required_payloads_for_head


SCHEMA = "entry-v2-held-stage-boundary-v2"
MANIFEST = "boundary.json"
EVIDENCE_SCHEMA = "entry-v2-held-stage-evidence-v2"
EVIDENCE_MANIFEST = "evidence.json"
FOLD_DIRECTORY = "primary-e3-fold"
STAGES = ("E1", "E2", "E3")
EVIDENCE_STAGES = ("ACCEPTANCE", *STAGES)
CANONICAL_ARMS = ("C0", "C1", "L0", "L1", "M1")
DECISION_HEADS = ("direct_neural", "catboost")

ACCEPTANCE_NUMERICAL_PAYLOADS = frozenset({
    *(f"acceptance/{arm}.competence.safetensors" for arm in CANONICAL_ARMS),
    *(f"acceptance/evidence/arm-{arm}.json" for arm in CANONICAL_ARMS),
    "acceptance/evidence/raw-fidelity.json",
    "acceptance/arm-authorization.json", "acceptance/manifest.json",
})
M8_EVIDENCE_PAYLOADS = frozenset({
    "M8/rehearsal-evidence.json", "M8/objective-ledger.json",
    "M8/path-evidence.json", "M8/restart-contract.json", "M8/manifest.json",
})

E1_NUMERICAL_PAYLOADS = frozenset({
    "pretext/C01P01.checkpoint.npz", "pretext/C02P01.checkpoint.npz",
    "finalists.json", "fit-contexts.json", "fit-ledger.json", "screens.json",
})
E2_NUMERICAL_PAYLOADS = frozenset({
    "encoder.safetensors", "head.safetensors", "objective-head.safetensors",
    "mapper.json", "calibrator.json", "thresholds.json", "capacity.json",
    "compact-targets.npz", "compact-context.json", "selection.json",
    "selected-horizon-normalizer.json", "validation-roster.json",
    "arm-authorization.json",
})


class StagePersistenceRefusal(RuntimeError):
    pass


class InjectedBoundaryCrash(RuntimeError):
    pass


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          allow_nan=False).encode()
    except (TypeError, ValueError) as exc:
        raise StagePersistenceRefusal("stage boundary is not canonical JSON") from exc


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _is_sha(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(
        char in "0123456789abcdef" for char in value
    )


def _safe_name(value: str) -> bool:
    path = Path(value)
    return (bool(value) and not path.is_absolute() and ".." not in path.parts
            and all(part not in {"", "."} for part in path.parts))


def _validate_numerical_payload(name: str, raw: bytes) -> None:
    if not _safe_name(name) or not isinstance(raw, bytes) or not raw:
        raise StagePersistenceRefusal("numerical payload name/bytes are invalid")
    if name.endswith(".json"):
        try:
            value = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise StagePersistenceRefusal(f"invalid numerical JSON: {name}") from exc
        native_catboost = (Path(name).name.startswith("catboost-")
                           and Path(name).stem.removeprefix("catboost-") in C.ASSETS)
        if (not isinstance(value, dict) or not value
                or (not native_catboost and (
                    not isinstance(value.get("schema"), str) or _canonical(value) != raw
                ))):
            raise StagePersistenceRefusal(
                f"numerical JSON must be canonical and schema-bearing: {name}"
            )
    elif name.endswith(".npz"):
        try:
            with np.load(io.BytesIO(raw), allow_pickle=False) as archive:
                if not archive.files:
                    raise StagePersistenceRefusal(f"empty numerical archive: {name}")
                for key in archive.files:
                    value = archive[key]
                    if value.dtype.hasobject:
                        raise StagePersistenceRefusal(
                            f"object numerical archive is forbidden: {name}"
                        )
        except (OSError, ValueError, EOFError) as exc:
            raise StagePersistenceRefusal(f"invalid numerical archive: {name}") from exc
    elif name.endswith(".safetensors"):
        try:
            from safetensors.torch import load
            state = load(raw)
        except Exception as exc:
            raise StagePersistenceRefusal(f"invalid safetensors payload: {name}") from exc
        if not state:
            raise StagePersistenceRefusal(f"empty safetensors payload: {name}")


def _validate_self_receipt(value: Mapping[str, Any], *, label: str) -> None:
    core = dict(value)
    declared = core.pop("receipt_sha256", None)
    if not _is_sha(declared) or _sha(_canonical(core)) != declared:
        raise StagePersistenceRefusal(f"{label} self receipt differs")


def _validate_acceptance_numerical(payloads: Mapping[str, bytes]) -> None:
    if set(payloads) != set(ACCEPTANCE_NUMERICAL_PAYLOADS):
        raise StagePersistenceRefusal("acceptance numerical payload census differs")
    for name, raw in payloads.items():
        _validate_numerical_payload(name, raw)
    try:
        manifest = json.loads(payloads["acceptance/manifest.json"])
        authorization = json.loads(payloads["acceptance/arm-authorization.json"])
        raw_evidence = json.loads(
            payloads["acceptance/evidence/raw-fidelity.json"])
        arm_evidence = {arm: json.loads(
            payloads[f"acceptance/evidence/arm-{arm}.json"])
            for arm in CANONICAL_ARMS}
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StagePersistenceRefusal("acceptance numerical metadata is invalid") from exc
    hashes = {name: _sha(raw) for name, raw in sorted(payloads.items())
              if name != "acceptance/manifest.json"}
    arm_rows = authorization.get("arms", {}) if isinstance(authorization, dict) else {}
    if (not isinstance(manifest, dict)
            or manifest.get("schema") != "entry-v2-acceptance-numerical-manifest-v1"
            or manifest.get("payload_sha256") != hashes
            or not isinstance(authorization, dict)
            or authorization.get("schema") != "entry-v2-accepted-arm-authorization-v1"
            or authorization.get("canonical_arms") != list(CANONICAL_ARMS)
            or set(arm_rows) != set(CANONICAL_ARMS)
            or any(not isinstance(row, dict)
                   or set(row) != {"checkpoint_sha256", "row_manifest_sha256",
                                   "representation_sha256", "evidence_sha256"}
                   or any(not _is_sha(value) for value in row.values())
                   or row["checkpoint_sha256"] != hashes[
                       f"acceptance/{arm}.competence.safetensors"]
                   or row["evidence_sha256"] != hashes[
                       f"acceptance/evidence/arm-{arm}.json"]
                   for arm, row in arm_rows.items())):
        raise StagePersistenceRefusal("acceptance authorization/manifest differs")
    if (authorization.get("raw_fidelity_evidence_sha256") != hashes[
            "acceptance/evidence/raw-fidelity.json"]
            or raw_evidence.get("schema") != "entry-v2-raw-fidelity-evidence-v1"
            or any(value.get("schema") != "entry-v2-arm-competence-evidence-v1"
                   or value.get("arm") != arm
                   for arm, value in arm_evidence.items())):
        raise StagePersistenceRefusal("acceptance measured evidence differs")
    _validate_self_receipt(manifest, label="acceptance manifest")
    _validate_self_receipt(authorization, label="acceptance authorization")
    _validate_self_receipt(raw_evidence, label="raw-fidelity evidence")
    for arm, value in arm_evidence.items():
        _validate_self_receipt(value, label=f"{arm} competence evidence")


def _validate_m8_evidence(payloads: Mapping[str, bytes]) -> None:
    m8 = {name: raw for name, raw in payloads.items() if name.startswith("M8/")}
    if not set(M8_EVIDENCE_PAYLOADS).issubset(m8):
        raise StagePersistenceRefusal("M8 required evidence payload census differs")
    for name, raw in m8.items():
        _validate_numerical_payload(name, raw)
    try:
        manifest = json.loads(m8["M8/manifest.json"])
        rehearsal = json.loads(m8["M8/rehearsal-evidence.json"])
        objective_ledger = json.loads(m8["M8/objective-ledger.json"])
        path_evidence = json.loads(m8["M8/path-evidence.json"])
        restart_contract = json.loads(m8["M8/restart-contract.json"])
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StagePersistenceRefusal("M8 evidence metadata is invalid") from exc
    real_ids = {probe.probe_id for probe in PROBE_REGISTRY}
    twin_ids = {shuffled_probe_for(probe).probe_id for probe in PROBE_REGISTRY}
    paths = {f"{arm}:{head}" for arm in CANONICAL_ARMS for head in DECISION_HEADS}
    goal_receipts = rehearsal.get("g7", {}).get(
        "goal_recovery_receipts", {}) if isinstance(rehearsal, dict) else {}
    expected_goal_receipts = {
        f"{stage}.{role}.{asset}"
        for stage in ("E1r", "E2r")
        for role in ("THRESHOLD", "FORWARD")
        for asset in ("HG", "NKD", "SI")
    }
    other_hashes = {name: _sha(raw) for name, raw in sorted(m8.items())
                    if name != "M8/manifest.json"}
    roles = manifest.get("payload_roles", {}) if isinstance(manifest, dict) else {}
    arm_payloads = (manifest.get("arm_checkpoint_payloads", {})
                    if isinstance(manifest, dict) else {})
    path_payloads = (manifest.get("path_payloads", {})
                     if isinstance(manifest, dict) else {})
    objective_payloads = (manifest.get("objective_payloads", {})
                          if isinstance(manifest, dict) else {})
    references: set[str] = set()
    for collection in (roles, path_payloads, objective_payloads):
        if isinstance(collection, dict):
            for names in collection.values():
                if isinstance(names, list):
                    references.update(names)
    if isinstance(arm_payloads, dict):
        for row in arm_payloads.values():
            if isinstance(row, dict):
                for names in row.values():
                    if isinstance(names, list):
                        references.update(names)
    if (not isinstance(manifest, dict)
            or manifest.get("schema") != "entry-v2-m8-evidence-manifest-v2"
            or manifest.get("arms") != list(CANONICAL_ARMS)
            or set(manifest.get("selectable_paths", ())) != paths
            or set(manifest.get("real_objective_ids", ())) != real_ids
            or set(manifest.get("twin_objective_ids", ())) != twin_ids
            or manifest.get("payload_sha256") != other_hashes
            or set(roles) != {"rehearsal", "objectives", "arm_head_paths",
                              "pretexts", "selected_full_transition",
                              "restart_contract"}
            or any(not isinstance(names, list) or not names for names in roles.values())
            or set(arm_payloads) != set(CANONICAL_ARMS)
            or any(not isinstance(row, dict)
                   or set(row) != {"initial", "pointwise", "best", "final"}
                   or any(not isinstance(names, list) or not names
                          for names in row.values())
                   for row in arm_payloads.values())
            or set(path_payloads) != paths
            or any(not isinstance(names, list) or not names
                   for names in path_payloads.values())
            or set(objective_payloads) != real_ids | twin_ids
            or any(not isinstance(names, list) or not names
                   for names in objective_payloads.values())
            or manifest.get("timing_receipt_location") != "timing/"
            or references != set(other_hashes)
            or rehearsal.get("schema") != "entry-v2-fit-only-held-rehearsal-v1"
            or rehearsal.get("status") not in {
                "PASS", "NO_FIT_ONLY_DEPLOYABLE_DEPTH"}
            or rehearsal.get("minimum_oracle_capture")
                != FIT_ONLY_MIN_ORACLE_CAPTURE
            or type(rehearsal.get("held_launch_permitted")) is not bool
            or (rehearsal.get("status") == "PASS") !=
                rehearsal.get("held_launch_permitted")
            or rehearsal.get("g7", {}).get("minimum_oracle_capture")
                != FIT_ONLY_MIN_ORACLE_CAPTURE
            or type(rehearsal.get("g7", {}).get(
                "goal_recovery_all_blocks")) is not bool
            or set(goal_receipts) != expected_goal_receipts
            or any(not _is_sha(value) for value in goal_receipts.values())
            or objective_ledger.get("schema") != "entry-v2-m8-objective-ledger-v1"
            or set(objective_ledger.get("real_objective_ids", ())) != real_ids
            or set(objective_ledger.get("twin_objective_ids", ())) != twin_ids
            or set(objective_ledger.get("rows", {})) != real_ids
            or path_evidence.get("schema") != "entry-v2-m8-five-arm-ten-path-v1"
            or path_evidence.get("arms") != list(CANONICAL_ARMS)
            or set(path_evidence.get("paths", {})) != paths
            or restart_contract.get("schema")
                != "entry-v2-m8-numerical-restart-contract-v2"
            or restart_contract.get("strict_second_process_reload_required") is not True
            or restart_contract.get("same_selected_full_learner_required") is not True
            or restart_contract.get("source_tree_sha256")
                != rehearsal.get("source_tree_sha256")
            or not _is_sha(restart_contract.get(
                "diagnostic_semantic_identity_sha256"))
            or not isinstance(restart_contract.get("one_load_id"), str)
            or not restart_contract["one_load_id"]):
        raise StagePersistenceRefusal("M8 5-arm/10-path/44+44 census differs")
    arm_matrix = rehearsal.get("e2r", {}).get("arm_head_matrix", {})
    selected_path = arm_matrix.get("winner") or arm_matrix.get("diagnostic_path")
    g7 = rehearsal.get("g7", {})
    selected_names = roles["selected_full_transition"]
    expected_learner_objective = (
        "A0_CURRENT_GROUPING"
        if isinstance(selected_path, str) and selected_path.startswith("C0:")
        else arm_matrix.get("selected_objective"))
    if (not isinstance(selected_path, str) or ":" not in selected_path
            or g7.get("single_real_path") != selected_path
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
            or not all(name in other_hashes for name in selected_names)
            or not any(name.endswith("/final.safetensors")
                       for name in selected_names)
            or not any(name.endswith("/objective-head.safetensors")
                       for name in selected_names)
            or not any(name.endswith("/canary-input.npz")
                       for name in selected_names)
            or not any(name.endswith("canary-output.npz")
                       for name in selected_names)
            or not any(name.endswith("/training.json")
                       for name in selected_names)
            or not {"mapper.json", "calibrator.json", "thresholds.json",
                    "scores.npz", "replay.json"}.issubset(
                        {Path(name).name for name in selected_names})
            or (selected_path.endswith(":catboost") and (
                sum(name.endswith("-pairlogit.cbm")
                    for name in selected_names) != 3
                or not any(name.endswith("/catboost/config.json")
                           for name in selected_names)))):
        raise StagePersistenceRefusal(
            "M8 same-full-learner E1r/E2r transition differs")
    # The v1 boundary pointed every role at one of three summaries.  The v2
    # boundary must contain executable numerical bytes for every fitted role.
    if (not any(name.endswith(".safetensors") for name in other_hashes)
            or not any(name.endswith(".npz") for name in other_hashes)
            or not any(name.endswith(".cbm") for name in other_hashes)):
        raise StagePersistenceRefusal("M8 executable numerical formats are absent")
    for arm, row in arm_payloads.items():
        for role, names in row.items():
            if (not all(name in other_hashes for name in names)
                    or not any(name.endswith(".safetensors") for name in names)):
                raise StagePersistenceRefusal(
                    f"M8 {arm}/{role} lacks a real checkpoint")
            if role in {"best", "final"} and not any(
                    name.endswith("canary-output.npz") for name in names):
                raise StagePersistenceRefusal(
                    f"M8 {arm}/{role} lacks its numerical output canary")
    for path, names in path_payloads.items():
        suffixes = {Path(name).name for name in names}
        if (not all(name in other_hashes for name in names)
                or not {"mapper.json", "calibrator.json", "thresholds.json",
                        "scores.npz", "replay.json"}.issubset(suffixes)
                or (path.endswith(":catboost")
                    and not any(name.endswith(".cbm") for name in names))):
            raise StagePersistenceRefusal(
                f"M8 {path} lacks its executable policy/replay artifacts")
    pretexts = roles["pretexts"]
    if (len(pretexts) < 3 or not all(name in other_hashes for name in pretexts)
            or sum(name.endswith("checkpoint.npz") for name in pretexts) < 2):
        raise StagePersistenceRefusal("M8 pretext restart plane is incomplete")
    ledger_rows = objective_ledger["rows"]
    twin_rows = objective_ledger.get("twin_rows", {})
    for objective, names in objective_payloads.items():
        if not all(name in other_hashes for name in names):
            raise StagePersistenceRefusal(
                f"M8 {objective} references an absent numerical payload")
        row = ledger_rows.get(objective)
        if row is None:
            row = twin_rows.get(objective)
        if not isinstance(row, dict):
            raise StagePersistenceRefusal(f"M8 {objective} ledger row is absent")
        materialized = row.get("status") == "MATERIALIZED"
        has_checkpoint = any(name.endswith(".safetensors") for name in names)
        if materialized != has_checkpoint:
            raise StagePersistenceRefusal(
                f"M8 {objective} availability/checkpoint census differs")
    _validate_self_receipt(rehearsal, label="M8 rehearsal")
    _validate_self_receipt(manifest, label="M8 manifest")


def _validate_evidence_payloads(stage: str, payloads: Mapping[str, bytes]) -> None:
    if stage == "ACCEPTANCE":
        acceptance = {name: raw for name, raw in payloads.items()
                      if name.startswith("acceptance/")}
        m8 = {name: raw for name, raw in payloads.items()
              if name.startswith("M8/")}
        if (set(acceptance) != set(ACCEPTANCE_NUMERICAL_PAYLOADS)
                or not set(M8_EVIDENCE_PAYLOADS).issubset(m8)
                or len(acceptance) + len(m8) != len(payloads)):
            raise StagePersistenceRefusal("acceptance evidence payload set differs")
        _validate_acceptance_numerical(acceptance)
        _validate_m8_evidence(payloads)
    elif any(name.startswith("M8/") for name in payloads):
        _validate_m8_evidence(payloads)


@dataclass(frozen=True)
class StageNumericalArtifacts:
    stage: str
    payloads: Mapping[str, bytes]
    payload_sha256: Mapping[str, str]
    artifact_sha256: str

    @classmethod
    def freeze(cls, stage: str, payloads: Mapping[str, bytes]
               ) -> "StageNumericalArtifacts":
        if stage not in ("E1", "E2"):
            raise StagePersistenceRefusal("numerical artifacts are only frozen at E1/E2")
        if any(not isinstance(name, str) or not isinstance(raw, bytes)
               for name, raw in payloads.items()):
            raise StagePersistenceRefusal("numerical artifacts require string/byte payloads")
        supplied = dict(payloads)
        required = E1_NUMERICAL_PAYLOADS if stage == "E1" else E2_NUMERICAL_PAYLOADS
        allowed = set(required)
        if stage == "E2":
            try:
                selection = json.loads(supplied["selection.json"])
                kind = selection["decision_head_kind"]
            except (KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise StagePersistenceRefusal("E2 selection payload is incomplete") from exc
            if kind == "catboost":
                base = set(required_payloads_for_head("direct_neural"))
                allowed |= set(required_payloads_for_head("catboost")) - base
            elif kind != "direct_neural":
                raise StagePersistenceRefusal("E2 selection decision head is unsupported")
        if set(supplied) != allowed:
            raise StagePersistenceRefusal(
                f"{stage} numerical payload set differs from the frozen schema"
            )
        for name, raw in supplied.items():
            _validate_numerical_payload(name, raw)
        hashes = {name: _sha(raw) for name, raw in sorted(supplied.items())}
        artifact = _sha(_canonical({"stage": stage, "payload_sha256": hashes}))
        return cls(stage, MappingProxyType(supplied), MappingProxyType(hashes), artifact)

    def validate(self) -> None:
        rebuilt = self.freeze(self.stage, self.payloads)
        if (dict(rebuilt.payload_sha256) != dict(self.payload_sha256)
                or rebuilt.artifact_sha256 != self.artifact_sha256):
            raise StagePersistenceRefusal("numerical artifact identity changed")


def _json_payload(artifacts: StageNumericalArtifacts, name: str) -> Mapping[str, Any]:
    try:
        value = json.loads(artifacts.payloads[name])
    except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StagePersistenceRefusal(f"numerical metadata is invalid: {name}") from exc
    if not isinstance(value, dict):
        raise StagePersistenceRefusal(f"numerical metadata is not an object: {name}")
    return value


def _validate_numerical_public_binding(
    public_result: E1ScreenResult | FrozenWinnerSelection,
    numerical: StageNumericalArtifacts,
) -> None:
    """Bind every numerical byte to the public selection without refitting."""
    numerical.validate()
    if numerical.stage == "E1":
        if not isinstance(public_result, E1ScreenResult):
            raise StagePersistenceRefusal("E1 numerical/public type differs")
        metadata = _json_payload(numerical, "finalists.json")
        other_hashes = {name: digest for name, digest in numerical.payload_sha256.items()
                        if name != "finalists.json"}
        if (set(metadata) != {"schema", "finalists", "finalist_receipt_sha256",
                              "payload_sha256"}
                or metadata["schema"] != "entry-v2-e1-finalists-v1"
                or not isinstance(metadata["finalists"], list)
                or any(not isinstance(item, str) for item in metadata["finalists"])
                or tuple(metadata["finalists"]) != public_result.finalists
                or metadata["finalist_receipt_sha256"]
                    != public_result.finalist_receipt_sha256
                or metadata["payload_sha256"] != other_hashes):
            raise StagePersistenceRefusal("E1 numerical bytes differ from its finalists")
        return
    if not isinstance(public_result, FrozenWinnerSelection):
        raise StagePersistenceRefusal("E2 numerical/public type differs")
    metadata = _json_payload(numerical, "selection.json")
    capacity = _json_payload(numerical, "capacity.json")
    selected_normalizer = _json_payload(
        numerical, "selected-horizon-normalizer.json")
    validation_roster = _json_payload(numerical, "validation-roster.json")
    arm_authorization = _json_payload(numerical, "arm-authorization.json")
    try:
        # ``StageNumericalArtifacts.validate`` has already checked the exact
        # immutable file-byte digest.  Capacity validation is over the parsed
        # semantic document; its canonical object hash deliberately includes
        # the repository JSON newline and therefore is not the raw file hash.
        validate_capacity_document(capacity)
    except C.EntryV2Refusal as exc:
        raise StagePersistenceRefusal(
            "E2 capacity bytes fail the shared economics contract"
        ) from exc
    other_hashes = {name: digest for name, digest in numerical.payload_sha256.items()
                    if name != "selection.json"}
    confirmation = public_result.confirmation
    normalizer_core = dict(selected_normalizer)
    normalizer_receipt = normalizer_core.pop("receipt_sha256", None)
    roster_core = dict(validation_roster)
    roster_receipt = roster_core.pop("receipt_sha256", None)
    expected_paths = {f"{arm}:{head}" for arm in CANONICAL_ARMS
                      for head in DECISION_HEADS}
    expected_capacity_rows = {
        asset: {
            key: value for key, value in
            dict(confirmation.economics[asset].canonical()).items()
            if key != "capacity_authority_sha256"
        }
        for asset in C.ASSETS
    }
    capacity_public_projection = {
        asset: dict(row) for asset, row in capacity.get("per_asset", {}).items()
    }
    if (set(metadata) != {"schema", "probe_id", "arm", "decision_head_kind",
                          "selection_hashes", "objective_freeze_receipt_sha256",
                          "payload_sha256"}
            or metadata["schema"] != "entry-v2-e2-selection-v1"
            or metadata["probe_id"] != confirmation.probe_id
            or metadata["arm"] != confirmation.arm
            or metadata["decision_head_kind"] != confirmation.decision_kind
            or metadata["selection_hashes"] != dict(public_result.selection_hashes)
            or metadata["objective_freeze_receipt_sha256"]
                != public_result.objective_freeze_receipt_sha256
            or metadata["payload_sha256"] != other_hashes
            or selected_normalizer.get("schema")
                != "entry-v2-selected-horizon-normalizer-v1"
            or selected_normalizer.get("coordinates")
                != [300, 600, 900, 1200, 1800, "FINAL"]
            or not _is_sha(selected_normalizer.get("target_schema_sha256"))
            or not _is_sha(selected_normalizer.get("target_law_sha256"))
            or not _is_sha(normalizer_receipt)
            or _sha(_canonical(normalizer_core)) != normalizer_receipt
            or validation_roster.get("schema")
                != "entry-v2-e2-validation-roster-v1"
            or validation_roster.get("weighting") != "UNWEIGHTED_VALID_ROWS"
            or validation_roster.get("selected_horizon_normalizer_sha256")
                != normalizer_receipt
            or not isinstance(validation_roster.get("days"), list)
            or not validation_roster["days"]
            or validation_roster["days"] != sorted(set(validation_roster["days"]))
            or not isinstance(validation_roster.get("candidate_ids"), list)
            or validation_roster["candidate_ids"]
                != sorted(set(validation_roster["candidate_ids"]))
            or not _is_sha(roster_receipt)
            or _sha(_canonical(roster_core)) != roster_receipt
            or arm_authorization.get("schema")
                != "entry-v2-e2-arm-authorization-v1"
            or arm_authorization.get("selected_arm") != confirmation.arm
            or set(arm_authorization.get("five_arm_checkpoint_sha256", {}))
                != set(CANONICAL_ARMS)
            or any(not _is_sha(value) for value in
                   arm_authorization.get("five_arm_checkpoint_sha256", {}).values())
            or set(arm_authorization.get("ten_path_receipt_sha256", {}))
                != expected_paths
            or any(not _is_sha(value) for value in
                   arm_authorization.get("ten_path_receipt_sha256", {}).values())
            or numerical.payload_sha256["mapper.json"] != confirmation.mapper_sha256
            or numerical.payload_sha256["calibrator.json"]
                != confirmation.calibrator_sha256
            or numerical.payload_sha256["thresholds.json"]
                != confirmation.thresholds_sha256
            or numerical.payload_sha256["capacity.json"]
                != confirmation.capacity_authority_sha256
            or capacity_public_projection != expected_capacity_rows):
        raise StagePersistenceRefusal("E2 numerical bytes differ from its frozen winner")


_DATACLASSES = {
    f"{value.__module__}.{value.__qualname__}": value for value in (
        PairedObservationRecord, ProbeSupportInputs, MeasuredProbeScreen,
        E1ScreenResult, AssetEconomics, MeasuredFinalistConfirmation,
        FrozenWinnerSelection,
    )
}
_ENUMS = {f"{SupportKind.__module__}.{SupportKind.__qualname__}": SupportKind}


def _encode_typed(value: Any, blobs: dict[str, bytes]) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not np.isfinite(value):
            raise StagePersistenceRefusal("non-finite public stage scalar")
        return value
    if isinstance(value, np.generic):
        return _encode_typed(value.item(), blobs)
    if isinstance(value, np.ndarray):
        if value.dtype.hasobject:
            raise StagePersistenceRefusal("public stage object array is forbidden")
        stream = io.BytesIO(); np.save(stream, np.ascontiguousarray(value), allow_pickle=False)
        logical = f"public/array-{len(blobs):06d}.npy"
        raw = stream.getvalue(); blobs[logical] = raw
        return {"$array": logical, "dtype": value.dtype.str,
                "shape": list(value.shape), "sha256": _sha(raw)}
    if isinstance(value, bytes):
        logical = f"public/bytes-{len(blobs):06d}.bin"
        blobs[logical] = value
        return {"$bytes": logical, "sha256": _sha(value)}
    if isinstance(value, Enum):
        tag = f"{type(value).__module__}.{type(value).__qualname__}"
        if tag not in _ENUMS:
            raise StagePersistenceRefusal("unregistered public stage enum")
        return {"$enum": tag, "value": value.value}
    if is_dataclass(value):
        tag = f"{type(value).__module__}.{type(value).__qualname__}"
        if tag not in _DATACLASSES:
            raise StagePersistenceRefusal(f"unregistered public stage dataclass: {tag}")
        return {"$dataclass": tag, "fields": {
            field.name: _encode_typed(getattr(value, field.name), blobs)
            for field in fields(value)
        }}
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise StagePersistenceRefusal("public stage mapping keys must be strings")
        return {"$mapping": {
            key: _encode_typed(value[key], blobs) for key in sorted(value)
        }}
    if isinstance(value, tuple):
        return {"$tuple": [_encode_typed(item, blobs) for item in value]}
    if isinstance(value, list):
        return {"$list": [_encode_typed(item, blobs) for item in value]}
    raise StagePersistenceRefusal(
        f"unsupported public stage value: {type(value).__module__}.{type(value).__qualname__}"
    )


def _decode_typed(value: Any, blobs: Mapping[str, bytes]) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if not isinstance(value, dict) or len(value) == 0:
        raise StagePersistenceRefusal("typed public stage node is invalid")
    if "$array" in value:
        if set(value) != {"$array", "dtype", "shape", "sha256"}:
            raise StagePersistenceRefusal("typed array schema differs")
        name = value["$array"]; raw = blobs.get(name)
        if raw is None or _sha(raw) != value["sha256"]:
            raise StagePersistenceRefusal("typed array bytes changed")
        try:
            array = np.load(io.BytesIO(raw), allow_pickle=False)
        except (OSError, ValueError, EOFError) as exc:
            raise StagePersistenceRefusal("typed array does not load") from exc
        if (array.dtype.str != value["dtype"] or list(array.shape) != value["shape"]
                or array.dtype.hasobject):
            raise StagePersistenceRefusal("typed array identity differs")
        array.setflags(write=False); return array
    if "$bytes" in value:
        if set(value) != {"$bytes", "sha256"}:
            raise StagePersistenceRefusal("typed bytes schema differs")
        raw = blobs.get(value["$bytes"])
        if raw is None or _sha(raw) != value["sha256"]:
            raise StagePersistenceRefusal("typed bytes changed")
        return raw
    if "$enum" in value:
        if set(value) != {"$enum", "value"} or value["$enum"] not in _ENUMS:
            raise StagePersistenceRefusal("typed enum schema differs")
        return _ENUMS[value["$enum"]](value["value"])
    if "$dataclass" in value:
        if set(value) != {"$dataclass", "fields"} or value["$dataclass"] not in _DATACLASSES:
            raise StagePersistenceRefusal("typed dataclass schema differs")
        cls = _DATACLASSES[value["$dataclass"]]
        raw_fields = value["fields"]
        expected = {field.name for field in fields(cls)}
        if not isinstance(raw_fields, dict) or set(raw_fields) != expected:
            raise StagePersistenceRefusal("typed dataclass fields differ")
        return cls(**{name: _decode_typed(raw_fields[name], blobs)
                      for name in sorted(raw_fields)})
    if "$mapping" in value:
        if set(value) != {"$mapping"} or not isinstance(value["$mapping"], dict):
            raise StagePersistenceRefusal("typed mapping schema differs")
        return MappingProxyType({key: _decode_typed(item, blobs)
                                 for key, item in value["$mapping"].items()})
    if "$tuple" in value:
        if set(value) != {"$tuple"} or not isinstance(value["$tuple"], list):
            raise StagePersistenceRefusal("typed tuple schema differs")
        return tuple(_decode_typed(item, blobs) for item in value["$tuple"])
    if "$list" in value:
        if set(value) != {"$list"} or not isinstance(value["$list"], list):
            raise StagePersistenceRefusal("typed list schema differs")
        return [_decode_typed(item, blobs) for item in value["$list"]]
    raise StagePersistenceRefusal("unknown typed public stage node")


def _typed_blob_references(value: Any) -> set[str]:
    if value is None or isinstance(value, (bool, int, float, str)):
        return set()
    if isinstance(value, list):
        result: set[str] = set()
        for item in value:
            result.update(_typed_blob_references(item))
        return result
    if not isinstance(value, dict):
        raise StagePersistenceRefusal("typed public stage node is invalid")
    if "$array" in value:
        return {value["$array"]} if isinstance(value["$array"], str) else set()
    if "$bytes" in value:
        return {value["$bytes"]} if isinstance(value["$bytes"], str) else set()
    result = set()
    for item in value.values():
        result.update(_typed_blob_references(item))
    return result


def _json_plain(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, (float, np.floating)):
        if not np.isfinite(value):
            raise StagePersistenceRefusal("execution detail contains a non-finite scalar")
        return float(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise StagePersistenceRefusal("execution detail keys must be strings")
        return {key: _json_plain(item) for key, item in sorted(value.items())}
    if isinstance(value, (tuple, list)):
        return [_json_plain(item) for item in value]
    raise StagePersistenceRefusal("execution detail is not canonical JSON data")


def _execution_payload(value: ExactComponentExecution) -> Mapping[str, Any]:
    return {
        "component": value.component,
        "passed": value.passed,
        "fit_only": value.fit_only,
        "maximum_day": value.maximum_day,
        "result_artifact_sha256": value.result_artifact_sha256,
        "frozen_row_manifest_sha256": value.frozen_row_manifest_sha256,
        "details": _json_plain(value.details),
    }


def _load_execution(value: Any, stage: str) -> ExactComponentExecution:
    expected = {field.name for field in fields(ExactComponentExecution)}
    if not isinstance(value, dict) or set(value) != expected:
        raise StagePersistenceRefusal("stage execution schema differs")
    result = ExactComponentExecution(**value)
    required_gates = {
        "frozen_inputs", "frozen_objective", "frozen_thresholds",
        "canonical_replay", "no_h2_open",
    } | ({"report_only", "no_selection_mutation"} if stage == "E3" else set())
    if (result.component != f"execute_{stage.lower()}" or not result.passed
            or result.fit_only or result.maximum_day != {"E1": 20211231,
                                                          "E2": 20220630,
                                                          "E3": 20221230}[stage]
            or not _is_sha(result.result_artifact_sha256)
            or not _is_sha(result.frozen_row_manifest_sha256)
            or result.frozen_row_manifest_sha256 != result.result_artifact_sha256
            or any(result.details.get(gate) is not True for gate in required_gates)):
        raise StagePersistenceRefusal("persisted stage execution is not exact/no-H2")
    return result


def _rebuild_e3_execution(
    acceptance_sha256: str,
    prior_stage_sha256: str,
    winner: FrozenWinnerSelection,
    artifacts: HeldWinnerArtifacts,
) -> ExactComponentExecution:
    verifier = ExactHeldStageEngine(C.CACHE_ROOT / "held-stage-persistence-verifier")
    verifier.acceptance_sha256 = acceptance_sha256
    verifier.e2 = winner
    try:
        return verifier.execute_e3(acceptance_sha256, prior_stage_sha256, artifacts)
    except HeldStageRefusal as exc:
        raise StagePersistenceRefusal(
            "E3 numerical/public artifact differs from its frozen E2 winner"
        ) from exc


@dataclass(frozen=True)
class LoadedStageBoundary:
    stage: str
    acceptance_sha256: str
    prior_stage_sha256: str
    parent_boundary_sha256: str
    boundary_sha256: str
    execution: ExactComponentExecution
    public_result: E1ScreenResult | FrozenWinnerSelection | HeldWinnerArtifacts
    numerical: StageNumericalArtifacts | None
    diagnostic_evidence_sha256: str


@dataclass(frozen=True)
class LoadedStageEvidence:
    """Winner-independent immutable evidence emitted before a stage decision."""
    stage: str
    payloads: Mapping[str, bytes]
    payload_sha256: Mapping[str, str]
    evidence_sha256: str


@dataclass(frozen=True)
class HeldStageResume:
    """An accepted-only restart has no held engine; restored E1+ does."""
    engine: ExactHeldStageEngine | None
    numerical: Mapping[str, StageNumericalArtifacts]
    restored_through: str | None

    def __iter__(self):
        # Preserve existing two-value unpacking while exposing explicit state.
        yield self.engine
        yield self.numerical


class StageBoundaryStore:
    def __init__(self, root: str | os.PathLike[str]) -> None:
        self.root = C.assert_workspace_output(root)
        C.guard_payload(self.root)

    def path(self, stage: str) -> Path:
        if stage not in STAGES:
            raise StagePersistenceRefusal("unknown held stage")
        return self.root / f"{stage}.boundary"

    def evidence_path(self, stage: str) -> Path:
        if stage not in EVIDENCE_STAGES:
            raise StagePersistenceRefusal("unknown held evidence stage")
        return self.root / f"{stage}.evidence"

    @staticmethod
    def _write(path: Path, raw: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "xb") as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())

    @staticmethod
    def _readonly_tree(root: Path) -> None:
        for path in sorted(root.rglob("*"), reverse=True):
            os.chmod(path, 0o555 if path.is_dir() else 0o444)
        os.chmod(root, 0o555)

    def publish_evidence(self, stage: str, payloads: Mapping[str, bytes]) -> str:
        """Atomically publish exact pre-decision evidence without requiring a winner."""
        target = self.evidence_path(stage)
        if (not isinstance(payloads, Mapping) or not payloads
                or any(not isinstance(name, str) or not _safe_name(name)
                       or not isinstance(raw, bytes) or not raw
                       for name, raw in payloads.items())):
            raise StagePersistenceRefusal("held evidence payloads are invalid")
        supplied = dict(payloads)
        _validate_evidence_payloads(stage, supplied)
        rows = [
            {"logical_name": name, "file": f"blobs/{index:06d}.bin",
             "sha256": _sha(raw), "bytes": len(raw)}
            for index, (name, raw) in enumerate(sorted(supplied.items()))
        ]
        core = {
            "schema": EVIDENCE_SCHEMA, "stage": stage,
            "payloads": rows, "h2_permit": False,
        }
        evidence_sha256 = _sha(_canonical(core))
        if target.exists():
            loaded = self.load_evidence(stage, expected_sha256=evidence_sha256)
            if (dict(loaded.payload_sha256)
                    != {name: _sha(raw) for name, raw in supplied.items()}):
                raise StagePersistenceRefusal("existing immutable held evidence differs")
            return loaded.evidence_sha256

        self.root.mkdir(parents=True, exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix=f".{stage}.evidence.", dir=self.root))
        published = False
        try:
            for row in rows:
                self._write(temporary / row["file"], supplied[row["logical_name"]])
            self._write(
                temporary / EVIDENCE_MANIFEST,
                _canonical({**core, "evidence_sha256": evidence_sha256}),
            )
            self._readonly_tree(temporary)
            try:
                os.rename(temporary, target)
            except OSError as exc:
                if not target.exists():
                    raise StagePersistenceRefusal(
                        "atomic held evidence publication failed"
                    ) from exc
                temporary.chmod(0o755)
                for path in temporary.rglob("*"):
                    try:
                        path.chmod(0o755 if path.is_dir() else 0o644)
                    except FileNotFoundError:
                        pass
                shutil.rmtree(temporary)
                loaded = self.load_evidence(stage, expected_sha256=evidence_sha256)
                if (dict(loaded.payload_sha256)
                        != {name: _sha(raw) for name, raw in supplied.items()}):
                    raise StagePersistenceRefusal(
                        "concurrent immutable held evidence differs"
                    )
                return loaded.evidence_sha256
            parent_fd = os.open(self.root, os.O_RDONLY)
            try:
                os.fsync(parent_fd)
            finally:
                os.close(parent_fd)
            published = True
        finally:
            if not published and temporary.exists():
                temporary.chmod(0o755)
                for path in temporary.rglob("*"):
                    try:
                        path.chmod(0o755 if path.is_dir() else 0o644)
                    except FileNotFoundError:
                        pass
                shutil.rmtree(temporary)
        return self.load_evidence(
            stage, expected_sha256=evidence_sha256
        ).evidence_sha256

    def load_evidence(
        self, stage: str, *, expected_sha256: str | None = None,
    ) -> LoadedStageEvidence:
        target = self.evidence_path(stage)
        if (target.is_symlink() or not target.is_dir()
                or stat.S_IMODE(target.stat().st_mode) & 0o222):
            raise StagePersistenceRefusal(
                f"{stage} held evidence is absent, mutable, or a symlink"
            )
        if {path.name for path in target.iterdir()} != {EVIDENCE_MANIFEST, "blobs"}:
            raise StagePersistenceRefusal("held evidence has missing/extra files")
        manifest_path = target / EVIDENCE_MANIFEST
        blob_dir = target / "blobs"
        if (manifest_path.is_symlink() or not manifest_path.is_file()
                or stat.S_IMODE(manifest_path.stat().st_mode) & 0o222
                or blob_dir.is_symlink() or not blob_dir.is_dir()
                or stat.S_IMODE(blob_dir.stat().st_mode) & 0o222):
            raise StagePersistenceRefusal("held evidence tree is mutable or invalid")
        raw_manifest = manifest_path.read_bytes()
        try:
            manifest = json.loads(raw_manifest)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise StagePersistenceRefusal("held evidence manifest is invalid JSON") from exc
        if _canonical(manifest) != raw_manifest:
            raise StagePersistenceRefusal("held evidence manifest is not canonical")
        if (not isinstance(manifest, dict)
                or set(manifest) != {"schema", "stage", "payloads", "h2_permit",
                                     "evidence_sha256"}
                or manifest["schema"] != EVIDENCE_SCHEMA
                or manifest["stage"] != stage
                or manifest["h2_permit"] is not False):
            raise StagePersistenceRefusal("held evidence manifest identity differs")
        core = dict(manifest); declared = core.pop("evidence_sha256")
        if (not _is_sha(declared) or _sha(_canonical(core)) != declared
                or (expected_sha256 is not None and declared != expected_sha256)):
            raise StagePersistenceRefusal("held evidence aggregate hash differs")
        rows = manifest["payloads"]
        if (not isinstance(rows, list) or not rows
                or any(not isinstance(row, dict)
                       or set(row) != {"logical_name", "file", "sha256", "bytes"}
                       or not isinstance(row["logical_name"], str)
                       or not _safe_name(row["logical_name"])
                       or not isinstance(row["file"], str)
                       or not _is_sha(row["sha256"])
                       or not isinstance(row["bytes"], int) or row["bytes"] <= 0
                       for row in rows)):
            raise StagePersistenceRefusal("held evidence payload manifest differs")
        if ([row["logical_name"] for row in rows]
                != sorted(row["logical_name"] for row in rows)
                or [row["file"] for row in rows]
                != [f"blobs/{index:06d}.bin" for index in range(len(rows))]):
            raise StagePersistenceRefusal("held evidence payload order differs")
        expected_files = {Path(row["file"]).name for row in rows}
        if (len(expected_files) != len(rows)
                or {path.name for path in blob_dir.iterdir()} != expected_files):
            raise StagePersistenceRefusal("held evidence blob set differs")
        payloads: dict[str, bytes] = {}
        hashes: dict[str, str] = {}
        for row in rows:
            path = target / row["file"]
            if (path.is_symlink() or not path.is_file()
                    or stat.S_IMODE(path.stat().st_mode) & 0o222):
                raise StagePersistenceRefusal("held evidence blob is mutable/missing")
            raw = path.read_bytes()
            if len(raw) != row["bytes"] or _sha(raw) != row["sha256"]:
                raise StagePersistenceRefusal("held evidence blob content changed")
            if row["logical_name"] in payloads:
                raise StagePersistenceRefusal("held evidence logical payload duplicates")
            payloads[row["logical_name"]] = raw
            hashes[row["logical_name"]] = row["sha256"]
        _validate_evidence_payloads(stage, payloads)
        return LoadedStageEvidence(
            stage, MappingProxyType(payloads), MappingProxyType(hashes), declared,
        )

    def _publish(
        self, stage: str, acceptance_sha256: str, prior_stage_sha256: str,
        execution: ExactComponentExecution,
        public_result: E1ScreenResult | FrozenWinnerSelection | HeldWinnerArtifacts,
        numerical: StageNumericalArtifacts | None,
        *, diagnostic_evidence_sha256: str | None,
        crash_after_boundary: bool,
    ) -> LoadedStageBoundary:
        if (not _is_sha(acceptance_sha256)
                or (stage != "E1" and not _is_sha(prior_stage_sha256))
                or (stage == "E1" and prior_stage_sha256 != "0" * 64)):
            raise StagePersistenceRefusal("stage boundary chain identity is invalid")
        diagnostic_evidence_sha256 = (
            acceptance_sha256 if diagnostic_evidence_sha256 is None
            else diagnostic_evidence_sha256
        )
        if not _is_sha(diagnostic_evidence_sha256):
            raise StagePersistenceRefusal("diagnostic evidence identity is invalid")
        parent_hash = "0" * 64
        parent: LoadedStageBoundary | None = None
        if stage != "E1":
            parent = self.load(STAGES[STAGES.index(stage) - 1])
            parent_hash = parent.boundary_sha256
            if parent.acceptance_sha256 != acceptance_sha256:
                raise StagePersistenceRefusal("stage boundary acceptance identity changed")
            if parent.diagnostic_evidence_sha256 != diagnostic_evidence_sha256:
                raise StagePersistenceRefusal("stage diagnostic evidence identity changed")
        if stage in ("E1", "E2"):
            if numerical is None or numerical.stage != stage:
                raise StagePersistenceRefusal("stage numerical artifact is absent/mistyped")
            if not isinstance(public_result, (E1ScreenResult, FrozenWinnerSelection)):
                raise StagePersistenceRefusal("stage public artifact type differs")
            _validate_numerical_public_binding(public_result, numerical)
        elif numerical is not None:
            raise StagePersistenceRefusal("E3 numerical payload must be the held bundle/fold")
        if stage == "E3":
            if (not isinstance(public_result, HeldWinnerArtifacts)
                    or parent is None
                    or not isinstance(parent.public_result, FrozenWinnerSelection)):
                raise StagePersistenceRefusal("E3 public artifact/parent type differs")
            try:
                public_result.validate(parent.public_result)
            except HeldStageRefusal as exc:
                raise StagePersistenceRefusal(
                    "E3 public artifact differs from its frozen E2 winner"
                ) from exc
            if _rebuild_e3_execution(
                acceptance_sha256, prior_stage_sha256,
                parent.public_result, public_result,
            ) != execution:
                raise StagePersistenceRefusal("E3 execution is not reproducible")

        target = self.path(stage)
        if target.exists():
            loaded = self.load(
                stage,
                expected_acceptance_sha256=acceptance_sha256,
                policy_factory=(public_result.policy_factory
                                if isinstance(public_result, HeldWinnerArtifacts) else None),
            )
            if (loaded.acceptance_sha256 != acceptance_sha256
                    or loaded.prior_stage_sha256 != prior_stage_sha256
                    or loaded.diagnostic_evidence_sha256
                        != diagnostic_evidence_sha256
                    or loaded.execution != execution
                    or (numerical is not None and (
                        loaded.numerical is None
                        or loaded.numerical.artifact_sha256
                        != numerical.artifact_sha256))):
                raise StagePersistenceRefusal("existing immutable stage boundary differs")
            if crash_after_boundary:
                raise InjectedBoundaryCrash(stage)
            return loaded
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix=f".{stage}.", dir=self.root))
        published = False
        try:
            blobs: dict[str, bytes] = {}
            if stage == "E3":
                if not isinstance(public_result, HeldWinnerArtifacts):
                    raise StagePersistenceRefusal("E3 public artifact type differs")
                public_node = {
                    "$held_e3": {
                        "objective_probe_id": public_result.objective_probe_id,
                        "policy_kind": public_result.policy_kind,
                        "target_row_manifest_sha256":
                            public_result.target_row_manifest_sha256,
                    }
                }
                for name, raw in public_result.bundle_payloads.items():
                    logical = f"bundle/{name}"; _validate_numerical_payload(logical, raw)
                    blobs[logical] = raw
                save_fold(temporary / FOLD_DIRECTORY, public_result.primary_e3)
            else:
                public_node = _encode_typed(public_result, blobs)
                assert numerical is not None
                for name, raw in numerical.payloads.items():
                    blobs[f"numerical/{name}"] = raw

            blob_rows = []
            for index, (logical, raw) in enumerate(sorted(blobs.items())):
                filename = f"blobs/{index:06d}.bin"
                self._write(temporary / filename, raw)
                blob_rows.append({"logical_name": logical, "file": filename,
                                  "sha256": _sha(raw), "bytes": len(raw)})
            public_artifact = (public_result.artifact_sha256
                               if stage in ("E1", "E2") else execution.result_artifact_sha256)
            core = {
                "schema": SCHEMA, "stage": stage, "acceptance_sha256": acceptance_sha256,
                "diagnostic_evidence_sha256": diagnostic_evidence_sha256,
                "prior_stage_sha256": prior_stage_sha256,
                "parent_boundary_sha256": parent_hash,
                "execution": _execution_payload(execution),
                "public_artifact_sha256": public_artifact,
                "public_result": public_node,
                "numerical_artifact_sha256": (
                    None if numerical is None else numerical.artifact_sha256
                ),
                "blobs": blob_rows, "h2_permit": False,
            }
            boundary_hash = _sha(_canonical(core))
            self._write(temporary / MANIFEST,
                        _canonical({**core, "boundary_sha256": boundary_hash}))
            parent_fd = os.open(self.root, os.O_RDONLY)
            try:
                os.fsync(parent_fd)
            finally:
                os.close(parent_fd)
            self._readonly_tree(temporary)
            try:
                os.rename(temporary, target)
            except OSError as exc:
                if not target.exists():
                    raise StagePersistenceRefusal("atomic stage publication failed") from exc
                temporary.chmod(0o755)
                for path in temporary.rglob("*"):
                    try: path.chmod(0o755 if path.is_dir() else 0o644)
                    except FileNotFoundError: pass
                shutil.rmtree(temporary)
            parent_fd = os.open(self.root, os.O_RDONLY)
            try:
                os.fsync(parent_fd)
            finally:
                os.close(parent_fd)
            published = True
        finally:
            if not published and temporary.exists():
                temporary.chmod(0o755)
                for path in temporary.rglob("*"):
                    try: path.chmod(0o755 if path.is_dir() else 0o644)
                    except FileNotFoundError: pass
                shutil.rmtree(temporary)
        loaded = self.load(
            stage,
            expected_acceptance_sha256=acceptance_sha256,
            policy_factory=(public_result.policy_factory
                            if isinstance(public_result, HeldWinnerArtifacts) else None),
        )
        if crash_after_boundary:
            raise InjectedBoundaryCrash(stage)
        return loaded

    def publish_e1(self, acceptance_sha256: str, execution: ExactComponentExecution,
                   result: E1ScreenResult, numerical: StageNumericalArtifacts, *,
                   diagnostic_evidence_sha256: str | None = None,
                   crash_after_boundary: bool = False) -> LoadedStageBoundary:
        return self._publish("E1", acceptance_sha256, "0" * 64, execution,
                             result, numerical,
                             diagnostic_evidence_sha256=diagnostic_evidence_sha256,
                             crash_after_boundary=crash_after_boundary)

    def publish_e2(self, acceptance_sha256: str, prior_stage_sha256: str,
                   execution: ExactComponentExecution, result: FrozenWinnerSelection,
                   numerical: StageNumericalArtifacts, *,
                   diagnostic_evidence_sha256: str | None = None,
                   crash_after_boundary: bool = False) -> LoadedStageBoundary:
        return self._publish("E2", acceptance_sha256, prior_stage_sha256, execution,
                             result, numerical,
                             diagnostic_evidence_sha256=diagnostic_evidence_sha256,
                             crash_after_boundary=crash_after_boundary)

    def publish_e3(self, acceptance_sha256: str, prior_stage_sha256: str,
                   execution: ExactComponentExecution, result: HeldWinnerArtifacts, *,
                   diagnostic_evidence_sha256: str | None = None,
                   crash_after_boundary: bool = False) -> LoadedStageBoundary:
        return self._publish("E3", acceptance_sha256, prior_stage_sha256, execution,
                             result, None,
                             diagnostic_evidence_sha256=diagnostic_evidence_sha256,
                             crash_after_boundary=crash_after_boundary)

    def load(self, stage: str, *, expected_acceptance_sha256: str | None = None,
             policy_factory: Callable[..., Any] | None = None) -> LoadedStageBoundary:
        target = self.path(stage)
        if target.is_symlink() or not target.is_dir():
            raise StagePersistenceRefusal(f"{stage} stage boundary is absent or a symlink")
        if stat.S_IMODE(target.stat().st_mode) & 0o222:
            raise StagePersistenceRefusal("stage boundary directory is mutable")
        expected_top = {MANIFEST, "blobs"} | ({FOLD_DIRECTORY} if stage == "E3" else set())
        if {path.name for path in target.iterdir()} != expected_top:
            raise StagePersistenceRefusal("stage boundary has missing/extra top-level files")
        manifest_path = target / MANIFEST
        if (manifest_path.is_symlink() or not manifest_path.is_file()
                or stat.S_IMODE(manifest_path.stat().st_mode) & 0o222):
            raise StagePersistenceRefusal("stage boundary manifest is mutable/missing")
        raw_manifest = manifest_path.read_bytes()
        try:
            manifest = json.loads(raw_manifest)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise StagePersistenceRefusal("stage boundary manifest is invalid JSON") from exc
        if _canonical(manifest) != raw_manifest:
            raise StagePersistenceRefusal("stage boundary manifest is not canonical")
        expected_keys = {
            "schema", "stage", "acceptance_sha256", "prior_stage_sha256",
            "diagnostic_evidence_sha256",
            "parent_boundary_sha256", "execution", "public_artifact_sha256",
            "public_result", "numerical_artifact_sha256", "blobs", "h2_permit",
            "boundary_sha256",
        }
        if (not isinstance(manifest, dict) or set(manifest) != expected_keys
                or manifest["schema"] != SCHEMA or manifest["stage"] != stage
                or manifest["h2_permit"] is not False
                or not _is_sha(manifest["acceptance_sha256"])
                or not _is_sha(manifest["diagnostic_evidence_sha256"])
                or not _is_sha(manifest["parent_boundary_sha256"])):
            raise StagePersistenceRefusal("stage boundary manifest identity differs")
        if ((stage == "E1" and manifest["prior_stage_sha256"] != "0" * 64)
                or (stage != "E1" and not _is_sha(manifest["prior_stage_sha256"]))):
            raise StagePersistenceRefusal("stage boundary prior-stage identity differs")
        core = dict(manifest); declared = core.pop("boundary_sha256")
        if not _is_sha(declared) or _sha(_canonical(core)) != declared:
            raise StagePersistenceRefusal("stage boundary aggregate hash differs")
        if (expected_acceptance_sha256 is not None
                and manifest["acceptance_sha256"] != expected_acceptance_sha256):
            raise StagePersistenceRefusal("stage boundary belongs to another acceptance")
        blob_dir = target / "blobs"
        if blob_dir.is_symlink() or not blob_dir.is_dir() \
                or stat.S_IMODE(blob_dir.stat().st_mode) & 0o222:
            raise StagePersistenceRefusal("stage blob directory is mutable/missing")
        rows = manifest["blobs"]
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise StagePersistenceRefusal("stage blob manifest is invalid")
        for row in rows:
            if (set(row) != {"logical_name", "file", "sha256", "bytes"}
                    or not isinstance(row["file"], str)
                    or not isinstance(row["logical_name"], str)
                    or not isinstance(row["bytes"], int) or row["bytes"] <= 0
                    or not _is_sha(row["sha256"])):
                raise StagePersistenceRefusal("stage blob row schema differs")
        if ([row["logical_name"] for row in rows]
                != sorted(row["logical_name"] for row in rows)
                or [row["file"] for row in rows]
                != [f"blobs/{index:06d}.bin" for index in range(len(rows))]):
            raise StagePersistenceRefusal("stage blob ordering differs")
        expected_files = {Path(row["file"]).name for row in rows}
        if (len(expected_files) != len(rows)
                or {path.name for path in blob_dir.iterdir()} != expected_files):
            raise StagePersistenceRefusal("stage blob set differs")
        blobs: dict[str, bytes] = {}
        for row in rows:
            if (not _safe_name(row["logical_name"])
                    or row["file"] != f"blobs/{Path(row['file']).name}"):
                raise StagePersistenceRefusal("stage blob row schema differs")
            path = target / row["file"]
            if (path.is_symlink() or not path.is_file()
                    or stat.S_IMODE(path.stat().st_mode) & 0o222):
                raise StagePersistenceRefusal("stage blob is mutable/missing")
            raw = path.read_bytes()
            if len(raw) != row["bytes"] or _sha(raw) != row["sha256"]:
                raise StagePersistenceRefusal("stage blob content changed")
            if row["logical_name"] in blobs:
                raise StagePersistenceRefusal("stage logical blob duplicates")
            blobs[row["logical_name"]] = raw

        execution = _load_execution(manifest["execution"], stage)
        if (execution.result_artifact_sha256 != manifest["public_artifact_sha256"]
                or execution.details.get("acceptance_sha256")
                != manifest["acceptance_sha256"]
                or (stage != "E1" and execution.details.get("prior_stage_sha256")
                    != manifest["prior_stage_sha256"])):
            raise StagePersistenceRefusal("stage execution/manifest identity differs")
        numerical = None
        if stage in ("E1", "E2"):
            prefix = "numerical/"
            payloads = {name.removeprefix(prefix): raw for name, raw in blobs.items()
                        if name.startswith(prefix)}
            numerical = StageNumericalArtifacts.freeze(stage, payloads)
            if numerical.artifact_sha256 != manifest["numerical_artifact_sha256"]:
                raise StagePersistenceRefusal("stage numerical aggregate differs")
            public_result = _decode_typed(manifest["public_result"], blobs)
            public_references = _typed_blob_references(manifest["public_result"])
            if set(blobs) != ({f"numerical/{name}" for name in payloads}
                              | public_references):
                raise StagePersistenceRefusal("stage has unreferenced/foreign blobs")
            expected_type = E1ScreenResult if stage == "E1" else FrozenWinnerSelection
            if not isinstance(public_result, expected_type):
                raise StagePersistenceRefusal("public stage result type differs")
            if public_result.artifact_sha256 != manifest["public_artifact_sha256"]:
                raise StagePersistenceRefusal("public stage artifact identity differs")
            if execution.result_artifact_sha256 != public_result.artifact_sha256:
                raise StagePersistenceRefusal("stage execution/public artifact identity differs")
            _validate_numerical_public_binding(public_result, numerical)
            if stage == "E1":
                if (not public_result.finalists
                        or not set(public_result.finalists).issubset(
                            public_result.screen_by_probe)
                        or len(public_result.support_receipts) != 44
                        or any(not _is_sha(value) for value in (
                            *public_result.paired_receipts.values(),
                            *public_result.support_receipts.values(),
                            public_result.holm_receipt_sha256,
                            public_result.finalist_receipt_sha256,
                        ))):
                    raise StagePersistenceRefusal("E1 public result identity is incomplete")
                try:
                    for row in public_result.screen_by_probe.values():
                        row.validate()
                except HeldStageRefusal as exc:
                    raise StagePersistenceRefusal(
                        "E1 public screen does not validate"
                    ) from exc
                # Recompute the same support-before-fit eligibility used by
                # ``execute_e1_screen``.  Typed-unavailable and no-feasible
                # rows remain in the 44-row ledger but correctly have no
                # paired-test receipt.
                expected_paired = {
                    probe_id for probe_id, row in
                    public_result.screen_by_probe.items()
                    if row.availability == "MATERIALIZED"
                    and row.path_availability == "MATERIALIZED"
                    and all(
                        item.measure().state is not
                            SupportState.UNAVAILABLE_LOW_SUPPORT
                        for item in (row.support, *row.additional_support)
                    )
                }
                if set(public_result.paired_receipts) != expected_paired:
                    raise StagePersistenceRefusal("E1 paired-screen ledger differs")
            else:
                try:
                    public_result.confirmation.validate(
                        public_result.confirmation.probe_id
                    )
                except HeldStageRefusal as exc:
                    raise StagePersistenceRefusal(
                        "E2 public confirmation does not validate"
                    ) from exc
                confirmation = public_result.confirmation
                expected_selection = {
                    "selected_arm_sha256": confirmation.selected_arm_sha256,
                    "selected_objective_sha256": confirmation.selected_objective_sha256,
                    "calibrator_sha256": confirmation.calibrator_sha256,
                    "thresholds_sha256": confirmation.thresholds_sha256,
                    "capacity_authority_sha256": confirmation.capacity_authority_sha256,
                }
                if dict(public_result.selection_hashes) != expected_selection:
                    raise StagePersistenceRefusal("E2 public selection differs from winner")
        else:
            if manifest["numerical_artifact_sha256"] is not None:
                raise StagePersistenceRefusal("E3 has an unexpected numerical aggregate")
            held = manifest["public_result"]
            if (not isinstance(held, dict) or set(held) != {"$held_e3"}
                    or not isinstance(held["$held_e3"], dict)
                    or policy_factory is None or not callable(policy_factory)):
                raise StagePersistenceRefusal("E3 resume requires its exact policy factory")
            metadata = held["$held_e3"]
            if set(metadata) != {"objective_probe_id", "policy_kind",
                                 "target_row_manifest_sha256"}:
                raise StagePersistenceRefusal("E3 held metadata differs")
            bundle = {name.removeprefix("bundle/"): raw for name, raw in blobs.items()
                      if name.startswith("bundle/")}
            if set(blobs) != {f"bundle/{name}" for name in bundle}:
                raise StagePersistenceRefusal("E3 has unreferenced/foreign blobs")
            if set(bundle) != set(required_payloads_for_head(metadata["policy_kind"])):
                raise StagePersistenceRefusal("E3 bundle payload set differs")
            for name, raw in bundle.items():
                _validate_numerical_payload(name, raw)
            fold_root = target / FOLD_DIRECTORY
            if (fold_root.is_symlink() or not fold_root.is_dir()
                    or any(path.is_symlink() or stat.S_IMODE(path.stat().st_mode) & 0o222
                           for path in (fold_root, *fold_root.rglob("*")))):
                raise StagePersistenceRefusal("E3 fold store is mutable or contains a symlink")
            fold = load_fold(fold_root)
            public_result = HeldWinnerArtifacts(
                MappingProxyType(bundle), fold, metadata["objective_probe_id"],
                metadata["policy_kind"], policy_factory,
                metadata["target_row_manifest_sha256"],
            )
            parent = self.load(
                "E2", expected_acceptance_sha256=manifest["acceptance_sha256"]
            )
            if (manifest["parent_boundary_sha256"] != parent.boundary_sha256
                    or not isinstance(parent.public_result, FrozenWinnerSelection)
                    or _rebuild_e3_execution(
                        manifest["acceptance_sha256"],
                        manifest["prior_stage_sha256"],
                        parent.public_result, public_result,
                    ) != execution):
                raise StagePersistenceRefusal("E3 execution/parent cannot be reproduced")
        return LoadedStageBoundary(
            stage, manifest["acceptance_sha256"], manifest["prior_stage_sha256"],
            manifest["parent_boundary_sha256"], declared, execution,
            public_result, numerical, manifest["diagnostic_evidence_sha256"],
        )

    def resume_engine(self, *, expected_acceptance_sha256: str,
                      expected_diagnostic_evidence_sha256: str | None = None,
                      policy_factory: Callable[..., Any] | None = None
                      ) -> HeldStageResume:
        present = [self.path(stage).exists() for stage in STAGES]
        if present not in ([False, False, False], [True, False, False],
                           [True, True, False], [True, True, True]):
            raise StagePersistenceRefusal("persisted stage boundary chain has a gap")
        engine: ExactHeldStageEngine | None = (
            ExactHeldStageEngine(self.root / "live") if present[0] else None
        )
        numerical: dict[str, StageNumericalArtifacts] = {}
        if present[0]:
            e1 = self.load("E1", expected_acceptance_sha256=expected_acceptance_sha256)
            if (expected_diagnostic_evidence_sha256 is not None
                    and e1.diagnostic_evidence_sha256
                    != expected_diagnostic_evidence_sha256):
                raise StagePersistenceRefusal("E1 diagnostic evidence differs")
            assert engine is not None
            engine.e1 = e1.public_result; engine.acceptance_sha256 = e1.acceptance_sha256
            engine.e1_stage_sha256 = e1.execution.result_artifact_sha256
            assert e1.numerical is not None; numerical["E1"] = e1.numerical
        if present[1]:
            e2 = self.load("E2", expected_acceptance_sha256=expected_acceptance_sha256)
            parent = self.load("E1", expected_acceptance_sha256=expected_acceptance_sha256)
            if e2.parent_boundary_sha256 != parent.boundary_sha256:
                raise StagePersistenceRefusal("E2 boundary parent identity differs")
            if (expected_diagnostic_evidence_sha256 is not None
                    and e2.diagnostic_evidence_sha256
                    != expected_diagnostic_evidence_sha256):
                raise StagePersistenceRefusal("E2 diagnostic evidence differs")
            assert engine is not None
            engine.e2 = e2.public_result; engine.e2_stage_sha256 = e2.execution.result_artifact_sha256
            assert e2.numerical is not None; numerical["E2"] = e2.numerical
        if present[2]:
            e3 = self.load("E3", expected_acceptance_sha256=expected_acceptance_sha256,
                           policy_factory=policy_factory)
            parent = self.load("E2", expected_acceptance_sha256=expected_acceptance_sha256)
            if e3.parent_boundary_sha256 != parent.boundary_sha256:
                raise StagePersistenceRefusal("E3 boundary parent identity differs")
            if (expected_diagnostic_evidence_sha256 is not None
                    and e3.diagnostic_evidence_sha256
                    != expected_diagnostic_evidence_sha256):
                raise StagePersistenceRefusal("E3 diagnostic evidence differs")
            assert engine is not None
            assert isinstance(e3.public_result, HeldWinnerArtifacts)
            assert isinstance(engine.e2, FrozenWinnerSelection)
            e3.public_result.validate(engine.e2)
            engine.artifacts = e3.public_result
        restored_through = next((stage for stage in reversed(STAGES)
                                 if self.path(stage).exists()), None)
        return HeldStageResume(engine, MappingProxyType(numerical), restored_through)


class CrashResumableHeldStageEngine:
    """Exact transitions followed by one atomic boundary publication."""
    def __init__(self, engine: ExactHeldStageEngine, store: StageBoundaryStore) -> None:
        self.engine, self.store = engine, store

    def execute_e1(self, acceptance_sha256: str, screens: Sequence[MeasuredProbeScreen],
                   numerical: StageNumericalArtifacts, *, crash_after_boundary: bool = False
                   ) -> ExactComponentExecution:
        execution = self.engine.execute_e1(acceptance_sha256, screens)
        assert self.engine.e1 is not None
        self.store.publish_e1(acceptance_sha256, execution, self.engine.e1, numerical,
                              crash_after_boundary=crash_after_boundary)
        return execution

    def execute_e2(self, acceptance_sha256: str, prior_stage_sha256: str,
                   confirmations: Sequence[MeasuredFinalistConfirmation],
                   objective_freeze_receipt_sha256: str,
                   numerical: StageNumericalArtifacts, *, crash_after_boundary: bool = False
                   ) -> ExactComponentExecution:
        execution = self.engine.execute_e2(
            acceptance_sha256, prior_stage_sha256, confirmations,
            objective_freeze_receipt_sha256,
        )
        assert self.engine.e2 is not None
        self.store.publish_e2(acceptance_sha256, prior_stage_sha256, execution,
                              self.engine.e2, numerical,
                              crash_after_boundary=crash_after_boundary)
        return execution

    def execute_e3(self, acceptance_sha256: str, prior_stage_sha256: str,
                   artifacts: HeldWinnerArtifacts, *, crash_after_boundary: bool = False
                   ) -> ExactComponentExecution:
        execution = self.engine.execute_e3(
            acceptance_sha256, prior_stage_sha256, artifacts
        )
        self.store.publish_e3(acceptance_sha256, prior_stage_sha256, execution,
                              artifacts, crash_after_boundary=crash_after_boundary)
        return execution


__all__ = [
    "ACCEPTANCE_NUMERICAL_PAYLOADS", "CrashResumableHeldStageEngine",
    "E1_NUMERICAL_PAYLOADS",
    "E2_NUMERICAL_PAYLOADS", "InjectedBoundaryCrash", "LoadedStageBoundary",
    "LoadedStageEvidence", "HeldStageResume", "M8_EVIDENCE_PAYLOADS",
    "StageBoundaryStore", "StageNumericalArtifacts", "StagePersistenceRefusal",
]
