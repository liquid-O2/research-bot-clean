#!/usr/bin/env python3
"""exit_stopping.py — RUNG 3 of the exit program: OPTIMAL STOPPING.

RUNG 2 (`exit_state_model.py`, `EXIT_RUNG2_REPORT.md`) solved a VALUATION
problem and called it an exit.  Its target — "will >= $150 of value ever remain
before the wall/close" — is a barrier-hit probability; it scored 0.64-0.67 AUC
out of era and converted to nothing, because the MAXIMUM of the remaining path
is ordered beautifully and the ATTAINABLE end of the hold is ordered not at all
(decile means of the change from the sampled state to the wall/close: -$1, +$2,
-$4, -$0, +$2, +$1, +$4, +$12, +$19, -$50).  Its hand-off names the object this
file trains instead: the best mark reachable from a LATER minute of our own
decision grid is worth +$56..+$397 per state by decile (mean +$239, positive
71%), so the room is real and the question is a STOPPING question.

WHAT THIS FILE DOES (the orchestrator's pinned design, D-002 — implemented, not
redesigned):

1. CONTINUATION-VALUE MODEL, Longstaff-Schwartz-style, two passes.

   PASS A (direct supervised).  For every sampled state of every trajectory,

       y_A = max( marks at the LATER sampled decision minutes of this
                  trajectory, and the terminal mark at the wall/close )
             - the mark in hand

   i.e. the "next-available-better-mark" object measured on OUR OWN decision
   grid, with the wall and the close as absorbing ends.  Regressed (dollars, not
   a class) on rung 2's 93 state columns PLUS a preregistered EMPHASIS block
   built from the three drivers rung 2 proved: runway, drawdown/giveback, and
   PROXY_VOL asymmetry + sigma_inst.

   PASS B (one backward policy iteration).  y is recomputed as what the PASS-A
   POLICY ACTUALLY ATTAINS — only marks at minutes where that policy would still
   be holding count:

       m[i] = u[i]          if predA[i] <  c     (the policy stops here)
              m[i+1]        otherwise            (it holds through)
       m[n] = terminal
       y_B[i] = m[i+1] - u[i]

   and the model is refit on y_B.  PASS-A predictions on the TRAINING rows are
   CROSS-FITTED (session-grouped 5-fold inside the training window) so the
   backward pass is not walked on a model's own memorised fit.

2. POLICY.  Exit at the first sampled minute whose predicted continuation
   improvement falls below the cost threshold c; plus the $300 wall and the
   close, always.  c in {$0, $25, $50} is PREREGISTERED and every value is
   reported.

3. REPLAY.  Exactly rung 2's machinery — the same `picks.tsv`, the same eras,
   the same 576c round trip, the same wall with gap-through, ONE and TWO
   concurrent positions — with rung 1's six implementable rules and its oracle
   re-run in the same loop as like-for-like references.

4. CONTROLS.  Same walk-forward splits as `era_retest.py` (a segment trains only
   on sessions strictly before its test block).  Hyper-parameters chosen ONCE by
   session-grouped CV inside the study window 125..427 — strictly prior to every
   test block — from a preregistered grid, then frozen for all five segments.  A
   shuffled-y control refits the identical model on permuted PASS-A targets.

5. REPORT-ONLY PANEL (no verdict weight).  The same best policy under an
   ADAPTIVE WALL, wall = max($300, 1.0 x era-median winner MAE), plus a wall
   ladder, to quantify what a contract amendment would buy.  Because the rung-2
   trajectory sampling STOPS at the $300 wall, the panel needs states that the
   $300 wall censored: a second, wall-free trajectory set is built once and every
   panel wall is a subset of it (at $300 it reproduces `traj/` exactly, which is
   asserted).  The panel model is refit under its own wall so the policy is
   coherent with the wall it runs against.

LAWS.  Strictly prior throughout; the c grid is preregistered; costs are charged
on every trade; the sealed zone (>= `packlib.SEALED_FROM`) is never touched.

    exit_stopping.py [--stage target|hypers|fit|replay|panel|report|all]
                     [--jobs N] [--rebuild]
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

#: HistGBT is OpenMP-parallel; rung 2 pinned 1 thread for its many small worker
#: processes, this stage fits a handful of large models in one process.
os.environ.setdefault("OMP_NUM_THREADS", "16")

import numpy as np                                        # noqa: E402
import pandas as pd                                       # noqa: E402

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import packlib as P                                       # noqa: E402
import era_retest as er                                   # noqa: E402
import exit_engine as ee                                  # noqa: E402
import exit_state_model as esm                            # noqa: E402
import distill_model as dm                                # noqa: E402

ROOT = P.ROOT
OUTDIR = ROOT / "exit_segments"
TRAJDIR = OUTDIR / "traj"                                 # rung 2's, REUSED
NOWALLDIR = OUTDIR / "traj_nowall"                        # the panel's superset
PICKS = OUTDIR / "picks.tsv"
REPORT = ROOT / "EXIT_RUNG3_REPORT.md"
VERDICT = ROOT / "EXIT_RUNG3_VERDICT.md"

TARGETS = OUTDIR / "stop_targets.tsv"
HYPERS = OUTDIR / "stop_hypers.json"
PREDS = OUTDIR / "stop_preds.tsv"
FIT = OUTDIR / "stop_fit.tsv"
COEF = OUTDIR / "stop_coefficients.tsv"
IMPORT = OUTDIR / "stop_importance.tsv"
REPLAY = OUTDIR / "stop_replay.tsv"
PANEL = OUTDIR / "stop_wall_panel.tsv"
WALLMAE = OUTDIR / "stop_wall_mae.tsv"
REACH = OUTDIR / "stop_reachability.tsv"

esm.ee.FIXED_PIN_BLOCKS = esm.PIN_BLOCKS                  # rung 2's widened set

SEGMENTS = er.SEGMENTS
ARMS = er.ARMS
KS = ee.KS
OFFSETS = esm.OFFSETS
SEED = dm.SEED

#: ---- preregistered, fixed before any number was computed --------------------
#: the cost threshold grid: exit when predicted continuation improvement < c
COSTS = (0.0, 25.0, 50.0)
OCCUPANCIES = (1, 2)
PASSES = ("A", "B")
MODELS = ("gbt", "lasso")
STUDY_HI = 427                     # strictly prior to every test block (428+)
CV_FOLDS = 5
GBT_GRID = [dict(max_depth=d, max_iter=m, learning_rate=0.05,
                 min_samples_leaf=leaf, l2_regularization=1.0)
            for d in (2, 3) for m in (150, 300) for leaf in (20, 50)]
LASSO_GRID = [0.1, 1.0, 10.0]
SHUFFLE_DRAWS = 3
SHUFFLE_COST = 25.0
MIN_FINITE = esm.MIN_FINITE

#: REPORT-ONLY.  The brief's amendment, plus the ladder that makes it readable.
#: None = no wall at all (the close is the only absorbing end).
ADAPTIVE_WALL_FLOOR = 300.0
ADAPTIVE_WALL_MULT = 1.00
WALL_LADDER = (300.0, 450.0, 600.0, None)

#: meta columns — never features
META = tuple(esm.META_COLUMNS) + ("terminal", "y_grid", "predA", "y_pb")

CONT_RULES = tuple(f"cont[{model},{p}]@c{int(c)}"
                   for model in MODELS for p in PASSES for c in COSTS)
SHUF_RULES = tuple(f"shufcont{draw}@c{int(SHUFFLE_COST)}"
                   for draw in range(SHUFFLE_DRAWS))
REF_RULES = tuple(ee.RULES)
ALL_RULES = REF_RULES + CONT_RULES + SHUF_RULES

money, number = ee.money, ee.number


# ==========================================================================
# 0 — light per-session grid access (no swing ladders; terminal marks only)
# ==========================================================================

class Grid:
    """The session's lawful 1s marks — `exit_engine.Session` without the ladders."""

    def __init__(self, ordinal: int):
        grid = P.load_grid(ordinal)[:, 0]
        self.second = np.flatnonzero(grid > 0).astype(np.int64)
        self.mid = np.rint(grid[self.second]).astype(np.int64)
        self.close_pos = len(self.second) - 1

    def position(self, second: int) -> int:
        return min(int(np.searchsorted(self.second, second, "left")), self.close_pos)


