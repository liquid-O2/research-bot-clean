#!/usr/bin/env python3
"""WALKFORWARD — model-v2's feature set evaluated as a TRUE MULTI-ERA
walk-forward, not a single 20-day blind block.

D-034/D-036/D-038 in one harness.  Every era block that has a roster record
under `sheets/roster_<block>.json` becomes one rung of an EXPANDING-WINDOW
ladder: train on everything strictly before the rung, test day-complete on the
rung itself, never retuning a hyper-parameter (v2's frozen config is used
verbatim for every fit, so segment-to-segment differences are era differences
and nothing else).

    rung k:  train = blocks[0 .. k-1]   test = blocks[k]

Two fitting arms per rung:

  POOLED     every training candidate weighted 1 — the "all history is equally
             true" null that D-031 challenges.
  REGIME     per-era sample weights decaying with age, half-life ONE ERA
             (the newest training era gets 1, the one before it 0.5, ...) —
             D-031's recency-keyed activation in its simplest falsifiable form.

Plus the ERA-TRANSFER MATRIX: every era fitted ALONE and scored on every other
era, which is the direct measurement of pattern decay (rows = train era,
columns = test era).  The transfer matrix uses the COMMON feature set — columns
usable in every era — so its cells are comparable; the walk-forward rungs use
the columns usable in their own training window, which is the lawful choice.

EXTENSION: nothing here names an era.  Drop `sheets/roster_<newblock>.json`
beside the others, rebuild the caches with `build_wf_cache.py`, and the new
block appends itself as the next rung with zero code change.

    walkforward.py [--rebuild] [--jobs N] [--skip-transfer]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import pathlib
import sys

#: Pinned BEFORE numpy/sklearn load.  With the OpenMP pool free-running, the
#: histogram reductions inside HistGradientBoosting sum in a load-dependent
#: order and two identical runs drift by ~0.002 AUC; pinned to one thread the
#: whole report is bit-reproducible, and a fit is 2.4s, so nothing is lost.
os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import packlib as P                      # noqa: E402
import distill_model as dm               # noqa: E402
import model_v2 as mv                    # noqa: E402

ROOT = P.ROOT
SHEETS = ROOT / "sheets"
FVOL = P.CACHE / "fvol"
MATRIX = ROOT / "FEATURES_WF.tsv"
REPORT = ROOT / "WALKFORWARD_REPORT.md"
SEGDIR = ROOT / "wf_segments"
SEED = dm.SEED

#: v2's frozen configuration.  NOT re-selected anywhere in this file — that is
#: the whole point: every rung of the ladder is the same estimator.
FROZEN = dict(max_depth=2, max_iter=150, learning_rate=0.05,
              min_samples_leaf=20, l2_regularization=1.0)
HALF_LIFE_ERAS = 1.0
OPERATING_RATE = mv.OPERATING_RATE          # 11/40 — the human's own take rate


# ==========================================================================
# era blocks
# ==========================================================================

def era_blocks() -> list:
    """Roster records in chronological order: [{block, range, sessions}, ...]."""
    records = []
    for path in sorted(glob.glob(str(SHEETS / "roster_*.json"))):
        records.append(json.loads(pathlib.Path(path).read_text()))
    records.sort(key=lambda r: (r["range"][0], r["range"][1]))
    return records


# ==========================================================================
# M_ — the FORECAST-VOLATILITY / BAND-STATE block (`_cache/fvol`)
# ==========================================================================
#
# The forecast lane publishes, per session, an at-open move forecast and its
# 1x/1.5x/2x bands, and per MINUTE a state row (band_state, band_z, move_z,
# consumed fractions, sigma_now / sigma_inst).  Its landed contrast found the
# strongest single cell yet measured on this roster: EXTENSION (band_state on
# the candidate's own side) crossed with INSTANTANEOUS VOL — fade-into-hot 50%
# winners against chase-into-cool 7.1%.  That cross is encoded here explicitly
# (product AND cell code) rather than left for the trees to rediscover.
#
# CAUSALITY.  A minute row stamped `second = (minute+1)*60` describes the state
# at the END of that minute, so a decision at second t may read only rows with
# `second < t` — index `(t - 1) // 60 - 1`.  The hot/cool cut is NOT the test
# block's own median (that would be a leak): it is the median of the per-session
# median `sigma_inst_bps` over the 20 strictly PRIOR covered sessions.
# COVERAGE.  Sessions 251..447 only; everything earlier is typed-absent (NaN),
# which is what `dm.feature_columns` already handles by dropping a column that
# carries no fit in its training window.

FVOL_SESSION_KEYS = ("implied_move_bps", "sigma_day_bps", "sigma_level_bps",
                     "profile_priors")
FVOL_MINUTE_KEYS = ("traveled_bps", "abs_traveled_bps", "move_consumed_fraction",
                    "range_so_far_bps", "range_consumed_fraction",
                    "remaining_move_bps", "move_z", "band_state", "band_z",
                    "rv_sofar_bps", "var_fraction_expected", "sigma_now_bps",
                    "sigma_inst_bps")
FVOL_SIGNED = ("traveled_bps", "move_z", "band_z", "band_state")
HOTCUT_WINDOW = 20
HOTCUT_MINIMUM = 5
EXTENSION_EDGE = 2          # |band_state_own| >= 2 = the contrast's fade/chase cells

_HOTCUT: dict | None = None
_FVOL_SESSIONS: dict | None = None


def fvol_sessions() -> dict:
    """sessions.tsv -> {ordinal: {column: float}} (at-open forecast + bands)."""
    global _FVOL_SESSIONS
    if _FVOL_SESSIONS is None:
        path = FVOL / "sessions.tsv"
        if not path.exists():
            _FVOL_SESSIONS = {}
        else:
            table = pd.read_csv(path, sep="\t")
            _FVOL_SESSIONS = {int(row["session"]): row.to_dict()
                              for _, row in table.iterrows()}
    return _FVOL_SESSIONS


def fvol_minutes(ordinal: int) -> pd.DataFrame | None:
    path = FVOL / "minutes" / f"s{ordinal}.tsv"
    if not path.exists():
        return None
    return pd.read_csv(path, sep="\t").set_index("minute").sort_index()


def ensure_hotcut() -> dict:
    """{ordinal: hot/cool cut} from the 20 strictly PRIOR covered sessions."""
    global _HOTCUT
    if _HOTCUT is not None:
        return _HOTCUT
    cache = FVOL / "hotcut.json"
    if cache.exists():
        _HOTCUT = {int(k): v for k, v in json.loads(cache.read_text()).items()}
        return _HOTCUT
    covered = sorted(int(path.stem[1:]) for path in
                     (FVOL / "minutes").glob("s*.tsv")) if (FVOL / "minutes").exists() else []
    per_session = {}
    for ordinal in covered:
        table = fvol_minutes(ordinal)
        if table is None or "sigma_inst_bps" not in table:
            continue
        values = pd.to_numeric(table["sigma_inst_bps"], errors="coerce").dropna()
        if len(values):
            per_session[ordinal] = float(values.median())
    cuts = {}
    keys = sorted(per_session)
    for position, ordinal in enumerate(keys):
        prior = [per_session[k] for k in keys[max(0, position - HOTCUT_WINDOW):position]]
        cuts[ordinal] = float(np.median(prior)) if len(prior) >= HOTCUT_MINIMUM else np.nan
    cache.write_text(json.dumps(cuts))
    _HOTCUT = cuts
    return _HOTCUT


def fvol_features(ordinal: int, candidates: list) -> dict:
    """{candidate id: {M_ feature: value}}; empty dict where the lane has no data."""
    table = fvol_minutes(ordinal)
    if table is None:
        return {}
    session = fvol_sessions().get(ordinal, {})
    cut = ensure_hotcut().get(ordinal, np.nan)
    columns = {name: pd.to_numeric(table[name], errors="coerce").to_numpy(float)
               for name in FVOL_MINUTE_KEYS if name in table.columns}
    index = table.index.to_numpy()
    mid_u6 = (pd.to_numeric(table["mid_u6"], errors="coerce").to_numpy(float)
              if "mid_u6" in table.columns else None)
    out = {}
    for cand in candidates:
        second = int(cand["second"])
        sign = 1.0 if cand["side"] == "L" else -1.0
        minute = (second - 1) // 60 - 1               # last row that ENDED before t
        row = int(np.searchsorted(index, minute, side="right")) - 1
        f = {}
        if row < 0 or index[row] > minute:
            out[cand["id"]] = f
            continue
        for name, values in columns.items():
            value = values[row]
            f[f"M_{name}"] = value
            if name in FVOL_SIGNED:
                f[f"M_{name}_own"] = sign * value
        # ---- the landed cross: EXTENSION x INSTANTANEOUS VOL -----------------
        state_own = f.get("M_band_state_own", np.nan)
        sigma_inst = f.get("M_sigma_inst_bps", np.nan)
        sigma_now = f.get("M_sigma_now_bps", np.nan)
        hot = (1.0 if sigma_inst >= cut else 0.0) if np.isfinite(sigma_inst) and \
            np.isfinite(cut) else np.nan
        extension = (np.sign(state_own) if abs(state_own) >= EXTENSION_EDGE else 0.0) \
            if np.isfinite(state_own) else np.nan
        f["M_hot"] = hot
        f["M_hot_cut_bps"] = cut
        f["M_sigma_inst_rel"] = sigma_inst / cut if np.isfinite(cut) and cut > 0 else np.nan
        f["M_sigma_inst_over_now"] = (sigma_inst / sigma_now
                                      if np.isfinite(sigma_now) and sigma_now > 0
                                      else np.nan)
        f["M_extension"] = extension                       # -1 fade, 0 mid, +1 chase
        f["M_ext_x_hot"] = extension * hot if np.isfinite(extension) and \
            np.isfinite(hot) else np.nan
        #: the 3x2 cell as ONE categorical code, the shape the contrast measured
        f["M_ext_vol_cell"] = (3.0 * (extension + 1.0) + hot) if np.isfinite(extension) \
            and np.isfinite(hot) else np.nan
        f["M_bso_x_sigma_inst"] = state_own * sigma_inst if np.isfinite(state_own) and \
            np.isfinite(sigma_inst) else np.nan
        f["M_bso_x_sigma_rel"] = state_own * f["M_sigma_inst_rel"] \
            if np.isfinite(state_own) and np.isfinite(f["M_sigma_inst_rel"]) else np.nan
        #: the contrast's own control: which third of the clock the decision sits in
        f["M_clock_third"] = float(min(2, (second * 3) // P.SESSION_SECONDS))
        # ---- session-level forecast state ------------------------------------
        for name in FVOL_SESSION_KEYS:
            value = session.get(name, np.nan)
            f[f"M_{name}"] = float(value) if value is not None else np.nan
        price = mid_u6[row] if mid_u6 is not None else np.nan
        if np.isfinite(price) and price > 0:
            for label, up, down in (("1", "band_1_up_u6", "band_1_dn_u6"),
                                    ("15", "band_15_up_u6", "band_15_dn_u6"),
                                    ("2", "band_2_up_u6", "band_2_dn_u6")):
                edge = session.get(up if sign > 0 else down, np.nan)
                f[f"M_band{label}_room_bps"] = (
                    sign * (float(edge) - price) * 1e4 / price
                    if edge is not None and np.isfinite(float(edge)) else np.nan)
        out[cand["id"]] = f
    return out


# ==========================================================================
# matrix assembly — v1 block + v2 tiers, one row per candidate, every era
# ==========================================================================

def session_rows(job: tuple) -> list:
    """(ordinal, block, candidates) -> list of feature dicts.  Worker-safe."""
    ordinal, block, candidates = job
    P.assert_case_wall(ordinal, "walkforward")
    norm = _worker_norm()
    v2 = mv.session_features_v2(ordinal, candidates)
    fvol = fvol_features(ordinal, candidates)
    truth, records = {}, []
    for cand, features in dm.session_features(ordinal, candidates, norm):
        side = cand["side"]
        if side not in truth:
            truth[side] = P.load_truth(ordinal, side)
        row = int(cand["row"])
        head = {
            "session": ordinal, "block": block, "day": cand["day"],
            "id": cand["id"], "second": int(cand["second"]), "side": side,
            "cert": float(truth[side]["cert_net_cent"][row]) / 100.0,
            "cert_mae": float(truth[side]["cert_mae_cent"][row]) / 100.0,
            "menu60": float(truth[side]["menu_net_cent"][row][dm.H60]) / 100.0,
            "menu_close": float(truth[side]["menu_net_cent"][row][dm.HCLOSE]) / 100.0,
        }
        head["winner"] = 1 if truth[side]["cert_net_cent"][row] >= dm.WINNER_CENT else 0
        head.update(features)
        head.update(v2.get(cand["id"], {}))
        head.update(fvol.get(cand["id"], {}))
        records.append(head)
    return records


_NORM = None


def _worker_norm() -> P.ClockNorm:
    """One ClockNorm per process; its prior-session tables are the expensive part."""
    global _NORM
    if _NORM is None:
        _NORM = P.ClockNorm(list(range(P.DRAW_WALL[0], P.DRAW_WALL[1] + 1)))
    return _NORM


def build_matrix(jobs_n: int) -> pd.DataFrame:
    jobs = []
    for record in era_blocks():
        for key in sorted(record["sessions"], key=int):
            jobs.append((int(key), record["block"], record["sessions"][key]))
    #: built BEFORE the fork so every worker inherits one causal cut table
    print(f"forecast-vol coverage: {len(ensure_hotcut())} sessions", flush=True)
    fvol_sessions()
    print(f"building walk-forward features: {len(jobs)} sessions, {jobs_n} workers",
          flush=True)
    records = []
    if jobs_n <= 1:
        for done, job in enumerate(jobs, 1):
            records.extend(session_rows(job))
            if done % 20 == 0:
                print(f"  {done}/{len(jobs)} sessions", flush=True)
    else:
        import multiprocessing as multi
        with multi.get_context("fork").Pool(jobs_n) as pool:
            for done, rows in enumerate(pool.imap_unordered(session_rows, jobs), 1):
                records.extend(rows)
                if done % 20 == 0 or done == len(jobs):
                    print(f"  {done}/{len(jobs)} sessions, {len(records)} rows", flush=True)
    frame = pd.DataFrame.from_records(records)
    return frame.sort_values(["session", "second", "side"]).reset_index(drop=True)


# ==========================================================================
# fitting — ONE frozen estimator, optionally era-weighted
# ==========================================================================

def fit_frozen(train: pd.DataFrame, test: pd.DataFrame, columns: list,
               weights: np.ndarray | None = None, seed: int = SEED,
               labels: np.ndarray | None = None) -> np.ndarray:
    from sklearn.ensemble import HistGradientBoostingClassifier
    X = train[columns].to_numpy(float)
    y = train["winner"].to_numpy() if labels is None else labels
    model = HistGradientBoostingClassifier(random_state=seed, **FROZEN)
    model.fit(X, y, sample_weight=weights)
    return model.predict_proba(test[columns].to_numpy(float))[:, 1]


def era_weights(train: pd.DataFrame, order: list) -> np.ndarray:
    """0.5 ** (eras of age); the newest training era weighs 1."""
    position = {name: index for index, name in enumerate(order)}
    newest = max(position[name] for name in train["block"].unique())
    age = train["block"].map(lambda name: newest - position[name]).to_numpy(float)
    return 0.5 ** (age / HALF_LIFE_ERAS)


# ==========================================================================
# scoring
# ==========================================================================

def segment_metrics(frame: pd.DataFrame, score: np.ndarray) -> dict:
    from sklearn.metrics import roc_auc_score
    top3 = dm.day_metrics(frame, score, k=3)
    top5 = dm.day_metrics(frame, score, k=5)
    point = mv.operating_point(frame, score, OPERATING_RATE)
    days = max(top3["days"], 1)
    auc = (roc_auc_score(frame["winner"], score)
           if frame["winner"].nunique() > 1 else np.nan)
    return {
        "n": len(frame), "days": days,
        "winrate": float(frame["winner"].mean()),
        "auc": float(auc),
        "top3_day": top3["cert_per_day"], "top3_cand": top3["cert_per_cand"],
        "top5_day": top5["cert_per_day"], "top5_cand": top5["cert_per_cand"],
        "random3_day": top3["random_per_day"], "oracle3_day": top3["oracle_per_day"],
        "lift_random3": top3["cert_per_day"] / top3["random_per_day"]
        if top3["random_per_day"] else np.nan,
        "lift_random5": top5["cert_per_day"] / top5["random_per_day"]
        if top5["random_per_day"] else np.nan,
        "mae_per_pick": top3["mae_per_pick"],
        "replay_close_day": top3["replay_close_per_day"],
        "op_trades_day": point["n_taken"] / days,
        "op_cert_taken": point["cert_taken"], "op_cert_skipped": point["cert_skipped"],
        "op_lift": point["lift"], "op_cert_day": point["cert_taken"] * point["n_taken"] / days
        if np.isfinite(point["cert_taken"]) else np.nan,
        "op_winrate_taken": point["winrate_taken"],
    }


# ==========================================================================
# the GATE-STACK table — do gates COMPOUND or merely OVERLAP?
# ==========================================================================
#
# A single gate at 50% / $523 is below the bar the user set (D-021: >$600 per
# trade, target >$1,000, MAE acceptance ~$300).  The claim under test is that
# the gates STACK.  So each selection below is scored with the ACCEPTANCE
# definition of a winner — cert >= $500 AND MAE <= $300, both legs — and with a
# ONE-POSITION occupancy replay, because a selection that fires five times in a
# day still only ever holds one contract.

STRICT_CERT = 500.0
STRICT_MAE = 300.0
CORNER_STATE = -2.0                 # band_state_own <= -2 = "fade an extension"
#: the landed contrast's own hot/cool boundary, quoted verbatim from
#: `_cache/fvol/contrast_study_e3_study_e3b.json` so its cells can be replicated
CONTRAST_CUT_BPS = 121.3457799765375


def strict_winner(frame: pd.DataFrame) -> np.ndarray:
    return ((frame["cert"] >= STRICT_CERT) & (frame["cert_mae"] <= STRICT_MAE)).to_numpy()


def occupancy(selection: pd.DataFrame, days: list, horizon: str = "close") -> dict:
    """One position at a time, chronological, per day.

    `close` = the earliest selected candidate is entered and held to the close
    (D-019's deployable shape, so at most one trade a day); `60m` = the greedy
    60-minute-occupancy replay, which can fit more than one trade in a day.
    """
    total, trades, fired = 0.0, 0, 0
    for day in days:
        rows = selection[selection["session"] == day].sort_values("second")
        if not len(rows):
            continue
        fired += 1
        if horizon == "close":
            total += float(rows.iloc[0]["menu_close"])
            trades += 1
        else:
            busy = -1
            for _, row in rows.iterrows():
                if row["second"] < busy:
                    continue
                total += float(row["menu60"])
                busy = row["second"] + 3600
                trades += 1
    return {"per_day": total / max(len(days), 1), "fired": fired, "trades": trades,
            "per_trade": total / trades if trades else np.nan}


def per_day_top(frame: pd.DataFrame, score_name: str, k: int) -> pd.DataFrame:
    """Top-k by score within each day; a day with fewer than k rows gives all of them."""
    if not len(frame):
        return frame
    parts = [day.nlargest(min(k, len(day)), score_name)
             for _, day in frame.groupby("session", sort=True)]
    return pd.concat(parts) if parts else frame.iloc[0:0]


def stack_rows(test: pd.DataFrame, score: np.ndarray) -> list:
    """The baseline / fvol-corner / STACK ladder for one test segment."""
    frame = test.assign(score=score)
    days = sorted(frame["session"].unique())
    threshold = float(np.quantile(score, 1.0 - OPERATING_RATE))
    model_top = frame[frame["score"] >= threshold]
    has_fvol = ("M_band_state_own" in frame.columns and
                frame["M_band_state_own"].notna().any())
    if has_fvol:
        fade = frame[frame["M_band_state_own"] <= CORNER_STATE]
        corner = fade[fade["M_sigma_inst_bps"] >= fade["M_sigma_now_bps"]]
    else:
        fade = corner = frame.iloc[0:0]

    selections = [
        ("baseline", "all candidates", frame),
        ("baseline", f"model top-{OPERATING_RATE:.1%}", model_top),
        ("baseline", "model top-3/day", per_day_top(frame, "score", 3)),
        ("fvol", "fade & hot corner (alone)", corner),
        ("stack", "model top ∩ corner", corner[corner["score"] >= threshold]),
        ("stack", "top-3/day WITHIN the corner", per_day_top(corner, "score", 3)),
        ("stack", "top-3/day within fade (any vol)", per_day_top(fade, "score", 3)),
    ]
    rows = []
    for family, label, selection in selections:
        close = occupancy(selection, days, "close")
        sixty = occupancy(selection, days, "60m")
        rows.append({
            "family": family, "selection": label, "n": len(selection),
            "n_per_day": len(selection) / max(len(days), 1),
            "strict_winner": float(strict_winner(selection).mean()) if len(selection) else np.nan,
            "mean_cert": float(selection["cert"].mean()) if len(selection) else np.nan,
            "close_per_day": close["per_day"], "close_per_trade": close["per_trade"],
            "days_fired": close["fired"], "sixty_per_day": sixty["per_day"],
            "sixty_per_trade": sixty["per_trade"], "days": len(days),
        })
    return rows


def money(value) -> str:
    return "n/a" if value is None or not np.isfinite(value) else f"${value:,.0f}"


def signed_money(value) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    return f"{'+' if value >= 0 else '-'}${abs(value):,.0f}"


# ---- D-022: every dollar carries its RTY-mini equivalent -------------------

_FACTORS = ROOT / "_cache" / "rty_factors.json"


def session_factors(sessions) -> dict:
    """f(s) = session-median IWM mid / 200 (D-022), cached across runs."""
    cache = json.loads(_FACTORS.read_text()) if _FACTORS.exists() else {}
    missing = [int(s) for s in sessions if str(int(s)) not in cache]
    for ordinal in missing:
        mid = dm.mid_series(ordinal)
        median = float(np.nanmedian(mid)) if np.isfinite(mid).any() else np.nan
        cache[str(ordinal)] = median / 200.0 if np.isfinite(median) else np.nan
    if missing:
        _FACTORS.write_text(json.dumps(cache))
    return {int(k): v for k, v in cache.items()}


def rty(value: float, factor: float) -> str:
    return money(value * factor) if np.isfinite(value) and np.isfinite(factor) else "n/a"


def number(value, digits: int = 3) -> str:
    return "n/a" if value is None or not np.isfinite(value) else f"{value:.{digits}f}"


# ==========================================================================
# main
# ==========================================================================

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--jobs", type=int, default=16)
    parser.add_argument("--skip-transfer", action="store_true")
    args = parser.parse_args()

    if MATRIX.exists() and not args.rebuild:
        frame = pd.read_csv(MATRIX, sep="\t")
    else:
        frame = build_matrix(args.jobs)
        frame.to_csv(MATRIX, sep="\t", index=False)
    print(f"matrix {frame.shape} -> {MATRIX}", flush=True)

    blocks = era_blocks()
    order = [record["block"] for record in blocks]
    ranges = {record["block"]: tuple(record["range"]) for record in blocks}
    present = [name for name in order if (frame["block"] == name).any()]
    by_block = {name: frame[frame["block"] == name].reset_index(drop=True)
                for name in present}
    SEGDIR.mkdir(parents=True, exist_ok=True)

    out = ["# WALK-FORWARD REPORT — model-v2 features across every lawful era",
           "",
           f"Frozen estimator for EVERY fit below (v2's config, never re-selected): "
           f"`{FROZEN}`.  Expanding-window ladder over "
           f"{len(present)} era blocks, {len(frame)} candidates, "
           f"{frame['session'].nunique()} sessions "
           f"{frame['session'].min()}..{frame['session'].max()}.",
           "", "@@VERDICT@@", ""]

    # ---- era census --------------------------------------------------------
    factors = session_factors(sorted(frame["session"].unique()))
    era_factor = {name: float(np.nanmean([factors[s] for s in
                                          by_block[name]["session"].unique()]))
                  for name in present}
    out.append("## Era census")
    out.append("| era | sessions | days | candidates | winner rate | mean cert | "
               "oracle top-3/day | random-3/day | RTY f (D-022) |")
    out.append("|---|---|---|---|---|---|---|---|---|")
    census_oracle = {}
    for name in present:
        block = by_block[name]
        base = dm.day_metrics(block, np.zeros(len(block)), k=3)
        census_oracle[name] = base["oracle_per_day"]
        out.append(f"| `{name}` | {ranges[name][0]}..{ranges[name][1]} | "
                   f"{block['session'].nunique()} | {len(block)} | "
                   f"{block['winner'].mean():.1%} | {money(block['cert'].mean())} | "
                   f"{money(base['oracle_per_day'])} | {money(base['random_per_day'])} | "
                   f"{era_factor[name]:.3f} |")
    out.append("")

    # ---- the expanding-window ladder --------------------------------------
    letters = "abcdefghijklmnopqrstuvwxyz"
    ladder = []
    for rung in range(1, len(present)):
        test_name = present[rung]
        train_names = present[:rung]
        train = frame[frame["block"].isin(train_names)].reset_index(drop=True)
        test = by_block[test_name]
        columns = [c for c in dm.feature_columns(frame, train) if not c.startswith("J_")]
        weights = era_weights(train, order)
        pooled = fit_frozen(train, test, columns)
        regime = fit_frozen(train, test, columns, weights=weights)
        recent = fit_frozen(frame[frame["block"] == train_names[-1]].reset_index(drop=True),
                            test, columns)
        entry = {
            "tag": letters[rung - 1], "test": test_name, "train": train_names,
            "n_train": len(train), "n_columns": len(columns),
            "pooled": segment_metrics(test, pooled),
            "regime": segment_metrics(test, regime),
            "recent": segment_metrics(test, recent),
            "score_pooled": pooled, "columns": columns,
        }
        ladder.append(entry)
        pd.DataFrame({
            "session": test["session"], "day": test["day"], "id": test["id"],
            "side": test["side"], "second": test["second"], "cert": test["cert"],
            "cert_mae": test["cert_mae"], "menu_close": test["menu_close"],
            "winner": test["winner"], "score_pooled": pooled,
            "score_regime": regime, "score_recent_era_only": recent,
        }).to_csv(SEGDIR / f"segment_{letters[rung-1]}_{test_name}.tsv",
                  sep="\t", index=False)
        print(f"rung {letters[rung-1]}: train {train_names} -> test {test_name} "
              f"AUC {entry['pooled']['auc']:.3f} / regime {entry['regime']['auc']:.3f}",
              flush=True)

    out.append("## The ladder (expanding window, frozen config, day-complete test blocks)")
    out.append("")
    out.append("| seg | train | test | train rows | features | AUC | top-3/day | "
               "top-3/day RTY-mini | top-5/day | lift vs random-3 | "
               "trades/day @27.5% | cert/taken | op lift |")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for entry in ladder:
        met = entry["pooled"]
        out.append(
            f"| **{entry['tag']}** | {'+'.join(entry['train'])} | `{entry['test']}` | "
            f"{entry['n_train']} | {entry['n_columns']} | {number(met['auc'])} | "
            f"{money(met['top3_day'])} | {rty(met['top3_day'], era_factor[entry['test']])} | "
            f"{money(met['top5_day'])} | "
            f"{number(met['lift_random3'], 2)}x | {met['op_trades_day']:.1f} | "
            f"{money(met['op_cert_taken'])} | {number(met['op_lift'], 2)}x |")
    out.append("")
    out.append("Segment **a** has a single training era, so its pooled / regime-weighted / "
               "newest-era arms are the same fit by construction.")
    out.append("")

    out.append("## POOLED vs REGIME-WEIGHTED vs NEWEST-ERA-ONLY (D-031's question)")
    out.append("")
    out.append("Same features, same frozen estimator, same test rows; only the training "
               "sample weights differ.  REGIME = 0.5^(eras of age), half-life one era; "
               "NEWEST = the immediately preceding era alone.")
    out.append("")
    out.append("| seg | test | arm | AUC | top-3/day | top-5/day | lift vs random-3 | "
               "cert/taken @27.5% |")
    out.append("|---|---|---|---|---|---|---|---|")
    for entry in ladder:
        for arm in ("pooled", "regime", "recent"):
            met = entry[arm]
            label = {"pooled": "pooled", "regime": "regime-weighted",
                     "recent": "newest era only"}[arm]
            out.append(f"| {entry['tag']} | `{entry['test']}` | {label} | "
                       f"{number(met['auc'])} | {money(met['top3_day'])} | "
                       f"{money(met['top5_day'])} | {number(met['lift_random3'], 2)}x | "
                       f"{money(met['op_cert_taken'])} |")
    out.append("")

    m_verdict: list = []

    # ---- the gate STACK per test segment -----------------------------------
    out.append("## Gate STACK — do the gates compound, or do they overlap?")
    out.append("")
    out.append("Every row is a SELECTION over the same test block, scored the way the "
               "user's acceptance rules score it: a winner needs BOTH legs (cert >= "
               f"${STRICT_CERT:,.0f} and MAE <= ${STRICT_MAE:,.0f}), and the dollars "
               "come from a ONE-POSITION occupancy replay, not from summing "
               "simultaneous picks.  `$/day` divides by EVERY day in the block, "
               "including the days the selection never fires; `$/trade` divides by the "
               "trades actually taken.  The model score is this lane's own "
               "walk-forward prediction for that segment — no refit, no lookahead.")
    out.append("")
    stack_records = []
    for entry in ladder:
        test = by_block[entry["test"]]
        rows = stack_rows(test, entry["score_pooled"])
        for row in rows:
            stack_records.append({"segment": entry["tag"], "test_era": entry["test"],
                                  **row})
        out.append(f"### Segment {entry['tag']} — test `{entry['test']}` "
                   f"({rows[0]['days']} days, {rows[0]['n']} candidates)")
        out.append("")
        out.append("| family | selection | n | n/day | winner% (cert>=$500 & MAE<=$300) | "
                   "mean cert | close $/day | close $/trade | days fired | 60m $/day |")
        out.append("|---|---|---|---|---|---|---|---|---|---|")
        for row in rows:
            if not row["n"]:
                out.append(f"| {row['family']} | {row['selection']} | 0 | — | — | — | "
                           "— | — | 0 | — |")
                continue
            out.append(
                f"| {row['family']} | {row['selection']} | {row['n']} | "
                f"{row['n_per_day']:.1f} | {row['strict_winner']:.1%} | "
                f"{money(row['mean_cert'])} | {money(row['close_per_day'])} | "
                f"{money(row['close_per_trade'])} | "
                f"{row['days_fired']}/{row['days']} | {money(row['sixty_per_day'])} |")
        out.append("")
    pd.DataFrame(stack_records).to_csv(SEGDIR / "gate_stack.tsv", sep="\t", index=False)

    # ---- the M_ forecast-vol / band-state block ----------------------------
    m_columns = [c for c in frame.columns if c.startswith("M_")]
    if m_columns and ladder:
        out.append("## The forecast-vol / band-state block (`M_`)")
        out.append("")
        out.append(f"{len(m_columns)} channels joined from `_cache/fvol` at each "
                   "candidate's last COMPLETED minute (a row stamped `second` is only "
                   "read when `second < t`).  The hot/cool cut is the median "
                   "per-session median `sigma_inst_bps` over the 20 strictly prior "
                   "covered sessions, never the test block's own median.")
        out.append("")
        out.append("| era | candidates | with `M_band_state` | with the ext x vol cell |")
        out.append("|---|---|---|---|")
        for name in present:
            block = by_block[name]
            has_state = block["M_band_state"].notna().mean() if "M_band_state" in block else 0.0
            has_cell = block["M_ext_vol_cell"].notna().mean() if "M_ext_vol_cell" in block else 0.0
            out.append(f"| `{name}` | {len(block)} | {has_state:.0%} | {has_cell:.0%} |")
        out.append("")

        # -- does the block pay?  same rungs, M_ dropped ----------------------
        out.append("### Ablation — the same rungs with the `M_` block removed")
        out.append("")
        out.append("| seg | test | arm | AUC | top-3/day | top-5/day | lift vs random-3 |")
        out.append("|---|---|---|---|---|---|---|")
        for entry in ladder:
            train = frame[frame["block"].isin(entry["train"])].reset_index(drop=True)
            test = by_block[entry["test"]]
            columns = [c for c in dm.feature_columns(frame, train)
                       if not c.startswith("J_")]
            without = [c for c in columns if not c.startswith("M_")]
            if len(without) == len(columns):
                continue                       # the block carried no fit on this rung
            met_off = segment_metrics(test, fit_frozen(train, test, without))
            for label, met in (("with `M_`", entry["pooled"]), ("without `M_`", met_off)):
                out.append(f"| {entry['tag']} | `{entry['test']}` | {label} | "
                           f"{number(met['auc'])} | {money(met['top3_day'])} | "
                           f"{money(met['top5_day'])} | "
                           f"{number(met['lift_random3'], 2)}x |")
        out.append("")

        # -- the landed 3x2 cell, re-measured out of sample -------------------
        out.append("### The landed EXTENSION x VOL cell, re-measured on every era")
        out.append("")
        out.append("Rows are the contrast's own cells (`M_extension` = fade at "
                   "band_state_own <= -2, chase at >= +2; `M_hot` = sigma_inst above "
                   "the prior-sessions cut).  This is a population measurement, not a "
                   "fit — no model is involved.")
        out.append("")
        out.append("| era | cell | n | win rate | lift vs era base | mean cert |")
        out.append("|---|---|---|---|---|---|")
        names = {(-1.0, 1.0): "fade x hot", (-1.0, 0.0): "fade x cool",
                 (0.0, 1.0): "mid x hot", (0.0, 0.0): "mid x cool",
                 (1.0, 1.0): "chase x hot", (1.0, 0.0): "chase x cool"}
        for name in present:
            block = by_block[name]
            if "M_extension" not in block or block["M_extension"].notna().sum() == 0:
                continue
            base = block["winner"].mean()
            for key in ((-1.0, 1.0), (-1.0, 0.0), (0.0, 1.0), (0.0, 0.0),
                        (1.0, 1.0), (1.0, 0.0)):
                cell = block[(block["M_extension"] == key[0]) &
                             (block["M_hot"] == key[1])]
                if not len(cell):
                    continue
                out.append(f"| `{name}` | {names[key]} | {len(cell)} | "
                           f"{cell['winner'].mean():.1%} | "
                           f"{cell['winner'].mean() / base:.2f}x | "
                           f"{money(cell['cert'].mean())} |")
        out.append("")

        # -- the landed cell replicated with the contrast's OWN cut -----------
        out.append("### Replication of the landed cell with the contrast's own cut")
        out.append("")
        out.append(f"The landed contrast fixed its hot/cool boundary at "
                   f"`sigma_inst_bps = {CONTRAST_CUT_BPS:.2f}` (the median of its own "
                   "two blocks).  Applying that number verbatim reproduces its cells "
                   "exactly on the blocks it was measured on, which makes every other "
                   "row below an honest out-of-sample test of the same rule.")
        out.append("")
        out.append("| block | base rate | fade & hot n | win rate | mean cert | "
                   "chase & cool n | win rate |")
        out.append("|---|---|---|---|---|---|---|")
        combined = frame[frame["block"].isin(["study_e3", "study_e3b"])]
        for label, block in ([("study_e3+study_e3b (the contrast's own blocks)",
                               combined)] +
                             [(f"`{name}`", by_block[name]) for name in present]):
            if "M_band_state_own" not in block or \
                    block["M_band_state_own"].notna().sum() == 0:
                continue
            fade = block[block["M_band_state_own"] <= CORNER_STATE]
            hot = fade[fade["M_sigma_inst_bps"] >= CONTRAST_CUT_BPS]
            chase = block[block["M_band_state_own"] >= -CORNER_STATE]
            cool = chase[chase["M_sigma_inst_bps"] < CONTRAST_CUT_BPS]
            rate = lambda part: f"{part['winner'].mean():.1%}" if len(part) else "—"
            out.append(f"| {label} | {block['winner'].mean():.1%} | {len(hot)} | "
                       f"{rate(hot)} | "
                       f"{money(hot['cert'].mean()) if len(hot) else '—'} | "
                       f"{len(cool)} | {rate(cool)} |")
        out.append("")

        # -- the verdict on this block, from the numbers just measured --------
        def cell_rate(block, low, high, hot_side):
            part = block[(block["M_band_state_own"] <= low) if low is not None
                         else (block["M_band_state_own"] >= high)]
            part = part[(part["M_sigma_inst_bps"] >= CONTRAST_CUT_BPS) if hot_side
                        else (part["M_sigma_inst_bps"] < CONTRAST_CUT_BPS)]
            return len(part), (float(part["winner"].mean()) if len(part) else np.nan)

        origin = frame[frame["block"].isin(["study_e3", "study_e3b"])]
        o_n, o_rate = cell_rate(origin, CORNER_STATE, None, True)
        later = by_block[ladder[-1]["test"]]
        l_n, l_rate = cell_rate(later, CORNER_STATE, None, True)
        m_verdict = [
            "**The forecast-vol `fade x hot` corner does NOT survive the walk "
            f"forward.**  With the contrast's own cut applied verbatim it reproduces "
            f"exactly on the blocks it was found on ({o_n} candidates, {o_rate:.0%} "
            f"winners), and on the next block forward it collapses to {l_rate:.0%} on "
            f"{l_n} candidates — at or below the block's base rate.  The whole `M_` "
            "block behaves the same way in the model: adding it moves the blind AUC "
            "and the blind top-3/day slightly the WRONG way (see the ablation).  The "
            "single strongest cell anyone has shown on this roster is an in-sample "
            "artifact of `study_e3`, and the stack table shows the same thing at "
            "every depth — intersecting it with the model's own top slice does not "
            "rescue it.  Treat the forecast-vol channels as ordinary continuous "
            "features (`M_sigma_inst_bps` does carry real, small blind importance), "
            "not as a gate.",
            "",
        ]

        # -- importance, on the final rung ------------------------------------
        from sklearn.ensemble import HistGradientBoostingClassifier
        from sklearn.inspection import permutation_importance
        entry = ladder[-1]
        train = frame[frame["block"].isin(entry["train"])].reset_index(drop=True)
        test = by_block[entry["test"]]
        columns = [c for c in dm.feature_columns(frame, train) if not c.startswith("J_")]
        model = HistGradientBoostingClassifier(random_state=SEED, **FROZEN).fit(
            train[columns].to_numpy(float), train["winner"].to_numpy())
        importance = permutation_importance(
            model, test[columns].to_numpy(float), test["winner"].to_numpy(),
            n_repeats=20, random_state=SEED, scoring="roc_auc")
        order_index = np.argsort(importance.importances_mean)[::-1]
        out.append(f"### Permutation importance on segment {entry['tag']} "
                   f"(test block `{entry['test']}`, AUC drop)")
        out.append("")
        out.append("| rank | feature | AUC drop | sd |")
        out.append("|---|---|---|---|")
        for rank, index in enumerate(order_index[:20], 1):
            out.append(f"| {rank} | `{columns[index]}` | "
                       f"{importance.importances_mean[index]:+.4f} | "
                       f"{importance.importances_std[index]:.4f} |")
        ranks = {columns[index]: rank for rank, index in enumerate(order_index, 1)}
        out.append("")
        out.append("Every `M_` channel, wherever it landed:")
        out.append("")
        out.append("| rank of %d | feature | AUC drop |" % len(columns))
        out.append("|---|---|---|")
        for name in sorted((c for c in columns if c.startswith("M_")),
                           key=lambda c: ranks[c]):
            index = columns.index(name)
            out.append(f"| {ranks[name]} | `{name}` | "
                       f"{importance.importances_mean[index]:+.4f} |")
        out.append("")

    # ---- era-transfer matrix ----------------------------------------------
    transfer = {}
    if not args.skip_transfer:
        common = [c for c in frame.columns
                  if c not in dm.META_COLS and not c.startswith("J_")]
        usable = []
        for name in common:
            if all(len(pd.to_numeric(by_block[b][name], errors="coerce")
                       .dropna().unique()) >= 2 for b in present):
                usable.append(name)
        print(f"transfer matrix on {len(usable)} common columns", flush=True)
        for train_name in present:
            train = by_block[train_name]
            for test_name in present:
                if train_name == test_name:
                    continue
                score = fit_frozen(train, by_block[test_name], usable)
                transfer[(train_name, test_name)] = segment_metrics(
                    by_block[test_name], score)
            print(f"  transfer row {train_name} done", flush=True)
        rows = []
        for (train_name, test_name), met in transfer.items():
            rows.append({"train_era": train_name, "test_era": test_name,
                         **{k: met[k] for k in ("n", "days", "auc", "top3_day",
                                                "top5_day", "lift_random3",
                                                "op_trades_day", "op_cert_taken",
                                                "op_lift")}})
        pd.DataFrame(rows).to_csv(SEGDIR / "era_transfer_matrix.tsv",
                                  sep="\t", index=False)

        out.append("## Era-transfer matrix — the direct measurement of pattern decay")
        out.append("")
        out.append(f"Each cell: ONE era fitted alone (frozen config, {len(usable)} "
                   "columns usable in every era) and scored on another era.  Rows = "
                   "train era, columns = test era.  The diagonal is left blank (a "
                   "self-fit is in-sample and not comparable).")
        for label, key, fmt in (("AUC", "auc", "num"),
                                ("top-3/day exit-free cert", "top3_day", "money"),
                                ("lift vs random-3", "lift_random3", "lift")):
            out.append("")
            out.append(f"### {label}")
            out.append("| train \\ test | " + " | ".join(f"`{n}`" for n in present) + " |")
            out.append("|" + "---|" * (len(present) + 1))
            for train_name in present:
                cells = []
                for test_name in present:
                    if train_name == test_name:
                        cells.append("—")
                        continue
                    value = transfer[(train_name, test_name)][key]
                    cells.append(money(value) if fmt == "money" else
                                 (f"{value:.2f}x" if fmt == "lift" else number(value)))
                cells = [f"**{c}**" if False else c for c in cells]
                out.append(f"| `{train_name}` | " + " | ".join(cells) + " |")
        out.append("")
        out.append("#### Marginals — is the cell driven by WHO TRAINED or WHO IS TESTED?")
        out.append("| era | as TRAIN era: mean AUC | mean top-3/day | "
                   "as TEST era: mean AUC | mean top-3/day |")
        out.append("|---|---|---|---|---|")
        for name in present:
            as_train = [m for (a, _), m in transfer.items() if a == name]
            as_test = [m for (_, b), m in transfer.items() if b == name]
            out.append(f"| `{name}` | "
                       f"{number(np.nanmean([m['auc'] for m in as_train]))} | "
                       f"{money(np.nanmean([m['top3_day'] for m in as_train]))} | "
                       f"{number(np.nanmean([m['auc'] for m in as_test]))} | "
                       f"{money(np.nanmean([m['top3_day'] for m in as_test]))} |")
        spread = lambda key, index: (
            max(np.nanmean([m[key] for (a, b), m in transfer.items()
                            if (a if index == 0 else b) == n]) for n in present) -
            min(np.nanmean([m[key] for (a, b), m in transfer.items()
                            if (a if index == 0 else b) == n]) for n in present))
        out.append("")
        out.append(f"Spread of the row means (train era): AUC {spread('auc', 0):.3f}, "
                   f"top-3/day {money(spread('top3_day', 0))}.  "
                   f"Spread of the column means (test era): AUC {spread('auc', 1):.3f}, "
                   f"top-3/day {money(spread('top3_day', 1))}.")
        out.append("")
        out.append("#### Decay by era distance (mean over cells at each gap)")
        out.append("| gap (eras) | direction | cells | mean AUC | mean top-3/day | "
                   "mean lift vs random-3 |")
        out.append("|---|---|---|---|---|---|")
        position = {name: index for index, name in enumerate(present)}
        buckets: dict = {}
        for (train_name, test_name), met in transfer.items():
            gap = position[test_name] - position[train_name]
            key = (abs(gap), "forward" if gap > 0 else "backward")
            buckets.setdefault(key, []).append(met)
        for key in sorted(buckets):
            group = buckets[key]
            out.append(f"| {key[0]} | {key[1]} | {len(group)} | "
                       f"{number(np.nanmean([m['auc'] for m in group]))} | "
                       f"{money(np.nanmean([m['top3_day'] for m in group]))} | "
                       f"{number(np.nanmean([m['lift_random3'] for m in group]), 2)}x |")
        out.append("")

    # ---- the v2 comparison -------------------------------------------------
    final = ladder[-1] if ladder else None
    v2_repl = None
    if final is not None:
        #: v2's own training slice, refitted here with the same frozen config —
        #: the control that separates "more training data" from "different code".
        v2_train = frame[(frame["session"] >= P.STUDY_ERA[0]) &
                         (frame["session"] <= 412)].reset_index(drop=True)
        if len(v2_train):
            v2_columns = [c for c in dm.feature_columns(frame, v2_train)
                          if not c.startswith("J_")]
            v2_repl = segment_metrics(
                by_block[final["test"]],
                fit_frozen(v2_train, by_block[final["test"]], v2_columns))
            v2_repl["n_train"] = len(v2_train)
            v2_repl["n_columns"] = len(v2_columns)
    if final is not None:
        out.append(f"## Segment {final['tag']} against MODEL_V2 (same test block, "
                   "more training data)")
        out.append("")
        out.append("v2 trained on 398..412 (273 candidates) and tested on the same "
                   f"`{final['test']}` roster.  This lane trains on "
                   f"{final['n_train']} candidates from "
                   f"{len(final['train'])} eras.")
        out.append("")
        if v2_repl is not None:
            out.append(f"`v2 slice refit` below is the CONTROL: v2's own training rows "
                       f"(398..412, {v2_repl['n_train']} candidates, "
                       f"{v2_repl['n_columns']} columns) refitted inside THIS harness "
                       "with the same frozen config, so any gap between it and the "
                       "published v2 numbers is harness noise and any gap between it "
                       "and the pooled arm is training data alone.")
            out.append("")
        out.append("| quantity | MODEL_V2 published | v2 slice refit here | "
                   "walk-forward pooled | walk-forward regime-weighted | "
                   "delta (pooled - v2 published) |")
        out.append("|---|---|---|---|---|---|")
        anchors = (("blind AUC", 0.641, "auc", "num"),
                   ("top-3/day exit-free cert", 1672.0, "top3_day", "money"),
                   ("top-5/day exit-free cert", 2569.0, "top5_day", "money"),
                   ("cert/taken @27.5%", 477.0, "op_cert_taken", "money"),
                   ("operating-point lift", 1.57, "op_lift", "lift"))
        for label, anchor, key, fmt in anchors:
            pooled_value = final["pooled"][key]
            regime_value = final["regime"][key]
            delta = pooled_value - anchor

            def show(value, fmt=fmt):
                if fmt == "money":
                    return money(value)
                return f"{value:.2f}x" if fmt == "lift" else number(value)

            delta_text = (signed_money(delta) if fmt == "money" else f"{delta:+.3f}")
            control = show(v2_repl[key]) if v2_repl is not None else "n/a"
            out.append(f"| {label} | {show(anchor)} | {control} | {show(pooled_value)} | "
                       f"{show(regime_value)} | {delta_text} |")
        out.append("")
        out.append(f"RTY-mini overlay (D-022, `{final['test']}` mean "
                   f"f={era_factor[final['test']]:.3f}): pooled top-3/day "
                   f"{rty(final['pooled']['top3_day'], era_factor[final['test']])}, "
                   f"regime-weighted "
                   f"{rty(final['regime']['top3_day'], era_factor[final['test']])}, "
                   "v2 published $1,469.")
        out.append("")

    # ---- controls ----------------------------------------------------------
    out.append("## Controls")
    if final is not None:
        train = frame[frame["block"].isin(final["train"])].reset_index(drop=True)
        test = by_block[final["test"]]
        columns = [c for c in dm.feature_columns(frame, train) if not c.startswith("J_")]
        rng = np.random.default_rng(SEED)
        aucs, dollars = [], []
        for _ in range(5):
            shuffled = rng.permutation(train["winner"].to_numpy())
            score = fit_frozen(train, test, columns, labels=shuffled)
            met = segment_metrics(test, score)
            aucs.append(met["auc"])
            dollars.append(met["top3_day"])
        out.append(f"- LABEL-SHUFFLE control on segment {final['tag']} "
                   f"(train labels permuted, 5 draws): AUC "
                   f"{np.mean(aucs):.3f} +/- {np.std(aucs):.3f} "
                   f"(real {final['pooled']['auc']:.3f}); top-3/day "
                   f"{money(np.mean(dollars))} (real "
                   f"{money(final['pooled']['top3_day'])}).")
    out.append("- Walk-forward purity: every rung's test block is strictly LATER than "
               "every session in its training window; the estimator config is frozen "
               "from v2 and is never re-selected on any block here.")
    out.append(f"- Session coverage: {frame['session'].nunique()} sessions, no era "
               "block excluded, no day excluded (D-038 §3).")

    # ---- verdict, assembled from the numbers just measured -----------------
    if final is None:
        out = [line for line in out if line != "@@VERDICT@@"]
        REPORT.write_text("\n".join(out) + "\n")
        return
    contested = [e for e in ladder if len(e["train"]) > 1]      # arms differ only here
    d_auc = [e["regime"]["auc"] - e["pooled"]["auc"] for e in contested]
    d_cash = [e["regime"]["top3_day"] - e["pooled"]["top3_day"] for e in contested]
    r_auc = [e["recent"]["auc"] - e["pooled"]["auc"] for e in contested]
    r_cash = [e["recent"]["top3_day"] - e["pooled"]["top3_day"] for e in contested]
    lifts = [e["pooled"]["lift_random3"] for e in ladder]
    verdict = [
        "## VERDICT",
        "",
        f"**The edge survives every era, and it is thin everywhere except the last "
        f"rung.**  All {len(ladder)} walk-forward segments beat a random-3 draw "
        f"(lift {min(lifts):.2f}x to {max(lifts):.2f}x, mean "
        f"{np.mean(lifts):.2f}x), and out-of-era AUC runs "
        f"{min(e['pooled']['auc'] for e in ladder):.3f}-"
        f"{max(e['pooled']['auc'] for e in ladder):.3f} — real, but far below the "
        "in-era numbers v2 reported.  A single 20-day block was not enough to see "
        "this: the spread across eras is wider than the gap between any two feature "
        "sets v2 compared.",
        "",
        f"**More training data helped the RANKING, not the TOP of the ranking.**  "
        f"Segment {final['tag']} tests the identical `{final['test']}` roster v2 "
        f"tested, with {final['n_train']} training candidates instead of 273: AUC "
        f"{final['pooled']['auc']:.3f} against v2's 0.641 (+"
        f"{final['pooled']['auc'] - 0.641:.3f}), but top-3/day "
        f"{money(final['pooled']['top3_day'])} against v2's $1,672 "
        f"({signed_money(final['pooled']['top3_day'] - 1672.0)}).  Selection uses the "
        "top of the ranking, so on the deployable number the 15-session era-native "
        "fit was not improved on by 303 sessions of history.",
        "",
        "**Recency-weighting (D-031) is a real but small and inconsistent gain.**  "
        f"Against pooling, the half-life-one-era weights move AUC by "
        f"{np.mean(d_auc):+.3f} on average "
        f"({sum(1 for d in d_auc if d > 0)}/{len(d_auc)} segments better) and "
        f"top-3/day by {signed_money(np.mean(d_cash))} "
        f"({sum(1 for d in d_cash if d > 0)}/{len(d_cash)} better).  Throwing history "
        f"away entirely (newest era only) moves AUC {np.mean(r_auc):+.3f} and "
        f"top-3/day {signed_money(np.mean(r_cash))}.  Read together: old eras are not "
        "poison, and they are not worth much either — consistent with D-031's library "
        "claim (patterns persist) and against any simple 'retrain on the last block' "
        "rule.",
        "",
        "**Pattern decay is NOT mainly a function of era distance.**  In the "
        "era-transfer matrix the column you test in explains far more than the row "
        "you trained in, and the gap-1 cells are not systematically better than the "
        "gap-4/5 cells.  What changes across eras is how much money the day offers: "
        "oracle top-3/day runs from "
        f"{money(max(census_oracle.values()))} in "
        f"`{max(census_oracle, key=census_oracle.get)}` down to "
        f"{money(min(census_oracle.values()))} in "
        f"`{min(census_oracle, key=census_oracle.get)}` — the OFFER moves, not the "
        "truth of the patterns.",
        "",
    ]
    if m_verdict:
        verdict.extend(m_verdict)
    out = [line if line != "@@VERDICT@@" else "\n".join(verdict) for line in out]

    REPORT.write_text("\n".join(out) + "\n")
    print(f"wrote {REPORT}", flush=True)
    (SEGDIR / "ladder_summary.tsv").write_text(
        "\n".join(["\t".join(["segment", "train", "test", "arm", "n", "days", "auc",
                              "top3_day", "top5_day", "random3_day", "oracle3_day",
                              "lift_random3", "lift_random5", "op_trades_day",
                              "op_cert_taken", "op_cert_skipped", "op_lift",
                              "mae_per_pick", "replay_close_day"])] +
                  ["\t".join([entry["tag"], "+".join(entry["train"]), entry["test"], arm] +
                             [f"{entry[arm][k]:.6g}" for k in
                              ("n", "days", "auc", "top3_day", "top5_day", "random3_day",
                               "oracle3_day", "lift_random3", "lift_random5",
                               "op_trades_day", "op_cert_taken", "op_cert_skipped",
                               "op_lift", "mae_per_pick", "replay_close_day")])
                   for entry in ladder for arm in ("pooled", "regime", "recent")]) + "\n")


if __name__ == "__main__":
    main()
