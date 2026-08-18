#!/usr/bin/env python3
"""One-open diagnostic truth bridge for the Entry V2 sufficiency campaign.

The ordinary corpus remains the input/context authority.  This module observes
the already-open verified QRE2 pack once, publishes its bounded learner prefix
to the shared array cache, copies only typed truth columns, and later binds all
sessions to the global A-004 schedule before materializing the label atlas.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation, ROUND_CEILING
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
from types import MappingProxyType
from typing import Any, Mapping, Sequence

import numpy as np
import torch

from . import common as C
from .causal_label_atlas import (
    ActionMaskCause,
    AtlasRefusal,
    BoundaryReason,
    CandidateAnchor,
    CanonicalOutcome,
    CellAvailability,
    EndpointStatus,
    MaterializedAtlas,
    PNL_UNITS_PER_USD,
    SessionTruthIndex,
    merge_candidate_truth_atlases,
)
from .corpus import (
    CORPUS_WINDOW_LAW_SHA256,
    CORPUS_WINDOW_SCHEMA,
    DiagnosticSessionObserver,
    EntryCorpus,
)
from .diagnostic_inputs import (
    A004CounterfactualAtoms,
    ActionMaskReason,
    CandidateTruthBinding,
    DerivedEventFieldBuilder,
    DerivedEventFields,
    EventTruthColumns,
    build_a004_counterfactual_atoms,
    build_candidate_truth_bindings,
    build_event_truth_columns,
)
from .event_pack import EventPack
from .durable_store import DurableEntryV2Store, DurableProduct
from .selected_horizon_contract import (
    COORDINATES as SELECTED_HORIZON_COORDINATES,
    COVERAGE_LAW as SELECTED_HORIZON_COVERAGE_LAW,
    COVERAGE_LAW_SHA256 as SELECTED_HORIZON_COVERAGE_LAW_SHA256,
    COVERAGE_SCHEMA as SELECTED_HORIZON_COVERAGE_SCHEMA,
    SCHEMA_SHA256 as SELECTED_HORIZON_SCHEMA_SHA256,
    TARGET_LAW as SELECTED_HORIZON_TARGET_LAW,
    SelectedHorizonContractRefusal,
    selected_horizon_coverage_receipt,
    validate_selected_horizon_coverage,
)
from .session_stream import SessionEventSource


DIAGNOSTIC_CORPUS_SCHEMA = "entry-v2-neural-sufficiency-corpus-v7"
SELECTED_TARGET_CORPUS_SCHEMA = "entry-v2-corpus-v7"
LIFECYCLE_PROVENANCE_SCHEMA = "entry-v2-corpus-lifecycle-provenance-v1"
LIFECYCLE_PROVENANCE_RECEIPT_KEY = "lifecycle_provenance"
CORPUS_READY_MILESTONE_SOURCE = "production_diagnostic_stage_return"
LIFECYCLE_COLD = "COLD"
LIFECYCLE_WARM = "WARM"
LIFECYCLE_MIXED = "MIXED"
DIAGNOSTIC_PLANE_LAW_SHA256 = hashlib.sha256(
    b"ENTRY_V2_DIAGNOSTIC_PLANE_V1|truth-quality-derived-semantic-map|"
    b"typed-contiguous-immutable-vectors"
).hexdigest()
WALL_UNITS = 900 * PNL_UNITS_PER_USD
PRIOR_SCALE_CONVERSION_LAW = (
    "ENTRY_V2_PRIOR_SCALE_V1|original-decimal-text|positive-finite|"
    "multiply-2000000000-units-per-usd|round-ceiling|error-lt-one-unit"
)
PRIOR_SCALE_CONVERSION_LAW_SHA256 = hashlib.sha256(
    PRIOR_SCALE_CONVERSION_LAW.encode()
).hexdigest()


class DiagnosticCorpusRefusal(C.EntryV2Refusal):
    pass


def _lifecycle_provenance(
    corpus: EntryCorpus,
    finalized: Sequence["FinalizedDiagnosticSession"],
    *, physical_full_pack_opens: int,
    model_array_physical_fills: int,
    diagnostic_plane_bytes: int,
    warm_corpus_ready: bool,
) -> Mapping[str, Any]:
    verified_hits = int(corpus.receipt.get("verified_session_warm_hits", 0))
    cold_publishes = int(corpus.receipt.get(
        "verified_session_cold_publishes", 0))
    diagnostic_hits = sum(
        row.observed.receipt.get("diagnostic_plane_durable_hit") is True
        for row in finalized
    )
    # Timing classes are deliberately binary.  Any newly materialized product
    # is a cold run even when other products were durably reused; WARM means
    # the complete corpus became ready with zero producer work.
    cold_or_warm = LIFECYCLE_WARM if warm_corpus_ready else LIFECYCLE_COLD
    model_materialized = int(corpus.receipt.get(
        "model_array_bytes_materialized", 0))
    model_reused = int(corpus.receipt.get("model_array_bytes_reused", 0))
    diagnostic_reused = sum(
        int(row.observed.receipt["diagnostic_plane_bytes"])
        for row in finalized
        if row.observed.receipt.get("diagnostic_plane_durable_hit") is True
    )
    diagnostic_materialized = diagnostic_plane_bytes - diagnostic_reused
    if diagnostic_materialized < 0:
        raise DiagnosticCorpusRefusal(
            "diagnostic lifecycle byte accounting is negative"
        )
    window_identity = {
        "corpus_window": dict(corpus.receipt["corpus_window"]),
        "window_chain": corpus.receipt.get("window_chain"),
    }
    return MappingProxyType({
        "schema": LIFECYCLE_PROVENANCE_SCHEMA,
        "cold_or_warm": cold_or_warm,
        "warm_corpus_ready": bool(warm_corpus_ready),
        "physical_full_pack_opens": int(physical_full_pack_opens),
        "model_array_physical_fills": int(model_array_physical_fills),
        "verified_session_durable_hits": verified_hits,
        "verified_session_cold_publishes": cold_publishes,
        "diagnostic_plane_durable_hits": int(diagnostic_hits),
        "model_array_bytes_materialized": model_materialized,
        "model_array_bytes_reused": model_reused,
        "diagnostic_plane_bytes_materialized": diagnostic_materialized,
        "diagnostic_plane_bytes_reused": diagnostic_reused,
        "corpus_ready_elapsed_milestone_source": CORPUS_READY_MILESTONE_SOURCE,
        "cumulative_window_identity_sha256": C.object_sha256(window_identity),
    })


def _merge_lifecycle_provenance(
    corpus: EntryCorpus, parts: Sequence["DiagnosticCorpus"],
) -> Mapping[str, Any]:
    """Aggregate measured window work; never reclassify cold work as warm."""
    numeric = (
        "physical_full_pack_opens", "model_array_physical_fills",
        "verified_session_durable_hits", "verified_session_cold_publishes",
        "diagnostic_plane_durable_hits", "model_array_bytes_materialized",
        "model_array_bytes_reused", "diagnostic_plane_bytes_materialized",
        "diagnostic_plane_bytes_reused",
    )
    values = []
    for part in parts:
        value = part.receipt.get(LIFECYCLE_PROVENANCE_RECEIPT_KEY)
        if (not isinstance(value, Mapping)
                or value.get("schema") != LIFECYCLE_PROVENANCE_SCHEMA
                or any(type(value.get(name)) is not int
                       or int(value[name]) < 0 for name in numeric)):
            raise DiagnosticCorpusRefusal(
                "diagnostic window lifecycle provenance is invalid"
            )
        values.append(value)
    totals = {name: sum(int(value[name]) for value in values)
              for name in numeric}
    has_cold = any(totals[name] > 0 for name in (
        "verified_session_cold_publishes", "physical_full_pack_opens",
        "model_array_physical_fills", "model_array_bytes_materialized",
        "diagnostic_plane_bytes_materialized",
    ))
    has_reuse = any(totals[name] > 0 for name in (
        "verified_session_durable_hits", "diagnostic_plane_durable_hits",
        "model_array_bytes_reused", "diagnostic_plane_bytes_reused",
    ))
    if has_cold:
        lifecycle_class = LIFECYCLE_COLD
    elif has_reuse:
        lifecycle_class = LIFECYCLE_WARM
    else:
        raise DiagnosticCorpusRefusal(
            "diagnostic window lifecycle records no corpus work"
        )
    window_identity = {
        "corpus_window": dict(corpus.receipt["corpus_window"]),
        "window_chain": corpus.receipt.get("window_chain"),
    }
    return MappingProxyType({
        "schema": LIFECYCLE_PROVENANCE_SCHEMA,
        "cold_or_warm": lifecycle_class,
        "warm_corpus_ready": lifecycle_class == LIFECYCLE_WARM,
        **totals,
        "corpus_ready_elapsed_milestone_source":
            CORPUS_READY_MILESTONE_SOURCE,
        "cumulative_window_identity_sha256": C.object_sha256(window_identity),
    })


def _array_sha256(*arrays: np.ndarray) -> str:
    digest = hashlib.sha256()
    for array in arrays:
        value = np.ascontiguousarray(array)
        digest.update(value.dtype.str.encode("ascii"))
        digest.update(np.asarray(value.shape, dtype=np.int64).tobytes())
        digest.update(value.tobytes())
    return digest.hexdigest()


@dataclass(slots=True)
class _DiagnosticPlaneBacking:
    path: Path
    mapping: np.memmap
    size_bytes: int
    device: int
    inode: int
    mtime_ns: int
    ctime_ns: int
    sha256: str
    descriptor_sha256: str
    durable_product: DurableProduct | None = None

    def validate(self) -> None:
        if self.durable_product is not None:
            product = self.durable_product
            data = product.data_path.lstat()
            sidecar = product.sidecar_path.lstat()
            if (not stat.S_ISREG(data.st_mode) or not stat.S_ISREG(sidecar.st_mode)
                    or stat.S_IMODE(data.st_mode) != 0o444
                    or stat.S_IMODE(sidecar.st_mode) != 0o444
                    or data.st_size != int(product.receipt["data_size_bytes"])
                    or C.file_sha256(product.data_path)
                        != product.receipt["data_sha256"]
                    or product.sidecar_path.read_bytes()
                        != C.canonical_bytes(dict(product.receipt))):
                raise DiagnosticCorpusRefusal(
                    "durable diagnostic plane identity changed"
                )
        value = self.path.stat()
        if ((value.st_size, value.st_dev, value.st_ino, value.st_mtime_ns,
             value.st_ctime_ns) != (self.size_bytes, self.device, self.inode,
                                     self.mtime_ns, self.ctime_ns)
                or stat.S_IMODE(value.st_mode) & 0o222):
            raise DiagnosticCorpusRefusal(
                "disk-backed diagnostic plane identity changed"
            )

    def close(self, *, unlink: bool = False) -> None:
        mmap_value = getattr(self.mapping, "_mmap", None)
        if mmap_value is not None and not mmap_value.closed:
            mmap_value.close()
        if unlink:
            if self.durable_product is not None:
                return
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass


def _write_all(handle: Any, value: memoryview, digest: Any) -> None:
    offset = 0
    chunk = 8 * 1024 * 1024
    while offset < len(value):
        part = value[offset:offset + chunk]
        written = handle.write(part)
        if not isinstance(written, int) or written != len(part):
            raise DiagnosticCorpusRefusal(
                "disk-backed diagnostic plane write was incomplete"
            )
        digest.update(part)
        offset += written


def _byte_view(value: np.ndarray) -> memoryview:
    """Return a byte view without NumPy's zero-shape cast failure."""
    array = np.asarray(value)
    if array.nbytes == 0:
        return memoryview(b"")
    return memoryview(array).cast("B")


