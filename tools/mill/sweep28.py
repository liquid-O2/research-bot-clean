#!/usr/bin/env python3
"""Sweep 28: F23-ZONE-GENEALOGY, the cross-day zone genealogy increment.

Unit 2 of Sol's power plan (``.audit/briefs/mill-powerplan-sol-out.md`` section
C rank 2, section D row 2), run because unit 1 did not live: sweep 27 landed
``LEVELMEMORY-UNRESOLVED`` clause U1 and its receipt is frozen per the charter.

WHAT IS NEW, AND IT IS ONLY ONE THING.  Sweep 27 gave the SEPARATE fixed-zone
components one valid out-of-fold selector test.  Every one of those components
is a COUNT: how many touches, what share held, how long since.  A count cannot
carry ORDER, and ``levels_zone`` serves exactly ONE prior EXPLORE session.  A
band that held four times and then broke twice is, in sweep 27's representation,
the same object as a band that broke twice and then held four times.  The first
is a level losing its defenders; the second is a level being reclaimed.

``tools/mill/zone_history.py`` builds the ordered store - TOUCH, HELD, BROKE and
ROLE-FLIP at an ATR-scaled price band, across EVERY licensed earlier EXPLORE
session - and this unit asks whether that order is worth anything.

THE TESTED OBJECT IS THE INCREMENT, not the level.  Two rankers are fit under
sweep 27's EXACT law, on the SAME candidates, the SAME lane, the SAME folds and
the SAME target:

    R_BASE   sweep 27's nineteen-component feature row, imported by value from
             ``sweep27.FEATURE_NAMES`` and built by ``sweep27.build_features``,
             so "exactly sweep 27's row" is a fact about the call graph.
    R_GEN    R_BASE plus the seven genealogy fields.

and what carries the letters is ``R_GEN`` selected cash MINUS ``R_BASE``
selected cash, paired by shared calendar date.  That is the only way to attribute
a result to the genealogy: both rankers see the same universe, so a difference
between them is the ordered history and nothing else.  The F22-style matched
control for ``R_GEN`` is reported beside it under the same maxT discipline.

WHAT IS HELD FIXED, so the genealogy is the only thing under test:

  * FORMATION.  Sweep 23's breach formation through ``S23.formation_pass``,
    called READ-ONLY.  It must return the parent's 3,790 candidates or this unit
    refuses.
  * ENTRY.  Lane A only - the USER's next-bar break-close timing, priced through
    ``S22.price_bar_entry``, never at the breach close itself.
  * OUTCOME.  The frozen wall-or-close law is PRIMARY; the 1800 s fixed hold is
    reported beside every line.
  * THE RANKER LAW.  ``S27.rank_folds``, ``S27.select_top`` and
    ``S27.fit_ridge``, called directly: per-asset ridge, lambda 1 fixed,
    within-asset-day cert percentile target, equal asset-day weights, warmup and
    thin-fold rules, top-four positive-score selection, top-three and top-five as
    non-letter neighbours.  There is no model search and no penalty search.
  * REPLAY.  The exact chronological seat replay, the full MDD ledger family,
    and both standing stresses.

THE STORE IS GATED BEFORE ANY CASH.  ``zone_history`` proves exact identity (the
returned band contains the query price and is the same key at every stamp),
strict time (every served event strictly earlier than the decision) and the
role-flip mutant on a planted three-session fixture.  This unit re-runs those
gates over its own 3,790 real queries and refuses on any violation.

Nothing here is executable.  EXPLORE only, kill-only tier, no packs, no HOLD, no
teacher labels, no 2021, no 2025H2, no commits, no freeze.  Sweeps 22, 23, 25,
27, ``levels_zone`` and ``zone_history`` are imported READ-ONLY and none of them
is modified.
"""

from __future__ import annotations

import argparse
import itertools
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
import sweep20 as S20  # noqa: E402,F401
import sweep22 as S22  # noqa: E402
import sweep23 as S23  # noqa: E402
import sweep25 as S25  # noqa: E402
import sweep27 as S27  # noqa: E402

# --------------------------------------------------------------------------
# The law, registered before anything is read.
# --------------------------------------------------------------------------

SPEC = """QRE2MILLSWEEP28
tier=exploratory; EXPLORE-only, kill-only.  Family F23-ZONE-GENEALOGY, the
  second unit of Sol's power plan (.audit/briefs/mill-powerplan-sol-out.md
  section C rank 2, section D row 2), licensed because unit 1 did not live.
  Seed 20260827.  Parent trial sweep27-021.  NO COMMITS, NO FREEZE, no packs, no
  HOLD, no teacher labels, no 2021, no 2025H2.  ONE entry lane, TWO rankers, ONE
  tested increment, one maxT family of TWO deciding lines; HG report-only.
INHERITANCE.  Sweeps 27, 25, 23 and 22 and levels_zone are imported and called
  READ-ONLY; their SPECs govern every clause not restated here: the GATE, the
  zone catalogue, the fold-trained zone width, breach formation with the
  persistence gate and the per (asset, day, phase, level, break direction)
  dedup, the frozen bar-entry law, the impulse ridge and its join, the frozen
  outcome law with the 1800 s label beside, the chronological seat replay, the
  MDD ledger family, the two stresses, and the matched control.  FORMATION MUST
  RETURN 3,790 CANDIDATES or this unit refuses.
0. THE STORE, GATED BEFORE ANY CASH.  tools/mill/zone_history.py builds a
  ZoneHistory keyed by (asset, ATR-scaled price band).  The band grid is
  floor(price / step) with step = 0.40 * atr_ref, where 0.40 is TWICE the levels
  cache's own default half-width multiplier so one genealogy band is one default
  cache band wide, and atr_ref is the MEDIAN prior-day ATR14 over the asset's
  FIRST 25 EXPLORE sessions - the ranker's own warmup, never scored and never
  out-of-fold - so the grid is fixed before the first scored session and reads no
  outcome.  For every EXPLORE session in CAUSAL ORDER the store appends the
  ordered events at each band: TOUCH, HELD, BROKE under the levels_zone anchored
  outcome law at the fixed band price (levels.outcome_bars at the band half
  width, the one definition levels_zone.outcome_pair itself calls; membership
  moves to the band, the verdict stays anchored on the TOUCHED price), and
  ROLE-FLIP where a resolved defence points OPPOSITE to the last resolved
  defence at that band.  A query (asset, zone_price, decision_stamp) is served
  ONLY by sessions whose calendar day is strictly earlier AND whose last bar
  closed strictly before the decision stamp - levels_zone's licensed
  prior-session law, generalized from one session to all of them.  HOLD stays
  sealed: the session list is sweep1._explore_days and nothing else.  THREE
  GATES are hard-asserted over this unit's own 3,790 real queries before any
  cash is read: EXACT IDENTITY (the returned band contains the query price, and
  the same price on the same day is the same key at every stamp), STRICT TIME
  (every served event strictly earlier in day AND in stamp), and the ROLE-FLIP
  MUTANT red on a planted three-session fixture.  THE ONE DISCLOSED DIFFERENCE
  from the accessor: levels_zone's band is CLOSED on both edges, so adjacent
  accessor bands OVERLAP and a bar on the shared price is counted by both; a
  genealogy KEY cannot do that or one price would have two histories, so the
  floor grid is a PARTITION and differs on exactly the bars sitting on a band's
  upper edge.  The selftest measures that set rather than asserting it away.
1. THE FORMATION AND THE LANE, sweep 27's, unchanged.  Sweep 23's breach
  formation through S23.formation_pass.  Lane A only: decide at the breach close
  and enter in the BREAK direction at the NEXT bar under the frozen entry law.
  NEVER a same-close fill.  The frozen wall-or-close outcome is PRIMARY; the
  1800 s label is reported beside it.
2. THE BARRIER READ, sweep 27's, unchanged, through S27.zone_read at the
  candidate's FIXED zone_price on the former defending side at DECISION STAMP
  lat[breach_bar - 1].  Every row must echo center_price == zone_price EXACTLY
  and a strictly prior source stamp, per row, or the run refuses.
3. THE TWO FEATURE ROWS.  R_BASE is sweep 27's nineteen columns, imported by
  value from S27.FEATURE_NAMES and built by S27.build_features, so it is that
  row and not a copy of it.  R_GEN is R_BASE plus SEVEN genealogy columns read
  at the SAME (asset, zone price, decision stamp) as the barrier read:
    gen_generations            distinct earlier sessions with any event
    gen_log_touches            log1p(earlier-session touch count)
    gen_held_rate              held / touches over earlier sessions
    gen_broke_rate             broke / touches over earlier sessions
    gen_role_flips             ordered role flips
    gen_events_since_flip      events appended after the last ROLE-FLIP
    gen_sessions_since_event   EXPLORE sessions since the last event
  A rate is NaN where its touch count is not positive, and "events since last
  flip" is NaN where no flip has occurred: undefined is not zero.  MISSINGNESS
  LAW, the standing one: a NaN is imputed at the TRAINING FOLD's own mean, so it
  standardizes to zero and carries no information.  EXCLUDED BY REGISTRATION:
  the raw event list, every absolute stamp inside it, the band index and the
  band price (identities, and a price level is not a component), and every
  current-day quantity.
4. THE RANKERS.  BOTH through S27.rank_folds at S27.RIDGE_LAMBDA, called
  directly so the law is sweep 27's by call graph: one ridge per ASSET, fit on
  STRICTLY PRIOR EXPLORE days, >= 25 prior EXPLORE days and >= 40 training rows,
  TARGET the WITHIN-ASSET-DAY PERCENTILE of the frozen cert, EACH ASSET-DAY
  WEIGHTED EQUALLY, columns standardized on the TRAINING FOLD, LAMBDA = 1 FIXED.
  NO model search, NO penalty search, NO feature selection.
5. THE SELECTION, sweep 27's.  On each out-of-fold asset-day keep at most the
  TOP FOUR POSITIVE-SCORE events, for EACH ranker.  Top-three and top-five are
  reported as NON-LETTER NEIGHBOURS for each ranker.
6. THE TESTED OBJECT IS THE INCREMENT.
  (a) THE INCREMENT.  Per asset and per shared calendar date, the sum of the
    frozen cert over R_GEN's selected events MINUS the same sum over R_BASE's,
    studentized, read under ONE shared-date-sign maxT family over NKD and SI
    with 10000 draws.  HG is carried report-only.  The seated-cash increment is
    reported beside it as information and carries no letter.
  (b) THE MATCHED CONTROL FOR R_GEN, the F22 form.  One paired G1 control per
    R_GEN-selected event, matched on ASSET, DATE, PHASE, BREACH-TIME BIN and
    MAGNITUDE BIN through S22.match_controls.  Selected minus matched control by
    shared calendar date, same maxT family discipline.  The COMPLETE
    level-plus-genealogy vector is PERMUTED INSIDE THE TRAINING FOLD and scored
    by that fold's own ranker, and the share earning a positive score and a
    top-four seat is reported.  BOTH (a) and (b) are reported.
  EVENT-LEVEL P-VALUES ARE FORBIDDEN and none is computed: several events share
  one impulse, one day and one seat ledger, so the independent unit is the
  calendar date.  C3 block-permutation nulls are reported with the standing
  caveat, unadjusted, as information.
7. PRICING, REPLAY, LEDGERS, sweep 27's.  Chronological seat replay with the
  frozen tie break, ONE open position per asset, at most 12 seated entries per
  PORTFOLIO date.  The full MDD ledger family including EVENT-TIME PORTFOLIO
  EQUITY; binding is the deciding assets' own trade and day ledgers plus every
  portfolio ledger, ceiling 1000 USD.  The 2 percent adversarial stress and the
  DOUBLED-SPREAD stress, both re-running the replay so occupancy follows.  C2:
  the formed-opportunity ceiling RAW and CAPPED at the 12 best events per
  portfolio date, hindsight bits named.
8. LETTERS, Sol's two kill clauses made exhaustive, with a registered precedence
  and a proven partition.  The charter licenses a kill ONLY under its two
  clauses, so everything else is UNRESOLVED.
  GENEALOGY-LIVE when R_GEN clears the FULL live bounds: BOTH deciding assets
    clear the rung at the point estimate AND at mean minus two asset-day-block
    standard errors, BOTH adjusted R_GEN control lines are at p <= 0.05, every
    binding MDD is below 1000, cap and occupancy are lawful, both stresses clear
    MDD, and neither the top-three nor the top-five neighbour flips a deciding
    sign.
  GENEALOGY-KILL clause K1 when THE GENEALOGY INCREMENT has a NON-POSITIVE 95
    percent simultaneous upper bound on EITHER deciding asset.
  GENEALOGY-KILL clause K2 when EITHER R_GEN matched-control delta is zero or
    negative.
  GENEALOGY-UNRESOLVED clause U1, Sol's named case: the increment is positive on
    both deciders and both R_GEN matched deltas are positive, but the live
    bounds fail or the power is inadequate.
  GENEALOGY-UNRESOLVED clause U0, THE REGISTERED RESIDUAL, disclosed rather than
    hidden.  A receipt in which a deciding increment bound or a deciding matched
    delta is UNDEFINED - no powered line, no shared dates, no pairs - satisfies
    none of the four: K1 needs a defined non-positive bound, K2 needs a defined
    non-positive delta, U1 needs all four defined and positive.  Section D
    licenses a kill ONLY under the two clauses above, so the residual CANNOT be
    a kill and is registered as UNRESOLVED BEFORE any outcome is read, the way
    sweep 27 registered its own U0.  The selftest proves the five-clause
    partition is total over all 512 outcome points and that the kill surface is
    exactly the charter's two clauses.
  PRECEDENCE LIVE > K1 > K2 > U1 > U0, no fallthrough.  One lane, one tested
  increment, one letter.
9. ON UNRESOLVED the receipt FREEZES and the F24 licensing check is evaluated
  and PRINTED: does any lane show positive matched deltas on BOTH deciders while
  losing material cash to occupancy?  Sweep 27 measured occupancy binding at 150
  of 468 selected events; this lane reports its occupancy loss the same way, for
  each ranker.  The check is a LICENCE READ, never a promotion and never a
  letter.
MUTANTS.  Each names the EXACT checks it must turn red; a mutant that reds some
  other check, or that leaves any named check green, fails the run.  The rosters
  are the MEASURED red sets, not the sets a reader would guess.
  QRE2_MILL_S28_MUTANT=selector_uses_test_day fits both rankers' folds - their
    standardization, their weights, their target percentiles and their
    coefficients - on days[:index+1] instead of days[:index], and fits the
    impulse ridge including the scoring day.  It must red the planted LEAK
    worlds, whose payoff gradient exists ONLY on the scoring day and which
    therefore must yield NO out-of-fold recovery when the fold is honest.
  QRE2_MILL_S28_MUTANT=genealogy_reads_current_day arms zone_history's own
    registered defect: the store serves the CURRENT day's session, whose events
    include bars that had not closed when the decision was made.  It must red
    the strict-time checks and the planted genealogy checks.
"""

RESIDUAL_NOTE = (
    "REGISTERED ENUMERATION DISCLOSURE, clause U0.  Sol's section D row 2 "
    "licenses a kill on exactly two grounds: a non-positive simultaneous upper "
    "bound on the genealogy INCREMENT on either decider, or a matched delta "
    "that is zero or negative.  Both grounds require a DEFINED number.  A "
    "receipt in which a deciding increment bound or a deciding matched delta "
    "is undefined - no powered line, no shared dates, no matched pairs - "
    "satisfies neither kill clause, and it cannot be called 'two positive "
    "deltas with inadequate power' either.  Sweep 25 met the same shape and "
    "had to register CEILING-UNREACHED by elimination; sweep 27 registered its "
    "own U0 in advance rather than repeat that.  This unit does the same: the "
    "residual cannot lawfully kill, so it is registered as UNRESOLVED clause "
    "U0 BEFORE any outcome is read.  The partition is proved total over all "
    "512 outcome points in the selftest, the kill surface is proved to be "
    "exactly the charter's two clauses, and the receipt reports which clause "
    "fired and which others matched.")