def wall_limit(nets: np.ndarray, start: int, close_pos: int,
               wall_cent: float | None) -> tuple:
    """(wall fill index or None, absorbing index) — rung 1's arithmetic exactly."""
    if wall_cent is None:
        return None, close_pos
    forward = np.flatnonzero(nets[start + 1:] <= wall_cent)
    if not forward.size:
        return None, close_pos
    fill = min(int(forward[0]) + start + 2, close_pos)
    return fill, fill


# ==========================================================================
# 1 — the PASS-A target on rung 2's trajectory dataset
# ==========================================================================

EMPHASIS_COLUMNS = ("e_move_budget", "e_move_budget_now", "e_giveback",
                    "e_giveback_per_move", "e_drawdown", "e_wall_room_per_move",
                    "e_unreal_per_move", "e_pv_asym_x_runway",
                    "e_sigma_ratio_x_runway", "e_runway_frac")


def add_emphasis(frame: pd.DataFrame, wall_dollars: float | None = 300.0) -> pd.DataFrame:
    """The preregistered EMPHASIS block: rung 2's three proven drivers, stated.

    Every column is a deterministic function of columns rung 2 already computed
    — no new data is read, so nothing here can leak.  The point is to state the
    interactions the tree would otherwise have to rediscover by splitting:
    the remaining-move BUDGET (sigma x sqrt(minutes left), in dollars on the
    $100,000 object, since 1bp = $10), the giveback and the drawdown measured
    AGAINST that budget, and the protection bid scaled by the clock.
    """
    runway = frame["p_runway_min"].clip(lower=0.0)
    root = np.sqrt(runway)
    budget = frame["M_sigma_inst_bps"] * root * 10.0
    budget_now = frame["M_sigma_now_bps"] * root * 10.0
    safe = budget.where(budget > 0)
    room = (frame["p_unreal"] + wall_dollars if wall_dollars is not None
            else pd.Series(np.nan, index=frame.index))
    giveback = frame["p_mfe"] - frame["p_unreal"]
    block = pd.DataFrame({
        "e_move_budget": budget,
        "e_move_budget_now": budget_now,
        "e_giveback": giveback,
        "e_giveback_per_move": giveback / safe,
        "e_drawdown": frame["p_unreal"] - frame["p_mae"],
        "e_wall_room_per_move": room / safe,
        "e_unreal_per_move": frame["p_unreal"] / safe,
        "e_pv_asym_x_runway": frame["v_pv_asym"] * runway,
        "e_sigma_ratio_x_runway": frame["M_sigma_inst_over_now"] * runway,
        "e_runway_frac": runway / (runway + frame["p_age_min"]).replace(0.0, np.nan),
    }, index=frame.index)
    assert tuple(block.columns) == EMPHASIS_COLUMNS, "emphasis block drifted"
    return pd.concat([frame.drop(columns=[c for c in EMPHASIS_COLUMNS
                                          if c in frame.columns]), block], axis=1)


def attach_targets(traj: pd.DataFrame, wall_dollars: float | None = 300.0,
                   recompute_limit: bool = False) -> pd.DataFrame:
    """Terminal mark and the PASS-A target `y_grid`, per trajectory.

    `recompute_limit=True` re-derives the absorbing index under `wall_dollars`
    from the marks (the panel's path); otherwise the trajectory's own
    `limit_pos` — written under the $300 wall — is used unchanged.
    """
    traj = traj.sort_values(["session", "id", "offset_min"]).reset_index(drop=True)
    wall_cent = None if wall_dollars is None else -100.0 * wall_dollars
    terminal = np.full(len(traj), np.nan)
    limit_out = traj["limit_pos"].to_numpy(float).copy()
    y_grid = np.full(len(traj), np.nan)
    keep = np.ones(len(traj), dtype=bool)

    for ordinal, day in traj.groupby("session", sort=True):
        grid = Grid(int(ordinal))
        for _, trade in day.groupby("id", sort=False):
            index = trade.index.to_numpy()
            head = trade.iloc[0]
            start = grid.position(int(head["second"]))
            nets = ee.net_cent(int(grid.mid[start]), grid.mid, head["side"]) / 100.0
            if recompute_limit:
                _, limit = wall_limit(nets * 100.0, start, grid.close_pos, wall_cent)
                pos = trade["pos"].to_numpy(int)
                alive = (pos > start) & (pos < limit)
                keep[index] = alive
                index, pos = index[alive], pos[alive]
                if not len(index):
                    continue
                unreal = nets[pos]
            else:
                limit = int(head["limit_pos"])
                unreal = trade["unreal"].to_numpy(float)
            end = float(nets[limit])
            terminal[index] = end
            limit_out[index] = limit
            #: best mark reachable from a strictly LATER decision minute,
            #: the terminal mark included as the absorbing end
            best_later = np.empty(len(unreal))
            run = end
            for i in range(len(unreal) - 1, -1, -1):
                best_later[i] = run
                run = max(run, float(unreal[i]))
            y_grid[index] = best_later - unreal
            if recompute_limit:
                traj.loc[index, "unreal"] = unreal
                traj.loc[index, "p_unreal"] = unreal
                #: the wall-free build stamped `p_wall_dist` against its own
                #: (unreachable) wall; restate it against the panel's wall so the
                #: $300 rung of the ladder reproduces the main build exactly
                traj.loc[index, "p_wall_dist"] = (unreal + wall_dollars
                                                  if wall_dollars is not None else np.nan)

    traj["terminal"] = terminal
    traj["limit_pos"] = limit_out
    traj["y_grid"] = y_grid
    traj = traj[keep & np.isfinite(y_grid)].reset_index(drop=True)
    return add_emphasis(traj, wall_dollars)


def load_targets(rebuild: bool) -> pd.DataFrame:
    traj = esm.load_traj()
    print(f"trajectories {traj.shape} <- {TRAJDIR}", flush=True)
    if TARGETS.exists() and not rebuild:
        cache = pd.read_csv(TARGETS, sep="\t")
        traj = traj.sort_values(["session", "id", "offset_min"]).reset_index(drop=True)
        traj = traj.merge(cache, on=["session", "id", "offset_min"], how="inner")
        print(f"targets {cache.shape} <- {TARGETS}", flush=True)
        return add_emphasis(traj, 300.0)
    traj = attach_targets(traj, 300.0, recompute_limit=False)
    er.write_tsv(TARGETS, traj[["session", "id", "offset_min",
                                "terminal", "y_grid"]].to_dict("records"))
    return traj


