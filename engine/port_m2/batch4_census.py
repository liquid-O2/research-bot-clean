#!/usr/bin/python3
"""PORT M2 — CENSUS BATCH 4: P030 / P031 / THE CELL-SEAT EXISTENCE CENSUS.

CC-M2-17 (BINDING) decomposed the decision into three stages — (1) SEAT
EXISTENCE, (2) CELL SIDE, (3) MOMENT — and ordered this batch as stage 1's
evidence base:

  "5. CENSUS BATCH 4 ORDERED: P030 CELL_VOL_CONCENTRATION (threshold sweep —
   the 150-vs-250 floor question), P031 CROSS_ASSET_FUEL_OVERHANG (the day-6
   winner evidence), and the CELL-SEAT EXISTENCE census (fraction of cells
   offering D-021 seats; predictability from rv1800-at-cell-open, menu-hat
   class where available, prior-cell outcomes — stage-1 of the decomposition,
   mirror+Holm discipline)."

THE UNIT OF ANALYSIS IS THE CELL, NOT THE CANDIDATE.  A CELL is
(asset, session, phase_dec) — the object a seat is spent in under CC-M2-10.3
phase-close seating.  Everything below is a cell-level statistic; the candidate
grain appears only inside a cell's own aggregates.  This is the batch's one
structural departure from batches 1-3 and it is the whole point: E1 day 6 lost
a replay with a 0.600-accurate SIDE call because four of nine cells had no
winner on EITHER side, and no candidate-grain census can see that.

WHAT IS CENSUSED
----------------
P030 CELL_VOL_CONCENTRATION — a FEASIBILITY/MAGNITUDE object with no mirror.
  Ledger fields: "S9 rv_nowcast w1800 on the FIRST candidate row of the
  (asset, phase) cell ; S14 winner_close aggregated to the cell ; S1 phase_dec
  + asset as the cell key."  Day 6 measured it on 54 cells and left the
  threshold explicitly UNSETTLED: a floor at 150 refuses HG/LONDON at rv 142.5,
  the day's BEST seat (+$1,338.75, 17 winners), and costs 8 of 8 on
  2021-07-05.  So this census reports it AS A CURVE, not a point:
    * BANDS   the day-6 band table (<100 / 100-150 / 150-250 / >=250) re-run at
              era scale, per asset x era, with winner content and BOTH
              certificate readings;
    * SWEEP   every floor on a dense grid, each row carrying what the floor
              BUYS (seat rate above, winner share retained) and what it COSTS
              (winners refused, best refused cell, cells refused) — the two
              halves of the 150-vs-250 question in one table;
    * GEE     logit of "this cell has a seat" on rv1800-at-open, and identity
              GEE of the cell's winner count, session-clustered.

P031 CROSS_ASSET_FUEL_OVERHANG — DIRECTIONAL, so the MIRROR LAW applies.
  Ledger fields: "S8 FUEL MAP trapped_above/trapped_below/phase_total of asset
  A's completed phase ; S8 phase sflow sign and magnitude ; the (asset, phase)
  cell of assets B, C that opens next."  The day-6 form exactly: SI's TOKYO
  fuel map (7,424 above / 1,211 below / 8,635 total, 86% trapped ABOVE) called
  HG/LONDON and NKD/LONDON SHORT (both right, both winning seats) and SI's own
  LONDON SHORT (wrong, -$930).  Censused as:
    SOURCE   for each target cell, the most recent cell of each OTHER asset
             whose phase CLOSED at or before this cell's open (wall-clock, so
             the assets' different session grids are handled honestly).  The
             overhang is read off that source cell's LAST candidate row, which
             is strictly prior to the target cell's open.
    CALL     trapped_against share >= THR -> the side that must absorb it:
             above/total >= THR -> SHORT, below/total >= THR -> LONG, else
             NO-CALL (scored as a miss, so abstention is not free).
    SCORE    agreement with the cell's WINNER-MAJORITY side, against its
             MIRROR, per (source_asset -> target_asset) pair, per era; NKD legs
             included in both directions.  The OWN-asset leg (A == B) is
             carried as the control — it is P009 FUEL_POLARITY, dead twice.
    MIRROR   side_probe's mirror_rows discipline: per-session win/tie/loss and
             `mirror_law_holds` = lost == 0 and won > 0, plus the session-level
             sign test.  A directional claim that does not beat its own mirror
             on every session does not exist (CC-M2-13.1).

CELL-SEAT EXISTENCE (stage 1 of CC-M2-17.1) — THE HIGHEST-VALUE ITEM.
  BASE RATES  P(cell contains >= 1 D-021-class walled winner) per asset x phase
              x era, with the winner-count distribution beside it.
  MODEL       GEE logit on STRICTLY-PRIOR cell-open features:
                rv1800          S9 rv nowcast (1800s) on the cell's first row
                prev_ret_sign   sign of the previous phase segment's net move
                prev_ret_mag    |that move| in dollars
                overnight_ratio pre-cell session range / ATR14_prev
                release_in_ph   a SCHEDULED release falls inside this phase
                                (calendar-only, D-057 — knowable at cell open)
                dow             day of week (calendar)
                menu_hat        the accepted forecaster's expected D-021-class
                                candidate count at the newest anchor STRICTLY
                                before the cell open (2022+; D20: the
                                forecaster has no 2021 output at all)
              Two feature sets, because menu_hat does not exist before 2022:
                BASE       everything except menu_hat, all years
                PLUS_MENU  BASE + menu_hat, 2022+ only
  AUC         WALK-FORWARD: for each year Y, fit on every FIT year < Y and
              score Y; the GATE-2025H1 echo is scored from the frozen
              all-FIT fit (era law).  Reported per era with the base rate
              beside it, and with per-feature univariate AUC + leave-one-out
              dAUC so "which features carry it" is answered by measurement.

DISCIPLINE (batches 1-3, restated so this file reads alone)
  * population = frozen v3 roster, every FIT session (2021-2024) of all three
    assets, plus the GATE-2025 **H1 ONLY** echo.  CC-M2-15.3 corrected the
    D-058 pre-exam holdout to 2025-07-01 onward; batch 4 NEVER LOADS a session
    on or after that date — the quarantine is a filter on the job list, not a
    flag on a row, and the receipt stamps the count it refused.
  * BOTH CC-M1-8 certificate readings (walled phase-close = adoption, walled
    peak-exit = companion) on every value row.
  * DESTRUCTION: the carrying field is shuffled WITHIN ITS OWN SESSION (P030:
    rv1800 across the session's cells; P031: the source overhang across the
    date's cells), 40 replicates, seeded.  The destroyed quantity is the EDGE.
  * INFERENCE: GEE, independence working correlation, Liang-Zeger sandwich
    clustered on SESSION (CR0 + Cameron-Miller CR1) + Kish ICC/DEFF/n_eff.
    P031 is a CROSS-ASSET object, so it is additionally reported clustered on
    the DATE (all three assets of one day are one cluster) — both readings, the
    date-clustered one being the conservative one.
  * HOLM-BONFERRONI over THE WHOLE BATCH — every GEE test of all three objects
    is one family.
  * CONCENTRATOR-vs-RULE vocabulary (CC-M2-9.1): a Holm-significant beta on the
    adoption metric is a RULE; a >= 1.25x winner-rate or conditional-value
    ratio with no adoption edge is a CONCENTRATOR and goes to the feature
    candidate set only; otherwise NULL.

OUTPUT (D-018: bulk under artifacts/cache/)
  artifacts/cache/port/m2/pattern_census/BATCH4_CENSUS_REPORT.md
  artifacts/cache/port/m2/pattern_census/
      BATCH4_CELLS.tsv            one row per cell (the census population)
      P030_BANDS.tsv              the day-6 band table at era scale
      P030_SWEEP.tsv              the threshold CURVE
      P031_PAIRS.tsv              agreement vs mirror, per asset pair
      P031_MIRROR.tsv             the per-session mirror law
      P031_SENSITIVITY.tsv        the overhang threshold sweep
      SEAT_BASE_RATES.tsv         stage-1 base rates
      SEAT_MODEL.tsv              GEE coefficients (both feature sets)
      SEAT_AUC.tsv                walk-forward AUC + univariate + LOO dAUC
      BATCH4_DESTRUCTION.tsv      mechanism destruction
      BATCH4_ROBUST.tsv           every GEE test, one Holm family
      batch4_census.receipt.json

Run:  lab/run.sh port-m2-batch4 -- /usr/bin/python3 engine/port_m2/batch4_census.py
"""
import argparse
import math
import os
import sys
import time

import multiprocessing as mp

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_M1 = "/workspace/engine/port_m1"
if _M1 not in sys.path:
    sys.path.insert(0, _M1)

import m2_common as MC                    # noqa: E402
import pattern_lib as PL                  # noqa: E402
import census_common as X                 # noqa: E402
import episode_v2 as EV                   # noqa: E402  (GEE sandwich, ICC)
import p001_census as P1                  # noqa: E402  (census machinery)

SECTION = ("DISCRETIONARY_METHOD §4.2 name->count census — batch 4 "
           "(CC-M2-17.5: P030 / P031 / CELL-SEAT EXISTENCE)")
OUT_DIR = MC.out_path("pattern_census", "_")[:-1]

FIT_YEARS = P1.FIT_YEARS                  # (2021, 2022, 2023, 2024)
GATE_YEAR = P1.GATE_YEAR                  # 2025
HOLDOUT_FROM_D8 = 20250701                # CC-M2-15.3, corrected D-058 boundary
PHASES = X.PHASE_NAMES                    # ("TOKYO", "LONDON", "NY")

# ---- P030 -------------------------------------------------------------------
# the day-6 band edges, kept verbatim so the era table is comparable to the
# 54-cell table the pattern was born on
P030_BANDS = ((0.0, 100.0), (100.0, 150.0), (150.0, 250.0), (250.0, 1e18))
P030_BAND_NAMES = ("lt100", "100-150", "150-250", "ge250")
# the sweep: dense through the contested region, coarse outside it
P030_SWEEP_GRID = tuple([0.0] + [float(v) for v in range(50, 501, 25)]
                        + [600.0, 800.0, 1000.0])

# ---- P031 -------------------------------------------------------------------
P031_THR = 0.65                           # e1d6_cellside C4's declared form
P031_THR_GRID = (0.55, 0.60, 0.65, 0.70, 0.75, 0.80)

# ---- the seat model ---------------------------------------------------------
SEAT_FEATURES_BASE = ("rv1800", "prev_ret_sign", "prev_ret_mag",
                      "overnight_ratio", "release_in_ph", "dow_sin", "dow_cos")
SEAT_FEATURES_MENU = SEAT_FEATURES_BASE + ("menu_hat",)
MENU_FROM_YEAR = 2022                     # D20: no forecaster output in 2021

