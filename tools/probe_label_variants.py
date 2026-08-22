#!/usr/bin/env python3
"""Label variant screen — ticket 23 (2026-08-22).

PREREGISTRATION (written before the real run; echoed into the receipt):
- Question: the generator already holds goal-grade names. Which LABELS,
  when ranked perfectly and cashed as the live-executable name's y,
  still print the per-asset rung on the live-deduped cell? Which of
  those labels can a prefix-only score actually rank?
- Keep: prefix keep-first, ticket 20 widths (HG 2θ, NKD 1θ, SI 1θ).
  y unused in the keep.
- Alignment: argmax(label) per cell, cash live y, `_cell_pick`.
  Binary labels: mean over draws of a uniform pick among positives,
  skip the cell if none. That is the classifier-enough ceiling.
- Mutant: y_cell_z must cash the same as raw_y to the cent.
- Null: within-cell shuffle of the label, then the same pick, cash y.
- Learnability: Spearman of prefix scores vs the label, vs a shuffle
  of the label. Scores cash y as a baseline (independent of label).
- TRAIN writes the letter. THRESHOLD/FORWARD reported, never knobs.
  2021 cannot promote. No CatBoost.

Letters:
  cannot_reach         TRAIN alignment < rung
  aligned_chance       alignment >= rung, no prefix Spearman above shuffle
  aligned_separable    alignment >= rung, at least one prefix Spearman above shuffle

Selftest: python3 tools/probe_label_variants.py --selftest
Real:     OMP_NUM_THREADS=1 python3 tools/probe_label_variants.py \\
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
from probe_path_dedup import _formation_sec, _theta, causal_first_mask  # noqa: E402
from probe_path_dedup_live import (  # noqa: E402
    DELTA_SEC, FORM_DELTA, SIDE_COL, VWAP_COL, _bucket_id, _join_form_aligned,
)
from probe_rho_on_dedup import WIDTH_MULT, _keep_idx  # noqa: E402
from probe_rho_ruler import (  # noqa: E402
    BLOCKS, PHASE_REMAINING_COL, RUNG_USD, _cell_groups,
    _mean_within_cell_spearman,
)
from probe_trained_accrual import (  # noqa: E402
    ELAPSED_COL, ProbeRefusal, _cell_pick, load_delta_rows, standardize_by_cell,
)

SCHEMA = "QRE2LABVAR1"
N_DRAW = 40
WINNER_MIN = 600.0
SHUFFLE_Q = 0.95


def _usd(score: np.ndarray, y: np.ndarray, cell: np.ndarray, day: np.ndarray,
         elapsed: np.ndarray, occupancy: np.ndarray, days: list[int]) -> float:
    pick = _cell_pick(score, y, cell, day, elapsed, occupancy, -np.inf)
    return float(np.mean([pick["all"].get(d, 0.0) for d in days]))


def _ols_apply(y: np.ndarray, x: np.ndarray, coef: tuple[float, float]) -> np.ndarray:
    a, b = coef
    xx = np.where(np.isfinite(x), x, 0.0)
    return y - (a + b * xx)


def _ols_fit(y: np.ndarray, x: np.ndarray) -> tuple[float, float]:
    ok = np.isfinite(y) & np.isfinite(x)
    if int(ok.sum()) < 8:
        return 0.0, 0.0
    A = np.column_stack([np.ones(int(ok.sum())), x[ok]])
    coef, *_ = np.linalg.lstsq(A, y[ok], rcond=None)
    return float(coef[0]), float(coef[1])


def _random_positive_usd(flag: np.ndarray, y: np.ndarray, cell: np.ndarray,
                         day: np.ndarray, elapsed: np.ndarray, occupancy: np.ndarray,
                         days: list[int], rng: np.random.Generator,
                         n_draw: int) -> float:
    vals = []
    for _ in range(n_draw):
        score = np.full(len(flag), -np.inf)
        for g in _cell_groups(cell):
            pos = g[flag[g]]
            if len(pos) == 0:
                continue
            score[int(rng.choice(pos))] = 1.0
        vals.append(_usd(score, y, cell, day, elapsed, occupancy, days))
    return float(np.mean(vals))


def _dawes(x: np.ndarray, names: list[str]) -> np.ndarray | None:
    if SIDE_COL not in names:
        return None
    try:
        resolved, _ = resolve_ingredients(names, SCORE_DEFS)
    except AccrualRefusal:
        return None
    side = x[:, _col(names, SIDE_COL)].astype(np.float64)
    return compute_scores(x.astype(np.float64), side, resolved)["COMBINED"]


def _letter(align: float, rung: float, separable: bool) -> str:
    if not np.isfinite(align) or align < rung:
        return "cannot_reach"
    return "aligned_separable" if separable else "aligned_chance"


def _spearman_beats_shuffle(score: np.ndarray, label: np.ndarray,
                            groups: list[np.ndarray], rng: np.random.Generator,
                            n_draw: int) -> dict:
    real = _mean_within_cell_spearman(score, label, groups)
    nulls = []
    for _ in range(n_draw):
        sh = label.copy()
        for g in groups:
            sh[g] = label[g][rng.permutation(len(g))]
        nulls.append(_mean_within_cell_spearman(score, sh, groups))
    band = float(np.nanquantile(nulls, SHUFFLE_Q)) if nulls else float("nan")
    return {"spearman": float(real), "shuffle_p95": band,
            "beats_shuffle": bool(np.isfinite(real) and np.isfinite(band) and real > band)}


def _label_pack(y: np.ndarray, remaining: np.ndarray, cell: np.ndarray,
                cluster_max: np.ndarray, resid_coef: tuple[float, float]) -> dict[str, np.ndarray]:
    rem = np.maximum(np.where(np.isfinite(remaining), remaining, 1.0), 1.0)
    return {
        "raw_y": y,
        "y_cell_z": standardize_by_cell(y, cell),
        "clock_resid": _ols_apply(y, remaining, resid_coef),
        "capture_remaining": y / rem,
        "cluster_max": cluster_max,
        "good_enough": (y >= WINNER_MIN).astype(np.float64),
        "sign_y": (y > 0.0).astype(np.float64),
    }


def _cluster_max(y: np.ndarray, buckets: np.ndarray) -> np.ndarray:
    mx: dict[int, float] = {}
    for i, b in enumerate(buckets):
        bb = int(b)
        v = float(y[i])
        mx[bb] = v if bb not in mx else max(mx[bb], v)
    return np.asarray([mx[int(b)] for b in buckets], np.float64)


def _block_report(y, cell, day, elapsed, occupancy, remaining, formed,
                  cluster_max, dawes, resid_coef, rung, rng, n_draw) -> dict:
    days = sorted({int(d) for d in day})
    groups = _cell_groups(cell)
    labels = _label_pack(y, remaining, cell, cluster_max, resid_coef)
    scores = {"peer_early": -formed.astype(np.float64),
              "clock_only": remaining.astype(np.float64)}
    if dawes is not None:
        scores["dawes"] = dawes
    score_usd = {k: _usd(v, y, cell, day, elapsed, occupancy, days) for k, v in scores.items()}
    cells_ge = []
    for g in groups:
        cells_ge.append(bool(np.any(y[g] >= WINNER_MIN)))
    out_labels = {}
    for name, lab in labels.items():
        if name in ("good_enough", "sign_y"):
            flag = lab > 0.5
            align = _random_positive_usd(flag, y, cell, day, elapsed, occupancy,
                                         days, rng, n_draw)
            shufs = []
            for _ in range(n_draw):
                sh = flag.copy()
                for g in groups:
                    sh[g] = flag[g][rng.permutation(len(g))]
                shufs.append(_random_positive_usd(sh, y, cell, day, elapsed,
                                                  occupancy, days, rng, 1))
            shuffle_usd = float(np.mean(shufs))
            same = float("nan")
        else:
            align = _usd(lab, y, cell, day, elapsed, occupancy, days)
            shufs = []
            for _ in range(n_draw):
                sh = lab.copy()
                for g in groups:
                    sh[g] = lab[g][rng.permutation(len(g))]
                shufs.append(_usd(sh, y, cell, day, elapsed, occupancy, days))
            shuffle_usd = float(np.mean(shufs))
            n_same = 0
            n_c = 0
            for g in groups:
                if len(g) == 0:
                    continue
                n_c += 1
                n_same += int(int(np.argmax(lab[g])) == int(np.argmax(y[g])))
            same = n_same / n_c if n_c else float("nan")
        learn = {sk: _spearman_beats_shuffle(sv, lab, groups, rng, n_draw)
                 for sk, sv in scores.items()}
        separable = any(v["beats_shuffle"] for v in learn.values())
        out_labels[name] = {
            "align_usd": float(align), "shuffle_usd": float(shuffle_usd),
            "same_as_ymax_frac": None if not np.isfinite(same) else float(same),
            "letter": _letter(float(align), rung, separable),
            "learnability": learn,
        }
    raw_a = out_labels["raw_y"]["align_usd"]
    z_a = out_labels["y_cell_z"]["align_usd"]
    if abs(raw_a - z_a) > 0.01:
        raise ProbeRefusal(
            f"y_cell_z cash {z_a} != raw_y cash {raw_a}; monotone mutant failed")
    sizes = [len(g) for g in groups]
    return {
        "days": len(days), "n_cells": len(groups),
        "n_per_cell_median": float(np.median(sizes)) if sizes else float("nan"),
        "ceiling_usd": _usd(y, y, cell, day, elapsed, occupancy, days),
        "frac_cells_with_y_ge_600": float(np.mean(cells_ge)) if cells_ge else float("nan"),
        "rung_usd": float(rung), "score_usd": score_usd, "labels": out_labels,
    }


def run(matrix_dir: Path, out_path: Path, *, blocks=BLOCKS, n_draw: int = N_DRAW,
        log=print) -> dict:
    rows180 = load_delta_rows(matrix_dir, deltas=(DELTA_SEC,))
    rows0 = load_delta_rows(matrix_dir, deltas=(FORM_DELTA,))
    if not np.isfinite(rows180.y).all():
        raise ProbeRefusal(
            f"{int(np.sum(~np.isfinite(rows180.y)))} non-finite y; expected all finite USD")
    names = rows180.feature_names
    if PHASE_REMAINING_COL not in names:
        raise ProbeRefusal(f"missing {PHASE_REMAINING_COL!r}")
    all_days = (int(rows180.day.min()), int(rows180.day.max()))
    report: dict = {
        "schema": SCHEMA, "prereg": __doc__, "matrix_receipt": rows180.matrix_receipt,
        "delta_sec": DELTA_SEC, "n_draw": n_draw, "width_mult": WIDTH_MULT,
        "blocks": {**{k: list(v) for k, v in blocks.items()}, "all": list(all_days)},
        "assets": {},
    }
    rng = np.random.default_rng(0)
    resid_by_asset: dict[str, tuple[float, float]] = {}
    block_items = list({**blocks, "all": all_days}.items())
    for asset in sorted(set(rows180.asset.tolist())):
        if asset not in WIDTH_MULT:
            continue
        report["assets"][asset] = {"rung_usd": RUNG_USD[asset], "width_mult": WIDTH_MULT[asset]}
        for bname, (lo, hi) in block_items:
            idx = np.flatnonzero(
                (rows180.asset == asset) & (rows180.day >= lo) & (rows180.day <= hi)
                & (rows180.delta == DELTA_SEC))
            if len(idx) == 0:
                continue
            kept = _keep_idx(rows180, rows0, idx, asset)
            # cluster max on the unreduced idx, then take kept
            form_al = _join_form_aligned(rows180, rows0, names, rows0.feature_names)[idx]
            formed_idx = _formation_sec(rows180.x[idx], names)
            cell_idx = rows180.cell[idx]
            theta = _theta(asset) * WIDTH_MULT[asset]
            buckets = cell_idx.astype(np.int64) * 10**9 + _bucket_id(form_al, theta)
            cmax_idx = _cluster_max(rows180.y[idx], buckets)
            pos_of = {int(i): p for p, i in enumerate(idx)}
            keep_pos = np.array([pos_of[int(k)] for k in kept], np.int64)
            y = rows180.y[kept]
            cell = rows180.cell[kept]
            day = rows180.day[kept]
            elapsed = rows180.elapsed[kept]
            occupancy = rows180.occupancy[kept]
            remaining = rows180.x[kept, _col(names, PHASE_REMAINING_COL)].astype(np.float64)
            formed = _formation_sec(rows180.x[kept], names)
            cmax = cmax_idx[keep_pos]
            dawes = _dawes(rows180.x[kept], names)
            if bname == "train" or asset not in resid_by_asset:
                resid_by_asset[asset] = _ols_fit(y, remaining)
            blk = _block_report(y, cell, day, elapsed, occupancy, remaining, formed,
                                cmax, dawes, resid_by_asset[asset], RUNG_USD[asset],
                                rng, n_draw)
            report["assets"][asset][bname] = blk
            letters = {n: v["letter"] for n, v in blk["labels"].items()}
            log(f"{asset:4s} {bname:10s} n={blk['n_per_cell_median']:.0f} "
                f"ceil={blk['ceiling_usd']:.0f} ge600={blk['frac_cells_with_y_ge_600']:.2f} "
                f"{letters}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=1, sort_keys=True))
    return report


def _plant_three_path_matrix(root: Path) -> None:
    names = ["min_alert_age_sec", "phase_index", ELAPSED_COL,
             "disc_fvol_phase_scope_elapsed_sec", PHASE_REMAINING_COL, VWAP_COL, SIDE_COL]
    theta = _theta("HG")
    specs = [
        (2500.0, 10000.0, 280.0, 0.0),
        (400.0, 80.0, 5180.0, 8.0 * theta),
        (800.0, 5000.0, 380.0, 16.0 * theta),
    ]
    xs, days, assets, series, ys, occs = [], [], [], [], [], []
    for d in (20210610, 20210611):
        for s, (yv, rem, el180, vwap) in enumerate(specs):
            for age in (0.0, 180.0):
                elapsed = el180 - 180.0 + age
                rem_row = rem + (180.0 - age)
                xs.append([age, 0.0, elapsed, elapsed, rem_row, vwap, 1.0])
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
        _plant_three_path_matrix(tmp / "p")
        rep = run(tmp / "p", tmp / "p.json", blocks=blocks, n_draw=8, log=lambda *_: None)
        tr = rep["assets"]["HG"]["train"]
        raw = tr["labels"]["raw_y"]["align_usd"]
        cap = tr["labels"]["capture_remaining"]["align_usd"]
        z = tr["labels"]["y_cell_z"]["align_usd"]
        assert abs(raw - 2500.0) < 1.0, raw
        assert abs(z - raw) < 0.01, (z, raw)
        assert abs(cap - 400.0) < 1.0, cap
        assert tr["labels"]["capture_remaining"]["letter"] == "cannot_reach", tr["labels"]
        assert tr["labels"]["raw_y"]["letter"] != "cannot_reach", tr["labels"]["raw_y"]
        _plant_three_path_matrix(tmp / "red")
        cur = np.load(tmp / "red" / "current_asinh.npy"); cur[1] = np.nan
        np.save(tmp / "red" / "current_asinh.npy", cur)
        try:
            run(tmp / "red", tmp / "red.json", blocks=blocks, n_draw=2, log=lambda *_: None)
        except ProbeRefusal as exc:
            assert "non-finite" in str(exc), exc
        else:
            raise AssertionError("NaN y was accepted")
    print("selftest OK: raw_y cashes 2500, capture_remaining cashes 400 and cannot_reach, "
          "cell-z matches raw_y, NaN refused")
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