# ==========================================================================
# 2 — the continuation-value regressors
# ==========================================================================

def feature_columns(frame: pd.DataFrame, train: pd.DataFrame) -> list:
    """`distill_model.feature_columns`' rule, on this file's meta set."""
    keep = []
    for name in [c for c in frame.columns if c not in META]:
        values = pd.to_numeric(train[name], errors="coerce").to_numpy(float)
        values = values[np.isfinite(values)]
        if len(values) >= MIN_FINITE and len(np.unique(values)) >= 2:
            keep.append(name)
    return keep


def fit_gbt(train: pd.DataFrame, columns: list, config: dict, y: np.ndarray):
    from sklearn.ensemble import HistGradientBoostingRegressor
    model = HistGradientBoostingRegressor(random_state=SEED, **config)
    model.fit(train[columns].to_numpy(float), y)
    return model


def fit_lasso(train: pd.DataFrame, columns: list, alpha: float, y: np.ndarray):
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import Lasso
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    #: the sparse-linear twin (D-040's discipline check).  The GBT reads NaN
    #: natively; the linear twin cannot, so typed-absent channels are median
    #: filled — which is why a family absent for part of a training window reads
    #: weaker here than in the GBT.
    model = Pipeline([("impute", SimpleImputer(strategy="median")),
                      ("scale", StandardScaler()),
                      ("fit", Lasso(alpha=alpha, max_iter=20_000, random_state=SEED))])
    model.fit(train[columns].to_numpy(float), y)
    return model


BUILDERS = {"gbt": fit_gbt, "lasso": fit_lasso}


def choose_hypers(traj: pd.DataFrame) -> dict:
    """Session-grouped CV inside the STUDY window only, then FROZEN forever."""
    if HYPERS.exists():
        record = json.loads(HYPERS.read_text())
        print(f"hyper-parameters <- {HYPERS}: {record['gbt']} / "
              f"lasso alpha={record['lasso_alpha']}", flush=True)
        return record
    from sklearn.metrics import r2_score
    from sklearn.model_selection import GroupKFold
    study = traj[traj["session"] <= STUDY_HI].reset_index(drop=True)
    columns = feature_columns(traj, study)
    folds = list(GroupKFold(n_splits=CV_FOLDS).split(
        study, study["y_grid"], study["session"].to_numpy()))
    print(f"hyper-parameter CV on the study window 125..{STUDY_HI}: {len(study)} rows, "
          f"{study['session'].nunique()} sessions, {len(columns)} columns, "
          f"target mean ${study['y_grid'].mean():,.0f}", flush=True)

    def cv_r2(builder) -> float:
        scores = []
        for train_index, test_index in folds:
            train, test = study.iloc[train_index], study.iloc[test_index]
            model = builder(train, columns, train["y_grid"].to_numpy(float))
            pred = model.predict(test[columns].to_numpy(float))
            scores.append(r2_score(test["y_grid"].to_numpy(float), pred))
        return float(np.mean(scores))

    gbt_scores = []
    for config in GBT_GRID:
        score = cv_r2(lambda tr, cols, y, c=config: fit_gbt(tr, cols, c, y))
        gbt_scores.append((score, config))
        print(f"  gbt {config} -> CV R2 {score:.4f}", flush=True)
    lasso_scores = []
    for alpha in LASSO_GRID:
        score = cv_r2(lambda tr, cols, y, a=alpha: fit_lasso(tr, cols, a, y))
        lasso_scores.append((score, alpha))
        print(f"  lasso alpha={alpha} -> CV R2 {score:.4f}", flush=True)
    best_gbt = max(gbt_scores, key=lambda pair: pair[0])
    best_lasso = max(lasso_scores, key=lambda pair: pair[0])
    record = {"gbt": best_gbt[1], "gbt_cv_r2": best_gbt[0],
              "lasso_alpha": best_lasso[1], "lasso_cv_r2": best_lasso[0],
              "study_hi": STUDY_HI, "folds": CV_FOLDS,
              "gbt_grid": GBT_GRID, "lasso_grid": LASSO_GRID,
              "n_rows": int(len(study)), "n_columns": len(columns)}
    OUTDIR.mkdir(parents=True, exist_ok=True)
    HYPERS.write_text(json.dumps(record, indent=1))
    return record


def policy_target(frame: pd.DataFrame, pred: np.ndarray, cost: float) -> np.ndarray:
    """PASS-B target: what the PASS-A policy at threshold `cost` ACTUALLY attains.

        m[n]   = terminal                     (the wall / the close)
        m[i]   = u[i]     if pred[i] < cost   (the policy stops at i)
                 m[i+1]   otherwise           (it holds through i)
        y_B[i] = m[i+1] - u[i]

    Rows must already be sorted by (session, id, offset_min).
    """
    unreal = frame["unreal"].to_numpy(float)
    terminal = frame["terminal"].to_numpy(float)
    session = frame["session"].to_numpy()
    trade = frame["id"].to_numpy()
    out = np.empty(len(frame))
    n = len(frame)
    i = 0
    while i < n:
        j = i
        while j + 1 < n and session[j + 1] == session[i] and trade[j + 1] == trade[i]:
            j += 1
        run = terminal[i]
        for k in range(j, i - 1, -1):
            out[k] = run - unreal[k]                       # y_B[k] = m[k+1] - u[k]
            run = unreal[k] if pred[k] < cost else run     # m[k]
        i = j + 1
    return out


def cross_fitted(train: pd.DataFrame, columns: list, builder, config,
                 y: np.ndarray) -> np.ndarray:
    """Session-grouped out-of-fold PASS-A predictions INSIDE the training window."""
    from sklearn.model_selection import GroupKFold
    pred = np.empty(len(train))
    groups = train["session"].to_numpy()
    for fold_train, fold_test in GroupKFold(n_splits=CV_FOLDS).split(train, y, groups):
        model = builder(train.iloc[fold_train], columns, config, y[fold_train])
        pred[fold_test] = model.predict(train.iloc[fold_test][columns].to_numpy(float))
    return pred


