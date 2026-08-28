#!/usr/bin/env python3
"""Sweep 29: F24-SIZE-SEAT, magnitude priority as a SEATING discipline.

Unit 3 of Sol's power plan (``.audit/briefs/mill-powerplan-sol-out.md`` section
C rank 3, section D row 3), run under the licence sweep 28 printed in its own
receipt::

    LICENSED: both deciding matched deltas are positive and the lane loses
    seats to occupancy, so F24-SIZE-SEAT may be run on this qualified entry set

so ``NOT-LICENSED`` cannot fire here.  Sweep 28 measured R_GEN matched deltas
NKD +86.3924 and SI +200.0000 USD/date, and 153 of 461 selected events - about
a third - rejected by occupancy.  That is the whole reason this unit exists.

THE LAW OF THE UNIT, per Sol: THE QUALIFIED ENTRY SET STAYS FIXED AND ONLY THE
SEATING DISCIPLINE CHANGES.  Sweep 28's R_GEN out-of-fold top-four selection is
reproduced event-for-event, and this unit refuses unless the reproduction is
exact - the count, the per-asset counts, the whole zone-kind / year / phase
breakdown, and sweep 28's own seated line (308 seated, 153 lost to occupancy,
NKD +170.4231 and SI -17.8125 USD/day).  Nothing about selection is touched.
There is no ranker search, no coverage search, no threshold ladder.

TWO SEATINGS ARE THEN REPLAYED OVER THE SAME EVENTS.

    S1_CHRONOLOGICAL  the standing law, ``sweep22.replay`` reproduced exactly:
                      seat when flat, exits before entries at an equal stamp,
                      at most twelve per portfolio date, zero-entry days carried.
    S2_MAGNITUDE      the tested discipline, fully causal:
                      (a) PRIORITY.  When two or more qualified entries are
                          seatable at the same stamp, the higher FROZEN
                          out-of-fold magnitude score - the I_break channel
                          already computed per candidate, not recomputed here -
                          takes the seat.
                      (b) DECLINE.  An arriving entry whose magnitude score is
                          below its asset-phase train-day median is DECLINED
                          while the asset is flat, but ONLY when the day's
                          remaining schedule can still seat a later entry.
                      (c) everything else identical to S1.

THE DECLINE RULE IS BLIND TO THE FUTURE.  It reads three things and no others:
its own frozen score, two thresholds trained on strictly prior days, and the
clock (how many lattice bars of this asset-phase session remain, and how many
seats this portfolio date has already spent).  It never reads whether a later
entry actually arrives, nor what any later entry's score is.  Two worlds that
agree up to the decision stamp and differ after it get the SAME decision, and
the selftest proves exactly that on a planted pair.  The mirror case - a
decline that was wrong because nothing later arrived - is priced honestly as
the cost of the rule, not hidden.

THE TESTED OBJECT is S2 seated cash MINUS S1 seated cash, paired by shared
calendar date, studentized, under one shared-date-sign maxT family over NKD and
SI at 10,000 draws.  HG is report-only.  The 1800 s pairing is reported beside
it as information.  Event-level p-values are forbidden: several events share
one impulse, one day and one seat ledger.

Nothing here is executable.  EXPLORE only, kill-only tier, no packs, no HOLD,
no teacher labels, no 2021, no 2025H2, no commits, no freeze.  Sweeps 28, 27,
25, 23 and 22, ``levels_zone`` and ``zone_history`` are imported READ-ONLY and
none of them is modified.
"""

from __future__ import annotations

import argparse
import json
import math
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

import mill as M  # noqa: E402,F401
import levels as LV  # noqa: E402
import levels_zone as LZ  # noqa: E402
import zone_history as ZH  # noqa: E402
import sweep1 as S1  # noqa: E402
import sweep8 as S8  # noqa: E402
import sweep9_twins as S9  # noqa: E402
import sweep12 as S12  # noqa: E402
import sweep14 as S14  # noqa: E402
import sweep19 as S19  # noqa: E402
import sweep22 as S22  # noqa: E402
import sweep23 as S23  # noqa: E402
import sweep25 as S25  # noqa: E402
import sweep27 as S27  # noqa: E402
import sweep28 as S28  # noqa: E402

# --------------------------------------------------------------------------
# The law, registered before anything is read.
# --------------------------------------------------------------------------

SPEC = """QRE2MILLSWEEP29
tier=exploratory; EXPLORE-only, kill-only.  Family F24-SIZE-SEAT, the third
  unit of Sol's power plan (.audit/briefs/mill-powerplan-sol-out.md section C
  rank 3, section D row 3).  Seed 20260827.  Parent trial sweep28-040.  NO
  COMMITS, NO FREEZE, no packs, no HOLD, no teacher labels, no 2021, no 2025H2.
  ONE entry set, TWO seatings, ONE paired tested object, one maxT family of TWO
  deciding lines; HG report-only.
LICENCE.  Sweep 28's receipt (.audit/mill-sweep28.json, key f24_licence, log row
  sweep28-039) reads LICENSED: both deciding matched deltas positive (NKD
  +86.3924, SI +200.0000 usd/date) and the lane loses 153 of 461 selected events
  to occupancy (share 0.3319).  The charter's NOT-LICENSED stamp therefore
  CANNOT FIRE in this unit and is not in its clause set.
INHERITANCE.  Sweeps 28, 27, 25, 23 and 22, levels_zone and zone_history are
  imported and called READ-ONLY; their SPECs govern every clause not restated
  here: the GATE, the zone catalogue, breach formation with the persistence gate
  and the per (asset, day, phase, level, break direction) dedup, the frozen
  bar-entry law, the impulse ridge and its join, the frozen wall-or-close outcome
  with the 1800 s label beside, the MDD ledger family, the two stresses.
1. THE ENTRY SET IS FIXED AND IS NOT RE-DERIVED FROM CASH.  Sweep 28's R_GEN
  ranker is rebuilt by call graph - S23.formation_pass, ZH.build, S27.zone_read,
  S27.pricing_pass, S22.fit_impulse, S22.impulse_scores, S28.genealogy_rows,
  S27.rank_folds, S27.selections at k=4 - and this unit REFUSES unless the
  reproduction is exact on ALL of: 3,790 formed candidates; 461 selected events;
  per-asset selected counts HG 157, NKD 149, SI 155; the complete zone-kind,
  year and phase breakdown of the selected close-label cert (n and total USD to
  1e-6); and sweep 28's own seated line - 308 seated, 153 rejected to occupancy,
  0 rejected to cap, NKD +170.42307692 and SI -17.81250000 usd/day.  No cash
  read of this unit may change which events are qualified.
2. S1_CHRONOLOGICAL, the standing law, is sweep22.replay reproduced exactly:
  events ordered by (entry stamp, asset, cell, bar, side); an entry is refused
  while its asset's open position has an exit stamp strictly after the entry
  stamp (so an exit at t frees the seat for an entry at t); at most 12 seats per
  PORTFOLIO DATE; every EXPLORE day of the asset carried, zero-entry days
  included, in the usd/day denominator.  S1 must reproduce sweep 28's numbers.
3. S2_MAGNITUDE, the tested seating discipline, registered IN FULL before any
  outcome of it is read.  m(e) is the FROZEN out-of-fold magnitude score of
  event e: the I_break impulse channel already computed for that candidate by
  S22.impulse_scores under sweep 22's walk-forward ridge.  It is not refit, not
  rescaled and not re-signed here.
  (a) PRIORITY.  Events are ordered by (entry stamp, -m(e), asset, cell, bar,
      side).  At an equal stamp the higher magnitude takes the seat; a
      non-finite m sorts last.  Everything else about the ordering is S1's.
  (b) DECLINE, and this is the entire rule.  Let e arrive at stamp t on asset a,
      phase p, portfolio date d, with lattice bar b of n_bars in its cell.  Let
      TRAIN(a,p,d) be every PRICED candidate of asset a and phase p on EXPLORE
      days strictly earlier than d.  Define
        mag_thr(a,p,d)  = the 0.5 quantile of {m(x) : x in TRAIN(a,p,d)},
        gap_thr(a,p,d)  = the 0.5 quantile of the within-day bar gaps between
                          consecutive arrivals in TRAIN(a,p,d).
      e is DECLINED if and only if ALL of
        i.   e is seatable: its asset is flat and its date is under the cap
             (the occupancy and cap tests of S1 have already passed),
        ii.  m(e) is finite and m(e) < mag_thr(a,p,d),
        iii. mag_thr and gap_thr are both DEFINED (no prior rows -> never
             decline: the rule fails closed),
        iv.  the remaining schedule can still seat a later entry:
             n_bars - b - 1 >= gap_thr(a,p,d), i.e. at least one trained
             inter-arrival gap of this asset-phase still fits in the session,
        v.   the portfolio date has room for a LATER seat as well:
             seats already spent on d < 12 - 1.
      A declined event is not seated, does not occupy its asset, and never
      returns.  THE RULE READS ONLY m(e), the two trained thresholds, the
      session clock and the seat ledger.  It never reads whether a later entry
      arrives, nor any later entry's score, nor any outcome.
  (c) Everything else - occupancy, the exits-before-entries seam, the cap, the
      day denominator, the labels, the MDD ledgers, the stresses - is S1's.
4. MEASUREMENT.  For each seating and each label (frozen wall-or-close PRIMARY,
  1800 s beside): seated n, usd/day, mean minus two asset-day-block SE, the
  complete MDD ledger family including event-time portfolio equity, both
  standing stresses (2 percent adversarial at realized MAE, doubled spread),
  occupancy / cap / decline counters, and zero-entry day shares.
5. THE TESTED OBJECT.  S2 seated cash MINUS S1 seated cash, summed inside each
  shared calendar date, per asset, studentized, read under ONE shared-date-sign
  maxT family over A_BREAK_CLOSE|NKD and A_BREAK_CLOSE|SI at 10,000 draws.  HG
  is carried report-only.  The 1800 s pairing is INFORMATION and carries no
  letter.  Event-level p-values are FORBIDDEN and not computed.
6. NEIGHBOURS, fixed before outcomes: the decline threshold at the train
  quantiles 0.4 and 0.6.  They are a sign-stability check on the paired delta.
  They are not a search: the letter is carried by 0.5 and by nothing else.
7. LETTERS, exhaustive, one precedence, evaluated in this order.
  LIVE = SIZESEAT-LIVE: S2 clears BOTH deciding rungs at the point estimate AND
    at mean minus two SE, the paired deltas are positive at maxT adjusted
    p <= 0.05 on BOTH deciders, EVERY S2 binding MDD is below 1,000, the cap is
    lawful, occupancy is lawful, both stresses clear, and neither decline
    neighbour flips the sign of a deciding paired delta.
  K1 = SIZESEAT-KILL: the paired cash 95 percent simultaneous UPPER bound is
    non-positive on EITHER deciding asset.
  K2 = SIZESEAT-KILL: S2's binding MDD does not fall below 1,000.
  U1 = SIZESEAT-UNRESOLVED: both deciding paired deltas are positive but the
    live bounds fail or the power is inadequate.
  U0 = SIZESEAT-UNRESOLVED, THE REGISTERED RESIDUAL: everything else - a
    deciding paired bound or delta undefined, or a non-positive paired point
    estimate that is not yet a kill.
  On UNRESOLVED the receipt FREEZES.  NOT-LICENSED cannot fire (clause LICENCE).
8. MUTANTS, each with a NAMED red roster fixed before the run.
  priority_reads_future_arrivals: the decline rule peeks at later arrivals'
    scores instead of the trained clock.  Must red the mirror decline case and
    the future-blindness check.
  selection_not_frozen: the qualified set is re-ranked inside this unit.  Must
    red the reproduction gate.
"""

DECLINE_NOTE = (
    "WHY THE DECLINE RULE IS SHAPED THIS WAY.  A seat is a scarce, DURABLE "
    "resource: under the frozen wall-or-close law an entry holds its asset "
    "until the phase closes, so the first arrival of a session usually spends "
    "the whole session's seat.  Sweep 28 lost 153 of 461 qualified events - a "
    "third of them - to exactly that.  The honest question is not 'which "
    "events are good' (that is selection, and it is frozen here) but 'is this "
    "arrival worth the seat, or is the session long enough that waiting is "
    "affordable'.  That question has a causal answer: the arrival's own frozen "
    "score against what this asset-phase has historically served, and the "
    "clock.  It has an ILLEGAL answer too - look at what arrives later - and "
    "the whole design of this unit is to make the legal answer testable and "
    "the illegal one detectable.  The mirror case is the price: sometimes the "
    "session ends with the seat unspent and the declined cash forgone.  That "
    "cost is counted, printed, and included in every cash line.")

RESIDUAL_NOTE = (
    "REGISTERED RESIDUAL.  U0 is written before any outcome is read and it "
    "absorbs every receipt the four named clauses do not: an undefined paired "
    "bound or delta on a decider, and a non-positive-but-not-yet-killed paired "
    "point estimate.  The partition is proved over constructed receipts in the "
    "selftest, not asserted: exactly one clause fires on every combination of "
    "the nine registered flags.")

ORDER_NOTE = (
    "WHAT THE SEAT ORDER CAN AND CANNOT BUY.  Reordering seats cannot create "
    "cash that the selected events do not already carry; the SELECTED cash is "
    "identical under both seatings by construction.  All a seating discipline "
    "can do is change WHICH of the qualified events are actually held.  So the "
    "paired delta is bounded above by the cash the occupancy rejections were "
    "carrying, and a positive delta means the magnitude channel ranks seatable "
    "arrivals better than the clock does.  A negative delta means the clock "
    "was already the better ranker and size is noise at this grain.")

ASSETS = S28.ASSETS
DECIDING = S28.DECIDING
REPORT_ONLY_ASSETS = S28.REPORT_ONLY_ASSETS
SEED = 20260827

FAMILY = "F24-SIZE-SEAT"
PARENT_TRIAL = "sweep28-040"
SELECTION_RULE = (
    "none, and that is the point: the qualified entry set is sweep 28's R_GEN "
    "out-of-fold top-four selection, reproduced event-for-event and gated "
    "against its receipt before any cash of this unit is read; the only thing "
    "this unit varies is the SEATING discipline over that fixed set, with the "
    "decline law registered in full before pricing and no variant search")
LOG_PREFIX = "sweep29"
OUT_PATH = ROOT / ".audit/mill-sweep29.json"
LOG_PATH = S1.LOG_PATH
PARENT_RECEIPT = ROOT / ".audit/mill-sweep28.json"

CLOSE = S28.CLOSE
FIXED = S28.FIXED
LABELS = S28.LABELS
MIN_PRIOR_DAYS = S28.MIN_PRIOR_DAYS
MIN_TRAIN_ROWS = S28.MIN_TRAIN_ROWS
DAY_RUNG_USD = S28.DAY_RUNG_USD
MDD_CEILING = S28.MDD_CEILING                       # 1000
PORTFOLIO_CAP = S28.PORTFOLIO_CAP                   # 12
SIGN_DRAWS = S28.SIGN_DRAWS                         # 10000
IMPULSE_HORIZON_S = S28.IMPULSE_HORIZON_S
EXPECT_CANDIDATES = S28.EXPECT_CANDIDATES           # 3790

LANE = S28.LANE                                     # A_BREAK_CLOSE
LANE_NAME = S28.LANE_NAME
RIDGE_LAMBDA = S28.RIDGE_LAMBDA
TOP_K = S28.TOP_K                                   # 4
FEATURES_ALL = S28.GEN_FEATURES_ALL
N_FEATURES = S28.N_ALL                              # 26

# --------------------------------------------------------------------------
# The reproduction gate: sweep 28's receipt, by value.
# --------------------------------------------------------------------------

EXPECT_SELECTED = 461
EXPECT_PER_ASSET = {"HG": 157, "NKD": 149, "SI": 155}
EXPECT_SEATED = 308
EXPECT_REJECTED_OCCUPANCY = 153
EXPECT_REJECTED_CAP = 0
EXPECT_USD_DAY = {"HG": 63.69318181818182,
                  "NKD": 170.42307692307693,
                  "SI": -17.812500000000018}
