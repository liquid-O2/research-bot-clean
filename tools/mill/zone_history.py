#!/usr/bin/env python3
"""The CROSS-DAY ZONE GENEALOGY store: what happened AT THIS BAND, in order.

Unit 2 of Sol's power plan (``.audit/briefs/mill-powerplan-sol-out.md`` section
C rank 2, section D row 2).  Sol's judgment on this information source is
exact:

    "Cross-day zone genealogy.  It preserves the ORDER of defend, weaken,
     breach and role-flip events across licensed EXPLORE sessions.  The current
     accessor reports ONE prior EXPLORE session and AGGREGATES the sequence."

That is the whole gap.  ``levels_zone.read_zone`` answers "what happened at this
price" with five same-day numbers and five prior-session numbers, and the
prior-session family is served by exactly ONE session - ``_prev_explore_d8``
returns the single most recent earlier EXPLORE day - collapsed to counts.  A
band that held four times and then broke twice is indistinguishable, in that
representation, from a band that broke twice and then held four times.  The
first is a level losing its defenders; the second is a level being reclaimed.
Order is the information, and a count cannot carry it.

WHAT THIS MODULE IS.  A store keyed by ``(asset, ATR-scaled price band)``.  For
every EXPLORE session in CAUSAL ORDER it appends the ORDERED events at each
band:

    TOUCH      a sourced bar whose mid lies inside the band
    HELD       that touch resolved UP first, under the levels_zone anchored
               outcome law at the fixed band price: the band acted as SUPPORT
    BROKE      that touch resolved DOWN first: the band acted as RESISTANCE
    ROLE-FLIP  the resolved defence just appended points the OPPOSITE way from
               the last resolved defence at this band - support has become
               resistance, or the reverse

and answers a query ``(asset, zone_price, decision_stamp)`` with the ordered
event history FROM EARLIER EXPLORE SESSIONS ONLY, plus the derived fields the
ranker consumes.

THE OUTCOME LAW IS ``levels_zone``'S, BY CALL GRAPH AND NOT BY RESTATEMENT.
A touch's verdict comes from ``levels.outcome_bars`` - the single definition
``levels_zone.outcome_pair`` itself calls - evaluated at the band's own half
width.  Membership moves to the fixed band; the OUTCOME of a touch stays
anchored on the TOUCHED price, exactly as ``build_levels.day_planes`` and
``levels_zone.same_day_counts`` resolve it.  The store computes at the
REGISTERED READING SIDE ``+1`` and records the DIRECTION; the side ``-1``
reading is the exact mirror (held and broke swap), which the selftest proves
rather than assumes.

THE BAND GRID.  ``band = floor(price / step)``, ``step = 0.40 * atr_ref``, where
``0.40`` is TWICE the levels cache's own default half-width multiplier
``BAND_MULTS[DEFAULT_MULT_INDEX] = 0.20``, so one genealogy band is exactly one
default cache band wide.  ``atr_ref`` is the MEDIAN prior-day ATR14 over the
asset's FIRST ``GRID_WARMUP_DAYS = 25`` EXPLORE sessions - the ranker's own
warmup days, which are never scored, never selected, and never out-of-fold.
The grid is therefore FIXED before the first scored session, uses no outcome
column, and is identical for every session and every query.  A floor grid makes
identity mechanical: the same price on the same day is the same key by
construction, and the band ``[k*step, (k+1)*step)`` contains its own query
price.

STRICT TIME.  A query at ``(d8, stamp)`` is served ONLY by sessions whose own
calendar day is strictly earlier AND whose last bar closed strictly before the
decision stamp.  The second clause is ``levels_zone``'s licensed prior-session
law, generalized from one session to all of them: nine EXPLORE asset-days carry
a prior session that closed after the current session opened, and those are not
served.  HOLD stays sealed - the session list is ``sweep1._explore_days`` and
nothing else.  The eligible set is proved to be a PREFIX (a session excluded by
its own late close is followed only by sessions excluded by day), so the whole
query is a binary search over per-session checkpoints and the derived fields are
O(1) rather than a scan.

THE MUTANTS.
  ``QRE2_MILL_ZH_MUTANT=flip_ignores_order`` counts role flips from the
    UNORDERED totals, ``min(held, broke)``, instead of walking the ordered
    sequence.  It must red the flip counts on the planted three-session fixture
    and the consistency check that ties the derived count to the emitted
    ROLE-FLIP events.
  ``QRE2_MILL_ZH_MUTANT=genealogy_reads_current_day`` serves the CURRENT day's
    own events.  It is armed by ``sweep28``'s own mutant of the same name and
    must red the strict-time gate and the planted current-day check.

Nothing here writes a cache of era bytes, opens a HOLD day, reads a teacher or
late label, or touches an outcome column.  ``levels.py``, ``levels_zone.py``,
``sweep1.py``, ``sweep8.py`` and ``sweep23.py`` are imported READ-ONLY and are
never modified.
"""

from __future__ import annotations

import argparse
import bisect
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

import levels as LV  # noqa: E402
import levels_zone as LZ  # noqa: E402

SCHEMA = "QRE2MILLZONEHISTORY1"
REPORT_PATH = ROOT / ".audit/mill-zone-history-build.json"
ASSETS = ("HG", "NKD", "SI")

# The grid.  0.40 = 2 * BAND_MULTS[DEFAULT_MULT_INDEX]: one genealogy band is
# exactly one default cache band wide, so a band's half width is the cache's own
# default half width and the anchored outcome law runs at the same scale.
BAND_ATR_MULT = 2.0 * LV.BAND_MULTS[LV.DEFAULT_MULT_INDEX]      # 0.40
GRID_WARMUP_DAYS = 25          # asserted equal to sweep 25's MIN_PRIOR_DAYS
READING_SIDE = 1               # the registered side; -1 is its exact mirror

AUDIT_QUERIES = 300
AUDIT_SEED = 20260827

# Event kinds, in the order they may be appended for one touch.
TOUCH = "TOUCH"
HELD = "HELD"
BROKE = "BROKE"
ROLE_FLIP = "ROLE-FLIP"
EVENT_KINDS = (TOUCH, HELD, BROKE, ROLE_FLIP)

# The derived fields a query returns beside the ordered history.  Registered by
# name; sweep 28 consumes exactly these and asserts the roster.
DERIVED_FIELDS = ("generations", "touches", "held", "broke", "held_rate",
                  "broke_rate", "role_flips", "events_since_last_flip",
                  "sessions_since_last_event", "events", "sessions_eligible")

MUTANT_ENV = "QRE2_MILL_ZH_MUTANT"
MUTANT_FLIP_UNORDERED = "flip_ignores_order"
MUTANT_CURRENT_DAY = "genealogy_reads_current_day"
MUTANTS = (MUTANT_FLIP_UNORDERED, MUTANT_CURRENT_DAY)


class HistoryStop(RuntimeError):
    """The genealogy store was asked for the impossible."""


def _mutant() -> str:
    name = os.environ.get(MUTANT_ENV, "")
    if name and name not in MUTANTS:
        raise HistoryStop(f"unknown zone-history mutant: {name}")
    return name


# --------------------------------------------------------------------------
# The band grid.
# --------------------------------------------------------------------------

def band_index(price: float, step: float) -> int:
    """``floor(price / step)``.  One price, one key, at every stamp forever."""

    if not float(step) > 0.0:
        raise HistoryStop(f"band step must be positive, got {step}")
    return int(math.floor(float(price) / float(step)))


def band_edges(index: int, step: float) -> tuple[float, float]:
    """``[lo, hi)`` of a band.  It contains every price that keys to it."""

    return (float(index) * float(step), float(index + 1) * float(step))


def band_center(index: int, step: float) -> float:
    return (float(index) + 0.5) * float(step)


