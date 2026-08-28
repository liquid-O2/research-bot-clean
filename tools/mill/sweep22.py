#!/usr/bin/env python3
"""Sweep 22 of the side-resolution mill: F19-LEVELCOLLISION, the decisive test.

Sol's pinpoint ruling ``.audit/briefs/mill-pinpoint-sol-out.md`` sections A, B
and D.  The root cause it names is a two-sided collision observed from one side:
the coarse plane measures an IMPULSE, G1 then treats every local zigzag extreme
the impulse crosses as an independent barrier decision, and a hold-or-break is
decided by barrier strength RELATIVE to impulse strength.  Section B's formation
rule LEVELCOLLISION supplies the missing half - candidates formed at causally
known, previously defended PRICE ZONES, with the barrier term read from the
landed level cache - and section D says to run it once, on EXPLORE, priced.

THE USER'S DIRECTIVE, folded into the charter and binding here: the unit has TWO
entry lanes, not one.  Sol's design is a PRE-TOUCH resting limit that decides
before the collision resolves.  The USER ordered a second lane that decides only
after the zone's whole episode has resolved - "we might be looking for
confirmation a bit too early" - so lane 2 waits for the episode to close beyond
a fold-trained band on EITHER side and then enters in the direction the episode
actually resolved.  Both lanes live in ONE max-stat family; neither is allowed
to be scored as if it were the only test that ran.

LAW OF INPUTS.  Features stay on the causal one-minute plane: the level cache
(``levels.py``), the frozen out-of-fold magnitude channel refit under sweep 20's
own ridge law, and the completed lane-2 window.  Raw tick suffixes PRICE
crossings, limit fills and outcomes, exactly as the frozen mill already prices
the -900 wall; no subminute value ever becomes an input.  The mutant
``QRE2_MILL_S22_MUTANT=selector_uses_test_day`` computes the selector's B and I
cuts including the scoring day and must turn the planted recovery red.

ONE DEVIATION FROM THE BRIEF, recorded here because it is not recoverable from
the column names.  The brief's barrier score reads three defence pairs from the
level cache: ``sd_held - sd_broke``, ``pd_held - pd_broke`` and
``ps_held - ps_broke``.  The cache carries only TWO such pairs (``levels.py``
``DEFENCE_COLUMNS``): same-day and prior-EXPLORE-session.  There is no
minute-grain prior-DAY pair and there cannot be one - the mill's licence binds
HOLD intraday paths as unread, which is exactly why the cache's prior session is
the prior EXPLORE session three locked days back.  The third pair is therefore
built HERE, at day scale, from two licensed facts: the context store's prior-day
OHLC (a prior-day extreme is a price the prior session reversed from) and the
current day's own strictly-prior path (a level already traded through today is a
broken level).  It is named ``pd_held``/``pd_broke`` throughout and its
construction is printed beside every barrier table.

Machinery is imported, never re-implemented.  Sweep 8 supplies the cells and
ATR14_prev, sweep 9 the row plane whose counters are the refuse-to-run gate,
sweep 12 the day states, sweep 14 the occurrence stream and fold law, sweep 19
the frozen to-close cert plane, sweep 20 the magnitude ridge law and the no-wall
horizon grid, sweep 1 the cost law, the replay ledgers and the log, ``levels.py``
the barrier plane and ``mill.py`` the frozen entry, fill and outcome laws.

Nothing here is executable.  EXPLORE only, kill-only tier, no packs, no HOLD, no
teacher labels, no 2021, no 2025H2, no commits.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
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

from engine.entry_v2.confirmation_types import FEE_USD  # noqa: E402

import mill as M  # noqa: E402
import levels as LV  # noqa: E402
import sweep1 as S1  # noqa: E402
import sweep7a as S7A  # noqa: E402
import sweep8 as S8  # noqa: E402
import sweep9_twins as S9  # noqa: E402
import sweep12 as S12  # noqa: E402
import sweep14 as S14  # noqa: E402
import sweep19 as S19  # noqa: E402
import sweep20 as S20  # noqa: E402

# --------------------------------------------------------------------------
# The law, registered before anything is read.
# --------------------------------------------------------------------------

SPEC = """QRE2MILLSWEEP22
tier=exploratory; EXPLORE-only, kill-only.  Family F19-LEVELCOLLISION, the one
  decisive priced test of Sol's pinpoint ruling.  Seed 20260827.  Parent trial
  sweep21-066.  NO COMMITS, NO FREEZE, no packs, no HOLD, no teacher labels, no
  2021, no 2025H2.  Two entry lanes in ONE max-stat family, per the USER.
GATE.  Sweep 9's row plane (47402 rows; certifiable HG 138 / NKD 132 / SI 132;
  candidates_seen 313131; cells_with_rows 385) and sweep 14's scoring days
  (41/40/39) reproduce before anything is formed.  The level cache manifest must
  carry schema QRE2MILLLEVELSMANIFEST1 with strictly-prior join evidence, and
  this unit's own levels join audit must report max(source stamp - bar stamp)
  strictly negative.  A miss on either refuses the run.
ZONES (Sol B.1).  Eligible zones per (asset, day, phase) are (a) the TRUE prior
  day's high, low and close from the context store's day-level OHLC, carried per
  cell in the level cache sidecar; (b) the cached prior-EXPLORE-session value
  edges, labelled prior-EXPLORE and never "yesterday"; and (c) same-day price
  zones, registered at the first bar whose cache row shows at least one RESOLVED
  prior touch (sd_held + sd_broke >= 1) at that price, deduplicated against
  already-registered zones by one zone width and capped at 8 per cell in birth
  order.  A same-day zone is eligible only at bars STRICTLY AFTER its birth bar.
ZONE WIDTH.  Fold-trained, train days only, per asset x phase.  Over cells of
  the stratum on strictly prior EXPLORE days, pool (cell mid range / atr_mid2)
  / 10 - a tenth of a session's travel, the granularity at which distinct price
  zones are distinguishable - take the Q_ZONE = 75th percentile and SNAP it to
  the nearest of the level cache's own band multipliers (0.10, 0.20, 0.40).
  Snapping is not a convenience: the defence memory this unit reads at the zone
  is measured by the cache AT THAT WIDTH, so an unsnapped width would score a
  barrier with a band it was never counted in.  The outer band is
  OUTER_STEP = 2.0 zone widths.
CANDIDATES (Sol B.2).  One candidate per FIRST approach to a zone from outside
  the outer band, deduplicated by (asset, day, phase, level, approach side) and
  locked until price causally departs the outer band or breaches the zone by a
  full width on the far side.  Formation reads only the lattice, the level cache
  and ATR14_prev; it never opens a shard.  Formed-opportunity counts per
  asset-day are recorded and reported.
FOLD-TRAINED LANE PARAMETERS.  Three parameter-free statistics are computed for
  every formed candidate at formation time, over the next MAX_EPISODE_BARS = 90
  bars: penetration fraction (how far into the zone price came, in half-widths
  from the near edge), reach (max |mid - zone| / w) and duration (bars until
  |mid - zone| first exceeds 1.5 w).  For a scoring day, each lane parameter is a
  fixed quantile of the pool from that stratum's STRICTLY PRIOR EXPLORE days:
  limit depth Q_DEPTH = 50th of penetration, clipped [0.05, 0.95] of the zone's
  full width; episode band Q_EPI = 60th of reach, clipped [1.2, 6.0] widths;
  cancel duration Q_CANCEL = 50th of duration, clipped [3, 90] bars; the
  floor is a registered testability floor, not a fit - a resting limit that
  lives one minute is not a resting-limit lane at all.  Because
  the three statistics are parameter-free, formation on day d depends only on
  days strictly before d and the recursion closes.
LANE 1, PRE-TOUCH (Sol B.3).  A fade-side resting limit at the fold-trained
  depth inside the zone, armed at the approach bar's stamp and cancelled after
  the fold-trained duration.  Approaching from below fades SHORT, from above
  fades LONG.  RAW TICKS decide the fill: the first raw mid at or through the
  limit inside the arm window, via the same monotone first-passage structure the
  frozen mill uses for the -900 wall.  Entry price IS the limit price on fill;
  entry stamp is the filling tick's stamp; cost is the frozen cost at the last
  trusted quote STRICTLY BEFORE that stamp.  No subminute value becomes an input.
LANE 2, EPISODE-RESOLUTION (the USER's).  The window opens at the approach bar
  and closes at the first one-minute CLOSE beyond the fold-trained episode band
  on EITHER side of the zone, provided at least one bar closed INSIDE the zone
  first.  A zone approached but never touched forms no lane-2 entry.  Entry is at
  the NEXT bar's stamp under the frozen entry law (last trusted quote strictly
  before t); the side IS the exit direction.  Window features - touch count,
  held and broke tallies under the levels-cache law, net signed aggressor flow
  absorbed at the zone, window duration and range - are recorded and reported;
  they do NOT gate, because the selector is preregistered identical across lanes
  and spending them would be the model search this unit forbids.
SELECTOR, preregistered monotone, IDENTICAL functional both lanes, no model
  search (Sol B.4).  Barrier score B = the mean of three train-fold-standardized
  differences read at the zone, at the last completed bar before that lane's own
  decision (lane 1: the approach bar; lane 2: the window-close bar):
  (sd_held - sd_broke), (pd_held - pd_broke) and (ps_held - ps_broke).  The
  sd and ps pairs are the level cache's own.  The pd pair is built by this unit
  at DAY scale because the cache carries no minute-grain prior-day pair by
  licence: pd_held = 1 when the zone is a prior-day extreme or a prior-EXPLORE
  value edge (a completed session reversed there), else 0; pd_broke = 1 when the
  current day's own strictly-prior path has already traded a full width beyond
  the zone on the far side, else 0.  Impulse score I = the frozen out-of-fold
  magnitude prediction: sweep 20's ridge law refit identically (its coarse
  post-reset universe, the 16 causal sweep-14 features, cell-balanced weights,
  lambda 1.0, >= 25 strictly prior EXPLORE days, >= 50 fit rows, target the
  no-wall ABSMOVE at h = 1800 s) and applied out of fold to the feature vector of
  the LAST G1 occurrence in the candidate's own cell strictly before its
  approach bar.  B and I are each standardized on the training fold per asset x
  phase.  TRADE IFF B >= the train TOP-TERCILE cut AND (B - I) >= the train
  MEDIAN cut.  High predicted magnitude is never a reason to trade by itself:
  it enters only negatively, through B - I.
NEIGHBOUR SENSITIVITY, required.  Both lanes are recomputed on the
  (quartile, tercile) x (median, 60th percentile) grid - barrier cut at the 75th
  and 66.667th percentiles crossed with the margin cut at the 50th and 60th.
  The registered LIVE cell is (tercile, median).  A LIVE letter requires the
  three neighbours not to flip the sign.
PRICING.  The frozen outcome law - the -900 wall or the phase close, whichever
  comes first - is PRIMARY and carries the letters.  Every entry in both lanes is
  priced by the frozen scalar law ``MillIndex.outcome``.  Lane-2 close-label
  certs are cross-checked against ``S19.build_cert_plane`` at the same
  (cell, side, bar) and a disagreement refuses the run.  The 1800 s fixed hold is
  reported BESIDE every line as the drift-stripping sensitivity, priced by the
  same law with the phase close replaced by min(entry + 1800 s, phase close).
REPLAY.  Exact chronological replay, fixhold page section B: sort by timestamp
  with the frozen tie break (stamp, asset, cell, bar, side); process EXITS
  BEFORE ENTRIES at an equal stamp; seat only when the asset is flat; hold to
  the registered exit; at most 12 seated entries per PORTFOLIO date, taken
  dynamically; carry every split date including zero-entry dates.
MDD.  Fixhold section D: per-asset trade and day ledgers, portfolio trade and
  day ledgers, and event-time portfolio equity that charges cost at entry and
  marks every open position at the causal raw mid until exit.  Cumulative cash
  starts at zero; MDD is the largest prior peak minus later equity.  Binding is
  the deciding assets' own ledgers plus every portfolio ledger.
STRESSES.  The standing 2 percent adversarial stress - the worst 2 percent of
  seated entries per asset take their own MAE as the realized outcome - and the
  doubled-spread stress, which charges the spread component of the frozen cost a
  second time on every entry.  Both re-run the replay so occupancy follows.
CONTROLS.  C1: per selected event a paired control drawn from the G1 occurrence
  universe, matched on asset, day, phase, approach-time bin (6 equal bins of the
  phase) and magnitude bin (train terciles of I), nearest in I with a frozen tie
  break, priced under the frozen outcome law at its own bar and side; its level
  memory and location vector is PERMUTED within the training fold and the share
  of permuted controls that would have been selected is reported as the
  count-match diagnostic.  Selected minus control by asset-day, studentized,
  shared-date-sign maxT over the family = 2 lanes x 2 deciding assets, 10000
  draws; HG report-only.  C2: the formed-opportunity ceiling - the best lawfully
  priced event inside each formed opportunity over both lanes, both sides and
  every legal bar of the window - reported as an exploratory ceiling with its
  hindsight bits named, both RAW (every formed opportunity) and CAPPED at
  the 12 best events per portfolio date so one ceiling line is comparable to
  a rung.  The KILL test reads the raw formed ceiling, per Sol B.  C3: block-permutation nulls on every headline, 2000
  draws, re-drawing the same selected COUNT uniformly inside each
  (asset, phase, day) block of formed candidates.
LETTERS, verbatim from the pinpoint page.
  LEVELCOLLISION-LIVE only if a lane has NKD and SI each above 1500 USD per
    asset-day at the point estimate AND at mean minus two asset-day-block
    standard errors, every binding MDD below 1000, cap and occupancy lawful, the
    paired control surviving maxT at 0.05, and adjacent fold-trained thresholds
    not flipping the result.
  LEVELCOLLISION-UNRESOLVED if the formed ceiling can carry both rungs and the
    causal matched delta is positive, but power or one live bound fails.
  LEVELCOLLISION-KILL if the formed ceiling misses either deciding rung, or a
    powered deciding asset has a non-positive 95 percent upper bound against its
    matched control.
  A letter per lane, plus the family letter: LIVE if any lane is LIVE, else
  UNRESOLVED if any lane qualifies, else KILL.
MUTANT.  QRE2_MILL_S22_MUTANT=selector_uses_test_day computes the selector's B
  and I standardizations and cuts INCLUDING the scoring day.  It must flip the
  planted recovery red.
