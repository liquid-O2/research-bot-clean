#!/usr/bin/env python3
"""Sweep 26 of the side-resolution mill: F21-SUBMINUTE-ORDER-ORACLE.

THE UNIT'S ONE REASON TO EXIST.  Sol's pinpoint page
(``.audit/briefs/mill-pinpoint-sol-out.md``, section D, "Lawful successor and
the bar for changing law") and the reconciliation page
(``.audit/briefs/mill-structbreak-sol-out.md``, section C, final paragraph)
register ONE receipt-level fact that would justify changing a USER-owned law:

    "An outcome-only raw-tick oracle must show on both NKD and SI that
    within-minute touch, absorption, and rejection order clears the rungs and
    MDD.  The same receipt must show that powered one-minute LEVELCOLLISION and
    STRUCTBREAK bounds are non-positive because those distinct orders collapse
    into the same bar."

That sentence is the GRAIN EVIDENCE BAR.  This unit is built to test it and
nothing else.  It measures within-minute atom ORDER at the formed zones, prices
each preregistered order class beside its MINUTE-COARSENED TWIN, and reports the
collapse rate that would explain any separation.

THIS UNIT CHANGES NO LAW.  The grain law stands.  Raw ticks are lawful here
because they PRICE and DESCRIBE outcomes - exactly as the frozen mill already
prices the -900 wall, the lane-1 limit fill of sweep 22 and the pullback fill of
sweep 23 - and because every ENTRY is taken at a lawful one-minute bar stamp
strictly after the class completes.  The sub-minute information is the
CONDITION; the entry is lawful-grain executable.  No policy is promoted from
this receipt, no verdict is written, no letter travels past this page.

EVENTS.  The union of the two formed universes, each reproduced through ITS OWN
formation pass with refuse-on-mismatch: ``sweep22.formation_pass`` (14,650 zone
approaches) and ``sweep23.formation_pass`` (3,790 breaks).  No universe is
re-implemented here; a drift in either count refuses the run.

Machinery is imported, never re-implemented.  Sweep 8 supplies the cells and
ATR14_prev, sweep 9 the row plane whose counters are the refuse-to-run gate,
sweep 14 the fold law and scoring days, sweep 22 the frozen entry, replay, MDD
and stress laws, sweep 23 the break universe, ``mill.py`` the frozen entry, fill
and outcome laws, ``flow.py`` the one-minute flow cache and ``event_pack.py``
the raw trade tape that carries the aggressor side.

Nothing here is executable.  EXPLORE only, kill-only tier, no packs, no HOLD, no
teacher labels, no 2021, no 2025H2, no commits, no freeze.
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

from engine.entry_v2.diagnostic_event_truth import native_book_quality  # noqa: E402
from engine.entry_v2.diagnostic_types import RAW_TICK  # noqa: E402
from engine.entry_v2.event_pack import EventPack  # noqa: E402

import mill as M  # noqa: E402
import flow as FLOW  # noqa: E402
import sweep1 as S1  # noqa: E402
import sweep8 as S8  # noqa: E402
import sweep9_twins as S9  # noqa: E402
import sweep12 as S12  # noqa: E402
import sweep14 as S14  # noqa: E402
import sweep19 as S19  # noqa: E402
import sweep22 as S22  # noqa: E402
import sweep23 as S23  # noqa: E402
import levels as LV  # noqa: E402

# --------------------------------------------------------------------------
# The law, registered before anything is read.
# --------------------------------------------------------------------------

SPEC = """QRE2MILLSWEEP26
tier=exploratory; EXPLORE-only, kill-only, EXPLORE nothing else.  Family
  F21-SUBMINUTE-ORDER-ORACLE.  Seed 20260827.  Parent trial sweep25-051.  NO
  COMMITS, NO FREEZE, no packs, no HOLD, no teacher labels, no 2021, no 2025H2.
THIS UNIT CHANGES NO LAW.  The one-minute grain law stands exactly as written.
  Raw ticks are lawful inside this unit because they PRICE and DESCRIBE
  outcomes: the frozen mill already walls off ticks for the -900 wall, sweep 22
  fills a resting limit on them and sweep 23 fills a pullback on them.  Every
  ENTRY here is taken at a one-minute bar stamp under the frozen entry law,
  strictly after the class completes.  Sub-minute order is the CONDITION only.
  No policy, threshold or selector is promoted from this receipt, and the
  verdict column stays empty.
GATE.  Sweep 9's row plane (47402 rows; certifiable HG 138 / NKD 132 / SI 132;
  candidates_seen 313131; cells_with_rows 385) and sweep 14's scoring days
  (41/40/39) reproduce before anything is formed.  The level cache manifest must
  carry schema QRE2MILLLEVELSMANIFEST1 against this split with a strictly-prior
  join.  A miss on either refuses the run.
EVENTS.  The union of the two formed universes, each reproduced through its own
  formation pass: sweep22.formation_pass must return EXACTLY 14650 zone
  approaches and sweep23.formation_pass EXACTLY 3790 breaks, or the run refuses.
  Neither universe is re-implemented, re-parameterized or re-fitted here.
DEDUPE, and the one registered deviation on this page.  The instruction is to
  "dedupe OVERLAPS by (asset, day, phase, level, kind)" while reproducing the
  two universes at EXACTLY 14650 and 3790 under refuse-on-mismatch.  Applied
  literally to the whole union, that key is not a dedupe of overlaps: because
  sweep 22 forms one candidate per RE-ARMED approach to a zone, the key collapses
  every later approach to a zone that was already approached that session and
  deletes about 84 percent of the approach universe the same sentence orders
  reproduced.  Reading ``kind`` as the ZONE kind deletes more still.  A key that
  destroys the universe it was told to reproduce cannot be the intended one, and
  the power it destroys is the power Sol's bar is measured with.
  PRIMARY, registered here before pricing: each parent universe keeps ITS OWN
  identity, exactly as reproduced, and the key removes only CROSS-UNIVERSE
  overlaps - a BREAK row is dropped when an APPROACH row at the same
  (asset, day, phase, level) has a window that overlaps it in time, because
  those two rows describe one episode at one price.  That is literally an
  overlap dedupe and it preserves 14650 + 3790.
  SENSITIVITY, priced identically and reported beside every primary number: the
  LITERAL whole-union key (asset, day, phase, level, event kind), first row per
  key in (universe, bar) order.  The family letter is reported under BOTH and a
  disagreement between them is reported as a disagreement, not resolved.
  A third count - what a zone-kind reading of ``kind`` would have dropped - is
  reported as a diagnostic only.
EVENT WINDOW.  APPROACH: from the approach bar's lattice stamp to its
  resolution - the lane-2 episode close where sweep 22 resolved one, else the
  end of the parent's own MAX_EPISODE_BARS = 90 bar horizon, clipped to the
  cell.  BREAK: from the breach close to the parent's own fold-trained cancel
  bar.  No window parameter is invented here; both come from the parent runs.
FLOW SCALE, train-day adaptive, no constants.  For each (asset, day) the day
  flow scale is the median over that day's one-minute bars of |delta| from the
  flow cache.  For a scoring day d the ABSORB scale is the MEDIAN of the day
  flow scales over that asset's STRICTLY PRIOR EXPLORE days.  The absorption
  threshold is ABSORB_Q = 1.0 times that scale: one prior-typical minute of
  net aggressor volume, arriving inside the band.  ABSORB_Q is a registered
  unit share, not a fitted quantile; the SCALE it multiplies is trained.
  A day with no prior day forms no event under the parent passes, so every
  event carries a trained scale.
ATOMS, from raw tick suffixes inside the event window.  Probe side s is the
  approach side for an APPROACH and the break direction for a BREAK.  The band
  is [zone - w, zone + w] at the candidate's own zone price and zone half width.
  region(x) = 0 inside the band, +1 beyond the far edge (s side), -1 beyond the
  near edge.  Scanning the window's trusted mid ticks in order:
    TOUCH   the first tick of an inside run (region 0).
    ABSORB  inside an inside run, cumulative s-signed aggressor volume of the
            trades PRINTED INSIDE THE BAND during that run first reaches the
            absorption threshold.  Aggressor side is the event pack's own B/A
            aggressor byte, the decoding ``build_flow.py`` censused.  The
            accumulator resets when price leaves the band, because absorption is
            a fact about one visit, not about a day.
    REJECT  the first tick of a run at region -1: price left the band against
            the probe side.
    BREACH  the first tick of a run at region +1: price traded through the far
            edge.
  The atom order is the ordered atom names with their tick stamps.  A completed
  cycle is TOUCH then ABSORB then REJECT in that order inside one window; the
  cycle count is reported per event.
SEEDING, registered because it is a law and not an implementation detail.  The
  window's opening state SEEDS the scanner and is not itself a transition.  It
  emits TOUCH when the window opens inside the band (price is already at the
  zone) and BREACH when it opens beyond the far edge - for a BREAK event that
  opening IS the formation breach the window is defined on, so P5 can see it.
  An opening at the near side emits nothing: that is where an approach begins by
  construction.  The twin seeds identically on its own clock, with the added
  minute reading that a bar whose RANGE crosses the band touches it even when it
  closes outside.
MINUTE SIGNATURE and the COLLAPSE FLAG.  The minute signature of an event is
  what a one-minute selector standing at that zone can see over the same span:
  the span length in bars and, per bar, (region(open), region(high),
  region(low), region(close)) in probe-side coordinates together with the
  bar's flow bucket sign(s * delta) bucketed at the same trained absorption
  scale into {-1, 0, +1}.  Two events are MINUTE-COLLAPSED when their minute
  signatures are identical and their atom orders differ.  The collapse rate of a
  class is the share of its events whose signature group contains at least one
  event with a different atom order; it is reported per class and per asset.
  Exact per-tick identity is not the test and never fires on real tape; the
  question Sol asks is whether the MINUTE PICTURE separates the orders.
PATTERN CLASSES, preregistered, exactly these five, NO ADDITIONS AFTER SEEING
  RESULTS.
  P1 ABSORB_THEN_REJECT   a completed TOUCH-ABSORB-REJECT cycle whose REJECT
                          lands within 60 s of that cycle's first touch.
  P2 REJECT_NO_ABSORB     a REJECT with no ABSORB earlier in its own inside run.
  P3 ABSORB_THEN_BREACH   a BREACH with an ABSORB earlier in its own inside run:
                          absorption failed, the trapped-cohort atom.
  P4 MULTI_CYCLE          two or more completed TOUCH-ABSORB-REJECT cycles.
  P5 BREACH_RETURN        price returns inside the band within 60 s of a BREACH.
  PRECEDENCE, fixed here before any result: P4, P3, P5, P1, P2.  Multi-cycle
  dominates a single cycle; a failed absorption dominates a later fake-break
  read of the same tape; a break-and-return dominates a plain single cycle; P2
  is the residual rejection with no flow fact.  An event matching none is
  UNCLASSED.  Each event carries at most one class.
ENTRY, executable, lawful grain.  Let k be the lattice bar CONTAINING the class
  completion stamp.  The entry bar is k + 1 - the NEXT one-minute bar's stamp
  after the class completes - priced by the frozen entry law
  (``S22.price_bar_entry``: last trusted quote strictly before lat[k+1], bar_ok
  and side legality enforced).  The entry stamp is therefore strictly after both
  the completion stamp and the close of the bar that contained it.
SIDES, from the class, never from the outcome.  P1 and P4 fade with the defence,
  side -s.  P3 takes the break direction, side +s.  P5 takes the back-inside
  direction, side -s.  P2 implies NO side: it is priced BOTH ways and its class
  line is the EQUAL-WEIGHT AVERAGE of the two, which is what a sideless
  condition is worth; both sides are reported beside it with the hindsight bit
  "which side" named.
MINUTE-COARSENED TWIN, the decisive comparison, defined HERE before any pricing.
  Over the same window bars, using ONLY one-minute bars and one-minute flow
  aggregates:
    mTOUCH  the first bar whose [low, high] intersects the band.
    mABSORB inside a run of bars whose CLOSE is in the band, cumulative
            s * delta first reaches the same trained absorption threshold.
    mREJECT the first bar whose CLOSE is at region -1.
    mBREACH the first bar whose CLOSE is at region +1.
  The same atom machinery, the same five class definitions and the same
  precedence run on the minute atom order, with "within 60 s" read as "within
  one bar".  The twin entry is the completion BAR plus one, the twin side rule
  is the class's own, and the twin is priced by the identical law.
PRICING.  The frozen outcome law - the -900 wall or the phase close, whichever
  comes first - is PRIMARY and carries the letters.  The 1800 s fixed hold is
  reported BESIDE every line, the same law with the phase close replaced by
  min(entry + 1800 s, phase close).  Every entry, class and twin, goes through
  ``S22.price_bar_entry`` and therefore through ``MillIndex.outcome``.
REPLAY.  Sweep 22's, imported: exact chronological replay, exits before entries
  at an equal stamp, one open position per asset, at most 12 seated entries per
  PORTFOLIO date, every split date carried including zero-entry dates.
MDD.  Sweep 22's four ledgers, imported: per-asset trade and day, portfolio
  trade and day, and event-time portfolio equity marked at the causal raw mid.
  Binding is the deciding assets' ledgers plus every portfolio ledger.
STRESSES.  Sweep 22's, imported: the 2 percent adversarial stress (the worst 2
  percent of seated entries per asset take their own MAE as realized) and the
  doubled-spread stress.  Both re-run the replay so occupancy follows.
REPORTED per class per asset, for BOTH the sub-minute class and its minute twin:
  n, coverage, usd per asset-day, over-rung ratio, mean minus 2SE, MDD, plus the
  collapse rate and the SEPARATION COUNT - the size of the symmetric difference
  between the tick class's event set and the twin class's event set.
