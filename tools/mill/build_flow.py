#!/usr/bin/env python3
"""Minute-scale order-flow feature cache for the side-resolution mill.

One uncompressed npz + json sidecar per EXPLORE (asset, d8).  Each cell of the
day -- a ``(phase, phase_open_ts_ns)`` formation window -- becomes a strip of
60-second bars aligned to the phase open, carrying the twelve level-anchored
flow signatures the discretionary integration asked for: signed aggressor
delta, traded volume/count/largest print, book-update rate, attack volume into
the running extreme, adverse yield per attack (absorption), best-size reload at
the extreme, and two-sided volume.

Nothing here reads a HOLD day, a teacher/late label, or any file outside
``.audit/mill-split.json``.

Row decoding (censused on HG/20220315, 300,190 rows, before any arithmetic):
``action`` is ASCII ``A`` add / ``C`` cancel / ``M`` modify / ``T`` trade;
``side`` is ``B`` bid / ``A`` ask / ``N`` none.  On a trade ``side`` names the
aggressor: of 12,370 ``B`` trades 98.04% printed at or above the ask and none
at or below the bid, and of 12,721 ``A`` trades 94.40% printed at or below the
bid and none at or above the ask.  ``B`` is therefore the buy aggressor
lifting the offer and ``A`` the sell aggressor hitting the bid, which is what
``confirmation_plane``, ``confirmation_types``, ``discretionary_tape`` and
``discretionary_profile_ledger`` already assume.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from typing import Mapping, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.entry_v2.confirmation_types import NANOS_PER_SECOND
from engine.entry_v2.diagnostic_event_truth import native_book_quality
from engine.entry_v2.diagnostic_types import RAW_TICK
from engine.entry_v2.event_pack import EVENT_DTYPE, EventPack

SPLIT_PATH = ROOT / ".audit/mill-split.json"
CANDIDATE_ROOT = ROOT / "artifacts/cache/port/entry_v2/g1/candidates"
RECEIPT_ROOT = ROOT / "artifacts/cache/port/entry_v2/g1/receipts"
EVENT_ROOT = ROOT / "artifacts/cache/port/entry_v2/events"
FLOW_ROOT = ROOT / "artifacts/cache/mill_flow"
FLOW_SCHEMA = "QRE2MILLFLOW1"
MANIFEST_SCHEMA = "QRE2MILLFLOWMANIFEST1"
ASSETS = ("HG", "NKD", "SI")
BAR_NS = 60 * NANOS_PER_SECOND
# The attack/reload window of the discretionary grammar is three ticks around
# the level.  Every price here lives in doubled units (``mid2 = bid + ask``),
# so the three-tick radius doubles with it.
ATTACK_TICKS = 3
CELL_FIELDS = (
    "candidate_id", "asset", "d8", "phase", "phase_open_utc", "phase_close_utc",
    "event_pack_sha256", "compliance_status",
)
FORBIDDEN_FIELDS = frozenset((
    "status", "ready", "cash", "cert_close_usd", "exit_ts_ns", "wall_hit",
    "mfe_usd", "mae_usd", "outcome",
))
FLOW_ARRAYS = (
    "bar_open_ts_ns", "bar_close_ts_ns", "delta", "vol", "ntrades", "maxtrade",
    "quote_events", "attack_low", "attack_high", "yield_low", "yield_high",
    "reload_low", "reload_high", "twoside", "bar_low_mid2", "bar_high_mid2",
    "run_low_mid2", "run_high_mid2", "run_low_valid", "run_high_valid",
)


class FlowStop(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class FlowCellKey:
    """One formation window: the mill's unit of many-read substrate."""

    phase: str
    open_ts_ns: int
    close_ts_ns: int

    def validate(self) -> None:
        if not self.phase or self.open_ts_ns <= 0 or self.close_ts_ns <= self.open_ts_ns:
            raise FlowStop(f"cell window is invalid: {self}")


def _integer(text: str, name: str) -> int:
    stripped = text.strip()
    body = stripped[1:] if stripped[:1] == "-" else stripped
    if not body.isdigit():
        raise FlowStop(f"{name} is not an exact integer: {text!r}")
    return int(stripped)


def load_split(path: Path = SPLIT_PATH) -> Mapping[str, object]:
    raw = path.read_bytes()
    value = json.loads(raw)
    if value.get("schema") != "QRE2MILLSPLIT1":
        raise FlowStop("mill split schema differs")
    value = dict(value)
    value["split_file_sha256"] = hashlib.sha256(raw).hexdigest()
    return value


