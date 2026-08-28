#!/usr/bin/env python3
"""Sweep 24: F19-LEVELCOLLISION-ZONEANCHOR, the corrected F19 read.

Sol's reconciliation ``.audit/briefs/mill-structbreak-sol-out.md`` sections A
and B refused sweep 22 as ``REFUSE, ZONE-MISCENTERED``.  The run reproduced,
its certificates matched and its leak mutant went red, but its barrier score
read the level cache at the READING BAR'S MID rather than at the candidate's
fixed zone price.  Zero of 14,650 approach reads and zero of 1,875 episode-close
reads were centred on the zone they named; the median approach read sat 1.90
zone widths away and every episode-close read sat more than two widths away, at
which distance the cached band is DISJOINT from the barrier band.  The selector
in sweep 22's SPEC was therefore never executed.

THE ONE CHANGE UNDER TEST.  This unit reruns sweep 22 with the barrier score B
computed through ``tools/mill/levels_zone.py`` at the candidate's FIXED
``zone_price``, and with the exhaustive letter partition sweep 23 proved.
Everything else is sweep 22's, imported and called, not re-implemented: the same
zone catalogue and formation pass (``S22.formation_pass``, 14,650 candidates or
the run refuses), the same two lanes, the same impulse ridge, the same monotone
selector functional and fold law, the same neighbour grid, the same frozen
outcome law with the 1800 s label beside, the same chronological seat replay,
MDD ledgers, stresses, C1 matched control, C2 ceilings and C3 block nulls.  The
attribution is therefore clean: any difference from sweep 22 is the price key.

THE BARRIER READ LAW.  For lane 1, B is read at ``zone_price`` with the trained
width, on the side defending against the approach (``fade_side``), stamped at
the arming decision (the approach bar's close).  For lane 2 the definition and
the side are IDENTICAL and only the stamp moves: the episode-close bar's close,
never the entry bar.  Every accessor result must echo ``center_price ==
zone_price`` exactly; the run asserts this per row and refuses on any mismatch.

THE DAY-SCALE TERM.  Sol accepted sweep 22's third component as lawful but
refused its name.  It is consumed here as ``day_scale_persistence`` and reported
as a day-scale persistence and location proxy.  No result from it claims that
prior-day defence memory was measured.

MUTANTS.  ``QRE2_MILL_S24_MUTANT=center_uses_current_mid`` pushes the accessor's
own registered defect (the reading bar's mid replaces the zone price) and must
turn the centre gate and the planted recovery red.
``QRE2_MILL_S24_MUTANT=selector_uses_test_day`` standardizes and cuts including
the scoring day and must turn the leak guard red.

EXPLORE only, kill-only tier, no packs, no HOLD, no teacher labels, no 2021, no
2025H2, no commits, no freeze, nothing executable.
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

import levels as LV  # noqa: E402
import levels_zone as LZ  # noqa: E402
import sweep1 as S1  # noqa: E402
import sweep8 as S8  # noqa: E402
import sweep9_twins as S9  # noqa: E402
import sweep12 as S12  # noqa: E402
import sweep14 as S14  # noqa: E402
import sweep19 as S19  # noqa: E402
import sweep22 as S22  # noqa: E402

# --------------------------------------------------------------------------
# The law, registered before anything is read.
# --------------------------------------------------------------------------

SPEC = """QRE2MILLSWEEP24
tier=exploratory; EXPLORE-only, kill-only.  Family F19-LEVELCOLLISION-ZONEANCHOR,
  the corrected rerun of the refused F19.  Seed 20260827.  Parent trial
  sweep22-033.  NO COMMITS, NO FREEZE, no packs, no HOLD, no teacher labels, no
  2021, no 2025H2.  Two entry lanes in ONE max-stat family, per the USER.
INHERITANCE.  Sweep 22 is imported and called READ-ONLY.  Its SPEC governs every
  clause not restated here: the GATE, the zone catalogue, the zone width and its
  snap to the cache's own band multipliers, candidate formation and the dedup
  lock, the fold-trained lane parameters, lane 1's pre-touch resting limit with
  its raw-tick fill and cancel law, lane 2's episode-resolution entry at the next
  bar after the episode close in the exit direction, the impulse ridge, the
  neighbour grid, the frozen outcome law with the 1800 s label beside, the
  chronological replay, the MDD ledgers, the two stresses, and controls C1, C2
  and C3.  The formation pass must return 14,650 candidates or this unit refuses:
  an identical universe is what makes the one change attributable.
THE ONE CHANGE.  The barrier score B is read through tools/mill/levels_zone.py at
  the candidate's FIXED zone_price with the trained half width, replacing sweep
  22's read of the level-cache row at the reading bar's mid.  B is the mean of
  three train-fold-standardized differences: (sd_held - sd_broke),
  day_scale_persistence and (ps_held - ps_broke), all three returned by one
  accessor call at the zone price.