DECISION LETTERS, preregistered, exhaustive, proved over constructed receipts.
  ORDER-RICH   some class clears BOTH deciding rungs (NKD and SI above 1500 USD
               per asset-day at the point estimate AND at mean minus 2SE) with
               every binding MDD below 1000 under the seat replay and both
               stresses, WHILE that class's minute twin has a non-positive upper
               95 percent bound on both deciders AND the collapse rate is
               reported and explains the separation.  This is the receipt that
               meets Sol's grain bar.
  ORDER-PRESENT a class clears the rungs at the point estimate but fails a
               bound, or clears one decider only.
  ORDER-POOR   no class reaches half of either deciding rung at the point
               estimate.  This KILLS the grain lever per Sol's bar and the next
               session's units stay at one-minute formation and power.
  UNPOWERED    the richest class has fewer than 30 entries on every deciding
               asset.
  The clauses are tested in the order UNPOWERED, ORDER-RICH, ORDER-PRESENT,
  ORDER-POOR and the partition is proved exhaustive in the selftest.  The family
  letter is the best class's letter under the order
  ORDER-RICH > ORDER-PRESENT > ORDER-POOR > UNPOWERED.
MUTANTS, each red by NAMED roster.
  QRE2_MILL_S26_MUTANT=atoms_use_minute_bars infers the atom order from minute
    OHLCV instead of raw ticks.  It must red the planted-sequence check and the
    planted-collapse checks.
  QRE2_MILL_S26_MUTANT=entry_precedes_completion enters at the class's OWN
    minute instead of the next one.  It must red the executable-entry check.
"""

ASSETS = S22.ASSETS
DECIDING = S22.DECIDING
REPORT_ONLY = S22.REPORT_ONLY
SEED = 20260827
NANOS = S22.NANOS

FAMILY = "F21-SUBMINUTE-ORACLE"
PARENT_TRIAL = "sweep25-051"
SELECTION_RULE = ("none: five preregistered within-minute order classes, one "
                  "trained flow scale, executable next-bar entries, no "
                  "selector and no model search")

LOG_PREFIX = "sweep26"
OUT_PATH = ROOT / ".audit/mill-sweep26.json"
LOG_PATH = S1.LOG_PATH

EXPECT_APPROACHES = 14_650
EXPECT_BREAKS = 3_790

CLOSE = S22.CLOSE
FIXED = S22.FIXED
LABELS = S22.LABELS
DAY_RUNG_USD = S22.DAY_RUNG_USD
MDD_CEILING = S22.MDD_CEILING
PORTFOLIO_CAP = S22.PORTFOLIO_CAP
MIN_PRIOR_DAYS = S22.MIN_PRIOR_DAYS
MAX_EPISODE_BARS = S22.MAX_EPISODE_BARS

# This unit's own constants, every one named and fixed before the run.
ABSORB_Q = 1.0               # unit share of the TRAINED prior-day flow scale
WITHIN_NS = 60 * NANOS       # "within one minute", in nanoseconds
WITHIN_BARS = 1              # the twin's reading of "within one minute"
MIN_CLASS_N = 30             # the UNPOWERED bound, per deciding asset
HALF_RUNG = 0.5              # the ORDER-POOR bound, share of a deciding rung
FLOW_BUCKET_Q = 1.0          # the twin signature's flow bucket, same scale

TOUCH, ABSORB, REJECT, BREACH = "TOUCH", "ABSORB", "REJECT", "BREACH"
ATOMS = (TOUCH, ABSORB, REJECT, BREACH)

P1 = "P1_ABSORB_THEN_REJECT"
P2 = "P2_REJECT_NO_ABSORB"
P3 = "P3_ABSORB_THEN_BREACH"
P4 = "P4_MULTI_CYCLE"
P5 = "P5_BREACH_RETURN"
CLASSES = (P1, P2, P3, P4, P5)
PRECEDENCE = (P4, P3, P5, P1, P2)
UNCLASSED = "UNCLASSED"
CLASS_NAME = {
    P1: "absorb-then-reject completed within one minute of first touch",
    P2: "reject without the flow fact (no implied side, priced both ways)",
    P3: "absorb-then-breach, the trapped-cohort atom",
    P4: "two or more completed touch-absorb-reject cycles",
    P5: "breach then return inside within one minute, the fake-break atom"}
# Side implied by the class, in probe-side units.  0 means no implied side.
CLASS_SIDE = {P1: -1, P2: 0, P3: +1, P4: -1, P5: -1}

LETTER_RICH = "ORDER-RICH"
LETTER_PRESENT = "ORDER-PRESENT"
LETTER_POOR = "ORDER-POOR"
LETTER_UNPOWERED = "UNPOWERED"
LETTER_RANK = {LETTER_RICH: 3, LETTER_PRESENT: 2, LETTER_POOR: 1,
               LETTER_UNPOWERED: 0}
CLAUSE_ORDER = ("UNPOWERED", "RICH", "PRESENT", "POOR")
CLAUSES = {
    "UNPOWERED": ("fewer than 30 entries on every deciding asset"),
    "RICH": ("both deciding rungs at point AND mean-2SE, every binding MDD "
             "below 1000 under replay and both stresses, twin upper 95 bound "
             "non-positive on both deciders, collapse rate reported"),
    "PRESENT": ("rungs at the point estimate with a failed bound, or one "
                "decider only"),
    "POOR": ("no class reaches half of either deciding rung at point")}

HINDSIGHT_P2 = ("which side: P2 implies none, so the class line is the "
                "equal-weight average of the two sides and each side is "
                "reported beside it as an oracle bit, never as a policy")

MUTANT_ENV = "QRE2_MILL_S26_MUTANT"
MUTANT_MINUTE_ATOMS = "atoms_use_minute_bars"
MUTANT_EARLY_ENTRY = "entry_precedes_completion"
MUTANTS = (MUTANT_MINUTE_ATOMS, MUTANT_EARLY_ENTRY)
EXPECTED_RED = {
    MUTANT_MINUTE_ATOMS: ("planted_atom_sequence", "planted_atom_order",
                          "planted_cycle_count", "planted_class",
                          "collapse_pair_different_atom_order",
                          "collapse_pair_fires", "separable_pair_silent"),
    MUTANT_EARLY_ENTRY: ("entry_after_completion", "entry_after_bar_close")}

APPROACH = "APPROACH"
BREAK = "BREAK"
KINDS = (APPROACH, BREAK)


class SweepRefusal(RuntimeError):
    pass


SPEC_SHA = S1._sha_text(SPEC)


def code_sha() -> str:
    return S1._sha_text(Path(__file__).read_text())


def _mutant() -> str:
    value = os.environ.get(MUTANT_ENV, "").strip()
    if value and value not in MUTANTS:
        raise SweepRefusal(f"unknown mutant {value!r}; roster {MUTANTS}")
    return value


_pct = S22._pct
_mean_se = S22._mean_se
_wilson = S22._wilson
_drawdown = S22._drawdown


def _show(value: object) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.4g}"
    return str(value)


def _n(value: object, width: int = 9, digits: int = 3) -> str:
    if value is None:
        return "n/a".rjust(width)
    if isinstance(value, bool):
        return ("yes" if value else "no").rjust(width)
    if isinstance(value, float):
        if not math.isfinite(value):
            return "n/a".rjust(width)
        return f"{value:,.{digits}f}".rjust(width)
    return str(value).rjust(width)


# --------------------------------------------------------------------------
# The event union.  Two parent universes, reproduced, never re-implemented.
# --------------------------------------------------------------------------

@dataclass(slots=True)
class Event:
    kind: str                  # APPROACH or BREAK
    source: int                # index inside its own parent universe
    asset: str
    d8: int
    phase: str
    cell: int
    year: int
    zone_kind: str
    zone_price: float
    width: float               # zone HALF width, in mid2
    probe_side: int            # approach side, or break direction
    bar0: int                  # the window's first lattice bar
    bar1: int                  # the window's last lattice bar, inclusive
    n_bars: int
    # filled by the tick pass
    scale: float = 0.0
    atoms: tuple = ()          # ((name, stamp_ns), ...)
    order: str = ""
    cycles: int = 0
    klass: str = UNCLASSED
    done_ts: int = -1
    entry_bar: int = -1
    signature: str = ""
    # filled by the twin pass
    twin_atoms: tuple = ()
    twin_order: str = ""
    twin_cycles: int = 0
    twin_class: str = UNCLASSED
    twin_done_bar: int = -1
    twin_entry_bar: int = -1
    collapsed: bool = False
    # the two dedupe readings; both are carried so both letters can be priced
    overlap_dropped: bool = False     # PRIMARY: a break inside an approach
    literal_dropped: bool = False     # SENSITIVITY: the literal whole-union key


def _window_approach(cand: S22.Cand) -> tuple[int, int]:
    """Approach bar to resolution, entirely from the parent's own geometry."""

    stop = min(int(cand.n_bars) - 1, int(cand.bar) + MAX_EPISODE_BARS)
    end = int(cand.close_bar) if int(cand.close_bar) >= 0 else stop
    return int(cand.bar), int(max(int(cand.bar), min(end, stop)))


def _window_break(cand: S23.Cand) -> tuple[int, int]:
    """Breach close to the parent's own fold-trained cancel bar."""

    end = int(max(int(cand.bar), int(cand.cancel_bar)))
    return int(cand.bar), int(min(end, int(cand.n_bars) - 1))


def build_events(approaches: Sequence[S22.Cand], breaks: Sequence[S23.Cand]
                 ) -> tuple[list[Event], dict[str, object]]:
    """The union of the two universes under the registered dedupe key."""

    rows: list[Event] = []
    for position, cand in enumerate(approaches):
        bar0, bar1 = _window_approach(cand)
        rows.append(Event(
            kind=APPROACH, source=int(position), asset=cand.asset,
            d8=int(cand.d8), phase=cand.phase, cell=int(cand.cell),
            year=int(cand.year), zone_kind=cand.zone_kind,
            zone_price=float(cand.zone_price), width=float(cand.width),
            probe_side=int(cand.approach_side), bar0=bar0, bar1=bar1,
            n_bars=int(cand.n_bars)))
    for position, cand in enumerate(breaks):
        bar0, bar1 = _window_break(cand)
        rows.append(Event(
            kind=BREAK, source=int(position), asset=cand.asset,
            d8=int(cand.d8), phase=cand.phase, cell=int(cand.cell),
            year=int(cand.year), zone_kind=cand.zone_kind,
            zone_price=float(cand.zone_price), width=float(cand.width),
            probe_side=int(cand.break_dir), bar0=bar0, bar1=bar1,
            n_bars=int(cand.n_bars)))

    # ---- PRIMARY: remove cross-universe overlaps only ---------------------
    spans: dict[tuple, list[tuple[int, int]]] = {}
    for row in rows:
        if row.kind != APPROACH:
            continue
        spans.setdefault(
            (row.asset, row.d8, row.phase, int(round(row.zone_price))),
            []).append((row.bar0, row.bar1))
    overlap_dropped = 0
    for row in rows:
        if row.kind != BREAK:
            continue
        key = (row.asset, row.d8, row.phase, int(round(row.zone_price)))
        for bar0, bar1 in spans.get(key, ()):
            if row.bar0 <= bar1 and bar0 <= row.bar1:
                row.overlap_dropped = True
                overlap_dropped += 1
                break

    # ---- SENSITIVITY: the literal whole-union key -------------------------
    seen: set[tuple] = set()
    zone_kind_seen: set[tuple] = set()
    zone_kind_dropped = 0
    literal = {APPROACH: 0, BREAK: 0}
    for row in rows:
        level = int(round(row.zone_price))
        alt = (row.asset, row.d8, row.phase, level, row.zone_kind)
        if alt in zone_kind_seen:
            zone_kind_dropped += 1
        zone_kind_seen.add(alt)
        key = (row.asset, row.d8, row.phase, level, row.kind)
        if key in seen:
            row.literal_dropped = True
            literal[row.kind] += 1
            continue
        seen.add(key)

    primary = [r for r in rows if not r.overlap_dropped]
    sensitivity = [r for r in rows if not r.literal_dropped]
    counters = {
        "approaches_in": len(approaches), "breaks_in": len(breaks),
        "union_in": len(rows),
        "primary_key": ("cross-universe overlaps only: a BREAK dropped when an "
                        "APPROACH at the same (asset, day, phase, level) has a "
                        "time-overlapping window"),
        "primary_out": len(primary),
        "primary_overlap_dropped": int(overlap_dropped),
        "literal_key": "(asset, day, phase, level_mid2, event_kind)",
        "literal_out": len(sensitivity),
        "literal_dropped_approach": literal[APPROACH],
        "literal_dropped_break": literal[BREAK],
        "zone_kind_reading_would_drop": int(zone_kind_dropped),
        "zone_kind_reading_note": (
            "diagnostic only: reading 'kind' as the ZONE kind would collapse "
            "an approach and a break at one price into one row and delete one "
            "of the two named universes"),
        "by_kind": {kind: sum(1 for r in primary if r.kind == kind)
                    for kind in KINDS},
        "by_asset": {asset: sum(1 for r in primary if r.asset == asset)
                     for asset in ASSETS},
        "literal_by_asset": {
            asset: sum(1 for r in sensitivity if r.asset == asset)
            for asset in ASSETS}}
    return rows, counters


# --------------------------------------------------------------------------
# The trained flow scale.  One number per (asset, scoring day), no constant.
# --------------------------------------------------------------------------

def day_flow_scales(explore_days: Mapping[str, Sequence[int]]
                    ) -> tuple[dict[tuple[str, int], float], dict[str, int]]:
    """Median |delta| over a day's one-minute bars, per (asset, day)."""

    out: dict[tuple[str, int], float] = {}
    counters = {"days": 0, "missing": 0, "empty": 0}
    for asset in ASSETS:
        for d8 in sorted(int(day) for day in explore_days[asset]):
            counters["days"] += 1
            try:
                day = FLOW.load_flow(asset, int(d8))
            except FLOW.FlowStop:
                counters["missing"] += 1
                continue
            pool = np.concatenate(
                [np.abs(np.asarray(arrays["delta"], np.float64))
                 for arrays in day.values()]) if day else np.zeros(0)
            if not len(pool):
                counters["empty"] += 1
                continue
            out[(asset, int(d8))] = float(np.median(pool))
    return out, counters


def absorb_scales(scales: Mapping[tuple[str, int], float],
                  explore_days: Mapping[str, Sequence[int]]
                  ) -> dict[tuple[str, int], float]:
    """The trained scale for a scoring day: median over STRICTLY PRIOR days."""

    out: dict[tuple[str, int], float] = {}
    for asset in ASSETS:
        days = sorted(int(day) for day in explore_days[asset])
        for index, d8 in enumerate(days):
            prior = [scales[(asset, d)] for d in days[:index]
                     if (asset, d) in scales]
            if not prior:
                continue
            out[(asset, int(d8))] = float(np.median(prior))
    return out


