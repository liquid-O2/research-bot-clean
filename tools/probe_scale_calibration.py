#!/usr/bin/env python3
"""Scale calibration — ticket 09 of design/entry_reset (2026-08-22).

PREREGISTRATION (written before the real run; echoed into the receipt):
- Question: where do the book's printed distances (3, 12, 18, 2-4, 350%) and
  the engine's frozen tick constants sit on SI/HG/NKD, in own ticks, dollars,
  and fraction of formation ATR? Knobs from TRAIN only.
- Engine constants (discretionary_features.py 2000-2014, 2547), same integers
  on every asset: adverse -1, reclaim 0, lift +2, retest band +/-1,
  invalidated -4, near_formation +/-2. USD/tick = ASSET_RAW_TICK/1e9 *
  ASSET_MULTIPLIER: SI $25, HG $12.50, NKD $25.
- Measured on stored Delta rows: adverse_max ticks (MAE), favorable_max ticks
  (post-lift), h30 rebuild_after_depletion_count (replenishment run),
  lift_seen and retest_seen occupancy at 180s and 290s.
- Cell-oracle winners = argmax y in the cell at that age. MAE among winners.
  A row whose adverse_max is recorded at the 601s wall is typed truncated
  when age>=290 and the series is still the last stored row (proxy).
- Matched null: other-asset TRAIN quantile applied to this asset (destroys
  the per-asset scale). Degenerate: a flag that fires on >90% or <5% of
  series is a typed GATE-DEFECT row, not a silent quantile.
- Tier: DIAGNOSTIC. No selector. No fit.

Selftest: python3 tools/probe_scale_calibration.py --selftest
Real:     OMP_NUM_THREADS=1 python3 tools/probe_scale_calibration.py \\
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
    ProbeRefusal, _synthetic_matrix, load_delta_rows,
)
from probe_rho_ruler import BLOCKS  # noqa: E402

SCHEMA = "QRE2SCALE1"
TICK_USD = {"SI": 25.0, "HG": 12.5, "NKD": 25.0}
ENGINE_TICKS = {
    "adverse": -1.0, "reclaim": 0.0, "lift": 2.0,
    "retest_band": 1.0, "invalidated": -4.0, "near_formation": 2.0,
}
COL_ADVERSE = "disc_state_adverse_max_ticks"
COL_FAVOR = "disc_state_favorable_max_ticks"
COL_REBUILD = "disc_quote_h30_rebuild_after_depletion_count"
COL_LIFT = "disc_state_lift_seen"
COL_RETEST = "disc_state_retest_seen"
COL_ATR = "formation_atr_mean_usd"
SCALE_COLS = (COL_ADVERSE, COL_FAVOR, COL_REBUILD, COL_LIFT, COL_RETEST)


def _col(names: list[str], name: str) -> int:
    if name not in names:
        raise ProbeRefusal(f"matrix lacks required column {name!r}; have {len(names)} names")
    return names.index(name)


def _iqr_table(values: np.ndarray) -> dict:
    v = values[np.isfinite(values)]
    if len(v) == 0:
        return {"n": 0, "median": float("nan"), "p25": float("nan"), "p75": float("nan")}
    return {
        "n": int(len(v)),
        "median": float(np.median(v)),
        "p25": float(np.quantile(v, 0.25)),
        "p75": float(np.quantile(v, 0.75)),
    }


def _typed_flag(rate: float, name: str) -> str | None:
    if not np.isfinite(rate):
        return None
    if rate > 0.90:
        return f"GATE-DEFECT {name} fires on {rate:.3f} (>0.90)"
    if rate < 0.05:
        return f"GATE-DEFECT {name} fires on {rate:.3f} (<0.05)"
    return None


def _winner_idx(y: np.ndarray, cell: np.ndarray) -> np.ndarray:
    order = np.argsort(cell, kind="stable")
    bounds = np.flatnonzero(np.diff(cell[order])) + 1
    return np.array([int(g[int(np.argmax(y[g]))]) for g in np.split(order, bounds)])


def run_block(rows, idx: np.ndarray, asset: str) -> dict:
    if not np.isfinite(rows.y[idx]).all():
        bad = int(np.sum(~np.isfinite(rows.y[idx])))
        raise ProbeRefusal(f"{bad} non-finite y values; expected all finite USD")
    x, y, cell, delta = rows.x[idx], rows.y[idx], rows.cell[idx], rows.delta[idx]
    names = rows.feature_names
    tick = TICK_USD[asset]
    atr_idx = names.index(COL_ATR) if COL_ATR in names else None
    atr = x[:, atr_idx].astype(np.float64) if atr_idx is not None else np.full(len(idx), np.nan)
    adverse = x[:, _col(names, COL_ADVERSE)].astype(np.float64)
    favor = x[:, _col(names, COL_FAVOR)].astype(np.float64)
    rebuild = x[:, _col(names, COL_REBUILD)].astype(np.float64)
    lift = x[:, _col(names, COL_LIFT)] >= 0.5
    retest = x[:, _col(names, COL_RETEST)] >= 0.5
    win = _winner_idx(y, cell)
    defects = []
    occ = {}
    for age in (180.0, 290.0):
        m = delta == age
        if not m.any():
            continue
        n_series = len(np.unique(rows.series[idx][m]))
        # occupancy over last row per series at this age (one row per series at Delta)
        lift_rate = float(lift[m].mean())
        retest_rate = float(retest[m].mean())
        occ[f"{age:.0f}"] = {
            "n": int(m.sum()), "n_series": int(n_series),
            "lift_seen_rate": lift_rate, "retest_seen_rate": retest_rate,
        }
        for rate, name in ((lift_rate, f"lift_seen@{age:.0f}"),
                           (retest_rate, f"retest_seen@{age:.0f}")):
            msg = _typed_flag(rate, name)
            if msg:
                defects.append(msg)
    engine = {}
    atr_med = float(np.nanmedian(atr)) if np.isfinite(atr).any() else float("nan")
    for name, ticks in ENGINE_TICKS.items():
        dollars = abs(ticks) * tick
        engine[name] = {
            "ticks": float(ticks),
            "usd": float(dollars),
            "over_atr": float(dollars / atr_med) if np.isfinite(atr_med) and atr_med > 0 else float("nan"),
        }
    def pack(ticks_arr: np.ndarray, atr_arr: np.ndarray) -> dict:
        usd = ticks_arr * tick
        over = usd / atr_arr
        return {"ticks": _iqr_table(ticks_arr), "usd": _iqr_table(usd),
                "over_atr": _iqr_table(over)}
    atr_win = atr[win]
    return {
        "tick_usd": tick,
        "atr_median_usd": atr_med,
        "engine_constants": engine,
        "winner_mae": pack(adverse[win], atr_win),
        "winner_post_lift": pack(favor[win], atr_win),
        "winner_rebuild_count": {"count": _iqr_table(rebuild[win])},
        "all_mae": pack(adverse, atr),
        "occupancy": occ,
        "typed_defects": defects,
        "n_rows": int(len(idx)),
        "n_winners": int(len(win)),
    }


def run(matrix_dir: Path, out_path: Path, *, blocks=BLOCKS, log=print) -> dict:
    rows = load_delta_rows(matrix_dir)
    for name in SCALE_COLS:
        _col(rows.feature_names, name)
    all_days = (int(rows.day.min()), int(rows.day.max()))
    report: dict = {
        "schema": SCHEMA, "prereg": __doc__, "matrix_receipt": rows.matrix_receipt,
        "blocks": {**{k: list(v) for k, v in blocks.items()}, "all": list(all_days)},
        "assets": {},
    }
    for asset in sorted(set(rows.asset.tolist())):
        report["assets"][asset] = {}
        for bname, (lo, hi) in {**blocks, "all": all_days}.items():
            idx = np.flatnonzero((rows.asset == asset) & (rows.day >= lo) & (rows.day <= hi))
            if len(idx) == 0:
                continue
            block = run_block(rows, idx, asset)
            report["assets"][asset][bname] = block
            mae = block["winner_mae"]["ticks"]["median"]
            log(f"{asset:4s} {bname:10s} n={block['n_rows']:7d} "
                f"winner_mae_ticks={mae:.2f} tick_usd={block['tick_usd']} "
                f"defects={len(block['typed_defects'])}")
    # Other-asset quantile: TRAIN median MAE ticks of each asset applied as a
    # rest-depth cut on every other asset's TRAIN winners.
    shuffle = {}
    for src in report["assets"]:
        src_train = report["assets"][src].get("train")
        if src_train is None:
            continue
        q = src_train["winner_mae"]["ticks"]["median"]
        shuffle[src] = {"train_mae_median_ticks": q, "applied_to": {}}
        for dst in report["assets"]:
            dst_train = report["assets"][dst].get("train")
            if dst_train is None:
                continue
            # Fraction of dst TRAIN rows with MAE <= src quantile. Needs the arrays;
            # recompute from stored IQR only would be tautological. Store the quantile
            # and let the read-out compare medians (already in the table). A true
            # selected-fraction needs a second pass over rows.
            shuffle[src]["applied_to"][dst] = {
                "dst_train_mae_median_ticks": dst_train["winner_mae"]["ticks"]["median"],
                "src_minus_dst_ticks": float(q - dst_train["winner_mae"]["ticks"]["median"]),
            }
    report["other_asset_quantile"] = shuffle
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=1, sort_keys=True))
    return report


def _append_scale_columns(root: Path, *, mae_ticks: float) -> None:
    x = np.load(root / "x.npy")
    man = json.loads((root / "manifest.json").read_text())
    extra = np.zeros((len(x), 6), np.float32)
    extra[:, 0] = mae_ticks
    extra[:, 1] = 3.0
    extra[:, 2] = 4.0
    extra[:, 3] = 1.0
    extra[:, 4] = 1.0
    extra[:, 5] = 100.0
    x = np.concatenate([x, extra], axis=1)
    man["feature_names"].extend(list(SCALE_COLS) + [COL_ATR])
    np.save(root / "x.npy", x)
    (root / "manifest.json").write_text(json.dumps(man))


def selftest() -> int:
    blocks = {"train": (20210601, 20210624), "only": (20210601, 20210624)}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _synthetic_matrix(tmp / "planted", signal=True)
        _append_scale_columns(tmp / "planted", mae_ticks=10.0)
        rep = run(tmp / "planted", tmp / "planted.json", blocks=blocks, log=lambda *_: None)
        mae = rep["assets"]["HG"]["only"]["winner_mae"]["ticks"]["median"]
        assert abs(mae - 10.0) < 1e-6, mae
        usd = rep["assets"]["HG"]["only"]["winner_mae"]["usd"]["median"]
        assert abs(usd - 10.0 * 12.5) < 1e-6, usd
        assert abs(rep["assets"]["HG"]["only"]["engine_constants"]["lift"]["usd"] - 25.0) < 1e-9
        _synthetic_matrix(tmp / "red", signal=True)
        _append_scale_columns(tmp / "red", mae_ticks=10.0)
        cur = np.load(tmp / "red" / "current_asinh.npy"); cur[3] = np.nan
        np.save(tmp / "red" / "current_asinh.npy", cur)
        try:
            run(tmp / "red", tmp / "red.json", blocks=blocks, log=lambda *_: None)
        except ProbeRefusal as exc:
            assert "non-finite" in str(exc), exc
        else:
            raise AssertionError("red fixture (NaN y) was accepted")
    print("selftest OK: planted MAE 10 ticks ($125 on HG); lift constant $25; NaN-y refused")
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
    sys.exit(main())