def atr_reference(atr_by_session: Mapping[str, Sequence[float]],
                  warmup: int = GRID_WARMUP_DAYS) -> dict[str, float]:
    """The per-asset grid scale: median prior-day ATR over the WARMUP sessions.

    Those sessions are the ranker's own warmup - never scored, never selected,
    never out-of-fold - so the grid is fixed before the first scored session and
    cannot have been chosen against any outcome it will later be asked about.
    """

    out: dict[str, float] = {}
    for asset in sorted(atr_by_session):
        values = [float(v) for v in atr_by_session[asset][:int(warmup)]
                  if math.isfinite(float(v)) and float(v) > 0.0]
        if not values:
            raise HistoryStop(f"no positive warmup ATR for {asset}")
        out[asset] = float(np.median(np.asarray(values, np.float64)))
    return out


# --------------------------------------------------------------------------
# The events.
# --------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Event:
    """One entry in a band's ordered history."""

    session: int          # index into the asset's EXPLORE session list
    d8: int
    bar: int
    stamp_ns: int         # lattice close of the TOUCH bar
    kind: str
    direction: int        # +1 resolved up, -1 resolved down, 0 unresolved
    verdict_stamp_ns: int  # lattice close of the verdict bar, -1 if unresolved

    def as_dict(self) -> dict[str, object]:
        return {"session": int(self.session), "d8": int(self.d8),
                "bar": int(self.bar), "stamp_ns": int(self.stamp_ns),
                "kind": str(self.kind), "direction": int(self.direction),
                "verdict_stamp_ns": int(self.verdict_stamp_ns)}


@dataclass(slots=True)
class Checkpoint:
    """The cumulative state of one band AFTER one session's events."""

    session: int
    events: int
    touches: int
    held: int
    broke: int
    flips: int
    events_after_last_flip: int   # -1 when no flip has yet occurred
    last_event_session: int


@dataclass(slots=True)
class Band:
    """One band's whole causal history, plus its per-session checkpoints."""

    events: list = field(default_factory=list)
    checkpoints: list = field(default_factory=list)
    last_direction: int = 0       # the last RESOLVED defence's direction
    sessions: int = 0
    touches: int = 0
    held: int = 0
    broke: int = 0
    flips: int = 0
    last_flip: int = -1           # position of the last ROLE-FLIP event
    last_event_session: int = -1


@dataclass(slots=True)
class AssetHistory:
    """One asset's grid, sessions and bands."""

    asset: str
    step: float
    atr_ref: float
    session_d8: list = field(default_factory=list)
    session_last_stamp: list = field(default_factory=list)
    session_first_stamp: list = field(default_factory=list)
    session_bars: list = field(default_factory=list)
    bands: dict = field(default_factory=dict)
    index_by_d8: dict = field(default_factory=dict)


def resolve_direction(hold_bar: int, broke_bar: int, total: int) -> int:
    """The anchored verdict of one touch, as ``levels_zone`` resolves it.

    ``levels.outcome_bars`` returns ``n`` for "never", so a leg at ``total`` did
    not resolve inside the session.  A completed session withholds nothing else:
    ``levels_zone.session_counts`` counts every touch that ever resolved.
    """

    hold = int(hold_bar)
    broke = int(broke_bar)
    if hold < broke and hold < int(total):
        return 1
    if broke < hold and broke < int(total):
        return -1
    return 0


def session_events(tape: LZ.Tape, step: float, session: int,
                   half_width: float | None = None
                   ) -> dict[int, list[tuple[int, int, int]]]:
    """``band -> [(bar, direction, verdict bar)]`` for ONE completed session.

    One ``levels.outcome_bars`` call serves every band: the law anchors on each
    touched price and depends on the half width alone, never on which band the
    touch happens to fall in.  Bars are walked in ascending order, which is
    lattice-close order, so the emitted sequence IS the causal sequence.
    """

    width = float(step) / 2.0 if half_width is None else float(half_width)
    mid = np.asarray(tape.mid, np.float64)
    sourced = np.asarray(tape.sourced, bool)
    total = int(tape.n)
    if total <= 0:
        return {}
    hold_bar, broke_bar = LV.outcome_bars(mid, width, READING_SIDE)
    out: dict[int, list[tuple[int, int, int]]] = {}
    for bar in range(total):
        if not bool(sourced[bar]):
            continue
        key = band_index(float(mid[bar]), float(step))
        direction = resolve_direction(int(hold_bar[bar]), int(broke_bar[bar]),
                                      total)
        verdict = (int(hold_bar[bar]) if direction > 0
                   else int(broke_bar[bar]) if direction < 0 else -1)
        out.setdefault(key, []).append((int(bar), int(direction), int(verdict)))
    return out


def append_session(history: AssetHistory, tape: LZ.Tape, d8: int) -> dict[str, int]:
    """Append ONE session's ordered events to every band it touched.

    Sessions arrive in causal order, so a band's event list is causal, its
    ``session`` column is non-decreasing, and one checkpoint per session records
    the cumulative state the query needs.  The ROLE-FLIP is emitted immediately
    after the resolved defence that caused it, so the ordered history is self
    describing and the derived count is a fact about the list.
    """

    session = len(history.session_d8)
    history.session_d8.append(int(d8))
    history.index_by_d8[int(d8)] = session
    history.session_first_stamp.append(int(tape.ts[0]) if tape.n else -1)
    history.session_last_stamp.append(int(tape.ts[-1]) if tape.n else -1)
    history.session_bars.append(int(tape.n))
    counters = {"touch": 0, "held": 0, "broke": 0, "flip": 0, "unresolved": 0,
                "bands": 0}
    grouped = session_events(tape, history.step, session)
    stamps = np.asarray(tape.ts, np.int64)
    for key in sorted(grouped):
        band = history.bands.get(key)
        if band is None:
            band = history.bands[key] = Band()
        counters["bands"] += 1
        band.sessions += 1
        for bar, direction, verdict in grouped[key]:
            stamp = int(stamps[bar])
            verdict_stamp = int(stamps[verdict]) if verdict >= 0 else -1
            band.events.append(Event(session, int(d8), int(bar), stamp, TOUCH,
                                     0, -1))
            band.touches += 1
            band.last_event_session = int(session)
            counters["touch"] += 1
            if direction == 0:
                counters["unresolved"] += 1
                continue
            kind = HELD if direction > 0 else BROKE
            band.events.append(Event(session, int(d8), int(bar), stamp, kind,
                                     int(direction), verdict_stamp))
            if direction > 0:
                band.held += 1
            else:
                band.broke += 1
            counters["held" if direction > 0 else "broke"] += 1
            flipped = (band.last_direction != 0
                       and int(direction) != int(band.last_direction))
            band.last_direction = int(direction)
            if flipped:
                band.events.append(Event(session, int(d8), int(bar), stamp,
                                         ROLE_FLIP, int(direction),
                                         verdict_stamp))
                band.flips += 1
                band.last_flip = len(band.events) - 1
                counters["flip"] += 1
        _checkpoint(band, session)
    return counters


def _checkpoint(band: Band, session: int) -> None:
    """Snapshot this band's running counters at a session boundary.

    The counters are maintained as the events are appended - a recount at every
    boundary would be quadratic in a band price spends whole sessions inside -
    and ``verify_checkpoints`` recounts each band ONCE at the end of the build
    and refuses if any snapshot disagrees with the events themselves.  Under the
    flip mutant the FLIP COUNT alone is taken from the UNORDERED totals, which
    is the defect being armed.
    """

    flips = (int(min(band.held, band.broke))
             if _mutant() == MUTANT_FLIP_UNORDERED else int(band.flips))
    band.checkpoints.append(Checkpoint(
        session=int(session), events=len(band.events), touches=int(band.touches),
        held=int(band.held), broke=int(band.broke), flips=flips,
        events_after_last_flip=(len(band.events) - 1 - int(band.last_flip)
                                if band.last_flip >= 0 else -1),
        last_event_session=int(band.last_event_session)))


