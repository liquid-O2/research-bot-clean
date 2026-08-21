"""Store reader, input capture and builder registry for the disc native gate.

The pure comparator lives in disc_native_differential.py; this module is the
half that touches real data.  It exists so the future C++ rebuild of
`CausalDiscretionaryPlane.feature_map` (discretionary_features.py:2389) can be
dropped in as one more registered builder and immediately measured against the
bytes already sitting in the dense store.

Everything here opens the store READ-ONLY.  No path under dense_store/ is ever
written; the differential's only output is its JSON report under
artifacts/entry_v2/tabular_recovery/diagnostics/.
"""

from __future__ import annotations

import contextlib
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterator, Mapping, Sequence

import numpy as np
from threadpoolctl import threadpool_limits

from engine.entry_v2 import confirmation
from engine.entry_v2.confirmation_experiment import (
    AuthoritativeConfirmationSessionSpec, discover_authoritative_session_specs)
from engine.entry_v2.diagnostic_inputs import fit_only_rehearsal_windows
from engine.entry_v2.disc_native_differential import (
    DISC_FEATURE_NAME_PREFIX, BuiltFeatures, DiscNativeVerdict,
    detach_capture_arrays)
from engine.entry_v2.discretionary_features import CausalDiscretionaryPlane
from engine.entry_v2.tabular_campaign import (
    NATIVE_THREADS_PER_CORPUS_WORKER, _dense_session_identity,
    materialize_runtime_dense_feature_session)

DISC_NATIVE_STORE_ROOT = Path(
    "/workspace/artifacts/entry_v2/tabular_recovery/dense_store")
DISC_NATIVE_SOURCE_ROOT = Path("/workspace/artifacts/cache/port/entry_v2")
DISC_NATIVE_MAX_DELAY_SEC = 300
# The store spans both rehearsal chronologies; one union window covers it.
DISC_NATIVE_STAGES = ("E1r", "E2r")
# Row-identity columns compared array-wise.  feature_receipt_sha256 is
# deliberately absent: it embeds implementation_sha256 (confirmation.py:168-176)
# and MUST differ once a native builder replaces the Python path.
SHARD_IDENTITY_COLUMNS = (
    "opportunity_id", "series_id", "candidate_id", "asset", "day", "side",
    "phase", "snapshot_ts_ns", "event_cutoff", "entry_event_ordinal",
    "entry_availability_ts_ns", "watch_age_sec", "sampling_reason")


@dataclass(frozen=True, slots=True)
class StoreSession:
    """One dense-store shard plus the spec that regenerates it."""

    spec: AuthoritativeConfirmationSessionSpec
    identity: str
    artifact_path: Path

    @property
    def label(self) -> str:
        return f"{self.spec.asset}/{self.spec.trading_day}"

    @property
    def prior_present(self) -> bool:
        return self.spec.previous_trading_day is not None


def disc_native_union_window() -> tuple[int, int]:
    bounds = [window for stage in DISC_NATIVE_STAGES
              for window in fit_only_rehearsal_windows(stage).values()]
    return min(low for low, _ in bounds), max(high for _, high in bounds)


def discover_store_sessions(
    *, source_root: Path = DISC_NATIVE_SOURCE_ROOT,
    store_root: Path = DISC_NATIVE_STORE_ROOT,
) -> tuple[StoreSession, ...]:
    """Every roster session whose dense shard is already on disk.

    The store is identity-addressed and the identity is not invertible, so the
    mapping runs forward: enumerate the authoritative roster, recompute each
    spec's identity with the store's own function, and keep the ones present.
    """

    specs = discover_authoritative_session_specs(
        source_root, disc_native_union_window())
    found = []
    for spec in specs:
        if spec.event_path is None:
            continue
        identity = _dense_session_identity(
            spec, max_delay_sec=DISC_NATIVE_MAX_DELAY_SEC)
        artifact = (Path(store_root) / identity / spec.asset
                    / f"{spec.trading_day}.npz")
        if artifact.is_file():
            found.append(StoreSession(spec, identity, artifact))
    return tuple(found)


def select_store_sessions(
    sessions: Sequence[StoreSession], selector: str,
) -> tuple[StoreSession, ...]:
    """`N-per-asset` deliberately covers prior-present AND prior-absent days.

    Prior-session memory is a whole feature family (PriorSessionContext,
    discretionary_features.py:66) that is simply absent on a roster's first
    session.  A sample of only prior-present days would leave that family
    untested, so the per-asset quota is filled prior-absent-first.
    """

    if selector == "all-store":
        return tuple(sessions)
    if not selector.endswith("-per-asset"):
        raise ValueError(
            "session selector must be 'all-store' or 'N-per-asset', got "
            f"{selector!r}")
    quota = int(selector.split("-", 1)[0])
    chosen: list[StoreSession] = []
    for asset in sorted({session.spec.asset for session in sessions}):
        pool = [session for session in sessions if session.spec.asset == asset]
        absent = [session for session in pool if not session.prior_present]
        present = [session for session in pool if session.prior_present]
        chosen.extend((absent[:1] + present + absent[1:])[:quota])
    return tuple(chosen)


