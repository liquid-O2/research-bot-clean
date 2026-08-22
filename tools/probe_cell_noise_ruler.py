#!/usr/bin/env python3
"""Cell noise ruler — ticket D7 of design/ENTRY_SELECTION_MAP.md (confirmation-window
frontier, 2026-08-22). The bar every trained object is judged against, stated BEFORE the
trained numbers are read.

PREREGISTRATION (written before the real run; echoed into the receipt):
- Question: how precisely must a decision-time score know each candidate's standalone
  value for a <=1-entry-per-cell picker to reach 80% of the per-asset-day ceiling, and
  the goal rung ($2,000 HG / $1,500 NKD, SI)?
- Picker: in every cell (asset, day, phase) it sees v_s = y(s, Delta=180s) + N(0, sigma^2)
  per series (y = standalone PnL of entering at 180s; 180s retains ~97% of the goal-cell
  value per delay_forfeit_20260822.json) and enters the top-v series; realized = that
  series' true y at 180s. One position per asset enforced greedily by session-elapsed
  time + occupancy_sec (same walk as probe_trained_accrual._cell_pick).
- Arms: enter-all; theta-skip (enter iff top v >= theta), theta chosen on the THRESHOLD
  block only at the same sigma, applied unchanged to FORWARD (knob provenance).
- Denominator: per (asset, day) sum over cells of the series-best value (matrix ceiling,
  occupancy-free); abstained cells $0; every block day counted.
- Grid: sigma in {0, 100, ..., 2000} USD; N_DRAW noise draws per cell (mean and 95% band).
- Output per (asset, block, sigma): capture_all, capture_skip, usd/asset-day (both arms);
  sigma* at 80% capture and at the rung (linear interpolation on the grid).
- Tier: DIAGNOSTIC ruler. sigma is a property of a hypothetical score, not a fitted one;
  the trained object's achieved capture is read against this curve, never the reverse.

Selftest: python3 tools/probe_cell_noise_ruler.py --selftest
Real:     python3 tools/probe_cell_noise_ruler.py --matrix-dir <round_0/component_matrix> \
            --out <receipt.json>
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe_trained_accrual import (  # noqa: E402
    DeltaRows, ProbeRefusal, _ceiling_by_day, _cell_pick, _synthetic_matrix, load_delta_rows,
)

DELTA_SEC = 180.0
SIGMA_GRID = tuple(float(s) for s in range(0, 2001, 100))
N_DRAW = 50
BLOCKS = {"threshold": (20210721, 20210806), "forward": (20210809, 20210826)}
RUNG_USD = {"HG": 2000.0, "NKD": 1500.0, "SI": 1500.0}
THETA_QUANTILES = 21


def _block_rows(rows: DeltaRows, asset: str, lo: int, hi: int) -> np.ndarray:
    return np.flatnonzero((rows.asset == asset) & (rows.delta == DELTA_SEC)
                          & (rows.day >= lo) & (rows.day <= hi))


def _pick_totals(rows: DeltaRows, idx: np.ndarray, noisy: np.ndarray, theta: float,
                 ceiling: dict[int, float]) -> tuple[float, float, float, float]:
    pick = _cell_pick(noisy, rows.y[idx], rows.cell[idx], rows.day[idx],
                      rows.elapsed[idx], rows.occupancy[idx], theta)
    days = sorted(ceiling)
    r_all = np.array([pick["all"].get(d, 0.0) for d in days])
    r_skip = np.array([pick["skip"].get(d, 0.0) for d in days])
    c = np.array([ceiling[d] for d in days])
    return (float(r_all.sum() / c.sum()), float(r_skip.sum() / c.sum()),
            float(r_all.mean()), float(r_skip.mean()))


def _choose_theta(rows: DeltaRows, idx: np.ndarray, noisy: np.ndarray) -> float:
    """theta on the prior block: top-of-cell noisy value whose enter-iff-above rule
    realizes the most true dollars there."""
    cell = rows.cell[idx]
    u, inv = np.unique(cell, return_inverse=True)
    order = np.lexsort((-noisy, inv))
    first = np.ones(len(order), bool); first[1:] = inv[order][1:] != inv[order][:-1]
    top_rows = order[first]
    top_v, realized = noisy[top_rows], rows.y[idx][top_rows]
    grid = np.quantile(top_v, np.linspace(0, 1, THETA_QUANTILES))
    totals = [float(realized[top_v >= q].sum()) for q in grid]
    return float(grid[int(np.argmax(totals))])


def _crossing(sigmas: np.ndarray, values: np.ndarray, target: float) -> float | None:
    """Largest sigma at which values (decreasing in sigma) still reach target; linear
    interpolation between grid points; None if never reached."""
    above = values >= target
    if not above.any():
        return None
    last = int(np.flatnonzero(above).max())
    if last == len(sigmas) - 1:
        return float(sigmas[last])
    s0, s1, v0, v1 = sigmas[last], sigmas[last + 1], values[last], values[last + 1]
    return float(s0 + (v0 - target) / (v0 - v1) * (s1 - s0)) if v0 != v1 else float(s0)


def run(matrix_dir: Path, out_path: Path, *, blocks=BLOCKS, sigmas=SIGMA_GRID,
        n_draw: int = N_DRAW, rung=RUNG_USD, seed: int = 20260822, log=print) -> dict:
    rows = load_delta_rows(matrix_dir, deltas=(DELTA_SEC,))
    rows.x = np.empty((0, 0), np.float32)  # features are not used by a noise ruler
    rng = np.random.default_rng(seed)
    report = {"schema": "QRE2CELLNOISERULER1", "prereg": __doc__.split("Selftest:")[0],
              "matrix_receipt": rows.matrix_receipt, "delta_sec": DELTA_SEC,
              "sigma_grid_usd": list(sigmas), "n_draw": n_draw, "blocks": dict(blocks),
              "rung_usd": dict(rung), "assets": {}}
    assets = sorted(set(rows.asset))
    for a in assets:
        report["assets"][a] = {}
        prior_name = "threshold" if "threshold" in blocks else next(iter(blocks))
        for bname, (lo, hi) in blocks.items():
            idx = _block_rows(rows, a, lo, hi)
            if not len(idx):
                raise ProbeRefusal(f"{a} {bname}: no rows at Delta={DELTA_SEC} in {lo}-{hi}")
            ceiling = _ceiling_by_day(rows, (rows.asset == a) & (rows.day >= lo) & (rows.day <= hi))
            prior_idx = _block_rows(rows, a, *blocks[prior_name])
            curve = []
            for s in sigmas:
                draws = []
                for _ in range(n_draw):
                    noisy = rows.y[idx] + rng.normal(0.0, s, len(idx))
                    prior_noisy = rows.y[prior_idx] + rng.normal(0.0, s, len(prior_idx))
                    theta = _choose_theta(rows, prior_idx, prior_noisy)
                    draws.append(_pick_totals(rows, idx, noisy, theta, ceiling))
                d = np.asarray(draws)
                curve.append({"sigma_usd": s,
                              "capture_all": round(float(d[:, 0].mean()), 4),
                              "capture_all_band95": [round(float(np.percentile(d[:, 0], 2.5)), 4),
                                                     round(float(np.percentile(d[:, 0], 97.5)), 4)],
                              "capture_skip": round(float(d[:, 1].mean()), 4),
                              "usd_per_asset_day_all": round(float(d[:, 2].mean()), 2),
                              "usd_per_asset_day_skip": round(float(d[:, 3].mean()), 2)})
            sig = np.asarray([c["sigma_usd"] for c in curve])
            cap_all = np.asarray([c["capture_all"] for c in curve])
            cap_skip = np.asarray([c["capture_skip"] for c in curve])
            usd_best = np.maximum(np.asarray([c["usd_per_asset_day_all"] for c in curve]),
                                  np.asarray([c["usd_per_asset_day_skip"] for c in curve]))
            report["assets"][a][bname] = {
                "n_days": len(ceiling), "n_rows": int(len(idx)),
                "ceiling_usd_per_asset_day": round(float(np.mean(list(ceiling.values()))), 2),
                "curve": curve,
                "sigma_at_80pct_capture_all": _crossing(sig, cap_all, 0.80),
                "sigma_at_80pct_capture_skip": _crossing(sig, cap_skip, 0.80),
                "sigma_at_rung_best_arm": _crossing(sig, usd_best, rung.get(a, 1500.0))}
            log(f"{a} {bname}: sigma@80% all={report['assets'][a][bname]['sigma_at_80pct_capture_all']} "
                f"skip={report['assets'][a][bname]['sigma_at_80pct_capture_skip']} "
                f"sigma@rung={report['assets'][a][bname]['sigma_at_rung_best_arm']} "
                f"(ceiling ${report['assets'][a][bname]['ceiling_usd_per_asset_day']}/asset-day)")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".json.partial")
    tmp.write_text(json.dumps(report, indent=1)); tmp.replace(out_path)
    return report


def selftest() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _synthetic_matrix(tmp / "m", signal=False, n_days=16, n_series=12, seed=3)
        blocks = {"threshold": (20210601, 20210608), "forward": (20210609, 20210616)}
        rep = run(tmp / "m", tmp / "r.json", blocks=blocks, sigmas=(0.0, 300.0, 1e6),
                  n_draw=8, rung={"HG": 600.0}, log=lambda *_: None)
        curve = rep["assets"]["HG"]["forward"]["curve"]
        caps = [c["capture_all"] for c in curve]
        assert caps[0] >= 0.90, f"sigma=0 picker should realize ~the cell ceiling: {caps[0]}"
        assert caps[0] > caps[1] > caps[2], f"capture must fall with sigma: {caps}"
        assert caps[2] < 0.6, f"sigma->inf picker should be near random-pick level: {caps[2]}"
        assert rep["assets"]["HG"]["forward"]["sigma_at_80pct_capture_all"] is not None
        bad = tmp / "bad"; _synthetic_matrix(bad, signal=False, n_days=4, seed=5)
        try:
            run(bad, tmp / "bad.json", blocks={"threshold": (20210601, 20210602),
                                               "forward": (20210701, 20210702)},
                sigmas=(0.0,), n_draw=1, log=lambda *_: None)
        except ProbeRefusal:
            pass
        else:
            raise AssertionError("empty forward block was accepted")
    print("selftest OK: sigma=0 capture %.3f > sigma=300 %.3f > sigma=inf %.3f; "
          "empty block refused" % tuple(caps))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("PREREGISTRATION")[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--matrix-dir", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--n-draw", type=int, default=N_DRAW)
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if not (args.matrix_dir and args.out):
        ap.error("--matrix-dir and --out are required (or --selftest)")
    run(args.matrix_dir, args.out, n_draw=args.n_draw)
    return 0


if __name__ == "__main__":
    sys.exit(main())
