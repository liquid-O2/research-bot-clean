#!/usr/bin/env python3
"""Sweep 7b of the side-resolution mill: the bleed decomposition and the
flipped-fade pricing.

Exploratory tier.  EXPLORE-day bytes only, can kill, cannot promote.  Two
questions, one opportunity set:

1. **Why is the money lost?**  Sweep 5's D-ALONE lines post -149.8 / -215.6 /
   +30.4 usd per asset-day.  The teacher-as-pricer conflates a right-side entry
   taken far too late with a wrong-side entry, so the raw cash says nothing
   about WHICH failure ate it.  Every D-ALONE entry is bucketed by decision
   quality (HARD-WRONG / SOFT-WRONG / RIGHT, read off the cert-lattice REM and
   ``sign(Delta*)`` at the entry bar) crossed with timing (IN-BUDGET / LATE
   against the per-asset O4b delay budget), and a counterfactual ladder
   removes one failure class at a time.  The ladder attributes the bleed.

2. **What does the anti-correlation buy?**  First-quiet side-hit runs 0.36-0.47,
   consistently BELOW coin.  An anti-correlated signal is a signal: flipping
   every fade to the opposite side at the SAME entries is a mechanical
   transform with zero new selection freedom.  Nobody has ever priced it.
   Part 2 prices it.

Laws carried unchanged, imported and never re-implemented: sweep 5's
composition state machine and its D-ALONE reading, sweep 4's candidate plane,
candidate-anchored entry law, cash/day and ``_drawdown`` aggregations, replay
shaping, adversarial stress and delay accounting, sweep 2's ``star_cell``
Delta*/REM law and bar extremes, sweep 1's Wilson interval, asset-day
block-permutation null and ``append_log``.

Stages:

  REPRO   the sweep-5 D-ALONE reproduction, asserted to the cent against
          ``.audit/mill-sweep5.json`` before anything else runs.
  PART 1  the bleed decomposition: bucket table, per-bucket MDD contribution
          and share of loss, and the counterfactual ladder.
  PART 2  the flipped fade, priced: coverage, side agreement with a Wilson CI,
          soft-hit, terminal hit of the FLIPPED side's own extreme, cash,
          drawdowns, engine replay, 2% adversarial stress, block-permutation
          null, and the pre-registered decision table.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import datetime as dt
import json
import os
from pathlib import Path
import sys
import time
from typing import Mapping, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from engine.entry_v2.confirmation_types import NANOS_PER_SECOND

import mill as M
import sweep1 as S1
import sweep2 as S2
import sweep3 as S3
import sweep4 as S4
import sweep5 as S5
import sweep6 as S6

# --------------------------------------------------------------------------
# The immutable law this sweep registers before it reads anything.
# --------------------------------------------------------------------------

SPEC = """QRE2MILLSWEEP7B
tier=exploratory; explore-only; can kill, cannot promote.  parent = the
  hypothesis-log tail at registration.  Charter: mill-side-resolution.md "Why
  can't we decide: the label post-mortem and the anti-correlation lead".
OPPORTUNITY SET (reproduced, never re-derived).  Sweep 5's D-ALONE law at the
  frozen selected configs - HG Q45/H0.30/k1, NKD Q10/H0.20/k1, SI Q30/H0.20/k3,
  zone deleted, no arbiter, no E floor, gate=episode so ONE detection per armed
  extreme, first CLEAR fade-side candidate at or after the detection bar close,
  one entry per cell, candidate-anchored (entry_ts = the candidate's own
  decision_ts_ns), entry_ts <= phase_close - 1800 s.  The reproduction is
  ASSERTED to the cent against .audit/mill-sweep5.json stage B before any
  measurement runs; a mismatch refuses the run.
PART 1 BUCKETS.  Each entry carries a quality and a timing.
  REM(side, bar) = sweep 2's cert-lattice suffix max under the LEGAL variant.
  quality, cascaded in this order:
    HARD-WRONG  REM(traded side, entry bar) <= 0.  Nothing was left on this side.
    SOFT-WRONG  REM > 0 and traded side != sign(Delta*) at the entry bar
                (sign is 0 where the cell is not sharp, which is a miss).
    RIGHT       traded side == sign(Delta*) at the entry bar.
  The cascade means a side-correct entry with non-positive REM buckets
  HARD-WRONG; that overlap is counted and printed, never hidden.
  timing: budget = 45 min (NKD), 60 min (SI), 60 min (HG) measured from the
    faded direction's TRUE terminal extreme bar close (sweep-4 O4b's budget).
    IN-BUDGET when entry_ts <= terminal + budget, else LATE.  A direction that
    never printed a new running extreme has no terminal bar and is IN-BUDGET
    by construction; that count is printed.
  Per asset per bucket: n, cash total, cash/trade, walls, MDD over that
    bucket's own day-sums, and share of gross loss (bucket cash divided by the
    sum of the negative buckets' cash).
COUNTERFACTUAL LADDER, per asset, each rung a strict subset/transform of the one
  above, cash/day and both MDD orderings on every rung:
    (a) ACTUAL             the reproduced D-ALONE line.
    (b) -HARD              HARD-WRONG entries abstain (no trade, not a flip).
    (c) -HARD-LATE         LATE entries also abstain.
    (d) -HARD-LATE+FLIP    the surviving SOFT-WRONG entries are flipped to the
                           Delta* side under the flip law below; a SOFT-WRONG
                           entry whose flip is unavailable abstains.
PART 2 FLIP LAW (mechanical, no selection freedom).  At every entry of the
  reproduced set, the same decision stamp, side = -side, priced from the
  candidate plane's opposite-side arrays at that same candidate row.  LEGAL only
  where an opposite-side CLEAR candidate had already formed at or before the
  stamp and the opposite side is certifiable there - sweep 4's stress-flip
  legality, applied at rate 1.0.  Otherwise UNAVAILABLE and skipped.  hit and
  delay are RE-DERIVED against the FLIPPED side's own terminal extreme.
  Reported per asset and per phase: coverage, side agreement vs sign(Delta*)
  with a Wilson 95% CI, soft-hit (flipped side REM > 0 at the entry bar),
  terminal hit, usd/day against the 2000/1500/1500 rungs, usd/trade, win, wall
  rate, MDD day- and trade-ordered; engine replay per asset (partial-day
  label); a 2% adversarial stress; and an asset-day block-permutation null,
  200 draws, seed 20260827, max-statistic across the three flipped lines and
  the pooled path.
SECOND COHORT.  Sweep 6's ARM-D opportunity set.  Its D arm is built by calling
  sweep 5's comp_entry with comp_for(asset, arbiter=False), which is this
  sweep's D-ALONE comp; the identity is asserted on the config and on the
  recorded sweep-6 coverage.  When identical the duplicate cohort is SKIPPED
  and said to be skipped.
PRE-REGISTERED READING (no multiplicity correction beyond the stated null; the
  flip is mechanical so there is no selection freedom to correct for):
  INTERESTING       side agreement >= 0.55 on NKD and SI, usd/day > 0 on both,
                    wall rate <= 0.25 on both.
  FREEZE CANDIDATE  INTERESTING and, on NKD and SI: usd/day >= the asset's rung,
                    MDD day-ordered < 1000 and MDD trade-ordered < 1000, and
                    stress held (the 2% adversarial line keeps usd/day > 0 and
                    both MDDs under 1000).
  HG is reported and never decides.  Every bound that fires is named.
MUTANT sweep7b: QRE2_MILL_S7B_MUTANT=bucket_uses_future_rem reads REM at bar 0 -
  the suffix max over the FULL lattice, including bars strictly before the entry
  - instead of at the entry bar, so the bucket describes value that was already
  gone.  This is the one branch in this module.