CONCENTRATOR_MIN = 1.25
DESTRUCTION_REPS = P1.DESTRUCTION_REPS    # 40
DESTRUCTION_SEED = 20260817

PARAMS = {
    "spec_section": SECTION,
    "order": "CC-M2-17.5 — census batch 4 (P030, P031, CELL-SEAT EXISTENCE)",
    "definition_source": "provenance/port_m2/PATTERN_LEDGER.tsv (P030, P031) "
                         "+ provenance/port_m2/E1_POSTMORTEMS.md day-6 + "
                         "engine/port_m2/e1d6_cellside.py C4",
    "unit": "THE CELL = (asset, session, phase_dec) — the CC-M2-10.3 "
            "phase-close seat's own object, not the candidate",
    "seat": "a cell HAS A SEAT when it contains >= 1 D-021-class winner: "
            "walled phase-close certificate >= $1,000 AND mae_before_argmax "
            "<= $300 AND the $-wall was never hit",
    "cell_open": "the FIRST candidate row of the cell by decision second; "
                 "every cell-open feature is read off that row and is "
                 "therefore strictly prior to any seat that cell can offer",
    "P030": "rv1800 at cell open vs cell winner content. Reported as a CURVE "
            "(threshold sweep over %d floors) and as the day-6 band table at "
            "era scale, per asset x era. It has NO MIRROR to fail (a "
            "feasibility object like P025) and can therefore only ever grade "
            "as a CONCENTRATOR, never as an entry rule."
            % len(P030_SWEEP_GRID),
    "P031": "DIRECTIONAL. Source = the most recent CLOSED cell of another "
            "asset (wall-clock), read at its last candidate row: "
            "trapped_above/phase_total >= %.2f -> target cell SHORT; "
            "trapped_below/phase_total >= %.2f -> LONG; else NO-CALL, scored "
            "as a miss. Target = the cell's winner-majority side. The MIRROR "
            "is scored on every cell and every session (CC-M2-13.1); the "
            "OWN-asset leg is the P009 control." % (P031_THR, P031_THR),
    "P031_clustering": "reported clustered on SESSION (asset, d8) AND on DATE "
                       "(d8) — a cross-asset estimator's cells inside one day "
                       "are not independent, and the date-clustered CR1 is "
                       "the conservative reading",
    "seat_model": "GEE logit of has_seat on strictly-prior cell-open "
                  "features; BASE = %s (all years); PLUS_MENU = BASE + "
                  "menu_hat (%d+ only, D20: the accepted forecaster has no "
                  "2021 output)" % (",".join(SEAT_FEATURES_BASE),
                                    MENU_FROM_YEAR),
    "seat_auc": "WALK-FORWARD: year Y is scored by a fit on the FIT years "
                "strictly before it; the GATE echo is scored by the frozen "
                "all-FIT fit (era law, D-058). Univariate AUC and "
                "leave-one-out dAUC name which features carry it.",
    "menu_hat_join": "the newest forecaster anchor STRICTLY BEFORE the cell's "
                     "open second (CC-M2-1.2 availability law); "
                     "menu_hat ships with the CC-M2-14.1 RANK-VALID caveat",
    "value": "c_c_roster.certificates — walled PHASE-CLOSE (adoption) and "
             "walled PEAK-EXIT (CC-M1-8 companion), both always reported",
    "population": "frozen v3 roster, FIT years %s; %d-H1 as an EVAL-ONLY GATE "
                  "echo. HOLDOUT QUARANTINE: sessions with d8 >= %d are NEVER "
                  "LOADED (CC-M2-15.3 corrected the D-058 pre-exam holdout to "
                  "2025-07-01 onward)"
                  % (list(FIT_YEARS), GATE_YEAR, HOLDOUT_FROM_D8),
    "destruction": "the carrying field shuffled WITHIN SESSION, %d replicates, "
                   "RandomState(%d + index); the destroyed quantity is the "
                   "EDGE" % (DESTRUCTION_REPS, DESTRUCTION_SEED),
    "inference": "CC-M1-12.4 — GEE independence working correlation with the "
                 "Liang-Zeger sandwich (CR0 + Cameron-Miller CR1); Kish "
                 "one-way ICC/DEFF for n_eff; Holm-Bonferroni over THE WHOLE "
                 "BATCH",
    "grading": "CC-M2-9.1 — ENTRY/VETO RULE (Holm-significant beta on the "
               "adoption metric) vs CONCENTRATOR (>= %.2fx winner rate or "
               "conditional value, no adoption edge -> feature candidate set "
               "only) vs NULL" % CONCENTRATOR_MIN,
    "P030_bands": [list(b) for b in P030_BANDS],
    "P030_sweep": list(P030_SWEEP_GRID),
    "P031_thresholds": list(P031_THR_GRID),
    "frame": PL.PARAMS_FRAME,
    "frame_v2": PL.PARAMS_FRAME_V2,
    "frame_v3": PL.PARAMS_FRAME_V3,
}


# ======================================================================== scan
CELL_KEYS_F = ("rv1800_open", "rv60_open", "atr_open", "prev_ret_usd",
               "prev_range_usd", "pre_cell_range_usd", "mean_close",
               "mean_peak", "sum_close", "sum_peak", "cond_close",
               "win_close_sum", "win_close_sum_long", "win_close_sum_short",
               "src_share_above", "src_share_below", "menu_hat",
               "open_mid", "close_fuel_share_above", "close_fuel_share_below")
CELL_KEYS_I = ("d8", "year", "phase", "n_cand", "n_win", "n_win_long",
               "n_win_short", "n_walled", "first_dec_sec", "last_dec_sec",
               "open_ts", "close_ts", "release_in_ph", "dow",
               "close_fuel_above", "close_fuel_below", "close_fuel_total",
               "close_sflow")


def _cells_of(f):
    """Collapse one session's frame into its (asset, phase_dec) CELLS."""
    out = []
    dec = f["dec_sec"].astype(np.int64)
    ph = f["phase_dec"].astype(np.int64)
    cert_c = f["cert_close_usd"].astype(np.float64)
    cert_p = f["cert_peak_usd"].astype(np.float64)
    win = f["winner"].astype(bool)
    side = f["side"].astype(np.int64)
    open_utc = int(f["open_utc"])
    for p in sorted(set(ph.tolist())):
        m = np.nonzero(ph == p)[0]
        if m.size == 0:
            continue
        first = m[np.argmin(dec[m])]
        last = m[np.argmax(dec[m])]
        pos = cert_c[m][cert_c[m] > 0]
        w = win[m]
        tot = float(f["fuel_total"][last])
        rec = {
            "asset": f["asset"], "d8": int(f["d8"]),
            "year": int(f["d8"]) // 10000, "phase": int(p),
            "n_cand": int(m.size), "n_win": int(w.sum()),
            "n_win_long": int((w & (side[m] > 0)).sum()),
            "n_win_short": int((w & (side[m] < 0)).sum()),
            "n_walled": int(f["walled"][m].sum()),
            "first_dec_sec": int(dec[first]), "last_dec_sec": int(dec[last]),
            "open_ts": open_utc + int(dec[first]),
            "close_ts": open_utc + int(dec[last]),
            "release_in_ph": int(bool(f["sched_release_in_phase"][first])),
            "dow": int(f["dow"][first]),
            # ---- cell-OPEN features (strictly prior to any seat) ----
            "rv1800_open": float(f["rv1800_usd"][first]),
            "rv60_open": float(f["rv60_usd"][first]),
            "atr_open": float(f["atr_usd"][first]),
            "prev_ret_usd": float(f["prev_phase_ret_usd"][first]),
            "prev_range_usd": float(f["prev_phase_range_usd"][first]),
            "pre_cell_range_usd": float(f["pre_cell_range_usd"][first]),
            "open_mid": float(f["mid_now"][first]),
            # ---- cell-CLOSE fuel map (the P031 SOURCE, never a self-feature)
            "close_fuel_above": int(f["fuel_above"][last]),
            "close_fuel_below": int(f["fuel_below"][last]),
            "close_fuel_total": int(f["fuel_total"][last]),
            "close_sflow": int(f["fph_sflow"][last]),
            "close_fuel_share_above": (float(f["fuel_above"][last]) / tot
                                       if tot > 0 else float("nan")),
            "close_fuel_share_below": (float(f["fuel_below"][last]) / tot
                                       if tot > 0 else float("nan")),
            # ---- value ----
            "mean_close": float(cert_c[m].mean()),
            "mean_peak": float(cert_p[m].mean()),
            "sum_close": float(cert_c[m].sum()),
            "sum_peak": float(cert_p[m].sum()),
            "cond_close": float(pos.mean()) if pos.size else float("nan"),
            "win_close_sum": float(cert_c[m][w].sum()),
            "win_close_sum_long": float(cert_c[m][w & (side[m] > 0)].sum()),
            "win_close_sum_short": float(cert_c[m][w & (side[m] < 0)].sum()),
            # filled by the cross-asset pass / the forecaster join
            "src_share_above": float("nan"),
            "src_share_below": float("nan"),
            "menu_hat": float("nan"),
        }
        out.append(rec)
    return out


def _one(job):
    asset, d8 = job
    try:
        f = PL.frame(asset, int(d8), with_levels=False, with_v3=True)
    except Exception as e:                # noqa: BLE001 — surfaced, not hidden
        return ("ERROR", asset, int(d8), repr(e)[:300])
    if f is None:
        return ("EMPTY", asset, int(d8), "")
    # open_utc is needed for the wall-clock cross-asset join and is not a
    # frame field; it is the session receipt's own meta, read once here.
    import assemble as A
    f = dict(f)
    f["open_utc"] = int(A.load_session(asset, int(d8))["s"].meta["open_utc"])
    return ("OK", _cells_of(f))


def scan(assets=MC.ASSET_ORDER, workers=4, limit_sessions=None):
    """Every FIT + GATE-2025H1 session, collapsed to cells."""
    jobs, quarantined = [], 0
    for a in assets:
        ds = PL.sessions(a, years=set(FIT_YEARS) | {GATE_YEAR})
        keep = [d for d in ds if int(d) < HOLDOUT_FROM_D8]
        quarantined += len(ds) - len(keep)
        if limit_sessions:
            keep = keep[:limit_sessions]
        jobs += [(a, d) for d in keep]
    jobs.sort()
    cells, errs = [], []
    t0 = time.time()
    if workers and workers > 1:
        with mp.Pool(processes=int(workers)) as pool:
            for n, res in enumerate(pool.imap(_one, jobs, chunksize=8), 1):
                if res[0] == "OK":
                    cells += res[1]
                elif res[0] == "ERROR":
                    errs.append((res[1], res[2], res[3]))
                if n % 250 == 0:
                    MC.hb("batch4 scan %d/%d  %.1fs"
                          % (n, len(jobs), time.time() - t0))
    else:
        for j in jobs:
            res = _one(j)
            if res[0] == "OK":
                cells += res[1]
            elif res[0] == "ERROR":
                errs.append((res[1], res[2], res[3]))
    if errs:
        raise RuntimeError("batch4 scan: %d session(s) failed, first=%s"
                           % (len(errs), errs[0]))
    cells.sort(key=lambda c: (c["asset"], c["d8"], c["phase"]))
    MC.hb("batch4 scan: %d cells over %d sessions (%d holdout sessions "
          "quarantined, never loaded), %.1fs"
          % (len(cells), len(jobs), quarantined, time.time() - t0))
    return cells, len(jobs), quarantined


