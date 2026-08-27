#!/usr/bin/env python3
"""Sweep 4 of the side-resolution mill: candidate-anchored terminal detection.

Exploratory tier.  EXPLORE-day bytes only, can kill, cannot promote.  The
sweep-3 cadence review caught two drifts and this sweep repairs both:

1. **Entry grain.**  Sweeps 1-3 declared at 60 s bar closes; the deployable
   system enters CLEAR candidates at their own decision moments (S0's identity,
   2753/3806/3869 usd per asset-day era-wide).  Every entry law here is
   CANDIDATE-ANCHORED: an entry intent at candidate row ``i`` of a cell means
   entry timestamp = that candidate's ``decision_ts_ns``, entry quote = the last
   trusted row strictly before it (``0 < bid < ask``), frozen cost from that
   row's spread, side = the candidate's own side, outcome from the mill index
   under the generation law.  Legality is inherent: the candidate IS formed.
2. **The stage-A metric.**  Sweep 2 selected on side error and picked the
   fastest (worst) quiet configs.  The metric here is TERMINAL-HIT RATE: an
   entry counts iff no new adverse extreme prints between entry and phase
   close.  Sweep 3 measured wall 0.000 at true terminal entries, so terminal
   hit controls cash and drawdown together.

Bar grain survives only where it belongs: the running-extreme geometry the
detector watches, sampled on the same 60 s completed-bar lattice (value at a
close is the last trusted row strictly before it).

Stages:

  STAGE O  oracles, no selection.  O4a the S0 replica (best-priced winner-side
           candidate at its own decision_ts) plus its second-best line,
           reconciled against the S0 era numbers and the REM ceiling.  O4b the
           recognition-delay budget curve (first winner-side candidate d
           minutes after the terminal extreme's bar close, d up to 60).  O4c
           terminality separability with no cash: quiet time after every new
           extreme, terminal vs non-terminal, the false-positive curve a
           quiet-Q detector faces, and the retrace bounce.
  STAGE A  the 72-config detector grid D(Q,H,k,zone), no cash, selected on the
           terminal-hit Wilson lower bound under a coverage floor.
  STAGE B  cash on the selected, the runner-up, and the per-session variant
           (each phase choosing its own Q by the same no-cash rule), with
           engine replay, a 2% adversarial stress, block-permutation nulls, and
           each line's per-trade mean beside its delay-matched O4b oracle.

Every table in every stage reports per (asset, phase_idx) as well as per asset:
phases are sessions and the USER directive makes the session dimension
first-class.

Laws carried unchanged, imported and never re-implemented: the 60 s completed
bar sampler, the Delta*/REM ``star_cell`` law, the bar extremes, the cash and
``_drawdown`` reductions, the engine replay shaping, the asset-day
block-permutation null, the Wilson interval, the r0 gate, ``append_log`` and
its 31 columns, and the ``ContextStore`` strictly-prior guard.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
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

from engine.entry_v2.confirmation_types import FEE_USD, NANOS_PER_SECOND
from engine.entry_v2.corpus_units import ASSET_MULTIPLIER

import context as CTX
import mill as M
import sweep1 as S1
import sweep2 as S2
import sweep3 as S3

# --------------------------------------------------------------------------
# The immutable law this sweep registers before it reads anything.
# --------------------------------------------------------------------------

SPEC = """QRE2MILLSWEEP4
tier=exploratory; explore-only; can kill, cannot promote.  parent=sweep3-052.
entry grain (NEW, used by every line in every stage): CANDIDATE-ANCHORED.  An
  entry intent at candidate row i of a cell means entry_ts = that candidate's
  decision_ts_ns; entry quote = the last trusted row strictly before it with
  0<bid<ask; frozen cost = (ask-bid)*multiplier/1e9 + fee from that row; side =
  the candidate's own side; outcome from the mill index with the generation
  law and the -900 wall / phase-close exit.  Legality is inherent (the
  candidate is formed).  One entry per cell; entry_ts <= phase_close - 1800 s;
  seed 20260827.
bar grain (geometry only): 60 s completed bars, value at close t = the last
  trusted row strictly before t.  New running extremes of the bar mid are
  sweep 2's ``extremes``.
per cell: W = sign(Delta*(tau=900 s)) under the LEGAL variant and the
  max(2*cost,100) ambiguity band (sweep 2 star_cell); cells not sharp at 900 s
  are AMBIGUOUS, skipped by the oracle lines and counted.  Terminal extreme on
  a direction = the LAST bar that sets a new running extreme on that
  direction; terminal extreme of the cell = the terminal extreme on W's
  adverse direction (down for W=+1).
STAGE O (no selection).  O4a S0 replica: the W-side CLEAR candidate with the
  best entry price (min cand entry_mid2 for W=+1, max for W=-1) entered at its
  own decision_ts, plus the second-best-priced candidate as its own line, plus
  a no-deadline variant for the S0-era reconciliation.  O4b delay tolerance:
  for d in {0,5,10,15,20,30,45,60} minutes the FIRST W-side candidate with
  decision_ts >= terminal_extreme_bar_close + d*60 s.  O4c terminality
  separability, no cash: quiet time from every new extreme to the next
  same-direction new extreme (or phase close), terminal vs non-terminal, the
  fraction of non-terminal quiets exceeding {10,15,20,30,45,60} minutes,
  the same conditioned on the sweep-3 A1m+0.25 zone or the |depth|<=0.35 ATR
  shallow band, and the max bounce in ATR units within {15,30} minutes.
STAGE A (no cash).  Detector D(Q,H,k,zone), both directions armed W-agnostically:
  a direction's extreme at bar j becomes DETECTED-terminal at bar T when
  T-j >= Q minutes with no newer same-direction extreme, and the retrace
  s*(mid[b]-mid[j])/ATR held >= H for every b in [T-k+1, T].  zone=none
  monitors every extreme; zone=zoned monitors extremes inside the union of the
  A1m+0.25 zone and the |depth from phase open| <= 0.35 ATR band.  On detection
  the entry intent is the first CLEAR candidate on the fade side with
  decision_ts >= the detection bar close; a newer same-direction extreme
  landing at or before that candidate cancels the detection and re-arms on the
  new extreme; abstain when nothing lands by phase_close - 1800 s.  One entry
  per cell, earliest detection-entry wins across the two directions.
  Grid Q in {10,15,20,30,45,60} min, H in {0.10,0.20,0.30} ATR, k in {1,3},
  zone in {none, zoned} = 72 configs.  Metrics per config per asset and per
  (asset, phase_idx): coverage, terminal-hit rate (no new adverse extreme
  between entry and phase close) with a Wilson 95% CI, median detection delay
  after the true terminal extreme, median entry time, no-detection and
  no-candidate rates.
selection (per asset, no cash): maximise the terminal-hit Wilson lower bound
  subject to coverage >= 0.30; ties to the smaller median detection delay,
  then simpler (zone=none first, then smaller Q, H, k), then key.  Best and
  runner-up.
STAGE B (cash): the selected, the runner-up, and the per-session variant (each
  phase choosing its own Q by the same no-cash rule inside the selected H, k
  and zone), each priced on its own asset; engine replay of each asset's best
  (partial-day label); a 2% adversarial stress (round(0.02*entries) entries
  flipped to the opposite side at the same timestamps, the legal flips with the
  largest cert damage taken); asset-day block-permutation nulls, 200 draws,
  seed 20260827, max-statistic across every priced line; and each line's
  per-trade mean against the O4b oracle whose d is nearest the line's median
  detection delay.
"""

SCHEMA = "QRE2MILLSWEEP4"
SEED = S1.SEED
BAR_SECONDS = S1.BAR_SECONDS
BAR_NS = S1.BAR_NS
ASSETS = S1.ASSETS
DAY_RUNG_USD = S1.DAY_RUNG_USD
MDD_CAP_USD = S1.MDD_CAP_USD

W_TAU_SECONDS = 900
W_BAR = W_TAU_SECONDS // BAR_SECONDS
REMAIN_SECONDS = 1800
REMAIN_NS = REMAIN_SECONDS * NANOS_PER_SECOND

DELAY_MINUTES = (0, 5, 10, 15, 20, 30, 45, 60)
PHASE_DELAY_MINUTES = (0, 15, 30, 60)
QUIET_MINUTES = (10, 15, 20, 30, 45, 60)
BOUNCE_MINUTES = (15, 30)
SHALLOW_ATR = 0.35
ZONE_KEY = "A1m+0.25"

Q_GRID = (10, 15, 20, 30, 45, 60)
H_GRID = (0.10, 0.20, 0.30)
K_GRID = (1, 3)
ZONE_GRID = ("none", "zoned")
COVERAGE_FLOOR = 0.30
STRESS_RATE = 0.02
NULL_DRAWS = S1.NULL_DRAWS
CEILING_TAU = "900"

# S0's era-wide per-asset-day cash, the object O4a replicates on EXPLORE.
S0_ERA_USD_DAY = {"HG": 2753.0, "NKD": 3806.0, "SI": 3869.0}

MUTANT_ENTRY_AT_BAR = "sweep4_entry_at_bar"
PARENT_TRIAL = "sweep3-052"
SELECTION_RULE = "hit_ci_low>coverage0.30>delay>simplicity"
FAMILY = "F1-TERMDETECT"

OUT_PATH = ROOT / ".audit/mill-sweep4.json"
CEILING_PATH = ROOT / ".audit/mill-rem-ceiling.json"
LOG_PATH = S1.LOG_PATH
SPLIT_PATH = S1.SPLIT_PATH
CACHE_NPZ = S1.CACHE_DIR / "sweep4_cands.npz"
CACHE_JSON = S1.CACHE_DIR / "sweep4_cands.json"


class SweepRefusal(RuntimeError):
    pass


SPEC_SHA = S1._sha_text(SPEC)


def code_sha() -> str:
    return S1._sha_file(Path(__file__).resolve())


def split_sha() -> str:
    return S1.split_sha()


def outcome_law_sha() -> str:
    return S1.outcome_law_sha()


def _sweep_mutant() -> str:
    """The sweep-4 mutant name, validated against the mill's registry."""

    name = os.environ.get("QRE2_MILL_MUTANT", "")
    if name and name not in M.MUTANTS:
        raise SweepRefusal(f"unknown mill mutant: {name}")
    return name


# --------------------------------------------------------------------------
# The candidate plane: the one seam that turns decision timestamps into fills.
# --------------------------------------------------------------------------