"""

SCHEMA = "QRE2MILLSWEEP7B"
SEED = S1.SEED
ASSETS = S1.ASSETS
BAR_SECONDS = S1.BAR_SECONDS
DAY_RUNG_USD = S1.DAY_RUNG_USD
MDD_CAP_USD = S1.MDD_CAP_USD
NULL_DRAWS = S1.NULL_DRAWS
STRESS_RATE = S4.STRESS_RATE
REPORT_ONLY = ("HG",)
DECIDING = ("NKD", "SI")

# The frozen sweep-5 selection, restated so a drift in the sweep-5 report is a
# refusal rather than a silent change of opportunity set.
FROZEN: dict[str, tuple[int, float, int]] = {
    "HG": (45, 0.30, 1), "NKD": (10, 0.20, 1), "SI": (30, 0.20, 3)}

# Sweep-4 O4b's recognition budget, per asset, in minutes off the TRUE terminal
# extreme.  NKD is the fast asset; the narrowness audit makes speed binding there.
BUDGET_MINUTES: dict[str, int] = {"HG": 60, "NKD": 45, "SI": 60}

QUALITIES = ("HARD-WRONG", "SOFT-WRONG", "RIGHT")
TIMINGS = ("IN-BUDGET", "LATE")
BUCKETS = tuple(f"{quality}/{timing}" for quality in QUALITIES
                for timing in TIMINGS)

LADDER = ("ACTUAL", "-HARD", "-HARD-LATE", "-HARD-LATE+FLIP")

AGREEMENT_BAR = 0.55
WALL_BAR = 0.25

MUTANT_FUTURE_REM = "bucket_uses_future_rem"
MUTANT_ENV = "QRE2_MILL_S7B_MUTANT"
MUTANTS = (MUTANT_FUTURE_REM,)
SELECTION_RULE = "none: mechanical flip, pre-registered reading"
FAMILY = "F4-BLEEDFLIP"

OUT_PATH = ROOT / ".audit/mill-sweep7b.json"
SWEEP5_PATH = ROOT / ".audit/mill-sweep5.json"
SWEEP6_PATH = ROOT / ".audit/mill-sweep6.json"
LOG_PATH = S1.LOG_PATH


class SweepRefusal(RuntimeError):
    pass


SPEC_SHA = S1._sha_text(SPEC)


def code_sha() -> str:
    return S1._sha_file(Path(__file__).resolve())


def _mutant() -> str:
    """This sweep's own mutant switch, validated against its own registry."""

    name = os.environ.get(MUTANT_ENV, "")
    if name and name not in MUTANTS:
        raise SweepRefusal(f"unknown sweep-7b mutant: {name}")
    return name


def _parent_trial() -> str:
    """The hypothesis log's tail id: the chain this sweep hangs off."""

    rows = [line for line in LOG_PATH.read_text().splitlines()[1:] if line.strip()]
    return rows[-1].split("\t")[0] if rows else "sweep5-108"


# --------------------------------------------------------------------------
# REPRO: sweep 5's D-ALONE, reproduced by import and asserted to the cent.
# --------------------------------------------------------------------------

def dalone_comp(asset: str) -> S5.Comp:
    """Sweep 5's D-ALONE control at this asset's frozen selected (Q,H,k)."""

    q, h, k = FROZEN[asset]
    return S5.Comp(S5.comp_key(q, h, k, 0, False), int(q), float(h), int(k), 0,
                   False)


def reproduce(plane: S4.Plane, arbs: Sequence[np.ndarray]
              ) -> tuple[dict[str, list[S4.Entry]], dict[str, object]]:
    """The reproduced D-ALONE entries per asset, plus the cents-exact check.

    Nothing else in this module runs until every asset matches: the whole sweep
    is a statement about sweep 5's set, so an unreproduced set is a refusal.
    """

    sweep5 = json.loads(SWEEP5_PATH.read_text())
    entries: dict[str, list[S4.Entry]] = {}
    check: dict[str, object] = {"source": SWEEP5_PATH.name, "by_asset": {}}
    for asset in ASSETS:
        comp = dalone_comp(asset)
        rows, book = S5.comp_line(plane, arbs, comp, asset)
        entries[asset] = rows
        recorded = sweep5["stage_b"]["lines"][f"{asset}/DALONE"]["summary"]
        line = S4.cash_by_asset(rows, plane)[asset]
        # Cents-exact on cash, and exact on the trade count and the config key:
        # cash alone could match by coincidence, the triple cannot.
        ok = (round(float(line["usd_per_asset_day"]), 2)
              == round(float(recorded["usd_per_asset_day"]), 2)
              and int(line["trades"]) == int(recorded["trades"])
              and comp.key == str(recorded["config"]))
        check["by_asset"][asset] = {
            "config": comp.key, "recorded_config": recorded["config"],
            "usd_per_asset_day": float(line["usd_per_asset_day"]),
            "recorded_usd_per_asset_day": float(recorded["usd_per_asset_day"]),
            "delta_usd": float(line["usd_per_asset_day"])
            - float(recorded["usd_per_asset_day"]),
            "trades": int(line["trades"]),
            "recorded_trades": int(recorded["trades"]),
            "coverage": float(line["coverage"]), "matches": bool(ok),
            "skips": dict(book)}
        if not ok:
            raise SweepRefusal(
                f"D-ALONE reproduction failed on {asset}: "
                f"{line['usd_per_asset_day']} vs {recorded['usd_per_asset_day']}")
    check["all_match"] = True
    check["sweep5_code_sha"] = sweep5["code_sha"]
    return entries, check


def second_cohort(plane: S4.Plane, entries: Mapping[str, list[S4.Entry]]
                  ) -> dict[str, object]:
    """Is sweep 6's ARM-D set the same set?  Assert it, do not assume it.

    Sweep 6 builds ARM-D by calling ``S5.comp_entry`` with
    ``comp_for(asset, arbiter=False)`` over every cell of the asset - the same
    call this module's reproduction makes.  The check is on the config params
    and on the recorded sweep-6 coverage, so it costs no re-run of sweep 6's
    zone machinery.
    """

    sweep6 = json.loads(SWEEP6_PATH.read_text())
    out: dict[str, object] = {"by_asset": {}}
    identical = True
    for asset in ASSETS:
        mine = dalone_comp(asset)
        theirs = S6.comp_for(asset, arbiter=False)
        recorded = sweep6["by_asset"][asset]["arms"]["D"]
        line = S4.cash_by_asset(entries[asset], plane)[asset]
        same = (mine.params == theirs.params and mine.key == theirs.key
                and int(recorded["entered"]) == int(line["trades"])
                and abs(float(recorded["coverage"]) - float(line["coverage"]))
                < 1e-12)
        identical = identical and same
        out["by_asset"][asset] = {
            "sweep7b_config": mine.key, "sweep6_config": theirs.key,
            "sweep6_entered": int(recorded["entered"]),
            "reproduced_entered": int(line["trades"]),
            "sweep6_coverage": float(recorded["coverage"]),
            "reproduced_coverage": float(line["coverage"]), "identical": same}
    out["identical"] = identical
    out["decision"] = ("SKIPPED: sweep-6 ARM-D is the same opportunity set"
                       if identical else "DISTINCT: priced separately")
    return out


# --------------------------------------------------------------------------
# PART 1: the bucket assignment.
# --------------------------------------------------------------------------

def entry_bar(plane: S4.Plane, row: S4.Entry) -> int:
    """The last completed bar at or before the entry's own decision stamp."""

    rec = plane.records[row.cell]
    return int(S5.decision_bar(rec, np.asarray([row.ts_ns], np.int64))[0])


def fade_rem(plane: S4.Plane, row: S4.Entry) -> float:
    """REM of the TRADED side at the entry bar: the cert-lattice suffix max.

    ``QRE2_MILL_S7B_MUTANT=bucket_uses_future_rem`` reads bar 0 instead, which
    is the suffix max over the FULL lattice - it includes cert peaks strictly
    BEFORE the entry, value that was already gone when the trade was taken.  A
    bucket built on that reading calls a dead entry live.  This is the one
    branch in this module.
    """

    star = plane.stars[row.cell]
    bar = 0 if _mutant() == MUTANT_FUTURE_REM else entry_bar(plane, row)
    return float(star.rem(row.side)[bar])


def quality_of(plane: S4.Plane, row: S4.Entry) -> str:
    """HARD-WRONG / SOFT-WRONG / RIGHT, cascaded in that order."""

    if fade_rem(plane, row) <= 0.0:
        return "HARD-WRONG"
    return "RIGHT" if S5.side_hit(plane, row) else "SOFT-WRONG"


def timing_of(plane: S4.Plane, row: S4.Entry) -> str:
    """IN-BUDGET / LATE against the faded direction's own terminal extreme."""

    terminal = plane.terminal_ts(row.cell, row.side)
    if terminal < 0:
        # The direction never printed a new running extreme, so there is no
        # terminal bar to be late against; sweep 4 already counts these as hits.
        return "IN-BUDGET"
    budget = BUDGET_MINUTES[row.asset] * 60 * NANOS_PER_SECOND
    return "IN-BUDGET" if row.ts_ns <= terminal + budget else "LATE"


