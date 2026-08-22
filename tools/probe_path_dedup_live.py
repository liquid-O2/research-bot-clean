#!/usr/bin/env python3
"""Path-dedup live keys — ticket 18 (2026-08-22).

PREREGISTRATION (written before the real run; echoed into the receipt):
- Question: ticket 16 clustered VWAP-aligned at Δ=180. Live dedup
  cannot see the finished cell and cannot use a VWAP that has moved
  since birth. Do formation-time keys and prefix NMS (same side,
  close in time, close in aligned dollars) still keep the cell-max
  while cutting names?
- Live rule (spec PATH_DEDUP_LIVE_20260822.md): path_id at birth is
  (side, round(zigzag pivot / θ)). Pivot is the swing high (SHORT)
  or low (LONG). Nested rungs share it. Until CandidateRow stores
  pivot, the coalescer is prefix NMS with T and W from TRAIN.
- Catalog, causal-first, y unused. θ = TRAIN winner MAE tight.
    snap180_vwap_1x          ticket 16 echo
    form0_vwap_1x / _2x      VWAP-aligned at age≈0
    form_side_time_60 / _120 nested-rung time bins
    form_nms_60_1x           prefix NMS T=60s W=θ
    after_form_earliest_16 / _12  cap after form0_vwap_1x
- Bars: TRAIN ret>=0.70, median names<=16, shrink>=rung. FORWARD of
  a TRAIN survivor is reported, never a knob. 2021 cannot promote.
- NaN formation-aligned does not merge (singleton).

Selftest: python3 tools/probe_path_dedup_live.py --selftest
Real:     OMP_NUM_THREADS=1 python3 tools/probe_path_dedup_live.py \\
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
from probe_path_dedup import (  # noqa: E402
    AGE_COL, PHASE_ELAPSED_COL, VWAP_COL, _formation_sec, _theta,
    causal_first_mask,
)
from probe_rho_ruler import BLOCKS, RUNG_USD, _cell_groups  # noqa: E402
from probe_trained_accrual import (  # noqa: E402
    ELAPSED_COL, ProbeRefusal, _synthetic_matrix, load_delta_rows,
)

SCHEMA = "QRE2PATHLIVE1"
N_DRAW = 200
MAJORITY = 0.70
MAX_NAMES = 16.0
DELTA_SEC = 180.0
SIDE_COL = "side"
FORM_DELTA = 0.0


def _bucket_id(aligned: np.ndarray, width: float) -> np.ndarray:
    n = len(aligned)
    out = -10**12 - np.arange(n, dtype=np.int64)
    ok = np.isfinite(aligned) & (width > 0)
    out[ok] = np.rint(aligned[ok] / width).astype(np.int64)
    return out


def prefix_nms_mask(formed: np.ndarray, side: np.ndarray, aligned: np.ndarray,
                    cell: np.ndarray, t_win: float, w_usd: float) -> np.ndarray:
    keep = np.zeros(len(formed), bool)
    kept: dict[int, list[int]] = {}
    for i in np.argsort(formed, kind="stable"):
        c = int(cell[i])
        lst = kept.setdefault(c, [])
        drop = False
        for j in lst:
            if side[i] != side[j]:
                continue
            if abs(float(formed[i]) - float(formed[j])) > t_win:
                continue
            if not (np.isfinite(aligned[i]) and np.isfinite(aligned[j])):
                continue
            if abs(float(aligned[i]) - float(aligned[j])) > w_usd:
                continue
            drop = True
            break
        if not drop:
            keep[i] = True
            lst.append(int(i))
    return keep


def cap_earliest(flag: np.ndarray, formed: np.ndarray, cell: np.ndarray,
                 k: int) -> np.ndarray:
    out = np.zeros(len(flag), bool)
    for g in _cell_groups(cell):
        gi = g[flag[g]]
        if len(gi) == 0:
            continue
        order = gi[np.argsort(formed[gi], kind="stable")]
        out[order[:k]] = True
    return out


def _join_form_aligned(rows180, rows0, names180: list[str], names0: list[str]) -> np.ndarray:
    n_series = int(max(int(rows180.series.max()), int(rows0.series.max()))) + 1
    src = np.full(n_series, np.nan)
    src[rows0.series] = rows0.x[:, _col(names0, VWAP_COL)].astype(np.float64)
    return src[rows180.series]


def _flag(name: str, *, formed, snap_al, form_al, side, cell, theta) -> np.ndarray:
    if name == "snap180_vwap_1x":
        b = cell.astype(np.int64) * 10**9 + _bucket_id(snap_al, theta)
        return causal_first_mask(formed, b)
    if name == "form0_vwap_1x":
        b = cell.astype(np.int64) * 10**9 + _bucket_id(form_al, theta)
        return causal_first_mask(formed, b)
    if name == "form0_vwap_2x":
        b = cell.astype(np.int64) * 10**9 + _bucket_id(form_al, 2.0 * theta)
        return causal_first_mask(formed, b)
    if name == "form_side_time_60":
        tbin = np.floor(np.nan_to_num(formed, nan=1e12) / 60.0).astype(np.int64)
        s = (side > 0).astype(np.int64)
        b = cell.astype(np.int64) * 10**9 + s * 10**7 + tbin
        return causal_first_mask(formed, b)
    if name == "form_side_time_120":
        tbin = np.floor(np.nan_to_num(formed, nan=1e12) / 120.0).astype(np.int64)
        s = (side > 0).astype(np.int64)
        b = cell.astype(np.int64) * 10**9 + s * 10**7 + tbin
        return causal_first_mask(formed, b)
    if name == "form_nms_60_1x":
        al = np.where(np.isfinite(form_al), form_al, snap_al)
        return prefix_nms_mask(formed, side, al, cell, 60.0, theta)
    if name == "after_form_earliest_16":
        b = cell.astype(np.int64) * 10**9 + _bucket_id(form_al, theta)
        return cap_earliest(causal_first_mask(formed, b), formed, cell, 16)
    if name == "after_form_earliest_12":
        b = cell.astype(np.int64) * 10**9 + _bucket_id(form_al, theta)
        return cap_earliest(causal_first_mask(formed, b), formed, cell, 12)
    raise ProbeRefusal(f"unknown live key {name!r}")


CATALOG = (
    "snap180_vwap_1x",
    "form0_vwap_1x",
    "form0_vwap_2x",
    "form_side_time_60",
    "form_side_time_120",
    "form_nms_60_1x",
    "after_form_earliest_16",
    "after_form_earliest_12",
)


def run(matrix_dir: Path, out_path: Path, *, blocks=BLOCKS, n_draw: int = N_DRAW,
        log=print) -> dict:
    rows180 = load_delta_rows(matrix_dir, deltas=(DELTA_SEC,))
    rows0 = load_delta_rows(matrix_dir, deltas=(FORM_DELTA,))
    if not np.isfinite(rows180.y).all():
        raise ProbeRefusal(
            f"{int(np.sum(~np.isfinite(rows180.y)))} non-finite y; expected all finite USD")
    names180 = rows180.feature_names
    _col(names180, VWAP_COL)
    _col(names180, AGE_COL)
    _col(names180, SIDE_COL)
    form_al = _join_form_aligned(rows180, rows0, names180, rows0.feature_names)
    all_days = (int(rows180.day.min()), int(rows180.day.max()))
    report: dict = {
        "schema": SCHEMA, "prereg": __doc__, "matrix_receipt": rows180.matrix_receipt,
        "delta_sec": DELTA_SEC, "n_draw": n_draw, "majority": MAJORITY,
        "max_names": MAX_NAMES, "catalog": list(CATALOG),
        "form0_aligned_coverage": float(np.mean(np.isfinite(form_al))),
        "blocks": {**{k: list(v) for k, v in blocks.items()}, "all": list(all_days)},
        "assets": {},
    }
    for asset in sorted(set(rows180.asset.tolist())):
        theta = _theta(asset)
        report["assets"][asset] = {"rung_usd": RUNG_USD[asset], "theta_usd": theta,
                                   "filters": {}, "survivors": [], "letter": ""}
        for fname in CATALOG:
            report["assets"][asset]["filters"][fname] = {}
            for bname, (lo, hi) in {**blocks, "all": all_days}.items():
                idx = np.flatnonzero(
                    (rows180.asset == asset) & (rows180.day >= lo) & (rows180.day <= hi)
                    & (rows180.delta == DELTA_SEC))
                if len(idx) == 0:
                    continue
                x = rows180.x[idx]
                formed = _formation_sec(x, names180)
                snap_al = x[:, _col(names180, VWAP_COL)].astype(np.float64)
                side = x[:, _col(names180, SIDE_COL)].astype(np.float64)
                cell = rows180.cell[idx]
                flag = _flag(fname, formed=formed, snap_al=snap_al,
                             form_al=form_al[idx], side=side, cell=cell, theta=theta)
                block = _score_mask(rows180, idx, flag, n_draw=n_draw, seed=0)
                report["assets"][asset]["filters"][fname][bname] = block
                log(f"{asset:4s} {fname:24s} {bname:10s} "
                    f"shrink={block['shrink_ceiling_usd_per_asset_day']:7.1f} "
                    f"ret={block['retained_fraction']:.2f} "
                    f"ncell={block['occupancy']['median_eligible_per_cell']:.1f}"
                    f"{'' if not block['typed'] else ' TYPED'}")
        ranked = []
        for fname in CATALOG:
            tr = report["assets"][asset]["filters"][fname].get("train")
            if tr is None:
                continue
            if tr["majority_kept"] and tr["proper_cut"] and (
                    tr["shrink_ceiling_usd_per_asset_day"] >= RUNG_USD[asset]):
                ranked.append((tr["shrink_ceiling_usd_per_asset_day"], fname))
        ranked.sort(reverse=True)
        report["assets"][asset]["survivors"] = [
            {"filter": f, "shrink_ceiling": s} for s, f in ranked]
        report["assets"][asset]["letter"] = (
            ranked[0][1] if ranked else "no majority-and-cut filter")
        if ranked:
            report["assets"][asset]["train_best_forward"] = (
                report["assets"][asset]["filters"][ranked[0][1]].get("forward"))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=1, sort_keys=True))
    return report


def _append_live_cols(root: Path, *, mode: str) -> None:
    x = np.load(root / "x.npy")
    man = json.loads((root / "manifest.json").read_text())
    y = np.sinh(np.load(root / "current_asinh.npy")) * 600.0
    needed = [VWAP_COL, PHASE_ELAPSED_COL, SIDE_COL]
    extra = np.full((len(x), len(needed)), 500.0, np.float32)
    extra[:, needed.index(PHASE_ELAPSED_COL)] = x[:, man["feature_names"].index(ELAPSED_COL)]
    extra[:, needed.index(SIDE_COL)] = 1.0
    day = np.load(root / "day.npy")
    series = np.asarray(np.load(root / "series_id.npy"), str)
    age = x[:, man["feature_names"].index("min_alert_age_sec")]
    phase = x[:, man["feature_names"].index("phase_index")]
    cell = day.astype(np.int64) * 10 + np.nan_to_num(phase, nan=9).astype(np.int64)
    at180 = np.abs(age - DELTA_SEC) <= 2.5
    vwap_i = needed.index(VWAP_COL)
    extra[:, vwap_i] = 16.0 * _theta("HG")
    order = np.argsort(cell, kind="stable")
    keep = order[at180[order]]
    bounds = np.flatnonzero(np.diff(cell[keep])) + 1
    theta = _theta("HG")
    for grp in np.split(keep, bounds):
        if len(grp) == 0:
            continue
        win = grp[int(np.argmax(y[grp]))]
        others = [i for i in grp if i != win]
        extra[series == series[win], vwap_i] = 0.0
        if others:
            late = others[0]
            mask_l = series == series[late]
            extra[mask_l, vwap_i] = 0.0
            extra[mask_l & at180, vwap_i] = 8.0 * theta
            dt = 20.0 if mode != "winner_last" else -20.0
            extra[mask_l, needed.index(PHASE_ELAPSED_COL)] = (
                extra[mask_l, needed.index(PHASE_ELAPSED_COL)] + dt)
    x = np.concatenate([x, extra], axis=1)
    man["feature_names"].extend(needed)
    np.save(root / "x.npy", x)
    (root / "manifest.json").write_text(json.dumps(man))


def selftest() -> int:
    blocks = {"train": (20210601, 20210624), "forward": (20210601, 20210624)}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _synthetic_matrix(tmp / "first", signal=True)
        _append_live_cols(tmp / "first", mode="winner_first")
        first = run(tmp / "first", tmp / "first.json", blocks=blocks, n_draw=40,
                    log=lambda *_: None)
        f0 = first["assets"]["HG"]["filters"]["form0_vwap_1x"]["train"]
        s180 = first["assets"]["HG"]["filters"]["snap180_vwap_1x"]["train"]
        nms = first["assets"]["HG"]["filters"]["form_nms_60_1x"]["train"]
        assert f0["occupancy"]["pick_rate"] > 0.99, f0
        assert nms["occupancy"]["pick_rate"] > 0.99, nms
        assert (s180["occupancy"]["median_eligible_per_cell"]
                >= f0["occupancy"]["median_eligible_per_cell"] - 1e-9), (s180, f0)
        _synthetic_matrix(tmp / "last", signal=True, seed=3)
        _append_live_cols(tmp / "last", mode="winner_last")
        last = run(tmp / "last", tmp / "last.json", blocks=blocks, n_draw=40,
                   log=lambda *_: None)
        nms_last = last["assets"]["HG"]["filters"]["form_nms_60_1x"]["train"]
        assert nms_last["retained_fraction"] < 0.99, nms_last
        _synthetic_matrix(tmp / "red", signal=True)
        _append_live_cols(tmp / "red", mode="winner_first")
        man = json.loads((tmp / "red" / "manifest.json").read_text())
        xred = np.load(tmp / "red" / "x.npy")
        age = xred[:, man["feature_names"].index("min_alert_age_sec")]
        hit = int(np.flatnonzero(np.abs(age - DELTA_SEC) <= 2.5)[0])
        cur = np.load(tmp / "red" / "current_asinh.npy"); cur[hit] = np.nan
        np.save(tmp / "red" / "current_asinh.npy", cur)
        try:
            run(tmp / "red", tmp / "red.json", blocks=blocks, n_draw=2, log=lambda *_: None)
        except ProbeRefusal as exc:
            assert "non-finite" in str(exc), exc
        else:
            raise AssertionError("red fixture (NaN y) was accepted")
    print("selftest OK: formation bucket keeps planted winner; NMS drops later twin; +180 splits; NaN y refused")
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