def verify_checkpoints(history: AssetHistory) -> dict[str, int]:
    """Recount every band ONCE and refuse if a snapshot drifted from its events.

    This is what lets the build maintain running counters instead of recounting
    at every session boundary: the cheap path is proved against the honest one
    over the whole store rather than trusted.
    """

    counters = {"bands": 0, "checkpoints": 0, "events": 0, "mismatched": 0}
    for key, band in history.bands.items():
        counters["bands"] += 1
        counters["events"] += len(band.events)
        touches = held = broke = flips = 0
        last_flip = -1
        want: dict[int, tuple[int, int, int, int, int]] = {}
        for position, event in enumerate(band.events):
            if event.kind == TOUCH:
                touches += 1
            elif event.kind == HELD:
                held += 1
            elif event.kind == BROKE:
                broke += 1
            elif event.kind == ROLE_FLIP:
                flips += 1
                last_flip = position
            want[int(event.session)] = (position + 1, touches, held, broke,
                                        flips)
        for checkpoint in band.checkpoints:
            counters["checkpoints"] += 1
            got = want.get(int(checkpoint.session))
            if got is None or (checkpoint.events, checkpoint.touches,
                               checkpoint.held, checkpoint.broke,
                               checkpoint.flips) != got:
                counters["mismatched"] += 1
        if (touches, held, broke, flips) != (band.touches, band.held,
                                             band.broke, band.flips):
            counters["mismatched"] += 1
    if counters["mismatched"]:
        raise HistoryStop(
            f"{counters['mismatched']} checkpoint(s) of {history.asset} "
            f"disagree with the events they summarize")
    return counters


# --------------------------------------------------------------------------
# The query.
# --------------------------------------------------------------------------

def eligible_sessions(history: AssetHistory, d8: int, stamp_ns: int
                      ) -> int:
    """How many leading sessions may lawfully serve this decision.

    A session serves only when its calendar day is strictly earlier AND its last
    bar closed strictly before the decision stamp.  The eligible set is a
    PREFIX: a session excluded by its own late close is followed only by
    sessions of a later day, which are excluded by day.  The prefix is computed
    and then VERIFIED, so a violation refuses instead of silently truncating.
    """

    if _mutant() == MUTANT_CURRENT_DAY:
        # THE DEFECT: the store serves the CURRENT day's own session, whose
        # events include bars that had not closed when the decision was made.
        ok = [int(history.session_d8[i]) <= int(d8)
              for i in range(len(history.session_d8))]
    else:
        ok = [int(history.session_d8[i]) < int(d8)
              and int(history.session_last_stamp[i]) < int(stamp_ns)
              for i in range(len(history.session_d8))]
    cut = 0
    while cut < len(ok) and ok[cut]:
        cut += 1
    if any(ok[cut:]):
        raise HistoryStop(
            f"the eligible session set is not a prefix for {history.asset} at "
            f"{d8}/{stamp_ns}: session {ok.index(True, cut)} qualifies after "
            f"the cut at {cut}")
    return int(cut)


_EMPTY = {"generations": 0, "touches": 0.0, "held": 0.0, "broke": 0.0,
          "held_rate": float("nan"), "broke_rate": float("nan"),
          "role_flips": 0.0, "events_since_last_flip": float("nan"),
          "sessions_since_last_event": float("nan"), "events": (),
          "sessions_eligible": 0}


def query(history: AssetHistory, zone_price: float, d8: int, stamp_ns: int,
          *, want_events: bool = True) -> dict[str, object]:
    """The ordered history of this price's band, from EARLIER sessions only.

    The band key is ``floor(price / step)`` - stamp independent, day independent
    and therefore identical every time the same price is asked for.  The cut is
    a binary search: a band's events are appended session by session, so their
    ``session`` column is non-decreasing and the eligible events are a prefix.
    """

    cut = eligible_sessions(history, int(d8), int(stamp_ns))
    key = band_index(float(zone_price), history.step)
    lo, hi = band_edges(key, history.step)
    out = dict(_EMPTY)
    out["band"] = int(key)
    out["band_lo"] = float(lo)
    out["band_hi"] = float(hi)
    out["band_center"] = float(band_center(key, history.step))
    out["step"] = float(history.step)
    out["sessions_eligible"] = int(cut)
    band = history.bands.get(key)
    if band is None or cut <= 0:
        out["events"] = ()
        return out
    # The last checkpoint strictly inside the eligible prefix.
    sessions = [int(cp.session) for cp in band.checkpoints]
    at = bisect.bisect_left(sessions, int(cut)) - 1
    if at < 0:
        out["events"] = ()
        return out
    cp = band.checkpoints[at]
    # The ranker consumes only the derived fields; materializing the ordered
    # history for all 3,790 candidates would copy millions of event pointers to
    # no purpose.  ``generations`` is the one derived field that needs the list,
    # so it is counted from the checkpoints instead when events are not wanted.
    events = tuple(band.events[:cp.events]) if want_events else ()
    decision_session = len(history.session_d8)
    for position, existing in enumerate(history.session_d8):
        if int(existing) >= int(d8):
            decision_session = position
            break
    out["events"] = events
    out["generations"] = int(len({int(e.session) for e in events})
                             if want_events else (at + 1))
    out["touches"] = float(cp.touches)
    out["held"] = float(cp.held)
    out["broke"] = float(cp.broke)
    out["held_rate"] = (float(cp.held) / float(cp.touches)
                        if cp.touches > 0 else float("nan"))
    out["broke_rate"] = (float(cp.broke) / float(cp.touches)
                         if cp.touches > 0 else float("nan"))
    out["role_flips"] = float(cp.flips)
    out["events_since_last_flip"] = (float(cp.events_after_last_flip)
                                     if cp.events_after_last_flip >= 0
                                     else float("nan"))
    out["sessions_since_last_event"] = (
        float(int(decision_session) - int(cp.last_event_session))
        if cp.last_event_session >= 0 else float("nan"))
    return out


# --------------------------------------------------------------------------
# The build.
# --------------------------------------------------------------------------