@dataclass(frozen=True, slots=True)
class StoredShardView:
    """Read-only view of a shard: values, name order, identity columns."""

    names: tuple[str, ...]
    matrix: np.ndarray
    identity: Mapping[str, np.ndarray]

    def disc_view(self) -> BuiltFeatures:
        columns = np.asarray([
            index for index, name in enumerate(self.names)
            if name.startswith(DISC_FEATURE_NAME_PREFIX)], np.int64)
        if not len(columns):
            raise ValueError(
                "shard carries no disc_ columns; the disc plane never ran")
        return BuiltFeatures(
            tuple(self.names[int(index)] for index in columns),
            np.ascontiguousarray(self.matrix[:, columns], np.float32),
            np.asarray(self.identity["snapshot_ts_ns"], np.int64),
            np.asarray(self.identity["side"], np.int64))

    def full_view(self) -> BuiltFeatures:
        return BuiltFeatures(
            self.names, np.asarray(self.matrix, np.float32),
            np.asarray(self.identity["snapshot_ts_ns"], np.int64),
            np.asarray(self.identity["side"], np.int64))


def read_stored_shard(path: Path) -> StoredShardView:
    """Open a stored .npz read-only.  Receipt strings are never read back."""

    with np.load(Path(path), allow_pickle=False) as handle:
        names = tuple(str(name) for name in handle["feature_names"])
        matrix = np.ascontiguousarray(handle["features"], np.float32)
        identity = {column: np.asarray(handle[column])
                    for column in SHARD_IDENTITY_COLUMNS}
    return StoredShardView(names, matrix, identity)


def shard_view_of_result(shard: object) -> StoredShardView:
    """Same view over a freshly computed CausalFeatureShard, no file involved."""

    return StoredShardView(
        tuple(str(name) for name in shard.feature_names),
        np.ascontiguousarray(shard.features, np.float32),
        {column: np.asarray(getattr(shard, column))
         for column in SHARD_IDENTITY_COLUMNS})


def compare_shard_identity_columns(
    reference: StoredShardView, candidate: StoredShardView, *, limit: int = 4,
) -> DiscNativeVerdict:
    """Every row-identity column, array-wise; receipt strings excluded."""

    failures: list[str] = []
    for column in SHARD_IDENTITY_COLUMNS:
        left = np.asarray(reference.identity[column])
        right = np.asarray(candidate.identity[column])
        if left.shape != right.shape:
            failures.append(
                f"identity column {column} shape differs: "
                f"reference={left.shape} candidate={right.shape}")
            continue
        differing = np.flatnonzero(left.astype(str) != right.astype(str))
        if len(differing):
            head = ", ".join(
                f"row {int(index)}: reference={left[index]!r} "
                f"candidate={right[index]!r}" for index in differing[:limit])
            failures.append(
                f"identity column {column} differs in {len(differing)} "
                f"row(s): {head}")
    return DiscNativeVerdict("PASS" if not failures else "FAIL",
                             tuple(failures))


class DiscCaptureComplete(RuntimeError):
    """Sentinel that aborts a dense materialize once enough rows are recorded."""


@dataclass(slots=True)
class DiscSessionCapture:
    """Exactly what confirmation.py hands the disc plane, for one session.

    `construction` is the kwargs at confirmation.py:1142; `queries` is one
    entry per emitted row, in emission order, as passed at confirmation.py:1260.
    Together they are the whole input surface a native builder must consume.
    """

    construction: dict[str, object] = field(default_factory=dict)
    queries: list[dict[str, object]] = field(default_factory=list)
    disc_seconds: float = 0.0
    outer_seconds: float = 0.0
    shard: object | None = None
    aborted: bool = False


@contextlib.contextmanager
def recording_disc_plane(
    capture: DiscSessionCapture, *, query_limit: int | None = None,
) -> Iterator[None]:
    """Patch the plane class confirmation.py resolves, record, then restore.

    A subclass that records and delegates cannot change the numbers: every
    computation still runs in the frozen module.  `query_limit` aborts the
    materialize once enough rows are recorded, which is what makes the refusal
    fixtures and the profile split cheap.
    """

    original = confirmation.CausalDiscretionaryPlane

    class _RecordingDiscretionaryPlane(original):  # type: ignore[misc,valid-type]

        def __init__(self, **kwargs: object) -> None:
            super().__init__(**kwargs)
            capture.construction = detach_capture_arrays(kwargs)

        def feature_map(self, **kwargs: object) -> Mapping[str, float]:
            if query_limit is not None and len(capture.queries) >= query_limit:
                capture.aborted = True
                raise DiscCaptureComplete("disc capture reached its row limit")
            capture.queries.append(dict(kwargs))
            start = time.perf_counter()
            try:
                return super().feature_map(**kwargs)
            finally:
                capture.disc_seconds += time.perf_counter() - start

    confirmation.CausalDiscretionaryPlane = _RecordingDiscretionaryPlane
    try:
        yield
    finally:
        confirmation.CausalDiscretionaryPlane = original


