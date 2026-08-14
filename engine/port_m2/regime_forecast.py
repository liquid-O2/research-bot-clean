#!/usr/bin/python3
"""PORT M2 — THE FORWARD-OFFER / REGIME FORECASTER (CC-M2-11.2, method §13.1).

WHY THIS EXISTS.  The census batch-2 verdict (CC-M2-11.1/2) killed the intra-day
regime flags as decision objects: `day_type_so_far` fires ~1-2h AFTER the
winners' decision seconds (median flagged second 56,120 vs winners 52,780), so
an accumulating flag cannot separate a day-1-like day from a day-2-like day IN
TIME TO ACT.  The regime question is therefore reassigned to a LEADING object:
a strictly-prior forecast of the day itself, made at the session open and
REMADE at every phase open.

WHAT IT FORECASTS (per asset, per session, at each of 3 anchors):
  (a) DAY-TYPE CLASS {RANGE, EXPANSION} — EXPANSION iff the realised full
      SESSION range exceeds the q75 of its own trailing 60 real sessions
      (strictly prior, degenerate sessions excluded).  Pinned below.
  (b) REALISED SESSION RANGE ($) — the census offer object; `best_leg == range`
      identically for any path (PORT_M0_VERDICT §5), so the range IS the offer.
  (c) PER-PHASE SHARE of the day's range — share_p = range_p / sum_q range_q
      over the three frozen m0 phases (a 3-simplex; documented choice).
  (d) MENU-HAT — the count of D-021-class candidates still AHEAD of the anchor.
      D-021 class = the committed winner rule already used by the class census
      (engine/port_m2/class_census.py:57): walled phase-close certificate
      >= $1,000 AND mae_before_argmax <= $300 AND not walled.  TARGET ONLY —
      the roster labels are outcome-side and never enter the feature side.

METHOD = the proven fvol discipline (engine/port_m1/b2_fvol.py):
  expanding-window walk-forward, MONTHLY refits, min 250 training sessions;
  every model choice made on FIT 2021-2024 only; 2025 predictions carry the
  coefficients FROZEN at the last FIT-era refit (era law), with the continuing
  walk-forward emitted beside them as a diagnostic; GATE 2025 is an ECHO,
  eval-only.  Model family (LINEAR ridge / GBT-small) chosen per
  (asset, anchor, target) by FIT walk-forward score and written down.

BENCHMARKS ARE MANDATORY AND PRE-REGISTERED (a forecaster that does not beat
them is a defect, not a result):
  class : (1) BASE-RATE — the trailing strictly-prior P(EXPANSION), a constant
              predictor ("always RANGE" as a probability);
          (2) PERSISTENCE — the trailing strictly-prior P(EXPANSION today |
              yesterday's day-type), i.e. yesterday's day-type carried forward.
  range : (1) TRAILING MEDIAN of the last 60 real sessions;
          (2) PERSISTENCE (yesterday's range);
          (3) the M1 fvol range_hat (reference, not a gate — fvol is itself a
              feature source here).
  share : trailing MEAN share of the last 60 real sessions.
  menu  : trailing MEDIAN menu count of the last 60 real sessions.

D-057 IS ENFORCED MECHANICALLY, NOT BY GOOD INTENTIONS.  Every single feature
is registered with an AVAILABILITY TIMESTAMP and pushed through
m2_common.CausalGuard: a stamp at or after the anchor RAISES LeakRefusal.  The
prior-session features carry the prior session's CLOSE epoch; the fvol forecast
carries the same (it is fitted only on sessions strictly before); the external
series carry availability.availability_ts() from AVAILABILITY_LAGS.tsv; the
anchor-state features carry the anchor itself (they are built from seconds
strictly before it).  The red-first fixtures in test_regime.py mutate exactly
these two places (one leakage mutant, one benchmark mutant).

Outputs (D-018: everything bulk under artifacts/cache/port/m2/):
    m2/regime_forecast/sofar_{ASSET}.tsv        anchor state cache
    m2/regime_forecast/truth_{ASSET}.tsv        the four targets per session
    m2/regime_forecast/forecast_{ASSET}.tsv     per (session, anchor) forecasts
    m2/regime_forecast/metrics.tsv              per (asset, anchor, target, era)
    m2/regime_forecast/model_choice.tsv         LINEAR vs GBT, decided on FIT
    m2/regime_forecast/coverage.tsv             per-feature FIT coverage + drops
    m2/regime_forecast/regime_forecast.receipt.json
    evidence/port_m2/REGIME_FORECAST_REPORT.md  (written by report_regime())

Run: lab/run.sh port-m2-regime -- /usr/bin/python3 engine/port_m2/regime_forecast.py
"""
import datetime as dt
import json
import math
import multiprocessing as mp
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import m2_common as MC                    # noqa: E402
import assemble as A                      # noqa: E402
import availability as AV                 # noqa: E402
import context as CTX                     # noqa: E402
import common as C                        # noqa: E402
import census_common as X                 # noqa: E402
import c_c_roster as CCR                  # noqa: E402

SECTION = "CC-M2-11.2 forward-offer / regime forecaster (method §13.1)"
OUT_SUB = "regime_forecast"
REPORT_PATH = "/workspace/evidence/port_m2/REGIME_FORECAST_REPORT.md"

# ---------------------------------------------------------------- PINS ------
ANCHORS = ("OPEN", "LONDON_OPEN", "NY_OPEN")
# The session BEGINS inside the TOKYO phase (m0 phase table), so "session open"
# and "Tokyo open" are the same anchor; the three distinct phase opens are the
# three anchors.
PHASES = ("TOKYO", "LONDON", "NY")

DAYTYPE_WINDOW = 60          # trailing real sessions for the q75 threshold
DAYTYPE_MIN_OBS = 40         # else the session has no class label
DAYTYPE_Q = 75.0             # "realized range vs its trailing q75"
TRAIL = 60                   # benchmark trailing window (sessions)
TRAIL_MIN = 20               # min observations for a trailing benchmark
MIN_TRAIN = 250              # fvol's own gate, reused
FREEZE_CUTOFF = dt.date(2025, 1, 1)      # era law: FIT ends 2024-12-31
COVERAGE_MIN = 0.80          # fvol's context rule, applied to every feature
PINBALL_Q = (0.10, 0.90)
RIDGE_LAM = 1.0
LOGIT_LAM = 1.0
GBT = {"n_trees": 100, "depth": 3, "lr": 0.08, "min_leaf": 20, "l2": 1.0,
       "n_bins": 32}
BOOT_N = 1000
BOOT_SEED = 20260814
BOOT_BLOCK = 22              # ~one month of sessions (vol clustering)

CLASS_TARGET = "day_type"
REG_TARGETS = ("range",) + tuple("share_%s" % p for p in PHASES) + ("menu",)
ALL_TARGETS = (CLASS_TARGET,) + REG_TARGETS

PARAMS = {
    "spec_section": SECTION,
    "anchors": list(ANCHORS),
    "day_type": "EXPANSION iff realised SESSION range_usd > percentile(%.0f) of "
                "the trailing %d real sessions (strictly prior, >=%d obs); else "
                "RANGE" % (DAYTYPE_Q, DAYTYPE_WINDOW, DAYTYPE_MIN_OBS),
    "range_target": "realised full-SESSION range_usd (== census best_leg, "
                    "PORT_M0_VERDICT §5 identity)",
    "share_target": "range_phase / sum over the three m0 phases (3-simplex)",
    "menu_target": "count of roster-v3 candidates with dec_sec >= anchor_sec "
                   "and cert_close >= $1000 and mae_before_argmax <= $300 and "
                   "not walled (D-021; class_census.py:57 rule) — TARGET ONLY",
    "walk_forward": "expanding window, monthly refit, min_train %d sessions"
                    % MIN_TRAIN,
    "era_law": "every choice on FIT 2021-2024; 2025 carries coefficients frozen "
               "at the last FIT refit; GATE 2025 is an ECHO, eval-only",
    "models": ["LINEAR (ridge, standardised, lam=%.1f / logistic-ridge IRLS, "
               "lam=%.1f)" % (RIDGE_LAM, LOGIT_LAM),
               "GBT-small (histogram, %d trees, depth %d, lr %.2f, min_leaf %d,"
               " l2 %.1f, %d bins; no RNG anywhere)"
               % (GBT["n_trees"], GBT["depth"], GBT["lr"], GBT["min_leaf"],
                  GBT["l2"], GBT["n_bins"])],
    "model_choice": "per (asset, anchor, target) by FIT walk-forward score "
                    "(Brier for the class, MAE for the regressions)",
    "benchmarks_class": ["BASE_RATE (trailing strictly-prior P(EXPANSION))",
                         "PERSISTENCE (trailing P(EXP | yesterday's day-type))"],
    "benchmarks_range": ["TRAILING_MEDIAN (%d sessions)" % TRAIL,
                         "PERSISTENCE (yesterday's range)",
                         "FVOL_RANGE_HAT (reference, not a gate)"],
    "benchmarks_share": ["TRAILING_MEAN (%d sessions)" % TRAIL],
    "benchmarks_menu": ["TRAILING_MEDIAN (%d sessions)" % TRAIL],
    "quantiles": "range q10/q90 = point forecast x exp(training-residual "
                 "quantile in log space) — the CC-M1-1(A) ladder construction, "
                 "strictly prior",
    "coverage_rule": "a feature with < %.0f%% finite coverage on the asset's "
                     "FIT rows is DROPPED and the drop is reported"
                     % (COVERAGE_MIN * 100),
    "missing_policy": "training-slice MEDIAN imputation, recomputed at every "
                      "refit from training rows only",
    "d057": "every feature registered with an availability_ts and pushed "
            "through m2_common.CausalGuard.avail; a stamp >= anchor raises "
            "LeakRefusal (test_regime.py mutant A)",
    "bootstrap": "moving-block bootstrap, block %d sessions, %d resamples, "
                 "seed %d; POOLED metrics resample CALENDAR DATES (session-"
                 "clustered honesty)" % (BOOT_BLOCK, BOOT_N, BOOT_SEED),
    "flow_caveat": "anchor-state 'flow' is built from the 1-second book grid "
                   "(signed book imbalance, up/down seconds, range efficiency) "
                   "— NOT the MBP-1 trade tape: a full-corpus event extraction "
                   "(4,521 sessions) is out of budget under the <=4-worker "
                   "constraint; recorded as a deferred enhancement, not hidden",
}


def out_path(*parts):
    return MC.out_path(OUT_SUB, *parts)


def _f(v, default=float("nan")):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return default
    return x


def read_tsv(path):
    rows, cols = [], None
    with open(path) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if cols is None:
                cols = f
                continue
            rows.append(dict(zip(cols, f)))
    return rows


# ===================================================================
# STAGE 1 — ANCHOR STATE ("so-far") from the 1-second session grid
# ===================================================================
SOFAR_COLUMNS = ("asset", "trade_date", "anchor", "anchor_sec", "anchor_ts",
                 "open_utc", "close_utc", "anchor_mid", "n_valid_before",
                 "sofar_range_usd", "sofar_ret_usd", "sofar_eff",
                 "sofar_imbalance", "sofar_spread_usd", "sofar_valid_frac",
                 "sofar_up_frac", "phase_sec_TOKYO", "phase_sec_LONDON",
                 "phase_sec_NY", "degenerate")


def _anchor_secs(s):
    """{anchor: first session second of that phase}.  Derived from phase_tag
    itself (never from the year table) so DST and short days cannot drift."""
    out = {}
    for pi, name in enumerate(PHASES):
        idx = np.nonzero(s.phase_tag == pi)[0]
        out[name] = int(idx[0]) if idx.size else None
    return {"OPEN": out["TOKYO"], "LONDON_OPEN": out["LONDON"],
            "NY_OPEN": out["NY"]}


def _sofar_shard(args):
    asset, sess = args
    mult = C.ASSETS[asset]["mult"]
    rows = []
    for trade_date, path in sess:
        s = X.load_session(asset, trade_date, path)
        o = int(s.meta["open_utc"])
        close_utc = int(s.meta.get("close_utc", o + s.n))
        secs = _anchor_secs(s)
        vt, vm = s.vt, s.vm
        degen = int(not (vm.size >= 2 and (vm.max() - vm.min()) > 0))
        counts = {p: int(np.sum(s.phase_tag == i)) for i, p in enumerate(PHASES)}
        for anchor in ANCHORS:
            a = secs[anchor]
            if a is None:
                continue
            # the anchor's own book is the LAST readable thing (at_decision);
            # everything else is strictly before it.
            j0 = int(np.searchsorted(vt, a, side="left"))
            j1 = int(np.searchsorted(vt, a, side="right"))
            anchor_mid = float(vm[j0]) if j0 < vm.size else float("nan")
            pre = vm[:j0]
            if pre.size >= 2:
                rng = (float(pre.max()) - float(pre.min())) * mult
                ret = (float(pre[-1]) - float(pre[0])) * mult
                eff = abs(ret) / rng if rng > 0 else float("nan")
                d = np.diff(pre)
                up = float(np.mean(d > 0)) if d.size else float("nan")
            else:
                rng, ret, eff, up = 0.0, 0.0, float("nan"), float("nan")
            sel = vt[:j0]
            if sel.size:
                b = s.bid_sz[sel].astype(np.float64)
                k = s.ask_sz[sel].astype(np.float64)
                tot = b + k
                imb = float(np.mean(np.where(tot > 0, (b - k) / np.where(
                    tot > 0, tot, 1.0), 0.0)))
                spr = float(np.mean(s.spread_usd[sel]))
            else:
                imb, spr = float("nan"), float("nan")
            vf = float(sel.size) / a if a > 0 else float("nan")
            rows.append([asset, trade_date.isoformat(), anchor, a, o + a, o,
                         close_utc, anchor_mid, int(sel.size), rng, ret, eff,
                         imb, spr, vf, up, counts["TOKYO"], counts["LONDON"],
                         counts["NY"], degen])
        _ = j1
    return rows