# --------------------------------------------------------------------------
# The raw trade tape.  Aggressor side comes from the event pack's own byte.
# --------------------------------------------------------------------------

@dataclass(slots=True)
class Tape:
    ts: np.ndarray             # int64, trade receive stamps, sorted
    price2: np.ndarray         # int64, doubled trade price, mid2 coordinates
    signed: np.ndarray         # int64, +size for a buy aggressor, -size a sell


EMPTY_TAPE = Tape(np.zeros(0, np.int64), np.zeros(0, np.int64),
                  np.zeros(0, np.int64))


def load_tape(asset: str, d8: int) -> tuple[Tape, dict[str, int]]:
    """Trusted trades for one EXPLORE day, with ``build_flow.py``'s decoding.

    ``B`` is the buy aggressor lifting the offer, ``A`` the sell aggressor
    hitting the bid - the census ``build_flow.py`` records in its docstring.  The
    trusted-message filter, the tick-multiple price test and the positive-size
    test are that builder's, so this tape is the same tape its minute delta is
    summed from, read at full resolution.
    """

    path = (ROOT / "artifacts/cache/port/entry_v2/events" / asset
            / f"{int(d8)}.qre2")
    if not path.is_file():
        return EMPTY_TAPE, {"missing_pack": 1, "rows": 0, "trades": 0}
    pack = EventPack(path)
    rows = pack.rows
    tick = int(RAW_TICK[asset])
    sane = ((rows["bid_px"] > 0) & (rows["ask_px"] > rows["bid_px"])
            & ((rows["ask_px"].astype(np.int64)
                - rows["bid_px"].astype(np.int64)) % tick == 0))
    quality = native_book_quality(rows["ts_recv_ns"], rows["flags"], sane)
    message = np.asarray(quality.trusted_message, bool)
    price = rows["price"].astype(np.int64)
    size = rows["size"].astype(np.int64)
    keep = ((rows["action"] == ord("T")) & message & (price > 0)
            & (price % tick == 0) & (size > 0))
    index = np.flatnonzero(keep)
    side = rows["side"][index]
    signed = np.where(side == ord("B"), size[index],
                      np.where(side == ord("A"), -size[index], 0))
    tape = Tape(ts=rows["ts_recv_ns"][index].astype(np.int64),
                price2=2 * price[index],
                signed=signed.astype(np.int64))
    counters = {"missing_pack": 0, "rows": int(len(rows)),
                "trades": int(len(index))}
    del rows
    return tape, counters


# --------------------------------------------------------------------------
# The atoms.  Raw ticks for the oracle, minute bars for the twin.
# --------------------------------------------------------------------------

def _regions(values: np.ndarray, zone: float, width: float, side: int
             ) -> np.ndarray:
    """0 inside the band, +1 beyond the far edge, -1 beyond the near edge."""

    offset = (np.asarray(values, np.float64) - float(zone)) * float(side)
    return np.where(offset > float(width), 1,
                    np.where(offset < -float(width), -1, 0)).astype(np.int64)


def tick_atoms(mid_ts: np.ndarray, mid2: np.ndarray, tape: Tape, zone: float,
               width: float, side: int, threshold: float
               ) -> tuple[tuple, int]:
    """The ordered atoms of one event window, from raw ticks.

    ``mid_ts``/``mid2`` are the window's trusted mid ticks in order; ``tape`` is
    the window's trades.  Returns the atom tuple and the completed cycle count.
    """

    if not len(mid_ts):
        return (), 0
    region = _regions(mid2, zone, width, side)
    atoms: list[tuple[str, int]] = []
    cycles = 0
    run_touch = False
    run_absorb = False
    cum = 0.0
    previous = None
    trade_cursor = 0
    n_trades = len(tape.ts)
    lo = float(zone) - float(width)
    hi = float(zone) + float(width)
    for position in range(len(mid_ts)):
        state = int(region[position])
        stamp = int(mid_ts[position])
        if state == 0 and not run_touch:
            atoms.append((TOUCH, stamp))
            run_touch = True
            run_absorb = False
            cum = 0.0
            # Trades printed before this tick belong to the run that ended.
            trade_cursor = int(np.searchsorted(tape.ts, stamp, side="left"))
        if state != 0:
            if state != previous or run_touch:
                if state < 0:
                    # The seed does not emit REJECT: the near side is where an
                    # approach begins by construction, not an event.
                    if previous is not None:
                        atoms.append((REJECT, stamp))
                        if run_touch and run_absorb:
                            cycles += 1
                else:
                    atoms.append((BREACH, stamp))
                run_touch = False
                run_absorb = False
                cum = 0.0
            previous = state
            continue
        previous = state
        if run_absorb or not n_trades:
            continue
        # Inside the band: accumulate the trades printed INSIDE the band since
        # the run began, up to and including this tick's stamp.
        stop = int(np.searchsorted(tape.ts, stamp, side="right"))
        if stop > trade_cursor:
            chunk = slice(trade_cursor, stop)
            inside = ((tape.price2[chunk] >= lo) & (tape.price2[chunk] <= hi))
            cum += float(np.asarray(tape.signed[chunk], np.float64)[inside].sum())
            trade_cursor = stop
        if float(side) * cum >= float(threshold) and threshold > 0.0:
            atoms.append((ABSORB, stamp))
            run_absorb = True
    return tuple(atoms), int(cycles)


def minute_atoms(opens: np.ndarray, highs: np.ndarray, lows: np.ndarray,
                 closes: np.ndarray, deltas: np.ndarray, bars: np.ndarray,
                 zone: float, width: float, side: int, threshold: float
                 ) -> tuple[tuple, int]:
    """The twin's atoms: one-minute bars and one-minute flow only."""

    if not len(bars):
        return (), 0
    lo = float(zone) - float(width)
    hi = float(zone) + float(width)
    region = _regions(closes, zone, width, side)
    atoms: list[tuple[str, int]] = []
    cycles = 0
    run_touch = False
    run_absorb = False
    cum = 0.0
    previous = None
    for position in range(len(bars)):
        bar = int(bars[position])
        state = int(region[position])
        # A bar whose RANGE crosses the band touches it even if it closes out:
        # that is exactly what a one-minute selector can see of a visit.
        crosses = (float(lows[position]) <= hi and float(highs[position]) >= lo)
        if (state == 0 or crosses) and not run_touch:
            atoms.append((TOUCH, bar))
            run_touch, run_absorb, cum = True, False, 0.0
        if state != 0:
            if state != previous or run_touch:
                if state < 0:
                    if previous is not None:
                        atoms.append((REJECT, bar))
                        if run_touch and run_absorb:
                            cycles += 1
                else:
                    atoms.append((BREACH, bar))
                run_touch, run_absorb, cum = False, False, 0.0
            previous = state
            continue
        previous = state
        if run_absorb:
            continue
        cum += float(side) * float(deltas[position])
        if cum >= float(threshold) and threshold > 0.0:
            atoms.append((ABSORB, bar))
            run_absorb = True
    return tuple(atoms), int(cycles)


def classify_atoms(atoms: Sequence[tuple], cycles: int, within: float
                   ) -> tuple[str, int]:
    """The five preregistered classes, in the registered precedence order.

    ``within`` is 60e9 ns for the tick oracle and 1 bar for the twin; the two
    readings of "within one minute" are the same predicate on the two clocks.
    Returns (class, completion stamp-or-bar); UNCLASSED carries -1.
    """

    names = [name for name, _ in atoms]
    marks = [int(mark) for _, mark in atoms]

    # ---- P4: the REJECT that completes the SECOND cycle -------------------
    completed: list[int] = []
    touched = absorbed = False
    touch_at = -1
    for name, mark in atoms:
        if name == TOUCH:
            touched, absorbed, touch_at = True, False, int(mark)
        elif name == ABSORB and touched:
            absorbed = True
        elif name == REJECT:
            if touched and absorbed:
                completed.append(int(mark))
            touched = absorbed = False
        elif name == BREACH:
            touched = absorbed = False
    if int(cycles) >= 2 and len(completed) >= 2:
        return P4, int(completed[1])

    # ---- P3: a BREACH with an ABSORB earlier in its own inside run --------
    absorbed = False
    for name, mark in atoms:
        if name == TOUCH:
            absorbed = False
        elif name == ABSORB:
            absorbed = True
        elif name == REJECT:
            absorbed = False
        elif name == BREACH and absorbed:
            return P3, int(mark)

    # ---- P5: back inside the band within one minute of a BREACH ----------
    for position, (name, mark) in enumerate(atoms):
        if name != BREACH:
            continue
        for later, mark2 in zip(names[position + 1:], marks[position + 1:]):
            if later == TOUCH:
                if float(mark2) - float(mark) <= float(within):
                    return P5, int(mark2)
                break
            if later in (REJECT, BREACH):
                break

    # ---- P1: one completed cycle, REJECT within one minute of its touch ---
    touched = absorbed = False
    touch_at = -1
    for name, mark in atoms:
        if name == TOUCH:
            touched, absorbed, touch_at = True, False, int(mark)
        elif name == ABSORB and touched:
            absorbed = True
        elif name == REJECT:
            if (touched and absorbed
                    and float(mark) - float(touch_at) <= float(within)):
                return P1, int(mark)
            touched = absorbed = False
        elif name == BREACH:
            touched = absorbed = False

    # ---- P2: a REJECT with no ABSORB earlier in its own inside run --------
    absorbed = False
    for name, mark in atoms:
        if name == TOUCH:
            absorbed = False
        elif name == ABSORB:
            absorbed = True
        elif name == BREACH:
            absorbed = False
        elif name == REJECT and not absorbed:
            return P2, int(mark)

    return UNCLASSED, -1


def order_text(atoms: Sequence[tuple]) -> str:
    return ",".join(name for name, _ in atoms)


def minute_signature(regions_o: np.ndarray, regions_h: np.ndarray,
                     regions_l: np.ndarray, regions_c: np.ndarray,
                     buckets: np.ndarray) -> str:
    """What a one-minute selector standing at this zone can see."""

    pieces = [str(len(regions_c))]
    for index in range(len(regions_c)):
        pieces.append(f"{int(regions_o[index])}{int(regions_h[index])}"
                      f"{int(regions_l[index])}{int(regions_c[index])}"
                      f"{int(buckets[index])}")
    return "|".join(pieces)


def collapse_flags(events: Sequence[Event]) -> dict[str, object]:
    """Two events are minute-collapsed when the minute picture is the same
    and the tick atom order is not."""

    groups: dict[str, list[int]] = {}
    for position, event in enumerate(events):
        event.collapsed = False
        if not event.signature:
            continue
        groups.setdefault(f"{event.asset}#{event.signature}", []).append(position)
    collapsed = 0
    for members in groups.values():
        orders = {events[p].order for p in members}
        if len(orders) <= 1:
            continue
        for p in members:
            events[p].collapsed = True
            collapsed += 1
    scored = [e for e in events if e.signature]
    return {
        "signature_groups": len(groups),
        "events_with_signature": len(scored),
        "groups_with_mixed_orders": int(sum(
            1 for members in groups.values()
            if len({events[p].order for p in members}) > 1)),
        "collapsed_events": int(collapsed),
        "collapse_rate": (float(collapsed / len(scored)) if scored else None),
        "by_asset": {
            asset: (float(np.mean([1.0 if e.collapsed else 0.0
                                   for e in scored if e.asset == asset]))
                    if any(e.asset == asset for e in scored) else None)
            for asset in ASSETS},
        "by_class": {
            klass: (float(np.mean([1.0 if e.collapsed else 0.0
                                   for e in scored if e.klass == klass]))
                    if any(e.klass == klass for e in scored) else None)
            for klass in CLASSES},
        "by_class_asset": {
            f"{klass}|{asset}": (
                float(np.mean([1.0 if e.collapsed else 0.0 for e in scored
                               if e.klass == klass and e.asset == asset]))
                if any(e.klass == klass and e.asset == asset for e in scored)
                else None)
            for klass in CLASSES for asset in ASSETS}}


# --------------------------------------------------------------------------
# The one shard pass: atoms, twins and every priced entry.
# --------------------------------------------------------------------------

def _bar_arrays(asset: str, d8: int, cell_key: tuple[str, int], n: int
                ) -> dict[str, np.ndarray] | None:
    """One-minute high/low/vol/delta shifted onto the mid series' causality.

    ``S19.load_deltas``'s law, applied to the four arrays the twin needs: flow
    bar ``k`` closes at ``lat[k+1]``, so the flow bar contemporaneous with mid
    bar ``j`` is flow bar ``j-1``.
    """

    try:
        day = FLOW.load_flow(asset, int(d8))
    except FLOW.FlowStop:
        return None
    arrays = day.get(cell_key)
    if arrays is None:
        return None
    out: dict[str, np.ndarray] = {}
    for name, source in (("high", "bar_high_mid2"), ("low", "bar_low_mid2"),
                         ("delta", "delta"), ("vol", "vol")):
        raw = np.asarray(arrays[source], np.float64)
        if len(raw) < n - 1:
            return None
        shifted = np.zeros(n, np.float64)
        shifted[1:] = raw[:n - 1]
        out[name] = shifted
    return out


def _entry_counters() -> dict[str, int]:
    counters: dict[str, int] = {}
    for tag in ("cls", "twin"):
        for suffix in ("out_of_range", "illegal", "unpriceable", "priced"):
            counters[f"{tag}_{suffix}"] = 0
    return counters