EXPECT_TRADES = {"HG": 103, "NKD": 97, "SI": 108}
REPRO_TOL_USD = 1e-6

LICENCE_QUOTE = (
    "LICENSED: both deciding matched deltas are positive and the lane loses "
    "seats to occupancy, so F24-SIZE-SEAT may be run on this qualified entry "
    "set")

# --------------------------------------------------------------------------
# The two seatings and the decline law's fixed constants.
# --------------------------------------------------------------------------

S1_CHRONOLOGICAL = "S1_CHRONOLOGICAL"
S2_MAGNITUDE = "S2_MAGNITUDE"
SEATINGS = (S1_CHRONOLOGICAL, S2_MAGNITUDE)

DECLINE_Q = 0.5                     # the registered decline threshold quantile
NEIGHBOUR_Q = (0.4, 0.6)            # the two registered sign-stability neighbours
GAP_Q = 0.5                         # the trained inter-arrival gap quantile

# --------------------------------------------------------------------------
# The letters.  Five clauses, one precedence, a total partition.
# --------------------------------------------------------------------------

LETTER_LIVE = "SIZESEAT-LIVE"
LETTER_UNRESOLVED = "SIZESEAT-UNRESOLVED"
LETTER_KILL = "SIZESEAT-KILL"
LETTER_NOT_LICENSED = "SIZESEAT-NOT-LICENSED"

CLAUSES = {
    "LIVE": ("S2 clears the full live bounds: both deciding assets clear the "
             "rung at the point estimate AND at mean minus two SE, both paired "
             "deltas are positive at maxT adjusted p <= 0.05, every S2 binding "
             "MDD is below 1000, the cap and occupancy are lawful, both "
             "stresses clear, and neither decline neighbour flips a deciding "
             "paired-delta sign"),
    "K1": ("the PAIRED CASH 95 percent simultaneous upper bound is "
           "non-positive on either deciding asset"),
    "K2": ("S2's binding MDD does not fall below 1000 USD"),
    "U1": ("both deciding paired deltas are positive but the live bounds fail "
           "or the power is inadequate"),
    "U0": ("THE REGISTERED RESIDUAL: a deciding paired bound or delta is "
           "undefined, or a deciding paired point estimate is non-positive "
           "while neither kill clause fires"),
}
CLAUSE_ORDER = ("LIVE", "K1", "K2", "U1", "U0")
CLAUSE_LETTER = {"LIVE": LETTER_LIVE, "K1": LETTER_KILL, "K2": LETTER_KILL,
                 "U1": LETTER_UNRESOLVED, "U0": LETTER_UNRESOLVED}

MUTANT_ENV = "QRE2_MILL_S29_MUTANT"
MUTANT_FUTURE = "priority_reads_future_arrivals"
MUTANT_SELECTION = "selection_not_frozen"
MUTANTS = (MUTANT_FUTURE, MUTANT_SELECTION)


class SweepRefusal(RuntimeError):
    pass


SPEC_SHA = S1._sha_text(SPEC)


def code_sha() -> str:
    """This unit plus every module whose behaviour it is asserting."""

    here = Path(__file__).resolve().parent
    return S1._sha_text("\n".join(
        S1._sha_file(Path(path).resolve()) for path in (
            __file__, here / "sweep28.py", here / "zone_history.py",
            here / "sweep27.py", here / "sweep25.py", here / "sweep23.py",
            here / "sweep22.py", here / "levels_zone.py")))


def _mutant() -> str:
    name = os.environ.get(MUTANT_ENV, "")
    if name and name not in MUTANTS:
        raise SweepRefusal(f"unknown sweep 29 mutant: {name}")
    return name


_n = S22._n
_show = S22._show
_check = S22._check
_mean_se = S22._mean_se


def _quantile(values: Sequence[float], q: float) -> float | None:
    finite = [float(v) for v in values if np.isfinite(v)]
    if not finite:
        return None
    return float(np.quantile(np.asarray(finite, np.float64), float(q)))


# --------------------------------------------------------------------------
# 3b. The trained decline thresholds.  Strictly prior days, no outcome read.
# --------------------------------------------------------------------------

def decline_thresholds(cands: Sequence[S23.Cand],
                       entries: Mapping[int, S22.Priced],
                       magnitude: np.ndarray,
                       explore_days: Mapping[str, Sequence[int]],
                       q: float = DECLINE_Q
                       ) -> tuple[dict[tuple[str, str, int], dict[str, float]],
                                  dict[str, object]]:
    """``mag_thr`` and ``gap_thr`` per (asset, phase, day), from prior days only.

    The pool is every PRICED candidate of the same asset and phase on EXPLORE
    days STRICTLY EARLIER than the day being seated.  Nothing about the day
    under seating, and no outcome of any day, enters either threshold: the
    magnitude score is the frozen out-of-fold impulse channel and the gap is a
    property of the arrival schedule, which formation fixes before pricing.
    """

    rows: dict[tuple[str, str], dict[int, list[tuple[int, float]]]] = {}
    for position, cand in enumerate(cands):
        if position not in entries:
            continue
        key = (str(cand.asset), str(cand.phase))
        rows.setdefault(key, {}).setdefault(int(cand.d8), []).append(
            (int(cand.bar), float(magnitude[position])))
    out: dict[tuple[str, str, int], dict[str, float]] = {}
    counters = {"cells": 0, "defined": 0, "no_mag": 0, "no_gap": 0}
    for (asset, phase), by_day in rows.items():
        days = sorted(int(day) for day in explore_days.get(asset, ()))
        seen_mag: list[float] = []
        seen_gap: list[float] = []
        for d8 in days:
            counters["cells"] += 1
            mag_thr = _quantile(seen_mag, q)
            gap_thr = _quantile(seen_gap, GAP_Q)
            if mag_thr is None:
                counters["no_mag"] += 1
            if gap_thr is None:
                counters["no_gap"] += 1
            if mag_thr is not None and gap_thr is not None:
                counters["defined"] += 1
                out[(asset, phase, int(d8))] = {
                    "mag_thr": float(mag_thr), "gap_thr": float(gap_thr),
                    "train_rows": int(len(seen_mag)),
                    "train_gaps": int(len(seen_gap))}
            today = sorted(by_day.get(int(d8), []))
            seen_mag.extend(value for _bar, value in today
                            if np.isfinite(value))
            bars = [bar for bar, _value in today]
            seen_gap.extend(float(bars[i] - bars[i - 1])
                            for i in range(1, len(bars)))
    return out, counters


# --------------------------------------------------------------------------
# 2 and 3.  The two seatings.
# --------------------------------------------------------------------------

def _sort_key(entries: Sequence[S22.Priced], score: Sequence[float],
              seating: str):
    if seating == S1_CHRONOLOGICAL:
        return lambda i: (int(entries[i].entry_ts_ns), entries[i].asset,
                          int(entries[i].cell), int(entries[i].bar),
                          int(entries[i].side))
    return lambda i: (int(entries[i].entry_ts_ns), -float(score[i]),
                      entries[i].asset, int(entries[i].cell),
                      int(entries[i].bar), int(entries[i].side))


def seat_replay(entries: Sequence[S22.Priced], label: str, seating: str,
                magnitude: Mapping[int, float] | None = None,
                n_bars: Mapping[int, int] | None = None,
                thresholds: Mapping[tuple[str, str, int], Mapping[str, float]]
                | None = None,
                overrides: Mapping[int, float] | None = None,
                mutant: str = "") -> dict[str, object]:
    """One seat replay under one discipline.

    ``S1_CHRONOLOGICAL`` is ``sweep22.replay`` reproduced line for line - the
    same order key, the same occupancy seam, the same cap, the same counters -
    and the reproduction gate proves that on real data.  ``S2_MAGNITUDE`` adds
    the two registered clauses and NOTHING else.
    """

    count = len(entries)
    raw = [float(magnitude[i]) if magnitude is not None and i in magnitude
           else float("nan") for i in range(count)]
    score = [value if np.isfinite(value) else -math.inf for value in raw]
    order = sorted(range(count), key=_sort_key(entries, score, seating))
    occupied: dict[str, int] = {}
    seated_by_date: dict[int, int] = {}
    trades: list[S22.Trade] = []
    seated_index: list[int] = []
    declined_index: list[int] = []
    rejected_occupancy = 0
    rejected_cap = 0
    declined = 0
    decline_undefined = 0
    decline_blocked_clock = 0
    decline_blocked_cap = 0
    for i in order:
        item = entries[i]
        stamp = int(item.entry_ts_ns)
        # Exits are processed before entries at an equal stamp: a position whose
        # exit stamp is <= this entry stamp has already freed the seat.
        if item.asset in occupied and occupied[item.asset] > stamp:
            rejected_occupancy += 1
            continue
        if seated_by_date.get(int(item.d8), 0) >= PORTFOLIO_CAP:
            rejected_cap += 1
            continue
        if seating == S2_MAGNITUDE:
            verdict = _decline(i, item, raw, n_bars, thresholds,
                               seated_by_date, entries, score, mutant)
            if verdict == "decline":
                declined += 1
                declined_index.append(i)
                continue
            if verdict == "undefined":
                decline_undefined += 1
            elif verdict == "clock":
                decline_blocked_clock += 1
            elif verdict == "cap":
                decline_blocked_cap += 1
        pnl = (float(overrides[i]) if overrides is not None and i in overrides
               else float(item.cert[label]))
        occupied[item.asset] = int(item.exit_ts[label])
        seated_by_date[int(item.d8)] = seated_by_date.get(int(item.d8), 0) + 1
        seated_index.append(i)
        trades.append(S22.Trade(
            asset=item.asset, d8=int(item.d8), cell=int(item.cell),
            bar=int(item.bar), exit_bar=int(item.exit_bar), side=int(item.side),
            entry_ts_ns=stamp, exit_ts_ns=int(item.exit_ts[label]),
            entry_mid2=int(item.entry_mid2), cost_usd=float(item.cost_usd),
            pnl_usd=pnl))
    return {"trades": trades, "rejected_occupancy": rejected_occupancy,
            "rejected_cap": rejected_cap, "seated": len(trades),
            "declined": declined, "decline_undefined": decline_undefined,
            "decline_blocked_clock": decline_blocked_clock,
            "decline_blocked_cap": decline_blocked_cap,
            "seated_index": seated_index, "declined_index": declined_index,
            "order": order}


def _decline(i: int, item: S22.Priced, raw: Sequence[float],
             n_bars: Mapping[int, int] | None,
             thresholds: Mapping[tuple[str, str, int], Mapping[str, float]] | None,
             seated_by_date: Mapping[int, int],
             entries: Sequence[S22.Priced], score: Sequence[float],
             mutant: str) -> str:
    """The registered decline law.  Returns why it did or did not fire.

    Reads: this event's own frozen magnitude, the two thresholds trained on
    STRICTLY PRIOR days, the session clock, and the seat ledger.  Nothing else
    exists in this function's inputs - in particular no later arrival's
    identity, score or existence, and no outcome of any event.
    """

    if thresholds is None or n_bars is None:
        return "undefined"
    cell = thresholds.get((str(item.asset), str(item.phase), int(item.d8)))
    if cell is None:
        return "undefined"
    value = float(raw[i])
    if not np.isfinite(value) or value >= float(cell["mag_thr"]):
        return "above"
    if seated_by_date.get(int(item.d8), 0) >= PORTFOLIO_CAP - 1:
        return "cap"
    if mutant == MUTANT_FUTURE:
        # THE MUTANT, and it is illegal: instead of asking the clock whether a
        # later entry COULD be seated, it asks the tape whether a better one
        # ACTUALLY arrives.  That is a read of the future.
        stamp = int(item.entry_ts_ns)
        later = any(entries[j].asset == item.asset
                    and int(entries[j].d8) == int(item.d8)
                    and int(entries[j].entry_ts_ns) > stamp
                    and float(score[j]) > float(score[i])
                    for j in range(len(entries)))
        return "decline" if later else "clock"
    remaining = int(n_bars.get(i, 0)) - int(item.bar) - 1
    if float(remaining) < float(cell["gap_thr"]):
        return "clock"
    return "decline"


# --------------------------------------------------------------------------
# 1. The reproduction gate.
# --------------------------------------------------------------------------

def selection_fingerprint(picks: Sequence[int], entries: Mapping[int, S22.Priced],
                          cands: Sequence[S23.Cand]) -> dict[str, object]:
    """Everything sweep 28's receipt pins about WHICH events were selected."""

    chosen = [entries[p] for p in picks]
    per_asset = {asset: sum(1 for e in chosen if e.asset == asset)
                 for asset in ASSETS}
    return {"n": int(len(picks)), "per_asset": per_asset,
            "breakdowns": S22.breakdowns(chosen, cands, CLOSE)}


def assert_reproduction(fingerprint: Mapping[str, object],
                        seated: Mapping[str, object],
                        cash: Mapping[str, object],
                        parent: Mapping[str, object]) -> dict[str, object]:
    """Refuse unless the FIXED entry set and S1's seating are sweep 28's."""

    fails: list[str] = []
    if int(fingerprint["n"]) != EXPECT_SELECTED:
        fails.append(f"selected {fingerprint['n']} events, not sweep 28's "
                     f"{EXPECT_SELECTED}")
    for asset in ASSETS:
        got = int(fingerprint["per_asset"][asset])       # type: ignore[index]
        if got != EXPECT_PER_ASSET[asset]:
            fails.append(f"{asset} selected {got}, not {EXPECT_PER_ASSET[asset]}")
    want = parent["by_ranker"]["R_GEN"]["breakdowns"]    # type: ignore[index]
    got = fingerprint["breakdowns"]                      # type: ignore[index]
    for name in sorted(want):
        if set(want[name]) != set(got.get(name, {})):    # type: ignore[union-attr]
            fails.append(f"the {name} breakdown has different keys than the "
                         f"parent receipt")
            continue
        for key in sorted(want[name]):
            a = want[name][key]
            b = got[name][key]                           # type: ignore[index]
            if int(a["n"]) != int(b["n"]):
                fails.append(f"{name}={key} has {b['n']} events, not {a['n']}")
            if abs(float(a["total_usd"]) - float(b["total_usd"])) > REPRO_TOL_USD:
                fails.append(f"{name}={key} totals {b['total_usd']:.6f} USD, "
                             f"not {a['total_usd']:.6f}")
    if int(seated["seated"]) != EXPECT_SEATED:
        fails.append(f"S1 seated {seated['seated']}, not {EXPECT_SEATED}")
    if int(seated["rejected_occupancy"]) != EXPECT_REJECTED_OCCUPANCY:
        fails.append(f"S1 lost {seated['rejected_occupancy']} to occupancy, "
                     f"not {EXPECT_REJECTED_OCCUPANCY}")
    if int(seated["rejected_cap"]) != EXPECT_REJECTED_CAP:
        fails.append(f"S1 lost {seated['rejected_cap']} to the cap, not "
                     f"{EXPECT_REJECTED_CAP}")
    for asset in ASSETS:
        got_usd = cash[asset]["usd_per_day"]             # type: ignore[index]
        if got_usd is None or abs(float(got_usd) - EXPECT_USD_DAY[asset]) > 1e-9:
            fails.append(f"S1 {asset} seated {_show(got_usd)} usd/day, not "
                         f"{EXPECT_USD_DAY[asset]:.8f}")
        got_trades = int(cash[asset]["trades"])          # type: ignore[index]
        if got_trades != EXPECT_TRADES[asset]:
            fails.append(f"S1 {asset} seated {got_trades} trades, not "
                         f"{EXPECT_TRADES[asset]}")
    return {"ok": not fails, "failures": fails,
            "expected": {"selected": EXPECT_SELECTED,
                         "per_asset": EXPECT_PER_ASSET,
                         "seated": EXPECT_SEATED,
                         "rejected_occupancy": EXPECT_REJECTED_OCCUPANCY,
                         "rejected_cap": EXPECT_REJECTED_CAP,
                         "usd_per_day": EXPECT_USD_DAY,
                         "trades": EXPECT_TRADES},
            "observed": {"selected": int(fingerprint["n"]),
                         "per_asset": fingerprint["per_asset"],
                         "seated": int(seated["seated"]),
                         "rejected_occupancy": int(seated["rejected_occupancy"]),
                         "rejected_cap": int(seated["rejected_cap"]),
                         "usd_per_day": {a: cash[a]["usd_per_day"]  # type: ignore[index]
                                         for a in ASSETS},
                         "trades": {a: int(cash[a]["trades"])       # type: ignore[index]
                                    for a in ASSETS}},
            "source": "sweep 28's own receipt, .audit/mill-sweep28.json"}


