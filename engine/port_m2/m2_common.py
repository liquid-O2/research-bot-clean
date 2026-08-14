#!/usr/bin/python3
"""PORT M2 — shared substrate for the sheet builder (P-M2a).

Implements design/PORT_M2_SHEETS_SPEC.md §1 encoding laws, §2 certificate
plumbing and the M2 output root.  This module carries NO section content: it
holds the frozen-spec pins, the fixed-width formatting primitives, the
deterministic token estimator, the section-budget table and the receipt
writers.

LAWS honoured here
  * D-018   every byte of bulk output goes under artifacts/cache/port/m2/
  * determinism  no RNG anywhere; every ordering is an explicit sort
  * seal    2026 payloads are never opened (the m0 guard is reused verbatim)
  * pins    M2 pins its own spec AND every upstream spec it reads receipts from

TOKEN COUNT (spec §1 "token count logged per sheet").  No BPE tokenizer exists
on this host (no tiktoken / transformers / anthropic package), so the logged
figure is a DETERMINISTIC PROXY, documented here and stamped into every
receipt so the orchestrator can recalibrate:

    alpha run of length L  -> max(1, ceil(L / 5))     (English BPE averages
                                                       ~4-5 chars per token)
    digit run of length L  -> ceil(L / 3)             (cl100k/o200k group
                                                       digits in <=3s)
    space/tab run of len L -> 0 if L <= 1 else max(1, ceil(L / 16))
                                                      (a single space merges
                                                       into the next token; a
                                                       padding RUN does not)
    each other char        -> 1
    each newline           -> 1

Raw chars / bytes / lines are logged beside it so the proxy is auditable and
replaceable without re-rendering anything.
"""
import datetime as dt
import json
import math
import os
import re
import sys

import numpy as np

_M0 = "/workspace/engine/port_m0"
_M1 = "/workspace/engine/port_m1"
for _p in (_M0, _M1):
    if _p not in sys.path:
        sys.path.insert(0, _p)
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import common as C                       # noqa: E402  m0 substrate
import census_common as X                # noqa: E402  m0 census substrate
import m1_common as M1                   # noqa: E402  m1 substrate

# --------------------------------------------------------------- spec pins --
SPEC_PATH = "/workspace/design/PORT_M2_SHEETS_SPEC.md"
SPEC_SHA16 = "f6ef73a41dbf8588"          # = design/PORT_M2_SHEETS_SPEC.md through CC-M2-24 (fix-pass adjudication, commit f6d46b5 — APPENDED adjudication prose only, no builder-behaviour clause); re-pinned 2026-08-15 by the E6 teacher round (the CC-M2-24 append moved the sha and the bump was missed, so every m2 tool refused at HEAD — the FD-8/qr_gen stale-pin defect class again). Previous: 19fedc9231ba9f0e (through CC-M2-22).

# V1.1 (P-M2c warm-up defect fixes, 2026-08-14): S9/S3/S10/S11/S2 REFUSED
# consistency (a derived field whose inputs are refused is refused and COUNTED
# in the certificate), the S7 refill-after-trade constructor rebuilt against the
# MBP-1 event grain, the S5 clock-norm z given a MAD floor with a '~' marker,
# and the S4 OR STATE given an explicit per-cell {TODAY|NOT_OPEN} state plus a
# level-birth causality guard.
SHEETS_VERSION = "PORT-SHEETS-V1.1"      # the §1 S1 "sheets-version stamp"

M2_ROOT = "/workspace/artifacts/cache/port/m2"
M1_ROOT = M1.M1_ROOT
M0_ROOT = C.OUT_ROOT

ASSET_ORDER = C.ASSET_ORDER
PHASE_NAMES = X.PHASE_NAMES

# generation_v3 family/rung vocabulary (the frozen S2.2 oracle, ORACLE_FREEZE)
FAMILIES = ("G1", "G1_FINE", "G1_FAST_OPEN", "G2_REJECT", "G2_RECLAIM",
            "NEWS_WINDOW", "MICRO_OPEN", "POST_SHOCK", "FIRST_TEST")
FAM_BIT = {f: 1 << i for i, f in enumerate(FAMILIES)}
RUNGS = (0.05, 0.075, 0.11, 0.15)
KEPT_LEVEL_FAMILIES = ("FVOL_LADDER", "FVOL_BAND", "NDAY", "PRIOR_DAY",
                       "PHASE_HL", "VWAP", "OR_EXT")
FLAG_NAMES = (("OREXT_BEYOND", 1 << 0), ("OREXT_BEYOND_ANY", 1 << 1),
              ("FIRST_TEST_VIRGIN", 1 << 2))
TOUCH_OUTCOMES = ("NONE", "REJECT", "BREAK", "RECLAIM")

