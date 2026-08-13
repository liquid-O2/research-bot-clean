#!/usr/bin/env python3
"""exit_rung4.py — RUNG 4 of the exit program: EXITS THAT REUSE THE ENTRY MODEL.

D-046 SCOPE CORRECTION.  Rungs 1-3 falsified the POST-ENTRY STATE at minute
grain (a price-symmetric mirror rule, a barrier probability, a continuation
valuation).  None of them tried the two formulations the charter names, both of
which spend the ENTRY model's intelligence instead of learning a new object:

  A  MODEL-MIRROR EXIT.  Holding a LONG opened at candidate c, exit at the
     first second at which ANY SHORT-side roster candidate of the same session
     scores above the arm's own study bar — i.e. our highest-precision detector
     firing the OPPOSITE side IS the exit signal.  (Rung 1 mirrored the raw
     ZigZag; this mirrors the MODEL.)  Symmetric for shorts.
  B  CLASS-CONDITIONAL EXIT.  The arm's entry-time P selects the exit STYLE per
     trade: P in the study top decile => hold to close (winners build); P below
     => a time stop at 30 or 60 minutes (duds bleed).
  A+B  the hold-class gets A instead of hold-to-close.

D-046 also withdraws every two-position framing: this file replays ONE
POSITION AT A TIME, one mini, and measures against $2,000/session.

STRICT PRIORITY.  The opposite-side score of a candidate exists AT THAT
CANDIDATE'S OWN DECISION SECOND (its features are computed there; the model is
fit strictly on earlier sessions), so an exit stamped at that second reads
nothing from the future.  The study bars (top-quartile / top-decile) are
quantiles of SESSION-GROUPED OUT-OF-FOLD predictions on each segment's own
TRAINING window and never touch a test block.

PREREGISTERED GRID — every cell reported, nothing selected on a test block:

    eras     blind_e3 (control), e4, e5, e6, e7      (era_retest segments e..i)
    arms     `E/T/I only`, `v3 no-M`
    streams  top-3, top-5, threshold P@top10, threshold P@top20
    rules    close | mirror@1.00 | mirror@1.00+patience15 | oracle          (carried)
             mmirror@{10,20,25}                                            (A, immediate)
             mmirror@{10,20,25}+patience15                                 (A, age floor)
             mmirror@{10,20,25}+prof                                       (A, profit-only)
             class[30] | class[60]                                         (B)
             class[30]+mmirror@25 | class[60]+mmirror@25                   (A+B)
    overlay  `cont[lasso,B]@c25` ON (the brief's configuration, D-021 keeper)
             and OFF (the basis every prior rung reported on)
    shuffle  A: opposite-fire TIMES permuted within (session, arm, side)
             B: entry-P permuted within (session, arm); 3 draws each

MONEY.  `qr_labels/money.hpp` via `exit_engine.net_cent`: 576 net cents charged
ONCE per trade on the $100,000 object.  The $300 wall is monitored from entry
for every rule and fills at the next lawful mark strictly after the crossing
(gap-through).  Marks are the 1s grid's carried mids.

    exit_rung4.py [--stage thresholds|replay|report|all] [--rebuild]
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
import precision as pr                                    # noqa: E402

ROOT = P.ROOT
MATRIX = ROOT / "FEATURES_ERA.tsv"
OUTDIR = ROOT / "rung4_segments"
REPORT = ROOT / "EXIT_RUNG4_REPORT.md"
VERDICT = ROOT / "EXIT_RUNG4_VERDICT.md"

SCORES = ROOT / "precision_segments" / "precision_scores.tsv"
PUB_THRESH = ROOT / "precision_segments" / "precision_thresholds.tsv"
TRADES_PUB = ROOT / "precision_segments" / "precision_trades.tsv"
STOP_PREDS = ROOT / "exit_segments" / "stop_preds.tsv"
PICKS = ROOT / "exit_segments" / "picks.tsv"

THRESH = OUTDIR / "rung4_thresholds.tsv"
CELLS = OUTDIR / "rung4_cells.tsv"
ANATOMY = OUTDIR / "rung4_anatomy.tsv"
TRADES = OUTDIR / "rung4_trades.tsv"
DIST = OUTDIR / "rung4_distribution.tsv"
CONTROL = OUTDIR / "rung4_controls.tsv"

SEGMENTS = er.SEGMENTS
ARMS = ("E/T/I only", "v3 no-M")
SEED = dm.SEED
FROZEN = wf.FROZEN
CV_FOLDS = 5
RTY = pr.RTY
OFFSETS = esm.OFFSETS

# ---- preregistered constants, fixed before any number was computed ---------
#: the study quantiles: 25 = the charter's TOP QUARTILE bar for formulation A;
#: 10 = the top DECILE that splits formulation B's classes; 5/15/20 carried so
#: the published `precision_thresholds.tsv` is reproduced as a control.
QUANTILES = (5, 10, 15, 20, 25)
MIRROR_BARS = (10, 20, 25)              # A's opposite-fire bars, all reported
CLASS_DECILE = 10                       # B's hold/stop split
CHARTER_BAR = 25                        # the bar A+B uses
TIME_STOPS = (30, 60)                   # B's preregistered stops, minutes
PATIENCE_S = ee.PATIENCE_FLOOR_S        # 15 min, rung 1's semantics
STREAM_Q = (10, 20)                     # the precision lane's threshold streams
TOPK = (3, 5)
WINNER_CERT = 500.0
OVERLAY_COLUMN = "p_lasso_B_c25"
OVERLAY_COST = 25.0
SHUFFLE_DRAWS = 3
SLOTS = 1                               # D-046: ONE position, ONE mini

RULES_CARRIED = ("close", "mirror@1.00", "mirror@1.00+patience15", "oracle")
RULES_A = (tuple(f"mmirror@{q}" for q in MIRROR_BARS)
           + tuple(f"mmirror@{q}+patience15" for q in MIRROR_BARS)
           + tuple(f"mmirror@{q}+prof" for q in MIRROR_BARS))
RULES_B = tuple(f"class[{h}]" for h in TIME_STOPS)
RULES_AB = tuple(f"class[{h}]+mmirror@{CHARTER_BAR}" for h in TIME_STOPS)
RULES = RULES_CARRIED + RULES_A + RULES_B + RULES_AB
SHUF_RULES = (tuple(f"shufA{d}@{CHARTER_BAR}" for d in range(1, SHUFFLE_DRAWS + 1))
              + tuple(f"shufB{d}[{TIME_STOPS[0]}]"
                      for d in range(1, SHUFFLE_DRAWS + 1)))
ALL_RULES = RULES + SHUF_RULES
#: the prior implementables this rung must beat, ONE position, same streams
PRIOR = ("close", "mirror@1.00", "mirror@1.00+patience15", "overlay-close")


# ==========================================================================
# 1 — the study bars: session-grouped OOF quantiles on each training window
# ==========================================================================

def oof_scores(train: pd.DataFrame, columns: list, y: np.ndarray) -> np.ndarray:
    """`precision.oof_scores`, unchanged: the bar must be a quantile of an
    OUT-OF-FOLD training-window prediction, never of an in-sample one."""
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


def stage_thresholds(rebuild: bool) -> pd.DataFrame:
    if not rebuild and THRESH.exists():
        frame = pd.read_csv(THRESH, sep="\t")
        print(f"thresholds {frame.shape} <- {THRESH}", flush=True)
        return frame
    matrix = pd.read_csv(MATRIX, sep="\t", low_memory=False)
    print(f"matrix {matrix.shape} <- {MATRIX}", flush=True)
    rows = []
    for seg, block in SEGMENTS:
        test = matrix[matrix["block"] == block].reset_index(drop=True)
        train = matrix[matrix["session"] < int(test["session"].min())] \
            .reset_index(drop=True)
        assert train["session"].max() < test["session"].min(), "walk-forward purity"
        sets = er.arm_columns(matrix, train)
        y = train["winner"].to_numpy().astype(int)
        for arm in ARMS:
            columns = sets[arm]
            oof = oof_scores(train, columns, y)
            finite = oof[np.isfinite(oof)]
            for q in QUANTILES:
                rows.append({"segment": seg, "block": block, "arm": arm,
                             "topq": q,
                             "threshold": float(np.quantile(finite, 1 - q / 100.0)),
                             "train_rows": len(train), "features": len(columns)})
            print(f"  {seg} {arm:12s} {len(columns):4d} cols  "
                  f"bar25={rows[-1]['threshold']:.4f}", flush=True)
    frame = pd.DataFrame(rows)
    OUTDIR.mkdir(parents=True, exist_ok=True)
    frame.to_csv(THRESH, sep="\t", index=False)
    return frame


# ==========================================================================
# 2 — the replay
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


class Trade:
    """One candidate's lawful marks, wall and entry geometry — rule-free."""

    __slots__ = ("cid", "second", "side", "cert", "winner", "start", "limit",
                 "wall_fill", "entry_second", "nets", "close_pos")

    def __init__(self, session: ee.Session, row: dict):
        self.cid = row["id"]
        self.second = int(row["second"])
        self.side = row["side"]
        self.cert = float(row["cert"])
        self.winner = int(row["cert"] >= WINNER_CERT)
        self.start = session.position(self.second)
        self.entry_second = int(session.second[self.start])
        self.nets = ee.net_cent(int(session.mid[self.start]), session.mid, self.side)
        self.close_pos = session.close_pos
        forward = np.flatnonzero(self.nets[self.start + 1:] <= ee.WALL_NET_CENT)
        self.wall_fill = (min(int(forward[0]) + self.start + 2, self.close_pos)
                          if forward.size else None)
        self.limit = self.wall_fill if self.wall_fill is not None else self.close_pos