# --------------------------------------------------------------------------
# 5. The tested object.
# --------------------------------------------------------------------------

def paired_lines(gen_trades: Sequence[S22.Trade], base_trades: Sequence[S22.Trade],
                 scoring: Mapping[str, Sequence[int]]
                 ) -> dict[str, dict[int, float]]:
    """S2 seated cash MINUS S1 seated cash, per asset, inside each shared date.

    EVERY SCORED DATE IS CARRIED, including dates where one seating seats
    nothing: a date where S2 holds a trade and S1 holds none is exactly the
    evidence this unit is meant to price, and dropping it would keep only the
    dates on which the two disciplines already agree.
    """

    out: dict[str, dict[int, float]] = {}
    for asset in ASSETS:
        a = S28.seated_cash_by_date(gen_trades, asset)
        b = S28.seated_cash_by_date(base_trades, asset)
        dates = sorted(set(int(d) for d in scoring.get(asset, ()))
                       | set(a) | set(b))
        out[f"{LANE}|{asset}"] = {
            int(d8): float(a.get(int(d8), 0.0) - b.get(int(d8), 0.0))
            for d8 in dates}
    return out


# --------------------------------------------------------------------------
# 7. The letters.
# --------------------------------------------------------------------------

def classify(rung_ok: bool, mdd_ok: bool, cap_ok: bool, occupancy_ok: bool,
             stress_ok: bool, paired_ok: bool, neighbours_ok: bool,
             paired_upper_nonpositive: bool, mdd_not_below: bool,
             bounds_defined: bool, deltas_positive: bool
             ) -> tuple[str, str, list[str]]:
    """Exactly one clause fires; every clause that matched is listed beside it."""

    live = bool(rung_ok and mdd_ok and cap_ok and occupancy_ok and stress_ok
                and paired_ok and neighbours_ok)
    matching: list[str] = []
    if live:
        matching.append("LIVE")
    if paired_upper_nonpositive:
        matching.append("K1")
    if mdd_not_below:
        matching.append("K2")
    rest = (not live and not paired_upper_nonpositive and not mdd_not_below)
    if rest and bounds_defined and deltas_positive:
        matching.append("U1")
    if rest and not (bounds_defined and deltas_positive):
        matching.append("U0")
    for clause in CLAUSE_ORDER:
        if clause in matching:
            return CLAUSE_LETTER[clause], clause, matching
    raise SweepRefusal("the letter partition failed to cover a receipt")


def family_letter(report: Mapping[str, object]) -> dict[str, object]:
    """One fixed entry set, one tested seating, one letter."""

    live = report["seating"][S2_MAGNITUDE][CLOSE]        # type: ignore[index]
    paired = report["paired"]["by_line"]                 # type: ignore[index]
    reasons: list[str] = []

    rung_ok = True
    for asset in DECIDING:
        block = live["cash"][asset]                      # type: ignore[index]
        if not block.get("clears_rung"):
            rung_ok = False
            reasons.append(f"{asset} misses the rung "
                           f"({block.get('usd_per_day')} point, "
                           f"{block.get('mean_minus_2se_usd')} at -2SE)")
    mdd_ok = bool(live["mdd"]["clears"])                 # type: ignore[index]
    mdd_not_below = not mdd_ok
    if not mdd_ok:
        reasons.append(f"S2 binding MDD {live['mdd']['max_binding_usd']:.1f} "
                       f">= {MDD_CEILING}")
    cap_ok = bool(live["cash"]["_portfolio"]["cap_lawful"])  # type: ignore[index]
    if not cap_ok:
        reasons.append("the portfolio cap was breached")
    occupancy_ok = bool(live["occupancy_lawful"])
    if not occupancy_ok:
        reasons.append("a seat was held by two positions at once")
    stress_ok = all(bool(live["stress"][kind]["mdd"]["clears"])  # type: ignore[index]
                    for kind in ("adversarial", "spread"))
    if not stress_ok:
        reasons.append("a stress replay breaches MDD")

    paired_ok = True
    for asset in DECIDING:
        cell = paired.get(f"{LANE}|{asset}")
        if (cell is None or cell.get("p_max_adjusted") is None
                or cell.get("delta_usd_per_date") is None):
            paired_ok = False
            reasons.append(f"{asset} has no powered paired delta")
            continue
        if float(cell["delta_usd_per_date"]) <= 0.0:
            paired_ok = False
            reasons.append(f"{asset} paired delta "
                           f"{cell['delta_usd_per_date']:.4f} is not positive")
        if float(cell["p_max_adjusted"]) > 0.05:
            paired_ok = False
            reasons.append(f"{asset} paired delta p "
                           f"{cell['p_max_adjusted']:.4f} > 0.05")
    neighbours_ok = bool(report["neighbours"]["agree"])  # type: ignore[index]
    if not neighbours_ok:
        reasons.append("a decline-threshold neighbour flips a deciding "
                       "paired-delta sign")

    uppers = {asset: (paired.get(f"{LANE}|{asset}") or {}).get(
        "upper95_simultaneous_usd") for asset in DECIDING}
    deltas = {asset: (paired.get(f"{LANE}|{asset}") or {}).get(
        "delta_usd_per_date") for asset in DECIDING}
    bounds_defined = all(value is not None for value in
                         list(uppers.values()) + list(deltas.values()))
    if not bounds_defined:
        reasons.append("a deciding paired bound or delta is undefined")
    paired_upper_nonpositive = any(
        value is not None and float(value) <= 0.0 for value in uppers.values())
    if paired_upper_nonpositive:
        reasons.append("the PAIRED CASH has a non-positive 95% simultaneous "
                       "upper bound on a deciding asset")
    deltas_positive = all(value is not None and float(value) > 0.0
                          for value in deltas.values())

    letter, clause, matching = classify(
        rung_ok, mdd_ok, cap_ok, occupancy_ok, stress_ok, paired_ok,
        neighbours_ok, paired_upper_nonpositive, mdd_not_below, bounds_defined,
        deltas_positive)
    return {"letter": letter, "clause": clause, "clause_text": CLAUSES[clause],
            "clauses_matching": matching, "reasons": reasons,
            "rung_ok": rung_ok, "mdd_ok": mdd_ok, "cap_ok": cap_ok,
            "occupancy_ok": occupancy_ok, "stress_ok": stress_ok,
            "paired_ok": paired_ok, "neighbours_ok": neighbours_ok,
            "paired_upper_nonpositive": paired_upper_nonpositive,
            "mdd_not_below_ceiling": mdd_not_below,
            "bounds_defined": bounds_defined,
            "deltas_positive": deltas_positive,
            "not_licensed_possible": False,
            "licence": LICENCE_QUOTE}


# --------------------------------------------------------------------------
# Occupancy audit: the replay's own invariant, checked on its output.
# --------------------------------------------------------------------------

def occupancy_lawful(trades: Sequence[S22.Trade]) -> bool:
    """No asset holds two positions at once, in the replay's own convention."""

    by_asset: dict[str, list[S22.Trade]] = {}
    for trade in trades:
        by_asset.setdefault(trade.asset, []).append(trade)
    for mine in by_asset.values():
        mine = sorted(mine, key=lambda t: int(t.entry_ts_ns))
        for a, b in zip(mine, mine[1:]):
            if int(a.exit_ts_ns) > int(b.entry_ts_ns):
                return False
    return True


# --------------------------------------------------------------------------
# The pipeline.  Built once per process and memoized: every gate, every
# selftest that touches real data and the run itself read the SAME artifacts.
# --------------------------------------------------------------------------

_PIPELINE: dict[str, object] | None = None


def pipeline() -> dict[str, object]:
    global _PIPELINE
    if _PIPELINE is not None:
        return _PIPELINE

    started = time.time()
    S28.assert_feature_law()
    if ZH.GRID_WARMUP_DAYS != MIN_PRIOR_DAYS:
        raise SweepRefusal(
            f"the genealogy grid warmup ({ZH.GRID_WARMUP_DAYS}) is not the "
            f"ranker's warmup ({MIN_PRIOR_DAYS})")

    cells, days, _skipped = S8.build_cells(ASSETS)
    records, _rec_days = S1.load_cache()
    explore_days = S1._explore_days(ASSETS)
    tape = S9.load_tape(cells)
    forecast = S9.forecast_variance(cells)
    plane9 = S9.build_plane(cells, forecast, tape)
    scoring = {asset: sorted(int(d) for d in explore_days[asset])[MIN_PRIOR_DAYS:]
               for asset in ASSETS}
    repro = S19.reproduce(plane9, scoring)
    if not repro["matches"]:
        raise SweepRefusal("sweep 9's occurrence plane did not reproduce")
    manifest = LV.load_manifest()
    if str(manifest.get("schema")) != LV.MANIFEST_SCHEMA:
        raise SweepRefusal("the levels manifest schema drifted")
    if str(manifest.get("split_sha256", "")) != S1.split_sha():
        raise SweepRefusal("the levels cache was built against a different split")
    cache_gap = int(manifest.get("totals", {}).get("max_src_minus_stamp_ns", 0))
    if cache_gap >= 0:
        raise SweepRefusal(
            f"the levels cache does not certify a strictly prior read: "
            f"max(source - stamp) = {cache_gap} ns")
    states = S12.day_states({asset: explore_days[asset] for asset in ASSETS})
    streams, stream_counters = S14.build_streams(plane9, cells, states, "")
    causal = S14.assert_causal(streams, plane9)
    if not causal["no_outcome_in_features"]:
        raise SweepRefusal("a feature reads the outcome it is choosing over")

    cands, formation = S23.formation_pass(cells, explore_days, "")
    if not formation["strictly_prior"]:
        raise SweepRefusal(
            f"a level read is not strictly prior to its breach close: "
            f"max(source - breach) = {formation['max_src_minus_breach_ns']} ns")
    if len(cands) != EXPECT_CANDIDATES:
        raise SweepRefusal(
            f"the formation pass returned {len(cands)} candidates, not sweep "
            f"28's {EXPECT_CANDIDATES}; the entry set is not the licensed one")

    store, store_build = ZH.build()
    store_audit = ZH.audit(store)
    ZH.assert_gates(store_audit)

    reader = LZ.reader(ASSETS)
    read = S27.zone_read(cands, records, reader)
    S27.assert_zone_anchored(read)

    priced = S27.pricing_pass(cands, cells, streams, records)
    if priced["plane_checks"]["mismatched"]:
        raise SweepRefusal("a lane-A close-label cert disagreed with the frozen "
                           "cert plane")
    if priced["same_close"]["violations"]:
        raise SweepRefusal(
            f"{priced['same_close']['violations']} lane-A entries filled at or "
            f"before their own breach close")

    folds_impulse, impulse_report = S22.fit_impulse(priced["mag"], explore_days,
                                                    "")
    occ_by_cell: dict[int, list[S14.Occ]] = {}
    for stream in streams:
        occ_by_cell[int(stream.cell)] = sorted(
            stream.occs, key=lambda o: (o.bar, o.side, o.row))
    join = {"joined": 0, "no_prior_occurrence": 0}
    for cand in cands:
        prior = [o for o in occ_by_cell.get(int(cand.cell), [])
                 if int(o.bar) < int(cand.bar)]
        if not prior:
            join["no_prior_occurrence"] += 1
            continue
        cand.imp_row = int(prior[-1].row)
        cand.x = np.asarray(prior[-1].x, np.float64)
        join["joined"] += 1
    impulse, impulse_counters = S22.impulse_scores(cands, folds_impulse)

    base, base_census = S27.build_features(read, cands)
    base[:, S27.I_BREAK_COLUMN] = impulse
    base_census["finite_per_column"]["I_break"] = int(np.isfinite(impulse).sum())
    base_census["rows_without_finite_I_break"] = int((~np.isfinite(impulse)).sum())
    gen, gen_block = S28.genealogy_rows(cands, records, store)
    S28.assert_genealogy_gates(gen_block)
    features = np.hstack([base, gen])

    entries = priced["entries"]
    cert = np.full(len(cands), np.nan, np.float64)
    for position, entry in entries.items():
        cert[int(position)] = float(entry.cert[CLOSE])
    positions_by_day: dict[tuple[str, int], list[int]] = {}
    for position, cand in enumerate(cands):
        if position not in entries:
            continue
        positions_by_day.setdefault((cand.asset, int(cand.d8)), []).append(
            int(position))
    folds, rank_report = S27.rank_folds(positions_by_day, features, cert,
                                        explore_days, "")
    rank_report["candidates_priced"] = int(len(entries))
    rank_report["candidates_unpriced"] = int(len(cands) - len(entries))

    _PIPELINE = {
        "cands": cands, "cells": cells, "records": records,
        "explore_days": explore_days, "scoring": scoring, "days": days,
        "formation": formation, "causal": causal,
        "stream_counters": stream_counters, "reproduction": repro,
        "store_build": store_build, "store_audit": store_audit,
        "zone_read": read.counters, "genealogy_read": gen_block,
        "priced": priced, "entries": entries, "impulse": impulse,
        "impulse_report": impulse_report, "impulse_join": join,
        "impulse_counters": impulse_counters, "features": features,
        "base_census": base_census, "folds": folds, "rank_report": rank_report,
        "cert": cert, "positions_by_day": positions_by_day,
        "elapsed_s": round(time.time() - started, 1)}
    return _PIPELINE


def qualified_set(bundle: Mapping[str, object], mutant: str = "") -> list[int]:
    """Sweep 28's R_GEN top-four selection, and nothing this unit invented.

    Under ``selection_not_frozen`` the unit re-ranks the same candidates on its
    OWN score - the magnitude channel - instead of reproducing the parent's
    ranker.  That is the forbidden move: the entry set would then depend on
    this unit, and the seating comparison would no longer be paired.
    """

    folds = bundle["folds"]                              # type: ignore[index]
    if mutant != MUTANT_SELECTION:
        return list(S27.selections(folds, TOP_K))
    impulse = bundle["impulse"]                          # type: ignore[index]
    out: list[int] = []
    for fold in folds:                                   # type: ignore[union-attr]
        rows = [int(p) for p in fold.positions]
        rows.sort(key=lambda p: (-(float(impulse[p]) if np.isfinite(impulse[p])
                                   else -math.inf), p))
        out.extend(rows[:TOP_K])
    return sorted(out)


# --------------------------------------------------------------------------
# The run.
# --------------------------------------------------------------------------

