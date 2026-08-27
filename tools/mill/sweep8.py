#!/usr/bin/env python3
"""Sweep 8 of the side-resolution mill: the survival-gated fade.

Exploratory tier.  EXPLORE-day bytes only, can kill, cannot promote.  Zero fit:
no weights, no supervised training, no swept knob.  Every number the gate reads
is a walk-forward empirical percentile inside an ``(asset, phase)`` stratum
calibrated on strictly-prior EXPLORE days, so the only free choices are the
ones the charter froze before any of this ran.

The charter is ``.audit/briefs/mill-side-resolution.md``, sections "Sweep 8
frozen pre-7b" (the gate law), "Sweep 7b verdict and the sweep-8 amendments"
(the two amendments this file obeys) and "Sweep 7a verdict and the survival
reframe" (post-entry extension is the primary no-cash metric).

Machinery is imported, never re-implemented: sweep 1's ``CellRec`` cache,
``Entry``/``make_entry`` law, ``cash_line``, ``asset_mdd_day``/
``asset_mdd_trade`` (the engine's ``_drawdown``), ``replay_line``,
``block_null``, ``wilson`` and ``append_log``; sweep 2's ``star_cell`` Delta*
and its REM suffix max; sweep 3's adversarial ``stress_line``; sweep 7a's zone
geometry (running extremes, new-extreme flags, terminal bar, the CLEAR
candidate plane); sweep 7b's bleed-bucket law and its budget table; the mill
context store for ``ATR14_prev``; ``mill_flow`` for the tape series and
``mill_flow_zones`` for the zone episodes and touches.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
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
import context as CTX
import flow as FLOW
import flow_zones as ZONES
import sweep1 as S1
import sweep2 as S2
import sweep3 as S3
import sweep4 as S4
import sweep7a as S7A
import sweep7b as S7B

# --------------------------------------------------------------------------
# The law, registered before anything is read.
# --------------------------------------------------------------------------

SPEC = """QRE2MILLSWEEP8
tier=exploratory; explore-only; can kill, cannot promote.  parent = the
  hypothesis-log tail at registration.  Charter: mill-side-resolution.md
  "Sweep 8 frozen pre-7b" as amended by "Sweep 7b verdict and the sweep-8
  amendments".  No fit of any kind: no weights, no swept knob, no selection
  over variants.  Every threshold below was frozen before the run.
GATE, per (cell, side), evaluated at completed 60 s bars once the side's last
  new extreme is at least 5 bars old and the bar is tradeable.  Five evidences,
  each an empirical percentile inside the (asset, phase) stratum, calibrated on
  EXPLORE days strictly before the scoring day, minimum 20 prior days; a cell
  in a stratum with fewer prior days is UNSCORED and counts as an abstain.
  Percentile is the plain empirical CDF, mean(sample <= value); every component
  is oriented larger = safer.
    E1 quiet age, against the stratum's same-side extreme-interarrival gaps.
    E2 tape die-off: 1 - percentile of the last 10 bars' sum of
       (quote_events + vol) restricted to this side's in-zone bars, against
       this side's own COMPLETED episode history in this cell; when the cell
       has no completed episode yet, against the stratum's episode
       distribution.  Missing when neither sample exists.
    E3 one-sidedness |delta|/vol of the last zone-touch bar, banked at the
       touch and read one-shot, against the stratum's touch distribution.
       Missing until a touch exists.
    E4 interarrival stretch: current gap divided by the median completed
       same-side gap so far in this cell, against the stratum's ratio
       distribution.  MISSING until three completed gaps exist.
    E5 opposite-side extreme recency: 1 - percentile of the opposite side's
       extreme age, so a MORE RECENT opposite extreme scores higher.
  G = mean of the components present; at least 4 of 5 must be present or the
  bar does not score.  FIRE when G >= the stratum's 60th percentile of G over
  strictly-prior scored days (frozen, never swept) AND the phase has at least
  1800 s of remaining time.  There is NO lateness cap (amendment one).
  Both sides are monitored on the same bars; the first fire wins the cell.  A
  new same-side extreme resets that side's state; a new opposite-side extreme
  between the fire and the entry cancels the pending entry and re-arms.
ENTRY, one per cell.  PRIMARY (amendment two): the first fade-side CLEAR
  candidate at or after the fire bar whose decision quote sits within
  0.15 * ATR14_prev of the faded extreme, abstaining when no such candidate
  appears within 15 bars of the fire.  CONTROL: the first fade-side CLEAR
  candidate at or after the fire bar regardless of depth.  Entries are
  candidate-anchored through sweep 1's make_entry, so cert, wall and exit come
  from the cached outcome lattice and nothing is re-derived.
STAGE A, no cash, per asset and per phase, for PRIMARY and CONTROL: coverage
  over scored cells, entries, post-entry extension rate (a new same-direction
  extreme strictly after the entry bar and before phase close - the primary
  metric), soft hit (REM > 0 at the entry bar), side agreement against
  sign(Delta*) (diagnostic only), delay from the faded side's TRUE terminal
  extreme (median, p90, and the share fired before that terminal), depth
  achieved in ATR units, candidate wait, and the miss branches
  (unscored / no_fire / no_candidate_in_depth / cancelled / no_candidate).
  Comparisons: sweep 7a's first-quiet line, imported from
  .audit/mill-sweep7a.json and never recomputed, and a random-timing control
  drawing a uniform eligible (side, bar) in each scored cell under the same
  entry law, 50 seeded draws.
STAGE B, cash, PRIMARY and CONTROL per asset: cash/day against the rungs
  (NKD 1500 and SI 1500 deciding, HG 2000 report-only), per trade, win rate,
  wall rate, MDD day-ordered and trade-ordered, sweep 7b's bleed-bucket table
  recomputed on THIS policy's entries with the SOFT-WRONG/IN-BUDGET loss share
  and wall rate printed beside 7b's own baselines, engine replay (partial-day
  label), 2% adversarial stress, and the asset-day block-permutation null,
  200 draws at seed 20260827, max-statistic adjusted across the priced lines.
DECISION, pre-registered.  Keep-to-price is satisfied by having run stage B.
  FREEZE-CANDIDATE only if a deciding asset posts usd/day >= its rung with
  both MDD orderings below 1000, stress held (stressed usd/day >= 0), and an
  adjusted null p <= 0.05.  INTERESTING if post-entry extension <= 0.25 at
  coverage >= 0.35 with cash/day > 0 and a SOFT-WRONG/IN-BUDGET loss share
  below 0.40.  KILL otherwise, with every fired bound listed.
MUTANT QRE2_MILL_S8_MUTANT=gate_peeks_forward folds the scoring day's own
  contributions into the calibration sample before the day is scored, which is
  exactly the walk-forward violation the whole gate rests on.
"""

ASSETS = S1.ASSETS
BAR_SECONDS = S1.BAR_SECONDS
SEED = S1.SEED
NULL_DRAWS = S1.NULL_DRAWS
DAY_RUNG_USD = S1.DAY_RUNG_USD

# Frozen gate constants.  Every one of these is in the charter text above; none
# is swept, and no alternative value is ever evaluated in this file.
QUIET_MIN_BARS = 5              # the side's extreme must be >= 5 min old
TAPE_WINDOW_BARS = 10           # E2's "last 10 min"
DEPTH_ATR = 0.15                # amendment two's depth band
DEPTH_WINDOW_BARS = 15          # abstain if no in-depth candidate within 15 min
REMAIN_MIN_S = 1800             # the only time law left after amendment one
MIN_PRIOR_DAYS = 20             # calibration floor
G_PERCENTILE = 60.0             # the frozen fire bar
MIN_COMPONENTS = 4              # >= 4 of 5 evidences present
E4_MIN_GAPS = 3                 # E4 is missing until three gaps exist
RANDOM_DRAWS = 50
STRESS_RATE = S3.STRESS_RATE    # 0.02

COVERAGE_FLOOR = 0.35
POSTX_CEILING = 0.25
MDD_CEILING = 1000.0
NULL_CEILING = 0.05
SWIB_SHARE_CEILING = 0.40

COMPONENTS = ("E1", "E2", "E3", "E4", "E5")
LINES = ("PRIMARY", "CONTROL")

# The judging law adopted after this sweep was dispatched (charter section "Sol
# co-ideation adopted: the sweep-8 judging law and both branches").  postX on an
# open-ended window is censored by whatever phase time happens to be left, so a
# gate that merely fires LATE scores well without detecting anything.  The fixed
# 1800 s horizon, stamped at the FIRE, is the object that separates a survival
# detector from a clock; the two extra controls are what it must beat.
HORIZON_BARS = REMAIN_MIN_S // BAR_SECONDS          # 30 bars of 60 s
GATE_CONTROLS = ("E1ONLY", "PHASEMATCH")
CREDIT_MARGIN = 0.05
PHASE_MATCH_WINDOW_S = 300

# --- Sweep 8b: the E1-ONLY gate priced -------------------------------------
# Sweep 8's credit test computed an E1-ONLY firing law as a control and found it
# posts roughly half the composite's fixed-horizon extension.  It was never
# priced.  8b takes that same firing law - E1 alone against its own walk-forward
# stratum 60th percentile - as the POLICY, under both entry laws.  One knob
# changes from sweep 8: which score fires.  Everything else (time floor,
# cancellation, one entry per cell, seed, entry laws) is identical.
LINES_8B = ("E1PRIMARY", "E1CONTROL")
NULL_LINES_8B = tuple(LINES) + LINES_8B          # max-stat across four lines
FAMILY_8B = "F5-E1GATE"
PARENT_8B = "sweep8-006"
INTERESTING_USD_DAY_8B = 300.0
INTERESTING_MDD_DAY_8B = 5000.0

MISS_UNSCORED = "unscored"
MISS_NO_FIRE = "no_fire"
MISS_NO_CANDIDATE = "no_candidate"
MISS_NO_DEPTH = "no_candidate_in_depth"
MISS_CANCELLED = "cancelled"
MISS_BRANCHES = (MISS_UNSCORED, MISS_NO_FIRE, MISS_NO_CANDIDATE,
                 MISS_NO_DEPTH, MISS_CANCELLED)

# Sweep 7b's measured baseline, quoted so the SWIB comparison prints beside the
# thing it is meant to shrink.  Read from its report at run time, never typed.
SWEEP7A_PATH = ROOT / ".audit/mill-sweep7a.json"
SWEEP7B_PATH = ROOT / ".audit/mill-sweep7b.json"
OUT_PATH = ROOT / ".audit/mill-sweep8.json"
LOG_PATH = S1.LOG_PATH

MUTANT_ENV = "QRE2_MILL_S8_MUTANT"
MUTANT_PEEK = "gate_peeks_forward"
MUTANTS = (MUTANT_PEEK,)

FAMILY = "F5-SURVGATE"
SELECTION_RULE = "none: frozen gate, pre-registered entry law and reading"


class SweepRefusal(RuntimeError):
    pass


SPEC_SHA = S1._sha_text(SPEC)


def code_sha() -> str:
    return S1._sha_file(Path(__file__).resolve())


def _mutant() -> str:
    name = os.environ.get(MUTANT_ENV, "")
    if name and name not in MUTANTS:
        raise SweepRefusal(f"unknown sweep-8 mutant: {name}")
    return name


def _parent_trial() -> str:
    """The hypothesis log's tail id: the chain this sweep hangs off."""

    rows = [line for line in LOG_PATH.read_text().splitlines()[1:] if line.strip()]
    return rows[-1].split("\t")[0] if rows else "sweep7b-006"


# --------------------------------------------------------------------------
# The percentile primitives.  Pure, so the selftest can hand-compute them.
# --------------------------------------------------------------------------

def ecdf(value: float, sample: Sequence[float]) -> float | None:
    """Plain empirical CDF: the share of the sample at or below ``value``."""

    array = np.asarray(list(sample), np.float64)
    array = array[np.isfinite(array)]
    if not len(array) or not np.isfinite(value):
        return None
    return float(np.count_nonzero(array <= float(value)) / len(array))


def ecdf_sorted(value: float, ordered: np.ndarray) -> float | None:
    """:func:`ecdf` against a pre-sorted sample, by binary search.

    The stratum samples reach tens of thousands of values and every bar of
    every cell queries five of them, so the linear form is too slow to run the
    corpus.  A selftest case pins the two readings together.
    """

    if not len(ordered) or not np.isfinite(value):
        return None
    return float(np.searchsorted(ordered, float(value), side="right") / len(ordered))


def _invert(percentile: float | None) -> float | None:
    """``1 - p``: the orientation flip for the two die-off components."""

    return None if percentile is None else float(1.0 - percentile)


def combine(components: Mapping[str, float | None]) -> tuple[float | None, int]:
    """``(G, present)``: the mean of the present evidences under the 4-of-5 law."""

    present = [float(components[name]) for name in COMPONENTS
               if components.get(name) is not None]
    if len(present) < MIN_COMPONENTS:
        return None, len(present)
    return float(sum(present) / len(present)), len(present)


def fires(g_value: float | None, g_sample: Sequence[float],
          remaining_s: float) -> bool:
    """The frozen fire law: G at or above the stratum bar, and time left."""

    if g_value is None or float(remaining_s) < REMAIN_MIN_S:
        return False
    array = np.asarray(list(g_sample), np.float64)
    if not len(array):
        return False
    return bool(float(g_value) >= float(np.percentile(array, G_PERCENTILE)))


def depth_atr(mid_value: float, extreme_value: float, atr_mid2: float) -> float:
    """Distance from the faded extreme in ATR units at the decision quote."""

    if not atr_mid2 > 0.0:
        return float("inf")
    return abs(float(mid_value) - float(extreme_value)) / float(atr_mid2)


# --------------------------------------------------------------------------
# Per-cell evidence series.
# --------------------------------------------------------------------------

@dataclass(slots=True)
class SideEvidence:
    """Every raw (un-percentiled) evidence series for one cell, one side."""

    side: int
    quiet_age: np.ndarray          # bars since this side's last new extreme
    opp_age: np.ndarray            # bars since the OPPOSITE side's last extreme
    tape10: np.ndarray             # last-10-bar in-zone (quote_events + vol)
    onesided: np.ndarray           # |delta|/vol at the banked last touch
    gap_ratio: np.ndarray          # current gap / median completed gap so far
    gaps_done: np.ndarray          # completed same-side gaps so far
    epi_tape: list[list[float]]    # per bar: this cell's completed episode sums
    eligible: np.ndarray           # quiet age law + tradeable bar
    remaining_s: np.ndarray        # phase close minus the bar's own stamp