def first_fire(fires: np.ndarray, after: int) -> int | None:
    index = int(np.searchsorted(fires, after, "right"))
    return int(fires[index]) if index < len(fires) else None


def overlay_position(session: ee.Session, trade: Trade, marks: dict) -> int:
    """The `cont[lasso,B]@c25` exit: the first preregistered offset whose
    predicted continuation is below $25.  Missing predictions abstain."""
    for offset in OFFSETS:
        value = marks.get(offset)
        if value is None:
            continue
        pos = session.position(trade.second + offset * 60)
        if pos <= trade.start or pos >= trade.limit:
            continue
        if value < OVERLAY_COST:
            return pos
    return trade.limit


def rule_position(session: ee.Session, trade: Trade, rule: str,
                  fires: dict, high: dict) -> int:
    """The exit POSITION of one rule, before the wall and the overlay."""
    close_pos = trade.close_pos
    if rule == "close":
        return close_pos
    if rule == "oracle":
        window = trade.nets[trade.start + 1:trade.limit + 1]
        if not window.size:
            return trade.limit
        best = int(np.argmax(window)) + trade.start + 1
        return best if trade.nets[best] > 0 else trade.limit

    if rule.startswith("mirror@1.00"):
        hit = session.mirror_second(1.00, trade.side, trade.entry_second)
        second = hit if hit is not None else int(session.second[close_pos])
        if rule.endswith("+patience15"):
            second = max(second, trade.entry_second + PATIENCE_S)
        return session.position(second)

    if rule.startswith("mmirror@"):
        bar = int(rule.split("@", 1)[1].split("+", 1)[0])
        return mmirror_position(session, trade, fires[bar],
                                patience=rule.endswith("+patience15"),
                                profit_only=rule.endswith("+prof"))

    if rule.startswith("class[") or rule.startswith("shufB"):
        hold = int(rule.split("[", 1)[1].split("]", 1)[0])
        key = "real" if rule.startswith("class[") else rule[:6]
        if high[key][trade.cid]:
            if "+mmirror@" in rule:
                bar = int(rule.split("+mmirror@", 1)[1])
                return mmirror_position(session, trade, fires[bar])
            return close_pos
        return session.position(trade.entry_second + hold * 60)

    if rule.startswith("shufA"):
        bar = int(rule.split("@", 1)[1])
        return mmirror_position(session, trade, fires[(rule[:6], bar)])

    raise ValueError(rule)


