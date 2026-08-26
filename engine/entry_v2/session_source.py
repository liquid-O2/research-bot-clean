"""Immutable external pin for exactly one QRE2 asset-session."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
import hashlib
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterator, Mapping

import numpy as np

from . import common as C
from .event_pack import (
    CATEGORICAL_FIELDS,
    CONTINUOUS_FIELDS,
    HEADER_BYTES,
    HEADER,
    MAGIC,
    ROW_BYTES,
    VERSION,
    EventPack,
)
from .session_cache import SessionArrayCache
from .session_receipt import (
    CUTOFF_RULE,
    MODEL_ARRAYS_CONVERSION_LAW_SHA256,
    SIDECAR_SCHEMA,
    SessionSourceMeasurements,
    SessionStreamReceipt,
)
from .session_stream_io import (
    _SIDECAR_LAYOUT,
    _canonical_source_path,
    _exact_int,
    _guard_path_components,
    _identity_int,
    _sha256,
    _strict_json_object,
)


@dataclass(frozen=True, slots=True)
class SessionEventSource:
    """Immutable external pin for exactly one QRE2 asset-session."""

    qre2_path: Path
    source_sha256: str
    sidecar_sha256: str
    asset: str
    d8: int
    locked_iid: int
    open_utc: int
    close_utc: int
    event_count: int
    max_cutoff: int
    source_size_bytes: int
    source_device: int
    source_inode: int
    source_mtime_ns: int
    source_ctime_ns: int
    array_cache: SessionArrayCache | None = field(
        default=None, compare=False, repr=False
    )
    measurements: SessionSourceMeasurements = field(
        default_factory=SessionSourceMeasurements, init=False,
        compare=False, repr=False
    )

    def __post_init__(self) -> None:
        d8 = _exact_int(self.d8, "d8")
        C.guard_date(d8)
        asset = str(self.asset).upper()
        if asset not in C.ASSET_INDEX:
            raise C.EntryV2Refusal(f"unknown session-stream asset: {self.asset!r}")
        path = _canonical_source_path(self.qre2_path, d8)
        iid = _exact_int(self.locked_iid, "locked_iid")
        open_utc = _exact_int(self.open_utc, "open_utc")
        close_utc = _exact_int(self.close_utc, "close_utc")
        event_count = _exact_int(self.event_count, "event_count")
        max_cutoff = _exact_int(self.max_cutoff, "max_cutoff")
        source_size = _exact_int(self.source_size_bytes, "source_size_bytes")
        source_device = _exact_int(self.source_device, "source_device")
        source_inode = _exact_int(self.source_inode, "source_inode")
        source_mtime = _exact_int(self.source_mtime_ns, "source_mtime_ns")
        source_ctime = _exact_int(self.source_ctime_ns, "source_ctime_ns")
        if self.array_cache is not None and not isinstance(
                self.array_cache, SessionArrayCache):
            raise C.EntryV2Refusal("array_cache must be a SessionArrayCache")
        if not isinstance(self.measurements, SessionSourceMeasurements):
            raise C.EntryV2Refusal("measurements must be SessionSourceMeasurements")
        if iid < 0 or open_utc <= 0 or close_utc <= open_utc:
            raise C.EntryV2Refusal("invalid pinned QRE2 session clock/IID")
        if event_count < 0 or not 0 <= max_cutoff <= event_count:
            raise C.EntryV2Refusal(
                "max_cutoff must lie inside the pinned event count"
            )
        expected_size = HEADER_BYTES + event_count * ROW_BYTES
        if (source_size != expected_size or source_device < 0 or source_inode <= 0
                or source_mtime <= 0 or source_ctime <= 0):
            raise C.EntryV2Refusal("invalid verified QRE2 source stat identity")
        object.__setattr__(self, "qre2_path", path)
        object.__setattr__(self, "source_sha256",
                           _sha256(self.source_sha256, "source"))
        object.__setattr__(self, "sidecar_sha256",
                           _sha256(self.sidecar_sha256, "sidecar"))
        object.__setattr__(self, "asset", asset)
        object.__setattr__(self, "d8", d8)
        object.__setattr__(self, "locked_iid", iid)
        object.__setattr__(self, "open_utc", open_utc)
        object.__setattr__(self, "close_utc", close_utc)
        object.__setattr__(self, "event_count", event_count)
        object.__setattr__(self, "max_cutoff", max_cutoff)
        object.__setattr__(self, "source_size_bytes", source_size)
        object.__setattr__(self, "source_device", source_device)
        object.__setattr__(self, "source_inode", source_inode)
        object.__setattr__(self, "source_mtime_ns", source_mtime)
        object.__setattr__(self, "source_ctime_ns", source_ctime)

    @property
    def trading_day(self) -> int:
        """Explicit asset-day key retained for downstream aggregation."""
        return self.d8

    @property
    def source_hash(self) -> str:
        """Alias matching :class:`RawPrefixRef` terminology."""
        return self.source_sha256

    @property
    def sidecar_path(self) -> Path:
        return self.qre2_path.with_suffix(self.qre2_path.suffix + ".json")

    @property
    def receipt(self) -> SessionStreamReceipt:
        start = HEADER_BYTES
        end = start + self.max_cutoff * ROW_BYTES
        return SessionStreamReceipt(
            qre2_path=str(self.qre2_path),
            source_sha256=self.source_sha256,
            sidecar_path=str(self.sidecar_path),
            sidecar_sha256=self.sidecar_sha256,
            asset=self.asset,
            d8=self.d8,
            trading_day=self.trading_day,
            locked_iid=self.locked_iid,
            open_utc=self.open_utc,
            close_utc=self.close_utc,
            pack_event_count=self.event_count,
            materialized_event_count=self.max_cutoff,
            source_event_byte_start=start,
            source_event_byte_end_exclusive=end,
            source_event_byte_count=end - start,
            conversion_law_sha256=MODEL_ARRAYS_CONVERSION_LAW_SHA256,
        )

    def durable_identity(self) -> Mapping[str, Any]:
        """Exact immutable source identity used by the persistent array key."""
        return MappingProxyType({
            "schema": "entry-v2-durable-session-source-v1",
            "session_stream_receipt": self.receipt.as_dict(),
            "source_stat": {
                "size_bytes": self.source_size_bytes,
                "device": self.source_device,
                "inode": self.source_inode,
                "mtime_ns": self.source_mtime_ns,
                "ctime_ns": self.source_ctime_ns,
            },
        })

    def _verify_canonical_file(self, path: Path, name: str) -> None:
        _guard_path_components(path)
        try:
            resolved = path.resolve(strict=True)
        except (FileNotFoundError, OSError) as exc:
            raise C.EntryV2Refusal(f"missing/unreadable pinned {name}: {path}") from exc
        if resolved != path:
            raise C.EntryV2Refusal(f"pinned {name} path identity drift: {path}")
        if not path.is_file():
            raise C.EntryV2Refusal(f"pinned {name} is not a regular file: {path}")

    def _read_and_verify_sidecar(self) -> Mapping[str, Any]:
        path = self.sidecar_path
        self._verify_canonical_file(path, "QRE2 sidecar")
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise C.EntryV2Refusal(f"cannot read pinned QRE2 sidecar: {path}") from exc
        actual = hashlib.sha256(raw).hexdigest()
        if actual != self.sidecar_sha256:
            raise C.EntryV2Refusal(
                f"event sidecar hash drift: expected={self.sidecar_sha256} actual={actual}"
            )
        obj = _strict_json_object(raw, "event sidecar")
        if obj.get("schema") != SIDECAR_SCHEMA or obj.get("status") != "READY":
            raise C.EntryV2Refusal("event sidecar schema/status identity drift")
        if obj.get("asset") != self.asset:
            raise C.EntryV2Refusal("event sidecar identity drift: asset")
        for name, expected in (
            ("asset_idx", C.ASSET_INDEX[self.asset]),
            ("d8", self.d8),
            ("locked_iid", self.locked_iid),
            ("open_utc", self.open_utc),
            ("close_utc", self.close_utc),
            ("event_count", self.event_count),
        ):
            _identity_int(obj, name, expected)
        if obj.get("event_pack_sha256") != self.source_sha256:
            raise C.EntryV2Refusal("event sidecar source-hash identity drift")
        source_hashes = obj.get("source_hashes")
        if (not isinstance(source_hashes, dict)
                or source_hashes.get("event_pack_sha256") != self.source_sha256):
            raise C.EntryV2Refusal("event sidecar nested source-hash identity drift")

        window = obj.get("record_window")
        if not isinstance(window, dict):
            raise C.EntryV2Refusal("event sidecar record window missing")
        try:
            start = _exact_int(window["start_d8"], "record_window.start_d8")
            end = _exact_int(
                window["end_d8_exclusive"], "record_window.end_d8_exclusive"
            )
        except KeyError as exc:
            raise C.EntryV2Refusal("event sidecar record window incomplete") from exc
        C.guard_decode_window(start, end)
        if not start <= self.d8 < end:
            raise C.EntryV2Refusal("event sidecar window excludes pinned d8")

        binary_file = obj.get("binary_file")
        if not isinstance(binary_file, str) or not binary_file:
            raise C.EntryV2Refusal("event sidecar binary_file missing")
        binary_relative = Path(binary_file)
        _guard_path_components(binary_relative)
        if (binary_relative.is_absolute() or ".." in binary_relative.parts
                or binary_relative.name != self.qre2_path.name
                or len(binary_relative.parts) < 2
                or binary_relative.parts[-2] != self.asset):
            raise C.EntryV2Refusal("event sidecar binary_file identity drift")
        if obj.get("cutoff_rule") != CUTOFF_RULE:
            raise C.EntryV2Refusal("event sidecar cutoff law identity drift")
        clock_contract = {
            "session_assignment_clock": "ts_recv",
            "symbology_date_clock": "floor_utc(ts_recv)",
            "causal_visibility_clock": "IndexTs/ts_recv",
            "exchange_feature_clock": "ts_event",
            "equal_receive_time": "future",
            "tie_order": "ordered_input_manifest_then_dbn_decode_ordinal",
        }
        for name, expected in clock_contract.items():
            if obj.get(name) != expected:
                raise C.EntryV2Refusal(
                    f"event sidecar clock law identity drift: {name}"
                )

        binary_schema = obj.get("binary_schema")
        if not isinstance(binary_schema, dict):
            raise C.EntryV2Refusal("event sidecar binary schema missing")
        expected_schema = {
            "magic": MAGIC.decode("ascii"),
            "byte_order": "little",
            "header_bytes": HEADER_BYTES,
            "row_bytes": ROW_BYTES,
            "layout": "packed_array_of_structs",
        }
        for name, expected in expected_schema.items():
            if binary_schema.get(name) != expected:
                raise C.EntryV2Refusal(
                    f"event sidecar binary schema identity drift: {name}"
                )
        arrays = binary_schema.get("arrays")
        if not isinstance(arrays, list):
            raise C.EntryV2Refusal("event sidecar array layout missing")
        actual_layout: set[tuple[str, str, int]] = set()
        for item in arrays:
            if not isinstance(item, dict) or set(item) != {
                    "name", "dtype", "offset_bytes"}:
                raise C.EntryV2Refusal("event sidecar array descriptor malformed")
            try:
                descriptor = (
                    str(item["name"]),
                    str(item["dtype"]),
                    _exact_int(item["offset_bytes"], "array offset"),
                )
            except KeyError as exc:  # defensive; exact-key check normally catches it
                raise C.EntryV2Refusal(
                    "event sidecar array descriptor incomplete"
                ) from exc
            if descriptor in actual_layout:
                raise C.EntryV2Refusal("duplicate event sidecar array descriptor")
            actual_layout.add(descriptor)
        if frozenset(actual_layout) != _SIDECAR_LAYOUT:
            raise C.EntryV2Refusal("event sidecar array layout identity drift")
        return obj

    def _verify_source_path(self) -> None:
        self._verify_canonical_file(self.qre2_path, "QRE2 source")
        stat = self.qre2_path.stat()
        actual = (
            stat.st_size,
            stat.st_dev,
            stat.st_ino,
            stat.st_mtime_ns,
            stat.st_ctime_ns,
        )
        expected = (
            self.source_size_bytes,
            self.source_device,
            self.source_inode,
            self.source_mtime_ns,
            self.source_ctime_ns,
        )
        if actual != expected:
            raise C.EntryV2Refusal("QRE2 source stat identity drift")

    def _open_verified_pack(self) -> EventPack:
        # The corpus trust boundary already hashed the complete QRE2 once.  A
        # materialization rechecks its immutable path/stat/header/sidecar pins,
        # but never performs another full-file SHA pass.
        self._read_and_verify_sidecar()
        self._verify_source_path()

        # Construct explicitly so even an exception late in EventPack.__init__
        # can close a partially created memmap.  A normal ``EventPack(...)``
        # assignment cannot retain the object when __init__ raises.
        from . import session_stream as stream
        event_pack_cls = stream.EventPack
        pack = event_pack_cls.__new__(event_pack_cls)
        try:
            event_pack_cls.__init__(pack, self.qre2_path, verify_hash=False,
                                   require_sidecar=True)
            header = pack.header
            actual_identity = (
                pack.path,
                header.asset,
                header.d8,
                header.locked_iid,
                header.open_utc,
                header.close_utc,
                header.n_events,
            )
            expected_identity = (
                self.qre2_path,
                self.asset,
                self.d8,
                self.locked_iid,
                self.open_utc,
                self.close_utc,
                self.event_count,
            )
            if actual_identity != expected_identity:
                raise C.EntryV2Refusal("QRE2 header/path identity drift")
            if self.max_cutoff > header.n_events:
                raise C.EntryV2Refusal("max_cutoff exceeds verified QRE2 event count")
            # Re-hash the exact sidecar path loaded by EventPack after its open.
            if C.file_sha256(self.sidecar_path) != self.sidecar_sha256:
                raise C.EntryV2Refusal("event sidecar changed during pack open")
        except BaseException:
            self._close_pack(pack)
            raise
        return pack

    def _verify_cached_header(self) -> None:
        """Recheck the exact 60-byte binary identity without mapping rows."""
        self._read_and_verify_sidecar()
        self._verify_source_path()
        try:
            with self.qre2_path.open("rb") as handle:
                raw = handle.read(HEADER_BYTES)
        except OSError as exc:
            raise C.EntryV2Refusal("cannot read pinned QRE2 header") from exc
        if len(raw) != HEADER_BYTES:
            raise C.EntryV2Refusal("truncated pinned QRE2 header")
        try:
            values = HEADER.unpack(raw)
        except Exception as exc:
            raise C.EntryV2Refusal("invalid pinned QRE2 header") from exc
        actual = values
        expected = (
            MAGIC, VERSION, C.ASSET_INDEX[self.asset], self.d8,
            self.locked_iid, self.open_utc, self.close_utc,
            self.event_count, ROW_BYTES, 0,
        )
        if actual != expected:
            raise C.EntryV2Refusal("QRE2 header/path identity drift")

    @staticmethod
    def _close_pack(pack: EventPack) -> None:
        """Close even a pack whose constructor failed after mapping rows."""
        rows = getattr(pack, "rows", None)
        if rows is not None:
            pack.close()

    @staticmethod
    def _validate_arrays(pack: EventPack, continuous: np.ndarray,
                         categorical: np.ndarray, rows: int) -> None:
        if (type(continuous) is not np.ndarray
                or continuous.shape != (rows, len(CONTINUOUS_FIELDS))
                or continuous.dtype != np.dtype(np.float64)
                or not continuous.flags.c_contiguous):
            raise C.EntryV2Refusal("model continuous array violates conversion law")
        if (type(categorical) is not np.ndarray
                or categorical.shape != (rows, len(CATEGORICAL_FIELDS))
                or categorical.dtype != np.dtype(np.uint8)
                or not categorical.flags.c_contiguous):
            raise C.EntryV2Refusal("model categorical array violates conversion law")
        if (np.shares_memory(continuous, pack.rows)
                or np.shares_memory(categorical, pack.rows)):
            raise C.EntryV2Refusal("model arrays retain the QRE2 memory map")

    def publish_from_open_pack(self, pack: EventPack) -> bool:
        """Convert and cache this bounded prefix from an already-open pack.

        This is the one-open corpus/diagnostic boundary: the same verified
        mmap supplies both the compact truth plane and the learner prefix.
        Later training accesses are cache hits that recheck only the pinned
        sidecar, stat identity, and fixed header.
        """
        if self.array_cache is None:
            return False
        header = pack.header
        if (pack.path, header.asset, header.d8, header.locked_iid,
                header.open_utc, header.close_utc, header.n_events) != (
                self.qre2_path, self.asset, self.d8, self.locked_iid,
                self.open_utc, self.close_utc, self.event_count):
            raise C.EntryV2Refusal(
                "open pack identity differs from session array source"
            )
        self.measurements.record_full_pack_open()
        arrays = pack.model_arrays(stop=self.max_cutoff)
        self.measurements.record_model_array_fill()
        self._validate_arrays(pack, *arrays, self.max_cutoff)
        arrays[0].setflags(write=False)
        arrays[1].setflags(write=False)
        self._verify_source_path()
        return self.array_cache.publish_verified(self, *arrays)

    @contextmanager
    def open_arrays(self) -> Iterator[tuple[np.ndarray, np.ndarray]]:
        """Yield bounded raw NumPy arrays and always close the QRE2 memmap."""
        if self.array_cache is not None:
            def fill() -> tuple[np.ndarray, np.ndarray]:
                pack: EventPack | None = None
                try:
                    self.measurements.assert_full_pack_open_allowed()
                    pack = self._open_verified_pack()
                    self.measurements.record_full_pack_open()
                    arrays = pack.model_arrays(stop=self.max_cutoff)
                    self.measurements.record_model_array_fill()
                    self._validate_arrays(pack, *arrays, self.max_cutoff)
                    self._verify_source_path()
                    return arrays
                finally:
                    if pack is not None:
                        self._close_pack(pack)

            continuous, categorical, hit = self.array_cache.get_or_fill(
                self, fill
            )
            if hit:
                self._verify_cached_header()
                self.measurements.record_header_revalidation()
                self.measurements.record_cache_hit()
            try:
                yield continuous, categorical
            finally:
                if hit:
                    self._verify_source_path()
            return
        pack: EventPack | None = None
        continuous: np.ndarray | None = None
        categorical: np.ndarray | None = None
        try:
            self.measurements.assert_full_pack_open_allowed()
            pack = self._open_verified_pack()
            self.measurements.record_full_pack_open()
            continuous, categorical = pack.model_arrays(stop=self.max_cutoff)
            self.measurements.record_model_array_fill()
            self._validate_arrays(pack, continuous, categorical, self.max_cutoff)
            self._verify_source_path()
            yield continuous, categorical
        finally:
            # Drop the context's own array references before closing.  Returned
            # arrays own their bytes and may legitimately outlive the context.
            continuous = None
            categorical = None
            if pack is not None:
                self._close_pack(pack)
