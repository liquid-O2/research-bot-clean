#!/usr/bin/env python3
"""Acceptance gate: rebuild every EXPLORE-day B5 trade from the substrate.

The B5 block is strict-loaded through the engine loader; each of its trades on
an EXPLORE day must be reproduced end to end out of the cached mill arrays --
timer, roster, argmax side with the candidate-id tie-break, timer quote,
frozen cost, generation, outcome -- and must agree on PnL to the cent, exit
timestamp, and wall/phase-close disposition.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
from typing import Mapping, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from engine.entry_v2 import common as C
from engine.entry_v2.confirmation_types import NANOS_PER_SECOND, _ceil_second
from engine.entry_v2.tabular_evaluation_policy import load_policy_block_result
from engine.entry_v2.tabular_recovery_contracts import RecoveryConfig

import mill as M

BLOCK_PATH = ROOT / (
    "artifacts/entry_v2/tabular_recovery/threshold/b5_common_clock_2400/real/raw_block.json")
SPLIT_PATH = ROOT / ".audit/mill-split.json"
AGE_SECONDS = 2400


def _opportunity_id(cell_text: str, timer: int, side: int, bid: int, ask: int,
                    cutoff: int) -> str:
    digest = C.object_sha256({"schema": "QRE2B5OPPORTUNITY1", "cell": cell_text,
                              "timer": timer, "side": side, "bid": bid, "ask": ask,
                              "cutoff": cutoff})
    return f"QRE2B5-{digest}"


def reproduce_shard(shard: M.Shard) -> dict[str, dict[str, object]]:
    """The B5 common-clock pipeline over one shard, from cached arrays alone."""

    out: dict[str, dict[str, object]] = {}
    for cell in shard.cells:
        timer = _ceil_second(cell.first_formation_ts_ns) + AGE_SECONDS * NANOS_PER_SECOND
        if timer >= cell.phase_close_ts_ns:
            continue
        index = shard.index(cell.quality_idx)
        quote = index.current(timer)
        if quote is None:
            continue
        bid, ask, mid2 = quote
        if not 0 < bid < ask or bid + ask != mid2:
            raise M.MillRefusal(f"timer prefix quote differs: {cell.text}")
        roster = shard.roster(cell, timer)
        if not roster:
            raise M.MillRefusal(f"formed roster is empty: {cell.text}")
        leader = min(roster, key=lambda row: (
            -(int(shard.side[row]) * (mid2 - int(shard.entry_mid2[row]))),
            shard.candidate_ids[row]))
        side = int(shard.side[leader])
        cost = M.frozen_cost_usd_exact(bid, ask, shard.asset)
        generation = index.generation_at_snapshot(timer)
        cutoff = int(np.searchsorted(
            shard.raw_ts.view(np.uint64), np.uint64(timer), side="left"))
        outcome = index.outcome(timer, side, mid2, cost, cell.phase_close_ts_ns,
                                generation=generation)
        opportunity = _opportunity_id(cell.text, timer, side, bid, ask, cutoff)
        out[opportunity] = {
            "cell": cell.text, "asset": shard.asset, "d8": shard.d8,
            "timer": timer, "side": side, "bid": bid, "ask": ask, "mid2": mid2,
            "cost": cost, "generation": generation, "roster": len(roster),
            "lineage": min(shard.candidate_ids[row] for row in roster
                           if int(shard.side[row]) == side),
            "cert": None if outcome is None else float(outcome.cert_close_usd),
            "exit_ts_ns": None if outcome is None else int(outcome.exit_ts_ns),
            "wall_hit": None if outcome is None else bool(outcome.wall_hit),
        }
    return out


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(M.MILL_ROOT))
    parser.add_argument("--limit-report", type=int, default=5)
    args = parser.parse_args(argv)
    split = json.loads(SPLIT_PATH.read_text())
    explore = {(asset, int(day)) for asset, days in split["explore"].items()
               for day in days}
    started = time.monotonic()
    block = load_policy_block_result(BLOCK_PATH, config=RecoveryConfig())
    trades = tuple(row for row in block.evidence.evaluation.trade_results
                   if (row.asset, int(row.trading_day)) in explore)
    by_day: dict[tuple[str, int], list] = {}
    for trade in trades:
        by_day.setdefault((trade.asset, int(trade.trading_day)), []).append(trade)
    matched = 0
    problems: list[str] = []
    for (asset, d8), day_trades in sorted(by_day.items()):
        shard = M.load_shard(asset, d8, root=Path(args.root))
        try:
            table = reproduce_shard(shard)
        finally:
            shard.close()
        for trade in sorted(day_trades, key=lambda row: row.entry_ts_ns):
            got = table.get(trade.candidate_id)
            if got is None:
                problems.append(
                    f"{asset}/{d8} entry={trade.entry_ts_ns} "
                    f"{trade.candidate_id[:20]}: no reproduced opportunity")
                continue
            if got["asset"] != trade.asset or got["d8"] != int(trade.trading_day) \
                    or got["timer"] != int(trade.entry_ts_ns):
                problems.append(
                    f"{got['cell']}: identity differs timer={got['timer']} "
                    f"block_entry={trade.entry_ts_ns}")
                continue
            if got["cert"] is None:
                problems.append(f"{got['cell']}: substrate has no certifiable suffix")
                continue
            wall_block = trade.exit_reason.value == "WALL"
            if round(float(got["cert"]), 2) != round(float(trade.pnl_usd), 2):
                problems.append(
                    f"{got['cell']}: cert={got['cert']:.6f} block={trade.pnl_usd:.6f}")
                continue
            if int(got["exit_ts_ns"]) != int(trade.exit_ts_ns):
                problems.append(
                    f"{got['cell']}: exit={got['exit_ts_ns']} "
                    f"block={trade.exit_ts_ns}")
                continue
            if bool(got["wall_hit"]) != wall_block:
                problems.append(
                    f"{got['cell']}: wall={got['wall_hit']} "
                    f"block_reason={trade.exit_reason.value}")
                continue
            matched += 1
    wall = time.monotonic() - started
    if problems or matched != len(trades):
        print(f"B5_REPRO FAIL matched={matched} explore_trades={len(trades)} "
              f"problems={len(problems)} wall={wall:.1f}s")
        for line in problems[:max(1, int(args.limit_report))]:
            print(f"  {line}")
        return 1
    print(f"B5_REPRO PASS n={matched}")
    print(f"  explore_asset_days_with_trades={len(by_day)} "
          f"block_trades_total={len(block.evidence.evaluation.trade_results)} "
          f"wall={wall:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
