#!/usr/bin/env python3
"""Concrete, fail-closed runtime for the frozen pre-H2 Entry V2 campaign."""

from __future__ import annotations

import argparse
import importlib
from dataclasses import dataclass, replace
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
import csv
import json
from pathlib import Path
import shutil
from threading import Event
from types import MappingProxyType
from typing import Any, Callable, Mapping, Sequence
import multiprocessing

import numpy as np
import torch

from . import common as C
from .context_sources import (
    CONTEXT_TENSOR_WIDTH,
    CONTEXT_TYPE_ID,
    CausalContextRepository,
    load_context_repository,
)
from .corpus import (
    CANDIDATE_FEATURE_SCHEMA,
    AssetArtifactSet,
    AssetScopedForecastProvider,
    EntryCorpus,
    QRE2ForecastArtifactInput,
    QRE2ForecastProvider,
    build_corpus,
    merge_asset_corpora,
    merge_chronological_corpora,
    DiagnosticSessionObserver,
    VERIFIED_SESSION_LAW_SHA256,
)
from .event_pack import CATEGORY_SIZES, CATEGORICAL_FIELDS, CONTINUOUS_FIELDS
from .diagnostic_corpus import (
    LIFECYCLE_PROVENANCE_RECEIPT_KEY, LIFECYCLE_PROVENANCE_SCHEMA,
    CORPUS_READY_MILESTONE_SOURCE,
    LIFECYCLE_COLD, LIFECYCLE_WARM,
    DIAGNOSTIC_PLANE_LAW_SHA256,
    DiagnosticCorpus, DiagnosticCorpusObserver, finalize_diagnostic_corpus,
    merge_diagnostic_corpora,
)
from .durable_store import DurableEntryV2Store
from .model import FullPrefixEntryModel
from .production_driver import (
    CorpusStage,
    DriverPlan,
    DriverRuntime,
    run_pre_h2_campaign,
)
from .session_stream import (
    MODEL_ARRAYS_CONVERSION_LAW_SHA256, SessionArrayCache, SessionEventSource,
)
from .train import EntryLearningSystem, TrainingConfig


FROZEN_PRODUCTION_CONFIG = TrainingConfig()
PRODUCTION_ARRAY_CACHE_BYTES = 192 * 1024 ** 3
PRODUCTION_MEMORY_RESERVE_BYTES = 256 * 1024 ** 3
PRODUCTION_DISK_CACHE_MEMORY_RESERVE_BYTES = 128 * 1024 ** 3
COLD_ASSET_WINDOW_SCHEMA = "entry-v2-cold-asset-window-v1"
COLD_ASSET_WINDOW_LAW_SHA256 = C.object_sha256({
    "schema": COLD_ASSET_WINDOW_SCHEMA,
    "execution": "persistent-spawn-process-per-asset-before-cuda",
    "publication": "verified-session+session-arrays+diagnostic-planes-before-parent",
    "parent": "strict-durable-reconstruction-no-cold-fallback",
})


def _required(root: Path, relative: str) -> Path:
    root = root.resolve()
    declared = root / relative
    if declared.is_symlink():
        raise C.EntryV2Refusal(f"production artifact cannot be a symlink: {relative}")
    path = declared.resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise C.EntryV2Refusal(f"production artifact escapes substrate root: {relative}") from exc
    if not path.is_file():
        raise C.EntryV2Refusal(f"required production artifact is absent: {relative}")
    C.guard_payload(path)
    return path


def _json(path: Path, name: str) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise C.EntryV2Refusal(f"invalid {name} JSON") from exc
    if not isinstance(value, Mapping):
        raise C.EntryV2Refusal(f"{name} JSON is not an object")
    return value


def _native_stage_pins(root: Path, asset: str) -> Mapping[str, Any]:
    outputs = {
        "tally": f"tallies/{asset}.tsv",
        "lock": f"locks/{asset}.tsv",
        "phase": f"phases/{asset}.tsv",
        "events": f"events/{asset}/manifest.tsv",
    }
    pins: dict[str, Any] = {}
    for stage, relative in outputs.items():
        output = _required(root, relative)
        receipt_path = _required(root, f"receipts/{asset}.{stage}.json")
        receipt = _json(receipt_path, f"{asset} {stage} receipt")
        if (
            receipt.get("schema") != "QRE2RECEIPT2"
            or receipt.get("stage") != stage
            or receipt.get("asset") != asset
            or int(receipt.get("start_d8", 0)) != 20210101
            or int(receipt.get("end_d8_exclusive", 0)) != C.HOLDOUT_START_D8
            or receipt.get("final_exam_permit") is not False
            or receipt.get("output_sha256") != C.file_sha256(output)
        ):
            raise C.EntryV2Refusal(f"{asset} {stage} receipt/output pin mismatch")
        pins[stage] = {
            "output": str(output),
            "output_sha256": receipt["output_sha256"],
            "receipt": str(receipt_path),
            "receipt_sha256": C.file_sha256(receipt_path),
        }
    return MappingProxyType(pins)


def _artifact_sets(root: Path) -> tuple[AssetArtifactSet, ...]:
    out = []
    for asset in C.ASSETS:
        candidate_manifest = _required(
            root, f"g1/candidates/{asset}/manifest.tsv"
        )
        teacher_manifest = _required(root, f"g1/teacher/{asset}/manifest.tsv")
        candidate_receipt = _required(
            root, f"g1/receipts/{asset}.candidates.json"
        )
        teacher_receipt = _required(root, f"g1/receipts/{asset}.teacher.json")
        out.append(AssetArtifactSet(
            root=root,
            asset=asset,
            candidate_manifest_sha256=C.file_sha256(candidate_manifest),
            teacher_manifest_sha256=C.file_sha256(teacher_manifest),
            candidate_receipt_sha256=C.file_sha256(candidate_receipt),
            teacher_receipt_sha256=C.file_sha256(teacher_receipt),
        ))
    return tuple(out)


def _forecast_provider(root: Path) -> QRE2ForecastProvider:
    inputs = []
    for asset in C.ASSETS:
        artifact = _required(root, f"forecast/{asset}.qrf4.tsv")
        receipt = _required(root, f"forecast/{asset}.qrf4.json")
        inputs.append(QRE2ForecastArtifactInput(
            root=root,
            asset=asset,
            artifact_sha256=C.file_sha256(artifact),
            receipt_sha256=C.file_sha256(receipt),
        ))
    return QRE2ForecastProvider(tuple(inputs))