THE BARRIER READ LAW.  Lane 1: side = the defending side against the approach
  (fade_side = -approach_side), decision stamp = the arming decision, the
  approach bar's lattice close, day-scale mode "approach".  Lane 2: the SAME B
  definition and the SAME side, decision stamp = the episode-close bar's close,
  NEVER the entry bar, day-scale mode "close" (sweep 22's lane-2 day-scale form).
  Every returned row must echo center_price == zone_price exactly and
  max_source_stamp strictly below the decision stamp; either miss refuses the run.
THE PARENT'S LANE-2 FALLBACK, carried unchanged.  Sweep 22 scores a candidate
  whose episode never resolved from its APPROACH bar's row in lane 2, with the
  day-scale negative term left at its zero default, and those rows enter the
  lane-2 training fold although they can never trade in that lane.  This unit
  reproduces that rule component for component at the corrected zone price:
  12,775 of 14,650 candidates take the approach read.  Dropping them instead
  would leave 1,875 fold rows, pin every barrier and margin cut to zero and make
  the neighbour grid degenerate - a SECOND change beside the price key, which
  would destroy the attribution this unit exists to make.  The run refuses if
  the fallback covers any candidate other than those with no episode close, and
  the receipt reports the dropped-row grid beside the carried one as
  information.
NAMING RESTRICTION, binding.  The third component is consumed as
  day_scale_persistence and reported as a day-scale persistence and location
  proxy.  It is NOT prior-day defence memory and no result may claim it is.
SELECTOR, unchanged from sweep 22 and identical across lanes.  B and the frozen
  impulse score I are each standardized on the training fold per asset x phase,
  over strictly prior EXPLORE days only, with the >= 25 prior day warmup and the
  >= 40 training candidate floor.  TRADE IFF B >= the train TOP-TERCILE cut AND
  (B - I) >= the train MEDIAN cut.  Grid (quartile, tercile) x (median, p60);
  the registered LIVE cell is (tercile, median).
INFORMATION, not a gate.  The Spearman rank correlation between this unit's
  zone-anchored B and sweep 22's miscentered B over the shared candidates is
  reported per lane per asset, on the raw component mean and on the standardized
  selector score, together with the share of selection decisions that flip.
LETTERS, the exhaustive partition, sweep 23's proved structure with this
  family's names.  Five clauses, one precedence, no fallthrough:
  LEVELCOLLISION-LIVE when a lane has NKD and SI each above 1500 USD per
    asset-day at the point estimate AND at mean minus two asset-day-block
    standard errors, every binding MDD below 1000, cap and occupancy lawful,
    both stresses clearing MDD, the paired matched control surviving maxT at
    0.05 on BOTH deciding assets, and the neighbours not flipping the sign.
  LEVELCOLLISION-KILL clause K1 when the formed ceiling misses either deciding
    rung.
  LEVELCOLLISION-KILL clause K2 when a powered deciding asset has a non-positive
    95 percent simultaneous upper bound against its matched control.
  LEVELCOLLISION-KILL clause K3, CEILING-UNREACHED, when the formed ceiling
    carries both rungs, no deciding upper bound is non-positive, and the causal
    matched delta is not positive on both deciding assets.
  LEVELCOLLISION-UNRESOLVED when the formed ceiling carries both rungs AND the
    causal matched delta is positive on both deciding assets, but a live or
    power bound fails.
  A letter per lane, plus the family letter: LIVE if any lane is LIVE, else
  UNRESOLVED if any lane earns it, else KILL with the clause named.  The selftest
  proves the partition over all 512 outcome points and constructs a receipt for
  every clause.
MUTANTS.  QRE2_MILL_S24_MUTANT=center_uses_current_mid substitutes the reading
  bar's mid for the zone price inside the accessor - the refused defect - and
  must red the centre gate and the planted recovery.
  QRE2_MILL_S24_MUTANT=selector_uses_test_day computes the selector's cuts
  including the scoring day and must red the leak guard.
"""

ASSETS = S22.ASSETS
DECIDING = S22.DECIDING
REPORT_ONLY = S22.REPORT_ONLY
SEED = S22.SEED

FAMILY = "F19-LEVELCOLLISION-ZONEANCHOR"
PARENT_TRIAL = "sweep22-033"
SELECTION_RULE = ("none: parent-preregistered two-lane formation, one monotone "
                  "selector, fold-trained thresholds, no model search; the only "
                  "change is the zone-anchored barrier read")

LOG_PREFIX = "sweep24"
OUT_PATH = ROOT / ".audit/mill-sweep24.json"
LOG_PATH = S1.LOG_PATH

EXPECT_CANDIDATES = 14_650

# Inherited, aliased so an upstream drift fails loudly here.
LANES = S22.LANES
LANE_NAME = S22.LANE_NAME
CLOSE = S22.CLOSE
FIXED = S22.FIXED
LABELS = S22.LABELS
GRID = S22.GRID
LIVE_CELL = S22.LIVE_CELL
BARRIER_CUTS = S22.BARRIER_CUTS
MARGIN_CUTS = S22.MARGIN_CUTS
MIN_PRIOR_DAYS = S22.MIN_PRIOR_DAYS
MIN_TRAIN_CANDS = S22.MIN_TRAIN_CANDS
DAY_RUNG_USD = S22.DAY_RUNG_USD
MDD_CEILING = S22.MDD_CEILING
PORTFOLIO_CAP = S22.PORTFOLIO_CAP
CONTROL_DRAWS = S22.CONTROL_DRAWS
SIGN_DRAWS = S22.SIGN_DRAWS
HINDSIGHT_CEILING = S22.HINDSIGHT_CEILING
IMPULSE_HORIZON_S = S22.IMPULSE_HORIZON_S

# The day-scale mode each lane consumes.  Lane 2 keeps sweep 22's own lane-2
# form; only the stamp it is evaluated at moves to the episode close.
LANE_DAY_SCALE_MODE = {"L1_PRETOUCH": "approach", "L2_EPISODE": "close"}

LETTER_LIVE = "LEVELCOLLISION-LIVE"
LETTER_UNRESOLVED = "LEVELCOLLISION-UNRESOLVED"
LETTER_KILL = "LEVELCOLLISION-KILL"
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

C3_CAVEAT = (
    "sweep 22's stated caveat, carried unchanged: the block null re-draws the "
    "SAME selected count uniformly inside each (asset, phase, day) block of "
    "formed candidates, so it tests only WHERE inside a block the selector "
    "picked - never how many it picked, nor on which days, nor whether the "
    "formed universe itself is special.  Its p is unadjusted across lines and "
    "carries none of the family maxT correction, so a single small p here is "
    "not a family result")

MUTANT_ENV = "QRE2_MILL_S24_MUTANT"
MUTANT_CENTER = "center_uses_current_mid"
MUTANT_TESTDAY = "selector_uses_test_day"
MUTANTS = (MUTANT_CENTER, MUTANT_TESTDAY)

# The planted world.  Prices are mid2, ATR is 100 units, so at band multiplier
# 0.10 the zone HALF width is 10.  Every number below is arithmetic.
PLANT_ATR = 100.0
PLANT_WIDTH = 10.0
PLANT_DEFENDED = 1000.0
PLANT_UNDEFENDED = 1400.0


class SweepRefusal(RuntimeError):
    pass


SPEC_SHA = S1._sha_text(SPEC)


def code_sha() -> str:
    """This unit plus the two modules whose behaviour it is asserting."""

    return S1._sha_text("\n".join(
        S1._sha_file(Path(path).resolve()) for path in (
            __file__,
            Path(__file__).resolve().parent / "sweep22.py",
            Path(__file__).resolve().parent / "levels_zone.py")))


def _mutant() -> str:
    name = os.environ.get(MUTANT_ENV, "")
    if name and name not in MUTANTS:
        raise SweepRefusal(f"unknown sweep 24 mutant: {name}")
    return name


def arm_mutant(mutant: str) -> str:
    """The centre mutant lives inside the accessor, so it is armed by env.

    ``levels_zone`` reads its own environment variable at every centre
    resolution.  Arming it here - and only here - keeps the defect at the one
    choke point the accessor registered for it.
    """

    if mutant == MUTANT_CENTER:
        os.environ[LZ.MUTANT_ENV] = LZ.MUTANT_CENTER_MID
    return mutant


# --------------------------------------------------------------------------
# The zone-anchored barrier read.  One accessor call per (candidate, lane).
# --------------------------------------------------------------------------

@dataclass(slots=True)
class ZoneRead:
    """What one lane's read produced, with the evidence that it is at the zone."""

    raw: np.ndarray                 # (n, 3) the three defence differences
    have: np.ndarray                # (n,) bool, the read landed
    center_gap: np.ndarray          # (n,) |center echoed - zone asked for|
    source_gap: np.ndarray          # (n,) max source stamp - decision stamp
    day_scale_held: np.ndarray      # (n,) the proxy's positive term, for the
                                    # parent's lane-2 fallback
    counters: dict


def lane_queries(cands: Sequence[S22.Cand], records: Sequence[S1.CellRec],
                 lane: str) -> tuple[list[LZ.ZoneQuery], list[int]]:
    """One query per candidate that HAS this lane's decision stamp.

    Lane 1's stamp is the approach bar's lattice close, the arming decision.
    Lane 2's stamp is the episode-CLOSE bar's close.  The entry bar is never a
    decision stamp: it is when the position is taken, not when it is decided.
    """

    if lane not in LANES:
        raise SweepRefusal(f"unknown lane: {lane}")
    mode = LANE_DAY_SCALE_MODE[lane]
    queries: list[LZ.ZoneQuery] = []
    positions: list[int] = []
    for position, cand in enumerate(cands):
        bar = int(cand.bar) if lane == "L1_PRETOUCH" else int(cand.close_bar)
        if bar < 0:
            continue
        lat = np.asarray(records[int(cand.cell)].lat, np.int64)
        if not 0 <= bar < len(lat):
            continue
        queries.append(LZ.ZoneQuery(
            cell=int(cand.cell), zone_price=float(cand.zone_price),
            band_width=float(cand.width), decision_stamp_ns=int(lat[bar]),
            side=int(cand.fade_side), zone_kind=str(cand.zone_kind),
            approach_side=int(cand.approach_side), day_scale_mode=mode))
        positions.append(position)
    return queries, positions


def zone_read(cands: Sequence[S22.Cand], records: Sequence[S1.CellRec],
              lane: str, reader: LZ.ZoneReader,
              fallback: ZoneRead | None = None) -> ZoneRead:
    """B's three components at the FIXED zone price, with the centre gate.

    The gate is not a diagnostic.  A row whose echoed centre differs from the
    zone price by any amount is the refused defect, so it raises rather than
    scoring, and the run stops.

    ``fallback`` carries the parent's lane-2 rule for candidates whose episode
    never resolved.  Sweep 22 scores those in lane 2 from the APPROACH bar's row
    (``lev_close if cand.lev_close is not None else cand.lev_approach``) with
    ``pd_broke_close`` still at its zero default, and they enter the lane-2
    training fold even though they can never trade in it.  Dropping them would
    empty 12,775 of 14,650 fold rows and pin every cut to zero, which would be a
    SECOND change beside the price key and would destroy the attribution this
    unit exists to make.  The parent's rule is therefore carried unchanged, and
    the diagnostic beside it reports what the lane-2 grid looks like without it.
    """

    queries, positions = lane_queries(cands, records, lane)
    rows = reader.rows(queries) if queries else []
    raw = np.full((len(cands), 3), np.nan, np.float64)
    have = np.zeros(len(cands), bool)
    center_gap = np.full(len(cands), np.nan, np.float64)
    source_gap = np.full(len(cands), np.nan, np.float64)
    held = np.full(len(cands), np.nan, np.float64)
    counters = {"queries": len(queries), "rows": len(rows),
                "center_exact": 0, "center_mismatched": 0,
                "strictly_prior": 0, "not_strictly_prior": 0,
                "prior_session_served": 0, "prior_session_absent": 0,
                "same_day_defined": 0, "same_day_undefined": 0,
                "day_scale_defined": 0, "day_scale_undefined": 0,
                "fallback_to_approach_read": 0}
    worst_center = 0.0
    worst_source = -(1 << 62)
    for row, query, position in zip(rows, queries, positions):
        gap = abs(float(row.center_price) - float(query.zone_price))
        center_gap[position] = gap
        worst_center = max(worst_center, gap)
        if float(row.center_price) == float(query.zone_price):
            counters["center_exact"] += 1
        else:
            counters["center_mismatched"] += 1
        delta = int(row.max_source_stamp) - int(row.decision_stamp_ns)
        source_gap[position] = float(delta)
        worst_source = max(worst_source, delta)
        if delta < 0:
            counters["strictly_prior"] += 1
        else:
            counters["not_strictly_prior"] += 1
        counters["prior_session_served" if row.ps_served
                 else "prior_session_absent"] += 1
        counters["same_day_defined" if math.isfinite(row.sd_touches)
                 else "same_day_undefined"] += 1
        counters["day_scale_defined" if math.isfinite(row.day_scale_persistence)
                 else "day_scale_undefined"] += 1
        raw[position] = (float(row.sd_held) - float(row.sd_broke),
                         float(row.day_scale_persistence),
                         float(row.ps_held) - float(row.ps_broke))
        held[position] = float(row.day_scale_held)
        have[position] = True
    counters["worst_center_gap_mid2"] = float(worst_center)
    counters["worst_source_minus_decision_ns"] = int(
        worst_source if rows else -1)
    if fallback is not None:
        # The parent's fallback, component for component: the approach bar's
        # same-day and prior-session pairs, and its day-scale term with the
        # negative half at the zero sweep 22 leaves it at for an unresolved
        # episode (``pd_broke_close`` is never assigned there).
        for position in range(len(cands)):
            if have[position] or not fallback.have[position]:
                continue
            raw[position] = (float(fallback.raw[position, 0]),
                             float(fallback.day_scale_held[position]) - 0.0,
                             float(fallback.raw[position, 2]))
            held[position] = float(fallback.day_scale_held[position])
            have[position] = True
            counters["fallback_to_approach_read"] += 1
    return ZoneRead(raw=raw, have=have, center_gap=center_gap,
                    source_gap=source_gap, day_scale_held=held,
                    counters=counters)


def assert_zone_anchored(read: ZoneRead, lane: str) -> None:
    """The refusal Sol's ruling requires, per row, before anything is scored."""

    if read.counters["center_mismatched"]:
        raise SweepRefusal(
            f"{lane}: {read.counters['center_mismatched']} of "
            f"{read.counters['rows']} barrier reads are not centred on the "
            f"candidate zone (worst gap "
            f"{read.counters['worst_center_gap_mid2']} mid2); this is the "
            f"refused F19 defect and nothing may be priced past it")
    if read.counters["not_strictly_prior"]:
        raise SweepRefusal(
            f"{lane}: {read.counters['not_strictly_prior']} barrier reads have "
            f"a source stamp at or after their own decision stamp (worst "
            f"{read.counters['worst_source_minus_decision_ns']} ns)")


# --------------------------------------------------------------------------
# Rank correlation, reported as information beside the corrected score.
# --------------------------------------------------------------------------

def _ranks(values: np.ndarray) -> np.ndarray:
    """Average ranks, so ties do not manufacture correlation."""

    order = np.argsort(values, kind="mergesort")
    ranked = np.empty(len(values), np.float64)
    ranked[order] = np.arange(len(values), dtype=np.float64)
    sorted_values = values[order]
    start = 0
    for index in range(1, len(values) + 1):
        if index == len(values) or sorted_values[index] != sorted_values[start]:
            if index - start > 1:
                ranked[order[start:index]] = float(start + index - 1) / 2.0
            start = index
    return ranked


def spearman(left: Sequence[float], right: Sequence[float]) -> float | None:
    a = np.asarray(left, np.float64)
    b = np.asarray(right, np.float64)
    keep = np.isfinite(a) & np.isfinite(b)
    if int(keep.sum()) < 3:
        return None
    ra = _ranks(a[keep])
    rb = _ranks(b[keep])
    ra = ra - ra.mean()
    rb = rb - rb.mean()
    denominator = float(np.sqrt((ra * ra).sum() * (rb * rb).sum()))
    if not denominator > 0.0:
        return None
    return float((ra * rb).sum() / denominator)


# --------------------------------------------------------------------------
# The selector.  Sweep 22's fold law verbatim, with B's components supplied.
# --------------------------------------------------------------------------

def score_selector(cands: Sequence[S22.Cand], raw: np.ndarray, lane: str,
                   impulse: np.ndarray,
                   explore_days: Mapping[str, Sequence[int]], mutant: str
                   ) -> tuple[list[S22.Scored], dict[str, object]]:
    """B and I standardized on the training fold, then the frozen monotone rule.

    This is ``S22.score_selector`` with one argument added: the (n, 3) matrix of
    barrier components.  Sweep 22 computed that matrix from the cache row at the
    reading bar's mid; here it arrives from the fixed-zone accessor.  Every other
    step - the stratum, the warmup, the training floor, the standardization, the
    cut percentiles and the monotone rule - is byte-for-byte the parent's, and
    the selftest asserts the two agree when fed the same matrix.
    """

    raw = np.asarray(raw, np.float64)
    if raw.shape != (len(cands), 3):
        raise SweepRefusal(f"barrier component matrix is {raw.shape}, expected "
                           f"{(len(cands), 3)}")
    by_stratum: dict[tuple[str, str], dict[int, list[int]]] = {}
    for position, cand in enumerate(cands):
        by_stratum.setdefault((cand.asset, cand.phase), {}).setdefault(
            cand.d8, []).append(position)
    out: list[S22.Scored] = []
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
                out.append(S22.Scored(lane=lane, position=int(position),
                                      b=float(b_score[local]),
                                      i=float(i_score[local]),
                                      margin=float(margin[local]),
                                      selected=selected))
                report["rows"] += 1
    return out, report


# --------------------------------------------------------------------------
# The letters.  Five clauses, a registered precedence, a real partition.
# --------------------------------------------------------------------------

def classify(rung_ok: bool, mdd_ok: bool, cap_ok: bool, stress_ok: bool,
             control_ok: bool, neighbours_ok: bool, ceiling_carries: bool,
             upper_nonpositive: bool, matched_positive: bool
             ) -> tuple[str, str, list[str]]:
    """The registered partition.  Exactly one clause fires; the rest are listed.

    Sweep 22's receipt had to record a FALLTHROUGH because the parent's three
    letters left a hole: a ceiling that carries both rungs, no non-positive
    upper bound, and a matched delta negative on one decider matched neither
    UNRESOLVED nor either registered KILL clause.  That hole is clause K3,
    CEILING-UNREACHED.  The chain is exhaustive by construction: LIVE is the
    conjunction of every live bound, and its negation splits on
    ceiling_carries, then upper_nonpositive, then matched_positive, with
    UNRESOLVED taking the remainder.
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
                       "is the enumeration gap the corrected family closes")


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
# The run.  Sweep 22's passes, called; one barrier read, replaced.
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

    # ---- formation: the parent's, unchanged, and the universe must match ----
    cands, formation = S22.formation_pass(cells, explore_days, "")
    if not formation["strictly_prior"]:
        raise SweepRefusal(
            f"a level read is not strictly prior to its entry stamp: "
            f"max(source - stamp) = {formation['max_src_minus_stamp_ns']} ns")
    if len(cands) != EXPECT_CANDIDATES:
        raise SweepRefusal(
            f"the formation pass returned {len(cands)} candidates, not the "
            f"parent's {EXPECT_CANDIDATES}; the universe is not identical, so "
            f"the one change under test is not attributable")

    # ---- THE ONE CHANGE: the barrier read, at the fixed zone price ----------
    reader = LZ.reader(ASSETS)
    zone_reads: dict[str, ZoneRead] = {}
    approach = zone_read(cands, records, "L1_PRETOUCH", reader)
    assert_zone_anchored(approach, "L1_PRETOUCH")
    zone_reads["L1_PRETOUCH"] = approach
    episode = zone_read(cands, records, "L2_EPISODE", reader,
                        fallback=approach)
    assert_zone_anchored(episode, "L2_EPISODE")
    zone_reads["L2_EPISODE"] = episode
    # The parent's fallback must cover exactly the candidates whose episode
    # never resolved, and no others.  A drift either way means the lane-2 fold
    # is not the parent's, and the one change under test stops being the only
    # change.
    unresolved = sum(1 for cand in cands if int(cand.close_bar) < 0)
    if episode.counters["fallback_to_approach_read"] != unresolved:
        raise SweepRefusal(
            f"the lane-2 fallback covered "
            f"{episode.counters['fallback_to_approach_read']} candidates, but "
            f"{unresolved} formed no episode close; the lane-2 training fold "
            f"is not the parent's")
    # Disclosed beside it, not gating: what the lane-2 fold would be if those
    # rows were dropped instead of carried.  Built by masking, not by a second
    # accessor pass, so it costs nothing and cannot drift from the read above.
    no_fallback_raw = np.array(episode.raw, np.float64)
    for position, cand in enumerate(cands):
        if int(cand.close_bar) < 0:
            no_fallback_raw[position] = np.nan

    priced = S22.pricing_pass(cands, cells, streams, records, explore_days, "")
    if priced["plane_checks"]["mismatched"]:
        raise SweepRefusal(
            "a lane-2 close-label cert disagreed with the frozen cert plane at "
            f"the same (cell, side, bar): worst "
            f"{priced['plane_checks']['worst_abs_usd']:.6f} USD")

    folds, impulse_report = S22.fit_impulse(priced["mag"], explore_days, "")
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
    impulse, impulse_counters = S22.impulse_scores(cands, folds)

    lane1 = priced["lane1"]
    lane2 = priced["lane2"]
    have = {"L1_PRETOUCH": lane1, "L2_EPISODE": lane2}
    formed_by_asset = {asset: sum(1 for c in cands if c.asset == asset)
                       for asset in ASSETS}
    formed_opportunities: dict[str, int] = {}
    for cand in cands:
        key = f"{cand.asset}|{cand.d8}"
        formed_opportunities[key] = formed_opportunities.get(key, 0) + 1

    scores: dict[str, list[S22.Scored]] = {}
    score_reports: dict[str, object] = {}
    for lane in LANES:
        rows, report_block = score_selector(cands, zone_reads[lane].raw, lane,
                                            impulse, explore_days, mutant)
        scores[lane] = rows
        score_reports[lane] = {k: v for k, v in report_block.items()
                               if k != "cuts"}
        score_reports[lane]["cut_sample"] = dict(
            list(report_block["cuts"].items())[:3])
        score_reports[lane]["zone_read"] = zone_reads[lane].counters

    # ---- information: how different is the corrected score? ----------------
    correlation = barrier_correlation(cands, zone_reads, impulse, explore_days,
                                      scores, mutant)
    # ---- information: the lane-2 fallback's effect on the fold -------------
    dropped_rows, dropped_report = score_selector(
        cands, no_fallback_raw, "L2_EPISODE", impulse, explore_days, mutant)
    fallback_diagnostic = {
        "carried": {
            "n_fold_rows_carried": int(
                episode.counters["fallback_to_approach_read"]),
            "selected_per_grid_cell": {
                f"{b}|{m}": sum(int(row.selected[(b, m)])
                                for row in scores["L2_EPISODE"]
                                if row.position in lane2)
                for (b, m) in GRID}},
        "dropped": {
            "selected_per_grid_cell": {
                f"{b}|{m}": sum(int(row.selected[(b, m)])
                                for row in dropped_rows
                                if row.position in lane2)
                for (b, m) in GRID},
            "days_scored": dropped_report["days_scored"]},
        "note": ("INFORMATION, not a gate.  Sweep 22 scores a candidate whose "
                 "episode never resolved from its APPROACH bar row in lane 2, "
                 "and those rows enter the lane-2 training fold.  This unit "
                 "carries that rule unchanged so the price key stays the only "
                 "change.  Dropping them instead leaves 1,875 of 14,650 fold "
                 "rows, pins every barrier and margin cut to zero and makes "
                 "the neighbour grid degenerate, which is a selector change "
                 "and not a corrected read")}

    live: dict[str, object] = {}
    grid_report: dict[str, object] = {}
    selected_entries: dict[str, list[S22.Priced]] = {}
    selected_positions: dict[str, list[int]] = {}
    for lane in LANES:
        pool = have[lane]
        by_cell = grid_report.setdefault(lane, {})
        for cut in GRID:
            picks = [row.position for row in scores[lane]
                     if row.selected.get(cut) and row.position in pool]
            entries = [pool[p] for p in picks]
            block = S22.evaluate_lane(lane, entries, cands, explore_days,
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

    for lane in LANES:
        entries = selected_entries[lane]
        stress: dict[str, object] = {}
        for kind in ("adversarial", "spread"):
            overrides = S22.stress_overrides(entries, CLOSE, kind)
            seated = S22.replay(entries, CLOSE, overrides)
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
            mean, se = S22._mean_se(series)
            cash[asset] = {
                "n": n, "usd_per_day": mean, "se_usd": se,
                "rung_usd": DAY_RUNG_USD[asset],
                "over_rung": (None if mean is None
                              else mean / DAY_RUNG_USD[asset]),
                "carries_rung": (None if mean is None
                                 else bool(mean >= DAY_RUNG_USD[asset]))}
        ceiling_block[lane] = {"cash": cash,
                               "hindsight_bits": list(HINDSIGHT_CEILING)}
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
        mean, _se = S22._mean_se(series)
        all_cash[asset] = {
            "n": n, "usd_per_day": mean, "rung_usd": DAY_RUNG_USD[asset],
            "over_rung": None if mean is None else mean / DAY_RUNG_USD[asset],
            "carries_rung": None if mean is None else bool(
                mean >= DAY_RUNG_USD[asset])}
    ceiling_block["FORMED_UNIVERSE"] = {"cash": all_cash,
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
        mean, _se = S22._mean_se(series)
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
        matched, counters = S22.match_controls(entries, cands,
                                               priced["g1_pool"], impulse,
                                               mag_bin)
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
        # The permutation diagnostic, now on the ZONE-ANCHORED components: give
        # each matched control a level vector drawn from a permutation inside the
        # pool and ask how often it would have carried a positive barrier.
        raw = zone_reads[lane].raw
        if len(cands) and matched:
            draw = rng.permutation(len(cands))
            hits = 0
            with np.errstate(invalid="ignore"):
                for slot, _position in enumerate(sorted(matched)):
                    donor = raw[int(draw[slot % len(draw)])]
                    value = float(np.nanmean(donor)) if np.isfinite(donor).any() \
                        else float("nan")
                    hits += int(math.isfinite(value) and value > 0.0)
            permuted_selected[lane] = {
                "n": len(matched),
                "share_permuted_positive_barrier": float(
                    hits / max(len(matched), 1))}
    family = [f"{lane}|{asset}" for lane in LANES for asset in DECIDING]
    control = S22.maxt_inference(control_lines, family)

    # ---- C3: block-permutation nulls, with the parent's caveat -------------
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
                explore_days, asset)

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
        "schema": "QRE2MILLSWEEP24", "spec_sha": SPEC_SHA,
        "code_sha": code_sha(), "split_sha": S1.split_sha(),
        "outcome_law_sha": S1.outcome_law_sha(), "seed": SEED,
        "mutant": mutant, "family": FAMILY, "parent_trial": PARENT_TRIAL,
        "selection_rule": SELECTION_RULE, "registered_utc": report_stamp(),
        "parent_spec_sha": S22.SPEC_SHA, "parent_code_sha": S22.code_sha(),
        "accessor_code_sha": S1._sha_file(
            Path(LZ.__file__).resolve()),
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
        "zone_read": {lane: zone_reads[lane].counters for lane in LANES},
        "zone_read_law": {
            "lane_stamp": {"L1_PRETOUCH": "approach bar close (the arming "
                                          "decision)",
                           "L2_EPISODE": "episode-close bar close (never the "
                                         "entry bar)"},
            "side": "fade_side, the side defending against the approach",
            "day_scale_mode": dict(LANE_DAY_SCALE_MODE),
            "third_component": "day_scale_persistence, a day-scale persistence "
                               "and location proxy, NOT prior-day defence "
                               "memory",
            "accessor": "tools/mill/levels_zone.py read_zone at zone_price"},
        "barrier_correlation": correlation,
        "lane2_fallback": fallback_diagnostic,
        "reader_counters": dict(reader.counters),
        "pricing_counters": priced["counters"],
        "coarse_counters": priced["coarse_counters"],
        "plane_checks": priced["plane_checks"],
        "impulse": impulse_report, "impulse_join": join,
        "impulse_counters": impulse_counters,
        "selector": score_reports, "grid": grid_report, "live": live,
        "ceiling": ceiling_block, "control": control,
        "control_counters": control_counters,
        "control_permutation": permuted_selected,
        "block_nulls": nulls, "block_null_caveat": C3_CAVEAT,
        "lane_extras": {"direction": direction, "window": window},
        "scoring_days": {a: scoring[a] for a in ASSETS},
        "clauses": CLAUSES, "clause_order": list(CLAUSE_ORDER),
        "elapsed_s": round(time.time() - started, 1)}
    letters = {lane: lane_letter(lane, report) for lane in LANES}
    if any(letters[lane]["letter"] == LETTER_LIVE for lane in LANES):
        family_letter = LETTER_LIVE
        family_clause = "LIVE"
    elif any(letters[lane]["letter"] == LETTER_UNRESOLVED for lane in LANES):
        family_letter = LETTER_UNRESOLVED
        family_clause = "UNRESOLVED"
    else:
        family_letter = LETTER_KILL
        family_clause = min(
            (letters[lane]["clause"] for lane in LANES),
            key=lambda c: CLAUSE_ORDER.index(c))
    report["letters"] = letters
    report["family_letter"] = family_letter
    report["family_clause"] = family_clause
    report["headline"] = headline(report)
    return report


def barrier_correlation(cands: Sequence[S22.Cand],
                        zone_reads: Mapping[str, ZoneRead],
                        impulse: np.ndarray,
                        explore_days: Mapping[str, Sequence[int]],
                        scores: Mapping[str, Sequence[S22.Scored]],
                        mutant: str) -> dict[str, object]:
    """How different is the corrected score from the refused one?

    Reported as INFORMATION, never as a gate.  Two rank correlations per lane
    per asset: on the raw component mean, and on the standardized selector score
    that actually gates.  The selection-flip share says how much of the decision
    the price key alone moved.
    """

    out: dict[str, object] = {}
    for lane in LANES:
        parent_raw = np.vstack([S22.barrier_components(cand, lane)
                                for cand in cands]) if len(cands) else np.zeros(
                                    (0, 3))
        parent_scores, _report = score_selector(
            cands, parent_raw, lane, impulse, explore_days, mutant)
        mine = {row.position: row for row in scores[lane]}
        theirs = {row.position: row for row in parent_scores}
        shared = sorted(set(mine) & set(theirs))
        with np.errstate(invalid="ignore"):
            mine_raw_mean = np.nanmean(zone_reads[lane].raw, axis=1)
            parent_raw_mean = np.nanmean(parent_raw, axis=1)
        by_asset: dict[str, object] = {}
        for asset in ASSETS:
            rows = [p for p in shared if cands[p].asset == asset]
            flips = sum(int(bool(mine[p].selected[LIVE_CELL])
                            != bool(theirs[p].selected[LIVE_CELL]))
                        for p in rows)
            by_asset[asset] = {
                "shared_candidates": len(rows),
                "rho_raw_component_mean": spearman(
                    [mine_raw_mean[p] for p in rows],
                    [parent_raw_mean[p] for p in rows]),
                "rho_selector_b": spearman([mine[p].b for p in rows],
                                           [theirs[p].b for p in rows]),
                "selected_zone_anchored": sum(
                    int(mine[p].selected[LIVE_CELL]) for p in rows),
                "selected_parent_miscentred": sum(
                    int(theirs[p].selected[LIVE_CELL]) for p in rows),
                "selection_flips": int(flips),
                "selection_flip_share": (float(flips / len(rows)) if rows
                                         else None)}
        out[lane] = by_asset
    return out


def headline(report: Mapping[str, object]) -> dict[str, object]:
    """Best lane's deciding usd/day over rung, then the formed ceiling beside."""

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
        "formed_ceiling_over_rung": {asset: ceiling[asset]["over_rung"]
                                     for asset in DECIDING},
        "capped_ceiling_over_rung": {asset: capped[asset]["over_rung"]
                                     for asset in DECIDING},
        "family_letter": report["family_letter"],
        "family_clause": report["family_clause"]}


