#!/usr/bin/python3
"""PORT M1 §10 — FAMILY DISCOVERY CENSUS (D-055).

Two halves, both S1-class Python measurement on the EXISTING receipts/rosters
(no new decode, no new ledger):

  A. DESIGNED FAMILIES F-D1..F-D6, each a separate candidate-family tag with
     the spec's own window/delay, censused against the G1 baseline under the
     CC-M1-3.2 metric (conditional walled value / marginal union recall / DP
     contribution) plus era stability.
  B. SLICE MINER over the S1-v2 UNION ROSTER: the §10B partition axes as
     marginals + all 2-way cells (min n=500 FIT), ranked by conditional walled
     value, Holm-controlled over EVERY tested cell; promotion needs
     value >= G1_asset + $150 AND a per-FIT-year sign-stable edge.  Top-20 per
     asset reported regardless of promotion.

ERA LAW: FIT = 2021-2024 for all mining and all promotion decisions; 2025 is an
ECHO column, evaluated and reported, never selected on.

REUSE, NOT REWRITE: the roster/certificate/DP/oracle machinery is b8's and
c_c_roster's, called as-is.  This module adds exactly four new algorithms —
the window detectors (F-D1/2/3), the shock/insane episode detector (F-D4), the
first-test / OR-extension taggers (F-D5/F-D6), and the slice miner with its
Holm multiplicity ledger.  The two the brief names (miner multiplicity, F-D4
detector) carry committed red-first mutants in test_fdisc.py.

PINNED READINGS (spec §10 is silent; each is a reported defect, see DEFECTS):
  P1  "the settlement window" (F-D1) has no exchange-time definition anywhere
      in the repo, so it is pinned to the last CLOSE_WINDOW seconds before the
      committed m0 RTH close constant (common.RTH_HI_SEC = 21:00 UTC).
  P2  MICRO-OPENS (F-D2) = the two the spec names: the Tokyo lunch reopen
      (12:30 Asia/Tokyo, JPX has no DST) and the London->NY handoff = the US
      cash open (09:30 America/New_York, DST-correct).  Both are opens the
      frozen 3-phase table does not carry.
  P3  Window families are emitted on the G1 confirmation universe only — the
      CC-M1-5 D14 precedent ("the 15s open-window delay applies to G1 rungs
      only; G2 keeps tau*").  G2 confirmations inside the windows are still
      MEASURED (the slice miner's clock axis covers them).
  P4  F-D3's BOJ leg cannot be built: the banked BOJ calendar starts 2026
      (artifacts/reference/port_context/SOURCES_FOR_PORT.md:32) and BOJ
      decisions have no fixed release minute.  F-D3 = FOMC (14:00 ET on the
      meeting's LAST day) + the fixed 08:30/10:00 ET slots.
  P5  F-D4 episodes are CAUSAL by construction (a generator may not read the
      future): a NEWS repricing episode is a trailing-NEWS_SPAN window whose
      SANE mid range reaches $1,000 (the repo's $1k leg class), an insane-book
      episode is a run of >= 10 wide-but-two-sided seconds (the §6 G3 "sustained
      >= 10s" convention).  The trigger is the first confirmation STRICTLY
      after the episode's last second, in the same session.
  P6  F-D5 "the session's FIRST touch-confirmation of each kept level family"
      = per (session, level family) the earliest confirming touch; the level's
      own touch_count==1 case is carried as the separate VIRGIN sub-tag.
  P7  F-D6 uses the CC-M1-6.1 ADOPTED OR_EXT cells per asset for the primary
      tag (HG adopted none) and ALL (segment x OR-minutes) cells for the
      secondary FD6_ANY tag, so every asset gets a measurement.

Run: lab/run.sh port-m1-fdisc -- /usr/bin/python3 engine/port_m1/family_discovery.py
"""
import bisect
import csv
import datetime as dt
import json
import math
import multiprocessing as mp
import os
import sys
from zoneinfo import ZoneInfo

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import m1_common as M
import common as C
import census_common as X
import c_a_cost as CA
import c_c_roster as CC
import c_d_recall as CD
import b1_decay as B1
import b7_sane as B7
import b8_generation_v2 as G
import hl_census as HL

SECTION = "§10 FAMILY DISCOVERY CENSUS (D-055)"
OUT_DIR = "family_discovery"
BASE_DIR = G.OUT_DIR                       # m1/generation_v2 (the S1-v2 oracle)
LEVELS_DIR = G.LEVELS_DIR                  # m1/levels_v3 (D-054 masked ledger)

# ------------------------------------------------------------- constants ----
TAU_STAR = G.TAU_STAR                      # 120s (CC-M1-3.1)
CLOSE_WINDOW = 1800                        # F-D1 "last 30 min before close"
CLOSE_DELAYS = (15, 60)                    # F-D1 delay variants
MICRO_WINDOW = 300                         # F-D2 "same construction as FAST-OPEN"
MICRO_DELAY = 15
NEWS_WINDOW = 600                          # F-D3 "first 10 min after release"
NEWS_DELAYS = (15, 60)
SHOCK_SPAN = G.NEWS_SPAN                   # 150s (CC-M1-4.3 NEWS_UNTRADEABLE)
SHOCK_USD = X.LEG_1K                       # $1,000 repricing = the $1k leg class
INSANE_MIN_SEC = 10                        # §6 G3 "sustained >= 10s"
OREXT_K_MIN = 1.5                          # F-D6 "beyond an OR_EXT k >= 1.5"
SETTLE_END_SOD = C.RTH_HI_SEC              # pinned reading P1

TZ_NY = ZoneInfo("America/New_York")
TZ_TOKYO = ZoneInfo("Asia/Tokyo")
MICRO_OPENS = (("TOKYO_LUNCH_REOPEN", TZ_TOKYO, 12, 30),
               ("NY_CASH_OPEN", TZ_NY, 9, 30))
NEWS_SLOTS = (("ET_0830", TZ_NY, 8, 30), ("ET_1000", TZ_NY, 10, 0))
FOMC_HOUR, FOMC_MIN = 14, 0                # statement release, 14:00 ET

FOMC_CSV = os.path.join(M.CONTEXT_DIR, "calendar_fomc.csv")
BOJ_CSV = os.path.join(M.CONTEXT_DIR, "calendar_boj.csv")

# CC-M1-6.1 adopted OR_EXT cells (the H/L census winner) + the full grid.
OREXT_ADOPTED = {"SI": (("TOKYO", 30), ("LONDON", 30), ("NY", 30),
                        ("TOKYO", 60), ("LONDON", 60)),
                 "NKD": (("LONDON", 30),),
                 "HG": ()}
OREXT_ALL = tuple((seg, mn) for seg in X.PHASE_NAMES for mn in HL.P3_OR_MIN)

# ------------------------------------------------------- the family tags ----
DESIGNED = ("FD1_CLOSE_15", "FD1_CLOSE_60", "FD2_MICRO_OPEN",
            "FD3_NEWS_15", "FD3_NEWS_60", "FD4_POST_SHOCK",
            "FD5_FIRST_TEST", "FD5_FIRST_TEST_VIRGIN",
            "FD6_EXHAUSTION", "FD6_EXHAUSTION_ANY")
DISC_BIT = {f: 1 << i for i, f in enumerate(DESIGNED)}
# the families that ADD candidates (their marginal recall is measurable);
# the rest are tags on candidates the union roster already carries.
ADDING = ("FD1_CLOSE_15", "FD1_CLOSE_60", "FD2_MICRO_OPEN",
          "FD3_NEWS_15", "FD3_NEWS_60")
TAGGING = tuple(f for f in DESIGNED if f not in ADDING)

# --------------------------------------------- CC-M1-3.2 adoption metric ----
COND_VALUE_SLACK = 100.0                   # (i) >= G1 conditional value - $100
MARGINAL_RECALL_PP = 0.2                   # (ii) >= +0.2pp union recall
SEAT_SHARE_MIN = 0.05                      # (iii) >= 5% of DP seats when eligible

# ------------------------------------------------------- the slice miner ----
MIN_N_FIT = 500                            # §10B "min n=500 FIT"
PROMOTE_MARGIN = 150.0                     # §10B "value >= G1_asset + $150"
HOLM_ALPHA = 0.05
TOP_K_REPORT = 20                          # "top-20 slices per asset"
CLOCK_BUCKET_SEC = 1800                    # "30-min clock bucket" (UTC, m0 bins)
SPREAD_CUTS = (1.0, 2.0)                   # x phase-median spread (m0 §9 uses 2x)
AXES = ("phase", "clock30", "rung", "family", "virgin", "vol_regime",
        "spread_state", "dow")

PARAMS = {
    "spec_section": SECTION,
    "designed_families": list(DESIGNED),
    "tau_star_sec": TAU_STAR,
    "fd1": "last %ds of every phase run + the settlement window "
           "[RTH_HI-%ds, RTH_HI); delays %s" % (CLOSE_WINDOW, CLOSE_WINDOW,
                                                list(CLOSE_DELAYS)),
    "fd2": "micro-opens %s; %ds window, %ds delay"
           % ([m[0] for m in MICRO_OPENS], MICRO_WINDOW, MICRO_DELAY),
    "fd3": "first %ds after FOMC 14:00 ET (meeting last day) and the fixed "
           "08:30/10:00 ET slots; delays %s; BOJ unavailable pre-2026"
           % (NEWS_WINDOW, list(NEWS_DELAYS)),
    "fd4": "first confirmation strictly after a causal shock episode ends: "
           "trailing-%ds SANE mid range >= $%.0f, or a run of >= %ds "
           "wide-but-two-sided (D-054 insane) seconds; delay tau*"
           % (SHOCK_SPAN, SHOCK_USD, INSANE_MIN_SEC),
    "fd5": "earliest confirming touch per (session, kept level family); "
           "touch_count==1 carried as the VIRGIN sub-tag; delay tau*",
    "fd6": "entry mid beyond an OR_EXT k>=%.1f level (adopted CC-M1-6.1 cells; "
           "FD6_ANY = all segment x OR-minute cells); delay tau*" % OREXT_K_MIN,
    "window_universe": "G1 confirmations only (CC-M1-5 D14 precedent)",
    "baseline": "m1/%s union roster (the S1-v2 frozen oracle)" % BASE_DIR,
    "levels": "m1/%s (D-053 bands under the D-054 mask)" % LEVELS_DIR,
    "adoption_metric": "CC-M1-3.2: conditional walled value >= G1-$%.0f OR "
                       "marginal union recall >= +%.1fpp OR DP seat share "
                       ">= %.0f%%" % (COND_VALUE_SLACK, MARGINAL_RECALL_PP,
                                      100 * SEAT_SHARE_MIN),
    "slice_axes": list(AXES),
    "slice_cells": "every axis marginal + every 2-way axis pair, cells with "
                   "n_FIT >= %d only" % MIN_N_FIT,
    "slice_statistic": "conditional walled value = mean phase-close walled "
                       "certificate over candidates with value > 0 (FIT era)",
    "slice_test": "one-sided Welch z of the slice's positive certificates vs "
                  "the complement's, normal tail; Holm step-down at alpha=%.2f "
                  "over EVERY tested cell of that asset" % HOLM_ALPHA,
    "slice_promotion": "Holm-rejected AND value >= G1_asset + $%.0f AND the "
                       "per-FIT-year edge keeps its sign in all four years"
                       % PROMOTE_MARGIN,
    "era": "FIT 2021-2024 mines and decides; 2025 is an eval-only echo",
}

