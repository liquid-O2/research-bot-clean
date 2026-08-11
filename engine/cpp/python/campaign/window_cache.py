"""window_cache.py — the DISK-BACKED ORIENTED-WINDOW CACHE (MooseFS).

WHY.  A native arm's epoch is dominated by turning the emitted side-neutral
group table into the oriented f32 window each micro-batch reaches.  Measured on
the real corpus: 4.15 s a session cached in RAM, 18.7 min for a 271-session
epoch, 9.4 h for a 30-epoch rung -- past the 2 h budget.  Holding the oriented
windows in RAM instead would cost ~76 GB (F4) and ~111 GB (F5), and F5 breaks
the 200 GB RSS law.  So the windows live on MooseFS, which has the room.

THE KEY PROPERTY THAT MAKES ONE CACHE SERVE THE WHOLE LADDER: a window is a
function of (session, side, micro-batch window) and of the EMITTED carriers --
never of the arm, never of the weights.  So a fold's cache is baked ONCE and
every native arm of that fold reads it, across all 30 epochs.

BIT-IDENTITY IS STRUCTURAL, NOT HOPED FOR.  The baker and the live path call the
SAME two functions, `train.window_geometry` and `train.window_bytes`; this module
never re-derives either.  The stored bytes are the f32 the live path produces,
and `verify_window_cache.py` proves it end to end (logits bit-identical on both
sides of s0125, per-shard sha256, and two-run identity).

LAYOUT
    <root>/<fold>/s0125_L.bin     oriented windows, f32, concatenated
    <root>/<fold>/s0125_L.idx     the index: dtype/shape/offset per (window, modality)
    <root>/<fold>/receipt.tsv     one row per shard: path, bytes, sha256

READING.  The shard is memmapped and a background thread double-buffers: while
the GPU computes window i, window i+1's byte range is faulted in.  If MooseFS
cannot sustain the read the caller is expected to fall back to the live path --
this module never silently degrades, it reports its measured throughput.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import queue
import threading

import numpy as np

DEFAULT_ROOT = pathlib.Path("/workspace/artifacts/cache/campaign/r4/window_cache")
MODALITIES = 3


class WindowCacheError(Exception):
    """The cache does not hold what the caller was told it holds."""


def shard_paths(root: pathlib.Path, fold: str, ordinal: int, side: str):
    directory = pathlib.Path(root) / fold
    stem = f"s{ordinal:04d}_{side}"
    return directory / f"{stem}.bin", directory / f"{stem}.idx"


# --- baking -----------------------------------------------------------------


def bake_session(root: pathlib.Path, fold: str, session, config, train_module) -> dict:
    """Bakes every window of one session (both sides) into its two shards."""
    binary_path, index_path = shard_paths(root, fold, session.ordinal, "L")
    binary_path.parent.mkdir(parents=True, exist_ok=True)

    written = {}
    for side in ("L", "S"):
        binary_path, index_path = shard_paths(root, fold, session.ordinal, side)
        batch, _ = session.sides[side]
        if batch.group_neutral is None:
            raise WindowCacheError(
                f"s{session.ordinal:04d}/{side}: the session was materialised; "
                "the cache stores WINDOWS, so the loader must be windowed")
        index = {"fold": fold, "ordinal": session.ordinal, "side": side,
                 "micro_batch": config.micro_batch, "windows": []}
        digest = hashlib.sha256()
        offset = 0
        with open(binary_path, "wb") as handle:
            for lo, rows in _windows(session, side, config, train_module):
                entry = {"lo": lo, "modalities": []}
                if rows.numel() == 0:
                    index["windows"].append(entry)
                    continue
                sliced_micro = batch.micro_slot[rows]
                sliced_bin_ref = batch.bin_ref[rows]
                sliced_jsa = batch.jsa_slot[rows]
                sliced_mod = batch.jsa_mod[rows]
                import torch
                for modality in range(MODALITIES):
                    slot = sliced_micro[:, modality]
                    reference = sliced_bin_ref[:, modality]
                    jsa_here = torch.where(sliced_mod == modality, sliced_jsa,
                                           torch.full_like(sliced_jsa, -1))
                    geometry = train_module.window_geometry(
                        batch, modality, slot, reference, jsa_here)
                    if geometry is None:
                        entry["modalities"].append(None)
                        continue
                    low, high, segment_low, segment_high = geometry
                    payload = train_module.window_bytes(batch, modality, low, high)
                    if payload.dtype != np.float32 or not payload.flags["C_CONTIGUOUS"]:
                        payload = np.ascontiguousarray(payload, dtype=np.float32)
                    raw = payload.tobytes()
                    handle.write(raw)
                    digest.update(raw)
                    entry["modalities"].append(
                        {"low": low, "high": high, "segment_low": segment_low,
                         "segment_high": segment_high, "offset": offset,
                         "rows": int(payload.shape[0]), "cols": int(payload.shape[1])})
                    offset += len(raw)
                index["windows"].append(entry)
        index["bytes"] = offset
        index["sha256"] = digest.hexdigest()
        index_path.write_text(json.dumps(index), encoding="utf-8")
        written[side] = {"bytes": offset, "sha256": index["sha256"],
                         "path": str(binary_path)}
    return written


def _windows(session, side, config, train_module):
    """The exact window partition `run_session` uses -- same selection, same step."""
    import synth
    selection = train_module.build_selection(session, ranked=True)
    clock_count = int(selection.clocks.numel())
    step = max(1, config.micro_batch // len(synth.SIDES))
    for lo in range(0, clock_count, step):
        index = selection.row_of[side][slice(lo, min(lo + step, clock_count))]
        yield lo, index[index >= 0]


# --- reading ----------------------------------------------------------------


class ShardReader:
    """One (session, side) shard, memmapped, with a double-buffered prefetch."""

    def __init__(self, root: pathlib.Path, fold: str, ordinal: int, side: str,
                 prefetch: bool = True) -> None:
        self.binary_path, index_path = shard_paths(root, fold, ordinal, side)
        if not index_path.is_file():
            raise WindowCacheError(f"no cache index at {index_path}")
        self.index = json.loads(index_path.read_text(encoding="utf-8"))
        self.map = np.memmap(self.binary_path, dtype=np.uint8, mode="r")
        self.by_lo = {entry["lo"]: entry for entry in self.index["windows"]}
        self.bytes_read = 0
        self._queue: queue.Queue | None = None
        self._thread: threading.Thread | None = None
        if prefetch:
            self._queue = queue.Queue(maxsize=2)

    def verify(self) -> bool:
        """Re-hashes the shard against its index -- the sha receipt, on read."""
        digest = hashlib.sha256()
        with open(self.binary_path, "rb") as handle:
            for block in iter(lambda: handle.read(1 << 22), b""):
                digest.update(block)
        return digest.hexdigest() == self.index["sha256"]

    def prefetch(self, lo: int) -> None:
        """Fault in the next window's byte range while the GPU is busy."""
        entry = self.by_lo.get(lo)
        if entry is None or self._queue is None:
            return
        if self._thread is not None and self._thread.is_alive():
            return

        def touch() -> None:
            for record in entry["modalities"]:
                if record is None:
                    continue
                start = record["offset"]
                stop = start + record["rows"] * record["cols"] * 4
                # A single strided touch faults the range without copying it.
                _ = int(self.map[start:stop:4096].sum())

        self._thread = threading.Thread(target=touch, daemon=True)
        self._thread.start()

    def read(self, lo: int, modality: int, low: int, high: int) -> np.ndarray:
        record = self.by_lo[lo]["modalities"][modality]
        if record is None:
            raise WindowCacheError(f"window {lo}/{modality} was baked empty")
        if record["low"] != low or record["high"] != high:
            raise WindowCacheError(
                f"window {lo}/{modality}: cache holds [{record['low']},{record['high']}) "
                f"but the live geometry asked for [{low},{high}) -- the cache is stale")
        count = record["rows"] * record["cols"] * 4
        start = record["offset"]
        self.bytes_read += count
        raw = np.asarray(self.map[start:start + count])
        return raw.view(np.float32).reshape(record["rows"], record["cols"])