def _disk_back_planes(
    backing_dir: Path, asset: str, d8: int,
    truth: EventTruthColumns, derived: DerivedEventFields | None,
) -> tuple[EventTruthColumns, DerivedEventFields | None, _DiagnosticPlaneBacking]:
    """Publish one immutable packed mapping for every session truth/derived array."""
    semantic: list[tuple[str, np.ndarray]] = []
    for name, value in sorted(truth.columns.items()):
        semantic.append((f"truth:{name}", np.asarray(value)))
    for key, plane in sorted(truth.quality_planes.items()):
        key_text = ":".join(str(int(value)) for value in key)
        for name, value in sorted(plane.items()):
            semantic.append((f"quality:{key_text}:{name}", np.asarray(value)))
    if derived is not None:
        for name, value in sorted(derived.derived_routes.items()):
            semantic.append((f"derived:{name}", np.asarray(value)))
        for name, value in sorted(derived.valid_masks.items()):
            semantic.append((f"valid:{name}", np.asarray(value)))
    if not semantic:
        raise DiagnosticCorpusRefusal("diagnostic plane has no arrays")

    unique: list[np.ndarray] = []
    unique_by_identity: dict[int, int] = {}
    semantic_to_unique: dict[str, int] = {}
    for name, value in semantic:
        if value.dtype.hasobject or value.ndim != 1:
            raise DiagnosticCorpusRefusal(
                f"diagnostic plane {name} is not a typed vector"
            )
        identity = id(value)
        index = unique_by_identity.get(identity)
        if index is None:
            index = len(unique)
            unique_by_identity[identity] = index
            unique.append(np.ascontiguousarray(value))
        semantic_to_unique[name] = index

    descriptors: list[dict[str, Any]] = []
    offset = 0
    for value in unique:
        alignment = max(64, int(value.dtype.alignment))
        offset = (offset + alignment - 1) // alignment * alignment
        descriptors.append({
            "offset": offset, "dtype": value.dtype.str,
            "shape": list(value.shape), "nbytes": int(value.nbytes),
        })
        offset += int(value.nbytes)
    data_size = max(offset, 1)
    descriptor_payload = {
        "schema": "entry-v2-diagnostic-plane-map-v1",
        "asset": asset, "d8": int(d8),
        "arrays": descriptors,
        "data_size_bytes": data_size,
        "semantic_to_unique": dict(sorted(semantic_to_unique.items())),
    }
    descriptor_sha256 = C.object_sha256(descriptor_payload)
    final = backing_dir / f"{int(d8)}.planes"
    if final.exists():
        raise DiagnosticCorpusRefusal("diagnostic plane path already exists")
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{int(d8)}.", suffix=".tmp", dir=backing_dir
    )
    temporary = Path(temporary_name)
    renamed = False
    digest = hashlib.sha256()
    try:
        with os.fdopen(fd, "wb", buffering=0) as handle:
            cursor = 0
            for value, descriptor in zip(unique, descriptors):
                padding = int(descriptor["offset"]) - cursor
                if padding:
                    zeros = b"\0" * padding
                    _write_all(handle, memoryview(zeros), digest)
                    cursor += padding
                _write_all(handle, _byte_view(value), digest)
                cursor += int(value.nbytes)
            if cursor < data_size:
                _write_all(handle, memoryview(b"\0" * (data_size - cursor)), digest)
            handle.flush(); os.fsync(handle.fileno()); os.fchmod(handle.fileno(), 0o444)
            if hasattr(os, "posix_fadvise") and hasattr(os, "POSIX_FADV_DONTNEED"):
                try:
                    os.posix_fadvise(handle.fileno(), 0, 0, os.POSIX_FADV_DONTNEED)
                except OSError:
                    pass
        os.link(temporary, final); renamed = True; temporary.unlink()
        directory_fd = os.open(backing_dir, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except BaseException:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        if renamed:
            try:
                final.unlink()
            except FileNotFoundError:
                pass
        raise

    value = final.stat()
    if value.st_size != data_size or stat.S_IMODE(value.st_mode) & 0o222:
        raise DiagnosticCorpusRefusal("diagnostic plane publication is not immutable")
    mapping = np.memmap(final, mode="r", dtype=np.uint8, shape=(data_size,))

    def view(name: str) -> np.ndarray:
        descriptor = descriptors[semantic_to_unique[name]]
        array = np.ndarray(
            tuple(descriptor["shape"]), dtype=np.dtype(descriptor["dtype"]),
            buffer=mapping, offset=int(descriptor["offset"]),
        )
        array.setflags(write=False)
        return array

    columns = MappingProxyType({
        name: view(f"truth:{name}") for name in truth.columns
    })
    quality_planes = {}
    for key, plane in truth.quality_planes.items():
        key_text = ":".join(str(int(item)) for item in key)
        quality_planes[key] = MappingProxyType({
            name: view(f"quality:{key_text}:{name}") for name in plane
        })
    mapped_truth = EventTruthColumns(
        columns, MappingProxyType(quality_planes)
    )
    mapped_derived = None
    if derived is not None:
        mapped_derived = DerivedEventFields(
            MappingProxyType({name: mapped_truth.columns[name]
                              for name in derived.raw_routes}),
            MappingProxyType({name: view(f"derived:{name}")
                              for name in derived.derived_routes}),
            MappingProxyType({name: view(f"valid:{name}")
                              for name in derived.valid_masks}),
            MappingProxyType(dict(derived.constant_mask)),
            derived.schema_sha256, derived.equation_sha256,
        )
    backing = _DiagnosticPlaneBacking(
        final, mapping, value.st_size, value.st_dev, value.st_ino,
        value.st_mtime_ns, value.st_ctime_ns, digest.hexdigest(),
        descriptor_sha256,
    )
    backing.validate()
    return mapped_truth, mapped_derived, backing


def _durable_plane_identity(
    source: SessionEventSource,
    candidates: tuple[Mapping[str, str], ...],
    teachers: tuple[Mapping[str, str], ...],
    include_derived: bool,
) -> Mapping[str, Any]:
    return MappingProxyType({
        "schema": "entry-v2-durable-diagnostic-source-v1",
        "source": dict(source.durable_identity()),
        "candidate_rows_sha256": C.object_sha256([dict(row) for row in candidates]),
        "teacher_rows_sha256": C.object_sha256([dict(row) for row in teachers]),
        "include_derived": bool(include_derived),
    })


def _diagnostic_semantic(
    truth: EventTruthColumns, derived: DerivedEventFields | None,
) -> tuple[tuple[np.ndarray, ...], Mapping[str, Any]]:
    arrays: list[np.ndarray] = []
    index_by_identity: dict[int, int] = {}

    def index(value: np.ndarray) -> int:
        raw = np.asarray(value)
        found = index_by_identity.get(id(value))
        if found is None:
            found = len(arrays)
            index_by_identity[id(value)] = found
            arrays.append(np.ascontiguousarray(raw))
        return found

    truth_map = {name: index(value) for name, value in sorted(truth.columns.items())}
    quality_map = {
        ":".join(str(int(item)) for item in key): {
            name: index(value) for name, value in sorted(plane.items())
        }
        for key, plane in sorted(truth.quality_planes.items())
    }
    derived_map = ({
        name: index(value) for name, value in sorted(derived.derived_routes.items())
    } if derived is not None else {})
    valid_map = ({
        name: index(value) for name, value in sorted(derived.valid_masks.items())
    } if derived is not None else {})
    semantic = {
        "schema": "entry-v2-diagnostic-plane-semantic-v1",
        "truth": truth_map,
        "quality": quality_map,
        "derived": derived_map,
        "valid": valid_map,
        "derived_raw_routes": ([] if derived is None else sorted(derived.raw_routes)),
        "derived_constant_mask": (
            {} if derived is None else dict(sorted(derived.constant_mask.items()))),
        "derived_schema_sha256": (
            None if derived is None else derived.schema_sha256),
        "derived_equation_sha256": (
            None if derived is None else derived.equation_sha256),
    }
    return tuple(arrays), MappingProxyType(semantic)


def _planes_from_durable_product(
    product: DurableProduct,
) -> tuple[EventTruthColumns, DerivedEventFields | None, _DiagnosticPlaneBacking]:
    semantic = product.receipt.get("semantic")
    producer = product.receipt.get("producer")
    if not isinstance(semantic, dict) or semantic.get("schema") != (
            "entry-v2-diagnostic-plane-semantic-v1"):
        product.close()
        raise DiagnosticCorpusRefusal("durable diagnostic semantic mapping drift")
    if (not isinstance(producer, dict)
            or producer.get("schema") != "entry-v2-diagnostic-plane-producer-v1"
            or producer.get("physical_full_pack_opens") != 1
            or producer.get("model_array_physical_fills") != 1
            or producer.get("source_receipt_sha256") != product.receipt[
                "identity"]["source"]["session_stream_receipt"][
                    "receipt_sha256"]):
        product.close()
        raise DiagnosticCorpusRefusal(
            "durable diagnostic producer provenance drift"
        )
    arrays = product.arrays
    try:
        truth = EventTruthColumns(
            MappingProxyType({
                name: arrays[int(index)]
                for name, index in semantic["truth"].items()
            }),
            MappingProxyType({
                tuple(int(item) for item in key.split(":")): MappingProxyType({
                    name: arrays[int(index)] for name, index in plane.items()
                })
                for key, plane in semantic["quality"].items()
            }),
        )
        derived = None
        if semantic["derived_schema_sha256"] is not None:
            derived = DerivedEventFields(
                MappingProxyType({
                    name: truth.columns[name]
                    for name in semantic["derived_raw_routes"]
                }),
                MappingProxyType({
                    name: arrays[int(index)]
                    for name, index in semantic["derived"].items()
                }),
                MappingProxyType({
                    name: arrays[int(index)]
                    for name, index in semantic["valid"].items()
                }),
                MappingProxyType(dict(semantic["derived_constant_mask"])),
                str(semantic["derived_schema_sha256"]),
                str(semantic["derived_equation_sha256"]),
            )
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        product.close()
        raise DiagnosticCorpusRefusal(
            "durable diagnostic semantic mapping is invalid"
        ) from exc
    value = product.data_path.stat()
    backing = _DiagnosticPlaneBacking(
        product.data_path, product.mapping, value.st_size, value.st_dev,
        value.st_ino, value.st_mtime_ns, value.st_ctime_ns,
        str(product.receipt["data_sha256"]), C.object_sha256(semantic), product,
    )
    backing.validate()
    return truth, derived, backing


def load_durable_diagnostic_planes(
    store: DurableEntryV2Store,
    source: SessionEventSource,
    candidates: tuple[Mapping[str, str], ...],
    teachers: tuple[Mapping[str, str], ...],
    *, include_derived: bool,
) -> tuple[EventTruthColumns, DerivedEventFields | None,
           _DiagnosticPlaneBacking] | None:
    product = store.load(
        "diagnostic-planes",
        _durable_plane_identity(source, candidates, teachers, include_derived),
        DIAGNOSTIC_PLANE_LAW_SHA256,
    )
    return None if product is None else _planes_from_durable_product(product)


def _durable_back_planes(
    store: DurableEntryV2Store, source: SessionEventSource,
    candidates: tuple[Mapping[str, str], ...],
    teachers: tuple[Mapping[str, str], ...],
    truth: EventTruthColumns, derived: DerivedEventFields | None,
) -> tuple[EventTruthColumns, DerivedEventFields | None, _DiagnosticPlaneBacking]:
    arrays, semantic = _diagnostic_semantic(truth, derived)
    measured = source.measurements.snapshot()
    if (measured["physical_full_pack_opens"],
            measured["model_array_physical_fills"]) != (1, 1):
        raise DiagnosticCorpusRefusal(
            "durable diagnostic producer lacks one-open provenance"
        )
    product = store.publish(
        "diagnostic-planes",
        _durable_plane_identity(source, candidates, teachers, derived is not None),
        DIAGNOSTIC_PLANE_LAW_SHA256, arrays, semantic=semantic,
        producer={
            "schema": "entry-v2-diagnostic-plane-producer-v1",
            "source_receipt_sha256": source.receipt.receipt_sha256,
            "physical_full_pack_opens": 1,
            "model_array_physical_fills": 1,
        },
    )
    return _planes_from_durable_product(product)


def _prior_scale_units_text(row: Mapping[str, str], name: str) -> int:
    """Conservatively quantize an exact decimal prior barrier to PnL units.

    ATR14 is a continuous average and normally has a fractional 1/14-dollar
    component, whereas realized PnL endpoints are exact integers at
    ``PNL_UNITS_PER_USD``.  Ceiling is intentional: both favorable and adverse
    scale barriers must not be declared hit before the original decimal
    magnitude is reached.  The quantization error is strictly below one PnL
    unit and the original manifest text remains the authority.
    """

    value = row.get(name)
    if value is None or isinstance(value, (float, np.floating)):
        raise DiagnosticCorpusRefusal(f"{name} is not original decimal text")
    try:
        decimal_value = Decimal(str(value))
        scaled = decimal_value * PNL_UNITS_PER_USD
    except InvalidOperation as exc:
        raise DiagnosticCorpusRefusal(f"invalid decimal field {name}") from exc
    if not scaled.is_finite() or decimal_value <= 0:
        raise DiagnosticCorpusRefusal(
            f"{name} prior scale must be finite and positive"
        )
    integral = scaled.to_integral_value(rounding=ROUND_CEILING)
    if integral > np.iinfo(np.int64).max:
        raise DiagnosticCorpusRefusal(f"{name} prior scale exceeds int64 units")
    return int(integral)


def _owned_mapping(row: Mapping[str, str]) -> Mapping[str, str]:
    return MappingProxyType({str(key): str(value) for key, value in row.items()})


@dataclass(frozen=True, slots=True)
class ObservedDiagnosticSession:
    source: SessionEventSource
    candidates: tuple[Mapping[str, str], ...]
    teachers: tuple[Mapping[str, str], ...]
    truth: EventTruthColumns | None
    derived: DerivedEventFields | None
    receipt: Mapping[str, Any]
    backing: _DiagnosticPlaneBacking | None = None

    @property
    def key(self) -> tuple[str, int]:
        return self.source.asset, self.source.d8

    def validate_backing(self) -> None:
        if self.backing is not None:
            self.backing.validate()


class DiagnosticCorpusObserver(DiagnosticSessionObserver):
    """Asset-local observer used by one corpus worker."""

    def __init__(self, asset: str, *, start_d8: int = 20210531,
                 truth_end_d8: int = 20250630,
                 derived_end_d8: int = 20221230,
                 end_d8_inclusive: int | None = None,
                 corpus_maximum_d8: int | None = None,
                 minimum_d8_exclusive: int | None = None,
                 backing_dir: Path | None = None,
                 durable_store: DurableEntryV2Store | None = None) -> None:
        self.asset = str(asset).upper()
        if self.asset not in C.ASSETS:
            raise DiagnosticCorpusRefusal("unknown diagnostic observer asset")
        C.guard_date(int(start_d8))
        if end_d8_inclusive is not None:
            # Backward-compatible test hook; it narrows both planes.
            truth_end_d8 = int(end_d8_inclusive)
            derived_end_d8 = truth_end_d8
        C.guard_date(int(truth_end_d8))
        C.guard_date(int(derived_end_d8))
        resolved_corpus_maximum = (
            C.DEVELOPMENT_END_D8
            if corpus_maximum_d8 is None else int(corpus_maximum_d8)
        )
        C.guard_date(resolved_corpus_maximum)
        if resolved_corpus_maximum > C.DEVELOPMENT_END_D8:
            raise DiagnosticCorpusRefusal("diagnostic corpus maximum crosses the H2 wall")
        if int(start_d8) > int(derived_end_d8) or int(derived_end_d8) > int(truth_end_d8):
            raise DiagnosticCorpusRefusal("diagnostic observer window is reversed")
        if (int(truth_end_d8) > resolved_corpus_maximum
                or int(derived_end_d8) > resolved_corpus_maximum):
            raise DiagnosticCorpusRefusal(
                "diagnostic observer exceeds the corpus window"
            )
        if int(truth_end_d8) >= C.HOLDOUT_START_D8:
            raise DiagnosticCorpusRefusal("diagnostic observer crosses the H2 wall")
        self.start_d8 = int(start_d8)
        self.truth_end_d8 = int(truth_end_d8)
        self.derived_end_d8 = int(derived_end_d8)
        self.corpus_maximum_d8 = resolved_corpus_maximum
        self.minimum_d8_exclusive = (
            None if minimum_d8_exclusive is None
            else int(minimum_d8_exclusive)
        )
        if self.minimum_d8_exclusive is not None:
            C.guard_date(self.minimum_d8_exclusive)
            if self.minimum_d8_exclusive >= self.corpus_maximum_d8:
                raise DiagnosticCorpusRefusal(
                    "diagnostic chronological interval is empty/reversed"
                )
        self.end_d8_inclusive = self.truth_end_d8
        self._sessions: dict[int, ObservedDiagnosticSession] = {}
        if backing_dir is not None and durable_store is not None:
            raise DiagnosticCorpusRefusal(
                "diagnostic backing_dir and durable_store are mutually exclusive"
            )
        if durable_store is not None and not isinstance(
                durable_store, DurableEntryV2Store):
            raise DiagnosticCorpusRefusal(
                "durable_store must be a DurableEntryV2Store"
            )
        self.durable_store = durable_store
        self.backing_dir: Path | None = None
        if backing_dir is not None:
            path = Path(backing_dir)
            if (not path.is_absolute() or ".." in path.parts or path.exists()
                    or not path.parent.is_dir()):
                raise DiagnosticCorpusRefusal(
                    "diagnostic plane cache requires a new absolute asset directory"
                )
            path.mkdir(mode=0o700)
            self.backing_dir = path

    @property
    def sessions(self) -> tuple[ObservedDiagnosticSession, ...]:
        return tuple(self._sessions[day] for day in sorted(self._sessions))

    def observe_session(
        self,
        *,
        source: SessionEventSource,
        pack: EventPack,
        candidates: tuple[Mapping[str, str], ...],
        teachers: tuple[Mapping[str, str], ...],
    ) -> None:
        if source.asset != self.asset:
            raise DiagnosticCorpusRefusal("diagnostic observer asset is wrong")
        if (not self.start_d8 <= source.d8 <= self.truth_end_d8
                or (self.minimum_d8_exclusive is not None
                    and source.d8 <= self.minimum_d8_exclusive)):
            return
        candidate_rows = tuple(_owned_mapping(row) for row in candidates)
        teacher_rows = tuple(_owned_mapping(row) for row in teachers)
        existing = self._sessions.get(source.d8)
        if existing is not None:
            header = pack.header
            actual_pack_identity = (
                pack.path, header.asset, header.d8, header.locked_iid,
                header.open_utc, header.close_utc, header.n_events,
            )
            expected_pack_identity = (
                source.qre2_path, source.asset, source.d8, source.locked_iid,
                source.open_utc, source.close_utc, source.event_count,
            )
            if (actual_pack_identity != expected_pack_identity
                    or existing.source.receipt.canonical_bytes()
                    != source.receipt.canonical_bytes()):
                raise DiagnosticCorpusRefusal(
                    "diagnostic callback source identity conflicts"
                )
            if (existing.candidates != candidate_rows
                    or existing.teachers != teacher_rows):
                raise DiagnosticCorpusRefusal(
                    "diagnostic callback payload conflicts"
                )
            raise DiagnosticCorpusRefusal(
                "diagnostic callback is duplicated exactly"
            )
        if source.array_cache is None:
            raise DiagnosticCorpusRefusal(
                "one-open diagnostic requires the shared session array cache"
            )
        # The corpus publishes these arrays from this exact pack before the
        # callback.  A hit proves no second full mmap/conversion is needed.
        try:
            source.measurements.require_single_full_open()
        except C.EntryV2Refusal as exc:
            raise DiagnosticCorpusRefusal(
                "diagnostic source lacks measured one-open evidence"
            ) from exc
        before = source.measurements.snapshot()
        if (before["physical_full_pack_opens"] != 1
                or before["model_array_physical_fills"] != 1
                or before["array_cache_hits"] != 0
                or before["header_revalidations"] != 0
                or before["single_full_open_required"] is not True):
            raise DiagnosticCorpusRefusal(
                "diagnostic source cache-hit baseline differs"
            )
        with source.open_arrays() as (continuous, categorical):
            if (continuous.shape[0] != source.max_cutoff
                    or categorical.shape[0] != source.max_cutoff):
                raise DiagnosticCorpusRefusal("cached learner prefix is misaligned")
        measured = source.measurements.snapshot()
        if (measured["physical_full_pack_opens"]
                != before["physical_full_pack_opens"]
                or measured["model_array_physical_fills"]
                != before["model_array_physical_fills"]
                or measured["array_cache_hits"]
                != before["array_cache_hits"] + 1
                or measured["header_revalidations"]
                != before["header_revalidations"] + 1
                or measured["single_full_open_required"] is not True):
            raise DiagnosticCorpusRefusal(
                "diagnostic one-open/cache-hit measurements differ"
            )

        include_derived = source.d8 <= self.derived_end_d8
        loaded = (None if self.durable_store is None else
                  load_durable_diagnostic_planes(
                      self.durable_store, source, candidate_rows, teacher_rows,
                      include_derived=include_derived,
                  ))
        if loaded is not None:
            truth, derived, backing = loaded
            durable_hit = True
        else:
            provisional = build_candidate_truth_bindings(candidate_rows, teacher_rows)
            truth = build_event_truth_columns(pack.rows, source.asset, provisional)
            if any(np.shares_memory(value, pack.rows)
                   for value in truth.all_arrays()):
                raise DiagnosticCorpusRefusal("truth plane retained the QRE2 mmap")
            derived = (DerivedEventFieldBuilder().build(truth)
                       if include_derived else None)
            backing = None
            durable_hit = False
            if self.durable_store is not None:
                truth, derived, backing = _durable_back_planes(
                    self.durable_store, source, candidate_rows, teacher_rows,
                    truth, derived,
                )
            elif self.backing_dir is not None:
                truth, derived, backing = _disk_back_planes(
                    self.backing_dir, source.asset, source.d8, truth, derived
                )
        body = {
            "schema": DIAGNOSTIC_CORPUS_SCHEMA,
            "asset": source.asset,
            "d8": source.d8,
            "source_receipt_sha256": source.receipt.receipt_sha256,
            "source_event_count": source.event_count,
            "learner_prefix_count": source.max_cutoff,
            "candidate_count": len(candidate_rows),
            "teacher_count": len(teacher_rows),
            "candidate_ids": [row["candidate_id"] for row in candidate_rows],
            "truth_columns": {
                name: [str(value.dtype), list(value.shape)]
                for name, value in sorted(truth.columns.items())
            },
            "truth_quality_keys": [list(key) for key in sorted(truth.quality_planes)],
            "derived_schema_sha256": None if derived is None else derived.schema_sha256,
            "derived_equation_sha256": None if derived is None else derived.equation_sha256,
            "truth_retained": True,
            "derived_retained": derived is not None,
            "corpus_maximum_d8": self.corpus_maximum_d8,
            "diagnostic_plane_disk_backed": backing is not None,
            "diagnostic_plane_bytes": 0 if backing is None else backing.size_bytes,
            "diagnostic_plane_sha256": None if backing is None else backing.sha256,
            "diagnostic_plane_descriptor_sha256": (
                None if backing is None else backing.descriptor_sha256),
            "diagnostic_plane_durable": self.durable_store is not None,
            "diagnostic_plane_durable_hit": durable_hit,
            "verified_session_durable_hit": False,
            "full_outcome_mmap_retained": False,
            "physical_full_pack_opens": measured["physical_full_pack_opens"],
            "model_array_physical_fills": measured["model_array_physical_fills"],
            "header_revalidations": measured["header_revalidations"],
            "array_cache_hits": measured["array_cache_hits"],
            "one_open_measured": bool(
                measured["single_full_open_required"]
                and measured["physical_full_pack_opens"] == 1
                and measured["model_array_physical_fills"] == 1
            ),
        }
        body["receipt_sha256"] = C.object_sha256(body)
        self._sessions[source.d8] = ObservedDiagnosticSession(
            source, candidate_rows, teacher_rows, truth, derived,
            MappingProxyType(body), backing,
        )

    def observe_cached_session(
        self, *, source: SessionEventSource,
        candidates: tuple[Mapping[str, str], ...],
        teachers: tuple[Mapping[str, str], ...],
    ) -> None:
        """Restore a fully verified session without reopening its QRE2 payload."""
        if (source.asset != self.asset
                or not self.start_d8 <= source.d8 <= self.truth_end_d8
                or (self.minimum_d8_exclusive is not None
                    and source.d8 <= self.minimum_d8_exclusive)):
            if source.asset != self.asset:
                raise DiagnosticCorpusRefusal("diagnostic observer asset is wrong")
            return
        if source.d8 in self._sessions:
            raise DiagnosticCorpusRefusal("diagnostic cached callback is duplicated")
        if self.durable_store is None:
            raise DiagnosticCorpusRefusal(
                "verified-session reload requires the durable diagnostic store"
            )
        candidate_rows = tuple(_owned_mapping(row) for row in candidates)
        teacher_rows = tuple(_owned_mapping(row) for row in teachers)
        include_derived = source.d8 <= self.derived_end_d8
        loaded = load_durable_diagnostic_planes(
            self.durable_store, source, candidate_rows, teacher_rows,
            include_derived=include_derived,
        )
        if loaded is None:
            raise DiagnosticCorpusRefusal(
                "verified-session diagnostic product is absent; rebuild forbidden"
            )
        truth, derived, backing = loaded
        measured = source.measurements.snapshot()
        if (measured["physical_full_pack_opens"] != 0
                or measured["model_array_physical_fills"] != 0
                or measured["header_revalidations"] != 1
                or measured["array_cache_hits"] != 1):
            backing.close()
            raise DiagnosticCorpusRefusal(
                "verified-session warm measurements differ"
            )
        body = {
            "schema": DIAGNOSTIC_CORPUS_SCHEMA,
            "asset": source.asset, "d8": source.d8,
            "source_receipt_sha256": source.receipt.receipt_sha256,
            "source_event_count": source.event_count,
            "learner_prefix_count": source.max_cutoff,
            "candidate_count": len(candidate_rows),
            "teacher_count": len(teacher_rows),
            "candidate_ids": [row["candidate_id"] for row in candidate_rows],
            "truth_columns": {name: [str(value.dtype), list(value.shape)]
                              for name, value in sorted(truth.columns.items())},
            "truth_quality_keys": [list(key) for key in sorted(truth.quality_planes)],
            "derived_schema_sha256": None if derived is None else derived.schema_sha256,
            "derived_equation_sha256": None if derived is None else derived.equation_sha256,
            "truth_retained": True, "derived_retained": derived is not None,
            "corpus_maximum_d8": self.corpus_maximum_d8,
            "diagnostic_plane_disk_backed": True,
            "diagnostic_plane_bytes": backing.size_bytes,
            "diagnostic_plane_sha256": backing.sha256,
            "diagnostic_plane_descriptor_sha256": backing.descriptor_sha256,
            "diagnostic_plane_durable": True,
            "diagnostic_plane_durable_hit": True,
            "verified_session_durable_hit": True,
            "full_outcome_mmap_retained": False,
            "physical_full_pack_opens": 0,
            "model_array_physical_fills": 0,
            "header_revalidations": 1,
            "array_cache_hits": 1,
            "one_open_measured": True,
        }
        body["receipt_sha256"] = C.object_sha256(body)
        self._sessions[source.d8] = ObservedDiagnosticSession(
            source, candidate_rows, teacher_rows, truth, derived,
            MappingProxyType(body), backing,
        )

    def close(self) -> None:
        for session in self._sessions.values():
            if session.backing is not None:
                session.backing.close()
        self._sessions.clear()
        if self.backing_dir is not None:
            shutil.rmtree(self.backing_dir, ignore_errors=True)


@dataclass(frozen=True, slots=True)
class FinalizedDiagnosticSession:
    observed: ObservedDiagnosticSession
    bindings: tuple[CandidateTruthBinding, ...]
    anchors: tuple[CandidateAnchor, ...]
    atlas: MaterializedAtlas

    @property
    def key(self) -> tuple[str, int]:
        return self.observed.key


@dataclass(frozen=True, slots=True)
class DiagnosticCorpus:
    corpus: EntryCorpus
    sessions: tuple[FinalizedDiagnosticSession, ...]
    bindings: tuple[CandidateTruthBinding, ...]
    receipt: Mapping[str, Any]


def _diagnostic_semantic_identity(
    corpus: EntryCorpus,
    finalized: Sequence[FinalizedDiagnosticSession],
    bindings: Sequence[CandidateTruthBinding],
) -> str:
    """Window/restart identity that excludes physical-load telemetry.

    Cold and durable-warm construction deliberately produce different open,
    cache, byte and timing receipts.  Those facts remain auditable in the full
    diagnostic receipt, but they cannot relabel an otherwise byte-identical
    learner population or make the mandatory second invocation impossible to
    resume.
    """
    window = corpus.receipt.get("corpus_window")
    if not isinstance(window, Mapping):
        raise DiagnosticCorpusRefusal("diagnostic semantic identity lacks a corpus window")
    stable_window = {
        key: window.get(key) for key in (
            "schema", "law_sha256", "minimum_d8_exclusive",
            "maximum_d8", "start_d8_inclusive", "observed_start_d8",
            "observed_end_d8", "full_manifest_authority_sha256",
        )
    }
    required_corpus = (
        "corpus_source_lineage_sha256", "teacher_store_sha256",
        "session_stream_receipt_aggregate_sha256",
        "clock_law_receipt_sha256", "model_arrays_conversion_law_sha256",
    )
    if any(not isinstance(corpus.receipt.get(key), str)
           for key in required_corpus):
        raise DiagnosticCorpusRefusal(
            "diagnostic semantic identity lacks a corpus authority")
    candidate_ids = sorted(row.candidate_id for row in bindings)
    if len(candidate_ids) != len(set(candidate_ids)):
        raise DiagnosticCorpusRefusal(
            "diagnostic semantic identity contains duplicate candidates")
    payload = {
        "schema": "entry-v2-diagnostic-semantic-identity-v1",
        "corpus_window": stable_window,
        "corpus_source_lineage_sha256":
            corpus.receipt["corpus_source_lineage_sha256"],
        "teacher_store_sha256": corpus.receipt["teacher_store_sha256"],
        "session_stream_receipt_aggregate_sha256":
            corpus.receipt["session_stream_receipt_aggregate_sha256"],
        "clock_law_receipt_sha256":
            corpus.receipt["clock_law_receipt_sha256"],
        "model_arrays_conversion_law_sha256":
            corpus.receipt["model_arrays_conversion_law_sha256"],
        "candidate_ids_sha256": C.object_sha256(candidate_ids),
        "atlas_receipts": [row.atlas.receipt["receipt_sha256"]
                           for row in finalized],
        "source_receipt_union": sorted(
            row.observed.source.receipt.receipt_sha256 for row in finalized),
        "selected_horizon_schema_sha256":
            corpus.receipt.get("selected_horizon_schema_sha256"),
        "selected_horizon_coverage_sha256":
            corpus.receipt.get("selected_horizon_coverage_sha256"),
        "selected_horizon_tensors_aggregate_sha256":
            corpus.receipt.get("selected_horizon_tensors_aggregate_sha256"),
        "candidate_suffix_rows_visited": 0,
        "h2_permit": False,
    }
    return C.object_sha256(payload)


def _atlas_columns(
    truth: EventTruthColumns,
    binding: CandidateTruthBinding | None = None,
) -> Mapping[str, np.ndarray]:
    source = truth.columns if binding is None else truth.candidate_columns(binding)
    missing = source["missing_mask"].astype(np.uint32, copy=False)
    return {
        "ts_recv_ns": source["ts_recv_ns"],
        "source_ordinal": source["ordinal"],
        "trusted_message": source["trusted_message"],
        "trusted_economic": source["trusted_economic"],
        "sane_bbo": source["sane"],
        "generation": source["generation"],
        "mid2": source["mid2"],
        "action": source["action"],
        "side": source["side"],
        "flags": source["flags"],
        "depth": source["depth"],
        "missing_mask": missing,
        "spread_mask": ((missing & 6) == 0).astype(np.uint32),
        "price": source["price"],
        "bid_px": source["bid_px"],
        "ask_px": source["ask_px"],
        "size": source["size"],
        "bid_size": source["bid_sz"],
        "ask_size": source["ask_sz"],
        "bid_count": source["bid_ct"],
        "ask_count": source["ask_ct"],
        "ts_in_delta": source["ts_in_delta"],
        "receive_session_sec": source["receive_session_sec"],
        "sequence": source["sequence"],
        "ts_event_ns": source["ts_event_ns"],
        "phase_open_ts_ns": source["phase_open_ts_ns"],
        "phase_close_ts_ns": source["phase_close_ts_ns"],
        "phase_sane_ceiling_units": source["phase_sane_ceiling_units"],
    }


def _mask_cause(binding: CandidateTruthBinding) -> ActionMaskCause:
    reason = binding.action_mask_reason
    exact = {
        ActionMaskReason.AVAILABLE_EXACT_TIME: ActionMaskCause.NONE,
        ActionMaskReason.OCCUPANCY: ActionMaskCause.A004_OCCUPANCY,
        ActionMaskReason.ASSET_CAP: ActionMaskCause.A004_ASSET_CAP,
        ActionMaskReason.PORTFOLIO_CAP: ActionMaskCause.A004_PORTFOLIO_CAP,
        ActionMaskReason.COMPLIANCE: ActionMaskCause.COMPLIANCE,
        ActionMaskReason.NO_SANE_SUFFIX: ActionMaskCause.NO_SANE_SUFFIX,
    }
    try:
        return exact[reason]
    except KeyError as exc:
        raise DiagnosticCorpusRefusal(
            f"non-atomic action mask cause for {binding.candidate_id}: {reason!r}"
        ) from exc


def _candidate_sane(columns: Mapping[str, np.ndarray],
                    start: int, stop: int) -> np.ndarray:
    if not 0 <= start <= stop <= len(columns["sane"]):
        raise DiagnosticCorpusRefusal("candidate sane slice is invalid")
    return columns["sane"][start:stop]


def _canonical_outcome(binding: CandidateTruthBinding,
                       truth: EventTruthColumns) -> tuple[CanonicalOutcome, int]:
    columns = truth.candidate_columns(binding)
    cutoff = int(binding.event_cutoff)
    n = len(columns["ts_recv_ns"])
    if not 0 <= cutoff <= n:
        raise DiagnosticCorpusRefusal("candidate cutoff exceeds truth plane")
    generation = int(columns["generation"][cutoff - 1]) if cutoff else 0
    if binding.teacher_status == "NO_SANE_SUFFIX":
        if any((binding.cert_close_units, binding.mfe_units, binding.mae_units,
                binding.exit_ts_ns, int(binding.wall_hit), int(binding.payer))):
            raise DiagnosticCorpusRefusal(
                "NO_SANE_SUFFIX binding carries economic teacher values"
            )
        return CanonicalOutcome(
            CellAvailability.NO_SANE_SUFFIX, binding.decision_ts_ns, cutoff,
            BoundaryReason.NO_SANE_SUFFIX, 0, False, 0, 0,
        ), generation

    # Native QRE2G1TEACH2 is already the authenticated full-suffix economic
    # authority.  The atlas additionally needs the exact terminal source
    # ordinal, which the TSV intentionally does not duplicate.  Resolve only
    # the equal-receive-time terminal batch; never replay every candidate's
    # suffix in Python (that would be O(candidates * suffix)).
    exit_ts = int(binding.exit_ts_ns)
    if exit_ts < binding.decision_ts_ns or exit_ts > binding.phase_close_ts_ns:
        raise DiagnosticCorpusRefusal("READY teacher exit is outside its causal phase")
    clock = columns["ts_recv_ns"]
    batch_left = int(np.searchsorted(clock, exit_ts, side="left"))
    batch_right = int(np.searchsorted(clock, exit_ts, side="right"))
    if batch_left == batch_right or batch_right <= cutoff:
        raise DiagnosticCorpusRefusal("READY teacher exit clock is absent from truth")
    start = max(cutoff, batch_left)
    sane = _candidate_sane(columns, start, batch_right)
    trusted = columns["trusted_message"][start:batch_right] & sane
    same_generation = columns["generation"][start:batch_right] == generation
    eligible = trusted & same_generation
    indices = np.flatnonzero(eligible) + start
    if not len(indices):
        raise DiagnosticCorpusRefusal(
            "READY teacher terminal batch has no trusted candidate-specific sane row"
        )
    net = np.asarray([
        int(binding.side)
        * (int(columns["mid2"][index]) - int(binding.entry_mid2))
        * int(binding.multiplier) - int(binding.frozen_cost_units)
        for index in indices
    ], dtype=object)
    matching = indices[np.asarray([
        int(value) == int(binding.cert_close_units) for value in net
    ], dtype=np.bool_)]
    wall = bool(binding.wall_hit)
    if wall:
        matching = np.asarray([
            index for index in matching
            if (int(binding.side)
                * (int(columns["mid2"][index]) - int(binding.entry_mid2))
                * int(binding.multiplier) - int(binding.frozen_cost_units)) <= -WALL_UNITS
        ], dtype=np.int64)
        # The native teacher stops on the first trusted wall row in provider
        # order, including within a whole equal-time batch.
        last_index = int(matching[0]) if len(matching) else -1
    else:
        # Phase-close teachers retain the last trusted sane row at their final
        # receive clock.
        last_index = int(matching[-1]) if len(matching) else -1
    if last_index < 0:
        raise DiagnosticCorpusRefusal("native teacher terminal value/row mismatch")
    exit_ordinal = int(columns["ordinal"][last_index])
    final = int(binding.cert_close_units)
    if (wall != (final <= -WALL_UNITS)
            or int(binding.mfe_units) < 0
            or int(binding.mae_units) < 0
            or (final > 0) != bool(binding.payer)):
        raise DiagnosticCorpusRefusal(
            f"canonical teacher byte/unit parity failed: {binding.candidate_id}"
        )
    return CanonicalOutcome(
        CellAvailability.MATERIALIZED, exit_ts, exit_ordinal,
        BoundaryReason.WALL if wall else BoundaryReason.PHASE,
        final, wall, int(binding.mfe_units), int(binding.mae_units),
    ), generation


def _anchor(binding: CandidateTruthBinding, candidate: Mapping[str, str],
            truth: EventTruthColumns,
            counterfactual: A004CounterfactualAtoms | None) -> CandidateAnchor:
    canonical, generation = _canonical_outcome(binding, truth)
    prior = _prior_scale_units_text(candidate, "atr14_prev_usd")
    group = f"{binding.asset}:{binding.trading_day}:{binding.decision_ts_ns}"
    return CandidateAnchor.from_binding(
        candidate_id=binding.candidate_id,
        decision_ts_ns=binding.decision_ts_ns,
        side=binding.side,
        entry_mid2=binding.entry_mid2,
        multiplier=binding.multiplier,
        frozen_cost_units=binding.frozen_cost_units,
        phase_close_ts_ns=binding.phase_close_ts_ns,
        phase_open_ts_ns=binding.phase_open_ts_ns,
        sane_ceiling_units=binding.sane_ceiling_units,
        source_ordinal=binding.prefix_last_event_ordinal,
        generation_at_cutoff=generation,
        canonical_terminal=canonical,
        action_mask_cause=_mask_cause(binding),
        authoritative_teacher_action=binding.action_target,
        asset=binding.asset,
        trading_day=binding.trading_day,
        exact_time_group_id=group,
        payer_target=binding.payer,
        native_candidate_local=binding.native_candidate_local,
        prior_location_units=0,
        prior_scale_units=prior if prior > 0 else None,
        now_wait_pass_regret_units=(None if counterfactual is None else
                                    counterfactual.now_wait_pass_regret_units),
        shadow_marginal_regret_units=(None if counterfactual is None else
                                      counterfactual.shadow_marginal_regret_units),
    )


def _selected_horizon_coverage_preflight(
    corpus: EntryCorpus,
    observed: Sequence[ObservedDiagnosticSession],
    binding_by_id: Mapping[str, CandidateTruthBinding],
    *,
    start_d8: int,
) -> Mapping[str, object] | None:
    """Prove the complete selected-target session algebra before atlas work."""

    if not isinstance(corpus, EntryCorpus):
        # Metadata-light fixtures do not carry learner specifications.  The
        # production path always supplies the concrete EntryCorpus.
        return None
    corpus_rows: list[dict[str, object]] = []
    for spec in corpus.sessions:
        selected = (
            spec.selected_horizon_value, spec.selected_horizon_valid,
            spec.selected_horizon_schema_sha256,
        )
        if any(value is not None for value in selected):
            raise DiagnosticCorpusRefusal(
                "selected horizon preflight received an already-attached corpus"
            )
        corpus_rows.append({
            "asset": spec.asset,
            "trading_day": spec.trading_day,
            "session_id": spec.session_id,
            "candidate_count": len(spec.candidate_ids),
            "candidate_ids_sha256": C.object_sha256(list(spec.candidate_ids)),
            "selected_attached": spec.trading_day >= int(start_d8),
        })

    diagnostic_rows: list[dict[str, object]] = []
    for session in observed:
        candidate_ids = tuple(str(row["candidate_id"])
                              for row in session.candidates)
        try:
            local = tuple(binding_by_id[candidate_id]
                          for candidate_id in candidate_ids)
        except KeyError as exc:
            raise DiagnosticCorpusRefusal(
                "diagnostic coverage candidate lacks a global truth binding"
            ) from exc
        eligible = tuple(
            row.candidate_id for row in local
            if row.compliance_status == "CLEAR" and row.teacher_status == "READY"
        )
        diagnostic_rows.append({
            "asset": session.key[0],
            "trading_day": session.key[1],
            "source_receipt_sha256": session.source.receipt.receipt_sha256,
            "candidate_count": len(candidate_ids),
            "candidate_ids_sha256": C.object_sha256(list(candidate_ids)),
            "eligible_ready_count": len(eligible),
            "eligible_ready_ids_sha256": C.object_sha256(list(eligible)),
        })
    try:
        return selected_horizon_coverage_receipt(
            start_d8=int(start_d8), corpus_sessions=corpus_rows,
            diagnostic_sessions=diagnostic_rows,
        )
    except SelectedHorizonContractRefusal as exc:
        raise DiagnosticCorpusRefusal(
            "selected horizon coverage preflight failed"
        ) from exc


def _bind_selected_horizon_corpus(
    corpus: EntryCorpus,
    finalized: Sequence[FinalizedDiagnosticSession],
    binding_by_id: Mapping[str, CandidateTruthBinding],
    coverage: Mapping[str, object] | None,
) -> EntryCorpus:
    """Attach exact atlas endpoints to metadata specs and rebind the receipt."""
    if not isinstance(corpus, EntryCorpus):
        # Narrow compatibility for metadata-light unit fixtures.  Production
        # always supplies the concrete immutable EntryCorpus.
        return corpus
    if tuple(SELECTED_HORIZON_COORDINATES) != (
            300, 600, 900, 1200, 1800, "FINAL"):
        raise DiagnosticCorpusRefusal(
            "selected horizon contract coordinate order changed"
        )
    if coverage is None:
        raise DiagnosticCorpusRefusal(
            "selected horizon coverage receipt is absent"
        )
    try:
        validate_selected_horizon_coverage(coverage)
    except SelectedHorizonContractRefusal as exc:
        raise DiagnosticCorpusRefusal(
            "selected horizon coverage receipt is invalid"
        ) from exc
    start_d8 = int(coverage["start_d8"])
    by_key = {row.key: row for row in finalized}
    if len(by_key) != len(finalized):
        raise DiagnosticCorpusRefusal(
            "selected target finalized atlas sessions duplicate an asset-day"
        )
    axes = np.asarray((3, 4, 5, 6, 7, 11), dtype=np.int64)
    sessions = []
    selected_receipts: dict[tuple[str, int, str], dict[str, Any]] = {}
    for spec in corpus.sessions:
        row = by_key.get((spec.asset, spec.trading_day))
        if row is None:
            if spec.trading_day >= start_d8:
                raise DiagnosticCorpusRefusal(
                    "selected target suffix session has no finalized atlas"
                )
            if any(value is not None for value in (
                    spec.selected_horizon_value, spec.selected_horizon_valid,
                    spec.selected_horizon_schema_sha256)):
                raise DiagnosticCorpusRefusal(
                    "selected target prefix unexpectedly carries targets"
                )
            sessions.append(spec)
            continue
        atlas_index = {candidate_id: index for index, candidate_id in enumerate(
            row.atlas.candidate_ids
        )}
        try:
            positions = np.asarray(
                [atlas_index[candidate_id] for candidate_id in spec.candidate_ids],
                dtype=np.int64,
            )
        except KeyError as exc:
            raise DiagnosticCorpusRefusal(
                "selected target candidate is absent from finalized atlas"
            ) from exc
        units = np.asarray(row.atlas.atoms["vertical_units"], np.int64)[
            positions][:, axes]
        valid = np.asarray(row.atlas.atoms["vertical_mask"], np.bool_)[
            positions][:, axes]
        status = np.asarray(row.atlas.atoms["vertical_status"])[
            positions][:, axes]
        if (units.shape != (len(spec.candidate_ids), len(axes))
                or valid.shape != units.shape or status.shape != units.shape
                or not np.isin(status, np.arange(
                    len(EndpointStatus), dtype=np.int8)).all()):
            raise DiagnosticCorpusRefusal(
                "selected target atlas coordinate/status plane differs"
            )
        for local, candidate_id in enumerate(spec.candidate_ids):
            binding = binding_by_id[candidate_id]
            if (binding.teacher_status != "READY" or not bool(valid[local, -1])
                    or int(units[local, -1]) != int(binding.cert_close_units)):
                raise DiagnosticCorpusRefusal(
                    "selected FINAL differs from exact READY teacher"
                )
        values = units.astype(np.float64) / float(PNL_UNITS_PER_USD)
        values[~valid] = 0.0
        # Bind both the exact integer atlas authority and the byte-exact raw
        # float64 USD carrier consumed by the selected-head normalizer.
        selected_sha = _array_sha256(units, values, valid, status)
        selected_receipts[(spec.asset, spec.trading_day, spec.session_id)] = {
            "selected_horizon_schema_sha256": SELECTED_HORIZON_SCHEMA_SHA256,
            "selected_horizon_tensors_sha256": selected_sha,
            "selected_horizon_status_sha256": _array_sha256(status),
        }
        attached = replace(
            spec,
            selected_horizon_value=torch.from_numpy(values),
            selected_horizon_valid=torch.from_numpy(valid.copy()),
            selected_horizon_schema_sha256=SELECTED_HORIZON_SCHEMA_SHA256,
        )
        attached.validate(corpus.teacher)
        sessions.append(attached)
    session_specs = []
    spec_keys = {
        (spec.asset, spec.trading_day, spec.session_id) for spec in corpus.sessions
    }
    for receipt in corpus.receipt["session_specs"]:
        key = (str(receipt["asset"]), int(receipt["d8"]),
               str(receipt["session_id"]))
        if key not in spec_keys:
            raise DiagnosticCorpusRefusal(
                "selected target receipt has no corpus session"
            )
        selected = selected_receipts.get(key)
        if selected is None:
            if key[1] >= start_d8 or any(
                    str(name).startswith("selected_horizon_")
                    for name in receipt):
                raise DiagnosticCorpusRefusal(
                    "selected target receipt/session identity differs"
                )
            session_specs.append(dict(receipt))
        else:
            session_specs.append({**dict(receipt), **selected})
    if (len(session_specs) != len(spec_keys)
            or len({(str(row["asset"]), int(row["d8"]),
                     str(row["session_id"])) for row in session_specs})
                != len(spec_keys)):
        raise DiagnosticCorpusRefusal(
            "selected target corpus/session receipt roster is not bijective"
        )
    attached_hashes = sorted(
        row["selected_horizon_tensors_sha256"] for row in session_specs
        if "selected_horizon_tensors_sha256" in row
    )
    if len(attached_hashes) != int(
            coverage["suffix_attached_session_count"]):
        raise DiagnosticCorpusRefusal(
            "selected target attached session count differs from preflight"
        )
    aggregate = C.object_sha256(attached_hashes)
    receipt = dict(corpus.receipt)
    receipt.pop("receipt_sha256", None)
    receipt.update({
        "schema": SELECTED_TARGET_CORPUS_SCHEMA,
        "selected_horizon_coordinates": list(SELECTED_HORIZON_COORDINATES),
        "selected_horizon_schema_sha256": SELECTED_HORIZON_SCHEMA_SHA256,
        "selected_horizon_target_law": SELECTED_HORIZON_TARGET_LAW,
        "selected_horizon_status_codes": [
            item.value for item in EndpointStatus
        ],
        "selected_horizon_coverage_schema":
            SELECTED_HORIZON_COVERAGE_SCHEMA,
        "selected_horizon_coverage_law": SELECTED_HORIZON_COVERAGE_LAW,
        "selected_horizon_coverage_law_sha256":
            SELECTED_HORIZON_COVERAGE_LAW_SHA256,
        "selected_horizon_start_d8": start_d8,
        "selected_horizon_coverage": dict(coverage),
        "selected_horizon_coverage_sha256": coverage["receipt_sha256"],
        "selected_horizon_tensors_aggregate_sha256": aggregate,
        "session_specs": session_specs,
    })
    receipt["receipt_sha256"] = C.object_sha256(receipt)
    model_binding = replace(
        corpus.model_input_binding,
        corpus_receipt_sha256=receipt["receipt_sha256"],
    )
    model_binding.validate()
    return replace(
        corpus, sessions=tuple(sessions), receipt=MappingProxyType(receipt),
        model_input_binding=model_binding,
    )


def finalize_diagnostic_corpus(
    corpus: EntryCorpus,
    observers: Mapping[str, DiagnosticCorpusObserver],
) -> DiagnosticCorpus:
    if set(observers) != set(C.ASSETS):
        raise DiagnosticCorpusRefusal("diagnostic observer roster is incomplete")
    corpus_window = corpus.receipt.get("corpus_window", {})
    if (corpus_window.get("schema") != CORPUS_WINDOW_SCHEMA
            or corpus_window.get("law_sha256") != CORPUS_WINDOW_LAW_SHA256):
        raise DiagnosticCorpusRefusal("source corpus window identity is missing")
    corpus_maximum_d8 = int(corpus_window.get("maximum_d8", 0))
    corpus_minimum_d8 = corpus_window.get("minimum_d8_exclusive")
    C.guard_date(corpus_maximum_d8)
    if any(
            observer.corpus_maximum_d8 != corpus_maximum_d8
            or observer.minimum_d8_exclusive != corpus_minimum_d8
            or observer.truth_end_d8 > corpus_maximum_d8
            or observer.derived_end_d8 > corpus_maximum_d8
            for observer in observers.values()):
        raise DiagnosticCorpusRefusal("diagnostic observer/corpus windows differ")
    diagnostic_starts = {observer.start_d8 for observer in observers.values()}
    if len(diagnostic_starts) != 1:
        raise DiagnosticCorpusRefusal(
            "diagnostic observers disagree on the selected-target start"
        )
    diagnostic_start_d8 = next(iter(diagnostic_starts))
    observed = tuple(sorted(
        (session for asset in sorted(C.ASSETS)
         for session in observers[asset].sessions),
        key=lambda row: (row.key[1], row.key[0],
                         row.source.receipt.receipt_sha256),
    ))
    candidate_rows = tuple(
        row for session in observed for row in session.candidates
    )
    teacher_rows = tuple(row for session in observed for row in session.teachers)
    bindings = build_candidate_truth_bindings(
        candidate_rows, teacher_rows, teacher_store=corpus.teacher
    )
    binding_by_id = {row.candidate_id: row for row in bindings}
    if len(binding_by_id) != len(bindings):
        raise DiagnosticCorpusRefusal("global diagnostic binding IDs duplicate")
    coverage = _selected_horizon_coverage_preflight(
        corpus, observed, binding_by_id, start_d8=diagnostic_start_d8,
    )
    counterfactuals = build_a004_counterfactual_atoms(bindings)

    finalized: list[FinalizedDiagnosticSession] = []
    truth_bytes_materialized = 0
    derived_bytes_materialized = 0
    truth_bytes_retained = 0
    derived_bytes_retained = 0
    post_e3_released = 0
    for session in observed:
        session.validate_backing()
        if session.truth is None:
            raise DiagnosticCorpusRefusal("observer released truth before atlas materialization")
        truth_bytes = session.truth.nbytes
        # raw_routes alias EventTruthColumns and are not counted twice.
        derived_bytes = (0 if session.derived is None else sum(
            int(np.asarray(value).nbytes) for mapping in (
                session.derived.derived_routes, session.derived.valid_masks)
            for value in mapping.values()))
        truth_bytes_materialized += truth_bytes
        derived_bytes_materialized += derived_bytes
        local_bindings = tuple(
            binding_by_id[row["candidate_id"]] for row in session.candidates
        )
        anchors = tuple(
            _anchor(binding, candidate, session.truth,
                    counterfactuals[binding.candidate_id])
            for binding, candidate in zip(local_bindings, session.candidates)
        )
        if anchors:
            positions_by_quality: dict[tuple[int, int, int, int], list[int]] = {}
            for position, binding in enumerate(local_bindings):
                positions_by_quality.setdefault(
                    session.truth.quality_key(binding), []).append(position)
            parts: list[tuple[tuple[int, ...], MaterializedAtlas]] = []
            for key in sorted(positions_by_quality):
                positions = tuple(positions_by_quality[key])
                binding = local_bindings[positions[0]]
                index = SessionTruthIndex(**_atlas_columns(session.truth, binding))
                parts.append((positions, index.materialize(
                    tuple(anchors[position] for position in positions)
                )))
            atlas = merge_candidate_truth_atlases(anchors, parts)
        else:
            index = SessionTruthIndex(**_atlas_columns(session.truth))
            atlas = index.materialize(anchors)
        suffix_keys = ("candidate_suffix_rows_visited", "suffix_row_visits")
        present = [key for key in suffix_keys if key in atlas.receipt]
        if len(present) != 1 or int(atlas.receipt[present[0]]) != 0:
            raise DiagnosticCorpusRefusal("atlas visited candidate suffix rows")
        retained = replace(session, candidates=(), teachers=())
        if session.key[1] > 20221230:
            retained = replace(retained, truth=None, derived=None, backing=None)
            observers[session.key[0]]._sessions[session.key[1]] = retained
            if session.backing is not None:
                session.backing.close(unlink=True)
            post_e3_released += 1
        else:
            truth_bytes_retained += truth_bytes
            derived_bytes_retained += derived_bytes
            observers[session.key[0]]._sessions[session.key[1]] = retained
        finalized.append(FinalizedDiagnosticSession(retained, local_bindings,
                                                    anchors, atlas))

    corpus = _bind_selected_horizon_corpus(
        corpus, finalized, binding_by_id, coverage
    )
    source_receipt_union = sorted({
        row.observed.source.receipt.receipt_sha256 for row in finalized
    })
    expected_source_union = sorted(
        (session.source.receipt.receipt_sha256 for session in observed)
        if coverage is None else
        (str(row["source_receipt_sha256"])
         for row in coverage["diagnostic_sessions"])
    )
    if (len(source_receipt_union) != len(finalized)
            or source_receipt_union != expected_source_union):
        raise DiagnosticCorpusRefusal("diagnostic source receipt union is not exact")
    measured_one_open = bool(finalized) and all(
        row.observed.receipt["one_open_measured"] is True
        and ((row.observed.receipt["physical_full_pack_opens"] == 1
              and row.observed.receipt["model_array_physical_fills"] == 1
              and row.observed.receipt.get("verified_session_durable_hit") is False)
             or (row.observed.receipt["physical_full_pack_opens"] == 0
                 and row.observed.receipt["model_array_physical_fills"] == 0
                 and row.observed.receipt.get("verified_session_durable_hit") is True))
        for row in finalized
    )
    body = {
        "schema": DIAGNOSTIC_CORPUS_SCHEMA,
        "source_corpus_receipt_sha256": corpus.receipt["receipt_sha256"],
        "source_model_input_binding_sha256": corpus.model_input_binding.binding_sha256,
        "source_corpus_window_sha256": C.object_sha256(dict(corpus_window)),
        "corpus_maximum_d8": corpus_maximum_d8,
        "assets": list(C.ASSETS),
        "observed_start_d8": min((row.key[1] for row in finalized), default=None),
        "observed_end_d8": max((row.key[1] for row in finalized), default=None),
        "session_count": len(finalized),
        "candidate_count": len(bindings),
        "truth_quality_index_count": sum(int(
            row.atlas.receipt.get("truth_quality_key_count", 0)
        ) for row in finalized),
        "session_receipts": [
            row.observed.receipt["receipt_sha256"] for row in finalized
        ],
        "atlas_receipts": [row.atlas.receipt["receipt_sha256"] for row in finalized],
        "physical_full_pack_opens": sum(int(
            row.observed.receipt["physical_full_pack_opens"]
        ) for row in finalized),
        "model_array_physical_fills": sum(int(
            row.observed.receipt["model_array_physical_fills"]
        ) for row in finalized),
        "header_revalidations": sum(int(
            row.observed.receipt["header_revalidations"]
        ) for row in finalized),
        "array_cache_hits": sum(int(
            row.observed.receipt["array_cache_hits"]
        ) for row in finalized),
        "one_open_per_session": measured_one_open,
        "diagnostic_planes_disk_backed": bool(finalized) and all(
            row.observed.receipt["diagnostic_plane_disk_backed"] is True
            for row in finalized),
        "diagnostic_plane_bytes": sum(int(
            row.observed.receipt["diagnostic_plane_bytes"]
        ) for row in finalized),
        "diagnostic_plane_receipts_sha256": C.object_sha256(sorted(
            row.observed.receipt["diagnostic_plane_sha256"]
            for row in finalized
            if row.observed.receipt["diagnostic_plane_sha256"] is not None
        )),
        "durable_products_ready": bool(finalized) and all(
            row.observed.receipt.get("diagnostic_plane_durable") is True
            for row in finalized
        ),
        # True only when the immutable verified-session, learner-array, and
        # diagnostic products all reopened without a physical full payload.
        "warm_corpus_ready": bool(
            corpus.receipt.get("warm_corpus_ready") is True
            and all(
                row.observed.receipt.get("verified_session_durable_hit") is True
                and row.observed.receipt.get("diagnostic_plane_durable_hit") is True
                for row in finalized
            )
        ),
        "source_receipt_union": source_receipt_union,
        "source_receipt_union_sha256": C.object_sha256(source_receipt_union),
        "full_outcome_mmap_retained": False,
        "candidate_suffix_rows_visited": 0,
        "h2_permit": False,
        "truth_start_d8": min((observer.start_d8 for observer in observers.values()),
                              default=None),
        "truth_end_d8": max((observer.truth_end_d8 for observer in observers.values()),
                            default=None),
        "derived_end_d8": max((observer.derived_end_d8 for observer in observers.values()),
                              default=None),
        "truth_bytes_materialized": truth_bytes_materialized,
        "derived_bytes_materialized": derived_bytes_materialized,
        "truth_bytes_retained": truth_bytes_retained,
        "derived_bytes_retained": derived_bytes_retained,
        "post_e3_session_count": post_e3_released,
        "post_e3_truth_released": all(
            row.observed.truth is None and row.observed.derived is None
            for row in finalized if row.key[1] > 20221230),
        "compact_atlas_session_count": len(finalized),
        "selected_objective_target_provider_ready": all(
            row.atlas.receipt.get("candidate_suffix_rows_visited",
                                 row.atlas.receipt.get("suffix_row_visits")) == 0
            for row in finalized),
        "selected_horizon_coordinates": list(SELECTED_HORIZON_COORDINATES),
        "selected_horizon_schema_sha256": SELECTED_HORIZON_SCHEMA_SHA256,
        "selected_horizon_target_law": SELECTED_HORIZON_TARGET_LAW,
        "selected_horizon_status_codes": [item.value for item in EndpointStatus],
        "selected_horizon_coverage_schema":
            SELECTED_HORIZON_COVERAGE_SCHEMA,
        "selected_horizon_coverage_law": SELECTED_HORIZON_COVERAGE_LAW,
        "selected_horizon_coverage_law_sha256":
            SELECTED_HORIZON_COVERAGE_LAW_SHA256,
        "selected_horizon_start_d8": diagnostic_start_d8,
        "selected_horizon_coverage": (
            dict(coverage) if coverage is not None else None),
        "selected_horizon_coverage_sha256": (
            coverage["receipt_sha256"] if coverage is not None else None),
        "selected_horizon_tensors_aggregate_sha256": corpus.receipt[
            "selected_horizon_tensors_aggregate_sha256"] if isinstance(
                corpus, EntryCorpus) else None,
        "prior_scale_conversion_law": PRIOR_SCALE_CONVERSION_LAW,
        "prior_scale_conversion_law_sha256":
            PRIOR_SCALE_CONVERSION_LAW_SHA256,
        "prior_scale_pnl_units_per_usd": PNL_UNITS_PER_USD,
    }
    body["semantic_identity_sha256"] = _diagnostic_semantic_identity(
        corpus, finalized, bindings)
    body[LIFECYCLE_PROVENANCE_RECEIPT_KEY] = dict(_lifecycle_provenance(
        corpus, finalized,
        physical_full_pack_opens=corpus.receipt.get(
            "physical_full_pack_opens", body["physical_full_pack_opens"]),
        model_array_physical_fills=corpus.receipt.get(
            "model_array_physical_fills", body["model_array_physical_fills"]),
        diagnostic_plane_bytes=body["diagnostic_plane_bytes"],
        warm_corpus_ready=body["warm_corpus_ready"],
    ))
    body["receipt_sha256"] = C.object_sha256(body)
    return DiagnosticCorpus(
        corpus, tuple(finalized), bindings, MappingProxyType(body)
    )


def merge_diagnostic_corpora(
    corpus: EntryCorpus,
    windows: Sequence[DiagnosticCorpus],
) -> DiagnosticCorpus:
    """Merge finalized adjacent windows without revisiting an old truth plane."""
    parts = tuple(windows)
    if len(parts) < 2:
        raise DiagnosticCorpusRefusal(
            "diagnostic chronological merge requires multiple windows"
        )
    corpus_chain = corpus.receipt.get("corpus_window", {}).get("window_chain", {})
    chain_parts = corpus_chain.get("parts")
    if not isinstance(chain_parts, list) or len(chain_parts) != len(parts):
        raise DiagnosticCorpusRefusal("diagnostic/corpus window chains differ")
    reference = parts[0].receipt
    merged_coverage = (corpus.receipt.get("selected_horizon_coverage")
                       if isinstance(corpus, EntryCorpus) else None)
    if isinstance(corpus, EntryCorpus):
        try:
            validate_selected_horizon_coverage(merged_coverage)
        except SelectedHorizonContractRefusal as exc:
            raise DiagnosticCorpusRefusal(
                "diagnostic merge lacks exact selected-horizon coverage"
            ) from exc
    finalized: list[FinalizedDiagnosticSession] = []
    binding_ids: set[str] = set()
    bindings: list[CandidateTruthBinding] = []
    day_owners: set[int] = set()
    diagnostic_chain: list[dict[str, Any]] = []
    for index, (part, corpus_part) in enumerate(zip(parts, chain_parts)):
        receipt = dict(part.receipt)
        claimed = receipt.pop("receipt_sha256", None)
        if not isinstance(claimed, str) or C.object_sha256(receipt) != claimed:
            raise DiagnosticCorpusRefusal("diagnostic window receipt hash drift")
        if (part.corpus.receipt["receipt_sha256"]
                != corpus_part.get("receipt_sha256")
                or part.receipt.get("source_corpus_receipt_sha256")
                    != part.corpus.receipt["receipt_sha256"]):
            raise DiagnosticCorpusRefusal("diagnostic source window binding differs")
        if (part.receipt.get("schema") != DIAGNOSTIC_CORPUS_SCHEMA
                or part.receipt.get("candidate_suffix_rows_visited") != 0
                or part.receipt.get("h2_permit") is not False
                or part.receipt.get("prior_scale_conversion_law")
                    != PRIOR_SCALE_CONVERSION_LAW
                or part.receipt.get("prior_scale_conversion_law_sha256")
                    != PRIOR_SCALE_CONVERSION_LAW_SHA256
                or part.receipt.get("prior_scale_pnl_units_per_usd")
                    != PNL_UNITS_PER_USD):
            raise DiagnosticCorpusRefusal("diagnostic window law/suffix drift")
        if isinstance(part.corpus, EntryCorpus):
            local_coverage = part.corpus.receipt.get(
                "selected_horizon_coverage")
            try:
                validate_selected_horizon_coverage(local_coverage)
            except SelectedHorizonContractRefusal as exc:
                raise DiagnosticCorpusRefusal(
                    "diagnostic window selected-horizon coverage differs"
                ) from exc
            if (part.receipt.get("selected_horizon_coverage_sha256")
                    != local_coverage.get("receipt_sha256")
                    or part.receipt.get("selected_horizon_coverage_law_sha256")
                    != SELECTED_HORIZON_COVERAGE_LAW_SHA256):
                raise DiagnosticCorpusRefusal(
                    "diagnostic window selected-horizon binding differs"
                )
        local_days = {row.key[1] for row in part.sessions}
        if day_owners.intersection(local_days):
            raise DiagnosticCorpusRefusal("diagnostic windows overlap a whole day")
        day_owners.update(local_days)
        for row in part.sessions:
            row.observed.validate_backing()
            suffix = row.atlas.receipt.get(
                "candidate_suffix_rows_visited",
                row.atlas.receipt.get("suffix_row_visits"),
            )
            if suffix != 0:
                raise DiagnosticCorpusRefusal("diagnostic atlas suffix law drift")
            finalized.append(row)
        for binding in part.bindings:
            if binding.candidate_id in binding_ids:
                raise DiagnosticCorpusRefusal("diagnostic binding overlap")
            binding_ids.add(binding.candidate_id)
            bindings.append(binding)
        diagnostic_chain.append({
            "receipt_sha256": claimed,
            "minimum_d8_exclusive": corpus_part.get("minimum_d8_exclusive"),
            "maximum_d8": corpus_part.get("maximum_d8"),
        })
        if index and corpus_part.get("minimum_d8_exclusive") != (
                chain_parts[index - 1].get("maximum_d8")):
            raise DiagnosticCorpusRefusal("diagnostic window chain has a gap/overlap")
    finalized.sort(key=lambda row: (row.key[1], row.key[0], row.observed.source.receipt.receipt_sha256))
    flattened = tuple(
        binding for row in finalized for binding in row.bindings
    )
    if tuple(binding.candidate_id for binding in flattened) != tuple(
            binding.candidate_id for binding in bindings):
        # Input windows must themselves already be canonical; sorting must not
        # silently repair a semantically observable completion order.
        bindings = list(flattened)
    source_union = sorted({
        row.observed.source.receipt.receipt_sha256 for row in finalized
    })
    if len(source_union) != len(finalized):
        raise DiagnosticCorpusRefusal("diagnostic merged source union duplicates")
    expected_union = (sorted(
        str(row["source_receipt_sha256"])
        for row in merged_coverage["diagnostic_sessions"]
    ) if merged_coverage is not None else sorted({
        spec.source.receipt.receipt_sha256 for spec in corpus.sessions
    }))
    if source_union != expected_union:
        raise DiagnosticCorpusRefusal("diagnostic merged source union is not exact")
    chain = {
        "schema": "entry-v2-diagnostic-window-chain-v1",
        "parts": diagnostic_chain,
    }
    chain["chain_sha256"] = C.object_sha256(chain)
    body = dict(reference)
    body.pop("receipt_sha256", None)
    summed = (
        "truth_quality_index_count", "physical_full_pack_opens",
        "model_array_physical_fills", "header_revalidations", "array_cache_hits",
        "diagnostic_plane_bytes", "truth_bytes_materialized",
        "derived_bytes_materialized", "truth_bytes_retained",
        "derived_bytes_retained", "post_e3_session_count",
        "compact_atlas_session_count",
    )
    body.update({key: sum(int(part.receipt[key]) for part in parts)
                 for key in summed})
    body.update({
        "source_corpus_receipt_sha256": corpus.receipt["receipt_sha256"],
        "source_model_input_binding_sha256": corpus.model_input_binding.binding_sha256,
        "source_corpus_window_sha256": C.object_sha256(
            dict(corpus.receipt["corpus_window"])),
        "corpus_maximum_d8": corpus.receipt["corpus_window"]["maximum_d8"],
        "observed_start_d8": min((row.key[1] for row in finalized), default=None),
        "observed_end_d8": max((row.key[1] for row in finalized), default=None),
        "session_count": len(finalized),
        "candidate_count": len(bindings),
        "session_receipts": [row.observed.receipt["receipt_sha256"]
                             for row in finalized],
        "atlas_receipts": [row.atlas.receipt["receipt_sha256"]
                           for row in finalized],
        "one_open_per_session": all(
            part.receipt["one_open_per_session"] is True for part in parts),
        "diagnostic_planes_disk_backed": all(
            part.receipt["diagnostic_planes_disk_backed"] is True for part in parts),
        "diagnostic_plane_receipts_sha256": C.object_sha256(sorted(
            row.observed.receipt["diagnostic_plane_sha256"]
            for row in finalized
            if row.observed.receipt["diagnostic_plane_sha256"] is not None)),
        "durable_products_ready": all(
            part.receipt["durable_products_ready"] is True for part in parts),
        "warm_corpus_ready": all(
            part.receipt["warm_corpus_ready"] is True for part in parts),
        "source_receipt_union": source_union,
        "source_receipt_union_sha256": C.object_sha256(source_union),
        "truth_start_d8": min(part.receipt["truth_start_d8"] for part in parts),
        "truth_end_d8": max(part.receipt["truth_end_d8"] for part in parts),
        "derived_end_d8": max(part.receipt["derived_end_d8"] for part in parts),
        "post_e3_truth_released": all(
            part.receipt["post_e3_truth_released"] is True for part in parts),
        "selected_objective_target_provider_ready": all(
            part.receipt["selected_objective_target_provider_ready"] is True
            for part in parts),
        "selected_horizon_coordinates": corpus.receipt[
            "selected_horizon_coordinates"] if isinstance(
                corpus, EntryCorpus) else reference.get(
                    "selected_horizon_coordinates"),
        "selected_horizon_schema_sha256": corpus.receipt[
            "selected_horizon_schema_sha256"] if isinstance(
                corpus, EntryCorpus) else reference.get(
                    "selected_horizon_schema_sha256"),
        "selected_horizon_target_law": corpus.receipt[
            "selected_horizon_target_law"] if isinstance(
                corpus, EntryCorpus) else reference.get(
                    "selected_horizon_target_law"),
        "selected_horizon_status_codes": corpus.receipt[
            "selected_horizon_status_codes"] if isinstance(
                corpus, EntryCorpus) else reference.get(
                    "selected_horizon_status_codes"),
        "selected_horizon_coverage_schema": corpus.receipt[
            "selected_horizon_coverage_schema"] if isinstance(
                corpus, EntryCorpus) else reference.get(
                    "selected_horizon_coverage_schema"),
        "selected_horizon_coverage_law": corpus.receipt[
            "selected_horizon_coverage_law"] if isinstance(
                corpus, EntryCorpus) else reference.get(
                    "selected_horizon_coverage_law"),
        "selected_horizon_coverage_law_sha256": corpus.receipt[
            "selected_horizon_coverage_law_sha256"] if isinstance(
                corpus, EntryCorpus) else reference.get(
                    "selected_horizon_coverage_law_sha256"),
        "selected_horizon_start_d8": corpus.receipt[
            "selected_horizon_start_d8"] if isinstance(
                corpus, EntryCorpus) else reference.get(
                    "selected_horizon_start_d8"),
        "selected_horizon_coverage": dict(merged_coverage) if isinstance(
            merged_coverage, Mapping) else reference.get(
                "selected_horizon_coverage"),
        "selected_horizon_coverage_sha256": corpus.receipt[
            "selected_horizon_coverage_sha256"] if isinstance(
                corpus, EntryCorpus) else reference.get(
                    "selected_horizon_coverage_sha256"),
        "selected_horizon_tensors_aggregate_sha256": corpus.receipt[
            "selected_horizon_tensors_aggregate_sha256"] if isinstance(
                corpus, EntryCorpus) else reference.get(
                    "selected_horizon_tensors_aggregate_sha256"),
        "window_chain": chain,
    })
    body["semantic_identity_sha256"] = _diagnostic_semantic_identity(
        corpus, finalized, bindings)
    body[LIFECYCLE_PROVENANCE_RECEIPT_KEY] = dict(
        _merge_lifecycle_provenance(corpus, parts)
    )
    body["receipt_sha256"] = C.object_sha256(body)
    return DiagnosticCorpus(
        corpus, tuple(finalized), tuple(bindings), MappingProxyType(body)
    )


__all__ = [
    "CORPUS_READY_MILESTONE_SOURCE",
    "DIAGNOSTIC_PLANE_LAW_SHA256",
    "DIAGNOSTIC_CORPUS_SCHEMA", "DiagnosticCorpus",
    "LIFECYCLE_COLD", "LIFECYCLE_MIXED", "LIFECYCLE_WARM",
    "LIFECYCLE_PROVENANCE_RECEIPT_KEY", "LIFECYCLE_PROVENANCE_SCHEMA",
    "PRIOR_SCALE_CONVERSION_LAW", "PRIOR_SCALE_CONVERSION_LAW_SHA256",
    "SELECTED_HORIZON_COVERAGE_LAW",
    "SELECTED_HORIZON_COVERAGE_LAW_SHA256",
    "SELECTED_HORIZON_COVERAGE_SCHEMA",
    "DiagnosticCorpusObserver", "DiagnosticCorpusRefusal",
    "FinalizedDiagnosticSession", "ObservedDiagnosticSession",
    "finalize_diagnostic_corpus", "load_durable_diagnostic_planes",
    "merge_diagnostic_corpora",
]
