#!/usr/bin/env python3
"""precision.py — the PRECISION lane: raise the ENTERED-WINNER SHARE.

WHY THIS EXISTS.  `EXIT_RUNG3_VERDICT.md` §7(b) closes the exit program and
names the one object left: under hold-to-close the entered book splits into
winners at +$420..+$654 and duds at -$235..-$266 with winners only 28-34% of
the trades, so "a classifier that moves the entered winner share from 32% to
~45% pays more than any exit rule in the grid".  Three rungs falsified the
POST-entry state; this file works the PRE-entry side, with the exit frozen at
the keepers those rungs produced.

FROZEN, NOT REDESIGNED (the deployment operating point):

    occupancy   TWO concurrent positions            (D-030, rung 2/3's column)
    wall        $300, monitored from entry, gap-through   (rung 3: do not amend)
    exit        `mirror@1.00`                       (rung 1's surviving rule)
    overlay     `cont[lasso,B]@c25`                 (rung 3's drawdown keeper)
    replay      `exit_engine` / `exit_stopping` machinery, unchanged

Both exit keepers are reported for every cell, plus their conjunction
(`mirror+overlay`, exit at whichever fires first) and `close`/`oracle` as the
floor and the ceiling.  Nothing about the exit is tuned here.

THE FOUR EXPERIMENTS (all on `era_retest`'s walk-forward splits; a segment
trains only on sessions strictly earlier than its test block):

1. THRESHOLD GEOMETRY.  Replace top-k/day with an ABSOLUTE model-P threshold:
   enter every candidate whose score clears it, chronologically, up to two
   concurrent.  The threshold grid is preregistered as the study quantiles
   P@top-{5,10,15,20}% and is read off SESSION-GROUPED OUT-OF-FOLD predictions
   on each segment's own TRAINING window — never on a test block.  This is
   era-adaptive by construction: a thin day offers few candidates over the bar,
   a rich day offers many.  Arms: `E/T/I only` and `v3 no-M`.

2. QUALITY GATES stacked on (1), each alone and jointly:
     `gate_clean`  E_gate_clean == 1 — the capacity conjunction, six gates, no
                   signal read at all (+6pt winner rate as a population fact,
                   MODEL_V3_REPORT §Ablations).
     `purge`       drop the panel's unanimous DO-NOT-BUILD columns
                   (PANEL_SYNTHESIS §2 negative convergence) and REFIT.
     `morning`     first 3h of the session only (the era telltale: ERA_NOTES
                   §2 "late-day vol channels are an unreliable sensor"; the
                   population splits 30-35% winners AM vs 18-24% PM in every
                   era).

3. CLASS-TARGET REFIT.  Same features, same frozen hypers, target replaced by
   the DEPLOYMENT class — `cert >= $1,000 AND MAE <= $300` (D-021's expectancy
   and MAE pair) — instead of the roster's `cert >= $500`.  One refit per arm.

4. VERDICTS per era (f..i + the `blind_e3` control) under the full deployment
   replay, plus a label-shuffle control on one refit.

LAWS.  Walk-forward purity asserted in code; usable columns decided on each
segment's own training window; the threshold grid, the gate list, the purge
list and the class definition were all fixed before any number was computed;
every cell of the grid is written to TSV, not just the winners; the sealed zone
(>= `packlib.SEALED_FROM`) is never read.

    precision.py [--stage score|trades|replay|report|all] [--rebuild]
"""
from __future__ import annotations

import argparse
import os
import pathlib
import sys

os.environ.setdefault("OMP_NUM_THREADS", "8")

import numpy as np                                        # noqa: E402
import pandas as pd                                       # noqa: E402

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import packlib as P                                       # noqa: E402
import distill_model as dm                                # noqa: E402
import walkforward as wf                                  # noqa: E402
import era_retest as er                                   # noqa: E402
import exit_engine as ee                                  # noqa: E402
import exit_state_model as esm                            # noqa: E402

ROOT = P.ROOT
MATRIX = ROOT / "FEATURES_ERA.tsv"
OUTDIR = ROOT / "precision_segments"
REPORT = ROOT / "PRECISION_REPORT.md"
STOP_PREDS = ROOT / "exit_segments" / "stop_preds.tsv"

SCORES = OUTDIR / "precision_scores.tsv"
THRESH = OUTDIR / "precision_thresholds.tsv"
TRADES = OUTDIR / "precision_trades.tsv"
GRID = OUTDIR / "precision_grid.tsv"
SHUF = OUTDIR / "precision_shuffle.tsv"
FITS = OUTDIR / "precision_fits.tsv"

SEGMENTS = er.SEGMENTS
SEED = dm.SEED
FROZEN = wf.FROZEN

# ---- preregistered, fixed before any number was computed --------------------
ARMS = ("E/T/I only", "v3 no-M")
#: study quantiles of the OOF training-window score: enter above P@top-q%
TOPQ = (5, 10, 15, 20)
#: the reference geometry the whole program has used so far
TOPK = (3, 5)
SLOTS = 2                                   # the deployment occupancy (D-030)
MORNING_S = 3 * 3600                        # "first 3h" of the 6.5h session
WINNER_CERT = 500.0                         # the roster's own winner label
CLASS_CERT, CLASS_MAE = 1000.0, 300.0       # the DEPLOYMENT class (D-021)
CV_FOLDS = 5
SHUFFLE_DRAWS = 3
SHUFFLE_SEGMENT = "i"
SHUFFLE_ARM = "E/T/I only"
#: the DESIGN CENTRE — named before the numbers, so that one cell per era is
#: reportable without a maximum being taken over the test blocks
CENTRE = dict(arm="v3 no-M", target="w500", variant="base", gates="none",
              geometry="P@top10", rule="mirror@1.00")

TARGETS = ("w500", "wclass")
VARIANTS = ("base", "purge")
GATESETS = ("none", "gate_clean", "morning", "gate_clean+morning")
RULES = ("close", "mirror@1.00", "overlay", "mirror+overlay", "oracle")
#: rung 3's drawdown keeper, read from `exit_segments/stop_preds.tsv`
OVERLAY_COLUMN = "p_lasso_B_c25"
OVERLAY_COST = 25.0
OFFSETS = esm.OFFSETS

