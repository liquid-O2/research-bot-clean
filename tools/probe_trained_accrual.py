#!/usr/bin/env python3
"""Trained-accrual probe — ticket D6 of design/ENTRY_SELECTION_MAP.md (confirmation-window
frontier, 2026-08-22).

PREREGISTRATION (written before the real run; echoed into the receipt):
- Question: with the FULL feature plane and a proper objective, how well does a trained
  object rank candidate series WITHIN a cell (asset, day, phase) at formation+Delta, for
  Delta in {0,30,60,120,180,240,290}s, and what fraction of the per-asset-day ceiling does
  picking the top-scored series of each cell at Delta realize?  Chronological folds only.
- Rows: the matrix row nearest each Delta target per series (exact sampled offsets; +/-2.5s).
  Features: every matrix column (min_alert_age_sec included; the plane refuses
  teacher/outcome names at load, so no leakage column exists by construction).
- Folds: the E1R action-fold chronology verbatim (name, train_lo, train_hi, val_lo, val_hi,
  score_lo, score_hi): fit on train days, early-stop on val days, score the score days.
  Never random day CV.
- Arms: CELLZ_RMSE (default; shallow RMSE on cell-standardized standalone y — cross-program
  evidence: day-standardized regression climbs, pairwise anti-correlates, shallow wins),
  PAIRLOGIT (PairLogitPairwise grouped by (cell, Delta) — control), WINNER_LOGLOSS (Logloss
  on series-best >= $600 — control).  Depth/iterations fixed here, never eval-selected.
- Luck bar: 5 real seeds + 5 matched shuffle seeds per arm; mean +/- sd; weakest real vs
  strongest shuffle.  The seed spread is the noise floor; a margin inside it is "not resolved".
- Matched null: labels permuted among rows within each (cell, Delta) group on the fit rows
  (destroys feature->outcome while keeping cell composition, the age structure and the
  marginal label distribution); score rows keep their true outcomes.
- Metrics per (fold, arm, lane:seed, asset, Delta): (1) within-cell pairwise AUC, winner
  series (best >= $600) vs loser series (best <= $0) — the v1/v2 accrual frame, for
  comparability; (2) CELL-PICK CAPTURE over ALL series: in every cell enter the top-scored
  series at Delta, realized = its standalone y at Delta; denominator = sum over cells of the
  series-best value (matrix ceiling, occupancy-free); skipped/occupied cells count $0.
  Arms: enter-all, and theta-skip with theta chosen on the fold's train+val cells only.
  One position per asset enforced greedily by session-elapsed time + occupancy_sec.
- Perfect-label check: a perfect ranker at Delta=290 retains 92-93% of the goal-cell ceiling
  (delay_forfeit_20260822.json) — above the 80% gate, so the label can carry the goal.
- Tier: DIAGNOSTIC.  Cell-pick dollars are not replay dollars; exact replay through the walk
  remains the only promotable number.  Reported numbers steer design round 2 only.
- AMENDMENT D6b (2026-08-22 ~12:05Z, preregistered before its run; first-run receipts stand
  unchanged): the instrument check on the FROZEN fold showed CELLZ_RMSE early-stops at 11
  trees (val RMSE 0.99 = the cell mean) and PAIRLOGIT completes 1 run per ~75 min.  Two
  replacement arms, same folds/seeds/metrics/null: YETIRANK (listwise CatBoostRanker grouped
  by (cell, Delta), early-stopped on its own ranking loss) and CELLZ_RMSE_FIXED (the RMSE arm
  with a FIXED 300 iterations, no early stopping — the validation RMSE of a noise-dominated
  target is the wrong stopping signal for a ranking use).  Iteration count fixed here, never
  eval-selected.

Selftest: python3 tools/probe_trained_accrual.py --selftest     (synthetic; no artifacts)
Real:     OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 tools/probe_trained_accrual.py \
            --matrix-dir <round_0/component_matrix> --execution <fit_only_execution.json> \
            --out <receipt.json> [--arms CELLZ_RMSE,PAIRLOGIT,WINNER_LOGLOSS] [--threads 2]
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe_confirmation_accrual import pairwise_auc_by_day, pooled_auc  # noqa: E402

DELTAS = (0.0, 30.0, 60.0, 120.0, 180.0, 240.0, 290.0)
DELTA_TOL_SEC = 2.5
WINNER_MIN_USD, LOSER_MAX_USD, VALUE_SCALE_USD = 600.0, 0.0, 600.0
ARMS = ("CELLZ_RMSE", "PAIRLOGIT", "WINNER_LOGLOSS", "YETIRANK", "CELLZ_RMSE_FIXED")
FIXED_ITERATIONS = 300
SEEDS = (20260820, 20260821, 20260822, 20260823, 20260824)
FIT_PARAMS = {"depth": 3, "iterations": 400, "learning_rate": 0.05,
              "early_stopping_rounds": 40}
THETA_QUANTILES = 21
ELAPSED_COL = "disc_fvol_session_scope_elapsed_sec"


class ProbeRefusal(RuntimeError):
    pass


@dataclass
class DeltaRows:
    x: np.ndarray            # (n, f) float32, NaN allowed
    y: np.ndarray            # standalone usd at the row
    day: np.ndarray
    asset: np.ndarray
    series: np.ndarray       # int series index
    cell: np.ndarray         # day*10 + phase
    delta: np.ndarray        # target delta the row stands for
    elapsed: np.ndarray      # session-elapsed sec at the row (NaN allowed)
    occupancy: np.ndarray
    series_best: np.ndarray  # series-best y over ALL matrix rows, indexed by series
    feature_names: list[str]
    matrix_receipt: str


def load_delta_rows(matrix_dir: Path, deltas=DELTAS, block: int = 200_000) -> DeltaRows:
    manifest = json.loads((matrix_dir / "manifest.json").read_text())
    names = list(manifest["feature_names"])
    for required in ("min_alert_age_sec", "phase_index"):
        if required not in names:
            raise ProbeRefusal(f"matrix lacks required column {required!r}")
    age_col, phase_col = names.index("min_alert_age_sec"), names.index("phase_index")
    elapsed_col = names.index(ELAPSED_COL) if ELAPSED_COL in names else -1
    day = np.load(matrix_dir / "day.npy").astype(np.int64)
    asset = np.asarray(np.load(matrix_dir / "asset.npy"), str)
    series_raw = np.asarray(np.load(matrix_dir / "series_id.npy"), str)
    y_all = np.sinh(np.load(matrix_dir / "current_asinh.npy")) * VALUE_SCALE_USD
    occupancy = np.load(matrix_dir / "occupancy_sec.npy").astype(np.float64)
    x = np.lib.format.open_memmap(matrix_dir / "x.npy", mode="r")
    n = len(day)
    if x.shape != (n, len(names)):
        raise ProbeRefusal(f"x shape {x.shape} != ({n}, {len(names)})")
    _u, inv = np.unique(series_raw, return_inverse=True)
    series_best = np.full(len(_u), -np.inf)
    np.maximum.at(series_best, inv, y_all)
    deltas = np.asarray(deltas, np.float64)
    keep_x, keep_idx, keep_delta = [], [], []
    for lo in range(0, n, block):
        hi = min(lo + block, n)
        blk = np.asarray(x[lo:hi], np.float32)
        age = blk[:, age_col].astype(np.float64)
        dist = np.abs(age[:, None] - deltas[None, :])
        nearest = np.argmin(dist, axis=1)
        mask = dist[np.arange(len(age)), nearest] <= DELTA_TOL_SEC
        keep_x.append(blk[mask]); keep_idx.append(np.flatnonzero(mask) + lo)
        keep_delta.append(deltas[nearest[mask]])
    idx = np.concatenate(keep_idx); delta = np.concatenate(keep_delta)
    xs = np.vstack(keep_x)
    # one row per (series, delta): keep the nearest (first after lexsort on distance)
    dist = np.abs(xs[:, age_col].astype(np.float64) - delta)
    order = np.lexsort((dist, delta, inv[idx]))
    key = inv[idx][order] * 1000 + delta[order].astype(np.int64)
    first = np.ones(len(order), bool); first[1:] = key[1:] != key[:-1]
    sel = order[first]; idx, delta, xs = idx[sel], delta[sel], xs[sel]
    phase = np.nan_to_num(xs[:, phase_col].astype(np.float64), nan=9).astype(np.int64)
    elapsed = (xs[:, elapsed_col].astype(np.float64) if elapsed_col >= 0
               else np.full(len(idx), np.nan))
    return DeltaRows(x=xs, y=y_all[idx], day=day[idx], asset=asset[idx], series=inv[idx],
                     cell=day[idx] * 10 + phase, delta=delta, elapsed=elapsed,
                     occupancy=occupancy[idx], series_best=series_best,
                     feature_names=names,
                     matrix_receipt=str(manifest.get("matrix_receipt_sha256")))


def standardize_by_cell(y: np.ndarray, cell: np.ndarray) -> np.ndarray:
    _u, inv = np.unique(cell, return_inverse=True)
    cnt = np.bincount(inv).astype(np.float64)
    mean = np.bincount(inv, weights=y) / cnt
    var = np.bincount(inv, weights=(y - mean[inv]) ** 2) / cnt
    sd = np.sqrt(var); sd[sd < 1.0] = 1.0
    return (y - mean[inv]) / sd[inv]


def shuffle_within_groups(values: np.ndarray, group: np.ndarray,
                          rng: np.random.Generator) -> np.ndarray:
    """Permute values among the rows of each group (the matched null)."""
    out = values.copy()
    order = np.argsort(group, kind="stable")
    bounds = np.flatnonzero(np.diff(group[order])) + 1
    for grp in np.split(order, bounds):
        out[grp] = values[grp[rng.permutation(len(grp))]]
    return out


def fit_and_score(arm: str, rows: DeltaRows, fit: np.ndarray, val: np.ndarray,
                  score: np.ndarray, *, seed: int, shuffle_seed: int | None,
                  threads: int, params: dict = FIT_PARAMS) -> np.ndarray:
    """Fit one arm on `fit` rows (early-stop on `val`), return scores on `score` rows.
    A shuffle_seed permutes labels within (cell, Delta) on the fit AND val rows."""
    from catboost import CatBoostClassifier, CatBoostRanker, CatBoostRegressor, Pool
    y_fit, y_val = rows.y[fit], rows.y[val]
    win_fit = (rows.series_best[rows.series[fit]] >= WINNER_MIN_USD).astype(np.int64)
    win_val = (rows.series_best[rows.series[val]] >= WINNER_MIN_USD).astype(np.int64)
    g_fit = rows.cell[fit] * 1000 + rows.delta[fit].astype(np.int64)
    g_val = rows.cell[val] * 1000 + rows.delta[val].astype(np.int64)
    if shuffle_seed is not None:
        rng = np.random.default_rng(shuffle_seed)
        y_fit = shuffle_within_groups(y_fit, g_fit, rng)
        win_fit = shuffle_within_groups(win_fit, g_fit, rng)
        y_val = shuffle_within_groups(y_val, g_val, rng)
        win_val = shuffle_within_groups(win_val, g_val, rng)
    common = dict(depth=params["depth"], iterations=params["iterations"],
                  learning_rate=params["learning_rate"], random_seed=int(seed),
                  thread_count=int(threads), verbose=0, allow_writing_files=False)
    es = params["early_stopping_rounds"]
    x_fit, x_val, x_score = rows.x[fit], rows.x[val], rows.x[score]
    if arm == "CELLZ_RMSE":
        z_fit = standardize_by_cell(y_fit, rows.cell[fit])
        z_val = standardize_by_cell(y_val, rows.cell[val])
        model = CatBoostRegressor(loss_function="RMSE", **common)
        model.fit(Pool(x_fit, label=z_fit), eval_set=Pool(x_val, label=z_val),
                  early_stopping_rounds=es, use_best_model=True)
        return model.predict(x_score)
    if arm == "CELLZ_RMSE_FIXED":
        z_fit = standardize_by_cell(y_fit, rows.cell[fit])
        model = CatBoostRegressor(loss_function="RMSE",
                                  **{**common, "iterations": FIXED_ITERATIONS})
        model.fit(Pool(x_fit, label=z_fit))
        return model.predict(x_score)
    if arm in ("PAIRLOGIT", "YETIRANK"):
        o_fit, o_val = np.argsort(g_fit, kind="stable"), np.argsort(g_val, kind="stable")
        loss = "PairLogitPairwise" if arm == "PAIRLOGIT" else "YetiRank"
        model = CatBoostRanker(loss_function=loss, **common)
        model.fit(Pool(x_fit[o_fit], label=y_fit[o_fit], group_id=g_fit[o_fit]),
                  eval_set=Pool(x_val[o_val], label=y_val[o_val], group_id=g_val[o_val]),
                  early_stopping_rounds=es, use_best_model=True)
        return model.predict(x_score)
    if arm == "WINNER_LOGLOSS":
        model = CatBoostClassifier(loss_function="Logloss", **common)
        model.fit(Pool(x_fit, label=win_fit), eval_set=Pool(x_val, label=win_val),
                  early_stopping_rounds=es, use_best_model=True)
        return model.predict_proba(x_score)[:, 1]
    raise ProbeRefusal(f"unknown arm {arm!r}; expected one of {ARMS}")


def _cell_pick(score: np.ndarray, y: np.ndarray, cell: np.ndarray, day: np.ndarray,
               elapsed: np.ndarray, occupancy: np.ndarray, theta: float) -> dict:
    """Greedy one-position-per-asset walk over cells in phase order for one (asset, Delta)
    row set. Returns per-day realized dollars (enter-all and theta-skip) and bookkeeping."""
    order = np.lexsort((cell, day))
    out_all: dict[int, float] = {}; out_skip: dict[int, float] = {}
    occupied_skips = 0; unordered = 0; picks = []
    prev_day, prev_exit_all, prev_exit_skip = None, -np.inf, -np.inf
    bounds = np.flatnonzero(np.diff(cell[order])) + 1
    for grp in np.split(order, bounds):
        d = int(day[grp[0]])
        if d != prev_day:
            prev_day, prev_exit_all, prev_exit_skip = d, -np.inf, -np.inf
        best = grp[int(np.argmax(score[grp]))]
        t = elapsed[best]; picks.append(int(best))
        if not np.isfinite(t):
            unordered += 1; t = -np.inf
        realized = float(y[best])
        if t < prev_exit_all:
            occupied_skips += 1; out_all[d] = out_all.get(d, 0.0)
        else:
            out_all[d] = out_all.get(d, 0.0) + realized
            prev_exit_all = t + float(occupancy[best]) if np.isfinite(t) else -np.inf
        if score[best] >= theta and t >= prev_exit_skip:
            out_skip[d] = out_skip.get(d, 0.0) + realized
            prev_exit_skip = t + float(occupancy[best]) if np.isfinite(t) else -np.inf
        else:
            out_skip[d] = out_skip.get(d, 0.0)
    return {"all": out_all, "skip": out_skip, "occupied_skips": occupied_skips,
            "unordered_rows": unordered, "picks": picks}


def _ceiling_by_day(rows: DeltaRows, mask: np.ndarray) -> dict[int, float]:
    """Sum over cells of the best series value in the cell (series-best over all rows)."""
    cell, day = rows.cell[mask], rows.day[mask]
    best = rows.series_best[rows.series[mask]]
    u, inv = np.unique(cell, return_inverse=True)
    cell_max = np.full(len(u), -np.inf); np.maximum.at(cell_max, inv, best)
    cell_day = np.zeros(len(u), np.int64); cell_day[inv] = day
    out: dict[int, float] = {}
    for c, d in enumerate(cell_day):
        out[int(d)] = out.get(int(d), 0.0) + float(max(cell_max[c], 0.0))
    return out


def choose_theta(score: np.ndarray, rows: DeltaRows, mask: np.ndarray) -> float:
    """theta from the fold's own train+val cells: the top-of-cell score quantile whose
    enter-iff-above rule realizes the most dollars there. Never touches score rows."""
    sub = np.flatnonzero(mask)
    cell = rows.cell[sub]
    u, inv = np.unique(cell, return_inverse=True)
    # highest score first within each cell; the first row of each cell is its top
    order = np.lexsort((-score[sub], inv))
    first = np.ones(len(order), bool); first[1:] = inv[order][1:] != inv[order][:-1]
    top_row = sub[order[first]]
    top = score[top_row]
    realized = rows.y[top_row]
    grid = np.quantile(top, np.linspace(0, 1, THETA_QUANTILES))
    totals = [float(realized[top >= q].sum()) for q in grid]
    return float(grid[int(np.argmax(totals))])


def evaluate_arm(score_fn, rows: DeltaRows, fold: tuple, *, lane: str, seed: int,
                 n_boot: int, rng: np.random.Generator) -> dict:
    name, tr_lo, tr_hi, va_lo, va_hi, sc_lo, sc_hi = fold
    fit = (rows.day >= tr_lo) & (rows.day <= tr_hi)
    val = (rows.day >= va_lo) & (rows.day <= va_hi)
    sco = (rows.day >= sc_lo) & (rows.day <= sc_hi)
    if not (fit.any() and val.any() and sco.any()):
        raise ProbeRefusal(f"fold {name}: empty fit/val/score window "
                           f"({fit.sum()}/{val.sum()}/{sco.sum()} rows)")
    scored = fit | val | sco
    score = np.full(len(rows.y), np.nan)
    score[scored] = score_fn(fit, val, scored)
    result: dict = {}
    for a in sorted(set(rows.asset[sco])):
        result[a] = {}
        for d in DELTAS:
            m = sco & (rows.asset == a) & (rows.delta == d)
            if not m.any():
                continue
            idx = np.flatnonzero(m)
            best = rows.series_best[rows.series[idx]]
            is_win, is_lose = best >= WINNER_MIN_USD, best <= LOSER_MAX_USD
            elig = idx[is_win | is_lose]
            per_day = pairwise_auc_by_day(score[elig], (best[is_win | is_lose] >= WINNER_MIN_USD),
                                          rows.day[elig], rows.cell[elig])
            auc = pooled_auc(per_day) if per_day else float("nan")
            theta_mask = (fit | val) & (rows.asset == a) & (rows.delta == d)
            theta = choose_theta(score, rows, theta_mask) if theta_mask.any() else -np.inf
            pick = _cell_pick(score[idx], rows.y[idx], rows.cell[idx], rows.day[idx],
                              rows.elapsed[idx], rows.occupancy[idx], theta)
            ceil = _ceiling_by_day(rows, (rows.asset == a) & sco)
            days = sorted(ceil)
            r_all = np.array([pick["all"].get(k, 0.0) for k in days])
            r_skip = np.array([pick["skip"].get(k, 0.0) for k in days])
            c = np.array([ceil[k] for k in days])
            cap_all = float(r_all.sum() / c.sum()) if c.sum() > 0 else float("nan")
            boots = []
            for _ in range(n_boot):
                b = rng.integers(0, len(days), len(days))
                boots.append(r_all[b].sum() / c[b].sum() if c[b].sum() > 0 else np.nan)
            result[a][str(int(d))] = {
                "auc": round(float(auc), 4), "n_pairs": int(sum(v[1] for v in per_day.values())),
                "capture_all": round(cap_all, 4),
                "capture_all_ci95": [round(float(np.nanpercentile(boots, 2.5)), 4),
                                     round(float(np.nanpercentile(boots, 97.5)), 4)],
                "capture_skip": round(float(r_skip.sum() / c.sum()), 4) if c.sum() > 0 else None,
                "usd_per_asset_day_all": round(float(r_all.mean()), 2),
                "usd_per_asset_day_skip": round(float(r_skip.mean()), 2),
                "ceiling_usd_per_asset_day": round(float(c.mean()), 2),
                "theta": None if not np.isfinite(theta) else round(theta, 6),
                "n_days": len(days), "n_cells": int(len(np.unique(rows.cell[idx]))),
                "occupied_skips": pick["occupied_skips"], "unordered_rows": pick["unordered_rows"]}
    return {"fold": name, "lane": lane, "seed": int(seed), "fit_rows": int(fit.sum()),
            "val_rows": int(val.sum()), "score_rows": int(sco.sum()), "by_asset": result}


def summarize(runs: list[dict]) -> dict:
    """Per (fold, arm, asset, Delta): real mean+-sd vs shuffle mean+-sd, weakest vs strongest."""
    table: dict = {}
    for r in runs:
        for a, by_d in r["by_asset"].items():
            for d, v in by_d.items():
                slot = table.setdefault(r["fold"], {}).setdefault(r["arm"], {}) \
                            .setdefault(a, {}).setdefault(d, {"real": [], "shuffle": []})
                slot[r["lane"]].append((v["auc"], v["capture_all"], v["capture_skip"]))
    out: dict = {}
    for fold, arms in table.items():
        for arm, assets in arms.items():
            for a, ds in assets.items():
                for d, lanes in ds.items():
                    entry = {}
                    for k, i in (("auc", 0), ("capture_all", 1), ("capture_skip", 2)):
                        real = np.array([t[i] for t in lanes["real"]], float)
                        shuf = np.array([t[i] for t in lanes["shuffle"]], float)
                        entry[k] = {"real_mean": round(float(np.nanmean(real)), 4) if len(real) else None,
                                    "real_sd": round(float(np.nanstd(real)), 4) if len(real) else None,
                                    "shuffle_mean": round(float(np.nanmean(shuf)), 4) if len(shuf) else None,
                                    "shuffle_sd": round(float(np.nanstd(shuf)), 4) if len(shuf) else None,
                                    "weakest_real": round(float(np.nanmin(real)), 4) if len(real) else None,
                                    "strongest_shuffle": round(float(np.nanmax(shuf)), 4) if len(shuf) else None,
                                    "separated": (bool(np.nanmin(real) > np.nanmax(shuf))
                                                  if len(real) and len(shuf) else None)}
                    out.setdefault(fold, {}).setdefault(arm, {}).setdefault(a, {})[d] = entry
    return out


def run(matrix_dir: Path, folds: list[tuple], out_path: Path, *, arms=ARMS, seeds=SEEDS,
        shuffle_seeds=SEEDS, threads: int = 2, n_boot: int = 200, params: dict = FIT_PARAMS,
        chronology_receipt: str = "", log=print) -> dict:
    rows = load_delta_rows(matrix_dir)
    log(f"loaded {len(rows.y)} delta rows x {rows.x.shape[1]} features; "
        f"{len(np.unique(rows.series))} series; {len(np.unique(rows.day))} days")
    rng = np.random.default_rng(20260822)
    runs: list[dict] = []
    for fold in folds:
        for arm in arms:
            for lane, seed_list in (("real", seeds), ("shuffle", shuffle_seeds)):
                for seed in seed_list:
                    def score_fn(fit, val, scored, _arm=arm, _seed=seed, _lane=lane):
                        return fit_and_score(_arm, rows, fit, val, scored, seed=_seed,
                            shuffle_seed=(None if _lane == "real" else _seed),
                            threads=threads, params=params)
                    r = evaluate_arm(score_fn, rows, fold, lane=lane, seed=seed,
                                     n_boot=n_boot, rng=rng)
                    r["arm"] = arm; runs.append(r)
                    hg = r["by_asset"]
                    log(f"[{fold[0]} {arm} {lane}:{seed}] " + " ".join(
                        f"{a}@290 auc={v.get('290', {}).get('auc')} cap={v.get('290', {}).get('capture_all')}"
                        for a, v in hg.items()))
                    _publish(out_path, rows, folds, arms, seeds, shuffle_seeds, params, runs,
                             chronology_receipt)
    return _publish(out_path, rows, folds, arms, seeds, shuffle_seeds, params, runs,
                    chronology_receipt)


def _publish(out_path, rows, folds, arms, seeds, shuffle_seeds, params, runs, chron) -> dict:
    report = {"schema": "QRE2TRAINEDACCRUAL1", "prereg": __doc__.split("Selftest:")[0],
              "matrix_receipt": rows.matrix_receipt, "chronology_receipt": chron,
              "deltas_sec": list(DELTAS), "arms": list(arms), "seeds": list(seeds),
              "shuffle_seeds": list(shuffle_seeds), "fit_params": dict(params),
              "folds": [list(f) for f in folds], "runs_completed": len(runs),
              "runs": runs, "summary": summarize(runs)}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".json.partial")
    tmp.write_text(json.dumps(report, indent=1)); tmp.replace(out_path)
    return report


# ----------------------------------------------------------------------------- selftest
def _synthetic_matrix(root: Path, *, signal: bool, n_days: int = 24, n_series: int = 20,
                      seed: int = 7, drop_age: bool = False) -> None:
    rng = np.random.default_rng(seed)
    names = ["min_alert_age_sec", "phase_index", ELAPSED_COL] + [f"f{i}" for i in range(10)]
    if drop_age:
        names.remove("min_alert_age_sec")
    ages = np.array([0, 5, 30, 60, 120, 180, 240, 290, 300], float)
    rows_x, day, asset, series, y, occ = [], [], [], [], [], []
    sid = 0
    for d in range(1, n_days + 1):
        for phase in range(3):
            for s in range(n_series):
                win = rng.random() < 0.3
                base = (rng.normal(900, 150) if win else rng.normal(-300, 150))
                for a in ages:
                    f = rng.normal(size=10)
                    if signal:
                        f[0] += (1.5 if win else -1.5) * (a / 290.0)
                    elapsed = phase * 7200 + 1800 + a
                    row = ([a] if not drop_age else []) + [phase, elapsed] + list(f)
                    rows_x.append(row); day.append(20210600 + d); asset.append("HG")
                    series.append(f"s{sid}"); y.append(base + rng.normal(0, 60))
                    occ.append(600.0)
                sid += 1
    x = np.asarray(rows_x, np.float32)
    root.mkdir(parents=True, exist_ok=True)
    np.save(root / "x.npy", x); np.save(root / "day.npy", np.asarray(day, np.int64))
    np.save(root / "asset.npy", np.asarray(asset)); np.save(root / "series_id.npy", np.asarray(series))
    np.save(root / "current_asinh.npy", np.arcsinh(np.asarray(y) / VALUE_SCALE_USD))
    np.save(root / "occupancy_sec.npy", np.asarray(occ))
    (root / "manifest.json").write_text(json.dumps(
        {"feature_names": names, "rows": len(x), "matrix_receipt_sha256": "synthetic"}))


def selftest() -> int:
    fast = {"depth": 2, "iterations": 60, "learning_rate": 0.1, "early_stopping_rounds": 20}
    folds = [("F1", 20210601, 20210612, 20210613, 20210616, 20210617, 20210624)]
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _synthetic_matrix(tmp / "planted", signal=True)
        rep = run(tmp / "planted", folds, tmp / "planted.json", arms=("CELLZ_RMSE",),
                  seeds=(1, 2), shuffle_seeds=(1, 2), threads=2, n_boot=20, params=fast,
                  log=lambda *_: None)
        s = rep["summary"]["F1"]["CELLZ_RMSE"]["HG"]
        gain = s["290"]["auc"]["real_mean"] - s["0"]["auc"]["real_mean"]
        cap_gain = s["290"]["capture_all"]["real_mean"] - s["0"]["capture_all"]["real_mean"]
        assert gain >= 0.15, f"planted accrual not recovered: AUC gain {gain:.3f}"
        assert cap_gain >= 0.10, f"planted capture gain too small: {cap_gain:.3f}"
        assert s["290"]["auc"]["strongest_shuffle"] < s["290"]["auc"]["weakest_real"], \
            f"shuffle arm not below real at 290: {s['290']['auc']}"
        rep_y = run(tmp / "planted", folds, tmp / "planted_y.json", arms=("YETIRANK",),
                    seeds=(1,), shuffle_seeds=(1,), threads=2, n_boot=20, params=fast,
                    log=lambda *_: None)
        sy = rep_y["summary"]["F1"]["YETIRANK"]["HG"]
        y_gain = sy["290"]["auc"]["real_mean"] - sy["0"]["auc"]["real_mean"]
        assert y_gain >= 0.15, f"YETIRANK did not recover the planted accrual: {y_gain:.3f}"
        _synthetic_matrix(tmp / "nosignal", signal=False, seed=11)
        rep = run(tmp / "nosignal", folds, tmp / "nosignal.json", arms=("CELLZ_RMSE",),
                  seeds=(1,), shuffle_seeds=(1,), threads=2, n_boot=20, params=fast,
                  log=lambda *_: None)
        auc = rep["summary"]["F1"]["CELLZ_RMSE"]["HG"]["290"]["auc"]["real_mean"]
        assert abs(auc - 0.5) < 0.10, f"no-signal fixture separated: {auc}"
        _synthetic_matrix(tmp / "red", signal=True, drop_age=True)
        try:
            load_delta_rows(tmp / "red")
        except ProbeRefusal:
            pass
        else:
            raise AssertionError("red fixture (no min_alert_age_sec) was accepted")
    print("selftest OK: planted accrual recovered (AUC gain %.3f, capture gain %.3f); "
          "no-signal at chance; red fixture refused" % (gain, cap_gain))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("PREREGISTRATION")[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--matrix-dir", type=Path)
    ap.add_argument("--execution", type=Path, help="fit_only_execution.json (action_folds)")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--arms", default=",".join(ARMS))
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--n-boot", type=int, default=200)
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if not (args.matrix_dir and args.execution and args.out):
        ap.error("--matrix-dir, --execution and --out are required (or --selftest)")
    execution = json.loads(args.execution.read_text())
    folds = [tuple([str(f[0])] + [int(v) for v in f[1:]])
             for f in execution["chronology"]["action_folds"]]
    arms = tuple(a for a in args.arms.split(",") if a)
    for a in arms:
        if a not in ARMS:
            ap.error(f"unknown arm {a!r}; expected subset of {ARMS}")
    run(args.matrix_dir, folds, args.out, arms=arms, threads=args.threads,
        n_boot=args.n_boot, chronology_receipt=str(execution.get("chronology_receipt_sha256")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
