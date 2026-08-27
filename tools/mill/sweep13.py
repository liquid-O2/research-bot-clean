#!/usr/bin/env python3
"""Sweep 13 of the side-resolution mill: the ordinal-2 candidate ablation.

Exploratory tier.  EXPLORE-day bytes only, can kill, cannot promote.  The unit
changes exactly one thing against sweep 8: the action operator downstream of the
frozen ``PRIMARY`` fire.  ``FIRST`` is sweep 8's own resolver, imported and
re-run, never re-implemented; ``SECOND`` takes the same fire and requires one
more distinct, observable candidate occurrence before it spends the cell.

The brief is ``.audit/briefs/mill-rootcause-sol-out.md`` section "C. The first
build".  Its diagnosis is ``argfirst``: every executable policy in 425 logged
trials took the first observation that cleared a local predicate, and the
occurrence ordinal has never once been policy state.  This file varies only that
operator.

Machinery is imported, never re-implemented: sweep 8's ``build_cells``,
``run_gate``, ``resolve``, ``entry_after``, ``_finish``, ``depth_atr``,
``horizon_table`` and its miss vocabulary; sweep 7a's zone geometry and CLEAR
candidate plane; sweep 2's ``star_cell``; sweep 1's ``make_entry``,
``cash_line``, ``asset_mdd_day``/``asset_mdd_trade``, ``replay_line``,
``block_null``, ``wilson`` and ``append_log``; sweep 3's ``stress_line``; the
mill substrate for the CLEAR candidate identities the ordinal is counted over.
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
import sweep1 as S1
import sweep2 as S2
import sweep3 as S3
import sweep7a as S7A
import sweep8 as S8

# --------------------------------------------------------------------------
# The law, registered before anything is read.
# --------------------------------------------------------------------------

SPEC = """QRE2MILLSWEEP13
tier=exploratory; explore-only; can kill, cannot promote.  parent = sweep11-004.
  Brief: .audit/briefs/mill-rootcause-sol-out.md section "C. The first build",
  followed verbatim.  No new score, fitted model, union or feature grid.  One
  knob moves against sweep 8: the occurrence ordinal at which the cell is spent.
FROZEN INPUTS.  EXPLORE only; the existing sweep-8 candidate, context and
  evidence caches; split sha b6d2decb1f3d6495e003a1a29a229195f4d4c1bdc0134d419
  5a1cc2c1c38f08f; outcome-law sha 64df3f7006ae02445de56f13ddd1f563a0db50f96eae
  c60e6a7a760e9901a720; seed 20260827.  HOLD, 2021, 2025, teacher stores, late
  labels and cash stay closed during stage A.
FIRST is the exact sweep-8 PRIMARY resolver, re-run here through sweep 8's own
  build_cells/run_gate/resolve.  G, its walk-forward 60th percentile, the 1800 s
  remaining-time floor at the fire, two-lane monitoring and the cancellation law
  are untouched.  The unit REFUSES to run stage A unless FIRST reproduces entry
  counts 118/111/121 and entry-stamp postX_1800 0.458/0.432/0.408 for HG/NKD/SI,
  denominators 118/111/120 (one SI entry is censored), and unless the per-cell
  fire threshold recovered from the frozen crossing counts reproduces sweep 8's
  PRIMARY shot in EVERY scored cell.
SECOND uses the same fire.  Inside 900 s of the fire it counts legal same-side
  CLEAR candidates whose decision quote sits within 0.15*ATR14_prev of the
  RUNNING extreme.  An occurrence counts only when the live keep-first candidate
  identity at that bar is new and its decision timestamp is strictly later than
  the previous occurrence's.  Identity is the newest same-side CLEAR candidate
  formed at or before the bar's own decision stamp, ties folded keep-first by
  (decision_ts_ns, candidate_id) - the mill's own cell ordering.  Occurrence one
  is therefore exactly the bar sweep-8 PRIMARY enters.  The ordinal-2 occurrence
  is entered at its own decision timestamp and must carry at least 1800 s of
  remaining phase time, the frozen time floor read at the entry rather than the
  fire; a shorter one voids the fire instead of being entered late.
RESET.  A new same-direction extreme resets the ordinal to zero and VOIDS the
  pending fire.  The resolver continues only from a later frozen G fire, which
  by the quiet-age law cannot land until the new extreme is itself 5 bars old.
  The existing opposite-extreme cancel is preserved over (fire, entry].  The
  first surviving ordinal-2 entry spends the cell; one entry per cell and the
  portfolio cap are unchanged.
TIME-MATCH draws legal candidate occurrences - same depth band, same 1800 s
  floor, either side - from a DIFFERENT asset-day, matching asset and phase
  exactly and both phase-elapsed and phase-remaining within 300 s of each SECOND
  entry.  200 draws at seed 20260827.  It prices the benefit of being late
  without giving credit to ordinal two.
STAGE A, no cash, by asset and by phase, HG report-only for the ruling: scored
  cells, fired cells, first- and second-occurrence availability, entries and
  cell coverage; duplicate identities, equal-timestamp candidates, same-side
  resets, opposite-side cancels, no-second-candidate misses and deadline misses;
  entry-stamp postX_1800 for FIRST, SECOND and TIME-MATCH; paired SECOND-FIRST
  and SECOND-TIME-MATCH differences by asset-day with block 95% intervals;
  first-to-second wait median and p90, phase time remaining, candidate ordinal
  and favourable quote change in ATR; terminal lead/lag as a diagnostic only.
  Asset-day block sign flips, 10000 draws, seed 20260827, max statistic across
  NKD/SI and both comparisons; the 95% interval is the paired asset-day block
  bootstrap at the same seed and draws.
RULING, pre-registered.  ORDINAL-SURVIVES needs all six on BOTH NKD and SI:
  (1) coverage >= 0.35; (2) SECOND postX_1800 <= 0.25; (3) SECOND beats FIRST by
  >= 0.10 and TIME-MATCH by >= 0.05; (4) each paired difference's 95% upper
  bound < 0 and max-adjusted p <= 0.05; (5) added first-to-second wait p90
  <= 900 s; (6) identity duplicates zero after keep-first dedup, every entry
  with >= 1800 s remaining, TIME-MATCH matching >= 90% of SECOND entries, and
  zero replay cap skips.  ORDINAL-ASSET-SCOPED if exactly one deciding asset
  passes every bound and the other's SECOND-FIRST point estimate is non-positive
  - price only the passing asset.  ORDINAL-KILL if neither passes or either
  asset worsens postX_1800 by >= 0.05.  No ordinal three, no zone change, no
  persistence in this unit.
ONE GATED PRICE READ, only under SURVIVES or ASSET-SCOPED, only for passing
  assets: exact chronological replay, cash against the asset-day rung, both MDD
  orderings below 1000, the existing 2% adverse stress positive, adjusted null
  p <= 0.05 and zero occupancy-or-cap skips.  It still cannot promote.
MUTANTS.  QRE2_MILL_S13_MUTANT=ordinal_kept_across_reset keeps the ordinal alive
  across a same-side new extreme; =future_cert_peek picks the occurrence with the
  largest future cert dollars instead of the second.  Both must turn the selftest
  red.
"""

ASSETS = S1.ASSETS
DECIDING = ("NKD", "SI")            # HG is reported, never deciding
BAR_SECONDS = S1.BAR_SECONDS
SEED = S1.SEED
NULL_DRAWS = S1.NULL_DRAWS
DAY_RUNG_USD = S1.DAY_RUNG_USD
MDD_CEILING = S1.MDD_CAP_USD
STRESS_RATE = S3.STRESS_RATE

# Everything below is inherited from sweep 8's frozen law, aliased so a drift
# there fails loudly here instead of silently diverging.
DEPTH_ATR = S8.DEPTH_ATR                 # 0.15
REMAIN_MIN_S = S8.REMAIN_MIN_S           # 1800
HORIZON_BARS = S8.HORIZON_BARS           # 30 bars of 60 s

# The one new law: the ordinal, and the window the occurrences are counted in.
ORDINAL = 2
OCC_WINDOW_S = 900
OCC_WINDOW_BARS = OCC_WINDOW_S // BAR_SECONDS      # 15

TIME_MATCH_DRAWS = 200
TIME_MATCH_WINDOW_S = 300
BLOCK_DRAWS = 10_000

# The pre-registered stage-A bounds.
COVERAGE_FLOOR = 0.35
POSTX_CEILING = 0.25
GAIN_OVER_FIRST = 0.10
GAIN_OVER_TIME_MATCH = 0.05
ADJUSTED_P_CEILING = 0.05
WAIT_P90_CEILING = 900.0
TIME_MATCH_COVER_FLOOR = 0.90
WORSEN_KILL = 0.05
NULL_CEILING = 0.05

# The refuse-to-run gate.  These are sweep 8's published PRIMARY numbers and the
# unit does not proceed past them on any mismatch.
REPRO_ENTRIES = {"HG": 118, "NKD": 111, "SI": 121}
REPRO_POSTX_N = {"HG": 118, "NKD": 111, "SI": 120}
REPRO_POSTX_RATE = {"HG": 0.458, "NKD": 0.432, "SI": 0.408}
REPRO_RATE_TOL = 0.001              # the brief quotes the rates to 3 decimals

MISS_UNSCORED = S8.MISS_UNSCORED
MISS_NO_FIRE = S8.MISS_NO_FIRE
MISS_CANCELLED = S8.MISS_CANCELLED
MISS_NO_FIRST = "no_first_occurrence"
MISS_NO_SECOND = "no_second_occurrence"
MISS_DEADLINE = "deadline"
MISS_RESET = "same_side_reset"
MISS_REMAIN = "remain_floor"
MISS_BRANCHES = (MISS_UNSCORED, MISS_NO_FIRE, MISS_NO_FIRST, MISS_NO_SECOND,
                 MISS_DEADLINE, MISS_RESET, MISS_REMAIN, MISS_CANCELLED)

LINES = ("FIRST", "SECOND")

OUT_PATH = ROOT / ".audit/mill-sweep13.json"
LOG_PATH = S1.LOG_PATH

MUTANT_ENV = "QRE2_MILL_S13_MUTANT"
MUTANT_KEEP = "ordinal_kept_across_reset"
MUTANT_PEEK = "future_cert_peek"
MUTANTS = (MUTANT_KEEP, MUTANT_PEEK)

FAMILY = "F10-ORDINAL"
PARENT_TRIAL = "sweep11-004"
SELECTION_RULE = "none: frozen sweep-8 PRIMARY fire, pre-registered ordinal law"


class SweepRefusal(RuntimeError):
    pass


SPEC_SHA = S1._sha_text(SPEC)


def code_sha() -> str:
    return S1._sha_file(Path(__file__).resolve())


def _mutant() -> str:
    name = os.environ.get(MUTANT_ENV, "")
    if name and name not in MUTANTS:
        raise SweepRefusal(f"unknown sweep-13 mutant: {name}")
    return name


def _rate(hits: int, total: int) -> dict[str, object]:
    low, high = S1.wilson(int(hits), int(total))
    return {"hits": int(hits), "n": int(total),
            "rate": (hits / total) if total else None,
            "ci_low": low if total else None, "ci_high": high if total else None}


def _q(values: Sequence[float], mark: float) -> float | None:
    array = np.asarray([float(v) for v in values], np.float64)
    return float(np.percentile(array, mark)) if len(array) else None


# --------------------------------------------------------------------------
# The candidate identity plane.
# --------------------------------------------------------------------------

@dataclass(slots=True)
class Ident:
    """Per bar, the live keep-first CLEAR candidate on one side of one cell.

    ``name`` is the substrate ``candidate_id`` of the NEWEST same-side CLEAR
    candidate whose decision stamp is at or before the bar's own decision stamp,
    with same-stamp arrivals folded keep-first under the mill's own cell
    ordering ``(decision_ts_ns, candidate_id)``.  That is what makes one
    occurrence distinct from the next: a new name has arrived and is live.  Two
    consecutive bars holding the same live name are ONE occurrence, which is the
    whole reason the ordinal is not simply "the next bar".
    """

    name: np.ndarray            # object array of ids, "" before the first
    decision_ts: np.ndarray     # int64 ns, -1 before the first
    arrivals: int               # distinct decision stamps on this side
    equal_ts_folded: int        # arrivals dropped by the keep-first fold


def _ident_from_rows(lat: np.ndarray, stamps: np.ndarray, names: Sequence[str]
                     ) -> Ident:
    """``Ident`` from one side's ``(decision stamp, candidate id)`` arrivals."""

    order = sorted(range(len(names)), key=lambda i: (int(stamps[i]), names[i]))
    kept_ts: list[int] = []
    kept_name: list[str] = []
    folded = 0
    for position in order:
        stamp = int(stamps[position])
        if kept_ts and stamp == kept_ts[-1]:
            # Same decision stamp as the standing arrival: keep-first wins and
            # the later id is not a new occurrence.
            folded += 1
            continue
        kept_ts.append(stamp)
        kept_name.append(str(names[position]))
    bars = len(lat)
    out_name = np.full(bars, "", dtype=object)
    out_ts = np.full(bars, -1, dtype=np.int64)
    if kept_ts:
        marks = np.asarray(kept_ts, np.int64)
        slot = np.searchsorted(marks, np.asarray(lat, np.int64), side="right") - 1
        live = slot >= 0
        picks = slot[live]
        out_ts[live] = marks[picks]
        out_name[live] = np.asarray(kept_name, dtype=object)[picks]
    return Ident(out_name, out_ts, len(kept_ts), folded)