# ============================================================ the P031 source
def attach_cross_asset(cells):
    """For every cell, the most recent CLOSED cell of each OTHER asset.

    Strictly causal: the source cell's LAST candidate row (where the fuel map
    is read) must sit at or before the target cell's OPEN second in wall-clock
    time.  Assets have different session grids, so the join is on epoch
    seconds, never on the phase name.

    -> {(asset, d8, phase): {src_asset: src_cell}}
    """
    by_asset = {}
    for c in cells:
        by_asset.setdefault(c["asset"], []).append(c)
    for a in by_asset:
        by_asset[a].sort(key=lambda c: c["close_ts"])
    closes = {a: np.array([c["close_ts"] for c in by_asset[a]],
                          dtype=np.int64) for a in by_asset}
    src = {}
    for c in cells:
        key = (c["asset"], c["d8"], c["phase"])
        got = {}
        for a, arr in closes.items():
            j = int(np.searchsorted(arr, c["open_ts"], side="right")) - 1
            if j < 0:
                continue
            s = by_asset[a][j]
            if s is c:
                continue
            # a source is only usable while it is fresh: the same trading day
            # or the one before it (a stale overhang is a different claim)
            if abs(int(s["d8"]) - int(c["d8"])) > 3:
                continue
            got[a] = s
        src[key] = got
    return src


def _overhang_call(src, thr):
    """The declared P031 rule on one source cell -> -1 SHORT / +1 LONG / 0."""
    tot = float(src["close_fuel_total"])
    if not (tot > 0):
        return 0
    if float(src["close_fuel_above"]) / tot >= thr:
        return -1                          # trapped longs must sell
    if float(src["close_fuel_below"]) / tot >= thr:
        return +1                          # trapped shorts must cover
    return 0


def winner_side(c):
    """The cell's realised WINNER-MAJORITY side; 0 = no winners or a tie."""
    if c["n_win_long"] > c["n_win_short"]:
        return +1
    if c["n_win_short"] > c["n_win_long"]:
        return -1
    return 0


# ================================================================== era masks
def era_of_cell(c):
    if c["year"] in FIT_YEARS:
        return "FIT"
    if c["year"] == GATE_YEAR:
        return "GATE_%dH1" % GATE_YEAR
    return "OTHER"


ERAS = ("FIT", "GATE_%dH1" % GATE_YEAR)


def _stats(sub):
    """The value block every table repeats, on BOTH CC-M1-8 readings."""
    n = len(sub)
    if n == 0:
        return dict(n_cells=0, n_sessions=0, n_cand=0, n_winners=0,
                    seat_rate=None, mean_win_per_cell=None,
                    mean_close=None, mean_peak=None, cond_close=None,
                    seat_value_usd=0.0, best_cell_usd=None)
    nw = np.array([c["n_win"] for c in sub], dtype=np.float64)
    mc = np.array([c["mean_close"] for c in sub], dtype=np.float64)
    mp_ = np.array([c["mean_peak"] for c in sub], dtype=np.float64)
    cd = np.array([c["cond_close"] for c in sub], dtype=np.float64)
    wv = np.array([c["win_close_sum"] for c in sub], dtype=np.float64)
    return dict(
        n_cells=n,
        n_sessions=len({(c["asset"], c["d8"]) for c in sub}),
        n_cand=int(sum(c["n_cand"] for c in sub)),
        n_winners=int(nw.sum()),
        seat_rate=float((nw >= 1).mean()),
        mean_win_per_cell=float(nw.mean()),
        mean_close=float(np.nanmean(mc)) if np.isfinite(mc).any() else None,
        mean_peak=float(np.nanmean(mp_)) if np.isfinite(mp_).any() else None,
        cond_close=float(np.nanmean(cd)) if np.isfinite(cd).any() else None,
        seat_value_usd=float(wv.sum()),
        best_cell_usd=float(wv.max()) if wv.size else None)


# ================================================================= P030 bands
BAND_COLUMNS = ("asset", "era", "band", "rv_lo", "rv_hi", "n_cells",
                "cell_share", "n_cells_with_seat", "seat_rate", "seat_lift",
                "n_winners", "winner_share", "n_candidates", "cand_share",
                "conc_ratio", "mean_win_per_cell", "mean_close_usd",
                "mean_peak_usd", "cond_close_usd", "seat_value_usd",
                "best_cell_usd")


def band_of(v):
    if not np.isfinite(v):
        return -1
    for k, (lo, hi) in enumerate(P030_BANDS):
        if lo <= v < hi:
            return k
    return len(P030_BANDS) - 1


def band_rows(cells, rows):
    groups = [("ALL", None)] + [(a, a) for a in MC.ASSET_ORDER]
    for aname, asel in groups:
        for ename in ERAS:
            stratum = [c for c in cells
                       if (asel is None or c["asset"] == asel)
                       and era_of_cell(c) == ename]
            if not stratum:
                continue
            base = _stats(stratum)
            for k, bn in enumerate(P030_BAND_NAMES):
                sub = [c for c in stratum if band_of(c["rv1800_open"]) == k]
                st = _stats(sub)
                cs = st["n_cells"] / base["n_cells"] if base["n_cells"] else 0.0
                ws = (st["n_winners"] / base["n_winners"]
                      if base["n_winners"] else 0.0)
                cds = (st["n_cand"] / base["n_cand"]
                       if base["n_cand"] else 0.0)
                rows.append([aname, ename, bn, P030_BANDS[k][0],
                             (P030_BANDS[k][1] if P030_BANDS[k][1] < 1e17
                              else float("inf")),
                             st["n_cells"], cs,
                             int(round(st["seat_rate"] * st["n_cells"]))
                             if st["n_cells"] else 0,
                             st["seat_rate"],
                             (st["seat_rate"] / base["seat_rate"]
                              if (st["seat_rate"] is not None
                                  and base["seat_rate"]) else None),
                             st["n_winners"], ws, st["n_cand"], cds,
                             (ws / cds) if cds > 0 else None,
                             st["mean_win_per_cell"], st["mean_close"],
                             st["mean_peak"], st["cond_close"],
                             st["seat_value_usd"], st["best_cell_usd"]])
    return rows


# ================================================================= P030 sweep
SWEEP_COLUMNS = ("asset", "era", "rv_floor", "n_cells_admitted",
                 "cell_share_admitted", "seat_rate_admitted",
                 "seat_rate_refused", "seat_rate_all", "seat_lift",
                 "n_winners_kept", "winner_share_kept", "n_winners_refused",
                 "best_refused_cell_usd", "value_kept_usd",
                 "value_refused_usd", "mean_close_admitted",
                 "mean_peak_admitted", "mean_close_refused",
                 "n_sessions_fully_refused", "n_cells_refused")


def sweep_rows(cells, rows):
    """The CURVE.  Every floor carries what it buys AND what it costs."""
    groups = [("ALL", None)] + [(a, a) for a in MC.ASSET_ORDER]
    for aname, asel in groups:
        for ename in ERAS:
            stratum = [c for c in cells
                       if (asel is None or c["asset"] == asel)
                       and era_of_cell(c) == ename]
            if not stratum:
                continue
            base = _stats(stratum)
            sess = {(c["asset"], c["d8"]) for c in stratum}
            for thr in P030_SWEEP_GRID:
                ad = [c for c in stratum if c["rv1800_open"] >= thr]
                rf = [c for c in stratum if not (c["rv1800_open"] >= thr)]
                sa, sr = _stats(ad), _stats(rf)
                # a session every one of whose cells the floor refuses is a
                # session the floor takes off the table entirely
                left = {(c["asset"], c["d8"]) for c in ad}
                rows.append([aname, ename, thr, sa["n_cells"],
                             (sa["n_cells"] / base["n_cells"]
                              if base["n_cells"] else None),
                             sa["seat_rate"], sr["seat_rate"],
                             base["seat_rate"],
                             (sa["seat_rate"] / base["seat_rate"]
                              if (sa["seat_rate"] is not None
                                  and base["seat_rate"]) else None),
                             sa["n_winners"],
                             (sa["n_winners"] / base["n_winners"]
                              if base["n_winners"] else None),
                             sr["n_winners"], sr["best_cell_usd"],
                             sa["seat_value_usd"], sr["seat_value_usd"],
                             sa["mean_close"], sa["mean_peak"],
                             sr["mean_close"], len(sess - left),
                             sr["n_cells"]])
    return rows


# ========================================================= the seat base rates
BASE_COLUMNS = ("asset", "phase", "era", "n_cells", "n_sessions",
                "n_candidates", "n_cells_with_seat", "seat_rate",
                "n_winners", "mean_win_per_cell", "p_ge2_winners",
                "mean_close_usd", "mean_peak_usd", "cond_close_usd",
                "seat_value_usd", "mean_rv1800_open", "median_rv1800_open")


def base_rate_rows(cells, rows):
    for aname in ("ALL",) + tuple(MC.ASSET_ORDER):
        for pname in ("ALL",) + tuple(PHASES):
            for ename in ERAS:
                sub = [c for c in cells
                       if (aname == "ALL" or c["asset"] == aname)
                       and (pname == "ALL" or PHASES[c["phase"]] == pname)
                       and era_of_cell(c) == ename]
                if not sub:
                    continue
                st = _stats(sub)
                nw = np.array([c["n_win"] for c in sub])
                rv = np.array([c["rv1800_open"] for c in sub],
                              dtype=np.float64)
                rows.append([aname, pname, ename, st["n_cells"],
                             st["n_sessions"], st["n_cand"],
                             int((nw >= 1).sum()), st["seat_rate"],
                             st["n_winners"], st["mean_win_per_cell"],
                             float((nw >= 2).mean()), st["mean_close"],
                             st["mean_peak"], st["cond_close"],
                             st["seat_value_usd"],
                             float(np.nanmean(rv)) if rv.size else None,
                             float(np.nanmedian(rv)) if rv.size else None])
    return rows


