#!/usr/bin/env python3
"""exit_engine.py — RUNG 1 of the exit program: MIRROR-CONFIRMATION EXITS.

THE PROBLEM (D-045).  `era_retest.py` shows selection PICKS $2,000-2,225/day at
top-5 in every 2024-25 era while the deployable one-position/hold-to-close shape
realises -$90..+$64/day.  Selection is not the bottleneck; the EXIT is.  This
file is the converter, and it contains ZERO machine learning: the exit is the
same causal ZigZag confirmation the entry roster is built from, run in the
OPPOSITE direction.

THE RULE (orchestrator's design, D-002 — implemented, not redesigned):

    entry = the candidate's decision second (the roster's own post-confirmation
            stage; `render.swings` confirmed the extreme, the roster waited
            60..120s, that second is the entry).
    exit  = the FIRST OPPOSITE-DIRECTION CONFIRMED PIVOT after entry.  A long
            was opened on a confirmed LOW; the swing AGAINST it is a HIGH, and
            a HIGH is CONFIRMED at the second price has retraced the session's
            ATR-relative threshold from it.  That confirmation second is the
            exit.  No opposite confirmation before the close => session close.
    wall  = the $300 (-30,000 net-cent) hard stop, retained, monitored from
            entry, filling at the NEXT lawful mark strictly after crossing
            (gap-through kept, exactly as `qr_labels/label_kernel.hpp` does).

PREREGISTERED VARIANT GRID (all reported, none tuned, no rule selected on a
test block):

    a  mirror x {0.75, 1.0, 1.5} of the entry threshold  (asymmetric trailing)
    b  mirror, never before +15min                        (patience floor)
    c  mirror OR breakeven-stop once the trade reaches +0.5 x the TRAINING
       window's median winner MFE                         (ratchet)
    d  fixed close                                        (baseline)
    e  oracle certificate                                 (ceiling, reference)

STRICT PRIORITY.  Every exit decision at second t uses only pivots CONFIRMED at
or before t (`render.swings` stamps a pivot at its extreme's second but only
emits it at the retrace, which is the causal object) and marks at or before t.
The ratchet's arming level is the median winner certificate of the segment's own
TRAINING window — strictly earlier sessions — never the test era's.  The oracle
arm is the only forward-looking object here and is labelled as a ceiling.

MONEY.  `qr_labels/money.hpp`, transcribed: frac_u6 = trunc(move_u6 * 1e6 /
entry_u6), net_cent = frac_u6 * 10 - 576, i.e. the 576-cent round trip charged
ONCE per trade, on the $100,000 notional.  The marks are the 1s grid's carried
mids (`packlib.load_grid`), which is the brief's specification and is one
half-spread per side more generous than the truth kernel's conservative
ask/bid envelope; section "calibration" of the report measures that gap against
`menu_net_cent[close]` on the identical candidates rather than assuming it.

    exit_engine.py [--stage picks|replay|all] [--rebuild]
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np                                        # noqa: E402
import pandas as pd                                       # noqa: E402

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import packlib as P                                       # noqa: E402
import render as R                                        # noqa: E402
import daylib as D                                        # noqa: E402
import distill_model as dm                                # noqa: E402
import walkforward as wf                                  # noqa: E402
import era_retest as er                                   # noqa: E402

ROOT = P.ROOT
MATRIX = ROOT / "FEATURES_ERA.tsv"
OUTDIR = ROOT / "exit_segments"
PICKS = OUTDIR / "picks.tsv"
REPORT = ROOT / "EXIT_RUNG1_REPORT.md"

#: the segments the brief names: the four new eras plus the published control
SEGMENTS = er.SEGMENTS                       # (e, blind_e3), (f, e4) ... (i, e7)
ARMS = er.ARMS
KS = (3, 5)

#: `qr_labels/money.hpp`
COST_CENT = 576
GROSS_CENT_PER_FRAC = 10
FRAC_SCALE_U6 = 1_000_000
WALL_NET_CENT = -30_000

#: `daylib.py` — blocks study_e1..blind_e3 were rostered at the fixed 15bp pin
#: (`render.SWING_REVERSAL_BPS`); e4..e7 at ORCH-6.1's max(12bp, 0.11 x ATR14).
#: Verified against the rosters: session 428 matches 14/14 pivots at 15.0 and
#: 3/14 at its ATR value; session 736 matches at its ATR value.
FIXED_PIN_BLOCKS = {"blind_e3"}

#: the preregistered grid.  `mirror@1.00` is the design centre.
MIRROR_MULTIPLIERS = (0.75, 1.00, 1.50)
PATIENCE_FLOOR_S = 15 * 60
RATCHET_FRACTION = 0.5

RULES = (["close"]
         + [f"mirror@{m:.2f}" for m in MIRROR_MULTIPLIERS]
         + ["mirror@1.00+patience15", "mirror@1.00+ratchet", "oracle"])


# ==========================================================================
# picks — the arms' own top-k lists, refit exactly as the era harness does
# ==========================================================================

def build_picks() -> pd.DataFrame:
    frame = pd.read_csv(MATRIX, sep="\t", low_memory=False)
    print(f"matrix {frame.shape} <- {MATRIX}", flush=True)
    rows = []
    for seg, block in SEGMENTS:
        test = frame[frame["block"] == block].reset_index(drop=True)
        train = frame[frame["session"] < int(test["session"].min())].reset_index(drop=True)
        assert train["session"].max() < test["session"].min(), "walk-forward purity"
        sets = er.arm_columns(frame, train)
        #: the ratchet's arming level, from the TRAINING window only
        winners = train.loc[train["winner"] == 1, "cert"]
        ratchet = float(np.median(winners)) if len(winners) else np.nan
        print(f"segment {seg}: train {len(train)} rows "
              f"({int(train['session'].min())}..{int(train['session'].max())}) -> "
              f"{block} {len(test)} rows; train median winner MFE ${ratchet:,.0f}",
              flush=True)
        for arm in ARMS:
            score = wf.fit_frozen(train, test, sets[arm])
            working = test.assign(_score=score)
            for k in KS:
                for session, day in working.groupby("session", sort=True):
                    for _, pick in day.nlargest(k, "_score").iterrows():
                        rows.append({
                            "segment": seg, "block": block, "arm": arm, "k": k,
                            "session": int(session), "id": pick["id"],
                            "second": int(pick["second"]), "side": pick["side"],
                            "cert": float(pick["cert"]),
                            "menu_close": float(pick["menu_close"]),
                            "ratchet_arm": ratchet,
                        })
            print(f"   {arm:12s} {len(sets[arm]):4d} cols picked", flush=True)
    out = pd.DataFrame(rows)
    OUTDIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(PICKS, sep="\t", index=False)
    return out


# ==========================================================================
# the money kernel — qr_labels/money.hpp, transcribed
# ==========================================================================

def net_cent(entry_u6: int, mark_u6: np.ndarray, side: str) -> np.ndarray:
    """Realised net cents of exiting at `mark_u6`; cost charged once."""
    move = (mark_u6 - entry_u6) if side == "L" else (entry_u6 - mark_u6)
    quotient = np.abs(move) * FRAC_SCALE_U6 // entry_u6          # trunc toward 0
    frac = np.where(move >= 0, quotient, -quotient)
    return frac * GROSS_CENT_PER_FRAC - COST_CENT


# ==========================================================================
# per-session objects: the grid, and the pivot ladders at each threshold
# ==========================================================================

class Session:
    """One session's lawful marks and its causal pivot ladders."""

    def __init__(self, ordinal: int, block: str):
        grid = P.load_grid(ordinal)[:, 0]
        self.second = np.flatnonzero(grid > 0).astype(np.int64)
        self.mid = np.rint(grid[self.second]).astype(np.int64)
        self.base_bps = (R.SWING_REVERSAL_BPS if block in FIXED_PIN_BLOCKS
                         else D.reversal_bps(ordinal))
        self.close_pos = len(self.second) - 1
        #: {multiplier: {"H": sorted confirmed seconds, "L": ...}}
        self.ladder = {}
        #: {multiplier: {kind: {confirmed second: the pivot's own extreme second}}}
        self.extreme = {}
        for multiplier in MIRROR_MULTIPLIERS:
            confirms = {"H": [], "L": []}
            extremes = {"H": {}, "L": {}}
            for pivot in R.swings(grid, self.base_bps * multiplier):
                confirms[pivot["kind"]].append(int(pivot["confirmed"]))
                extremes[pivot["kind"]][int(pivot["confirmed"])] = int(pivot["second"])
            self.ladder[multiplier] = {kind: np.array(sorted(values), dtype=np.int64)
                                       for kind, values in confirms.items()}
            self.extreme[multiplier] = extremes

    def position(self, second: int) -> int:
        """Index of the first lawful mark at or after `second` (close if past)."""
        return min(int(np.searchsorted(self.second, second, "left")), self.close_pos)

    def mirror_second(self, multiplier: float, side: str, entry_second: int) -> int | None:
        """First confirmation of a swing AGAINST `side`, strictly after entry."""
        kind = "H" if side == "L" else "L"
        confirms = self.ladder[multiplier][kind]
        index = int(np.searchsorted(confirms, entry_second, "right"))
        return int(confirms[index]) if index < len(confirms) else None

    def entry_pivot_second(self, multiplier: float, side: str, entry_second: int):
        """The FAVOURABLE pivot the entry came from: the last same-direction
        confirmation at or before entry.  Used only by the giveback anatomy."""
        kind = "L" if side == "L" else "H"
        confirms = self.ladder[multiplier][kind]
        index = int(np.searchsorted(confirms, entry_second, "right")) - 1
        if index < 0:
            return None
        return self.extreme[multiplier][kind][int(confirms[index])]