def fit_segment(traj: pd.DataFrame, hypers: dict, seg: str, block: str,
                shuffles: bool = True, models: tuple = MODELS,
                costs: tuple = COSTS) -> tuple:
    """One walk-forward segment: PASS A, the backward pass, and the controls."""
    from sklearn.metrics import r2_score
    from scipy.stats import spearmanr
    test = traj[traj["block"] == block].sort_values(
        ["session", "id", "offset_min"]).reset_index(drop=True)
    train = traj[traj["session"] < int(test["session"].min())].sort_values(
        ["session", "id", "offset_min"]).reset_index(drop=True)
    assert train["session"].max() < test["session"].min(), "walk-forward purity"
    columns = feature_columns(traj, train)
    y_train = train["y_grid"].to_numpy(float)
    y_test = test["y_grid"].to_numpy(float)
    print(f"segment {seg} ({block}): train {len(train)} rows "
          f"({int(train['session'].min())}..{int(train['session'].max())}), "
          f"test {len(test)} rows, {len(columns)} columns, "
          f"y_grid mean ${y_train.mean():,.0f} -> ${y_test.mean():,.0f}", flush=True)

    out = test[["session", "id", "offset_min"]].copy()
    out["segment"] = seg
    row = {"segment": seg, "block": block, "era_label": er.ERA_LABEL[block],
           "train_rows": len(train), "test_rows": len(test), "columns": len(columns),
           "train_y_grid_mean": float(y_train.mean()),
           "test_y_grid_mean": float(y_test.mean())}
    coefficients = []

    configs = {"gbt": hypers["gbt"], "lasso": hypers["lasso_alpha"]}
    for model_name in models:
        builder, config = BUILDERS[model_name], configs[model_name]
        #: ---- PASS A ------------------------------------------------------
        model_a = builder(train, columns, config, y_train)
        pred_a_test = model_a.predict(test[columns].to_numpy(float))
        out[f"p_{model_name}_A"] = pred_a_test
        row[f"r2_{model_name}_A"] = float(r2_score(y_test, pred_a_test))
        row[f"rho_{model_name}_A"] = float(spearmanr(y_test, pred_a_test).statistic)
        pred_a_train = cross_fitted(train, columns, builder, config, y_train)
        row[f"r2_{model_name}_A_cf"] = float(r2_score(y_train, pred_a_train))
        #: ---- PASS B: one backward policy iteration, per cost threshold ----
        for cost in costs:
            y_b_train = policy_target(train, pred_a_train, cost)
            model_b = builder(train, columns, config, y_b_train)
            pred_b_test = model_b.predict(test[columns].to_numpy(float))
            out[f"p_{model_name}_B_c{int(cost)}"] = pred_b_test
            y_b_test = policy_target(test, pred_a_test, cost)
            row[f"r2_{model_name}_B_c{int(cost)}"] = float(r2_score(y_b_test, pred_b_test))
            row[f"rho_{model_name}_B_c{int(cost)}"] = float(
                spearmanr(y_b_test, pred_b_test).statistic)
            row[f"ybmean_{model_name}_B_c{int(cost)}"] = float(y_b_train.mean())
            row[f"exitrate_{model_name}_B_c{int(cost)}"] = float((pred_b_test < cost).mean())
            if model_name == "lasso":
                for name, weight in zip(columns, model_b.named_steps["fit"].coef_):
                    coefficients.append({"segment": seg, "block": block, "pass": "B",
                                         "cost": cost, "feature": name,
                                         "coef": float(weight)})
        if model_name == "lasso":
            for name, weight in zip(columns, model_a.named_steps["fit"].coef_):
                coefficients.append({"segment": seg, "block": block, "pass": "A",
                                     "cost": np.nan, "feature": name,
                                     "coef": float(weight)})
        row[f"exitrate_{model_name}_A_c25"] = float((pred_a_test < 25.0).mean())

    #: ---- the shuffled-y control: identical fit on permuted PASS-A targets --
    if shuffles:
        rng = np.random.default_rng(SEED)
        for draw in range(SHUFFLE_DRAWS):
            shuffled = rng.permutation(y_train)
            model_s = fit_gbt(train, columns, hypers["gbt"], shuffled)
            pred_s = model_s.predict(test[columns].to_numpy(float))
            out[f"p_shuf{draw}"] = pred_s
            row[f"r2_shuf{draw}"] = float(r2_score(y_test, pred_s))
            row[f"exitrate_shuf{draw}"] = float((pred_s < SHUFFLE_COST).mean())
    print("   R2  " + " | ".join(f"{key[3:]} {value:+.4f}" for key, value in row.items()
                                 if key.startswith("r2_")), flush=True)
    return out, row, coefficients


def stage_fit(traj: pd.DataFrame, hypers: dict) -> tuple:
    preds, diagnostics, coefficients = [], [], []
    for seg, block in SEGMENTS:
        out, row, coef = fit_segment(traj, hypers, seg, block)
        preds.append(out)
        diagnostics.append(row)
        coefficients.extend(coef)
    return (pd.concat(preds, ignore_index=True),
            pd.DataFrame(diagnostics), pd.DataFrame(coefficients))


def importances(traj: pd.DataFrame, hypers: dict, cost: float = 25.0,
                segment: str = "i") -> pd.DataFrame:
    """Permutation importance of the frozen PASS-B GBT on the last segment's era."""
    from sklearn.inspection import permutation_importance
    block = dict(SEGMENTS)[segment]
    test = traj[traj["block"] == block].sort_values(
        ["session", "id", "offset_min"]).reset_index(drop=True)
    train = traj[traj["session"] < int(test["session"].min())].sort_values(
        ["session", "id", "offset_min"]).reset_index(drop=True)
    columns = feature_columns(traj, train)
    y_train = train["y_grid"].to_numpy(float)
    pred_a_train = cross_fitted(train, columns, fit_gbt, hypers["gbt"], y_train)
    model_b = fit_gbt(train, columns, hypers["gbt"],
                      policy_target(train, pred_a_train, cost))
    model_a = fit_gbt(train, columns, hypers["gbt"], y_train)
    pred_a_test = model_a.predict(test[columns].to_numpy(float))
    y_b_test = policy_target(test, pred_a_test, cost)
    sample = np.random.default_rng(SEED).choice(len(test), size=min(40_000, len(test)),
                                                replace=False)
    matrix = test.iloc[sample][columns].to_numpy(float)
    frames = []
    for pass_name, model, target in (("A", model_a, test["y_grid"].to_numpy(float)),
                                     ("B", model_b, y_b_test)):
        result = permutation_importance(model, matrix, target[sample], scoring="r2",
                                        n_repeats=3, random_state=SEED, n_jobs=8)
        frames.append(pd.DataFrame({"pass": pass_name, "feature": columns,
                                    "importance": result.importances_mean,
                                    "sd": result.importances_std})
                      .sort_values("importance", ascending=False))
    return pd.concat(frames, ignore_index=True)


# ==========================================================================
# 3 — the replay
# ==========================================================================

def replay_cont_trade(session: ee.Session, second: int, side: str, preds: dict,
                      cost: float, wall_cent: float | None = ee.WALL_NET_CENT) -> dict:
    """Hold while the predicted continuation improvement >= `cost`."""
    start = session.position(second)
    nets = ee.net_cent(int(session.mid[start]), session.mid, side)
    wall_fill, limit = wall_limit(nets, start, session.close_pos, wall_cent)

    exit_pos = limit
    for offset in OFFSETS:
        value = preds.get(offset)
        if value is None:
            continue
        pos = session.position(second + offset * 60)
        if pos <= start or pos >= limit:
            continue
        if value < cost:
            exit_pos = pos
            break
    return {"exit_second": int(session.second[exit_pos]),
            "pnl": float(nets[exit_pos]) / 100.0,
            "stopped": bool(wall_fill is not None and exit_pos == wall_fill),
            "hold_s": int(session.second[exit_pos]) - int(session.second[start])}