# --------------------------------------------------------------------------
# Printing.  The parent's tables are reused; this unit adds the read receipt.
# --------------------------------------------------------------------------

_n = S22._n


def print_summary(report: Mapping[str, object]) -> None:
    head = report["headline"]
    best = ", ".join(
        f"{asset} {_n(head['best_lane_over_rung'].get(asset), 6, 3)}x"
        for asset in DECIDING)
    ceiling = ", ".join(
        f"{asset} {_n(head['formed_ceiling_over_rung'].get(asset), 6, 3)}x"
        for asset in DECIDING)
    print(f"SWEEP 24 zone-anchored: best lane {head['best_lane']} at {best} "
          f"rung; formed ceiling {ceiling} rung; family {head['family_letter']} "
          f"(clause {head['family_clause']})")


def print_zone_read(report: Mapping[str, object]) -> None:
    print("\n== THE ONE CHANGE: BARRIER READ AT THE FIXED ZONE PRICE ==")
    law = report["zone_read_law"]
    print(f"  accessor            : {law['accessor']}")
    print(f"  side                : {law['side']}")
    for lane in LANES:
        print(f"  {lane:<12} stamp : {law['lane_stamp'][lane]}, day-scale mode "
              f"{law['day_scale_mode'][lane]}")
    print(f"  third component     : {law['third_component']}")
    print("  lane          queries    rows  centre-exact  mismatch  "
          "worst-gap  strictly-prior  worst src-dec ns")
    for lane in LANES:
        cell = report["zone_read"][lane]
        print(f"  {lane:<13} {cell['queries']:>6} {cell['rows']:>7} "
              f"{cell['center_exact']:>13} {cell['center_mismatched']:>9} "
              f"{cell['worst_center_gap_mid2']:>10.1f} "
              f"{cell['strictly_prior']:>15} "
              f"{cell['worst_source_minus_decision_ns']:>17d}")
    print("  definedness: " + "; ".join(
        f"{lane} same-day {report['zone_read'][lane]['same_day_defined']}/"
        f"{report['zone_read'][lane]['rows']}, prior-session served "
        f"{report['zone_read'][lane]['prior_session_served']}, day-scale "
        f"{report['zone_read'][lane]['day_scale_defined']}"
        for lane in LANES))
    print(f"  accessor counters   : {report['reader_counters']}")
    print(f"  formation matches the parent's 14,650 candidates: "
          f"{report['candidates_match_parent']}")
    fall = report["lane2_fallback"]
    print(f"\n  lane-2 fallback (the parent's rule, carried unchanged): "
          f"{fall['carried']['n_fold_rows_carried']} candidates with no "
          f"episode close are scored from their approach-bar row")
    print(f"    selected per grid cell, carried : "
          f"{fall['carried']['selected_per_grid_cell']}")
    print(f"    selected per grid cell, dropped : "
          f"{fall['dropped']['selected_per_grid_cell']}   (INFORMATION only)")

    print("\n== INFORMATION: CORRECTED B vs SWEEP 22's MISCENTRED B ==")
    print("  rank correlation over the shared candidates; not a gate")
    print("  lane          asset  shared   rho(raw mean)  rho(selector B)   "
          "sel zone  sel parent   flips   flip share")
    for lane in LANES:
        for asset in ASSETS:
            cell = report["barrier_correlation"][lane][asset]
            print(f"  {lane:<13} {asset:<5} {cell['shared_candidates']:>7} "
                  f"{_n(cell['rho_raw_component_mean'], 14, 4)} "
                  f"{_n(cell['rho_selector_b'], 16, 4)} "
                  f"{cell['selected_zone_anchored']:>10} "
                  f"{cell['selected_parent_miscentred']:>11} "
                  f"{cell['selection_flips']:>7} "
                  f"{_n(cell['selection_flip_share'], 12, 4)}")


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
    print("  lane            letter                       rung  MDD  cap  "
          "stress  control  neighbours  ceiling  upper<=0  matched+")
    for lane in LANES:
        cell = report["letters"][lane]
        print(f"  {lane:<15} {cell['letter']:<28} {_n(cell['rung_ok'], 5)} "
              f"{_n(cell['mdd_ok'], 4)} {_n(cell['cap_ok'], 4)} "
              f"{_n(cell['stress_ok'], 6)} {_n(cell['control_ok'], 8)} "
              f"{_n(cell['neighbours_ok'], 11)} "
              f"{_n(cell['ceiling_carries_both_rungs'], 8)} "
              f"{_n(cell['upper_bound_nonpositive'], 9)} "
              f"{_n(cell['matched_delta_positive'], 9)}")
        print(f"      clause {cell['clause']}: {cell['clause_text']}")
        print(f"      clauses matching: {cell['clauses_matching']}")
        for reason in cell["reasons"]:
            print(f"      - {reason}")
    print(f"\n  FAMILY LETTER: {report['family_letter']} "
          f"(clause {report['family_clause']})")
    print("  the registered partition, exhaustive over all 512 outcome points:")
    for clause in CLAUSE_ORDER:
        print(f"    {clause:<11} -> {CLAUSE_LETTER[clause]:<26} "
              f"{CLAUSES[clause]}")