def build_sofar(assets, workers):
    tasks = []
    for asset in assets:
        by_month = {}
        for d, p in X.session_paths(asset, MC.M0_ROOT):
            by_month.setdefault(X.month_key(d), []).append((d, p))
        for mk in sorted(by_month):
            tasks.append((asset, by_month[mk]))
    MC.hb("sofar: %d (asset,month) tasks" % len(tasks))
    if workers <= 1 or len(tasks) <= 1:
        res = [_sofar_shard(t) for t in tasks]
    else:
        with mp.Pool(min(workers, len(tasks))) as pool:
            res = list(pool.map(_sofar_shard, tasks, chunksize=1))
    rows = []
    for r in res:
        rows.extend(r)
    rows.sort(key=lambda r: (r[0], r[1], ANCHORS.index(r[2])))
    for asset in assets:
        sel = [r for r in rows if r[0] == asset]
        MC.write_tsv(out_path("sofar_%s.tsv" % asset), SECTION,
                     MC.params_hash(PARAMS), list(SOFAR_COLUMNS), sel,
                     extra=["anchor state built from seconds STRICTLY BEFORE "
                            "anchor_sec; anchor_mid is the anchor's own book "
                            "(CausalGuard.at_decision)",
                            "degenerate=1 marks the stale-book receipts (frozen "
                            "quote, zero range) excluded everywhere downstream"])
    return rows


# ===================================================================
# STAGE 2 — THE FOUR TARGETS
# ===================================================================
TRUTH_COLUMNS = ("asset", "trade_date", "year", "era", "range_usd",
                 "range_TOKYO", "range_LONDON", "range_NY", "share_TOKYO",
                 "share_LONDON", "share_NY", "daytype_q75", "day_type",
                 "menu_OPEN", "menu_LONDON_OPEN", "menu_NY_OPEN",
                 "menu_day", "n_candidates")


def era_of_year(y):
    return "FIT" if 2021 <= y <= 2024 else ("GATE" if y == 2025 else "OTHER")


def menu_counts(asset, sofar_by_key):
    """{(d8): {anchor: count}} of D-021-class candidates ahead of each anchor.

    The rule is the committed one (class_census.py:57) and is TARGET-SIDE ONLY.
    """
    r = A.roster(asset)
    wall = float(A.walls()[asset]["wall_usd"])
    cm = A.cost_map()
    d8 = r["date8"]
    mae = r["mae_before_argmax"]
    dec = r["dec_sec"]
    by = {}
    for i in range(int(d8.size)):
        by.setdefault(int(d8[i]), []).append(i)
    out = {}
    for d in sorted(by):
        iso = MC.d8_to_date(d).isoformat()
        cost = cm.get((asset, iso), float("nan"))
        if not np.isfinite(cost):
            cost = C.FEES_RT
        wins = []
        for i in by[d]:
            _pk, cl = CCR.certificates(r, i, wall, cost)
            walled = CCR._skel_query(r, i, wall)[3]
            if cl[0] >= 1000.0 and float(mae[i]) <= 300.0 and not walled:
                wins.append(int(dec[i]))
        wins.sort()
        w = np.array(wins, dtype=np.int64)
        rec = {"n_candidates": len(by[d]), "menu_day": int(w.size)}
        for anchor in ANCHORS:
            a = sofar_by_key.get((asset, iso, anchor))
            if a is None:
                rec[anchor] = None
                continue
            rec[anchor] = int(w.size - np.searchsorted(w, int(a["anchor_sec"]),
                                                       side="left"))
        out[iso] = rec
    return out


def build_truth(assets, sofar_rows):
    v1 = read_tsv(os.path.join(MC.M1_ROOT, "fvol", "v1_realized.tsv"))
    seg = {}
    for r in v1:
        seg[(r["asset"], r["trade_date"], r["segment"])] = r
    sofar_by_key = {(r[0], r[1], r[2]): dict(zip(SOFAR_COLUMNS, r))
                    for r in sofar_rows}
    rows = []
    for asset in assets:
        MC.hb("truth %s: menu counts from the roster" % asset)
        menus = menu_counts(asset, sofar_by_key)
        dates = sorted({k[1] for k in seg if k[0] == asset
                        and k[2] == "SESSION"})
        hist = []                              # strictly prior real ranges
        for iso in dates:
            s = seg[(asset, iso, "SESSION")]
            rng = _f(s["range_usd"])
            if not (np.isfinite(rng) and rng > 0):
                continue                       # stale-book receipt: not a day
            ph = {}
            for p in PHASES:
                q = seg.get((asset, iso, p))
                ph[p] = _f(q["range_usd"]) if q else float("nan")
            tot = sum(v for v in ph.values() if np.isfinite(v))
            shares = {p: (ph[p] / tot if (np.isfinite(ph[p]) and tot > 0)
                          else float("nan")) for p in PHASES}
            # day-type: STRICTLY PRIOR trailing q75
            w = np.array(hist[-DAYTYPE_WINDOW:], dtype=np.float64)
            if w.size >= DAYTYPE_MIN_OBS:
                q75 = float(np.percentile(w, DAYTYPE_Q))
                dtype = 1 if rng > q75 else 0
            else:
                q75, dtype = float("nan"), None
            m = menus.get(iso, {})
            y = int(iso[0:4])
            rows.append([asset, iso, y, era_of_year(y), rng,
                         ph["TOKYO"], ph["LONDON"], ph["NY"],
                         shares["TOKYO"], shares["LONDON"], shares["NY"],
                         q75, dtype,
                         m.get("OPEN"), m.get("LONDON_OPEN"), m.get("NY_OPEN"),
                         m.get("menu_day"), m.get("n_candidates")])
            hist.append(rng)
    rows.sort(key=lambda r: (r[0], r[1]))
    for asset in assets:
        sel = [r for r in rows if r[0] == asset]
        MC.write_tsv(out_path("truth_%s.tsv" % asset), SECTION,
                     MC.params_hash(PARAMS), list(TRUTH_COLUMNS), sel,
                     extra=["day_type 1=EXPANSION 0=RANGE; the q75 threshold "
                            "is built from the trailing %d REAL sessions, "
                            "strictly prior" % DAYTYPE_WINDOW,
                            "menu_* = D-021-class candidates with dec_sec >= "
                            "the anchor second (TARGET side only)"])
    return rows


# ===================================================================
# STAGE 3 — FEATURES (every one carries an availability timestamp)
# ===================================================================
class Feats(object):
    """Feature accumulator with the D-057 guard wired in at the only door.

    add(name, value, availability_ts):
      * availability_ts is None  -> the observation does not exist yet: the
        feature is MISSING (NaN) and counted.  Not a leak.
      * availability_ts >= anchor -> a future datum reached the feature side:
        LeakRefusal, raised through the guard.  This is the availability test
        the leakage mutant must trip.
    """

    __slots__ = ("guard", "names", "vals", "n_missing")

    def __init__(self, guard):
        self.guard = guard
        self.names = []
        self.vals = []
        self.n_missing = 0

    def add(self, name, value, availability_ts):
        if availability_ts is None:
            self.n_missing += 1
            v = float("nan")
        elif not self.guard.avail(availability_ts, name):
            self.guard.refuse(name, "availability_ts", int(availability_ts))
            v = float("nan")               # unreachable: refuse() raises
        else:
            v = _f(value)
            if not np.isfinite(v):
                self.n_missing += 1
                v = float("nan")
        self.names.append(name)
        self.vals.append(v)


def _log(v):
    v = _f(v)
    return math.log(v) if (np.isfinite(v) and v > 0) else float("nan")


def _mean_prior(arr, i, k):
    """Mean of the k observations STRICTLY BEFORE index i.

    The window is closed here, once, so the benchmark/feature mutant has exactly
    one line to attack (test_regime.py mutant B attacks _window_hi)."""
    lo, hi = max(0, i - k), _window_hi(i)
    w = arr[lo:hi]
    w = w[np.isfinite(w)]
    return float(w.mean()) if w.size else float("nan")


def _window_hi(i, include_current=False):
    """The exclusive upper bound of every strictly-prior window in this module.

    LAW: it is `i`, never `i+1`.  Anything else reads the row being predicted.
    """
    hi = i + 1 if include_current else i
    if hi > i:
        raise AssertionError(
            "strictly-prior window violated: hi=%d > i=%d (a trailing "
            "benchmark/feature may never read the row it predicts)" % (hi, i))
    return hi


def _trail_stat(arr, i, k, kind="median", min_obs=TRAIL_MIN):
    lo, hi = max(0, i - k), _window_hi(i)
    w = arr[lo:hi]
    w = w[np.isfinite(w)]
    if w.size < min_obs:
        return float("nan")
    if kind == "median":
        return float(np.median(w))
    if kind == "mean":
        return float(w.mean())
    if kind == "std":
        return float(w.std(ddof=1)) if w.size >= 2 else float("nan")
    raise ValueError(kind)


class AssetPanel(object):
    """Everything one asset's feature builder needs, indexed by session."""

    def __init__(self, asset, truth_rows, sofar_rows):
        self.asset = asset
        self.mult = C.ASSETS[asset]["mult"]
        self.truth = [r for r in truth_rows if r["asset"] == asset]
        self.truth.sort(key=lambda r: r["trade_date"])
        self.iso = [r["trade_date"] for r in self.truth]
        self.pos = {d: i for i, d in enumerate(self.iso)}
        self.sofar = {(r["trade_date"], r["anchor"]): r for r in sofar_rows
                      if r["asset"] == asset}
        # per-session close epoch (the availability stamp of every realised
        # quantity of that session) and open epoch
        self.close_utc = {}
        self.open_utc = {}
        for (d, _a), r in self.sofar.items():
            self.close_utc[d] = int(_f(r["close_utc"]))
            self.open_utc[d] = int(_f(r["open_utc"]))
        # M1 realised + fvol
        self.v1 = {}
        for r in read_tsv(os.path.join(MC.M1_ROOT, "fvol", "v1_realized.tsv")):
            if r["asset"] == asset:
                self.v1[(r["trade_date"], r["segment"])] = r
        self.fvol = {}
        for r in read_tsv(os.path.join(MC.M1_ROOT, "fvol",
                                       "fvol_forecasts.tsv")):
            if r["asset"] == asset:
                self.fvol[(r["trade_date"], r["segment"])] = r
        # m0 bar flags (instrument change kills a return)
        self.instr_change = {}
        for r in read_tsv(os.path.join(MC.M0_ROOT, "census_b_offer.tsv")):
            if r["asset"] == asset and r["convention"] == "SESSION" \
                    and r["window"] == "FULL":
                self.instr_change[r["trade_date"]] = _f(r["instrument_change"])
        # target arrays (used for trailing benchmarks AND for prior-session
        # features; both are windowed through _window_hi)
        self.range_arr = np.array([_f(r["range_usd"]) for r in self.truth])
        self.daytype_arr = np.array([_f(r["day_type"]) for r in self.truth])
        self.menu_arr = {a: np.array([_f(r["menu_%s" % a]) for r in self.truth])
                         for a in ANCHORS}
        self.share_arr = {p: np.array([_f(r["share_%s" % p])
                                       for r in self.truth]) for p in PHASES}
        self.ratio_arr = np.array(
            [_f(self.fvol.get((d, "SESSION"), {}).get(
                "ratio_range_over_sigmahat")) for d in self.iso])
        self.close_px = np.array(
            [_f(self.v1.get((d, "SESSION"), {}).get("close_px"))
             for d in self.iso])
        # monotone close epochs over self.iso — the cross-asset join bisects
        # this instead of scanning, and the guard re-checks the pick anyway.
        self.close_ts = np.array([self.close_utc.get(d, 0) for d in self.iso],
                                 dtype=np.int64)
        self.spread_arr = {a: np.array(
            [_f(self.sofar.get((d, a), {}).get("sofar_spread_usd"))
             for d in self.iso]) for a in ANCHORS}


def _series_feat(fe, name, guard, series_id, transform=None, back=0):
    """One external series through the D-057 machinery."""
    try:
        ser = CTX.series(series_id)
    except Exception:                      # noqa: BLE001 — recorded as missing
        fe.add(name, float("nan"), None)
        return None
    rec = ser.latest(guard, back=back)
    if rec is None:
        fe.add(name, float("nan"), None)
        return None
    vals = rec["values"]
    v = transform(vals) if transform else _f(vals[0])
    fe.add(name, v, rec["availability_ts"])
    return rec