def oracle_pass(events: Sequence[Event], cells: Sequence[S8.Cell8],
                trained: Mapping[tuple[str, int], float], mutant: str
                ) -> dict[str, object]:
    """One pass over the shards: raw-tick atoms, minute twins, priced entries."""

    cell_by_position = {int(cell.position): cell for cell in cells}
    by_cell: dict[int, list[int]] = {}
    for position, event in enumerate(events):
        by_cell.setdefault(int(event.cell), []).append(position)
    by_day: dict[tuple[str, int], list[int]] = {}
    for position in sorted(by_cell):
        cell = cell_by_position.get(position)
        if cell is not None:
            by_day.setdefault((cell.asset, int(cell.d8)), []).append(position)

    counters = {"shards": 0, "cells": 0, "cells_missing_shard": 0,
                "cells_missing_bars": 0, "events_scanned": 0,
                "events_no_ticks": 0, "events_no_scale": 0,
                "events_classed": 0, "events_unclassed": 0,
                "twin_classed": 0, "tape_missing": 0, "tape_trades": 0}
    counters.update(_entry_counters())
    atom_counts = {f"{asset}|{atom}": 0 for asset in ASSETS for atom in ATOMS}
    entries: dict[str, dict[int, S22.Priced]] = {}
    twin_entries: dict[str, dict[int, S22.Priced]] = {}
    mid_by_cell: dict[int, np.ndarray] = {}
    lat_by_cell: dict[int, np.ndarray] = {}
    entry_audit: list[dict[str, object]] = []
    entry_law = {"checked": 0, "violations": 0, "worst_gap_ns": None}

    for (asset, d8) in sorted(by_day):
        counters["shards"] += 1
        tape, tape_counters = load_tape(asset, int(d8))
        counters["tape_missing"] += int(tape_counters["missing_pack"])
        counters["tape_trades"] += int(tape_counters["trades"])
        shard = M.load_shard(asset, int(d8))
        try:
            by_text = {cell.text: cell for cell in shard.cells}
            for position in sorted(by_day[(asset, int(d8))]):
                cell8 = cell_by_position[position]
                rec = cell8.rec
                shard_cell = by_text.get(rec.text)
                if shard_cell is None:
                    counters["cells_missing_shard"] += 1
                    continue
                index = shard.cell_index(shard_cell)
                counters["cells"] += 1
                lat = np.asarray(rec.lat, np.int64)
                mid = np.asarray(rec.mid, np.int64)
                mid_by_cell[position] = mid
                lat_by_cell[position] = lat
                key = (rec.phase, int(rec.phase_open_ts_ns))
                bars = _bar_arrays(asset, int(d8), key, int(rec.n))
                if bars is None:
                    counters["cells_missing_bars"] += 1
                    continue
                tick_ts = np.asarray(index.ts, np.uint64).astype(np.int64)
                tick_mid = np.asarray(index.mid2, np.int64)

                for local in by_cell.get(position, []):
                    event = events[local]
                    counters["events_scanned"] += 1
                    scale = float(trained.get((asset, int(d8)), 0.0))
                    if not scale > 0.0:
                        counters["events_no_scale"] += 1
                        continue
                    event.scale = scale
                    threshold = ABSORB_Q * scale
                    b0, b1 = int(event.bar0), int(event.bar1)
                    if not 0 <= b0 <= b1 < int(rec.n):
                        counters["events_no_ticks"] += 1
                        continue
                    start_ns = int(lat[b0])
                    stop_ns = int(lat[b1])
                    lo = int(np.searchsorted(tick_ts, start_ns, side="left"))
                    hi = int(np.searchsorted(tick_ts, stop_ns, side="right"))
                    if hi <= lo:
                        counters["events_no_ticks"] += 1
                        continue
                    t_lo = int(np.searchsorted(tape.ts, start_ns, side="left"))
                    t_hi = int(np.searchsorted(tape.ts, stop_ns, side="right"))
                    window_tape = Tape(tape.ts[t_lo:t_hi], tape.price2[t_lo:t_hi],
                                       tape.signed[t_lo:t_hi])

                    bar_index = np.arange(b0, b1 + 1, dtype=np.int64)
                    opens = mid[np.maximum(bar_index - 1, 0)].astype(np.float64)
                    closes = mid[bar_index].astype(np.float64)
                    highs = bars["high"][bar_index]
                    lows = bars["low"][bar_index]
                    deltas = bars["delta"][bar_index]
                    # A bar with no book prints 0 in the flow cache; fall back
                    # to the lattice close so the twin never reads a fake
                    # extreme at price zero.
                    blank = (highs <= 0.0) | (lows <= 0.0)
                    highs = np.where(blank, closes, highs)
                    lows = np.where(blank, closes, lows)

                    if mutant == MUTANT_MINUTE_ATOMS:
                        atoms, cycles = minute_atoms(
                            opens, highs, lows, closes, deltas, bar_index,
                            event.zone_price, event.width, event.probe_side,
                            threshold)
                        atoms = tuple((name, int(lat[int(mark)]))
                                      for name, mark in atoms)
                    else:
                        atoms, cycles = tick_atoms(
                            tick_ts[lo:hi], tick_mid[lo:hi], window_tape,
                            event.zone_price, event.width, event.probe_side,
                            threshold)
                    event.atoms = atoms
                    event.order = order_text(atoms)
                    event.cycles = int(cycles)
                    for name, _mark in atoms:
                        atom_counts[f"{asset}|{name}"] += 1
                    klass, done = classify_atoms(atoms, cycles, WITHIN_NS)
                    event.klass = klass
                    event.done_ts = int(done)

                    # ---- the minute signature, for the collapse flag -------
                    event.signature = minute_signature(
                        _regions(opens, event.zone_price, event.width,
                                 event.probe_side),
                        _regions(highs, event.zone_price, event.width,
                                 event.probe_side),
                        _regions(lows, event.zone_price, event.width,
                                 event.probe_side),
                        _regions(closes, event.zone_price, event.width,
                                 event.probe_side),
                        np.where(
                            float(event.probe_side) * deltas
                            >= FLOW_BUCKET_Q * scale, 1,
                            np.where(float(event.probe_side) * deltas
                                     <= -FLOW_BUCKET_Q * scale, -1, 0)))

                    # ---- the minute twin ----------------------------------
                    twin, twin_cycles = minute_atoms(
                        opens, highs, lows, closes, deltas, bar_index,
                        event.zone_price, event.width, event.probe_side,
                        threshold)
                    event.twin_atoms = twin
                    event.twin_order = order_text(twin)
                    event.twin_cycles = int(twin_cycles)
                    twin_class, twin_done = classify_atoms(
                        twin, twin_cycles, WITHIN_BARS)
                    event.twin_class = twin_class
                    event.twin_done_bar = int(twin_done)

                    # ---- the executable entries ---------------------------
                    if klass != UNCLASSED and done >= 0:
                        counters["events_classed"] += 1
                        containing = int(np.searchsorted(lat, int(done),
                                                         side="left"))
                        entry_bar = containing + (
                            0 if mutant == MUTANT_EARLY_ENTRY else 1)
                        event.entry_bar = int(entry_bar)
                        for side in _sides(klass, event.probe_side):
                            tag = _line(klass, side, event.probe_side)
                            priced = S22.price_bar_entry(
                                index, rec, tag, local, None, asset, int(d8),
                                rec.phase, position, int(entry_bar), int(side),
                                counters, "cls")
                            if priced is None:
                                continue
                            entries.setdefault(tag, {})[local] = priced
                            entry_law["checked"] += 1
                            gap = int(done) - int(priced.entry_ts_ns)
                            worst = entry_law["worst_gap_ns"]
                            entry_law["worst_gap_ns"] = (
                                gap if worst is None else max(int(worst), gap))
                            if gap >= 0:
                                entry_law["violations"] += 1
                            if len(entry_audit) < 10:
                                entry_audit.append({
                                    "asset": asset, "d8": int(d8),
                                    "cell": position, "kind": event.kind,
                                    "class": klass, "order": event.order,
                                    "completion_ts_ns": int(done),
                                    "containing_bar": containing,
                                    "containing_bar_close_ns": int(
                                        lat[min(containing, int(rec.n) - 1)]),
                                    "entry_bar": int(entry_bar),
                                    "entry_ts_ns": int(priced.entry_ts_ns),
                                    "entry_minus_completion_ns": -int(gap)})
                    else:
                        counters["events_unclassed"] += 1

                    if twin_class != UNCLASSED and twin_done >= 0:
                        counters["twin_classed"] += 1
                        twin_bar = int(twin_done) + 1
                        event.twin_entry_bar = twin_bar
                        for side in _sides(twin_class, event.probe_side):
                            tag = _line(twin_class, side, event.probe_side)
                            priced = S22.price_bar_entry(
                                index, rec, f"TWIN|{tag}", local, None, asset,
                                int(d8), rec.phase, position, twin_bar,
                                int(side), counters, "twin")
                            if priced is None:
                                continue
                            twin_entries.setdefault(tag, {})[local] = priced
        finally:
            shard.close()
        del tape
    return {"counters": counters, "atom_counts": atom_counts,
            "entries": entries, "twin_entries": twin_entries,
            "mid_by_cell": mid_by_cell, "lat_by_cell": lat_by_cell,
            "entry_law": entry_law, "entry_audit": entry_audit}


def _sides(klass: str, probe: int) -> tuple[int, ...]:
    """The class's implied side.  P2 implies none and is priced both ways."""

    implied = CLASS_SIDE[klass]
    if implied == 0:
        return (1, -1)
    return (int(implied * int(probe)),)


def _line(klass: str, side: int, probe: int) -> str:
    """The line tag: the class, plus the side leg where the class implies none."""

    if CLASS_SIDE[klass] != 0:
        return klass
    return f"{klass}|{'LONG' if int(side) > 0 else 'SHORT'}"


def class_lines(klass: str) -> tuple[str, ...]:
    if CLASS_SIDE[klass] != 0:
        return (klass,)
    return (f"{klass}|LONG", f"{klass}|SHORT")


# --------------------------------------------------------------------------
# Measurement, replay and the two stresses, per class and per twin.
# --------------------------------------------------------------------------

def average_cash(blocks: Sequence[Mapping[str, object]], key: str
                 ) -> float | None:
    values = [b[key] for b in blocks if b.get(key) is not None]
    if len(values) != len(blocks) or not values:
        return None
    return float(np.mean([float(v) for v in values]))


def evaluate(lines: Sequence[str], raw_pool: Mapping[str, Mapping[int, S22.Priced]],
             events: Sequence[Event], explore_days: Mapping[str, Sequence[int]],
             mid_by_cell: Mapping[int, np.ndarray],
             lat_by_cell: Mapping[int, np.ndarray], formed: Mapping[str, int],
             with_stresses: bool, allowed: set[int] | None = None
             ) -> dict[str, object]:
    """One class, or one twin class: measured, seated, MDD'd and stressed.

    When a class implies no side it has two legs.  The measured line is the
    EQUAL-WEIGHT AVERAGE of the legs - what a sideless condition is worth - and
    each leg is reported beside it.  The seat replay of a two-leg class seats
    both legs, so its occupancy and cap are the honest ones.
    """

    # One priced pool serves both dedupe readings; ``allowed`` names the event
    # positions that reading admits, so nothing is priced twice.
    pool = {line: ({position: entry
                    for position, entry in raw_pool[line].items()
                    if allowed is None or position in allowed})
            for line in lines if line in raw_pool}
    legs = [line for line in lines if line in pool and pool[line]]
    chosen = [entry for line in legs for entry in pool[line].values()]
    per_asset = {asset: {} for asset in ASSETS}
    leg_report: dict[str, object] = {}
    days = {asset: sorted(int(d) for d in explore_days[asset])
            for asset in ASSETS}
    for asset in ASSETS:
        blocks = []
        for line in legs:
            block = S22.measure_line(list(pool[line].values()), CLOSE, asset,
                                     days[asset], formed.get(asset, 0))
            leg_report.setdefault(line, {})[asset] = block
            blocks.append(block)
        for label in LABELS:
            per_asset[asset][label] = S22.measure_line(
                [entry for line in legs for entry in pool[line].values()],
                label, asset, days[asset], formed.get(asset, 0))
        if len(legs) > 1:
            averaged = dict(per_asset[asset][CLOSE])
            for key in ("usd_per_asset_day", "mean_minus_2se_usd",
                        "mean_cert_usd", "total_usd", "over_rung"):
                averaged[key] = average_cash(blocks, key)
            averaged["legs_averaged"] = True
            per_asset[asset][CLOSE] = averaged

    replay = S22.replay(chosen, CLOSE)
    cash = S22.replay_cash(replay["trades"], explore_days)
    if len(legs) > 1:
        # Two legs of one sideless condition: the seated cash of the class is
        # the average of the legs' own seated cash, not the sum of a portfolio
        # that took both sides of every event.
        for asset in ASSETS:
            leg_cash = []
            for line in legs:
                leg_replay = S22.replay(list(pool[line].values()), CLOSE)
                leg_cash.append(S22.replay_cash(leg_replay["trades"],
                                                explore_days)[asset])
            merged = dict(cash[asset])
            for key in ("usd_per_day", "mean_minus_2se_usd", "total_usd"):
                merged[key] = average_cash(leg_cash, key)
            merged["clears_rung"] = (
                None if merged["usd_per_day"] is None
                or merged["mean_minus_2se_usd"] is None else
                bool(merged["usd_per_day"] >= DAY_RUNG_USD[asset]
                     and merged["mean_minus_2se_usd"] >= DAY_RUNG_USD[asset]))
            merged["legs_averaged"] = True
            cash[asset] = merged
    mdd = S22.mdd_ledgers(replay["trades"], mid_by_cell, lat_by_cell,
                          explore_days)
    out: dict[str, object] = {
        "lines": list(legs), "n": len(chosen), "per_asset": per_asset,
        "legs": leg_report, "replay": {k: v for k, v in replay.items()
                                       if k != "trades"},
        "cash": cash, "mdd": mdd,
        "events": sorted({int(p) for line in legs for p in pool[line]}),
    }
    if with_stresses:
        stresses: dict[str, object] = {}
        for kind in ("adversarial", "spread"):
            overrides = S22.stress_overrides(chosen, CLOSE, kind)
            seated = S22.replay(chosen, CLOSE, overrides)
            stresses[kind] = {
                "seated": seated["seated"],
                "cash": S22.replay_cash(seated["trades"], explore_days),
                "mdd": S22.mdd_ledgers(seated["trades"], mid_by_cell,
                                       lat_by_cell, explore_days)}
        out["stresses"] = stresses
    return out


def upper95(cash: Mapping[str, object], asset: str) -> float | None:
    block = cash.get(asset, {})
    mean = block.get("usd_per_day")
    se = block.get("se_usd")
    if mean is None or se is None:
        return None
    return float(mean) + 2.0 * float(se)


# --------------------------------------------------------------------------
# The letters.
# --------------------------------------------------------------------------

