#!/usr/bin/python3
"""PORT M0 censuses — shared substrate accessors (spec §6-§10 support module).

This module carries NO census formula.  It holds only the things every census
needs: the frozen-spec pin, receipt readers bound to the EXACT array names the
s2/s3 substrate writes, deterministic quantile/rank helpers, and the TSV writer
that stamps the census spec sha (§11.5).

Substrate binding (never guessed — read off engine/port_m0/s3_sessions.py and
engine/port_m0/s2_decode.py):

  session receipt  m0/sessions/{ASSET}/{YYYYMMDD}.npz
      g{slot}_bid_px g{slot}_ask_px g{slot}_bid_sz g{slot}_ask_sz
      g{slot}_state g{slot}_upd_count g{slot}_mid g{slot}_spread_usd g{slot}_iid
      phase_tag  trades_sec trades_px trades_size trades_side  meta_json
      slot 0 is ALWAYS the session-dominant instrument; slot 1 (HG/NKD roll
      windows only) is the runner-up.  Every census reads slot 0 only, which is
      what makes "never compute across an instrument change" (§7/§9) true by
      construction: within one session slot 0 is one instrument, and the other
      instrument's time simply shows up as non-TWO_SIDED seconds.

  day receipt      m0/receipts/{ASSET}/{YYYYMMDD}.npz
      tracked_ids bid_px ask_px bid_sz ask_sz state upd_count
      trades_* tally_iid tally_updates tally_trades tally_trade_size_sum
      map_iid map_symbol map_outright carry_* meta_json

  phases_{ASSET}.json   years -> boundaries_utc_sec
  bars_{ASSET}.tsv      trade_date .. ATR14_prev_usd ..
"""
import datetime as dt
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

# --------------------------------------------------------------- spec pin ---
# The frozen spec identity for the census lane (§6-§10 + CC-M0-1).  common.py
# still pins the PRE-CC-M0-1 sha (b921566ef3a28dea); see the lane report.
SPEC_SHA16 = "8b0a000ab822c726"

PHASE_NAMES = ("TOKYO", "LONDON", "NY")
N_PHASES = 3

# §1 gate constants — pre-registered, never tuned.
GATE_COST_GREEN = 0.10          # cost_rt / $1,000
GATE_COST_CAUTION = 0.20
GATE_OFFER_FLOOR = 2500.0       # $/day median, full Globex session
GATE_SEATABLE_FLOOR = 2500.0    # $/day median
GATE_RECALL = 0.95
INSUFFICIENT_BOOK_FRAC = 0.30   # §6 excluded_frac above this -> no verdict

WINNER_MFE = 1000.0             # §1 wall fit: winners = unwalled MFE >= $1,000
WALL_CAP = 900.0                # §1 wall($) = min(round_$25(p99), $900)
WALL_ROUND = 25.0
WALL_FIT_YEARS = (2021, 2022, 2023, 2024)   # §8 sub-pass 2: 2025 excluded

RUNGS = (0.075, 0.11, 0.15)     # §1 ZigZag rungs x ATR14($)
RUNG_FLOOR_TICKS = 4            # §1 floor: max(4 x tick_$, 2 x phase median spread_$)
RUNG_FLOOR_SPREAD_MULT = 2
ORACLE_RUNG = 1.0               # §9 oracle ZigZag threshold x ATR14($)
ORACLE_LEG_MIN = 1500.0         # §9 legs >= $1,500
ORACLE_TOP_K = 2                # §9 top-2 by |$ travel| per session
RECALL_THRESHOLDS = (900.0, 1000.0, 1100.0)   # §9 primary 1000 + sensitivity
RECALL_PRIMARY = 1000.0
TRADABLE_SPREAD_MULT = 2.0      # §9 spread_at_decision <= 2 x phase median

DECISION_LAG = 60               # §1/D-033 decision_sec = confirmation_sec + 60
LEG_1K = 1000.0                 # §7 legs count / §8 $1k-class threshold
HORIZON_MARKS = (1800, 3600, 7200)            # §8 30m / 60m / 120m

# §7 windows.  RTH is the committed fixed [14:30, 21:00) UTC quirk (§3).
WINDOWS = ("FULL", "RTH", "TOKYO", "LONDON", "NY")