def print_c3_caveat(report: Mapping[str, object]) -> None:
    print(f"\n  C3 CAVEAT: {report['block_null_caveat']}.")


# --------------------------------------------------------------------------
# Selftest.  The planted collision world, rebuilt with the zone-anchored read.
# --------------------------------------------------------------------------

_check = S22._check


def plant_tape() -> tuple[LZ.Tape, dict[str, object]]:
    """Sweep 22's collision, rebuilt so each zone has RESOLVED prior history.

    Sweep 22 planted the cache's defence columns directly, so its path never
    had to earn a hold or a break at the zone.  The zone-anchored read counts
    real touches under ``levels.outcome_bars``, so the world now carries a
    prologue in which the defended zone genuinely holds and the undefended zone
    genuinely breaks, then departs and approaches each zone afresh.  Every count
    below is hand-derived in ``_selftest_planted``.
    """

    path = [
        940.0, 970.0,                      # 0-1   approach the defended zone
        995.0, 1005.0, 1000.0,             # 2-4   three touches of D = 1000
        985.0,                             # 5     <= 990: all three HELD
        960.0, 1200.0,                     # 6-7   leave D, travel to U
        1395.0, 1402.0,                    # 8-9   two touches of U = 1400
        1425.0,                            # 10    > 1412: both BROKE
        1300.0, 1150.0, 1050.0, 940.0,     # 11-14 fall away, arm D again
        960.0, 995.0,                      # 15-16 THE D APPROACH BAR is 16
        1004.0, 1006.0, 998.0,             # 17-19 the episode inside D
        975.0, 950.0, 930.0,               # 20-22 D holds, price rejects away
        1100.0, 1250.0, 1340.0,            # 23-25 travel back to U
        1385.0,                            # 26    THE U APPROACH BAR is 26
        1396.0, 1420.0, 1460.0,            # 27-29 U breaks upward again
        1500.0, 1460.0,                    # 30-31 the episode resolves up
    ]
    mid = np.asarray(path, np.float64)
    n = len(mid)
    ts = (np.arange(n, dtype=np.int64) * S1.BAR_NS + 1_600_000_000_000_000_000)
    tape = LZ.Tape(asset="HG", d8=20220315, ts=ts, mid=mid,
                   delta=np.zeros(n, np.float64), sourced=np.ones(n, bool))
    world = {"defended": PLANT_DEFENDED, "undefended": PLANT_UNDEFENDED,
             "width": PLANT_WIDTH, "atr": PLANT_ATR,
             "defended_bar": 16, "undefended_bar": 26,
             "defended_kind": "PD_HIGH", "undefended_kind": "PD_CLOSE",
             "approach_side": 1, "fade_side": -1}
    return tape, world