def explore_days(split: Mapping[str, object], assets: Sequence[str]
                 ) -> tuple[tuple[str, int], ...]:
    table = split["explore"]
    jobs: list[tuple[str, int]] = []
    for asset in assets:
        if asset not in table:
            raise FlowStop(f"asset is not in the split: {asset}")
        days = tuple(int(day) for day in table[asset])
        if len(set(days)) != len(days) or len(days) != int(split["counts"][asset]["explore"]):
            raise FlowStop(f"explore roster drifted for {asset}")
        jobs.extend((asset, day) for day in sorted(days))
    return tuple(jobs)


def _cell_table(path: Path, asset: str, d8: int
                ) -> tuple[tuple[FlowCellKey, ...], str, int, str]:
    """Parse the CLEAR formation rows down to their distinct cell windows."""

    if FORBIDDEN_FIELDS.intersection(name.lower() for name in CELL_FIELDS):
        raise FlowStop("formation parser exposes a late-label or outcome field")
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    lines = raw.decode("utf-8").splitlines()
    if len(lines) < 2 or not lines[0].startswith("# QRE2G1CAND2 "):
        raise FlowStop(f"candidate schema differs: {path}")
    columns = tuple(lines[1].split("\t"))
    missing = tuple(sorted(set(CELL_FIELDS) - set(columns)))
    if missing:
        raise FlowStop(f"candidate fields are absent: {missing}")
    positions = tuple(columns.index(name) for name in CELL_FIELDS)
    windows: dict[tuple[str, int], int] = {}
    lineage: set[str] = set()
    total = 0
    for number, line in enumerate(lines[2:], start=3):
        if not line:
            continue
        total += 1
        values = line.split("\t")
        if len(values) != len(columns):
            raise FlowStop(f"candidate width differs at {asset}/{d8}:{number}")
        row = {name: values[index]
               for name, index in zip(CELL_FIELDS, positions, strict=True)}
        if row["asset"] != asset or _integer(row["d8"], "d8") != d8:
            raise FlowStop(f"candidate identity differs for {asset}/{d8}")
        if row["compliance_status"] not in {"CLEAR", "PROHIBITED", "COMPLIANCE_UNKNOWN"}:
            raise FlowStop(f"candidate compliance differs for {row['candidate_id']}")
        if row["compliance_status"] != "CLEAR":
            continue
        open_ns = _integer(row["phase_open_utc"], "phase_open_utc") * NANOS_PER_SECOND
        close_ns = _integer(row["phase_close_utc"], "phase_close_utc") * NANOS_PER_SECOND
        key = (row["phase"], open_ns)
        if windows.setdefault(key, close_ns) != close_ns:
            raise FlowStop(f"phase close differs inside cell {key} for {asset}/{d8}")
        lineage.add(row["event_pack_sha256"])
    if not windows:
        raise FlowStop(f"candidate table has no CLEAR row: {asset}/{d8}")
    if len(lineage) != 1 or len(next(iter(lineage))) != 64:
        raise FlowStop(f"candidate EventPack lineage is not single-valued: {asset}/{d8}")
    cells = tuple(FlowCellKey(phase, open_ns, windows[(phase, open_ns)])
                  for phase, open_ns in sorted(windows))
    for cell in cells:
        cell.validate()
    return cells, sha, total, next(iter(lineage))


def _segment_reduce(ufunc: np.ufunc, values: np.ndarray, edges: np.ndarray,
                    empty: int) -> np.ndarray:
    """Reduce ``values`` over the half-open row spans named by ``edges``.

    ``reduceat`` reads a start list, not spans, so an empty bar would silently
    re-read the row at its start.  Feeding it only the non-empty starts makes
    the next start the true stop of the span before it, because every bar
    between them is empty.
    """

    bars = len(edges) - 1
    out = np.full(bars, empty, np.int64)
    live = np.diff(edges) > 0
    if bool(live.any()):
        out[live] = ufunc.reduceat(values, edges[:-1][live]).astype(np.int64, copy=False)
    return out