"""

ASSETS = S1.ASSETS
DECIDING = ("NKD", "SI")
REPORT_ONLY = ("HG",)
PHASES = S14.PHASES
SEED = 20260827
BAR_SECONDS = S1.BAR_SECONDS
NANOS = 1_000_000_000

FAMILY = "F19-LEVELCOLLISION"
PARENT_TRIAL = "sweep21-066"
SELECTION_RULE = ("none: preregistered two-lane formation, one monotone "
                  "selector, fold-trained thresholds, no model search")

LOG_PREFIX = "sweep22"
OUT_PATH = ROOT / ".audit/mill-sweep22.json"
LOG_PATH = S1.LOG_PATH

# Inherited, aliased so an upstream drift fails loudly here.
FEATURES = S14.FEATURES
NFEAT = S14.NFEAT
RIDGE_LAMBDA = S14.RIDGE_LAMBDA               # 1.0
MIN_PRIOR_DAYS = 25                           # scoring warmup, S14.MIN_PRIOR_DAYS_FIT
MIN_FIT_ROWS = S14.MIN_FIT_ROWS               # 50
DAY_RUNG_USD = S1.DAY_RUNG_USD                # HG 2000, NKD 1500, SI 1500
MDD_CEILING = S1.MDD_CAP_USD                  # 1000
STRESS_RATE = 0.02
REPRO_ROWS = S14.REPRO_ROWS
REPRO_COUNTERS = S14.REPRO_COUNTERS
REPRO_CERTIFIABLE = S14.REPRO_CERTIFIABLE
REPRO_SCORING_DAYS = {"HG": 41, "NKD": 40, "SI": 39}

# This unit's own constants, every one named and fixed before the run.
LANES = ("L1_PRETOUCH", "L2_EPISODE")
LANE_NAME = {"L1_PRETOUCH": "pre-touch fade-side resting limit (Sol B.3)",
             "L2_EPISODE": "episode-resolution entry (the USER's late lane)"}
CLOSE = "close"
FIXHOLD_S = 1800
FIXED = str(FIXHOLD_S)
LABELS = (CLOSE, FIXED)

Q_ZONE = 75.0            # zone width, of (cell range / atr) / 10, then snapped
ZONE_RANGE_DIVISOR = 10.0
OUTER_STEP = 2.0         # outer band, in zone widths
Q_DEPTH = 50.0           # lane-1 limit depth, of the penetration pool
DEPTH_CLIP = (0.05, 0.95)
Q_EPI = 60.0             # lane-2 episode band, of the reach pool
EPI_CLIP = (1.2, 6.0)
Q_CANCEL = 50.0          # lane-1 cancel duration, of the duration pool
CANCEL_CLIP = (3, 90)        # a limit must live >= 3 bars to be a lane
MAX_EPISODE_BARS = 90
REACH_REFERENCE = 1.5    # the parameter-free duration reference, in widths
MAX_SAME_DAY_ZONES = 8
MIN_SD_RESOLVED = 1.0    # resolved prior touches a same-day zone needs
MIN_TRAIN_CANDS = 40     # a stratum below this trades nothing on that day

BARRIER_CUTS = {"tercile": 100.0 * 2.0 / 3.0, "quartile": 75.0}
MARGIN_CUTS = {"median": 50.0, "p60": 60.0}
LIVE_CELL = ("tercile", "median")
GRID = [(b, m) for b in ("quartile", "tercile") for m in ("median", "p60")]

IMPULSE_HORIZON_S = 1800     # sweep 20's shortest no-wall horizon, frozen here
TIME_BINS = 6                # approach-time bins for the C1 match
MAG_BINS = 3                 # magnitude bins, train terciles of I
CONTROL_DRAWS = 2000         # C3 block-permutation draws
SIGN_DRAWS = 10_000          # C1 shared-date-sign maxT draws
PORTFOLIO_CAP = 12

ZONE_KINDS = ("PD_HIGH", "PD_LOW", "PD_CLOSE", "PEXP_VALUE_HI",
              "PEXP_VALUE_LO", "SAME_DAY")
# pd_held: a completed session reversed at this price.  Not a location flag -
# a prior-day extreme and a prior-EXPLORE value edge are both prices a finished
# session turned at, which is exactly the day-scale defence the minute-grain
# cache is forbidden to count for the immediately prior locked day.
PD_HELD_KINDS = ("PD_HIGH", "PD_LOW", "PEXP_VALUE_HI", "PEXP_VALUE_LO")

HINDSIGHT_CEILING = ("which lane", "which bar inside the formed window",
                     "which side")

MUTANT_ENV = "QRE2_MILL_S22_MUTANT"
MUTANT_TESTDAY = "selector_uses_test_day"
MUTANTS = (MUTANT_TESTDAY,)

PLANT_ASSET = "HG"
PLANT_USD_PER_ATR = 400.0
PLANT_LEVEL_MID2 = 400_000_000_000


class SweepRefusal(RuntimeError):
    pass


SPEC_SHA = S1._sha_text(SPEC)


def code_sha() -> str:
    return S1._sha_file(Path(__file__).resolve())


def _mutant() -> str:
    name = os.environ.get(MUTANT_ENV, "")
    if name and name not in MUTANTS:
        raise SweepRefusal(f"unknown sweep 22 mutant: {name}")
    return name


def _pct(values: Sequence[float], mark: float) -> float | None:
    clean = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    return float(np.percentile(clean, mark)) if clean else None


def _mean_se(values: Sequence[float]) -> tuple[float | None, float | None]:
    if not len(values):
        return None, None
    array = np.asarray(values, np.float64)
    mean = float(array.mean())
    if len(array) < 2:
        return mean, None
    return mean, float(array.std(ddof=1) / math.sqrt(len(array)))


def _wilson(hits: int, total: int) -> dict[str, object]:
    if total <= 0:
        return {"hits": 0, "n": 0, "rate": None, "lo": None, "hi": None}
    p = hits / total
    z = 1.959963984540054
    denominator = 1.0 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return {"hits": int(hits), "n": int(total), "rate": float(p),
            "lo": float(centre - half), "hi": float(centre + half)}


def _drawdown(values: Sequence[float]) -> float:
    from engine.entry_v2.replay import _drawdown as engine_drawdown
    return float(engine_drawdown(list(values)))


# --------------------------------------------------------------------------
# The zone catalogue.  Every price is mid2 and every one is causally known at
# the bar it becomes eligible.
# --------------------------------------------------------------------------

@dataclass(slots=True)
class Zone:
    kind: str
    price: float
    born_bar: int          # eligible only at bars STRICTLY after this


def zone_catalogue(sidecar_cell: Mapping[str, object], lcell: LV.LevelCell,
                   mult_index: int, mid: np.ndarray, width: float
                   ) -> tuple[list[Zone], dict[str, int]]:
    """Sol B.1's three families, in one list, with the same-day family grown.

    The day-level prices come from the level cache sidecar, which copied them
    from the context store's prior-day OHLC and the prior-EXPLORE session's
    value edges.  The same-day family is grown from the cache's OWN resolved
    touch counts, which are strictly-prior by construction, and a zone is used
    only at bars after the bar that registered it.
    """

    counters = {"day_level": 0, "same_day": 0, "same_day_deduped": 0,
                "same_day_capped": 0}
    out: list[Zone] = []
    for kind, key in (("PD_HIGH", "pd_high"), ("PD_LOW", "pd_low"),
                      ("PD_CLOSE", "pd_close"),
                      ("PEXP_VALUE_HI", "value_hi"),
                      ("PEXP_VALUE_LO", "value_lo")):
        value = float(sidecar_cell.get(key, float("nan")))
        if math.isfinite(value) and value > 0.0:
            out.append(Zone(kind=kind, price=value, born_bar=-1))
            counters["day_level"] += 1

    # The same-day family.  Both cache sides are read: a price defended against
    # a low fade and a price defended against a high fade are the same price,
    # and the resolved counts are side-signed, so the union is the honest test
    # of "this price has a resolved history".
    resolved = np.zeros(lcell.bars, np.float64)
    for side in LV.SIDES:
        plane = lcell.matrix(side, mult_index)
        held = plane[:, LV.LEVEL_INDEX["sd_held"]]
        broke = plane[:, LV.LEVEL_INDEX["sd_broke"]]
        pair = np.where(np.isfinite(held), held, 0.0) + np.where(
            np.isfinite(broke), broke, 0.0)
        resolved = np.maximum(resolved, pair)
    grown: list[Zone] = []
    for bar in range(1, min(int(lcell.bars), len(mid))):
        if resolved[bar] < MIN_SD_RESOLVED:
            continue
        price = float(mid[bar])
        if any(abs(price - z.price) <= width for z in out + grown):
            counters["same_day_deduped"] += 1
            continue
        if len(grown) >= MAX_SAME_DAY_ZONES:
            counters["same_day_capped"] += 1
            continue
        grown.append(Zone(kind="SAME_DAY", price=price, born_bar=bar))
        counters["same_day"] += 1
    return out + grown, counters


# --------------------------------------------------------------------------
# Candidate formation.  Lattice, level cache and ATR only - no shard is opened.
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
    approach_side: int         # +1 approached from below, -1 from above
    fade_side: int             # the lane-1 trade side, -approach_side
    bar: int                   # the approach bar
    n_bars: int
    # parameter-free pool statistics, computed at formation
    pen_frac: float
    reach: float
    dur: int
    # the barrier read at the approach bar (lane 1's decision bar)
    lev_approach: np.ndarray
    pd_held: float
    pd_broke: float
    # filled once the day's fold-trained parameters are known
    limit_mid2: int = 0
    cancel_bar: int = 0
    close_bar: int = -1
    entry_bar: int = -1
    exit_dir: int = 0
    touches: int = 0
    win_held: float = 0.0
    win_broke: float = 0.0
    win_flow: float = 0.0
    win_bars: int = 0
    win_range_atr: float = 0.0
    lev_close: np.ndarray | None = None
    pd_broke_close: float = 0.0
    # the impulse join
    imp_row: int = -1
    x: np.ndarray | None = None


def _pool_stats(mid: np.ndarray, bar: int, zone: float, width: float,
                approach_side: int) -> tuple[float, float, int]:
    """The three parameter-free statistics every candidate carries.

    They are parameter-free ON PURPOSE.  The lane parameters are quantiles of
    these pools over strictly prior days, so if the statistics themselves
    depended on a parameter the fold recursion would not close.
    """

    stop = min(len(mid), bar + MAX_EPISODE_BARS)
    window = np.asarray(mid[bar:stop], np.float64)
    if not len(window):
        return 0.0, 0.0, MAX_EPISODE_BARS
    near_edge = zone - float(approach_side) * width
    penetration = (float(approach_side) * (window - near_edge)) / (2.0 * width)
    pen = float(np.clip(np.max(penetration), 0.0, 2.0))
    distance = np.abs(window - zone) / width
    reach = float(np.max(distance))
    beyond = np.flatnonzero(distance > REACH_REFERENCE)
    dur = int(beyond[0]) if len(beyond) else MAX_EPISODE_BARS
    return pen, reach, max(int(dur), 1)


def form_candidates(cell: S8.Cell8, lcell: LV.LevelCell,
                    sidecar_cell: Mapping[str, object], mult_index: int,
                    counters: dict[str, int]) -> list[Cand]:
    """Sol B.2: one candidate per first approach from outside the outer band."""

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
    zones, zone_counts = zone_catalogue(sidecar_cell, lcell, mult_index,
                                        mid, width)
    for key, value in zone_counts.items():
        counters[f"zone_{key}"] = counters.get(f"zone_{key}", 0) + value
    outer = OUTER_STEP * width
    out: list[Cand] = []
    running_high = np.maximum.accumulate(mid)
    running_low = np.minimum.accumulate(mid)
    for zone in zones:
        distance = mid[:n] - zone.price
        inside_outer = np.abs(distance) <= outer
        start = max(int(zone.born_bar) + 1, 1)
        # ``armed`` is the dedup lock of Sol B.2.  It starts FALSE, so a zone
        # price is already sitting at cannot manufacture an approach; it turns
        # true only once price is causally outside the outer band, or once price
        # has breached the zone by a full width on the far side.
        armed = False
        breach_from = 0
        for bar in range(start, n):
            if not inside_outer[bar]:
                armed = True
                breach_from = 0
                continue
            if breach_from and float(distance[bar]) * breach_from > width:
                armed = True
            if not armed:
                continue
            approach_side = 1 if float(distance[bar - 1]) < 0.0 else -1
            pen, reach, dur = _pool_stats(mid, bar, zone.price, width,
                                          approach_side)
            fade_side = -approach_side
            plane = lcell.matrix(fade_side, mult_index)
            # pd_broke at the approach bar: has the current day already traded a
            # full width beyond this zone, on the far side, STRICTLY BEFORE now?
            far = (float(running_high[bar - 1]) > zone.price + width
                   if approach_side > 0 else
                   float(running_low[bar - 1]) < zone.price - width)
            out.append(Cand(
                asset=cell.asset, d8=int(cell.d8), phase=cell.phase,
                cell=int(cell.position), year=int(cell.d8) // 10000,
                zone_kind=zone.kind, zone_price=float(zone.price),
                width=width, atr_mid2=float(cell.atr_mid2),
                approach_side=int(approach_side), fade_side=int(fade_side),
                bar=int(bar), n_bars=int(n), pen_frac=pen, reach=reach, dur=dur,
                lev_approach=np.asarray(plane[bar], np.float64),
                pd_held=1.0 if zone.kind in PD_HELD_KINDS else 0.0,
                pd_broke=1.0 if far else 0.0))
            counters["candidates"] += 1
            # The dedup lock: this (asset, day, phase, level, approach side)
            # forms nothing further until price departs the outer band or
            # breaches the zone by a full width on the far side.
            armed = False
            breach_from = int(approach_side)
    return out


def resolve_lanes(cand: Cand, mid: np.ndarray, lcell: LV.LevelCell,
                  mult_index: int, delta: np.ndarray | None,
                  depth_frac: float, epi_frac: float, cancel_bars: int,
                  counters: dict[str, int]) -> None:
    """Both lanes' geometry, once the day's fold-trained parameters are known."""

    zone = cand.zone_price
    width = cand.width
    bar = cand.bar
    n = cand.n_bars

    # ---- lane 1: the limit price and the cancel bar -----------------------
    near_edge = zone - float(cand.approach_side) * width
    level = near_edge + float(cand.approach_side) * depth_frac * 2.0 * width
    # The frozen wall's own floor/ceil convention: a long boundary floors, a
    # short boundary ceils, so a fill is never manufactured by rounding.
    cand.limit_mid2 = int(math.floor(level) if cand.fade_side > 0
                          else math.ceil(level))
    cand.cancel_bar = int(min(n - 1, bar + int(cancel_bars)))

    # ---- lane 2: the episode window ---------------------------------------
    band = epi_frac * width
    touched = False
    touches = 0
    close_bar = -1
    for t in range(bar, min(n, bar + MAX_EPISODE_BARS)):
        offset = float(mid[t]) - zone
        if abs(offset) <= width:
            touched = True
            touches += 1
        if touched and abs(offset) > band:
            close_bar = t
            break
    if close_bar < 0:
        counters["lane2_unresolved" if touched else "lane2_never_touched"] += 1
        return
    entry_bar = close_bar + 1
    if entry_bar >= n - 1:
        counters["lane2_no_next_bar"] += 1
        return
    cand.close_bar = int(close_bar)
    cand.entry_bar = int(entry_bar)
    cand.exit_dir = 1 if float(mid[close_bar]) > zone else -1
    cand.touches = int(touches)
    cand.win_bars = int(close_bar - bar + 1)
    window = np.asarray(mid[bar:close_bar + 1], np.float64)
    cand.win_range_atr = float((window.max() - window.min()) / cand.atr_mid2)
    if delta is not None and len(delta) > close_bar:
        # Net signed aggressor flow absorbed at the zone: only the bars that
        # closed INSIDE the zone count, because flow printed on the way there
        # is impulse, not absorption.
        inside = np.abs(window - zone) <= width
        cand.win_flow = float(np.asarray(delta[bar:close_bar + 1],
                                         np.float64)[inside].sum())
    # The barrier read at lane 2's own decision bar: the window close.  Its
    # source stamp is lat[close_bar], strictly before lat[entry_bar].
    plane = lcell.matrix(cand.fade_side, mult_index)
    cand.lev_close = np.asarray(plane[close_bar], np.float64)
    cand.win_held = float(plane[close_bar, LV.LEVEL_INDEX["sd_held"]])
    cand.win_broke = float(plane[close_bar, LV.LEVEL_INDEX["sd_broke"]])
    running_high = float(np.max(mid[:close_bar + 1]))
    running_low = float(np.min(mid[:close_bar + 1]))
    cand.pd_broke_close = 1.0 if (running_high > zone + width
                                  and running_low < zone - width) else cand.pd_broke
    counters["lane2_resolved"] += 1


# --------------------------------------------------------------------------
# The fold-trained stratum parameters.
# --------------------------------------------------------------------------

@dataclass(slots=True)
class Params:
    mult_index: int
    width_atr: float
    depth_frac: float
    epi_frac: float
    cancel_bars: int
    train_days: int
    train_cands: int


def zone_mult_index(range_pool: Sequence[float]) -> int:
    """Q_ZONE of (cell range / atr) / 10, snapped to the cache's own widths."""

    raw = _pct(range_pool, Q_ZONE)
    if raw is None or not raw > 0.0:
        return LV.DEFAULT_MULT_INDEX
    diffs = [abs(float(mult) - float(raw)) for mult in LV.BAND_MULTS]
    return int(np.argmin(diffs))


