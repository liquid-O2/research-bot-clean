#!/usr/bin/env python3
"""Forward-vol vs oracle — ticket 19 (2026-08-22).

PREREGISTRATION (written before the real run; echoed into the receipt):
- Question: does the owned QRE2FORECAST4 HAR/OLS forecast (session-open
  sigma/range/q50, READY only) correlate with cell-oracle dollars, or
  with which G1 name wins inside a cell? Can it mint better candidates?
  Generator frozen (D-110): a forecast is a skip/scale on existing
  names, never a new birth family.
- Live join only: {asset}.qrf4.tsv READY rows. Do not open *.eval.tsv
  (diagnostics-only hindsight plane). availability is session open.
- 2021 matrix is expected to have typed-absent HAR columns. Receipt
  READY overlap with matrix days. If overlap is 0, the HAR forecast
  cannot be scored on this sample.
- Live vol-like columns that ARE on the plane: formation_atr_mean_usd,
  disc_fvol_{phase,session}_actual_range_usd,
  disc_fvol_{phase,session}_range_consumption_usd_per_min.
- Between-cell Spearman of cell-mean(col) vs cell-max y, 200 shuffles
  of cell-max across cells (destroys day/vol pairing). Within-cell
  Spearman vs y; cells where col is constant are typed cell-constant
  (cannot rank names).
- 2021 cannot promote. Dollars vs rung are not claimed from a Spearman.

Selftest: python3 tools/probe_fvol_oracle_join.py --selftest
Real:     OMP_NUM_THREADS=1 python3 tools/probe_fvol_oracle_join.py \\
            --matrix-dir <component_matrix> --forecast-dir <qrf4 dir> \\
            --out <receipt.json>
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import tempfile
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

os.environ.setdefault("OMP_NUM_THREADS", "1")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe_location_family_screen import _col  # noqa: E402
from probe_rho_ruler import BLOCKS, RUNG_USD, _cell_groups  # noqa: E402
from probe_trained_accrual import (  # noqa: E402
    ProbeRefusal, _synthetic_matrix, load_delta_rows,
)

SCHEMA = "QRE2FVOLORCL1"
N_DRAW = 200
DELTA_SEC = 180.0
HAR_ABSENT = (
    "disc_fvol_session_sigma_hat_usd",
    "disc_fvol_phase_sigma_hat_usd",
    "disc_fvol_session_move_q50_usd",
    "disc_fvol_phase_forecast_present",
)
LIVE_VOL = (
    "formation_atr_mean_usd",
    "disc_fvol_phase_actual_range_usd",
    "disc_fvol_session_actual_range_usd",
    "disc_fvol_phase_range_consumption_usd_per_min",
    "disc_fvol_session_range_consumption_usd_per_min",
)
PHASE_SEG = {0: "TOKYO", 1: "LONDON", 2: "NY"}


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    ok = np.isfinite(a) & np.isfinite(b)
    if int(ok.sum()) < 8:
        return float("nan")
    rho, _ = spearmanr(a[ok], b[ok])
    return float(rho)


def _between_cell(col: np.ndarray, y: np.ndarray, cell: np.ndarray,
                  n_draw: int, rng: np.random.Generator) -> dict:
    groups = _cell_groups(cell)
    mean_x = np.array([float(np.nanmean(col[g])) for g in groups], np.float64)
    max_y = np.array([float(np.max(y[g])) for g in groups], np.float64)
    const = float(np.mean([
        (np.nanmax(col[g]) - np.nanmin(col[g]) < 1e-9)
        if np.isfinite(col[g]).any() else True for g in groups]))
    rho = _spearman(mean_x, max_y)
    shuf = np.empty(n_draw, np.float64)
    for i in range(n_draw):
        shuf[i] = _spearman(mean_x, rng.permutation(max_y))
    lo, hi = float(np.nanquantile(shuf, 0.025)), float(np.nanquantile(shuf, 0.975))
    return {
        "n_cells": int(len(groups)),
        "frac_cells_constant": const,
        "spearman": rho,
        "shuffle_p025": lo,
        "shuffle_p975": hi,
        "inside_shuffle_band": bool(np.isfinite(rho) and lo <= rho <= hi),
        "typed": (["cell-constant cannot rank names"] if const > 0.90 else []),
    }


def _within_cell(col: np.ndarray, y: np.ndarray, cell: np.ndarray) -> dict:
    groups = _cell_groups(cell)
    rhos = []
    for g in groups:
        if np.nanmax(col[g]) - np.nanmin(col[g]) < 1e-9:
            continue
        r = _spearman(col[g], y[g])
        if np.isfinite(r):
            rhos.append(r)
    return {
        "n_cells_varying": int(len(rhos)),
        "median_spearman": float(np.median(rhos)) if rhos else float("nan"),
    }


def forecast_ready_overlap(forecast_dir: Path, asset: str, days: np.ndarray) -> dict:
    path = forecast_dir / f"{asset}.qrf4.tsv"
    if not path.is_file():
        raise ProbeRefusal(f"missing live forecast tsv {path}")
    uniq = {int(d) for d in days}
    ready_days: set[int] = set()
    n_rows = n_ready = 0
    with path.open() as fh:
        rows = csv.DictReader((ln for ln in fh if not ln.startswith("#")), delimiter="\t")
        for row in rows:
            n_rows += 1
            d8 = int(row["d8"])
            if row.get("status") == "READY":
                n_ready += 1
                if d8 in uniq:
                    ready_days.add(d8)
    return {
        "tsv": str(path),
        "n_tsv_rows": n_rows,
        "n_tsv_ready": n_ready,
        "n_matrix_days": int(len(uniq)),
        "n_overlap_ready_days": int(len(ready_days)),
        "first_overlap_d8": (min(ready_days) if ready_days else None),
        "last_overlap_d8": (max(ready_days) if ready_days else None),
    }


def run(matrix_dir: Path, out_path: Path, forecast_dir: Path, *,
        blocks=BLOCKS, n_draw: int = N_DRAW, log=print) -> dict:
    rows = load_delta_rows(matrix_dir, deltas=(DELTA_SEC,))
    if not np.isfinite(rows.y).all():
        raise ProbeRefusal(
            f"{int(np.sum(~np.isfinite(rows.y)))} non-finite y; expected all finite USD")
    present = [c for c in LIVE_VOL if c in rows.feature_names]
    absent_har = [c for c in HAR_ABSENT if c not in rows.feature_names]
    all_days = (int(rows.day.min()), int(rows.day.max()))
    report: dict = {
        "schema": SCHEMA, "prereg": __doc__, "matrix_receipt": rows.matrix_receipt,
        "delta_sec": DELTA_SEC, "n_draw": n_draw, "live_vol_present": present,
        "har_columns_absent": absent_har,
        "blocks": {**{k: list(v) for k, v in blocks.items()}, "all": list(all_days)},
        "assets": {},
    }
    for asset in sorted(set(rows.asset.tolist())):
        overlap = forecast_ready_overlap(
            forecast_dir, asset, rows.day[rows.asset == asset])
        report["assets"][asset] = {
            "rung_usd": RUNG_USD[asset], "forecast_overlap": overlap, "columns": {},
        }
        log(f"{asset:4s} READY overlap {overlap['n_overlap_ready_days']}/"
            f"{overlap['n_matrix_days']} days")
        for bname, (lo, hi) in {**blocks, "all": all_days}.items():
            idx = np.flatnonzero(
                (rows.asset == asset) & (rows.day >= lo) & (rows.day <= hi)
                & (rows.delta == DELTA_SEC))
            if len(idx) == 0:
                continue
            rng = np.random.default_rng(0)
            for col in present:
                x = rows.x[idx, _col(rows.feature_names, col)].astype(np.float64)
                between = _between_cell(x, rows.y[idx], rows.cell[idx], n_draw, rng)
                within = _within_cell(x, rows.y[idx], rows.cell[idx])
                report["assets"][asset]["columns"].setdefault(col, {})
                report["assets"][asset]["columns"][col][bname] = {
                    "between_cell": between, "within_cell": within,
                }
                log(f"{asset:4s} {col:44s} {bname:10s} "
                    f"btw={between['spearman']:.3f} "
                    f"const={between['frac_cells_constant']:.2f} "
                    f"win_n={within['n_cells_varying']} "
                    f"win_med={within['median_spearman']:.3f}"
                    f"{'' if not between['typed'] else ' TYPED'}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=1, sort_keys=True))
    return report


def _append_vol(root: Path, *, plant: bool) -> None:
    x = np.load(root / "x.npy")
    man = json.loads((root / "manifest.json").read_text())
    y = np.sinh(np.load(root / "current_asinh.npy")) * 600.0
    extra = np.zeros((len(x), len(LIVE_VOL)), np.float32)
    day = np.load(root / "day.npy")
    for i, d in enumerate(day):
        extra[i, 0] = 100.0 + 0.02 * float(d - 20210600)
    if plant:
        # Between-cell: ATR tracks day so it tracks planted y level.
        age = x[:, man["feature_names"].index("min_alert_age_sec")]
        extra[:, 0] = 50.0 + np.clip(y / 20.0, -20.0, 80.0)
        extra[np.abs(age - DELTA_SEC) > 2.5, 0] = 50.0
    x = np.concatenate([x, extra], axis=1)
    man["feature_names"].extend(list(LIVE_VOL))
    np.save(root / "x.npy", x)
    (root / "manifest.json").write_text(json.dumps(man))


def _tiny_forecast(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    header = "asset\td8\tsegment\tstatus\n"
    (root / "HG.qrf4.tsv").write_text(
        "# QRE2FORECAST4\n" + header
        + "HG\t20210601\tSESSION\tMISSING\n"
        + "HG\t20210610\tSESSION\tMISSING\n")


def selftest() -> int:
    blocks = {"train": (20210601, 20210624), "forward": (20210601, 20210624)}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _synthetic_matrix(tmp / "planted", signal=True)
        _append_vol(tmp / "planted", plant=True)
        fc = tmp / "fc"
        _tiny_forecast(fc)
        planted = run(tmp / "planted", tmp / "p.json", fc, blocks=blocks, n_draw=40,
                      log=lambda *_: None)
        btw = planted["assets"]["HG"]["columns"]["formation_atr_mean_usd"]["train"]["between_cell"]
        assert btw["spearman"] > btw["shuffle_p975"], btw
        assert planted["assets"]["HG"]["forecast_overlap"]["n_overlap_ready_days"] == 0
        _synthetic_matrix(tmp / "flat", signal=True, seed=3)
        _append_vol(tmp / "flat", plant=False)
        flat = run(tmp / "flat", tmp / "f.json", fc, blocks=blocks, n_draw=40,
                   log=lambda *_: None)
        fbtw = flat["assets"]["HG"]["columns"]["disc_fvol_phase_actual_range_usd"]["train"]["between_cell"]
        assert fbtw["frac_cells_constant"] > 0.90, fbtw
        _synthetic_matrix(tmp / "red", signal=True)
        _append_vol(tmp / "red", plant=True)
        man = json.loads((tmp / "red" / "manifest.json").read_text())
        xred = np.load(tmp / "red" / "x.npy")
        age = xred[:, man["feature_names"].index("min_alert_age_sec")]
        hit = int(np.flatnonzero(np.abs(age - DELTA_SEC) <= 2.5)[0])
        cur = np.load(tmp / "red" / "current_asinh.npy"); cur[hit] = np.nan
        np.save(tmp / "red" / "current_asinh.npy", cur)
        try:
            run(tmp / "red", tmp / "r.json", fc, blocks=blocks, n_draw=2, log=lambda *_: None)
        except ProbeRefusal as exc:
            assert "non-finite" in str(exc), exc
        else:
            raise AssertionError("red fixture (NaN y) was accepted")
    print("selftest OK: planted ATR/y Spearman above shuffle; READY overlap 0; constant typed; NaN y refused")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--matrix-dir", type=Path)
    ap.add_argument("--forecast-dir", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--n-draw", type=int, default=N_DRAW)
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.matrix_dir is None or a.forecast_dir is None or a.out is None:
        ap.error("--matrix-dir --forecast-dir --out required unless --selftest")
    run(a.matrix_dir, a.out, a.forecast_dir, n_draw=a.n_draw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
