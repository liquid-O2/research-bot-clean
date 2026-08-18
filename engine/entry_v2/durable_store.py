#!/usr/bin/env python3
"""Fail-closed content-addressed storage for reusable Entry V2 planes."""

from __future__ import annotations

from dataclasses import dataclass
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import threading
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from . import common as C


DURABLE_STORE_SCHEMA = "entry-v2-durable-store-v1"
DURABLE_PRODUCT_SCHEMA = "entry-v2-durable-product-v1"
DURABLE_STORE_LAW_SHA256 = hashlib.sha256(
    b"ENTRY_V2_DURABLE_STORE_V1|content-addressed|canonical-json|"
    b"regular-0444|tmp-fsync-rename-directory-fsync|no-rebuild-on-drift"
).hexdigest()
_KINDS = ("session-arrays", "diagnostic-planes", "verified-sessions")
_SHA = re.compile(r"[0-9a-f]{64}")
_LOCK_GUARD = threading.Lock()
_KEY_LOCKS: dict[tuple[str, str, str], threading.Lock] = {}


@dataclass(slots=True)
class DurableProduct:
    key: str
    data_path: Path
    sidecar_path: Path
    mapping: np.memmap
    arrays: tuple[np.ndarray, ...]
    receipt: Mapping[str, Any]
    published: bool

    def close(self) -> None:
        mmap_value = getattr(self.mapping, "_mmap", None)
        if mmap_value is not None and not mmap_value.closed:
            mmap_value.close()


def _strict_json(raw: bytes) -> dict[str, Any]:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in pairs:
            if key in out:
                raise C.EntryV2Refusal(f"duplicate durable sidecar key: {key}")
            out[key] = value
        return out

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique)
    except C.EntryV2Refusal:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise C.EntryV2Refusal("invalid durable sidecar JSON") from exc
    if not isinstance(value, dict) or C.canonical_bytes(value) != raw:
        raise C.EntryV2Refusal("durable sidecar is not canonical JSON")
    return value


def _mode_regular_0444(path: Path) -> os.stat_result:
    try:
        value = path.lstat()
    except OSError as exc:
        raise C.EntryV2Refusal("durable product is missing/unreadable") from exc
    if stat.S_ISLNK(value.st_mode) or not stat.S_ISREG(value.st_mode):
        raise C.EntryV2Refusal("durable product is not a regular file")
    if stat.S_IMODE(value.st_mode) != 0o444:
        raise C.EntryV2Refusal("durable product is mutable")
    return value


def _guard_dates(value: Any, name: str = "root") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            _guard_dates(item, str(key))
    elif isinstance(value, (list, tuple)):
        for item in value:
            _guard_dates(item, name)
    elif name.endswith("d8") and isinstance(value, int):
        C.guard_date(value)
    elif isinstance(value, str):
        if "path" in name.lower() and ".." in Path(value).parts:
            raise C.EntryV2Refusal("durable identity contains path traversal")
        if "path" in name.lower():
            for component in Path(value).parts:
                for d8 in C.dates_in_basename(component):
                    C.guard_date(d8)