def build(assets: Sequence[str] = ASSETS, *, verbose: bool = False
          ) -> tuple[dict[str, AssetHistory], dict[str, object]]:
    """Every EXPLORE session of every asset, in causal order.  No HOLD byte."""

    import build_levels as BL
    import flow as FLOW
    import sweep1 as S1
    import sweep8 as S8

    started = time.time()
    cells, _days, _skipped = S8.build_cells(tuple(assets))
    records, _rec_days = S1.load_cache()
    explore = S1._explore_days(tuple(assets))

    index: dict[tuple[str, int], list[int]] = {}
    for position, rec in enumerate(records):
        index.setdefault((str(rec.asset), int(rec.d8)), []).append(position)
    atr_by_cell: dict[tuple[str, int], list[float]] = {}
    for cell in cells:
        atr_by_cell.setdefault((str(cell.asset), int(cell.d8)), []).append(
            float(cell.atr_mid2))

    atr_by_session: dict[str, list[float]] = {}
    session_days: dict[str, list[int]] = {}
    for asset in assets:
        days = sorted(int(day) for day in explore[str(asset)])
        session_days[str(asset)] = days
        values: list[float] = []
        for d8 in days:
            mine = [v for v in atr_by_cell.get((str(asset), int(d8)), [])
                    if math.isfinite(v) and v > 0.0]
            values.append(float(np.median(np.asarray(mine, np.float64)))
                          if mine else float("nan"))
        atr_by_session[str(asset)] = values
    refs = atr_reference(atr_by_session)

    store: dict[str, AssetHistory] = {}
    counters = {"sessions": 0, "sessions_absent": 0, "touch": 0, "held": 0,
                "broke": 0, "flip": 0, "unresolved": 0, "bands_touched": 0}
    per_asset: dict[str, object] = {}
    for asset in assets:
        step = float(BAND_ATR_MULT) * float(refs[str(asset)])
        history = AssetHistory(asset=str(asset), step=step,
                               atr_ref=float(refs[str(asset)]))
        mine = {"sessions": 0, "sessions_absent": 0, "touch": 0, "held": 0,
                "broke": 0, "flip": 0, "unresolved": 0}
        for d8 in session_days[str(asset)]:
            positions = index.get((str(asset), int(d8)), [])
            tape = None
            if positions:
                try:
                    tape = LZ.tape_from_day(BL.day_tape(
                        records, positions, FLOW.load_flow(str(asset), int(d8)),
                        str(asset), int(d8)))
                except Exception:  # noqa: BLE001 - an absent day is not a crash
                    tape = None
            if tape is None or tape.n <= 0:
                mine["sessions_absent"] += 1
                counters["sessions_absent"] += 1
                # A session with no tape still consumes a session index, so the
                # causal order and the "sessions since" arithmetic stay honest.
                history.session_d8.append(int(d8))
                history.index_by_d8[int(d8)] = len(history.session_d8) - 1
                history.session_first_stamp.append(-1)
                history.session_last_stamp.append(-1)
                history.session_bars.append(0)
                continue
            got = append_session(history, tape, int(d8))
            for name in ("touch", "held", "broke", "flip", "unresolved"):
                mine[name] += int(got[name])
                counters[name] += int(got[name])
            mine["sessions"] += 1
            counters["sessions"] += 1
            if verbose:
                print(f"  {asset} {d8}: {got}")
        # The two build-time proofs.  (1) Session close stamps advance with the
        # calendar, which is what makes the eligible set a PREFIX and therefore
        # the query a binary search rather than a scan.  (2) Every checkpoint
        # agrees with the events it summarizes.
        closes = [int(v) for v in history.session_last_stamp if int(v) >= 0]
        if closes != sorted(closes):
            raise HistoryStop(
                f"{asset}'s session close stamps are not increasing, so the "
                f"eligible session set is not a prefix and the checkpoint "
                f"index is unsound")
        verified = verify_checkpoints(history)
        store[str(asset)] = history
        counters["bands_touched"] += len(history.bands)
        occupancy = sorted((len(b.events) for b in history.bands.values()),
                           reverse=True)
        per_asset[str(asset)] = {
            "sessions": int(mine["sessions"]),
            "sessions_absent": int(mine["sessions_absent"]),
            "atr_ref_mid2": float(history.atr_ref),
            "band_step_mid2": float(history.step),
            "band_half_width_mid2": float(history.step) / 2.0,
            "bands": int(len(history.bands)),
            "events": int(sum(len(b.events) for b in history.bands.values())),
            "touch": int(mine["touch"]), "held": int(mine["held"]),
            "broke": int(mine["broke"]), "flip": int(mine["flip"]),
            "unresolved": int(mine["unresolved"]),
            "bands_with_multiple_sessions": int(sum(
                1 for b in history.bands.values() if b.sessions > 1)),
            "max_events_in_one_band": int(occupancy[0]) if occupancy else 0,
            "median_events_per_band": (float(np.median(
                np.asarray(occupancy, np.float64))) if occupancy else None),
            "session_closes_increasing": True,
            "checkpoints_verified": verified}
    report = {"counters": counters, "per_asset": per_asset,
              "elapsed_s": round(time.time() - started, 1)}
    return store, report


# --------------------------------------------------------------------------
# The three gates, hard-asserted before any cash is read.
# --------------------------------------------------------------------------

def audit(store: Mapping[str, AssetHistory], rows: int = AUDIT_QUERIES,
          seed: int = AUDIT_SEED) -> dict[str, object]:
    """The identity and strict-time gates, over REAL sweep-25 candidates.

    The queries are drawn from sweep 23's formation pass - the same 3,790
    zone-anchored break candidates sweep 25 formed and sweep 27 ranked - so the
    gate runs on the price keys and decision stamps this unit will actually use,
    not on a convenient synthetic sample.
    """

    import sweep1 as S1
    import sweep8 as S8
    import sweep23 as S23

    cells, _days, _skipped = S8.build_cells(ASSETS)
    explore = S1._explore_days(ASSETS)
    cands, formation = S23.formation_pass(cells, explore, "")
    if not formation["strictly_prior"]:
        raise HistoryStop("sweep 23's formation pass is not strictly prior")
    records, _rec_days = S1.load_cache()

    by_stratum: dict[tuple[str, str], list[int]] = {}
    for position, cand in enumerate(cands):
        by_stratum.setdefault((cand.asset, cand.zone_kind), []).append(position)
    strata = sorted(by_stratum)
    per = max(1, int(math.ceil(rows / max(1, len(strata)))))
    rng = np.random.default_rng(int(seed))
    drawn: list[list[int]] = []
    for stratum in strata:
        pool = by_stratum[stratum]
        take = rng.choice(len(pool), size=min(per, len(pool)), replace=False)
        drawn.append([pool[int(offset)] for offset in sorted(take)])
    picks: list[int] = []
    for slot in range(max((len(block) for block in drawn), default=0)):
        for block in drawn:
            if slot < len(block):
                picks.append(block[slot])
    picks = picks[:int(rows)]

    counters = {"queries": 0, "candidates_formed": len(cands),
                "strata": len(strata),
                "identity_contains_price": 0, "identity_price_outside": 0,
                "identity_key_stable": 0, "identity_key_drifted": 0,
                "strict_time_ok": 0, "strict_time_violations": 0,
                "current_day_events": 0, "events_returned": 0,
                "with_any_event": 0, "with_multiple_generations": 0,
                "with_any_flip": 0}
    worst = {"latest_event_stamp_minus_decision_ns": None,
             "max_event_d8_minus_decision_d8": None}
    generations: list[int] = []
    for position in picks:
        cand = cands[position]
        lat = np.asarray(records[int(cand.cell)].lat, np.int64)
        bar = int(cand.bar)
        if bar - 1 < 0:
            continue
        stamp = int(lat[bar - 1])
        history = store[str(cand.asset)]
        got = query(history, float(cand.zone_price), int(cand.d8), stamp)
        counters["queries"] += 1
        # GATE 1a: the returned band CONTAINS the query price.
        inside = (float(got["band_lo"]) <= float(cand.zone_price)
                  < float(got["band_hi"]))
        counters["identity_contains_price" if inside
                 else "identity_price_outside"] += 1
        # GATE 1b: the same price on the same day is the SAME key, at any stamp.
        again = query(history, float(cand.zone_price), int(cand.d8), stamp)
        other = query(history, float(cand.zone_price), int(cand.d8),
                      int(lat[max(0, bar - 2)]))
        stable = (int(again["band"]) == int(got["band"])
                  == int(other["band"])
                  == band_index(float(cand.zone_price), history.step))
        counters["identity_key_stable" if stable
                 else "identity_key_drifted"] += 1
        # GATE 2: strict time, per event.
        bad = 0
        for event in got["events"]:
            counters["events_returned"] += 1
            gap = int(event.stamp_ns) - int(stamp)
            day_gap = int(event.d8) - int(cand.d8)
            if worst["latest_event_stamp_minus_decision_ns"] is None or \
                    gap > int(worst["latest_event_stamp_minus_decision_ns"]):
                worst["latest_event_stamp_minus_decision_ns"] = int(gap)
            if worst["max_event_d8_minus_decision_d8"] is None or \
                    day_gap > int(worst["max_event_d8_minus_decision_d8"]):
                worst["max_event_d8_minus_decision_d8"] = int(day_gap)
            if day_gap >= 0:
                counters["current_day_events"] += 1
                bad += 1
            elif gap >= 0:
                bad += 1
        counters["strict_time_violations" if bad else "strict_time_ok"] += 1
        if got["events"]:
            counters["with_any_event"] += 1
        if int(got["generations"]) > 1:
            counters["with_multiple_generations"] += 1
        if float(got["role_flips"]) > 0.0:
            counters["with_any_flip"] += 1
        generations.append(int(got["generations"]))
    counters["generations_mean"] = (
        float(np.mean(np.asarray(generations, np.float64)))
        if generations else None)
    counters["generations_max"] = int(max(generations)) if generations else 0
    return {"counters": counters, "worst": worst}


