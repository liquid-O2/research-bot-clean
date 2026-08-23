#!/usr/bin/env python3
"""The exact diagnosis — ticket 50 (2026-08-23).

"We keep getting nulls" is not a diagnosis. This probe forces the failure to name
itself by measuring the three things that discriminate between them, plus the
one structural question about the hold.

  (S) SELECTION   events pay on average and we pick badly.
                  Discriminator: mean y over events > 0, and enter-all banks well.
  (P) PAYOFF      the events do not pay; one wins and the rest sink the book.
                  Discriminator: mean y over events <= 0 while the max is large.
  (C) CAPACITY    events pay, selection is adequate, and the entries we are
                  allowed cannot reach the rung whatever we pick.
                  Discriminator: rung / entries-per-day > the best per-trade
                  dollar available.

  (H) THE HOLD    ticket 28's hold fires when NO newer name has beaten the
                  running extreme for H seconds. By construction the price has
                  therefore NOT gone further in the extending direction — so the
                  hold enters at a price at or WORSE than the payer's own, and
                  the retracement it waits through is the front of the very move
                  it wanted. This measures that retracement in dollars.

Every number is at DELTA_SEC of age, where the label is exact. No proxy.

Selftest: python3 tools/probe_entry_economics.py --selftest
Real:     OMP_NUM_THREADS=1 python3 tools/probe_entry_economics.py \
            --matrix-dir <component_matrix> --out <receipt.json>
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

import numpy as np

os.environ.setdefault("OMP_NUM_THREADS", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from probe_extreme_events import extreme_events  # noqa: E402
from probe_hold_running_extreme import (  # noqa: E402
    PHASE_VWAP_COL, _cash_flag, _cash_stats, _cell_groups, _hold_walk, _plant,
    _stage_a,
)
from probe_location_family_screen import _col  # noqa: E402
from probe_path_dedup import PHASE_ELAPSED_COL, _formation_sec  # noqa: E402
from probe_path_dedup_live import DELTA_SEC, FORM_DELTA, SIDE_COL, VWAP_COL  # noqa: E402
from probe_rho_on_dedup import WIDTH_MULT, _keep_idx  # noqa: E402
from probe_rho_ruler import BLOCKS, PHASE_REMAINING_COL, RUNG_USD  # noqa: E402
from probe_trained_accrual import ELAPSED_COL, ProbeRefusal, load_delta_rows  # noqa: E402

SCHEMA = "QRE2ENTRYECON1"
SCORE_COLS = (("session", VWAP_COL), ("phase", PHASE_VWAP_COL))
HOLD_H_SEC = 7200.0


def event_payoff(y: np.ndarray, is_event: np.ndarray, cell: np.ndarray) -> dict:
    """(S) vs (P): does an event pay on average, or only its best member?"""
    ev = y[is_event]
    ev = ev[np.isfinite(ev)]
    if not len(ev):
        return {"n_events": 0}
    ranks: dict[int, list[float]] = {}
    for g in _cell_groups(cell):
        gi = g[is_event[g]]
        vals = np.sort(y[gi][np.isfinite(y[gi])])[::-1]
        for r, v in enumerate(vals):
            ranks.setdefault(r, []).append(float(v))
    return {
        "n_events": int(len(ev)),
        "mean_usd": float(np.mean(ev)),
        "median_usd": float(np.median(ev)),
        "frac_positive": float(np.mean(ev > 0)),
        "p90_usd": float(np.percentile(ev, 90)),
        "sum_usd": float(np.sum(ev)),
        "by_rank_mean_usd": {str(r): float(np.mean(v)) for r, v in sorted(ranks.items())[:8]},
        "by_rank_n": {str(r): len(v) for r, v in sorted(ranks.items())[:8]},
    }


def hold_retracement(y, side, score, cell, formed, close, elapsed,
                     long_min: bool, short_min: bool, h_sec: float) -> dict:
    """(H): how much worse is the hold's entry price than the payer's own?

    The hold fires only when nothing has beaten the running extreme for h_sec, so
    at fire time the most extreme available price is the extreme's OWN, set
    h_sec earlier. Any name eligible in between is by definition LESS extreme.
    The gap between the extreme's score and the best score still on the table at
    fire time is the retracement the hold sits through, in the same USD units as
    the score.
    """
    flag, fired = _hold_walk(formed, side, score, cell, h_sec, close,
                             long_min, short_min)
    eligible = formed + DELTA_SEC
    gaps, held_y, best_y = [], [], []
    for g in _cell_groups(cell):
        pick = g[flag[g]]
        if not len(pick):
            continue
        i = int(pick[0])
        t_fire = float(fired[i])
        if not np.isfinite(t_fire):
            continue
        # Names of the same side eligible at or before the fire moment, excluding
        # the extreme itself: the prices actually available when the hold fires.
        same = g[((side[g] > 0) == (side[i] > 0)) & (eligible[g] <= t_fire + 1e-9)]
        same = same[same != i]
        s_ok = same[np.isfinite(score[same])]
        if len(s_ok):
            take_min = long_min if side[i] > 0 else short_min
            avail = float(np.min(score[s_ok]) if take_min else np.max(score[s_ok]))
            gaps.append(abs(float(score[i]) - avail))
        held_y.append(float(y[i]))
        gi = g[np.isfinite(y[g])]
        if len(gi):
            best_y.append(float(np.max(y[gi])))
    return {
        "n_fires": len(held_y),
        "retracement_median_usd": float(np.median(gaps)) if gaps else None,
        "retracement_mean_usd": float(np.mean(gaps)) if gaps else None,
        "retracement_p90_usd": float(np.percentile(gaps, 90)) if gaps else None,
        "held_pick_mean_y_usd": float(np.mean(held_y)) if held_y else None,
        "cell_best_mean_y_usd": float(np.mean(best_y)) if best_y else None,
    }


def run(matrix_dir: Path, out_path: Path, *, blocks=BLOCKS, log=print) -> dict:
    rows180 = load_delta_rows(matrix_dir, deltas=(DELTA_SEC,))
    rows0 = load_delta_rows(matrix_dir, deltas=(FORM_DELTA,))
    if not np.isfinite(rows180.y).all():
        raise ProbeRefusal("non-finite y on the component matrix")
    names = rows180.feature_names
    rng = np.random.default_rng(20260823)
    report: dict = {"schema": SCHEMA, "prereg": __doc__,
                    "matrix_receipt": rows180.matrix_receipt, "assets": {}}

    for asset in sorted(set(rows180.asset.tolist())):
        if asset not in WIDTH_MULT:
            continue
        rung = RUNG_USD[asset]
        entry: dict = {"rung_usd": rung}
        report["assets"][asset] = entry
        for bname, (lo, hi) in blocks.items():
            idx = np.flatnonzero((rows180.asset == asset) & (rows180.day >= lo)
                                 & (rows180.day <= hi) & (rows180.delta == DELTA_SEC))
            if len(idx) == 0:
                continue
            kept = _keep_idx(rows180, rows0, idx, asset)
            y = rows180.y[kept]; cell = rows180.cell[kept]; day = rows180.day[kept]
            elapsed = rows180.elapsed[kept]; occupancy = rows180.occupancy[kept]
            side = rows180.x[kept, _col(names, SIDE_COL)].astype(np.float64)
            formed = _formation_sec(rows180.x[kept], names)
            pe = PHASE_ELAPSED_COL if PHASE_ELAPSED_COL in names else ELAPSED_COL
            close = (rows180.x[kept, _col(names, pe)].astype(np.float64)
                     + rows180.x[kept, _col(names, PHASE_REMAINING_COL)].astype(np.float64))
            days = sorted({int(d) for d in day})
            if bname == "train":
                best = None
                for tag, _c in SCORE_COLS:
                    blk = _stage_a(y, side, rows180.x[kept, _col(names, _c)].astype(np.float64),
                                   cell, day, elapsed, occupancy, days, rung, rng, 8)
                    if best is None or blk["vwap_better_usd"] > best[2]["vwap_better_usd"]:
                        best = (tag, _c, blk)
                tag, colname, ablk = best
                entry["chosen_score"] = tag
                entry["orientation"] = ablk["best_orientation"]
            colname = dict(SCORE_COLS)[entry["chosen_score"]]
            score = rows180.x[kept, _col(names, colname)].astype(np.float64)
            long_min = entry["orientation"].startswith("long_min")
            short_min = entry["orientation"].endswith("short_min")
            ev, _, _ = extreme_events(formed, side, score, cell, long_min, short_min)

            pay = event_payoff(y, ev, cell)
            all_ev = _cash_stats(ev, y, cell, day, elapsed, occupancy, days)
            per_day_entries = [int(np.sum(ev & (day == d))) for d in days]
            hold = hold_retracement(y, side, score, cell, formed, close, elapsed,
                                    long_min, short_min, HOLD_H_SEC)
            n_cells_per_day = float(np.mean([len(set(cell[day == d].tolist())) for d in days]))
            entry[bname] = {
                "event_payoff": pay,
                "enter_all_events": {**all_ev,
                                     "entries_per_day_mean": float(np.mean(per_day_entries)),
                                     "entries_per_day_max": int(max(per_day_entries))},
                "cells_per_day_mean": n_cells_per_day,
                "usd_per_trade_needed_at_1_per_cell": rung / n_cells_per_day if n_cells_per_day else None,
                "hold_retracement": hold,
            }
            log(f"{asset:4s} {bname:10s} events n={pay['n_events']:5d} "
                f"mean ${pay.get('mean_usd', 0):7.1f} median ${pay.get('median_usd', 0):7.1f} "
                f"pos {100*pay.get('frac_positive', 0):4.1f}% | enter-all "
                f"${all_ev['usd_per_asset_day']:7.0f}/day at "
                f"{np.mean(per_day_entries):.1f} trades | need "
                f"${rung / n_cells_per_day:6.0f}/trade at 1/cell")
            log(f"{asset:4s} {bname:10s} HOLD retracement median "
                f"${hold['retracement_median_usd'] or 0:7.1f} p90 "
                f"${hold['retracement_p90_usd'] or 0:7.1f} | held pick mean y "
                f"${hold['held_pick_mean_y_usd'] or 0:7.1f} vs cell best "
                f"${hold['cell_best_mean_y_usd'] or 0:7.1f}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=1, sort_keys=True))
    return report


def selftest() -> int:
    y = np.array([100.0, -20.0, 50.0, -10.0])
    ev = np.array([True, True, True, False])
    cell = np.array([1, 1, 2, 2])
    p = event_payoff(y, ev, cell)
    assert p["n_events"] == 3, p
    assert abs(p["mean_usd"] - (100 - 20 + 50) / 3) < 1e-9, p
    assert abs(p["frac_positive"] - 2 / 3) < 1e-9, p
    # rank 0 is the best of each cell: 100 in cell 1, 50 in cell 2 -> mean 75
    assert abs(p["by_rank_mean_usd"]["0"] - 75.0) < 1e-9, p["by_rank_mean_usd"]
    assert abs(p["by_rank_mean_usd"]["1"] - (-20.0)) < 1e-9, p["by_rank_mean_usd"]
    assert event_payoff(y, np.zeros(4, bool), cell)["n_events"] == 0

    # Retracement: a cell where the extreme is set early and a less extreme name
    # arrives later. The gap between them is what the hold sits through.
    formed = np.array([0.0, 100.0, 5000.0])
    side = np.ones(3)
    score = np.array([-900.0, -400.0, -100.0])
    cell3 = np.array([5, 5, 5])
    close = np.full(3, 100000.0)
    h = hold_retracement(np.array([10.0, 20.0, 30.0]), side, score, cell3, formed,
                         close, formed, True, True, 300.0)
    assert h["n_fires"] == 1, h
    assert abs(h["retracement_median_usd"] - 500.0) < 1e-9, h
    print("selftest OK: event payoff by rank exact on a planted cell, empty event "
          "set handled, hold retracement measures the gap to the best price still "
          "available when it fires")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--matrix-dir", type=Path)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.matrix_dir is None or a.out is None:
        ap.error("--matrix-dir and --out are required unless --selftest")
    run(a.matrix_dir, a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
