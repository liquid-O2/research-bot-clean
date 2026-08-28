#!/usr/bin/env python3
"""The FIXED-ZONE memory accessor: defence history AT A NAMED PRICE.

WHY THIS EXISTS.  ``levels.py`` centres every band on ``band_center_mid2``, the
READING BAR'S OWN MID.  That is the right key for "what has happened at the
price I am standing on", and it is the wrong key for "what has happened at the
barrier I am about to trade against".  Sweep 22 asked the second question and
read the first answer: a direct audit over its 14,650 formed candidates found
ZERO exact zone centres, a median approach offset of 1.90 zone widths and a
median episode-close offset of 3.32 widths, at which distance the cached band is
disjoint from the barrier band.  Sol's ruling
(``.audit/briefs/mill-structbreak-sol-out.md``, section B, "Replace the
disclosed shifting-center approximation") refuses F19 on that ground and orders
one fixed-zone query built before any outcome reopens.

WHAT THIS IS.  One function over a query
``(cell, zone_price, band_width, decision_stamp_ns, side)`` that answers, for a
band centred EXACTLY at ``zone_price``:

1. SAME-DAY, from current-day bars whose lattice close is STRICTLY BEFORE
   ``decision_stamp_ns``: ``sd_touches``, ``sd_held``, ``sd_broke``,
   ``sd_mins_since_touch``, ``sd_touch_delta``.
2. PRIOR-EXPLORE-SESSION, the same quantities over the licensed prior EXPLORE
   session's whole path, under the ``ps_*`` names.  The prior EXPLORE session is
   three locked days back under the split law, NOT the calendar prior day: the
   mill's licence binds HOLD intraday paths as unread, so a minute-grain
   prior-session read may not open the immediately prior locked day.
3. ``day_scale_persistence``, sweep 22's day-scale term carried numerically
   unchanged for comparability.

SIDE IS NOT OPTIONAL.  ``held`` and ``broke`` are side-signed under the levels
law - a touch that HELD a low fade is the same touch that BROKE a high fade - so
a sideless held count does not exist.  The query carries the side the consumer
is scoring, exactly as ``lcell.matrix(side, mult)`` does.

THE LAW IS THE CACHE'S LAW, RE-DERIVED AT THE FIXED CENTRE.  Membership moves to
the fixed price; the OUTCOME of a touch stays anchored on the TOUCHED price, as
in ``build_levels.day_planes``.  Touch at ``P`` inside the band, half width
``w``: side +1 HELD when price reached ``P + w`` before printing below
``P - w``, and BROKE when it printed below ``P - w`` first; side -1 mirrors it.
Both legs are the same distance on purpose.  An outcome counts only once its
VERDICT bar is itself strictly before the decision, so a touch whose verdict is
not yet in contributes to the touch count and to neither outcome.  Reading the
resolution over the whole day and then keeping only verdicts strictly before the
decision is identical to scanning only the pre-decision window: the first hit
before the decision is the first hit, and a leg whose first hit is after the
decision cannot beat one whose first hit is before it.

WHAT THE ROW PROVES.  Every row carries ``center_price`` (the centre ACTUALLY
used, so the gate is mechanical rather than remembered), ``band_width``,
``max_source_stamp`` and ``n_source_bars``.  ``max_source_stamp`` is the
conservative bound: the lattice close of the last current-day bar the read could
have seen, and the prior EXPLORE session's last stamp where that family is
served.  Strictly less than ``decision_stamp_ns`` or the read is not causal.

NAMING (Sol's restriction).  The day-scale term is ``day_scale_persistence``,
never ``pd_held - pd_broke``.  Sol accepts sweep 22's number as a day-scale
persistence and location proxy and refuses the name as a semantic claim:
``day_scale_held`` marks a price a COMPLETED session turned at (a prior-day
extreme or a prior-EXPLORE value edge), which is not proof that a defence held,
and ``day_scale_broke`` measures TODAY's prior traversal, not a prior-day break.
The two terms describe different horizons.  The minute-grain defence pair at
this fixed price is ``sd_held``/``sd_broke`` and ``ps_held``/``ps_broke``; no
result from ``day_scale_persistence`` may claim that prior-day defence memory
was exhausted.

SOURCES.  Computed on the fly from the mill prep shards (``sweep1.load_cache``)
and the minute flow cache (``flow.load_flow``), through the SAME day-tape
construction the levels builder uses (``build_levels.day_tape``, imported, not
copied).  No cache is written: a fixed-zone read is keyed by an arbitrary price
and an arbitrary stamp, so there is no finite grid to precompute, and a stale
cache is a worse failure than a recomputation.  The day tape and the per
``(day, width, side)`` outcome arrays are memoised in process.

THE MUTANT.  ``QRE2_MILL_LEVELSZONE_MUTANT=center_uses_current_mid`` substitutes
the last completed bar's mid for the requested centre - the exact F19 defect.
It must turn the centre-equality gate and the hand counts red.

Nothing here writes a cache, opens a HOLD day, reads a teacher or late label, or
touches an outcome column.  ``levels.py`` and ``build_levels.py`` are read and
imported, never modified.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import math
import os
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

import levels as LV

ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = ROOT / ".audit/mill-levels-zone-build.json"
SCHEMA = "QRE2MILLLEVELSZONE1"
ASSETS = ("HG", "NKD", "SI")

VERIFY_ROWS = 500
VERIFY_SEED = 20260827
HAND_ROWS = 20

MUTANT_ENV = "QRE2_MILL_LEVELSZONE_MUTANT"
MUTANT_CENTER_MID = "center_uses_current_mid"
MUTANTS = (MUTANT_CENTER_MID,)

# Sweep 22's PD_HELD_KINDS, restated here so the law functions stay importable
# without the sweep.  ``verify`` asserts the two rosters are identical.
DAY_SCALE_TURN_KINDS = ("PD_HIGH", "PD_LOW", "PEXP_VALUE_HI", "PEXP_VALUE_LO")
DAY_SCALE_MODES = ("approach", "close")

# The fixed column order of one fixed-zone row.
ZONE_ROW_FIELDS = (
    # identity and the causal receipt
    "asset", "d8", "phase", "cell", "side", "zone_kind",
    "center_price", "band_width", "decision_stamp_ns", "max_source_stamp",
    "n_source_bars",
    # 1. same-day memory at the fixed price
    "sd_touches", "sd_held", "sd_broke", "sd_mins_since_touch", "sd_touch_delta",
    # 2. prior EXPLORE session memory at the same fixed price
    "ps_touches", "ps_held", "ps_broke", "ps_mins_since_touch", "ps_touch_delta",
    "ps_sess_d8", "ps_served", "n_ps_source_bars",
    # 3. the day-scale persistence proxy, carried for comparability
    "day_scale_held", "day_scale_broke", "day_scale_persistence",
    "day_scale_mode", "n_day_scale_bars",
)

NANOS_PER_MINUTE = LV.NANOS_PER_MINUTE


class ZoneStop(RuntimeError):
    """The fixed-zone accessor was asked for the impossible."""


def _mutant() -> str:
    name = os.environ.get(MUTANT_ENV, "")
    if name and name not in MUTANTS:
        raise ZoneStop(f"unknown levels-zone mutant: {name}")
    return name


# --------------------------------------------------------------------------
# The tape.  A minimal price path with the two flags the law needs, so every
# law function below runs on a synthetic fixture with no cache present.
# --------------------------------------------------------------------------

@dataclass(slots=True)
class Tape:
    """One price path on the mill lattice: closes, mids, flow, sourced flags."""

    asset: str
    d8: int
    ts: np.ndarray          # (n,) lattice close stamp of each bar
    mid: np.ndarray         # (n,) bar mid, mid2 units
    delta: np.ndarray       # (n,) net signed aggressor flow on the mill lattice
    sourced: np.ndarray     # (n,) a trusted raw row exists strictly before ts

    @property
    def n(self) -> int:
        return int(len(self.ts))


def tape_from_day(day) -> Tape:
    """Adapt ``build_levels.DayTape`` without copying its construction."""

    return Tape(str(day.asset), int(day.d8), np.asarray(day.ts, np.int64),
                np.asarray(day.mid, np.float64),
                np.asarray(day.delta, np.float64),
                np.asarray(day.sourced, bool))


# --------------------------------------------------------------------------
# The law.  Pure functions over tapes; the reader and the selftest call exactly
# these, so the synthetic hand counts and the real rows cannot drift apart.
# --------------------------------------------------------------------------

def prior_window(tape: Tape, decision_stamp_ns: int) -> int:
    """How many leading bars closed STRICTLY BEFORE the decision stamp.

    The lattice is strictly increasing, so the eligible set is a prefix and one
    integer names it.  ``searchsorted`` with side "left" returns the first index
    whose stamp is >= the decision, which is exactly the prefix length.
    """

    return int(np.searchsorted(np.asarray(tape.ts, np.int64),
                               np.int64(decision_stamp_ns), side="left"))


def resolved_center(zone_price: float, tape: Tape, window: int) -> float:
    """The centre the read ACTUALLY uses.  One choke point, one defect site.

    Normally the requested zone price, unchanged.  Under the mutant it becomes
    the last completed bar's mid - F19's defect, reproduced on purpose so the
    centre-equality gate has something to catch.
    """

    if _mutant() == MUTANT_CENTER_MID and int(window) > 0:
        return float(tape.mid[int(window) - 1])
    return float(zone_price)


def outcome_pair(tape: Tape, half_width: float, side: int
                 ) -> tuple[np.ndarray, np.ndarray]:
    """``(hold_bar, broke_bar)`` for a touch AT each bar of the tape.

    ``levels.outcome_bars`` is the one definition of the anchored-touch law; it
    is called here rather than restated, so "identical to the builder" is a fact
    about the call graph and not a claim in a comment.  ``n`` means "never".
    """

    return LV.outcome_bars(np.asarray(tape.mid, np.float64), float(half_width),
                           int(side))


def same_day_counts(tape: Tape, center: float, half_width: float, side: int,
                    decision_stamp_ns: int, *,
                    outcomes: tuple[np.ndarray, np.ndarray] | None = None
                    ) -> dict[str, float]:
    """The same-day memory of ONE FIXED PRICE, read at a decision stamp.

    Membership is centred on ``center`` - not on any bar's own mid.  The outcome
    of each touch stays anchored on the TOUCHED price, and counts only once its
    verdict bar closed strictly before the decision.  Every returned count is
    NaN when no sourced bar closed before the decision: an empty window has no
    memory, which is not the same fact as a price nothing ever touched.
    """

    window = prior_window(tape, int(decision_stamp_ns))
    mid = np.asarray(tape.mid, np.float64)[:window]
    stamps = np.asarray(tape.ts, np.int64)[:window]
    sourced = np.asarray(tape.sourced, bool)[:window]
    blank = {"touches": float("nan"), "held": float("nan"),
             "broke": float("nan"), "mins_since_touch": float("nan"),
             "touch_delta": float("nan"), "n_source_bars": 0, "window": window}
    if window <= 0 or not bool(sourced.any()):
        return blank
    touch = (np.abs(mid - float(center)) <= float(half_width)) & sourced
    hold_bar, broke_bar = (outcomes if outcomes is not None
                           else outcome_pair(tape, half_width, side))
    # A verdict counts only if its own bar closed before the decision.  The
    # sentinel is the full tape length, so an unresolved leg is never "before".
    total = int(tape.n)
    ts_full = np.asarray(tape.ts, np.int64)
    resolved_hold = (hold_bar[:window] < total) & (
        ts_full[np.minimum(hold_bar[:window], total - 1)] < int(decision_stamp_ns))
    resolved_broke = (broke_bar[:window] < total) & (
        ts_full[np.minimum(broke_bar[:window], total - 1)] < int(decision_stamp_ns))
    held = touch & (hold_bar[:window] < broke_bar[:window]) & resolved_hold
    broke = touch & (broke_bar[:window] < hold_bar[:window]) & resolved_broke
    where = np.flatnonzero(touch)
    gap = (float(int(decision_stamp_ns) - int(stamps[where[-1]]))
           / float(NANOS_PER_MINUTE)) if len(where) else float("nan")
    return {"touches": float(touch.sum()), "held": float(held.sum()),
            "broke": float(broke.sum()), "mins_since_touch": gap,
            "touch_delta": float(
                np.asarray(tape.delta, np.float64)[:window][touch].sum()),
            "n_source_bars": int(sourced.sum()), "window": window}


def session_counts(tape: Tape, center: float, half_width: float, side: int,
                   reference_stamp_ns: int, *,
                   outcomes: tuple[np.ndarray, np.ndarray] | None = None
                   ) -> dict[str, float]:
    """The same quantities over a COMPLETED session's whole path.

    A finished session has no unresolved verdicts to withhold, so every touch
    that ever resolved counts - exactly the ``ps_held``/``ps_broke`` law of the
    cache.  ``reference_stamp_ns`` only dates the "minutes since" figure, which
    therefore spans the session gap and is reported as such.
    """

    mid = np.asarray(tape.mid, np.float64)
    sourced = np.asarray(tape.sourced, bool)
    if tape.n <= 0 or not bool(sourced.any()):
        return {"touches": float("nan"), "held": float("nan"),
                "broke": float("nan"), "mins_since_touch": float("nan"),
                "touch_delta": float("nan"), "n_source_bars": 0}
    touch = (np.abs(mid - float(center)) <= float(half_width)) & sourced
    hold_bar, broke_bar = (outcomes if outcomes is not None
                           else outcome_pair(tape, half_width, side))
    held = touch & (hold_bar < broke_bar)
    broke = touch & (broke_bar < hold_bar)
    where = np.flatnonzero(touch)
    gap = (float(int(reference_stamp_ns) - int(tape.ts[where[-1]]))
           / float(NANOS_PER_MINUTE)) if len(where) else float("nan")
    return {"touches": float(touch.sum()), "held": float(held.sum()),
            "broke": float(broke.sum()), "mins_since_touch": gap,
            "touch_delta": float(np.asarray(tape.delta, np.float64)[touch].sum()),
            "n_source_bars": int(sourced.sum())}


def day_scale_terms(cell_mid: Sequence[float], cell_ts: Sequence[int],
                    center: float, half_width: float, decision_stamp_ns: int,
                    *, zone_kind: str | None, approach_side: int | None,
                    mode: str = "approach") -> dict[str, float]:
    """Sweep 22's day-scale proxy, numerically unchanged, correctly named.

    ``day_scale_held`` is sweep 22's ``pd_held``: one for a price a COMPLETED
    session turned at - a prior-day extreme or a prior-EXPLORE value edge - and
    zero otherwise.  ``day_scale_broke`` is sweep 22's ``pd_broke``: has TODAY
    already traded a full width beyond this price, strictly before the decision?
    Mode "approach" is the lane-1 form, one-sided against the approach; mode
    "close" is the lane-2 form, which reads one when the day has traversed BOTH
    sides and otherwise falls back to the approach form.  The scan is over the
    CELL's own bars, as sweep 22 scanned ``mid[:bar]``, not over the day tape.

    Sol's ruling stands over the whole block: this is a day-scale persistence
    and location proxy.  Its positive and negative terms describe different
    horizons and it is not a defence pair.
    """

    if str(mode) not in DAY_SCALE_MODES:
        raise ZoneStop(f"unknown day-scale mode: {mode}")
    stamps = np.asarray(cell_ts, np.int64)
    prior = int(np.searchsorted(stamps, np.int64(decision_stamp_ns), side="left"))
    values = np.asarray(cell_mid, np.float64)[:prior]
    held = (float("nan") if zone_kind is None else
            (1.0 if str(zone_kind) in DAY_SCALE_TURN_KINDS else 0.0))
    if prior <= 0:
        return {"held": held, "broke": float("nan"),
                "persistence": float("nan"), "bars": 0}
    above = float(values.max()) > float(center) + float(half_width)
    below = float(values.min()) < float(center) - float(half_width)
    if approach_side is None:
        one_sided = float("nan")
    else:
        one_sided = 1.0 if (above if int(approach_side) > 0 else below) else 0.0
    broke = one_sided
    if str(mode) == "close" and above and below:
        broke = 1.0
    persistence = (held - broke
                   if not (math.isnan(held) or math.isnan(broke))
                   else float("nan"))
    return {"held": held, "broke": broke, "persistence": persistence,
            "bars": int(prior)}


# --------------------------------------------------------------------------
# The query and the row.
# --------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class ZoneQuery:
    """One fixed-zone read.

    ``cell`` is the prep-cache record index, the key sweep 8 calls
    ``Cell8.position`` and sweep 22 stores as ``Cand.cell``.  ``zone_price`` and
    ``band_width`` are mid2; ``band_width`` is the HALF width, matching
    ``mult * atr_mid2`` in the cache.  ``side`` is the fade side being scored.
    ``zone_kind`` and ``approach_side`` feed only the day-scale proxy and are
    optional; the terms that need them are NaN when they are absent.
    """

    cell: int
    zone_price: float
    band_width: float
    decision_stamp_ns: int
    side: int
    zone_kind: str | None = None
    approach_side: int | None = None
    day_scale_mode: str = "approach"


@dataclass(slots=True)
class ZoneRow:
    """The answer, with the evidence that it is causal and correctly centred."""

    asset: str
    d8: int
    phase: str
    cell: int
    side: int
    zone_kind: str
    center_price: float
    band_width: float
    decision_stamp_ns: int
    max_source_stamp: int
    n_source_bars: int
    sd_touches: float
    sd_held: float
    sd_broke: float
    sd_mins_since_touch: float
    sd_touch_delta: float
    ps_touches: float
    ps_held: float
    ps_broke: float
    ps_mins_since_touch: float
    ps_touch_delta: float
    ps_sess_d8: int
    ps_served: bool
    n_ps_source_bars: int
    day_scale_held: float
    day_scale_broke: float
    day_scale_persistence: float
    day_scale_mode: str
    n_day_scale_bars: int

    def as_dict(self) -> dict[str, object]:
        out: dict[str, object] = {}
        for name in ZONE_ROW_FIELDS:
            value = getattr(self, name)
            if isinstance(value, float) and not math.isfinite(value):
                out[name] = None
            elif isinstance(value, (np.floating, np.integer)):
                out[name] = value.item()
            else:
                out[name] = value
        return out


# --------------------------------------------------------------------------
# The reader.  One day resident at a time, outcome arrays memoised per
# (day, width, side) because they do not depend on the zone price.
# --------------------------------------------------------------------------

@dataclass
class ZoneReader:
    """The accessor over the real mill shards and flow caches.

    Nothing is written.  The day tape is built by ``build_levels.day_tape``, the
    same construction the cache was built from, so the same-day memory here is
    "earlier in the same day across ALL phases" exactly as the cache means it.
    """

    assets: tuple[str, ...] = ASSETS
    tape_slots: int = 6
    _records: list = field(default_factory=list, repr=False)
    _index: dict = field(default_factory=dict, repr=False)
    _explore: dict = field(default_factory=dict, repr=False)
    _tapes: dict = field(default_factory=dict, repr=False)
    _tape_order: list = field(default_factory=list, repr=False)
    _spans: dict = field(default_factory=dict, repr=False)
    _outcomes: dict = field(default_factory=dict, repr=False)
    _bl: object = field(default=None, repr=False)
    counters: dict = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        # Imported here, not at module import, so the selftest and every law
        # function above run with numpy and levels.py alone.
        import build_levels as BL
        import sweep1 as S1

        self._bl = BL
        records, _days = S1.load_cache()
        self._records = list(records)
        index: dict[tuple[str, int], list[int]] = {}
        for position, rec in enumerate(self._records):
            index.setdefault((rec.asset, int(rec.d8)), []).append(position)
        self._index = index
        self._explore = S1._explore_days(tuple(self.assets))
        self.counters = {"rows": 0, "tape_builds": 0, "outcome_builds": 0,
                         "prior_session_served": 0, "prior_session_absent": 0,
                         "empty_window": 0, "undefined_same_day": 0}

    # -- tapes ------------------------------------------------------------

    def _tape(self, asset: str, d8: int) -> Tape | None:
        key = (str(asset), int(d8))
        if key in self._tapes:
            return self._tapes[key]
        import flow as FLOW

        positions = self._index.get(key, [])
        if not positions:
            built = None
        else:
            try:
                built = tape_from_day(self._bl.day_tape(
                    self._records, positions, FLOW.load_flow(asset, int(d8)),
                    asset, int(d8)))
            except Exception:  # noqa: BLE001 - an absent day is a NaN, not a crash
                built = None
        self.counters["tape_builds"] += 1
        # The span outlives the tape.  It is three integers, it never changes,
        # and the causality audit asks about it for every row - rebuilding a
        # whole day to reread its first and last stamp would be the only slow
        # part of this accessor.
        self._spans[key] = ((int(built.ts[0]), int(built.ts[-1]), int(built.n))
                            if built is not None and built.n > 0 else None)
        self._tapes[key] = built
        self._tape_order.append(key)
        while len(self._tape_order) > int(self.tape_slots):
            self._tapes.pop(self._tape_order.pop(0), None)
        return built

    def span(self, asset: str, d8: int) -> tuple[int, int, int] | None:
        """``(first close, last close, bars)`` of a day tape, built if needed."""

        key = (str(asset), int(d8))
        if key not in self._spans:
            self._tape(asset, int(d8))
        return self._spans.get(key)

    def _prev_explore_d8(self, asset: str, d8: int) -> int:
        earlier = [int(day) for day in self._explore.get(str(asset), ())
                   if int(day) < int(d8)]
        return max(earlier) if earlier else -1

    def _outcome(self, tape: Tape, half_width: float, side: int
                 ) -> tuple[np.ndarray, np.ndarray]:
        key = (str(tape.asset), int(tape.d8), round(float(half_width), 6),
               int(side))
        if key not in self._outcomes:
            if len(self._outcomes) > 64:
                self._outcomes.clear()
            self._outcomes[key] = outcome_pair(tape, half_width, side)
            self.counters["outcome_builds"] += 1
        return self._outcomes[key]

    # -- the accessor -----------------------------------------------------

    def row(self, query: ZoneQuery) -> ZoneRow:
        """One fixed-zone read.  Total: an unknown cell returns NaNs, not a raise."""

        self.counters["rows"] += 1
        if int(query.side) not in LV.SIDES:
            raise ZoneStop(f"side must be +1 or -1, got {query.side}")
        if not float(query.band_width) > 0.0:
            raise ZoneStop(f"band width must be positive, got {query.band_width}")
        position = int(query.cell)
        if not 0 <= position < len(self._records):
            raise ZoneStop(f"no prep-cache record at cell {position}")
        rec = self._records[position]
        asset, d8 = str(rec.asset), int(rec.d8)
        width = float(query.band_width)
        stamp = int(query.decision_stamp_ns)

        tape = self._tape(asset, d8)
        if tape is None:
            raise ZoneStop(f"no day tape for {asset}/{d8}")
        window = prior_window(tape, stamp)
        center = resolved_center(float(query.zone_price), tape, window)
        same = same_day_counts(tape, center, width, int(query.side), stamp,
                               outcomes=self._outcome(tape, width, int(query.side)))
        if window <= 0:
            self.counters["empty_window"] += 1
        if not math.isfinite(same["touches"]):
            self.counters["undefined_same_day"] += 1

        prev_d8 = self._prev_explore_d8(asset, d8)
        prev = self._tape(asset, prev_d8) if prev_d8 > 0 else None
        # The licence: the prior session is served only where its own last stamp
        # is strictly before the decision.  Nine EXPLORE asset-days carry a
        # prior session that closed after the current session opened.
        served = bool(prev is not None and prev.n > 0
                      and int(prev.ts[-1]) < stamp)
        if served:
            self.counters["prior_session_served"] += 1
            prior = session_counts(prev, center, width, int(query.side), stamp,
                                   outcomes=self._outcome(prev, width,
                                                          int(query.side)))
        else:
            self.counters["prior_session_absent"] += 1
            prior = {"touches": float("nan"), "held": float("nan"),
                     "broke": float("nan"), "mins_since_touch": float("nan"),
                     "touch_delta": float("nan"), "n_source_bars": 0}

        scale = day_scale_terms(
            np.asarray(rec.mid, np.float64), np.asarray(rec.lat, np.int64),
            center, width, stamp, zone_kind=query.zone_kind,
            approach_side=query.approach_side, mode=str(query.day_scale_mode))

        # The conservative source bound: the last current-day bar whose close
        # precedes the decision, and the prior session's last stamp where that
        # family is served.  Everything the read could have seen closed by then.
        stamps: list[int] = []
        if window > 0:
            stamps.append(int(tape.ts[window - 1]))
        if served and prev is not None:
            stamps.append(int(prev.ts[-1]))
        max_source = max(stamps) if stamps else -1

        return ZoneRow(
            asset=asset, d8=d8, phase=str(rec.phase), cell=position,
            side=int(query.side),
            zone_kind=("" if query.zone_kind is None else str(query.zone_kind)),
            center_price=float(center), band_width=width,
            decision_stamp_ns=stamp, max_source_stamp=int(max_source),
            n_source_bars=int(same["n_source_bars"]),
            sd_touches=float(same["touches"]), sd_held=float(same["held"]),
            sd_broke=float(same["broke"]),
            sd_mins_since_touch=float(same["mins_since_touch"]),
            sd_touch_delta=float(same["touch_delta"]),
            ps_touches=float(prior["touches"]), ps_held=float(prior["held"]),
            ps_broke=float(prior["broke"]),
            ps_mins_since_touch=float(prior["mins_since_touch"]),
            ps_touch_delta=float(prior["touch_delta"]),
            ps_sess_d8=int(prev_d8), ps_served=bool(served),
            n_ps_source_bars=int(prior["n_source_bars"]),
            day_scale_held=float(scale["held"]),
            day_scale_broke=float(scale["broke"]),
            day_scale_persistence=float(scale["persistence"]),
            day_scale_mode=str(query.day_scale_mode),
            n_day_scale_bars=int(scale["bars"]))

    def rows(self, queries: Sequence[ZoneQuery]) -> list[ZoneRow]:
        """Every query, cheapest first: one day resident, one outcome pass each.

        Sorted by ``(asset, d8, width, side)`` so the tape and the outcome
        arrays are built once per group; the caller's order is restored.
        """

        order = sorted(range(len(queries)), key=lambda i: (
            str(self._records[int(queries[i].cell)].asset),
            int(self._records[int(queries[i].cell)].d8),
            round(float(queries[i].band_width), 6), int(queries[i].side)))
        out: list[ZoneRow | None] = [None] * len(queries)
        for position in order:
            out[position] = self.row(queries[position])
        if any(row is None for row in out):
            raise ZoneStop("the accessor left a query unanswered")
        return [row for row in out]  # type: ignore[misc]


_READER: ZoneReader | None = None


def reader(assets: Sequence[str] = ASSETS) -> ZoneReader:
    """The process-wide accessor.  Building it loads the prep cache once."""

    global _READER
    if _READER is None:
        _READER = ZoneReader(assets=tuple(assets))
    return _READER


def read_zone(cell: int, zone_price: float, band_width: float,
              decision_stamp_ns: int, side: int, *, zone_kind: str | None = None,
              approach_side: int | None = None,
              day_scale_mode: str = "approach") -> ZoneRow:
    """THE accessor.  Defence history at a NAMED price, as of a decision stamp."""

    return reader().row(ZoneQuery(
        cell=int(cell), zone_price=float(zone_price),
        band_width=float(band_width), decision_stamp_ns=int(decision_stamp_ns),
        side=int(side), zone_kind=zone_kind, approach_side=approach_side,
        day_scale_mode=str(day_scale_mode)))


# --------------------------------------------------------------------------
# The independent recount.  Deliberately the long way: the accessor is a
# vectorized pass over prefix masks, so the only recount worth having walks the
# bars one at a time and never touches a numpy comparison the accessor uses.
# --------------------------------------------------------------------------

def hand_recount(tape: Tape, center: float, half_width: float, side: int,
                 decision_stamp_ns: int) -> dict[str, float]:
    """Plain-loop touches, held, broke at a FIXED centre, in Python."""

    hold_step = LV.HOLD_BANDS * float(half_width) * (1.0 if side > 0 else -1.0)
    breach_step = LV.BREACH_BANDS * float(half_width) * (1.0 if side > 0 else -1.0)
    stop = 0
    while stop < tape.n and int(tape.ts[stop]) < int(decision_stamp_ns):
        stop += 1
    touches = held = broke = 0
    delta = 0.0
    last = -1
    sourced_bars = 0
    for j in range(stop):
        if not bool(tape.sourced[j]):
            continue
        sourced_bars += 1
        if abs(float(tape.mid[j]) - float(center)) > float(half_width):
            continue
        touches += 1
        last = j
        delta += float(tape.delta[j])
        price = float(tape.mid[j])
        hold_bar, broke_bar = -1, -1
        for t in range(j + 1, tape.n):
            value = float(tape.mid[t])
            if hold_bar < 0 and (value >= price + hold_step if side > 0
                                 else value <= price + hold_step):
                hold_bar = t
            if broke_bar < 0 and (value < price - breach_step if side > 0
                                  else value > price - breach_step):
                broke_bar = t
            if hold_bar >= 0 and broke_bar >= 0:
                break
        hold_seen = hold_bar >= 0 and int(tape.ts[hold_bar]) < int(decision_stamp_ns)
        broke_seen = broke_bar >= 0 and int(tape.ts[broke_bar]) < int(decision_stamp_ns)
        if hold_seen and (broke_bar < 0 or hold_bar < broke_bar):
            held += 1
        if broke_seen and (hold_bar < 0 or broke_bar < hold_bar):
            broke += 1
    if sourced_bars == 0:
        return {"touches": float("nan"), "held": float("nan"),
                "broke": float("nan"), "touch_delta": float("nan"),
                "mins_since_touch": float("nan")}
    return {"touches": float(touches), "held": float(held),
            "broke": float(broke), "touch_delta": delta,
            "mins_since_touch": (
                float(int(decision_stamp_ns) - int(tape.ts[last]))
                / float(NANOS_PER_MINUTE) if last >= 0 else float("nan"))}


def hand_recount_session(tape: Tape, center: float, half_width: float,
                         side: int) -> dict[str, float]:
    """The same plain loop over a COMPLETED session: no verdict is withheld."""

    hold_step = LV.HOLD_BANDS * float(half_width) * (1.0 if side > 0 else -1.0)
    breach_step = LV.BREACH_BANDS * float(half_width) * (1.0 if side > 0 else -1.0)
    touches = held = broke = 0
    sourced_bars = 0
    for j in range(tape.n):
        if not bool(tape.sourced[j]):
            continue
        sourced_bars += 1
        if abs(float(tape.mid[j]) - float(center)) > float(half_width):
            continue
        touches += 1
        price = float(tape.mid[j])
        hold_bar, broke_bar = -1, -1
        for t in range(j + 1, tape.n):
            value = float(tape.mid[t])
            if hold_bar < 0 and (value >= price + hold_step if side > 0
                                 else value <= price + hold_step):
                hold_bar = t
            if broke_bar < 0 and (value < price - breach_step if side > 0
                                  else value > price - breach_step):
                broke_bar = t
            if hold_bar >= 0 and broke_bar >= 0:
                break
        if hold_bar >= 0 and (broke_bar < 0 or hold_bar < broke_bar):
            held += 1
        if broke_bar >= 0 and (hold_bar < 0 or broke_bar < hold_bar):
            broke += 1
    if sourced_bars == 0:
        return {"touches": float("nan"), "held": float("nan"),
                "broke": float("nan")}
    return {"touches": float(touches), "held": float(held),
            "broke": float(broke)}


# --------------------------------------------------------------------------
# Selftest: synthetic bars only.  Zero era bytes, no cache, no shard.
# --------------------------------------------------------------------------

SELFTEST_ATR = 100.0
SELFTEST_WIDTH = 10.0          # 0.10 * 100, the cache's narrowest band
SELFTEST_OPEN_NS = 1_700_000_000_000_000_000


def _fixture_tape(asset: str, d8: int, mid: Sequence[float], open_ns: int) -> Tape:
    """``build_levels``'s fixture tape, rebuilt locally: delta is bar ordinal + 1."""

    values = np.asarray(mid, np.float64)
    bars = len(values)
    ts = open_ns + NANOS_PER_MINUTE * np.arange(1, bars + 1, dtype=np.int64)
    return Tape(asset, int(d8), ts, values,
                np.arange(1.0, bars + 1.0), np.ones(bars, bool))


