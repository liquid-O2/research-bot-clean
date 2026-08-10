"""decision_tape_loader — the manifest-verifying mmap reader for a DecisionTape.

SPEC: FINAL_PLAN.md APPENDIX C4:

    "C4 DecisionTape (per session/side): `features/`: ... `truth/`: ...
     manifest.tsv (path,dtype,shape,rows,sha256 + sources + census + build id).
     Separation BY PROCESS (review F4): the feature BUILDER's fd census proves
     it never opens truth/; the TRAINER opens an explicit truth allowlist for
     loss computation only + static check no truth array is concatenated into
     any feature tensor."

and FINAL_PLAN.md APPENDIX C7: "manifest + mmap features".

WHAT THIS MODULE ENFORCES, in the order a reader meets it:

  1. THE MANIFEST IS THE AUTHORITY. Every leaf named in manifest.tsv must exist,
     and its own .npy header must agree with the manifest row on dtype, shape
     and row count, and its size must be exactly the size that dtype and shape
     imply. Any disagreement is a refusal — never a reshape, never a cast.
     A .npy file on disk that the manifest does not name is also a refusal: a
     tape is the set of leaves its manifest declares.
  2. features() NEVER MAPS truth/. Not by convention: the method resolves only
     rows whose section is `features`, and asserts on the resolved path before
     opening it. Every path this loader opens is recorded in `opened_paths`, so
     a caller can prove what a run touched.
  3. truth() DEMANDS AN EXPLICIT ALLOWLIST. There is no default, no "all", and
     no way to spell one: the caller passes the leaf names it is entitled to
     read, and asking for anything outside that list is a refusal.
  4. SHA VERIFICATION ON DEMAND. verify() re-hashes the whole file (header
     included, exactly as the writer hashed it) and refuses on any mismatch.
     It is not implicit, because re-hashing a 27GB session on every open would
     be a different kind of defect.

No pip dependencies beyond numpy, which the trainer already requires.
"""
from __future__ import annotations

import ast
import hashlib
import os
import pathlib
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

import numpy as np

MANIFEST_NAME = "manifest.tsv"
MANIFEST_SCHEMA = "qr_emit_manifest_v1"
FEATURES_SECTION = "features"
TRUTH_SECTION = "truth"
NPY_MAGIC = b"\x93NUMPY"
NPY_ALIGNMENT = 64

# The four APPENDIX C4 element types and nothing else.
DTYPES: Mapping[str, np.dtype] = {
    "<i8": np.dtype("<i8"),
    "<i4": np.dtype("<i4"),
    "<f4": np.dtype("<f4"),
    "|u1": np.dtype("|u1"),
}


class DecisionTapeError(Exception):
    """A tape that cannot be trusted. Never raised for a recoverable case."""


@dataclass(frozen=True)
class Leaf:
    rel_path: str
    section: str
    name: str
    dtype: str
    shape: tuple[int, ...]
    rows: int
    sha256: str


def _refuse(message: str) -> None:
    raise DecisionTapeError(message)