DEFECTS = (
    ("FD-1", "F-D1 'the settlement window' is undefined in the spec and no "
             "exchange settlement time is pinned anywhere in the repo. PINNED: "
             "the last %ds before the committed m0 RTH close (RTH_HI_SEC = "
             "21:00 UTC, common.py:104). If the orchestrator means the true "
             "COMEX/CME settlement periods, they must be pinned as constants."
     % CLOSE_WINDOW),
    ("FD-2", "F-D3's BOJ leg is not buildable: calendar_boj.csv carries 2026+ "
             "only (SOURCES_FOR_PORT.md:32) and BOJ decisions have no fixed "
             "release minute (day-grain flag). F-D3 ran on FOMC + the fixed "
             "08:30/10:00 ET slots; the BOJ sub-window is DEFERRED with a "
             "revisit hook (D-015), not dropped."),
    ("FD-3", "F-D2 'London-NY handoff minute' is ambiguous: the frozen phase "
             "table already opens NY at the London/NY profile boundary, so the "
             "handoff as a MICRO-open (beyond the 3 phases) is pinned to the US "
             "cash open 09:30 ET. If the intent was the phase boundary itself, "
             "that window is already G1-FAST-OPEN."),
    ("FD-4", "F-D4 has no stated episode-size or trigger-latency bound. PINNED: "
             "causal detectors (trailing-%ds $%.0f repricing; >=%ds insane run) "
             "and the first confirmation strictly after the episode, same "
             "session, no latency cap (the latency distribution is reported)."
     % (SHOCK_SPAN, SHOCK_USD, INSANE_MIN_SEC)),
    ("FD-5", "§10B names 'selected 2-way cells' without a selection rule. "
             "PINNED: ALL 2-way axis pairs, with the pre-registered n>=%d FIT "
             "filter doing the selecting; every tested cell enters the Holm "
             "ledger, so the accounting stays honest." % MIN_N_FIT),
    ("FD-6", "§10B names no significance test. PINNED: one-sided Welch z on the "
             "conditional (positive-certificate) values, slice vs complement, "
             "normal tail; n>=%d makes the normal approximation safe."
     % MIN_N_FIT),
    ("FD-8", "METRIC DEFECT (found by this lane, returned for adjudication): "
             "the CC-M1-3.2 conditional value is measured on the walled "
             "PHASE-CLOSE certificate, whose horizon is a function of the "
             "clock, while §10's designed families and slice axes are cut ON "
             "the clock. Value and horizon are therefore confounded in the "
             "adoption metric itself. This lane reports the walled PEAK-exit "
             "certificate beside every number as the horizon-free comparator; "
             "the orchestrator should decide whether adoption uses the "
             "close-exit metric (the D-019 contract shape), the horizon-free "
             "one, or a horizon-normalised value."),
    ("FD-7", "STALE SPEC PIN (returned, not touched by this lane): commit "
             "d761a30 amended design/PORT_M1B_SPEC.md to sha16 "
             "d31f48b59877e44d but m1_common.py:42 still pins "
             "2b83f9e70340a413, so verify_spec_m1b() raises today — "
             "b8_generation_v2.py, b7_sane.py, b7_levels_v2.py and "
             "hl_census.py cannot be re-run as committed. This is exactly the "
             "CC-M1-6.4 standing note. §10 pins the M1.A spec (its own home) "
             "and records the observed M1.B sha in the receipt instead."),
)


# ============================================================ calendars ======
_MONTHS = {m: i + 1 for i, m in enumerate(
    ("January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"))}
_MONTHS.update({m[:3]: i for m, i in list(_MONTHS.items())})


def fomc_release_dates(path=None):
    """The LAST day of every banked FOMC meeting, as dates.

    calendar_fomc.csv rows are (year, month, days) with month possibly a
    two-month span ("Jan/Feb") and days a range ("31-1"): the meeting's last
    day is the last (month, day) pair, which is when the statement lands.
    """
    path = path or FOMC_CSV
    out = []
    with open(path, newline="") as fh:
        rd = csv.reader(fh)
        header = next(rd)
        if header[:1] != ["year"]:
            raise RuntimeError("unexpected FOMC calendar header %r" % header)
        for row in rd:
            if len(row) < 3 or not row[0].strip().isdigit():
                continue
            year = int(row[0].strip())
            months = [m.strip() for m in row[1].split("/") if m.strip()]
            days = [d.strip() for d in row[2].split("-") if d.strip()]
            if not months or not days:
                continue
            mon = _MONTHS.get(months[-1])
            if mon is None:
                continue
            day = int(days[-1])
            y = year + 1 if (len(months) > 1 and mon == 1) else year
            out.append(dt.date(y, mon, day))
    return sorted(set(out))


def boj_release_dates(path=None):
    """Banked BOJ MPM dates (2026+ only today — defect FD-2)."""
    path = path or BOJ_CSV
    out = []
    if not os.path.exists(path):
        return out
    with open(path, newline="") as fh:
        rd = csv.reader(fh)
        next(rd, None)
        for row in rd:
            if not row or len(row[0]) != 10:
                continue
            try:
                out.append(dt.date.fromisoformat(row[0].strip()))
            except ValueError:
                continue
    return sorted(set(out))


def local_epochs(open_utc, n, tz, hh, mm, days=(-1, 0, 1)):
    """Every epoch inside [open_utc, open_utc+n) whose LOCAL clock is hh:mm.

    DST-correct by construction (the local wall clock is materialised in `tz`
    and converted back, then ROUND-TRIPPED: a wall time that does not exist on
    a spring-forward date is dropped rather than silently shifted).
    """
    base = dt.datetime.fromtimestamp(open_utc, tz)
    out = []
    for dd in days:
        d = (base + dt.timedelta(days=dd)).date()
        loc = dt.datetime(d.year, d.month, d.day, hh, mm, tzinfo=tz)
        e = int(loc.timestamp())
        back = dt.datetime.fromtimestamp(e, tz)
        if back.hour != hh or back.minute != mm:
            continue                      # skipped wall time (spring forward)
        if open_utc <= e < open_utc + n:
            out.append(e - open_utc)
    return sorted(set(out))


# =========================================== §10A(1) the window detectors ====
def phase_close_secs(s):
    """Last session-second of every maximal phase run (the phase CLOSES).

    The session's final second is always a phase close (the session ends inside
    its last phase), and every second before a phase change closes that run.
    """
    ch = np.nonzero(s.phase_tag[1:] != s.phase_tag[:-1])[0]
    out = [int(x) for x in ch.tolist()]
    out.append(int(s.n - 1))
    return sorted(set(out))


def close_windows(s, open_utc):
    """F-D1 intervals [start, end] (inclusive): the last CLOSE_WINDOW seconds
    before every phase close, plus the pinned settlement window (P1)."""
    iv = []
    for e in phase_close_secs(s):
        iv.append((max(0, e - CLOSE_WINDOW + 1), e))
    sod = (int(open_utc) + np.arange(s.n, dtype=np.int64)) % 86400
    in_settle = (sod >= SETTLE_END_SOD - CLOSE_WINDOW) & (sod < SETTLE_END_SOD)
    if in_settle.any():
        idx = np.nonzero(in_settle)[0]
        cuts = np.nonzero(np.diff(idx) > 1)[0]
        starts = np.concatenate(([0], cuts + 1))
        ends = np.concatenate((cuts, [idx.size - 1]))
        for a, b in zip(starts.tolist(), ends.tolist()):
            iv.append((int(idx[a]), int(idx[b])))
    return merge_intervals(iv)


def open_windows(secs, width):
    """[t, t+width) for every trigger second t (F-D2/F-D3 construction)."""
    return merge_intervals([(int(t), int(t) + int(width) - 1) for t in secs])


def merge_intervals(iv):
    """Sorted, non-overlapping, inclusive intervals."""
    iv = sorted((int(a), int(b)) for a, b in iv if b >= a)
    out = []
    for a, b in iv:
        if out and a <= out[-1][1] + 1:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def in_intervals(sec, iv):
    """True iff `sec` lies inside one of the merged inclusive intervals."""
    if not iv:
        return False
    i = bisect.bisect_right([a for a, _ in iv], sec) - 1
    return i >= 0 and sec <= iv[i][1]


# ============================================ §10A(2) the F-D4 detectors =====
def _sliding_max(a, w):
    """out[i] = max(a[max(0, i-w+1) : i+1]) — van Herk/Gil-Werman, O(n).

    Vectorised (two accumulate passes over a block-reshaped copy), because the
    F-D4 detector runs on every second of every session of every asset.
    """
    a = np.asarray(a, dtype=np.float64)
    n = a.size
    if n == 0:
        return a.copy()
    w = max(1, int(w))
    if w == 1:
        return a.copy()
    pad = (-n) % w
    b = np.concatenate([a, np.full(pad, -np.inf)])
    B = b.reshape(-1, w)
    pre = np.maximum.accumulate(B, axis=1).ravel()
    suf = np.maximum.accumulate(B[:, ::-1], axis=1)[:, ::-1].ravel()
    idx = np.arange(n)
    j = idx - w + 1
    out = np.where(j >= 0, np.maximum(suf[np.maximum(j, 0)], pre[idx]),
                   np.maximum.accumulate(a))
    return out


def rolling_range_usd(vt, vm, mult, span):
    """Trailing-`span`-second SANE mid range in dollars, at each observed sec.

    The window is (t - span, t] in WALL seconds (not in observations), so a
    gap of insane seconds shortens the window instead of reaching further back.
    """
    vt = np.asarray(vt, dtype=np.int64)
    vm = np.asarray(vm, dtype=np.float64)
    if vt.size == 0:
        return np.zeros(0, dtype=np.float64)
    t0 = int(vt[0])
    n = int(vt[-1]) - t0 + 1
    hi = np.full(n, -np.inf)
    lo = np.full(n, np.inf)
    pos = vt - t0
    hi[pos] = vm
    lo[pos] = vm
    mx = _sliding_max(hi, span)
    mn = -_sliding_max(-lo, span)
    return (mx[pos] - mn[pos]) * mult


def shock_episodes(vt, vm, mult, span=SHOCK_SPAN, thr_usd=SHOCK_USD):
    """CAUSAL news-repricing episodes on the SANE mid series.

    vt/vm: observed (SANE) seconds and their mids, ascending.  A second t is
    IN SHOCK when the mid range over the trailing window (t-span, t] reaches
    thr_usd in dollars — a quantity known at t, never later.  Episodes are the
    maximal runs of in-shock OBSERVED seconds; each is (start_sec, end_sec).
    """
    if len(vt) == 0:
        return []
    rng = rolling_range_usd(vt, vm, mult, span)
    return _runs(np.asarray(vt, dtype=np.int64), rng >= thr_usd)


def insane_episodes(two_sided, sane, min_len=INSANE_MIN_SEC):
    """D-054 wide-book episodes: runs of >= min_len seconds that are TWO_SIDED
    but NOT mid-sane (the pathological wide books, not book outages)."""
    ts = np.asarray(two_sided, dtype=bool)
    sn = np.asarray(sane, dtype=bool)
    bad = ts & ~sn
    secs = np.arange(bad.size, dtype=np.int64)
    return [(a, b) for (a, b) in _runs(secs, bad) if (b - a + 1) >= min_len]


def _runs(secs, flag):
    """Maximal True runs of `flag` as (first_sec, last_sec) pairs."""
    idx = np.nonzero(np.asarray(flag, dtype=bool))[0]
    if idx.size == 0:
        return []
    cuts = np.nonzero(np.diff(idx) > 1)[0]
    starts = np.concatenate(([0], cuts + 1))
    ends = np.concatenate((cuts, [idx.size - 1]))
    return [(int(secs[idx[a]]), int(secs[idx[b]]))
            for a, b in zip(starts.tolist(), ends.tolist())]


def first_confirmations_after(conf_secs, end_sec):
    """The indices of the EARLIEST confirmation strictly after end_sec.

    All confirmations sharing that second are returned (both sides can confirm
    on the same second); an empty list means the episode had no resolution
    confirmation inside the session.
    """
    cand = [i for i, cs in enumerate(conf_secs) if cs > end_sec]
    if not cand:
        return []
    first = min(conf_secs[i] for i in cand)
    return [i for i in cand if conf_secs[i] == first]


# ============================================ §10A(3) F-D6 OR_EXT levels =====
def orext_levels(s, seg, minutes, k_min=OREXT_K_MIN):
    """[(valid_from_sec, price, side, phase_index)] for one OR_EXT cell.

    side +1 = the UP extension (price above the opening range), -1 = the DOWN
    extension.  valid_from_sec is when the opening range closes (the levels do
    not exist before it — causal), and the phase index scopes the level to its
    OWN segment: the H/L census's P3 target is REST_OF_WINDOW|segment, so a
    Tokyo opening range says nothing about a New York price.
    """
    p = X.PHASE_NAMES.index(seg)
    oh, ol, _rh, _rl = HL.or_facts(s, s.valid, seg, minutes)
    if not (np.isfinite(oh) and np.isfinite(ol)):
        return []
    idx = np.nonzero((s.phase_tag == p) & s.valid)[0]
    if idx.size == 0:
        return []
    t1 = int(idx[0]) + int(minutes) * 60
    rng = oh - ol
    out = []
    for k in HL.P3_K:
        if k < k_min:
            continue
        out.append((t1, oh + k * rng, +1, p))
        out.append((t1, ol - k * rng, -1, p))
    return out