# ==================================================== multivariate GEE + AUC
def gee_multi(y, Xm, clusters, link="logit"):
    """GEE with an independence working correlation over a DESIGN MATRIX.

    episode_v2.gee_independence is the one-regressor form; this is the same
    estimator (same IRLS, same Liang-Zeger meat, same Cameron-Miller CR1)
    generalised to p regressors, which the seat model needs.  Verified against
    it on a single column by test_batch4.t01.
    """
    y = np.asarray(y, dtype=np.float64)
    Xm = np.asarray(Xm, dtype=np.float64)
    if Xm.ndim == 1:
        Xm = Xm[:, None]
    cl = np.asarray(clusters)
    n = y.size
    Xd = np.column_stack([np.ones(n), Xm])
    p = Xd.shape[1]
    if n <= p:
        return None
    if link == "logit":
        beta, ok = EV._irls_logit(Xd, y)
        if not ok:
            return None
        eta = np.clip(Xd @ beta, -30.0, 30.0)
        mu = 1.0 / (1.0 + np.exp(-eta))
        a = np.maximum(mu * (1.0 - mu), 1e-12)
        phi = 1.0
    else:
        beta = np.linalg.lstsq(Xd, y, rcond=None)[0]
        mu = Xd @ beta
        a = np.ones(n)
        phi = float(((y - mu) ** 2).sum() / max(n - p, 1))
    r = y - mu
    bread = Xd.T @ (Xd * a[:, None])
    try:
        binv = np.linalg.inv(bread)
    except np.linalg.LinAlgError:
        return None
    order = np.argsort(cl, kind="stable")
    cs = cl[order]
    edges = np.flatnonzero(cs[1:] != cs[:-1]) + 1
    starts = np.concatenate(([0], edges))
    stops = np.concatenate((edges, [n]))
    meat = np.zeros((p, p))
    for s, e in zip(starts.tolist(), stops.tolist()):
        idx = order[s:e]
        u = Xd[idx].T @ r[idx]
        meat += np.outer(u, u)
    g = starts.size
    robust = binv @ meat @ binv
    cr1 = (g / max(g - 1.0, 1.0)) * ((n - 1.0) / max(n - p, 1.0))
    naive = binv * phi
    return {"beta": beta,
            "se_naive": np.sqrt(np.maximum(np.diag(naive), 0.0)),
            "se_cr0": np.sqrt(np.maximum(np.diag(robust), 0.0)),
            "se_cr1": np.sqrt(np.maximum(np.diag(robust) * cr1, 0.0)),
            "n": int(n), "n_clusters": int(g), "p": int(p)}


def auc(y, s):
    """Rank AUC with ties handled at half weight; NaN when one class is empty."""
    y = np.asarray(y, dtype=np.float64)
    s = np.asarray(s, dtype=np.float64)
    ok = np.isfinite(s)
    y, s = y[ok], s[ok]
    n1 = float((y > 0).sum())
    n0 = float((y <= 0).sum())
    if n1 == 0 or n0 == 0:
        return float("nan")
    r = P1.__dict__.get("rankdata") or X.rankdata
    rr = r(s)
    return float((rr[y > 0].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0))


def _standardise(Xm):
    """Column-centre/scale using FINITE entries; a dead column stays zero."""
    mu = np.zeros(Xm.shape[1])
    sd = np.ones(Xm.shape[1])
    for j in range(Xm.shape[1]):
        col = Xm[:, j]
        ok = np.isfinite(col)
        if ok.sum() < 2:
            continue
        mu[j] = float(col[ok].mean())
        s = float(col[ok].std())
        sd[j] = s if s > 1e-12 else 1.0
    return mu, sd


def design(cells, names):
    """The cell-open design matrix.  NaN -> the column mean (recorded)."""
    cols = []
    for nm in names:
        if nm == "rv1800":
            v = [c["rv1800_open"] for c in cells]
        elif nm == "prev_ret_sign":
            v = [np.sign(c["prev_ret_usd"]) if np.isfinite(c["prev_ret_usd"])
                 else np.nan for c in cells]
        elif nm == "prev_ret_mag":
            v = [abs(c["prev_ret_usd"]) for c in cells]
        elif nm == "overnight_ratio":
            v = [(c["pre_cell_range_usd"] / c["atr_open"])
                 if (np.isfinite(c["pre_cell_range_usd"]) and c["atr_open"] > 0)
                 else np.nan for c in cells]
        elif nm == "release_in_ph":
            v = [float(c["release_in_ph"]) for c in cells]
        elif nm == "dow_sin":
            v = [math.sin(2 * math.pi * c["dow"] / 7.0) for c in cells]
        elif nm == "dow_cos":
            v = [math.cos(2 * math.pi * c["dow"] / 7.0) for c in cells]
        elif nm == "menu_hat":
            v = [c["menu_hat"] for c in cells]
        else:
            raise KeyError(nm)
        cols.append(np.array(v, dtype=np.float64))
    Xm = np.column_stack(cols) if cols else np.zeros((len(cells), 0))
    return Xm


def _impute(Xm, mu):
    out = Xm.copy()
    for j in range(out.shape[1]):
        bad = ~np.isfinite(out[:, j])
        out[bad, j] = mu[j]
    return out


def fit_logit(Xtr, ytr):
    """Ridge-stabilised IRLS logit; -> (beta, mu, sd) or None."""
    mu, sd = _standardise(Xtr)
    Z = (_impute(Xtr, mu) - mu) / sd
    Zd = np.column_stack([np.ones(Z.shape[0]), Z])
    beta, ok = EV._irls_logit(Zd, ytr.astype(np.float64))
    if not ok or not np.all(np.isfinite(beta)):
        return None
    return beta, mu, sd


def predict_logit(model, Xte):
    beta, mu, sd = model
    Z = (_impute(Xte, mu) - mu) / sd
    Zd = np.column_stack([np.ones(Z.shape[0]), Z])
    return 1.0 / (1.0 + np.exp(-np.clip(Zd @ beta, -30.0, 30.0)))


# ============================================================= the seat model
MODEL_COLUMNS = ("feature_set", "asset", "era", "term", "beta", "se_naive",
                 "se_cr0", "se_cr1", "z_cr1", "p_cr1", "odds_ratio_per_sd",
                 "n", "n_clusters", "n_seats", "seat_rate")


def model_rows(cells, rows):
    for fname, feats in (("BASE", SEAT_FEATURES_BASE),
                         ("PLUS_MENU", SEAT_FEATURES_MENU)):
        for aname in ("ALL",) + tuple(MC.ASSET_ORDER):
            for ename in ERAS:
                sub = [c for c in cells
                       if (aname == "ALL" or c["asset"] == aname)
                       and era_of_cell(c) == ename
                       and (fname == "BASE" or c["year"] >= MENU_FROM_YEAR)]
                if fname == "PLUS_MENU":
                    sub = [c for c in sub if np.isfinite(c["menu_hat"])]
                if len(sub) < 60:
                    continue
                y = np.array([1.0 if c["n_win"] >= 1 else 0.0 for c in sub])
                if y.sum() == 0 or y.sum() == y.size:
                    continue
                Xm = design(sub, feats)
                mu, sd = _standardise(Xm)
                Z = (_impute(Xm, mu) - mu) / sd
                cl = np.array(["%s-%08d" % (c["asset"], c["d8"])
                               for c in sub])
                g = gee_multi(y, Z, cl, link="logit")
                if g is None:
                    continue
                terms = ("intercept",) + tuple(feats)
                for j, tn in enumerate(terms):
                    z = (g["beta"][j] / g["se_cr1"][j]
                         if g["se_cr1"][j] > 0 else float("nan"))
                    rows.append([fname, aname, ename, tn,
                                 float(g["beta"][j]), float(g["se_naive"][j]),
                                 float(g["se_cr0"][j]), float(g["se_cr1"][j]),
                                 z, P1._p_two_sided(z),
                                 float(np.exp(g["beta"][j])),
                                 g["n"], g["n_clusters"], int(y.sum()),
                                 float(y.mean())])
    return rows


AUC_COLUMNS = ("feature_set", "asset", "scope", "n_train", "n_test",
               "base_rate_test", "auc", "auc_lo_boot", "auc_hi_boot",
               "brier", "brier_base", "feature", "univariate_auc",
               "loo_delta_auc")

BOOT_REPS = 400
BOOT_SEED = 20260817


def _cluster_boot_auc(y, s, cl, reps=BOOT_REPS, seed=BOOT_SEED):
    """Session-cluster bootstrap CI for AUC (whole sessions, never cells)."""
    uniq, inv = np.unique(cl, return_inverse=True)
    if uniq.size < 20:
        return float("nan"), float("nan")
    idx_by = [np.nonzero(inv == g)[0] for g in range(uniq.size)]
    rng = np.random.RandomState(seed)
    out = []
    for _ in range(reps):
        pick = rng.randint(0, uniq.size, uniq.size)
        take = np.concatenate([idx_by[g] for g in pick])
        a = auc(y[take], s[take])
        if np.isfinite(a):
            out.append(a)
    if len(out) < 20:
        return float("nan"), float("nan")
    return (float(np.percentile(out, 2.5)),
            float(np.percentile(out, 97.5)))