# ==========================================================================
# the replay — one trade, one rule
# ==========================================================================

def replay_trade(session: Session, second: int, side: str, rule: str,
                 ratchet_arm: float) -> dict:
    """Realised dollars of one trade under one exit rule.

    The wall is monitored from entry for EVERY rule; whichever of (wall, rule)
    fires first is the exit, and the wall fills at the next lawful mark strictly
    after the crossing.
    """
    start = session.position(second)
    entry_u6 = int(session.mid[start])
    nets = net_cent(entry_u6, session.mid, side)

    #: the shared wall scan — marks STRICTLY after entry, exactly as the kernel
    forward = np.flatnonzero(nets[start + 1:] <= WALL_NET_CENT)
    wall_pos = int(forward[0]) + start + 1 if forward.size else None
    wall_fill = min(wall_pos + 1, session.close_pos) if wall_pos is not None else None

    limit = wall_fill if wall_fill is not None else session.close_pos

    if rule == "close":
        rule_pos = session.close_pos
    elif rule == "oracle":
        #: the certificate: the uncapped best positive mark before the wall
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
            rule_second = max(rule_second, int(session.second[start]) + PATIENCE_FLOOR_S)
        rule_pos = session.position(rule_second)
        if rule.endswith("+ratchet") and np.isfinite(ratchet_arm):
            level = RATCHET_FRACTION * ratchet_arm * 100.0        # dollars -> cents
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


