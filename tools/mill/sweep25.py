#!/usr/bin/env python3
"""Sweep 25: F20-STRUCTBREAK-ZONEANCHOR, the corrected F20 read.

Unit 3 of the corrected path.  Unit 1 built the fixed-zone accessor
(``tools/mill/levels_zone.py``).  Unit 2 reran F19 through it and returned a
VALID kill (``.audit/mill-sweep24.json``, ``LEVELCOLLISION-KILL`` clause K3,
CEILING-UNREACHED, formed ceiling 46.8x and 55.0x the deciding rungs against a
causal line at 0.036x and 0.078x).  Sol's decision tree
(``.audit/briefs/mill-structbreak-sol-out.md`` section C, priority 3) routes a
valid F19 KILL to the corrected two-lane F20, and section B promotes the
break-close line into the letter family before the read.

WHAT IS UNDER TEST.  The break event, not the fade.  Every dead family in this
program asked a level whether it would HOLD.  F20 waits until a one-minute close
has ANSWERED that question and then trades the answer, asking the level to
confirm continuation instead of to defend.  Sweep 23 built that formation and
ran it, but Sol refused its lineage: its barrier score read the level cache at
the last INSIDE bar's own mid rather than at the candidate's fixed zone price,
so the persistence gate and B both inherited a moving price key.  Sweep 23 is
imported here READ-ONLY as a refused build receipt - its formation, its raw-tick
fill law, its replay, its controls and its stress fixtures are called, never
re-implemented - and the barrier read is replaced.

THE FOUR CORRECTIONS Sol's section B requires, each registered in the SPEC:

  1. FIXED-ZONE READ.  ``B_opp`` is the defence score of the FORMER DEFENDING
     SIDE - the side trapped by the break, ``-break_dir`` - read through
     ``levels_zone.read_zone`` AT ``candidate.zone_price`` with the trained
     width, stamped at the last completed bar before the breach close.  Every
     row must echo ``center_price == zone_price`` exactly or the run refuses.
     The breach itself is never folded into the counts.
  2. BREAK_CLOSE PROMOTED.  Sweep 23 carried the USER's break-close timing as a
     report-only line outside the letters.  It is now lane A, a full
     letter-carrying lane, so a pullback failure cannot kill STRUCTBREAK without
     testing the event the USER ordered.
  3. THE SELECTOR LAW, verbatim.  ``trade iff B_opp >= train top-tercile AND
     I_break >= train median``.  Both terms positive: a level that was
     repeatedly DEFENDED strands a cohort when it fails, and the magnitude
     channel supplies fuel for a direction the break has already revealed.
  4. THE EXHAUSTIVE PARTITION.  Five clauses, one precedence, ``CEILING-UNREACHED``
     registered as K3, proved over all 512 outcome points and over five
     constructed receipts, a letter per lane and one for the family.

ONE PARENT DEVIATION, registered for Sol's next pass and carried as lane C.
Sweep 23 MEASURED that its two marginal medians do not compose: the limit depth
was the median of the depth pool and the cancel duration the median of the
duration pool, drawn independently, and the resulting pair filled 263 of 3,790
armed orders (0.069) leaving 19 seated entries, while the fills that did occur
retraced about 1.2 full widths inside 1.4 bars - far past a limit the marginal
law had placed.  Lane C is lane B with depth and cancel trained JOINTLY as one
two-dimensional quantile over the reachable region, and is otherwise identical.
It is a parent deviation because Sol registered the marginal law; it is
registered here rather than substituted, so lane B still carries Sol's law.

Nothing here is executable.  EXPLORE only, kill-only tier, no packs, no HOLD, no
teacher labels, no 2021, no 2025H2, no commits, no freeze.  Sweeps 22, 23, 24
and ``levels_zone`` are imported and are not modified.
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

# --------------------------------------------------------------------------
# The law, registered before anything is read.
# --------------------------------------------------------------------------

SPEC = """QRE2MILLSWEEP25
tier=exploratory; EXPLORE-only, kill-only.  Family F20-STRUCTBREAK-ZONEANCHOR,
  the corrected F20 after the VALID F19 kill in .audit/mill-sweep24.json.  Seed
  20260827.  Parent trial sweep24-039.  NO COMMITS, NO FREEZE, no packs, no
  HOLD, no teacher labels, no 2021, no 2025H2.  THREE entry lanes in ONE
  max-stat family; HG is carried report-only on every line.
INHERITANCE.  Sweep 23 is imported and called READ-ONLY as a refused build
  receipt; sweep 22 supplies the shared machinery underneath it.  Their SPECs
  govern every clause not restated here: the GATE, the zone catalogue, the
  fold-trained zone width and its snap to the cache band multipliers, breach
  formation with the persistence gate and the per (asset, day, phase, level,
  break direction) dedup, the parameter-free pullback statistics, the raw-tick
  first-passage fill with its floor/ceil convention, the frozen bar-entry law,
  the impulse ridge and its join, the frozen outcome law with the 1800 s label
  beside, the chronological seat replay, the MDD ledger family, the two
  stresses, and controls C1, C2 and C3.  FORMATION MUST RETURN 3,790 CANDIDATES
  or this unit refuses: an identical universe is what makes the corrections
  attributable.
CORRECTION 1, THE BARRIER READ.  B_opp is read through
  tools/mill/levels_zone.py read_zone at the candidate's FIXED zone_price with
  the trained HALF width, on side = defence_side = -break_dir, THE FORMER
  DEFENDING SIDE, the side trapped by the break.  DECISION STAMP = the lattice
  close of the LAST COMPLETED BAR BEFORE THE BREACH CLOSE, lat[breach_bar - 1].
  The accessor counts only bars whose close is STRICTLY BEFORE that stamp, so
  the read sees bars 0..breach_bar-2: the breach bar cannot enter the counts and
  neither can the bar contemporaneous with the decision stamp.  This is one bar
  stricter than sweep 24's lane-1 convention and is the reading Sol's section B
  names.  B_opp is the mean of three train-fold-standardized differences from
  ONE accessor call: (sd_held - sd_broke), day_scale_persistence, and
  (ps_held - ps_broke).  Every returned row must echo center_price ==
  zone_price EXACTLY and max_source_stamp strictly below the decision stamp;
  either miss refuses the run, per row.
THE DAY-SCALE TERM AND THE ZERO-DEFAULT QUIRK, disclosed rather than inherited.
  The third component is consumed as day_scale_persistence, a day-scale
  persistence and location proxy, NEVER prior-day defence memory, under Sol's
  naming restriction.  It is built at the SAME single decision stamp as the
  other two, mode "approach", approach_side = break_dir, which reproduces sweep
  23's pd_broke question (had today's own strictly prior path already traded a
  full width beyond this zone on the BREAK side?) at the corrected price key.
  Sweep 24 had to carry a fallback because its lane 2 owned a SECOND decision
  stamp that 12,775 of 14,650 candidates never reached, and those rows took the
  approach read with the negative half left at its zero default.  F20 has ONE
  decision event, so every candidate gets exactly one accessor row and NO
  candidate's day-scale term is ever defaulted to zero.  The run asserts
  zero_default_used == 0.  Where the term is genuinely unreadable - a breach at
  bar 1 leaves no bar strictly before the decision stamp - day_scale_broke and
  day_scale_persistence are NaN, not zero, the NaN drops out of the component
  mean exactly as in sweep 24, and both counts are reported.
CORRECTION 2, THREE REGISTERED LETTER-CARRYING LANES.  maxT family = 3 lanes x 2
  deciding assets = 6 lines.  HG carried as ineligible lines.
  LANE A BREAK_CLOSE, Sol's promotion and the USER's timing: decide at the first
    lawful one-minute close beyond the trained breach band - the breach bar,
    which formation already defines as the first close carrying price past an
    edge - and enter in the BREAK direction at the NEXT bar under the frozen
    entry law.  NEVER a same-close fill: the earliest market entry is
    lat[breach_bar + 1], which the run asserts is strictly after the breach
    close for every priced row.
  LANE B PULLBACK, Sol's registered marginal law, sweep 23's verbatim: arm one
    resting limit at the first raw tick STRICTLY AFTER the breach close, at
    broken_edge - break_dir * depth * 2w with depth the fold-trained
    Q_DEPTH = 50th percentile of the strictly-prior depth pool clipped to
    [0.05, 0.95], cancelled at the fold-trained Q_CANCEL = 50th percentile of
    the strictly-prior duration pool clipped to [3, 90] bars.  RAW FIRST PASSAGE
    decides the fill.
  LANE C PULLBACK-JOINT, the registered PARENT DEVIATION, identical to lane B
    except that depth and cancel are trained JOINTLY.  GROUNDS, measured by
    sweep 23 and not asserted: the two marginals do not compose - fill rate
    0.069 (263 of 3,790 armed), 19 seated entries, and the fills that occur
    retrace about 1.2 full widths within 1.4 bars.  THE JOINT LAW, one
    two-dimensional quantile over the REACHABLE region of the strictly prior
    training pool: (i) cancel = ceil of the Q_CANCEL percentile of the durations
    of training pullbacks that RETURNED to the broken edge inside
    MAX_EPISODE_BARS, clipped to [3, 90]; (ii) depth = the Q_DEPTH percentile of
    the DEPTH REACHED WITHIN THAT CANCEL WINDOW among the training pullbacks
    that returned WITHIN it, clipped to [0.05, 0.95].  The within-window depth
    is the running maximum of break_dir * (broken_edge - mid) / 2w over the
    first `cancel` bars after the breach, computed on the same bar slice sweep
    23's own pool statistic uses and padded with its final value where the cell
    ends first.  REGISTERED FALLBACK: if no training pullback returned, or none
    returned within the cancel window, the day falls back to lane B's marginal
    pair and the fallback is counted and reported.  Everything else - formation,
    arming, the raw-tick fill, pricing, replay, ledgers, stresses, controls -
    is lane B's, unchanged.
  The reachable share of the training pool at each lane's chosen pair is
  reported per stratum-day as INFORMATION, not as a gate.
CORRECTION 3, THE SELECTOR, Sol's law verbatim and identical across lanes.
  B_opp and the frozen impulse score I_break are each standardized on the
  TRAINING FOLD per asset x phase-type over strictly prior EXPLORE days only,
  with the >= 25 prior-day warmup and the >= 40 training-candidate floor.
  TRADE IFF B_opp >= the train TOP-TERCILE cut AND I_break >= the train MEDIAN
  cut.  I_break is the frozen out-of-fold magnitude prediction applied to the
  feature vector of the LAST eligible causal G1 occurrence in the candidate's
  own cell STRICTLY BEFORE the breach close - sweep 23's join, unchanged.  Two
  interpretive registrations carried from sweep 23: the I cut is a percentile of
  the FINITE training I only, and A CANDIDATE WITH NO FINITE I IS NEVER
  SELECTED, because a conjunction cannot be satisfied by a term that does not
  exist.  NEIGHBOUR GRID, required: (quartile, tercile) x (median, p60).  The
  registered LIVE cell is (tercile, median); a LIVE letter requires the three
  neighbours not to flip the sign on either deciding asset.
PRICING, REPLAY, CONTROLS.  Identical law to sweeps 23 and 24.  The frozen
  outcome law - the -900 wall or the phase close, whichever comes first - is
  PRIMARY and carries the letters; the 1800 s fixed hold is reported beside
  every line.  Chronological seat replay with the frozen tie break, exits before
  entries at an equal stamp, one open position per asset, at most 12 seated
  entries per PORTFOLIO date, every split date carried including zero-entry
  dates.  The full MDD ledger family including event-time portfolio equity;
  binding is the deciding assets' own ledgers plus every portfolio ledger,
  ceiling 1000 USD.  The 2 percent adversarial stress and the doubled-spread
  stress, both re-running the replay so occupancy follows.  C1: one paired G1
  control per selected event matched on asset, day, phase, breach-time bin and
  magnitude bin, its level features PERMUTED WITHIN THE TRAINING FOLD, selected
  minus control by asset-day, studentized, shared-date-sign maxT over the
  6-line family, 10000 draws.  C2: the formed-opportunity ceiling RAW and CAPPED
  at the 12 best events per portfolio date, hindsight bits named; the KILL test
  reads the RAW FORMED ceiling, never the selected subset.  C3: block-permutation
  nulls, 2000 draws, with the standing caveat printed beside them.
CORRECTION 4, LETTERS, the proven exhaustive partition with this family's names.
  Five clauses, one registered precedence LIVE > K1 > K2 > K3 > UNRESOLVED, no
  fallthrough:
  STRUCTBREAK-LIVE when a lane has NKD and SI each above 1500 USD per asset-day
    at the point estimate AND at mean minus two asset-day-block standard errors,
    every binding MDD below 1000, cap and occupancy lawful, both stresses
    clearing MDD, the paired matched control surviving maxT at 0.05 on BOTH
    deciding assets, and the neighbours not flipping the sign.
  STRUCTBREAK-KILL clause K1 when the formed ceiling misses either deciding rung.
  STRUCTBREAK-KILL clause K2 when a powered deciding asset has a non-positive 95
    percent simultaneous upper bound against its matched control.
  STRUCTBREAK-KILL clause K3, CEILING-UNREACHED, when the formed ceiling carries
    both rungs, no deciding upper bound is non-positive, and the causal matched
    delta is not positive on both deciding assets.
  STRUCTBREAK-UNRESOLVED when the formed ceiling carries both rungs AND the
    causal matched delta is positive on both deciding assets, but a live or
    power bound fails.
  A letter per lane, then the family letter: LIVE if ANY lane is LIVE, else
  UNRESOLVED if any lane earns it, else KILL with the first clause in precedence
  order among the lanes.  The selftest proves the partition over all 512 outcome
  points, constructs a receipt for every clause, and asserts agreement with
  sweep 23's own classifier.
MUTANTS.  Each names the EXACT checks it must turn red; a mutant that reds some
  other check, or that leaves any named check green, fails the run.
  QRE2_MILL_S25_MUTANT=center_uses_current_mid arms the accessor's own
  registered defect - the reading bar's mid replaces the requested zone price -
  and must red the centre-equality gate on the fixture AND on the 50 real formed
  rows, and the two hand counts that price the trapped cohort.  DISCLOSED, and
  the reason the gate is centre equality rather than a ranking: on this fixture
  the miscentred read still ranks the trapped cohort above the weak zone,
  because the last bar inside the zone sits within a half width of it and the
  outcome of each touch stays anchored on the TOUCHED price.  A wrong price key
  can look plausible - that is exactly how sweep 22 passed its own selftest - so
  the refusal is mechanical equality per row and never a plausibility check.
  QRE2_MILL_S25_MUTANT=selector_uses_test_day computes the selector's
  standardizations and cuts INCLUDING the scoring day and fits the impulse ridge
  including it, and must red the leak guard.