def run(mutant: str | None = None) -> dict[str, object]:
    mutant = _mutant() if mutant is None else mutant
    started = time.time()
    bundle = pipeline()
    cands = bundle["cands"]
    entries = bundle["entries"]
    impulse = bundle["impulse"]
    explore_days = bundle["explore_days"]
    scoring = bundle["scoring"]
    priced = bundle["priced"]

    parent = json.loads(PARENT_RECEIPT.read_text())
    licence = parent["f24_licence"]
    if not bool(licence.get("licensed")):
        raise SweepRefusal("sweep 28's receipt does not license F24-SIZE-SEAT")

    # ---- 1. the FIXED qualified entry set, gated before any cash of ours ----
    picks = qualified_set(bundle, mutant)
    chosen = [entries[p] for p in picks]
    fingerprint = selection_fingerprint(picks, entries, cands)
    magnitude = {index: float(impulse[entry.position])
                 for index, entry in enumerate(chosen)}
    n_bars = {index: int(cands[entry.position].n_bars)
              for index, entry in enumerate(chosen)}

    thresholds, threshold_counters = decline_thresholds(
        cands, entries, impulse, explore_days, DECLINE_Q)

    base_seat = seat_replay(chosen, CLOSE, S1_CHRONOLOGICAL)
    base_cash = S22.replay_cash(base_seat["trades"], explore_days)
    gate = assert_reproduction(fingerprint, base_seat, base_cash, parent)
    if not gate["ok"]:
        raise SweepRefusal(
            "THE FIXED ENTRY SET DID NOT REPRODUCE SWEEP 28, so the seating "
            "comparison is not the licensed one: " + "; ".join(gate["failures"]))

    # ---- 2 and 3: the two seatings, both labels ---------------------------
    seat: dict[str, dict[str, object]] = {}
    replays: dict[tuple[str, str], dict[str, object]] = {}
    for seating in SEATINGS:
        seat[seating] = {}
        for label in LABELS:
            got = seat_replay(chosen, label, seating, magnitude, n_bars,
                              thresholds, None, mutant)
            replays[(seating, label)] = got
            cash = S22.replay_cash(got["trades"], explore_days)
            block: dict[str, object] = {
                "seating": seating, "label": label,
                "n_selected": int(len(chosen)),
                "replay": {k: got[k] for k in (
                    "seated", "rejected_occupancy", "rejected_cap", "declined",
                    "decline_undefined", "decline_blocked_clock",
                    "decline_blocked_cap")},
                "cash": cash,
                "mdd": S22.mdd_ledgers(got["trades"], priced["mid_by_cell"],
                                       priced["lat_by_cell"], explore_days),
                "occupancy_lawful": occupancy_lawful(got["trades"])}
            stress: dict[str, object] = {}
            for kind in ("adversarial", "spread"):
                overrides = S22.stress_overrides(chosen, label, kind)
                stressed = seat_replay(chosen, label, seating, magnitude,
                                       n_bars, thresholds, overrides, mutant)
                stress[kind] = {
                    "seated": stressed["seated"],
                    "cash": S22.replay_cash(stressed["trades"], explore_days),
                    "mdd": S22.mdd_ledgers(stressed["trades"],
                                           priced["mid_by_cell"],
                                           priced["lat_by_cell"], explore_days)}
            block["stress"] = stress
            seat[seating][label] = block

    # ---- 5. THE TESTED OBJECT --------------------------------------------
    family = [f"{LANE}|{asset}" for asset in DECIDING]
    lines = paired_lines(replays[(S2_MAGNITUDE, CLOSE)]["trades"],
                         replays[(S1_CHRONOLOGICAL, CLOSE)]["trades"], scoring)
    paired = S22.maxt_inference(lines, family, SIGN_DRAWS)
    paired["definition"] = (
        "S2_MAGNITUDE seated cash MINUS S1_CHRONOLOGICAL seated cash over the "
        "SAME fixed qualified entry set, summed inside each shared calendar "
        "date under the frozen close label, studentized and read under one "
        "shared-date-sign maxT family over NKD and SI")
    paired["event_level_p"] = (
        "FORBIDDEN and not computed: several events share one impulse, one day "
        "and one seat ledger, so the independent unit is the calendar date")
    lines_1800 = paired_lines(replays[(S2_MAGNITUDE, FIXED)]["trades"],
                              replays[(S1_CHRONOLOGICAL, FIXED)]["trades"],
                              scoring)
    paired_1800 = S22.maxt_inference(lines_1800, family, SIGN_DRAWS)
    paired_1800["note"] = (
        "INFORMATION ONLY, carries no letter: the 1800 s label is the frozen "
        "sensitivity, reported beside the primary pairing as the charter "
        "requires and never used to decide one")

    per_date = {
        f"{LANE}|{asset}": {
            "close": {str(d8): value for d8, value
                      in sorted(lines[f"{LANE}|{asset}"].items())
                      if abs(value) > 1e-9},
            "1800": {str(d8): value for d8, value
                     in sorted(lines_1800[f"{LANE}|{asset}"].items())
                     if abs(value) > 1e-9}}
        for asset in ASSETS}

    # ---- 6. the two registered decline neighbours -------------------------
    neighbour_blocks: dict[str, object] = {}
    agree = True
    for q in NEIGHBOUR_Q:
        alt, alt_counters = decline_thresholds(cands, entries, impulse,
                                               explore_days, q)
        got = seat_replay(chosen, CLOSE, S2_MAGNITUDE, magnitude, n_bars, alt,
                          None, mutant)
        alt_lines = paired_lines(got["trades"],
                                 replays[(S1_CHRONOLOGICAL, CLOSE)]["trades"],
                                 scoring)
        alt_paired = S22.maxt_inference(alt_lines, family, SIGN_DRAWS)
        flips: list[str] = []
        for asset in DECIDING:
            key = f"{LANE}|{asset}"
            a = paired["by_line"].get(key, {}).get("delta_usd_per_date")
            b = alt_paired["by_line"].get(key, {}).get("delta_usd_per_date")
            if a is None or b is None:
                flips.append(asset)
                continue
            if (float(a) > 0.0) != (float(b) > 0.0):
                flips.append(asset)
        if flips:
            agree = False
        neighbour_blocks[f"{q:.1f}"] = {
            "quantile": q, "threshold_counters": alt_counters,
            "seated": got["seated"], "declined": got["declined"],
            "cash": S22.replay_cash(got["trades"], explore_days),
            "delta": {asset: alt_paired["by_line"].get(
                f"{LANE}|{asset}", {}).get("delta_usd_per_date")
                for asset in ASSETS},
            "p_max_adjusted": {asset: alt_paired["by_line"].get(
                f"{LANE}|{asset}", {}).get("p_max_adjusted")
                for asset in DECIDING},
            "sign_flips": flips}
    neighbour_blocks["agree"] = bool(agree)

    # ---- the decline and priority ledgers ---------------------------------
    decline_ledger = decline_report(chosen, replays[(S2_MAGNITUDE, CLOSE)],
                                    replays[(S1_CHRONOLOGICAL, CLOSE)],
                                    magnitude, n_bars, thresholds, cands)
    collisions = collision_report(chosen, magnitude)

    report: dict[str, object] = {
        "schema": "QRE2MILLSWEEP29", "spec_sha": SPEC_SHA,
        "code_sha": code_sha(), "split_sha": S1.split_sha(),
        "outcome_law_sha": S1.outcome_law_sha(), "seed": SEED,
        "mutant": mutant, "family": FAMILY, "parent_trial": PARENT_TRIAL,
        "selection_rule": SELECTION_RULE, "registered_utc": report_stamp(),
        "decline_note": DECLINE_NOTE, "residual_note": RESIDUAL_NOTE,
        "order_note": ORDER_NOTE,
        "compression_note": S27.COMPRESSION_NOTE,
        "selector_sign_note": S23.SELECTOR_SIGN_NOTE,
        "contamination_note": S25.CONTAMINATION_NOTE,
        "parent_spec_sha": S28.SPEC_SHA, "parent_code_sha": S28.code_sha(),
        "accessor_code_sha": S1._sha_file(Path(LZ.__file__).resolve()),
        "store_code_sha": S1._sha_file(Path(ZH.__file__).resolve()),
        "licence": {
            "source": "sweep 28's receipt, .audit/mill-sweep28.json key "
                      "f24_licence, log row sweep28-039",
            "licensed": bool(licence["licensed"]),
            "verdict": licence["verdict"],
            "matched_deltas": licence["matched_deltas"],
            "occupancy": licence["occupancy"],
            "not_licensed_can_fire": False,
            "note": "NOT-LICENSED cannot fire in this unit: the licence is "
                    "already in the parent receipt and is cited, not re-derived"},
        "asset_days": {a: int(bundle["days"].get(a, 0)) for a in ASSETS},
        "reproduction": bundle["reproduction"],
        "reproduction_gate": gate,
        "stream_counters": bundle["stream_counters"],
        "causality": bundle["causal"],
        "formation": {k: v for k, v in bundle["formation"].items()
                      if k != "params"},
        "candidates_match_parent": bool(len(cands) == EXPECT_CANDIDATES),
        "zone_read": bundle["zone_read"],
        "store_build": bundle["store_build"], "store_audit": bundle["store_audit"],
        "genealogy_read": bundle["genealogy_read"],
        "impulse": bundle["impulse_report"], "impulse_join": bundle["impulse_join"],
        "impulse_counters": bundle["impulse_counters"],
        "ranker": bundle["rank_report"],
        "feature_law": {"names": list(FEATURES_ALL), "n": N_FEATURES,
                        "source": "sweep28.GEN_FEATURES_ALL, by value; the "
                                  "ranker is sweep 27's by call graph"},
        "magnitude_law": {
            "channel": "I_break, the frozen out-of-fold impulse score computed "
                       "by sweep22.impulse_scores under sweep 22's "
                       "walk-forward ridge on strictly prior days",
            "recomputed_here": False,
            "horizon_s": IMPULSE_HORIZON_S,
            "finite_selected": int(sum(1 for v in magnitude.values()
                                       if np.isfinite(v))),
            "selected": int(len(magnitude))},
        "decline_law": {
            "quantile": DECLINE_Q, "gap_quantile": GAP_Q,
            "neighbours": list(NEIGHBOUR_Q),
            "pool": "every PRICED candidate of the same asset and phase on "
                    "EXPLORE days STRICTLY EARLIER than the day being seated",
            "clock": "n_bars - bar - 1 >= gap_thr, with gap_thr the trained "
                     "median within-day bar gap between consecutive arrivals",
            "cap": f"seats already spent on the portfolio date < "
                   f"{PORTFOLIO_CAP - 1}",
            "fails_closed": "an undefined threshold never declines",
            "reads_future": bool(mutant == MUTANT_FUTURE),
            "counters": threshold_counters},
        "seating": seat, "paired": paired, "paired_1800": paired_1800,
        "paired_per_date": per_date,
        "neighbours": neighbour_blocks,
        "decline_ledger": decline_ledger, "collisions": collisions,
        "scoring_days": {a: scoring[a] for a in ASSETS},
        "clauses": CLAUSES, "clause_order": list(CLAUSE_ORDER),
        "elapsed_s": round(time.time() - started, 1)}
    letter = family_letter(report)
    report["letter"] = letter
    report["family_letter"] = letter["letter"]
    report["family_clause"] = letter["clause"]
    report["headline"] = headline(report)
    return report


def decline_report(chosen: Sequence[S22.Priced], s2: Mapping[str, object],
                   s1: Mapping[str, object], magnitude: Mapping[int, float],
                   n_bars: Mapping[int, int],
                   thresholds: Mapping[tuple[str, str, int], Mapping[str, float]],
                   cands: Sequence[S23.Cand]) -> dict[str, object]:
    """What the decline rule cost and what it bought, per asset, honestly.

    A decline is WORKED if the same asset-day later seats something under S2;
    it is a MIRROR if it does not, and the mirror's forgone cash is the price of
    the rule.  Both are counted at the same grain and both are inside every
    cash line already reported: nothing here is a correction to them.
    """

    declined = list(s2["declined_index"])                # type: ignore[index]
    seated = set(int(i) for i in s2["seated_index"])     # type: ignore[index]
    seated_by_key: dict[tuple[str, int], list[int]] = {}
    for i in sorted(seated):
        item = chosen[i]
        seated_by_key.setdefault((item.asset, int(item.d8)), []).append(i)
    per_asset: dict[str, object] = {}
    worked_total = 0
    mirror_total = 0
    forgone = 0.0
    recovered = 0.0
    for asset in ASSETS:
        mine = [i for i in declined if chosen[i].asset == asset]
        worked: list[int] = []
        mirror: list[int] = []
        for i in mine:
            item = chosen[i]
            later = [j for j in seated_by_key.get((asset, int(item.d8)), [])
                     if int(chosen[j].entry_ts_ns) > int(item.entry_ts_ns)]
            (worked if later else mirror).append(i)
        worked_total += len(worked)
        mirror_total += len(mirror)
        mirror_cash = float(sum(chosen[i].cert[CLOSE] for i in mirror))
        worked_cash = float(sum(chosen[i].cert[CLOSE] for i in worked))
        forgone += mirror_cash
        recovered += worked_cash
        per_asset[asset] = {
            "declined": len(mine), "worked": len(worked), "mirror": len(mirror),
            "declined_cash_usd": float(sum(chosen[i].cert[CLOSE] for i in mine)),
            "mirror_forgone_usd": mirror_cash,
            "worked_declined_cash_usd": worked_cash,
            "mean_magnitude": (float(np.mean([magnitude[i] for i in mine]))
                               if mine else None)}
    s1_seated = set(int(i) for i in s1["seated_index"])  # type: ignore[index]
    return {
        "declined": len(declined), "worked": worked_total,
        "mirror": mirror_total,
        "mirror_forgone_usd": forgone,
        "worked_declined_cash_usd": recovered,
        "per_asset": per_asset,
        "seat_swaps": {
            "s2_only": int(len(seated - s1_seated)),
            "s1_only": int(len(s1_seated - seated)),
            "both": int(len(seated & s1_seated))},
        "definition": "a decline WORKED if its asset-day later seats an entry "
                      "under S2; a MIRROR decline is one where nothing later "
                      "seated, and its forgone cash is the honest cost of the "
                      "rule, already inside every S2 cash line"}


def collision_report(chosen: Sequence[S22.Priced],
                     magnitude: Mapping[int, float]) -> dict[str, object]:
    """Equal-stamp seat contention: how often priority has anything to decide."""

    groups: dict[tuple[str, int], list[int]] = {}
    for index, item in enumerate(chosen):
        groups.setdefault((item.asset, int(item.entry_ts_ns)), []).append(index)
    same_asset = [rows for rows in groups.values() if len(rows) > 1]
    reordered = 0
    for rows in same_asset:
        chrono = sorted(rows, key=lambda i: (chosen[i].asset, int(chosen[i].cell),
                                             int(chosen[i].bar),
                                             int(chosen[i].side)))
        by_mag = sorted(rows, key=lambda i: (
            -(magnitude[i] if np.isfinite(magnitude[i]) else -math.inf),
            chosen[i].asset, int(chosen[i].cell), int(chosen[i].bar),
            int(chosen[i].side)))
        reordered += int(chrono[0] != by_mag[0])
    stamps: dict[int, list[int]] = {}
    for index, item in enumerate(chosen):
        stamps.setdefault(int(item.entry_ts_ns), []).append(index)
    return {
        "same_asset_stamp_groups": len(same_asset),
        "same_asset_events_in_groups": int(sum(len(r) for r in same_asset)),
        "same_asset_groups_reordered": reordered,
        "cross_asset_stamp_groups": int(sum(
            1 for rows in stamps.values()
            if len({chosen[i].asset for i in rows}) > 1)),
        "note": "a cross-asset equal stamp costs no seat while the portfolio "
                "cap does not bind, since occupancy is per asset"}


def headline(report: Mapping[str, object]) -> dict[str, object]:
    live = report["seating"][S2_MAGNITUDE][CLOSE]        # type: ignore[index]
    paired = report["paired"]["by_line"]                 # type: ignore[index]
    return {
        "s2_over_rung": {
            asset: (None if live["cash"][asset]["usd_per_day"] is None else
                    float(live["cash"][asset]["usd_per_day"])
                    / DAY_RUNG_USD[asset]) for asset in DECIDING},
        "s2_usd_day": {asset: live["cash"][asset]["usd_per_day"]
                       for asset in ASSETS},
        "paired_delta": {asset: paired.get(f"{LANE}|{asset}", {}).get(
            "delta_usd_per_date") for asset in ASSETS},
        "paired_p_adjusted": {asset: paired.get(f"{LANE}|{asset}", {}).get(
            "p_max_adjusted") for asset in DECIDING},
        "paired_upper95": {asset: paired.get(f"{LANE}|{asset}", {}).get(
            "upper95_simultaneous_usd") for asset in DECIDING},
        "s2_max_binding_mdd_usd": live["mdd"]["max_binding_usd"],
        "mdd_ceiling_usd": float(MDD_CEILING),
        "s2_mdd_clears": bool(live["mdd"]["clears"]),
        "letter": report["family_letter"], "clause": report["family_clause"]}