INCREMENT_NOTE = (
    "WHY THE INCREMENT AND NOT THE LEVEL.  Sweep 27 already measured what the "
    "fixed-zone component plane is worth: LEVELMEMORY-UNRESOLVED, both deciding "
    "rungs missed, both matched controls far from significance.  If this unit "
    "measured R_GEN's own cash against the rung it would be re-measuring that "
    "same plane with seven columns added, and a null result would be "
    "unattributable - it could be the genealogy failing or the level plane "
    "failing underneath it.  The INCREMENT removes the ambiguity by "
    "construction.  Both rankers see the SAME 3,790 candidates, the SAME lane, "
    "the SAME folds, the SAME target, the SAME penalty and the SAME selection "
    "rule; the ONLY difference between them is whether the ordered cross-day "
    "history is in the feature row.  Pairing them by shared calendar date also "
    "differences out every day-level nuisance the two rankers share - the day's "
    "volatility, its formed count, its seat contention - so the paired series "
    "is the genealogy's own contribution and nothing else.  This is also why "
    "the increment, not R_GEN's level, carries clause K1: Sol's charter asks "
    "whether the GENEALOGY earns its place, not whether the underlying plane "
    "does.")

ORDER_NOTE = (
    "WHAT ORDER BUYS, STATED BEFORE IT IS MEASURED.  levels_zone serves counts "
    "from ONE prior EXPLORE session: touches, held, broke, recency, signed "
    "flow.  Two facts are unreachable in that representation.  FIRST, DEPTH: a "
    "band defended across nine earlier sessions and a band defended once are "
    "the same object once the count is collapsed to the single most recent "
    "session, and this store's real queries reach a median depth well past one "
    "generation.  SECOND, SEQUENCE: held-then-broke and broke-then-held give "
    "identical held and broke counts and describe opposite regimes - a level "
    "losing its defenders against a level being reclaimed.  The ROLE-FLIP event "
    "is the minimal statistic that separates them, and 'events since the last "
    "flip' dates the current regime.  Both are ORDER facts, both are zero-cost "
    "to a count representation, and the flip mutant - which recomputes the same "
    "flips from the unordered totals min(held, broke) - is what proves this "
    "unit actually uses the order rather than merely storing it.")

ASSETS = S23.ASSETS
DECIDING = S23.DECIDING
REPORT_ONLY_ASSETS = S23.REPORT_ONLY_ASSETS
SEED = 20260827

FAMILY = "F23-ZONE-GENEALOGY"
PARENT_TRIAL = "sweep27-021"
SELECTION_RULE = ("none: parent-preregistered break formation and break-close "
                  "lane, sweep 27's exact ranker law run twice over the same "
                  "candidates - once on its own nineteen components and once "
                  "with the seven ordered-genealogy fields added - at a fixed "
                  "lambda=1, coverage set by the twelve-entry seat budget; the "
                  "tested object is the paired increment between the two, no "
                  "model search, no penalty search, no cash-tuned cutoff")

LOG_PREFIX = "sweep28"
OUT_PATH = ROOT / ".audit/mill-sweep28.json"
LOG_PATH = S1.LOG_PATH

EXPECT_CANDIDATES = S25.EXPECT_CANDIDATES          # 3,790

# Inherited by value, so an upstream drift fails loudly here.
CLOSE = S25.CLOSE
FIXED = S25.FIXED
LABELS = S25.LABELS
MIN_PRIOR_DAYS = S25.MIN_PRIOR_DAYS                # 25
MIN_TRAIN_ROWS = S25.MIN_TRAIN_CANDS               # 40
DAY_RUNG_USD = S25.DAY_RUNG_USD
MDD_CEILING = S25.MDD_CEILING                      # 1000
PORTFOLIO_CAP = S25.PORTFOLIO_CAP                  # 12
CONTROL_DRAWS = S25.CONTROL_DRAWS                  # 2000
SIGN_DRAWS = S25.SIGN_DRAWS                        # 10000
IMPULSE_HORIZON_S = S25.IMPULSE_HORIZON_S
MAX_EPISODE_BARS = S25.MAX_EPISODE_BARS
TIME_BINS = S25.TIME_BINS
HINDSIGHT_CEILING = S25.HINDSIGHT_CEILING

LANE = S27.LANE                                    # A_BREAK_CLOSE
LANE_NAME = S27.LANE_NAME
RIDGE_LAMBDA = S27.RIDGE_LAMBDA
TOP_K = S27.TOP_K
NEIGHBOUR_K = S27.NEIGHBOUR_K
ALL_K = S27.ALL_K

# --------------------------------------------------------------------------
# The two feature rosters.  R_BASE is sweep 27's, by value.
# --------------------------------------------------------------------------

BASE_FEATURES = tuple(S27.FEATURE_NAMES)
N_BASE = len(BASE_FEATURES)

GEN_FEATURES = ("gen_generations", "gen_log_touches", "gen_held_rate",
                "gen_broke_rate", "gen_role_flips", "gen_events_since_flip",
                "gen_sessions_since_event")
N_GEN = len(GEN_FEATURES)
GEN_FEATURES_FROM = {
    "gen_generations": "generations",
    "gen_log_touches": "touches (as log1p)",
    "gen_held_rate": "held_rate",
    "gen_broke_rate": "broke_rate",
    "gen_role_flips": "role_flips",
    "gen_events_since_flip": "events_since_last_flip",
    "gen_sessions_since_event": "sessions_since_last_event"}

GEN_FEATURES_ALL = BASE_FEATURES + GEN_FEATURES
N_ALL = len(GEN_FEATURES_ALL)

EXCLUDED_HISTORY_FIELDS = {
    "events": "the raw ordered event list: it is the EVIDENCE the derived "
              "fields summarize, and every entry carries absolute stamps",
    "sessions_eligible": "row count that reveals warmup (how many sessions "
                         "have elapsed)",
    "band": "identity",
    "band_lo": "identity, and a price level is not a component",
    "band_hi": "identity, and a price level is not a component",
    "band_center": "identity, and a price level is not a component",
    "step": "the asset's fixed grid constant, identical on every row of an "
            "asset, so it has no within-asset spread and is not a component",
    "held": "carried as held_rate against its own touch count; the raw count "
            "enters once, as gen_log_touches",
    "broke": "carried as broke_rate against its own touch count",
}

RANKERS = ("R_BASE", "R_GEN")

# --------------------------------------------------------------------------
# The letters.
# --------------------------------------------------------------------------

LETTER_LIVE = "GENEALOGY-LIVE"
LETTER_UNRESOLVED = "GENEALOGY-UNRESOLVED"
LETTER_KILL = "GENEALOGY-KILL"
CLAUSES = {
    "LIVE": ("R_GEN clears the full live bounds: both deciding assets clear "
             "the rung at the point estimate AND at mean minus two SE, both "
             "adjusted R_GEN control lines p <= 0.05, every binding MDD below "
             "1000, lawful cap and occupancy, both stresses, and no sign flip "
             "at the top-three or top-five neighbour"),
    "K1": ("the genealogy INCREMENT has a non-positive 95 percent simultaneous "
           "upper bound on either deciding asset"),
    "K2": ("either R_GEN matched-control delta is zero or negative"),
    "U1": ("the increment is positive on both deciders and both R_GEN matched "
           "deltas are positive, but the live bounds fail or the power is "
           "inadequate"),
    "U0": ("THE REGISTERED RESIDUAL: a deciding increment bound or a deciding "
           "matched delta is UNDEFINED, so neither kill clause can lawfully "
           "fire and the receipt cannot be called positive-but-underpowered "
           "either.  The charter licenses a kill only under K1 or K2, so this "
           "receipt cannot kill and is parked UNRESOLVED"),
}
CLAUSE_ORDER = ("LIVE", "K1", "K2", "U1", "U0")
CLAUSE_LETTER = {"LIVE": LETTER_LIVE, "K1": LETTER_KILL, "K2": LETTER_KILL,
                 "U1": LETTER_UNRESOLVED, "U0": LETTER_UNRESOLVED}

C3_CAVEAT = S25.C3_CAVEAT

MUTANT_ENV = "QRE2_MILL_S28_MUTANT"
MUTANT_TESTDAY = "selector_uses_test_day"
MUTANT_CURRENT_DAY = "genealogy_reads_current_day"
MUTANTS = (MUTANT_TESTDAY, MUTANT_CURRENT_DAY)


class SweepRefusal(RuntimeError):
    pass


SPEC_SHA = S1._sha_text(SPEC)


def code_sha() -> str:
    """This unit plus every module whose behaviour it is asserting."""

    here = Path(__file__).resolve().parent
    return S1._sha_text("\n".join(
        S1._sha_file(Path(path).resolve()) for path in (
            __file__, here / "zone_history.py", here / "sweep27.py",
            here / "sweep25.py", here / "sweep23.py", here / "sweep22.py",
            here / "levels_zone.py")))


def _mutant() -> str:
    name = os.environ.get(MUTANT_ENV, "")
    if name and name not in MUTANTS:
        raise SweepRefusal(f"unknown sweep 28 mutant: {name}")
    return name


def arm_mutant(mutant: str) -> str:
    """The store mutant lives inside ``zone_history``, so it is armed by env."""

    if mutant == MUTANT_CURRENT_DAY:
        os.environ[ZH.MUTANT_ENV] = ZH.MUTANT_CURRENT_DAY
    return mutant


_n = S22._n
_show = S22._show
_check = S22._check
_mean_se = S22._mean_se


# --------------------------------------------------------------------------
# 3. THE GENEALOGY FEATURE BLOCK.
# --------------------------------------------------------------------------

def genealogy_rows(cands: Sequence[S23.Cand], records: Sequence[S1.CellRec],
                   store: Mapping[str, ZH.AssetHistory]
                   ) -> tuple[np.ndarray, dict[str, object]]:
    """One genealogy row per candidate, at the barrier read's OWN stamp.

    The query key is the candidate's fixed ``zone_price`` and the decision stamp
    ``lat[breach_bar - 1]`` - byte for byte the key and stamp sweep 27's barrier
    read uses, so the two blocks of the R_GEN row describe the same instant at
    the same price and the increment is attributable to the ordered history
    alone.  Every query is audited here as well as in the store's own build:
    this unit refuses on its own 3,790 rows, not only on the build's 300.
    """

    matrix = np.full((len(cands), N_GEN), np.nan, np.float64)
    counters = {"candidates": len(cands), "queried": 0, "no_decision_stamp": 0,
                "no_history": 0, "with_any_event": 0,
                "with_multiple_generations": 0, "with_any_flip": 0,
                "identity_contains_price": 0, "identity_price_outside": 0,
                "identity_key_stable": 0, "identity_key_drifted": 0,
                "strict_time_ok": 0, "strict_time_violations": 0,
                "current_day_events": 0}
    worst = {"latest_event_stamp_minus_decision_ns": None,
             "max_event_d8_minus_decision_d8": None}
    generations: list[int] = []
    for position, cand in enumerate(cands):
        stamp = S25.decision_stamp(cand, records)
        if stamp < 0:
            counters["no_decision_stamp"] += 1
            continue
        history = store.get(str(cand.asset))
        if history is None:
            counters["no_history"] += 1
            continue
        got = ZH.query(history, float(cand.zone_price), int(cand.d8),
                       int(stamp), want_events=False)
        counters["queried"] += 1
        # THE IDENTITY GATE, on this unit's own rows.
        inside = (float(got["band_lo"]) <= float(cand.zone_price)
                  < float(got["band_hi"]))
        counters["identity_contains_price" if inside
                 else "identity_price_outside"] += 1
        again = ZH.query(history, float(cand.zone_price), int(cand.d8),
                         int(stamp), want_events=False)
        counters["identity_key_stable"
                 if int(again["band"]) == int(got["band"])
                 == ZH.band_index(float(cand.zone_price), history.step)
                 else "identity_key_drifted"] += 1
        # THE STRICT-TIME GATE.  The derived query does not carry the event
        # list, so the bound is taken from the eligible session set itself:
        # every served session's day and close stamp.
        bad = 0
        for index in range(int(got["sessions_eligible"])):
            gap = int(history.session_last_stamp[index]) - int(stamp)
            day_gap = int(history.session_d8[index]) - int(cand.d8)
            if worst["latest_event_stamp_minus_decision_ns"] is None or \
                    gap > int(worst["latest_event_stamp_minus_decision_ns"]):
                worst["latest_event_stamp_minus_decision_ns"] = int(gap)
            if worst["max_event_d8_minus_decision_d8"] is None or \
                    day_gap > int(worst["max_event_d8_minus_decision_d8"]):
                worst["max_event_d8_minus_decision_d8"] = int(day_gap)
            if day_gap >= 0:
                counters["current_day_events"] += 1
                bad += 1
            elif gap >= 0:
                bad += 1
        counters["strict_time_violations" if bad else "strict_time_ok"] += 1

        touches = float(got["touches"])
        matrix[position, 0] = float(got["generations"])
        matrix[position, 1] = (float(math.log1p(touches))
                               if math.isfinite(touches) and touches >= 0.0
                               else float("nan"))
        matrix[position, 2] = float(got["held_rate"])
        matrix[position, 3] = float(got["broke_rate"])
        matrix[position, 4] = float(got["role_flips"])
        matrix[position, 5] = float(got["events_since_last_flip"])
        matrix[position, 6] = float(got["sessions_since_last_event"])
        if int(got["generations"]) > 0:
            counters["with_any_event"] += 1
        if int(got["generations"]) > 1:
            counters["with_multiple_generations"] += 1
        if float(got["role_flips"]) > 0.0:
            counters["with_any_flip"] += 1
        generations.append(int(got["generations"]))
    counters["generations_mean"] = (
        float(np.mean(np.asarray(generations, np.float64)))
        if generations else None)
    counters["generations_median"] = (
        float(np.median(np.asarray(generations, np.float64)))
        if generations else None)
    counters["generations_max"] = int(max(generations)) if generations else 0
    census = {name: int(np.isfinite(matrix[:, index]).sum())
              for index, name in enumerate(GEN_FEATURES)}
    return matrix, {"counters": counters, "worst": worst,
                    "finite_per_column": census}


def assert_genealogy_gates(block: Mapping[str, object]) -> None:
    """The store gates, re-asserted on this unit's own rows, before any cash."""

    counters = block["counters"]                      # type: ignore[index]
    if counters["queried"] <= 0:
        raise SweepRefusal("no candidate produced a genealogy query")
    if counters["identity_price_outside"]:
        raise SweepRefusal(
            f"{counters['identity_price_outside']} of {counters['queried']} "
            f"genealogy reads returned a band that does not contain the "
            f"candidate's own zone price")
    if counters["identity_key_drifted"]:
        raise SweepRefusal(
            f"{counters['identity_key_drifted']} of {counters['queried']} "
            f"genealogy reads keyed the same price on the same day to two "
            f"different bands")
    if counters["strict_time_violations"] or counters["current_day_events"]:
        raise SweepRefusal(
            f"{counters['strict_time_violations']} genealogy reads were served "
            f"a session at or after their own decision "
            f"({counters['current_day_events']} of them the CURRENT day); the "
            f"store is not causal and nothing may be scored past it")


def assert_feature_law() -> None:
    """The two rosters, and the exclusions, checked mechanically."""

    S27.assert_feature_law()
    if BASE_FEATURES != tuple(S27.FEATURE_NAMES):
        raise SweepRefusal("R_BASE is not sweep 27's feature row")
    if GEN_FEATURES_ALL[:N_BASE] != BASE_FEATURES:
        raise SweepRefusal("R_GEN does not extend R_BASE in place")
    if len(set(GEN_FEATURES_ALL)) != N_ALL:
        raise SweepRefusal("the combined roster repeats a name")
    derived = set(ZH.DERIVED_FIELDS)
    consumed = {"generations", "touches", "held_rate", "broke_rate",
                "role_flips", "events_since_last_flip",
                "sessions_since_last_event"}
    excluded = set(EXCLUDED_HISTORY_FIELDS)
    missing = consumed - derived
    if missing:
        raise SweepRefusal(f"this unit consumes history fields the store does "
                           f"not serve: {sorted(missing)}")
    overlap = consumed & excluded
    if overlap:
        raise SweepRefusal(f"a history field is both consumed and excluded: "
                           f"{sorted(overlap)}")
    uncovered = derived - consumed - excluded
    if uncovered:
        raise SweepRefusal(
            f"the store serves fields this unit neither consumes nor registers "
            f"as excluded: {sorted(uncovered)}")
    for name in GEN_FEATURES:
        lowered = name.lower()
        for token in S27.FORBIDDEN_OUTCOME_TOKENS:
            if token in lowered:
                raise SweepRefusal(f"genealogy feature {name!r} names an "
                                   f"outcome token {token!r}")