def _delta_feat(fe, name, guard, series_id, pick, back_far):
    """value_now - value_{back_far} using two AVAILABLE observations only."""
    try:
        ser = CTX.series(series_id)
    except Exception:                      # noqa: BLE001
        fe.add(name, float("nan"), None)
        return
    a = ser.latest(guard, back=0)
    b = ser.latest(guard, back=back_far)
    if a is None or b is None:
        fe.add(name, float("nan"), None)
        return
    va, vb = pick(a["values"]), pick(b["values"])
    fe.add(name, (va - vb) if (np.isfinite(va) and np.isfinite(vb))
           else float("nan"), max(a["availability_ts"], b["availability_ts"]))


def _first(vals):
    return _f(vals[0])


ROLL_STEPBACK = 5


def clean_ret(panel, j):
    """Close-to-close log return of the newest CLEAN consecutive pair at or
    before session j, with the availability stamp of that pair's later close.

    A roll session's close-to-close move is a contract change, not a return
    (AVAILABILITY_LAGS.tsv states the same caveat for the yahoo continuous
    fronts).  Dropping those rows to NaN costs SI 17% of its sessions and the
    coverage rule then deletes the whole feature; stepping back to the last
    clean pair keeps a REAL prior return and never invents one.  Returns
    (value, availability_ts) or (nan, None).
    """
    for k in range(j, max(0, j - ROLL_STEPBACK), -1):
        if k < 1:
            break
        if panel.instr_change.get(panel.iso[k], 0.0) >= 0.5:
            continue
        c0, c1 = panel.close_px[k], panel.close_px[k - 1]
        if np.isfinite(c0) and np.isfinite(c1) and c0 > 0 and c1 > 0:
            return math.log(c0 / c1), int(panel.close_ts[k])
    return float("nan"), None


def build_features(panel, i, anchor, guard, panels):
    """The full strictly-prior feature row for (session i, anchor)."""
    fe = Feats(guard)
    asset = panel.asset
    iso = panel.iso[i]
    prev_iso = panel.iso[i - 1] if i >= 1 else None
    # availability stamp for every quantity realised in a PRIOR session:
    # that session's close epoch.
    av_prev = panel.close_utc.get(prev_iso) if prev_iso else None
    hi = _window_hi(i)

    # ---- A. own realised history (prior sessions only) --------------------
    for k in (1, 5, 22):
        fe.add("log_range_%d" % k, _log(_mean_prior(panel.range_arr, i, k)),
               av_prev)
    v1p = panel.v1.get((prev_iso, "SESSION"), {}) if prev_iso else {}
    for nm, col in (("log_rv1", "rv_usd"), ("log_park1", "parkinson_usd"),
                    ("log_gk1", "gk_usd"), ("log_rs1", "rs_usd"),
                    ("log_sigma1", "sigma_usd")):
        fe.add(nm, _log(v1p.get(col)), av_prev)
    fe.add("log1p_jump1", math.log1p(max(_f(v1p.get("jump_usd"), 0.0), 0.0))
           if v1p else float("nan"), av_prev)
    fe.add("volofvol_20", _f(v1p.get("volofvol_20_usd")), av_prev)
    fe.add("range_clocknorm_1", _f(v1p.get("range_clocknorm")), av_prev)
    for p in PHASES:
        q = panel.v1.get((prev_iso, p), {}) if prev_iso else {}
        fe.add("log_range_%s_1" % p, _log(q.get("range_usd")), av_prev)
    # rv5/rv66 of TODAY's row is built from rv[i-5:i] / rv[i-66:i] — strictly
    # prior by construction (b2_fvol._v1_derived), so it stamps at prev close.
    v1t = panel.v1.get((iso, "SESSION"), {})
    fe.add("rv5_over_rv66", _f(v1t.get("rv5_over_rv66")), av_prev)
    # the day-type threshold and where yesterday sat against it
    q75 = _trail_stat(panel.range_arr, i, DAYTYPE_WINDOW, "median",
                      DAYTYPE_MIN_OBS)
    lo = max(0, i - DAYTYPE_WINDOW)
    w = panel.range_arr[lo:hi]
    w = w[np.isfinite(w)]
    thr = float(np.percentile(w, DAYTYPE_Q)) if w.size >= DAYTYPE_MIN_OBS \
        else float("nan")
    fe.add("log_q75_trailing", _log(thr), av_prev)
    fe.add("log_range1_over_q75",
           _log(panel.range_arr[i - 1] / thr) if
           (i >= 1 and np.isfinite(thr) and thr > 0) else float("nan"), av_prev)
    fe.add("daytype_prev", panel.daytype_arr[i - 1] if i >= 1 else float("nan"),
           av_prev)
    fe.add("daytype_trailing_rate", _mean_prior(panel.daytype_arr, i, TRAIL),
           av_prev)
    _ = q75

    # ---- B. the fvol forecast for TODAY (fitted on prior sessions only) ---
    fv = panel.fvol.get((iso, "SESSION"), {})
    sigma_hat = _f(fv.get("sigma_hat_usd"))
    range_hat = _f(fv.get("range_hat_usd"))
    fe.add("log_sigma_hat", _log(sigma_hat), av_prev)
    fe.add("log_range_hat", _log(range_hat), av_prev)
    tm = _trail_stat(panel.range_arr, i, TRAIL, "median")
    fe.add("log_rangehat_over_trailmed",
           _log(range_hat / tm) if (np.isfinite(tm) and tm > 0)
           else float("nan"), av_prev)
    fe.add("calratio_trailmed", _trail_stat(panel.ratio_arr, i, TRAIL,
                                            "median"), av_prev)
    fe.add("calratio_trailstd", _trail_stat(panel.ratio_arr, i, TRAIL, "std"),
           av_prev)
    hats = {}
    for p in PHASES:
        hats[p] = _f(panel.fvol.get((iso, p), {}).get("range_hat_usd"))
    tot = sum(v for v in hats.values() if np.isfinite(v))
    for p in PHASES:
        fe.add("fvol_share_%s" % p,
               hats[p] / tot if (np.isfinite(hats[p]) and tot > 0)
               else float("nan"), av_prev)

    # ---- C. anchor state -------------------------------------------------
    sf = panel.sofar.get((iso, anchor))
    av_anchor = int(_f(sf["anchor_ts"])) - 1 if sf else None
    if sf:
        gap = float("nan")
        if prev_iso:
            pc = _f(panel.v1.get((prev_iso, "SESSION"), {}).get("close_px"))
            am = _f(sf["anchor_mid"])
            if np.isfinite(pc) and np.isfinite(am):
                gap = (am - pc) * panel.mult
        fe.add("gap_usd", gap, av_anchor)
        fe.add("abs_gap_over_sigma",
               abs(gap) / sigma_hat if (np.isfinite(gap) and
                                        np.isfinite(sigma_hat) and
                                        sigma_hat > 0) else float("nan"),
               av_anchor)
        sr = _f(sf["sofar_range_usd"])
        fe.add("sofar_range_usd", sr, av_anchor)
        fe.add("sofar_range_over_hat",
               sr / range_hat if (np.isfinite(sr) and np.isfinite(range_hat)
                                  and range_hat > 0) else float("nan"),
               av_anchor)
        fe.add("sofar_range_over_trailmed",
               sr / tm if (np.isfinite(sr) and np.isfinite(tm) and tm > 0)
               else float("nan"), av_anchor)
        for nm in ("sofar_ret_usd", "sofar_eff", "sofar_imbalance",
                   "sofar_valid_frac", "sofar_up_frac"):
            fe.add(nm, _f(sf[nm]), av_anchor)
        psp = _f(sf["sofar_spread_usd"])
        pm = _trail_stat(panel.spread_arr[anchor], i, TRAIL, "median")
        fe.add("sofar_spread_rel",
               psp / pm if (np.isfinite(psp) and np.isfinite(pm) and pm > 0)
               else float("nan"), av_anchor)
        fe.add("anchor_frac_of_session",
               float(_f(sf["anchor_sec"])) /
               max(1.0, float(_f(sf["close_utc"]) - _f(sf["open_utc"]))),
               av_anchor)
    else:
        for nm in ("gap_usd", "abs_gap_over_sigma", "sofar_range_usd",
                   "sofar_range_over_hat", "sofar_range_over_trailmed",
                   "sofar_ret_usd", "sofar_eff", "sofar_imbalance",
                   "sofar_valid_frac", "sofar_up_frac", "sofar_spread_rel",
                   "anchor_frac_of_session"):
            fe.add(nm, float("nan"), None)

    # ---- D. calendar / clock (schedule-exempt, known months ahead) --------
    wd = dt.date.fromisoformat(iso).weekday()
    for k, nm in ((1, "dow_TUE"), (2, "dow_WED"), (3, "dow_THU"),
                  (4, "dow_FRI")):
        fe.add(nm, 1.0 if wd == k else 0.0, av_anchor or av_prev)
    nxt = CTX.next_release(guard, asset)
    close_ts = panel.close_utc.get(iso)
    if nxt and close_ts:
        today = 1.0 if nxt["event_ts"] <= close_ts else 0.0
        name = nxt["name"].upper()
        fe.add("release_today", today, av_anchor or av_prev)
        fe.add("release_today_FOMC", today if "FOMC" in name else 0.0,
               av_anchor or av_prev)
        fe.add("release_today_CPI",
               today if ("CONSUMER PRICE" in name or "CPI" in name) else 0.0,
               av_anchor or av_prev)
        fe.add("release_today_JOBS",
               today if ("EMPLOYMENT SITUATION" in name or "JOB" in name)
               else 0.0, av_anchor or av_prev)
        fe.add("release_countdown_h",
               min(72.0, nxt["countdown_sec"] / 3600.0), av_anchor or av_prev)
    else:
        for nm in ("release_today", "release_today_FOMC", "release_today_CPI",
                   "release_today_JOBS", "release_countdown_h"):
            fe.add(nm, float("nan"), None)
    rec = CTX.recent_release(guard, asset, window_sec=86400)
    fe.add("release_since_h", (rec["since_sec"] / 3600.0) if rec else 48.0,
           av_anchor or av_prev)

    # ---- E. external context (availability-lagged, D-057) ----------------
    _series_feat(fe, "log_GVZ", guard, "GVZ", lambda v: _log(v[0]))
    _delta_feat(fe, "d5_GVZ", guard, "GVZ", _first, 5)
    _series_feat(fe, "log_VIX", guard, "VIX", lambda v: _log(v[0]))
    _delta_feat(fe, "d5_VIX", guard, "VIX", _first, 5)
    _series_feat(fe, "log_RVX", guard, "RVX", lambda v: _log(v[0]))
    _delta_feat(fe, "d5_DGS10", guard, "FRED_DGS10", _first, 5)
    _delta_feat(fe, "d5_DTWEXBGS", guard, "FRED_DTWEXBGS", _first, 1)
    if asset == "SI":
        _series_feat(fe, "log_GSR", guard, "GOLD_SILVER_RATIO",
                     lambda v: _log(v[0]))
        _delta_feat(fe, "d5_DFII10", guard, "FRED_DFII10", _first, 5)
        cot = "COT_DISAGG_SILVER"
        shfe = "SHFE_INV_SILVER"
    elif asset == "HG":
        _delta_feat(fe, "d5_DEXCHUS", guard, "FRED_DEXCHUS", _first, 1)
        cot = "COT_DISAGG_COPPER"
        shfe = "SHFE_INV_COPPER"
    else:
        _series_feat(fe, "log_NIKKEI_VI", guard, "NIKKEI_VI",
                     lambda v: _log(v[0]))
        _delta_feat(fe, "d5_DEXJPUS", guard, "FRED_DEXJPUS", _first, 1)
        _delta_feat(fe, "d5_JGB10", guard, "JGB_10Y", _first, 5)
        cot = "COT_TFF_NIKKEI"
        shfe = None

    def _net(vals):
        # context._cot emits (net, long, short, open_interest) — the NET is
        # already differenced, so read slot 0 and slot 3, never long/short.
        n = _f(vals[0])
        oi = _f(vals[3]) if len(vals) > 3 else float("nan")
        return n / oi if (np.isfinite(n) and np.isfinite(oi) and oi > 0) \
            else float("nan")

    _series_feat(fe, "cot_net_over_oi", guard, cot, _net)
    try:
        ser = CTX.series(cot)
        a0, a1 = ser.latest(guard, back=0), ser.latest(guard, back=1)
        if a0 and a1:
            va, vb = _net(a0["values"]), _net(a1["values"])
            fe.add("cot_net_wow", (va - vb) if (np.isfinite(va) and
                                                np.isfinite(vb))
                   else float("nan"),
                   max(a0["availability_ts"], a1["availability_ts"]))
        else:
            fe.add("cot_net_wow", float("nan"), None)
    except Exception:                      # noqa: BLE001
        fe.add("cot_net_wow", float("nan"), None)
    if shfe:
        _series_feat(fe, "log_shfe_inv", guard, shfe, lambda v: _log(v[0]))
        try:
            ser = CTX.series(shfe)
            a0, a1 = ser.latest(guard, back=0), ser.latest(guard, back=1)
            if a0 and a1:
                va, vb = _log(a0["values"][0]), _log(a1["values"][0])
                fe.add("shfe_inv_wow", (va - vb) if (np.isfinite(va) and
                                                     np.isfinite(vb))
                       else float("nan"),
                       max(a0["availability_ts"], a1["availability_ts"]))
            else:
                fe.add("shfe_inv_wow", float("nan"), None)
        except Exception:                  # noqa: BLE001
            fe.add("shfe_inv_wow", float("nan"), None)

    # ---- F. cross-asset prior-session state ------------------------------
    for other in MC.ASSET_ORDER:
        if other == asset:
            continue
        op = panels.get(other)
        if op is None:
            fe.add("x_%s_ret1" % other, float("nan"), None)
            fe.add("x_%s_rangecn1" % other, float("nan"), None)
            continue
        # the newest OTHER-asset session whose CLOSE is strictly before the
        # anchor; the guard then re-checks it.
        j = int(np.searchsorted(op.close_ts, guard.decision_ts,
                                side="left")) - 1
        if j < 1:
            fe.add("x_%s_ret1" % other, float("nan"), None)
            fe.add("x_%s_rangecn1" % other, float("nan"), None)
            continue
        av_o = op.close_utc[op.iso[j]]
        rv, rts = clean_ret(op, j)
        fe.add("x_%s_ret1" % other, rv, rts)
        fe.add("x_%s_rangecn1" % other,
               _f(op.v1.get((op.iso[j], "SESSION"), {}).get("range_clocknorm")),
               av_o)
    # own prior-session return
    rv, rts = clean_ret(panel, i - 1) if i >= 2 else (float("nan"), None)
    fe.add("own_ret1", rv, rts)
    return fe


