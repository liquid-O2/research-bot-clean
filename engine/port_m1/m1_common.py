#!/usr/bin/python3
"""PORT M1 Track B — shared substrate for §2-§6 (+ CC-M1-1).

This module carries NO measurement formula.  It holds the frozen-spec pin, the
M1 output roots, the TSV/JSON writers that stamp the M1 spec sha, the era law,
and the strictly-prior context-series joins.

EVERYTHING else is reused from engine/port_m0 (D-051(2) grandfathered Python
census substrate): common.py (assets, seal, savez_det, receipts), census_common
(session/bar/phase accessors, deterministic statistics), c_a_cost (phase median
spreads, session cost_rt), c_c_roster (zigzag_scan, _emit_candidate skeletons,
certificates, dp_schedule), c_d_recall (oracle legs).  Track B never rewrites
any of them.
"""
import bisect
import csv
import datetime as dt
import json
import os
import sys

import numpy as np

_M0 = "/workspace/engine/port_m0"
if _M0 not in sys.path:
    sys.path.insert(0, _M0)
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import common as C                      # noqa: E402  (m0 substrate)
import census_common as X               # noqa: E402  (m0 census substrate)

# --------------------------------------------------------------- spec pin ---
SPEC_PATH = "/workspace/design/PORT_M1_SPEC.md"
# 65708676a27deae7 (freeze) -> ce0a8ca16e342cd7 (CC-M1-1) -> 418755209f3d08cb
# (CC-M1-3 + D-053 VWAP bands) -> ed126c64eee71c41 (CC-M1-4 mid-sanity, D-054)
SPEC_SHA16 = "3a793af2f6953e2a"
# M1.B (production generation / label tensor / atlas screen).  a3852e13b75464bd
# was the freeze; 2b83f9e70340a413 carried the D-053 VWAP amendment;
# d31f48b59877e44d carries CC-M1-5 (the additive FAST-OPEN family, D13/D14).
SPEC_M1B_PATH = "/workspace/design/PORT_M1B_SPEC.md"
SPEC_M1B_SHA16 = "d31f48b59877e44d"
M1_ROOT = "/workspace/artifacts/cache/port/m1"
M0_ROOT = C.OUT_ROOT

ASSET_ORDER = C.ASSET_ORDER
ERA_FIT = X.ERA_FIT
ERA_GATE = X.ERA_GATE
ERA_ALL = X.ERA_ALL
FIT_YEARS = X.WALL_FIT_YEARS
PHASE_NAMES = X.PHASE_NAMES
N_PHASES = X.N_PHASES

# §4(c) "overnight-before-open" is not in the frozen 3-phase m0 table.  It is
# built here as an ADDITIONAL segment (not a partition member): the session
# seconds strictly before the committed RTH open constant (m0 §3 RTH_LO_SEC =
# 52200 = 14:30 UTC) — the classic overnight-high/low object.  Reported as a
# spec defect (§4(c) names four phases, the frozen table has three).
SEG_NAMES = ("OVERNIGHT", "TOKYO", "LONDON", "NY")
OVERNIGHT_END_SOD = C.RTH_LO_SEC


def spec_sha():
    return C.sha256_file(SPEC_PATH)


def verify_spec():
    got = spec_sha()[:16]
    if got != SPEC_SHA16:
        raise RuntimeError("M1 spec sha16 %s != frozen %s" % (got, SPEC_SHA16))
    X.verify_spec()                     # the m0 spec must also still be frozen
    return got


def spec_m1b_sha():
    return C.sha256_file(SPEC_M1B_PATH)


def verify_spec_m1b():
    """M1.B lanes pin BOTH frozen specs (M1.B implements CC-M1-3 of M1.A)."""
    got = spec_m1b_sha()[:16]
    if got != SPEC_M1B_SHA16:
        raise RuntimeError("M1B spec sha16 %s != frozen %s"
                           % (got, SPEC_M1B_SHA16))
    verify_spec()
    return got


def out_path(*parts):
    p = os.path.join(M1_ROOT, *parts)
    d = os.path.dirname(p)
    if d:
        os.makedirs(d, exist_ok=True)
    return p


def env_receipt(params):
    e = C.env_receipt(params)
    e["m1_spec_sha"] = spec_sha()
    e["m1_spec_sha16"] = SPEC_SHA16
    return e


def write_json(path, obj):
    return C.write_json(path, obj)