"""

DEVIATION_NOTE = (
    "REGISTERED PARENT DEVIATION, lane C, for Sol's next pass.  Sol registered "
    "the marginal pullback law and it is run unchanged as lane B.  Lane C is "
    "added beside it because sweep 23 MEASURED that the two marginals do not "
    "compose: drawing the limit depth from the median of the depth pool and the "
    "cancel duration from the median of the duration pool - two independent "
    "one-dimensional quantiles - names a pair that the joint distribution "
    "rarely contains, and the receipt shows it: 263 fills from 3,790 armed "
    "orders (0.069), 19 seated entries, and a mean realized retracement of "
    "about 1.2 full widths inside about 1.4 bars on the fills that did occur. "
    "A limit deep enough to be worth resting is not reached inside a window "
    "trained on durations that are dominated by shallow fast returns.  Lane C "
    "changes ONLY the estimator of the pair, to one two-dimensional quantile "
    "over the reachable region, and leaves formation, arming, the raw-tick "
    "fill, pricing, replay, ledgers, stresses and controls identical.  It is "
    "registered as a deviation and not substituted for lane B, so Sol's law "
    "still carries its own letter and the comparison is between two priced "
    "lanes rather than between a law and its replacement.")

CONTAMINATION_NOTE = (
    "Sweep 23's SELECTOR SIGN NOTE is printed beside this one and is carried "
    "as the parent's, verbatim.  One clause of it is stated in sweep 23's own "
    "frame and is STRONGER here, so it is restated rather than left to be "
    "read across.  The note's live risk is contamination: if the present "
    "breach were counted in sd_broke, the high-B_opp events would be exactly "
    "the ones scored down and the trapped-cohort sign would invert.  Sweep 23 "
    "answered that with the cache's verdict law at a READ BAR that is itself "
    "strictly before the breach.  This unit does not read a bar's cache row at "
    "all.  It calls the fixed-zone accessor with a decision stamp of "
    "lat[breach_bar - 1], and the accessor counts only bars closing STRICTLY "
    "BEFORE that stamp, so the breach bar and the bar naming the stamp are "
    "both outside the window by construction - not by a property of the cache. "
    "The receipt's centre-exact and strictly-prior counts are the mechanical "
    "evidence, and the formed-universe component means are printed above so a "
    "reader can check the sign rather than trust it.")

ASSETS = S23.ASSETS
DECIDING = S23.DECIDING
REPORT_ONLY_ASSETS = S23.REPORT_ONLY_ASSETS
SEED = 20260827

FAMILY = "F20-STRUCTBREAK-ZONEANCHOR"
PARENT_TRIAL = "sweep24-039"
SELECTION_RULE = ("none: parent-preregistered break formation, Sol's monotone "
                  "selector at the corrected zone-anchored barrier, "
                  "fold-trained thresholds, no model search; the registered "
                  "lane-C deviation changes only the pullback pair estimator")

LOG_PREFIX = "sweep25"
OUT_PATH = ROOT / ".audit/mill-sweep25.json"
LOG_PATH = S1.LOG_PATH

EXPECT_CANDIDATES = 3_790

# Inherited by value, so an upstream drift fails loudly here.
CLOSE = S23.CLOSE
FIXED = S23.FIXED
LABELS = S23.LABELS
NANOS = S23.NANOS
MIN_PRIOR_DAYS = S23.MIN_PRIOR_DAYS
MIN_TRAIN_CANDS = S23.MIN_TRAIN_CANDS
DAY_RUNG_USD = S23.DAY_RUNG_USD
MDD_CEILING = S23.MDD_CEILING
PORTFOLIO_CAP = S23.PORTFOLIO_CAP
CONTROL_DRAWS = S23.CONTROL_DRAWS
SIGN_DRAWS = S23.SIGN_DRAWS
IMPULSE_HORIZON_S = S23.IMPULSE_HORIZON_S
MAX_EPISODE_BARS = S23.MAX_EPISODE_BARS
Q_DEPTH = S23.Q_DEPTH
Q_CANCEL = S23.Q_CANCEL
DEPTH_CLIP = S23.DEPTH_CLIP
CANCEL_CLIP = S23.CANCEL_CLIP
DEPTH_STAT_CLIP = S23.DEPTH_STAT_CLIP
BARRIER_CUTS = S23.BARRIER_CUTS
IMPULSE_CUTS = S23.IMPULSE_CUTS
LIVE_CELL = S23.LIVE_CELL
GRID = S23.GRID
HINDSIGHT_CEILING = S23.HINDSIGHT_CEILING
TIME_BINS = S23.TIME_BINS

LANE_A = "A_BREAK_CLOSE"
LANE_B = "B_PULLBACK"
LANE_C = "C_PULLBACK_JOINT"
LANES = (LANE_A, LANE_B, LANE_C)
PULLBACK_LANES = (LANE_B, LANE_C)
LANE_NAME = {
    LANE_A: "break close: enter the break direction at the NEXT bar (Sol's "
            "promotion, the USER's timing)",
    LANE_B: "first pullback, MARGINAL depth and cancel (Sol's registered law)",
    LANE_C: "first pullback, JOINTLY trained depth and cancel (registered "
            "parent deviation)"}
LANE_TAG = {LANE_A: "nb", LANE_B: "pb", LANE_C: "pj"}

LETTER_LIVE = S23.LETTER_LIVE               # STRUCTBREAK-LIVE
LETTER_UNRESOLVED = S23.LETTER_UNRESOLVED   # STRUCTBREAK-UNRESOLVED
LETTER_KILL = S23.LETTER_KILL               # STRUCTBREAK-KILL
CLAUSES = dict(S23.CLAUSES)
CLAUSE_ORDER = tuple(S23.CLAUSE_ORDER)
CLAUSE_LETTER = dict(S23.CLAUSE_LETTER)

C3_CAVEAT = (
    "the standing caveat, carried unchanged from sweeps 22, 23 and 24: the "
    "block null re-draws the SAME selected count uniformly inside each (asset, "
    "phase, day) block of formed candidates, so it tests only WHERE inside a "
    "block the selector picked - never how many it picked, nor on which days, "
    "nor whether the formed universe itself is special.  Its p is unadjusted "
    "across lines and carries none of the family maxT correction, so a single "
    "small p here is not a family result")

MUTANT_ENV = "QRE2_MILL_S25_MUTANT"
MUTANT_CENTER = "center_uses_current_mid"
MUTANT_TESTDAY = "selector_uses_test_day"
MUTANTS = (MUTANT_CENTER, MUTANT_TESTDAY)

# Each mutant names the checks it MUST red.  "at least one check went red" is a
# weak contract - it passes when a mutant reds something incidental - so the
# roster is asserted by name and a survivor is a failure.
EXPECTED_RED = {
    MUTANT_CENTER: (
        "the barrier is read AT the defended zone, not at the reading bar's mid",
        "the barrier is read AT the weakly defended zone",
        "the trapped cohort's hand count is 4 touches, 3 held, 0 broke",
        "the hand-computed B_opp is +2.0 at the defended zone and -1.5 at the "
        "weak zone",
        "every real row echoes centre_price == zone_price EXACTLY"),
    MUTANT_TESTDAY: (
        "the leak-only world yields NO causal recovery",),
}

# The planted trapped-cohort world.  Prices are mid2, ATR is 100 units, so at
# band multiplier 0.10 the zone HALF width is 10.  Every count is arithmetic.
PLANT_WIDTH = 10.0
PLANT_DEFENDED = 1000.0
PLANT_UNDEFENDED = 1400.0


class SweepRefusal(RuntimeError):
    pass


SPEC_SHA = S1._sha_text(SPEC)


def code_sha() -> str:
    """This unit plus every module whose behaviour it is asserting."""

    here = Path(__file__).resolve().parent
    return S1._sha_text("\n".join(
        S1._sha_file(Path(path).resolve()) for path in (
            __file__, here / "sweep23.py", here / "sweep22.py",
            here / "levels_zone.py")))


def _mutant() -> str:
    name = os.environ.get(MUTANT_ENV, "")
    if name and name not in MUTANTS:
        raise SweepRefusal(f"unknown sweep 25 mutant: {name}")
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
# CORRECTION 1: the barrier read, at the FIXED zone price, one per candidate.
# --------------------------------------------------------------------------

@dataclass(slots=True)
class ZoneRead:
    """What the read produced, with the evidence that it is at the zone."""

    raw: np.ndarray                 # (n, 3) the three defence differences
    have: np.ndarray                # (n,) bool, the read landed
    center_gap: np.ndarray          # (n,) |centre echoed - zone asked for|
    source_gap: np.ndarray          # (n,) max source stamp - decision stamp
    stamp: np.ndarray               # (n,) the decision stamp actually used
    counters: dict


def decision_stamp(cand: S23.Cand, records: Sequence[S1.CellRec]) -> int:
    """The last completed bar BEFORE the breach close.

    The breach bar's own close is the decision EVENT; the last bar completed
    before it is ``breach_bar - 1``, and its lattice close is the stamp the
    accessor is asked for.  ``levels_zone`` counts only bars closing STRICTLY
    BEFORE the stamp, so the read window is bars 0..breach_bar-2: the breach
    cannot enter its own barrier score, and neither can the bar that the stamp
    itself names.  Formation guarantees ``breach_bar >= 1``.
    """

    bar = int(cand.bar) - 1
    if bar < 0:
        return -1
    lat = np.asarray(records[int(cand.cell)].lat, np.int64)
    if not 0 <= bar < len(lat):
        return -1
    return int(lat[bar])


def zone_queries(cands: Sequence[S23.Cand], records: Sequence[S1.CellRec]
                 ) -> tuple[list[LZ.ZoneQuery], list[int]]:
    """One query per candidate.  One decision event, so one read each."""

    queries: list[LZ.ZoneQuery] = []
    positions: list[int] = []
    for position, cand in enumerate(cands):
        stamp = decision_stamp(cand, records)
        if stamp < 0:
            continue
        queries.append(LZ.ZoneQuery(
            cell=int(cand.cell), zone_price=float(cand.zone_price),
            band_width=float(cand.width), decision_stamp_ns=int(stamp),
            side=int(cand.defence_side), zone_kind=str(cand.zone_kind),
            approach_side=int(cand.break_dir), day_scale_mode="approach"))
        positions.append(position)
    return queries, positions


def zone_read(cands: Sequence[S23.Cand], records: Sequence[S1.CellRec],
              reader: LZ.ZoneReader) -> ZoneRead:
    """B_opp's three components at the FIXED zone price, with the centre gate.

    The gate is not a diagnostic.  A row whose echoed centre differs from the
    zone price by any amount is the defect Sol refused F19 for, so the run stops
    rather than scoring past it.  There is no fallback and no zero default: one
    decision event means one accessor row per candidate, and an unreadable
    component stays NaN and drops out of the component mean.
    """

    queries, positions = zone_queries(cands, records)
    rows = reader.rows(queries) if queries else []
    raw = np.full((len(cands), 3), np.nan, np.float64)
    have = np.zeros(len(cands), bool)
    center_gap = np.full(len(cands), np.nan, np.float64)
    source_gap = np.full(len(cands), np.nan, np.float64)
    stamps = np.full(len(cands), -1, np.int64)
    counters = {"candidates": len(cands), "queries": len(queries),
                "rows": len(rows), "no_decision_stamp": 0,
                "center_exact": 0, "center_mismatched": 0,
                "strictly_prior": 0, "not_strictly_prior": 0,
                "prior_session_served": 0, "prior_session_absent": 0,
                "same_day_defined": 0, "same_day_undefined": 0,
                "day_scale_defined": 0, "day_scale_undefined": 0,
                "prior_session_defined": 0, "prior_session_undefined": 0,
                "all_three_undefined": 0, "zero_default_used": 0,
                "fallback_reads": 0}
    counters["no_decision_stamp"] = len(cands) - len(queries)
    worst_center = 0.0
    worst_source = -(1 << 62)
    for row, query, position in zip(rows, queries, positions):
        gap = abs(float(row.center_price) - float(query.zone_price))
        center_gap[position] = gap
        worst_center = max(worst_center, gap)
        counters["center_exact" if float(row.center_price)
                 == float(query.zone_price) else "center_mismatched"] += 1
        delta = int(row.max_source_stamp) - int(row.decision_stamp_ns)
        source_gap[position] = float(delta)
        worst_source = max(worst_source, delta)
        counters["strictly_prior" if delta < 0 else "not_strictly_prior"] += 1
        counters["prior_session_served" if row.ps_served
                 else "prior_session_absent"] += 1
        sd = float(row.sd_held) - float(row.sd_broke)
        scale = float(row.day_scale_persistence)
        ps = float(row.ps_held) - float(row.ps_broke)
        counters["same_day_defined" if math.isfinite(sd)
                 else "same_day_undefined"] += 1
        counters["day_scale_defined" if math.isfinite(scale)
                 else "day_scale_undefined"] += 1
        counters["prior_session_defined" if math.isfinite(ps)
                 else "prior_session_undefined"] += 1
        if not (math.isfinite(sd) or math.isfinite(scale)
                or math.isfinite(ps)):
            counters["all_three_undefined"] += 1
        raw[position] = (sd, scale, ps)
        stamps[position] = int(row.decision_stamp_ns)
        have[position] = True
    counters["worst_center_gap_mid2"] = float(worst_center)
    counters["worst_source_minus_decision_ns"] = int(
        worst_source if rows else -1)
    return ZoneRead(raw=raw, have=have, center_gap=center_gap,
                    source_gap=source_gap, stamp=stamps, counters=counters)


def assert_zone_anchored(read: ZoneRead) -> None:
    """The refusals Sol's ruling requires, per row, before anything is scored."""

    counters = read.counters
    if counters["center_mismatched"]:
        raise SweepRefusal(
            f"{counters['center_mismatched']} of {counters['rows']} barrier "
            f"reads are not centred on the candidate zone (worst gap "
            f"{counters['worst_center_gap_mid2']} mid2); this is the refused "
            f"F19 defect and nothing may be priced past it")
    if counters["not_strictly_prior"]:
        raise SweepRefusal(
            f"{counters['not_strictly_prior']} barrier reads have a source "
            f"stamp at or after their own decision stamp (worst "
            f"{counters['worst_source_minus_decision_ns']} ns)")
    if counters["zero_default_used"] or counters["fallback_reads"]:
        raise SweepRefusal(
            "a candidate inherited a defaulted or fallback barrier component; "
            "F20 has one decision event and must not carry sweep 24's "
            "unresolved-episode quirk")
    if counters["rows"] != counters["candidates"]:
        raise SweepRefusal(
            f"the accessor answered {counters['rows']} of "
            f"{counters['candidates']} candidates; every formed candidate has a "
            f"bar strictly before its breach and must be readable")


# --------------------------------------------------------------------------
# LANE C: the joint pullback pair.  One two-dimensional quantile, not two
# marginals.
# --------------------------------------------------------------------------

def back_profile(mid: np.ndarray, bar: int, edge: float, width: float,
                 break_dir: int) -> np.ndarray:
    """The running-max retracement toward the broken zone, bar by bar.

    ``profile[k]`` is the deepest adverse excursion, in FULL zone widths back
    from the broken edge, reached by the end of bar ``bar + 1 + k``.  The slice
    is sweep 23's own ``_pool_stats`` slice, so ``profile[-1]`` is that
    statistic's ``max(back)`` before clipping and the two cannot drift.  Where
    the cell ends first the profile is padded with its final value: nothing more
    is reachable, and pretending otherwise would invent depth.
    """

    stop = min(len(mid), int(bar) + MAX_EPISODE_BARS)
    window = np.asarray(mid[int(bar) + 1:stop], np.float64)
    out = np.full(MAX_EPISODE_BARS, float(DEPTH_STAT_CLIP[0]), np.float64)
    if not len(window):
        return out
    back = (float(break_dir) * (float(edge) - window)) / (2.0 * float(width))
    running = np.maximum.accumulate(back)
    out[:len(running)] = running
    out[len(running):] = running[-1]
    return out


