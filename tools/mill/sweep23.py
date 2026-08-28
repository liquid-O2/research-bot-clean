#!/usr/bin/env python3
"""Sweep 23 of the side-resolution mill: F20-STRUCTBREAK-PULLBACK.

Sol's pre-named successor to the killed F19-LEVELCOLLISION
(``.audit/briefs/mill-pinpoint-sol-out.md`` section D, "Lawful successor"):
"Form one candidate only after a one-minute close causally breaches a prior
persistent level, then arm the first pullback from the other side.  It uses the
same level cache and magnitude plane but asks a porous level to CONFIRM
CONTINUATION instead of asking it to hold."

The turn is the whole point.  Every dead family in this program asked the same
question at a level - will it hold? - and the pinpoint page says the coarse
plane cannot answer it because it observes the impulse and never the barrier.
F19 supplied the barrier term and still could not reach the money: its formed
universe carried 46.8x and 55.0x of the deciding rungs while its causal
selector reached 0.056x and 0.032x.  F20 keeps F19's entire measurement
apparatus and changes only the QUESTION.  It waits until the hold-or-break
question has been ANSWERED by a one-minute close through the level, and only
then takes a position - in the direction the answer went.  What was an
unobservable forecast becomes an observation, and the level is asked to confirm
continuation rather than to defend.

THE RULE, registered before anything is read.
  1. A candidate exists only after a one-minute CLOSE causally breaches an
     eligible PERSISTENT zone.  The zone set is sweep 22's: the true prior day's
     high, low and close; the cached prior-EXPLORE value edges, labelled
     prior-EXPLORE and never "yesterday"; and same-day zones with strictly
     earlier RESOLVED history.  Persistence adds a gate F19 did not have:
     nonzero defence history AT the zone.  A price nothing ever defended is not
     a structure and its break traps nobody.
  2. After the breach, arm the FIRST PULLBACK: price returns toward the broken
     zone from the break side.  Entry is in the BREAK direction via a resting
     limit at a fold-trained depth inside the broken edge, cancelled after a
     fold-trained duration, with RAW TICKS deciding the fill under sweep 22's
     own fill law.  One candidate per (asset, day, phase, level, break
     direction).
  3. Selector, PARENT-PREREGISTERED and parent-fixed: trade iff B >= the train
     top-tercile cut AND I >= the train median cut.  B is sweep 22's barrier
     score at the zone - a persistent level that breaks means something, and the
     trapped cohort is proportional to the defence that failed.  I is the frozen
     out-of-fold magnitude score - impulse present in the break.  Both enter
     POSITIVELY, which is the exact inversion of F19's fade selector, where the
     impulse entered only through the negative margin B - I.  The builder was
     told to flag the sign if it disagreed and to run it as written either way;
     see ``SELECTOR_SIGN_NOTE`` below, which agrees.

LAW OF INPUTS.  Unchanged from sweep 22.  Features stay on the causal one-minute
plane: the level cache (``levels.py``), the frozen out-of-fold magnitude channel
refit under sweep 20's own ridge law, and the completed pre-breach window.  Raw
tick suffixes PRICE crossings, limit fills and outcomes exactly as the frozen
mill already prices the -900 wall; no subminute value ever becomes an input.
The mutant ``QRE2_MILL_S23_MUTANT=selector_uses_test_day`` computes the
selector's B and I cuts including the scoring day and must turn the planted
recovery red.

THREE CONSTRUCTIONS RECORDED HERE because they are not recoverable from the
column names, each one forced by a fact about the cache rather than chosen.

  (a) WHERE THE BARRIER IS READ.  The level cache's plane at bar k describes the
      band centred on ``mid[k]`` - the price where the market IS at bar k
      (``build_levels.py``: ``band_center_mid2 = mid``).  At the breach bar price
      is by definition already beyond the far edge of the zone, so reading the
      plane there would score the band around the POST-BREAK price, not the
      zone.  The barrier is therefore read at the READ BAR: the last completed
      bar strictly before the breach at which price closed INSIDE the zone band.
      That bar's plane row is centred within one half-width of the zone, so it
      is the zone's own defence history, and it is strictly earlier than the
      breach, hence strictly earlier than the arm and the fill.  A breach whose
      zone the day never closed inside forms NO candidate: price that jumps a
      whole band in one minute has not traversed a structure.
  (b) WHICH SIDE IS READ.  ``levels.outcome_bars`` signs its verdicts: side +1
      fades a low (defenders must lift price to P + w before it prints below
      P - w); side -1 is the mirror.  The side that was DEFENDING against our
      break is therefore ``-break_dir``: an up-break is the failure of the -1
      side.  B is read there.  This is the same law sweep 22 used when it read
      the fade side, evaluated at the direction now being tested.
  (c) THE pd PAIR.  Verbatim from sweep 22, including its own recorded
      deviation: the cache carries only two defence pairs (same-day and
      prior-EXPLORE-session) because the mill's licence binds HOLD intraday
      paths as unread, which is why the cache's prior session is the prior
      EXPLORE session three locked days back.  The third pair is built here at
      DAY scale: ``pd_held`` = 1 when the zone is a prior-day extreme or a
      prior-EXPLORE value edge (a completed session reversed there);
      ``pd_broke`` = 1 when the current day's own strictly-prior path had
      already traded beyond the zone on the break side before the read bar.

Machinery is IMPORTED FROM SWEEP 22, never re-implemented: its zone catalogue,
levels join, impulse ridge, fill law, bar-entry law, replay, MDD ledgers,
stresses, matched control, maxT, block nulls, measurement and printing helpers
are called directly.  Sweep 22 is not modified.  Sweep 8 supplies the cells and
ATR14_prev, sweep 9 the row plane whose counters are the refuse-to-run gate,
sweep 12 the day states, sweep 14 the occurrence stream and fold law, sweep 19
the frozen to-close cert plane, sweep 20 the magnitude ridge law, sweep 1 the
cost law, the replay ledgers and the log.

Nothing here is executable.  EXPLORE only, kill-only tier, no packs, no HOLD, no
teacher labels, no 2021, no 2025H2, no commits.
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
import sweep1 as S1  # noqa: E402
import sweep8 as S8  # noqa: E402
import sweep9_twins as S9  # noqa: E402
import sweep12 as S12  # noqa: E402
import sweep14 as S14  # noqa: E402
import sweep19 as S19  # noqa: E402
import sweep20 as S20  # noqa: E402
import sweep22 as S22  # noqa: E402

# --------------------------------------------------------------------------
# The law, registered before anything is read.
# --------------------------------------------------------------------------

SPEC = """QRE2MILLSWEEP23
tier=exploratory; EXPLORE-only, kill-only.  Family F20-STRUCTBREAK, Sol's
  pre-named successor to the killed F19-LEVELCOLLISION.  Seed 20260827.  Parent
  trial sweep22-033.  NO COMMITS, NO FREEZE, no packs, no HOLD, no teacher
  labels, no 2021, no 2025H2.  ONE letter-carrying line; the no-pullback timing
  variant is REPORT-ONLY and outside the letter family.
GATE.  Sweep 9's row plane (47402 rows; certifiable HG 138 / NKD 132 / SI 132;
  candidates_seen 313131; cells_with_rows 385) and sweep 14's scoring days
  (41/40/39) reproduce before anything is formed.  The level cache manifest must
  carry schema QRE2MILLLEVELSMANIFEST1 against this split with strictly-prior
  join evidence, and this unit's own levels audit must report max(level source
  stamp - breach close stamp) strictly negative.  A miss on either refuses the
  run.  The report-only line's close-label certs are cross-checked against
  S19.build_cert_plane at the same (cell, side, bar); a disagreement refuses.
ZONES.  Sweep 22's catalogue, imported unchanged: (a) the TRUE prior day's high,
  low and close from the context store's day-level OHLC carried per cell in the
  level cache sidecar; (b) the cached prior-EXPLORE-session value edges,
  labelled prior-EXPLORE and never "yesterday"; (c) same-day price zones
  registered at the first bar whose cache row shows at least one RESOLVED prior
  touch (sd_held + sd_broke >= 1), deduplicated by one zone width, capped at 8
  per cell in birth order and eligible only at bars STRICTLY AFTER birth.
ZONE WIDTH.  Sweep 22's, unchanged and for its reason: fold-trained on train
  days only per asset x phase, the Q_ZONE = 75th percentile of
  (cell mid range / atr_mid2) / 10 over strictly prior EXPLORE days, SNAPPED to
  the nearest of the cache's own band multipliers (0.10, 0.20, 0.40).  The
  defence memory read at the zone is measured by the cache AT THAT WIDTH, so an
  unsnapped width would score a barrier with a band it was never counted in.
PERSISTENCE.  A zone is eligible for a breach only if it carries NONZERO defence
  history at the read bar: max over sides of (sd_held + sd_broke), plus max over
  sides of (ps_held + ps_broke), plus pd_held, strictly greater than zero.  A
  price nothing ever defended is not a structure and its break traps nobody.
  Rejections are counted and reported.
BREACH.  Region per bar is +1 beyond the upper edge, -1 beyond the lower edge, 0
  inside the band.  A BREACH fires at bar t when region(t) is nonzero and
  region(t-1) differs - a one-minute CLOSE that carries price from inside the
  zone (or from the far side) to beyond an edge.  The READ BAR is the last bar
  strictly before t at which region was 0; a breach with no such bar forms no
  candidate.  ONE candidate per (asset, day, phase, level, break direction): a
  second breach of the same zone in the same direction is deduplicated.
FOLD-TRAINED PARAMETERS.  Two parameter-free statistics are computed for every
  formed candidate at formation time over the next MAX_EPISODE_BARS = 90 bars:
  PULLBACK DEPTH, max over the window of break_dir * (broken edge - mid) in FULL
  widths (0 at the broken edge, 0.5 at the zone centre, 1.0 at the far edge,
  negative when price never returns), and PULLBACK DURATION, bars until price
  first returns to the broken edge.  For a scoring day each parameter is a fixed
  quantile of that stratum's STRICTLY PRIOR EXPLORE days: limit depth
  Q_DEPTH = 50th of the depth pool, clipped [0.05, 0.95] of the zone's full
  width; cancel duration Q_CANCEL = 50th of the duration pool, clipped [3, 90]
  bars.  Both clips are registered testability floors, not fits: a limit that
  rests at the broken edge is not a pullback and a limit that lives one minute
  is not a resting-limit lane.  Because the statistics are parameter-free,
  formation on day d depends only on days strictly before d.
ENTRY, THE PULLBACK.  A resting limit in the BREAK direction at
  broken_edge - break_dir * depth * 2w, armed at the first raw tick STRICTLY
  AFTER the breach bar's close stamp and cancelled at the fold-trained bar.  RAW
  TICKS decide the fill via the same monotone first-passage structure the frozen
  mill uses for the -900 wall: a long limit rests below and fills on the first
  raw mid at or through it, a short limit rests above.  A long boundary floors
  and a short ceils, so a fill is never manufactured by rounding.  Entry price
  IS the limit price on fill; entry stamp is the filling tick's; cost is the
  frozen cost at the last trusted quote STRICTLY BEFORE that stamp.
REPORT-ONLY LINE, outside the letter family.  The NO-PULLBACK variant: entry at
  the bar AFTER the breach close, in the break direction, under the frozen entry
  law - the USER's box-exit timing.  Same selector, same cuts, same labels, same
  replay, same ledgers, same stresses, its own matched control carried as an
  INELIGIBLE maxT line.  It informs the timing question and carries no letter.
SELECTOR, preregistered by the parent and NOT re-derived here.  Barrier score
  B = the mean of three train-fold-standardized defence differences read at the
  READ BAR on the DEFENDING side (-break_dir): (sd_held - sd_broke),
  (pd_held - pd_broke), (ps_held - ps_broke), the sd and ps pairs the cache's
  own and the pd pair built at day scale as recorded in the module docstring.
  Impulse score I = the frozen out-of-fold magnitude prediction: sweep 20's
  ridge law refit identically (coarse post-reset universe, the 16 causal
  sweep-14 features, cell-balanced weights, lambda 1.0, >= 25 strictly prior
  EXPLORE days, >= 50 fit rows, target the no-wall ABSMOVE at h = 1800 s),
  applied out of fold to the feature vector of the LAST G1 occurrence in the
  candidate's own cell strictly before its BREACH bar.  B and I are each
  standardized on the training fold per asset x phase.  TRADE IFF B >= the train
  TOP-TERCILE cut AND I >= the train MEDIAN cut.  Two interpretive registrations,
  fixed before the run: the I cut is the percentile of the FINITE training I
  only (substituting zeros for unscored rows would distort the quantile of the
  very quantity being cut on), and a candidate with NO finite impulse score is
  NOT selected, because a conjunction cannot be satisfied by a term that does
  not exist.  Unscored counts are reported.
NEIGHBOUR SENSITIVITY, required.  The line is recomputed on the
  (quartile, tercile) x (median, p60) grid - barrier cut at the 75th and
  66.667th percentiles crossed with the impulse cut at the 50th and 60th.  The
  registered LIVE cell is (tercile, median).  A LIVE letter requires the three
  neighbours not to flip the sign on either deciding asset.
PRICING.  Identical to sweep 22.  The frozen outcome law - the -900 wall or the
  phase close, whichever comes first - is PRIMARY and carries the letters.  The
  1800 s fixed hold is reported BESIDE every line as the drift-stripping
  sensitivity, priced by the same law with the phase close replaced by
  min(entry + 1800 s, phase close).