# --------------------------------------------------------------------------
# Reporting.
# --------------------------------------------------------------------------

def print_summary(report: Mapping[str, object]) -> None:
    head = report["headline"]
    print(f"\nSWEEP 29  {FAMILY}  seed {SEED}  parent {PARENT_TRIAL}"
          f"  mutant={report['mutant'] or 'none'}")
    print("  " + "S2 deciding usd/day over rung " + ", ".join(
        f"{asset} {_show(head['s2_over_rung'].get(asset))}x"
        for asset in DECIDING)
        + "; PAIRED S2-S1 " + ", ".join(
            f"{asset} {_show(head['paired_delta'].get(asset))} usd/date at "
            f"adjusted p {_show(head['paired_p_adjusted'].get(asset))}"
            for asset in DECIDING)
        + f"; S2 max binding MDD {_show(head['s2_max_binding_mdd_usd'])} "
          f"against {MDD_CEILING} -> clears {head['s2_mdd_clears']}")
    print(f"  LETTER {head['letter']} (clause {head['clause']})")


def print_licence(report: Mapping[str, object]) -> None:
    lic = report["licence"]
    print("\nLICENCE, cited and not re-derived")
    print(f"  source            {lic['source']}")
    print(f"  verdict           {lic['verdict']}")
    print("  matched deltas    " + ", ".join(
        f"{a} {_show(v)}" for a, v in sorted(lic["matched_deltas"].items())))
    for name, cell in sorted(lic["occupancy"].items()):
        print(f"  occupancy {name:<7} {cell['rejected_occupancy']} of "
              f"{cell['selected']} selected lost to occupancy "
              f"(share {_show(cell['occupancy_share'])}), seated "
              f"{cell['seated']}")
    print(f"  NOT-LICENSED can fire: {lic['not_licensed_can_fire']}")


def print_gate(report: Mapping[str, object]) -> None:
    gate = report["reproduction_gate"]
    print("\nTHE REPRODUCTION GATE: the qualified entry set is sweep 28's")
    exp = gate["expected"]
    obs = gate["observed"]
    print(f"  formed candidates    {report['formation']['counters']['candidates']}"
          f"  (parent {EXPECT_CANDIDATES})")
    print(f"  selected             {obs['selected']}  (parent {exp['selected']})")
    print("  per asset            " + ", ".join(
        f"{a} {obs['per_asset'][a]} (parent {exp['per_asset'][a]})"
        for a in ASSETS))
    print(f"  S1 seated            {obs['seated']}  (parent {exp['seated']})")
    print(f"  S1 occupancy losses  {obs['rejected_occupancy']}  "
          f"(parent {exp['rejected_occupancy']})")
    print(f"  S1 cap losses        {obs['rejected_cap']}  "
          f"(parent {exp['rejected_cap']})")
    for asset in ASSETS:
        print(f"  S1 {asset:<3} usd/day       {_show(obs['usd_per_day'][asset])}"
              f"  (parent {exp['usd_per_day'][asset]:.8f}), trades "
              f"{obs['trades'][asset]} (parent {exp['trades'][asset]})")
    print(f"  breakdown match      zone_kind / year / phase to 1e-6 USD")
    print(f"  GATE {'PASSED' if gate['ok'] else 'FAILED'}")
    for line in gate["failures"]:
        print(f"    ! {line}")


def print_decline_law(report: Mapping[str, object]) -> None:
    law = report["decline_law"]
    ledger = report["decline_ledger"]
    coll = report["collisions"]
    print("\nTHE SEATING DISCIPLINE UNDER TEST, registered before pricing")
    print(f"  magnitude channel    {report['magnitude_law']['channel']}")
    print(f"  recomputed here      {report['magnitude_law']['recomputed_here']}"
          f"; finite on {report['magnitude_law']['finite_selected']} of "
          f"{report['magnitude_law']['selected']} selected")
    print(f"  decline threshold    train quantile {law['quantile']} of the "
          f"asset-phase prior-day magnitude pool")
    print(f"  schedule test        {law['clock']}")
    print(f"  cap test             {law['cap']}")
    print(f"  fails closed         {law['fails_closed']}")
    print(f"  reads the future     {law['reads_future']}")
    print(f"  threshold cells      {law['counters']['defined']} defined of "
          f"{law['counters']['cells']} (no magnitude pool "
          f"{law['counters']['no_mag']}, no gap pool {law['counters']['no_gap']})")
    print("\nPRIORITY AND DECLINE LEDGERS")
    print(f"  equal-stamp same-asset groups {coll['same_asset_stamp_groups']} "
          f"covering {coll['same_asset_events_in_groups']} events; magnitude "
          f"changes who is first in {coll['same_asset_groups_reordered']}")
    print(f"  cross-asset equal stamps      {coll['cross_asset_stamp_groups']}")
    print(f"  declines {ledger['declined']}: worked {ledger['worked']}, "
          f"mirror {ledger['mirror']} (forgone "
          f"{_show(ledger['mirror_forgone_usd'])} USD)")
    print(f"  seat swaps: S2 only {ledger['seat_swaps']['s2_only']}, S1 only "
          f"{ledger['seat_swaps']['s1_only']}, both "
          f"{ledger['seat_swaps']['both']}")
    print(f"  {'asset':<5} {'declined':>9} {'worked':>7} {'mirror':>7} "
          f"{'mirror USD':>11} {'mean m':>9}")
    for asset in ASSETS:
        cell = ledger["per_asset"][asset]
        print(f"  {asset:<5} {cell['declined']:>9} {cell['worked']:>7} "
              f"{cell['mirror']:>7} {_n(cell['mirror_forgone_usd'], 11, 2)} "
              f"{_n(cell['mean_magnitude'], 9, 3)}")


def print_seatings(report: Mapping[str, object]) -> None:
    print("\nTHE TWO SEATINGS, SIDE BY SIDE, over the SAME 461 qualified events")
    for label in LABELS:
        print(f"\n  label {label}")
        print(f"  {'asset':<5} | {'S1 n':>5} {'S1 usd/day':>11} {'S1 -2SE':>10} "
              f"{'S1 zero':>8} | {'S2 n':>5} {'S2 usd/day':>11} {'S2 -2SE':>10} "
              f"{'S2 zero':>8} | {'d usd/day':>10}")
        for asset in ASSETS:
            a = report["seating"][S1_CHRONOLOGICAL][label]["cash"][asset]
            b = report["seating"][S2_MAGNITUDE][label]["cash"][asset]
            delta = (None if a["usd_per_day"] is None or b["usd_per_day"] is None
                     else float(b["usd_per_day"]) - float(a["usd_per_day"]))
            print(f"  {asset:<5} | {a['trades']:>5} {_n(a['usd_per_day'], 11, 3)} "
                  f"{_n(a['mean_minus_2se_usd'], 10, 2)} "
                  f"{_n(a['zero_entry_fraction'], 8, 3)} | "
                  f"{b['trades']:>5} {_n(b['usd_per_day'], 11, 3)} "
                  f"{_n(b['mean_minus_2se_usd'], 10, 2)} "
                  f"{_n(b['zero_entry_fraction'], 8, 3)} | "
                  f"{_n(delta, 10, 3)}")
        for seating in SEATINGS:
            block = report["seating"][seating][label]
            rep = block["replay"]
            port = block["cash"]["_portfolio"]
            print(f"    {seating:<17} seated {rep['seated']:>4}, occupancy "
                  f"{rep['rejected_occupancy']:>4}, cap {rep['rejected_cap']:>3}, "
                  f"declined {rep['declined']:>4}; dates with entries "
                  f"{port['dates_with_entries']}, max seats/date "
                  f"{port['portfolio_seats_max']}, cap lawful "
                  f"{port['cap_lawful']}, occupancy lawful "
                  f"{block['occupancy_lawful']}")


def print_mdd(report: Mapping[str, object]) -> None:
    print("\nMDD LEDGERS, every binding grain, primary label")
    block = report["seating"][S2_MAGNITUDE][CLOSE]["mdd"]
    keys = list(block["binding_ledgers"])
    print(f"  {'ledger':<18} {'S1 USD':>12} {'S2 USD':>12}  binding")
    base = report["seating"][S1_CHRONOLOGICAL][CLOSE]["mdd"]
    for key in sorted(set(list(base) + list(block))):
        if key in ("binding_ledgers", "max_binding_usd", "clears"):
            continue
        print(f"  {key:<18} {_n(base.get(key), 12, 2)} {_n(block.get(key), 12, 2)}"
              f"  {'yes' if key in keys else 'no'}")
    print(f"  {'MAX BINDING':<18} {_n(base['max_binding_usd'], 12, 2)} "
          f"{_n(block['max_binding_usd'], 12, 2)}  ceiling {MDD_CEILING}")
    print(f"  {'clears ceiling':<18} {str(base['clears']):>12} "
          f"{str(block['clears']):>12}")
    print("\nSTRESSES, S2, primary label")
    for kind in ("adversarial", "spread"):
        cell = report["seating"][S2_MAGNITUDE][CLOSE]["stress"][kind]
        print(f"  {kind:<12} seated {cell['seated']:>4}, " + ", ".join(
            f"{a} {_n(cell['cash'][a]['usd_per_day'], 9, 2)} usd/day"
            for a in ASSETS)
            + f"; max binding MDD {_n(cell['mdd']['max_binding_usd'], 10, 2)} "
              f"clears {cell['mdd']['clears']}")
    print("  STRESSES, S1, primary label")
    for kind in ("adversarial", "spread"):
        cell = report["seating"][S1_CHRONOLOGICAL][CLOSE]["stress"][kind]
        print(f"  {kind:<12} seated {cell['seated']:>4}, " + ", ".join(
            f"{a} {_n(cell['cash'][a]['usd_per_day'], 9, 2)} usd/day"
            for a in ASSETS)
            + f"; max binding MDD {_n(cell['mdd']['max_binding_usd'], 10, 2)} "
              f"clears {cell['mdd']['clears']}")


def print_paired(report: Mapping[str, object]) -> None:
    print("\nTHE TESTED OBJECT: S2 minus S1 seated cash, paired by shared date")
    for name, block in (("close  (PRIMARY)", report["paired"]),
                        ("1800 s (information)", report["paired_1800"])):
        print(f"\n  {name}: {block['dates']} shared dates, {block['draws']} "
              f"sign draws, maxT c95 {_show(block['c95'])}")
        print(f"  {'line':<22} {'delta/date':>11} {'SE':>10} {'t':>8} "
              f"{'adj p':>8} {'lower95':>11} {'upper95':>11}  eligible")
        for key in sorted(block["by_line"]):
            cell = block["by_line"][key]
            print(f"  {key:<22} {_n(cell['delta_usd_per_date'], 11, 3)} "
                  f"{_n(cell['se_usd'], 10, 3)} {_n(cell['t'], 8, 3)} "
                  f"{_n(cell['p_max_adjusted'], 8, 4)} "
                  f"{_n(cell['lower95_simultaneous_usd'], 11, 3)} "
                  f"{_n(cell['upper95_simultaneous_usd'], 11, 3)}  "
                  f"{cell['eligible']}")
    print("\n  the per-date pairing, dates where the two seatings differ")
    for asset in ASSETS:
        cell = report["paired_per_date"][f"{LANE}|{asset}"]
        for label in ("close", "1800"):
            rows = cell[label]
            shown = ", ".join(f"{d8}:{value:+.2f}"
                              for d8, value in sorted(rows.items())[:12])
            print(f"    {asset:<4} {label:<6} {len(rows):>3} dates differ"
                  + (f"  {shown}" + (" ..." if len(rows) > 12 else "")
                     if rows else ""))
    print("\n  NEIGHBOURS, the decline threshold at train quantiles "
          f"{list(NEIGHBOUR_Q)}")
    print(f"  {'q':<5} {'declined':>9} {'seated':>7} " + " ".join(
        f"{'d ' + a:>11}" for a in ASSETS) + "  sign flips")
    for q in NEIGHBOUR_Q:
        cell = report["neighbours"][f"{q:.1f}"]
        print(f"  {q:<5} {cell['declined']:>9} {cell['seated']:>7} " + " ".join(
            _n(cell["delta"].get(a), 11, 3) for a in ASSETS)
            + f"  {cell['sign_flips'] or 'none'}")
    print(f"  neighbours agree: {report['neighbours']['agree']}")


def print_decision(report: Mapping[str, object]) -> None:
    cell = report["letter"]
    print("\nTHE DECISION TABLE")
    print(f"  {'test':<34} {'result':>8}")
    for name, key in (("both deciding rungs, point and -2SE", "rung_ok"),
                      ("every S2 binding MDD below 1000", "mdd_ok"),
                      ("portfolio cap lawful", "cap_ok"),
                      ("occupancy lawful", "occupancy_ok"),
                      ("both stresses clear", "stress_ok"),
                      ("paired deltas positive at p<=0.05", "paired_ok"),
                      ("neither neighbour flips a sign", "neighbours_ok"),
                      ("paired upper bound non-positive", "paired_upper_nonpositive"),
                      ("S2 MDD not below 1000", "mdd_not_below_ceiling"),
                      ("bounds defined", "bounds_defined"),
                      ("both paired deltas positive", "deltas_positive")):
        print(f"  {name:<34} {str(cell[key]):>8}")
    print(f"\n  clauses matching {cell['clauses_matching']}")
    print(f"  CLAUSE {cell['clause']} = {cell['clause_text']}")
    print(f"  LETTER {cell['letter']}")
    for line in cell["reasons"]:
        print(f"    - {line}")
    print(f"  NOT-LICENSED cannot fire: {cell['licence']}")
    if cell["letter"] == LETTER_UNRESOLVED:
        print("  ON UNRESOLVED THE RECEIPT FREEZES: no coverage, no threshold "
              "and no seating variant is tuned on these outcomes.")


# --------------------------------------------------------------------------
# Selftest fixtures.
# --------------------------------------------------------------------------

def _plant(asset: str, d8: int, stamp: int, exit_ts: int, pnl: float,
           bar: int, cell: int = 1, phase: str = "0") -> S22.Priced:
    """A hand-built priced entry, sweep 22's fixture shape."""

    return S22.Priced(
        lane=LANE, position=0, asset=asset, d8=d8, phase=phase, cell=cell,
        bar=bar, exit_bar=bar + 1, side=1, entry_ts_ns=stamp, entry_mid2=0,
        cost_usd=0.0, spread_usd=1.0,
        cert={CLOSE: pnl, FIXED: pnl}, wall={CLOSE: False, FIXED: False},
        mae={CLOSE: 10.0, FIXED: 10.0}, mfe={CLOSE: 0.0, FIXED: 0.0},
        exit_ts={CLOSE: exit_ts, FIXED: exit_ts})