def class_letter(block: Mapping[str, object], twin: Mapping[str, object],
                 collapse: object) -> dict[str, object]:
    """The four preregistered clauses, tested in the registered order."""

    per_asset = block["per_asset"]
    cash = block["cash"]
    n_by_asset = {asset: int(per_asset[asset][CLOSE]["n"]) for asset in ASSETS}
    powered = any(n_by_asset[asset] >= MIN_CLASS_N for asset in DECIDING)

    point = {asset: cash[asset]["usd_per_day"] for asset in DECIDING}
    lower = {asset: cash[asset]["mean_minus_2se_usd"] for asset in DECIDING}
    rung = {asset: DAY_RUNG_USD[asset] for asset in DECIDING}
    over = {asset: (None if point[asset] is None
                    else float(point[asset]) / rung[asset])
            for asset in DECIDING}
    point_ok = {asset: (point[asset] is not None
                        and float(point[asset]) >= rung[asset])
                for asset in DECIDING}
    lower_ok = {asset: (lower[asset] is not None
                        and float(lower[asset]) >= rung[asset])
                for asset in DECIDING}
    mdd_values = [float(block["mdd"]["max_binding_usd"])]
    for kind in ("adversarial", "spread"):
        stress = block.get("stresses", {}).get(kind)
        if stress is not None:
            mdd_values.append(float(stress["mdd"]["max_binding_usd"]))
    mdd_ok = bool(max(mdd_values) < MDD_CEILING)
    twin_upper = {asset: upper95(twin["cash"], asset) for asset in DECIDING}
    twin_nonpositive = all(
        twin_upper[asset] is not None and float(twin_upper[asset]) <= 0.0
        for asset in DECIDING)
    half = {asset: (over[asset] is not None and float(over[asset]) >= HALF_RUNG)
            for asset in DECIDING}

    reasons: list[str] = []
    if not powered:
        letter = LETTER_UNPOWERED
        reasons.append(
            f"fewer than {MIN_CLASS_N} entries on every deciding asset: "
            + ", ".join(f"{a} {n_by_asset[a]}" for a in DECIDING))
    elif (all(point_ok.values()) and all(lower_ok.values()) and mdd_ok
          and twin_nonpositive and collapse is not None):
        letter = LETTER_RICH
        reasons.append("both deciders clear at point and mean-2SE, every "
                       "binding MDD under replay and both stresses is below "
                       f"{MDD_CEILING:.0f}, and the minute twin's upper 95 "
                       "bound is non-positive on both deciders")
    elif any(point_ok.values()):
        letter = LETTER_PRESENT
        if all(point_ok.values()):
            missing = []
            if not all(lower_ok.values()):
                missing.append("mean-2SE")
            if not mdd_ok:
                missing.append("MDD")
            if not twin_nonpositive:
                missing.append("twin upper bound")
            reasons.append("both deciders clear at the point estimate; failed "
                           + ", ".join(missing or ["collapse evidence"]))
        else:
            reasons.append("one decider only at the point estimate: "
                           + ", ".join(f"{a} {_show(over[a])}x"
                                       for a in DECIDING))
    elif not any(half.values()):
        letter = LETTER_POOR
        reasons.append("no deciding rung reached at half at the point "
                       "estimate: " + ", ".join(f"{a} {_show(over[a])}x"
                                                for a in DECIDING))
    else:
        letter = LETTER_PRESENT
        reasons.append("half a deciding rung is reached but no rung is "
                       "cleared at the point estimate: "
                       + ", ".join(f"{a} {_show(over[a])}x" for a in DECIDING))
    return {"letter": letter, "reasons": reasons, "n": n_by_asset,
            "powered": powered, "point": point, "lower": lower, "over": over,
            "point_ok": point_ok, "lower_ok": lower_ok,
            "max_binding_mdd_usd": float(max(mdd_values)), "mdd_ok": mdd_ok,
            "twin_upper95": twin_upper,
            "twin_upper_nonpositive": bool(twin_nonpositive),
            "collapse_rate": collapse,
            "reaches_half_rung": half}


# --------------------------------------------------------------------------
# The run.
# --------------------------------------------------------------------------

def run() -> dict[str, object]:
    mutant = _mutant()
    started = time.time()
    cells, _days, _skipped = S8.build_cells(ASSETS)
    records, _rec_days = S1.load_cache()
    explore_days = S1._explore_days(ASSETS)
    tape9 = S9.load_tape(cells)
    forecast = S9.forecast_variance(cells)
    plane9 = S9.build_plane(cells, forecast, tape9)
    scoring = {asset: sorted(int(d) for d in explore_days[asset])[MIN_PRIOR_DAYS:]
               for asset in ASSETS}
    repro = S19.reproduce(plane9, scoring)
    if not repro["matches"]:
        raise SweepRefusal("sweep 9's occurrence plane did not reproduce; no "
                           "event is formed past this point")
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
    streams, _stream_counters = S14.build_streams(plane9, cells, states, "")
    causal = S14.assert_causal(streams, plane9)
    if not causal["no_outcome_in_features"]:
        raise SweepRefusal("a feature reads the outcome it is choosing over")

    # ---- the two universes, each through its OWN formation pass -----------
    approaches, approach_formation = S22.formation_pass(cells, explore_days, "")
    if len(approaches) != EXPECT_APPROACHES:
        raise SweepRefusal(
            f"sweep 22's formation pass returned {len(approaches)} zone "
            f"approaches, not {EXPECT_APPROACHES}; the universe under test is "
            f"not the one Sol's bar names")
    if not approach_formation["strictly_prior"]:
        raise SweepRefusal("the approach universe's level read is not strictly "
                           "prior to its own entry stamp")
    breaks, break_formation = S23.formation_pass(cells, explore_days, "")
    if len(breaks) != EXPECT_BREAKS:
        raise SweepRefusal(
            f"sweep 23's break formation returned {len(breaks)} breaks, not "
            f"{EXPECT_BREAKS}; the universe under test is not the one Sol's "
            f"bar names")
    if not break_formation["strictly_prior"]:
        raise SweepRefusal("the break universe's level read is not strictly "
                           "prior to its breach close")

    events, union = build_events(approaches, breaks)

    # ---- the trained absorption scale ------------------------------------
    scales, scale_counters = day_flow_scales(explore_days)
    trained = absorb_scales(scales, explore_days)
    scale_report = {
        "counters": scale_counters,
        "day_scales": len(scales), "trained_days": len(trained),
        "absorb_q": ABSORB_Q,
        "sample": {f"{asset}|{d8}": float(value)
                   for (asset, d8), value in sorted(trained.items())[:6]},
        "per_asset_median": {
            asset: (float(np.median([v for (a, _d), v in trained.items()
                                     if a == asset]))
                    if any(a == asset for a, _d in trained) else None)
            for asset in ASSETS}}

    # ---- the one shard pass ----------------------------------------------
    oracle = oracle_pass(events, cells, trained, mutant)
    if oracle["entry_law"]["violations"]:
        raise SweepRefusal(
            f"{oracle['entry_law']['violations']} entries were not strictly "
            f"after their own class completion; the executable-entry law is "
            f"this unit's whole licence to read ticks")

    # ---- both dedupe readings, off ONE priced pool ------------------------
    readings: dict[str, list[int]] = {
        "PRIMARY": [p for p, e in enumerate(events) if not e.overlap_dropped],
        "LITERAL": [p for p, e in enumerate(events) if not e.literal_dropped]}
    results: dict[str, dict[str, object]] = {}
    for name, positions in readings.items():
        allowed = set(positions)
        subset = [events[p] for p in positions]
        collapse = collapse_flags(subset)
        formed = {asset: sum(1 for e in subset if e.asset == asset)
                  for asset in ASSETS}
        class_counts = {
            f"{klass}|{asset}": int(sum(1 for e in subset if e.klass == klass
                                        and e.asset == asset))
            for klass in list(CLASSES) + [UNCLASSED] for asset in ASSETS}
        twin_counts = {
            f"{klass}|{asset}": int(sum(1 for e in subset
                                        if e.twin_class == klass
                                        and e.asset == asset))
            for klass in list(CLASSES) + [UNCLASSED] for asset in ASSETS}
        blocks: dict[str, object] = {}
        twins: dict[str, object] = {}
        letters: dict[str, object] = {}
        separation: dict[str, object] = {}
        for klass in CLASSES:
            lines = class_lines(klass)
            blocks[klass] = evaluate(lines, oracle["entries"], events,
                                     explore_days, oracle["mid_by_cell"],
                                     oracle["lat_by_cell"], formed, True,
                                     allowed)
            twins[klass] = evaluate(lines, oracle["twin_entries"], events,
                                    explore_days, oracle["mid_by_cell"],
                                    oracle["lat_by_cell"], formed, False,
                                    allowed)
            tick_set = {p for p in positions if events[p].klass == klass}
            twin_set = {p for p in positions if events[p].twin_class == klass}
            separation[klass] = {
                "tick_n": len(tick_set), "twin_n": len(twin_set),
                "both": len(tick_set & twin_set),
                "separation_n": len(tick_set ^ twin_set),
                "by_asset": {
                    asset: int(sum(1 for p in (tick_set ^ twin_set)
                                   if events[p].asset == asset))
                    for asset in ASSETS}}
            letters[klass] = class_letter(blocks[klass], twins[klass],
                                          collapse["by_class"].get(klass))

        def _rank(klass: str, table=letters) -> tuple[int, float]:
            over = table[klass]["over"]
            worst = min(float(over[a]) if over[a] is not None else -9e9
                        for a in DECIDING)
            return (LETTER_RANK[table[klass]["letter"]], worst)

        ranked = sorted(CLASSES, key=_rank, reverse=True)
        results[name] = {
            "events": len(subset), "collapse": collapse,
            "class_counts": class_counts, "twin_counts": twin_counts,
            "classes": {k: _slim(blocks[k]) for k in CLASSES},
            "twins": {k: _slim(twins[k]) for k in CLASSES},
            "letters": letters, "separation": separation,
            "class_rank": ranked, "best_class": ranked[0],
            "family_letter": letters[ranked[0]]["letter"],
            "best_detail": {"class": blocks[ranked[0]],
                            "twin": twins[ranked[0]]}}

    primary = results["PRIMARY"]
    literal = results["LITERAL"]
    collapse = primary["collapse"]
    class_counts = primary["class_counts"]
    twin_counts = primary["twin_counts"]
    letters = primary["letters"]
    separation = primary["separation"]
    ranked = primary["class_rank"]
    best = primary["best_class"]
    family_letter = primary["family_letter"]
    # Re-flag the primary reading so the reported ``collapsed`` field matches
    # the reported collapse table.
    collapse_flags([events[p] for p in readings["PRIMARY"]])
    agreement = {
        "primary_letter": family_letter,
        "literal_letter": literal["family_letter"],
        "letters_agree": bool(family_letter == literal["family_letter"]),
        "primary_best": best, "literal_best": literal["best_class"],
        "primary_events": primary["events"], "literal_events": literal["events"],
        "note": ("the family letter is reported under BOTH dedupe readings; a "
                 "disagreement would be reported as a disagreement, not "
                 "resolved")}

    report: dict[str, object] = {
        "family": FAMILY, "parent_trial": PARENT_TRIAL, "seed": SEED,
        "spec": SPEC, "spec_sha": SPEC_SHA, "code_sha": code_sha(),
        "split_sha": S1.split_sha(), "outcome_law_sha": S1.outcome_law_sha(),
        "registered_utc": report_stamp(), "mutant": mutant,
        "law_note": ("THIS UNIT CHANGES NO LAW.  The grain law stands.  Raw "
                     "ticks price and describe outcomes here; every entry is a "
                     "lawful one-minute bar stamp strictly after the class "
                     "completes.  No policy is promoted from this receipt."),
        "gate": {"sweep9": repro,
                 "levels_manifest_gap_ns": cache_gap,
                 "scoring_days": {a: len(scoring[a]) for a in ASSETS}},
        "scoring_days": scoring,
        "universes": {
            "approaches": {"n": len(approaches),
                           "expected": EXPECT_APPROACHES,
                           "counters": approach_formation["counters"],
                           "strictly_prior": approach_formation["strictly_prior"]},
            "breaks": {"n": len(breaks), "expected": EXPECT_BREAKS,
                       "counters": break_formation["counters"],
                       "strictly_prior": break_formation["strictly_prior"]}},
        "union": union,
        "flow_scale": scale_report,
        "oracle_counters": oracle["counters"],
        "atom_counts": oracle["atom_counts"],
        "entry_law": oracle["entry_law"],
        "entry_audit": oracle["entry_audit"],
        "class_counts": class_counts, "twin_counts": twin_counts,
        "collapse": collapse,
        "separation": separation,
        "classes": primary["classes"],
        "twins": primary["twins"],
        "letters": letters,
        "best_class": best, "family_letter": family_letter,
        "class_rank": ranked,
        "best_detail": primary["best_detail"],
        "dedupe_readings": {name: {k: v for k, v in block.items()
                                   if k != "best_detail"}
                            for name, block in results.items()},
        "dedupe_agreement": agreement,
        "hindsight_bits": {P2: HINDSIGHT_P2},
        "clauses": CLAUSES, "clause_order": list(CLAUSE_ORDER),
        "precedence": list(PRECEDENCE),
        "elapsed_s": round(time.time() - started, 1),
    }
    report["headline"] = headline(report)
    return report


def _slim(block: Mapping[str, object]) -> dict[str, object]:
    """The block without its per-event index, which the report does not need."""

    return {k: v for k, v in block.items() if k != "events"}


def headline(report: Mapping[str, object]) -> dict[str, object]:
    best = str(report["best_class"])
    letter = report["letters"][best]
    twin = report["twins"][best]
    return {
        "best_class": best,
        "letter": letter["letter"],
        "over_rung": {a: letter["over"][a] for a in DECIDING},
        "twin_over_rung": {
            a: (None if twin["cash"][a]["usd_per_day"] is None else
                float(twin["cash"][a]["usd_per_day"]) / DAY_RUNG_USD[a])
            for a in DECIDING},
        "collapse_rate": report["collapse"]["collapse_rate"],
        "collapse_rate_best_class": report["collapse"]["by_class"].get(best),
        "family_letter": report["family_letter"]}


# --------------------------------------------------------------------------
# Printing.
# --------------------------------------------------------------------------