def anatomy(session: Session, second: int, side: str) -> dict:
    """WHERE THE LEG GOES, under the design-centre rule `mirror@1.00`.

    A confirmation-in / confirmation-out trade pays the threshold TWICE: once
    to enter (the roster enters 60-120s after price has already retraced the
    threshold off the extreme) and once to exit (the opposite pivot is only
    confirmed after price has retraced the threshold off its own extreme).
    This decomposes the pivot-to-pivot leg into exactly those pieces, in
    dollars on the $100,000 object, all of them GROSS of the 576c so the cost
    appears once, on its own line.
    """
    start = session.position(second)
    entry_u6 = int(session.mid[start])
    entry_second = int(session.second[start])
    nets = net_cent(entry_u6, session.mid, side)
    gross = (nets + COST_CENT) / 100.0

    low_second = session.entry_pivot_second(1.00, side, entry_second)
    exit_confirm = session.mirror_second(1.00, side, entry_second)
    if exit_confirm is None:
        peak_second = int(session.second[session.close_pos])
        exit_second = peak_second
    else:
        peak_second = session.extreme[1.00]["H" if side == "L" else "L"][exit_confirm]
        exit_second = exit_confirm
    peak_pos = session.position(max(peak_second, entry_second))
    exit_pos = session.position(exit_second)
    entry_giveback = np.nan
    if low_second is not None:
        pivot_u6 = int(session.mid[session.position(low_second)])
        entry_giveback = float(net_cent(pivot_u6, np.array([entry_u6]), side)[0]
                               + COST_CENT) / 100.0
    return {"leg_at_turn": float(gross[peak_pos]),
            "exit_giveback": float(gross[peak_pos] - gross[exit_pos]),
            "entry_giveback": entry_giveback,
            "realized_gross": float(gross[exit_pos]),
            "realized_net": float(nets[exit_pos]) / 100.0}