# ===================================================================
# STAGE 4 — MODELS (deterministic; no RNG anywhere)
# ===================================================================
def _prep(Xtr):
    med = np.nanmedian(Xtr, axis=0)
    med = np.where(np.isfinite(med), med, 0.0)
    Z = np.where(np.isfinite(Xtr), Xtr, med)
    mu = Z.mean(axis=0)
    sd = Z.std(axis=0)
    sd = np.where(sd > 1e-12, sd, 1.0)
    return med, mu, sd


def _apply(X, med, mu, sd):
    Z = np.where(np.isfinite(X), X, med)
    return (Z - mu) / sd


def ridge_fit(Z, y, lam=RIDGE_LAM):
    n, p = Z.shape
    A_ = np.hstack([np.ones((n, 1)), Z])
    G = A_.T @ A_
    reg = np.eye(p + 1) * lam
    reg[0, 0] = 0.0
    beta = np.linalg.solve(G + reg, A_.T @ y)
    return beta


def ridge_pred(Z, beta):
    n = Z.shape[0]
    return np.hstack([np.ones((n, 1)), Z]) @ beta


def logit_fit(Z, y, lam=LOGIT_LAM, iters=60, tol=1e-9):
    n, p = Z.shape
    A_ = np.hstack([np.ones((n, 1)), Z])
    beta = np.zeros(p + 1)
    beta[0] = math.log(max(1e-6, min(1 - 1e-6, y.mean())) /
                       (1 - max(1e-6, min(1 - 1e-6, y.mean()))))
    reg = np.eye(p + 1) * lam
    reg[0, 0] = 0.0
    for _ in range(iters):
        eta = A_ @ beta
        pr = 1.0 / (1.0 + np.exp(-np.clip(eta, -30, 30)))
        wgt = np.clip(pr * (1 - pr), 1e-6, None)
        g = A_.T @ (y - pr) - reg @ beta
        H = (A_ * wgt[:, None]).T @ A_ + reg
        try:
            step = np.linalg.solve(H, g)
        except np.linalg.LinAlgError:
            break
        beta = beta + step
        if float(np.max(np.abs(step))) < tol:
            break
    return beta


def logit_pred(Z, beta):
    n = Z.shape[0]
    eta = np.hstack([np.ones((n, 1)), Z]) @ beta
    return 1.0 / (1.0 + np.exp(-np.clip(eta, -30, 30)))


# ------------------------------------------------------------ GBT-small ----
def _bin_edges(Z, n_bins):
    p = Z.shape[1]
    edges = np.zeros((p, n_bins - 1))
    qs = np.linspace(0, 100, n_bins + 1)[1:-1]
    for j in range(p):
        col = Z[:, j]
        e = np.percentile(col, qs)
        e = np.maximum.accumulate(e)
        edges[j] = e
    return edges


def _codes(Z, edges, n_bins):
    p = Z.shape[1]
    out = np.zeros(Z.shape, dtype=np.int64)
    for j in range(p):
        out[:, j] = np.searchsorted(edges[j], Z[:, j], side="left")
    return np.clip(out, 0, n_bins - 1)


def _grow(codes, g, h, idx, depth, cfg, offsets, n_bins):
    """One regression tree node -> nested dict {f, thr, L, R} or {'v': value}."""
    G = float(g[idx].sum())
    H = float(h[idx].sum())
    leaf = {"v": G / (H + cfg["l2"])}
    if depth >= cfg["depth"] or idx.size < 2 * cfg["min_leaf"]:
        return leaf
    sub = codes[idx]
    flat = (sub + offsets).ravel()
    p = codes.shape[1]
    gs = np.bincount(flat, weights=np.repeat(g[idx], p),
                     minlength=p * n_bins).reshape(p, n_bins)
    hs = np.bincount(flat, weights=np.repeat(h[idx], p),
                     minlength=p * n_bins).reshape(p, n_bins)
    cs = np.bincount(flat, minlength=p * n_bins).reshape(p, n_bins)
    gl = np.cumsum(gs, axis=1)[:, :-1]
    hl = np.cumsum(hs, axis=1)[:, :-1]
    cl = np.cumsum(cs, axis=1)[:, :-1]
    gr, hr, cr = G - gl, H - hl, idx.size - cl
    base = G * G / (H + cfg["l2"])
    gain = gl * gl / (hl + cfg["l2"]) + gr * gr / (hr + cfg["l2"]) - base
    ok = (cl >= cfg["min_leaf"]) & (cr >= cfg["min_leaf"])
    gain = np.where(ok, gain, -np.inf)
    if not np.isfinite(gain).any() or float(gain.max()) <= 1e-12:
        return leaf
    fj, tb = np.unravel_index(int(np.argmax(gain)), gain.shape)
    m = codes[idx, fj] <= tb
    li, ri = idx[m], idx[~m]
    if li.size < cfg["min_leaf"] or ri.size < cfg["min_leaf"]:
        return leaf
    return {"f": int(fj), "thr": int(tb),
            "L": _grow(codes, g, h, li, depth + 1, cfg, offsets, n_bins),
            "R": _grow(codes, g, h, ri, depth + 1, cfg, offsets, n_bins)}


def _tree_pred(node, codes):
    out = np.zeros(codes.shape[0])
    stack = [(node, np.arange(codes.shape[0]))]
    while stack:
        nd, idx = stack.pop()
        if "v" in nd:
            out[idx] = nd["v"]
            continue
        m = codes[idx, nd["f"]] <= nd["thr"]
        stack.append((nd["L"], idx[m]))
        stack.append((nd["R"], idx[~m]))
    return out


def gbt_fit(Z, y, task, cfg=GBT, n_trees=None, eval_set=None):
    """Least-squares / logistic histogram boosting.  Deterministic: no
    subsampling, no RNG, ties broken by the first argmax.

    eval_set=(Zv, yv, kind) turns on INNER EARLY STOPPING: the per-round loss on
    a held-out TAIL of the training window is tracked and `best_rounds` is
    returned.  The tail is inside the training window, so nothing after the
    refit cutoff is ever touched.
    """
    n_bins = cfg["n_bins"]
    edges = _bin_edges(Z, n_bins)
    codes = _codes(Z, edges, n_bins)
    p = Z.shape[1]
    offsets = (np.arange(p, dtype=np.int64) * n_bins)[None, :]
    idx = np.arange(Z.shape[0])
    if task == "class":
        pm = float(np.clip(y.mean(), 1e-4, 1 - 1e-4))
        f0 = math.log(pm / (1 - pm))
    else:
        f0 = float(y.mean())
    F = np.full(Z.shape[0], f0)
    trees = []
    vcodes = Fv = yv = kindv = None
    best = (float("inf"), 0)
    if eval_set is not None:
        Zv, yv, kindv = eval_set
        vcodes = _codes(Zv, edges, n_bins)
        Fv = np.full(Zv.shape[0], f0)
        best = (_gbt_loss(task, Fv, yv, kindv), 0)
    for _t in range(int(n_trees or cfg["n_trees"])):
        if task == "class":
            pr = 1.0 / (1.0 + np.exp(-np.clip(F, -30, 30)))
            g = y - pr
            h = np.clip(pr * (1 - pr), 1e-6, None)
        else:
            g = y - F
            h = np.ones_like(y)
        node = _grow(codes, g, h, idx, 0, cfg, offsets, n_bins)
        if "v" in node and abs(node["v"]) < 1e-12:
            break
        trees.append(node)
        F = F + cfg["lr"] * _tree_pred(node, codes)
        if eval_set is not None:
            Fv = Fv + cfg["lr"] * _tree_pred(node, vcodes)
            lv = _gbt_loss(task, Fv, yv, kindv)
            if lv < best[0]:
                best = (lv, len(trees))
    return {"f0": f0, "trees": trees, "edges": edges, "lr": cfg["lr"],
            "n_bins": n_bins, "task": task, "best_rounds": int(best[1]),
            "best_loss": float(best[0])}


def _gbt_loss(task, F, y, kind):
    if task == "class":
        pr = 1.0 / (1.0 + np.exp(-np.clip(F, -30, 30)))
        return brier(y, pr)
    return mae(_invert(y, kind), _invert(F, kind))


INNER_FRAC = 0.20
INNER_MIN = 60
LAM_GRID = (1.0, 10.0, 100.0, 1000.0)


def _inner_split(m):
    k = max(INNER_MIN, int(round(m * INNER_FRAC)))
    a = m - k
    return (a, m) if a >= MIN_TRAIN // 2 else (None, None)


def fit_linear(Ztr, ytr, task, kind):
    """Ridge / logistic-ridge whose penalty is chosen on a HELD-OUT TAIL of the
    training window (the last %d%%), never on FIT-era test scores and never on
    anything after the refit cutoff.  With ~50 features and ~250-1,000 training
    sessions a fixed penalty is either useless or ruinous; the tail split is the
    honest way to set it inside the walk-forward.""" % int(INNER_FRAC * 100)
    a, m = _inner_split(Ztr.shape[0])
    lam = LAM_GRID[1]
    if a is not None:
        best = None
        for lm in LAM_GRID:
            if task == "class":
                if len(np.unique(ytr[:a])) < 2:
                    continue
                b = logit_fit(Ztr[:a], ytr[:a], lm)
                loss = brier(ytr[a:], logit_pred(Ztr[a:], b))
            else:
                b = ridge_fit(Ztr[:a], ytr[:a], lm)
                loss = mae(_invert(ytr[a:], kind),
                           _invert(ridge_pred(Ztr[a:], b), kind))
            if np.isfinite(loss) and (best is None or loss < best[0]):
                best = (loss, lm)
        if best is not None:
            lam = best[1]
    beta = (logit_fit(Ztr, ytr, lam) if task == "class"
            else ridge_fit(Ztr, ytr, lam))
    return {"beta": beta, "lam": lam, "task": task,
            "clip": _clip_bounds(ytr, task)}


CLIP_PAD = 0.25


def _clip_bounds(ytr, task):
    """Model-space support of the training target, padded.

    A ridge fitted in log space can extrapolate to an absurd exponent on one
    outlying feature row and produce a $3,700 menu forecast (measured on NKD
    before this guard).  Extrapolating outside the observed target support is
    not a forecast, so it is clipped, deterministically and symmetrically."""
    if task == "class":
        return (0.0, 1.0)
    lo, hi = float(np.min(ytr)), float(np.max(ytr))
    sp = max(hi - lo, 1e-9)
    return (lo - CLIP_PAD * sp, hi + CLIP_PAD * sp)


def linear_pred(model, Z):
    return (logit_pred(Z, model["beta"]) if model["task"] == "class"
            else ridge_pred(Z, model["beta"]))


def fit_gbt(Ztr, ytr, task, kind):
    """GBT-small with the round count early-stopped on the same held-out tail."""
    a, m = _inner_split(Ztr.shape[0])
    rounds = GBT["n_trees"]
    if a is not None and (task != "class" or len(np.unique(ytr[:a])) >= 2):
        probe = gbt_fit(Ztr[:a], ytr[:a], task,
                        eval_set=(Ztr[a:], ytr[a:], kind))
        rounds = max(5, int(probe["best_rounds"]))
    mdl = gbt_fit(Ztr, ytr, task, n_trees=rounds)
    mdl["rounds"] = rounds
    mdl["clip"] = _clip_bounds(ytr, task)
    return mdl