def bucket_of(plane: S4.Plane, row: S4.Entry) -> str:
    return f"{quality_of(plane, row)}/{timing_of(plane, row)}"


def _bucket_row(rows: Sequence[S4.Entry], asset: str, days: int,
                gross_loss: float) -> dict[str, object]:
    certs = np.asarray([row.cert_usd for row in rows], np.float64)
    total = float(certs.sum()) if len(certs) else 0.0
    return {
        "n": len(rows), "cash_usd": total,
        "usd_per_asset_day": total / max(1, days),
        "usd_per_trade": float(certs.mean()) if len(certs) else None,
        "walls": int(sum(row.wall for row in rows)),
        "wall_rate": (float(np.mean([row.wall for row in rows]))
                      if rows else None),
        "win_rate": float((certs > 0).mean()) if len(certs) else None,
        "mdd_day_usd": S1.asset_mdd_day(rows, asset),
        "mdd_trade_usd": S1.asset_mdd_trade(rows, asset),
        "share_of_gross_loss": (total / gross_loss) if gross_loss else None,
        "entry_delay_median_s": S4._median([row.delay_s for row in rows]),
    }


def decompose(plane: S4.Plane, entries: Mapping[str, list[S4.Entry]]
              ) -> dict[str, object]:
    """The bucket table per asset, with the overlap and no-terminal counts."""

    report: dict[str, object] = {
        "budget_minutes": dict(BUDGET_MINUTES), "buckets": list(BUCKETS),
        "by_asset": {}}
    for asset in sorted(entries):
        rows = entries[asset]
        days = int(plane.days.get(asset, 0))
        by_bucket: dict[str, list[S4.Entry]] = {name: [] for name in BUCKETS}
        for row in rows:
            by_bucket[bucket_of(plane, row)].append(row)
        gross_loss = sum(
            float(sum(item.cert_usd for item in kept))
            for kept in by_bucket.values()
            if float(sum(item.cert_usd for item in kept)) < 0.0)
        table = {name: _bucket_row(by_bucket[name], asset, days, gross_loss)
                 for name in BUCKETS}
        line = S4.cash_by_asset(rows, plane)[asset]
        report["by_asset"][asset] = {
            "cells": plane.cells.get(asset, 0), "days": days,
            "entries": len(rows), "gross_loss_usd": gross_loss,
            "line_usd_per_asset_day": line["usd_per_asset_day"],
            "line_cash_usd": line["total_usd"], "table": table,
            # Honest overlaps: a side-correct entry can still have nothing left,
            # and a direction with no new extreme has no lateness to measure.
            "right_side_but_rem_nonpositive": int(sum(
                1 for row in rows
                if S5.side_hit(plane, row) and fade_rem(plane, row) <= 0.0)),
            "no_terminal_extreme": int(sum(
                1 for row in rows if plane.terminal_ts(row.cell, row.side) < 0)),
            "unsharp_at_entry": int(sum(
                1 for row in rows
                if int(plane.stars[row.cell].sign[entry_bar(plane, row)]) == 0)),
        }
    return report


# --------------------------------------------------------------------------
# The flip law, shared by the ladder's last rung and by PART 2.
# --------------------------------------------------------------------------

def flip_entry(plane: S4.Plane, row: S4.Entry) -> S4.Entry | None:
    """The same decision stamp, the opposite side, priced at the same row.

    Legality is sweep 4's stress-flip law: an opposite-side CLEAR candidate must
    have formed at or before this stamp and the opposite side must be
    certifiable at this row.  ``hit`` and ``delay_s`` are RE-DERIVED against the
    FLIPPED side's own terminal extreme - sweep 4's stress carries the original
    values because it prices damage to one line, while this line is measured on
    its own geometry.  ``detect_bar`` is left on the original side's detection,
    which is what selected the moment; the detect-delay column is therefore not
    reported for flipped lines.
    """

    cell = plane.cands[row.cell]
    other = -int(row.side)
    formed = cell.first_ts(other)
    if formed < 0 or formed > row.ts_ns or not bool(cell.ok(other)[row.bar]):
        return None
    terminal = plane.terminal_ts(row.cell, other)
    return S4.Entry(
        cell=row.cell, asset=row.asset, d8=row.d8, bar=row.bar,
        ts_ns=row.ts_ns, side=other, cert_usd=float(cell.cert(other)[row.bar]),
        wall=bool(cell.wall(other)[row.bar]),
        exit_ts_ns=int(cell.exit_ts(other)[row.bar]), text=row.text,
        raw_cut=row.raw_cut, raw_last=row.raw_last, phase_idx=row.phase_idx,
        detect_bar=row.detect_bar,
        hit=bool(terminal < 0 or row.ts_ns >= terminal),
        delay_s=(float("nan") if terminal < 0
                 else (row.ts_ns - terminal) / NANOS_PER_SECOND))


def flip_line(plane: S4.Plane, rows: Sequence[S4.Entry]
              ) -> tuple[list[S4.Entry], int]:
    """Every entry flipped; the unavailable ones counted and skipped."""

    out: list[S4.Entry] = []
    unavailable = 0
    for row in rows:
        flipped = flip_entry(plane, row)
        if flipped is None:
            unavailable += 1
            continue
        out.append(flipped)
    return out, unavailable


# --------------------------------------------------------------------------
# PART 1: the counterfactual ladder.
# --------------------------------------------------------------------------

def _rung(rows: Sequence[S4.Entry], plane: S4.Plane, asset: str,
          extra: Mapping[str, object]) -> dict[str, object]:
    line = S4.cash_by_asset(rows, plane)[asset]
    keep = ("trades", "coverage", "total_usd", "usd_per_asset_day",
            "usd_per_trade", "win_rate", "wall_rate", "walls", "mdd_day_usd",
            "mdd_trade_usd", "terminal_hit_rate", "rung_usd")
    out = {name: line[name] for name in keep}
    out.update(extra)
    return out


def ladder(plane: S4.Plane, entries: Mapping[str, list[S4.Entry]]
           ) -> dict[str, object]:
    """Remove one failure class at a time; the deltas attribute the bleed."""

    report: dict[str, object] = {"rungs": list(LADDER), "by_asset": {}}
    for asset in sorted(entries):
        rows = entries[asset]
        quality = {id(row): quality_of(plane, row) for row in rows}
        timing = {id(row): timing_of(plane, row) for row in rows}
        no_hard = [row for row in rows if quality[id(row)] != "HARD-WRONG"]
        no_late = [row for row in no_hard if timing[id(row)] != "LATE"]
        flipped: list[S4.Entry] = []
        unavailable = 0
        unsharp = 0
        turned = 0
        for row in no_late:
            if quality[id(row)] != "SOFT-WRONG":
                flipped.append(row)
                continue
            if int(plane.stars[row.cell].sign[entry_bar(plane, row)]) == 0:
                # No Delta* side exists at that bar, so there is nothing to flip
                # TO; the counterfactual abstains rather than inventing a side.
                unsharp += 1
                continue
            other = flip_entry(plane, row)
            if other is None:
                unavailable += 1
                continue
            turned += 1
            flipped.append(other)
        report["by_asset"][asset] = {
            "ACTUAL": _rung(rows, plane, asset, {"removed": 0}),
            "-HARD": _rung(no_hard, plane, asset,
                           {"removed": len(rows) - len(no_hard)}),
            "-HARD-LATE": _rung(no_late, plane, asset,
                                {"removed": len(no_hard) - len(no_late)}),
            "-HARD-LATE+FLIP": _rung(flipped, plane, asset, {
                "flipped": turned, "flip_unavailable": unavailable,
                "flip_unsharp": unsharp}),
        }
    return report


# --------------------------------------------------------------------------
# PART 2: the flipped fade, priced.
# --------------------------------------------------------------------------

