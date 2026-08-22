#!/usr/bin/env python3
"""Location-watch — ticket 17 (2026-08-22).

PREREGISTRATION (written before the real run; echoed into the receipt):
- Question: does treating a location as a WATCH (event, then G1 names
  formed in the window) keep the cell-max, unlike |aligned|<=θ at
  formation price (ticket 11 leftover 83/73/52%)?
- Generator is zigzag reversal only (g1.cpp RawZigZag). Continuation
  is a selection window on those zigzags, not a new birth family.
  "IV low" is prior VAL. IB low is a sibling, screened alone.
- On-matrix slice (no entry_mid2 on the component matrix, so prior-VAL
  tape windows cannot run yet). Families one at a time:
    ib_v_reclaim: opposing IB break and currently inside IB
    ib_break_hold: directional IB break and not reentry
    ib_formed_after_break: directional IB break and age <= break_age
    value_v_reclaim / value_break_hold / value_formed_after_escape:
      the same three shapes on phase value (LIVE, not S0)
- Bars: TRAIN retained_fraction >= 0.70 and median names <= 16.
  Occupancy vs 200-draw within-cell shuffle. 2021 cannot promote.
- Kill: TRAIN shrink below the rung AND occupancy inside shuffle,
  per family, never a null of "location".

Selftest: python3 tools/probe_location_watch.py --selftest
Real:     OMP_NUM_THREADS=1 python3 tools/probe_location_watch.py \\
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
from probe_location_family_screen import _col  # noqa: E402
from probe_oracle_retention_filters import _score_mask  # noqa: E402
from probe_rho_ruler import BLOCKS, RUNG_USD  # noqa: E402
from probe_trained_accrual import (  # noqa: E402
    ProbeRefusal, _synthetic_matrix, load_delta_rows,
)

SCHEMA = "QRE2LOCWATCH1"
N_DRAW = 200
MAJORITY = 0.70
MAX_NAMES = 16.0
DELTA_SEC = 180.0
AGE_COL = "min_alert_age_sec"
LIVE = frozenset({
    "value_v_reclaim", "value_break_hold", "value_formed_after_escape",
})
WATCHES = (
    "ib_v_reclaim",
    "ib_break_hold",
    "ib_formed_after_break",
    "value_v_reclaim",
    "value_break_hold",
    "value_formed_after_escape",
)
COLS = (
    "disc_ib_phase_opposing_break_seen",
    "disc_ib_phase_inside",
    "disc_ib_phase_directional_break_seen",
    "disc_ib_phase_directional_break_reentry_seen",
    "disc_ib_phase_directional_break_age_sec",
    "disc_auction_phase_opposing_escape_time_fraction",
    "disc_auction_phase_inside_value",
    "disc_auction_phase_directional_escape_current_run_sec",
    "disc_auction_phase_failed_directional_auction",
    "disc_auction_phase_directional_escape_episodes",
    "disc_auction_phase_directional_escape_age_sec",
)


def _gt(x: np.ndarray, names: list[str], col: str, thresh: float = 0.5) -> np.ndarray:
    return x[:, _col(names, col)].astype(np.float64) > thresh


def _le_age(x: np.ndarray, names: list[str], age_col: str, clock_col: str) -> np.ndarray:
    age = x[:, _col(names, AGE_COL)].astype(np.float64)
    clock = x[:, _col(names, clock_col)].astype(np.float64)
    return np.isfinite(age) & np.isfinite(clock) & (age <= clock)


def watch_mask(x: np.ndarray, names: list[str], watch: str) -> np.ndarray:
    if watch == "ib_v_reclaim":
        return (_gt(x, names, "disc_ib_phase_opposing_break_seen")
                & _gt(x, names, "disc_ib_phase_inside"))
    if watch == "ib_break_hold":
        return (_gt(x, names, "disc_ib_phase_directional_break_seen")
                & ~_gt(x, names, "disc_ib_phase_directional_break_reentry_seen"))
    if watch == "ib_formed_after_break":
        return (_gt(x, names, "disc_ib_phase_directional_break_seen")
                & _le_age(x, names, AGE_COL, "disc_ib_phase_directional_break_age_sec"))
    if watch == "value_v_reclaim":
        return (_gt(x, names, "disc_auction_phase_opposing_escape_time_fraction", 0.0)
                & _gt(x, names, "disc_auction_phase_inside_value"))
    if watch == "value_break_hold":
        return (_gt(x, names, "disc_auction_phase_directional_escape_current_run_sec", 0.0)
                & ~_gt(x, names, "disc_auction_phase_failed_directional_auction"))
    if watch == "value_formed_after_escape":
        return (_gt(x, names, "disc_auction_phase_directional_escape_episodes", 0.0)
                & _le_age(x, names, AGE_COL,
                          "disc_auction_phase_directional_escape_age_sec"))
    raise ProbeRefusal(f"unknown watch {watch!r}")


def run(matrix_dir: Path, out_path: Path, *, blocks=BLOCKS, n_draw: int = N_DRAW,
        log=print) -> dict:
    rows = load_delta_rows(matrix_dir, deltas=(DELTA_SEC,))
    if not np.isfinite(rows.y).all():
        raise ProbeRefusal(
            f"{int(np.sum(~np.isfinite(rows.y)))} non-finite y; expected all finite USD")
    for c in COLS:
        _col(rows.feature_names, c)
    all_days = (int(rows.day.min()), int(rows.day.max()))
    report: dict = {
        "schema": SCHEMA, "prereg": __doc__, "matrix_receipt": rows.matrix_receipt,
        "delta_sec": DELTA_SEC, "n_draw": n_draw, "majority": MAJORITY,
        "max_names": MAX_NAMES, "watches": list(WATCHES), "live": sorted(LIVE),
        "blocks": {**{k: list(v) for k, v in blocks.items()}, "all": list(all_days)},
        "assets": {},
    }
    for asset in sorted(set(rows.asset.tolist())):
        report["assets"][asset] = {"rung_usd": RUNG_USD[asset], "filters": {},
                                   "survivors": [], "letter": ""}
        for watch in WATCHES:
            tag = "live" if watch in LIVE else "finished_or_clock"
            report["assets"][asset]["filters"][watch] = {"tag": tag}
            for bname, (lo, hi) in {**blocks, "all": all_days}.items():
                idx = np.flatnonzero(
                    (rows.asset == asset) & (rows.day >= lo) & (rows.day <= hi)
                    & (rows.delta == DELTA_SEC))
                if len(idx) == 0:
                    continue
                flag = watch_mask(rows.x[idx], rows.feature_names, watch)
                block = _score_mask(rows, idx, flag, n_draw=n_draw, seed=0)
                report["assets"][asset]["filters"][watch][bname] = block
                log(f"{asset:4s} {watch:28s} {bname:10s} "
                    f"shrink={block['shrink_ceiling_usd_per_asset_day']:7.1f} "
                    f"ret={block['retained_fraction']:.2f} "
                    f"ncell={block['occupancy']['median_eligible_per_cell']:.1f} "
                    f"maj={int(block['majority_kept'])} cut={int(block['proper_cut'])}"
                    f"{'' if not block['typed'] else ' TYPED'}")
        ranked = []
        for watch in WATCHES:
            if watch in LIVE:
                continue
            tr = report["assets"][asset]["filters"][watch].get("train")
            if tr is None:
                continue
            if tr["majority_kept"] and tr["proper_cut"]:
                ranked.append((tr["shrink_ceiling_usd_per_asset_day"], watch))
        ranked.sort(reverse=True)
        report["assets"][asset]["survivors"] = [
            {"filter": f, "shrink_ceiling": s} for s, f in ranked]
        report["assets"][asset]["letter"] = (
            ranked[0][1] if ranked else "no majority-and-cut filter")
        if ranked:
            report["assets"][asset]["train_best_forward"] = (
                report["assets"][asset]["filters"][ranked[0][1]].get("forward"))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=1, sort_keys=True))
    return report


def _append_watch_cols(root: Path, *, plant: str | None) -> None:
    x = np.load(root / "x.npy")
    man = json.loads((root / "manifest.json").read_text())
    y = np.sinh(np.load(root / "current_asinh.npy")) * 600.0
    extra = np.zeros((len(x), len(COLS)), np.float32)
    day = np.load(root / "day.npy")
    series = np.asarray(np.load(root / "series_id.npy"), str)
    age = x[:, man["feature_names"].index("min_alert_age_sec")]
    phase = x[:, man["feature_names"].index("phase_index")]
    at_delta = np.abs(age - DELTA_SEC) <= 2.5
    cell = day.astype(np.int64) * 10 + np.nan_to_num(phase, nan=9).astype(np.int64)
    if plant:
        order = np.argsort(cell, kind="stable")
        keep = order[at_delta[order]]
        bounds = np.flatnonzero(np.diff(cell[keep])) + 1
        for grp in np.split(keep, bounds):
            if len(grp) == 0:
                continue
            win = grp[int(np.argmax(y[grp]))]
            rows = series == series[win]
            extra[rows, COLS.index("disc_ib_phase_opposing_break_seen")] = 1.0
            extra[rows, COLS.index("disc_ib_phase_inside")] = 1.0
            extra[rows, COLS.index("disc_ib_phase_directional_break_seen")] = 1.0
            extra[rows, COLS.index("disc_ib_phase_directional_break_age_sec")] = 400.0
    x = np.concatenate([x, extra], axis=1)
    man["feature_names"].extend(list(COLS))
    np.save(root / "x.npy", x)
    (root / "manifest.json").write_text(json.dumps(man))


def selftest() -> int:
    blocks = {"train": (20210601, 20210624), "forward": (20210601, 20210624)}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _synthetic_matrix(tmp / "planted", signal=True)
        _append_watch_cols(tmp / "planted", plant="ib_v_reclaim")
        planted = run(tmp / "planted", tmp / "planted.json", blocks=blocks, n_draw=40,
                      log=lambda *_: None)
        ib = planted["assets"]["HG"]["filters"]["ib_v_reclaim"]["train"]
        assert ib["occupancy"]["pick_rate"] > 0.99, ib
        after = planted["assets"]["HG"]["filters"]["ib_formed_after_break"]["train"]
        assert after["occupancy"]["pick_rate"] > 0.99, after
        _synthetic_matrix(tmp / "noise", signal=True, seed=11)
        _append_watch_cols(tmp / "noise", plant=None)
        noise = run(tmp / "noise", tmp / "noise.json", blocks=blocks, n_draw=40,
                    log=lambda *_: None)
        n = noise["assets"]["HG"]["filters"]["ib_v_reclaim"]["train"]["occupancy"]
        assert n["diff_inside_shuffle_band"], n
        _synthetic_matrix(tmp / "red", signal=True)
        _append_watch_cols(tmp / "red", plant="ib_v_reclaim")
        man = json.loads((tmp / "red" / "manifest.json").read_text())
        xred = np.load(tmp / "red" / "x.npy")
        age = xred[:, man["feature_names"].index("min_alert_age_sec")]
        hit = int(np.flatnonzero(np.abs(age - DELTA_SEC) <= 2.5)[0])
        cur = np.load(tmp / "red" / "current_asinh.npy"); cur[hit] = np.nan
        np.save(tmp / "red" / "current_asinh.npy", cur)
        try:
            run(tmp / "red", tmp / "red.json", blocks=blocks, n_draw=2, log=lambda *_: None)
        except ProbeRefusal as exc:
            assert "non-finite" in str(exc), exc
        else:
            raise AssertionError("red fixture (NaN y) was accepted")
    print("selftest OK: planted IB V pick_rate=1; formed-after-break planted; noise inside shuffle; NaN y refused")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--matrix-dir", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--n-draw", type=int, default=N_DRAW)
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.matrix_dir is None or a.out is None:
        ap.error("--matrix-dir and --out are required unless --selftest")
    run(a.matrix_dir, a.out, n_draw=a.n_draw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