def mmirror_position(session: ee.Session, trade: Trade, side_fires: dict,
                     patience: bool = False, profit_only: bool = False) -> int:
    """A's exit: the first opposite-SIDE model fire strictly after entry."""
    opposite = "S" if trade.side == "L" else "L"
    fires = side_fires[opposite]
    if profit_only:
        index = int(np.searchsorted(fires, trade.entry_second, "right"))
        while index < len(fires):
            pos = session.position(int(fires[index]))
            if pos > trade.start and trade.nets[min(pos, trade.limit)] > 0:
                return pos
            index += 1
        return trade.close_pos
    hit = first_fire(fires, trade.entry_second)
    second = hit if hit is not None else int(session.second[trade.close_pos])
    if patience:
        second = max(second, trade.entry_second + PATIENCE_S)
    return session.position(second)


def settle(trade: Trade, session: ee.Session, rule_pos: int,
           overlay_pos: int | None) -> dict:
    pos = rule_pos if overlay_pos is None else min(rule_pos, overlay_pos)
    exit_pos = min(pos, trade.limit)
    stopped = (trade.wall_fill is not None and exit_pos == trade.wall_fill
               and trade.wall_fill <= pos)
    return {"exit_second": int(session.second[exit_pos]),
            "pnl": float(trade.nets[exit_pos]) / 100.0,
            "stopped": bool(stopped),
            "hold_s": int(session.second[exit_pos]) - trade.entry_second,
            "cert": trade.cert, "winner": trade.winner, "id": trade.cid,
            "second": trade.second}


def occupancy_day(exits: dict, picks: list) -> tuple:
    """ONE position at a time, chronological (D-046).  `exit_engine.replay_day`
    with SLOTS=1 — identical admission test, kept byte-for-byte."""
    total, taken, busy = 0.0, [], -1
    for pick in sorted(picks, key=lambda row: (row["second"], row["id"])):
        if pick["second"] < busy:
            continue
        trade = exits[pick["id"]]
        total += trade["pnl"]
        taken.append(trade)
        busy = trade["exit_second"]
    return total, taken