@dataclass(slots=True)
class Cell8:
    """One cell: sweep-1 record, sweep-7a geometry, Delta*, and the evidence."""

    position: int
    asset: str
    d8: int
    phase: str
    n: int
    rec: S1.CellRec
    geo: S7A.Geo
    star: S2.Star
    atr_mid2: float
    sides: dict[int, SideEvidence]


def _last_true_index(flags: np.ndarray) -> np.ndarray:
    """Index of the most recent True at or before each bar, 0 before any."""

    order = np.arange(len(flags), dtype=np.int64)
    return np.maximum.accumulate(np.where(np.asarray(flags, bool), order, 0))


def _running_median_ratio(marks: np.ndarray, quiet_age: np.ndarray, bars: int
                          ) -> tuple[np.ndarray, np.ndarray]:
    """``(gap ratio, completed gaps)`` per bar from the extreme-mark positions.

    A gap is COMPLETED only once both of its endpoints have printed, so the
    median a bar reads never contains the gap the bar is currently inside.
    """

    ratio = np.full(bars, np.nan, np.float64)
    done = np.zeros(bars, np.int64)
    if len(marks) < 2:
        return ratio, done
    gaps = np.diff(marks).astype(np.float64)
    for position in range(1, len(marks)):
        start = int(marks[position])
        stop = int(marks[position + 1]) if position + 1 < len(marks) else bars
        history = gaps[:position]
        done[start:stop] = len(history)
        median = float(np.median(history))
        if median > 0.0:
            ratio[start:stop] = quiet_age[start:stop] / median
    return ratio, done


def _episode_tape(spans: np.ndarray, qv: np.ndarray, bars: int
                  ) -> list[list[float]]:
    """Per bar, the tape sums of this side's episodes that CLOSED before it."""

    out: list[list[float]] = [[] for _ in range(bars)]
    closed: list[tuple[int, float]] = []
    for row in spans:
        start, end = int(row[0]), int(row[1])
        window = qv[max(start, end + 1 - TAPE_WINDOW_BARS): end + 1]
        closed.append((end, float(window.sum()) if len(window) else 0.0))
    closed.sort()
    running: list[float] = []
    cursor = 0
    for bar in range(bars):
        while cursor < len(closed) and closed[cursor][0] < bar:
            running.append(closed[cursor][1])
            cursor += 1
        out[bar] = list(running)
    return out


def side_evidence(rec: S1.CellRec, geo: S7A.Geo, side: int,
                  qv: np.ndarray, delta: np.ndarray, vol: np.ndarray,
                  zside: ZONES.ZoneSide) -> SideEvidence:
    """Every raw evidence series for one side of one cell."""

    bars = rec.n
    _prior, new_ext, _armed = S7A.side_arrays(geo, side)
    _oprior, opp_new, _oarmed = S7A.side_arrays(geo, -side)
    order = np.arange(bars, dtype=np.int64)
    quiet_age = (order - _last_true_index(new_ext)).astype(np.float64)
    opp_age = (order - _last_true_index(opp_new)).astype(np.float64)

    in_zone = np.asarray(zside.series["in_zone"], bool)[:bars]
    masked = np.where(in_zone, qv[:bars], 0.0)
    cumulative = np.concatenate(([0.0], np.cumsum(masked)))
    lower = np.maximum(order + 1 - TAPE_WINDOW_BARS, 0)
    tape10 = cumulative[order + 1] - cumulative[lower]

    # E3 is BANKED: the value is stamped at the touch bar and read unchanged
    # until the next touch replaces it, which is what "one-shot license" means.
    touch_bar = np.asarray(zside.series["last_touch_bar"], np.int64)[:bars]
    onesided = np.full(bars, np.nan, np.float64)
    have = touch_bar >= 0
    if bool(have.any()):
        picks = touch_bar[have]
        volume = vol[picks]
        stamped = np.where(volume > 0.0, np.abs(delta[picks]) / np.maximum(volume, 1e-12),
                           np.nan)
        onesided[have] = stamped

    marks = np.flatnonzero(new_ext)
    gap_ratio, gaps_done = _running_median_ratio(marks, quiet_age, bars)
    epi_tape = _episode_tape(zside.episodes[:, :2] if len(zside.episodes)
                             else np.zeros((0, 2)), masked, bars)

    stamps = np.asarray(rec.lat, np.int64)[:bars]
    remaining = (int(rec.phase_close_ts_ns) - stamps) / float(NANOS_PER_SECOND)
    eligible = (quiet_age >= QUIET_MIN_BARS) & np.asarray(rec.bar_ok, bool)[:bars]
    return SideEvidence(int(side), quiet_age, opp_age, tape10, onesided,
                        gap_ratio, gaps_done, epi_tape, eligible,
                        remaining.astype(np.float64))


def build_cells(assets: Sequence[str]) -> tuple[list[Cell8], dict[str, int],
                                                dict[str, int]]:
    """Every EXPLORE cell that carries an ATR prior and a flow/zones shard."""

    records, days = S1.load_cache()
    records = [rec for rec in records if rec.asset in assets]
    store = CTX.ContextStore()
    cells: list[Cell8] = []
    skipped: dict[str, int] = {asset: 0 for asset in assets}
    cache: dict[tuple[str, int], tuple[dict, dict]] = {}
    for position, rec in enumerate(records):
        payload = store.context_for(rec.asset, rec.d8)
        priors = payload.get("priors")
        if priors is None or str(priors.get("atr14_present", "0")) != "1":
            skipped[rec.asset] += 1
            continue
        atr_usd = float(priors["atr14_prev_usd"])
        if not atr_usd > 0.0:
            skipped[rec.asset] += 1
            continue
        atr_mid2 = atr_usd * S7A.usd_to_mid2(rec.asset)
        key = (rec.asset, rec.d8)
        if key not in cache:
            cache[key] = (FLOW.load_flow(rec.asset, rec.d8),
                          ZONES.load_zones(rec.asset, rec.d8))
        flow_day, zones_day = cache[key]
        cell_key = (rec.phase, int(rec.phase_open_ts_ns))
        if cell_key not in flow_day or cell_key not in zones_day:
            skipped[rec.asset] += 1
            continue
        bars = flow_day[cell_key]["vol"]
        if len(bars) < rec.n:
            skipped[rec.asset] += 1
            continue
        qv = (np.asarray(flow_day[cell_key]["quote_events"], np.float64)
              + np.asarray(flow_day[cell_key]["vol"], np.float64))[:rec.n]
        delta = np.asarray(flow_day[cell_key]["delta"], np.float64)[:rec.n]
        vol = np.asarray(flow_day[cell_key]["vol"], np.float64)[:rec.n]
        geo = S7A.geometry(rec, atr_mid2)
        star = S2.star_cell(rec, S7A.W_VARIANT, S7A.W_BAND)
        zcell = zones_day[cell_key]
        sides = {side: side_evidence(rec, geo, side, qv, delta, vol,
                                     zcell.sides[side]) for side in (1, -1)}
        cells.append(Cell8(position, rec.asset, int(rec.d8), rec.phase, rec.n,
                           rec, geo, star, float(atr_mid2), sides))
    return cells, {k: int(v) for k, v in days.items() if k in assets}, skipped


# --------------------------------------------------------------------------
# The walk-forward calibration store.
# --------------------------------------------------------------------------

@dataclass(slots=True)
class Stratum:
    """One (asset, phase) stratum's prior-day samples and its pending day."""

    prior: dict[str, list[float]] = field(
        default_factory=lambda: {name: [] for name in
                                 ("gap", "epi", "touch", "ratio", "oppage",
                                  "G", "E1")})
    pending: dict[str, list[float]] = field(
        default_factory=lambda: {name: [] for name in
                                 ("gap", "epi", "touch", "ratio", "oppage",
                                  "G", "E1")})
    prior_days: int = 0
    ordered: dict[str, np.ndarray] = field(default_factory=dict)

    def flush(self) -> None:
        for name, values in self.pending.items():
            self.prior[name].extend(values)
            values.clear()
        self.prior_days += 1
        self.ordered.clear()

    def sample(self, name: str) -> np.ndarray:
        """The prior sample, sorted once per day and reused by every query."""

        cached = self.ordered.get(name)
        if cached is None:
            array = np.asarray(self.prior[name], np.float64)
            cached = np.sort(array[np.isfinite(array)])
            self.ordered[name] = cached
        return cached


def contributions(cell: Cell8) -> dict[str, list[float]]:
    """What one cell adds to its stratum once the day is finished with."""

    out: dict[str, list[float]] = {name: [] for name in
                                   ("gap", "epi", "touch", "ratio", "oppage")}
    for side in (1, -1):
        ev = cell.sides[side]
        _prior, new_ext, _armed = S7A.side_arrays(cell.geo, side)
        marks = np.flatnonzero(new_ext)
        if len(marks) > 1:
            out["gap"].extend(float(value) for value in np.diff(marks))
        zone_sums = ev.epi_tape[cell.n - 1] if cell.n else []
        out["epi"].extend(float(value) for value in zone_sums)
        touches = ev.onesided[np.isfinite(ev.onesided)]
        # Only the DISTINCT banked values, so a long hold of one touch does not
        # dominate the stratum's touch distribution.
        if len(touches):
            keep = np.concatenate(([True], touches[1:] != touches[:-1]))
            out["touch"].extend(float(value) for value in touches[keep])
        pick = ev.eligible
        ratios = ev.gap_ratio[pick]
        out["ratio"].extend(float(value) for value in ratios[np.isfinite(ratios)])
        out["oppage"].extend(float(value) for value in ev.opp_age[pick])
    return out


def score_bar(cell: Cell8, side: int, bar: int, stratum: Stratum
              ) -> tuple[float | None, int, dict[str, float | None]]:
    """The five evidences and G at one (cell, side, bar), or ``None``."""

    ev = cell.sides[side]
    parts: dict[str, float | None] = {name: None for name in COMPONENTS}
    parts["E1"] = ecdf_sorted(float(ev.quiet_age[bar]), stratum.sample("gap"))
    own = ev.epi_tape[bar]
    parts["E2"] = _invert(ecdf(float(ev.tape10[bar]), own) if own
                          else ecdf_sorted(float(ev.tape10[bar]),
                                           stratum.sample("epi")))
    parts["E3"] = ecdf_sorted(float(ev.onesided[bar]), stratum.sample("touch"))
    if int(ev.gaps_done[bar]) >= E4_MIN_GAPS:
        parts["E4"] = ecdf_sorted(float(ev.gap_ratio[bar]),
                                  stratum.sample("ratio"))
    parts["E5"] = _invert(ecdf_sorted(float(ev.opp_age[bar]),
                                      stratum.sample("oppage")))
    value, present = combine(parts)
    return value, present, parts


# --------------------------------------------------------------------------
# The gate run: fire resolution and entry.
# --------------------------------------------------------------------------

@dataclass(slots=True)
class Shot8:
    """One counted entry (or the miss that replaced it) for one cell."""

    cell: int
    asset: str
    phase: str
    d8: int
    side: int
    fire_bar: int
    entry_bar: int
    g_value: float
    depth: float
    miss: str
    post_extreme: bool = False
    soft_hit: bool = False
    side_ok: bool | None = None
    delay_s: int = 0
    before_terminal: bool = False
    wait_s: int = -1
    # The judging law's objects: a FIXED 1800 s horizon, stamped twice.  The
    # open-ended rate above is censored by however much phase is left, so it
    # cannot separate a survival detector from a clock with kind censoring.
    postx1800_fire: bool = False
    postx1800_entry: bool = False
    fire_full_window: bool = False
    entry_full_window: bool = False
    fire_phase_s: int = 0


