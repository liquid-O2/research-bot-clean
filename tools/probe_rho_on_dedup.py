#!/usr/bin/env python3
"""Rho ruler on the live-deduped cell — ticket 22 (2026-08-22).

PREREGISTRATION (written before the real run; echoed into the receipt):
- Question: after prefix keep-first on formation VWAP (ticket 20 widths:
  HG 2θ, NKD 1θ, SI 1θ), how strong a within-cell score must be to
  print the rung on the REMAINING names? Does AUC 0.60 (the best
  measured on the unreduced cell, $508 HG) buy more dollars when
  N drops from ~64 to ~15?
- Live coalescer only. y unused in the keep. Copula score vs y on
  the kept rows. Same picker as ticket 01 (top-1 per cell at Δ=180).
- Matched null is rho=0 on the reduced cell (must sit near the
  reduced pool mean, not the rung).
- Knob: per-asset width from ticket 20 TRAIN (highest ret among
  ncell<=16, shrink>=rung). FORWARD unused as a knob.
- 2021 cannot promote. Dollars at AUC 0.60 are a diagnostic.

Selftest: python3 tools/probe_rho_on_dedup.py --selftest
Real:     OMP_NUM_THREADS=1 python3 tools/probe_rho_on_dedup.py \\
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
from probe_path_dedup import _formation_sec, _theta, causal_first_mask  # noqa: E402
from probe_path_dedup_live import (  # noqa: E402
    DELTA_SEC, FORM_DELTA, _bucket_id, _join_form_aligned,
)
from probe_rho_ruler import (  # noqa: E402
    BLOCKS, N_DRAW, RHO_GRID, RUNG_USD, rho_ruler_block,
)
from probe_trained_accrual import ProbeRefusal, _synthetic_matrix, load_delta_rows  # noqa: E402

SCHEMA = "QRE2RHODEDUP1"
# Ticket 20 TRAIN letter among ncell<=16: HG 1.75θ, NKD/SI 1θ.
# HG 2θ holds FORWARD better (0.936 vs 0.927). Taken: 2.00 / 1.00 / 1.00.
WIDTH_MULT = {"HG": 2.00, "NKD": 1.00, "SI": 1.00}


def _keep_idx(rows180, rows0, idx: np.ndarray, asset: str) -> np.ndarray:
    names = rows180.feature_names
    form_al = _join_form_aligned(rows180, rows0, names, rows0.feature_names)[idx]
    formed = _formation_sec(rows180.x[idx], names)
    cell = rows180.cell[idx]
    theta = _theta(asset) * WIDTH_MULT[asset]
    buckets = cell.astype(np.int64) * 10**9 + _bucket_id(form_al, theta)
    return idx[causal_first_mask(formed, buckets)]


def run(matrix_dir: Path, out_path: Path, *, blocks=BLOCKS, n_draw: int = N_DRAW,
        log=print) -> dict:
    rows180 = load_delta_rows(matrix_dir, deltas=(DELTA_SEC,))
    rows0 = load_delta_rows(matrix_dir, deltas=(FORM_DELTA,))
    if not np.isfinite(rows180.y).all():
        raise ProbeRefusal(
            f"{int(np.sum(~np.isfinite(rows180.y)))} non-finite y; expected all finite USD")
    all_days = (int(rows180.day.min()), int(rows180.day.max()))
    report: dict = {
        "schema": SCHEMA, "prereg": __doc__, "matrix_receipt": rows180.matrix_receipt,
        "delta_sec": DELTA_SEC, "n_draw": n_draw, "width_mult": WIDTH_MULT,
        "rho_grid": list(RHO_GRID),
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
            block = rho_ruler_block(rows180, kept, asset, n_draw=n_draw)
            report["assets"][asset][bname] = block
            log(f"{asset:4s} {bname:10s} nmed={block['anatomy']['n_per_cell_median']:.0f} "
                f"ceil={block['ceiling_180_usd_per_asset_day']:7.0f} "
                f"rho@rung={block['rho_at_rung']:.2f} auc@rung={block['auc_at_rung']:.2f} "
                f"$@auc.60={block['usd_at_reference_auc']['0.60']['usd_per_asset_day']:.0f} "
                f"pool={block['anatomy']['pool_mean_usd_per_trade']:.0f}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=1, sort_keys=True))
    return report


def selftest() -> int:
    from probe_path_dedup_live import _append_live_cols
    blocks = {"train": (20210601, 20210624)}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _synthetic_matrix(tmp / "p", signal=True)
        _append_live_cols(tmp / "p", mode="winner_first")
        rep = run(tmp / "p", tmp / "p.json", blocks=blocks, n_draw=8, log=lambda *_: None)
        tr = rep["assets"]["HG"]["train"]
        assert tr["anatomy"]["n_per_cell_median"] <= 20, tr["anatomy"]
        assert "0.60" in tr["usd_at_reference_auc"], tr
    print("selftest OK: reduced-cell rho ruler runs; ncell cut")
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