def lane_params(range_pool: Sequence[float], pen_pool: Sequence[float],
                reach_pool: Sequence[float], dur_pool: Sequence[float],
                train_days: int) -> Params:
    index = zone_mult_index(range_pool)
    depth = _pct(pen_pool, Q_DEPTH)
    epi = _pct(reach_pool, Q_EPI)
    cancel = _pct(dur_pool, Q_CANCEL)
    return Params(
        mult_index=index, width_atr=float(LV.BAND_MULTS[index]),
        depth_frac=float(np.clip(depth if depth is not None else 0.5,
                                 *DEPTH_CLIP)),
        epi_frac=float(np.clip(epi if epi is not None else 2.0, *EPI_CLIP)),
        cancel_bars=int(np.clip(int(math.ceil(cancel if cancel is not None
                                              else 15.0)), *CANCEL_CLIP)),
        train_days=int(train_days), train_cands=len(pen_pool))


# --------------------------------------------------------------------------
# The impulse channel: sweep 20's magnitude ridge law, refit identically.
# --------------------------------------------------------------------------

@dataclass(slots=True)
class MagRow:
    asset: str
    d8: int
    cell: int
    row: int
    bar: int
    x: np.ndarray
    absmove: float


def fit_impulse(mag: Sequence[MagRow], explore_days: Mapping[str, Sequence[int]],
                mutant: str) -> tuple[dict[tuple[str, int], dict[str, object]],
                                      dict[str, object]]:
    """One frozen ridge per (asset, scored day), trained on strictly prior days.

    This is ``S20.build_folds`` plus ``S20.fold_scores`` with the score side
    left open: the fold's beta is kept so it can be applied to THIS unit's
    candidate rows, which are not sweep 20's rows.  Every arithmetic step - the
    imputation, the cell-balanced weights, the standardization, lambda and the
    weighted centre - is sweep 20's, line for line.
    """

    by_asset: dict[str, dict[int, list[int]]] = {}
    for position, row in enumerate(mag):
        by_asset.setdefault(row.asset, {}).setdefault(row.d8, []).append(position)
    out: dict[tuple[str, int], dict[str, object]] = {}
    counters = {"folds": 0, "skipped_warmup": 0, "skipped_rows": 0,
                "train_rows": 0, "r2_days": 0}
    r2_parts: dict[str, list[tuple[float, float]]] = {}
    for asset in ASSETS:
        days = sorted(int(day) for day in explore_days[asset])
        table = by_asset.get(asset, {})
        for index, d8 in enumerate(days):
            if index < MIN_PRIOR_DAYS:
                counters["skipped_warmup"] += 1
                continue
            train_days = (days[:index + 1] if mutant == MUTANT_TESTDAY
                          else days[:index])
            train = [p for day in train_days for p in table.get(day, [])]
            if len(train) < MIN_FIT_ROWS:
                counters["skipped_rows"] += 1
                continue
            take = np.asarray(train, np.int64)
            xt = np.vstack([mag[int(i)].x for i in take])
            with np.errstate(invalid="ignore"):
                impute = np.nanmean(np.where(np.isfinite(xt), xt, np.nan), axis=0)
            impute = np.where(np.isfinite(impute), impute, 0.0)
            xt = S14._impute(xt, impute)
            counts: dict[int, int] = {}
            for i in take:
                counts[mag[int(i)].cell] = counts.get(mag[int(i)].cell, 0) + 1
            raw = np.asarray([1.0 / counts[mag[int(i)].cell] for i in take],
                             np.float64)
            total = float(raw.sum())
            weight = raw * (len(take) / total) if total > 0 else np.ones(len(take))
            mean = xt.mean(axis=0)
            sd = np.sqrt(np.maximum(xt.var(axis=0), 0.0))
            sd[sd <= 1e-12] = 1.0
            zt = (xt - mean) / sd
            lhs = zt.T @ (zt * weight[:, None]) + RIDGE_LAMBDA * np.eye(NFEAT)
            y = np.asarray([mag[int(i)].absmove for i in take], np.float64)
            centre = float((weight * y).sum() / weight.sum())
            beta = np.linalg.solve(lhs, zt.T @ (weight * (y - centre)))
            out[(asset, int(d8))] = {"impute": impute, "mean": mean, "sd": sd,
                                     "centre": centre, "beta": beta,
                                     "train_rows": len(take)}
            counters["folds"] += 1
            counters["train_rows"] += len(take)
            today = table.get(d8, [])
            if today:
                xs = S14._impute(np.vstack([mag[int(i)].x for i in today]), impute)
                pred = centre + ((xs - mean) / sd) @ beta
                actual = np.asarray([mag[int(i)].absmove for i in today],
                                    np.float64)
                r2_parts.setdefault(asset, []).append(
                    (float(((actual - pred) ** 2).sum()),
                     float(((actual - actual.mean()) ** 2).sum())
                     if len(actual) > 1 else 0.0))
                counters["r2_days"] += 1
    r2 = {}
    for asset, parts in r2_parts.items():
        sse = sum(p[0] for p in parts)
        sst = sum(p[1] for p in parts)
        r2[asset] = (1.0 - sse / sst) if sst > 0 else None
    return out, {"counters": counters, "pooled_within_day_r2": r2,
                 "horizon_s": IMPULSE_HORIZON_S, "target": "no-wall ABSMOVE"}


def impulse_scores(cands: Sequence[Cand],
                   folds: Mapping[tuple[str, int], Mapping[str, object]]
                   ) -> tuple[np.ndarray, dict[str, int]]:
    values = np.full(len(cands), np.nan, np.float64)
    counters = {"scored": 0, "no_fold": 0, "no_features": 0}
    for position, cand in enumerate(cands):
        fold = folds.get((cand.asset, cand.d8))
        if fold is None:
            counters["no_fold"] += 1
            continue
        if cand.x is None:
            counters["no_features"] += 1
            continue
        x = S14._impute(np.asarray(cand.x, np.float64)[None, :],
                        np.asarray(fold["impute"], np.float64))
        z = (x - np.asarray(fold["mean"], np.float64)) / np.asarray(
            fold["sd"], np.float64)
        values[position] = float(fold["centre"]) + float(
            (z @ np.asarray(fold["beta"], np.float64))[0])
        counters["scored"] += 1
    return values, counters


# --------------------------------------------------------------------------
# The barrier score and the monotone selector.
# --------------------------------------------------------------------------

def barrier_components(cand: Cand, lane: str) -> np.ndarray:
    """The three defence differences, read at THIS lane's own decision bar."""

    if lane == "L1_PRETOUCH":
        plane = cand.lev_approach
        pd_broke = cand.pd_broke
    else:
        plane = cand.lev_close if cand.lev_close is not None else cand.lev_approach
        pd_broke = cand.pd_broke_close
    sd = (plane[LV.LEVEL_INDEX["sd_held"]] - plane[LV.LEVEL_INDEX["sd_broke"]])
    ps = (plane[LV.LEVEL_INDEX["ps_held"]] - plane[LV.LEVEL_INDEX["ps_broke"]])
    pd = float(cand.pd_held) - float(pd_broke)
    return np.asarray([sd, pd, ps], np.float64)


@dataclass(slots=True)
class Scored:
    lane: str
    position: int             # index into the candidate list
    b: float
    i: float
    margin: float
    selected: dict[tuple[str, str], bool]


def score_selector(cands: Sequence[Cand], lane: str, impulse: np.ndarray,
                   explore_days: Mapping[str, Sequence[int]], mutant: str
                   ) -> tuple[list[Scored], dict[str, object]]:
    """B and I standardized on the training fold, then the frozen monotone rule.

    The functional is identical in both lanes.  Only the bar at which the
    barrier is read differs, and it differs for one reason: each lane's decision
    happens at a different completed bar, so each lane reads the last bar it
    lawfully can.
    """

    raw = np.vstack([barrier_components(cand, lane) for cand in cands]) if len(
        cands) else np.zeros((0, 3))
    by_stratum: dict[tuple[str, str], dict[int, list[int]]] = {}
    for position, cand in enumerate(cands):
        by_stratum.setdefault((cand.asset, cand.phase), {}).setdefault(
            cand.d8, []).append(position)
    out: list[Scored] = []
    report = {"strata": 0, "days_scored": 0, "days_thin": 0, "rows": 0,
              "cuts": {}}
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
            i_train = np.where(finite, (i_raw_train - i_mean) / i_sd, 0.0)
            margin_train = b_train - i_train
            cuts = {}
            for b_name, b_mark in BARRIER_CUTS.items():
                for m_name, m_mark in MARGIN_CUTS.items():
                    cuts[(b_name, m_name)] = (
                        float(np.percentile(b_train, b_mark)),
                        float(np.percentile(margin_train, m_mark)))
            report["cuts"][f"{asset}|{phase}|{d8}"] = {
                f"{b}|{m}": [v[0], v[1]] for (b, m), v in cuts.items()}
            scoreblock = raw[look]
            b_score = np.nanmean(
                np.where(np.isfinite(scoreblock),
                         (scoreblock - centre) / spread, np.nan), axis=1)
            b_score = np.where(np.isfinite(b_score), b_score, 0.0)
            i_raw = impulse[look]
            i_score = np.where(np.isfinite(i_raw), (i_raw - i_mean) / i_sd, 0.0)
            margin = b_score - i_score
            for local, position in enumerate(look):
                selected = {}
                for key, (b_cut, m_cut) in cuts.items():
                    selected[key] = bool(b_score[local] >= b_cut
                                         and margin[local] >= m_cut)
                out.append(Scored(lane=lane, position=int(position),
                                  b=float(b_score[local]),
                                  i=float(i_score[local]),
                                  margin=float(margin[local]),
                                  selected=selected))
                report["rows"] += 1
    return out, report


# --------------------------------------------------------------------------
# Pricing.  Every entry, both lanes, goes through the frozen scalar law.
# --------------------------------------------------------------------------

@dataclass(slots=True)
class Priced:
    lane: str
    position: int
    asset: str
    d8: int
    phase: str
    cell: int
    bar: int                    # the lattice bar of the decision
    exit_bar: int
    side: int
    entry_ts_ns: int
    entry_mid2: int
    cost_usd: float
    spread_usd: float
    cert: dict[str, float] = field(default_factory=dict)
    wall: dict[str, bool] = field(default_factory=dict)
    mae: dict[str, float] = field(default_factory=dict)
    mfe: dict[str, float] = field(default_factory=dict)
    exit_ts: dict[str, int] = field(default_factory=dict)


def _price_entry(index: M.MillIndex, asset: str, stamp: int, side: int,
                 entry_mid2: int, phase_close_ns: int
                 ) -> dict[str, object] | None:
    """The frozen outcome law at one stamp, under BOTH labels.

    ``close`` is the law as written - the -900 wall or the phase close.  The
    1800 s sensitivity is the SAME law with the phase close replaced by
    min(entry + 1800 s, phase close), which is exactly sweep 16's fixed hold: the
    first of the wall, the horizon and the close.
    """

    quote = index.current(int(stamp))
    if quote is None:
        return None
    bid, ask, _mid = quote
    if not (bid > 0 and ask > bid):
        return None
    cost = M.frozen_cost_usd(bid, ask, asset)
    spread = float(ask - bid) * float(index.multiplier) / 1e9
    out: dict[str, object] = {"cost_usd": float(cost), "spread_usd": spread}
    generation = index.generation_at_snapshot(int(stamp))
    for label in LABELS:
        close_ns = (int(phase_close_ns) if label == CLOSE else
                    int(min(int(stamp) + FIXHOLD_S * NANOS, int(phase_close_ns))))
        outcome = index.outcome(int(stamp), int(side), int(entry_mid2),
                                float(cost), close_ns, generation=generation)
        if outcome is None:
            return None
        out[f"{label}|cert"] = float(outcome.cert_close_usd)
        out[f"{label}|wall"] = bool(outcome.wall_hit)
        out[f"{label}|mae"] = float(outcome.mae_usd)
        out[f"{label}|mfe"] = float(outcome.mfe_usd)
        out[f"{label}|exit"] = int(outcome.exit_ts_ns)
    return out


def price_lane1(index: M.MillIndex, rec: S1.CellRec, cands: Sequence[Cand],
                positions: Sequence[int], counters: dict[str, int]
                ) -> list[Priced]:
    """Raw ticks decide the fill; the limit price IS the entry price."""

    out: list[Priced] = []
    if not len(positions):
        return out
    lat = np.asarray(rec.lat, np.int64)
    close_ns = int(rec.phase_close_ts_ns)
    arms = np.asarray([int(lat[cands[p].bar]) for p in positions], np.int64)
    ends = np.asarray([int(min(lat[cands[p].cancel_bar], close_ns))
                       for p in positions], np.int64)
    starts = np.searchsorted(index.ts, arms.astype(np.uint64), side="left")
    stops = np.searchsorted(index.ts, ends.astype(np.uint64), side="right")
    stops = np.minimum(stops, len(index.ts))
    thresholds = np.asarray([cands[p].limit_mid2 for p in positions], np.int64)
    sides = np.asarray([cands[p].fade_side for p in positions], np.int64)
    rows = np.full(len(positions), -1, np.int64)
    for side in (1, -1):
        pick = np.flatnonzero((sides == side) & (starts < stops))
        if not len(pick):
            continue
        # A long fade rests BELOW and fills on the first mid at or through it;
        # a short fade rests ABOVE.  Same monotone first-passage structure the
        # frozen mill uses for the -900 wall.
        rows[pick] = index.range.first_many(starts[pick], stops[pick],
                                            thresholds[pick],
                                            use_min=(side > 0))
    for local, position in enumerate(positions):
        cand = cands[position]
        counters["l1_armed"] += 1
        row = int(rows[local])
        if row < 0:
            counters["l1_no_fill"] += 1
            continue
        stamp = int(index.ts[row])
        priced = _price_entry(index, cand.asset, stamp, cand.fade_side,
                              int(cand.limit_mid2), close_ns)
        if priced is None:
            counters["l1_unpriceable"] += 1
            continue
        exit_bar = int(np.searchsorted(np.asarray(rec.lat, np.int64),
                                       int(priced[f"{CLOSE}|exit"]),
                                       side="right") - 1)
        out.append(Priced(
            lane="L1_PRETOUCH", position=int(position), asset=cand.asset,
            d8=cand.d8, phase=cand.phase, cell=cand.cell, bar=int(cand.bar),
            exit_bar=int(max(exit_bar, cand.bar)), side=int(cand.fade_side),
            entry_ts_ns=stamp, entry_mid2=int(cand.limit_mid2),
            cost_usd=float(priced["cost_usd"]),
            spread_usd=float(priced["spread_usd"]),
            cert={label: float(priced[f"{label}|cert"]) for label in LABELS},
            wall={label: bool(priced[f"{label}|wall"]) for label in LABELS},
            mae={label: float(priced[f"{label}|mae"]) for label in LABELS},
            mfe={label: float(priced[f"{label}|mfe"]) for label in LABELS},
            exit_ts={label: int(priced[f"{label}|exit"]) for label in LABELS}))
        counters["l1_filled"] += 1
    return out