def _fixture() -> tuple[Tape, Tape]:
    """The builder's two-day fixture, rebuilt here so no private state is imported.

    TODAY  [500, 300, 100, 105, 130, 100, 88, 121, 103, 96, 300, 104]
    PRIOR  [300, 105, 130, 100, 85, 300]
    Half width 10 throughout.  Every count below is hand-computed in the check
    that asserts it.
    """

    today = _fixture_tape(
        "HG", 20220318,
        [500, 300, 100, 105, 130, 100, 88, 121, 103, 96, 300, 104],
        SELFTEST_OPEN_NS)
    prior = _fixture_tape("HG", 20220315, [300, 105, 130, 100, 85, 300],
                          SELFTEST_OPEN_NS - 86_400 * NANOS_PER_MINUTE)
    return today, prior


def selftest() -> int:
    mutant = _mutant()
    today, prior = _fixture()
    width = SELFTEST_WIDTH
    end_of_day = int(today.ts[11]) + NANOS_PER_MINUTE     # after bar 11 closed
    at_bar_11 = int(today.ts[11])                          # bars 0..10 visible
    at_bar_8 = int(today.ts[8])                            # bars 0..7 visible
    failures: list[str] = []

    def _check(name: str, body) -> None:
        try:
            body()
        except Exception as error:  # noqa: BLE001 - a red case is the signal
            failures.append(f"{name}: {type(error).__name__}: {error}")

    def sd(zone: float, side: int, stamp: int) -> dict[str, float]:
        center = resolved_center(zone, today, prior_window(today, stamp))
        return same_day_counts(today, center, width, side, stamp)

    def ps(zone: float, side: int, stamp: int) -> dict[str, float]:
        center = resolved_center(zone, today, prior_window(today, stamp))
        return session_counts(prior, center, width, side, stamp)

    def zone_never_visited() -> None:
        # 200 with a half width of 10 is [190, 210].  The path prints 500, 300,
        # 130, 121, 104 and below - nothing inside.  Twelve sourced bars have
        # closed, so the answer is a DEFINED zero, not "unknown".
        row = sd(200.0, 1, end_of_day)
        assert row["touches"] == 0.0, f"touches {row['touches']}"
        assert row["held"] == 0.0, f"held {row['held']}"
        assert row["broke"] == 0.0, f"broke {row['broke']}"
        assert row["touch_delta"] == 0.0, f"delta {row['touch_delta']}"
        assert math.isnan(row["mins_since_touch"]), "a never-touched price aged"
        assert row["n_source_bars"] == 12, f"bars {row['n_source_bars']}"
        # The prior session never visits 200 either: 300, 105, 130, 100, 85, 300.
        edge = ps(200.0, 1, end_of_day)
        assert edge["touches"] == 0.0, f"ps touches {edge['touches']}"
        assert edge["held"] == 0.0 and edge["broke"] == 0.0, "ps outcome at 200"

    def zone_crossed_repeatedly() -> None:
        # 100 with a half width of 10 is [90, 110].  Inside it: bars 2 (100),
        # 3 (105), 5 (100), 8 (103), 9 (96) and 11 (104) - six touches; bar 6
        # (88) misses by two.  Side +1: bar 2 reaches 110 at bar 4 before 90 at
        # bar 6, bar 3 reaches 115 at bar 4, bars 8 and 9 reach 113 and 106 at
        # bar 10 - four holds.  Bar 5 prints 88 at bar 6 before 110 at bar 7 -
        # one break.  Bar 11 has no later bar at all, so it is a touch with no
        # verdict.  Delta is the bar ordinal plus one: 3+4+6+9+10+12 = 44.
        row = sd(100.0, 1, end_of_day)
        assert row["touches"] == 6.0, f"touches {row['touches']}"
        assert row["held"] == 4.0, f"held {row['held']}"
        assert row["broke"] == 1.0, f"broke {row['broke']}"
        assert row["touch_delta"] == 44.0, f"delta {row['touch_delta']}"
        # The last touch is bar 11 and the stamp is one minute past its close.
        assert row["mins_since_touch"] == 1.0, f"gap {row['mins_since_touch']}"
        # Side -1 mirrors every leg: the four that were lifted first now break.
        low = sd(100.0, -1, end_of_day)
        assert low["touches"] == 6.0, f"touches- {low['touches']}"
        assert low["held"] == 1.0, f"held- {low['held']}"
        assert low["broke"] == 4.0, f"broke- {low['broke']}"
        # The same fixed price one bar earlier.  Bar 11 has not closed, so the
        # sixth touch is gone and bar 9 is the most recent, two minutes back;
        # bars 8 and 9 have by then resolved at bar 10.  The counts move with
        # the STAMP and not with wherever price happens to be standing, which is
        # the whole point: at this stamp price sits at 300, nowhere near 100.
        earlier = sd(100.0, 1, at_bar_11)
        assert earlier["touches"] == 5.0, f"touches@11 {earlier['touches']}"
        assert earlier["held"] == 4.0, f"held@11 {earlier['held']}"
        assert earlier["broke"] == 1.0, f"broke@11 {earlier['broke']}"
        assert earlier["touch_delta"] == 32.0, f"delta@11 {earlier['touch_delta']}"
        assert earlier["mins_since_touch"] == 2.0, (
            f"gap@11 {earlier['mins_since_touch']}")

    def fixed_center_reproduces_the_cache_row() -> None:
        # The one case where the fixed-zone read and the cache row MUST agree:
        # ask for the price the reading bar happens to sit on.  Bar 11's mid is
        # 104 and the builder's own fixture documents that row as five touches,
        # four holds, one break, delta 32 and a two-minute gap; side -1 is one
        # and four.  Reading at bar 11's stamp shows bars 0..10, which is what
        # the cache row shows.
        row = sd(104.0, 1, at_bar_11)
        assert row["touches"] == 5.0, f"touches {row['touches']}"
        assert row["held"] == 4.0, f"held {row['held']}"
        assert row["broke"] == 1.0, f"broke {row['broke']}"
        assert row["touch_delta"] == 32.0, f"delta {row['touch_delta']}"
        assert row["mins_since_touch"] == 2.0, f"gap {row['mins_since_touch']}"
        low = sd(104.0, -1, at_bar_11)
        assert low["held"] == 1.0 and low["broke"] == 4.0, (
            f"mirror {low['held']}/{low['broke']}")

    def prior_session_at_the_same_fixed_price() -> None:
        # The prior session inside [94, 114]: 105 at bar 1 and 100 at bar 3.
        # Bar 1 reaches 115 at bar 2 (held); bar 3 prints 85 at bar 4 before
        # reaching 110 at bar 5 (broke).  A completed session withholds nothing.
        row = ps(104.0, 1, at_bar_11)
        assert row["touches"] == 2.0, f"ps touches {row['touches']}"
        assert row["held"] == 1.0, f"ps held {row['held']}"
        assert row["broke"] == 1.0, f"ps broke {row['broke']}"
        # The same two bars sit inside [90, 110], so the same pair answers 100.
        wide = ps(100.0, 1, at_bar_11)
        assert wide["touches"] == 2.0, f"ps touches@100 {wide['touches']}"
        assert wide["held"] == 1.0 and wide["broke"] == 1.0, (
            f"ps outcome@100 {wide['held']}/{wide['broke']}")
        # It reads the PRIOR tape and only the prior tape: today's bar 11 sits
        # at 104 and would be a third touch if the current day leaked in.
        assert int(prior.ts[-1]) < int(today.ts[0]), "the fixture sessions overlap"

    def anchored_outcome_at_fixed_center() -> None:
        # Moving the CENTRE to a fixed price must not move the OUTCOME ANCHOR
        # onto it.  Zone 113, half width 10, side +1, read at bar 9's stamp:
        # bars 0..8 are visible and bars 3 (105), 7 (121) and 8 (103) sit inside
        # [103, 123] - bar 8 exactly on the lower edge, which is a touch.
        # Bar 7's touch is anchored at 121, so its breach leg is 111 and bar 8
        # (103) crosses it, a verdict that lands INSIDE the window.  Anchored on
        # the centre instead the breach leg would be 103, which bar 8 does not
        # cross (the tie goes to the level) and bar 9 (96) only crosses at the
        # decision itself - so the wrong law would report no break at all.
        row = sd(113.0, 1, int(today.ts[9]))
        assert row["touches"] == 3.0, f"touches {row['touches']}"
        assert row["held"] == 1.0, f"held {row['held']}"
        assert row["broke"] == 1.0, f"broke {row['broke']}"
        hold_bar, broke_bar = outcome_pair(today, width, 1)
        assert int(broke_bar[7]) == 8, f"anchored breach bar {int(broke_bar[7])}"
        # The counterfactual, computed here so the discrimination is visible
        # rather than asserted: resolve every touch against the CENTRE's band
        # instead of its own price and the break disappears.
        centre_broke = 0
        for j in (3, 7, 8):
            hold_at = next((t for t in range(j + 1, today.n)
                            if float(today.mid[t]) >= 113.0 + width), today.n)
            broke_at = next((t for t in range(j + 1, today.n)
                             if float(today.mid[t]) < 113.0 - width), today.n)
            if broke_at < hold_at and int(today.ts[broke_at]) < int(today.ts[9]):
                centre_broke += 1
        assert centre_broke == 0, (
            f"the centre-anchored counterfactual broke {centre_broke} times, so "
            "this fixture no longer discriminates the two laws")

    def unresolved_is_not_an_outcome() -> None:
        # Read at bar 9's stamp with the centre at bar 9's own price, 96: the
        # band is [86, 106] and bars 2, 3, 5, 6 and 8 are inside.  Bar 8's
        # verdict lands at bar 10, so it is a touch with no outcome yet.
        row = sd(96.0, 1, int(today.ts[9]))
        assert row["touches"] == 5.0, f"touches@9 {row['touches']}"
        assert row["held"] == 3.0, f"held@9 {row['held']}"
        assert row["broke"] == 1.0, f"broke@9 {row['broke']}"

    def empty_window_is_undefined() -> None:
        # Before the first bar closes there is no memory at all.  That is NaN,
        # not zero: "nothing has happened here" and "I cannot see" differ.
        row = sd(104.0, 1, int(today.ts[0]))
        assert math.isnan(row["touches"]), f"touches {row['touches']}"
        assert row["n_source_bars"] == 0, f"bars {row['n_source_bars']}"

    def hand_recount_agrees() -> None:
        # The vectorized law against the plain loop, on every fixture case.
        for zone, side, stamp in ((200.0, 1, end_of_day), (100.0, 1, end_of_day),
                                  (100.0, -1, end_of_day), (104.0, 1, at_bar_11),
                                  (113.0, 1, int(today.ts[9])),
                                  (113.0, -1, int(today.ts[9])),
                                  (96.0, 1, at_bar_8), (96.0, -1, at_bar_8)):
            centre = resolved_center(zone, today, prior_window(today, stamp))
            fast = same_day_counts(today, centre, width, side, stamp)
            slow = hand_recount(today, centre, width, side, stamp)
            for name in ("touches", "held", "broke", "touch_delta",
                         "mins_since_touch"):
                a, b = float(fast[name]), float(slow[name])
                same = (math.isnan(a) and math.isnan(b)) or a == b
                assert same, f"{zone}/{side} {name}: fast={a} slow={b}"
            centre_p = centre
            fast_p = session_counts(prior, centre_p, width, side, stamp)
            slow_p = hand_recount_session(prior, centre_p, width, side)
            for name in ("touches", "held", "broke"):
                a, b = float(fast_p[name]), float(slow_p[name])
                same = (math.isnan(a) and math.isnan(b)) or a == b
                assert same, f"ps {zone}/{side} {name}: fast={a} slow={b}"

    def day_scale_proxy() -> None:
        # The cell IS the fixture tape here.  Read at bar 4's stamp the cell has
        # printed 500, 300, 100, 105.  Zone 100, half width 10: the day has
        # traded above 110 (bar 0 at 500) and never below 90.
        cell_mid, cell_ts = today.mid, today.ts
        up = day_scale_terms(cell_mid, cell_ts, 100.0, width, int(today.ts[4]),
                             zone_kind="PD_LOW", approach_side=1)
        assert up["held"] == 1.0 and up["broke"] == 1.0, (
            f"approach from below {up['held']}/{up['broke']}")
        assert up["persistence"] == 0.0, f"persistence {up['persistence']}"
        down = day_scale_terms(cell_mid, cell_ts, 100.0, width, int(today.ts[4]),
                               zone_kind="PD_LOW", approach_side=-1)
        assert down["broke"] == 0.0, f"approach from above {down['broke']}"
        assert down["persistence"] == 1.0, f"persistence {down['persistence']}"
        # A kind no completed session turned at carries no positive term.
        plain = day_scale_terms(cell_mid, cell_ts, 100.0, width,
                                int(today.ts[4]), zone_kind="SAME_DAY",
                                approach_side=-1)
        assert plain["held"] == 0.0, f"same-day held {plain['held']}"
        assert plain["persistence"] == -0.0 or plain["persistence"] == 0.0, (
            f"same-day persistence {plain['persistence']}")
        # Mode "close" reads one only when BOTH sides have been traversed; at
        # bar 4 only the upside has, so it falls back to the approach form.
        close_early = day_scale_terms(cell_mid, cell_ts, 100.0, width,
                                      int(today.ts[4]), zone_kind="PD_LOW",
                                      approach_side=-1, mode="close")
        assert close_early["broke"] == 0.0, f"close early {close_early['broke']}"
        # By bar 8 the day has printed 88, so both sides are traversed and the
        # close form reads one whatever the approach side was.
        close_late = day_scale_terms(cell_mid, cell_ts, 100.0, width,
                                     int(today.ts[8]), zone_kind="PD_LOW",
                                     approach_side=-1, mode="close")
        assert close_late["broke"] == 1.0, f"close late {close_late['broke']}"
        # An absent approach side leaves the one-sided term undefined, never zero.
        blind = day_scale_terms(cell_mid, cell_ts, 100.0, width,
                                int(today.ts[4]), zone_kind="PD_LOW",
                                approach_side=None)
        assert math.isnan(blind["broke"]), f"blind broke {blind['broke']}"
        assert math.isnan(blind["persistence"]), "a blind proxy was numbered"

    def center_is_the_requested_price() -> None:
        # The gate, on the synthetic path: the centre used IS the price asked
        # for, at every stamp, including one where the reading bar sits far away.
        for zone in (200.0, 100.0, 104.0, 96.0):
            for stamp in (at_bar_8, at_bar_11, end_of_day):
                got = resolved_center(zone, today, prior_window(today, stamp))
                assert got == zone, f"centre {got} for zone {zone} at {stamp}"

    _check("zone_never_visited", zone_never_visited)
    _check("zone_crossed_repeatedly", zone_crossed_repeatedly)
    _check("fixed_center_reproduces_the_cache_row",
           fixed_center_reproduces_the_cache_row)
    _check("prior_session_at_the_same_fixed_price",
           prior_session_at_the_same_fixed_price)
    _check("anchored_outcome_at_fixed_center", anchored_outcome_at_fixed_center)
    _check("unresolved_is_not_an_outcome", unresolved_is_not_an_outcome)
    _check("empty_window_is_undefined", empty_window_is_undefined)
    _check("hand_recount_agrees", hand_recount_agrees)
    _check("day_scale_proxy", day_scale_proxy)
    _check("center_is_the_requested_price", center_is_the_requested_price)

    cases = 10
    expected_red = {MUTANT_CENTER_MID: ("center_is_the_requested_price",
                                        "zone_never_visited",
                                        "zone_crossed_repeatedly",
                                        "fixed_center_reproduces_the_cache_row")}
    if mutant:
        died = {line.split(":", 1)[0] for line in failures}
        targets = expected_red.get(mutant)
        if targets is None:
            print(f"levels_zone_selftest_unknown_mutant {mutant}")
            return 1
        missed = [name for name in targets if name not in died]
        if missed:
            print(f"levels_zone_selftest_mutant_survived mutant={mutant} "
                  f"cases={missed}")
            return 1
        print(f"levels_zone_selftest_red mutant={mutant} cases={cases} "
              f"died={sorted(died)}")
        for line in failures:
            print(f"  {line}")
        return 1
    if failures:
        print("levels_zone_selftest_red died="
              f"{sorted(line.split(':', 1)[0] for line in failures)}")
        for line in failures:
            print(f"  {line}")
        return 1
    print(f"levels_zone_selftest_ok cases={cases}")
    return 0