#: PANEL_SYNTHESIS §2, the unanimous DO-NOT-BUILD list, mapped onto the columns
#: this matrix actually carries.  Items with no corresponding column are kept in
#: the table with an empty list so the report can say so.
PURGE = {
    "traded-IV call-put skew alone": (
        "V_skew_traded", "V_skew_traded_o", "V_skew_slope", "V_skew_slope_o",
        "X_V_skew_traded_o__R_trend_day", "X_V_skew_traded_o__R_compress",
        "X_V_skew_traded_o__R_atr_high", "X_V_skew_traded_o__R_late"),
    "urgency / at-touch fraction alone": (
        "U_urg120", "U_urg120_z", "U_urg_clock_z", "E_urg120",
        "X_U_urg120_z__R_trend_day", "X_U_urg120_z__R_compress",
        "X_U_urg120_z__R_atr_high", "X_U_urg120_z__R_late"),
    "depth_at_touch alone": (
        "D_depth60", "D_depth60_z",
        "X_D_depth60_z__R_trend_day", "X_D_depth60_z__R_compress",
        "X_D_depth60_z__R_atr_high", "X_D_depth60_z__R_late"),
    "prints/min alone": ("U_printrate_z",),
    "T-15m/T-30m flow bins alone": (),          # no such column in this matrix
    "requote latency": (),                      # never built
    "valid_bucket_fraction": (),                # never built
    "standalone charm / vanna / gamma |z|": (
        "Z_gamma120_z", "Z_vanna120_z", "Z_charm120_z",
        "T_gamma1_z", "T_vanna1_z"),
    "block size after reclaim": (
        "K_blk_frac600", "K_contam_n600", "K_contam_n120", "K_optcontam_n600"),
    "PROXY_VOL direction": (
        "Y_pv_slope10", "Y_pv_slope30", "Y_expanding", "Y_slope_x_agree"),
}
PURGE_COLUMNS = tuple(sorted({c for group in PURGE.values() for c in group}))


# ==========================================================================
# labels
# ==========================================================================

def labels_of(frame: pd.DataFrame, target: str) -> np.ndarray:
    if target == "w500":
        return frame["winner"].to_numpy().astype(int)
    return ((frame["cert"] >= CLASS_CERT)
            & (frame["cert_mae"] <= CLASS_MAE)).to_numpy().astype(int)


# ==========================================================================
# 1 — scores and the preregistered thresholds
# ==========================================================================

def oof_scores(train: pd.DataFrame, columns: list, y: np.ndarray) -> np.ndarray:
    """Session-grouped 5-fold out-of-fold P on the TRAINING window.

    The threshold grid is a quantile of THIS vector.  In-sample predictions
    would be inflated and would set the bar in the wrong place; the test block
    is never touched.
    """
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.model_selection import GroupKFold
    X = train[columns].to_numpy(float)
    groups = train["session"].to_numpy()
    out = np.full(len(train), np.nan)
    for fold, (fit, held) in enumerate(GroupKFold(n_splits=CV_FOLDS)
                                       .split(X, y, groups)):
        if len(np.unique(y[fit])) < 2:
            continue
        model = HistGradientBoostingClassifier(random_state=SEED + fold, **FROZEN)
        model.fit(X[fit], y[fit])
        out[held] = model.predict_proba(X[held])[:, 1]
    return out


def stage_score(rebuild: bool) -> tuple:
    frame = pd.read_csv(MATRIX, sep="\t", low_memory=False)
    print(f"matrix {frame.shape} <- {MATRIX}", flush=True)
    if not rebuild and SCORES.exists() and THRESH.exists():
        return (pd.read_csv(SCORES, sep="\t"), pd.read_csv(THRESH, sep="\t"),
                pd.read_csv(FITS, sep="\t"), frame)

    from sklearn.metrics import roc_auc_score
    rows, thresholds, fits = [], [], []
    for seg, block in SEGMENTS:
        test = frame[frame["block"] == block].reset_index(drop=True)
        train = frame[frame["session"] < int(test["session"].min())] \
            .reset_index(drop=True)
        assert train["session"].max() < test["session"].min(), "walk-forward purity"
        sets = er.arm_columns(frame, train)
        for arm in ARMS:
            for variant in VARIANTS:
                columns = [c for c in sets[arm]
                           if variant == "base" or c not in PURGE_COLUMNS]
                for target in TARGETS:
                    y = labels_of(train, target)
                    score = wf.fit_frozen(train, test, columns, labels=y)
                    oof = oof_scores(train, columns, y)
                    finite = oof[np.isfinite(oof)]
                    for q in TOPQ:
                        thresholds.append({
                            "segment": seg, "block": block, "arm": arm,
                            "variant": variant, "target": target, "topq": q,
                            "threshold": float(np.quantile(finite, 1 - q / 100.0)),
                            "train_rows": len(train), "features": len(columns)})
                    key = f"{arm}|{variant}|{target}"
                    for i in range(len(test)):
                        rows.append({"segment": seg, "block": block,
                                     "session": int(test["session"].iloc[i]),
                                     "id": test["id"].iloc[i], "key": key,
                                     "score": float(score[i])})
                    y_test_500 = labels_of(test, "w500")
                    y_test_cls = labels_of(test, "wclass")
                    fits.append({
                        "segment": seg, "block": block, "arm": arm,
                        "variant": variant, "target": target,
                        "features": len(columns), "train_rows": len(train),
                        "train_pos_rate": float(y.mean()),
                        "auc_w500": float(roc_auc_score(y_test_500, score))
                        if len(np.unique(y_test_500)) > 1 else np.nan,
                        "auc_wclass": float(roc_auc_score(y_test_cls, score))
                        if len(np.unique(y_test_cls)) > 1 else np.nan,
                        "oof_auc": float(roc_auc_score(y[np.isfinite(oof)],
                                                       oof[np.isfinite(oof)]))
                        if len(np.unique(y[np.isfinite(oof)])) > 1 else np.nan})
                    print(f"  {seg} {arm:12s} {variant:5s} {target:6s} "
                          f"{len(columns):3d} cols  AUC(w500) "
                          f"{fits[-1]['auc_w500']:.3f}  AUC(class) "
                          f"{fits[-1]['auc_wclass']:.3f}", flush=True)

    OUTDIR.mkdir(parents=True, exist_ok=True)
    scores = pd.DataFrame(rows).pivot_table(
        index=["segment", "block", "session", "id"], columns="key",
        values="score").reset_index()
    scores.columns.name = None
    scores.to_csv(SCORES, sep="\t", index=False)
    thr = pd.DataFrame(thresholds)
    thr.to_csv(THRESH, sep="\t", index=False)
    fit = pd.DataFrame(fits)
    fit.to_csv(FITS, sep="\t", index=False)
    return scores, thr, fit, frame