def price_bar_entry(index: M.MillIndex, rec: S1.CellRec, lane: str,
                    position: int, cand: Cand | None, asset: str, d8: int,
                    phase: str, cell: int, bar: int, side: int,
                    counters: dict[str, int], tag: str) -> Priced | None:
    """A lattice-bar entry under the frozen entry law."""

    if not 0 <= bar < int(rec.n) - 1:
        counters[f"{tag}_out_of_range"] += 1
        return None
    if not bool(np.asarray(rec.bar_ok, bool)[bar]) or not rec.legal_at(side, bar):
        counters[f"{tag}_illegal"] += 1
        return None
    stamp = int(np.asarray(rec.lat, np.int64)[bar])
    entry_mid2 = int(np.asarray(rec.mid, np.int64)[bar])
    priced = _price_entry(index, asset, stamp, side, entry_mid2,
                          int(rec.phase_close_ts_ns))
    if priced is None:
        counters[f"{tag}_unpriceable"] += 1
        return None
    exit_bar = int(np.searchsorted(np.asarray(rec.lat, np.int64),
                                   int(priced[f"{CLOSE}|exit"]), side="right") - 1)
    counters[f"{tag}_priced"] += 1
    return Priced(
        lane=lane, position=int(position), asset=asset, d8=int(d8), phase=phase,
        cell=int(cell), bar=int(bar), exit_bar=int(max(exit_bar, bar)),
        side=int(side), entry_ts_ns=stamp, entry_mid2=entry_mid2,
        cost_usd=float(priced["cost_usd"]),
        spread_usd=float(priced["spread_usd"]),
        cert={label: float(priced[f"{label}|cert"]) for label in LABELS},
        wall={label: bool(priced[f"{label}|wall"]) for label in LABELS},
        mae={label: float(priced[f"{label}|mae"]) for label in LABELS},
        mfe={label: float(priced[f"{label}|mfe"]) for label in LABELS},
        exit_ts={label: int(priced[f"{label}|exit"]) for label in LABELS})


# --------------------------------------------------------------------------
# The chronological replay, the MDD ledgers and the two stresses.
# --------------------------------------------------------------------------

@dataclass(slots=True)
class Trade:
    asset: str
    d8: int
    cell: int
    bar: int
    exit_bar: int
    side: int
    entry_ts_ns: int
    exit_ts_ns: int
    entry_mid2: int
    cost_usd: float
    pnl_usd: float


def replay(entries: Sequence[Priced], label: str,
           overrides: Mapping[int, float] | None = None) -> dict[str, object]:
    """Fixhold section B, exactly: chronology, occupancy, portfolio-date cap."""

    events = sorted(range(len(entries)),
                    key=lambda i: (entries[i].entry_ts_ns, entries[i].asset,
                                   entries[i].cell, entries[i].bar,
                                   entries[i].side))
    occupied: dict[str, int] = {}
    seated_by_date: dict[int, int] = {}
    trades: list[Trade] = []
    rejected_occupancy = 0
    rejected_cap = 0
    for i in events:
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
        pnl = (float(overrides[i]) if overrides is not None and i in overrides
               else float(item.cert[label]))
        occupied[item.asset] = int(item.exit_ts[label])
        seated_by_date[int(item.d8)] = seated_by_date.get(int(item.d8), 0) + 1
        trades.append(Trade(
            asset=item.asset, d8=int(item.d8), cell=int(item.cell),
            bar=int(item.bar), exit_bar=int(item.exit_bar), side=int(item.side),
            entry_ts_ns=stamp, exit_ts_ns=int(item.exit_ts[label]),
            entry_mid2=int(item.entry_mid2), cost_usd=float(item.cost_usd),
            pnl_usd=pnl))
    return {"trades": trades, "rejected_occupancy": rejected_occupancy,
            "rejected_cap": rejected_cap, "seated": len(trades)}


def replay_cash(trades: Sequence[Trade],
                explore_days: Mapping[str, Sequence[int]]) -> dict[str, object]:
    out: dict[str, object] = {}
    for asset in ASSETS:
        days = sorted(int(day) for day in explore_days[asset])
        sums = {day: 0.0 for day in days}
        seats = {day: 0 for day in days}
        for trade in trades:
            if trade.asset != asset or int(trade.d8) not in sums:
                continue
            sums[int(trade.d8)] += float(trade.pnl_usd)
            seats[int(trade.d8)] += 1
        series = [sums[day] for day in days]
        counts = [seats[day] for day in days]
        mean, se = _mean_se(series)
        out[asset] = {
            "days": len(days), "trades": int(sum(counts)),
            "usd_per_day": mean, "se_usd": se,
            "mean_minus_2se_usd": (None if mean is None or se is None
                                   else mean - 2.0 * se),
            "rung_usd": DAY_RUNG_USD[asset],
            "clears_rung": (None if mean is None or se is None else
                            bool(mean >= DAY_RUNG_USD[asset]
                                 and mean - 2.0 * se >= DAY_RUNG_USD[asset])),
            "total_usd": float(sum(series)),
            "seats_mean": float(np.mean(counts)) if counts else 0.0,
            "seats_max": int(max(counts)) if counts else 0,
            "zero_entry_fraction": (float(np.mean([c == 0 for c in counts]))
                                    if counts else None)}
    per_date: dict[int, int] = {}
    for trade in trades:
        per_date[int(trade.d8)] = per_date.get(int(trade.d8), 0) + 1
    out["_portfolio"] = {
        "dates_with_entries": len(per_date),
        "portfolio_seats_max": int(max(per_date.values())) if per_date else 0,
        "at_cap_dates": int(sum(1 for v in per_date.values()
                                if v >= PORTFOLIO_CAP)),
        "cap_lawful": bool(all(v <= PORTFOLIO_CAP for v in per_date.values()))}
    return out


def mdd_ledgers(trades: Sequence[Trade],
                mid_by_cell: Mapping[int, np.ndarray],
                lat_by_cell: Mapping[int, np.ndarray],
                explore_days: Mapping[str, Sequence[int]]) -> dict[str, object]:
    """Fixhold section D: four ledgers, cumulative cash from zero."""

    out: dict[str, object] = {}
    ordered = sorted(trades, key=lambda t: (t.entry_ts_ns, t.exit_ts_ns,
                                            t.cell, t.bar, t.side))
    for asset in ASSETS:
        mine = [t for t in ordered if t.asset == asset]
        days = sorted(int(day) for day in explore_days[asset])
        sums = {day: 0.0 for day in days}
        for trade in mine:
            if int(trade.d8) in sums:
                sums[int(trade.d8)] += float(trade.pnl_usd)
        out[f"{asset}|trade"] = _drawdown([t.pnl_usd for t in mine])
        out[f"{asset}|day"] = _drawdown([sums[day] for day in days])
    out["PORTFOLIO|trade"] = _drawdown([t.pnl_usd for t in ordered])
    all_days = sorted({int(day) for asset in ASSETS for day in explore_days[asset]})
    port = {day: 0.0 for day in all_days}
    for trade in ordered:
        if int(trade.d8) in port:
            port[int(trade.d8)] += float(trade.pnl_usd)
    out["PORTFOLIO|day"] = _drawdown([port[day] for day in all_days])

    marks: list[tuple[int, int, float, bool]] = []
    factor = {asset: 0.5e-9 * float(M.ASSET_MULTIPLIER[asset]) for asset in ASSETS}
    for number, trade in enumerate(ordered):
        lat = lat_by_cell.get(trade.cell)
        mid = mid_by_cell.get(trade.cell)
        marks.append((int(trade.entry_ts_ns), number, -float(trade.cost_usd), False))
        if lat is not None and mid is not None:
            for bar in range(int(trade.bar) + 1, int(trade.exit_bar)):
                if bar >= len(lat) or bar >= len(mid):
                    break
                value = (trade.side * (float(mid[bar]) - float(trade.entry_mid2))
                         * factor[trade.asset] - float(trade.cost_usd))
                marks.append((int(lat[bar]), number, value, False))
        marks.append((int(trade.exit_ts_ns), number, float(trade.pnl_usd), True))
    marks.sort(key=lambda item: (item[0], 1 if item[3] else 0, item[1]))
    realized = 0.0
    open_marks: dict[int, float] = {}
    peak = 0.0
    worst = 0.0
    for _stamp, number, value, closing in marks:
        if closing:
            open_marks.pop(number, None)
            realized += value
        else:
            open_marks[number] = value
        equity = realized + sum(open_marks.values())
        peak = max(peak, equity)
        worst = max(worst, peak - equity)
    out["PORTFOLIO|event"] = float(worst)
    binding = ([f"{asset}|{grain}" for asset in DECIDING
                for grain in ("trade", "day")]
               + ["PORTFOLIO|trade", "PORTFOLIO|day", "PORTFOLIO|event"])
    out["binding_ledgers"] = binding
    out["max_binding_usd"] = float(max([out[key] for key in binding] or [0.0]))
    out["clears"] = bool(out["max_binding_usd"] < MDD_CEILING)
    return out


def stress_overrides(entries: Sequence[Priced], label: str, kind: str
                     ) -> dict[int, float]:
    """The two standing stresses, as overrides on the same replay."""

    out: dict[int, float] = {}
    if kind == "adversarial":
        # The worst 2 percent per asset take their own MAE as realized: the
        # adverse excursion they actually printed, not an invented number.
        for asset in ASSETS:
            picks = [i for i, e in enumerate(entries) if e.asset == asset]
            if not picks:
                continue
            target = int(round(STRESS_RATE * len(picks)))
            if target <= 0:
                continue
            damage = sorted(
                ((entries[i].cert[label] + entries[i].mae[label], i)
                 for i in picks), key=lambda item: (-item[0], item[1]))
            for _value, i in damage[:target]:
                out[i] = float(-entries[i].mae[label])
    elif kind == "spread":
        for i, entry in enumerate(entries):
            out[i] = float(entry.cert[label] - entry.spread_usd)
    else:
        raise SweepRefusal(f"unknown stress {kind!r}")
    return out


# --------------------------------------------------------------------------
# Measurement.
# --------------------------------------------------------------------------

def measure_line(entries: Sequence[Priced], label: str, asset: str,
                 days: Sequence[int], formed: int) -> dict[str, object]:
    mine = [e for e in entries if e.asset == asset]
    certs = [float(e.cert[label]) for e in mine]
    day_list = sorted(int(day) for day in days)
    sums = {day: 0.0 for day in day_list}
    for entry in mine:
        if int(entry.d8) in sums:
            sums[int(entry.d8)] += float(entry.cert[label])
    series = [sums[day] for day in day_list]
    mean, se = _mean_se(series)
    return {
        "n": len(mine), "formed": int(formed),
        "coverage": (float(len(mine) / formed) if formed else None),
        "mean_cert_usd": float(np.mean(certs)) if certs else None,
        "median_cert_usd": float(np.median(certs)) if certs else None,
        "p_cert_positive": _wilson(sum(1 for c in certs if c > 0), len(certs)),
        "usd_per_asset_day": mean, "se_usd": se,
        "mean_minus_2se_usd": (None if mean is None or se is None
                               else mean - 2.0 * se),
        "rung_usd": DAY_RUNG_USD[asset],
        "over_rung": (None if mean is None else mean / DAY_RUNG_USD[asset]),
        "total_usd": float(sum(certs)),
        "wall_rate": (float(np.mean([1.0 if e.wall[label] else 0.0
                                     for e in mine])) if mine else None),
        "mdd_day_usd": _drawdown(series),
        "days": len(day_list)}


def breakdowns(entries: Sequence[Priced], cands: Sequence[Cand], label: str
               ) -> dict[str, object]:
    out: dict[str, object] = {}
    for name, key in (("zone_type", lambda e: cands[e.position].zone_kind),
                      ("year", lambda e: str(cands[e.position].year)),
                      ("phase", lambda e: e.phase)):
        table: dict[str, list[float]] = {}
        for entry in entries:
            table.setdefault(str(key(entry)), []).append(float(entry.cert[label]))
        out[name] = {k: {"n": len(v), "mean_usd": float(np.mean(v)),
                         "total_usd": float(sum(v))}
                     for k, v in sorted(table.items())}
    return out


# --------------------------------------------------------------------------
# C1: the matched, level-permuted control and the shared-sign maxT.
# --------------------------------------------------------------------------

def match_controls(selected: Sequence[Priced], cands: Sequence[Cand],
                   pool: Mapping[tuple[str, int, str], list[dict[str, object]]],
                   impulse: np.ndarray, mag_bin: Mapping[int, int]
                   ) -> tuple[dict[int, dict[str, object]], dict[str, int]]:
    """One G1 control per selected event, matched on the five frozen keys."""

    counters = {"matched": 0, "no_pool": 0, "no_bin": 0}
    out: dict[int, dict[str, object]] = {}
    used: dict[tuple[str, int, str], set[int]] = {}
    for position, entry in enumerate(selected):
        cand = cands[entry.position]
        key = (cand.asset, cand.d8, cand.phase)
        rows = pool.get(key)
        if not rows:
            counters["no_pool"] += 1
            continue
        want_time = min(TIME_BINS - 1, int(TIME_BINS * cand.bar / max(cand.n_bars, 1)))
        want_mag = int(mag_bin.get(entry.position, 0))
        target = (float(impulse[entry.position])
                  if np.isfinite(impulse[entry.position]) else 0.0)
        taken = used.setdefault(key, set())
        best = None
        for row in rows:
            if int(row["time_bin"]) != want_time:
                continue
            if int(row["mag_bin"]) != want_mag:
                continue
            if int(row["row"]) in taken:
                continue
            gap = abs(float(row["impulse"]) - target)
            token = (gap, int(row["row"]))
            if best is None or token < best[0]:
                best = (token, row)
        if best is None:
            counters["no_bin"] += 1
            continue
        taken.add(int(best[1]["row"]))
        out[position] = best[1]
        counters["matched"] += 1
    return out, counters


def maxt_inference(lines: Mapping[str, dict[int, float]],
                   family: Sequence[str], draws: int = SIGN_DRAWS
                   ) -> dict[str, object]:
    """Shared-date-sign studentized maxT over the family, fixhold section A."""

    dates = sorted({d8 for series in lines.values() for d8 in series})
    if not dates:
        return {"draws": draws, "dates": 0, "c95": None, "by_line": {}}
    stacked = np.column_stack([
        np.asarray([lines[name].get(d8, 0.0) for d8 in dates], np.float64)
        for name in family]) if family else np.zeros((len(dates), 0))
    stats: dict[str, tuple[float, float, float, int]] = {}
    for name, series in lines.items():
        values = np.asarray([series.get(d8, 0.0) for d8 in dates], np.float64)
        mean = float(values.mean())
        se = (float(values.std(ddof=1) / math.sqrt(len(values)))
              if len(values) > 1 else 0.0)
        stats[name] = (mean, se, (mean / se) if se > 0 else 0.0, len(values))
    rng = np.random.default_rng(SEED + 61)
    maxima = np.zeros(draws, np.float64)
    if stacked.shape[1]:
        done = 0
        step = 500
        while done < draws:
            take = min(step, draws - done)
            signs = rng.choice(np.asarray([-1.0, 1.0]), size=(take, len(dates)))
            means = (signs @ stacked) / float(len(dates))
            sds = np.sqrt(((signs[:, :, None] * stacked[None, :, :]
                            - means[:, None, :]) ** 2).sum(axis=1)
                          / max(len(dates) - 1, 1))
            se_draw = sds / math.sqrt(len(dates))
            with np.errstate(divide="ignore", invalid="ignore"):
                t = np.where(se_draw > 0, means / se_draw, 0.0)
            maxima[done:done + take] = t.max(axis=1)
            done += take
    c95 = float(np.percentile(maxima, 95.0)) if stacked.shape[1] else None
    by_line: dict[str, object] = {}
    for name, (mean, se, t, count) in stats.items():
        eligible = name in family
        by_line[name] = {
            "eligible": eligible, "dates": count, "delta_usd_per_date": mean,
            "se_usd": se, "t": t,
            "p_max_adjusted": (float((1 + int((maxima >= t).sum())) / (draws + 1))
                               if eligible and stacked.shape[1] else None),
            "upper95_simultaneous_usd": (mean + c95 * se) if c95 is not None else None,
            "lower95_simultaneous_usd": (mean - c95 * se) if c95 is not None else None}
    return {"draws": draws, "dates": len(dates), "c95": c95,
            "family": list(family), "by_line": by_line}