def auc_rows(cells, rows):
    """WALK-FORWARD AUC per era, plus univariate and leave-one-out dAUC."""
    for fname, feats in (("BASE", SEAT_FEATURES_BASE),
                         ("PLUS_MENU", SEAT_FEATURES_MENU)):
        pool = [c for c in cells
                if fname == "BASE" or (c["year"] >= MENU_FROM_YEAR
                                       and np.isfinite(c["menu_hat"]))]
        for aname in ("ALL",) + tuple(MC.ASSET_ORDER):
            sub0 = [c for c in pool
                    if aname == "ALL" or c["asset"] == aname]
            if len(sub0) < 200:
                continue
            # ---- the walk-forward scopes -------------------------------
            scopes = []
            for yr in FIT_YEARS:
                tr = [c for c in sub0 if c["year"] in FIT_YEARS
                      and c["year"] < yr]
                te = [c for c in sub0 if c["year"] == yr]
                if len(tr) >= 200 and len(te) >= 50:
                    scopes.append(("WF_%d" % yr, tr, te))
            fit_all = [c for c in sub0 if c["year"] in FIT_YEARS]
            gate = [c for c in sub0 if era_of_cell(c) == ERAS[1]]
            if len(fit_all) >= 200 and len(gate) >= 50:
                scopes.append(("GATE_%dH1_FROZEN" % GATE_YEAR, fit_all, gate))
            # the pooled walk-forward: every WF test year concatenated
            wf_all = [s for s in scopes if s[0].startswith("WF_")]
            for name, tr, te in scopes + (
                    [("WF_POOLED",
                      None, [c for _n, _t, t in wf_all for c in t])]
                    if wf_all else []):
                yte = np.array([1.0 if c["n_win"] >= 1 else 0.0 for c in te])
                cl = np.array(["%s-%08d" % (c["asset"], c["d8"]) for c in te])
                if name == "WF_POOLED":
                    # score each test year with ITS OWN prior-years fit
                    p = []
                    yy = []
                    cc = []
                    for _n, tr_i, te_i in wf_all:
                        m = fit_logit(design(tr_i, feats),
                                      np.array([1.0 if c["n_win"] >= 1 else 0.0
                                                for c in tr_i]))
                        if m is None:
                            continue
                        p.append(predict_logit(m, design(te_i, feats)))
                        yy.append(np.array([1.0 if c["n_win"] >= 1 else 0.0
                                            for c in te_i]))
                        cc.append(np.array(["%s-%08d" % (c["asset"], c["d8"])
                                            for c in te_i]))
                    if not p:
                        continue
                    pr = np.concatenate(p)
                    yte = np.concatenate(yy)
                    cl = np.concatenate(cc)
                    n_tr = sum(len(t) for _n, t, _e in wf_all)
                else:
                    m = fit_logit(design(tr, feats),
                                  np.array([1.0 if c["n_win"] >= 1 else 0.0
                                            for c in tr]))
                    if m is None:
                        continue
                    pr = predict_logit(m, design(te, feats))
                    n_tr = len(tr)
                a = auc(yte, pr)
                lo, hi = _cluster_boot_auc(yte, pr, cl)
                br = float(np.mean((pr - yte) ** 2))
                base = float(yte.mean())
                brb = float(np.mean((base - yte) ** 2))
                rows.append([fname, aname, name, n_tr, len(yte), base, a,
                             lo, hi, br, brb, "ALL_FEATURES", None, None])
                # ---- which features carry it ---------------------------
                if name not in ("WF_POOLED", "GATE_%dH1_FROZEN" % GATE_YEAR):
                    continue
                for j, fe in enumerate(feats):
                    uv = auc(yte, design(te, (fe,))[:, 0])
                    if uv < 0.5 and np.isfinite(uv):
                        uv = 1.0 - uv     # a feature's sign is not its skill
                    keep = tuple(x for x in feats if x != fe)
                    if name == "WF_POOLED":
                        pl = []
                        for _n, tr_i, te_i in wf_all:
                            mm = fit_logit(design(tr_i, keep),
                                           np.array([1.0 if c["n_win"] >= 1
                                                     else 0.0
                                                     for c in tr_i]))
                            if mm is None:
                                pl = None
                                break
                            pl.append(predict_logit(mm, design(te_i, keep)))
                        pl = np.concatenate(pl) if pl else None
                    else:
                        mm = fit_logit(design(tr, keep),
                                       np.array([1.0 if c["n_win"] >= 1 else
                                                 0.0 for c in tr]))
                        pl = predict_logit(mm, design(te, keep)) \
                            if mm is not None else None
                    d = (a - auc(yte, pl)) if pl is not None else None
                    rows.append([fname, aname, name, n_tr, len(yte), base,
                                 a, lo, hi, br, brb, fe, uv, d])
    return rows


# ======================================================================= P031
PAIR_COLUMNS = ("threshold", "source_asset", "target_asset", "leg", "era",
                "n_cells", "n_called", "call_rate", "n_scoreable",
                "n_agree", "agreement", "mirror_agreement", "beats_mirror",
                "n_sessions", "sign_test_p", "est_value_usd",
                "mirror_value_usd", "delta_value_usd", "cluster_unit",
                "beta", "se_cr1", "z_cr1", "p_cr1", "icc_rho", "deff",
                "n_eff", "verdict")


def _cell_side_value(c, side):
    """What a cell-side call is worth: the winner value it selects minus the
    winner value it forgoes.  Zero when the cell has no winners at all — the
    feasibility fact a side call cannot see, kept explicit."""
    if side > 0:
        return c["win_close_sum_long"] - c["win_close_sum_short"]
    if side < 0:
        return c["win_close_sum_short"] - c["win_close_sum_long"]
    return 0.0


def pair_rows(cells, src, rows, robust, thr=P031_THR, full=True):
    """Agreement vs mirror for every (source -> target) leg."""
    legs = [(sa, ta) for sa in MC.ASSET_ORDER for ta in MC.ASSET_ORDER]
    for sa, ta in legs + [("ANY_OTHER", ta) for ta in MC.ASSET_ORDER] \
            + [("ANY_OTHER", "ALL")]:
        for ename in ERAS:
            recs = []
            for c in cells:
                if ta != "ALL" and c["asset"] != ta:
                    continue
                if era_of_cell(c) != ename:
                    continue
                got = src.get((c["asset"], c["d8"], c["phase"]), {})
                if sa == "ANY_OTHER":
                    # the strongest overhang among the OTHER assets, the day-6
                    # form ("the OTHER metals' trapped-inventory imbalance")
                    best, bshare = 0, 0.0
                    for a2, s2 in got.items():
                        if a2 == c["asset"]:
                            continue
                        tot = float(s2["close_fuel_total"])
                        if not (tot > 0):
                            continue
                        sh = max(s2["close_fuel_above"],
                                 s2["close_fuel_below"]) / tot
                        if sh > bshare:
                            bshare, best = sh, _overhang_call(s2, thr)
                    call = best
                else:
                    s2 = got.get(sa)
                    call = _overhang_call(s2, thr) if s2 is not None else 0
                recs.append((c, call))
            if not recs:
                continue
            leg = ("OWN" if sa == ta else
                   ("CROSS" if sa != "ANY_OTHER" else "CROSS_BEST"))
            called = [(c, k) for c, k in recs if k != 0]
            scor = [(c, k) for c, k in called if winner_side(c) != 0]
            n_ag = sum(1 for c, k in scor if k == winner_side(c))
            n_sc = len(scor)
            agree = (n_ag / n_sc) if n_sc else None
            mir = (1.0 - agree) if agree is not None else None
            ev = sum(_cell_side_value(c, k) for c, k in called)
            mv = sum(_cell_side_value(c, -k) for c, k in called)
            # per-SESSION mirror law (CC-M2-13.1)
            by_s = {}
            for c, k in called:
                by_s.setdefault((c["asset"], c["d8"]), []).append((c, k))
            won = tie = lost = 0
            for key, grp in by_s.items():
                de = (sum(_cell_side_value(c, k) for c, k in grp)
                      - sum(_cell_side_value(c, -k) for c, k in grp))
                won += de > 0
                lost += de < 0
                tie += de == 0
            p_sign = _sign_test(won, lost)
            rows.append([thr, sa, ta, leg, ename, len(recs), len(called),
                         (len(called) / len(recs)) if recs else None,
                         n_sc, n_ag, agree, mir,
                         int(agree > 0.5) if agree is not None else None,
                         len(by_s), p_sign, ev, mv, ev - mv, "-",
                         None, None, None, None, None, None, None, "-"])
            if not full or n_sc < 30:
                continue
            # GEE: does the signed call carry the realised winner-majority
            # side?  Two clusterings, both reported (P031 is cross-asset).
            y = np.array([1.0 if winner_side(c) > 0 else 0.0
                          for c, _k in scor])
            xs = np.array([float(k) for _c, k in scor])
            for unit, cl in (("SESSION",
                              np.array(["%s-%08d" % (c["asset"], c["d8"])
                                        for c, _k in scor])),
                             ("DATE", np.array(["%08d" % c["d8"]
                                                for c, _k in scor]))):
                g = EV.gee_independence(y, xs, cl, link="logit")
                ic = EV.icc_oneway(y, np.unique(cl, return_inverse=True)[1])
                if g is None:
                    continue
                z = (g["beta"] / g["se_cr1"]) if g["se_cr1"] > 0 else \
                    float("nan")
                p = P1._p_two_sided(z)
                robust.append(["P031_%s_%s>%s" % (leg, sa, ta), ename,
                               "winner_majority_side", unit, g["n"],
                               g["n_clusters"], len(called), g["beta"],
                               g["se_naive"], g["se_cr0"], g["se_cr1"], z, p,
                               ic["rho"] if ic else float("nan"),
                               ic["deff"] if ic else float("nan"),
                               ic["n_eff"] if ic else float("nan"),
                               "SIGNIFICANT_p<0.05"
                               if (np.isfinite(p) and p < 0.05)
                               else "NOT_SIGNIFICANT"])
    return rows


def _sign_test(won, lost):
    """Two-sided sign test over sessions (ties excluded).

    Exact binomial while the tail is representable; a normal approximation
    with the continuity correction beyond that (2**n overflows float64 at
    n ~ 1024, and an era-scale leg has thousands of sessions).
    """
    n = won + lost
    if n == 0:
        return float("nan")
    k = min(won, lost)
    if n > 200:
        z = (2.0 * k + 1.0 - n) / math.sqrt(float(n))
        return float(min(1.0, P1._p_two_sided(z)))
    tot = 0
    for i in range(k + 1):
        tot += math.comb(n, i)
    return float(min(1.0, 2.0 * tot / float(2 ** n)))


MIRROR_COLUMNS = ("threshold", "source_asset", "target_asset", "leg", "era",
                  "n_sessions", "sessions_won", "sessions_tied",
                  "sessions_lost", "mirror_law_holds", "mean_delta_usd",
                  "se_session", "z", "p", "holm_rank", "holm_threshold",
                  "holm_verdict")


def mirror_rows(cells, src, rows, thr=P031_THR):
    for sa in tuple(MC.ASSET_ORDER) + ("ANY_OTHER",):
        for ta in tuple(MC.ASSET_ORDER) + ("ALL",):
            for ename in ERAS:
                by_s = {}
                for c in cells:
                    if ta != "ALL" and c["asset"] != ta:
                        continue
                    if era_of_cell(c) != ename:
                        continue
                    got = src.get((c["asset"], c["d8"], c["phase"]), {})
                    if sa == "ANY_OTHER":
                        best, bshare = 0, 0.0
                        for a2, s2 in got.items():
                            if a2 == c["asset"]:
                                continue
                            tot = float(s2["close_fuel_total"])
                            if not (tot > 0):
                                continue
                            sh = max(s2["close_fuel_above"],
                                     s2["close_fuel_below"]) / tot
                            if sh > bshare:
                                bshare, best = sh, _overhang_call(s2, thr)
                        k = best
                    else:
                        s2 = got.get(sa)
                        k = _overhang_call(s2, thr) if s2 is not None else 0
                    if k == 0:
                        continue
                    by_s.setdefault((c["asset"], c["d8"]), []).append((c, k))
                if not by_s:
                    continue
                d = np.array([sum(_cell_side_value(c, k) for c, k in g)
                              - sum(_cell_side_value(c, -k) for c, k in g)
                              for g in by_s.values()])
                won = int((d > 0).sum())
                lost = int((d < 0).sum())
                tie = int((d == 0).sum())
                mu = float(d.mean()) if d.size else float("nan")
                se = (float(d.std(ddof=1) / math.sqrt(d.size))
                      if d.size > 1 else float("nan"))
                z = mu / se if (np.isfinite(se) and se > 0) else float("nan")
                leg = ("OWN" if sa == ta else
                       ("CROSS" if sa != "ANY_OTHER" else "CROSS_BEST"))
                rows.append([thr, sa, ta, leg, ename, len(by_s), won, tie,
                             lost, int(lost == 0 and won > 0), mu, se, z,
                             P1._p_two_sided(z)])
    return _holm(rows, 13, len(MIRROR_COLUMNS))


