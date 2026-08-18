"""Concrete production adoption layer for the neural-sufficiency runner.

The executor protocol is deliberately component-specific: a generic function
returning a PASS mapping cannot satisfy it.  The real trainer owns numerical
work while this backend owns order, one-load identity, immutable artifact
lineage, and conversion into the runner's typed gate evidence.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import stat
import sys
import time
from typing import Any, Mapping, Protocol

# ``python -m package.module`` executes this file as ``__main__``.  The real
# resource/executor modules import its typed result classes by canonical package
# name; without this early alias Python creates a second module object and an
# otherwise identical dataclass fails the strict production type boundary.
_CANONICAL_MODULE_NAME = "engine.entry_v2.neural_sufficiency_production"
if __name__ == "__main__":
    current = sys.modules[__name__]
    prior = sys.modules.get(_CANONICAL_MODULE_NAME)
    if prior is not None and prior is not current:
        raise RuntimeError(
            "neural sufficiency production module was loaded under two identities"
        )
    sys.modules[_CANONICAL_MODULE_NAME] = current

from .neural_sufficiency_runner import (
    ACCEPTANCE_COMPONENTS, ACCEPTANCE_FIT_END, GateEvidence, RunContext,
    adopt_e3_winner, load_acceptance_receipt, load_stage_receipt,
    run_neural_sufficiency,
)
from .capacity_contract import FIT_ONLY_MIN_ORACLE_CAPTURE
from .neural_sufficiency_source_manifest import (
    HeldSourceManifestRefusal, held_rehearsal_source_tree_sha256,
)


class ProductionDiagnosticRefusal(RuntimeError):
    pass


@dataclass(frozen=True)
class ExactComponentExecution:
    component: str
    passed: bool
    fit_only: bool
    maximum_day: int
    result_artifact_sha256: str
    frozen_row_manifest_sha256: str
    details: Mapping[str, Any]


class ExactNeuralDiagnosticExecutor(Protocol):
    def bind_stage_boundary_store(self, store: Any) -> None: ...
    def resume_stage_boundaries(self, store: Any, acceptance: Any) -> str: ...
    def timing_provenance(self) -> Mapping[str, Any]: ...
    def prepare(self) -> ExactComponentExecution: ...
    def raw_fidelity(self) -> ExactComponentExecution: ...
    def train_and_rehearse_arm(self, arm: str) -> ExactComponentExecution: ...
    def run_atlas(self) -> ExactComponentExecution: ...
    def run_direct_head(self) -> ExactComponentExecution: ...
    def run_catboost(self) -> ExactComponentExecution: ...
    def fit_mapper(self) -> ExactComponentExecution: ...
    def calibrate(self) -> ExactComponentExecution: ...
    def select_threshold_with_canonical_sweep(self) -> ExactComponentExecution: ...
    def run_canonical_replay(self) -> ExactComponentExecution: ...
    def validate_fit_ledger(self) -> ExactComponentExecution: ...
    def finalize(self) -> ExactComponentExecution: ...
    def execute_stage(self, mode: str, acceptance_sha256: str,
                      prior_stage_sha256: str) -> ExactComponentExecution: ...
    def close(self, adoption_sha256: str | None) -> ExactComponentExecution: ...
    def export_winner_bundle_payloads(self, adoption_sha256: str) -> Mapping[str, bytes]: ...
    def export_primary_e3_fold(self, adoption_sha256: str) -> Path: ...
    def transfer_winner_resources(self, adoption_sha256: str) -> Any: ...


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          allow_nan=False).encode()
    except (TypeError, ValueError) as error:
        raise ProductionDiagnosticRefusal("executor result is not canonical JSON") from error


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _is_sha(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(
        character in "0123456789abcdef" for character in value
    )


def _write_immutable(path: Path, payload: Mapping[str, Any]) -> str:
    raw = _canonical(payload); digest = _sha(raw)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(path, "xb") as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    except FileExistsError:
        if path.read_bytes() != raw:
            raise ProductionDiagnosticRefusal(
                f"immutable orchestration artifact differs: {path.name}"
            )
    os.chmod(path, 0o444)
    return digest


class NonSemanticTimingLedger:
    """Append-only monotonic side receipts, never inputs to semantic hashes."""

    SCHEMA = "entry-v2-nonsemantic-monotonic-timing-v2"
    # A-020 restart law: these are NONSEMANTIC wall-clock ceilings.  They stop
    # the invocation that exceeds one, they never poison the run root.
    LIMITS_NS = {
        ("cold", "corpus_ready"): 3600 * 1_000_000_000,
        ("warm", "corpus_ready"): 1200 * 1_000_000_000,
        ("cold", "first_competence"): 1800 * 1_000_000_000,
        ("warm", "first_competence"): 1500 * 1_000_000_000,
        ("warm", "complete_pre_h2"): 4 * 60 * 60 * 1_000_000_000,
    }

    def __init__(self, root: Path, *, segment_start_ns: int | None = None) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._sequence = 0
        self._prior_ceiling_refusals = 0
        self._parent = "0" * 64
        self._base_elapsed_ns = 0
        self._load_class: str | None = None
        last_segment_id = -1
        last_segment_class: str | None = None
        last_invocation_elapsed_ns = 0
        segment_base_elapsed_ns = 0
        for path in sorted(self.root.iterdir()):
            if (path.is_symlink() or not path.is_file()
                    or stat.S_IMODE(path.stat().st_mode) & 0o222):
                raise ProductionDiagnosticRefusal("timing side receipt tree is mutable")
            try:
                raw = path.read_bytes()
                value = json.loads(raw)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ProductionDiagnosticRefusal("timing side receipt is invalid") from exc
            core = dict(value); declared = core.pop("receipt_sha256", None)
            expected = {
                "schema", "sequence", "milestone", "load_class",
                "segment_id",
                "invocation_elapsed_ns", "milestone_elapsed_ns",
                "ceiling_elapsed_ns", "cumulative_elapsed_ns", "parent_sha256",
                "provenance", "ceiling_ns", "status",
            }
            if (_canonical(value) != raw
                    or set(core) != expected or value.get("schema") != self.SCHEMA
                    or value.get("sequence") != self._sequence
                    or value.get("parent_sha256") != self._parent
                    or not _is_sha(declared) or _sha(_canonical(core)) != declared
                    or path.name != f"{self._sequence:04d}.{value['milestone']}.{declared}.json"
                    or type(value.get("invocation_elapsed_ns")) is not int
                    or type(value.get("milestone_elapsed_ns")) is not int
                    or type(value.get("ceiling_elapsed_ns")) is not int
                    or type(value.get("cumulative_elapsed_ns")) is not int
                    or type(value.get("segment_id")) is not int
                    or not isinstance(value.get("provenance"), dict)
                    or not isinstance(value.get("milestone"), str)
                    or not value["milestone"]
                    or any(character not in
                           "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"
                           for character in value["milestone"])
                    or value["segment_id"] < 0
                    or value["segment_id"] not in (last_segment_id,
                                                    last_segment_id + 1)
                    or value["invocation_elapsed_ns"] < 0
                    or value["milestone_elapsed_ns"] < 0
                    or value["ceiling_elapsed_ns"] < 0
                    or value["milestone_elapsed_ns"]
                        > value["invocation_elapsed_ns"]
                    or value["cumulative_elapsed_ns"] < self._base_elapsed_ns):
                raise ProductionDiagnosticRefusal("timing side receipt chain differs")
            load_class = value.get("load_class")
            if load_class not in ("cold", "warm"):
                raise ProductionDiagnosticRefusal("timing load class differs")
            new_segment = value["segment_id"] != last_segment_id
            if new_segment:
                segment_base_elapsed_ns = self._base_elapsed_ns
                last_invocation_elapsed_ns = 0
            if (value["invocation_elapsed_ns"] < last_invocation_elapsed_ns
                    or value["cumulative_elapsed_ns"]
                        != segment_base_elapsed_ns
                           + value["invocation_elapsed_ns"]):
                raise ProductionDiagnosticRefusal(
                    "timing invocation/cumulative elapsed differs")
            expected_ceiling_elapsed = (
                value["invocation_elapsed_ns"]
                if value["milestone"] in {"corpus_ready", "complete_pre_h2"}
                else value["milestone_elapsed_ns"]
            )
            if value["ceiling_elapsed_ns"] != expected_ceiling_elapsed:
                raise ProductionDiagnosticRefusal(
                    "timing milestone ceiling basis differs")
            if (new_segment and (value.get("milestone") != "corpus_ready"
                                 or value.get("provenance", {}).get("load_class")
                                    != load_class)):
                raise ProductionDiagnosticRefusal(
                    "timing invocation lacks its corpus-ready classification")
            if not new_segment and value.get("provenance") != {}:
                raise ProductionDiagnosticRefusal(
                    "timing provenance repeated within an invocation")
            if not new_segment and value.get("milestone") == "corpus_ready":
                raise ProductionDiagnosticRefusal(
                    "timing corpus-ready milestone repeated within an invocation")
            ceiling = self.LIMITS_NS.get((load_class, value["milestone"]))
            expected_status = ("PASS" if ceiling is None
                               or value["ceiling_elapsed_ns"] <= ceiling
                               else "REFUSED")
            if (value.get("ceiling_ns") != ceiling
                    or value.get("status") != expected_status):
                raise ProductionDiagnosticRefusal(
                    "timing ceiling/status receipt differs")
            if expected_status != "PASS":
                # A-020 restart law.  A NONSEMANTIC timing ceiling stops the
                # invocation that exceeded it (see emit(), which raises after
                # writing the typed REFUSED receipt).  It must NEVER poison the
                # run root: a later process reconstructs the ledger over the
                # REFUSED receipt and continues.  The event stays visible in the
                # receipt tree and is counted here for the timing provenance.
                self._prior_ceiling_refusals += 1
            if (value["segment_id"] == last_segment_id
                    and last_segment_class != load_class):
                raise ProductionDiagnosticRefusal(
                    "timing load class changed within an invocation")
            if value["segment_id"] != last_segment_id:
                last_segment_id = value["segment_id"]
                last_segment_class = load_class
            self._sequence += 1
            self._parent = declared
            self._base_elapsed_ns = value["cumulative_elapsed_ns"]
            last_invocation_elapsed_ns = value["invocation_elapsed_ns"]
        self._segment_id = last_segment_id + 1
        now_ns = time.monotonic_ns()
        if (segment_start_ns is not None
                and (type(segment_start_ns) is not int
                     or segment_start_ns < 0 or segment_start_ns > now_ns)):
            raise ProductionDiagnosticRefusal(
                "timing invocation start is invalid")
        self._segment_start_ns = (now_ns if segment_start_ns is None
                                  else segment_start_ns)
        self._milestone_start_ns = self._segment_start_ns

    @property
    def prior_ceiling_refusals(self) -> int:
        """Count of REFUSED ceiling receipts left by earlier invocations.

        Report-only.  A nonzero value never blocks reconstruction (A-020).
        """
        return self._prior_ceiling_refusals

    def record(self, milestone: str, *,
               provenance: Mapping[str, Any] | None = None) -> str:
        if (not milestone or any(character not in
                "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"
                for character in milestone)):
            raise ProductionDiagnosticRefusal("timing milestone is invalid")
        provenance_value = dict(provenance or {})
        starting_invocation = self._load_class is None
        declared_class = provenance_value.get("load_class")
        if declared_class is not None:
            if declared_class not in ("cold", "warm"):
                raise ProductionDiagnosticRefusal("timing provenance load class differs")
            if self._load_class not in (None, declared_class):
                raise ProductionDiagnosticRefusal("timing provenance changed load class")
            self._load_class = declared_class
        if (starting_invocation
                and (milestone != "corpus_ready" or declared_class is None)):
            raise ProductionDiagnosticRefusal(
                "timing invocation must start with one corpus-ready provenance receipt")
        if not starting_invocation and provenance_value:
            raise ProductionDiagnosticRefusal(
                "timing provenance repeated within an invocation")
        if not starting_invocation and milestone == "corpus_ready":
            raise ProductionDiagnosticRefusal(
                "timing corpus-ready milestone repeated within an invocation")
        if self._load_class is None:
            raise ProductionDiagnosticRefusal(
                "timing milestone preceded cold/warm corpus classification")
        now_ns = time.monotonic_ns()
        invocation_elapsed = now_ns - self._segment_start_ns
        milestone_elapsed = now_ns - self._milestone_start_ns
        if invocation_elapsed < 0 or milestone_elapsed < 0:
            raise ProductionDiagnosticRefusal("monotonic clock moved backwards")
        cumulative = self._base_elapsed_ns + invocation_elapsed
        ceiling_elapsed = (
            invocation_elapsed
            if milestone in {"corpus_ready", "complete_pre_h2"}
            else milestone_elapsed
        )
        ceiling = self.LIMITS_NS.get((self._load_class, milestone))
        status = ("PASS" if ceiling is None or ceiling_elapsed <= ceiling
                  else "REFUSED")
        core = {
            "schema": self.SCHEMA, "sequence": self._sequence,
            "milestone": milestone, "load_class": self._load_class,
            "segment_id": self._segment_id,
            "invocation_elapsed_ns": invocation_elapsed,
            "milestone_elapsed_ns": milestone_elapsed,
            "ceiling_elapsed_ns": ceiling_elapsed,
            "cumulative_elapsed_ns": cumulative,
            "parent_sha256": self._parent,
            "provenance": provenance_value,
            "ceiling_ns": ceiling, "status": status,
        }
        digest = _sha(_canonical(core))
        _write_immutable(
            self.root / f"{self._sequence:04d}.{milestone}.{digest}.json",
            {**core, "receipt_sha256": digest},
        )
        self._sequence += 1; self._parent = digest
        self._milestone_start_ns = now_ns
        if status != "PASS":
            raise ProductionDiagnosticRefusal(
                f"{self._load_class} {milestone} timing ceiling exceeded")
        return digest


def _attempt_payload(*, phase: str, component: str, context: RunContext,
                     position: int | None, parent_sha256: str,
                     acceptance_sha256: str | None = None,
                     prior_stage_sha256: str | None = None) -> Mapping[str, Any]:
    return {
        "schema": "entry-v2-orchestration-attempt-v1",
        "status": "STARTED", "phase": phase, "component": component,
        "position": position, "parent_sha256": parent_sha256,
        "acceptance_sha256": acceptance_sha256,
        "prior_stage_sha256": prior_stage_sha256,
        "one_load_id": context.one_load_id,
        "corpus_sha256": context.corpus_sha256,
        "chronology_sha256": context.chronology_sha256,
        "maximum_opened_day": context.opened_through_day,
        "h2_permit": False,
    }


def _persist_failure(root: Path, *, phase: str, component: str,
                     attempt_sha256: str | None, error: BaseException,
                     layer: str, evidence_sha256: str | None = None,
                     outputs: Mapping[str, str] | None = None) -> str:
    if (not layer or len(layer) > 128
            or any(character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789:_-|."
                   for character in layer)):
        raise ProductionDiagnosticRefusal("failure layer is invalid")
    if attempt_sha256 is not None and not _is_sha(attempt_sha256):
        raise ProductionDiagnosticRefusal("failure attempt identity is invalid")
    if evidence_sha256 is not None and not _is_sha(evidence_sha256):
        raise ProductionDiagnosticRefusal("failure evidence identity is invalid")
    if any(not isinstance(name, str) or not _is_sha(digest)
           for name, digest in (outputs or {}).items()):
        raise ProductionDiagnosticRefusal("failure output inventory is invalid")
    encoded = str(error).encode("utf-8", errors="replace")
    bounded = encoded[:2048].decode("utf-8", errors="ignore")
    if not bounded:
        bounded = type(error).__qualname__[:2048]
    payload = {
        "schema": "entry-v2-orchestration-failure-v1", "status": "REFUSED",
        "phase": phase, "component": component, "layer": layer,
        "attempt_sha256": attempt_sha256,
        "error_type": f"{type(error).__module__}.{type(error).__qualname__}",
        "error_message": bounded,
        "error_message_sha256": _sha(bounded.encode()),
        "evidence_sha256": evidence_sha256,
        "outputs": dict(sorted((outputs or {}).items())),
        "cache_recovery": "NO_UNRECEIPTED_PROCESS_CACHE_REUSE",
        "h2_permit": False,
    }
    digest = _sha(_canonical(payload))
    _write_immutable(root / "failures" / f"{phase}.{component}.{digest}.json", payload)
    return digest


def _record_failure_without_masking(
    root: Path, *, phase: str, component: str,
    attempt_sha256: str | None, error: BaseException,
    layer: str, evidence_sha256: str | None = None,
    outputs: Mapping[str, str] | None = None,
) -> str | None:
    try:
        component_evidence = getattr(error, "component_evidence", None)
        if evidence_sha256 is None and isinstance(component_evidence, Mapping):
            evidence_raw = _canonical(component_evidence)
            evidence_sha256 = _sha(evidence_raw)
            _write_immutable(
                root / "evidence" / f"{layer}.{evidence_sha256}.json",
                dict(component_evidence),
            )
        return _persist_failure(
            root, phase=phase, component=component,
            attempt_sha256=attempt_sha256, error=error, layer=layer,
            evidence_sha256=evidence_sha256, outputs=outputs,
        )
    except BaseException as ledger_error:
        error.add_note(
            "typed failure receipt persistence also failed: "
            f"{type(ledger_error).__name__}: {ledger_error}"
        )
        return None


def _output_inventory(root: Path) -> Mapping[str, str]:
    candidates = [
        *(root / name for name in (
            "acceptance.json", "E1.json", "E2.json", "E3.json",
            "winner-adoption.json", "winner-integration.json",
            "held-rehearsal.json", "fit-only-rehearsal.json",
            "fit-only-reload.json", "E2-to-E3-reload.json",
            "E3-reload.json",
        )),
        *(root.glob("components/*.json")),
        *(root.glob("components/attempts/*.json")),
        *(root.glob("[0-9][0-9].*.json")),
        *(root.glob("attempts/*.json")),
        *(root.glob("held-boundaries/*.boundary/boundary.json")),
        *(root.glob("held-boundaries/*.evidence/evidence.json")),
        *(root.glob("timing/*.json")),
        *(root.glob("winner-bundle/manifest.json")),
    ]
    result: dict[str, str] = {}
    for path in sorted(set(candidates)):
        if path.is_file() and not path.is_symlink():
            result[path.relative_to(root).as_posix()] = _sha(path.read_bytes())
    return result


def _failure_layer(phase: str, component: str, error: BaseException) -> str:
    declared = getattr(error, "failure_layer", None)
    if declared is not None:
        if not isinstance(declared, str):
            raise ProductionDiagnosticRefusal("typed failure layer is not a string")
        return declared
    if phase == "ACCEPTANCE":
        return f"ACCEPTANCE:{component}"
    return {"E1": "E1:ENGINE", "E2": "E2:ENGINE", "E3": "E3:REPORT",
            "CHAIN": f"CHAIN:{component}", "LIFECYCLE": "LIFECYCLE:CLOSE",
            "FACTORY": "FACTORY:RESOURCE_LOAD"}.get(phase, f"CHAIN:{component}")


def _held_evidence_sha(root: Path, stage: str, error: BaseException) -> str | None:
    declared = getattr(error, "evidence_sha256", None)
    if declared is not None:
        if not _is_sha(declared):
            raise ProductionDiagnosticRefusal("typed held evidence identity is invalid")
        return declared
    if stage not in ("E1", "E2", "E3"):
        return None
    from .neural_sufficiency_stage_persistence import (
        StageBoundaryStore, StagePersistenceRefusal,
    )
    try:
        return StageBoundaryStore(root / "held-boundaries").load_evidence(
            stage
        ).evidence_sha256
    except StagePersistenceRefusal:
        return None


def _publish_e3_report_evidence(
    root: Path, result: ExactComponentExecution,
) -> str:
    """Persist a returned E3 report before any pass/economics decision."""
    from .neural_sufficiency_stage_persistence import StageBoundaryStore
    store = StageBoundaryStore(root / "held-boundaries")
    if store.evidence_path("E3").exists():
        return store.load_evidence("E3").evidence_sha256
    payload = {
        "schema": "entry-v2-e3-report-evidence-v1",
        "status": "REPORTED",
        "component": result.component,
        "provider_passed": result.passed,
        "fit_only": result.fit_only,
        "maximum_day": result.maximum_day,
        "result_artifact_sha256": result.result_artifact_sha256,
        "frozen_row_manifest_sha256": result.frozen_row_manifest_sha256,
        "details": dict(result.details),
        "h2_permit": False,
    }
    return store.publish_evidence("E3", {"report.json": _canonical(payload)})


def _validate_fit_only_rehearsal_gate(component_root: Path) -> tuple[str, str]:
    files = tuple(component_root.glob("[0-9][0-9].finalize.*.json"))
    if len(files) != 1:
        raise ProductionDiagnosticRefusal("fit-only held rehearsal finalizer is absent")
    try:
        component = json.loads(files[0].read_bytes())
        rehearsal = component["details"]["held_rehearsal"]
        declared = rehearsal["receipt_sha256"]
    except (KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProductionDiagnosticRefusal(
            "fit-only held rehearsal receipt is invalid"
        ) from exc
    core = dict(rehearsal); core.pop("receipt_sha256", None)
    g7 = rehearsal.get("g7")
    ceiling = g7.get("candidate_ceiling_receipts", {}) if isinstance(g7, Mapping) else {}
    status = rehearsal.get("status")
    e1r = rehearsal.get("e1r")
    e2r = rehearsal.get("e2r")
    screen = e1r.get("probe_screen", {}) if isinstance(e1r, Mapping) else {}
    arm_matrix = e2r.get("arm_head_matrix", {}) if isinstance(e2r, Mapping) else {}
    selected_path = (arm_matrix.get("winner")
                     or arm_matrix.get("diagnostic_path"))
    expected_learner_objective = (
        "A0_CURRENT_GROUPING"
        if isinstance(selected_path, str) and selected_path.startswith("C0:")
        else arm_matrix.get("selected_objective"))
    expected_paths = {f"{arm}:{head}" for arm in ("C0", "C1", "L0", "L1", "M1")
                      for head in ("direct_neural", "catboost")}
    expected_goal_receipts = {
        f"{stage}.{role}.{asset}"
        for stage in ("E1r", "E2r")
        for role in ("THRESHOLD", "FORWARD")
        for asset in ("HG", "NKD", "SI")
    }
    if (rehearsal.get("schema") != "entry-v2-fit-only-held-rehearsal-v1"
            or status not in {"PASS", "NO_FIT_ONLY_DEPLOYABLE_DEPTH"}
            or rehearsal.get("minimum_oracle_capture")
                != FIT_ONLY_MIN_ORACLE_CAPTURE
            or rehearsal.get("fit_only_max_d8") != 20210930
            or rehearsal.get("no_held_labels") is not True
            or type(rehearsal.get("held_launch_permitted")) is not bool
            or (status == "PASS") != rehearsal.get("held_launch_permitted")
            or not isinstance(e1r, Mapping)
            or not isinstance(e2r, Mapping)
            or len(screen.get("ledger", {})) != 44
            or set(arm_matrix.get("matrix", {})) != expected_paths
            or not _is_sha(declared) or _sha(_canonical(core)) != declared
            or not isinstance(g7, Mapping)
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
            or set(ceiling) != {"E1r.THRESHOLD", "E1r.FORWARD",
                               "E2r.THRESHOLD", "E2r.FORWARD"}
            or any(not _is_sha(value) for value in ceiling.values())):
        raise ProductionDiagnosticRefusal("fit-only held rehearsal launch gate differs")
    if status == "PASS" and not (
            g7["all_asset_in_sample"] and g7["all_asset_disjoint_forward"]
            and g7["goal_recovery_all_blocks"]):
        raise ProductionDiagnosticRefusal(
            "fit-only PASS lacks all-asset threshold/forward feasibility")
    try:
        current_source_tree = held_rehearsal_source_tree_sha256()
    except HeldSourceManifestRefusal as exc:
        raise ProductionDiagnosticRefusal(
            "held rehearsal source manifest cannot be verified"
        ) from exc
    if rehearsal.get("source_tree_sha256") != current_source_tree:
        raise ProductionDiagnosticRefusal(
            "fit-only held rehearsal belongs to different source bytes"
        )
    return declared, str(status)


def _load_fit_only_orchestration_boundary(
    root: Path, *, acceptance_sha256: str,
    diagnostic_evidence_sha256: str,
) -> Mapping[str, Any]:
    """Load proof that a prior invocation stopped before held E1."""
    path = root / "fit-only-rehearsal.json"
    if not path.is_file() or path.is_symlink() or path.stat().st_mode & 0o222:
        raise ProductionDiagnosticRefusal(
            "prior fit-only invocation boundary is absent or mutable")
    try:
        value = json.loads(path.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProductionDiagnosticRefusal(
            "prior fit-only invocation boundary is invalid") from exc
    core = dict(value) if isinstance(value, dict) else {}
    declared = core.pop("receipt_sha256", None)
    if (value.get("schema") != "entry-v2-fit-only-orchestration-rehearsal-v2"
            or value.get("status") not in {
                "PASS", "NO_FIT_ONLY_DEPLOYABLE_DEPTH"}
            or value.get("held_launch_permitted")
                != (value.get("status") == "PASS")
            or value.get("h2_permit") is not False
            or value.get("maximum_d8") != ACCEPTANCE_FIT_END
            or value.get("acceptance_sha256") != acceptance_sha256
            or value.get("diagnostic_evidence_sha256")
                != diagnostic_evidence_sha256
            or not _is_sha(value.get("fit_only_rehearsal_sha256"))
            or value.get("held_stage_started") is not False
            or value.get("mandatory_process_stop") is not True
            or value.get("strict_second_process_reload_required") is not True
            or not _is_sha(value.get("producer_process_identity_sha256"))
            or declared != _sha(_canonical(core))):
        raise ProductionDiagnosticRefusal(
            "prior fit-only invocation boundary differs")
    return value


def _current_process_identity_sha256() -> str:
    """Bind a launch boundary to one Linux process incarnation.

    PID alone is reusable.  Linux boot identity plus `/proc/self/stat`
    starttime distinguishes a later process even when the numeric PID is
    recycled.  A platform that cannot prove this identity may not authorize
    held labels.
    """
    try:
        boot_id = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        stat = Path("/proc/self/stat").read_text().strip()
        close = stat.rfind(")")
        fields = stat[close + 2:].split()
        start_ticks = int(fields[19])
    except (OSError, ValueError, IndexError) as exc:
        raise ProductionDiagnosticRefusal(
            "process incarnation identity cannot be proven") from exc
    if not boot_id or start_ticks <= 0:
        raise ProductionDiagnosticRefusal(
            "process incarnation identity is incomplete")
    return _sha(_canonical({
        "schema": "entry-v2-linux-process-incarnation-v1",
        "boot_id": boot_id,
        "pid": os.getpid(),
        "start_ticks": start_ticks,
    }))


class ProductionDiagnosticBackends:
    def __init__(self, executor: ExactNeuralDiagnosticExecutor, *,
                 artifact_root: str | Path, context: RunContext,
                 invocation_start_ns: int | None = None) -> None:
        self.executor = executor
        self.root = Path(artifact_root)
        self.context = context
        self._position = 0
        self._parent_sha256 = "0" * 64
        self._closed = False
        self.timing = NonSemanticTimingLedger(
            self._run_root() / "timing", segment_start_ns=invocation_start_ns)

    def _run_root(self) -> Path:
        return self.root.parent if self.root.name == "components" else self.root

    def resume_finalized_chain(self) -> None:
        files = sorted(self.root.glob("[0-9][0-9].*.json"))
        if len(files) != len(ACCEPTANCE_COMPONENTS):
            raise ProductionDiagnosticRefusal("restart component chain is incomplete")
        parent = "0" * 64
        for position, (path, component) in enumerate(zip(files, ACCEPTANCE_COMPONENTS)):
            raw = path.read_bytes(); payload = json.loads(raw)
            digest = _sha(raw)
            if (payload.get("position") != position or payload.get("component") != component
                    or payload.get("parent_sha256") != parent
                    or payload.get("one_load_id") != self.context.one_load_id
                    or digest not in path.name):
                raise ProductionDiagnosticRefusal("restart component chain differs")
            parent = digest
        self._position = len(files); self._parent_sha256 = parent

    def _persist(self, component: str, result: ExactComponentExecution) -> GateEvidence:
        expected = ACCEPTANCE_COMPONENTS[self._position]
        if component != expected or result.component != component:
            raise ProductionDiagnosticRefusal(
                f"component order/result mismatch: expected {expected}, got {component}"
            )
        if (type(result) is not ExactComponentExecution or not result.passed
                or not result.fit_only or result.maximum_day > ACCEPTANCE_FIT_END):
            raise ProductionDiagnosticRefusal(f"{component} exact execution did not pass fit-only")
        for label, digest in (("result artifact", result.result_artifact_sha256),
                              ("row manifest", result.frozen_row_manifest_sha256)):
            if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
                raise ProductionDiagnosticRefusal(f"{component} {label} is invalid")
        payload = {
            "schema": "entry-v2-production-diagnostic-component-v1",
            "component": component, "position": self._position,
            "parent_sha256": self._parent_sha256,
            "one_load_id": self.context.one_load_id,
            "corpus_sha256": self.context.corpus_sha256,
            "chronology_sha256": self.context.chronology_sha256,
            "maximum_day": result.maximum_day, "fit_only": result.fit_only,
            "frozen_row_manifest_sha256": result.frozen_row_manifest_sha256,
            "result_artifact_sha256": result.result_artifact_sha256,
            "details": dict(result.details),
        }
        raw = _canonical(payload); digest = _sha(raw)
        path = self.root / f"{self._position:02d}.{component}.{digest}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(path, "xb") as stream:
                stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        except FileExistsError:
            if path.read_bytes() != raw:
                raise ProductionDiagnosticRefusal("immutable component artifact differs")
        os.chmod(path, 0o444)
        self._position += 1; self._parent_sha256 = digest
        details = dict(result.details)
        details["_visible_max_day"] = result.maximum_day
        details["_frozen_row_manifest_sha256"] = result.frozen_row_manifest_sha256
        return GateEvidence(component, True, True, True, result.maximum_day,
                            digest, details)

    def _run(self, component: str) -> GateEvidence:
        attempt = _attempt_payload(
            phase="ACCEPTANCE", component=component, context=self.context,
            position=self._position, parent_sha256=self._parent_sha256,
        )
        attempt_sha = _sha(_canonical(attempt))
        _write_immutable(self.root / "attempts" /
                         f"{self._position:02d}.{component}.{attempt_sha}.json", attempt)
        try:
            if component == "one_load": result = self.executor.prepare()
            elif component == "raw_fidelity": result = self.executor.raw_fidelity()
            elif component.startswith("arm_"):
                result = self.executor.train_and_rehearse_arm(
                    component.removeprefix("arm_"))
            elif component == "atlas_probe_loss": result = self.executor.run_atlas()
            elif component == "direct_head": result = self.executor.run_direct_head()
            elif component == "catboost": result = self.executor.run_catboost()
            elif component == "mapper": result = self.executor.fit_mapper()
            elif component == "calibration": result = self.executor.calibrate()
            elif component == "threshold": result = self.executor.select_threshold_with_canonical_sweep()
            elif component == "canonical_replay": result = self.executor.run_canonical_replay()
            elif component == "fit_ledger": result = self.executor.validate_fit_ledger()
            elif component == "finalize": result = self.executor.finalize()
            else: raise ProductionDiagnosticRefusal(f"unknown exact component {component}")
            evidence = self._persist(component, result)
            if component == "raw_fidelity":
                self.timing.record("first_competence")
            return evidence
        except BaseException as exc:
            _record_failure_without_masking(
                self.root, phase="ACCEPTANCE", component=component,
                attempt_sha256=attempt_sha, error=exc,
                layer=_failure_layer("ACCEPTANCE", component, exc),
                outputs=_output_inventory(self._run_root()))
            raise

    def callbacks(self) -> Mapping[str, Any]:
        callbacks: dict[str, Any] = {}
        for component in ACCEPTANCE_COMPONENTS:
            def callback(_context: RunContext, name: str = component) -> GateEvidence:
                if _context != self.context:
                    raise ProductionDiagnosticRefusal("runner/executor context differs")
                return self._run(name)
            callback.__name__ = f"entry_v2_production_{component}"
            callbacks[component] = callback
        return callbacks

    def held_callback(self, mode: str, *, acceptance_sha256: str,
                      prior_stage_sha256: str,
                      diagnostic_evidence_sha256: str | None = None,
                      ) -> Mapping[str, Any]:
        component = f"execute_{mode.lower()}"
        if mode not in ("E1", "E2", "E3") or self._position != len(ACCEPTANCE_COMPONENTS):
            raise ProductionDiagnosticRefusal("held execution requires finalized acceptance")
        def callback(_context: RunContext) -> GateEvidence:
            if _context != self.context:
                raise ProductionDiagnosticRefusal("runner/executor held context differs")
            attempt = _attempt_payload(
                phase=mode, component=component, context=self.context,
                position=None, parent_sha256=prior_stage_sha256,
                acceptance_sha256=acceptance_sha256,
                prior_stage_sha256=prior_stage_sha256,
            )
            attempt_sha = _sha(_canonical(attempt))
            _write_immutable(self.root / "attempts" /
                             f"held.{mode}.{attempt_sha}.json", attempt)
            try:
                result = self.executor.execute_stage(mode, acceptance_sha256,
                                                     prior_stage_sha256)
                if mode == "E3" and type(result) is ExactComponentExecution:
                    _publish_e3_report_evidence(self._run_root(), result)
            except BaseException as exc:
                _record_failure_without_masking(
                    self.root, phase=mode, component=component,
                    attempt_sha256=attempt_sha, error=exc,
                    layer=_failure_layer(mode, component, exc),
                    evidence_sha256=_held_evidence_sha(self._run_root(), mode, exc),
                    outputs=_output_inventory(self._run_root()))
                raise
            try:
                if (type(result) is not ExactComponentExecution
                        or result.component != component or not result.passed
                        or result.fit_only):
                    raise ProductionDiagnosticRefusal("held executor returned a weak result")
                if any(len(value) != 64 or any(c not in "0123456789abcdef" for c in value)
                       for value in (result.result_artifact_sha256,
                                     result.frozen_row_manifest_sha256)):
                    raise ProductionDiagnosticRefusal(
                        "held executor artifact binding is invalid")
                details = dict(result.details)
                if diagnostic_evidence_sha256 is not None:
                    details["diagnostic_evidence_sha256"] = (
                        diagnostic_evidence_sha256)
                details["_result_artifact_sha256"] = result.result_artifact_sha256
                details["_visible_max_day"] = result.maximum_day
                details["_frozen_row_manifest_sha256"] = result.frozen_row_manifest_sha256
                raw = _canonical({"component": component,
                                  "parent_sha256": prior_stage_sha256,
                                  "acceptance_sha256": acceptance_sha256,
                                  "details": details})
                digest = _sha(raw)
                path = self.root / f"held.{component}.{digest}.json"
                try:
                    with open(path, "xb") as stream:
                        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
                except FileExistsError:
                    if path.read_bytes() != raw:
                        raise ProductionDiagnosticRefusal(
                            "held artifact differs on restart")
                os.chmod(path, 0o444)
                return GateEvidence(component, True, True, False,
                                    result.maximum_day, digest, details)
            except BaseException as exc:
                _record_failure_without_masking(
                    self.root, phase=mode, component=component,
                    attempt_sha256=attempt_sha, error=exc,
                    layer=_failure_layer(mode, component, exc),
                    evidence_sha256=_held_evidence_sha(self._run_root(), mode, exc),
                    outputs=_output_inventory(self._run_root()))
                raise
        callback.__name__ = f"entry_v2_production_{component}"
        return {component: callback}

    def record_corpus_ready(self) -> None:
        self.timing.record(
            "corpus_ready", provenance=self.executor.timing_provenance())

    def record_resumed_competence(self) -> None:
        self.timing.record("first_competence")

    def record_boundary(self, stage: str) -> None:
        self.timing.record(f"{stage.lower()}_boundary")

    def record_complete_pre_h2(self) -> None:
        self.timing.record("complete_pre_h2")

    def close(self, adoption_sha256: str | None) -> None:
        if self._closed:
            raise ProductionDiagnosticRefusal("one-load executor closed twice")
        legacy_close = getattr(self.executor, "close", None)
        chain_close = getattr(self.executor, "close_after_chain", None)
        if callable(chain_close):
            chain_close()
            result = ExactComponentExecution(
                "close", True, False, ACCEPTANCE_FIT_END,
                _sha(_canonical({"adoption_sha256": adoption_sha256,
                                 "resources_closed": True})), "0" * 64,
                {"resources_closed": True, "adoption_sha256": adoption_sha256},
            )
        elif callable(legacy_close):
            result = legacy_close(adoption_sha256)
        else:
            raise ProductionDiagnosticRefusal("executor lacks one-load lifecycle close")
        if (type(result) is not ExactComponentExecution or result.component != "close"
                or not result.passed or result.details.get("resources_closed") is not True):
            raise ProductionDiagnosticRefusal("executor did not close the one-load resources")
        raw = _canonical({"component": "close", "adoption_sha256": adoption_sha256,
                          "result_artifact_sha256": result.result_artifact_sha256,
                          "details": dict(result.details)})
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / f"lifecycle.close.{_sha(raw)}.json"
        try:
            with open(path, "xb") as stream:
                stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        except FileExistsError:
            if path.read_bytes() != raw:
                raise ProductionDiagnosticRefusal("close artifact differs")
        os.chmod(path, 0o444); self._closed = True


def derive_production_context(*, corpus_receipt: Mapping[str, Any],
                              chronology: Mapping[str, Any], one_load_id: str,
                              source_paths: tuple[str, ...],
                              available_host_gib: float) -> RunContext:
    """Derive identities from loaded receipts; callers cannot supply hashes."""
    if not one_load_id or not chronology:
        raise ProductionDiagnosticRefusal("production chronology/one-load identity is empty")
    corpus_hash = corpus_receipt.get("semantic_identity_sha256")
    if not _is_sha(corpus_hash):
        raise ProductionDiagnosticRefusal(
            "production corpus lacks its cold/warm-invariant semantic identity")
    chronology_hash = _sha(_canonical(dict(chronology)))
    try:
        corpus_max_day = int(chronology["corpus_max_day"])
        opened_through_day = int(chronology["opened_through_day"])
    except (KeyError, TypeError, ValueError) as error:
        raise ProductionDiagnosticRefusal("chronology lacks physical corpus/open bounds") from error
    return RunContext(corpus_max_day, opened_through_day, source_paths,
                      float(available_host_gib), corpus_hash, chronology_hash,
                      one_load_id)


def run_production_chain(executor: ExactNeuralDiagnosticExecutor, context: RunContext,
                         *, run_root: str | Path,
                         _stop_after_fit_only_rehearsal: bool = False,
                         _stop_after_held_rehearsal: bool = False,
                         _invocation_start_ns: int | None = None,
                         ) -> Mapping[str, str]:
    root = Path(run_root); backend = ProductionDiagnosticBackends(
        executor, artifact_root=root / "components", context=context,
        invocation_start_ns=_invocation_start_ns,
    )
    acceptance_path = root / "acceptance.json"
    adoption_sha256: str | None = None
    winner_resources: Any | None = None
    active_phase = "BOOTSTRAP"
    active_error: BaseException | None = None
    try:
      from .neural_sufficiency_stage_persistence import StageBoundaryStore
      boundary_store = StageBoundaryStore(root / "held-boundaries")
      process_identity_sha256 = _current_process_identity_sha256()
      bind_store = getattr(executor, "bind_stage_boundary_store", None)
      if not callable(bind_store):
          raise ProductionDiagnosticRefusal(
              "executor cannot persist immutable numerical stage boundaries")
      bind_store(boundary_store)
      # The resource factory has already returned the exact diagnostic stage.
      # Record corpus readiness here, before one_load validation or numerical
      # restart work, so the corpus ceiling measures the boundary named by its
      # provenance.  Subsequent competence ceilings are measured from this
      # milestone rather than from process start.
      backend.record_corpus_ready()
      fresh_acceptance = not acceptance_path.exists()
      prior_fit_only_boundary: Mapping[str, Any] | None = None
      m8_reload_proof_sha256: str | None = None
      if not fresh_acceptance:
          acceptance = load_acceptance_receipt(
              acceptance_path,
              allow_diagnostic_fail=_stop_after_fit_only_rehearsal)
          prior_fit_only_boundary = _load_fit_only_orchestration_boundary(
              root,
              acceptance_sha256=acceptance.acceptance_sha256,
              diagnostic_evidence_sha256=acceptance.diagnostic_evidence_sha256,
          )
          if prior_fit_only_boundary[
                  "producer_process_identity_sha256"] == process_identity_sha256:
              raise ProductionDiagnosticRefusal(
                  "held E1 requires a later OS process after fit-only rehearsal")
          backend.resume_finalized_chain()
          resume = getattr(executor, "resume_stage_boundaries", None)
          if not callable(resume):
              raise ProductionDiagnosticRefusal(
                  "executor cannot restore immutable numerical stage boundaries")
          m8_reload_proof_sha256 = resume(boundary_store, acceptance)
          if not _is_sha(m8_reload_proof_sha256):
              raise ProductionDiagnosticRefusal(
                  "fit-only M8 learner was not strict-reloaded")
          backend.record_resumed_competence()
      else:
          active_phase = "ACCEPTANCE"
          acceptance = run_neural_sufficiency(
        "preheld-fit-only-acceptance", context, backend.callbacks(),
        output_path=acceptance_path, production=True,
          )
      fit_only_rehearsal_sha256, fit_only_rehearsal_status = \
          _validate_fit_only_rehearsal_gate(
          backend.root
          )
      if acceptance.status != fit_only_rehearsal_status:
          raise ProductionDiagnosticRefusal(
              "acceptance/rehearsal diagnostic status differs")
      if fresh_acceptance:
          rehearsal_core = {
              "schema": "entry-v2-fit-only-orchestration-rehearsal-v2",
              "status": fit_only_rehearsal_status,
              "held_launch_permitted": fit_only_rehearsal_status == "PASS",
              "h2_permit": False,
              "maximum_d8": ACCEPTANCE_FIT_END,
              "acceptance_sha256": acceptance.acceptance_sha256,
              "diagnostic_evidence_sha256":
                  acceptance.diagnostic_evidence_sha256,
              "fit_only_rehearsal_sha256": fit_only_rehearsal_sha256,
              "held_stage_started": False,
              "mandatory_process_stop": True,
              "strict_second_process_reload_required": True,
              "producer_process_identity_sha256": process_identity_sha256,
          }
          rehearsal_sha = _sha(_canonical(rehearsal_core))
          rehearsal = {
              **rehearsal_core, "receipt_sha256": rehearsal_sha,
          }
          path = root / "fit-only-rehearsal.json"
          _write_immutable(path, rehearsal)
          backend.timing.record("fit_only_rehearsal_total")
          return {
              "fit_only_rehearsal": str(path),
              "fit_only_rehearsal_sha256": rehearsal_sha,
              "status": fit_only_rehearsal_status,
          }
      if not (prior_fit_only_boundary is not None):
          raise ProductionDiagnosticRefusal(
              "internal invariant failed: prior_fit_only_boundary is not None")
      if (prior_fit_only_boundary["status"] != fit_only_rehearsal_status
              or prior_fit_only_boundary["fit_only_rehearsal_sha256"]
                  != fit_only_rehearsal_sha256):
          raise ProductionDiagnosticRefusal(
              "fit-only boundary was not strict-reloaded by a later process")
      reload_core = {
          "schema": "entry-v2-fit-only-strict-reload-v1",
          "status": fit_only_rehearsal_status,
          "acceptance_sha256": acceptance.acceptance_sha256,
          "diagnostic_evidence_sha256": acceptance.diagnostic_evidence_sha256,
          "fit_only_boundary_sha256": prior_fit_only_boundary["receipt_sha256"],
          "m8_reload_proof_sha256": m8_reload_proof_sha256,
          "producer_process_identity_sha256":
              prior_fit_only_boundary["producer_process_identity_sha256"],
          "consumer_process_identity_sha256": process_identity_sha256,
          "separate_process_strict_reload": True,
          "held_stage_started": False,
          "h2_permit": False,
      }
      reload_receipt = {**reload_core,
                        "receipt_sha256": _sha(_canonical(reload_core))}
      _write_immutable(root / "fit-only-reload.json", reload_receipt)
      if _stop_after_fit_only_rehearsal:
          return {
              "fit_only_rehearsal": str(root / "fit-only-rehearsal.json"),
              "fit_only_rehearsal_sha256":
                  prior_fit_only_boundary["receipt_sha256"],
              "fit_only_reload": str(root / "fit-only-reload.json"),
              "fit_only_reload_sha256": reload_receipt["receipt_sha256"],
              "status": fit_only_rehearsal_status,
          }
      if fit_only_rehearsal_status != "PASS":
          raise ProductionDiagnosticRefusal(
              "fit-only diagnostic did not authorize held E1")
      e1_path = root / "E1.json"
      active_phase = "E1"
      e1 = (load_stage_receipt(e1_path) if e1_path.exists() else run_neural_sufficiency(
        "E1", context, backend.held_callback(
            "E1", acceptance_sha256=acceptance.acceptance_sha256,
            prior_stage_sha256=acceptance.acceptance_sha256,
            diagnostic_evidence_sha256=acceptance.diagnostic_evidence_sha256),
        output_path=e1_path, acceptance_receipt_path=acceptance_path,
        production=True,
      ))
      if not boundary_store.path("E1").exists():
          raise ProductionDiagnosticRefusal("E1 numerical boundary was not persisted")
      backend.record_boundary("E1")
      e2_path = root / "E2.json"
      active_phase = "E2"
      e2 = (load_stage_receipt(e2_path) if e2_path.exists() else run_neural_sufficiency(
        "E2", context, backend.held_callback(
            "E2", acceptance_sha256=acceptance.acceptance_sha256,
            prior_stage_sha256=e1.stage_sha256,
            diagnostic_evidence_sha256=acceptance.diagnostic_evidence_sha256),
        output_path=e2_path, acceptance_receipt_path=acceptance_path,
        prior_stage_receipt_path=e1_path, production=True,
      ))
      if not boundary_store.path("E2").exists():
          raise ProductionDiagnosticRefusal("E2 numerical boundary was not persisted")
      backend.record_boundary("E2")
      e2_boundary = boundary_store.load(
          "E2", expected_acceptance_sha256=acceptance.acceptance_sha256)
      e2_reload_proof = resume(boundary_store, acceptance)
      if e2_reload_proof != m8_reload_proof_sha256:
          raise ProductionDiagnosticRefusal(
              "E2 discard/reload changed the frozen fit-only learner proof")
      e2_reload_core = {
          "schema": "entry-v2-e2-to-e3-strict-reload-v1",
          "acceptance_sha256": acceptance.acceptance_sha256,
          "e2_stage_sha256": e2.stage_sha256,
          "e2_boundary_sha256": e2_boundary.boundary_sha256,
          "m8_reload_proof_sha256": e2_reload_proof,
          "discarded_live_selection_state": True,
          "strict_loaded_before_e3": True,
          "h2_permit": False,
      }
      _write_immutable(root / "E2-to-E3-reload.json", {
          **e2_reload_core,
          "receipt_sha256": _sha(_canonical(e2_reload_core)),
      })
      e3_path = root / "E3.json"
      active_phase = "E3"
      e3 = (load_stage_receipt(e3_path) if e3_path.exists() else run_neural_sufficiency(
        "E3", context, backend.held_callback(
            "E3", acceptance_sha256=acceptance.acceptance_sha256,
            prior_stage_sha256=e2.stage_sha256,
            diagnostic_evidence_sha256=acceptance.diagnostic_evidence_sha256),
        output_path=e3_path, acceptance_receipt_path=acceptance_path,
        prior_stage_receipt_path=e2_path, production=True,
      ))
      if not boundary_store.path("E3").exists():
          raise ProductionDiagnosticRefusal("E3 numerical boundary was not persisted")
      backend.record_boundary("E3")
      e3_reload_proof = resume(boundary_store, acceptance)
      if e3_reload_proof != m8_reload_proof_sha256:
          raise ProductionDiagnosticRefusal(
              "E3 strict reload changed the frozen fit-only learner proof")
      restored_kind = getattr(
          getattr(e2_boundary.public_result, "confirmation", None),
          "decision_kind", None)
      restored_factory_name = {
          "direct_neural": "entry_v2_selected_direct_policy_factory",
          "catboost": "entry_v2_selected_catboost_policy_factory",
      }.get(restored_kind)
      restored_factory = (getattr(executor.provider, restored_factory_name, None)
                          if hasattr(executor, "provider")
                          and restored_factory_name is not None else None)
      e3_boundary = boundary_store.load(
          "E3", expected_acceptance_sha256=acceptance.acceptance_sha256,
          policy_factory=restored_factory,
      )
      e3_reload_core = {
          "schema": "entry-v2-e3-report-strict-reload-v1",
          "acceptance_sha256": acceptance.acceptance_sha256,
          "e3_stage_sha256": e3.stage_sha256,
          "e3_boundary_sha256": e3_boundary.boundary_sha256,
          "m8_reload_proof_sha256": e3_reload_proof,
          "strict_loaded_after_report": True,
          "h2_permit": False,
      }
      _write_immutable(root / "E3-reload.json", {
          **e3_reload_core,
          "receipt_sha256": _sha(_canonical(e3_reload_core)),
      })
      e1_boundary = boundary_store.load(
          "E1", expected_acceptance_sha256=acceptance.acceptance_sha256)
      if (e2_boundary.parent_boundary_sha256 != e1_boundary.boundary_sha256
              or e1.acceptance_sha256 != acceptance.acceptance_sha256
              or e2.prior_stage_sha256 != e1.stage_sha256
              or e3.prior_stage_sha256 != e2.stage_sha256):
          raise ProductionDiagnosticRefusal(
              "held orchestration rehearsal chain differs")
      held_reasons = e3_boundary.execution.details.get("held_reasons_by_asset")
      if (e3.status not in {"PASS", "FAIL"}
              or not isinstance(held_reasons, Mapping)
              or set(held_reasons) != {"HG", "NKD", "SI"}
              or (e3.status == "PASS" and any(held_reasons.values()))
              or (e3.status == "FAIL" and not any(held_reasons.values()))):
          raise ProductionDiagnosticRefusal(
              "held E3 status/reasons are not measured and typed")
      rehearsal_core = {
          "schema": "entry-v2-held-orchestration-rehearsal-v2",
          "status": e3.status,
          "adoption_permitted": e3.status == "PASS",
          "held_reasons_by_asset": dict(held_reasons),
          "h2_permit": False,
          "acceptance_sha256": acceptance.acceptance_sha256,
          "e1_stage_sha256": e1.stage_sha256,
          "e2_stage_sha256": e2.stage_sha256,
          "e3_stage_sha256": e3.stage_sha256,
          "e1_boundary_sha256": e1_boundary.boundary_sha256,
          "e2_boundary_sha256": e2_boundary.boundary_sha256,
          "e3_boundary_sha256": e3_boundary.boundary_sha256,
          "e3_boundary_present": True,
          "e2_reloaded_before_e3": True,
          "e3_reloaded_after_report": True,
          "attempt_ledgers_persisted_before_execution": True,
          "typed_failure_receipts_enabled": True,
      }
      rehearsal_sha = _sha(_canonical(rehearsal_core))
      rehearsal = {**rehearsal_core, "receipt_sha256": rehearsal_sha}
      _write_immutable(root / "held-rehearsal.json", rehearsal)
      backend.timing.record("held_rehearsal_total")
      if _stop_after_held_rehearsal or e3.status == "FAIL":
          return {"held_rehearsal": str(root / "held-rehearsal.json"),
                  "held_rehearsal_sha256": rehearsal_sha,
                  "status": e3.status}
      active_phase = "ADOPTION"
      winner_path = root / "winner-adoption.json"
      winner = adopt_e3_winner(
        acceptance_receipt_path=acceptance_path, e1_receipt_path=e1_path,
        e2_receipt_path=e2_path, e3_receipt_path=e3_path, output_path=winner_path,
    )
      adoption_sha256 = winner.adoption_sha256
      # Adoption is not complete until the held standard E3 fold, exact model
      # bytes and SAME live one-open owner have crossed into E4--E8.  Every
      # method below is concrete and intentionally fail-closed on a fit-only
      # provider that has not produced real held artifacts.
      payloads = executor.export_winner_bundle_payloads(adoption_sha256)
      primary_e3_fold = Path(executor.export_primary_e3_fold(adoption_sha256)).resolve()
      from .fold_store import (
          fold_store_aggregate_sha256, load_fold, release_fold,
      )
      e3_fold_probe = load_fold(primary_e3_fold)
      try:
          primary_e3_fold_sha256 = fold_store_aggregate_sha256(primary_e3_fold)
          if e3_fold_probe.store_aggregate_sha256 != primary_e3_fold_sha256:
              raise ProductionDiagnosticRefusal(
                  "loaded primary E3 store identity differs"
              )
      finally:
          release_fold(e3_fold_probe)
      winner_resources = executor.transfer_winner_resources(adoption_sha256)
      if getattr(winner_resources, "ownership_transferred", None) is not True:
          raise ProductionDiagnosticRefusal("one-load winner ownership did not transfer")
      from . import common as C
      from .neural_winner_artifact import (
          publish_winner_bundle, publish_winner_integration,
      )
      arm_payload = json.loads(payloads["arm.json"])
      objective_payload = json.loads(payloads["objective.json"])
      stage = winner_resources.context_corpus(C.CACHE_ROOT)
      binding = stage.corpus.model_input_binding
      bundle_path = root / "winner-bundle"
      bundle = publish_winner_bundle(
          bundle_path, adoption_receipt_path=winner_path,
          arm=str(arm_payload["arm"]),
          architecture=dict(arm_payload["architecture"]),
          objective=dict(objective_payload), model_input_binding=binding,
          payloads=payloads, primary_e3_fold_sha256=primary_e3_fold_sha256,
      )
      integration_path = root / "winner-integration.json"
      integration = publish_winner_integration(
          integration_path, pending_adoption_path=winner_path,
          winner_bundle_path=bundle_path, resources=winner_resources,
      )
      from .production_driver import DriverPlan, run_pre_h2_campaign
      from .production_runtime import build_production_runtime
      forward_root = root / "forward"
      runtime = build_production_runtime(C.CACHE_ROOT,
                                         winner_resources=winner_resources,
                                         winner_bundle=bundle)
      forward = run_pre_h2_campaign(DriverPlan(
          forward_root, prebuilt_substrate_root=C.CACHE_ROOT,
          neural_acceptance_receipt=acceptance_path,
          neural_e1_receipt=e1_path, neural_e2_receipt=e2_path,
          neural_e3_receipt=e3_path,
          neural_winner_adoption_receipt=winner_path,
          neural_winner_bundle=bundle_path,
          neural_winner_integration_receipt=integration_path,
          adopted_primary_e3_fold=primary_e3_fold,
      ), runtime)
      backend.record_complete_pre_h2()
      return {"acceptance": str(acceptance_path), "E1": str(e1_path),
              "E2": str(e2_path), "E3": str(e3_path),
              "winner_adoption": str(winner_path),
              "winner_adoption_sha256": winner.adoption_sha256,
              "winner_bundle": str(bundle_path),
              "winner_bundle_sha256": bundle.bundle_sha256,
              "winner_integration": str(integration_path),
              "winner_integration_sha256": integration.integration_sha256,
              "forward_campaign_sha256":
                  forward.campaign.receipt["receipt_sha256"]}
    except BaseException as exc:
      active_error = exc
      _record_failure_without_masking(
          root, phase="CHAIN", component=active_phase,
          attempt_sha256=None, error=exc,
          layer=_failure_layer("CHAIN", active_phase, exc),
          evidence_sha256=_held_evidence_sha(root, active_phase, exc),
          outputs=_output_inventory(root),
      )
      raise
    finally:
      try:
          if winner_resources is None:
              backend.close(adoption_sha256)
          else:
              close = getattr(winner_resources, "close", None)
              if not callable(close):
                  raise ProductionDiagnosticRefusal(
                      "transferred winner owner lacks physical close")
              close()
      except BaseException as close_error:
          _record_failure_without_masking(
              root, phase="LIFECYCLE", component="close",
              attempt_sha256=None, error=close_error,
              layer=_failure_layer("LIFECYCLE", "close", close_error),
              outputs=_output_inventory(root),
          )
          if active_error is None:
              raise


def run_held_orchestration_rehearsal(
    executor: ExactNeuralDiagnosticExecutor, context: RunContext, *,
    run_root: str | Path,
) -> Mapping[str, str]:
    """Exercise exact acceptance -> E1 -> E2 -> E3 and stop before adoption."""
    return run_production_chain(
        executor, context, run_root=run_root, _stop_after_held_rehearsal=True,
    )


def run_fit_only_learning_rehearsal(
    executor: ExactNeuralDiagnosticExecutor, context: RunContext, *,
    run_root: str | Path,
) -> Mapping[str, str]:
    """Run the real fit-only learner gate and stop before held E1 is opened."""
    return run_production_chain(
        executor, context, run_root=run_root,
        _stop_after_fit_only_rehearsal=True,
    )


def load_held_orchestration_rehearsal(path: str | Path) -> Mapping[str, Any]:
    target = Path(path)
    if not target.is_file() or target.stat().st_mode & 0o222:
        raise ProductionDiagnosticRefusal("held rehearsal receipt is absent/mutable")
    try:
        value = json.loads(target.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProductionDiagnosticRefusal("held rehearsal receipt is invalid") from exc
    if not isinstance(value, dict):
        raise ProductionDiagnosticRefusal("held rehearsal receipt is not an object")
    core = dict(value); declared = core.pop("receipt_sha256", None)
    sha_fields = ("acceptance_sha256", "e1_stage_sha256", "e2_stage_sha256",
                  "e3_stage_sha256", "e1_boundary_sha256", "e2_boundary_sha256",
                  "e3_boundary_sha256")
    reasons = value.get("held_reasons_by_asset")
    if (value.get("schema") != "entry-v2-held-orchestration-rehearsal-v2"
            or value.get("status") not in {"PASS", "FAIL"}
            or value.get("adoption_permitted") != (value.get("status") == "PASS")
            or not isinstance(reasons, Mapping)
            or set(reasons) != {"HG", "NKD", "SI"}
            or (value.get("status") == "PASS" and any(reasons.values()))
            or (value.get("status") == "FAIL" and not any(reasons.values()))
            or value.get("h2_permit") is not False
            or value.get("e3_boundary_present") is not True
            or value.get("e2_reloaded_before_e3") is not True
            or value.get("e3_reloaded_after_report") is not True
            or value.get("attempt_ledgers_persisted_before_execution") is not True
            or value.get("typed_failure_receipts_enabled") is not True
            or any(not isinstance(value.get(key), str)
                   or len(value[key]) != 64 for key in sha_fields)
            or declared != _sha(_canonical(core))):
        raise ProductionDiagnosticRefusal("held rehearsal gate differs")
    return value


def main(argv: list[str] | None = None) -> int:
    invocation_start_ns = time.monotonic_ns()
    parser = argparse.ArgumentParser(description="Run exact Entry V2 neural acceptance→E3")
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--executor-factory", required=True,
                        help="module:function returning (ExactNeuralDiagnosticExecutor, RunContext)")
    parser.add_argument(
        "--fit-only-rehearsal", action="store_true",
        help="stop after the real <=2021-09-30 learnability/economics gate",
    )
    args = parser.parse_args(argv)
    try:
        module_name, function_name = args.executor_factory.split(":", 1)
        factory = getattr(importlib.import_module(module_name), function_name)
        executor, context = factory(args.run_root)
    except Exception as error:
        _record_failure_without_masking(
            Path(args.run_root), phase="FACTORY", component="resource_load",
            attempt_sha256=None, error=error,
            layer=_failure_layer("FACTORY", "resource_load", error),
            outputs=_output_inventory(Path(args.run_root)),
        )
        raise ProductionDiagnosticRefusal("exact executor factory could not be loaded") from error
    result = run_production_chain(
        executor, context, run_root=args.run_root,
        _stop_after_fit_only_rehearsal=args.fit_only_rehearsal,
        _invocation_start_ns=invocation_start_ns,
    )
    print(json.dumps(result, sort_keys=True))
    # V4: a typed non-PASS terminal status is a real refusal for the caller.
    # Returning 0 for FAIL / NO_FIT_ONLY_DEPLOYABLE_DEPTH let shell drivers,
    # CI, and the campaign runner treat a refused chain as a success.
    status = result.get("status")
    if status is None:
        return 0
    if status == "PASS":
        return 0
    if status in {"FAIL", "NO_FIT_ONLY_DEPLOYABLE_DEPTH"}:
        return 1
    raise ProductionDiagnosticRefusal(
        f"production chain returned an unrecognized terminal status: {status!r}")


__all__ = [
    "ExactComponentExecution", "ExactNeuralDiagnosticExecutor",
    "ProductionDiagnosticBackends", "ProductionDiagnosticRefusal",
    "derive_production_context",
    "run_production_chain", "run_fit_only_learning_rehearsal",
    "run_held_orchestration_rehearsal",
    "load_held_orchestration_rehearsal", "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
