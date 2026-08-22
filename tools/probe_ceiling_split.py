#!/usr/bin/env python3
"""Ceiling split — ticket 07 of design/entry_reset (2026-08-22).

PREREGISTRATION (written before the real run; echoed into the receipt):
- Question: how many dollars does a rho~0.15 within-cell picker at Delta=180s
  bank when one dimension at a time is made perfect? Not three piles that
  sum to ceiling_180.
- P0: copula picker at the rho the ruler maps to winner-vs-loser AUC 0.60
  (same machinery as probe_rho_ruler; must match usd_at_reference_auc['0.60']
  to +/-$5). Seed 0, n_draw 100.
- P_a: that picker, plus oracle cell-skip (keep a cell iff its max y > 0).
  Also report the day total after dropping the 1 and 2 lowest cell_max cells
  (diagnostic; cell maxima are unequal, frac_winner_ge_600~0.14).
- P_b: that picker, realizing the picked series' best stored-Delta y
  (timing-within-stored-grid). Preregistered bound: P_b-P0 <=
  ceiling_series_best-ceiling_180 ($199 HG / $176 NKD / $207 SI on all).
  Printing above that bound is an implementation defect. Continuous timing
  off the stored grid is unmeasured.
- P_c: copula at rho_at_rung on the same rows (sanity: should sit near the
  rung). Does not decide the letter.
- Shuffle: P_a keeps a random subset of cells at the same keep-rate; P_b
  takes a random stored Delta of the picked series; P_c is copula rho=0.
- Planted: 20% of cells hold the money, within-cell y is constant there.
  P_a must recover >=80% of ceiling_180. Non-finite y is refused.
- MDD: peak-to-trough of the chronological daily ceiling path, per asset
  and of the 3-asset portfolio-day sum. A ceiling that already breaches
  $1000 is typed, not a selector finding.
- Letter: A if P_a>=rung, B if P_b>=rung, else 'no single dimension'.
  Ticket 08 does not depend on the letter.
- Tier: DIAGNOSTIC ruler extension. No learner.

Selftest: python3 tools/probe_ceiling_split.py --selftest
Real:     OMP_NUM_THREADS=1 python3 tools/probe_ceiling_split.py \\
            --matrix-dir <round_0/component_matrix> --out <receipt.json>
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
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe_trained_accrual import (  # noqa: E402
    DELTAS, VALUE_SCALE_USD, ProbeRefusal, _cell_pick, load_delta_rows,
)
from probe_rho_ruler import (  # noqa: E402
    BLOCKS, N_DRAW, RUNG_USD, copula_score, rho_ruler_block, _cell_groups,
)

SCHEMA = "QRE2CEILSPLIT2"
DELTA_SEC = 180.0
STORED_GAP = {"HG": 199.0, "NKD": 176.0, "SI": 207.0}  # ceiling_series_best - ceiling_180, all
MDD_CAP = 1000.0


def _refuse_non_finite(y: np.ndarray) -> None:
    bad = int(np.sum(~np.isfinite(y)))
    if bad:
        raise ProbeRefusal(f"{bad} non-finite y values; expected all finite USD")


def _usd_per_day(by_day: dict[int, float], n_days: int) -> float:
    return float(sum(by_day.values()) / n_days) if n_days else float("nan")


def _max_drawdown(daily: list[tuple[int, float]]) -> float:
    """Peak-to-trough of the cumulative path, in USD. 0 if never retraces."""
    peak = 0.0
    cum = 0.0
    mdd = 0.0
    for _, x in daily:
        cum += x
        if cum > peak:
            peak = cum
        dd = peak - cum
        if dd > mdd:
            mdd = dd
    return float(mdd)


def _cell_max(y: np.ndarray, cell: np.ndarray, groups: list[np.ndarray]) -> np.ndarray:
    mx = np.empty(len(y))
    for g in groups:
        mx[g] = float(y[g].max())
    return mx


def split_block(rows, idx180: np.ndarray, idx_all: np.ndarray, asset: str, *,
                n_draw: int, seed: int) -> dict:
    _refuse_non_finite(rows.y[idx_all])
    ruler = rho_ruler_block(rows, idx180, asset, n_draw=n_draw, seed=seed)
    p0_auc = float(ruler["usd_at_reference_auc"]["0.60"]["usd_per_asset_day"])
    rho_p0 = float(ruler["usd_at_reference_auc"]["0.60"]["rho"])
    curve = {c["rho"]: c for c in ruler["rho_curve"]}
    p0_rho15 = float(curve[0.15]["usd_per_asset_day"]) if 0.15 in curve else float("nan")
    # WHY fall back: a planted cell with constant y has undefined winner-vs-loser AUC.
    p0 = p0_auc if np.isfinite(p0_auc) else p0_rho15
    if not np.isfinite(rho_p0):
        rho_p0 = 0.15
    rho_rung = float(ruler["rho_at_rung"])
    y180, cell180, day180 = rows.y[idx180], rows.cell[idx180], rows.day[idx180]
    elapsed, occ = rows.elapsed[idx180], rows.occupancy[idx180]
    groups = _cell_groups(cell180)
    days = sorted({int(d) for d in day180})
    n_days = len(days)
    rng = np.random.default_rng(seed)
    score = copula_score(y180, groups, rho_p0, rng)
    pick = _cell_pick(score, y180, cell180, day180, elapsed, occ, -np.inf)
    # Oracle cell-skip: keep cell iff cell max > 0. Realize the same picks.
    cell_max = _cell_max(y180, cell180, groups)
    keep = cell_max > 0.0
    skip_by_day: dict[int, float] = {d: 0.0 for d in days}
    keep_rate = float(keep.mean())
    picks = pick["picks"]
    for i in picks:
        d = int(day180[i])
        if keep[i]:
            skip_by_day[d] += float(y180[i])
    p_a = _usd_per_day(skip_by_day, n_days)
    # Shuffle A: same keep-rate, random cells.
    rng_a = np.random.default_rng(seed + 1)
    shuf_keep = rng_a.random(len(keep)) < keep_rate
    shuf_a: dict[int, float] = {d: 0.0 for d in days}
    for i in picks:
        d = int(day180[i])
        if shuf_keep[i]:
            shuf_a[d] += float(y180[i])
    p_a_shuffle = _usd_per_day(shuf_a, n_days)
    # Skip-1 / skip-2 diagnostic on oracle cell_max (not the picker).
    by_day_cells: dict[int, list[float]] = {d: [] for d in days}
    seen = set()
    for g in groups:
        d = int(day180[g[0]])
        key = int(cell180[g[0]])
        if key in seen:
            continue
        seen.add(key)
        by_day_cells[d].append(float(y180[g].max()))
    skip1 = []; skip2 = []; n_cells = []
    for d in days:
        vals = sorted(by_day_cells[d], reverse=True)
        n_cells.append(len(vals))
        skip1.append(sum(vals[:-1]) if len(vals) > 1 else 0.0)
        skip2.append(sum(vals[:-2]) if len(vals) > 2 else 0.0)
    # P_b: picked series' best stored-Delta y, same occupancy as P0.
    series180 = rows.series[idx180]
    y_all, series_all, delta_all = rows.y[idx_all], rows.series[idx_all], rows.delta[idx_all]
    best_by_series: dict[int, float] = {}
    rows_by_series: dict[int, np.ndarray] = {}
    for s in np.unique(series180):
        m = series_all == s
        best_by_series[int(s)] = float(y_all[m].max()) if m.any() else float("nan")
        rows_by_series[int(s)] = y_all[m]
    pb_day: dict[int, float] = {d: 0.0 for d in days}
    pb_shuf_day: dict[int, float] = {d: 0.0 for d in days}
    rng_b = np.random.default_rng(seed + 2)
    occupied_until = -np.inf
    prev_day = None
    order = np.lexsort((cell180, day180))
    bounds = np.flatnonzero(np.diff(cell180[order])) + 1
    for grp in np.split(order, bounds):
        d = int(day180[grp[0]])
        if d != prev_day:
            prev_day, occupied_until = d, -np.inf
        best = grp[int(np.argmax(score[grp]))]
        t = elapsed[best]
        if not np.isfinite(t):
            t = -np.inf
        if t < occupied_until:
            continue
        occupied_until = t + float(occ[best]) if np.isfinite(t) else -np.inf
        s = int(series180[best])
        pb_day[d] += best_by_series[s]
        ys = rows_by_series[s]
        pb_shuf_day[d] += float(ys[int(rng_b.integers(0, len(ys)))]) if len(ys) else 0.0
    p_b = _usd_per_day(pb_day, n_days)
    p_b_shuffle = _usd_per_day(pb_shuf_day, n_days)
    # P_c: copula at rho_at_rung.
    rng_c = np.random.default_rng(seed + 3)
    usd_c = []
    usd_c0 = []
    rho_c = rho_rung if np.isfinite(rho_rung) else 1.0
    rho_c = min(max(rho_c, 0.0), 1.0)
    for _ in range(n_draw):
        sc = copula_score(y180, groups, rho_c, rng_c)
        pk = _cell_pick(sc, y180, cell180, day180, elapsed, occ, -np.inf)
        usd_c.append(_usd_per_day(pk["all"], n_days))
        sc0 = copula_score(y180, groups, 0.0, rng_c)
        pk0 = _cell_pick(sc0, y180, cell180, day180, elapsed, occ, -np.inf)
        usd_c0.append(_usd_per_day(pk0["all"], n_days))
    p_c = float(np.mean(usd_c))
    p_c_shuffle = float(np.mean(usd_c0))
    # Ceiling path MDD.
    ceil_day = []
    for d in days:
        ceil_day.append((d, float(sum(by_day_cells[d]))))
    mdd = _max_drawdown(ceil_day)
    rung = RUNG_USD[asset]
    bound = STORED_GAP[asset]
    typed = []
    if (p_b - p0) > bound + 1.0:
        typed.append(f"P_b-P0={p_b - p0:.1f} exceeds stored-grid bound {bound}")
    if mdd >= MDD_CAP:
        typed.append(f"ceiling path MDD {mdd:.1f} breaches ${MDD_CAP:.0f}")
    letter = "A" if p_a >= rung else ("B" if p_b >= rung else "no single dimension")
    return {
        "days": n_days, "day_range": [days[0], days[-1]],
        "rung_usd": rung, "rho_p0": rho_p0, "rho_at_rung": rho_rung,
        "ceiling_180_usd_per_asset_day": float(ruler["ceiling_180_usd_per_asset_day"]),
        "ceiling_series_best_usd_per_asset_day": float(ruler["ceiling_series_best_usd_per_asset_day"]),
        "p0_usd_per_asset_day": p0,
        "p_a_oracle_skip_usd_per_asset_day": p_a,
        "p_a_shuffle_usd_per_asset_day": p_a_shuffle,
        "p_a_keep_rate": keep_rate,
        "p_b_stored_grid_usd_per_asset_day": p_b,
        "p_b_shuffle_usd_per_asset_day": p_b_shuffle,
        "p_b_minus_p0": float(p_b - p0),
        "stored_grid_bound_usd": bound,
        "p_c_rho_at_rung_usd_per_asset_day": p_c,
        "p_c_shuffle_usd_per_asset_day": p_c_shuffle,
        "skip1_cell_max_usd_per_asset_day": float(np.mean(skip1)) if skip1 else float("nan"),
        "skip2_cell_max_usd_per_asset_day": float(np.mean(skip2)) if skip2 else float("nan"),
        "cells_per_day_mean": float(np.mean(n_cells)) if n_cells else float("nan"),
        "ceiling_path_mdd_usd": mdd,
        "letter": letter,
        "typed": typed,
        "decomposition_order": "P0 measured AUC0.60 picker; P_a skip on cell_max>0; "
                               "P_b max stored-Delta of P0 series; P_c copula at rho_at_rung. "
                               "No sum-to-ceiling clause.",
    }


def run(matrix_dir: Path, out_path: Path, *, blocks=BLOCKS, n_draw: int = N_DRAW,
        log=print) -> dict:
    rows = load_delta_rows(matrix_dir, deltas=DELTAS)
    _refuse_non_finite(rows.y)
    all_days = (int(rows.day.min()), int(rows.day.max()))
    report: dict = {
        "schema": SCHEMA, "prereg": __doc__, "matrix_receipt": rows.matrix_receipt,
        "n_draw": n_draw, "delta_sec": DELTA_SEC,
        "blocks": {**{k: list(v) for k, v in blocks.items()}, "all": list(all_days)},
        "assets": {},
    }
    portfolio_days: dict[int, float] = {}
    for asset in sorted(set(rows.asset.tolist())):
        report["assets"][asset] = {}
        for bname, (lo, hi) in {**blocks, "all": all_days}.items():
            idx_all = np.flatnonzero((rows.asset == asset) & (rows.day >= lo) & (rows.day <= hi))
            idx180 = np.flatnonzero((rows.asset == asset) & (rows.day >= lo) & (rows.day <= hi)
                                    & (rows.delta == DELTA_SEC))
            if len(idx180) == 0:
                continue
            block = split_block(rows, idx180, idx_all, asset, n_draw=n_draw, seed=0)
            report["assets"][asset][bname] = block
            log(f"{asset:4s} {bname:10s} P0={block['p0_usd_per_asset_day']:7.1f} "
                f"Pa={block['p_a_oracle_skip_usd_per_asset_day']:7.1f} "
                f"Pb={block['p_b_stored_grid_usd_per_asset_day']:7.1f} "
                f"Pc={block['p_c_rho_at_rung_usd_per_asset_day']:7.1f} "
                f"letter={block['letter']} mdd={block['ceiling_path_mdd_usd']:.0f}")
            if bname == "all":
                # rebuild daily ceiling into portfolio (best-effort: mean cells already in block)
                pass
    # Portfolio MDD needs per-day ceiling across assets; recompute cheaply from ALL rows.
    report["portfolio_mdd_usd"] = _portfolio_mdd(rows)
    if report["portfolio_mdd_usd"] >= MDD_CAP:
        report.setdefault("typed", []).append(
            f"portfolio ceiling path MDD {report['portfolio_mdd_usd']:.1f} breaches ${MDD_CAP:.0f}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=1, sort_keys=True))
    return report


def _portfolio_mdd(rows) -> float:
    days = sorted({int(d) for d in rows.day})
    daily = []
    for d in days:
        total = 0.0
        for asset in sorted(set(rows.asset.tolist())):
            m = (rows.day == d) & (rows.asset == asset) & (rows.delta == DELTA_SEC)
            if not m.any():
                continue
            y, cell = rows.y[m], rows.cell[m]
            for g in _cell_groups(cell):
                total += float(y[g].max())
        daily.append((d, total))
    return _max_drawdown(daily)


def _planted_between_cell(root: Path) -> None:
    """20% of cells have y=800 constant; 80% have y=0. Ages include 180 and 290."""
    names = ["min_alert_age_sec", "phase_index", "disc_fvol_session_scope_elapsed_sec"]
    ages = np.array([0, 30, 60, 120, 180, 240, 290], float)
    rows_x, day, asset, series, y, occ = [], [], [], [], [], []
    sid = 0
    n_days, n_phase, n_series = 12, 3, 10
    for d in range(1, n_days + 1):
        for phase in range(n_phase):
            rich = (phase == 0)
            for s in range(n_series):
                base = 800.0 if rich else -50.0
                for a in ages:
                    elapsed = phase * 7200 + 1800 + a
                    rows_x.append([a, phase, elapsed])
                    day.append(20210600 + d); asset.append("HG")
                    series.append(f"s{sid}"); y.append(base); occ.append(600.0)
                sid += 1
    root.mkdir(parents=True, exist_ok=True)
    x = np.asarray(rows_x, np.float32)
    np.save(root / "x.npy", x)
    np.save(root / "day.npy", np.asarray(day, np.int64))
    np.save(root / "asset.npy", np.asarray(asset))
    np.save(root / "series_id.npy", np.asarray(series))
    np.save(root / "current_asinh.npy", np.arcsinh(np.asarray(y, np.float64) / VALUE_SCALE_USD))
    np.save(root / "occupancy_sec.npy", np.asarray(occ))
    (root / "manifest.json").write_text(json.dumps(
        {"feature_names": names, "rows": len(x), "matrix_receipt_sha256": "synthetic-between"}))


def selftest() -> int:
    blocks = {"only": (20210601, 20210624)}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _planted_between_cell(tmp / "planted")
        rep = run(tmp / "planted", tmp / "planted.json", blocks=blocks, n_draw=20,
                  log=lambda *_: None)
        blk = rep["assets"]["HG"]["only"]
        ceil = blk["ceiling_180_usd_per_asset_day"]
        assert blk["p_a_oracle_skip_usd_per_asset_day"] > blk["p0_usd_per_asset_day"] + 50.0, blk
        assert blk["p_a_oracle_skip_usd_per_asset_day"] >= 0.90 * 800.0, blk
        assert blk["letter"] in {"A", "no single dimension", "B"}
        _planted_between_cell(tmp / "red")
        cur = np.load(tmp / "red" / "current_asinh.npy"); cur[2] = np.nan
        np.save(tmp / "red" / "current_asinh.npy", cur)
        try:
            run(tmp / "red", tmp / "red.json", blocks=blocks, n_draw=2, log=lambda *_: None)
        except ProbeRefusal as exc:
            assert "non-finite" in str(exc), exc
        else:
            raise AssertionError("red fixture (NaN y) was accepted")
    print(f"selftest OK: planted between-cell P_a={blk['p_a_oracle_skip_usd_per_asset_day']:.1f} "
          f"vs ceiling {ceil:.1f}; NaN-y refused")
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
    sys.exit(main())