# --------------------------------------------------------------------------
# 6. THE INCREMENT.
# --------------------------------------------------------------------------

def cash_by_date(positions: Sequence[int], entries: Mapping[int, S22.Priced],
                 cands: Sequence[S23.Cand], asset: str, label: str = CLOSE
                 ) -> dict[int, float]:
    """The selected cash of ONE asset, summed inside each calendar date."""

    series: dict[int, float] = {}
    for position in positions:
        cand = cands[int(position)]
        if str(cand.asset) != str(asset):
            continue
        entry = entries.get(int(position))
        if entry is None:
            continue
        series[int(cand.d8)] = series.get(int(cand.d8), 0.0) + float(
            entry.cert[label])
    return series


def increment_lines(picks: Mapping[str, Sequence[int]],
                    entries: Mapping[int, S22.Priced],
                    cands: Sequence[S23.Cand], scoring: Mapping[str, Sequence[int]],
                    label: str = CLOSE) -> dict[str, dict[int, float]]:
    """R_GEN selected cash MINUS R_BASE selected cash, per asset per date.

    EVERY SCORED DATE IS CARRIED, including dates on which one ranker or both
    selected nothing: a date where R_GEN picks four events and R_BASE picks none
    is exactly the evidence the increment is meant to price, and dropping it
    would keep only the dates where the two agree.  A date absent from a
    ranker's selection contributes 0.0 for that ranker, which is what "selected
    no cash that day" means.
    """

    out: dict[str, dict[int, float]] = {}
    for asset in ASSETS:
        gen = cash_by_date(picks["R_GEN"], entries, cands, asset, label)
        base = cash_by_date(picks["R_BASE"], entries, cands, asset, label)
        dates = sorted(set(int(d) for d in scoring.get(asset, ()))
                       | set(gen) | set(base))
        out[f"{LANE}|{asset}"] = {
            int(d8): float(gen.get(int(d8), 0.0) - base.get(int(d8), 0.0))
            for d8 in dates}
    return out


def seated_cash_by_date(trades: Sequence[object], asset: str
                        ) -> dict[int, float]:
    """The SEATED cash of one asset per date, for the information line."""

    series: dict[int, float] = {}
    for trade in trades:
        if str(getattr(trade, "asset")) != str(asset):
            continue
        d8 = int(getattr(trade, "d8"))
        series[d8] = series.get(d8, 0.0) + float(getattr(trade, "pnl_usd"))
    return series


# --------------------------------------------------------------------------
# 8. THE LETTERS.  Five clauses, one precedence, a total partition.
# --------------------------------------------------------------------------

def classify(rung_ok: bool, mdd_ok: bool, cap_ok: bool, stress_ok: bool,
             control_ok: bool, neighbours_ok: bool,
             increment_upper_nonpositive: bool, matched_nonpositive: bool,
             bounds_defined: bool) -> tuple[str, str, list[str]]:
    """Exactly one clause fires; every clause that matched is listed beside it."""

    live = bool(rung_ok and mdd_ok and cap_ok and stress_ok and control_ok
                and neighbours_ok)
    matching: list[str] = []
    if live:
        matching.append("LIVE")
    if increment_upper_nonpositive:
        matching.append("K1")
    if matched_nonpositive:
        matching.append("K2")
    if (not live and not increment_upper_nonpositive
            and not matched_nonpositive and bounds_defined):
        matching.append("U1")
    if (not live and not increment_upper_nonpositive
            and not matched_nonpositive and not bounds_defined):
        matching.append("U0")
    for clause in CLAUSE_ORDER:
        if clause in matching:
            return CLAUSE_LETTER[clause], clause, matching
    raise SweepRefusal("the letter partition failed to cover a receipt")


def family_letter(report: Mapping[str, object]) -> dict[str, object]:
    """One lane, one tested increment, one letter."""

    live = report["live"]                                # type: ignore[index]
    control = report["control"]["by_line"]               # type: ignore[index]
    increment = report["increment"]["by_line"]           # type: ignore[index]
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
    if not mdd_ok:
        reasons.append(f"binding MDD {live['mdd']['max_binding_usd']:.1f} "
                       f">= {MDD_CEILING}")
    cap_ok = bool(live["cash"]["_portfolio"]["cap_lawful"])  # type: ignore[index]
    if not cap_ok:
        reasons.append("the portfolio cap was breached")
    stress_ok = all(bool(live["stress"][kind]["mdd"]["clears"])  # type: ignore[index]
                    for kind in ("adversarial", "spread"))
    if not stress_ok:
        reasons.append("a stress replay breaches MDD")
    control_ok = True
    for asset in DECIDING:
        cell = control.get(f"{LANE}|{asset}")
        if cell is None or cell.get("p_max_adjusted") is None:
            control_ok = False
            reasons.append(f"{asset} has no powered R_GEN matched control")
            continue
        if float(cell["p_max_adjusted"]) > 0.05:
            control_ok = False
            reasons.append(f"{asset} R_GEN control p "
                           f"{cell['p_max_adjusted']:.4f} > 0.05")
    neighbours_ok = bool(live["neighbours_agree"])
    if not neighbours_ok:
        reasons.append("the top-three or top-five neighbour flips a deciding "
                       "sign")

    uppers = {asset: (increment.get(f"{LANE}|{asset}") or {}).get(
        "upper95_simultaneous_usd") for asset in DECIDING}
    deltas = {asset: (control.get(f"{LANE}|{asset}") or {}).get(
        "delta_usd_per_date") for asset in DECIDING}
    bounds_defined = all(value is not None for value in
                         list(uppers.values()) + list(deltas.values()))
    if not bounds_defined:
        reasons.append("a deciding increment bound or matched delta is "
                       "undefined, so neither kill clause can lawfully fire")
    increment_upper_nonpositive = any(
        value is not None and float(value) <= 0.0 for value in uppers.values())
    if increment_upper_nonpositive:
        reasons.append("the genealogy INCREMENT has a non-positive 95% "
                       "simultaneous upper bound on a deciding asset")
    matched_nonpositive = any(
        value is not None and float(value) <= 0.0 for value in deltas.values())
    if matched_nonpositive:
        reasons.append("an R_GEN matched delta is zero or negative")

    letter, clause, matching = classify(
        rung_ok, mdd_ok, cap_ok, stress_ok, control_ok, neighbours_ok,
        increment_upper_nonpositive, matched_nonpositive, bounds_defined)
    return {"letter": letter, "clause": clause, "clause_text": CLAUSES[clause],
            "clauses_matching": matching, "reasons": reasons,
            "rung_ok": rung_ok, "mdd_ok": mdd_ok, "cap_ok": cap_ok,
            "stress_ok": stress_ok, "control_ok": control_ok,
            "neighbours_ok": neighbours_ok,
            "increment_upper_nonpositive": increment_upper_nonpositive,
            "matched_delta_nonpositive": matched_nonpositive,
            "bounds_defined": bounds_defined}


def f24_licence(report: Mapping[str, object]) -> dict[str, object]:
    """Sol's F24 gate, evaluated and PRINTED on UNRESOLVED.  Never a promotion.

    The charter: run F24 only if F22 or F23 yields positive matched deltas on
    BOTH assets but loses material cash to occupancy, cap or MDD.  Sweep 27
    measured occupancy binding at 150 of 468 selected events; this reports the
    same two numbers for each ranker, beside the matched-delta condition.
    """

    control = report["control"]["by_line"]               # type: ignore[index]
    deltas = {asset: (control.get(f"{LANE}|{asset}") or {}).get(
        "delta_usd_per_date") for asset in DECIDING}
    both_positive = all(value is not None and float(value) > 0.0
                        for value in deltas.values())
    occupancy: dict[str, object] = {}
    for name in RANKERS:
        block = report["by_ranker"][name]                # type: ignore[index]
        replay = block["replay"]
        selected = int(block["n"])
        rejected = int(replay["rejected_occupancy"])
        occupancy[name] = {
            "selected": selected, "seated": int(replay["seated"]),
            "rejected_occupancy": rejected,
            "rejected_cap": int(replay["rejected_cap"]),
            "occupancy_share": (float(rejected) / float(selected)
                                if selected else None)}
    parent = {"selected": 468, "rejected_occupancy": 150,
              "occupancy_share": 150.0 / 468.0,
              "source": "sweep 27's own receipt, .audit/mill-sweep27.json"}
    material = any(
        cell["occupancy_share"] is not None                # type: ignore[index]
        and float(cell["occupancy_share"]) > 0.0           # type: ignore[index]
        for cell in occupancy.values())
    return {
        "gate": "does any lane show positive matched deltas on BOTH deciders "
                "while losing material cash to occupancy, cap or MDD?",
        "matched_deltas": deltas,
        "both_deciders_positive": both_positive,
        "occupancy": occupancy, "parent_reference": parent,
        "occupancy_material": material,
        "licensed": bool(both_positive and material),
        "verdict": ("LICENSED: both deciding matched deltas are positive and "
                    "the lane loses seats to occupancy, so F24-SIZE-SEAT may "
                    "be run on this qualified entry set"
                    if both_positive and material else
                    "NOT LICENSED: " + ("the deciding matched deltas are not "
                                        "both positive"
                                        if not both_positive else
                                        "no material cash is lost to "
                                        "occupancy") + "; per the charter F24 "
                    "is stamped NOT-LICENSED without an outcome read"),
        "note": "a LICENCE READ only.  It is not a letter, it promotes "
                "nothing, and it opens no outcome byte."}


# --------------------------------------------------------------------------
# The run.
# --------------------------------------------------------------------------