def stage_replay(bars: pd.DataFrame) -> tuple:
    scores = pd.read_csv(SCORES, sep="\t")
    roster = pd.read_csv(TRADES_PUB, sep="\t").drop_duplicates(
        ["segment", "session", "id"])[
        ["segment", "block", "session", "id", "second", "side", "cert",
         "cert_mae", "winner"]]
    roster = roster.merge(scores, on=["segment", "block", "session", "id"],
                          how="left", validate="one_to_one")
    for arm in ARMS:
        assert roster[f"{arm}|base|w500"].notna().all(), f"scores missing for {arm}"
    overlay = overlay_lookup()
    bar_of = {(row.segment, row.arm, row.topq): row.threshold
              for row in bars.itertuples(index=False)}

    #: `ee.Session` builds a confirmed-pivot ladder per entry in this tuple.
    #: Only the 1.00 ladder is used here (rung 1's `mirror@1.00` baseline); the
    #: 0.75/1.50 ladders were rung 1's multiplier grid and are not in this
    #: brief, so they are not built.  The reproduction control below proves the
    #: 1.00 ladder is unchanged.
    ee.MIRROR_MULTIPLIERS = (1.00,)

    rng = np.random.default_rng(SEED)
    cells, trade_rows, controls, anatomy = [], [], [], []
    covered = total = 0
    repro, stream_repro = [], []
    published_trades = pd.read_csv(TRADES_PUB, sep="\t")
    published_trades = {(int(r.session), r.id, r.rule): float(r.pnl)
                        for r in published_trades.itertuples(index=False)}
    published_picks = pd.read_csv(PICKS, sep="\t")
    published_picks = {(arm, k): set(zip(
        published_picks[(published_picks["arm"] == arm)
                        & (published_picks["k"] == k)]["session"],
        published_picks[(published_picks["arm"] == arm)
                        & (published_picks["k"] == k)]["id"]))
        for arm in ARMS for k in TOPK}
    REPRO_MAP = {("close", 0): "close", ("mirror@1.00", 0): "mirror@1.00",
                 ("oracle", 0): "oracle", ("close", 1): "overlay",
                 ("mirror@1.00", 1): "mirror+overlay"}

    for seg, block in SEGMENTS:
        part = roster[roster["segment"] == seg]
        sessions = sorted(part["session"].unique())
        print(f"segment {seg} ({block}): {len(sessions)} sessions, "
              f"{len(part)} candidates", flush=True)
        #: accumulators {(arm, stream, rule, overlay): ([day $], [trades])}
        acc, picked = {}, {}
        for done, ordinal in enumerate(sessions, 1):
            session = ee.Session(int(ordinal), block)
            rows = part[part["session"] == ordinal].to_dict("records")
            trades = {row["id"]: Trade(session, row) for row in rows}
            marks = {row["id"]: overlay.get((int(ordinal), row["id"])) for row in rows}
            covered += sum(1 for v in marks.values() if v)
            total += len(rows)
            over_pos = {cid: (overlay_position(session, trade, marks[cid] or {}))
                        for cid, trade in trades.items()}

            for arm in ARMS:
                column = f"{arm}|base|w500"
                score = {row["id"]: float(row[column]) for row in rows}
                #: --- the fire ladders (A) and the class split (B) ----------
                fires = {}
                for q in MIRROR_BARS:
                    bar = bar_of[(seg, arm, q)]
                    fires[q] = {
                        s: np.array(sorted(int(r["second"]) for r in rows
                                           if r["side"] == s
                                           and score[r["id"]] >= bar),
                                    dtype=np.int64)
                        for s in ("L", "S")}
                decile = bar_of[(seg, arm, CLASS_DECILE)]
                high = {"real": {cid: score[cid] >= decile for cid in score}}

                #: --- the shuffles ------------------------------------------
                for draw in range(1, SHUFFLE_DRAWS + 1):
                    #: A: permute the opposite-fire TIMES within (session, side)
                    key = (f"shufA{draw}", CHARTER_BAR)
                    bar = bar_of[(seg, arm, CHARTER_BAR)]
                    permuted = {}
                    for s in ("L", "S"):
                        seconds = np.array(sorted(int(r["second"]) for r in rows
                                                  if r["side"] == s), dtype=np.int64)
                        n_fire = int(sum(1 for r in rows if r["side"] == s
                                         and score[r["id"]] >= bar))
                        pick = (rng.permutation(len(seconds))[:n_fire]
                                if len(seconds) else np.zeros(0, dtype=int))
                        permuted[s] = np.array(sorted(seconds[pick]), dtype=np.int64)
                    fires[key] = permuted
                    #: B: permute entry-P within the session
                    ids = list(score)
                    values = rng.permutation(np.array([score[c] for c in ids]))
                    high[f"shufB{draw}"] = {c: bool(v >= decile)
                                            for c, v in zip(ids, values)}

                #: --- every rule's exit for every candidate -----------------
                exits = {}
                for rule in ALL_RULES:
                    off, on = {}, {}
                    for cid, trade in trades.items():
                        pos = rule_position(session, trade, rule, fires, high)
                        off[cid] = settle(trade, session, pos, None)
                        if rule in RULES:
                            on[cid] = settle(trade, session, pos, over_pos[cid])
                    exits[(rule, 0)] = off
                    if rule in RULES:
                        exits[(rule, 1)] = on
                    #: reproduction control — these five rules do not depend on
                    #: the arm and must land on `precision_trades.tsv` to the
                    #: cent, which is what makes this rung's replay the SAME
                    #: machinery as rungs 1/3 and the precision lane
                    if arm == ARMS[0]:
                        for ov, name in ((0, REPRO_MAP.get((rule, 0))),
                                         (1, REPRO_MAP.get((rule, 1)))):
                            if name is None:
                                continue
                            table = off if ov == 0 else on
                            for cid, t in table.items():
                                want = published_trades.get((int(ordinal), cid, name))
                                if want is not None:
                                    repro.append(abs(t["pnl"] - want))

                #: --- the OCCUPANCY-FREE anatomy: what each formulation does
                #: to EVERY candidate, so the failure is diagnosed on the
                #: population and not only on the trades occupancy admitted
                for cid, trade in trades.items():
                    anatomy.append({
                        "segment": seg, "block": block, "session": int(ordinal),
                        "id": cid, "arm": arm, "side": trade.side,
                        "cert": trade.cert, "winner": trade.winner,
                        "p": score[cid], "high_p": int(high["real"][cid]),
                        "fires25": int(score[cid]
                                       >= bar_of[(seg, arm, CHARTER_BAR)]),
                        "pnl_close": exits[("close", 0)][cid]["pnl"],
                        #: the UNCONDITIONAL time stops, on every candidate,
                        #: so B's split can be read against its own alternative
                        "pnl_stop30": settle(trade, session, session.position(
                            trade.entry_second + TIME_STOPS[0] * 60), None)["pnl"],
                        "pnl_stop60": settle(trade, session, session.position(
                            trade.entry_second + TIME_STOPS[1] * 60), None)["pnl"],
                        "pnl_mm25": exits[(f"mmirror@{CHARTER_BAR}", 0)][cid]["pnl"],
                        "hold_mm25": exits[(f"mmirror@{CHARTER_BAR}", 0)][cid]["hold_s"],
                        "hold_close": exits[("close", 0)][cid]["hold_s"],
                        "pnl_oracle": exits[("oracle", 0)][cid]["pnl"]})

                #: --- the pick streams --------------------------------------
                streams = {}
                order = sorted(rows, key=lambda r: (-score[r["id"]], r["id"]))
                for k in TOPK:
                    streams[f"top{k}"] = order[:k]
                    mine = {(int(ordinal), r["id"]) for r in order[:k]}
                    stream_repro.append(
                        len(mine & published_picks[(arm, k)]) - len(mine))
                for q in STREAM_Q:
                    bar = bar_of[(seg, arm, q)]
                    streams[f"thr{q}"] = [r for r in rows if score[r["id"]] >= bar]

                for stream, picks in streams.items():
                    for (rule, ov), table in exits.items():
                        key = (arm, stream, rule, ov)
                        day, taken = occupancy_day(table, picks)
                        acc.setdefault(key, ([], []))
                        acc[key][0].append(day)
                        acc[key][1].extend(taken)
                        if ov == 0:
                            for t in taken:
                                trade_rows.append({
                                    "segment": seg, "block": block,
                                    "session": int(ordinal), "arm": arm,
                                    "stream": stream, "rule": rule,
                                    "id": t["id"], "cert": t["cert"],
                                    "winner": t["winner"], "pnl": t["pnl"],
                                    "hold_s": t["hold_s"],
                                    "stopped": int(t["stopped"])})
                    picked.setdefault((arm, stream), []).append(
                        sum(float(r["cert"]) for r in picks))

            if done % 25 == 0 or done == len(sessions):
                print(f"  {done}/{len(sessions)} sessions", flush=True)

        for (arm, stream, rule, ov), (days, taken) in acc.items():
            cells.append({"segment": seg, "block": block,
                          "era_label": er.ERA_LABEL[block], "arm": arm,
                          "stream": stream, "rule": rule, "overlay": ov,
                          "rty_f": RTY[block],
                          **summarise(days, taken,
                                      float(np.mean(picked[(arm, stream)])))})
    controls.append({"control": "overlay coverage",
                     "value": f"{covered}/{total} candidates carry a "
                              f"`{OVERLAY_COLUMN}` prediction set; the rest "
                              f"abstain (the overlay never fires on them)"})
    controls.append({
        "control": "replay reproduction vs `precision_trades.tsv`",
        "value": f"max |delta| ${max(repro) if repro else 0:.4f} over "
                 f"{len(repro)} (candidate, rule) realised P&Ls across "
                 f"close / mirror@1.00 / oracle / overlay / mirror+overlay"})
    controls.append({
        "control": "pick-stream reproduction vs `exit_segments/picks.tsv`",
        "value": f"{sum(1 for v in stream_repro if v == 0)}/{len(stream_repro)} "
                 f"(session, arm, k) top-k baskets identical"})
    pd.DataFrame(anatomy).to_csv(ANATOMY, sep="\t", index=False)
    return pd.DataFrame(cells), pd.DataFrame(trade_rows), controls