def flip_stats(plane: S4.Plane, rows: Sequence[S4.Entry], asset: str,
               cells: int, days: int) -> dict[str, object]:
    certs = np.asarray([row.cert_usd for row in rows], np.float64)
    agree = [S5.side_hit(plane, row) for row in rows]
    soft = [fade_rem(plane, row) > 0.0 for row in rows]
    hits = int(sum(agree))
    low, high = S1.wilson(hits, len(rows))
    return {
        "cells": cells, "trades": len(rows),
        "coverage": len(rows) / max(1, cells),
        "side_agreement": (hits / len(rows)) if rows else None,
        "side_agree_ci95": [low, high],
        "soft_hit_rate": (float(np.mean(soft)) if rows else None),
        "terminal_hit_rate": (float(np.mean([row.hit for row in rows]))
                              if rows else None),
        "joint_hit_rate": (float(np.mean([bool(a and row.hit)
                                          for a, row in zip(agree, rows)]))
                           if rows else None),
        "total_usd": float(certs.sum()) if len(certs) else 0.0,
        "usd_per_asset_day": (float(certs.sum() / max(1, days))
                              if len(certs) else 0.0),
        "usd_per_trade": float(certs.mean()) if len(certs) else None,
        "win_rate": float((certs > 0).mean()) if len(certs) else None,
        "wall_rate": (float(np.mean([row.wall for row in rows]))
                      if rows else None),
        "walls": int(sum(row.wall for row in rows)),
        "mdd_day_usd": S1.asset_mdd_day(rows, asset),
        "mdd_trade_usd": S1.asset_mdd_trade(rows, asset),
        "entry_delay_median_s": S4._median([row.delay_s for row in rows]),
        "entry_seconds_median": S4._median([S4.entry_seconds(plane, row)
                                            for row in rows]),
        "long_fraction": (float(np.mean([row.side > 0 for row in rows]))
                          if rows else None),
        "rung_usd": DAY_RUNG_USD[asset],
    }


def price_flip(plane: S4.Plane, entries: Mapping[str, list[S4.Entry]],
               explore_days: Mapping[str, list[int]]) -> dict[str, object]:
    report: dict[str, object] = {
        "r0_median_gate_mid2": S1.r0_gate(plane.records), "lines": {},
        "base": {}, "replays": {}, "stress": {}, "report_only": list(REPORT_ONLY)}
    priced: dict[str, list[S4.Entry]] = {}
    for asset in ASSETS:
        rows = entries[asset]
        flipped, unavailable = flip_line(plane, rows)
        name = f"{asset}/FLIP"
        priced[name] = flipped
        days = int(plane.days.get(asset, 0))
        cells = plane.cells.get(asset, 0)
        summary = flip_stats(plane, flipped, asset, cells, days)
        summary.update({
            "line_name": name, "config": dalone_comp(asset).key,
            "params": [*FROZEN[asset], BUDGET_MINUTES[asset]],
            "report_only": asset in REPORT_ONLY,
            "base_entries": len(rows), "flip_unavailable": unavailable,
            "flip_coverage_of_base": len(flipped) / max(1, len(rows))})
        by_phase: dict[str, object] = {}
        for phase in plane.phases.get(asset, ()):
            kept = [row for row in flipped if row.phase_idx == phase]
            by_phase[str(phase)] = flip_stats(
                plane, kept, asset, plane.phase_cells.get((asset, phase), 0),
                days)
        report["lines"][name] = {"summary": summary, "by_phase": by_phase}
        # The base line beside it, so the flip's delta is a number on the page.
        base = flip_stats(plane, rows, asset, cells, days)
        report["base"][f"{asset}/BASE"] = base
        report["lines"][name]["flip_delta"] = {
            key: (None if summary[key] is None or base[key] is None
                  else float(summary[key]) - float(base[key]))
            for key in ("side_agreement", "soft_hit_rate", "terminal_hit_rate",
                        "usd_per_asset_day", "usd_per_trade", "win_rate",
                        "wall_rate", "mdd_day_usd", "mdd_trade_usd")}
        report["replays"][name] = S4.replay_line(
            flipped, plane.records, (asset,),
            f"mill-sweep7b:{code_sha()[:16]}:{name.replace('/', '-')}")
        report["stress"][name] = S4.stress_line(flipped, plane, asset,
                                                STRESS_RATE)
    report["nulls"] = S1.block_null(priced, explore_days, draws=NULL_DRAWS,
                                    seed=SEED)
    return report


def decide(report: Mapping[str, object]) -> dict[str, object]:
    """The pre-registered reading.  Every bound that fires is named."""

    fired: list[str] = []
    interesting = True
    freeze = True
    per_asset: dict[str, object] = {}
    for asset in DECIDING:
        line = report["lines"][f"{asset}/FLIP"]["summary"]
        stress = report["stress"][f"{asset}/FLIP"]
        agreement = line["side_agreement"]
        usd = line["usd_per_asset_day"]
        wall = line["wall_rate"]
        tests = {
            "agreement>=0.55": agreement is not None and agreement >= AGREEMENT_BAR,
            "usd_day>0": usd is not None and usd > 0.0,
            "wall<=0.25": wall is not None and wall <= WALL_BAR,
        }
        rungs = {
            "usd_day>=rung": usd is not None and usd >= DAY_RUNG_USD[asset],
            "mdd_day<1000": abs(float(line["mdd_day_usd"])) < MDD_CAP_USD,
            "mdd_trade<1000": abs(float(line["mdd_trade_usd"])) < MDD_CAP_USD,
            "stress_held": (float(stress["usd_per_asset_day"]) > 0.0
                            and abs(float(stress["mdd_day_usd"])) < MDD_CAP_USD
                            and abs(float(stress["mdd_trade_usd"])) < MDD_CAP_USD),
        }
        for name, ok in list(tests.items()) + list(rungs.items()):
            if not ok:
                fired.append(f"{asset}:{name}")
        interesting = interesting and all(tests.values())
        freeze = freeze and all(tests.values()) and all(rungs.values())
        per_asset[asset] = {
            "side_agreement": agreement, "usd_per_asset_day": usd,
            "wall_rate": wall, "mdd_day_usd": line["mdd_day_usd"],
            "mdd_trade_usd": line["mdd_trade_usd"],
            "stress_usd_per_asset_day": stress["usd_per_asset_day"],
            "interesting_tests": tests, "freeze_tests": rungs}
    return {"interesting": bool(interesting),
            "freeze_candidate": bool(freeze and interesting),
            "bounds_fired": fired, "by_asset": per_asset,
            "deciding": list(DECIDING), "report_only": list(REPORT_ONLY),
            "bars": {"agreement": AGREEMENT_BAR, "wall": WALL_BAR,
                     "mdd_cap": MDD_CAP_USD, "rungs": dict(DAY_RUNG_USD)}}


# --------------------------------------------------------------------------
# Hypothesis log.
# --------------------------------------------------------------------------

def log_rows(report: Mapping[str, object]) -> list[dict[str, object]]:
    stamp = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    shared = {
        "registered_utc": stamp, "spec_sha": SPEC_SHA, "code_sha": code_sha(),
        "split_sha": S4.split_sha(), "outcome_law_sha": S4.outcome_law_sha(),
        "null_seed": SEED, "parent_trial": report["parent_trial"],
        "selection_rule": SELECTION_RULE, "verdict": "",
        "days": sum(report["asset_days"].values())}
    miss = {"HG": "err_rate_hg", "NKD": "err_rate_nkd", "SI": "err_rate_si"}
    usd = {"HG": "hg_usd_day", "NKD": "nkd_usd_day", "SI": "si_usd_day"}
    mdd = {"HG": "mdd_hg", "NKD": "mdd_nkd", "SI": "mdd_si"}
    walls = {"HG": "walls_hg", "NKD": "walls_nkd", "SI": "walls_si"}
    rows: list[dict[str, object]] = []
    counter = 0
    for asset in ASSETS:
        block = report["part1_decomposition"]["by_asset"][asset]
        rung = report["part1_ladder"]["by_asset"][asset]["ACTUAL"]
        hard = block["table"]["HARD-WRONG/IN-BUDGET"]["n"] \
            + block["table"]["HARD-WRONG/LATE"]["n"]
        counter += 1
        rows.append({
            **shared, "id": f"sweep7b-{counter:03d}", "family": FAMILY,
            "rule": f"{asset}/DECOMP", "params": json.dumps(
                [*FROZEN[asset], BUDGET_MINUTES[asset]]),
            "coverage": rung["coverage"], "delay_med_s": None,
            miss[asset]: (hard / max(1, block["entries"])),
            walls[asset]: rung["walls"], usd[asset]: rung["usd_per_asset_day"],
            mdd[asset]: rung["mdd_day_usd"],
            "note": f"part1 bleed hard_frac; n={block['entries']}"[:60]})
    nulls = report["part2_flip"]["nulls"]["by_line"]
    replays = report["part2_flip"]["replays"]
    for asset in ASSETS:
        name = f"{asset}/FLIP"
        line = report["part2_flip"]["lines"][name]["summary"]
        counter += 1
        skips: object = ""
        if replays.get(name, {}).get("status") == "OK":
            skips = replays[name]["occupancy_or_cap_skips"]
        agreement = line["side_agreement"]
        rows.append({
            **shared, "id": f"sweep7b-{counter:03d}", "family": FAMILY,
            "rule": name, "params": json.dumps(line["params"]),
            "coverage": line["coverage"],
            "delay_med_s": line["entry_delay_median_s"],
            miss[asset]: None if agreement is None else 1.0 - float(agreement),
            walls[asset]: line["walls"], usd[asset]: line["usd_per_asset_day"],
            mdd[asset]: line["mdd_day_usd"], "replay_skips": skips,
            "null_margin": nulls.get(name, {}).get("p_max_adjusted"),
            "note": f"part2 flipped fade {line['config']}"[:60]})
    return rows