def assert_gates(block: Mapping[str, object]) -> None:
    """The refusals.  Nothing downstream may read cash past any of these."""

    counters = block["counters"]                      # type: ignore[index]
    if counters["queries"] <= 0:
        raise HistoryStop("the audit drew no queries")
    if counters["identity_price_outside"]:
        raise HistoryStop(
            f"{counters['identity_price_outside']} of {counters['queries']} "
            f"queries returned a band that does not contain the query price")
    if counters["identity_key_drifted"]:
        raise HistoryStop(
            f"{counters['identity_key_drifted']} of {counters['queries']} "
            f"queries keyed the same price on the same day to two bands")
    if counters["strict_time_violations"] or counters["current_day_events"]:
        raise HistoryStop(
            f"{counters['strict_time_violations']} queries were served an "
            f"event at or after their own decision "
            f"({counters['current_day_events']} of them from the CURRENT day)")


# --------------------------------------------------------------------------
# The planted three-session fixture.  Hand computed, in the docstring.
# --------------------------------------------------------------------------

PLANT_STEP = 20.0                       # half width 10, band 5 = [100, 120)
PLANT_OPEN_NS = LZ.SELFTEST_OPEN_NS
PLANT_DAY_NS = 86_400 * LZ.NANOS_PER_MINUTE


def plant_history() -> tuple[AssetHistory, dict[str, object]]:
    """Three sessions at one band, with ONE role flip, computed by hand.

    ``step = 20`` so the half width is 10 and band 5 is ``[100, 120)``.  Under
    ``levels.outcome_bars`` at side +1 a touch at price ``P`` HOLDS at the first
    later bar ``>= P + 10`` and BREAKS at the first later bar ``< P - 10``.

    SESSION A  d8 20220101  mid [110, 105, 130, 90]
      bar 0  P=110  band floor(110/20)=5.  hold >= 120 at bar 2 (130); broke
             < 100 at bar 3 (90).  2 < 3, so UP -> HELD.
      bar 1  P=105  band 5.  hold >= 115 at bar 2; broke < 95 at bar 3.  HELD.
      bar 2  P=130  band 6.   bar 3  P=90  band 4.
      Band 5 gets TOUCH, HELD, TOUCH, HELD.  No flip: the first resolved
      defence cannot be one, and the second points the same way.

    SESSION B  d8 20220102  mid [110, 95, 130]
      bar 0  P=110  band 5.  hold >= 120 at bar 2 (130); broke < 100 at bar 1
             (95).  1 < 2, so DOWN -> BROKE.  The last resolved defence was
             HELD, so this is the ROLE FLIP: support has become resistance.
      bar 1  P=95  band 4.   bar 2  P=130  band 6.
      Band 5 gets TOUCH, BROKE, ROLE-FLIP.

    SESSION C  d8 20220103  mid [115, 98, 140]
      bar 0  P=115  band 5.  hold >= 125 at bar 2 (140); broke < 105 at bar 1
             (98).  1 < 2, so DOWN -> BROKE.  The last resolved defence was
             also DOWN, so there is NO second flip.
      bar 1  P=98  band 4.   bar 2  P=140  band 7.
      Band 5 gets TOUCH, BROKE.

    THE ORDERED HISTORY AT BAND 5, nine events:
      TOUCH HELD TOUCH HELD | TOUCH BROKE ROLE-FLIP | TOUCH BROKE
    THE DERIVED FIELDS, asked on a fourth day:
      generations 3, touches 4, held 2, broke 2, held rate 0.5, broke rate 0.5,
      role flips 1, events since last flip 2 (the ROLE-FLIP is event 6 of 0..8),
      sessions since last event 1 (session C is index 2, the query is index 3).
    THE MUTANT'S NUMBER: ``min(held, broke) = min(2, 2) = 2``, not 1.  The
    planted order is chosen so the unordered total and the ordered count differ.
    """

    paths = {20220101: [110.0, 105.0, 130.0, 90.0],
             20220102: [110.0, 95.0, 130.0],
             20220103: [115.0, 98.0, 140.0]}
    history = AssetHistory(asset="SI", step=PLANT_STEP, atr_ref=PLANT_STEP
                           / BAND_ATR_MULT)
    for offset, d8 in enumerate(sorted(paths)):
        tape = LZ._fixture_tape("SI", int(d8), paths[d8],
                                PLANT_OPEN_NS + offset * PLANT_DAY_NS)
        append_session(history, tape, int(d8))
    world = {
        "band": 5, "step": PLANT_STEP, "half_width": PLANT_STEP / 2.0,
        "sessions": sorted(paths), "paths": paths,
        "decision_d8": 20220104,
        "decision_stamp_ns": PLANT_OPEN_NS + 3 * PLANT_DAY_NS,
        "order": [TOUCH, HELD, TOUCH, HELD, TOUCH, BROKE, ROLE_FLIP, TOUCH,
                  BROKE],
        "generations": 3, "touches": 4.0, "held": 2.0, "broke": 2.0,
        "held_rate": 0.5, "broke_rate": 0.5, "role_flips": 1.0,
        "events_since_last_flip": 2.0, "sessions_since_last_event": 1.0,
        "unordered_flips": 2.0}
    return history, world


# --------------------------------------------------------------------------
# Selftest.  Synthetic bars only: no cache, no shard, no era byte.
# --------------------------------------------------------------------------

def _check(name: str, ok: bool, detail: str = "") -> tuple[str, bool, str]:
    return (name, bool(ok), detail)


def _selftest_grid() -> list[tuple[str, bool, str]]:
    out = [_check(
        "the band step is TWICE the levels cache's own default half-width "
        "multiplier, so one genealogy band is one default cache band wide",
        BAND_ATR_MULT == 2.0 * LV.BAND_MULTS[LV.DEFAULT_MULT_INDEX]
        and abs(BAND_ATR_MULT - 0.40) < 1e-12,
        f"{BAND_ATR_MULT} = 2 x {LV.BAND_MULTS[LV.DEFAULT_MULT_INDEX]}")]
    step = 20.0
    out.append(_check(
        "the key is floor(price / step): 100, 110 and 119.999 all key to band "
        "5 and 120 opens band 6",
        (band_index(100.0, step) == band_index(110.0, step)
         == band_index(119.999, step) == 5 and band_index(120.0, step) == 6),
        f"{[band_index(p, step) for p in (100.0, 110.0, 119.999, 120.0)]}"))
    out.append(_check(
        "a band CONTAINS every price that keys to it",
        all(band_edges(band_index(p, step), step)[0] <= p
            < band_edges(band_index(p, step), step)[1]
            for p in (0.0, 1.5, 99.9, 100.0, 119.9, 120.0, 4321.7)),
        "checked at seven prices"))
    out.append(_check(
        "the key is STAMP FREE and DAY FREE by construction: it is a pure "
        "function of the price and the asset's fixed step",
        band_index(107.3, step) == band_index(107.3, step) == 5))
    out.append(_check(
        "a negative price still keys inside its own band (floor, not truncate)",
        band_index(-1.0, step) == -1
        and band_edges(-1, step) == (-20.0, 0.0)))
    out.append(_check(
        "the grid scale is the MEDIAN warmup ATR, so one wild session cannot "
        "set it",
        abs(atr_reference({"SI": [10.0] * 24 + [1e6] + [0.5] * 40})["SI"]
            - 10.0) < 1e-12,
        "24 tens, one million, then forties outside the warmup -> 10.0"))
    out.append(_check(
        "the grid warmup equals the ranker's own warmup, so the grid is fixed "
        "before the first scored session",
        GRID_WARMUP_DAYS == 25, f"{GRID_WARMUP_DAYS} sessions"))
    return out