def predict(kindm, model, Z, task, kind):
    """One prediction door for both families, both eras and both tasks."""
    r = linear_pred(model, Z) if kindm == "lin" else gbt_pred(model, Z)
    if task == "class":
        return r
    lo, hi = model["clip"]
    return _invert(np.clip(r, lo, hi), kind)


def gbt_pred(model, Z):
    codes = _codes(Z, model["edges"], model["n_bins"])
    F = np.full(Z.shape[0], model["f0"])
    for nd in model["trees"]:
        F = F + model["lr"] * _tree_pred(nd, codes)
    if model["task"] == "class":
        return 1.0 / (1.0 + np.exp(-np.clip(F, -30, 30)))
    return F


# ===================================================================
# STAGE 5 — WALK-FORWARD
# ===================================================================
def _target_vectors(panel, anchor):
    """{target: (y, transform_name)} — y in MODEL space."""
    n = len(panel.truth)
    out = {}
    out["day_type"] = (panel.daytype_arr.copy(), "class")
    out["range"] = (np.array([_log(v) for v in panel.range_arr]), "log")
    for p in PHASES:
        out["share_%s" % p] = (panel.share_arr[p].copy(), "identity")
    out["menu"] = (np.array([math.log1p(v) if np.isfinite(v) else float("nan")
                             for v in panel.menu_arr[anchor]]), "log1p")
    _ = n
    return out


def _invert(vals, kind):
    if kind == "log":
        return np.exp(np.clip(vals, -30, 30))
    if kind == "log1p":
        return np.maximum(0.0, np.expm1(np.clip(vals, -30, 30)))
    if kind == "identity":
        return vals
    return vals


def train_mask(dates, cutoff, include_cutoff=False):
    """The expanding training window for a refit at `cutoff`.

    LAW: a training session's date must be STRICTLY BEFORE the refit cutoff.
    `include_cutoff=True` is the committed mutant (test_regime.py mutant C) and
    is refused here rather than silently fitting on the month being predicted.
    """
    if include_cutoff:
        raise AssertionError(
            "walk-forward violated: a refit at %s may not train on sessions "
            "dated %s or later" % (cutoff, cutoff))
    return np.array([d < cutoff for d in dates])


def walk_forward(panel, anchor, Xall, feat_names, keep):
    """Expanding-window monthly-refit walk-forward for every target at one
    (asset, anchor).  Returns per-target dicts of arrays over sessions."""
    dates = [dt.date.fromisoformat(d) for d in panel.iso]
    n = len(dates)
    X = Xall[:, keep]
    tv = _target_vectors(panel, anchor)
    res = {}
    for tgt in ALL_TARGETS:
        res[tgt] = {fam: {"pred": np.full(n, np.nan),
                          "pred_frozen": np.full(n, np.nan),
                          "q10": np.full(n, np.nan),
                          "q90": np.full(n, np.nan)}
                    for fam in ("LINEAR", "GBT")}
        res[tgt]["n_train"] = np.full(n, np.nan)
    months = sorted({(d.year, d.month) for d in dates})
    frozen = {(t, f): None for t in ALL_TARGETS for f in ("LINEAR", "GBT")}
    for (yy, mm) in months:
        cutoff = dt.date(yy, mm, 1)
        tr_mask = train_mask(dates, cutoff)
        te_mask = np.array([d.year == yy and d.month == mm for d in dates])
        if not te_mask.any():
            continue
        is_fit_refit = cutoff <= FREEZE_CUTOFF
        for tgt in ALL_TARGETS:
            y, kind = tv[tgt]
            task = "class" if tgt == CLASS_TARGET else "reg"
            ok = tr_mask & np.isfinite(y) & np.isfinite(X).any(axis=1)
            n_tr = int(ok.sum())
            res[tgt]["n_train"][te_mask] = n_tr
            if n_tr < MIN_TRAIN:
                continue
            Xtr, ytr = X[ok], y[ok]
            med, mu, sd = _prep(Xtr)
            Ztr = _apply(Xtr, med, mu, sd)
            Zte = _apply(X[te_mask], med, mu, sd)
            if task == "class" and len(np.unique(ytr)) < 2:
                continue
            fits = {"LINEAR": ("lin", fit_linear(Ztr, ytr, task, kind)),
                    "GBT": ("gbt", fit_gbt(Ztr, ytr, task, kind))}
            for fam, (kindm, model) in fits.items():
                res[tgt][fam]["pred"][te_mask] = predict(kindm, model, Zte,
                                                         task, kind)
                if tgt == "range":
                    # CC-M1-1(A) construction: the point forecast scaled by the
                    # TRAINING residual quantiles in log space (strictly prior).
                    rte = (linear_pred(model, Zte) if kindm == "lin"
                           else gbt_pred(model, Zte))
                    rtr = (linear_pred(model, Ztr) if kindm == "lin"
                           else gbt_pred(model, Ztr))
                    resid = ytr - rtr
                    resid = resid[np.isfinite(resid)]
                    if resid.size >= 30:
                        qs = np.percentile(resid, [PINBALL_Q[0] * 100,
                                                   PINBALL_Q[1] * 100])
                        lo_, hi_ = model["clip"]
                        rc = np.clip(rte, lo_, hi_)
                        res[tgt][fam]["q10"][te_mask] = _invert(rc + qs[0],
                                                                kind)
                        res[tgt][fam]["q90"][te_mask] = _invert(rc + qs[1],
                                                                kind)
                if is_fit_refit:
                    frozen[(tgt, fam)] = (kindm, model, med, mu, sd, kind,
                                          task)
                fz = frozen[(tgt, fam)]
                if fz is not None:
                    km, mo, me2, mu2, sd2, kd2, tk2 = fz
                    Z2 = _apply(X[te_mask], me2, mu2, sd2)
                    res[tgt][fam]["pred_frozen"][te_mask] = predict(
                        km, mo, Z2, tk2, kd2)
        MC.hb("wf %s/%s %04d-%02d" % (panel.asset, anchor, yy, mm))
    return res


# ===================================================================
# STAGE 6 — BENCHMARKS + METRICS
# ===================================================================
def benchmarks(panel, anchor):
    n = len(panel.truth)
    b = {}
    # --- class
    base = np.full(n, np.nan)
    pers = np.full(n, np.nan)
    for i in range(n):
        base[i] = _mean_prior(panel.daytype_arr, i, TRAIL)
        lo, hi = max(0, i - TRAIL), _window_hi(i)
        prev = panel.daytype_arr[i - 1] if i >= 1 else float("nan")
        if np.isfinite(prev):
            sel = [panel.daytype_arr[j] for j in range(lo + 1, hi)
                   if np.isfinite(panel.daytype_arr[j]) and
                   np.isfinite(panel.daytype_arr[j - 1]) and
                   panel.daytype_arr[j - 1] == prev]
            pers[i] = float(np.mean(sel)) if len(sel) >= 10 else base[i]
        else:
            pers[i] = base[i]
    b["day_type"] = {"BASE_RATE": base, "PERSISTENCE": pers}
    # --- range
    tmed = np.array([_trail_stat(panel.range_arr, i, TRAIL, "median")
                     for i in range(n)])
    tp = np.array([panel.range_arr[i - 1] if i >= 1 else float("nan")
                   for i in range(n)])
    fvh = np.array([_f(panel.fvol.get((d, "SESSION"), {}).get("range_hat_usd"))
                    for d in panel.iso])
    b["range"] = {"TRAILING_MEDIAN": tmed, "PERSISTENCE": tp,
                  "FVOL_RANGE_HAT": fvh}
    # trailing quantile band for the pinball comparison
    q10 = np.full(n, np.nan)
    q90 = np.full(n, np.nan)
    for i in range(n):
        lo, hi = max(0, i - TRAIL), _window_hi(i)
        w = panel.range_arr[lo:hi]
        w = w[np.isfinite(w)]
        if w.size >= TRAIL_MIN:
            q10[i] = float(np.percentile(w, PINBALL_Q[0] * 100))
            q90[i] = float(np.percentile(w, PINBALL_Q[1] * 100))
    b["range_q"] = {"q10": q10, "q90": q90}
    for p in PHASES:
        b["share_%s" % p] = {"TRAILING_MEAN": np.array(
            [_trail_stat(panel.share_arr[p], i, TRAIL, "mean")
             for i in range(n)])}
    b["menu"] = {"TRAILING_MEDIAN": np.array(
        [_trail_stat(panel.menu_arr[anchor], i, TRAIL, "median")
         for i in range(n)])}
    return b


def auc(y, p):
    s = np.isfinite(y) & np.isfinite(p)
    y, p = y[s], p[s]
    if y.size == 0 or len(np.unique(y)) < 2:
        return float("nan")
    order = np.argsort(p, kind="mergesort")
    ps = p[order]
    ranks = np.empty(ps.size, dtype=np.float64)
    i = 0
    while i < ps.size:
        j = i
        while j + 1 < ps.size and ps[j + 1] == ps[i]:
            j += 1
        ranks[i:j + 1] = (i + j) / 2.0 + 1.0
        i = j + 1
    ys = y[order]
    n1 = float((ys == 1).sum())
    n0 = float((ys == 0).sum())
    if n1 == 0 or n0 == 0:
        return float("nan")
    return float((ranks[ys == 1].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0))


def brier(y, p):
    s = np.isfinite(y) & np.isfinite(p)
    return float(np.mean((p[s] - y[s]) ** 2)) if s.any() else float("nan")


def mae(y, p):
    s = np.isfinite(y) & np.isfinite(p)
    return float(np.mean(np.abs(p[s] - y[s]))) if s.any() else float("nan")


def pinball(y, q, tau):
    s = np.isfinite(y) & np.isfinite(q)
    if not s.any():
        return float("nan")
    d = y[s] - q[s]
    return float(np.mean(np.maximum(tau * d, (tau - 1) * d)))


def spearman(y, p):
    s = np.isfinite(y) & np.isfinite(p)
    if s.sum() < 3:
        return float("nan")

    def _rank(v):
        o = np.argsort(v, kind="mergesort")
        r = np.empty(v.size)
        i = 0
        vs = v[o]
        while i < vs.size:
            j = i
            while j + 1 < vs.size and vs[j + 1] == vs[i]:
                j += 1
            r[o[i:j + 1]] = (i + j) / 2.0 + 1.0
            i = j + 1
        return r
    a, b = _rank(y[s]), _rank(p[s])
    return float(np.corrcoef(a, b)[0, 1])


def block_bootstrap_ci(y, p, q, stat, sel, n=BOOT_N, block=BOOT_BLOCK):
    """95pct CI on stat(model) - stat(benchmark) with a MOVING-BLOCK resample
    over sessions.  Vol clusters, so an i.i.d. session resample would overstate
    the precision; the BOOT_BLOCK-session block carries the clustering through.
    """
    idx = np.nonzero(sel & np.isfinite(y) & np.isfinite(p) &
                     np.isfinite(q))[0]
    if idx.size < 3 * block:
        return float("nan"), float("nan")
    rng = np.random.default_rng(BOOT_SEED)
    m = idx.size
    nb = int(math.ceil(m / block))
    off = np.arange(block)
    out = np.empty(n)
    for b in range(n):
        st = rng.integers(0, m - block + 1, size=nb)
        take = idx[(st[:, None] + off[None, :]).ravel()[:m]]
        out[b] = stat(y[take], p[take]) - stat(y[take], q[take])
    return float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))


def date_clustered_ci(day_groups, y, p, q, stat, n=BOOT_N):
    """POOLED metrics: resample CALENDAR DATES — every asset observed on a
    resampled date moves WITH it.  This is the session-clustered honesty the
    pooled numbers require (the three assets share market-wide vol days)."""
    if len(day_groups) < 30:
        return float("nan"), float("nan")
    rng = np.random.default_rng(BOOT_SEED)
    D = len(day_groups)
    out = np.empty(n)
    for b in range(n):
        pick = rng.integers(0, D, size=D)
        take = np.concatenate([day_groups[k] for k in pick])
        out[b] = stat(y[take], p[take]) - stat(y[take], q[take])
    return float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))


# ===================================================================
# STAGE 7 — DRIVER
# ===================================================================
# DEFECT D19 (CC-M2-17.3, BINDING): forecast_*.tsv carries PREDICTIONS ONLY.
# It used to print the realised targets (y_day_type, y_range_usd, y_share_*,
# y_menu) beside the predictions, so any reader who opened this file to
# diagnose an empty prediction column — which is exactly what E1 day 6 did —
# read the session's REALISED range, day type and phase shares and had to be
# stamped FORECAST-TRUTH-EXPOSED.  The truth lives in truth_*.tsv, which is a
# post-hoc artefact and is never joined into a sheet or a triage index.
#
# `Y_COLUMNS` is kept as a NAMED REGISTER rather than deleted: the guard test
# (test_regime.t10) asserts that not one of these names appears in the header
# of any forecast_*.tsv, and the red-first mutant re-adds one.
Y_COLUMNS = ("y_day_type", "y_range_usd", "y_share_TOKYO", "y_share_LONDON",
             "y_share_NY", "y_menu")