@contextlib.contextmanager
def timing_confirmation_plane(capture: DiscSessionCapture) -> Iterator[None]:
    """Wall-clock the outer per-row map so disc vs REST needs no profiler.

    The outer map is `_SessionPlane.feature_map` (confirmation.py:1165); its
    disc call sits at confirmation.py:1259-1270, so REST = outer - disc.
    """

    original = confirmation._SessionPlane.feature_map

    def _timed_confirmation_feature_map(self, *args: object, **kwargs: object):
        start = time.perf_counter()
        try:
            return original(self, *args, **kwargs)
        finally:
            capture.outer_seconds += time.perf_counter() - start

    confirmation._SessionPlane.feature_map = _timed_confirmation_feature_map
    try:
        yield
    finally:
        confirmation._SessionPlane.feature_map = original


def capture_disc_session(
    session: StoreSession, *, query_limit: int | None = None,
    time_outer: bool = False,
) -> DiscSessionCapture:
    """Cold-compute one dense session and record the disc plane's inputs.

    The recompute is the point: its shard is what proves the oracle still
    reproduces its own stored bytes before any candidate is judged against
    them.
    """

    capture = DiscSessionCapture()
    outer = (timing_confirmation_plane(capture) if time_outer
             else contextlib.nullcontext())
    with recording_disc_plane(capture, query_limit=query_limit), outer:
        try:
            capture.shard = materialize_runtime_dense_feature_session(
                session.spec, max_delay_sec=DISC_NATIVE_MAX_DELAY_SEC)
        except DiscCaptureComplete:
            capture.shard = None
    if not capture.construction or not capture.queries:
        raise RuntimeError(
            f"capture recorded nothing for {session.label}: "
            f"construction={bool(capture.construction)} "
            f"queries={len(capture.queries)}")
    return capture


def build_disc_features(
    construction: Mapping[str, object], queries: Sequence[Mapping[str, object]],
) -> BuiltFeatures:
    """Evaluate the frozen oracle cold over one session's recorded queries.

    Pinned to the same BLAS topology the dense corpus workers use
    (tabular_campaign.py:359) — the store's own comment warns that float64
    provenance varies with reduction topology otherwise.
    """

    names: tuple[str, ...] | None = None
    matrix: np.ndarray | None = None
    snapshots = np.empty(len(queries), np.int64)
    sides = np.empty(len(queries), np.int64)
    with threadpool_limits(limits=NATIVE_THREADS_PER_CORPUS_WORKER):
        plane = CausalDiscretionaryPlane(**construction)
        for index, query in enumerate(queries):
            mapping = plane.feature_map(**query)
            emitted = tuple(mapping)
            if names is None:
                names = emitted
                matrix = np.empty((len(queries), len(names)), np.float32)
            elif emitted != names:
                raise RuntimeError(
                    "oracle emitted a different name order at row "
                    f"{index}: first divergence "
                    f"{next(a for a, b in zip(emitted, names) if a != b)!r}")
            matrix[index] = np.asarray(tuple(mapping.values()), np.float32)
            snapshots[index] = int(query["snapshot_ts_ns"])
            sides[index] = int(query["side"])
    return BuiltFeatures(names, matrix, snapshots, sides)


DiscNativeBuilder = Callable[[DiscSessionCapture, StoredShardView], BuiltFeatures]


@dataclass(frozen=True, slots=True)
class RegisteredDiscBuilder:
    """One candidate implementation of the per-row disc query path."""

    name: str
    build: DiscNativeBuilder
    consumes_inputs: bool
    emits_float64: bool
    note: str


def _oracle_build(
    capture: DiscSessionCapture, stored: StoredShardView,
) -> BuiltFeatures:
    return build_disc_features(capture.construction, capture.queries)


def _stub_store_build(
    capture: DiscSessionCapture, stored: StoredShardView,
) -> BuiltFeatures:
    return stored.disc_view()


DISC_NATIVE_BUILDERS: Mapping[str, RegisteredDiscBuilder] = {
    "oracle": RegisteredDiscBuilder(
        "oracle", _oracle_build, True, False,
        "the frozen Python path, re-evaluated cold from the recorded inputs"),
    "stub-store": RegisteredDiscBuilder(
        "stub-store", _stub_store_build, False, False,
        "returns the stored shard bytes verbatim; a plumbing stand-in for the "
        "future native module, so it can only ever fail on the mutants"),
}


__all__ = [
    "DISC_NATIVE_BUILDERS", "DISC_NATIVE_MAX_DELAY_SEC",
    "DISC_NATIVE_SOURCE_ROOT", "DISC_NATIVE_STORE_ROOT",
    "DiscCaptureComplete", "DiscSessionCapture", "RegisteredDiscBuilder",
    "SHARD_IDENTITY_COLUMNS", "StoreSession", "StoredShardView",
    "build_disc_features", "capture_disc_session",
    "compare_shard_identity_columns", "discover_store_sessions",
    "read_stored_shard", "recording_disc_plane", "select_store_sessions",
    "shard_view_of_result", "timing_confirmation_plane",
]