def _selftest_collision(mutant: str) -> list[tuple[str, bool, str]]:
    """A planted collision day: two seatable arrivals, one seat, hand-verified.

    Both entries arrive at the SAME stamp on the SAME asset while it is flat.
    Chronology breaks the tie on (cell, bar, side) and seats the low-magnitude
    one; magnitude priority seats the high-magnitude one.  The cash is planted
    so the two answers are distinguishable: the low-magnitude entry pays 10, the
    high-magnitude entry pays 100.
    """

    low = _plant("NKD", 20220601, 1_000, 9_000, 10.0, bar=5, cell=1)
    high = _plant("NKD", 20220601, 1_000, 9_000, 100.0, bar=5, cell=2)
    entries = [low, high]
    magnitude = {0: 0.10, 1: 0.90}
    n_bars = {0: 400, 1: 400}
    # No thresholds: the decline rule fails closed, so ONLY priority is on test.
    chrono = seat_replay(entries, CLOSE, S1_CHRONOLOGICAL)
    prio = seat_replay(entries, CLOSE, S2_MAGNITUDE, magnitude, n_bars, None,
                       None, mutant)
    out = [_check(
        "A PLANTED COLLISION: two qualified entries at one stamp, one seat, "
        "and magnitude takes it",
        chrono["seated"] == 1 and prio["seated"] == 1
        and abs(chrono["trades"][0].pnl_usd - 10.0) < 1e-9
        and abs(prio["trades"][0].pnl_usd - 100.0) < 1e-9,
        f"chronological seats {chrono['trades'][0].pnl_usd:.1f}, magnitude "
        f"seats {prio['trades'][0].pnl_usd:.1f}")]
    out.append(_check(
        "the collision costs the same one seat under both disciplines",
        chrono["rejected_occupancy"] == 1 and prio["rejected_occupancy"] == 1,
        f"chronological {chrono['rejected_occupancy']}, magnitude "
        f"{prio['rejected_occupancy']}"))
    tie = seat_replay([low, high], CLOSE, S2_MAGNITUDE, {0: 0.5, 1: 0.5},
                      n_bars, None, None, mutant)
    out.append(_check(
        "an exact magnitude tie falls back to the chronological tie-break",
        abs(tie["trades"][0].pnl_usd - 10.0) < 1e-9,
        f"seats {tie['trades'][0].pnl_usd:.1f}"))
    nan_first = seat_replay([low, high], CLOSE, S2_MAGNITUDE,
                            {0: float("nan"), 1: 0.1}, n_bars, None, None,
                            mutant)
    out.append(_check(
        "a non-finite magnitude sorts last and never wins a seat",
        abs(nan_first["trades"][0].pnl_usd - 100.0) < 1e-9,
        f"seats {nan_first['trades'][0].pnl_usd:.1f}"))
    return out


def _selftest_decline(mutant: str) -> list[tuple[str, bool, str]]:
    """The planted decline, its mirror, and the proof it cannot see the future.

    WORLD A: a below-threshold arrival at bar 5, and an above-threshold arrival
    at bar 120 of a 400-bar session.  The trained gap is 20 bars, so at bar 5
    the remaining schedule (394) clears it: the low arrival is DECLINED and the
    later high arrival takes the seat.  Hand-verified: 200 USD instead of 10.

    WORLD B is WORLD A with the later arrival deleted.  It is identical to
    WORLD A at and before the decision stamp.  The decline rule must make the
    SAME decision - decline - and the day must then earn NOTHING.  That is the
    mirror, and it is the honest price of the rule.
    """

    low = _plant("SI", 20220701, 1_000, 9_000, 10.0, bar=5, cell=1)
    high = _plant("SI", 20220701, 5_000, 9_000, 200.0, bar=120, cell=1)
    thresholds = {("SI", "0", 20220701): {"mag_thr": 0.5, "gap_thr": 20.0}}
    world_a = seat_replay([low, high], CLOSE, S2_MAGNITUDE, {0: 0.1, 1: 0.9},
                          {0: 400, 1: 400}, thresholds, None, mutant)
    chrono_a = seat_replay([low, high], CLOSE, S1_CHRONOLOGICAL)
    out = [_check(
        "A PLANTED DECLINE: a below-threshold arrival is declined while flat "
        "and the later above-threshold arrival takes the seat",
        world_a["declined"] == 1 and world_a["seated"] == 1
        and abs(world_a["trades"][0].pnl_usd - 200.0) < 1e-9
        and chrono_a["seated"] == 1
        and abs(chrono_a["trades"][0].pnl_usd - 10.0) < 1e-9,
        f"S2 declines {world_a['declined']} and seats "
        f"{world_a['trades'][0].pnl_usd if world_a['trades'] else None}; S1 "
        f"seats {chrono_a['trades'][0].pnl_usd if chrono_a['trades'] else None}"
        f" and loses {chrono_a['rejected_occupancy']} to occupancy")]

    world_b = seat_replay([low], CLOSE, S2_MAGNITUDE, {0: 0.1},
                          {0: 400}, thresholds, None, mutant)
    chrono_b = seat_replay([low], CLOSE, S1_CHRONOLOGICAL)
    out.append(_check(
        "THE MIRROR: the same decline with NOTHING later, priced honestly as "
        "the cost of the rule",
        world_b["declined"] == 1 and world_b["seated"] == 0
        and chrono_b["seated"] == 1
        and abs(chrono_b["trades"][0].pnl_usd - 10.0) < 1e-9,
        f"S2 declines {world_b['declined']}, seats {world_b['seated']} and "
        f"forgoes 10.0 USD; S1 seats {chrono_b['seated']} for "
        f"{chrono_b['trades'][0].pnl_usd if chrono_b['trades'] else None}"))
    out.append(_check(
        "THE DECLINE RULE IS BLIND TO THE FUTURE: two worlds identical up to "
        "the decision stamp and different after it get the SAME decision",
        world_a["declined_index"][:1] == [0] == world_b["declined_index"][:1],
        f"world with a later arrival declines {world_a['declined_index']}, "
        f"world without one declines {world_b['declined_index']}"))

    late = _plant("SI", 20220701, 1_000, 9_000, 10.0, bar=395, cell=1)
    clock = seat_replay([late], CLOSE, S2_MAGNITUDE, {0: 0.1}, {0: 400},
                        thresholds, None, mutant)
    out.append(_check(
        "the clock refuses a decline when the remaining schedule is shorter "
        "than one trained inter-arrival gap",
        clock["declined"] == 0 and clock["seated"] == 1,
        f"remaining bars 4 against gap 20: declined {clock['declined']}, "
        f"seated {clock['seated']}"))

    closed = seat_replay([low], CLOSE, S2_MAGNITUDE, {0: 0.1}, {0: 400}, {},
                         None, mutant)
    out.append(_check(
        "the decline rule FAILS CLOSED: an undefined threshold never declines",
        closed["declined"] == 0 and closed["seated"] == 1
        and closed["decline_undefined"] == 1,
        f"declined {closed['declined']}, seated {closed['seated']}, undefined "
        f"{closed['decline_undefined']}"))

    filler = [_plant(("HG", "NKD", "SI")[i % 3], 20220701, 10 * (i + 1),
                     10 * (i + 1) + 1, 1.0, bar=10 + i, cell=10 + i)
              for i in range(PORTFOLIO_CAP - 1)]
    crowd = seat_replay(filler + [low], CLOSE, S2_MAGNITUDE,
                        {i: 0.9 for i in range(len(filler))}
                        | {len(filler): 0.1},
                        {i: 400 for i in range(len(filler) + 1)}, thresholds,
                        None, mutant)
    out.append(_check(
        "a decline is refused when the portfolio date has no room for a LATER "
        "seat",
        crowd["declined"] == 0 and crowd["decline_blocked_cap"] == 1
        and crowd["seated"] == PORTFOLIO_CAP,
        f"{len(filler)} seats already spent: declined {crowd['declined']}, "
        f"blocked by cap {crowd['decline_blocked_cap']}, seated "
        f"{crowd['seated']}"))
    return out


def _selftest_s1_is_the_standing_law() -> list[tuple[str, bool, str]]:
    """S1 is ``sweep22.replay`` and not a paraphrase of it, on fixtures."""

    worlds = {
        "occupancy": [_plant("NKD", 20220101, 100, 300, 10.0, 1),
                      _plant("NKD", 20220101, 200, 400, 20.0, 2)],
        "the exits-before-entries seam": [
            _plant("NKD", 20220101, 100, 200, 10.0, 1),
            _plant("NKD", 20220101, 200, 300, 20.0, 2)],
        "the portfolio cap": [
            _plant("NKD" if i % 2 else "SI", 20220101, 100 * i, 100 * i + 1,
                   1.0, i + 1) for i in range(1, 20)],
    }
    out: list[tuple[str, bool, str]] = []
    for name, entries in worlds.items():
        mine = seat_replay(entries, CLOSE, S1_CHRONOLOGICAL)
        theirs = S22.replay(entries, CLOSE)
        same = (mine["seated"] == theirs["seated"]
                and mine["rejected_occupancy"] == theirs["rejected_occupancy"]
                and mine["rejected_cap"] == theirs["rejected_cap"]
                and [t.pnl_usd for t in mine["trades"]]
                == [t.pnl_usd for t in theirs["trades"]])
        out.append(_check(
            f"S1 IS THE STANDING LAW, not a paraphrase: {name}", same,
            f"mine seated {mine['seated']}/{mine['rejected_occupancy']}/"
            f"{mine['rejected_cap']}, sweep22 {theirs['seated']}/"
            f"{theirs['rejected_occupancy']}/{theirs['rejected_cap']}"))
    return out


def _selftest_thresholds() -> list[tuple[str, bool, str]]:
    """The trained thresholds read strictly prior days and nothing else."""

    class _C:
        __slots__ = ("asset", "phase", "d8", "bar", "n_bars")

        def __init__(self, asset, phase, d8, bar):
            self.asset = asset
            self.phase = phase
            self.d8 = d8
            self.bar = bar
            self.n_bars = 400

    cands = [_C("SI", "0", 20220101, 10), _C("SI", "0", 20220101, 30),
             _C("SI", "0", 20220102, 20), _C("SI", "0", 20220103, 40)]
    entries = {i: None for i in range(len(cands))}
    magnitude = np.asarray([1.0, 3.0, 100.0, 0.0], np.float64)
    days = {"SI": [20220101, 20220102, 20220103], "NKD": [], "HG": []}
    table, counters = decline_thresholds(cands, entries, magnitude, days, 0.5)
    out = [_check(
        "the first day of an asset-phase has NO trained threshold, so it can "
        "never decline",
        ("SI", "0", 20220101) not in table,
        f"cells defined {sorted(k[2] for k in table)}")]
    cell = table.get(("SI", "0", 20220103))
    out.append(_check(
        "the threshold on day 3 is the median of days 1 and 2 ONLY, never of "
        "its own day",
        cell is not None and abs(float(cell["mag_thr"]) - 3.0) < 1e-9
        and int(cell["train_rows"]) == 3,
        f"{cell}"))
    out.append(_check(
        "the trained gap is the median WITHIN-DAY bar gap of prior days",
        cell is not None and abs(float(cell["gap_thr"]) - 20.0) < 1e-9,
        f"gap {None if cell is None else cell['gap_thr']}"))
    later = decline_thresholds(cands + [_C("SI", "0", 20220104, 5)], entries,
                               np.append(magnitude, -999.0), days, 0.5)[0]
    out.append(_check(
        "a day AFTER the last EXPLORE day cannot move any earlier threshold",
        later.get(("SI", "0", 20220103), {}).get("mag_thr")
        == table.get(("SI", "0", 20220103), {}).get("mag_thr"),
        f"{later.get(('SI', '0', 20220103))}"))
    out.append(_check(
        "every threshold cell is accounted for",
        counters["cells"] == counters["defined"] + counters["no_mag"],
        f"{counters}"))
    return out


def _selftest_pairing() -> list[tuple[str, bool, str]]:
    """The paired-date law: shared dates, carried zeros, no event-level unit."""

    def trade(asset: str, d8: int, pnl: float) -> S22.Trade:
        return S22.Trade(asset=asset, d8=d8, cell=1, bar=1, exit_bar=2, side=1,
                         entry_ts_ns=1, exit_ts_ns=2, entry_mid2=0,
                         cost_usd=0.0, pnl_usd=pnl)

    s2 = [trade("NKD", 20220101, 100.0), trade("NKD", 20220103, 50.0)]
    s1 = [trade("NKD", 20220101, 40.0), trade("NKD", 20220102, 70.0)]
    scoring = {"NKD": [20220101, 20220102, 20220103, 20220104], "HG": [],
               "SI": []}
    lines = paired_lines(s2, s1, scoring)[f"{LANE}|NKD"]
    out = [_check(
        "THE PAIRED-DATE LAW: the unit is the shared calendar date and every "
        "scored date is carried, zeros included",
        sorted(lines) == [20220101, 20220102, 20220103, 20220104],
        f"{sorted(lines)}")]
    out.append(_check(
        "a date where only S1 seats enters as a NEGATIVE difference, not as a "
        "dropped row",
        abs(lines[20220102] + 70.0) < 1e-9, f"{lines[20220102]}"))
    out.append(_check(
        "a date where only S2 seats enters as a POSITIVE difference",
        abs(lines[20220103] - 50.0) < 1e-9, f"{lines[20220103]}"))
    out.append(_check(
        "a date both seat is differenced, not summed",
        abs(lines[20220101] - 60.0) < 1e-9, f"{lines[20220101]}"))
    out.append(_check(
        "a date neither seats contributes exactly zero and still counts as a "
        "date",
        abs(lines[20220104]) < 1e-12, f"{lines[20220104]}"))
    same = paired_lines(s1, s1, scoring)[f"{LANE}|NKD"]
    out.append(_check(
        "an identical seating pairs to an exactly zero line",
        all(abs(v) < 1e-12 for v in same.values()), f"{same}"))
    got = S22.maxt_inference(paired_lines(s2, s1, scoring),
                             [f"{LANE}|{a}" for a in DECIDING], 200)
    out.append(_check(
        "the maxT family is the two deciding lines and HG is not eligible",
        got["by_line"][f"{LANE}|HG"]["eligible"] is False
        and got["by_line"][f"{LANE}|NKD"]["eligible"] is True,
        f"family {got['family']}"))
    return out


def _receipt(usd: float, mdd: float, p: float, delta: float | None,
             upper: float | None, neighbours: bool = True,
             stress: bool = True, cap: bool = True,
             occupancy: bool = True) -> dict[str, object]:
    """A hand-built receipt, in the exact shape ``family_letter`` reads."""

    cash = {asset: {"usd_per_day": usd, "mean_minus_2se_usd": usd - 10.0,
                    "clears_rung": bool(usd - 10.0 >= DAY_RUNG_USD[asset])}
            for asset in ASSETS}
    cash["_portfolio"] = {"cap_lawful": cap}
    ledger = {"clears": bool(mdd < MDD_CEILING), "max_binding_usd": mdd}
    stress_block = {kind: {"mdd": {"clears": stress}}
                    for kind in ("adversarial", "spread")}
    line = {"delta_usd_per_date": delta, "p_max_adjusted": p,
            "upper95_simultaneous_usd": upper}
    return {
        "seating": {S2_MAGNITUDE: {CLOSE: {
            "cash": cash, "mdd": ledger, "stress": stress_block,
            "occupancy_lawful": occupancy}}},
        "paired": {"by_line": {f"{LANE}|{asset}": dict(line)
                               for asset in ASSETS}},
        "neighbours": {"agree": neighbours}}


