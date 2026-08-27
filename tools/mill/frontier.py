#!/usr/bin/env python3
"""First frontier measurements over the mill substrate (EXPLORE tier).

Cash surface, winner-side decay, side knowability, wall geometry and the joint
wedge table with its two nulls.  Every cert is the frozen outcome law replayed
at a lattice point; every side call is a causal function of trusted rows
strictly before the read time.  Exploratory: these numbers can kill and cannot
promote.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile
import time
from typing import Mapping, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from engine.entry_v2.confirmation_types import NANOS_PER_SECOND
from engine.entry_v2.replay import _drawdown

import mill as M

OUT_PATH = ROOT / ".audit/mill-frontier.json"
SPLIT_PATH = ROOT / ".audit/mill-split.json"
FRONTIER_SCHEMA = "QRE2MILLFRONTIER1"
REFERENCE_SECONDS = (300, 600, 900, 1200, 1800, 2400, 3000, 3600, 5400, 7200,
                     10800, 14400)
PHASE_FRACTIONS = (0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90)
PER_TRADE_RUNG_USD = {"HG": 2000.0 / 3.0, "NKD": 1500.0 / 3.0, "SI": 1500.0 / 3.0}
DISTANCE_EDGES_USD = (0.0, 100.0, 250.0, 500.0, 1000.0)
SIDE_CALLS = ("momentum", "reversal", "range_below_mid", "range_above_mid",
              "vs_formation", "vs_formation_flip", "vs_mean", "vs_mean_flip")
QUANTILES = (10, 25, 50, 75, 90)


def _running(index: M.MillIndex) -> Mapping[str, np.ndarray]:
    mid2 = index.mid2.astype(np.int64)
    n = len(mid2)
    run_max = np.maximum.accumulate(mid2)
    run_min = np.minimum.accumulate(mid2)
    order = np.arange(n, dtype=np.int64)
    new_high = np.empty(n, bool)
    new_low = np.empty(n, bool)
    if n:
        new_high[0] = True
        new_low[0] = True
        new_high[1:] = mid2[1:] > run_max[:-1]
        new_low[1:] = mid2[1:] < run_min[:-1]
    last_high = np.maximum.accumulate(np.where(new_high, order, -1))
    last_low = np.maximum.accumulate(np.where(new_low, order, -1))
    momentum = np.where(last_high >= last_low, 1, -1).astype(np.int64)
    below_mid = np.where(2 * mid2 < (run_max + run_min), 1, -1).astype(np.int64)
    mean = np.cumsum(mid2.astype(np.float64)) / (order + 1)
    vs_mean = np.where(mid2.astype(np.float64) - mean >= 0.0, 1, -1).astype(np.int64)
    return {"mid2": mid2, "run_max": run_max, "run_min": run_min,
            "momentum": momentum, "below_mid": below_mid, "vs_mean": vs_mean}


def _calls_at(running: Mapping[str, np.ndarray], positions: np.ndarray,
              anchor_mid2: int) -> Mapping[str, np.ndarray]:
    momentum = running["momentum"][positions]
    below = running["below_mid"][positions]
    formation = np.where(
        running["mid2"][positions] - int(anchor_mid2) >= 0, 1, -1).astype(np.int64)
    mean = running["vs_mean"][positions]
    return {"momentum": momentum, "reversal": -momentum,
            "range_below_mid": below, "range_above_mid": -below,
            "vs_formation": formation, "vs_formation_flip": -formation,
            "vs_mean": mean, "vs_mean_flip": -mean}


def _dense(grid: Mapping[str, np.ndarray], size: int
           ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    cert = np.full(size, np.nan)
    wall = np.zeros(size, bool)
    ok = np.zeros(size, bool)
    keep = grid["input_index"]
    if len(keep):
        cert[keep] = grid["cert_close_usd"]
        wall[keep] = grid["wall_hit"]
        ok[keep] = True
    return cert, wall, ok


class CellFrontier:
    """Every per-cell array the frontier tables are reduced from."""

    __slots__ = ("asset", "d8", "cell", "lattice", "since_open", "since_first",
                 "fraction", "cert", "wall", "ok", "calls", "jitter_calls",
                 "winner", "best", "distance")

    def __init__(self, shard: M.Shard, cell: M.Cell, lattice_ns: int,
                 rng: np.random.Generator, running: Mapping[str, np.ndarray]) -> None:
        index = shard.cell_index(cell)
        span = int(cell.phase_close_ts_ns) - int(cell.phase_open_ts_ns)
        lattice = np.arange(int(cell.phase_open_ts_ns), int(cell.phase_close_ts_ns),
                            lattice_ns, dtype=np.int64)
        self.asset = shard.asset
        self.d8 = shard.d8
        self.cell = cell.text
        self.lattice = lattice
        self.since_open = (lattice - int(cell.phase_open_ts_ns)) // NANOS_PER_SECOND
        self.since_first = (lattice - int(cell.first_formation_ts_ns)) // NANOS_PER_SECOND
        self.fraction = (lattice - int(cell.phase_open_ts_ns)) / max(1, span)
        self.cert = {}
        self.wall = {}
        self.ok = {}
        for side in (1, -1):
            cert, wall, ok = _dense(
                index.outcomes_grid(lattice, side, int(cell.phase_close_ts_ns)),
                len(lattice))
            self.cert[side] = cert
            self.wall[side] = wall
            self.ok[side] = ok
        positions = np.maximum(index.positions(lattice), 0)
        self.calls = _calls_at(running, positions, cell.anchor_entry_mid2)
        shift = int(rng.integers(0, max(1, span)))
        jitter = int(cell.phase_open_ts_ns) + (
            (lattice - int(cell.phase_open_ts_ns) + shift) % max(1, span))
        self.jitter_calls = _calls_at(
            running, np.maximum(index.positions(jitter), 0), cell.anchor_entry_mid2)
        best = {}
        for side in (1, -1):
            values = self.cert[side][self.ok[side]]
            best[side] = float(np.max(values)) if len(values) else float("nan")
        self.best = best
        long_best, short_best = best[1], best[-1]
        if np.isnan(long_best) and np.isnan(short_best):
            self.winner = 0
        elif np.isnan(short_best) or (not np.isnan(long_best) and long_best >= short_best):
            self.winner = 1
        else:
            self.winner = -1
        factor = index.factor
        mid2 = running["mid2"][positions]
        self.distance = {
            1: (running["run_max"][positions] - mid2) * factor,
            -1: (mid2 - running["run_min"][positions]) * factor,
        }

    def at(self, seconds: int) -> int | None:
        found = int(np.searchsorted(self.since_open, seconds, side="left"))
        if found >= len(self.since_open) or int(self.since_open[found]) != seconds:
            return None
        return found


def _quantiles(values: Sequence[float]) -> dict[str, float]:
    if not len(values):
        return {"n": 0}
    array = np.asarray(values, np.float64)
    out = {"n": int(len(array)), "mean": float(array.mean()),
           "sum": float(array.sum())}
    for q in QUANTILES:
        out[f"p{q}"] = float(np.percentile(array, q))
    return out


def _separation(line: Mapping[tuple[str, int], float],
                null: Mapping[tuple[str, int], float]) -> dict[str, float]:
    keys = sorted(set(line) | set(null))
    diffs = np.asarray([line.get(key, 0.0) - null.get(key, 0.0) for key in keys],
                       np.float64)
    if len(diffs) < 2:
        return {"days": int(len(diffs)), "mean_diff": 0.0, "se": 0.0,
                "separated": False}
    se = float(diffs.std(ddof=1) / np.sqrt(len(diffs)))
    mean = float(diffs.mean())
    return {"days": int(len(diffs)), "mean_diff": mean, "se": se,
            "separated": bool(abs(mean) > 2.0 * se)}


def _wedge_line(rows: Sequence[tuple[str, int, int, float, bool]],
                asset_days: int) -> dict[str, object]:
    if not rows:
        return {"cells": 0, "usd_per_asset_day": 0.0, "win_rate": 0.0,
                "wall_rate": 0.0, "max_drawdown_usd": 0.0, "total_usd": 0.0}
    ordered = sorted(rows, key=lambda row: (row[1], row[2], row[0]))
    certs = np.asarray([row[3] for row in ordered], np.float64)
    walls = np.asarray([row[4] for row in ordered], bool)
    return {
        "cells": int(len(ordered)),
        "total_usd": float(certs.sum()),
        "usd_per_asset_day": float(certs.sum() / max(1, asset_days)),
        "win_rate": float((certs > 0).mean()),
        "wall_rate": float(walls.mean()),
        "max_drawdown_usd": float(_drawdown(float(value) for value in certs)),
    }


def _by_day(rows: Sequence[tuple[str, int, int, float, bool]]
            ) -> dict[tuple[str, int], float]:
    out: dict[tuple[str, int], float] = {}
    for cell, _entry, day, cert, _wall in rows:
        key = (cell.split("/")[0], day)
        out[key] = out.get(key, 0.0) + float(cert)
    return out


def measure(store: M.CellStore, lattice_sec: int, seed: int = 20260827,
            reference_seconds: Sequence[int] = REFERENCE_SECONDS) -> dict[str, object]:
    lattice_ns = int(lattice_sec) * NANOS_PER_SECOND
    reference_seconds = tuple(int(value) for value in reference_seconds)
    per_asset: dict[str, dict[str, object]] = {}
    frontiers: dict[str, list[CellFrontier]] = {}
    asset_days: dict[str, set[int]] = {}
    silent = 0
    cells_seen = 0
    rng = np.random.default_rng(seed)
    for shard in store.shards():
        asset_days.setdefault(shard.asset, set()).add(shard.d8)
        running: dict[int, Mapping[str, np.ndarray]] = {}
        for cell in shard.cells:
            cells_seen += 1
            if cell.quality_idx not in running:
                running[cell.quality_idx] = _running(shard.cell_index(cell))
            frontier = CellFrontier(shard, cell, lattice_ns, rng,
                                    running[cell.quality_idx])
            if frontier.winner == 0:
                silent += 1
                continue
            frontiers.setdefault(shard.asset, []).append(frontier)
    for asset, rows in sorted(frontiers.items()):
        days = len(asset_days.get(asset, ()))
        decay: dict[str, dict[str, object]] = {}
        accuracy: dict[str, dict[str, float]] = {}
        wall_table: dict[str, dict[str, object]] = {}
        wedge: dict[str, dict[str, object]] = {}
        for seconds in reference_seconds:
            winner_certs: list[float] = []
            for row in rows:
                position = row.at(seconds)
                if position is None or not row.ok[row.winner][position]:
                    continue
                winner_certs.append(float(row.cert[row.winner][position]))
            decay[str(seconds)] = _quantiles(winner_certs)
            hits = {name: [0, 0] for name in SIDE_CALLS}
            for row in rows:
                position = row.at(seconds)
                if position is None or not row.ok[row.winner][position]:
                    continue
                for name in SIDE_CALLS:
                    hits[name][1] += 1
                    hits[name][0] += int(row.calls[name][position]) == row.winner
            accuracy[str(seconds)] = {
                name: (hit / total if total else 0.0) for name, (hit, total) in hits.items()}
            accuracy[str(seconds)]["cells"] = float(
                max(total for _hit, total in hits.values()) if hits else 0.0)
            buckets: dict[str, list[int]] = {}
            for row in rows:
                position = row.at(seconds)
                if position is None:
                    continue
                for side in (1, -1):
                    if not row.ok[side][position]:
                        continue
                    distance = float(row.distance[side][position])
                    edge = int(np.searchsorted(DISTANCE_EDGES_USD, distance, side="right"))
                    key = f"side{'+1' if side > 0 else '-1'}/d{edge}"
                    entry = buckets.setdefault(key, [0, 0])
                    entry[0] += int(bool(row.wall[side][position]))
                    entry[1] += 1
            wall_table[str(seconds)] = {
                key: {"wall_rate": hit / total, "n": total}
                for key, (hit, total) in sorted(buckets.items()) if total}
            for name in SIDE_CALLS:
                line: list[tuple[str, int, int, float, bool]] = []
                flip: list[tuple[str, int, int, float, bool]] = []
                jitter: list[tuple[str, int, int, float, bool]] = []
                for row in rows:
                    position = row.at(seconds)
                    if position is None:
                        continue
                    for bucket, call in ((line, int(row.calls[name][position])),
                                         (flip, -int(row.calls[name][position])),
                                         (jitter, int(row.jitter_calls[name][position]))):
                        if not row.ok[call][position]:
                            continue
                        bucket.append((row.cell, int(row.lattice[position]), row.d8,
                                       float(row.cert[call][position]),
                                       bool(row.wall[call][position])))
                wedge[f"{name}@{seconds}"] = {
                    "line": _wedge_line(line, days),
                    "null_side_flip": _wedge_line(flip, days),
                    "null_time_jitter": _wedge_line(jitter, days),
                    "separation_vs_side_flip": _separation(_by_day(line), _by_day(flip)),
                    "separation_vs_time_jitter": _separation(
                        _by_day(line), _by_day(jitter)),
                }
        fraction_decay: dict[str, dict[str, object]] = {}
        for fraction in PHASE_FRACTIONS:
            values: list[float] = []
            for row in rows:
                if not len(row.lattice):
                    continue
                position = int(np.searchsorted(row.fraction, fraction, side="left"))
                if position >= len(row.lattice) or not row.ok[row.winner][position]:
                    continue
                values.append(float(row.cert[row.winner][position]))
            fraction_decay[f"{fraction:.2f}"] = _quantiles(values)
        formation_decay: dict[str, dict[str, object]] = {}
        for seconds in reference_seconds:
            values = []
            for row in rows:
                position = int(np.searchsorted(row.since_first, seconds, side="left"))
                if position >= len(row.lattice) or not row.ok[row.winner][position]:
                    continue
                values.append(float(row.cert[row.winner][position]))
            formation_decay[str(seconds)] = _quantiles(values)
        rung = PER_TRADE_RUNG_USD.get(asset, 500.0)
        crossing = None
        for seconds in reference_seconds:
            stats = decay[str(seconds)]
            if stats.get("n") and float(stats["mean"]) >= rung:
                crossing = seconds
        per_asset[asset] = {
            "asset_days": days, "cells": len(rows),
            "winner_long": sum(row.winner > 0 for row in rows),
            "winner_short": sum(row.winner < 0 for row in rows),
            "best_long_mean": float(np.nanmean([row.best[1] for row in rows])),
            "best_short_mean": float(np.nanmean([row.best[-1] for row in rows])),
            "per_trade_rung_usd": rung, "t_max_seconds": crossing,
            "decay_since_phase_open": decay,
            "decay_since_first_formation": formation_decay,
            "decay_by_phase_fraction": fraction_decay,
            "side_call_accuracy": accuracy,
            "wall_by_distance": wall_table,
            "joint_wedge": wedge,
        }
    return {
        "schema": FRONTIER_SCHEMA, "tier": "exploratory",
        "claim": "EXPLORE-day frontier; can kill, cannot promote",
        "lattice_seconds": int(lattice_sec), "seed": seed,
        "cells_seen": cells_seen, "cells_silent": silent,
        "reference_seconds": list(reference_seconds),
        "side_calls": list(SIDE_CALLS),
        "distance_edges_usd": list(DISTANCE_EDGES_USD),
        "by_asset": per_asset,
    }


def _print_tables(report: Mapping[str, object]) -> None:
    ladder = tuple(int(value) for value in report["reference_seconds"])
    for asset, block in sorted(report["by_asset"].items()):
        print(f"\n== {asset}  asset_days={block['asset_days']} cells={block['cells']} "
              f"W(long)={block['winner_long']} W(short)={block['winner_short']} "
              f"rung/trade={block['per_trade_rung_usd']:.0f} "
              f"T_max={block['t_max_seconds']}")
        print("  winner-side decay (usd, since phase open)")
        print("   t_sec      n     mean      p10      p50      p90")
        for seconds in ladder:
            row = block["decay_since_phase_open"][str(seconds)]
            if not row.get("n"):
                continue
            print(f"  {seconds:6d} {row['n']:6d} {row['mean']:8.1f} "
                  f"{row['p10']:8.1f} {row['p50']:8.1f} {row['p90']:8.1f}")
        print("  side-call accuracy vs W(cell)")
        print("   t_sec " + " ".join(f"{name[:9]:>10}" for name in SIDE_CALLS))
        for seconds in ladder:
            row = block["side_call_accuracy"][str(seconds)]
            if not row.get("cells"):
                continue
            print(f"  {seconds:6d} " + " ".join(
                f"{row[name]:10.3f}" for name in SIDE_CALLS))
        print("  wall rate by distance-from-running-extreme bucket")
        for seconds in ladder:
            row = block["wall_by_distance"][str(seconds)]
            if not row:
                continue
            print(f"  {seconds:6d} " + " ".join(
                f"{key}={value['wall_rate']:.2f}(n={value['n']})"
                for key, value in sorted(row.items())))
        print("  joint wedge (usd/asset-day; nulls: flip / jitter)")
        print("   call@t                      cells   usd/day    win    wall"
              "       mdd   flip_usd  jit_usd  sep")
        for key, value in sorted(block["joint_wedge"].items()):
            line = value["line"]
            if not line["cells"]:
                continue
            flag = ("F" if value["separation_vs_side_flip"]["separated"] else "-") + (
                "J" if value["separation_vs_time_jitter"]["separated"] else "-")
            print(f"  {key:26s} {line['cells']:6d} {line['usd_per_asset_day']:9.1f} "
                  f"{line['win_rate']:6.2f} {line['wall_rate']:7.2f} "
                  f"{line['max_drawdown_usd']:9.0f} "
                  f"{value['null_side_flip']['usd_per_asset_day']:10.1f} "
                  f"{value['null_time_jitter']['usd_per_asset_day']:8.1f}  {flag}")


def selftest(lattice_sec: int) -> int:
    """Synthetic fixture only.  The reference ladder shrinks to the fixture."""

    days = (20220301, 20220302, 20220303, 20220304)
    ladder = (30, 60, 90, 120, 150)
    lattice_sec = min(int(lattice_sec), 30)
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        written = _load_builder().write_synthetic_shards(root, days)
        store = M.CellStore(written, root)
        report = measure(store, lattice_sec, seed=7, reference_seconds=ladder)
        _print_tables(report)
        (root / "frontier.json").write_text(json.dumps(report, sort_keys=True))
        assert report["cells_seen"] == 4 * len(days), "synthetic cell count differs"
        block = report["by_asset"]["HG"]
        assert block["asset_days"] == len(days), "synthetic asset-day count differs"
        assert block["cells"] >= 1, "no synthetic cell survived"
        assert block["winner_long"] + block["winner_short"] == block["cells"]
        decay = block["decay_since_phase_open"]["30"]
        assert decay.get("n"), "winner-side decay is empty at t=30"
        assert block["decay_by_phase_fraction"]["0.50"].get("n"), "fraction decay is empty"
        assert block["decay_since_first_formation"]["30"].get("n"), "formation decay empty"
        assert block["wall_by_distance"]["30"], "wall-by-distance table is empty"
        for name in SIDE_CALLS:
            key = f"{name}@30"
            assert key in block["joint_wedge"], f"wedge line is absent: {key}"
            entry = block["joint_wedge"][key]
            assert entry["line"]["cells"], f"wedge line entered no cell: {key}"
            for null in ("null_side_flip", "null_time_jitter"):
                assert null in entry, f"{key} lacks {null}"
            assert 0.0 <= block["side_call_accuracy"]["30"][name] <= 1.0
        pair = block["side_call_accuracy"]["30"]
        assert abs(pair["momentum"] + pair["reversal"] - 1.0) < 1e-9, (
            "momentum/reversal polarities do not partition")
    print("frontier_selftest_ok")
    return 0


def _load_builder():
    import build_substrate  # noqa: PLC0415 - sibling module, path pinned above

    return build_substrate


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", default="HG,NKD,SI")
    parser.add_argument("--lattice-sec", type=int, default=30)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--root", default=str(M.MILL_ROOT))
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest(int(args.lattice_sec))
    assets = tuple(name.strip().upper() for name in args.assets.split(",") if name.strip())
    started = time.monotonic()
    store = M.load_store(SPLIT_PATH, assets, root=Path(args.root))
    report = measure(store, int(args.lattice_sec))
    report["assets"] = list(assets)
    report["wall_seconds"] = round(time.monotonic() - started, 2)
    OUT_PATH.write_text(json.dumps(report, sort_keys=True, indent=1) + "\n")
    _print_tables(report)
    print(f"\nwrote {OUT_PATH} wall={report['wall_seconds']}s "
          f"cells={report['cells_seen']} silent={report['cells_silent']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