def build_identities(cells: Sequence[S8.Cell8], explore_days: Mapping[str, list[int]]
                     ) -> dict[int, dict[int, Ident]]:
    """One ``Ident`` per (cell, side), read from the frozen EXPLORE substrate."""

    wanted: dict[tuple[str, int], list[S8.Cell8]] = {}
    for cell in cells:
        wanted.setdefault((cell.asset, cell.d8), []).append(cell)
    allowed = {(asset, int(day)) for asset, days in explore_days.items()
               for day in days}
    out: dict[int, dict[int, Ident]] = {}
    for key in sorted(wanted):
        if key not in allowed:
            raise SweepRefusal(f"substrate day outside the EXPLORE split: {key}")
        shard = M.load_shard(key[0], key[1])
        try:
            for cell in wanted[key]:
                source = shard.cell(cell.phase, int(cell.rec.phase_open_ts_ns))
                rows = np.asarray(source.rows, np.int64)
                sides = shard.side[rows]
                stamps = shard.decision_ts_ns[rows].astype(np.int64)
                book: dict[int, Ident] = {}
                for side in (1, -1):
                    pick = np.flatnonzero(sides == side)
                    book[side] = _ident_from_rows(
                        cell.rec.lat, stamps[pick],
                        [shard.candidate_ids[int(rows[i])] for i in pick])
                out[cell.position] = book
        finally:
            shard.close()
    return out


# --------------------------------------------------------------------------
# The frozen fire stream, recovered from sweep 8's own run.
# --------------------------------------------------------------------------

def derived_threshold(scored: Sequence[tuple[int, int, float, float]],
                      crossed: int) -> float | None:
    """The fire bar that reproduces sweep 8's crossing count in this cell.

    ``run_gate`` does not publish the stratum threshold, only how many scored
    rows cleared it.  Any value inside the gap between the ``crossed``-th and
    ``crossed+1``-th largest G fires exactly the same rows, so the ``crossed``-th
    largest value is behaviourally identical to the real bar - and the
    reproduction gate proves it by re-resolving every scored cell with it.
    """

    if crossed <= 0:
        return None
    values = sorted((float(row[2]) for row in scored
                     if np.isfinite(float(row[2]))), reverse=True)
    if crossed > len(values):
        return None
    return float(values[crossed - 1])


@dataclass(slots=True)
class Recorded:
    """What the frozen sweep-8 pass did, keyed by CELL, not by its tag.

    ``run_gate`` publishes its scored pool and crossing counts under
    ``asset/d8/phase``, and 17 EXPLORE asset-days carry two phase-0 cell
    instances, so that key silently aliases one cell onto another.  The shots it
    returns are a complete list, so sweep 8's own totals are unharmed - but an
    ordinal policy has to walk the SAME cell the fire came from.  These two
    shims observe the frozen functions in place (they call straight through and
    change nothing) and file the result under ``cell.position``.
    """

    scored: dict[int, list[tuple[int, int, float, float]]] = field(
        default_factory=dict)
    threshold: dict[int, float] = field(default_factory=dict)


def record_gate(cells: Sequence[S8.Cell8]) -> tuple[S8.GateRun, Recorded]:
    """Run sweep 8's own gate, recording each cell's scored list and fire bar."""

    book = Recorded()
    real_score, real_resolve = S8.score_cell, S8.resolve

    def score_cell(cell: S8.Cell8, stratum: S8.Stratum):
        scored = real_score(cell, stratum)
        book.scored[cell.position] = scored
        return scored

    def resolve(cell: S8.Cell8, scored, threshold: float, depth_law: bool, *,
                column: int = 2):
        if column == 2:
            book.threshold.setdefault(cell.position, float(threshold))
        return real_resolve(cell, scored, threshold, depth_law, column=column)

    S8.score_cell, S8.resolve = score_cell, resolve
    try:
        run = S8.run_gate(cells)
    finally:
        S8.score_cell, S8.resolve = real_score, real_resolve
    return run, book


def reproduce_first(cells: Sequence[S8.Cell8], run: S8.GateRun, book: Recorded
                    ) -> dict[str, object]:
    """The refuse-to-run gate; every frozen PRIMARY shot must come back exact."""

    by_position = {cell.position: cell for cell in cells}
    shots = {int(row.cell): row for row in run.shots["PRIMARY"]}
    checked = 0
    recovered_ok = 0
    mismatches: list[str] = []
    for position, threshold in sorted(book.threshold.items()):
        cell = by_position[position]
        scored = book.scored[position]
        tag = f"{cell.asset}/{cell.d8}/{cell.phase}@{cell.rec.phase_open_ts_ns}"
        replay, _miss = S8.resolve(cell, scored, threshold, depth_law=True)
        frozen = shots.get(position)
        checked += 1
        # Cross-check the published crossing count against the true bar: the
        # count is the only fire evidence sweep 8 writes to its own receipt.
        crossed = sum(1 for row in scored if float(row[2]) >= threshold)
        guess = derived_threshold(scored, crossed)
        if guess is None or sum(1 for row in scored
                                if float(row[2]) >= guess) == crossed:
            recovered_ok += 1
        else:
            mismatches.append(f"{tag}: recovered fire bar changes the fire set")
        if frozen is None:
            if replay is not None:
                mismatches.append(f"{tag}: replay entered where sweep 8 missed")
            continue
        if replay is None:
            mismatches.append(f"{tag}: replay missed where sweep 8 entered")
        elif (replay.side, replay.fire_bar, replay.entry_bar) != (
                frozen.side, frozen.fire_bar, frozen.entry_bar):
            mismatches.append(
                f"{tag}: ({replay.side},{replay.fire_bar},{replay.entry_bar}) != "
                f"({frozen.side},{frozen.fire_bar},{frozen.entry_bar})")
    unscored_entries = sorted(position for position in shots
                              if position not in book.threshold)
    for position in unscored_entries:
        mismatches.append(f"cell {position}: sweep 8 entered an unscored cell")
    scored_by_asset: dict[str, int] = {asset: 0 for asset in ASSETS}
    for position in book.threshold:
        scored_by_asset[by_position[position].asset] += 1
    for asset in ASSETS:
        if scored_by_asset[asset] != int(run.scored_cells.get(asset, 0)):
            mismatches.append(
                f"{asset}: scored cells {scored_by_asset[asset]} != "
                f"{run.scored_cells.get(asset)}")
    horizons = {asset: S8.horizon_table(
        [row for row in run.shots["PRIMARY"] if row.asset == asset])
        for asset in ASSETS}
    checks: list[dict[str, object]] = []
    for asset in ASSETS:
        entries = int(horizons[asset]["n"])
        block = horizons[asset]["postx1800_entry"]
        rate = block["rate"]
        checks.append({
            "asset": asset, "entries": entries,
            "entries_expected": REPRO_ENTRIES[asset],
            "entries_ok": entries == REPRO_ENTRIES[asset],
            "postx_n": int(block["n"]), "postx_n_expected": REPRO_POSTX_N[asset],
            "postx_n_ok": int(block["n"]) == REPRO_POSTX_N[asset],
            "postx_rate": rate, "postx_rate_expected": REPRO_POSTX_RATE[asset],
            "postx_rate_ok": rate is not None and abs(
                float(rate) - REPRO_POSTX_RATE[asset]) <= REPRO_RATE_TOL,
        })
    return {
        "checks": checks, "cells_rechecked": checked,
        "cells_scored": scored_by_asset,
        "crossing_count_recovers_fire_set": recovered_ok,
        "threshold_mismatches": mismatches[:20],
        "threshold_mismatch_count": len(mismatches),
        "verdict": "PASS" if (not mismatches and all(
            row["entries_ok"] and row["postx_n_ok"] and row["postx_rate_ok"]
            for row in checks)) else "FAIL",
    }