def build_profiles(cands: Sequence[S23.Cand], records: Sequence[S1.CellRec]
                   ) -> np.ndarray:
    """One running-max retracement profile per candidate, from the cached mids."""

    out = np.full((len(cands), MAX_EPISODE_BARS), float(DEPTH_STAT_CLIP[0]),
                  np.float64)
    for position, cand in enumerate(cands):
        mid = np.asarray(records[int(cand.cell)].mid, np.float64)
        out[position] = back_profile(mid, int(cand.bar), float(cand.broken_edge),
                                     float(cand.width), int(cand.break_dir))
    return out


def marginal_pair(depth_pool: Sequence[float], dur_pool: Sequence[float]
                  ) -> tuple[float, int, float, float]:
    """Sweep 23's law: two independent one-dimensional quantiles."""

    depth = _pct(depth_pool, Q_DEPTH)
    cancel = _pct(dur_pool, Q_CANCEL)
    return (float(np.clip(depth if depth is not None else 0.5, *DEPTH_CLIP)),
            int(np.clip(int(math.ceil(cancel if cancel is not None else 15.0)),
                        *CANCEL_CLIP)),
            float(depth) if depth is not None else float("nan"),
            float(cancel) if cancel is not None else float("nan"))


def joint_pair(durations: Sequence[float], profiles: np.ndarray,
               depth_pool: Sequence[float], dur_pool: Sequence[float]
               ) -> dict[str, object]:
    """ONE two-dimensional quantile over the REACHABLE region.

    The marginal law asks two questions of two different populations: how deep
    does a pullback go over the whole window, and how long does a pullback take.
    Their medians can name a pair that no pullback in the pool ever realized -
    a depth only the slow returns reach, inside a window only the fast returns
    fit.  This law asks ONE question of ONE population: among training pullbacks
    that came BACK to the broken edge, how long did that take, and how deep did
    price get inside exactly that window.  Both halves are read off the same
    joint sample, so the pair is realizable by construction.
    """

    dur = np.asarray(durations, np.float64)
    profiles = np.asarray(profiles, np.float64)
    returned = np.isfinite(dur) & (dur < float(MAX_EPISODE_BARS))
    out: dict[str, object] = {"train_rows": int(len(dur)),
                              "returners": int(returned.sum()),
                              "fallback": None}
    if not bool(returned.any()):
        depth, cancel, depth_raw, cancel_raw = marginal_pair(depth_pool,
                                                             dur_pool)
        out.update({"depth_frac": depth, "cancel_bars": cancel,
                    "depth_raw": depth_raw, "cancel_raw": cancel_raw,
                    "reachable": 0, "fallback": "no training pullback returned"})
        return out
    cancel_raw = float(np.percentile(dur[returned], Q_CANCEL))
    cancel = int(np.clip(int(math.ceil(cancel_raw)), *CANCEL_CLIP))
    reach = returned & (dur <= float(cancel))
    if not bool(reach.any()):
        depth, marg_cancel, depth_raw, marg_raw = marginal_pair(depth_pool,
                                                                dur_pool)
        out.update({"depth_frac": depth, "cancel_bars": marg_cancel,
                    "depth_raw": depth_raw, "cancel_raw": marg_raw,
                    "reachable": 0,
                    "fallback": "no training pullback returned inside the "
                                "cancel window"})
        return out
    within = np.clip(profiles[reach, int(cancel) - 1], *DEPTH_STAT_CLIP)
    depth_raw = float(np.percentile(within, Q_DEPTH))
    depth = float(np.clip(depth_raw, *DEPTH_CLIP))
    out.update({"depth_frac": depth, "cancel_bars": int(cancel),
                "depth_raw": depth_raw, "cancel_raw": cancel_raw,
                "reachable": int(reach.sum())})
    return out


def reachable_share(depth: float, cancel: int, durations: Sequence[float],
                    profiles: np.ndarray) -> float | None:
    """What share of a training pool would have filled at this pair.

    INFORMATION, never a gate.  A bar-grid answer: the raw tape can only fill
    more often, never less, so this is a conservative floor on the pair's
    realizability.
    """

    dur = np.asarray(durations, np.float64)
    profiles = np.asarray(profiles, np.float64)
    if not len(dur):
        return None
    index = int(np.clip(int(cancel), 1, MAX_EPISODE_BARS)) - 1
    return float(np.mean(profiles[:, index] >= float(depth)))


def joint_pass(cands: Sequence[S23.Cand], records: Sequence[S1.CellRec],
               profiles: np.ndarray,
               explore_days: Mapping[str, Sequence[int]]
               ) -> tuple[list[S23.Cand], dict[str, object], dict[str, object]]:
    """Lane C's candidates: lane B's, with the pair re-estimated jointly.

    The training pool is rebuilt from the FORMED CANDIDATES themselves, which is
    exactly how ``S23.formation_pass`` builds its own pool - it appends
    ``(pull_frac, pull_dur)`` per formed candidate and reads back every strictly
    prior day of the same (asset, phase) stratum.  Reconstructing it here is
    therefore identical by construction rather than by resemblance, and it costs
    no second pass over the levels cache.
    """

    table: dict[tuple[str, str], dict[int, list[int]]] = {}
    for position, cand in enumerate(cands):
        table.setdefault((cand.asset, cand.phase), {}).setdefault(
            int(cand.d8), []).append(position)
    clones = [S23.Cand(**{f.name: getattr(cand, f.name)
                          for f in S23.Cand.__dataclass_fields__.values()})
              for cand in cands]
    params_used: dict[str, dict[str, object]] = {}
    counters = {"strata": 0, "days_paired": 0, "days_no_prior": 0,
                "fallback_no_returner": 0, "fallback_no_reachable": 0,
                "pairs_differ_from_marginal": 0}
    for (asset, phase), by_day in sorted(table.items()):
        counters["strata"] += 1
        days = sorted(int(day) for day in explore_days[asset])
        for index, d8 in enumerate(days):
            today = by_day.get(d8, [])
            if not today:
                continue
            prior = [p for day in days[:index] for p in by_day.get(day, [])]
            if not prior:
                counters["days_no_prior"] += 1
            take = np.asarray(prior, np.int64)
            dur_pool = [float(cands[p].pull_dur) for p in prior]
            depth_pool = [float(cands[p].pull_frac) for p in prior]
            block = profiles[take] if len(take) else np.zeros(
                (0, MAX_EPISODE_BARS), np.float64)
            joint = joint_pair(dur_pool, block, depth_pool, dur_pool)
            marginal = marginal_pair(depth_pool, dur_pool)
            if joint["fallback"] == "no training pullback returned":
                counters["fallback_no_returner"] += 1
            elif joint["fallback"] is not None:
                counters["fallback_no_reachable"] += 1
            if (abs(float(joint["depth_frac"]) - marginal[0]) > 1e-12
                    or int(joint["cancel_bars"]) != marginal[1]):
                counters["pairs_differ_from_marginal"] += 1
            counters["days_paired"] += 1
            params_used.setdefault(f"{asset}|{phase}", {})[str(d8)] = {
                "joint_depth_frac": float(joint["depth_frac"]),
                "joint_cancel_bars": int(joint["cancel_bars"]),
                "joint_depth_raw": float(joint["depth_raw"]),
                "joint_cancel_raw": float(joint["cancel_raw"]),
                "marginal_depth_frac": marginal[0],
                "marginal_cancel_bars": marginal[1],
                "train_rows": int(joint["train_rows"]),
                "returners": int(joint["returners"]),
                "reachable_at_joint_pair": reachable_share(
                    float(joint["depth_frac"]), int(joint["cancel_bars"]),
                    dur_pool, block),
                "reachable_at_marginal_pair": reachable_share(
                    marginal[0], marginal[1], dur_pool, block),
                "fallback": joint["fallback"]}
            for position in today:
                mid = np.asarray(records[int(cands[position].cell)].mid,
                                 np.float64)
                S23.resolve_pullback(clones[position], mid,
                                     float(joint["depth_frac"]),
                                     int(joint["cancel_bars"]))
    return clones, params_used, counters


# --------------------------------------------------------------------------
# CORRECTION 3: the selector.  Sweep 23's fold law, with B_opp supplied.
# --------------------------------------------------------------------------

def score_selector(cands: Sequence[S23.Cand], raw: np.ndarray,
                   impulse: np.ndarray,
                   explore_days: Mapping[str, Sequence[int]], mutant: str
                   ) -> tuple[list[S23.Scored], dict[str, object]]:
    """B_opp and I_break standardized on the training fold, then Sol's rule.

    This is ``S23.score_selector`` with one argument added: the (n, 3) matrix of
    barrier components.  Sweep 23 computed that matrix from the level-cache row
    at the last inside bar's own mid; here it arrives from the fixed-zone
    accessor.  Every other step - the stratum, the warmup, the training floor,
    the standardization, the finite-only I quantile, the cut percentiles and the
    monotone rule - is the parent's, and the selftest asserts the two agree
    exactly when fed the same matrix.
    """

    raw = np.asarray(raw, np.float64)
    if raw.shape != (len(cands), 3):
        raise SweepRefusal(f"barrier component matrix is {raw.shape}, expected "
                           f"{(len(cands), 3)}")
    by_stratum: dict[tuple[str, str], dict[int, list[int]]] = {}
    for position, cand in enumerate(cands):
        by_stratum.setdefault((cand.asset, cand.phase), {}).setdefault(
            cand.d8, []).append(position)
    out: list[S23.Scored] = []
    report = {"strata": 0, "days_scored": 0, "days_thin": 0, "rows": 0,
              "rows_no_impulse": 0, "cuts": {}}
    for (asset, phase), table in sorted(by_stratum.items()):
        report["strata"] += 1
        days = sorted(int(day) for day in explore_days[asset])
        for index, d8 in enumerate(days):
            today = table.get(d8, [])
            if index < MIN_PRIOR_DAYS or not today:
                continue
            train_days = (days[:index + 1] if mutant == MUTANT_TESTDAY
                          else days[:index])
            train = [p for day in train_days for p in table.get(day, [])]
            if len(train) < MIN_TRAIN_CANDS:
                report["days_thin"] += 1
                continue
            report["days_scored"] += 1
            take = np.asarray(train, np.int64)
            look = np.asarray(today, np.int64)
            block = raw[take]
            with np.errstate(invalid="ignore"):
                centre = np.nanmean(np.where(np.isfinite(block), block, np.nan),
                                    axis=0)
                spread = np.nanstd(np.where(np.isfinite(block), block, np.nan),
                                   axis=0)
            centre = np.where(np.isfinite(centre), centre, 0.0)
            spread = np.where(np.isfinite(spread) & (spread > 1e-12), spread, 1.0)
            b_train = np.nanmean(np.where(np.isfinite(block),
                                          (block - centre) / spread, np.nan),
                                 axis=1)
            b_train = np.where(np.isfinite(b_train), b_train, 0.0)
            i_raw_train = impulse[take]
            finite = np.isfinite(i_raw_train)
            i_mean = float(i_raw_train[finite].mean()) if finite.any() else 0.0
            i_sd = float(i_raw_train[finite].std()) if finite.any() else 1.0
            i_sd = i_sd if i_sd > 1e-12 else 1.0
            # Registered: the I cut is a percentile of the FINITE training I.
            i_train = ((i_raw_train[finite] - i_mean) / i_sd if finite.any()
                       else np.zeros(1, np.float64))
            cuts = {}
            for b_name, b_mark in BARRIER_CUTS.items():
                for i_name, i_mark in IMPULSE_CUTS.items():
                    cuts[(b_name, i_name)] = (
                        float(np.percentile(b_train, b_mark)),
                        float(np.percentile(i_train, i_mark)))
            report["cuts"][f"{asset}|{phase}|{d8}"] = {
                f"{b}|{i}": [v[0], v[1]] for (b, i), v in cuts.items()}
            scoreblock = raw[look]
            b_score = np.nanmean(
                np.where(np.isfinite(scoreblock),
                         (scoreblock - centre) / spread, np.nan), axis=1)
            b_score = np.where(np.isfinite(b_score), b_score, 0.0)
            i_raw = impulse[look]
            have = np.isfinite(i_raw)
            i_score = np.where(have, (i_raw - i_mean) / i_sd, np.nan)
            for local, position in enumerate(look):
                got = bool(have[local])
                if not got:
                    report["rows_no_impulse"] += 1
                selected = {}
                for key, (b_cut, i_cut) in cuts.items():
                    # Registered: a conjunction cannot be satisfied by a term
                    # that does not exist.
                    selected[key] = bool(got and b_score[local] >= b_cut
                                         and i_score[local] >= i_cut)
                out.append(S23.Scored(
                    position=int(position), b=float(b_score[local]),
                    i=float(i_score[local]) if got else float("nan"),
                    has_impulse=got, selected=selected))
                report["rows"] += 1
    return out, report


# --------------------------------------------------------------------------
# CORRECTION 4: the letters.  Five clauses, a precedence, a real partition.
# --------------------------------------------------------------------------

def classify(rung_ok: bool, mdd_ok: bool, cap_ok: bool, stress_ok: bool,
             control_ok: bool, neighbours_ok: bool, ceiling_carries: bool,
             upper_nonpositive: bool, matched_positive: bool
             ) -> tuple[str, str, list[str]]:
    """The registered partition.  Exactly one clause fires; the rest are listed.

    Exhaustive by construction: LIVE is the conjunction of every live bound, and
    its negation splits on ``ceiling_carries``, then ``upper_nonpositive``, then
    ``matched_positive``, with UNRESOLVED taking the remainder.  ``K3``,
    CEILING-UNREACHED, is the case sweep 22 had to record as a fallthrough.
    """

    live = bool(rung_ok and mdd_ok and cap_ok and stress_ok and control_ok
                and neighbours_ok)
    matching: list[str] = []
    if live:
        matching.append("LIVE")
    if not ceiling_carries:
        matching.append("K1")
    if upper_nonpositive:
        matching.append("K2")
    if ceiling_carries and not upper_nonpositive and not matched_positive:
        matching.append("K3")
    if (not live and ceiling_carries and not upper_nonpositive
            and matched_positive):
        matching.append("UNRESOLVED")
    for clause in CLAUSE_ORDER:
        if clause in matching:
            return CLAUSE_LETTER[clause], clause, matching
    raise SweepRefusal("the letter partition failed to cover a receipt; this is "
                       "the enumeration gap the corrected family closes")