# --------------------------------------------------------------------------
# Report I/O and printing.
# --------------------------------------------------------------------------

def read_report() -> dict[str, object]:
    if OUT_PATH.is_file():
        return json.loads(OUT_PATH.read_text())
    return {"schema": SCHEMA, "tier": "exploratory",
            "claim": "EXPLORE-day sweep 7b: the D-ALONE bleed decomposition "
                     "and the mechanically flipped fade; can kill, cannot promote"}


def write_report(report: Mapping[str, object]) -> None:
    payload = {key: value for key, value in report.items()
               if not key.startswith("_")}
    OUT_PATH.write_text(json.dumps(payload, sort_keys=True, indent=1,
                                   default=S1._json_default) + "\n")


def _num(value: object, width: int = 8, digits: int = 2) -> str:
    return S1._num(value, width, digits)


def print_repro(block: Mapping[str, object]) -> None:
    print("\n== REPRO: sweep-5 D-ALONE, reproduced by import (cents-exact gate)")
    print(f"  {'asset':6s} {'config':22s} {'trades':>7s} {'usd/day':>12s} "
          f"{'sweep5 usd/day':>16s} {'delta':>10s} {'match':>6s}")
    for asset in ASSETS:
        row = block["by_asset"][asset]
        print(f"  {asset:6s} {row['config']:22s} {row['trades']:7d} "
              f"{row['usd_per_asset_day']:12.10f} "
              f"{row['recorded_usd_per_asset_day']:16.10f} "
              f"{row['delta_usd']:10.2f} {str(row['matches']):>6s}")


def print_cohort(block: Mapping[str, object]) -> None:
    print("\n== SECOND COHORT: sweep-6 ARM-D")
    for asset in ASSETS:
        row = block["by_asset"][asset]
        print(f"  {asset:6s} sweep7b={row['sweep7b_config']:22s} "
              f"sweep6={row['sweep6_config']:22s} "
              f"n {row['reproduced_entered']:4d}/{row['sweep6_entered']:4d} "
              f"cov {row['reproduced_coverage']:.6f}/{row['sweep6_coverage']:.6f} "
              f"identical={row['identical']}")
    print(f"  {block['decision']}")


BUCKET_HEAD = (f"{'n':>5s} {'cash_usd':>11s} {'usd/day':>9s} {'usd/trd':>9s} "
               f"{'walls':>6s} {'wall':>6s} {'win':>6s} {'mdd_day':>9s} "
               f"{'mdd_trd':>9s} {'loss_sh':>8s} {'dly50':>8s}")


def _bucket_line(row: Mapping[str, object]) -> str:
    return (f"{row['n']:5d} {_num(row['cash_usd'], 11, 1)} "
            f"{_num(row['usd_per_asset_day'], 9, 1)} "
            f"{_num(row['usd_per_trade'], 9, 1)} {row['walls']:6d} "
            f"{_num(row['wall_rate'], 6, 3)} {_num(row['win_rate'], 6, 3)} "
            f"{_num(row['mdd_day_usd'], 9, 1)} {_num(row['mdd_trade_usd'], 9, 1)} "
            f"{_num(row['share_of_gross_loss'], 8, 3)} "
            f"{_num(row['entry_delay_median_s'], 8, 0)}")


def print_decomposition(block: Mapping[str, object]) -> None:
    print("\n== PART 1: the bleed decomposition (quality x timing) on the "
          "reproduced D-ALONE entries")
    print("   quality cascade: HARD-WRONG (fade REM <= 0 at the entry bar) > "
          "SOFT-WRONG (REM > 0, side != sign(Delta*)) > RIGHT")
    print("   timing: IN-BUDGET = entry <= the faded direction's terminal "
          f"extreme + {block['budget_minutes']} min")
    for asset in ASSETS:
        row = block["by_asset"][asset]
        print(f"\n-- {asset}  cells={row['cells']} days={row['days']} "
              f"entries={row['entries']}  line={row['line_usd_per_asset_day']:.1f} "
              f"usd/day  gross_loss={row['gross_loss_usd']:.1f} usd")
        print(f"  {'bucket':22s} {BUCKET_HEAD}")
        for name in BUCKETS:
            print(f"  {name:22s} {_bucket_line(row['table'][name])}")
        print(f"  overlaps: side-correct with REM<=0 (bucketed HARD) = "
              f"{row['right_side_but_rem_nonpositive']}; entries whose faded "
              f"direction never printed a new extreme = "
              f"{row['no_terminal_extreme']}; unsharp at the entry bar = "
              f"{row['unsharp_at_entry']}")


LADDER_HEAD = (f"{'trd':>5s} {'cov':>6s} {'usd/day':>9s} {'usd/trd':>9s} "
               f"{'win':>6s} {'wall':>6s} {'mdd_day':>9s} {'mdd_trd':>9s} "
               f"{'term':>6s}")


def _ladder_line(row: Mapping[str, object]) -> str:
    return (f"{row['trades']:5d} {_num(row['coverage'], 6, 3)} "
            f"{_num(row['usd_per_asset_day'], 9, 1)} "
            f"{_num(row['usd_per_trade'], 9, 1)} {_num(row['win_rate'], 6, 3)} "
            f"{_num(row['wall_rate'], 6, 3)} {_num(row['mdd_day_usd'], 9, 1)} "
            f"{_num(row['mdd_trade_usd'], 9, 1)} "
            f"{_num(row['terminal_hit_rate'], 6, 3)}")


def print_ladder(block: Mapping[str, object]) -> None:
    print("\n== PART 1: the counterfactual ladder (each rung removes one "
          "failure class; abstain, never a free trade)")
    print(f"{'asset':6s} {'rung':18s} {LADDER_HEAD} {'note':>28s}")
    for asset in ASSETS:
        rows = block["by_asset"][asset]
        for name in LADDER:
            row = rows[name]
            note = (f"flipped={row.get('flipped')} "
                    f"unavail={row.get('flip_unavailable')} "
                    f"unsharp={row.get('flip_unsharp')}"
                    if "flipped" in row else f"removed={row.get('removed')}")
            print(f"{asset:6s} {name:18s} {_ladder_line(row)} {note:>28s}")


FLIP_HEAD = (f"{'trd':>5s} {'cov':>6s} {'agree':>6s} {'ci_lo':>6s} {'ci_hi':>6s} "
             f"{'soft':>6s} {'term':>6s} {'usd/day':>9s} {'usd/trd':>9s} "
             f"{'win':>6s} {'wall':>6s} {'mdd_day':>9s} {'mdd_trd':>9s}")


def _flip_line(row: Mapping[str, object]) -> str:
    return (f"{row['trades']:5d} {_num(row['coverage'], 6, 3)} "
            f"{_num(row['side_agreement'], 6, 3)} "
            f"{_num(row['side_agree_ci95'][0], 6, 3)} "
            f"{_num(row['side_agree_ci95'][1], 6, 3)} "
            f"{_num(row['soft_hit_rate'], 6, 3)} "
            f"{_num(row['terminal_hit_rate'], 6, 3)} "
            f"{_num(row['usd_per_asset_day'], 9, 1)} "
            f"{_num(row['usd_per_trade'], 9, 1)} {_num(row['win_rate'], 6, 3)} "
            f"{_num(row['wall_rate'], 6, 3)} {_num(row['mdd_day_usd'], 9, 1)} "
            f"{_num(row['mdd_trade_usd'], 9, 1)}")