def _ceiling_pins(root: Path, artifacts: Sequence[AssetArtifactSet]
                  ) -> Mapping[str, Any]:
    teacher_hash = {item.asset: item.teacher_manifest_sha256 for item in artifacts}
    pins: dict[str, Any] = {}
    for asset in C.ASSETS:
        asset_pins: dict[str, Any] = {}
        for kind, universe in (
            ("deployable_ceiling", "DEPLOYABLE_CLEAR_ONLY"),
            ("mechanical_ceiling", "MECHANICAL_ALL"),
        ):
            output = _required(root, f"g1/schedules/{asset}.{kind}.tsv")
            receipt_path = _required(root, f"g1/receipts/{asset}.{kind}.json")
            receipt = _json(receipt_path, f"{asset} {kind} receipt")
            if (
                receipt.get("schema") != "QRE2G1SCHEDRECEIPT2"
                or receipt.get("scope") != asset
                or receipt.get("universe") != universe
                or receipt.get("final_exam_permit") is not False
                or int(receipt.get("holdout_start_d8", 0)) != C.HOLDOUT_START_D8
                or receipt.get("output_sha256") != C.file_sha256(output)
                or receipt.get("teacher_manifest_sha256") != {
                    asset: teacher_hash[asset]
                }
            ):
                raise C.EntryV2Refusal(f"{asset} {kind} receipt/output pin mismatch")
            asset_pins[kind] = {
                "output": str(output),
                "output_sha256": receipt["output_sha256"],
                "receipt": str(receipt_path),
                "receipt_sha256": C.file_sha256(receipt_path),
                "reported_total_usd": receipt.get("total_usd"),
                "reported_usd_per_session_diagnostic_only":
                    receipt.get("usd_per_session"),
            }
        pins[asset] = asset_pins
    return MappingProxyType(pins)


def _table(path: Path) -> tuple[Mapping[str, str], ...]:
    lines = path.read_text().splitlines()
    if len(lines) < 2 or not lines[0].startswith("# QRE2"):
        raise C.EntryV2Refusal(f"native history header missing: {path}")
    return tuple(csv.DictReader(lines[1:], delimiter="\t"))


def _history(root: Path, stage_pins: Mapping[str, Any],
             ceiling_pins: Mapping[str, Any]) -> Mapping[str, Any]:
    locks: list[dict[str, Any]] = []
    phases: list[dict[str, Any]] = []
    for asset in C.ASSETS:
        lock_path = _required(root, f"locks/{asset}.tsv")
        for row in _table(lock_path):
            if row.get("asset") != asset or row.get("status") != "LOCKED":
                continue
            session_day = int(row["d8"])
            basis_day = int(row["selection_basis_d8"])
            C.guard_date(session_day)
            C.guard_date(basis_day)
            if basis_day >= session_day:
                raise C.EntryV2Refusal("native locked iid is not strictly prior")
            locks.append({
                "asset": asset,
                "session_day": session_day,
                "selection_basis_day": basis_day,
                "locked_iid": int(row["locked_iid"]),
            })
        phase_path = _required(root, f"phases/{asset}.tsv")
        for row in _table(phase_path):
            if row.get("asset") != asset:
                raise C.EntryV2Refusal("native phase asset mismatch")
            month = int(row["month"])
            effective = month * 100 + 1
            fit_end = int(row["fit_end_d8"])
            C.guard_date(effective)
            if fit_end > 0:
                C.guard_date(fit_end)
            if fit_end >= effective:
                raise C.EntryV2Refusal("native phase fit is not strictly prior")
            phases.append({
                "asset": asset,
                "effective_from_day": effective,
                "fit_start_day": int(row["fit_start_d8"]),
                "fit_end_day": fit_end,
                "source": row["source"],
                "profile_sha256": row["profile_sha256"],
            })
    if not locks or not phases:
        raise C.EntryV2Refusal("native lock/phase history is empty")
    return MappingProxyType({
        "locked_iid": locks,
        "phases": phases,
        "native_stage_pins": dict(stage_pins),
        "native_ceiling_pins": dict(ceiling_pins),
    })


def _context_repository(asset: str) -> CausalContextRepository:
    repository = load_context_repository(asset, C.DEVELOPMENT_END_D8)
    rows = repository.receipt.get("series")
    if (
        not isinstance(rows, list)
        or not rows
        or not any(int(row.get("consumed_observation_count", 0)) > 0
                   for row in rows)
    ):
        raise C.EntryV2Refusal(f"{asset} causal context is absent")
    return repository


def _contexts() -> Mapping[str, CausalContextRepository]:
    return MappingProxyType({
        asset: _context_repository(asset) for asset in C.ASSETS
    })


def _cold_asset_window_identity(
    root: Path, artifact: AssetArtifactSet, asset: str,
    maximum_d8: int, minimum_d8_exclusive: int | None,
) -> Mapping[str, Any]:
    """Bind an isolated producer marker to exact inputs and executable laws."""
    source_tree = C.object_sha256({
        name: C.file_sha256(C.REPO_ROOT / "engine" / "entry_v2" / name)
        for name in (
            "corpus.py", "diagnostic_corpus.py", "production_runtime.py",
            "session_stream.py", "durable_store.py",
        )
    })
    return MappingProxyType({
        "schema": COLD_ASSET_WINDOW_SCHEMA,
        "asset": asset,
        "maximum_d8": int(maximum_d8),
        "minimum_d8_exclusive": (
            None if minimum_d8_exclusive is None
            else int(minimum_d8_exclusive)
        ),
        "candidate_manifest_sha256": artifact.candidate_manifest_sha256,
        "teacher_manifest_sha256": artifact.teacher_manifest_sha256,
        "candidate_receipt_sha256": artifact.candidate_receipt_sha256,
        "teacher_receipt_sha256": artifact.teacher_receipt_sha256,
        "verified_session_law_sha256": VERIFIED_SESSION_LAW_SHA256,
        "model_arrays_conversion_law_sha256":
            MODEL_ARRAYS_CONVERSION_LAW_SHA256,
        "diagnostic_plane_law_sha256": DIAGNOSTIC_PLANE_LAW_SHA256,
        "producer_source_tree_sha256": source_tree,
        "substrate_root_sha256": C.object_sha256(str(root.resolve())),
    })


def _cold_asset_window_semantic(
    corpus: EntryCorpus, observer: DiagnosticCorpusObserver,
) -> Mapping[str, Any]:
    receipt = corpus.receipt
    observed = observer.sessions
    return MappingProxyType({
        "schema": COLD_ASSET_WINDOW_SCHEMA,
        "corpus_window": dict(receipt["corpus_window"]),
        "sessions": int(receipt["sessions"]),
        "candidate_batches": int(receipt["candidate_batches"]),
        "clear_ready_candidates": int(receipt["clear_ready_candidates"]),
        "session_stream_receipt_aggregate_sha256":
            receipt["session_stream_receipt_aggregate_sha256"],
        "corpus_source_lineage_sha256":
            receipt["corpus_source_lineage_sha256"],
        "teacher_store_sha256": receipt["teacher_store_sha256"],
        "session_specs_sha256": C.object_sha256(receipt["session_specs"]),
        "verified_session_count": int(
            receipt["verified_session_warm_hits"]
            + receipt["verified_session_cold_publishes"]
        ),
        "model_array_bytes": int(
            receipt["model_array_bytes_materialized"]
            + receipt["model_array_bytes_reused"]
        ),
        "diagnostic_session_count": len(observed),
        "diagnostic_plane_bytes": sum(int(
            row.receipt["diagnostic_plane_bytes"]
        ) for row in observed),
    })