def _selftest_direction() -> list[tuple[str, bool, str]]:
    """The anchored verdict, and the mirror that lets ONE side serve both."""

    out = [_check(
        "an unresolved touch is neither held nor broke: 'never' is the tape "
        "length, not a verdict",
        resolve_direction(4, 4, 4) == 0 and resolve_direction(9, 9, 4) == 0,
        "both legs at or past the sentinel")]
    out.append(_check(
        "the earlier leg wins: hold before breach is UP, breach before hold "
        "is DOWN",
        resolve_direction(2, 3, 9) == 1 and resolve_direction(3, 2, 9) == -1))
    tape = LZ._fixture_tape("SI", 20220101,
                            [110.0, 105.0, 130.0, 90.0], PLANT_OPEN_NS)
    up = LV.outcome_bars(np.asarray(tape.mid, np.float64), 10.0, 1)
    down = LV.outcome_bars(np.asarray(tape.mid, np.float64), 10.0, -1)
    mirrored = all(
        resolve_direction(int(up[0][j]), int(up[1][j]), tape.n)
        == -resolve_direction(int(down[0][j]), int(down[1][j]), tape.n)
        for j in range(tape.n))
    out.append(_check(
        "SIDE -1 IS THE EXACT MIRROR OF SIDE +1, so the store reads ONE side "
        "and records the direction: every bar's verdict simply changes sign",
        mirrored, f"{tape.n} bars checked at half width 10"))
    out.append(_check(
        "the verdict comes from levels.outcome_bars, the one definition "
        "levels_zone itself calls, and not from a restatement of it",
        LZ.outcome_pair.__module__ == "levels_zone"
        and LV.outcome_bars(np.asarray([1.0, 2.0]), 1.0, 1)[0].tolist()
        == LZ.outcome_pair(LZ._fixture_tape("SI", 1, [1.0, 2.0], 0), 1.0,
                           1)[0].tolist(),
        "outcome_pair delegates to levels.outcome_bars"))
    return out


def _selftest_plant(mutant: str) -> list[tuple[str, bool, str]]:
    """The planted three-session world, every number hand computed above."""

    history, world = plant_history()
    got = query(history, 110.0, int(world["decision_d8"]),
                int(world["decision_stamp_ns"]))
    order = [str(e.kind) for e in got["events"]]
    out = [_check(
        "THE PLANTED EVENT ORDER: nine events at band 5 read "
        "TOUCH HELD TOUCH HELD | TOUCH BROKE ROLE-FLIP | TOUCH BROKE",
        order == list(world["order"]),
        f"{order}")]
    out.append(_check(
        "the planted history is keyed to band 5, [100, 120), which contains "
        "the queried price 110",
        int(got["band"]) == int(world["band"])
        and float(got["band_lo"]) == 100.0 and float(got["band_hi"]) == 120.0,
        f"band {got['band']} [{got['band_lo']}, {got['band_hi']})"))
    hand = {"generations": 3, "touches": 4.0, "held": 2.0, "broke": 2.0,
            "held_rate": 0.5, "broke_rate": 0.5}
    bad = [name for name, value in hand.items()
           if abs(float(got[name]) - float(value)) > 1e-12]
    out.append(_check(
        "the hand-computed derived fields are exact: 3 generations, 4 touches, "
        "2 held, 2 broke, held rate 0.5, broke rate 0.5",
        not bad, f"mismatched {bad}; got "
                 f"{ {k: got[k] for k in hand} }"))
    out.append(_check(
        "THE ROLE FLIP IS ORDERED AND THERE IS EXACTLY ONE: support held twice, "
        "then resistance took the band, and the second break is not a second "
        "flip",
        float(got["role_flips"]) == float(world["role_flips"]),
        f"role_flips {got['role_flips']}, wanted {world['role_flips']} "
        f"(the unordered total min(held, broke) would say "
        f"{world['unordered_flips']})"))
    out.append(_check(
        "the derived flip count equals the number of ROLE-FLIP events actually "
        "emitted into the ordered history",
        float(got["role_flips"]) == float(order.count(ROLE_FLIP)),
        f"derived {got['role_flips']}, emitted {order.count(ROLE_FLIP)}"))
    out.append(_check(
        "events since the last flip is 2: the ROLE-FLIP is event 6 of 0..8 and "
        "session C appends two events after it",
        float(got["events_since_last_flip"])
        == float(world["events_since_last_flip"]),
        f"{got['events_since_last_flip']}"))
    out.append(_check(
        "sessions since the last event is 1: session C is index 2 and the "
        "query day is index 3",
        float(got["sessions_since_last_event"])
        == float(world["sessions_since_last_event"]),
        f"{got['sessions_since_last_event']}"))
    # The same band, re-queried: identity.
    again = query(history, 119.5, int(world["decision_d8"]),
                  int(world["decision_stamp_ns"]))
    out.append(_check(
        "A SAME-BAND RE-QUERY IS IDENTICAL: 110 and 119.5 key to the same band "
        "and return the same history and the same derived fields",
        int(again["band"]) == int(got["band"])
        and [str(e.kind) for e in again["events"]] == order
        and all(float(again[name]) == float(got[name])
                for name in ("touches", "held", "broke", "role_flips")),
        f"110 -> {got['band']}, 119.5 -> {again['band']}"))
    lean = query(history, 110.0, int(world["decision_d8"]),
                 int(world["decision_stamp_ns"]), want_events=False)
    out.append(_check(
        "the derived-only query the ranker uses returns EXACTLY the same "
        "numbers as the full one, without materializing the event list",
        not lean["events"]
        and all(str(lean[name]) == str(got[name]) for name in DERIVED_FIELDS
                if name != "events"),
        f"generations {lean['generations']} vs {got['generations']}, flips "
        f"{lean['role_flips']} vs {got['role_flips']}"))
    outside = query(history, 130.0, int(world["decision_d8"]),
                    int(world["decision_stamp_ns"]))
    out.append(_check(
        "a price in the NEXT band gets that band's history and not this one's",
        int(outside["band"]) == 6 and outside["events"] != got["events"],
        f"130 -> band {outside['band']} with "
        f"{len(outside['events'])} events"))
    return out


def _selftest_strict_time(mutant: str) -> list[tuple[str, bool, str]]:
    """A current-day event may never appear, at any stamp, ever."""

    history, world = plant_history()
    # Session C is index 2; ask ON session C, at the close of its FIRST bar -
    # the earliest lawful decision stamp inside it, and the stamp of the very
    # touch a current-day leak would hand back.
    d8 = int(history.session_d8[2])
    stamp = int(history.session_first_stamp[2])
    got = query(history, 110.0, d8, stamp)
    same_day = [e for e in got["events"] if int(e.d8) >= d8]
    out = [_check(
        "A STRICT-TIME CHECK: a query made DURING session C is served only by "
        "sessions A and B, and never by C's own events",
        not same_day and int(got["generations"]) == 2
        and float(got["touches"]) == 3.0,
        f"{len(same_day)} current-day events, generations "
        f"{got['generations']}, touches {got['touches']}")]
    out.append(_check(
        "and the flip that happened in session B is already visible mid-way "
        "through session C, because it is strictly earlier",
        float(got["role_flips"]) == 1.0, f"{got['role_flips']}"))
    late = [e for e in got["events"] if int(e.stamp_ns) >= stamp]
    out.append(_check(
        "every served event's own stamp is strictly before the decision stamp",
        not late, f"{len(late)} events at or after the decision"))
    first = query(history, 110.0, int(history.session_d8[0]),
                  int(history.session_first_stamp[0]))
    out.append(_check(
        "the FIRST session has no genealogy at all: there is nothing earlier "
        "to serve it, and that is an empty history rather than a zero",
        not first["events"] and int(first["generations"]) == 0
        and math.isnan(float(first["held_rate"])),
        f"{len(first['events'])} events, held rate {first['held_rate']}"))
    out.append(_check(
        "an untouched band answers with an empty history and undefined rates, "
        "never a silent zero rate",
        math.isnan(float(query(history, 9999.0, int(world["decision_d8"]),
                               int(world["decision_stamp_ns"]))["held_rate"])),
        "a price nothing ever touched has no rate"))
    return out