def print_flip(block: Mapping[str, object]) -> None:
    print("\n== PART 2: the flipped fade, priced (same entries, side negated, "
          "sweep-4 stress-flip legality at rate 1.0)")
    print(f"{'line':16s} {'ph':>3s} {FLIP_HEAD} {'rung':>6s}")
    for asset in ASSETS:
        name = f"{asset}/FLIP"
        row = block["lines"][name]["summary"]
        print(f"{name:16s} {'-':>3s} {_flip_line(row)} {row['rung_usd']:6.0f}")
        for phase, prow in sorted(block["lines"][name]["by_phase"].items()):
            print(f"{'':16s} {phase:>3s} {_flip_line(prow)}")
        base = block["base"][f"{asset}/BASE"]
        print(f"{asset + '/BASE':16s} {'-':>3s} {_flip_line(base)}")
        print(f"  unavailable flips: {row['flip_unavailable']} of "
              f"{row['base_entries']} base entries "
              f"({row['flip_coverage_of_base']:.3f} kept)")
    print("\n-- the flip's delta over its own base line")
    print(f"  {'asset':6s} {'d_agree':>8s} {'d_soft':>8s} {'d_term':>8s} "
          f"{'d_usd/day':>10s} {'d_usd/trd':>10s} {'d_win':>7s} {'d_wall':>7s} "
          f"{'d_mdd_day':>10s} {'d_mdd_trd':>10s}")
    for asset in ASSETS:
        row = block["lines"][f"{asset}/FLIP"]["flip_delta"]
        print(f"  {asset:6s} {_num(row['side_agreement'], 8, 3)} "
              f"{_num(row['soft_hit_rate'], 8, 3)} "
              f"{_num(row['terminal_hit_rate'], 8, 3)} "
              f"{_num(row['usd_per_asset_day'], 10, 1)} "
              f"{_num(row['usd_per_trade'], 10, 1)} "
              f"{_num(row['win_rate'], 7, 3)} {_num(row['wall_rate'], 7, 3)} "
              f"{_num(row['mdd_day_usd'], 10, 1)} "
              f"{_num(row['mdd_trade_usd'], 10, 1)}")
    print("\n-- engine replay (partial-day: the split breaks portfolio days)")
    for name in sorted(block["replays"]):
        row = block["replays"][name]
        if row.get("status") != "OK":
            print(f"  {name:16s} {row.get('status')}")
            continue
        print(f"  {name:16s} {row['label']}  days={row['asset_days']:4d} "
              f"trades={row['trades']:4d} "
              f"usd/day={row['usd_per_asset_day']:9.1f} "
              f"usd/trd={row['usd_per_trade']:8.1f} "
              f"mdd={row['max_drawdown_usd']:9.1f} "
              f"breach={row['drawdown_breach_rate']:.3f} "
              f"skips={row['occupancy_or_cap_skips']:3d}")
    print(f"\n-- {STRESS_RATE:.0%} adversarial stress on each flipped line")
    print(f"  {'line':16s} {'flips':>6s} {'avail':>6s} {'usd/day':>9s} "
          f"{'usd/trd':>9s} {'wall':>6s} {'mdd_day':>9s} {'mdd_trd':>9s}")
    for name in sorted(block["stress"]):
        row = block["stress"][name]
        print(f"  {name:16s} {row['flips_applied']:6d} "
              f"{row['flips_available']:6d} "
              f"{_num(row['usd_per_asset_day'], 9, 1)} "
              f"{_num(row['usd_per_trade'], 9, 1)} "
              f"{_num(row['wall_rate'], 6, 3)} "
              f"{_num(row['mdd_day_usd'], 9, 1)} "
              f"{_num(row['mdd_trade_usd'], 9, 1)}")
    nulls = block["nulls"]
    print(f"\n-- block-permutation null, {nulls['draws']} draws, seed "
          f"{nulls['seed']}, max-statistic across the three flipped lines "
          "and the pooled path")
    print(f"  {'line':16s} {'obs_mdd':>9s} {'null_mean':>10s} {'p_own':>7s} "
          f"{'p_adj':>7s} {'pool_obs':>9s} {'p_pool':>7s} {'p_pool_adj':>10s}")
    for name in sorted(nulls["by_line"]):
        row = nulls["by_line"][name]
        print(f"  {name:16s} {row['observed_max_asset_mdd_usd']:9.1f} "
              f"{row['null_asset_mdd_mean_usd']:10.1f} {row['p_own']:7.3f} "
              f"{row['p_max_adjusted']:7.3f} "
              f"{row['observed_pooled_mdd_usd']:9.1f} "
              f"{row['p_pooled_own']:7.3f} {row['p_pooled_max_adjusted']:10.3f}")
    if nulls["lines_held_out_empty"]:
        print(f"  held out (no entries): "
              f"{', '.join(nulls['lines_held_out_empty'])}")


def print_decision(block: Mapping[str, object]) -> None:
    print("\n== DECISION TABLE (pre-registered; HG reports and never decides)")
    print(f"  INTERESTING      = agreement >= {AGREEMENT_BAR:.2f} on NKD and SI "
          f"AND usd/day > 0 on both AND wall <= {WALL_BAR:.2f} on both")
    print(f"  FREEZE CANDIDATE = INTERESTING and, on both, usd/day >= the rung, "
          f"both MDD orderings < {MDD_CAP_USD:.0f}, stress held")
    print(f"  {'asset':6s} {'agree':>7s} {'usd/day':>9s} {'wall':>6s} "
          f"{'mdd_day':>9s} {'mdd_trd':>9s} {'stress/day':>11s} "
          f"{'interesting':>12s} {'freeze':>7s}")
    for asset in block["deciding"]:
        row = block["by_asset"][asset]
        print(f"  {asset:6s} {_num(row['side_agreement'], 7, 3)} "
              f"{_num(row['usd_per_asset_day'], 9, 1)} "
              f"{_num(row['wall_rate'], 6, 3)} "
              f"{_num(row['mdd_day_usd'], 9, 1)} "
              f"{_num(row['mdd_trade_usd'], 9, 1)} "
              f"{_num(row['stress_usd_per_asset_day'], 11, 1)} "
              f"{str(all(row['interesting_tests'].values())):>12s} "
              f"{str(all(row['freeze_tests'].values())):>7s}")
    print(f"  INTERESTING={block['interesting']}  "
          f"FREEZE_CANDIDATE={block['freeze_candidate']}")
    print(f"  bounds fired: {', '.join(block['bounds_fired']) or 'none'}")


# --------------------------------------------------------------------------
# Selftest: synthetic arrays only, zero era bytes.
# --------------------------------------------------------------------------

SELFTEST_ASSET = S4.SELFTEST_ASSET
BARS = 120
FLAT = 9_200_000_000
LOW = 9_150_000_000
UP = 9_230_000_000
IN_BAR = 45          # 2700 s: inside HG's 60 min budget off the bar-20 low
LATE_BAR = 85        # 5100 s: past 1200 + 3600 s, and inside the 5400 s deadline
SHORT_BAR = 40       # a short candidate that forms before the long entry


def _series() -> list[int]:
    """Bars 0-19 flat, bar 20 the only new running low, bars 21+ recovered.

    The only long-fade detection is the bar-20 low's, declared at bar 30 by
    Q=10/H=0.10/k=1 (retrace 8.0e7/8.0e7 = 1.0 ATR).  The short side never
    holds a retrace, so exactly one entry per cell and its side is LONG.  The
    terminal long-fade extreme is bar 20 = 1200 s, so the HG budget boundary is
    1200 + 3600 = 4800 s: bar 45 (2700 s) is IN-BUDGET and bar 85 (5100 s) LATE.
    """

    return [FLAT] * 20 + [LOW] + [UP] * (BARS - 21)


def _cell(text: str, cert_p: Sequence[float], cert_m: Sequence[float]
          ) -> S1.CellRec:
    """A synthetic cell with hand-set lattice certs, every bar legal and ok."""

    mid = _series()
    n = len(mid)
    lat = np.arange(n, dtype=np.int64) * S1.BAR_NS
    return S1.CellRec(
        asset=SELFTEST_ASSET, d8=20220301, phase="0", text=text,
        phase_open_ts_ns=0, phase_close_ts_ns=int(n * S1.BAR_NS),
        locked_iid=1, pack_sha256="0" * 64, raw_first=0, k0=1, r0_mid2=100.0,
        legal_from_p=0, legal_from_m=0, lat=lat,
        mid=np.asarray(mid, np.int64), bar_ok=np.ones(n, bool),
        cost=np.full(n, 20.0), cert_p=np.asarray(cert_p, np.float64),
        cert_m=np.asarray(cert_m, np.float64), ok_p=np.ones(n, bool),
        ok_m=np.ones(n, bool), wall_p=np.zeros(n, bool),
        wall_m=np.zeros(n, bool), exit_p=lat.copy(), exit_m=lat.copy(),
        cum_long=np.zeros(n, np.int32), cum_short=np.zeros(n, np.int32),
        raw_cut=np.zeros(n, np.int64), raw_last=np.zeros(n, np.int64))