# ==========================================================================
# occupancy replay — one position at a time, chronological
# ==========================================================================

def replay_day(trades: dict, picks: list) -> tuple:
    """(day dollars, taken trades) for one session's pick list under one rule."""
    total, taken, busy = 0.0, [], -1
    for pick in sorted(picks, key=lambda row: (row["second"], row["id"])):
        if pick["second"] < busy:
            continue
        trade = trades[pick["id"]]
        total += trade["pnl"]
        taken.append(dict(trade, cert=pick["cert"]))
        busy = trade["exit_second"]
    return total, taken


# ==========================================================================
# main
# ==========================================================================

def summarise(days: list, trades: list, picked_day: float) -> dict:
    daily = np.array(days, dtype=float)
    pnl = np.array([t["pnl"] for t in trades], dtype=float) if trades else np.zeros(0)
    #: the certificate value of the picks this rule ACTUALLY ENTERED.  One
    #: position at a time means most of the day's k picks are never available,
    #: so `picked_day` is a ceiling no occupancy-respecting rule can reach; this
    #: is the reachable denominator.
    entered = (sum(t["cert"] for t in trades) / len(daily)) if daily.size else np.nan
    return {
        "days": len(daily),
        "realized_day": float(daily.mean()) if daily.size else np.nan,
        "picked_day": picked_day,
        "entered_cert_day": entered,
        "capture_pct": (100.0 * daily.mean() / picked_day) if picked_day else np.nan,
        "capture_entered_pct": (100.0 * daily.mean() / entered
                                if entered and np.isfinite(entered) and entered
                                else np.nan),
        "median_day": float(np.median(daily)) if daily.size else np.nan,
        "worst_day": float(daily.min()) if daily.size else np.nan,
        "best_day": float(daily.max()) if daily.size else np.nan,
        "sd_day": float(daily.std()) if daily.size else np.nan,
        "loss_days_pct": (100.0 * float((daily < 0).mean())) if daily.size else np.nan,
        "trades_day": (len(pnl) / len(daily)) if daily.size else np.nan,
        "trade_mean": float(pnl.mean()) if pnl.size else np.nan,
        "max_trade_loss": float(pnl.min()) if pnl.size else np.nan,
        "max_trade_gain": float(pnl.max()) if pnl.size else np.nan,
        "win_rate": (100.0 * float((pnl > 0).mean())) if pnl.size else np.nan,
        "stop_rate": (100.0 * float(np.mean([t["stopped"] for t in trades])))
                     if trades else np.nan,
        "hold_min": (float(np.mean([t["hold_s"] for t in trades])) / 60.0)
                    if trades else np.nan,
        #: the same trades split by the TRUTH class of the candidate taken — a
        #: read-only diagnostic (no rule reads it), and the one that says
        #: whether a rule fails by cutting winners or by not cutting duds
        "winner_trade_mean": _class_mean(trades, True),
        "dud_trade_mean": _class_mean(trades, False),
        "winner_share": (100.0 * float(np.mean([t["cert"] >= 500.0 for t in trades])))
                        if trades else np.nan,
    }


def _class_mean(trades: list, winners: bool) -> float:
    part = [t["pnl"] for t in trades if (t["cert"] >= 500.0) == winners]
    return float(np.mean(part)) if part else np.nan


def money(value) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    return f"-${abs(value):,.0f}" if value < 0 else f"${value:,.0f}"