def run() -> dict[str, object]:
    mutant = arm_mutant(_mutant())
    started = time.time()
    assert_feature_law()
    if ZH.GRID_WARMUP_DAYS != MIN_PRIOR_DAYS:
        raise SweepRefusal(
            f"the genealogy grid warmup ({ZH.GRID_WARMUP_DAYS}) is not the "
            f"ranker's warmup ({MIN_PRIOR_DAYS}), so the grid is not fixed "
            f"before the first scored session")

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
        raise SweepRefusal("the levels cache was built against a different "
                           "split than this unit reads")
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

    # ---- 1. formation: sweep 23's, unchanged, and the universe must match ---
    cands, formation = S23.formation_pass(cells, explore_days, "")
    if not formation["strictly_prior"]:
        raise SweepRefusal(
            f"a level read is not strictly prior to its breach close: "
            f"max(source - breach) = {formation['max_src_minus_breach_ns']} ns")
    if len(cands) != EXPECT_CANDIDATES:
        raise SweepRefusal(
            f"the formation pass returned {len(cands)} candidates, not the "
            f"parent's {EXPECT_CANDIDATES}; the universe is not identical, so "
            f"the increment under test is not attributable")

    # ---- 0. THE STORE, BUILT AND GATED BEFORE ANY CASH ---------------------
    store, store_build = ZH.build()
    store_audit = ZH.audit(store)
    ZH.assert_gates(store_audit)

    # ---- 2. the barrier read, sweep 27's, at the fixed zone price ----------
    reader = LZ.reader(ASSETS)
    read = S27.zone_read(cands, records, reader)
    S27.assert_zone_anchored(read)

    # ---- pricing: lane A, the G1 pool, the magnitude rows, the ceiling -----
    priced = S27.pricing_pass(cands, cells, streams, records)
    if priced["plane_checks"]["mismatched"]:
        raise SweepRefusal(
            "a lane-A close-label cert disagreed with the frozen cert plane at "
            f"the same (cell, side, bar): worst "
            f"{priced['plane_checks']['worst_abs_usd']:.6f} USD")
    if priced["same_close"]["violations"]:
        raise SweepRefusal(
            f"{priced['same_close']['violations']} lane-A entries filled at or "
            f"before their own breach close")

    folds_impulse, impulse_report = S22.fit_impulse(priced["mag"], explore_days,
                                                    mutant)
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

    # ---- 3. the two feature rows ------------------------------------------
    base, base_census = S27.build_features(read, cands)
    base[:, S27.I_BREAK_COLUMN] = impulse
    base_census["finite_per_column"]["I_break"] = int(np.isfinite(impulse).sum())
    base_census["rows_without_finite_I_break"] = int(
        (~np.isfinite(impulse)).sum())
    gen, gen_block = genealogy_rows(cands, records, store)
    assert_genealogy_gates(gen_block)
    features = {"R_BASE": base, "R_GEN": np.hstack([base, gen])}

    # ---- 4. the two rankers, both through sweep 27's own fold law ----------
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

    folds: dict[str, list] = {}
    rank_reports: dict[str, object] = {}
    diagnostics: dict[str, object] = {}
    beta_mean: dict[str, object] = {}
    for name in RANKERS:
        got, rank_report = S27.rank_folds(positions_by_day, features[name],
                                          cert, explore_days, mutant)
        rank_report["candidates_priced"] = int(len(entries))
        rank_report["candidates_unpriced"] = int(len(cands) - len(entries))
        folds[name] = got
        rank_reports[name] = rank_report
        columns = GEN_FEATURES_ALL if name == "R_GEN" else BASE_FEATURES
        diagnostics[name] = {
            asset: {
                "folds": len([f for f in got if f.asset == asset]),
                "folds_with_rank_corr": len(
                    [f for f in got if f.asset == asset
                     and f.rank_corr is not None]),
                "oof_rank_corr_mean": (float(np.mean(
                    [f.rank_corr for f in got if f.asset == asset
                     and f.rank_corr is not None]))
                    if any(f.asset == asset and f.rank_corr is not None
                           for f in got) else None),
                "oof_rank_corr_median": (float(np.median(
                    [f.rank_corr for f in got if f.asset == asset
                     and f.rank_corr is not None]))
                    if any(f.asset == asset and f.rank_corr is not None
                           for f in got) else None),
                "oof_rank_corr_p_positive": (float(np.mean(
                    [f.rank_corr > 0 for f in got if f.asset == asset
                     and f.rank_corr is not None]))
                    if any(f.asset == asset and f.rank_corr is not None
                           for f in got) else None),
                "train_rows_mean": (float(np.mean(
                    [f.train_rows for f in got if f.asset == asset]))
                    if any(f.asset == asset for f in got) else None),
                "scored_rows": int(sum(len(f.positions) for f in got
                                       if f.asset == asset)),
                "beta_l2_mean": (float(np.mean(
                    [float(np.linalg.norm(f.beta)) for f in got
                     if f.asset == asset]))
                    if any(f.asset == asset for f in got) else None)}
            for asset in ASSETS}
        beta_mean[name] = {
            asset: {column: float(np.mean([float(f.beta[index]) for f in got
                                           if f.asset == asset]))
                    for index, column in enumerate(columns)}
            for asset in ASSETS if any(f.asset == asset for f in got)}

    # ---- 5. the selection, and its two non-letter neighbours, per ranker ---
    formed_by_asset = {asset: sum(1 for c in cands if c.asset == asset)
                       for asset in ASSETS}
    formed_opportunities: dict[str, int] = {}
    for cand in cands:
        key = f"{cand.asset}|{cand.d8}"
        formed_opportunities[key] = formed_opportunities.get(key, 0) + 1

    picks: dict[str, dict[int, list[int]]] = {
        name: {k: S27.selections(folds[name], k) for k in ALL_K}
        for name in RANKERS}
    by_ranker: dict[str, object] = {}
    neighbours: dict[str, object] = {}
    trades_by_ranker: dict[str, object] = {}
    for name in RANKERS:
        by_k: dict[str, object] = {}
        for k in ALL_K:
            chosen = [entries[p] for p in picks[name][k]]
            by_k[str(k)] = S22.evaluate_lane(LANE, chosen, cands, explore_days,
                                             formed_by_asset)
        block = by_k[str(TOP_K)]
        agree = True
        for asset in DECIDING:
            base_value = block["cash"][asset]["usd_per_day"]
            for k in NEIGHBOUR_K:
                other = by_k[str(k)]["cash"][asset]["usd_per_day"]
                if base_value is None or other is None:
                    agree = False
                elif (base_value > 0) != (other > 0):
                    agree = False
        block["neighbours_agree"] = bool(agree)
        trades_by_ranker[name] = list(block["trades"])
        neighbours[name] = {str(k): {
            "n": by_k[str(k)]["n"],
            "seated": by_k[str(k)]["replay"]["seated"],
            "cash": {asset: {
                "usd_per_day": by_k[str(k)]["cash"][asset]["usd_per_day"],
                "mean_minus_2se_usd": by_k[str(k)]["cash"][asset][
                    "mean_minus_2se_usd"],
                "clears_rung": by_k[str(k)]["cash"][asset]["clears_rung"]}
                for asset in ASSETS}} for k in ALL_K}
        for k in ALL_K:
            by_k[str(k)].pop("trades", None)
        by_ranker[name] = block

    live = by_ranker["R_GEN"]
    selected_positions = list(picks["R_GEN"][TOP_K])
    selected_entries = [entries[p] for p in selected_positions]

    # ---- 7. stresses and the MDD ledger family, for both rankers ----------
    for name in RANKERS:
        chosen = [entries[p] for p in picks[name][TOP_K]]
        block = by_ranker[name]
        stress: dict[str, object] = {}
        for kind in ("adversarial", "spread"):
            overrides = S22.stress_overrides(chosen, CLOSE, kind)
            seated = S22.replay(chosen, CLOSE, overrides)
            stress[kind] = {
                "seated": seated["seated"],
                "cash": S22.replay_cash(seated["trades"], explore_days),
                "mdd": S22.mdd_ledgers(seated["trades"], priced["mid_by_cell"],
                                       priced["lat_by_cell"], explore_days)}
        block["stress"] = stress
        block["mdd"] = S22.mdd_ledgers(trades_by_ranker[name],
                                       priced["mid_by_cell"],
                                       priced["lat_by_cell"], explore_days)

    # ---- 6a. THE INCREMENT, the tested object -----------------------------
    lines = increment_lines({name: picks[name][TOP_K] for name in RANKERS},
                            entries, cands, scoring)
    family = [f"{LANE}|{asset}" for asset in DECIDING]
    increment = S22.maxt_inference(lines, family, SIGN_DRAWS)
    increment["event_level_p"] = (
        "FORBIDDEN and not computed: several events share one impulse, one day "
        "and one seat ledger, so the independent unit is the calendar date")
    increment["definition"] = (
        "R_GEN selected cash MINUS R_BASE selected cash, summed inside each "
        "shared calendar date over the frozen close-label cert, studentized "
        "and read under one shared-date-sign maxT family over NKD and SI")

    seated_lines: dict[str, dict[int, float]] = {}
    for asset in ASSETS:
        gen_series = seated_cash_by_date(trades_by_ranker["R_GEN"], asset)
        base_series = seated_cash_by_date(trades_by_ranker["R_BASE"], asset)
        dates = sorted(set(int(d) for d in scoring.get(asset, ()))
                       | set(gen_series) | set(base_series))
        seated_lines[f"{LANE}|{asset}"] = {
            int(d8): float(gen_series.get(int(d8), 0.0)
                           - base_series.get(int(d8), 0.0)) for d8 in dates}
    increment_seated = S22.maxt_inference(seated_lines, family, SIGN_DRAWS)
    increment_seated["note"] = (
        "INFORMATION ONLY, carries no letter: the SEATED increment moves with "
        "seat contention, which both rankers share but do not share equally, "
        "so it is not the clean paired object the selected increment is")

    increment_counts = {
        name: {asset: {"events": sum(1 for p in picks[name][TOP_K]
                                     if cands[p].asset == asset),
                       "dates": len({int(cands[p].d8) for p in picks[name][TOP_K]
                                     if cands[p].asset == asset})}
               for asset in ASSETS} for name in RANKERS}
    overlap = {asset: {
        "both": len(set(p for p in picks["R_GEN"][TOP_K]
                        if cands[p].asset == asset)
                    & set(p for p in picks["R_BASE"][TOP_K]
                          if cands[p].asset == asset)),
        "gen_only": len(set(p for p in picks["R_GEN"][TOP_K]
                            if cands[p].asset == asset)
                        - set(p for p in picks["R_BASE"][TOP_K]
                              if cands[p].asset == asset)),
        "base_only": len(set(p for p in picks["R_BASE"][TOP_K]
                             if cands[p].asset == asset)
                         - set(p for p in picks["R_GEN"][TOP_K]
                               if cands[p].asset == asset))}
        for asset in ASSETS}

    # ---- C2: the formed ceiling -------------------------------------------
    ceiling_block: dict[str, object] = {
        "SELECTED": {"cash": S23.ceiling_cash(selected_positions, cands,
                                              priced["ceiling"], explore_days),
                     "hindsight_bits": list(HINDSIGHT_CEILING)},
        "FORMED_UNIVERSE": {"cash": S23.ceiling_cash(range(len(cands)), cands,
                                                     priced["ceiling"],
                                                     explore_days),
                            "hindsight_bits": list(HINDSIGHT_CEILING)}}
    best_by_date: dict[int, list[tuple[float, str]]] = {}
    for position, cand in enumerate(cands):
        best = priced["ceiling"].get(position)
        if best is None:
            continue
        best_by_date.setdefault(int(cand.d8), []).append(
            (float(best["usd"]), cand.asset))
    capped_cash: dict[str, object] = {}
    for asset in ASSETS:
        day_list = sorted(int(d) for d in explore_days[asset])
        sums = {day: 0.0 for day in day_list}
        n = 0
        for d8, rows in best_by_date.items():
            if d8 not in sums:
                continue
            for value, owner in sorted(rows, key=lambda r: -r[0])[:PORTFOLIO_CAP]:
                if owner == asset:
                    sums[d8] += value
                    n += 1
        series = [sums[day] for day in day_list]
        mean, _se = _mean_se(series)
        capped_cash[asset] = {
            "n": n, "usd_per_day": mean, "rung_usd": DAY_RUNG_USD[asset],
            "over_rung": None if mean is None else mean / DAY_RUNG_USD[asset],
            "carries_rung": None if mean is None else bool(
                mean >= DAY_RUNG_USD[asset])}
    ceiling_block["FORMED_CAPPED"] = {
        "cash": capped_cash,
        "hindsight_bits": list(HINDSIGHT_CEILING) + ["which twelve per date"]}

    # ---- 6b. C1: the matched, vector-permuted control for R_GEN -----------
    finite = impulse[np.isfinite(impulse)]
    edges = (np.percentile(finite, [100.0 / 3.0, 200.0 / 3.0])
             if len(finite) else np.asarray([0.0, 0.0]))
    for key, rows in priced["g1_pool"].items():
        fold = folds_impulse.get((key[0], key[1]))
        if fold is None:
            continue
        for row in rows:
            if row["x"] is None:
                continue
            x = S14._impute(np.asarray(row["x"], np.float64)[None, :],
                            np.asarray(fold["impute"], np.float64))
            z = (x - np.asarray(fold["mean"], np.float64)) / np.asarray(
                fold["sd"], np.float64)
            value = float(fold["centre"]) + float(
                (z @ np.asarray(fold["beta"], np.float64))[0])
            row["impulse"] = value
            row["mag_bin"] = int(np.searchsorted(edges, value))
    mag_bin = {}
    for entry in selected_entries:
        value = impulse[entry.position]
        mag_bin[entry.position] = int(
            np.searchsorted(edges, value)) if np.isfinite(value) else 0
    matched, match_counters = S22.match_controls(selected_entries, cands,
                                                 priced["g1_pool"], impulse,
                                                 mag_bin)
    control_lines: dict[str, dict[int, float]] = {}
    control_pairs = {asset: 0 for asset in ASSETS}
    for asset in ASSETS:
        series: dict[int, float] = {}
        for position, entry in enumerate(selected_entries):
            if entry.asset != asset or position not in matched:
                continue
            control_entry = priced["g1_priced"].get(int(matched[position]["row"]))
            if control_entry is None:
                continue
            series[int(entry.d8)] = series.get(int(entry.d8), 0.0) + (
                float(entry.cert[CLOSE]) - float(control_entry.cert[CLOSE]))
            control_pairs[asset] += 1
        control_lines[f"{LANE}|{asset}"] = series
    control = S22.maxt_inference(control_lines, family, SIGN_DRAWS)
    control["event_level_p"] = (
        "FORBIDDEN and not computed: several events share one impulse, one day "
        "and one seat ledger, so the independent unit is the calendar date")

    # The registered permutation, over the COMPLETE level-plus-genealogy vector.
    rng = np.random.default_rng(SEED + 64)
    fold_by_day = {(f.asset, f.d8): f for f in folds["R_GEN"]}
    permuted = {"controls": 0, "positive_score": 0, "top4_score": 0,
                "selected_positive": 0, "selected_top4": 0}
    for position, entry in enumerate(selected_entries):
        fold = fold_by_day.get((entry.asset, int(entry.d8)))
        if fold is None or position not in matched:
            continue
        train_days = [d for d in sorted(int(day) for day in
                                        S1._explore_days((entry.asset,))[entry.asset])
                      if d < int(entry.d8)]
        pool = [p for day in train_days
                for p in positions_by_day.get((entry.asset, day), [])]
        if not pool:
            continue
        donor = int(pool[int(rng.integers(0, len(pool)))])
        z = S27._design(features["R_GEN"][donor][None, :], fold.centre,
                        fold.spread)
        score = float((z @ fold.beta)[0])
        permuted["controls"] += 1
        permuted["positive_score"] += int(score > 0.0)
        cut = sorted(fold.scores, reverse=True)[:TOP_K]
        threshold = float(cut[-1]) if cut else 0.0
        permuted["top4_score"] += int(score > 0.0 and score >= threshold)
        own = float(fold.scores[int(np.flatnonzero(
            fold.positions == int(entry.position))[0])])
        permuted["selected_positive"] += int(own > 0.0)
        permuted["selected_top4"] += 1
    permuted["share_permuted_positive"] = (
        float(permuted["positive_score"] / permuted["controls"])
        if permuted["controls"] else None)
    permuted["share_permuted_top4"] = (
        float(permuted["top4_score"] / permuted["controls"])
        if permuted["controls"] else None)

    # ---- C3: block-permutation nulls, with the standing caveat -------------
    eligible: dict[tuple[str, str, int], list[int]] = {}
    for position, cand in enumerate(cands):
        eligible.setdefault((cand.asset, cand.phase, cand.d8), []).append(position)
    cert_by_position = {p: float(entries[p].cert[CLOSE]) for p in entries}
    nulls = {f"{LANE}|{asset}": S22.block_null(
        selected_positions, cands, eligible, cert_by_position, explore_days,
        asset, CONTROL_DRAWS) for asset in ASSETS}

    # ---- the selected cohort, recorded, never gating ----------------------
    cohort: dict[str, object] = {}
    direction: dict[str, dict[int, int]] = {}
    for entry in selected_entries:
        cand = cands[entry.position]
        table = direction.setdefault(cand.asset, {1: 0, -1: 0})
        table[int(cand.break_dir)] = table.get(int(cand.break_dir), 0) + 1
    for asset in ASSETS:
        mine = [e.position for e in selected_entries if e.asset == asset]
        pool = [p for p, c in enumerate(cands) if c.asset == asset]
        if not mine:
            continue
        take = np.asarray(mine, np.int64)
        base_take = np.asarray(pool, np.int64)
        with np.errstate(invalid="ignore"):
            cohort[asset] = {
                "n": int(len(mine)),
                "selected_mean": {name: float(np.nanmean(
                    features["R_GEN"][take, index]))
                    for index, name in enumerate(GEN_FEATURES_ALL)},
                "formed_mean": {name: float(np.nanmean(
                    features["R_GEN"][base_take, index]))
                    for index, name in enumerate(GEN_FEATURES_ALL)}}

    report: dict[str, object] = {
        "schema": "QRE2MILLSWEEP28", "spec_sha": SPEC_SHA,
        "code_sha": code_sha(), "split_sha": S1.split_sha(),
        "outcome_law_sha": S1.outcome_law_sha(), "seed": SEED,
        "mutant": mutant, "family": FAMILY, "parent_trial": PARENT_TRIAL,
        "selection_rule": SELECTION_RULE, "registered_utc": report_stamp(),
        "residual_note": RESIDUAL_NOTE, "increment_note": INCREMENT_NOTE,
        "order_note": ORDER_NOTE,
        "compression_note": S27.COMPRESSION_NOTE,
        "selector_sign_note": S23.SELECTOR_SIGN_NOTE,
        "contamination_note": S25.CONTAMINATION_NOTE,
        "parent_spec_sha": S27.SPEC_SHA, "parent_code_sha": S27.code_sha(),
        "accessor_code_sha": S1._sha_file(Path(LZ.__file__).resolve()),
        "store_code_sha": S1._sha_file(Path(ZH.__file__).resolve()),
        "asset_days": {a: int(days.get(a, 0)) for a in ASSETS},
        "reproduction": repro, "stream_counters": stream_counters,
        "causality": causal,
        "formation": {k: v for k, v in formation.items() if k != "params"},
        "formed_opportunities_per_asset_day": formed_opportunities,
        "formed_by_asset": formed_by_asset,
        "candidates_match_parent": bool(len(cands) == EXPECT_CANDIDATES),
        "zone_read": read.counters,
        "store_build": store_build, "store_audit": store_audit,
        "store_law": {
            "key": f"(asset, floor(price / step)), step = "
                   f"{ZH.BAND_ATR_MULT} * atr_ref",
            "atr_ref": f"median prior-day ATR14 over the first "
                       f"{ZH.GRID_WARMUP_DAYS} EXPLORE sessions",
            "events": list(ZH.EVENT_KINDS),
            "reading_side": ZH.READING_SIDE,
            "strict_time": "calendar day strictly earlier AND session close "
                           "strictly before the decision stamp",
            "hold": "SEALED"},
        "genealogy_read": gen_block,
        "feature_law": {
            "R_BASE": {"names": list(BASE_FEATURES), "n": N_BASE,
                       "source": "sweep27.FEATURE_NAMES, by value"},
            "R_GEN": {"names": list(GEN_FEATURES_ALL), "n": N_ALL,
                      "added": list(GEN_FEATURES),
                      "added_from": GEN_FEATURES_FROM},
            "excluded_history_fields": EXCLUDED_HISTORY_FIELDS,
            "missingness": "a NaN is imputed at the TRAINING FOLD mean of its "
                           "own column, so it standardizes to exactly zero and "
                           "carries no information; a rate is NaN where its "
                           "touch count is not positive, and events-since-flip "
                           "is NaN where no flip has occurred",
            "base_census": base_census,
            "gen_census": gen_block["finite_per_column"]},
        "ranker_law": {
            "source": "sweep27.rank_folds / select_top / fit_ridge, called "
                      "directly: the law is sweep 27's by call graph",
            "scope": "one ridge per ASSET, refit on every out-of-fold asset-day",
            "target": "the WITHIN-ASSET-DAY PERCENTILE of the frozen cert",
            "weights": "each asset-day weighted equally",
            "penalty": f"lambda = {RIDGE_LAMBDA}, FIXED; no model search, no "
                       f"penalty search",
            "warmup": f">= {MIN_PRIOR_DAYS} prior EXPLORE days and "
                      f">= {MIN_TRAIN_ROWS} training rows",
            "selection": f"at most the top {TOP_K} POSITIVE-score events per "
                         f"out-of-fold asset-day, for EACH ranker; "
                         f"{list(NEIGHBOUR_K)} as non-letter neighbours"},
        "ranker": rank_reports, "ranker_diagnostics": diagnostics,
        "ranker_beta_mean": beta_mean,
        "pricing_counters": priced["counters"],
        "plane_checks": priced["plane_checks"],
        "same_close_check": priced["same_close"],
        "impulse": impulse_report, "impulse_join": join,
        "impulse_counters": impulse_counters,
        "selection_counts": {name: {str(k): len(picks[name][k]) for k in ALL_K}
                             for name in RANKERS},
        "selection_overlap": overlap, "increment_counts": increment_counts,
        "by_ranker": by_ranker, "live": live, "neighbours": neighbours,
        "increment": increment, "increment_seated": increment_seated,
        "ceiling": ceiling_block, "control": control,
        "control_counters": match_counters,
        "control_pairs_per_asset": control_pairs,
        "control_permutation": permuted,
        "block_nulls": nulls, "block_null_caveat": C3_CAVEAT,
        "selected_cohort": cohort, "selected_direction": direction,
        "scoring_days": {a: scoring[a] for a in ASSETS},
        "clauses": CLAUSES, "clause_order": list(CLAUSE_ORDER),
        "elapsed_s": round(time.time() - started, 1)}
    letter = family_letter(report)
    report["letter"] = letter
    report["family_letter"] = letter["letter"]
    report["family_clause"] = letter["clause"]
    report["f24_licence"] = f24_licence(report)
    report["headline"] = headline(report)
    return report