def summarise(days: list, trades: list, picked_day: float) -> dict:
    daily = np.array(days, dtype=float)
    pnl = np.array([t["pnl"] for t in trades], dtype=float) if trades else np.zeros(0)
    cert = np.array([t["cert"] for t in trades], dtype=float) if trades else np.zeros(0)
    entered = (cert.sum() / len(daily)) if daily.size else np.nan
    win = np.array([t["winner"] for t in trades], dtype=float) if trades else np.zeros(0)
    return {
        "days": len(daily),
        "trades": len(pnl),
        "realized_day": float(daily.mean()) if daily.size else np.nan,
        "picked_day": picked_day,
        "entered_cert_day": entered,
        "capture_pct": (100.0 * daily.mean() / picked_day) if picked_day else np.nan,
        "capture_entered_pct": (100.0 * daily.mean() / entered
                                if entered and np.isfinite(entered) else np.nan),
        "trade_mean": float(pnl.mean()) if pnl.size else np.nan,
        "trade_median": float(np.median(pnl)) if pnl.size else np.nan,
        "winner_share": (100.0 * float(win.mean())) if win.size else np.nan,
        "winner_trade_mean": (float(pnl[win == 1].mean()) if (win == 1).any()
                              else np.nan),
        "dud_trade_mean": (float(pnl[win == 0].mean()) if (win == 0).any()
                           else np.nan),
        "median_day": float(np.median(daily)) if daily.size else np.nan,
        "worst_day": float(daily.min()) if daily.size else np.nan,
        "best_day": float(daily.max()) if daily.size else np.nan,
        "worst_trade": float(pnl.min()) if pnl.size else np.nan,
        "best_trade": float(pnl.max()) if pnl.size else np.nan,
        "loss_days_pct": (100.0 * float((daily < 0).mean())) if daily.size else np.nan,
        "trades_day": (len(pnl) / len(daily)) if daily.size else np.nan,
        "win_rate": (100.0 * float((pnl > 0).mean())) if pnl.size else np.nan,
        "stop_rate": (100.0 * float(np.mean([t["stopped"] for t in trades])))
                     if trades else np.nan,
        "hold_min": (float(np.mean([t["hold_s"] for t in trades])) / 60.0)
                    if trades else np.nan,
        "pnl_ge_900_pct": (100.0 * float((pnl >= 900).mean())) if pnl.size else np.nan,
        "pnl_ge_600_pct": (100.0 * float((pnl >= 600).mean())) if pnl.size else np.nan,
    }


# ==========================================================================
# 3 — report
# ==========================================================================

def money(value) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    return f"-${abs(value):,.0f}" if value < 0 else f"${value:,.0f}"


def number(value, digits=1) -> str:
    return "n/a" if value is None or not np.isfinite(value) else f"{value:.{digits}f}"


def loeo(frame: pd.DataFrame, block: str, pool: tuple) -> pd.Series | None:
    """LEAVE-ONE-ERA-OUT selection: the cell with the best mean $/day over the
    OTHER four eras, read out on `block`.  No test block selects its own cell."""
    part = frame[(frame["overlay"] == 0) & (frame["rule"].isin(pool))]
    other = part[part["block"] != block]
    if other.empty:
        return None
    ranked = (other.groupby(["arm", "stream", "rule"])["realized_day"]
              .mean().sort_values(ascending=False))
    for (arm, stream, rule) in ranked.index:
        hit = part[(part["block"] == block) & (part["arm"] == arm)
                   & (part["stream"] == stream) & (part["rule"] == rule)]
        if not hit.empty:
            return hit.iloc[0]
    return None