# --------------------------------------------------------------------------
# The audit over real queries.  Sweep 22's zone catalogue is imported READ ONLY
# and its formation pass is re-run to draw genuine (cell, zone price, decision
# stamp) triples; nothing in sweep 22 is modified and no outcome is opened.
# --------------------------------------------------------------------------

def draw_queries(rows: int = VERIFY_ROWS, seed: int = VERIFY_SEED
                 ) -> tuple[list[ZoneQuery], list[dict[str, object]],
                            dict[str, object]]:
    """Real triples from sweep 22's own formed candidates, stratified.

    Every asset and every zone kind sweep 22 forms gets an equal share, and each
    drawn candidate contributes its lane-1 decision stamp (the approach bar) and,
    where its episode resolved, its lane-2 stamps (the window close, which is the
    bar sweep 22 reads at, and the entry bar, which is the stamp its day-scale
    close term is built at).
    """

    import sweep1 as S1
    import sweep8 as S8
    import sweep22 as S22

    if tuple(S22.PD_HELD_KINDS) != DAY_SCALE_TURN_KINDS:
        raise ZoneStop("sweep 22's day-scale turn kinds drifted from this module")
    cells, _days, _skipped = S8.build_cells(ASSETS)
    explore = S1._explore_days(ASSETS)
    cands, formation = S22.formation_pass(cells, explore, "")
    if not formation["strictly_prior"]:
        raise ZoneStop("sweep 22's own formation pass is not strictly prior")
    records, _rec_days = S1.load_cache()

    by_stratum: dict[tuple[str, str], list[int]] = {}
    for position, cand in enumerate(cands):
        by_stratum.setdefault((cand.asset, cand.zone_kind), []).append(position)
    strata = sorted(by_stratum)
    per = max(1, int(math.ceil(rows / max(1, len(strata)))))
    rng = np.random.default_rng(int(seed))
    queries: list[ZoneQuery] = []
    meta: list[dict[str, object]] = []
    for stratum in strata:
        pool = by_stratum[stratum]
        take = rng.choice(len(pool), size=min(per, len(pool)), replace=False)
        for offset in sorted(int(value) for value in take):
            cand = cands[pool[offset]]
            lat = np.asarray(records[int(cand.cell)].lat, np.int64)
            flavours = [("L1_APPROACH", int(lat[int(cand.bar)]), "approach")]
            if int(cand.close_bar) >= 0:
                flavours.append(("L2_CLOSE_READ", int(lat[int(cand.close_bar)]),
                                 "approach"))
            if int(cand.entry_bar) >= 0:
                flavours.append(("L2_ENTRY", int(lat[int(cand.entry_bar)]),
                                 "close"))
            for flavour, stamp, mode in flavours:
                queries.append(ZoneQuery(
                    cell=int(cand.cell), zone_price=float(cand.zone_price),
                    band_width=float(cand.width), decision_stamp_ns=int(stamp),
                    side=int(cand.fade_side), zone_kind=str(cand.zone_kind),
                    approach_side=int(cand.approach_side), day_scale_mode=mode))
                meta.append({
                    "flavour": flavour, "asset": cand.asset, "d8": int(cand.d8),
                    "phase": cand.phase, "zone_kind": cand.zone_kind,
                    "approach_bar": int(cand.bar),
                    "close_bar": int(cand.close_bar),
                    "entry_bar": int(cand.entry_bar),
                    "s22_pd_held": float(cand.pd_held),
                    "s22_pd_broke": float(cand.pd_broke),
                    "s22_pd_broke_close": float(cand.pd_broke_close)})
    return queries, meta, {"candidates": len(cands), "strata": len(strata),
                           "per_stratum": per,
                           "formation_counters": formation["counters"]}


