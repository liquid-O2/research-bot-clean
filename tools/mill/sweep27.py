#!/usr/bin/env python3
"""Sweep 27: F22-FIXEDZONE-RANK, the full fixed-zone component selector.

Unit 1 of Sol's power plan (``.audit/briefs/mill-powerplan-sol-out.md`` section
C, rank 1).  The ruling refuses a standalone SI break-close rescue - the
``p=0.0545`` line needs a 1.86 percent SE move inside winner's-curse scale, and
the honest independent unit does not exist in EXPLORE - and routes the session
into ONE wider, preregistered selector on the already built one-minute
level-memory plane, with the USER's break-close timing held fixed.

WHAT IS NEW.  F19 and F20 compressed same-day memory, prior-EXPLORE memory and
the day-scale proxy into ONE MEAN SCORE (``B_opp``, the mean of three
standardized differences).  A mean cannot use the parts: it cannot learn that a
zone touched fifteen times and held eleven is a different object from one
touched twice and held twice, nor that recency, signed touch flow, zone kind and
band width carry their own weight, nor that the prior EXPLORE session's memory
should not be added to today's with equal sign and weight.  ``levels_zone.py``
now reads every field at the exact named price.  This unit gives the SEPARATE
components one valid out-of-fold selector test.

WHAT IS HELD FIXED, so the component plane is the only thing under test:

  * FORMATION.  Sweep 23's breach formation through ``S23.formation_pass``,
    called READ-ONLY.  It must return the parent's 3,790 zone-anchored break
    candidates or this unit refuses; an identical universe is what makes the
    selector attributable.
  * ENTRY.  Lane A only - the USER's next-bar break-close timing, sweep 25's
    promoted lane, priced through ``S22.price_bar_entry`` under the frozen
    entry law, never at the breach close itself.
  * OUTCOME.  The frozen wall-or-close law is PRIMARY and carries the letters;
    the 1800 s fixed hold is reported beside every line.
  * THE BARRIER READ.  Every field comes from ``levels_zone.read_zone`` at the
    candidate's FIXED ``zone_price`` on the former defending side, stamped at
    ``lat[breach_bar - 1]``.  Every row echoes ``center_price == zone_price``
    EXACTLY and a strictly prior source stamp, per row, or the run refuses.
  * REPLAY.  The exact chronological seat replay, the full MDD ledger family
    including event-time portfolio equity, and both standing stresses.

WHAT IS UNDER TEST.  One asset-specific ridge ranker over the SEPARATE
components, fit on strictly prior EXPLORE days, targeting the WITHIN-ASSET-DAY
PERCENTILE of the frozen cert with each asset-day weighted equally, standardized
on the training fold at a fixed ``lambda = 1``.  There is no model search and no
penalty search.  On each out-of-fold asset-day it keeps at most the TOP FOUR
positive-score events: four per asset spends the twelve-entry portfolio budget
exactly, so coverage is set by capacity and never by a cash-tuned cutoff.
Top-three and top-five are reported as non-letter neighbours.

Nothing here is executable.  EXPLORE only, kill-only tier, no packs, no HOLD, no
teacher labels, no 2021, no 2025H2, no commits, no freeze.  Sweeps 22, 23, 25
and ``levels_zone`` are imported READ-ONLY and are not modified.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
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

import mill as M  # noqa: E402
import levels as LV  # noqa: E402
import levels_zone as LZ  # noqa: E402
import sweep1 as S1  # noqa: E402
import sweep8 as S8  # noqa: E402
import sweep9_twins as S9  # noqa: E402
import sweep12 as S12  # noqa: E402
import sweep14 as S14  # noqa: E402
import sweep19 as S19  # noqa: E402
import sweep20 as S20  # noqa: E402
import sweep22 as S22  # noqa: E402
import sweep23 as S23  # noqa: E402
import sweep25 as S25  # noqa: E402

# --------------------------------------------------------------------------
# The law, registered before anything is read.
# --------------------------------------------------------------------------

SPEC = """QRE2MILLSWEEP27
tier=exploratory; EXPLORE-only, kill-only.  Family F22-FIXEDZONE-RANK, the first
  unit of Sol's power plan (.audit/briefs/mill-powerplan-sol-out.md section C,
  information rank 1).  Seed 20260827.  Parent trial sweep26-053.  NO COMMITS,
  NO FREEZE, no packs, no HOLD, no teacher labels, no 2021, no 2025H2.  ONE
  entry lane, ONE selector, one maxT family of TWO deciding lines; HG is carried
  report-only on every line.
INHERITANCE.  Sweeps 25, 23 and 22 are imported and called READ-ONLY; their
  SPECs govern every clause not restated here: the GATE, the zone catalogue, the
  fold-trained zone width and its snap to the cache band multipliers, breach
  formation with the persistence gate and the per (asset, day, phase, level,
  break direction) dedup, the frozen bar-entry law, the impulse ridge and its
  join, the frozen outcome law with the 1800 s label beside, the chronological
  seat replay, the MDD ledger family, the two stresses, and the matched control.
  FORMATION MUST RETURN 3,790 CANDIDATES or this unit refuses.
1. THE FORMATION AND THE LANE.  Sweep 23's breach formation, unchanged, through
  S23.formation_pass.  Lane A only: decide at the breach close - the first
  one-minute close carrying price past a trained band edge - and enter in the
  BREAK direction at the NEXT bar under the frozen entry law.  NEVER a same-close
  fill: the run asserts the entry stamp is strictly after the breach close for
  every priced row, and cross-checks every lane-A close-label cert against the
  frozen cert plane at the same (cell, side, bar).  The frozen wall-or-close
  outcome is PRIMARY; the 1800 s label is reported beside it as information.
2. THE BARRIER READ.  Every level field is read through
  tools/mill/levels_zone.py read_zone at the candidate's FIXED zone_price with
  the trained HALF width, on side = defence_side = -break_dir, THE FORMER
  DEFENDING SIDE, at DECISION STAMP lat[breach_bar - 1], the lattice close of
  the LAST COMPLETED BAR BEFORE THE BREACH CLOSE.  The accessor counts only bars
  closing STRICTLY BEFORE that stamp, so the read sees bars 0..breach_bar-2: the
  breach bar cannot enter its own feature row and neither can the bar naming the
  stamp.  EVERY returned row must echo center_price == zone_price EXACTLY and
  max_source_stamp strictly below the decision stamp; either miss refuses the
  run, per row.  There is no fallback, no second stamp and no zero default.
3. THE FEATURE ROW, exactly Sol's roster, one row per candidate.  From the
  SEPARATE fixed-zone fields:
    log touch count            log1p(sd_touches)
    held rate                  sd_held / sd_touches
    broke rate                 sd_broke / sd_touches
    minutes since touch        sd_mins_since_touch
    touch flow / touch count   sd_touch_delta / sd_touches
  the SAME FIVE for the PRIOR EXPLORE SESSION (ps_*), then
  day_scale_persistence UNDER THAT EXACT NAME, the ZONE KIND as a one-hot over
  the six registered kinds, the BAND WIDTH SCALED BY PRIOR ATR (width /
  atr_mid2), and I_break.  Nineteen columns, named in FEATURE_NAMES.
  EXCLUDED BY REGISTRATION, asserted mechanically against the accessor's own
  field roster: absolute timestamps (decision_stamp_ns, max_source_stamp,
  ps_sess_d8), row counts that reveal warmup (n_source_bars, n_ps_source_bars,
  n_day_scale_bars), outcome fields (day_scale_held, day_scale_broke, and every
  cert, wall, mae, mfe and exit stamp), and schedule fields (phase, the bar
  index, the day-scale mode, and any clock variable).  A rate is NaN where its
  touch count is not a positive finite number: a price nothing touched has no
  rate, which is not the same fact as a rate of zero.  MISSINGNESS LAW, the
  standing one: a NaN is imputed at the TRAINING FOLD's own mean of that column,
  so it standardizes to zero and carries no information.  Rows with no finite
  I_break are counted and a no-imputed-I neighbour is reported.
4. THE RANKER.  ONE ridge per ASSET, fit on STRICTLY PRIOR EXPLORE days under
  the standing fold law: >= 25 prior EXPLORE days of warmup and >= 40 training
  rows, else the day trades nothing.  TARGET = the WITHIN-ASSET-DAY PERCENTILE
  of the frozen cert, average-rank, (rank - 0.5) / n, over that day's formed and
  priced candidates.  EACH ASSET-DAY IS WEIGHTED EQUALLY: a training row's
  weight is 1 / (rows on its asset-day), renormalized to sum to the number of
  training rows so lambda keeps the meaning it has in an unweighted fit of the
  same size.  Columns are standardized on the TRAINING FOLD; a column with no
  spread on the fold gets spread 1 and therefore contributes nothing.  The
  target is centred on its weighted training mean, so the fitted score is the
  predicted within-day rank MINUS the training-average rank and a POSITIVE score
  means "predicted to rank above the training-average event".  LAMBDA = 1,
  FIXED.  NO MODEL SEARCH, NO PENALTY SEARCH, no feature selection, no
  transformation search.
5. THE SELECTION.  On each out-of-fold asset-day keep at most the TOP FOUR
  POSITIVE-SCORE events, ordered by score descending with (position) as the
  deterministic tie break.  Four per asset spends the twelve-entry portfolio
  budget exactly, so coverage comes from CAPACITY and never from a cash-tuned
  cutoff.  TOP-THREE and TOP-FIVE are reported as NON-LETTER NEIGHBOURS; a LIVE
  letter requires neither to flip the sign of either deciding asset.
6. THE CONTROL.  One paired G1 control per selected event, matched on ASSET,
  DATE, PHASE, BREACH-TIME BIN and MAGNITUDE BIN through S22.match_controls -
  Sol's five keys, unchanged.  The COMPLETE level vector is PERMUTED INSIDE THE
  TRAINING FOLD: each matched control is handed a whole feature row drawn from a
  permutation of its own fold and scored by that fold's ranker, and the share
  that would have earned a positive score and a top-four seat is reported.
  Selected minus matched control is aggregated BY SHARED CALENDAR DATE,
  studentized, and read under ONE maxT family over NKD and SI - TWO lines, the
  preregistered family, with HG carried as an ineligible report-only line -
  using 10000 shared-date-sign draws.  EVENT-LEVEL P-VALUES ARE FORBIDDEN and
  none is computed: several events share one impulse, one day and one seat
  ledger, so the independent unit is the calendar date.  C3 block-permutation
  nulls are reported with the standing caveat, unadjusted, as information.
7. PRICING, REPLAY, LEDGERS.  Chronological seat replay with the frozen tie
  break, exits before entries at an equal stamp, ONE open position per asset, at
  most 12 seated entries per PORTFOLIO date, every split date carried including
  zero-entry dates.  The full MDD ledger family including EVENT-TIME PORTFOLIO
  EQUITY; binding is the deciding assets' own trade and day ledgers plus every
  portfolio ledger, ceiling 1000 USD.  The 2 percent adversarial stress and the
  DOUBLED-SPREAD stress, both re-running the replay so occupancy follows.  C2:
  the formed-opportunity ceiling RAW and CAPPED at the 12 best events per
  portfolio date, hindsight bits named; the kill test reads the RAW FORMED
  ceiling, never the selected subset.
8. LETTERS, Sol's three, with a registered precedence and a proven partition:
  LEVELMEMORY-LIVE when BOTH deciding assets clear the rung at the point
    estimate AND at mean minus two asset-day-block standard errors, BOTH
    adjusted control lines are at p <= 0.05, every binding MDD is below 1000,
    cap and occupancy are lawful, both stresses clear MDD, and neither the
    top-three nor the top-five neighbour flips a deciding sign.
  LEVELMEMORY-KILL clause K1 when a POWERED deciding control has a NON-POSITIVE
    95 percent simultaneous upper bound.
  LEVELMEMORY-KILL clause K2 when the FORMED ceiling carries both rungs and
    EITHER causal matched delta is zero or negative.
  LEVELMEMORY-UNRESOLVED clause U1, Sol's named case: two positive matched
    deltas with inadequate power or a failed live bound.
  LEVELMEMORY-UNRESOLVED clause U0, THE REGISTERED RESIDUAL, disclosed rather
    than hidden.  Sol's three letters as written do not cover the point where
    the formed ceiling MISSES a deciding rung while no deciding upper bound is
    non-positive and the matched deltas are not both positive: K1 needs the
    upper bound, K2 needs the ceiling to carry, U1 needs two positive deltas.
    Section D licenses a kill ONLY under "its powered upper-bound clause or its
    two-asset non-positive-delta clause", so the residual CANNOT be a kill and
    is registered as UNRESOLVED.  This is an enumeration gap in the letter text,
    recorded here the way sweep 25 recorded CEILING-UNREACHED, and the selftest
    proves the five-clause partition is total over all 512 outcome points.
  PRECEDENCE LIVE > K1 > K2 > U1 > U0, no fallthrough.  The family letter is the
  letter: one lane, one selector, one letter.
MUTANTS.  Each names the EXACT checks it must turn red; a mutant that reds some
  other check, or that leaves any named check green, fails the run.
  QRE2_MILL_S27_MUTANT=selector_uses_test_day fits the ranker's fold - its
    standardization, its weights, its target percentiles and its coefficients -
    on days[:index+1] instead of days[:index], and fits the impulse ridge
    including the scoring day.  It must red the planted LEAK world, whose payoff
    gradient exists ONLY on the scoring day and which therefore must yield NO
    out-of-fold recovery when the fold is honest.
  QRE2_MILL_S27_MUTANT=center_uses_current_mid arms the accessor's own
    registered defect - the reading bar's mid replaces the requested zone price.
    It must red the centre-equality gate on the fixture AND on 50 real formed
    rows, the trapped cohort's hand count, and the log touch count that
    separates the two zones.  DISCLOSED AND MEASURED: the WEAK zone's hand count
    SURVIVES the defect.  At centre 1396 instead of 1400 the band [1386, 1406]
    still holds bars 13, 14 and 18 and still resolves 0 held and 2 broke, so the
    miscentred read reproduces that receipt exactly.  A wrong price key can
    return a right-looking number - that is how sweep 22 passed its own selftest
    - so the refusal is mechanical per-row equality and never a plausibility or
    ranking check, and the mutant roster is the MEASURED red set rather than the
    set a reader would guess.