def _selftest_prefix() -> list[tuple[str, bool, str]]:
    """The eligibility prefix, and the licence that a late session is not served."""

    history, world = plant_history()
    cuts = [eligible_sessions(history, d8, PLANT_OPEN_NS + i * PLANT_DAY_NS)
            for i, d8 in enumerate(history.session_d8)]
    out = [_check(
        "the eligible session count grows by one per elapsed session",
        cuts == [0, 1, 2], f"{cuts}")]
    # The levels_zone licence: an earlier session that closed AFTER the decision
    # stamp is not served, even though its calendar day is earlier.
    late = AssetHistory(asset="SI", step=PLANT_STEP, atr_ref=1.0)
    append_session(late, LZ._fixture_tape("SI", 20220101, [110.0, 130.0],
                                          PLANT_OPEN_NS), 20220101)
    early_stamp = int(late.session_last_stamp[0]) - 1
    out.append(_check(
        "THE LICENSED PRIOR-SESSION LAW: an earlier session whose last bar "
        "closed at or after the decision stamp is NOT served, exactly as "
        "levels_zone refuses it",
        eligible_sessions(late, 20220102, early_stamp) == 0
        and eligible_sessions(late, 20220102,
                              int(late.session_last_stamp[0]) + 1) == 1,
        f"cut {eligible_sessions(late, 20220102, early_stamp)} at the late "
        f"stamp, 1 once the session has closed"))
    out.append(_check(
        "a checkpoint exists for every session that touched a band, and its "
        "cumulative counts are a recount of the events themselves",
        all(cp.touches == sum(1 for e in band.events[:cp.events]
                              if e.kind == TOUCH)
            for band in history.bands.values() for cp in band.checkpoints),
        f"{sum(len(b.checkpoints) for b in history.bands.values())} "
        f"checkpoints"))
    out.append(_check(
        "a band's session column is non-decreasing, which is what makes the "
        "eligible prefix a binary search rather than a scan",
        all([int(e.session) for e in band.events]
            == sorted(int(e.session) for e in band.events)
            for band in history.bands.values())))
    return out


def _selftest_law_matches_accessor() -> list[tuple[str, bool, str]]:
    """The store's session events must be ``levels_zone``'s own law, re-ordered.

    THE ONE DISCLOSED DIFFERENCE, measured here rather than asserted away.  The
    accessor's band is CLOSED on both edges - ``|mid - centre| <= w`` - so two
    adjacent accessor bands OVERLAP at the price they share, and a bar sitting
    exactly on that price is counted by BOTH.  That is correct for an accessor,
    which answers one named price at a time.  It is impossible for a genealogy
    KEY: a price that keyed to two bands would have two histories and the
    exact-identity gate would mean nothing.  The floor grid is therefore a
    PARTITION, and it differs from the accessor on exactly one set of bars -
    those whose mid equals a band's upper edge, which floor assigns to the band
    above.  This check proves that the difference is exactly that set and
    nothing else, band by band, and that the partition loses no bar.
    """

    out: list[tuple[str, bool, str]] = []
    tape = LZ._fixture_tape(
        "HG", 20220318,
        [500, 300, 100, 105, 130, 100, 88, 121, 103, 96, 300, 104],
        PLANT_OPEN_NS)
    step = 20.0
    half = step / 2.0
    mid = np.asarray(tape.mid, np.float64)
    grouped = session_events(tape, step, 0)
    stamp = int(tape.ts[-1]) + 1
    bad: list[str] = []
    edge_bars = 0
    for key, rows in sorted(grouped.items()):
        centre = band_center(key, step)
        lo, hi = band_edges(key, step)
        mine = {int(bar) for bar, _d, _v in rows}
        # The accessor's own closed band at this centre, bar for bar.
        theirs = {int(j) for j in range(tape.n)
                  if bool(tape.sourced[j]) and abs(float(mid[j]) - centre) <= half}
        on_upper_edge = {int(j) for j in theirs if float(mid[j]) == hi}
        edge_bars += len(on_upper_edge)
        if mine != theirs - on_upper_edge:
            bad.append(f"band {key}: store {sorted(mine)} vs accessor "
                       f"{sorted(theirs)} minus upper edge "
                       f"{sorted(on_upper_edge)}")
            continue
        # On the bars they share, the verdict must be identical - it is the
        # same levels.outcome_bars call in both.
        want = LZ.session_counts(tape, centre, half, READING_SIDE, stamp)
        held = sum(1 for _bar, direction, _v in rows if direction > 0)
        broke = sum(1 for _bar, direction, _v in rows if direction < 0)
        edge_held = edge_broke = 0
        hold_bar, broke_bar = LV.outcome_bars(mid, half, READING_SIDE)
        for j in on_upper_edge:
            direction = resolve_direction(int(hold_bar[j]), int(broke_bar[j]),
                                          tape.n)
            edge_held += int(direction > 0)
            edge_broke += int(direction < 0)
        if (float(want["touches"]) != float(len(mine) + len(on_upper_edge))
                or float(want["held"]) != float(held + edge_held)
                or float(want["broke"]) != float(broke + edge_broke)):
            bad.append(f"band {key}: store {len(mine)}/{held}/{broke} + edge "
                       f"{len(on_upper_edge)}/{edge_held}/{edge_broke} vs "
                       f"accessor {want['touches']}/{want['held']}/"
                       f"{want['broke']}")
    out.append(_check(
        "THE STORE IS THE ACCESSOR'S OWN LAW, RE-ORDERED: at every band the "
        "store's touches, held and broke equal levels_zone.session_counts at "
        "that band's centre and half width, once the bars on the shared upper "
        "edge - which the accessor double counts into both neighbours and the "
        "floor key assigns to exactly one - are put back",
        not bad, "; ".join(bad) if bad else
        f"{len(grouped)} bands agree exactly, {edge_bars} bar(s) on a shared "
        f"edge reassigned by the partition"))
    out.append(_check(
        "THE KEY IS A PARTITION: every sourced bar of the session lands in "
        "exactly one band, so no touch is lost and none is double counted",
        sum(len(rows) for rows in grouped.values())
        == int(np.asarray(tape.sourced, bool).sum()),
        f"{sum(len(rows) for rows in grouped.values())} events over "
        f"{int(np.asarray(tape.sourced, bool).sum())} sourced bars"))
    out.append(_check(
        "the fixture actually EXERCISES the edge case, so this is a measured "
        "difference and not a hypothetical one",
        edge_bars > 0, f"{edge_bars} bar(s) sit exactly on a band edge"))
    mirrored = LZ.session_counts(tape, band_center(5, step), step / 2.0, -1,
                                 int(tape.ts[-1]) + 1)
    straight = LZ.session_counts(tape, band_center(5, step), step / 2.0, 1,
                                 int(tape.ts[-1]) + 1)
    out.append(_check(
        "and the accessor agrees that side -1 swaps held and broke, which is "
        "why one reading side suffices",
        float(mirrored["held"]) == float(straight["broke"])
        and float(mirrored["broke"]) == float(straight["held"]),
        f"+1 {straight['held']}/{straight['broke']} vs -1 "
        f"{mirrored['held']}/{mirrored['broke']}"))
    return out


EXPECTED_RED = {
    MUTANT_FLIP_UNORDERED: (
        "THE ROLE FLIP IS ORDERED AND THERE IS EXACTLY ONE: support held twice, "
        "then resistance took the band, and the second break is not a second "
        "flip",
        "the derived flip count equals the number of ROLE-FLIP events actually "
        "emitted into the ordered history"),
    # MEASURED, not guessed.  Serving the current day moves the eligibility cut
    # by exactly one session everywhere, so every check that pins the cut goes
    # red together - including the first session's emptiness and the licensed
    # prior-session refusal.  All five are time-law checks; the roster is the
    # measured red set, as sweep 27 registers its own.
    MUTANT_CURRENT_DAY: (
        "A STRICT-TIME CHECK: a query made DURING session C is served only by "
        "sessions A and B, and never by C's own events",
        "every served event's own stamp is strictly before the decision stamp",
        "the FIRST session has no genealogy at all: there is nothing earlier "
        "to serve it, and that is an empty history rather than a zero",
        "the eligible session count grows by one per elapsed session",
        "THE LICENSED PRIOR-SESSION LAW: an earlier session whose last bar "
        "closed at or after the decision stamp is NOT served, exactly as "
        "levels_zone refuses it"),
}