def bar_anchor_ts(cand_ts: np.ndarray, phase_open_ts_ns: int) -> np.ndarray:
    """Close of the last completed 60 s bar at or before each decision stamp.

    This is the quote source the BAR-grain law (sweeps 1-3) would have used for
    the same entry, and it is exactly what the mutant substitutes.
    """

    offset = np.asarray(cand_ts, np.int64) - int(phase_open_ts_ns)
    return int(phase_open_ts_ns) + (offset // BAR_NS) * BAR_NS


def price_candidates(index: M.MillIndex, asset: str, cand_ts: np.ndarray,
                     phase_open_ts_ns: int, phase_close_ts_ns: int,
                     raw_ts: np.ndarray) -> dict[str, np.ndarray]:
    """Fill every candidate-anchored entry of one cell, both sides.

    The law: entry timestamp is the candidate's own ``decision_ts_ns``; the
    entry quote is the last trusted row STRICTLY before it and must satisfy
    ``0 < bid < ask``; the frozen cost is that row's spread by the frozen
    formula; the outcome is the mill index's own grid from that timestamp.

    ``QRE2_MILL_MUTANT=sweep4_entry_at_bar`` takes the quote and the cost from
    the last completed bar close instead of the candidate's own decision row.
    The entry timestamp, and therefore the outcome window, is untouched: this
    is the entry-QUOTE mutant, and it is the one branch in this module.
    """

    times = np.asarray(cand_ts, np.int64)
    if times.ndim != 1:
        raise SweepRefusal("candidate stamps must be a 1-D array")
    if len(times) and not bool(np.all((times >= int(phase_open_ts_ns))
                                      & (times < int(phase_close_ts_ns)))):
        raise SweepRefusal("a candidate stamp fell outside its own phase")
    anchor = bar_anchor_ts(times, phase_open_ts_ns)
    source = anchor if _sweep_mutant() == MUTANT_ENTRY_AT_BAR else times
    position = index.positions(source)
    taken = np.maximum(position, 0)
    bid = index.bid[taken].astype(np.int64) if len(index.ts) else np.zeros(len(times), np.int64)
    ask = index.ask[taken].astype(np.int64) if len(index.ts) else np.zeros(len(times), np.int64)
    mid2 = (index.mid2[taken].astype(np.int64) if len(index.ts)
            else np.zeros(len(times), np.int64))
    quote_ok = (position >= 0) & (bid > 0) & (ask > bid)
    cost = (ask - bid) * float(ASSET_MULTIPLIER[asset]) / 1e9 + FEE_USD
    stamps = np.asarray(raw_ts, np.int64)
    raw_cut = np.searchsorted(stamps, times, side="left").astype(np.int64)
    raw_last = (stamps[np.maximum(raw_cut - 1, 0)] if len(stamps)
                else np.zeros(len(times), np.int64))
    out: dict[str, np.ndarray] = {
        "anchor_ts": anchor, "quote_mid2": mid2, "cost": cost,
        "quote_ok": quote_ok, "raw_cut": raw_cut, "raw_last": raw_last,
        "bid": bid, "ask": ask}
    for side, tag in ((1, "p"), (-1, "m")):
        cert = np.zeros(len(times), np.float64)
        wall = np.zeros(len(times), np.bool_)
        exit_ts = np.zeros(len(times), np.int64)
        ok = np.zeros(len(times), np.bool_)
        grid = index.outcomes_grid(times, side, int(phase_close_ts_ns),
                                   entry_mid2=mid2, cost_usd=cost)
        keep = grid["input_index"]
        if len(keep):
            cert[keep] = grid["cert_close_usd"]
            wall[keep] = grid["wall_hit"]
            exit_ts[keep] = grid["exit_ts_ns"]
            ok[keep] = True
        out[f"cert_{tag}"] = cert
        out[f"wall_{tag}"] = wall
        out[f"exit_{tag}"] = exit_ts
        out[f"ok_{tag}"] = ok & quote_ok
    return out


CAND_ARRAYS = (
    ("ts", np.int64), ("side", np.int8), ("cand_mid2", np.int64),
    ("quote_mid2", np.int64), ("cost", np.float64), ("anchor_ts", np.int64),
    ("raw_cut", np.int64), ("raw_last", np.int64),
    ("cert_p", np.float64), ("cert_m", np.float64),
    ("wall_p", np.bool_), ("wall_m", np.bool_),
    ("exit_p", np.int64), ("exit_m", np.int64),
    ("ok_p", np.bool_), ("ok_m", np.bool_),
)


@dataclass(slots=True)
class CandCell:
    """Every CLEAR candidate of one cell, priced at its own decision stamp."""

    text: str
    phase_idx: int
    first_ts_p: int          # earliest LONG formation, -1 when the side never forms
    first_ts_m: int
    ts: np.ndarray
    side: np.ndarray
    cand_mid2: np.ndarray
    quote_mid2: np.ndarray
    cost: np.ndarray
    anchor_ts: np.ndarray
    raw_cut: np.ndarray
    raw_last: np.ndarray
    cert_p: np.ndarray
    cert_m: np.ndarray
    wall_p: np.ndarray
    wall_m: np.ndarray
    exit_p: np.ndarray
    exit_m: np.ndarray
    ok_p: np.ndarray
    ok_m: np.ndarray

    @property
    def n(self) -> int:
        return int(len(self.ts))

    def cert(self, side: int) -> np.ndarray:
        return self.cert_p if int(side) > 0 else self.cert_m

    def wall(self, side: int) -> np.ndarray:
        return self.wall_p if int(side) > 0 else self.wall_m

    def exit_ts(self, side: int) -> np.ndarray:
        return self.exit_p if int(side) > 0 else self.exit_m

    def ok(self, side: int) -> np.ndarray:
        return self.ok_p if int(side) > 0 else self.ok_m

    def first_ts(self, side: int) -> int:
        return self.first_ts_p if int(side) > 0 else self.first_ts_m

    def usable(self, side: int) -> np.ndarray:
        """Rows this cell may enter on ``side``: own side and certifiable."""

        return (self.side == int(side)) & self.ok(side)


def build_cand_cells(shard: M.Shard) -> list[CandCell]:
    cells: list[CandCell] = []
    raw = shard.raw_ts.astype(np.int64)
    for cell in shard.cells:
        index = shard.cell_index(cell)
        if not len(index.ts):
            continue
        order = sorted(cell.rows, key=lambda row: (int(shard.decision_ts_ns[row]),
                                                   shard.candidate_ids[row]))
        rows = np.asarray(order, np.int64)
        times = shard.decision_ts_ns[rows].astype(np.int64)
        sides = shard.side[rows].astype(np.int8)
        filled = price_candidates(index, shard.asset, times,
                                  int(cell.phase_open_ts_ns),
                                  int(cell.phase_close_ts_ns), raw)
        first = {}
        for side, tag in ((1, "p"), (-1, "m")):
            same = times[sides == side]
            first[tag] = int(same.min()) if len(same) else -1
        cells.append(CandCell(
            text=cell.text, phase_idx=int(cell.phase_idx),
            first_ts_p=first["p"], first_ts_m=first["m"],
            ts=times, side=sides,
            cand_mid2=shard.entry_mid2[rows].astype(np.int64),
            quote_mid2=filled["quote_mid2"], cost=filled["cost"],
            anchor_ts=filled["anchor_ts"], raw_cut=filled["raw_cut"],
            raw_last=filled["raw_last"],
            cert_p=filled["cert_p"], cert_m=filled["cert_m"],
            wall_p=filled["wall_p"], wall_m=filled["wall_m"],
            exit_p=filled["exit_p"], exit_m=filled["exit_m"],
            ok_p=filled["ok_p"], ok_m=filled["ok_m"]))
    return cells


def build_cands(store: M.CellStore) -> dict[str, CandCell]:
    out: dict[str, CandCell] = {}
    for shard in store.shards():
        for cell in build_cand_cells(shard):
            if cell.text in out:
                raise SweepRefusal(f"duplicate cell identity: {cell.text}")
            out[cell.text] = cell
    return out


def save_cand_cache(cells: Mapping[str, CandCell], mutant: str) -> None:
    S1.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    order = sorted(cells)
    offsets = np.cumsum([0] + [cells[key].n for key in order]).astype(np.int64)
    payload = {name: np.concatenate(
        [getattr(cells[key], name) for key in order]).astype(dtype)
        for name, dtype in CAND_ARRAYS}
    payload["offsets"] = offsets
    with CACHE_NPZ.open("wb") as handle:
        np.savez(handle, **payload)
    CACHE_JSON.write_text(json.dumps({
        "schema": SCHEMA, "spec_sha": SPEC_SHA, "split_sha": split_sha(),
        "mutant": mutant,
        "cells": [{"text": key, "phase_idx": cells[key].phase_idx,
                   "first_ts_p": cells[key].first_ts_p,
                   "first_ts_m": cells[key].first_ts_m} for key in order],
    }, sort_keys=True))


def load_cand_cache(mutant: str) -> dict[str, CandCell]:
    if not (CACHE_NPZ.is_file() and CACHE_JSON.is_file()):
        raise SweepRefusal("candidate cache is absent")
    meta = json.loads(CACHE_JSON.read_text())
    if (meta.get("spec_sha") != SPEC_SHA or meta.get("split_sha") != split_sha()
            or meta.get("mutant", "") != mutant):
        raise SweepRefusal("candidate cache was built under a different law")
    data = np.load(CACHE_NPZ)
    offsets = data["offsets"]
    out: dict[str, CandCell] = {}
    for position, scalars in enumerate(meta["cells"]):
        lo, hi = int(offsets[position]), int(offsets[position + 1])
        arrays = {name: data[name][lo:hi] for name, _dtype in CAND_ARRAYS}
        out[str(scalars["text"])] = CandCell(
            text=str(scalars["text"]), phase_idx=int(scalars["phase_idx"]),
            first_ts_p=int(scalars["first_ts_p"]),
            first_ts_m=int(scalars["first_ts_m"]), **arrays)
    return out


def cands_for(records: Sequence[S1.CellRec], assets: Sequence[str], root: Path,
              mutant: str) -> list[CandCell]:
    try:
        table = load_cand_cache(mutant)
    except SweepRefusal:
        table = build_cands(M.load_store(SPLIT_PATH, assets, root=root))
        save_cand_cache(table, mutant)
    missing = [rec.text for rec in records if rec.text not in table]
    if missing:
        raise SweepRefusal(f"{len(missing)} cells carry no candidate plane")
    return [table[rec.text] for rec in records]


# --------------------------------------------------------------------------
# Cell plane: bar geometry, the winner side, and the detector's arrays.
# --------------------------------------------------------------------------

def terminal_extreme_bar(ext: S2.Extremes, side: int) -> int:
    """Last bar setting a new running extreme on ``side``'s adverse direction.

    A LONG fade's adverse direction is down, so its terminal extreme is the
    last bar that printed a new running minimum.  ``-1`` when the direction
    never printed a new extreme (the phase's first bar held the extreme).
    """

    flag = ext.new_low if int(side) > 0 else ext.new_high
    found = np.flatnonzero(np.asarray(flag, bool))
    return int(found[-1]) if len(found) else -1


def rolling_min(values: np.ndarray, window: int) -> np.ndarray:
    """Minimum over ``[b-window+1, b]``; the first ``window-1`` slots are -inf."""

    out = np.asarray(values, np.float64).copy()
    for shift in range(1, int(window)):
        out[shift:] = np.minimum(out[shift:], values[:-shift])
    out[:int(window) - 1] = -np.inf
    return out


@dataclass(slots=True)
class SideGeometry:
    """Everything the detector needs for one cell on one fade side."""

    anchor: np.ndarray       # bar index of the current running extreme, -1 before the first
    age: np.ndarray          # bars since that extreme
    retrace: np.ndarray      # side*(mid - mid[anchor]) / ATR, -inf where undefined
    gated: np.ndarray        # the anchor extreme sits in the zoned monitor set
    stop_ns: np.ndarray      # stamp of the next same-direction extreme, else phase close
    held: dict[tuple[float, int], np.ndarray]
    cand_ts: np.ndarray      # enterable same-side candidate stamps, ascending
    cand_row: np.ndarray     # their rows in the CandCell arrays
    terminal_bar: int


def side_geometry(rec: S1.CellRec, ext: S2.Extremes, ctx: S3.Ctx,
                  cand: CandCell, side: int) -> SideGeometry:
    flag = np.asarray(ext.new_low if int(side) > 0 else ext.new_high, bool)
    order = np.arange(rec.n, dtype=np.int64)
    anchor = np.maximum.accumulate(np.where(flag, order, -1))
    age = order - anchor
    mid = np.asarray(rec.mid, np.float64)
    retrace = int(side) * (mid - mid[np.maximum(anchor, 0)]) / ctx.atr_mid2
    retrace[anchor < 0] = -np.inf
    zone_masks = S3.zone_masks(rec, ctx, S3.ZONE_BY_KEY[ZONE_KEY])
    in_zone = np.asarray(zone_masks[0] if int(side) > 0 else zone_masks[1], bool)
    shallow = np.abs(mid - ctx.open_mid2) / ctx.atr_mid2 <= SHALLOW_ATR
    monitor = in_zone | shallow
    gated = np.where(anchor < 0, False, monitor[np.maximum(anchor, 0)])
    marks = np.flatnonzero(flag)
    if len(marks):
        following = np.searchsorted(marks, order, side="right")
        stop_bar = np.where(following < len(marks),
                            marks[np.minimum(following, len(marks) - 1)], -1)
    else:
        stop_bar = np.full(rec.n, -1, np.int64)
    stop_ns = np.where(stop_bar >= 0, rec.lat[np.maximum(stop_bar, 0)],
                       int(rec.phase_close_ts_ns)).astype(np.int64)
    held = {(h, k): (rolling_min(retrace, k) >= h)
            for h in H_GRID for k in K_GRID}
    rows = np.flatnonzero(cand.usable(side))
    return SideGeometry(anchor, age, retrace, gated, stop_ns, held,
                        cand.ts[rows], rows, terminal_extreme_bar(ext, side))


@dataclass(slots=True)
class Plane:
    records: list[S1.CellRec]
    cands: list[CandCell]
    exts: list[S2.Extremes]
    stars: list[S2.Star]
    ctxs: list[S3.Ctx | None]
    winner: list[int]                       # 0 when the cell is ambiguous at tau=900
    geometry: list[dict[int, SideGeometry] | None]
    days: dict[str, int]
    cells: dict[str, int]
    phase_cells: dict[tuple[str, int], int]
    phases: dict[str, tuple[int, ...]]
    diagnostics: dict[str, object]

    def deadline_ts(self, position: int) -> int:
        return int(self.records[position].phase_close_ts_ns) - REMAIN_NS

    def terminal_ts(self, position: int, side: int) -> int:
        """Bar close of the terminal extreme on ``side``'s adverse direction."""

        bar = terminal_extreme_bar(self.exts[position], side)
        rec = self.records[position]
        return -1 if bar < 0 else int(rec.lat[bar])


def winner_side(star: S2.Star, rec: S1.CellRec) -> int:
    if rec.n <= W_BAR or not bool(star.sharp[W_BAR]):
        return 0
    return int(star.sign[W_BAR])


def build_plane(records: Sequence[S1.CellRec], cands: Sequence[CandCell],
                store: CTX.ContextStore, days: Mapping[str, int]) -> Plane:
    exts = [S2.extremes(rec) for rec in records]
    stars = S2.stars_for(records, "legal", "max2cost100")
    ctxs = S3.contexts_for(records, store)
    winner = [winner_side(star, rec) for star, rec in zip(stars, records)]
    geometry: list[dict[int, SideGeometry] | None] = []
    for position, rec in enumerate(records):
        ctx = ctxs[position]
        if ctx is None:
            geometry.append(None)
            continue
        geometry.append({side: side_geometry(rec, exts[position], ctx,
                                             cands[position], side)
                         for side in (1, -1)})
    phase_cells: dict[tuple[str, int], int] = {}
    phases: dict[str, set[int]] = {}
    for rec, cell in zip(records, cands):
        key = (rec.asset, cell.phase_idx)
        phase_cells[key] = phase_cells.get(key, 0) + 1
        phases.setdefault(rec.asset, set()).add(cell.phase_idx)
    dropped = int(sum(int(np.count_nonzero(
        (cell.side == side) & ~cell.ok(side))) for cell in cands
        for side in (1, -1)))
    total = int(sum(cell.n for cell in cands))
    matched = int(sum(int(np.count_nonzero(cell.cand_mid2 == cell.quote_mid2))
                      for cell in cands))
    return Plane(
        list(records), list(cands), exts, stars, ctxs, winner, geometry,
        dict(days), S1.cells_by_asset(records), phase_cells,
        {asset: tuple(sorted(value)) for asset, value in sorted(phases.items())},
        {"candidates": total, "uncertifiable_own_side": dropped,
         "stored_entry_mid2_equals_recomputed_quote": matched,
         "stored_quote_agreement": matched / max(1, total),
         "cells_without_context": int(sum(1 for ctx in ctxs if ctx is None)),
         "ambiguous_cells": int(sum(1 for side in winner if side == 0))})


# --------------------------------------------------------------------------
# Entries.  Candidate-anchored, so the "bar" field is a candidate ordinal.
# --------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Entry:
    """One candidate-anchored trade.

    Field names match ``sweep1.Entry`` so every cash reduction there applies
    unchanged; ``bar`` is the candidate's ordinal inside its cell, not a
    lattice index, and the raw prefix bounds travel with the row because they
    are read at the decision stamp rather than at a bar close.
    """

    cell: int
    asset: str
    d8: int
    bar: int
    ts_ns: int
    side: int
    cert_usd: float
    wall: bool
    exit_ts_ns: int
    text: str
    raw_cut: int
    raw_last: int
    phase_idx: int
    detect_bar: int
    hit: bool
    delay_s: float


def make_entry(plane: Plane, position: int, row: int, side: int,
               detect_bar: int = -1) -> Entry | None:
    """The candidate-anchored entry at candidate ``row``, or ``None``."""

    cell = plane.cands[position]
    rec = plane.records[position]
    if not 0 <= int(row) < cell.n or int(side) not in (1, -1):
        return None
    if int(cell.side[row]) != int(side) or not bool(cell.ok(side)[row]):
        return None
    stamp = int(cell.ts[row])
    if stamp > plane.deadline_ts(position):
        return None
    terminal = plane.terminal_ts(position, side)
    return Entry(
        cell=position, asset=rec.asset, d8=rec.d8, bar=int(row), ts_ns=stamp,
        side=int(side), cert_usd=float(cell.cert(side)[row]),
        wall=bool(cell.wall(side)[row]), exit_ts_ns=int(cell.exit_ts(side)[row]),
        text=rec.text, raw_cut=int(cell.raw_cut[row]),
        raw_last=int(cell.raw_last[row]), phase_idx=int(cell.phase_idx),
        detect_bar=int(detect_bar), hit=bool(terminal < 0 or stamp >= terminal),
        delay_s=(float("nan") if terminal < 0
                 else (stamp - terminal) / NANOS_PER_SECOND))


def entry_seconds(plane: Plane, row: Entry) -> float:
    rec = plane.records[row.cell]
    return float(row.ts_ns - int(rec.phase_open_ts_ns)) / NANOS_PER_SECOND


def detect_delay_seconds(plane: Plane, row: Entry) -> float:
    """Detection bar close minus the faded direction's terminal extreme."""

    if row.detect_bar < 0:
        return float("nan")
    terminal = plane.terminal_ts(row.cell, row.side)
    if terminal < 0:
        return float("nan")
    rec = plane.records[row.cell]
    return float(int(rec.lat[row.detect_bar]) - terminal) / NANOS_PER_SECOND


# --------------------------------------------------------------------------
# Cash tables, per asset and per (asset, phase_idx).
# --------------------------------------------------------------------------

def _median(values: Sequence[float]) -> float | None:
    kept = [value for value in values if value == value]
    return float(np.median(kept)) if kept else None


def cash_by_asset(entries: Sequence[Entry], plane: Plane) -> dict[str, dict]:
    line = S1.cash_line(entries, plane.days, plane.cells)
    for asset in ASSETS:
        rows = [row for row in entries if row.asset == asset]
        line[asset].update({
            "terminal_hits": int(sum(row.hit for row in rows)),
            "terminal_hit_rate": (float(np.mean([row.hit for row in rows]))
                                  if rows else None),
            "entry_seconds_median": _median([entry_seconds(plane, row)
                                             for row in rows]),
            "entry_delay_median_s": _median([row.delay_s for row in rows]),
            "detect_delay_median_s": _median([detect_delay_seconds(plane, row)
                                              for row in rows]),
            "rung_usd": DAY_RUNG_USD[asset]})
    return line


def cash_by_phase(entries: Sequence[Entry], plane: Plane
                  ) -> dict[str, dict[str, dict]]:
    """Per (asset, phase) cash.  Days stay the asset's, so phases add up."""

    out: dict[str, dict[str, dict]] = {}
    for asset in ASSETS:
        out[asset] = {}
        for phase in plane.phases.get(asset, ()):
            rows = [row for row in entries
                    if row.asset == asset and row.phase_idx == phase]
            certs = np.asarray([row.cert_usd for row in rows], np.float64)
            n_days = max(1, int(plane.days.get(asset, 0)))
            cells = max(1, plane.phase_cells.get((asset, phase), 1))
            out[asset][str(phase)] = {
                "phase_idx": phase, "cells": plane.phase_cells.get((asset, phase), 0),
                "trades": len(rows), "coverage": len(rows) / cells,
                "usd_per_asset_day": float(certs.sum() / n_days) if len(certs) else 0.0,
                "usd_per_trade": float(certs.mean()) if len(certs) else None,
                "win_rate": float((certs > 0).mean()) if len(certs) else None,
                "wall_rate": (float(np.mean([row.wall for row in rows]))
                              if rows else None),
                "walls": int(sum(row.wall for row in rows)),
                "mdd_day_usd": S1.asset_mdd_day(rows, asset),
                "mdd_trade_usd": S1.asset_mdd_trade(rows, asset),
                "terminal_hit_rate": (float(np.mean([row.hit for row in rows]))
                                      if rows else None),
                "entry_seconds_median": _median([entry_seconds(plane, row)
                                                 for row in rows]),
                "detect_delay_median_s": _median(
                    [detect_delay_seconds(plane, row) for row in rows]),
            }
    return out


def line_block(entries: Sequence[Entry], plane: Plane,
               skips: Mapping[str, Mapping[str, int]]) -> dict[str, object]:
    return {"by_asset": cash_by_asset(entries, plane),
            "by_phase": cash_by_phase(entries, plane),
            "skips": {asset: dict(book) for asset, book in skips.items()}}


def _skipbook() -> dict[str, dict[str, int]]:
    return {asset: {"cells": 0, "ambiguous": 0, "no_context": 0, "no_terminal": 0,
                    "no_candidate": 0, "past_deadline": 0, "entered": 0}
            for asset in ASSETS}


# --------------------------------------------------------------------------
# STAGE O.
# --------------------------------------------------------------------------

def _eligible_rows(plane: Plane, position: int, side: int,
                   floor_ts: int | None = None) -> np.ndarray:
    """Enterable same-side candidate rows inside the deadline."""

    cell = plane.cands[position]
    keep = cell.usable(side) & (cell.ts <= plane.deadline_ts(position))
    if floor_ts is not None:
        keep &= cell.ts >= int(floor_ts)
    return np.flatnonzero(keep)


def o4a_line(plane: Plane, rank: int, deadline: bool) -> tuple[list[Entry],
                                                               dict[str, dict[str, int]]]:
    """The S0 replica at price rank ``rank`` (0 = best-priced, 1 = second).

    ``deadline`` ranks inside the 1800 s-remaining pool.  With it off the rank
    is taken over every enterable candidate and the cell is then dropped when
    that candidate sits past the deadline: the carried law is never bypassed,
    so the drop count measures how much of S0's price-order identity the
    1800 s rule removes.
    """

    entries: list[Entry] = []
    skips = _skipbook()
    for position, rec in enumerate(plane.records):
        book = skips[rec.asset]
        book["cells"] += 1
        side = plane.winner[position]
        if not side:
            book["ambiguous"] += 1
            continue
        cell = plane.cands[position]
        keep = cell.usable(side)
        if deadline:
            keep &= cell.ts <= plane.deadline_ts(position)
        rows = np.flatnonzero(keep)
        if len(rows) <= rank:
            book["no_candidate"] += 1
            continue
        # Deepest in W's favour: the lowest entry_mid2 for a long winner, the
        # highest for a short.  Stable sort keeps the earliest stamp on ties.
        order = np.argsort(side * cell.cand_mid2[rows], kind="stable")
        entry = make_entry(plane, position, int(rows[order[rank]]), side)
        if entry is None:
            book["past_deadline"] += 1
            continue
        book["entered"] += 1
        entries.append(entry)
    return entries, skips


def o4a(plane: Plane) -> dict[str, object]:
    ceiling = json.loads(CEILING_PATH.read_text())
    out: dict[str, object] = {
        "ceiling_source": CEILING_PATH.name, "ceiling_tau": CEILING_TAU,
        "s0_era_usd_day": dict(S0_ERA_USD_DAY), "lines": {}}
    plan = (("S0R-BEST", 0, True), ("S0R-SECOND", 1, True),
            ("S0R-BEST-UNFILTERED", 0, False))
    for name, rank, deadline in plan:
        entries, skips = o4a_line(plane, rank, deadline)
        block = line_block(entries, plane, skips)
        for asset in ASSETS:
            rung = ceiling.get(asset, {}).get(CEILING_TAU, {})
            usd = block["by_asset"][asset]["usd_per_asset_day"]
            block["by_asset"][asset].update({
                "rem_ceiling_legal_usd_day": rung.get("ceil_l_day"),
                "capture_of_ceiling": (usd / float(rung["ceil_l_day"])
                                       if rung.get("ceil_l_day") else None),
                "s0_era_usd_day": S0_ERA_USD_DAY[asset],
                "share_of_s0_era": usd / S0_ERA_USD_DAY[asset]})
        out["lines"][name] = block
    return out


def o4b_line(plane: Plane, minutes: int) -> tuple[list[Entry],
                                                  dict[str, dict[str, int]]]:
    entries: list[Entry] = []
    skips = _skipbook()
    for position, rec in enumerate(plane.records):
        book = skips[rec.asset]
        book["cells"] += 1
        side = plane.winner[position]
        if not side:
            book["ambiguous"] += 1
            continue
        terminal = plane.terminal_ts(position, side)
        if terminal < 0:
            book["no_terminal"] += 1
            continue
        floor = terminal + int(minutes) * BAR_SECONDS * NANOS_PER_SECOND
        rows = _eligible_rows(plane, position, side, floor)
        if not len(rows):
            book["no_candidate"] += 1
            continue
        entry = make_entry(plane, position, int(rows[0]), side)
        if entry is None:
            book["past_deadline"] += 1
            continue
        book["entered"] += 1
        entries.append(entry)
    return entries, skips


def o4b(plane: Plane) -> dict[str, object]:
    out: dict[str, object] = {"minutes": list(DELAY_MINUTES),
                              "phase_minutes": list(PHASE_DELAY_MINUTES),
                              "lines": {}}
    for minutes in DELAY_MINUTES:
        entries, skips = o4b_line(plane, minutes)
        block = line_block(entries, plane, skips)
        if minutes not in PHASE_DELAY_MINUTES:
            block.pop("by_phase")
        out["lines"][str(minutes)] = block
    return out


@dataclass(slots=True)
class ExtremeRow:
    """One new-extreme bar, with everything O4c splits on."""

    asset: str
    phase_idx: int
    side: int
    terminal: bool
    quiet_s: float
    in_zone: bool
    shallow: bool
    bounce: dict[int, float]


def extreme_rows(plane: Plane) -> list[ExtremeRow]:
    rows: list[ExtremeRow] = []
    for position, rec in enumerate(plane.records):
        ctx = plane.ctxs[position]
        if ctx is None:
            continue
        mid = np.asarray(rec.mid, np.float64)
        zone_masks = S3.zone_masks(rec, ctx, S3.ZONE_BY_KEY[ZONE_KEY])
        shallow = np.abs(mid - ctx.open_mid2) / ctx.atr_mid2 <= SHALLOW_ATR
        for side in (1, -1):
            flag = np.asarray(plane.exts[position].new_low if side > 0
                              else plane.exts[position].new_high, bool)
            marks = np.flatnonzero(flag)
            zone = np.asarray(zone_masks[0] if side > 0 else zone_masks[1], bool)
            for slot, bar in enumerate(marks):
                terminal = slot == len(marks) - 1
                stop = (int(rec.phase_close_ts_ns) if terminal
                        else int(rec.lat[marks[slot + 1]]))
                bounce: dict[int, float] = {}
                for window in BOUNCE_MINUTES:
                    top = min(rec.n - 1, int(bar) + window)
                    if top <= int(bar):
                        bounce[window] = 0.0
                        continue
                    moves = side * (mid[int(bar) + 1:top + 1] - mid[int(bar)])
                    bounce[window] = float(max(0.0, moves.max()) / ctx.atr_mid2)
                rows.append(ExtremeRow(
                    asset=rec.asset, phase_idx=plane.cands[position].phase_idx,
                    side=side, terminal=terminal,
                    quiet_s=float(stop - int(rec.lat[int(bar)])) / NANOS_PER_SECOND,
                    in_zone=bool(zone[int(bar)]), shallow=bool(shallow[int(bar)]),
                    bounce=bounce))
    return rows


def _o4c_summary(rows: Sequence[ExtremeRow]) -> dict[str, object]:
    terminal = [row for row in rows if row.terminal]
    other = [row for row in rows if not row.terminal]
    gated = [row for row in other if row.in_zone or row.shallow]
    gated_terminal = [row for row in terminal if row.in_zone or row.shallow]
    out: dict[str, object] = {
        "extremes": len(rows), "terminal": len(terminal),
        "non_terminal": len(other), "gated_non_terminal": len(gated),
        "gated_terminal": len(gated_terminal),
        "quiet_nonterminal_s": S1._quantiles([row.quiet_s for row in other],
                                             (10, 25, 50, 75, 90)),
        "quiet_terminal_s": S1._quantiles([row.quiet_s for row in terminal],
                                          (10, 25, 50, 75, 90)),
        "quiet_gated_nonterminal_s": S1._quantiles([row.quiet_s for row in gated],
                                                   (10, 25, 50, 75, 90)),
        "false_positive_curve": {}, "false_positive_curve_gated": {},
        "terminal_survives_curve": {}, "bounce": {}}
    for minutes in QUIET_MINUTES:
        cut = minutes * BAR_SECONDS
        out["false_positive_curve"][str(minutes)] = (
            float(np.mean([row.quiet_s > cut for row in other])) if other else None)
        out["false_positive_curve_gated"][str(minutes)] = (
            float(np.mean([row.quiet_s > cut for row in gated])) if gated else None)
        out["terminal_survives_curve"][str(minutes)] = (
            float(np.mean([row.quiet_s > cut for row in terminal]))
            if terminal else None)
    for window in BOUNCE_MINUTES:
        out["bounce"][str(window)] = {
            "terminal": S1._quantiles([row.bounce[window] for row in terminal]),
            "non_terminal": S1._quantiles([row.bounce[window] for row in other])}
    return out


def o4c(plane: Plane) -> dict[str, object]:
    rows = extreme_rows(plane)
    out: dict[str, object] = {
        "quiet_minutes": list(QUIET_MINUTES), "bounce_minutes": list(BOUNCE_MINUTES),
        "shallow_atr": SHALLOW_ATR, "zone": ZONE_KEY,
        "by_asset": {}, "by_phase": {}}
    for asset in ASSETS:
        kept = [row for row in rows if row.asset == asset]
        out["by_asset"][asset] = _o4c_summary(kept)
        out["by_phase"][asset] = {
            str(phase): _o4c_summary([row for row in kept if row.phase_idx == phase])
            for phase in plane.phases.get(asset, ())}
    return out


def stage_o(plane: Plane) -> dict[str, object]:
    return {"o4a": o4a(plane), "o4b": o4b(plane), "o4c": o4c(plane)}


# --------------------------------------------------------------------------
# STAGE A: the detector grid, no cash.
# --------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Detector:
    key: str
    q: int
    h: float
    k: int
    zone: str

    @property
    def simplicity(self) -> tuple:
        return (0 if self.zone == "none" else 1, self.q, self.h, self.k)

    @property
    def params(self) -> list:
        return [self.q, self.h, self.k, self.zone]


def detector_grid() -> tuple[Detector, ...]:
    out: list[Detector] = []
    for zone in ZONE_GRID:
        for q in Q_GRID:
            for h in H_GRID:
                for k in K_GRID:
                    out.append(Detector(f"Q{q}/H{h:.2f}/k{k}/{zone}",
                                        int(q), float(h), int(k), zone))
    return tuple(out)


DETECTORS = detector_grid()
DETECTOR_BY_KEY = {det.key: det for det in DETECTORS}


def detection_bars(geo: SideGeometry, det: Detector, deadline_ts: int,
                   lat: np.ndarray) -> np.ndarray:
    """Bars where this config declares the current extreme terminal."""

    live = geo.held[(det.h, det.k)] & (geo.age >= det.q) & (geo.anchor >= 0)
    live &= lat <= deadline_ts
    if det.zone != "none":
        live &= geo.gated
    return np.flatnonzero(live)


def side_shot(plane: Plane, position: int, side: int, det: Detector
              ) -> tuple[int, int] | None:
    """``(detection bar, candidate row)`` of this side's first entry, or None.

    A detection whose first fade-side candidate lands at or after the next
    same-direction extreme is cancelled: the detector re-arms on that new
    extreme, which the scan reaches on a later bar.
    """

    geometry = plane.geometry[position]
    if geometry is None:
        return None
    geo = geometry[side]
    rec = plane.records[position]
    deadline = plane.deadline_ts(position)
    bars = detection_bars(geo, det, deadline, rec.lat)
    if not len(bars) or not len(geo.cand_ts):
        return None
    slot = np.searchsorted(geo.cand_ts, rec.lat[bars], side="left")
    live = slot < len(geo.cand_ts)
    stamps = geo.cand_ts[np.minimum(slot, len(geo.cand_ts) - 1)]
    live &= (stamps < geo.stop_ns[bars]) & (stamps <= deadline)
    found = np.flatnonzero(live)
    if not len(found):
        return None
    first = int(found[0])
    return int(bars[first]), int(geo.cand_row[int(slot[first])])


def detector_entry(plane: Plane, position: int, det: Detector
                   ) -> tuple[Entry | None, str]:
    """The cell's one entry under ``det``, with the abstention reason."""

    if plane.geometry[position] is None:
        return None, "no_context"
    shots: list[tuple[int, int, int, int]] = []
    for side in (1, -1):
        shot = side_shot(plane, position, side, det)
        if shot is None:
            continue
        cell = plane.cands[position]
        shots.append((int(cell.ts[shot[1]]), shot[0], -side, shot[1]))
    if not shots:
        return None, "no_detection_entry"
    shots.sort()
    stamp, bar, negated, row = shots[0]
    entry = make_entry(plane, position, row, -negated, bar)
    return (entry, "entered") if entry is not None else (None, "unavailable")


def detector_line(plane: Plane, det: Detector,
                  per_phase: Mapping[int, int] | None = None,
                  asset: str | None = None
                  ) -> tuple[list[Entry], dict[str, dict[str, int]]]:
    entries: list[Entry] = []
    skips = {name: {"cells": 0, "no_context": 0, "no_detection_entry": 0,
                    "unavailable": 0, "entered": 0} for name in ASSETS}
    for position, rec in enumerate(plane.records):
        if asset is not None and rec.asset != asset:
            continue
        book = skips[rec.asset]
        book["cells"] += 1
        use = det
        if per_phase is not None:
            phase = plane.cands[position].phase_idx
            if phase not in per_phase:
                book["no_detection_entry"] += 1
                continue
            use = Detector(f"{det.key}@p{phase}", int(per_phase[phase]), det.h,
                           det.k, det.zone)
        entry, reason = detector_entry(plane, position, use)
        book[reason if entry is None else "entered"] += 1
        if entry is not None:
            entries.append(entry)
    return entries, skips


def _detector_stats(entries: Sequence[Entry], plane: Plane, asset: str,
                    cells: int, book: Mapping[str, int]) -> dict[str, object]:
    rows = list(entries)
    hits = int(sum(row.hit for row in rows))
    low, high = S1.wilson(hits, len(rows))
    delays = [detect_delay_seconds(plane, row) for row in rows]
    return {
        "cells": cells, "entered": len(rows),
        "coverage": len(rows) / max(1, cells),
        "terminal_hits": hits,
        "terminal_hit_rate": (hits / len(rows)) if rows else None,
        "ci95": [low, high],
        "detect_delay_median_s": _median(delays),
        "detect_delay_negative_rate": (float(np.mean([value < 0 for value in delays
                                                      if value == value]))
                                       if any(v == v for v in delays) else None),
        "entry_delay_median_s": _median([row.delay_s for row in rows]),
        "entry_seconds_median": _median([entry_seconds(plane, row) for row in rows]),
        "long_fraction": (float(np.mean([row.side > 0 for row in rows]))
                          if rows else None),
        "no_context": int(book.get("no_context", 0)),
        "no_detection_entry": int(book.get("no_detection_entry", 0)),
        "unavailable": int(book.get("unavailable", 0)),
        "no_candidate_rate": (int(book.get("no_detection_entry", 0))
                              + int(book.get("unavailable", 0))) / max(1, cells),
    }


def stage_a(plane: Plane) -> dict[str, object]:
    configs: dict[str, dict[str, object]] = {}
    for det in DETECTORS:
        entries, skips = detector_line(plane, det)
        per_asset: dict[str, dict[str, object]] = {}
        per_phase: dict[str, dict[str, dict[str, object]]] = {}
        for asset in ASSETS:
            rows = [row for row in entries if row.asset == asset]
            per_asset[asset] = _detector_stats(
                rows, plane, asset, plane.cells.get(asset, 0), skips[asset])
            per_phase[asset] = {}
            for phase in plane.phases.get(asset, ()):
                kept = [row for row in rows if row.phase_idx == phase]
                per_phase[asset][str(phase)] = _detector_stats(
                    kept, plane, asset, plane.phase_cells.get((asset, phase), 0), {})
        pooled = len(entries)
        configs[det.key] = {
            "params": det.params, "simplicity": list(det.simplicity),
            "by_asset": per_asset, "by_phase": per_phase,
            "entered_pooled": pooled,
            "coverage_pooled": pooled / max(1, sum(plane.cells.values())),
            "terminal_hit_pooled": (float(np.mean([row.hit for row in entries]))
                                    if entries else None),
            "detect_delay_median_pooled_s": _median(
                [detect_delay_seconds(plane, row) for row in entries]),
        }
    return {"coverage_floor": COVERAGE_FLOOR, "configs": configs,
            "selection": {asset: select_for_asset(configs, asset)
                          for asset in ASSETS}}


def _order_key(row: Mapping[str, object], simplicity: Sequence[float], key: str
               ) -> tuple:
    delay = row["detect_delay_median_s"]
    return (-float(row["ci95"][0]),
            float("inf") if delay is None else float(delay),
            tuple(simplicity), key)


def select_for_asset(configs: Mapping[str, Mapping[str, object]], asset: str
                     ) -> dict[str, object]:
    """Best and runner-up, no cash: hit CI lower bound, coverage floor, delay."""

    passing = [key for key, entry in configs.items()
               if float(entry["by_asset"][asset]["coverage"]) >= COVERAGE_FLOOR]
    flags: list[str] = []
    pool = passing
    if not pool:
        flags.append("COVERAGE_FAIL")
        pool = list(configs)
    ordered = sorted(pool, key=lambda key: _order_key(
        configs[key]["by_asset"][asset], configs[key]["simplicity"], key))
    return {"best": ordered[0],
            "runner_up": ordered[1] if len(ordered) > 1 else None,
            "flags": flags, "n_pass_coverage": len(passing),
            "ordered": ordered[:8]}


def select_phase_q(plane: Plane, det: Detector, asset: str) -> dict[str, object]:
    """Each phase picks its own Q by the stage-A rule, other params fixed."""

    by_q: dict[int, list[Entry]] = {}
    for q in Q_GRID:
        probe = Detector(f"Q{q}/H{det.h:.2f}/k{det.k}/{det.zone}", int(q),
                         det.h, det.k, det.zone)
        by_q[int(q)] = detector_line(plane, probe, asset=asset)[0]
    chosen: dict[int, int] = {}
    detail: dict[str, object] = {}
    for phase in plane.phases.get(asset, ()):
        cells = plane.phase_cells.get((asset, phase), 0)
        scored: list[tuple[tuple, int, dict[str, object]]] = []
        for q in Q_GRID:
            rows = [row for row in by_q[int(q)] if row.phase_idx == phase]
            stats = _detector_stats(rows, plane, asset, cells, {})
            simplicity = (0 if det.zone == "none" else 1, q, det.h, det.k)
            scored.append((_order_key(stats, simplicity, f"Q{q}"), int(q), stats))
        passing = [row for row in scored if row[2]["coverage"] >= COVERAGE_FLOOR]
        pool = passing or scored
        pool.sort(key=lambda row: row[0])
        chosen[phase] = pool[0][1]
        detail[str(phase)] = {
            "q": pool[0][1], "coverage_floor_met": bool(passing),
            "cells": cells, "candidates": {str(row[1]): {
                "coverage": row[2]["coverage"],
                "terminal_hit_rate": row[2]["terminal_hit_rate"],
                "ci_low": row[2]["ci95"][0],
                "detect_delay_median_s": row[2]["detect_delay_median_s"]}
                for row in scored}}
    return {"chosen": {str(key): value for key, value in chosen.items()},
            "detail": detail, "_chosen": chosen}


# --------------------------------------------------------------------------
# STAGE B: cash.
# --------------------------------------------------------------------------

def replay_line(entries: Sequence[Entry], records: Sequence[S1.CellRec],
                assets: Sequence[str], tag: str) -> dict[str, object]:
    """Sweep 1's replay shaping with candidate-anchored prefix bounds.

    Identical to ``sweep1.replay_line`` except that the raw prefix cutoff and
    last stamp come from the entry row (read at the decision stamp) instead of
    a lattice bar, because a candidate-anchored entry has no lattice bar.
    """

    keep = {position for position, rec in enumerate(records) if rec.asset in assets}
    sessions: dict[tuple[str, int], S1.SessionRef] = {}
    for position, rec in enumerate(records):
        if position in keep:
            sessions[(rec.asset, rec.d8)] = S1.SessionRef(
                rec.asset, rec.d8, str(rec.locked_iid))
    arrivals: list[S1.ScoredArrival] = []
    for row in sorted((row for row in entries if row.cell in keep),
                      key=lambda item: (item.ts_ns, item.text)):
        rec = records[row.cell]
        cutoff = int(row.raw_cut)
        prefix = S1.RawPrefixRef(
            f"mill/{rec.asset}/{rec.d8}.npz", 0, cutoff, cutoff,
            (rec.raw_first if cutoff else None),
            (int(row.raw_last) if cutoff else None), rec.pack_sha256)
        opportunity = f"MILL4-{rec.text.replace('/', '-')}-{row.bar}"
        example = S1.CausalEntryExample(
            opportunity, rec.asset, rec.d8, str(rec.locked_iid), row.ts_ns,
            S1.Side.LONG if row.side > 0 else S1.Side.SHORT, rec.phase,
            rec.locked_iid, prefix, {"frozen_rule_snapshot_present": 1.0}, None,
            S1._sha_text(f"{opportunity}|{tag}"))
        score = S1.EntryScore(opportunity, rec.asset, row.ts_ns, tag,
                              0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0, True)
        outcome = S1.ReplayOutcome(
            opportunity, row.exit_ts_ns, float(row.cert_usd),
            rec.phase_close_ts_ns, float(row.cert_usd),
            row.exit_ts_ns if row.wall else None,
            float(row.cert_usd) if row.wall else -900.0)
        arrivals.append(S1.ScoredArrival(example, score, outcome))
    if not arrivals:
        return {"status": "EMPTY_ARRIVALS"}
    evaluation = S1.replay(tuple(sorted(
        arrivals, key=lambda item: (item.example.decision_ts_ns,
                                    item.example.candidate_id))),
        expected_sessions=tuple(sorted(sessions.values())))
    taken = {trade.candidate_id for trade in evaluation.trade_results}
    return {
        "status": "OK", "label": "partial-day (split breaks portfolio days)",
        "asset_days": evaluation.asset_days, "trades": evaluation.trades,
        "usd_per_asset_day": evaluation.usd_per_asset_day,
        "usd_per_trade": evaluation.usd_per_trade,
        "total_usd": evaluation.total_pnl_usd,
        "max_drawdown_usd": evaluation.max_drawdown_usd,
        "drawdown_p90_usd": evaluation.drawdown_p90_usd,
        "drawdown_breach_rate": evaluation.drawdown_breach_rate,
        "worst_asset_day_usd": evaluation.worst_asset_day_usd,
        "arrivals": len(arrivals),
        "occupancy_or_cap_skips": len(arrivals) - len(taken),
    }


def stress_line(entries: Sequence[Entry], plane: Plane, asset: str,
                rate: float = STRESS_RATE) -> dict[str, object]:
    """Flip ``rate`` of the entries to the opposite side at the same stamps.

    A flip is legal only where an opposite-side CLEAR candidate had already
    formed at or before the entry stamp, and only where the opposite side is
    certifiable there.  Adversarial: the legal flips with the largest cert
    damage are the ones taken.
    """

    rows = [row for row in entries if row.asset == asset]
    target = int(round(rate * len(rows)))
    damages: list[tuple[float, int]] = []
    for position, row in enumerate(rows):
        cell = plane.cands[row.cell]
        other = -row.side
        formed = cell.first_ts(other)
        if formed < 0 or formed > row.ts_ns or not bool(cell.ok(other)[row.bar]):
            continue
        damages.append((row.cert_usd - float(cell.cert(other)[row.bar]), position))
    damages.sort(key=lambda item: (-item[0], item[1]))
    picks = {position for _damage, position in damages[:target]}
    flipped: list[Entry] = []
    for position, row in enumerate(rows):
        if position not in picks:
            flipped.append(row)
            continue
        cell = plane.cands[row.cell]
        other = -row.side
        flipped.append(Entry(
            cell=row.cell, asset=row.asset, d8=row.d8, bar=row.bar,
            ts_ns=row.ts_ns, side=other, cert_usd=float(cell.cert(other)[row.bar]),
            wall=bool(cell.wall(other)[row.bar]),
            exit_ts_ns=int(cell.exit_ts(other)[row.bar]), text=row.text,
            raw_cut=row.raw_cut, raw_last=row.raw_last, phase_idx=row.phase_idx,
            detect_bar=row.detect_bar, hit=row.hit, delay_s=row.delay_s))
    line = cash_by_asset(flipped, plane)[asset]
    line.update({"flips_requested": target, "flips_applied": len(picks),
                 "flips_available": len(damages), "rate": rate,
                 "damage_usd": float(sum(value for value, _p in damages[:target]))})
    return line


def _nearest_delay(seconds: float | None) -> int:
    if seconds is None or seconds != seconds:
        return DELAY_MINUTES[0]
    minutes = float(seconds) / BAR_SECONDS
    return min(DELAY_MINUTES, key=lambda value: (abs(value - minutes), value))


def stage_b(plane: Plane, explore_days: Mapping[str, list[int]],
            a_report: Mapping[str, object],
            o4b_block: Mapping[str, object]) -> dict[str, object]:
    gate = S1.r0_gate(plane.records)
    report: dict[str, object] = {
        "r0_median_gate_mid2": gate, "lines": {}, "replays": {}, "stress": {},
        "phase_q": {}, "capture": {}}
    priced: dict[str, list[Entry]] = {}
    selection = a_report["selection"]
    for asset in ASSETS:
        pick = selection[asset]
        best = DETECTOR_BY_KEY[pick["best"]]
        plan: list[tuple[str, Detector, Mapping[int, int] | None]] = [
            ("BEST", best, None)]
        if pick["runner_up"]:
            plan.append(("RUNNERUP", DETECTOR_BY_KEY[pick["runner_up"]], None))
        phase_q = select_phase_q(plane, best, asset)
        report["phase_q"][asset] = {key: value for key, value in phase_q.items()
                                    if not key.startswith("_")}
        plan.append(("BEST+PHASEQ", best, phase_q["_chosen"]))
        for role, det, per_phase in plan:
            entries, skips = detector_line(plane, det, per_phase, asset=asset)
            name = f"{asset}/{role}"
            priced[name] = entries
            block = line_block(entries, plane,
                               {key: value for key, value in skips.items()})
            line = block["by_asset"][asset]
            line.update({"role": role, "config": det.key, "params": det.params,
                         "line_name": name,
                         "per_phase_q": (None if per_phase is None else
                                         {str(k): v for k, v in per_phase.items()})})
            report["lines"][name] = {"summary": line, "by_phase": block["by_phase"][asset],
                                     "skips": block["skips"][asset]}
            matched = _nearest_delay(line["detect_delay_median_s"])
            oracle = o4b_block["lines"][str(matched)]["by_asset"][asset]
            report["capture"][name] = {
                "matched_delay_minutes": matched,
                "line_usd_per_trade": line["usd_per_trade"],
                "oracle_usd_per_trade": oracle["usd_per_trade"],
                "capture_ratio": (line["usd_per_trade"] / oracle["usd_per_trade"]
                                  if oracle["usd_per_trade"] else None),
                "line_usd_per_asset_day": line["usd_per_asset_day"],
                "oracle_usd_per_asset_day": oracle["usd_per_asset_day"]}
            if role == "BEST":
                report["replays"][name] = replay_line(
                    entries, plane.records, (asset,),
                    f"mill-sweep4:{code_sha()[:16]}:{name.replace('/', '-')}")
                report["stress"][name] = stress_line(entries, plane, asset)
    report["nulls"] = S1.block_null(priced, explore_days, draws=NULL_DRAWS, seed=SEED)
    return report


# --------------------------------------------------------------------------
# Hypothesis log.
# --------------------------------------------------------------------------

def log_rows(report: Mapping[str, object]) -> list[dict[str, object]]:
    stamp = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    shared = {
        "registered_utc": stamp, "spec_sha": SPEC_SHA, "code_sha": code_sha(),
        "split_sha": split_sha(), "outcome_law_sha": outcome_law_sha(),
        "null_seed": SEED, "parent_trial": PARENT_TRIAL,
        "selection_rule": SELECTION_RULE, "verdict": "",
        "days": sum(report["asset_days"].values()),
    }
    miss = {"HG": "err_rate_hg", "NKD": "err_rate_nkd", "SI": "err_rate_si"}
    usd = {"HG": "hg_usd_day", "NKD": "nkd_usd_day", "SI": "si_usd_day"}
    mdd = {"HG": "mdd_hg", "NKD": "mdd_nkd", "SI": "mdd_si"}
    walls = {"HG": "walls_hg", "NKD": "walls_nkd", "SI": "walls_si"}
    rows: list[dict[str, object]] = []
    counter = 0
    stage = report["stage_a"]
    chosen: dict[str, list[str]] = {}
    for asset in ASSETS:
        pick = stage["selection"][asset]
        for role, key in (("B", pick["best"]), ("R", pick["runner_up"])):
            if key:
                chosen.setdefault(key, []).append(f"{asset}:{role}")
    for key in sorted(stage["configs"]):
        entry = stage["configs"][key]
        counter += 1
        mark = ";SEL " + ",".join(chosen[key]) if key in chosen else ""
        row = {**shared, "id": f"sweep4-{counter:03d}", "family": FAMILY,
               "rule": key, "params": json.dumps(entry["params"]),
               "coverage": entry["coverage_pooled"],
               "delay_med_s": entry["detect_delay_median_pooled_s"],
               "note": ("stage-A no-cash termhit" + mark)[:60]}
        for asset in ASSETS:
            hit = entry["by_asset"][asset]["terminal_hit_rate"]
            row[miss[asset]] = None if hit is None else 1.0 - float(hit)
        rows.append(row)
    if "stage_b" not in report:
        return rows
    nulls = report["stage_b"]["nulls"]["by_line"]
    replays = report["stage_b"]["replays"]
    for name in sorted(report["stage_b"]["lines"]):
        line = report["stage_b"]["lines"][name]["summary"]
        asset = name.split("/")[0]
        counter += 1
        skips = ""
        if replays.get(name, {}).get("status") == "OK":
            skips = replays[name]["occupancy_or_cap_skips"]
        hit = line["terminal_hit_rate"]
        rows.append({
            **shared, "id": f"sweep4-{counter:03d}", "family": FAMILY,
            "rule": name, "params": json.dumps(line["params"]),
            "coverage": line["coverage"], "delay_med_s": line["detect_delay_median_s"],
            miss[asset]: None if hit is None else 1.0 - float(hit),
            walls[asset]: line["walls"], usd[asset]: line["usd_per_asset_day"],
            mdd[asset]: line["mdd_day_usd"], "replay_skips": skips,
            "null_margin": nulls.get(name, {}).get("p_max_adjusted"),
            "note": f"stage-B {line['role']} {line['config']}"[:60]})
    return rows


# --------------------------------------------------------------------------
# Report I/O and printing.
# --------------------------------------------------------------------------

def read_report() -> dict[str, object]:
    if OUT_PATH.is_file():
        return json.loads(OUT_PATH.read_text())
    return {"schema": SCHEMA, "tier": "exploratory",
            "claim": "EXPLORE-day sweep 4 candidate-anchored terminal detection; "
                     "can kill, cannot promote"}


def write_report(report: Mapping[str, object]) -> None:
    payload = {key: value for key, value in report.items()
               if not key.startswith("_")}
    OUT_PATH.write_text(json.dumps(payload, sort_keys=True, indent=1,
                                   default=S1._json_default) + "\n")


def _num(value: object, width: int = 8, digits: int = 2) -> str:
    return S1._num(value, width, digits)


CASH_HEAD = (f"{'trd':>5s} {'cov':>6s} {'usd/day':>9s} {'usd/trd':>9s} "
             f"{'win':>6s} {'wall':>6s} {'mdd_day':>9s} {'mdd_trd':>9s} "
             f"{'hit':>6s} {'t_med':>7s}")


def _cash_row(row: Mapping[str, object]) -> str:
    return (f"{row['trades']:5d} {_num(row['coverage'], 6, 3)} "
            f"{_num(row['usd_per_asset_day'], 9, 1)} "
            f"{_num(row['usd_per_trade'], 9, 1)} {_num(row['win_rate'], 6, 3)} "
            f"{_num(row['wall_rate'], 6, 3)} {_num(row['mdd_day_usd'], 9, 1)} "
            f"{_num(row['mdd_trade_usd'], 9, 1)} "
            f"{_num(row['terminal_hit_rate'], 6, 3)} "
            f"{_num(row['entry_seconds_median'], 7, 0)}")


def print_line_block(name: str, block: Mapping[str, object]) -> None:
    for asset in ASSETS:
        print(f"{name:20s} {asset:5s} {'-':>3s} {_cash_row(block['by_asset'][asset])}")
    if "by_phase" not in block:
        return
    for asset in ASSETS:
        for phase, row in sorted(block["by_phase"][asset].items()):
            print(f"{name:20s} {asset:5s} {phase:>3s} {_cash_row(row)}")


def print_o4a(block: Mapping[str, object]) -> None:
    print("\n== O4a S0 replica: best-priced winner-side CANDIDATE at its own "
          "decision_ts")
    print(f"{'line':20s} {'asset':5s} {'ph':>3s} {CASH_HEAD}")
    for name in ("S0R-BEST", "S0R-SECOND", "S0R-BEST-UNFILTERED"):
        print_line_block(name, block["lines"][name])
    print("\n-- reconciliation (exploratory EXPLORE-day numbers vs the era reads)")
    print(f"  {'line':20s} {'asset':5s} {'usd/day':>9s} {'S0 era':>9s} "
          f"{'share':>7s} {'REMceil':>9s} {'capture':>8s} {'amb':>5s} {'nocand':>7s}")
    for name in ("S0R-BEST", "S0R-BEST-UNFILTERED"):
        for asset in ASSETS:
            row = block["lines"][name]["by_asset"][asset]
            skips = block["lines"][name]["skips"][asset]
            print(f"  {name:20s} {asset:5s} {_num(row['usd_per_asset_day'], 9, 1)} "
                  f"{row['s0_era_usd_day']:9.0f} {_num(row['share_of_s0_era'], 7, 3)} "
                  f"{_num(row['rem_ceiling_legal_usd_day'], 9, 1)} "
                  f"{_num(row['capture_of_ceiling'], 8, 3)} {skips['ambiguous']:5d} "
                  f"{skips['no_candidate']:7d}")


def print_o4b(block: Mapping[str, object]) -> None:
    print("\n== O4b recognition-delay budget: first winner-side candidate d "
          "minutes after the terminal extreme")
    print(f"{'d_min':>5s} {'asset':5s} {'ph':>3s} {CASH_HEAD} {'delay50':>8s}")
    for minutes in DELAY_MINUTES:
        line = block["lines"][str(minutes)]
        for asset in ASSETS:
            row = line["by_asset"][asset]
            print(f"{minutes:5d} {asset:5s} {'-':>3s} {_cash_row(row)} "
                  f"{_num(row['entry_delay_median_s'], 8, 0)}")
    print("\n-- per (asset, phase) for d in " + str(list(PHASE_DELAY_MINUTES)))
    print(f"{'d_min':>5s} {'asset':5s} {'ph':>3s} {CASH_HEAD}")
    for minutes in PHASE_DELAY_MINUTES:
        line = block["lines"][str(minutes)]
        for asset in ASSETS:
            for phase, row in sorted(line["by_phase"][asset].items()):
                print(f"{minutes:5d} {asset:5s} {phase:>3s} {_cash_row(row)}")


def _print_o4c_rows(label: str, rows: Mapping[str, object]) -> None:
    quiet_n = rows["quiet_nonterminal_s"]
    quiet_t = rows["quiet_terminal_s"]
    print(f"{label:12s} {rows['extremes']:6d} {rows['terminal']:6d} "
          f"{_num(quiet_n.get('p25'), 8, 0)} {_num(quiet_n.get('p50'), 8, 0)} "
          f"{_num(quiet_n.get('p75'), 8, 0)} {_num(quiet_n.get('p90'), 8, 0)} "
          f"{_num(quiet_t.get('p25'), 9, 0)} {_num(quiet_t.get('p50'), 9, 0)} "
          f"{_num(quiet_t.get('p75'), 9, 0)}")


def print_o4c(block: Mapping[str, object]) -> None:
    print("\n== O4c terminality separability (no cash).  quiet = seconds to the "
          "next same-direction new extreme, or to phase close")
    print(f"{'unit':12s} {'ext':>6s} {'term':>6s} {'nt_p25':>8s} {'nt_p50':>8s} "
          f"{'nt_p75':>8s} {'nt_p90':>8s} {'t_p25':>9s} {'t_p50':>9s} {'t_p75':>9s}")
    for asset in ASSETS:
        _print_o4c_rows(asset, block["by_asset"][asset])
        for phase, rows in sorted(block["by_phase"][asset].items()):
            _print_o4c_rows(f"  {asset}/p{phase}", rows)
    print("\n-- false-positive curve: P(quiet after a NON-terminal extreme > Q)")
    print(f"{'unit':12s} {'set':10s} " + " ".join(f"{q:>7d}" for q in QUIET_MINUTES))
    for asset in ASSETS:
        rows = block["by_asset"][asset]
        for tag, key in (("all", "false_positive_curve"),
                         ("zone|shallow", "false_positive_curve_gated"),
                         ("TERMINAL", "terminal_survives_curve")):
            print(f"{asset:12s} {tag:10s} " + " ".join(
                _num(rows[key][str(q)], 7, 3) for q in QUIET_MINUTES))
        for phase, prow in sorted(block["by_phase"][asset].items()):
            print(f"  {asset}/p{phase:4s} {'all':10s} " + " ".join(
                _num(prow["false_positive_curve"][str(q)], 7, 3)
                for q in QUIET_MINUTES))
    print("\n-- max bounce off the extreme in ATR units, terminal vs non-terminal")
    print(f"{'asset':12s} {'win':>4s} {'term_p25':>9s} {'term_p50':>9s} "
          f"{'term_p75':>9s} {'nt_p25':>9s} {'nt_p50':>9s} {'nt_p75':>9s}")
    for asset in ASSETS:
        for window in BOUNCE_MINUTES:
            rows = block["by_asset"][asset]["bounce"][str(window)]
            term, other = rows["terminal"], rows["non_terminal"]
            print(f"{asset:12s} {window:4d} {_num(term.get('p25'), 9, 3)} "
                  f"{_num(term.get('p50'), 9, 3)} {_num(term.get('p75'), 9, 3)} "
                  f"{_num(other.get('p25'), 9, 3)} {_num(other.get('p50'), 9, 3)} "
                  f"{_num(other.get('p75'), 9, 3)}")


def print_stage_a(report: Mapping[str, object], top: int = 5) -> None:
    configs = report["configs"]
    print("\n== STAGE A (no cash): terminal-hit rate per detector config")
    for asset in ASSETS:
        pick = report["selection"][asset]
        print(f"\n-- {asset}  floor={COVERAGE_FLOOR:.2f} "
              f"pass={pick['n_pass_coverage']}/{len(configs)} "
              f"flags={','.join(pick['flags']) or '-'}")
        print(f"  {'config':24s} {'cov':>6s} {'ent':>5s} {'hit':>6s} {'ci_lo':>6s} "
              f"{'ci_hi':>6s} {'dly50':>7s} {'neg':>6s} {'t_med':>7s} "
              f"{'nocand':>7s} {'long':>6s}")
        for key in pick["ordered"][:top]:
            row = configs[key]["by_asset"][asset]
            mark = "*" if key == pick["best"] else ("+" if key == pick["runner_up"]
                                                    else " ")
            print(f" {mark}{key:24s} {_num(row['coverage'], 6, 3)} "
                  f"{row['entered']:5d} {_num(row['terminal_hit_rate'], 6, 3)} "
                  f"{_num(row['ci95'][0], 6, 3)} {_num(row['ci95'][1], 6, 3)} "
                  f"{_num(row['detect_delay_median_s'], 7, 0)} "
                  f"{_num(row['detect_delay_negative_rate'], 6, 3)} "
                  f"{_num(row['entry_seconds_median'], 7, 0)} "
                  f"{_num(row['no_candidate_rate'], 7, 3)} "
                  f"{_num(row['long_fraction'], 6, 2)}")
        print(f"  selected best={pick['best']} runner_up={pick['runner_up']}")
        best = configs[pick["best"]]["by_phase"][asset]
        print(f"  per-phase for the selected: " + "  ".join(
            f"p{phase}: cov={_num(row['coverage'], 5, 3)} "
            f"hit={_num(row['terminal_hit_rate'], 5, 3)} n={row['entered']}"
            for phase, row in sorted(best.items())))


def print_stage_b(block: Mapping[str, object]) -> None:
    print("\n== STAGE B priced lines (exploratory; verdict column left empty)")
    print(f"{'line':20s} {'config':26s} {'ph':>3s} {CASH_HEAD} {'rung':>6s}")
    for name in sorted(block["lines"]):
        row = block["lines"][name]["summary"]
        print(f"{name:20s} {row['config']:26s} {'-':>3s} {_cash_row(row)} "
              f"{row['rung_usd']:6.0f}")
        for phase, prow in sorted(block["lines"][name]["by_phase"].items()):
            print(f"{'':20s} {'':26s} {phase:>3s} {_cash_row(prow)}")
    print("\n-- per-session Q chosen by the stage-A rule inside each asset's best")
    for asset in ASSETS:
        chosen = block["phase_q"][asset]["chosen"]
        print(f"  {asset:5s} " + "  ".join(
            f"phase {phase}: Q={value}" for phase, value in sorted(chosen.items())))
        for phase, detail in sorted(block["phase_q"][asset]["detail"].items()):
            row = detail["candidates"][str(detail["q"])]
            print(f"    p{phase} cells={detail['cells']:3d} floor_met="
                  f"{str(detail['coverage_floor_met']):5s} "
                  f"cov={_num(row['coverage'], 6, 3)} "
                  f"hit={_num(row['terminal_hit_rate'], 6, 3)} "
                  f"ci_lo={_num(row['ci_low'], 6, 3)}")
    print("\n-- engine replay (partial-day: the split breaks portfolio days)")
    for name in sorted(block["replays"]):
        row = block["replays"][name]
        if row.get("status") != "OK":
            print(f"  {name:20s} {row.get('status')}")
            continue
        print(f"  {name:20s} days={row['asset_days']:4d} trades={row['trades']:4d} "
              f"usd/day={row['usd_per_asset_day']:9.1f} "
              f"usd/trd={row['usd_per_trade']:8.1f} "
              f"mdd={row['max_drawdown_usd']:9.1f} "
              f"breach={row['drawdown_breach_rate']:.3f} "
              f"skips={row['occupancy_or_cap_skips']:3d}")
    print("\n-- 2% adversarial stress on each asset's BEST line")
    print(f"  {'line':20s} {'flips':>6s} {'avail':>6s} {'usd/day':>9s} "
          f"{'usd/trd':>9s} {'wall':>6s} {'mdd_day':>9s} {'mdd_trd':>9s}")
    for name in sorted(block["stress"]):
        row = block["stress"][name]
        print(f"  {name:20s} {row['flips_applied']:6d} {row['flips_available']:6d} "
              f"{_num(row['usd_per_asset_day'], 9, 1)} "
              f"{_num(row['usd_per_trade'], 9, 1)} {_num(row['wall_rate'], 6, 3)} "
              f"{_num(row['mdd_day_usd'], 9, 1)} {_num(row['mdd_trade_usd'], 9, 1)}")
    print("\n-- capture of the delay-matched O4b oracle (d nearest the line's "
          "median detection delay)")
    print(f"  {'line':20s} {'d_min':>5s} {'line/trd':>9s} {'oracle/trd':>11s} "
          f"{'capture':>8s} {'line/day':>9s} {'oracle/day':>11s}")
    for name in sorted(block["capture"]):
        row = block["capture"][name]
        print(f"  {name:20s} {row['matched_delay_minutes']:5d} "
              f"{_num(row['line_usd_per_trade'], 9, 1)} "
              f"{_num(row['oracle_usd_per_trade'], 11, 1)} "
              f"{_num(row['capture_ratio'], 8, 3)} "
              f"{_num(row['line_usd_per_asset_day'], 9, 1)} "
              f"{_num(row['oracle_usd_per_asset_day'], 11, 1)}")
    nulls = block["nulls"]
    print(f"\n-- block-permutation null, {nulls['draws']} draws, seed {nulls['seed']}, "
          "max-statistic across every priced line")
    print(f"  {'line':20s} {'obs_mdd':>9s} {'null_mean':>10s} {'p_own':>7s} "
          f"{'p_adj':>7s} {'pool_obs':>9s} {'p_pool':>7s} {'p_pool_adj':>10s}")
    for name in sorted(nulls["by_line"]):
        row = nulls["by_line"][name]
        print(f"  {name:20s} {row['observed_max_asset_mdd_usd']:9.1f} "
              f"{row['null_asset_mdd_mean_usd']:10.1f} {row['p_own']:7.3f} "
              f"{row['p_max_adjusted']:7.3f} {row['observed_pooled_mdd_usd']:9.1f} "
              f"{row['p_pooled_own']:7.3f} {row['p_pooled_max_adjusted']:10.3f}")
    if nulls["lines_held_out_empty"]:
        print(f"  held out (no entries): {', '.join(nulls['lines_held_out_empty'])}")


# --------------------------------------------------------------------------
# Selftest: synthetic arrays only, zero era bytes.
# --------------------------------------------------------------------------

SELFTEST_ASSET = "HG"
SELFTEST_ATR_MID2 = S3.SELFTEST_ATR_MID2      # 1000 usd * 2e9 / 25000 = 8e7
SELFTEST_OPEN = S3.SELFTEST_OPEN              # 9.200e9


def _quiet_series() -> list[int]:
    """120 bars.  A false quiet at bar 20, the true terminal low at bar 46.

    Bars 0..19 hold 9.200e9 so bar 20's 9.150e9 is the phase's first new
    running low (0.625 ATR under the open).  Bars 21..45 sit at 9.170e9, a
    retrace of 2.0e7 mid2 = 0.25 ATR, held for 25 bars: a Q=10 detector calls
    bar 20 terminal at bar 30 and is WRONG.  Bar 46 prints 9.140e9, a newer
    running low, so a Q=30 detector never fires on bar 20; it fires at bar 76
    on the extreme that really is terminal.  Bars 47..119 sit at 9.160e9, a
    2.0e7 = 0.25 ATR retrace off bar 46.
    """

    values = [9_200_000_000] * 20
    values += [9_150_000_000]
    values += [9_170_000_000] * 25
    values += [9_140_000_000]
    values += [9_160_000_000] * (120 - len(values))
    return values


def _selftest_geometry() -> list[tuple[str, bool, str]]:
    rec = S3._cell(_quiet_series())
    ext = S2.extremes(rec)
    ctx = S3._ctx()
    cand = _cand_cell(rec, [])
    geo = side_geometry(rec, ext, ctx, cand, 1)
    marks = list(np.flatnonzero(ext.new_low))
    q10 = Detector("Q10", 10, 0.10, 1, "none")
    q30 = Detector("Q30", 30, 0.10, 1, "none")
    deadline = int(rec.phase_close_ts_ns) - REMAIN_NS
    bars10 = detection_bars(geo, q10, deadline, rec.lat)
    bars30 = detection_bars(geo, q30, deadline, rec.lat)
    anchors10 = [int(geo.anchor[bar]) for bar in bars10]
    anchors30 = [int(geo.anchor[bar]) for bar in bars30]
    return [
        ("new_running_lows_are_the_hand_bars", marks == [20, 46],
         f"new lows at {marks}, hand value [20, 46]"),
        ("terminal_extreme_is_the_last_new_low",
         terminal_extreme_bar(ext, 1) == 46,
         f"terminal={terminal_extreme_bar(ext, 1)} expected 46"),
        ("terminal_extreme_of_the_other_direction_is_absent",
         terminal_extreme_bar(ext, -1) == -1,
         f"a new running high printed: {terminal_extreme_bar(ext, -1)}"),
        ("retrace_off_the_false_extreme_is_quarter_atr",
         abs(float(geo.retrace[30]) - 0.25) < 1e-9,
         f"retrace[30]={float(geo.retrace[30])} hand value 2.0e7/8.0e7"),
        ("age_resets_at_the_newer_extreme",
         int(geo.age[45]) == 25 and int(geo.age[46]) == 0
         and int(geo.age[47]) == 1,
         f"ages 45/46/47 = {int(geo.age[45])}/{int(geo.age[46])}/"
         f"{int(geo.age[47])}"),
        ("false_quiet_detected_at_bar_30_by_Q10",
         len(bars10) and int(bars10[0]) == 30 and anchors10[0] == 20,
         f"Q=10 first detection {list(bars10[:3])} anchored {anchors10[:3]}"),
        ("Q30_never_calls_the_false_quiet_terminal",
         20 not in anchors30,
         f"Q=30 anchored a detection on the bar-20 pause: {anchors30[:5]}"),
        ("Q30_fires_only_on_the_true_terminal_extreme",
         len(bars30) and int(bars30[0]) == 76 and set(anchors30) == {46},
         f"Q=30 detections {list(bars30[:3])} anchored {sorted(set(anchors30))}"),
        ("held_k3_needs_three_bars_of_retrace",
         not bool(geo.held[(0.10, 3)][22]) and bool(geo.held[(0.10, 3)][23]),
         f"held(k=3) at 22/23 = {bool(geo.held[(0.10, 3)][22])}/"
         f"{bool(geo.held[(0.10, 3)][23])}"),
        ("stop_stamp_is_the_next_same_direction_extreme",
         int(geo.stop_ns[30]) == int(rec.lat[46])
         and int(geo.stop_ns[76]) == int(rec.phase_close_ts_ns),
         f"stop at 30={int(geo.stop_ns[30])} expected {int(rec.lat[46])}"),
    ]


def _cand_cell(rec: S1.CellRec, rows: Sequence[tuple[int, int]],
               phase_idx: int = 0) -> CandCell:
    """A synthetic candidate plane: ``rows`` are ``(stamp, side)`` pairs."""

    stamps = np.asarray([int(stamp) for stamp, _side in rows], np.int64)
    sides = np.asarray([int(side) for _stamp, side in rows], np.int8)
    n = len(stamps)
    ones = np.ones(n, np.bool_)
    return CandCell(
        text=rec.text, phase_idx=int(phase_idx),
        first_ts_p=int(stamps[sides > 0].min()) if int((sides > 0).sum()) else -1,
        first_ts_m=int(stamps[sides < 0].min()) if int((sides < 0).sum()) else -1,
        ts=stamps, side=sides, cand_mid2=np.zeros(n, np.int64),
        quote_mid2=np.zeros(n, np.int64), cost=np.full(n, 20.0),
        anchor_ts=bar_anchor_ts(stamps, int(rec.phase_open_ts_ns)),
        raw_cut=np.zeros(n, np.int64), raw_last=np.zeros(n, np.int64),
        cert_p=np.zeros(n, np.float64), cert_m=np.zeros(n, np.float64),
        wall_p=np.zeros(n, np.bool_), wall_m=np.zeros(n, np.bool_),
        exit_p=stamps.copy(), exit_m=stamps.copy(), ok_p=ones, ok_m=ones.copy())


def _selftest_rearm() -> list[tuple[str, bool, str]]:
    """The cancellation: a newer extreme before the entry re-arms the detector.

    Long candidates print only at the bar-50 and bar-60 closes.  The Q=10
    detection at bar 30 is anchored on the bar-20 pause, and its first
    fade-side candidate lands at bar 50 - after the bar-46 new low.  The law
    cancels that detection and re-arms on bar 46, whose own detection at bar 56
    takes the bar-60 candidate.  Without the cancellation the entry would have
    been the bar-50 candidate off a non-terminal extreme.
    """

    rec = S3._cell(_quiet_series())
    cand = _cand_cell(rec, [(int(rec.lat[50]), 1), (int(rec.lat[60]), 1)])
    plane = _selftest_plane([rec], [cand])
    q10 = Detector("Q10", 10, 0.10, 1, "none")
    shot = side_shot(plane, 0, 1, q10)
    entry, reason = detector_entry(plane, 0, q10)
    fired = detection_bars(plane.geometry[0][1], q10, plane.deadline_ts(0), rec.lat)
    return [
        ("rearm_skips_the_cancelled_detection",
         shot is not None and shot[0] == 56,
         f"detection bar {None if shot is None else shot[0]} expected 56"),
        ("rearm_takes_the_candidate_after_the_new_extreme",
         shot is not None and int(cand.ts[shot[1]]) == int(rec.lat[60]),
         f"entry stamp {None if shot is None else int(cand.ts[shot[1]])} "
         f"expected {int(rec.lat[60])}"),
        ("cancelled_detection_fires_first_and_is_the_one_dropped",
         len(fired) and int(fired[0]) == 30
         and int(rec.lat[50]) >= int(rec.lat[46]),
         f"first detection {list(fired[:3])}; the bar-50 candidate lands at or "
         f"after the bar-46 new low"),
        ("entry_is_the_terminal_extreme_fade", entry is not None and entry.hit
         and entry.detect_bar == 56 and reason == "entered", f"{entry}"),
        ("entry_delay_is_measured_off_the_true_terminal_extreme",
         entry is not None
         and entry.delay_s == float(int(rec.lat[60]) - int(rec.lat[46]))
         / NANOS_PER_SECOND, f"{None if entry is None else entry.delay_s}"),
    ]


def _selftest_plane(records: Sequence[S1.CellRec], cands: Sequence[CandCell]
                    ) -> Plane:
    exts = [S2.extremes(rec) for rec in records]
    ctx = S3._ctx()
    geometry = [{side: side_geometry(rec, ext, ctx, cand, side)
                 for side in (1, -1)}
                for rec, ext, cand in zip(records, exts, cands)]
    return Plane(
        list(records), list(cands), exts, [S2.star_cell(rec) for rec in records],
        [ctx] * len(records), [1] * len(records), geometry,
        {rec.asset: 1 for rec in records}, S1.cells_by_asset(records),
        {(rec.asset, cell.phase_idx): 1 for rec, cell in zip(records, cands)},
        {rec.asset: (0,) for rec in records}, {})


SELFTEST_ROWS_NS = tuple(value * NANOS_PER_SECOND for value in (10, 100, 122, 150))
SELFTEST_BIDS = (9_100_000_000, 9_150_000_000, 9_180_000_000, 9_190_000_000)
SELFTEST_SPREADS = (200_000, 400_000, 600_000, 800_000)
SELFTEST_CAND_NS = 125 * NANOS_PER_SECOND


def _selftest_index() -> M.MillIndex:
    bid = np.asarray(SELFTEST_BIDS, np.int64)
    ask = bid + np.asarray(SELFTEST_SPREADS, np.int64)
    stamps = np.asarray(SELFTEST_ROWS_NS, np.int64)
    return M.MillIndex(SELFTEST_ASSET, stamps, bid + ask, bid, ask,
                       np.zeros(len(stamps), np.uint32), stamps,
                       np.zeros(len(stamps), np.uint32))


def _selftest_fill() -> list[tuple[str, bool, str]]:
    """The candidate-anchored quote and cost, and the mutant that moves them.

    Rows sit at 10 s, 100 s, 122 s and 150 s.  The candidate decides at 125 s,
    so the last trusted row STRICTLY before it is the 122 s row (index 2) and
    the frozen cost is that row's 600,000 mid2 spread: 600000*25000/1e9 + 5.0 =
    20.0 usd.  The last completed 60 s bar close at or before 125 s is 120 s,
    whose last strictly-earlier row is the 100 s row (index 1) with a 400,000
    spread and cost 400000*25000/1e9 + 5.0 = 15.0 usd.  Those are the two
    numbers ``sweep4_entry_at_bar`` swaps.
    """

    index = _selftest_index()
    stamps = np.asarray([SELFTEST_CAND_NS], np.int64)
    filled = price_candidates(index, SELFTEST_ASSET, stamps, 0,
                              200 * NANOS_PER_SECOND, np.asarray(SELFTEST_ROWS_NS,
                                                                 np.int64))
    own_mid2 = int(SELFTEST_BIDS[2] * 2 + SELFTEST_SPREADS[2])
    bar_mid2 = int(SELFTEST_BIDS[1] * 2 + SELFTEST_SPREADS[1])
    own_cost = SELFTEST_SPREADS[2] * ASSET_MULTIPLIER[SELFTEST_ASSET] / 1e9 + FEE_USD
    bar_cost = SELFTEST_SPREADS[1] * ASSET_MULTIPLIER[SELFTEST_ASSET] / 1e9 + FEE_USD
    return [
        ("entry_quote_hand_values_differ_between_the_two_laws",
         own_mid2 != bar_mid2 and abs(own_cost - bar_cost) > 1e-9
         and abs(own_cost - 20.0) < 1e-9 and abs(bar_cost - 15.0) < 1e-9,
         f"decision-row cost {own_cost}, bar-close cost {bar_cost}"),
        ("bar_anchor_is_the_last_completed_bar_close",
         int(filled["anchor_ts"][0]) == 120 * NANOS_PER_SECOND,
         f"anchor={int(filled['anchor_ts'][0])} expected {120 * NANOS_PER_SECOND}"),
        ("entry_quote_comes_from_the_candidates_own_decision_row",
         int(filled["quote_mid2"][0]) == own_mid2,
         f"quote_mid2={int(filled['quote_mid2'][0])} expected the 122 s row's "
         f"{own_mid2}, not the bar-close row's {bar_mid2}"),
        ("frozen_cost_comes_from_that_rows_spread",
         abs(float(filled["cost"][0]) - own_cost) < 1e-9,
         f"cost={float(filled['cost'][0])} expected the 122 s row's {own_cost}, "
         f"not the bar-close row's {bar_cost}"),
        ("entry_quote_is_two_sided",
         bool(filled["quote_ok"][0]) and 0 < int(filled["bid"][0])
         < int(filled["ask"][0]),
         f"bid={int(filled['bid'][0])} ask={int(filled['ask'][0])}"),
        ("a_row_stamped_at_the_decision_is_future",
         index.position(SELFTEST_ROWS_NS[2]) == 1,
         f"position at the row's own stamp = {index.position(SELFTEST_ROWS_NS[2])}"),
    ]


def _selftest_oracles() -> list[tuple[str, bool, str]]:
    """O4a's price rank and O4b's delay floor on hand-built candidates."""

    rec = S3._cell(_quiet_series())
    rows = [(int(rec.lat[10]), 1), (int(rec.lat[30]), 1), (int(rec.lat[50]), 1),
            (int(rec.lat[95]), 1)]
    cand = _cand_cell(rec, rows)
    cand.cand_mid2 = np.asarray([9_200_000_000, 9_150_000_000, 9_170_000_000,
                                 9_100_000_000], np.int64)
    plane = _selftest_plane([rec], [cand])
    best, _skips = o4a_line(plane, 0, True)
    second, _skips2 = o4a_line(plane, 1, True)
    raw, raw_skips = o4a_line(plane, 0, False)
    delays = {minutes: o4b_line(plane, minutes)[0] for minutes in (0, 30)}
    deadline = plane.deadline_ts(0)
    return [
        ("deadline_is_phase_close_minus_1800s",
         deadline == int(rec.phase_close_ts_ns) - REMAIN_NS
         and int(rec.lat[95]) > deadline and int(rec.lat[50]) <= deadline,
         f"deadline={deadline}; bar95={int(rec.lat[95])}"),
        ("o4a_takes_the_deepest_priced_winner_side_candidate",
         len(best) == 1 and best[0].bar == 1,
         f"{[row.bar for row in best]} expected the 9.150e9 candidate at row 1"),
        ("o4a_second_line_takes_the_next_best_price",
         len(second) == 1 and second[0].bar == 2,
         f"{[row.bar for row in second]} expected row 2 (9.170e9)"),
        ("o4a_unfiltered_rank_drops_a_cell_whose_deepest_price_is_late",
         not len(raw) and raw_skips[SELFTEST_ASSET]["past_deadline"] == 1,
         f"unfiltered line took {[row.bar for row in raw]}; the 9.100e9 "
         f"candidate at bar 95 sits past the deadline"),
        ("o4b_d0_takes_the_first_candidate_after_the_terminal_extreme",
         len(delays[0]) == 1 and delays[0][0].bar == 2,
         f"{[row.bar for row in delays[0]]}; terminal bar is 46, bar-50 candidate"),
        ("o4b_delay_floor_skips_a_cell_with_nothing_left",
         not len(delays[30]),
         f"d=30 entered {[row.bar for row in delays[30]]} past the deadline"),
        ("o4b_entries_are_terminal_hits_by_construction",
         all(row.hit for row in delays[0]), f"{[row.hit for row in delays[0]]}"),
    ]


def _selftest_o4c() -> list[tuple[str, bool, str]]:
    rec = S3._cell(_quiet_series())
    cand = _cand_cell(rec, [(int(rec.lat[50]), 1)])
    plane = _selftest_plane([rec], [cand])
    rows = [row for row in extreme_rows(plane) if row.side > 0]
    quiet = {row.quiet_s: row.terminal for row in rows}
    return [
        ("o4c_sees_both_low_extremes", len(rows) == 2,
         f"{len(rows)} low extremes, hand value 2"),
        ("o4c_quiet_of_the_false_extreme_is_26_minutes",
         any(abs(value - 26 * 60) < 1e-9 and not terminal
             for value, terminal in quiet.items()),
         f"quiets {sorted(quiet)}"),
        ("o4c_terminal_quiet_runs_to_phase_close",
         any(abs(value - (120 - 46) * 60) < 1e-9 and terminal
             for value, terminal in quiet.items()),
         f"quiets {sorted(quiet)}"),
        ("o4c_bounce_is_measured_in_atr_units",
         all(abs(row.bounce[15] - 0.25) < 1e-9 for row in rows),
         f"{[row.bounce[15] for row in rows]} hand value 2.0e7/8.0e7"),
    ]


def selftest() -> int:
    mutant = _sweep_mutant()
    checks: list[tuple[str, bool, str]] = [
        ("detector_grid_is_6Q_x_3H_x_2k_x_2zone", len(DETECTORS) == 72,
         f"{len(DETECTORS)} configs"),
        ("winner_side_bar_is_tau_900s", W_BAR == 15, f"W_BAR={W_BAR}"),
    ]
    checks.extend(_selftest_fill())
    checks.extend(_selftest_geometry())
    checks.extend(_selftest_rearm())
    checks.extend(_selftest_oracles())
    checks.extend(_selftest_o4c())
    dead = [(name, why) for name, ok, why in checks if not ok]
    if dead:
        for name, why in dead:
            print(f"DEAD: {name}: {why}")
        print(f"sweep4_selftest_dead mutant={mutant or 'none'} "
              f"cases={len(dead)}/{len(checks)}")
        return 1
    if mutant:
        print(f"DEAD: mutant {mutant} left every sweep-4 case green")
        return 1
    print(f"sweep4_selftest_ok cases={len(checks)}")
    return 0


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _load(assets: Sequence[str], root: Path
          ) -> tuple[list[S1.CellRec], dict[str, int]]:
    try:
        return S1.load_cache()
    except S1.SweepRefusal:
        store = M.load_store(SPLIT_PATH, assets, root=root)
        records, days = S1.prep(store)
        S1.save_cache(records, days)
        return records, days


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", nargs="?", default="all",
                        choices=("stage-o", "stage-a", "stage-b", "log", "all"))
    parser.add_argument("--assets", default="HG,NKD,SI")
    parser.add_argument("--root", default=str(M.MILL_ROOT))
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    mutant = _sweep_mutant()
    assets = tuple(name.strip().upper() for name in args.assets.split(",")
                   if name.strip())
    started = time.monotonic()
    records, days = _load(assets, Path(args.root))
    explore_days = S1._explore_days(assets)
    cands = cands_for(records, assets, Path(args.root), mutant)
    plane = build_plane(records, cands, CTX.ContextStore(), days)
    report = read_report()
    report.setdefault("spec_sha", SPEC_SHA)
    report["code_sha"] = code_sha()
    report["split_sha"] = split_sha()
    report["outcome_law_sha"] = outcome_law_sha()
    report["parent_trial"] = PARENT_TRIAL
    report["mutant"] = mutant
    report["asset_days"] = dict(days)
    report["cells"] = dict(plane.cells)
    report["phase_cells"] = {f"{asset}/{phase}": value
                             for (asset, phase), value in sorted(plane.phase_cells.items())}
    report["diagnostics"] = plane.diagnostics

    if args.stage in ("stage-o", "all"):
        block = stage_o(plane)
        report["stage_o"] = block
        print_o4a(block["o4a"])
        print_o4b(block["o4b"])
        print_o4c(block["o4c"])
    if args.stage in ("stage-a", "stage-b", "log", "all"):
        if "stage_a" not in report or args.stage in ("stage-a", "all"):
            report["stage_a"] = stage_a(plane)
            print_stage_a(report["stage_a"], args.top)
    if args.stage in ("stage-b", "all"):
        if "stage_o" not in report:
            report["stage_o"] = {"o4b": o4b(plane)}
        report["stage_b"] = stage_b(plane, explore_days, report["stage_a"],
                                    report["stage_o"]["o4b"])
        print_stage_b(report["stage_b"])
    if args.stage in ("log", "all"):
        rows = log_rows(report)
        written = S1.append_log(rows)
        report["log"] = {"rows_appended": written,
                         "registered_utc": rows[0]["registered_utc"],
                         "first_id": rows[0]["id"], "last_id": rows[-1]["id"]}
        print(f"\nlog: appended {written} rows to {LOG_PATH}")

    report["wall_seconds"] = round(time.monotonic() - started, 2)
    write_report(report)
    print(f"\nwrote {OUT_PATH} wall={report['wall_seconds']}s "
          f"cells={len(records)} spec_sha={SPEC_SHA[:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