def _sub_edges(selected: np.ndarray, edges: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Re-express bar edges in the coordinates of a compacted row subset."""

    index = np.flatnonzero(selected)
    return index, np.searchsorted(index, edges, side="left")


def bar_boundaries(open_ts_ns: int, close_ts_ns: int) -> np.ndarray:
    """Bar edges in nanoseconds, aligned to the phase open, last bar clipped."""

    span = close_ts_ns - open_ts_ns
    bars = int(-(-span // BAR_NS))
    edges = open_ts_ns + np.arange(bars + 1, dtype=np.int64) * BAR_NS
    edges[-1] = close_ts_ns
    return edges


def extract_cell(rows: np.ndarray, ts: np.ndarray, trusted_message: np.ndarray,
                 trusted_economic: np.ndarray, cell: FlowCellKey, *, tick: int,
                 mutant: str = "") -> dict[str, np.ndarray]:
    """The one flow extraction path: real packs and the selftest share it."""

    boundaries = bar_boundaries(cell.open_ts_ns, cell.close_ts_ns)
    bars = len(boundaries) - 1
    # A bar closing at t sees rows with ts_recv_ns < t, so every edge is a
    # left insertion point.  The mutant admits the row landing exactly on the
    # close, which is the future-data reading the clock law forbids.
    seek = "right" if mutant == "flow_uses_row_at_close" else "left"
    edges = np.searchsorted(ts, boundaries, side=seek).astype(np.int64, copy=False)
    lo, hi = int(edges[0]), int(edges[-1])
    local = edges - edges[0]
    view = rows[lo:hi]
    message = trusted_message[lo:hi]
    economic = trusted_economic[lo:hi]
    action = view["action"]
    side = view["side"]
    size = view["size"].astype(np.int64)  # cast before every signed operation
    price = view["price"].astype(np.int64)
    bid_px = view["bid_px"].astype(np.int64)
    ask_px = view["ask_px"].astype(np.int64)

    trade = (action == ord("T")) & message & (price > 0) & (price % tick == 0) & (size > 0)
    quote = np.isin(action, (ord("A"), ord("C"), ord("M"))) & message
    trade_index, trade_edges = _sub_edges(trade, local)
    quote_index, quote_edges = _sub_edges(quote, local)
    econ_index, econ_edges = _sub_edges(economic, local)

    trade_size = size[trade_index]
    trade_side = side[trade_index]
    trade_price2 = 2 * price[trade_index]  # doubled, to meet mid2 coordinates
    buy = trade_side == ord("B")
    sell = trade_side == ord("A")
    buy_volume = _segment_reduce(np.add, np.where(buy, trade_size, 0), trade_edges, 0)
    sell_volume = _segment_reduce(np.add, np.where(sell, trade_size, 0), trade_edges, 0)
    vol = _segment_reduce(np.add, trade_size, trade_edges, 0)
    ntrades = np.diff(trade_edges).astype(np.int64)
    maxtrade = _segment_reduce(np.maximum, trade_size, trade_edges, 0)
    quote_events = np.diff(quote_edges).astype(np.int64)

    mid2 = (bid_px + ask_px)[econ_index]
    has_book = np.diff(econ_edges) > 0
    big = np.iinfo(np.int64).max
    bar_low = _segment_reduce(np.minimum, mid2, econ_edges, big)
    bar_high = _segment_reduce(np.maximum, mid2, econ_edges, -big)
    # The running extreme is the session extreme established by the bars that
    # closed before this one; a bar cannot set the level it is tested against.
    run_low = np.empty(bars, np.int64)
    run_high = np.empty(bars, np.int64)
    run_low[0], run_high[0] = big, -big
    if bars > 1:
        run_low[1:] = np.minimum.accumulate(bar_low)[:-1]
        run_high[1:] = np.maximum.accumulate(bar_high)[:-1]
    run_low_valid = run_low != big
    run_high_valid = run_high != -big
    safe_low = np.where(run_low_valid, run_low, 0)
    safe_high = np.where(run_high_valid, run_high, 0)

    window = 2 * ATTACK_TICKS * tick
    trade_bar = np.repeat(np.arange(bars, dtype=np.int64), np.diff(trade_edges))
    near_low = run_low_valid[trade_bar] & (
        np.abs(trade_price2 - safe_low[trade_bar]) <= window)
    near_high = run_high_valid[trade_bar] & (
        np.abs(trade_price2 - safe_high[trade_bar]) <= window)
    attack_low = _segment_reduce(np.add, np.where(near_low, trade_size, 0), trade_edges, 0)
    attack_high = _segment_reduce(np.add, np.where(near_high, trade_size, 0), trade_edges, 0)

    # Effort versus result: ticks of fresh adverse progress bought per unit of
    # attack.  Absorption is a large attack that buys almost no new extreme.
    beyond_low = np.where(run_low_valid & has_book, np.maximum(0, safe_low - bar_low), 0)
    beyond_high = np.where(run_high_valid & has_book, np.maximum(0, bar_high - safe_high), 0)
    yield_low = (beyond_low / (2.0 * tick)) / (attack_low + 1.0)
    yield_high = (beyond_high / (2.0 * tick)) / (attack_high + 1.0)

    econ_bar = np.repeat(np.arange(bars, dtype=np.int64), np.diff(econ_edges))
    reload_low = _reload(bid_px[econ_index], view["bid_sz"][econ_index].astype(np.int64),
                         mid2, econ_bar, econ_edges, safe_low, run_low_valid, window)
    reload_high = _reload(ask_px[econ_index], view["ask_sz"][econ_index].astype(np.int64),
                          mid2, econ_bar, econ_edges, safe_high, run_high_valid, window)

    return {
        "bar_open_ts_ns": boundaries[:-1].copy(),
        "bar_close_ts_ns": boundaries[1:].copy(),
        "delta": buy_volume - sell_volume,
        "vol": vol, "ntrades": ntrades, "maxtrade": maxtrade,
        "quote_events": quote_events,
        "attack_low": attack_low, "attack_high": attack_high,
        "yield_low": yield_low, "yield_high": yield_high,
        "reload_low": reload_low, "reload_high": reload_high,
        "twoside": np.minimum(buy_volume, sell_volume),
        "bar_low_mid2": np.where(has_book, bar_low, 0),
        "bar_high_mid2": np.where(has_book, bar_high, 0),
        "run_low_mid2": np.where(run_low_valid, run_low, 0),
        "run_high_mid2": np.where(run_high_valid, run_high, 0),
        "run_low_valid": run_low_valid, "run_high_valid": run_high_valid,
    }


def _reload(best_px: np.ndarray, best_sz: np.ndarray, mid2: np.ndarray,
            econ_bar: np.ndarray, econ_edges: np.ndarray, safe: np.ndarray,
            valid: np.ndarray, window: int) -> np.ndarray:
    """Sum positive best-size increases at an unchanged best price.

    MBP-1 carries no order identity, so replenishment is read as the queue
    growing back at the same price between consecutive book rows of one bar,
    counted only while the market sits inside the attack window of the level.
    """

    increase = np.zeros(len(mid2), np.int64)
    if len(mid2) > 1:
        step = best_sz[1:] - best_sz[:-1]
        bar = econ_bar[1:]
        same = (econ_bar[1:] == econ_bar[:-1]) & (best_px[1:] == best_px[:-1])
        near = valid[bar] & (np.abs(mid2[1:] - safe[bar]) <= window)
        increase[1:] = np.where(same & near & (step > 0), step, 0)
    return _segment_reduce(np.add, increase, econ_edges, 0)


def extract_shard(asset: str, d8: int, rows: np.ndarray,
                  cells: Sequence[FlowCellKey], *, locked_iid: int, open_utc: int,
                  close_utc: int, pack_sha256: str, candidates_sha256: str,
                  candidate_rows: int, mutant: str = "",
                  ) -> tuple[dict[str, np.ndarray], dict[str, object]]:
    tick = int(RAW_TICK[asset])
    ts = rows["ts_recv_ns"].astype(np.int64)
    sane = ((rows["bid_px"] > 0) & (rows["ask_px"] > rows["bid_px"])
            & ((rows["ask_px"].astype(np.int64)
                - rows["bid_px"].astype(np.int64)) % tick == 0))
    quality = native_book_quality(rows["ts_recv_ns"], rows["flags"], sane)
    message = np.asarray(quality.trusted_message, bool)
    economic = np.asarray(quality.trusted_economic, bool)
    arrays: dict[str, np.ndarray] = {}
    bar_counts: list[int] = []
    for position, cell in enumerate(cells):
        values = extract_cell(rows, ts, message, economic, cell,
                              tick=tick, mutant=mutant)
        if tuple(sorted(values)) != tuple(sorted(FLOW_ARRAYS)):
            raise FlowStop(f"flow array roster drifted for {asset}/{d8}")
        for name, array in values.items():
            arrays[f"c{position}_{name}"] = array
        bar_counts.append(int(len(values["vol"])))
    arrays["cell_open_ts_ns"] = np.asarray([cell.open_ts_ns for cell in cells], np.int64)
    arrays["cell_close_ts_ns"] = np.asarray([cell.close_ts_ns for cell in cells], np.int64)
    arrays["cell_bars"] = np.asarray(bar_counts, np.int64)
    sidecar = {
        "schema": FLOW_SCHEMA, "asset": asset, "d8": d8,
        "locked_iid": int(locked_iid), "open_utc": int(open_utc),
        "close_utc": int(close_utc), "raw_tick": tick, "bar_ns": BAR_NS,
        "attack_ticks": ATTACK_TICKS,
        "event_pack_sha256": pack_sha256, "candidates_sha256": candidates_sha256,
        "phases": [cell.phase for cell in cells],
        "counts": {
            "raw_rows": int(len(rows)), "candidate_rows": int(candidate_rows),
            "cells": len(cells), "bars": int(sum(bar_counts)),
            "trusted_message_rows": int(message.sum()),
            "trusted_economic_rows": int(economic.sum()),
        },
        "cells": [{"phase": cell.phase, "phase_open_ts_ns": cell.open_ts_ns,
                   "phase_close_ts_ns": cell.close_ts_ns, "bars": count}
                  for cell, count in zip(cells, bar_counts, strict=True)],
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


def _sources(asset: str, d8: int) -> tuple[Path, Path, Path]:
    return (CANDIDATE_ROOT / asset / f"{d8}.tsv",
            RECEIPT_ROOT / asset / f"{d8}.candidates.json",
            EVENT_ROOT / asset / f"{d8}.qre2")


def _authorized_pack(asset: str, d8: int) -> tuple[EventPack, tuple[FlowCellKey, ...],
                                                   str, str, int, bytes]:
    candidate_path, receipt_path, event_path = _sources(asset, d8)
    if not all(path.is_file() for path in (candidate_path, receipt_path, event_path)):
        raise FlowStop(f"locked raw source is absent for {asset}/{d8}")
    receipt_raw = receipt_path.read_bytes()
    receipt = json.loads(receipt_raw)
    cells, candidates_sha, candidate_rows, lineage = _cell_table(candidate_path, asset, d8)
    if (receipt.get("schema") != "QRE2G1CANDRECEIPT2"
            or receipt.get("asset") != asset or int(receipt.get("d8", 0)) != d8
            or int(receipt.get("rows", -1)) != candidate_rows
            or receipt.get("output_sha256") != candidates_sha):
        raise FlowStop(f"candidate receipt differs for {asset}/{d8}")
    source_hashes = receipt.get("source_hashes")
    if not isinstance(source_hashes, dict):
        raise FlowStop(f"candidate receipt lacks sources for {asset}/{d8}")
    expected_event_sha = str(source_hashes.get("event_pack_sha256", ""))
    if len(expected_event_sha) != 64 or lineage != expected_event_sha:
        raise FlowStop(f"candidate EventPack lineage differs for {asset}/{d8}")
    pack = EventPack(event_path, verify_hash=True)
    event_sha = str(pack.sidecar.get(
        "event_pack_sha256", pack.sidecar.get("output_sha256", "")))
    if (event_sha != expected_event_sha or pack.header.asset != asset
            or pack.header.d8 != d8):
        pack.close()
        raise FlowStop(f"EventPack lineage differs for {asset}/{d8}")
    return pack, cells, event_sha, candidates_sha, candidate_rows, receipt_raw


def build_one(asset: str, d8: int, out_root: Path = FLOW_ROOT) -> dict[str, object]:
    started = time.monotonic()
    pack, cells, event_sha, candidates_sha, candidate_rows, receipt_raw = _authorized_pack(
        asset, d8)
    with pack:
        arrays, sidecar = extract_shard(
            asset, d8, np.asarray(pack.rows), cells,
            locked_iid=pack.header.locked_iid, open_utc=pack.header.open_utc,
            close_utc=pack.header.close_utc, pack_sha256=event_sha,
            candidates_sha256=candidates_sha, candidate_rows=candidate_rows)
        event_rows = int(pack.header.n_events)
        event_bytes = int(_sources(asset, d8)[2].stat().st_size)
    npz_sha, npz_bytes = write_shard(out_root, asset, d8, arrays, sidecar)
    return {
        "asset": asset, "d8": d8, "npz_sha256": npz_sha, "npz_bytes": npz_bytes,
        "event_pack_sha256": event_sha, "candidates_sha256": candidates_sha,
        "receipt_sha256": hashlib.sha256(receipt_raw).hexdigest(),
        "event_rows": event_rows, "event_bytes": event_bytes,
        "counts": dict(sidecar["counts"]),
        "wall_seconds": round(time.monotonic() - started, 3),
    }


def _job(payload: tuple[str, int, str]) -> dict[str, object]:
    asset, d8, out_root = payload
    return build_one(asset, d8, Path(out_root))


def build_all(assets: Sequence[str], workers: int, out_root: Path = FLOW_ROOT
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
        raise FlowStop("flow shard build failed:\n  " + "\n  ".join(failures[:10]))
    shards.sort(key=lambda row: (ASSETS.index(str(row["asset"])), int(row["d8"])))
    wall = time.monotonic() - started
    totals = {
        "shards": len(shards),
        "npz_bytes": sum(int(row["npz_bytes"]) for row in shards),
        "event_bytes": sum(int(row["event_bytes"]) for row in shards),
        "event_rows": sum(int(row["event_rows"]) for row in shards),
        "cells": sum(int(row["counts"]["cells"]) for row in shards),
        "bars": sum(int(row["counts"]["bars"]) for row in shards),
        "shards_by_asset": {asset: sum(row["asset"] == asset for row in shards)
                            for asset in assets},
        "wall_seconds": round(wall, 2),
        "shard_wall_seconds": round(sum(float(row["wall_seconds"]) for row in shards), 2),
    }
    manifest = {
        "schema": MANIFEST_SCHEMA, "tier": "exploratory",
        "split_sha256": str(split["split_sha256"]),
        "split_file_sha256": str(split["split_file_sha256"]),
        "split_path": str(SPLIT_PATH.relative_to(ROOT)),
        "assets": list(assets), "workers": workers, "bar_ns": BAR_NS,
        "attack_ticks": ATTACK_TICKS,
        "built_unix": int(time.time()), "totals": totals, "shards": shards,
    }
    (out_root / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=1) + "\n")
    return manifest


# --------------------------------------------------------------------------
# Conservation: one shard, two independent code paths over the same rows.
# --------------------------------------------------------------------------

def conservation(asset: str, d8: int) -> int:
    """Re-total one shard's traded size without touching the array machinery."""

    pack, cells, event_sha, candidates_sha, candidate_rows, _receipt = _authorized_pack(
        asset, d8)
    tick = int(RAW_TICK[asset])
    with pack:
        rows = np.asarray(pack.rows)
        arrays, sidecar = extract_shard(
            asset, d8, rows, cells, locked_iid=pack.header.locked_iid,
            open_utc=pack.header.open_utc, close_utc=pack.header.close_utc,
            pack_sha256=event_sha, candidates_sha256=candidates_sha,
            candidate_rows=candidate_rows)
        sane = ((rows["bid_px"] > 0) & (rows["ask_px"] > rows["bid_px"])
                & ((rows["ask_px"].astype(np.int64)
                    - rows["bid_px"].astype(np.int64)) % tick == 0))
        message = np.asarray(native_book_quality(
            rows["ts_recv_ns"], rows["flags"], sane).trusted_message, bool)
        failures = 0
        for position, cell in enumerate(cells):
            # Different path: EventPack's own cutoff law, then a plain Python
            # loop over the row tuples.  No searchsorted edges, no reduceat.
            lo, hi = pack.cutoffs(np.asarray(
                [cell.open_ts_ns, cell.close_ts_ns], np.int64))
            hand_volume = 0
            hand_trades = 0
            hand_delta = 0
            hand_max = 0
            for index in range(int(lo), int(hi)):
                row = rows[index]
                size = int(row["size"])
                price = int(row["price"])
                if (int(row["action"]) != ord("T") or not bool(message[index])
                        or price <= 0 or price % tick != 0 or size <= 0):
                    continue
                hand_volume += size
                hand_trades += 1
                hand_max = max(hand_max, size)
                if int(row["side"]) == ord("B"):
                    hand_delta += size
                elif int(row["side"]) == ord("A"):
                    hand_delta -= size
            got = {name: int(arrays[f"c{position}_{name}"].sum())
                   for name in ("vol", "ntrades", "delta")}
            got_max = int(arrays[f"c{position}_maxtrade"].max())
            agree = (got["vol"] == hand_volume and got["ntrades"] == hand_trades
                     and got["delta"] == hand_delta and got_max == hand_max)
            failures += 0 if agree else 1
            print(f"  cell {position} phase={cell.phase} bars={len(arrays[f'c{position}_vol'])} "
                  f"vol={got['vol']}/{hand_volume} ntrades={got['ntrades']}/{hand_trades} "
                  f"delta={got['delta']}/{hand_delta} maxtrade={got_max}/{hand_max} "
                  f"{'ok' if agree else 'MISMATCH'}")
    print(f"conservation asset={asset} d8={d8} cells={len(cells)} "
          f"rows={sidecar['counts']['raw_rows']} mismatches={failures}")
    return 0 if failures == 0 else 1


# --------------------------------------------------------------------------
# Selftest: synthetic rows only.  Zero era bytes.
# --------------------------------------------------------------------------

SELFTEST_ASSET = "HG"
SELFTEST_BASE_TS = 1_600_000_000 * NANOS_PER_SECOND
SELFTEST_BASE_BID = 4_500_000_000
SELFTEST_BARS = 4
SELFTEST_TICK = int(RAW_TICK[SELFTEST_ASSET])


def _row(ts_ns: int, action: str, side: str, price: int, size: int,
         bid: int, bid_sz: int, ask_sz: int) -> tuple:
    return (np.uint64(ts_ns), np.uint64(ts_ns), price, bid, bid + SELFTEST_TICK,
            size, bid_sz, ask_sz, 1, 1, 0, 0, int((ts_ns - SELFTEST_BASE_TS) // NANOS_PER_SECOND),
            ord(action), ord(side), 0, 0)


def synthetic_rows() -> tuple[np.ndarray, FlowCellKey]:
    """Four 60s bars over one cell, laid out so every case is hand-countable."""

    tick = SELFTEST_TICK
    base = SELFTEST_BASE_BID
    low_bid = base - 4 * tick
    plan: list[tuple] = []

    def at(second: int, action: str, side: str, price: int, size: int,
           bid: int, bid_sz: int = 10, ask_sz: int = 10) -> None:
        plan.append(_row(SELFTEST_BASE_TS + second * NANOS_PER_SECOND, action, side,
                         price, size, bid, bid_sz, ask_sz))

    # Bar 0: the book sits at base; three trades set delta/vol/max/twoside.
    at(0, "A", "B", base, 1, base)
    at(10, "T", "B", base + tick, 5, base)
    at(20, "T", "A", base, 3, base)
    at(30, "T", "B", base + tick, 7, base)
    at(40, "C", "A", base, 1, base)
    # Bar 1: the book steps four ticks down and sets the running low.
    at(60, "A", "B", low_bid, 1, low_bid)
    at(90, "M", "B", low_bid, 1, low_bid)
    # Bar 2: attack at the low, one print outside the three-tick window, a
    # fresh one-tick low, and two same-price bid replenishments.
    at(120, "T", "A", low_bid, 100, low_bid, bid_sz=10)
    at(121, "A", "B", low_bid, 1, low_bid, bid_sz=4)
    at(122, "A", "B", low_bid, 1, low_bid, bid_sz=12)
    at(123, "A", "B", low_bid, 1, low_bid, bid_sz=20)
    at(130, "T", "B", low_bid + 5 * tick, 40, low_bid)
    at(150, "T", "A", low_bid - tick, 6, low_bid - tick)
    # The boundary row: exactly at bar 2's close, so it belongs to bar 3.
    at(180, "T", "B", low_bid + tick, 999, low_bid)
    at(200, "T", "A", low_bid, 2, low_bid)
    rows = np.array(plan, dtype=EVENT_DTYPE)
    cell = FlowCellKey("0", int(SELFTEST_BASE_TS),
                       int(SELFTEST_BASE_TS + SELFTEST_BARS * 60 * NANOS_PER_SECOND))
    cell.validate()
    return rows, cell


def selftest() -> int:
    mutant = os.environ.get("QRE2_MILL_FLOW_MUTANT", "")
    rows, cell = synthetic_rows()
    ts = rows["ts_recv_ns"].astype(np.int64)
    sane = ((rows["bid_px"] > 0) & (rows["ask_px"] > rows["bid_px"])
            & ((rows["ask_px"].astype(np.int64)
                - rows["bid_px"].astype(np.int64)) % SELFTEST_TICK == 0))
    quality = native_book_quality(rows["ts_recv_ns"], rows["flags"], sane)
    flow = extract_cell(rows, ts, np.asarray(quality.trusted_message, bool),
                        np.asarray(quality.trusted_economic, bool), cell,
                        tick=SELFTEST_TICK, mutant=mutant)
    tick = SELFTEST_TICK
    base_mid2 = 2 * SELFTEST_BASE_BID + tick
    low_mid2 = base_mid2 - 8 * tick
    failures: list[str] = []

    def _check(name: str, body) -> None:
        try:
            body()
        except Exception as error:  # noqa: BLE001 - a red case is the signal
            failures.append(f"{name}: {type(error).__name__}: {error}")

    def bars() -> None:
        assert len(flow["vol"]) == SELFTEST_BARS, f"bar count {len(flow['vol'])}"
        assert list(flow["bar_close_ts_ns"]) == [
            SELFTEST_BASE_TS + (k + 1) * 60 * NANOS_PER_SECOND
            for k in range(SELFTEST_BARS)], "bar closes are not phase-aligned"

    def delta_and_volume() -> None:
        # Bar 0 by hand: buys 5 and 7, sell 3.
        assert int(flow["delta"][0]) == 9, f"delta0 {flow['delta'][0]}"
        assert int(flow["vol"][0]) == 15, f"vol0 {flow['vol'][0]}"
        assert int(flow["ntrades"][0]) == 3, f"ntrades0 {flow['ntrades'][0]}"
        assert int(flow["maxtrade"][0]) == 7, f"maxtrade0 {flow['maxtrade'][0]}"
        assert int(flow["twoside"][0]) == 3, f"twoside0 {flow['twoside'][0]}"
        assert int(flow["quote_events"][0]) == 2, f"quote0 {flow['quote_events'][0]}"
        assert int(flow["quote_events"][1]) == 2, f"quote1 {flow['quote_events'][1]}"
        # Bar 2 by hand: sells 100 and 6, buy 40.
        assert int(flow["delta"][2]) == 40 - 106, f"delta2 {flow['delta'][2]}"
        assert int(flow["vol"][2]) == 146, f"vol2 {flow['vol'][2]}"
        assert int(flow["maxtrade"][2]) == 100, f"maxtrade2 {flow['maxtrade'][2]}"
        assert int(flow["twoside"][2]) == 40, f"twoside2 {flow['twoside'][2]}"

    def running_extreme() -> None:
        assert not bool(flow["run_low_valid"][0]), "bar 0 cannot have a prior extreme"
        assert int(flow["run_low_mid2"][2]) == low_mid2, (
            f"run_low2 {flow['run_low_mid2'][2]} != {low_mid2}")
        assert int(flow["bar_low_mid2"][2]) == low_mid2 - 2 * tick, (
            f"bar_low2 {flow['bar_low_mid2'][2]}")

    def attack_and_yield() -> None:
        # Bar 2 by hand: the 100 print sits 0.5 tick from the running low and
        # the 6 print 1.5 ticks; the 40 print sits 4.5 ticks out and is not an
        # attack.  Fresh progress is exactly one tick below the running low.
        assert int(flow["attack_low"][2]) == 106, f"attack_low2 {flow['attack_low'][2]}"
        assert int(flow["attack_low"][0]) == 0, "bar 0 has no level to attack"
        hand = 1.0 / (106 + 1.0)
        assert abs(float(flow["yield_low"][2]) - hand) < 1e-12, (
            f"yield_low2 {flow['yield_low'][2]} != {hand}")
        # Bar 1 takes four fresh ticks with no attack at all: maximum yield.
        assert float(flow["yield_low"][1]) == 4.0, f"yield_low1 {flow['yield_low'][1]}"

    def reload_proxy() -> None:
        # Bar 2 by hand: bid size 10 -> 4 -> 12 -> 20 at one unchanged price,
        # so only the +8 and +8 are replenishment; the drop to 4 is not, and
        # the later fall back to 10 is not.
        assert int(flow["reload_low"][2]) == 16, f"reload_low2 {flow['reload_low'][2]}"
        assert int(flow["reload_low"][0]) == 0, "bar 0 has no level to reload"

    def strictly_before_boundary() -> None:
        # The 999 print lands exactly on bar 2's close, so bar 3 owns it.
        assert int(flow["vol"][2]) == 146, (
            f"row exactly at the bar close was counted early: vol2={flow['vol'][2]}")
        assert int(flow["vol"][3]) == 1001, (
            f"row exactly at the bar close is missing from bar 3: vol3={flow['vol'][3]}")

    _check("bars", bars)
    _check("delta_and_volume", delta_and_volume)
    _check("running_extreme", running_extreme)
    _check("attack_and_yield", attack_and_yield)
    _check("reload_proxy", reload_proxy)
    _check("strictly_before_boundary", strictly_before_boundary)

    expected_red = {"flow_uses_row_at_close": "strictly_before_boundary"}
    if mutant:
        died = {line.split(":", 1)[0] for line in failures}
        target = expected_red.get(mutant)
        if target is None:
            print(f"flow_selftest_unknown_mutant {mutant}")
            return 1
        if target not in died:
            print(f"flow_selftest_mutant_survived mutant={mutant} case={target}")
            return 1
        print(f"flow_selftest_red mutant={mutant} died={sorted(died)}")
        for line in failures:
            print(f"  {line}")
        return 1
    if failures:
        print(f"flow_selftest_red died={sorted(line.split(':', 1)[0] for line in failures)}")
        for line in failures:
            print(f"  {line}")
        return 1
    print("flow_selftest_ok")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--conservation", default="")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--assets", default=",".join(ASSETS))
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.conservation:
        asset, day = args.conservation.split("/")
        return conservation(asset.strip().upper(), int(day))
    assets = tuple(name.strip().upper() for name in args.assets.split(",") if name.strip())
    if any(asset not in ASSETS for asset in assets):
        raise FlowStop(f"unknown asset in {args.assets!r}")
    manifest = build_all(assets, max(1, int(args.workers)))
    totals = manifest["totals"]
    print(f"shards={totals['shards']} by_asset={totals['shards_by_asset']}")
    print(f"cells={totals['cells']} bars={totals['bars']}")
    print(f"npz_bytes={totals['npz_bytes']} event_bytes={totals['event_bytes']} "
          f"event_rows={totals['event_rows']}")
    print(f"wall_seconds={totals['wall_seconds']} "
          f"shard_wall_seconds={totals['shard_wall_seconds']}")
    print(f"manifest={FLOW_ROOT / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