def number(value, digits=1) -> str:
    return "n/a" if value is None or not np.isfinite(value) else f"{value:.{digits}f}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", default="all", choices=("picks", "replay", "all"))
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()

    if args.rebuild or not PICKS.exists():
        picks = build_picks()
    else:
        picks = pd.read_csv(PICKS, sep="\t")
        print(f"picks {picks.shape} <- {PICKS}", flush=True)
    if args.stage == "picks":
        return

    OUTDIR.mkdir(parents=True, exist_ok=True)
    results, calibration, anatomies = [], [], []

    for seg, block in SEGMENTS:
        part = picks[picks["segment"] == seg]
        sessions = sorted(part["session"].unique())
        ratchet_arm = float(part["ratchet_arm"].iloc[0])
        #: {(arm, k): {session: [pick rows]}}
        books = {(arm, k): {} for arm in ARMS for k in KS}
        for row in part.to_dict("records"):
            books[(row["arm"], row["k"])].setdefault(row["session"], []).append(row)
        #: accumulators: {(arm, k, rule): ([day dollars], [trades])}
        acc = {(arm, k, rule): ([], []) for arm in ARMS for k in KS for rule in RULES}
        picked = {(arm, k): [] for arm in ARMS for k in KS}

        print(f"segment {seg} ({block}): {len(sessions)} sessions", flush=True)
        for done, ordinal in enumerate(sessions, 1):
            session = Session(int(ordinal), block)
            wanted = {row["id"]: row for row in part[part["session"] == ordinal]
                      .to_dict("records")}
            trades = {rule: {cid: replay_trade(session, row["second"], row["side"],
                                               rule, ratchet_arm)
                             for cid, row in wanted.items()}
                      for rule in RULES}
            for cid, row in wanted.items():
                calibration.append({"segment": seg, "session": int(ordinal), "id": cid,
                                    "grid_close": trades["close"][cid]["pnl"],
                                    "truth_close": row["menu_close"],
                                    "grid_oracle": trades["oracle"][cid]["pnl"],
                                    "truth_cert": row["cert"]})
                anatomies.append({"segment": seg, "block": block,
                                  "session": int(ordinal), "id": cid,
                                  "winner": int(row["cert"] >= 500.0),
                                  **anatomy(session, row["second"], row["side"])})
            for arm in ARMS:
                for k in KS:
                    day_picks = books[(arm, k)].get(ordinal, [])
                    picked[(arm, k)].append(sum(p["cert"] for p in day_picks))
                    for rule in RULES:
                        total, taken = replay_day(trades[rule], day_picks)
                        acc[(arm, k, rule)][0].append(total)
                        acc[(arm, k, rule)][1].extend(taken)
            if done % 25 == 0 or done == len(sessions):
                print(f"  {done}/{len(sessions)} sessions", flush=True)

        seg_rows = []
        for arm in ARMS:
            for k in KS:
                picked_day = float(np.mean(picked[(arm, k)]))
                for rule in RULES:
                    days, trades_list = acc[(arm, k, rule)]
                    row = {"segment": seg, "block": block,
                           "era_label": er.ERA_LABEL[block], "arm": arm, "k": k,
                           "rule": rule, "ratchet_arm": ratchet_arm,
                           **summarise(days, trades_list, picked_day)}
                    seg_rows.append(row)
                    results.append(row)
        er.write_tsv(OUTDIR / f"exit_{seg}_{block}.tsv", seg_rows)

    frame = pd.DataFrame(results)
    er.write_tsv(OUTDIR / "exit_summary.tsv", results)
    calib = pd.DataFrame(calibration).drop_duplicates(subset=["segment", "session", "id"])
    er.write_tsv(OUTDIR / "calibration.tsv", calib.to_dict("records"))
    anat = pd.DataFrame(anatomies).drop_duplicates(subset=["segment", "session", "id"])
    er.write_tsv(OUTDIR / "giveback_anatomy.tsv", anat.to_dict("records"))
    write_report(frame, calib, anat)