def print_summary(report: Mapping[str, object]) -> None:
    head = report["headline"]
    best = str(head["best_class"])
    over = head["over_rung"]
    twin = head["twin_over_rung"]
    print(f"\nSWEEP 26  {FAMILY}  parent {PARENT_TRIAL}  "
          f"mutant={report['mutant'] or 'none'}")
    print(f"  BEST CLASS {best}: NKD {_show(over['NKD'])}x rung, SI "
          f"{_show(over['SI'])}x rung | MINUTE TWIN NKD {_show(twin['NKD'])}x, "
          f"SI {_show(twin['SI'])}x | collapse rate "
          f"{_show(head['collapse_rate_best_class'])} (all events "
          f"{_show(head['collapse_rate'])}) -> {head['family_letter']}")
    print(f"  {report['law_note']}")


def print_gate(report: Mapping[str, object]) -> None:
    gate = report["gate"]
    print("\nGATE")
    print(f"  sweep 9 row plane reproduces      {gate['sweep9']['matches']}")
    print(f"  levels manifest max(src - stamp)  "
          f"{gate['levels_manifest_gap_ns']} ns (must be < 0)")
    print(f"  scoring days                      "
          + ", ".join(f"{a} {gate['scoring_days'][a]}" for a in ASSETS))
    for name, block in report["universes"].items():
        print(f"  {name:<12} formed {block['n']:>6} of expected "
              f"{block['expected']:>6}   strictly prior "
              f"{block['strictly_prior']}")
    union = report["union"]
    print(f"  union {union['union_in']} rows (14650 + 3790, both reproduced)")
    print(f"  PRIMARY dedupe ({union['primary_key']}): "
          f"{union['primary_out']} events, {union['primary_overlap_dropped']} "
          f"breaks dropped inside an overlapping approach")
    print(f"  SENSITIVITY, the literal key {union['literal_key']}: "
          f"{union['literal_out']} events (dropped "
          f"{union['literal_dropped_approach']} approach, "
          f"{union['literal_dropped_break']} break) - it deletes "
          f"{100.0 * union['literal_dropped_approach'] / max(union['approaches_in'], 1):.0f}"
          f"% of the approach universe the same instruction orders reproduced")
    print(f"  diagnostic: a zone-kind reading of 'kind' would have dropped "
          f"{union['zone_kind_reading_would_drop']} rows and deleted one "
          f"universe")
    agree = report["dedupe_agreement"]
    print(f"  letters under both readings: PRIMARY {agree['primary_letter']} "
          f"({agree['primary_best']}, {agree['primary_events']} events) vs "
          f"LITERAL {agree['literal_letter']} ({agree['literal_best']}, "
          f"{agree['literal_events']} events) -> agree "
          f"{agree['letters_agree']}")
    scale = report["flow_scale"]
    print(f"  trained absorption scale: {scale['trained_days']} scoring days, "
          f"ABSORB_Q {scale['absorb_q']}, per-asset median scale "
          + ", ".join(f"{a} {_show(scale['per_asset_median'][a])}"
                      for a in ASSETS))


def print_atoms(report: Mapping[str, object]) -> None:
    print("\nATOM AND CLASS COUNTERS, per asset")
    print(f"  {'asset':<6}" + "".join(f"{atom:>10}" for atom in ATOMS)
          + "".join(f"{k.split('_')[0]:>8}" for k in CLASSES)
          + f"{'UNCLS':>8}{'events':>8}")
    counts = report["atom_counts"]
    for asset in ASSETS:
        row = f"  {asset:<6}"
        row += "".join(f"{counts[f'{asset}|{atom}']:>10,}" for atom in ATOMS)
        row += "".join(f"{report['class_counts'][f'{k}|{asset}']:>8,}"
                       for k in CLASSES)
        row += f"{report['class_counts'][f'{UNCLASSED}|{asset}']:>8,}"
        row += f"{report['union']['by_asset'][asset]:>8,}"
        print(row)
    print("  (atom counts are over every scanned row of both universes; the "
          "class columns are the PRIMARY dedupe reading)")
    counters = report["oracle_counters"]
    print(f"  scanned {counters['events_scanned']:,}, classed "
          f"{counters['events_classed']:,}, unclassed "
          f"{counters['events_unclassed']:,}, no ticks "
          f"{counters['events_no_ticks']:,}, twin classed "
          f"{counters['twin_classed']:,}; raw trades read "
          f"{counters['tape_trades']:,} over {counters['shards']} shards")
    law = report["entry_law"]
    print(f"  executable-entry law: {law['checked']:,} entries checked, "
          f"{law['violations']} violations, worst (completion - entry) "
          f"{law['worst_gap_ns']} ns (must be < 0)")


def print_classes(report: Mapping[str, object]) -> None:
    print("\nCLASS TABLES, sub-minute class beside its MINUTE-COARSENED TWIN "
          "(frozen close label)")
    print(f"  {'class':<24}{'asset':<5}{'n':>6}{'cov':>8}{'usd/day':>11}"
          f"{'x rung':>8}{'-2SE':>11}{'MDD':>10} | "
          f"{'twin n':>7}{'twin usd/day':>13}{'twin x':>8}{'twin -2SE':>11}"
          f"{'twin MDD':>10}{'collapse':>9}{'sep n':>7}")
    for klass in CLASSES:
        block = report["classes"][klass]
        twin = report["twins"][klass]
        sep = report["separation"][klass]
        for asset in ASSETS:
            cell = block["per_asset"][asset][CLOSE]
            tcell = twin["per_asset"][asset][CLOSE]
            cash = block["cash"][asset]
            tcash = twin["cash"][asset]
            rate = report["collapse"]["by_class_asset"].get(f"{klass}|{asset}")
            print(f"  {klass if asset == ASSETS[0] else '':<24}{asset:<5}"
                  f"{cell['n']:>6,}{_n(cell['coverage'], 8, 4)}"
                  f"{_n(cash['usd_per_day'], 11, 1)}"
                  f"{_n(cell['over_rung'], 8, 3)}"
                  f"{_n(cash['mean_minus_2se_usd'], 11, 1)}"
                  f"{_n(cell['mdd_day_usd'], 10, 0)} | "
                  f"{tcell['n']:>7,}{_n(tcash['usd_per_day'], 13, 1)}"
                  f"{_n(tcell['over_rung'], 8, 3)}"
                  f"{_n(tcash['mean_minus_2se_usd'], 11, 1)}"
                  f"{_n(tcell['mdd_day_usd'], 10, 0)}"
                  f"{_n(rate, 9, 3)}"
                  f"{sep['by_asset'][asset]:>7,}")
        print(f"  {'':<24}{'':<5}{'':>6}  {CLASS_NAME[klass]}")


def print_collapse(report: Mapping[str, object]) -> None:
    collapse = report["collapse"]
    print("\nCOLLAPSE (identical minute signature, different tick atom order)")
    print(f"  signature groups {collapse['signature_groups']:,}, of which "
          f"{collapse['groups_with_mixed_orders']:,} carry more than one atom "
          f"order")
    print(f"  collapsed events {collapse['collapsed_events']:,} of "
          f"{collapse['events_with_signature']:,} -> rate "
          f"{_show(collapse['collapse_rate'])}")
    print("  by asset  " + "  ".join(
        f"{a} {_show(collapse['by_asset'][a])}" for a in ASSETS))
    print("  by class  " + "  ".join(
        f"{k.split('_')[0]} {_show(collapse['by_class'][k])}" for k in CLASSES))


def print_best(report: Mapping[str, object]) -> None:
    best = str(report["best_class"])
    block = report["best_detail"]["class"]
    print(f"\nSEAT REPLAY AND MDD LEDGERS, best class {best} "
          f"({CLASS_NAME[best]})")
    replay = block["replay"]
    print(f"  seated {replay['seated']:,}; rejected occupancy "
          f"{replay['rejected_occupancy']:,}, rejected cap "
          f"{replay['rejected_cap']:,}")
    port = block["cash"]["_portfolio"]
    print(f"  portfolio: dates with entries {port['dates_with_entries']}, max "
          f"seats {port['portfolio_seats_max']}, at-cap dates "
          f"{port['at_cap_dates']}, cap lawful {port['cap_lawful']}")
    for asset in ASSETS:
        cash = block["cash"][asset]
        print(f"  {asset:<4} usd/day {_n(cash['usd_per_day'], 10, 1)}  -2SE "
              f"{_n(cash['mean_minus_2se_usd'], 10, 1)}  trades "
              f"{cash['trades']:>5,}  seats/day {_n(cash['seats_mean'], 6, 2)}"
              f"  zero-entry days {_n(cash['zero_entry_fraction'], 6, 3)}"
              f"  clears rung {cash['clears_rung']}")
    print("  MDD ledgers (USD, bound 1000)")
    mdd = block["mdd"]
    for key in mdd["binding_ledgers"]:
        print(f"    {key:<18}{_n(mdd[key], 12, 1)}  BINDING")
    for key in sorted(k for k in mdd if "|" in k
                      and k not in mdd["binding_ledgers"]):
        print(f"    {key:<18}{_n(mdd[key], 12, 1)}")
    print(f"    max binding {_n(mdd['max_binding_usd'], 12, 1)}  clears "
          f"{mdd['clears']}")
    print("  STRESSES")
    for kind, stress in sorted(block.get("stresses", {}).items()):
        line = (f"    {kind:<14} seated {stress['seated']:>5,}  "
                + "  ".join(f"{a} {_n(stress['cash'][a]['usd_per_day'], 9, 1)}"
                            for a in ASSETS))
        print(line + f"  max binding MDD "
                     f"{_n(stress['mdd']['max_binding_usd'], 10, 1)}  clears "
                     f"{stress['mdd']['clears']}")
    if best == P2:
        print(f"  HINDSIGHT BIT: {HINDSIGHT_P2}")
        for line, legs in sorted(block["legs"].items()):
            print("    leg " + line + ": " + "  ".join(
                f"{a} {_n(legs[a]['usd_per_asset_day'], 9, 1)}"
                for a in ASSETS))


def print_decision(report: Mapping[str, object]) -> None:
    print("\nDECISION TABLE")
    print(f"  {'class':<24}{'letter':<16}{'NKD x':>9}{'SI x':>9}"
          f"{'NKD -2SE':>11}{'SI -2SE':>11}{'maxMDD':>10}"
          f"{'twin up95 NKD':>15}{'twin up95 SI':>14}{'collapse':>10}")
    for klass in report["class_rank"]:
        letter = report["letters"][klass]
        print(f"  {klass:<24}{letter['letter']:<16}"
              f"{_n(letter['over']['NKD'], 9, 3)}{_n(letter['over']['SI'], 9, 3)}"
              f"{_n(letter['lower']['NKD'], 11, 1)}"
              f"{_n(letter['lower']['SI'], 11, 1)}"
              f"{_n(letter['max_binding_mdd_usd'], 10, 0)}"
              f"{_n(letter['twin_upper95']['NKD'], 15, 1)}"
              f"{_n(letter['twin_upper95']['SI'], 14, 1)}"
              f"{_n(letter['collapse_rate'], 10, 3)}")
    for klass in report["class_rank"]:
        for reason in report["letters"][klass]["reasons"]:
            print(f"    {klass}: {reason}")
    agree = report["dedupe_agreement"]
    print(f"\n  FAMILY LETTER {report['family_letter']} (best class "
          f"{report['best_class']}, PRIMARY dedupe, "
          f"{agree['primary_events']} events)")
    print(f"  under the LITERAL key: {agree['literal_letter']} (best class "
          f"{agree['literal_best']}, {agree['literal_events']} events) -> the "
          f"two readings agree: {agree['letters_agree']}")
    literal = report["dedupe_readings"]["LITERAL"]
    print(f"  {'class':<24}{'literal letter':<16}{'NKD x':>9}{'SI x':>9}")
    for klass in literal["class_rank"]:
        block = literal["letters"][klass]
        print(f"  {klass:<24}{block['letter']:<16}"
              f"{_n(block['over']['NKD'], 9, 3)}{_n(block['over']['SI'], 9, 3)}")
    print(f"  clause order {', '.join(CLAUSE_ORDER)}")
    for name in CLAUSE_ORDER:
        print(f"    {name:<11} {CLAUSES[name]}")


def print_causality(report: Mapping[str, object]) -> None:
    print("\nEXECUTABLE-ENTRY AUDIT (first rows): completion < containing bar "
          "close < entry stamp")
    for row in report["entry_audit"][:6]:
        print(f"  {row['asset']}/{row['d8']} cell {row['cell']:<5} "
              f"{row['kind']:<8} {row['class']:<24} order {row['order']}")
        print(f"      completion {row['completion_ts_ns']}  bar "
              f"{row['containing_bar']} closes "
              f"{row['containing_bar_close_ns']}  entry bar "
              f"{row['entry_bar']} at {row['entry_ts_ns']}  (+"
              f"{row['entry_minus_completion_ns']:,} ns)")


# --------------------------------------------------------------------------
# Selftest: planted tape, planted collapse pair, planted separable pair,
# the executable-entry law and the letter partition.
# --------------------------------------------------------------------------

def _check(name: str, ok: bool, detail: str = "") -> tuple[str, bool, str]:
    return (name, bool(ok), detail)


PLANT_ZONE = 1000.0
PLANT_WIDTH = 10.0
PLANT_SIDE = 1            # approached from below
PLANT_THRESHOLD = 100.0
BASE_TS = 1_600_000_000 * NANOS


def _plant_tick_path() -> tuple[np.ndarray, np.ndarray, Tape]:
    """A hand-computed path: TOUCH, ABSORB, REJECT, TOUCH, BREACH.

    Every stamp is one second apart, so the whole sequence is inside one minute
    and P1's "within 60 s" predicate is decidable by hand.
    """

    prices = [985.0,       # outside, near side       (region -1)
              1002.0,      # inside the band          TOUCH  at t=1
              1004.0,      # still inside             ABSORB at t=2 (flow lands)
              1006.0,      # still inside
              986.0,       # back out, near side      REJECT at t=4
              1001.0,      # inside again             TOUCH  at t=5
              1015.0]      # through the far edge     BREACH at t=6
    ts = np.asarray([BASE_TS + i * NANOS for i in range(len(prices))], np.int64)
    mid = np.asarray(prices, np.float64)
    # One buy-aggressor print of 120 inside the band at t=2: 120 >= 100.
    tape = Tape(ts=np.asarray([BASE_TS + 2 * NANOS], np.int64),
                price2=np.asarray([1004], np.int64),
                signed=np.asarray([120], np.int64))
    return ts, mid, tape