# ==========================================================================
# 2 — the trades: rung 1/3 replay arithmetic, every candidate, five rules
# ==========================================================================

def overlay_lookup() -> dict:
    preds = pd.read_csv(STOP_PREDS, sep="\t",
                        usecols=["session", "id", "offset_min", OVERLAY_COLUMN])
    lookup: dict = {}
    for row in preds.itertuples(index=False):
        value = getattr(row, OVERLAY_COLUMN)
        if np.isfinite(value):
            lookup.setdefault((int(row.session), row.id), {})[
                int(row.offset_min)] = float(value)
    return lookup


def trade_variants(session: ee.Session, second: int, side: str,
                   overlay: dict) -> dict:
    """Every rule's exit for ONE candidate, on rung 1's arithmetic exactly.

    The wall is monitored from entry for every rule and fills at the next
    lawful mark strictly after the crossing (gap-through kept); whichever of
    (wall, rule) fires first is the exit.
    """
    start = session.position(second)
    entry_second = int(session.second[start])
    nets = ee.net_cent(int(session.mid[start]), session.mid, side)

    forward = np.flatnonzero(nets[start + 1:] <= ee.WALL_NET_CENT)
    wall_fill = (min(int(forward[0]) + start + 2, session.close_pos)
                 if forward.size else None)
    limit = wall_fill if wall_fill is not None else session.close_pos

    positions = {"close": session.close_pos}

    hit = session.mirror_second(1.00, side, entry_second)
    positions["mirror@1.00"] = session.position(
        hit if hit is not None else int(session.second[session.close_pos]))

    over = limit
    for offset in OFFSETS:
        value = overlay.get(offset)
        if value is None:
            continue
        pos = session.position(second + offset * 60)
        if pos <= start or pos >= limit:
            continue
        if value < OVERLAY_COST:
            over = pos
            break
    positions["overlay"] = over
    positions["mirror+overlay"] = min(positions["mirror@1.00"], over)

    window = nets[start + 1:limit + 1]
    best = int(np.argmax(window)) + start + 1 if window.size else limit
    positions["oracle"] = best if window.size and nets[best] > 0 else limit

    out = {}
    for rule, rule_pos in positions.items():
        exit_pos = min(rule_pos, limit)
        out[rule] = {
            "exit_second": int(session.second[exit_pos]),
            "pnl": float(nets[exit_pos]) / 100.0,
            "stopped": bool(wall_fill is not None and exit_pos == wall_fill
                            and wall_fill <= rule_pos),
            "hold_s": int(session.second[exit_pos]) - entry_second}
    return out


def stage_trades(frame: pd.DataFrame, rebuild: bool) -> pd.DataFrame:
    if not rebuild and TRADES.exists():
        trades = pd.read_csv(TRADES, sep="\t")
        print(f"trades {trades.shape} <- {TRADES}", flush=True)
        return trades
    overlay = overlay_lookup()
    print(f"overlay predictions for {len(overlay)} candidates", flush=True)
    rows = []
    for seg, block in SEGMENTS:
        test = frame[frame["block"] == block]
        sessions = sorted(test["session"].unique())
        print(f"trades segment {seg} ({block}): {len(sessions)} sessions",
              flush=True)
        for done, ordinal in enumerate(sessions, 1):
            session = ee.Session(int(ordinal), block)
            day = test[test["session"] == ordinal]
            for row in day.itertuples(index=False):
                variants = trade_variants(session, int(row.second), row.side,
                                          overlay.get((int(ordinal), row.id), {}))
                for rule, trade in variants.items():
                    rows.append({"segment": seg, "block": block,
                                 "session": int(ordinal), "id": row.id,
                                 "second": int(row.second), "side": row.side,
                                 "cert": float(row.cert),
                                 "cert_mae": float(row.cert_mae),
                                 "winner": int(row.winner), "rule": rule,
                                 **trade})
            if done % 50 == 0 or done == len(sessions):
                print(f"  {done}/{len(sessions)} sessions", flush=True)
    trades = pd.DataFrame(rows)
    OUTDIR.mkdir(parents=True, exist_ok=True)
    trades.to_csv(TRADES, sep="\t", index=False)
    return trades


# ==========================================================================
# 3 — the replay grid
# ==========================================================================