def _parse_manifest(text: str) -> tuple[dict[str, str], list[tuple[str, str, str]],
                                        list[tuple[str, str, str]], list[Leaf]]:
    meta: dict[str, str] = {}
    sources: list[tuple[str, str, str]] = []
    census: list[tuple[str, str, str]] = []
    leaves: list[Leaf] = []
    lines = text.split("\n")
    if not lines or not lines[0].startswith(f"# {MANIFEST_SCHEMA}\t"):
        _refuse(f"manifest does not open with the '# {MANIFEST_SCHEMA}' field line")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    for number, line in enumerate(lines[1:], start=2):
        if not line:
            _refuse(f"manifest line {number} is empty")
        fields = line.split("\t")
        kind = fields[0]
        if kind == "meta":
            if len(fields) != 3:
                _refuse(f"manifest line {number}: a meta row is kind,key,value")
            meta[fields[1]] = fields[2]
        elif kind in ("source", "census"):
            if len(fields) != 4:
                _refuse(f"manifest line {number}: a {kind} row is kind,id,sha256,path")
            row = (fields[1], fields[2], fields[3])
            (sources if kind == "source" else census).append(row)
        elif kind == "leaf":
            if len(fields) != 6:
                _refuse(f"manifest line {number}: a leaf row is kind,path,dtype,shape,rows,sha256")
            rel_path, dtype, shape_text, rows_text, sha256 = fields[1:]
            parts = rel_path.split("/")
            if len(parts) != 2 or parts[0] not in (FEATURES_SECTION, TRUTH_SECTION):
                _refuse(f"manifest line {number}: leaf path {rel_path!r} is not section/name.npy")
            if not parts[1].endswith(".npy"):
                _refuse(f"manifest line {number}: leaf path {rel_path!r} is not a .npy leaf")
            if dtype not in DTYPES:
                _refuse(f"manifest line {number}: dtype {dtype!r} is outside APPENDIX C4")
            try:
                shape = tuple(int(item) for item in shape_text.split(","))
                rows = int(rows_text)
            except ValueError:
                _refuse(f"manifest line {number}: shape/rows are not integers")
            if not 1 <= len(shape) <= 3 or any(extent < 0 for extent in shape):
                _refuse(f"manifest line {number}: shape {shape} is not 1..3 non-negative dims")
            if rows != shape[0]:
                _refuse(f"manifest line {number}: rows {rows} is not the leading dimension")
            if len(sha256) != 64 or any(character not in "0123456789abcdef" for character in sha256):
                _refuse(f"manifest line {number}: sha256 is not 64 lowercase hex digits")
            leaves.append(
                Leaf(rel_path, parts[0], parts[1][: -len(".npy")], dtype, shape, rows, sha256)
            )
        else:
            _refuse(f"manifest line {number}: unknown record kind {kind!r}")
    return meta, sources, census, leaves


def read_npy_header(path: pathlib.Path) -> tuple[np.dtype, tuple[int, ...], int]:
    """(dtype, shape, header_bytes) from a .npy v1.0 prologue, or a refusal.

    Validates the parts numpy's own reader would accept silently and that this
    substrate must not: the 64-byte alignment, the version, C order, and the
    four pinned dtypes.
    """
    with open(path, "rb") as handle:
        prologue = handle.read(10)
        if len(prologue) < 10 or prologue[:6] != NPY_MAGIC:
            _refuse(f"{path}: not a .npy file (magic)")
        if prologue[6] != 1 or prologue[7] != 0:
            _refuse(f"{path}: .npy version {prologue[6]}.{prologue[7]}, the ruling is 1.0")
        header_len = int.from_bytes(prologue[8:10], "little")
        if (10 + header_len) % NPY_ALIGNMENT != 0:
            _refuse(
                f"{path}: header of {header_len} bytes leaves the payload at offset "
                f"{10 + header_len}, which is not a multiple of {NPY_ALIGNMENT}"
            )
        header = handle.read(header_len)
    if len(header) != header_len:
        _refuse(f"{path}: header is truncated")
    if not header.endswith(b"\n"):
        _refuse(f"{path}: header is not newline-terminated")
    try:
        described = ast.literal_eval(header.decode("latin1").strip())
    except (SyntaxError, ValueError):
        _refuse(f"{path}: header dict does not parse")
    if not isinstance(described, dict) or set(described) != {"descr", "fortran_order", "shape"}:
        _refuse(f"{path}: header dict is not the three .npy keys")
    if described["fortran_order"] is not False:
        _refuse(f"{path}: fortran_order is not False; the ruling is C order")
    descr = described["descr"]
    if descr not in DTYPES:
        _refuse(f"{path}: descr {descr!r} is outside APPENDIX C4")
    shape = tuple(int(extent) for extent in described["shape"])
    return DTYPES[descr], shape, 10 + header_len