def headline(report: Mapping[str, object]) -> dict[str, object]:
    """Deciding usd/day over rung for R_GEN, the increment, the ceilings."""

    cash = report["live"]["cash"]                           # type: ignore[index]
    increment = report["increment"]["by_line"]              # type: ignore[index]
    control = report["control"]["by_line"]                  # type: ignore[index]
    ceiling = report["ceiling"]["FORMED_UNIVERSE"]["cash"]  # type: ignore[index]
    capped = report["ceiling"]["FORMED_CAPPED"]["cash"]     # type: ignore[index]
    return {
        "read": "zone genealogy increment over the fixed-zone component plane",
        "over_rung": {asset: (None if cash[asset]["usd_per_day"] is None
                              else cash[asset]["usd_per_day"]
                              / DAY_RUNG_USD[asset]) for asset in DECIDING},
        "increment_usd_per_date": {
            asset: (increment.get(f"{LANE}|{asset}") or {}).get(
                "delta_usd_per_date") for asset in DECIDING},
        "increment_p_adjusted": {
            asset: (increment.get(f"{LANE}|{asset}") or {}).get(
                "p_max_adjusted") for asset in DECIDING},
        "increment_upper95": {
            asset: (increment.get(f"{LANE}|{asset}") or {}).get(
                "upper95_simultaneous_usd") for asset in DECIDING},
        "matched_delta_usd_per_date": {
            asset: (control.get(f"{LANE}|{asset}") or {}).get(
                "delta_usd_per_date") for asset in DECIDING},
        "matched_p_adjusted": {
            asset: (control.get(f"{LANE}|{asset}") or {}).get("p_max_adjusted")
            for asset in DECIDING},
        "formed_ceiling_over_rung": {asset: ceiling[asset]["over_rung"]
                                     for asset in DECIDING},
        "capped_ceiling_over_rung": {asset: capped[asset]["over_rung"]
                                     for asset in DECIDING},
        "family_letter": report["family_letter"],
        "family_clause": report["family_clause"]}


# --------------------------------------------------------------------------
# Printing.
# --------------------------------------------------------------------------

def print_summary(report: Mapping[str, object]) -> None:
    head = report["headline"]
    over = ", ".join(f"{asset} {_n(head['over_rung'].get(asset), 7, 4)}x"
                     for asset in DECIDING)
    delta = ", ".join(
        f"{asset} {_n(head['increment_usd_per_date'].get(asset), 8, 1)} "
        f"usd/date (p {_n(head['increment_p_adjusted'].get(asset), 6, 4)})"
        for asset in DECIDING)
    ceiling = ", ".join(
        f"{asset} {_n(head['formed_ceiling_over_rung'].get(asset), 7, 3)}x"
        for asset in DECIDING)
    capped = ", ".join(
        f"{asset} {_n(head['capped_ceiling_over_rung'].get(asset), 7, 3)}x"
        for asset in DECIDING)
    print(f"F23-ZONE-GENEALOGY: R_GEN deciding usd/day over rung {over}; "
          f"GENEALOGY INCREMENT {delta}; formed ceiling {ceiling}; capped "
          f"ceiling {capped}; family {head['family_letter']} (clause "
          f"{head['family_clause']})")


def print_gate(report: Mapping[str, object]) -> None:
    repro = report["reproduction"]
    print("\n== GATE ==")
    print(f"  sweep 9 plane reproduces : {repro['matches']}")
    print(f"  stream counters          : {report['stream_counters']}")
    print(f"  no outcome in features   : "
          f"{report['causality']['no_outcome_in_features']}")
    formation = report["formation"]
    print(f"  formation levels audit   : strictly prior "
          f"{formation['strictly_prior']}, max(level source - breach close) "
          f"{formation['max_src_minus_breach_ns']} ns")
    print(f"  candidates match sweep 25's {EXPECT_CANDIDATES}: "
          f"{report['candidates_match_parent']}")
    print(f"  pricing counters         : {report['pricing_counters']}")
    checks = report["plane_checks"]
    print(f"  lane A vs frozen cert plane: compared {checks['compared']}, "
          f"mismatched {checks['mismatched']}, worst "
          f"{checks['worst_abs_usd']:.9f} USD")
    same = report["same_close_check"]
    print(f"  lane A same-close prohibition: checked {same['checked']}, "
          f"violations {same['violations']}, worst (breach close - entry) "
          f"{_show(same['worst_gap_ns'])} ns (must be strictly negative)")
    cell = report["zone_read"]
    print(f"  barrier read (sweep 27's): centre EXACT "
          f"{cell['center_exact']}/{cell['rows']}, mismatched "
          f"{cell['center_mismatched']}, strictly prior "
          f"{cell['strictly_prior']}/{cell['rows']}, worst "
          f"{cell['worst_source_minus_decision_ns']} ns")
    print(f"  impulse ridge            : {report['impulse']['counters']}, "
          f"WITHIN-DAY R2 {report['impulse']['pooled_within_day_r2']}")


def print_store(report: Mapping[str, object]) -> None:
    law = report["store_law"]
    block = report["store_build"]
    print("\n== THE ZONE GENEALOGY STORE, GATED BEFORE ANY CASH ==")
    for key in ("key", "atr_ref", "strict_time", "hold"):
        print(f"  {key:<14}: {law[key]}")
    print(f"  events        : {law['events']}, read at side "
          f"{law['reading_side']} (the mirror records both)")
    print(f"  counters      : {block['counters']}")
    print("  asset  sessions   bands  multi-session      events     touch"
          "      held     broke   flips   unresolved")
    for asset in ASSETS:
        cell = block["per_asset"][asset]
        print(f"  {asset:<5} {cell['sessions']:>9} {cell['bands']:>7} "
              f"{cell['bands_with_multiple_sessions']:>14} "
              f"{cell['events']:>11} {cell['touch']:>9} {cell['held']:>9} "
              f"{cell['broke']:>9} {cell['flip']:>7} {cell['unresolved']:>12}")
    audit = report["store_audit"]["counters"]
    print(f"\n  THE BUILD'S OWN 300-QUERY AUDIT over real sweep-25 candidates:")
    print(f"    identity, band contains the price : "
          f"{audit['identity_contains_price']}/{audit['queries']} "
          f"(outside {audit['identity_price_outside']})")
    print(f"    identity, same price same day same key : "
          f"{audit['identity_key_stable']}/{audit['queries']} "
          f"(drifted {audit['identity_key_drifted']})")
    print(f"    strict time, every event earlier  : "
          f"{audit['strict_time_ok']}/{audit['queries']} "
          f"(violations {audit['strict_time_violations']}, current-day "
          f"{audit['current_day_events']})")
    print(f"    worst (event stamp - decision) "
          f"{report['store_audit']['worst']['latest_event_stamp_minus_decision_ns']}"
          f" ns, worst (event day - decision day) "
          f"{report['store_audit']['worst']['max_event_d8_minus_decision_d8']}")

    gen = report["genealogy_read"]
    counters = gen["counters"]
    print(f"\n  THIS UNIT'S OWN {counters['queried']} QUERIES, one per formed "
          f"candidate, re-gated:")
    print(f"    identity, band contains the price : "
          f"{counters['identity_contains_price']}/{counters['queried']} "
          f"(outside {counters['identity_price_outside']})")
    print(f"    identity, same key at every stamp : "
          f"{counters['identity_key_stable']}/{counters['queried']} "
          f"(drifted {counters['identity_key_drifted']})")
    print(f"    strict time                       : "
          f"{counters['strict_time_ok']}/{counters['queried']} "
          f"(violations {counters['strict_time_violations']}, current-day "
          f"{counters['current_day_events']})")
    print(f"    worst (served session close - decision) "
          f"{gen['worst']['latest_event_stamp_minus_decision_ns']} ns, worst "
          f"(served session day - decision day) "
          f"{gen['worst']['max_event_d8_minus_decision_d8']}")
    print(f"    DEPTH: queries with any earlier event "
          f"{counters['with_any_event']}, with more than one generation "
          f"{counters['with_multiple_generations']}, with any role flip "
          f"{counters['with_any_flip']}")
    print(f"    generations per query: mean "
          f"{_show(counters['generations_mean'])}, median "
          f"{_show(counters['generations_median'])}, max "
          f"{counters['generations_max']}")


def print_features(report: Mapping[str, object]) -> None:
    law = report["feature_law"]
    print("\n== THE TWO FEATURE ROWS ==")
    print(f"  R_BASE {law['R_BASE']['n']} columns, {law['R_BASE']['source']}")
    print(f"  R_GEN  {law['R_GEN']['n']} columns = R_BASE + "
          f"{len(law['R_GEN']['added'])} genealogy fields")
    print("  #  genealogy column             from                       "
          "finite   share")
    rows = int(law["base_census"]["rows"])
    for index, name in enumerate(law["R_GEN"]["added"]):
        finite = int(law["gen_census"][name])
        print(f"  {index:>2} {name:<28} {law['R_GEN']['added_from'][name]:<26} "
              f"{finite:>6} {finite / max(rows, 1):>7.4f}")
    print(f"  MISSINGNESS: {law['missingness']}")
    print("  EXCLUDED store fields, registered and asserted against "
          "zone_history.DERIVED_FIELDS:")
    for name, why in sorted(law["excluded_history_fields"].items()):
        print(f"    {name:<20} {why}")


def print_rankers(report: Mapping[str, object]) -> None:
    law = report["ranker_law"]
    print("\n== THE TWO RANKERS, ONE LAW ==")
    for key in ("source", "scope", "target", "weights", "penalty", "warmup",
                "selection"):
        print(f"  {key:<12}: {law[key]}")
    for name in RANKERS:
        block = report["ranker"][name]
        print(f"\n  {name}: {block['days_scored']} out-of-fold asset-days "
              f"scored, {block['days_warmup']} in warmup, {block['days_thin']} "
              f"thin, {block['scored_rows']} rows scored, "
              f"{block['train_rows_total']} training rows summed over folds")
        print("  asset  folds  with-corr   mean rho   median rho   P(rho>0)   "
              "train rows   scored   |beta|")
        for asset in ASSETS:
            cell = report["ranker_diagnostics"][name][asset]
            print(f"  {asset:<5} {cell['folds']:>6} "
                  f"{cell['folds_with_rank_corr']:>10} "
                  f"{_n(cell['oof_rank_corr_mean'], 10, 4)} "
                  f"{_n(cell['oof_rank_corr_median'], 12, 4)} "
                  f"{_n(cell['oof_rank_corr_p_positive'], 10, 3)} "
                  f"{_n(cell['train_rows_mean'], 12, 1)} "
                  f"{cell['scored_rows']:>8} {_n(cell['beta_l2_mean'], 8, 3)}")
    print("\n  MEAN RIDGE COEFFICIENT PER COLUMN (standardized units; recorded, "
          "never a gate).  R_BASE columns first, then the genealogy block:")
    print("  column                        " + "".join(
        f"{asset + ' base':>14}{asset + ' gen':>14}" for asset in DECIDING))
    for name in GEN_FEATURES_ALL:
        cells = ""
        for asset in DECIDING:
            base_v = report["ranker_beta_mean"]["R_BASE"].get(asset, {}).get(name)
            gen_v = report["ranker_beta_mean"]["R_GEN"].get(asset, {}).get(name)
            cells += _n(base_v, 14, 4) + _n(gen_v, 14, 4)
        marker = "  <-- GENEALOGY" if name in GEN_FEATURES else ""
        print(f"  {name:<28}{cells}{marker}")


def print_selection(report: Mapping[str, object]) -> None:
    for name in RANKERS:
        block = report["by_ranker"][name]
        print(f"\n== {name}: top {TOP_K} positive-score events per out-of-fold "
              f"asset-day ==")
        print(f"  selected entries {block['n']}, seated "
              f"{block['replay']['seated']}, rejected occupancy "
              f"{block['replay']['rejected_occupancy']}, rejected cap "
              f"{block['replay']['rejected_cap']}")
        print("  asset  label       n  cover   P(>0)  [lo, hi]        mean    "
              "median     usd/day    over-rung    seated usd/day   -2SE   "
              "MDD(day)")
        for asset in ASSETS:
            for label in LABELS:
                row = block["per_asset"][asset][label]
                cash = block["cash"][asset] if label == CLOSE else None
                wilson = row["p_cert_positive"]
                print(f"  {asset:<5} {label:<6} {row['n']:>5} "
                      f"{_n(row['coverage'], 6, 3)} {_n(wilson['rate'], 6, 3)} "
                      f"[{_n(wilson['lo'], 5, 2)},{_n(wilson['hi'], 5, 2)}] "
                      f"{_n(row['mean_cert_usd'], 9, 1)} "
                      f"{_n(row['median_cert_usd'], 8, 1)} "
                      f"{_n(row['usd_per_asset_day'], 11, 1)} "
                      f"{_n(row['over_rung'], 8, 3)} "
                      f"{_n(cash['usd_per_day'] if cash else None, 12, 1)} "
                      f"{_n(cash['mean_minus_2se_usd'] if cash else None, 10, 1)} "
                      f"{_n(row['mdd_day_usd'], 9, 1)}")
        port = block["cash"]["_portfolio"]
        print(f"  portfolio: dates with entries {port['dates_with_entries']}, "
              f"max seats/date {port['portfolio_seats_max']}, at cap "
              f"{port['at_cap_dates']}, cap lawful {port['cap_lawful']}")
        mdd = block["mdd"]
        print("  MDD ledgers: " + ", ".join(
            f"{key} {_n(mdd[key], 8, 1)}" for key in mdd["binding_ledgers"]))
        print(f"    max binding {_n(mdd['max_binding_usd'], 9, 1)} "
              f"clears {mdd['clears']}")
        for kind in ("adversarial", "spread"):
            stress = block["stress"][kind]
            print(f"  stress {kind:<12}: seated {stress['seated']}, " + ", ".join(
                f"{asset} {_n(stress['cash'][asset]['usd_per_day'], 9, 1)} usd/day"
                for asset in DECIDING) + f", max binding MDD "
                f"{_n(stress['mdd']['max_binding_usd'], 8, 1)} "
                f"clears {stress['mdd']['clears']}")
        print(f"  neighbours agree on sign : {block['neighbours_agree']}")
        print("  NON-LETTER NEIGHBOURS:  top-k      n  seated      "
              "NKD usd/day     SI usd/day")
        for k in ALL_K:
            cell = report["neighbours"][name][str(k)]
            print(f"                          top-{k:<5} {cell['n']:>5} "
                  f"{cell['seated']:>7} "
                  f"{_n(cell['cash']['NKD']['usd_per_day'], 15, 1)} "
                  f"{_n(cell['cash']['SI']['usd_per_day'], 14, 1)}"
                  f"{'   <-- REGISTERED' if k == TOP_K else ''}")