# --------------------------------------------------------------------------
# The ordinal-2 resolver.
# --------------------------------------------------------------------------

@dataclass(slots=True)
class Occurrence:
    ordinal: int
    bar: int
    name: str
    decision_ts: int
    depth: float


@dataclass(slots=True)
class Counters:
    fires: int = 0
    resets: int = 0
    cancels: int = 0
    identity_repeats: int = 0
    duplicates_after_dedup: int = 0
    equal_ts_skips: int = 0
    remain_drops: int = 0
    no_first: int = 0
    no_second: int = 0
    deadline: int = 0
    first_seen: int = 0          # fires whose walk reached occurrence one
    second_seen: int = 0         # fires whose walk reached occurrence two

    def add(self, other: "Counters") -> None:
        for name in self.__slots__:  # type: ignore[attr-defined]
            setattr(self, name, getattr(self, name) + getattr(other, name))


@dataclass(slots=True)
class Walk:
    occurrences: list[Occurrence]
    branch: str
    entry: Occurrence | None
    counters: Counters
    truncated: bool


def walk_from_fire(cell: S8.Cell8, side: int, fire_bar: int, ident: Ident,
                   mutant: str | None = None,
                   cands: frozenset[int] | None = None) -> Walk:
    """The ordered occurrence stream after one fire, and what it resolves to."""

    if mutant is None:
        mutant = _mutant()
    counters = Counters(fires=1)
    prior, new_ext, _armed = S7A.side_arrays(cell.geo, side)
    if cands is None:
        cands = frozenset(int(bar) for bar
                          in S7A.candidate_bars(cell.rec, side))
    remaining = cell.sides[side].remaining_s
    limit = int(fire_bar) + OCC_WINDOW_BARS
    truncated = limit > cell.n - 1
    stop = min(limit, cell.n - 1)
    occurrences: list[Occurrence] = []
    seen: set[str] = set()
    entry: Occurrence | None = None
    for bar in range(int(fire_bar), stop + 1):
        if bar > int(fire_bar) and bool(new_ext[bar]):
            # A new same-direction extreme: the episode the fire belongs to is
            # over.  The ordinal resets to zero and the pending fire is void.
            counters.resets += 1
            if mutant != MUTANT_KEEP:
                return Walk(occurrences, MISS_RESET, None, counters, truncated)
        if bar not in cands:
            continue
        reach = S8.depth_atr(float(cell.rec.mid[bar]), float(prior[bar]),
                             cell.atr_mid2)
        if reach > DEPTH_ATR:
            continue
        name = str(ident.name[bar])
        stamp = int(ident.decision_ts[bar])
        if not name:
            continue
        if name in seen:
            # The same live candidate sampled again: not a new occurrence.
            counters.identity_repeats += 1
            continue
        if occurrences and stamp <= occurrences[-1].decision_ts:
            counters.equal_ts_skips += 1
            continue
        occurrences.append(Occurrence(len(occurrences) + 1, bar, name, stamp,
                                      reach))
        seen.add(name)
        if len(occurrences) == ORDINAL and mutant != MUTANT_PEEK:
            entry = occurrences[-1]
            break
    if mutant == MUTANT_PEEK and len(occurrences) >= ORDINAL:
        # The peek mutant spends the cell on the occurrence that pays best,
        # which is a label no live policy can read.
        certs = cell.rec.cert(side)
        entry = max(occurrences, key=lambda row: float(certs[row.bar]))
    counters.first_seen = int(bool(occurrences))
    counters.second_seen = int(len(occurrences) >= ORDINAL)
    counters.duplicates_after_dedup = len(occurrences) - len(
        {row.name for row in occurrences})
    if entry is None:
        if not occurrences:
            branch = MISS_DEADLINE if truncated else MISS_NO_FIRST
            counters.no_first += 1
        else:
            branch = MISS_DEADLINE if truncated else MISS_NO_SECOND
            counters.no_second += 1
        if truncated:
            counters.deadline += 1
        return Walk(occurrences, branch, None, counters, truncated)
    if float(remaining[entry.bar]) < REMAIN_MIN_S:
        # The frozen 1800 s floor, read at the entry.  Entering later than the
        # floor allows would buy a better postX_1800 with censoring.
        counters.remain_drops += 1
        return Walk(occurrences, MISS_REMAIN, None, counters, truncated)
    _oprior, opp_new, _oarmed = S7A.side_arrays(cell.geo, -side)
    if bool(np.any(opp_new[int(fire_bar) + 1: entry.bar + 1])):
        counters.cancels += 1
        return Walk(occurrences, MISS_CANCELLED, None, counters, truncated)
    return Walk(occurrences, "", entry, counters, truncated)


@dataclass(slots=True)
class Take:
    """One ordinal-2 entry, its sweep-8 shot and the ordinal diagnostics."""

    shot: S8.Shot8
    first_bar: int
    first_name: str
    second_name: str
    added_wait_s: int
    favorable_atr: float
    remaining_s: float
    ordinal: int


def second_resolve(cell: S8.Cell8, scored: Sequence[tuple[int, int, float, float]],
                   threshold: float, idents: Mapping[int, Ident],
                   mutant: str | None = None
                   ) -> tuple[Take | None, str, Counters]:
    """The first fire whose ordinal-2 occurrence survives every law."""

    counters = Counters()
    miss = MISS_NO_FIRE
    cands = {side: frozenset(int(bar) for bar
                             in S7A.candidate_bars(cell.rec, side))
             for side in (1, -1)}
    for row in scored:
        side, bar, value = int(row[0]), int(row[1]), float(row[2])
        if not np.isfinite(value) or value < threshold:
            continue
        walk = walk_from_fire(cell, side, bar, idents[side], mutant,
                              cands[side])
        counters.add(walk.counters)
        if walk.branch or walk.entry is None:
            miss = walk.branch
            continue
        entry = walk.entry
        first = walk.occurrences[0]
        shot = S8._finish(cell, side, bar, entry.bar, value, entry.depth)
        # Favourable means the quote moved DEEPER into the fade between the two
        # occurrences: side +1 fades a low, so a lower mid is the better entry.
        moved = -float(side) * (float(cell.rec.mid[entry.bar])
                                - float(cell.rec.mid[first.bar]))
        take = Take(
            shot=shot, first_bar=first.bar, first_name=first.name,
            second_name=entry.name,
            added_wait_s=int((entry.bar - first.bar) * BAR_SECONDS),
            favorable_atr=(moved / cell.atr_mid2) if cell.atr_mid2 > 0.0 else 0.0,
            remaining_s=float(cell.sides[side].remaining_s[entry.bar]),
            ordinal=entry.ordinal)
        return take, "", counters
    return None, miss, counters


@dataclass(slots=True)
class OrdinalRun:
    """Everything the ordinal pass produced, keyed by ``cell.position``."""

    takes: list[Take] = field(default_factory=list)
    misses: dict[int, str] = field(default_factory=dict)
    counters: dict[int, Counters] = field(default_factory=dict)
    fired_cells: dict[int, int] = field(default_factory=dict)
    first_cells: dict[int, int] = field(default_factory=dict)
    second_cells: dict[int, int] = field(default_factory=dict)


def run_second(cells: Sequence[S8.Cell8], book: Recorded,
               idents: Mapping[int, dict[int, Ident]],
               mutant: str | None = None) -> OrdinalRun:
    out = OrdinalRun()
    for cell in cells:
        position = cell.position
        if position not in book.threshold:
            out.misses[position] = MISS_UNSCORED
            continue
        take, miss, counters = second_resolve(
            cell, book.scored[position], book.threshold[position],
            idents[position], mutant)
        out.counters[position] = counters
        out.fired_cells[position] = 1 if counters.fires else 0
        out.first_cells[position] = 1 if counters.first_seen else 0
        out.second_cells[position] = 1 if counters.second_seen else 0
        if take is None:
            out.misses[position] = miss
        else:
            out.takes.append(take)
    return out


# --------------------------------------------------------------------------
# The TIME-MATCH control.
# --------------------------------------------------------------------------

@dataclass(slots=True)
class Donor:
    asset: str
    phase: str
    d8: int
    elapsed_s: int
    remaining_s: int
    postx: bool
    full: bool


def _postx_arrays(cell: S8.Cell8, side: int) -> tuple[np.ndarray, np.ndarray]:
    """``(extended within 1800 s, full window observable)`` for every bar.

    The same object ``_finish`` stamps one bar at a time, vectorised so the
    donor pool can be built without a Python loop over every bar.
    """

    _prior, new_ext, _armed = S7A.side_arrays(cell.geo, side)
    order = np.arange(cell.n, dtype=np.int64)
    cumulative = np.concatenate(([0], np.cumsum(np.asarray(new_ext, np.int64))))
    stop = np.minimum(order + 1 + HORIZON_BARS, cell.n)
    hit = (cumulative[stop] - cumulative[np.minimum(order + 1, cell.n)]) > 0
    full = (order + 1 + HORIZON_BARS) <= cell.n
    return hit, full