def lane_letter(lane: str, report: Mapping[str, object]) -> dict[str, object]:
    live = report["live"][lane]                      # type: ignore[index]
    # The kill test reads the ceiling of the FORMED opportunity universe, not of
    # the subset this selector picked.  Scoring the kill against the selected
    # subset would let a selector that picks nothing kill the formation rule on
    # its own thinness.
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
    cap_ok = bool(live["cash"]["_portfolio"]["cap_lawful"])   # type: ignore[index]
    if not cap_ok:
        reasons.append("the portfolio cap was breached")
    stress_ok = all(bool(live["stress"][kind]["mdd"]["clears"])  # type: ignore[index]
                    for kind in ("adversarial", "spread"))
    if not stress_ok:
        reasons.append("a stress replay breaches MDD")
    control_ok = True
    for asset in DECIDING:
        cell = control.get(f"{lane}|{asset}")
        if cell is None or cell.get("p_max_adjusted") is None:
            control_ok = False
            reasons.append(f"{asset} has no powered matched control")
            continue
        if float(cell["p_max_adjusted"]) > 0.05:
            control_ok = False
            reasons.append(f"{asset} control p {cell['p_max_adjusted']:.4f} > 0.05")
    neighbours_ok = bool(live["neighbours_agree"])
    if not neighbours_ok:
        reasons.append("an adjacent fold-trained threshold flips the sign")

    ceiling_carries = all(
        bool(ceiling["cash"][asset].get("carries_rung"))   # type: ignore[index]
        for asset in DECIDING)
    if not ceiling_carries:
        reasons.append("the formed ceiling misses a deciding rung")
    matched_positive = all(
        (control.get(f"{lane}|{asset}") or {}).get("delta_usd_per_date", 0.0) > 0.0
        for asset in DECIDING)
    if not matched_positive:
        reasons.append("the causal matched delta is not positive on both "
                       "deciding assets")
    upper_nonpositive = any(
        (control.get(f"{lane}|{asset}") or {}).get(
            "upper95_simultaneous_usd") is not None
        and float(control[f"{lane}|{asset}"]["upper95_simultaneous_usd"]) <= 0.0
        for asset in DECIDING)
    if upper_nonpositive:
        reasons.append("a powered deciding asset has a non-positive 95% upper "
                       "bound against its matched control")

    letter, clause, matching = classify(
        rung_ok, mdd_ok, cap_ok, stress_ok, control_ok, neighbours_ok,
        ceiling_carries, upper_nonpositive, matched_positive)
    return {"lane": lane, "letter": letter, "clause": clause,
            "clause_text": CLAUSES[clause], "clauses_matching": matching,
            "reasons": reasons,
            "rung_ok": rung_ok, "mdd_ok": mdd_ok, "cap_ok": cap_ok,
            "stress_ok": stress_ok, "control_ok": control_ok,
            "neighbours_ok": neighbours_ok,
            "ceiling_carries_both_rungs": ceiling_carries,
            "upper_bound_nonpositive": upper_nonpositive,
            "matched_delta_positive": matched_positive}


# --------------------------------------------------------------------------
# Pricing: one shard pass, three lanes.
# --------------------------------------------------------------------------

def _fill_counters() -> dict[str, int]:
    return {"pb_armed": 0, "pb_filled": 0, "pb_no_fill": 0, "pb_no_window": 0,
            "pb_unpriceable": 0}