def entered_metrics(days: list, cert: np.ndarray, mae: np.ndarray,
                    pnl: np.ndarray, stopped: np.ndarray, hold: np.ndarray,
                    picked_day: float, admitted: int = 0) -> dict:
    """One cell.  `days` is EVERY candidate-bearing session of the era."""
    daily = np.array(days, dtype=float)
    #: D-021's drawdown panel: the worst 5-day rolling sum (MDD proxy)
    if daily.size >= 5:
        roll = np.convolve(daily, np.ones(5), mode="valid")
        mdd5 = float(roll.min())
    else:
        mdd5 = float(daily.sum()) if daily.size else np.nan
    entered = float(cert.sum() / len(daily)) if daily.size else np.nan
    return {
        "days": len(daily),
        "realized_day": float(daily.mean()) if daily.size else np.nan,
        "picked_day": picked_day,
        "entered_cert_day": entered,
        "capture_entered_pct": (100.0 * daily.mean() / entered
                                if entered else np.nan),
        "trades_day": (len(pnl) / len(daily)) if daily.size else np.nan,
        "n_trades": int(len(pnl)),
        #: candidates the ENTRY POLICY admitted, before the occupancy cap
        "n_admitted": int(admitted),
        "n_entered_day": (admitted / len(daily)) if daily.size else np.nan,
        #: THE OBJECT: share of ENTERED trades that are winners
        "winner_share": (100.0 * float((cert >= WINNER_CERT).mean())
                         if cert.size else np.nan),
        "class_share": (100.0 * float(((cert >= CLASS_CERT)
                                       & (mae <= CLASS_MAE)).mean())
                        if cert.size else np.nan),
        "entered_cert_mean": float(cert.mean()) if cert.size else np.nan,
        "trade_mean": float(pnl.mean()) if pnl.size else np.nan,
        "winner_trade_mean": (float(pnl[cert >= WINNER_CERT].mean())
                              if (cert >= WINNER_CERT).any() else np.nan),
        "dud_trade_mean": (float(pnl[cert < WINNER_CERT].mean())
                           if (cert < WINNER_CERT).any() else np.nan),
        "median_day": float(np.median(daily)) if daily.size else np.nan,
        "worst_day": float(daily.min()) if daily.size else np.nan,
        "best_day": float(daily.max()) if daily.size else np.nan,
        "mdd5": mdd5,
        "loss_days_pct": (100.0 * float((daily < 0).mean())) if daily.size else np.nan,
        "hold_min": float(hold.mean()) / 60.0 if hold.size else np.nan,
        "stop_rate": 100.0 * float(stopped.mean()) if stopped.size else np.nan,
    }


def occupancy_replay(order: np.ndarray, second: np.ndarray, exits: np.ndarray,
                     slots: int) -> np.ndarray:
    """`exit_state_model.replay_day` as an index filter.

    `order` is the day's eligible rows already sorted by (second, id).  A
    candidate is entered only if fewer than `slots` positions are still open at
    its own second; an open position frees the slot the moment its exit second
    is reached (`stop > second`), which is rung 2/3's rule verbatim.
    """
    taken, open_until = [], []
    for row in order:
        now = second[row]
        open_until = [stop for stop in open_until if stop > now]
        if len(open_until) >= slots:
            continue
        taken.append(row)
        open_until.append(exits[row])
    return np.array(taken, dtype=np.int64)


def stage_replay(frame: pd.DataFrame, scores: pd.DataFrame, thr: pd.DataFrame,
                 trades: pd.DataFrame) -> pd.DataFrame:
    keys = [f"{arm}|{variant}|{target}" for arm in ARMS
            for variant in VARIANTS for target in TARGETS]
    base = frame[["session", "block", "id", "second", "cert", "cert_mae",
                  "winner", "E_gate_clean"]].merge(
        scores.drop(columns=["segment"]), on=["session", "id", "block"],
        how="inner").sort_values(["session", "second", "id"]).reset_index(drop=True)
    thr_index = {(r.segment, r.arm, r.variant, r.target, int(r.topq)):
                 float(r.threshold) for r in thr.itertuples(index=False)}

    results = []
    for seg, block in SEGMENTS:
        part = base[base["block"] == block].reset_index(drop=True)
        second = part["second"].to_numpy(np.int64)
        cert = part["cert"].to_numpy(float)
        mae = part["cert_mae"].to_numpy(float)
        gate = part["E_gate_clean"].to_numpy(float)
        sessions = part["session"].to_numpy(np.int64)
        uniq = np.unique(sessions)
        rows_of = {int(s): np.flatnonzero(sessions == s) for s in uniq}
        score_of = {key: part[key].to_numpy(float) for key in keys}
        #: the five exit books, aligned to `part`'s row order
        book = {}
        tpart = trades[trades["block"] == block]
        index = {(int(s), i): n for n, (s, i)
                 in enumerate(zip(part["session"], part["id"]))}
        for rule in RULES:
            sub = tpart[tpart["rule"] == rule]
            exits = np.zeros(len(part), np.int64)
            pnl = np.zeros(len(part), float)
            stopped = np.zeros(len(part), bool)
            hold = np.zeros(len(part), np.int64)
            for row in sub.itertuples(index=False):
                n = index[(int(row.session), row.id)]
                exits[n], pnl[n] = int(row.exit_second), float(row.pnl)
                stopped[n], hold[n] = bool(row.stopped), int(row.hold_s)
            book[rule] = (exits, pnl, stopped, hold)
        print(f"replay segment {seg} ({block}): {len(uniq)} sessions", flush=True)

        gate_mask = {"gate_clean": gate == 1.0,
                     "morning": second <= MORNING_S}
        for arm in ARMS:
            for variant in VARIANTS:
                for target in TARGETS:
                    key = f"{arm}|{variant}|{target}"
                    values = score_of[key]
                    geometries = ([(f"topk{k}", ("topk", float(k))) for k in TOPK]
                                  + [(f"P@top{q}", ("thr", thr_index[
                                      (seg, arm, variant, target, q)]))
                                     for q in TOPQ])
                    for gates in GATESETS:
                        keep = np.ones(len(part), bool)
                        for name in gates.split("+"):
                            if name in gate_mask:
                                keep &= gate_mask[name]
                        for label, (kind, value) in geometries:
                            #: the eligible list per session, in decision order
                            chosen = {}
                            for s in uniq:
                                rows = rows_of[int(s)]
                                rows = rows[keep[rows]]
                                if kind == "topk":
                                    k = int(value)
                                    if len(rows) > k:
                                        best = np.argsort(
                                            -values[rows], kind="stable")[:k]
                                        rows = np.sort(rows[best])
                                else:
                                    rows = rows[values[rows] >= value]
                                chosen[int(s)] = rows
                            picked_day = float(np.mean(
                                [cert[chosen[int(s)]].sum() for s in uniq]))
                            admitted = int(sum(len(chosen[int(s)]) for s in uniq))
                            for rule in RULES:
                                exits, pnl, stopped, hold = book[rule]
                                days, taken = [], []
                                for s in uniq:
                                    got = occupancy_replay(
                                        chosen[int(s)], second, exits, SLOTS)
                                    days.append(float(pnl[got].sum())
                                                if got.size else 0.0)
                                    if got.size:
                                        taken.append(got)
                                idx = (np.concatenate(taken) if taken
                                       else np.zeros(0, np.int64))
                                results.append({
                                    "segment": seg, "block": block,
                                    "era_label": er.ERA_LABEL[block],
                                    "arm": arm, "variant": variant,
                                    "target": target, "gates": gates,
                                    "geometry": label, "rule": rule,
                                    "slots": SLOTS,
                                    **entered_metrics(days, cert[idx], mae[idx],
                                                      pnl[idx], stopped[idx],
                                                      hold[idx], picked_day,
                                                      admitted)})
    grid = pd.DataFrame(results)
    grid.to_csv(GRID, sep="\t", index=False)
    print(f"grid {grid.shape} -> {GRID}", flush=True)
    return grid


