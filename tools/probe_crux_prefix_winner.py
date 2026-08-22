#!/usr/bin/env python3
"""Prefix identification of the cell-max — ticket 25 (2026-08-22).

PREREGISTRATION (written before the real run; echoed into the receipt):
- The side-first dollars ($1986 HG / $985 NKD TRAIN) are hindsight
  oracles, not a model, and already miss the rung. Finished-cell
  ranking of 15 names is not live: later names are not born yet.
- Live object: keep-first names become eligible at formation+180,
  in formation order. When the cell-max becomes eligible, the
  comparison set is the prefix of already-eligible names. Can a
  prefix-only non-clock score rank the cell-max above those earlier
  names?
- Null: shuffle the winner identity among the prefix (destroys
  identification, keeps prefix size). Clock is a control and cannot
  grant 'seen'.
- Also cash enter-first (fully live, no score) vs cell-max (illegal
  finished oracle). TRAIN writes the letter. 2021 cannot promote.

Letters:
  first_prints    enter-first >= rung
  prefix_seen     enter-first < rung, a non-clock score AUC>=0.60
                  and above shuffle on winner-vs-earlier
  prefix_blind    enter-first < rung, nothing sees the winner

Selftest: python3 tools/probe_crux_prefix_winner.py --selftest
Real:     OMP_NUM_THREADS=1 python3 tools/probe_crux_prefix_winner.py \\
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
from probe_path_dedup import _formation_sec  # noqa: E402
from probe_path_dedup_live import DELTA_SEC, FORM_DELTA, SIDE_COL, VWAP_COL  # noqa: E402
from probe_rho_on_dedup import WIDTH_MULT, _keep_idx  # noqa: E402
from probe_rho_ruler import (  # noqa: E402
    BLOCKS, PHASE_REMAINING_COL, RUNG_USD, _cell_groups,
)
from probe_trained_accrual import (  # noqa: E402
    ELAPSED_COL, ProbeRefusal, _cell_pick, load_delta_rows,
)

SCHEMA = "QRE2CRUXPRE1"
N_DRAW = 40
SHUFFLE_Q = 0.95
PLANE_COLS = (
    "disc_auction_session_directional_profile_skewness",
    "disc_state_favorable_max_ticks",
    "aligned_from_formation_mean_usd",
    "disc_auction_phase_vwap_aligned_usd",
    "w60_favorable_excursion_usd",
)


def _usd(score: np.ndarray, y: np.ndarray, cell: np.ndarray, day: np.ndarray,
         elapsed: np.ndarray, occupancy: np.ndarray, days: list[int]) -> float:
    pick = _cell_pick(score, y, cell, day, elapsed, occupancy, -np.inf)
    return float(np.mean([pick["all"].get(d, 0.0) for d in days]))


def _dawes(x: np.ndarray, names: list[str]) -> np.ndarray | None:
    if SIDE_COL not in names:
        return None
    try:
        resolved, _ = resolve_ingredients(names, SCORE_DEFS)
    except AccrualRefusal:
        return None
    side = x[:, _col(names, SIDE_COL)].astype(np.float64)
    return compute_scores(x.astype(np.float64), side, resolved)["COMBINED"]


def _mann_whitney(win_s: np.ndarray, lose_s: np.ndarray) -> float:
    w = win_s[np.isfinite(win_s)]
    l = lose_s[np.isfinite(lose_s)]
    if len(w) == 0 or len(l) == 0:
        return float("nan")
    return float(((w[:, None] > l[None, :]).sum()
                  + 0.5 * (w[:, None] == l[None, :]).sum()) / (len(w) * len(l)))


def _letter(first_usd: float, rung: float, seen: bool) -> str:
    if np.isfinite(first_usd) and first_usd >= rung:
        return "first_prints"
    return "prefix_seen" if seen else "prefix_blind"


def _block(y, cell, day, elapsed, occupancy, formed, scores: dict[str, np.ndarray],
           rung: float, rng: np.random.Generator, n_draw: int) -> dict:
    days = sorted({int(d) for d in day})
    groups = _cell_groups(cell)
    n = len(y)
    first_flag = np.full(n, False)
    win_flag = np.full(n, False)
    prefix_n = []
    winner_rank = []
    multi: list[np.ndarray] = []
    winners: list[int] = []
    n_multi = 0
    for g in groups:
        order = g[np.argsort(formed[g], kind="stable")]
        first_flag[int(order[0])] = True
        wi = int(g[np.argmax(y[g])])
        win_flag[wi] = True
        pref = order[formed[order] <= formed[wi] + 1e-9]
        prefix_n.append(int(len(pref)))
        winner_rank.append(int(np.flatnonzero(pref == wi)[0] + 1))
        if len(pref) < 2:
            continue
        n_multi += 1
        multi.append(pref)
        winners.append(wi)
    first_usd = _usd(np.where(first_flag, 1.0, -np.inf), y, cell, day, elapsed, occupancy, days)
    win_usd = _usd(np.where(win_flag, 1.0, -np.inf), y, cell, day, elapsed, occupancy, days)
    id_table = {}
    seen = False
    for name, sc in scores.items():
        reals = []
        for pref, wi in zip(multi, winners):
            others = pref[pref != wi]
            reals.append(_mann_whitney(np.asarray([sc[wi]]), sc[others]))
        real = float(np.nanmean(reals)) if reals else float("nan")
        sh = []
        if n_multi >= 4:
            for _ in range(n_draw):
                fake = []
                for pref, wi in zip(multi, winners):
                    fj = int(pref[rng.integers(0, len(pref))])
                    others = pref[pref != fj]
                    fake.append(_mann_whitney(np.asarray([sc[fj]]), sc[others]))
                sh.append(float(np.nanmean(fake)))
        band = float(np.nanquantile(sh, SHUFFLE_Q)) if sh else float("nan")
        beats = bool(np.isfinite(real) and np.isfinite(band) and real > band and real >= 0.60)
        id_table[name] = {"auc_winner_vs_earlier": None if not np.isfinite(real) else real,
                          "shuffle_p95": None if not np.isfinite(band) else float(band),
                          "beats_shuffle": beats, "n_multi_prefix": n_multi}
        if beats and name != "clock":
            seen = True
    sizes = np.asarray(prefix_n, np.float64)
    ranks = np.asarray(winner_rank, np.float64)
    return {
        "days": len(days), "n_cells": len(groups),
        "n_eligible_when_winner_median": float(np.median(sizes)) if len(sizes) else float("nan"),
        "n_eligible_when_winner_p90": float(np.quantile(sizes, 0.90)) if len(sizes) else float("nan"),
        "frac_winner_is_first": float(np.mean(ranks == 1)) if len(ranks) else float("nan"),
        "frac_winner_in_first_three": float(np.mean(ranks <= 3)) if len(ranks) else float("nan"),
        "enter_first_usd": float(first_usd),
        "cell_max_usd": float(win_usd),
        "gap_usd": float(win_usd - first_usd),
        "rung_usd": float(rung),
        "identify": id_table,
        "letter": _letter(float(first_usd), rung, seen),
    }


def run(matrix_dir: Path, out_path: Path, *, blocks=BLOCKS, n_draw: int = N_DRAW,
        log=print) -> dict:
    rows180 = load_delta_rows(matrix_dir, deltas=(DELTA_SEC,))
    rows0 = load_delta_rows(matrix_dir, deltas=(FORM_DELTA,))
    if not np.isfinite(rows180.y).all():
        raise ProbeRefusal(
            f"{int(np.sum(~np.isfinite(rows180.y)))} non-finite y; expected all finite USD")
    names = rows180.feature_names
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
            scores: dict[str, np.ndarray] = {}
            if PHASE_REMAINING_COL in names:
                scores["clock"] = rows180.x[kept, _col(names, PHASE_REMAINING_COL)].astype(np.float64)
            dawes = _dawes(rows180.x[kept], names)
            if dawes is not None:
                scores["dawes"] = dawes
            for c in PLANE_COLS:
                if c in names:
                    scores[c] = rows180.x[kept, _col(names, c)].astype(np.float64)
            blk = _block(y, cell, day, elapsed, occupancy, formed, scores,
                         RUNG_USD[asset], rng, n_draw)
            report["assets"][asset][bname] = blk
            log(f"{asset:4s} {bname:10s} letter={blk['letter']:14s} "
                f"first={blk['enter_first_usd']:.0f} max={blk['cell_max_usd']:.0f} "
                f"npre={blk['n_eligible_when_winner_median']:.0f} "
                f"p1={blk['frac_winner_is_first']:.2f}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=1, sort_keys=True))
    return report


def _plant(root: Path, *, mode: str = "ok") -> None:
    names = ["min_alert_age_sec", "phase_index", ELAPSED_COL,
             "disc_fvol_phase_scope_elapsed_sec", PHASE_REMAINING_COL, VWAP_COL,
             SIDE_COL, "aligned_from_formation_mean_usd"]
    from probe_path_dedup import _theta
    theta = _theta("HG")
    # second-born is the winner; planted aligned score marks it
    specs = [
        (400.0, 280.0, 0.0, 1.0),
        (2500.0, 480.0, 8.0 * theta, 5.0),
        (100.0, 680.0, 16.0 * theta, 0.0),
    ]
    xs, days, assets, series, ys, occs = [], [], [], [], [], []
    for d in (20210610, 20210611):
        for s, (yv, el180, vwap, al) in enumerate(specs):
            for age in (0.0, 180.0):
                elapsed = el180 - 180.0 + age
                xs.append([age, 0.0, elapsed, elapsed, 10000.0 - elapsed, vwap, 1.0, al])
                days.append(d); assets.append("HG"); series.append(f"s{d}_{s}")
                ys.append(yv); occs.append(600.0)
    root.mkdir(parents=True, exist_ok=True)
    yv = np.asarray(ys, np.float64)
    if mode == "nan":
        yv[1] = np.nan
    np.save(root / "x.npy", np.asarray(xs, np.float32))
    np.save(root / "day.npy", np.asarray(days, np.int64))
    np.save(root / "asset.npy", np.asarray(assets))
    np.save(root / "series_id.npy", np.asarray(series))
    np.save(root / "current_asinh.npy", np.arcsinh(yv / 600.0))
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
        assert abs(tr["enter_first_usd"] - 400.0) < 1.0, tr["enter_first_usd"]
        assert abs(tr["cell_max_usd"] - 2500.0) < 1.0, tr["cell_max_usd"]
        assert tr["n_eligible_when_winner_median"] == 2, tr
        auc = tr["identify"]["aligned_from_formation_mean_usd"]["auc_winner_vs_earlier"]
        assert auc is not None and auc > 0.99, tr["identify"]
        _plant(tmp / "red", mode="nan")
        try:
            run(tmp / "red", tmp / "red.json", blocks=blocks, n_draw=2, log=lambda *_: None)
        except ProbeRefusal as exc:
            assert "non-finite" in str(exc), exc
        else:
            raise AssertionError("NaN y was accepted")
    print("selftest OK: enter-first 400, cell-max 2500, prefix n=2, planted AUC 1, NaN refused")
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
