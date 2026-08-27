#!/usr/bin/env python3
"""Side-resolution mill substrate builder (EXPLORE asset-days only).

One uncompressed npz + json sidecar per EXPLORE (asset, d8).  The npz caches
the exact ``_OutcomeIndex`` interior arrays per ``truth_quality_key`` plus the
whole-pack raw clock/generation arrays the strict raw cutoff needs, so every
later hypothesis is an array op over frozen bytes.  Nothing here reads a HOLD
day, a teacher/late label, or any file outside ``.audit/mill-split.json``.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from decimal import Decimal
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import time
from typing import Mapping, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.entry_v2.confirmation_types import FEE_USD, NANOS_PER_SECOND
from engine.entry_v2.corpus_units import ASSET_MULTIPLIER
from engine.entry_v2.diagnostic_types import (
    F_BAD_TS_RECV, F_SNAPSHOT, RAW_TICK, UNITS_PER_USD,
)
from engine.entry_v2.event_pack import EVENT_DTYPE, EventPack
from engine.entry_v2.late_teacher import _decimal, _index_by_quality, _integer

SPLIT_PATH = ROOT / ".audit/mill-split.json"
CANDIDATE_ROOT = ROOT / "artifacts/cache/port/entry_v2/g1/candidates"
RECEIPT_ROOT = ROOT / "artifacts/cache/port/entry_v2/g1/receipts"
EVENT_ROOT = ROOT / "artifacts/cache/port/entry_v2/events"
MILL_ROOT = ROOT / "artifacts/cache/mill"
SUBSTRATE_SCHEMA = "QRE2MILLSUBSTRATE1"
MANIFEST_SCHEMA = "QRE2MILLMANIFEST1"
ASSETS = ("HG", "NKD", "SI")
CANDIDATE_FIELDS = (
    "candidate_id", "asset", "d8", "locked_iid", "decision_ts_ns", "side",
    "phase", "phase_open_utc", "phase_close_utc", "event_cutoff",
    "event_pack_sha256", "prefix_sha256", "lineage_sha256", "entry_bid_px",
    "entry_ask_px", "entry_mid2", "entry_spread_usd", "frozen_cost_usd",
    "sane_ceiling_usd", "compliance_status",
)
FORBIDDEN_FIELDS = frozenset((
    "status", "ready", "cash", "cert_close_usd", "exit_ts_ns", "wall_hit",
    "mfe_usd", "mae_usd", "outcome",
))


class MillStop(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class MillCandidate:
    """The CLEAR formation row, parsed exactly as the B5 scorer parses it."""

    candidate_id: str
    asset: str
    d8: int
    locked_iid: int
    decision_ts_ns: int
    side: int
    phase: str
    phase_open_ts_ns: int
    phase_close_ts_ns: int
    entry_mid2: int
    entry_bid_px: int
    entry_ask_px: int
    frozen_cost_usd: Decimal
    sane_ceiling_units: int
    multiplier: int
    event_cutoff: int
    event_pack_sha256: str
    prefix_sha256: str
    lineage_sha256: str

    def validate(self) -> None:
        if (not self.candidate_id or self.asset not in ASSET_MULTIPLIER
                or self.multiplier != ASSET_MULTIPLIER[self.asset]
                or self.side not in {-1, 1} or self.locked_iid < 0
                or not self.phase
                or not self.phase_open_ts_ns <= self.decision_ts_ns < self.phase_close_ts_ns
                or self.entry_mid2 <= 0 or self.sane_ceiling_units <= 0
                or self.entry_bid_px + self.entry_ask_px != self.entry_mid2
                or self.event_cutoff <= 0
                or any(len(value) != 64 for value in (
                    self.event_pack_sha256, self.prefix_sha256, self.lineage_sha256))):
            raise MillStop(f"candidate contract is invalid for {self.candidate_id!r}")

    @property
    def truth_quality_key(self) -> tuple[int, int, int, int]:
        return (self.phase_open_ts_ns, self.phase_close_ts_ns,
                self.sane_ceiling_units, self.multiplier)

    @property
    def cell_key(self) -> tuple[str, int]:
        return (self.phase, self.phase_open_ts_ns)


def load_split(path: Path = SPLIT_PATH) -> Mapping[str, object]:
    raw = path.read_bytes()
    value = json.loads(raw)
    if value.get("schema") != "QRE2MILLSPLIT1":
        raise MillStop("mill split schema differs")
    value = dict(value)
    value["split_file_sha256"] = hashlib.sha256(raw).hexdigest()
    return value


def explore_days(split: Mapping[str, object], assets: Sequence[str]
                 ) -> tuple[tuple[str, int], ...]:
    table = split["explore"]
    jobs: list[tuple[str, int]] = []
    for asset in assets:
        if asset not in table:
            raise MillStop(f"asset is not in the split: {asset}")
        days = tuple(int(day) for day in table[asset])
        if len(set(days)) != len(days) or len(days) != int(split["counts"][asset]["explore"]):
            raise MillStop(f"explore roster drifted for {asset}")
        jobs.extend((asset, day) for day in sorted(days))
    return tuple(jobs)


def _candidate_table(path: Path, asset: str, d8: int
                     ) -> tuple[tuple[MillCandidate, ...], str, int, int]:
    if FORBIDDEN_FIELDS.intersection(name.lower() for name in CANDIDATE_FIELDS):
        raise MillStop("formation parser exposes a late-label or outcome field")
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeDecodeError as error:
        raise MillStop(f"candidate table is not UTF-8: {path}") from error
    if len(lines) < 2 or not lines[0].startswith("# QRE2G1CAND2 "):
        raise MillStop(f"candidate schema differs: {path}")
    columns = tuple(lines[1].split("\t"))
    missing = tuple(sorted(set(CANDIDATE_FIELDS) - set(columns)))
    if missing:
        raise MillStop(f"candidate fields are absent: {missing}")
    positions = tuple(columns.index(name) for name in CANDIDATE_FIELDS)
    rows: list[MillCandidate] = []
    total = 0
    for number, line in enumerate(lines[2:], start=3):
        if not line:
            continue
        total += 1
        values = line.split("\t")
        if len(values) != len(columns):
            raise MillStop(f"candidate width differs at {asset}/{d8}:{number}")
        row = {name: values[index]
               for name, index in zip(CANDIDATE_FIELDS, positions, strict=True)}
        if row["asset"] != asset or _integer(row["d8"], "d8") != d8:
            raise MillStop(f"candidate identity differs for {asset}/{d8}")
        if row["compliance_status"] not in {"CLEAR", "PROHIBITED", "COMPLIANCE_UNKNOWN"}:
            raise MillStop(f"candidate compliance differs for {row['candidate_id']}")
        if row["compliance_status"] != "CLEAR":
            continue
        ceiling = _decimal(row["sane_ceiling_usd"], "sane_ceiling_usd") * UNITS_PER_USD
        if ceiling != ceiling.to_integral_value():
            raise MillStop(f"candidate sane ceiling is not exact: {row['candidate_id']}")
        candidate = MillCandidate(
            row["candidate_id"], asset, d8,
            _integer(row["locked_iid"], "locked_iid"),
            _integer(row["decision_ts_ns"], "decision_ts_ns"),
            _integer(row["side"], "side"), row["phase"],
            _integer(row["phase_open_utc"], "phase_open_utc") * NANOS_PER_SECOND,
            _integer(row["phase_close_utc"], "phase_close_utc") * NANOS_PER_SECOND,
            _integer(row["entry_mid2"], "entry_mid2"),
            _integer(row["entry_bid_px"], "entry_bid_px"),
            _integer(row["entry_ask_px"], "entry_ask_px"),
            _decimal(row["frozen_cost_usd"], "frozen_cost_usd"), int(ceiling),
            ASSET_MULTIPLIER[asset], _integer(row["event_cutoff"], "event_cutoff"),
            row["event_pack_sha256"], row["prefix_sha256"], row["lineage_sha256"])
        candidate.validate()
        rows.append(candidate)
    if not rows:
        raise MillStop(f"candidate table has no CLEAR row: {asset}/{d8}")
    ids = tuple(row.candidate_id for row in rows)
    if len(ids) != len(set(ids)):
        raise MillStop(f"candidate IDs repeat: {asset}/{d8}")
    return tuple(rows), sha, len(raw), total


def extract_shard(asset: str, d8: int, raw_rows: np.ndarray,
                  candidates: Sequence[MillCandidate], *, locked_iid: int,
                  open_utc: int, close_utc: int, pack_sha256: str,
                  candidates_sha256: str, candidate_rows: int,
                  ) -> tuple[dict[str, np.ndarray], dict[str, object]]:
    """The one extraction path: real packs and the selftest fixture share it."""

    indices = _index_by_quality(raw_rows, candidates)
    keys = tuple(sorted(indices))
    key_index = {key: position for position, key in enumerate(keys)}
    raw_ts = np.asarray(raw_rows["ts_recv_ns"], np.uint64).astype(np.int64)
    raw_generation: np.ndarray | None = None
    arrays: dict[str, np.ndarray] = {}
    trusted_counts: list[int] = []
    for position, key in enumerate(keys):
        index = indices[key]
        if raw_generation is None:
            raw_generation = np.asarray(index.raw_generation, np.uint32)
        elif not np.array_equal(raw_generation, index.raw_generation):
            raise MillStop(f"raw generation plane differs by quality key: {asset}/{d8}")
        rows = index.indices
        arrays[f"q{position}_ts"] = np.asarray(index.ts, np.uint64).astype(np.int64)
        arrays[f"q{position}_mid2"] = np.asarray(index.mid2, np.int64)
        arrays[f"q{position}_bid"] = np.asarray(raw_rows["bid_px"][rows], np.int64)
        arrays[f"q{position}_ask"] = np.asarray(raw_rows["ask_px"][rows], np.int64)
        arrays[f"q{position}_generation"] = np.asarray(index.generation, np.uint32)
        trusted_counts.append(int(len(rows)))
    if raw_generation is None:
        raise MillStop(f"no truth-quality plane for {asset}/{d8}")
    arrays["raw_ts"] = raw_ts
    arrays["raw_generation"] = raw_generation
    arrays["quality_keys"] = np.asarray(
        [[key[0], key[1], key[2], key[3]] for key in keys], np.int64)
    phases = tuple(sorted({row.phase for row in candidates}))
    phase_index = {phase: position for position, phase in enumerate(phases)}
    arrays["cand_decision_ts_ns"] = np.asarray(
        [row.decision_ts_ns for row in candidates], np.int64)
    arrays["cand_side"] = np.asarray([row.side for row in candidates], np.int8)
    arrays["cand_phase_idx"] = np.asarray(
        [phase_index[row.phase] for row in candidates], np.int32)
    arrays["cand_phase_open_ts_ns"] = np.asarray(
        [row.phase_open_ts_ns for row in candidates], np.int64)
    arrays["cand_phase_close_ts_ns"] = np.asarray(
        [row.phase_close_ts_ns for row in candidates], np.int64)
    arrays["cand_entry_mid2"] = np.asarray(
        [row.entry_mid2 for row in candidates], np.int64)
    arrays["cand_entry_bid_px"] = np.asarray(
        [row.entry_bid_px for row in candidates], np.int64)
    arrays["cand_entry_ask_px"] = np.asarray(
        [row.entry_ask_px for row in candidates], np.int64)
    arrays["cand_frozen_cost_usd"] = np.asarray(
        [float(row.frozen_cost_usd) for row in candidates], np.float64)
    arrays["cand_quality_idx"] = np.asarray(
        [key_index[row.truth_quality_key] for row in candidates], np.int32)
    cells = sorted({row.cell_key for row in candidates})
    sidecar = {
        "schema": SUBSTRATE_SCHEMA, "asset": asset, "d8": d8,
        "locked_iid": int(locked_iid), "open_utc": int(open_utc),
        "close_utc": int(close_utc), "multiplier": int(ASSET_MULTIPLIER[asset]),
        "event_pack_sha256": pack_sha256, "candidates_sha256": candidates_sha256,
        "phases": list(phases),
        "candidate_ids": [row.candidate_id for row in candidates],
        "quality_keys": [list(key) for key in keys],
        "quality_trusted_rows": trusted_counts,
        "counts": {
            "raw_rows": int(len(raw_rows)), "candidate_rows": int(candidate_rows),
            "clear_candidates": int(len(candidates)),
            "quality_keys": int(len(keys)), "cells": int(len(cells)),
            "phases": int(len(phases)),
        },
        "cells": [{"phase": phase, "phase_open_ts_ns": open_ns}
                  for phase, open_ns in cells],
    }
    return arrays, sidecar


def write_shard(out_root: Path, asset: str, d8: int,
                arrays: Mapping[str, np.ndarray], sidecar: Mapping[str, object],
                ) -> tuple[str, int]:
    directory = out_root / asset
    directory.mkdir(parents=True, exist_ok=True)
    npz_path = directory / f"{d8}.npz"
    with npz_path.open("wb") as handle:
        np.savez(handle, **arrays)
    payload = hashlib.sha256(npz_path.read_bytes()).hexdigest()
    (directory / f"{d8}.json").write_text(
        json.dumps({**sidecar, "npz_sha256": payload}, sort_keys=True, indent=1) + "\n")
    return payload, int(npz_path.stat().st_size)


def build_one(asset: str, d8: int, out_root: Path = MILL_ROOT) -> dict[str, object]:
    started = time.monotonic()
    candidate_path = CANDIDATE_ROOT / asset / f"{d8}.tsv"
    receipt_path = RECEIPT_ROOT / asset / f"{d8}.candidates.json"
    event_path = EVENT_ROOT / asset / f"{d8}.qre2"
    if not all(path.is_file() for path in (candidate_path, receipt_path, event_path)):
        raise MillStop(f"locked raw source is absent for {asset}/{d8}")
    receipt_raw = receipt_path.read_bytes()
    receipt = json.loads(receipt_raw)
    candidates, candidates_sha, candidate_bytes, candidate_rows = _candidate_table(
        candidate_path, asset, d8)
    if (receipt.get("schema") != "QRE2G1CANDRECEIPT2"
            or receipt.get("asset") != asset or int(receipt.get("d8", 0)) != d8
            or int(receipt.get("rows", -1)) != candidate_rows
            or receipt.get("output_sha256") != candidates_sha):
        raise MillStop(f"candidate receipt differs for {asset}/{d8}")
    source_hashes = receipt.get("source_hashes")
    if not isinstance(source_hashes, dict):
        raise MillStop(f"candidate receipt lacks sources for {asset}/{d8}")
    expected_event_sha = str(source_hashes.get("event_pack_sha256", ""))
    if len(expected_event_sha) != 64 or any(
            row.event_pack_sha256 != expected_event_sha for row in candidates):
        raise MillStop(f"candidate EventPack lineage differs for {asset}/{d8}")
    with EventPack(event_path, verify_hash=True) as pack:
        event_sha = str(pack.sidecar.get(
            "event_pack_sha256", pack.sidecar.get("output_sha256", "")))
        if (event_sha != expected_event_sha or pack.header.asset != asset
                or pack.header.d8 != d8
                or any(row.locked_iid != pack.header.locked_iid for row in candidates)):
            raise MillStop(f"EventPack lineage differs for {asset}/{d8}")
        raw_rows = np.asarray(pack.rows)
        arrays, sidecar = extract_shard(
            asset, d8, raw_rows, candidates, locked_iid=pack.header.locked_iid,
            open_utc=pack.header.open_utc, close_utc=pack.header.close_utc,
            pack_sha256=event_sha, candidates_sha256=candidates_sha,
            candidate_rows=candidate_rows)
        event_rows = int(pack.header.n_events)
        event_bytes = int(event_path.stat().st_size)
    npz_sha, npz_bytes = write_shard(out_root, asset, d8, arrays, sidecar)
    return {
        "asset": asset, "d8": d8, "npz_sha256": npz_sha, "npz_bytes": npz_bytes,
        "event_pack_sha256": event_sha, "candidates_sha256": candidates_sha,
        "receipt_sha256": hashlib.sha256(receipt_raw).hexdigest(),
        "event_rows": event_rows, "event_bytes": event_bytes,
        "candidate_bytes": candidate_bytes,
        "counts": dict(sidecar["counts"]),
        "wall_seconds": round(time.monotonic() - started, 3),
    }


def _job(payload: tuple[str, int, str]) -> dict[str, object]:
    asset, d8, out_root = payload
    return build_one(asset, d8, Path(out_root))


def build_all(assets: Sequence[str], workers: int, out_root: Path = MILL_ROOT
              ) -> dict[str, object]:
    split = load_split()
    jobs = explore_days(split, assets)
    out_root.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    shards: list[dict[str, object]] = []
    failures: list[str] = []
    payloads = [(asset, d8, str(out_root)) for asset, d8 in jobs]
    if workers <= 1:
        for payload in payloads:
            shards.append(_job(payload))
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_job, payload): payload for payload in payloads}
            done = 0
            for future in as_completed(futures):
                asset, d8, _root = futures[future]
                try:
                    shards.append(future.result())
                except Exception as error:  # noqa: BLE001 - reported, not swallowed
                    failures.append(f"{asset}/{d8}: {type(error).__name__}: {error}")
                done += 1
                if done % 25 == 0:
                    print(f"  built {done}/{len(payloads)} "
                          f"elapsed={time.monotonic() - started:.1f}s", flush=True)
    if failures:
        raise MillStop("shard build failed:\n  " + "\n  ".join(failures[:10]))
    shards.sort(key=lambda row: (ASSETS.index(str(row["asset"])), int(row["d8"])))
    wall = time.monotonic() - started
    totals = {
        "shards": len(shards),
        "npz_bytes": sum(int(row["npz_bytes"]) for row in shards),
        "event_bytes": sum(int(row["event_bytes"]) for row in shards),
        "event_rows": sum(int(row["event_rows"]) for row in shards),
        "clear_candidates": sum(int(row["counts"]["clear_candidates"]) for row in shards),
        "cells": sum(int(row["counts"]["cells"]) for row in shards),
        "quality_keys": sum(int(row["counts"]["quality_keys"]) for row in shards),
        "shards_by_asset": {asset: sum(row["asset"] == asset for row in shards)
                            for asset in assets},
        "wall_seconds": round(wall, 2),
        "shard_wall_seconds": round(
            sum(float(row["wall_seconds"]) for row in shards), 2),
    }
    manifest = {
        "schema": MANIFEST_SCHEMA, "tier": "exploratory",
        "split_sha256": str(split["split_sha256"]),
        "split_file_sha256": str(split["split_file_sha256"]),
        "split_path": str(SPLIT_PATH.relative_to(ROOT)),
        "assets": list(assets), "workers": workers,
        "built_unix": int(time.time()), "totals": totals, "shards": shards,
    }
    (out_root / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=1) + "\n")
    return manifest


# --------------------------------------------------------------------------
# Selftest: synthetic rows only.  Zero era bytes.
# --------------------------------------------------------------------------

SELFTEST_ASSET = "HG"
SELFTEST_BASE_TS = 1_600_000_000 * NANOS_PER_SECOND
SELFTEST_BASE_BID = 4_500_000_000
SELFTEST_ROWS = 600
SELFTEST_PHASES = (("0", 0, 99), ("1", 100, 299), ("2", 300, 399), ("3", 400, 599))
_HEX = "0" * 64


def _synthetic_steps(seed: int) -> np.ndarray:
    steps = np.zeros(SELFTEST_ROWS, np.int64)
    steps[10:100] = np.arange(90, dtype=np.int64) * 8 // 89          # case 1: +8 by row 99
    steps[100:300] = ((np.arange(200, dtype=np.int64) + seed) % 5) - 2
    steps[300:400] = (np.arange(100, dtype=np.int64) + seed) % 7 - 3
    steps[400:600] = ((np.arange(200, dtype=np.int64) * (seed + 1)) % 9) - 4
    steps[309] = 3
    steps[310] = -3
    return steps


def synthetic_pack(seed: int = 0) -> tuple[np.ndarray, tuple[MillCandidate, ...],
                                           dict[str, object]]:
    tick = RAW_TICK[SELFTEST_ASSET]
    multiplier = ASSET_MULTIPLIER[SELFTEST_ASSET]
    factor = 0.5e-9 * multiplier
    steps = _synthetic_steps(seed)
    rows = np.zeros(SELFTEST_ROWS, EVENT_DTYPE)
    ts = SELFTEST_BASE_TS + np.arange(SELFTEST_ROWS, dtype=np.int64) * NANOS_PER_SECOND
    rows["ts_recv_ns"] = ts.astype(np.uint64)
    rows["ts_event_ns"] = ts.astype(np.uint64)
    bid = SELFTEST_BASE_BID + steps * tick
    spread = np.full(SELFTEST_ROWS, tick, np.int64)
    spread[50] = 2 * tick                       # wide row: sane under key A only
    rows["bid_px"] = bid
    rows["ask_px"] = bid + spread
    rows["price"] = bid
    rows["receive_session_sec"] = np.arange(SELFTEST_ROWS, dtype=np.int64)
    # Case 2: exact wall.  Entry quote is row 109; the boundary row is unique.
    entry_mid2 = int(2 * SELFTEST_BASE_BID + tick) + 2 * int(steps[109]) * tick
    cost = float(spread[109]) * multiplier / 1e9 + FEE_USD
    boundary = math.floor(entry_mid2 + (-900.0 + cost) / factor)
    drop = (entry_mid2 - boundary) // 2
    rows["bid_px"][200] = SELFTEST_BASE_BID + int(steps[109]) * tick - int(drop)
    rows["ask_px"][200] = rows["bid_px"][200] + tick
    # Case 4: a clean snapshot block bumps the generation inside phase 3.
    rows["flags"][500] = F_SNAPSHOT | F_BAD_TS_RECV
    ceilings = {"A": Decimal("25"), "B": Decimal("12.5")}
    candidates: list[MillCandidate] = []

    def _make(cid: str, phase: str, lo: int, hi: int, row: int, side: int,
              ceiling: Decimal) -> MillCandidate:
        b = int(rows["bid_px"][row])
        a = int(rows["ask_px"][row])
        units = int(ceiling * UNITS_PER_USD)
        return MillCandidate(
            cid, SELFTEST_ASSET, 20220301, 1, int(ts[row]), side, phase,
            int(ts[lo]), int(ts[hi]), b + a, b, a,
            Decimal(a - b) * Decimal(multiplier) / Decimal(NANOS_PER_SECOND)
            + Decimal(str(FEE_USD)), units, multiplier, row + 1,
            _HEX, _HEX, _HEX)

    candidates.append(_make("SELF-A", "0", 0, 99, 10, 1, ceilings["A"]))
    candidates.append(_make("SELF-B", "0", 0, 99, 20, -1, ceilings["B"]))
    candidates.append(_make("SELF-C", "1", 100, 299, 110, 1, ceilings["A"]))
    candidates.append(_make("SELF-D", "1", 100, 299, 140, -1, ceilings["A"]))
    candidates.append(_make("SELF-E", "2", 300, 399, 310, 1, ceilings["A"]))
    candidates.append(_make("SELF-F", "2", 300, 399, 330, -1, ceilings["A"]))
    candidates.append(_make("SELF-G", "3", 400, 599, 410, 1, ceilings["A"]))
    candidates.append(_make("SELF-H", "3", 400, 599, 450, -1, ceilings["A"]))
    for candidate in candidates:
        candidate.validate()
    meta = {
        "boundary": boundary, "entry_mid2": entry_mid2, "cost": cost,
        "factor": factor, "wall_row": 200, "ts": ts, "tick": tick,
        "multiplier": multiplier,
    }
    return rows, tuple(candidates), meta


def write_synthetic_shards(out_root: Path, days: Sequence[int] = (20220301,)
                           ) -> tuple[tuple[str, int], ...]:
    written: list[tuple[str, int]] = []
    for seed, d8 in enumerate(days):
        rows, candidates, _meta = synthetic_pack(seed)
        candidates = tuple(
            MillCandidate(f"{row.candidate_id}-{d8}", row.asset, d8, row.locked_iid,
                          row.decision_ts_ns, row.side, row.phase,
                          row.phase_open_ts_ns, row.phase_close_ts_ns, row.entry_mid2,
                          row.entry_bid_px, row.entry_ask_px, row.frozen_cost_usd,
                          row.sane_ceiling_units, row.multiplier, row.event_cutoff,
                          row.event_pack_sha256, row.prefix_sha256, row.lineage_sha256)
            for row in candidates)
        arrays, sidecar = extract_shard(
            SELFTEST_ASSET, d8, rows, candidates, locked_iid=1,
            open_utc=SELFTEST_BASE_TS // NANOS_PER_SECOND,
            close_utc=SELFTEST_BASE_TS // NANOS_PER_SECOND + SELFTEST_ROWS,
            pack_sha256=_HEX, candidates_sha256=_HEX, candidate_rows=len(candidates))
        write_shard(out_root, SELFTEST_ASSET, d8, arrays, sidecar)
        written.append((SELFTEST_ASSET, d8))
    return tuple(written)


def load_mill():
    """Import the sibling adapter without depending on the caller's sys.path."""

    spec = importlib.util.spec_from_file_location(
        "mill", Path(__file__).resolve().parent / "mill.py")
    if spec is None or spec.loader is None:
        raise MillStop("cannot load tools/mill/mill.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("mill", module)
    spec.loader.exec_module(module)
    return module


def selftest() -> int:
    mill_module = load_mill()
    mutant = os.environ.get("QRE2_MILL_MUTANT", "")
    rows, candidates, meta = synthetic_pack(0)
    factor = float(meta["factor"])
    cost = float(meta["cost"])
    ts = meta["ts"]
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        arrays, sidecar = extract_shard(
            SELFTEST_ASSET, 20220301, rows, candidates, locked_iid=1,
            open_utc=SELFTEST_BASE_TS // NANOS_PER_SECOND,
            close_utc=SELFTEST_BASE_TS // NANOS_PER_SECOND + SELFTEST_ROWS,
            pack_sha256=_HEX, candidates_sha256=_HEX, candidate_rows=len(candidates))
        write_shard(root, SELFTEST_ASSET, 20220301, arrays, sidecar)
        shard = mill_module.load_shard(SELFTEST_ASSET, 20220301, root=root)

        def _check(name: str, body) -> None:
            try:
                body()
            except Exception as error:  # noqa: BLE001 - a red case is the signal
                failures.append(f"{name}: {type(error).__name__}: {error}")

        def phase_close_cert() -> None:
            cell = shard.cell("0", int(ts[0]))
            index = shard.index(cell.quality_idx)
            quote = index.current(int(ts[10]))
            assert quote is not None and quote[2] == int(rows["bid_px"][9]) + int(
                rows["ask_px"][9]), "entry quote is not row 9"
            got = index.outcome(int(ts[10]), 1, quote[2], cost,
                                int(cell.phase_close_ts_ns))
            expected = 1 * (int(rows["bid_px"][99]) + int(rows["ask_px"][99])
                            - quote[2]) * factor - cost
            assert got is not None, "phase-close outcome is missing"
            assert round(got.cert_close_usd, 2) == round(expected, 2), (
                f"cert {got.cert_close_usd} != hand {expected}")
            assert round(expected, 2) == 82.50, f"hand cert drifted: {expected}"
            assert not got.wall_hit, "phase-close case reported a wall"
            assert got.exit_ts_ns == int(ts[99]), "phase-close exit row differs"

        def exact_wall() -> None:
            cell = shard.cell("1", int(ts[100]))
            index = shard.index(cell.quality_idx)
            quote = index.current(int(ts[110]))
            assert quote is not None and quote[2] == int(meta["entry_mid2"]), (
                f"wall entry quote differs: {quote}")
            got = index.outcome(int(ts[110]), 1, quote[2], cost,
                                int(cell.phase_close_ts_ns))
            hand = (int(meta["boundary"]) - int(meta["entry_mid2"])) * factor - cost
            assert got is not None, "wall outcome is missing"
            assert got.wall_hit, "exact wall crossing was not found"
            assert got.exit_ts_ns == int(ts[int(meta["wall_row"])]), (
                f"wall exit row differs: {got.exit_ts_ns}")
            assert round(got.cert_close_usd, 2) == round(hand, 2), (
                f"wall cert {got.cert_close_usd} != hand {hand}")
            assert got.cert_close_usd <= -900.0 + 1e-9, (
                f"wall cert is not at the wall: {got.cert_close_usd}")

        def strictly_before() -> None:
            cell = shard.cell("2", int(ts[300]))
            index = shard.index(cell.quality_idx)
            quote = index.current(int(ts[310]))
            at_t = int(rows["bid_px"][310]) + int(rows["ask_px"][310])
            before = int(rows["bid_px"][309]) + int(rows["ask_px"][309])
            assert quote is not None, "visibility case has no quote"
            assert at_t != before, "fixture rows 309/310 must differ"
            assert quote[2] == before, (
                f"row exactly at t was visible: mid2={quote[2]} at_t={at_t}")

        def generation_truncation() -> None:
            cell = shard.cell("3", int(ts[400]))
            index = shard.index(cell.quality_idx)
            quote = index.current(int(ts[410]))
            generation = index.generation_at_snapshot(int(ts[410]))
            assert generation == 0, f"prefix generation differs: {generation}"
            assert index.generation_at_snapshot(int(ts[520])) == 1, (
                "suffix generation did not change")
            got = index.outcome(int(ts[410]), 1, quote[2], cost,
                                int(cell.phase_close_ts_ns), generation=generation)
            assert got is not None, "generation case has no outcome"
            assert got.exit_ts_ns == int(ts[499]), (
                f"generation truncation exit differs: {got.exit_ts_ns} "
                f"expected {int(ts[499])}")
            expected = (int(rows["bid_px"][499]) + int(rows["ask_px"][499])
                        - quote[2]) * factor - cost
            assert round(got.cert_close_usd, 2) == round(expected, 2), (
                f"truncated cert {got.cert_close_usd} != hand {expected}")

        def engine_equality() -> None:
            if mutant:
                return
            cell = shard.cell("1", int(ts[100]))
            index = shard.index(cell.quality_idx)
            for row, side in ((110, 1), (140, -1), (150, 1)):
                t = int(ts[row])
                got = index.outcome(t, side, index.current(t)[2], cost,
                                    int(cell.phase_close_ts_ns))
                mirror = index.outcome_mirror(t, side, index.current(t)[2], cost,
                                              int(cell.phase_close_ts_ns))
                assert (got is None) == (mirror is None), "mirror disagrees on None"
                if got is not None:
                    assert got == mirror, f"mirror differs from engine at row {row}"
                grid = index.outcomes_grid(np.asarray([t], np.int64), side,
                                           int(cell.phase_close_ts_ns))
                assert len(grid["input_index"]) == (0 if got is None else 1)
                if got is not None:
                    assert abs(float(grid["cert_close_usd"][0])
                               - got.cert_close_usd) < 1e-9, "grid differs from scalar"
                    assert int(grid["exit_ts_ns"][0]) == got.exit_ts_ns
                    assert bool(grid["wall_hit"][0]) == got.wall_hit

        _check("phase_close_cert", phase_close_cert)
        _check("exact_wall", exact_wall)
        _check("strictly_before_visibility", strictly_before)
        _check("generation_truncation", generation_truncation)
        _check("engine_equality", engine_equality)
    expected_red = {
        "visibility_at_t": "strictly_before_visibility",
        "wall_boundary_off_by_one": "exact_wall",
        "generation_carryover": "generation_truncation",
    }
    if mutant:
        died = {line.split(":", 1)[0] for line in failures}
        target = expected_red.get(mutant)
        if target is None:
            print(f"selftest_unknown_mutant {mutant}")
            return 1
        if target not in died:
            print(f"selftest_mutant_survived mutant={mutant} case={target}")
            return 1
        print(f"selftest_red mutant={mutant} died={sorted(died)}")
        for line in failures:
            print(f"  {line}")
        return 1
    if failures:
        print(f"selftest_red died={sorted(line.split(':', 1)[0] for line in failures)}")
        for line in failures:
            print(f"  {line}")
        return 1
    print("selftest_ok")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--assets", default=",".join(ASSETS))
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    assets = tuple(name.strip().upper() for name in args.assets.split(",") if name.strip())
    if any(asset not in ASSETS for asset in assets):
        raise MillStop(f"unknown asset in {args.assets!r}")
    manifest = build_all(assets, max(1, int(args.workers)))
    totals = manifest["totals"]
    print(f"shards={totals['shards']} by_asset={totals['shards_by_asset']}")
    print(f"clear_candidates={totals['clear_candidates']} cells={totals['cells']} "
          f"quality_keys={totals['quality_keys']}")
    print(f"npz_bytes={totals['npz_bytes']} event_bytes={totals['event_bytes']} "
          f"event_rows={totals['event_rows']}")
    print(f"wall_seconds={totals['wall_seconds']} "
          f"shard_wall_seconds={totals['shard_wall_seconds']}")
    print(f"manifest={MILL_ROOT / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main())