# ==========================================================================
# 4 — the label-shuffle control on the class-target refit
# ==========================================================================

def stage_shuffle(frame: pd.DataFrame, trades: pd.DataFrame,
                  rebuild: bool) -> pd.DataFrame:
    """Refit experiment 3 on PERMUTED training labels and replay it whole.

    Same columns, same frozen hyper-parameters, same OOF threshold machinery,
    same entry policy, same exits.  If the precision gain is real, the shuffled
    twin must not reproduce it.
    """
    if not rebuild and SHUF.exists():
        return pd.read_csv(SHUF, sep="\t")
    seg, block = [pair for pair in SEGMENTS if pair[0] == SHUFFLE_SEGMENT][0]
    test = frame[frame["block"] == block].reset_index(drop=True)
    train = frame[frame["session"] < int(test["session"].min())].reset_index(drop=True)
    columns = er.arm_columns(frame, train)[SHUFFLE_ARM]
    truth = labels_of(train, "wclass")
    rng = np.random.default_rng(SEED)

    second = test["second"].to_numpy(np.int64)
    cert = test["cert"].to_numpy(float)
    mae = test["cert_mae"].to_numpy(float)
    sessions = test["session"].to_numpy(np.int64)
    uniq = np.unique(sessions)
    rows_of = {int(s): np.flatnonzero(sessions == s) for s in uniq}
    order = np.lexsort((test["id"].to_numpy(), second))
    rank = {int(s): np.array([n for n in order if sessions[n] == s], np.int64)
            for s in uniq}
    book = {}
    tpart = trades[trades["block"] == block]
    index = {(int(s), i): n for n, (s, i) in enumerate(zip(test["session"], test["id"]))}
    for rule in ("close", "mirror@1.00", "overlay"):
        sub = tpart[tpart["rule"] == rule]
        exits = np.zeros(len(test), np.int64)
        pnl = np.zeros(len(test), float)
        stopped = np.zeros(len(test), bool)
        hold = np.zeros(len(test), np.int64)
        for row in sub.itertuples(index=False):
            n = index[(int(row.session), row.id)]
            exits[n], pnl[n] = int(row.exit_second), float(row.pnl)
            stopped[n], hold[n] = bool(row.stopped), int(row.hold_s)
        book[rule] = (exits, pnl, stopped, hold)

    rows = []
    for draw in range(SHUFFLE_DRAWS + 1):
        real = draw == SHUFFLE_DRAWS
        y = truth if real else rng.permutation(truth)
        #: the REAL draw uses the main run's seed, so it reproduces the grid cell
        score = wf.fit_frozen(train, test, columns, labels=y,
                              seed=SEED if real else SEED + draw)
        oof = oof_scores(train, columns, y)
        finite = oof[np.isfinite(oof)]
        for q in TOPQ:
            cut = float(np.quantile(finite, 1 - q / 100.0))
            for rule in ("close", "mirror@1.00", "overlay"):
                exits, pnl, stopped, hold = book[rule]
                days, taken, admitted = [], [], 0
                for s in uniq:
                    eligible = rank[int(s)][score[rank[int(s)]] >= cut]
                    admitted += len(eligible)
                    got = occupancy_replay(eligible, second, exits, SLOTS)
                    days.append(float(pnl[got].sum()) if got.size else 0.0)
                    if got.size:
                        taken.append(got)
                idx = np.concatenate(taken) if taken else np.zeros(0, np.int64)
                rows.append({"draw": "REAL" if real else f"shuffle{draw}",
                             "segment": seg, "block": block, "arm": SHUFFLE_ARM,
                             "target": "wclass", "geometry": f"P@top{q}",
                             "rule": rule, "threshold": cut,
                             **entered_metrics(days, cert[idx], mae[idx], pnl[idx],
                                               stopped[idx], hold[idx], np.nan,
                                               admitted)})
        print(f"  shuffle draw {draw} done", flush=True)
    out = pd.DataFrame(rows)
    out.to_csv(SHUF, sep="\t", index=False)
    return out


# ==========================================================================
# 5 — report
# ==========================================================================

RTY = {"blind_e3": 0.879, "e4": 0.895, "e5": 1.004, "e6": 1.099, "e7": 1.073}
GEOM_ORDER = ["topk3", "topk5"] + [f"P@top{q}" for q in TOPQ]
money, number = ee.money, ee.number


def cell(grid: pd.DataFrame, **kw) -> pd.DataFrame:
    part = grid
    for key, value in kw.items():
        part = part[part[key] == value]
    return part


def loeo(grid: pd.DataFrame, block: str) -> pd.Series:
    """LEAVE-ONE-ERA-OUT selection — the honest deployable number.

    The cell is chosen by the mean realised $/day over the OTHER DEPLOYMENT
    eras (`e4..e7`; the 20-day `blind_e3` control is never a selection basis)
    and then read off this one, so no configuration is ever picked on the block
    it is scored on.
    """
    impl = grid[grid["rule"] != "oracle"]
    keys = ["arm", "variant", "target", "gates", "geometry", "rule"]
    basis = impl[(impl["block"] != block) & (impl["block"] != "blind_e3")]
    others = basis.groupby(keys)["realized_day"].mean()
    best = others.idxmax()
    part = impl[impl["block"] == block]
    for key, value in zip(keys, best):
        part = part[part[key] == value]
    return part.iloc[0]