def write_tsv(path, section, phash, columns, rows, extra=(), spec="PORT_M1"):
    """Every M1 TSV names its spec section + params_hash + M1 spec sha.

    `spec` selects which frozen spec the section number belongs to: "PORT_M1"
    (M1.A) or "PORT_M1B" (the M1.B stage specs, CC-M1-3 work).
    """
    tmp = path + ".tmp"
    name, sha = (("PORT_M1B_SPEC.md", SPEC_M1B_SHA16) if spec == "PORT_M1B"
                 else ("PORT_M1_SPEC.md", SPEC_SHA16))
    lines = ["# %s %s (spec_sha16=%s)" % (name, section, sha),
             "# params_hash=%s" % phash]
    for e in extra:
        lines.append("# %s" % e)
    lines.append("\t".join(columns))
    with open(tmp, "w") as fh:
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


def d8(d):
    return d.year * 10000 + d.month * 100 + d.day


def d8_to_date(n):
    n = int(n)
    return dt.date(n // 10000, (n // 100) % 100, n % 100)


def eras_of(year):
    return X.eras_of(year)


def is_fit(year):
    return int(year) in FIT_YEARS


# --------------------------------------------------- context series (§3) ----
class PriorSeries(object):
    """A daily context series joined STRICTLY PRIOR to a trade date.

    value_before(d) returns the last observation whose observation date is < d
    (never == d): the series is a daily close published after our session's
    information cutoff would otherwise be ambiguous, so the join is strict.
    """

    __slots__ = ("name", "dates", "values", "_keys")

    def __init__(self, name, pairs):
        pairs = sorted(pairs)
        self.name = name
        self.dates = [p[0] for p in pairs]
        self.values = [p[1] for p in pairs]
        self._keys = self.dates

    def __len__(self):
        return len(self.dates)

    def value_before(self, d):
        i = bisect.bisect_left(self._keys, d)
        if i == 0:
            return float("nan")
        return self.values[i - 1]

    def date_before(self, d):
        i = bisect.bisect_left(self._keys, d)
        return self.dates[i - 1] if i else None


CONTEXT_DIR = "/workspace/artifacts/reference/port_context"
CONTEXT_FILES = {"SI": ("GVZ", os.path.join(CONTEXT_DIR, "FRED_GVZCLS.csv")),
                 "NKD": ("NIKKEI_VI", os.path.join(CONTEXT_DIR,
                                                   "NIKKEI_VI_daily.csv")),
                 "HG": (None, None)}


def load_context(asset):
    """§3 context: SI -> GVZ close, NKD -> Nikkei VI close, HG -> none."""
    name, path = CONTEXT_FILES[asset]
    if name is None:
        return None
    pairs = []
    # NIKKEI_VI_daily.csv carries a non-UTF-8 copyright footer; the numeric
    # rows are pure ASCII, so decode leniently and let the row filter drop it.
    with open(path, newline="", encoding="utf-8", errors="replace") as fh:
        rd = csv.reader(fh)
        header = next(rd)
        for row in rd:
            if not row or len(row) < 2:
                continue
            ds, vs = row[0].strip().strip('"'), row[1].strip().strip('"')
            ds = ds.replace("/", "-")
            if len(ds) != 10 or not ds[:4].isdigit():
                continue            # trailing copyright/footer lines
            try:
                d = dt.date.fromisoformat(ds)
                v = float(vs)
            except ValueError:
                continue
            if d.year >= 2026:      # seal-consistent: never join 2026 rows
                continue
            pairs.append((d, v))
    return PriorSeries(name, pairs)


# ------------------------------------------------------------ statistics ----
med = X.med
mean = X.mean
pct = X.pct
round_half_up = X.round_half_up


def mad(a):
    """Median absolute deviation (robust z support, §6 G3)."""
    a = np.asarray(a, dtype=np.float64)
    a = a[np.isfinite(a)]
    if a.size == 0:
        return float("nan")
    m = np.median(a)
    return float(np.median(np.abs(a - m)))


def run_lengths(mask):
    """Length of the run of True ending at each position (vectorised, causal)."""
    mask = np.asarray(mask, dtype=bool)
    n = mask.size
    if n == 0:
        return np.zeros(0, dtype=np.int64)
    idx = np.arange(n, dtype=np.int64)
    last_false = np.maximum.accumulate(np.where(~mask, idx, -1))
    return idx - last_false


def hb(msg):
    C.hb(msg)