def block_null(selected_positions: Sequence[int], cands: Sequence[Cand],
               eligible: Mapping[tuple[str, str, int], list[int]],
               cert_by_position: Mapping[int, float],
               days: Mapping[str, Sequence[int]], asset: str,
               draws: int = CONTROL_DRAWS) -> dict[str, object]:
    """C3: re-draw the same COUNT inside each (asset, phase, day) block."""

    day_list = sorted(int(day) for day in days[asset])
    counts: dict[tuple[str, str, int], int] = {}
    for position in selected_positions:
        cand = cands[position]
        if cand.asset != asset:
            continue
        counts[(cand.asset, cand.phase, cand.d8)] = counts.get(
            (cand.asset, cand.phase, cand.d8), 0) + 1
    if not counts:
        return {"draws": draws, "observed_usd_day": None, "p": None}
    observed = 0.0
    for position in selected_positions:
        if cands[position].asset == asset:
            observed += float(cert_by_position.get(position, 0.0))
    observed /= max(len(day_list), 1)
    rng = np.random.default_rng(SEED + 62)
    null = np.zeros(draws, np.float64)
    blocks = [(key, count, np.asarray(eligible.get(key, []), np.int64))
              for key, count in sorted(counts.items())]
    for draw in range(draws):
        total = 0.0
        for _key, count, pool in blocks:
            if not len(pool):
                continue
            take = rng.choice(pool, size=min(count, len(pool)), replace=False)
            total += float(sum(cert_by_position.get(int(p), 0.0) for p in take))
        null[draw] = total / max(len(day_list), 1)
    return {"draws": draws, "observed_usd_day": float(observed),
            "null_mean_usd_day": float(null.mean()),
            "null_p95_usd_day": float(np.percentile(null, 95.0)),
            "p": float((1 + int((null >= observed).sum())) / (draws + 1))}


# --------------------------------------------------------------------------
# The letters.
# --------------------------------------------------------------------------

def lane_letter(lane: str, report: Mapping[str, object]) -> dict[str, object]:
    live = report["live"][lane]                      # type: ignore[index]
    # Sol B's kill condition names "the formed ceiling", which is the ceiling of
    # the FORMED opportunity universe - not of the subset this selector picked.
    # Scoring the kill against the selected subset would let a selector that
    # picks nothing kill the formation rule on its own thinness.
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
    matched_positive = all(
        (control.get(f"{lane}|{asset}") or {}).get("delta_usd_per_date", 0.0) > 0.0
        for asset in DECIDING)
    upper_nonpositive = any(
        (control.get(f"{lane}|{asset}") or {}).get(
            "upper95_simultaneous_usd") is not None
        and float(control[f"{lane}|{asset}"]["upper95_simultaneous_usd"]) <= 0.0
        for asset in DECIDING)

    # Sol's three letters do not partition the space: a run whose formed ceiling
    # CARRIES both rungs, whose matched upper bounds are all positive, and whose
    # matched delta is negative on one deciding asset matches neither the
    # UNRESOLVED condition (which requires a positive delta) nor either KILL
    # clause.  That case falls through to KILL and the receipt names it, so a
    # reader can tell a registered kill from a fallthrough.
    clause = None
    if (rung_ok and mdd_ok and cap_ok and stress_ok and control_ok
            and neighbours_ok):
        letter = "LEVELCOLLISION-LIVE"
        clause = "all live bounds cleared"
    elif not ceiling_carries or upper_nonpositive:
        letter = "LEVELCOLLISION-KILL"
        if not ceiling_carries:
            clause = "registered: the formed ceiling misses a deciding rung"
            reasons.append("the formed ceiling misses a deciding rung")
        if upper_nonpositive:
            clause = ("registered: a powered deciding asset has a non-positive "
                      "95% upper bound against its matched control")
            reasons.append("a powered deciding asset has a non-positive 95% "
                           "upper bound against its matched control")
    elif ceiling_carries and matched_positive:
        letter = "LEVELCOLLISION-UNRESOLVED"
        clause = ("registered: the formed ceiling carries both rungs and the "
                  "matched delta is positive, but a live bound fails")
    else:
        letter = "LEVELCOLLISION-KILL"
        clause = ("FALLTHROUGH, not a registered clause: the formed ceiling "
                  "carries both rungs and no deciding upper bound is "
                  "non-positive, but the causal matched delta is not positive "
                  "on both deciding assets, so UNRESOLVED cannot be earned")
        reasons.append("the causal matched delta is not positive on both "
                       "deciding assets")
    return {"lane": lane, "letter": letter, "clause": clause,
            "reasons": reasons,
            "rung_ok": rung_ok, "mdd_ok": mdd_ok, "cap_ok": cap_ok,
            "stress_ok": stress_ok, "control_ok": control_ok,
            "neighbours_ok": neighbours_ok,
            "ceiling_carries_both_rungs": ceiling_carries,
            "matched_delta_positive": matched_positive}


# --------------------------------------------------------------------------
# The run.  One formation pass over the lattice, then one shard pass.
# --------------------------------------------------------------------------

def _sidecar(asset: str, d8: int) -> Mapping[str, object]:
    path = LV.LEVELS_ROOT / str(asset) / f"{int(d8)}.json"
    if not path.is_file():
        raise LV.LevelStop(f"levels sidecar is absent: {path}")
    return json.loads(path.read_text())


def formation_pass(cells: Sequence[S8.Cell8],
                   explore_days: Mapping[str, Sequence[int]], mutant: str
                   ) -> tuple[list[Cand], dict[str, object]]:
    """Every EXPLORE day, in order, with parameters from strictly prior days.

    Formation on day ``d`` reads only days strictly before ``d``: the zone width
    comes from prior cell ranges and the three lane parameters are quantiles of
    parameter-free statistics collected on prior candidates.  Nothing here opens
    a shard, so this whole pass is lattice plus level cache.
    """

    by_day: dict[tuple[str, int], list[S8.Cell8]] = {}
    for cell in cells:
        by_day.setdefault((cell.asset, int(cell.d8)), []).append(cell)
    counters = {"cells": 0, "cells_no_levels": 0, "cells_too_short": 0,
                "cells_zero_width": 0, "candidates": 0, "lane2_resolved": 0,
                "lane2_never_touched": 0, "lane2_unresolved": 0,
                "lane2_no_next_bar": 0, "days_formed": 0, "days_warmup": 0,
                "levels_missing_cell": 0}
    range_pool: dict[tuple[str, str], dict[int, list[float]]] = {}
    stat_pool: dict[tuple[str, str], dict[int, list[tuple[float, float, int]]]] = {}
    params_used: dict[str, dict[str, object]] = {}
    audit: list[dict[str, object]] = []
    audited_cells: set[int] = set()
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
                sidecar = _sidecar(asset, d8)
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
                params = lane_params(
                    ranges, [s[0] for s in stats], [s[1] for s in stats],
                    [s[2] for s in stats], len(prior))
                params_used.setdefault(f"{asset}|{cell.phase}", {})[str(d8)] = {
                    "mult_index": params.mult_index,
                    "width_atr": params.width_atr,
                    "depth_frac": params.depth_frac,
                    "epi_frac": params.epi_frac,
                    "cancel_bars": params.cancel_bars,
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
                                        params.mult_index, counters)
                lat = np.asarray(cell.rec.lat, np.int64)
                src = np.asarray(lcell.src_ts_ns, np.int64)
                for cand in fresh:
                    stat_pool.setdefault(stratum, {}).setdefault(d8, []).append(
                        (cand.pen_frac, cand.reach, cand.dur))
                    resolve_lanes(cand, mid, lcell, params.mult_index,
                                  deltas.get(int(cell.position)),
                                  params.depth_frac, params.epi_frac,
                                  params.cancel_bars, counters)
                    read_bar = (cand.close_bar if cand.close_bar >= 0
                                else cand.bar)
                    entry_bar = (cand.entry_bar if cand.entry_bar >= 0
                                 else cand.bar)
                    gap = int(src[read_bar]) - int(lat[entry_bar])
                    worst_gap = max(worst_gap, gap)
                    if (len(audit) < 10 and cand.entry_bar >= 0
                            and int(cell.position) not in audited_cells):
                        audited_cells.add(int(cell.position))
                        audit.append({
                            "asset": asset, "d8": int(d8), "phase": cell.phase,
                            "cell": int(cell.position), "zone": cand.zone_kind,
                            "approach_bar": int(cand.bar),
                            "close_bar": int(cand.close_bar),
                            "entry_bar": int(cand.entry_bar),
                            "source_ts_ns": int(src[read_bar]),
                            "entry_ts_ns": int(lat[entry_bar]),
                            "source_minus_stamp_ns": int(gap)})
                out.extend(fresh)
    return out, {"counters": counters, "flow_counters": flow_counters,
                 "params": params_used, "causality_rows": audit,
                 "max_src_minus_stamp_ns": int(worst_gap),
                 "strictly_prior": bool(worst_gap < 0)}


def pricing_pass(cands: Sequence[Cand], cells: Sequence[S8.Cell8],
                 streams: Sequence[S14.Stream], records: Sequence[S1.CellRec],
                 explore_days: Mapping[str, Sequence[int]], mutant: str
                 ) -> dict[str, object]:
    """One shard pass: the magnitude target, both lanes, the G1 control pool."""

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
                "l1_armed": 0, "l1_filled": 0, "l1_no_fill": 0,
                "l1_unpriceable": 0, "mag_rows": 0, "mag_dropped": 0,
                "g1_rows": 0}
    for tag in ("l2", "g1", "ceil"):
        for suffix in ("out_of_range", "illegal", "unpriceable", "priced"):
            counters[f"{tag}_{suffix}"] = 0
    mag: list[MagRow] = []
    lane1: dict[int, Priced] = {}
    lane2: dict[int, Priced] = {}
    g1_pool: dict[tuple[str, int, str], list[dict[str, object]]] = {}
    g1_priced: dict[int, Priced] = {}
    ceiling: dict[int, dict[str, object]] = {}
    mid_by_cell: dict[int, np.ndarray] = {}
    lat_by_cell: dict[int, np.ndarray] = {}
    cert_plane = S19.build_cert_plane(cells)
    plane_checks = {"compared": 0, "mismatched": 0, "worst_abs_usd": 0.0}

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
                        mag.append(MagRow(
                            asset=asset, d8=int(d8), cell=int(position),
                            row=int(occ.row), bar=int(occ.bar),
                            x=np.asarray(occ.x, np.float64),
                            absmove=float(move[local])))
                        counters["mag_rows"] += 1

                # ---- the G1 control pool: every occurrence in this cell ----
                stream = stream_by_cell.get(position)
                if stream is not None:
                    for occ in stream.occs:
                        priced = price_bar_entry(
                            index, rec, "G1", -1, None, asset, int(d8),
                            rec.phase, position, int(occ.bar), int(occ.side),
                            counters, "g1")
                        if priced is None:
                            continue
                        g1_priced[int(occ.row)] = priced
                        g1_pool.setdefault((asset, int(d8), rec.phase), []).append({
                            "row": int(occ.row), "bar": int(occ.bar),
                            "side": int(occ.side), "x": np.asarray(occ.x,
                                                                  np.float64),
                            "time_bin": min(TIME_BINS - 1,
                                            int(TIME_BINS * occ.bar
                                                / max(int(rec.n), 1))),
                            "impulse": float("nan"), "mag_bin": 0})
                        counters["g1_rows"] += 1

                # ---- lane 1 and lane 2 for this cell's candidates ---------
                mine = cand_by_cell.get(position, [])
                if not mine:
                    continue
                for entry in price_lane1(index, rec, cands, mine, counters):
                    lane1[int(entry.position)] = entry
                for local in mine:
                    cand = cands[local]
                    if cand.entry_bar < 0:
                        continue
                    priced = price_bar_entry(
                        index, rec, "L2_EPISODE", local, cand, asset, int(d8),
                        rec.phase, position, int(cand.entry_bar),
                        int(cand.exit_dir), counters, "l2")
                    if priced is None:
                        continue
                    lane2[local] = priced
                    reference = float(cert_plane.cert[
                        cert_plane.index[position],
                        0 if cand.exit_dir > 0 else 1, int(cand.entry_bar)])
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
                    priced = price_bar_entry(
                        index, rec, "CEILING", local, cand, asset, int(d8),
                        rec.phase, position, int(best[1]), int(best[2]),
                        counters, "ceil")
                    if priced is not None:
                        fixed = float(priced.cert[FIXED])
                    ceiling[local] = {"usd": float(best[0]), "bar": int(best[1]),
                                      "side": int(best[2]), "fixed_usd": fixed}
        finally:
            shard.close()
    return {"mag": mag, "lane1": lane1, "lane2": lane2, "g1_pool": g1_pool,
            "g1_priced": g1_priced, "ceiling": ceiling,
            "mid_by_cell": mid_by_cell, "lat_by_cell": lat_by_cell,
            "counters": counters, "coarse_counters": coarse_counters,
            "plane_checks": plane_checks}