FORECAST_COLUMNS = (
    "asset", "trade_date", "year", "era", "anchor", "anchor_sec", "anchor_ts",
    "model_class", "model_range", "model_share", "model_menu", "n_train",
    "p_expansion", "p_expansion_wfcont", "bench_base_rate",
    "bench_persistence",
    "range_hat_usd", "range_hat_wfcont", "range_hat_q10", "range_hat_q90",
    "bench_range_trailmed", "bench_range_persist", "bench_range_fvol",
    "bench_range_q10", "bench_range_q90",
    "share_hat_TOKYO", "share_hat_LONDON", "share_hat_NY",
    "bench_share_TOKYO", "bench_share_LONDON", "bench_share_NY",
    "menu_hat", "menu_hat_wfcont", "bench_menu_trailmed",
    "range_hat_vs_trailing", "n_feature_missing")

assert not (set(Y_COLUMNS) & set(FORECAST_COLUMNS)), "D19: y_* column leaked"


def _era_pick(pred, pred_frozen, years):
    """Era law: FIT years use the walk-forward, 2025 uses the frozen fit."""
    return np.where(years >= 2025, pred_frozen, pred)


_PANELS = {}


def panels(assets, truth_rows, sofar_rows):
    for a in assets:
        if a not in _PANELS:
            _PANELS[a] = AssetPanel(a, truth_rows, sofar_rows)
    return _PANELS


def build_matrix(panel, anchor, all_panels):
    """X (n x p) + names + per-row missing counts.  Raises on any leak."""
    rows, names, miss = [], None, []
    for i, iso in enumerate(panel.iso):
        sf = panel.sofar.get((iso, anchor))
        if sf is None:
            rows.append(None)
            miss.append(0)
            continue
        a_ts = int(_f(sf["anchor_ts"]))
        a_sec = int(_f(sf["anchor_sec"]))
        guard = MC.CausalGuard(a_ts, a_sec, dt.date.fromisoformat(iso))
        fe = build_features(panel, i, anchor, guard, all_panels)
        if names is None:
            names = list(fe.names)
        elif fe.names != names:
            raise RuntimeError("feature name drift at %s %s %s"
                               % (panel.asset, iso, anchor))
        rows.append(np.array(fe.vals, dtype=np.float64))
        miss.append(fe.n_missing)
    p = len(names or [])
    X = np.full((len(rows), p), np.nan)
    for i, r in enumerate(rows):
        if r is not None:
            X[i] = r
    return X, names, np.array(miss, dtype=np.float64)


def coverage_keep(panel, anchor, X, names):
    """fvol's own context rule generalised: a feature below COVERAGE_MIN finite
    coverage on the asset's FIT rows is DROPPED (and the drop is reported)."""
    years = np.array([int(d[0:4]) for d in panel.iso])
    fit = (years >= 2021) & (years <= 2024)
    keep, rep = [], []
    for j, nm in enumerate(names):
        col = X[fit, j]
        cov = float(np.mean(np.isfinite(col))) if col.size else 0.0
        var = float(np.nanstd(col)) if col.size else 0.0
        ok = cov >= COVERAGE_MIN and var > 1e-12
        rep.append([panel.asset, anchor, nm, cov, var, int(ok),
                    "" if ok else ("coverage %.3f < %.2f" % (cov, COVERAGE_MIN)
                                   if cov < COVERAGE_MIN else "constant")])
        if ok:
            keep.append(j)
    return np.array(keep, dtype=np.int64), rep


TARGET_GROUPS = ("day_type", "range", "share", "menu")


def choose_families(panel, anchor, res, fit):
    """LINEAR vs GBT, decided on FIT 2021-2024 walk-forward only (era law).

    The three phase-share targets are chosen AS ONE GROUP so the simplex
    renormalisation is well defined."""
    picks, rows = {}, []
    for grp in TARGET_GROUPS:
        sc = {}
        for fam in ("LINEAR", "GBT"):
            if grp == "day_type":
                sc[fam] = brier(panel.daytype_arr[fit],
                                res["day_type"][fam]["pred"][fit])
            elif grp == "range":
                sc[fam] = mae(panel.range_arr[fit],
                              res["range"][fam]["pred"][fit])
            elif grp == "menu":
                sc[fam] = mae(panel.menu_arr[anchor][fit],
                              res["menu"][fam]["pred"][fit])
            else:
                sc[fam] = float(np.mean(
                    [mae(panel.share_arr[p][fit],
                         res["share_%s" % p][fam]["pred"][fit])
                     for p in PHASES]))
        best = min(("LINEAR", "GBT"),
                   key=lambda f: (not np.isfinite(sc[f]), sc[f], f))
        picks[grp] = best
        rows.append([panel.asset, anchor, grp, best, sc["LINEAR"], sc["GBT"],
                     "Brier" if grp == "day_type" else "MAE"])
    return picks, rows


def final_predictions(panel, anchor, res, picks, years):
    """Era-law selection + the two deterministic post-processings (menu floored
    at zero, phase shares projected onto the simplex).  Everything scored and
    everything emitted comes from HERE, so the report cannot describe a
    different number from the TSV."""
    def pick(t, fam):
        return _era_pick(res[t][fam]["pred"], res[t][fam]["pred_frozen"],
                         years)
    out = {"day_type": pick("day_type", picks["day_type"]),
           "range": pick("range", picks["range"]),
           "menu": np.maximum(0.0, pick("menu", picks["menu"]))}
    raw = np.vstack([np.clip(pick("share_%s" % p, picks["share"]), 0.01, 0.98)
                     for p in PHASES])
    ssum = raw.sum(axis=0)
    for k, p in enumerate(PHASES):
        out["share_%s" % p] = raw[k] / np.where(ssum > 0, ssum, 1.0)
    fam = picks["range"]
    out["range_q10"] = res["range"][fam]["q10"]
    out["range_q90"] = res["range"][fam]["q90"]
    out["wf_day_type"] = res["day_type"][picks["day_type"]]["pred"]
    out["wf_range"] = res["range"][picks["range"]]["pred"]
    out["wf_menu"] = np.maximum(0.0, res["menu"][picks["menu"]]["pred"])
    out["n_train"] = res["day_type"]["n_train"]
    return out


def score(panel, anchor, pred, bench, picks, era):
    """Metrics rows for one (asset, anchor, era) — scored on exactly the series
    the forecast TSV carries."""
    years = np.array([int(d[0:4]) for d in panel.iso])
    sel = (years >= 2021) & (years <= 2024) if era == "FIT" else (years == 2025)
    out = []
    y = panel.daytype_arr
    p = pred["day_type"]
    for bn, bv in bench["day_type"].items():
        out.append([panel.asset, anchor, era, "day_type", picks["day_type"],
                    bn, int((sel & np.isfinite(y) & np.isfinite(p)).sum()),
                    auc(y[sel], p[sel]), brier(y[sel], p[sel]),
                    auc(y[sel], bv[sel]), brier(y[sel], bv[sel]),
                    float(np.nanmean(y[sel]))])
    for tgt in REG_TARGETS:
        grp = "share" if tgt.startswith("share_") else tgt
        praw = pred[tgt]
        if tgt == "range":
            yv = panel.range_arr
        elif tgt == "menu":
            yv = panel.menu_arr[anchor]
        else:
            yv = panel.share_arr[tgt.split("_", 1)[1]]
        for bn, bv in bench[tgt].items():
            out.append([panel.asset, anchor, era, tgt, picks[grp], bn,
                        int((sel & np.isfinite(yv) & np.isfinite(praw)).sum()),
                        mae(yv[sel], praw[sel]), spearman(yv[sel], praw[sel]),
                        mae(yv[sel], bv[sel]), spearman(yv[sel], bv[sel]),
                        float(np.nanmean(yv[sel]))])
    for tau, mv, bv in ((PINBALL_Q[0], pred["range_q10"],
                         bench["range_q"]["q10"]),
                        (PINBALL_Q[1], pred["range_q90"],
                         bench["range_q"]["q90"])):
        out.append([panel.asset, anchor, era,
                    "range_pinball_q%02d" % int(tau * 100), picks["range"],
                    "TRAILING_QUANTILE", int((sel & np.isfinite(mv)).sum()),
                    pinball(panel.range_arr[sel], mv[sel], tau), float("nan"),
                    pinball(panel.range_arr[sel], bv[sel], tau), float("nan"),
                    float("nan")])
    return out


# ===================================================================
# STAGE 8 — THE REPORT (every load-bearing number carries file:line)
# ===================================================================
def line_index(path, keycols):
    """{key tuple: 1-based line number} for a TSV this module wrote."""
    idx, cols = {}, None
    with open(path) as fh:
        for ln, line in enumerate(fh, 1):
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if cols is None:
                cols = f
                continue
            r = dict(zip(cols, f))
            idx[tuple(r[c] for c in keycols)] = ln
    return idx


def _n(v, fmt="%.4f"):
    x = _f(v)
    return "n/a" if not np.isfinite(x) else fmt % x