def planted_read(tape: LZ.Tape, zone: float, bar: int, world: Mapping[str, object],
                 kind: str) -> dict[str, object]:
    """One zone-anchored read on the fixture, through the accessor's own law.

    ``resolved_center`` is the accessor's single centre choke point, so the
    registered centre mutant reaches this fixture exactly as it reaches the real
    rows.
    """

    stamp = int(tape.ts[int(bar)])
    width = float(world["width"])
    side = int(world["fade_side"])
    window = LZ.prior_window(tape, stamp)
    center = LZ.resolved_center(float(zone), tape, window)
    same = LZ.same_day_counts(tape, center, width, side, stamp)
    scale = LZ.day_scale_terms(tape.mid, tape.ts, center, width, stamp,
                               zone_kind=kind,
                               approach_side=int(world["approach_side"]),
                               mode="approach")
    sd = float(same["held"]) - float(same["broke"])
    components = np.asarray([sd, float(scale["persistence"]), float("nan")],
                            np.float64)
    with np.errstate(invalid="ignore"):
        b = float(np.nanmean(components))
    return {"center": float(center), "zone": float(zone), "window": int(window),
            "sd_held": float(same["held"]), "sd_broke": float(same["broke"]),
            "sd_touches": float(same["touches"]),
            "day_scale_held": float(scale["held"]),
            "day_scale_broke": float(scale["broke"]),
            "day_scale_persistence": float(scale["persistence"]),
            "b": b}


