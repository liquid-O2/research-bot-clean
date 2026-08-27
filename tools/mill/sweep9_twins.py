#!/usr/bin/env python3
"""Sweep 9 of the side-resolution mill: the matched-history survival certificate.

Exploratory tier, NO CASH.  Sweep 8 KILLed the five-evidence composite and
sweep 8b KILLed the E1-only gate as a priced line, so the open question is no
longer which score to fire: it is whether the allowed causal state can identify
1800 s survival at deployable coverage AT ALL.  This file answers that with a
matched-history certificate and nothing else.  It can route one regime-scoped
successor or close transformations of the current causal state.  It cannot
promote a trading line, and it never opens cash.

The contract is the fenced dispatch block in
``.audit/briefs/mill-sweep8-sol-out.md`` section "If Sweep 8 kills", read
against the charter sections "Sweep 8 ruling" and "Sweep 8b ruling" in
``.audit/briefs/mill-side-resolution.md``.

Machinery is imported, never re-implemented: sweep 1's ``CellRec`` cache,
``wilson`` and ``append_log``; sweep 2's ``star_cell``; sweep 7a's zone
geometry, running extremes and CLEAR candidate plane; sweep 8's ``build_cells``,
``Stratum``, ``prepare_day``, ``score_bar`` (E1..E5 verbatim), ``score_cell``
and ``depth_atr``; the mill context store for ``ATR14_prev`` and the day's
forecast variance; ``mill_flow`` for the tape series and ``mill_flow_zones``
for the zone episodes.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import datetime as dt
import json
import math
import os
from pathlib import Path
import sys
from typing import Mapping, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from engine.entry_v2.confirmation_types import NANOS_PER_SECOND

import mill as M  # noqa: F401  (the loader package the caches hang off)
import context as CTX
import flow as FLOW  # noqa: F401  (loaded through sweep 8's build_cells)
import flow_zones as ZONES  # noqa: F401
import sweep1 as S1
import sweep2 as S2  # noqa: F401  (star_cell rides inside Cell8)
import sweep3 as S3
import sweep7a as S7A
import sweep8 as S8

# --------------------------------------------------------------------------
# The law, registered before anything is read.
# --------------------------------------------------------------------------

SPEC = """QRE2MILLSWEEP9
tier=exploratory; EXPLORE-only; NO CASH of any kind.  Can route one scoped
  successor or close the current causal state; cannot promote a line.  Parent =
  sweep8b-004, the hypothesis-log tail at registration.