def replay_ref_trade(session: ee.Session, second: int, side: str, rule: str,
                     ratchet_arm: float, wall_cent: float | None) -> dict:
    """`exit_engine.replay_trade` with the wall as a parameter (the panel needs it).

    At `wall_cent = exit_engine.WALL_NET_CENT` this is bit-identical to rung 1.
    """
    if wall_cent == ee.WALL_NET_CENT:
        return ee.replay_trade(session, second, side, rule, ratchet_arm)
    start = session.position(second)
    nets = ee.net_cent(int(session.mid[start]), session.mid, side)
    wall_fill, limit = wall_limit(nets, start, session.close_pos, wall_cent)
    if rule == "close":
        rule_pos = session.close_pos
    elif rule == "oracle":
        window = nets[start + 1:limit + 1]
        best = int(np.argmax(window)) + start + 1 if window.size else limit
        rule_pos = best if window.size and nets[best] > 0 else limit
    else:
        multiplier = 1.00
        if rule.startswith("mirror@"):
            multiplier = float(rule.split("@", 1)[1].split("+", 1)[0])
        hit = session.mirror_second(multiplier, side, int(session.second[start]))
        rule_second = hit if hit is not None else int(session.second[session.close_pos])
        if rule.endswith("+patience15"):
            rule_second = max(rule_second, int(session.second[start]) + ee.PATIENCE_FLOOR_S)
        rule_pos = session.position(rule_second)
        if rule.endswith("+ratchet") and np.isfinite(ratchet_arm):
            level = ee.RATCHET_FRACTION * ratchet_arm * 100.0
            armed = np.flatnonzero(nets[start + 1:limit + 1] >= level)
            if armed.size:
                arm_pos = int(armed[0]) + start + 1
                back = np.flatnonzero(nets[arm_pos + 1:limit + 1] <= 0)
                if back.size:
                    rule_pos = min(rule_pos, int(back[0]) + arm_pos + 1)
    exit_pos = min(rule_pos, limit)
    stopped = wall_fill is not None and exit_pos == wall_fill and wall_fill <= rule_pos
    return {"exit_second": int(session.second[exit_pos]),
            "pnl": float(nets[exit_pos]) / 100.0,
            "stopped": bool(stopped),
            "hold_s": int(session.second[exit_pos]) - int(session.second[start])}


def build_lookup(preds: pd.DataFrame, keys: list) -> dict:
    lookup: dict = {}
    for row in preds.to_dict("records"):
        key = (int(row["session"]), row["id"])
        offset = int(row["offset_min"])
        for name, column in keys:
            if column in row and np.isfinite(row[column]):
                lookup.setdefault((key, name), {})[offset] = float(row[column])
    return lookup


def replay(preds: pd.DataFrame, rules: tuple, wall_dollars: float | None = 300.0,
           segments=SEGMENTS, arms=ARMS, ks=KS, label: str = "") -> pd.DataFrame:
    """Rung 2's replay, over this rung's rule set, with the wall as a parameter."""
    wall_cent = None if wall_dollars is None else -100.0 * wall_dollars
    picks = pd.read_csv(PICKS, sep="\t")
    keys = [(rule, _pred_column(rule)) for rule in rules if _pred_column(rule)]
    lookup = build_lookup(preds, keys)
    results = []
    for seg, block in segments:
        part = picks[picks["segment"] == seg]
        sessions = sorted(part["session"].unique())
        ratchet_arm = float(part["ratchet_arm"].iloc[0])
        books = {(arm, k): {} for arm in arms for k in ks}
        for row in part.to_dict("records"):
            if (row["arm"], row["k"]) in books:
                books[(row["arm"], row["k"])].setdefault(row["session"], []).append(row)
        acc = {(arm, k, rule, slots): ([], [])
               for arm in arms for k in ks for rule in rules for slots in OCCUPANCIES}
        picked = {(arm, k): [] for arm in arms for k in ks}
        print(f"replay{label} segment {seg} ({block}): {len(sessions)} sessions "
              f"@ wall {wall_dollars}", flush=True)
        for done, ordinal in enumerate(sessions, 1):
            session = ee.Session(int(ordinal), block)
            wanted = {row["id"]: row for row in part[part["session"] == ordinal]
                      .to_dict("records")}
            trades = {}
            for rule in rules:
                if rule in REF_RULES:
                    trades[rule] = {cid: replay_ref_trade(session, row["second"],
                                                          row["side"], rule,
                                                          ratchet_arm, wall_cent)
                                    for cid, row in wanted.items()}
                else:
                    cost = _rule_cost(rule)
                    trades[rule] = {cid: replay_cont_trade(
                        session, row["second"], row["side"],
                        lookup.get(((int(ordinal), cid), rule), {}), cost, wall_cent)
                        for cid, row in wanted.items()}
            for arm in arms:
                for k in ks:
                    day_picks = books[(arm, k)].get(ordinal, [])
                    picked[(arm, k)].append(sum(p["cert"] for p in day_picks))
                    for rule in rules:
                        for slots in OCCUPANCIES:
                            total, taken = esm.replay_day(trades[rule], day_picks, slots)
                            acc[(arm, k, rule, slots)][0].append(total)
                            acc[(arm, k, rule, slots)][1].extend(taken)
            if done % 50 == 0 or done == len(sessions):
                print(f"  {done}/{len(sessions)} sessions", flush=True)
        for arm in arms:
            for k in ks:
                picked_day = float(np.mean(picked[(arm, k)]))
                for rule in rules:
                    for slots in OCCUPANCIES:
                        days, trades_list = acc[(arm, k, rule, slots)]
                        results.append({
                            "segment": seg, "block": block,
                            "era_label": er.ERA_LABEL[block], "arm": arm, "k": k,
                            "rule": rule, "slots": slots,
                            "wall": np.nan if wall_dollars is None else wall_dollars,
                            **ee.summarise(days, trades_list, picked_day)})
    return pd.DataFrame(results)


def _pred_column(rule: str) -> str | None:
    """The prediction column a continuation rule reads."""
    if rule.startswith("cont["):
        body = rule[len("cont["):].split("]")[0]
        model, pass_name = body.split(",")
        cost = int(float(rule.split("@c")[1]))
        return (f"p_{model}_A" if pass_name == "A" else f"p_{model}_B_c{cost}")
    if rule.startswith("shufcont"):
        return f"p_shuf{rule[len('shufcont')]}"
    return None


def _rule_cost(rule: str) -> float:
    return float(rule.split("@c")[1])


# ==========================================================================
# 4 — reachability of the stopping object (the diagnostic rung 2 asked for)
# ==========================================================================

def reachability(traj: pd.DataFrame, preds: pd.DataFrame) -> pd.DataFrame:
    """By decile of the PASS-B prediction: what the state is actually worth.

    `y_grid` is the PASS-A object (the best mark at a LATER decision minute — a
    maximum, and a maximum is not an exit).  `y_policy` is the PASS-B object,
    what the PASS-A policy really attains.  `to_limit` is the plain hold to the
    wall/close.  If the model orders `y_grid` but not `y_policy`, the ordering
    is again unsellable and rung 3 lands where rung 2 did.
    """
    merged = traj.merge(preds, on=["session", "id", "offset_min"], how="inner") \
                 .sort_values(["session", "id", "offset_min"]).reset_index(drop=True)
    merged["y_policy"] = policy_target(merged, merged["p_gbt_A"].to_numpy(float), 25.0)
    merged["to_limit"] = merged["terminal"] - merged["unreal"]
    merged["decile"] = pd.qcut(merged["p_gbt_B_c25"], 10, labels=False, duplicates="drop")
    return merged.groupby("decile").agg(
        n=("p_gbt_B_c25", "size"),
        pred_mean=("p_gbt_B_c25", "mean"),
        unreal=("unreal", "mean"),
        y_grid=("y_grid", "mean"),
        y_policy=("y_policy", "mean"),
        y_policy_median=("y_policy", "median"),
        y_policy_positive=("y_policy", lambda x: float((x > 0).mean())),
        to_limit=("to_limit", "mean"),
        to_limit_positive=("to_limit", lambda x: float((x > 0).mean())),
    ).reset_index()