class DecisionTape:
    """One published (session, side) tape, read through its manifest."""

    def __init__(self, root: str | os.PathLike[str], *, verify_sha: bool = False) -> None:
        self.root = pathlib.Path(root)
        self.opened_paths: list[str] = []
        manifest_path = self.root / MANIFEST_NAME
        if not manifest_path.is_file():
            _refuse(f"{self.root}: no {MANIFEST_NAME}; an unmanifested directory is not a tape")
        self.opened_paths.append(str(manifest_path))
        text = manifest_path.read_text(encoding="utf-8")
        self.manifest_sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
        self.meta, self.sources, self.census, leaves = _parse_manifest(text)

        if self.meta.get("manifest_schema") != MANIFEST_SCHEMA:
            _refuse("manifest_schema is not " + MANIFEST_SCHEMA)
        for key in ("build_id", "session_ordinal", "side", "leaf_count", "total_leaf_bytes"):
            if key not in self.meta:
                _refuse(f"manifest is missing the meta key {key!r}")
        if int(self.meta["leaf_count"]) != len(leaves):
            _refuse(
                f"manifest says {self.meta['leaf_count']} leaves and carries {len(leaves)} rows"
            )
        self._leaves: dict[str, Leaf] = {}
        for leaf in leaves:
            if leaf.rel_path in self._leaves:
                _refuse(f"manifest names {leaf.rel_path} twice")
            self._leaves[leaf.rel_path] = leaf

        declared_bytes = 0
        for leaf in leaves:
            declared_bytes += self._check_leaf(leaf)
        if declared_bytes != int(self.meta["total_leaf_bytes"]):
            _refuse(
                f"leaf bytes on disk total {declared_bytes}, manifest says "
                f"{self.meta['total_leaf_bytes']}"
            )

        # A .npy on disk that the manifest does not name is an unaccounted-for
        # array, which is exactly what a half-finished or mixed build leaves.
        for section in (FEATURES_SECTION, TRUTH_SECTION):
            directory = self.root / section
            if not directory.is_dir():
                continue
            for entry in sorted(directory.iterdir()):
                relative = f"{section}/{entry.name}"
                if relative not in self._leaves:
                    _refuse(f"{relative} is on disk but not in the manifest")
        if verify_sha:
            self.verify()

    # --- structure ---------------------------------------------------------

    def _check_leaf(self, leaf: Leaf) -> int:
        path = self.root / leaf.rel_path
        if not path.is_file():
            _refuse(f"manifest names {leaf.rel_path}, which is not on disk")
        dtype, shape, header_bytes = read_npy_header(path)
        if dtype != DTYPES[leaf.dtype]:
            _refuse(f"{leaf.rel_path}: file dtype {dtype.str} != manifest {leaf.dtype}")
        if shape != leaf.shape:
            _refuse(f"{leaf.rel_path}: file shape {shape} != manifest {leaf.shape}")
        expected = header_bytes + int(np.prod(leaf.shape, dtype=np.int64)) * dtype.itemsize
        actual = path.stat().st_size
        if actual != expected:
            _refuse(f"{leaf.rel_path}: {actual} bytes on disk, {expected} implied by the manifest")
        return actual

    @property
    def build_id(self) -> str:
        return self.meta["build_id"]

    @property
    def session_ordinal(self) -> int:
        return int(self.meta["session_ordinal"])

    @property
    def side(self) -> str:
        return self.meta["side"]

    def leaf_names(self, section: str) -> list[str]:
        if section not in (FEATURES_SECTION, TRUTH_SECTION):
            _refuse(f"{section!r} is not a DecisionTape section")
        return sorted(leaf.name for leaf in self._leaves.values() if leaf.section == section)

    def leaf(self, section: str, name: str) -> Leaf:
        key = f"{section}/{name}.npy"
        if key not in self._leaves:
            _refuse(f"{key} is not in the manifest")
        return self._leaves[key]

    # --- the two doors -----------------------------------------------------

    def features(self, names: Sequence[str] | None = None) -> dict[str, np.memmap]:
        """Read-only mmaps of the features/ leaves. This never maps truth/."""
        wanted = self.leaf_names(FEATURES_SECTION) if names is None else list(names)
        out: dict[str, np.memmap] = {}
        for name in wanted:
            leaf = self.leaf(FEATURES_SECTION, name)
            if leaf.section != FEATURES_SECTION:
                _refuse(f"features() refuses to map {leaf.rel_path}")
            out[name] = self._map(leaf)
        return out

    def truth(self, allowlist: Iterable[str], names: Sequence[str] | None = None
              ) -> dict[str, np.memmap]:
        """Read-only mmaps of truth/ leaves, restricted to an explicit allowlist.

        `allowlist` is required and may not be empty: under APPENDIX C4 a
        trainer reads the truth leaves its loss needs, named one by one, and
        nothing else. There is deliberately no way to ask for "all of truth".
        """
        allowed = list(allowlist)
        if not allowed:
            _refuse("truth() requires a non-empty explicit allowlist")
        if len(set(allowed)) != len(allowed):
            _refuse("the truth allowlist repeats a name")
        known = set(self.leaf_names(TRUTH_SECTION))
        unknown = [name for name in allowed if name not in known]
        if unknown:
            _refuse(f"the truth allowlist names leaves this tape does not have: {unknown}")
        wanted = allowed if names is None else list(names)
        outside = [name for name in wanted if name not in allowed]
        if outside:
            _refuse(f"truth leaves requested outside the allowlist: {outside}")
        out: dict[str, np.memmap] = {}
        for name in wanted:
            out[name] = self._map(self.leaf(TRUTH_SECTION, name))
        return out

    def _map(self, leaf: Leaf) -> np.memmap:
        path = self.root / leaf.rel_path
        self.opened_paths.append(str(path))
        array = np.load(path, mmap_mode="r", allow_pickle=False)
        if array.dtype != DTYPES[leaf.dtype] or array.shape != leaf.shape:
            _refuse(f"{leaf.rel_path}: numpy read a different array than the manifest declares")
        return array

    # --- verification ------------------------------------------------------

    def verify(self, names: Sequence[str] | None = None) -> None:
        """Re-hashes whole leaf files against the manifest. Refuses a mismatch."""
        targets = (
            list(self._leaves.values())
            if names is None
            else [self._leaves[name] for name in names]
        )
        for leaf in targets:
            path = self.root / leaf.rel_path
            digest = hashlib.sha256()
            with open(path, "rb") as handle:
                self.opened_paths.append(str(path))
                for block in iter(lambda handle=handle: handle.read(1 << 20), b""):
                    digest.update(block)
            if digest.hexdigest() != leaf.sha256:
                _refuse(
                    f"{leaf.rel_path}: sha256 {digest.hexdigest()} != manifest {leaf.sha256}"
                )

    def truth_paths_opened(self) -> list[str]:
        return [path for path in self.opened_paths if _has_truth_component(path)]

    def assert_features_never_touched_truth(self) -> None:
        touched = self.truth_paths_opened()
        if touched:
            _refuse(f"this loader opened truth paths: {touched}")


def _has_truth_component(path: str) -> bool:
    return TRUTH_SECTION in pathlib.PurePath(path).parts


def assert_no_truth_arrays(arrays: Mapping[str, np.ndarray]) -> None:
    """Refuses if any array in `arrays` is backed by a file under truth/.

    The runtime half of C4's "no truth array is concatenated into any feature
    tensor": a memmap carries the file it came from, and so does any view of it,
    so a truth leaf that reached a feature bundle is visible here even when it
    arrived through a slice or a reshape.
    """
    for name, array in arrays.items():
        candidate: object = array
        while candidate is not None:
            filename = getattr(candidate, "filename", None)
            if filename is not None and _has_truth_component(str(filename)):
                _refuse(f"feature bundle entry {name!r} is backed by the truth leaf {filename}")
            candidate = getattr(candidate, "base", None)