def _selftest_letters() -> list[tuple[str, bool, str]]:
    """The registered letters fire on constructed receipts, and only them."""

    out: list[tuple[str, bool, str]] = []
    live = family_letter(_receipt(3000.0, 500.0, 0.01, 120.0, 300.0))
    out.append(_check("SIZESEAT-LIVE fires on a receipt that clears everything",
                      live["letter"] == LETTER_LIVE and live["clause"] == "LIVE",
                      f"{live['letter']} / {live['clause']}"))
    # A non-positive simultaneous upper bound forces a non-positive point
    # estimate - upper = mean + c95 * SE with c95 >= 0 and SE >= 0 - so the K1
    # receipt is built the only way it can exist.
    k1 = family_letter(_receipt(3000.0, 500.0, 0.90, -50.0, -1.0))
    out.append(_check(
        "K1 KILLS on a non-positive paired simultaneous upper bound",
        k1["letter"] == LETTER_KILL and k1["clause"] == "K1",
        f"{k1['letter']} / {k1['clause']}"))
    k1_zero = family_letter(_receipt(3000.0, 500.0, 0.90, -50.0, 0.0))
    out.append(_check("a paired upper bound of exactly zero is a KILL",
                      k1_zero["clause"] == "K1", f"{k1_zero['clause']}"))
    k1_first = family_letter(_receipt(3000.0, 5000.0, 0.90, -50.0, -1.0))
    out.append(_check(
        "K1 takes precedence over K2 when both kills match, and the letter is "
        "the same either way",
        k1_first["clause"] == "K1" and k1_first["letter"] == LETTER_KILL
        and set(k1_first["clauses_matching"]) == {"K1", "K2"},
        f"{k1_first['clause']} of {k1_first['clauses_matching']}"))
    k2 = family_letter(_receipt(3000.0, 1000.0, 0.01, 120.0, 300.0))
    out.append(_check(
        "K2 KILLS when the S2 binding MDD does not fall below 1000",
        k2["letter"] == LETTER_KILL and k2["clause"] == "K2",
        f"{k2['letter']} / {k2['clause']} at MDD 1000.0"))
    u1 = family_letter(_receipt(3000.0, 500.0, 0.20, 120.0, 300.0))
    out.append(_check(
        "U1 parks a positive-but-underpowered paired delta",
        u1["letter"] == LETTER_UNRESOLVED and u1["clause"] == "U1",
        f"{u1['letter']} / {u1['clause']}"))
    u0 = family_letter(_receipt(3000.0, 500.0, 0.20, -5.0, 300.0))
    out.append(_check(
        "U0 takes a negative-but-not-killed paired delta as the residual",
        u0["letter"] == LETTER_UNRESOLVED and u0["clause"] == "U0",
        f"{u0['letter']} / {u0['clause']}"))
    undef = family_letter(_receipt(3000.0, 500.0, 0.01, None, None))
    out.append(_check(
        "U0 also takes an UNDEFINED deciding bound, and no kill fires on it",
        undef["clause"] == "U0", f"{undef['clause']}"))
    miss = family_letter(_receipt(10.0, 500.0, 0.01, 120.0, 300.0))
    out.append(_check("a missed rung cannot be LIVE",
                      miss["clause"] == "U1", f"{miss['clause']}"))
    flip = family_letter(_receipt(3000.0, 500.0, 0.01, 120.0, 300.0,
                                  neighbours=False))
    out.append(_check("a neighbour sign flip cannot be LIVE",
                      flip["clause"] == "U1", f"{flip['clause']}"))
    stressed = family_letter(_receipt(3000.0, 500.0, 0.01, 120.0, 300.0,
                                      stress=False))
    out.append(_check("a stress MDD breach cannot be LIVE",
                      stressed["clause"] == "U1", f"{stressed['clause']}"))
    seat = family_letter(_receipt(3000.0, 500.0, 0.01, 120.0, 300.0,
                                  occupancy=False))
    out.append(_check("an unlawful occupancy ledger cannot be LIVE",
                      seat["clause"] == "U1", f"{seat['clause']}"))
    out.append(_check(
        "NOT-LICENSED is not in this unit's clause set and cannot fire",
        LETTER_NOT_LICENSED not in set(CLAUSE_LETTER.values())
        and live["not_licensed_possible"] is False,
        f"letters {sorted(set(CLAUSE_LETTER.values()))}"))
    return out


def _selftest_partition() -> list[tuple[str, bool, str]]:
    """THE PARTITION PROOF, over every constructible receipt, not asserted."""

    seen: dict[str, int] = {}
    total = 0
    excluded = 0
    live_receipts = 0
    bad: list[str] = []
    for bits in range(1 << 11):
        flags = [bool(bits >> i & 1) for i in range(11)]
        (rung, mdd_ok, cap, occ, stress, paired, neigh, upper_np, mdd_not,
         defined, positive) = flags
        # THE STRUCTURAL FACTS a receipt cannot violate, stated once.  They are
        # arithmetic, not policy: mdd_ok and mdd_not name one fact; paired_ok
        # is defined as both deltas positive AND both p <= 0.05, so it implies
        # both other flags; and upper = mean + c95 * SE with c95 >= 0 and
        # SE >= 0, so a positive point estimate cannot have a non-positive
        # simultaneous upper bound.
        impossible = (mdd_ok == mdd_not
                      or (positive and not defined)
                      or (paired and not positive)
                      or (paired and not defined)
                      or (positive and upper_np))
        if impossible:
            excluded += 1
            continue
        total += 1
        letter, clause, matching = classify(
            rung, mdd_ok, cap, occ, stress, paired, neigh, upper_np, mdd_not,
            defined, positive)
        seen[clause] = seen.get(clause, 0) + 1
        if not matching:
            bad.append(f"no clause matched {flags}")
        if clause not in matching:
            bad.append(f"the fired clause {clause} is not in {matching}")
        if CLAUSE_LETTER[clause] != letter:
            bad.append(f"clause {clause} returned letter {letter}")
        live = rung and mdd_ok and cap and occ and stress and paired and neigh
        if live:
            live_receipts += 1
            if upper_np or mdd_not:
                bad.append(f"LIVE and a kill matched together on {flags}")
        if not live and not upper_np and not mdd_not and clause not in ("U1", "U0"):
            bad.append(f"a non-live non-kill receipt fired {clause}")
    out = [_check(
        "THE PARTITION: exactly one clause fires on every constructible "
        "receipt and the fired clause is always one that matched",
        not bad and total > 0,
        f"{total} constructible receipts ({excluded} structurally impossible "
        f"and excluded), {len(bad)} defects"
        + (f": {bad[0]}" if bad else ""))]
    out.append(_check(
        "every registered clause is REACHABLE: none is decoration",
        set(seen) == set(CLAUSE_ORDER),
        ", ".join(f"{k} {v}" for k, v in sorted(seen.items()))))
    out.append(_check(
        "LIVE and a KILL are mutually exclusive BY CONSTRUCTION, not by "
        "precedence",
        live_receipts > 0
        and not any("LIVE and a kill" in line for line in bad),
        f"{live_receipts} LIVE receipts, none of which matched K1 or K2"))
    out.append(_check(
        "the residual U0 covers every receipt U1 does not, so no receipt "
        "falls through",
        not any("no clause matched" in line for line in bad)
        and seen.get("U0", 0) > 0 and seen.get("U1", 0) > 0,
        f"U1 {seen.get('U1', 0)}, U0 {seen.get('U0', 0)}"))
    return out


def _selftest_real(mutant: str) -> list[tuple[str, bool, str]]:
    """THE GATE ON REAL DATA: S1 must be sweep 28, event for event."""

    bundle = pipeline()
    parent = json.loads(PARENT_RECEIPT.read_text())
    picks = qualified_set(bundle, mutant)
    entries = bundle["entries"]
    cands = bundle["cands"]
    chosen = [entries[p] for p in picks]
    fingerprint = selection_fingerprint(picks, entries, cands)
    seated = seat_replay(chosen, CLOSE, S1_CHRONOLOGICAL)
    cash = S22.replay_cash(seated["trades"], bundle["explore_days"])
    gate = assert_reproduction(fingerprint, seated, cash, parent)
    counts_ok = (int(fingerprint["n"]) == EXPECT_SELECTED
                 and all(int(fingerprint["per_asset"][a]) == EXPECT_PER_ASSET[a]
                         for a in ASSETS)
                 and not any("breakdown" in f or "events, not" in f
                             or "totals" in f for f in gate["failures"]))
    seat_ok = (int(seated["seated"]) == EXPECT_SEATED
               and int(seated["rejected_occupancy"]) == EXPECT_REJECTED_OCCUPANCY
               and int(seated["rejected_cap"]) == EXPECT_REJECTED_CAP
               and all(cash[a]["usd_per_day"] is not None
                       and abs(float(cash[a]["usd_per_day"])
                               - EXPECT_USD_DAY[a]) < 1e-9 for a in ASSETS))
    out = [_check(
        "THE REPRODUCTION GATE: the qualified entry set is sweep 28's R_GEN "
        "top-four selection, event for event",
        counts_ok,
        f"selected {fingerprint['n']} (want {EXPECT_SELECTED}), per asset "
        f"{fingerprint['per_asset']}, zone-kind/year/phase totals match "
        f"{not any('totals' in f for f in gate['failures'])}")]
    out.append(_check(
        "S1 REPRODUCES SWEEP 28's SEATED LINE on real data",
        seat_ok,
        f"seated {seated['seated']} (want {EXPECT_SEATED}), occupancy "
        f"{seated['rejected_occupancy']} (want {EXPECT_REJECTED_OCCUPANCY}), "
        f"NKD {_show(cash['NKD']['usd_per_day'])} (want "
        f"{EXPECT_USD_DAY['NKD']:.4f}), SI {_show(cash['SI']['usd_per_day'])} "
        f"(want {EXPECT_USD_DAY['SI']:.4f})"))
    out.append(_check(
        "the F24 LICENCE is in the parent receipt and is cited, not re-derived",
        bool(parent["f24_licence"]["licensed"])
        and parent["f24_licence"]["verdict"] == LICENCE_QUOTE,
        parent["f24_licence"]["verdict"][:60] + "..."))
    finite = int(np.isfinite(bundle["impulse"][
        [e.position for e in chosen]]).sum()) if chosen else 0
    out.append(_check(
        "the magnitude channel is the FROZEN I_break score and is finite on "
        "the selected events",
        finite > 0 and finite <= len(chosen),
        f"{finite} of {len(chosen)} selected have a finite frozen magnitude"))
    return out


EXPECTED_RED = {
    MUTANT_FUTURE: (
        "THE MIRROR: the same decline with NOTHING later, priced honestly as "
        "the cost of the rule",
        "THE DECLINE RULE IS BLIND TO THE FUTURE: two worlds identical up to "
        "the decision stamp and different after it get the SAME decision"),
    MUTANT_SELECTION: (
        "THE REPRODUCTION GATE: the qualified entry set is sweep 28's R_GEN "
        "top-four selection, event for event",
        "S1 REPRODUCES SWEEP 28's SEATED LINE on real data"),
}


def selftest(mutant: str | None = None, real: bool = True) -> int:
    mutant = _mutant() if mutant is None else mutant
    results: list[tuple[str, bool, str]] = []
    results += _selftest_s1_is_the_standing_law()
    results += _selftest_collision(mutant)
    results += _selftest_decline(mutant)
    results += _selftest_thresholds()
    results += _selftest_pairing()
    results += _selftest_letters()
    results += _selftest_partition()
    if real:
        results += _selftest_real(mutant)
    # The inherited fixtures whose laws this unit is standing on.
    results += S22._selftest_replay()
    results += S22._selftest_stress()
    results += S23._selftest_formation()
    results += S27._selftest_top_k()
    print(f"sweep 29 selftest  mutant={mutant or 'none'}")
    bad = 0
    for name, ok, detail in results:
        mark = "ok  " if ok else "FAIL"
        bad += int(not ok)
        print(f"  [{mark}] {name}" + (f"  ({detail})" if detail else ""))
    print(f"  {len(results) - bad}/{len(results)} checks passed")
    if mutant in MUTANTS:
        red = [name for name, ok, _d in results if not ok]
        wanted = EXPECTED_RED[mutant]
        survived = [name for name in wanted if name not in set(red)]
        extra = [name for name in red if name not in set(wanted)]
        print(f"  MUTANT {mutant}: {len(red)} check(s) red, "
              f"{len(wanted)} registered as required")
        for name in red:
            print(f"    red: {name}")
        if survived:
            print("  THE GUARD IS NOT LOAD BEARING: a registered check survived")
            for name in survived:
                print(f"    survived: {name}")
            return 1
        if extra:
            print("  THE MUTANT IS NOT SURGICAL: it reds a check outside its "
                  "registered roster")
            for name in extra:
                print(f"    unregistered red: {name}")
            return 1
        print("  the guard is load bearing and surgical: every registered "
              "check went red and nothing else did")
        return 0
    return 1 if bad else 0


# --------------------------------------------------------------------------
# The log and the entry point.
# --------------------------------------------------------------------------

