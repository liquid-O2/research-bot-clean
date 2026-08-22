#!/usr/bin/env python3
"""Delay-forfeit curve (D5 / catalog Part D item 3).

PREREGISTRATION (before the real run; echoed into the receipt):
- Question: how many ceiling dollars does WAITING cost? If entry into each
  (asset, day, phase) cell may only happen at candidate age >= Delta seconds, what
  fraction of the cell's best available standalone value survives?
- V(cell, Delta) = max over ALL series in the cell of max(y at sampled rows with
  min_alert_age_sec in [Delta, 300]). The delayed decision may switch to a different
  series — the wait forfeits only what no candidate can still offer.
- Population: goal-grade cells only (V(cell, 0) >= $600) — the cells the ladder is made
  of (A7: the optimum is <=1 entry per (asset, phase)).
- Metric per (asset, Delta in {0,30,60,120,180,300}): mean over cells of
  V(Delta)/V(0) (capture retained), mean dollar forfeit V(0)-V(Delta), and the fraction
  of cells with NO row at age>=Delta (candidate pool expired before the wait ended —
  counted as full forfeit AND reported separately: the matrix samples only to 300s, so
  expiry here is a sampling floor as much as a market fact).
- CI: day-level bootstrap (200 draws). Diagnostic tier — replay remains the only
  authoritative dollar number.

Selftest: python3 tools/probe_delay_forfeit.py --selftest
Real:     python3 tools/probe_delay_forfeit.py --matrix-dir <component_matrix> --out <json>
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

# 290 (not 300): sampled ages top out at 299.99, so age>=300 matches nothing —
# the earlier 300 row read 0.0 retention as a pure sampling artifact.
DELTAS = (0.0, 30.0, 60.0, 120.0, 180.0, 240.0, 290.0)
GOAL_MIN_USD = 600.0
VALUE_SCALE_USD = 600.0


def run(matrix_dir: Path, out_path: Path, *, n_boot: int = 200,
        seed: int = 20260822) -> dict:
    manifest = json.loads((matrix_dir / "manifest.json").read_text())
    names = list(manifest["feature_names"])
    x = np.lib.format.open_memmap(matrix_dir / "x.npy", mode="r")
    age_col, phase_col = names.index("min_alert_age_sec"), names.index("phase_index")
    n = int(manifest["rows"])
    age = np.empty(n, np.float64)
    phase = np.empty(n, np.float64)
    for lo in range(0, n, 400_000):
        hi = min(lo + 400_000, n)
        block = np.asarray(x[lo:hi][:, [age_col, phase_col]], np.float64)
        age[lo:hi], phase[lo:hi] = block[:, 0], block[:, 1]
    day = np.load(matrix_dir / "day.npy")
    asset = np.asarray(np.load(matrix_dir / "asset.npy"), str)
    y = np.sinh(np.load(matrix_dir / "current_asinh.npy")) * VALUE_SCALE_USD
    # Silent-empty guard (DEFECT class: grid point outside sampled support reads as
    # zero): every Delta must lie inside the observed age support, or refuse.
    max_age = float(age.max())
    bad = [d for d in DELTAS if d > max_age]
    if bad:
        raise ValueError(
            f"delta grid points {bad} exceed the sampled age support "
            f"(max observed min_alert_age_sec = {max_age:.2f}); shrink the grid")

    cell_key = np.char.add(np.char.add(asset, day.astype(str)),
                           np.nan_to_num(phase, nan=9.0).astype(int).astype(str))
    cells, cinv = np.unique(cell_key, return_inverse=True)
    rng = np.random.default_rng(seed)
    report = {"schema": "QRE2DELAYFORFEIT1", "prereg": __doc__.split("Selftest:")[0],
              "matrix_receipt": manifest.get("matrix_receipt_sha256"),
              "deltas_sec": DELTAS, "goal_min_usd": GOAL_MIN_USD, "assets": {}}
    v = {}
    for d in DELTAS:
        best = np.full(len(cells), -np.inf)
        mask = age >= d
        np.maximum.at(best, cinv[mask], y[mask])
        v[d] = best
    goal = v[0.0] >= GOAL_MIN_USD
    cell_asset = np.empty(len(cells), dtype=asset.dtype)
    cell_day = np.empty(len(cells), np.int64)
    cell_asset[cinv], cell_day[cinv] = asset, day
    for a in sorted(set(asset)):
        sel = np.flatnonzero(goal & (cell_asset == a))
        days = cell_day[sel]
        uniq_days = np.unique(days)
        rows = {}
        for d in DELTAS:
            vd = v[d][sel]
            expired = ~np.isfinite(vd)
            ratio = np.where(expired, 0.0, np.maximum(vd, 0.0)) / v[0.0][sel]
            forfeit_usd = v[0.0][sel] - np.where(expired, 0.0, np.maximum(vd, 0.0))
            def stat(pick_days):
                m = np.isin(days, pick_days)
                return float(np.mean(ratio[m])), float(np.mean(forfeit_usd[m]))
            boots = [stat(rng.choice(uniq_days, len(uniq_days)))
                     for _ in range(n_boot)]
            r_ci = np.percentile([b[0] for b in boots], [2.5, 97.5])
            rows[str(int(d))] = {
                "capture_retained_mean": round(float(np.mean(ratio)), 4),
                "capture_ci95": [round(float(r_ci[0]), 4), round(float(r_ci[1]), 4)],
                "forfeit_usd_mean": round(float(np.mean(forfeit_usd)), 2),
                "expired_cell_fraction": round(float(np.mean(expired)), 4)}
        report["assets"][a] = {"n_goal_cells": int(len(sel)),
                               "n_days": int(len(uniq_days)), "per_delta": rows}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=1))
    return report


def selftest() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        names = ["min_alert_age_sec", "phase_index"]
        rows, day, asset, series, yv = [], [], [], [], []
        for d in (20210601, 20210602, 20210603, 20210604):
            # cell with a flat-value winner (waiting costs ~nothing)
            for a_age in (0, 60, 120, 180, 300):
                rows.append([a_age, 0.0]); day.append(d); asset.append("HG")
                series.append(f"flat_{d}"); yv.append(900.0)
            # cell whose value dies after 60s (waiting past 60 forfeits all)
            for a_age in (0, 30, 60, 120, 180, 300):
                rows.append([a_age, 1.0]); day.append(d); asset.append("HG")
                series.append(f"dying_{d}"); yv.append(800.0 if a_age <= 60 else -50.0)
        mdir = root / "m"; mdir.mkdir()
        np.save(mdir / "x.npy", np.asarray(rows, np.float32))
        np.save(mdir / "day.npy", np.asarray(day, np.int64))
        np.save(mdir / "asset.npy", np.asarray(asset))
        np.save(mdir / "series_id.npy", np.asarray(series))
        np.save(mdir / "current_asinh.npy", np.arcsinh(np.asarray(yv) / VALUE_SCALE_USD))
        (mdir / "manifest.json").write_text(json.dumps(
            {"feature_names": names, "rows": len(rows), "matrix_receipt_sha256": "st"}))
        rep = run(mdir, root / "o.json", n_boot=20)
        pd = rep["assets"]["HG"]["per_delta"]
        assert pd["0"]["capture_retained_mean"] == 1.0
        assert pd["30"]["capture_retained_mean"] > 0.95, pd["30"]
        assert 0.45 < pd["120"]["capture_retained_mean"] < 0.55, pd["120"]
        assert rep["assets"]["HG"]["n_goal_cells"] == 8
        # red fixture: matrix without min_alert_age_sec must fail loudly
        (mdir / "manifest.json").write_text(json.dumps(
            {"feature_names": ["phase_index"], "rows": len(rows)}))
        try:
            run(mdir, root / "o2.json", n_boot=5)
        except ValueError:
            pass
        else:
            raise AssertionError("red fixture accepted: missing age column")
    print("selftest OK: flat winner retains ~1.0, dying winner halves at 120s, "
          "red fixture refused")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--matrix-dir", type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if not args.matrix_dir or not args.out:
        ap.error("--matrix-dir and --out required (or --selftest)")
    rep = run(args.matrix_dir, args.out)
    for a, ar in rep["assets"].items():
        row = "  ".join(f"{d}s:{v['capture_retained_mean']:.3f}"
                        for d, v in ar["per_delta"].items())
        print(f"{a} ({ar['n_goal_cells']} goal cells): {row}")
    print(f"receipt: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