DATA LAW.  EXPLORE days only, off the existing mill candidate plane, context
  cache and flow-zone cache.  HOLD, 2021, 2025, teacher labels, late stores,
  packs and every sealed R4mem field stay shut.  Only completed bars and facts
  available at the decision timestamp are read.  ONE ROW IS ONE DISTINCT IN-ZONE
  CLEAR CANDIDATE at its own decision timestamp: a fade-side CLEAR candidate bar
  (sweep 1's make_entry legality) whose decision quote sits within 0.15 *
  ATR14_prev of the side's running extreme.  A row requires the side's extreme
  age >= 300 s, phase time remaining >= 1800 s, and a tradeable bar.  Candidate
  identity is (side, decision mid2, running-extreme mid2); the FIRST bar
  carrying an identity keeps the row and later repeats of the same identity in
  the same cell and side are dropped.
LABEL.  Y1800 = 1 when NO same-side new extreme prints in the next 1800 s
  (30 completed bars) after the decision bar, else 0.  postX_1800 = 1 - mean
  Y1800.  Rows whose 1800 s window runs past phase close are not admitted.
  Through-close terminality is carried as a SECONDARY column only.  Neither
  label is ever a feature.
FEATURE VIEWS, frozen.  CLOCK = asset, phase, phase time remaining, phase
  elapsed; matching and control only, NOT eligible for a SURVIVOR letter.  S8 =
  E1..E5 exactly as sweep 8 computes them (imported score_bar), plus candidate
  ordinal since the last same-side extreme and ATR-normalised distance from the
  running extreme.  SEQUENCE = extreme age, prior same-side extreme count, the
  last three same-side interarrival gaps, the last-10-minute quote and volume
  ratios, the current gap ratio, opposite-side extreme recency, and the in-zone
  candidate ordinal.  UNION = S8 union SEQUENCE.  No fitted flow composite.
WALK-FORWARD LAW.  Every continuous field is scaled (mean/sd) from strictly
  earlier EXPLORE days inside the row's own (asset, phase) stratum; a field
  missing at a row scales to 0, the prior-day mean.  A twin must share asset and
  phase exactly, sit within 300 s on BOTH phase elapsed and phase time
  remaining, and come from a strictly earlier day - which also forbids a twin
  from the same asset-day.  Nearest twin is Euclidean over the view's own
  scaled fields (for CLOCK, over the two scaled clock fields).  Risk = 1 - twin
  label; the deciding estimator is the fixed 5-nearest-neighbour mean risk, and
  the 1-NN line is reported beside it.  The selective bar is calibrated inside
  each (asset, phase) stratum on strictly prior days as the smallest risk
  threshold reaching 0.35 prior-day cell coverage.  Sweep 8's laws carry over
  unchanged: both sides monitored, FIRST FIRE wins the cell, one entry per
  cell, and a pending entry cancelled by an opposite-side new extreme between
  the fire and the entry - a window that is empty by construction here, because
  the row IS the entry.  A cell is CERTIFIABLE only under sweep 8's arming: at
  least 20 strictly-prior EXPLORE days in the stratum and a non-empty prior-day
  G and E1 sample.  Coverage denominators are certifiable cells.
REGIME CUT.  The existing causal ratio: running mid range at the bar in USD
  over sqrt(the day's forecast variance) from the context cache.  Balance /
  middle / trend tercile edges are fitted per asset on strictly earlier days.
  Cell coverage under a regime is measured over ALL certifiable cells, not over
  the admitted regime's cells.
CONTROLS AND NULL.  Control one, E1ONLY: select on E1 alone against a
  prior-day bar calibrated to the same 0.35 cell coverage, same first-fire and
  one-per-cell law.  Control two, PHASEMATCH: 50 seeded draws that pick, per
  certifiable cell, a random eligible row within 300 s of phase-elapsed of a
  randomly drawn real selection of that asset.  Null: Y1800 permuted by
  asset-day blocks inside (asset, phase, regime), 1000 draws, the row sets held
  fixed; the statistic is min(postX(E1ONLY) - postX(selected), postX(PHASEMATCH)
  - postX(selected)); the max statistic runs over NKD, SI, the four views and
  the four cuts (pooled plus the three regimes - pooled is carried inside the
  family so the pooled bound is adjusted too, which is strictly conservative).
  Paired day-block 95 % intervals come from 1000 asset-day bootstrap draws.
  Every draw is seeded 20260827.
METRICS, per asset and per view, pooled first then the three frozen regimes:
  selected cell coverage, postX_1800, the delta against both controls, the
  day-block 95 % interval on each delta, adjusted null p, median nearest-twin
  distance, label disagreement among the closest 35 % of twins with its Wilson
  interval, candidate availability, and p90 decision delay.  HG is REPORT-ONLY.
BOUNDS.  SURVIVOR on a deciding asset and eligible view: coverage >= 0.35,
  postX_1800 <= 0.25, improvement over BOTH controls >= 0.05, both paired lower
  bounds > 0, adjusted p <= 0.05.  REGIME_SURVIVOR: the pooled line misses, one
  frozen regime meets every SURVIVOR bound at >= 0.35 OVERALL coverage, and it
  leads the other regimes by >= 0.10 with adjusted p <= 0.05; it routes exactly
  that view and regime to one scoped survival unit.  CERTIFICATE: every view
  has postX_1800 > 0.30 at 0.35 coverage, every improvement upper bound < 0.05,
  and closest-twin disagreement has a 95 % lower bound >= 0.35 on both NKD and
  SI; it closes transformations of the current causal state and says nothing
  about feeds or markets it cannot see.  UNRESOLVED is the interval between
  those bounds and is never priced.
MUTANT QRE2_MILL_S9_MUTANT=next_gap_peek adds the bars-to-the-NEXT-same-side-
  extreme as a feature of every eligible view, which is the label read forward.
  It must turn the selftest red.
"""

ASSETS = S1.ASSETS
DECIDING = ("NKD", "SI")
REPORT_ONLY = ("HG",)
BAR_SECONDS = S1.BAR_SECONDS
SEED = 20260827

# Frozen constants.  Every one is in the dispatch text; none is swept.
QUIET_MIN_S = 300
REMAIN_MIN_S = 1800
HORIZON_BARS = REMAIN_MIN_S // BAR_SECONDS      # 30 completed bars
DEPTH_ATR = S8.DEPTH_ATR                        # 0.15, the in-zone band
MIN_PRIOR_DAYS = S8.MIN_PRIOR_DAYS              # 20
TAPE_WINDOW_BARS = S8.TAPE_WINDOW_BARS          # 10
CLOCK_WINDOW_S = 300
KNN = 5
COVERAGE_TARGET = 0.35
CONTROL_DRAWS = 50
NULL_DRAWS = 1000
BOOT_DRAWS = 1000

COVERAGE_FLOOR = 0.35
POSTX_CEILING = 0.25
IMPROVE_MIN = 0.05
NULL_CEILING = 0.05
REGIME_LEAD = 0.10
CERT_POSTX_FLOOR = 0.30
CERT_IMPROVE_UPPER = 0.05
CERT_DISAGREE_FLOOR = 0.35
DISAGREE_SHARE = 0.35

CLOCK_FIELDS = ("elapsed_s", "remaining_s")
S8_FIELDS = ("E1", "E2", "E3", "E4", "E5", "cand_ordinal", "depth_atr")
SEQ_FIELDS = ("extreme_age_s", "prior_ext_count", "gap1", "gap2", "gap3",
              "quote_ratio10", "vol_ratio10", "gap_ratio", "opp_age_s",
              "inzone_ordinal")
PEEK_FIELD = "next_gap_bars"
FIELDS = CLOCK_FIELDS + S8_FIELDS + SEQ_FIELDS + (PEEK_FIELD,)
FIELD_INDEX = {name: index for index, name in enumerate(FIELDS)}

VIEWS = ("CLOCK", "S8", "SEQUENCE", "UNION")
ELIGIBLE_VIEWS = ("S8", "SEQUENCE", "UNION")
REGIMES = ("balance", "middle", "trend")
CUTS = ("pooled",) + REGIMES
# Sweep 7a put most continuation risk in phase 2, so the phases are reported
# beside the frozen regimes.  They are REPORTING cuts: the spec's max-statistic
# family is the pooled line and the three regimes, and stays that way.
PHASE_CUTS = ("phase0", "phase1", "phase2")
ALL_CUTS = CUTS + PHASE_CUTS
CONTROLS = ("E1ONLY", "PHASEMATCH")

FAMILY = "F6-TWINS"
PARENT_TRIAL = "sweep8b-004"
SELECTION_RULE = "none: frozen views, frozen bar target, no fit"

MUTANT_ENV = "QRE2_MILL_S9_MUTANT"
MUTANT_PEEK = "next_gap_peek"
MUTANTS = (MUTANT_PEEK,)

OUT_PATH = ROOT / ".audit/mill-sweep9-twins.json"
LOG_PATH = S1.LOG_PATH
SWEEP8_PATH = ROOT / ".audit/mill-sweep8.json"


class SweepRefusal(RuntimeError):
    pass


SPEC_SHA = S1._sha_text(SPEC)


def code_sha() -> str:
    return S1._sha_file(Path(__file__).resolve())


def _mutant() -> str:
    name = os.environ.get(MUTANT_ENV, "")
    if name and name not in MUTANTS:
        raise SweepRefusal(f"unknown sweep-9 mutant: {name}")
    return name


def view_fields(view: str, mutant: str = "") -> tuple[str, ...]:
    """The fields a view's TWIN DISTANCE runs over, under the frozen law."""

    if view == "CLOCK":
        return CLOCK_FIELDS
    if view == "S8":
        base = S8_FIELDS
    elif view == "SEQUENCE":
        base = SEQ_FIELDS
    elif view == "UNION":
        base = tuple(dict.fromkeys(S8_FIELDS + SEQ_FIELDS))
    else:
        raise SweepRefusal(f"unknown view: {view}")
    return base + ((PEEK_FIELD,) if mutant == MUTANT_PEEK else ())


# --------------------------------------------------------------------------
# The row plane.
# --------------------------------------------------------------------------

@dataclass(slots=True)
class Plane:
    """Every admitted row as parallel arrays, plus the coverage denominators."""

    asset: np.ndarray
    phase: np.ndarray
    d8: np.ndarray
    cell: np.ndarray
    side: np.ndarray
    bar: np.ndarray
    elapsed: np.ndarray
    remaining: np.ndarray
    raw: np.ndarray                 # (N, len(FIELDS))
    y1800: np.ndarray               # 1 = survived the fixed horizon
    y_close: np.ndarray             # secondary: survived through phase close
    regime_ratio: np.ndarray
    delay_s: np.ndarray             # decision minus the side's TRUE terminal
    certifiable: dict[str, int] = field(default_factory=dict)
    cells_total: dict[str, int] = field(default_factory=dict)
    asset_days: dict[str, int] = field(default_factory=dict)
    counters: dict[str, int] = field(default_factory=dict)
    # Certifiable cells per (asset, phase, day): the coverage denominator the
    # selective bar is calibrated against, so the prior-day target and the
    # reported coverage are the same object.
    stratum_day_cells: dict[tuple[str, str, int], int] = field(default_factory=dict)

    @property
    def n(self) -> int:
        return int(len(self.asset))

    def stratum_keys(self) -> np.ndarray:
        return np.asarray([f"{a}/{p}" for a, p in zip(self.asset, self.phase)])

    def day_keys(self) -> np.ndarray:
        return np.asarray([f"{a}/{d}" for a, d in zip(self.asset, self.d8)])

    def cell_keys(self) -> np.ndarray:
        return np.asarray([f"{a}/{d}/{p}/{c}" for a, d, p, c
                           in zip(self.asset, self.d8, self.phase, self.cell)])


def _tape_ratios(qv_quotes: np.ndarray, qv_vol: np.ndarray, bar: int
                 ) -> tuple[float, float]:
    """Last-10-bar tape against this cell's own running mean, causally."""

    lower = max(0, bar + 1 - TAPE_WINDOW_BARS)
    span = float(bar + 1 - lower)
    out: list[float] = []
    for series in (qv_quotes, qv_vol):
        recent = float(series[lower: bar + 1].sum()) / span
        base = float(series[: bar + 1].mean()) if bar >= 0 else 0.0
        out.append(recent / base if base > 0.0 else float("nan"))
    return out[0], out[1]


def _last_gaps(marks: np.ndarray, bar: int) -> tuple[float, float, float]:
    """The last three COMPLETED same-side interarrival gaps at ``bar``."""

    seen = marks[marks <= bar]
    if len(seen) < 2:
        return (float("nan"),) * 3
    gaps = np.diff(seen).astype(np.float64)
    out = [float("nan")] * 3
    for position in range(min(3, len(gaps))):
        out[position] = float(gaps[-1 - position])
    return out[0], out[1], out[2]


def build_plane(cells: Sequence[S8.Cell8], forecast: Mapping[tuple[str, int], float],
                tape: Mapping[int, tuple[np.ndarray, np.ndarray]],
                mutant: str = "") -> Plane:
    """The walk-forward pass that emits the row plane and arms the cells.

    The day loop is sweep 8's, step for step: bank the day's contributions,
    refuse the cell until the stratum has 20 prior days and a non-empty prior G
    and E1 sample, score the cell (which is what banks G and E1 for the next
    day), and only then read the day's own candidates.  That is what makes the
    certifiable-cell count reproduce sweep 8's ``cells_scored`` exactly.
    """

    strata: dict[tuple[str, str], S8.Stratum] = {}
    by_day: dict[tuple[str, int], list[S8.Cell8]] = {}
    for cell in cells:
        by_day.setdefault((cell.asset, cell.d8), []).append(cell)

    rows: list[dict[str, object]] = []
    certifiable = {asset: 0 for asset in ASSETS}
    stratum_day_cells: dict[tuple[str, str, int], int] = {}
    cells_total = {asset: 0 for asset in ASSETS}
    counters = {"candidates_seen": 0, "dropped_identity": 0, "dropped_window": 0,
                "dropped_zone": 0, "dropped_eligibility": 0, "cells_with_rows": 0,
                "cancelled": 0}
    for cell in cells:
        cells_total[cell.asset] += 1

    for asset, d8 in sorted(by_day):
        for cell in by_day[(asset, d8)]:
            S8.prepare_day(strata.setdefault((cell.asset, cell.phase), S8.Stratum()),
                           [cell])
        for cell in by_day[(asset, d8)]:
            stratum = strata[(cell.asset, cell.phase)]
            if stratum.prior_days < MIN_PRIOR_DAYS:
                continue
            scored = S8.score_cell(cell, stratum)
            stratum.pending["G"].extend(row[2] for row in scored)
            stratum.pending["E1"].extend(row[3] for row in scored
                                         if np.isfinite(row[3]))
            if not stratum.prior["G"] or not stratum.prior["E1"]:
                continue
            certifiable[cell.asset] += 1
            slot = (cell.asset, cell.phase, cell.d8)
            stratum_day_cells[slot] = stratum_day_cells.get(slot, 0) + 1
            variance = forecast.get((cell.asset, cell.d8))
            mid = np.asarray(cell.rec.mid, np.float64)
            run_high = np.maximum.accumulate(mid)
            run_low = np.minimum.accumulate(mid)
            span_usd = (run_high - run_low) / S3.usd_to_mid2(cell.asset)
            open_ns = int(cell.rec.phase_open_ts_ns)
            quote_series, vol_series = tape[cell.position]
            produced = 0
            for side in (1, -1):
                ev = cell.sides[side]
                prior, new_ext, _armed = S7A.side_arrays(cell.geo, side)
                marks = np.flatnonzero(new_ext)
                terminal = S7A.terminal_bar(cell.geo, side)
                cands = S7A.candidate_bars(cell.rec, side)
                seen: set[tuple[int, int]] = set()
                all_ordinal = 0
                zone_ordinal = 0
                last_mark = -1
                for raw_bar in cands:
                    bar = int(raw_bar)
                    if bar < 1 or bar >= cell.n:
                        continue
                    counters["candidates_seen"] += 1
                    mark = int(marks[marks <= bar][-1]) if len(marks[marks <= bar]) else -1
                    if mark != last_mark:
                        # The ordinal resets on every same-side new extreme.
                        all_ordinal = 0
                        zone_ordinal = 0
                        seen = set()
                        last_mark = mark
                    all_ordinal += 1
                    if not bool(ev.eligible[bar]) or float(ev.remaining_s[bar]) < REMAIN_MIN_S:
                        counters["dropped_eligibility"] += 1
                        continue
                    reach = S8.depth_atr(float(cell.rec.mid[bar]), float(prior[bar]),
                                         cell.atr_mid2)
                    if not reach <= DEPTH_ATR:
                        counters["dropped_zone"] += 1
                        continue
                    zone_ordinal += 1
                    identity = (int(cell.rec.mid[bar]), int(prior[bar]))
                    if identity in seen:
                        counters["dropped_identity"] += 1
                        continue
                    seen.add(identity)
                    stop = bar + 1 + HORIZON_BARS
                    if stop > cell.n:
                        counters["dropped_window"] += 1
                        continue
                    parts = S8.score_bar(cell, side, bar, stratum)[2]
                    quotes, vols = _tape_ratios(quote_series, vol_series, bar)
                    gap1, gap2, gap3 = _last_gaps(marks, bar)
                    ahead = marks[marks > bar]
                    values = {
                        "elapsed_s": float((int(cell.rec.lat[bar]) - open_ns)
                                           / NANOS_PER_SECOND),
                        "remaining_s": float(ev.remaining_s[bar]),
                        "E1": parts["E1"], "E2": parts["E2"], "E3": parts["E3"],
                        "E4": parts["E4"], "E5": parts["E5"],
                        "cand_ordinal": float(all_ordinal),
                        "depth_atr": float(reach),
                        "extreme_age_s": float(ev.quiet_age[bar]) * BAR_SECONDS,
                        "prior_ext_count": float(len(marks[marks <= bar])),
                        "gap1": gap1, "gap2": gap2, "gap3": gap3,
                        "quote_ratio10": quotes, "vol_ratio10": vols,
                        "gap_ratio": float(ev.gap_ratio[bar]),
                        "opp_age_s": float(ev.opp_age[bar]) * BAR_SECONDS,
                        "inzone_ordinal": float(zone_ordinal),
                        PEEK_FIELD: float(ahead[0] - bar) if len(ahead)
                        else float(cell.n - bar),
                    }
                    vector = np.asarray(
                        [float(values[name]) if values[name] is not None
                         else float("nan") for name in FIELDS], np.float64)
                    rows.append({
                        "asset": cell.asset, "phase": cell.phase, "d8": cell.d8,
                        "cell": cell.position, "side": int(side), "bar": bar,
                        "elapsed": values["elapsed_s"],
                        "remaining": values["remaining_s"],
                        "raw": vector,
                        "y1800": int(not bool(np.any(new_ext[bar + 1: stop]))),
                        "y_close": int(not bool(np.any(new_ext[bar + 1:]))),
                        "regime": (float(span_usd[bar] / math.sqrt(variance))
                                   if variance and variance > 0.0 else float("nan")),
                        "delay_s": (float((bar - terminal) * BAR_SECONDS)
                                    if terminal >= 0 else 0.0),
                    })
                    produced += 1
            if produced:
                counters["cells_with_rows"] += 1
        for cell in by_day[(asset, d8)]:
            strata[(cell.asset, cell.phase)].flush()

    if not rows:
        raise SweepRefusal("sweep 9 produced no rows: the plane is empty")
    plane = Plane(
        asset=np.asarray([r["asset"] for r in rows]),
        phase=np.asarray([r["phase"] for r in rows]),
        d8=np.asarray([r["d8"] for r in rows], np.int64),
        cell=np.asarray([r["cell"] for r in rows], np.int64),
        side=np.asarray([r["side"] for r in rows], np.int64),
        bar=np.asarray([r["bar"] for r in rows], np.int64),
        elapsed=np.asarray([r["elapsed"] for r in rows], np.float64),
        remaining=np.asarray([r["remaining"] for r in rows], np.float64),
        raw=np.vstack([r["raw"] for r in rows]),
        y1800=np.asarray([r["y1800"] for r in rows], np.int64),
        y_close=np.asarray([r["y_close"] for r in rows], np.int64),
        regime_ratio=np.asarray([r["regime"] for r in rows], np.float64),
        delay_s=np.asarray([r["delay_s"] for r in rows], np.float64),
        certifiable=certifiable, cells_total=cells_total, counters=counters,
        stratum_day_cells=stratum_day_cells)
    return plane


# --------------------------------------------------------------------------
# Walk-forward scaling and the twin search.
# --------------------------------------------------------------------------

def scale_plane(plane: Plane) -> np.ndarray:
    """Z-scores from strictly earlier days inside each (asset, phase) stratum."""

    out = np.zeros_like(plane.raw)
    strata = plane.stratum_keys()
    for key in sorted(set(strata.tolist())):
        pick = np.flatnonzero(strata == key)
        days = plane.d8[pick]
        order = np.argsort(days, kind="stable")
        pick = pick[order]
        days = days[order]
        unique = np.unique(days)
        for day in unique:
            here = pick[days == day]
            past = pick[days < day]
            if not len(past):
                continue
            history = plane.raw[past]
            with np.errstate(invalid="ignore"):
                mean = np.nanmean(np.where(np.isfinite(history), history, np.nan),
                                  axis=0)
                sd = np.nanstd(np.where(np.isfinite(history), history, np.nan),
                               axis=0)
            mean = np.where(np.isfinite(mean), mean, 0.0)
            sd = np.where(np.isfinite(sd) & (sd > 0.0), sd, 1.0)
            block = (plane.raw[here] - mean) / sd
            out[here] = np.where(np.isfinite(block), block, 0.0)
    return out


@dataclass(slots=True)
class Twins:
    """Per-row nearest-twin distance, its label, and the k-NN risk."""

    distance: np.ndarray            # nearest-twin Euclidean distance, nan = none
    twin_label: np.ndarray          # nearest twin's Y1800, -1 = none
    risk1: np.ndarray               # 1 - twin label, nan = none
    risk5: np.ndarray               # mean 1 - label over up to KNN twins
    twins_found: np.ndarray         # how many twins the row actually had

    def score(self, risk: np.ndarray) -> np.ndarray:
        """The risk with its frozen, label-free tie-break.

        A k=5 risk takes six values, so its cell-coverage curve is a six-step
        staircase and "the smallest bar reaching 0.35" lands mid-tie and then
        floods: one bar of 0.0 admits every row whose five twins all survived,
        which is most cells.  The tie is broken by the row's own nearest-twin
        distance through a bounded monotone map, so a closer twin is preferred
        inside one risk level and no row can ever cross into the next level.
        The map reads no label and no sample statistic, so it adds no fit and
        no walk-forward exposure.
        """

        offset = 0.19 * (1.0 - np.exp(-np.where(np.isfinite(self.distance),
                                                self.distance, 0.0)))
        return risk + offset


def match_twins(plane: Plane, scaled: np.ndarray, view: str,
                mutant: str = "") -> Twins:
    """Nearest prior-day twin per row, inside the frozen clock window."""

    columns = [FIELD_INDEX[name] for name in view_fields(view, mutant)]
    matrix = scaled[:, columns]
    total = plane.n
    distance = np.full(total, np.nan)
    twin_label = np.full(total, -1, np.int64)
    risk1 = np.full(total, np.nan)
    risk5 = np.full(total, np.nan)
    found = np.zeros(total, np.int64)
    strata = plane.stratum_keys()
    for key in sorted(set(strata.tolist())):
        pick = np.flatnonzero(strata == key)
        order = np.argsort(plane.elapsed[pick], kind="stable")
        pick = pick[order]
        elapsed = plane.elapsed[pick]
        remaining = plane.remaining[pick]
        days = plane.d8[pick]
        labels = plane.y1800[pick]
        block = matrix[pick]
        for position in range(len(pick)):
            low = int(np.searchsorted(elapsed, elapsed[position] - CLOCK_WINDOW_S,
                                      side="left"))
            high = int(np.searchsorted(elapsed, elapsed[position] + CLOCK_WINDOW_S,
                                       side="right"))
            window = np.arange(low, high)
            if not len(window):
                continue
            keep = ((days[window] < days[position])
                    & (np.abs(remaining[window] - remaining[position])
                       <= CLOCK_WINDOW_S))
            window = window[keep]
            if not len(window):
                continue
            diff = block[window] - block[position]
            dist = np.sqrt(np.einsum("ij,ij->i", diff, diff))
            rank = np.argsort(dist, kind="stable")
            best = rank[0]
            row = int(pick[position])
            distance[row] = float(dist[best])
            twin_label[row] = int(labels[window[best]])
            risk1[row] = 1.0 - float(labels[window[best]])
            top = rank[:KNN]
            risk5[row] = 1.0 - float(np.mean(labels[window[top]]))
            found[row] = int(len(window))
    return Twins(distance, twin_label, risk1, risk5, found)


# --------------------------------------------------------------------------
# Bar calibration and the first-fire selection.
# --------------------------------------------------------------------------

def _cell_coverage(cell_ids: np.ndarray, hit: np.ndarray, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return float(len(set(cell_ids[hit].tolist())) / denominator)


def calibrate_and_select(plane: Plane, score: np.ndarray, *, lower_is_better: bool,
                         cell_ids: np.ndarray) -> tuple[np.ndarray, dict[str, object]]:
    """First-fire selection under a prior-day bar aimed at 0.35 cell coverage.

    ``score`` is oriented so that a SMALLER value is a safer row when
    ``lower_is_better`` (the risk estimates), and so that a LARGER value is
    safer otherwise (the E1-only control).  The bar is recalibrated for every
    (asset, phase) stratum on every scoring day from strictly earlier days.
    Cell coverage is monotone in the threshold, so the prior-day rows are walked
    in safety order and the walk stops at the first threshold that reaches the
    0.35 target - the same answer a grid scan gives, without its cost.
    """

    total = plane.n
    selected = np.zeros(total, bool)
    strata = plane.stratum_keys()
    bars: dict[str, float] = {}
    saturated = 0
    for key in sorted(set(strata.tolist())):
        asset, phase = key.split("/")
        prior_cell_count: dict[int, int] = {}
        running = 0
        for day in sorted({d for (a, p, d) in plane.stratum_day_cells
                           if a == asset and p == phase}):
            prior_cell_count[day] = running
            running += plane.stratum_day_cells[(asset, phase, day)]
        pick = np.flatnonzero(strata == key)
        days = plane.d8[pick]
        for day in sorted(set(days.tolist())):
            here = pick[days == day]
            past = pick[days < day]
            usable = past[np.isfinite(score[past])]
            prior_cells = prior_cell_count.get(day, 0)
            if not len(usable) or prior_cells <= 0:
                continue
            order = usable[np.argsort(score[usable] if lower_is_better
                                      else -score[usable], kind="stable")]
            reached: set[str] = set()
            bar = None
            need = COVERAGE_TARGET * prior_cells
            for position in order:
                reached.add(cell_ids[position])
                if len(reached) >= need:
                    bar = float(score[position])
                    break
            if bar is None:
                bar = float(score[order[-1]])
                saturated += 1
            bars[f"{key}/{day}"] = bar
            today = score[here]
            ok = np.where(np.isfinite(today),
                          today <= bar if lower_is_better else today >= bar,
                          False)
            # First fire wins the cell; one entry per cell; the cancellation
            # window between fire and entry is empty because the row IS the
            # entry, so no row can be cancelled here.
            cells_here: dict[int, int] = {}
            order = np.argsort(plane.bar[here], kind="stable")
            for index in order:
                if not ok[index]:
                    continue
                cell = int(plane.cell[here[index]])
                if cell in cells_here:
                    continue
                cells_here[cell] = int(here[index])
            for row in cells_here.values():
                selected[row] = True
    return selected, {"bars_fitted": len(bars), "bars_saturated": saturated,
                      "median_bar": (float(np.median(list(bars.values())))
                                     if bars else None)}


def phase_matched_control(plane: Plane, selected: np.ndarray,
                          draws: int = CONTROL_DRAWS) -> np.ndarray:
    """Counts per row across seeded draws of the phase-elapsed-matched control."""

    counts = np.zeros(plane.n, np.float64)
    rng = np.random.default_rng(SEED)
    targets: dict[str, np.ndarray] = {}
    for asset in ASSETS:
        pick = np.flatnonzero((plane.asset == asset) & selected)
        targets[asset] = plane.elapsed[pick]
    by_cell: dict[tuple[str, int, str, int], np.ndarray] = {}
    keys = plane.cell_keys()
    for key in sorted(set(keys.tolist())):
        by_cell[key] = np.flatnonzero(keys == key)
    for _draw in range(draws):
        for key, members in by_cell.items():
            asset = key.split("/")[0]
            wanted = targets.get(asset)
            if wanted is None or not len(wanted):
                continue
            aim = float(wanted[int(rng.integers(len(wanted)))])
            near = members[np.abs(plane.elapsed[members] - aim) <= CLOCK_WINDOW_S]
            if not len(near):
                continue
            counts[int(near[int(rng.integers(len(near)))])] += 1.0
    return counts


# --------------------------------------------------------------------------
# Regimes.
# --------------------------------------------------------------------------

def regime_labels(plane: Plane) -> tuple[np.ndarray, dict[str, object]]:
    """Balance / middle / trend, terciles fitted per asset on earlier days."""

    out = np.full(plane.n, "", dtype=object)
    edges: dict[str, object] = {}
    for asset in ASSETS:
        pick = np.flatnonzero(plane.asset == asset)
        days = plane.d8[pick]
        fitted: dict[int, tuple[float, float]] = {}
        for day in sorted(set(days.tolist())):
            past = pick[days < day]
            values = plane.regime_ratio[past]
            values = values[np.isfinite(values)]
            if len(values) < 3:
                continue
            low = float(np.percentile(values, 100.0 / 3.0))
            high = float(np.percentile(values, 200.0 / 3.0))
            fitted[day] = (low, high)
            here = pick[days == day]
            ratio = plane.regime_ratio[here]
            names = np.where(ratio <= low, "balance",
                             np.where(ratio <= high, "middle", "trend"))
            names = np.where(np.isfinite(ratio), names, "")
            out[here] = names
        edges[asset] = {"days_fitted": len(fitted),
                        "last_edges": list(fitted[max(fitted)]) if fitted else None}
    return out, edges


# --------------------------------------------------------------------------
# Metrics.
# --------------------------------------------------------------------------

def _rate(hits: float, total: float) -> dict[str, object]:
    low, high = S1.wilson(int(round(hits)), int(round(total)))
    return {"hits": int(round(hits)), "n": int(round(total)),
            "rate": (float(hits) / float(total)) if total else None,
            "ci_low": low if total else None, "ci_high": high if total else None}


def _postx(weights: np.ndarray, y: np.ndarray) -> tuple[float | None, float]:
    """Weighted postX_1800 and the weight mass behind it."""

    mass = float(weights.sum())
    if mass <= 0.0:
        return None, 0.0
    return float(np.dot(weights, 1 - y) / mass), mass


def bootstrap_delta(plane: Plane, day_keys: np.ndarray, target: np.ndarray,
                    control: np.ndarray, draws: int = BOOT_DRAWS
                    ) -> tuple[float | None, float | None]:
    """Day-block 95 % interval on postX(control) - postX(target).

    The blocks are the asset-days that actually carry mass for this cut; days
    with no weight on either side are not resampled, or the interval would be
    the interval of a randomly thinned sample rather than of the measurement.
    """

    days = sorted(set(day_keys.tolist()))
    if not days:
        return None, None
    index = {day: position for position, day in enumerate(days)}
    slot = np.asarray([index[day] for day in day_keys.tolist()], np.int64)
    y = 1 - plane.y1800
    size = len(days)
    t_hits = np.bincount(slot, weights=target * y, minlength=size)
    t_mass = np.bincount(slot, weights=target, minlength=size)
    c_hits = np.bincount(slot, weights=control * y, minlength=size)
    c_mass = np.bincount(slot, weights=control, minlength=size)
    live = np.flatnonzero((t_mass > 0) | (c_mass > 0))
    if not len(live):
        return None, None
    t_hits, t_mass = t_hits[live], t_mass[live]
    c_hits, c_mass = c_hits[live], c_mass[live]
    size = len(live)
    rng = np.random.default_rng(SEED)
    picks = rng.integers(0, size, size=(draws, size))
    th = t_hits[picks].sum(axis=1)
    tm = t_mass[picks].sum(axis=1)
    ch = c_hits[picks].sum(axis=1)
    cm = c_mass[picks].sum(axis=1)
    keep = (tm > 0) & (cm > 0)
    if not bool(keep.any()):
        return None, None
    delta = (ch[keep] / cm[keep]) - (th[keep] / tm[keep])
    return float(np.percentile(delta, 2.5)), float(np.percentile(delta, 97.5))


# --------------------------------------------------------------------------
# The run.
# --------------------------------------------------------------------------

@dataclass(slots=True)
class ViewRun:
    """One view's twin match, selection, controls and per-asset weights."""

    twins: Twins
    selected: np.ndarray
    weights: np.ndarray             # 1.0 on selected rows
    e1_weights: np.ndarray
    pm_weights: np.ndarray
    bar_info: dict[str, object]
    e1_bar_info: dict[str, object]
    k1_weights: np.ndarray          # the 1-NN risk line, reported beside K5


def run_views(plane: Plane, scaled: np.ndarray, mutant: str = "") -> dict[str, ViewRun]:
    keys = plane.cell_keys()
    e1 = plane.raw[:, FIELD_INDEX["E1"]]
    e1_selected, e1_info = calibrate_and_select(
        plane, e1, lower_is_better=False, cell_ids=keys)
    e1_weights = e1_selected.astype(np.float64)
    out: dict[str, ViewRun] = {}
    for view in VIEWS:
        twins = match_twins(plane, scaled, view, mutant)
        selected, info = calibrate_and_select(
            plane, twins.score(twins.risk5), lower_is_better=True, cell_ids=keys)
        k1, _k1_info = calibrate_and_select(
            plane, twins.score(twins.risk1), lower_is_better=True, cell_ids=keys)
        pm = phase_matched_control(plane, selected)
        out[view] = ViewRun(twins, selected, selected.astype(np.float64),
                            e1_weights, pm, info, e1_info,
                            k1.astype(np.float64))
    return out


def _disagreement(plane: Plane, twins: Twins, mask: np.ndarray) -> dict[str, object]:
    """Label disagreement among the closest ``DISAGREE_SHARE`` of twins."""

    pick = np.flatnonzero(mask & np.isfinite(twins.distance))
    if not len(pick):
        return {"n": 0, "rate": None, "ci_low": None, "ci_high": None}
    order = pick[np.argsort(twins.distance[pick], kind="stable")]
    keep = order[: max(1, int(round(DISAGREE_SHARE * len(order))))]
    hits = int(np.sum(plane.y1800[keep] != twins.twin_label[keep]))
    return _rate(hits, len(keep))


def _admit(plane: Plane, in_asset: np.ndarray, regimes: np.ndarray,
           cut: str) -> np.ndarray:
    """Which rows one reporting cut admits."""

    if cut == "pooled":
        return in_asset
    if cut in PHASE_CUTS:
        return in_asset & (plane.phase == cut[-1])
    return in_asset & (regimes == cut)


def measure(plane: Plane, runs: Mapping[str, ViewRun], regimes: np.ndarray
            ) -> dict[str, object]:
    day_keys = plane.day_keys()
    cell_ids = plane.cell_keys()
    report: dict[str, object] = {}
    for asset in ASSETS:
        in_asset = plane.asset == asset
        denominator = max(1, plane.certifiable.get(asset, 0))
        available = _cell_coverage(cell_ids, in_asset, denominator)
        block: dict[str, object] = {
            "certifiable_cells": plane.certifiable.get(asset, 0),
            "cells": plane.cells_total.get(asset, 0),
            "rows": int(np.sum(in_asset)),
            "candidate_availability": available,
            "base_postx1800": float(np.mean(1 - plane.y1800[in_asset]))
            if int(np.sum(in_asset)) else None,
            "base_postclose": float(np.mean(1 - plane.y_close[in_asset]))
            if int(np.sum(in_asset)) else None,
            "views": {}}
        for view, run in runs.items():
            per_view: dict[str, object] = {}
            for cut in ALL_CUTS:
                admit = _admit(plane, in_asset, regimes, cut)
                weights = run.weights * admit
                e1w = run.e1_weights * admit
                pmw = run.pm_weights * admit
                postx, mass = _postx(weights, plane.y1800)
                e1_postx, e1_mass = _postx(e1w, plane.y1800)
                pm_postx, pm_mass = _postx(pmw, plane.y1800)
                hit = weights > 0
                coverage = _cell_coverage(cell_ids, hit, denominator)
                e1_cov = _cell_coverage(cell_ids, e1w > 0, denominator)
                deltas: dict[str, object] = {}
                for name, control_postx, control_weights in (
                        ("E1ONLY", e1_postx, e1w), ("PHASEMATCH", pm_postx, pmw)):
                    if postx is None or control_postx is None:
                        deltas[name] = {"delta": None, "ci_low": None,
                                        "ci_high": None}
                        continue
                    low, high = bootstrap_delta(plane, day_keys, weights,
                                                control_weights)
                    deltas[name] = {"delta": float(control_postx - postx),
                                    "ci_low": low, "ci_high": high}
                selected_rows = np.flatnonzero(hit)
                per_view[cut] = {
                    "coverage": coverage,
                    "entries": int(mass),
                    "postx1800": postx,
                    "postx1800_ci": (_rate(np.dot(weights, 1 - plane.y1800), mass)
                                     if mass else None),
                    "postclose": (float(np.dot(weights, 1 - plane.y_close) / mass)
                                  if mass else None),
                    "control_E1ONLY": {"postx1800": e1_postx, "coverage": e1_cov,
                                       "entries": int(e1_mass)},
                    "control_PHASEMATCH": {"postx1800": pm_postx,
                                           "draw_mass": pm_mass},
                    "delta": deltas,
                    "twin_distance_median": (
                        float(np.nanmedian(run.twins.distance[selected_rows]))
                        if len(selected_rows) else None),
                    "twin_disagreement": _disagreement(plane, run.twins, admit),
                    "decision_delay_p90_s": (
                        float(np.percentile(plane.delay_s[selected_rows], 90))
                        if len(selected_rows) else None),
                    "decision_delay_median_s": (
                        float(np.percentile(plane.delay_s[selected_rows], 50))
                        if len(selected_rows) else None),
                    "extreme_age_p90_s": (
                        float(np.percentile(
                            plane.raw[selected_rows, FIELD_INDEX["extreme_age_s"]], 90))
                        if len(selected_rows) else None),
                }
            # The 1-NN risk line, run beside the deciding 5-NN estimate.
            k1 = run.k1_weights * in_asset
            k1_postx, k1_mass = _postx(k1, plane.y1800)
            per_view["k1_pooled"] = {
                "coverage": _cell_coverage(cell_ids, k1 > 0, denominator),
                "entries": int(k1_mass), "postx1800": k1_postx}
            block["views"][view] = per_view
        report[asset] = block
    return report


def null_test(plane: Plane, runs: Mapping[str, ViewRun], regimes: np.ndarray,
              draws: int = NULL_DRAWS) -> dict[str, object]:
    """Block-permuted Y1800 with the row sets held fixed; max-stat adjusted.

    The block is the asset-day; the permutation runs INSIDE (asset, phase,
    regime), so a day's labels move to another day of the same stratum and
    regime as one piece.  Reordering blocks preserves each group's label rate
    exactly, which is what makes this a null about the SELECTION rather than
    about the base rate.
    """

    rng = np.random.default_rng(SEED)
    groups: list[tuple[np.ndarray, list[np.ndarray]]] = []
    for asset in ASSETS:
        for phase in sorted(set(plane.phase.tolist())):
            for regime in list(REGIMES) + [""]:
                mask = ((plane.asset == asset) & (plane.phase == phase)
                        & (regimes == regime))
                pick = np.flatnonzero(mask)
                if not len(pick):
                    continue
                blocks = [pick[plane.d8[pick] == day]
                          for day in sorted(set(plane.d8[pick].tolist()))]
                groups.append((np.concatenate(blocks), blocks))
    y = 1 - plane.y1800
    permuted = np.zeros((plane.n, draws), np.float32)
    for draw in range(draws):
        column = np.array(y, np.float32)
        for slots, blocks in groups:
            order = rng.permutation(len(blocks))
            column[slots] = np.concatenate([y[blocks[position]]
                                            for position in order])
        permuted[:, draw] = column

    cells: list[tuple[str, str, str]] = []
    matrix: list[np.ndarray] = []
    masses: list[float] = []
    for asset in ASSETS:
        in_asset = plane.asset == asset
        for view in VIEWS:
            run = runs[view]
            for cut in ALL_CUTS:
                admit = _admit(plane, in_asset, regimes, cut)
                for name, weights in (("SEL", run.weights * admit),
                                      ("E1ONLY", run.e1_weights * admit),
                                      ("PHASEMATCH", run.pm_weights * admit)):
                    cells.append((f"{asset}/{view}/{cut}", name, ""))
                    matrix.append(weights.astype(np.float32))
                    masses.append(float(weights.sum()))
    stack = np.vstack(matrix)
    mass = np.asarray(masses, np.float32)
    mass = np.where(mass > 0.0, mass, np.nan)
    rates = (stack @ permuted) / mass[:, None]
    observed_rates = (stack @ (1 - plane.y1800).astype(np.float32)) / mass

    names = [row[0] for row in cells[::3]]
    statistics = np.full((len(names), draws), np.nan, np.float64)
    observed = np.full(len(names), np.nan, np.float64)
    for position in range(len(names)):
        sel, e1, pm = 3 * position, 3 * position + 1, 3 * position + 2
        statistics[position] = np.minimum(rates[e1] - rates[sel],
                                          rates[pm] - rates[sel])
        observed[position] = float(min(observed_rates[e1] - observed_rates[sel],
                                       observed_rates[pm] - observed_rates[sel]))
    # The max-statistic family is exactly the spec's: the two deciding assets,
    # the four views, and the pooled plus three regime cuts.  The phase rows are
    # reported with an own-p only; they never widen or narrow the family.
    family = [position for position, name in enumerate(names)
              if name.split("/")[0] in DECIDING and name.split("/")[2] in CUTS]
    with np.errstate(invalid="ignore"):
        null_max = np.nanmax(statistics[family], axis=0)
    out: dict[str, object] = {"draws": draws, "seed": SEED,
                              "statistic": "min(postX(E1ONLY)-postX(SEL), "
                                           "postX(PHASEMATCH)-postX(SEL))",
                              "family_size": len(family), "by_cell": {}}
    for position, name in enumerate(names):
        own = statistics[position]
        seen = observed[position]
        if not np.isfinite(seen):
            out["by_cell"][name] = {"observed": None, "p_own": None,
                                    "p_max_adjusted": None}
            continue
        out["by_cell"][name] = {
            "observed": float(seen),
            "p_own": float((1 + int(np.nansum(own >= seen))) / (1 + draws)),
            "p_max_adjusted": float((1 + int(np.nansum(null_max >= seen)))
                                    / (1 + draws)),
        }
    return out


# --------------------------------------------------------------------------
# The letters.
# --------------------------------------------------------------------------

def _get(block: Mapping[str, object], *path: str) -> object:
    node: object = block
    for step in path:
        if not isinstance(node, Mapping) or step not in node:
            return None
        node = node[step]
    return node


def letters(report: Mapping[str, object], nulls: Mapping[str, object]
            ) -> dict[str, object]:
    out: dict[str, object] = {"by_asset": {}}
    for asset in ASSETS:
        asset_out: dict[str, object] = {"views": {}}
        for view in VIEWS:
            pooled = _get(report, asset, "views", view, "pooled")
            eligible = view in ELIGIBLE_VIEWS
            checks: dict[str, object] = {}
            null_p = _get(nulls, "by_cell", f"{asset}/{view}/pooled",
                          "p_max_adjusted")
            coverage = _get(pooled, "coverage")
            postx = _get(pooled, "postx1800")
            deltas = {name: _get(pooled, "delta", name) for name in CONTROLS}
            checks["coverage>=0.35"] = bool(coverage is not None
                                            and coverage >= COVERAGE_FLOOR)
            checks["postx<=0.25"] = bool(postx is not None and postx <= POSTX_CEILING)
            checks["improve>=0.05_both"] = bool(all(
                d and d.get("delta") is not None and d["delta"] >= IMPROVE_MIN
                for d in deltas.values()))
            checks["ci_low>0_both"] = bool(all(
                d and d.get("ci_low") is not None and d["ci_low"] > 0.0
                for d in deltas.values()))
            checks["adj_p<=0.05"] = bool(null_p is not None and null_p <= NULL_CEILING)
            survivor = eligible and all(checks.values())
            regime_letter = None
            regime_detail: dict[str, object] = {}
            if eligible and not survivor:
                for regime in REGIMES:
                    cut = _get(report, asset, "views", view, regime)
                    p_cut = _get(nulls, "by_cell", f"{asset}/{view}/{regime}",
                                 "p_max_adjusted")
                    cover = _get(cut, "coverage")
                    px = _get(cut, "postx1800")
                    cut_deltas = {name: _get(cut, "delta", name) for name in CONTROLS}
                    others = [_get(report, asset, "views", view, other, "postx1800")
                              for other in REGIMES if other != regime]
                    lead = (min((o - px) for o in others if o is not None)
                            if px is not None and any(o is not None for o in others)
                            else None)
                    passes = (cover is not None and cover >= COVERAGE_FLOOR
                              and px is not None and px <= POSTX_CEILING
                              and all(d and d.get("delta") is not None
                                      and d["delta"] >= IMPROVE_MIN
                                      for d in cut_deltas.values())
                              and all(d and d.get("ci_low") is not None
                                      and d["ci_low"] > 0.0
                                      for d in cut_deltas.values())
                              and p_cut is not None and p_cut <= NULL_CEILING
                              and lead is not None and lead >= REGIME_LEAD)
                    regime_detail[regime] = {"coverage": cover, "postx1800": px,
                                             "lead_over_others": lead,
                                             "adj_p": p_cut, "passes": bool(passes)}
                    if passes and regime_letter is None:
                        regime_letter = regime
            asset_out["views"][view] = {
                "eligible": eligible, "checks": checks,
                "letter": ("SURVIVOR" if survivor else
                           "REGIME_SURVIVOR" if regime_letter else None),
                "regime": regime_letter, "regime_detail": regime_detail,
                "adj_p": null_p, "coverage": coverage, "postx1800": postx,
            }
        asset_out["letter"] = next(
            (asset_out["views"][v]["letter"] for v in ELIGIBLE_VIEWS
             if asset_out["views"][v]["letter"] == "SURVIVOR"), None)
        if asset_out["letter"] is None:
            asset_out["letter"] = next(
                (asset_out["views"][v]["letter"] for v in ELIGIBLE_VIEWS
                 if asset_out["views"][v]["letter"] == "REGIME_SURVIVOR"), None)
        out["by_asset"][asset] = asset_out

    # CERTIFICATE is a statement about the WHOLE causal state, so it is judged
    # across every view (CLOCK included) on both deciding assets at once.
    cert_checks: dict[str, object] = {}
    postx_ok = True
    improve_ok = True
    for asset in DECIDING:
        for view in VIEWS:
            pooled = _get(report, asset, "views", view, "pooled")
            coverage = _get(pooled, "coverage")
            postx = _get(pooled, "postx1800")
            if postx is None or not (postx > CERT_POSTX_FLOOR) or coverage is None \
                    or coverage < COVERAGE_FLOOR:
                postx_ok = False
            for name in CONTROLS:
                high = _get(pooled, "delta", name, "ci_high")
                if high is None or not (high < CERT_IMPROVE_UPPER):
                    improve_ok = False
    disagree_ok = True
    for asset in DECIDING:
        for view in ELIGIBLE_VIEWS:
            low = _get(report, asset, "views", view, "pooled",
                       "twin_disagreement", "ci_low")
            if low is None or low < CERT_DISAGREE_FLOOR:
                disagree_ok = False
    cert_checks["every_view_postx>0.30_at_cov>=0.35"] = bool(postx_ok)
    cert_checks["every_improve_ci_high<0.05"] = bool(improve_ok)
    cert_checks["twin_disagreement_ci_low>=0.35_both"] = bool(disagree_ok)
    certificate = all(cert_checks.values())
    out["certificate"] = {"checks": cert_checks, "letter":
                          "CERTIFICATE" if certificate else None}

    fired = [out["by_asset"][a]["letter"] for a in DECIDING
             if out["by_asset"][a]["letter"]]
    if "SURVIVOR" in fired:
        overall = "SURVIVOR"
        routes = ("route the survivor view to a scoped survival unit; "
                  "no cash opens from this certificate")
    elif "REGIME_SURVIVOR" in fired:
        overall = "REGIME_SURVIVOR"
        routes = "route exactly that view and regime to one scoped survival unit"
    elif certificate:
        overall = "CERTIFICATE"
        routes = ("closes transformations of the current causal state; it is not "
                  "a claim about unavailable feeds or markets")
    else:
        overall = "UNRESOLVED"
        routes = "do not price an unresolved result"
    out["overall"] = overall
    out["routes"] = routes
    return out


# --------------------------------------------------------------------------
# Sweep 8 reproduction gate.
# --------------------------------------------------------------------------

def reproduce_sweep8(cells: Sequence[S8.Cell8], days: Mapping[str, int],
                     skipped: Mapping[str, int], plane: Plane) -> dict[str, object]:
    """The spec's own gate: sweep 8's eligible opportunity counts, re-derived."""

    receipt = json.loads(SWEEP8_PATH.read_text())
    run = S8.run_gate(cells)
    live = {
        "cells": {asset: int(sum(1 for c in cells if c.asset == asset))
                  for asset in ASSETS},
        "cells_scored": {asset: int(run.scored_cells.get(asset, 0))
                         for asset in ASSETS},
        "asset_days": {asset: int(days.get(asset, 0)) for asset in ASSETS},
        "skipped_no_context": {asset: int(skipped.get(asset, 0)) for asset in ASSETS},
    }
    banked = {name: {asset: int(receipt[name][asset]) for asset in ASSETS}
              for name in live}
    plane_cells = {asset: int(plane.certifiable.get(asset, 0)) for asset in ASSETS}
    return {"receipt": banked, "recomputed": live, "sweep9_certifiable": plane_cells,
            "matches": bool(live == banked),
            "certifiable_matches_scored": bool(plane_cells == live["cells_scored"])}


# --------------------------------------------------------------------------
# Printing.
# --------------------------------------------------------------------------

def _n(value: object, width: int = 7, digits: int = 3) -> str:
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return "-".rjust(width)
    if isinstance(value, (int, np.integer)) and not isinstance(value, bool):
        return f"{int(value):{width}d}"
    return f"{float(value):{width}.{digits}f}"


def print_reproduction(block: Mapping[str, object]) -> None:
    print("\n== sweep 8 eligible opportunity counts, reproduced before measuring")
    print(f"{'field':22s} {'asset':5s} {'receipt':>9s} {'recomputed':>11s} {'ok':>4s}")
    for name in ("cells", "cells_scored", "asset_days", "skipped_no_context"):
        for asset in ASSETS:
            banked = block["receipt"][name][asset]
            live = block["recomputed"][name][asset]
            print(f"{name:22s} {asset:5s} {banked:9d} {live:11d} "
                  f"{('OK' if banked == live else 'DIFF'):>4s}")
    print(f"reproduction matches sweep 8 receipt: {block['matches']}")
    print(f"sweep 9 certifiable cells == sweep 8 cells_scored: "
          f"{block['certifiable_matches_scored']} "
          f"{block['sweep9_certifiable']}")


def print_plane(plane: Plane) -> None:
    print("\n== row plane (one distinct in-zone CLEAR candidate per decision stamp)")
    print(f"{'asset':5s} {'cells':>6s} {'certif':>7s} {'rows':>7s} {'avail':>7s} "
          f"{'postX':>7s} {'postClose':>10s}")
    for asset in ASSETS:
        pick = plane.asset == asset
        rows = int(np.sum(pick))
        cells = plane.cell_keys()
        avail = _cell_coverage(cells, pick, max(1, plane.certifiable.get(asset, 0)))
        postx = float(np.mean(1 - plane.y1800[pick])) if rows else None
        close = float(np.mean(1 - plane.y_close[pick])) if rows else None
        print(f"{asset:5s} {plane.cells_total.get(asset, 0):6d} "
              f"{plane.certifiable.get(asset, 0):7d} {rows:7d} {_n(avail)} "
              f"{_n(postx)} {_n(close, 10)}")
    print("counters " + json.dumps(plane.counters, sort_keys=True))


def print_metrics(report: Mapping[str, object], nulls: Mapping[str, object]) -> None:
    for asset in ASSETS:
        tag = "REPORT-ONLY" if asset in REPORT_ONLY else "deciding"
        print(f"\n== {asset} ({tag}); certifiable cells "
              f"{report[asset]['certifiable_cells']}, rows {report[asset]['rows']}, "
              f"candidate availability {_n(report[asset]['candidate_availability'])}, "
              f"pool postX_1800 {_n(report[asset]['base_postx1800'])}")
        print(f"{'view':9s} {'cut':8s} {'cov':>6s} {'n':>5s} {'postX':>7s} "
              f"{'pClose':>7s} {'E1cov':>6s} {'E1ctl':>7s} {'dE1':>7s} {'lo':>7s} "
              f"{'hi':>7s} {'PMctl':>7s} {'dPM':>7s} {'lo':>7s} {'hi':>7s} "
              f"{'adjP':>6s} {'twinD':>7s} {'disag':>7s} {'dlo':>6s} {'p90dly':>8s}")
        for view in VIEWS:
            for cut in ALL_CUTS:
                row = report[asset]["views"][view][cut]
                null_p = _get(nulls, "by_cell", f"{asset}/{view}/{cut}",
                              "p_max_adjusted")
                d1 = row["delta"]["E1ONLY"]
                d2 = row["delta"]["PHASEMATCH"]
                print(f"{view:9s} {cut:8s} {_n(row['coverage'], 6)} "
                      f"{row['entries']:5d} {_n(row['postx1800'])} "
                      f"{_n(row['postclose'])} "
                      f"{_n(row['control_E1ONLY']['coverage'], 6)} "
                      f"{_n(row['control_E1ONLY']['postx1800'])} "
                      f"{_n(d1['delta'])} {_n(d1['ci_low'])} {_n(d1['ci_high'])} "
                      f"{_n(row['control_PHASEMATCH']['postx1800'])} "
                      f"{_n(d2['delta'])} {_n(d2['ci_low'])} {_n(d2['ci_high'])} "
                      f"{_n(null_p, 6)} {_n(row['twin_distance_median'])} "
                      f"{_n(row['twin_disagreement']['rate'])} "
                      f"{_n(row['twin_disagreement']['ci_low'], 6)} "
                      f"{_n(row['decision_delay_p90_s'], 8, 0)}")
        print(f"{'':9s} 1-NN line (reported beside the deciding 5-NN): " + "; ".join(
            f"{view} cov {_n(report[asset]['views'][view]['k1_pooled']['coverage'], 5)}"
            f" postX {_n(report[asset]['views'][view]['k1_pooled']['postx1800'], 5)}"
            for view in VIEWS))


def print_letters(block: Mapping[str, object]) -> None:
    print("\n== letters")
    print(f"{'asset':5s} {'view':9s} {'elig':>5s} {'cov':>6s} {'postX':>7s} "
          f"{'adjP':>6s} {'cov>=':>6s} {'pX<=':>6s} {'d>=':>6s} {'ci>0':>6s} "
          f"{'p<=':>6s} {'letter':>16s}")
    for asset in ASSETS:
        for view in VIEWS:
            row = block["by_asset"][asset]["views"][view]
            checks = row["checks"]
            print(f"{asset:5s} {view:9s} {str(row['eligible']):>5s} "
                  f"{_n(row['coverage'], 6)} {_n(row['postx1800'])} "
                  f"{_n(row['adj_p'], 6)} "
                  f"{str(checks['coverage>=0.35']):>6s} "
                  f"{str(checks['postx<=0.25']):>6s} "
                  f"{str(checks['improve>=0.05_both']):>6s} "
                  f"{str(checks['ci_low>0_both']):>6s} "
                  f"{str(checks['adj_p<=0.05']):>6s} "
                  f"{str(row['letter'] or '-'):>16s}")
    print("\nCERTIFICATE checks: " + json.dumps(block["certificate"]["checks"],
                                                sort_keys=True))
    for asset in ASSETS:
        print(f"deciding-asset letter {asset}: "
              f"{block['by_asset'][asset]['letter'] or 'none'}"
              + ("  (report-only)" if asset in REPORT_ONLY else ""))
    print(f"\nOVERALL LETTER: {block['overall']}")
    print(f"ROUTES: {block['routes']}")


# --------------------------------------------------------------------------
# Selftest.
# --------------------------------------------------------------------------

def _check(name: str, ok: bool, detail: str = "") -> tuple[str, bool, str]:
    return (name, bool(ok), detail)


def _synthetic(kind: str, seed: int = SEED) -> Plane:
    """Two synthetic planes: one perfectly causal, one perfectly ambiguous.

    ``causal``: a feature (``gap_ratio``) splits survival exactly, and the row's
    clock is drawn so twins are always findable.  ``ambiguous``: every row's
    state is one of a handful of IDENTICAL points, and the label is a coin flip
    banked per row, so no transformation of the state can separate anything -
    except a feature that reads the label forward, which is what the mutant does.
    """

    rng = np.random.default_rng(seed)
    rows: list[dict[str, object]] = []
    days = list(range(20220101, 20220101 + 40))
    for asset in ("NKD", "SI"):
        for day_index, day in enumerate(days):
            for cell_index in range(4):
                for row_index in range(6):
                    elapsed = 600.0 + 300.0 * row_index
                    if kind == "causal":
                        good = bool(rng.integers(2))
                        y = 1 if good else 0
                        ratio = 3.0 + rng.normal(0.0, 0.05) if good \
                            else 0.4 + rng.normal(0.0, 0.05)
                    else:
                        y = int(rng.integers(2))
                        ratio = 1.0
                    vector = np.zeros(len(FIELDS), np.float64)
                    vector[FIELD_INDEX["elapsed_s"]] = elapsed
                    vector[FIELD_INDEX["remaining_s"]] = 20000.0 - elapsed
                    vector[FIELD_INDEX["gap_ratio"]] = ratio
                    vector[FIELD_INDEX["E1"]] = ratio / 4.0
                    vector[FIELD_INDEX["extreme_age_s"]] = 300.0 + 60.0 * row_index
                    vector[FIELD_INDEX["inzone_ordinal"]] = float(row_index + 1)
                    vector[FIELD_INDEX["cand_ordinal"]] = float(row_index + 1)
                    # The forward peek: a survivor's next same-side extreme is
                    # by definition more than 30 bars away.
                    vector[FIELD_INDEX[PEEK_FIELD]] = 60.0 if y else 5.0
                    rows.append({
                        "asset": asset, "phase": "1", "d8": day,
                        "cell": day_index * 10 + cell_index, "side": 1,
                        "bar": 10 + row_index, "elapsed": elapsed,
                        "remaining": 20000.0 - elapsed, "raw": vector,
                        "y1800": y, "y_close": y,
                        "regime": float(rng.uniform(0.5, 1.5)), "delay_s": 600.0})
    plane = Plane(
        asset=np.asarray([r["asset"] for r in rows]),
        phase=np.asarray([r["phase"] for r in rows]),
        d8=np.asarray([r["d8"] for r in rows], np.int64),
        cell=np.asarray([r["cell"] for r in rows], np.int64),
        side=np.asarray([r["side"] for r in rows], np.int64),
        bar=np.asarray([r["bar"] for r in rows], np.int64),
        elapsed=np.asarray([r["elapsed"] for r in rows], np.float64),
        remaining=np.asarray([r["remaining"] for r in rows], np.float64),
        raw=np.vstack([r["raw"] for r in rows]),
        y1800=np.asarray([r["y1800"] for r in rows], np.int64),
        y_close=np.asarray([r["y_close"] for r in rows], np.int64),
        regime_ratio=np.asarray([r["regime"] for r in rows], np.float64),
        delay_s=np.asarray([r["delay_s"] for r in rows], np.float64),
        certifiable={"HG": 0, "NKD": 160, "SI": 160},
        cells_total={"HG": 0, "NKD": 160, "SI": 160},
        asset_days={"HG": 0, "NKD": 40, "SI": 40}, counters={},
        stratum_day_cells={(asset, "1", day): 4
                           for asset in ("NKD", "SI") for day in days})
    return plane


def _synthetic_postx(kind: str, view: str, mutant: str) -> tuple[float, float]:
    plane = _synthetic(kind)
    scaled = scale_plane(plane)
    twins = match_twins(plane, scaled, view, mutant)
    keys = plane.cell_keys()
    selected, _info = calibrate_and_select(plane, twins.score(twins.risk5),
                                           lower_is_better=True, cell_ids=keys)
    weights = selected.astype(np.float64)
    postx, mass = _postx(weights, plane.y1800)
    coverage = _cell_coverage(keys, weights > 0,
                              plane.certifiable["NKD"] + plane.certifiable["SI"])
    return (postx if postx is not None else 1.0), coverage


def selftest() -> int:
    mutant = _mutant()
    results: list[tuple[str, bool, str]] = []

    # 1. The percentile and combination primitives are sweep 8's, unchanged.
    parts = {"E1": 0.9, "E2": 0.8, "E3": None, "E4": 0.7, "E5": 0.6}
    value, present = S8.combine(parts)
    results.append(_check("s8 combine imported, 4-of-5 honoured",
                          present == 4 and abs(value - 0.75) < 1e-12,
                          f"G={value} present={present}"))
    results.append(_check("s8 E1..E5 names unchanged",
                          S8.COMPONENTS == ("E1", "E2", "E3", "E4", "E5"),
                          str(S8.COMPONENTS)))

    # 2. Views are frozen and CLOCK is never eligible.
    results.append(_check("UNION is the union of S8 and SEQUENCE",
                          set(view_fields("UNION")) ==
                          set(S8_FIELDS) | set(SEQ_FIELDS),
                          ""))
    results.append(_check("CLOCK is not a SURVIVOR-eligible view",
                          "CLOCK" not in ELIGIBLE_VIEWS, ""))

    # 3. The label is the fixed horizon and never a feature.
    results.append(_check("label fields absent from every view",
                          all(name not in view_fields(view)
                              for view in VIEWS for name in ("y1800", "y_close")),
                          ""))

    # 4. The twin law: strictly prior day, inside the clock window.
    plane = _synthetic("causal")
    scaled = scale_plane(plane)
    twins = match_twins(plane, scaled, "SEQUENCE", "")
    first_day = plane.d8 == plane.d8.min()
    results.append(_check("first day has no prior-day twin",
                          bool(np.all(~np.isfinite(twins.distance[first_day]))),
                          ""))
    results.append(_check("later days do find twins",
                          bool(np.any(np.isfinite(twins.distance[~first_day]))),
                          ""))

    # 5. A perfectly causal feature must be found.
    causal_postx, causal_cov = _synthetic_postx("causal", "SEQUENCE", mutant)
    results.append(_check("causal plane: postX <= 0.05 at coverage >= 0.35",
                          causal_postx <= 0.05 and causal_cov >= COVERAGE_TARGET,
                          f"postX={causal_postx:.4f} cov={causal_cov:.4f}"))

    # 6. Identical states with opposing labels must NOT separate.  This is the
    #    check the next-gap mutant breaks: reading the next interarrival gap is
    #    reading the label, so the ambiguous plane suddenly separates perfectly.
    amb_postx, amb_cov = _synthetic_postx("ambiguous", "SEQUENCE", mutant)
    results.append(_check("ambiguous plane: postX stays near the 0.5 base rate",
                          abs(amb_postx - 0.5) <= 0.10,
                          f"postX={amb_postx:.4f} cov={amb_cov:.4f}"))

    # 7. The mutant is exactly the forward peek and nothing else.
    results.append(_check("mutant adds only the next-gap field",
                          set(view_fields("SEQUENCE", MUTANT_PEEK))
                          - set(view_fields("SEQUENCE", "")) == {PEEK_FIELD},
                          ""))

    # 8. Bootstrap and Wilson wiring.
    low, high = S1.wilson(35, 100)
    results.append(_check("wilson imported from sweep 1", low < 0.35 < high,
                          f"{low:.4f}..{high:.4f}"))

    width = max(len(name) for name, _ok, _detail in results)
    for name, ok, detail in results:
        print(f"{'PASS' if ok else 'FAIL'} {name:{width}s} {detail}")
    failures = sum(1 for _name, ok, _detail in results if not ok)
    label = f"mutant={mutant}" if mutant else "clean"
    print(f"\nselftest {label}: {len(results) - failures}/{len(results)} pass"
          f"{'' if not failures else f'  RED ({failures} failed)'}")
    return 1 if failures else 0


# --------------------------------------------------------------------------
# Hypothesis log and receipt.
# --------------------------------------------------------------------------

def log_rows(report: Mapping[str, object]) -> list[dict[str, object]]:
    stamp = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    shared = {
        "registered_utc": stamp, "spec_sha": SPEC_SHA, "code_sha": code_sha(),
        "split_sha": S1.split_sha(), "outcome_law_sha": S1.outcome_law_sha(),
        "null_seed": SEED, "parent_trial": PARENT_TRIAL,
        "selection_rule": SELECTION_RULE, "verdict": "",
        "days": sum(report["asset_days"].values()),
    }
    metrics = report["metrics"]
    nulls = report["null"]
    rows: list[dict[str, object]] = []
    counter = 0
    for view in VIEWS:
        counter += 1
        cover = [metrics[a]["views"][view]["pooled"]["coverage"] for a in ASSETS]
        delays = [metrics[a]["views"][view]["pooled"]["decision_delay_median_s"]
                  for a in ASSETS]
        delays = [d for d in delays if d is not None]
        margins = [_get(nulls, "by_cell", f"{a}/{view}/pooled", "p_max_adjusted")
                   for a in DECIDING]
        margins = [m for m in margins if m is not None]
        note = "postX " + "/".join(
            (f"{metrics[a]['views'][view]['pooled']['postx1800']:.3f}"
             if metrics[a]["views"][view]["pooled"]["postx1800"] is not None
             else "-") for a in ASSETS)
        rows.append({
            **shared, "id": f"sweep9-{counter:03d}", "family": FAMILY,
            "rule": f"TWINS/{view}",
            "params": json.dumps([KNN, COVERAGE_TARGET, CLOCK_WINDOW_S,
                                  REMAIN_MIN_S]),
            "coverage": float(np.mean(cover)) if cover else None,
            "delay_med_s": float(np.mean(delays)) if delays else None,
            "err_rate_hg": metrics["HG"]["views"][view]["pooled"]["postx1800"],
            "err_rate_nkd": metrics["NKD"]["views"][view]["pooled"]["postx1800"],
            "err_rate_si": metrics["SI"]["views"][view]["pooled"]["postx1800"],
            "null_margin": min(margins) if margins else None,
            "note": (f"{report['letters']['overall']};{note}")[:60],
        })
    counter += 1
    rows.append({
        **shared, "id": f"sweep9-{counter:03d}", "family": FAMILY,
        "rule": "CERTIFICATE/LETTER",
        "params": json.dumps([KNN, COVERAGE_TARGET, CLOCK_WINDOW_S, REMAIN_MIN_S]),
        "coverage": float(np.mean(
            [metrics[a]["views"]["UNION"]["pooled"]["coverage"] for a in ASSETS])),
        "note": (f"{report['letters']['overall']}: "
                 f"{report['letters']['routes']}")[:60],
    })
    return rows


def _json_default(value: object) -> object:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    raise TypeError(f"unserialisable: {type(value)!r}")


def write_report(report: Mapping[str, object]) -> None:
    OUT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True,
                                   default=_json_default) + "\n")


def forecast_variance(cells: Sequence[S8.Cell8]) -> dict[tuple[str, int], float]:
    store = CTX.ContextStore()
    out: dict[tuple[str, int], float] = {}
    for cell in cells:
        key = (cell.asset, cell.d8)
        if key in out:
            continue
        payload = store.context_for(cell.asset, cell.d8)
        row = payload.get("forecast")
        if isinstance(row, Mapping) and row.get("forecast_variance"):
            out[key] = float(row["forecast_variance"])
    return out


def run(assets: Sequence[str] = ASSETS) -> tuple:
    mutant = _mutant()
    cells, days, skipped = S8.build_cells(assets)
    # The tape series are read once per cell so the row plane can take the
    # last-10-bar quote and volume ratios without re-opening the flow shard.
    tape = load_tape(cells)
    forecast = forecast_variance(cells)
    plane = build_plane(cells, forecast, tape, mutant)
    repro = reproduce_sweep8(cells, days, skipped, plane)
    if not repro["matches"]:
        raise SweepRefusal("sweep 8 opportunity counts did not reproduce; "
                           "no measurement is believed past this point")
    plane.asset_days = {asset: int(days.get(asset, 0)) for asset in ASSETS}
    scaled = scale_plane(plane)
    regimes, edges = regime_labels(plane)
    runs = run_views(plane, scaled, mutant)
    metrics = measure(plane, runs, regimes)
    nulls = null_test(plane, runs, regimes)
    block = letters(metrics, nulls)
    report = {
        "schema": "QRE2MILLSWEEP9", "spec_sha": SPEC_SHA, "code_sha": code_sha(),
        "split_sha": S1.split_sha(), "outcome_law_sha": S1.outcome_law_sha(),
        "seed": SEED, "mutant": mutant, "parent_trial": PARENT_TRIAL,
        "asset_days": plane.asset_days, "cells": plane.cells_total,
        "certifiable_cells": plane.certifiable, "plane_counters": plane.counters,
        "rows": plane.n,
        "sweep8_reproduction": repro,
        "regime_edges": edges,
        "bars": {view: runs[view].bar_info for view in VIEWS},
        "e1_control_bar": runs[VIEWS[0]].e1_bar_info,
        "metrics": metrics, "null": nulls, "letters": block,
    }
    return report, plane, repro, metrics, nulls, block


def load_tape(cells: Sequence[S8.Cell8]
              ) -> dict[int, tuple[np.ndarray, np.ndarray]]:
    """Each cell's quote-event and volume series, keyed by cell position."""

    cache: dict[tuple[str, int], dict] = {}
    out: dict[int, tuple[np.ndarray, np.ndarray]] = {}
    for cell in cells:
        key = (cell.asset, cell.d8)
        if key not in cache:
            cache[key] = FLOW.load_flow(cell.asset, cell.d8)
        arrays = cache[key][(cell.phase, int(cell.rec.phase_open_ts_ns))]
        out[cell.position] = (
            np.asarray(arrays["quote_events"], np.float64)[:cell.n],
            np.asarray(arrays["vol"], np.float64)[:cell.n])
    return out


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--no-log", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    report, plane, repro, metrics, nulls, block = run()
    print(f"sweep 9 spec_sha {SPEC_SHA[:16]} code_sha {code_sha()[:16]} "
          f"seed {SEED} mutant {_mutant() or 'none'}")
    print_reproduction(repro)
    print_plane(plane)
    print_metrics(metrics, nulls)
    print_letters(block)
    write_report(report)
    print(f"\nwrote {OUT_PATH}")
    if not args.no_log:
        rows = log_rows(report)
        written = S1.append_log(rows)
        print(f"appended {written} hypothesis-log rows to {LOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