# ------------------------------------------------------- candidate class ----
# D-071 (2026-08-14, BINDING): the candidate CLASS is observable at generation —
# the emitting family IS the mechanism, so no router and no inference.  A
# candidate carrying several family tags declares the class of its
# HIGHEST-PRIORITY family under the CC-M1-11.4 pre-registered total order
# (POST_SHOCK > FIRST_TEST > NEWS_WINDOW > MICRO_OPEN > G2 > G1_FAST_OPEN >
# G1_FINE > G1); the remaining tags are listed beside it, never dropped.
CLASS_REVERSAL = "REVERSAL-CONFIRMATION"
CLASS_RECLAIM = "RECLAIM"
CLASS_SHOCK = "SHOCK-RESOLUTION"
CLASS_OPEN = "OPEN-DYNAMICS"
CLASS_NEWS = "NEWS-WINDOW"
CLASS_FIRST_TEST = "LEVEL-FIRST-TEST"

FAMILY_CLASS = {"G1": CLASS_REVERSAL,
                "G1_FINE": CLASS_REVERSAL,
                "G2_REJECT": CLASS_REVERSAL,
                "G2_RECLAIM": CLASS_RECLAIM,
                "POST_SHOCK": CLASS_SHOCK,
                "G1_FAST_OPEN": CLASS_OPEN,
                "MICRO_OPEN": CLASS_OPEN,
                "NEWS_WINDOW": CLASS_NEWS,
                "FIRST_TEST": CLASS_FIRST_TEST}

# mirrors engine/port_m1/episode_census.FAM_PRIORITY (CC-M1-11.4).  The mirror
# is guarded by test_m2.t18 — a divergence from the pre-registered order is a
# defect, not a local choice.
FAMILY_PRIORITY = {"POST_SHOCK": 0, "FIRST_TEST": 1, "NEWS_WINDOW": 2,
                   "MICRO_OPEN": 3, "G2_REJECT": 4, "G2_RECLAIM": 4,
                   "G1_FAST_OPEN": 5, "G1_FINE": 6, "G1": 7}

# class declaration order = the priority of each class's best family, then the
# FAMILIES declaration order (the G2_REJECT / G2_RECLAIM tie at priority 4)
CLASS_ORDER = tuple(sorted(
    {FAMILY_CLASS[f] for f in FAMILIES},
    key=lambda c: min((FAMILY_PRIORITY[f], FAMILIES.index(f))
                      for f in FAMILIES if FAMILY_CLASS[f] == c)))
CLASS_UNKNOWN = "UNCLASSED"

# ------------------------------------------------- CC-M2-22.1 display names --
# R102.  CC-M2-22.1 (BINDING) renames NEWS_WINDOW to US_CLOCK because only 19%
# of its fires sit on dated releases — the family's edge is clock structure, so
# the name must say so (D-006 honesty).  Executing that as a SUBSTITUTION would
# break five consumers at once: FAMILY_CLASS, the `cls` string in all 204,737
# rendered sheets, the `cls` column of every committed triage index,
# baseline_replay.COND_VALUE, and e1_blind_declared_policy.HI_CLASSES — which
# CC-M2-4.3 forbids editing.  So the rename is a DISPLAY-LAYER ALIAS and the
# WIRE VALUE stays pinned: every sealed artefact keeps its sealed spelling and
# every report renders the adjudicated name.
WIRE_TO_DISPLAY = {"NEWS_WINDOW": "US_CLOCK",
                   CLASS_NEWS: "US-CLOCK"}
DISPLAY_TO_WIRE = {v: k for k, v in WIRE_TO_DISPLAY.items()}


def display_name(wire):
    """The adjudicated display name for a sealed family/class spelling."""
    return WIRE_TO_DISPLAY.get(str(wire), str(wire))


def wire_name(display):
    """The sealed spelling for an adjudicated display name.  Every join, every
    lookup and every committed column uses THIS, never the display name."""
    return DISPLAY_TO_WIRE.get(str(display), str(display))


def class_of(fam_mask):
    """(class, driver_family, [other family tags]) for a candidate's fam_mask."""
    fams = fam_names(fam_mask)
    if not fams:
        return CLASS_UNKNOWN, None, []
    fams = sorted(fams, key=lambda f: (FAMILY_PRIORITY[f], FAMILIES.index(f)))
    return FAMILY_CLASS[fams[0]], fams[0], fams[1:]


def classes_of(fam_mask):
    """Every class the candidate's tags touch, in declaration order (the
    declared class first).  Cross-class tags are tracked, never dropped."""
    cls, driver, others = class_of(fam_mask)
    rest = [c for c in CLASS_ORDER
            if c != cls and any(FAMILY_CLASS[f] == c for f in others)]
    return [cls] + rest


WALL_CAP = X.WALL_CAP                    # $900 (§1 / D-021 lineage)
TAU_STAR = 120

# ------------------------------------------------------------------ eras ----
# spec §3 ERAS verbatim.  Sessions before E1 (HG/NKD carry 2021H1 tape that the
# protocol does not enter) are tagged PRE_E1 and are out of protocol scope.
ERAS = (("E1", 20210701, 20211231),
        ("E2", 20220101, 20220630),
        ("E3", 20220701, 20221231),
        ("E4", 20230101, 20230630),
        ("E5", 20230701, 20231231),
        ("E6", 20240101, 20240630),
        ("E7", 20240701, 20241231),
        ("E8", 20250101, 20250630))
ERA_HOLDOUT = ("HOLDOUT_2025H2", 20250701, 20251231)
SEAL_CUTOFF = C.SEAL_CUTOFF              # 20260101