REPLAY.  Sweep 22's, imported: exact chronological replay with the frozen tie
  break (stamp, asset, cell, bar, side); EXITS BEFORE ENTRIES at an equal stamp;
  seat only when the asset is flat; hold to the registered exit; at most 12
  seated entries per PORTFOLIO date taken dynamically; every split date carried
  including zero-entry dates.
MDD.  Sweep 22's four ledgers plus event-time portfolio equity, imported: per
  asset trade and day, portfolio trade and day, and event-time equity that
  charges cost at entry and marks every open position at the causal raw mid
  until exit.  Binding is the deciding assets' own ledgers plus every portfolio
  ledger; the ceiling is 1000 USD.
STRESSES.  Sweep 22's two, imported: the 2 percent adversarial stress (the worst
  2 percent of seated entries per asset realize their own MAE) and the
  doubled-spread stress (the spread component of the frozen cost charged a
  second time).  Both re-run the replay so occupancy follows.
CONTROLS.  C1: per selected event a paired control drawn from the G1 occurrence
  universe, matched on asset, day, phase, breach-time bin (6 equal bins of the
  phase) and magnitude bin (train terciles of I), nearest in I with a frozen tie
  break, priced under the frozen outcome law at its own bar and side; its level
  memory and location vector is PERMUTED within the training fold and the share
  of permuted controls that would have been selected is reported.  Selected
  minus control by asset-day, studentized, shared-date-sign maxT over the family
  = 1 LANE x 2 DECIDING ASSETS, 10000 draws; HG and the report-only line are
  carried as ineligible lines.  C2: the formed-opportunity ceiling - the best
  lawfully priced event inside each formed opportunity over both sides and every
  legal bar of the window - with its hindsight bits named, RAW over every formed
  opportunity and CAPPED at the 12 best events per portfolio date so one ceiling
  line is comparable to a rung.  The KILL test reads the RAW formed ceiling.
  C3: block-permutation nulls on every headline, 2000 draws, re-drawing the same
  selected COUNT uniformly inside each (asset, phase, day) block of formed
  candidates.
LETTERS.  F19's letters with the partition FIXED - sweep 22's receipt had to
  record a FALLTHROUGH because the parent's three letters did not cover the
  space.  Precedence is registered: the FIRST matching clause in this order is
  the reported clause, and every other matching clause is listed beside it.
  STRUCTBREAK-LIVE: NKD and SI each above 1500 USD per asset-day at the point
    estimate AND at mean minus two asset-day-block standard errors, every
    binding MDD below 1000, cap and occupancy lawful, both stresses clearing,
    matched-control maxT p <= 0.05 on BOTH deciders, and neighbours not flipping.
  STRUCTBREAK-KILL clause K1: the formed ceiling misses either deciding rung.
  STRUCTBREAK-KILL clause K2: a powered deciding asset has a non-positive 95
    percent upper bound against its matched control.
  STRUCTBREAK-KILL clause K3, CEILING-UNREACHED: the formed ceiling carries both
    rungs and no deciding upper bound is non-positive, but the causal matched
    delta is NOT positive on both deciding assets, so UNRESOLVED cannot be
    earned.  This is the case sweep 22 had to call a fallthrough.
  STRUCTBREAK-UNRESOLVED: the formed ceiling carries both rungs AND the causal
    matched delta is positive on both deciding assets, but power or one live
    bound fails.
  The five clauses partition every possible receipt.  The selftest asserts it
  over the complete truth table and over five constructed receipts.
MUTANT.  QRE2_MILL_S23_MUTANT=selector_uses_test_day computes the selector's B
  and I standardizations and cuts INCLUDING the scoring day, and fits the
  impulse ridge including it.  It must flip the planted recovery red.
"""

SELECTOR_SIGN_NOTE = (
    "The parent's sign is RIGHT and the builder ran it as written.  F19 faded a "
    "level, so its selector wanted a strong barrier and PENALIZED impulse "
    "through the margin B - I: a big incoming move is bad news for a fade.  F20 "
    "trades the break, so both terms turn positive and for different reasons.  "
    "High B is the trapped-cohort term: only a level that was repeatedly "
    "DEFENDED can strand a cohort when it finally fails, and the size of that "
    "cohort is proportional to the defence that failed - a shelf nobody held is "
    "a break that traps nobody.  High I is the fuel term: sweep 15's one durable "
    "out-of-fold fact is that the plane predicts SIZE and never direction, and "
    "a break supplies the direction the plane cannot, so the magnitude channel "
    "is finally being asked a question it can answer.  The one live risk in the "
    "sign is contamination rather than direction: if the cache counted the "
    "present break in sd_broke at the read bar, high-B events would be exactly "
    "the ones scored down.  It cannot.  The cache resolves an outcome only from "
    "the bar its verdict lands on and only when that bar is strictly before the "
    "reading bar, the manifest certifies max(source - stamp) < 0, and the read "
    "bar is itself strictly before the breach.  The component means are printed "
    "beside the barrier table so a reader can check this rather than trust it.")

ASSETS = S1.ASSETS
DECIDING = ("NKD", "SI")
REPORT_ONLY_ASSETS = ("HG",)
SEED = 20260827

FAMILY = "F20-STRUCTBREAK"
PARENT_TRIAL = "sweep22-033"
SELECTION_RULE = ("none: parent-preregistered break-pullback formation, one "
                  "monotone selector fixed by the parent, fold-trained "
                  "thresholds, no model search")

LOG_PREFIX = "sweep23"
OUT_PATH = ROOT / ".audit/mill-sweep23.json"
LOG_PATH = S1.LOG_PATH

# Inherited, aliased so an upstream drift fails loudly here.
NFEAT = S14.NFEAT
MIN_PRIOR_DAYS = S22.MIN_PRIOR_DAYS           # 25
DAY_RUNG_USD = S1.DAY_RUNG_USD                # HG 2000, NKD 1500, SI 1500
MDD_CEILING = S1.MDD_CAP_USD                  # 1000
NANOS = S22.NANOS

CLOSE = S22.CLOSE
FIXED = S22.FIXED
LABELS = S22.LABELS
FIXHOLD_S = S22.FIXHOLD_S

LANE = "PULLBACK"
REPORT_LANE = "NOPULLBACK"
LINES = (LANE, REPORT_LANE)
LINE_NAME = {
    LANE: "first pullback to the broken zone, break-direction resting limit",
    REPORT_LANE: "no pullback: next bar after the breach close (report-only)"}
LETTER_LINES = (LANE,)

# Sweep 22's zone geometry, imported by value so a drift there fails loudly.
Q_ZONE = S22.Q_ZONE
ZONE_RANGE_DIVISOR = S22.ZONE_RANGE_DIVISOR
MAX_SAME_DAY_ZONES = S22.MAX_SAME_DAY_ZONES
MIN_SD_RESOLVED = S22.MIN_SD_RESOLVED
PD_HELD_KINDS = S22.PD_HELD_KINDS
MAX_EPISODE_BARS = S22.MAX_EPISODE_BARS
MIN_TRAIN_CANDS = S22.MIN_TRAIN_CANDS
PORTFOLIO_CAP = S22.PORTFOLIO_CAP
TIME_BINS = S22.TIME_BINS
CONTROL_DRAWS = S22.CONTROL_DRAWS
SIGN_DRAWS = S22.SIGN_DRAWS
IMPULSE_HORIZON_S = S22.IMPULSE_HORIZON_S

# This unit's own constants, every one named and fixed before the run.
Q_DEPTH = 50.0               # pullback limit depth, of the depth pool
DEPTH_CLIP = (0.05, 0.95)
Q_CANCEL = 50.0              # cancel duration, of the pullback-duration pool
CANCEL_CLIP = (3, 90)
DEPTH_STAT_CLIP = (-2.0, 2.0)

BARRIER_CUTS = S22.BARRIER_CUTS               # tercile 66.667, quartile 75
IMPULSE_CUTS = {"median": 50.0, "p60": 60.0}
LIVE_CELL = ("tercile", "median")
GRID = [(b, m) for b in ("quartile", "tercile") for m in ("median", "p60")]

HINDSIGHT_CEILING = ("which bar inside the formed window", "which side")

MUTANT_ENV = "QRE2_MILL_S23_MUTANT"
MUTANT_TESTDAY = "selector_uses_test_day"
MUTANTS = (MUTANT_TESTDAY,)

LETTER_LIVE = "STRUCTBREAK-LIVE"
LETTER_UNRESOLVED = "STRUCTBREAK-UNRESOLVED"
LETTER_KILL = "STRUCTBREAK-KILL"
CLAUSES = {
    "LIVE": "registered: every live bound cleared",
    "K1": "registered K1: the formed ceiling misses a deciding rung",
    "K2": ("registered K2: a powered deciding asset has a non-positive 95% "
           "upper bound against its matched control"),
    "K3": ("registered K3 CEILING-UNREACHED: the formed ceiling carries both "
           "rungs and no deciding upper bound is non-positive, but the causal "
           "matched delta is not positive on both deciding assets"),
    "UNRESOLVED": ("registered: the formed ceiling carries both rungs and the "
                   "causal matched delta is positive on both deciding assets, "
                   "but power or one live bound fails"),
}
CLAUSE_ORDER = ("LIVE", "K1", "K2", "K3", "UNRESOLVED")
CLAUSE_LETTER = {"LIVE": LETTER_LIVE, "K1": LETTER_KILL, "K2": LETTER_KILL,
                 "K3": LETTER_KILL, "UNRESOLVED": LETTER_UNRESOLVED}

PLANT_ASSET = "HG"
PLANT_BASE_MID2 = 400_000_000_000
PLANT_USD_PER_ATR = 400.0


class SweepRefusal(RuntimeError):
    pass


SPEC_SHA = S1._sha_text(SPEC)


def code_sha() -> str:
    return S1._sha_file(Path(__file__).resolve())


def _mutant() -> str:
    name = os.environ.get(MUTANT_ENV, "")
    if name and name not in MUTANTS:
        raise SweepRefusal(f"unknown sweep 23 mutant: {name}")
    return name


_pct = S22._pct
_mean_se = S22._mean_se
_wilson = S22._wilson
_drawdown = S22._drawdown
_n = S22._n


def _nan0(value: float) -> float:
    value = float(value)
    return value if math.isfinite(value) else 0.0


# --------------------------------------------------------------------------
# Candidate formation: one per (zone, break direction), after a breaching close.
# --------------------------------------------------------------------------

@dataclass(slots=True)
class Cand:
    asset: str
    d8: int
    phase: str
    cell: int
    year: int
    zone_kind: str
    zone_price: float
    width: float               # zone HALF width in mid2
    atr_mid2: float
    break_dir: int             # +1 broke up, -1 broke down
    defence_side: int          # -break_dir, the side that was defending
    broken_edge: float
    bar: int                   # the BREACH bar, this line's decision bar
    read_bar: int              # last bar strictly before the breach inside the zone
    n_bars: int
    # parameter-free pool statistics, computed at formation
    pull_frac: float
    pull_dur: int
    ext_reach: float
    # the barrier read at the read bar, on the defending side
    lev_read: np.ndarray
    pd_held: float
    pd_broke: float
    defence_history: float
    # the pre-breach visit window, recorded and reported, NEVER gating
    visit_bars: int
    visit_touches: int
    visit_flow: float
    # filled once the day's fold-trained parameters are known
    limit_mid2: int = 0
    cancel_bar: int = 0
    bar_grid_reaches_limit: bool = False
    src_ts: int = 0            # the level cache's source stamp at the read bar
    # the impulse join
    imp_row: int = -1
    x: np.ndarray | None = None


def _pool_stats(mid: np.ndarray, bar: int, edge: float, width: float,
                break_dir: int) -> tuple[float, int, float]:
    """The two parameter-free pullback statistics, plus the extension reach.

    They are parameter-free ON PURPOSE.  The lane parameters are quantiles of
    these pools over strictly prior days, so if the statistics themselves
    depended on a parameter the fold recursion would not close.
    """

    stop = min(len(mid), bar + MAX_EPISODE_BARS)
    window = np.asarray(mid[bar + 1:stop], np.float64)
    if not len(window):
        return float(DEPTH_STAT_CLIP[0]), MAX_EPISODE_BARS, 0.0
    back = (float(break_dir) * (edge - window)) / (2.0 * width)
    depth = float(np.clip(np.max(back), *DEPTH_STAT_CLIP))
    returned = np.flatnonzero(back >= 0.0)
    duration = int(returned[0]) + 1 if len(returned) else MAX_EPISODE_BARS
    ahead = (float(break_dir) * (window - edge)) / width
    return depth, max(int(duration), 1), float(np.max(ahead))


def defence_history(lcell: LV.LevelCell, mult_index: int, bar: int,
                    pd_held: float) -> tuple[float, float, float]:
    """Nonzero defence history at the zone is what makes a zone PERSISTENT.

    Both cache sides are read and the maximum taken: a price defended against a
    low fade and a price defended against a high fade are the same price, so the
    union is the honest test of "this price has a resolved history".
    """

    same_day = 0.0
    prior_session = 0.0
    for side in LV.SIDES:
        row = lcell.matrix(side, mult_index)[bar]
        same_day = max(same_day, _nan0(row[LV.LEVEL_INDEX["sd_held"]])
                       + _nan0(row[LV.LEVEL_INDEX["sd_broke"]]))
        prior_session = max(prior_session, _nan0(row[LV.LEVEL_INDEX["ps_held"]])
                            + _nan0(row[LV.LEVEL_INDEX["ps_broke"]]))
    return same_day, prior_session, same_day + prior_session + float(pd_held)


def form_candidates(cell: S8.Cell8, lcell: LV.LevelCell,
                    sidecar_cell: Mapping[str, object], mult_index: int,
                    delta: np.ndarray | None, counters: dict[str, int]
                    ) -> list[Cand]:
    """One candidate per (zone, break direction), after a breaching close."""

    rec = cell.rec
    mid = np.asarray(rec.mid, np.float64)
    n = min(int(rec.n), int(lcell.bars))
    if n < 3 or not float(cell.atr_mid2) > 0.0:
        counters["cells_too_short"] += 1
        return []
    width = float(LV.BAND_MULTS[mult_index]) * float(cell.atr_mid2)
    if not width > 0.0:
        counters["cells_zero_width"] += 1
        return []
    # Sweep 22's catalogue, imported unchanged.
    zones, zone_counts = S22.zone_catalogue(sidecar_cell, lcell, mult_index,
                                            mid, width)
    for key, value in zone_counts.items():
        counters[f"zone_{key}"] = counters.get(f"zone_{key}", 0) + value
    running_high = np.maximum.accumulate(mid)
    running_low = np.minimum.accumulate(mid)
    out: list[Cand] = []
    for zone in zones:
        distance = mid[:n] - zone.price
        region = np.where(distance > width, 1,
                          np.where(distance < -width, -1, 0)).astype(np.int64)
        start = max(int(zone.born_bar) + 1, 1)
        last_inside = -1
        formed_dirs: set[int] = set()
        visits = 0
        for bar in range(start, n):
            if int(region[bar - 1]) == 0:
                last_inside = bar - 1
                visits += 1
            state = int(region[bar])
            if state == 0 or state == int(region[bar - 1]):
                continue
            counters["breach_closes"] += 1
            if state in formed_dirs:
                counters["breach_deduped"] += 1
                continue
            if last_inside < 0:
                # Price jumped a whole band in one minute; it never traversed
                # the structure, so there is no cohort to trap.
                counters["breach_no_zone_visit"] += 1
                continue
            read_bar = int(last_inside)
            pd_held = 1.0 if zone.kind in PD_HELD_KINDS else 0.0
            same_day, prior_session, history = defence_history(
                lcell, mult_index, read_bar, pd_held)
            if not history > 0.0:
                counters["breach_no_defence_history"] += 1
                continue
            break_dir = state
            defence_side = -break_dir
            plane = lcell.matrix(defence_side, mult_index)
            edge = float(zone.price) + float(break_dir) * width
            # pd_broke at the read bar: had the current day's own strictly-prior
            # path already traded beyond this zone on the BREAK side?
            if read_bar >= 1:
                far = (float(running_high[read_bar - 1]) > zone.price + width
                       if break_dir > 0 else
                       float(running_low[read_bar - 1]) < zone.price - width)
            else:
                far = False
            depth, duration, ahead = _pool_stats(mid, bar, edge, width, break_dir)
            flow = 0.0
            if delta is not None and len(delta) > bar:
                inside = np.flatnonzero(region[:bar] == 0)
                if len(inside):
                    flow = float(np.asarray(delta, np.float64)[inside].sum())
            out.append(Cand(
                asset=cell.asset, d8=int(cell.d8), phase=cell.phase,
                cell=int(cell.position), year=int(cell.d8) // 10000,
                zone_kind=zone.kind, zone_price=float(zone.price), width=width,
                atr_mid2=float(cell.atr_mid2), break_dir=int(break_dir),
                defence_side=int(defence_side), broken_edge=float(edge),
                bar=int(bar), read_bar=read_bar, n_bars=int(n),
                pull_frac=depth, pull_dur=duration, ext_reach=ahead,
                lev_read=np.asarray(plane[read_bar], np.float64),
                pd_held=pd_held, pd_broke=1.0 if far else 0.0,
                defence_history=float(history),
                visit_bars=int(visits),
                visit_touches=int(np.count_nonzero(region[:bar] == 0)),
                visit_flow=flow))
            counters["candidates"] += 1
            counters["breach_up" if break_dir > 0 else "breach_down"] += 1
            formed_dirs.add(state)
    return out


def resolve_pullback(cand: Cand, mid: np.ndarray, depth_frac: float,
                     cancel_bars: int) -> None:
    """The limit price and the cancel bar, once the day's parameters are known."""

    level = cand.broken_edge - float(cand.break_dir) * depth_frac * 2.0 * cand.width
    # The frozen wall's own floor/ceil convention: a long boundary floors, a
    # short boundary ceils, so a fill is never manufactured by rounding.
    cand.limit_mid2 = int(math.floor(level) if cand.break_dir > 0
                          else math.ceil(level))
    cand.cancel_bar = int(min(cand.n_bars - 1, cand.bar + int(cancel_bars)))
    stop = min(len(mid), cand.cancel_bar + 1)
    window = np.asarray(mid[cand.bar + 1:stop], np.float64)
    if len(window):
        reach = float(np.max(float(cand.break_dir) * (level - window)))
        cand.bar_grid_reaches_limit = bool(reach >= 0.0)