def _selftest_planted() -> list[tuple[str, bool, str]]:
    """The planted collision, read AT the zone, hand-computed bar by bar.

    Defended zone D = 1000, half width 10, fade side -1 (the approach is from
    below, so the defending side is the one selling into it).  At the approach
    bar 16 the prior window is bars 0..15 and the band [990, 1010] was touched at
    bars 2 (995), 3 (1005) and 4 (1000).  Under ``levels.outcome_bars`` with side
    -1 a touch at P holds when a later bar prints at or below P - 10 before any
    bar prints above P + 10.  Bar 5 prints 985, which is <= 985, <= 995 and <=
    990, so all three hold at bar 5; the first bar above 1015 is bar 8 (1395), so
    every verdict is HELD and both verdict bars closed before bar 16.  Hence
    sd_held 3, sd_broke 0, difference +3.

    Undefended zone U = 1400 at approach bar 26: the prior window is bars 0..25
    and the band [1390, 1410] was touched at bars 8 (1395) and 9 (1402).  Bar 10
    prints 1425, above both 1405 and 1412, and the first bar at or below 1385 is
    bar 11 (1300), which is later, so both are BROKE.  Hence sd_held 0, sd_broke
    2, difference -2.

    Day scale: D is a PD_HIGH, a completed session's turn, so held = 1; U is a
    PD_CLOSE, which is not a turn kind, so held = 0.  Both windows have already
    printed 1425, which is above each zone's upper edge, so broke = 1 on both.
    Persistence is 0 for D and -1 for U.  B is the mean of the defined
    components: 1.5 for D and -1.5 for U.  The prior session is absent in the
    fixture, so the third component is NaN and does not enter the mean.
    """

    tape, world = plant_tape()
    out: list[tuple[str, bool, str]] = []
    defended = planted_read(tape, world["defended"], world["defended_bar"],
                            world, world["defended_kind"])
    undefended = planted_read(tape, world["undefended"], world["undefended_bar"],
                              world, world["undefended_kind"])

    out.append(_check(
        "the barrier is read AT the defended zone, not at the reading bar's mid",
        defended["center"] == world["defended"],
        f"centre {defended['center']} vs zone {world['defended']}, last "
        f"completed mid {float(tape.mid[defended['window'] - 1])}"))
    out.append(_check(
        "the barrier is read AT the undefended zone",
        undefended["center"] == world["undefended"],
        f"centre {undefended['center']} vs zone {world['undefended']}"))
    out.append(_check(
        "the defended zone's hand count is 3 held, 0 broke",
        defended["sd_held"] == 3.0 and defended["sd_broke"] == 0.0,
        f"touches {defended['sd_touches']}, held {defended['sd_held']}, broke "
        f"{defended['sd_broke']}"))
    out.append(_check(
        "the undefended zone's hand count is 0 held, 2 broke",
        undefended["sd_held"] == 0.0 and undefended["sd_broke"] == 2.0,
        f"touches {undefended['sd_touches']}, held {undefended['sd_held']}, "
        f"broke {undefended['sd_broke']}"))
    out.append(_check(
        "the day-scale persistence proxy is 0 at the defended zone and -1 at "
        "the undefended zone",
        defended["day_scale_persistence"] == 0.0
        and undefended["day_scale_persistence"] == -1.0,
        f"D {defended['day_scale_persistence']}, U "
        f"{undefended['day_scale_persistence']}"))
    out.append(_check(
        "the hand-computed B is +1.5 at the defended zone and -1.5 at the "
        "undefended zone",
        abs(defended["b"] - 1.5) < 1e-12 and abs(undefended["b"] + 1.5) < 1e-12,
        f"D {defended['b']}, U {undefended['b']}"))
    out.append(_check(
        "THE PLANTED RECOVERY: the zone-anchored barrier ranks the defended "
        "zone above the undefended zone",
        defended["b"] > undefended["b"],
        f"defended {defended['b']:.3f} vs undefended {undefended['b']:.3f}"))
    # The read may only see bars that closed before its own decision.
    out.append(_check(
        "each read's window stops strictly before its own decision bar",
        defended["window"] == world["defended_bar"]
        and undefended["window"] == world["undefended_bar"],
        f"D window {defended['window']} (bar {world['defended_bar']}), U window "
        f"{undefended['window']} (bar {world['undefended_bar']})"))
    # The lane-2 form: the same definition, evaluated at the episode close.
    close_bar = 20
    stamp = int(tape.ts[close_bar])
    scale = LZ.day_scale_terms(
        tape.mid, tape.ts, world["defended"], world["width"], stamp,
        zone_kind=world["defended_kind"],
        approach_side=int(world["approach_side"]), mode="close")
    out.append(_check(
        "the lane-2 day-scale form reads a traversal of BOTH sides as broken",
        scale["broke"] == 1.0 and scale["held"] == 1.0,
        f"held {scale['held']}, broke {scale['broke']} at the episode close "
        f"bar {close_bar}"))
    return out


