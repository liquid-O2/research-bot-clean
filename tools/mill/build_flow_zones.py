#!/usr/bin/env python3
"""Zone-episode cache for the side-resolution mill (audit finding 1b).

One uncompressed npz + json sidecar per EXPLORE ``(asset, d8)`` under
``artifacts/cache/mill_flow_zones/``.  Each cell of the day - a
``(phase, phase_open_ts_ns)`` formation window - becomes, for each of its two
sides, the bar-resolution zone series and the completed episode table defined by
``flow_zones.py``.

The bar lattice is the MILL's, not the flow cache's: ``sweep1`` samples the cell
at ``lat[j] = phase_open + 60 j`` and reads the value at that close from rows
strictly before it, while ``build_flow.py`` numbers the same closes from zero.
Flow bar ``j - 1`` therefore closes at mill bar ``j``, and mill bar 0 (the phase
open itself) has no flow behind it.  Every join in this module is that one
shift, asserted per cell.

Sources: the sweep-1 prep cache (``artifacts/cache/mill/``), the minute flow
cache (``artifacts/cache/mill_flow/`` via ``flow.load_flow``), and the context
store (``artifacts/cache/mill_context/`` via ``context.ContextStore``).  EXPLORE
days only, per ``.audit/mill-split.json``.  Nothing here opens a HOLD day, a
teacher or late label, or any outcome column.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
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
sys.path.insert(0, str(Path(__file__).resolve().parent))

import context as CTX
import flow as FLOW
import flow_zones as FZ
import sweep1 as S1
import sweep2 as S2
import sweep3 as S3

SPLIT_PATH = ROOT / ".audit/mill-split.json"
ASSETS = ("HG", "NKD", "SI")
DEFAULT_WORKERS = 10

# Every value the cache carries is derived from these three inputs plus the
# frozen zone geometry; the sidecar records them so a reader can prove lineage.
SOURCE_NAMES = ("mill_prep", "mill_flow", "mill_context")


class BuildStop(RuntimeError):
    pass


# --------------------------------------------------------------------------
# Per-worker state.  A process loads the prep cache and the context store once.
# --------------------------------------------------------------------------

_STATE: dict[str, object] = {}


def _state() -> tuple[dict[tuple[str, int], list[int]], list[S1.CellRec],
                      list[S2.Extremes], list[S3.Ctx | None]]:
    if "records" not in _STATE:
        records, _days = S1.load_cache()
        store = CTX.ContextStore()
        index: dict[tuple[str, int], list[int]] = {}
        for position, rec in enumerate(records):
            index.setdefault((rec.asset, int(rec.d8)), []).append(position)
        _STATE["records"] = records
        _STATE["index"] = index
        _STATE["exts"] = [S2.extremes(rec) for rec in records]
        _STATE["ctxs"] = S3.contexts_for(records, store)
    return (_STATE["index"], _STATE["records"],  # type: ignore[return-value]
            _STATE["exts"], _STATE["ctxs"])


def to_lattice(values: np.ndarray, bars: int) -> np.ndarray:
    """Flow bar ``j-1`` closes at mill bar ``j``; mill bar 0 has no flow."""

    out = np.zeros(bars, np.float64)
    out[1:] = np.asarray(values, np.float64)[: bars - 1]
    return out


def build_cell(rec: S1.CellRec, ext: S2.Extremes, ctx: S3.Ctx,
               arrays: Mapping[str, np.ndarray]
               ) -> tuple[dict[int, FZ.ZoneSide], dict[str, np.ndarray]]:
    """One cell's two sides plus the shared per-bar flow, on the mill lattice."""

    bars = int(rec.n)
    if len(arrays["vol"]) != bars:
        raise BuildStop(
            f"flow cell has {len(arrays['vol'])} bars, mill cell has {bars}")
    tick2 = 2.0 * float(S1.ASSET_RAW_TICK[rec.asset])
    shared = {name: to_lattice(arrays[name], bars) for name in FZ.CELL_SERIES}
    sides: dict[int, FZ.ZoneSide] = {}
    for side in FZ.SIDES:
        tag = "low" if side > 0 else "high"
        sides[side] = FZ.cell_side_zones(
            np.asarray(rec.mid, np.float64),
            np.asarray(ext.new_low if side > 0 else ext.new_high, bool),
            to_lattice(arrays[f"attack_{tag}"], bars),
            to_lattice(arrays[f"reload_{tag}"], bars),
            shared["delta"], shared["vol"], side,
            tick2=tick2, atr_mid2=float(ctx.atr_mid2))
    return sides, shared