def _selftest_planted(mutant: str) -> list[tuple[str, bool, str]]:
    out: list[tuple[str, bool, str]] = []
    ts, mid, tape = _plant_tick_path()
    if mutant == MUTANT_MINUTE_ATOMS:
        # The mutant reads the same path as ONE minute bar: open 985, high
        # 1015, low 985, close 1015, one delta.  Every atom stamp collapses.
        atoms, cycles = minute_atoms(
            np.asarray([985.0]), np.asarray([1015.0]), np.asarray([985.0]),
            np.asarray([1015.0]), np.asarray([120.0]), np.asarray([0]),
            PLANT_ZONE, PLANT_WIDTH, PLANT_SIDE, PLANT_THRESHOLD)
    else:
        atoms, cycles = tick_atoms(ts, mid, tape, PLANT_ZONE, PLANT_WIDTH,
                                   PLANT_SIDE, PLANT_THRESHOLD)
    expected = (TOUCH, ABSORB, REJECT, TOUCH, BREACH)
    got = tuple(name for name, _ in atoms)
    out.append(_check("planted_atom_sequence", got == expected,
                      f"expected {expected}, got {got}"))
    stamps = [int(mark) for _, mark in atoms]
    hand = [BASE_TS + i * NANOS for i in (1, 2, 4, 5, 6)]
    out.append(_check("planted_atom_order", stamps == hand,
                      f"expected {hand}, got {stamps}"))
    out.append(_check("planted_cycle_count", int(cycles) == 1,
                      f"one completed TOUCH-ABSORB-REJECT cycle, got {cycles}"))
    klass, done = classify_atoms(atoms, cycles, WITHIN_NS)
    # Precedence P4, P3, P5, P1, P2: no second cycle, no ABSORB inside the run
    # that breached, no return within a minute of the breach, so P1 fires on
    # the completed cycle whose REJECT is 3 s after its own TOUCH.
    out.append(_check("planted_class", klass == P1 and done == hand[2],
                      f"expected {P1} at {hand[2]}, got {klass} at {done}"))
    # The executable-entry law, on BOTH planted completion positions: one
    # strictly inside a bar and one landing exactly on a bar close.  The
    # early-entry mutant must red both checks, and only one position exposes
    # each of them, so both are required.
    lat = np.asarray([BASE_TS + 60 * NANOS * k for k in range(4)], np.int64)
    interior = int(done)                       # 4 s into bar 1
    on_close = int(lat[1])                     # exactly at bar 1's close
    after_completion = True
    after_bar_close = True
    detail: list[str] = []
    for name, stamp in (("interior", interior), ("on_close", on_close)):
        containing = int(np.searchsorted(lat, stamp, side="left"))
        entry_bar = containing + (0 if mutant == MUTANT_EARLY_ENTRY else 1)
        entry_ts = int(lat[entry_bar])
        after_completion &= entry_ts > stamp
        after_bar_close &= entry_ts > int(lat[containing])
        detail.append(f"{name}: completion {stamp}, containing bar "
                      f"{containing} closes {int(lat[containing])}, entry bar "
                      f"{entry_bar} at {entry_ts}")
    out.append(_check("entry_after_completion", after_completion,
                      "; ".join(detail)))
    out.append(_check("entry_after_bar_close", after_bar_close,
                      "; ".join(detail)))
    out.append(_check("planted_side", _sides(P1, PLANT_SIDE) == (-1,),
                      "P1 fades with the defence: side -probe"))
    return out


def _plant_collapse_pair(mutant: str = ""
                         ) -> tuple[dict[str, object], dict[str, object]]:
    """Two tick paths with DIFFERENT atom orders and the SAME minute picture.

    Both spend the bar inside the band with the same open, high, low, close
    regions and the same flow bucket; one absorbs before it rejects and the
    other rejects with no flow fact at all.  A one-minute selector cannot tell
    them apart; the tick tape can.
    """

    def path(with_flow: bool) -> dict[str, object]:
        prices = [985.0, 1002.0, 1004.0, 986.0]
        ts = np.asarray([BASE_TS + i * NANOS for i in range(len(prices))],
                        np.int64)
        tape = (Tape(np.asarray([BASE_TS + 2 * NANOS], np.int64),
                     np.asarray([1004], np.int64),
                     np.asarray([120], np.int64)) if with_flow else EMPTY_TAPE)
        # The minute picture: one bar, open 985 (near side), high 1004 (inside),
        # low 985 (near side), close 986 (near side).  Both paths print it, and
        # both sit in the SAME flow bucket because the twin's bucket is taken
        # at the same trained scale and neither bar's delta clears it.
        opens = np.asarray([985.0])
        highs = np.asarray([1004.0])
        lows = np.asarray([985.0])
        closes = np.asarray([986.0])
        deltas = np.asarray([0.0])
        if mutant == MUTANT_MINUTE_ATOMS:
            atoms, cycles = minute_atoms(
                opens, highs, lows, closes, deltas, np.asarray([0]),
                PLANT_ZONE, PLANT_WIDTH, PLANT_SIDE, PLANT_THRESHOLD)
        else:
            atoms, cycles = tick_atoms(ts, np.asarray(prices, np.float64),
                                       tape, PLANT_ZONE, PLANT_WIDTH,
                                       PLANT_SIDE, PLANT_THRESHOLD)
        signature = minute_signature(
            _regions(opens, PLANT_ZONE, PLANT_WIDTH, PLANT_SIDE),
            _regions(highs, PLANT_ZONE, PLANT_WIDTH, PLANT_SIDE),
            _regions(lows, PLANT_ZONE, PLANT_WIDTH, PLANT_SIDE),
            _regions(closes, PLANT_ZONE, PLANT_WIDTH, PLANT_SIDE),
            np.where(deltas >= FLOW_BUCKET_Q * PLANT_THRESHOLD, 1,
                     np.where(deltas <= -FLOW_BUCKET_Q * PLANT_THRESHOLD,
                              -1, 0)))
        return {"order": order_text(atoms), "signature": signature,
                "cycles": cycles}

    return path(True), path(False)


def _as_event(payload: Mapping[str, object], asset: str = "HG") -> Event:
    event = Event(kind=APPROACH, source=0, asset=asset, d8=20220315,
                  phase="P", cell=0, year=2022, zone_kind="SAME_DAY",
                  zone_price=PLANT_ZONE, width=PLANT_WIDTH,
                  probe_side=PLANT_SIDE, bar0=0, bar1=0, n_bars=1)
    event.order = str(payload["order"])
    event.signature = str(payload["signature"])
    return event


def _selftest_collapse(mutant: str) -> list[tuple[str, bool, str]]:
    out: list[tuple[str, bool, str]] = []
    left, right = _plant_collapse_pair(mutant)
    same_signature = left["signature"] == right["signature"]
    different_order = left["order"] != right["order"]
    out.append(_check("collapse_pair_same_minute_signature", same_signature,
                      f"{left['signature']} vs {right['signature']}"))
    out.append(_check("collapse_pair_different_atom_order", different_order,
                      f"{left['order']} vs {right['order']}"))
    events = [_as_event(left), _as_event(right)]
    report = collapse_flags(events)
    out.append(_check("collapse_pair_fires",
                      all(e.collapsed for e in events)
                      and report["collapsed_events"] == 2,
                      f"collapsed {report['collapsed_events']} of 2, rate "
                      f"{report['collapse_rate']}"))

    # The separable pair: different atom orders AND different minute pictures.
    # The second path CLOSES beyond the far edge, which the minute bar shows.
    separable_right = dict(right)
    separable_right["signature"] = minute_signature(
        _regions(np.asarray([985.0]), PLANT_ZONE, PLANT_WIDTH, PLANT_SIDE),
        _regions(np.asarray([1015.0]), PLANT_ZONE, PLANT_WIDTH, PLANT_SIDE),
        _regions(np.asarray([985.0]), PLANT_ZONE, PLANT_WIDTH, PLANT_SIDE),
        _regions(np.asarray([1015.0]), PLANT_ZONE, PLANT_WIDTH, PLANT_SIDE),
        np.asarray([0]))
    pair = [_as_event(left), _as_event(separable_right)]
    separable = collapse_flags(pair)
    out.append(_check(
        "separable_pair_silent",
        not any(e.collapsed for e in pair)
        and separable["collapsed_events"] == 0
        and left["signature"] != separable_right["signature"]
        and left["order"] != separable_right["order"],
        f"collapsed {separable['collapsed_events']} of 2 with signatures "
        f"{left['signature']!r} vs {separable_right['signature']!r}"))
    return out


def _receipt(nkd: float, si: float, nkd_lo: float, si_lo: float, mdd: float,
             n: int, twin_nkd: float, twin_se: float
             ) -> tuple[dict[str, object], dict[str, object]]:
    """One constructed class receipt plus its twin, for the partition proof."""

    def cash(usd: float, lo: float, se: float = 10.0) -> dict[str, object]:
        return {"usd_per_day": usd, "mean_minus_2se_usd": lo, "se_usd": se,
                "clears_rung": None, "trades": n, "seats_mean": 1.0,
                "zero_entry_fraction": 0.0, "total_usd": usd * 40.0,
                "days": 40, "rung_usd": 1500.0, "seats_max": 1}

    block = {
        "per_asset": {asset: {CLOSE: {"n": n, "over_rung": None,
                                      "coverage": 0.1, "mdd_day_usd": mdd,
                                      "usd_per_asset_day": None}}
                      for asset in ASSETS},
        "cash": {"HG": cash(0.0, 0.0), "NKD": cash(nkd, nkd_lo),
                 "SI": cash(si, si_lo)},
        "mdd": {"max_binding_usd": mdd},
        "stresses": {"adversarial": {"mdd": {"max_binding_usd": mdd}},
                     "spread": {"mdd": {"max_binding_usd": mdd}}}}
    twin = {"cash": {"HG": cash(0.0, 0.0),
                     "NKD": cash(twin_nkd, twin_nkd - 2 * twin_se, twin_se),
                     "SI": cash(twin_nkd, twin_nkd - 2 * twin_se, twin_se)}}
    return block, twin


def _selftest_letters() -> list[tuple[str, bool, str]]:
    out: list[tuple[str, bool, str]] = []
    cases = [
        ("rich", _receipt(2000.0, 1900.0, 1700.0, 1600.0, 400.0, 80,
                          -100.0, 20.0), 0.4, LETTER_RICH),
        ("rich_blocked_by_twin",
         _receipt(2000.0, 1900.0, 1700.0, 1600.0, 400.0, 80, 50.0, 20.0),
         0.4, LETTER_PRESENT),
        ("rich_blocked_by_mdd",
         _receipt(2000.0, 1900.0, 1700.0, 1600.0, 4000.0, 80, -100.0, 20.0),
         0.4, LETTER_PRESENT),
        ("point_only", _receipt(2000.0, 1900.0, 100.0, 90.0, 400.0, 80,
                                -100.0, 20.0), 0.4, LETTER_PRESENT),
        ("one_decider", _receipt(2000.0, 100.0, 1700.0, 50.0, 400.0, 80,
                                 -100.0, 20.0), 0.4, LETTER_PRESENT),
        ("half_rung_no_rung", _receipt(900.0, 800.0, 700.0, 600.0, 400.0, 80,
                                       -100.0, 20.0), 0.4, LETTER_PRESENT),
        ("poor", _receipt(100.0, 50.0, 10.0, 5.0, 400.0, 80, -100.0, 20.0),
         0.4, LETTER_POOR),
        ("unpowered", _receipt(2000.0, 1900.0, 1700.0, 1600.0, 400.0, 5,
                               -100.0, 20.0), 0.4, LETTER_UNPOWERED),
    ]
    seen: set[str] = set()
    for name, (block, twin), collapse, expected in cases:
        got = class_letter(block, twin, collapse)
        seen.add(got["letter"])
        out.append(_check(f"letter_{name}", got["letter"] == expected,
                          f"expected {expected}, got {got['letter']} "
                          f"({'; '.join(got['reasons'])})"))
    out.append(_check("letter_partition_exhaustive",
                      seen == {LETTER_RICH, LETTER_PRESENT, LETTER_POOR,
                               LETTER_UNPOWERED},
                      f"reached {sorted(seen)}"))
    # Exhaustiveness by construction: every branch of ``class_letter`` returns
    # one of the four letters, and the eight receipts above reach all four.
    out.append(_check("letter_precedence_registered",
                      PRECEDENCE == (P4, P3, P5, P1, P2)
                      and set(PRECEDENCE) == set(CLASSES),
                      f"precedence {PRECEDENCE}"))
    return out


def _selftest_twin() -> list[tuple[str, bool, str]]:
    """The twin is a MINUTE reading of the same window, not a second oracle."""

    out: list[tuple[str, bool, str]] = []
    # One bar that opens outside, ranges into the band and closes outside: the
    # twin sees a touch it cannot order against the flow.
    atoms, cycles = minute_atoms(
        np.asarray([985.0, 1002.0]), np.asarray([1004.0, 1004.0]),
        np.asarray([985.0, 986.0]), np.asarray([1002.0, 986.0]),
        np.asarray([120.0, 0.0]), np.asarray([0, 1]),
        PLANT_ZONE, PLANT_WIDTH, PLANT_SIDE, PLANT_THRESHOLD)
    got = tuple(name for name, _ in atoms)
    out.append(_check("twin_minute_atoms", got == (TOUCH, ABSORB, REJECT),
                      f"got {got}"))
    klass, done = classify_atoms(atoms, cycles, WITHIN_BARS)
    out.append(_check("twin_class_within_one_bar", klass == P1 and done == 1,
                      f"got {klass} at {done}"))
    out.append(_check("twin_entry_is_next_bar", done + 1 == 2,
                      "the twin enters at the bar after the completion bar"))
    return out