def write_report(frame: pd.DataFrame, calib: pd.DataFrame, anat: pd.DataFrame) -> None:
    out = []
    out.append("# EXIT RUNG 1 — MIRROR-CONFIRMATION EXITS\n")
    out.append("Zero ML.  Entry = the candidate's decision second; exit = the FIRST "
               "opposite-direction CONFIRMED pivot after entry, on the same causal "
               "ZigZag the roster is built from; the $300 wall retained with "
               "gap-through; 576c charged once per trade; one position at a time, "
               "chronological.  Marks are the 1s grid's carried mids "
               "(`packlib.load_grid`).  Every number below is a REALISED dollar, "
               "not an exit-free certificate.\n")

    verdict = ROOT / "EXIT_RUNG1_VERDICT.md"
    if verdict.exists():
        out.append("\n" + verdict.read_text().rstrip() + "\n")

    for k in KS:
        out.append(f"\n## Rule x era capture table — top-{k} picks, "
                   f"realised $/day and capture of picked\n")
        out.append("`picked` is the arm's own top-%d exit-free certified sum per day "
                   "(the era-retest number).  `capture` is realised / picked.\n" % k)
        out.append("| era | arm | picked $/day | " +
                   " | ".join(f"{rule}" for rule in RULES) + " |")
        out.append("|---|---|---|" + "---|" * len(RULES))
        for seg, block in SEGMENTS:
            for arm in ARMS:
                part = frame[(frame["segment"] == seg) & (frame["arm"] == arm)
                             & (frame["k"] == k)]
                if part.empty:
                    continue
                picked_day = float(part["picked_day"].iloc[0])
                cells = []
                for rule in RULES:
                    row = part[part["rule"] == rule].iloc[0]
                    cells.append(f"{money(row['realized_day'])} "
                                 f"({number(row['capture_pct'], 0)}%)")
                out.append(f"| `{block}` | {arm} | {money(picked_day)} | "
                           + " | ".join(cells) + " |")

    out.append("\n## The full per-(era, arm, rule) panel — top-5\n")
    out.append("| era | arm | rule | realised $/day | capture of picked | "
               "capture of entered | median day | worst day | "
               "loss days | trades/day | $/trade | $/winner-trade | $/dud-trade | "
               "max trade loss | win rate | stop rate | mean hold |")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for _, row in frame[frame["k"] == 5].iterrows():
        out.append(f"| `{row['block']}` | {row['arm']} | {row['rule']} | "
                   f"**{money(row['realized_day'])}** | "
                   f"{number(row['capture_pct'], 0)}% | "
                   f"{number(row['capture_entered_pct'], 0)}% | "
                   f"{money(row['median_day'])} | "
                   f"{money(row['worst_day'])} | {number(row['loss_days_pct'], 0)}% | "
                   f"{number(row['trades_day'], 1)} | {money(row['trade_mean'])} | "
                   f"{money(row['winner_trade_mean'])} | "
                   f"{money(row['dud_trade_mean'])} | "
                   f"{money(row['max_trade_loss'])} | {number(row['win_rate'], 0)}% | "
                   f"{number(row['stop_rate'], 0)}% | "
                   f"{number(row['hold_min'], 0)}min |")

    out.append("\n## The full per-(era, arm, rule) panel — top-3\n")
    out.append("| era | arm | rule | realised $/day | capture of picked | "
               "capture of entered | median day | worst day | "
               "loss days | trades/day | $/trade | $/winner-trade | $/dud-trade | "
               "max trade loss | win rate | stop rate | mean hold |")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for _, row in frame[frame["k"] == 3].iterrows():
        out.append(f"| `{row['block']}` | {row['arm']} | {row['rule']} | "
                   f"**{money(row['realized_day'])}** | "
                   f"{number(row['capture_pct'], 0)}% | "
                   f"{number(row['capture_entered_pct'], 0)}% | "
                   f"{money(row['median_day'])} | "
                   f"{money(row['worst_day'])} | {number(row['loss_days_pct'], 0)}% | "
                   f"{number(row['trades_day'], 1)} | {money(row['trade_mean'])} | "
                   f"{money(row['winner_trade_mean'])} | "
                   f"{money(row['dud_trade_mean'])} | "
                   f"{money(row['max_trade_loss'])} | {number(row['win_rate'], 0)}% | "
                   f"{number(row['stop_rate'], 0)}% | "
                   f"{number(row['hold_min'], 0)}min |")

    out.append("\n## WHY — the anatomy of the giveback (`mirror@1.00`, every picked "
               "candidate of the era, gross of cost)\n")
    out.append("A confirmation-in / confirmation-out trade pays the ZigZag threshold "
               "TWICE.  `entry giveback` is what the leg had already travelled between "
               "its own pivot extreme and our entry mark (the confirmation retrace plus "
               "the roster's 60-120s delay); `leg at turn` is what is still left from "
               "our entry to the opposite pivot's extreme; `exit giveback` is what the "
               "opposite confirmation costs to be sure the turn happened.  The 576c "
               "round trip is charged once, on its own line.\n")
    out.append("| era | picks | full leg (pivot->pivot) | entry giveback | "
               "leg at turn | exit giveback | gross realised | cost | net realised |")
    out.append("|---|---|---|---|---|---|---|---|---|")
    for seg, block in SEGMENTS:
        part = anat[anat["segment"] == seg]
        if part.empty:
            continue
        entry_gb = float(part["entry_giveback"].mean())
        leg = float(part["leg_at_turn"].mean())
        out.append(f"| `{block}` | {len(part)} | {money(entry_gb + leg)} | "
                   f"{money(entry_gb)} | {money(leg)} | "
                   f"{money(part['exit_giveback'].mean())} | "
                   f"{money(part['realized_gross'].mean())} | "
                   f"{money(-COST_CENT / 100.0)} | "
                   f"{money(part['realized_net'].mean())} |")
    out.append("\nThe same table split by the candidate's TRUTH class "
               "(read-only; no rule reads it):\n")
    out.append("| era | class | picks | entry giveback | leg at turn | exit giveback | "
               "net realised |")
    out.append("|---|---|---|---|---|---|---|")
    for seg, block in SEGMENTS:
        for flag, name in ((1, "winners (cert >= $500)"), (0, "duds")):
            part = anat[(anat["segment"] == seg) & (anat["winner"] == flag)]
            if part.empty:
                continue
            out.append(f"| `{block}` | {name} | {len(part)} | "
                       f"{money(part['entry_giveback'].mean())} | "
                       f"{money(part['leg_at_turn'].mean())} | "
                       f"{money(part['exit_giveback'].mean())} | "
                       f"{money(part['realized_net'].mean())} |")

    out.append("\n## Calibration control — the grid-mid replay against the truth leaf\n")
    out.append("The replay's `close` rule and the truth leaf's `menu_net_cent[close]` "
               "are the SAME trade; the difference is the fill envelope (grid mids "
               "here, conservative ask/bid there) and is measured, not assumed.  "
               "`oracle` against `certificate_net_cent` is the same comparison for "
               "the ceiling arm.\n")
    out.append("| segment | trades | mean grid close | mean truth close | delta | "
               "mean grid oracle | mean truth cert | delta |")
    out.append("|---|---|---|---|---|---|---|---|")
    for seg, block in SEGMENTS:
        part = calib[calib["segment"] == seg]
        if part.empty:
            continue
        out.append(f"| {seg} (`{block}`) | {len(part)} | "
                   f"{money(part['grid_close'].mean())} | "
                   f"{money(part['truth_close'].mean())} | "
                   f"{money(part['grid_close'].mean() - part['truth_close'].mean())} | "
                   f"{money(part['grid_oracle'].mean())} | "
                   f"{money(part['truth_cert'].mean())} | "
                   f"{money(part['grid_oracle'].mean() - part['truth_cert'].mean())} |")

    out.append("\n## Laws and controls\n")
    out.append("- STRICTLY PRIOR: the exit at second t reads only pivots CONFIRMED at "
               "or before t (`render.swings` emits a pivot at its retrace, not at its "
               "extreme) and marks at or before t.  The ratchet's arming level is the "
               "median winner certificate of each segment's own TRAINING window "
               "(strictly earlier sessions), never the test era's.")
    out.append("- The `oracle` arm is the only forward-looking rule and is reported as "
               "a CEILING, never as a candidate rule.")
    out.append("- PREREGISTERED GRID: the three mirror multipliers, the patience floor "
               "and the ratchet were fixed by the brief before any number was "
               "computed, and every one of them is reported for every era and arm.  "
               "No rule, multiplier or threshold is selected on a test block.")
    out.append("- COSTS: 576 net cents charged once per trade "
               "(`qr_labels/money.hpp`), on every rule including the oracle.")
    out.append(f"- WALL: -30,000 net cents, monitored from entry on marks strictly "
               f"after the entry mark, filling at the next lawful mark strictly after "
               f"the crossing; gap-through retained.")
    out.append(f"- SEALED ZONE: `P.SEALED_FROM` = {P.SEALED_FROM}; the highest session "
               f"replayed here is {int(calib['session'].max())}.")
    out.append("- The confirmation threshold base is the roster's own: the fixed 15bp "
               "pin for `blind_e3`, ORCH-6.1's max(12bp, 0.11 x ATR14) for `e4..e7` "
               "(verified against the rosters' own pivot seconds).")

    REPORT.write_text("\n".join(out) + "\n")
    print(f"report -> {REPORT}", flush=True)


if __name__ == "__main__":
    main()