SENS_COLUMNS = ("threshold", "leg", "era", "n_called", "n_scoreable",
                "agreement", "mirror_agreement", "delta_value_usd",
                "sessions_won", "sessions_lost")


def sensitivity_rows(cells, src, rows):
    """The overhang threshold is a fitted number too — report the whole grid."""
    for thr in P031_THR_GRID:
        for leg_want in ("CROSS", "OWN", "CROSS_BEST"):
            for ename in ERAS:
                called = []
                for c in cells:
                    if era_of_cell(c) != ename:
                        continue
                    got = src.get((c["asset"], c["d8"], c["phase"]), {})
                    ks = []
                    for a2, s2 in got.items():
                        own = (a2 == c["asset"])
                        if leg_want == "OWN" and not own:
                            continue
                        if leg_want != "OWN" and own:
                            continue
                        k = _overhang_call(s2, thr)
                        if k:
                            tot = float(s2["close_fuel_total"])
                            ks.append((max(s2["close_fuel_above"],
                                           s2["close_fuel_below"]) / tot, k))
                    if not ks:
                        continue
                    if leg_want == "CROSS_BEST":
                        ks = [max(ks)]
                    for _sh, k in ks:
                        called.append((c, k))
                if not called:
                    continue
                scor = [(c, k) for c, k in called if winner_side(c) != 0]
                n_ag = sum(1 for c, k in scor if k == winner_side(c))
                ag = (n_ag / len(scor)) if scor else None
                dv = sum(_cell_side_value(c, k) - _cell_side_value(c, -k)
                         for c, k in called)
                by_s = {}
                for c, k in called:
                    by_s.setdefault((c["asset"], c["d8"]), []).append((c, k))
                dd = np.array([sum(_cell_side_value(c, k)
                                   - _cell_side_value(c, -k) for c, k in g)
                               for g in by_s.values()])
                rows.append([thr, leg_want, ename, len(called), len(scor), ag,
                             (1.0 - ag) if ag is not None else None, dv,
                             int((dd > 0).sum()), int((dd < 0).sum())])
    return rows


# =================================================================== the GEEs
ROBUST_COLUMNS = ("object", "era", "metric", "cluster_unit", "n",
                  "n_clusters", "n_fire", "beta", "se_naive", "se_cr0",
                  "se_cr1", "z_cr1", "p_cr1", "icc_rho", "deff", "n_eff",
                  "verdict", "holm_rank", "holm_threshold", "holm_verdict")


def _holm(rows, pcol, ncols, alpha=0.05):
    idx = [i for i, r in enumerate(rows) if np.isfinite(r[pcol])]
    order = sorted(idx, key=lambda i: rows[i][pcol])
    m = len(order)
    still = True
    for rank, i in enumerate(order, 1):
        thr = alpha / (m - rank + 1)
        ok = still and rows[i][pcol] <= thr
        still = still and ok
        rows[i] += [rank, thr,
                    "HOLM_SIGNIFICANT" if ok else "HOLM_NOT_SIGNIFICANT"]
    for i, r in enumerate(rows):
        if len(r) == ncols - 3:
            rows[i] += [0, float("nan"), "NO_TEST"]
    return rows


def p030_robust_rows(cells, robust):
    """P030's own GEEs: does rv1800-at-open carry the seat and its value?"""
    for aname in ("ALL",) + tuple(MC.ASSET_ORDER):
        for ename in ERAS:
            sub = [c for c in cells
                   if (aname == "ALL" or c["asset"] == aname)
                   and era_of_cell(c) == ename]
            if len(sub) < 60:
                continue
            cl = np.array(["%s-%08d" % (c["asset"], c["d8"]) for c in sub])
            gi = np.unique(cl, return_inverse=True)[1]
            rv = np.array([c["rv1800_open"] for c in sub], dtype=np.float64)
            ok = np.isfinite(rv)
            if ok.sum() < 60:
                continue
            rvz = np.zeros(rv.size)
            rvz[ok] = (rv[ok] - rv[ok].mean()) / max(rv[ok].std(), 1e-9)
            for metric, y, link in (
                    ("has_seat",
                     np.array([1.0 if c["n_win"] >= 1 else 0.0 for c in sub]),
                     "logit"),
                    ("n_winners",
                     np.array([float(c["n_win"]) for c in sub]), "identity"),
                    ("cell_mean_close",
                     np.array([c["mean_close"] for c in sub]), "identity"),
                    ("cell_mean_peak",
                     np.array([c["mean_peak"] for c in sub]), "identity")):
                m = ok & np.isfinite(y)
                if m.sum() < 60 or len(set(y[m].tolist())) < 2:
                    continue
                g = EV.gee_independence(y[m], rvz[m], cl[m], link=link)
                ic = EV.icc_oneway(y[m], gi[m])
                if g is None:
                    continue
                z = (g["beta"] / g["se_cr1"]) if g["se_cr1"] > 0 else \
                    float("nan")
                p = P1._p_two_sided(z)
                robust.append(["P030_rv1800_open_%s" % aname, ename, metric,
                               "SESSION", g["n"], g["n_clusters"],
                               int((rv[m] >= 150).sum()), g["beta"],
                               g["se_naive"], g["se_cr0"], g["se_cr1"], z, p,
                               ic["rho"] if ic else float("nan"),
                               ic["deff"] if ic else float("nan"),
                               ic["n_eff"] if ic else float("nan"),
                               "SIGNIFICANT_p<0.05"
                               if (np.isfinite(p) and p < 0.05)
                               else "NOT_SIGNIFICANT"])
    return robust


def seat_robust_rows(cells, robust):
    """The seat model's own single-degree-of-freedom test: the fitted score."""
    for fname, feats in (("BASE", SEAT_FEATURES_BASE),
                         ("PLUS_MENU", SEAT_FEATURES_MENU)):
        for ename in ERAS:
            sub = [c for c in cells if era_of_cell(c) == ename
                   and (fname == "BASE"
                        or (c["year"] >= MENU_FROM_YEAR
                            and np.isfinite(c["menu_hat"])))]
            if len(sub) < 200:
                continue
            fit = [c for c in cells if c["year"] in FIT_YEARS
                   and (fname == "BASE"
                        or (c["year"] >= MENU_FROM_YEAR
                            and np.isfinite(c["menu_hat"])))]
            if ename == "FIT":
                # in-sample fit would be a tautology; use the walk-forward
                # score built from strictly prior years only
                pr, y, cl = [], [], []
                for yr in FIT_YEARS:
                    tr = [c for c in fit if c["year"] < yr]
                    te = [c for c in sub if c["year"] == yr]
                    if len(tr) < 200 or not te:
                        continue
                    m = fit_logit(design(tr, feats),
                                  np.array([1.0 if c["n_win"] >= 1 else 0.0
                                            for c in tr]))
                    if m is None:
                        continue
                    pr.append(predict_logit(m, design(te, feats)))
                    y.append(np.array([1.0 if c["n_win"] >= 1 else 0.0
                                       for c in te]))
                    cl.append(np.array(["%s-%08d" % (c["asset"], c["d8"])
                                        for c in te]))
                if not pr:
                    continue
                pr = np.concatenate(pr)
                y = np.concatenate(y)
                cl = np.concatenate(cl)
            else:
                m = fit_logit(design(fit, feats),
                              np.array([1.0 if c["n_win"] >= 1 else 0.0
                                        for c in fit]))
                if m is None:
                    continue
                pr = predict_logit(m, design(sub, feats))
                y = np.array([1.0 if c["n_win"] >= 1 else 0.0 for c in sub])
                cl = np.array(["%s-%08d" % (c["asset"], c["d8"])
                               for c in sub])
            gi = np.unique(cl, return_inverse=True)[1]
            g = EV.gee_independence(y, pr, cl, link="logit")
            ic = EV.icc_oneway(y, gi)
            if g is None:
                continue
            z = (g["beta"] / g["se_cr1"]) if g["se_cr1"] > 0 else float("nan")
            p = P1._p_two_sided(z)
            robust.append(["SEAT_MODEL_%s_score" % fname, ename, "has_seat",
                           "SESSION", g["n"], g["n_clusters"],
                           int(y.sum()), g["beta"], g["se_naive"],
                           g["se_cr0"], g["se_cr1"], z, p,
                           ic["rho"] if ic else float("nan"),
                           ic["deff"] if ic else float("nan"),
                           ic["n_eff"] if ic else float("nan"),
                           "SIGNIFICANT_p<0.05"
                           if (np.isfinite(p) and p < 0.05)
                           else "NOT_SIGNIFICANT"])
    return robust


# ================================================================ destruction
DESTR_COLUMNS = ("object", "era", "neutralised_field", "n_reps", "edge_real",
                 "edge_destroyed_mean", "edge_destroyed_sd",
                 "edge_destroyed_p05", "edge_destroyed_p95", "z_vs_null",
                 "verdict")
# The verdict is SIGN-AWARE on purpose.  |z| >= 2 is not "the mechanism
# survived": an edge that sits BELOW its own within-session shuffle is a real
# result and the opposite one — the field is carrying information AGAINST the
# claim, not for it.  Three outcomes, named:
#   SURVIVES   real edge >= null + 2 sd   (the mechanism is in the field)
#   DESTROYED  real edge inside the null  (it was a stratum artefact)
#   INVERTED   real edge <= null - 2 sd   (worse than its own shuffle)


def _shuffle_within(values, groups, rs):
    """Permute `values` within each group, leaving the group sizes alone."""
    out = values.copy()
    order = np.argsort(groups, kind="stable")
    gs = groups[order]
    edges = np.flatnonzero(gs[1:] != gs[:-1]) + 1
    for s, e in zip(np.concatenate(([0], edges)).tolist(),
                    np.concatenate((edges, [gs.size])).tolist()):
        idx = order[s:e]
        out[idx] = values[idx[rs.permutation(idx.size)]]
    return out