def cache_agreement(queries: Sequence[ZoneQuery], read: ZoneReader,
                    limit: int = 40) -> dict[str, object]:
    """The identity proof on REAL bytes: ask for the price the cache centred on.

    ``levels.py`` centres bar ``b``'s band on ``mid[b]``.  Point this accessor at
    THAT price, at ``lat[b]``, with the same width and side, and every same-day
    and prior-session count must equal the cached row to the bit.  The accessor
    is then demonstrably the cache's own law with a movable centre, and the only
    thing the fixed-zone read changes is the centre - which is the entire claim.

    A disagreement here refuses the unit: it would mean the fixed-zone read is a
    DIFFERENT law that merely looks similar, and no comparison with sweep 22's
    numbers would mean anything.
    """

    counters = {"checked": 0, "agreed": 0, "no_shard": 0, "no_cell": 0,
                "no_bar": 0, "width_off_grid": 0, "undefined_cache_row": 0}
    problems: list[str] = []
    seen: set[tuple[str, int, str, int, int]] = set()
    for query in queries:
        if counters["checked"] >= int(limit):
            break
        rec = read._records[int(query.cell)]
        asset, d8 = str(rec.asset), int(rec.d8)
        lat = np.asarray(rec.lat, np.int64)
        bar = int(np.searchsorted(lat, np.int64(query.decision_stamp_ns),
                                  side="left"))
        if not 0 <= bar < len(lat) or int(lat[bar]) != int(query.decision_stamp_ns):
            counters["no_bar"] += 1
            continue
        # The cache stores a fixed grid of widths; a query off that grid has no
        # cached row to be compared with, which is not a failure.
        atr = None
        mult_index = -1
        try:
            day = LV.load_levels(asset, d8)
        except LV.LevelStop:
            counters["no_shard"] += 1
            continue
        lcell = day.get((str(rec.phase), int(rec.phase_open_ts_ns)))
        if lcell is None:
            counters["no_cell"] += 1
            continue
        atr = float(lcell.atr_mid2)
        for index, mult in enumerate(LV.BAND_MULTS):
            if abs(float(mult) * atr - float(query.band_width)) <= 1e-6 * float(
                    query.band_width):
                mult_index = index
        if mult_index < 0:
            counters["width_off_grid"] += 1
            continue
        key = (asset, d8, str(rec.phase), bar, int(query.side))
        if key in seen:
            continue
        seen.add(key)
        cached = lcell.matrix(int(query.side), mult_index)[bar]
        centre = float(cached[LV.LEVEL_INDEX["band_center_mid2"]])
        if not np.isfinite(centre):
            counters["undefined_cache_row"] += 1
            continue
        # The float64 mid the builder centred on, before the shard's float32.
        row = read.row(ZoneQuery(
            cell=int(query.cell), zone_price=float(rec.mid[bar]),
            band_width=float(query.band_width),
            decision_stamp_ns=int(query.decision_stamp_ns),
            side=int(query.side)))
        counters["checked"] += 1
        ok = True
        for name, got in (("sd_touches", row.sd_touches),
                          ("sd_held", row.sd_held), ("sd_broke", row.sd_broke),
                          ("sd_mins_since_touch", row.sd_mins_since_touch),
                          ("sd_touch_delta", row.sd_touch_delta),
                          ("ps_touches", row.ps_touches),
                          ("ps_held", row.ps_held), ("ps_broke", row.ps_broke)):
            want = float(cached[LV.LEVEL_INDEX[name]])
            if math.isnan(want) and math.isnan(float(got)):
                continue
            # The shard is float32; a count is exact there, a flow sum is not.
            tolerance = 1e-5 * max(1.0, abs(want))
            if math.isnan(want) or math.isnan(float(got)) or abs(
                    float(got) - want) > tolerance:
                ok = False
                problems.append(
                    f"{asset}/{d8}/{rec.phase} bar={bar} side={query.side} "
                    f"{name}: accessor={got} cache={want}")
        counters["agreed"] += int(ok)
    return {"counters": counters, "problems": problems,
            "agrees": bool(counters["checked"] > 0
                           and counters["agreed"] == counters["checked"])}