def print_increment(report: Mapping[str, object]) -> None:
    increment = report["increment"]
    print("\n== THE TESTED OBJECT: THE GENEALOGY INCREMENT ==")
    print(f"  {increment['definition']}")
    print(f"  shared-date-sign maxT, {increment['draws']} draws over "
          f"{increment['dates']} dates, family "
          f"{increment.get('family', [])}, c95 {_n(increment['c95'], 7, 3)}")
    print(f"  {increment['event_level_p']}")
    print("  line                        dates   delta/date       SE        t  "
          " max-p    upper95   lower95")
    for name, cell in sorted(increment["by_line"].items()):
        print(f"  {name:<27} {cell['dates']:>5} "
              f"{_n(cell['delta_usd_per_date'], 12, 1)} "
              f"{_n(cell['se_usd'], 9, 1)} {_n(cell['t'], 8, 3)} "
              f"{_n(cell['p_max_adjusted'], 7, 4)} "
              f"{_n(cell['upper95_simultaneous_usd'], 10, 1)} "
              f"{_n(cell['lower95_simultaneous_usd'], 10, 1)}"
              f"{'' if cell['eligible'] else '   (HG report-only)'}")
    print("\n  WHAT THE TWO RANKERS ACTUALLY PICKED:")
    print("  asset   R_BASE events/dates   R_GEN events/dates   both   "
          "gen-only   base-only")
    for asset in ASSETS:
        base_c = report["increment_counts"]["R_BASE"][asset]
        gen_c = report["increment_counts"]["R_GEN"][asset]
        over = report["selection_overlap"][asset]
        print(f"  {asset:<5} {base_c['events']:>13}/{base_c['dates']:<5} "
              f"{gen_c['events']:>15}/{gen_c['dates']:<5} "
              f"{over['both']:>8} {over['gen_only']:>10} "
              f"{over['base_only']:>11}")
    seated = report["increment_seated"]
    print(f"\n  THE SEATED INCREMENT, beside it: {seated['note']}")
    print("  line                        dates   delta/date       SE        t  "
          " max-p    upper95   lower95")
    for name, cell in sorted(seated["by_line"].items()):
        print(f"  {name:<27} {cell['dates']:>5} "
              f"{_n(cell['delta_usd_per_date'], 12, 1)} "
              f"{_n(cell['se_usd'], 9, 1)} {_n(cell['t'], 8, 3)} "
              f"{_n(cell['p_max_adjusted'], 7, 4)} "
              f"{_n(cell['upper95_simultaneous_usd'], 10, 1)} "
              f"{_n(cell['lower95_simultaneous_usd'], 10, 1)}")


def print_controls(report: Mapping[str, object]) -> None:
    control = report["control"]
    print("\n== C1: R_GEN's PAIRED MATCHED CONTROL, complete "
          "level-plus-genealogy vector permuted in fold ==")
    print(f"  shared-date-sign maxT, {control['draws']} draws over "
          f"{control['dates']} dates, family {control.get('family', [])}, c95 "
          f"{_n(control['c95'], 7, 3)}")
    print("  line                        dates   delta/date       SE        t  "
          " max-p    upper95   lower95")
    for name, cell in sorted(control["by_line"].items()):
        print(f"  {name:<27} {cell['dates']:>5} "
              f"{_n(cell['delta_usd_per_date'], 12, 1)} "
              f"{_n(cell['se_usd'], 9, 1)} {_n(cell['t'], 8, 3)} "
              f"{_n(cell['p_max_adjusted'], 7, 4)} "
              f"{_n(cell['upper95_simultaneous_usd'], 10, 1)} "
              f"{_n(cell['lower95_simultaneous_usd'], 10, 1)}"
              f"{'' if cell['eligible'] else '   (HG report-only)'}")
    print(f"  match counters: {report['control_counters']}; pairs per asset "
          f"{report['control_pairs_per_asset']}")
    permuted = report["control_permutation"]
    print(f"  PERMUTED COMPLETE LEVEL-PLUS-GENEALOGY VECTOR inside the training "
          f"fold: {permuted['controls']} controls scored by their own fold's "
          f"ranker; share with a positive score "
          f"{_show(permuted['share_permuted_positive'])}, share that would "
          f"have made the top-{TOP_K} cut "
          f"{_show(permuted['share_permuted_top4'])} (the real selection is "
          f"{permuted['selected_positive']}/{permuted['selected_top4']} "
          f"positive by construction)")

    print("\n== C2: FORMED-OPPORTUNITY CEILING (exploratory) ==")
    print(f"  hindsight bits spent: {'; '.join(HINDSIGHT_CEILING)}")
    print("  scope                    asset      n     usd/day   over-rung "
          "carries")
    for scope in ("SELECTED", "FORMED_UNIVERSE", "FORMED_CAPPED"):
        for asset in ASSETS:
            cell = report["ceiling"][scope]["cash"][asset]
            print(f"  {scope:<24} {asset:<5} {cell['n']:>6} "
                  f"{_n(cell['usd_per_day'], 11, 1)} "
                  f"{_n(cell['over_rung'], 10, 3)} "
                  f"{_n(cell.get('carries_rung'), 8)}")

    print("\n== C3: BLOCK-PERMUTATION NULLS (information only) ==")
    print("  line                        observed usd/day   null mean    "
          "null p95      p")
    for name, cell in sorted(report["block_nulls"].items()):
        print(f"  {name:<27} {_n(cell.get('observed_usd_day'), 14, 1)} "
              f"{_n(cell.get('null_mean_usd_day'), 11, 1)} "
              f"{_n(cell.get('null_p95_usd_day'), 11, 1)} "
              f"{_n(cell.get('p'), 6, 4)}")
    print(f"\n  C3 CAVEAT: {report['block_null_caveat']}.")


def print_decision(report: Mapping[str, object]) -> None:
    head = report["headline"]
    cell = report["letter"]
    print("\n== DECISION TABLE ==")
    print("  asset   R_GEN usd/day over rung   INCREMENT/date   incr upper95   "
          "incr p   R_GEN matched delta   matched p")
    for asset in DECIDING:
        print(f"  {asset:<5} {_n(head['over_rung'].get(asset), 23, 4)}x "
              f"{_n(head['increment_usd_per_date'].get(asset), 16, 1)} "
              f"{_n(head['increment_upper95'].get(asset), 14, 1)} "
              f"{_n(head['increment_p_adjusted'].get(asset), 8, 4)} "
              f"{_n(head['matched_delta_usd_per_date'].get(asset), 20, 1)} "
              f"{_n(head['matched_p_adjusted'].get(asset), 11, 4)}")
    print("\n  gate               rung  MDD  cap  stress  control  neighbours  "
          "incr<=0  matched<=0  defined")
    print(f"  {'F23-ZONE-GENEALOGY':<18} {_n(cell['rung_ok'], 5)} "
          f"{_n(cell['mdd_ok'], 4)} {_n(cell['cap_ok'], 4)} "
          f"{_n(cell['stress_ok'], 6)} {_n(cell['control_ok'], 8)} "
          f"{_n(cell['neighbours_ok'], 11)} "
          f"{_n(cell['increment_upper_nonpositive'], 8)} "
          f"{_n(cell['matched_delta_nonpositive'], 11)} "
          f"{_n(cell['bounds_defined'], 8)}")
    print(f"\n  FAMILY LETTER: {report['family_letter']} "
          f"(clause {report['family_clause']})")
    print(f"  CLAUSE {cell['clause']}: {cell['clause_text']}")
    print(f"  clauses matching: {cell['clauses_matching']}")
    for reason in cell["reasons"]:
        print(f"    - {reason}")
    print("\n  the registered partition, exhaustive over all 512 outcome "
          "points:")
    for clause in CLAUSE_ORDER:
        print(f"    {clause:<5} -> {CLAUSE_LETTER[clause]:<22} "
              f"{CLAUSES[clause]}")

    licence = report["f24_licence"]
    print(f"\n== THE F24 LICENSING CHECK (evaluated and printed on UNRESOLVED; "
          f"a licence read, never a promotion) ==")
    print(f"  gate: {licence['gate']}")
    print(f"  R_GEN matched deltas: " + ", ".join(
        f"{asset} {_show(licence['matched_deltas'].get(asset))}"
        for asset in DECIDING)
        + f"; both deciders positive {licence['both_deciders_positive']}")
    print("  ranker   selected   seated   rejected occupancy   share   "
          "rejected cap")
    for name in RANKERS:
        occ = licence["occupancy"][name]
        print(f"  {name:<8} {occ['selected']:>8} {occ['seated']:>8} "
              f"{occ['rejected_occupancy']:>20} "
              f"{_n(occ['occupancy_share'], 7, 4)} "
              f"{occ['rejected_cap']:>14}")
    parent = licence["parent_reference"]
    print(f"  sweep 27 measured, the same way: {parent['rejected_occupancy']} "
          f"of {parent['selected']} selected events lost to occupancy "
          f"(share {parent['occupancy_share']:.4f}) - {parent['source']}")
    print(f"  F24 LICENCE: {licence['verdict']}")
    print(f"  {licence['note']}")


# --------------------------------------------------------------------------
# Selftest.
# --------------------------------------------------------------------------

def _plant_increment_world(gradient_on_prior_days: bool
                           ) -> tuple[np.ndarray, np.ndarray, np.ndarray,
                                      dict[tuple[str, int], list[int]],
                                      dict[str, list[int]]]:
    """A world in which ONLY the genealogy carries the payoff.

    THE ARITHMETIC, by hand.  One asset, ``ROWS = 10`` events on each of 31
    EXPLORE days.  On row ``j`` of a day:

        gen_held_rate = j / 10                   (0.0, 0.1, ... 0.9)
        cert          = 100 * j                  (0, 100, ... 900)

    EVERY R_BASE COLUMN IS A CONSTANT.  On any training fold each has zero
    spread, so it takes spread 1 by the registered law and standardizes to
    exactly zero; the design matrix ``R_BASE`` sees is therefore identically
    zero, ``beta`` solves ``(0 + I) b = 0`` and is exactly zero, every score is
    exactly zero, and ZERO IS NOT POSITIVE - so ``R_BASE`` selects NOTHING at
    all.  It is not that the base ranker ranks the day badly; it cannot see the
    day.  ``R_GEN`` has the same nineteen dead columns plus one live one, its
    score is strictly increasing in ``j``, and it keeps ``j = 9, 8, 7, 6`` for a
    mean payoff of 750 against a day base of 450.

    ``gradient_on_prior_days=False`` builds the INCREMENT LEAK world: every
    prior day's cert is a constant, so every prior-day target is a tie at
    percentile 0.5, the centred target is exactly zero over the whole training
    fold, ``beta`` is exactly zero for BOTH rankers, and an honest fold selects
    nothing.  The gradient exists only on the scoring day - which a fold that
    included the scoring day would read.
    """

    asset = "SI"
    rows, day_count = 10, 31
    days = [20220100 + d for d in range(day_count)]
    base = np.zeros((rows * day_count, N_BASE), np.float64)
    gen = np.zeros((rows * day_count, N_GEN), np.float64)
    cert = np.zeros(rows * day_count, np.float64)
    positions_by_day: dict[tuple[str, int], list[int]] = {}
    for index, d8 in enumerate(days):
        last = index == day_count - 1
        for j in range(rows):
            position = index * rows + j
            gen[position, GEN_FEATURES.index("gen_held_rate")] = j / 10.0
            cert[position] = (100.0 * j if (last or gradient_on_prior_days)
                              else 0.0)
            positions_by_day.setdefault((asset, d8), []).append(position)
    return base, gen, cert, positions_by_day, {asset: days}


def _selftest_increment(mutant: str) -> list[tuple[str, bool, str]]:
    """THE INCREMENT LAW: R_GEN beats R_BASE where only genealogy has payoff."""

    base, gen, cert, by_day, days = _plant_increment_world(True)
    combined = np.hstack([base, gen])
    base_folds, _r1 = S27.rank_folds(by_day, base, cert, days, mutant)
    gen_folds, _r2 = S27.rank_folds(by_day, combined, cert, days, mutant)
    out = [_check(
        "the planted increment world scores exactly the days past the 25-day "
        "warmup, for BOTH rankers",
        len(base_folds) == len(gen_folds) == 31 - MIN_PRIOR_DAYS,
        f"R_BASE {len(base_folds)} folds, R_GEN {len(gen_folds)} folds")]
    if not base_folds or not gen_folds:
        return out
    last_base, last_gen = base_folds[-1], gen_folds[-1]
    base_picks = S27.select_top(last_base, TOP_K)
    gen_picks = S27.select_top(last_gen, TOP_K)
    want = [int(last_gen.positions[i]) for i in (9, 8, 7, 6)]
    day_base = float(np.mean([cert[p] for p in last_gen.positions]))
    out.append(_check(
        "R_BASE CANNOT SEE IT: every one of its nineteen columns is constant "
        "on the fold, so its beta is exactly zero, every score is exactly zero, "
        "and a zero score is never seated",
        not base_picks and float(np.max(np.abs(last_base.beta))) == 0.0
        and float(np.max(np.abs(last_base.scores))) == 0.0,
        f"picked {base_picks}, max |beta| "
        f"{float(np.max(np.abs(last_base.beta))):.3e}, max |score| "
        f"{float(np.max(np.abs(last_base.scores))):.3e}"))
    out.append(_check(
        "R_GEN RECOVERS IT OUT OF FOLD: it keeps exactly the four "
        "highest-payoff events (j = 9, 8, 7, 6)",
        gen_picks == want,
        f"picked {[int(p) for p in gen_picks]}, wanted {want}"))
    recovered = (float(np.mean([cert[p] for p in gen_picks]))
                 if gen_picks else day_base)
    base_recovered = (float(np.mean([cert[p] for p in base_picks]))
                      if base_picks else day_base)
    out.append(_check(
        "THE INCREMENT IS THE HAND-COMPUTED 300 PER EVENT: R_GEN recovers a "
        "mean payoff of 750 against a day base of 450, and R_BASE recovers the "
        "base because it selects nothing",
        abs(recovered - 750.0) < 1e-9 and abs(base_recovered - 450.0) < 1e-9
        and abs((recovered - base_recovered) - 300.0) < 1e-9,
        f"R_GEN {recovered:.1f}, R_BASE {base_recovered:.1f}, increment "
        f"{recovered - base_recovered:.1f}"))
    out.append(_check(
        "and the increment in SELECTED CASH is positive on the scoring date, "
        "which is the quantity the letter reads",
        sum(cert[p] for p in gen_picks) - sum(cert[p] for p in base_picks)
        == 3000.0,
        f"{sum(cert[p] for p in gen_picks)} - "
        f"{sum(cert[p] for p in base_picks)}"))
    out.append(_check(
        "R_GEN's out-of-fold rank correlation with the day's own cert "
        "percentile is exactly +1 while R_BASE's is undefined (a flat score "
        "has no ordering at all)",
        last_gen.rank_corr is not None
        and abs(float(last_gen.rank_corr) - 1.0) < 1e-9
        and last_base.rank_corr is None,
        f"R_GEN rho {last_gen.rank_corr}, R_BASE rho {last_base.rank_corr}"))
    out.append(_check(
        "R_GEN extends R_BASE IN PLACE: the first nineteen columns of the "
        "combined matrix are R_BASE's own, untouched",
        bool(np.array_equal(combined[:, :N_BASE], base))
        and combined.shape[1] == N_ALL,
        f"{combined.shape} = {base.shape} + {gen.shape}"))
    return out


def _selftest_increment_leak(mutant: str) -> list[tuple[str, bool, str]]:
    """The leak guard on the increment: a gradient only on the scoring day."""

    base, gen, cert, by_day, days = _plant_increment_world(False)
    combined = np.hstack([base, gen])
    gen_folds, _r = S27.rank_folds(by_day, combined, cert, days, mutant)
    if not gen_folds:
        return [_check("THE INCREMENT LEAK GUARD: a world whose genealogy "
                       "gradient exists ONLY on the scoring day yields NO "
                       "out-of-fold recovery", False, "no fold was scored")]
    last = gen_folds[-1]
    picked = S27.select_top(last, TOP_K)
    day_base = float(np.mean([cert[p] for p in last.positions]))
    recovered = float(np.mean([cert[p] for p in picked])) if picked else day_base
    return [_check(
        "THE INCREMENT LEAK GUARD: a world whose genealogy gradient exists "
        "ONLY on the scoring day yields NO out-of-fold recovery",
        not picked and recovered <= day_base + 1e-9,
        f"{len(picked)} picked, mean {recovered:.1f} vs day base "
        f"{day_base:.1f}")]