def pricing_pass(cands: Sequence[S23.Cand], joint_cands: Sequence[S23.Cand],
                 cells: Sequence[S8.Cell8], streams: Sequence[S14.Stream],
                 records: Sequence[S1.CellRec],
                 explore_days: Mapping[str, Sequence[int]], mutant: str
                 ) -> dict[str, object]:
    """One shard pass: the magnitude target, all three lanes, the G1 pool.

    Sweep 23's pass with lane A promoted out of report-only and lane C priced
    beside lane B on its own limit prices.  Both pullback lanes go through
    ``S23.price_pullback`` unchanged, so the raw-tick first-passage law, the
    floor/ceil convention and the strictly-after-the-breach arm search are the
    parent's, not a copy of them.
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
    fills = {LANE_B: _fill_counters(), LANE_C: _fill_counters()}
    mag: list[S22.MagRow] = []
    entries: dict[str, dict[int, S22.Priced]] = {lane: {} for lane in LANES}
    g1_pool: dict[tuple[str, int, str], list[dict[str, object]]] = {}
    g1_priced: dict[int, S22.Priced] = {}
    ceiling: dict[int, dict[str, object]] = {}
    mid_by_cell: dict[int, np.ndarray] = {}
    lat_by_cell: dict[int, np.ndarray] = {}
    cert_plane = S19.build_cert_plane(cells)
    plane_checks = {"compared": 0, "mismatched": 0, "worst_abs_usd": 0.0}
    # ``worst_gap_ns`` starts at None, not 0.  Seeding a max with 0 when every
    # lawful value is negative pins the reported worst at 0 forever, which is
    # exactly the number the line tells the reader must never appear.
    same_close: dict[str, object] = {"checked": 0, "violations": 0,
                                     "worst_gap_ns": None}
    audit: dict[str, list[dict[str, object]]] = {LANE_B: [], LANE_C: []}

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
                        index, rec, LANE_A, local, cand, asset, int(d8),
                        rec.phase, position, int(cand.bar) + 1,
                        int(cand.break_dir), counters, "nb")
                    if priced is None:
                        continue
                    entries[LANE_A][local] = priced
                    # The registered same-close prohibition, per priced row.
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

                # ---- LANES B and C: raw ticks decide the fill --------------
                for lane, pool in ((LANE_B, cands), (LANE_C, joint_cands)):
                    for entry in S23.price_pullback(index, rec, pool, mine,
                                                    fills[lane], audit[lane]):
                        entry.lane = lane
                        entries[lane][int(entry.position)] = entry

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
    return {"mag": mag, "entries": entries, "fills": fills,
            "g1_pool": g1_pool, "g1_priced": g1_priced, "ceiling": ceiling,
            "mid_by_cell": mid_by_cell, "lat_by_cell": lat_by_cell,
            "counters": counters, "coarse_counters": coarse_counters,
            "plane_checks": plane_checks, "same_close": same_close,
            "causality_rows": audit}


# --------------------------------------------------------------------------
# The run.
# --------------------------------------------------------------------------

def run() -> dict[str, object]:
    mutant = arm_mutant(_mutant())
    started = time.time()
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
        raise SweepRefusal("sweep 9's occurrence plane did not reproduce; no "
                           "candidate is formed past this point")
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

    # ---- formation: sweep 23's, unchanged, and the universe must match -----
    cands, formation = S23.formation_pass(cells, explore_days, "")
    if not formation["strictly_prior"]:
        raise SweepRefusal(
            f"a level read is not strictly prior to its breach close: "
            f"max(source - breach) = {formation['max_src_minus_breach_ns']} ns")
    if len(cands) != EXPECT_CANDIDATES:
        raise SweepRefusal(
            f"the formation pass returned {len(cands)} candidates, not the "
            f"parent's {EXPECT_CANDIDATES}; the universe is not identical, so "
            f"the corrections under test are not attributable")

    # ---- CORRECTION 1: the barrier read, at the fixed zone price -----------
    reader = LZ.reader(ASSETS)
    read = zone_read(cands, records, reader)
    assert_zone_anchored(read)

    # ---- the registered lane-C deviation: the joint pullback pair ----------
    profiles = build_profiles(cands, records)
    profile_check = {
        "rows": int(len(cands)),
        "agrees_with_parent_pool_stat": bool(np.allclose(
            np.clip(profiles[:, -1], *DEPTH_STAT_CLIP),
            np.asarray([float(c.pull_frac) for c in cands], np.float64),
            rtol=0.0, atol=1e-9)) if len(cands) else True}
    if not profile_check["agrees_with_parent_pool_stat"]:
        raise SweepRefusal(
            "the retracement profile disagrees with sweep 23's own depth "
            "statistic at the full window; lane C would not be lane B's law "
            "with a different estimator")
    joint_cands, joint_params_used, joint_counters = joint_pass(
        cands, records, profiles, explore_days)

    priced = pricing_pass(cands, joint_cands, cells, streams, records,
                          explore_days, mutant)
    if priced["plane_checks"]["mismatched"]:
        raise SweepRefusal(
            "a lane-A close-label cert disagreed with the frozen cert plane at "
            f"the same (cell, side, bar): worst "
            f"{priced['plane_checks']['worst_abs_usd']:.6f} USD")
    if priced["same_close"]["violations"]:
        raise SweepRefusal(
            f"{priced['same_close']['violations']} lane-A entries filled at or "
            f"before their own breach close; the same-close prohibition is the "
            f"registered law of that lane")
    for lane in PULLBACK_LANES:
        bad = [row for row in priced["causality_rows"][lane]
               if not (int(row["source_ts_ns"]) < int(row["breach_close_ts_ns"])
                       < int(row["arm_ts_ns"]) <= int(row["fill_ts_ns"]))]
        if bad:
            raise SweepRefusal(f"{lane}: a fill violates source < breach < arm "
                               f"<= fill: {bad[0]}")

    folds, impulse_report = S22.fit_impulse(priced["mag"], explore_days, mutant)
    # I_break: the last G1 occurrence in the candidate's own cell that closed
    # STRICTLY BEFORE the breach bar.  Sweep 23's join, unchanged.
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
    impulse, impulse_counters = S22.impulse_scores(cands, folds)

    have = priced["entries"]
    formed_by_asset = {asset: sum(1 for c in cands if c.asset == asset)
                       for asset in ASSETS}
    formed_opportunities: dict[str, int] = {}
    for cand in cands:
        key = f"{cand.asset}|{cand.d8}"
        formed_opportunities[key] = formed_opportunities.get(key, 0) + 1

    scores, score_report = score_selector(cands, read.raw, impulse,
                                          explore_days, mutant)
    score_summary = {k: v for k, v in score_report.items() if k != "cuts"}
    score_summary["cut_sample"] = dict(list(score_report["cuts"].items())[:3])
    score_summary["zone_read"] = read.counters

    live: dict[str, object] = {}
    grid_report: dict[str, object] = {}
    selected_entries: dict[str, list[S22.Priced]] = {}
    selected_positions: dict[str, list[int]] = {}
    for lane in LANES:
        pool = have[lane]
        by_cell = grid_report.setdefault(lane, {})
        for cut in GRID:
            picks = [row.position for row in scores
                     if row.selected.get(cut) and row.position in pool]
            chosen = [pool[p] for p in picks]
            block = S22.evaluate_lane(lane, chosen, cands, explore_days,
                                      formed_by_asset)
            by_cell[f"{cut[0]}|{cut[1]}"] = {
                "n": block["n"],
                "cash": {asset: {
                    "usd_per_day": block["cash"][asset]["usd_per_day"],
                    "mean_minus_2se_usd": block["cash"][asset][
                        "mean_minus_2se_usd"],
                    "clears_rung": block["cash"][asset]["clears_rung"]}
                    for asset in ASSETS}}
            if cut == LIVE_CELL:
                selected_entries[lane] = chosen
                selected_positions[lane] = picks
                live[lane] = block

    for lane in LANES:
        agree = True
        for asset in DECIDING:
            base = grid_report[lane][
                f"{LIVE_CELL[0]}|{LIVE_CELL[1]}"]["cash"][asset]["usd_per_day"]
            for cut in GRID:
                if cut == LIVE_CELL:
                    continue
                other = grid_report[lane][
                    f"{cut[0]}|{cut[1]}"]["cash"][asset]["usd_per_day"]
                if base is None or other is None:
                    agree = False
                elif (base > 0) != (other > 0):
                    agree = False
        live[lane]["neighbours_agree"] = bool(agree)

    # ---- stresses and MDD on the registered cell --------------------------
    for lane in LANES:
        chosen = selected_entries[lane]
        stress: dict[str, object] = {}
        for kind in ("adversarial", "spread"):
            overrides = S22.stress_overrides(chosen, CLOSE, kind)
            seated = S22.replay(chosen, CLOSE, overrides)
            stress[kind] = {
                "seated": seated["seated"],
                "cash": S22.replay_cash(seated["trades"], explore_days),
                "mdd": S22.mdd_ledgers(seated["trades"], priced["mid_by_cell"],
                                       priced["lat_by_cell"], explore_days)}
        live[lane]["stress"] = stress
        live[lane]["mdd"] = S22.mdd_ledgers(live[lane]["trades"],
                                            priced["mid_by_cell"],
                                            priced["lat_by_cell"], explore_days)
        live[lane].pop("trades", None)

    # ---- C2: the formed ceiling -------------------------------------------
    ceiling_block: dict[str, object] = {
        lane: {"cash": S23.ceiling_cash(selected_positions[lane], cands,
                                        priced["ceiling"], explore_days),
               "hindsight_bits": list(HINDSIGHT_CEILING)}
        for lane in LANES}
    ceiling_block["FORMED_UNIVERSE"] = {
        "cash": S23.ceiling_cash(range(len(cands)), cands, priced["ceiling"],
                                 explore_days),
        "hindsight_bits": list(HINDSIGHT_CEILING)}
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

    # ---- C1: matched, level-permuted controls ------------------------------
    finite = impulse[np.isfinite(impulse)]
    edges = (np.percentile(finite, [100.0 / 3.0, 200.0 / 3.0])
             if len(finite) else np.asarray([0.0, 0.0]))
    for key, rows in priced["g1_pool"].items():
        fold = folds.get((key[0], key[1]))
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
    control_lines: dict[str, dict[int, float]] = {}
    control_counters: dict[str, object] = {}
    permuted_selected: dict[str, object] = {}
    rng = np.random.default_rng(SEED + 63)
    for lane in LANES:
        chosen = selected_entries[lane]
        mag_bin = {}
        for entry in chosen:
            value = impulse[entry.position]
            mag_bin[entry.position] = int(
                np.searchsorted(edges, value)) if np.isfinite(value) else 0
        matched, counters = S22.match_controls(chosen, cands,
                                               priced["g1_pool"], impulse,
                                               mag_bin)
        control_counters[lane] = counters
        for asset in ASSETS:
            series: dict[int, float] = {}
            for position, entry in enumerate(chosen):
                if entry.asset != asset or position not in matched:
                    continue
                control_row = matched[position]
                control_entry = priced["g1_priced"].get(int(control_row["row"]))
                if control_entry is None:
                    continue
                series[int(entry.d8)] = series.get(int(entry.d8), 0.0) + (
                    float(entry.cert[CLOSE]) - float(control_entry.cert[CLOSE]))
            control_lines[f"{lane}|{asset}"] = series
        # The permutation diagnostic, on the ZONE-ANCHORED components: give each
        # matched control a level vector drawn from a permutation inside the
        # pool and ask how often it would have carried a positive barrier.
        if len(cands) and matched:
            draw = rng.permutation(len(cands))
            hits = 0
            with np.errstate(invalid="ignore"):
                for slot, _position in enumerate(sorted(matched)):
                    donor = read.raw[int(draw[slot % len(draw)])]
                    value = (float(np.nanmean(donor)) if np.isfinite(donor).any()
                             else float("nan"))
                    hits += int(math.isfinite(value) and value > 0.0)
            permuted_selected[lane] = {
                "n": len(matched),
                "share_permuted_positive_barrier": float(
                    hits / max(len(matched), 1))}
    family = [f"{lane}|{asset}" for lane in LANES for asset in DECIDING]
    control = S22.maxt_inference(control_lines, family, SIGN_DRAWS)

    # ---- C3: block-permutation nulls, with the standing caveat -------------
    eligible: dict[tuple[str, str, int], list[int]] = {}
    for position, cand in enumerate(cands):
        eligible.setdefault((cand.asset, cand.phase, cand.d8), []).append(position)
    nulls: dict[str, object] = {}
    for lane in LANES:
        pool = have[lane]
        cert_by_position = {p: float(pool[p].cert[CLOSE]) for p in pool}
        for asset in ASSETS:
            nulls[f"{lane}|{asset}"] = S22.block_null(
                selected_positions[lane], cands, eligible, cert_by_position,
                explore_days, asset, CONTROL_DRAWS)

    # ---- lane extras: direction, the selected cohort, the fill picture ----
    lane_extras: dict[str, object] = {}
    for lane in LANES:
        direction: dict[str, dict[int, int]] = {}
        window: dict[str, dict[str, float]] = {}
        for entry in selected_entries[lane]:
            cand = cands[entry.position]
            table = direction.setdefault(cand.asset, {1: 0, -1: 0})
            table[int(cand.break_dir)] = table.get(int(cand.break_dir), 0) + 1
            row = window.setdefault(cand.asset, {
                "n": 0, "defence_history": 0.0, "pull_frac": 0.0,
                "pull_dur": 0.0, "ext_reach": 0.0, "visit_touches": 0.0,
                "visit_flow": 0.0, "sd_diff": 0.0, "day_scale": 0.0,
                "ps_diff": 0.0})
            row["n"] += 1
            row["defence_history"] += cand.defence_history
            row["pull_frac"] += cand.pull_frac
            row["pull_dur"] += cand.pull_dur
            row["ext_reach"] += cand.ext_reach
            row["visit_touches"] += cand.visit_touches
            row["visit_flow"] += cand.visit_flow
            row["sd_diff"] += S23._nan0(read.raw[entry.position, 0])
            row["day_scale"] += S23._nan0(read.raw[entry.position, 1])
            row["ps_diff"] += S23._nan0(read.raw[entry.position, 2])
        for row in window.values():
            n = max(row["n"], 1)
            for key in list(row):
                if key != "n":
                    row[key] = float(row[key] / n)
            row["n"] = int(n)
        lane_extras[lane] = {"direction": direction, "window": window}
    formed_components = {}
    for asset in ASSETS:
        mine = [position for position, c in enumerate(cands) if c.asset == asset]
        if not mine:
            continue
        stack = read.raw[np.asarray(mine, np.int64)]
        with np.errstate(invalid="ignore"):
            formed_components[asset] = {
                "n": int(len(mine)),
                "sd_diff": float(np.nanmean(stack[:, 0])),
                "day_scale_persistence": float(np.nanmean(stack[:, 1])),
                "ps_diff": float(np.nanmean(stack[:, 2])),
                "defence_history": float(np.mean(
                    [cands[p].defence_history for p in mine]))}

    report: dict[str, object] = {
        "schema": "QRE2MILLSWEEP25", "spec_sha": SPEC_SHA,
        "code_sha": code_sha(), "split_sha": S1.split_sha(),
        "outcome_law_sha": S1.outcome_law_sha(), "seed": SEED,
        "mutant": mutant, "family": FAMILY, "parent_trial": PARENT_TRIAL,
        "selection_rule": SELECTION_RULE, "registered_utc": report_stamp(),
        "deviation_note": DEVIATION_NOTE,
        "selector_sign_note": S23.SELECTOR_SIGN_NOTE,
        "contamination_note": CONTAMINATION_NOTE,
        "parent_spec_sha": S23.SPEC_SHA, "parent_code_sha": S23.code_sha(),
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
            "side": "defence_side = -break_dir, the FORMER DEFENDING SIDE, the "
                    "side trapped by the break",
            "decision_stamp": "lat[breach_bar - 1], the lattice close of the "
                              "last completed bar BEFORE the breach close; the "
                              "accessor counts only bars closing strictly "
                              "before it, so the read sees bars 0..breach_bar-2",
            "breach_excluded": True,
            "day_scale_mode": "approach, approach_side = break_dir",
            "third_component": "day_scale_persistence, a day-scale persistence "
                               "and location proxy, NOT prior-day defence "
                               "memory",
            "zero_default": "NONE.  F20 has one decision event, so every "
                            "candidate carries exactly one accessor row and no "
                            "component is ever defaulted to zero.  Sweep 24's "
                            "quirk arose only because its lane 2 owned a second "
                            "stamp that 12,775 candidates never reached.  Where "
                            "a component is genuinely unreadable it is NaN and "
                            "drops out of the component mean; the counts are "
                            "reported above as *_undefined"},
        "lane_c_deviation": {
            "note": DEVIATION_NOTE,
            "law": "cancel = ceil(Q_CANCEL percentile of the durations of "
                   "training pullbacks that RETURNED), clipped to "
                   f"{list(CANCEL_CLIP)}; depth = Q_DEPTH percentile of the "
                   "running-max retracement reached WITHIN that window among "
                   "training pullbacks that returned inside it, clipped to "
                   f"{list(DEPTH_CLIP)}",
            "counters": joint_counters,
            "profile_check": profile_check,
            "params_sample": dict(list(joint_params_used.items())[:3])},
        "pricing_counters": priced["counters"],
        "fill_counters": priced["fills"],
        "coarse_counters": priced["coarse_counters"],
        "plane_checks": priced["plane_checks"],
        "same_close_check": priced["same_close"],
        "causality_rows": {lane: priced["causality_rows"][lane][:10]
                           for lane in PULLBACK_LANES},
        "impulse": impulse_report, "impulse_join": join,
        "impulse_counters": impulse_counters,
        "selector": score_summary, "grid": grid_report, "live": live,
        "ceiling": ceiling_block, "control": control,
        "control_counters": control_counters,
        "control_permutation": permuted_selected,
        "block_nulls": nulls, "block_null_caveat": C3_CAVEAT,
        "lane_extras": lane_extras, "formed_components": formed_components,
        "scoring_days": {a: scoring[a] for a in ASSETS},
        "clauses": CLAUSES, "clause_order": list(CLAUSE_ORDER),
        "elapsed_s": round(time.time() - started, 1)}
    letters = {lane: lane_letter(lane, report) for lane in LANES}
    if any(letters[lane]["letter"] == LETTER_LIVE for lane in LANES):
        family_letter, family_clause = LETTER_LIVE, "LIVE"
    elif any(letters[lane]["letter"] == LETTER_UNRESOLVED for lane in LANES):
        family_letter, family_clause = LETTER_UNRESOLVED, "UNRESOLVED"
    else:
        family_letter = LETTER_KILL
        family_clause = min((letters[lane]["clause"] for lane in LANES),
                            key=lambda c: CLAUSE_ORDER.index(c))
    report["letters"] = letters
    report["family_letter"] = family_letter
    report["family_clause"] = family_clause
    report["headline"] = headline(report)
    return report


def headline(report: Mapping[str, object]) -> dict[str, object]:
    """Best lane's deciding usd/day over rung, formed ceiling ratios beside."""

    best = None
    for lane in LANES:
        cash = report["live"][lane]["cash"]              # type: ignore[index]
        ratios = []
        for asset in DECIDING:
            value = cash[asset]["usd_per_day"]
            ratios.append(None if value is None
                          else value / DAY_RUNG_USD[asset])
        worst = min([r for r in ratios if r is not None], default=None)
        if worst is not None and (best is None or worst > best[0]):
            best = (worst, lane, ratios)
    ceiling = report["ceiling"]["FORMED_UNIVERSE"]["cash"]  # type: ignore[index]
    capped = report["ceiling"]["FORMED_CAPPED"]["cash"]     # type: ignore[index]
    return {
        "read": "zone-anchored",
        "best_lane": None if best is None else best[1],
        "best_lane_over_rung": {} if best is None else {
            asset: best[2][i] for i, asset in enumerate(DECIDING)},
        "lane_over_rung": {
            lane: {asset: (None if report["live"][lane]["cash"][asset][
                "usd_per_day"] is None
                else report["live"][lane]["cash"][asset]["usd_per_day"]
                / DAY_RUNG_USD[asset]) for asset in DECIDING}
            for lane in LANES},
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
    best = ", ".join(
        f"{asset} {_n(head['best_lane_over_rung'].get(asset), 7, 4)}x"
        for asset in DECIDING)
    ceiling = ", ".join(
        f"{asset} {_n(head['formed_ceiling_over_rung'].get(asset), 7, 3)}x"
        for asset in DECIDING)
    capped = ", ".join(
        f"{asset} {_n(head['capped_ceiling_over_rung'].get(asset), 6, 3)}x"
        for asset in DECIDING)
    print(f"F20-STRUCTBREAK-ZONEANCHOR zone-anchored: best lane "
          f"{head['best_lane']} deciding usd/day over rung {best}; formed "
          f"ceiling {ceiling} (capped {capped}); family {head['family_letter']} "
          f"(clause {head['family_clause']})")


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
    print(f"  candidates match sweep 23's {EXPECT_CANDIDATES}: "
          f"{report['candidates_match_parent']}")
    print(f"  formation counters       : {formation['counters']}")
    print(f"  pricing counters         : {report['pricing_counters']}")
    print(f"  fill counters            : {report['fill_counters']}")
    checks = report["plane_checks"]
    print(f"  lane A vs frozen cert plane: compared {checks['compared']}, "
          f"mismatched {checks['mismatched']}, worst "
          f"{checks['worst_abs_usd']:.9f} USD")
    same = report["same_close_check"]
    print(f"  lane A same-close prohibition: checked {same['checked']}, "
          f"violations {same['violations']}, worst (breach close - entry) "
          f"{_show(same['worst_gap_ns'])} ns over the priced rows "
          f"(must be strictly negative; None means no row was priced)")
    print(f"  impulse ridge            : {report['impulse']['counters']}, "
          f"WITHIN-DAY R2 {report['impulse']['pooled_within_day_r2']}")
    print(f"  impulse join             : {report['impulse_join']}, "
          f"{report['impulse_counters']}")
    print(f"  selector                 : {report['selector']['strata']} strata, "
          f"{report['selector']['days_scored']} days scored, "
          f"{report['selector']['days_thin']} thin, "
          f"{report['selector']['rows']} rows, "
          f"{report['selector']['rows_no_impulse']} with no impulse score "
          f"(never selected, by registration)")


def print_zone_read(report: Mapping[str, object]) -> None:
    law = report["zone_read_law"]
    cell = report["zone_read"]
    print("\n== CORRECTION 1: THE BARRIER READ AT THE FIXED ZONE PRICE ==")
    print(f"  accessor        : {law['accessor']}")
    print(f"  side            : {law['side']}")
    print(f"  decision stamp  : {law['decision_stamp']}")
    print(f"  day-scale mode  : {law['day_scale_mode']}")
    print(f"  third component : {law['third_component']}")
    print(f"  candidates {cell['candidates']}, queries {cell['queries']}, rows "
          f"{cell['rows']}, no decision stamp {cell['no_decision_stamp']}")
    print(f"  centre EXACT {cell['center_exact']}/{cell['rows']}, mismatched "
          f"{cell['center_mismatched']}, worst gap "
          f"{cell['worst_center_gap_mid2']} mid2")
    print(f"  strictly prior {cell['strictly_prior']}/{cell['rows']}, worst "
          f"(source - decision) {cell['worst_source_minus_decision_ns']} ns")
    print(f"  definedness: same-day {cell['same_day_defined']} defined / "
          f"{cell['same_day_undefined']} undefined; day-scale "
          f"{cell['day_scale_defined']} / {cell['day_scale_undefined']}; "
          f"prior-session {cell['prior_session_defined']} / "
          f"{cell['prior_session_undefined']}; all three undefined "
          f"{cell['all_three_undefined']}")
    print(f"  prior session served {cell['prior_session_served']}, absent "
          f"{cell['prior_session_absent']}")
    print(f"  ZERO DEFAULTS USED: {cell['zero_default_used']}, fallback reads "
          f"{cell['fallback_reads']}")
    print(f"  {law['zero_default']}")
    print("\n  barrier decomposition over the WHOLE formed universe, read at "
          "the fixed zone on the defending side:")
    print("  asset      n   sd_diff  day_scale   ps_diff  defence_history")
    for asset, row in sorted(report["formed_components"].items()):
        print(f"  {asset:<5} {row['n']:>6} {_n(row['sd_diff'], 9, 3)} "
              f"{_n(row['day_scale_persistence'], 10, 3)} "
              f"{_n(row['ps_diff'], 9, 3)} "
              f"{_n(row['defence_history'], 16, 3)}")


def print_deviation(report: Mapping[str, object]) -> None:
    block = report["lane_c_deviation"]
    print("\n== REGISTERED PARENT DEVIATION: LANE C, THE JOINT PULLBACK PAIR ==")
    print(f"  {block['note']}")
    print(f"  LAW: {block['law']}")
    print(f"  counters: {block['counters']}")
    print(f"  profile agrees with sweep 23's own depth statistic at the full "
          f"window: {block['profile_check']['agrees_with_parent_pool_stat']} "
          f"over {block['profile_check']['rows']} rows")
    print("\n  sample strata, last scored day: marginal pair vs joint pair and "
          "the reachable share of the training pool at each")
    print("  stratum   day        marg depth  marg cancel   joint depth  "
          "joint cancel   reach(marg)  reach(joint)  train  returners")
    for stratum, table in block["params_sample"].items():
        for d8, row in list(table.items())[-2:]:
            print(f"  {stratum:<9} {d8}  {row['marginal_depth_frac']:>10.4f} "
                  f"{row['marginal_cancel_bars']:>12} "
                  f"{row['joint_depth_frac']:>13.4f} "
                  f"{row['joint_cancel_bars']:>13} "
                  f"{_n(row['reachable_at_marginal_pair'], 13, 4)} "
                  f"{_n(row['reachable_at_joint_pair'], 13, 4)} "
                  f"{row['train_rows']:>6} {row['returners']:>10}")
    fills = report["fill_counters"]
    print("\n  fill and cancel rates per pullback lane:")
    for lane in PULLBACK_LANES:
        cell = fills[lane]
        armed = max(int(cell["pb_armed"]), 1)
        print(f"    {lane:<18} armed {cell['pb_armed']:>5}, filled "
              f"{cell['pb_filled']:>5} ({cell['pb_filled'] / armed:.4f}), "
              f"cancelled unfilled {cell['pb_no_fill']:>5} "
              f"({cell['pb_no_fill'] / armed:.4f}), no tick window "
              f"{cell['pb_no_window']}, unpriceable {cell['pb_unpriceable']}")


def print_causality_rows(report: Mapping[str, object]) -> None:
    print("\n== CAUSALITY, REAL FILLED PULLBACK ROWS: source < breach close < "
          "arm <= fill ==")
    for lane in PULLBACK_LANES:
        rows = report["causality_rows"][lane]
        print(f"  {lane}")
        if not rows:
            print("    (no filled rows)")
            continue
        print("    asset      d8 ph zone            dir  read breach   "
              "source-minus-fill_ns   breach-minus-arm_ns")
        worst_src = None
        worst_arm = None
        for row in rows:
            src_gap = int(row["source_ts_ns"]) - int(row["fill_ts_ns"])
            arm_gap = int(row["breach_close_ts_ns"]) - int(row["arm_ts_ns"])
            worst_src = src_gap if worst_src is None else max(worst_src, src_gap)
            worst_arm = arm_gap if worst_arm is None else max(worst_arm, arm_gap)
            print(f"    {row['asset']:<5} {row['d8']} {row['phase']:>2} "
                  f"{row['zone']:<15} {row['dir']:>3} {row['read_bar']:>5} "
                  f"{row['breach_bar']:>6} {src_gap:>22d} {arm_gap:>21d}")
        print(f"    max source-minus-fill {worst_src} ns, max breach-minus-arm "
              f"{worst_arm} ns (both must be strictly negative)")


def print_formation(report: Mapping[str, object]) -> None:
    print("\n== FORMED OPPORTUNITIES AND CANDIDATES ==")
    per_day = report["formed_opportunities_per_asset_day"]
    for asset in ASSETS:
        mine = [v for k, v in per_day.items() if k.startswith(f"{asset}|")]
        total = sum(mine)
        print(f"  {asset:<4} asset-days with candidates {len(mine):>4}  "
              f"candidates {total:>6}  per asset-day mean "
              f"{(total / len(mine) if mine else 0):8.2f}  max "
              f"{(max(mine) if mine else 0):>4}")
    counters = report["formation"]["counters"]
    total_breach = max(int(counters["breach_closes"]), 1)
    print(f"  breaching closes seen {counters['breach_closes']}: formed "
          f"{counters['candidates']} "
          f"({counters['candidates'] / total_breach:.3f}), deduped "
          f"{counters['breach_deduped']}, rejected for no zone visit "
          f"{counters['breach_no_zone_visit']}, rejected for NO DEFENCE HISTORY "
          f"{counters['breach_no_defence_history']}")
    print(f"  direction of formed breaks: up {counters['breach_up']}, down "
          f"{counters['breach_down']}")
    print("  fold-trained formation parameters, sample strata:")
    for stratum, table in report["formation_params_sample"].items():
        for d8, block in list(table.items())[-1:]:
            print(f"    {stratum:<8} {d8}  band x{block['width_atr']:.2f} ATR  "
                  f"marginal depth {block['depth_frac']:.3f} of full width, "
                  f"cancel {block['cancel_bars']} bars, train "
                  f"{block['train_days']} days / {block['train_cands']} "
                  f"candidates")


def print_lane(report: Mapping[str, object], lane: str) -> None:
    print(f"\n== LANE {lane}: {LANE_NAME[lane]} ==")
    block = report["live"][lane]
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
    print(f"  neighbours agree on sign : {block['neighbours_agree']}")
    for name, table in block["breakdowns"].items():
        cells = ", ".join(f"{k} n={v['n']} mean {v['mean_usd']:.0f}"
                          for k, v in table.items())
        print(f"  by {name:<10}: {cells if cells else '-'}")
    extras = report["lane_extras"][lane]
    print("  break direction split of the selected cohort: " + "; ".join(
        f"{asset} up {extras['direction'].get(asset, {}).get(1, 0)} down "
        f"{extras['direction'].get(asset, {}).get(-1, 0)}" for asset in ASSETS))
    print("  selected-cohort features (recorded, NOT gating):")
    print("  asset   n  defence  sd_diff  day_scale  ps_diff  pull_frac  "
          "pull_dur  ext_reach  visits    flow")
    for asset in ASSETS:
        row = extras["window"].get(asset)
        if not row:
            continue
        print(f"  {asset:<5} {row['n']:>4} {_n(row['defence_history'], 7, 2)} "
              f"{_n(row['sd_diff'], 8, 2)} {_n(row['day_scale'], 10, 2)} "
              f"{_n(row['ps_diff'], 8, 2)} {_n(row['pull_frac'], 10, 3)} "
              f"{_n(row['pull_dur'], 9, 1)} {_n(row['ext_reach'], 10, 2)} "
              f"{_n(row['visit_touches'], 7, 1)} {_n(row['visit_flow'], 7, 0)}")


def print_grid(report: Mapping[str, object]) -> None:
    print("\n== SELECTOR SENSITIVITY GRID (barrier cut x impulse cut) ==")
    print("  the registered LIVE cell is (tercile, median); the other three "
          "are its neighbours")
    for lane in LANES:
        print(f"  {lane}")
        print("    barrier  impulse     n     NKD usd/day   NKD -2SE      "
              "SI usd/day    SI -2SE   registered")
        for cut in GRID:
            cell = report["grid"][lane][f"{cut[0]}|{cut[1]}"]
            print(f"    {cut[0]:<8} {cut[1]:<8} {cell['n']:>5} "
                  f"{_n(cell['cash']['NKD']['usd_per_day'], 13, 1)} "
                  f"{_n(cell['cash']['NKD']['mean_minus_2se_usd'], 11, 1)} "
                  f"{_n(cell['cash']['SI']['usd_per_day'], 12, 1)} "
                  f"{_n(cell['cash']['SI']['mean_minus_2se_usd'], 10, 1)}"
                  f"{'   <-- LIVE' if tuple(cut) == LIVE_CELL else ''}")


def print_controls(report: Mapping[str, object]) -> None:
    control = report["control"]
    print("\n== C1: PAIRED MATCHED CONTROL, level memory permuted in fold ==")
    print(f"  shared-date-sign maxT, {control['draws']} draws over "
          f"{control['dates']} dates, family {control['family']} "
          f"(3 lanes x 2 deciding assets), c95 {_n(control['c95'], 7, 3)}")
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
    print(f"  match counters: {report['control_counters']}")
    print(f"  permuted-level diagnostic: {report['control_permutation']}")

    print("\n== C2: FORMED-OPPORTUNITY CEILING (exploratory) ==")
    print(f"  hindsight bits spent: {'; '.join(HINDSIGHT_CEILING)}")
    print("  scope                    asset      n     usd/day   over-rung "
          "carries")
    for scope in list(LANES) + ["FORMED_UNIVERSE", "FORMED_CAPPED"]:
        for asset in ASSETS:
            cell = report["ceiling"][scope]["cash"][asset]
            print(f"  {scope:<24} {asset:<5} {cell['n']:>6} "
                  f"{_n(cell['usd_per_day'], 11, 1)} "
                  f"{_n(cell['over_rung'], 10, 3)} "
                  f"{_n(cell.get('carries_rung'), 8)}")

    print("\n== C3: BLOCK-PERMUTATION NULLS ON EVERY HEADLINE ==")
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
    print("\n== DECISION TABLE ==")
    for lane in LANES:
        ratios = ", ".join(
            f"{asset} {_n(head['lane_over_rung'][lane].get(asset), 7, 4)}x rung"
            for asset in DECIDING)
        print(f"  {lane:<18} {ratios}")
    ceiling = ", ".join(
        f"{asset} {_n(head['formed_ceiling_over_rung'].get(asset), 7, 3)}x rung"
        for asset in DECIDING)
    print(f"  BEST LANE {head['best_lane']}; formed ceiling beside it: {ceiling}")
    print("  lane               letter                  rung  MDD  cap  stress "
          " control  neighbours  ceiling  upper<=0  matched+")
    for lane in LANES:
        cell = report["letters"][lane]
        print(f"  {lane:<18} {cell['letter']:<23} {_n(cell['rung_ok'], 5)} "
              f"{_n(cell['mdd_ok'], 4)} {_n(cell['cap_ok'], 4)} "
              f"{_n(cell['stress_ok'], 6)} {_n(cell['control_ok'], 8)} "
              f"{_n(cell['neighbours_ok'], 11)} "
              f"{_n(cell['ceiling_carries_both_rungs'], 8)} "
              f"{_n(cell['upper_bound_nonpositive'], 9)} "
              f"{_n(cell['matched_delta_positive'], 9)}")
        print(f"      CLAUSE {cell['clause']}: {cell['clause_text']}")
        print(f"      clauses matching: {cell['clauses_matching']}")
        for reason in cell["reasons"]:
            print(f"      - {reason}")
    print(f"\n  FAMILY LETTER: {report['family_letter']} "
          f"(clause {report['family_clause']})")
    print("  the registered partition, exhaustive over all 512 outcome points:")
    for clause in CLAUSE_ORDER:
        print(f"    {clause:<11} -> {CLAUSE_LETTER[clause]:<24} "
              f"{CLAUSES[clause]}")


# --------------------------------------------------------------------------
# Selftest: the planted worlds, rebuilt with the corrected read.
# --------------------------------------------------------------------------

def plant_tape() -> tuple[LZ.Tape, dict[str, object]]:
    """Sweep 23's break world, rebuilt so each zone EARNS its defence history.

    Sweep 23 planted the cache's defence columns directly, so its path never had
    to earn a hold or a break at the zone; that is precisely what let a
    miscentred read look green.  The zone-anchored read counts real touches under
    ``levels.outcome_bars``, so the world now carries a prologue in which the
    defended zone genuinely HOLDS three times against the side that later gets
    trapped, and the undefended zone genuinely BREAKS twice against the same
    side, before each zone is broken upward.  Every count is hand-derived in
    ``_selftest_planted``.
    """

    path = [
        940.0, 970.0,                       # 0-1   approach D from below
        995.0, 1005.0, 1000.0,              # 2-4   three touches of D = 1000
        985.0,                              # 5     <= 985: all three HELD
        960.0, 975.0,                       # 6-7   away, outside the band
        995.0, 1004.0,                      # 8-9   two more touches of D
        1030.0,                             # 10    THE D BREACH BAR (up)
        1120.0, 1250.0,                     # 11-12 travel to U
        1395.0, 1402.0,                     # 13-14 two touches of U = 1400
        1425.0,                             # 15    > 1412: both BROKE
        1380.0, 1350.0,                     # 16-17 fall away, arm U again
        1396.0, 1404.0,                     # 18-19 two more touches of U
        1440.0,                             # 20    THE U BREACH BAR (up)
        1500.0, 1460.0,                     # 21-22 the continuation
    ]
    mid = np.asarray(path, np.float64)
    n = len(mid)
    ts = (np.arange(n, dtype=np.int64) * S1.BAR_NS + 1_600_000_000_000_000_000)
    tape = LZ.Tape(asset="HG", d8=20220315, ts=ts, mid=mid,
                   delta=np.zeros(n, np.float64), sourced=np.ones(n, bool))
    world = {"defended": PLANT_DEFENDED, "undefended": PLANT_UNDEFENDED,
             "width": PLANT_WIDTH,
             "defended_breach_bar": 10, "undefended_breach_bar": 20,
             "defended_kind": "PD_HIGH", "undefended_kind": "PD_CLOSE",
             "break_dir": 1, "defence_side": -1}
    return tape, world


def planted_read(tape: LZ.Tape, zone: float, breach_bar: int,
                 world: Mapping[str, object], kind: str) -> dict[str, object]:
    """One zone-anchored read on the fixture, through the accessor's own law.

    The decision stamp is this unit's registered stamp - the close of the last
    completed bar BEFORE the breach close - and ``resolved_center`` is the
    accessor's single centre choke point, so the registered centre mutant reaches
    this fixture exactly as it reaches the real rows.
    """

    stamp = int(tape.ts[int(breach_bar) - 1])
    width = float(world["width"])
    side = int(world["defence_side"])
    window = LZ.prior_window(tape, stamp)
    center = LZ.resolved_center(float(zone), tape, window)
    same = LZ.same_day_counts(tape, center, width, side, stamp)
    scale = LZ.day_scale_terms(tape.mid, tape.ts, center, width, stamp,
                               zone_kind=kind,
                               approach_side=int(world["break_dir"]),
                               mode="approach")
    components = np.asarray([float(same["held"]) - float(same["broke"]),
                             float(scale["persistence"]), float("nan")],
                            np.float64)
    with np.errstate(invalid="ignore"):
        b = float(np.nanmean(components))
    return {"center": float(center), "zone": float(zone), "window": int(window),
            "stamp": stamp, "sd_touches": float(same["touches"]),
            "sd_held": float(same["held"]), "sd_broke": float(same["broke"]),
            "day_scale_held": float(scale["held"]),
            "day_scale_broke": float(scale["broke"]),
            "day_scale_persistence": float(scale["persistence"]), "b": b}


def _selftest_planted() -> list[tuple[str, bool, str]]:
    """The planted break, read AT the zone on the DEFENDING side, by hand.

    Defended zone D = 1000, half width 10, defending side -1 (the break is
    upward, so the trapped side is the one that was selling into 1000).  Under
    ``levels.outcome_bars`` with side -1 and HOLD_BANDS = BREACH_BANDS = 1, a
    touch at P HELD when a later bar printed at or below P - 10 before any bar
    printed above P + 10, and BROKE the other way round.

    D's breach is bar 10, so the decision stamp is ts[9] and the window is bars
    0..8.  Inside [990, 1010]: bars 2 (995), 3 (1005), 4 (1000) and 8 (995) -
    four touches; bars 5 (985), 6 (960) and 7 (975) miss.  Bar 5 prints 985,
    which is <= 985, <= 995 and <= 990, so bars 2, 3 and 4 all HELD at bar 5,
    and bar 5 closed before the stamp.  Bar 8's only verdict is the breach bar
    itself at 1030, which is NOT before the stamp, so it is a touch with no
    outcome.  Hence sd_held 3, sd_broke 0, difference +3.

    U = 1400 breaches at bar 20, stamp ts[19], window bars 0..18.  Inside
    [1390, 1410]: bars 13 (1395), 14 (1402) and 18 (1396).  Bar 15 prints 1425,
    above 1405 and above 1412, and the first bar at or below 1385 is bar 16
    (1380), which is later, so bars 13 and 14 both BROKE at bar 15 - inside the
    window.  Bar 18's verdict is the breach bar at 1440, outside it.  Hence
    sd_held 0, sd_broke 2, difference -2.

    Day scale: D is a PD_HIGH, a completed session's turn, so held = 1, and the
    window's high is 1005, which never cleared 1010, so broke = 0 and
    persistence = +1.  U is a PD_CLOSE, not a turn kind, so held = 0, and the
    window has already printed 1425 above 1410, so broke = 1 and persistence
    = -1.  The prior session is absent in the fixture, so the third component is
    NaN and drops out.  B_opp is +2.0 at D and -1.5 at U.
    """

    tape, world = plant_tape()
    out: list[tuple[str, bool, str]] = []
    trapped = planted_read(tape, world["defended"],
                           world["defended_breach_bar"], world,
                           world["defended_kind"])
    weak = planted_read(tape, world["undefended"],
                        world["undefended_breach_bar"], world,
                        world["undefended_kind"])

    out.append(_check(
        "the barrier is read AT the defended zone, not at the reading bar's mid",
        trapped["center"] == world["defended"],
        f"centre {trapped['center']} vs zone {world['defended']}, last "
        f"completed mid {float(tape.mid[trapped['window'] - 1])}"))
    out.append(_check(
        "the barrier is read AT the weakly defended zone",
        weak["center"] == world["undefended"],
        f"centre {weak['center']} vs zone {world['undefended']}"))
    out.append(_check(
        "the read stops at the last completed bar BEFORE the breach close, so "
        "the breach never enters its own barrier score",
        trapped["window"] == world["defended_breach_bar"] - 1
        and weak["window"] == world["undefended_breach_bar"] - 1
        and trapped["stamp"] == int(tape.ts[world["defended_breach_bar"] - 1]),
        f"D window {trapped['window']} (breach bar "
        f"{world['defended_breach_bar']}), U window {weak['window']} (breach "
        f"bar {world['undefended_breach_bar']})"))
    out.append(_check(
        "the trapped cohort's hand count is 4 touches, 3 held, 0 broke",
        trapped["sd_touches"] == 4.0 and trapped["sd_held"] == 3.0
        and trapped["sd_broke"] == 0.0,
        f"touches {trapped['sd_touches']}, held {trapped['sd_held']}, broke "
        f"{trapped['sd_broke']}"))
    out.append(_check(
        "the weak zone's hand count is 3 touches, 0 held, 2 broke",
        weak["sd_touches"] == 3.0 and weak["sd_held"] == 0.0
        and weak["sd_broke"] == 2.0,
        f"touches {weak['sd_touches']}, held {weak['sd_held']}, broke "
        f"{weak['sd_broke']}"))
    out.append(_check(
        "the day-scale persistence proxy is +1 at the defended zone and -1 at "
        "the weak zone",
        trapped["day_scale_persistence"] == 1.0
        and weak["day_scale_persistence"] == -1.0,
        f"D {trapped['day_scale_persistence']}, U "
        f"{weak['day_scale_persistence']}"))
    out.append(_check(
        "the hand-computed B_opp is +2.0 at the defended zone and -1.5 at the "
        "weak zone",
        abs(trapped["b"] - 2.0) < 1e-12 and abs(weak["b"] + 1.5) < 1e-12,
        f"D {trapped['b']}, U {weak['b']}"))
    out.append(_check(
        "THE PLANTED RECOVERY: the zone-anchored B_opp ranks the TRAPPED-COHORT "
        "case above the weak-defence case",
        trapped["b"] > weak["b"],
        f"trapped {trapped['b']:.3f} vs weak {weak['b']:.3f}"))
    # The side matters: read the CONTINUATION side instead and the ranking that
    # the mechanism depends on is not the same measurement.
    flipped = LZ.same_day_counts(
        tape, float(world["defended"]), float(world["width"]), 1,
        int(tape.ts[int(world["defended_breach_bar"]) - 1]))
    out.append(_check(
        "the defending side is signed: the same touches on the CONTINUATION "
        "side are not the same counts",
        float(flipped["held"]) != trapped["sd_held"],
        f"defending held {trapped['sd_held']} vs continuation held "
        f"{flipped['held']}"))
    return out


def _selftest_center_gate_real() -> list[tuple[str, bool, str]]:
    """The centre gate on REAL rows: 50 formed candidates of THIS family.

    Sweep 24 drew from sweep 22's formed candidates because that was its own
    universe.  This unit's universe is sweep 23's breach formation, so the gate
    is asserted against the bytes this run actually reads: real candidates, real
    zone prices, and this unit's own decision stamp.
    """

    cells, _days, _skipped = S8.build_cells(ASSETS)
    records, _rec_days = S1.load_cache()
    explore_days = S1._explore_days(ASSETS)
    cands, formation = S23.formation_pass(cells, explore_days, "")
    out = [_check(
        "the real formation reproduces sweep 23's candidate universe",
        len(cands) == EXPECT_CANDIDATES and bool(formation["strictly_prior"]),
        f"{len(cands)} candidates, strictly prior "
        f"{formation['strictly_prior']}")]
    if not cands:
        return out + [_check("50 real formed candidates are drawn", False,
                             "no candidates")]
    # Stratified by (asset, zone kind) so the draw is not one asset's day.
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
    # Round robin across strata, so the first fifty are spread over every
    # (asset, zone kind) rather than over the earliest days.
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
    for cand, position in zip(sample, range(len(sample))):
        lat = np.asarray(records[int(cand.cell)].lat, np.int64)
        if int(read.stamp[position]) != int(lat[int(cand.bar) - 1]):
            stamps_ok = False
    out.append(_check(
        "every real row is stamped at the last completed bar BEFORE the breach "
        "close, so the breach bar is excluded from its own barrier score",
        stamps_ok, f"{len(sample)} rows checked"))
    out.append(_check(
        "no real row takes a zero default or a fallback read",
        counters["zero_default_used"] == 0 and counters["fallback_reads"] == 0
        and counters["no_decision_stamp"] == 0,
        f"zero defaults {counters['zero_default_used']}, fallbacks "
        f"{counters['fallback_reads']}, no stamp "
        f"{counters['no_decision_stamp']}"))
    return out


def _selftest_joint_pair() -> list[tuple[str, bool, str]]:
    """The lane-C law, on a training set whose marginals do not compose.

    One hundred training pullbacks, two kinds, hand-built so the arithmetic is
    visible:

      FAST, 50 rows: return to the broken edge at bar 2 and reach 0.20 of a full
        width, and never go deeper for the rest of the window.
      SLOW, 50 rows: run away first - the running-max retracement is still only
        0.10 at bar 31 - and only return at bar 60, reaching 0.90 by then.

    MARGINALS.  The depth pool is fifty 0.20s and fifty 0.90s, so its 50th
    percentile is 0.55.  The duration pool is fifty 2s and fifty 60s, so its 50th
    percentile is 31.  The marginal pair is therefore (0.55, 31) - and NOTHING in
    the pool realizes it: within 31 bars the fast rows reach 0.20 and the slow
    rows reach 0.10, so the reachable share at that pair is exactly 0.

    JOINT.  Every row returns, so the cancel window is the same 31 bars.  The
    rows that returned INSIDE it are the fifty fast ones, whose within-window
    depth is 0.20 apiece, so the depth is 0.20.  The joint pair (0.20, 31) is
    realized by exactly those fifty rows: a reachable share of 0.50.
    """

    fast, slow = 50, 50
    durations = [2.0] * fast + [60.0] * slow
    depth_pool = [0.20] * fast + [0.90] * slow
    profiles = np.zeros((fast + slow, MAX_EPISODE_BARS), np.float64)
    profiles[:fast, :1] = -0.40                 # before the return at bar 2
    profiles[:fast, 1:] = 0.20
    profiles[slow:, :] = 0.0
    profiles[fast:, :30] = 0.10                 # still shallow at bar 31
    profiles[fast:, 30:59] = 0.10
    profiles[fast:, 59:] = 0.90                 # the deep return at bar 60
    marginal = marginal_pair(depth_pool, durations)
    joint = joint_pair(durations, profiles, depth_pool, durations)
    reach_marginal = reachable_share(marginal[0], marginal[1], durations,
                                     profiles)
    reach_joint = reachable_share(float(joint["depth_frac"]),
                                  int(joint["cancel_bars"]), durations, profiles)
    out = [_check(
        "the marginal law names the hand-computed pair (0.55 deep, 31 bars)",
        abs(marginal[0] - 0.55) < 1e-12 and marginal[1] == 31,
        f"depth {marginal[0]}, cancel {marginal[1]}")]
    out.append(_check(
        "the marginal pair is UNREACHABLE: no training pullback in the pool "
        "reaches that depth inside that window",
        reach_marginal == 0.0, f"reachable share {reach_marginal}"))
    out.append(_check(
        "the joint law names the hand-computed reachable pair (0.20 deep, "
        "31 bars)",
        abs(float(joint["depth_frac"]) - 0.20) < 1e-12
        and int(joint["cancel_bars"]) == 31 and joint["fallback"] is None,
        f"depth {joint['depth_frac']}, cancel {joint['cancel_bars']}, fallback "
        f"{joint['fallback']}"))
    out.append(_check(
        "the joint pair IS reachable, by exactly the fifty rows that returned "
        "inside the window",
        reach_joint is not None and abs(reach_joint - 0.50) < 1e-12
        and int(joint["reachable"]) == fast,
        f"reachable share {reach_joint}, reachable rows {joint['reachable']}"))
    # The two registered fallbacks, each on its own constructed pool.
    none_return = joint_pair([float(MAX_EPISODE_BARS)] * 10,
                             np.zeros((10, MAX_EPISODE_BARS), np.float64),
                             [-0.5] * 10, [float(MAX_EPISODE_BARS)] * 10)
    out.append(_check(
        "a pool where NO pullback returned falls back to the marginal pair, and "
        "says so",
        none_return["fallback"] == "no training pullback returned"
        and int(none_return["reachable"]) == 0,
        f"{none_return['fallback']}"))
    # The parity check: the marginal helper is sweep 23's own lane_params.
    parent = S23.lane_params([0.5], depth_pool, durations, 5)
    out.append(_check(
        "the marginal helper reproduces sweep 23's own lane_params exactly",
        abs(parent.depth_frac - marginal[0]) < 1e-12
        and parent.cancel_bars == marginal[1],
        f"parent ({parent.depth_frac}, {parent.cancel_bars}) vs here "
        f"({marginal[0]}, {marginal[1]})"))
    # The profile must agree with sweep 23's own pool statistic at the full
    # window, or lane C is not lane B's law with a different estimator.
    pieces = S23._plant_pieces()
    mid = np.asarray(pieces["mid"], np.float64)
    counters = S23._empty_counters()
    planted = S23.form_candidates(pieces["cell"], pieces["lcell"],
                                  pieces["sidecar"], 0, None, counters)
    agree = True
    for cand in planted:
        profile = back_profile(mid, int(cand.bar), float(cand.broken_edge),
                               float(cand.width), int(cand.break_dir))
        if abs(float(np.clip(profile[-1], *DEPTH_STAT_CLIP))
               - float(cand.pull_frac)) > 1e-9:
            agree = False
    out.append(_check(
        "the running-max profile equals sweep 23's own depth statistic at the "
        "full window, on every planted candidate",
        agree and bool(planted), f"{len(planted)} planted candidates"))
    return out


def _selftest_lane_a() -> list[tuple[str, bool, str]]:
    """Lane A: the break-direction entry at the NEXT bar, never a same close."""

    pieces = S23._plant_pieces()
    rec = pieces["rec"]
    world = pieces["world"]
    lat = np.asarray(rec.lat, np.int64)
    counters = S23._empty_counters()
    cands = S23.form_candidates(pieces["cell"], pieces["lcell"],
                                pieces["sidecar"], 0, None, counters)
    held = next(c for c in cands
                if round(c.zone_price) == round(world["held_zone"])
                and c.break_dir == 1)
    index = S23._plant_index(rec)
    price_counters = {f"nb_{suffix}": 0 for suffix in
                      ("out_of_range", "illegal", "unpriceable", "priced")}
    priced = S22.price_bar_entry(index, rec, LANE_A, 0, held, rec.asset,
                                 int(rec.d8), rec.phase, 0, int(held.bar) + 1,
                                 int(held.break_dir), price_counters, "nb")
    out = [_check("lane A prices an entry at the bar AFTER the breach close",
                  priced is not None and int(priced.bar) == int(held.bar) + 1,
                  f"{price_counters}")]
    if priced is None:
        return out + [_check("lane A never fills at the breach close itself",
                             False, "no priced entry")]
    out.append(_check(
        "lane A NEVER fills at the breach close itself: the entry stamp is "
        "strictly after it",
        int(priced.entry_ts_ns) > int(lat[int(held.bar)]),
        f"entry {priced.entry_ts_ns} vs breach close {int(lat[int(held.bar)])} "
        f"(gap {int(priced.entry_ts_ns) - int(lat[int(held.bar)])} ns)"))
    out.append(_check(
        "lane A enters in the BREAK direction",
        int(priced.side) == int(held.break_dir),
        f"side {priced.side} vs break {held.break_dir}"))
    out.append(_check(
        "lane A's entry price is the NEXT bar's mid, under the frozen entry law",
        int(priced.entry_mid2) == int(np.asarray(rec.mid,
                                                 np.int64)[int(held.bar) + 1]),
        f"entry mid2 {priced.entry_mid2}"))
    return out


def _selftest_selector_parity(mutant: str) -> list[tuple[str, bool, str]]:
    """This unit's fold law is sweep 23's: same matrix in, same rows out."""

    cands, payoff, impulse, days = S23._planted_selector()
    parent_raw = np.vstack([S23.barrier_components(cand) for cand in cands])
    mine, _report = score_selector(cands, parent_raw, impulse, days, mutant)
    theirs, _parent = S23.score_selector(cands, impulse, days, mutant)
    same = (len(mine) == len(theirs)
            and all(a.position == b.position
                    and abs(a.b - b.b) < 1e-12
                    and a.has_impulse == b.has_impulse
                    and a.selected == b.selected
                    for a, b in zip(mine, theirs)))
    out = [_check(
        "the selector reproduces sweep 23's fold law exactly on the same "
        "barrier matrix",
        same, f"{len(mine)} rows here vs {len(theirs)} in the parent")]
    picked = [r.position for r in mine if r.selected[LIVE_CELL]]
    recovered = float(np.mean([payoff[p] for p in picked])) if picked else 0.0
    base = float(np.mean(payoff))
    out.append(_check(
        "the selector recovers the planted defended-and-fast rows",
        len(picked) > 0 and recovered > base + 200.0,
        f"{len(picked)} picked, mean {recovered:.1f} vs base {base:.1f}"))
    strong = [p for p in picked
              if cands[p].lev_read[LV.LEVEL_INDEX["sd_held"]] > 0]
    out.append(_check("every selected row is a high-barrier row",
                      bool(picked) and len(strong) == len(picked),
                      f"{len(strong)}/{len(picked)} strong"))
    fast = [p for p in picked if impulse[p] > 0]
    out.append(_check(
        "every selected row is a high-impulse row (the I gate is load bearing)",
        bool(picked) and len(fast) == len(picked),
        f"{len(fast)}/{len(picked)} fast"))
    blind = np.array(impulse, copy=True)
    blind[::7] = np.nan
    rows_b, _report_b = score_selector(cands, parent_raw, blind, days, mutant)
    unscored = {r.position for r in rows_b if not r.has_impulse}
    picked_b = {r.position for r in rows_b if r.selected[LIVE_CELL]}
    out.append(_check(
        "a candidate with no finite I_break is NEVER selected, by registration",
        bool(unscored) and not (unscored & picked_b),
        f"{len(unscored)} unscored, {len(unscored & picked_b)} of them selected"))
    return out


def _selftest_leak(mutant: str) -> list[tuple[str, bool, str]]:
    """The leak guard: a world where only the scoring day carries the signal."""

    cands, payoff, impulse, days = S23._planted_leak()
    raw = np.vstack([S23.barrier_components(cand) for cand in cands])
    rows, _report = score_selector(cands, raw, impulse, days, mutant)
    picked = [r.position for r in rows if r.selected[LIVE_CELL]]
    day_rows = [p for p, c in enumerate(cands) if c.d8 == max(days["SI"])]
    base = float(np.mean([payoff[p] for p in day_rows]))
    recovered = float(np.mean([payoff[p] for p in picked])) if picked else base
    return [_check(
        "the leak-only world yields NO causal recovery",
        recovered <= base + 60.0,
        f"{len(picked)} of {len(day_rows)} day rows picked, mean "
        f"{recovered:.1f} vs day base {base:.1f}")]


def _receipt(usd: float, mdd: float, p: float, ceiling: float, delta: float,
             upper: float | None = None) -> dict[str, object]:
    cash = {asset: {"usd_per_day": usd, "mean_minus_2se_usd": usd - 10.0,
                    "clears_rung": usd - 10.0 >= DAY_RUNG_USD[asset]}
            for asset in ASSETS}
    cash["_portfolio"] = {"cap_lawful": True}
    stress = {kind: {"mdd": {"clears": mdd < MDD_CEILING}}
              for kind in ("adversarial", "spread")}
    return {
        "live": {lane: {
            "cash": cash,
            "mdd": {"clears": mdd < MDD_CEILING, "max_binding_usd": mdd},
            "stress": stress, "neighbours_agree": True} for lane in LANES},
        "ceiling": {"FORMED_UNIVERSE": {"cash": {
            asset: {"carries_rung": ceiling >= DAY_RUNG_USD[asset]}
            for asset in ASSETS}}},
        "control": {"by_line": {
            f"{lane}|{asset}": {
                "p_max_adjusted": p, "delta_usd_per_date": delta,
                "upper95_simultaneous_usd": (delta + 50.0 if upper is None
                                             else upper)}
            for lane in LANES for asset in ASSETS}}}


def _selftest_letters() -> list[tuple[str, bool, str]]:
    """Every clause fires on a constructed receipt, and the partition holds."""

    lane = LANES[0]
    cases = [
        ("LIVE", LETTER_LIVE, _receipt(3000.0, 100.0, 0.01, 5000.0, 300.0)),
        ("K1", LETTER_KILL, _receipt(100.0, 100.0, 0.01, 10.0, 300.0)),
        ("K2", LETTER_KILL,
         _receipt(100.0, 100.0, 0.20, 5000.0, -300.0, upper=-10.0)),
        ("K3", LETTER_KILL,
         _receipt(100.0, 100.0, 0.20, 5000.0, -300.0, upper=400.0)),
        ("UNRESOLVED", LETTER_UNRESOLVED,
         _receipt(100.0, 100.0, 0.20, 5000.0, 300.0)),
    ]
    out: list[tuple[str, bool, str]] = []
    for clause, letter, receipt in cases:
        got = lane_letter(lane, receipt)
        out.append(_check(
            f"the constructed {clause} receipt fires {clause}",
            got["clause"] == clause and got["letter"] == letter,
            f"got {got['letter']} / {got['clause']}"))
    out.append(_check(
        "a breached MDD cannot be LIVE",
        lane_letter(lane, _receipt(3000.0, 5000.0, 0.01, 5000.0, 300.0)
                    )["letter"] != LETTER_LIVE))
    # Every lane sees the same partition, and the family letter obeys its own
    # precedence over the lanes.
    live_receipt = _receipt(3000.0, 100.0, 0.01, 5000.0, 300.0)
    per_lane = {lane: lane_letter(lane, live_receipt) for lane in LANES}
    out.append(_check(
        "every registered lane carries a letter from the same partition",
        all(per_lane[lane]["letter"] == LETTER_LIVE for lane in LANES)
        and len(per_lane) == 3, f"{ {k: v['letter'] for k, v in per_lane.items()} }"))
    seen: dict[str, int] = {}
    total = 0
    agrees = True
    for bits in itertools.product((False, True), repeat=9):
        letter, clause, matching = classify(*bits)
        parent_letter, parent_clause, _m = S23.classify(*bits)
        if (parent_letter, parent_clause) != (letter, clause):
            agrees = False
        total += 1
        if clause not in CLAUSE_ORDER or CLAUSE_LETTER[clause] != letter:
            out.append(_check("the letter partition covers every outcome", False,
                              f"bad mapping at {bits}"))
            return out
        if not matching or clause != next(c for c in CLAUSE_ORDER
                                          if c in matching):
            out.append(_check("the letter partition covers every outcome", False,
                              f"precedence violated at {bits}"))
            return out
        seen[clause] = seen.get(clause, 0) + 1
    out.append(_check(
        "every one of the 512 outcome points maps to exactly one letter and "
        "clause, with no fallthrough",
        total == 512 and sum(seen.values()) == 512, f"{seen}"))
    out.append(_check("all five registered clauses are reachable",
                      set(seen) == set(CLAUSE_ORDER), f"{sorted(seen)}"))
    out.append(_check(
        "the partition agrees with sweep 23's own classifier at all 512 points",
        agrees))
    return out


def selftest() -> int:
    mutant = arm_mutant(_mutant())
    results: list[tuple[str, bool, str]] = []
    results += _selftest_planted()
    results += _selftest_center_gate_real()
    results += _selftest_joint_pair()
    results += _selftest_lane_a()
    results += _selftest_letters()
    results += _selftest_selector_parity(mutant)
    results += _selftest_leak(mutant)
    # Sweep 23's own fixture law, reused unchanged: breach formation, the
    # raw-tick pullback fill under both labels, the fake break priced as a loss,
    # and sweep 22's occupancy, cap, MDD and stress fixtures underneath them.
    results += S23._selftest_formation()
    results += S23._selftest_fill()
    results += S23._selftest_reclaim()
    results += S22._selftest_replay()
    results += S22._selftest_stress()
    print(f"sweep 25 selftest  mutant={mutant or 'none'}")
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
        print(f"  MUTANT {mutant}: {len(red)} check(s) red, "
              f"{len(wanted)} registered as required")
        for name in red:
            print(f"    red: {name}")
        if survived:
            print("  THE GUARD IS NOT LOAD BEARING: a registered check survived")
            for name in survived:
                print(f"    survived: {name}")
            return 1
        print("  the guard is load bearing: every registered check went red")
        return 0
    return 1 if bad else 0


# --------------------------------------------------------------------------
# The log and the entry point.
# --------------------------------------------------------------------------

def log_rows(report: Mapping[str, object]) -> list[dict[str, object]]:
    params = json.dumps({
        "lanes": list(LANES), "labels": list(LABELS),
        "read": "zone-anchored via levels_zone.read_zone at zone_price, side "
                "-break_dir, stamp lat[breach_bar-1]",
        "q_zone": S23.Q_ZONE, "q_depth": Q_DEPTH, "q_cancel": Q_CANCEL,
        "depth_clip": list(DEPTH_CLIP), "cancel_clip": list(CANCEL_CLIP),
        "max_episode_bars": MAX_EPISODE_BARS,
        "barrier_cuts": BARRIER_CUTS, "impulse_cuts": IMPULSE_CUTS,
        "live_cell": list(LIVE_CELL), "impulse_horizon_s": IMPULSE_HORIZON_S,
        "min_prior_days": MIN_PRIOR_DAYS, "portfolio_cap": PORTFOLIO_CAP,
        "sign_draws": SIGN_DRAWS, "control_draws": CONTROL_DRAWS,
        "clauses": list(CLAUSE_ORDER),
        "lane_c_joint": "one 2-D quantile over the reachable region",
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

    # 1. the registered live cell, per lane x label x asset
    for lane in LANES:
        block = report["live"][lane]
        for label in LABELS:
            for asset in ASSETS:
                counter += 1
                line = blank(dict(shared))
                cell = block["per_asset"][asset][label]
                cash = block["cash"][asset]
                zone = report["zone_read"]
                line["id"] = f"{LOG_PREFIX}-{counter:03d}"
                line["rule"] = f"{lane}/{label}/{asset}"
                line["days"] = cell["days"]
                line["coverage"] = cell["coverage"]
                tag = asset.lower()
                line[f"{tag}_usd_day"] = cell["usd_per_asset_day"]
                line[f"mdd_{tag}"] = cell["mdd_day_usd"]
                line[f"walls_{tag}"] = cell["wall_rate"]
                line["replay_skips"] = (block["replay"]["rejected_occupancy"]
                                        + block["replay"]["rejected_cap"])
                line["null_margin"] = report["block_nulls"].get(
                    f"{lane}|{asset}", {}).get("p")
                line["note"] = (
                    f"ZONE-ANCHORED {lane} ({LANE_NAME[lane]}), label {label}, "
                    f"{asset}: n {cell['n']} of {cell['formed']} formed, "
                    f"coverage {_show(cell['coverage'])}, mean "
                    f"{_show(cell['mean_cert_usd'])} median "
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
                    f"{block['neighbours_agree']}; B_opp read at the fixed zone "
                    f"price on the former defending side, "
                    f"{zone['center_exact']}/{zone['rows']} centres exact, "
                    f"worst gap {zone['worst_center_gap_mid2']} mid2; letter "
                    f"{report['letters'][lane]['letter']}")
                rows.append(line)

    # 2. the selector sensitivity grid
    for lane in LANES:
        for cut in GRID:
            counter += 1
            cell = report["grid"][lane][f"{cut[0]}|{cut[1]}"]
            line = blank(dict(shared))
            line["id"] = f"{LOG_PREFIX}-{counter:03d}"
            line["rule"] = f"{lane}/grid/{cut[0]}-{cut[1]}"
            line["days"] = len(report["scoring_days"]["NKD"])
            for asset in ASSETS:
                line[f"{asset.lower()}_usd_day"] = cell["cash"][asset][
                    "usd_per_day"]
            line["note"] = (
                f"selector sensitivity (zone-anchored), {lane}, barrier cut "
                f"{cut[0]} x impulse cut {cut[1]}: n {cell['n']}; " + "; ".join(
                    f"{asset} {_show(cell['cash'][asset]['usd_per_day'])} "
                    f"usd/day, -2SE "
                    f"{_show(cell['cash'][asset]['mean_minus_2se_usd'])}"
                    for asset in ASSETS)
                + ("; REGISTERED LIVE CELL" if tuple(cut) == LIVE_CELL
                   else "; neighbour"))
            rows.append(line)

    # 3. C1, the matched control
    for name, cell in sorted(report["control"]["by_line"].items()):
        counter += 1
        lane, asset = name.split("|")
        line = blank(dict(shared))
        line["id"] = f"{LOG_PREFIX}-{counter:03d}"
        line["rule"] = f"{lane}/control/{asset}"
        line["days"] = cell["dates"]
        line[f"{asset.lower()}_usd_day"] = cell["delta_usd_per_date"]
        line["null_margin"] = cell["p_max_adjusted"]
        line["note"] = (
            f"C1 paired matched control (zone-anchored selection), {lane}, "
            f"{asset}: selected minus control "
            f"{_show(cell['delta_usd_per_date'])} usd per asset-day over "
            f"{cell['dates']} dates, SE {_show(cell['se_usd'])}, t "
            f"{_show(cell['t'])}, shared-date-sign max-stat p "
            f"{_show(cell['p_max_adjusted'])} over "
            f"{len(report['control']['family'])} lines (3 lanes x 2 deciding "
            f"assets), simultaneous 95% "
            f"[{_show(cell['lower95_simultaneous_usd'])}, "
            f"{_show(cell['upper95_simultaneous_usd'])}]"
            f"{'' if cell['eligible'] else '; HG report-only'}")
        rows.append(line)

    # 4. C2, the formed ceiling
    for scope in list(LANES) + ["FORMED_UNIVERSE", "FORMED_CAPPED"]:
        counter += 1
        cash = report["ceiling"][scope]["cash"]
        bits = report["ceiling"][scope]["hindsight_bits"]
        line = blank(dict(shared))
        line["id"] = f"{LOG_PREFIX}-{counter:03d}"
        line["rule"] = f"{scope}/ceiling"
        line["days"] = len(report["scoring_days"]["NKD"])
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

    # 5. the fill picture and the registered lane-C deviation
    fills = report["fill_counters"]
    deviation = report["lane_c_deviation"]
    for lane in LANES:
        counter += 1
        line = blank(dict(shared))
        line["id"] = f"{LOG_PREFIX}-{counter:03d}"
        line["rule"] = f"{lane}/entry-mechanics"
        line["days"] = len(report["scoring_days"]["NKD"])
        if lane == LANE_A:
            same = report["same_close_check"]
            line["note"] = (
                f"ENTRY MECHANICS {lane}: bar entries priced "
                f"{report['pricing_counters']['nb_priced']}, illegal "
                f"{report['pricing_counters']['nb_illegal']}, out of range "
                f"{report['pricing_counters']['nb_out_of_range']}; same-close "
                f"prohibition checked {same['checked']} rows, violations "
                f"{same['violations']}, worst (breach close - entry) "
                f"{_show(same['worst_gap_ns'])} ns; frozen cert-plane cross-check "
                f"compared {report['plane_checks']['compared']}, mismatched "
                f"{report['plane_checks']['mismatched']}")
        else:
            cell = fills[lane]
            armed = max(int(cell["pb_armed"]), 1)
            line["note"] = (
                f"ENTRY MECHANICS {lane}: armed {cell['pb_armed']}, filled "
                f"{cell['pb_filled']} (rate {cell['pb_filled'] / armed:.4f}), "
                f"cancelled unfilled {cell['pb_no_fill']}, no tick window "
                f"{cell['pb_no_window']}, unpriceable "
                f"{cell['pb_unpriceable']}"
                + ("; MARGINAL depth and cancel, Sol's registered law"
                   if lane == LANE_B else
                   f"; JOINT depth and cancel, REGISTERED PARENT DEVIATION: "
                   f"{deviation['law']}; pair counters "
                   f"{deviation['counters']}"))
        rows.append(line)

    # 6. the letters
    for lane in LANES:
        counter += 1
        cell = report["letters"][lane]
        line = blank(dict(shared))
        line["id"] = f"{LOG_PREFIX}-{counter:03d}"
        line["rule"] = f"{lane}/letter"
        line["days"] = len(report["scoring_days"]["NKD"])
        for asset in DECIDING:
            line[f"{asset.lower()}_usd_day"] = report["live"][lane]["cash"][
                asset]["usd_per_day"]
        line["note"] = (
            f"LETTER {cell['letter']} for {lane}: rung {cell['rung_ok']}, MDD "
            f"{cell['mdd_ok']}, cap {cell['cap_ok']}, stress "
            f"{cell['stress_ok']}, control {cell['control_ok']}, neighbours "
            f"{cell['neighbours_ok']}, ceiling carries both rungs "
            f"{cell['ceiling_carries_both_rungs']}, upper bound non-positive "
            f"{cell['upper_bound_nonpositive']}, matched delta positive "
            f"{cell['matched_delta_positive']}; CLAUSE {cell['clause']} = "
            f"{cell['clause_text']}; clauses matching "
            f"{cell['clauses_matching']}"
            + ("; " + "; ".join(cell["reasons"]) if cell["reasons"] else ""))
        rows.append(line)

    counter += 1
    line = blank(dict(shared))
    line["id"] = f"{LOG_PREFIX}-{counter:03d}"
    line["rule"] = f"{FAMILY}/family"
    line["days"] = len(report["scoring_days"]["NKD"])
    head = report["headline"]
    line["note"] = (
        f"FAMILY LETTER {report['family_letter']} (clause "
        f"{report['family_clause']}), ZONE-ANCHORED read: best lane "
        f"{head['best_lane']} at " + ", ".join(
            f"{asset} {_show(head['best_lane_over_rung'].get(asset))}x rung"
            for asset in DECIDING)
        + "; formed ceiling beside it " + ", ".join(
            f"{asset} {_show(head['formed_ceiling_over_rung'].get(asset))}x rung"
            for asset in DECIDING)
        + "; capped ceiling " + ", ".join(
            f"{asset} {_show(head['capped_ceiling_over_rung'].get(asset))}x rung"
            for asset in DECIDING)
        + f"; every barrier read centred on the candidate zone "
          f"({report['zone_read']['center_exact']} of "
          f"{report['zone_read']['rows']} rows exact, worst gap "
          f"{report['zone_read']['worst_center_gap_mid2']} mid2) on the FORMER "
          f"DEFENDING SIDE at the last completed bar before the breach close; "
          f"3 registered lanes x 2 deciding assets in one maxT family; lane C "
          f"is a REGISTERED PARENT DEVIATION; EXPLORE-only, kill-only, no "
          f"promotion")
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
    print_deviation(report)
    print_causality_rows(report)
    print_formation(report)
    for lane in LANES:
        print_lane(report, lane)
    print_grid(report)
    print_controls(report)
    print_decision(report)
    print(f"\nSELECTOR SIGN NOTE (sweep 23's, carried verbatim)\n"
          f"  {report['selector_sign_note']}")
    print(f"\nCONTAMINATION NOTE (this unit)\n  {report['contamination_note']}")
    write_report(report)
    print(f"\nreport: {OUT_PATH}")
    if args.log:
        rows = log_rows(report)
        written = S1.append_log(rows)
        print(f"log: appended {written} rows to {LOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