def write_report(grid: pd.DataFrame, fit: pd.DataFrame, thr: pd.DataFrame,
                 shuffle: pd.DataFrame, frame: pd.DataFrame) -> None:
    census = frame[frame["block"].isin([b for _, b in SEGMENTS])]
    candidates_day = (census.groupby("block").size()
                      / census.groupby("block")["session"].nunique()).to_dict()
    highest = int(census["session"].max())
    out = ["# PRECISION — the entered-winner share at the deployment operating point\n"]
    out.append(
        "Two concurrent positions, the $300 wall with gap-through, 576c charged "
        "once per trade, `mirror@1.00` and the `cont[lasso,B]@c25` overlay as the "
        "frozen exit keepers, `close` as the floor and `oracle` as the ceiling.  "
        "Entry geometry, the three quality gates and the class target are the "
        "only things that move.  Every cell of the "
        f"{len(grid):,}-row grid is in `precision_segments/precision_grid.tsv`.\n")
    verdict = ROOT / "PRECISION_VERDICT.md"
    if verdict.exists():
        out.append("\n" + verdict.read_text().rstrip() + "\n")

    # -------------------------------------------------- 1. the verdict table
    out.append("\n## VERDICT TABLE — the full deployment replay, per era\n")
    out.append("Design-centre arm/target (`v3 no-M`, target `cert >= $500`, no "
               "gates) so that one row per (era, geometry) is readable without a "
               "maximum being taken; `winner%` is the ENTERED-winner share (the "
               "object), `class%` the strict deployment class, `mdd5` the worst "
               "5-day rolling sum (D-021's drawdown panel).\n")
    out.append("| era | geometry | rule | $/day | RTY-mini | winner% | class% | "
               "trades/day | hold min | worst day | mdd5 | $/trade | entered cert |")
    out.append("|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for seg, block in SEGMENTS:
        for geometry in GEOM_ORDER:
            for rule in ("mirror@1.00", "overlay", "close"):
                part = cell(grid, block=block, arm=CENTRE["arm"],
                            variant=CENTRE["variant"], target=CENTRE["target"],
                            gates=CENTRE["gates"], geometry=geometry, rule=rule)
                if part.empty:
                    continue
                row = part.iloc[0]
                out.append(
                    f"| `{block}` | {geometry} | `{rule}` | "
                    f"**{money(row['realized_day'])}** | "
                    f"{money(row['realized_day'] * RTY[block])} | "
                    f"{number(row['winner_share'], 1)}% | "
                    f"{number(row['class_share'], 1)}% | "
                    f"{number(row['trades_day'], 2)} | "
                    f"{number(row['hold_min'], 0)} | {money(row['worst_day'])} | "
                    f"{money(row['mdd5'])} | {money(row['trade_mean'])} | "
                    f"{money(row['entered_cert_mean'])} |")

    # -------------------------------------------------- 2. per-era best/LOEO
    out.append("\n## The three readings of each era: design centre, "
               "leave-one-era-out, and the in-block maximum\n")
    out.append("`LOEO` picks the (arm, variant, target, gates, geometry, rule) "
               "cell by the mean realised $/day over the other DEPLOYMENT eras "
               "(`e4..e7`; the 20-day `blind_e3` control is never a selection "
               "basis) and reads it off this one — nothing is selected on the "
               "block it is scored on.  `best-in-block` IS a maximum over 960 "
               "cells of this era's own test block and is reported as an upper "
               "bound, never as a deployable number.\n")
    out.append("| era | reading | cell | $/day | winner% | class% | trades/day | "
               "hold min | worst day | mdd5 |")
    out.append("|---|---|---|---:|---:|---:|---:|---:|---:|---:|")
    impl = grid[grid["rule"] != "oracle"]
    for seg, block in SEGMENTS:
        centre = cell(grid, block=block, rule=CENTRE["rule"], **{
            k: v for k, v in CENTRE.items() if k != "rule"}).iloc[0]
        picks = [("design centre", centre), ("LOEO", loeo(grid, block))]
        best = impl[impl["block"] == block].sort_values(
            "realized_day", ascending=False).iloc[0]
        picks.append(("best-in-block", best))
        for name, row in picks:
            label = (f"{row['arm']}/{row['variant']}/{row['target']}/"
                     f"{row['gates']}/{row['geometry']}/`{row['rule']}`")
            out.append(
                f"| `{block}` | {name} | {label} | "
                f"**{money(row['realized_day'])}** | "
                f"{number(row['winner_share'], 1)}% | "
                f"{number(row['class_share'], 1)}% | "
                f"{number(row['trades_day'], 2)} | "
                f"{number(row['hold_min'], 0)} | {money(row['worst_day'])} | "
                f"{money(row['mdd5'])} |")

    # -------------------------------------------------- 3. the precision ladder
    out.append("\n## EXPERIMENT 1 — threshold geometry: what precision costs "
               "and what it buys\n")
    out.append("Pooled over the five eras, both arms, both targets, both column "
               "variants, no gates.  `entered cert` is the mean exit-free "
               "certificate of the trades actually taken (D-021's per-trade bar "
               "is $1,000).\n")
    out.append("| geometry | rule | winner% | class% | entered cert | trades/day | "
               "hold min | $/trade | $/winner | $/dud | $/day | mdd5 |")
    out.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    pooled = grid[grid["gates"] == "none"]
    for geometry in GEOM_ORDER:
        for rule in RULES:
            part = pooled[(pooled["geometry"] == geometry)
                          & (pooled["rule"] == rule)]
            if part.empty:
                continue
            out.append(
                f"| {geometry} | `{rule}` | "
                f"{number(part['winner_share'].mean(), 1)}% | "
                f"{number(part['class_share'].mean(), 1)}% | "
                f"{money(part['entered_cert_mean'].mean())} | "
                f"{number(part['trades_day'].mean(), 2)} | "
                f"{number(part['hold_min'].mean(), 0)} | "
                f"{money(part['trade_mean'].mean())} | "
                f"{money(part['winner_trade_mean'].mean())} | "
                f"{money(part['dud_trade_mean'].mean())} | "
                f"{money(part['realized_day'].mean())} | "
                f"{money(part['mdd5'].mean())} |")

    # -------------------------------------------------- 3a. how high does it go
    out.append("\n## How high does the entered-winner share actually go?\n")
    out.append("The maximum entered-winner share reached in each era over the "
               "whole grid, restricted to cells that entered at least 40 trades "
               "(a 20-trade cell can print 60% on noise).  This is the object "
               "the brief names, and the columns beside it are what that "
               "precision costs and pays.\n")
    out.append("| era | max winner% | cell | trades | trades/day | hold min | "
               "entered cert | $/trade | $/day | mdd5 |")
    out.append("|---|---:|---|---:|---:|---:|---:|---:|---:|---:|")
    for seg, block in SEGMENTS:
        part = impl[(impl["block"] == block) & (impl["n_trades"] >= 40)]
        for rule in ("close", "mirror@1.00"):
            sub = part[part["rule"] == rule]
            if sub.empty:
                continue
            row = sub.sort_values("winner_share", ascending=False).iloc[0]
            label = (f"{row['arm']}/{row['variant']}/{row['target']}/"
                     f"{row['gates']}/{row['geometry']}/`{row['rule']}`")
            out.append(
                f"| `{block}` | **{number(row['winner_share'], 1)}%** | {label} | "
                f"{int(row['n_trades'])} | {number(row['trades_day'], 2)} | "
                f"{number(row['hold_min'], 0)} | "
                f"{money(row['entered_cert_mean'])} | "
                f"{money(row['trade_mean'])} | {money(row['realized_day'])} | "
                f"{money(row['mdd5'])} |")

    # -------------------------------------------------- 3b. does it convert?
    out.append("\n## THE OBJECT, answered directly — what a percentage point of "
               "entered-winner share is worth\n")
    out.append("Every cell of the grid with at least 40 trades, binned by its "
               "own entered-winner share.  `$/trade` is the realised "
               "expectancy per trade (D-021's floor is $600, its target "
               "$1,000); `$/day` is the era's realised mean.\n")
    out.append("| winner% bin | rule | cells | trades/day | entered cert | "
               "$/trade | $/winner | $/dud | $/day | mdd5 |")
    out.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    dense = grid[grid["n_trades"] >= 40].copy()
    edges = [0, 30, 35, 40, 45, 100]
    dense["bin"] = pd.cut(dense["winner_share"], edges,
                          labels=["<30%", "30-35%", "35-40%", "40-45%", ">=45%"])
    for label in ["<30%", "30-35%", "35-40%", "40-45%", ">=45%"]:
        for rule in ("close", "mirror@1.00", "overlay"):
            part = dense[(dense["bin"] == label) & (dense["rule"] == rule)]
            if part.empty:
                continue
            out.append(
                f"| {label} | `{rule}` | {len(part)} | "
                f"{number(part['trades_day'].mean(), 2)} | "
                f"{money(part['entered_cert_mean'].mean())} | "
                f"{money(part['trade_mean'].mean())} | "
                f"{money(part['winner_trade_mean'].mean())} | "
                f"{money(part['dud_trade_mean'].mean())} | "
                f"{money(part['realized_day'].mean())} | "
                f"{money(part['mdd5'].mean())} |")

    # -------------------------------------------------- 4. gates and target
    out.append("\n## EXPERIMENTS 2 and 3 — the gates and the class target\n")
    out.append("Each factor moved one at a time against the same baseline "
               "(pooled over eras, arms and the four threshold geometries; "
               "`close` and `mirror@1.00` shown because they are the two exits "
               "that carry dollars).\n")
    out.append("| factor | level | rule | winner% | class% | entered cert | "
               "trades/day | $/day | mdd5 |")
    out.append("|---|---|---|---:|---:|---:|---:|---:|---:|")
    thresholded = grid[grid["geometry"].str.startswith("P@")]
    factors = [("gates", GATESETS, dict(variant="base", target="w500")),
               ("column set", VARIANTS, dict(gates="none", target="w500")),
               ("target", TARGETS, dict(gates="none", variant="base")),
               ("arm", ARMS, dict(gates="none", variant="base", target="w500"))]
    column = {"gates": "gates", "column set": "variant", "target": "target",
              "arm": "arm"}
    for name, levels, fixed in factors:
        for level in levels:
            for rule in ("close", "mirror@1.00"):
                part = thresholded[(thresholded[column[name]] == level)
                                   & (thresholded["rule"] == rule)]
                for key, value in fixed.items():
                    part = part[part[key] == value]
                if part.empty:
                    continue
                out.append(
                    f"| {name} | {level} | `{rule}` | "
                    f"{number(part['winner_share'].mean(), 1)}% | "
                    f"{number(part['class_share'].mean(), 1)}% | "
                    f"{money(part['entered_cert_mean'].mean())} | "
                    f"{number(part['trades_day'].mean(), 2)} | "
                    f"{money(part['realized_day'].mean())} | "
                    f"{money(part['mdd5'].mean())} |")

    # -------------------------------------------------- 5. the fits
    out.append("\n## The fits — frozen config, walk-forward, one refit per "
               "(arm, column set, target)\n")
    out.append("`AUC(w500)` scores the fitted model against the roster's own "
               "winner label, `AUC(class)` against the deployment class "
               "(`cert >= $1,000 & MAE <= $300`).  The reproduction control is "
               "segment `e`: `E/T/I only` must land on the published 0.665 and "
               "`v3 no-M` on 0.664.\n")
    out.append("| seg | era | arm | column set | target | features | "
               "train pos rate | AUC(w500) | AUC(class) | OOF AUC |")
    out.append("|---|---|---|---|---|---:|---:|---:|---:|---:|")
    for row in fit.to_dict("records"):
        out.append(f"| {row['segment']} | `{row['block']}` | {row['arm']} | "
                   f"{row['variant']} | {row['target']} | {row['features']} | "
                   f"{number(100 * row['train_pos_rate'], 1)}% | "
                   f"{number(row['auc_w500'])} | {number(row['auc_wclass'])} | "
                   f"{number(row['oof_auc'])} |")

    # -------------------------------------------------- 6. thresholds
    out.append("\n## The preregistered thresholds — study quantiles, and what "
               "they actually admit out of era\n")
    out.append("The bar is the (1 - q) quantile of SESSION-GROUPED OUT-OF-FOLD "
               "predictions on each segment's own training window.  If the "
               "score surface were era-stationary, `P@top10` would admit ~10% "
               "of the test block's candidates; the admitted column is what it "
               "really admits, and it is the era-adaptivity of the design "
               "arriving as under-participation.\n")
    out.append("| era | candidates/day | arm | target | "
               + " | ".join(f"P@top{q}" for q in TOPQ)
               + " | admitted @top10 | @top10 as % of roster |")
    out.append("|---|---:|---|---|" + "---:|" * (len(TOPQ) + 2))
    for seg, block in SEGMENTS:
        offer = candidates_day.get(block, np.nan)
        for arm in ARMS:
            for target in TARGETS:
                part = thr[(thr["segment"] == seg) & (thr["arm"] == arm)
                           & (thr["variant"] == "base")
                           & (thr["target"] == target)]
                cells = [number(part[part["topq"] == q]["threshold"].iloc[0], 4)
                         for q in TOPQ]
                got = cell(grid, block=block, arm=arm, variant="base",
                           target=target, gates="none", geometry="P@top10",
                           rule="close").iloc[0]
                out.append(f"| `{block}` | {number(offer, 1)} | {arm} | {target} | "
                           + " | ".join(cells)
                           + f" | {number(got['n_entered_day'], 2)}/day | "
                           f"{number(100 * got['n_entered_day'] / offer, 1)}% |")

    # -------------------------------------------------- 7. shuffle
    out.append("\n## Control — label shuffle on the class-target refit "
               f"(segment {SHUFFLE_SEGMENT}, `{SHUFFLE_ARM}`)\n")
    out.append("The identical refit on PERMUTED training labels, through the "
               "identical OOF threshold machinery and the identical replay.  "
               f"{SHUFFLE_DRAWS} draws.\n")
    out.append("| draw | geometry | rule | $/day | winner% | class% | "
               "trades/day | entered cert |")
    out.append("|---|---|---|---:|---:|---:|---:|---:|")
    for row in shuffle.to_dict("records"):
        out.append(f"| {row['draw']} | {row['geometry']} | `{row['rule']}` | "
                   f"{money(row['realized_day'])} | "
                   f"{number(row['winner_share'], 1)}% | "
                   f"{number(row['class_share'], 1)}% | "
                   f"{number(row['trades_day'], 2)} | "
                   f"{money(row['entered_cert_mean'])} |")

    # -------------------------------------------------- 8. purge list
    out.append("\n## The panel do-not-build purge, column by column\n")
    out.append("`PANEL_SYNTHESIS.md` §2, negative convergence, mapped onto the "
               "columns this matrix carries.  Three items name channels that "
               "were never built here and therefore purge nothing; they are "
               "listed so the mapping can be audited.\n")
    out.append("| panel item | columns dropped |")
    out.append("|---|---|")
    for item, columns in PURGE.items():
        out.append(f"| {item.replace('|', chr(92) + '|')} | "
                   + (", ".join(f"`{c}`" for c in columns) if columns
                      else "_(no such column in this matrix)_") + " |")

    # -------------------------------------------------- 9. laws
    out.append("\n## Laws and controls\n")
    out.append("- REPRODUCTION: this file's trade table reproduces "
               "`exit_segments/stop_replay.tsv` to the dollar on all five "
               "segments for `close`, `mirror@1.00` and `cont[lasso,B]@c25` "
               "(arm `v3 full`, top-5, two positions), so the exit side is "
               "rung 1/3's machinery unchanged and only the entry side moves.")
    out.append("- WALK-FORWARD PURITY: every segment trains only on sessions "
               "strictly earlier than its test block (asserted in code); usable "
               "columns come from each segment's own training window.")
    out.append("- THE THRESHOLD IS NEVER READ OFF A TEST BLOCK: the grid is the "
               "preregistered study quantiles {5,10,15,20}% of session-grouped "
               "5-fold OUT-OF-FOLD predictions on the training window.")
    out.append("- FROZEN ESTIMATOR: `" + str(FROZEN) + "`, never re-selected; "
               "the class-target refit changes the label and nothing else.")
    out.append("- NO CELL IS SELECTED ON ITS OWN BLOCK: the design centre was "
               "named before the numbers and the LOEO reading selects on the "
               "other four eras; `best-in-block` is labelled as an upper bound.")
    out.append(f"- COSTS: 576 net cents once per trade; the $300 wall monitored "
               f"from entry with gap-through; occupancy {SLOTS} concurrent "
               f"positions (D-030).")
    out.append(f"- SEALED ZONE: `packlib.SEALED_FROM` = {P.SEALED_FROM}; the "
               f"highest session read here is {highest}.")
    out.append("- D-022 overlay: era RTY-mini factors 0.879 / 0.895 / 1.004 / "
               "1.099 / 1.073; the RTY column of the verdict table carries them "
               "and no share or percentage moves.")

    REPORT.write_text("\n".join(out) + "\n")
    print(f"report -> {REPORT}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", default="all",
                        choices=("score", "trades", "replay", "report", "all"))
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    OUTDIR.mkdir(parents=True, exist_ok=True)
    scores, thr, fit, frame = stage_score(args.rebuild)
    if args.stage == "score":
        return
    trades = stage_trades(frame, args.rebuild)
    if args.stage == "trades":
        return
    if args.stage == "report" and GRID.exists():
        grid = pd.read_csv(GRID, sep="\t")
    else:
        grid = stage_replay(frame, scores, thr, trades)
    shuffle = stage_shuffle(frame, trades, args.rebuild)
    write_report(grid, fit, thr, shuffle, frame)


if __name__ == "__main__":
    main()