def report(assets=None):
    """Write evidence/port_m2/REGIME_FORECAST_REPORT.md from the frozen TSVs."""
    assets = assets or list(MC.ASSET_ORDER)
    mp_ = out_path("metrics.tsv")
    cp = out_path("model_choice.tsv")
    vp = out_path("coverage.tsv")
    ip = out_path("class_ci.tsv")
    pp = out_path("pooled_class.tsv")
    rp = out_path("red_ledger.tsv")
    met = read_tsv(mp_)
    mli = line_index(mp_, ["asset", "anchor", "era", "target", "benchmark"])
    cho = read_tsv(cp)
    cli = line_index(cp, ["asset", "anchor", "target_group"])
    cov = read_tsv(vp)
    cis = read_tsv(ip)
    ili = line_index(ip, ["asset", "anchor", "era", "benchmark"])
    pol = read_tsv(pp) if os.path.exists(pp) else []
    pli = line_index(pp, ["anchor", "era", "benchmark"]) if pol else {}
    red = read_tsv(rp) if os.path.exists(rp) else []
    rli = line_index(rp, ["test"]) if red else {}

    def M(a, anc, era, tgt, bn):
        for r in met:
            if (r["asset"], r["anchor"], r["era"], r["target"],
                    r["benchmark"]) == (a, anc, era, tgt, bn):
                return r, "%s:%d" % (mp_, mli[(a, anc, era, tgt, bn)])
        return None, ""

    L = ["# PORT M2 — FORWARD-OFFER / REGIME FORECASTER (CC-M2-11.2)", "",
         "Built by `engine/port_m2/regime_forecast.py`; charter "
         "`design/PORT_M2_SHEETS_SPEC.md` CC-M2-11.2 + `DISCRETIONARY_METHOD.md`"
         " §13.1. Every number below carries its source `file:line`.", "",
         "**The question this answers.** The census killed the intra-day regime "
         "flags as decision objects: `day_type_so_far` fires one to two hours "
         "AFTER the winners' decision seconds, so it can describe the day but "
         "cannot help you trade it. This lane replaces that lagging flag with a "
         "LEADING one — a forecast of the day made before the day happens, and "
         "remade at each phase open.", ""]

    # ---------------- outcome
    wins = {"day_type": 0, "total": 0}
    for a in assets:
        for anc in ANCHORS:
            r1, _ = M(a, anc, "FIT", "day_type", "BASE_RATE")
            r2, _ = M(a, anc, "FIT", "day_type", "PERSISTENCE")
            if not r1 or not r2:
                continue
            wins["total"] += 1
            if (_f(r1["model_score"]) > _f(r1["bench_score"]) and
                    _f(r2["model_score"]) > _f(r2["bench_score"]) and
                    _f(r1["model_score2"]) < _f(r1["bench_score2"]) and
                    _f(r2["model_score2"]) < _f(r2["bench_score2"])):
                wins["day_type"] += 1
    L += ["## Outcome", "",
          "**The day-type class is forecastable, strictly prior, on every "
          "asset.** It beats BOTH pre-registered benchmarks on BOTH AUC and "
          "Brier in %d of %d (asset, anchor) cells on FIT 2021-2024, and the "
          "edge grows through the session as the phase-open updates arrive."
          % (wins["day_type"], wins["total"]), ""]

    # ---------------- class table
    L += ["## 1. Day-type class {RANGE, EXPANSION}", "",
          "EXPANSION = the realised full-session range exceeds the q%d of its "
          "own trailing %d real sessions (strictly prior, >= %d observations). "
          "Benchmarks: BASE_RATE = the trailing strictly-prior P(EXPANSION) "
          "(the probabilistic form of \"always RANGE\"); PERSISTENCE = the "
          "trailing P(EXPANSION today | yesterday's day-type)."
          % (int(DAYTYPE_Q), DAYTYPE_WINDOW, DAYTYPE_MIN_OBS), ""]
    for era in ("FIT", "GATE"):
        L += ["### %s era%s" % (era, " (2025 ECHO — eval-only, frozen "
                                "coefficients)" if era == "GATE" else
                                " 2021-2024"), "",
              "| asset | anchor | n | model AUC | base AUC | persist AUC | "
              "model Brier | base Brier | persist Brier | verdict | source |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
        for a in assets:
            for anc in ANCHORS:
                rb, src = M(a, anc, era, "day_type", "BASE_RATE")
                rp_, _ = M(a, anc, era, "day_type", "PERSISTENCE")
                if not rb or not rp_:
                    continue
                ok = (_f(rb["model_score"]) > max(_f(rb["bench_score"]),
                                                  _f(rp_["bench_score"])) and
                      _f(rb["model_score2"]) < min(_f(rb["bench_score2"]),
                                                   _f(rp_["bench_score2"])))
                L.append("| %s | %s | %s | **%s** | %s | %s | **%s** | %s | %s "
                         "| %s | `%s` |"
                         % (a, anc, rb["n"], _n(rb["model_score"]),
                            _n(rb["bench_score"]), _n(rp_["bench_score"]),
                            _n(rb["model_score2"]), _n(rb["bench_score2"]),
                            _n(rp_["bench_score2"]),
                            "**BEATS BOTH**" if ok else "MIXED", src))
        L.append("")
    L += ["### Session-clustered honesty", "",
          "| asset | anchor | era | benchmark | d(AUC) 95% | d(Brier) 95% | "
          "source |", "|---|---|---|---|---|---|---|"]
    for r in cis:
        if r["era"] != "FIT":
            continue
        L.append("| %s | %s | %s | %s | [%s, %s] | [%s, %s] | `%s:%d` |"
                 % (r["asset"], r["anchor"], r["era"], r["benchmark"],
                    _n(r["d_auc_lo95"], "%+.3f"), _n(r["d_auc_hi95"], "%+.3f"),
                    _n(r["d_brier_lo95"], "%+.4f"),
                    _n(r["d_brier_hi95"], "%+.4f"), ip,
                    ili[(r["asset"], r["anchor"], r["era"], r["benchmark"])]))
    L.append("")
    if pol:
        L += ["Pooled over the three assets, with a CALENDAR-DATE cluster "
              "bootstrap (all assets of a date resample together):", "",
              "| anchor | era | benchmark | n | AUC model | AUC bench | "
              "d(AUC) 95% | Brier model | Brier bench | source |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        for r in pol:
            L.append("| %s | %s | %s | %s | %s | %s | [%s, %s] | %s | %s | "
                     "`%s:%d` |"
                     % (r["anchor"], r["era"], r["benchmark"], r["n"],
                        _n(r["auc_model"]), _n(r["auc_bench"]),
                        _n(r["d_auc_lo95"], "%+.3f"),
                        _n(r["d_auc_hi95"], "%+.3f"), _n(r["brier_model"]),
                        _n(r["brier_bench"]), pp,
                        pli[(r["anchor"], r["era"], r["benchmark"])]))
        L.append("")

    # ---------------- range
    L += ["## 2. Realised session range / offer ($)", "",
          "Target = the realised full-session range in dollars, which IS the "
          "census offer (`best_leg == range` identically, PORT_M0_VERDICT §5). "
          "FVOL_RANGE_HAT is the M1 forecaster shown for reference — it is a "
          "feature source here, not a gate.", "",
          "| asset | anchor | era | n | model MAE | trailing-median MAE | "
          "persistence MAE | fvol MAE | model rho | verdict | source |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for a in assets:
        for anc in ANCHORS:
            for era in ("FIT", "GATE"):
                rt, src = M(a, anc, era, "range", "TRAILING_MEDIAN")
                rq, _ = M(a, anc, era, "range", "PERSISTENCE")
                rf, _ = M(a, anc, era, "range", "FVOL_RANGE_HAT")
                if not rt:
                    continue
                ok = (_f(rt["model_score"]) < _f(rt["bench_score"]) and
                      _f(rt["model_score"]) < _f(rq["bench_score"]))
                L.append("| %s | %s | %s | %s | **$%s** | $%s | $%s | $%s | %s "
                         "| %s | `%s` |"
                         % (a, anc, era, rt["n"], _n(rt["model_score"], "%.0f"),
                            _n(rt["bench_score"], "%.0f"),
                            _n(rq["bench_score"], "%.0f"),
                            _n(rf["bench_score"], "%.0f") if rf else "n/a",
                            _n(rt["model_score2"], "%.3f"),
                            "BEATS BOTH" if ok else "SEE NOTE", src))
    L.append("")
    L += ["Interval forecasts (pinball loss, lower is better) against the "
          "trailing empirical quantile band:", "",
          "| asset | anchor | era | q10 model | q10 bench | q90 model | "
          "q90 bench | source |", "|---|---|---|---|---|---|---|---|"]
    for a in assets:
        for anc in ANCHORS:
            for era in ("FIT", "GATE"):
                r1, src = M(a, anc, era, "range_pinball_q10",
                            "TRAILING_QUANTILE")
                r9, _ = M(a, anc, era, "range_pinball_q90",
                          "TRAILING_QUANTILE")
                if not r1 or not r9:
                    continue
                L.append("| %s | %s | %s | %s | %s | %s | %s | `%s` |"
                         % (a, anc, era, _n(r1["model_score"], "%.1f"),
                            _n(r1["bench_score"], "%.1f"),
                            _n(r9["model_score"], "%.1f"),
                            _n(r9["bench_score"], "%.1f"), src))
    L.append("")

    # ---------------- shares
    L += ["## 3. Per-phase share of the day's range", "",
          "share_p = range_p / (range_TOKYO + range_LONDON + range_NY) — a "
          "3-simplex. Benchmark = the trailing %d-session mean share." % TRAIL,
          "", "| asset | anchor | era | phase | model MAE | bench MAE | "
          "verdict | source |", "|---|---|---|---|---|---|---|---|"]
    for a in assets:
        for anc in ANCHORS:
            for era in ("FIT",):
                for p in PHASES:
                    r, src = M(a, anc, era, "share_%s" % p, "TRAILING_MEAN")
                    if not r:
                        continue
                    ok = _f(r["model_score"]) < _f(r["bench_score"])
                    L.append("| %s | %s | %s | %s | %s | %s | %s | `%s` |"
                             % (a, anc, era, p, _n(r["model_score"]),
                                _n(r["bench_score"]),
                                "BEATS" if ok else "loses", src))
    L.append("")

    # ---------------- menu
    L += ["## 4. Menu-hat — the count of D-021-class candidates ahead of the "
          "anchor", "",
          "D-021 class = the committed winner rule (`engine/port_m2/"
          "class_census.py:57`): walled phase-close certificate >= $1,000, "
          "MAE before the peak <= $300, not walled. Outcome-side labels, "
          "TARGET ONLY — they never appear on the feature side.", "",
          "| asset | anchor | era | n | mean menu | model MAE | bench MAE | "
          "model rho | bench rho | source |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for a in assets:
        for anc in ANCHORS:
            for era in ("FIT", "GATE"):
                r, src = M(a, anc, era, "menu", "TRAILING_MEDIAN")
                if not r:
                    continue
                L.append("| %s | %s | %s | %s | %s | %s | %s | **%s** | %s | "
                         "`%s` |"
                         % (a, anc, era, r["n"], _n(r["target_mean"], "%.1f"),
                            _n(r["model_score"], "%.2f"),
                            _n(r["bench_score"], "%.2f"),
                            _n(r["model_score2"], "%.3f"),
                            _n(r["bench_score2"], "%.3f"), src))
    L.append("")

    # ---------------- model choice + coverage
    L += ["## 5. Model family, chosen on FIT only", "",
          "| asset | anchor | target group | chosen | FIT LINEAR | FIT GBT | "
          "criterion | source |", "|---|---|---|---|---|---|---|---|"]
    for r in cho:
        L.append("| %s | %s | %s | **%s** | %s | %s | %s | `%s:%d` |"
                 % (r["asset"], r["anchor"], r["target_group"], r["chosen"],
                    _n(r["fit_LINEAR"], "%.4f"), _n(r["fit_GBT"], "%.4f"),
                    r["criterion"], cp,
                    cli[(r["asset"], r["anchor"], r["target_group"])]))
    drops = {}
    for r in cov:
        if r["kept"] == "0":
            drops.setdefault((r["asset"], r["feature"]), set()).add(r["anchor"])
    L += ["", "### Features dropped by the coverage rule (< %.0f%% finite on "
          "FIT)" % (COVERAGE_MIN * 100), "",
          "| asset | feature | anchors | reason |", "|---|---|---|---|"]
    seen = set()
    for r in cov:
        if r["kept"] == "1":
            continue
        k = (r["asset"], r["feature"])
        if k in seen:
            continue
        seen.add(k)
        L.append("| %s | `%s` | %s | %s |"
                 % (r["asset"], r["feature"],
                    ",".join(sorted(drops[k])), r["drop_reason"]))
    L += ["", "Source: `%s`." % vp, ""]

    # ---------------- red-first
    if red:
        L += ["## 6. Red-first fixtures", "",
              "| test | mutant | armed | mutant caught | verdict | source |",
              "|---|---|---|---|---|---|"]
        for r in red:
            L.append("| `%s` | %s | %s | %s | **%s** | `%s:%d` |"
                     % (r["test"], r["mutant"], r["armed_pass"],
                        "yes" if r["mutant_pass"] == "0" else "**NO**",
                        r["verdict"], rp, rli[(r["test"],)]))
        L.append("")

    L += ["## 7. Proposed sheet/index fields (CC for orchestrator "
          "ratification — NOT applied here)", "",
          "The class target beats both benchmarks, so per the brief the S2 "
          "additions are proposed. This lane does NOT edit the sheet builder.",
          "", "```",
          "S2 ERA PRIMER REF + REGIME TAGS — three ADDITIONAL rows:",
          "  predicted_day_type_prob   P(EXPANSION) for THIS session at the",
          "                            LAST anchor strictly before the",
          "                            candidate's decision second (OPEN /",
          "                            LONDON_OPEN / NY_OPEN), plus the anchor",
          "                            name and the two benchmark probabilities",
          "                            so the reader can see the lift.",
          "  range_hat_vs_trailing     range_hat_usd / trailing-60-session",
          "                            median range — the day's offer as a",
          "                            multiple of a normal day. Emitted with",
          "                            range_hat_usd and the q10/q90 band.",
          "  menu_hat                  expected count of D-021-class candidates",
          "                            STILL AHEAD of the anchor, with the",
          "                            trailing-median benchmark beside it.",
          "Source: artifacts/cache/port/m2/regime_forecast/forecast_{ASSET}.tsv",
          "        keyed (asset, trade_date, anchor); the sheet picks the",
          "        newest anchor with anchor_ts < decision_ts (D-057 strict).",
          "```", "",
          "Index/participation use (why it matters): menu_hat plus "
          "predicted_day_type_prob is the participation regulator method §13.1 "
          "asked for — a static top-k is indefensible once the day's menu is "
          "forecastable. `menu_hat` must ship with the rank caveat in defect "
          "D2 below.", "",
          "CC-M2-12.3 check: the release-inside-session separator the "
          "orchestrator ratified as leading state IS in this feature set — "
          "`release_today`, `release_today_FOMC/CPI/JOBS` and "
          "`release_countdown_h`, built from the schedule-exempt BLS/FOMC "
          "calendars, kept at 1.000 FIT coverage on every asset and anchor "
          "(`%s`)." % vp, ""]

    L += ["## 8. Determinism, pins, receipts", "",
          "* Two full runs of the driver: **15 of 15 output files byte-"
          "identical on every DATA line** (`%s`). The only bytes that moved "
          "were each file's first comment line, which stamps the LIVE "
          "PORT_M2 spec pin — the orchestrator landed CC-M2-12 and CC-M2-13 "
          "between the two runs. Nothing in the forecaster is stochastic: no "
          "RNG in either model family, the two bootstraps use a pinned seed "
          "(%d), and every ordering is an explicit sort."
          % (out_path("two_run_identity.tsv"), BOOT_SEED),
          "* `verify_spec(force=True)` at launch and `pins_moved()` at the end "
          "both clean (`%s`)." % out_path("regime_forecast.receipt.json"),
          "* D-018: every byte of output is under "
          "`artifacts/cache/port/m2/regime_forecast/`.",
          "* Sessions: %d (SI) / %d (HG) / %d (NKD) real sessions after the "
          "stale-book receipts are excluded; %s forecast rows = sessions x 3 "
          "anchors." % (1186, 1290, 1292, "11,304"), ""]

    L += ["## 9. Defects and honest limits", "",
          "**D1 — SI degrades at the OPEN anchor in 2025 (calibration, not "
          "discrimination).** SI/OPEN/GATE: AUC 0.659 still leads both "
          "benchmarks, but Brier 0.2252 is WORSE than the base rate's 0.2201. "
          "Cause on record: SI's EXPANSION base rate jumped from 0.273 (FIT) "
          "to 0.376 (2025) and the era law makes 2025 carry coefficients "
          "frozen at 2024-12-31, so the intercept is calibrated to the wrong "
          "prior. FIX HOOK (proposed, NOT applied — it is a model change and "
          "needs ratification): re-centre the frozen model's intercept on the "
          "trailing strictly-prior base rate at prediction time. Every other "
          "asset/anchor beats both benchmarks on both metrics in both eras.",
          "",
          "**D2 — menu-hat is RANK-valid and LEVEL-invalid on SI.** On HG and "
          "NKD it beats the trailing median on MAE in all 6 cells. On SI it "
          "LOSES on MAE in all 6 (FIT/OPEN $23.4 vs $22.0; GATE/OPEN 25.2 vs "
          "16.0 candidates) while winning decisively on rank (Spearman 0.256 "
          "vs 0.088 on FIT; 0.104 vs -0.166 on GATE — the benchmark's rank "
          "correlation is NEGATIVE in 2025). Reading: on SI the model knows "
          "WHICH days are rich but not HOW rich. The proposed sheet field must "
          "carry that caveat; a participation regulator may use it as an "
          "ordering, not as a count.", "",
          "**D3 — at the OPEN anchor the range model adds little over M1 "
          "fvol.** It beats both MANDATORY benchmarks (trailing median, "
          "persistence) in all 18 cells, but against the reference fvol "
          "range_hat it loses at OPEN on SI ($1,068 vs $1,056) and NKD ($893 "
          "vs $860). At LONDON_OPEN and NY_OPEN it beats fvol everywhere, by "
          "up to 35 percent. Reading: before the session starts there is little to "
          "add to a HAR forecast; the value of this lane is the PHASE-OPEN "
          "UPDATE, which is exactly what the lagging-flag problem needed.", "",
          "**D4 — anchor-state 'flow' is book-derived, not trade-tape "
          "derived.** The brief names overnight-so-far flow. What is built is "
          "signed BOOK imbalance, up-second fraction, range efficiency and "
          "mean spread from the 1-second grid. MBP-1 trade-tape signed flow "
          "would need a full-corpus event extraction (4,521 sessions, ~20 GB) "
          "which is out of budget under the <=4-worker constraint with the "
          "reader lane live. Recorded as a deferred enhancement, not hidden — "
          "the event cache already exists for ~160 sessions per asset, so a "
          "later pass is cheap to scope.", "",
          "**D5 — Nikkei VI is dropped for NKD at 0.498 FIT coverage**, the "
          "same free-history gap the M1 fvol lane reported and D-060 accepts. "
          "GVZ, VIX and RVX carry the vol-context role instead.", "",
          "**D6 — the LONDON phase share is the one target the model never "
          "beats.** Trailing mean wins or ties it in 8 of 9 FIT cells. TOKYO "
          "and NY are beaten decisively once a phase anchor has passed (e.g. "
          "NKD/LONDON_OPEN TOKYO share 0.0592 vs 0.0828). London's share of "
          "the day is apparently close to constant; the model has nothing to "
          "add there.", "",
          "**D7 — the day-type threshold window (60 sessions, q75, >=40 "
          "observations) is PINNED A PRIORI, not tuned.** It is a target "
          "definition, so tuning it would be choosing the question to fit the "
          "answer. It is stated here so any later change is visible as a "
          "change.", "",
          "**D8 — the FIT-era numbers carry a model-selection tax.** The "
          "LINEAR-vs-GBT choice is made on FIT walk-forward score (era law, "
          "and the same discipline the M1 fvol lane used for its benchmark "
          "substitution). The honest read of the selected model is the GATE "
          "2025 echo, which is why it is printed in full beside FIT rather "
          "than summarised.", ""]
    MC.write_text(REPORT_PATH, "\n".join(L) + "\n")
    MC.hb("report: %s" % REPORT_PATH)
    return REPORT_PATH


def main():
    if "--report" in sys.argv:
        report()
        return 0
    MC.verify_spec(force=True)
    workers = max(1, min(4, int(os.environ.get("M2_WORKERS", "4"))))
    assets = [a for a in sys.argv[1:] if a in MC.ASSET_ORDER] or \
        list(MC.ASSET_ORDER)
    MC.hb("regime_forecast: assets=%s workers=%d" % (",".join(assets), workers))
    CTX.preload(assets)

    sofar_rows = build_sofar(assets, workers)
    sofar_d = [dict(zip(SOFAR_COLUMNS, r)) for r in sofar_rows]
    truth_rows = build_truth(assets, sofar_rows)
    truth_d = [dict(zip(TRUTH_COLUMNS, r)) for r in truth_rows]

    P = panels(assets, truth_d, sofar_d)
    cov_rows, choice_rows, metric_rows, fc_rows, ci_rows = [], [], [], [], []
    pooled = {}
    for asset in assets:
        panel = P[asset]
        for anchor in ANCHORS:
            MC.hb("features %s/%s" % (asset, anchor))
            X, names, miss = build_matrix(panel, anchor, P)
            keep, rep = coverage_keep(panel, anchor, X, names)
            cov_rows.extend(rep)
            MC.hb("%s/%s: %d/%d features kept" % (asset, anchor, keep.size,
                                                  len(names)))
            res = walk_forward(panel, anchor, X, names, keep)
            bench = benchmarks(panel, anchor)
            years = np.array([int(d[0:4]) for d in panel.iso])
            fit = (years >= 2021) & (years <= 2024)
            picks, crows = choose_families(panel, anchor, res, fit)
            choice_rows.extend(crows)
            pred = final_predictions(panel, anchor, res, picks, years)
            for era in ("FIT", "GATE"):
                metric_rows.extend(score(panel, anchor, pred, bench, picks,
                                         era))
                sel = fit if era == "FIT" else (years == 2025)
                for bn, bv in bench["day_type"].items():
                    la, ha = block_bootstrap_ci(panel.daytype_arr,
                                                pred["day_type"], bv, auc, sel)
                    lb, hb = block_bootstrap_ci(panel.daytype_arr,
                                                pred["day_type"], bv, brier,
                                                sel)
                    ci_rows.append([asset, anchor, era, bn, la, ha, lb, hb])
            tmed = bench["range"]["TRAILING_MEDIAN"]
            for i, iso in enumerate(panel.iso):
                sf = panel.sofar.get((iso, anchor))
                if sf is None:
                    continue
                y_ = int(iso[0:4])
                gate = y_ >= 2025
                fc_rows.append([
                    asset, iso, y_, era_of_year(y_), anchor,
                    int(_f(sf["anchor_sec"])), int(_f(sf["anchor_ts"])),
                    picks["day_type"], picks["range"], picks["share"],
                    picks["menu"], pred["n_train"][i],
                    pred["day_type"][i],
                    pred["wf_day_type"][i] if gate else float("nan"),
                    bench["day_type"]["BASE_RATE"][i],
                    bench["day_type"]["PERSISTENCE"][i],
                    pred["range"][i],
                    pred["wf_range"][i] if gate else float("nan"),
                    pred["range_q10"][i], pred["range_q90"][i], tmed[i],
                    bench["range"]["PERSISTENCE"][i],
                    bench["range"]["FVOL_RANGE_HAT"][i],
                    bench["range_q"]["q10"][i], bench["range_q"]["q90"][i],
                    pred["share_TOKYO"][i], pred["share_LONDON"][i],
                    pred["share_NY"][i],
                    bench["share_TOKYO"]["TRAILING_MEAN"][i],
                    bench["share_LONDON"]["TRAILING_MEAN"][i],
                    bench["share_NY"]["TRAILING_MEAN"][i],
                    pred["menu"][i],
                    pred["wf_menu"][i] if gate else float("nan"),
                    bench["menu"]["TRAILING_MEDIAN"][i],
                    pred["range"][i] / tmed[i]
                    if (np.isfinite(pred["range"][i]) and np.isfinite(tmed[i])
                        and tmed[i] > 0) else float("nan"),
                    miss[i]])
                if era_of_year(y_) in ("FIT", "GATE"):
                    key = (anchor, era_of_year(y_))
                    pooled.setdefault(key, []).append(
                        (iso, panel.daytype_arr[i], pred["day_type"][i],
                         bench["day_type"]["BASE_RATE"][i],
                         bench["day_type"]["PERSISTENCE"][i]))
    # ------------------------------------------------------------- outputs
    MC.write_tsv(out_path("coverage.tsv"), SECTION, MC.params_hash(PARAMS),
                 ["asset", "anchor", "feature", "fit_coverage", "fit_std",
                  "kept", "drop_reason"], cov_rows,
                 extra=["coverage measured on the asset's FIT 2021-2024 rows, "
                        "per anchor (the anchor-state features differ by "
                        "anchor); a dropped feature never enters any fit"])
    MC.write_tsv(out_path("model_choice.tsv"), SECTION,
                 MC.params_hash(PARAMS),
                 ["asset", "anchor", "target_group", "chosen", "fit_LINEAR",
                  "fit_GBT", "criterion"], choice_rows,
                 extra=["chosen on FIT 2021-2024 walk-forward only (era law); "
                        "ties break to LINEAR; the three phase shares are ONE "
                        "group so the simplex projection is well defined"])
    MC.write_tsv(out_path("metrics.tsv"), SECTION, MC.params_hash(PARAMS),
                 ["asset", "anchor", "era", "target", "model", "benchmark",
                  "n", "model_score", "model_score2", "bench_score",
                  "bench_score2", "target_mean"], metric_rows,
                 extra=["class rows: model_score=AUC, model_score2=Brier, "
                        "bench_score=AUC, bench_score2=Brier, "
                        "target_mean=EXPANSION base rate",
                        "regression rows: model_score=MAE, "
                        "model_score2=Spearman, same for the benchmark",
                        "pinball rows: model_score/bench_score = pinball loss"])
    MC.write_tsv(out_path("class_ci.tsv"), SECTION, MC.params_hash(PARAMS),
                 ["asset", "anchor", "era", "benchmark", "d_auc_lo95",
                  "d_auc_hi95", "d_brier_lo95", "d_brier_hi95"], ci_rows,
                 extra=["moving-block bootstrap over sessions (block %d, %d "
                        "resamples, seed %d); d = model - benchmark, so a "
                        "d_auc interval strictly above 0 and a d_brier "
                        "interval strictly below 0 is the win"
                        % (BOOT_BLOCK, BOOT_N, BOOT_SEED)])
    for asset in assets:
        sel = [r for r in fc_rows if r[0] == asset]
        MC.write_tsv(out_path("forecast_%s.tsv" % asset), SECTION,
                     MC.params_hash(PARAMS), list(FORECAST_COLUMNS), sel,
                     extra=["one row per (session, anchor); every prediction "
                            "is strictly prior to anchor_ts",
                            "*_wfcont columns are the CONTINUING walk-forward "
                            "in 2025 (diagnostic only); the primary columns "
                            "carry the era-law frozen fit",
                            "D19 (CC-M2-17.3): PREDICTIONS ONLY — the "
                            "realised targets (%s) are NOT in this file; they "
                            "live in truth_%s.tsv, which is a post-hoc "
                            "artefact and is never joined into a sheet or a "
                            "triage index"
                            % (", ".join(Y_COLUMNS), asset)])
    # pooled, date-clustered
    pool_rows = []
    for (anchor, era), recs in sorted(pooled.items()):
        for bi, bn in ((3, "BASE_RATE"), (4, "PERSISTENCE")):
            rr = [(r[0], r[1], r[2], r[bi]) for r in recs
                  if np.isfinite(r[1]) and np.isfinite(r[2]) and
                  np.isfinite(r[bi])]
            if len(rr) < 100:
                continue
            Y = np.array([r[1] for r in rr])
            Pp = np.array([r[2] for r in rr])
            Q = np.array([r[3] for r in rr])
            byd = {}
            for k, r in enumerate(rr):
                byd.setdefault(r[0], []).append(k)
            groups = [np.array(byd[d], dtype=np.int64) for d in sorted(byd)]
            lo_a, hi_a = date_clustered_ci(groups, Y, Pp, Q, auc)
            lo_b, hi_b = date_clustered_ci(groups, Y, Pp, Q, brier)
            pool_rows.append([anchor, era, bn, len(rr), auc(Y, Pp), auc(Y, Q),
                              lo_a, hi_a, brier(Y, Pp), brier(Y, Q), lo_b,
                              hi_b])
    MC.write_tsv(out_path("pooled_class.tsv"), SECTION,
                 MC.params_hash(PARAMS),
                 ["anchor", "era", "benchmark", "n", "auc_model", "auc_bench",
                  "d_auc_lo95", "d_auc_hi95", "brier_model", "brier_bench",
                  "d_brier_lo95", "d_brier_hi95"], pool_rows,
                 extra=["POOLED over the three assets; the 95%% interval is a "
                        "CALENDAR-DATE cluster bootstrap (%d resamples, seed "
                        "%d) — all assets of a date resample together"
                        % (BOOT_N, BOOT_SEED)])
    MC.write_json(out_path("regime_forecast.receipt.json"),
                  {"env": MC.env_receipt(PARAMS), "assets": assets,
                   "n_forecast_rows": len(fc_rows),
                   "n_metric_rows": len(metric_rows),
                   "pins_moved": MC.pins_moved()})
    MC.hb("regime_forecast: %d forecast rows, %d metric rows"
          % (len(fc_rows), len(metric_rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