def no_prior_session_rows(read: ZoneReader) -> dict[str, object]:
    """The unlicensed branch, on real days: an asset's FIRST EXPLORE session.

    Sweep 22 never forms a candidate there - its formation pass skips each
    asset's first EXPLORE day as warmup - so the real draw cannot reach this
    branch, and an untested branch in a unit whose whole product is trust is a
    hole.  With no prior EXPLORE session the ``ps_*`` family must be NaN while
    the same-day family stays defined, and the centre gate must still hold.
    """

    out: list[dict[str, object]] = []
    problems: list[str] = []
    for asset in read.assets:
        days = sorted(int(day) for day in read._explore.get(str(asset), ()))
        if not days:
            continue
        d8 = days[0]
        positions = read._index.get((str(asset), d8), [])
        if not positions:
            continue
        position = min(positions,
                       key=lambda p: int(read._records[p].phase_open_ts_ns))
        rec = read._records[position]
        bar = int(rec.n) // 2
        zone = float(rec.mid[bar])
        width = 0.20 * float(np.abs(np.diff(np.asarray(rec.mid, np.float64))).mean()
                             * 20.0 + 1.0)
        row = read.row(ZoneQuery(
            cell=int(position), zone_price=zone, band_width=width,
            decision_stamp_ns=int(rec.lat[bar]), side=1))
        if row.ps_served:
            problems.append(f"{asset}/{d8} served a prior session that is absent")
        for name, value in (("ps_touches", row.ps_touches),
                            ("ps_held", row.ps_held), ("ps_broke", row.ps_broke)):
            if not math.isnan(float(value)):
                problems.append(f"{asset}/{d8} {name} is {value}, want NaN")
        if not math.isfinite(row.sd_touches):
            problems.append(f"{asset}/{d8} same-day memory is undefined")
        if float(row.center_price) != zone:
            problems.append(f"{asset}/{d8} centre moved off the requested price")
        if int(row.max_source_stamp) >= int(row.decision_stamp_ns):
            problems.append(f"{asset}/{d8} source stamp is not prior")
        out.append({"asset": asset, "d8": d8, "cell": int(position),
                    "bar": bar, "ps_served": bool(row.ps_served),
                    "ps_sess_d8": int(row.ps_sess_d8),
                    "sd_touches": float(row.sd_touches),
                    "center_exact": bool(float(row.center_price) == zone),
                    "src_minus_decision_ns": int(row.max_source_stamp)
                    - int(row.decision_stamp_ns)})
    return {"rows": out, "problems": problems,
            "clean": bool(out and not problems)}