def write_report(cells: pd.DataFrame, trades: pd.DataFrame,
                 bars: pd.DataFrame, controls: list) -> None:
    out = ["# EXIT RUNG 4 — MODEL-MIRROR AND CLASS-CONDITIONAL EXITS\n",
           "ONE position, ONE mini (D-046).  Exit rules that spend the ENTRY "
           "model's own intelligence: **A** exits when the model fires the "
           "OPPOSITE side above its study bar; **B** lets the entry-time P pick "
           "the exit style (top-decile holds to close, the rest gets a time "
           "stop); **A+B** gives the hold-class A.  Carried baselines: "
           "hold-to-close, `mirror@1.00` (rung 1), `oracle` (ceiling).  Every "
           "number is a REALISED dollar on the $100,000 object with the 576c "
           "round trip charged once and the $300 wall live.\n"]
    if VERDICT.exists():
        out.append("\n" + VERDICT.read_text().rstrip() + "\n")

    deployment = [b for _, b in SEGMENTS if b != "blind_e3"]

    # --- headline verdict table --------------------------------------------
    out.append("\n## VERDICT TABLE — best implementable cell per era, "
               "one position, overlay OFF\n")
    out.append("`prior` = the best of the rules carried from rungs 1-3 "
               "(`close`, `mirror@1.00`, `+patience15`, the `cont[lasso,B]@c25` "
               "overlay on hold-to-close) over the SAME streams and arms.  "
               "`new` = the best of formulations A / B / A+B.  Both columns are "
               "in-block maxima (upper bounds); the LOEO column selects the cell "
               "on the OTHER four eras only and reads it out here.\n")
    out.append("| era | prior best $/day | A/B best $/day | A/B best cell | "
               "LOEO A/B $/day | LOEO cell | oracle ceiling $/day | vs $2,000 |")
    out.append("|---|---|---|---|---|---|---|---|")
    new_pool = RULES_A + RULES_B + RULES_AB
    for seg, block in SEGMENTS:
        era = cells[cells["block"] == block]
        prior = era[(era["overlay"] == 0) & (era["rule"].isin(RULES_CARRIED[:3]))]
        prior_ov = era[(era["overlay"] == 1) & (era["rule"] == "close")]
        prior_all = pd.concat([prior, prior_ov])
        best_prior = prior_all.loc[prior_all["realized_day"].idxmax()]
        pool = era[(era["overlay"] == 0) & (era["rule"].isin(new_pool))]
        best_new = pool.loc[pool["realized_day"].idxmax()]
        ceiling = era[(era["overlay"] == 0) & (era["rule"] == "oracle")]
        best_ceiling = ceiling["realized_day"].max()
        pick = loeo(cells, block, new_pool)
        out.append(
            f"| `{block}` | {money(best_prior['realized_day'])} "
            f"({best_prior['rule']}, {best_prior['arm']}, {best_prior['stream']}) | "
            f"**{money(best_new['realized_day'])}** | "
            f"{best_new['rule']} / {best_new['arm']} / {best_new['stream']} | "
            f"{money(pick['realized_day']) if pick is not None else 'n/a'} | "
            f"{(pick['rule'] + ' / ' + pick['arm'] + ' / ' + pick['stream']) if pick is not None else 'n/a'} | "
            f"{money(best_ceiling)} | "
            f"{number(100.0 * best_new['realized_day'] / 2000.0, 0)}% |")

    # --- the four asked-for readings ---------------------------------------
    out.append("\n## (i) Does A and/or B beat ALL prior implementables, per era?\n")
    out.append("| era | best prior | best A | best B | best A+B | A beats prior | "
               "B beats prior | A+B beats prior |")
    out.append("|---|---|---|---|---|---|---|---|")
    for seg, block in SEGMENTS:
        era = cells[cells["block"] == block]
        prior_all = pd.concat([era[(era["overlay"] == 0)
                                   & (era["rule"].isin(RULES_CARRIED[:3]))],
                               era[(era["overlay"] == 1) & (era["rule"] == "close")]])
        pbest = float(prior_all["realized_day"].max())
        cell = {}
        for name, pool in (("A", RULES_A), ("B", RULES_B), ("A+B", RULES_AB)):
            sub = era[(era["overlay"] == 0) & (era["rule"].isin(pool))]
            cell[name] = float(sub["realized_day"].max()) if not sub.empty else np.nan
        out.append(f"| `{block}` | {money(pbest)} | {money(cell['A'])} | "
                   f"{money(cell['B'])} | {money(cell['A+B'])} | "
                   + " | ".join("YES" if np.isfinite(cell[n]) and cell[n] > pbest
                                else "no" for n in ("A", "B", "A+B")) + " |")

    out.append("\n## (ii) Best ONE-POSITION realised $/day per era vs "
               "$2,000 / $1,500\n")
    out.append("| era | best cell $/day | RTY-mini | % of $2,000 | % of $1,500 | "
               "picked $/day | entered cert $/day | capture of entered | "
               "trades/day | $/trade | mean hold |")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for seg, block in SEGMENTS:
        era = cells[(cells["block"] == block) & (cells["overlay"] == 0)
                    & (cells["rule"] != "oracle")]
        row = era.loc[era["realized_day"].idxmax()]
        out.append(
            f"| `{block}` | **{money(row['realized_day'])}** "
            f"({row['rule']}, {row['arm']}, {row['stream']}) | "
            f"{money(row['realized_day'] * RTY[block])} | "
            f"{number(100.0 * row['realized_day'] / 2000.0, 0)}% | "
            f"{number(100.0 * row['realized_day'] / 1500.0, 0)}% | "
            f"{money(row['picked_day'])} | {money(row['entered_cert_day'])} | "
            f"{number(row['capture_entered_pct'], 0)}% | "
            f"{number(row['trades_day'], 2)} | {money(row['trade_mean'])} | "
            f"{number(row['hold_min'], 0)}min |")

    out.append("\n## (iii) The per-trade realised distribution at the best cell "
               "(the $900+/trade need)\n")
    out.append("| era | cell | trades | mean | median | p10 | p25 | p75 | p90 | "
               "share > $0 | share >= $600 | share >= $900 | worst |")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    dist_rows = []
    for seg, block in SEGMENTS:
        era = cells[(cells["block"] == block) & (cells["overlay"] == 0)
                    & (cells["rule"] != "oracle")]
        row = era.loc[era["realized_day"].idxmax()]
        part = trades[(trades["block"] == block) & (trades["arm"] == row["arm"])
                      & (trades["stream"] == row["stream"])
                      & (trades["rule"] == row["rule"])]
        pnl = part["pnl"].to_numpy(float)
        q = np.percentile(pnl, [10, 25, 75, 90]) if pnl.size else [np.nan] * 4
        dist_rows.append({"block": block, "arm": row["arm"],
                          "stream": row["stream"], "rule": row["rule"],
                          "trades": len(pnl),
                          "mean": float(pnl.mean()) if pnl.size else np.nan,
                          "median": float(np.median(pnl)) if pnl.size else np.nan,
                          "p10": q[0], "p25": q[1], "p75": q[2], "p90": q[3],
                          "pos_pct": 100.0 * float((pnl > 0).mean()) if pnl.size else np.nan,
                          "ge600_pct": 100.0 * float((pnl >= 600).mean()) if pnl.size else np.nan,
                          "ge900_pct": 100.0 * float((pnl >= 900).mean()) if pnl.size else np.nan,
                          "worst": float(pnl.min()) if pnl.size else np.nan})
        d = dist_rows[-1]
        out.append(
            f"| `{block}` | {row['rule']} / {row['arm']} / {row['stream']} | "
            f"{d['trades']} | {money(d['mean'])} | {money(d['median'])} | "
            f"{money(d['p10'])} | {money(d['p25'])} | {money(d['p75'])} | "
            f"{money(d['p90'])} | {number(d['pos_pct'], 0)}% | "
            f"{number(d['ge600_pct'], 0)}% | {number(d['ge900_pct'], 0)}% | "
            f"{money(d['worst'])} |")
    pd.DataFrame(dist_rows).to_csv(DIST, sep="\t", index=False)

    out.append("\n## (iv) Shuffle controls\n")
    out.append("A's control permutes the opposite-fire TIMES within "
               "(session, arm, side) — the same number of fires per side, "
               "random clocks.  B's control permutes the entry-P within "
               "(session, arm) — the same class sizes, random membership.  "
               "Three draws each; the ENTRY stream is untouched in both, so "
               "only the exit-side use of the score is randomised.\n")
    out.append("| era | arm | stream | real A (`mmirror@25`) | shuffled A (3 draws) | "
               "real B (`class[30]`) | shuffled B (3 draws) |")
    out.append("|---|---|---|---|---|---|---|")
    for seg, block in SEGMENTS:
        for arm in ARMS:
            for stream in ("top5", "thr20"):
                sel = cells[(cells["block"] == block) & (cells["arm"] == arm)
                            & (cells["stream"] == stream) & (cells["overlay"] == 0)]
                def get(rule):
                    hit = sel[sel["rule"] == rule]
                    return float(hit["realized_day"].iloc[0]) if len(hit) else np.nan
                sa = [get(f"shufA{d}@{CHARTER_BAR}") for d in range(1, SHUFFLE_DRAWS + 1)]
                sb = [get(f"shufB{d}[{TIME_STOPS[0]}]") for d in range(1, SHUFFLE_DRAWS + 1)]
                out.append(f"| `{block}` | {arm} | {stream} | "
                           f"{money(get(f'mmirror@{CHARTER_BAR}'))} | "
                           f"{money(float(np.nanmean(sa)))} "
                           f"[{', '.join(money(v) for v in sa)}] | "
                           f"{money(get(f'class[{TIME_STOPS[0]}]'))} | "
                           f"{money(float(np.nanmean(sb)))} "
                           f"[{', '.join(money(v) for v in sb)}] |")

    # --- WHY: the occupancy-free anatomy -----------------------------------
    if ANATOMY.exists():
        anat = pd.read_csv(ANATOMY, sep="\t")
        out.append("\n## WHY — the anatomy, on EVERY candidate (occupancy-free)\n")
        out.append("These tables do not pass through the one-position filter, "
                   "so they measure the formulations themselves rather than the "
                   "book they happen to produce.\n")
        out.append("\n**B — does the entry-time P know which trades benefit "
                   "from being held?**  If it does, the top-decile class must "
                   "gain from holding and the rest must lose from it.\n")
        out.append("| era | arm | class | candidates | winner share | "
                   "hold-to-close $ | 30-min stop $ | 60-min stop $ | "
                   "close - stop30 | oracle $ |")
        out.append("|---|---|---|---|---|---|---|---|---|---|")
        for seg, block in SEGMENTS:
            for arm in ARMS:
                for flag, name in ((1, "P in top decile"), (0, "the rest")):
                    part = anat[(anat["block"] == block) & (anat["arm"] == arm)
                                & (anat["high_p"] == flag)]
                    if part.empty:
                        out.append(f"| `{block}` | {arm} | {name} | 0 | n/a | "
                                   f"n/a | n/a | n/a | n/a | n/a |")
                        continue
                    out.append(
                        f"| `{block}` | {arm} | {name} | {len(part)} | "
                        f"{number(100.0 * part['winner'].mean(), 0)}% | "
                        f"{money(part['pnl_close'].mean())} | "
                        f"{money(part['pnl_stop30'].mean())} | "
                        f"{money(part['pnl_stop60'].mean())} | "
                        f"{money(part['pnl_close'].mean() - part['pnl_stop30'].mean())} | "
                        f"{money(part['pnl_oracle'].mean())} |")

        out.append("\n**A — what the opposite-side model fire does when it "
                   "fires**, split by the TRUTH class of the trade it is "
                   "closing (read-only; no rule reads it).  A working exit cuts "
                   "duds harder than winners.\n")
        out.append("| era | arm | class | candidates | fires before close | "
                   "mean hold under A | hold-to-close $ | `mmirror@25` $ | "
                   "A - close |")
        out.append("|---|---|---|---|---|---|---|---|---|")
        for seg, block in SEGMENTS:
            for arm in ARMS:
                for flag, name in ((1, "winners (cert >= $500)"), (0, "duds")):
                    part = anat[(anat["block"] == block) & (anat["arm"] == arm)
                                & (anat["winner"] == flag)]
                    if part.empty:
                        continue
                    fired = float((part["hold_mm25"] < part["hold_close"]).mean())
                    out.append(
                        f"| `{block}` | {arm} | {name} | {len(part)} | "
                        f"{number(100.0 * fired, 0)}% | "
                        f"{number(part['hold_mm25'].mean() / 60.0, 0)}min | "
                        f"{money(part['pnl_close'].mean())} | "
                        f"{money(part['pnl_mm25'].mean())} | "
                        f"{money(part['pnl_mm25'].mean() - part['pnl_close'].mean())} |")

    # --- deployment-era means ----------------------------------------------
    out.append("\n## Deployment-era mean (e4..e7), every rule x arm x stream, "
               "overlay OFF\n")
    out.append("| rule | arm | stream | mean $/day | mean $/trade | winner share | "
               "capture of entered | trades/day | mean hold | worst day | "
               "worst trade |")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|")
    dep = cells[(cells["block"].isin(deployment)) & (cells["overlay"] == 0)]
    agg = (dep.groupby(["rule", "arm", "stream"])
           .agg(day=("realized_day", "mean"), tr=("trade_mean", "mean"),
                ws=("winner_share", "mean"), cap=("capture_entered_pct", "mean"),
                td=("trades_day", "mean"), hold=("hold_min", "mean"),
                wd=("worst_day", "min"), wt=("worst_trade", "min"))
           .reset_index().sort_values("day", ascending=False))
    for _, row in agg.iterrows():
        out.append(f"| {row['rule']} | {row['arm']} | {row['stream']} | "
                   f"**{money(row['day'])}** | {money(row['tr'])} | "
                   f"{number(row['ws'], 0)}% | {number(row['cap'], 0)}% | "
                   f"{number(row['td'], 2)} | {number(row['hold'], 0)}min | "
                   f"{money(row['wd'])} | {money(row['wt'])} |")

    # --- overlay panel ------------------------------------------------------
    out.append("\n## The `cont[lasso,B]@c25` overlay ON — the brief's "
               "configuration\n")
    out.append("The overlay is rung 3's drawdown keeper and is run ON for every "
               "rule, as specified.  It is also reported OFF above, because "
               "every prior rung's implementable numbers are overlay-free and "
               "the comparison has to be like-for-like.\n")
    out.append("| rule | arm | stream | $/day OFF | $/day ON | hold OFF | "
               "hold ON | worst day OFF | worst day ON |")
    out.append("|---|---|---|---|---|---|---|---|---|")
    pivot = dep.set_index(["rule", "arm", "stream"])
    depon = cells[(cells["block"].isin(deployment)) & (cells["overlay"] == 1)]
    aggon = (depon.groupby(["rule", "arm", "stream"])
             .agg(day=("realized_day", "mean"), hold=("hold_min", "mean"),
                  wd=("worst_day", "min")).reset_index())
    merged = agg.merge(aggon, on=["rule", "arm", "stream"], suffixes=("", "_on"))
    for _, row in merged.sort_values("day", ascending=False).iterrows():
        out.append(f"| {row['rule']} | {row['arm']} | {row['stream']} | "
                   f"{money(row['day'])} | {money(row['day_on'])} | "
                   f"{number(row['hold'], 0)}min | {number(row['hold_on'], 0)}min | "
                   f"{money(row['wd'])} | {money(row['wd_on'])} |")

    # --- full cell panel ----------------------------------------------------
    out.append("\n## Full panel — every (era, arm, stream, rule, overlay) cell\n")
    out.append("Written in full to `rung4_segments/rung4_cells.tsv`; the "
               "overlay-OFF rows are reproduced here.\n")
    out.append("| era | arm | stream | rule | $/day | $/trade | winner share | "
               "entered cert/day | capture entered | trades/day | mean hold | "
               "worst day | worst trade | win rate | stop rate |")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for _, row in cells[cells["overlay"] == 0].sort_values(
            ["segment", "arm", "stream", "rule"]).iterrows():
        out.append(f"| `{row['block']}` | {row['arm']} | {row['stream']} | "
                   f"{row['rule']} | **{money(row['realized_day'])}** | "
                   f"{money(row['trade_mean'])} | {number(row['winner_share'], 0)}% | "
                   f"{money(row['entered_cert_day'])} | "
                   f"{number(row['capture_entered_pct'], 0)}% | "
                   f"{number(row['trades_day'], 2)} | {number(row['hold_min'], 0)}min | "
                   f"{money(row['worst_day'])} | {money(row['worst_trade'])} | "
                   f"{number(row['win_rate'], 0)}% | {number(row['stop_rate'], 0)}% |")

    # --- bars ---------------------------------------------------------------
    out.append("\n## The study bars (training-window OOF quantiles)\n")
    out.append("| segment | era | arm | train rows | features | " +
               " | ".join(f"P@top{q}" for q in QUANTILES) + " |")
    out.append("|---|---|---|---|---|" + "---|" * len(QUANTILES))
    for seg, block in SEGMENTS:
        for arm in ARMS:
            part = bars[(bars["segment"] == seg) & (bars["arm"] == arm)]
            if part.empty:
                continue
            head = part.iloc[0]
            values = [float(part[part["topq"] == q]["threshold"].iloc[0])
                      for q in QUANTILES]
            out.append(f"| {seg} | `{block}` | {arm} | {int(head['train_rows'])} | "
                       f"{int(head['features'])} | "
                       + " | ".join(f"{v:.4f}" for v in values) + " |")

    out.append("\n## Laws and controls\n")
    for row in controls:
        out.append(f"- CONTROL — {row['control']}: {row['value']}")
    out.append("- STRICTLY PRIOR: a candidate's model score is a function of "
               "features stamped at its OWN decision second and of a model fit "
               "on strictly earlier sessions, so an exit stamped at an "
               "opposite-side candidate's decision second reads nothing from the "
               "future.  The study bars are quantiles of session-grouped "
               "OUT-OF-FOLD predictions on each segment's training window.")
    out.append("- NO TEST TUNING: the bar ladder {10,20,25}%, the class decile, "
               "the time stops {30,60}, the three A variants, the four streams "
               "and the two arms were all fixed before any number was computed, "
               "and every cell is reported.  The headline table carries a "
               "leave-one-era-out reading beside the in-block maximum.")
    out.append(f"- ONE POSITION, ONE MINI (D-046): SLOTS={SLOTS}; the occupancy "
               f"replay is `exit_engine.replay_day`'s admission test unchanged.")
    out.append("- COSTS: 576 net cents once per trade on every rule including "
               "the oracle (`qr_labels/money.hpp`).")
    out.append("- WALL: -30,000 net cents, monitored from entry on marks "
               "strictly after the entry mark, filling at the next lawful mark "
               "after the crossing; gap-through retained; unchanged from rung 1.")
    out.append(f"- SEALED ZONE: `packlib.SEALED_FROM` = {P.SEALED_FROM}; the "
               f"highest session replayed here is "
               f"{int(trades['session'].max())}.")
    out.append("- D-022 overlay: era RTY-mini factors "
               + ", ".join(f"`{b}` {RTY[b]:.3f}" for _, b in SEGMENTS)
               + "; every dollar figure is within 12% of its one-mini "
                 "equivalent and no percentage moves.")

    REPORT.write_text("\n".join(out) + "\n")
    print(f"report -> {REPORT}", flush=True)


