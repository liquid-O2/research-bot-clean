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
SPEC_SHA16 = "44c223198086ac6b"          # FROZEN by orchestrator 2026-08-13

SHEETS_VERSION = "PORT-SHEETS-V1"        # the §1 S1 "sheets-version stamp"

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
# D-071 recalibration (same ~1.15x-of-observed-maximum rule, re-measured on the
# 30-sheet pilot after the class line joined S1 and the class census card joined
# S13): S1 640 -> 720, S13 420 -> 560.  Every other budget is unchanged.
SECTION_BUDGET = {
    "S1": 720, "S2": 260, "S3": 780, "S4": 1100, "S5": 340,
    "S6": 3000, "S7": 240, "S8": 600, "S9": 300, "S10": 340,
    "S11": 180, "S12": 720, "S13": 560, "S14": 760,
}
# Binding whole-sheet cap, not the sum of the parts: a sheet may not spend every
# section's headroom at once.  CC-M2-1.1: 7,400 -> 8,500 with the S6 raise.
SHEET_BUDGET_BLIND = 8500
S6_TOKENS_PER_RAW_SEC = 25               # CC-M2-1.1 exchange rate, on record


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
    return str(v)


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