def _selftest_center_gate_real() -> list[tuple[str, bool, str]]:
    """The centre gate on REAL rows: 50 formed candidates, echo equality.

    The draw is the accessor's own stratified draw over sweep 22's formed
    candidates, so this asserts the gate against the same bytes the run reads.
    """

    queries, meta, info = LZ.draw_queries(rows=50, seed=SEED)
    reader = LZ.reader(ASSETS)
    rows = reader.rows(queries)
    candidates = {(int(q.cell), float(q.zone_price), int(m["approach_bar"]))
                  for q, m in zip(queries, meta)}
    exact = sum(int(float(row.center_price) == float(query.zone_price))
                for row, query in zip(rows, queries))
    worst = max((abs(float(row.center_price) - float(query.zone_price))
                 for row, query in zip(rows, queries)), default=0.0)
    prior = sum(int(int(row.max_source_stamp) < int(row.decision_stamp_ns))
                for row in rows)
    out = [_check(
        "at least 50 real formed candidates are drawn",
        len(candidates) >= 50,
        f"{len(candidates)} candidates, {len(rows)} rows, from "
        f"{info['candidates']} formed over {info['strata']} strata")]
    out.append(_check(
        "every real row echoes centre_price == zone_price EXACTLY",
        exact == len(rows) and len(rows) > 0,
        f"{exact}/{len(rows)} exact, worst gap {worst} mid2"))
    out.append(_check(
        "every real row's source stamp is strictly before its decision",
        prior == len(rows) and len(rows) > 0, f"{prior}/{len(rows)}"))
    return out