def build_one(asset: str, d8: int, out_root: Path) -> dict[str, object]:
    started = time.monotonic()
    index, records, exts, ctxs = _state()
    positions = index.get((asset, int(d8)), [])
    if not positions:
        raise BuildStop(f"prep cache has no cell for {asset}/{d8}")
    cells = FLOW.load_flow(asset, d8)
    payload: dict[str, np.ndarray] = {}
    sidecar_cells: list[dict[str, object]] = []
    skipped: list[str] = []
    episodes_total = 0
    kept = 0
    for position in positions:
        rec = records[position]
        ctx = ctxs[position]
        if ctx is None:
            # Skipped by law: without ATR14_prev the zone has no width.
            skipped.append(rec.phase)
            continue
        key = (rec.phase, int(rec.phase_open_ts_ns))
        if key not in cells:
            raise BuildStop(f"flow shard lacks cell {key} for {asset}/{d8}")
        sides, shared = build_cell(rec, exts[position], ctx, cells[key])
        slot = kept
        for name, array in shared.items():
            payload[f"c{slot}_{name}"] = array
        for side, zone in sides.items():
            tag = FZ.SIDE_TAG[side]
            for name in FZ.SIDE_SERIES:
                payload[f"c{slot}_{tag}_{name}"] = zone.series[name]
            payload[f"c{slot}_{tag}_episodes"] = zone.episodes
            episodes_total += int(len(zone.episodes))
        sidecar_cells.append({
            "phase": rec.phase, "phase_open_ts_ns": int(rec.phase_open_ts_ns),
            "phase_close_ts_ns": int(rec.phase_close_ts_ns), "bars": int(rec.n),
            "tick2": 2.0 * float(S1.ASSET_RAW_TICK[asset]),
            "atr_mid2": float(ctx.atr_mid2), "prior_d8": int(ctx.prior_d8),
            "prior_low_mid2": float(ctx.prior_low),
            "prior_high_mid2": float(ctx.prior_high),
            "episodes": {FZ.SIDE_TAG[side]: int(len(sides[side].episodes))
                         for side in FZ.SIDES}})
        kept += 1
    sidecar = {
        "schema": FZ.ZONES_SCHEMA, "asset": asset, "d8": int(d8),
        "zone_w_atr": FZ.ZONE_W_ATR, "merge_gap_bars": FZ.MERGE_GAP_BARS,
        "core_ticks": FZ.CORE_TICKS, "held_bars": FZ.HELD_BARS,
        "post_bars": FZ.POST_BARS,
        "episode_columns": list(FZ.EPISODE_COLUMNS),
        "side_series": list(FZ.SIDE_SERIES), "cell_series": list(FZ.CELL_SERIES),
        "cells": sidecar_cells, "skipped_phases": skipped,
        "counts": {"cells": kept, "skipped": len(skipped),
                   "bars": int(sum(int(cell["bars"]) for cell in sidecar_cells)),
                   "episodes": episodes_total}}
    directory = out_root / asset
    directory.mkdir(parents=True, exist_ok=True)
    npz_path = directory / f"{int(d8)}.npz"
    with npz_path.open("wb") as handle:
        np.savez(handle, **payload)
    npz_sha = hashlib.sha256(npz_path.read_bytes()).hexdigest()
    (directory / f"{int(d8)}.json").write_text(
        json.dumps({**sidecar, "npz_sha256": npz_sha}, sort_keys=True, indent=1)
        + "\n")
    return {"asset": asset, "d8": int(d8), "npz_sha256": npz_sha,
            "npz_bytes": int(npz_path.stat().st_size),
            "counts": dict(sidecar["counts"]),
            "wall_seconds": round(time.monotonic() - started, 3)}


def _job(job: tuple[str, int, str]) -> dict[str, object]:
    asset, d8, out_root = job
    return build_one(asset, int(d8), Path(out_root))