# ==========================================================================
# main
# ==========================================================================

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", default="all",
                        choices=("thresholds", "replay", "report", "all"))
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()

    OUTDIR.mkdir(parents=True, exist_ok=True)
    bars = stage_thresholds(args.rebuild)
    if args.stage == "thresholds":
        return

    #: reproduction control — the published {5,10,15,20} bars must come back
    published = pd.read_csv(PUB_THRESH, sep="\t")
    published = published[(published["variant"] == "base")
                          & (published["target"] == "w500")
                          & (published["arm"].isin(ARMS))]
    check = bars.merge(published, on=["segment", "arm", "topq"],
                       suffixes=("", "_pub"))
    delta = float((check["threshold"] - check["threshold_pub"]).abs().max())
    print(f"control: published-bar reproduction, max |delta| = {delta:.3e} "
          f"over {len(check)} bars", flush=True)
    controls_extra = [{"control": "published bar reproduction",
                       "value": f"max |delta| {delta:.2e} over {len(check)} "
                                f"(segment, arm, topq) bars of "
                                f"`precision_thresholds.tsv`"}]

    if args.stage in ("replay", "all"):
        cells, trades, controls = stage_replay(bars)
        cells.to_csv(CELLS, sep="\t", index=False)
        trades.to_csv(TRADES, sep="\t", index=False)
        pd.DataFrame(controls + controls_extra).to_csv(CONTROL, sep="\t", index=False)
    else:
        cells = pd.read_csv(CELLS, sep="\t")
        trades = pd.read_csv(TRADES, sep="\t")
        controls = pd.read_csv(CONTROL, sep="\t").to_dict("records")
    if args.stage == "replay":
        return

    if args.stage == "report":
        controls = pd.read_csv(CONTROL, sep="\t").to_dict("records")
    else:
        controls = controls + controls_extra
    write_report(cells, trades, bars, controls)


if __name__ == "__main__":
    main()