def evaluate_lane(lane: str, entries: Sequence[Priced], cands: Sequence[Cand],
                  explore_days: Mapping[str, Sequence[int]],
                  formed: Mapping[str, int], label: str = CLOSE
                  ) -> dict[str, object]:
    """One selection's full priced picture under one label."""

    out: dict[str, object] = {"n": len(entries), "label": label}
    out["per_asset"] = {
        asset: {lbl: measure_line(entries, lbl, asset, explore_days[asset],
                                  formed.get(asset, 0))
                for lbl in LABELS} for asset in ASSETS}
    seated = replay(entries, label)
    out["replay"] = {"seated": seated["seated"],
                     "rejected_occupancy": seated["rejected_occupancy"],
                     "rejected_cap": seated["rejected_cap"]}
    out["cash"] = replay_cash(seated["trades"], explore_days)
    out["trades"] = seated["trades"]
    out["breakdowns"] = breakdowns(entries, cands, label)
    return out


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
    # The cache's own causal certificate: the worst per-bar (max source stamp
    # minus that bar's own lattice stamp) across every shard.  Strictly negative
    # or the barrier term is not causal and nothing below may be priced.
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
            f"a level read is not strictly prior to its entry stamp: "
            f"max(source - stamp) = {formation['max_src_minus_stamp_ns']} ns")

    priced = pricing_pass(cands, cells, streams, records, explore_days, mutant)
    if priced["plane_checks"]["mismatched"]:
        raise SweepRefusal(
            "a lane-2 close-label cert disagreed with the frozen cert plane at "
            f"the same (cell, side, bar): worst "
            f"{priced['plane_checks']['worst_abs_usd']:.6f} USD")

    folds, impulse_report = fit_impulse(priced["mag"], explore_days, mutant)
    # The impulse join: the last G1 occurrence in the candidate's own cell that
    # closed STRICTLY BEFORE the approach bar.  Its features are the frozen
    # 16-column plane; nothing is re-derived at an arbitrary bar.
    occ_by_cell: dict[int, list[S14.Occ]] = {}
    for stream in streams:
        occ_by_cell[int(stream.cell)] = sorted(stream.occs,
                                               key=lambda o: (o.bar, o.side, o.row))
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
    impulse, impulse_counters = impulse_scores(cands, folds)

    lane1 = priced["lane1"]
    lane2 = priced["lane2"]
    have = {"L1_PRETOUCH": lane1, "L2_EPISODE": lane2}
    formed_by_asset = {asset: sum(1 for c in cands if c.asset == asset)
                       for asset in ASSETS}
    formed_opportunities = {}
    for cand in cands:
        key = f"{cand.asset}|{cand.d8}"
        formed_opportunities[key] = formed_opportunities.get(key, 0) + 1

    scores: dict[str, list[Scored]] = {}
    score_reports: dict[str, object] = {}
    for lane in LANES:
        rows, report = score_selector(cands, lane, impulse, explore_days, mutant)
        scores[lane] = rows
        score_reports[lane] = {k: v for k, v in report.items() if k != "cuts"}
        score_reports[lane]["cut_sample"] = dict(
            list(report["cuts"].items())[:3])

    live: dict[str, object] = {}
    grid_report: dict[str, object] = {}
    selected_entries: dict[str, list[Priced]] = {}
    selected_positions: dict[str, list[int]] = {}
    for lane in LANES:
        pool = have[lane]
        by_cell = grid_report.setdefault(lane, {})
        for cut in GRID:
            picks = [row.position for row in scores[lane]
                     if row.selected.get(cut) and row.position in pool]
            entries = [pool[p] for p in picks]
            block = evaluate_lane(lane, entries, cands, explore_days,
                                  formed_by_asset)
            by_cell[f"{cut[0]}|{cut[1]}"] = {
                "n": block["n"],
                "cash": {asset: {
                    "usd_per_day": block["cash"][asset]["usd_per_day"],
                    "mean_minus_2se_usd": block["cash"][asset]["mean_minus_2se_usd"],
                    "clears_rung": block["cash"][asset]["clears_rung"]}
                    for asset in ASSETS}}
            if cut == LIVE_CELL:
                selected_entries[lane] = entries
                selected_positions[lane] = picks
                live[lane] = block

    # Neighbour agreement: the three non-registered cells must not flip the
    # sign of the deciding assets' usd/day.
    for lane in LANES:
        agree = True
        for asset in DECIDING:
            base = grid_report[lane][f"{LIVE_CELL[0]}|{LIVE_CELL[1]}"]["cash"][asset]["usd_per_day"]
            for cut in GRID:
                if cut == LIVE_CELL:
                    continue
                other = grid_report[lane][f"{cut[0]}|{cut[1]}"]["cash"][asset]["usd_per_day"]
                if base is None or other is None:
                    agree = False
                elif (base > 0) != (other > 0):
                    agree = False
        live[lane]["neighbours_agree"] = bool(agree)

    # ---- stresses on the registered cell ---------------------------------
    for lane in LANES:
        entries = selected_entries[lane]
        stress: dict[str, object] = {}
        for kind in ("adversarial", "spread"):
            overrides = stress_overrides(entries, CLOSE, kind)
            seated = replay(entries, CLOSE, overrides)
            stress[kind] = {
                "seated": seated["seated"],
                "cash": replay_cash(seated["trades"], explore_days),
                "mdd": mdd_ledgers(seated["trades"], priced["mid_by_cell"],
                                   priced["lat_by_cell"], explore_days)}
        live[lane]["stress"] = stress
        live[lane]["mdd"] = mdd_ledgers(live[lane]["trades"],
                                        priced["mid_by_cell"],
                                        priced["lat_by_cell"], explore_days)
        live[lane].pop("trades", None)

    # ---- C2: the formed ceiling ------------------------------------------
    ceiling_block: dict[str, object] = {}
    for lane in LANES:
        picks = selected_positions[lane]
        cash: dict[str, object] = {}
        for asset in ASSETS:
            day_list = sorted(int(d) for d in explore_days[asset])
            sums = {day: 0.0 for day in day_list}
            n = 0
            for position in picks:
                cand = cands[position]
                if cand.asset != asset:
                    continue
                best = priced["ceiling"].get(position)
                if best is None:
                    continue
                sums[int(cand.d8)] = sums.get(int(cand.d8), 0.0) + float(best["usd"])
                n += 1
            series = [sums[day] for day in day_list]
            mean, se = _mean_se(series)
            cash[asset] = {
                "n": n, "usd_per_day": mean, "se_usd": se,
                "rung_usd": DAY_RUNG_USD[asset],
                "over_rung": (None if mean is None
                              else mean / DAY_RUNG_USD[asset]),
                "carries_rung": (None if mean is None
                                 else bool(mean >= DAY_RUNG_USD[asset]))}
        ceiling_block[lane] = {"cash": cash,
                               "hindsight_bits": list(HINDSIGHT_CEILING)}
    # The whole formed universe's ceiling, not only the selected subset.
    all_cash: dict[str, object] = {}
    for asset in ASSETS:
        day_list = sorted(int(d) for d in explore_days[asset])
        sums = {day: 0.0 for day in day_list}
        n = 0
        for position, cand in enumerate(cands):
            if cand.asset != asset:
                continue
            best = priced["ceiling"].get(position)
            if best is None:
                continue
            sums[int(cand.d8)] = sums.get(int(cand.d8), 0.0) + float(best["usd"])
            n += 1
        series = [sums[day] for day in day_list]
        mean, _se = _mean_se(series)
        all_cash[asset] = {
            "n": n, "usd_per_day": mean, "rung_usd": DAY_RUNG_USD[asset],
            "over_rung": None if mean is None else mean / DAY_RUNG_USD[asset],
            "carries_rung": None if mean is None else bool(
                mean >= DAY_RUNG_USD[asset])}
    ceiling_block["FORMED_UNIVERSE"] = {"cash": all_cash,
                                        "hindsight_bits": list(HINDSIGHT_CEILING)}
    # The raw per-opportunity sum above is dominated by how many opportunities
    # the rule forms, not by what a book could hold.  This second ceiling keeps
    # only the 12 best events per PORTFOLIO date - the cap law, with occupancy
    # still unenforced - so it stays a strict upper bound on any lawful seating
    # while being comparable to a rung.  It spends one more hindsight bit:
    # which twelve.
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
        for row in rows:
            fold = folds.get((key[0], key[1]))
            if fold is None or row["x"] is None:
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
        entries = selected_entries[lane]
        mag_bin = {}
        for entry in entries:
            value = impulse[entry.position]
            mag_bin[entry.position] = int(
                np.searchsorted(edges, value)) if np.isfinite(value) else 0
        matched, counters = match_controls(entries, cands,
                                           priced["g1_pool"], impulse, mag_bin)
        control_counters[lane] = counters
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
            control_lines[f"{lane}|{asset}"] = series
        # The permutation diagnostic: give each matched control a level vector
        # drawn from a permutation inside the training fold and ask how often it
        # would have been selected.  A level-blind control should select at the
        # base rate, not at the selector's rate.
        pool_positions = [p for p in range(len(cands))]
        if pool_positions and matched:
            draw = rng.permutation(len(pool_positions))
            hits = 0
            for slot, position in enumerate(sorted(matched)):
                donor = cands[pool_positions[int(draw[slot % len(draw)])]]
                comp = barrier_components(donor, lane)
                hits += int(np.nanmean(comp) > 0.0)
            permuted_selected[lane] = {
                "n": len(matched),
                "share_permuted_positive_barrier": float(hits / max(len(matched), 1))}
    family = [f"{lane}|{asset}" for lane in LANES for asset in DECIDING]
    control = maxt_inference(control_lines, family)

    # ---- C3: block-permutation nulls on every headline --------------------
    eligible: dict[tuple[str, str, int], list[int]] = {}
    for position, cand in enumerate(cands):
        eligible.setdefault((cand.asset, cand.phase, cand.d8), []).append(position)
    nulls: dict[str, object] = {}
    for lane in LANES:
        pool = have[lane]
        cert_by_position = {p: float(pool[p].cert[CLOSE]) for p in pool}
        for asset in ASSETS:
            nulls[f"{lane}|{asset}"] = block_null(
                selected_positions[lane], cands, eligible, cert_by_position,
                explore_days, asset)

    # ---- lane extras: fill/cancel rates and the resolution direction split --
    direction: dict[str, dict[int, int]] = {}
    window: dict[str, dict[str, float]] = {}
    for entry in selected_entries["L2_EPISODE"]:
        cand = cands[entry.position]
        table = direction.setdefault(cand.asset, {1: 0, -1: 0})
        table[int(cand.exit_dir)] = table.get(int(cand.exit_dir), 0) + 1
        row = window.setdefault(cand.asset, {"n": 0, "touches": 0.0,
                                             "held": 0.0, "broke": 0.0,
                                             "flow": 0.0, "bars": 0.0,
                                             "range_atr": 0.0})
        row["n"] += 1
        row["touches"] += cand.touches
        row["held"] += cand.win_held
        row["broke"] += cand.win_broke
        row["flow"] += cand.win_flow
        row["bars"] += cand.win_bars
        row["range_atr"] += cand.win_range_atr
    for row in window.values():
        n = max(row["n"], 1)
        for key in ("touches", "held", "broke", "flow", "bars", "range_atr"):
            row[key] = float(row[key] / n)
        row["n"] = int(n)

    report: dict[str, object] = {
        "schema": "QRE2MILLSWEEP22", "spec_sha": SPEC_SHA,
        "code_sha": code_sha(), "split_sha": S1.split_sha(),
        "outcome_law_sha": S1.outcome_law_sha(), "seed": SEED,
        "mutant": mutant, "family": FAMILY, "parent_trial": PARENT_TRIAL,
        "selection_rule": SELECTION_RULE, "registered_utc": report_stamp(),
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
        "impulse": impulse_report, "impulse_join": join,
        "impulse_counters": impulse_counters,
        "selector": score_reports, "grid": grid_report, "live": live,
        "ceiling": ceiling_block, "control": control,
        "control_counters": control_counters,
        "control_permutation": permuted_selected,
        "block_nulls": nulls,
        "lane_extras": {"direction": direction, "window": window},
        "scoring_days": {a: scoring[a] for a in ASSETS},
        "elapsed_s": round(time.time() - started, 1)}
    letters = {lane: lane_letter(lane, report) for lane in LANES}
    if any(letters[lane]["letter"] == "LEVELCOLLISION-LIVE" for lane in LANES):
        family_letter = "LEVELCOLLISION-LIVE"
    elif any(letters[lane]["letter"] == "LEVELCOLLISION-UNRESOLVED"
             for lane in LANES):
        family_letter = "LEVELCOLLISION-UNRESOLVED"
    else:
        family_letter = "LEVELCOLLISION-KILL"
    report["letters"] = letters
    report["family_letter"] = family_letter
    report["headline"] = headline(report)
    return report


def headline(report: Mapping[str, object]) -> dict[str, object]:
    """Best lane's deciding usd/day over rung, then the formed ceiling beside it."""

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
    return {
        "best_lane": None if best is None else best[1],
        "best_lane_over_rung": {} if best is None else {
            asset: best[2][i] for i, asset in enumerate(DECIDING)},
        "formed_ceiling_over_rung": {asset: ceiling[asset]["over_rung"]
                                     for asset in DECIDING},
        "family_letter": report["family_letter"]}


# --------------------------------------------------------------------------
# Printing.
# --------------------------------------------------------------------------

def _n(value: object, width: int = 9, digits: int = 3) -> str:
    if value is None:
        return "-".rjust(width)
    if isinstance(value, bool):
        return ("yes" if value else "no").rjust(width)
    if isinstance(value, float):
        return f"{value:{width}.{digits}f}"
    return str(value).rjust(width)


def print_gate(report: Mapping[str, object]) -> None:
    repro = report["reproduction"]
    print("\n== GATE ==")
    print(f"  sweep 9 plane reproduces : {repro['matches']}")
    for key in ("rows", "certifiable", "counters", "scoring_days"):
        if key in repro:
            print(f"    {key:<14} {repro[key]}")
    stream = report["stream_counters"]
    print(f"  stream counters          : {stream}")
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
          f"{formation['strictly_prior']}, max(source - entry stamp) "
          f"{formation['max_src_minus_stamp_ns']} ns")
    print(f"  formation counters       : {formation['counters']}")
    print(f"  pricing counters         : {report['pricing_counters']}")
    checks = report["plane_checks"]
    print(f"  lane-2 vs frozen cert plane: compared {checks['compared']}, "
          f"mismatched {checks['mismatched']}, worst "
          f"{checks['worst_abs_usd']:.9f} USD")
    print(f"  impulse ridge            : {report['impulse']['counters']}, "
          f"WITHIN-DAY R2 (a harder denominator than sweep 20's pooled R2, "
          f"not a contradiction of it) "
          f"{report['impulse']['pooled_within_day_r2']}")
    print(f"  impulse join             : {report['impulse_join']}, "
          f"{report['impulse_counters']}")


def print_causality_rows(report: Mapping[str, object]) -> None:
    rows = report["formation"]["causality_rows"]
    print("\n== LANE-2 EPISODE CLOSE CAUSALITY, 10 real rows ==")
    print("  asset      d8 ph cell zone            appr close entry  "
          "source-minus-stamp_ns")
    worst = None
    for row in rows:
        gap = int(row["source_minus_stamp_ns"])
        worst = gap if worst is None else max(worst, gap)
        print(f"  {row['asset']:<5} {row['d8']} {row['phase']:>2} "
              f"{row['cell']:>4} {row['zone']:<15} {row['approach_bar']:>4} "
              f"{row['close_bar']:>5} {row['entry_bar']:>5}  {gap:>16d}")
    print(f"  max source-minus-stamp over these rows: {worst} ns "
          f"(must be strictly negative)")


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
    print("\n  fold-trained lane parameters, sample strata:")
    for stratum, table in report["formation_params_sample"].items():
        for d8, block in list(table.items())[-1:]:
            print(f"    {stratum:<8} {d8}  band x{block['width_atr']:.2f} ATR "
                  f"(mult index {block['mult_index']})  depth "
                  f"{block['depth_frac']:.3f}  episode band "
                  f"{block['epi_frac']:.2f} w  cancel {block['cancel_bars']} bars "
                  f"(train {block['train_days']} days / "
                  f"{block['train_cands']} candidates)")


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
            line = block["per_asset"][asset][label]
            cash = block["cash"][asset] if label == CLOSE else None
            wilson = line["p_cert_positive"]
            print(f"  {asset:<5} {label:<6} {line['n']:>5} "
                  f"{_n(line['coverage'], 6, 3)} {_n(wilson['rate'], 6, 3)} "
                  f"[{_n(wilson['lo'], 5, 2)},{_n(wilson['hi'], 5, 2)}] "
                  f"{_n(line['mean_cert_usd'], 9, 1)} "
                  f"{_n(line['median_cert_usd'], 8, 1)} "
                  f"{_n(line['usd_per_asset_day'], 11, 1)} "
                  f"{_n(line['over_rung'], 8, 3)} "
                  f"{_n(cash['usd_per_day'] if cash else None, 12, 1)} "
                  f"{_n(cash['mean_minus_2se_usd'] if cash else None, 10, 1)} "
                  f"{_n(line['mdd_day_usd'], 9, 1)}")
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


def print_lane_extras(report: Mapping[str, object],
                      extras: Mapping[str, object]) -> None:
    print("\n== LANE-1 FILL AND CANCEL RATES ==")
    counters = report["pricing_counters"]
    armed = int(counters["l1_armed"])
    print(f"  armed {armed}, filled {counters['l1_filled']}, cancelled unfilled "
          f"{counters['l1_no_fill']}, unpriceable {counters['l1_unpriceable']}")
    if armed:
        print(f"  fill rate {counters['l1_filled'] / armed:.4f}   "
              f"cancel rate {counters['l1_no_fill'] / armed:.4f}")
    print("\n== LANE-2 EPISODE RESOLUTION DIRECTION SPLIT ==")
    for asset in ASSETS:
        block = extras["direction"].get(asset, {})
        total = sum(block.values()) or 1
        print(f"  {asset:<5} up {block.get(1, 0):>5} "
              f"({block.get(1, 0) / total:.3f})   down {block.get(-1, 0):>5} "
              f"({block.get(-1, 0) / total:.3f})")
    print("\n  lane-2 window features at entry (recorded, NOT gating):")
    print("  asset   n  touches  held  broke   flow      bars  range/ATR")
    for asset in ASSETS:
        row = extras["window"].get(asset)
        if not row:
            continue
        print(f"  {asset:<5} {row['n']:>4} {_n(row['touches'], 7, 2)} "
              f"{_n(row['held'], 6, 2)} {_n(row['broke'], 6, 2)} "
              f"{_n(row['flow'], 9, 1)} {_n(row['bars'], 6, 1)} "
              f"{_n(row['range_atr'], 9, 3)}")