def build_all(assets: Sequence[str], workers: int,
              out_root: Path = FZ.ZONES_ROOT) -> dict[str, object]:
    days = S1._explore_days(assets)
    jobs = [(asset, int(day), str(out_root)) for asset in assets
            for day in days[asset]]
    out_root.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    shards: list[dict[str, object]] = []
    failures: list[str] = []
    if workers <= 1:
        for job in jobs:
            shards.append(_job(job))
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_job, job): job for job in jobs}
            done = 0
            for future in as_completed(futures):
                asset, day, _root = futures[future]
                try:
                    shards.append(future.result())
                except Exception as error:  # noqa: BLE001 - reported, not swallowed
                    failures.append(f"{asset}/{day}: {type(error).__name__}: {error}")
                done += 1
                if done % 40 == 0:
                    print(f"  built {done}/{len(jobs)} "
                          f"elapsed={time.monotonic() - started:.1f}s", flush=True)
    if failures:
        raise BuildStop("zones shard build failed:\n  " + "\n  ".join(failures[:10]))
    shards.sort(key=lambda row: (ASSETS.index(str(row["asset"])), int(row["d8"])))
    split = json.loads(SPLIT_PATH.read_text())
    totals = {
        "shards": len(shards),
        "npz_bytes": sum(int(row["npz_bytes"]) for row in shards),
        "cells": sum(int(row["counts"]["cells"]) for row in shards),
        "skipped_cells": sum(int(row["counts"]["skipped"]) for row in shards),
        "bars": sum(int(row["counts"]["bars"]) for row in shards),
        "episodes": sum(int(row["counts"]["episodes"]) for row in shards),
        "shards_by_asset": {asset: sum(row["asset"] == asset for row in shards)
                            for asset in assets},
        "episodes_by_asset": {
            asset: sum(int(row["counts"]["episodes"]) for row in shards
                       if row["asset"] == asset) for asset in assets},
        "cells_by_asset": {
            asset: sum(int(row["counts"]["cells"]) for row in shards
                       if row["asset"] == asset) for asset in assets},
        "wall_seconds": round(time.monotonic() - started, 2)}
    manifest = {
        "schema": FZ.MANIFEST_SCHEMA, "tier": "exploratory",
        "split_sha256": str(split["split_sha256"]),
        "assets": list(assets), "workers": int(workers),
        "zone_w_atr": FZ.ZONE_W_ATR, "merge_gap_bars": FZ.MERGE_GAP_BARS,
        "core_ticks": FZ.CORE_TICKS, "held_bars": FZ.HELD_BARS,
        "post_bars": FZ.POST_BARS, "sources": list(SOURCE_NAMES),
        "built_unix": int(time.time()), "totals": totals, "shards": shards}
    (out_root / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=1) + "\n")
    return manifest


# --------------------------------------------------------------------------
# Distributions: the numbers audit finding 3 says must come from our own bytes.
# --------------------------------------------------------------------------

def distributions(assets: Sequence[str]) -> dict[str, object]:
    """Dip-past-first-touch and reward-to-confirm, terminal vs non-terminal."""

    days = S1._explore_days(assets)
    out: dict[str, object] = {}
    for asset in assets:
        buckets: dict[str, dict[str, list[float]]] = {
            label: {name: [] for name in
                    ("dip_ticks", "dip_atr", "post_mfe_ticks", "post_mfe_atr")}
            for label in ("terminal", "non_terminal", "all")}
        counts = {"episodes": 0, "with_touch": 0, "terminal": 0, "cells": 0}
        for day in days[asset]:
            for cell in FZ.load_zones(asset, day).values():
                counts["cells"] += 1
                for side in FZ.SIDES:
                    table = cell.sides[side].episodes
                    for row in table:
                        counts["episodes"] += 1
                        terminal = bool(row[FZ.EPISODE_INDEX["terminal"]])
                        counts["terminal"] += int(terminal)
                        touched = row[FZ.EPISODE_INDEX["first_touch"]] >= 0
                        counts["with_touch"] += int(touched)
                        label = "terminal" if terminal else "non_terminal"
                        for name in ("dip_ticks", "dip_atr", "post_mfe_ticks",
                                     "post_mfe_atr"):
                            value = float(row[FZ.EPISODE_INDEX[name]])
                            buckets[label][name].append(value)
                            buckets["all"][name].append(value)
        out[asset] = {
            "counts": counts,
            "quantiles": {label: {name: FZ.quantiles(values)
                                  for name, values in table.items()}
                          for label, table in buckets.items()},
            "n": {label: len([v for v in table["post_mfe_ticks"]])
                  for label, table in buckets.items()},
            "n_dip": {label: int(np.isfinite(np.asarray(table["dip_ticks"],
                                                        np.float64)).sum())
                      for label, table in buckets.items()}}
    return out