def _cold_asset_window_execution(
    corpus: EntryCorpus, observer: DiagnosticCorpusObserver,
) -> Mapping[str, Any]:
    receipt = corpus.receipt
    observed = observer.sessions
    diagnostic_hits = sum(
        row.receipt.get("diagnostic_plane_durable_hit") is True
        for row in observed
    )
    diagnostic_reused = sum(
        int(row.receipt["diagnostic_plane_bytes"])
        for row in observed
        if row.receipt.get("diagnostic_plane_durable_hit") is True
    )
    diagnostic_total = sum(int(
        row.receipt["diagnostic_plane_bytes"]
    ) for row in observed)
    return MappingProxyType({
        "physical_full_pack_opens": int(receipt["physical_full_pack_opens"]),
        "model_array_physical_fills": int(
            receipt["model_array_physical_fills"]),
        "verified_session_durable_hits": int(
            receipt["verified_session_warm_hits"]),
        "verified_session_cold_publishes": int(
            receipt["verified_session_cold_publishes"]),
        "diagnostic_plane_durable_hits": int(diagnostic_hits),
        "model_array_bytes_materialized": int(
            receipt["model_array_bytes_materialized"]),
        "model_array_bytes_reused": int(
            receipt["model_array_bytes_reused"]),
        "diagnostic_plane_bytes_materialized": int(
            diagnostic_total - diagnostic_reused),
        "diagnostic_plane_bytes_reused": int(diagnostic_reused),
    })


def _validate_cold_asset_marker(product: Any) -> Mapping[str, Any]:
    try:
        semantic = product.receipt["semantic"]
        producer = product.receipt["producer"]
        arrays = product.arrays
        valid = (
            isinstance(semantic, Mapping)
            and semantic.get("schema") == COLD_ASSET_WINDOW_SCHEMA
            and isinstance(producer, Mapping)
            and producer == {
                "schema": COLD_ASSET_WINDOW_SCHEMA,
                "process_start_method": "spawn",
                "process_isolated": True,
                "cuda_initialized": False,
            }
            and len(arrays) == 1
            and arrays[0].shape == (1,)
            and arrays[0].dtype == np.dtype(np.uint8)
            and int(arrays[0][0]) == 1
        )
        if not valid:
            raise C.EntryV2Refusal("isolated asset-window marker semantic differs")
        return dict(semantic)
    finally:
        product.close()


_ISOLATED_DURABLE_STORES: dict[str, DurableEntryV2Store] = {}


def _isolated_durable_store(root: Path) -> DurableEntryV2Store:
    key = str(root.resolve())
    store = _ISOLATED_DURABLE_STORES.get(key)
    if store is None:
        store = DurableEntryV2Store(Path(key))
        _ISOLATED_DURABLE_STORES[key] = store
    return store