def _finish(cell: Cell8, side: int, fire_bar: int, entry_bar: int,
            g_value: float, depth: float) -> Shot8:
    """Fill in the metrics every stage-A rate needs for one taken entry."""

    _prior, new_ext, _armed = S7A.side_arrays(cell.geo, side)
    terminal = S7A.terminal_bar(cell.geo, side)
    rem = cell.star.rem(side)
    sign = int(cell.star.sign[entry_bar])

    def horizon(anchor: int) -> tuple[bool, bool]:
        """``(extended within 1800 s, the full window was observable)``."""

        stop = int(anchor) + 1 + HORIZON_BARS
        return (bool(np.any(new_ext[int(anchor) + 1: stop])), bool(stop <= cell.n))

    fire_hit, fire_full = horizon(fire_bar)
    entry_hit, entry_full = horizon(entry_bar)
    open_s = int(cell.rec.phase_open_ts_ns)
    return Shot8(
        cell=cell.position, asset=cell.asset, phase=cell.phase, d8=cell.d8,
        side=int(side), fire_bar=int(fire_bar), entry_bar=int(entry_bar),
        g_value=float(g_value), depth=float(depth), miss="",
        post_extreme=bool(np.any(new_ext[entry_bar + 1:])),
        soft_hit=bool(float(rem[entry_bar]) > 0.0),
        side_ok=None if sign == 0 else bool(int(side) == sign),
        delay_s=int((int(entry_bar) - terminal) * BAR_SECONDS) if terminal >= 0 else 0,
        before_terminal=bool(terminal >= 0 and int(entry_bar) < terminal),
        wait_s=int((int(entry_bar) - int(fire_bar)) * BAR_SECONDS),
        postx1800_fire=fire_hit, postx1800_entry=entry_hit,
        fire_full_window=fire_full, entry_full_window=entry_full,
        fire_phase_s=int((int(cell.rec.lat[fire_bar]) - open_s)
                         // NANOS_PER_SECOND))


def entry_after(cell: Cell8, side: int, fire_bar: int, depth_law: bool
                ) -> tuple[int, float, str]:
    """``(entry bar, depth, miss)`` under the primary or the control law."""

    cands = S7A.candidate_bars(cell.rec, side)
    position = int(np.searchsorted(cands, int(fire_bar), side="left"))
    prior, _new, _armed = S7A.side_arrays(cell.geo, side)
    extreme = float(prior[fire_bar])
    if position >= len(cands):
        return -1, float("nan"), MISS_NO_CANDIDATE
    if not depth_law:
        bar = int(cands[position])
        return bar, depth_atr(float(cell.rec.mid[bar]), extreme, cell.atr_mid2), ""
    limit = int(fire_bar) + DEPTH_WINDOW_BARS
    for bar in cands[position:]:
        bar = int(bar)
        if bar > limit:
            break
        reach = depth_atr(float(cell.rec.mid[bar]), extreme, cell.atr_mid2)
        if reach <= DEPTH_ATR:
            return bar, reach, ""
    return -1, float("nan"), MISS_NO_DEPTH


def score_cell(cell: Cell8, stratum: Stratum) -> list[tuple[int, int, float, float]]:
    """Every eligible ``(side, bar, G, E1)`` in one cell, both sides, bar order.

    The scan does NOT stop at the fire.  The stratum's G distribution has to be
    a property of the tape, not of where this policy happened to enter, or the
    60th-percentile bar would be calibrated on a sample its own past entries
    truncated.  Firing reads this list; calibration banks all of it.

    E1 rides along because the judging law needs an E1-ONLY gate calibrated the
    same walk-forward way: without it a composite cannot be shown to beat its
    own strongest single component.
    """

    scored: list[tuple[int, int, float, float]] = []
    for bar in range(1, cell.n):
        for side in (1, -1):
            ev = cell.sides[side]
            if not bool(ev.eligible[bar]) or float(ev.remaining_s[bar]) < REMAIN_MIN_S:
                continue
            value, _present, parts = score_bar(cell, side, bar, stratum)
            if value is not None:
                lone = parts["E1"]
                scored.append((side, bar, float(value),
                               float("nan") if lone is None else float(lone)))
    return scored


def resolve(cell: Cell8, scored: Sequence[tuple[int, int, float, float]],
            threshold: float, depth_law: bool, *, column: int = 2
            ) -> tuple[Shot8 | None, str]:
    """The first fire that survives the entry law and the cancel clause.

    ``column`` picks which score fires: 2 is the composite G, 3 the E1-only
    control.  Everything downstream of the fire is identical, so the two lines
    differ in exactly the evidence and nothing else.
    """

    miss = MISS_NO_FIRE
    for row in scored:
        side, bar, value = int(row[0]), int(row[1]), float(row[column])
        if not np.isfinite(value) or value < threshold:
            continue
        entry_bar, depth, branch = entry_after(cell, side, bar, depth_law)
        if entry_bar < 0:
            miss = branch
            continue
        _oprior, opp_new, _oarmed = S7A.side_arrays(cell.geo, -side)
        if bool(np.any(opp_new[bar + 1: entry_bar + 1])):
            # The opposite side printed a new extreme before the entry landed:
            # the pending entry is cancelled and the cell re-arms.
            miss = MISS_CANCELLED
            continue
        return _finish(cell, side, bar, entry_bar, value, depth), ""
    return None, miss


def prepare_day(stratum: Stratum, cells: Sequence[Cell8]) -> None:
    """Bank one day's evidence into its stratum, ready for the NEXT day.

    ``QRE2_MILL_S8_MUTANT=gate_peeks_forward`` moves the flush to here, so the
    day's own gaps, episodes, touches, ratios and ages are inside the empirical
    CDF that the same day is about to be scored against.  This is the whole
    walk-forward law, and it is the module's only branch on the mutant.
    """

    for cell in cells:
        for name, values in contributions(cell).items():
            stratum.pending[name].extend(values)
    if _mutant() == MUTANT_PEEK:
        stratum.flush()
        stratum.prior_days -= 1


@dataclass(slots=True)
class GateRun:
    """One walk-forward pass: both entry laws off one shared scoring pass."""

    shots: dict[str, list[Shot8]]
    misses: dict[str, dict[str, str]]
    pool: dict[str, list[tuple[int, int, float, float]]]
    scored_cells: dict[str, int]
    crossings: dict[str, list[tuple[int, int]]] = field(default_factory=dict)


def run_gate(cells: Sequence[Cell8]) -> GateRun:
    """The whole walk-forward pass, strata advanced one EXPLORE day at a time.

    The gate is identical for both entry laws, so the expensive part - five
    percentile lookups on every eligible bar of every cell - runs once and both
    laws resolve against the same scored list.
    """

    strata: dict[tuple[str, str], Stratum] = {}
    by_day: dict[tuple[str, int], list[Cell8]] = {}
    for cell in cells:
        by_day.setdefault((cell.asset, cell.d8), []).append(cell)
    tracked = tuple(LINES) + ("E1ONLY",) + LINES_8B
    run = GateRun({name: [] for name in tracked},
                  {name: {} for name in tracked}, {},
                  {asset: 0 for asset in ASSETS})
    for asset, d8 in sorted(by_day):
        for cell in by_day[(asset, d8)]:
            prepare_day(strata.setdefault((cell.asset, cell.phase), Stratum()),
                        [cell])
        for cell in by_day[(asset, d8)]:
            stratum = strata[(cell.asset, cell.phase)]
            tag = f"{cell.asset}/{cell.d8}/{cell.phase}"
            if stratum.prior_days < MIN_PRIOR_DAYS:
                for name in run.misses:
                    run.misses[name][tag] = MISS_UNSCORED
                continue
            scored = score_cell(cell, stratum)
            # G is banked as soon as the five evidences can be computed, which
            # is one day EARLIER than the first day that can fire: the fire bar
            # is a percentile of prior-day G, and that sample has to be filled
            # by a day that could not yet act on it.  Banking only from cells
            # that fired would make the sample self-referential and empty.
            stratum.pending["G"].extend(row[2] for row in scored)
            stratum.pending["E1"].extend(row[3] for row in scored
                                         if np.isfinite(row[3]))
            if not stratum.prior["G"] or not stratum.prior["E1"]:
                for name in run.misses:
                    run.misses[name][tag] = MISS_UNSCORED
                continue
            run.pool[tag] = scored
            run.scored_cells[cell.asset] = run.scored_cells.get(cell.asset, 0) + 1
            threshold = float(np.percentile(
                np.asarray(stratum.prior["G"], np.float64), G_PERCENTILE))
            lone_bar = float(np.percentile(
                np.asarray(stratum.prior["E1"], np.float64), G_PERCENTILE))
            # The repeated-look statistic the calibration critique asks for: the
            # bar is a percentile of SINGLE BARS but it is watched over every
            # eligible bar of the cell, so the per-bar crossing frequency and the
            # per-cell (episode-level) coverage are different objects.
            run.crossings[tag] = [
                (sum(1 for row in scored if row[2] >= threshold), len(scored))]
            for name in LINES:
                shot, miss = resolve(cell, scored, threshold,
                                     depth_law=(name == "PRIMARY"))
                if shot is None:
                    run.misses[name][tag] = miss
                else:
                    run.shots[name].append(shot)
            # The E1-ONLY control fires on its own component against its own
            # walk-forward bar, and then takes the PRIMARY entry law, so the
            # composite is compared against it at the same stamp on the same
            # opportunity set.
            shot, miss = resolve(cell, scored, lone_bar, depth_law=True, column=3)
            if shot is None:
                run.misses["E1ONLY"][tag] = miss
            else:
                run.shots["E1ONLY"].append(shot)
            # SWEEP 8b: the same E1-ONLY firing law promoted to POLICY, under
            # both entry laws.  E1PRIMARY is computed by the identical call the
            # credit control just made, which is what pins the two together.
            for name, depth in (("E1PRIMARY", True), ("E1CONTROL", False)):
                shot, miss = resolve(cell, scored, lone_bar, depth_law=depth,
                                     column=3)
                if shot is None:
                    run.misses[name][tag] = miss
                else:
                    run.shots[name].append(shot)
        for cell in by_day[(asset, d8)]:
            strata[(cell.asset, cell.phase)].flush()
    return run


# --------------------------------------------------------------------------
# Stage A.
# --------------------------------------------------------------------------

def _rate(hits: int, total: int) -> dict[str, object]:
    low, high = S1.wilson(int(hits), int(total))
    return {"hits": int(hits), "n": int(total),
            "rate": (hits / total) if total else None,
            "ci_low": low if total else None, "ci_high": high if total else None}


def _q(values: Sequence[float], mark: float) -> float | None:
    array = np.asarray([float(v) for v in values], np.float64)
    array = array[np.isfinite(array)]
    return float(np.percentile(array, mark)) if len(array) else None


def shot_table(shots: Sequence[Shot8], cells: int) -> dict[str, object]:
    rows = list(shots)
    graded = [row for row in rows if row.side_ok is not None]
    return {
        "cells_scored": int(cells), "entries": len(rows),
        "coverage": (len(rows) / cells) if cells else None,
        "post_extension": _rate(sum(1 for r in rows if r.post_extreme), len(rows)),
        "soft_hit": _rate(sum(1 for r in rows if r.soft_hit), len(rows)),
        "side_agree": _rate(sum(1 for r in graded if r.side_ok), len(graded)),
        "before_terminal": _rate(sum(1 for r in rows if r.before_terminal), len(rows)),
        "delay_median_s": _q([r.delay_s for r in rows], 50),
        "delay_p90_s": _q([r.delay_s for r in rows], 90),
        "depth_median_atr": _q([r.depth for r in rows], 50),
        "depth_p90_atr": _q([r.depth for r in rows], 90),
        "wait_median_s": _q([r.wait_s for r in rows], 50),
        "wait_p90_s": _q([r.wait_s for r in rows], 90),
    }


def stage_a(shots: Sequence[Shot8], misses: Mapping[str, str],
            scored_cells: Mapping[str, int]) -> dict[str, object]:
    by_asset: dict[str, object] = {}
    by_phase: dict[str, object] = {}
    branches: dict[str, dict[str, int]] = {asset: {name: 0 for name in MISS_BRANCHES}
                                           for asset in ASSETS}
    for tag, branch in misses.items():
        asset = tag.split("/")[0]
        branches[asset][branch] = branches[asset].get(branch, 0) + 1
    for asset in ASSETS:
        rows = [row for row in shots if row.asset == asset]
        block = shot_table(rows, int(scored_cells.get(asset, 0)))
        block["miss_branches"] = branches[asset]
        by_asset[asset] = block
    phases = sorted({row.phase for row in shots} | {tag.split("/")[2]
                                                    for tag in misses})
    for phase in phases:
        rows = [row for row in shots if row.phase == phase]
        seen = sum(1 for tag, branch in misses.items()
                   if tag.split("/")[2] == phase and branch != MISS_UNSCORED)
        by_phase[phase] = shot_table(rows, seen + len(rows))
    return {"by_asset": by_asset, "by_phase": by_phase}


def random_control(cells: Sequence[Cell8],
                   pool: Mapping[str, list[tuple[int, int, float]]],
                   depth_law: bool, draws: int = RANDOM_DRAWS
                   ) -> dict[str, object]:
    """Uniform eligible bar in each scored cell, same entry law, seeded draws."""

    by_tag = {f"{cell.asset}/{cell.d8}/{cell.phase}": cell for cell in cells}
    rng = np.random.default_rng(SEED)
    per_draw: list[list[Shot8]] = []
    for _draw in range(draws):
        picked: list[Shot8] = []
        for tag, scored in sorted(pool.items()):
            if not scored:
                continue
            cell = by_tag[tag]
            chosen = scored[int(rng.integers(len(scored)))]
            side, bar, value = int(chosen[0]), int(chosen[1]), float(chosen[2])
            entry_bar, depth, branch = entry_after(cell, side, bar, depth_law)
            if entry_bar < 0:
                continue
            picked.append(_finish(cell, side, bar, entry_bar, value, depth))
        per_draw.append(picked)
    out: dict[str, object] = {"draws": draws, "seed": SEED, "by_asset": {}}
    for asset in ASSETS:
        cells_seen = sum(1 for tag, scored in pool.items()
                         if scored and tag.split("/")[0] == asset)
        tables = [shot_table([r for r in rows if r.asset == asset], cells_seen)
                  for rows in per_draw]
        def mean(path: str, inner: str | None = None) -> float | None:
            values = [t[path] if inner is None else t[path][inner]  # type: ignore[index]
                      for t in tables]
            values = [float(v) for v in values if v is not None]
            return float(np.mean(values)) if values else None
        out["by_asset"][asset] = {
            "cells_scored": cells_seen,
            "entries_mean": float(np.mean([t["entries"] for t in tables])),
            "coverage_mean": mean("coverage"),
            "post_extension_mean": mean("post_extension", "rate"),
            "soft_hit_mean": mean("soft_hit", "rate"),
            "delay_median_s_mean": mean("delay_median_s"),
            "depth_median_atr_mean": mean("depth_median_atr"),
        }
    return out


def horizon_table(shots: Sequence[Shot8]) -> dict[str, object]:
    """The three-object separation: postX_1800 at both stamps, and the wait."""

    rows = list(shots)
    fire_full = [r for r in rows if r.fire_full_window]
    entry_full = [r for r in rows if r.entry_full_window]
    return {
        "n": len(rows),
        "postx1800_fire": _rate(sum(1 for r in fire_full if r.postx1800_fire),
                                len(fire_full)),
        "postx1800_entry": _rate(sum(1 for r in entry_full if r.postx1800_entry),
                                 len(entry_full)),
        "fire_window_censored": len(rows) - len(fire_full),
        "entry_window_censored": len(rows) - len(entry_full),
        "wait_median_s": _q([r.wait_s for r in rows], 50),
        "wait_p90_s": _q([r.wait_s for r in rows], 90),
        "wait_max_s": _q([r.wait_s for r in rows], 100),
        "fire_phase_median_s": _q([r.fire_phase_s for r in rows], 50),
    }


def phase_matched_control(cells: Sequence[Cell8],
                          pool: Mapping[str, list[tuple[int, int, float, float]]],
                          fires: Sequence[Shot8], depth_law: bool,
                          draws: int = RANDOM_DRAWS) -> dict[str, object]:
    """Random fire bars matched to the real fires on phase-elapsed time.

    An unmatched random draw sits at a different point of the phase than the
    gate does, so it carries different censoring and different remaining
    opportunity.  Matching within 300 s of phase-elapsed removes the clock and
    leaves only the question the gate claims to answer.
    """

    by_tag = {f"{cell.asset}/{cell.d8}/{cell.phase}": cell for cell in cells}
    targets: dict[str, list[int]] = {}
    for row in fires:
        targets.setdefault(row.asset, []).append(int(row.fire_phase_s))
    rng = np.random.default_rng(SEED)
    per_draw: list[list[Shot8]] = []
    unmatched = 0
    for _draw in range(draws):
        picked: list[Shot8] = []
        for tag, scored in sorted(pool.items()):
            cell = by_tag[tag]
            wanted = targets.get(cell.asset)
            if not scored or not wanted:
                continue
            aim = int(wanted[int(rng.integers(len(wanted)))])
            open_ns = int(cell.rec.phase_open_ts_ns)
            near = [row for row in scored
                    if abs(int((int(cell.rec.lat[int(row[1])]) - open_ns)
                               // NANOS_PER_SECOND) - aim) <= PHASE_MATCH_WINDOW_S]
            if not near:
                unmatched += 1
                continue
            chosen = near[int(rng.integers(len(near)))]
            side, bar = int(chosen[0]), int(chosen[1])
            entry_bar, depth, _branch = entry_after(cell, side, bar, depth_law)
            if entry_bar < 0:
                continue
            picked.append(_finish(cell, side, bar, entry_bar, float(chosen[2]),
                                  depth))
        per_draw.append(picked)
    out: dict[str, object] = {"draws": draws, "seed": SEED,
                              "match_window_s": PHASE_MATCH_WINDOW_S,
                              "cells_unmatched": unmatched, "by_asset": {}}
    for asset in ASSETS:
        tables = [horizon_table([r for r in rows if r.asset == asset])
                  for rows in per_draw]
        hits = sum(t["postx1800_fire"]["hits"] for t in tables)
        total = sum(t["postx1800_fire"]["n"] for t in tables)
        out["by_asset"][asset] = {
            "entries_mean": float(np.mean([t["n"] for t in tables])),
            "postx1800_fire": _rate(hits, total),
            "fire_phase_median_s": _mean([t["fire_phase_median_s"]
                                          for t in tables]),
        }
    return out


def crossing_stats(run: GateRun, cells: Sequence[Cell8]) -> dict[str, object]:
    """Bar-level crossing frequency against episode-level entry coverage."""

    by_tag = {f"{cell.asset}/{cell.d8}/{cell.phase}": cell for cell in cells}
    out: dict[str, object] = {"by_stratum": {}}
    book: dict[tuple[str, str], list[int]] = {}
    for tag, rows in run.crossings.items():
        cell = by_tag[tag]
        key = (cell.asset, cell.phase)
        crossed, total = rows[0]
        entry = book.setdefault(key, [0, 0, 0, 0])
        entry[0] += crossed
        entry[1] += total
        entry[2] += 1
        entry[3] += 1 if crossed else 0
    counts: dict[tuple[str, str], int] = {}
    for row in run.shots["PRIMARY"]:
        counts[(row.asset, row.phase)] = counts.get((row.asset, row.phase), 0) + 1
    for key in sorted(book):
        crossed, total, cells_n, cells_crossed = book[key]
        out["by_stratum"][f"{key[0]}/{key[1]}"] = {
            "bars_scored": total, "bars_crossed": crossed,
            "bar_crossing_freq": (crossed / total) if total else None,
            "cells_scored": cells_n,
            "cells_with_a_crossing": cells_crossed,
            "episode_crossing_rate": (cells_crossed / cells_n) if cells_n else None,
            "entries": counts.get(key, 0),
            "episode_entry_coverage": (counts.get(key, 0) / cells_n) if cells_n
            else None,
        }
    return out


def clears_margin(delta: float) -> bool:
    """``delta >= 0.05`` with a float guard.

    An exactly-0.05 edge is not representable: ``0.70 - 0.65`` evaluates to
    0.049999999999999996, so a bare comparison would fail a verdict that the
    adopted law says passes.
    """

    return bool(float(delta) >= CREDIT_MARGIN - 1e-9)


def credit_verdict(report: Mapping[str, object]) -> dict[str, object]:
    """The adopted judging law, at the FIRE stamp, per asset.

    The composite earns belief only when its fixed-horizon extension beats BOTH
    the E1-ONLY gate and the phase-time-matched random draw by at least 0.05.
    """

    out: dict[str, object] = {"margin": CREDIT_MARGIN, "by_asset": {}}
    horizons = report["horizons"]
    for asset in ASSETS:
        composite = horizons["PRIMARY"]["by_asset"][asset]["postx1800_fire"]
        lone = horizons["E1ONLY"]["by_asset"][asset]["postx1800_fire"]
        matched = (report["phase_matched_control"]["by_asset"][asset]
                   ["postx1800_fire"])
        beats: dict[str, object] = {}
        for name, other in (("E1ONLY", lone), ("PHASEMATCH", matched)):
            if composite["rate"] is None or other["rate"] is None:
                beats[name] = {"delta": None, "pass": False}
                continue
            delta = float(other["rate"]) - float(composite["rate"])
            beats[name] = {"delta": delta, "pass": clears_margin(delta)}
        out["by_asset"][asset] = {
            "deciding": asset in ("NKD", "SI"),
            "composite": composite, "e1only": lone, "phasematch": matched,
            "beats": beats,
            "verdict": ("PASS" if all(beats[k]["pass"] for k in beats) else "FAIL"),
        }
    deciding = [out["by_asset"][a]["verdict"] for a in ("NKD", "SI")]
    out["overall"] = "PASS" if all(v == "PASS" for v in deciding) else "FAIL"
    return out


def horizon_block(shots: Sequence[Shot8]) -> dict[str, object]:
    """The fixed-horizon table per asset and per phase for one line."""

    phases = sorted({row.phase for row in shots})
    return {
        "by_asset": {asset: horizon_table([r for r in shots if r.asset == asset])
                     for asset in ASSETS},
        "by_phase": {phase: horizon_table([r for r in shots if r.phase == phase])
                     for phase in phases},
    }


def sweep7a_reference() -> dict[str, object]:
    """Sweep 7a's first-quiet control, imported and never recomputed."""

    payload = json.loads(SWEEP7A_PATH.read_text())
    block = payload["screen_a"]["controls"]["first_quiet"]
    return {asset: {
        "cells": block[asset]["cells"], "selections": block[asset]["selections"],
        "coverage": block[asset]["coverage"],
        "post_new_extreme": block[asset]["post_new_extreme"]["rate"],
        "soft_hit": block[asset]["soft_hit"]["rate"],
        "delay_median_s": block[asset]["delay_median_s"],
        "delay_p90_s": block[asset]["delay_p90_s"],
    } for asset in ASSETS if asset in block}


# --------------------------------------------------------------------------
# Stage B.
# --------------------------------------------------------------------------

def entries_of(shots: Sequence[Shot8], records: Sequence[S1.CellRec]
               ) -> list[S1.Entry]:
    """Sweep 1's candidate-anchored entry for every taken shot."""

    out: list[S1.Entry] = []
    for row in shots:
        made = S1.make_entry(row.cell, records[row.cell], row.entry_bar, row.side)
        if made is not None:
            out.append(made)
    return out


def bucket_of(shot: Shot8, cell: Cell8) -> str:
    """Sweep 7b's bleed bucket, its law applied to this policy's entries."""

    rem = float(cell.star.rem(shot.side)[shot.entry_bar])
    if rem <= 0.0:
        quality = "HARD-WRONG"
    else:
        quality = "RIGHT" if shot.side_ok else "SOFT-WRONG"
    terminal = S7A.terminal_bar(cell.geo, shot.side)
    if terminal < 0:
        timing = "IN-BUDGET"
    else:
        budget = S7B.BUDGET_MINUTES[shot.asset] * 60
        late = (shot.entry_bar - terminal) * BAR_SECONDS > budget
        timing = "LATE" if late else "IN-BUDGET"
    return f"{quality}/{timing}"


def bleed_table(shots: Sequence[Shot8], cells: Mapping[int, Cell8],
                records: Sequence[S1.CellRec], days: Mapping[str, int]
                ) -> dict[str, object]:
    """The 7b bucket table recomputed on THIS policy, per asset."""

    out: dict[str, object] = {"budget_minutes": dict(S7B.BUDGET_MINUTES),
                              "by_asset": {}}
    for asset in ASSETS:
        rows = [row for row in shots if row.asset == asset]
        book: dict[str, list[tuple[Shot8, S1.Entry]]] = {}
        for row in rows:
            made = S1.make_entry(row.cell, records[row.cell], row.entry_bar, row.side)
            if made is None:
                continue
            book.setdefault(bucket_of(row, cells[row.cell]), []).append((row, made))
        totals = {name: float(sum(e.cert_usd for _s, e in pairs))
                  for name, pairs in book.items()}
        gross_loss = float(sum(value for value in totals.values() if value < 0.0))
        table: dict[str, object] = {}
        for name in S7B.BUCKETS:
            pairs = book.get(name, [])
            certs = np.asarray([e.cert_usd for _s, e in pairs], np.float64)
            table[name] = {
                "n": len(pairs),
                "cash_usd": float(certs.sum()) if len(certs) else 0.0,
                "usd_per_asset_day": (float(certs.sum() / max(1, days.get(asset, 1)))
                                      if len(certs) else 0.0),
                "usd_per_trade": float(certs.mean()) if len(certs) else None,
                "wall_rate": (float(np.mean([e.wall for _s, e in pairs]))
                              if pairs else None),
                "win_rate": float((certs > 0).mean()) if len(certs) else None,
                # Sweep 7b's own convention, kept exactly so the SWIB row can be
                # read beside its baseline: gross_loss is negative, so a
                # PROFITABLE bucket carries a negative share.
                "share_of_gross_loss": ((float(certs.sum()) / gross_loss)
                                        if gross_loss else None),
            }
        out["by_asset"][asset] = {"table": table, "gross_loss_usd": gross_loss,
                                  "entries": sum(len(v) for v in book.values())}
    return out


def sweep7b_baseline() -> dict[str, object]:
    """7b's own SOFT-WRONG/IN-BUDGET row, read from its report."""

    payload = json.loads(SWEEP7B_PATH.read_text())
    block = payload["part1_decomposition"]["by_asset"]
    return {asset: {
        "n": block[asset]["table"]["SOFT-WRONG/IN-BUDGET"]["n"],
        "share_of_gross_loss":
            block[asset]["table"]["SOFT-WRONG/IN-BUDGET"]["share_of_gross_loss"],
        "wall_rate": block[asset]["table"]["SOFT-WRONG/IN-BUDGET"]["wall_rate"],
        "usd_per_asset_day":
            block[asset]["table"]["SOFT-WRONG/IN-BUDGET"]["usd_per_asset_day"],
    } for asset in ASSETS if asset in block}


def stage_b(lines: Mapping[str, list[Shot8]], cells: Sequence[Cell8],
            records: Sequence[S1.CellRec], days: Mapping[str, int],
            scored_cells: Mapping[str, int],
            explore_days: Mapping[str, list[int]],
            names: Sequence[str] = LINES) -> dict[str, object]:
    by_index = {cell.position: cell for cell in cells}
    priced: dict[str, list[S1.Entry]] = {}
    report: dict[str, object] = {
        "lines": {}, "bleed": {}, "bleed_baseline_7b": sweep7b_baseline(),
        "replays": {}, "stress": {}, "priced_lines": list(names)}
    cell_counts = {asset: int(scored_cells.get(asset, 0)) for asset in ASSETS}
    for name in names:
        shots = list(lines[name])
        entries = entries_of(shots, records)
        cash = S1.cash_line(entries, days, cell_counts)
        for asset in ASSETS:
            priced[f"{asset}/{name}"] = [row for row in entries if row.asset == asset]
        report["lines"][name] = cash
        report["bleed"][name] = bleed_table(shots, by_index, records, days)
        report["replays"][name] = S1.replay_line(
            entries, records, f"sweep8-{name.lower()}")
        report["stress"][name] = {
            asset: S3.stress_line(entries, records, days, cell_counts, asset,
                                  STRESS_RATE)
            for asset in ASSETS}
    report["null"] = S1.block_null(priced, explore_days, NULL_DRAWS, SEED)
    return report


# --------------------------------------------------------------------------
# The pre-registered decision.
# --------------------------------------------------------------------------

def decide(report: Mapping[str, object]) -> dict[str, object]:
    out: dict[str, object] = {"keep_to_price": True, "by_asset": {}}
    stage_a_block = report["stage_a"]
    stage_b_block = report["stage_b"]
    null_lines = stage_b_block["null"]["by_line"]
    for asset in ASSETS:
        rows: dict[str, object] = {}
        for name in LINES:
            cash = stage_b_block["lines"][name][asset]
            table = stage_a_block[name]["by_asset"][asset]
            stress = stage_b_block["stress"][name][asset]
            bucket = (stage_b_block["bleed"][name]["by_asset"][asset]["table"]
                      ["SOFT-WRONG/IN-BUDGET"])
            null_row = null_lines.get(f"{asset}/{name}")
            adjusted = (float(null_row["p_max_adjusted"]) if null_row else None)
            postx = table["post_extension"]["rate"]
            coverage = table["coverage"]
            fired: list[str] = []
            if not float(cash["usd_per_asset_day"]) >= DAY_RUNG_USD[asset]:
                fired.append(f"usd/day {cash['usd_per_asset_day']:.1f} "
                             f"< rung {DAY_RUNG_USD[asset]:.0f}")
            if float(cash["mdd_day_usd"]) >= MDD_CEILING:
                fired.append(f"mdd_day {cash['mdd_day_usd']:.0f} >= {MDD_CEILING:.0f}")
            if float(cash["mdd_trade_usd"]) >= MDD_CEILING:
                fired.append(f"mdd_trade {cash['mdd_trade_usd']:.0f} "
                             f">= {MDD_CEILING:.0f}")
            if not float(stress["usd_per_asset_day"]) >= 0.0:
                fired.append(f"stress {stress['usd_per_asset_day']:.1f} < 0")
            if adjusted is None or adjusted > NULL_CEILING:
                fired.append(f"adjusted null {adjusted} > {NULL_CEILING}")
            interesting = bool(
                postx is not None and float(postx) <= POSTX_CEILING
                and coverage is not None and float(coverage) >= COVERAGE_FLOOR
                and float(cash["usd_per_asset_day"]) > 0.0
                and bucket["share_of_gross_loss"] is not None
                and float(bucket["share_of_gross_loss"]) < SWIB_SHARE_CEILING)
            rows[name] = {
                "deciding": asset in ("NKD", "SI"),
                "usd_per_asset_day": cash["usd_per_asset_day"],
                "mdd_day_usd": cash["mdd_day_usd"],
                "mdd_trade_usd": cash["mdd_trade_usd"],
                "stress_usd_per_asset_day": stress["usd_per_asset_day"],
                "adjusted_null_p": adjusted,
                "post_extension": postx, "coverage": coverage,
                "swib_loss_share": bucket["share_of_gross_loss"],
                "freeze_candidate": bool(not fired) and asset in ("NKD", "SI"),
                "interesting": interesting,
                "verdict": ("FREEZE-CANDIDATE" if (not fired and asset in ("NKD", "SI"))
                            else "INTERESTING" if interesting else "KILL"),
                "bounds_fired": fired,
            }
        out["by_asset"][asset] = rows
    verdicts = {row["verdict"] for asset in ASSETS
                for row in out["by_asset"][asset].values()}
    out["overall"] = ("FREEZE-CANDIDATE" if "FREEZE-CANDIDATE" in verdicts
                      else "INTERESTING" if "INTERESTING" in verdicts else "KILL")
    return out


# --------------------------------------------------------------------------
# Log rows.
# --------------------------------------------------------------------------

def decide_8b(report: Mapping[str, object]) -> dict[str, object]:
    """Sweep 8b's own pre-registered reading, stated before its cash was read."""

    out: dict[str, object] = {
        "bars": {"freeze": "rung + both MDD < 1000 + stress > 0 + adj null <= 0.05",
                 "interesting": (f"usd/day > {INTERESTING_USD_DAY_8B} and "
                                 f"mdd_day < {INTERESTING_MDD_DAY_8B} and "
                                 f"stress > 0 on a deciding asset")},
        "by_asset": {}}
    block = report["sweep8b"]["stage_b"]
    null_lines = block["null"]["by_line"]
    for asset in ASSETS:
        rows: dict[str, object] = {}
        for name in LINES_8B:
            cash = block["lines"][name][asset]
            stress = block["stress"][name][asset]
            null_row = null_lines.get(f"{asset}/{name}")
            adjusted = float(null_row["p_max_adjusted"]) if null_row else None
            deciding = asset in ("NKD", "SI")
            usd = float(cash["usd_per_asset_day"])
            mdd_day = float(cash["mdd_day_usd"])
            mdd_trade = float(cash["mdd_trade_usd"])
            stressed = float(stress["usd_per_asset_day"])
            fired: list[str] = []
            if not usd >= DAY_RUNG_USD[asset]:
                fired.append(f"usd/day {usd:.1f} < rung {DAY_RUNG_USD[asset]:.0f}")
            if mdd_day >= MDD_CEILING:
                fired.append(f"mdd_day {mdd_day:.0f} >= {MDD_CEILING:.0f}")
            if mdd_trade >= MDD_CEILING:
                fired.append(f"mdd_trade {mdd_trade:.0f} >= {MDD_CEILING:.0f}")
            if not stressed > 0.0:
                fired.append(f"stress {stressed:.1f} <= 0")
            if adjusted is None or adjusted > NULL_CEILING:
                fired.append(f"adjusted null {adjusted} > {NULL_CEILING}")
            freeze = bool(not fired and deciding)
            interesting = bool(deciding and usd > INTERESTING_USD_DAY_8B
                               and mdd_day < INTERESTING_MDD_DAY_8B
                               and stressed > 0.0)
            rows[name] = {
                "deciding": deciding, "usd_per_asset_day": usd,
                "mdd_day_usd": mdd_day, "mdd_trade_usd": mdd_trade,
                "stress_usd_per_asset_day": stressed, "adjusted_null_p": adjusted,
                "trades": cash["trades"], "coverage": cash["coverage"],
                "freeze_candidate": freeze, "interesting": interesting,
                "verdict": ("FREEZE-CANDIDATE" if freeze
                            else "INTERESTING" if interesting else "KILL"),
                "bounds_fired": fired,
            }
        out["by_asset"][asset] = rows
    verdicts = {row["verdict"] for asset in ASSETS
                for row in out["by_asset"][asset].values()}
    out["overall"] = ("FREEZE-CANDIDATE" if "FREEZE-CANDIDATE" in verdicts
                      else "INTERESTING" if "INTERESTING" in verdicts else "KILL")
    return out


def log_rows_8b(report: Mapping[str, object]) -> list[dict[str, object]]:
    stamp = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    shared = {
        "registered_utc": stamp, "spec_sha": SPEC_SHA, "code_sha": code_sha(),
        "split_sha": S1.split_sha(), "outcome_law_sha": S1.outcome_law_sha(),
        "null_seed": SEED, "parent_trial": PARENT_8B,
        "selection_rule": "none: one knob off sweep 8 (E1-only fires)",
        "verdict": "", "days": sum(report["asset_days"].values()),
    }
    block = report["sweep8b"]
    rows: list[dict[str, object]] = []
    counter = 0
    for name in LINES_8B:
        stage = block["stage_a"][name]["by_asset"]
        horizon = block["horizons"][name]["by_asset"]
        counter += 1
        rows.append({
            **shared, "id": f"sweep8b-{counter:03d}", "family": FAMILY_8B,
            "rule": f"STAGE-A/{name}",
            "params": json.dumps([G_PERCENTILE, DEPTH_ATR, REMAIN_MIN_S,
                                  HORIZON_BARS]),
            "coverage": _mean([stage[a]["coverage"] for a in ASSETS]),
            "delay_med_s": _mean([stage[a]["delay_median_s"] for a in ASSETS]),
            "err_rate_hg": _one_minus(stage["HG"]["side_agree"]["rate"]),
            "err_rate_nkd": _one_minus(stage["NKD"]["side_agree"]["rate"]),
            "err_rate_si": _one_minus(stage["SI"]["side_agree"]["rate"]),
            "note": (f"fire-stamp postX_1800 "
                     f"{_show(horizon['HG']['postx1800_fire']['rate'])}/"
                     f"{_show(horizon['NKD']['postx1800_fire']['rate'])}/"
                     f"{_show(horizon['SI']['postx1800_fire']['rate'])}"),
        })
    for name in LINES_8B:
        cash = block["stage_b"]["lines"][name]
        null_block = block["stage_b"]["null"]["by_line"]
        counter += 1
        margins = [float(null_block[f"{a}/{name}"]["p_max_adjusted"])
                   for a in ASSETS if f"{a}/{name}" in null_block]
        rows.append({
            **shared, "id": f"sweep8b-{counter:03d}", "family": FAMILY_8B,
            "rule": f"PRICED/{name}",
            "params": json.dumps([G_PERCENTILE, DEPTH_ATR, REMAIN_MIN_S,
                                  HORIZON_BARS]),
            "coverage": _mean([cash[a]["coverage"] for a in ASSETS]),
            "walls_hg": cash["HG"]["walls"], "walls_nkd": cash["NKD"]["walls"],
            "walls_si": cash["SI"]["walls"],
            "hg_usd_day": cash["HG"]["usd_per_asset_day"],
            "nkd_usd_day": cash["NKD"]["usd_per_asset_day"],
            "si_usd_day": cash["SI"]["usd_per_asset_day"],
            "mdd_hg": cash["HG"]["mdd_day_usd"], "mdd_nkd": cash["NKD"]["mdd_day_usd"],
            "mdd_si": cash["SI"]["mdd_day_usd"],
            "replay_skips": block["stage_b"]["replays"][name].get(
                "occupancy_or_cap_skips"),
            "null_margin": max(margins) if margins else None,
            "note": f"verdict {block['decision']['overall']}",
        })
    return rows


def log_rows(report: Mapping[str, object]) -> list[dict[str, object]]:
    stamp = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    shared = {
        "registered_utc": stamp, "spec_sha": SPEC_SHA, "code_sha": code_sha(),
        "split_sha": S1.split_sha(), "outcome_law_sha": S1.outcome_law_sha(),
        "null_seed": SEED, "parent_trial": report["parent_trial"],
        "selection_rule": SELECTION_RULE, "verdict": "",
        "days": sum(report["asset_days"].values()),
    }
    rows: list[dict[str, object]] = []
    counter = 0
    for name in LINES:
        block = report["stage_a"][name]["by_asset"]
        counter += 1
        rows.append({
            **shared, "id": f"sweep8-{counter:03d}", "family": FAMILY,
            "rule": f"STAGE-A/{name}",
            "params": json.dumps([QUIET_MIN_BARS, G_PERCENTILE, DEPTH_ATR,
                                  REMAIN_MIN_S]),
            "coverage": _mean([block[a]["coverage"] for a in ASSETS]),
            "delay_med_s": _mean([block[a]["delay_median_s"] for a in ASSETS]),
            "err_rate_hg": _one_minus(block["HG"]["side_agree"]["rate"]),
            "err_rate_nkd": _one_minus(block["NKD"]["side_agree"]["rate"]),
            "err_rate_si": _one_minus(block["SI"]["side_agree"]["rate"]),
            "note": (f"postX {_show(block['HG']['post_extension']['rate'])}/"
                     f"{_show(block['NKD']['post_extension']['rate'])}/"
                     f"{_show(block['SI']['post_extension']['rate'])}"),
        })
    for name in LINES:
        cash = report["stage_b"]["lines"][name]
        null_block = report["stage_b"]["null"]["by_line"]
        counter += 1
        margins = [float(null_block[f"{a}/{name}"]["p_max_adjusted"])
                   for a in ASSETS if f"{a}/{name}" in null_block]
        rows.append({
            **shared, "id": f"sweep8-{counter:03d}", "family": FAMILY,
            "rule": f"PRICED/{name}",
            "params": json.dumps([QUIET_MIN_BARS, G_PERCENTILE, DEPTH_ATR,
                                  REMAIN_MIN_S]),
            "coverage": _mean([cash[a]["coverage"] for a in ASSETS]),
            "walls_hg": cash["HG"]["walls"], "walls_nkd": cash["NKD"]["walls"],
            "walls_si": cash["SI"]["walls"],
            "hg_usd_day": cash["HG"]["usd_per_asset_day"],
            "nkd_usd_day": cash["NKD"]["usd_per_asset_day"],
            "si_usd_day": cash["SI"]["usd_per_asset_day"],
            "mdd_hg": cash["HG"]["mdd_day_usd"], "mdd_nkd": cash["NKD"]["mdd_day_usd"],
            "mdd_si": cash["SI"]["mdd_day_usd"],
            "replay_skips": report["stage_b"]["replays"][name].get(
                "occupancy_or_cap_skips"),
            "null_margin": max(margins) if margins else None,
            "note": f"verdict {report['decision']['overall']}",
        })
    # The judging law's two control lines, no cash: they exist to be beaten.
    for name in GATE_CONTROLS:
        counter += 1
        if name == "E1ONLY":
            block = report["horizons"]["E1ONLY"]["by_asset"]
            rates = {a: block[a]["postx1800_fire"]["rate"] for a in ASSETS}
            coverage = _mean([report["stage_a"]["E1ONLY"]["by_asset"][a]["coverage"]
                              for a in ASSETS])
            delay = _mean([report["stage_a"]["E1ONLY"]["by_asset"][a]
                           ["delay_median_s"] for a in ASSETS])
        else:
            block = report["phase_matched_control"]["by_asset"]
            rates = {a: block[a]["postx1800_fire"]["rate"] for a in ASSETS}
            coverage = None
            delay = None
        rows.append({
            **shared, "id": f"sweep8-{counter:03d}", "family": FAMILY,
            "rule": f"CONTROL/{name}",
            "params": json.dumps([G_PERCENTILE, HORIZON_BARS,
                                  PHASE_MATCH_WINDOW_S]),
            "coverage": coverage, "delay_med_s": delay,
            "note": (f"fire-stamp postX_1800 "
                     f"{_show(rates['HG'])}/{_show(rates['NKD'])}/"
                     f"{_show(rates['SI'])}; credit "
                     f"{report['credit']['overall']}"),
        })
    return rows


def _mean(values: Sequence[object]) -> float | None:
    kept = [float(v) for v in values if v is not None]
    return float(np.mean(kept)) if kept else None


def _one_minus(value: object) -> float | None:
    return None if value is None else float(1.0 - float(value))


def _show(value: object) -> str:
    return "-" if value is None else f"{float(value):.3f}"


# --------------------------------------------------------------------------
# Printing.
# --------------------------------------------------------------------------

def _n(value: object, width: int = 8, digits: int = 2) -> str:
    if value is None:
        return " " * (width - 1) + "-"
    return f"{float(value):{width}.{digits}f}"


def print_stage_a(report: Mapping[str, object],
                  names: Sequence[str] = tuple(LINES) + ("E1ONLY",),
                  source: str = "stage_a") -> None:
    for name in names:
        block = report[source][name]
        print(f"\nSTAGE A  {name}   by asset")
        print(f"{'asset':5s} {'cells':>6s} {'entries':>8s} {'cover':>7s} "
              f"{'postX':>7s} {'ci_lo':>7s} {'ci_hi':>7s} {'soft':>7s} "
              f"{'side':>7s} {'pre_term':>9s} {'delay_med':>10s} {'delay_p90':>10s} "
              f"{'depth_med':>10s} {'wait_med':>9s}")
        for asset in ASSETS:
            row = block["by_asset"][asset]
            print(f"{asset:5s} {row['cells_scored']:6d} {row['entries']:8d} "
                  f"{_n(row['coverage'], 7, 3)} "
                  f"{_n(row['post_extension']['rate'], 7, 3)} "
                  f"{_n(row['post_extension']['ci_low'], 7, 3)} "
                  f"{_n(row['post_extension']['ci_high'], 7, 3)} "
                  f"{_n(row['soft_hit']['rate'], 7, 3)} "
                  f"{_n(row['side_agree']['rate'], 7, 3)} "
                  f"{_n(row['before_terminal']['rate'], 9, 3)} "
                  f"{_n(row['delay_median_s'], 10, 0)} "
                  f"{_n(row['delay_p90_s'], 10, 0)} "
                  f"{_n(row['depth_median_atr'], 10, 3)} "
                  f"{_n(row['wait_median_s'], 9, 0)}")
        print(f"\nSTAGE A  {name}   miss branches")
        print(f"{'asset':5s} " + " ".join(f"{b:>21s}" for b in MISS_BRANCHES))
        for asset in ASSETS:
            counts = block["by_asset"][asset]["miss_branches"]
            print(f"{asset:5s} " + " ".join(f"{counts.get(b, 0):21d}"
                                            for b in MISS_BRANCHES))
        print(f"\nSTAGE A  {name}   by phase")
        print(f"{'phase':5s} {'cells':>6s} {'entries':>8s} {'cover':>7s} "
              f"{'postX':>7s} {'soft':>7s} {'side':>7s} {'delay_med':>10s} "
              f"{'depth_med':>10s}")
        for phase in sorted(block["by_phase"]):
            row = block["by_phase"][phase]
            print(f"{phase:5s} {row['cells_scored']:6d} {row['entries']:8d} "
                  f"{_n(row['coverage'], 7, 3)} "
                  f"{_n(row['post_extension']['rate'], 7, 3)} "
                  f"{_n(row['soft_hit']['rate'], 7, 3)} "
                  f"{_n(row['side_agree']['rate'], 7, 3)} "
                  f"{_n(row['delay_median_s'], 10, 0)} "
                  f"{_n(row['depth_median_atr'], 10, 3)}")


def print_controls(report: Mapping[str, object]) -> None:
    print("\nCONTROL  sweep-7a first-quiet line (imported, not recomputed)")
    print(f"{'asset':5s} {'cells':>6s} {'sel':>6s} {'cover':>7s} {'postX':>7s} "
          f"{'soft':>7s} {'delay_med':>10s} {'delay_p90':>10s}")
    for asset, row in report["sweep7a_first_quiet"].items():
        print(f"{asset:5s} {int(row['cells']):6d} {int(row['selections']):6d} "
              f"{_n(row['coverage'], 7, 3)} {_n(row['post_new_extreme'], 7, 3)} "
              f"{_n(row['soft_hit'], 7, 3)} {_n(row['delay_median_s'], 10, 0)} "
              f"{_n(row['delay_p90_s'], 10, 0)}")
    for name in LINES:
        block = report["random_control"][name]
        print(f"\nCONTROL  random timing, {block['draws']} draws seed "
              f"{block['seed']}, {name} entry law")
        print(f"{'asset':5s} {'cells':>6s} {'entries':>8s} {'cover':>7s} "
              f"{'postX':>7s} {'soft':>7s} {'delay_med':>10s} {'depth_med':>10s}")
        for asset in ASSETS:
            row = block["by_asset"][asset]
            print(f"{asset:5s} {row['cells_scored']:6d} "
                  f"{_n(row['entries_mean'], 8, 1)} "
                  f"{_n(row['coverage_mean'], 7, 3)} "
                  f"{_n(row['post_extension_mean'], 7, 3)} "
                  f"{_n(row['soft_hit_mean'], 7, 3)} "
                  f"{_n(row['delay_median_s_mean'], 10, 0)} "
                  f"{_n(row['depth_median_atr_mean'], 10, 3)}")


def _phase_order(phases: Sequence[str]) -> list[str]:
    """Phase 2 is read first: the adopted judging law says so explicitly."""

    return sorted(phases, key=lambda p: (p != "2", p))


def print_horizons(report: Mapping[str, object]) -> None:
    print(f"\nJUDGING LAW  fixed-horizon extension, {HORIZON_BARS} bars "
          f"({REMAIN_MIN_S} s), by asset")
    print(f"{'line':10s} {'asset':5s} {'n':>5s} {'pX1800_fire':>12s} {'ci_lo':>7s} "
          f"{'ci_hi':>7s} {'pX1800_entry':>13s} {'ci_lo':>7s} {'ci_hi':>7s} "
          f"{'wait_med':>9s} {'wait_p90':>9s} {'firephase':>10s} {'cens_f':>7s} "
          f"{'cens_e':>7s}")
    for name in tuple(LINES) + ("E1ONLY",):
        for asset in ASSETS:
            row = report["horizons"][name]["by_asset"][asset]
            fire, entry = row["postx1800_fire"], row["postx1800_entry"]
            print(f"{name:10s} {asset:5s} {row['n']:5d} "
                  f"{_n(fire['rate'], 12, 3)} {_n(fire['ci_low'], 7, 3)} "
                  f"{_n(fire['ci_high'], 7, 3)} {_n(entry['rate'], 13, 3)} "
                  f"{_n(entry['ci_low'], 7, 3)} {_n(entry['ci_high'], 7, 3)} "
                  f"{_n(row['wait_median_s'], 9, 0)} "
                  f"{_n(row['wait_p90_s'], 9, 0)} "
                  f"{_n(row['fire_phase_median_s'], 10, 0)} "
                  f"{row['fire_window_censored']:7d} "
                  f"{row['entry_window_censored']:7d}")
    print("\nJUDGING LAW  fixed-horizon extension, by phase (phase 2 first)")
    print(f"{'line':10s} {'phase':5s} {'n':>5s} {'pX1800_fire':>12s} "
          f"{'pX1800_entry':>13s} {'wait_med':>9s} {'firephase':>10s}")
    for name in tuple(LINES) + ("E1ONLY",):
        block = report["horizons"][name]["by_phase"]
        for phase in _phase_order(list(block)):
            row = block[phase]
            print(f"{name:10s} {phase:5s} {row['n']:5d} "
                  f"{_n(row['postx1800_fire']['rate'], 12, 3)} "
                  f"{_n(row['postx1800_entry']['rate'], 13, 3)} "
                  f"{_n(row['wait_median_s'], 9, 0)} "
                  f"{_n(row['fire_phase_median_s'], 10, 0)}")
    matched = report["phase_matched_control"]
    print(f"\nCONTROL  phase-time-matched random fire, {matched['draws']} draws, "
          f"seed {matched['seed']}, matched within {matched['match_window_s']} s "
          f"(unmatched cell-draws {matched['cells_unmatched']})")
    print(f"{'asset':5s} {'entries':>8s} {'pX1800_fire':>12s} {'ci_lo':>7s} "
          f"{'ci_hi':>7s} {'firephase':>10s}")
    for asset in ASSETS:
        row = matched["by_asset"][asset]
        fire = row["postx1800_fire"]
        print(f"{asset:5s} {_n(row['entries_mean'], 8, 1)} "
              f"{_n(fire['rate'], 12, 3)} {_n(fire['ci_low'], 7, 3)} "
              f"{_n(fire['ci_high'], 7, 3)} "
              f"{_n(row['fire_phase_median_s'], 10, 0)}")
    print("\nCALIBRATION  bar-level crossing vs episode-level coverage, per stratum")
    print(f"{'stratum':10s} {'bars':>7s} {'crossed':>8s} {'bar_freq':>9s} "
          f"{'cells':>6s} {'cells_x':>8s} {'epi_cross':>10s} {'entries':>8s} "
          f"{'epi_cover':>10s}")
    for key in sorted(report["calibration"]["by_stratum"]):
        row = report["calibration"]["by_stratum"][key]
        print(f"{key:10s} {row['bars_scored']:7d} {row['bars_crossed']:8d} "
              f"{_n(row['bar_crossing_freq'], 9, 4)} {row['cells_scored']:6d} "
              f"{row['cells_with_a_crossing']:8d} "
              f"{_n(row['episode_crossing_rate'], 10, 3)} {row['entries']:8d} "
              f"{_n(row['episode_entry_coverage'], 10, 3)}")
    credit = report["credit"]
    print(f"\nCREDIT VERDICT  composite must beat BOTH controls by "
          f">= {credit['margin']} on fire-stamp postX_1800")
    print(f"{'asset':5s} {'dec':5s} {'composite':>10s} {'ci_lo':>7s} {'ci_hi':>7s} "
          f"{'E1ONLY':>8s} {'d_E1':>7s} {'PHASEM':>8s} {'d_PM':>7s} {'verdict':8s}")
    for asset in ASSETS:
        row = credit["by_asset"][asset]
        comp, lone, matched_row = row["composite"], row["e1only"], row["phasematch"]
        print(f"{asset:5s} {str(row['deciding'])[:5]:5s} "
              f"{_n(comp['rate'], 10, 3)} {_n(comp['ci_low'], 7, 3)} "
              f"{_n(comp['ci_high'], 7, 3)} {_n(lone['rate'], 8, 3)} "
              f"{_n(row['beats']['E1ONLY']['delta'], 7, 3)} "
              f"{_n(matched_row['rate'], 8, 3)} "
              f"{_n(row['beats']['PHASEMATCH']['delta'], 7, 3)} "
              f"{row['verdict']:8s}")
    print(f"CREDIT OVERALL (deciding assets NKD+SI): {credit['overall']}")


def print_stage_b(report: Mapping[str, object], source: str = "stage_b") -> None:
    block = report[source]
    lines = tuple(block.get("priced_lines", LINES))
    print("\nSTAGE B  cash")
    print(f"{'line':9s} {'asset':5s} {'trades':>7s} {'usd/day':>9s} {'rung':>7s} "
          f"{'clears':>7s} {'usd/trd':>9s} {'win':>6s} {'wall':>6s} "
          f"{'mdd_day':>9s} {'mdd_trd':>9s}")
    for name in lines:
        for asset in ASSETS:
            row = block["lines"][name][asset]
            print(f"{name:9s} {asset:5s} {row['trades']:7d} "
                  f"{_n(row['usd_per_asset_day'], 9, 1)} "
                  f"{DAY_RUNG_USD[asset]:7.0f} {str(row['clears_rung']):>7s} "
                  f"{_n(row['usd_per_trade'], 9, 1)} {_n(row['win_rate'], 6, 3)} "
                  f"{_n(row['wall_rate'], 6, 3)} {_n(row['mdd_day_usd'], 9, 0)} "
                  f"{_n(row['mdd_trade_usd'], 9, 0)}")
    print("\nSTAGE B  bleed buckets on THIS policy's entries")
    print(f"{'line':9s} {'asset':5s} {'bucket':24s} {'n':>5s} {'cash_usd':>10s} "
          f"{'usd/day':>9s} {'usd/trd':>9s} {'win':>6s} {'wall':>6s} {'lossshr':>8s}")
    for name in lines:
        for asset in ASSETS:
            table = block["bleed"][name]["by_asset"][asset]["table"]
            for bucket in S7B.BUCKETS:
                row = table[bucket]
                print(f"{name:9s} {asset:5s} {bucket:24s} {row['n']:5d} "
                      f"{_n(row['cash_usd'], 10, 1)} "
                      f"{_n(row['usd_per_asset_day'], 9, 1)} "
                      f"{_n(row['usd_per_trade'], 9, 1)} "
                      f"{_n(row['win_rate'], 6, 3)} {_n(row['wall_rate'], 6, 3)} "
                      f"{_n(row['share_of_gross_loss'], 8, 3)}")
    print("\nSTAGE B  SOFT-WRONG/IN-BUDGET vs sweep 7b baseline")
    print(f"{'asset':5s} {'7b_n':>6s} {'7b_share':>9s} {'7b_wall':>8s} "
          f"{'7b_usd/day':>11s} | " + " | ".join(
              f"{name}_n {name}_share {name}_wall {name}_usd/day" for name in lines))
    for asset in ASSETS:
        base = block["bleed_baseline_7b"][asset]
        cells = [f"{asset:5s} {int(base['n']):6d} "
                 f"{_n(base['share_of_gross_loss'], 9, 3)} "
                 f"{_n(base['wall_rate'], 8, 3)} "
                 f"{_n(base['usd_per_asset_day'], 11, 1)} |"]
        for name in lines:
            row = (block["bleed"][name]["by_asset"][asset]["table"]
                   ["SOFT-WRONG/IN-BUDGET"])
            cells.append(f" {row['n']:5d} {_n(row['share_of_gross_loss'], 9, 3)} "
                         f"{_n(row['wall_rate'], 8, 3)} "
                         f"{_n(row['usd_per_asset_day'], 11, 1)} |")
        print("".join(cells))
    print("\nSTAGE B  engine replay")
    print(f"{'line':9s} {'status':6s} {'label':40s} {'trades':>7s} {'usd/day':>9s} "
          f"{'usd/trd':>9s} {'mdd':>9s} {'skips':>6s}")
    for name in lines:
        row = block["replays"][name]
        print(f"{name:9s} {str(row.get('status')):6s} "
              f"{str(row.get('label', '')):40s} {int(row.get('trades', 0)):7d} "
              f"{_n(row.get('usd_per_asset_day'), 9, 1)} "
              f"{_n(row.get('usd_per_trade'), 9, 1)} "
              f"{_n(row.get('max_drawdown_usd'), 9, 0)} "
              f"{int(row.get('occupancy_or_cap_skips', 0)):6d}")
    print(f"\nSTAGE B  2% adversarial stress (rate {STRESS_RATE})")
    print(f"{'line':9s} {'asset':5s} {'flips':>6s} {'avail':>6s} {'usd/day':>9s} "
          f"{'damage':>10s} {'mdd_day':>9s} {'wall':>6s}")
    for name in lines:
        for asset in ASSETS:
            row = block["stress"][name][asset]
            print(f"{name:9s} {asset:5s} {int(row['flips_applied']):6d} "
                  f"{int(row['flips_available']):6d} "
                  f"{_n(row['usd_per_asset_day'], 9, 1)} "
                  f"{_n(row['damage_usd'], 10, 1)} {_n(row['mdd_day_usd'], 9, 0)} "
                  f"{_n(row['wall_rate'], 6, 3)}")
    null_block = block["null"]
    print(f"\nSTAGE B  block-permutation null, {null_block['draws']} draws, "
          f"seed {null_block['seed']}")
    print(f"{'line':16s} {'obs_asset_mdd':>14s} {'null_mean':>10s} {'p_own':>7s} "
          f"{'p_max_adj':>10s} {'p_pooled_adj':>13s}")
    for key in sorted(null_block["by_line"]):
        row = null_block["by_line"][key]
        print(f"{key:16s} {_n(row['observed_max_asset_mdd_usd'], 14, 0)} "
              f"{_n(row['null_asset_mdd_mean_usd'], 10, 0)} "
              f"{_n(row['p_own'], 7, 3)} {_n(row['p_max_adjusted'], 10, 3)} "
              f"{_n(row['p_pooled_max_adjusted'], 13, 3)}")
    if null_block.get("lines_held_out_empty"):
        print(f"held out (no entries): {null_block['lines_held_out_empty']}")


def print_sweep8b(report: Mapping[str, object]) -> None:
    block = report["sweep8b"]
    print("\n" + "=" * 78)
    print("SWEEP 8b  the E1-ONLY gate priced (one knob off sweep 8: E1 alone fires)")
    print("=" * 78)
    print_stage_a(block, LINES_8B, source="stage_a")
    print(f"\nSWEEP 8b  fixed-horizon extension, {HORIZON_BARS} bars "
          f"({REMAIN_MIN_S} s), by asset")
    print(f"{'line':11s} {'asset':5s} {'n':>5s} {'pX1800_fire':>12s} {'ci_lo':>7s} "
          f"{'ci_hi':>7s} {'pX1800_entry':>13s} {'wait_med':>9s} {'firephase':>10s} "
          f"{'cens_f':>7s} {'cens_e':>7s}")
    for name in LINES_8B:
        for asset in ASSETS:
            row = block["horizons"][name]["by_asset"][asset]
            fire = row["postx1800_fire"]
            print(f"{name:11s} {asset:5s} {row['n']:5d} {_n(fire['rate'], 12, 3)} "
                  f"{_n(fire['ci_low'], 7, 3)} {_n(fire['ci_high'], 7, 3)} "
                  f"{_n(row['postx1800_entry']['rate'], 13, 3)} "
                  f"{_n(row['wait_median_s'], 9, 0)} "
                  f"{_n(row['fire_phase_median_s'], 10, 0)} "
                  f"{row['fire_window_censored']:7d} "
                  f"{row['entry_window_censored']:7d}")
    print("\nSWEEP 8b  fixed-horizon extension, by phase (phase 2 first)")
    print(f"{'line':11s} {'phase':5s} {'n':>5s} {'pX1800_fire':>12s} "
          f"{'pX1800_entry':>13s} {'wait_med':>9s} {'firephase':>10s}")
    for name in LINES_8B:
        table = block["horizons"][name]["by_phase"]
        for phase in _phase_order(list(table)):
            row = table[phase]
            print(f"{name:11s} {phase:5s} {row['n']:5d} "
                  f"{_n(row['postx1800_fire']['rate'], 12, 3)} "
                  f"{_n(row['postx1800_entry']['rate'], 13, 3)} "
                  f"{_n(row['wait_median_s'], 9, 0)} "
                  f"{_n(row['fire_phase_median_s'], 10, 0)}")
    print_stage_b(block, source="stage_b")
    print("\nSWEEP 8b  SWIB vs the sweep-8 composite-gate baseline")
    print(f"{'asset':5s} " + " ".join(f"{n + '_share':>16s} {n + '_wall':>15s}"
                                      for n in tuple(LINES) + LINES_8B))
    for asset in ASSETS:
        cells = [f"{asset:5s} "]
        for name in LINES:
            row = (report["stage_b"]["bleed"][name]["by_asset"][asset]["table"]
                   ["SOFT-WRONG/IN-BUDGET"])
            cells.append(f"{_n(row['share_of_gross_loss'], 16, 3)} "
                         f"{_n(row['wall_rate'], 15, 3)} ")
        for name in LINES_8B:
            row = (block["stage_b"]["bleed"][name]["by_asset"][asset]["table"]
                   ["SOFT-WRONG/IN-BUDGET"])
            cells.append(f"{_n(row['share_of_gross_loss'], 16, 3)} "
                         f"{_n(row['wall_rate'], 15, 3)} ")
        print("".join(cells))
    decision = block["decision"]
    print("\nSWEEP 8b  DECISION TABLE (pre-registered)")
    print(f"  freeze:      {decision['bars']['freeze']}")
    print(f"  interesting: {decision['bars']['interesting']}")
    print(f"{'asset':5s} {'line':11s} {'dec':5s} {'trades':>7s} {'usd/day':>9s} "
          f"{'mddD':>8s} {'mddT':>8s} {'stress':>9s} {'nullp':>7s} {'verdict':16s}")
    for asset in ASSETS:
        for name in LINES_8B:
            row = decision["by_asset"][asset][name]
            print(f"{asset:5s} {name:11s} {str(row['deciding'])[:5]:5s} "
                  f"{int(row['trades']):7d} {_n(row['usd_per_asset_day'], 9, 1)} "
                  f"{_n(row['mdd_day_usd'], 8, 0)} {_n(row['mdd_trade_usd'], 8, 0)} "
                  f"{_n(row['stress_usd_per_asset_day'], 9, 1)} "
                  f"{_n(row['adjusted_null_p'], 7, 3)} {row['verdict']:16s}")
    print("\nSWEEP 8b  BOUNDS FIRED")
    for asset in ASSETS:
        for name in LINES_8B:
            fired = decision["by_asset"][asset][name]["bounds_fired"]
            print(f"{asset:5s} {name:11s} " + ("; ".join(fired) if fired else "none"))
    print(f"\nSWEEP 8b OVERALL {decision['overall']}")


def print_decision(report: Mapping[str, object]) -> None:
    block = report["decision"]
    print("\nDECISION TABLE (pre-registered bounds)")
    print(f"{'asset':5s} {'line':9s} {'dec':4s} {'usd/day':>9s} {'mddD':>7s} "
          f"{'mddT':>7s} {'stress':>9s} {'nullp':>7s} {'postX':>7s} {'cover':>7s} "
          f"{'swib':>7s} {'verdict':16s}")
    for asset in ASSETS:
        for name in LINES:
            row = block["by_asset"][asset][name]
            print(f"{asset:5s} {name:9s} {str(row['deciding'])[:4]:4s} "
                  f"{_n(row['usd_per_asset_day'], 9, 1)} "
                  f"{_n(row['mdd_day_usd'], 7, 0)} {_n(row['mdd_trade_usd'], 7, 0)} "
                  f"{_n(row['stress_usd_per_asset_day'], 9, 1)} "
                  f"{_n(row['adjusted_null_p'], 7, 3)} "
                  f"{_n(row['post_extension'], 7, 3)} {_n(row['coverage'], 7, 3)} "
                  f"{_n(row['swib_loss_share'], 7, 3)} {row['verdict']:16s}")
    print("\nBOUNDS FIRED")
    for asset in ASSETS:
        for name in LINES:
            fired = block["by_asset"][asset][name]["bounds_fired"]
            print(f"{asset:5s} {name:9s} " + ("; ".join(fired) if fired else "none"))
    print(f"\nOVERALL {block['overall']}")


# --------------------------------------------------------------------------
# Selftest.
# --------------------------------------------------------------------------

def _check(name: str, ok: bool, detail: str = "") -> tuple[str, bool, str]:
    return (name, bool(ok), detail)


def _selftest_percentiles() -> list[tuple[str, bool, str]]:
    """Hand-computed E1..E5 and G on a tiny stratum."""

    out: list[tuple[str, bool, str]] = []
    # Stratum samples chosen so every percentile is exact in tenths.
    gaps = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    e1 = ecdf(7.0, gaps)                      # 7 of 10 values are <= 7
    out.append(_check("E1 ecdf", e1 == 0.7, f"{e1}"))
    tape = [10.0, 20.0, 30.0, 40.0]
    e2 = _invert(ecdf(20.0, tape))            # 2 of 4 <= 20 -> 1 - 0.5
    out.append(_check("E2 inverse ecdf", e2 == 0.5, f"{e2}"))
    touches = [0.1, 0.2, 0.3, 0.4, 0.5]
    e3 = ecdf(0.4, touches)                   # 4 of 5
    out.append(_check("E3 ecdf", e3 == 0.8, f"{e3}"))
    ratios = [0.5, 1.0, 1.5, 2.0]
    e4 = ecdf(1.5, ratios)                    # 3 of 4
    out.append(_check("E4 ecdf", e4 == 0.75, f"{e4}"))
    ages = [2.0, 4.0, 6.0, 8.0, 10.0]
    e5 = _invert(ecdf(4.0, ages))             # 2 of 5 <= 4 -> 1 - 0.4
    out.append(_check("E5 inverse ecdf", abs(e5 - 0.6) < 1e-12, f"{e5}"))
    g, present = combine({"E1": e1, "E2": e2, "E3": e3, "E4": e4, "E5": e5})
    expected = (0.7 + 0.5 + 0.8 + 0.75 + 0.6) / 5.0
    out.append(_check("G is the mean of five", present == 5 and abs(g - expected) < 1e-12,
                      f"{g} vs {expected}"))
    g4, present4 = combine({"E1": e1, "E2": e2, "E3": e3, "E4": None, "E5": e5})
    out.append(_check("G with four present", present4 == 4
                      and abs(g4 - (0.7 + 0.5 + 0.8 + 0.6) / 4.0) < 1e-12, f"{g4}"))
    g3, present3 = combine({"E1": e1, "E2": e2, "E3": None, "E4": None, "E5": e5})
    out.append(_check("3-of-5 refuses to score", g3 is None and present3 == 3, f"{g3}"))
    out.append(_check("empty sample gives no percentile", ecdf(1.0, []) is None))
    mixed = [3.0, 1.0, 4.0, 1.0, 5.0, 9.0, 2.0, 6.0]
    ordered = np.sort(np.asarray(mixed, np.float64))
    agree = all(ecdf(float(v), mixed) == ecdf_sorted(float(v), ordered)
                for v in (0.5, 1.0, 2.5, 5.0, 9.0, 10.0))
    out.append(_check("sorted percentile equals the linear one", agree))
    out.append(_check("empty sorted sample gives no percentile",
                      ecdf_sorted(1.0, np.zeros(0)) is None))
    return out


def _selftest_fire() -> list[tuple[str, bool, str]]:
    """The frozen 60th-percentile bar and the 1800 s remaining-time law."""

    out: list[tuple[str, bool, str]] = []
    sample = [float(v) / 10.0 for v in range(1, 11)]     # 0.1 .. 1.0
    bar = float(np.percentile(np.asarray(sample), G_PERCENTILE))
    out.append(_check("stratum bar is p60", abs(bar - 0.64) < 1e-12, f"{bar}"))
    out.append(_check("G above the bar fires", fires(0.70, sample, 3600.0)))
    out.append(_check("G at the bar fires", fires(bar, sample, 3600.0)))
    out.append(_check("G below the bar does not", not fires(0.60, sample, 3600.0)))
    out.append(_check("1799 s left refuses", not fires(0.99, sample, 1799.0)))
    out.append(_check("1800 s left is enough", fires(0.99, sample, 1800.0)))
    out.append(_check("no G refuses", not fires(None, sample, 3600.0)))
    out.append(_check("no stratum sample refuses", not fires(0.99, [], 3600.0)))
    return out


def _fixture_cell(certs_p: Sequence[float], certs_m: Sequence[float],
                  mid: Sequence[float], *, asset: str = "NKD", d8: int = 20220301,
                  phase: str = "0") -> Cell8:  # noqa: D401
    """A hand-built cell with a known extreme, candidate plane and quote path."""

    n = len(mid)
    zeros = np.zeros(n, np.float64)
    rec = S1.CellRec(
        asset=asset, d8=d8, phase=phase, text=f"{asset}/{d8}/{phase}/0",
        phase_open_ts_ns=0, phase_close_ts_ns=(n + 120) * 60 * NANOS_PER_SECOND,
        locked_iid=1, pack_sha256="0" * 64, raw_first=0, k0=0, r0_mid2=0.0,
        legal_from_p=1, legal_from_m=1,
        lat=np.arange(n, dtype=np.int64) * 60 * NANOS_PER_SECOND,
        mid=np.asarray(mid, np.float64), bar_ok=np.ones(n, bool),
        cost=np.full(n, 10.0), cert_p=np.asarray(certs_p, np.float64),
        cert_m=np.asarray(certs_m, np.float64), ok_p=np.ones(n, bool),
        ok_m=np.ones(n, bool), wall_p=np.zeros(n, bool), wall_m=np.zeros(n, bool),
        exit_p=np.arange(n, dtype=np.int64), exit_m=np.arange(n, dtype=np.int64),
        cum_long=zeros, cum_short=zeros, raw_cut=np.zeros(n, np.int64),
        raw_last=np.zeros(n, np.int64))
    geo = S7A.geometry(rec, 100.0)
    star = S2.star_cell(rec, S7A.W_VARIANT, S7A.W_BAND)
    qv = np.full(n, 100.0)
    zside = ZONES.cell_side_zones(rec.mid, geo.new_low, zeros, zeros, zeros,
                                  np.full(n, 10.0), 1, tick2=1.0, atr_mid2=100.0)
    zother = ZONES.cell_side_zones(rec.mid, geo.new_high, zeros, zeros, zeros,
                                   np.full(n, 10.0), -1, tick2=1.0, atr_mid2=100.0)
    sides = {1: side_evidence(rec, geo, 1, qv, zeros, np.full(n, 10.0), zside),
             -1: side_evidence(rec, geo, -1, qv, zeros, np.full(n, 10.0), zother)}
    return Cell8(0, asset, d8, phase, n, rec, geo, star, 100.0, sides)


def _selftest_entry() -> list[tuple[str, bool, str]]:
    """Depth acceptance and rejection, and the opposite-extension cancel."""

    out: list[tuple[str, bool, str]] = []
    # A low at bar 3, then a slow climb.  The zone half-width is 0.15*100 = 15.
    mid = [1000.0, 990.0, 980.0, 900.0, 905.0, 912.0, 930.0, 960.0, 1000.0, 1010.0]
    cell = _fixture_cell([50.0] * 10, [-50.0] * 10, mid)
    prior, _new, _armed = S7A.side_arrays(cell.geo, 1)
    out.append(_check("faded extreme at the fire is the running low",
                      float(prior[6]) == 900.0, f"{prior[6]}"))
    reach4 = depth_atr(mid[4], 900.0, 100.0)
    reach7 = depth_atr(mid[7], 900.0, 100.0)
    out.append(_check("bar 4 is inside 0.15 ATR", abs(reach4 - 0.05) < 1e-12,
                      f"{reach4}"))
    out.append(_check("bar 7 is outside 0.15 ATR", reach7 > DEPTH_ATR, f"{reach7}"))
    bar, depth, miss = entry_after(cell, 1, 4, True)
    out.append(_check("primary takes the in-depth candidate",
                      bar == 4 and miss == "" and depth <= DEPTH_ATR,
                      f"bar={bar} depth={depth} miss={miss}"))
    bar, _depth, miss = entry_after(cell, 1, 7, True)
    out.append(_check("primary abstains when nothing is in depth",
                      bar == -1 and miss == MISS_NO_DEPTH, f"bar={bar} miss={miss}"))
    bar, _depth, miss = entry_after(cell, 1, 7, False)
    out.append(_check("control takes the first candidate regardless",
                      bar == 7 and miss == "", f"bar={bar} miss={miss}"))
    # The opposite side prints a new high at bar 9, between a fire at 8 and the
    # entry that would land at 9; the pending entry must cancel.
    _oprior, opp_new, _oarmed = S7A.side_arrays(cell.geo, -1)
    out.append(_check("fixture has an opposite extreme at bar 9",
                      bool(opp_new[9]), f"{np.flatnonzero(opp_new).tolist()}"))
    cancels = bool(np.any(opp_new[8 + 1: 9 + 1]))
    out.append(_check("opposite extension cancels a pending entry", cancels))
    holds = bool(np.any(opp_new[4 + 1: 4 + 1]))
    out.append(_check("no opposite extreme leaves the entry standing", not holds))

    # resolve() walks the scored list in bar order and takes the FIRST fire.
    scored = [(1, 4, 0.50), (1, 5, 0.90), (1, 6, 0.95)]
    shot, miss = resolve(cell, scored, 0.80, depth_law=False)
    out.append(_check("first supra-threshold bar wins the cell",
                      shot is not None and shot.fire_bar == 5 and miss == "",
                      f"{None if shot is None else shot.fire_bar} miss={miss}"))
    shot, miss = resolve(cell, scored, 0.99, depth_law=False)
    out.append(_check("no bar clears the bar -> no_fire",
                      shot is None and miss == MISS_NO_FIRE, f"miss={miss}"))
    shot, miss = resolve(cell, [(1, 7, 0.95)], 0.80, depth_law=True)
    out.append(_check("a fire with nothing in depth abstains",
                      shot is None and miss == MISS_NO_DEPTH, f"miss={miss}"))
    return out


def _selftest_horizon() -> list[tuple[str, bool, str]]:
    """The fixed 1800 s window, its censoring flag, and the credit arithmetic."""

    out: list[tuple[str, bool, str]] = []
    out.append(_check("horizon is 30 bars", HORIZON_BARS == 30, f"{HORIZON_BARS}"))
    # A long cell whose only new low after bar 3 lands at bar 50: inside the
    # open-ended window from a fire at bar 10, outside the fixed 30-bar one.
    mid = [1000.0 - v for v in range(4)] + [1000.0] * 46 + [800.0] + [900.0] * 10
    cell = _fixture_cell([50.0] * len(mid), [-50.0] * len(mid), mid)
    _prior, new_ext, _armed = S7A.side_arrays(cell.geo, 1)
    lows = np.flatnonzero(new_ext).tolist()
    out.append(_check("fixture prints its late low at bar 50", 50 in lows, f"{lows}"))
    shot = _finish(cell, 1, 10, 12, 0.9, 0.05)
    out.append(_check("open-ended postX sees the late extreme", shot.post_extreme))
    out.append(_check("fixed-horizon postX from the fire does not",
                      not shot.postx1800_fire, f"{shot.postx1800_fire}"))
    out.append(_check("the fire's 30-bar window was fully observable",
                      shot.fire_full_window))
    near = _finish(cell, 1, 45, 46, 0.9, 0.05)
    out.append(_check("a fire 5 bars before the extreme does see it",
                      near.postx1800_fire, f"{near.postx1800_fire}"))
    out.append(_check("a window running past the cell end is flagged censored",
                      not near.fire_full_window, f"{near.fire_full_window}"))
    out.append(_check("fire phase seconds are bar*60", shot.fire_phase_s == 600,
                      f"{shot.fire_phase_s}"))
    out.append(_check("phase 2 is ordered first",
                      _phase_order(["0", "1", "2"])[0] == "2",
                      f"{_phase_order(['0', '1', '2'])}"))
    # The credit law: strictly LOWER extension by at least the margin.
    out.append(_check("an exact 0.05 edge passes despite float error",
                      clears_margin(0.70 - 0.65), f"{0.70 - 0.65!r}"))
    out.append(_check("a 0.04 edge fails", not clears_margin(0.69 - 0.65)))
    out.append(_check("a negative edge fails", not clears_margin(-0.20)))
    return out


def _selftest_bucket() -> list[tuple[str, bool, str]]:
    """One bleed-bucket assignment on a hand-built entry."""

    out: list[tuple[str, bool, str]] = []
    mid = [1000.0, 990.0, 980.0, 900.0, 905.0, 912.0, 930.0, 960.0, 1000.0, 1010.0]
    # Long REM stays positive at bar 4 and Delta* points long, so the entry is
    # RIGHT; the low terminal is bar 3 and bar 4 is one minute later, so the
    # 45-minute NKD budget is not breached.
    cell = _fixture_cell([200.0] * 10, [-200.0] * 10, mid)
    shot = _finish(cell, 1, 4, 4, 0.9, 0.05)
    out.append(_check("REM positive at the entry bar",
                      float(cell.star.rem(1)[4]) > 0.0, f"{cell.star.rem(1)[4]}"))
    out.append(_check("side agrees with Delta*", shot.side_ok is True,
                      f"{shot.side_ok} sign={cell.star.sign[4]}"))
    bucket = bucket_of(shot, cell)
    out.append(_check("RIGHT/IN-BUDGET assigned", bucket == "RIGHT/IN-BUDGET", bucket))
    dead = _fixture_cell([-200.0] * 10, [200.0] * 10, mid)
    dead_shot = _finish(dead, 1, 4, 4, 0.9, 0.05)
    out.append(_check("non-positive REM buckets HARD-WRONG",
                      bucket_of(dead_shot, dead).startswith("HARD-WRONG"),
                      bucket_of(dead_shot, dead)))
    late_shot = _finish(cell, 1, 4, 9, 0.9, 0.05)
    late_bucket = bucket_of(late_shot, cell)
    out.append(_check("a 6-minute-old entry is still IN-BUDGET for NKD",
                      late_bucket.endswith("IN-BUDGET"), late_bucket))
    return out


def _selftest_walkforward() -> list[tuple[str, bool, str]]:
    """The calibration case the mutant must flip: prior-only vs day-inclusive."""

    out: list[tuple[str, bool, str]] = []
    stratum = Stratum()
    stratum.prior["gap"] = [1.0, 2.0, 3.0, 4.0]
    stratum.pending["gap"] = [100.0, 200.0]
    honest = ecdf(50.0, stratum.prior["gap"])
    stratum.flush()
    peeked = ecdf(50.0, stratum.prior["gap"])
    out.append(_check("prior-only percentile", honest == 1.0, f"{honest}"))
    out.append(_check("day-inclusive percentile differs",
                      peeked is not None and abs(peeked - 4.0 / 6.0) < 1e-12,
                      f"{peeked}"))
    out.append(_check("the two readings disagree", honest != peeked,
                      f"{honest} vs {peeked}"))

    # THE MUTANT'S TARGET.  The fixture cell prints same-side extremes at bars
    # 1, 2, 3 and an opposite extreme run at 8, 9, so its own gap contributions
    # are 1-bar gaps.  Honestly banked, they are invisible to the day that
    # produced them and the percentile of a 5-bar gap against a stratum of
    # {10, 20, 30, 40} stays 0.0.  Under gate_peeks_forward they are already in
    # the sample when the day is scored, and the reading moves.
    mid = [1000.0, 990.0, 980.0, 900.0, 905.0, 912.0, 930.0, 960.0, 1000.0, 1010.0]
    cell = _fixture_cell([50.0] * 10, [-50.0] * 10, mid)
    live = Stratum()
    live.prior["gap"] = [10.0, 20.0, 30.0, 40.0]
    before = ecdf(5.0, live.prior["gap"])
    prepare_day(live, [cell])
    after = ecdf(5.0, live.prior["gap"])
    out.append(_check("the day's own gaps exist to leak",
                      len(live.pending["gap"]) + len(live.prior["gap"]) > 4,
                      f"pending={live.pending['gap']}"))
    out.append(_check("MUTANT TARGET: scoring-day evidence stays out of the CDF",
                      after == before,
                      f"{before} -> {after}"))
    return out


def _selftest_walkforward_run() -> list[tuple[str, bool, str]]:
    """The gate must actually start scoring: the calibration cannot deadlock.

    The fire bar is a percentile of PRIOR-day G, and G is produced by scoring.
    If a cell were scored only once a prior G sample existed, no cell could ever
    produce the first sample and the whole sweep would abstain everywhere.  This
    case runs the real loop over enough synthetic days to cross both floors.
    """

    out: list[tuple[str, bool, str]] = []
    # A low at bar 3 that is then hovered on, so touches, episodes and gaps all
    # exist; every day is the same shape, which is all the calibration needs.
    mid = [1000.0, 995.0, 990.0, 900.0, 901.0, 900.5, 901.0, 902.0, 905.0,
           930.0, 960.0, 1000.0, 1010.0]
    days = MIN_PRIOR_DAYS + 4
    cells = [_fixture_cell([200.0] * len(mid), [-200.0] * len(mid), mid,
                           d8=20220300 + day) for day in range(1, days + 1)]
    for position, cell in enumerate(cells):
        cell.position = position
    run = run_gate(cells)
    early = [tag for tag in run.misses["PRIMARY"]
             if int(tag.split("/")[1]) - 20220300 <= MIN_PRIOR_DAYS]
    out.append(_check("days inside the calibration floor never score",
                      len(early) >= MIN_PRIOR_DAYS, f"{len(early)}"))
    out.append(_check("the gate does start scoring (no calibration deadlock)",
                      len(run.pool) > 0, f"scored cells={len(run.pool)}"))
    out.append(_check("scored cells carry G values",
                      any(len(v) for v in run.pool.values()),
                      f"{ {k: len(v) for k, v in run.pool.items()} }"))
    # Both control paths consume the scored rows, so they are exercised here:
    # a shape change in the pool must fail in the suite, not in the corpus run.
    try:
        random_control(cells, run.pool, depth_law=True, draws=2)
        phase_matched_control(cells, run.pool, run.shots["PRIMARY"],
                              depth_law=True, draws=2)
        ran = True
        detail = ""
    except Exception as error:                       # noqa: BLE001
        ran = False
        detail = f"{type(error).__name__}: {error}"
    out.append(_check("both random controls run on the scored pool", ran, detail))

    # SWEEP 8b's identity requirement: the priced E1PRIMARY line must be the
    # SAME firing law the credit control measured, or 8b would be pricing a
    # different gate than the one sweep 8 reported as beating the composite.
    stamp = lambda rows: sorted(  # noqa: E731
        (r.cell, r.side, r.fire_bar, r.entry_bar) for r in rows)
    out.append(_check("8b E1PRIMARY fires match the credit control exactly",
                      stamp(run.shots["E1PRIMARY"]) == stamp(run.shots["E1ONLY"]),
                      f"{len(run.shots['E1PRIMARY'])} vs "
                      f"{len(run.shots['E1ONLY'])}"))
    out.append(_check("8b E1CONTROL shares the E1 fire bars",
                      {(r.cell, r.side, r.fire_bar)
                       for r in run.shots["E1CONTROL"]}
                      >= {(r.cell, r.side, r.fire_bar)
                          for r in run.shots["E1PRIMARY"]},
                      f"{len(run.shots['E1CONTROL'])} entries"))
    return out


def selftest() -> int:
    cases: list[tuple[str, bool, str]] = []
    cases.extend(_selftest_percentiles())
    cases.extend(_selftest_fire())
    cases.extend(_selftest_entry())
    cases.extend(_selftest_horizon())
    cases.extend(_selftest_bucket())
    cases.extend(_selftest_walkforward())
    cases.extend(_selftest_walkforward_run())
    mutant = _mutant()
    failed = [row for row in cases if not row[1]]
    for name, ok, detail in cases:
        print(f"{'ok  ' if ok else 'FAIL'}  {name}" + (f"   [{detail}]" if detail else ""))
    print(f"\nselftest: {len(cases) - len(failed)}/{len(cases)} green"
          + (f"  mutant={mutant}" if mutant else ""))
    if failed:
        return 1
    if mutant:
        # A mutant that leaves every case green is a mutant nothing tests.
        print(f"DEAD: mutant {mutant} left every sweep-8 case green")
        return 1
    return 0


# --------------------------------------------------------------------------
# Main.
# --------------------------------------------------------------------------

def write_report(report: Mapping[str, object]) -> None:
    OUT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True,
                                   default=_json_default) + "\n")


def _json_default(value: object) -> object:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    raise TypeError(f"unserializable: {type(value)}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--log", action="store_true")
    parser.add_argument("--assets", nargs="*", default=list(ASSETS))
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    started = time.time()
    mutant = _mutant()
    cells, days, skipped = build_cells(tuple(args.assets))
    records, _days = S1.load_cache()
    explore_days = S1._explore_days(ASSETS)
    run = run_gate(cells)
    lines = run.shots
    scored_ref = run.scored_cells
    stage_a_block: dict[str, object] = {}
    random_block: dict[str, object] = {}
    horizons: dict[str, object] = {}
    for name in tuple(LINES) + ("E1ONLY",):
        stage_a_block[name] = stage_a(run.shots[name], run.misses[name], scored_ref)
        horizons[name] = horizon_block(run.shots[name])
    for name in LINES:
        random_block[name] = random_control(cells, run.pool,
                                            depth_law=(name == "PRIMARY"))
    report: dict[str, object] = {
        "schema": "QRE2MILLSWEEP8", "tier": "exploratory", "mutant": mutant,
        "spec_sha": SPEC_SHA, "code_sha": code_sha(), "split_sha": S1.split_sha(),
        "outcome_law_sha": S1.outcome_law_sha(), "seed": SEED,
        "parent_trial": _parent_trial(),
        "asset_days": days, "skipped_no_context": skipped,
        "cells": {asset: sum(1 for c in cells if c.asset == asset)
                  for asset in ASSETS},
        "cells_scored": scored_ref,
        "gate": {"quiet_min_bars": QUIET_MIN_BARS, "g_percentile": G_PERCENTILE,
                 "min_components": MIN_COMPONENTS, "min_prior_days": MIN_PRIOR_DAYS,
                 "depth_atr": DEPTH_ATR, "depth_window_bars": DEPTH_WINDOW_BARS,
                 "remaining_min_s": REMAIN_MIN_S},
        "stage_a": stage_a_block,
        "random_control": random_block,
        "horizons": horizons,
        "horizon_bars": HORIZON_BARS,
        "phase_matched_control": phase_matched_control(
            cells, run.pool, run.shots["PRIMARY"], depth_law=True),
        "calibration": crossing_stats(run, cells),
        "sweep7a_first_quiet": sweep7a_reference(),
    }
    report["credit"] = credit_verdict(report)
    report["stage_b"] = stage_b(
        {name: lines[name] for name in LINES}, cells, records, days, scored_ref,
        explore_days)
    report["decision"] = decide(report)
    # SWEEP 8b: the same walk-forward pass, the E1-ONLY firing law priced under
    # both entry laws.  Its null pool spans all four priced lines, so the
    # max-statistic adjustment covers everything either sweep priced.
    report["sweep8b"] = {
        "knob": "E1-ONLY fires (sweep 8 fires the 5-evidence composite G)",
        "lines": list(LINES_8B), "null_lines": list(NULL_LINES_8B),
        "stage_a": {name: stage_a(run.shots[name], run.misses[name], scored_ref)
                    for name in LINES_8B},
        "horizons": {name: horizon_block(run.shots[name]) for name in LINES_8B},
        "stage_b": stage_b(
            {name: run.shots[name] for name in NULL_LINES_8B}, cells, records,
            days, scored_ref, explore_days, names=NULL_LINES_8B),
    }
    report["sweep8b"]["decision"] = decide_8b(report)
    report["log"] = log_rows(report)
    report["log_8b"] = log_rows_8b(report)
    report["wall_seconds"] = round(time.time() - started, 1)
    write_report(report)
    print_stage_a(report)
    print_controls(report)
    print_horizons(report)
    print_stage_b(report)
    print_decision(report)
    print_sweep8b(report)
    if args.log and not mutant:
        written = S1.append_log(report["log"])
        print(f"\nappended {written} rows to {LOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