def destruction_rows(cells, src, rows):
    """P030: shuffle rv1800-at-open across the SESSION's own cells.
       P031: shuffle the source overhang across the DATE's own cells.
    The edge is what the object claims; a shuffle that reproduces it means the
    claim was a stratum artefact."""
    for ename in ERAS:
        sub = [c for c in cells if era_of_cell(c) == ename]
        if len(sub) < 100:
            continue
        # ---- P030 -------------------------------------------------------
        rv = np.array([c["rv1800_open"] for c in sub], dtype=np.float64)
        seat = np.array([1.0 if c["n_win"] >= 1 else 0.0 for c in sub])
        sess = np.array(["%s-%08d" % (c["asset"], c["d8"]) for c in sub])
        fire = rv >= 150.0
        real = (float(seat[fire].mean() - seat[~fire].mean())
                if fire.any() and (~fire).any() else float("nan"))
        rs = np.random.RandomState(DESTRUCTION_SEED)
        null = []
        for _ in range(DESTRUCTION_REPS):
            f2 = _shuffle_within(rv, sess, rs) >= 150.0
            if f2.any() and (~f2).any():
                null.append(float(seat[f2].mean() - seat[~f2].mean()))
        rows.append(_destr_row("P030_rv1800_open>=150", ename,
                               "rv1800_open (within session)", real, null))
        # ---- P031 -------------------------------------------------------
        calls, ys, dates = [], [], []
        for c in sub:
            got = src.get((c["asset"], c["d8"], c["phase"]), {})
            best, bshare = 0, 0.0
            for a2, s2 in got.items():
                if a2 == c["asset"]:
                    continue
                tot = float(s2["close_fuel_total"])
                if not (tot > 0):
                    continue
                sh = max(s2["close_fuel_above"], s2["close_fuel_below"]) / tot
                if sh > bshare:
                    bshare, best = sh, _overhang_call(s2, P031_THR)
            if best == 0 or winner_side(c) == 0:
                continue
            calls.append(float(best))
            ys.append(float(winner_side(c)))
            dates.append("%08d" % c["d8"])
        if len(calls) < 50:
            continue
        ca = np.array(calls)
        ya = np.array(ys)
        da = np.array(dates)
        real = float((ca == ya).mean() - 0.5)
        rs = np.random.RandomState(DESTRUCTION_SEED + 1)
        null = [float((_shuffle_within(ca, da, rs) == ya).mean() - 0.5)
                for _ in range(DESTRUCTION_REPS)]
        rows.append(_destr_row("P031_cross_overhang", ename,
                               "source overhang call (within date)",
                               real, null))
    return rows


def _destr_row(obj, era, field, real, null):
    n = np.array(null, dtype=np.float64)
    mu = float(n.mean()) if n.size else float("nan")
    sd = float(n.std(ddof=1)) if n.size > 1 else float("nan")
    z = ((real - mu) / sd) if (np.isfinite(sd) and sd > 0) else float("nan")
    verdict = "NO_NULL"
    if np.isfinite(z):
        verdict = ("SURVIVES" if z >= 2.0 else
                   ("INVERTED" if z <= -2.0 else "DESTROYED"))
    return [obj, era, field, int(n.size), real, mu, sd,
            float(np.percentile(n, 5)) if n.size else float("nan"),
            float(np.percentile(n, 95)) if n.size else float("nan"), z,
            verdict]


# ============================================================== the menu join
def attach_menu_hat(cells):
    """The accepted forecaster's menu_hat at the newest anchor STRICTLY BEFORE
    each cell's open second (CC-M2-1.2).  D20: no 2021 output exists at all."""
    import triage_index as TI
    n_ok = 0
    for c in cells:
        try:
            r = TI.regime_at(c["asset"], c["d8"], c["open_ts"])
        except Exception:                 # noqa: BLE001 — absent file is a fact
            r = None
        v = r[2].get("menu_hat") if r else None
        if v is not None and np.isfinite(v):
            c["menu_hat"] = float(v)
            n_ok += 1
    return n_ok


# =================================================================== grading
def grade_p030(bands, sweep):
    """P030 has no mirror, so its ONLY reachable grade is CONCENTRATOR."""
    hi = [r for r in bands if r[0] == "ALL" and r[1] == "FIT"
          and r[2] == "ge250"]
    lo = [r for r in bands if r[0] == "ALL" and r[1] == "FIT"
          and r[2] == "lt100"]
    if not hi or not lo or not hi[0][8] or not lo[0][8]:
        return "NULL", "no band table"
    ratio = hi[0][8] / lo[0][8] if lo[0][8] > 0 else float("inf")
    if ratio >= CONCENTRATOR_MIN:
        return ("CONCENTRATOR",
                "seat rate %.3f in the >=250 band vs %.3f in the <100 band "
                "(%.2fx); FEATURE CANDIDATE ONLY — it is a feasibility object "
                "with no mirror and can never be an entry rule"
                % (hi[0][8], lo[0][8], ratio))
    return "NULL", "seat-rate ratio %.2fx < %.2f" % (ratio, CONCENTRATOR_MIN)


def grade_p031(pairs, mirror):
    cross = [r for r in pairs if r[3] == "CROSS_BEST" and r[2] == "ALL"
             and r[4] == "FIT"]
    if not cross:
        return "NULL", "no cross rows"
    r = cross[0]
    ag = r[10]
    ml = [m for m in mirror if m[1] == "ANY_OTHER" and m[2] == "ALL"
          and m[4] == "FIT"]
    holds = bool(ml and ml[0][9])
    if ag is None:
        return "NULL", "no scoreable cells"
    if holds and ag > 0.5:
        return "DIRECTION_CANDIDATE", ("agreement %.3f > mirror %.3f AND the "
                                       "mirror law holds" % (ag, 1 - ag))
    return ("DEAD_AS_A_RULE",
            "agreement %.3f (mirror %.3f); mirror law holds = %s — a "
            "directional claim that does not beat its own mirror on every "
            "session does not exist (CC-M2-13.1)" % (ag, 1 - ag, holds))


# ==================================================================== report
_fmt = P1._fmt