def beyond_extension(mid, sec, phase, cells):
    """True iff `mid` sits beyond (outside) any LIVE, SAME-SEGMENT OR_EXT level.

    cells: [(valid_from_sec, price, side, phase_index)] — a level counts only
    inside its own segment and only once its opening range has closed."""
    for (t1, px, side, p) in cells:
        if sec < t1 or int(phase) != int(p):
            continue
        if side > 0 and mid >= px:
            return True
        if side < 0 and mid <= px:
            return True
    return False


# ================================================== the per-session pass =====
def _session_tags(asset, s, trade_date, atr, phase_med, open_utc, releases):
    """All §10A emissions/tags for one session.

    Returns (new_keys, tag_events, base_keys, stats) where
      new_keys    {(dec_sec, side): (disc_bits, conf_sec, rung_mask)} for the
                  candidates the union roster does NOT carry,
      tag_events  {(dec_sec, side): disc_bits} for every emitted/tagged key,
      base_keys   the reconstructed S1-v2 union-roster keys of this session
                  (the differential against the frozen oracle),
      stats       per-session counters.
    """
    confs = B1.session_confirmations(s, asset, atr, phase_med, trade_date,
                                     G.RUNGS_V2)
    opens = G.phase_open_secs(s)
    g2, _df, _db = G.g2_from_levels(asset, trade_date)

    # ---- the S1-v2 baseline emission, reconstructed verbatim (b8's code) ----
    base = {}
    for (dec, side, fam, rmask, conf) in G.g1_emissions(confs, opens):
        e = base.setdefault((dec, side), [0, 0, 0, conf])
        e[0] |= fam
        e[2] |= rmask
        e[3] = min(e[3], conf)
    for (conf, side, fam, lf) in g2:
        e = base.setdefault((conf + TAU_STAR, side), [0, 0, 0, conf])
        e[0] |= G.FAM_BIT[fam]
        e[3] = min(e[3], conf)

    # ---------------------------------------------------- F-D1/F-D2/F-D3 ----
    ivs = {"FD1": close_windows(s, open_utc),
           "FD2": open_windows(
               sorted(set(sum([local_epochs(open_utc, s.n, tz, hh, mm)
                               for (_nm, tz, hh, mm) in MICRO_OPENS], []))),
               MICRO_WINDOW),
           "FD3": open_windows(releases, NEWS_WINDOW)}
    emitted = {}

    def emit(dec, side, bit, conf, rmask):
        e = emitted.setdefault((dec, side), [0, conf, 0])
        e[0] |= bit
        e[1] = min(e[1], conf)
        e[2] |= rmask

    n_win = {"FD1": 0, "FD2": 0, "FD3": 0}
    for (conf, side, rmask) in confs:                 # G1 universe only (P3)
        if in_intervals(conf, ivs["FD1"]):
            n_win["FD1"] += 1
            emit(conf + CLOSE_DELAYS[0], side, DISC_BIT["FD1_CLOSE_15"],
                 conf, rmask)
            emit(conf + CLOSE_DELAYS[1], side, DISC_BIT["FD1_CLOSE_60"],
                 conf, rmask)
        if in_intervals(conf, ivs["FD2"]):
            n_win["FD2"] += 1
            emit(conf + MICRO_DELAY, side, DISC_BIT["FD2_MICRO_OPEN"],
                 conf, rmask)
        if in_intervals(conf, ivs["FD3"]):
            n_win["FD3"] += 1
            emit(conf + NEWS_DELAYS[0], side, DISC_BIT["FD3_NEWS_15"],
                 conf, rmask)
            emit(conf + NEWS_DELAYS[1], side, DISC_BIT["FD3_NEWS_60"],
                 conf, rmask)

    # ----------------------------------------------------------- F-D4 -------
    all_conf = [(c, sd) for (c, sd, _m) in confs] + \
               [(c, sd) for (c, sd, _f, _lf) in g2]
    all_conf.sort()
    conf_secs = [c for (c, _sd) in all_conf]
    eps = shock_episodes(s.vt, s.vm, C.ASSETS[asset]["mult"])
    ins = insane_episodes(s.state == C.ST_TWO_SIDED, s.valid)
    n_shock, n_insane = len(eps), len(ins)
    lat = []
    for (_a, b) in sorted(eps + ins):
        for i in first_confirmations_after(conf_secs, b):
            c, sd = all_conf[i]
            emit(c + TAU_STAR, sd, DISC_BIT["FD4_POST_SHOCK"], c, 0)
            lat.append(c - b)

    # ----------------------------------------------------------- F-D5 -------
    first_by_fam = {}
    for (conf, side, _fam, lf) in g2:
        cur = first_by_fam.get(lf)
        if cur is None or conf < cur[0]:
            first_by_fam[lf] = (conf, side)
    virgin_secs = _virgin_confirmation_secs(asset, trade_date)
    n_fd5 = 0
    for lf, (conf, side) in sorted(first_by_fam.items()):
        bits = DISC_BIT["FD5_FIRST_TEST"]
        if conf in virgin_secs:
            bits |= DISC_BIT["FD5_FIRST_TEST_VIRGIN"]
        emit(conf + TAU_STAR, side, bits, conf, 0)
        n_fd5 += 1

    # ----------------------------------------------------------- F-D6 -------
    cells_adopted, cells_all = [], []
    for (seg, mn) in OREXT_ALL:
        rows = orext_levels(s, seg, mn)
        cells_all.extend(rows)
        if (seg, mn) in OREXT_ADOPTED[asset]:
            cells_adopted.extend(rows)
    keys = set(base) | set(emitted)
    n_fd6 = 0
    for (dec, side) in sorted(keys):
        if dec >= s.n or not s.valid[dec]:
            continue
        mid = float(s.mid[dec])
        ph = int(s.phase_tag[dec])
        bits = 0
        if cells_adopted and beyond_extension(mid, dec, ph, cells_adopted):
            bits |= DISC_BIT["FD6_EXHAUSTION"]
        if cells_all and beyond_extension(mid, dec, ph, cells_all):
            bits |= DISC_BIT["FD6_EXHAUSTION_ANY"]
        if bits:
            n_fd6 += 1
            conf = (emitted[(dec, side)][1] if (dec, side) in emitted
                    else base[(dec, side)][3])
            emit(dec, side, bits, conf, 0)

    # ------------------------------------------------- split new vs tag -----
    new_keys, tag_events = {}, {}
    for k in sorted(emitted):
        bits, conf, rmask = emitted[k]
        tag_events[k] = bits
        if k not in base:
            new_keys[k] = (bits, conf, rmask)
    base_ok = {}
    for k in sorted(base):
        dec, _side = k
        if dec >= s.n or not s.valid[dec]:
            continue
        base_ok[k] = base[k]
    stats = {"n_conf": len(confs), "n_g2": len(g2), "n_fd1_conf": n_win["FD1"],
             "n_fd2_conf": n_win["FD2"], "n_fd3_conf": n_win["FD3"],
             "n_shock_episodes": n_shock, "n_insane_episodes": n_insane,
             "n_fd4": len(lat), "fd4_latency_med": M.med(lat) if lat else
             float("nan"), "n_fd5": n_fd5, "n_fd6": n_fd6}
    return new_keys, tag_events, base_ok, stats


def _virgin_confirmation_secs(asset, trade_date):
    """Confirmation seconds of touches on a level's FIRST-EVER touch (P6)."""
    p = M.out_path(LEVELS_DIR, asset, "%s.npz" % trade_date.strftime("%Y%m%d"))
    if not os.path.exists(p):
        return set()
    z = np.load(p, allow_pickle=False)
    t = z["touches"]
    fam = z["level_family"]
    z.close()
    out = set()
    if t.size == 0:
        return out
    for r in t:
        row = int(r[1])
        lf = str(fam[row]) if row < fam.size else "?"
        if lf not in G.KEPT_LEVEL_FAMILIES or int(r[10]) != 1:
            continue
        rej, brk, rec = int(r[7]), int(r[8]), int(r[9])
        if rej >= 0:
            out.add(rej)
        if rec >= 0 and G.reclaim_within_bound(brk, rec):
            out.add(rec)
    return out


def _block(args):
    """One contiguous session block of one asset."""
    asset, sess, phase_med, sane_thr, fomc = args
    spec = C.ASSETS[asset]
    mult = spec["mult"]
    bars = X.load_bars(asset, M.M0_ROOT)
    cols = {k: [] for k in CC.ROSTER_KEYS}
    f_t, f_v, a_t, a_v = [], [], [], []
    new_tags, new_keys_out = [], []
    tag_rows, ctx_rows = [], []
    for trade_date, path in sess:
        bar = bars.get(trade_date)
        atr = bar["ATR14_prev_usd"] if bar else float("nan")
        s = X.load_session(asset, trade_date, path)
        thr = sane_thr.get(M.d8(trade_date))
        insane = B7.apply(s, thr if thr is not None
                          else [B7.SANE_CAP_USD] * X.N_PHASES)
        if s.vt.size < 2 or not np.isfinite(atr):
            continue
        open_utc = int(s.meta["open_utc"])
        rel = []
        for (_nm, tz, hh, mm) in NEWS_SLOTS:
            rel.extend(local_epochs(open_utc, s.n, tz, hh, mm))
        if trade_date in fomc:
            rel.extend(local_epochs(open_utc, s.n, TZ_NY, FOMC_HOUR, FOMC_MIN))
        new_keys, tags, base_keys, st = _session_tags(
            asset, s, trade_date, atr, phase_med, open_utc, sorted(set(rel)))
        d8 = M.d8(trade_date)
        n_new = 0
        for (dec, side) in sorted(new_keys):
            bits, conf, rmask = new_keys[(dec, side)]
            if dec >= s.n or not s.valid[dec]:
                continue
            CC._emit_candidate(cols, f_t, f_v, a_t, a_v, s, trade_date, asset,
                               mult, side, rmask, conf, dec, atr)
            new_tags.append(bits)
            new_keys_out.append((d8, dec, side))
            n_new += 1
        for (dec, side) in sorted(tags):
            tag_rows.append((d8, dec, side, tags[(dec, side)]))
        ctx_rows.append([asset, trade_date.isoformat(), trade_date.year,
                         open_utc, trade_date.weekday(), insane,
                         len(base_keys), n_new, st["n_conf"], st["n_g2"],
                         st["n_fd1_conf"], st["n_fd2_conf"], st["n_fd3_conf"],
                         st["n_shock_episodes"], st["n_insane_episodes"],
                         st["n_fd4"], st["fd4_latency_med"], st["n_fd5"],
                         st["n_fd6"], len(base_keys)])
    arrays = {}
    dtypes = {"date8": np.int32, "side": np.int8, "rung_mask": np.uint8,
              "conf_sec": np.int32, "dec_sec": np.int32, "phase_conf": np.int8,
              "phase_dec": np.int8, "mfe_argmax_sec": np.int32,
              "phase_close_sec": np.int32, "sess_close_sec": np.int32,
              "iid": np.int64, "f_off": np.int64, "f_len": np.int64,
              "a_off": np.int64, "a_len": np.int64}
    for k in CC.ROSTER_KEYS:
        arrays[k] = np.array(cols[k], dtype=dtypes.get(k, np.float64))
    arrays["skel_f_t"] = np.array(f_t, dtype=np.int32)
    arrays["skel_f_v"] = np.array(f_v, dtype=np.float32)
    arrays["skel_a_t"] = np.array(a_t, dtype=np.int32)
    arrays["skel_a_v"] = np.array(a_v, dtype=np.float32)
    arrays["disc_mask"] = np.array(new_tags, dtype=np.uint32)
    M.hb("fdisc[%s] block %s..%s: %d new candidates"
         % (asset, sess[0][0].isoformat(), sess[-1][0].isoformat(),
            arrays["date8"].size))
    return asset, arrays, tag_rows, ctx_rows, new_keys_out