class WindowCache:
    """The per-fold cache: a reader per (session, side), opened on demand."""

    def __init__(self, root: pathlib.Path, fold: str, prefetch: bool = True) -> None:
        self.root = pathlib.Path(root)
        self.fold = fold
        self.prefetch_enabled = prefetch
        self.readers: dict = {}
        self.key = None
        self.bytes_read = 0

    def available(self, ordinal: int, side: str) -> bool:
        return shard_paths(self.root, self.fold, ordinal, side)[1].is_file()

    def reader(self, ordinal: int, side: str) -> ShardReader:
        handle = self.readers.get((ordinal, side))
        if handle is None:
            handle = ShardReader(self.root, self.fold, ordinal, side,
                                 prefetch=self.prefetch_enabled)
            self.readers[(ordinal, side)] = handle
        return handle

    def read(self, key, modality: int, low: int, high: int) -> np.ndarray:
        ordinal, side, lo = key
        handle = self.reader(ordinal, side)
        payload = handle.read(lo, modality, low, high)
        self.bytes_read += payload.nbytes
        return payload

    def prefetch(self, key) -> None:
        ordinal, side, lo = key
        if self.available(ordinal, side):
            self.reader(ordinal, side).prefetch(lo)

    def release(self, ordinal: int | None = None) -> None:
        for (held, _side) in list(self.readers):
            if ordinal is None or held == ordinal:
                self.readers.pop((held, _side), None)
