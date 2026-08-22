#!/usr/bin/env python3
"""Prefix ceiling after waiting — ticket 27 (2026-08-22).

PREREGISTRATION (written before the real run; echoed into the receipt):
- After live keep-first, wait W seconds after the first name's
  formation. Oracle among names already born: max y in that prefix.
  Not a model. Uses later y of those names, never names not yet born.
- Grid W = 0, 300, 600, 1800, 2400, 3600, inf (full cell-max).
- Publish $/asset-day, capture vs inf, frac cells whose cell-max is
  already born, and whether W=2400 clears the rung on TRAIN.
- Matched null: not required for a ceiling ruler. W=0 must match
  ticket 25 enter-first. W=inf must match ticket 25 cell-max.
- 2021 cannot promote. No CatBoost. Generator untouched.

Selftest: python3 tools/probe_wait_prefix_ceiling.py --selftest
Real:     OMP_NUM_THREADS=1 python3 tools/probe_wait_prefix_ceiling.py \\
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
from probe_crux_prefix_winner import _usd  # noqa: E402
from probe_path_dedup import _formation_sec, _theta  # noqa: E402
from probe_path_dedup_live import DELTA_SEC, FORM_DELTA, SIDE_COL, VWAP_COL  # noqa: E402
from probe_rho_on_dedup import WIDTH_MULT, _keep_idx  # noqa: E402
from probe_rho_ruler import BLOCKS, RUNG_USD, _cell_groups  # noqa: E402
from probe_trained_accrual import (  # noqa: E402
    ELAPSED_COL, ProbeRefusal, load_delta_rows,
)
from probe_rho_ruler import PHASE_REMAINING_COL  # noqa: E402

SCHEMA = "QRE2WAITCEIL1"
WAIT_SEC = (0.0, 300.0, 600.0, 1800.0, 2400.0, 3600.0)


def _prefix_pick(y: np.ndarray, formed: np.ndarray, cell: np.ndarray,
                 wait: float | None) -> np.ndarray:
    score = np.full(len(y), -np.inf)
    for g in _cell_groups(cell):
        first = float(formed[g].min())
        if wait is None:
            mask = np.ones(len(g), bool)
        else:
            mask = formed[g] <= first + wait + 1e-9
        if not np.any(mask):
            continue
        gi = g[mask]
        score[int(gi[np.argmax(y[gi])])] = 1.0
    return score


def _winner_born(y: np.ndarray, formed: np.ndarray, cell: np.ndarray,
                 wait: float) -> float:
    hits = []
    for g in _cell_groups(cell):
        first = float(formed[g].min())
        wi = int(g[np.argmax(y[g])])
        hits.append(float(formed[wi] <= first + wait + 1e-9))
    return float(np.mean(hits)) if hits else float("nan")


def _block(y, cell, day, elapsed, occupancy, formed, rung: float) -> dict:
    days = sorted({int(d) for d in day})
    inf_usd = _usd(_prefix_pick(y, formed, cell, None), y, cell, day,
                   elapsed, occupancy, days)
    grid = []
    for w in WAIT_SEC:
        usd = _usd(_prefix_pick(y, formed, cell, w), y, cell, day,
                   elapsed, occupancy, days)
        born = _winner_born(y, formed, cell, w)
        grid.append({
            "wait_sec": w,
            "usd_per_asset_day": usd,
            "capture_of_cell_max": (usd / inf_usd) if inf_usd else float("nan"),
            "frac_winner_born": born,
            "clears_rung": bool(usd >= rung),
        })
    inf_row = {
        "wait_sec": None,
        "usd_per_asset_day": inf_usd,
        "capture_of_cell_max": 1.0,
        "frac_winner_born": 1.0,
        "clears_rung": bool(inf_usd >= rung),
    }
    at2400 = next(r for r in grid if r["wait_sec"] == 2400.0)
    return {
        "days": len(days), "rung_usd": float(rung),
        "cell_max_usd": float(inf_usd),
        "grid": grid + [inf_row],
        "wait_2400_usd": at2400["usd_per_asset_day"],
        "wait_2400_capture": at2400["capture_of_cell_max"],
        "wait_2400_frac_winner_born": at2400["frac_winner_born"],
        "wait_2400_clears_rung": at2400["clears_rung"],
    }


def run(matrix_dir: Path, out_path: Path, *, blocks=BLOCKS, log=print) -> dict:
    rows180 = load_delta_rows(matrix_dir, deltas=(DELTA_SEC,))
    rows0 = load_delta_rows(matrix_dir, deltas=(FORM_DELTA,))
    if not np.isfinite(rows180.y).all():
        raise ProbeRefusal(
            f"{int(np.sum(~np.isfinite(rows180.y)))} non-finite y; expected all finite USD")
    names = rows180.feature_names
    all_days = (int(rows180.day.min()), int(rows180.day.max()))
    report: dict = {
        "schema": SCHEMA, "prereg": __doc__, "matrix_receipt": rows180.matrix_receipt,
        "delta_sec": DELTA_SEC, "width_mult": WIDTH_MULT, "wait_sec": list(WAIT_SEC),
        "blocks": {**{k: list(v) for k, v in blocks.items()}, "all": list(all_days)},
        "assets": {},
    }
    for asset in sorted(set(rows180.asset.tolist())):
        if asset not in WIDTH_MULT:
            continue
        report["assets"][asset] = {"rung_usd": RUNG_USD[asset], "width_mult": WIDTH_MULT[asset]}
        for bname, (lo, hi) in {**blocks, "all": all_days}.items():
            idx = np.flatnonzero(
                (rows180.asset == asset) & (rows180.day >= lo) & (rows180.day <= hi)
                & (rows180.delta == DELTA_SEC))
            if len(idx) == 0:
                continue
            kept = _keep_idx(rows180, rows0, idx, asset)
            blk = _block(rows180.y[kept], rows180.cell[kept], rows180.day[kept],
                         rows180.elapsed[kept], rows180.occupancy[kept],
                         _formation_sec(rows180.x[kept], names), RUNG_USD[asset])
            report["assets"][asset][bname] = blk
            log(f"{asset:4s} {bname:10s} w0={blk['grid'][0]['usd_per_asset_day']:.0f} "
                f"w2400={blk['wait_2400_usd']:.0f} cap={blk['wait_2400_capture']:.2f} "
                f"born={blk['wait_2400_frac_winner_born']:.2f} "
                f"max={blk['cell_max_usd']:.0f} rung={blk['wait_2400_clears_rung']}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=1, sort_keys=True))
    return report


def _plant(root: Path, *, mode: str = "ok") -> None:
    from probe_trained_accrual import ELAPSED_COL
    names = ["min_alert_age_sec", "phase_index", ELAPSED_COL,
             "disc_fvol_phase_scope_elapsed_sec", PHASE_REMAINING_COL, VWAP_COL, SIDE_COL]
    theta = _theta("HG")
    specs = [
        (400.0, 280.0, 0.0),
        (2500.0, 480.0, 8.0 * theta),
        (100.0, 680.0, 16.0 * theta),
    ]
    xs, days, assets, series, ys, occs = [], [], [], [], [], []
    for d in (20210610, 20210611):
        for s, (yv, el180, vwap) in enumerate(specs):
            for age in (0.0, 180.0):
                elapsed = el180 - 180.0 + age
                xs.append([age, 0.0, elapsed, elapsed, 10000.0 - elapsed, vwap, 1.0])
                days.append(d); assets.append("HG"); series.append(f"s{d}_{s}")
                ys.append(yv); occs.append(600.0)
    root.mkdir(parents=True, exist_ok=True)
    yv = np.asarray(ys, np.float64)
    if mode == "nan":
        yv[1] = np.nan
    np.save(root / "x.npy", np.asarray(xs, np.float32))
    np.save(root / "day.npy", np.asarray(days, np.int64))
    np.save(root / "asset.npy", np.asarray(assets))
    np.save(root / "series_id.npy", np.asarray(series))
    np.save(root / "current_asinh.npy", np.arcsinh(yv / 600.0))
    np.save(root / "occupancy_sec.npy", np.asarray(occs, np.float64))
    (root / "manifest.json").write_text(json.dumps(
        {"feature_names": names, "rows": len(xs), "matrix_receipt_sha256": "synthetic"}))


def selftest() -> int:
    blocks = {"train": (20210610, 20210709)}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _plant(tmp / "p")
        rep = run(tmp / "p", tmp / "p.json", blocks=blocks, log=lambda *_: None)
        g = {r["wait_sec"]: r for r in rep["assets"]["HG"]["train"]["grid"]}
        assert abs(g[0.0]["usd_per_asset_day"] - 400.0) < 1.0, g[0.0]
        assert abs(g[300.0]["usd_per_asset_day"] - 2500.0) < 1.0, g[300.0]
        inf = next(r for r in rep["assets"]["HG"]["train"]["grid"] if r["wait_sec"] is None)
        assert abs(inf["usd_per_asset_day"] - 2500.0) < 1.0, inf
        _plant(tmp / "red", mode="nan")
        try:
            run(tmp / "red", tmp / "red.json", blocks=blocks, log=lambda *_: None)
        except ProbeRefusal as exc:
            assert "non-finite" in str(exc), exc
        else:
            raise AssertionError("NaN y was accepted")
    print("selftest OK: W=0 cashes 400, W=300 cashes 2500, NaN refused")
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