# --------------------------------------------------------------------------
# The fold-trained stratum parameters.
# --------------------------------------------------------------------------

@dataclass(slots=True)
class Params:
    mult_index: int
    width_atr: float
    depth_frac: float
    depth_raw: float
    cancel_bars: int
    cancel_raw: float
    train_days: int
    train_cands: int


def lane_params(range_pool: Sequence[float], depth_pool: Sequence[float],
                dur_pool: Sequence[float], train_days: int) -> Params:
    index = S22.zone_mult_index(range_pool)          # sweep 22's snapped width
    depth = _pct(depth_pool, Q_DEPTH)
    cancel = _pct(dur_pool, Q_CANCEL)
    return Params(
        mult_index=index, width_atr=float(LV.BAND_MULTS[index]),
        depth_frac=float(np.clip(depth if depth is not None else 0.5,
                                 *DEPTH_CLIP)),
        depth_raw=float(depth) if depth is not None else float("nan"),
        cancel_bars=int(np.clip(int(math.ceil(cancel if cancel is not None
                                              else 15.0)), *CANCEL_CLIP)),
        cancel_raw=float(cancel) if cancel is not None else float("nan"),
        train_days=int(train_days), train_cands=len(depth_pool))


# --------------------------------------------------------------------------
# The barrier score and the parent's monotone selector.
# --------------------------------------------------------------------------

def barrier_components(cand: Cand) -> np.ndarray:
    """The three defence differences, read at the zone on the defending side."""

    plane = cand.lev_read
    sd = (plane[LV.LEVEL_INDEX["sd_held"]] - plane[LV.LEVEL_INDEX["sd_broke"]])
    ps = (plane[LV.LEVEL_INDEX["ps_held"]] - plane[LV.LEVEL_INDEX["ps_broke"]])
    pd = float(cand.pd_held) - float(cand.pd_broke)
    return np.asarray([sd, pd, ps], np.float64)


@dataclass(slots=True)
class Scored:
    position: int
    b: float
    i: float
    has_impulse: bool
    selected: dict[tuple[str, str], bool]


def score_selector(cands: Sequence[Cand], impulse: np.ndarray,
                   explore_days: Mapping[str, Sequence[int]], mutant: str
                   ) -> tuple[list[Scored], dict[str, object]]:
    """B and I standardized on the training fold, then the parent's rule.

    Sweep 22's ``score_selector`` line for line, with the ONE preregistered
    change this family exists to test: the second condition is a cut on I
    itself, not on the negative margin B - I.  A break-continuation wants the
    impulse present; a fade wanted it absent.
    """

    raw = (np.vstack([barrier_components(cand) for cand in cands])
           if len(cands) else np.zeros((0, 3)))
    by_stratum: dict[tuple[str, str], dict[int, list[int]]] = {}
    for position, cand in enumerate(cands):
        by_stratum.setdefault((cand.asset, cand.phase), {}).setdefault(
            cand.d8, []).append(position)
    out: list[Scored] = []
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
            # Registered: the I cut is a percentile of the FINITE training I
            # only.  Substituting zeros for unscored rows would distort the
            # quantile of the very quantity being cut on.
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
                    # that does not exist, so an unscored row is never selected.
                    selected[key] = bool(got and b_score[local] >= b_cut
                                         and i_score[local] >= i_cut)
                out.append(Scored(position=int(position), b=float(b_score[local]),
                                  i=float(i_score[local]) if got else float("nan"),
                                  has_impulse=got, selected=selected))
                report["rows"] += 1
    return out, report


# --------------------------------------------------------------------------
# Pricing.  The pullback fill; the report-only bar entry is sweep 22's verbatim.
# --------------------------------------------------------------------------

def price_pullback(index: M.MillIndex, rec: S1.CellRec, cands: Sequence[Cand],
                   positions: Sequence[int], counters: dict[str, int],
                   audit: list[dict[str, object]] | None = None
                   ) -> list[S22.Priced]:
    """Raw ticks decide the fill; the limit price IS the entry price.

    Sweep 22's ``price_lane1`` with one strengthening: the arm search opens at
    the first tick STRICTLY AFTER the breach bar's close stamp, so the print
    that decided the breach can never be the print that fills the order.
    """

    out: list[S22.Priced] = []
    if not len(positions):
        return out
    lat = np.asarray(rec.lat, np.int64)
    close_ns = int(rec.phase_close_ts_ns)
    breaches = np.asarray([int(lat[cands[p].bar]) for p in positions], np.int64)
    ends = np.asarray([int(min(lat[cands[p].cancel_bar], close_ns))
                       for p in positions], np.int64)
    starts = np.searchsorted(index.ts, breaches.astype(np.uint64), side="right")
    stops = np.searchsorted(index.ts, ends.astype(np.uint64), side="right")
    stops = np.minimum(stops, len(index.ts))
    thresholds = np.asarray([cands[p].limit_mid2 for p in positions], np.int64)
    sides = np.asarray([cands[p].break_dir for p in positions], np.int64)
    rows = np.full(len(positions), -1, np.int64)
    for side in (1, -1):
        pick = np.flatnonzero((sides == side) & (starts < stops))
        if not len(pick):
            continue
        # A long limit rests BELOW the broken edge and fills on the first mid at
        # or through it; a short limit rests ABOVE.  Same monotone first-passage
        # structure the frozen mill uses for the -900 wall.
        rows[pick] = index.range.first_many(starts[pick], stops[pick],
                                            thresholds[pick],
                                            use_min=(side > 0))
    for local, position in enumerate(positions):
        cand = cands[position]
        counters["pb_armed"] += 1
        if starts[local] >= stops[local]:
            counters["pb_no_window"] += 1
            continue
        arm_ts = int(index.ts[int(starts[local])])
        row = int(rows[local])
        if row < 0:
            counters["pb_no_fill"] += 1
            continue
        stamp = int(index.ts[row])
        priced = S22._price_entry(index, cand.asset, stamp, cand.break_dir,
                                  int(cand.limit_mid2), close_ns)
        if priced is None:
            counters["pb_unpriceable"] += 1
            continue
        exit_bar = int(np.searchsorted(lat, int(priced[f"{CLOSE}|exit"]),
                                       side="right") - 1)
        out.append(S22.Priced(
            lane=LANE, position=int(position), asset=cand.asset, d8=cand.d8,
            phase=cand.phase, cell=cand.cell, bar=int(cand.bar),
            exit_bar=int(max(exit_bar, cand.bar)), side=int(cand.break_dir),
            entry_ts_ns=stamp, entry_mid2=int(cand.limit_mid2),
            cost_usd=float(priced["cost_usd"]),
            spread_usd=float(priced["spread_usd"]),
            cert={label: float(priced[f"{label}|cert"]) for label in LABELS},
            wall={label: bool(priced[f"{label}|wall"]) for label in LABELS},
            mae={label: float(priced[f"{label}|mae"]) for label in LABELS},
            mfe={label: float(priced[f"{label}|mfe"]) for label in LABELS},
            exit_ts={label: int(priced[f"{label}|exit"]) for label in LABELS}))
        counters["pb_filled"] += 1
        if audit is not None and len(audit) < 10:
            audit.append({
                "asset": cand.asset, "d8": int(cand.d8), "phase": cand.phase,
                "cell": int(cand.cell), "zone": cand.zone_kind,
                "dir": int(cand.break_dir), "read_bar": int(cand.read_bar),
                "breach_bar": int(cand.bar),
                "source_ts_ns": int(cand.src_ts),
                "breach_close_ts_ns": int(breaches[local]),
                "arm_ts_ns": arm_ts, "fill_ts_ns": stamp})
    return out


# --------------------------------------------------------------------------
# The letters.  Five clauses, a registered precedence, and a real partition.
# --------------------------------------------------------------------------