def report(cells, res, elapsed, pins, n_sessions, n_quar):
    L = []
    A = L.append
    A("# PORT M2 — CENSUS BATCH 4 (CC-M2-17.5): P030 / P031 / CELL-SEAT "
      "EXISTENCE")
    A("")
    A("* population: %d CELLS over %d sessions of the frozen v3 roster "
      "(FIT %s + GATE-%dH1 echo)."
      % (len(cells), n_sessions, "-".join(str(y) for y in
                                          (FIT_YEARS[0], FIT_YEARS[-1])),
         GATE_YEAR))
    A("* HOLDOUT: %d sessions with d8 >= %d were NEVER LOADED (CC-M2-15.3)."
      % (n_quar, HOLDOUT_FROM_D8))
    A("* unit of analysis: the CELL = (asset, session, phase). A seat exists "
      "when the cell holds >= 1 D-021-class walled winner.")
    A("* runtime %.1fs; pins %s"
      % (elapsed, "HELD" if not pins else "MOVED: " + "; ".join(pins)))
    A("")

    A("## 1. THE CELL-SEAT EXISTENCE BASE RATES (stage 1 of CC-M2-17.1)")
    A("")
    A("| asset | phase | era | cells | seats | seat rate | winners | "
      "mean win/cell | P(>=2) | seat value $ |")
    A("|---|---|---|---|---|---|---|---|---|---|")
    for r in res["base"]:
        if r[0] == "ALL" and r[1] == "ALL":
            continue
        if r[2] != "FIT":
            continue
        if r[0] != "ALL" and r[1] == "ALL":
            pass
        elif r[0] != "ALL":
            continue
        A("| %s | %s | %s | %d | %d | %s | %d | %s | %s | %s |"
          % (r[0], r[1], r[2], r[3], r[6], _fmt(r[7], 3), r[8],
             _fmt(r[9], 2), _fmt(r[10], 3), _fmt(r[14], 0)))
    A("")
    A("Per (asset, phase), FIT:")
    A("")
    A("| asset | phase | cells | seat rate | winners | mean win/cell |")
    A("|---|---|---|---|---|---|")
    for r in res["base"]:
        if r[0] == "ALL" or r[1] == "ALL" or r[2] != "FIT":
            continue
        A("| %s | %s | %d | %s | %d | %s |"
          % (r[0], r[1], r[3], _fmt(r[7], 3), r[8], _fmt(r[9], 2)))
    A("")

    A("## 2. PREDICTABILITY — WALK-FORWARD AUC (the headline)")
    A("")
    A("| set | asset | scope | n_train | n_test | base rate | AUC | "
      "95% CI (session bootstrap) | Brier | Brier(base) |")
    A("|---|---|---|---|---|---|---|---|---|---|")
    for r in res["auc"]:
        if r[11] != "ALL_FEATURES":
            continue
        A("| %s | %s | %s | %d | %d | %s | **%s** | [%s, %s] | %s | %s |"
          % (r[0], r[1], r[2], r[3], r[4], _fmt(r[5], 3), _fmt(r[6], 4),
             _fmt(r[7], 3), _fmt(r[8], 3), _fmt(r[9], 4), _fmt(r[10], 4)))
    A("")
    A("### which features carry it (pooled walk-forward, ALL assets)")
    A("")
    A("| set | feature | univariate AUC | leave-one-out dAUC |")
    A("|---|---|---|---|")
    for r in res["auc"]:
        if r[1] != "ALL" or r[2] != "WF_POOLED" or r[11] == "ALL_FEATURES":
            continue
        A("| %s | %s | %s | %s |"
          % (r[0], r[11], _fmt(r[12], 4), _fmt(r[13], 4)))
    A("")
    A("### the model's Holm-corrected coefficients (FIT, ALL assets, BASE)")
    A("")
    A("| term | beta (per SD) | se_CR1 | z | p |")
    A("|---|---|---|---|---|")
    for r in res["model"]:
        if r[0] != "BASE" or r[1] != "ALL" or r[2] != "FIT":
            continue
        A("| %s | %s | %s | %s | %s |"
          % (r[3], _fmt(r[4], 4), _fmt(r[7], 4), _fmt(r[8], 2),
             _fmt(r[9], 5)))
    A("")

    A("## 3. P030 CELL_VOL_CONCENTRATION — the band table at era scale")
    A("")
    A("| asset | era | band | cells | seat rate | winners | winner share | "
      "conc ratio | mean close $ |")
    A("|---|---|---|---|---|---|---|---|---|")
    for r in res["bands"]:
        if r[0] != "ALL":
            continue
        A("| %s | %s | %s | %d | %s | %d | %s | %s | %s |"
          % (r[0], r[1], r[2], r[5], _fmt(r[8], 3), r[10], _fmt(r[11], 3),
             _fmt(r[14], 2), _fmt(r[16], 0)))
    A("")
    A("### THE CURVE (ALL assets, FIT) — what each floor buys and costs")
    A("")
    A("| rv floor | cells kept | seat rate kept | seat rate refused | "
      "winners kept | winner share kept | winners refused | "
      "best refused cell $ | sessions fully refused |")
    A("|---|---|---|---|---|---|---|---|---|")
    for r in res["sweep"]:
        if r[0] != "ALL" or r[1] != "FIT":
            continue
        A("| %s | %d | %s | %s | %d | %s | %d | %s | %d |"
          % (_fmt(r[2], 0), r[3], _fmt(r[5], 3), _fmt(r[6], 3), r[9],
             _fmt(r[10], 3), r[11], _fmt(r[12], 0), r[18]))
    A("")
    A("VERDICT P030: **%s** — %s" % res["grade_p030"])
    A("")

    A("## 4. P031 CROSS_ASSET_FUEL_OVERHANG — agreement vs MIRROR")
    A("")
    A("| source | target | leg | era | cells | called | scoreable | agree | "
      "mirror | beats mirror | delta value $ | sign-test p |")
    A("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in res["pairs"]:
        if r[4] != "FIT" or r[18] != "-":
            continue
        A("| %s | %s | %s | %s | %d | %d | %d | %s | %s | %s | %s | %s |"
          % (r[1], r[2], r[3], r[4], r[5], r[6], r[8], _fmt(r[10], 3),
             _fmt(r[11], 3), r[12], _fmt(r[17], 0), _fmt(r[14], 4)))
    A("")
    A("### the MIRROR LAW, per session (CC-M2-13.1)")
    A("")
    A("| source | target | leg | era | sessions | won | tied | lost | "
      "mirror law holds | mean delta $ | Holm |")
    A("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in res["mirror"]:
        if r[4] != "FIT":
            continue
        A("| %s | %s | %s | %s | %d | %d | %d | %d | **%d** | %s | %s |"
          % (r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9],
             _fmt(r[10], 0), r[16]))
    A("")
    A("VERDICT P031: **%s** — %s" % res["grade_p031"])
    A("")

    A("## 5. MECHANISM DESTRUCTION")
    A("")
    A("| object | era | neutralised | edge | destroyed mean | destroyed sd | "
      "z | verdict |")
    A("|---|---|---|---|---|---|---|---|")
    for r in res["destr"]:
        A("| %s | %s | %s | %s | %s | %s | %s | **%s** |"
          % (r[0], r[1], r[2], _fmt(r[4], 4), _fmt(r[5], 4), _fmt(r[6], 4),
             _fmt(r[9], 2), r[10]))
    A("")
    A("SURVIVES = the real edge clears its own within-session shuffle by >= 2 "
      "sd; DESTROYED = it sits inside the null; **INVERTED = it sits BELOW "
      "the null**, i.e. the field carries information against the claim.")
    A("")
    A("## 6. EVERY GEE TEST, ONE HOLM FAMILY (%d tests)"
      % len([r for r in res["robust"] if np.isfinite(r[12])]))
    A("")
    A("| object | era | metric | cluster | n | clusters | beta | se_CR1 | "
      "z | p | n_eff | Holm |")
    A("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in res["robust"]:
        if r[19] != "HOLM_SIGNIFICANT":
            continue
        A("| %s | %s | %s | %s | %d | %d | %s | %s | %s | %s | %s | %s |"
          % (r[0], r[1], r[2], r[3], r[4], r[5], _fmt(r[7], 4),
             _fmt(r[10], 4), _fmt(r[11], 2), _fmt(r[12], 6),
             _fmt(r[15], 0), r[19]))
    A("")
    A("(only the Holm-significant rows are rendered; BATCH4_ROBUST.tsv "
      "carries every test.)")
    return "\n".join(L) + "\n"


# ====================================================================== build
def build(workers=4, limit_sessions=None):
    t0 = time.time()
    MC.verify_spec(force=True)
    cells, n_sessions, n_quar = scan(workers=workers,
                                     limit_sessions=limit_sessions)
    n_menu = attach_menu_hat(cells)
    MC.hb("batch4: menu_hat joined on %d/%d cells" % (n_menu, len(cells)))
    src = attach_cross_asset(cells)

    res = {}
    res["bands"] = band_rows(cells, [])
    res["sweep"] = sweep_rows(cells, [])
    res["base"] = base_rate_rows(cells, [])
    res["model"] = model_rows(cells, [])
    MC.hb("batch4: seat model fitted (%d coefficient rows)" % len(res["model"]))
    res["auc"] = auc_rows(cells, [])
    MC.hb("batch4: walk-forward AUC done (%d rows)" % len(res["auc"]))

    robust = []
    res["pairs"] = pair_rows(cells, src, [], robust)
    res["mirror"] = mirror_rows(cells, src, [])
    res["sens"] = sensitivity_rows(cells, src, [])
    p030_robust_rows(cells, robust)
    seat_robust_rows(cells, robust)
    _holm(robust, 12, len(ROBUST_COLUMNS))
    res["robust"] = robust
    res["destr"] = destruction_rows(cells, src, [])
    res["grade_p030"] = grade_p030(res["bands"], res["sweep"])
    res["grade_p031"] = grade_p031(res["pairs"], res["mirror"])

    phash = MC.params_hash(PARAMS)
    extra = ["CC-M2-17.5 census batch 4 — the CELL is the unit of analysis",
             "BOTH CC-M1-8 certificate readings are reported on every value "
             "row",
             "Holm-Bonferroni over the WHOLE batch, not per object",
             "HOLDOUT: no session with d8 >= %d was loaded (CC-M2-15.3)"
             % HOLDOUT_FROM_D8]
    cell_cols = ["asset"] + list(CELL_KEYS_I) + list(CELL_KEYS_F) + \
        ["era", "has_seat", "winner_side"]
    crows = [[c["asset"]] + [c[k] for k in CELL_KEYS_I]
             + [c[k] for k in CELL_KEYS_F]
             + [era_of_cell(c), int(c["n_win"] >= 1), winner_side(c)]
             for c in cells]
    W = MC.write_tsv
    W(os.path.join(OUT_DIR, "BATCH4_CELLS.tsv"), SECTION, phash, cell_cols,
      crows, extra=extra + ["one row per CELL; close_fuel_* is the cell's own "
                            "PHASE-CLOSE fuel map and is a SOURCE for OTHER "
                            "cells, never a feature of this one"])
    W(os.path.join(OUT_DIR, "P030_BANDS.tsv"), SECTION, phash,
      list(BAND_COLUMNS), res["bands"],
      extra=extra + ["conc_ratio = winner share / candidate share inside the "
                     "(asset, era) stratum; 1.00 = the band holds winners in "
                     "proportion to the candidates generated inside it"])
    W(os.path.join(OUT_DIR, "P030_SWEEP.tsv"), SECTION, phash,
      list(SWEEP_COLUMNS), res["sweep"],
      extra=extra + ["THE CURVE: every floor carries what it BUYS "
                     "(seat_rate_admitted, winner_share_kept) and what it "
                     "COSTS (n_winners_refused, best_refused_cell_usd, "
                     "n_sessions_fully_refused) — the 150-vs-250 question is "
                     "not a point estimate"])
    W(os.path.join(OUT_DIR, "SEAT_BASE_RATES.tsv"), SECTION, phash,
      list(BASE_COLUMNS), res["base"], extra=extra)
    W(os.path.join(OUT_DIR, "SEAT_MODEL.tsv"), SECTION, phash,
      list(MODEL_COLUMNS), res["model"],
      extra=extra + ["betas are per STANDARD DEVIATION of the feature; "
                     "menu_hat carries the CC-M2-14.1 RANK-VALID caveat"])
    W(os.path.join(OUT_DIR, "SEAT_AUC.tsv"), SECTION, phash,
      list(AUC_COLUMNS), res["auc"],
      extra=extra + ["WF_<year> = fitted on the FIT years strictly before it; "
                     "GATE_2025H1_FROZEN = the era-law frozen all-FIT fit; "
                     "univariate_auc is orientation-corrected (a feature's "
                     "sign is not its skill)"])
    W(os.path.join(OUT_DIR, "P031_PAIRS.tsv"), SECTION, phash,
      list(PAIR_COLUMNS), res["pairs"],
      extra=extra + ["leg OWN = the P009 control (dead twice); CROSS = one "
                     "named source asset; CROSS_BEST = the strongest overhang "
                     "among the OTHER assets, the day-6 form"])
    W(os.path.join(OUT_DIR, "P031_MIRROR.tsv"), SECTION, phash,
      list(MIRROR_COLUMNS), res["mirror"],
      extra=extra + ["CC-M2-13.1: mirror_law_holds = the estimator beat its "
                     "mirror on EVERY session and lost on none"])
    W(os.path.join(OUT_DIR, "P031_SENSITIVITY.tsv"), SECTION, phash,
      list(SENS_COLUMNS), res["sens"], extra=extra)
    W(os.path.join(OUT_DIR, "BATCH4_DESTRUCTION.tsv"), SECTION, phash,
      list(DESTR_COLUMNS), res["destr"], extra=extra)
    W(os.path.join(OUT_DIR, "BATCH4_ROBUST.tsv"), SECTION, phash,
      list(ROBUST_COLUMNS), res["robust"], extra=extra)

    pins = MC.pins_moved()
    el = time.time() - t0
    MC.write_text(os.path.join(OUT_DIR, "BATCH4_CENSUS_REPORT.md"),
                  report(cells, res, el, pins, n_sessions, n_quar))
    MC.write_json(os.path.join(OUT_DIR, "batch4_census.receipt.json"),
                  {"env": MC.env_receipt(PARAMS),
                   "n_cells": len(cells), "n_sessions": n_sessions,
                   "n_holdout_sessions_quarantined": n_quar,
                   "holdout_from_d8": HOLDOUT_FROM_D8,
                   "n_cells_with_menu_hat": n_menu,
                   "n_gee_tests": int(len([r for r in res["robust"]
                                           if np.isfinite(r[12])])),
                   "n_holm_significant":
                       int(len([r for r in res["robust"]
                                if r[19] == "HOLM_SIGNIFICANT"])),
                   "grade_P030": res["grade_p030"][0],
                   "grade_P031": res["grade_p031"][0],
                   "elapsed_sec": el, "pins_moved": pins,
                   "out_dir": OUT_DIR})
    MC.hb("batch4 census: %d cells, P030=%s, P031=%s, %.1fs"
          % (len(cells), res["grade_p030"][0], res["grade_p031"][0], el))
    return res


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--limit-sessions", type=int, default=None)
    a = p.parse_args()
    if a.workers > 6:
        raise SystemExit("workers capped at 6 (D-002 lane discipline)")
    build(workers=a.workers, limit_sessions=a.limit_sessions)
    return 0


if __name__ == "__main__":
    sys.exit(main())