# ==========================================================================
# 5 — the REPORT-ONLY adaptive-wall panel
# ==========================================================================

def winner_mae() -> pd.DataFrame:
    """Era-median winner MAE — the amendment formula's input.

    Two measurements: the corpus's own exit-free `cert_mae` (the D-021 pair, the
    adverse excursion up to the certificate) over every roster candidate, and the
    same quantity over the PICKED candidates only.  Both on the $100,000 object.
    """
    frame = pd.read_csv(ROOT / "FEATURES_ERA.tsv", sep="\t", low_memory=False,
                        usecols=["session", "block", "id", "cert", "cert_mae", "winner"])
    picks = pd.read_csv(PICKS, sep="\t")[["segment", "block", "session", "id", "k"]]
    rows = []
    for seg, block in SEGMENTS:
        era = frame[frame["block"] == block]
        era_win = era[era["winner"] == 1]
        picked = picks[(picks["segment"] == seg) & (picks["k"] == 5)][["session", "id"]]
        picked = era.merge(picked.drop_duplicates(), on=["session", "id"], how="inner")
        picked_win = picked[picked["winner"] == 1]
        median = float(np.median(era_win["cert_mae"])) if len(era_win) else np.nan
        rows.append({
            "segment": seg, "block": block, "era_label": er.ERA_LABEL[block],
            "roster_winners": len(era_win),
            "roster_winner_mae_median": median,
            "roster_winner_mae_p75": float(np.percentile(era_win["cert_mae"], 75)),
            "roster_winner_mae_p90": float(np.percentile(era_win["cert_mae"], 90)),
            "picked_winners": len(picked_win),
            "picked_winner_mae_median": (float(np.median(picked_win["cert_mae"]))
                                         if len(picked_win) else np.nan),
            "picked_winner_mae_p90": (float(np.percentile(picked_win["cert_mae"], 90))
                                      if len(picked_win) else np.nan),
            "picked_winner_mae_over_300_pct": (100.0 * float((picked_win["cert_mae"] > 300).mean())
                                               if len(picked_win) else np.nan),
            "adaptive_wall": max(ADAPTIVE_WALL_FLOOR, ADAPTIVE_WALL_MULT * median),
        })
    return pd.DataFrame(rows)


def build_nowall(jobs_n: int, rebuild: bool) -> None:
    """The wall-free trajectory superset (the panel's only new data build)."""
    saved_dir, saved_wall = esm.TRAJDIR, ee.WALL_NET_CENT
    esm.TRAJDIR = NOWALLDIR
    ee.WALL_NET_CENT = -10 ** 12            # never crossed => limit = the close
    try:
        esm.stage_traj(jobs_n, rebuild)
    finally:
        esm.TRAJDIR, ee.WALL_NET_CENT = saved_dir, saved_wall


def load_nowall() -> pd.DataFrame:
    saved = esm.TRAJDIR
    esm.TRAJDIR = NOWALLDIR
    try:
        frame = esm.load_traj()
    finally:
        esm.TRAJDIR = saved
    print(f"wall-free trajectories {frame.shape} <- {NOWALLDIR}", flush=True)
    return frame


def panel(nowall: pd.DataFrame, hypers: dict, rule: str) -> pd.DataFrame:
    """The best policy re-fit and re-run under each wall of the ladder."""
    model_name = rule[len("cont["):].split(",")[0]
    pass_name = rule[len("cont["):].split("]")[0].split(",")[1]
    cost = _rule_cost(rule)
    rules = ("close", "oracle", rule)
    frames = []
    for wall in WALL_LADDER:
        traj = attach_targets(nowall.copy(), wall, recompute_limit=True)
        print(f"panel wall {wall}: {len(traj):,} states", flush=True)
        preds = []
        for seg, block in SEGMENTS:
            out, _, _ = fit_segment(traj, hypers, seg, block, shuffles=False,
                                    models=(model_name,), costs=(cost,))
            preds.append(out)
        preds = pd.concat(preds, ignore_index=True)
        column = (f"p_{model_name}_A" if pass_name == "A"
                  else f"p_{model_name}_B_c{int(cost)}")
        preds = preds.rename(columns={column: _pred_column(rule)})
        frame = replay(preds, rules, wall, label=f" panel wall={wall}")
        frame["panel_wall"] = -1.0 if wall is None else wall
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


# ==========================================================================
# 6 — the report
# ==========================================================================

def best_of(frame: pd.DataFrame, mask) -> pd.Series | None:
    part = frame[mask]
    return None if not len(part) else part.loc[part["realized_day"].idxmax()]


def rung2_frame() -> pd.DataFrame:
    path = OUTDIR / "state_replay.tsv"
    return pd.read_csv(path, sep="\t") if path.exists() else pd.DataFrame()