def print_distributions(block: Mapping[str, object]) -> None:
    print("\n== zone-episode distributions (EXPLORE, p25/p50/p75/p90)")
    print(f"{'asset':5s} {'label':13s} {'metric':15s} {'n':>7s} "
          f"{'p25':>10s} {'p50':>10s} {'p75':>10s} {'p90':>10s}")
    for asset, table in block.items():
        counts = table["counts"]
        print(f"{asset:5s} cells={counts['cells']} episodes={counts['episodes']} "
              f"with_touch={counts['with_touch']} terminal={counts['terminal']}")
        for label in ("all", "terminal", "non_terminal"):
            for name in ("dip_ticks", "dip_atr", "post_mfe_ticks", "post_mfe_atr"):
                values = table["quantiles"][label][name]
                size = (table["n_dip"][label] if name.startswith("dip")
                        else table["n"][label])
                cells = " ".join(
                    ("-".rjust(10) if value is None else f"{value:10.4f}")
                    for value in values)
                print(f"{asset:5s} {label:13s} {name:15s} {size:7d} {cells}")


# --------------------------------------------------------------------------
# Selftest: synthetic bars only.  Zero era bytes.
# --------------------------------------------------------------------------

SELFTEST_TICK2 = 2.0
SELFTEST_ATR = 100.0


def _synthetic() -> dict[str, np.ndarray]:
    """A 24-bar low-side fixture laid out so every case is hand-countable.

    Zone width is ``0.15 * 100 = 15`` mid2 units and the core band is
    ``2 * 2 = 4``.  The path sets a low of 0 at bar 2, holds inside the zone
    with two touches, leaves the zone for three bars (a gap that MERGES), comes
    back for a third touch, then leaves for six bars (a gap that SPLITS) and
    opens a second episode that pushes the low to -6.
    """

    mid = np.array([
        200.0, 100.0,      # bars 0-1: falling, running low is set at bar 1
        0.0,               # bar 2: new low 0 (run low at bar 2 is 100)
        2.0, 3.0,          # bars 3-4: inside the zone, both inside the core
        40.0, 45.0, 50.0,  # bars 5-7: out of zone, a three-bar gap
        6.0,               # bar 8: back in zone, outside the core (6 > 4)
        1.0,               # bar 9: in zone, a third touch
        60.0, 61.0, 62.0, 63.0, 64.0, 65.0,   # bars 10-15: a six-bar gap
        8.0,               # bar 16: in zone, opens the second episode
        -6.0,              # bar 17: new low, still in zone
        -5.0,              # bar 18: in zone, inside the core of -6
        70.0, 71.0, 72.0, 73.0, 74.0,         # bars 19-23: away, the reward
    ], np.float64)
    bars = len(mid)
    run_min = np.minimum.accumulate(mid)
    new_low = np.zeros(bars, bool)
    new_low[1:] = mid[1:] < run_min[:-1]
    return {"mid": mid, "new_low": new_low,
            "attack": np.ones(bars, np.float64),
            "reload": np.zeros(bars, np.float64),
            "delta": np.full(bars, -2.0), "vol": np.full(bars, 10.0)}