def print_grid(report: Mapping[str, object]) -> None:
    print("\n== SELECTOR SENSITIVITY GRID (barrier cut x margin cut) ==")
    print("  the registered LIVE cell is (tercile, median); the other three "
          "are its neighbours")
    for lane in LANES:
        print(f"  {lane}")
        print("    barrier  margin      n     NKD usd/day   NKD -2SE      "
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
          f"{control['dates']} dates, family {control['family']}, "
          f"c95 {_n(control['c95'], 7, 3)}")
    print("  line                 dates    delta/date       SE        t   "
          "max-p    upper95   lower95")
    for name, cell in sorted(control["by_line"].items()):
        print(f"  {name:<20} {cell['dates']:>5} "
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
    print("  line                observed usd/day   null mean    null p95      p")
    for name, cell in sorted(report["block_nulls"].items()):
        print(f"  {name:<20} {_n(cell['observed_usd_day'], 14, 1)} "
              f"{_n(cell.get('null_mean_usd_day'), 11, 1)} "
              f"{_n(cell.get('null_p95_usd_day'), 11, 1)} "
              f"{_n(cell.get('p'), 6, 4)}")


def print_decision(report: Mapping[str, object]) -> None:
    head = report["headline"]
    print("\n== DECISION TABLE ==")
    best = head["best_lane"]
    ratios = ", ".join(
        f"{asset} {_n(head['best_lane_over_rung'].get(asset), 6, 3)}x rung"
        for asset in DECIDING)
    ceiling = ", ".join(
        f"{asset} {_n(head['formed_ceiling_over_rung'].get(asset), 6, 3)}x rung"
        for asset in DECIDING)
    print(f"  BEST LANE {best}: {ratios}; formed ceiling beside it: {ceiling}")
    print("  lane            letter                    rung  MDD  cap  stress "
          " control  neighbours  ceiling  matched+")
    for lane in LANES:
        cell = report["letters"][lane]
        print(f"  {lane:<15} {cell['letter']:<25} {_n(cell['rung_ok'], 5)} "
              f"{_n(cell['mdd_ok'], 4)} {_n(cell['cap_ok'], 4)} "
              f"{_n(cell['stress_ok'], 6)} {_n(cell['control_ok'], 8)} "
              f"{_n(cell['neighbours_ok'], 11)} "
              f"{_n(cell['ceiling_carries_both_rungs'], 8)} "
              f"{_n(cell['matched_delta_positive'], 9)}")
        print(f"      clause: {cell['clause']}")
        for reason in cell["reasons"]:
            print(f"      - {reason}")
    print(f"\n  FAMILY LETTER: {report['family_letter']}")


# --------------------------------------------------------------------------
# Selftest and the red mutant.
# --------------------------------------------------------------------------

def _check(name: str, ok: bool, detail: str = "") -> tuple[str, bool, str]:
    return (name, bool(ok), detail)


def _plant_rec(mid_path: Sequence[float], asset: str = PLANT_ASSET,
               d8: int = 20220315, phase: str = "0") -> S1.CellRec:
    """A CellRec over a hand-built mid path, sweep 21's construction."""

    mid = np.asarray([int(round(v)) for v in mid_path], np.int64)
    n = len(mid)
    lat = (np.arange(n, dtype=np.int64) * S1.BAR_NS
           + 1_600_000_000_000_000_000)
    scale = S7A.usd_to_mid2(asset)
    travel = (mid[-1] - mid).astype(np.float64) / scale
    zeros = np.zeros(n, np.int64)
    return S1.CellRec(
        asset=asset, d8=int(d8), phase=phase, text="PLANT",
        phase_open_ts_ns=int(lat[0]), phase_close_ts_ns=int(lat[-1]),
        locked_iid=0, pack_sha256="", raw_first=0, k0=0,
        r0_mid2=float(mid[0]), legal_from_p=1, legal_from_m=1,
        lat=lat, mid=mid, bar_ok=np.ones(n, bool), cost=np.zeros(n, np.float64),
        cert_p=travel, cert_m=-travel,
        ok_p=np.ones(n, bool), ok_m=np.ones(n, bool),
        wall_p=np.zeros(n, bool), wall_m=np.zeros(n, bool),
        exit_p=np.full(n, int(lat[-1]), np.int64),
        exit_m=np.full(n, int(lat[-1]), np.int64),
        cum_long=zeros, cum_short=zeros, raw_cut=zeros, raw_last=zeros)


class _PlantCell:
    """The Cell8 surface ``form_candidates`` reads, over a planted record."""

    __slots__ = ("position", "asset", "d8", "phase", "n", "rec", "atr_mid2")

    def __init__(self, rec: S1.CellRec, atr_mid2: float, position: int = 0):
        self.position = position
        self.asset = rec.asset
        self.d8 = rec.d8
        self.phase = rec.phase
        self.n = rec.n
        self.rec = rec
        self.atr_mid2 = float(atr_mid2)


def _plant_levels(mid: np.ndarray, atr: float, mult_index: int,
                  held_at: float | None, broke_at: float | None,
                  width: float) -> LV.LevelCell:
    """A LevelCell whose defence columns are planted, everything else zero.

    ``held_at`` is a price whose same-day pair says DEFENDED (held 3, broke 0);
    ``broke_at`` says UNDEFENDED (held 0, broke 3).  Every other column is zero
    or NaN-free, so the barrier score is exactly the planted contrast.
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
                if held_at is not None and abs(price - held_at) <= width:
                    plane[bar, LV.LEVEL_INDEX["sd_touches"]] = 3.0
                    plane[bar, LV.LEVEL_INDEX["sd_held"]] = 3.0
                if broke_at is not None and abs(price - broke_at) <= width:
                    plane[bar, LV.LEVEL_INDEX["sd_touches"]] = 3.0
                    plane[bar, LV.LEVEL_INDEX["sd_broke"]] = 3.0
            planes[(side, index)] = plane
    return LV.LevelCell(
        asset=PLANT_ASSET, d8=20220315, phase="0",
        phase_open_ts_ns=0, phase_close_ts_ns=0, bars=n, atr_mid2=float(atr),
        tick2=1.0, prior_d8=20220314, prev_sess_d8=20220311,
        value_lo=float("nan"), value_hi=float("nan"),
        src_ts_ns=np.arange(n, dtype=np.int64), planes=planes)


def _collision_world() -> dict[str, object]:
    """The planted collision: a defended zone that holds, an undefended one that
    breaks, and a third zone that is approached but never touched.

    Prices are in mid2; ATR is 100 units, so at band multiplier 0.10 the zone
    half-width is 10.  Every bar below is arithmetic, not a fitted number.
    """

    atr = 100.0
    width = 0.10 * atr                                   # 10
    defended = 1000.0                                    # holds the fade
    undefended = 1400.0                                  # breaks upward
    untouched = 2000.0                                   # approached, never met

    # 0-3 approach the defended zone from below, 4-6 touch it, 7-12 reject away.
    path = [940.0, 960.0, 985.0, 995.0, 1002.0, 1006.0, 998.0, 975.0, 950.0,
            925.0, 905.0, 890.0, 880.0]
    # 13-19 travel up to the undefended zone and go straight through it.
    path += [960.0, 1100.0, 1250.0, 1340.0, 1385.0, 1396.0, 1404.0]
    # 20-25 keep going: the break resolves the episode UPWARD.
    path += [1440.0, 1470.0, 1500.0, 1530.0, 1560.0, 1590.0]
    # 26-30 approach the untouched zone from below: price enters the OUTER band
    # (1980..2020) but never the zone band itself (1990..2010), so the episode
    # has no touch and lane 2 must refuse it.
    path += [1900.0, 1955.0, 1982.0, 1985.0, 1988.0]
    # 31-35 fall away again so the run ends cleanly.
    path += [1900.0, 1850.0, 1800.0, 1750.0, 1700.0]
    return {"atr": atr, "width": width, "defended": defended,
            "undefended": undefended, "untouched": untouched,
            "path": np.asarray(path, np.float64)}


def _selftest_formation() -> list[tuple[str, bool, str]]:
    world = _collision_world()
    rec = _plant_rec(world["path"])
    cell = _PlantCell(rec, world["atr"])
    mid = np.asarray(rec.mid, np.float64)
    lcell = _plant_levels(mid, world["atr"], 0, world["defended"],
                          world["undefended"], world["width"])
    sidecar = {"pd_high": world["defended"], "pd_low": 0.0,
               "pd_close": world["undefended"], "value_hi": world["untouched"],
               "value_lo": 0.0}
    counters = {"cells_too_short": 0, "cells_zero_width": 0, "candidates": 0}
    cands = form_candidates(cell, lcell, sidecar, 0, counters)
    out = [_check("formation forms candidates", len(cands) >= 3,
                  f"{len(cands)} candidates")]

    by_zone = {}
    for cand in cands:
        by_zone.setdefault(round(cand.zone_price), []).append(cand)
    out.append(_check("the defended zone forms a candidate",
                      round(world["defended"]) in by_zone,
                      f"zones {sorted(by_zone)}"))
    out.append(_check("the undefended zone forms a candidate",
                      round(world["undefended"]) in by_zone,
                      f"zones {sorted(by_zone)}"))
    out.append(_check("the never-touched zone forms a candidate",
                      round(world["untouched"]) in by_zone,
                      f"zones {sorted(by_zone)}"))

    counters2 = {"lane2_resolved": 0, "lane2_never_touched": 0,
                 "lane2_unresolved": 0, "lane2_no_next_bar": 0}
    for cand in cands:
        resolve_lanes(cand, mid, lcell, 0, None, 0.5, 2.0, 12, counters2)
    defended_cand = by_zone[round(world["defended"])][0]
    undefended_cand = by_zone[round(world["undefended"])][0]
    untouched_cand = by_zone[round(world["untouched"])][0]

    out.append(_check(
        "a zone approached but never touched forms NO lane-2 entry",
        untouched_cand.entry_bar < 0 and untouched_cand.touches == 0,
        f"entry_bar {untouched_cand.entry_bar}, touches "
        f"{untouched_cand.touches}, counter "
        f"{counters2['lane2_never_touched']}"))
    out.append(_check(
        "the undefended zone's episode resolves in the BREAK direction",
        undefended_cand.entry_bar >= 0 and undefended_cand.exit_dir == 1,
        f"entry_bar {undefended_cand.entry_bar}, dir "
        f"{undefended_cand.exit_dir}"))
    out.append(_check(
        "the defended zone's episode resolves AWAY from the fade side",
        defended_cand.entry_bar >= 0 and defended_cand.exit_dir == -1,
        f"entry_bar {defended_cand.entry_bar}, dir {defended_cand.exit_dir}"))
    out.append(_check(
        "the episode close strictly precedes the lane-2 entry stamp",
        all(c.close_bar < c.entry_bar for c in cands if c.entry_bar >= 0),
        "; ".join(f"{c.close_bar}<{c.entry_bar}" for c in cands
                  if c.entry_bar >= 0)))

    # The barrier score sees the planted contrast: defended high, undefended low.
    b_def = float(np.nanmean(barrier_components(defended_cand, "L1_PRETOUCH")))
    b_und = float(np.nanmean(barrier_components(undefended_cand, "L1_PRETOUCH")))
    out.append(_check("the selector's barrier ranks defended above undefended",
                      b_def > b_und, f"defended {b_def:.3f} vs undefended "
                                     f"{b_und:.3f}"))
    return out


def _selftest_fill() -> list[tuple[str, bool, str]]:
    """A hand-computed lane-1 fill that respects tick-path ordering."""

    world = _collision_world()
    rec = _plant_rec(world["path"])
    # Ticks one nanosecond BEFORE each bar stamp plus one tick inside the bar
    # that spikes THROUGH the limit and comes back.  A minute-close reader would
    # never see the spike; a tick reader must.
    lat = np.asarray(rec.lat, np.int64)
    mid = np.asarray(rec.mid, np.int64)
    ts: list[int] = []
    values: list[int] = []
    for bar in range(len(lat)):
        ts.append(int(lat[bar]) - 1)
        values.append(int(mid[bar]))
        if bar == 3:
            # the intraminute spike to 1004, above the limit, then away
            ts.append(int(lat[bar]) + 10)
            values.append(1004)
    order = np.argsort(np.asarray(ts, np.int64), kind="stable")
    ts_array = np.asarray(ts, np.int64)[order]
    mid_array = np.asarray(values, np.int64)[order] * 2
    bid = mid_array // 2 - 1
    ask = mid_array // 2 + 1
    generation = np.zeros(len(ts_array), np.uint32)
    index = M.MillIndex(PLANT_ASSET, ts_array, mid_array, bid, ask, generation,
                        ts_array, generation)

    # Arm a SHORT fade at 1002 (mid2 2004) from bar 3, cancel after 2 bars.
    cand = Cand(asset=PLANT_ASSET, d8=20220315, phase="0", cell=0, year=2022,
                zone_kind="PD_HIGH", zone_price=2000.0, width=20.0,
                atr_mid2=200.0, approach_side=1, fade_side=-1, bar=3,
                n_bars=len(lat), pen_frac=0.5, reach=1.0, dur=5,
                lev_approach=np.zeros(LV.NLEV), pd_held=1.0, pd_broke=0.0)
    cand.limit_mid2 = 2004
    cand.cancel_bar = 5
    counters = {"l1_armed": 0, "l1_filled": 0, "l1_no_fill": 0,
                "l1_unpriceable": 0}
    filled = price_lane1(index, rec, [cand], [0], counters)
    hit = bool(filled)
    stamp = int(filled[0].entry_ts_ns) if hit else -1
    out = [_check("the lane-1 limit fills on the intraminute tick, not the bar",
                  hit and stamp == int(lat[3]) + 10,
                  f"filled {hit}, stamp {stamp}, spike stamp "
                  f"{int(lat[3]) + 10}")]
    out.append(_check("the entry price IS the limit price on fill",
                      hit and int(filled[0].entry_mid2) == 2004,
                      f"entry_mid2 {filled[0].entry_mid2 if hit else None}"))
    # Hand-computed cert: short from 2004, exit at the phase close mid 1760.
    if hit:
        factor = 0.5e-9 * float(M.ASSET_MULTIPLIER[PLANT_ASSET])
        exit_mid = int(mid_array[-1])
        want = -1 * (exit_mid - 2004) * factor - float(filled[0].cost_usd)
        got = float(filled[0].cert[CLOSE])
        out.append(_check("the hand-computed lane-1 cert matches the frozen law",
                          abs(want - got) < 1e-6,
                          f"hand {want:.6f} vs law {got:.6f}"))
    else:
        out.append(_check("the hand-computed lane-1 cert matches the frozen law",
                          False, "no fill"))

    # The cancel law: arm the same limit but cancel BEFORE the spike.
    cand2 = Cand(**{f.name: getattr(cand, f.name)
                    for f in Cand.__dataclass_fields__.values()})
    cand2.cancel_bar = 3
    counters2 = {"l1_armed": 0, "l1_filled": 0, "l1_no_fill": 0,
                 "l1_unpriceable": 0}
    none = price_lane1(index, rec, [cand2], [0], counters2)
    out.append(_check("a limit cancelled before the spike does not fill",
                      not none and counters2["l1_no_fill"] == 1,
                      f"filled {len(none)}, no_fill {counters2['l1_no_fill']}"))
    return out


def _planted_selector(rows: int = 900, seed: int = SEED
                      ) -> tuple[list[Cand], np.ndarray, dict[str, list[int]]]:
    """A world where high barrier pays and the permuted control does not."""

    rng = np.random.default_rng(seed)
    days = [20220100 + d for d in range(60)]
    cands: list[Cand] = []
    payoff: list[float] = []
    for d8 in days:
        for k in range(rows // len(days)):
            strong = (k % 3 == 0)
            lev = np.zeros(LV.NLEV, np.float64)
            lev[LV.LEVEL_INDEX["sd_held"]] = 4.0 if strong else 0.0
            lev[LV.LEVEL_INDEX["sd_broke"]] = 0.0 if strong else 4.0
            lev[LV.LEVEL_INDEX["ps_held"]] = 2.0 if strong else 0.0
            lev[LV.LEVEL_INDEX["ps_broke"]] = 0.0 if strong else 2.0
            cand = Cand(asset="NKD", d8=int(d8), phase="0", cell=int(d8),
                        year=2022, zone_kind="PD_HIGH", zone_price=100.0,
                        width=1.0, atr_mid2=10.0, approach_side=1,
                        fade_side=-1, bar=10 + k, n_bars=200, pen_frac=0.5,
                        reach=1.0, dur=5, lev_approach=lev,
                        pd_held=1.0 if strong else 0.0, pd_broke=0.0)
            cand.x = np.zeros(NFEAT, np.float64)
            cands.append(cand)
            payoff.append(400.0 + float(rng.normal(0, 20)) if strong
                          else -120.0 + float(rng.normal(0, 20)))
    return cands, np.asarray(payoff, np.float64), {"NKD": days}


def _selftest_selector(mutant: str) -> list[tuple[str, bool, str]]:
    cands, payoff, days = _planted_selector()
    impulse = np.zeros(len(cands), np.float64)
    rows, _report = score_selector(cands, "L1_PRETOUCH", impulse, days, mutant)
    picked = [r.position for r in rows if r.selected[LIVE_CELL]]
    recovered = float(np.mean([payoff[p] for p in picked])) if picked else 0.0
    base = float(np.mean(payoff))
    out = [_check("the selector recovers the planted defended rows",
                  len(picked) > 0 and recovered > base + 200.0,
                  f"{len(picked)} picked, mean {recovered:.1f} vs base "
                  f"{base:.1f}")]
    strong = [p for p in picked
              if cands[p].lev_approach[LV.LEVEL_INDEX["sd_held"]] > 0]
    out.append(_check("every selected row is a high-barrier row",
                      picked and len(strong) == len(picked),
                      f"{len(strong)}/{len(picked)} strong"))
    # The permuted control: level memory shuffled across rows kills the signal.
    rng = np.random.default_rng(SEED + 7)
    shuffled = list(cands)
    order = rng.permutation(len(cands))
    permuted = []
    for slot, cand in enumerate(shuffled):
        clone = Cand(**{f.name: getattr(cand, f.name)
                        for f in Cand.__dataclass_fields__.values()})
        donor = cands[int(order[slot])]
        clone.lev_approach = donor.lev_approach
        clone.pd_held = donor.pd_held
        permuted.append(clone)
    rows_c, _r = score_selector(permuted, "L1_PRETOUCH", impulse, days, mutant)
    picked_c = [r.position for r in rows_c if r.selected[LIVE_CELL]]
    control_mean = (float(np.mean([payoff[p] for p in picked_c]))
                    if picked_c else 0.0)
    out.append(_check("the permuted control does NOT recover the planted rows",
                      abs(control_mean - base) < 120.0,
                      f"control mean {control_mean:.1f} vs base {base:.1f}"))
    out += _selftest_leak(mutant)
    return out


def _planted_leak() -> tuple[list[Cand], np.ndarray, dict[str, list[int]]]:
    """A world whose only paying structure lives on the SCORING day itself.

    Twenty-five training days carry two candidates each, all at the same barrier
    value, so the training fold's top-tercile cut is uninformative.  The scoring
    day then carries two hundred candidates whose barrier runs 0..9, and only
    those at 7 and above pay.  A lawful cut, learned from days strictly before,
    admits almost the whole scoring day and recovers nothing.  A cut that folds
    the scoring day in is DOMINATED by that day - 200 rows against 50 - so it
    lands near the day's own top tercile and picks the payers.  The gap between
    those two answers is exactly the leak the guard exists to prevent.
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
            approach_side=1, fade_side=-1, bar=int(bar), n_bars=400,
            pen_frac=0.5, reach=1.0, dur=5, lev_approach=lev,
            pd_held=0.0, pd_broke=0.0))
        payoff.append(400.0 if pays else -120.0)

    for d8 in days[:25]:
        for k in range(2):
            make(d8, 1.0, False, 10 + k)
    for k in range(200):
        held = float(k % 10)
        make(days[25], held, held >= 7.0, 10 + k)
    return cands, np.asarray(payoff, np.float64), {"SI": days}