def _selftest_events() -> list[tuple[str, bool, str]]:
    """The dedupe key and the window law, on hand-built rows."""

    out: list[tuple[str, bool, str]] = []

    class _A:
        def __init__(self, bar, close_bar, n):
            self.asset, self.d8, self.phase, self.cell = "HG", 20220315, "P", 0
            self.year, self.zone_kind = 2022, "SAME_DAY"
            self.zone_price, self.width = PLANT_ZONE, PLANT_WIDTH
            self.approach_side, self.bar = 1, bar
            self.close_bar, self.n_bars = close_bar, n

    class _B:
        def __init__(self, bar, cancel_bar, n):
            self.asset, self.d8, self.phase, self.cell = "HG", 20220315, "P", 0
            self.year, self.zone_kind = 2022, "SAME_DAY"
            self.zone_price, self.width = PLANT_ZONE, PLANT_WIDTH
            self.break_dir, self.bar = 1, bar
            self.cancel_bar, self.n_bars = cancel_bar, n

    # Two approaches at one zone (windows 10-30 and 50-140) and two breaks at
    # the same zone: one inside the second approach's window, one clear of it.
    approaches = [_A(10, 30, 200), _A(50, -1, 200)]
    breaks = [_B(60, 75, 200), _B(160, 175, 200)]
    events, union = build_events(approaches, breaks)
    out.append(_check("union_reproduces_both_universes",
                      len(events) == 4 and union["union_in"] == 4
                      and union["approaches_in"] == 2
                      and union["breaks_in"] == 2,
                      f"got {len(events)} rows from {union['approaches_in']} + "
                      f"{union['breaks_in']}"))
    kept = [e for e in events if not e.overlap_dropped]
    out.append(_check(
        "primary_keeps_every_approach",
        sum(1 for e in kept if e.kind == APPROACH) == 2
        and union["primary_out"] == 3,
        f"primary kept {union['primary_out']} of 4: "
        f"{[(e.kind, e.bar0) for e in kept]}"))
    out.append(_check(
        "primary_drops_only_the_overlapping_break",
        [e.overlap_dropped for e in events if e.kind == BREAK] == [True, False]
        and union["primary_overlap_dropped"] == 1,
        f"break drops {[e.overlap_dropped for e in events if e.kind == BREAK]}"))
    out.append(_check(
        "literal_key_collapses_repeats",
        union["literal_dropped_approach"] == 1
        and union["literal_dropped_break"] == 1
        and union["literal_out"] == 2,
        f"literal dropped {union['literal_dropped_approach']} approach and "
        f"{union['literal_dropped_break']} break rows, leaving "
        f"{union['literal_out']}"))
    approach = [e for e in events if e.kind == APPROACH][0]
    out.append(_check("approach_window_is_resolution",
                      (approach.bar0, approach.bar1) == (10, 30),
                      f"got {(approach.bar0, approach.bar1)}"))
    unresolved = _window_approach(_A(50, -1, 200))
    out.append(_check("unresolved_window_is_parent_horizon",
                      unresolved == (50, 50 + MAX_EPISODE_BARS),
                      f"got {unresolved}"))
    brk = [e for e in events if e.kind == BREAK][0]
    out.append(_check("break_window_is_cancel", (brk.bar0, brk.bar1) == (60, 75),
                      f"got {(brk.bar0, brk.bar1)}"))
    return out


def selftest() -> int:
    mutant = _mutant()
    results: list[tuple[str, bool, str]] = []
    results += _selftest_planted(mutant)
    results += _selftest_collapse(mutant)
    results += _selftest_twin()
    results += _selftest_events()
    results += _selftest_letters()
    print(f"\nSWEEP 26 SELFTEST  mutant={mutant or 'none'}  "
          f"spec {SPEC_SHA[:12]}  code {code_sha()[:12]}")
    failures = 0
    for name, ok, detail in results:
        mark = "ok  " if ok else "FAIL"
        print(f"  [{mark}] {name}" + (f"   {detail}" if not ok else ""))
        if not ok:
            failures += 1
    if mutant:
        expected = set(EXPECTED_RED[mutant])
        red = {name for name, ok, _ in results if not ok}
        exact = red == expected
        print(f"\n  MUTANT ROSTER {mutant}")
        print(f"    must red exactly: {sorted(expected)}")
        print(f"    actually red:     {sorted(red)}")
        print(f"    roster exact:     {exact}")
        if not exact:
            print("    REFUSED: a mutant must red its own named checks and no "
                  "others")
            return 1
        return 0
    print(f"\n  {len(results) - failures} of {len(results)} checks green")
    return 1 if failures else 0


# --------------------------------------------------------------------------
# The log.
# --------------------------------------------------------------------------

def log_rows(report: Mapping[str, object]) -> list[dict[str, object]]:
    params = json.dumps({
        "classes": list(CLASSES), "precedence": list(PRECEDENCE),
        "absorb_q": ABSORB_Q, "within_ns": WITHIN_NS,
        "within_bars": WITHIN_BARS, "labels": list(LABELS),
        "min_class_n": MIN_CLASS_N, "half_rung": HALF_RUNG,
        "portfolio_cap": PORTFOLIO_CAP,
        "universes": {"approaches": EXPECT_APPROACHES,
                      "breaks": EXPECT_BREAKS},
        "dedupe_key": "(asset, day, phase, level_mid2, event_kind)",
        "twin": ("one-minute bars and one-minute flow only, same window, same "
                 "class definitions, within-one-minute read as within one bar"),
        "entry": "next one-minute bar stamp after the class completes",
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
        for name in ("replay_skips", "null_margin", "coverage", "delay_med_s"):
            line[name] = None
        return line

    # 1. every class x label x asset, the sub-minute oracle line
    for klass in CLASSES:
        block = report["classes"][klass]
        letter = report["letters"][klass]
        for label in LABELS:
            for asset in ASSETS:
                counter += 1
                cell = block["per_asset"][asset][label]
                cash = block["cash"][asset]
                rate = report["collapse"]["by_class_asset"].get(
                    f"{klass}|{asset}")
                line = blank(dict(shared))
                line["id"] = f"{LOG_PREFIX}-{counter:03d}"
                line["rule"] = f"{klass}/{label}/{asset}"
                line["days"] = cell["days"]
                line["coverage"] = cell["coverage"]
                tag = asset.lower()
                line[f"{tag}_usd_day"] = cell["usd_per_asset_day"]
                line[f"mdd_{tag}"] = cell["mdd_day_usd"]
                line[f"walls_{tag}"] = cell["wall_rate"]
                line["replay_skips"] = (block["replay"]["rejected_occupancy"]
                                        + block["replay"]["rejected_cap"])
                line["note"] = (
                    f"SUB-MINUTE ORDER CLASS {klass} ({CLASS_NAME[klass]}), "
                    f"label {label}, {asset}: n {cell['n']} of "
                    f"{cell['formed']} formed events, coverage "
                    f"{_show(cell['coverage'])}, mean "
                    f"{_show(cell['mean_cert_usd'])}, P(cert>0) "
                    f"{_show(cell['p_cert_positive']['rate'])}, usd/day "
                    f"{_show(cell['usd_per_asset_day'])} = "
                    f"{_show(cell['over_rung'])} rung; seated replay "
                    f"{_show(cash['usd_per_day'])} usd/day, mean-2SE "
                    f"{_show(cash['mean_minus_2se_usd'])}, clears rung "
                    f"{cash['clears_rung']}; max binding MDD "
                    f"{_show(block['mdd']['max_binding_usd'])} clears "
                    f"{block['mdd']['clears']}; collapse rate {_show(rate)}; "
                    f"entry at the NEXT one-minute bar after completion; "
                    f"letter {letter['letter']}; NO LAW CHANGES FROM THIS UNIT")
                rows.append(line)

    # 2. every class x asset, the MINUTE-COARSENED TWIN beside it
    for klass in CLASSES:
        twin = report["twins"][klass]
        block = report["classes"][klass]
        sep = report["separation"][klass]
        for asset in ASSETS:
            counter += 1
            cell = twin["per_asset"][asset][CLOSE]
            cash = twin["cash"][asset]
            own = block["cash"][asset]
            line = blank(dict(shared))
            line["id"] = f"{LOG_PREFIX}-{counter:03d}"
            line["rule"] = f"{klass}/TWIN/{asset}"
            line["days"] = cell["days"]
            line["coverage"] = cell["coverage"]
            tag = asset.lower()
            line[f"{tag}_usd_day"] = cell["usd_per_asset_day"]
            line[f"mdd_{tag}"] = cell["mdd_day_usd"]
            line[f"walls_{tag}"] = cell["wall_rate"]
            line["note"] = (
                f"MINUTE-COARSENED TWIN of {klass}, {asset}: the same selector "
                f"re-expressed on one-minute bars and one-minute flow over the "
                f"same window; n {cell['n']}, usd/day "
                f"{_show(cash['usd_per_day'])} = {_show(cell['over_rung'])} "
                f"rung, mean-2SE {_show(cash['mean_minus_2se_usd'])}, upper 95 "
                f"{_show(upper95(twin['cash'], asset))}, MDD "
                f"{_show(twin['mdd']['max_binding_usd'])}; the sub-minute line "
                f"is {_show(own['usd_per_day'])} usd/day; separation on this "
                f"asset {sep['by_asset'][asset]} events of "
                f"{sep['tick_n']} tick / {sep['twin_n']} twin")
            rows.append(line)

    # 3. the collapse receipt
    collapse = report["collapse"]
    for klass in CLASSES:
        counter += 1
        line = blank(dict(shared))
        line["id"] = f"{LOG_PREFIX}-{counter:03d}"
        line["rule"] = f"{klass}/collapse"
        line["days"] = len(report["scoring_days"]["NKD"])
        line["null_margin"] = collapse["by_class"].get(klass)
        sep = report["separation"][klass]
        line["note"] = (
            f"COLLAPSE RECEIPT {klass}: share of events whose MINUTE signature "
            f"group carries more than one tick atom order = "
            f"{_show(collapse['by_class'].get(klass))}; per asset "
            + ", ".join(
                f"{a} {_show(collapse['by_class_asset'].get(f'{klass}|{a}'))}"
                for a in ASSETS)
            + f"; separation n {sep['separation_n']} "
              f"(tick {sep['tick_n']}, twin {sep['twin_n']}, both "
              f"{sep['both']})")
        rows.append(line)

    # 4. the stresses on the best class
    best = str(report["best_class"])
    detail = report["best_detail"]["class"]
    for kind, stress in sorted(detail.get("stresses", {}).items()):
        counter += 1
        line = blank(dict(shared))
        line["id"] = f"{LOG_PREFIX}-{counter:03d}"
        line["rule"] = f"{best}/stress/{kind}"
        line["days"] = len(report["scoring_days"]["NKD"])
        for asset in ASSETS:
            line[f"{asset.lower()}_usd_day"] = stress["cash"][asset][
                "usd_per_day"]
            line[f"mdd_{asset.lower()}"] = stress["mdd"].get(f"{asset}|day")
        line["note"] = (
            f"STRESS {kind} on the best class {best}: seated "
            f"{stress['seated']}, " + ", ".join(
                f"{a} {_show(stress['cash'][a]['usd_per_day'])} usd/day"
                for a in ASSETS)
            + f"; max binding MDD "
              f"{_show(stress['mdd']['max_binding_usd'])} clears "
              f"{stress['mdd']['clears']}")
        rows.append(line)

    # 5. the family decision
    counter += 1
    head = report["headline"]
    line = blank(dict(shared))
    line["id"] = f"{LOG_PREFIX}-{counter:03d}"
    line["rule"] = f"FAMILY/{report['family_letter']}"
    line["days"] = len(report["scoring_days"]["NKD"])
    for asset in ASSETS:
        line[f"{asset.lower()}_usd_day"] = detail["cash"][asset]["usd_per_day"]
        line[f"mdd_{asset.lower()}"] = detail["mdd"].get(f"{asset}|day")
    line["null_margin"] = report["collapse"]["collapse_rate"]
    line["note"] = (
        f"FAMILY LETTER {report['family_letter']}, best class {best}: NKD "
        f"{_show(head['over_rung']['NKD'])}x and SI "
        f"{_show(head['over_rung']['SI'])}x of rung, minute twin NKD "
        f"{_show(head['twin_over_rung']['NKD'])}x and SI "
        f"{_show(head['twin_over_rung']['SI'])}x, collapse rate "
        f"{_show(head['collapse_rate_best_class'])} for the class and "
        f"{_show(head['collapse_rate'])} over all events; universes "
        f"{EXPECT_APPROACHES} approaches + {EXPECT_BREAKS} breaks -> "
        f"{report['union']['primary_out']} events under the PRIMARY "
        f"overlap dedupe; clause order {', '.join(CLAUSE_ORDER)}; EXPLORE-only, "
        f"kill-only, outcome-only raw-tick oracle with NO PROMOTION AUTHORITY; "
        f"THIS UNIT CHANGES NO LAW and the grain law stands")
    rows.append(line)

    # 6. the dedupe sensitivity: the same letter under the literal key
    counter += 1
    agree = report["dedupe_agreement"]
    other = report["dedupe_readings"]["LITERAL"]
    detail2 = other["classes"][other["best_class"]]
    line = blank(dict(shared))
    line["id"] = f"{LOG_PREFIX}-{counter:03d}"
    line["rule"] = f"DEDUPE_SENSITIVITY/{agree['literal_letter']}"
    line["days"] = len(report["scoring_days"]["NKD"])
    for asset in ASSETS:
        line[f"{asset.lower()}_usd_day"] = detail2["cash"][asset]["usd_per_day"]
        line[f"mdd_{asset.lower()}"] = detail2["mdd"].get(f"{asset}|day")
    line["null_margin"] = other["collapse"]["collapse_rate"]
    line["note"] = (
        f"DEDUPE SENSITIVITY: under the LITERAL whole-union key "
        f"{report['union']['literal_key']} the union falls to "
        f"{agree['literal_events']} events (it deletes "
        f"{report['union']['literal_dropped_approach']} of "
        f"{EXPECT_APPROACHES} approaches the same instruction orders "
        f"reproduced) and the family letter is {agree['literal_letter']} with "
        f"best class {agree['literal_best']}; the PRIMARY overlap dedupe gives "
        f"{agree['primary_letter']} on {agree['primary_events']} events; the "
        f"two readings agree: {agree['letters_agree']}")
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
    print_atoms(report)
    print_causality(report)
    print_classes(report)
    print_collapse(report)
    print_best(report)
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