def _selftest_selector_parity(mutant: str) -> list[tuple[str, bool, str]]:
    """This unit's fold law is the parent's: same matrix in, same rows out."""

    cands, payoff, days = S22._planted_selector()
    impulse = np.zeros(len(cands), np.float64)
    parent_raw = np.vstack([S22.barrier_components(cand, "L1_PRETOUCH")
                            for cand in cands])
    mine, _report = score_selector(cands, parent_raw, "L1_PRETOUCH", impulse,
                                   days, mutant)
    theirs, _parent_report = S22.score_selector(cands, "L1_PRETOUCH", impulse,
                                                days, mutant)
    same = (len(mine) == len(theirs)
            and all(a.position == b.position
                    and abs(a.b - b.b) < 1e-12
                    and abs(a.margin - b.margin) < 1e-12
                    and a.selected == b.selected
                    for a, b in zip(mine, theirs)))
    out = [_check(
        "the selector reproduces sweep 22's fold law exactly on the same "
        "barrier matrix",
        same, f"{len(mine)} rows here vs {len(theirs)} in the parent")]
    picked = [r.position for r in mine if r.selected[LIVE_CELL]]
    recovered = float(np.mean([payoff[p] for p in picked])) if picked else 0.0
    base = float(np.mean(payoff))
    out.append(_check(
        "the selector recovers the planted defended rows",
        len(picked) > 0 and recovered > base + 200.0,
        f"{len(picked)} picked, mean {recovered:.1f} vs base {base:.1f}"))
    return out


def _selftest_leak(mutant: str) -> list[tuple[str, bool, str]]:
    """The leak guard: a world where only the scoring day carries the signal."""

    cands, payoff, days = S22._planted_leak()
    impulse = np.zeros(len(cands), np.float64)
    raw = np.vstack([S22.barrier_components(cand, "L1_PRETOUCH")
                     for cand in cands])
    rows, _report = score_selector(cands, raw, "L1_PRETOUCH", impulse, days,
                                   mutant)
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
    seen: dict[str, int] = {}
    total = 0
    for bits in itertools.product((False, True), repeat=9):
        letter, clause, matching = classify(*bits)
        total += 1
        if clause not in CLAUSE_ORDER or CLAUSE_LETTER[clause] != letter:
            out.append(_check("the letter partition covers every outcome",
                              False, f"bad mapping at {bits}"))
            return out
        if not matching or clause != next(c for c in CLAUSE_ORDER
                                          if c in matching):
            out.append(_check("the letter partition covers every outcome",
                              False, f"precedence violated at {bits}"))
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
    mutant = arm_mutant(_mutant())
    results: list[tuple[str, bool, str]] = []
    results += _selftest_planted()
    results += _selftest_center_gate_real()
    results += _selftest_letters()
    results += _selftest_selector_parity(mutant)
    results += _selftest_leak(mutant)
    # The parent's fixture law, reused unchanged: formation, the raw-tick fill,
    # the chronological replay with occupancy and the cap, and the stresses.
    results += S22._selftest_formation()
    results += S22._selftest_fill()
    results += S22._selftest_replay()
    results += S22._selftest_stress()
    print(f"sweep 24 selftest  mutant={mutant or 'none'}")
    bad = 0
    for name, ok, detail in results:
        mark = "ok  " if ok else "FAIL"
        bad += int(not ok)
        print(f"  [{mark}] {name}" + (f"  ({detail})" if detail else ""))
    print(f"  {len(results) - bad}/{len(results)} checks passed")
    if mutant in MUTANTS:
        red = [name for name, ok, _d in results if not ok]
        print(f"  MUTANT {mutant}: {len(red)} check(s) red -> "
              f"{'the guard is load bearing' if red else 'THE GUARD IS NOT LOAD BEARING'}")
        for name in red:
            print(f"    red: {name}")
        return 0 if red else 1
    return 1 if bad else 0


# --------------------------------------------------------------------------
# The log and the entry point.
# --------------------------------------------------------------------------

_show = S22._show


def log_rows(report: Mapping[str, object]) -> list[dict[str, object]]:
    params = json.dumps({
        "lanes": list(LANES), "labels": list(LABELS),
        "read": "zone-anchored via levels_zone.read_zone at zone_price",
        "lane_day_scale_mode": dict(LANE_DAY_SCALE_MODE),
        "q_zone": S22.Q_ZONE, "outer_step": S22.OUTER_STEP,
        "q_depth": S22.Q_DEPTH, "q_epi": S22.Q_EPI, "q_cancel": S22.Q_CANCEL,
        "max_episode_bars": S22.MAX_EPISODE_BARS,
        "barrier_cuts": BARRIER_CUTS, "margin_cuts": MARGIN_CUTS,
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
                zone = report["zone_read"][lane]
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
                    f"{block['neighbours_agree']}; barrier read at the fixed "
                    f"zone price, {zone['center_exact']}/{zone['rows']} centres "
                    f"exact, worst gap {zone['worst_center_gap_mid2']} mid2; "
                    f"letter {letter}")
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
                f"{cut[0]} x margin cut {cut[1]}: n {cell['n']}; " + "; ".join(
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
            + f"; EXPLORATORY, hindsight bits "
              f"{len(report['ceiling'][scope]['hindsight_bits'])} "
              f"({'; '.join(report['ceiling'][scope]['hindsight_bits'])})")
        rows.append(line)

    # 5. the corrected-versus-refused barrier comparison, information only
    for lane in LANES:
        for asset in ASSETS:
            counter += 1
            cell = report["barrier_correlation"][lane][asset]
            line = blank(dict(shared))
            line["id"] = f"{LOG_PREFIX}-{counter:03d}"
            line["rule"] = f"{lane}/barrier-correlation/{asset}"
            line["days"] = len(report["scoring_days"]["NKD"])
            line["note"] = (
                f"INFORMATION, not a gate: zone-anchored B vs sweep 22's "
                f"miscentred B, {lane}, {asset} over "
                f"{cell['shared_candidates']} shared candidates: Spearman rho "
                f"on the raw component mean "
                f"{_show(cell['rho_raw_component_mean'])}, on the standardized "
                f"selector B {_show(cell['rho_selector_b'])}; selected here "
                f"{cell['selected_zone_anchored']}, selected by the refused "
                f"read {cell['selected_parent_miscentred']}, decisions flipped "
                f"{cell['selection_flips']} "
                f"({_show(cell['selection_flip_share'])})")
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
          f"({report['zone_read']['L1_PRETOUCH']['center_exact']} lane-1 and "
          f"{report['zone_read']['L2_EPISODE']['center_exact']} lane-2 rows "
          f"exact); EXPLORE-only, kill-only, no promotion")
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
    S22.print_gate(report)
    print_zone_read(report)
    S22.print_causality_rows(report)
    S22.print_formation(report)
    for lane in LANES:
        S22.print_lane(report, lane)
    S22.print_lane_extras(report, report["lane_extras"])
    S22.print_grid(report)
    S22.print_controls(report)
    print_c3_caveat(report)
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
