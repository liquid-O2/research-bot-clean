"""fvol_contrast.py — FORWARD-VOL REVIVAL, step 4: the TIMING HYPOTHESIS.

The user's hypothesis is that winners cluster at particular states of the day's
move budget: a certain fraction of the implied move already consumed, a certain
band of the level system, a certain nowcast regime.  This tests it on the D-034
STUDY block (398..427, outcomes lawful) in the same telltale format as the prior
contrasts: winners (cert >= $500) against everything else, per column, with the
per-bucket winner rate and the lift over the block's base rate.

Nothing here feeds selection or certification — D-020 case studies generate
hypotheses only.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import fvol_emit as E                                      # noqa: E402
import packlib as P                                        # noqa: E402

LEDGER = P.ROOT / "FEATURES_WF.tsv"
WINNER_DOLLARS = 500.0

#: The emitted columns the hypothesis is stated in.
CONTINUOUS = ("move_consumed_fraction", "range_consumed_fraction", "remaining_move_bps",
              "move_z", "band_z", "sigma_now_bps", "sigma_inst_bps", "rv_sofar_bps",
              "var_fraction_expected")
#: and the session-level ones, which say whether the DAY was the right kind of day.
SESSION_LEVEL = ("implied_move_bps", "sigma_day_bps")

QUINTILES = 5


def load_ledger(block: str) -> list:
    lines = LEDGER.read_text().splitlines()
    names = lines[0].split("\t")
    keep = ("session", "block", "day", "id", "second", "side", "cert", "winner")
    index = {name: names.index(name) for name in keep}
    rows = []
    for line in lines[1:]:
        parts = line.split("\t")
        if parts[index["block"]] != block:
            continue
        rows.append({
            "session": int(parts[index["session"]]), "id": parts[index["id"]],
            "second": int(parts[index["second"]]), "side": parts[index["side"]],
            "cert": float(parts[index["cert"]]),
        })
    return rows


def join_context(rows: list) -> list:
    forecast = E.read_forecast()
    profile = E.Profile(list(range(125, 448)))
    cache = {}
    joined = []
    for row in rows:
        ordinal = row["session"]
        if ordinal not in forecast:
            continue
        if ordinal not in cache:
            cache[ordinal] = E.session_minutes(ordinal, forecast, profile)
        context, minutes = cache[ordinal]
        chosen = None
        for minute in minutes:
            if minute["second"] <= row["second"]:
                chosen = minute
            else:
                break
        if chosen is None:
            continue
        merged = dict(row)
        merged.update({name: context[name] for name in SESSION_LEVEL})
        merged.update({name: chosen[name] for name in CONTINUOUS})
        merged["band_state"] = chosen["band_state"]
        #: the signed band collapses to a magnitude when read against a SIDE:
        #: "extended in my own direction" is the trader's question, and a short
        #: at -2 sigma is the mirror image of a long at +2.
        merged["band_state_own"] = (chosen["band_state"] if row["side"] == "L"
                                    else -chosen["band_state"])
        merged["move_z_own"] = (chosen["move_z"] if row["side"] == "L" else -chosen["move_z"])
        merged["winner"] = 1 if row["cert"] >= WINNER_DOLLARS else 0
        joined.append(merged)
    return joined


def quintile_table(rows: list, column: str) -> dict:
    values = np.array([row[column] for row in rows], dtype=np.float64)
    wins = np.array([row["winner"] for row in rows], dtype=np.float64)
    good = np.isfinite(values)
    values, wins = values[good], wins[good]
    if values.size < QUINTILES * 4:
        return {"n": int(values.size)}
    edges = np.quantile(values, np.linspace(0, 1, QUINTILES + 1))
    edges[0], edges[-1] = -np.inf, np.inf
    base = float(wins.mean())
    buckets = []
    for k in range(QUINTILES):
        mask = (values >= edges[k]) & (values < edges[k + 1])
        if mask.sum() == 0:
            continue
        buckets.append({
            "bucket": k + 1,
            "lo": None if k == 0 else float(edges[k]),
            "hi": None if k == QUINTILES - 1 else float(edges[k + 1]),
            "n": int(mask.sum()),
            "winners": int(wins[mask].sum()),
            "win_rate": float(wins[mask].mean()),
            "lift": float(wins[mask].mean() / base) if base > 0 else float("nan"),
        })
    winners = np.array([row[column] for row in rows if row["winner"] == 1], dtype=np.float64)
    rest = np.array([row[column] for row in rows if row["winner"] == 0], dtype=np.float64)
    winners, rest = winners[np.isfinite(winners)], rest[np.isfinite(rest)]
    pooled = np.sqrt((winners.var(ddof=1) + rest.var(ddof=1)) / 2.0) if min(
        winners.size, rest.size) > 1 else np.nan
    return {
        "n": int(values.size), "base_rate": base,
        "winner_mean": float(winners.mean()), "rest_mean": float(rest.mean()),
        "winner_median": float(np.median(winners)), "rest_median": float(np.median(rest)),
        "cohens_d": float((winners.mean() - rest.mean()) / pooled) if pooled and pooled > 0
        else float("nan"),
        "buckets": buckets,
    }


def categorical_table(rows: list, column: str) -> dict:
    wins = np.array([row["winner"] for row in rows], dtype=np.float64)
    base = float(wins.mean())
    out = {"base_rate": base, "levels": []}
    for level in sorted({row[column] for row in rows}):
        mask = np.array([row[column] == level for row in rows])
        out["levels"].append({
            "level": int(level), "n": int(mask.sum()),
            "winners": int(wins[mask].sum()),
            "win_rate": float(wins[mask].mean()),
            "lift": float(wins[mask].mean() / base) if base > 0 else float("nan"),
        })
    return out


#: The three columns that most obviously ride the clock.  `var_fraction_expected`
#: IS the clock, so any column correlated with it can look powerful for a reason
#: that has nothing to do with volatility.  This control asks the only question
#: that matters: WITHIN a slice of the day, does the column still separate?
CLOCK = "var_fraction_expected"
CLOCK_SLICES = 3


def clock_controlled(rows: list, column: str) -> dict:
    """Terciles of the column computed INSIDE each tercile of the session clock."""
    clock = np.array([row[CLOCK] for row in rows], dtype=np.float64)
    edges = np.quantile(clock, np.linspace(0, 1, CLOCK_SLICES + 1))
    edges[0], edges[-1] = -np.inf, np.inf
    out = []
    for k in range(CLOCK_SLICES):
        inside = [row for row, value in zip(rows, clock)
                  if edges[k] <= value < edges[k + 1]]
        if len(inside) < 30:
            continue
        values = np.array([row[column] for row in inside], dtype=np.float64)
        wins = np.array([row["winner"] for row in inside], dtype=np.float64)
        cuts = np.quantile(values, [1 / 3, 2 / 3])
        low = wins[values <= cuts[0]]
        high = wins[values >= cuts[1]]
        out.append({
            "clock_slice": k + 1, "n": len(inside), "base_rate": float(wins.mean()),
            "low_third_n": int(low.size), "low_third_win_rate": float(low.mean()),
            "high_third_n": int(high.size), "high_third_win_rate": float(high.mean()),
            "high_minus_low": float(high.mean() - low.mean()),
        })
    return {"slices": out,
            "mean_high_minus_low": float(np.mean([s["high_minus_low"] for s in out]))
            if out else float("nan")}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--block", default="study_e3b",
                        help="one block, or a comma-separated list to pool")
    args = parser.parse_args()

    blocks = [name.strip() for name in args.block.split(",") if name.strip()]
    rows = [row for name in blocks for row in join_context(load_ledger(name))]
    report = {
        "block": args.block, "blocks": blocks, "candidates": len(rows),
        "winners": sum(row["winner"] for row in rows),
        "winner_dollars": WINNER_DOLLARS,
        "sessions": sorted({row["session"] for row in rows}),
        "continuous": {}, "categorical": {},
    }
    report["base_rate"] = report["winners"] / len(rows) if rows else float("nan")
    for column in (*CONTINUOUS, *SESSION_LEVEL, "move_z_own"):
        report["continuous"][column] = quintile_table(rows, column)
    for column in ("band_state", "band_state_own"):
        report["categorical"][column] = categorical_table(rows, column)
    report["clock_controlled"] = {
        column: clock_controlled(rows, column) for column in
        ("sigma_inst_bps", "sigma_now_bps", "move_consumed_fraction",
         "range_consumed_fraction", "remaining_move_bps", "rv_sofar_bps",
         "implied_move_bps", "move_z_own")}

    #: THE TELLTALE.  Two axes survived the clock control and replicated across
    #: both study blocks: how hard volatility is firing right now, and whether
    #: price is stretched AGAINST the candidate's own direction (fade) or already
    #: run in its favour (chase).  Their 2x2 is the headline of this contrast.
    hot_cut = float(np.quantile([row["sigma_inst_bps"] for row in rows], 0.6))
    cells = []
    for label, test in (("fade<=-2", lambda r: r["band_state_own"] <= -2),
                        ("mid", lambda r: -2 < r["band_state_own"] < 2),
                        ("chase>=+2", lambda r: r["band_state_own"] >= 2)):
        for heat, hot in (("hot", True), ("cool", False)):
            inside = [row for row in rows
                      if test(row) and ((row["sigma_inst_bps"] >= hot_cut) == hot)]
            if len(inside) < 20:
                continue
            cells.append({
                "extension": label, "vol_state": heat, "n": len(inside),
                "win_rate": float(np.mean([row["winner"] for row in inside])),
                "mean_cert": float(np.mean([row["cert"] for row in inside])),
            })
    report["telltale_2x2"] = {"sigma_inst_hot_cut_bps": hot_cut, "cells": cells}

    out = P.CACHE / "fvol" / f"contrast_{'_'.join(blocks)}.json"
    out.write_text(json.dumps(report, indent=2))

    print(f"block {args.block}: {len(rows)} candidates, {report['winners']} winners "
          f"(>= ${WINNER_DOLLARS:.0f}), base rate {report['base_rate']:.3f}")
    print(f"\n{'column':<26} {'win mean':>10} {'rest mean':>10} {'d':>7}   quintile win-rates")
    for column, block in report["continuous"].items():
        if "buckets" not in block:
            continue
        rates = " ".join(f"{b['win_rate']:.2f}" for b in block["buckets"])
        print(f"{column:<26} {block['winner_mean']:>10.3f} {block['rest_mean']:>10.3f} "
              f"{block['cohens_d']:>+7.2f}   {rates}")
    for column, block in report["categorical"].items():
        print(f"\n{column} (base {block['base_rate']:.3f}):")
        for level in block["levels"]:
            print(f"   {level['level']:+d}  n={level['n']:>4}  win_rate={level['win_rate']:.3f}"
                  f"  lift={level['lift']:.2f}")
    print("\n--- CLOCK-CONTROLLED (top third minus bottom third win rate, "
          "within each third of the session clock) ---")
    print(f"{'column':<26} {'slice1':>8} {'slice2':>8} {'slice3':>8} {'mean':>8}")
    for column, block in report["clock_controlled"].items():
        cells = " ".join(f"{s['high_minus_low']:>+8.3f}" for s in block["slices"])
        print(f"{column:<26} {cells} {block['mean_high_minus_low']:>+8.3f}")
    print(f"\n--- TELLTALE 2x2 (extension against own side x volatility firing) ---")
    print(f"{'extension':<12} {'vol':<6} {'n':>5} {'win_rate':>9} {'mean_cert':>10}")
    for cell in report["telltale_2x2"]["cells"]:
        print(f"{cell['extension']:<12} {cell['vol_state']:<6} {cell['n']:>5} "
              f"{cell['win_rate']:>9.3f} {cell['mean_cert']:>10.0f}")
    print(f"\n{out}")


if __name__ == "__main__":
    main()