def classify(rung_ok: bool, mdd_ok: bool, cap_ok: bool, stress_ok: bool,
             control_ok: bool, neighbours_ok: bool, ceiling_carries: bool,
             upper_nonpositive: bool, matched_positive: bool
             ) -> tuple[str, str, list[str]]:
    """The registered partition.  Exactly one clause fires; the rest are listed.

    Sweep 22's receipt had to record a FALLTHROUGH because the parent's three
    letters left a hole: a ceiling that carries both rungs, no non-positive
    upper bound, and a matched delta that is negative on one decider matched
    neither UNRESOLVED nor either registered KILL clause.  That hole is now
    clause K3, CEILING-UNREACHED, and the chain below is exhaustive by
    construction: LIVE is the conjunction of every live bound, and its negation
    splits on ceiling_carries, then upper_nonpositive, then matched_positive,
    with UNRESOLVED taking the remainder.
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
    raise SweepRefusal("the letter partition failed to cover a receipt; this "
                       "is the enumeration gap the family exists to close")


def line_letter(report: Mapping[str, object]) -> dict[str, object]:
    live = report["live"][LANE]                      # type: ignore[index]
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
        reasons.append("an adjacent fold-trained threshold flips the sign")

    ceiling_carries = all(
        bool(ceiling["cash"][asset].get("carries_rung"))   # type: ignore[index]
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
    return {"lane": LANE, "letter": letter, "clause": clause,
            "clause_text": CLAUSES[clause],
            "clauses_matching": matching, "reasons": reasons,
            "rung_ok": rung_ok, "mdd_ok": mdd_ok, "cap_ok": cap_ok,
            "stress_ok": stress_ok, "control_ok": control_ok,
            "neighbours_ok": neighbours_ok,
            "ceiling_carries_both_rungs": ceiling_carries,
            "upper_bound_nonpositive": upper_nonpositive,
            "matched_delta_positive": matched_positive}


# --------------------------------------------------------------------------
# The run.  One formation pass over the lattice, then one shard pass.
# --------------------------------------------------------------------------

def formation_pass(cells: Sequence[S8.Cell8],
                   explore_days: Mapping[str, Sequence[int]], mutant: str
                   ) -> tuple[list[Cand], dict[str, object]]:
    """Every EXPLORE day, in order, with parameters from strictly prior days."""

    by_day: dict[tuple[str, int], list[S8.Cell8]] = {}
    for cell in cells:
        by_day.setdefault((cell.asset, int(cell.d8)), []).append(cell)
    counters = {"cells": 0, "cells_no_levels": 0, "cells_too_short": 0,
                "cells_zero_width": 0, "candidates": 0, "breach_closes": 0,
                "breach_deduped": 0, "breach_no_zone_visit": 0,
                "breach_no_defence_history": 0, "breach_up": 0,
                "breach_down": 0, "days_formed": 0, "days_warmup": 0,
                "levels_missing_cell": 0}
    range_pool: dict[tuple[str, str], dict[int, list[float]]] = {}
    stat_pool: dict[tuple[str, str], dict[int, list[tuple[float, int]]]] = {}
    params_used: dict[str, dict[str, object]] = {}
    read_gaps: list[int] = []
    worst_gap = -(1 << 62)
    out: list[Cand] = []
    deltas, flow_counters = S19.load_deltas(cells)

    for asset in ASSETS:
        days = sorted(int(day) for day in explore_days[asset])
        for index, d8 in enumerate(days):
            day_cells = by_day.get((asset, d8), [])
            if not day_cells:
                continue
            if index < 1:
                counters["days_warmup"] += 1
                continue
            prior = days[:index]
            try:
                sidecar = S22._sidecar(asset, d8)
                day_levels = LV.load_levels(asset, d8)
            except LV.LevelStop:
                counters["cells_no_levels"] += len(day_cells)
                continue
            cell_side = {(str(c["phase"]), int(c["phase_open_ts_ns"])): c
                         for c in sidecar.get("cells", [])}
            counters["days_formed"] += 1
            for cell in sorted(day_cells, key=lambda c: c.position):
                counters["cells"] += 1
                stratum = (asset, cell.phase)
                ranges = [v for day in prior
                          for v in range_pool.get(stratum, {}).get(day, [])]
                stats = [v for day in prior
                         for v in stat_pool.get(stratum, {}).get(day, [])]
                params = lane_params(ranges, [s[0] for s in stats],
                                     [s[1] for s in stats], len(prior))
                params_used.setdefault(f"{asset}|{cell.phase}", {})[str(d8)] = {
                    "mult_index": params.mult_index,
                    "width_atr": params.width_atr,
                    "depth_frac": params.depth_frac,
                    "depth_raw": params.depth_raw,
                    "cancel_bars": params.cancel_bars,
                    "cancel_raw": params.cancel_raw,
                    "train_days": params.train_days,
                    "train_cands": params.train_cands}
                key = (cell.phase, int(cell.rec.phase_open_ts_ns))
                lcell = day_levels.get(key)
                side_row = cell_side.get(key)
                mid = np.asarray(cell.rec.mid, np.float64)
                if float(cell.atr_mid2) > 0.0 and len(mid) > 1:
                    range_pool.setdefault(stratum, {}).setdefault(d8, []).append(
                        float((mid.max() - mid.min()) / cell.atr_mid2)
                        / ZONE_RANGE_DIVISOR)
                if lcell is None or side_row is None:
                    counters["levels_missing_cell"] += 1
                    continue
                fresh = form_candidates(cell, lcell, side_row,
                                        params.mult_index,
                                        deltas.get(int(cell.position)), counters)
                lat = np.asarray(cell.rec.lat, np.int64)
                src = np.asarray(lcell.src_ts_ns, np.int64)
                for cand in fresh:
                    stat_pool.setdefault(stratum, {}).setdefault(d8, []).append(
                        (cand.pull_frac, cand.pull_dur))
                    resolve_pullback(cand, mid, params.depth_frac,
                                     params.cancel_bars)
                    # The level read must be strictly prior to the breach close,
                    # which is itself strictly prior to the arm and the fill.
                    gap = int(src[cand.read_bar]) - int(lat[cand.bar])
                    worst_gap = max(worst_gap, gap)
                    read_gaps.append(int(cand.bar - cand.read_bar))
                    cand.src_ts = int(src[cand.read_bar])
                out.extend(fresh)
    return out, {
        "counters": counters, "flow_counters": flow_counters,
        "params": params_used,
        "max_src_minus_breach_ns": int(worst_gap),
        "strictly_prior": bool(worst_gap < 0),
        "read_gap_bars": {
            "mean": float(np.mean(read_gaps)) if read_gaps else None,
            "max": int(max(read_gaps)) if read_gaps else None,
            "is_previous_bar_share": (float(np.mean([g == 1 for g in read_gaps]))
                                      if read_gaps else None)}}


def pricing_pass(cands: Sequence[Cand], cells: Sequence[S8.Cell8],
                 streams: Sequence[S14.Stream], records: Sequence[S1.CellRec],
                 explore_days: Mapping[str, Sequence[int]], mutant: str
                 ) -> dict[str, object]:
    """One shard pass: the magnitude target, both lines, the G1 control pool."""

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
                "pb_armed": 0, "pb_filled": 0, "pb_no_fill": 0,
                "pb_no_window": 0, "pb_unpriceable": 0,
                "mag_rows": 0, "mag_dropped": 0, "g1_rows": 0}
    for tag in ("nb", "g1", "ceil"):
        for suffix in ("out_of_range", "illegal", "unpriceable", "priced"):
            counters[f"{tag}_{suffix}"] = 0
    mag: list[S22.MagRow] = []
    pullback: dict[int, S22.Priced] = {}
    nopullback: dict[int, S22.Priced] = {}
    g1_pool: dict[tuple[str, int, str], list[dict[str, object]]] = {}
    g1_priced: dict[int, S22.Priced] = {}
    ceiling: dict[int, dict[str, object]] = {}
    mid_by_cell: dict[int, np.ndarray] = {}
    lat_by_cell: dict[int, np.ndarray] = {}
    cert_plane = S19.build_cert_plane(cells)
    plane_checks = {"compared": 0, "mismatched": 0, "worst_abs_usd": 0.0}
    audit: list[dict[str, object]] = []

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

                # ---- the pullback line: raw ticks decide the fill ----------
                for entry in price_pullback(index, rec, cands, mine, counters,
                                            audit):
                    pullback[int(entry.position)] = entry

                # ---- the report-only no-pullback line ----------------------
                for local in mine:
                    cand = cands[local]
                    priced = S22.price_bar_entry(
                        index, rec, REPORT_LANE, local, cand, asset, int(d8),
                        rec.phase, position, int(cand.bar) + 1,
                        int(cand.break_dir), counters, "nb")
                    if priced is None:
                        continue
                    nopullback[local] = priced
                    reference = float(cert_plane.cert[
                        cert_plane.index[position],
                        0 if cand.break_dir > 0 else 1, int(cand.bar) + 1])
                    if math.isfinite(reference):
                        plane_checks["compared"] += 1
                        gap = abs(reference - float(priced.cert[CLOSE]))
                        plane_checks["worst_abs_usd"] = max(
                            plane_checks["worst_abs_usd"], gap)
                        if gap > 1e-6:
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
    return {"mag": mag, "pullback": pullback, "nopullback": nopullback,
            "g1_pool": g1_pool, "g1_priced": g1_priced, "ceiling": ceiling,
            "mid_by_cell": mid_by_cell, "lat_by_cell": lat_by_cell,
            "counters": counters, "coarse_counters": coarse_counters,
            "plane_checks": plane_checks, "causality_rows": audit}


def ceiling_cash(positions: Sequence[int], cands: Sequence[Cand],
                 best: Mapping[int, Mapping[str, object]],
                 explore_days: Mapping[str, Sequence[int]]) -> dict[str, object]:
    cash: dict[str, object] = {}
    for asset in ASSETS:
        day_list = sorted(int(d) for d in explore_days[asset])
        sums = {day: 0.0 for day in day_list}
        n = 0
        for position in positions:
            cand = cands[position]
            if cand.asset != asset:
                continue
            row = best.get(position)
            if row is None:
                continue
            sums[int(cand.d8)] = sums.get(int(cand.d8), 0.0) + float(row["usd"])
            n += 1
        series = [sums[day] for day in day_list]
        mean, se = _mean_se(series)
        cash[asset] = {
            "n": n, "usd_per_day": mean, "se_usd": se,
            "rung_usd": DAY_RUNG_USD[asset],
            "over_rung": None if mean is None else mean / DAY_RUNG_USD[asset],
            "carries_rung": None if mean is None else bool(
                mean >= DAY_RUNG_USD[asset])}
    return cash


def run() -> dict[str, object]:
    mutant = _mutant()
    started = time.time()
    cells, days, _skipped = S8.build_cells(ASSETS)
    records, _rec_days = S1.load_cache()
    records = [rec for rec in records if rec.asset in ASSETS]
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

    cands, formation = formation_pass(cells, explore_days, mutant)
    if not formation["strictly_prior"]:
        raise SweepRefusal(
            f"a level read is not strictly prior to its breach close: "
            f"max(source - breach) = {formation['max_src_minus_breach_ns']} ns")

    priced = pricing_pass(cands, cells, streams, records, explore_days, mutant)
    if priced["plane_checks"]["mismatched"]:
        raise SweepRefusal(
            "a no-pullback close-label cert disagreed with the frozen cert "
            f"plane at the same (cell, side, bar): worst "
            f"{priced['plane_checks']['worst_abs_usd']:.6f} USD")
    bad = [row for row in priced["causality_rows"]
           if not (int(row["source_ts_ns"]) < int(row["breach_close_ts_ns"])
                   < int(row["arm_ts_ns"]) <= int(row["fill_ts_ns"]))]
    if bad:
        raise SweepRefusal(f"a fill violates source < breach < arm <= fill: "
                           f"{bad[0]}")

    folds, impulse_report = S22.fit_impulse(priced["mag"], explore_days, mutant)
    # The impulse join: the last G1 occurrence in the candidate's own cell that
    # closed STRICTLY BEFORE the breach bar.  Its features are the frozen
    # 16-column plane; nothing is re-derived at an arbitrary bar.
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

    have = {LANE: priced["pullback"], REPORT_LANE: priced["nopullback"]}
    formed_by_asset = {asset: sum(1 for c in cands if c.asset == asset)
                       for asset in ASSETS}
    formed_opportunities: dict[str, int] = {}
    for cand in cands:
        key = f"{cand.asset}|{cand.d8}"
        formed_opportunities[key] = formed_opportunities.get(key, 0) + 1

    scores, score_report = score_selector(cands, impulse, explore_days, mutant)
    score_summary = {k: v for k, v in score_report.items() if k != "cuts"}
    score_summary["cut_sample"] = dict(list(score_report["cuts"].items())[:3])

    live: dict[str, object] = {}
    grid_report: dict[str, object] = {}
    selected_entries: dict[str, list[S22.Priced]] = {}
    selected_positions: dict[str, list[int]] = {}
    for line in LINES:
        pool = have[line]
        by_cell = grid_report.setdefault(line, {})
        for cut in GRID:
            picks = [row.position for row in scores
                     if row.selected.get(cut) and row.position in pool]
            entries = [pool[p] for p in picks]
            block = S22.evaluate_lane(line, entries, cands, explore_days,
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
                selected_entries[line] = entries
                selected_positions[line] = picks
                live[line] = block

    # Neighbour agreement: the three non-registered cells must not flip the
    # sign of the deciding assets' usd/day.
    for line in LINES:
        agree = True
        for asset in DECIDING:
            base = grid_report[line][
                f"{LIVE_CELL[0]}|{LIVE_CELL[1]}"]["cash"][asset]["usd_per_day"]
            for cut in GRID:
                if cut == LIVE_CELL:
                    continue
                other = grid_report[line][
                    f"{cut[0]}|{cut[1]}"]["cash"][asset]["usd_per_day"]
                if base is None or other is None:
                    agree = False
                elif (base > 0) != (other > 0):
                    agree = False
        live[line]["neighbours_agree"] = bool(agree)

    # ---- stresses and MDD on the registered cell --------------------------
    for line in LINES:
        entries = selected_entries[line]
        stress: dict[str, object] = {}
        for kind in ("adversarial", "spread"):
            overrides = S22.stress_overrides(entries, CLOSE, kind)
            seated = S22.replay(entries, CLOSE, overrides)
            stress[kind] = {
                "seated": seated["seated"],
                "cash": S22.replay_cash(seated["trades"], explore_days),
                "mdd": S22.mdd_ledgers(seated["trades"], priced["mid_by_cell"],
                                       priced["lat_by_cell"], explore_days)}
        live[line]["stress"] = stress
        live[line]["mdd"] = S22.mdd_ledgers(live[line]["trades"],
                                            priced["mid_by_cell"],
                                            priced["lat_by_cell"], explore_days)
        live[line].pop("trades", None)

    # ---- C2: the formed ceiling ------------------------------------------
    ceiling_block: dict[str, object] = {
        "SELECTED": {"cash": ceiling_cash(selected_positions[LANE], cands,
                                          priced["ceiling"], explore_days),
                     "hindsight_bits": list(HINDSIGHT_CEILING)},
        "FORMED_UNIVERSE": {"cash": ceiling_cash(range(len(cands)), cands,
                                                 priced["ceiling"],
                                                 explore_days),
                            "hindsight_bits": list(HINDSIGHT_CEILING)}}
    # The raw per-opportunity sum is dominated by how many opportunities the
    # rule forms, not by what a book could hold.  This second ceiling keeps only
    # the 12 best events per PORTFOLIO date - the cap law, with occupancy still
    # unenforced - so it stays a strict upper bound on any lawful seating while
    # being comparable to a rung.  It spends one more hindsight bit: which twelve.
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

    # ---- C1: matched, level-permuted controls -----------------------------
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
    for line in LINES:
        entries = selected_entries[line]
        mag_bin = {}
        for entry in entries:
            value = impulse[entry.position]
            mag_bin[entry.position] = int(
                np.searchsorted(edges, value)) if np.isfinite(value) else 0
        matched, counters = S22.match_controls(entries, cands,
                                               priced["g1_pool"], impulse,
                                               mag_bin)
        control_counters[line] = counters
        for asset in ASSETS:
            series: dict[int, float] = {}
            for position, entry in enumerate(entries):
                if entry.asset != asset or position not in matched:
                    continue
                control_row = matched[position]
                control_entry = priced["g1_priced"].get(int(control_row["row"]))
                if control_entry is None:
                    continue
                series[int(entry.d8)] = series.get(int(entry.d8), 0.0) + (
                    float(entry.cert[CLOSE]) - float(control_entry.cert[CLOSE]))
            control_lines[f"{line}|{asset}"] = series
        # The permutation diagnostic: give each matched control a level vector
        # drawn from a permutation inside the training fold and ask how often it
        # would have been selected.  A level-blind control should select at the
        # base rate, not at the selector's rate.
        if len(cands) and matched:
            draw = rng.permutation(len(cands))
            hits = 0
            for slot, _position in enumerate(sorted(matched)):
                donor = cands[int(draw[slot % len(draw)])]
                hits += int(float(np.nanmean(barrier_components(donor))) > 0.0)
            permuted_selected[line] = {
                "n": len(matched),
                "share_permuted_positive_barrier":
                    float(hits / max(len(matched), 1))}
    family = [f"{LANE}|{asset}" for asset in DECIDING]
    control = S22.maxt_inference(control_lines, family, SIGN_DRAWS)

    # ---- C3: block-permutation nulls on every headline --------------------
    eligible: dict[tuple[str, str, int], list[int]] = {}
    for position, cand in enumerate(cands):
        eligible.setdefault((cand.asset, cand.phase, cand.d8), []).append(position)
    nulls: dict[str, object] = {}
    for line in LINES:
        pool = have[line]
        cert_by_position = {p: float(pool[p].cert[CLOSE]) for p in pool}
        for asset in ASSETS:
            nulls[f"{line}|{asset}"] = S22.block_null(
                selected_positions[line], cands, eligible, cert_by_position,
                explore_days, asset, CONTROL_DRAWS)

    # ---- line extras: direction split, barrier decomposition, windows -----
    direction: dict[str, dict[int, int]] = {}
    window: dict[str, dict[str, float]] = {}
    for entry in selected_entries[LANE]:
        cand = cands[entry.position]
        table = direction.setdefault(cand.asset, {1: 0, -1: 0})
        table[int(cand.break_dir)] = table.get(int(cand.break_dir), 0) + 1
        row = window.setdefault(cand.asset, {
            "n": 0, "defence_history": 0.0, "pull_frac": 0.0, "pull_dur": 0.0,
            "ext_reach": 0.0, "visit_touches": 0.0, "visit_flow": 0.0,
            "sd_diff": 0.0, "pd_diff": 0.0, "ps_diff": 0.0})
        row["n"] += 1
        row["defence_history"] += cand.defence_history
        row["pull_frac"] += cand.pull_frac
        row["pull_dur"] += cand.pull_dur
        row["ext_reach"] += cand.ext_reach
        row["visit_touches"] += cand.visit_touches
        row["visit_flow"] += cand.visit_flow
        components = barrier_components(cand)
        row["sd_diff"] += _nan0(components[0])
        row["pd_diff"] += _nan0(components[1])
        row["ps_diff"] += _nan0(components[2])
    for row in window.values():
        n = max(row["n"], 1)
        for key in list(row):
            if key != "n":
                row[key] = float(row[key] / n)
        row["n"] = int(n)
    # The same decomposition over the WHOLE formed universe, so a reader can see
    # that the selected cohort really is the defended cohort.
    formed_components = {}
    for asset in ASSETS:
        mine = [barrier_components(c) for c in cands if c.asset == asset]
        if not mine:
            continue
        stack = np.vstack(mine)
        formed_components[asset] = {
            "n": int(len(mine)),
            "sd_diff": float(np.nanmean(stack[:, 0])),
            "pd_diff": float(np.nanmean(stack[:, 1])),
            "ps_diff": float(np.nanmean(stack[:, 2])),
            "defence_history": float(np.mean(
                [c.defence_history for c in cands if c.asset == asset])),
            "pd_broke_rate": float(np.mean(
                [c.pd_broke for c in cands if c.asset == asset]))}

    report: dict[str, object] = {
        "schema": "QRE2MILLSWEEP23", "spec_sha": SPEC_SHA,
        "code_sha": code_sha(), "split_sha": S1.split_sha(),
        "outcome_law_sha": S1.outcome_law_sha(), "seed": SEED,
        "mutant": mutant, "family": FAMILY, "parent_trial": PARENT_TRIAL,
        "selection_rule": SELECTION_RULE, "registered_utc": report_stamp(),
        "selector_sign_note": SELECTOR_SIGN_NOTE,
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
        "pricing_counters": priced["counters"],
        "coarse_counters": priced["coarse_counters"],
        "plane_checks": priced["plane_checks"],
        "causality_rows": priced["causality_rows"],
        "impulse": impulse_report, "impulse_join": join,
        "impulse_counters": impulse_counters,
        "selector": score_summary, "grid": grid_report, "live": live,
        "ceiling": ceiling_block, "control": control,
        "control_counters": control_counters,
        "control_permutation": permuted_selected,
        "block_nulls": nulls,
        "line_extras": {"direction": direction, "window": window,
                        "formed_components": formed_components},
        "scoring_days": {a: scoring[a] for a in ASSETS},
        "elapsed_s": round(time.time() - started, 1)}
    letter = line_letter(report)
    report["letters"] = {LANE: letter}
    report["family_letter"] = letter["letter"]
    report["headline"] = headline(report)
    return report


def headline(report: Mapping[str, object]) -> dict[str, object]:
    """The deciding usd/day over rung, with the formed ceiling ratios beside."""

    cash = report["live"][LANE]["cash"]                   # type: ignore[index]
    ratios = {}
    for asset in DECIDING:
        value = cash[asset]["usd_per_day"]
        ratios[asset] = None if value is None else value / DAY_RUNG_USD[asset]
    ceiling = report["ceiling"]["FORMED_UNIVERSE"]["cash"]  # type: ignore[index]
    capped = report["ceiling"]["FORMED_CAPPED"]["cash"]     # type: ignore[index]
    other = report["live"][REPORT_LANE]["cash"]            # type: ignore[index]
    return {
        "lane": LANE,
        "lane_over_rung": ratios,
        "report_only_over_rung": {
            asset: (None if other[asset]["usd_per_day"] is None
                    else other[asset]["usd_per_day"] / DAY_RUNG_USD[asset])
            for asset in DECIDING},
        "formed_ceiling_over_rung": {asset: ceiling[asset]["over_rung"]
                                     for asset in DECIDING},
        "formed_capped_over_rung": {asset: capped[asset]["over_rung"]
                                    for asset in DECIDING},
        "family_letter": report["family_letter"],
        "clause": report["letters"][LANE]["clause"]}


# --------------------------------------------------------------------------
# Printing.
# --------------------------------------------------------------------------

def print_summary(report: Mapping[str, object]) -> None:
    head = report["headline"]
    lane = ", ".join(f"{asset} {_n(head['lane_over_rung'].get(asset), 7, 4)}x"
                     for asset in DECIDING)
    ceiling = ", ".join(
        f"{asset} {_n(head['formed_ceiling_over_rung'].get(asset), 7, 3)}x"
        for asset in DECIDING)
    print(f"\nF20-STRUCTBREAK-PULLBACK  deciding usd/day over rung: {lane}"
          f"   |   formed ceiling: {ceiling}   |   {head['family_letter']}"
          f" ({head['clause']})")


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
    print(f"  THIS UNIT'S levels audit : strictly prior "
          f"{formation['strictly_prior']}, max(level source - breach close) "
          f"{formation['max_src_minus_breach_ns']} ns")
    print(f"  read bar behind breach   : {formation['read_gap_bars']}")
    print(f"  formation counters       : {formation['counters']}")
    print(f"  pricing counters         : {report['pricing_counters']}")
    checks = report["plane_checks"]
    print(f"  no-pullback vs frozen cert plane: compared {checks['compared']}, "
          f"mismatched {checks['mismatched']}, worst "
          f"{checks['worst_abs_usd']:.9f} USD")
    print(f"  impulse ridge            : {report['impulse']['counters']}, "
          f"WITHIN-DAY R2 (a harder denominator than sweep 20's pooled R2, "
          f"not a contradiction of it) "
          f"{report['impulse']['pooled_within_day_r2']}")
    print(f"  impulse join             : {report['impulse_join']}, "
          f"{report['impulse_counters']}")
    print(f"  selector                 : {report['selector']['strata']} strata, "
          f"{report['selector']['days_scored']} days scored, "
          f"{report['selector']['days_thin']} thin, "
          f"{report['selector']['rows']} rows, "
          f"{report['selector']['rows_no_impulse']} with no impulse score "
          f"(never selected, by registration)")


def print_causality_rows(report: Mapping[str, object]) -> None:
    rows = report["causality_rows"]
    print("\n== CAUSALITY, 10 REAL FILLED ROWS: source < breach close < arm "
          "<= fill ==")
    print("  asset      d8 ph zone            dir  read breach   "
          "source-minus-fill_ns   breach-minus-arm_ns")
    worst_src = None
    worst_arm = None
    for row in rows:
        src_gap = int(row["source_ts_ns"]) - int(row["fill_ts_ns"])
        arm_gap = int(row["breach_close_ts_ns"]) - int(row["arm_ts_ns"])
        worst_src = src_gap if worst_src is None else max(worst_src, src_gap)
        worst_arm = arm_gap if worst_arm is None else max(worst_arm, arm_gap)
        print(f"  {row['asset']:<5} {row['d8']} {row['phase']:>2} "
              f"{row['zone']:<15} {row['dir']:>3} {row['read_bar']:>5} "
              f"{row['breach_bar']:>6} {src_gap:>22d} {arm_gap:>21d}")
    print(f"  max source-minus-fill  : {worst_src} ns (must be strictly negative)")
    print(f"  max breach-minus-arm   : {worst_arm} ns (must be strictly negative)")


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
    print("\n  fold-trained parameters, sample strata:")
    for stratum, table in report["formation_params_sample"].items():
        for d8, block in list(table.items())[-1:]:
            print(f"    {stratum:<8} {d8}  band x{block['width_atr']:.2f} ATR "
                  f"(mult index {block['mult_index']})  limit depth "
                  f"{block['depth_frac']:.3f} of full width (raw quantile "
                  f"{block['depth_raw']:.3f})  cancel {block['cancel_bars']} "
                  f"bars (raw {block['cancel_raw']:.1f})  train "
                  f"{block['train_days']} days / {block['train_cands']} "
                  f"candidates")
    print("\n  barrier decomposition over the WHOLE formed universe "
          "(sd_held-sd_broke, pd, ps at the read bar, defending side):")
    print("  asset      n   sd_diff   pd_diff   ps_diff  defence_history  "
          "pd_broke_rate")
    for asset, row in sorted(report["line_extras"]["formed_components"].items()):
        print(f"  {asset:<5} {row['n']:>6} {_n(row['sd_diff'], 9, 3)} "
              f"{_n(row['pd_diff'], 9, 3)} {_n(row['ps_diff'], 9, 3)} "
              f"{_n(row['defence_history'], 16, 3)} "
              f"{_n(row['pd_broke_rate'], 14, 3)}")


def print_line(report: Mapping[str, object], line: str) -> None:
    tag = "" if line in LETTER_LINES else "   [REPORT-ONLY, outside the letter family]"
    print(f"\n== LINE {line}: {LINE_NAME[line]}{tag} ==")
    block = report["live"][line]
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


def print_line_extras(report: Mapping[str, object]) -> None:
    extras = report["line_extras"]
    counters = report["pricing_counters"]
    armed = int(counters["pb_armed"])
    print("\n== PULLBACK FILL AND CANCEL RATES ==")
    print(f"  armed {armed}, filled {counters['pb_filled']}, cancelled unfilled "
          f"{counters['pb_no_fill']}, no tick window {counters['pb_no_window']}, "
          f"unpriceable {counters['pb_unpriceable']}")
    if armed:
        print(f"  fill rate {counters['pb_filled'] / armed:.4f}   "
              f"cancel rate {counters['pb_no_fill'] / armed:.4f}")
    print(f"  no-pullback bar entries priced {counters['nb_priced']}, illegal "
          f"{counters['nb_illegal']}, out of range {counters['nb_out_of_range']}")
    print("\n== BREAK DIRECTION SPLIT OF THE SELECTED PULLBACK COHORT ==")
    for asset in ASSETS:
        block = extras["direction"].get(asset, {})
        total = sum(block.values()) or 1
        print(f"  {asset:<5} up {block.get(1, 0):>5} "
              f"({block.get(1, 0) / total:.3f})   down {block.get(-1, 0):>5} "
              f"({block.get(-1, 0) / total:.3f})")
    print("\n  selected-cohort features (recorded, NOT gating):")
    print("  asset   n  defence  sd_diff  pd_diff  ps_diff  pull_frac  "
          "pull_dur  ext_reach  visits    flow")
    for asset in ASSETS:
        row = extras["window"].get(asset)
        if not row:
            continue
        print(f"  {asset:<5} {row['n']:>4} {_n(row['defence_history'], 7, 2)} "
              f"{_n(row['sd_diff'], 8, 2)} {_n(row['pd_diff'], 8, 2)} "
              f"{_n(row['ps_diff'], 8, 2)} {_n(row['pull_frac'], 10, 3)} "
              f"{_n(row['pull_dur'], 9, 1)} {_n(row['ext_reach'], 10, 2)} "
              f"{_n(row['visit_touches'], 7, 1)} {_n(row['visit_flow'], 7, 0)}")


def print_grid(report: Mapping[str, object]) -> None:
    print("\n== SELECTOR SENSITIVITY GRID (barrier cut x impulse cut) ==")
    print("  the registered LIVE cell is (tercile, median); the other three "
          "are its neighbours")
    for line in LINES:
        print(f"  {line}{'' if line in LETTER_LINES else '  (report-only)'}")
        print("    barrier  impulse     n     NKD usd/day   NKD -2SE      "
              "SI usd/day    SI -2SE   registered")
        for cut in GRID:
            cell = report["grid"][line][f"{cut[0]}|{cut[1]}"]
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
          f"(1 lane x 2 deciding assets), c95 {_n(control['c95'], 7, 3)}")
    print("  line                     dates    delta/date       SE        t   "
          "max-p    upper95   lower95")
    for name, cell in sorted(control["by_line"].items()):
        print(f"  {name:<24} {cell['dates']:>5} "
              f"{_n(cell['delta_usd_per_date'], 12, 1)} "
              f"{_n(cell['se_usd'], 9, 1)} {_n(cell['t'], 8, 3)} "
              f"{_n(cell['p_max_adjusted'], 7, 4)} "
              f"{_n(cell['upper95_simultaneous_usd'], 10, 1)} "
              f"{_n(cell['lower95_simultaneous_usd'], 10, 1)}"
              f"{'' if cell['eligible'] else '   (report-only)'}")
    print(f"  match counters: {report['control_counters']}")
    print(f"  permuted-level diagnostic: {report['control_permutation']}")

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

    print("\n== C3: BLOCK-PERMUTATION NULLS ON EVERY HEADLINE ==")
    print(f"  {CONTROL_DRAWS} draws, same selected count re-drawn inside each "
          f"(asset, phase, day) block of formed candidates")
    print("  line                     observed usd/day   null mean    null p95"
          "      p")
    for name, cell in sorted(report["block_nulls"].items()):
        print(f"  {name:<24} {_n(cell['observed_usd_day'], 14, 1)} "
              f"{_n(cell.get('null_mean_usd_day'), 11, 1)} "
              f"{_n(cell.get('null_p95_usd_day'), 11, 1)} "
              f"{_n(cell.get('p'), 6, 4)}")


def print_decision(report: Mapping[str, object]) -> None:
    head = report["headline"]
    print("\n== DECISION TABLE ==")
    print("  " + ", ".join(
        f"{asset} lane {_n(head['lane_over_rung'].get(asset), 7, 4)}x rung, "
        f"report-only {_n(head['report_only_over_rung'].get(asset), 7, 4)}x, "
        f"ceiling {_n(head['formed_ceiling_over_rung'].get(asset), 7, 3)}x "
        f"(capped {_n(head['formed_capped_over_rung'].get(asset), 6, 3)}x)"
        for asset in DECIDING))
    print("  line            letter                    rung  MDD  cap  stress "
          " control  neighbours  ceiling  upper<=0  matched+")
    cell = report["letters"][LANE]
    print(f"  {LANE:<15} {cell['letter']:<25} {_n(cell['rung_ok'], 5)} "
          f"{_n(cell['mdd_ok'], 4)} {_n(cell['cap_ok'], 4)} "
          f"{_n(cell['stress_ok'], 6)} {_n(cell['control_ok'], 8)} "
          f"{_n(cell['neighbours_ok'], 11)} "
          f"{_n(cell['ceiling_carries_both_rungs'], 8)} "
          f"{_n(cell['upper_bound_nonpositive'], 9)} "
          f"{_n(cell['matched_delta_positive'], 9)}")
    print(f"      CLAUSE {cell['clause']}: {cell['clause_text']}")
    if len(cell["clauses_matching"]) > 1:
        print(f"      also matching (registered precedence "
              f"{' > '.join(CLAUSE_ORDER)}): "
              f"{', '.join(c for c in cell['clauses_matching'] if c != cell['clause'])}")
    for reason in cell["reasons"]:
        print(f"      - {reason}")
    print(f"  {REPORT_LANE:<15} no letter: report-only, outside the family")
    print(f"\n  FAMILY LETTER: {report['family_letter']}")


# --------------------------------------------------------------------------
# Selftest and the red mutant.
# --------------------------------------------------------------------------

_check = S22._check


def _plant_levels(mid: np.ndarray, atr: float, width: float,
                  specs: Sequence[tuple[float, float, float]]) -> LV.LevelCell:
    """A LevelCell whose defence columns are planted, everything else zero.

    ``specs`` is a list of ``(price, held, broke)``: at every bar whose mid is
    within ``width`` of ``price``, the same-day pair is planted.  A zone absent
    from ``specs`` therefore has NO defence history, which is exactly the case
    the persistence gate must refuse.  Adapted from sweep 22's ``_plant_levels``
    to carry more than two prices.
    """

    n = len(mid)
    planes: dict[tuple[int, int], np.ndarray] = {}
    for side in LV.SIDES:
        for index in range(len(LV.BAND_MULTS)):
            plane = np.zeros((n, LV.NLEV), np.float64)
            plane[:, LV.LEVEL_INDEX["band_mult"]] = LV.BAND_MULTS[index]
            plane[:, LV.LEVEL_INDEX["band_center_mid2"]] = mid
            plane[:, LV.LEVEL_INDEX["band_w_mid2"]] = LV.BAND_MULTS[index] * atr
            for bar in range(n):
                price = float(mid[bar])
                for centre, held, broke in specs:
                    if abs(price - centre) <= width:
                        plane[bar, LV.LEVEL_INDEX["sd_touches"]] = held + broke
                        plane[bar, LV.LEVEL_INDEX["sd_held"]] = held
                        plane[bar, LV.LEVEL_INDEX["sd_broke"]] = broke
            planes[(side, index)] = plane
    return LV.LevelCell(
        asset=PLANT_ASSET, d8=20220315, phase="0",
        phase_open_ts_ns=0, phase_close_ts_ns=0, bars=n, atr_mid2=float(atr),
        tick2=1.0, prior_d8=20220314, prev_sess_d8=20220311,
        value_lo=float("nan"), value_hi=float("nan"),
        src_ts_ns=np.arange(n, dtype=np.int64), planes=planes)


def _break_world() -> dict[str, object]:
    """The planted world: one clean break-pullback-continuation, one fake break
    that reclaims and must be priced as a LOSS, and one zone with NO defence
    history that must form no candidate.

    Every price below is arithmetic on USD offsets from a base mid2, so the
    hand-computed certs are exact.  ATR is 400 USD worth; at band multiplier
    0.10 the zone half-width is 40 USD and the full width is 80 USD.
    """

    unit = float(S22.S7A.usd_to_mid2(PLANT_ASSET))     # mid2 per USD
    atr = PLANT_USD_PER_ATR * unit
    width = 0.10 * atr                                  # 40 USD worth
    # offsets in USD from the base price
    offsets = [
        -240.0, -160.0, -60.0, -20.0, 20.0, 100.0, 72.0, 36.0, 16.0, 120.0,
        280.0, 460.0, 700.0, 990.0, 1120.0, 1400.0, 1700.0, 2000.0, 2250.0,
        2390.0, 2520.0, 2480.0, 2430.0, 2400.0, 2340.0, 2200.0, 2000.0,
        1850.0, 1750.0, 1700.0,
    ]
    offsets += [1690.0 - 2.5 * k for k in range(36)]     # bars 30..65
    path = np.asarray([PLANT_BASE_MID2 + off * unit for off in offsets],
                      np.float64)
    return {"unit": unit, "atr": atr, "width": width, "offsets": offsets,
            "path": path,
            "held_zone": float(PLANT_BASE_MID2),               # A, breaks up
            "fake_zone": float(PLANT_BASE_MID2 + 2400.0 * unit),  # B, reclaims
            "bare_zone": float(PLANT_BASE_MID2 + 1000.0 * unit)}  # C, no history


def _plant_pieces() -> dict[str, object]:
    world = _break_world()
    rec = S22._plant_rec(world["path"])
    cell = S22._PlantCell(rec, world["atr"])
    mid = np.asarray(rec.mid, np.float64)
    lcell = _plant_levels(mid, world["atr"], world["width"],
                          [(world["held_zone"], 4.0, 0.0),
                           (world["fake_zone"], 1.0, 3.0)])
    sidecar = {"pd_high": world["held_zone"], "pd_low": 0.0,
               "pd_close": world["bare_zone"], "value_hi": world["fake_zone"],
               "value_lo": 0.0}
    return {"world": world, "rec": rec, "cell": cell, "mid": mid,
            "lcell": lcell, "sidecar": sidecar}


def _empty_counters() -> dict[str, int]:
    return {"cells_too_short": 0, "cells_zero_width": 0, "candidates": 0,
            "breach_closes": 0, "breach_deduped": 0, "breach_no_zone_visit": 0,
            "breach_no_defence_history": 0, "breach_up": 0, "breach_down": 0}


def _selftest_formation() -> list[tuple[str, bool, str]]:
    pieces = _plant_pieces()
    world = pieces["world"]
    counters = _empty_counters()
    cands = form_candidates(pieces["cell"], pieces["lcell"], pieces["sidecar"],
                            0, None, counters)
    by_key = {(round(c.zone_price), c.break_dir): c for c in cands}
    out = [_check("the planted world forms exactly three candidates",
                  len(cands) == 3,
                  f"{len(cands)}: {sorted((round(c.zone_price - PLANT_BASE_MID2), c.break_dir) for c in cands)}")]
    out.append(_check(
        "the persistent zone forms an UP-break candidate",
        (round(world["held_zone"]), 1) in by_key,
        f"keys {sorted((k[0] - PLANT_BASE_MID2, k[1]) for k in by_key)}"))
    out.append(_check(
        "the fake-break zone forms an UP-break candidate",
        (round(world["fake_zone"]), 1) in by_key, ""))
    out.append(_check(
        "a zone with NO defence history forms NO candidate",
        all(round(c.zone_price) != round(world["bare_zone"]) for c in cands)
        and counters["breach_no_defence_history"] == 1,
        f"no-defence rejections {counters['breach_no_defence_history']}, "
        f"breaching closes {counters['breach_closes']}"))
    out.append(_check(
        "a second breach of the same zone in the same direction is deduped",
        counters["breach_deduped"] >= 1,
        f"deduped {counters['breach_deduped']}"))
    held = by_key[(round(world["held_zone"]), 1)]
    fake = by_key[(round(world["fake_zone"]), 1)]
    out.append(_check(
        "the breach bar is the first close beyond the edge",
        held.bar == 5 and fake.bar == 20,
        f"held breach bar {held.bar}, fake breach bar {fake.bar}"))
    out.append(_check(
        "the barrier is read at the last bar INSIDE the zone, strictly before "
        "the breach",
        held.read_bar == 4 and fake.read_bar == 19
        and held.read_bar < held.bar and fake.read_bar < fake.bar,
        f"read bars {held.read_bar} < {held.bar}, {fake.read_bar} < {fake.bar}"))
    inside = all(abs(float(pieces["mid"][c.read_bar]) - c.zone_price)
                 <= c.width for c in cands)
    out.append(_check("price at every read bar is inside the zone band", inside))
    out.append(_check(
        "the defending side is the side the break went through",
        all(c.defence_side == -c.break_dir for c in cands),
        f"{[(c.break_dir, c.defence_side) for c in cands]}"))
    b_held = float(np.nanmean(barrier_components(held)))
    b_fake = float(np.nanmean(barrier_components(fake)))
    out.append(_check(
        "the barrier ranks the strongly defended zone above the weakly "
        "defended one", b_held > b_fake,
        f"held {b_held:.3f} vs fake {b_fake:.3f}"))
    # the pullback geometry
    resolve_pullback(held, pieces["mid"], 0.30, 12)
    want = held.broken_edge - 0.30 * 2.0 * held.width
    out.append(_check("the limit rests inside the broken edge, in the pullback",
                      abs(held.limit_mid2 - math.floor(want)) < 1e-6
                      and held.limit_mid2 < held.broken_edge,
                      f"limit {held.limit_mid2}, edge {held.broken_edge:.0f}"))
    depth, duration, ahead = _pool_stats(pieces["mid"], held.bar,
                                         held.broken_edge, held.width, 1)
    out.append(_check(
        "the pullback depth statistic is the retracement in full widths",
        abs(depth - (40.0 - 16.0) / 80.0) < 1e-9,
        f"{depth:.6f} vs hand 0.30 ((40-16)/80 USD widths)"))
    out.append(_check(
        "the pullback duration is bars until price regains the broken edge",
        duration == 2, f"{duration} (bar 7 at +36 USD, two bars after 5)"))
    out.append(_check("the continuation extension is measured beyond the edge",
                      ahead > 0.0, f"{ahead:.2f} widths"))
    return out


def _plant_index(rec: S1.CellRec, spike: tuple[int, float] | None = None
                 ) -> M.MillIndex:
    """A tick tape over the planted bars, one tick just before each bar stamp.

    ``spike`` adds one INTRAMINUTE tick at ``lat[bar] - 1 + 10`` at the given
    USD offset - a print a minute-close reader would never see and a tick reader
    must.
    """

    lat = np.asarray(rec.lat, np.int64)
    mid = np.asarray(rec.mid, np.int64)
    unit = float(S22.S7A.usd_to_mid2(PLANT_ASSET))
    ts: list[int] = []
    values: list[int] = []
    for bar in range(len(lat)):
        ts.append(int(lat[bar]) - 1)
        values.append(int(mid[bar]))
        if spike is not None and bar == spike[0]:
            ts.append(int(lat[bar]) - 1 + 10)
            values.append(int(round(PLANT_BASE_MID2 + spike[1] * unit)))
    order = np.argsort(np.asarray(ts, np.int64), kind="stable")
    ts_array = np.asarray(ts, np.int64)[order]
    mid_array = np.asarray(values, np.int64)[order]
    bid = mid_array // 2 - 1
    ask = mid_array // 2 + 1
    generation = np.zeros(len(ts_array), np.uint32)
    return M.MillIndex(PLANT_ASSET, ts_array, mid_array, bid, ask, generation,
                       ts_array, generation)


def _selftest_fill() -> list[tuple[str, bool, str]]:
    """The planted pullback fill, hand-computed under BOTH labels."""

    pieces = _plant_pieces()
    rec = pieces["rec"]
    world = pieces["world"]
    lat = np.asarray(rec.lat, np.int64)
    counters = _empty_counters()
    cands = form_candidates(pieces["cell"], pieces["lcell"], pieces["sidecar"],
                            0, None, counters)
    held = next(c for c in cands
                if round(c.zone_price) == round(world["held_zone"])
                and c.break_dir == 1)
    resolve_pullback(held, pieces["mid"], 0.30, 12)
    # A dip to +10 USD inside bar 6 goes THROUGH the limit at +16 and comes back.
    index = _plant_index(rec, spike=(6, 10.0))
    counts = {"pb_armed": 0, "pb_filled": 0, "pb_no_fill": 0,
              "pb_no_window": 0, "pb_unpriceable": 0}
    audit: list[dict[str, object]] = []
    held.src_ts = int(lat[held.read_bar]) - 1
    filled = price_pullback(index, rec, [held], [0], counts, audit)
    hit = bool(filled)
    spike_ts = int(lat[6]) - 1 + 10
    stamp = int(filled[0].entry_ts_ns) if hit else -1
    out = [_check("the pullback limit fills on the intraminute tick, not the bar",
                  hit and stamp == spike_ts,
                  f"filled {hit}, stamp {stamp}, spike stamp {spike_ts}")]
    out.append(_check("the entry price IS the limit price on fill",
                      hit and int(filled[0].entry_mid2) == int(held.limit_mid2),
                      f"entry {filled[0].entry_mid2 if hit else None} vs limit "
                      f"{held.limit_mid2}"))
    out.append(_check("the entry side is the BREAK direction",
                      hit and int(filled[0].side) == 1,
                      f"side {filled[0].side if hit else None}"))
    if hit:
        factor = 0.5e-9 * float(M.ASSET_MULTIPLIER[PLANT_ASSET])
        cost = float(filled[0].cost_usd)
        # close label: the last tick of the tape, bar 65.
        exit_close = int(np.asarray(rec.mid, np.int64)[65])
        want_close = (exit_close - int(held.limit_mid2)) * factor - cost
        got_close = float(filled[0].cert[CLOSE])
        out.append(_check(
            "the hand-computed CLOSE-label cert matches the frozen law",
            abs(want_close - got_close) < 1e-6,
            f"hand {want_close:.6f} vs law {got_close:.6f}"))
        # 1800 s label: entry + 30 bars lands inside the phase, so the last tick
        # at or before it is bar 36's print.
        exit_fixed = int(np.asarray(rec.mid, np.int64)[36])
        want_fixed = (exit_fixed - int(held.limit_mid2)) * factor - cost
        got_fixed = float(filled[0].cert[FIXED])
        out.append(_check(
            "the hand-computed 1800 s cert matches the frozen law",
            abs(want_fixed - got_fixed) < 1e-6,
            f"hand {want_fixed:.6f} vs law {got_fixed:.6f}"))
        out.append(_check("the two labels genuinely differ on this plant",
                          abs(want_close - want_fixed) > 1.0,
                          f"close {got_close:.1f} vs 1800 s {got_fixed:.1f}"))
        out.append(_check(
            "the break-pullback-continuation trade is a WIN",
            got_close > 0.0 and got_fixed > 0.0,
            f"close {got_close:.1f}, 1800 s {got_fixed:.1f}"))
        out.append(_check(
            "the causality chain holds: source < breach close < arm <= fill",
            bool(audit) and int(audit[0]["source_ts_ns"])
            < int(audit[0]["breach_close_ts_ns"]) < int(audit[0]["arm_ts_ns"])
            <= int(audit[0]["fill_ts_ns"]),
            f"{audit[0] if audit else 'no audit row'}"))
    else:
        for name in ("the hand-computed CLOSE-label cert matches the frozen law",
                     "the hand-computed 1800 s cert matches the frozen law",
                     "the two labels genuinely differ on this plant",
                     "the break-pullback-continuation trade is a WIN",
                     "the causality chain holds: source < breach close < arm "
                     "<= fill"):
            out.append(_check(name, False, "no fill"))

    # The cancel law: the same limit cancelled BEFORE the spike does not fill.
    cancelled = Cand(**{f.name: getattr(held, f.name)
                        for f in Cand.__dataclass_fields__.values()})
    cancelled.cancel_bar = 6
    counts2 = {"pb_armed": 0, "pb_filled": 0, "pb_no_fill": 0,
               "pb_no_window": 0, "pb_unpriceable": 0}
    none = price_pullback(index, rec, [cancelled], [0], counts2)
    out.append(_check("a limit cancelled before the pullback tick does not fill",
                      not none and counts2["pb_no_fill"] == 1,
                      f"filled {len(none)}, no_fill {counts2['pb_no_fill']}"))
    return out


def _selftest_reclaim() -> list[tuple[str, bool, str]]:
    """The planted FAKE break: it pulls back, fills, then reclaims and loses."""

    pieces = _plant_pieces()
    rec = pieces["rec"]
    world = pieces["world"]
    counters = _empty_counters()
    cands = form_candidates(pieces["cell"], pieces["lcell"], pieces["sidecar"],
                            0, None, counters)
    fake = next(c for c in cands
                if round(c.zone_price) == round(world["fake_zone"])
                and c.break_dir == 1)
    resolve_pullback(fake, pieces["mid"], 0.30, 12)
    index = _plant_index(rec)
    counts = {"pb_armed": 0, "pb_filled": 0, "pb_no_fill": 0,
              "pb_no_window": 0, "pb_unpriceable": 0}
    filled = price_pullback(index, rec, [fake], [0], counts)
    hit = bool(filled)
    out = [_check("the fake break's pullback limit fills", hit,
                  f"{counts}")]
    if not hit:
        return out + [_check("the fake break is priced as a LOSS", False,
                             "no fill")]
    factor = 0.5e-9 * float(M.ASSET_MULTIPLIER[PLANT_ASSET])
    cost = float(filled[0].cost_usd)
    exit_close = int(np.asarray(rec.mid, np.int64)[65])
    want = (exit_close - int(fake.limit_mid2)) * factor - cost
    got = float(filled[0].cert[CLOSE])
    out.append(_check("the fake break's hand-computed cert matches the law",
                      abs(want - got) < 1e-6,
                      f"hand {want:.6f} vs law {got:.6f}"))
    out.append(_check("the fake break is priced HONESTLY as a loss",
                      got < 0.0 and float(filled[0].cert[FIXED]) < 0.0,
                      f"close {got:.1f}, 1800 s {filled[0].cert[FIXED]:.1f}"))
    out.append(_check("no wall was hit, so the loss is the honest excursion",
                      not filled[0].wall[CLOSE],
                      f"wall {filled[0].wall[CLOSE]}, MAE "
                      f"{filled[0].mae[CLOSE]:.1f}"))
    return out


def _planted_selector(rows: int = 900, seed: int = SEED
                      ) -> tuple[list[Cand], np.ndarray, np.ndarray,
                                 dict[str, list[int]]]:
    """A world where a defended level that BREAKS with impulse pays, and where
    neither term alone is enough."""

    rng = np.random.default_rng(seed)
    days = [20220100 + d for d in range(60)]
    cands: list[Cand] = []
    payoff: list[float] = []
    impulse: list[float] = []
    for d8 in days:
        for k in range(rows // len(days)):
            strong = (k % 3 == 0)
            fast = (k % 2 == 0)
            lev = np.zeros(LV.NLEV, np.float64)
            lev[LV.LEVEL_INDEX["sd_held"]] = 4.0 if strong else 0.0
            lev[LV.LEVEL_INDEX["sd_broke"]] = 0.0 if strong else 4.0
            lev[LV.LEVEL_INDEX["ps_held"]] = 2.0 if strong else 0.0
            lev[LV.LEVEL_INDEX["ps_broke"]] = 0.0 if strong else 2.0
            cands.append(Cand(
                asset="NKD", d8=int(d8), phase="0", cell=int(d8), year=2022,
                zone_kind="PD_HIGH", zone_price=100.0, width=1.0, atr_mid2=10.0,
                break_dir=1, defence_side=-1, broken_edge=101.0, bar=10 + k,
                read_bar=9 + k, n_bars=200, pull_frac=0.3, pull_dur=4,
                ext_reach=1.0, lev_read=lev,
                pd_held=1.0 if strong else 0.0, pd_broke=0.0,
                defence_history=4.0, visit_bars=2, visit_touches=2,
                visit_flow=0.0))
            cands[-1].x = np.zeros(NFEAT, np.float64)
            impulse.append(1.0 if fast else -1.0)
            payoff.append(400.0 + float(rng.normal(0, 20)) if (strong and fast)
                          else -120.0 + float(rng.normal(0, 20)))
    return (cands, np.asarray(payoff, np.float64),
            np.asarray(impulse, np.float64), {"NKD": days})


def _selftest_selector(mutant: str) -> list[tuple[str, bool, str]]:
    cands, payoff, impulse, days = _planted_selector()
    rows, _report = score_selector(cands, impulse, days, mutant)
    picked = [r.position for r in rows if r.selected[LIVE_CELL]]
    recovered = float(np.mean([payoff[p] for p in picked])) if picked else 0.0
    base = float(np.mean(payoff))
    out = [_check("the selector recovers the planted defended-and-fast rows",
                  len(picked) > 0 and recovered > base + 200.0,
                  f"{len(picked)} picked, mean {recovered:.1f} vs base "
                  f"{base:.1f}")]
    strong = [p for p in picked
              if cands[p].lev_read[LV.LEVEL_INDEX["sd_held"]] > 0]
    out.append(_check("every selected row is a high-barrier row",
                      bool(picked) and len(strong) == len(picked),
                      f"{len(strong)}/{len(picked)} strong"))
    fast = [p for p in picked if impulse[p] > 0]
    out.append(_check("every selected row is a high-impulse row (the I gate is "
                      "load bearing)",
                      bool(picked) and len(fast) == len(picked),
                      f"{len(fast)}/{len(picked)} fast"))
    # A row with NO impulse score is never selected, by registration.
    blind = np.array(impulse, copy=True)
    blind[::7] = np.nan
    rows_b, report_b = score_selector(cands, blind, days, mutant)
    unscored = {r.position for r in rows_b if not r.has_impulse}
    picked_b = {r.position for r in rows_b if r.selected[LIVE_CELL]}
    out.append(_check("a candidate with no impulse score is never selected",
                      bool(unscored) and not (unscored & picked_b),
                      f"{len(unscored)} unscored, "
                      f"{len(unscored & picked_b)} of them selected"))
    # The permuted control: level memory shuffled across rows kills the signal.
    rng = np.random.default_rng(SEED + 7)
    order = rng.permutation(len(cands))
    permuted = []
    for slot, cand in enumerate(cands):
        clone = Cand(**{f.name: getattr(cand, f.name)
                        for f in Cand.__dataclass_fields__.values()})
        donor = cands[int(order[slot])]
        clone.lev_read = donor.lev_read
        clone.pd_held = donor.pd_held
        permuted.append(clone)
    rows_c, _r = score_selector(permuted, impulse, days, mutant)
    picked_c = [r.position for r in rows_c if r.selected[LIVE_CELL]]
    control_mean = (float(np.mean([payoff[p] for p in picked_c]))
                    if picked_c else 0.0)
    out.append(_check("the permuted control does NOT recover the planted rows",
                      abs(control_mean - base) < 200.0,
                      f"control mean {control_mean:.1f} vs base {base:.1f}"))
    out += _selftest_leak(mutant)
    return out


def _planted_leak() -> tuple[list[Cand], np.ndarray, np.ndarray,
                             dict[str, list[int]]]:
    """A world whose only paying structure lives on the SCORING day itself.

    Twenty-five training days carry two candidates each, all at the same barrier
    value, so the training fold's top-tercile cut is uninformative.  The scoring
    day then carries two hundred candidates whose barrier runs 0..9, and only
    those at 7 and above pay.  A lawful cut, learned from days strictly before,
    admits almost the whole scoring day and recovers nothing.  A cut that folds
    the scoring day in is DOMINATED by that day - 200 rows against 50 - so it
    lands near the day's own top tercile and picks the payers.  The gap between
    those two answers is exactly the leak the guard exists to prevent.  Impulse
    is constant, so the I gate is a no-op and the B gate alone decides.
    """

    days = [20220100 + d for d in range(26)]
    cands: list[Cand] = []
    payoff: list[float] = []

    def make(d8: int, held: float, pays: bool, bar: int) -> None:
        lev = np.zeros(LV.NLEV, np.float64)
        lev[LV.LEVEL_INDEX["sd_held"]] = float(held)
        cands.append(Cand(
            asset="SI", d8=int(d8), phase="0", cell=int(d8), year=2022,
            zone_kind="SAME_DAY", zone_price=100.0, width=1.0, atr_mid2=10.0,
            break_dir=1, defence_side=-1, broken_edge=101.0, bar=int(bar),
            read_bar=int(bar) - 1, n_bars=400, pull_frac=0.3, pull_dur=4,
            ext_reach=1.0, lev_read=lev, pd_held=0.0, pd_broke=0.0,
            defence_history=float(held) + 1.0, visit_bars=1, visit_touches=1,
            visit_flow=0.0))
        payoff.append(400.0 if pays else -120.0)

    for d8 in days[:25]:
        for k in range(2):
            make(d8, 1.0, False, 10 + k)
    for k in range(200):
        held = float(k % 10)
        make(days[25], held, held >= 7.0, 10 + k)
    return (cands, np.asarray(payoff, np.float64),
            np.zeros(len(cands), np.float64), {"SI": days})


def _selftest_leak(mutant: str) -> list[tuple[str, bool, str]]:
    cands, payoff, impulse, days = _planted_leak()
    rows, _report = score_selector(cands, impulse, days, mutant)
    picked = [r.position for r in rows if r.selected[LIVE_CELL]]
    day_rows = [p for p, c in enumerate(cands) if c.d8 == max(days["SI"])]
    base = float(np.mean([payoff[p] for p in day_rows]))
    recovered = float(np.mean([payoff[p] for p in picked])) if picked else base
    # Causally the cut admits nearly the whole day, so the selection cannot beat
    # the day's own base rate by more than a rounding of one row.
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
        "live": {LANE: {
            "cash": cash,
            "mdd": {"clears": mdd < MDD_CEILING, "max_binding_usd": mdd},
            "stress": stress, "neighbours_agree": True}},
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
    """All five clauses fire on constructed receipts, and the partition holds."""

    cases = [
        ("LIVE", LETTER_LIVE,
         _receipt(3000.0, 100.0, 0.01, 5000.0, 300.0)),
        ("K1", LETTER_KILL,
         _receipt(100.0, 100.0, 0.01, 10.0, 300.0)),
        ("K2", LETTER_KILL,
         _receipt(100.0, 100.0, 0.20, 5000.0, -300.0, upper=-10.0)),
        ("K3", LETTER_KILL,
         _receipt(100.0, 100.0, 0.20, 5000.0, -300.0, upper=400.0)),
        ("UNRESOLVED", LETTER_UNRESOLVED,
         _receipt(100.0, 100.0, 0.20, 5000.0, 300.0)),
    ]
    out: list[tuple[str, bool, str]] = []
    for clause, letter, receipt in cases:
        got = line_letter(receipt)
        out.append(_check(
            f"the constructed {clause} receipt fires {clause}",
            got["clause"] == clause and got["letter"] == letter,
            f"got {got['letter']} / {got['clause']}"))
    out.append(_check(
        "a breached MDD cannot be LIVE",
        line_letter(_receipt(3000.0, 5000.0, 0.01, 5000.0, 300.0))["letter"]
        != LETTER_LIVE))
    # The partition assertion: every point of the outcome space maps to exactly
    # one letter AND exactly one clause, and every clause is reachable.
    seen: dict[str, int] = {}
    total = 0
    for bits in itertools.product((False, True), repeat=9):
        letter, clause, matching = classify(*bits)
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
    return out


def selftest() -> int:
    mutant = _mutant()
    results: list[tuple[str, bool, str]] = []
    results += _selftest_formation()
    results += _selftest_fill()
    results += _selftest_reclaim()
    results += _selftest_selector(mutant)
    results += S22._selftest_replay()
    results += _selftest_letters()
    results += S22._selftest_stress()
    print(f"sweep 23 selftest  mutant={mutant or 'none'}")
    bad = 0
    for name, ok, detail in results:
        mark = "ok  " if ok else "FAIL"
        bad += int(not ok)
        print(f"  [{mark}] {name}" + (f"  ({detail})" if detail else ""))
    print(f"  {len(results) - bad}/{len(results)} checks passed")
    if mutant == MUTANT_TESTDAY:
        red = [name for name, ok, _d in results if not ok]
        print(f"  MUTANT {mutant}: {len(red)} check(s) red -> "
              f"{'the guard is load bearing' if red else 'THE GUARD IS NOT LOAD BEARING'}")
        return 0 if red else 1
    return 1 if bad else 0


# --------------------------------------------------------------------------
# The log and the entry point.
# --------------------------------------------------------------------------

_show = S22._show


def log_rows(report: Mapping[str, object]) -> list[dict[str, object]]:
    params = json.dumps({
        "lines": list(LINES), "letter_lines": list(LETTER_LINES),
        "labels": list(LABELS), "q_zone": Q_ZONE, "q_depth": Q_DEPTH,
        "q_cancel": Q_CANCEL, "depth_clip": list(DEPTH_CLIP),
        "cancel_clip": list(CANCEL_CLIP),
        "max_episode_bars": MAX_EPISODE_BARS,
        "barrier_cuts": BARRIER_CUTS, "impulse_cuts": IMPULSE_CUTS,
        "live_cell": list(LIVE_CELL), "impulse_horizon_s": IMPULSE_HORIZON_S,
        "min_prior_days": MIN_PRIOR_DAYS, "portfolio_cap": PORTFOLIO_CAP,
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

    # 1. the registered live cell, per line x label x asset
    for name in LINES:
        block = report["live"][name]
        for label in LABELS:
            for asset in ASSETS:
                counter += 1
                line = blank(dict(shared))
                cell = block["per_asset"][asset][label]
                cash = block["cash"][asset]
                letter = (report["letters"][LANE]["letter"]
                          if name in LETTER_LINES else "REPORT-ONLY (no letter)")
                line["id"] = f"{LOG_PREFIX}-{counter:03d}"
                line["rule"] = f"{name}/{label}/{asset}"
                line["days"] = cell["days"]
                line["coverage"] = cell["coverage"]
                tag = asset.lower()
                line[f"{tag}_usd_day"] = cell["usd_per_asset_day"]
                line[f"mdd_{tag}"] = cell["mdd_day_usd"]
                line[f"walls_{tag}"] = cell["wall_rate"]
                line["replay_skips"] = (block["replay"]["rejected_occupancy"]
                                        + block["replay"]["rejected_cap"])
                line["null_margin"] = report["block_nulls"].get(
                    f"{name}|{asset}", {}).get("p")
                line["note"] = (
                    f"{name} ({LINE_NAME[name]}), label {label}, {asset}: "
                    f"n {cell['n']} of {cell['formed']} formed, coverage "
                    f"{_show(cell['coverage'])}, mean "
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
                    f"{block['neighbours_agree']}; letter {letter}")
                rows.append(line)

    # 2. the selector sensitivity grid
    for name in LINES:
        for cut in GRID:
            counter += 1
            cell = report["grid"][name][f"{cut[0]}|{cut[1]}"]
            line = blank(dict(shared))
            line["id"] = f"{LOG_PREFIX}-{counter:03d}"
            line["rule"] = f"{name}/grid/{cut[0]}-{cut[1]}"
            line["days"] = len(report["scoring_days"]["NKD"])
            for asset in ASSETS:
                line[f"{asset.lower()}_usd_day"] = cell["cash"][asset][
                    "usd_per_day"]
            line["note"] = (
                f"selector sensitivity, {name}, barrier cut {cut[0]} x impulse "
                f"cut {cut[1]}: n {cell['n']}; " + "; ".join(
                    f"{asset} {_show(cell['cash'][asset]['usd_per_day'])} "
                    f"usd/day, -2SE "
                    f"{_show(cell['cash'][asset]['mean_minus_2se_usd'])}"
                    for asset in ASSETS)
                + ("; REGISTERED LIVE CELL" if tuple(cut) == LIVE_CELL
                   else "; neighbour")
                + ("" if name in LETTER_LINES else "; REPORT-ONLY line"))
            rows.append(line)

    # 3. C1, the matched control
    for name, cell in sorted(report["control"]["by_line"].items()):
        counter += 1
        which, asset = name.split("|")
        line = blank(dict(shared))
        line["id"] = f"{LOG_PREFIX}-{counter:03d}"
        line["rule"] = f"{which}/control/{asset}"
        line["days"] = cell["dates"]
        line[f"{asset.lower()}_usd_day"] = cell["delta_usd_per_date"]
        line["null_margin"] = cell["p_max_adjusted"]
        line["note"] = (
            f"C1 paired matched control, {which}, {asset}: selected minus "
            f"control {_show(cell['delta_usd_per_date'])} usd per asset-day "
            f"over {cell['dates']} dates, SE {_show(cell['se_usd'])}, t "
            f"{_show(cell['t'])}, shared-date-sign max-stat p "
            f"{_show(cell['p_max_adjusted'])} over "
            f"{len(report['control']['family'])} lines, simultaneous 95% "
            f"[{_show(cell['lower95_simultaneous_usd'])}, "
            f"{_show(cell['upper95_simultaneous_usd'])}]"
            f"{'' if cell['eligible'] else '; report-only, outside the family'}")
        rows.append(line)

    # 4. C2, the formed ceiling
    for scope in ("SELECTED", "FORMED_UNIVERSE", "FORMED_CAPPED"):
        counter += 1
        cash = report["ceiling"][scope]["cash"]
        line = blank(dict(shared))
        line["id"] = f"{LOG_PREFIX}-{counter:03d}"
        line["rule"] = f"{scope}/ceiling"
        line["days"] = len(report["scoring_days"]["NKD"])
        for asset in ASSETS:
            line[f"{asset.lower()}_usd_day"] = cash[asset]["usd_per_day"]
        bits = report["ceiling"][scope]["hindsight_bits"]
        line["note"] = (
            f"C2 formed-opportunity ceiling, {scope}: " + "; ".join(
                f"{asset} {_show(cash[asset]['usd_per_day'])} usd/day = "
                f"{_show(cash[asset]['over_rung'])} rung over "
                f"{cash[asset]['n']} opportunities, carries rung "
                f"{cash[asset].get('carries_rung')}" for asset in ASSETS)
            + f"; EXPLORATORY, hindsight bits {len(bits)} ({'; '.join(bits)})")
        rows.append(line)

    # 5. the letter and the family line
    counter += 1
    cell = report["letters"][LANE]
    line = blank(dict(shared))
    line["id"] = f"{LOG_PREFIX}-{counter:03d}"
    line["rule"] = f"{LANE}/letter"
    line["days"] = len(report["scoring_days"]["NKD"])
    for asset in DECIDING:
        line[f"{asset.lower()}_usd_day"] = report["live"][LANE]["cash"][asset][
            "usd_per_day"]
    line["note"] = (
        f"LETTER {cell['letter']} for {LANE}: rung {cell['rung_ok']}, MDD "
        f"{cell['mdd_ok']}, cap {cell['cap_ok']}, stress {cell['stress_ok']}, "
        f"control {cell['control_ok']}, neighbours {cell['neighbours_ok']}, "
        f"ceiling carries both rungs {cell['ceiling_carries_both_rungs']}, "
        f"upper bound non-positive {cell['upper_bound_nonpositive']}, matched "
        f"delta positive {cell['matched_delta_positive']}; CLAUSE "
        f"{cell['clause']} = {cell['clause_text']}; clauses matching "
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
        f"FAMILY LETTER {report['family_letter']} (clause {head['clause']}); "
        f"pullback lane at " + ", ".join(
            f"{asset} {_show(head['lane_over_rung'].get(asset))}x rung"
            for asset in DECIDING)
        + "; report-only no-pullback line " + ", ".join(
            f"{asset} {_show(head['report_only_over_rung'].get(asset))}x"
            for asset in DECIDING)
        + "; formed ceiling " + ", ".join(
            f"{asset} {_show(head['formed_ceiling_over_rung'].get(asset))}x"
            for asset in DECIDING)
        + "; capped ceiling " + ", ".join(
            f"{asset} {_show(head['formed_capped_over_rung'].get(asset))}x"
            for asset in DECIDING)
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
    print_causality_rows(report)
    print_formation(report)
    for line in LINES:
        print_line(report, line)
    print_line_extras(report)
    print_grid(report)
    print_controls(report)
    print_decision(report)
    print(f"\nSELECTOR SIGN NOTE\n  {SELECTOR_SIGN_NOTE}")
    write_report(report)
    print(f"\nreport: {OUT_PATH}")
    if args.log:
        rows = log_rows(report)
        written = S1.append_log(rows)
        print(f"log: appended {written} rows to {LOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