def _selftest_leak(mutant: str) -> list[tuple[str, bool, str]]:
    cands, payoff, days = _planted_leak()
    impulse = np.zeros(len(cands), np.float64)
    rows, _report = score_selector(cands, "L1_PRETOUCH", impulse, days, mutant)
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


def _selftest_replay() -> list[tuple[str, bool, str]]:
    """Occupancy, the exits-before-entries seam and the portfolio cap."""

    def entry(asset: str, d8: int, stamp: int, exit_ts: int, pnl: float,
              bar: int = 1) -> Priced:
        return Priced(lane="L1_PRETOUCH", position=0, asset=asset, d8=d8,
                      phase="0", cell=bar, bar=bar, exit_bar=bar + 1, side=1,
                      entry_ts_ns=stamp, entry_mid2=0, cost_usd=0.0,
                      spread_usd=1.0,
                      cert={CLOSE: pnl, FIXED: pnl},
                      wall={CLOSE: False, FIXED: False},
                      mae={CLOSE: 10.0, FIXED: 10.0},
                      mfe={CLOSE: 0.0, FIXED: 0.0},
                      exit_ts={CLOSE: exit_ts, FIXED: exit_ts})

    overlap = [entry("NKD", 20220101, 100, 300, 10.0, 1),
               entry("NKD", 20220101, 200, 400, 20.0, 2)]
    result = replay(overlap, CLOSE)
    out = [_check("occupancy blocks a second entry while the asset is open",
                  result["seated"] == 1 and result["rejected_occupancy"] == 1,
                  f"seated {result['seated']}, rejected "
                  f"{result['rejected_occupancy']}")]
    seam = [entry("NKD", 20220101, 100, 200, 10.0, 1),
            entry("NKD", 20220101, 200, 300, 20.0, 2)]
    result = replay(seam, CLOSE)
    out.append(_check("an exit at t frees the seat for an entry at t",
                      result["seated"] == 2,
                      f"seated {result['seated']}"))
    cap = [entry("NKD" if i % 2 else "SI", 20220101, 100 * i, 100 * i + 1,
                 1.0, i + 1) for i in range(1, 20)]
    result = replay(cap, CLOSE)
    out.append(_check("the portfolio cap holds at 12 seats per date",
                      result["seated"] == PORTFOLIO_CAP
                      and result["rejected_cap"] > 0,
                      f"seated {result['seated']}, rejected_cap "
                      f"{result['rejected_cap']}"))
    trades = replay(seam, CLOSE)["trades"]
    ledgers = mdd_ledgers(trades, {}, {}, {"NKD": [20220101], "HG": [],
                                           "SI": []})
    out.append(_check("the MDD ledger law returns every binding ledger",
                      set(ledgers["binding_ledgers"]) <= set(ledgers),
                      f"{ledgers['binding_ledgers']}"))
    losses = [entry("NKD", 20220101, 100, 150, 50.0, 1),
              entry("NKD", 20220101, 200, 250, -400.0, 2)]
    trades = replay(losses, CLOSE)["trades"]
    ledgers = mdd_ledgers(trades, {}, {}, {"NKD": [20220101], "HG": [],
                                           "SI": []})
    out.append(_check("a 400 USD give-back is a 400 USD trade drawdown",
                      abs(ledgers["NKD|trade"] - 400.0) < 1e-9,
                      f"{ledgers['NKD|trade']}"))
    return out


def _selftest_letters() -> list[tuple[str, bool, str]]:
    """The pre-registered letters fire on hand-built receipts."""

    def receipt(usd: float, mdd: float, p: float, ceiling: float,
                delta: float) -> dict[str, object]:
        cash = {asset: {"usd_per_day": usd,
                        "mean_minus_2se_usd": usd - 10.0,
                        "clears_rung": usd - 10.0 >= DAY_RUNG_USD[asset]}
                for asset in ASSETS}
        cash["_portfolio"] = {"cap_lawful": True}
        stress = {kind: {"mdd": {"clears": mdd < MDD_CEILING}}
                  for kind in ("adversarial", "spread")}
        return {
            "live": {"L1_PRETOUCH": {
                "cash": cash, "mdd": {"clears": mdd < MDD_CEILING,
                                      "max_binding_usd": mdd},
                "stress": stress, "neighbours_agree": True}},
            "ceiling": {"FORMED_UNIVERSE": {"cash": {
                asset: {"carries_rung": ceiling >= DAY_RUNG_USD[asset]}
                for asset in ASSETS}}},
            "control": {"by_line": {
                f"L1_PRETOUCH|{asset}": {
                    "p_max_adjusted": p, "delta_usd_per_date": delta,
                    "upper95_simultaneous_usd": delta + 50.0}
                for asset in ASSETS}}}

    out = [_check("a clean receipt is LIVE",
                  lane_letter("L1_PRETOUCH",
                              receipt(3000.0, 100.0, 0.01, 5000.0, 300.0)
                              )["letter"] == "LEVELCOLLISION-LIVE")]
    out.append(_check(
        "a ceiling that misses a rung is KILL",
        lane_letter("L1_PRETOUCH", receipt(100.0, 100.0, 0.01, 10.0, 300.0)
                    )["letter"] == "LEVELCOLLISION-KILL"))
    out.append(_check(
        "a rich ceiling with a positive delta but a failed bound is UNRESOLVED",
        lane_letter("L1_PRETOUCH", receipt(100.0, 100.0, 0.01, 5000.0, 300.0)
                    )["letter"] == "LEVELCOLLISION-UNRESOLVED"))
    out.append(_check(
        "a breached MDD cannot be LIVE",
        lane_letter("L1_PRETOUCH", receipt(3000.0, 5000.0, 0.01, 5000.0, 300.0)
                    )["letter"] != "LEVELCOLLISION-LIVE"))
    return out


def _selftest_stress() -> list[tuple[str, bool, str]]:
    entry = Priced(lane="L1_PRETOUCH", position=0, asset="NKD", d8=20220101,
                   phase="0", cell=1, bar=1, exit_bar=2, side=1,
                   entry_ts_ns=100, entry_mid2=0, cost_usd=7.0, spread_usd=2.0,
                   cert={CLOSE: 50.0, FIXED: 50.0},
                   wall={CLOSE: False, FIXED: False},
                   mae={CLOSE: 30.0, FIXED: 30.0},
                   mfe={CLOSE: 60.0, FIXED: 60.0},
                   exit_ts={CLOSE: 200, FIXED: 200})
    spread = stress_overrides([entry], CLOSE, "spread")
    out = [_check("the doubled-spread stress charges the spread once more",
                  abs(spread[0] - 48.0) < 1e-9, f"{spread.get(0)}")]
    many = [entry] * 100
    adverse = stress_overrides(many, CLOSE, "adversarial")
    out.append(_check("the 2 percent adversarial stress hits 2 of 100 entries",
                      len(adverse) == 2, f"{len(adverse)} overridden"))
    out.append(_check("an adversarial entry realizes its own MAE",
                      all(abs(v + 30.0) < 1e-9 for v in adverse.values()),
                      f"{sorted(set(adverse.values()))}"))
    return out


def selftest() -> int:
    mutant = _mutant()
    results: list[tuple[str, bool, str]] = []
    results += _selftest_formation()
    results += _selftest_fill()
    results += _selftest_selector(mutant)
    results += _selftest_replay()
    results += _selftest_letters()
    results += _selftest_stress()
    print(f"sweep 22 selftest  mutant={mutant or 'none'}")
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

def _show(value: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def log_rows(report: Mapping[str, object]) -> list[dict[str, object]]:
    params = json.dumps({
        "lanes": list(LANES), "labels": list(LABELS),
        "q_zone": Q_ZONE, "outer_step": OUTER_STEP, "q_depth": Q_DEPTH,
        "q_epi": Q_EPI, "q_cancel": Q_CANCEL,
        "max_episode_bars": MAX_EPISODE_BARS,
        "barrier_cuts": BARRIER_CUTS, "margin_cuts": MARGIN_CUTS,
        "live_cell": list(LIVE_CELL), "impulse_horizon_s": IMPULSE_HORIZON_S,
        "min_prior_days": MIN_PRIOR_DAYS, "portfolio_cap": PORTFOLIO_CAP,
        "sign_draws": SIGN_DRAWS, "control_draws": CONTROL_DRAWS,
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
                letter = report["letters"][lane]["letter"]
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
                    f"{lane} ({LANE_NAME[lane]}), label {label}, {asset}: "
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
                f"selector sensitivity, {lane}, barrier cut {cut[0]} x margin "
                f"cut {cut[1]}: n {cell['n']}; " + "; ".join(
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
            f"C1 paired matched control, {lane}, {asset}: selected minus "
            f"control {_show(cell['delta_usd_per_date'])} usd per asset-day "
            f"over {cell['dates']} dates, SE {_show(cell['se_usd'])}, t "
            f"{_show(cell['t'])}, shared-date-sign max-stat p "
            f"{_show(cell['p_max_adjusted'])} over "
            f"{len(report['control']['family'])} lines, simultaneous 95% "
            f"[{_show(cell['lower95_simultaneous_usd'])}, "
            f"{_show(cell['upper95_simultaneous_usd'])}]"
            f"{'' if cell['eligible'] else '; HG report-only'}")
        rows.append(line)

    # 4. C2, the formed ceiling
    for scope in list(LANES) + ["FORMED_UNIVERSE", "FORMED_CAPPED"]:
        counter += 1
        cash = report["ceiling"][scope]["cash"]
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
            + f"; EXPLORATORY, hindsight bits {len(HINDSIGHT_CEILING)} "
              f"({'; '.join(HINDSIGHT_CEILING)})")
        rows.append(line)

    # 5. the letters
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
            f"{cell['ceiling_carries_both_rungs']}, matched delta positive "
            f"{cell['matched_delta_positive']}; CLAUSE {cell['clause']}"
            + ("; " + "; ".join(cell["reasons"]) if cell["reasons"] else ""))
        rows.append(line)
    counter += 1
    line = blank(dict(shared))
    line["id"] = f"{LOG_PREFIX}-{counter:03d}"
    line["rule"] = "F19-LEVELCOLLISION/family"
    line["days"] = len(report["scoring_days"]["NKD"])
    head = report["headline"]
    line["note"] = (
        f"FAMILY LETTER {report['family_letter']}; best lane "
        f"{head['best_lane']} at " + ", ".join(
            f"{asset} {_show(head['best_lane_over_rung'].get(asset))}x rung"
            for asset in DECIDING)
        + "; formed ceiling beside it " + ", ".join(
            f"{asset} {_show(head['formed_ceiling_over_rung'].get(asset))}x rung"
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
    print_gate(report)
    print_causality_rows(report)
    print_formation(report)
    for lane in LANES:
        print_lane(report, lane)
    print_lane_extras(report, report["lane_extras"])
    print_grid(report)
    print_controls(report)
    print_decision(report)
    write_report(report)
    print(f"\nreport: {OUT_PATH}")
    if args.log:
        rows = log_rows(report)
        written = S1.append_log(rows)
        print(f"log: appended {written} rows to {LOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