def _selftest_feature_law() -> list[tuple[str, bool, str]]:
    out: list[tuple[str, bool, str]] = []
    try:
        assert_feature_law()
        ok, detail = True, f"{N_BASE} + {N_GEN} = {N_ALL} columns"
    except SweepRefusal as error:
        ok, detail = False, str(error)
    out.append(_check(
        "the two rosters are lawful: R_BASE is sweep 27's row by value, R_GEN "
        "extends it in place, and every store field is consumed or registered "
        "as excluded",
        ok, detail))
    out.append(_check(
        "R_BASE IS sweep 27's feature row, not a copy of it",
        BASE_FEATURES == tuple(S27.FEATURE_NAMES) and N_BASE == S27.NFEAT,
        f"{N_BASE} columns from sweep27.FEATURE_NAMES"))
    out.append(_check(
        "the genealogy block adds exactly the seven registered fields and "
        "names no outcome token",
        len(GEN_FEATURES) == 7 and not set(GEN_FEATURES) & set(BASE_FEATURES),
        f"{list(GEN_FEATURES)}"))
    out.append(_check(
        "the raw event list and every band identity are EXCLUDED by "
        "registration: the ranker sees derived order statistics, never a price "
        "level or an absolute stamp",
        {"events", "band", "band_lo", "band_hi", "band_center", "step"}
        <= set(EXCLUDED_HISTORY_FIELDS)))
    out.append(_check(
        "the ranker law constants are sweep 27's own, by value",
        (RIDGE_LAMBDA, TOP_K, tuple(NEIGHBOUR_K), MIN_PRIOR_DAYS)
        == (S27.RIDGE_LAMBDA, S27.TOP_K, tuple(S27.NEIGHBOUR_K),
            S25.MIN_PRIOR_DAYS),
        f"lambda {RIDGE_LAMBDA}, top {TOP_K}, neighbours {list(NEIGHBOUR_K)}"))
    out.append(_check(
        "the genealogy grid warmup IS the ranker's warmup, so the band grid is "
        "fixed before the first scored session",
        ZH.GRID_WARMUP_DAYS == MIN_PRIOR_DAYS,
        f"{ZH.GRID_WARMUP_DAYS} == {MIN_PRIOR_DAYS}"))
    return out


def _selftest_increment_pairing() -> list[tuple[str, bool, str]]:
    """The pairing law, on a constructed two-date world."""

    cand = S23.Cand(
        asset="NKD", d8=20220301, phase="RTH", cell=0, year=2022,
        zone_kind="PD_HIGH", zone_price=100.0, width=25.0, atr_mid2=250.0,
        break_dir=1, defence_side=-1, broken_edge=125.0, bar=30, read_bar=29,
        n_bars=300, pull_frac=0.0, pull_dur=1, ext_reach=0.0,
        lev_read=np.zeros(len(LV.LEVEL_FEATURES)), pd_held=0.0, pd_broke=0.0,
        defence_history=0.0, visit_bars=0, visit_touches=0, visit_flow=0.0)
    import copy
    cands = []
    for offset, (d8, asset) in enumerate(
            [(20220301, "NKD"), (20220301, "NKD"), (20220302, "NKD"),
             (20220301, "SI")]):
        made = copy.copy(cand)
        made.d8, made.asset = d8, asset
        cands.append(made)

    class _P:
        def __init__(self, value):
            self.cert = {CLOSE: float(value), FIXED: float(value)}
    entries = {0: _P(100.0), 1: _P(50.0), 2: _P(-30.0), 3: _P(900.0)}
    scoring = {"NKD": [20220301, 20220302, 20220303], "SI": [20220301],
               "HG": []}
    lines = increment_lines({"R_GEN": [0, 1, 2, 3], "R_BASE": [1]}, entries,
                            cands, scoring)
    nkd = lines[f"{LANE}|NKD"]
    out = [_check(
        "the increment is R_GEN's selected cash minus R_BASE's, summed inside "
        "each date: 20220301 is (100+50) - 50 = 100, 20220302 is -30 - 0 = -30",
        nkd.get(20220301) == 100.0 and nkd.get(20220302) == -30.0,
        f"{ {k: v for k, v in sorted(nkd.items())} }")]
    out.append(_check(
        "EVERY SCORED DATE IS CARRIED, including one on which neither ranker "
        "selected anything: dropping those would keep only the dates where the "
        "two rankers agree",
        20220303 in nkd and nkd[20220303] == 0.0,
        f"20220303 -> {nkd.get(20220303)}"))
    out.append(_check(
        "a date on which only R_GEN selected contributes its whole cash, which "
        "is exactly the evidence the increment prices",
        nkd[20220302] == -30.0))
    out.append(_check(
        "the lines are per asset: SI's 900 never reaches NKD's series",
        lines[f"{LANE}|SI"].get(20220301) == 900.0
        and 900.0 not in nkd.values(),
        f"SI {lines[f'{LANE}|SI']}"))
    out.append(_check(
        "the increment of a ranker against ITSELF is identically zero on every "
        "date, which is the null the maxT family is read against",
        all(v == 0.0 for v in increment_lines(
            {"R_GEN": [0, 1, 2], "R_BASE": [0, 1, 2]}, entries, cands,
            scoring)[f"{LANE}|NKD"].values())))
    return out


def _receipt(usd: float, mdd: float, p: float, delta: float | None,
             upper: float | None) -> dict[str, object]:
    cash = {asset: {"usd_per_day": usd, "mean_minus_2se_usd": usd - 10.0,
                    "clears_rung": usd - 10.0 >= DAY_RUNG_USD[asset]}
            for asset in ASSETS}
    cash["_portfolio"] = {"cap_lawful": True}
    stress = {kind: {"mdd": {"clears": mdd < MDD_CEILING}}
              for kind in ("adversarial", "spread")}
    return {
        "live": {"cash": cash,
                 "mdd": {"clears": mdd < MDD_CEILING, "max_binding_usd": mdd},
                 "stress": stress, "neighbours_agree": True},
        "control": {"by_line": {
            f"{LANE}|{asset}": {"p_max_adjusted": p,
                                "delta_usd_per_date": delta}
            for asset in ASSETS}},
        "increment": {"by_line": {
            f"{LANE}|{asset}": {"upper95_simultaneous_usd": upper,
                                "delta_usd_per_date": (None if upper is None
                                                       else upper - 50.0)}
            for asset in ASSETS}},
        "by_ranker": {name: {"n": 100, "replay": {
            "seated": 80, "rejected_occupancy": 20, "rejected_cap": 0}}
            for name in RANKERS}}


def _selftest_letters() -> list[tuple[str, bool, str]]:
    """Every clause fires on a constructed receipt, and the partition is total."""

    cases = [
        ("LIVE", LETTER_LIVE, _receipt(3000.0, 100.0, 0.01, 300.0, 400.0)),
        ("K1", LETTER_KILL, _receipt(100.0, 100.0, 0.20, 300.0, -10.0)),
        ("K2", LETTER_KILL, _receipt(100.0, 100.0, 0.20, -300.0, 400.0)),
        ("U1", LETTER_UNRESOLVED, _receipt(100.0, 100.0, 0.20, 300.0, 400.0)),
        ("U0", LETTER_UNRESOLVED, _receipt(100.0, 100.0, 0.20, 300.0, None)),
    ]
    out: list[tuple[str, bool, str]] = []
    for clause, letter, receipt in cases:
        got = family_letter(receipt)
        out.append(_check(
            f"the constructed {clause} receipt fires {clause}",
            got["clause"] == clause and got["letter"] == letter,
            f"got {got['letter']} / {got['clause']}"))
    out.append(_check(
        "a breached MDD cannot be LIVE",
        family_letter(_receipt(3000.0, 5000.0, 0.01, 300.0, 400.0)
                      )["letter"] != LETTER_LIVE))
    out.append(_check(
        "an R_GEN control p above 0.05 cannot be LIVE",
        family_letter(_receipt(3000.0, 100.0, 0.20, 300.0, 400.0)
                      )["letter"] != LETTER_LIVE))
    out.append(_check(
        "A NON-POSITIVE INCREMENT UPPER BOUND KILLS EVEN WHEN THE DECIDING "
        "CASH CLEARS ITS RUNG: the tested object is the genealogy, not the "
        "level, so a rich lane whose increment cannot be shown positive still "
        "dies at K1",
        family_letter(_receipt(3000.0, 100.0, 0.20, 300.0, -10.0)
                      )["clause"] == "K1",
        "rung clears, control p 0.20 so the live bounds fail, increment "
        "upper95 -10"))
    out.append(_check(
        "THE REGISTERED PRECEDENCE, LIVE > K1: a receipt that clears EVERY "
        "live bound is NOT killed by a flat increment.  Sol states LIVE as a "
        "property of R_GEN, unconditional on the increment, and a kill-only "
        "charter must not kill a policy that clears every live bound - the "
        "honest reading of that receipt is that the POLICY lives while the "
        "genealogy earned nothing, which is a licensing question and not a "
        "kill",
        family_letter(_receipt(3000.0, 100.0, 0.01, 300.0, -10.0)
                      )["clause"] == "LIVE"
        and family_letter(_receipt(3000.0, 100.0, 0.01, 300.0, -10.0)
                          )["clauses_matching"] == ["LIVE", "K1"],
        "the receipt matches BOTH LIVE and K1 and the precedence resolves it "
        "to LIVE, with K1 recorded beside it"))
    out.append(_check(
        "THE KILL IS NARROW, as the charter requires: an undefined bound is "
        "parked UNRESOLVED at clause U0 and never killed",
        family_letter(_receipt(100.0, 100.0, 0.20, None, None)
                      )["letter"] == LETTER_UNRESOLVED))
    seen: dict[str, int] = {}
    total = 0
    for bits in itertools.product((False, True), repeat=9):
        letter, clause, matching = classify(*bits)
        total += 1
        if clause not in CLAUSE_ORDER or CLAUSE_LETTER[clause] != letter:
            return out + [_check("the letter partition covers every outcome",
                                 False, f"bad mapping at {bits}")]
        if not matching or clause != next(c for c in CLAUSE_ORDER
                                          if c in matching):
            return out + [_check("the letter partition covers every outcome",
                                 False, f"precedence violated at {bits}")]
        seen[clause] = seen.get(clause, 0) + 1
    out.append(_check(
        "every one of the 512 outcome points maps to exactly one letter and "
        "clause, with no fallthrough",
        total == 512 and sum(seen.values()) == 512, f"{seen}"))
    out.append(_check("all five registered clauses are reachable",
                      set(seen) == set(CLAUSE_ORDER), f"{sorted(seen)}"))
    kills = 0
    for bits in itertools.product((False, True), repeat=9):
        _letter, clause, _m = classify(*bits)
        if clause in ("K1", "K2"):
            kills += 1
            if not (bits[6] or bits[7]):
                return out + [_check("the kill surface is exactly the "
                                     "charter's two clauses", False,
                                     f"at {bits}")]
    out.append(_check(
        "the kill surface is EXACTLY the charter's two clauses: a non-positive "
        "increment upper bound on either decider, or an R_GEN matched delta "
        "that is zero or negative",
        kills == seen.get("K1", 0) + seen.get("K2", 0), f"{kills} kill points"))
    return out


def _selftest_f24() -> list[tuple[str, bool, str]]:
    """The licence read, on constructed receipts.  It never promotes anything."""

    positive = _receipt(100.0, 100.0, 0.20, 300.0, 400.0)
    positive["by_ranker"]["R_GEN"]["replay"]["rejected_occupancy"] = 20
    got = f24_licence(positive)
    out = [_check(
        "the F24 gate is LICENSED when both deciding matched deltas are "
        "positive and the lane loses seats to occupancy",
        got["licensed"] and got["both_deciders_positive"]
        and abs(float(got["occupancy"]["R_GEN"]["occupancy_share"]) - 0.20)
        < 1e-12,
        f"licensed {got['licensed']}, share "
        f"{got['occupancy']['R_GEN']['occupancy_share']}")]
    negative = _receipt(100.0, 100.0, 0.20, -300.0, 400.0)
    out.append(_check(
        "and NOT LICENSED when a deciding matched delta is not positive, "
        "which is the charter's own condition",
        not f24_licence(negative)["licensed"]))
    idle = _receipt(100.0, 100.0, 0.20, 300.0, 400.0)
    for name in RANKERS:
        idle["by_ranker"][name]["replay"]["rejected_occupancy"] = 0
    out.append(_check(
        "and NOT LICENSED when nothing is lost to occupancy, however good the "
        "deltas look",
        not f24_licence(idle)["licensed"]))
    out.append(_check(
        "the licence carries sweep 27's own measured 150 of 468 beside this "
        "lane's number, so the two are read the same way",
        f24_licence(positive)["parent_reference"]["rejected_occupancy"] == 150
        and f24_licence(positive)["parent_reference"]["selected"] == 468))
    return out


EXPECTED_RED = {
    MUTANT_TESTDAY: (
        "THE LEAK GUARD: a world whose gradient exists ONLY on the scoring day "
        "yields NO out-of-fold recovery",
        "THE INCREMENT LEAK GUARD: a world whose genealogy gradient exists "
        "ONLY on the scoring day yields NO out-of-fold recovery"),
    MUTANT_CURRENT_DAY: (
        "A STRICT-TIME CHECK: a query made DURING session C is served only by "
        "sessions A and B, and never by C's own events",
        "every served event's own stamp is strictly before the decision stamp",
        "the FIRST session has no genealogy at all: there is nothing earlier "
        "to serve it, and that is an empty history rather than a zero",
        "the eligible session count grows by one per elapsed session",
        "THE LICENSED PRIOR-SESSION LAW: an earlier session whose last bar "
        "closed at or after the decision stamp is NOT served, exactly as "
        "levels_zone refuses it"),
}