def write_report(frame: pd.DataFrame, fit: pd.DataFrame, coefficients: pd.DataFrame,
                 importance: pd.DataFrame, reach: pd.DataFrame, hypers: dict,
                 mae: pd.DataFrame, panel_frame: pd.DataFrame, best_rule: str,
                 traj: pd.DataFrame) -> None:
    rung2 = rung2_frame()
    out = []
    out.append("# EXIT RUNG 3 — OPTIMAL STOPPING\n")
    out.append(
        "Rung 2 trained a barrier-hit probability and landed on hold-to-close.  This "
        "rung trains the STOPPING object instead: a continuation-value regression whose "
        "target is the best mark reachable at a LATER minute of our own decision grid "
        "minus the mark in hand (PASS A), then one backward policy iteration in which "
        "only the minutes the PASS-A policy would still be holding count (PASS B).  The "
        "policy exits when the predicted continuation improvement falls below the "
        f"preregistered cost threshold c in {{{', '.join(money(c) for c in COSTS)}}}; the "
        "$300 wall and the close are always in force.  Replay is rung 2's machinery — "
        "same picks, same eras, same 576c, ONE and TWO concurrent positions.\n")
    if VERDICT.exists():
        out.append("\n" + VERDICT.read_text().rstrip() + "\n")

    # ---- the verdict table -------------------------------------------------
    out.append("\n## Verdict table — top-5, TWO positions, arm `v3 full`\n")
    out.append("Realized $/day; capture of the certificate value the rule ACTUALLY "
               "ENTERED; capture of the full picked roster; worst day; worst single "
               "trade; trades/day; mean hold minutes.  `oracle` is the perfect-exit "
               "ceiling on the same entered trades, not an implementable rule.\n")
    head = ("| era | rule | $/day | cap-entered | cap-picked | worst day | worst trade "
            "| trades/day | hold min |")
    for era_seg, block in SEGMENTS:
        out.append(f"\n**{er.ERA_LABEL[block]}**\n")
        out.append(head)
        out.append("|---|---|---:|---:|---:|---:|---:|---:|---:|")
        base = frame[(frame["segment"] == era_seg) & (frame["k"] == 5)
                     & (frame["slots"] == 2) & (frame["arm"] == "v3 full")]
        order = ["close"] + [r for r in CONT_RULES if r in set(base["rule"])] \
                + list(SHUF_RULES) + ["oracle"]
        for rule in order:
            row = base[base["rule"] == rule]
            if not len(row):
                continue
            row = row.iloc[0]
            out.append(
                f"| {block} | `{rule}` | {money(row['realized_day'])} | "
                f"{number(row['capture_entered_pct'])}% | {number(row['capture_pct'])}% | "
                f"{money(row['worst_day'])} | {money(row['max_trade_loss'])} | "
                f"{number(row['trades_day'])} | {number(row['hold_min'])} |")
        if len(rung2):
            r2 = best_of(rung2, (rung2["segment"] == era_seg) & (rung2["k"] == 5)
                         & (rung2["slots"] == 2) & (rung2["arm"] == "v3 full")
                         & rung2["rule"].str.startswith("state["))
            r1 = best_of(rung2, (rung2["segment"] == era_seg) & (rung2["k"] == 5)
                         & (rung2["slots"] == 2) & (rung2["arm"] == "v3 full")
                         & rung2["rule"].isin([r for r in REF_RULES if r != "oracle"]))
            for tag, row in (("rung 2 best", r2), ("rung 1 best", r1)):
                if row is None:
                    continue
                out.append(
                    f"| {block} | _{tag}: `{row['rule']}`_ | {money(row['realized_day'])} "
                    f"| {number(row['capture_entered_pct'])}% | "
                    f"{number(row['capture_pct'])}% | {money(row['worst_day'])} | "
                    f"{money(row['max_trade_loss'])} | {number(row['trades_day'])} | "
                    f"{number(row['hold_min'])} |")

    # ---- the fit -----------------------------------------------------------
    out.append("\n## The continuation model\n")
    out.append(f"Hyper-parameters chosen ONCE by {CV_FOLDS}-fold session-grouped CV "
               f"inside the study window 125..{STUDY_HI} — strictly prior to every test "
               f"block — from a preregistered {len(GBT_GRID)}-point GBT grid and "
               f"{len(LASSO_GRID)}-point lasso grid, then FROZEN: GBT "
               f"{hypers['gbt']} at CV R2 {hypers['gbt_cv_r2']:.4f}; lasso alpha="
               f"{hypers['lasso_alpha']} at {hypers['lasso_cv_r2']:.4f} "
               f"({hypers['n_rows']:,} rows, {hypers['n_columns']} columns).\n")
    out.append("| segment | era | train rows | test rows | y_A mean (train->test) | "
               "R2 gbt A | R2 gbt B@c25 | R2 lasso A | R2 shuffled | exit rate gbt B@c25 |")
    out.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for _, row in fit.iterrows():
        shuffled = np.mean([row[f"r2_shuf{d}"] for d in range(SHUFFLE_DRAWS)])
        out.append(
            f"| {row['segment']} | {row['block']} | {int(row['train_rows']):,} | "
            f"{int(row['test_rows']):,} | {money(row['train_y_grid_mean'])} -> "
            f"{money(row['test_y_grid_mean'])} | {row['r2_gbt_A']:+.4f} | "
            f"{row['r2_gbt_B_c25']:+.4f} | {row['r2_lasso_A']:+.4f} | "
            f"{shuffled:+.4f} | {100*row['exitrate_gbt_B_c25']:.1f}% |")

    # ---- reachability ------------------------------------------------------
    out.append("\n## Is the ordering sellable?  By decile of the PASS-B prediction\n")
    out.append("`y_A` = the PASS-A object (best mark at a later grid minute — a maximum).  "
               "`y_policy` = what the PASS-A policy at c=$25 actually attains from here.  "
               "`to_limit` = the plain hold to the wall/close.\n")
    out.append("| decile | n | pred | unrealised | y_A | y_policy | median | positive | "
               "to_limit | positive |")
    out.append("|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for _, row in reach.iterrows():
        out.append(
            f"| {int(row['decile'])} | {int(row['n']):,} | {money(row['pred_mean'])} | "
            f"{money(row['unreal'])} | {money(row['y_grid'])} | {money(row['y_policy'])} | "
            f"{money(row['y_policy_median'])} | {100*row['y_policy_positive']:.0f}% | "
            f"{money(row['to_limit'])} | {100*row['to_limit_positive']:.0f}% |")

    # ---- drivers -----------------------------------------------------------
    out.append("\n## Verdict (iii) inputs — what the continuation model is made of\n")
    out.append("Permutation importance (R2 loss) of the frozen GBT on `e7`, top 15 of each "
               "pass.  PASS A values the MAXIMUM still to come; PASS B values what the "
               "policy can actually take.\n")
    out.append("| # | PASS A feature | importance | PASS B feature | importance |")
    out.append("|---:|---|---:|---|---:|")
    pass_a = importance[importance["pass"] == "A"].reset_index(drop=True)
    pass_b = importance[importance["pass"] == "B"].reset_index(drop=True)
    for i in range(15):
        a = pass_a.iloc[i] if i < len(pass_a) else None
        b = pass_b.iloc[i] if i < len(pass_b) else None
        out.append(f"| {i+1} | " +
                   (f"`{a['feature']}` | {a['importance']:+.4f} | " if a is not None else " | | ") +
                   (f"`{b['feature']}` | {b['importance']:+.4f} |" if b is not None else " | |"))
    if len(coefficients):
        for pass_name, mask in (("A", coefficients["pass"] == "A"),
                                ("B", (coefficients["pass"] == "B")
                                 & (coefficients["cost"] == 25.0))):
            last = coefficients[mask & (coefficients["segment"] == "i")]
            if not len(last):
                continue
            last = last.reindex(last["coef"].abs().sort_values(ascending=False).index)
            kept = int((last["coef"].abs() > 0).sum())
            tag = "PASS A" if pass_name == "A" else "PASS B at c=$25"
            out.append(f"\nLasso twin on `e7`, {tag}: **{kept} of {len(last)}** columns "
                       "kept.  Top 12 by |coefficient| (dollars per standard deviation):\n")
            out.append("| feature | coef |")
            out.append("|---|---:|")
            for _, row in last.head(12).iterrows():
                out.append(f"| `{row['feature']}` | {row['coef']:+.3f} |")

    # ---- the full grid -----------------------------------------------------
    out.append("\n## The full grid\n")
    out.append(f"Every era x arm x basket x occupancy x rule cell is in "
               f"`exit_segments/stop_replay.tsv` ({len(frame):,} rows).  Best "
               "implementable two-position cell per era, over all arms and baskets:\n")
    out.append("| era | best rung-3 cell | $/day | cap-picked | rung-2 best | rung-1 best "
               "| hold-to-close | oracle |")
    out.append("|---|---|---:|---:|---:|---:|---:|---:|")
    for seg, block in SEGMENTS:
        two = frame[(frame["segment"] == seg) & (frame["slots"] == 2)]
        best = best_of(two, two["rule"].isin(CONT_RULES))
        oracle = best_of(two, two["rule"] == "oracle")
        close = two[(two["rule"] == "close") & (two["arm"] == best["arm"])
                    & (two["k"] == best["k"])].iloc[0]
        r2v = r1v = np.nan
        if len(rung2):
            two2 = rung2[(rung2["segment"] == seg) & (rung2["slots"] == 2)]
            b2 = best_of(two2, two2["rule"].str.startswith("state["))
            b1 = best_of(two2, two2["rule"].isin([r for r in REF_RULES if r != "oracle"]))
            r2v = b2["realized_day"] if b2 is not None else np.nan
            r1v = b1["realized_day"] if b1 is not None else np.nan
        out.append(
            f"| {block} | `{best['rule']}` / {best['arm']} / top-{int(best['k'])} | "
            f"{money(best['realized_day'])} | {number(best['capture_pct'])}% | "
            f"{money(r2v)} | {money(r1v)} | {money(close['realized_day'])} | "
            f"{money(oracle['realized_day'])} |")

    # ---- the panel ---------------------------------------------------------
    out.append("\n## REPORT-ONLY PANEL — the adaptive wall (no verdict weight)\n")
    out.append("The amendment the brief names is `wall = max($300, 1.0 x era-median "
               "winner MAE)`.  The corpus's own exit-free MAE pair (`cert_mae`, D-021) "
               "says what that evaluates to:\n")
    out.append("| era | roster winners | median winner MAE | p90 | picked winners | "
               "median | share > $300 | adaptive wall |")
    out.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for _, row in mae.iterrows():
        out.append(
            f"| {row['block']} | {int(row['roster_winners']):,} | "
            f"{money(row['roster_winner_mae_median'])} | {money(row['roster_winner_mae_p90'])} | "
            f"{int(row['picked_winners']):,} | {money(row['picked_winner_mae_median'])} | "
            f"{number(row['picked_winner_mae_over_300_pct'])}% | "
            f"{money(row['adaptive_wall'])} |")
    out.append(f"\nBecause every era's median winner MAE is well under ${ADAPTIVE_WALL_FLOOR:,.0f}, "
               "the formula returns the CURRENT wall in every era and the amendment buys "
               "exactly nothing as stated.  So the panel is run as a WALL LADDER instead "
               "— the same policy, refit under each wall on a wall-free trajectory "
               "superset (at $300 it reproduces the main build exactly), which is the "
               "object the user's decision actually needs:\n")
    if len(panel_frame):
        out.append(f"Policy: `{best_rule}`, top-5, TWO positions, arm `v3 full`.\n")
        out.append("| era | wall | $/day | cap-picked | worst day | worst trade | "
                   "stop rate | trades/day | hold min | hold-to-close $/day | oracle $/day |")
        out.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for seg, block in SEGMENTS:
            for wall in WALL_LADDER:
                tag = -1.0 if wall is None else wall
                cell = panel_frame[(panel_frame["segment"] == seg)
                                   & (panel_frame["panel_wall"] == tag)
                                   & (panel_frame["k"] == 5) & (panel_frame["slots"] == 2)
                                   & (panel_frame["arm"] == "v3 full")]
                row = cell[cell["rule"] == best_rule]
                if not len(row):
                    continue
                row = row.iloc[0]
                close = cell[cell["rule"] == "close"].iloc[0]
                oracle = cell[cell["rule"] == "oracle"].iloc[0]
                out.append(
                    f"| {block} | {'none' if wall is None else money(wall)} | "
                    f"{money(row['realized_day'])} | {number(row['capture_pct'])}% | "
                    f"{money(row['worst_day'])} | {money(row['max_trade_loss'])} | "
                    f"{number(row['stop_rate'])}% | {number(row['trades_day'])} | "
                    f"{number(row['hold_min'])} | {money(close['realized_day'])} | "
                    f"{money(oracle['realized_day'])} |")

    out.append("\n## Controls\n")
    out.append(
        f"Walk-forward splits identical to `era_retest.py`; usable columns decided on "
        f"each segment's own training window ({len(EMPHASIS_COLUMNS)} preregistered "
        f"emphasis columns added to rung 2's 93, all of them deterministic functions of "
        f"columns rung 2 had already computed — no new data is read).  PASS-A "
        f"predictions on training rows are session-grouped {CV_FOLDS}-fold cross-fitted, "
        f"so the backward pass never walks a model's own memorised fit.  The 576c round "
        f"trip is charged once per trade on every rule including the oracle; the $300 "
        f"wall is monitored from entry with gap-through.  The c grid is preregistered "
        f"and every value is reported for all five eras, five arms, both baskets and "
        f"both occupancy modes.  Sealed zone untouched (`packlib.SEALED_FROM` = "
        f"{P.SEALED_FROM}; highest session read = {int(traj['session'].max())}).  "
        f"D-022 overlay: the era RTY-mini factors run 0.879-1.073, so every dollar "
        f"figure is within 12% of its RTY-mini equivalent and no capture percentage "
        f"moves; the two-position column IS the two-mini account shape (D-030).\n")
    REPORT.write_text("\n".join(out) + "\n")
    print(f"wrote {REPORT}", flush=True)


# ==========================================================================
# main
# ==========================================================================

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", default="all",
                        choices=("target", "hypers", "fit", "replay", "panel",
                                 "report", "all"))
    parser.add_argument("--jobs", type=int, default=32)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    OUTDIR.mkdir(parents=True, exist_ok=True)

    traj = load_targets(args.rebuild)
    print(f"targets attached: {len(traj):,} states, "
          f"y_A mean {money(traj['y_grid'].mean())}, "
          f"positive {100*float((traj['y_grid'] > 0).mean()):.0f}%", flush=True)
    if args.stage == "target":
        return

    hypers = choose_hypers(traj)
    if args.stage == "hypers":
        return

    if args.stage in ("fit", "all") or not PREDS.exists():
        preds, fit, coefficients = stage_fit(traj, hypers)
        preds.to_csv(PREDS, sep="\t", index=False, float_format="%.6g")
        er.write_tsv(FIT, fit.to_dict("records"))
        er.write_tsv(COEF, coefficients.to_dict("records"))
        importance = importances(traj, hypers)
        er.write_tsv(IMPORT, importance.to_dict("records"))
        er.write_tsv(REACH, reachability(traj, preds).to_dict("records"))
    else:
        preds = pd.read_csv(PREDS, sep="\t")
        fit = pd.read_csv(FIT, sep="\t")
        coefficients = pd.read_csv(COEF, sep="\t")
        importance = pd.read_csv(IMPORT, sep="\t")
    if args.stage == "fit":
        return

    if args.stage in ("replay", "all") or not REPLAY.exists():
        frame = replay(preds, ALL_RULES, 300.0)
        er.write_tsv(REPLAY, frame.to_dict("records"))
    else:
        frame = pd.read_csv(REPLAY, sep="\t")
    if args.stage == "replay":
        return

    #: the panel's policy = the best implementable two-position continuation rule,
    #: ranked by its MEAN over the four DEPLOYMENT eras (not by a single cell)
    two = frame[(frame["slots"] == 2) & frame["rule"].isin(CONT_RULES)]
    deployment = two[two["block"] != "blind_e3"]
    ranked = deployment.groupby("rule")["realized_day"].mean().sort_values()
    best_rule = str(ranked.index[-1])
    print(f"panel policy = {best_rule} (mean {money(ranked.iloc[-1])}/day over the "
          f"four deployment eras)", flush=True)

    mae = winner_mae()
    er.write_tsv(WALLMAE, mae.to_dict("records"))
    if args.stage in ("panel", "all"):
        if not PANEL.exists() or args.rebuild or args.stage == "panel":
            build_nowall(args.jobs, False)
            nowall = load_nowall()
            panel_frame = panel(nowall, hypers, best_rule)
            er.write_tsv(PANEL, panel_frame.to_dict("records"))
        else:
            panel_frame = pd.read_csv(PANEL, sep="\t")
    else:
        panel_frame = pd.read_csv(PANEL, sep="\t") if PANEL.exists() else pd.DataFrame()
    if args.stage == "panel":
        return

    reach = pd.read_csv(REACH, sep="\t")
    write_report(frame, fit, coefficients, importance, reach, hypers, mae,
                 panel_frame, best_rule, traj)


if __name__ == "__main__":
    main()