# D-058 PRE-EXAM HOLDOUT — the ONE boundary (CC-M2-15.3 corrected it to
# 2025-07-01).  It lived as a private constant in batch4_census and five
# modules simply never imported it (R57/R58/R105/R118).  It lives HERE now and
# the session enumerators refuse past it unless a caller opts in explicitly.
HOLDOUT_FROM_D8 = ERA_HOLDOUT[1]         # 20250701


class HoldoutRefusal(RuntimeError):
    """Raised when a lane enumerates D-058 pre-exam holdout sessions without
    an explicit allow_holdout=True.  A refusal, never a silent filter."""


def in_holdout(d8):
    return int(d8) >= HOLDOUT_FROM_D8


def guarded_session_paths(asset, root=None, allow_holdout=False):
    """THE M2 session enumerator.  Returns (paths, n_quarantined).

    R118's structural fix: `census_common.session_paths` is the substrate's
    enumerator and has no modelling boundary in it, so every M2 lane that
    walked it directly (regime_forecast) silently trained on the D-058 holdout.
    Every M2 consumer goes through here instead; the quarantine count is
    RETURNED so it is declared in a receipt rather than being invisible.
    """
    out = X.session_paths(asset, root if root is not None else M0_ROOT)
    if allow_holdout:
        return out, 0
    keep = [(d, p) for d, p in out if not in_holdout(d8(d))]
    return keep, len(out) - len(keep)


def era_of(d8):
    d8 = int(d8)
    if d8 >= SEAL_CUTOFF:
        raise C.SealRefusal("SEAL: 2026 session %d is never rendered" % d8)
    for name, lo, hi in ERAS:
        if lo <= d8 <= hi:
            return name
    if ERA_HOLDOUT[1] <= d8 <= ERA_HOLDOUT[2]:
        return ERA_HOLDOUT[0]
    return "PRE_E1"


# --------------------------------------------------------------- modes ------
MODE_BLIND = "BLIND"
MODE_STUDY = "STUDY"
MODES = (MODE_BLIND, MODE_STUDY)

# §1: S14 exists ONLY in study mode, and only as a SEPARATE appendix rendered
# after the call is committed.  The builder therefore owns two artefacts, never
# one file with a hidden tail.
BLIND_SECTIONS = tuple("S%d" % i for i in range(1, 14))
STUDY_SECTIONS = ("S14",)

SECTION_TITLES = {
    "S1": "HEADER + COMPLETENESS CERTIFICATE",
    "S2": "ERA PRIMER REF + REGIME TAGS",
    "S3": "SESSION PATH + SWING CHAIN",
    "S4": "LEVEL LEDGER VIEW",
    "S5": "T-MINUS TRAJECTORY",
    "S6": "RAW EVENT RIBBON",
    "S7": "BOOK/QUEUE STATE",
    "S8": "FLOW STATE",
    "S9": "VOL STATE",
    "S10": "VOLUME PROFILE",
    "S11": "CROSS-ASSET",
    "S12": "CONTEXT (availability-lagged)",
    "S13": "CANDIDATE MECHANICS",
    "S14": "OUTCOMES (STUDY MODE)",
}