def selftest() -> int:
    mutant = arm_mutant(_mutant())
    results: list[tuple[str, bool, str]] = []
    results += _selftest_feature_law()
    results += _selftest_increment(mutant)
    results += _selftest_increment_leak(mutant)
    results += _selftest_increment_pairing()
    results += _selftest_letters()
    results += _selftest_f24()
    # The store's own fixtures: the planted three-session genealogy, the
    # same-band re-query identity check and the strict-time check.
    results += ZH._selftest_grid()
    results += ZH._selftest_direction()
    results += ZH._selftest_plant(ZH._mutant())
    results += ZH._selftest_strict_time(ZH._mutant())
    results += ZH._selftest_prefix()
    results += ZH._selftest_law_matches_accessor()
    # Sweep 27's percentile-target, top-four, centre-equality and leak
    # fixtures, reused unchanged.
    results += S27._selftest_percentile()
    results += S27._selftest_top_k()
    results += S27._selftest_ridge()
    results += S27._selftest_leak(mutant)
    results += S27._selftest_planted_read()
    # The replay, MDD, stress and formation fixtures.
    results += S22._selftest_replay()
    results += S22._selftest_stress()
    results += S23._selftest_formation()
    print(f"sweep 28 selftest  mutant={mutant or 'none'}")
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
        "rankers": list(RANKERS),
        "tested_object": "the paired genealogy INCREMENT: R_GEN selected cash "
                         "minus R_BASE selected cash by shared calendar date",
        "base_features": list(BASE_FEATURES), "n_base": N_BASE,
        "genealogy_features": list(GEN_FEATURES), "n_gen": N_GEN,
        "n_features": N_ALL,
        "store": {"key": "(asset, floor(price / step))",
                  "band_atr_mult": ZH.BAND_ATR_MULT,
                  "grid_warmup_days": ZH.GRID_WARMUP_DAYS,
                  "events": list(ZH.EVENT_KINDS),
                  "reading_side": ZH.READING_SIDE},
        "target": "within-asset-day percentile of the frozen cert",
        "weights": "each asset-day equal",
        "ridge_lambda": RIDGE_LAMBDA, "top_k": TOP_K,
        "neighbour_k": list(NEIGHBOUR_K),
        "min_prior_days": MIN_PRIOR_DAYS, "min_train_rows": MIN_TRAIN_ROWS,
        "portfolio_cap": PORTFOLIO_CAP, "impulse_horizon_s": IMPULSE_HORIZON_S,
        "sign_draws": SIGN_DRAWS, "control_draws": CONTROL_DRAWS,
        "clauses": list(CLAUSE_ORDER),
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

    # 1. the store build and its gates
    counter += 1
    build = report["store_build"]
    audit = report["store_audit"]["counters"]
    gen = report["genealogy_read"]["counters"]
    line = blank(dict(shared))
    line["id"] = f"{LOG_PREFIX}-{counter:03d}"
    line["rule"] = "store/zone-history"
    line["days"] = int(build["counters"]["sessions"])
    line["note"] = (
        f"THE ZONE GENEALOGY STORE, built and gated BEFORE any cash: "
        f"{build['counters']['sessions']} EXPLORE sessions in causal order over "
        f"{build['counters']['bands_touched']} ATR-scaled bands keyed "
        f"floor(price / {ZH.BAND_ATR_MULT} * atr_ref) with atr_ref the median "
        f"prior-day ATR14 over the first {ZH.GRID_WARMUP_DAYS} EXPLORE sessions "
        f"(the ranker's own warmup, so the grid is fixed before the first "
        f"scored session); ordered events TOUCH {build['counters']['touch']}, "
        f"HELD {build['counters']['held']}, BROKE {build['counters']['broke']}, "
        f"ROLE-FLIP {build['counters']['flip']}, unresolved "
        f"{build['counters']['unresolved']}; GATES over "
        f"{audit['queries']} real sweep-25 candidates: identity contains price "
        f"{audit['identity_contains_price']}/{audit['queries']}, same key at "
        f"every stamp {audit['identity_key_stable']}/{audit['queries']}, strict "
        f"time {audit['strict_time_ok']}/{audit['queries']} (violations "
        f"{audit['strict_time_violations']}, current-day "
        f"{audit['current_day_events']}); re-gated over this unit's own "
        f"{gen['queried']} queries with {gen['strict_time_violations']} "
        f"violations; HOLD SEALED")
    rows.append(line)

    # 2. the registered selection, per ranker x label x asset
    for name in RANKERS:
        block = report["by_ranker"][name]
        for label in LABELS:
            for asset in ASSETS:
                counter += 1
                line = blank(dict(shared))
                cell = block["per_asset"][asset][label]
                cash = block["cash"][asset]
                line["id"] = f"{LOG_PREFIX}-{counter:03d}"
                line["rule"] = f"{name}/top{TOP_K}/{label}/{asset}"
                line["days"] = cell["days"]
                line["coverage"] = cell["coverage"]
                tag = asset.lower()
                line[f"{tag}_usd_day"] = cell["usd_per_asset_day"]
                line[f"mdd_{tag}"] = cell["mdd_day_usd"]
                line[f"walls_{tag}"] = cell["wall_rate"]
                line["replay_skips"] = (block["replay"]["rejected_occupancy"]
                                        + block["replay"]["rejected_cap"])
                line["note"] = (
                    f"{name} SELECTION, top-{TOP_K} positive-score events per "
                    f"out-of-fold asset-day on the {LANE} lane, label {label}, "
                    f"{asset}: n {cell['n']} of {cell['formed']} formed, "
                    f"coverage {_show(cell['coverage'])}, mean "
                    f"{_show(cell['mean_cert_usd'])} median "
                    f"{_show(cell['median_cert_usd'])}, P(cert>0) "
                    f"{_show(cell['p_cert_positive']['rate'])}, usd/day "
                    f"{_show(cell['usd_per_asset_day'])} = "
                    f"{_show(cell['over_rung'])} rung; seated replay "
                    f"{_show(cash['usd_per_day'])} usd/day, mean-2SE "
                    f"{_show(cash['mean_minus_2se_usd'])}, clears rung "
                    f"{cash['clears_rung']}; max binding MDD "
                    f"{_show(block['mdd']['max_binding_usd'])} clears "
                    f"{block['mdd']['clears']}; neighbours agree "
                    f"{block['neighbours_agree']}; "
                    f"{N_ALL if name == 'R_GEN' else N_BASE} columns "
                    f"({'19 fixed-zone components plus 7 ordered-genealogy '
                        'fields' if name == 'R_GEN' else
                        "sweep 27's 19 fixed-zone components, by value"})")
                rows.append(line)

    # 3. the neighbours, per ranker
    for name in RANKERS:
        for k in ALL_K:
            counter += 1
            cell = report["neighbours"][name][str(k)]
            line = blank(dict(shared))
            line["id"] = f"{LOG_PREFIX}-{counter:03d}"
            line["rule"] = f"{name}/neighbour/top{k}"
            line["days"] = days_scored
            for asset in ASSETS:
                line[f"{asset.lower()}_usd_day"] = cell["cash"][asset][
                    "usd_per_day"]
            line["note"] = (
                f"COVERAGE NEIGHBOUR {name} top-{k} per out-of-fold asset-day: "
                f"n {cell['n']}, seated {cell['seated']}; " + "; ".join(
                    f"{asset} {_show(cell['cash'][asset]['usd_per_day'])} "
                    f"usd/day, -2SE "
                    f"{_show(cell['cash'][asset]['mean_minus_2se_usd'])}"
                    for asset in ASSETS)
                + ("; REGISTERED CELL, coverage set by the twelve-entry seat "
                   "budget and never by cash" if k == TOP_K
                   else "; NON-LETTER NEIGHBOUR, sign-flip check only"))
            rows.append(line)

    # 4. THE TESTED OBJECT: the increment, per line
    for name, cell in sorted(report["increment"]["by_line"].items()):
        counter += 1
        _lane, asset = name.split("|")
        line = blank(dict(shared))
        line["id"] = f"{LOG_PREFIX}-{counter:03d}"
        line["rule"] = f"increment/{asset}"
        line["days"] = cell["dates"]
        line[f"{asset.lower()}_usd_day"] = cell["delta_usd_per_date"]
        line["null_margin"] = cell["p_max_adjusted"]
        line["note"] = (
            f"THE TESTED OBJECT, THE GENEALOGY INCREMENT, {asset}: R_GEN "
            f"selected cash minus R_BASE selected cash "
            f"{_show(cell['delta_usd_per_date'])} usd per shared calendar date "
            f"over {cell['dates']} dates, SE {_show(cell['se_usd'])}, t "
            f"{_show(cell['t'])}, shared-date-sign max-stat p "
            f"{_show(cell['p_max_adjusted'])} over "
            f"{len(report['increment'].get('family', []))} lines (2 deciding "
            f"assets), simultaneous 95% "
            f"[{_show(cell['lower95_simultaneous_usd'])}, "
            f"{_show(cell['upper95_simultaneous_usd'])}]; both rankers see the "
            f"SAME candidates, lane, folds, target and penalty, so the "
            f"difference is the ordered cross-day history and nothing else; "
            f"event-level p-values forbidden and not computed"
            f"{'' if cell['eligible'] else '; HG report-only'}")
        rows.append(line)

    # 5. the seated increment, information only
    for name, cell in sorted(report["increment_seated"]["by_line"].items()):
        counter += 1
        _lane, asset = name.split("|")
        line = blank(dict(shared))
        line["id"] = f"{LOG_PREFIX}-{counter:03d}"
        line["rule"] = f"increment-seated/{asset}"
        line["days"] = cell["dates"]
        line[f"{asset.lower()}_usd_day"] = cell["delta_usd_per_date"]
        line["null_margin"] = cell["p_max_adjusted"]
        line["note"] = (
            f"THE SEATED INCREMENT, INFORMATION ONLY and carrying no letter, "
            f"{asset}: R_GEN seated cash minus R_BASE seated cash "
            f"{_show(cell['delta_usd_per_date'])} usd per date over "
            f"{cell['dates']} dates, t {_show(cell['t'])}, p "
            f"{_show(cell['p_max_adjusted'])}, simultaneous 95% "
            f"[{_show(cell['lower95_simultaneous_usd'])}, "
            f"{_show(cell['upper95_simultaneous_usd'])}]; it moves with seat "
            f"contention, which the two rankers share but do not share "
            f"equally, so it is not the clean paired object")
        rows.append(line)

    # 6. C1, R_GEN's matched control
    for name, cell in sorted(report["control"]["by_line"].items()):
        counter += 1
        _lane, asset = name.split("|")
        line = blank(dict(shared))
        line["id"] = f"{LOG_PREFIX}-{counter:03d}"
        line["rule"] = f"control/{asset}"
        line["days"] = cell["dates"]
        line[f"{asset.lower()}_usd_day"] = cell["delta_usd_per_date"]
        line["null_margin"] = cell["p_max_adjusted"]
        line["note"] = (
            f"C1 R_GEN paired matched control, complete level-plus-genealogy "
            f"vector permuted inside the training fold, {asset}: selected minus "
            f"control {_show(cell['delta_usd_per_date'])} usd per asset-day "
            f"over {cell['dates']} shared dates, SE {_show(cell['se_usd'])}, t "
            f"{_show(cell['t'])}, shared-date-sign max-stat p "
            f"{_show(cell['p_max_adjusted'])}, simultaneous 95% "
            f"[{_show(cell['lower95_simultaneous_usd'])}, "
            f"{_show(cell['upper95_simultaneous_usd'])}]; event-level p-values "
            f"forbidden and not computed"
            f"{'' if cell['eligible'] else '; HG report-only'}")
        rows.append(line)

    # 7. C2, the formed ceiling
    for scope in ("SELECTED", "FORMED_UNIVERSE", "FORMED_CAPPED"):
        counter += 1
        cash = report["ceiling"][scope]["cash"]
        bits = report["ceiling"][scope]["hindsight_bits"]
        line = blank(dict(shared))
        line["id"] = f"{LOG_PREFIX}-{counter:03d}"
        line["rule"] = f"{scope}/ceiling"
        line["days"] = days_scored
        for asset in ASSETS:
            line[f"{asset.lower()}_usd_day"] = cash[asset]["usd_per_day"]
        line["note"] = (
            f"C2 formed-opportunity ceiling, {scope}: " + "; ".join(
                f"{asset} {_show(cash[asset]['usd_per_day'])} usd/day = "
                f"{_show(cash[asset]['over_rung'])} rung over "
                f"{cash[asset]['n']} opportunities, carries rung "
                f"{cash[asset].get('carries_rung')}" for asset in ASSETS)
            + f"; EXPLORATORY, hindsight bits {len(bits)} ({'; '.join(bits)})")
        rows.append(line)

    # 8. the ranker diagnostics, per ranker per asset
    for name in RANKERS:
        for asset in ASSETS:
            counter += 1
            cell = report["ranker_diagnostics"][name][asset]
            line = blank(dict(shared))
            line["id"] = f"{LOG_PREFIX}-{counter:03d}"
            line["rule"] = f"ranker/{name}/{asset}"
            line["days"] = cell["folds"]
            line["null_margin"] = cell["oof_rank_corr_mean"]
            line["note"] = (
                f"RANKER DIAGNOSTIC {name} {asset}: {cell['folds']} "
                f"out-of-fold asset-days, OOF rank correlation of the score "
                f"with the day's own frozen-cert percentile mean "
                f"{_show(cell['oof_rank_corr_mean'])}, median "
                f"{_show(cell['oof_rank_corr_median'])}, share positive "
                f"{_show(cell['oof_rank_corr_p_positive'])}; mean training rows "
                f"{_show(cell['train_rows_mean'])}, rows scored "
                f"{cell['scored_rows']}, mean |beta| "
                f"{_show(cell['beta_l2_mean'])}; asset-specific ridge through "
                f"sweep27.rank_folds, lambda={RIDGE_LAMBDA} fixed, "
                f"{N_ALL if name == 'R_GEN' else N_BASE} columns, no model or "
                f"penalty search")
            rows.append(line)

    # 9. the vector permutation
    counter += 1
    permuted = report["control_permutation"]
    line = blank(dict(shared))
    line["id"] = f"{LOG_PREFIX}-{counter:03d}"
    line["rule"] = "control/vector-permutation"
    line["days"] = days_scored
    line["null_margin"] = permuted.get("share_permuted_positive")
    line["note"] = (
        f"PERMUTED COMPLETE LEVEL-PLUS-GENEALOGY VECTOR inside the training "
        f"fold: {permuted['controls']} matched controls handed a whole "
        f"{N_ALL}-column feature row drawn from a permutation of their own fold "
        f"and scored by that fold's own ranker; share with a positive score "
        f"{_show(permuted.get('share_permuted_positive'))}, share that would "
        f"have made the top-{TOP_K} cut "
        f"{_show(permuted.get('share_permuted_top4'))}; the real selection is "
        f"positive by construction "
        f"({permuted['selected_positive']}/{permuted['selected_top4']})")
    rows.append(line)

    # 10. the F24 licence read
    counter += 1
    licence = report["f24_licence"]
    line = blank(dict(shared))
    line["id"] = f"{LOG_PREFIX}-{counter:03d}"
    line["rule"] = "F24/licence-check"
    line["days"] = days_scored
    occ = licence["occupancy"]["R_GEN"]
    line["replay_skips"] = occ["rejected_occupancy"]
    line["note"] = (
        f"F24 LICENSING CHECK, evaluated and printed on UNRESOLVED: "
        f"{licence['gate']} R_GEN matched deltas " + ", ".join(
            f"{asset} {_show(licence['matched_deltas'].get(asset))}"
            for asset in DECIDING)
        + f"; both deciders positive {licence['both_deciders_positive']}; "
          f"occupancy loss R_GEN {occ['rejected_occupancy']} of "
          f"{occ['selected']} selected (share "
          f"{_show(occ['occupancy_share'])}), R_BASE "
          f"{licence['occupancy']['R_BASE']['rejected_occupancy']} of "
          f"{licence['occupancy']['R_BASE']['selected']} (share "
          f"{_show(licence['occupancy']['R_BASE']['occupancy_share'])}); "
          f"sweep 27 measured 150 of 468 (share 0.3205) the same way; "
          f"{licence['verdict']}; {licence['note']}")
    rows.append(line)

    # 11. the letter
    counter += 1
    cell = report["letter"]
    head = report["headline"]
    line = blank(dict(shared))
    line["id"] = f"{LOG_PREFIX}-{counter:03d}"
    line["rule"] = f"{FAMILY}/family"
    line["days"] = days_scored
    for asset in DECIDING:
        line[f"{asset.lower()}_usd_day"] = report["live"]["cash"][asset][
            "usd_per_day"]
    line["note"] = (
        f"FAMILY LETTER {report['family_letter']} (clause "
        f"{report['family_clause']}): R_GEN deciding usd/day over rung "
        + ", ".join(f"{asset} {_show(head['over_rung'].get(asset))}x"
                    for asset in DECIDING)
        + "; GENEALOGY INCREMENT " + ", ".join(
            f"{asset} {_show(head['increment_usd_per_date'].get(asset))} "
            f"usd/date at adjusted p "
            f"{_show(head['increment_p_adjusted'].get(asset))}, upper95 "
            f"{_show(head['increment_upper95'].get(asset))}"
            for asset in DECIDING)
        + "; R_GEN matched delta " + ", ".join(
            f"{asset} {_show(head['matched_delta_usd_per_date'].get(asset))} "
            f"usd/date at adjusted p "
            f"{_show(head['matched_p_adjusted'].get(asset))}"
            for asset in DECIDING)
        + "; formed ceiling " + ", ".join(
            f"{asset} {_show(head['formed_ceiling_over_rung'].get(asset))}x"
            for asset in DECIDING)
        + "; capped ceiling " + ", ".join(
            f"{asset} {_show(head['capped_ceiling_over_rung'].get(asset))}x"
            for asset in DECIDING)
        + f"; rung {cell['rung_ok']}, MDD {cell['mdd_ok']}, cap "
          f"{cell['cap_ok']}, stress {cell['stress_ok']}, control "
          f"{cell['control_ok']}, neighbours {cell['neighbours_ok']}, "
          f"increment upper non-positive "
          f"{cell['increment_upper_nonpositive']}, matched delta non-positive "
          f"{cell['matched_delta_nonpositive']}, bounds defined "
          f"{cell['bounds_defined']}; CLAUSE {cell['clause']} = "
          f"{cell['clause_text']}; clauses matching {cell['clauses_matching']}"
        + ("; " + "; ".join(cell["reasons"]) if cell["reasons"] else "")
        + "; EXPLORE-only, kill-only, no promotion")
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
    parser.add_argument("--log", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    report = run()
    print_summary(report)
    print_gate(report)
    print_store(report)
    print_features(report)
    print_rankers(report)
    print_selection(report)
    print_increment(report)
    print_controls(report)
    print_decision(report)
    print(f"\nWHY THE INCREMENT AND NOT THE LEVEL\n"
          f"  {report['increment_note']}")
    print(f"\nWHAT ORDER BUYS\n  {report['order_note']}")
    print(f"\nREGISTERED ENUMERATION DISCLOSURE\n  {report['residual_note']}")
    print(f"\nSELECTOR SIGN NOTE (sweep 23's, carried verbatim)\n"
          f"  {report['selector_sign_note']}")
    print(f"\nCONTAMINATION NOTE (sweep 25's, carried verbatim)\n"
          f"  {report['contamination_note']}")
    write_report(report)
    print(f"\nreport: {OUT_PATH}")
    if args.log:
        rows = log_rows(report)
        written = S1.append_log(rows)
        print(f"log: appended {written} rows to {LOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