def build_donors(cells: Sequence[S8.Cell8]) -> list[Donor]:
    """Every legal in-depth candidate occurrence carrying the 1800 s floor."""

    donors: list[Donor] = []
    for cell in cells:
        open_ns = int(cell.rec.phase_open_ts_ns)
        for side in (1, -1):
            prior, _new, _armed = S7A.side_arrays(cell.geo, side)
            remaining = cell.sides[side].remaining_s
            hit, full = _postx_arrays(cell, side)
            for bar in S7A.candidate_bars(cell.rec, side):
                bar = int(bar)
                if float(remaining[bar]) < REMAIN_MIN_S or not bool(full[bar]):
                    continue
                if S8.depth_atr(float(cell.rec.mid[bar]), float(prior[bar]),
                                cell.atr_mid2) > DEPTH_ATR:
                    continue
                donors.append(Donor(
                    cell.asset, cell.phase, cell.d8,
                    int((int(cell.rec.lat[bar]) - open_ns) // NANOS_PER_SECOND),
                    int(remaining[bar]), bool(hit[bar]), True))
    return donors


def time_match(takes: Sequence[Take], cells: Sequence[S8.Cell8],
               draws: int = TIME_MATCH_DRAWS) -> dict[str, object]:
    """200 seeded draws of a phase-time twin from a different asset-day."""

    donors = build_donors(cells)
    buckets: dict[tuple[str, str], list[Donor]] = {}
    for row in donors:
        buckets.setdefault((row.asset, row.phase), []).append(row)
    keyed: dict[tuple[str, str], tuple[np.ndarray, list[Donor]]] = {}
    for key, rows in buckets.items():
        rows.sort(key=lambda row: row.elapsed_s)
        keyed[key] = (np.asarray([row.elapsed_s for row in rows], np.int64), rows)
    by_cell = {cell.position: cell for cell in cells}
    pools: list[tuple[Take, list[Donor]]] = []
    for take in takes:
        cell = by_cell[take.shot.cell]
        open_ns = int(cell.rec.phase_open_ts_ns)
        elapsed = int((int(cell.rec.lat[take.shot.entry_bar]) - open_ns)
                      // NANOS_PER_SECOND)
        remaining = int(take.remaining_s)
        stamps, rows = keyed.get((take.shot.asset, take.shot.phase),
                                 (np.zeros(0, np.int64), []))
        low = int(np.searchsorted(stamps, elapsed - TIME_MATCH_WINDOW_S, "left"))
        high = int(np.searchsorted(stamps, elapsed + TIME_MATCH_WINDOW_S, "right"))
        pool = [row for row in rows[low:high]
                if row.d8 != take.shot.d8
                and abs(row.remaining_s - remaining) <= TIME_MATCH_WINDOW_S]
        pools.append((take, pool))
    rng = np.random.default_rng(SEED)
    matched = sum(1 for _take, pool in pools if pool)
    by_asset_hits = {asset: 0 for asset in ASSETS}
    by_asset_n = {asset: 0 for asset in ASSETS}
    by_phase_hits: dict[str, int] = {}
    by_phase_n: dict[str, int] = {}
    by_day_hits: dict[tuple[str, int], int] = {}
    by_day_n: dict[tuple[str, int], int] = {}
    pool_sizes = [len(pool) for _take, pool in pools]
    for _draw in range(draws):
        for take, pool in pools:
            if not pool:
                continue
            pick = pool[int(rng.integers(len(pool)))]
            asset, phase = take.shot.asset, take.shot.phase
            key = (asset, take.shot.d8)
            by_asset_n[asset] += 1
            by_phase_n[phase] = by_phase_n.get(phase, 0) + 1
            by_day_n[key] = by_day_n.get(key, 0) + 1
            if pick.postx:
                by_asset_hits[asset] += 1
                by_phase_hits[phase] = by_phase_hits.get(phase, 0) + 1
                by_day_hits[key] = by_day_hits.get(key, 0) + 1
    return {
        "draws": draws, "seed": SEED, "match_window_s": TIME_MATCH_WINDOW_S,
        "donors": len(donors), "entries": len(pools), "entries_matched": matched,
        "match_share": (matched / len(pools)) if pools else None,
        "pool_median": _q(pool_sizes, 50), "pool_min": (min(pool_sizes)
                                                        if pool_sizes else None),
        "by_asset": {asset: _rate(by_asset_hits[asset], by_asset_n[asset])
                     for asset in ASSETS},
        "by_phase": {phase: _rate(by_phase_hits.get(phase, 0), by_phase_n[phase])
                     for phase in sorted(by_phase_n)},
        "by_day": {f"{asset}/{day}": {"hits": by_day_hits.get((asset, day), 0),
                                      "n": by_day_n[(asset, day)]}
                   for asset, day in sorted(by_day_n)},
        "matched_share_by_asset": {
            asset: (sum(1 for take, pool in pools
                        if take.shot.asset == asset and pool)
                    / max(1, sum(1 for take, _p in pools
                                 if take.shot.asset == asset)))
            for asset in ASSETS},
    }


# --------------------------------------------------------------------------
# Paired asset-day statistics.
# --------------------------------------------------------------------------

def day_rates(shots: Sequence[S8.Shot8], asset: str
              ) -> dict[int, tuple[int, int]]:
    """``{d8: (extended, entries)}`` over the full-window entries of one asset."""

    out: dict[int, tuple[int, int]] = {}
    for row in shots:
        if row.asset != asset or not row.entry_full_window:
            continue
        hits, total = out.get(row.d8, (0, 0))
        out[row.d8] = (hits + int(row.postx1800_entry), total + 1)
    return out


def paired(second: Mapping[int, tuple[int, int]],
           other: Mapping[int, tuple[int, int]]
           ) -> tuple[list[int], np.ndarray]:
    """Asset-day blocks present in both arms, and ``SECOND - other`` per day."""

    days = sorted(set(second) & set(other))
    diffs = np.asarray(
        [second[day][0] / second[day][1] - other[day][0] / other[day][1]
         for day in days if second[day][1] and other[day][1]], np.float64)
    kept = [day for day in days if second[day][1] and other[day][1]]
    return kept, diffs


def block_ci(diffs: np.ndarray, draws: int = BLOCK_DRAWS, seed: int = SEED
             ) -> dict[str, object]:
    """Paired asset-day block bootstrap: percentile 95% interval of the mean."""

    if not len(diffs):
        return {"n_days": 0, "delta": None, "ci_low": None, "ci_high": None}
    rng = np.random.default_rng(seed)
    picks = rng.integers(0, len(diffs), size=(draws, len(diffs)))
    means = diffs[picks].mean(axis=1)
    return {"n_days": int(len(diffs)), "delta": float(diffs.mean()),
            "ci_low": float(np.percentile(means, 2.5)),
            "ci_high": float(np.percentile(means, 97.5))}


def sign_flip(blocks: Mapping[str, tuple[list[int], np.ndarray]],
              groups: Mapping[str, str], pool: Sequence[str],
              draws: int = BLOCK_DRAWS, seed: int = SEED) -> dict[str, object]:
    """Asset-day block sign flips with a max statistic across ``pool``.

    ``groups`` maps each statistic to the asset whose day blocks it sits on.
    One sign is drawn per (asset, day) and BOTH comparisons on that asset read
    it at their own days, so an asset-day that flips flips in both statistics
    and their dependence survives inside the null.

    ``pool`` is the pre-registered max-statistic family: NKD/SI and both
    comparisons, four statistics.  HG is report-only, so it is measured and
    printed but never widens the ceiling the deciding assets are judged against.
    """

    names = [name for name in sorted(blocks) if len(blocks[name][1])]
    if not names:
        return {"draws": draws, "seed": seed, "statistics": [],
                "max_pool": list(pool), "by_stat": {}}
    pooled = [name for name in names if name in set(pool)]
    rng = np.random.default_rng(seed)
    observed = {name: float(blocks[name][1].mean()) for name in names}
    day_index: dict[str, dict[int, int]] = {}
    for asset in sorted({groups[name] for name in names}):
        days = sorted({day for name in names if groups[name] == asset
                       for day in blocks[name][0]})
        day_index[asset] = {day: slot for slot, day in enumerate(days)}
    slots = {name: np.asarray([day_index[groups[name]][day]
                               for day in blocks[name][0]], np.int64)
             for name in names}
    null: dict[str, list[float]] = {name: [] for name in names}
    null_max: list[float] = []
    for _draw in range(draws):
        signs = {asset: rng.choice((-1.0, 1.0), size=len(index))
                 for asset, index in day_index.items()}
        best = 0.0
        for name in names:
            flipped = float((blocks[name][1]
                             * signs[groups[name]][slots[name]]).mean())
            null[name].append(flipped)
            if name in pooled:
                best = max(best, abs(flipped))
        null_max.append(best)
    ceiling = np.asarray(null_max, np.float64)
    out: dict[str, object] = {"draws": draws, "seed": seed,
                              "statistics": names, "max_pool": pooled,
                              "by_stat": {}}
    for name in names:
        own = np.abs(np.asarray(null[name], np.float64))
        seen = abs(observed[name])
        out["by_stat"][name] = {
            "delta": observed[name], "n_days": int(len(blocks[name][1])),
            "p_own": float((1 + int(np.sum(own >= seen))) / (1 + draws)),
            "p_max_adjusted": float((1 + int(np.sum(ceiling >= seen)))
                                    / (1 + draws)),
        }
    return out


# --------------------------------------------------------------------------
# Stage A.
# --------------------------------------------------------------------------

def ordinal_table(takes: Sequence[Take]) -> dict[str, object]:
    rows = list(takes)
    return {
        "entries": len(rows),
        "added_wait_median_s": _q([r.added_wait_s for r in rows], 50),
        "added_wait_p90_s": _q([r.added_wait_s for r in rows], 90),
        "added_wait_max_s": _q([r.added_wait_s for r in rows], 100),
        "fire_to_entry_median_s": _q([r.shot.wait_s for r in rows], 50),
        "fire_to_entry_p90_s": _q([r.shot.wait_s for r in rows], 90),
        "remaining_median_s": _q([r.remaining_s for r in rows], 50),
        "remaining_min_s": (min(r.remaining_s for r in rows) if rows else None),
        "ordinal_median": _q([r.ordinal for r in rows], 50),
        "favorable_atr_median": _q([r.favorable_atr for r in rows], 50),
        "favorable_atr_p90": _q([r.favorable_atr for r in rows], 90),
        "favorable_share": (float(np.mean([r.favorable_atr > 0.0 for r in rows]))
                            if rows else None),
        "depth_median_atr": _q([r.shot.depth for r in rows], 50),
        # Diagnostic only: terminal lead/lag never selects anything here.
        "terminal_delay_median_s": _q([r.shot.delay_s for r in rows], 50),
        "before_terminal_share": (
            float(np.mean([r.shot.before_terminal for r in rows]))
            if rows else None),
        "soft_hit_share": (float(np.mean([r.shot.soft_hit for r in rows]))
                           if rows else None),
    }


def stage_a(first: Sequence[S8.Shot8], second: OrdinalRun, book: Recorded,
            cells: Sequence[S8.Cell8], control: Mapping[str, object]
            ) -> dict[str, object]:
    by_position = {cell.position: cell for cell in cells}
    scored_by_asset: dict[str, int] = {asset: 0 for asset in ASSETS}
    scored_by_phase: dict[str, int] = {}
    for position in book.threshold:
        cell = by_position[position]
        scored_by_asset[cell.asset] = scored_by_asset.get(cell.asset, 0) + 1
        scored_by_phase[cell.phase] = scored_by_phase.get(cell.phase, 0) + 1

    def block(keep, scored: int) -> dict[str, object]:
        takes = [row for row in second.takes if keep(row.shot.asset,
                                                     row.shot.phase)]
        firsts = [row for row in first if keep(row.asset, row.phase)]
        counters = Counters()
        fired = 0
        first_cells = 0
        second_cells = 0
        branches: dict[str, int] = {name: 0 for name in MISS_BRANCHES}
        for position, values in second.counters.items():
            cell = by_position[position]
            if not keep(cell.asset, cell.phase):
                continue
            counters.add(values)
            fired += second.fired_cells.get(position, 0)
            first_cells += second.first_cells.get(position, 0)
            second_cells += second.second_cells.get(position, 0)
        for position, branch in second.misses.items():
            cell = by_position[position]
            if not keep(cell.asset, cell.phase):
                continue
            branches[branch] = branches.get(branch, 0) + 1
        return {
            "cells_scored": int(scored), "cells_fired": int(fired),
            "fires": counters.fires,
            "first_occurrence_available": int(first_cells),
            "second_occurrence_available": int(second_cells),
            "fires_with_first_occurrence": counters.first_seen,
            "fires_with_second_occurrence": counters.second_seen,
            "entries": len(takes),
            "coverage": (len(takes) / scored) if scored else None,
            "first_entries": len(firsts),
            "first_coverage": (len(firsts) / scored) if scored else None,
            "duplicate_identities": counters.duplicates_after_dedup,
            "identity_repeats_skipped": counters.identity_repeats,
            "equal_timestamp_candidates": counters.equal_ts_skips,
            "same_side_resets": counters.resets,
            "opposite_side_cancels": counters.cancels,
            "no_second_candidate": counters.no_second,
            "no_first_candidate": counters.no_first,
            "deadline_misses": counters.deadline,
            "remain_floor_drops": counters.remain_drops,
            "miss_branches": branches,
            "postx1800": {
                "FIRST": S8.horizon_table(firsts)["postx1800_entry"],
                "SECOND": S8.horizon_table([r.shot for r in takes])
                          ["postx1800_entry"],
            },
            "censored_entry_windows": {
                "FIRST": sum(1 for r in firsts if not r.entry_full_window),
                "SECOND": sum(1 for r in takes if not r.shot.entry_full_window),
            },
            "ordinal": ordinal_table(takes),
        }

    by_asset: dict[str, object] = {}
    for asset in ASSETS:
        row = block(lambda a, _p, want=asset: a == want,
                    int(scored_by_asset.get(asset, 0)))
        row["postx1800"]["TIME-MATCH"] = control["by_asset"][asset]
        by_asset[asset] = row
    by_phase: dict[str, object] = {}
    for phase in sorted(scored_by_phase):
        row = block(lambda _a, p, want=phase: p == want,
                    int(scored_by_phase[phase]))
        row["postx1800"]["TIME-MATCH"] = control["by_phase"].get(
            phase, _rate(0, 0))
        by_phase[phase] = row
    return {"by_asset": by_asset, "by_phase": by_phase}


def paired_block(first: Sequence[S8.Shot8], takes: Sequence[Take],
                 control: Mapping[str, object]) -> dict[str, object]:
    """Every paired asset-day difference, its interval and its adjusted p."""

    seconds = [row.shot for row in takes]
    blocks: dict[str, tuple[list[int], np.ndarray]] = {}
    groups: dict[str, str] = {}
    detail: dict[str, object] = {}
    control_days = control["by_day"]
    for asset in ASSETS:
        second_days = day_rates(seconds, asset)
        first_days = day_rates(first, asset)
        tm_days = {int(key.split("/")[1]): (int(value["hits"]), int(value["n"]))
                   for key, value in control_days.items()
                   if key.split("/")[0] == asset and int(value["n"])}
        for label, other in (("FIRST", first_days), ("TIME-MATCH", tm_days)):
            days, diffs = paired(second_days, other)
            name = f"{asset}/SECOND-{label}"
            blocks[name] = (days, diffs)
            groups[name] = asset
            detail[name] = {**block_ci(diffs), "days_paired": len(days),
                            "days_second": len(second_days),
                            "days_other": len(other)}
    # The pre-registered family: NKD/SI and both comparisons.  HG is measured
    # the same way and printed, but it is report-only and never enters the max.
    pool = [f"{asset}/SECOND-{label}" for asset in DECIDING
            for label in ("FIRST", "TIME-MATCH")]
    flips = sign_flip(blocks, groups, pool)
    for name, row in detail.items():
        stat = flips["by_stat"].get(name)
        row["p_own"] = stat["p_own"] if stat else None
        row["p_max_adjusted"] = stat["p_max_adjusted"] if stat else None
    return {"by_stat": detail, "sign_flip": flips,
            "bootstrap_draws": BLOCK_DRAWS, "seed": SEED}


# --------------------------------------------------------------------------
# The pre-registered ruling.
# --------------------------------------------------------------------------

def _bound(name: str, ok: bool, detail: str) -> dict[str, object]:
    return {"bound": name, "pass": bool(ok), "detail": detail}


def rule(report: Mapping[str, object]) -> dict[str, object]:
    stage = report["stage_a"]["by_asset"]
    pairs = report["paired"]["by_stat"]
    control = report["time_match"]
    out: dict[str, object] = {"by_asset": {}}
    for asset in ASSETS:
        row = stage[asset]
        second = row["postx1800"]["SECOND"]["rate"]
        first = row["postx1800"]["FIRST"]["rate"]
        match = row["postx1800"]["TIME-MATCH"]["rate"]
        coverage = row["coverage"]
        gain_first = (None if second is None or first is None
                      else float(first) - float(second))
        gain_match = (None if second is None or match is None
                      else float(match) - float(second))
        pair_first = pairs[f"{asset}/SECOND-FIRST"]
        pair_match = pairs[f"{asset}/SECOND-TIME-MATCH"]
        wait = row["ordinal"]["added_wait_p90_s"]
        skips = report.get("price", {}).get("replay_skips_total")
        bounds = [
            _bound("1 coverage >= 0.35",
                   coverage is not None and float(coverage) >= COVERAGE_FLOOR,
                   f"coverage {coverage}"),
            _bound("2 SECOND postX_1800 <= 0.25",
                   second is not None and float(second) <= POSTX_CEILING,
                   f"postX {second}"),
            _bound("3a SECOND beats FIRST by >= 0.10",
                   gain_first is not None and gain_first >= GAIN_OVER_FIRST,
                   f"gain {gain_first}"),
            _bound("3b SECOND beats TIME-MATCH by >= 0.05",
                   gain_match is not None and gain_match >= GAIN_OVER_TIME_MATCH,
                   f"gain {gain_match}"),
            _bound("4a SECOND-FIRST 95% upper bound < 0",
                   pair_first["ci_high"] is not None
                   and float(pair_first["ci_high"]) < 0.0,
                   f"ci_high {pair_first['ci_high']}"),
            _bound("4b SECOND-TIME-MATCH 95% upper bound < 0",
                   pair_match["ci_high"] is not None
                   and float(pair_match["ci_high"]) < 0.0,
                   f"ci_high {pair_match['ci_high']}"),
            _bound("4c max-adjusted p <= 0.05 (both)",
                   pair_first["p_max_adjusted"] is not None
                   and pair_match["p_max_adjusted"] is not None
                   and float(pair_first["p_max_adjusted"]) <= ADJUSTED_P_CEILING
                   and float(pair_match["p_max_adjusted"]) <= ADJUSTED_P_CEILING,
                   f"p {pair_first['p_max_adjusted']}/"
                   f"{pair_match['p_max_adjusted']}"),
            _bound("5 added wait p90 <= 900 s",
                   wait is not None and float(wait) <= WAIT_P90_CEILING,
                   f"p90 {wait}"),
            _bound("6a identity duplicates == 0",
                   int(row["duplicate_identities"]) == 0,
                   f"duplicates {row['duplicate_identities']}"),
            _bound("6b every entry has >= 1800 s remaining",
                   row["ordinal"]["remaining_min_s"] is None
                   or float(row["ordinal"]["remaining_min_s"]) >= REMAIN_MIN_S,
                   f"min remaining {row['ordinal']['remaining_min_s']}"),
            _bound("6c TIME-MATCH matches >= 90% of SECOND entries",
                   float(control["matched_share_by_asset"][asset])
                   >= TIME_MATCH_COVER_FLOOR,
                   f"matched {control['matched_share_by_asset'][asset]}"),
            _bound("6d replay cap skips == 0",
                   skips in (None, 0),
                   f"skips {'not read (stage A)' if skips is None else skips}"),
        ]
        worsens = (gain_first is not None and gain_first <= -WORSEN_KILL)
        out["by_asset"][asset] = {
            "deciding": asset in DECIDING,
            "postx_first": first, "postx_second": second, "postx_time_match": match,
            "gain_over_first": gain_first, "gain_over_time_match": gain_match,
            "coverage": coverage, "added_wait_p90_s": wait,
            "delta_first": pair_first["delta"], "delta_time_match": pair_match["delta"],
            "bounds": bounds,
            "bounds_failed": [b["bound"] for b in bounds if not b["pass"]],
            "passes": all(b["pass"] for b in bounds),
            "worsens_postx": worsens,
        }
    passing = [a for a in DECIDING if out["by_asset"][a]["passes"]]
    worsened = [a for a in DECIDING if out["by_asset"][a]["worsens_postx"]]
    if worsened:
        verdict = "ORDINAL-KILL"
    elif len(passing) == len(DECIDING):
        verdict = "ORDINAL-SURVIVES"
    elif len(passing) == 1:
        other = [a for a in DECIDING if a not in passing][0]
        point = out["by_asset"][other]["gain_over_first"]
        # "non-positive" on the other asset means SECOND did not IMPROVE it:
        # gain_over_first is FIRST - SECOND, so the point estimate is the
        # negated gain and non-positive means gain >= 0 is not required.
        verdict = ("ORDINAL-ASSET-SCOPED"
                   if point is not None and -float(point) <= 0.0
                   else "ORDINAL-KILL")
    else:
        verdict = "ORDINAL-KILL"
    out["passing_assets"] = passing
    out["verdict"] = verdict
    out["price_licensed"] = verdict in ("ORDINAL-SURVIVES", "ORDINAL-ASSET-SCOPED")
    out["price_assets"] = passing if out["price_licensed"] else []
    return out


# --------------------------------------------------------------------------
# The one gated price read.
# --------------------------------------------------------------------------

def price_second(takes: Sequence[Take], records: Sequence[S1.CellRec],
                 days: Mapping[str, int], scored: Mapping[str, int],
                 explore_days: Mapping[str, list[int]],
                 assets: Sequence[str]) -> dict[str, object]:
    shots = [row.shot for row in takes if row.shot.asset in assets]
    entries = S8.entries_of(shots, records)
    cells = {asset: int(scored.get(asset, 0)) for asset in ASSETS}
    cash = S1.cash_line(entries, days, cells)
    replay = S1.replay_line(entries, records, f"sweep13-second:{code_sha()[:16]}")
    stress = {asset: S3.stress_line(entries, records, days, cells, asset,
                                    STRESS_RATE) for asset in assets}
    null = S1.block_null({f"{asset}/SECOND": [row for row in entries
                                              if row.asset == asset]
                          for asset in assets},
                         explore_days, NULL_DRAWS, SEED)
    verdicts: dict[str, object] = {}
    for asset in assets:
        line = cash[asset]
        null_row = null["by_line"].get(f"{asset}/SECOND")
        adjusted = float(null_row["p_max_adjusted"]) if null_row else None
        fired: list[str] = []
        if float(line["usd_per_asset_day"]) < DAY_RUNG_USD[asset]:
            fired.append(f"usd/day {line['usd_per_asset_day']:.1f} "
                         f"< rung {DAY_RUNG_USD[asset]:.0f}")
        if float(line["mdd_day_usd"]) >= MDD_CEILING:
            fired.append(f"mdd_day {line['mdd_day_usd']:.0f} >= {MDD_CEILING:.0f}")
        if float(line["mdd_trade_usd"]) >= MDD_CEILING:
            fired.append(f"mdd_trade {line['mdd_trade_usd']:.0f} "
                         f">= {MDD_CEILING:.0f}")
        if float(stress[asset]["usd_per_asset_day"]) <= 0.0:
            fired.append(f"stress {stress[asset]['usd_per_asset_day']:.1f} <= 0")
        if adjusted is None or adjusted > NULL_CEILING:
            fired.append(f"adjusted null {adjusted} > {NULL_CEILING}")
        skips = replay.get("occupancy_or_cap_skips")
        if skips not in (None, 0):
            fired.append(f"replay skips {skips} != 0")
        verdicts[asset] = {"bounds_fired": fired,
                           "survives_explore": not fired,
                           "adjusted_null_p": adjusted}
    return {"assets": list(assets), "entries": len(entries), "cash": cash,
            "replay": replay, "stress": stress, "null": null,
            "replay_skips_total": replay.get("occupancy_or_cap_skips"),
            "by_asset": verdicts,
            "overall": ("EXPLORE-SURVIVOR"
                        if all(verdicts[a]["survives_explore"] for a in assets)
                        else "CASH-FAIL")}


# --------------------------------------------------------------------------
# Printers.
# --------------------------------------------------------------------------

def _n(value: object, width: int = 8, digits: int = 3) -> str:
    if value is None:
        return "-".rjust(width)
    if isinstance(value, bool):
        return ("yes" if value else "no").rjust(width)
    if isinstance(value, (int, np.integer)):
        return str(int(value)).rjust(width)
    return f"{float(value):.{digits}f}".rjust(width)


def print_repro(report: Mapping[str, object]) -> None:
    receipt = report["reproduction"]
    print("\n== FIRST reproduction gate (sweep-8 PRIMARY, frozen) ==")
    print(f"{'asset':<6}{'entries':>9}{'want':>7}{'postX n':>9}{'want':>6}"
          f"{'postX':>8}{'want':>8}{'ok':>5}")
    for row in receipt["checks"]:
        ok = row["entries_ok"] and row["postx_n_ok"] and row["postx_rate_ok"]
        print(f"{row['asset']:<6}{row['entries']:>9}{row['entries_expected']:>7}"
              f"{row['postx_n']:>9}{row['postx_n_expected']:>6}"
              f"{_n(row['postx_rate'], 8)}{row['postx_rate_expected']:>8.3f}"
              f"{'PASS' if ok else 'FAIL':>5}")
    print(f"scored cells re-resolved with the frozen fire bar: "
          f"{receipt['cells_rechecked']} "
          f"({receipt['cells_scored']}), crossing count recovers the fire set in "
          f"{receipt['crossing_count_recovers_fire_set']}; mismatches "
          f"{receipt['threshold_mismatch_count']}")
    for line in receipt["threshold_mismatches"]:
        print(f"  {line}")
    print(f"reproduction verdict: {receipt['verdict']}")


def _print_stage_rows(title: str, table: Mapping[str, object]) -> None:
    print(f"\n-- {title} --")
    print(f"{'key':<6}{'scored':>7}{'fired':>7}{'fires':>7}{'occ1':>6}{'occ2':>6}"
          f"{'entries':>8}{'cover':>7}{'1st_n':>7}{'1st_cov':>8}")
    for key, row in table.items():
        print(f"{key:<6}{row['cells_scored']:>7}{row['cells_fired']:>7}"
              f"{row['fires']:>7}{row['first_occurrence_available']:>6}"
              f"{row['second_occurrence_available']:>6}{row['entries']:>8}"
              f"{_n(row['coverage'], 7)}{row['first_entries']:>7}"
              f"{_n(row['first_coverage'], 8)}")
    print(f"\n{'key':<6}{'dupIDs':>7}{'idRept':>7}{'eqTS':>6}{'resets':>7}"
          f"{'cancel':>7}{'no2nd':>7}{'no1st':>7}{'deadln':>7}{'remflr':>7}")
    for key, row in table.items():
        print(f"{key:<6}{row['duplicate_identities']:>7}"
              f"{row['identity_repeats_skipped']:>7}"
              f"{row['equal_timestamp_candidates']:>6}{row['same_side_resets']:>7}"
              f"{row['opposite_side_cancels']:>7}{row['no_second_candidate']:>7}"
              f"{row['no_first_candidate']:>7}{row['deadline_misses']:>7}"
              f"{row['remain_floor_drops']:>7}")
    print(f"\n{'key':<6}{'FIRST':>9}{'n':>6}{'SECOND':>9}{'n':>6}"
          f"{'TIMEMATCH':>10}{'n':>8}{'cens1':>7}{'cens2':>7}")
    for key, row in table.items():
        block = row["postx1800"]
        print(f"{key:<6}{_n(block['FIRST']['rate'], 9)}{block['FIRST']['n']:>6}"
              f"{_n(block['SECOND']['rate'], 9)}{block['SECOND']['n']:>6}"
              f"{_n(block['TIME-MATCH']['rate'], 10)}{block['TIME-MATCH']['n']:>8}"
              f"{row['censored_entry_windows']['FIRST']:>7}"
              f"{row['censored_entry_windows']['SECOND']:>7}")
    print(f"\n{'key':<6}{'wait_md':>8}{'wait_p90':>9}{'f2e_md':>8}{'rem_md':>8}"
          f"{'rem_min':>9}{'ord_md':>7}{'favATR':>8}{'fav%':>7}{'termlag':>9}")
    for key, row in table.items():
        block = row["ordinal"]
        print(f"{key:<6}{_n(block['added_wait_median_s'], 8, 0)}"
              f"{_n(block['added_wait_p90_s'], 9, 0)}"
              f"{_n(block['fire_to_entry_median_s'], 8, 0)}"
              f"{_n(block['remaining_median_s'], 8, 0)}"
              f"{_n(block['remaining_min_s'], 9, 0)}"
              f"{_n(block['ordinal_median'], 7, 1)}"
              f"{_n(block['favorable_atr_median'], 8)}"
              f"{_n(block['favorable_share'], 7)}"
              f"{_n(block['terminal_delay_median_s'], 9, 0)}")
    print(f"\n{'key':<6}  miss branches")
    for key, row in table.items():
        parts = ", ".join(f"{name}={count}"
                          for name, count in row["miss_branches"].items() if count)
        print(f"{key:<6}  {parts or '(none)'}")


def print_stage_a(report: Mapping[str, object]) -> None:
    print("\n== Stage A: the ordinal-2 ablation (no cash, HG report-only) ==")
    _print_stage_rows("by asset", report["stage_a"]["by_asset"])
    _print_stage_rows("by phase", report["stage_a"]["by_phase"])
    control = report["time_match"]
    print(f"\nTIME-MATCH: {control['draws']} draws, seed {control['seed']}, "
          f"window +-{control['match_window_s']} s, donors {control['donors']}, "
          f"matched {control['entries_matched']}/{control['entries']} "
          f"({_n(control['match_share'], 5)}), pool median "
          f"{_n(control['pool_median'], 6, 0)} min "
          f"{_n(control['pool_min'], 5, 0)}")
    print("  matched share by asset: " + ", ".join(
        f"{asset} {control['matched_share_by_asset'][asset]:.3f}"
        for asset in ASSETS))
    print("\n-- paired asset-day differences (SECOND minus arm) --")
    print(f"{'statistic':<26}{'days':>6}{'delta':>9}{'ci_low':>9}{'ci_high':>9}"
          f"{'p_own':>8}{'p_adj':>8}")
    for name, row in report["paired"]["by_stat"].items():
        print(f"{name:<26}{row['n_days']:>6}{_n(row['delta'], 9)}"
              f"{_n(row['ci_low'], 9)}{_n(row['ci_high'], 9)}"
              f"{_n(row['p_own'], 8)}{_n(row['p_max_adjusted'], 8)}")
    print(f"sign flips {report['paired']['sign_flip']['draws']} draws, "
          f"bootstrap {report['paired']['bootstrap_draws']} draws, "
          f"seed {report['paired']['seed']}; max statistic across "
          f"{len(report['paired']['sign_flip']['max_pool'])} comparisons "
          f"({', '.join(report['paired']['sign_flip']['max_pool'])}); "
          f"HG is report-only and outside the max pool")


def print_ruling(report: Mapping[str, object]) -> None:
    ruling = report["ruling"]
    print("\n== Pre-registered stage-A ruling ==")
    for asset in ASSETS:
        row = ruling["by_asset"][asset]
        tag = "deciding" if row["deciding"] else "report-only"
        print(f"\n{asset} ({tag}): postX FIRST {_n(row['postx_first'], 6)} "
              f"SECOND {_n(row['postx_second'], 6)} "
              f"TIME-MATCH {_n(row['postx_time_match'], 6)}; "
              f"gains {_n(row['gain_over_first'], 6)}/"
              f"{_n(row['gain_over_time_match'], 6)}")
        for bound in row["bounds"]:
            print(f"   [{'PASS' if bound['pass'] else 'FAIL'}] "
                  f"{bound['bound']:<44} {bound['detail']}")
        print(f"   -> all bounds {'PASS' if row['passes'] else 'FAIL'}"
              + (f"; worsens postX by >= {WORSEN_KILL}"
                 if row["worsens_postx"] else ""))
    print(f"\nVERDICT: {ruling['verdict']}  "
          f"(passing deciding assets: {ruling['passing_assets'] or 'none'})")
    print(f"price read licensed: {ruling['price_licensed']}")


def print_price(report: Mapping[str, object]) -> None:
    block = report.get("price")
    if not block:
        print("\n== Gated price read: NOT OPENED (the ruling does not license it) ==")
        return
    print("\n== The one gated price read ==")
    print(f"{'asset':<6}{'trades':>8}{'usd/day':>10}{'rung':>8}{'usd/trd':>9}"
          f"{'win':>7}{'wall':>7}{'mdd_day':>9}{'mdd_trd':>9}{'stress':>9}"
          f"{'nullp':>8}")
    for asset in block["assets"]:
        line = block["cash"][asset]
        print(f"{asset:<6}{line['trades']:>8}{_n(line['usd_per_asset_day'], 10, 1)}"
              f"{DAY_RUNG_USD[asset]:>8.0f}{_n(line['usd_per_trade'], 9, 1)}"
              f"{_n(line['win_rate'], 7)}{_n(line['wall_rate'], 7)}"
              f"{_n(line['mdd_day_usd'], 9, 0)}{_n(line['mdd_trade_usd'], 9, 0)}"
              f"{_n(block['stress'][asset]['usd_per_asset_day'], 9, 1)}"
              f"{_n(block['by_asset'][asset]['adjusted_null_p'], 8)}")
    replay = block["replay"]
    print(f"replay: {replay.get('status')} {replay.get('label', '')} "
          f"arrivals {replay.get('arrivals')} trades {replay.get('trades')} "
          f"occupancy_or_cap_skips {replay.get('occupancy_or_cap_skips')}")
    for asset in block["assets"]:
        row = block["by_asset"][asset]
        print(f"  {asset}: {'SURVIVES EXPLORE' if row['survives_explore'] else 'FAIL'}"
              + ("" if row["survives_explore"]
                 else "; " + "; ".join(row["bounds_fired"])))
    print(f"price verdict: {block['overall']}")


# --------------------------------------------------------------------------
# Selftest.
# --------------------------------------------------------------------------

def _check(name: str, ok: bool, detail: str = "") -> tuple[str, bool, str]:
    return (name, bool(ok), detail)


def _ident_fixture(bars: int, changes: Mapping[int, str]) -> Ident:
    """A hand-built identity series: ``changes`` maps bar -> new live name."""

    name = np.full(bars, "", dtype=object)
    stamp = np.full(bars, -1, dtype=np.int64)
    live, live_ts = "", -1
    for bar in range(bars):
        if bar in changes:
            live = changes[bar]
            live_ts = bar * BAR_SECONDS * NANOS_PER_SECOND
        name[bar] = live
        stamp[bar] = live_ts
    return Ident(name, stamp, len(changes), 0)


def _selftest_identity() -> list[tuple[str, bool, str]]:
    """Keep-first folding and the newest-live rule on hand-built arrivals."""

    out: list[tuple[str, bool, str]] = []
    lat = np.arange(6, dtype=np.int64) * 60 * NANOS_PER_SECOND
    stamps = np.asarray([0, 120, 120, 300], np.int64) * NANOS_PER_SECOND
    ident = _ident_from_rows(lat, stamps, ["c-b", "c-d", "c-a", "c-z"])
    out.append(_check("keep-first folds the equal-stamp arrival",
                      ident.equal_ts_folded == 1 and ident.arrivals == 3,
                      f"folded={ident.equal_ts_folded} kept={ident.arrivals}"))
    out.append(_check("the equal-stamp winner is the smaller id",
                      str(ident.name[2]) == "c-a", f"{ident.name[2]}"))
    out.append(_check("the live name is the newest arrival at or before the bar",
                      [str(v) for v in ident.name] ==
                      ["c-b", "c-b", "c-a", "c-a", "c-a", "c-z"],
                      f"{[str(v) for v in ident.name]}"))
    out.append(_check("stamps are non-decreasing and match the arrival",
                      int(ident.decision_ts[5]) == 300 * NANOS_PER_SECOND,
                      f"{ident.decision_ts.tolist()}"))
    return out


def _selftest_threshold() -> list[tuple[str, bool, str]]:
    """The recovered fire bar reproduces the crossing count exactly."""

    out: list[tuple[str, bool, str]] = []
    scored = [(1, 3, 0.10, 0.0), (1, 4, 0.90, 0.0), (-1, 4, 0.90, 0.0),
              (1, 5, 0.55, 0.0)]
    thr = derived_threshold(scored, 2)
    fired = [row for row in scored if float(row[2]) >= float(thr or 1e9)]
    out.append(_check("two crossings recover a bar that fires exactly two rows",
                      thr == 0.90 and len(fired) == 2, f"thr={thr} n={len(fired)}"))
    out.append(_check("zero crossings recover no bar",
                      derived_threshold(scored, 0) is None))
    thr = derived_threshold(scored, 4)
    out.append(_check("all crossings recover the smallest scored value",
                      thr == 0.10, f"thr={thr}"))
    return out


FIXTURE_SCORED = ((1, 4, 0.90, 0.0), (1, 20, 0.90, 0.0))


def _ordinal_fixture() -> tuple[S8.Cell8, dict[int, Ident]]:
    """A cell the ordinal-2 policy survives and the frozen first-entry does not.

    Side +1 fades a low printed at bar 3; the 0.15 ATR band is 15 mid2 wide on
    the fixture's 100 mid2 ATR.  A new same-direction low lands at bar 6.  Two
    fires are offered, at bar 4 and at bar 20.

    FIRST takes the bar-4 fire and enters at bar 4, and the bar-6 extension sits
    inside its 1800 s window: it extends.  SECOND cannot: the bar-6 extreme
    resets the ordinal and voids that fire before a second occurrence exists, so
    it waits for the bar-20 fire on the new extreme and enters its ordinal-2
    occurrence at bar 22, whose own window is clean.  That asymmetry is the only
    one available - a forward window from a LATER bar can never dodge an
    extension a strictly earlier entry saw unless the fire itself was voided.
    """

    mid = ([1000.0, 990.0, 980.0, 900.0, 905.0, 908.0, 895.0] + [900.0] * 63)
    certs_p = [50.0] * len(mid)
    certs_p[20] = 5000.0     # the peek mutant's bait: occurrence one pays most
    cell = S8._fixture_cell(certs_p, [-50.0] * len(mid), mid)
    idents = {1: _ident_fixture(len(mid), {0: "c-000", 22: "c-022"}),
              -1: _ident_fixture(len(mid), {0: "d-000"})}
    return cell, idents


def _selftest_ordinal() -> list[tuple[str, bool, str]]:
    """The ordinal-2 entry survives, the frozen first entry does not."""

    out: list[tuple[str, bool, str]] = []
    cell, idents = _ordinal_fixture()
    scored = list(FIXTURE_SCORED)
    prior, new_ext, _armed = S7A.side_arrays(cell.geo, 1)
    out.append(_check("the fixture fades a low printed at bar 3",
                      float(prior[4]) == 900.0 and bool(new_ext[3]),
                      f"prior={prior[4]} marks={np.flatnonzero(new_ext).tolist()}"))
    out.append(_check("its only later same-side extreme is at bar 6",
                      np.flatnonzero(new_ext).tolist() == [1, 2, 3, 6],
                      f"{np.flatnonzero(new_ext).tolist()}"))
    frozen, frozen_miss = S8.resolve(cell, scored, 0.5, depth_law=True)
    out.append(_check("the frozen sweep-8 resolver enters the bar-4 fire",
                      frozen is not None and frozen.fire_bar == 4
                      and frozen.entry_bar == 4 and frozen_miss == "",
                      f"{None if frozen is None else frozen.entry_bar} "
                      f"miss={frozen_miss}"))
    out.append(_check("the FIRST entry extends inside its 1800 s window",
                      frozen is not None and frozen.postx1800_entry
                      and frozen.entry_full_window,
                      f"postx={None if frozen is None else frozen.postx1800_entry}"))
    voided = walk_from_fire(cell, 1, 4, idents[1])
    out.append(_check("occurrence one is the bar the frozen resolver enters",
                      bool(voided.occurrences)
                      and voided.occurrences[0].bar
                      == S8.entry_after(cell, 1, 4, True)[0],
                      f"occ1={[r.bar for r in voided.occurrences]}"))
    out.append(_check("a same-side new extreme resets the count and voids",
                      voided.branch == MISS_RESET and voided.entry is None
                      and voided.counters.resets == 1,
                      f"branch={voided.branch} resets={voided.counters.resets}"))
    walk = walk_from_fire(cell, 1, 20, idents[1])
    out.append(_check("the ordinal-2 occurrence is entered at its own bar",
                      walk.entry is not None and walk.entry.bar == 22
                      and walk.entry.ordinal == 2,
                      f"entry={None if walk.entry is None else walk.entry.bar}"))
    out.append(_check("the repeated live identity is not a new occurrence",
                      walk.counters.identity_repeats > 0
                      and walk.counters.duplicates_after_dedup == 0,
                      f"repeats={walk.counters.identity_repeats}"))
    take, miss, _counters = second_resolve(cell, scored, 0.5, idents)
    out.append(_check("second_resolve skips the voided fire and takes the next",
                      take is not None and take.shot.fire_bar == 20
                      and take.shot.entry_bar == 22 and take.first_bar == 20
                      and miss == "",
                      f"take={None if take is None else take.shot.entry_bar} "
                      f"miss={miss}"))
    out.append(_check("the SECOND entry does not extend inside its 1800 s window",
                      take is not None and not take.shot.postx1800_entry
                      and take.shot.entry_full_window,
                      f"postx={None if take is None else take.shot.postx1800_entry}"))
    out.append(_check("the added wait is the first-to-second gap",
                      take is not None and take.added_wait_s == 120,
                      f"{None if take is None else take.added_wait_s}"))
    take_void, miss, _counters = second_resolve(cell, [FIXTURE_SCORED[0]], 0.5,
                                                idents)
    out.append(_check("a voided fire with no successor enters nothing",
                      take_void is None and miss == MISS_RESET, f"miss={miss}"))
    # The running extreme the depth band is read against never moves inside a
    # surviving window, which is what makes "running extreme" and sweep 8's
    # "extreme at the fire" the same object on every entry this unit takes.
    out.append(_check("the running extreme is constant across a surviving walk",
                      all(float(prior[row.bar]) == float(prior[20])
                          for row in walk.occurrences),
                      f"{[float(prior[row.bar]) for row in walk.occurrences]}"))
    return out


def _selftest_mutants() -> list[tuple[str, bool, str]]:
    """Both mutants must break facts the ordinal selftest above asserts."""

    out: list[tuple[str, bool, str]] = []
    cell, idents = _ordinal_fixture()
    kept = walk_from_fire(cell, 1, 4, idents[1], MUTANT_KEEP)
    out.append(_check(f"{MUTANT_KEEP}: the reset no longer voids the fire",
                      kept.branch != MISS_RESET,
                      f"branch={kept.branch} resets={kept.counters.resets}"))
    peek = walk_from_fire(cell, 1, 20, idents[1], MUTANT_PEEK)
    out.append(_check(f"{MUTANT_PEEK}: the entry is not the ordinal-2 occurrence",
                      peek.entry is not None and peek.entry.bar != 22,
                      f"entry={None if peek.entry is None else peek.entry.bar}"))
    return out


def _selftest_stats() -> list[tuple[str, bool, str]]:
    """The paired machinery on hand-computable blocks."""

    out: list[tuple[str, bool, str]] = []
    second = {1: (1, 4), 2: (0, 2)}
    first = {1: (3, 4), 2: (1, 2)}
    days, diffs = paired(second, first)
    out.append(_check("paired differences are second minus other, per day",
                      days == [1, 2] and abs(diffs[0] + 0.5) < 1e-12
                      and abs(diffs[1] + 0.5) < 1e-12, f"{diffs.tolist()}"))
    ci = block_ci(diffs, draws=200, seed=SEED)
    out.append(_check("a constant block has a degenerate interval at its mean",
                      abs(float(ci["delta"]) + 0.5) < 1e-12
                      and abs(float(ci["ci_high"]) + 0.5) < 1e-12,
                      f"{ci}"))
    flips = sign_flip({"A/x": (days, diffs)}, {"A/x": "A"}, ["A/x"],
                      draws=1000, seed=SEED)
    stat = flips["by_stat"]["A/x"]
    out.append(_check("a two-day constant block cannot beat p=0.05",
                      float(stat["p_own"]) > 0.05, f"p={stat['p_own']}"))
    out.append(_check("the adjusted p is at least the own p",
                      float(stat["p_max_adjusted"]) >= float(stat["p_own"]),
                      f"{stat}"))
    hit, full = _postx_arrays(_ordinal_fixture()[0], 1)
    reference = S8._finish(_ordinal_fixture()[0], 1, 4, 4, 1.0, 0.05)
    out.append(_check("the vectorised postX matches _finish at the same bar",
                      bool(hit[4]) == reference.postx1800_entry
                      and bool(full[4]) == reference.entry_full_window,
                      f"hit={bool(hit[4])} full={bool(full[4])}"))
    return out


def selftest() -> int:
    mutant = _mutant()
    blocks = [("identity", _selftest_identity()),
              ("threshold", _selftest_threshold()),
              ("ordinal", _selftest_ordinal()),
              ("statistics", _selftest_stats())]
    if not mutant:
        blocks.append(("mutants", _selftest_mutants()))
    failed = 0
    print(f"sweep 13 selftest (mutant={mutant or 'none'})")
    for title, rows in blocks:
        print(f"-- {title} --")
        for name, ok, detail in rows:
            failed += 0 if ok else 1
            print(f"  [{'ok' if ok else 'FAIL'}] {name}"
                  + (f"  ({detail})" if detail and not ok else ""))
    print(f"{'PASS' if not failed else 'FAIL'}: {failed} failing check(s)")
    return 0 if not failed else 1


# --------------------------------------------------------------------------
# Report, log, main.
# --------------------------------------------------------------------------

def _show(value: object) -> str:
    return "-" if value is None else f"{float(value):.3f}"


def log_rows(report: Mapping[str, object]) -> list[dict[str, object]]:
    stamp = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    shared = {
        "registered_utc": stamp, "family": FAMILY, "spec_sha": SPEC_SHA,
        "code_sha": report["code_sha"], "split_sha": report["split_sha"],
        "outcome_law_sha": report["outcome_law_sha"], "null_seed": SEED,
        "parent_trial": PARENT_TRIAL, "selection_rule": SELECTION_RULE,
        "verdict": "", "days": sum(report["asset_days"].values()),
    }
    params = json.dumps([ORDINAL, OCC_WINDOW_S, DEPTH_ATR, REMAIN_MIN_S,
                         TIME_MATCH_WINDOW_S])
    stage = report["stage_a"]["by_asset"]
    rows: list[dict[str, object]] = []
    counter = 0
    for name in LINES:
        counter += 1
        rates = {asset: stage[asset]["postx1800"][name]["rate"] for asset in ASSETS}
        coverage = [stage[asset]["coverage" if name == "SECOND"
                                 else "first_coverage"] for asset in ASSETS]
        rows.append({
            **shared, "id": f"sweep13-{counter:03d}", "rule": f"STAGE-A/{name}",
            "params": params,
            "coverage": float(np.mean([v for v in coverage if v is not None]))
                        if any(v is not None for v in coverage) else None,
            "delay_med_s": (stage["NKD"]["ordinal"]["terminal_delay_median_s"]
                            if name == "SECOND" else None),
            "err_rate_hg": rates["HG"], "err_rate_nkd": rates["NKD"],
            "err_rate_si": rates["SI"],
            "note": (f"entry-stamp postX_1800 {_show(rates['HG'])}/"
                     f"{_show(rates['NKD'])}/{_show(rates['SI'])}; "
                     f"{'ordinal-2' if name == 'SECOND' else 'frozen sweep-8 PRIMARY'}"),
        })
    counter += 1
    control = report["time_match"]["by_asset"]
    rows.append({
        **shared, "id": f"sweep13-{counter:03d}", "rule": "CONTROL/TIME-MATCH",
        "params": json.dumps([TIME_MATCH_DRAWS, TIME_MATCH_WINDOW_S, REMAIN_MIN_S]),
        "err_rate_hg": control["HG"]["rate"], "err_rate_nkd": control["NKD"]["rate"],
        "err_rate_si": control["SI"]["rate"],
        "note": (f"phase-time twin from another asset-day; matched "
                 f"{report['time_match']['entries_matched']}/"
                 f"{report['time_match']['entries']}"),
    })
    ruling = report["ruling"]
    for asset in DECIDING:
        counter += 1
        row = ruling["by_asset"][asset]
        rows.append({
            **shared, "id": f"sweep13-{counter:03d}",
            "rule": f"RULING/{asset}", "params": params,
            "coverage": row["coverage"],
            "err_rate_nkd": row["postx_second"] if asset == "NKD" else None,
            "err_rate_si": row["postx_second"] if asset == "SI" else None,
            "null_margin": (report["paired"]["by_stat"][f"{asset}/SECOND-FIRST"]
                            ["p_max_adjusted"]),
            "note": (f"{ruling['verdict']}; failed "
                     f"{len(row['bounds_failed'])} bound(s): "
                     + ("; ".join(row["bounds_failed"]) or "none"))[:400],
        })
    price = report.get("price")
    if price:
        for asset in price["assets"]:
            counter += 1
            line = price["cash"][asset]
            rows.append({
                **shared, "id": f"sweep13-{counter:03d}",
                "rule": f"PRICED/SECOND/{asset}", "params": params,
                "coverage": line["coverage"],
                "walls_hg": line["walls"] if asset == "HG" else None,
                "walls_nkd": line["walls"] if asset == "NKD" else None,
                "walls_si": line["walls"] if asset == "SI" else None,
                "hg_usd_day": line["usd_per_asset_day"] if asset == "HG" else None,
                "nkd_usd_day": line["usd_per_asset_day"] if asset == "NKD" else None,
                "si_usd_day": line["usd_per_asset_day"] if asset == "SI" else None,
                "mdd_hg": line["mdd_day_usd"] if asset == "HG" else None,
                "mdd_nkd": line["mdd_day_usd"] if asset == "NKD" else None,
                "mdd_si": line["mdd_day_usd"] if asset == "SI" else None,
                "replay_skips": price["replay"].get("occupancy_or_cap_skips"),
                "null_margin": price["by_asset"][asset]["adjusted_null_p"],
                "note": f"gated price read; {price['overall']}",
            })
    return rows


def write_report(report: Mapping[str, object]) -> None:
    OUT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True,
                                   default=S8._json_default) + "\n")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--log", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    started = time.time()
    mutant = _mutant()
    # The whole record is keyed on Entry.cell indexing the FILTERED record list,
    # so this unit never subsets the assets: it would silently misalign cash.
    cells, days, skipped = S8.build_cells(ASSETS)
    records, _days = S1.load_cache()
    records = [rec for rec in records if rec.asset in ASSETS]
    explore_days = S1._explore_days(ASSETS)
    run, book = record_gate(cells)
    receipt = reproduce_first(cells, run, book)
    report: dict[str, object] = {
        "schema": "QRE2MILLSWEEP13", "tier": "exploratory", "mutant": mutant,
        "spec_sha": SPEC_SHA, "code_sha": code_sha(), "split_sha": S1.split_sha(),
        "outcome_law_sha": S1.outcome_law_sha(), "seed": SEED,
        "parent_trial": PARENT_TRIAL, "family": FAMILY,
        "asset_days": days, "skipped_no_context": skipped,
        "cells": {asset: sum(1 for c in cells if c.asset == asset)
                  for asset in ASSETS},
        "cells_scored": dict(run.scored_cells),
        "law": {"ordinal": ORDINAL, "occurrence_window_s": OCC_WINDOW_S,
                "depth_atr": DEPTH_ATR, "remaining_min_s": REMAIN_MIN_S,
                "horizon_bars": HORIZON_BARS,
                "time_match_draws": TIME_MATCH_DRAWS,
                "time_match_window_s": TIME_MATCH_WINDOW_S,
                "block_draws": BLOCK_DRAWS},
        "reproduction": receipt,
    }
    print_repro(report)
    if receipt["verdict"] != "PASS":
        write_report(report)
        raise SweepRefusal(
            "the frozen sweep-8 PRIMARY reproduction failed; stage A refuses "
            "to run (see .audit/mill-sweep13.json 'reproduction')")
    idents = build_identities(cells, explore_days)
    second = run_second(cells, book, idents, mutant)
    control = time_match(second.takes, cells)
    report["time_match"] = control
    report["stage_a"] = stage_a(run.shots["PRIMARY"], second, book, cells,
                                control)
    report["paired"] = paired_block(run.shots["PRIMARY"], second.takes, control)
    report["ruling"] = rule(report)
    print_stage_a(report)
    print_ruling(report)
    if report["ruling"]["price_licensed"]:
        report["price"] = price_second(
            second.takes, records, days, run.scored_cells, explore_days,
            report["ruling"]["price_assets"])
        # The cap-skip bound is only readable after the replay, so the ruling is
        # recomputed once with it in hand rather than left stale.
        report["ruling"] = rule(report)
    print_price(report)
    report["log"] = log_rows(report)
    report["wall_seconds"] = round(time.time() - started, 1)
    write_report(report)
    if args.log:
        if mutant:
            raise SweepRefusal("a mutant run must never touch the hypothesis log")
        written = S1.append_log(report["log"])
        print(f"\nappended {written} hypothesis-log rows to {LOG_PATH}")
    print(f"\nwrote {OUT_PATH} in {report['wall_seconds']} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