def _cands(rec: S1.CellRec, rows: Sequence[tuple[int, int]],
           cert_p: Sequence[float], cert_m: Sequence[float]) -> S4.CandCell:
    """A synthetic candidate plane with hand-set per-row certs on both sides."""

    stamps = np.asarray([int(rec.lat[bar]) for bar, _side in rows], np.int64)
    sides = np.asarray([int(side) for _bar, side in rows], np.int8)
    n = len(stamps)
    return S4.CandCell(
        text=rec.text, phase_idx=0,
        first_ts_p=int(stamps[sides > 0].min()) if int((sides > 0).sum()) else -1,
        first_ts_m=int(stamps[sides < 0].min()) if int((sides < 0).sum()) else -1,
        ts=stamps, side=sides, cand_mid2=np.zeros(n, np.int64),
        quote_mid2=np.zeros(n, np.int64), cost=np.full(n, 20.0),
        anchor_ts=S4.bar_anchor_ts(stamps, int(rec.phase_open_ts_ns)),
        raw_cut=np.zeros(n, np.int64), raw_last=np.zeros(n, np.int64),
        cert_p=np.asarray(cert_p, np.float64),
        cert_m=np.asarray(cert_m, np.float64), wall_p=np.zeros(n, np.bool_),
        wall_m=np.zeros(n, np.bool_), exit_p=stamps.copy(),
        exit_m=stamps.copy(), ok_p=np.ones(n, np.bool_),
        ok_m=np.ones(n, np.bool_))


def _flat(at: Mapping[int, float] | None = None) -> list[float]:
    """A zero cert lattice with the named bars set to their hand values."""

    out = [0.0] * BARS
    for bar, amount in (at or {}).items():
        out[bar] = float(amount)
    return out


def _hard_certs() -> list[float]:
    """+800 at bar 10, -50 from bar 11 on: REM at bar 45 is -50, at bar 0 +800.

    The suffix max from any entry bar past 10 is -50, so the entry is
    HARD-WRONG; the suffix max from bar 0 is +800, which is exactly the value
    the mutant reads and exactly the value that was already gone.
    """

    out = [0.0] * 11
    out[10] = 800.0
    return out + [-50.0] * (BARS - 11)


# (text, lattice cert_p, lattice cert_m, candidate rows, cand cert_p,
#  cand cert_m, expected bucket).  One cell per bucket class.
def _fixture() -> list[tuple[str, list[float], list[float],
                             list[tuple[int, int]], list[float], list[float],
                             str]]:
    right_p = _flat({100: 500.0})
    soft_p = _flat({100: 200.0})
    soft_m = _flat({100: 500.0})
    zero = _flat()
    return [
        # RIGHT: Delta*(45) = 500 - 0 = +500 > band 100, sign +1 == side.
        ("HG/C1", right_p, zero, [(IN_BAR, 1)], [100.0], [0.0],
         "RIGHT/IN-BUDGET"),
        ("HG/C2", right_p, zero, [(LATE_BAR, 1)], [40.0], [0.0], "RIGHT/LATE"),
        # SOFT-WRONG: REM_p = 200 > 0 but Delta*(45) = 200 - 500 = -300, sign -1.
        # C3 carries a short candidate at bar 40 so its flip is legal.
        ("HG/C3", soft_p, soft_m, [(SHORT_BAR, -1), (IN_BAR, 1)],
         [0.0, -300.0], [0.0, 250.0], "SOFT-WRONG/IN-BUDGET"),
        ("HG/C4", soft_p, soft_m, [(LATE_BAR, 1)], [-200.0], [0.0],
         "SOFT-WRONG/LATE"),
        # HARD-WRONG: REM_p at the entry bar is -50 <= 0; Delta* = -50, inside
        # the max(2*cost,100) band, so the cell is not sharp there either.
        ("HG/C5", _hard_certs(), zero, [(IN_BAR, 1)], [-700.0], [0.0],
         "HARD-WRONG/IN-BUDGET"),
        ("HG/C6", _hard_certs(), zero, [(LATE_BAR, 1)], [-500.0], [0.0],
         "HARD-WRONG/LATE"),
    ]


def _fixture_plane() -> tuple[S4.Plane, list[S4.Entry], list[str]]:
    records: list[S1.CellRec] = []
    cands: list[S4.CandCell] = []
    expected: list[str] = []
    for text, lat_p, lat_m, rows, cand_p, cand_m, bucket in _fixture():
        rec = _cell(text, lat_p, lat_m)
        records.append(rec)
        cands.append(_cands(rec, rows, cand_p, cand_m))
        expected.append(bucket)
    plane = S4._selftest_plane(records, cands)
    arbs = [S5.arbiter_series(rec) for rec in records]
    comp = S5.Comp(S5.comp_key(10, 0.10, 1, 0, False), 10, 0.10, 1, 0, False)
    entries: list[S4.Entry] = []
    for position in range(len(records)):
        entry, reason, _a, _e = S5.comp_entry(plane, arbs, position, comp)
        if entry is None:
            raise SweepRefusal(f"fixture cell {position} abstained: {reason}")
        entries.append(entry)
    return plane, entries, expected


def _selftest_buckets() -> list[tuple[str, bool, str]]:
    """One entry per bucket class, each hand-assigned."""

    plane, entries, expected = _fixture_plane()
    seen = [bucket_of(plane, row) for row in entries]
    rems = [round(fade_rem(plane, row), 2) for row in entries]
    signs = [int(plane.stars[row.cell].sign[entry_bar(plane, row)])
             for row in entries]
    bars = [entry_bar(plane, row) for row in entries]
    return [
        ("every_fixture_cell_enters_long_at_its_hand_bar",
         all(row.side == 1 for row in entries)
         and bars == [IN_BAR, LATE_BAR, IN_BAR, LATE_BAR, IN_BAR, LATE_BAR],
         f"bars={bars} sides={[row.side for row in entries]}"),
        ("the_six_hand_buckets_are_the_six_measured_buckets",
         seen == expected, f"{seen} expected {expected}"),
        ("the_hand_rem_values_are_the_measured_rem_values",
         rems == [500.0, 500.0, 200.0, 200.0, -50.0, -50.0], f"{rems}"),
        ("the_hand_delta_star_signs_are_the_measured_signs",
         signs == [1, 1, -1, -1, 0, 0], f"{signs}"),
        ("the_budget_boundary_is_the_terminal_extreme_plus_the_asset_budget",
         plane.terminal_ts(0, 1) == 20 * S1.BAR_NS
         and BUDGET_MINUTES[SELFTEST_ASSET] == 60
         and int(plane.records[0].lat[IN_BAR]) <= 20 * S1.BAR_NS + 3600 * NANOS_PER_SECOND
         and int(plane.records[0].lat[LATE_BAR]) > 20 * S1.BAR_NS + 3600 * NANOS_PER_SECOND,
         f"terminal={plane.terminal_ts(0, 1)} in={int(plane.records[0].lat[IN_BAR])} "
         f"late={int(plane.records[0].lat[LATE_BAR])}"),
        ("a_side_correct_entry_with_dead_rem_buckets_hard_not_right",
         quality_of(plane, entries[4]) == "HARD-WRONG"
         and not S5.side_hit(plane, entries[4]),
         f"{quality_of(plane, entries[4])}"),
    ]


def _selftest_flip() -> list[tuple[str, bool, str]]:
    """The hand-computed flip: side, candidate row, and cash sign."""

    plane, entries, _expected = _fixture_plane()
    c1 = flip_entry(plane, entries[0])
    c3 = flip_entry(plane, entries[2])
    flipped, unavailable = flip_line(plane, entries)
    return [
        ("a_cell_with_no_opposite_side_candidate_cannot_be_flipped",
         c1 is None and plane.cands[0].first_ts_m == -1,
         f"flip={c1} first_ts_m={plane.cands[0].first_ts_m}"),
        ("the_flip_takes_the_opposite_side_at_the_same_candidate_row",
         c3 is not None and c3.side == -1 and c3.bar == entries[2].bar == 1
         and c3.ts_ns == entries[2].ts_ns,
         f"side={None if c3 is None else c3.side} "
         f"bar={None if c3 is None else c3.bar}"),
        ("the_flipped_cash_is_the_hand_value_and_flips_sign",
         c3 is not None and c3.cert_usd == 250.0
         and entries[2].cert_usd == -300.0,
         f"flip={None if c3 is None else c3.cert_usd} base={entries[2].cert_usd}"),
        ("the_flipped_hit_is_read_off_the_flipped_sides_own_extreme",
         c3 is not None and plane.terminal_ts(2, -1) == 21 * S1.BAR_NS
         and c3.hit and c3.delay_s == float(IN_BAR - 21) * S1.BAR_SECONDS,
         f"terminal={plane.terminal_ts(2, -1)} hit="
         f"{None if c3 is None else c3.hit} "
         f"delay={None if c3 is None else c3.delay_s}"),
        ("only_the_cell_with_a_formed_opposite_candidate_survives_the_flip",
         len(flipped) == 1 and unavailable == 5,
         f"flipped={len(flipped)} unavailable={unavailable}"),
    ]


