#!/usr/bin/env python3
"""S6 occupancy — ticket 10 of design/entry_reset (2026-08-22).

PREREGISTRATION (written before the real run; echoed into the receipt):
- Question: at stored Delta ages, do oracle-picked series (argmax y in the cell)
  over-represent S6-complete more than non-picks, above a within-cell shuffle of
  the flag? S6-complete is geometric return AND defense (quote rebuilt after
  depletion AND memory reload), not retest_seen alone.
- Rows: matrix row nearest each Delta in {0,30,60,120,180,240,290}s per series.
- Flag S6: disc_state_retest_seen==1 AND disc_state_invalidated_seen==0 AND
  disc_quote_h30_rebuild_after_depletion_count>=1 AND
  disc_memory_z2_defense_reload_count>=1. Columns verified on matrix 7e9e2588.
- Flag GEOMETRY: disc_state_retest_seen==1 only. Never labelled S6.
- Matched null: the flag permuted within each cell (keeps base rate and cell
  structure; destroys pick-vs-flag association). 200 draws; 2.5/97.5 band.
- Kill: on TRAIN and THRESHOLD, at every age, S6 pick-rate minus non-pick-rate
  sits inside the shuffle band. Then S6 carries no within-cell information at
  Delta<=290s on that asset; ticket 08 is closed for that asset, scoped
  "S6 from existing quote/memory columns, Delta<=290s, 2021 sample".
- Truncation: fraction of series whose last stored row is not S6-complete.
  The state series stops at formation+601s; incomplete vs truncated is the
  same bit on this matrix.
- Degenerate: pick rate <0.02 at every age is typed "S6 does not complete
  inside the snapshot grid", not a null.
- Tier: DIAGNOSTIC. No selector. No fit. Does not promote.

Selftest: python3 tools/probe_s6_occupancy.py --selftest
Real:     OMP_NUM_THREADS=1 python3 tools/probe_s6_occupancy.py \\
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
    DELTAS, ProbeRefusal, _synthetic_matrix, load_delta_rows,
    shuffle_within_groups,
)
from probe_rho_ruler import BLOCKS  # noqa: E402

SCHEMA = "QRE2S6OCC1"
N_DRAW = 200
S6_RETEST = "disc_state_retest_seen"
S6_INVALID = "disc_state_invalidated_seen"
S6_REBUILD = "disc_quote_h30_rebuild_after_depletion_count"
S6_RELOAD = "disc_memory_z2_defense_reload_count"
S6_COLS = (S6_RETEST, S6_INVALID, S6_REBUILD, S6_RELOAD)


def _col(names: list[str], name: str) -> int:
    if name not in names:
        raise ProbeRefusal(f"matrix lacks required column {name!r}; have {len(names)} names")
    return names.index(name)


def s6_complete_mask(x: np.ndarray, names: list[str]) -> np.ndarray:
    """Geometry return plus defense. WHY join: retest_seen is a nested price latch."""
    retest = x[:, _col(names, S6_RETEST)] >= 0.5
    valid = x[:, _col(names, S6_INVALID)] < 0.5
    rebuild = x[:, _col(names, S6_REBUILD)] >= 1.0
    reload = x[:, _col(names, S6_RELOAD)] >= 1.0
    return retest & valid & rebuild & reload


def geometry_mask(x: np.ndarray, names: list[str]) -> np.ndarray:
    return x[:, _col(names, S6_RETEST)] >= 0.5


def _cell_groups(cell: np.ndarray) -> list[np.ndarray]:
    order = np.argsort(cell, kind="stable")
    bounds = np.flatnonzero(np.diff(cell[order])) + 1
    return np.split(order, bounds)


def occupancy_rates(flag: np.ndarray, y: np.ndarray, cell: np.ndarray, *,
                    n_draw: int, rng: np.random.Generator) -> dict:
    """Pick vs non-pick flag rate, plus within-cell shuffle band of the pick rate."""
    if not np.isfinite(y).all():
        bad = int(np.sum(~np.isfinite(y)))
        raise ProbeRefusal(f"{bad} non-finite y values; expected all finite USD")
    groups = _cell_groups(cell)
    picks = np.array([int(g[int(np.argmax(y[g]))]) for g in groups], np.int64)
    pick_flag = flag[picks]
    non = np.ones(len(flag), bool)
    non[picks] = False
    pick_rate = float(pick_flag.mean()) if len(picks) else float("nan")
    non_rate = float(flag[non].mean()) if non.any() else float("nan")
    diff = pick_rate - non_rate
    shuf_pick = np.empty(n_draw, np.float64)
    shuf_diff = np.empty(n_draw, np.float64)
    f = flag.astype(np.float64)
    for i in range(n_draw):
        perm = shuffle_within_groups(f, cell, rng)
        shuf_pick[i] = float(perm[picks].mean())
        shuf_diff[i] = float(perm[picks].mean() - perm[non].mean()) if non.any() else 0.0
    plo, phi = float(np.quantile(shuf_pick, 0.025)), float(np.quantile(shuf_pick, 0.975))
    dlo, dhi = float(np.quantile(shuf_diff, 0.025)), float(np.quantile(shuf_diff, 0.975))
    return {
        "n_cells": int(len(groups)),
        "n_rows": int(len(flag)),
        "base_rate": float(flag.mean()),
        "pick_rate": pick_rate,
        "nonpick_rate": non_rate,
        "pick_minus_nonpick": float(diff),
        "shuffle_pick_rate_p025": plo,
        "shuffle_pick_rate_p975": phi,
        "shuffle_diff_p025": dlo,
        "shuffle_diff_p975": dhi,
        "pick_rate_inside_shuffle_band": bool(plo <= pick_rate <= phi),
        "diff_inside_shuffle_band": bool(dlo <= diff <= dhi),
    }


def _truncation_rate(flag: np.ndarray, series: np.ndarray, delta: np.ndarray) -> float:
    """Fraction of series whose last stored Delta row is not S6-complete."""
    last = {}
    for i, (s, d) in enumerate(zip(series, delta)):
        prev = last.get(int(s))
        if prev is None or d >= prev[0]:
            last[int(s)] = (float(d), bool(flag[i]))
    if not last:
        return float("nan")
    return float(sum(1 for _, ok in last.values() if not ok) / len(last))


def run_block(rows, idx: np.ndarray, *, n_draw: int, seed: int) -> dict:
    x, y, cell = rows.x[idx], rows.y[idx], rows.cell[idx]
    delta, series = rows.delta[idx], rows.series[idx]
    names = rows.feature_names
    s6 = s6_complete_mask(x, names)
    geo = geometry_mask(x, names)
    rng = np.random.default_rng(seed)
    ages = {}
    for age in DELTAS:
        m = delta == age
        if not m.any():
            continue
        ages[f"{age:.0f}"] = {
            "s6": occupancy_rates(s6[m], y[m], cell[m], n_draw=n_draw, rng=rng),
            "geometry": occupancy_rates(geo[m], y[m], cell[m], n_draw=n_draw, rng=rng),
        }
    s6_pick = [ages[k]["s6"]["pick_rate"] for k in ages]
    typed = None
    if s6_pick and max(s6_pick) < 0.02:
        typed = "S6 does not complete inside the snapshot grid"
    return {
        "ages": ages,
        "truncation_or_incomplete_rate": _truncation_rate(s6, series, delta),
        "typed_degenerate": typed,
        "n_rows": int(len(idx)),
    }


def run(matrix_dir: Path, out_path: Path, *, blocks=BLOCKS, n_draw: int = N_DRAW,
        log=print) -> dict:
    rows = load_delta_rows(matrix_dir, deltas=DELTAS)
    for name in S6_COLS:
        _col(rows.feature_names, name)
    all_days = (int(rows.day.min()), int(rows.day.max()))
    report: dict = {
        "schema": SCHEMA, "prereg": __doc__, "matrix_receipt": rows.matrix_receipt,
        "n_draw": n_draw, "deltas": list(DELTAS),
        "blocks": {**{k: list(v) for k, v in blocks.items()}, "all": list(all_days)},
        "assets": {},
    }
    for asset in sorted(set(rows.asset.tolist())):
        report["assets"][asset] = {}
        for bname, (lo, hi) in {**blocks, "all": all_days}.items():
            idx = np.flatnonzero((rows.asset == asset) & (rows.day >= lo) & (rows.day <= hi))
            if len(idx) == 0:
                continue
            block = run_block(rows, idx, n_draw=n_draw, seed=0)
            report["assets"][asset][bname] = block
            a180 = block["ages"].get("180", {})
            s6 = a180.get("s6", {})
            log(f"{asset:4s} {bname:10s} n={block['n_rows']:7d} "
                f"s6_pick180={s6.get('pick_rate', float('nan')):.3f} "
                f"geo_pick180={a180.get('geometry', {}).get('pick_rate', float('nan')):.3f} "
                f"trunc={block['truncation_or_incomplete_rate']:.3f}"
                f"{'' if block['typed_degenerate'] is None else ' TYPED:' + block['typed_degenerate']}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=1, sort_keys=True))
    return report


def _append_s6_columns(root: Path, *, mode: str) -> None:
    """mode='planted': S6 iff y >= cell 80th pct. mode='geometry': retest random, defense off."""
    x = np.load(root / "x.npy")
    man = json.loads((root / "manifest.json").read_text())
    y = np.sinh(np.load(root / "current_asinh.npy")) * 600.0
    day = np.load(root / "day.npy")
    phase = x[:, man["feature_names"].index("phase_index")]
    cell = day.astype(np.int64) * 10 + np.nan_to_num(phase, nan=9).astype(np.int64)
    extra = np.zeros((len(x), 4), np.float32)
    if mode == "planted":
        order = np.argsort(cell, kind="stable")
        bounds = np.flatnonzero(np.diff(cell[order])) + 1
        for grp in np.split(order, bounds):
            thr = np.quantile(y[grp], 0.80)
            hit = y[grp] >= thr
            extra[grp, 0] = hit.astype(np.float32)
            extra[grp, 2] = hit.astype(np.float32)
            extra[grp, 3] = hit.astype(np.float32)
    elif mode == "geometry":
        rng = np.random.default_rng(3)
        extra[:, 0] = (rng.random(len(x)) < 0.45).astype(np.float32)
    else:
        raise ProbeRefusal(f"unknown s6 plant mode {mode!r}")
    x = np.concatenate([x, extra], axis=1)
    man["feature_names"].extend(list(S6_COLS))
    np.save(root / "x.npy", x)
    (root / "manifest.json").write_text(json.dumps(man))


def selftest() -> int:
    blocks = {"only": (20210601, 20210624)}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _synthetic_matrix(tmp / "planted", signal=True)
        _append_s6_columns(tmp / "planted", mode="planted")
        rep = run(tmp / "planted", tmp / "planted.json", blocks=blocks, n_draw=40,
                  log=lambda *_: None)
        blk = rep["assets"]["HG"]["only"]["ages"]["180"]["s6"]
        assert abs(blk["pick_rate"] - 1.0) < 1e-9, blk
        assert blk["shuffle_pick_rate_p025"] < 0.95, blk
        _synthetic_matrix(tmp / "geo", signal=True, seed=11)
        _append_s6_columns(tmp / "geo", mode="geometry")
        geo = run(tmp / "geo", tmp / "geo.json", blocks=blocks, n_draw=40, log=lambda *_: None)
        g = geo["assets"]["HG"]["only"]["ages"]["180"]["geometry"]
        assert g["pick_rate_inside_shuffle_band"], g
        s6g = geo["assets"]["HG"]["only"]["ages"]["180"]["s6"]
        assert s6g["pick_rate"] < 0.02, s6g
        _synthetic_matrix(tmp / "red", signal=True)
        _append_s6_columns(tmp / "red", mode="planted")
        cur = np.load(tmp / "red" / "current_asinh.npy"); cur[7] = np.nan
        np.save(tmp / "red" / "current_asinh.npy", cur)
        try:
            run(tmp / "red", tmp / "red.json", blocks=blocks, n_draw=2, log=lambda *_: None)
        except ProbeRefusal as exc:
            assert "non-finite" in str(exc), exc
        else:
            raise AssertionError("red fixture (NaN y) was accepted")
    print("selftest OK: planted S6 pick_rate=1.0; geometry-only inside shuffle band; "
          "NaN-y refused")
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