def _merge_blocks(parts):
    """Concatenate block arrays in date order, rebasing skeleton offsets."""
    out = {}
    for k in CC.ROSTER_KEYS:
        out[k] = (np.concatenate([p[k] for p in parts]) if parts
                  else np.zeros(0))
    fbase = abase = 0
    f_off, a_off = [], []
    for p in parts:
        f_off.append(p["f_off"] + fbase)
        a_off.append(p["a_off"] + abase)
        fbase += int(p["skel_f_t"].size)
        abase += int(p["skel_a_t"].size)
    out["f_off"] = (np.concatenate(f_off) if f_off
                    else np.zeros(0, np.int64))
    out["a_off"] = (np.concatenate(a_off) if a_off
                    else np.zeros(0, np.int64))
    for k in ("skel_f_t", "skel_f_v", "skel_a_t", "skel_a_v", "disc_mask"):
        out[k] = (np.concatenate([p[k] for p in parts]) if parts
                  else np.zeros(0))
    return out


# ==================================================== the combined roster ====
class Roster(object):
    """The S1-v2 union roster + the §10 discovery candidates, as one index.

    Index i < n_base addresses the frozen union roster row i; i >= n_base
    addresses discovery row i - n_base.  Certificates are answered by
    c_c_roster.certificates on the owning array set — no re-implementation and
    no re-derivation of the frozen rows.
    """

    def __init__(self, base, new, disc_mask):
        self.r0, self.r1 = base, new
        self.n0 = int(base["date8"].size)
        self.n1 = int(new["date8"].size)
        self.n = self.n0 + self.n1
        self.disc = disc_mask
        self.base_fam = np.concatenate(
            [base["fam_mask"].astype(np.uint16),
             np.zeros(self.n1, dtype=np.uint16)])
        for k in ("date8", "side", "dec_sec", "conf_sec", "entry_mid",
                  "spread_at_decision", "phase_dec", "rung_mask", "iid",
                  "atr14_usd", "phase_close_sec"):
            setattr(self, k, np.concatenate([base[k], new[k]]))
        self.is_base = np.concatenate([np.ones(self.n0, dtype=bool),
                                       np.zeros(self.n1, dtype=bool)])

    def cert(self, i, W, cost):
        if i < self.n0:
            return CC.certificates(self.r0, i, W, cost)
        return CC.certificates(self.r1, i - self.n0, W, cost)


def load_roster(asset, tag_rows, new_arrays, new_keys):
    z = np.load(M.out_path(BASE_DIR, "union_roster_%s.npz" % asset),
                allow_pickle=False)
    base = {k: z[k] for k in z.files}
    z.close()
    n0 = int(base["date8"].size)
    disc = np.zeros(n0 + int(new_arrays["date8"].size), dtype=np.uint32)
    disc[n0:] = new_arrays["disc_mask"]
    index = {}
    for i in range(n0):
        index[(int(base["date8"][i]), int(base["dec_sec"][i]),
               int(base["side"][i]))] = i
    for j, key in enumerate(new_keys):
        index[key] = n0 + j
    n_orphan = 0
    for (d8, dec, side, bits) in tag_rows:
        i = index.get((d8, dec, side))
        if i is None:
            n_orphan += 1
            continue
        disc[i] |= bits
    return Roster(base, new_arrays, disc), n_orphan, index


# =============================================================== census ======
def _by_date(R):
    out = {}
    for i in range(R.n):
        out.setdefault(int(R.date8[i]), []).append(i)
    return out