def _selftest_ladder() -> list[tuple[str, bool, str]]:
    """The ladder arithmetic, hand-summed over the six fixture cells.

    ACTUAL = 100 + 40 - 300 - 200 - 700 - 500 = -1560.  Dropping the two
    HARD-WRONG cells leaves -360; dropping the two LATE survivors leaves -200;
    flipping the one SOFT-WRONG survivor from -300 to +250 leaves +350.
    """

    plane, entries, _expected = _fixture_plane()
    block = ladder(plane, {SELFTEST_ASSET: entries})["by_asset"][SELFTEST_ASSET]
    values = {name: round(float(block[name]["total_usd"]), 6) for name in LADDER}
    hand = {"ACTUAL": -1560.0, "-HARD": -360.0, "-HARD-LATE": -200.0,
            "-HARD-LATE+FLIP": 350.0}
    counts = {name: int(block[name]["trades"]) for name in LADDER}
    table = decompose(plane, {SELFTEST_ASSET: entries})
    row = table["by_asset"][SELFTEST_ASSET]
    shares = {name: row["table"][name]["share_of_gross_loss"]
              for name in BUCKETS}
    return [
        ("the_ladder_totals_are_the_hand_totals", values == hand,
         f"{values} expected {hand}"),
        ("each_rung_is_a_strict_subset_or_transform_of_the_one_above",
         counts == {"ACTUAL": 6, "-HARD": 4, "-HARD-LATE": 2,
                    "-HARD-LATE+FLIP": 2}, f"{counts}"),
        ("the_flip_rung_reports_its_one_flip_and_no_unavailable",
         block["-HARD-LATE+FLIP"]["flipped"] == 1
         and block["-HARD-LATE+FLIP"]["flip_unavailable"] == 0
         and block["-HARD-LATE+FLIP"]["flip_unsharp"] == 0,
         f"{block['-HARD-LATE+FLIP']}"),
        ("the_gross_loss_is_the_sum_of_the_negative_buckets",
         round(float(row["gross_loss_usd"]), 6) == -1700.0,
         f"{row['gross_loss_usd']} expected -1700"),
        ("the_hard_in_budget_bucket_carries_its_hand_share_of_the_loss",
         abs(float(shares["HARD-WRONG/IN-BUDGET"]) - (-700.0 / -1700.0)) < 1e-12
         and shares["RIGHT/IN-BUDGET"] is not None,
         f"{shares['HARD-WRONG/IN-BUDGET']}"),
        ("the_bucket_cash_adds_back_to_the_line_cash",
         abs(sum(float(row["table"][name]["cash_usd"]) for name in BUCKETS)
             - float(row["line_cash_usd"])) < 1e-9,
         f"{sum(float(row['table'][n]['cash_usd']) for n in BUCKETS)} vs "
         f"{row['line_cash_usd']}"),
    ]


def _selftest_law() -> list[tuple[str, bool, str]]:
    """The frozen configs and the imported D-ALONE reading, checked by identity."""

    comps = {asset: dalone_comp(asset) for asset in ASSETS}
    return [
        ("the_frozen_configs_are_the_sweep5_selected_ones",
         [comps[a].key for a in ASSETS]
         == ["Q45/H0.30/k1/DALONE", "Q10/H0.20/k1/DALONE",
             "Q30/H0.20/k3/DALONE"],
         f"{[comps[a].key for a in ASSETS]}"),
        ("the_dalone_reading_carries_no_arbiter_and_no_floor",
         all(not c.arbiter and c.e == 0 and c.gate == S5.GATE_EPISODE
             for c in comps.values()), f"{[c.params for c in comps.values()]}"),
        ("the_zone_is_deleted_from_every_detector",
         all(c.detector.zone == "none" for c in comps.values()),
         "a config carried a zone"),
        ("sweep6_arm_d_uses_the_same_comp",
         all(comps[a].params == S6.comp_for(a, arbiter=False).params
             for a in ASSETS),
         f"{[S6.comp_for(a, arbiter=False).params for a in ASSETS]}"),
        ("the_budgets_are_the_o4b_per_asset_budgets",
         BUDGET_MINUTES == {"HG": 60, "NKD": 45, "SI": 60},
         f"{BUDGET_MINUTES}"),
        ("the_preregistered_bars_are_the_stated_ones",
         AGREEMENT_BAR == 0.55 and WALL_BAR == 0.25 and MDD_CAP_USD == 1000.0,
         f"{AGREEMENT_BAR} {WALL_BAR} {MDD_CAP_USD}"),
    ]


def selftest() -> int:
    mutant = _mutant()
    checks: list[tuple[str, bool, str]] = []
    checks.extend(_selftest_law())
    checks.extend(_selftest_buckets())
    checks.extend(_selftest_flip())
    checks.extend(_selftest_ladder())
    dead = [(name, why) for name, ok, why in checks if not ok]
    if dead:
        for name, why in dead:
            print(f"DEAD: {name}: {why}")
        print(f"sweep7b_selftest_dead mutant={mutant or 'none'} "
              f"cases={len(dead)}/{len(checks)}")
        return 1
    if mutant:
        print(f"DEAD: mutant {mutant} left every sweep-7b case green")
        return 1
    print(f"sweep7b_selftest_ok cases={len(checks)}")
    return 0


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", nargs="?", default="all",
                        choices=("part1", "part2", "log", "all"))
    parser.add_argument("--assets", default="HG,NKD,SI")
    parser.add_argument("--root", default=str(M.MILL_ROOT))
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    mutant = _mutant()
    assets = tuple(name.strip().upper() for name in args.assets.split(",")
                   if name.strip())
    started = time.monotonic()
    plane, arbs, days = S5.load_plane(assets, Path(args.root))
    explore_days = S1._explore_days(assets)
    report = read_report()
    report.setdefault("spec_sha", SPEC_SHA)
    report["code_sha"] = code_sha()
    report["split_sha"] = S4.split_sha()
    report["outcome_law_sha"] = S4.outcome_law_sha()
    report["parent_trial"] = _parent_trial()
    report["mutant"] = mutant
    report["asset_days"] = dict(days)
    report["cells"] = dict(plane.cells)
    report["frozen_configs"] = {a: list(FROZEN[a]) for a in FROZEN}
    report["budget_minutes"] = dict(BUDGET_MINUTES)

    entries, check = reproduce(plane, arbs)
    report["repro"] = check
    print_repro(check)
    report["second_cohort"] = second_cohort(plane, entries)
    print_cohort(report["second_cohort"])

    if args.stage in ("part1", "log", "all"):
        report["part1_decomposition"] = decompose(plane, entries)
        report["part1_ladder"] = ladder(plane, entries)
        print_decomposition(report["part1_decomposition"])
        print_ladder(report["part1_ladder"])
    if args.stage in ("part2", "log", "all"):
        report["part2_flip"] = price_flip(plane, entries, explore_days)
        print_flip(report["part2_flip"])
        report["decision"] = decide(report["part2_flip"])
        print_decision(report["decision"])
    if args.stage in ("log", "all"):
        rows = log_rows(report)
        written = S1.append_log(rows)
        report["log"] = {"rows_appended": written,
                         "registered_utc": rows[0]["registered_utc"],
                         "first_id": rows[0]["id"], "last_id": rows[-1]["id"]}
        print(f"\nlog: appended {written} rows to {LOG_PATH}")

    report["wall_seconds"] = round(time.monotonic() - started, 2)
    write_report(report)
    print(f"\nwrote {OUT_PATH} wall={report['wall_seconds']}s "
          f"cells={len(plane.records)} spec_sha={SPEC_SHA[:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