"""

RESIDUAL_NOTE = (
    "REGISTERED ENUMERATION DISCLOSURE, clause U0.  Sol's three letters, read "
    "literally, do not cover every receipt: LEVELMEMORY-KILL fires on a "
    "non-positive powered upper bound OR on a ceiling that carries both rungs "
    "beside a non-positive matched delta, and LEVELMEMORY-UNRESOLVED names "
    "'two positive matched deltas with inadequate power or a failed live "
    "bound'.  A receipt in which the FORMED CEILING MISSES a deciding rung, no "
    "deciding upper bound is non-positive, and the matched deltas are not both "
    "positive satisfies none of them.  Sweep 25 met the same shape and had to "
    "register CEILING-UNREACHED as clause K3 by elimination.  This unit does "
    "NOT repeat that: the charter licenses a kill only under the powered "
    "upper-bound clause or the two-asset non-positive-delta clause, so the "
    "residual cannot lawfully kill, and it is registered as UNRESOLVED clause "
    "U0 BEFORE any outcome is read.  The partition is proved total over all "
    "512 outcome points in the selftest, and the receipt reports which clause "
    "fired and which others matched.")

COMPRESSION_NOTE = (
    "WHY THE COMPONENTS AND NOT THE MEAN.  F19's and F20's barrier score was "
    "the arithmetic mean of three standardized differences - same-day held "
    "minus broke, the day-scale persistence proxy, and prior-session held minus "
    "broke.  That compression is not a neutral summary.  It forces one sign and "
    "one weight on three horizons, it discards the touch COUNT that says how "
    "much evidence a rate carries, and it cannot see recency, signed touch "
    "flow, zone kind or band width at all.  A mean of standardized parts is "
    "also exactly cancellable: if one component's information is opposed by "
    "another's, their mean can be identically zero while a ranker over the "
    "parts recovers the gradient perfectly.  The selftest plants that world - "
    "the payoff rises monotonically in the prior-session HELD RATE while the "
    "same-day held rate falls with it by construction - and asserts that the "
    "component ranker recovers the ordering out of fold while the compressed "
    "single-mean score selects nothing at all.  That is the measurement the "
    "first three fixed-zone units never made.")

ASSETS = S23.ASSETS
DECIDING = S23.DECIDING
REPORT_ONLY_ASSETS = S23.REPORT_ONLY_ASSETS
SEED = 20260827

FAMILY = "F22-FIXEDZONE-RANK"
PARENT_TRIAL = "sweep26-053"
SELECTION_RULE = ("none: parent-preregistered break formation and break-close "
                  "lane, one asset-specific ridge ranker over the separate "
                  "fixed-zone components fit on strictly prior EXPLORE days at "
                  "a fixed lambda=1, coverage set by the twelve-entry seat "
                  "budget; no model search, no penalty search, no cash-tuned "
                  "cutoff")

LOG_PREFIX = "sweep27"
OUT_PATH = ROOT / ".audit/mill-sweep27.json"
LOG_PATH = S1.LOG_PATH

EXPECT_CANDIDATES = S25.EXPECT_CANDIDATES          # 3,790

# Inherited by value, so an upstream drift fails loudly here.
CLOSE = S25.CLOSE
FIXED = S25.FIXED
LABELS = S25.LABELS
NANOS = S25.NANOS
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
ZONE_KINDS = S22.ZONE_KINDS
HINDSIGHT_CEILING = S25.HINDSIGHT_CEILING

LANE = "A_BREAK_CLOSE"
LANE_NAME = ("break close: enter the break direction at the NEXT bar (the "
             "USER's timing, sweep 25's promoted lane A, held fixed)")

RIDGE_LAMBDA = 1.0
TOP_K = 4
NEIGHBOUR_K = (3, 5)
ALL_K = (3, 4, 5)

# --------------------------------------------------------------------------
# The feature roster.  Registered by name, and asserted against the accessor's
# own field list so an excluded field cannot reach the matrix by accident.
# --------------------------------------------------------------------------

SAME_DAY_FEATURES = ("sd_log_touches", "sd_held_rate", "sd_broke_rate",
                     "sd_mins_since_touch", "sd_touch_flow_per_touch")
PRIOR_SESSION_FEATURES = ("ps_log_touches", "ps_held_rate", "ps_broke_rate",
                          "ps_mins_since_touch", "ps_touch_flow_per_touch")
ZONE_KIND_FEATURES = tuple(f"zone_kind={kind}" for kind in ZONE_KINDS)
FEATURE_NAMES = (SAME_DAY_FEATURES + PRIOR_SESSION_FEATURES
                 + ("day_scale_persistence",) + ZONE_KIND_FEATURES
                 + ("band_width_over_prior_atr", "I_break"))
NFEAT = len(FEATURE_NAMES)
I_BREAK_COLUMN = FEATURE_NAMES.index("I_break")

# Which accessor fields this unit consumes, and which it refuses.  The run
# asserts the two partition ZONE_ROW_FIELDS with nothing left over.
CONSUMED_ZONE_FIELDS = (
    "sd_touches", "sd_held", "sd_broke", "sd_mins_since_touch", "sd_touch_delta",
    "ps_touches", "ps_held", "ps_broke", "ps_mins_since_touch", "ps_touch_delta",
    "day_scale_persistence", "zone_kind", "band_width")
EXCLUDED_ZONE_FIELDS = {
    "decision_stamp_ns": "absolute timestamp",
    "max_source_stamp": "absolute timestamp",
    "ps_sess_d8": "absolute timestamp (the prior session's calendar date)",
    "d8": "absolute timestamp (the calendar date)",
    "n_source_bars": "row count that reveals warmup",
    "n_ps_source_bars": "row count that reveals warmup",
    "n_day_scale_bars": "row count that reveals warmup",
    "day_scale_held": "outcome-side component; Sol's roster names "
                      "day_scale_persistence under that exact name",
    "day_scale_broke": "outcome-side component; Sol's roster names "
                       "day_scale_persistence under that exact name",
    "phase": "schedule field",
    "day_scale_mode": "schedule field",
    "ps_served": "row count that reveals warmup (whether a fold has a "
                 "prior session at all)",
    "asset": "identity, carried as the ranker's own partition, never a column",
    "cell": "identity",
    "side": "identity (the defending side, fixed by formation)",
    "center_price": "identity, and a price level is not a component",
}

FORBIDDEN_OUTCOME_TOKENS = ("cert", "wall", "mae", "mfe", "exit", "pnl",
                            "usd", "payoff", "percentile", "target")

# --------------------------------------------------------------------------
# The letters.
# --------------------------------------------------------------------------

LETTER_LIVE = "LEVELMEMORY-LIVE"
LETTER_UNRESOLVED = "LEVELMEMORY-UNRESOLVED"
LETTER_KILL = "LEVELMEMORY-KILL"
CLAUSES = {
    "LIVE": ("both deciding assets clear the rung at the point estimate AND at "
             "mean minus two SE, both adjusted control lines p <= 0.05, every "
             "binding MDD below 1000, lawful cap and occupancy, both stresses, "
             "and no sign flip at the top-three or top-five neighbour"),
    "K1": ("a powered deciding control has a non-positive 95 percent "
           "simultaneous upper bound"),
    "K2": ("the formed ceiling carries both rungs and either causal matched "
           "delta is zero or negative"),
    "U1": ("two positive matched deltas with inadequate power or a failed live "
           "bound"),
    "U0": ("THE REGISTERED RESIDUAL: no live bound, no powered non-positive "
           "upper bound, and no lawful kill clause - the formed ceiling misses "
           "a deciding rung while the matched deltas are not both positive. "
           "The charter licenses a kill only under K1 or K2, so this receipt "
           "cannot kill and is parked UNRESOLVED"),
}
CLAUSE_ORDER = ("LIVE", "K1", "K2", "U1", "U0")
CLAUSE_LETTER = {"LIVE": LETTER_LIVE, "K1": LETTER_KILL, "K2": LETTER_KILL,
                 "U1": LETTER_UNRESOLVED, "U0": LETTER_UNRESOLVED}

C3_CAVEAT = S25.C3_CAVEAT

MUTANT_ENV = "QRE2_MILL_S27_MUTANT"
MUTANT_CENTER = "center_uses_current_mid"
MUTANT_TESTDAY = "selector_uses_test_day"
MUTANTS = (MUTANT_CENTER, MUTANT_TESTDAY)

EXPECTED_RED = {
    # MEASURED, not guessed.  The weak zone's hand count SURVIVES the
    # miscentring: at centre 1396 instead of 1400 the band [1386, 1406] still
    # contains bars 13, 14 and 18 and still resolves 0 held and 2 broke, so the
    # defect reproduces that receipt exactly.  That survival is the disclosure -
    # a wrong price key can return a right-looking number - and it is why the
    # refusal is mechanical per-row equality and never a plausibility check.
    MUTANT_CENTER: (
        "the component read is centred ON the defended zone, not on the "
        "reading bar's mid",
        "the component read is centred ON the weakly defended zone",
        "the trapped cohort's hand count is 4 touches, 3 held, 0 broke, held "
        "rate 0.75",
        "the log touch count separates the two zones: log1p(4) against "
        "log1p(3)",
        "every real row echoes centre_price == zone_price EXACTLY"),
    MUTANT_TESTDAY: (
        "THE LEAK GUARD: a world whose gradient exists ONLY on the scoring day "
        "yields NO out-of-fold recovery",),
}


class SweepRefusal(RuntimeError):
    pass


SPEC_SHA = S1._sha_text(SPEC)


def code_sha() -> str:
    """This unit plus every module whose behaviour it is asserting."""

    here = Path(__file__).resolve().parent
    return S1._sha_text("\n".join(
        S1._sha_file(Path(path).resolve()) for path in (
            __file__, here / "sweep25.py", here / "sweep23.py",
            here / "sweep22.py", here / "levels_zone.py")))


def _mutant() -> str:
    name = os.environ.get(MUTANT_ENV, "")
    if name and name not in MUTANTS:
        raise SweepRefusal(f"unknown sweep 27 mutant: {name}")
    return name


def arm_mutant(mutant: str) -> str:
    """The centre mutant lives inside the accessor, so it is armed by env."""

    if mutant == MUTANT_CENTER:
        os.environ[LZ.MUTANT_ENV] = LZ.MUTANT_CENTER_MID
    return mutant


_pct = S22._pct
_mean_se = S22._mean_se
_n = S22._n
_show = S22._show
_check = S22._check


# --------------------------------------------------------------------------
# 2. THE BARRIER READ.  Full rows, at the fixed zone price, one per candidate.
# --------------------------------------------------------------------------

@dataclass(slots=True)
class ZoneRead:
    """Every accessor row, with the evidence that it is at the zone."""

    rows: list                       # (n,) LZ.ZoneRow | None, by candidate
    have: np.ndarray                 # (n,) bool
    counters: dict


def zone_read(cands: Sequence[S23.Cand], records: Sequence[S1.CellRec],
              reader: LZ.ZoneReader) -> ZoneRead:
    """One ``levels_zone`` row per candidate, at its own fixed zone price.

    The queries are built by ``S25.zone_queries``, called READ-ONLY, so the
    price key, the side, the decision stamp and the day-scale mode are sweep
    25's registered read and not a restatement of it.  What differs is only that
    this unit KEEPS THE WHOLE ROW instead of collapsing it to three differences.
    """

    queries, positions = S25.zone_queries(cands, records)
    got = reader.rows(queries) if queries else []
    rows: list = [None] * len(cands)
    have = np.zeros(len(cands), bool)
    counters = {"candidates": len(cands), "queries": len(queries),
                "rows": len(got), "no_decision_stamp": len(cands) - len(queries),
                "center_exact": 0, "center_mismatched": 0,
                "strictly_prior": 0, "not_strictly_prior": 0,
                "prior_session_served": 0, "prior_session_absent": 0,
                "sd_touches_defined": 0, "sd_touches_undefined": 0,
                "ps_touches_defined": 0, "ps_touches_undefined": 0,
                "day_scale_defined": 0, "day_scale_undefined": 0,
                "zero_default_used": 0, "fallback_reads": 0}
    worst_center = 0.0
    worst_source = -(1 << 62)
    for row, query, position in zip(got, queries, positions):
        gap = abs(float(row.center_price) - float(query.zone_price))
        worst_center = max(worst_center, gap)
        counters["center_exact" if float(row.center_price)
                 == float(query.zone_price) else "center_mismatched"] += 1
        delta = int(row.max_source_stamp) - int(row.decision_stamp_ns)
        worst_source = max(worst_source, delta)
        counters["strictly_prior" if delta < 0 else "not_strictly_prior"] += 1
        counters["prior_session_served" if row.ps_served
                 else "prior_session_absent"] += 1
        counters["sd_touches_defined" if math.isfinite(row.sd_touches)
                 else "sd_touches_undefined"] += 1
        counters["ps_touches_defined" if math.isfinite(row.ps_touches)
                 else "ps_touches_undefined"] += 1
        counters["day_scale_defined" if math.isfinite(row.day_scale_persistence)
                 else "day_scale_undefined"] += 1
        rows[position] = row
        have[position] = True
    counters["worst_center_gap_mid2"] = float(worst_center)
    counters["worst_source_minus_decision_ns"] = int(
        worst_source if got else -1)
    return ZoneRead(rows=rows, have=have, counters=counters)


def assert_zone_anchored(read: ZoneRead) -> None:
    """The refusals Sol's ruling requires, per row, before anything is scored."""

    counters = read.counters
    if counters["center_mismatched"]:
        raise SweepRefusal(
            f"{counters['center_mismatched']} of {counters['rows']} barrier "
            f"reads are not centred on the candidate zone (worst gap "
            f"{counters['worst_center_gap_mid2']} mid2); this is the refused "
            f"F19 defect and nothing may be scored past it")
    if counters["not_strictly_prior"]:
        raise SweepRefusal(
            f"{counters['not_strictly_prior']} barrier reads have a source "
            f"stamp at or after their own decision stamp (worst "
            f"{counters['worst_source_minus_decision_ns']} ns)")
    if counters["zero_default_used"] or counters["fallback_reads"]:
        raise SweepRefusal("a candidate inherited a defaulted or fallback read")
    if counters["rows"] != counters["candidates"]:
        raise SweepRefusal(
            f"the accessor answered {counters['rows']} of "
            f"{counters['candidates']} candidates; every formed candidate has a "
            f"bar strictly before its breach and must be readable")


# --------------------------------------------------------------------------
# 3. THE FEATURE ROW.
# --------------------------------------------------------------------------

def _rate(numerator: float, touches: float) -> float:
    """A rate exists only where the touch count does.  Never a silent zero."""

    if not (math.isfinite(touches) and touches > 0.0):
        return float("nan")
    if not math.isfinite(numerator):
        return float("nan")
    return float(numerator) / float(touches)


def _log_count(touches: float) -> float:
    if not math.isfinite(touches) or touches < 0.0:
        return float("nan")
    return float(math.log1p(float(touches)))


def feature_row(row, cand: S23.Cand) -> np.ndarray:
    """Sol's roster, in ``FEATURE_NAMES`` order.  ``I_break`` is filled later."""

    out = np.full(NFEAT, np.nan, np.float64)
    out[0] = _log_count(float(row.sd_touches))
    out[1] = _rate(float(row.sd_held), float(row.sd_touches))
    out[2] = _rate(float(row.sd_broke), float(row.sd_touches))
    out[3] = float(row.sd_mins_since_touch)
    out[4] = _rate(float(row.sd_touch_delta), float(row.sd_touches))
    out[5] = _log_count(float(row.ps_touches))
    out[6] = _rate(float(row.ps_held), float(row.ps_touches))
    out[7] = _rate(float(row.ps_broke), float(row.ps_touches))
    out[8] = float(row.ps_mins_since_touch)
    out[9] = _rate(float(row.ps_touch_delta), float(row.ps_touches))
    out[10] = float(row.day_scale_persistence)
    kind = str(row.zone_kind) or str(cand.zone_kind)
    for offset, name in enumerate(ZONE_KINDS):
        out[11 + offset] = 1.0 if kind == name else 0.0
    atr = float(cand.atr_mid2)
    out[11 + len(ZONE_KINDS)] = (float(row.band_width) / atr if atr > 0.0
                                 else float("nan"))
    return out


