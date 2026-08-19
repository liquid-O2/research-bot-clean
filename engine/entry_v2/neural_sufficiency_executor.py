"""Concrete, fail-closed fit-only executor for neural sufficiency acceptance.

Numerical kernels are supplied by a production resource provider because the
one-open corpus, GPU ownership and canonical replay live in the production
process.  This module owns the authority boundary: it derives the visible row
manifest from the loaded :class:`DiagnosticCorpus`, runs the exact atlas loss
and CatBoost implementations itself, and refuses any result not bound to that
manifest.  A provider cannot return a generic PASS mapping.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Protocol, Sequence

import numpy as np
import torch

from . import common as C
from .atlas_losses import loss_for_probe
from .atlas_materializers import materialize_probe_target
from .atlas_statistics import (
    FitLedgerRecord, e1_fit_count, through_e2_fit_count, validate_fit_ledger,
)
from .capacity_contract import FIT_ONLY_MIN_ORACLE_CAPTURE
from .causal_label_atlas import (
    PADDED_OUTPUT_WIDTH, PROBE_REGISTRY, AtlasRefusal, CellAvailability,
    shuffled_probe_for,
)
from .diagnostic_catboost import (
    CatBoostCompetenceResult, FrozenRepresentationRows,
    rehearse_catboost_competence,
)
from .diagnostic_corpus import DiagnosticCorpus
from .diagnostic_corpus import (
    CORPUS_READY_MILESTONE_SOURCE, LIFECYCLE_COLD, LIFECYCLE_PROVENANCE_RECEIPT_KEY,
    LIFECYCLE_PROVENANCE_SCHEMA, LIFECYCLE_WARM,
)
from .diagnostic_inputs import fit_only_rehearsal_windows
from .neural_sufficiency_model import CANONICAL_ARMS, FrozenRowManifest
from .neural_sufficiency_production import ExactComponentExecution
from .neural_sufficiency_runner import ACCEPTANCE_FIT_END, ASSETS


class RealDiagnosticExecutorRefusal(RuntimeError):
    pass


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(C.canonical_json_value(value), sort_keys=True,
                          separators=(",", ":"), allow_nan=False).encode()
    except (TypeError, ValueError) as exc:
        raise RealDiagnosticExecutorRefusal("non-canonical diagnostic result") from exc


def _sha(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _valid_sha(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(
        char in "0123456789abcdef" for char in value
    )


@dataclass(frozen=True)
class LoadedFitOnlyResources:
    corpus: DiagnosticCorpus
    one_load_id: str
    preload_workers: int
    one_corpus_build: bool
    one_session_cache: bool
    disk_backed_session_cache: bool
    effective_memory_available_bytes: int
    array_cache_capacity_bytes: int
    sequential_gpu: bool
    catboost_not_overlapped: bool
    atomic_boundaries: bool
    h2_open_count: int
    source_open_count_by_session: Mapping[str, int]
    resource_admission: Mapping[str, Any]
    fit_only_preflight: Mapping[str, Any] = field(default_factory=dict)


#: F2: statuses that mean the rehearsal transport path is BROKEN, not that
#: the economics lost.  See neural_sufficiency_resources.REHEARSAL_PATH_STATUSES.
DEGENERATE_PATH_STATUSES = frozenset({"DEGENERATE_MAPPER", "DEGENERATE_CALIBRATOR"})


def _catboost_deterministic_cpu() -> bool:
    """Measured: the frozen CatBoost parameter set is CPU and seed-pinned."""
    from .diagnostic_catboost import _classifier_params, _ranker_params
    return all(
        params.get("task_type") == "CPU"
        and params.get("bootstrap_type") == "No"
        and float(params.get("random_strength", 1.0)) == 0.0
        and isinstance(params.get("random_seed"), int)
        for params in (_classifier_params(), _ranker_params()))


def _corpus_selected_horizon_start_d8(corpus: DiagnosticCorpus) -> int:
    """A8: the diagnostic start wall, read off the corpus receipt.

    A rebuilt corpus with a different start day silently kept the hardcoded
    ``20210531`` literal, so the roster laws checked the wrong window.
    """
    value = getattr(corpus, "receipt", {}).get("selected_horizon_start_d8")
    if not isinstance(value, (int, np.integer)) or not 19000101 <= int(value) <= 99991231:
        raise RealDiagnosticExecutorRefusal(
            "corpus receipt selected_horizon_start_d8 is absent or invalid")
    return int(value)


def _degenerate_path_statuses(payload: object) -> set[str]:
    """Collect every degenerate transport status anywhere in a receipt tree."""
    found: set[str] = set()
    if isinstance(payload, Mapping):
        status = payload.get("status")
        if isinstance(status, str) and status in DEGENERATE_PATH_STATUSES:
            found.add(status)
        for value in payload.values():
            found |= _degenerate_path_statuses(value)
    elif isinstance(payload, (list, tuple)):
        for value in payload:
            found |= _degenerate_path_statuses(value)
    return found


@dataclass(frozen=True)
class RawFidelityResult:
    manifest_sha256: str
    left_searchsorted: bool
    equal_time_excluded: bool
    prefix_hashes_exact: bool
    all_21_raw_fields: bool
    before_equal_after_pack: bool
    causal_oracle_pass: bool
    raw_summary_learner_pass: bool
    initial_book_trust_exact: bool
    snapshot_seed_exact: bool
    adjacent_phase_exact: bool
    visible_prefix_constant_census: bool
    fit_only_normalizer: bool
    fit_only_firewall_exact: bool
    artifact_sha256: str


@dataclass(frozen=True)
class ArmRehearsalResult:
    arm: str
    manifest_sha256: str
    field_schema_sha256: str
    all_routes_gradient: bool
    suffix_bit_identical: bool
    continuous_mae: float
    categorical_accuracy: float
    minimum_auroc: float
    minimum_ap: float
    maximum_bce: float
    shared_head_exact: bool
    time_band_routing: bool
    no_retrain_occlusion: bool
    fit_only_firewall_exact: bool
    representation: FrozenRepresentationRows
    artifact_sha256: str


@dataclass(frozen=True)
class AtlasFitResult:
    manifest_sha256: str
    pretext_artifact_sha256: tuple[str, str]
    probe_artifact_sha256: Mapping[str, str | None]
    twin_artifact_sha256: Mapping[str, str | None]
    real_beyond_twin: bool
    fit_only_firewall_exact: bool
    competence_artifact_sha256: str
    artifact_sha256: str


@dataclass(frozen=True)
class DirectHeadResult:
    manifest_sha256: str
    rows: FrozenRepresentationRows
    minimum_auroc: float
    minimum_ap: float
    maximum_bce: float
    every_head_gradient: bool
    fit_only_firewall_exact: bool
    artifact_sha256: str


@dataclass(frozen=True)
class PolicyReplayResult:
    manifest_sha256: str
    candidate_manifest_sha256: str
    threshold_by_asset: Mapping[str, float]
    mapper_positive_skill: bool
    calibration_positive_slope: bool
    fast_sweep_parity: bool
    canonical_parity: bool
    equal_time_ties: bool
    occupancy_caps_cost_wall: bool
    full_denominator: bool
    mdd_exact: bool
    fit_only_firewall_exact: bool
    teacher_isolation_exact: bool
    mapper_row_ids: tuple[str, ...]
    calibration_row_ids: tuple[str, ...]
    threshold_row_ids: tuple[str, ...]
    artifact_sha256: str


class ExactDiagnosticResourceProvider(Protocol):
    """Production numerical boundary; all results are concrete typed objects."""

    def load_once(self) -> LoadedFitOnlyResources: ...
    def audit_raw_fidelity(self, loaded: LoadedFitOnlyResources,
                           manifest: FrozenRowManifest) -> RawFidelityResult: ...
    def train_and_rehearse_arm(self, loaded: LoadedFitOnlyResources,
                               manifest: FrozenRowManifest,
                               arm: str) -> ArmRehearsalResult: ...
    def fit_atlas(self, loaded: LoadedFitOnlyResources,
                  manifest: FrozenRowManifest) -> AtlasFitResult: ...
    def fit_direct_head(self, loaded: LoadedFitOnlyResources,
                        manifest: FrozenRowManifest,
                        representation: FrozenRepresentationRows) -> DirectHeadResult: ...
    def fit_catboost_competence(
        self, rows: FrozenRepresentationRows,
    ) -> CatBoostCompetenceResult: ...
    def fit_policy_and_replay(self, loaded: LoadedFitOnlyResources,
                              manifest: FrozenRowManifest,
                              rows: FrozenRepresentationRows,
                              catboost: CatBoostCompetenceResult) -> PolicyReplayResult: ...
    def rehearse_held_chain(self) -> Mapping[str, Any]: ...
    def export_acceptance_numerical_artifacts(self) -> Mapping[str, bytes]: ...
    def export_stage_evidence(self, stage: str) -> Mapping[str, bytes]: ...
    def restore_fit_only_m8_artifacts(
        self, payloads: Mapping[str, bytes],
    ) -> str: ...
    def restore_stage_numerical_artifacts(
        self, engine: Any, numerical: Mapping[str, Any], *,
        acceptance_artifacts: Mapping[str, bytes] | None = None,
    ) -> None: ...
    def fit_only_timing_provenance(self) -> Mapping[str, Any]: ...
    def close(self, loaded: LoadedFitOnlyResources) -> str: ...


class RealDataExactNeuralDiagnosticExecutor:
    """One-use executor implementing every acceptance component in order."""

    def __init__(self, provider: ExactDiagnosticResourceProvider) -> None:
        self.provider = provider
        self.loaded: LoadedFitOnlyResources | None = None
        self.manifest: FrozenRowManifest | None = None
        self.arms: dict[str, ArmRehearsalResult] = {}
        self.atlas: AtlasFitResult | None = None
        self.direct: DirectHeadResult | None = None
        self.catboost: CatBoostCompetenceResult | None = None
        self.policy: PolicyReplayResult | None = None
        self.ledger = None
        self.closed = False
        self.acceptance_finalized = False
        self._stage_boundary_store = None
        self._diagnostic_evidence_sha256: str | None = None
        self._timing_provenance: Mapping[str, Any] | None = None
        self._resumed_stage_executions: dict[str, ExactComponentExecution] = {}
        self._m8_reload_proof_sha256: str | None = None

    def bind_stage_boundary_store(self, store) -> None:
        if self._stage_boundary_store is not None:
            raise RealDiagnosticExecutorRefusal("stage boundary store is already bound")
        self._stage_boundary_store = store

    def resume_stage_boundaries(self, store, acceptance) -> str:
        acceptance_sha256 = acceptance.acceptance_sha256
        evidence_sha256 = acceptance.diagnostic_evidence_sha256
        accepted = store.load_evidence(
            "ACCEPTANCE", expected_sha256=evidence_sha256)
        from .neural_sufficiency_stage_persistence import (
            ACCEPTANCE_NUMERICAL_PAYLOADS,
        )
        acceptance_artifacts = {
            name: raw for name, raw in accepted.payloads.items()
            if name in ACCEPTANCE_NUMERICAL_PAYLOADS
        }
        if set(acceptance_artifacts) != set(ACCEPTANCE_NUMERICAL_PAYLOADS):
            raise RealDiagnosticExecutorRefusal(
                "accepted numerical restart payload census differs")
        m8_artifacts = {name: raw for name, raw in accepted.payloads.items()
                        if name.startswith("M8/")}
        restore_m8 = getattr(self.provider, "restore_fit_only_m8_artifacts", None)
        if not callable(restore_m8):
            raise RealDiagnosticExecutorRefusal(
                "provider cannot strict-load fit-only M8 learner artifacts")
        reload_proof = restore_m8(m8_artifacts)
        if not _valid_sha(reload_proof):
            raise RealDiagnosticExecutorRefusal(
                "provider returned an invalid M8 strict-reload proof")
        self._m8_reload_proof_sha256 = reload_proof
        policy_factory = None
        loaded_boundaries = {}
        if store.path("E3").exists():
            e2_boundary = store.load(
                "E2", expected_acceptance_sha256=acceptance_sha256)
            loaded_boundaries["E2"] = e2_boundary
            public = e2_boundary.public_result
            confirmation = getattr(public, "confirmation", None)
            kind = getattr(confirmation, "decision_kind", None)
            factory_name = {
                "direct_neural": "entry_v2_selected_direct_policy_factory",
                "catboost": "entry_v2_selected_catboost_policy_factory",
            }.get(kind)
            policy_factory = (None if factory_name is None else
                              getattr(self.provider, factory_name, None))
            if not callable(policy_factory):
                raise RealDiagnosticExecutorRefusal(
                    "restored E3 lacks its frozen named policy factory")
        resumed = store.resume_engine(
            expected_acceptance_sha256=acceptance_sha256,
            expected_diagnostic_evidence_sha256=evidence_sha256,
            policy_factory=policy_factory)
        for stage in ("E1", "E2", "E3"):
            if not store.path(stage).exists() or stage in loaded_boundaries:
                continue
            loaded_boundaries[stage] = store.load(
                stage, expected_acceptance_sha256=acceptance_sha256,
                policy_factory=(policy_factory if stage == "E3" else None),
            )
        restore = getattr(self.provider, "restore_stage_numerical_artifacts", None)
        if not callable(restore):
            raise RealDiagnosticExecutorRefusal("provider cannot restore numerical stages")
        restore(resumed.engine, resumed.numerical,
                acceptance_artifacts=acceptance_artifacts)
        loaded = getattr(self.provider, "loaded", None)
        if type(loaded) is not LoadedFitOnlyResources:
            raise RealDiagnosticExecutorRefusal("restored provider lacks live one-load resources")
        self.loaded = loaded
        self.manifest = self._derive_manifest(loaded.corpus)
        self.acceptance_finalized = True
        self._diagnostic_evidence_sha256 = evidence_sha256
        self._stage_boundary_store = store
        self._resumed_stage_executions = {
            stage: boundary.execution
            for stage, boundary in loaded_boundaries.items()
        }
        return reload_proof

    def timing_provenance(self) -> Mapping[str, Any]:
        # Corpus readiness is an earlier boundary than executor.prepare(): the
        # production factory has completed and retained the provider's exact
        # one-load resource, but the executor must remain logically unprepared
        # until the `one_load` acceptance component runs.  Validate that same
        # concrete resource here without mutating executor state; after
        # prepare/resume, self.loaded is the identical object and follows the
        # same path below.
        loaded = self.loaded
        if loaded is None:
            loaded = getattr(self.provider, "loaded", None)
        if type(loaded) is not LoadedFitOnlyResources or self.closed:
            raise RealDiagnosticExecutorRefusal(
                "corpus timing provenance lacks the factory-loaded resource"
            )
        export = getattr(self.provider, "fit_only_timing_provenance", None)
        if not callable(export):
            raise RealDiagnosticExecutorRefusal(
                "provider lacks measured cold/warm timing provenance")
        value = export()
        required = {
            "schema", "cold_or_warm", "warm_corpus_ready",
            "physical_full_pack_opens", "model_array_physical_fills",
            "verified_session_durable_hits",
            "verified_session_cold_publishes",
            "diagnostic_plane_durable_hits",
            "diagnostic_plane_bytes_materialized",
            "diagnostic_plane_bytes_reused",
            "corpus_ready_elapsed_milestone_source",
            "cumulative_window_identity_sha256",
        }
        if (not isinstance(value, Mapping) or set(value) != required
                or type(value["warm_corpus_ready"]) is not bool
                or value["schema"] != LIFECYCLE_PROVENANCE_SCHEMA
                or value["cold_or_warm"] not in {
                    LIFECYCLE_COLD, LIFECYCLE_WARM}
                or value["corpus_ready_elapsed_milestone_source"]
                    != CORPUS_READY_MILESTONE_SOURCE
                or not _valid_sha(value["cumulative_window_identity_sha256"])
                or any(type(value[name]) is not int or value[name] < 0
                       for name in (
                           "physical_full_pack_opens",
                           "model_array_physical_fills",
                           "verified_session_durable_hits",
                           "verified_session_cold_publishes",
                           "diagnostic_plane_durable_hits",
                           "diagnostic_plane_bytes_materialized",
                           "diagnostic_plane_bytes_reused"))):
            raise RealDiagnosticExecutorRefusal(
                "cold/warm corpus timing provenance is incomplete")
        lifecycle_class = value["cold_or_warm"]
        warm = lifecycle_class == LIFECYCLE_WARM
        if (value["model_array_physical_fills"]
                > value["physical_full_pack_opens"]
                or value["physical_full_pack_opens"]
                > value["verified_session_cold_publishes"]):
            raise RealDiagnosticExecutorRefusal(
                "one-open/fill counts exceed their cold publication population")
        if value["warm_corpus_ready"] is not warm:
            raise RealDiagnosticExecutorRefusal(
                "warm corpus boolean differs from lifecycle class")
        cold_names = ("verified_session_cold_publishes",
                      "physical_full_pack_opens", "model_array_physical_fills",
                      "diagnostic_plane_bytes_materialized")
        if (warm and (value["verified_session_durable_hits"] < 1
                      or value["diagnostic_plane_durable_hits"] < 1
                      or any(value[name] != 0 for name in cold_names))):
            raise RealDiagnosticExecutorRefusal(
                "warm corpus timing provenance contains cold work")
        if (lifecycle_class == LIFECYCLE_COLD
                and not any(value[name] > 0 for name in cold_names)):
            raise RealDiagnosticExecutorRefusal(
                "cold corpus timing provenance lacks producer work")
        lifecycle = loaded.corpus.receipt.get(LIFECYCLE_PROVENANCE_RECEIPT_KEY)
        if (not isinstance(lifecycle, Mapping)
                or any(lifecycle.get(name) != value[name]
                       for name in required)):
            raise RealDiagnosticExecutorRefusal(
                "resource timing provenance differs from the corpus lifecycle receipt")
        frozen = {"load_class": "warm" if warm else "cold",
                  "resource": dict(value), "lifecycle": dict(lifecycle)}
        self._timing_provenance = frozen
        return frozen

    def _execution(self, component: str, details: Mapping[str, Any]) -> ExactComponentExecution:
        if self.manifest is None:
            raise RealDiagnosticExecutorRefusal("execution has no frozen manifest")
        payload = {"component": component, "manifest": self.manifest.receipt_sha256,
                   "details": dict(details)}
        return ExactComponentExecution(
            component, True, True, ACCEPTANCE_FIT_END, _sha(payload),
            self.manifest.receipt_sha256, dict(details),
        )

    def _require_loaded(self) -> tuple[LoadedFitOnlyResources, FrozenRowManifest]:
        if self.loaded is None or self.manifest is None or self.closed:
            raise RealDiagnosticExecutorRefusal("one-load resources are unavailable")
        return self.loaded, self.manifest

    @staticmethod
    def _derive_manifest(corpus: DiagnosticCorpus) -> FrozenRowManifest:
        if type(corpus) is not DiagnosticCorpus:
            raise RealDiagnosticExecutorRefusal("provider did not supply DiagnosticCorpus")
        learner_ids = {
            candidate_id
            for session in getattr(corpus.corpus, "sessions", ())
            for candidate_id in session.candidate_ids
        }
        start_d8 = _corpus_selected_horizon_start_d8(corpus)
        authoritative_learner = {
            row.candidate_id for row in corpus.bindings
            if start_d8 <= int(row.trading_day) <= ACCEPTANCE_FIT_END
            and row.compliance_status == "CLEAR" and row.teacher_status == "READY"
        }
        # A10: the previous form re-scanned every binding for every learner id
        # (O(n^2) over the full roster).  One dict lookup is exact and linear.
        binding_day_by_id: dict[str, int] = {}
        for row in corpus.bindings:
            if row.candidate_id in binding_day_by_id:
                raise RealDiagnosticExecutorRefusal(
                    "diagnostic binding candidate id is duplicated")
            binding_day_by_id[row.candidate_id] = int(row.trading_day)
        learner_fit_ids = {
            candidate_id for candidate_id in learner_ids
            if start_d8 <= binding_day_by_id.get(candidate_id, -1)
            <= ACCEPTANCE_FIT_END
        }
        if learner_fit_ids != authoritative_learner:
            raise RealDiagnosticExecutorRefusal(
                "learner tensor roster differs from CLEAR+READY fit bindings"
            )
        eligible = tuple(row for row in corpus.bindings
                         if row.candidate_id in learner_fit_ids
                         and bool(row.action_loss_mask))
        selected = []
        # Deterministic day-round-robin prevents the bounded rehearsal from
        # degenerating into one early session while using no outcome magnitude
        # or caller-provided split labels.
        partitions = ((20210531, 20210730, 12),
                      (20210801, 20210831, 10),
                      (20210901, 20210930, 10))
        for asset in ASSETS:
            for label in (True, False):
                for start, end, quota in partitions:
                    pool = [row for row in eligible if row.asset == asset
                            and bool(row.action_target) == label
                            and start <= int(row.trading_day) <= end]
                    by_day: dict[int, list[Any]] = {}
                    for row in sorted(pool, key=lambda item: (
                            item.trading_day, item.decision_ts_ns, item.candidate_id)):
                        by_day.setdefault(int(row.trading_day), []).append(row)
                    chosen = []
                    while len(chosen) < quota and any(by_day.values()):
                        for day in sorted(by_day):
                            if by_day[day] and len(chosen) < quota:
                                chosen.append(by_day[day].pop(0))
                    if len(chosen) != quota:
                        raise RealDiagnosticExecutorRefusal(
                            f"{asset} lacks chronological 32/32 competence support"
                        )
                    selected.extend(chosen)
        selected.sort(key=lambda row: (row.asset, row.trading_day,
                                       row.decision_ts_ns, row.candidate_id))
        manifest = FrozenRowManifest.build(
            [row.candidate_id for row in selected], [row.asset for row in selected],
            [row.trading_day for row in selected], chronology="E1",
        )
        if set(manifest.split) != {"FIT"} or max(manifest.day) > ACCEPTANCE_FIT_END:
            raise RealDiagnosticExecutorRefusal("visible manifest crossed fit-only wall")
        return manifest

    @staticmethod
    def _bound(result: object, manifest: FrozenRowManifest) -> None:
        if getattr(result, "manifest_sha256", None) != manifest.receipt_sha256:
            raise RealDiagnosticExecutorRefusal("result is not bound to visible row manifest")
        if getattr(result, "fit_only_firewall_exact", False) is not True:
            raise RealDiagnosticExecutorRefusal("fit-only loaded-roster firewall differs")
        if not _valid_sha(getattr(result, "artifact_sha256", None)):
            raise RealDiagnosticExecutorRefusal("result lacks immutable artifact identity")

    @staticmethod
    def _validate_rows(rows: FrozenRepresentationRows,
                       manifest: FrozenRowManifest) -> None:
        rows.validate()
        ids = tuple(np.asarray(rows.candidate_id, str).tolist())
        if set(ids) != set(manifest.candidate_id) or len(ids) != len(manifest.candidate_id):
            raise RealDiagnosticExecutorRefusal("representation rows differ from manifest")
        expected = {cid: (asset, day) for cid, asset, day in zip(
            manifest.candidate_id, manifest.asset, manifest.day
        )}
        for cid, asset, day in zip(ids, np.asarray(rows.asset, str), np.asarray(rows.day, int)):
            if expected[cid] != (str(asset), int(day)):
                raise RealDiagnosticExecutorRefusal("representation chronology differs")
        if not np.all(rows.frozen_split() == "FIT"):
            raise RealDiagnosticExecutorRefusal("representation exposed non-fit rows")

    def prepare(self) -> ExactComponentExecution:
        if self.loaded is not None:
            raise RealDiagnosticExecutorRefusal("executor prepare is one-shot")
        loaded = self.provider.load_once()
        if type(loaded) is not LoadedFitOnlyResources:
            raise RealDiagnosticExecutorRefusal("weak load resource substitute")
        manifest = self._derive_manifest(loaded.corpus)
        # Runtime preload authority is the deduplicated union: ordinary corpus
        # sessions plus diagnostic-observer sessions.  The latter can include
        # candidate-bearing sources absent from EntryCorpus.sessions.
        source_keys: set[str] = set()
        ordinary = getattr(loaded.corpus.corpus, "sessions", ())
        for session in ordinary:
            source_keys.add(f"{session.source.asset}:{int(session.source.d8)}")
        for session in loaded.corpus.sessions:
            source_keys.add(f"{session.observed.source.asset}:{int(session.observed.source.d8)}")
        admission = dict(loaded.resource_admission)
        preflight = dict(loaded.fit_only_preflight)
        if (not loaded.one_load_id or loaded.preload_workers != 4
                or not all((loaded.one_corpus_build, loaded.one_session_cache,
                            loaded.disk_backed_session_cache,
                            loaded.sequential_gpu, loaded.catboost_not_overlapped,
                            loaded.atomic_boundaries))
                or loaded.effective_memory_available_bytes < 128 * 1024 ** 3
                or loaded.array_cache_capacity_bytes < 192 * 1024 ** 3
                or loaded.h2_open_count != 0
                or set(loaded.source_open_count_by_session) != source_keys
                or any(type(v) is not int or int(v) not in (0, 1)
                       for v in loaded.source_open_count_by_session.values())
                or admission.get("schema") !=
                    "entry-v2-production-resource-admission-v1"
                or admission.get("session_mapping_upper_bound", 0) < len(source_keys)
                or admission.get("nofile_soft_after", 0) <
                    admission.get("nofile_required", 1)
                or admission.get("vm_map_limit", 0) <
                    admission.get("vm_map_required", 1)
                or admission.get("disk_free_bytes", 0) <
                    admission.get("disk_free_required_bytes", 1)
                or admission.get("free_inodes", 0) <
                    admission.get("free_inodes_required", 1)
                or not _valid_sha(admission.get("receipt_sha256"))
                or preflight.get("schema") !=
                    "entry-v2-fit-only-real-corpus-preflight-v1"
                or preflight.get("status") != "PASS"
                or not _valid_sha(preflight.get("receipt_sha256"))
                or int(loaded.corpus.receipt.get("candidate_suffix_rows_visited", -1)) != 0):
            raise RealDiagnosticExecutorRefusal("one-load resource law failed")
        self.loaded, self.manifest = loaded, manifest
        self.timing_provenance()
        return self._execution("one_load", {
            "one_corpus_build": True, "one_session_cache": True,
            "disk_backed_session_cache": True,
            "effective_memory_available_bytes":
                loaded.effective_memory_available_bytes,
            "array_cache_capacity_bytes": loaded.array_cache_capacity_bytes,
            "four_worker_preload": True, "sequential_gpu": True,
            "catboost_not_overlapped": True, "atomic_boundaries": True,
            "one_load_id": loaded.one_load_id, "h2_open_count": 0,
            "candidate_suffix_rows_visited": 0,
            "resource_admission": admission,
            "fit_only_preflight": preflight,
            "visible_manifest_sha256": manifest.receipt_sha256,
            "visible_row_count": len(manifest.candidate_id),
        })

    def raw_fidelity(self) -> ExactComponentExecution:
        loaded, manifest = self._require_loaded()
        result = self.provider.audit_raw_fidelity(loaded, manifest)
        if type(result) is not RawFidelityResult:
            raise RealDiagnosticExecutorRefusal("weak raw-fidelity substitute")
        self._bound(result, manifest)
        fields = tuple(name for name in asdict(result) if name not in {
            "manifest_sha256", "artifact_sha256"
        })
        if any(getattr(result, name) is not True for name in fields):
            raise RealDiagnosticExecutorRefusal("raw fidelity competence failed")
        details = {name: getattr(result, name) for name in fields}
        details["artifact_sha256"] = result.artifact_sha256
        return self._execution("raw_fidelity", details)

    def train_and_rehearse_arm(self, arm: str) -> ExactComponentExecution:
        loaded, manifest = self._require_loaded()
        expected = CANONICAL_ARMS[len(self.arms)] if len(self.arms) < 5 else None
        if arm != expected:
            raise RealDiagnosticExecutorRefusal("canonical arm order changed")
        result = self.provider.train_and_rehearse_arm(loaded, manifest, arm)
        if type(result) is not ArmRehearsalResult or result.arm != arm:
            raise RealDiagnosticExecutorRefusal("weak/misnamed arm result")
        self._bound(result, manifest); self._validate_rows(result.representation, manifest)
        booleans = (result.all_routes_gradient, result.suffix_bit_identical,
                    result.shared_head_exact, result.time_band_routing,
                    result.no_retrain_occlusion, result.fit_only_firewall_exact)
        # Rulings 16/19: MECHANICAL laws stay hard (structural defects);
        # CAPABILITY metrics (memorization, reconstruction) are typed per-arm
        # verdicts recorded in the receipt — an incompetent arm continues as
        # ledger evidence and is excluded from selection by the provider.
        if not all(booleans) or not _valid_sha(result.field_schema_sha256):
            raise RealDiagnosticExecutorRefusal(f"{arm} mechanical law failed")
        self.arms[arm] = result
        # B-13/V2: every gate key below is READ OFF the measured stage result.
        # Emitting literal ``True`` made the receipt a restatement of the
        # assertion above rather than evidence of what was measured.
        reconstruction_pass = bool(result.continuous_mae <= 1e-3
                                   and result.categorical_accuracy == 1.0)
        balanced_oracle_overfit = bool(
            result.minimum_auroc >= .995 and result.minimum_ap >= .995
            and result.maximum_bce <= .02)
        return self._execution(f"arm_{arm}", {
            "all_routes_gradient": bool(result.all_routes_gradient),
            "suffix_bit_identical": bool(result.suffix_bit_identical),
            "reconstruction_pass": reconstruction_pass,
            "balanced_oracle_overfit": balanced_oracle_overfit,
            "shared_head_exact": bool(result.shared_head_exact),
            "real_fit_only_rehearsal": bool(result.fit_only_firewall_exact),
            "time_band_routing": bool(result.time_band_routing),
            "no_retrain_occlusion": bool(result.no_retrain_occlusion),
            "continuous_mae": result.continuous_mae,
            "categorical_accuracy": result.categorical_accuracy,
            "minimum_auroc": result.minimum_auroc, "minimum_ap": result.minimum_ap,
            "maximum_bce": result.maximum_bce,
            "arm_competent": bool(reconstruction_pass and balanced_oracle_overfit),
            "assets": list(ASSETS),
            "manifest_sha256": manifest.receipt_sha256,
            "measured_evidence_sha256": result.artifact_sha256,
        })

    def run_atlas(self) -> ExactComponentExecution:
        loaded, manifest = self._require_loaded()
        if tuple(self.arms) != CANONICAL_ARMS:
            raise RealDiagnosticExecutorRefusal("atlas cannot precede all arm rehearsals")
        # Execute every registered materializer and loss on the already-built
        # session truth planes. Unsupported cells remain typed, never skipped.
        seen: set[str] = set(); numeric: set[str] = set()
        materialized: set[str] = set(); typed: set[str] = set()
        unavailable: set[str] = set()
        for session in loaded.corpus.sessions:
            local_ids = set(session.atlas.candidate_ids)
            if not local_ids & set(manifest.candidate_id):
                continue
            for spec in PROBE_REGISTRY:
                target = materialize_probe_target(session.atlas, spec, fit_context=None)
                seen.add(spec.probe_id)
                if isinstance(target.state, CellAvailability):
                    typed.add(spec.probe_id)
                if target.state == CellAvailability.MATERIALIZED and bool(target.validity_mask.any()):
                    materialized.add(spec.probe_id)
                    prediction = torch.linspace(
                        -0.17, 0.19,
                        len(target.values) * PADDED_OUTPUT_WIDTH,
                        dtype=torch.float32,
                    ).reshape(
                        len(target.values), PADDED_OUTPUT_WIDTH,
                    ).requires_grad_(True)
                    # Cross-lane item 26: a fully-masked batch is a typed
                    # UNAVAILABLE ledger state, never a crash or a silent zero.
                    try:
                        loss = loss_for_probe(spec, prediction, target)
                    except AtlasRefusal as error:
                        if not str(error).startswith("UNAVAILABLE:"):
                            raise
                        unavailable.add(spec.probe_id)
                        continue
                    loss.backward()
                    if not bool(torch.isfinite(loss)) or prediction.grad is None \
                            or not bool(torch.isfinite(prediction.grad).all()) \
                            or not bool(prediction.grad.abs().sum() > 0):
                        raise RealDiagnosticExecutorRefusal(f"nonfinite atlas loss {spec.probe_id}")
                    numeric.add(spec.probe_id)
        if seen != {spec.probe_id for spec in PROBE_REGISTRY}:
            raise RealDiagnosticExecutorRefusal("not all 44 atlas probes reached availability")
        result = self.provider.fit_atlas(loaded, manifest)
        if type(result) is not AtlasFitResult:
            raise RealDiagnosticExecutorRefusal("weak atlas result")
        self._bound(result, manifest)
        expected = {spec.probe_id for spec in PROBE_REGISTRY}
        paired = tuple((result.probe_artifact_sha256[probe_id],
                        result.twin_artifact_sha256[probe_id])
                       for probe_id in sorted(expected))
        if (len(PROBE_REGISTRY) != 44 or set(result.probe_artifact_sha256) != expected
                or set(result.twin_artifact_sha256) != expected
                or len(result.pretext_artifact_sha256) != 2
                or not all(map(_valid_sha, result.pretext_artifact_sha256))
                or any((left is None) != (right is None) for left, right in paired)
                or any(not _valid_sha(value) for pair in paired for value in pair
                       if value is not None)
                or not any(left is not None for left, _ in paired)
                or not result.real_beyond_twin
                or not _valid_sha(result.competence_artifact_sha256)):
            raise RealDiagnosticExecutorRefusal("atlas 44+44+2 execution is incomplete")
        self.atlas = result
        # B-13: measured, not declared.  ``registered_e1_slots`` and
        # ``maximum_through_e2`` are derived from len(PROBE_REGISTRY) through
        # the frozen A-011 counters instead of being written as 90/98.
        registered_e1_slots = e1_fit_count(
            len(PROBE_REGISTRY), len(PROBE_REGISTRY), 2)
        maximum_through_e2 = through_e2_fit_count(
            4, base_e1_fits=registered_e1_slots)
        return self._execution("atlas_probe_loss", {
            "all_44_registered": bool(seen == expected and len(PROBE_REGISTRY) == 44),
            "all_losses_numeric_gradient": bool(
                numeric == (materialized - unavailable)),
            "typed_unavailable_probe_count": len(unavailable),
            "real_beyond_recipient_fixed_twin": bool(result.real_beyond_twin),
            "support_typed": bool(typed == seen),
            "materialization_end_to_end": bool(
                materialized and numeric == (materialized - unavailable)
                and seen == expected),
            "registered_e1_slots": registered_e1_slots,
            "maximum_through_e2": maximum_through_e2,
            "numeric_supported_probe_count": len(numeric),
            "materialized_probe_count": len(materialized),
            "manifest_sha256": manifest.receipt_sha256,
            "measured_evidence_sha256": result.artifact_sha256,
            "competence_artifact_sha256": result.competence_artifact_sha256,
        })

    def run_direct_head(self) -> ExactComponentExecution:
        loaded, manifest = self._require_loaded()
        if self.atlas is None:
            raise RealDiagnosticExecutorRefusal("direct head preceded atlas")
        # M1 is the full-plus-bypass representation used for the identical
        # direct/tree competence comparison.
        base = self.arms["M1"].representation
        result = self.provider.fit_direct_head(loaded, manifest, base)
        if type(result) is not DirectHeadResult:
            raise RealDiagnosticExecutorRefusal("weak direct-head result")
        self._bound(result, manifest); self._validate_rows(result.rows, manifest)
        # Same rulings-16/19 split: identity + gradient laws hard;
        # memorization metrics are a typed verdict in the receipt.
        if (result.rows.representation_sha256 != base.representation_sha256
                or not result.every_head_gradient):
            raise RealDiagnosticExecutorRefusal("direct head mechanical law failed")
        self.direct = result
        return self._execution("direct_head", {
            "head_competent": bool(result.minimum_auroc >= .995
                                   and result.minimum_ap >= .995
                                   and result.maximum_bce <= .02),
            "balanced_oracle_overfit": bool(
                result.minimum_auroc >= .995 and result.minimum_ap >= .995
                and result.maximum_bce <= .02),
            "every_head_gradient": bool(result.every_head_gradient),
            "identical_representation": bool(
                result.rows.representation_sha256 == base.representation_sha256),
            "minimum_auroc": float(result.minimum_auroc),
            "minimum_ap": float(result.minimum_ap),
            "maximum_bce": float(result.maximum_bce),
            "representation_sha256": result.rows.representation_sha256,
            "candidate_manifest_sha256": manifest.receipt_sha256,
            "measured_evidence_sha256": result.artifact_sha256,
        })

    def run_catboost(self) -> ExactComponentExecution:
        _, manifest = self._require_loaded()
        if self.direct is None:
            raise RealDiagnosticExecutorRefusal("CatBoost preceded direct head")
        result = self.provider.fit_catboost_competence(self.direct.rows)
        if (set(result.auroc_by_asset) != set(ASSETS)
                or min(result.auroc_by_asset.values()) < .995
                or min(result.ap_by_asset.values()) < .995
                or max(result.bce_by_asset.values()) > .02
                or result.representation_sha256 != self.direct.rows.representation_sha256
                or tuple(np.asarray(result.candidate_id, str)) != tuple(
                    np.asarray(self.direct.rows.candidate_id, str))
                or np.asarray(result.action_probability).shape != (
                    len(self.direct.rows.candidate_id),)
                or not np.all(np.isfinite(result.action_probability))
                or any(result.ranker_availability_by_asset.get(asset) != "MATERIALIZED"
                       for asset in ASSETS)
                or any(result.pair_group_count_by_asset.get(asset, 0) < 40
                       for asset in ASSETS)
                or any(result.pair_accuracy_by_asset.get(asset) is None
                       for asset in ASSETS)
                or not _valid_sha(result.pair_row_manifest_sha256)
                or not _valid_sha(result.row_manifest_sha256)):
            raise RealDiagnosticExecutorRefusal("CatBoost numerical competence differs")
        self.catboost = result
        probability_array = np.asarray(result.action_probability)
        return self._execution("catboost", {
            "balanced_oracle_overfit": bool(
                min(result.auroc_by_asset.values()) >= .995
                and min(result.ap_by_asset.values()) >= .995
                and max(result.bce_by_asset.values()) <= .02),
            "singleton_action_classifier": bool(
                probability_array.ndim == 1
                and probability_array.shape == (len(self.direct.rows.candidate_id),)),
            "pairlogit_group_semantics": "asset-day-phase",
            "equal_timestamp_claim": False,
            # B-13: measured from the frozen CatBoost parameter set actually
            # used for the fit, not declared.
            "deterministic_cpu": _catboost_deterministic_cpu(),
            "minimum_auroc": float(min(result.auroc_by_asset.values())),
            "minimum_ap": float(min(result.ap_by_asset.values())),
            "maximum_bce": float(max(result.bce_by_asset.values())),
            "pair_group_count_by_asset": dict(result.pair_group_count_by_asset),
            "pair_accuracy_by_asset": dict(result.pair_accuracy_by_asset),
            "pair_manifest_sha256_by_asset": dict(
                result.pair_manifest_sha256_by_asset),
            "pair_row_manifest_sha256": result.pair_row_manifest_sha256,
            "representation_sha256": result.representation_sha256,
            "candidate_manifest_sha256": manifest.receipt_sha256,
            "competence_sha256": result.receipt_sha256,
        })

    def _ensure_policy(self) -> PolicyReplayResult:
        loaded, manifest = self._require_loaded()
        if self.direct is None or self.catboost is None:
            raise RealDiagnosticExecutorRefusal("policy preceded head competence")
        if self.policy is None:
            result = self.provider.fit_policy_and_replay(
                loaded, manifest, self.direct.rows, self.catboost
            )
            if type(result) is not PolicyReplayResult:
                raise RealDiagnosticExecutorRefusal("weak policy/replay result")
            self._bound(result, manifest)
            if (not _valid_sha(result.candidate_manifest_sha256)
                    or result.candidate_manifest_sha256 == manifest.receipt_sha256
                    or set(result.threshold_by_asset) != set(ASSETS)
                    or any(not 0 <= float(value) <= 1
                           for value in result.threshold_by_asset.values())
                    or not all((result.mapper_positive_skill,
                                result.calibration_positive_slope,
                                result.fast_sweep_parity, result.canonical_parity,
                                result.equal_time_ties, result.occupancy_caps_cost_wall,
                                result.full_denominator, result.mdd_exact,
                                result.teacher_isolation_exact))):
                raise RealDiagnosticExecutorRefusal("policy/replay competence failed")
            expected_partitions = tuple(tuple(part) for part in self._partition_ids())
            actual_partitions = (result.mapper_row_ids, result.calibration_row_ids,
                                 result.threshold_row_ids)
            if actual_partitions != expected_partitions:
                raise RealDiagnosticExecutorRefusal(
                    "policy partitions differ from internally derived chronology"
                )
            self.policy = result
            self._policy_measurements = self._measure_policy_partitions(result)
        return self.policy

    def _measure_policy_partitions(self, result: PolicyReplayResult
                                   ) -> Mapping[str, Any]:
        """B-13: measure the chronology/disjointness/fit-only partition laws.

        The mapper/calibration/threshold receipts used to emit literal ``True``
        for these keys.  Each one is now derived from the frozen bindings.
        """
        loaded, _ = self._require_loaded()
        rows = {row.candidate_id: row for row in loaded.corpus.bindings}
        groups = {"mapper": tuple(result.mapper_row_ids),
                  "calibration": tuple(result.calibration_row_ids),
                  "threshold": tuple(result.threshold_row_ids)}
        missing = [cid for group in groups.values() for cid in group
                   if cid not in rows]
        if missing:
            raise RealDiagnosticExecutorRefusal(
                "policy partition references an unbound candidate")
        days = {name: tuple(rows[cid].trading_day for cid in group)
                for name, group in groups.items()}
        masks = {name: tuple(bool(rows[cid].action_loss_mask) for cid in group)
                 for name, group in groups.items()}
        if any(not group for group in groups.values()):
            raise RealDiagnosticExecutorRefusal("policy partition is empty")
        return MappingProxyType({
            "a004_mask_exact": bool(all(masks["mapper"])),
            "mapper_fit_only": bool(max(days["mapper"]) <= ACCEPTANCE_FIT_END),
            "calibration_chronological": bool(
                max(days["mapper"]) <= min(days["calibration"])),
            "calibration_fit_disjoint": bool(
                set(groups["calibration"]).isdisjoint(groups["mapper"])),
            "threshold_chronological": bool(
                max(days["calibration"]) <= min(days["threshold"])),
            "threshold_calibration_disjoint": bool(
                set(groups["threshold"]).isdisjoint(groups["calibration"])
                and set(groups["threshold"]).isdisjoint(groups["mapper"])),
            "threshold_no_held_labels": bool(
                max(days["threshold"]) <= ACCEPTANCE_FIT_END),
            "maximum_partition_day": int(max(
                day for group in days.values() for day in group)),
        })

    def _policy_measurement(self, key: str) -> bool:
        measurements = getattr(self, "_policy_measurements", None)
        if not isinstance(measurements, Mapping) or key not in measurements:
            raise RealDiagnosticExecutorRefusal(
                f"policy partition measurement {key!r} was never taken")
        return bool(measurements[key])

    def _partition_ids(self) -> tuple[list[str], list[str], list[str]]:
        loaded, _ = self._require_loaded()
        # A-013 fit-only rehearsal chronology.  The Aug 9-31 forward block is
        # consumed only by G7 and is never reused for mapper/Platt/threshold.
        e1r = fit_only_rehearsal_windows("E1r")
        ranges = (e1r["FIT"], e1r["PLATT"], e1r["THRESHOLD"])
        learner_ids = {candidate_id for session in loaded.corpus.corpus.sessions
                       for candidate_id in session.candidate_ids}
        start_d8 = _corpus_selected_horizon_start_d8(loaded.corpus)
        rows = tuple(row for row in loaded.corpus.bindings
                     if row.candidate_id in learner_ids
                     and row.compliance_status == "CLEAR"
                     and row.teacher_status == "READY"
                     and start_d8 <= row.trading_day <= ACCEPTANCE_FIT_END)
        rows = tuple(sorted(rows, key=lambda row: (
            row.asset, row.trading_day, row.decision_ts_ns, row.candidate_id)))
        ids = [[row.candidate_id for row in rows if start <= row.trading_day <= end]
               for start, end in ranges]
        if any(not group for group in ids):
            raise RealDiagnosticExecutorRefusal("derived policy partitions are empty")
        return ids[0], ids[1], ids[2]

    def fit_mapper(self) -> ExactComponentExecution:
        result = self._ensure_policy(); fit = list(result.mapper_row_ids)
        return self._execution("mapper", {
            "a004_mask_exact": self._policy_measurement("a004_mask_exact"),
            "fit_only": self._policy_measurement("mapper_fit_only"),
            "positive_skill": bool(result.mapper_positive_skill),
            "row_ids": fit, "candidate_manifest_sha256": result.candidate_manifest_sha256,
            "measured_evidence_sha256": result.artifact_sha256,
        })

    def calibrate(self) -> ExactComponentExecution:
        result = self._ensure_policy(); calibration = list(result.calibration_row_ids)
        return self._execution("calibration", {
            "positive_slope": bool(result.calibration_positive_slope),
            "chronological": self._policy_measurement("calibration_chronological"),
            "fit_disjoint": self._policy_measurement("calibration_fit_disjoint"),
            "row_ids": calibration,
            "candidate_manifest_sha256": result.candidate_manifest_sha256,
            "measured_evidence_sha256": result.artifact_sha256,
        })

    def select_threshold_with_canonical_sweep(self) -> ExactComponentExecution:
        result = self._ensure_policy(); threshold = list(result.threshold_row_ids)
        return self._execution("threshold", {
            "chronological": self._policy_measurement("threshold_chronological"),
            "calibration_disjoint":
                self._policy_measurement("threshold_calibration_disjoint"),
            "no_held_labels":
                self._policy_measurement("threshold_no_held_labels"),
            "row_ids": threshold,
            "canonical_fast_sweep": result.fast_sweep_parity,
            "selected_threshold_parity": result.canonical_parity,
            "threshold_by_asset": dict(result.threshold_by_asset),
            "candidate_manifest_sha256": result.candidate_manifest_sha256,
            "measured_evidence_sha256": result.artifact_sha256,
        })

    def run_canonical_replay(self) -> ExactComponentExecution:
        result = self._ensure_policy()
        return self._execution("canonical_replay", {
            "canonical_parity": bool(result.canonical_parity),
            "equal_time_ties": bool(result.equal_time_ties),
            "occupancy_caps_cost_wall": bool(result.occupancy_caps_cost_wall),
            "full_denominator": bool(result.full_denominator),
            "mdd_exact": bool(result.mdd_exact),
            "fast_sweep_parity": bool(result.fast_sweep_parity),
            "fit_only_end_to_end": bool(result.fit_only_firewall_exact),
            "teacher_isolation_exact": bool(result.teacher_isolation_exact),
            "candidate_manifest_sha256": result.candidate_manifest_sha256,
            "artifact_sha256": result.artifact_sha256,
        })

    def validate_fit_ledger(self) -> ExactComponentExecution:
        _, manifest = self._require_loaded()
        if self.atlas is None:
            raise RealDiagnosticExecutorRefusal("ledger preceded atlas")
        records: list[FitLedgerRecord] = []
        for objective_id, digest in zip(("C01P01", "C02P01"),
                                        self.atlas.pretext_artifact_sha256):
            records.append(FitLedgerRecord(
                f"pretext-{objective_id}", "E1_PRETEXT", "FIT", digest, objective_id))
        for spec in PROBE_REGISTRY:
            real = self.atlas.probe_artifact_sha256[spec.probe_id]
            twin = self.atlas.twin_artifact_sha256[spec.probe_id]
            status = "FIT" if real is not None else "UNAVAILABLE"
            records.append(FitLedgerRecord(spec.probe_id, "E1_REAL", status, real))
            records.append(FitLedgerRecord(
                shuffled_probe_for(spec).probe_id, "E1_TWIN", status, twin))
        records.append(FitLedgerRecord("fit-only-competence", "COMPETENCE", "FIT",
                                       self.atlas.competence_artifact_sha256))
        receipt = validate_fit_ledger(records, finalist_count=0)
        # Declared limitation (2026-08-18 sweep): the COMPETENCE row is
        # artifact-backed (competence_artifact_sha256) but its clone fits run
        # outside the optimizer census (fit_probe path), so the census
        # under-counts by that stage only — conservative for the 98-fit cap.
        # Revisit hook: route fit_probe constructions through _run_optimizer.
        # C3/A-011: reconcile the DECLARATIVE ledger above against the MEASURED
        # process-global optimizer census.  Every optimizer construction on the
        # atlas/arm/head paths is routed through ``_run_optimizer``; a
        # registered fit that never ran, or a hidden extra fit, refuses here.
        from .neural_sufficiency_resources import (
            LEDGER_FIT_CATEGORIES, MAXIMUM_REGISTERED_FITS_THROUGH_E2,
            optimizer_fit_census,
        )
        census = optimizer_fit_census()
        declared = {category: sum(row.category == category and row.status == "FIT"
                                  for row in records)
                    for category in LEDGER_FIT_CATEGORIES}
        measured = {category: int(census["counts"][category])
                    for category in LEDGER_FIT_CATEGORIES}
        if measured != declared:
            raise RealDiagnosticExecutorRefusal(
                "declared fit ledger differs from the measured optimizer census: "
                f"declared={declared} measured={measured}")
        if census["registered_total"] > MAXIMUM_REGISTERED_FITS_THROUGH_E2:
            raise RealDiagnosticExecutorRefusal(
                "measured optimizer census exceeds the 98-fit through-E2 ceiling")
        if census["registered_total"] != receipt.through_e2_optimizer_fits:
            raise RealDiagnosticExecutorRefusal(
                "through-E2 optimizer fit totals differ from the measured census")
        self.ledger = receipt
        return self._execution("fit_ledger", {
            "all_fits_counted": bool(measured == declared
                                     and census["registered_total"]
                                     == receipt.through_e2_optimizer_fits),
            "competence_separate": bool(
                receipt.through_e2_optimizer_fits
                == receipt.e1_optimizer_fits + receipt.e2_optimizer_fits),
            "e1_registered_slots": receipt.e1_registered_slots,
            "through_e2_optimizer_fits": receipt.through_e2_optimizer_fits,
            "discarded_competence_fits": receipt.discarded_competence_fits,
            "measured_optimizer_census": dict(census["counts"]),
            "measured_registered_total": int(census["registered_total"]),
            "measured_optimizer_census_sha256": census["records_sha256"],
            "manifest_sha256": manifest.receipt_sha256,
        })

    def finalize(self) -> ExactComponentExecution:
        loaded, manifest = self._require_loaded()
        if self.ledger is None or self.policy is None or self.catboost is None:
            raise RealDiagnosticExecutorRefusal("component chain is incomplete")
        # Acceptance finalization freezes the component chain but deliberately
        # leaves the one-load corpus/cache live for held E1/E2/E3.  Physical
        # close belongs to the outer production-chain finally block.
        if self._stage_boundary_store is None:
            raise RealDiagnosticExecutorRefusal(
                "acceptance numerical boundary store is not bound")
        export_acceptance = getattr(
            self.provider, "export_acceptance_numerical_artifacts", None)
        export_evidence = getattr(self.provider, "export_stage_evidence", None)
        if not callable(export_acceptance) or not callable(export_evidence):
            raise RealDiagnosticExecutorRefusal(
                "provider lacks acceptance/M8 evidence exporters")
        acceptance_payloads = export_acceptance()
        m8_payloads = export_evidence("M8")
        if (not isinstance(acceptance_payloads, Mapping)
                or not isinstance(m8_payloads, Mapping)):
            raise RealDiagnosticExecutorRefusal(
                "provider returned weak acceptance evidence mappings")
        combined = {**dict(acceptance_payloads), **dict(m8_payloads)}
        if (len(combined) != len(acceptance_payloads) + len(m8_payloads)
                or any(not isinstance(name, str) or not isinstance(raw, bytes)
                       for name, raw in combined.items())):
            raise RealDiagnosticExecutorRefusal(
                "provider returned weak/colliding acceptance evidence")
        try:
            rehearsal = json.loads(m8_payloads["M8/rehearsal-evidence.json"])
        except (KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RealDiagnosticExecutorRefusal(
                "M8 fit-only held rehearsal payload is invalid") from exc
        if (not isinstance(rehearsal, Mapping) or rehearsal.get("status") not in {
                "PASS", "NO_FIT_ONLY_DEPLOYABLE_DEPTH"}
                or rehearsal.get("minimum_oracle_capture")
                    != FIT_ONLY_MIN_ORACLE_CAPTURE
                or rehearsal.get("fit_only_max_d8") != 20210930
                or rehearsal.get("no_held_labels") is not True
                or type(rehearsal.get("held_launch_permitted")) is not bool
                or (rehearsal.get("status") == "PASS") !=
                    rehearsal.get("held_launch_permitted")
                or not _valid_sha(rehearsal.get("source_tree_sha256"))
                or not _valid_sha(rehearsal.get("receipt_sha256"))):
            raise RealDiagnosticExecutorRefusal("fit-only held rehearsal receipt differs")
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
                or not _valid_sha(g7.get("learner_law_sha256"))
                or not _valid_sha(g7.get("e1r_checkpoint_sha256"))
                or not _valid_sha(g7.get("e2r_checkpoint_sha256"))
                or g7.get("e1r_checkpoint_sha256")
                    == g7.get("e2r_checkpoint_sha256")
                or g7.get("e1r_fit_wall") != 20210709
                or g7.get("e2r_fit_wall") != 20210813
                or g7.get("same_full_learner_independent_fits") is not True
                or g7.get("minimum_oracle_capture")
                    != FIT_ONLY_MIN_ORACLE_CAPTURE
                or type(g7.get("goal_recovery_all_blocks")) is not bool
                or set(g7.get("goal_recovery_receipts", {}))
                    != expected_goal_receipts
                or any(not _valid_sha(value) for value in
                       g7.get("goal_recovery_receipts", {}).values())
                or (rehearsal["status"] == "PASS" and not (
                    g7.get("all_asset_in_sample") is True
                    and g7.get("all_asset_disjoint_forward") is True
                    and g7["goal_recovery_all_blocks"] is True))):
            raise RealDiagnosticExecutorRefusal(
                "fit-only goal-recovery rehearsal evidence differs")
        # F2: a degenerate mapper/calibrator anywhere in the rehearsal is an
        # IMPLEMENTATION defect.  It must never be reported as an economic
        # loser, so it refuses here regardless of the overall status.
        degenerate = _degenerate_path_statuses(rehearsal)
        if degenerate:
            raise RealDiagnosticExecutorRefusal(
                "fit-only rehearsal produced a degenerate transport path: "
                + ",".join(sorted(degenerate)))
        # D-095: a PERFECT score must survive the identical mapper/Platt/
        # threshold-sweep/feasibility/goal-recovery/forward-replay transport.
        # Failing that is an implementation refusal, never an economic loser.
        prophet = g7.get("prophet_positive_control")
        if not isinstance(prophet, Mapping) or set(prophet) != {"E1r", "E2r"}:
            raise RealDiagnosticExecutorRefusal(
                "prophet-through-funnel positive control is absent")
        for chronology in sorted(prophet):
            control = prophet[chronology]
            if (not isinstance(control, Mapping)
                    or control.get("chronology") != chronology
                    or control.get("artifact")
                        != f"G7/{chronology}/PROPHET/positive-control"
                    or not _valid_sha(control.get("path_receipt_sha256"))
                    or not _valid_sha(control.get("receipt_sha256"))):
                raise RealDiagnosticExecutorRefusal(
                    "prophet positive-control receipt differs")
            if control.get("status") != "ELIGIBLE":
                raise RealDiagnosticExecutorRefusal(
                    "transport funnel cannot carry a perfect score")
            # Quantitative bar: measured healthy transport recovers 82-91% of
            # the goal-grade ceiling.  Below the prelaunch floor the funnel is
            # broken even when every block reports "feasible".
            if (control.get("minimum_oracle_capture") != FIT_ONLY_MIN_ORACLE_CAPTURE
                    or control.get("ceiling_admission")
                        != "cert_close_usd >= MIN_EXPECTANCY_USD"
                    or control.get("meets_capture_bar") is not True):
                raise RealDiagnosticExecutorRefusal(
                    "transport funnel cannot carry a perfect score")
        diagnostic_evidence_sha256 = self._stage_boundary_store.publish_evidence(
            "ACCEPTANCE", combined)
        self._diagnostic_evidence_sha256 = diagnostic_evidence_sha256
        close_sha = _sha({"one_load_id": loaded.one_load_id,
                          "state": "LIVE_AFTER_ACCEPTANCE"})
        self.acceptance_finalized = True
        return self._execution("finalize", {
            "all_components_complete": True, "fit_only_boundary_frozen": True,
            "one_load_retained_for_held": True,
            "immutable_chain_complete": True,
            "restart_payload_complete": True,
            "restartable_boundaries": False,
            "m8_reload_proof_sha256": None,
            "one_load_id": loaded.one_load_id,
            "manifest_sha256": manifest.receipt_sha256,
            "held_rehearsal": dict(rehearsal),
            "diagnostic_evidence_sha256": diagnostic_evidence_sha256,
            "live_resource_sha256": close_sha,
        })

    def close_after_chain(self) -> None:
        if self.closed:
            return
        if self.loaded is not None:
            close = getattr(self.provider, "close_after_chain", None)
            if not callable(close):
                raise RealDiagnosticExecutorRefusal("provider lacks chain lifecycle close")
            close()
        self.closed = True

    def execute_stage(self, mode: str, acceptance_sha256: str,
                      prior_stage_sha256: str) -> ExactComponentExecution:
        resumed = self._resumed_stage_executions.pop(mode, None)
        if resumed is not None:
            expected_component = f"execute_{mode.lower()}"
            if (resumed.component != expected_component or not resumed.passed
                    or resumed.fit_only
                    or resumed.details.get("acceptance_sha256") != acceptance_sha256
                    or (mode != "E1" and
                        resumed.details.get("prior_stage_sha256")
                            != prior_stage_sha256)):
                raise RealDiagnosticExecutorRefusal(
                    "persisted held execution differs from the requested stage chain"
                )
            public = self.provider.stage_public_result(mode)
            if (public is None
                    or getattr(public, "artifact_sha256", None)
                        != resumed.result_artifact_sha256):
                raise RealDiagnosticExecutorRefusal(
                    "persisted held execution differs from restored numerical state"
                )
            return resumed
        execute = getattr(self.provider, "execute_stage", None)
        if not callable(execute):
            raise RealDiagnosticExecutorRefusal(
                "held-stage executor dependency is not installed; acceptance remains fit-only"
            )
        result = execute(mode, acceptance_sha256, prior_stage_sha256)
        if type(result) is not ExactComponentExecution:
            raise RealDiagnosticExecutorRefusal("held-stage provider returned weak evidence")
        if self._stage_boundary_store is None:
            raise RealDiagnosticExecutorRefusal("held stage boundary store is not bound")
        if not _valid_sha(self._diagnostic_evidence_sha256):
            raise RealDiagnosticExecutorRefusal(
                "held stage lacks its accepted diagnostic evidence")
        public = self.provider.stage_public_result(mode)
        if mode in ("E1", "E2"):
            numerical = self.provider.export_stage_numerical_artifacts(mode)
            if mode == "E1":
                self._stage_boundary_store.publish_e1(
                    acceptance_sha256, result, public, numerical,
                    diagnostic_evidence_sha256=self._diagnostic_evidence_sha256)
            else:
                self._stage_boundary_store.publish_e2(
                    acceptance_sha256, prior_stage_sha256, result, public, numerical,
                    diagnostic_evidence_sha256=self._diagnostic_evidence_sha256)
        elif mode == "E3":
            self._stage_boundary_store.publish_e3(
                acceptance_sha256, prior_stage_sha256, result, public,
                diagnostic_evidence_sha256=self._diagnostic_evidence_sha256)
        return result

    def export_winner_bundle_payloads(self, adoption_sha256: str) -> Mapping[str, bytes]:
        export = getattr(self.provider, "export_winner_bundle_payloads", None)
        if not callable(export):
            raise RealDiagnosticExecutorRefusal(
                "winner-bundle exporter dependency is not installed; no synthetic payloads"
            )
        result = export(adoption_sha256)
        if not isinstance(result, Mapping) or any(
                not isinstance(name, str) or not isinstance(payload, bytes)
                for name, payload in result.items()):
            raise RealDiagnosticExecutorRefusal("winner-bundle exporter returned weak payloads")
        return result

    def transfer_winner_resources(self, adoption_sha256: str):
        transfer = getattr(self.provider, "transfer_winner_resources", None)
        if not callable(transfer):
            raise RealDiagnosticExecutorRefusal("provider cannot transfer one-load ownership")
        resource = transfer(adoption_sha256)
        self.closed = True
        return resource

    def export_primary_e3_fold(self, adoption_sha256: str) -> Path:
        export = getattr(self.provider, "export_primary_e3_fold", None)
        if not callable(export):
            raise RealDiagnosticExecutorRefusal(
                "real held E3 fold exporter is not installed; retraining is forbidden"
            )
        path = Path(export(adoption_sha256)).resolve()
        if not path.is_dir():
            raise RealDiagnosticExecutorRefusal("held E3 exporter did not return a fold directory")
        return path


__all__ = [
    "ArmRehearsalResult", "AtlasFitResult", "DirectHeadResult",
    "ExactDiagnosticResourceProvider", "LoadedFitOnlyResources",
    "PolicyReplayResult", "RawFidelityResult",
    "RealDataExactNeuralDiagnosticExecutor", "RealDiagnosticExecutorRefusal",
]
