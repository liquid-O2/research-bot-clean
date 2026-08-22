#!/usr/bin/env python3
"""Path-dedup — ticket 16 first measure (2026-08-22).

PREREGISTRATION (written before the real run; echoed into the receipt):
- Question: the cell is ~64 near-duplicate G1 zigzags on a handful of
  price paths. Does keeping one name per VWAP-aligned/θ bucket keep
  the cell-max while cutting names? Location proximity already missed
  52-83% of winners. This is post-birth, not a generator rewrite.
- Cluster key: round(disc_auction_session_vwap_aligned_usd / θ).
  θ is TRAIN winner MAE (ticket 09 tight = median ticks × TICK_USD).
- Causal keep: earliest formation in the bucket
  (disc_fvol_phase_scope_elapsed_sec - min_alert_age_sec; session
  elapsed if phase elapsed is absent). y is not used.
- Hindsight max-per-bucket always keeps the cell-max (tautological).
  Reported only as a name-count diagnostic.
- Control: leftover-only (not at finished PDH/PDL, prior VAH/VAL,
  prior LVN, session IB). Expected fat net.
- Bars: TRAIN retained_fraction >= 0.70 and median names <= 16.
  Occupancy vs 200-draw within-cell shuffle of the keep flag.
- 2021 cannot promote. FORWARD of a TRAIN survivor is reported,
  never a knob.

Selftest: python3 tools/probe_path_dedup.py --selftest
Real:     OMP_NUM_THREADS=1 python3 tools/probe_path_dedup.py \\
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
from probe_location_family_screen import (  # noqa: E402
    DELTA_SEC, EXPLORATORY_FAMILIES, FAMILIES, THETA_TICKS, TICK_USD,
    _col, at_family_mask,
)
from probe_oracle_retention_filters import _score_mask  # noqa: E402
from probe_rho_ruler import BLOCKS, RUNG_USD, _cell_groups  # noqa: E402
from probe_trained_accrual import (  # noqa: E402
    ELAPSED_COL, ProbeRefusal, _synthetic_matrix, load_delta_rows,
)

SCHEMA = "QRE2PATHDEDUP1"
N_DRAW = 200
MAJORITY = 0.70
MAX_NAMES = 16.0
VWAP_COL = "disc_auction_session_vwap_aligned_usd"
AGE_COL = "min_alert_age_sec"
PHASE_ELAPSED_COL = "disc_fvol_phase_scope_elapsed_sec"
FINISHED = ("pdh_pdl", "prior_vah_val", "prior_lvn", "ib_session")


def _theta(asset: str) -> float:
    return THETA_TICKS[asset]["tight"] * TICK_USD[asset]


def _formation_sec(x: np.ndarray, names: list[str]) -> np.ndarray:
    age = x[:, _col(names, AGE_COL)].astype(np.float64)
    elapsed_name = PHASE_ELAPSED_COL if PHASE_ELAPSED_COL in names else ELAPSED_COL
    elapsed = x[:, _col(names, elapsed_name)].astype(np.float64)
    return elapsed - age


def _bucket_id(aligned: np.ndarray, theta: float) -> np.ndarray:
    out = np.full(len(aligned), -10**12, np.int64)
    ok = np.isfinite(aligned) & (theta > 0)
    out[ok] = np.rint(aligned[ok] / theta).astype(np.int64)
    return out


def causal_first_mask(formed: np.ndarray, buckets: np.ndarray) -> np.ndarray:
    order = np.argsort(formed, kind="stable")
    seen: set[int] = set()
    keep = np.zeros(len(formed), bool)
    for i in order:
        b = int(buckets[i])
        if b in seen:
            continue
        seen.add(b)
        keep[i] = True
    return keep


def hindsight_max_mask(y: np.ndarray, buckets: np.ndarray) -> np.ndarray:
    keep = np.zeros(len(y), bool)
    order = np.argsort(-y, kind="stable")
    seen: set[int] = set()
    for i in order:
        b = int(buckets[i])
        if b in seen:
            continue
        seen.add(b)
        keep[i] = True
    return keep


def _finished_union(x: np.ndarray, names: list[str], theta: float) -> np.ndarray:
    loc = dict(FAMILIES)
    loc.update(EXPLORATORY_FAMILIES)
    acc = np.zeros(len(x), bool)
    for fam in FINISHED:
        acc |= at_family_mask(x, names, loc[fam], theta)
    return acc


def run(matrix_dir: Path, out_path: Path, *, blocks=BLOCKS, n_draw: int = N_DRAW,
        log=print) -> dict:
    rows = load_delta_rows(matrix_dir, deltas=(DELTA_SEC,))
    if not np.isfinite(rows.y).all():
        raise ProbeRefusal(
            f"{int(np.sum(~np.isfinite(rows.y)))} non-finite y; expected all finite USD")
    _col(rows.feature_names, VWAP_COL)
    _col(rows.feature_names, AGE_COL)
    loc = dict(FAMILIES)
    loc.update(EXPLORATORY_FAMILIES)
    for fam in FINISHED:
        for c in loc[fam]:
            _col(rows.feature_names, c)
    all_days = (int(rows.day.min()), int(rows.day.max()))
    catalog = ("causal_first", "hindsight_max", "leftover_only")
    report: dict = {
        "schema": SCHEMA, "prereg": __doc__, "matrix_receipt": rows.matrix_receipt,
        "delta_sec": DELTA_SEC, "n_draw": n_draw, "majority": MAJORITY,
        "max_names": MAX_NAMES, "cluster": VWAP_COL, "finished": list(FINISHED),
        "blocks": {**{k: list(v) for k, v in blocks.items()}, "all": list(all_days)},
        "assets": {},
    }
    for asset in sorted(set(rows.asset.tolist())):
        theta = _theta(asset)
        report["assets"][asset] = {"rung_usd": RUNG_USD[asset], "theta_usd": theta,
                                   "filters": {}, "letter": ""}
        for fname in catalog:
            report["assets"][asset]["filters"][fname] = {}
            for bname, (lo, hi) in {**blocks, "all": all_days}.items():
                idx = np.flatnonzero(
                    (rows.asset == asset) & (rows.day >= lo) & (rows.day <= hi)
                    & (rows.delta == DELTA_SEC))
                if len(idx) == 0:
                    continue
                x = rows.x[idx]
                names = rows.feature_names
                aligned = x[:, _col(names, VWAP_COL)].astype(np.float64)
                formed = _formation_sec(x, names)
                cell = rows.cell[idx]
                buckets = cell.astype(np.int64) * 10**9 + _bucket_id(aligned, theta)
                if fname == "causal_first":
                    flag = causal_first_mask(formed, buckets)
                elif fname == "hindsight_max":
                    flag = hindsight_max_mask(rows.y[idx], buckets)
                else:
                    flag = ~_finished_union(x, names, theta)
                block = _score_mask(rows, idx, flag, n_draw=n_draw, seed=0)
                n_unique = []
                for g in _cell_groups(cell):
                    n_unique.append(len(set(int(b) for b in buckets[g])))
                block["median_unique_buckets"] = float(np.median(n_unique)) if n_unique else float("nan")
                report["assets"][asset]["filters"][fname][bname] = block
                log(f"{asset:4s} {fname:16s} {bname:10s} "
                    f"shrink={block['shrink_ceiling_usd_per_asset_day']:7.1f} "
                    f"ret={block['retained_fraction']:.2f} "
                    f"ncell={block['occupancy']['median_eligible_per_cell']:.1f} "
                    f"nbucket={block['median_unique_buckets']:.1f}"
                    f"{'' if not block['typed'] else ' TYPED'}")
        tr = report["assets"][asset]["filters"]["causal_first"].get("train")
        letter = "no majority-and-cut filter"
        if tr is not None and tr["majority_kept"] and tr["proper_cut"]:
            letter = "causal_first"
        report["assets"][asset]["letter"] = letter
        if letter == "causal_first":
            report["assets"][asset]["train_best_forward"] = (
                report["assets"][asset]["filters"]["causal_first"].get("forward"))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=1, sort_keys=True))
    return report


def _append_path_cols(root: Path, *, mode: str) -> None:
    x = np.load(root / "x.npy")
    man = json.loads((root / "manifest.json").read_text())
    y = np.sinh(np.load(root / "current_asinh.npy")) * 600.0
    needed = [VWAP_COL, PHASE_ELAPSED_COL]
    loc = dict(FAMILIES)
    loc.update(EXPLORATORY_FAMILIES)
    for fam in FINISHED:
        for c in loc[fam]:
            if c not in needed:
                needed.append(c)
    extra = np.full((len(x), len(needed)), 500.0, np.float32)
    extra[:, needed.index(PHASE_ELAPSED_COL)] = x[:, man["feature_names"].index(ELAPSED_COL)]
    day = np.load(root / "day.npy")
    series = np.asarray(np.load(root / "series_id.npy"), str)
    age = x[:, man["feature_names"].index("min_alert_age_sec")]
    phase = x[:, man["feature_names"].index("phase_index")]
    at_delta = np.abs(age - DELTA_SEC) <= 2.5
    cell = day.astype(np.int64) * 10 + np.nan_to_num(phase, nan=9).astype(np.int64)
    order = np.argsort(cell, kind="stable")
    keep = order[at_delta[order]]
    bounds = np.flatnonzero(np.diff(cell[keep])) + 1
    theta = _theta("HG")
    for grp in np.split(keep, bounds):
        if len(grp) == 0:
            continue
        win = grp[int(np.argmax(y[grp]))]
        others = [i for i in grp if i != win]
        extra[series == series[win], needed.index(VWAP_COL)] = 0.0
        if others:
            late = others[0]
            extra[series == series[late], needed.index(VWAP_COL)] = 0.0
            if mode == "winner_last":
                extra[series == series[win], needed.index(PHASE_ELAPSED_COL)] = (
                    extra[win, needed.index(PHASE_ELAPSED_COL)] + 400.0)
            else:
                extra[series == series[late], needed.index(PHASE_ELAPSED_COL)] = (
                    extra[late, needed.index(PHASE_ELAPSED_COL)] + 400.0)
            for i in others[1:]:
                extra[series == series[i], needed.index(VWAP_COL)] = 8.0 * theta
    x = np.concatenate([x, extra], axis=1)
    man["feature_names"].extend(needed)
    np.save(root / "x.npy", x)
    (root / "manifest.json").write_text(json.dumps(man))


def selftest() -> int:
    blocks = {"train": (20210601, 20210624), "forward": (20210601, 20210624)}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _synthetic_matrix(tmp / "first", signal=True)
        _append_path_cols(tmp / "first", mode="winner_first")
        first = run(tmp / "first", tmp / "first.json", blocks=blocks, n_draw=40,
                    log=lambda *_: None)
        causal = first["assets"]["HG"]["filters"]["causal_first"]["train"]
        hint = first["assets"]["HG"]["filters"]["hindsight_max"]["train"]
        assert causal["occupancy"]["pick_rate"] > 0.99, causal
        assert hint["retained_fraction"] > 0.99, hint
        _synthetic_matrix(tmp / "last", signal=True, seed=3)
        _append_path_cols(tmp / "last", mode="winner_last")
        last = run(tmp / "last", tmp / "last.json", blocks=blocks, n_draw=40,
                   log=lambda *_: None)
        causal_last = last["assets"]["HG"]["filters"]["causal_first"]["train"]
        hint_last = last["assets"]["HG"]["filters"]["hindsight_max"]["train"]
        assert causal_last["retained_fraction"] < 0.99, causal_last
        assert hint_last["retained_fraction"] > 0.99, hint_last
        _synthetic_matrix(tmp / "red", signal=True)
        _append_path_cols(tmp / "red", mode="winner_first")
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
    print("selftest OK: causal-first plants winner-first; drops winner-last; hindsight tautological; NaN y refused")
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