def selftest() -> int:
    mutant = _mutant()
    results: list[tuple[str, bool, str]] = []
    results += _selftest_grid()
    results += _selftest_direction()
    results += _selftest_plant(mutant)
    results += _selftest_strict_time(mutant)
    results += _selftest_prefix()
    results += _selftest_law_matches_accessor()
    print(f"zone_history selftest  mutant={mutant or 'none'}")
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
        extra = [name for name in red if name not in set(wanted)]
        print(f"  MUTANT {mutant}: {len(red)} check(s) red, {len(wanted)} "
              f"registered as required")
        for name in red:
            print(f"    red: {name}")
        if survived:
            print("  THE GUARD IS NOT LOAD BEARING: a registered check survived")
            for name in survived:
                print(f"    survived: {name}")
            return 1
        if extra:
            print("  THE MUTANT IS NOT SURGICAL: it reds a check outside its "
                  "registered roster")
            for name in extra:
                print(f"    unregistered red: {name}")
            return 1
        print("  the guard is load bearing and surgical: every registered "
              "check went red and nothing else did")
        return 0
    return 1 if bad else 0


# --------------------------------------------------------------------------
# The build report.
# --------------------------------------------------------------------------

def build_report(store: Mapping[str, AssetHistory],
                 build_block: Mapping[str, object],
                 audit_block: Mapping[str, object]) -> dict[str, object]:
    import sweep1 as S1

    _history, world = plant_history()
    got = query(_history, 110.0, int(world["decision_d8"]),
                int(world["decision_stamp_ns"]))
    return {
        "schema": SCHEMA,
        "code_sha": S1._sha_file(Path(__file__).resolve()),
        "accessor_code_sha": S1._sha_file(Path(LZ.__file__).resolve()),
        "split_sha": S1.split_sha(),
        "seed": AUDIT_SEED,
        "mutant": _mutant(),
        "law": {
            "key": "(asset, floor(price / step)) with step = "
                   f"{BAND_ATR_MULT} * atr_ref",
            "atr_ref": f"the MEDIAN prior-day ATR14 over the asset's first "
                       f"{GRID_WARMUP_DAYS} EXPLORE sessions - the ranker's "
                       f"own warmup, never scored and never out-of-fold - so "
                       f"the grid is fixed before the first scored session",
            "band_mult_note": "0.40 = 2 x BAND_MULTS[DEFAULT_MULT_INDEX], so "
                              "one genealogy band is exactly one default "
                              "levels-cache band wide and the anchored outcome "
                              "law runs at the same half width",
            "events": list(EVENT_KINDS),
            "outcome": "levels.outcome_bars at the band's half width, the one "
                       "definition levels_zone.outcome_pair itself calls; "
                       "membership is at the FIXED band, the verdict stays "
                       "anchored on the TOUCHED price",
            "reading_side": READING_SIDE,
            "mirror": "side -1 is the exact mirror (held and broke swap), "
                      "proved in the selftest, so one reading side records "
                      "both",
            "role_flip": "a resolved defence pointing OPPOSITE to the last "
                         "resolved defence at that band: support has become "
                         "resistance, or the reverse.  The first resolved "
                         "defence at a band is never a flip",
            "strict_time": "a session serves only when its calendar day is "
                           "strictly earlier AND its last bar closed strictly "
                           "before the decision stamp - levels_zone's licensed "
                           "prior-session law, generalized from one session to "
                           "all of them",
            "hold": "SEALED: the session list is sweep1._explore_days and "
                    "nothing else",
            "derived_fields": list(DERIVED_FIELDS)},
        "build": build_block,
        "audit": audit_block,
        "planted_fixture": {
            "world": {k: v for k, v in world.items() if k != "paths"},
            "paths": {str(k): v for k, v in world["paths"].items()},
            "returned_order": [str(e.kind) for e in got["events"]],
            "returned_derived": {name: (None if isinstance(got[name], float)
                                        and not math.isfinite(got[name])
                                        else got[name])
                                 for name in DERIVED_FIELDS
                                 if name != "events"}},
        "mutants": {name: list(EXPECTED_RED[name]) for name in MUTANTS},
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    if not args.build:
        parser.error("choose --selftest or --build")
    store, block = build(verbose=args.verbose)
    audit_block = audit(store)
    assert_gates(audit_block)
    report = build_report(store, block, audit_block)
    print_build(report)
    import sweep8 as S8
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True,
                                      default=S8._json_default) + "\n")
    print(f"\nreport: {REPORT_PATH}")
    return 0


def print_build(report: Mapping[str, object]) -> None:
    law = report["law"]
    print("== THE ZONE GENEALOGY STORE ==")
    for key in ("key", "atr_ref", "band_mult_note", "outcome", "role_flip",
                "strict_time", "hold"):
        print(f"  {key:<16}: {law[key]}")
    print(f"  events          : {law['events']}")
    print(f"  derived fields  : {law['derived_fields']}")
    block = report["build"]
    print(f"\n  build counters  : {block['counters']}")
    print(f"  elapsed         : {block['elapsed_s']} s")
    print("\n  asset  sessions  absent   atr_ref   step   half  bands  "
          "multi-session      events    touch     held    broke  flips  unres")
    for asset in ASSETS:
        cell = block["per_asset"][asset]
        print(f"  {asset:<5} {cell['sessions']:>9} {cell['sessions_absent']:>7} "
              f"{cell['atr_ref_mid2']:>9.1f} {cell['band_step_mid2']:>6.1f} "
              f"{cell['band_half_width_mid2']:>6.1f} {cell['bands']:>6} "
              f"{cell['bands_with_multiple_sessions']:>14} "
              f"{cell['events']:>11} {cell['touch']:>8} {cell['held']:>8} "
              f"{cell['broke']:>8} {cell['flip']:>6} {cell['unresolved']:>6}")
    print("  band occupancy  : " + ", ".join(
        f"{asset} max {block['per_asset'][asset]['max_events_in_one_band']} "
        f"median {block['per_asset'][asset]['median_events_per_band']}"
        for asset in ASSETS))
    audit_block = report["audit"]
    counters = audit_block["counters"]
    print(f"\n== THE GATES, over {counters['queries']} REAL sweep-25 "
          f"candidates ==")
    print(f"  drawn from {counters['candidates_formed']} formed candidates "
          f"over {counters['strata']} (asset, zone kind) strata")
    print(f"  GATE 1a EXACT IDENTITY, the band contains the query price : "
          f"{counters['identity_contains_price']}/{counters['queries']} "
          f"(outside {counters['identity_price_outside']})")
    print(f"  GATE 1b EXACT IDENTITY, the same price on the same day is the "
          f"same key at every stamp : {counters['identity_key_stable']}/"
          f"{counters['queries']} (drifted {counters['identity_key_drifted']})")
    print(f"  GATE 2 STRICT TIME, every event strictly earlier              : "
          f"{counters['strict_time_ok']}/{counters['queries']} "
          f"(violations {counters['strict_time_violations']}, current-day "
          f"events {counters['current_day_events']})")
    print(f"    worst (event stamp - decision stamp) "
          f"{audit_block['worst']['latest_event_stamp_minus_decision_ns']} ns, "
          f"worst (event day - decision day) "
          f"{audit_block['worst']['max_event_d8_minus_decision_d8']}")
    print(f"  events served {counters['events_returned']}, queries with any "
          f"event {counters['with_any_event']}, with more than one generation "
          f"{counters['with_multiple_generations']}, with any role flip "
          f"{counters['with_any_flip']}")
    print(f"  generations per query: mean {counters['generations_mean']}, max "
          f"{counters['generations_max']}")
    plant = report["planted_fixture"]
    print("\n== GATE 3, THE PLANTED THREE-SESSION FIXTURE ==")
    print(f"  ordered history : {' '.join(plant['returned_order'])}")
    print(f"  derived         : {plant['returned_derived']}")
    print(f"  the unordered total min(held, broke) would say "
          f"{plant['world']['unordered_flips']} flips, not "
          f"{plant['world']['role_flips']}; that gap is what the "
          f"{MUTANT_FLIP_UNORDERED} mutant must red")


if __name__ == "__main__":
    raise SystemExit(main())