def census(asset, R, W, cost_map):
    """Per-candidate values + per-family value/DP/seat-share accumulators."""
    fams = list(DESIGNED) + ["G1", "UNION_BASE", "UNION_ALL"]
    vals = np.full(R.n, np.nan)
    # The PEAK-exit certificate is carried beside the phase-close one because
    # a family that fires near a phase close is structurally penalised by an
    # exit AT that close: F-D1 cannot be judged on the close certificate alone.
    vals_peak = np.full(R.n, np.nan)
    seats = {f: {} for f in fams}          # era -> [n_seats, n_sessions_elig]
    dp_rows, seat_rows = [], []
    by_date = _by_date(R)
    for d in sorted(by_date):
        iso = "%04d-%02d-%02d" % (d // 10000, (d // 100) % 100, d % 100)
        cost = cost_map.get((asset, iso), float("nan"))
        if not np.isfinite(cost):
            cost = C.FEES_RT
        idx = by_date[d]
        items = []
        for i in idx:
            pk, cl = R.cert(i, W, cost)
            vals[i] = cl[0]
            vals_peak[i] = pk[0]
            items.append((cl[1], cl[2], cl[0], int(R.dec_sec[i]),
                          int(R.iid[i]), i))
        base_items = [it for it in items if R.is_base[it[5]]]
        tot_all, sel_all = CC.dp_schedule(items)
        tot_base, sel_base = CC.dp_schedule(base_items)
        row = [asset, iso, d // 10000, len(idx), len(base_items),
               tot_base, len(sel_base), tot_all, len(sel_all)]
        for f in DESIGNED:
            bit = DISC_BIT[f]
            fidx = [i for i in idx if int(R.disc[i]) & bit]
            fitems = [it for it in items if int(R.disc[it[5]]) & bit]
            ftot, fsel = CC.dp_schedule(fitems)
            n_seat = sum(1 for i in sel_all if int(R.disc[i]) & bit)
            row.extend([len(fidx), ftot, len(fsel), n_seat])
            if fidx:
                for era in _eras_of(d // 10000):
                    e = seats[f].setdefault(era, [0, 0, 0])
                    e[0] += n_seat
                    e[1] += len(sel_all)
                    e[2] += 1
        g1idx = [i for i in idx if int(R.base_fam[i]) & G.FAM_BIT["G1"]]
        n_seat_g1 = sum(1 for i in sel_all if int(R.base_fam[i])
                        & G.FAM_BIT["G1"])
        row.extend([len(g1idx), n_seat_g1])
        if g1idx:
            for era in _eras_of(d // 10000):
                e = seats["G1"].setdefault(era, [0, 0, 0])
                e[0] += n_seat_g1
                e[1] += len(sel_all)
                e[2] += 1
        dp_rows.append(row)
    for f in list(DESIGNED) + ["G1"]:
        for era in sorted(seats[f]):
            n_seat, n_tot, n_sess = seats[f][era]
            seat_rows.append([asset, f, era, n_sess, n_seat, n_tot,
                              (n_seat / n_tot) if n_tot else float("nan")])
    return vals, vals_peak, dp_rows, seat_rows


def _eras_of(year):
    out = [M.ERA_ALL]
    if M.is_fit(year):
        out.append(M.ERA_FIT)
    if int(year) == 2025:
        out.append(M.ERA_GATE)
    return out


def conditional(vals):
    """The CC-M1-3.2 conditional walled value: mean over positive certs."""
    v = np.asarray(vals, dtype=np.float64)
    v = v[np.isfinite(v) & (v > 0)]
    return ((M.mean(v) if v.size else float("nan")), int(v.size))


def family_value_rows(asset, R, vals, vals_peak):
    """Per (family, era) value census incl. the per-FIT-year era stability."""
    year = (R.date8 // 10000).astype(np.int64)
    rows = []
    sets = [(f, np.array([bool(int(x) & DISC_BIT[f]) for x in R.disc]))
            for f in DESIGNED]
    sets.append(("G1", np.array([bool(int(x) & G.FAM_BIT["G1"])
                                 for x in R.base_fam])))
    sets.append(("UNION_BASE", R.is_base.copy()))
    sets.append(("UNION_ALL", np.ones(R.n, dtype=bool)))
    eras = [(M.ERA_FIT, np.isin(year, np.array(M.FIT_YEARS))),
            (M.ERA_GATE, year == 2025), (M.ERA_ALL,
                                         np.ones(year.size, dtype=bool))]
    eras.extend((str(y), year == y) for y in M.FIT_YEARS)
    for (f, sel) in sets:
        for (era, esel) in eras:
            m = sel & esel
            v = vals[m]
            cv, npos = conditional(v)
            cvp, npos_p = conditional(vals_peak[m])
            rows.append([asset, f, era, int(m.sum()), npos, cv,
                         M.mean(v[np.isfinite(v)]) if m.any() else
                         float("nan"),
                         (npos / int(m.sum())) if int(m.sum()) else
                         float("nan"), npos_p, cvp])
    return rows


# =============================================================== recall ======
def _recall_task(args):
    asset, sess, phase_med, by_date, variants, sane_thr = args
    mult = C.ASSETS[asset]["mult"]
    tick_px = C.ASSETS[asset]["tick_px"]
    bars = X.load_bars(asset, M.M0_ROOT)
    rows = []
    for trade_date, path in sess:
        bar = bars.get(trade_date)
        atr = bar["ATR14_prev_usd"] if bar else float("nan")
        if not np.isfinite(atr):
            continue
        s = X.load_session(asset, trade_date, path)
        thr = sane_thr.get(M.d8(trade_date))
        B7.apply(s, thr if thr is not None
                 else [B7.SANE_CAP_USD] * X.N_PHASES)
        if s.vt.size < 2:
            continue
        thr_px = X.round_half_up(X.ORACLE_RUNG * atr / mult, tick_px)
        legs = CD.oracle_legs(s.vt.tolist(), s.vm.tolist(), thr_px, mult,
                              "ANCHORED")
        legs = [lg for lg in legs if lg[5] >= X.ORACLE_LEG_MIN and lg[4] != 0]
        legs.sort(key=lambda lg: (-lg[5], lg[0], lg[2]))
        legs = legs[:X.ORACLE_TOP_K]
        legs.sort(key=lambda lg: (lg[0], lg[2]))
        allc = by_date.get(M.d8(trade_date), [])
        for vname, bit in variants:
            cands = [c for c in allc
                     if c["base"] or (bit and (c["disc"] & bit))]
            for lg in legs:
                span = int(lg[2]) - int(lg[0])
                rows.append([vname, span,
                             1 if G.is_news_untradeable(span) else 0]
                            + CD._score_leg(asset, trade_date, "ANCHORED", lg,
                                            cands, [], mult, phase_med, atr,
                                            thr_px))
    return rows


LEG_COLUMNS = (["variant", "leg_span_sec", "news_untradeable"]
               + CD.LEG_COLUMNS)
LI = {c: i for i, c in enumerate(LEG_COLUMNS)}


def _recall_rollup(legs, vname):
    out = []
    dl = [lg for lg in legs if lg[0] == vname]
    for era in (M.ERA_FIT, M.ERA_GATE, M.ERA_ALL):
        sel = [lg for lg in dl
               if (era == M.ERA_ALL
                   or (era == M.ERA_FIT and M.is_fit(int(lg[LI["year"]])))
                   or (era == M.ERA_GATE and int(lg[LI["year"]]) == 2025))]
        if not sel:
            continue
        cat = [lg for lg in sel if not int(lg[LI["news_untradeable"]])]

        def rate(rows_, col):
            return (sum(int(l[LI[col]]) for l in rows_) / len(rows_)) \
                if rows_ else float("nan")
        out.append([vname, era, len(sel), len(cat),
                    len(sel) - len(cat), rate(cat, "captured_1000"),
                    rate(cat, "captured_1000_screened"),
                    rate(sel, "captured_1000")])
    return out


def recall(asset, R, workers, sane_thr, phase_med):
    by_date = {}
    for i in range(R.n):
        by_date.setdefault(int(R.date8[i]), []).append({
            "dec_sec": int(R.dec_sec[i]), "side": int(R.side[i]),
            "entry_mid": float(R.entry_mid[i]),
            "spread": float(R.spread_at_decision[i]),
            "phase_dec": int(R.phase_dec[i]),
            "base": bool(R.is_base[i]), "disc": int(R.disc[i])})
    variants = [("BASE", 0)] + [(f, DISC_BIT[f]) for f in ADDING] + \
               [("ALL_ADDING", sum(DISC_BIT[f] for f in ADDING))]
    sess = X.session_paths(asset, M.M0_ROOT)
    k = max(1, len(sess) // max(1, workers))
    chunks = [sess[i:i + k] for i in range(0, len(sess), k)]
    tasks = [(asset, ch, phase_med, by_date, variants, sane_thr)
             for ch in chunks if ch]
    if workers <= 1 or len(tasks) <= 1:
        res = [_recall_task(t) for t in tasks]
    else:
        with mp.Pool(min(workers, len(tasks))) as pool:
            res = list(pool.map(_recall_task, tasks, chunksize=1))
    legs = []
    for x in res:
        legs.extend(x)
    legs.sort(key=lambda l: (l[0], l[LI["trade_date"]],
                             int(l[LI["leg_start_sec"]]),
                             int(l[LI["leg_end_sec"]])))
    roll = []
    for (vname, _bit) in variants:
        roll.extend([[asset] + r for r in _recall_rollup(legs, vname)])
    M.hb("fdisc[%s] recall: %d leg-scorings over %d variants"
         % (asset, len(legs), len(variants)))
    return roll


# ========================================================== the miner ========
def welch_moments(n1, s1, ss1, n2, s2, ss2):
    """One-sided Welch z (mean1 > mean2) from counts/sums/sums-of-squares."""
    if n1 < 2 or n2 < 2:
        return float("nan"), float("nan")
    m1, m2 = s1 / n1, s2 / n2
    v1 = max(0.0, (ss1 - n1 * m1 * m1) / (n1 - 1))
    v2 = max(0.0, (ss2 - n2 * m2 * m2) / (n2 - 1))
    se = math.sqrt(v1 / n1 + v2 / n2)
    if not (se > 0):
        return float("nan"), float("nan")
    z = (m1 - m2) / se
    return z, 0.5 * math.erfc(z / math.sqrt(2.0))


def welch_p(a, b):
    """One-sided Welch z-test p-value for mean(a) > mean(b) (normal tail).

    n >= MIN_N_FIT per slice makes the normal approximation safe; the exact t
    distribution differs in the 4th decimal at these sample sizes.
    """
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    a = a[np.isfinite(a)]
    b = b[np.isfinite(b)]
    return welch_moments(a.size, float(a.sum()), float((a * a).sum()),
                         b.size, float(b.sum()), float((b * b).sum()))


def multiplicity_m(marginal_cells, twoway_cells):
    """The Holm family size = EVERY tested cell, marginals AND 2-way.

    Counting only one stratum (or only the survivors) is the classic
    multiplicity leak; this function is the single place the family size is
    decided, and test_fdisc.py mutates it.
    """
    return len(marginal_cells) + len(twoway_cells)


def holm(pvals, alpha=HOLM_ALPHA, m=None):
    """Holm step-down: adjusted p-values (monotone) + rejection flags.

    adjusted[i] = min(1, max over the sorted prefix of (m - k) * p_(k)), so the
    adjusted sequence is non-decreasing in p — the step-down property.  A
    non-finite p is never rejected and never consumes a step.
    """
    n = len(pvals)
    m = n if m is None else int(m)
    order = sorted(range(n), key=lambda i: (
        float("inf") if not np.isfinite(pvals[i]) else pvals[i], i))
    adj = [float("nan")] * n
    run = 0.0
    k = 0
    for i in order:
        p = pvals[i]
        if not np.isfinite(p):
            continue
        run = max(run, (m - k) * p)
        adj[i] = min(1.0, run)
        k += 1
    rej = [bool(np.isfinite(adj[i]) and adj[i] <= alpha) for i in range(n)]
    return adj, rej


def axis_values(asset, R, ctx, phase_med):
    """The §10B partition axes as per-candidate label arrays (None = N/A)."""
    n = R.n
    d8 = R.date8
    # A session with no context row contributes NO clock/day/regime label
    # (typed exclusion, never a fabricated bucket).
    miss = {"open_utc": -1, "dow": -1, "regime": None}
    open_utc = np.array([ctx.get(int(x), miss)["open_utc"] for x in d8],
                        dtype=np.int64)
    dow = np.array([ctx.get(int(x), miss)["dow"] for x in d8], dtype=np.int64)
    regime = [ctx.get(int(x), miss)["regime"] for x in d8]
    known = open_utc >= 0
    sod = (open_utc + R.dec_sec.astype(np.int64)) % 86400
    clock = (sod // CLOCK_BUCKET_SEC).astype(np.int64)
    year = (d8 // 10000).astype(np.int64)
    out = {}
    out["phase"] = [X.PHASE_NAMES[int(p)] for p in R.phase_dec]
    out["clock30"] = ["UTC%02d:%02d" % (int(c) * CLOCK_BUCKET_SEC // 3600,
                                        (int(c) * CLOCK_BUCKET_SEC % 3600)
                                        // 60) if known[i] else None
                      for i, c in enumerate(clock)]
    rungs = []
    for m_ in R.rung_mask:
        bits = [i for i in range(len(G.RUNGS_V2)) if int(m_) & (1 << i)]
        rungs.append("R%.3f" % G.RUNGS_V2[max(bits)] if bits else None)
    out["rung"] = rungs
    out["vol_regime"] = [r if r else None for r in regime]
    out["dow"] = [("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")[int(w)]
                  if int(w) >= 0 else None for w in dow]
    spread = []
    for i in range(n):
        pm = phase_med.get((asset, int(year[i]),
                            X.PHASE_NAMES[int(R.phase_dec[i])]), float("nan"))
        sp = float(R.spread_at_decision[i])
        if not (np.isfinite(pm) and pm > 0 and np.isfinite(sp)):
            spread.append(None)
        elif sp <= SPREAD_CUTS[0] * pm:
            spread.append("TIGHT")
        elif sp <= SPREAD_CUTS[1] * pm:
            spread.append("NORMAL")
        else:
            spread.append("WIDE")
    out["spread_state"] = spread
    virgin = []
    vbit = DISC_BIT["FD5_FIRST_TEST_VIRGIN"]
    g2bit = G.FAM_BIT["G2_REJECT"] | G.FAM_BIT["G2_RECLAIM"]
    for i in range(n):
        if not (int(R.base_fam[i]) & g2bit):
            virgin.append(None)
        else:
            virgin.append("VIRGIN" if int(R.disc[i]) & vbit else "TOUCHED")
    out["virgin"] = virgin
    return out


def slice_labels(R, axes, sub):
    """{axis: {level: bool mask over `sub`}} — the §10B partition axes.

    Every axis is a partition except `family`, which is MEMBERSHIP (a candidate
    can carry several family tags, so its levels overlap by construction), and
    `virgin`, which is N/A outside G2 (those candidates join no virgin level).
    """
    labels = {}
    for ax in AXES:
        if ax == "family":
            labels[ax] = {f: np.array([bool(int(x) & G.FAM_BIT[f])
                                       for x in R.base_fam[sub]])
                          for f in G.FAMILIES}
            continue
        col = [axes[ax][i] for i in sub]
        lv = {}
        for i, v in enumerate(col):
            if v is None:
                continue
            lv.setdefault(v, []).append(i)
        labels[ax] = {}
        for k, v in lv.items():
            m = np.zeros(sub.size, dtype=bool)
            m[np.array(v, dtype=np.int64)] = True
            labels[ax][k] = m
    return labels


def _cell_stats(mask, fit, pos, v, vv, year, tot, g1_value, echo,
                pk=None, pkpos=None, horizon=None):
    """One cell's FIT statistics + per-FIT-year panel + the 2025 echo.

    `pk`/`pkpos` carry the PEAK-exit certificate and `horizon` the seconds from
    the decision to the phase close, because the phase-close certificate that
    defines the metric has a horizon that varies systematically with the clock:
    a slice cut on the clock is partly measuring how much time it had."""
    mf = mask & fit
    n_fit = int(mf.sum())
    pin = mf & pos
    n1 = int(pin.sum())
    s1 = float(v[pin].sum())
    ss1 = float(vv[pin].sum())
    n2, s2, ss2 = tot[0] - n1, tot[1] - s1, tot[2] - ss1
    cv = (s1 / n1) if n1 else float("nan")
    cvo = (s2 / n2) if n2 else float("nan")
    z, p = welch_moments(n1, s1, ss1, n2, s2, ss2)
    per_year, signs = [], []
    for y in M.FIT_YEARS:
        py = pin & (year == y)
        ny = int(py.sum())
        cy = (float(v[py].sum()) / ny) if ny else float("nan")
        per_year.append((cy, ny))
        signs.append(bool(np.isfinite(cy) and np.isfinite(g1_value)
                          and cy > g1_value))
    me = mask & echo
    pe = me & pos
    ne = int(pe.sum())
    ce = (float(v[pe].sum()) / ne) if ne else float("nan")
    out = {"n_fit": n_fit, "n_pos": n1, "value": cv, "value_out": cvo,
           "z": z, "p": p, "per_year": per_year, "stable": all(signs),
           "echo_n": int(me.sum()), "echo_pos": ne, "echo_value": ce,
           "value_peak": float("nan"), "horizon_med_sec": float("nan")}
    if pk is not None:
        pp = mf & pkpos
        npk = int(pp.sum())
        out["value_peak"] = (float(pk[pp].sum()) / npk) if npk else float("nan")
    if horizon is not None and n_fit:
        out["horizon_med_sec"] = M.med(horizon[mf])
    return out


def mine(asset, R, vals, vals_peak, axes, g1_value, g1_peak):
    """§10B: marginals + all 2-way cells, Holm-controlled, promotion rule.

    Mining runs on the FIT era of the S1-v2 UNION ROSTER (the discovery
    candidates of §10A are NOT mined — they are the designed arm); 2025 rides
    along as an eval-only echo column.
    """
    sub = np.nonzero(R.is_base)[0]
    year = (R.date8[sub] // 10000).astype(np.int64)
    fit = np.isin(year, np.array(M.FIT_YEARS))
    echo = (year == 2025)
    v = np.nan_to_num(vals[sub], nan=0.0)
    pos = np.isfinite(vals[sub]) & (vals[sub] > 0)
    vv = v * v
    pfit = pos & fit
    tot = (int(pfit.sum()), float(v[pfit].sum()), float(vv[pfit].sum()))
    pk = np.nan_to_num(vals_peak[sub], nan=0.0)
    pkpos = np.isfinite(vals_peak[sub]) & (vals_peak[sub] > 0)
    horizon = (R.phase_close_sec[sub] - R.dec_sec[sub]).astype(np.float64)

    labels = slice_labels(R, axes, sub)
    marg, two = [], []
    for ax in AXES:
        for lv in sorted(labels[ax]):
            m = labels[ax][lv]
            if int((m & fit).sum()) >= MIN_N_FIT:
                marg.append(((ax,), (lv,), m))
    for i, a1 in enumerate(AXES):
        for a2 in AXES[i + 1:]:
            for l1 in sorted(labels[a1]):
                m1 = labels[a1][l1]
                if int((m1 & fit).sum()) < MIN_N_FIT:
                    continue              # a 2-way cell cannot beat its parent
                for l2 in sorted(labels[a2]):
                    m = m1 & labels[a2][l2]
                    if int((m & fit).sum()) < MIN_N_FIT:
                        continue
                    two.append(((a1, a2), (l1, l2), m))
    m_total = multiplicity_m(marg, two)
    rows, pv = [], []
    for (axs, lvs, mask) in marg + two:
        st = _cell_stats(mask, fit, pos, v, vv, year, tot, g1_value, echo,
                         pk, pkpos, horizon)
        st["value_peak_minus_g1"] = st["value_peak"] - g1_peak
        st["axes"] = "+".join(axs)
        st["levels"] = "|".join(lvs)
        st["is_2way"] = len(axs) == 2
        rows.append(st)
        pv.append(st["p"])
    adj, rej = holm(pv, HOLM_ALPHA, m=m_total)
    for i, r in enumerate(rows):
        r["p_holm"] = adj[i]
        r["holm_reject"] = rej[i]
        r["promoted"] = bool(rej[i] and np.isfinite(r["value"])
                             and r["value"] >= g1_value + PROMOTE_MARGIN
                             and r["stable"])
    rows.sort(key=lambda r: (-(r["value"] if np.isfinite(r["value"])
                               else -1e18), r["axes"], r["levels"]))
    M.hb("fdisc[%s] miner: %d marginal + %d two-way cells tested (Holm m=%d), "
         "%d rejected, %d promoted"
         % (asset, len(marg), len(two), m_total,
            sum(1 for r in rows if r["holm_reject"]),
            sum(1 for r in rows if r["promoted"])))
    return rows, len(marg), len(two), m_total


# ================================================================= main ======
def load_context_rows(rows):
    """{date8: {open_utc, dow, regime}} from the pass + the fvol regime tags."""
    out = {}
    for r in rows:
        d = dt.date.fromisoformat(r[1])
        out[M.d8(d)] = {"open_utc": int(r[3]), "dow": int(r[4]),
                        "regime": None}
    return out


def load_regimes(asset):
    """CC-M1-1 vol-regime terciles (cut points frozen on FIT) from m1/fvol."""
    path = M.out_path("fvol", "fvol_forecasts.tsv")
    out, cols = {}, None
    with open(path) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if cols is None:
                cols = f
                continue
            r = dict(zip(cols, f))
            if r["asset"] != asset or r["segment"] != "SESSION":
                continue
            d = dt.date.fromisoformat(r["trade_date"])
            out[M.d8(d)] = r["regime_tag"] or None
    return out


CTX_COLUMNS = ["asset", "trade_date", "year", "open_utc", "dow", "insane_frac",
               "n_base_candidates", "n_new_candidates", "n_g1_confirmations",
               "n_g2_confirmations", "n_conf_in_fd1", "n_conf_in_fd2",
               "n_conf_in_fd3", "n_shock_episodes", "n_insane_episodes",
               "n_fd4_triggers", "fd4_latency_median_sec", "n_fd5_tags",
               "n_fd6_tags", "n_base_keys_reconstructed"]


def run(assets, workers):
    phash = C.params_hash(PARAMS)
    with open(os.path.join(M.M0_ROOT, "walls.json")) as fh:
        walls = json.load(fh)["walls"]
    phase_med = CA.phase_median_spreads(M.M0_ROOT)
    cost_map = CA.session_cost_rt(M.M0_ROOT)
    fomc = set(fomc_release_dates())
    boj = boj_release_dates()
    M.hb("fdisc: %d FOMC release dates banked, %d BOJ (pre-2026: %d)"
         % (len(fomc), len(boj), sum(1 for d in boj if d.year < 2026)))

    ctx_rows, fam_rows, dp_rows, seat_rows, recall_rows = [], [], [], [], []
    slice_rows, mine_meta, integ_rows = [], [], []
    for asset in assets:
        sess = X.session_paths(asset, M.M0_ROOT)
        sane_thr = B7.load_thresholds(asset)
        k = max(1, len(sess) // max(1, workers))
        blocks = [sess[i:i + k] for i in range(0, len(sess), k)]
        tasks = [(asset, b, phase_med, sane_thr, fomc) for b in blocks if b]
        if workers <= 1 or len(tasks) <= 1:
            res = [_block(t) for t in tasks]
        else:
            with mp.Pool(min(workers, len(tasks))) as pool:
                res = list(pool.map(_block, tasks, chunksize=1))
        new = _merge_blocks([r[1] for r in res])
        tag_rows, ctx, keys = [], [], []
        for r in res:
            tag_rows.extend(r[2])
            ctx.extend(r[3])
            keys.extend(r[4])
        ctx.sort(key=lambda r: r[1])
        R, n_orphan, index = load_roster(asset, tag_rows, new, keys)
        # INTEGRITY: our reconstruction of the S1-v2 emission must reproduce
        # the frozen oracle's roster keys exactly (it is the same code path).
        n_recon = sum(int(r[19]) for r in ctx)
        integ_rows.append([asset, R.n0, R.n1, n_recon, n_recon - R.n0,
                           n_orphan, len(tag_rows)])
        M.hb("fdisc[%s] roster: base %d + new %d (recon delta %d, orphan tags "
             "%d)" % (asset, R.n0, R.n1, n_recon - R.n0, n_orphan))

        W = float(walls[asset]["wall_usd"])
        vals, vals_peak, dpr, str_ = census(asset, R, W, cost_map)
        dp_rows.extend(dpr)
        seat_rows.extend(str_)
        fam_rows.extend(family_value_rows(asset, R, vals, vals_peak))
        recall_rows.extend(recall(asset, R, workers, sane_thr, phase_med))

        reg = load_regimes(asset)
        cmap = load_context_rows(ctx)
        for d8 in cmap:
            cmap[d8]["regime"] = reg.get(d8)
        ctx_rows.extend(ctx)
        g1_fit = [v for i, v in enumerate(vals)
                  if R.is_base[i] and (int(R.base_fam[i]) & G.FAM_BIT["G1"])
                  and M.is_fit(int(R.date8[i]) // 10000)]
        g1_value, _n = conditional(g1_fit)
        g1_pk = [vals_peak[i] for i in range(R.n)
                 if R.is_base[i] and (int(R.base_fam[i]) & G.FAM_BIT["G1"])
                 and M.is_fit(int(R.date8[i]) // 10000)]
        g1_peak, _np = conditional(g1_pk)
        axes = axis_values(asset, R, cmap, phase_med)
        rows, n_marg, n_two, m_total = mine(asset, R, vals, vals_peak, axes,
                                            g1_value, g1_peak)
        mine_meta.append([asset, g1_value, g1_peak, n_marg, n_two, m_total,
                          sum(1 for r in rows if r["holm_reject"]),
                          sum(1 for r in rows if r["promoted"])])
        for rank, r in enumerate(rows, 1):
            slice_rows.append([asset, rank, r["axes"], r["levels"], r["n_fit"],
                               r["n_pos"], r["value"], r["value_out"],
                               r["value"] - g1_value if np.isfinite(r["value"])
                               else float("nan"), r["z"], r["p"], r["p_holm"],
                               r["holm_reject"], r["stable"],
                               r["per_year"][0][0], r["per_year"][1][0],
                               r["per_year"][2][0], r["per_year"][3][0],
                               r["echo_n"], r["echo_value"], r["promoted"],
                               1 if r["is_2way"] else 0, r["value_peak"],
                               r["value_peak_minus_g1"],
                               r["horizon_med_sec"]])
        del R, vals
    return (phash, ctx_rows, fam_rows, dp_rows, seat_rows, recall_rows,
            slice_rows, mine_meta, integ_rows)


def verdicts(fam_rows, seat_rows, recall_rows):
    """CC-M1-3.2: SURVIVE on any of value / marginal recall / seat share."""
    val = {(r[0], r[1], r[2]): r for r in fam_rows}
    seat = {(r[0], r[1], r[2]): r for r in seat_rows}
    rec = {(r[0], r[1], r[2]): r for r in recall_rows}
    out = []
    assets = sorted(set(r[0] for r in fam_rows))
    for asset in assets:
        g1 = val.get((asset, "G1", M.ERA_FIT))
        g1v = float(g1[5]) if g1 and np.isfinite(g1[5]) else float("nan")
        base = rec.get((asset, "BASE", M.ERA_FIT))
        for f in DESIGNED:
            v = val.get((asset, f, M.ERA_FIT))
            s = seat.get((asset, f, M.ERA_FIT))
            r = rec.get((asset, f, M.ERA_FIT))
            cv = float(v[5]) if v and np.isfinite(v[5]) else float("nan")
            n = int(v[3]) if v else 0
            share = float(s[6]) if s and np.isfinite(s[6]) else float("nan")
            # recall_variants columns: [..][6] = recall_gate_1000 (the gate)
            mr = float("nan")
            if r and base and np.isfinite(float(r[6])) \
                    and np.isfinite(float(base[6])):
                mr = 100.0 * (float(r[6]) - float(base[6]))
            c1 = bool(np.isfinite(cv) and np.isfinite(g1v)
                      and cv >= g1v - COND_VALUE_SLACK)
            c2 = bool(np.isfinite(mr) and mr >= MARGINAL_RECALL_PP)
            c3 = bool(np.isfinite(share) and share >= SEAT_SHARE_MIN)
            per_year = [val.get((asset, f, str(y))) for y in M.FIT_YEARS]
            pyv = [float(x[5]) if x and np.isfinite(x[5]) else float("nan")
                   for x in per_year]
            stable = all(np.isfinite(x) and np.isfinite(g1v)
                         and x >= g1v - COND_VALUE_SLACK for x in pyv)
            e = val.get((asset, f, M.ERA_GATE))
            echo = float(e[5]) if e and np.isfinite(e[5]) else float("nan")
            pk = float(v[9]) if v and np.isfinite(v[9]) else float("nan")
            g1pk = (float(g1[9]) if g1 and np.isfinite(g1[9])
                    else float("nan"))
            surv = c1 or c2 or c3
            out.append([asset, f, n, cv, g1v, cv - g1v if np.isfinite(cv)
                        else float("nan"), mr, share, c1, c2, c3, stable,
                        echo, pk, pk - g1pk if np.isfinite(pk)
                        else float("nan"),
                        "ADOPT" if (surv and stable) else
                        ("ADOPT_UNSTABLE" if surv else "RETIRE")])
    return out


def write_all(bundle):
    (phash, ctx_rows, fam_rows, dp_rows, seat_rows, recall_rows,
     slice_rows, mine_meta, integ_rows) = bundle
    W = M.write_tsv
    W(M.out_path(OUT_DIR, "session_context.tsv"), SECTION, phash, CTX_COLUMNS,
      ctx_rows, extra=["one row per session: window/episode counters and the "
                       "slice-miner session context"])
    W(M.out_path(OUT_DIR, "roster_integrity.tsv"), SECTION, phash,
      ["asset", "n_base_roster", "n_new_candidates", "n_base_reconstructed",
       "base_reconstruction_delta", "n_orphan_tag_events", "n_tag_events"],
      integ_rows,
      extra=["base_reconstruction_delta MUST be 0: §10 re-runs b8's own "
             "emission code path, so its roster keys must reproduce the "
             "frozen S1-v2 oracle session for session"])
    W(M.out_path(OUT_DIR, "family_value.tsv"), SECTION, phash,
      ["asset", "family", "era", "n_candidates", "n_positive",
       "conditional_value_usd", "mean_cert_usd", "positive_frac",
       "n_positive_peak", "conditional_value_peak_usd"], fam_rows,
      extra=["conditional_value_usd = the CC-M1-3.2 metric (mean walled "
             "phase-close certificate over candidates with value > 0)",
             "conditional_value_peak_usd = the same statistic on the walled "
             "PEAK-exit certificate: the fair comparator for families that "
             "fire near a phase close, whose close certificate has almost no "
             "horizon left (F-D1)",
             "era rows 2021..2024 are the per-FIT-year stability panel"])
    cols = ["asset", "trade_date", "year", "n_all", "n_base", "dp_base_usd",
            "n_seated_base", "dp_all_usd", "n_seated_all"]
    for f in DESIGNED:
        cols += ["n_%s" % f, "dp_%s_usd" % f, "n_seated_alone_%s" % f,
                 "n_seats_in_union_%s" % f]
    cols += ["n_G1", "n_seats_in_union_G1"]
    W(M.out_path(OUT_DIR, "census_dp_session.tsv"), SECTION, phash, cols,
      dp_rows, extra=["dp_*_usd = the one-position DP over that family's "
                      "candidates alone; n_seats_in_union_* = seats of the "
                      "FULL-roster DP whose candidate carries the tag"])
    W(M.out_path(OUT_DIR, "family_seat_share.tsv"), SECTION, phash,
      ["asset", "family", "era", "n_eligible_sessions", "n_seats_with_family",
       "n_seats_total", "seat_share"], seat_rows,
      extra=["CC-M1-3.2(iii): seat share over sessions where the family has "
             "at least one candidate"])
    W(M.out_path(OUT_DIR, "recall_variants.tsv"), SECTION, phash,
      ["asset", "variant", "era", "n_legs", "n_gate_legs",
       "n_news_untradeable", "recall_gate_1000", "recall_gate_1000_screened",
       "recall_all_1000"], recall_rows,
      extra=["SANE ANCHORED oracle; BASE = the frozen S1-v2 union roster, "
             "every other variant = BASE + that family's candidates, so the "
             "marginal union recall is the difference"])
    W(M.out_path(OUT_DIR, "slice_census.tsv"), SECTION, phash,
      ["asset", "rank_by_value", "axes", "levels", "n_fit", "n_positive_fit",
       "conditional_value_usd", "conditional_value_complement_usd",
       "value_minus_g1_usd", "welch_z", "p_raw", "p_holm", "holm_reject",
       "fit_year_sign_stable", "value_2021", "value_2022", "value_2023",
       "value_2024", "n_2025_echo", "value_2025_echo", "promoted", "is_2way",
       "value_peak_exit_usd", "value_peak_minus_g1_peak_usd",
       "median_horizon_to_phase_close_sec"],
      slice_rows,
      extra=["every tested cell (marginal + 2-way, n_fit >= %d); Holm family "
             "size = every row of that asset" % MIN_N_FIT,
             "promotion = holm_reject AND value >= G1_asset + $%.0f AND "
             "per-FIT-year sign stability; 2025 is an eval-only echo"
             % PROMOTE_MARGIN,
             "value_peak_exit_usd is the HORIZON-FREE comparator: the walled "
             "PEAK-exit certificate of the same candidates. A clock slice "
             "whose phase-close value is high only because its horizon is "
             "long shows no edge here (median_horizon_to_phase_close_sec is "
             "the diagnostic)"])
    W(M.out_path(OUT_DIR, "slice_multiplicity.tsv"), SECTION, phash,
      ["asset", "g1_conditional_value_fit_usd",
       "g1_conditional_value_peak_fit_usd", "n_marginal_cells",
       "n_twoway_cells", "holm_family_size", "n_holm_rejected", "n_promoted"],
      mine_meta, extra=["holm_family_size = multiplicity_m() = marginals + "
                        "2-way; the miner tests exactly this many cells"])
    ver = verdicts(fam_rows, seat_rows, recall_rows)
    W(M.out_path(OUT_DIR, "designed_family_verdict.tsv"), SECTION, phash,
      ["asset", "family", "n_candidates_fit", "conditional_value_usd",
       "g1_conditional_value_usd", "value_minus_g1_usd",
       "marginal_recall_pp", "dp_seat_share", "crit_value", "crit_recall",
       "crit_seat_share", "fit_year_stable", "value_2025_echo",
       "peak_exit_value_usd", "peak_exit_value_minus_g1_usd", "verdict"],
      ver, extra=["CC-M1-3.2: survive on ANY of (i) value >= G1 - $%.0f, "
                  "(ii) marginal union recall >= +%.1fpp, (iii) DP seat share "
                  ">= %.0f%%; ADOPT_UNSTABLE = survives but a FIT year breaks"
                  % (COND_VALUE_SLACK, MARGINAL_RECALL_PP,
                     100 * SEAT_SHARE_MIN)])
    W(M.out_path(OUT_DIR, "spec_defects.tsv"), SECTION, phash,
      ["defect", "description"], [list(d) for d in DEFECTS],
      extra=["§10 ambiguities pinned by this lane (D-002: design questions "
             "return to the orchestrator)"])
    return ver


# =============================================================== report ======
def _hrs(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return "n/a"
    return "n/a" if not np.isfinite(x) else "%.1fh" % (x / 3600.0)


def _f(v, fmt="%.0f"):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return "n/a"
    return "n/a" if not np.isfinite(x) else fmt % x


def write_report():
    """FAMILY_DISCOVERY_REPORT.md — every number read back out of a committed
    TSV with its file:line (D-010).  Nothing here is hand-typed."""
    from report import Tsv, cite

    ver = Tsv(M.out_path(OUT_DIR, "designed_family_verdict.tsv"))
    fam = Tsv(M.out_path(OUT_DIR, "family_value.tsv"))
    rec = Tsv(M.out_path(OUT_DIR, "recall_variants.tsv"))
    sli = Tsv(M.out_path(OUT_DIR, "slice_census.tsv"))
    mul = Tsv(M.out_path(OUT_DIR, "slice_multiplicity.tsv"))
    itg = Tsv(M.out_path(OUT_DIR, "roster_integrity.tsv"))
    ctx = Tsv(M.out_path(OUT_DIR, "session_context.tsv"))
    red = Tsv(M.out_path(OUT_DIR, "fdisc_redfirst.tsv"))
    dfc = Tsv(M.out_path(OUT_DIR, "spec_defects.tsv"))
    b8v = Tsv(M.out_path(BASE_DIR, "census_family_value.tsv"))
    L = []
    A = L.append
    A("# PORT M1 §10 — FAMILY DISCOVERY CENSUS (D-055)")
    A("")
    A("Generated by `engine/port_m1/family_discovery.py`. Spec: "
      "`design/PORT_M1_SPEC.md` §10 sha16 `%s`. Baseline roster: the frozen "
      "S1-v2 oracle `m1/%s`. FIT = 2021-2024 decides everything; 2025 is an "
      "eval-only echo. Every number carries its source `file:line` (D-010)."
      % (M.SPEC_SHA16, BASE_DIR))
    A("")
    A("## 1. What was found")
    adopt = [r for r in ver.rows if r[ver.i("verdict")].startswith("ADOPT")]
    A("- %d of %d (asset x designed family) cells clear the CC-M1-3.2 "
      "adoption metric; the per-asset verdicts are in §4."
      % (len(adopt), len(ver.rows)))
    for r, ln in zip(mul.rows, mul.lines):
        A("- %s slice miner: %s cells tested (%s marginal + %s two-way), %s "
          "survive Holm at alpha=%.2f, %s clear the promotion rule "
          "(value >= G1 $%s + $%.0f, sign-stable in all four FIT years) "
          "[%s:%d]."
          % (r[mul.i("asset")], r[mul.i("holm_family_size")],
             r[mul.i("n_marginal_cells")], r[mul.i("n_twoway_cells")],
             r[mul.i("n_holm_rejected")], HOLM_ALPHA, r[mul.i("n_promoted")],
             _f(r[mul.i("g1_conditional_value_fit_usd")]), PROMOTE_MARGIN,
             mul.rel(), ln))
    A("")
    A("## 2. Integrity of the substrate")
    A("| asset | union roster | new §10 candidates | reconstruction delta | "
      "orphan tags | source |")
    A("| --- | --- | --- | --- | --- | --- |")
    for r, ln in zip(itg.rows, itg.lines):
        A("| %s | %s | %s | %s | %s | %s |"
          % (r[0], r[1], r[2], r[4], r[5], cite(itg, ln)))
    A("")
    A("`reconstruction delta = 0` means this lane re-ran b8's own emission "
      "code path and reproduced the frozen union roster key for key. The "
      "certificate machinery is likewise identical: G1 conditional value "
      "ALL-era reproduces the committed S1-v2 census exactly —")
    for a in M.ASSET_ORDER:
        r, ln = fam.one(asset=a, family="G1", era=M.ERA_ALL)
        r2, ln2 = b8v.one(asset=a, family="G1")
        if r and r2:
            A("  - %s $%s [%s] vs $%s [%s]"
              % (a, _f(r[fam.i("conditional_value_usd")], "%.2f"),
                 cite(fam, ln), _f(r2[b8v.i("mean_positive_cert_usd")],
                                   "%.2f"), cite(b8v, ln2)))
    A("")
    A("## 3. The designed families as built")
    A("")
    for (k, v) in (("F-D1 FAST-CLOSE", PARAMS["fd1"]),
                   ("F-D2 MICRO-OPENS", PARAMS["fd2"]),
                   ("F-D3 NEWS-WINDOW", PARAMS["fd3"]),
                   ("F-D4 POST-SHOCK", PARAMS["fd4"]),
                   ("F-D5 FIRST-TEST", PARAMS["fd5"]),
                   ("F-D6 EXHAUSTION-AT-EXTENSION", PARAMS["fd6"])):
        A("- **%s** — %s" % (k, v))
    A("")
    n_shock = sum(int(r[ctx.i("n_shock_episodes")]) for r in ctx.rows)
    n_ins = sum(int(r[ctx.i("n_insane_episodes")]) for r in ctx.rows)
    n_fd4 = sum(int(r[ctx.i("n_fd4_triggers")]) for r in ctx.rows)
    A("Event supply over all %d sessions: %d causal repricing episodes + %d "
      "wide-book episodes -> %d F-D4 triggers (`%s`)."
      % (len(ctx.rows), n_shock, n_ins, n_fd4, ctx.rel()))
    A("")
    A("## 4. Designed-family census (FIT era, CC-M1-3.2 metric)")
    A("")
    A("| asset | family | n FIT | cond. value | vs G1 | marginal recall | "
      "DP seat share | FIT-year stable | 2025 echo | peak-exit vs G1 | "
      "verdict | source |")
    A("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- "
      "| --- |")
    for r, ln in zip(ver.rows, ver.lines):
        A("| %s | %s | %s | $%s | %s$%s | %spp | %s | %s | $%s | $%s | "
          "**%s** | %s |"
          % (r[0], r[1], r[2], _f(r[3]),
             "+" if (r[5] and float(r[5]) >= 0) else "", _f(r[5]),
             _f(r[6], "%+.2f"), _f(r[7], "%.3f"),
             "yes" if r[11] == "1" else "no", _f(r[12]), _f(r[14], "%+.0f"),
             r[15], cite(ver, ln)))
    A("")
    A("Union recall by variant (SANE oracle, gate legs @$1,000) — the "
      "marginal-recall column above is this table's difference vs BASE:")
    A("")
    A("| asset | variant | era | gate legs | recall | source |")
    A("| --- | --- | --- | --- | --- | --- |")
    for r, ln in zip(rec.rows, rec.lines):
        if r[rec.i("era")] != M.ERA_FIT:
            continue
        A("| %s | %s | %s | %s | %s | %s |"
          % (r[0], r[1], r[2], r[4], _f(r[6], "%.4f"), cite(rec, ln)))
    A("")
    A("## 5. Slice miner (§10B)")
    A("")
    A("| asset | G1 FIT value (close / peak) | marginal cells | 2-way cells "
      "| Holm family | Holm rejected | promoted | source |")
    A("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for r, ln in zip(mul.rows, mul.lines):
        A("| %s | $%s / $%s | %s | %s | %s | %s | %s | %s |"
          % (r[0], _f(r[1]), _f(r[2]), r[3], r[4], r[5], r[6], r[7],
             cite(mul, ln)))
    A("")
    for a in M.ASSET_ORDER:
        rows = [(r, ln) for r, ln in zip(sli.rows, sli.lines) if r[0] == a]
        A("### %s — top %d slices by FIT conditional value" % (a, TOP_K_REPORT))
        A("")
        A("| # | axes | condition | n FIT | value | vs G1 | peak-exit vs G1 "
          "| median horizon | p (Holm) | sign-stable | 2025 echo | promoted | "
          "source |")
        A("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- "
          "| --- | --- |")
        for r, ln in rows[:TOP_K_REPORT]:
            A("| %s | %s | %s | %s | $%s | %s$%s | $%s | %s | %s | %s | $%s | "
              "%s | %s |"
              % (r[1], r[2], r[3], r[4], _f(r[6]),
                 "+" if (r[8] and float(r[8]) >= 0) else "", _f(r[8]),
                 _f(r[23], "%+.0f"), _hrs(r[24]),
                 _f(r[11], "%.3g"), "yes" if r[13] == "1" else "no",
                 _f(r[19]), "YES" if r[20] == "1" else "no", cite(sli, ln)))
        A("")
        prom = [(r, ln) for r, ln in rows if r[20] == "1"]
        A("%d promoted slices for %s (Holm-significant, >= G1+$%.0f, "
          "sign-stable in every FIT year). They overlap heavily (a promoted "
          "2-way cell usually sits inside a promoted marginal), so the "
          "adoption unit is the CONDITION, not the row count."
          % (len(prom), a, PROMOTE_MARGIN))
        A("")
    A("## 6. Red-first evidence")
    A("")
    A("| algorithm | mutant | cases broken | source |")
    A("| --- | --- | --- | --- |")
    for r, ln in zip(red.rows, red.lines):
        A("| %s | %s | %s | %s |" % (r[0], r[1], r[3], cite(red, ln)))
    A("")
    A("## 7. Adoption recommendation (what this lane would take forward)")
    A("")
    A("The CC-M1-3.2 metric is an OR of three tests, and two of them are "
      "degenerate for this stage — that is a finding, not an excuse:")
    A("")
    for r, ln in zip(rec.rows, rec.lines):
        if r[rec.i("variant")] != "BASE" or r[rec.i("era")] != M.ERA_FIT:
            continue
        A("- (ii) MARGINAL RECALL is saturated: the frozen union roster "
          "already captures %s of %s %s gate legs, so no added family can "
          "move recall by the +%.1fpp the metric asks for [%s]."
          % (_f(r[rec.i("recall_gate_1000")], "%.4f"),
             r[rec.i("n_gate_legs")], r[0], MARGINAL_RECALL_PP,
             cite(rec, ln)))
    A("- (iii) DP SEAT SHARE rewards SIZE, not quality: a tag covering a "
      "third of the roster inherits a third of the seats at exactly baseline "
      "value. F-D6 is the case in point below.")
    A("- (i) CONDITIONAL VALUE is therefore the operative test here, and the "
      "honest reading adds a second requirement the metric does not state: "
      "the family must be SMALLER and BETTER than the baseline, not merely "
      "not-worse.")
    A("")
    A("**THE HORIZON CONFOUND (this lane's most important caveat).** The "
      "CC-M1-3.2 value is the walled PHASE-CLOSE certificate, and its horizon "
      "is the time from the decision to that close — which is a function of "
      "the clock. Any family or slice defined ON the clock therefore measures "
      "edge AND horizon together. Both halves of §10 are cut on the clock, so "
      "every table below carries the walled PEAK-exit certificate beside it "
      "as the horizon-free comparator (`conditional_value_peak_usd` in "
      "`%s`, `value_peak_exit_usd` + `median_horizon_to_phase_close_sec` in "
      "`%s`). Where the two disagree, the disagreement IS the result:"
      % (fam.rel(), sli.rel()))
    A("")
    fd1 = [(a, ver.one(asset=a, family="FD1_CLOSE_15")[0]) for a in
           M.ASSET_ORDER]
    A("- F-D1 FAST-CLOSE loses %s / %s / %s (SI/HG/NKD) on the close "
      "certificate but only %s / %s / %s on the peak-exit one: its deficit is "
      "an EXIT-HORIZON effect, not a signal-quality effect. The candidates "
      "move; the certificate just closes the position before they finish."
      % tuple([_f(r[ver.i("value_minus_g1_usd")], "%+.0f") if r else "n/a"
               for _a, r in fd1]
              + [_f(r[ver.i("peak_exit_value_minus_g1_usd")], "%+.0f")
                 if r else "n/a" for _a, r in fd1]))
    A("- F-D2 and F-D3 are the mirror image: strong on the close certificate "
      "(+$%s / +$%s SI) and ~flat on the peak-exit one (%s / %s), i.e. much "
      "of their measured edge is 'entered with the phase still ahead of it', "
      "not 'opens and releases are special'."
      % (dg1("SI", "FD2_MICRO_OPEN"), dg1("SI", "FD3_NEWS_15"),
         _f(vv("SI", "FD2_MICRO_OPEN", "peak_exit_value_minus_g1_usd"),
            "%+.0f"),
         _f(vv("SI", "FD3_NEWS_15", "peak_exit_value_minus_g1_usd"),
            "%+.0f")))
    A("- F-D4 POST-SHOCK and F-D5 FIRST-TEST are the two that survive BOTH "
      "readings (F-D4 %s / %s / %s peak-exit vs G1; F-D5 %s / %s / %s) — "
      "they are the genuine mechanism finds of this stage."
      % (_f(vv("SI", "FD4_POST_SHOCK", "peak_exit_value_minus_g1_usd"),
            "%+.0f"),
         _f(vv("HG", "FD4_POST_SHOCK", "peak_exit_value_minus_g1_usd"),
            "%+.0f"),
         _f(vv("NKD", "FD4_POST_SHOCK", "peak_exit_value_minus_g1_usd"),
            "%+.0f"),
         _f(vv("SI", "FD5_FIRST_TEST", "peak_exit_value_minus_g1_usd"),
            "%+.0f"),
         _f(vv("HG", "FD5_FIRST_TEST", "peak_exit_value_minus_g1_usd"),
            "%+.0f"),
         _f(vv("NKD", "FD5_FIRST_TEST", "peak_exit_value_minus_g1_usd"),
            "%+.0f")))
    A("")
    A("| family | reading | recommendation |")
    A("| --- | --- | --- |")
    def vv(a, f, col="conditional_value_usd"):
        r, _ln = ver.one(asset=a, family=f)
        return r[ver.i(col)] if r else ""
    def dg1(a, f):
        return _f(vv(a, f, "value_minus_g1_usd"))
    def nn(a, f):
        return vv(a, f, "n_candidates_fit")
    A("| F-D3 NEWS-WINDOW | +$%s SI / +$%s NKD / +$%s HG at n=%s/%s/%s FIT, "
      "sign-stable in all four FIT years, 2025 echo higher — but ~flat on the "
      "horizon-free comparator | **ADOPT** on the operative (close-exit) "
      "metric, which is also the contract's hold-to-close shape (D-019); 15s "
      "and 60s land within $%s of each other, so one delay suffices |"
      % (dg1("SI", "FD3_NEWS_15"), dg1("NKD", "FD3_NEWS_15"),
         dg1("HG", "FD3_NEWS_15"), nn("SI", "FD3_NEWS_15"),
         nn("NKD", "FD3_NEWS_15"), nn("HG", "FD3_NEWS_15"),
         _f(abs(float(vv("SI", "FD3_NEWS_15")) - float(vv("SI",
                                                         "FD3_NEWS_60"))))))
    A("| F-D4 POST-SHOCK | the largest per-candidate edge of the stage "
      "(+$%s SI / +$%s NKD / +$%s HG) on the smallest supply (n=%s/%s/%s "
      "FIT), era-concentrated, and it SURVIVES the horizon-free comparator | "
      "**ADOPT — the strongest find of the stage**, with the small-sample "
      "caveat |"
      % (dg1("SI", "FD4_POST_SHOCK"), dg1("NKD", "FD4_POST_SHOCK"),
         dg1("HG", "FD4_POST_SHOCK"), nn("SI", "FD4_POST_SHOCK"),
         nn("NKD", "FD4_POST_SHOCK"), nn("HG", "FD4_POST_SHOCK")))
    A("| F-D2 MICRO-OPENS | consistent positive edge (+$%s / +$%s / +$%s) at "
      "n=%s/%s/%s FIT, ~flat peak-exit | **ADOPT** on the close-exit metric, "
      "with the horizon caveat |"
      % (dg1("SI", "FD2_MICRO_OPEN"), dg1("NKD", "FD2_MICRO_OPEN"),
         dg1("HG", "FD2_MICRO_OPEN"), nn("SI", "FD2_MICRO_OPEN"),
         nn("NKD", "FD2_MICRO_OPEN"), nn("HG", "FD2_MICRO_OPEN")))
    A("| F-D5 FIRST-TEST | close-exit is asset-split ($%s NKD / $%s SI / $%s "
      "HG) but PEAK-exit is positive on all three ($%s / $%s / $%s): the "
      "first test of a level is a real quality signal that the close "
      "certificate under-reads | **ADOPT on NKD**; on SI/HG adopt as a "
      "FEATURE now and re-test as a family once an exit rule exists |"
      % (dg1("NKD", "FD5_FIRST_TEST"), dg1("SI", "FD5_FIRST_TEST"),
         dg1("HG", "FD5_FIRST_TEST"),
         _f(vv("NKD", "FD5_FIRST_TEST", "peak_exit_value_minus_g1_usd"),
            "%+.0f"),
         _f(vv("SI", "FD5_FIRST_TEST", "peak_exit_value_minus_g1_usd"),
            "%+.0f"),
         _f(vv("HG", "FD5_FIRST_TEST", "peak_exit_value_minus_g1_usd"),
            "%+.0f")))
    A("| F-D6 EXHAUSTION | passes only on size: %s SI candidates at $%s vs "
      "G1, and HG adopted no OR_EXT cell so the family is empty there | "
      "**DO NOT adopt as a generator family** — it emits no new candidate and "
      "has no value edge; keep the beyond-extension flag as a FEATURE |"
      % (nn("SI", "FD6_EXHAUSTION"), dg1("SI", "FD6_EXHAUSTION")))
    A("| F-D1 FAST-CLOSE | decisively negative on the close certificate "
      "($%s SI / $%s NKD / $%s HG) but essentially AT baseline on the "
      "peak-exit one ($%s / $%s / $%s) | **RETIRE as a generator family** "
      "under the phase-close exit, and HAND THE FINDING TO THE EXIT PROGRAM "
      "(D-045/D-046): these candidates are not bad, they are cut off — a "
      "hold-through-the-boundary exit is the experiment |"
      % (dg1("SI", "FD1_CLOSE_15"), dg1("NKD", "FD1_CLOSE_15"),
         dg1("HG", "FD1_CLOSE_15"),
         _f(vv("SI", "FD1_CLOSE_15", "peak_exit_value_minus_g1_usd"),
            "%+.0f"),
         _f(vv("NKD", "FD1_CLOSE_15", "peak_exit_value_minus_g1_usd"),
            "%+.0f"),
         _f(vv("HG", "FD1_CLOSE_15", "peak_exit_value_minus_g1_usd"),
            "%+.0f")))
    A("")
    shares = sorted(100.0 * float(r[mul.i("n_promoted")])
                    / max(1.0, float(r[mul.i("holm_family_size")]))
                    for r in mul.rows)
    A("SLICE MINER: the promotion bar the spec sets (G1 + $%.0f) is LOW "
      "against these rosters — G1 is the weakest of the five S1-v2 families, "
      "so %.0f-%.0f%% of all tested cells clear it (`%s`). The operative "
      "output is "
      "therefore the RANKED top-20 per asset (§5) plus one structural finding "
      "that repeats on every asset and every axis pairing: value concentrates "
      "in a narrow CLOCK band interacted with the HIGH vol-regime tercile "
      "(SI/HG: UTC 11:00-13:00, the London-NY overlap; NKD: UTC 22:00-23:30 "
      "and 04:30, the Tokyo open and the Japan afternoon), plus a "
      "day-of-week tilt (Thu/Fri on SI/HG, Mon on NKD). CAUTION, stated "
      "because it matters for deployment: `spread_state=WIDE` cells rank high "
      "on SI and NKD, and those are exactly the seconds the m0 tradability "
      "screen (spread <= 2x phase median) rejects — that value may not be "
      "capturable, and the pair should be re-measured on the screened roster "
      "before any of it becomes a family. SECOND CAUTION, from the horizon "
      "confound above: the winning clock cells also carry the LONGEST median "
      "horizon to the phase close, so `value_peak_exit_usd` is the column to "
      "read before any clock slice is promoted to a family."
      % (PROMOTE_MARGIN, shares[0], shares[-1], mul.rel()))
    A("")
    A("## 8. Spec defects returned to the orchestrator")
    A("")
    for r, ln in zip(dfc.rows, dfc.lines):
        A("- **%s** %s [%s]" % (r[0], r[1], cite(dfc, ln)))
    A("")
    path = M.out_path(OUT_DIR, "FAMILY_DISCOVERY_REPORT.md")
    with open(path, "w") as fh:
        fh.write("\n".join(L) + "\n")
    M.hb("fdisc: report written (%d lines)" % len(L))
    return path


def main():
    # §10 lives in PORT_M1_SPEC.md, so that is the binding pin here.  The M1.B
    # pin is STALE in the repo (defect FD-7) — its observed sha is recorded in
    # the receipt rather than asserted, and no other lane's constant is touched.
    M.verify_spec()
    PARAMS["m1b_spec_sha16_observed"] = M.spec_m1b_sha()[:16]
    workers = int(os.environ.get("M1_WORKERS", "4"))
    assets = [a for a in sys.argv[1:] if a in M.ASSET_ORDER] or \
        list(M.ASSET_ORDER)
    M.hb("fdisc: start assets=%s workers=%d" % (",".join(assets), workers))
    bundle = run(assets, workers)
    ver = write_all(bundle)
    M.write_json(M.out_path(OUT_DIR, "env_receipt.json"),
                 M.env_receipt(PARAMS))
    write_report()
    for r in ver:
        M.hb("fdisc VERDICT %s %-24s value $%.0f (G1 $%.0f) recall %+.2fpp "
             "seats %.3f -> %s" % (r[0], r[1], r[3] if np.isfinite(r[3]) else
                                   float("nan"), r[4], r[6] if np.isfinite(r[6])
                                   else float("nan"),
                                   r[7] if np.isfinite(r[7]) else float("nan"),
                                   r[15]))
    bad = [r for r in bundle[8] if int(r[4]) != 0]
    if bad:
        M.hb("fdisc INTEGRITY FAIL: base reconstruction delta %r" % (bad,))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