def _isolated_asset_window_producer(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    """Spawn worker: publish one asset/window, never train or initialize CUDA."""
    if torch.cuda.is_initialized():
        raise C.EntryV2Refusal("isolated corpus worker inherited CUDA state")
    root = Path(str(payload["substrate_root"])).resolve()
    durable_root = Path(str(payload["durable_root"])).resolve()
    asset = str(payload["asset"])
    maximum_d8 = int(payload["maximum_d8"])
    minimum_raw = payload.get("minimum_d8_exclusive")
    minimum_d8 = None if minimum_raw is None else int(minimum_raw)
    artifacts = _artifact_sets(root)
    artifact = next((item for item in artifacts if item.asset == asset), None)
    if artifact is None:
        raise C.EntryV2Refusal("isolated corpus worker asset is absent")
    marker_identity = _cold_asset_window_identity(
        root, artifact, asset, maximum_d8, minimum_d8,
    )
    store = _isolated_durable_store(durable_root)
    existing = store.load(
        "verified-sessions", marker_identity, COLD_ASSET_WINDOW_LAW_SHA256,
    )
    if existing is not None:
        semantic = _validate_cold_asset_marker(existing)
        return {
            "asset": asset,
            "marker_hit": True,
            "marker_semantic_sha256": C.object_sha256(semantic),
            "semantic": semantic,
            "execution": None,
        }

    forecasts = _forecast_provider(root)
    context = _context_repository(asset)
    cache = SessionArrayCache(PRODUCTION_ARRAY_CACHE_BYTES, durable_store=store)
    observer = DiagnosticCorpusObserver(
        asset,
        truth_end_d8=maximum_d8,
        derived_end_d8=min(20221230, maximum_d8),
        corpus_maximum_d8=maximum_d8,
        minimum_d8_exclusive=minimum_d8,
        durable_store=store,
    )
    try:
        corpus = build_corpus(
            (artifact,), {asset: context},
            AssetScopedForecastProvider(forecasts, asset),
            require_assets=(asset,), array_cache=cache,
            diagnostic_observer=observer, maximum_d8=maximum_d8,
            minimum_d8_exclusive=minimum_d8,
        )
        if torch.cuda.is_initialized():
            raise C.EntryV2Refusal("isolated corpus worker initialized CUDA")
        semantic = _cold_asset_window_semantic(corpus, observer)
        execution = _cold_asset_window_execution(corpus, observer)
        product = store.publish(
            "verified-sessions", marker_identity,
            COLD_ASSET_WINDOW_LAW_SHA256,
            (np.ones((1,), dtype=np.uint8),),
            semantic=semantic,
            producer={
                "schema": COLD_ASSET_WINDOW_SCHEMA,
                "process_start_method": "spawn",
                "process_isolated": True,
                "cuda_initialized": False,
            },
        )
        marker_semantic = _validate_cold_asset_marker(product)
        return {
            "asset": asset,
            "marker_hit": False,
            "marker_semantic_sha256": C.object_sha256(marker_semantic),
            "semantic": dict(marker_semantic),
            "execution": dict(execution),
        }
    finally:
        observer.close()
        cache.close()


class ColdAssetProcessPool:
    """Persistent spawned workers shared by all chronological corpus windows."""

    def __init__(self) -> None:
        if torch.cuda.is_initialized():
            raise C.EntryV2Refusal(
                "cold asset process pool must be created before CUDA initialization"
            )
        self._executor: ProcessPoolExecutor | None = ProcessPoolExecutor(
            max_workers=len(C.ASSETS),
            mp_context=multiprocessing.get_context("spawn"),
        )

    def prepare(
        self, substrate_root: Path, durable_store: DurableEntryV2Store, *,
        maximum_d8: int, minimum_d8_exclusive: int | None,
    ) -> Mapping[str, Mapping[str, Any]]:
        if self._executor is None:
            raise C.EntryV2Refusal("cold asset process pool is closed")
        payloads = ({
            "substrate_root": str(Path(substrate_root).resolve()),
            "durable_root": str(durable_store.root),
            "asset": asset,
            "maximum_d8": int(maximum_d8),
            "minimum_d8_exclusive": minimum_d8_exclusive,
        } for asset in sorted(C.ASSETS))
        futures = {
            self._executor.submit(_isolated_asset_window_producer, payload):
                str(payload["asset"])
            for payload in payloads
        }
        results: dict[str, Mapping[str, Any]] = {}
        try:
            for future in as_completed(tuple(futures)):
                asset = futures[future]
                value = future.result()
                if value.get("asset") != asset:
                    raise C.EntryV2Refusal(
                        "isolated asset-window worker result is permuted"
                    )
                results[asset] = MappingProxyType(dict(value))
        except BaseException:
            self.abort()
            raise
        if set(results) != set(C.ASSETS):
            self.abort()
            raise C.EntryV2Refusal(
                "isolated asset-window worker roster is incomplete"
            )
        return MappingProxyType(results)

    def abort(self) -> None:
        executor, self._executor = self._executor, None
        if executor is None:
            return
        for process in tuple(getattr(executor, "_processes", {}).values()):
            process.terminate()
        executor.shutdown(wait=True, cancel_futures=True)

    def close(self) -> None:
        executor, self._executor = self._executor, None
        if executor is not None:
            executor.shutdown(wait=True, cancel_futures=True)


def _bind_isolated_process_lifecycle(
    diagnostic: DiagnosticCorpus,
    results: Mapping[str, Mapping[str, Any]],
) -> DiagnosticCorpus:
    """Replace parent warm-cache counters with actual producer invocation work."""
    if set(results) != set(C.ASSETS):
        raise C.EntryV2Refusal("isolated lifecycle asset roster is incomplete")
    execution_names = (
        "physical_full_pack_opens", "model_array_physical_fills",
        "verified_session_durable_hits", "verified_session_cold_publishes",
        "diagnostic_plane_durable_hits", "model_array_bytes_materialized",
        "model_array_bytes_reused", "diagnostic_plane_bytes_materialized",
        "diagnostic_plane_bytes_reused",
    )
    aggregate = {name: 0 for name in execution_names}
    provenance: dict[str, Any] = {}
    semantic_verified = 0
    semantic_model_bytes = 0
    semantic_diagnostic_sessions = 0
    semantic_diagnostic_bytes = 0
    for asset in sorted(C.ASSETS):
        value = results[asset]
        semantic = value.get("semantic")
        if (not isinstance(semantic, Mapping)
                or semantic.get("schema") != COLD_ASSET_WINDOW_SCHEMA
                or C.object_sha256(semantic)
                    != value.get("marker_semantic_sha256")):
            raise C.EntryV2Refusal(
                "isolated lifecycle marker semantic/hash differs"
            )
        semantic_verified += int(semantic["verified_session_count"])
        semantic_model_bytes += int(semantic["model_array_bytes"])
        semantic_diagnostic_sessions += int(semantic["diagnostic_session_count"])
        semantic_diagnostic_bytes += int(semantic["diagnostic_plane_bytes"])
        if value.get("marker_hit") is True:
            execution = {
                "physical_full_pack_opens": 0,
                "model_array_physical_fills": 0,
                "verified_session_durable_hits":
                    int(semantic["verified_session_count"]),
                "verified_session_cold_publishes": 0,
                "diagnostic_plane_durable_hits":
                    int(semantic["diagnostic_session_count"]),
                "model_array_bytes_materialized": 0,
                "model_array_bytes_reused": int(semantic["model_array_bytes"]),
                "diagnostic_plane_bytes_materialized": 0,
                "diagnostic_plane_bytes_reused":
                    int(semantic["diagnostic_plane_bytes"]),
            }
        else:
            execution = value.get("execution")
            if not isinstance(execution, Mapping):
                raise C.EntryV2Refusal(
                    "isolated lifecycle cold execution is absent"
                )
        if (set(execution) != set(execution_names)
                or any(type(execution[name]) is not int
                       or int(execution[name]) < 0 for name in execution_names)):
            raise C.EntryV2Refusal(
                "isolated lifecycle execution counters are invalid"
            )
        for name in execution_names:
            aggregate[name] += int(execution[name])
        provenance[asset] = {
            "marker_hit": bool(value["marker_hit"]),
            "marker_semantic_sha256": value["marker_semantic_sha256"],
            "execution": dict(execution),
        }

    corpus_receipt = diagnostic.corpus.receipt
    body = dict(diagnostic.receipt)
    if (semantic_verified != int(corpus_receipt["verified_session_warm_hits"])
            or semantic_model_bytes
                != int(corpus_receipt["model_array_bytes_reused"])
            or semantic_diagnostic_sessions != len(diagnostic.sessions)
            or semantic_diagnostic_bytes != int(body["diagnostic_plane_bytes"])):
        raise C.EntryV2Refusal(
            "isolated lifecycle semantic totals differ from parent reconstruction"
        )
    if (aggregate["model_array_physical_fills"]
            > aggregate["physical_full_pack_opens"]
            or aggregate["physical_full_pack_opens"]
            > aggregate["verified_session_cold_publishes"]):
        raise C.EntryV2Refusal(
            "isolated lifecycle one-open/fill ordering is impossible"
        )
    has_cold = any(aggregate[name] > 0 for name in (
        "verified_session_cold_publishes", "physical_full_pack_opens",
        "model_array_physical_fills", "model_array_bytes_materialized",
        "diagnostic_plane_bytes_materialized",
    ))
    has_reuse = any(aggregate[name] > 0 for name in (
        "verified_session_durable_hits", "diagnostic_plane_durable_hits",
        "model_array_bytes_reused", "diagnostic_plane_bytes_reused",
    ))
    if has_cold:
        lifecycle_class = LIFECYCLE_COLD
    elif has_reuse:
        lifecycle_class = LIFECYCLE_WARM
    else:
        raise C.EntryV2Refusal("isolated lifecycle records no corpus work")
    warm = lifecycle_class == LIFECYCLE_WARM
    old_lifecycle = body.get(LIFECYCLE_PROVENANCE_RECEIPT_KEY)
    if not isinstance(old_lifecycle, Mapping):
        raise C.EntryV2Refusal("parent lifecycle provenance is absent")
    lifecycle = {
        "schema": LIFECYCLE_PROVENANCE_SCHEMA,
        "cold_or_warm": lifecycle_class,
        "warm_corpus_ready": warm,
        **aggregate,
        "corpus_ready_elapsed_milestone_source":
            CORPUS_READY_MILESTONE_SOURCE,
        "cumulative_window_identity_sha256":
            old_lifecycle["cumulative_window_identity_sha256"],
    }
    body.update({
        "physical_full_pack_opens": aggregate["physical_full_pack_opens"],
        "model_array_physical_fills": aggregate["model_array_physical_fills"],
        "warm_corpus_ready": warm,
        LIFECYCLE_PROVENANCE_RECEIPT_KEY: lifecycle,
        "isolated_asset_window_execution": provenance,
    })
    body.pop("receipt_sha256", None)
    body["receipt_sha256"] = C.object_sha256(body)
    return replace(diagnostic, receipt=MappingProxyType(body))


def _build_parallel_asset_corpus(
    artifacts: Sequence[AssetArtifactSet],
    contexts: Mapping[str, CausalContextRepository],
    forecasts: QRE2ForecastProvider,
    array_cache: SessionArrayCache | None = None,
    diagnostic_observers: Mapping[str, DiagnosticSessionObserver] | None = None,
    maximum_d8: int | None = None,
    minimum_d8_exclusive: int | None = None,
    require_durable_window: bool = False,
) -> EntryCorpus:
    """Run the three independent verified asset scans concurrently."""

    by_asset = {item.asset: item for item in artifacts}
    if set(by_asset) != set(C.ASSETS):
        raise C.EntryV2Refusal("parallel corpus artifacts do not cover all assets")
    if diagnostic_observers is not None and set(diagnostic_observers) != set(C.ASSETS):
        raise C.EntryV2Refusal(
            "diagnostic observers must cover the exact production asset roster"
        )

    cancel = Event()

    def build_one(asset: str) -> EntryCorpus:
        return build_corpus(
            (by_asset[asset],),
            {asset: contexts[asset]},
            AssetScopedForecastProvider(forecasts, asset),
            require_assets=(asset,),
            cancel_event=cancel,
            array_cache=array_cache,
            diagnostic_observer=(None if diagnostic_observers is None
                                 else diagnostic_observers[asset]),
            maximum_d8=maximum_d8,
            minimum_d8_exclusive=minimum_d8_exclusive,
            require_durable_window=require_durable_window,
        )

    # Detect any lane failure as soon as it completes so sibling scans observe
    # cancellation immediately.  Successful parts are still assembled only
    # in canonical asset order, so scheduling cannot enter a receipt or tensor
    # ordering.
    executor = ThreadPoolExecutor(
        max_workers=len(C.ASSETS), thread_name_prefix="entry-v2-corpus"
    )
    futures = {}
    try:
        for asset in sorted(C.ASSETS):
            futures[asset] = executor.submit(build_one, asset)
        asset_by_future = {future: asset for asset, future in futures.items()}
        results = {}
        for future in as_completed(tuple(asset_by_future)):
            asset = asset_by_future[future]
            results[asset] = future.result()
        parts = tuple(results[asset] for asset in sorted(C.ASSETS))
    except BaseException:
        cancel.set()
        for future in futures.values():
            future.cancel()
        executor.shutdown(wait=True, cancel_futures=True)
        raise
    else:
        executor.shutdown(wait=True)
    return merge_asset_corpora(
        parts, maximum_d8=maximum_d8,
        minimum_d8_exclusive=minimum_d8_exclusive,
    )


def _host_mem_available_bytes() -> int:
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                fields = line.split()
                if len(fields) == 3 and fields[2] == "kB":
                    return int(fields[1]) * 1024
    except (OSError, ValueError) as exc:
        raise C.EntryV2Refusal("cannot determine MemAvailable") from exc
    raise C.EntryV2Refusal("cannot determine MemAvailable")


def _cgroup_available_bytes() -> int | None:
    """Return the effective cgroup-v2 headroom when one is configured.

    ``/proc/meminfo`` describes the host and can materially exceed a
    container/job limit.  A production admission that ignores ``memory.max``
    can therefore pass and later be killed by the kernel without a Python
    traceback.  ``None`` means this process has no finite cgroup-v2 limit.
    """
    maximum_path = Path("/sys/fs/cgroup/memory.max")
    current_path = Path("/sys/fs/cgroup/memory.current")
    try:
        maximum_raw = maximum_path.read_text().strip()
        if maximum_raw == "max":
            return None
        maximum = int(maximum_raw)
        current = int(current_path.read_text().strip())
        stat_fields = {
            fields[0]: int(fields[1])
            for line in Path("/sys/fs/cgroup/memory.stat").read_text().splitlines()
            if len(fields := line.split()) == 2
        }
    except (OSError, ValueError) as exc:
        raise C.EntryV2Refusal("cannot determine cgroup memory headroom") from exc
    if maximum <= 0 or current < 0:
        raise C.EntryV2Refusal("cgroup memory identity is invalid")
    # Clean file-backed cache is reclaimable by the kernel and must not be
    # treated like pinned anonymous memory.  Dirty/writeback and shmem pages
    # are deliberately excluded from this credit.
    clean_file = max(
        0,
        stat_fields.get("file", 0)
        - stat_fields.get("shmem", 0)
        - stat_fields.get("file_dirty", 0)
        - stat_fields.get("file_writeback", 0),
    )
    return min(maximum, max(0, maximum - current) + clean_file)


def _mem_available_bytes() -> int:
    host = _host_mem_available_bytes()
    cgroup = _cgroup_available_bytes()
    return host if cgroup is None else min(host, cgroup)


def effective_memory_available_bytes() -> int:
    """Public production admission value: host and cgroup, whichever binds."""
    return _mem_available_bytes()


def _planned_array_bytes(sources: Sequence[SessionEventSource]) -> int:
    identities: dict[str, bytes] = {}
    total = 0
    for source in sources:
        key = source.receipt.receipt_sha256
        identity = source.receipt.canonical_bytes()
        previous = identities.get(key)
        if previous is not None:
            if previous != identity:
                raise C.EntryV2Refusal(
                    "session array cache receipt-hash collision"
                )
            continue
        identities[key] = identity
        total += SessionArrayCache.planned_bytes(source)
    return total


def _source_process_payload(source: SessionEventSource) -> Mapping[str, Any]:
    return {
        name: getattr(source, name) for name in (
            "qre2_path", "source_sha256", "sidecar_sha256", "asset", "d8",
            "locked_iid", "open_utc", "close_utc", "event_count", "max_cutoff",
            "source_size_bytes", "source_device", "source_inode",
            "source_mtime_ns", "source_ctime_ns",
        )
    }


def _isolated_array_fill(
    payload: Mapping[str, Any],
) -> tuple[Any, Any, tuple[int, int]]:
    """Spawn-safe conversion worker; imports no learner and never initializes CUDA."""
    source = SessionEventSource(**dict(payload))
    with source.open_arrays() as arrays:
        continuous = arrays[0].copy(order="C")
        categorical = arrays[1].copy(order="C")
    measured = source.measurements.snapshot()
    return continuous, categorical, (
        int(measured["physical_full_pack_opens"]),
        int(measured["model_array_physical_fills"]),
    )


def _preload_session_arrays(
    corpus: EntryCorpus, cache: SessionArrayCache, *,
    additional_sources: Sequence[SessionEventSource] = (),
) -> int:
    union = tuple(spec.source for spec in corpus.sessions) + tuple(additional_sources)
    by_receipt: dict[str, SessionEventSource] = {}
    for source in union:
        prior = by_receipt.get(source.receipt.receipt_sha256)
        if prior is not None and prior.receipt.canonical_bytes() != source.receipt.canonical_bytes():
            raise C.EntryV2Refusal("preload union receipt-hash collision")
        by_receipt[source.receipt.receipt_sha256] = source
    sources = tuple(sorted(
        by_receipt.values(),
        key=lambda source: (
            source.asset, source.d8, str(source.qre2_path),
            source.receipt.receipt_sha256,
        ),
    ))
    if any(source.array_cache is not cache for source in sources):
        raise C.EntryV2Refusal("production sessions do not share one array cache")
    if (not isinstance(cache, SessionArrayCache)
            or cache.durable_store is None):
        # A child process cannot publish into a process-local cache.  Structural
        # caches and explicitly non-durable SessionArrayCaches therefore retain
        # the bounded in-process compatibility path.  Production supplies the
        # durable store and takes the isolated process path below.
        required = _planned_array_bytes(sources)
        if required > cache.capacity_bytes:
            raise C.EntryV2Refusal(
                "planned session arrays exceed production cache capacity")
        if _mem_available_bytes() < required + PRODUCTION_MEMORY_RESERVE_BYTES:
            raise C.EntryV2Refusal(
                "effective MemAvailable is below the production cache admission reserve")
        def fill_compat(source: SessionEventSource) -> None:
            with source.open_arrays():
                pass
        executor = ThreadPoolExecutor(max_workers=4)
        futures = {executor.submit(fill_compat, source): source
                   for source in sources}
        try:
            for future in as_completed(tuple(futures)):
                future.result()
        except BaseException:
            for future in futures:
                future.cancel()
            executor.shutdown(wait=True, cancel_futures=True)
            if hasattr(cache, "clear"):
                cache.clear()
            raise
        else:
            executor.shutdown(wait=True)
        if cache.bytes_used != required:
            if hasattr(cache, "clear"):
                cache.clear()
            raise C.EntryV2Refusal("production array cache byte accounting drift")
        return required
    resident_before = cache.resident_receipts()
    delta = tuple(source for source in sources
                  if source.receipt.receipt_sha256 not in resident_before)
    delta_required = _planned_array_bytes(delta)
    required = cache.bytes_used + delta_required
    if required > cache.capacity_bytes:
        raise C.EntryV2Refusal(
            "planned session arrays exceed production cache capacity"
        )
    resident_required = (0 if not delta else (
        PRODUCTION_DISK_CACHE_MEMORY_RESERVE_BYTES
        if getattr(cache, "disk_backed", False)
        else delta_required + PRODUCTION_MEMORY_RESERVE_BYTES
    ))
    if _mem_available_bytes() < resident_required:
        raise C.EntryV2Refusal(
            "effective MemAvailable is below the production cache admission reserve"
        )
    admitted: set[str] = set()
    try:
        durable_hits = []
        cold = []
        for source in delta:
            store = cache.durable_store
            if store is not None and store.has_product(
                    "session-arrays", source.durable_identity(),
                    source.receipt.conversion_law_sha256):
                durable_hits.append(source)
            else:
                cold.append(source)
        for source in durable_hits:
            with source.open_arrays():
                pass
            admitted.add(source.receipt.receipt_sha256)
        # Cold conversion is isolated before CUDA initialization.  At most one
        # bounded worker wave is resident, and the parent publishes results in
        # canonical source order regardless of completion order.
        for offset in range(0, len(cold), 4):
            wave = cold[offset:offset + 4]
            executor = ProcessPoolExecutor(
                max_workers=len(wave),
                mp_context=multiprocessing.get_context("spawn"),
            )
            futures = {
                executor.submit(_isolated_array_fill, _source_process_payload(source)):
                    source for source in wave
            }
            results = {}
            try:
                for future in as_completed(tuple(futures)):
                    source = futures[future]
                    results[source.receipt.receipt_sha256] = future.result()
            except BaseException:
                for future in futures:
                    future.cancel()
                for process in tuple(getattr(executor, "_processes", {}).values()):
                    process.terminate()
                executor.shutdown(wait=True, cancel_futures=True)
                raise
            else:
                executor.shutdown(wait=True)
            for source in wave:
                continuous, categorical, measurements = results[
                    source.receipt.receipt_sha256]
                if measurements != (1, 1):
                    raise C.EntryV2Refusal(
                        "isolated array producer provenance differs"
                    )
                continuous.setflags(write=False)
                categorical.setflags(write=False)
                source.measurements.record_full_pack_open()
                source.measurements.record_model_array_fill()
                cache.publish_verified(source, continuous, categorical)
                admitted.add(source.receipt.receipt_sha256)
    except BaseException as exc:
        cache.discard_receipts(admitted)
        if isinstance(exc, C.EntryV2Refusal):
            raise
        raise C.EntryV2Refusal("production session array preload failed") from exc
    if cache.bytes_used != required:
        cache.discard_receipts(admitted)
        raise C.EntryV2Refusal("production array cache byte accounting drift")
    return required


def build_production_corpus_stage(
    substrate_root: Path,
    *,
    array_cache: SessionArrayCache | None = None,
    diagnostic_observers: Mapping[str, DiagnosticSessionObserver] | None = None,
    maximum_d8: int | None = None,
    minimum_d8_exclusive: int | None = None,
    require_durable_window: bool = False,
) -> CorpusStage:
    root = Path(substrate_root).resolve()
    if root != C.CACHE_ROOT.resolve():
        raise C.EntryV2Refusal("production runtime received the wrong substrate root")
    stage_pins = {
        asset: dict(_native_stage_pins(root, asset)) for asset in C.ASSETS
    }
    artifacts = _artifact_sets(root)
    ceilings = _ceiling_pins(root, artifacts)
    forecasts = _forecast_provider(root)
    contexts = _contexts()
    corpus = _build_parallel_asset_corpus(
        artifacts, contexts, forecasts, array_cache=array_cache,
        diagnostic_observers=diagnostic_observers,
        maximum_d8=maximum_d8,
        minimum_d8_exclusive=minimum_d8_exclusive,
        require_durable_window=require_durable_window,
    )
    if array_cache is not None:
        observer_sources = tuple(
            session.source for observer in (diagnostic_observers or {}).values()
            for session in getattr(observer, "sessions", ())
        )
        _preload_session_arrays(corpus, array_cache,
                                additional_sources=observer_sources)
    return CorpusStage(corpus, _history(root, stage_pins, ceilings))


class _ProductionCorpusBuilder:
    """Own one cache across corpus construction and all training folds."""

    def __init__(self, root: Path, array_cache: SessionArrayCache) -> None:
        self.root = root
        self.array_cache = array_cache

    def __call__(self, requested: Path) -> CorpusStage:
        if Path(requested).resolve() != self.root:
            self.array_cache.clear()
            raise C.EntryV2Refusal("driver/runtime substrate binding differs")
        try:
            return build_production_corpus_stage(
                self.root, array_cache=self.array_cache
            )
        except BaseException:
            self.array_cache.clear()
            raise

    def close(self) -> None:
        self.array_cache.close()


@dataclass
class ProductionDiagnosticStage:
    corpus_stage: CorpusStage
    diagnostic_corpus: DiagnosticCorpus
    observers: Mapping[str, DiagnosticCorpusObserver]
    plane_backing_root: Path
    array_cache: SessionArrayCache
    durable_store: DurableEntryV2Store | None
    substrate_root: Path
    window_observers: tuple[Mapping[str, DiagnosticCorpusObserver], ...]
    cold_process_pool: ColdAssetProcessPool | None = None
    _owns_observers: bool = True
    _closed: bool = False

    @property
    def lifecycle_provenance(self) -> Mapping[str, Any]:
        value = self.diagnostic_corpus.receipt.get(
            LIFECYCLE_PROVENANCE_RECEIPT_KEY
        )
        if (not isinstance(value, Mapping)
                or value.get("schema") != LIFECYCLE_PROVENANCE_SCHEMA):
            raise C.EntryV2Refusal(
                "production diagnostic lifecycle provenance is absent"
            )
        return value

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if not self._owns_observers:
            return
        for window in self.window_observers:
            for observer in window.values():
                observer.close()
        self._owns_observers = False


def build_production_diagnostic_stage(
    substrate_root: Path = C.CACHE_ROOT, *,
    array_cache: SessionArrayCache | None = None,
    maximum_d8: int | None = None,
    minimum_d8_exclusive: int | None = None,
    durable_store: DurableEntryV2Store | None = None,
    cold_process_pool: ColdAssetProcessPool | None = None,
    pre_finalize_validator: Callable[[CorpusStage], None] | None = None,
) -> ProductionDiagnosticStage:
    if array_cache is None or not array_cache.disk_backed:
        raise C.EntryV2Refusal(
            "production diagnostic requires the disk-backed one-load array cache"
        )
    cache = array_cache
    resident_before = cache.resident_receipts()
    if durable_store is not None:
        if cache.durable_store is not durable_store:
            raise C.EntryV2Refusal(
                "production diagnostic cache/store ownership differs"
            )
        try:
            durable_store.root.relative_to(C.CACHE_ROOT.resolve())
        except ValueError:
            pass
        else:
            raise C.EntryV2Refusal(
                "durable store must be outside production/run substrate roots"
            )
        plane_root = durable_store.root / "diagnostic-planes"
    else:
        if not (cache.backing_dir is not None):
            raise C.EntryV2Refusal(
                "internal invariant failed: cache.backing_dir is not None")
        plane_root = (
            cache.backing_dir.parent
            / f"{cache.backing_dir.name}.diagnostic-planes"
        )
        if plane_root.exists():
            raise C.EntryV2Refusal("diagnostic plane cache already exists")
        plane_root.mkdir(mode=0o700)
    resolved_maximum_d8 = (
        C.DEVELOPMENT_END_D8 if maximum_d8 is None else int(maximum_d8)
    )
    C.guard_date(resolved_maximum_d8)
    if resolved_maximum_d8 > C.DEVELOPMENT_END_D8:
        raise C.EntryV2Refusal("diagnostic maximum exceeds the development window")
    require_durable_window = cold_process_pool is not None
    cold_process_results: Mapping[str, Mapping[str, Any]] | None = None
    if require_durable_window:
        if durable_store is None:
            raise C.EntryV2Refusal(
                "isolated cold asset production requires the durable store"
            )
        cold_process_results = cold_process_pool.prepare(
            Path(substrate_root).resolve(), durable_store,
            maximum_d8=resolved_maximum_d8,
            minimum_d8_exclusive=minimum_d8_exclusive,
        )
    observers = {
        asset: DiagnosticCorpusObserver(
            asset,
            truth_end_d8=resolved_maximum_d8,
            derived_end_d8=min(20221230, resolved_maximum_d8),
            corpus_maximum_d8=resolved_maximum_d8,
            minimum_d8_exclusive=minimum_d8_exclusive,
            backing_dir=(None if durable_store is not None else plane_root / asset),
            durable_store=durable_store,
        )
        for asset in C.ASSETS
    }
    try:
        stage = build_production_corpus_stage(
            substrate_root, array_cache=cache, diagnostic_observers=observers,
            maximum_d8=resolved_maximum_d8,
            minimum_d8_exclusive=minimum_d8_exclusive,
            require_durable_window=require_durable_window,
        )
        # Learning-support and oracle-attainability checks belong before the
        # expensive candidate-level atlas finalizer.  The callback is optional
        # for ordinary corpus users, but the production sufficiency resource
        # supplies an exact real-data firewall.  It may inspect only the
        # already-built causal corpus and cannot replace or mutate it.
        if pre_finalize_validator is not None:
            pre_finalize_validator(stage)
        diagnostic = finalize_diagnostic_corpus(stage.corpus, observers)
        if cold_process_results is not None:
            diagnostic = _bind_isolated_process_lifecycle(
                diagnostic, cold_process_results,
            )
        stage = replace(stage, corpus=diagnostic.corpus)
        if not diagnostic.receipt["diagnostic_planes_disk_backed"]:
            raise C.EntryV2Refusal("production diagnostic planes are not disk-backed")
        frozen_observers = MappingProxyType(observers)
        return ProductionDiagnosticStage(
            stage, diagnostic, frozen_observers, plane_root, cache,
            durable_store, Path(substrate_root).resolve(), (frozen_observers,),
            cold_process_pool,
        )
    except BaseException:
        for observer in observers.values():
            observer.close()
        cache.discard_receipts(cache.resident_receipts() - resident_before)
        if durable_store is None:
            shutil.rmtree(plane_root, ignore_errors=True)
        raise


def extend_production_diagnostic_stage(
    stage: ProductionDiagnosticStage, *, new_maximum_d8: int,
) -> ProductionDiagnosticStage:
    """Consume one live owner and append exactly ``(old_max,new_max]``."""
    if not isinstance(stage, ProductionDiagnosticStage) or stage._closed:
        raise C.EntryV2Refusal("production diagnostic stage is not a live owner")
    if not stage._owns_observers:
        raise C.EntryV2Refusal("production diagnostic ownership was transferred")
    if stage.durable_store is None or stage.array_cache.durable_store is not (
            stage.durable_store):
        raise C.EntryV2Refusal(
            "incremental diagnostic extension requires the same durable owner"
        )
    old_maximum = int(stage.corpus_stage.corpus.receipt[
        "corpus_window"]["maximum_d8"])
    new_maximum = int(new_maximum_d8)
    C.guard_date(new_maximum)
    if new_maximum <= old_maximum or new_maximum > C.DEVELOPMENT_END_D8:
        raise C.EntryV2Refusal("diagnostic extension maximum is not later development")
    extension: ProductionDiagnosticStage | None = None
    resident_before = stage.array_cache.resident_receipts()
    try:
        extension_kwargs: dict[str, Any] = {
            "array_cache": stage.array_cache,
            "maximum_d8": new_maximum,
            "minimum_d8_exclusive": old_maximum,
            "durable_store": stage.durable_store,
        }
        if stage.cold_process_pool is not None:
            extension_kwargs["cold_process_pool"] = stage.cold_process_pool
        extension = build_production_diagnostic_stage(
            stage.substrate_root, **extension_kwargs,
        )
        merged_corpus = merge_chronological_corpora((
            stage.corpus_stage.corpus, extension.corpus_stage.corpus,
        ))
        merged_diagnostic = merge_diagnostic_corpora(merged_corpus, (
            stage.diagnostic_corpus, extension.diagnostic_corpus,
        ))
        # History authority is full-manifest global authority and must be
        # byte-identical between intervals; it is not fabricated or summed.
        if dict(stage.corpus_stage.history) != dict(extension.corpus_stage.history):
            raise C.EntryV2Refusal("diagnostic extension history authority differs")
        merged_stage = CorpusStage(merged_corpus, stage.corpus_stage.history)
        windows = stage.window_observers + extension.window_observers
        stage._owns_observers = False
        extension._owns_observers = False
        return ProductionDiagnosticStage(
            merged_stage, merged_diagnostic, extension.observers,
            stage.plane_backing_root, stage.array_cache, stage.durable_store,
            stage.substrate_root, windows,
            stage.cold_process_pool,
        )
    except BaseException:
        if extension is not None:
            extension.close()
        stage.array_cache.discard_receipts(
            stage.array_cache.resident_receipts() - resident_before
        )
        raise


def _system_factory(config: TrainingConfig) -> EntryLearningSystem:
    torch.manual_seed(config.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(config.seed)
    encoder = FullPrefixEntryModel(
        n_event_continuous=len(CONTINUOUS_FIELDS),
        n_candidate_features=len(CANDIDATE_FEATURE_SCHEMA),
        n_context_continuous=CONTEXT_TENSOR_WIDTH,
        n_context_types=len(CONTEXT_TYPE_ID),
        event_category_sizes=CATEGORY_SIZES,
        n_value_bins=5,
    )
    return EntryLearningSystem(encoder, n_phase_classes=config.n_phase_classes)


def build_production_runtime(
    substrate_root: Path = C.CACHE_ROOT,
    config: TrainingConfig = FROZEN_PRODUCTION_CONFIG,
    *, winner_system_factory: Any | None = None,
    winner_policy_kind: str | None = None,
    winner_policy_factory: Any | None = None,
    winner_bundle: Any | None = None,
    winner_resources: Any | None = None,
) -> DriverRuntime:
    if config != FROZEN_PRODUCTION_CONFIG:
        raise C.EntryV2Refusal("production training configuration is frozen")
    root = Path(substrate_root).resolve()

    def no_rebuild(*_args: Any, **_kwargs: Any) -> Mapping[str, Any]:
        raise C.EntryV2Refusal(
            "production runtime is prebuilt-only; native source must not be rerun"
        )

    if winner_resources is not None:
        from .neural_winner_artifact import (
            load_winner_policy_factory, make_selected_winner_system_factory,
        )
        if getattr(winner_resources, "ownership_transferred", None) is not True:
            raise C.EntryV2Refusal(
                "winner runtime requires the transferred live diagnostic owner"
            )
        if any(value is not None for value in (
                winner_system_factory, winner_policy_kind,
                winner_policy_factory)):
            raise C.EntryV2Refusal(
                "winner resources cannot be mixed with separate weak adapters"
            )
        winner_system_factory = make_selected_winner_system_factory(winner_resources)
        winner_policy_kind = winner_resources.policy_kind
        if winner_policy_kind not in ("direct_neural", "catboost"):
            raise C.EntryV2Refusal("winner resources lack a selected policy kind")
        if winner_bundle is None:
            raise C.EntryV2Refusal(
                "winner runtime requires the independently loadable bundle"
            )
        if winner_bundle.architecture["decision_head_kind"] != winner_policy_kind:
            raise C.EntryV2Refusal("winner bundle/resource policy kinds differ")
        winner_policy_factory = load_winner_policy_factory(winner_bundle)
        corpus_stage = getattr(winner_resources, "context_corpus", None)
        if not callable(corpus_stage):
            raise C.EntryV2Refusal(
                "winner resources lack the shared one-open context_corpus builder"
            )
    else:
        corpus_stage = _ProductionCorpusBuilder(
            root, SessionArrayCache(PRODUCTION_ARRAY_CACHE_BYTES)
        )

    return DriverRuntime(
        cpp_wave=no_rebuild,
        context_corpus=corpus_stage,
        system_factory=lambda: _system_factory(config),
        config=config,
        winner_system_factory=winner_system_factory,
        winner_policy_kind=winner_policy_kind,
        policy_factory=winner_policy_factory,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run/resume the frozen Entry V2 pre-H2 production campaign"
    )
    parser.add_argument(
        "--run-root", required=True, type=Path,
        help="new immutable campaign root; must not be inside the substrate tree",
    )
    parser.add_argument(
        "--neural-acceptance", required=True, type=Path,
        help="immutable preheld fit-only neural-sufficiency acceptance receipt",
    )
    for option in ("e1", "e2", "e3", "winner-adoption"):
        parser.add_argument(f"--neural-{option}", required=True, type=Path)
    parser.add_argument("--neural-winner-bundle", required=True, type=Path)
    parser.add_argument("--neural-winner-integration", required=True, type=Path)
    parser.add_argument("--adopted-primary-e3-fold", required=True, type=Path)
    parser.add_argument(
        "--winner-resource-factory", required=True,
        help=("module:function returning the concrete one-open compact-atlas, "
              "expanded-event and selected policy resources"),
    )
    args = parser.parse_args(argv)
    substrate = C.CACHE_ROOT
    try:
        module_name, function_name = args.winner_resource_factory.split(":", 1)
        resource_factory = getattr(importlib.import_module(module_name), function_name)
        winner_resources = resource_factory(substrate, args.neural_winner_bundle)
    except Exception as exc:
        raise C.EntryV2Refusal(
            "concrete selected-winner resource factory could not be loaded"
        ) from exc
    from .neural_winner_artifact import load_winner_bundle
    winner_bundle = load_winner_bundle(args.neural_winner_bundle)
    runtime = build_production_runtime(
        substrate, winner_resources=winner_resources, winner_bundle=winner_bundle,
    )
    try:
        result = run_pre_h2_campaign(
            DriverPlan(args.run_root, prebuilt_substrate_root=substrate,
                       neural_acceptance_receipt=args.neural_acceptance,
                       neural_e1_receipt=args.neural_e1,
                       neural_e2_receipt=args.neural_e2,
                       neural_e3_receipt=args.neural_e3,
                       neural_winner_adoption_receipt=args.neural_winner_adoption,
                       neural_winner_bundle=args.neural_winner_bundle,
                       neural_winner_integration_receipt=
                           args.neural_winner_integration,
                       adopted_primary_e3_fold=args.adopted_primary_e3_fold),
            runtime,
        )
    finally:
        close = getattr(winner_resources, "close", None)
        if callable(close):
            close()
    print(json.dumps({
        "schema": "entry-v2-production-cli-result-v1",
        "run_root": str(args.run_root.resolve()),
        "campaign_receipt_sha256": result.campaign.receipt["receipt_sha256"],
        "oracle_preflight_receipt_sha256":
            result.oracle_preflight["receipt_sha256"],
        "accepted": result.audit_report["payload"]["passed"],
        "h2_permit": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "FROZEN_PRODUCTION_CONFIG", "PRODUCTION_ARRAY_CACHE_BYTES",
    "PRODUCTION_MEMORY_RESERVE_BYTES",
    "PRODUCTION_DISK_CACHE_MEMORY_RESERVE_BYTES",
    "COLD_ASSET_WINDOW_SCHEMA", "COLD_ASSET_WINDOW_LAW_SHA256",
    "ColdAssetProcessPool",
    "build_production_corpus_stage", "effective_memory_available_bytes",
    "ProductionDiagnosticStage", "build_production_diagnostic_stage",
    "extend_production_diagnostic_stage",
    "build_production_runtime", "main",
]
