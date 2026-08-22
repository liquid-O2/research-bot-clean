#!/usr/bin/env python3
"""Per-feature accrual scan (user ruling 2026-08-22: the v1 hand-built state scores are
not right — let the RAW DATA rank every observable and rebuild the states from what wins).

PREREGISTRATION:
- For EVERY matrix feature, per asset: within-(asset,day,phase) winner-vs-loser pairwise
  AUC at Delta=0 and Delta=290s (row nearest target within +/-15s; winner series-best
  >= $600, loser <= $0). Report per asset: top features by ACCRUAL (AUC290-AUC0, folded
  to >=0.5 orientation) and by level at 290s.
- Multiple-comparisons law: with 1,764 features the null tail is crowded — the scan is a
  RANKING device for state-v2 ingredient selection, never a finding by itself; any
  chosen ingredient must re-clear the accrual probe's permutation null inside its state
  score. NaN cells are median-imputed within cell (biases toward 0.5 = conservative).

Selftest: python3 tools/probe_feature_accrual_scan.py --selftest
Real:     python3 tools/probe_feature_accrual_scan.py --matrix-dir <dir> --out <json>
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

DELTA_LO, DELTA_HI, TOL = 0.0, 290.0, 15.0
WINNER_MIN_USD, LOSER_MAX_USD, VALUE_SCALE_USD = 600.0, 0.0, 600.0


def _rows_at(age: np.ndarray, inv: np.ndarray, idx: np.ndarray, target: float) -> np.ndarray:
    cand = idx[np.abs(age[idx] - target) <= TOL]
    if not len(cand):
        raise ValueError(f"no rows within {TOL}s of target {target}s — grid outside support")
    order = np.lexsort((np.abs(age[cand] - target), inv[cand]))
    cand = cand[order]
    first = np.ones(len(cand), bool)
    first[1:] = inv[cand][1:] != inv[cand][:-1]
    return cand[first]


def _auc_all_features(x_rows: np.ndarray, is_win: np.ndarray,
                      cell: np.ndarray) -> np.ndarray:
    """Pair-weighted within-cell Mann-Whitney AUC per feature column."""
    n_feat = x_rows.shape[1]
    num = np.zeros(n_feat)
    den = 0.0
    order = np.argsort(cell, kind="stable")
    cell_s = cell[order]
    boundaries = np.flatnonzero(np.diff(cell_s)) + 1
    from scipy.stats import rankdata
    for grp in np.split(order, boundaries):
        w_mask = is_win[grp]
        n_w, n_l = int(w_mask.sum()), int((~w_mask).sum())
        if not n_w or not n_l:
            continue
        block = x_rows[grp].copy()
        med = np.nanmedian(block, axis=0)
        nan_mask = np.isnan(block)
        block[nan_mask] = np.broadcast_to(med, block.shape)[nan_mask]
        block[:, np.isnan(med)] = 0.0
        ranks = rankdata(block, axis=0)
        u = ranks[w_mask].sum(axis=0) - n_w * (n_w + 1) / 2.0
        num += u
        den += n_w * n_l
    if den == 0:
        raise ValueError("no cell contained both a winner and a loser")
    return num / den


def run(matrix_dir: Path, out_path: Path, *, top_k: int = 40) -> dict:
    manifest = json.loads((matrix_dir / "manifest.json").read_text())
    names = list(manifest["feature_names"])
    day = np.load(matrix_dir / "day.npy")
    asset = np.asarray(np.load(matrix_dir / "asset.npy"), str)
    series = np.asarray(np.load(matrix_dir / "series_id.npy"), str)
    y = np.sinh(np.load(matrix_dir / "current_asinh.npy")) * VALUE_SCALE_USD
    x = np.lib.format.open_memmap(matrix_dir / "x.npy", mode="r")
    age_col, phase_col = names.index("min_alert_age_sec"), names.index("phase_index")
    n = len(day)
    age = np.empty(n, np.float64); phase = np.empty(n, np.float64)
    for lo in range(0, n, 400_000):
        hi = min(lo + 400_000, n)
        blk = np.asarray(x[lo:hi][:, [age_col, phase_col]], np.float64)
        age[lo:hi], phase[lo:hi] = blk[:, 0], blk[:, 1]
    _u, inv = np.unique(series, return_inverse=True)
    best = np.full(len(_u), -np.inf)
    np.maximum.at(best, inv, y)
    s_win, s_lose = best >= WINNER_MIN_USD, best <= LOSER_MAX_USD
    eligible_rows = np.flatnonzero((s_win | s_lose)[inv])
    report = {"schema": "QRE2FEATACCRUALSCAN1", "prereg": __doc__.split("Selftest:")[0],
              "matrix_receipt": manifest.get("matrix_receipt_sha256"),
              "deltas": [DELTA_LO, DELTA_HI], "assets": {}}
    for a in sorted(set(asset)):
        a_idx = eligible_rows[asset[eligible_rows] == a]
        aucs = {}
        for target in (DELTA_LO, DELTA_HI):
            rows = _rows_at(age, inv, a_idx, target)
            x_rows = np.asarray(x[np.sort(rows)], np.float64)
            rows = np.sort(rows)
            cell = (day[rows].astype(np.int64) * 10
                    + np.nan_to_num(phase[rows], nan=9.0).astype(np.int64))
            aucs[target] = _auc_all_features(x_rows, s_win[inv[rows]], cell)
        folded_hi = np.abs(aucs[DELTA_HI] - 0.5)
        accrual = folded_hi - np.abs(aucs[DELTA_LO] - 0.5)
        def table(order_stat, k=top_k):
            idx = np.argsort(order_stat)[::-1][:k]
            return [{"feature": names[i],
                     "auc0": round(float(aucs[DELTA_LO][i]), 4),
                     "auc290": round(float(aucs[DELTA_HI][i]), 4),
                     "accrual_folded": round(float(accrual[i]), 4)} for i in idx]
        report["assets"][a] = {"top_by_accrual": table(accrual),
                               "top_by_level290": table(folded_hi)}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=1))
    return report


def selftest() -> int:
    rng = np.random.default_rng(5)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp); mdir = root / "m"; mdir.mkdir()
        names = ["min_alert_age_sec", "phase_index", "f_accruing", "f_flat", "f_nan"]
        rows, day, asset, series, yv = [], [], [], [], []
        for d in range(20210601, 20210611):
            for s_i in range(12):
                win = s_i < 5
                for a_age in (0.0, 290.0):
                    accr = (0.0 if a_age == 0 else (2.0 if win else 0.0)) + rng.normal()
                    rows.append([a_age, 0.0, accr, rng.normal(), np.nan])
                    day.append(d); asset.append("HG")
                    series.append(f"s{d}_{s_i}")
                    yv.append(900.0 if win else -100.0)
        np.save(mdir / "x.npy", np.asarray(rows, np.float32))
        np.save(mdir / "day.npy", np.asarray(day, np.int64))
        np.save(mdir / "asset.npy", np.asarray(asset))
        np.save(mdir / "series_id.npy", np.asarray(series))
        np.save(mdir / "current_asinh.npy", np.arcsinh(np.asarray(yv) / VALUE_SCALE_USD))
        (mdir / "manifest.json").write_text(json.dumps(
            {"feature_names": names, "rows": len(rows), "matrix_receipt_sha256": "st"}))
        rep = run(mdir, root / "o.json", top_k=3)
        top = rep["assets"]["HG"]["top_by_accrual"][0]
        assert top["feature"] == "f_accruing", f"planted accruer not ranked first: {top}"
        assert top["accrual_folded"] > 0.1
        flat = [r for r in rep["assets"]["HG"]["top_by_accrual"] if r["feature"] == "f_flat"]
        if flat:
            assert abs(flat[0]["auc290"] - 0.5) < 0.12
        # red fixture: a grid outside support must refuse
        try:
            rows2 = np.asarray(rows, np.float32); rows2[:, 0] = 5000.0
            np.save(mdir / "x.npy", rows2)
            run(mdir, root / "o2.json")
        except ValueError as e:
            assert "support" in str(e)
        else:
            raise AssertionError("red fixture accepted: out-of-support grid ran")
    print("selftest OK: planted accruer ranked first, flat feature ~0.5, "
          "out-of-support grid refused")
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
        print(f"=== {a} top accruers:")
        for r in ar["top_by_accrual"][:12]:
            print(f"  {r['feature']:52s} {r['auc0']:.3f} -> {r['auc290']:.3f}")
    print(f"receipt: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
