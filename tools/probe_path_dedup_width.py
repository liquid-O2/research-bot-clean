#!/usr/bin/env python3
"""Path-dedup width grid — ticket 20 (2026-08-22).

PREREGISTRATION (written before the real run; echoed into the receipt):
- Question: can a TRAIN-chosen formation-VWAP width hit retained_fraction
  >= 0.94 on HG, NKD and SI at median names <= 16? Ticket 18's 2θ is
  0.95/0.88/0.91. 1θ is 0.99/0.92/0.93 with HG at 23 names.
- Live coalescer only: formation VWAP-aligned (age≈0), causal-first.
  Widths 1.00, 1.25, 1.50, 1.75, 2.00 × TRAIN θ (ticket 09 tight).
  Extra: merge-adjacent at 1θ (union-find on |Δaligned|<=θ inside cell).
- Per-asset TRAIN letter: among keys with ncell<=16 and shrink>=rung,
  highest retained_fraction. Target ret>=0.94 is reported, not a
  refusal if missed. FORWARD of the TRAIN pick is unused as a knob.
- 2021 cannot promote. y unused in the keep.

Selftest: python3 tools/probe_path_dedup_width.py --selftest
Real:     OMP_NUM_THREADS=1 python3 tools/probe_path_dedup_width.py \\
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
from probe_path_dedup import VWAP_COL, _formation_sec, _theta, causal_first_mask  # noqa: E402
from probe_path_dedup_live import (  # noqa: E402
    DELTA_SEC, FORM_DELTA, SIDE_COL, _bucket_id, _join_form_aligned,
)
from probe_rho_ruler import BLOCKS, RUNG_USD, _cell_groups  # noqa: E402
from probe_trained_accrual import ProbeRefusal, _synthetic_matrix, load_delta_rows  # noqa: E402

SCHEMA = "QRE2PATHWID1"
N_DRAW = 200
MAJORITY = 0.94
MAX_NAMES = 16.0
WIDTHS = (1.00, 1.25, 1.50, 1.75, 2.00)


def merge_adj_ids(aligned: np.ndarray, cell: np.ndarray, width: float) -> np.ndarray:
    n = len(aligned)
    parent = np.arange(n, dtype=np.int64)

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = int(parent[i])
        return i

    for g in _cell_groups(cell):
        order = g[np.argsort(aligned[g], kind="stable")]
        for a, b in zip(order[:-1], order[1:]):
            if not (np.isfinite(aligned[a]) and np.isfinite(aligned[b])):
                continue
            if abs(float(aligned[b]) - float(aligned[a])) > width:
                continue
            ra, rb = find(int(a)), find(int(b))
            if ra != rb:
                parent[rb] = ra
    roots = np.fromiter((find(i) for i in range(n)), np.int64, n)
    return cell.astype(np.int64) * (n + 1) + roots


def run(matrix_dir: Path, out_path: Path, *, blocks=BLOCKS, n_draw: int = N_DRAW,
        log=print) -> dict:
    rows180 = load_delta_rows(matrix_dir, deltas=(DELTA_SEC,))
    rows0 = load_delta_rows(matrix_dir, deltas=(FORM_DELTA,))
    if not np.isfinite(rows180.y).all():
        raise ProbeRefusal(
            f"{int(np.sum(~np.isfinite(rows180.y)))} non-finite y; expected all finite USD")
    names180 = rows180.feature_names
    form_al_all = _join_form_aligned(rows180, rows0, names180, rows0.feature_names)
    all_days = (int(rows180.day.min()), int(rows180.day.max()))
    catalog = [f"form0_x{w:.2f}".replace(".", "p") for w in WIDTHS] + ["form0_merge_1x"]
    report: dict = {
        "schema": SCHEMA, "prereg": __doc__, "matrix_receipt": rows180.matrix_receipt,
        "delta_sec": DELTA_SEC, "n_draw": n_draw, "target_ret": MAJORITY,
        "max_names": MAX_NAMES, "widths": list(WIDTHS), "catalog": catalog,
        "form0_aligned_coverage": float(np.mean(np.isfinite(form_al_all))),
        "blocks": {**{k: list(v) for k, v in blocks.items()}, "all": list(all_days)},
        "assets": {},
    }
    for asset in sorted(set(rows180.asset.tolist())):
        theta = _theta(asset)
        report["assets"][asset] = {"rung_usd": RUNG_USD[asset], "theta_usd": theta,
                                   "filters": {}, "survivors": [], "letter": ""}
        for w, fname in zip(WIDTHS, catalog[:-1]):
            report["assets"][asset]["filters"][fname] = {}
        report["assets"][asset]["filters"]["form0_merge_1x"] = {}
        for bname, (lo, hi) in {**blocks, "all": all_days}.items():
            idx = np.flatnonzero(
                (rows180.asset == asset) & (rows180.day >= lo) & (rows180.day <= hi)
                & (rows180.delta == DELTA_SEC))
            if len(idx) == 0:
                continue
            formed = _formation_sec(rows180.x[idx], names180)
            cell = rows180.cell[idx]
            form_al = form_al_all[idx]
            for w, fname in zip(WIDTHS, catalog[:-1]):
                buckets = cell.astype(np.int64) * 10**9 + _bucket_id(form_al, w * theta)
                flag = causal_first_mask(formed, buckets)
                block = _score_mask(rows180, idx, flag, n_draw=n_draw, seed=0)
                report["assets"][asset]["filters"][fname][bname] = block
                log(f"{asset:4s} {fname:16s} {bname:10s} "
                    f"shrink={block['shrink_ceiling_usd_per_asset_day']:7.1f} "
                    f"ret={block['retained_fraction']:.3f} "
                    f"ncell={block['occupancy']['median_eligible_per_cell']:.1f}")
            mid = merge_adj_ids(form_al, cell, theta)
            flag = causal_first_mask(formed, mid)
            block = _score_mask(rows180, idx, flag, n_draw=n_draw, seed=0)
            report["assets"][asset]["filters"]["form0_merge_1x"][bname] = block
            log(f"{asset:4s} {'form0_merge_1x':16s} {bname:10s} "
                f"shrink={block['shrink_ceiling_usd_per_asset_day']:7.1f} "
                f"ret={block['retained_fraction']:.3f} "
                f"ncell={block['occupancy']['median_eligible_per_cell']:.1f}")
        ranked = []
        for fname, spec in report["assets"][asset]["filters"].items():
            tr = spec.get("train")
            if tr is None:
                continue
            if (tr["occupancy"]["median_eligible_per_cell"] <= MAX_NAMES
                    and tr["shrink_ceiling_usd_per_asset_day"] >= RUNG_USD[asset]):
                ranked.append((tr["retained_fraction"],
                               tr["shrink_ceiling_usd_per_asset_day"], fname))
        ranked.sort(reverse=True)
        report["assets"][asset]["survivors"] = [
            {"filter": f, "ret": r, "shrink_ceiling": s} for r, s, f in ranked]
        letter = "no ncell<=16 key"
        if ranked:
            letter = ranked[0][2]
            if ranked[0][0] < MAJORITY:
                letter = letter + f" ret={ranked[0][0]:.3f}<0.94"
        report["assets"][asset]["letter"] = letter
        if ranked:
            report["assets"][asset]["train_best_forward"] = (
                report["assets"][asset]["filters"][ranked[0][2]].get("forward"))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=1, sort_keys=True))
    return report


def selftest() -> int:
    from probe_path_dedup_live import _append_live_cols
    blocks = {"train": (20210601, 20210624), "forward": (20210601, 20210624)}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _synthetic_matrix(tmp / "p", signal=True)
        _append_live_cols(tmp / "p", mode="winner_first")
        rep = run(tmp / "p", tmp / "p.json", blocks=blocks, n_draw=40, log=lambda *_: None)
        x2 = rep["assets"]["HG"]["filters"]["form0_x2p00"]["train"]
        assert x2["occupancy"]["pick_rate"] > 0.99, x2
        _synthetic_matrix(tmp / "red", signal=True)
        _append_live_cols(tmp / "red", mode="winner_first")
        man = json.loads((tmp / "red" / "manifest.json").read_text())
        xred = np.load(tmp / "red" / "x.npy")
        age = xred[:, man["feature_names"].index("min_alert_age_sec")]
        hit = int(np.flatnonzero(np.abs(age - 180.0) <= 2.5)[0])
        cur = np.load(tmp / "red" / "current_asinh.npy"); cur[hit] = np.nan
        np.save(tmp / "red" / "current_asinh.npy", cur)
        try:
            run(tmp / "red", tmp / "r.json", blocks=blocks, n_draw=2, log=lambda *_: None)
        except ProbeRefusal as exc:
            assert "non-finite" in str(exc), exc
        else:
            raise AssertionError("red fixture (NaN y) was accepted")
    print("selftest OK: 2x width keeps planted winner; NaN y refused")
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
