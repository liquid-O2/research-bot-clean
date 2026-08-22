#!/usr/bin/env python3
"""Side-then-earliest + side-plane — ticket 24 (2026-08-22).

PREREGISTRATION (written before the real run; echoed into the receipt):
- Test 1, ceiling: after live keep-first, cash the earliest keep-first
  name on the cell-max side (side_first). Cash the earliest on the
  other side (wrong_first). Null: random side, then the same earliest
  rule, two-sided cells only (one-sided cells have no call to make).
  TRAIN letters against the per-asset rung. y unused in the keep.
- Test 2, plane: among two-sided cells, pick the side whose earliest
  name has the higher prefix score. Hit rate vs the cell-max side,
  against a shuffle of that side. Clock (phase_remaining_sec) is a
  control and cannot grant 'seen'. Dawes COMBINED and on-matrix
  side-aligned columns are the families. No CatBoost.
- Combined letter: side_carries_seen / side_carries_unseen /
  side_insufficient (Fable). 2021 cannot promote.

Selftest: python3 tools/probe_side_split.py --selftest
Real:     OMP_NUM_THREADS=1 python3 tools/probe_side_split.py \\
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
from probe_confirmation_accrual import (  # noqa: E402
    AccrualRefusal, SCORE_DEFS, compute_scores, resolve_ingredients,
)
from probe_location_family_screen import _col  # noqa: E402
from probe_path_dedup import _formation_sec, _theta  # noqa: E402
from probe_path_dedup_live import (  # noqa: E402
    DELTA_SEC, FORM_DELTA, SIDE_COL, VWAP_COL,
)
from probe_rho_on_dedup import WIDTH_MULT, _keep_idx  # noqa: E402
from probe_rho_ruler import (  # noqa: E402
    BLOCKS, PHASE_REMAINING_COL, RUNG_USD, WALL_HIT_USD, _cell_groups,
)
from probe_trained_accrual import (  # noqa: E402
    ELAPSED_COL, ProbeRefusal, _cell_pick, load_delta_rows,
)

SCHEMA = "QRE2SIDESPLIT1"
N_DRAW = 40
SHUFFLE_Q = 0.95
PLANE_COLS = (
    "disc_auction_session_directional_profile_skewness",
    "disc_auction_phase_poc_aligned_usd",
    "disc_auction_phase_vwap_aligned_usd",
    "disc_ib_phase_directional_break_age_sec",
    "disc_eclock_n1024_size_count_divergence",
    "disc_tclock_n512_aligned_flow_fraction",
    "w120_add_side_size",
    "disc_prior_high_aligned_usd",
    "disc_prior_low_aligned_usd",
)


def _usd(score: np.ndarray, y: np.ndarray, cell: np.ndarray, day: np.ndarray,
         elapsed: np.ndarray, occupancy: np.ndarray, days: list[int]) -> float:
    pick = _cell_pick(score, y, cell, day, elapsed, occupancy, -np.inf)
    return float(np.mean([pick["all"].get(d, 0.0) for d in days]))


def _cash_idx(pick: np.ndarray, y: np.ndarray, cell: np.ndarray, day: np.ndarray,
              elapsed: np.ndarray, occupancy: np.ndarray, days: list[int]) -> float:
    score = np.full(len(y), -np.inf)
    ok = pick >= 0
    score[pick[ok]] = 1.0
    return _usd(score, y, cell, day, elapsed, occupancy, days)


def _dawes(x: np.ndarray, names: list[str]) -> np.ndarray | None:
    if SIDE_COL not in names:
        return None
    try:
        resolved, _ = resolve_ingredients(names, SCORE_DEFS)
    except AccrualRefusal:
        return None
    side = x[:, _col(names, SIDE_COL)].astype(np.float64)
    return compute_scores(x.astype(np.float64), side, resolved)["COMBINED"]


def _earliest(formed: np.ndarray, mask: np.ndarray) -> int:
    if not np.any(mask):
        return -1
    idx = np.flatnonzero(mask)
    return int(idx[np.argmin(formed[idx])])


def _kth_earliest(formed: np.ndarray, mask: np.ndarray, k: int) -> int:
    if int(np.sum(mask)) <= k:
        return -1
    idx = np.flatnonzero(mask)
    order = idx[np.argsort(formed[idx], kind="stable")]
    return int(order[k])


def _mdd(daily: dict[int, float]) -> float:
    peak = 0.0
    mdd = 0.0
    cum = 0.0
    for d in sorted(daily):
        cum += float(daily[d])
        peak = max(peak, cum)
        mdd = min(mdd, cum - peak)
    return float(-mdd)


def _letter(side_first: float, rung: float, plane_seen: bool) -> str:
    if not np.isfinite(side_first) or side_first < rung:
        return "side_insufficient"
    return "side_carries_seen" if plane_seen else "side_carries_unseen"


def _block(y, side, cell, day, elapsed, occupancy, formed, scores: dict[str, np.ndarray],
           rung: float, rng: np.random.Generator, n_draw: int) -> dict:
    days = sorted({int(d) for d in day})
    groups = _cell_groups(cell)
    n = len(y)
    first_win = np.full(n, False)
    first_wrong = np.full(n, False)
    kth = {1: np.full(n, False), 2: np.full(n, False)}
    two_sided = np.zeros(len(groups), bool)
    pair: dict[str, list[tuple[float, float]]] = {name: [] for name in scores}
    truth_side: list[int] = []
    n_two = 0
    for gi, g in enumerate(groups):
        gs = side[g] > 0
        long_m = np.zeros(n, bool); long_m[g[gs]] = True
        short_m = np.zeros(n, bool); short_m[g[~gs]] = True
        has_l, has_s = bool(np.any(long_m)), bool(np.any(short_m))
        two_sided[gi] = has_l and has_s
        win_i = int(g[np.argmax(y[g])])
        wside = 1 if side[win_i] > 0 else -1
        wm = long_m if wside > 0 else short_m
        om = short_m if wside > 0 else long_m
        fw = _earliest(formed, wm)
        fo = _earliest(formed, om)
        if fw >= 0:
            first_win[fw] = True
        if fo >= 0:
            first_wrong[fo] = True
        for k in (1, 2):
            ik = _kth_earliest(formed, wm, k)
            if ik >= 0:
                kth[k][ik] = True
        if not two_sided[gi]:
            continue
        n_two += 1
        il = _earliest(formed, long_m)
        ish = _earliest(formed, short_m)
        truth_side.append(wside)
        for name, sc in scores.items():
            pair[name].append((float(sc[il]), float(sc[ish])))
    side_first = _cash_idx(np.flatnonzero(first_win), y, cell, day, elapsed, occupancy, days)
    wrong_first = _cash_idx(np.flatnonzero(first_wrong), y, cell, day, elapsed, occupancy, days)
    side_k = {}
    for k, flag in kth.items():
        side_k[str(k + 1)] = _cash_idx(np.flatnonzero(flag), y, cell, day, elapsed,
                                       occupancy, days)
    nulls = []
    for _ in range(n_draw):
        pick = np.full(n, False)
        for gi, g in enumerate(groups):
            gs = side[g] > 0
            long_m = np.zeros(n, bool); long_m[g[gs]] = True
            short_m = np.zeros(n, bool); short_m[g[~gs]] = True
            if two_sided[gi]:
                call = 1 if rng.random() < 0.5 else -1
            else:
                call = 1 if np.any(long_m) else -1
            wm = long_m if call > 0 else short_m
            fw = _earliest(formed, wm)
            if fw >= 0:
                pick[fw] = True
        nulls.append(_cash_idx(np.flatnonzero(pick), y, cell, day, elapsed, occupancy, days))
    null_mean = float(np.mean(nulls)) if nulls else float("nan")
    null_p975 = float(np.quantile(nulls, 0.975)) if nulls else float("nan")
    plane = {}
    truth = np.asarray(truth_side, np.int64)
    plane_seen = False
    for name, pairs in pair.items():
        if n_two == 0:
            plane[name] = {"hit_rate": float("nan"), "shuffle_p95": float("nan"),
                           "beats_shuffle": False, "n_two_sided": 0}
            continue
        pred = np.asarray([1 if a >= b else -1 for a, b in pairs], np.int64)
        real = float(np.mean(pred == truth))
        sh = []
        for _ in range(n_draw):
            sh.append(float(np.mean(pred == rng.permutation(truth))))
        band = float(np.quantile(sh, SHUFFLE_Q))
        beats = bool(real > band and real >= 0.60)
        plane[name] = {"hit_rate": real, "shuffle_p95": band,
                       "beats_shuffle": beats, "n_two_sided": n_two}
        if beats and name != "clock":
            plane_seen = True
    pick = _cell_pick(np.where(first_win, 1.0, -np.inf), y, cell, day, elapsed,
                      occupancy, -np.inf)
    mdd = _mdd(pick["all"])
    wall_frac = float(np.mean(y[first_win] <= WALL_HIT_USD)) if np.any(first_win) else float("nan")
    n_cells = len(groups)
    return {
        "days": len(days), "n_cells": n_cells,
        "frac_two_sided": float(np.mean(two_sided)) if n_cells else float("nan"),
        "ceiling_usd": _usd(y, y, cell, day, elapsed, occupancy, days),
        "side_first_usd": float(side_first),
        "wrong_first_usd": float(wrong_first),
        "side_k_usd": side_k,
        "random_side_usd": null_mean,
        "random_side_p975": null_p975,
        "clears_random": bool(np.isfinite(side_first) and np.isfinite(null_p975)
                              and side_first > null_p975),
        "side_first_mdd_usd": mdd,
        "wall_frac_first_win": wall_frac,
        "rung_usd": float(rung),
        "plane": plane,
        "plane_seen": bool(plane_seen),
        "letter": _letter(float(side_first), rung, plane_seen),
    }


def run(matrix_dir: Path, out_path: Path, *, blocks=BLOCKS, n_draw: int = N_DRAW,
        log=print) -> dict:
    rows180 = load_delta_rows(matrix_dir, deltas=(DELTA_SEC,))
    rows0 = load_delta_rows(matrix_dir, deltas=(FORM_DELTA,))
    if not np.isfinite(rows180.y).all():
        raise ProbeRefusal(
            f"{int(np.sum(~np.isfinite(rows180.y)))} non-finite y; expected all finite USD")
    names = rows180.feature_names
    if SIDE_COL not in names:
        raise ProbeRefusal(f"missing {SIDE_COL!r}")
    all_days = (int(rows180.day.min()), int(rows180.day.max()))
    report: dict = {
        "schema": SCHEMA, "prereg": __doc__, "matrix_receipt": rows180.matrix_receipt,
        "delta_sec": DELTA_SEC, "n_draw": n_draw, "width_mult": WIDTH_MULT,
        "blocks": {**{k: list(v) for k, v in blocks.items()}, "all": list(all_days)},
        "assets": {},
    }
    rng = np.random.default_rng(0)
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
            y = rows180.y[kept]
            cell = rows180.cell[kept]
            day = rows180.day[kept]
            elapsed = rows180.elapsed[kept]
            occupancy = rows180.occupancy[kept]
            formed = _formation_sec(rows180.x[kept], names)
            side = rows180.x[kept, _col(names, SIDE_COL)].astype(np.float64)
            scores: dict[str, np.ndarray] = {}
            if PHASE_REMAINING_COL in names:
                scores["clock"] = rows180.x[kept, _col(names, PHASE_REMAINING_COL)].astype(np.float64)
            dawes = _dawes(rows180.x[kept], names)
            if dawes is not None:
                scores["dawes"] = dawes
            for c in PLANE_COLS:
                if c in names:
                    scores[c] = rows180.x[kept, _col(names, c)].astype(np.float64)
            blk = _block(y, side, cell, day, elapsed, occupancy, formed, scores,
                         RUNG_USD[asset], rng, n_draw)
            report["assets"][asset][bname] = blk
            log(f"{asset:4s} {bname:10s} letter={blk['letter']:20s} "
                f"first={blk['side_first_usd']:.0f} wrong={blk['wrong_first_usd']:.0f} "
                f"rand={blk['random_side_usd']:.0f} two={blk['frac_two_sided']:.2f} "
                f"plane={blk['plane_seen']}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=1, sort_keys=True))
    return report


def _plant(root: Path) -> None:
    names = ["min_alert_age_sec", "phase_index", ELAPSED_COL,
             "disc_fvol_phase_scope_elapsed_sec", PHASE_REMAINING_COL, VWAP_COL, SIDE_COL]
    theta = _theta("HG")
    specs = [
        (900.0, 280.0, 0.0, 1.0),
        (700.0, 680.0, 8.0 * theta, 1.0),
        (-900.0, 1080.0, 16.0 * theta, 1.0),
        (-300.0, 380.0, 24.0 * theta, -1.0),
        (-850.0, 580.0, 32.0 * theta, -1.0),
    ]
    xs, days, assets, series, ys, occs = [], [], [], [], [], []
    for d in (20210610, 20210611):
        for s, (yv, el180, vwap, sd) in enumerate(specs):
            for age in (0.0, 180.0):
                elapsed = el180 - 180.0 + age
                rem = 10000.0 - elapsed
                xs.append([age, 0.0, elapsed, elapsed, rem, vwap, sd])
                days.append(d); assets.append("HG"); series.append(f"s{d}_{s}")
                ys.append(yv); occs.append(600.0)
    root.mkdir(parents=True, exist_ok=True)
    np.save(root / "x.npy", np.asarray(xs, np.float32))
    np.save(root / "day.npy", np.asarray(days, np.int64))
    np.save(root / "asset.npy", np.asarray(assets))
    np.save(root / "series_id.npy", np.asarray(series))
    np.save(root / "current_asinh.npy", np.arcsinh(np.asarray(ys) / 600.0))
    np.save(root / "occupancy_sec.npy", np.asarray(occs, np.float64))
    (root / "manifest.json").write_text(json.dumps(
        {"feature_names": names, "rows": len(xs), "matrix_receipt_sha256": "synthetic"}))


def selftest() -> int:
    blocks = {"train": (20210610, 20210709)}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _plant(tmp / "p")
        rep = run(tmp / "p", tmp / "p.json", blocks=blocks, n_draw=8, log=lambda *_: None)
        tr = rep["assets"]["HG"]["train"]
        assert abs(tr["side_first_usd"] - 900.0) < 1.0, tr["side_first_usd"]
        assert abs(tr["wrong_first_usd"] - (-300.0)) < 1.0, tr["wrong_first_usd"]
        assert tr["frac_two_sided"] == 1.0, tr["frac_two_sided"]
        _plant(tmp / "red")
        cur = np.load(tmp / "red" / "current_asinh.npy"); cur[1] = np.nan
        np.save(tmp / "red" / "current_asinh.npy", cur)
        try:
            run(tmp / "red", tmp / "red.json", blocks=blocks, n_draw=2, log=lambda *_: None)
        except ProbeRefusal as exc:
            assert "non-finite" in str(exc), exc
        else:
            raise AssertionError("NaN y was accepted")
    print("selftest OK: side_first cashes 900, wrong_first cashes -300, NaN refused")
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