def _span_stats(values: Sequence[int]) -> dict[str, int]:
    order = sorted(int(value) for value in values)
    if not order:
        return {"rows": 0, "max": 0, "median": 0, "min": 0}
    return {"rows": len(order), "max": order[-1],
            "median": order[len(order) // 2], "min": order[0]}


def verify(rows: int = VERIFY_ROWS, hand_rows: int = HAND_ROWS,
           seed: int = VERIFY_SEED) -> dict[str, object]:
    """The four refuse gates, hard-asserted over real queries."""

    queries, meta, draw = draw_queries(rows=rows, seed=seed)
    read = reader()
    out = read.rows(queries)
    if len(out) != len(queries):
        raise ZoneStop("the accessor dropped a query")

    failures: list[str] = []
    worst_gap = -(1 << 62)
    worst_row = -1
    centers_exact = 0
    stamps_strict = 0
    ps_rows = 0
    ps_clean = 0
    s22_checked = {"approach": 0, "close": 0}
    s22_agree = {"approach": 0, "close": 0}
    per_asset: dict[str, int] = {}
    per_kind: dict[str, int] = {}
    per_flavour: dict[str, int] = {}
    defined_same_day = 0
    defined_prior_session = 0
    defined_day_scale = 0
    gaps: list[int] = []
    ps_gaps: list[int] = []
    ps_overlap: list[int] = []
    ps_overlap_rows = 0

    for position, (query, row, info) in enumerate(zip(queries, out, meta,
                                                      strict=True)):
        # GATE 1: the centre used IS the price asked for, bit for bit.
        if float(row.center_price) == float(query.zone_price):
            centers_exact += 1
        else:
            failures.append(
                f"row {position} {row.asset}/{row.d8} centre "
                f"{row.center_price!r} != zone {query.zone_price!r}")
        if float(row.band_width) != float(query.band_width):
            failures.append(f"row {position} width {row.band_width} != "
                            f"{query.band_width}")
        # GATE 2: every source stamp strictly precedes the decision.
        gap = int(row.max_source_stamp) - int(row.decision_stamp_ns)
        gaps.append(gap)
        if gap < 0:
            stamps_strict += 1
        else:
            failures.append(f"row {position} {row.asset}/{row.d8} source "
                            f"stamp is not prior: gap {gap} ns")
        if gap > worst_gap:
            worst_gap, worst_row = gap, position
        # GATE 4: the prior-session read never touches the current day.
        if row.ps_served:
            ps_rows += 1
            prev = read.span(row.asset, int(row.ps_sess_d8))
            today = read.span(row.asset, int(row.d8))
            clean = (int(row.ps_sess_d8) < int(row.d8) and prev is not None
                     and today is not None
                     and int(prev[1]) < int(today[0])
                     and int(prev[1]) < int(row.decision_stamp_ns))
            if prev is not None:
                ps_gaps.append(int(prev[1]) - int(row.decision_stamp_ns))
                if today is not None:
                    overlap = int(prev[1]) - int(today[0])
                    ps_overlap.append(overlap)
                    if overlap >= 0:
                        ps_overlap_rows += 1
            if clean:
                ps_clean += 1
            else:
                failures.append(
                    f"row {position} prior session {row.ps_sess_d8} is not "
                    f"clear of {row.d8}")
        # Comparability: the day-scale proxy reproduces sweep 22's own number.
        if str(info["flavour"]) == "L1_APPROACH":
            s22_checked["approach"] += 1
            if (float(row.day_scale_held) == float(info["s22_pd_held"])
                    and float(row.day_scale_broke) == float(info["s22_pd_broke"])):
                s22_agree["approach"] += 1
            else:
                failures.append(
                    f"row {position} day-scale approach "
                    f"{row.day_scale_held}/{row.day_scale_broke} != sweep 22 "
                    f"{info['s22_pd_held']}/{info['s22_pd_broke']}")
        elif str(info["flavour"]) == "L2_ENTRY":
            s22_checked["close"] += 1
            if float(row.day_scale_broke) == float(info["s22_pd_broke_close"]):
                s22_agree["close"] += 1
            else:
                failures.append(
                    f"row {position} day-scale close {row.day_scale_broke} != "
                    f"sweep 22 {info['s22_pd_broke_close']}")
        per_asset[row.asset] = per_asset.get(row.asset, 0) + 1
        per_kind[row.zone_kind] = per_kind.get(row.zone_kind, 0) + 1
        per_flavour[str(info["flavour"])] = per_flavour.get(
            str(info["flavour"]), 0) + 1
        defined_same_day += int(math.isfinite(row.sd_touches))
        defined_prior_session += int(math.isfinite(row.ps_touches))
        defined_day_scale += int(math.isfinite(row.day_scale_persistence))

    # GATE 3: an independent plain-loop recount at the fixed centre.
    rng = np.random.default_rng(int(seed) + 1)
    picks = sorted(int(value) for value in
                   rng.choice(len(queries), size=min(int(hand_rows), len(queries)),
                              replace=False))
    hand: list[dict[str, object]] = []
    hand_mismatches: list[str] = []
    for position in picks:
        query, row = queries[position], out[position]
        today = read._tape(row.asset, int(row.d8))
        slow = hand_recount(today, float(query.zone_price),
                            float(query.band_width), int(query.side),
                            int(query.decision_stamp_ns))
        fast = {"touches": row.sd_touches, "held": row.sd_held,
                "broke": row.sd_broke, "touch_delta": row.sd_touch_delta,
                "mins_since_touch": row.sd_mins_since_touch}
        entry = {"row": position, "asset": row.asset, "d8": int(row.d8),
                 "phase": row.phase, "zone_kind": row.zone_kind,
                 "side": int(row.side), "zone_price": float(query.zone_price),
                 "band_width": float(query.band_width),
                 "decision_stamp_ns": int(query.decision_stamp_ns),
                 "recount": {}, "accessor": {}}
        for name in fast:
            a, b = float(fast[name]), float(slow[name])
            entry["accessor"][name] = None if not math.isfinite(a) else a
            entry["recount"][name] = None if not math.isfinite(b) else b
            same = ((math.isnan(a) and math.isnan(b))
                    or abs(a - b) <= 1e-9 * max(1.0, abs(b)))
            if not same:
                hand_mismatches.append(
                    f"row {position} {row.asset}/{row.d8} {name}: "
                    f"accessor={a} recount={b}")
        if row.ps_served:
            prev = read._tape(row.asset, int(row.ps_sess_d8))
            slow_ps = hand_recount_session(prev, float(query.zone_price),
                                           float(query.band_width),
                                           int(query.side))
            for name, value in (("touches", row.ps_touches),
                                ("held", row.ps_held), ("broke", row.ps_broke)):
                a, b = float(value), float(slow_ps[name])
                entry["accessor"][f"ps_{name}"] = None if not math.isfinite(a) else a
                entry["recount"][f"ps_{name}"] = None if not math.isfinite(b) else b
                same = ((math.isnan(a) and math.isnan(b))
                        or abs(a - b) <= 1e-9 * max(1.0, abs(b)))
                if not same:
                    hand_mismatches.append(
                        f"row {position} {row.asset}/{row.d8} ps_{name}: "
                        f"accessor={a} recount={b}")
        hand.append(entry)

    # The law-identity proof and the unlicensed branch, both on real bytes.
    agreement = cache_agreement(queries, read)
    unlicensed = no_prior_session_rows(read)
    failures.extend(hand_mismatches)
    failures.extend(agreement["problems"][:10])
    failures.extend(unlicensed["problems"])
    order = sorted(gaps)
    return {
        "rows": len(out), "draw": draw,
        "mismatches": failures,
        "gates": {
            "center_exact_rows": centers_exact,
            "center_exact": bool(centers_exact == len(out)),
            "strictly_prior_rows": stamps_strict,
            "strictly_prior": bool(stamps_strict == len(out)),
            "hand_rows": len(hand), "hand_mismatches": len(hand_mismatches),
            "hand_recount_exact": bool(not hand_mismatches),
            "prior_session_rows": ps_rows, "prior_session_clean_rows": ps_clean,
            "prior_session_never_current_day": bool(ps_clean == ps_rows),
            "cache_agreement_rows": int(agreement["counters"]["checked"]),
            "cache_agreement": bool(agreement["agrees"]),
            "no_prior_session_rows": len(unlicensed["rows"]),
            "no_prior_session_clean": bool(unlicensed["clean"])},
        "cache_agreement": agreement, "no_prior_session": unlicensed,
        "worst_gap_ns": int(worst_gap), "worst_gap_row": int(worst_row),
        # The same-day gap is uniformly one lattice step: a decision stamp IS a
        # lattice stamp, so the newest bar that closed before it closed exactly
        # 60 s earlier.  A degenerate distribution is the right answer here and
        # the load-bearing fact is only that it never reaches zero.
        "gap_stats": {
            "max": int(order[-1]) if order else 0,
            "p99": int(order[min(len(order) - 1, int(0.99 * len(order)))]) if order else 0,
            "median": int(order[len(order) // 2]) if order else 0,
            "min": int(order[0]) if order else 0},
        # The prior-session margins are NOT degenerate, and the second one is a
        # real hazard: Sol's note records nine EXPLORE asset-days whose prior
        # EXPLORE session closed AFTER the current session opened.  Where that
        # happens the session-order intuition is wrong and only the explicit
        # "prev last stamp < decision" licence keeps the read causal.
        "prior_session_gap_stats": _span_stats(ps_gaps),
        "prior_session_minus_day_open_stats": _span_stats(ps_overlap),
        "prior_session_closed_after_day_open_rows": int(ps_overlap_rows),
        "coverage": {"by_asset": per_asset, "by_zone_kind": per_kind,
                     "by_flavour": per_flavour,
                     "defined_same_day": defined_same_day,
                     "defined_prior_session": defined_prior_session,
                     "defined_day_scale": defined_day_scale},
        "sweep22_comparability": {"checked": s22_checked, "agree": s22_agree},
        "hand_checks": hand,
        "sample_rows": [out[position].as_dict() for position in picks[:3]],
        "reader_counters": dict(read.counters)}


def main(argv: Sequence[str] | None = None) -> int:
    import argparse
    import hashlib
    import time

    parser = argparse.ArgumentParser(description="fixed-zone memory accessor")
    parser.add_argument("stage", nargs="?", default="verify",
                        choices=("verify",))
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--rows", type=int, default=VERIFY_ROWS)
    parser.add_argument("--hand-rows", type=int, default=HAND_ROWS)
    parser.add_argument("--seed", type=int, default=VERIFY_SEED)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    # A mutant may RUN the audit - that is how the real 596-row gate is shown to
    # be load bearing rather than decorative - but it may never leave a receipt.
    if _mutant() and not args.no_write:
        raise ZoneStop("refusing to write a build report under a mutant; "
                       "rerun the mutant with --no-write")

    started = time.time()
    audit = verify(rows=int(args.rows), hand_rows=int(args.hand_rows),
                   seed=int(args.seed))
    gates = audit["gates"]
    print(f"rows={audit['rows']} "
          f"center_exact={gates['center_exact_rows']}/{audit['rows']} "
          f"strictly_prior={gates['strictly_prior_rows']}/{audit['rows']} "
          f"hand_rows={gates['hand_rows']} "
          f"hand_mismatches={gates['hand_mismatches']} "
          f"mismatches={len(audit['mismatches'])}")
    stats = audit["gap_stats"]
    print(f"worst_source_minus_decision_ns={audit['worst_gap_ns']} "
          f"p99={stats['p99']} median={stats['median']} min={stats['min']}")
    ps_gap = audit["prior_session_gap_stats"]
    ps_open = audit["prior_session_minus_day_open_stats"]
    print(f"prior_session rows={gates['prior_session_rows']} "
          f"clean={gates['prior_session_clean_rows']} "
          f"never_current_day={gates['prior_session_never_current_day']}")
    print(f"prior_session_minus_decision_ns max={ps_gap['max']} "
          f"median={ps_gap['median']} min={ps_gap['min']}")
    print(f"prior_session_minus_day_open_ns max={ps_open['max']} "
          f"median={ps_open['median']} "
          f"rows_closing_after_open="
          f"{audit['prior_session_closed_after_day_open_rows']}")
    print(f"coverage by_asset={audit['coverage']['by_asset']}")
    print(f"coverage by_zone_kind={audit['coverage']['by_zone_kind']}")
    print(f"coverage by_flavour={audit['coverage']['by_flavour']}")
    print(f"defined same_day={audit['coverage']['defined_same_day']} "
          f"prior_session={audit['coverage']['defined_prior_session']} "
          f"day_scale={audit['coverage']['defined_day_scale']} "
          f"of {audit['rows']}")
    print(f"sweep22_comparability={audit['sweep22_comparability']}")
    print(f"cache_agreement rows={gates['cache_agreement_rows']} "
          f"agrees={gates['cache_agreement']} "
          f"counters={audit['cache_agreement']['counters']}")
    print(f"no_prior_session rows={gates['no_prior_session_rows']} "
          f"clean={gates['no_prior_session_clean']}")
    for line in audit["mismatches"][:10]:
        print(f"  {line}")
    print("hand recount, first 6 of "
          f"{len(audit['hand_checks'])} (accessor | plain loop):")
    print(f"  {'asset/day/phase':<22s} {'zone kind':<14s} {'side':>4s} "
          f"{'touches':>16s} {'held':>12s} {'broke':>12s}")
    for entry in audit["hand_checks"][:6]:
        got, want = entry["accessor"], entry["recount"]
        print(f"  {entry['asset']}/{entry['d8']}/{entry['phase']:<9s} "
              f"{entry['zone_kind']:<14s} {entry['side']:>4d} "
              f"{str(got['touches']) + ' | ' + str(want['touches']):>16s} "
              f"{str(got['held']) + ' | ' + str(want['held']):>12s} "
              f"{str(got['broke']) + ' | ' + str(want['broke']):>12s}")
    print("sample rows:")
    for sample in audit["sample_rows"]:
        print("  " + json.dumps(sample, sort_keys=True))

    report = {
        "schema": SCHEMA, "tier": "exploratory",
        "unit": "fixed-zone memory accessor (Sol unit 1)",
        "code_sha256": hashlib.sha256(
            Path(__file__).resolve().read_bytes()).hexdigest(),
        "levels_code_sha256": hashlib.sha256(
            (Path(__file__).resolve().parent / "levels.py").read_bytes()).hexdigest(),
        "build_levels_code_sha256": hashlib.sha256(
            (Path(__file__).resolve().parent / "build_levels.py").read_bytes()
        ).hexdigest(),
        "row_schema": list(ZONE_ROW_FIELDS),
        "query_schema": ["cell", "zone_price", "band_width",
                         "decision_stamp_ns", "side", "zone_kind",
                         "approach_side", "day_scale_mode"],
        "day_scale_turn_kinds": list(DAY_SCALE_TURN_KINDS),
        "day_scale_modes": list(DAY_SCALE_MODES),
        "hold_bands": LV.HOLD_BANDS, "breach_bands": LV.BREACH_BANDS,
        "mutants": list(MUTANTS), "seed": int(args.seed),
        "sources": ["mill_prep", "mill_flow"],
        "cache_written": False,
        "audit": audit,
        "wall_seconds": round(time.time() - started, 2),
        "written_unix": int(time.time())}
    if not args.no_write:
        REPORT_PATH.write_text(
            json.dumps(report, sort_keys=True, indent=1) + "\n")
        print(f"report={REPORT_PATH}")
    ok = (gates["center_exact"] and gates["strictly_prior"]
          and gates["hand_recount_exact"]
          and gates["prior_session_never_current_day"]
          and gates["cache_agreement"] and gates["no_prior_session_clean"])
    print(f"levels_zone_gate={'PASS' if ok else 'REFUSE'}")
    return 0 if ok else 1


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.path.insert(0, str(ROOT))
    raise SystemExit(main())
