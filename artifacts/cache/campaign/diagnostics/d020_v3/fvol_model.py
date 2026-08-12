"""fvol_model.py — FORWARD-VOL REVIVAL, step 2: the walk-forward DAILY MODEL.

Two heads, both forecast at the OPEN of session s from STRICTLY PRIOR inputs:

    rng_bps  the session's RTH high-low range  -> the IMPLIED MOVE OF THE DAY
    rv_bps   the session's realised volatility -> SIGMA_DAY

FEATURES (every one lagged; nothing from session s except the calendar):
    HAR-RV terms   log of the day / week (5) / month (22) means of BOTH realised
                   series, taken over sessions strictly before s
    rv_prior_rate  packlib's own prior realised-variance rate (already prior-only)
    atr14_bps      packlib session_meta (a 14-session prior statistic)
    PROXY_VOL      session s-1's closing W2.1 straddle PROXY_VOL, bid AND ask
                   planes plus their mean; TYPED-ABSENT before s209 -> the value
                   is train-median-filled and a presence indicator carries the
                   absence (never a silent zero)
    RVX            session s-1's RVX close and its 1-day and 5-day log changes
    prior returns  |log return| of the prior close-to-close, and the prior day's
                   own high-low-over-close bar range
    calendar       day-of-week dummies + log(session_seconds / 23400) so early
                   closes are scaled rather than mis-compared

FIT.  Expanding window, refit every REFIT_EVERY sessions, minimum MIN_TRAIN rows;
alpha picked by a purely in-train TimeSeriesSplit.  A row is only ever predicted
by a model whose training rows all lie strictly before it.  Range pinned 125..447.

BASELINES (both DEBIASED on the training window, i.e. given their best shot):
    persistence  yesterday's realised value    + train-fitted log offset
    atr14        prior-day ATR14               + train-fitted log offset
Admission (D-017) requires beating BOTH, per era, on both loss and rank.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import TimeSeriesSplit
from scipy import optimize, stats

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import packlib as P                                        # noqa: E402

FVOL = P.CACHE / "fvol"
TABLE = FVOL / "daily_table.tsv"
PRIOR = FVOL / "prior_daily.tsv"

HEADS = ("rng_bps", "rv_bps")
#: MIN_TRAIN and the feature set are the only two development knobs.  They are
#: chosen on the EARLIEST out-of-sample era (E2) alone -- the DEV era -- and the
#: later eras (E3 / STUDY / BLIND) are reported untouched by that choice.  With
#: ~40 columns a 60-row training window is under-determined, which is what the
#: first pass demonstrated; the selected value is recorded in model_report.json.
#: SELECTED ON E2 ALONE (60/90/120/150/180 tried): 120 is the best DEV-era value
#: for both heads and both arms.  E1 therefore carries NO out-of-sample rows --
#: with 323 in-scope sessions the first era is unavoidably the warm-up, and that
#: is reported as an absence rather than papered over.
DEV_ERA = "E2_2023H1"
MIN_TRAIN = 120
REFIT_EVERY = 21
ALPHAS = (0.3, 1.0, 3.0, 10.0, 30.0, 100.0, 300.0, 1000.0)
WARMUP = 66                     # the longest HAR window

#: Reporting eras.  D-037's three walk-forward eras, with the gate_select era cut
#: at the D-034 study/blind boundary so the emitted context can be read per block.
ERAS = (("E1_2022H2", 125, 229), ("E2_2023H1", 230, 330), ("E3_2023Q3", 331, 397),
        ("STUDY_398_427", 398, 427), ("BLIND_428_447", 428, 447))


def read_tsv(path: pathlib.Path) -> dict:
    lines = path.read_text().splitlines()
    names = lines[0].split("\t")
    cols = {name: [] for name in names}
    for line in lines[1:]:
        for name, value in zip(names, line.split("\t")):
            cols[name].append(value)
    out = {}
    for name, values in cols.items():
        out[name] = np.array(values) if name == "day" else np.array(values, dtype=np.float64)
    out["session"] = out["session"].astype(int)
    return out


def read_table() -> dict:
    """The scored table (125..447) with the warm-up daily series joined on.

    The HAR terms are taken from the ENGINE'S OWN daily summaries, which exist
    from ordinal 0; joining them lets s125 itself carry a full 66-session HAR
    history instead of the model only becoming usable a quarter into the scope.
    The TARGETS stay the 1s-grid quantities of `daily_table.tsv` -- only the
    lagged inputs come from the warm-up series.
    """
    table = read_tsv(TABLE)
    prior = read_tsv(PRIOR)
    #: `warm` is indexed by ordinal so the HAR windows can walk BELOW 125.
    warm = {int(s): i for i, s in enumerate(prior["session"])}
    table["_warm"] = prior
    table["_warm_index"] = warm
    return table


def build_design(table: dict) -> tuple:
    """`(X, names, present, targets)` — one row per session, all inputs lagged."""
    n = len(table["session"])
    sessions = table["session"]
    warm, warm_index = table["_warm"], table["_warm_index"]
    columns, names = [], []

    def warm_window(series: str, window: int, skip: int = 1) -> np.ndarray:
        """mean of the `window` warm-up sessions ending `skip` sessions before s."""
        values = warm[series]
        out = np.full(n, np.nan)
        for i, ordinal in enumerate(sessions):
            end = warm_index.get(int(ordinal))
            if end is None or end - skip + 1 - window < 0:
                continue
            chunk = values[end - skip + 1 - window:end - skip + 1]
            if chunk.size == window and np.all(np.isfinite(chunk)):
                out[i] = float(np.mean(chunk))
        return out

    def warm_lag(series: str, k: int) -> np.ndarray:
        values = warm[series]
        out = np.full(n, np.nan)
        for i, ordinal in enumerate(sessions):
            end = warm_index.get(int(ordinal))
            if end is not None and end - k >= 0:
                out[i] = values[end - k]
        return out

    def add(name: str, values: np.ndarray) -> None:
        names.append(name)
        columns.append(np.asarray(values, dtype=np.float64))

    def lag(series: np.ndarray, k: int) -> np.ndarray:
        out = np.full(n, np.nan)
        if k < n:
            out[k:] = series[:n - k]
        return out

    for label, series in (("rng", "w_rng_bps"), ("rv", "w_rv_bps")):
        add(f"har_{label}_d", np.log(np.clip(warm_lag(series, 1), 1e-6, None)))
        for window in (5, 22, 66):
            add(f"har_{label}_{window}", np.log(np.clip(warm_window(series, window), 1e-6, None)))

    add("log_rv_prior_rate", np.log(np.clip(table["rv_prior_rate"], 1e-6, None)))
    add("log_atr14", np.log(np.clip(table["atr14_bps"], 1e-6, None)))
    add("log_atr14_warm", np.log(np.clip(warm_lag("w_atr14_bps", 0), 1e-6, None)))

    pv_bid = lag(table["proxy_vol_close_bid"], 1)
    pv_ask = lag(table["proxy_vol_close_ask"], 1)
    pv_mid = 0.5 * (pv_bid + pv_ask)
    pv_present = np.isfinite(pv_mid).astype(np.float64)
    add("log_pv_bid", np.log(np.clip(pv_bid, 1e-6, None)))
    add("log_pv_ask", np.log(np.clip(pv_ask, 1e-6, None)))
    add("log_pv_mid", np.log(np.clip(pv_mid, 1e-6, None)))
    add("pv_spread_rel", np.where(pv_mid > 0, (pv_ask - pv_bid) / pv_mid, np.nan))
    add("pv_present", pv_present)

    logs = {}
    for name in ("rvx", "vix", "vxd"):
        series = table[f"{name}_close"]
        one, two, six = lag(series, 1), lag(series, 2), lag(series, 6)
        logs[name] = np.log(np.clip(one, 1e-6, None))
        add(f"log_{name}", logs[name])
        add(f"d_log_{name}_1", logs[name] - np.log(np.clip(two, 1e-6, None)))
        add(f"d_log_{name}_5", logs[name] - np.log(np.clip(six, 1e-6, None)))
    #: the small-cap vol premium: how much more the market pays for Russell vol
    #: than for the broad index, prior close only.
    add("rvx_vix_spread", logs["rvx"] - logs["vix"])
    add("rvx_vxd_spread", logs["rvx"] - logs["vxd"])
    #: implied-vs-realised: prior RVX against our own prior realised HAR day term
    add("iv_rv_gap", logs["rvx"] - np.log(np.clip(warm_lag("w_rv_bps", 1), 1e-6, None)))

    close = warm_lag("w_close_u6", 1)
    add("abs_prior_ret_bps", np.log(np.clip(
        np.abs(np.log(np.clip(close, 1e-6, None)) - np.log(np.clip(lag(close, 1), 1e-6, None)))
        * 1e4, 1e-3, None)))
    add("log_prior_bar_range", np.log(np.clip(
        (warm_lag("w_high_u6", 1) - warm_lag("w_low_u6", 1)) * 1e4 / np.clip(close, 1e-6, None),
        1e-3, None)))
    #: where the prior close sat inside its own bar -- a close on the low is a
    #: different next-day setup from a close on the high, at equal range.
    add("prior_close_location", np.clip(
        (close - warm_lag("w_low_u6", 1))
        / np.clip(warm_lag("w_high_u6", 1) - warm_lag("w_low_u6", 1), 1e-6, None), 0.0, 1.0))

    #: TARGET-CONSISTENT HAR.  The warm-up HAR above is built on the engine's
    #: 1-SECOND realised series, while the targets are the 1s-grid range and the
    #: 1-MINUTE realised vol -- a different estimator.  The persistence baseline
    #: gets the target's own lag, so the model must have it too or the comparison
    #: is rigged against the model.  These terms only exist once 22 in-scope
    #: sessions have passed, so they are SOFT (train-median filled behind their
    #: own presence indicator) rather than a row-killing requirement.
    def grid_window(series: np.ndarray, window: int) -> np.ndarray:
        out = np.full(n, np.nan)
        for i in range(n):
            if i - window < 0:
                continue
            chunk = series[i - window:i]
            if np.all(np.isfinite(chunk)):
                out[i] = float(np.mean(chunk))
        return out

    def grid_ewma(series: np.ndarray, halflife: float) -> np.ndarray:
        """EWMA of the sessions STRICTLY BEFORE each row."""
        decay = 0.5 ** (1.0 / halflife)
        out = np.full(n, np.nan)
        state = weight = 0.0
        for i in range(n):
            if weight > 0:
                out[i] = state / weight
            value = series[i]
            if np.isfinite(value):
                state = state * decay + value
                weight = weight * decay + 1.0
        return out

    grid_soft = []
    for label, series in (("rng", table["rng_bps"]), ("rv", table["rv_bps"])):
        grid_soft.append(f"g_{label}_d")
        add(f"g_{label}_d", np.log(np.clip(lag(series, 1), 1e-6, None)))
        for window in (5, 22):
            grid_soft.append(f"g_{label}_{window}")
            add(f"g_{label}_{window}", np.log(np.clip(grid_window(series, window), 1e-6, None)))
        grid_soft.append(f"g_{label}_ewma5")
        add(f"g_{label}_ewma5", np.log(np.clip(grid_ewma(series, 5.0), 1e-6, None)))
    add("g_present", np.isfinite(grid_window(table["rv_bps"], 22)).astype(np.float64))

    add("log_session_frac", np.log(table["session_seconds"] / 23400.0))
    weekday = np.array([_weekday(day) for day in table["day"]], dtype=np.float64)
    for k in range(1, 5):
        add(f"dow_{k}", (weekday == k).astype(np.float64))

    X = np.column_stack(columns)
    #: A row is USABLE when everything except the typed-absent PROXY_VOL block is
    #: finite; PROXY_VOL absence is carried by `pv_present` and filled in-train.
    soft = {names.index(name) for name in
            ("log_pv_bid", "log_pv_ask", "log_pv_mid", "pv_spread_rel", *grid_soft)}
    hard = [i for i in range(X.shape[1]) if i not in soft]
    usable = np.all(np.isfinite(X[:, hard]), axis=1)
    for head in HEADS:
        usable &= np.isfinite(table[head])
    return X, names, sorted(soft), usable


def _weekday(day: str) -> int:
    import datetime
    y, m, d = (int(part) for part in day.split("-"))
    return datetime.date(y, m, d).weekday()


def _fill(X: np.ndarray, soft: list, medians: np.ndarray) -> np.ndarray:
    out = X.copy()
    for position, column in enumerate(soft):
        values = out[:, column]
        out[:, column] = np.where(np.isfinite(values), values, medians[position])
    out[~np.isfinite(out)] = 0.0
    return out


def walk_forward(X: np.ndarray, y: np.ndarray, usable: np.ndarray, soft: list,
                 estimator: str) -> tuple:
    """Expanding-window predictions in LOG space; NaN where no lawful model exists."""
    n = len(y)
    pred = np.full(n, np.nan)
    rows = np.flatnonzero(usable)
    fits = []
    model = None
    medians = None
    mu = sd = None
    next_refit = 0
    for i in rows:
        train = rows[rows < i]
        if len(train) < MIN_TRAIN:
            continue
        if model is None or len(train) >= next_refit:
            Xtr_raw = X[train]
            medians = np.array([np.nanmedian(Xtr_raw[:, c]) if np.any(np.isfinite(Xtr_raw[:, c]))
                                else 0.0 for c in soft])
            Xtr = _fill(Xtr_raw, soft, medians)
            mu, sd = Xtr.mean(axis=0), Xtr.std(axis=0)
            sd = np.where(sd > 1e-12, sd, 1.0)
            Ztr = (Xtr - mu) / sd
            ytr = y[train]
            if estimator == "ridge":
                best, best_score = ALPHAS[0], np.inf
                splits = TimeSeriesSplit(n_splits=4)
                for alpha in ALPHAS:
                    errors = []
                    for inner_tr, inner_va in splits.split(Ztr):
                        fitted = Ridge(alpha=alpha).fit(Ztr[inner_tr], ytr[inner_tr])
                        errors.append(np.mean((fitted.predict(Ztr[inner_va]) - ytr[inner_va]) ** 2))
                    score = float(np.mean(errors))
                    if score < best_score:
                        best, best_score = alpha, score
                model = Ridge(alpha=best).fit(Ztr, ytr)
                fits.append({"at": int(i), "n_train": int(len(train)), "alpha": best})
            else:
                model = HistGradientBoostingRegressor(
                    max_iter=200, learning_rate=0.05, max_depth=3, min_samples_leaf=20,
                    l2_regularization=1.0, early_stopping=False,
                    random_state=P.SEED % 2**31).fit(Ztr, ytr)
                fits.append({"at": int(i), "n_train": int(len(train))})
            next_refit = len(train) + REFIT_EVERY
        Zi = ((_fill(X[i:i + 1], soft, medians) - mu) / sd)
        pred[i] = float(model.predict(Zi)[0])
    return pred, fits


def debiased_baseline(raw_log: np.ndarray, y: np.ndarray, usable: np.ndarray) -> np.ndarray:
    """`raw_log` plus the expanding-window mean of (y - raw_log): its best shot."""
    n = len(y)
    out = np.full(n, np.nan)
    rows = np.flatnonzero(usable & np.isfinite(raw_log))
    for i in rows:
        train = rows[rows < i]
        if len(train) < MIN_TRAIN:
            continue
        out[i] = raw_log[i] + float(np.mean(y[train] - raw_log[train]))
    return out


#: The stack's own warm-up: how many rows of walk-forward-OOS predictions must
#: exist before the combination weights are fitted.
STACK_MIN = 40


def stack(curves: dict, y: np.ndarray, usable: np.ndarray) -> np.ndarray:
    """Non-negative combination of the arms, refitted causally at every row.

    Every input is ALREADY an out-of-sample walk-forward prediction, so fitting
    the weights on rows strictly before `i` uses nothing the model had not
    already earned.  Non-negativity plus a free intercept keeps a 4-arm stack
    stable at ~100 training rows and makes the weights readable: this is the
    lawful way to say "keep the ridge where it wins and fall back on ATR14
    where it does not", instead of choosing per era after the fact.
    """
    arms = list(curves)
    matrix = np.column_stack([curves[name] for name in arms])
    out = np.full(len(y), np.nan)
    have = np.all(np.isfinite(matrix), axis=1) & usable & np.isfinite(y)
    rows = np.flatnonzero(have)
    for position, i in enumerate(rows):
        if position < STACK_MIN:
            continue
        train = rows[:position]
        design = np.column_stack([np.ones(len(train)), matrix[train]])
        #: centre the target so the intercept absorbs level and nnls only has to
        #: allocate the SHAPE across arms.
        weights, _ = optimize.nnls(design, y[train])
        out[i] = float(np.concatenate([[1.0], matrix[i]]) @ weights)
    return out


def score(y: np.ndarray, pred: np.ndarray, mask: np.ndarray) -> dict:
    rows = mask & np.isfinite(pred) & np.isfinite(y)
    if rows.sum() < 5:
        return {"n": int(rows.sum())}
    a, b = y[rows], pred[rows]
    sse = float(np.sum((a - b) ** 2))
    sst = float(np.sum((a - a.mean()) ** 2))
    return {
        "n": int(rows.sum()),
        "sse": sse,
        "r2_log": 1.0 - sse / sst if sst > 0 else float("nan"),
        "spearman": float(stats.spearmanr(a, b).statistic),
        "mae_bps": float(np.mean(np.abs(np.exp(a) - np.exp(b)))),
        "mape": float(np.mean(np.abs(np.expm1(b - a)))),
    }


def main() -> None:
    global MIN_TRAIN
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-train", type=int, default=MIN_TRAIN)
    parser.add_argument("--tag", default="")
    args = parser.parse_args()
    MIN_TRAIN = args.min_train
    table = read_table()
    X, names, soft, usable = build_design(table)
    sessions = table["session"]
    report = {"features": names, "n_usable": int(usable.sum()), "heads": {}}
    emit = {"session": sessions}

    for head in HEADS:
        y = np.log(np.clip(table[head], 1e-6, None))
        base_persist = np.full(len(y), np.nan)
        base_persist[1:] = y[:-1]
        base_atr = np.log(np.clip(table["atr14_bps"], 1e-6, None))
        preds = {
            "ridge": walk_forward(X, y, usable, soft, "ridge"),
            "gbt": walk_forward(X, y, usable, soft, "gbt"),
        }
        curves = {name: value[0] for name, value in preds.items()}
        curves["persistence"] = debiased_baseline(base_persist, y, usable)
        curves["atr14"] = debiased_baseline(base_atr, y, usable)
        curves["stack"] = stack({k: curves[k] for k in
                                 ("ridge", "gbt", "persistence", "atr14")}, y, usable)

        head_report = {"fits_ridge": len(preds["ridge"][1]), "eras": {}}
        for era_name, lo, hi in ERAS:
            mask = (sessions >= lo) & (sessions <= hi)
            era = {name: score(y, curve, mask) for name, curve in curves.items()}
            for arm in ("ridge", "gbt", "stack"):
                for base in ("persistence", "atr14"):
                    if "sse" in era[arm] and "sse" in era[base] and era[base]["sse"] > 0:
                        era[arm][f"skill_vs_{base}"] = 1.0 - era[arm]["sse"] / era[base]["sse"]
            head_report["eras"][era_name] = era
        mask_all = sessions >= 0
        head_report["ALL"] = {name: score(y, curve, mask_all) for name, curve in curves.items()}
        report["heads"][head] = head_report
        for name, curve in curves.items():
            emit[f"{head}__{name}"] = curve
        emit[f"{head}__actual"] = y

    report["min_train"] = MIN_TRAIN
    report["dev_era"] = DEV_ERA
    (FVOL / f"model_report{args.tag}.json").write_text(json.dumps(report, indent=2))
    columns = list(emit)
    with (FVOL / f"daily_forecast{args.tag}.tsv").open("w") as handle:
        handle.write("\t".join(columns) + "\n")
        for i in range(len(sessions)):
            handle.write("\t".join(
                str(int(emit[c][i])) if c == "session" else
                ("" if not np.isfinite(emit[c][i]) else f"{emit[c][i]:.6f}")
                for c in columns) + "\n")

    for head, block in report["heads"].items():
        print(f"\n=== {head} ===")
        for era_name, era in block["eras"].items():
            line = [f"{era_name:<14} n={era['ridge'].get('n', 0):>3}"]
            for arm in ("ridge", "gbt", "stack", "persistence", "atr14"):
                s = era[arm]
                if "r2_log" in s:
                    line.append(f"{arm}: R2={s['r2_log']:+.3f} rho={s['spearman']:+.3f}")
            print("  " + " | ".join(line))
            for arm in ("ridge", "gbt", "stack"):
                s = era[arm]
                if "skill_vs_persistence" in s:
                    print(f"      {arm} skill vs persistence {s['skill_vs_persistence']:+.3f}"
                          f"  vs atr14 {s['skill_vs_atr14']:+.3f}")
    print("\n" + str(FVOL / f"model_report{args.tag}.json"))


if __name__ == "__main__":
    main()