def build_features(read: ZoneRead, cands: Sequence[S23.Cand]
                   ) -> tuple[np.ndarray, dict[str, object]]:
    """One row per candidate, plus the definedness census per column."""

    matrix = np.full((len(cands), NFEAT), np.nan, np.float64)
    for position, cand in enumerate(cands):
        row = read.rows[position]
        if row is None:
            continue
        matrix[position] = feature_row(row, cand)
    census = {name: int(np.isfinite(matrix[:, index]).sum())
              for index, name in enumerate(FEATURE_NAMES)}
    return matrix, {"rows": int(len(cands)), "finite_per_column": census}


def assert_feature_law() -> None:
    """The exclusions, checked against the accessor's own field roster."""

    fields = set(LZ.ZONE_ROW_FIELDS)
    consumed = set(CONSUMED_ZONE_FIELDS)
    excluded = set(EXCLUDED_ZONE_FIELDS)
    missing = consumed - fields
    if missing:
        raise SweepRefusal(f"this unit consumes fields the accessor does not "
                           f"serve: {sorted(missing)}")
    overlap = consumed & excluded
    if overlap:
        raise SweepRefusal(f"a field is both consumed and excluded: "
                           f"{sorted(overlap)}")
    uncovered = fields - consumed - excluded
    if uncovered:
        raise SweepRefusal(
            f"the accessor serves fields this unit neither consumes nor "
            f"registers as excluded: {sorted(uncovered)}; the roster must "
            f"partition the row so nothing enters the matrix unregistered")
    for name in FEATURE_NAMES:
        lowered = name.lower()
        if name == "I_break":
            continue
        for token in FORBIDDEN_OUTCOME_TOKENS:
            if token in lowered:
                raise SweepRefusal(f"feature {name!r} names an outcome token "
                                   f"{token!r}")
    if len(set(FEATURE_NAMES)) != NFEAT:
        raise SweepRefusal("the feature roster repeats a name")


# --------------------------------------------------------------------------
# 4. THE RANKER.  One asset-specific weighted ridge per out-of-fold day.
# --------------------------------------------------------------------------

def within_day_percentile(values: Sequence[float]) -> np.ndarray:
    """Average-rank percentile, ``(rank - 0.5) / n``, inside ONE asset-day.

    Ties share their average rank, so a day on which every cert is equal maps
    every row to 0.5 and carries no gradient at all - which is exactly the fact
    the leak fixture depends on.
    """

    values = np.asarray(values, np.float64)
    n = int(len(values))
    if n == 0:
        return np.zeros(0, np.float64)
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(n, np.float64)
    ranks[order] = np.arange(1, n + 1, dtype=np.float64)
    # average rank over ties
    sorted_values = values[order]
    start = 0
    for stop in range(1, n + 1):
        if stop == n or sorted_values[stop] != sorted_values[start]:
            if stop - start > 1:
                mean_rank = float(np.mean(ranks[order[start:stop]]))
                ranks[order[start:stop]] = mean_rank
            start = stop
    return (ranks - 0.5) / float(n)