# §1 "section budget enforced (S6 is the largest)".  Budgets are in PROXY
# tokens (see module docstring); they are pinned here, stamped into PARAMS and
# reported per sheet.  A section over budget is a certificate FAILURE.
# Calibrated against the 30-sheet pilot (artifacts/cache/port/m2/pilot/
# pilot.receipt.json): each budget is ~1.15x the observed per-section maximum,
# so the law binds without failing sheets for ordinary content variation.  S6
# is the exception: its budget is the POLICY knob, and the raw ribbon fills
# whatever it is given (see sections.py S6 block).
# CC-M2-1.1 (BINDING, orchestrator 2026-08-13): S6 2,000 -> 3,000 proxy tokens.
# The raw-ribbon coverage roughly doubles (~20s median raw) at the recorded
# exchange rate of 25 proxy-tokens per raw second; the episode-digest mechanism
# stays the lossless layer for the remainder, and low-density candidates keep
# carrying the full 90s raw window.
# D-071 recalibration: S1 640 -> 720 (the class line) and S13 420 -> 720 (the
# class census card).  S13 is the one budget that must be set from its WORST
# CASE rather than from the 30-sheet pilot: its family card prints one row per
# carried family per era, so a candidate tagged with many families renders a
# much longer section than any pilot sheet did (measured: a 9-tag FIRST_TEST
# candidate spends 566 against the pilot maximum of 499).  The bound is
# 2 class rows + 9 families x 2 eras + 4 fixed lines ~= 620 proxy tokens, so the
# budget is 1.15x that bound.  Every other budget is unchanged and every other
# section is row-bounded by construction (S3 last 8 pivots, S4 12 levels, S8
# last 6 prints, S12 a fixed series list); S6 fits itself to its budget.
# V1.1 recalibration (P-M2c defect fixes), each against the new worst case:
#   S1  720 -> 1000  the REFUSED-DERIVED roster (up to 30 keys, wrapped) rides
#                    in the certificate block; a fully fvol-refused SI sheet
#                    spends ~870.
#   S5  340 ->  400  the z-column law is now stated in the section title and
#                    every z carries the '~' floor marker.
#   S7  240 ->  320  refill_after_trade grew three audit fields (n_measurable,
#                    swept, no_book_reaction) plus its one-line definition.
# V1.2 (the D-001 fix pass, 2026-08-14):
#   S4 1100 -> 1240  spec §1 S4 names "distance ($ AND ATR)" and "CREATED-WHEN"
#                    and the table carried NEITHER (R100; `created_d8` was read
#                    and never used).  Two columns on 12 rows plus the refused
#                    prior-state accounting (R96).
#   S5  400 ->  520  spec §1 S5 names sflow/min, RV nowcast and mid among the
#                    z-scored quantities and the code emitted z for none of the
#                    three (R99), with abs_sflow_per_min computed into the
#                    clock-norm digest and never consumed.
#   S12 720 ->  800  the R14 VINTAGE declaration (which of the joined series
#                    carry no point-in-time archive) is a line the reader has to
#                    have; a fully-joined SI sheet spent 720 of 720 without it.
#   S3  780 ->  860  the OBSERVED-close runway rides beside the scheduled one
#                    (D15/V1.2: the nominal runway is wrong by HOURS on
#                    early-close sessions and runway_to_seat is the program's
#                    central conditioning object).
# S6 is the elastic section and is rendered last with the sheet's remaining
# allowance, so these raises spend S6's headroom, not the sheet cap.
SECTION_BUDGET = {
    "S1": 1000, "S2": 260, "S3": 860, "S4": 1240, "S5": 520,
    "S6": 3000, "S7": 320, "S8": 600, "S9": 300, "S10": 340,
    "S11": 180, "S12": 800, "S13": 720, "S14": 760,
}
# Binding whole-sheet cap, not the sum of the parts: a sheet may not spend every
# section's headroom at once.  CC-M2-1.1: 7,400 -> 8,500 with the S6 raise.
SHEET_BUDGET_BLIND = 8500
# MINOR (R100 list): `S6_TOKENS_PER_RAW_SEC = 25` was the CC-M2-1.1 exchange
# rate ON RECORD and was referenced NOWHERE, while the actual fit uses
# `sections.S6_RAW_TOKEN_EST = 27` PER LINE — different units, so a budget
# re-derivation from the recorded rate could not reproduce the code.  The rate
# is kept for the record with its units named and its live counterpart cited.
S6_TOKENS_PER_RAW_SEC = 25               # CC-M2-1.1, tokens per raw SECOND
                                         # (the record); the BINDING constant
                                         # is sections.S6_RAW_TOKEN_EST = 27
                                         # tokens per raw LINE


# ------------------------------------------------------------ KNOWN_TRAPS ---
# CC-M2-1.3 (BINDING): the registry of receipt fields whose committed value is
# NOT knowable at decision time.  A consumer that reads one directly leaks.
# Every entry names the test that proves the builder refuses the trap; the
# registry test (test_m2.t16) fails if an entry names a test that does not
# exist, which is the mechanical form of "additions require a test".
KNOWN_TRAPS = {
    "levels_v4.last_test_outcome": {
        "receipt": "artifacts/cache/port/m1/levels_v4/{ASSET}/{d8}.npz",
        "field": "touches[:,5] (outcome) / touches[:,6] (outcome_sec)",
        "why": "a touch outcome resolves inside a FORWARD 15-minute window "
               "(b3_levels REJECT_WINDOW); the committed column is the "
               "end-of-window value",
        "builder_rule": "S4 prints PENDING until the outcome's own resolution "
                        "second (or the whole 15-minute window) has elapsed "
                        "before decision_sec",
        "test": "t09_s4_touch_state_is_causal",
        "registered": "2026-08-13 CC-M2-1.3",
    },
    "levels_v4.touch_count": {
        "receipt": "artifacts/cache/port/m1/levels_v4/{ASSET}/{d8}.npz",
        "field": "touch_count",
        "why": "end-of-session count over the whole session",
        "builder_rule": "S4 recounts touches with sec < decision_sec and adds "
                        "the causal birth snapshot only",
        "test": "t09_s4_touch_state_is_causal",
        "registered": "2026-08-13 CC-M2-1.3",
    },
    "levels_v4.fvol_open_anchor": {
        "receipt": "artifacts/cache/port/m1/levels_v4/{ASSET}/{d8}.npz",
        "field": "level_price for FVOL_BAND / FVOL_LADDER / FVOL_LADDER_RS "
                 "rows whose level_id carries an OPEN_<PHASE> anchor",
        "why": "b3_levels anchors these families at each of TOKYO/LONDON/NY's "
               "OPENING MID (b3_levels.py:239-273) and levels_v4 persists no "
               "`active_from`, so the committed price of an OPEN_NY level is "
               "computed from a mid HOURS AFTER a Tokyo-phase decision (R93: "
               "1,998 of 12,418 E1 BLIND sheets, 6,892 rows)",
        "builder_rule": "sections._level_birth_sec routes the static fvol "
                        "families through _anchor_birth_sec, which is the "
                        "phase's first SANE second; the guard then excludes "
                        "any level not yet born at decision_sec",
        "test": "t22_s4_shows_no_unborn_level",
        "registered": "2026-08-14 R93 (the D-001 fix pass)",
    },
    "fvol_forecasts.ratio_range_over_sigmahat": {
        "receipt": "artifacts/cache/port/m1/fvol/fvol_forecasts.tsv",
        "field": "ratio_range_over_sigmahat",
        "why": "b2_fvol.py:673 computes it as the row's OWN SESSION realized "
               "range divided by sigma_hat — an end-of-session outcome sitting "
               "in the same dict S2/S3/S9 index by name, one .get() away from "
               "a live leak",
        "builder_rule": "no section reads it; the registry makes a future "
                        "reader's .get() a registered trap rather than a "
                        "silent one",
        "test": "t17_known_traps_registered",
        "registered": "2026-08-14 R100-list (the D-001 fix pass)",
    },
    "m0_session_meta.dominant_share": {
        "receipt": "artifacts/cache/port/m0/sessions/{ASSET}/{d8}.npz",
        "field": "meta_json.dominant_share / roll_window / dying_book_week / "
                 "instrument_change / last_two_sided_sec",
        "why": "whole-session or strictly FORWARD facts (s3_sessions.py:335, "
               ":361, :365-366, :340) — dying_book_week and roll_window look "
               "FIVE SESSIONS AHEAD (R94)",
        "builder_rule": "S2 REFUSES all four and prints the causal "
                        "insane_frac_so_far in place of session_insane_frac; "
                        "last_two_sided_sec reaches the sheet only through "
                        "session_close.trailing_shortfall, a strictly-prior "
                        "trailing window",
        "test": "t20_refused_derived_is_refused_and_counted",
        "registered": "2026-08-14 R94 (the D-001 fix pass)",
    },
}