def selftest() -> int:
    mutant = FZ._mutant()
    fixture = _synthetic()
    zone = FZ.cell_side_zones(
        fixture["mid"], fixture["new_low"], fixture["attack"], fixture["reload"],
        fixture["delta"], fixture["vol"], 1,
        tick2=SELFTEST_TICK2, atr_mid2=SELFTEST_ATR)
    series = zone.series
    failures: list[str] = []

    def _check(name: str, body) -> None:
        try:
            body()
        except Exception as error:  # noqa: BLE001 - a red case is the signal
            failures.append(f"{name}: {type(error).__name__}: {error}")

    def strictly_before() -> None:
        # Bar 0 has no prior bar, so it has no level and cannot be in zone.
        assert not bool(series["run_ext_valid"][0]), "bar 0 carries a level"
        assert not bool(series["in_zone"][0]), "bar 0 is in a zone"
        # Bar 2 PRINTS the low of 0; the level it is measured against is still
        # 100, which is 100 away, so bar 2 is not in its own zone.
        assert float(series["run_ext_mid2"][2]) == 100.0, (
            f"run_ext at bar 2 is {series['run_ext_mid2'][2]}")
        assert not bool(series["in_zone"][2]), "the new-low bar zoned itself"
        assert float(series["run_ext_mid2"][3]) == 0.0, (
            f"run_ext at bar 3 is {series['run_ext_mid2'][3]}")

    def merge() -> None:
        # Bars 3,4 and 8,9 are in zone with a THREE-bar gap (5,6,7) between
        # them: 3 < 5, so one episode.  Bars 10-15 are a SIX-bar gap: 6 >= 5,
        # so bar 16 opens a second.
        spans = FZ.episode_spans(series["in_zone"])
        assert spans == [(3, 9), (16, 18)], f"episode spans {spans}"
        assert len(zone.episodes) == 2, f"episodes {len(zone.episodes)}"
        assert int(zone.column("start")[0]) == 3 and int(zone.column("end")[0]) == 9, (
            f"episode 0 span {zone.episodes[0][:2]}")

    def touches() -> None:
        # Core band is 4 mid2 units around the level.  Episode 0: bar 3 (|2-0|),
        # bar 4 (|3-0|) and bar 9 (|1-0|) are touches; bar 8 (|6-0|) is not.
        marks = list(np.flatnonzero(series["touch"]))
        assert marks == [3, 4, 9, 18], f"touch bars {marks}"
        assert int(zone.column("touches")[0]) == 3, (
            f"episode 0 touches {zone.column('touches')[0]}")
        assert int(zone.column("first_touch")[0]) == 3, (
            f"episode 0 first touch {zone.column('first_touch')[0]}")
        assert int(zone.column("touches")[1]) == 1, (
            f"episode 1 touches {zone.column('touches')[1]}")

    def memory() -> None:
        # touches_so_far is a running count; held credits a touch at the bar its
        # five-bar window closes, and only when no new low printed inside it.
        assert list(series["touches_so_far"][[3, 4, 8, 9, 17, 18]]) == [
            1, 2, 2, 3, 3, 4], f"touches_so_far {list(series['touches_so_far'])}"
        # Touch 3 resolves at bar 8 with no new low in 4..8 -> held.  Touch 4
        # resolves at 9, also held.  Touch 9 resolves at 14, held.  Touch 18
        # resolves at 23, held.  Nothing is credited before bar 8.
        assert int(series["held_so_far"][7]) == 0, (
            f"held credited early: {series['held_so_far'][7]}")
        assert int(series["held_so_far"][8]) == 1, (
            f"held at bar 8 is {series['held_so_far'][8]}")
        assert int(series["held_so_far"][14]) == 3, (
            f"held at bar 14 is {series['held_so_far'][14]}")
        assert list(series["episodes_so_far"][[2, 3, 15, 16]]) == [0, 1, 1, 2], (
            f"episodes_so_far {list(series['episodes_so_far'])}")
        assert list(series["last_touch_bar"][[2, 3, 5, 9, 12]]) == [
            -1, 3, 4, 9, 9], f"last_touch_bar {list(series['last_touch_bar'])}"

    def truncation() -> None:
        # The running accumulators are truncated at the reading bar: at bar 4 the
        # episode has consumed two bars of attack, not its whole seven.
        assert float(series["cum_attack"][4]) == 2.0, (
            f"cum_attack at bar 4 is {series['cum_attack'][4]}")
        assert float(series["cum_attack"][9]) == 7.0, (
            f"cum_attack at bar 9 is {series['cum_attack'][9]}")
        # Attacking delta at a low is the SELL side, so a delta of -2 per bar is
        # +2 of attack per bar.
        assert float(series["cum_adelta"][4]) == 4.0, (
            f"cum_adelta at bar 4 is {series['cum_adelta'][4]}")
        # Opposite aggression: vol 10 with delta -2 is 4 buys and 6 sells.
        assert float(series["cum_opp_vol"][4]) == 8.0, (
            f"cum_opp_vol at bar 4 is {series['cum_opp_vol'][4]}")
        # Episode 0 never pushes past the level it opened on, so no extension.
        assert float(series["cum_ext_ticks"][9]) == 0.0, (
            f"episode 0 extension {series['cum_ext_ticks'][9]}")
        # Episode 1 opens on a level of 0 and pushes to -6: three ticks.
        assert float(series["cum_ext_ticks"][17]) == 3.0, (
            f"episode 1 extension at bar 17 is {series['cum_ext_ticks'][17]}")

    def terminal_flag() -> None:
        # Episode 0's level (0) IS taken out at bar 17, so it is not terminal.
        # Episode 1's level (-6) is never taken out again.
        assert not bool(zone.column("terminal")[0]), "episode 0 read terminal"
        assert bool(zone.column("terminal")[1]), "episode 1 read non-terminal"

    def rewards() -> None:
        # Episode 0 ends at bar 9 (mid 1.0); the best of bars 10..23 is 74, so
        # the reward is 73 mid2 = 36.5 ticks.  Episode 1 ends at bar 18 (-5) and
        # the best of 19..23 is 74, so 79 mid2 = 39.5 ticks.
        assert abs(float(zone.column("post_mfe_ticks")[0]) - 36.5) < 1e-9, (
            f"episode 0 reward {zone.column('post_mfe_ticks')[0]}")
        assert abs(float(zone.column("post_mfe_ticks")[1]) - 39.5) < 1e-9, (
            f"episode 1 reward {zone.column('post_mfe_ticks')[1]}")
        # Dip past the first touch: episode 0's first touch is bar 3 (mid 2) and
        # the episode bottoms at 1, so 1 mid2 = 0.5 ticks.  Episode 1's first
        # touch is bar 18 (mid -5) and nothing below it follows inside it.
        assert abs(float(zone.column("dip_ticks")[0]) - 0.5) < 1e-9, (
            f"episode 0 dip {zone.column('dip_ticks')[0]}")
        assert float(zone.column("dip_ticks")[1]) == 0.0, (
            f"episode 1 dip {zone.column('dip_ticks')[1]}")

    _check("strictly_before", strictly_before)
    _check("merge", merge)
    _check("touches", touches)
    _check("memory", memory)
    _check("truncation", truncation)
    _check("terminal_flag", terminal_flag)
    _check("rewards", rewards)

    expected_red = {FZ.MUTANT_OWN_BAR: "strictly_before"}
    if mutant:
        died = {line.split(":", 1)[0] for line in failures}
        target = expected_red.get(mutant)
        if target is None:
            print(f"zones_selftest_unknown_mutant {mutant}")
            return 1
        if target not in died:
            print(f"zones_selftest_mutant_survived mutant={mutant} case={target}")
            return 1
        print(f"zones_selftest_red mutant={mutant} died={sorted(died)}")
        for line in failures:
            print(f"  {line}")
        return 1
    if failures:
        print("zones_selftest_red died="
              f"{sorted(line.split(':', 1)[0] for line in failures)}")
        for line in failures:
            print(f"  {line}")
        return 1
    print("zones_selftest_ok cases=7")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", nargs="?", default="build",
                        choices=("build", "dist", "all"))
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--assets", default=",".join(ASSETS))
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    if os.environ.get(FZ.MUTANT_ENV, ""):
        raise BuildStop("refusing to write a cache under a zones mutant")
    assets = tuple(name.strip().upper() for name in args.assets.split(",")
                   if name.strip())
    if any(asset not in ASSETS for asset in assets):
        raise BuildStop(f"unknown asset in {args.assets!r}")
    if args.stage in ("build", "all"):
        manifest = build_all(assets, max(1, int(args.workers)))
        totals = manifest["totals"]
        print(f"shards={totals['shards']} by_asset={totals['shards_by_asset']}")
        print(f"cells={totals['cells']} by_asset={totals['cells_by_asset']} "
              f"skipped={totals['skipped_cells']} bars={totals['bars']}")
        print(f"episodes={totals['episodes']} "
              f"by_asset={totals['episodes_by_asset']}")
        print(f"npz_bytes={totals['npz_bytes']} "
              f"wall_seconds={totals['wall_seconds']} workers={args.workers}")
        print(f"manifest={FZ.ZONES_ROOT / 'manifest.json'}")
    if args.stage in ("dist", "all"):
        print_distributions(distributions(assets))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
