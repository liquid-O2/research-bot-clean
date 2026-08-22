#!/usr/bin/env python3
"""Rho ruler — ticket 01 of design/ENTRY_RESET_PLAN_2026-08-22.md (T1).

The bar a one-entry-per-phase picker must clear, stated in SCORE-QUALITY units so any
measured within-cell AUC or Spearman can be placed on it before its dollars are believed.

PREREGISTRATION (written before the real run; echoed into the receipt):
- Question: how strongly must a decision-time score correlate (within a cell = asset, day,
  phase) with each candidate's standalone value for a <=1-entry-per-cell picker at
  Delta=180s to reach (a) the ladder rung ($2,000 HG / $1,500 NKD, SI per asset-day) and
  (b) 80% of the cell ceiling at that Delta? And what do the AUCs measured so far buy?
- Score model: Gaussian copula on within-cell ranks. score = rho*z(y) + sqrt(1-rho^2)*noise,
  z = normal score of the candidate's rank among its cell's candidates. rho is therefore the
  within-cell rank correlation of score and outcome; the same score's winner(>=$600) vs
  loser(<=$0) AUC and its within-cell Spearman are reported beside it so a measured AUC maps
  to a rho and a dollar figure. Why a copula and not additive dollar noise (D7's sigma): a
  learned score is a ranking, and D7's sigma depends on the dollar scale of y, which differs
  per asset; rho does not.
- Picker: enter the top-scored series in every cell at Delta=180s (realized = its true y at
  180s); one position per asset enforced greedily by session-elapsed + occupancy
  (probe_trained_accrual._cell_pick, enter-all arm, theta=-inf). Abstained days $0.
- Denominators: ceiling_180 = per (asset, day) sum over cells of max y at 180s (what a
  perfect 180s picker banks; the rho=1 arm must reproduce it to the cent) and
  ceiling_series_best (A7-comparable). Capture is against ceiling_180.
- Blocks: TRAIN 20210610-0709, THRESHOLD 20210721-0806, FORWARD 20210809-0826, ALL.
- Grid: rho in {0,.1,.15,.2,.3,...,1.0}; N_DRAW draws per (asset, block, rho).
- Output per (asset, block): pool anatomy (n per cell, mean, within-cell sd, %>=600, %wall),
  the rho curve (usd/asset-day, capture, AUC, Spearman), rho* and AUC* at the rung and at
  80% capture (linear interpolation), usd/asset-day at the reference AUCs {.60,.65,.70}.
- Also receipted: flat_by_phase_close_violations = rows whose occupancy_sec exceeds the
  phase_remaining_sec feature (the fact that lets a <=1/phase policy replay without a walk).
- Tier: DIAGNOSTIC ruler. rho is a property of a hypothetical score, never a fitted one.

Selftest: python3 tools/probe_rho_ruler.py --selftest
Real:     python3 tools/probe_rho_ruler.py --matrix-dir <round_0/component_matrix> --out <receipt.json>
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import numpy as np
from scipy.stats import norm

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe_trained_accrual import (  # noqa: E402
    DeltaRows, ProbeRefusal, _cell_pick, _synthetic_matrix, load_delta_rows,
)

SCHEMA = "QRE2RHORULER1"
DELTA_SEC = 180.0
RHO_GRID = (0.0, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)
N_DRAW = 100
REFERENCE_AUCS = (0.60, 0.65, 0.70)
WINNER_MIN_USD, LOSER_MAX_USD, WALL_HIT_USD = 600.0, 0.0, -850.0
BLOCKS = {"train": (20210610, 20210709), "threshold": (20210721, 20210806),
          "forward": (20210809, 20210826)}
RUNG_USD = {"HG": 2000.0, "NKD": 1500.0, "SI": 1500.0}
PHASE_REMAINING_COL = "phase_remaining_sec"


def _cell_groups(cell: np.ndarray) -> list[np.ndarray]:
    order = np.argsort(cell, kind="stable")
    bounds = np.flatnonzero(np.diff(cell[order])) + 1
    return np.split(order, bounds)


def copula_score(y: np.ndarray, groups: list[np.ndarray], rho: float,
                 rng: np.random.Generator) -> np.ndarray:
    """Within-cell rank-copula score with rank correlation rho to y."""
    z = np.empty(len(y))
    for g in groups:
        rank = np.argsort(np.argsort(y[g], kind="stable"), kind="stable")
        z[g] = norm.ppf((rank + 0.5) / len(g))
    return rho * z + np.sqrt(1.0 - rho * rho) * rng.standard_normal(len(y))


def _winner_loser_auc(score: np.ndarray, y: np.ndarray, groups: list[np.ndarray]) -> float:
    """Pooled within-cell Mann-Whitney AUC of winners (>= $600) over losers (<= $0)."""
    wins = 0.0; pairs = 0
    for g in groups:
        w = g[y[g] >= WINNER_MIN_USD]; l = g[y[g] <= LOSER_MAX_USD]
        if len(w) == 0 or len(l) == 0:
            continue
        wins += float((score[w][:, None] > score[l][None, :]).sum()); pairs += len(w) * len(l)
    return float("nan") if pairs == 0 else wins / pairs


def _mean_within_cell_spearman(score: np.ndarray, y: np.ndarray,
                               groups: list[np.ndarray]) -> float:
    vals = []
    for g in groups:
        if len(g) < 4:
            continue
        rs = np.argsort(np.argsort(score[g])); ry = np.argsort(np.argsort(y[g]))
        vals.append(float(np.corrcoef(rs, ry)[0, 1]))
    return float(np.mean(vals)) if vals else float("nan")


def _pool_anatomy(y: np.ndarray, groups: list[np.ndarray]) -> dict:
    sizes = np.array([len(g) for g in groups])
    sd = np.array([float(y[g].std()) for g in groups if len(g) > 1])
    return {"cells": int(len(groups)), "n_per_cell_median": float(np.median(sizes)),
            "n_per_cell_min": int(sizes.min()), "n_per_cell_max": int(sizes.max()),
            "pool_mean_usd_per_trade": float(y.mean()),
            "within_cell_sd_usd_median": float(np.median(sd)) if len(sd) else float("nan"),
            "frac_winner_ge_600": float((y >= WINNER_MIN_USD).mean()),
            "frac_wall_hit": float((y <= WALL_HIT_USD).mean())}


def _ceiling_180_by_day(y: np.ndarray, day: np.ndarray, groups: list[np.ndarray]) -> dict[int, float]:
    out: dict[int, float] = {}
    for g in groups:
        d = int(day[g[0]]); out[d] = out.get(d, 0.0) + float(y[g].max())
    return out


def _interp_x_at(curve: list[dict], key: str, target: float) -> float:
    """First rho on the grid where curve[key] reaches target (linear between grid points)."""
    for lo, hi in zip(curve, curve[1:]):
        if hi[key] >= target > lo[key] or (lo[key] >= target and lo is curve[0]):
            if lo[key] >= target:
                return lo["rho"]
            return lo["rho"] + (target - lo[key]) / (hi[key] - lo[key]) * (hi["rho"] - lo["rho"])
    return float("nan")


def _interp_y_at_rho(curve: list[dict], key: str, rho: float) -> float:
    xs = [c["rho"] for c in curve]; ys = [c[key] for c in curve]
    return float("nan") if not np.isfinite(rho) else float(np.interp(rho, xs, ys))


def rho_ruler_block(rows: DeltaRows, idx: np.ndarray, asset: str, *, rho_grid=RHO_GRID,
                    n_draw: int = N_DRAW, seed: int = 0) -> dict:
    """The ruler for one (asset, block): anatomy, rho curve, rho*/AUC* at rung and 80%."""
    y, cell, day = rows.y[idx], rows.cell[idx], rows.day[idx]
    elapsed, occupancy = rows.elapsed[idx], rows.occupancy[idx]
    groups = _cell_groups(cell)
    days = sorted({int(d) for d in day})
    ceiling_180 = _ceiling_180_by_day(y, day, groups)
    ceiling_180_per_day = sum(ceiling_180.values()) / len(days)
    series_best = rows.series_best[rows.series[idx]]
    best_by_day: dict[int, float] = {}
    for g in groups:
        d = int(day[g[0]]); best_by_day[d] = best_by_day.get(d, 0.0) + float(series_best[g].max())
    rng = np.random.default_rng(seed)
    curve = []
    for rho in rho_grid:
        usd, aucs, sps = [], [], []
        for _ in range(n_draw):
            score = copula_score(y, groups, float(rho), rng)
            pick = _cell_pick(score, y, cell, day, elapsed, occupancy, -np.inf)
            usd.append(float(np.mean([pick["all"].get(d, 0.0) for d in days])))
            aucs.append(_winner_loser_auc(score, y, groups))
            sps.append(_mean_within_cell_spearman(score, y, groups))
        u = np.asarray(usd)
        curve.append({"rho": float(rho), "usd_per_asset_day": float(u.mean()),
                      "usd_per_asset_day_band95": [float(np.quantile(u, .025)),
                                                   float(np.quantile(u, .975))],
                      "capture_180": float(u.mean() / ceiling_180_per_day),
                      "auc_winner_vs_loser": float(np.nanmean(aucs)),
                      "spearman_within_cell": float(np.nanmean(sps))})
    rung = RUNG_USD[asset]
    rho_at_rung = _interp_x_at(curve, "usd_per_asset_day", rung)
    rho_at_80 = _interp_x_at(curve, "capture_180", 0.80)
    at_reference = {}
    for auc in REFERENCE_AUCS:
        r = _interp_x_at(curve, "auc_winner_vs_loser", auc)
        at_reference[f"{auc:.2f}"] = {"rho": r,
                                      "usd_per_asset_day": _interp_y_at_rho(curve, "usd_per_asset_day", r)}
    return {"days": len(days), "day_range": [days[0], days[-1]],
            "ceiling_180_usd_per_asset_day": float(ceiling_180_per_day),
            "ceiling_series_best_usd_per_asset_day": float(sum(best_by_day.values()) / len(days)),
            "anatomy": _pool_anatomy(y, groups), "rho_curve": curve,
            "rung_usd": rung, "rho_at_rung": rho_at_rung,
            "auc_at_rung": _interp_y_at_rho(curve, "auc_winner_vs_loser", rho_at_rung),
            "rho_at_80pct_capture": rho_at_80,
            "auc_at_80pct_capture": _interp_y_at_rho(curve, "auc_winner_vs_loser", rho_at_80),
            "usd_at_reference_auc": at_reference}


def _flat_by_phase_close_violations(rows: DeltaRows) -> int:
    """Rows whose occupancy outlives the phase. Zero means a <=1/phase policy needs no walk."""
    if PHASE_REMAINING_COL not in rows.feature_names:
        raise ProbeRefusal(f"feature {PHASE_REMAINING_COL!r} absent; have {len(rows.feature_names)} names")
    remaining = rows.x[:, rows.feature_names.index(PHASE_REMAINING_COL)].astype(np.float64)
    return int(np.sum(rows.occupancy > remaining + 1.0))


def _refuse_non_finite(rows: DeltaRows) -> None:
    # WHY series_best too: it is a max over EVERY matrix row, so one NaN anywhere in y
    # poisons it; checking only the Delta rows let a corrupt matrix through (selftest red).
    bad = int(np.sum(~np.isfinite(rows.y))) + int(np.sum(~np.isfinite(rows.series_best)))
    if bad:
        raise ProbeRefusal(f"{bad} non-finite y values (Delta rows + series-best); expected all finite USD")


def run(matrix_dir: Path, out_path: Path, *, blocks=BLOCKS, rho_grid=RHO_GRID,
        n_draw: int = N_DRAW, log=print) -> dict:
    rows = load_delta_rows(matrix_dir, deltas=(DELTA_SEC,))
    _refuse_non_finite(rows)
    violations = _flat_by_phase_close_violations(rows)
    all_days = (int(rows.day.min()), int(rows.day.max()))
    report: dict = {"schema": SCHEMA, "prereg": __doc__, "matrix_receipt": rows.matrix_receipt,
                    "delta_sec": DELTA_SEC, "rho_grid": list(rho_grid), "n_draw": n_draw,
                    "blocks": {**{k: list(v) for k, v in blocks.items()}, "all": list(all_days)},
                    "flat_by_phase_close_violations": violations, "rows_checked": int(len(rows.y)),
                    "assets": {}}
    for asset in sorted(set(rows.asset.tolist())):
        report["assets"][asset] = {}
        for name, (lo, hi) in {**blocks, "all": all_days}.items():
            idx = np.flatnonzero((rows.asset == asset) & (rows.day >= lo) & (rows.day <= hi))
            if len(idx) == 0:
                continue
            block = rho_ruler_block(rows, idx, asset, rho_grid=rho_grid, n_draw=n_draw)
            report["assets"][asset][name] = block
            log(f"{asset:4s} {name:10s} days={block['days']:3d} ceiling180={block['ceiling_180_usd_per_asset_day']:7.0f}"
                f" rho@rung={block['rho_at_rung']:.2f} auc@rung={block['auc_at_rung']:.2f}"
                f" rho@80%={block['rho_at_80pct_capture']:.2f}"
                f" $@auc.60={block['usd_at_reference_auc']['0.60']['usd_per_asset_day']:.0f}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=1, sort_keys=True))
    return report


def selftest() -> int:
    blocks = {"only": (20210601, 20210624)}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _synthetic_matrix(tmp / "planted", signal=True)
        # WHY the synthetic matrix lacks phase_remaining_sec: it predates this tool; append it
        # as "phase never closes" so the flatness check runs on the fixture too.
        _append_phase_remaining(tmp / "planted")
        rep = run(tmp / "planted", tmp / "planted.json", blocks=blocks, n_draw=20, log=lambda *_: None)
        blk = rep["assets"]["HG"]["only"]
        curve = {c["rho"]: c for c in blk["rho_curve"]}
        perfect = curve[1.0]["usd_per_asset_day"]; ceiling = blk["ceiling_180_usd_per_asset_day"]
        assert abs(perfect - ceiling) < 0.01, f"rho=1 picker banks {perfect:.2f}, ceiling_180 is {ceiling:.2f}"
        assert curve[1.0]["auc_winner_vs_loser"] > 0.999, curve[1.0]
        rows = load_delta_rows(tmp / "planted", deltas=(DELTA_SEC,))
        random_mean = float(np.mean([rows.y[rows.cell == c].mean() for c in np.unique(rows.cell)])) * 3
        lo, hi = curve[0.0]["usd_per_asset_day_band95"]
        assert lo - 100 <= random_mean <= hi + 100, f"rho=0 band {lo:.0f}..{hi:.0f} misses random mean {random_mean:.0f}"
        assert abs(curve[0.0]["auc_winner_vs_loser"] - 0.5) < 0.05, curve[0.0]
        assert rep["flat_by_phase_close_violations"] == 0, rep["flat_by_phase_close_violations"]
        _synthetic_matrix(tmp / "red", signal=True)
        _append_phase_remaining(tmp / "red")
        cur = np.load(tmp / "red" / "current_asinh.npy"); cur[7] = np.nan
        np.save(tmp / "red" / "current_asinh.npy", cur)
        try:
            run(tmp / "red", tmp / "red.json", blocks=blocks, n_draw=2, log=lambda *_: None)
        except ProbeRefusal as exc:
            assert "non-finite" in str(exc), exc
        else:
            raise AssertionError("red fixture (NaN y) was accepted")
    print(f"selftest OK: rho=1 reproduces ceiling_180 ({ceiling:.2f}); rho=0 inside random band; "
          "flatness check 0 violations; NaN-y fixture refused")
    return 0


def _append_phase_remaining(root: Path) -> None:
    x = np.load(root / "x.npy"); man = json.loads((root / "manifest.json").read_text())
    x = np.concatenate([x, np.full((len(x), 1), 1e6, np.float32)], axis=1)
    man["feature_names"].append(PHASE_REMAINING_COL)
    np.save(root / "x.npy", x); (root / "manifest.json").write_text(json.dumps(man))


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
    sys.exit(main())