# ------------------------------------------------------------- spec guard ---
def spec_sha():
    return C.sha256_file(SPEC_PATH)


_VERIFIED = {}


def verify_spec(force=False):
    """M2 pins its own spec AND every upstream spec whose receipts it reads.

    PIN-AT-LAUNCH (P-M2b): the check is performed once per PROCESS and then
    memoised.  The workspace is shared with other lanes that edit and re-pin the
    UPSTREAM specs (PORT_M1_SPEC §11 landed in the middle of a P-M2b render and
    killed it at sheet 95/391).  A run must be verified against the pins it
    started with, not race a concurrent editor mid-render; `force=True` (the
    driver's start-of-run call) always performs the real check, and callers that
    care re-check at the END through `pins_moved()`, which reports rather than
    hides a mid-run move.
    """
    if _VERIFIED and not force:
        return _VERIFIED["m2_spec_sha16"]
    got = spec_sha()[:16]
    if got != SPEC_SHA16:
        raise RuntimeError("M2 spec sha16 %s != frozen %s" % (got, SPEC_SHA16))
    M1.verify_spec_m1b()                 # pins PORT_M1B + PORT_M1 + PORT_M0
    _VERIFIED.clear()
    _VERIFIED.update(spec_shas())
    return got


def pins_moved():
    """Re-read every pinned spec; [] when the pins still hold at HEAD."""
    out = []
    try:
        verify_spec(force=True)
    except Exception as e:                # noqa: BLE001 — reported, not raised
        out.append(str(e))
    return out


def spec_shas():
    return {"m2_spec_sha16": SPEC_SHA16,
            "m1b_spec_sha16": M1.SPEC_M1B_SHA16,
            "m1_spec_sha16": M1.SPEC_SHA16,
            "m0_spec_sha16": C.SPEC_SHA16}


def out_path(*parts):
    p = os.path.join(M2_ROOT, *parts)
    d = os.path.dirname(p)
    if d:
        os.makedirs(d, exist_ok=True)
    return p


# ------------------------------------------------------- candidate identity --
SIDE_CHAR = {1: "L", -1: "S"}
CHAR_SIDE = {"L": 1, "S": -1}
_CID_RE = re.compile(r"^(SI|HG|NKD)-(\d{8})-(\d{6})-([LS])$")


def make_cid(asset, d8, dec_sec, side):
    """The candidate id.  (session, decision_sec, side) is the generation-v3
    dedup key, so this is unique by construction and needs no counter."""
    return "%s-%08d-%06d-%s" % (asset, int(d8), int(dec_sec),
                                SIDE_CHAR[int(side)])


def parse_cid(cid):
    m = _CID_RE.match(cid)
    if not m:
        raise ValueError("bad candidate id %r" % cid)
    return m.group(1), int(m.group(2)), int(m.group(3)), CHAR_SIDE[m.group(4)]


# ------------------------------------------------------------- formatting ---
# §1 ENCODING LAWS: fixed-width columns, no prose padding, integer ticks where
# possible, deterministic byte-identical rendering.
NA = "."                                 # the single typed-missing glyph


def fnum(v, width, dec):
    """Fixed-width decimal.  Non-finite -> the typed-missing glyph, never 0."""
    if v is None:
        return NA.rjust(width)
    v = float(v)
    if not np.isfinite(v):
        return NA.rjust(width)
    # round-half-up on the printed grid so two runs cannot differ on a tie
    q = 10.0 ** dec
    r = math.floor(abs(v) * q + 0.5) / q
    s = "%.*f" % (dec, r)
    if v < 0 and r != 0.0:
        s = "-" + s
    return s.rjust(width)