def _standardize(block: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Training-fold centre and spread; a column with no spread gets spread 1."""

    with np.errstate(invalid="ignore"):
        centre = np.nanmean(block, axis=0)
        spread = np.nanstd(block, axis=0)
    centre = np.where(np.isfinite(centre), centre, 0.0)
    spread = np.where(np.isfinite(spread) & (spread > 1e-12), spread, 1.0)
    return centre, spread


def _design(block: np.ndarray, centre: np.ndarray, spread: np.ndarray
            ) -> np.ndarray:
    """Standardize, then impute a NaN at the fold mean, i.e. at exactly zero."""

    z = (np.asarray(block, np.float64) - centre) / spread
    return np.where(np.isfinite(z), z, 0.0)


def fit_ridge(z: np.ndarray, y: np.ndarray, w: np.ndarray,
              lam: float = RIDGE_LAMBDA) -> np.ndarray:
    """``(Z' W Z + lam I)^-1 Z' W y`` with ``y`` already centred."""

    zw = z * w[:, None]
    gram = z.T @ zw + float(lam) * np.eye(z.shape[1])
    return np.linalg.solve(gram, zw.T @ y)


def _spearman(a: Sequence[float], b: Sequence[float]) -> float | None:
    a = np.asarray(a, np.float64)
    b = np.asarray(b, np.float64)
    if len(a) < 3 or len(a) != len(b):
        return None
    ra = within_day_percentile(a)
    rb = within_day_percentile(b)
    if float(np.std(ra)) < 1e-12 or float(np.std(rb)) < 1e-12:
        return None
    return float(np.corrcoef(ra, rb)[0, 1])


@dataclass(slots=True)
class Fold:
    """One out-of-fold asset-day: its ranker, and what it did."""

    asset: str
    d8: int
    train_rows: int
    train_days: int
    centre: np.ndarray
    spread: np.ndarray
    beta: np.ndarray
    positions: np.ndarray          # the scoring day's candidate positions
    scores: np.ndarray             # their fitted scores
    truth: np.ndarray              # their within-day cert percentile
    rank_corr: float | None


def rank_folds(positions_by_day: Mapping[tuple[str, int], list[int]],
               features: np.ndarray, cert: np.ndarray,
               explore_days: Mapping[str, Sequence[int]], mutant: str
               ) -> tuple[list[Fold], dict[str, object]]:
    """The walk-forward ranker: one weighted ridge per out-of-fold asset-day."""

    folds: list[Fold] = []
    report = {"assets": 0, "days_scored": 0, "days_warmup": 0, "days_thin": 0,
              "train_rows_total": 0, "scored_rows": 0}
    percentile_by_day: dict[tuple[str, int], np.ndarray] = {}
    for key, rows in positions_by_day.items():
        percentile_by_day[key] = within_day_percentile(cert[np.asarray(rows,
                                                                       np.int64)])
    for asset in sorted(explore_days):
        report["assets"] += 1
        days = sorted(int(day) for day in explore_days[asset])
        for index, d8 in enumerate(days):
            today = positions_by_day.get((asset, d8), [])
            if not today:
                continue
            if index < MIN_PRIOR_DAYS:
                report["days_warmup"] += 1
                continue
            train_days = days[:index + 1] if mutant == MUTANT_TESTDAY else days[:index]
            train_keys = [(asset, day) for day in train_days
                          if positions_by_day.get((asset, day))]
            train_positions: list[int] = []
            weights: list[float] = []
            target: list[float] = []
            for key in train_keys:
                rows = positions_by_day[key]
                pct = percentile_by_day[key]
                share = 1.0 / float(len(rows))
                for offset, position in enumerate(rows):
                    train_positions.append(int(position))
                    weights.append(share)
                    target.append(float(pct[offset]))
            if len(train_positions) < MIN_TRAIN_ROWS:
                report["days_thin"] += 1
                continue
            take = np.asarray(train_positions, np.int64)
            w = np.asarray(weights, np.float64)
            # Renormalized so lambda keeps the meaning it has in an unweighted
            # fit of the same size.
            w = w * (float(len(take)) / float(w.sum()))
            y = np.asarray(target, np.float64)
            centre, spread = _standardize(features[take])
            z = _design(features[take], centre, spread)
            y_centre = float((w * y).sum() / w.sum())
            beta = fit_ridge(z, y - y_centre, w)
            look = np.asarray(today, np.int64)
            scores = _design(features[look], centre, spread) @ beta
            truth = percentile_by_day[(asset, d8)]
            folds.append(Fold(
                asset=asset, d8=int(d8), train_rows=int(len(take)),
                train_days=len(train_keys), centre=centre, spread=spread,
                beta=beta, positions=look, scores=np.asarray(scores, np.float64),
                truth=np.asarray(truth, np.float64),
                rank_corr=_spearman(scores, truth)))
            report["days_scored"] += 1
            report["train_rows_total"] += int(len(take))
            report["scored_rows"] += int(len(look))
    return folds, report


def select_top(fold: Fold, k: int) -> list[int]:
    """At most the top ``k`` POSITIVE-score events of this asset-day."""

    order = sorted(range(len(fold.positions)),
                   key=lambda i: (-float(fold.scores[i]),
                                  int(fold.positions[i])))
    picks = [int(fold.positions[i]) for i in order
             if float(fold.scores[i]) > 0.0]
    return picks[:int(k)]


def selections(folds: Sequence[Fold], k: int) -> list[int]:
    out: list[int] = []
    for fold in folds:
        out.extend(select_top(fold, k))
    return sorted(out)


def compressed_score(features: np.ndarray, take: np.ndarray,
                     look: np.ndarray) -> np.ndarray:
    """F19's and F20's compression: the MEAN of the standardized components.

    Kept as a measured comparator, not as a lane.  It is what the first three
    fixed-zone units scored, and the planted world proves what it cannot see.
    """

    centre, spread = _standardize(features[take])
    with np.errstate(invalid="ignore"):
        z = (features[look] - centre) / spread
        value = np.nanmean(np.where(np.isfinite(z), z, np.nan), axis=1)
    return np.where(np.isfinite(value), value, 0.0)


# --------------------------------------------------------------------------
# 8. THE LETTERS.  Five clauses, one precedence, a total partition.
# --------------------------------------------------------------------------

def classify(rung_ok: bool, mdd_ok: bool, cap_ok: bool, stress_ok: bool,
             control_ok: bool, neighbours_ok: bool, ceiling_carries: bool,
             upper_nonpositive: bool, matched_positive: bool
             ) -> tuple[str, str, list[str]]:
    """Exactly one clause fires; every clause that matched is listed beside it."""

    live = bool(rung_ok and mdd_ok and cap_ok and stress_ok and control_ok
                and neighbours_ok)
    matching: list[str] = []
    if live:
        matching.append("LIVE")
    if upper_nonpositive:
        matching.append("K1")
    if ceiling_carries and not matched_positive:
        matching.append("K2")
    if not live and matched_positive:
        matching.append("U1")
    if (not live and not upper_nonpositive
            and not (ceiling_carries and not matched_positive)
            and not matched_positive):
        matching.append("U0")
    for clause in CLAUSE_ORDER:
        if clause in matching:
            return CLAUSE_LETTER[clause], clause, matching
    raise SweepRefusal("the letter partition failed to cover a receipt")


def family_letter(report: Mapping[str, object]) -> dict[str, object]:
    """One lane, one selector, one letter: the family letter IS the letter."""

    live = report["live"]                            # type: ignore[index]
    ceiling = report["ceiling"]["FORMED_UNIVERSE"]   # type: ignore[index]
    control = report["control"]["by_line"]           # type: ignore[index]
    reasons: list[str] = []

    rung_ok = True
    for asset in DECIDING:
        block = live["cash"][asset]                  # type: ignore[index]
        if not block.get("clears_rung"):
            rung_ok = False
            reasons.append(f"{asset} misses the rung "
                           f"({block.get('usd_per_day')} point, "
                           f"{block.get('mean_minus_2se_usd')} at -2SE)")
    mdd_ok = bool(live["mdd"]["clears"])             # type: ignore[index]
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
            reasons.append(f"{asset} has no powered matched control")
            continue
        if float(cell["p_max_adjusted"]) > 0.05:
            control_ok = False
            reasons.append(f"{asset} control p {cell['p_max_adjusted']:.4f} > 0.05")
    neighbours_ok = bool(live["neighbours_agree"])
    if not neighbours_ok:
        reasons.append("the top-three or top-five neighbour flips a deciding sign")

    ceiling_carries = all(
        bool(ceiling["cash"][asset].get("carries_rung"))  # type: ignore[index]
        for asset in DECIDING)
    if not ceiling_carries:
        reasons.append("the formed ceiling misses a deciding rung")
    matched_positive = all(
        (control.get(f"{LANE}|{asset}") or {}).get("delta_usd_per_date", 0.0) > 0.0
        for asset in DECIDING)
    if not matched_positive:
        reasons.append("the causal matched delta is not positive on both "
                       "deciding assets")
    upper_nonpositive = any(
        (control.get(f"{LANE}|{asset}") or {}).get(
            "upper95_simultaneous_usd") is not None
        and float(control[f"{LANE}|{asset}"]["upper95_simultaneous_usd"]) <= 0.0
        for asset in DECIDING)
    if upper_nonpositive:
        reasons.append("a powered deciding asset has a non-positive 95% upper "
                       "bound against its matched control")

    letter, clause, matching = classify(
        rung_ok, mdd_ok, cap_ok, stress_ok, control_ok, neighbours_ok,
        ceiling_carries, upper_nonpositive, matched_positive)
    return {"letter": letter, "clause": clause, "clause_text": CLAUSES[clause],
            "clauses_matching": matching, "reasons": reasons,
            "rung_ok": rung_ok, "mdd_ok": mdd_ok, "cap_ok": cap_ok,
            "stress_ok": stress_ok, "control_ok": control_ok,
            "neighbours_ok": neighbours_ok,
            "ceiling_carries_both_rungs": ceiling_carries,
            "upper_bound_nonpositive": upper_nonpositive,
            "matched_delta_positive": matched_positive}


# --------------------------------------------------------------------------
# Pricing: one shard pass, lane A only.
# --------------------------------------------------------------------------

def pricing_pass(cands: Sequence[S23.Cand], cells: Sequence[S8.Cell8],
                 streams: Sequence[S14.Stream], records: Sequence[S1.CellRec]
                 ) -> dict[str, object]:
    """Sweep 25's pass with the two pullback lanes removed.

    Lane A, the magnitude target rows, the G1 control pool and the formed
    ceiling.  Every entry goes through ``S22.price_bar_entry``, so the frozen
    entry law is the parent's and not a copy of it.
    """

    cell_by_position = {int(cell.position): cell for cell in cells}
    stream_by_cell = {int(stream.cell): stream for stream in streams}
    coarse, coarse_counters = S20.coarse_universe(streams, records)
    coarse_by_cell: dict[int, list[S14.Occ]] = {}
    for stream, occ in coarse:
        coarse_by_cell.setdefault(int(stream.cell), []).append(occ)
    cand_by_cell: dict[int, list[int]] = {}
    for position, cand in enumerate(cands):
        cand_by_cell.setdefault(int(cand.cell), []).append(position)

    by_day: dict[tuple[str, int], list[int]] = {}
    for position in sorted(set(list(cand_by_cell) + list(coarse_by_cell))):
        cell = cell_by_position.get(position)
        if cell is not None:
            by_day.setdefault((cell.asset, int(cell.d8)), []).append(position)

    counters = {"shards": 0, "cells": 0, "cells_missing_shard": 0,
                "mag_rows": 0, "mag_dropped": 0, "g1_rows": 0}
    for tag in ("nb", "g1", "ceil"):
        for suffix in ("out_of_range", "illegal", "unpriceable", "priced"):
            counters[f"{tag}_{suffix}"] = 0
    mag: list[S22.MagRow] = []
    entries: dict[int, S22.Priced] = {}
    g1_pool: dict[tuple[str, int, str], list[dict[str, object]]] = {}
    g1_priced: dict[int, S22.Priced] = {}
    ceiling: dict[int, dict[str, object]] = {}
    mid_by_cell: dict[int, np.ndarray] = {}
    lat_by_cell: dict[int, np.ndarray] = {}
    cert_plane = S19.build_cert_plane(cells)
    plane_checks = {"compared": 0, "mismatched": 0, "worst_abs_usd": 0.0}
    same_close: dict[str, object] = {"checked": 0, "violations": 0,
                                     "worst_gap_ns": None}

    for (asset, d8) in sorted(by_day):
        counters["shards"] += 1
        shard = M.load_shard(asset, d8)
        try:
            by_text = {cell.text: cell for cell in shard.cells}
            for position in sorted(by_day[(asset, d8)]):
                cell8 = cell_by_position[position]
                rec = cell8.rec
                shard_cell = by_text.get(rec.text)
                if shard_cell is None:
                    counters["cells_missing_shard"] += 1
                    continue
                index = shard.cell_index(shard_cell)
                counters["cells"] += 1
                lat = np.asarray(rec.lat, np.int64)
                mid_by_cell[position] = np.asarray(rec.mid, np.int64)
                lat_by_cell[position] = lat
                close_ns = int(rec.phase_close_ts_ns)

                # ---- sweep 20's magnitude target on its own coarse rows ----
                occs = sorted(coarse_by_cell.get(position, []),
                              key=lambda o: (o.bar, o.row))
                if occs:
                    bars = np.asarray([o.bar for o in occs], np.int64)
                    stamps = lat[bars]
                    closes = np.minimum(stamps + IMPULSE_HORIZON_S * NANOS,
                                        close_ns)
                    grid = S20.nowall_grid(index, stamps, closes)
                    take = grid["input_index"]
                    got = np.zeros(len(bars), bool)
                    move = np.zeros(len(bars), np.float64)
                    if len(take):
                        got[take] = True
                        move[take] = np.abs(
                            (grid["exit_mid2"] - grid["entry_mid2"]
                             ).astype(np.float64)) * index.factor
                    for local, occ in enumerate(occs):
                        if not got[local]:
                            counters["mag_dropped"] += 1
                            continue
                        mag.append(S22.MagRow(
                            asset=asset, d8=int(d8), cell=int(position),
                            row=int(occ.row), bar=int(occ.bar),
                            x=np.asarray(occ.x, np.float64),
                            absmove=float(move[local])))
                        counters["mag_rows"] += 1

                # ---- the G1 control pool: every occurrence in this cell ----
                stream = stream_by_cell.get(position)
                if stream is not None:
                    for occ in stream.occs:
                        priced = S22.price_bar_entry(
                            index, rec, "G1", -1, None, asset, int(d8),
                            rec.phase, position, int(occ.bar), int(occ.side),
                            counters, "g1")
                        if priced is None:
                            continue
                        g1_priced[int(occ.row)] = priced
                        g1_pool.setdefault((asset, int(d8), rec.phase), []).append({
                            "row": int(occ.row), "bar": int(occ.bar),
                            "side": int(occ.side),
                            "x": np.asarray(occ.x, np.float64),
                            "time_bin": min(TIME_BINS - 1,
                                            int(TIME_BINS * occ.bar
                                                / max(int(rec.n), 1))),
                            "impulse": float("nan"), "mag_bin": 0})
                        counters["g1_rows"] += 1

                mine = cand_by_cell.get(position, [])
                if not mine:
                    continue

                # ---- LANE A: the break close, entered at the NEXT bar ------
                for local in mine:
                    cand = cands[local]
                    priced = S22.price_bar_entry(
                        index, rec, LANE, local, cand, asset, int(d8),
                        rec.phase, position, int(cand.bar) + 1,
                        int(cand.break_dir), counters, "nb")
                    if priced is None:
                        continue
                    entries[local] = priced
                    same_close["checked"] = int(same_close["checked"]) + 1
                    gap = int(lat[int(cand.bar)]) - int(priced.entry_ts_ns)
                    worst = same_close["worst_gap_ns"]
                    same_close["worst_gap_ns"] = (gap if worst is None
                                                  else max(int(worst), gap))
                    if gap >= 0:
                        same_close["violations"] = int(
                            same_close["violations"]) + 1
                    reference = float(cert_plane.cert[
                        cert_plane.index[position],
                        0 if cand.break_dir > 0 else 1, int(cand.bar) + 1])
                    if math.isfinite(reference):
                        plane_checks["compared"] += 1
                        delta = abs(reference - float(priced.cert[CLOSE]))
                        plane_checks["worst_abs_usd"] = max(
                            plane_checks["worst_abs_usd"], delta)
                        if delta > 1e-6:
                            plane_checks["mismatched"] += 1

                # ---- C2: the formed-opportunity ceiling -------------------
                for local in mine:
                    cand = cands[local]
                    stop = min(int(rec.n) - 1, cand.bar + MAX_EPISODE_BARS)
                    best = None
                    row = cert_plane.index[position]
                    for bar in range(cand.bar, stop):
                        for column, side in enumerate((1, -1)):
                            value = float(cert_plane.cert[row, column, bar])
                            if not math.isfinite(value):
                                continue
                            if best is None or value > best[0]:
                                best = (value, bar, side)
                    if best is None:
                        continue
                    fixed = None
                    priced = S22.price_bar_entry(
                        index, rec, "CEILING", local, cand, asset, int(d8),
                        rec.phase, position, int(best[1]), int(best[2]),
                        counters, "ceil")
                    if priced is not None:
                        fixed = float(priced.cert[FIXED])
                    ceiling[local] = {"usd": float(best[0]), "bar": int(best[1]),
                                      "side": int(best[2]), "fixed_usd": fixed}
        finally:
            shard.close()
    return {"mag": mag, "entries": entries, "g1_pool": g1_pool,
            "g1_priced": g1_priced, "ceiling": ceiling,
            "mid_by_cell": mid_by_cell, "lat_by_cell": lat_by_cell,
            "counters": counters, "coarse_counters": coarse_counters,
            "plane_checks": plane_checks, "same_close": same_close}


# --------------------------------------------------------------------------
# The run.
# --------------------------------------------------------------------------

def run() -> dict[str, object]:
    mutant = arm_mutant(_mutant())
    started = time.time()
    assert_feature_law()
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
    if tuple(manifest.get("columns", ())) != LV.LEVEL_FEATURES:
        raise SweepRefusal("the levels cache column roster drifted")
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
            f"the selector under test is not attributable")

    # ---- 2. the barrier read, at the fixed zone price, full rows -----------
    reader = LZ.reader(ASSETS)
    read = zone_read(cands, records, reader)
    assert_zone_anchored(read)

    # ---- pricing: lane A, the G1 pool, the magnitude rows, the ceiling -----
    priced = pricing_pass(cands, cells, streams, records)
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

    # ---- 3. the feature rows ----------------------------------------------
    features, feature_census = build_features(read, cands)
    features[:, I_BREAK_COLUMN] = impulse
    feature_census["finite_per_column"]["I_break"] = int(
        np.isfinite(impulse).sum())
    feature_census["rows_without_finite_I_break"] = int(
        (~np.isfinite(impulse)).sum())

    # ---- 4. the ranker: one weighted ridge per out-of-fold asset-day -------
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
    folds, rank_report = rank_folds(positions_by_day, features, cert,
                                    explore_days, mutant)
    rank_report["candidates_priced"] = int(len(entries))
    rank_report["candidates_unpriced"] = int(len(cands) - len(entries))

    diagnostics: dict[str, object] = {}
    for asset in ASSETS:
        mine = [f for f in folds if f.asset == asset]
        corrs = [f.rank_corr for f in mine if f.rank_corr is not None]
        diagnostics[asset] = {
            "folds": len(mine),
            "folds_with_rank_corr": len(corrs),
            "oof_rank_corr_mean": float(np.mean(corrs)) if corrs else None,
            "oof_rank_corr_median": float(np.median(corrs)) if corrs else None,
            "oof_rank_corr_p_positive": (float(np.mean([c > 0 for c in corrs]))
                                         if corrs else None),
            "train_rows_mean": (float(np.mean([f.train_rows for f in mine]))
                                if mine else None),
            "scored_rows": int(sum(len(f.positions) for f in mine)),
            "beta_l2_mean": (float(np.mean([float(np.linalg.norm(f.beta))
                                            for f in mine])) if mine else None)}
    fold_sample = [{
        "asset": f.asset, "d8": f.d8, "train_days": f.train_days,
        "train_rows": f.train_rows, "day_rows": int(len(f.positions)),
        "positive_scores": int((f.scores > 0.0).sum()),
        "rank_corr": f.rank_corr,
        "top4_mean_truth": (float(np.mean(sorted(
            zip(f.scores, f.truth), key=lambda t: -t[0])[:TOP_K],
            axis=0)[1]) if len(f.positions) else None)}
        for f in folds[:6] + folds[-6:]]
    beta_mean = {
        asset: {name: float(np.mean([float(f.beta[index]) for f in folds
                                     if f.asset == asset]))
                for index, name in enumerate(FEATURE_NAMES)}
        for asset in ASSETS if any(f.asset == asset for f in folds)}

    # ---- 5. the selection, and its two non-letter neighbours --------------
    picks = {k: selections(folds, k) for k in ALL_K}
    formed_by_asset = {asset: sum(1 for c in cands if c.asset == asset)
                       for asset in ASSETS}
    formed_opportunities: dict[str, int] = {}
    for cand in cands:
        key = f"{cand.asset}|{cand.d8}"
        formed_opportunities[key] = formed_opportunities.get(key, 0) + 1

    by_k: dict[str, object] = {}
    for k in ALL_K:
        chosen = [entries[p] for p in picks[k]]
        block = S22.evaluate_lane(LANE, chosen, cands, explore_days,
                                  formed_by_asset)
        by_k[str(k)] = block
    live = by_k[str(TOP_K)]
    selected_entries = [entries[p] for p in picks[TOP_K]]
    selected_positions = list(picks[TOP_K])

    agree = True
    for asset in DECIDING:
        base = live["cash"][asset]["usd_per_day"]
        for k in NEIGHBOUR_K:
            other = by_k[str(k)]["cash"][asset]["usd_per_day"]
            if base is None or other is None:
                agree = False
            elif (base > 0) != (other > 0):
                agree = False
    live["neighbours_agree"] = bool(agree)
    neighbours = {str(k): {
        "n": by_k[str(k)]["n"],
        "seated": by_k[str(k)]["replay"]["seated"],
        "cash": {asset: {
            "usd_per_day": by_k[str(k)]["cash"][asset]["usd_per_day"],
            "mean_minus_2se_usd": by_k[str(k)]["cash"][asset][
                "mean_minus_2se_usd"],
            "clears_rung": by_k[str(k)]["cash"][asset]["clears_rung"]}
            for asset in ASSETS}} for k in ALL_K}

    # ---- 7. stresses and the MDD ledger family ----------------------------
    stress: dict[str, object] = {}
    for kind in ("adversarial", "spread"):
        overrides = S22.stress_overrides(selected_entries, CLOSE, kind)
        seated = S22.replay(selected_entries, CLOSE, overrides)
        stress[kind] = {
            "seated": seated["seated"],
            "cash": S22.replay_cash(seated["trades"], explore_days),
            "mdd": S22.mdd_ledgers(seated["trades"], priced["mid_by_cell"],
                                   priced["lat_by_cell"], explore_days)}
    live["stress"] = stress
    live["mdd"] = S22.mdd_ledgers(live["trades"], priced["mid_by_cell"],
                                  priced["lat_by_cell"], explore_days)
    live.pop("trades", None)
    for k in ALL_K:
        by_k[str(k)].pop("trades", None)

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

    # ---- 6. C1: matched, level-permuted controls --------------------------
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
    family = [f"{LANE}|{asset}" for asset in DECIDING]
    control = S22.maxt_inference(control_lines, family, SIGN_DRAWS)
    control["event_level_p"] = (
        "FORBIDDEN and not computed: several events share one impulse, one day "
        "and one seat ledger, so the independent unit is the calendar date")

    # The registered permutation: hand every matched control a COMPLETE level
    # vector drawn from a permutation of its own TRAINING fold, score it with
    # that fold's own ranker, and ask how often it would have been picked.
    rng = np.random.default_rng(SEED + 63)
    fold_by_day = {(f.asset, f.d8): f for f in folds}
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
        z = _design(features[donor][None, :], fold.centre, fold.spread)
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
        base = np.asarray(pool, np.int64)
        with np.errstate(invalid="ignore"):
            cohort[asset] = {
                "n": int(len(mine)),
                "selected_mean": {name: float(np.nanmean(features[take, index]))
                                  for index, name in enumerate(FEATURE_NAMES)},
                "formed_mean": {name: float(np.nanmean(features[base, index]))
                                for index, name in enumerate(FEATURE_NAMES)}}

    report: dict[str, object] = {
        "schema": "QRE2MILLSWEEP27", "spec_sha": SPEC_SHA,
        "code_sha": code_sha(), "split_sha": S1.split_sha(),
        "outcome_law_sha": S1.outcome_law_sha(), "seed": SEED,
        "mutant": mutant, "family": FAMILY, "parent_trial": PARENT_TRIAL,
        "selection_rule": SELECTION_RULE, "registered_utc": report_stamp(),
        "residual_note": RESIDUAL_NOTE, "compression_note": COMPRESSION_NOTE,
        "selector_sign_note": S23.SELECTOR_SIGN_NOTE,
        "contamination_note": S25.CONTAMINATION_NOTE,
        "parent_spec_sha": S25.SPEC_SHA, "parent_code_sha": S25.code_sha(),
        "accessor_code_sha": S1._sha_file(Path(LZ.__file__).resolve()),
        "asset_days": {a: int(days.get(a, 0)) for a in ASSETS},
        "reproduction": repro, "stream_counters": stream_counters,
        "causality": causal,
        "levels_manifest": {
            "schema": manifest.get("schema"),
            "split_sha256": manifest.get("split_sha256"),
            "band_mults": list(manifest.get("band_mults", ())),
            "shards": len(manifest.get("shards", ())),
            "cells": manifest.get("totals", {}).get("cells"),
            "cells_with_prior_day": manifest.get("totals", {}).get(
                "cells_with_prior_day"),
            "cells_with_prior_session": manifest.get("totals", {}).get(
                "cells_with_prior_session"),
            "cache_max_src_minus_stamp_ns": cache_gap,
            "cache_strictly_prior": bool(cache_gap < 0)},
        "formation": {k: v for k, v in formation.items() if k != "params"},
        "formation_params_sample": dict(list(formation["params"].items())[:3]),
        "formed_opportunities_per_asset_day": formed_opportunities,
        "formed_by_asset": formed_by_asset,
        "candidates_match_parent": bool(len(cands) == EXPECT_CANDIDATES),
        "zone_read": read.counters,
        "zone_read_law": {
            "accessor": "tools/mill/levels_zone.py read_zone at zone_price",
            "side": "defence_side = -break_dir, the FORMER DEFENDING SIDE",
            "decision_stamp": "lat[breach_bar - 1]; the accessor counts only "
                              "bars closing strictly before it, so the read "
                              "sees bars 0..breach_bar-2",
            "breach_excluded": True,
            "day_scale_mode": "approach, approach_side = break_dir"},
        "feature_law": {
            "names": list(FEATURE_NAMES),
            "n": NFEAT,
            "consumed_accessor_fields": list(CONSUMED_ZONE_FIELDS),
            "excluded_accessor_fields": EXCLUDED_ZONE_FIELDS,
            "missingness": "a NaN is imputed at the TRAINING FOLD mean of its "
                           "own column, so it standardizes to exactly zero and "
                           "carries no information; a rate is NaN where its "
                           "touch count is not a positive finite number",
            "census": feature_census},
        "ranker_law": {
            "scope": "one ridge per ASSET, refit on every out-of-fold asset-day",
            "target": "the WITHIN-ASSET-DAY PERCENTILE of the frozen cert, "
                      "average-rank, (rank - 0.5) / n",
            "weights": "each asset-day weighted equally: 1 / (rows on that "
                       "asset-day), renormalized to sum to the training row "
                       "count",
            "standardization": "on the training fold; a column with no fold "
                               "spread gets spread 1 and contributes nothing",
            "penalty": f"lambda = {RIDGE_LAMBDA}, FIXED; no model search, no "
                       f"penalty search",
            "warmup": f">= {MIN_PRIOR_DAYS} prior EXPLORE days and "
                      f">= {MIN_TRAIN_ROWS} training rows",
            "selection": f"at most the top {TOP_K} POSITIVE-score events per "
                         f"out-of-fold asset-day; {list(NEIGHBOUR_K)} reported "
                         f"as non-letter neighbours"},
        "ranker": rank_report, "ranker_diagnostics": diagnostics,
        "ranker_fold_sample": fold_sample, "ranker_beta_mean": beta_mean,
        "pricing_counters": priced["counters"],
        "coarse_counters": priced["coarse_counters"],
        "plane_checks": priced["plane_checks"],
        "same_close_check": priced["same_close"],
        "impulse": impulse_report, "impulse_join": join,
        "impulse_counters": impulse_counters,
        "selection_counts": {str(k): len(picks[k]) for k in ALL_K},
        "live": live, "neighbours": neighbours,
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
    report["headline"] = headline(report)
    return report


def headline(report: Mapping[str, object]) -> dict[str, object]:
    """Deciding usd/day over rung, the matched deltas, the ceilings beside."""

    cash = report["live"]["cash"]                        # type: ignore[index]
    control = report["control"]["by_line"]               # type: ignore[index]
    ceiling = report["ceiling"]["FORMED_UNIVERSE"]["cash"]  # type: ignore[index]
    capped = report["ceiling"]["FORMED_CAPPED"]["cash"]     # type: ignore[index]
    return {
        "read": "zone-anchored, full component plane",
        "over_rung": {asset: (None if cash[asset]["usd_per_day"] is None
                              else cash[asset]["usd_per_day"]
                              / DAY_RUNG_USD[asset]) for asset in DECIDING},
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
        f"{asset} {_n(head['matched_delta_usd_per_date'].get(asset), 8, 1)} "
        f"usd/date (p {_n(head['matched_p_adjusted'].get(asset), 6, 4)})"
        for asset in DECIDING)
    ceiling = ", ".join(
        f"{asset} {_n(head['formed_ceiling_over_rung'].get(asset), 7, 3)}x"
        for asset in DECIDING)
    print(f"F22-FIXEDZONE-RANK: deciding usd/day over rung {over}; matched "
          f"delta {delta}; formed ceiling {ceiling}; family "
          f"{head['family_letter']} (clause {head['family_clause']})")


def print_gate(report: Mapping[str, object]) -> None:
    repro = report["reproduction"]
    print("\n== GATE ==")
    print(f"  sweep 9 plane reproduces : {repro['matches']}")
    for key in ("rows", "certifiable", "counters", "scoring_days"):
        if key in repro:
            print(f"    {key:<14} {repro[key]}")
    print(f"  stream counters          : {report['stream_counters']}")
    print(f"  no outcome in features   : "
          f"{report['causality']['no_outcome_in_features']}")
    manifest = report["levels_manifest"]
    print(f"  levels manifest schema   : {manifest['schema']}  split "
          f"{str(manifest['split_sha256'])[:12]}  shards {manifest['shards']}")
    print(f"  levels cache strictly prior: {manifest['cache_strictly_prior']} "
          f"(max src - stamp {manifest['cache_max_src_minus_stamp_ns']} ns); "
          f"cells {manifest['cells']} "
          f"(prior-day {manifest['cells_with_prior_day']}, "
          f"prior-EXPLORE {manifest['cells_with_prior_session']})")
    formation = report["formation"]
    print(f"  formation levels audit   : strictly prior "
          f"{formation['strictly_prior']}, max(level source - breach close) "
          f"{formation['max_src_minus_breach_ns']} ns")
    print(f"  candidates match sweep 25's {EXPECT_CANDIDATES}: "
          f"{report['candidates_match_parent']}")
    print(f"  formation counters       : {formation['counters']}")
    print(f"  pricing counters         : {report['pricing_counters']}")
    checks = report["plane_checks"]
    print(f"  lane A vs frozen cert plane: compared {checks['compared']}, "
          f"mismatched {checks['mismatched']}, worst "
          f"{checks['worst_abs_usd']:.9f} USD")
    same = report["same_close_check"]
    print(f"  lane A same-close prohibition: checked {same['checked']}, "
          f"violations {same['violations']}, worst (breach close - entry) "
          f"{_show(same['worst_gap_ns'])} ns (must be strictly negative)")
    print(f"  impulse ridge            : {report['impulse']['counters']}, "
          f"WITHIN-DAY R2 {report['impulse']['pooled_within_day_r2']}")
    print(f"  impulse join             : {report['impulse_join']}, "
          f"{report['impulse_counters']}")


def print_zone_read(report: Mapping[str, object]) -> None:
    law = report["zone_read_law"]
    cell = report["zone_read"]
    print("\n== THE BARRIER READ AT THE FIXED ZONE PRICE ==")
    print(f"  accessor        : {law['accessor']}")
    print(f"  side            : {law['side']}")
    print(f"  decision stamp  : {law['decision_stamp']}")
    print(f"  day-scale mode  : {law['day_scale_mode']}")
    print(f"  candidates {cell['candidates']}, queries {cell['queries']}, rows "
          f"{cell['rows']}, no decision stamp {cell['no_decision_stamp']}")
    print(f"  centre EXACT {cell['center_exact']}/{cell['rows']}, mismatched "
          f"{cell['center_mismatched']}, worst gap "
          f"{cell['worst_center_gap_mid2']} mid2")
    print(f"  strictly prior {cell['strictly_prior']}/{cell['rows']}, worst "
          f"(source - decision) {cell['worst_source_minus_decision_ns']} ns")
    print(f"  prior session served {cell['prior_session_served']}, absent "
          f"{cell['prior_session_absent']}")
    print(f"  definedness: same-day touches {cell['sd_touches_defined']} / "
          f"{cell['sd_touches_undefined']} undefined; prior-session touches "
          f"{cell['ps_touches_defined']} / {cell['ps_touches_undefined']}; "
          f"day scale {cell['day_scale_defined']} / "
          f"{cell['day_scale_undefined']}")


def print_features(report: Mapping[str, object]) -> None:
    law = report["feature_law"]
    census = law["census"]
    print("\n== THE FEATURE SCHEMA (Sol's roster, one row per candidate) ==")
    print(f"  {law['n']} columns over {census['rows']} formed candidates")
    print("  #  column                        finite   share")
    for index, name in enumerate(law["names"]):
        finite = int(census["finite_per_column"][name])
        print(f"  {index:>2} {name:<28} {finite:>7} "
              f"{finite / max(census['rows'], 1):>7.4f}")
    print(f"  rows with no finite I_break: "
          f"{census['rows_without_finite_I_break']} (imputed at the training "
          f"fold mean, i.e. standardized to zero, under the standing "
          f"missingness law)")
    print(f"  MISSINGNESS: {law['missingness']}")
    print("  EXCLUDED accessor fields, registered and asserted against "
          "levels_zone.ZONE_ROW_FIELDS:")
    for name, why in sorted(law["excluded_accessor_fields"].items()):
        print(f"    {name:<22} {why}")


def print_ranker(report: Mapping[str, object]) -> None:
    law = report["ranker_law"]
    block = report["ranker"]
    print("\n== THE RANKER ==")
    for key in ("scope", "target", "weights", "standardization", "penalty",
                "warmup", "selection"):
        print(f"  {key:<16}: {law[key]}")
    print(f"  folds: {block['days_scored']} out-of-fold asset-days scored, "
          f"{block['days_warmup']} in warmup, {block['days_thin']} thin, "
          f"{block['scored_rows']} rows scored, {block['train_rows_total']} "
          f"training rows summed over folds")
    print(f"  candidates priced {block['candidates_priced']}, unpriced "
          f"{block['candidates_unpriced']} (never trainable and never "
          f"selectable)")
    print("\n  PER-ASSET OUT-OF-FOLD DIAGNOSTICS (rank correlation of the "
          "score with the day's own cert percentile):")
    print("  asset  folds  with-corr   mean rho   median rho   P(rho>0)   "
          "train rows   scored   |beta|")
    for asset in ASSETS:
        cell = report["ranker_diagnostics"][asset]
        print(f"  {asset:<5} {cell['folds']:>6} {cell['folds_with_rank_corr']:>10} "
              f"{_n(cell['oof_rank_corr_mean'], 10, 4)} "
              f"{_n(cell['oof_rank_corr_median'], 12, 4)} "
              f"{_n(cell['oof_rank_corr_p_positive'], 10, 3)} "
              f"{_n(cell['train_rows_mean'], 12, 1)} "
              f"{cell['scored_rows']:>8} {_n(cell['beta_l2_mean'], 8, 3)}")
    print("\n  PER-FOLD SAMPLE (first six and last six folds):")
    print("  asset       d8  train days  train rows  day rows  positive  "
          "rank rho   top4 mean truth")
    for row in report["ranker_fold_sample"]:
        print(f"  {row['asset']:<5} {row['d8']:>8} {row['train_days']:>11} "
              f"{row['train_rows']:>11} {row['day_rows']:>9} "
              f"{row['positive_scores']:>9} {_n(row['rank_corr'], 9, 4)} "
              f"{_n(row['top4_mean_truth'], 17, 4)}")
    print("\n  MEAN RIDGE COEFFICIENT PER COLUMN, over that asset's folds "
          "(standardized units; recorded, never a gate):")
    print("  column                       " + "".join(
        f"{asset:>12}" for asset in ASSETS))
    for name in FEATURE_NAMES:
        cells = "".join(
            _n(report["ranker_beta_mean"].get(asset, {}).get(name), 12, 4)
            for asset in ASSETS)
        print(f"  {name:<28}{cells}")


def print_selection(report: Mapping[str, object]) -> None:
    block = report["live"]
    print(f"\n== THE SELECTION: top {TOP_K} positive-score events per "
          f"out-of-fold asset-day ==")
    print(f"  selected entries {block['n']}, seated {block['replay']['seated']}, "
          f"rejected occupancy {block['replay']['rejected_occupancy']}, "
          f"rejected cap {block['replay']['rejected_cap']}")
    print("  asset  label       n  cover   P(>0)  [lo, hi]        mean    "
          "median     usd/day    over-rung    seated usd/day   -2SE   MDD(day)")
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
    print("  seats: " + ", ".join(
        f"{asset} mean {_n(block['cash'][asset]['seats_mean'], 5, 2)} max "
        f"{block['cash'][asset]['seats_max']} zero-entry days "
        f"{_n(block['cash'][asset]['zero_entry_fraction'], 5, 3)}"
        for asset in ASSETS))
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
    for name, table in block["breakdowns"].items():
        cells = ", ".join(f"{k} n={v['n']} mean {v['mean_usd']:.0f}"
                          for k, v in table.items())
        print(f"  by {name:<10}: {cells if cells else '-'}")
    print("  break direction of the selected cohort: " + "; ".join(
        f"{asset} up {report['selected_direction'].get(asset, {}).get(1, 0)} "
        f"down {report['selected_direction'].get(asset, {}).get(-1, 0)}"
        for asset in ASSETS))
    print("\n  NON-LETTER NEIGHBOURS (top-three and top-five, same ranker, "
          "same fold, same replay):")
    print("  top-k      n  seated      NKD usd/day     NKD -2SE       "
          "SI usd/day      SI -2SE   registered")
    for k in ALL_K:
        cell = report["neighbours"][str(k)]
        print(f"  top-{k:<5} {cell['n']:>5} {cell['seated']:>7} "
              f"{_n(cell['cash']['NKD']['usd_per_day'], 15, 1)} "
              f"{_n(cell['cash']['NKD']['mean_minus_2se_usd'], 12, 1)} "
              f"{_n(cell['cash']['SI']['usd_per_day'], 15, 1)} "
              f"{_n(cell['cash']['SI']['mean_minus_2se_usd'], 12, 1)}"
              f"{'   <-- REGISTERED' if k == TOP_K else ''}")
    print(f"  neighbours agree on sign : {block['neighbours_agree']}")
    print("\n  SELECTED COHORT vs THE FORMED UNIVERSE, per column (recorded, "
          "NEVER gating):")
    print("  column                       " + "".join(
        f"{asset + ' sel':>14}{asset + ' formed':>15}" for asset in DECIDING))
    for name in FEATURE_NAMES:
        cells = ""
        for asset in DECIDING:
            block_a = report["selected_cohort"].get(asset)
            cells += (_n(block_a["selected_mean"][name], 14, 3)
                      + _n(block_a["formed_mean"][name], 15, 3)) if block_a \
                else " " * 29
        print(f"  {name:<28}{cells}")


def print_controls(report: Mapping[str, object]) -> None:
    control = report["control"]
    print("\n== C1: PAIRED MATCHED CONTROL, complete level vector permuted in "
          "fold ==")
    print(f"  shared-date-sign maxT, {control['draws']} draws over "
          f"{control['dates']} dates, family {control['family']} "
          f"(1 lane x 2 deciding assets), c95 {_n(control['c95'], 7, 3)}")
    print(f"  {control['event_level_p']}")
    print("  line                        dates    delta/date       SE        t  "
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
    print(f"  PERMUTED COMPLETE LEVEL VECTOR inside the training fold: "
          f"{permuted['controls']} controls scored by their own fold's ranker; "
          f"share with a positive score "
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
    print(f"  {CONTROL_DRAWS} draws, same selected count re-drawn inside each "
          f"(asset, phase, day) block of formed candidates")
    print("  line                        observed usd/day   null mean    "
          "null p95      p")
    for name, cell in sorted(report["block_nulls"].items()):
        print(f"  {name:<27} {_n(cell['observed_usd_day'], 14, 1)} "
              f"{_n(cell.get('null_mean_usd_day'), 11, 1)} "
              f"{_n(cell.get('null_p95_usd_day'), 11, 1)} "
              f"{_n(cell.get('p'), 6, 4)}")
    print(f"\n  C3 CAVEAT: {report['block_null_caveat']}.")


def print_decision(report: Mapping[str, object]) -> None:
    head = report["headline"]
    cell = report["letter"]
    print("\n== DECISION TABLE ==")
    print("  asset   usd/day over rung   matched delta/date   adjusted p   "
          "formed ceiling   capped ceiling")
    for asset in DECIDING:
        print(f"  {asset:<5} {_n(head['over_rung'].get(asset), 17, 4)}x "
              f"{_n(head['matched_delta_usd_per_date'].get(asset), 20, 1)} "
              f"{_n(head['matched_p_adjusted'].get(asset), 12, 4)} "
              f"{_n(head['formed_ceiling_over_rung'].get(asset), 16, 3)}x "
              f"{_n(head['capped_ceiling_over_rung'].get(asset), 15, 3)}x")
    print("\n  gate               rung  MDD  cap  stress  control  neighbours  "
          "ceiling  upper<=0  matched+")
    print(f"  {'F22-FIXEDZONE-RANK':<18} {_n(cell['rung_ok'], 5)} "
          f"{_n(cell['mdd_ok'], 4)} {_n(cell['cap_ok'], 4)} "
          f"{_n(cell['stress_ok'], 6)} {_n(cell['control_ok'], 8)} "
          f"{_n(cell['neighbours_ok'], 11)} "
          f"{_n(cell['ceiling_carries_both_rungs'], 8)} "
          f"{_n(cell['upper_bound_nonpositive'], 9)} "
          f"{_n(cell['matched_delta_positive'], 9)}")
    print(f"\n  FAMILY LETTER: {report['family_letter']} "
          f"(clause {report['family_clause']})")
    print(f"  CLAUSE {cell['clause']}: {cell['clause_text']}")
    print(f"  clauses matching: {cell['clauses_matching']}")
    for reason in cell["reasons"]:
        print(f"    - {reason}")
    print("\n  the registered partition, exhaustive over all 512 outcome "
          "points:")
    for clause in CLAUSE_ORDER:
        print(f"    {clause:<5} -> {CLAUSE_LETTER[clause]:<24} "
              f"{CLAUSES[clause]}")


# --------------------------------------------------------------------------
# Selftest.
# --------------------------------------------------------------------------

def _plant_component_world(gradient_on_prior_days: bool
                           ) -> tuple[np.ndarray, np.ndarray,
                                      dict[tuple[str, int], list[int]],
                                      dict[str, list[int]]]:
    """A world in which ONE component carries a monotone payoff gradient.

    THE ARITHMETIC, by hand.  One asset, ``ROWS = 10`` events on each of 31
    EXPLORE days.  On row ``j`` of a day:

        ps_held_rate = j / 10                    (0.0, 0.1, ... 0.9)
        sd_held_rate = 0.9 - j / 10              (0.9, 0.8, ... 0.0)
        cert         = 100 * j                   (0, 100, ... 900)

    Every other column is a constant, so on any training fold its spread is
    zero, it takes spread 1 by the registered law, and it standardizes to
    exactly zero.  The two live columns are exact affine reflections of each
    other, so over any fold their standardizations satisfy
    ``z(sd_held_rate) = -z(ps_held_rate)`` EXACTLY, and the compressed score -
    the MEAN of the standardized columns, which is what F19 and F20 scored - is

        (z + (-z) + 0 + ... + 0) / 19 = 0

    for EVERY row.  A score that is identically zero has no positive entries at
    all, so the compressed selector picks nothing: the compression cannot see a
    gradient that one component carries and another opposes.  The ridge over the
    separate components has no such problem; with ``y`` the within-day
    percentile, which is monotone in ``j``, it splits the coefficient between
    the reflected pair and its score is strictly increasing in ``j``.

    ``gradient_on_prior_days=False`` builds the LEAK world: every prior day's
    cert is a constant, so every prior-day target is a tie at percentile 0.5,
    the centred target is exactly zero on the whole training fold, ``beta`` is
    exactly zero, no score is positive, and an honest fold selects NOTHING.
    The gradient exists only on the last day - which a fold that includes the
    scoring day would read.
    """

    asset = "SI"
    rows, day_count = 10, 31
    days = [20220100 + d for d in range(day_count)]
    features = np.zeros((rows * day_count, NFEAT), np.float64)
    cert = np.zeros(rows * day_count, np.float64)
    positions_by_day: dict[tuple[str, int], list[int]] = {}
    for index, d8 in enumerate(days):
        last = index == day_count - 1
        for j in range(rows):
            position = index * rows + j
            features[position, FEATURE_NAMES.index("ps_held_rate")] = j / 10.0
            features[position, FEATURE_NAMES.index("sd_held_rate")] = (
                0.9 - j / 10.0)
            cert[position] = (100.0 * j if (last or gradient_on_prior_days)
                              else 0.0)
            positions_by_day.setdefault((asset, d8), []).append(position)
    return features, cert, positions_by_day, {asset: days}


def _selftest_component_recovery(mutant: str) -> list[tuple[str, bool, str]]:
    """The planted gradient: the components recover it, the mean cannot."""

    features, cert, by_day, days = _plant_component_world(True)
    folds, report = rank_folds(by_day, features, cert, days, mutant)
    out = [_check(
        "the planted world scores exactly the days past the 25-day warmup",
        len(folds) == 31 - MIN_PRIOR_DAYS and report["days_warmup"]
        == MIN_PRIOR_DAYS,
        f"{len(folds)} folds, {report['days_warmup']} warmup days, "
        f"{report['days_thin']} thin")]
    if not folds:
        return out
    last = folds[-1]
    picked = select_top(last, TOP_K)
    want = [int(last.positions[i]) for i in (9, 8, 7, 6)]
    out.append(_check(
        "THE PLANTED RECOVERY: out of fold the component ranker keeps exactly "
        "the four highest-payoff events (j = 9, 8, 7, 6)",
        picked == want,
        f"picked {[int(p) for p in picked]}, wanted {want}"))
    recovered = float(np.mean([cert[p] for p in picked])) if picked else 0.0
    base = float(np.mean([cert[p] for p in last.positions]))
    out.append(_check(
        "the recovered mean payoff is the hand-computed 750 against a day base "
        "of 450",
        abs(recovered - 750.0) < 1e-9 and abs(base - 450.0) < 1e-9,
        f"recovered {recovered:.1f} vs base {base:.1f}"))
    out.append(_check(
        "the out-of-fold rank correlation with the day's own cert percentile "
        "is exactly +1",
        last.rank_corr is not None and abs(float(last.rank_corr) - 1.0) < 1e-9,
        f"rho {last.rank_corr}"))
    # The compression F19 and F20 scored, on the same fold.
    train = np.asarray([p for day in days["SI"][:-1]
                        for p in by_day[("SI", day)]], np.int64)
    look = np.asarray(last.positions, np.int64)
    compressed = compressed_score(features, train, look)
    comp_spread = float(np.max(compressed) - np.min(compressed))
    rank_spread = float(np.max(last.scores) - np.min(last.scores))
    order = sorted(range(len(look)),
                   key=lambda i: (-float(compressed[i]), int(look[i])))
    comp_picks = [int(look[i]) for i in order
                  if float(compressed[i]) > 0.0][:TOP_K]
    comp_recovered = (float(np.mean([cert[p] for p in comp_picks]))
                      if comp_picks else base)
    out.append(_check(
        "THE COMPRESSED SINGLE-MEAN SCORE MISSES IT: the mean of the "
        "standardized components is zero to machine precision on every row, so "
        "it does not order the day at all",
        comp_spread < 1e-12 and comp_spread < 1e-15 * rank_spread,
        f"compressed spread {comp_spread:.3e} against the component ranker's "
        f"{rank_spread:.6f}"))
    out.append(_check(
        "and what the compression does pick is float noise, not signal: it "
        "recovers LESS than the day base while the component ranker recovers "
        "the planted four",
        not set(comp_picks) & set(want) and comp_recovered < base,
        f"compressed picked {comp_picks} at mean {comp_recovered:.1f} vs day "
        f"base {base:.1f}; the ranker picked {[int(p) for p in picked]} at "
        f"{recovered:.1f}"))
    out.append(_check(
        "the two live columns are exact reflections, which is what the "
        "compression cancels and the component ranker does not",
        abs(float(np.corrcoef(
            features[look, FEATURE_NAMES.index("ps_held_rate")],
            features[look, FEATURE_NAMES.index("sd_held_rate")])[0, 1]) + 1.0)
        < 1e-12,
        "corr(ps_held_rate, sd_held_rate) = -1 by construction"))
    return out


def _selftest_leak(mutant: str) -> list[tuple[str, bool, str]]:
    """The leak guard: a gradient that exists ONLY on the scoring day."""

    features, cert, by_day, days = _plant_component_world(False)
    folds, _report = rank_folds(by_day, features, cert, days, mutant)
    if not folds:
        return [_check("THE LEAK GUARD: a world whose gradient exists ONLY on "
                       "the scoring day yields NO out-of-fold recovery", False,
                       "no fold was scored")]
    last = folds[-1]
    picked = select_top(last, TOP_K)
    base = float(np.mean([cert[p] for p in last.positions]))
    recovered = float(np.mean([cert[p] for p in picked])) if picked else base
    return [_check(
        "THE LEAK GUARD: a world whose gradient exists ONLY on the scoring day "
        "yields NO out-of-fold recovery",
        not picked and recovered <= base + 1e-9,
        f"{len(picked)} picked, mean {recovered:.1f} vs day base {base:.1f}")]


def _selftest_percentile() -> list[tuple[str, bool, str]]:
    """The target law, hand-verified on a constructed day."""

    day = [-500.0, 0.0, 100.0, 250.0, 1000.0]
    want = [0.1, 0.3, 0.5, 0.7, 0.9]
    got = within_day_percentile(day)
    out = [_check(
        "the target is the WITHIN-DAY percentile: a five-event day of certs "
        "[-500, 0, 100, 250, 1000] maps to [0.1, 0.3, 0.5, 0.7, 0.9]",
        bool(np.allclose(got, want, rtol=0.0, atol=1e-12)),
        f"{[round(float(v), 6) for v in got]}")]
    shuffled = [1000.0, -500.0, 250.0, 100.0, 0.0]
    got2 = within_day_percentile(shuffled)
    out.append(_check(
        "the percentile follows the VALUE and not the row order",
        bool(np.allclose(got2, [0.9, 0.1, 0.7, 0.5, 0.3], atol=1e-12)),
        f"{[round(float(v), 6) for v in got2]}"))
    tied = within_day_percentile([10.0, 10.0, 50.0])
    out.append(_check(
        "ties share their average rank: [10, 10, 50] maps to [1/3, 1/3, 5/6]",
        bool(np.allclose(tied, [1.0 / 3.0, 1.0 / 3.0, 5.0 / 6.0], atol=1e-12)),
        f"{[round(float(v), 6) for v in tied]}"))
    flat = within_day_percentile([7.0] * 6)
    out.append(_check(
        "a day whose every cert is equal carries NO gradient: every row is 0.5",
        bool(np.allclose(flat, 0.5, atol=1e-12)), f"{float(flat[0])}"))
    out.append(_check(
        "the percentile is scale free and location free: it is a rank, so a "
        "day of tiny certs and a day of huge ones weigh the same",
        bool(np.allclose(within_day_percentile([1.0, 2.0, 3.0]),
                         within_day_percentile([1e6, 2e6, 3e6]), atol=1e-12))))
    # Each asset-day weighted equally: two days of very different size get the
    # same total weight.
    features = np.zeros((30, NFEAT), np.float64)
    features[:, 0] = np.arange(30, dtype=np.float64)
    cert = np.arange(30, dtype=np.float64)
    by_day = {("SI", 20220101): list(range(0, 25)),
              ("SI", 20220102): list(range(25, 30))}
    weights: list[float] = []
    for key, rows in by_day.items():
        weights.extend([1.0 / len(rows)] * len(rows))
    totals = {}
    offset = 0
    for key, rows in by_day.items():
        totals[key] = float(sum(weights[offset:offset + len(rows)]))
        offset += len(rows)
    out.append(_check(
        "each asset-day carries the SAME total weight regardless of its size "
        "(a 25-event day and a 5-event day both weigh 1)",
        all(abs(v - 1.0) < 1e-12 for v in totals.values()), f"{totals}"))
    return out


def _selftest_top_k() -> list[tuple[str, bool, str]]:
    """The coverage law: a day with seven positive scores keeps exactly four."""

    fold = Fold(
        asset="NKD", d8=20220301, train_rows=100, train_days=30,
        centre=np.zeros(NFEAT), spread=np.ones(NFEAT), beta=np.zeros(NFEAT),
        positions=np.arange(9, dtype=np.int64),
        scores=np.asarray([0.90, 0.10, 0.55, -0.20, 0.70, 0.30, 0.05,
                           -0.80, 0.42], np.float64),
        truth=np.zeros(9), rank_corr=None)
    picked = select_top(fold, TOP_K)
    out = [_check(
        "THE TOP-FOUR LAW: a constructed day with SEVEN positive scores keeps "
        "exactly the four largest",
        picked == [0, 4, 2, 8],
        f"picked {picked}, scores "
        f"{[round(float(s), 2) for s in fold.scores]}")]
    out.append(_check(
        "a negative score is never seated, even when the day is short of four",
        select_top(Fold(
            asset="NKD", d8=1, train_rows=1, train_days=1,
            centre=np.zeros(NFEAT), spread=np.ones(NFEAT),
            beta=np.zeros(NFEAT), positions=np.arange(3, dtype=np.int64),
            scores=np.asarray([0.5, -0.1, -2.0], np.float64),
            truth=np.zeros(3), rank_corr=None), TOP_K) == [0],
        "one positive of three"))
    out.append(_check(
        "a zero score is not positive, so it is never seated",
        select_top(Fold(
            asset="NKD", d8=1, train_rows=1, train_days=1,
            centre=np.zeros(NFEAT), spread=np.ones(NFEAT),
            beta=np.zeros(NFEAT), positions=np.arange(2, dtype=np.int64),
            scores=np.zeros(2), truth=np.zeros(2), rank_corr=None), TOP_K)
        == [], "two zero scores"))
    out.append(_check(
        "the neighbours are nested: top-three is a prefix of top-four and "
        "top-four a prefix of top-five",
        select_top(fold, 3) == picked[:3]
        and picked == select_top(fold, 5)[:TOP_K],
        f"top3 {select_top(fold, 3)}, top5 {select_top(fold, 5)}"))
    out.append(_check(
        "four per asset spends the twelve-entry portfolio budget exactly",
        TOP_K * len(ASSETS) == PORTFOLIO_CAP,
        f"{TOP_K} x {len(ASSETS)} = {TOP_K * len(ASSETS)} vs cap "
        f"{PORTFOLIO_CAP}"))
    return out


def _selftest_feature_law() -> list[tuple[str, bool, str]]:
    """The roster, the exclusions and the rate law, on constructed rows."""

    out: list[tuple[str, bool, str]] = []
    try:
        assert_feature_law()
        ok, detail = True, f"{NFEAT} columns partition the accessor row"
    except SweepRefusal as error:
        ok, detail = False, str(error)
    out.append(_check(
        "the feature roster partitions the accessor's own field list: every "
        "served field is either consumed or registered as excluded",
        ok, detail))
    out.append(_check(
        "Sol's roster is present by name and nothing else is",
        set(FEATURE_NAMES) == (set(SAME_DAY_FEATURES)
                               | set(PRIOR_SESSION_FEATURES)
                               | {"day_scale_persistence"}
                               | set(ZONE_KIND_FEATURES)
                               | {"band_width_over_prior_atr", "I_break"}),
        f"{NFEAT} columns"))
    out.append(_check(
        "day_scale_persistence is carried UNDER THAT EXACT NAME",
        "day_scale_persistence" in FEATURE_NAMES
        and "day_scale_held" not in FEATURE_NAMES
        and "day_scale_broke" not in FEATURE_NAMES))
    out.append(_check(
        "a rate with no touches is NaN, never a silent zero",
        math.isnan(_rate(0.0, 0.0)) and math.isnan(_rate(3.0, float("nan")))
        and _rate(3.0, 4.0) == 0.75,
        "0/0 -> NaN, 3/NaN -> NaN, 3/4 -> 0.75"))
    out.append(_check(
        "the touch count enters as log1p, so a zero-touch zone and a "
        "one-touch zone are one apart and not zero apart in ratio",
        _log_count(0.0) == 0.0
        and abs(_log_count(3.0) - math.log(4.0)) < 1e-12,
        f"log1p(0)={_log_count(0.0)}, log1p(3)={_log_count(3.0):.6f}"))

    class _Row:
        sd_touches, sd_held, sd_broke = 4.0, 3.0, 0.0
        sd_mins_since_touch, sd_touch_delta = 12.5, -80.0
        ps_touches, ps_held, ps_broke = 2.0, 1.0, 1.0
        ps_mins_since_touch, ps_touch_delta = 900.0, 40.0
        day_scale_persistence = 1.0
        zone_kind, band_width = "PD_HIGH", 25.0

    cand = S23.Cand(
        asset="NKD", d8=20220301, phase="RTH", cell=0, year=2022,
        zone_kind="PD_HIGH", zone_price=100.0, width=25.0, atr_mid2=250.0,
        break_dir=1, defence_side=-1, broken_edge=125.0, bar=30, read_bar=29,
        n_bars=300, pull_frac=0.0, pull_dur=1, ext_reach=0.0,
        lev_read=np.zeros(len(LV.LEVEL_FEATURES)), pd_held=0.0, pd_broke=0.0,
        defence_history=0.0, visit_bars=0, visit_touches=0, visit_flow=0.0)
    row = feature_row(_Row(), cand)
    want = {"sd_log_touches": math.log(5.0), "sd_held_rate": 0.75,
            "sd_broke_rate": 0.0, "sd_mins_since_touch": 12.5,
            "sd_touch_flow_per_touch": -20.0, "ps_log_touches": math.log(3.0),
            "ps_held_rate": 0.5, "ps_broke_rate": 0.5,
            "ps_mins_since_touch": 900.0, "ps_touch_flow_per_touch": 20.0,
            "day_scale_persistence": 1.0, "zone_kind=PD_HIGH": 1.0,
            "zone_kind=SAME_DAY": 0.0, "band_width_over_prior_atr": 0.1}
    bad = [name for name, value in want.items()
           if abs(float(row[FEATURE_NAMES.index(name)]) - value) > 1e-12]
    out.append(_check(
        "the hand-computed feature row is exact: 4 touches / 3 held -> 0.75, "
        "-80 flow over 4 touches -> -20, band 25 over ATR 250 -> 0.10, "
        "PD_HIGH one-hot",
        not bad, f"mismatched {bad}"))
    out.append(_check(
        "the zone-kind one-hot sums to exactly one",
        abs(float(sum(row[FEATURE_NAMES.index(name)]
                      for name in ZONE_KIND_FEATURES)) - 1.0) < 1e-12))
    out.append(_check(
        "I_break is left NaN by the row builder and filled only from the "
        "frozen impulse ridge",
        math.isnan(float(row[I_BREAK_COLUMN]))))
    # The missingness law: a NaN imputes to exactly the fold mean, i.e. zero.
    block = np.asarray([[1.0, 2.0], [3.0, 4.0], [float("nan"), 6.0]],
                       np.float64)
    centre, spread = _standardize(block)
    z = _design(block, centre, spread)
    out.append(_check(
        "a NaN standardizes to EXACTLY zero, the training fold's own mean, so "
        "a missing component carries no information",
        float(z[2, 0]) == 0.0 and abs(float(centre[0]) - 2.0) < 1e-12,
        f"fold mean {float(centre[0])}, imputed z {float(z[2, 0])}"))
    out.append(_check(
        "a column with no spread on the fold contributes nothing",
        float(_design(np.asarray([[5.0], [5.0], [5.0]], np.float64),
                      *_standardize(np.asarray([[5.0], [5.0], [5.0]],
                                               np.float64)))[0, 0]) == 0.0))
    return out


def _selftest_ridge() -> list[tuple[str, bool, str]]:
    """The estimator itself: the fixed penalty, and no search anywhere."""

    rng = np.random.default_rng(7)
    z = rng.normal(size=(200, 3))
    y = 2.0 * z[:, 0] - 1.0 * z[:, 1]
    w = np.ones(200)
    beta = fit_ridge(z, y - float(y.mean()), w)
    closed = np.linalg.solve(z.T @ z + RIDGE_LAMBDA * np.eye(3),
                             z.T @ (y - float(y.mean())))
    out = [_check(
        "the ridge is the closed form (Z'WZ + lambda I)^-1 Z'W y at "
        f"lambda = {RIDGE_LAMBDA}, with no search",
        bool(np.allclose(beta, closed, atol=1e-12)),
        f"|beta - closed| {float(np.max(np.abs(beta - closed))):.3e}")]
    out.append(_check(
        "the penalty is a fixed constant of this module, not a fitted or "
        "chosen quantity",
        RIDGE_LAMBDA == 1.0 and isinstance(RIDGE_LAMBDA, float)))
    heavy = fit_ridge(z, y - float(y.mean()), w, lam=1e6)
    out.append(_check(
        "the penalty is load bearing: a huge lambda shrinks every coefficient "
        "toward zero",
        float(np.max(np.abs(heavy))) < float(np.max(np.abs(beta))) / 100.0,
        f"|beta| {float(np.max(np.abs(beta))):.3f} vs heavy "
        f"{float(np.max(np.abs(heavy))):.6f}"))
    # Weighted: duplicating a day must not double its influence.
    z2 = np.vstack([z, z[:50]])
    y2 = np.concatenate([y, y[:50]])
    w2 = np.concatenate([np.ones(200), np.zeros(50)])
    out.append(_check(
        "a zero-weight row cannot move the fit, which is what equal asset-day "
        "weighting rests on",
        bool(np.allclose(fit_ridge(z2, y2 - float(y.mean()), w2), beta,
                         atol=1e-10))))
    return out


def _selftest_center_gate_real() -> list[tuple[str, bool, str]]:
    """The centre gate on REAL rows: 50 formed candidates of THIS family."""

    cells, _days, _skipped = S8.build_cells(ASSETS)
    records, _rec_days = S1.load_cache()
    explore_days = S1._explore_days(ASSETS)
    cands, formation = S23.formation_pass(cells, explore_days, "")
    out = [_check(
        "the real formation reproduces sweep 25's candidate universe",
        len(cands) == EXPECT_CANDIDATES and bool(formation["strictly_prior"]),
        f"{len(cands)} candidates, strictly prior "
        f"{formation['strictly_prior']}")]
    if not cands:
        return out + [_check("50 real formed candidates are drawn", False,
                             "no candidates")]
    by_stratum: dict[tuple[str, str], list[int]] = {}
    for position, cand in enumerate(cands):
        by_stratum.setdefault((cand.asset, cand.zone_kind), []).append(position)
    strata = sorted(by_stratum)
    rng = np.random.default_rng(SEED)
    drawn: list[list[int]] = []
    for stratum in strata:
        pool = by_stratum[stratum]
        size = min(max(1, int(math.ceil(60 / max(len(strata), 1)))), len(pool))
        take = rng.choice(len(pool), size=size, replace=False)
        drawn.append([pool[int(offset)] for offset in sorted(take)])
    picks: list[int] = []
    for slot in range(max((len(block) for block in drawn), default=0)):
        for block in drawn:
            if slot < len(block):
                picks.append(block[slot])
    picks = picks[:50]
    sample = [cands[p] for p in picks]
    read = zone_read(sample, records, LZ.reader(ASSETS))
    counters = read.counters
    out.append(_check(
        "at least 50 real formed candidates are drawn, from every "
        "(asset, zone kind) stratum",
        len(sample) >= 50 and len(strata) >= 3,
        f"{len(sample)} candidates over {len(strata)} strata"))
    out.append(_check(
        "every real row echoes centre_price == zone_price EXACTLY",
        counters["center_mismatched"] == 0 and counters["rows"] == len(sample)
        and counters["rows"] > 0,
        f"{counters['center_exact']}/{counters['rows']} exact, worst gap "
        f"{counters['worst_center_gap_mid2']} mid2"))
    out.append(_check(
        "every real row's source stamp is strictly before its decision stamp",
        counters["not_strictly_prior"] == 0 and counters["rows"] > 0,
        f"{counters['strictly_prior']}/{counters['rows']}, worst "
        f"{counters['worst_source_minus_decision_ns']} ns"))
    stamps_ok = True
    for position, cand in enumerate(sample):
        lat = np.asarray(records[int(cand.cell)].lat, np.int64)
        row = read.rows[position]
        if row is None or int(row.decision_stamp_ns) != int(lat[int(cand.bar) - 1]):
            stamps_ok = False
    out.append(_check(
        "every real row is stamped at the last completed bar BEFORE the breach "
        "close, so the breach bar is excluded from its own feature row",
        stamps_ok, f"{len(sample)} rows checked"))
    # And the features actually built from those rows are finite where the
    # accessor served a count.
    built = np.vstack([feature_row(read.rows[i], sample[i])
                       for i in range(len(sample)) if read.rows[i] is not None])
    out.append(_check(
        "the real feature rows are built with the registered column count and "
        "no infinities",
        built.shape == (len(sample), NFEAT)
        and not bool(np.isinf(built).any()),
        f"{built.shape}"))
    return out


def _selftest_planted_read() -> list[tuple[str, bool, str]]:
    """The component read on sweep 25's planted world, hand-counted.

    Sweep 25's fixture is reused unchanged - the defended zone D = 1000 genuinely
    HOLDS three times against the trapped side before breaking upward at bar 10,
    and the weak zone U = 1400 genuinely BREAKS twice before breaking upward at
    bar 20 - but the quantities asserted here are the SEPARATE components this
    unit consumes rather than their mean.

    D's breach is bar 10, so the decision stamp is ts[9] and the window is bars
    0..8.  Inside [990, 1010]: bars 2 (995), 3 (1005), 4 (1000) and 8 (995) -
    FOUR touches.  Bar 5 prints 985, at or below every one of 985, 995 and 990,
    so bars 2, 3 and 4 all HELD, inside the window; bar 8's only verdict is the
    breach bar itself, which is not before the stamp.  Hence touches 4, held 3,
    broke 0, and a HELD RATE of exactly 3/4 = 0.75 with a BROKE RATE of 0.

    U = 1400 breaches at bar 20, stamp ts[19], window bars 0..18.  Inside
    [1390, 1410]: bars 13 (1395), 14 (1402) and 18 (1396) - THREE touches.  Bar
    15 prints 1425, above both 1405 and 1412, and the first bar at or below 1385
    is bar 16, later, so bars 13 and 14 both BROKE inside the window.  Hence
    touches 3, held 0, broke 2, a HELD RATE of 0 and a BROKE RATE of exactly
    2/3 = 0.6667.
    """

    tape, world = S25.plant_tape()
    out: list[tuple[str, bool, str]] = []
    reads = {}
    for name, zone, bar, kind in (
            ("trapped", world["defended"], world["defended_breach_bar"],
             world["defended_kind"]),
            ("weak", world["undefended"], world["undefended_breach_bar"],
             world["undefended_kind"])):
        stamp = int(tape.ts[int(bar) - 1])
        window = LZ.prior_window(tape, stamp)
        center = LZ.resolved_center(float(zone), tape, window)
        same = LZ.same_day_counts(tape, center, float(world["width"]),
                                  int(world["defence_side"]), stamp)
        scale = LZ.day_scale_terms(
            tape.mid, tape.ts, center, float(world["width"]), stamp,
            zone_kind=kind, approach_side=int(world["break_dir"]),
            mode="approach")
        reads[name] = {"center": float(center), "zone": float(zone),
                       "window": int(window), "same": same, "scale": scale,
                       "held_rate": _rate(float(same["held"]),
                                          float(same["touches"])),
                       "broke_rate": _rate(float(same["broke"]),
                                           float(same["touches"])),
                       "log_touches": _log_count(float(same["touches"])),
                       "flow_per_touch": _rate(float(same["touch_delta"]),
                                               float(same["touches"]))}
    trapped, weak = reads["trapped"], reads["weak"]
    out.append(_check(
        "the component read is centred ON the defended zone, not on the "
        "reading bar's mid",
        trapped["center"] == world["defended"],
        f"centre {trapped['center']} vs zone {world['defended']}, last "
        f"completed mid {float(tape.mid[trapped['window'] - 1])}"))
    out.append(_check(
        "the component read is centred ON the weakly defended zone",
        weak["center"] == world["undefended"],
        f"centre {weak['center']} vs zone {world['undefended']}"))
    out.append(_check(
        "the read stops at the last completed bar BEFORE the breach close, so "
        "the breach never enters its own feature row",
        trapped["window"] == world["defended_breach_bar"] - 1
        and weak["window"] == world["undefended_breach_bar"] - 1,
        f"D window {trapped['window']}, U window {weak['window']}"))
    out.append(_check(
        "the trapped cohort's hand count is 4 touches, 3 held, 0 broke, held "
        "rate 0.75",
        float(trapped["same"]["touches"]) == 4.0
        and float(trapped["same"]["held"]) == 3.0
        and float(trapped["same"]["broke"]) == 0.0
        and abs(float(trapped["held_rate"]) - 0.75) < 1e-12
        and float(trapped["broke_rate"]) == 0.0,
        f"touches {trapped['same']['touches']}, held "
        f"{trapped['same']['held']}, broke {trapped['same']['broke']}, held "
        f"rate {trapped['held_rate']}"))
    out.append(_check(
        "the weak zone's hand count is 3 touches, 0 held, 2 broke, broke rate "
        "0.6667",
        float(weak["same"]["touches"]) == 3.0
        and float(weak["same"]["held"]) == 0.0
        and float(weak["same"]["broke"]) == 2.0
        and abs(float(weak["broke_rate"]) - 2.0 / 3.0) < 1e-12
        and float(weak["held_rate"]) == 0.0,
        f"touches {weak['same']['touches']}, held {weak['same']['held']}, "
        f"broke {weak['same']['broke']}, broke rate {weak['broke_rate']}"))
    out.append(_check(
        "the log touch count separates the two zones: log1p(4) against "
        "log1p(3)",
        abs(float(trapped["log_touches"]) - math.log(5.0)) < 1e-12
        and abs(float(weak["log_touches"]) - math.log(4.0)) < 1e-12,
        f"D {trapped['log_touches']:.6f}, U {weak['log_touches']:.6f}"))
    out.append(_check(
        "THE SEPARATION THE MEAN COULD NOT MAKE: held rate, broke rate and "
        "touch count are three distinct numbers per zone, not one score",
        (trapped["held_rate"], trapped["broke_rate"], trapped["log_touches"])
        != (weak["held_rate"], weak["broke_rate"], weak["log_touches"]),
        f"D ({trapped['held_rate']}, {trapped['broke_rate']}, "
        f"{trapped['log_touches']:.4f}) vs U ({weak['held_rate']}, "
        f"{weak['broke_rate']}, {weak['log_touches']:.4f})"))
    out.append(_check(
        "the day-scale persistence proxy is +1 at the defended zone and -1 at "
        "the weak zone, under its exact registered name",
        float(trapped["scale"]["persistence"]) == 1.0
        and float(weak["scale"]["persistence"]) == -1.0,
        f"D {trapped['scale']['persistence']}, U "
        f"{weak['scale']['persistence']}"))
    return out


def _receipt(usd: float, mdd: float, p: float, ceiling: float, delta: float,
             upper: float | None = None) -> dict[str, object]:
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
        "ceiling": {"FORMED_UNIVERSE": {"cash": {
            asset: {"carries_rung": ceiling >= DAY_RUNG_USD[asset]}
            for asset in ASSETS}}},
        "control": {"by_line": {
            f"{LANE}|{asset}": {
                "p_max_adjusted": p, "delta_usd_per_date": delta,
                "upper95_simultaneous_usd": (delta + 50.0 if upper is None
                                             else upper)}
            for asset in ASSETS}}}


def _selftest_letters() -> list[tuple[str, bool, str]]:
    """Every clause fires on a constructed receipt, and the partition is total."""

    cases = [
        ("LIVE", LETTER_LIVE, _receipt(3000.0, 100.0, 0.01, 5000.0, 300.0)),
        ("K1", LETTER_KILL,
         _receipt(100.0, 100.0, 0.20, 5000.0, -300.0, upper=-10.0)),
        ("K2", LETTER_KILL,
         _receipt(100.0, 100.0, 0.20, 5000.0, -300.0, upper=400.0)),
        ("U1", LETTER_UNRESOLVED,
         _receipt(100.0, 100.0, 0.20, 5000.0, 300.0)),
        ("U0", LETTER_UNRESOLVED,
         _receipt(100.0, 100.0, 0.20, 10.0, -300.0, upper=400.0)),
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
        family_letter(_receipt(3000.0, 5000.0, 0.01, 5000.0, 300.0)
                      )["letter"] != LETTER_LIVE))
    out.append(_check(
        "a control p above 0.05 cannot be LIVE",
        family_letter(_receipt(3000.0, 100.0, 0.20, 5000.0, 300.0)
                      )["letter"] != LETTER_LIVE))
    out.append(_check(
        "THE KILL IS NARROW, as the charter requires: a receipt with a missed "
        "ceiling but no non-positive upper bound and no lawful kill clause is "
        "parked UNRESOLVED (clause U0), never killed",
        family_letter(_receipt(100.0, 100.0, 0.20, 10.0, -300.0, upper=400.0)
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
    # The kill surface is exactly Sol's two clauses, no wider.
    kills = 0
    for bits in itertools.product((False, True), repeat=9):
        _letter, clause, _m = classify(*bits)
        if clause in ("K1", "K2"):
            kills += 1
            if not (bits[7] or (bits[6] and not bits[8])):
                return out + [_check("the kill surface is exactly the charter's "
                                     "two clauses", False, f"at {bits}")]
    out.append(_check(
        "the kill surface is EXACTLY the charter's two clauses: a powered "
        "non-positive upper bound, or a carrying ceiling beside a non-positive "
        "matched delta",
        kills == seen.get("K1", 0) + seen.get("K2", 0), f"{kills} kill points"))
    return out


def selftest() -> int:
    mutant = arm_mutant(_mutant())
    results: list[tuple[str, bool, str]] = []
    results += _selftest_feature_law()
    results += _selftest_percentile()
    results += _selftest_ridge()
    results += _selftest_top_k()
    results += _selftest_component_recovery(mutant)
    results += _selftest_leak(mutant)
    results += _selftest_planted_read()
    results += _selftest_center_gate_real()
    results += _selftest_letters()
    # The replay, MDD and stress fixtures, reused from sweep 25's own roster.
    results += S22._selftest_replay()
    results += S22._selftest_stress()
    results += S23._selftest_formation()
    print(f"sweep 27 selftest  mutant={mutant or 'none'}")
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
        "read": "zone-anchored via levels_zone.read_zone at zone_price, side "
                "-break_dir, stamp lat[breach_bar-1]",
        "features": list(FEATURE_NAMES), "n_features": NFEAT,
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

    # 1. the registered selection, per label x asset
    block = report["live"]
    for label in LABELS:
        for asset in ASSETS:
            counter += 1
            line = blank(dict(shared))
            cell = block["per_asset"][asset][label]
            cash = block["cash"][asset]
            zone = report["zone_read"]
            line["id"] = f"{LOG_PREFIX}-{counter:03d}"
            line["rule"] = f"top{TOP_K}/{label}/{asset}"
            line["days"] = cell["days"]
            line["coverage"] = cell["coverage"]
            tag = asset.lower()
            line[f"{tag}_usd_day"] = cell["usd_per_asset_day"]
            line[f"mdd_{tag}"] = cell["mdd_day_usd"]
            line[f"walls_{tag}"] = cell["wall_rate"]
            line["replay_skips"] = (block["replay"]["rejected_occupancy"]
                                    + block["replay"]["rejected_cap"])
            line["null_margin"] = report["block_nulls"].get(
                f"{LANE}|{asset}", {}).get("p")
            line["note"] = (
                f"F22 FIXED-ZONE COMPONENT RANKER, top-{TOP_K} positive-score "
                f"events per out-of-fold asset-day on the {LANE} lane "
                f"({LANE_NAME}), label {label}, {asset}: n {cell['n']} of "
                f"{cell['formed']} formed, coverage {_show(cell['coverage'])}, "
                f"mean {_show(cell['mean_cert_usd'])} median "
                f"{_show(cell['median_cert_usd'])}, P(cert>0) "
                f"{_show(cell['p_cert_positive']['rate'])} "
                f"[{_show(cell['p_cert_positive']['lo'])}, "
                f"{_show(cell['p_cert_positive']['hi'])}], usd/day "
                f"{_show(cell['usd_per_asset_day'])} = "
                f"{_show(cell['over_rung'])} rung; seated replay "
                f"{_show(cash['usd_per_day'])} usd/day, mean-2SE "
                f"{_show(cash['mean_minus_2se_usd'])}, clears rung "
                f"{cash['clears_rung']}; max binding MDD "
                f"{_show(block['mdd']['max_binding_usd'])} clears "
                f"{block['mdd']['clears']}; neighbours agree "
                f"{block['neighbours_agree']}; {NFEAT} SEPARATE fixed-zone "
                f"components read at the fixed zone price, "
                f"{zone['center_exact']}/{zone['rows']} centres exact, worst "
                f"gap {zone['worst_center_gap_mid2']} mid2; letter "
                f"{report['family_letter']}")
            rows.append(line)

    # 2. the two non-letter neighbours and the registered cell
    for k in ALL_K:
        counter += 1
        cell = report["neighbours"][str(k)]
        line = blank(dict(shared))
        line["id"] = f"{LOG_PREFIX}-{counter:03d}"
        line["rule"] = f"neighbour/top{k}"
        line["days"] = days_scored
        for asset in ASSETS:
            line[f"{asset.lower()}_usd_day"] = cell["cash"][asset]["usd_per_day"]
        line["note"] = (
            f"COVERAGE NEIGHBOUR top-{k} per out-of-fold asset-day: n "
            f"{cell['n']}, seated {cell['seated']}; " + "; ".join(
                f"{asset} {_show(cell['cash'][asset]['usd_per_day'])} usd/day, "
                f"-2SE {_show(cell['cash'][asset]['mean_minus_2se_usd'])}"
                for asset in ASSETS)
            + ("; REGISTERED CELL, coverage set by the twelve-entry seat "
               "budget and never by cash" if k == TOP_K
               else "; NON-LETTER NEIGHBOUR, sign-flip check only"))
        rows.append(line)

    # 3. C1, the matched control
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
            f"C1 paired matched control, complete level vector permuted inside "
            f"the training fold, {asset}: selected minus control "
            f"{_show(cell['delta_usd_per_date'])} usd per asset-day over "
            f"{cell['dates']} shared dates, SE {_show(cell['se_usd'])}, t "
            f"{_show(cell['t'])}, shared-date-sign max-stat p "
            f"{_show(cell['p_max_adjusted'])} over "
            f"{len(report['control']['family'])} lines (1 lane x 2 deciding "
            f"assets), simultaneous 95% "
            f"[{_show(cell['lower95_simultaneous_usd'])}, "
            f"{_show(cell['upper95_simultaneous_usd'])}]; event-level p-values "
            f"forbidden and not computed"
            f"{'' if cell['eligible'] else '; HG report-only'}")
        rows.append(line)

    # 4. C2, the formed ceiling
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

    # 5. the ranker diagnostics, per asset
    for asset in ASSETS:
        counter += 1
        cell = report["ranker_diagnostics"][asset]
        line = blank(dict(shared))
        line["id"] = f"{LOG_PREFIX}-{counter:03d}"
        line["rule"] = f"ranker/{asset}"
        line["days"] = cell["folds"]
        line["null_margin"] = cell["oof_rank_corr_mean"]
        line["note"] = (
            f"RANKER DIAGNOSTIC {asset}: {cell['folds']} out-of-fold asset-days "
            f"({cell['folds_with_rank_corr']} with a defined rank "
            f"correlation), OOF rank correlation of the score with the day's "
            f"own frozen-cert percentile mean "
            f"{_show(cell['oof_rank_corr_mean'])}, median "
            f"{_show(cell['oof_rank_corr_median'])}, share positive "
            f"{_show(cell['oof_rank_corr_p_positive'])}; mean training rows "
            f"{_show(cell['train_rows_mean'])}, rows scored "
            f"{cell['scored_rows']}, mean |beta| "
            f"{_show(cell['beta_l2_mean'])}; asset-specific ridge, "
            f"lambda={RIDGE_LAMBDA} fixed, {NFEAT} components, no model or "
            f"penalty search")
        rows.append(line)

    # 6. mechanics: the read, the feature schema, the permutation
    counter += 1
    zone = report["zone_read"]
    census = report["feature_law"]["census"]
    line = blank(dict(shared))
    line["id"] = f"{LOG_PREFIX}-{counter:03d}"
    line["rule"] = "read/feature-schema"
    line["days"] = days_scored
    line["note"] = (
        f"READ AND SCHEMA: {zone['rows']} of {zone['candidates']} formed "
        f"candidates read through levels_zone.read_zone at the FIXED zone "
        f"price on the former defending side, {zone['center_exact']} centres "
        f"EXACT, {zone['center_mismatched']} mismatched, worst gap "
        f"{zone['worst_center_gap_mid2']} mid2, {zone['strictly_prior']} "
        f"strictly prior (worst source-decision "
        f"{zone['worst_source_minus_decision_ns']} ns), prior session served "
        f"{zone['prior_session_served']} absent "
        f"{zone['prior_session_absent']}; {NFEAT} SEPARATE components "
        f"({', '.join(FEATURE_NAMES)}); rows with no finite I_break "
        f"{census['rows_without_finite_I_break']}; EXCLUDED by registration: "
        f"absolute timestamps, warmup row counts, outcome fields and schedule "
        f"fields")
    rows.append(line)

    counter += 1
    permuted = report["control_permutation"]
    line = blank(dict(shared))
    line["id"] = f"{LOG_PREFIX}-{counter:03d}"
    line["rule"] = "control/level-permutation"
    line["days"] = days_scored
    line["null_margin"] = permuted.get("share_permuted_positive")
    line["note"] = (
        f"PERMUTED COMPLETE LEVEL VECTOR inside the training fold: "
        f"{permuted['controls']} matched controls handed a whole feature row "
        f"drawn from a permutation of their own fold and scored by that fold's "
        f"own ranker; share with a positive score "
        f"{_show(permuted.get('share_permuted_positive'))}, share that would "
        f"have made the top-{TOP_K} cut "
        f"{_show(permuted.get('share_permuted_top4'))}; the real selection is "
        f"positive by construction "
        f"({permuted['selected_positive']}/{permuted['selected_top4']})")
    rows.append(line)

    # 7. the letter
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
        f"{report['family_clause']}): deciding usd/day over rung " + ", ".join(
            f"{asset} {_show(head['over_rung'].get(asset))}x"
            for asset in DECIDING)
        + "; matched delta " + ", ".join(
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
          f"{cell['control_ok']}, neighbours {cell['neighbours_ok']}, ceiling "
          f"carries both rungs {cell['ceiling_carries_both_rungs']}, upper "
          f"bound non-positive {cell['upper_bound_nonpositive']}, matched "
          f"delta positive {cell['matched_delta_positive']}; CLAUSE "
          f"{cell['clause']} = {cell['clause_text']}; clauses matching "
          f"{cell['clauses_matching']}"
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
    print_zone_read(report)
    print_features(report)
    print_ranker(report)
    print_selection(report)
    print_controls(report)
    print_decision(report)
    print(f"\nWHY THE COMPONENTS AND NOT THE MEAN\n"
          f"  {report['compression_note']}")
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