class DurableEntryV2Store:
    """Persistent immutable store; close never removes published products."""

    def __init__(self, root: os.PathLike[str] | str) -> None:
        path = Path(root)
        if not path.is_absolute() or ".." in path.parts:
            raise C.EntryV2Refusal("durable store root must be absolute and canonical")
        if path.exists() and path.is_symlink():
            raise C.EntryV2Refusal("durable store root cannot be a symlink")
        if not path.exists():
            if not path.parent.is_dir():
                raise C.EntryV2Refusal("durable store parent is absent")
            path.mkdir(mode=0o700)
        if path.resolve(strict=True) != path or not path.is_dir():
            raise C.EntryV2Refusal("durable store root identity is invalid")
        self.root = path
        self._identity_laws: dict[str, dict[str, dict[str, str]]] = {
            kind: {} for kind in _KINDS
        }
        for kind in _KINDS:
            child = path / kind
            if child.exists() and child.is_symlink():
                raise C.EntryV2Refusal("durable store namespace cannot be a symlink")
            child.mkdir(mode=0o700, exist_ok=True)
        self._scan()

    def _scan(self) -> None:
        allowed = set(_KINDS)
        if {item.name for item in self.root.iterdir()} != allowed:
            raise C.EntryV2Refusal("durable store root contains extra entries")
        for kind in _KINDS:
            directory = self.root / kind
            # Publication creates temporary files in the namespace before the
            # immutable pair is renamed into place.  Startup must take the
            # same cross-process lock as publication or a sibling worker can
            # turn that valid transient state into a false corruption refusal.
            with self._publication_lock(directory):
                names = {item.name for item in directory.iterdir()}
                expected: set[str] = set()
                keys: set[str] = set()
                for name in names:
                    match = re.fullmatch(r"([0-9a-f]{64})\.(bin|json)", name)
                    if match is None:
                        raise C.EntryV2Refusal(
                            "durable store contains an extra entry")
                    keys.add(match.group(1))
                for key in keys:
                    expected.update((f"{key}.bin", f"{key}.json"))
                if names != expected:
                    raise C.EntryV2Refusal("durable product pair is incomplete")
                for key in sorted(keys):
                    body = self._load_metadata(kind, key)
                    self._index_metadata(kind, key, body)

    def _index_metadata(self, kind: str, key: str,
                        body: Mapping[str, Any]) -> None:
        identity_sha = C.object_sha256(body["identity"])
        law = str(body["product_law_sha256"])
        laws = self._identity_laws[kind].setdefault(identity_sha, {})
        prior = laws.get(law)
        if prior is not None and prior != key:
            raise C.EntryV2Refusal("durable identity/law index duplicates")
        laws[law] = key

    def _load_metadata(self, kind: str, key: str) -> Mapping[str, Any]:
        directory = self.root / kind
        data_path = directory / f"{key}.bin"
        sidecar_path = directory / f"{key}.json"
        data_stat = _mode_regular_0444(data_path)
        _mode_regular_0444(sidecar_path)
        body = _strict_json(sidecar_path.read_bytes())
        _guard_dates(body)
        required = {
            "schema", "store_schema", "store_law_sha256", "kind", "key",
            "product_law_sha256", "identity", "data_file", "data_size_bytes",
            "data_sha256", "arrays", "semantic", "producer", "receipt_sha256",
        }
        core = dict(body)
        claimed = core.pop("receipt_sha256", None)
        if (set(body) != required or body.get("schema") != DURABLE_PRODUCT_SCHEMA
                or body.get("store_schema") != DURABLE_STORE_SCHEMA
                or body.get("store_law_sha256") != DURABLE_STORE_LAW_SHA256
                or body.get("kind") != kind or body.get("key") != key
                or body.get("data_file") != data_path.name
                or _SHA.fullmatch(str(claimed)) is None
                or C.object_sha256(core) != claimed
                or self.product_key(kind, body.get("identity", {}),
                                    str(body.get("product_law_sha256", ""))) != key
                or data_stat.st_size != int(body.get("data_size_bytes", -1))):
            raise C.EntryV2Refusal("durable sidecar metadata identity drift")
        descriptors = body.get("arrays")
        if not isinstance(descriptors, list):
            raise C.EntryV2Refusal("durable array descriptors are invalid")
        previous_end = 0
        for descriptor in descriptors:
            if not isinstance(descriptor, dict) or set(descriptor) != {
                    "offset", "dtype", "shape", "nbytes"}:
                raise C.EntryV2Refusal("durable array descriptor schema drift")
            offset = int(descriptor["offset"])
            dtype = np.dtype(descriptor["dtype"])
            shape = tuple(int(value) for value in descriptor["shape"])
            nbytes = int(descriptor["nbytes"])
            if (dtype.hasobject or offset < previous_end or nbytes < 0
                    or offset + nbytes > data_stat.st_size
                    or int(np.prod(shape, dtype=np.int64)) * dtype.itemsize != nbytes):
                raise C.EntryV2Refusal("durable array descriptor bounds drift")
            previous_end = offset + nbytes
        return MappingProxyType(body)

    @staticmethod
    def product_key(kind: str, identity: Mapping[str, Any], law_sha256: str) -> str:
        if kind not in _KINDS or _SHA.fullmatch(str(law_sha256)) is None:
            raise C.EntryV2Refusal("invalid durable product kind/law")
        _guard_dates(identity)
        return C.object_sha256({
            "schema": DURABLE_STORE_SCHEMA,
            "store_law_sha256": DURABLE_STORE_LAW_SHA256,
            "kind": kind,
            "product_law_sha256": law_sha256,
            "identity": dict(identity),
        })

    def contains(self, kind: str, key: str) -> bool:
        if kind not in _KINDS or _SHA.fullmatch(key) is None:
            raise C.EntryV2Refusal("invalid durable product lookup")
        data = self.root / kind / f"{key}.bin"
        sidecar = self.root / kind / f"{key}.json"
        if data.exists() != sidecar.exists():
            raise C.EntryV2Refusal("durable product pair is incomplete")
        return data.exists()

    def has_product(self, kind: str, identity: Mapping[str, Any],
                    law_sha256: str) -> bool:
        """Answer from the startup index without reading product payload bytes.

        A product for the same immutable identity under a different law is an
        authority conflict, never a cold-cache miss.
        """
        key = self.product_key(kind, identity, law_sha256)
        identity_sha = C.object_sha256(dict(identity))
        laws = self._identity_laws[kind].get(identity_sha, {})
        exact = laws.get(law_sha256)
        if exact is not None:
            if exact != key:
                raise C.EntryV2Refusal("durable identity/law index differs")
            return True
        if laws:
            raise C.EntryV2Refusal("durable product law is stale")
        # A sibling process may have published the exact key after this
        # object's startup scan.  Refresh only that O(1) key's metadata; the
        # eventual load still performs the full content hash verification.
        if self.contains(kind, key):
            body = self._load_metadata(kind, key)
            if (body["identity"] != dict(identity)
                    or body["product_law_sha256"] != law_sha256):
                raise C.EntryV2Refusal("durable product source identity drift")
            self._index_metadata(kind, key, body)
            return True
        return False

    @staticmethod
    def _descriptors(arrays: Sequence[np.ndarray]) -> tuple[list[dict[str, Any]], int]:
        descriptors: list[dict[str, Any]] = []
        offset = 0
        for raw in arrays:
            value = np.asarray(raw)
            if value.dtype.hasobject or not value.flags.c_contiguous:
                raise C.EntryV2Refusal("durable product array is not plain contiguous data")
            alignment = max(64, int(value.dtype.alignment))
            offset = (offset + alignment - 1) // alignment * alignment
            descriptors.append({
                "offset": offset,
                "dtype": value.dtype.str,
                "shape": list(value.shape),
                "nbytes": int(value.nbytes),
            })
            offset += int(value.nbytes)
        # NumPy cannot mmap a zero-byte file.  A one-byte inert trailer keeps an
        # all-empty typed product reopenable without changing any descriptor.
        return descriptors, max(offset, 1)

    @staticmethod
    def _write_all(handle: Any, raw: memoryview, digest: Any) -> None:
        offset = 0
        while offset < len(raw):
            part = raw[offset:offset + 8 * 1024 * 1024]
            count = handle.write(part)
            if count != len(part):
                raise C.EntryV2Refusal("durable product write was incomplete")
            digest.update(part)
            offset += count

    @staticmethod
    def _byte_view(value: np.ndarray) -> memoryview:
        """Return a byte view that is also defined for zero-sized arrays."""
        array = np.asarray(value)
        if array.nbytes == 0:
            return memoryview(b"")
        return memoryview(array).cast("B")

    @staticmethod
    def _fsync_directory(path: Path) -> None:
        descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    @staticmethod
    @contextmanager
    def _publication_lock(path: Path):
        descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def publish(
        self, kind: str, identity: Mapping[str, Any], law_sha256: str,
        arrays: Sequence[np.ndarray], *, semantic: Mapping[str, Any],
        producer: Mapping[str, Any],
    ) -> DurableProduct:
        key = self.product_key(kind, identity, law_sha256)
        # Lane C: an all-empty product used to be published as a real one, so a
        # downstream strict reload saw published=True over zero bytes.  A
        # product with no array, or with every array empty, is refused.
        materialized = tuple(np.asarray(value) for value in arrays)
        if not materialized or all(value.size == 0 for value in materialized):
            raise C.EntryV2Refusal(
                f"durable product {kind}/{key} has no materialized array bytes")
        descriptors, total = self._descriptors(arrays)
        expected_digest = hashlib.sha256()
        cursor = 0
        for raw, descriptor in zip(arrays, descriptors):
            padding = int(descriptor["offset"]) - cursor
            if padding:
                expected_digest.update(b"\0" * padding)
                cursor += padding
            value = np.asarray(raw)
            expected_digest.update(self._byte_view(value))
            cursor += int(value.nbytes)
        if cursor < total:
            expected_digest.update(b"\0" * (total - cursor))
        lock_key = (str(self.root), kind, key)
        directory = self.root / kind
        with _LOCK_GUARD:
            lock = _KEY_LOCKS.setdefault(lock_key, threading.Lock())
        with lock, self._publication_lock(directory):
            existing = self.load(kind, identity, law_sha256)
            if existing is not None:
                if (existing.receipt["arrays"] != descriptors
                        or existing.receipt["semantic"] != dict(semantic)
                        or existing.receipt["producer"] != dict(producer)
                        or existing.receipt["data_sha256"]
                            != expected_digest.hexdigest()):
                    existing.close()
                    raise C.EntryV2Refusal(
                        "existing durable product differs from publication"
                    )
                return existing
            data_path = directory / f"{key}.bin"
            sidecar_path = directory / f"{key}.json"
            data_fd, data_tmp_name = tempfile.mkstemp(prefix=f".{key}.", dir=directory)
            data_tmp = Path(data_tmp_name)
            side_tmp: Path | None = None
            digest = hashlib.sha256()
            published_data = False
            published_sidecar = False
            try:
                with os.fdopen(data_fd, "wb", buffering=0) as handle:
                    cursor = 0
                    for raw, descriptor in zip(arrays, descriptors):
                        value = np.asarray(raw)
                        padding = int(descriptor["offset"]) - cursor
                        if padding:
                            self._write_all(handle, memoryview(b"\0" * padding), digest)
                            cursor += padding
                        self._write_all(handle, self._byte_view(value), digest)
                        cursor += int(value.nbytes)
                    if cursor < total:
                        self._write_all(
                            handle, memoryview(b"\0" * (total - cursor)), digest
                        )
                    os.fsync(handle.fileno())
                    os.fchmod(handle.fileno(), 0o444)
                body = {
                    "schema": DURABLE_PRODUCT_SCHEMA,
                    "store_schema": DURABLE_STORE_SCHEMA,
                    "store_law_sha256": DURABLE_STORE_LAW_SHA256,
                    "kind": kind,
                    "key": key,
                    "product_law_sha256": law_sha256,
                    "identity": dict(identity),
                    "data_file": data_path.name,
                    "data_size_bytes": total,
                    "data_sha256": digest.hexdigest(),
                    "arrays": descriptors,
                    "semantic": dict(semantic),
                    "producer": dict(producer),
                }
                body["receipt_sha256"] = C.object_sha256(body)
                raw_sidecar = C.canonical_bytes(body)
                side_fd, side_tmp_name = tempfile.mkstemp(prefix=f".{key}.", dir=directory)
                side_tmp = Path(side_tmp_name)
                with os.fdopen(side_fd, "wb", buffering=0) as handle:
                    if handle.write(raw_sidecar) != len(raw_sidecar):
                        raise C.EntryV2Refusal("durable sidecar write was incomplete")
                    os.fsync(handle.fileno())
                    os.fchmod(handle.fileno(), 0o444)
                os.rename(data_tmp, data_path)
                published_data = True
                os.rename(side_tmp, sidecar_path)
                published_sidecar = True
                self._fsync_directory(directory)
            except FileExistsError:
                if published_data and not published_sidecar:
                    data_path.unlink(missing_ok=True)
                winner = self._load(kind, key, identity, law_sha256)
                self._index_metadata(kind, key, winner.receipt)
                return winner
            except BaseException:
                if published_sidecar:
                    sidecar_path.unlink(missing_ok=True)
                if published_data:
                    data_path.unlink(missing_ok=True)
                raise
            finally:
                data_tmp.unlink(missing_ok=True)
                if side_tmp is not None:
                    side_tmp.unlink(missing_ok=True)
            product = self._load(kind, key, identity, law_sha256)
            product.published = True
            self._index_metadata(kind, key, product.receipt)
            return product

    def load(self, kind: str, identity: Mapping[str, Any],
             law_sha256: str) -> DurableProduct | None:
        key = self.product_key(kind, identity, law_sha256)
        exact = self._load(
            kind, key, identity, law_sha256, absent_ok=True
        )
        if exact is not None:
            self._index_metadata(kind, key, exact.receipt)
            return exact
        # An entry for the exact source identity under another semantic law is
        # stale authority, not a cache miss that may be silently rebuilt.
        identity_sha = C.object_sha256(dict(identity))
        laws = self._identity_laws[kind].get(identity_sha, {})
        if laws and law_sha256 not in laws:
            raise C.EntryV2Refusal("durable product law is stale")
        return None

    def _load(self, kind: str, key: str,
              expected_identity: Mapping[str, Any] | None,
              expected_law: str | None, *, absent_ok: bool = False) -> DurableProduct | None:
        directory = self.root / kind
        data_path = directory / f"{key}.bin"
        sidecar_path = directory / f"{key}.json"
        data_exists, side_exists = data_path.exists(), sidecar_path.exists()
        if not data_exists and not side_exists and absent_ok:
            return None
        if not data_exists or not side_exists:
            raise C.EntryV2Refusal("durable product pair is incomplete")
        data_stat = _mode_regular_0444(data_path)
        _mode_regular_0444(sidecar_path)
        raw = sidecar_path.read_bytes()
        body = _strict_json(raw)
        _guard_dates(body)
        required = {
            "schema", "store_schema", "store_law_sha256", "kind", "key",
            "product_law_sha256", "identity", "data_file", "data_size_bytes",
            "data_sha256", "arrays", "semantic", "producer", "receipt_sha256",
        }
        if set(body) != required:
            raise C.EntryV2Refusal("durable sidecar schema has missing/extra fields")
        claimed = body["receipt_sha256"]
        core = dict(body); core.pop("receipt_sha256")
        if (body["schema"] != DURABLE_PRODUCT_SCHEMA
                or body["store_schema"] != DURABLE_STORE_SCHEMA
                or body["store_law_sha256"] != DURABLE_STORE_LAW_SHA256
                or body["kind"] != kind or body["key"] != key
                or body["data_file"] != data_path.name
                or _SHA.fullmatch(str(claimed)) is None
                or C.object_sha256(core) != claimed):
            raise C.EntryV2Refusal("durable sidecar identity/hash drift")
        if self.product_key(
                kind, body["identity"], body["product_law_sha256"]) != key:
            raise C.EntryV2Refusal("durable product key binding drift")
        if expected_identity is not None and body["identity"] != dict(expected_identity):
            raise C.EntryV2Refusal("durable product source identity drift")
        if expected_law is not None and body["product_law_sha256"] != expected_law:
            raise C.EntryV2Refusal("durable product law is stale")
        size = int(body["data_size_bytes"])
        if data_stat.st_size != size or C.file_sha256(data_path) != body["data_sha256"]:
            raise C.EntryV2Refusal("durable product size/hash drift")
        descriptors = body["arrays"]
        if not isinstance(descriptors, list):
            raise C.EntryV2Refusal("durable array descriptors are invalid")
        mapping = np.memmap(data_path, mode="r", dtype=np.uint8, shape=(size,))
        arrays: list[np.ndarray] = []
        try:
            previous_end = 0
            for descriptor in descriptors:
                if not isinstance(descriptor, dict) or set(descriptor) != {
                        "offset", "dtype", "shape", "nbytes"}:
                    raise C.EntryV2Refusal("durable array descriptor schema drift")
                offset = int(descriptor["offset"])
                dtype = np.dtype(descriptor["dtype"])
                shape = tuple(int(value) for value in descriptor["shape"])
                nbytes = int(descriptor["nbytes"])
                if (dtype.hasobject or offset < previous_end or nbytes < 0
                        or offset + nbytes > size
                        or int(np.prod(shape, dtype=np.int64)) * dtype.itemsize != nbytes):
                    raise C.EntryV2Refusal("durable array descriptor bounds drift")
                value = np.ndarray(shape, dtype=dtype, buffer=mapping, offset=offset)
                value.setflags(write=False)
                arrays.append(value)
                previous_end = offset + nbytes
        except BaseException:
            mapping._mmap.close()
            raise
        return DurableProduct(
            key, data_path, sidecar_path, mapping, tuple(arrays),
            MappingProxyType(body), False,
        )

    def close(self) -> None:
        """The store has no owned mappings and publication is persistent."""


__all__ = [
    "DURABLE_PRODUCT_SCHEMA", "DURABLE_STORE_LAW_SHA256",
    "DURABLE_STORE_SCHEMA", "DurableEntryV2Store", "DurableProduct",
]