def fint(v, width):
    if v is None:
        return NA.rjust(width)
    if isinstance(v, float) and not np.isfinite(v):
        return NA.rjust(width)
    return ("%d" % int(v)).rjust(width)


def fstr(s, width):
    s = "" if s is None else str(s)
    if len(s) > width:
        s = s[:width]
    return s.ljust(width)


def fsec(sec):
    """Session second -> HH:MM:SS of the session clock (fixed width 8)."""
    if sec is None or (isinstance(sec, float) and not np.isfinite(sec)):
        return NA.rjust(8)
    sec = int(sec)
    sign = "-" if sec < 0 else ""
    a = abs(sec)
    return "%s%02d:%02d:%02d" % (sign, a // 3600, (a // 60) % 60, a % 60)


def futc(epoch):
    """UTC epoch second -> 'YYYY-MM-DDTHH:MM:SSZ' (fixed width 20)."""
    return dt.datetime.utcfromtimestamp(int(epoch)).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def ticks(px, anchor_px, tick_px):
    """Signed integer tick offset of a price from the sheet anchor (§1 'integer
    ticks where possible').  Non-finite in -> None out."""
    if px is None or not np.isfinite(px):
        return None
    return int(math.floor((px - anchor_px) / tick_px + 0.5))


def row(*cells):
    """Join fixed-width cells with a single space and strip the trailing run —
    trailing whitespace is invisible and would make byte identity fragile."""
    return " ".join(cells).rstrip()


def bits_to_names(mask, table):
    out = []
    for name, bit in table:
        if int(mask) & bit:
            out.append(name)
    return out


def fam_names(fam_mask):
    return [f for f in FAMILIES if int(fam_mask) & FAM_BIT[f]]


def rung_names(rung_mask):
    return ["%.4g" % RUNGS[i] for i in range(len(RUNGS))
            if int(rung_mask) & (1 << i)]


def level_fam_names(level_mask):
    return [KEPT_LEVEL_FAMILIES[i] for i in range(len(KEPT_LEVEL_FAMILIES))
            if int(level_mask) & (1 << i)]


# --------------------------------------------------------- token estimator --
_TOK_RE = re.compile(r"[A-Za-z]+|[0-9]+|\n|[ \t]+|[^\sA-Za-z0-9]")
TOKEN_PROXY_ID = "M2-PROXY-2"


def count_tokens(text):
    """Deterministic BPE proxy — see the module docstring for the rule.

    PROXY-2 adds the whitespace term.  PROXY-1 charged nothing for padding,
    which flattered fixed-width tables badly: a single space merges into the
    following token in every BPE this program will ever face, but a RUN of
    padding spaces does not, and this builder pads every column.
    """
    n = 0
    for m in _TOK_RE.finditer(text):
        s = m.group(0)
        c = s[0]
        if c == "\n":
            n += 1
        elif c in " \t":
            n += 0 if len(s) <= 1 else max(1, -(-len(s) // 16))
        elif c.isdigit():
            n += -(-len(s) // 3)
        elif c.isalpha():
            n += max(1, -(-len(s) // 5))
        else:
            n += 1
    return n


def text_metrics(text):
    return {"tokens_proxy": count_tokens(text),
            "chars": len(text),
            "bytes": len(text.encode("utf-8")),
            "lines": text.count("\n") + (0 if text.endswith("\n") else 1)
            if text else 0}


# ---------------------------------------------------------------- receipts --
def env_receipt(params):
    e = C.env_receipt(params)
    e.update(spec_shas())
    e["sheets_version"] = SHEETS_VERSION
    e["token_proxy"] = TOKEN_PROXY_ID
    return e


def write_json(path, obj):
    return C.write_json(path, obj)


def write_text(path, text):
    """Deterministic text write (atomic replace, LF only, no trailing spaces)."""
    tmp = path + ".tmp"
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(tmp, "w", newline="\n") as fh:
        fh.write(text)
    os.replace(tmp, path)
    return path


def write_tsv(path, section, phash, columns, rows, extra=()):
    tmp = path + ".tmp"
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    lines = ["# PORT_M2_SHEETS_SPEC.md %s (spec_sha16=%s)" % (section, SPEC_SHA16),
             "# params_hash=%s" % phash]
    for e in extra:
        lines.append("# %s" % e)
    lines.append("\t".join(columns))
    with open(tmp, "w", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
        for r in rows:
            fh.write("\t".join(_cell(v) for v in r) + "\n")
    os.replace(tmp, path)
    return path


def _cell(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, (float, np.floating)):
        v = float(v)
        return "" if not np.isfinite(v) else "%.6f" % v
    if isinstance(v, (np.integer,)):
        return str(int(v))
    return _escape_cell(str(v))


# R38: free text written verbatim into a TSV silently shifted every later
# column of its row.  Tabs/newlines/CR are escaped on the way out; nothing in
# the corpus legitimately contains them, so this is loss-free in practice and
# the escape is reversible.
_ESCAPES = (("\\", "\\\\"), ("\t", "\\t"), ("\r", "\\r"), ("\n", "\\n"))


def _escape_cell(s):
    if not any(c in s for c in ("\\", "\t", "\r", "\n")):
        return s
    for a, b in _ESCAPES:
        s = s.replace(a, b)
    return s


def unescape_cell(s):
    """Inverse of `_escape_cell` for consumers that need the original text."""
    out, i, n = [], 0, len(s)
    while i < n:
        c = s[i]
        if c == "\\" and i + 1 < n:
            nx = s[i + 1]
            if nx == "\\":
                out.append("\\")
            elif nx == "t":
                out.append("\t")
            elif nx == "r":
                out.append("\r")
            elif nx == "n":
                out.append("\n")
            else:
                out.append(c)
                out.append(nx)
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


# ------------------------------------------------------- refusal vocabulary --
# CC-M2-20.3 REFUSED-CLAUSE LAW, implemented as a VALUE (R06/R21/R71..R74/
# R89/R96/R109/R110/R122).  A derived flag has three states, not two: fired,
# did-not-fire, and could-not-be-computed.  `R` is the third; every consumer
# that treats it as a number must refuse instead.
REFUSED_TOKEN = "R"


def flag3(inputs_ok, condition):
    """Three-valued derived flag: 1 / 0 / 'R'.

    inputs_ok  — every input the predicate reads was present
    condition  — the predicate's truth value (evaluated only when inputs_ok)
    """
    if not inputs_ok:
        return REFUSED_TOKEN
    return 1 if bool(condition) else 0


def is_refused(v):
    return isinstance(v, str) and v == REFUSED_TOKEN


# ------------------------------------------------------------- mirror law ----
# R59.  `mirror_law_holds = (lost == 0 and won > 0)` was minted (CC-M2-13.1) on
# STUDY ROUNDS of 4-14 sessions, where a clean sweep is attainable, and then
# transplanted verbatim to eras of 3,000+ asset-sessions, where it is an
# unpassable criterion with zero power that no real signal can clear.  It gated
# EVERY directional verdict the program ratified (P031, S10 side, erosion side,
# hand side-calling).  The two forms are different tests and both live here,
# under different names, with the era-scale form being a proper paired test.
MIRROR_MIN_SESSIONS = 30                 # power floor for the era-scale form


def mirror_sweep_clean(won, lost):
    """The STUDY-ROUND diagnostic, under its own name: a clean sweep.

    Honest only where a sweep is attainable (n <= ~20 sessions).  Never a
    verdict criterion at era scale — see `mirror_paired`."""
    return int(int(lost) == 0 and int(won) > 0)


def mirror_paired(deltas, min_sessions=None):
    """The ERA-SCALE mirror law: a session-clustered PAIRED test.

    `deltas` is one value per SESSION (or per cluster): the estimator's value
    on that session MINUS its sign-flipped mirror's value on the same session.
    The pairing is the cluster, so the session-clustered SE is the ordinary SEM
    over the paired differences (Cameron-Miller CR1 with one observation per
    cluster reduces to exactly this) and a t(n-1) reference is used, not the
    normal, per Cameron-Miller.

    Returns a dict; the caller applies Holm over its own family and reads
    `holds` only after adjusting `p`.  `verdict` is NO_TEST below the power
    floor — an unpowered cell is never scored as a negative.
    """
    a = np.asarray([float(x) for x in deltas], dtype=np.float64)
    a = a[np.isfinite(a)]
    n = int(a.size)
    lo = int(MIRROR_MIN_SESSIONS if min_sessions is None else min_sessions)
    out = {"n_sessions": n, "mean_delta": float("nan"), "sd": float("nan"),
           "se": float("nan"), "t": float("nan"), "p": float("nan"),
           "df": max(n - 1, 0), "n_won": int((a > 0).sum()),
           "n_lost": int((a < 0).sum()), "n_tied": int((a == 0).sum()),
           "p_sign": float("nan"), "mde_80": float("nan"),
           "sweep_clean": mirror_sweep_clean(int((a > 0).sum()),
                                             int((a < 0).sum())),
           "verdict": "NO_TEST", "holds": 0}
    if n == 0:
        return out
    out["mean_delta"] = float(a.mean())
    if n < 2:
        return out
    sd = float(a.std(ddof=1))
    out["sd"] = sd
    se = sd / np.sqrt(n) if sd > 0 else 0.0
    out["se"] = float(se)
    # 80% power, two-sided 5%: |mean| detectable = 2.802 * sd / sqrt(n)
    out["mde_80"] = float(2.802 * sd / np.sqrt(n)) if sd > 0 else 0.0
    out["p_sign"] = float(_sign_test_p(out["n_won"], out["n_lost"]))
    if se > 0:
        t = float(a.mean() / se)
        out["t"] = t
        out["p"] = float(_t_two_sided(t, n - 1))
    elif a.mean() != 0.0:
        out["t"] = float("inf") if a.mean() > 0 else float("-inf")
        out["p"] = 0.0
    else:
        out["t"] = 0.0
        out["p"] = 1.0
    if n < lo:
        out["verdict"] = "NO_TEST"        # underpowered: not a negative
        return out
    out["verdict"] = "TESTED"
    out["holds"] = int(out["mean_delta"] > 0.0 and out["p"] < 0.05)
    return out


def _sign_test_p(won, lost):
    """Exact two-sided binomial sign test (ties excluded)."""
    n = int(won) + int(lost)
    if n == 0:
        return 1.0
    k = min(int(won), int(lost))
    # exact tail, computed in log space so large n does not overflow
    from math import lgamma, exp, log
    tot = 0.0
    for i in range(0, k + 1):
        lp = (lgamma(n + 1) - lgamma(i + 1) - lgamma(n - i + 1)
              + n * log(0.5))
        tot += exp(lp)
    return float(min(1.0, 2.0 * tot))


def _t_two_sided(t, df):
    """Two-sided p from Student-t via the regularised incomplete beta."""
    if df <= 0:
        return float("nan")
    x = float(df) / (float(df) + float(t) * float(t))
    return float(min(1.0, _betainc(0.5 * df, 0.5, x)))


def _betainc(a, b, x):
    """Regularised incomplete beta I_x(a,b) — Lentz continued fraction."""
    from math import lgamma, exp, log
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = lgamma(a + b) - lgamma(a) - lgamma(b)
    front = exp(log(x) * a + log(1.0 - x) * b + lbeta) / a
    if x > (a + 1.0) / (a + b + 2.0):
        return 1.0 - _betainc(b, a, 1.0 - x)
    f, c, d = 1.0, 1.0, 0.0
    for i in range(0, 300):
        m = i // 2
        if i == 0:
            num = 1.0
        elif i % 2 == 0:
            num = (m * (b - m) * x) / ((a + 2.0 * m - 1.0) * (a + 2.0 * m))
        else:
            num = (-(a + m) * (a + b + m) * x
                   / ((a + 2.0 * m) * (a + 2.0 * m + 1.0)))
        d = 1.0 + num * d
        if abs(d) < 1e-30:
            d = 1e-30
        d = 1.0 / d
        c = 1.0 + num / c
        if abs(c) < 1e-30:
            c = 1e-30
        f *= c * d
        if abs(1.0 - c * d) < 1e-12:
            break
    return front * (f - 1.0)


def params_hash(params):
    return C.params_hash(params)


def d8_to_date(n):
    return M1.d8_to_date(n)


def d8(d):
    return M1.d8(d)


def hb(msg):
    C.hb(msg)


# --------------------------------------------------------- leak accounting --
class LeakRefusal(RuntimeError):
    """Raised by the D-057 guard.  NEVER caught inside a section renderer: a
    refusal must reach the builder, which fails the sheet's certificate."""


class CausalGuard(object):
    """The single choke point for "is this datum knowable at decision_ts?".

    Every section that touches a time-stamped datum routes through here, so the
    leak fixture has exactly one thing to attack and the audit is one grep.
    """

    __slots__ = ("decision_ts", "decision_sec", "trade_date", "refusals",
                 "checks")

    def __init__(self, decision_ts, decision_sec, trade_date):
        self.decision_ts = int(decision_ts)
        self.decision_sec = int(decision_sec)
        self.trade_date = trade_date
        self.refusals = []
        self.checks = 0

    # --- session-clock data (tape, levels, profiles, skeletons) -------------
    def sec(self, sec, what):
        """A session second must be STRICTLY BEFORE the decision second.

        Strict, not <=: the decision second's own book is the LAST thing the
        sheet may show, and it is shown through `at_decision` below, which is
        the only sanctioned equal-time reader.
        """
        self.checks += 1
        if sec is None:
            return False
        if int(sec) >= self.decision_sec:
            return False
        return True

    def at_decision(self, sec, what):
        """The decision second itself (the entry book).  Anything later is a
        refusal, not a silent drop — a future session second in a sheet is a
        builder defect, never data."""
        self.checks += 1
        if sec is not None and int(sec) > self.decision_sec:
            self.refusals.append((what, "session_sec", int(sec),
                                  self.decision_sec))
            raise LeakRefusal(
                "D-057: %s reads session second %d > decision second %d"
                % (what, int(sec), self.decision_sec))
        return True

    # --- wall-clock data (every external / context series) ------------------
    def avail(self, availability_ts, what):
        """D-057 strict availability join.

        The directive reads "STRICT (availability_ts <= decision_ts, never
        equal-time)".  Those two clauses cannot both be literal, so the PINNED
        READING (reported) is the conservative one that satisfies both:
            availability_ts < decision_ts
        Availability stamps live on coarse publication clocks (a Friday 15:30
        ET COT release, a next-business-day 00:00 ET FRED post), so strictness
        never costs a legitimately-available observation; it only removes the
        equal-time case the directive names.
        """
        self.checks += 1
        if availability_ts is None:
            return False
        return int(availability_ts) < self.decision_ts

    def refuse(self, what, kind, got):
        self.refusals.append((what, kind, got, self.decision_ts))
        raise LeakRefusal("D-057: %s (%s) not available at decision_ts %d: %s"
                          % (what, kind, self.decision_ts, got))