def log_rows(report: Mapping[str, object]) -> list[dict[str, object]]:
    params = json.dumps({
        "lane": LANE, "labels": list(LABELS),
        "seatings": list(SEATINGS),
        "tested_object": "the PAIRED SEATING delta: S2_MAGNITUDE seated cash "
                         "minus S1_CHRONOLOGICAL seated cash over one FIXED "
                         "qualified entry set, by shared calendar date",
        "entry_set": "sweep 28 R_GEN top-4, reproduced and gated",
        "decline_quantile": DECLINE_Q, "gap_quantile": GAP_Q,
        "decline_neighbours": list(NEIGHBOUR_Q),
        "magnitude_channel": "I_break, frozen out-of-fold, not recomputed",
        "features": list(FEATURES_ALL), "n_features": N_FEATURES,
        "ridge_lambda": RIDGE_LAMBDA, "top_k": TOP_K,
        "min_prior_days": MIN_PRIOR_DAYS, "min_train_rows": MIN_TRAIN_ROWS,
        "portfolio_cap": PORTFOLIO_CAP, "impulse_horizon_s": IMPULSE_HORIZON_S,
        "sign_draws": SIGN_DRAWS, "mdd_ceiling": MDD_CEILING,
        "clauses": list(CLAUSE_ORDER),
        "licence": "sweep28-039 / .audit/mill-sweep28.json f24_licence",
    }, sort_keys=True)
    shared = {
        "registered_utc": report["registered_utc"], "family": FAMILY,
        "params": params, "spec_sha": report["spec_sha"],
        "code_sha": report["code_sha"], "split_sha": report["split_sha"],
        "outcome_law_sha": report["outcome_law_sha"], "null_seed": SEED,
        "parent_trial": PARENT_TRIAL, "selection_rule": SELECTION_RULE,
        "verdict": "",
    }
    rows: list[dict[str, object]] = []
    counter = 0

    def blank(line: dict[str, object]) -> dict[str, object]:
        for tag in ("hg", "nkd", "si"):
            line[f"{tag}_usd_day"] = None
            line[f"mdd_{tag}"] = None
            line[f"walls_{tag}"] = None
            line[f"err_rate_{tag}"] = None
        line["replay_skips"] = None
        line["null_margin"] = None
        line["coverage"] = None
        line["delay_med_s"] = None
        return line

    days_scored = len(report["scoring_days"]["NKD"])
    head = report["headline"]

    # 1. the licence, cited
    counter += 1
    lic = report["licence"]
    line = blank(dict(shared))
    line["id"] = f"{LOG_PREFIX}-{counter:03d}"
    line["rule"] = "licence/cited"
    line["days"] = days_scored
    line["note"] = (
        f"THE LICENCE IS THE PARENT'S AND IS CITED, NOT RE-DERIVED: "
        f"{lic['source']}; verdict -- {lic['verdict']} --; R_GEN matched deltas "
        + ", ".join(f"{a} {_show(v)}"
                    for a, v in sorted(lic["matched_deltas"].items()))
        + "; occupancy R_GEN "
        f"{lic['occupancy']['R_GEN']['rejected_occupancy']} of "
        f"{lic['occupancy']['R_GEN']['selected']} selected (share "
        f"{_show(lic['occupancy']['R_GEN']['occupancy_share'])}); therefore "
        f"NOT-LICENSED CANNOT FIRE in this unit and is absent from its clause "
        f"set {list(CLAUSE_ORDER)}")
    rows.append(line)

    # 2. the reproduction gate
    counter += 1
    gate = report["reproduction_gate"]
    obs = gate["observed"]
    exp = gate["expected"]
    line = blank(dict(shared))
    line["id"] = f"{LOG_PREFIX}-{counter:03d}"
    line["rule"] = "gate/entry-set-frozen"
    line["days"] = days_scored
    line["nkd_usd_day"] = obs["usd_per_day"]["NKD"]
    line["si_usd_day"] = obs["usd_per_day"]["SI"]
    line["hg_usd_day"] = obs["usd_per_day"]["HG"]
    line["replay_skips"] = obs["rejected_occupancy"] + obs["rejected_cap"]
    line["note"] = (
        f"THE ENTRY SET IS FIXED AND GATED BEFORE ANY CASH OF THIS UNIT: "
        f"{report['formation']['counters']['candidates']} formed candidates "
        f"(parent {EXPECT_CANDIDATES}), {obs['selected']} selected (parent "
        f"{exp['selected']}), per asset HG {obs['per_asset']['HG']}/NKD "
        f"{obs['per_asset']['NKD']}/SI {obs['per_asset']['SI']} (parent HG "
        f"{exp['per_asset']['HG']}/NKD {exp['per_asset']['NKD']}/SI "
        f"{exp['per_asset']['SI']}), the whole zone-kind, year and phase "
        f"breakdown equal to 1e-6 USD; S1 seated {obs['seated']} (parent "
        f"{exp['seated']}), occupancy {obs['rejected_occupancy']} (parent "
        f"{exp['rejected_occupancy']}), cap {obs['rejected_cap']} (parent "
        f"{exp['rejected_cap']}), NKD {_show(obs['usd_per_day']['NKD'])} and "
        f"SI {_show(obs['usd_per_day']['SI'])} usd/day; GATE "
        f"{'PASSED' if gate['ok'] else 'FAILED'}; the unit refuses on any "
        f"mismatch, so no cash read here can change which events qualify")
    rows.append(line)

    # 3. the registered decline law
    counter += 1
    law = report["decline_law"]
    line = blank(dict(shared))
    line["id"] = f"{LOG_PREFIX}-{counter:03d}"
    line["rule"] = "law/decline-registered"
    line["days"] = days_scored
    line["note"] = (
        f"THE SEATING LAW, REGISTERED IN FULL BEFORE PRICING AND NOT SEARCHED: "
        f"(a) PRIORITY - at an equal stamp the higher FROZEN out-of-fold "
        f"magnitude (I_break, recomputed here {report['magnitude_law']['recomputed_here']}) "
        f"takes the seat, a non-finite score sorts last; (b) DECLINE - an "
        f"arrival is declined while flat if and only if its magnitude is below "
        f"the train quantile {law['quantile']} of {law['pool']}, AND "
        f"{law['clock']} at gap quantile {law['gap_quantile']}, AND "
        f"{law['cap']}; {law['fails_closed']}; reads future arrivals "
        f"{law['reads_future']}; {law['counters']['defined']} of "
        f"{law['counters']['cells']} asset-phase-day cells have a defined "
        f"threshold; neighbours {list(NEIGHBOUR_Q)} are a sign check, not a "
        f"search")
    rows.append(line)

    # 4. the two seatings, per label per asset
    for seating in SEATINGS:
        for label in LABELS:
            for asset in ASSETS:
                counter += 1
                block = report["seating"][seating][label]
                cash = block["cash"][asset]
                line = blank(dict(shared))
                line["id"] = f"{LOG_PREFIX}-{counter:03d}"
                line["rule"] = f"{seating}/{label}/{asset}"
                line["days"] = cash["days"]
                tag = asset.lower()
                line[f"{tag}_usd_day"] = cash["usd_per_day"]
                line[f"mdd_{tag}"] = block["mdd"].get(f"{asset}|day")
                line["replay_skips"] = (block["replay"]["rejected_occupancy"]
                                        + block["replay"]["rejected_cap"]
                                        + block["replay"]["declined"])
                line["note"] = (
                    f"{seating} over the FIXED {block['n_selected']}-event "
                    f"qualified set, label {label}, {asset}: seated "
                    f"{cash['trades']} of {block['replay']['seated']} total "
                    f"seats, usd/day "
                    f"{_show(cash['usd_per_day'])}, mean-2SE "
                    f"{_show(cash['mean_minus_2se_usd'])}, clears rung "
                    f"{cash['clears_rung']}, zero-entry day share "
                    f"{_show(cash['zero_entry_fraction'])}, seats/day mean "
                    f"{_show(cash['seats_mean'])} max {cash['seats_max']}; "
                    f"replay lost {block['replay']['rejected_occupancy']} to "
                    f"occupancy, {block['replay']['rejected_cap']} to the cap, "
                    f"{block['replay']['declined']} declined; asset-day MDD "
                    f"{_show(block['mdd'].get(f'{asset}|day'))}, max binding "
                    f"{_show(block['mdd']['max_binding_usd'])} clears "
                    f"{block['mdd']['clears']}; occupancy lawful "
                    f"{block['occupancy_lawful']}, cap lawful "
                    f"{block['cash']['_portfolio']['cap_lawful']}")
                rows.append(line)

    # 5. the tested object, per line, both labels
    for name, block in (("paired/close", report["paired"]),
                        ("paired/1800", report["paired_1800"])):
        for asset in ASSETS:
            counter += 1
            cell = block["by_line"][f"{LANE}|{asset}"]
            line = blank(dict(shared))
            line["id"] = f"{LOG_PREFIX}-{counter:03d}"
            line["rule"] = f"{name}/{asset}"
            line["days"] = cell["dates"]
            line[f"{asset.lower()}_usd_day"] = cell["delta_usd_per_date"]
            line["null_margin"] = cell["p_max_adjusted"]
            line["note"] = (
                f"{'THE TESTED OBJECT' if name.endswith('close') else 'INFORMATION ONLY'}: "
                f"S2 minus S1 seated cash paired by shared calendar date, "
                f"{asset}, label {'close' if name.endswith('close') else '1800'}"
                f": delta {_show(cell['delta_usd_per_date'])} usd/date over "
                f"{cell['dates']} dates, SE {_show(cell['se_usd'])}, t "
                f"{_show(cell['t'])}, shared-date-sign maxT over "
                f"{block['family']} at {block['draws']} draws, c95 "
                f"{_show(block['c95'])}, adjusted p "
                f"{_show(cell['p_max_adjusted'])}, simultaneous 95% bounds "
                f"[{_show(cell['lower95_simultaneous_usd'])}, "
                f"{_show(cell['upper95_simultaneous_usd'])}], eligible "
                f"{cell['eligible']}"
                + ("" if name.endswith("close") else "; carries no letter")
                + "; event-level p FORBIDDEN and not computed")
            rows.append(line)

    # 6. the decline and priority ledgers
    counter += 1
    ledger = report["decline_ledger"]
    coll = report["collisions"]
    line = blank(dict(shared))
    line["id"] = f"{LOG_PREFIX}-{counter:03d}"
    line["rule"] = "ledger/decline-and-priority"
    line["days"] = days_scored
    line["replay_skips"] = ledger["declined"]
    line["note"] = (
        f"WHAT THE DISCIPLINE ACTUALLY DID: {coll['same_asset_stamp_groups']} "
        f"equal-stamp same-asset collision groups covering "
        f"{coll['same_asset_events_in_groups']} events, magnitude changes who "
        f"is first in {coll['same_asset_groups_reordered']}; "
        f"{coll['cross_asset_stamp_groups']} cross-asset equal stamps (no seat "
        f"cost while the cap does not bind); {ledger['declined']} declines of "
        f"which {ledger['worked']} WORKED (the asset-day later seated) and "
        f"{ledger['mirror']} were MIRRORS (nothing later seated), the mirror "
        f"cost being {_show(ledger['mirror_forgone_usd'])} USD of forgone "
        f"selected cash, already inside every S2 cash line and not corrected "
        f"out; seat swaps S2-only {ledger['seat_swaps']['s2_only']}, S1-only "
        f"{ledger['seat_swaps']['s1_only']}, both {ledger['seat_swaps']['both']}"
        + "; per asset " + ", ".join(
            f"{a} {ledger['per_asset'][a]['declined']} declined "
            f"({ledger['per_asset'][a]['mirror']} mirror, "
            f"{_show(ledger['per_asset'][a]['mirror_forgone_usd'])} USD)"
            for a in ASSETS))
    rows.append(line)

    # 7. the two registered neighbours
    for q in NEIGHBOUR_Q:
        counter += 1
        cell = report["neighbours"][f"{q:.1f}"]
        line = blank(dict(shared))
        line["id"] = f"{LOG_PREFIX}-{counter:03d}"
        line["rule"] = f"neighbour/decline-q{q:.1f}"
        line["days"] = days_scored
        for asset in ASSETS:
            line[f"{asset.lower()}_usd_day"] = cell["delta"].get(asset)
        line["replay_skips"] = cell["declined"]
        line["note"] = (
            f"DECLINE-THRESHOLD NEIGHBOUR at train quantile {q} (registered "
            f"before outcomes as a sign-stability check, NOT a search): "
            f"{cell['declined']} declines, {cell['seated']} seated; paired "
            f"delta " + ", ".join(f"{a} {_show(cell['delta'].get(a))}"
                                  for a in ASSETS)
            + "; adjusted p " + ", ".join(
                f"{a} {_show(cell['p_max_adjusted'].get(a))}" for a in DECIDING)
            + f"; deciding sign flips {cell['sign_flips'] or 'none'}")
        rows.append(line)

    # 8. the MDD ledgers, per seating
    for seating in SEATINGS:
        counter += 1
        mdd = report["seating"][seating][CLOSE]["mdd"]
        line = blank(dict(shared))
        line["id"] = f"{LOG_PREFIX}-{counter:03d}"
        line["rule"] = f"mdd/{seating}"
        line["days"] = days_scored
        for asset in ASSETS:
            line[f"mdd_{asset.lower()}"] = mdd.get(f"{asset}|day")
        line["note"] = (
            f"THE FULL MDD LEDGER FAMILY, {seating}, primary label: "
            + ", ".join(f"{key} {_show(mdd[key])}" for key in sorted(mdd)
                        if key not in ("binding_ledgers", "max_binding_usd",
                                       "clears"))
            + f"; binding {mdd['binding_ledgers']}; MAX BINDING "
              f"{_show(mdd['max_binding_usd'])} against the {MDD_CEILING} USD "
              f"ceiling, clears {mdd['clears']}; the event-time portfolio "
              f"equity ledger PORTFOLIO|event marks every open position at "
              f"every bar and is included")
        rows.append(line)

    # 9. the stresses, per seating
    for seating in SEATINGS:
        for kind in ("adversarial", "spread"):
            counter += 1
            cell = report["seating"][seating][CLOSE]["stress"][kind]
            line = blank(dict(shared))
            line["id"] = f"{LOG_PREFIX}-{counter:03d}"
            line["rule"] = f"stress/{seating}/{kind}"
            line["days"] = days_scored
            for asset in ASSETS:
                line[f"{asset.lower()}_usd_day"] = cell["cash"][asset]["usd_per_day"]
                line[f"mdd_{asset.lower()}"] = cell["mdd"].get(f"{asset}|day")
            line["note"] = (
                f"STANDING STRESS {kind} on {seating}, primary label: seated "
                f"{cell['seated']}, " + ", ".join(
                    f"{a} {_show(cell['cash'][a]['usd_per_day'])} usd/day "
                    f"(mean-2SE {_show(cell['cash'][a]['mean_minus_2se_usd'])})"
                    for a in ASSETS)
                + f"; max binding MDD {_show(cell['mdd']['max_binding_usd'])} "
                  f"clears {cell['mdd']['clears']}"
                + ("; the worst 2 percent per asset realize their own printed "
                   "MAE" if kind == "adversarial" else
                   "; every entry pays its own spread a second time"))
            rows.append(line)

    # 10. the family letter
    counter += 1
    cell = report["letter"]
    live = report["seating"][S2_MAGNITUDE][CLOSE]
    line = blank(dict(shared))
    line["id"] = f"{LOG_PREFIX}-{counter:03d}"
    line["rule"] = f"{FAMILY}/family"
    line["days"] = days_scored
    line["nkd_usd_day"] = live["cash"]["NKD"]["usd_per_day"]
    line["si_usd_day"] = live["cash"]["SI"]["usd_per_day"]
    line["hg_usd_day"] = live["cash"]["HG"]["usd_per_day"]
    line["null_margin"] = head["paired_p_adjusted"].get("SI")
    line["replay_skips"] = live["replay"]["declined"]
    line["note"] = (
        f"FAMILY LETTER {cell['letter']} (clause {cell['clause']}): S2 "
        f"deciding usd/day over rung " + ", ".join(
            f"{a} {_show(head['s2_over_rung'].get(a))}x" for a in DECIDING)
        + "; PAIRED S2-S1 " + ", ".join(
            f"{a} {_show(head['paired_delta'].get(a))} usd/date at adjusted p "
            f"{_show(head['paired_p_adjusted'].get(a))}, upper95 "
            f"{_show(head['paired_upper95'].get(a))}" for a in DECIDING)
        + f"; S2 max binding MDD {_show(head['s2_max_binding_mdd_usd'])} "
          f"against {MDD_CEILING} clears {head['s2_mdd_clears']}"
        + f"; rung {cell['rung_ok']}, MDD {cell['mdd_ok']}, cap "
          f"{cell['cap_ok']}, occupancy {cell['occupancy_ok']}, stress "
          f"{cell['stress_ok']}, paired {cell['paired_ok']}, neighbours "
          f"{cell['neighbours_ok']}, paired upper non-positive "
          f"{cell['paired_upper_nonpositive']}, MDD not below ceiling "
          f"{cell['mdd_not_below_ceiling']}, bounds defined "
          f"{cell['bounds_defined']}; CLAUSE {cell['clause']} = "
          f"{cell['clause_text']}; clauses matching {cell['clauses_matching']}"
        + ("; " + "; ".join(cell["reasons"]) if cell["reasons"] else "")
        + f"; NOT-LICENSED could not fire, the licence is sweep28-039; "
          f"EXPLORE-only, kill-only, no promotion")
    rows.append(line)
    return rows


def write_report(report: Mapping[str, object]) -> None:
    OUT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True,
                                   default=S8._json_default) + "\n")


def report_stamp() -> str:
    import datetime as dt
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--selftest-all", action="store_true",
                        help="the clean selftest and BOTH mutant rosters in "
                             "one process, over one shared pipeline")
    parser.add_argument("--no-real", action="store_true",
                        help="skip the real-data reproduction gate in the "
                             "selftest (fixtures only)")
    parser.add_argument("--log", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest_all:
        codes = []
        for mutant in ("",) + MUTANTS:
            print("=" * 78)
            codes.append(selftest(mutant, real=not args.no_real))
        print("=" * 78)
        print(f"selftest-all: clean {codes[0]}, {MUTANT_FUTURE} {codes[1]}, "
              f"{MUTANT_SELECTION} {codes[2]}  (0 = as registered)")
        return max(codes)
    if args.selftest:
        return selftest(real=not args.no_real)
    report = run()
    # The receipt is written BEFORE anything is printed: a formatting fault
    # must never cost a measured run.
    write_report(report)
    print_summary(report)
    print_licence(report)
    print_gate(report)
    print_decline_law(report)
    print_seatings(report)
    print_mdd(report)
    print_paired(report)
    print_decision(report)
    print(f"\nWHY THE DECLINE RULE IS SHAPED THIS WAY\n  {report['decline_note']}")
    print(f"\nWHAT SEAT ORDER CAN AND CANNOT BUY\n  {report['order_note']}")
    print(f"\nREGISTERED RESIDUAL\n  {report['residual_note']}")
    print(f"\nSELECTOR SIGN NOTE (sweep 23's, carried verbatim)\n"
          f"  {report['selector_sign_note']}")
    print(f"\nCONTAMINATION NOTE (sweep 25's, carried verbatim)\n"
          f"  {report['contamination_note']}")
    print(f"\nreport: {OUT_PATH}")
    if args.log:
        rows = log_rows(report)
        written = S1.append_log(rows)
        print(f"log: appended {written} rows to {LOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