# ---------------------------------------------------------------- eras ------
# SPEC DEFECT (reported): "era" is used in §6/§7/§8/§9 but never defined, and no
# companion charter defining it exists in the repo.  The only era statements the
# spec itself makes are "era thinness table (year x median offer)" (§7) and
# "2025 ... is a gate-evaluation era" (§8 sub-pass 2).  This lane therefore emits
# era rows for exactly those two readings and nothing invented: each calendar
# year, the wall-fit block 2021-2024, the gate-evaluation block 2025, and ALL.
ERA_FIT = "FIT_2021_2024"
ERA_GATE = "GATE_2025"
ERA_ALL = "ALL"


def eras_of(year):
    """Every era bucket a session-year belongs to (deterministic order)."""
    out = [str(year)]
    if year in WALL_FIT_YEARS:
        out.append(ERA_FIT)
    elif year == 2025:
        out.append(ERA_GATE)
    out.append(ERA_ALL)
    return out


# ------------------------------------------------------------ spec guard ----
def verify_spec():
    got = C.spec_sha()[:16]
    if got != SPEC_SHA16:
        raise RuntimeError("census spec sha16 %s != frozen %s" % (got, SPEC_SHA16))
    return got


def write_tsv(path, section, phash, columns, rows, extra=()):
    """§11.5 header comments naming spec section + params_hash, census spec sha."""
    tmp = path + ".tmp"
    lines = ["# PORT_M0_CENSUS_SPEC.md %s (spec_sha16=%s)" % (section, SPEC_SHA16),
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
    if isinstance(v, float):
        if not np.isfinite(v):
            return ""
        return "%.6f" % v
    return str(v)


def out_path(root, *parts):
    p = os.path.join(root, *parts)
    d = os.path.dirname(p)
    if d:
        os.makedirs(d, exist_ok=True)
    return p


# ------------------------------------------------------------ statistics ----
def pct(a, q):
    """Deterministic percentile: numpy linear interpolation, NaN on empty."""
    a = np.asarray(a, dtype=np.float64)
    a = a[np.isfinite(a)]
    if a.size == 0:
        return float("nan")
    return float(np.percentile(a, q))


def med(a):
    return pct(a, 50)


def mean(a):
    a = np.asarray(a, dtype=np.float64)
    a = a[np.isfinite(a)]
    return float(a.mean()) if a.size else float("nan")


def hist_quantile(hist, q):
    """Exact quantile of an integer-keyed count histogram (q in 0..100).

    Used for pooled per-(asset,year,phase) spread quantiles: spreads live on the
    tick grid, so an integer histogram gives the EXACT population quantile
    without holding tens of millions of seconds in memory.  Convention matches
    numpy's linear interpolation on the sorted population.
    """
    keys = sorted(hist)
    if not keys:
        return float("nan")
    counts = np.array([hist[k] for k in keys], dtype=np.int64)
    n = int(counts.sum())
    if n == 0:
        return float("nan")
    pos = (n - 1) * (q / 100.0)
    lo_i = int(math.floor(pos))
    hi_i = int(math.ceil(pos))
    cum = np.cumsum(counts)
    lo_v = keys[int(np.searchsorted(cum, lo_i, side="right"))]
    hi_v = keys[int(np.searchsorted(cum, hi_i, side="right"))]
    if lo_i == hi_i:
        return float(lo_v)
    return float(lo_v + (hi_v - lo_v) * (pos - lo_i))


def rankdata(x):
    """Average-tie ranks (Spearman support); stable and RNG-free."""
    x = np.asarray(x, dtype=np.float64)
    n = x.size
    order = np.argsort(x, kind="stable")
    ranks = np.empty(n, dtype=np.float64)
    sx = x[order]
    i = 0
    while i < n:
        j = i
        while j + 1 < n and sx[j + 1] == sx[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + 1 + j + 1) / 2.0
        i = j + 1
    return ranks


def pearson(a, b):
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    m = np.isfinite(a) & np.isfinite(b)
    if m.sum() < 3:
        return float("nan"), int(m.sum())
    a, b = a[m], b[m]
    if a.std() == 0 or b.std() == 0:
        return float("nan"), int(m.sum())
    return float(np.corrcoef(a, b)[0, 1]), int(m.sum())


def spearman(a, b):
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    m = np.isfinite(a) & np.isfinite(b)
    if m.sum() < 3:
        return float("nan"), int(m.sum())
    return pearson(rankdata(a[m]), rankdata(b[m]))


def round_half_up(x, step):
    """HALF-UP rounding onto a grid (§1: thresholds rounded HALF-UP to ticks)."""
    if not np.isfinite(x):
        return float("nan")
    return math.floor(x / step + 0.5) * step


# ------------------------------------------------------ session accessors ---
class Session(object):
    """Slot-0 (dominant instrument) view of one session receipt."""

    __slots__ = ("asset", "trade_date", "year", "path", "meta", "n", "mid",
                 "spread_usd", "state", "bid_sz", "ask_sz", "phase_tag",
                 "valid", "vt", "vm", "iid")

    @property
    def roll_window(self):
        return bool(self.meta.get("roll_window", False))

    @property
    def dying_book_week(self):
        return bool(self.meta.get("dying_book_week", False))

    @property
    def instrument_change(self):
        return bool(self.meta.get("instrument_change", False))

    @property
    def dominant_share(self):
        v = self.meta.get("dominant_share")
        return float(v) if v is not None else float("nan")


def session_paths(asset, root=None):
    """(trade_date, path) for every session receipt, sorted by date.

    Read from sessions_index_{ASSET}.tsv when present (the §5 receipt), else by
    directory listing — both sorted, so the order is identical either way.
    """
    root = root or C.OUT_ROOT
    idx = os.path.join(root, "sessions_index_%s.tsv" % asset)
    out = []
    if os.path.exists(idx):
        with open(idx) as fh:
            for line in fh:
                if line.startswith("#") or line.startswith("trade_date\t"):
                    continue
                f = line.rstrip("\n").split("\t")
                out.append((dt.date.fromisoformat(f[0]), f[7]))
    else:
        d = os.path.join(root, "sessions", asset)
        if os.path.isdir(d):
            for n in sorted(os.listdir(d)):
                if n.endswith(".npz"):
                    out.append((dt.date(int(n[0:4]), int(n[4:6]), int(n[6:8])),
                                os.path.join(d, n)))
    return sorted(out)


def load_session(asset, trade_date, path):
    z = np.load(path, allow_pickle=False)
    s = Session()
    s.asset = asset
    s.trade_date = trade_date
    s.year = trade_date.year
    s.path = path
    s.meta = json.loads(str(z["meta_json"]))
    mid = z["g0_mid"]
    ph = z["phase_tag"]
    # DST-safe: s3 sizes the grids from (close_utc - open_utc) but the phase tag
    # from a fixed 23h span; clip to the shorter so every array aligns.
    n = int(min(len(mid), len(ph)))
    s.n = n
    s.mid = mid[:n]
    s.spread_usd = z["g0_spread_usd"][:n]
    s.state = z["g0_state"][:n]
    s.bid_sz = z["g0_bid_sz"][:n]
    s.ask_sz = z["g0_ask_sz"][:n]
    s.phase_tag = ph[:n]
    s.iid = int(z["g0_iid"])
    z.close()
    s.valid = (s.state == C.ST_TWO_SIDED)
    s.vt = np.nonzero(s.valid)[0].astype(np.int64)
    s.vm = s.mid[s.vt]
    return s


def rth_mask(session):
    """[52200, 75600) UTC seconds-of-day over session seconds (§3/§7)."""
    o = int(session.meta["open_utc"])
    sod = (o + np.arange(session.n, dtype=np.int64)) % 86400
    return (sod >= C.RTH_LO_SEC) & (sod < C.RTH_HI_SEC)


def window_mask(session, window):
    if window == "FULL":
        return np.ones(session.n, dtype=bool)
    if window == "RTH":
        return rth_mask(session)
    return session.phase_tag == PHASE_NAMES.index(window)


def next_phase_boundary(session, sec):
    """First session-second strictly after `sec` whose phase differs; else the
    session's last second (§8 sub-pass 3 'next phase boundary / session close')."""
    p = int(session.phase_tag[sec])
    tail = session.phase_tag[sec + 1:]
    w = np.nonzero(tail != p)[0]
    if w.size:
        return int(sec + 1 + w[0])
    return session.n - 1


# ---------------------------------------------------------------- bars ------
def load_bars(asset, root=None):
    """trade_date -> {'ATR14_prev_usd', 'ATR14_usd', 'H', 'L', 'C', ...}."""
    root = root or C.OUT_ROOT
    p = os.path.join(root, "bars_%s.tsv" % asset)
    out = {}
    if not os.path.exists(p):
        return out
    cols = None
    with open(p) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if cols is None:
                cols = f
                continue
            r = dict(zip(cols, f))
            d = dt.date.fromisoformat(r["trade_date"])
            out[d] = {
                "ATR14_prev_usd": _f(r.get("ATR14_prev_usd")),
                "ATR14_usd": _f(r.get("ATR14_usd")),
                "H": _f(r.get("H")), "L": _f(r.get("L")), "C": _f(r.get("C")),
                "dominant_id": int(r["dominant_id"]),
                "instrument_change": r.get("instrument_change") == "1",
            }
    return out


def _f(v):
    if v is None or v == "":
        return float("nan")
    try:
        return float(v)
    except ValueError:
        return float("nan")


def load_phases(asset, root=None):
    root = root or C.OUT_ROOT
    p = os.path.join(root, "phases_%s.json" % asset)
    if not os.path.exists(p):
        return {}
    with open(p) as fh:
        return json.load(fh)


# ------------------------------------------------------------- day receipts -
def day_paths(asset, root=None):
    root = root or C.OUT_ROOT
    d = os.path.join(root, "receipts", asset)
    out = []
    if os.path.isdir(d):
        for n in sorted(os.listdir(d)):
            if n.endswith(".npz"):
                out.append((dt.date(int(n[0:4]), int(n[4:6]), int(n[6:8])),
                            os.path.join(d, n)))
    return out


def load_day_dominant(asset, path):
    """UTC-day convention (§3/§7): the day's update-count winner among OUTRIGHTS
    (the program-mode variant of the s1-pinned R1 rule, §5/CC-M0-1).

    Returns (iid, mid_array_over_86400_with_NaN, ok_flag) or (None, None, flag).
    """
    z = np.load(path, allow_pickle=False)
    tally_iid = z["tally_iid"]
    tally_upd = z["tally_updates"]
    map_iid = z["map_iid"]
    map_out = z["map_outright"]
    tracked = z["tracked_ids"]
    outr = {int(i): bool(o) for i, o in zip(map_iid.tolist(), map_out.tolist())}
    best, best_n = None, -1
    for i, u in zip(tally_iid.tolist(), tally_upd.tolist()):
        if not outr.get(int(i), False):
            continue
        if u > best_n or (u == best_n and (best is None or int(i) < best)):
            best, best_n = int(i), int(u)
    flag = ""
    if best is None:
        z.close()
        return None, None, "NO_OUTRIGHT"
    w = np.nonzero(tracked == best)[0]
    if not len(w):
        # SI tracks only the top-3 by update count; fall back to the highest
        # update-count TRACKED outright and say so.
        cands = [int(i) for i in tracked.tolist() if outr.get(int(i), False)]
        if not cands:
            z.close()
            return None, None, "DOMINANT_NOT_TRACKED"
        upd = {int(i): int(u) for i, u in zip(tally_iid.tolist(), tally_upd.tolist())}
        best = max(cands, key=lambda i: (upd.get(i, 0), -i))
        w = np.nonzero(tracked == best)[0]
        flag = "DOMINANT_NOT_TRACKED_FALLBACK"
    row = int(w[0])
    st = z["state"][row]
    ts = (st == C.ST_TWO_SIDED)
    mid = np.full(86400, np.nan)
    if ts.any():
        b = z["bid_px"][row][ts].astype(np.float64)
        a = z["ask_px"][row][ts].astype(np.float64)
        mid[ts] = (b + a) / 2 * C.ASSETS[asset]["px_scale"]
    z.close()
    return best, mid, flag


# ------------------------------------------------------------- misc --------
def month_key(d):
    return "%04d-%02d" % (d.year, d.month)


def sha_dir(root, exts=(".tsv", ".npz", ".json", ".md")):
    """sha256 of every output file under `root`, sorted by relative path."""
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for n in sorted(filenames):
            if not n.endswith(exts):
                continue
            p = os.path.join(dirpath, n)
            out.append((os.path.relpath(p, root), C.sha256_file(p)))
    return sorted(out)
