#!/usr/bin/python3
"""PORT M2 — CENSUS BATCH 5 (CC-M2-19.6, BINDING).

CC-M2-19.6 ordered six objects, all on the batch-4 population and under the
batch-1..4 discipline (FIT + GATE-2025H1 only, BOTH CC-M1-8 certificate
readings, destruction, session-clustered GEE with CR0/CR1 + Kish n_eff, ONE
Holm family over the whole batch, the mirror law on anything directional, and
the CONCENTRATOR-vs-RULE vocabulary of CC-M2-9.1):

  1. ROLLING SEAT-MODEL REFIT (the headline).  CC-M2-19.1: "seat state is a
     ROLLING PER-ROW object (row-level rv1800 >= 250 holds 92.8% of 7-session
     winners vs 1.76% below), not a per-cell call — cell-open anchors go stale
     on long phases."  The batch-4 seat model is refitted on ROW anchors with
     `unspent_sess` restored (CC-M2-19.4) and compared to the batch-4 cell-open
     model PAIRED on the same test cells.
  2. S10 SIDE GEOMETRY under the mirror law (d_POC sign + in_VA), at BOTH
     grains — the last surviving hand-instrument for stage 2 (CC-M2-18.3).
  3. P032 PRIOR_CELL_TRAVEL — the sign contradiction between the day-7 ledger
     (prior-cell range >= $1,000 seats a cell) and CC-M2-18.1 (prior-cell
     MAGNITUDE is NEGATIVE in the accepted seat model).  Censused at both
     grains AND both readings (marginal vs partial-given-rv1800), because a
     sign flip has exactly two honest explanations and this separates them.
  4. P033 FEASIBILITY_IS_RUNWAY_TIMES_VOL — census-first as ruled (CC-M2-19.3),
     concentrator framing, raw runway band as the control.
  5. V2/V3 POOLED RE-GRADE over ALL SEVEN study sessions with the CC-M2-17.4
     seat-spender split (panel_score.veto_census) + the pooled replay delta.
  6. S7/S8 EVENT-STATISTIC CENSUSES on the full 3,341-session event cache:
     c2f, side-resolved erosion (dBsz/dAsz), through-book prints, each against
     winner content at ROW grain.

THE TWO GRAINS, NAMED ONCE
  ROW   = one v3-roster candidate (asset, session, decision second, side).
  CELL  = (asset, session, phase_dec) — CC-M2-17.1's seat-existence unit and
          batch 4's unit of analysis.  Every cell statistic here is built from
          THIS module's own rows, so the row and cell tables are the same data
          read at two resolutions (batch 4 built cells directly; the cell block
          below reproduces its fields exactly and t04 pins that).

THE ROLLING SEAT STATE (the batch's one new estimand)
  y_row = "a D-021-class seat still exists in this cell AT OR AFTER this row"
        = any winner in the cell with dec_sec >= this row's dec_sec.
  Features are read AT THE ROW (rv1800, unspent_sess) or are cell-constant
  facts already available at the cell open (the batch-4 set).  Three scores are
  compared on the SAME test cells, because "rolling beats cell-open" is a claim
  about two DECISION PROCEDURES and each has to be priced honestly:
    OPEN        the batch-4 model, one call at the cell open        (causal)
    OPEN+UNS    the same + unspent_sess at the cell open            (causal)
    ROLL@open   the rolling model evaluated on the cell's FIRST row (causal —
                isolates how much of any gain is the added feature rather than
                the moving anchor)
    ROLL_MAX    the rolling model's per-cell series aggregated by MAX — "did
                the monitor ever turn on in this cell".  This is a LATER
                commitment than the cell open (it may fire hours in), and it is
                reported as an operating mode, never as a cell-open forecast.
  The rolling model's own fully-causal reading is its ROW-grain AUC, reported
  beside all four.

DISCIPLINE (restated so this file reads alone)
  * population = frozen v3 roster, every FIT session (2021-2024) + the
    GATE-2025 H1 echo; sessions with d8 >= 20250701 are NEVER LOADED
    (CC-M2-15.3), and the receipt stamps the count refused.
  * BOTH CC-M1-8 readings (walled phase-close = adoption, walled peak-exit =
    companion) on every value row.
  * DESTRUCTION: the carrying field is shuffled WITHIN ITS OWN SESSION, 40
    replicates, seeded; the destroyed quantity is the EDGE; verdicts are
    sign-aware (SURVIVES / DESTROYED / INVERTED).
  * INFERENCE: GEE, independence working correlation, Liang-Zeger sandwich
    clustered on SESSION (CR0 + Cameron-Miller CR1) + Kish ICC/DEFF/n_eff.
  * HOLM-BONFERRONI over THE WHOLE BATCH — every GEE test of all six objects
    is one family.
  * REUSE: the batch-4 estimators (gee_multi, the logit fitter, the AUC and
    cluster bootstrap, the within-session shuffle, Holm, the sign test) are
    IMPORTED from batch4_census, not re-typed; panel_score owns the veto
    census; pattern_lib owns every field.

OUTPUT (D-018: bulk under artifacts/cache/)
  artifacts/cache/port/m2/pattern_census/BATCH5_CENSUS_REPORT.md
  artifacts/cache/port/m2/pattern_census/
      BATCH5_CELLS.tsv          the cell population (batch-4 fields + rolling)
      SEAT_ROLLING_AUC.tsv      the headline: paired rolling vs cell-open AUC
      SEAT_ROLLING_MODEL.tsv    GEE coefficients of both models
      SEAT_ROLLING_BANDS.tsv    row-grain rv1800 bands (the day-7 92.8% claim)
      S10_SIDE.tsv              d_POC/in_VA side geometry, both grains
      S10_MIRROR.tsv            the per-session mirror law for S10
      P032_GRAINS.tsv           prior-cell travel, both grains, both readings
      P033_DECILES.tsv          runway x rv1800 deciles, runway band control
      VETO_POOLED.tsv           V2/V3 pooled re-grade + seat-spender split
      VETO_SESSIONS.tsv         per-session replay deltas
      EVENT_STATS.tsv           c2f / erosion / through-book, row grain
      EVENT_MIRROR.tsv          the erosion side claim under the mirror law
      BATCH5_DESTRUCTION.tsv    mechanism destruction
      BATCH5_ROBUST.tsv         every GEE test, ONE Holm family
      batch5_census.receipt.json

Run:  lab/run.sh port-m2-batch5 -- /usr/bin/python3 engine/port_m2/batch5_census.py
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
import assemble as A                      # noqa: E402
import common as C                        # noqa: E402  (m0 substrate: ASSETS)
import tape as TAPE                       # noqa: E402  (event cache reader)
import census_common as X                 # noqa: E402
import episode_v2 as EV                   # noqa: E402  (GEE sandwich, ICC)
import p001_census as P1                  # noqa: E402  (census machinery)
import batch4_census as B4                # noqa: E402  (batch-4 estimators)
import panel_score as PS                  # noqa: E402  (the veto census)
import e1d7_policy as P7                  # noqa: E402  (the CORE + V2/V3 forms)

SECTION = ("DISCRETIONARY_METHOD §4.2 name->count census — batch 5 "
           "(CC-M2-19.6: rolling seat, S10 side, P032, P033, V2/V3, events)")
OUT_DIR = MC.out_path("pattern_census", "_")[:-1]

FIT_YEARS = P1.FIT_YEARS                  # (2021, 2022, 2023, 2024)
GATE_YEAR = P1.GATE_YEAR                  # 2025
HOLDOUT_FROM_D8 = B4.HOLDOUT_FROM_D8      # 20250701 (CC-M2-15.3)
PHASES = X.PHASE_NAMES
ERAS = B4.ERAS                            # ("FIT", "GATE_2025H1")

CONCENTRATOR_MIN = B4.CONCENTRATOR_MIN    # 1.25x
DESTRUCTION_REPS = P1.DESTRUCTION_REPS    # 40
DESTRUCTION_SEED = 20260818

# ---- item 1: the seat models ------------------------------------------------
CELL_FEATURES = B4.SEAT_FEATURES_BASE     # the batch-4 BASE set, verbatim
CELL_FEATURES_UNS = CELL_FEATURES + ("unspent_sess",)
ROW_FEATURES = ("rv1800", "unspent_sess", "prev_ret_sign", "prev_ret_mag",
                "overnight_ratio", "release_in_ph", "dow_sin", "dow_cos")
ROLL_RV_BANDS = (0.0, 100.0, 150.0, 250.0, 400.0, 1e18)
ROLL_RV_BAND_NAMES = ("lt100", "100-150", "150-250", "250-400", "ge400")

# ---- item 2: S10 ------------------------------------------------------------
S10_THR_GRID = (0.0, 250.0, 500.0, 1000.0)
S10_THR = 500.0                           # the day-7 S2c declared threshold

# ---- item 3: P032 -----------------------------------------------------------
P032_CLAUSE_USD = 1000.0                  # the day-7 S1b clause, verbatim

# ---- item 4: P033 -----------------------------------------------------------
P033_DECILES = 10
P025_BANDS = ((0, 3600), (3600, 12000), (12000, 21600), (21600, 36000),
              (36000, 10 ** 9))
P025_BAND_NAMES = ("lt1h", "1h-12000s", "12000-21600s", "21600-36000s",
                   "ge36000s")

# ---- item 5: the seven E1 study sessions (CC-M2-8.1 draw, in order) ---------
STUDY_D8 = (20210701, 20210702, 20210705, 20210706, 20210707, 20210708,
            20210709)

# ---- item 6: the event statistics ------------------------------------------
EVENT_STATS = ("c2f_60", "c2f_300", "dbsz_min", "dasz_min", "thru_n")
EROSION_THR_GRID = (0.0, 5.0, 20.0, 100.0)
EROSION_THR = 20.0

BOOT_REPS = 400
BOOT_SEED = 20260818

PARAMS = {
    "spec_section": SECTION,
    "order": "CC-M2-19.6 — census batch 5",
    "definition_source": "provenance/port_m2/PATTERN_LEDGER.tsv (P030, P032, "
                         "P033, P028) + provenance/port_m2/E1D7_CELL_LEDGER.md "
                         "+ E1_POSTMORTEMS day-6/day-7 + "
                         "engine/port_m2/e1d7_policy.py (CORE, V2, V3)",
    "grains": "ROW = one v3-roster candidate; CELL = (asset, session, "
              "phase_dec).  Cells are built from THIS module's rows, so both "
              "tables are one population read at two resolutions.",
    "rolling_seat_state": "y_row = a D-021-class winner exists in the row's "
                          "own cell at a decision second >= the row's "
                          "(CC-M2-19.1: the seat is a rolling per-row object). "
                          "Features: rv1800 AT THE ROW, unspent_sess AT THE "
                          "ROW (CC-M2-19.4, restored), plus the batch-4 "
                          "cell-open set (%s)" % ",".join(CELL_FEATURES),
    "rolling_vs_open": "four scores on the SAME test cells against the SAME "
                       "target (cell has >=1 D-021 winner): OPEN (batch-4 "
                       "model), OPEN+UNS, ROLL@open (rolling model at the "
                       "cell's first row — causal), ROLL_MAX (the rolling "
                       "series aggregated by max — an operating mode that "
                       "commits later than the open, never a cell-open "
                       "forecast).  Deltas carry a PAIRED session-cluster "
                       "bootstrap (the same resampled sessions score both).",
    "walk_forward": "year Y is scored by a fit on the FIT years strictly "
                    "before it; the GATE echo is scored by the frozen all-FIT "
                    "fit (era law, D-058)",
    "S10": "d_POC = (entry_mid - developing POC) x mult and in_VA, read off "
           "the SAME causal S10 developing row sections.s10_profile reads "
           "(dev_sec <= dec_sec).  SIDE CALL: in_VA == 0 AND |d_POC| >= THR "
           "-> above value = SHORT, below value = LONG; else NO-CALL.  Scored "
           "at ROW grain (against the row's own side) and at CELL grain "
           "(read at the cell open, against the winner-majority side), both "
           "under the mirror law (CC-M2-13.1).",
    "P032": "prior-cell travel in three spellings — prev_phase_range_usd "
            "(the day-7 S1b field), |prev_phase_ret_usd| (the batch-4 "
            "prev_ret_mag field CC-M2-18.1 found NEGATIVE) and the signed "
            "return — each MARGINAL and PARTIAL (with rv1800 in the same "
            "model), at BOTH grains.  The 2x3x2 table is the contradiction's "
            "resolution.",
    "P033": "runway_binding_sec x rv1800 at the ROW, and its sqrt form "
            "sigma_to_exit = rv1800 * sqrt(runway/1800) — the grade the round "
            "already computes.  Deciles cut on the FIT pool and APPLIED to the "
            "GATE echo; the raw runway band is the control.  A magnitude "
            "object: no mirror, so CONCENTRATOR is its ceiling.",
    "veto_regrade": "V2/V3 exactly as engine/port_m2/e1d7_policy.py defines "
                    "them, over ALL SEVEN E1 study sessions.  Pre-veto pool = "
                    "the frozen five-term CORE (e1d7_policy.terms) on every "
                    "candidate of those sessions — one uniform pool on every "
                    "session, so the pooled statistic is not a mix of arms.  "
                    "Reported with panel_score.veto_census's seat-spender "
                    "split (DP + REPLAY) and the pooled REPLAY DELTA, which "
                    "is the reading ERA_NOTES §67 showed can disagree "
                    "completely with the sole-block statistic.",
    "event_stats": "S7 c2f = n_cancel / traded size over [dec-w, dec]; S7 "
                   "dBsz/min, dAsz/min = (last - first) L1 size x 60/w over "
                   "the 60s window; S8 through-book = trade prints outside the "
                   "prevailing L1 over [dec-600, dec].  All three are "
                   "sections.py's own forms, vectorised over the corpus event "
                   "cache; t01 pins them against the committed day-7 triage "
                   "index row for row.",
    "erosion_side": "DIRECTIONAL, so the mirror law applies: the L1 side that "
                    "is RESTOCKING faster is the side being defended -> call "
                    "LONG when dBsz - dAsz >= THR, SHORT when <= -THR, else "
                    "NO-CALL.  Declared here before the count.",
    "value": "c_c_roster.certificates — walled PHASE-CLOSE (adoption) and "
             "walled PEAK-EXIT (CC-M1-8 companion), both always reported",
    "population": "frozen v3 roster, FIT years %s; %d-H1 as an EVAL-ONLY GATE "
                  "echo.  HOLDOUT QUARANTINE: sessions with d8 >= %d are NEVER "
                  "LOADED (CC-M2-15.3)"
                  % (list(FIT_YEARS), GATE_YEAR, HOLDOUT_FROM_D8),
    "destruction": "the carrying field shuffled WITHIN SESSION, %d replicates, "
                   "RandomState(%d + index); the destroyed quantity is the "
                   "EDGE; verdicts sign-aware (SURVIVES/DESTROYED/INVERTED)"
                   % (DESTRUCTION_REPS, DESTRUCTION_SEED),
    "inference": "CC-M1-12.4 — GEE independence working correlation with the "
                 "Liang-Zeger sandwich (CR0 + Cameron-Miller CR1); Kish "
                 "one-way ICC/DEFF for n_eff; Holm-Bonferroni over THE WHOLE "
                 "BATCH",
    "grading": "CC-M2-9.1 — ENTRY/VETO RULE (Holm-significant beta on the "
               "adoption metric) vs CONCENTRATOR (>= %.2fx winner rate or "
               "conditional value, no adoption edge) vs NULL" % CONCENTRATOR_MIN,
    "S10_thresholds": list(S10_THR_GRID),
    "erosion_thresholds": list(EROSION_THR_GRID),
    "study_sessions": list(STUDY_D8),
    "frame": PL.PARAMS_FRAME,
    "frame_v2": PL.PARAMS_FRAME_V2,
    "frame_v3": PL.PARAMS_FRAME_V3,
}


# ======================================================================= scan
_F64 = ("cert_close", "cert_peak", "mae", "rv1800", "rv60", "atr",
        "unspent_sess", "prev_range", "prev_ret", "pre_cell_range",
        "entry_mid", "d_poc", "slope_1m", "range_so_far",
        "c2f_60", "c2f_300", "dbsz_min", "dasz_min")
_I32 = ("dec_sec", "runway_phase", "runway_binding", "phase_age",
        "extreme_age", "f60_n", "f60_vol", "f60_sflow", "f5m_vol", "f5m_sflow",
        "fph_vol", "fuel_above", "fuel_below", "fuel_total", "cell_first_dec",
        "thru_n", "thru_bid", "thru_ask", "n_ev_60")
_I8 = ("side", "phase", "day_type", "in_va", "release_in_ph", "dow")
_BOOL = ("winner", "walled", "cell_open", "sess_close_exit")
_CONCAT = _F64 + _I32 + _I8 + _BOOL

_WANT_EVENTS = True                        # set by the pool initialiser


def _init(want_events):
    global _WANT_EVENTS
    _WANT_EVENTS = bool(want_events)
    MC.verify_spec(force=True)


def _s10_of(asset, d8, dec_sec, entry_mid):
    """d_POC (usd) and in_VA off the CAUSAL developing profile row.

    sections.s10_profile takes the last `dev_sec` STRICTLY before the decision
    second (searchsorted left, minus one) and derives in_VA from the VA edges,
    refusing when an edge is missing.  Reproduced here, vectorised."""
    z, _p = A.load_profile(asset, int(d8))
    n = dec_sec.size
    if z is None:
        return (np.full(n, np.nan), np.full(n, -1, dtype=np.int64))
    spec = C.ASSETS[asset]
    tick, mult = float(spec["tick_px"]), float(spec["mult"])
    ds = z["dev_sec"]
    j = np.searchsorted(ds, dec_sec, side="left") - 1
    ok = j >= 0
    jj = np.maximum(j, 0)
    poc = np.where(ok, z["dev_poc_tick"][jj] * tick, np.nan)
    vah = np.where(ok, z["dev_vah_tick"][jj] * tick, np.nan)
    val = np.where(ok, z["dev_val_tick"][jj] * tick, np.nan)
    d_poc = (entry_mid - poc) * mult
    edges_ok = np.isfinite(val) & np.isfinite(vah)
    in_va = np.where(edges_ok,
                     ((val <= entry_mid) & (entry_mid <= vah)).astype(np.int64),
                     -1)                   # -1 = REFUSED, never "outside"
    return d_poc, in_va


def _event_stats(asset, d8, open_utc, dec_sec):
    """S7 c2f/erosion + S8 through-book at every decision second.

    sections.s7_book / s8_flow verbatim: the windows are [dec_ts - w, dec_ts]
    inclusive of the decision second (hi = dec_ts + 1 in nanoseconds), c2f is
    n_cancel / traded SIZE, the erosion terms are the L1 size difference
    between the window's last and first records scaled to a minute, and the
    through-book count is the 600s count of prints outside the prevailing L1.
    """
    n = dec_sec.size
    out = {k: np.full(n, np.nan) for k in ("c2f_60", "c2f_300", "dbsz_min",
                                           "dasz_min")}
    out["thru_n"] = np.full(n, -1, dtype=np.int64)
    out["thru_bid"] = np.full(n, -1, dtype=np.int64)
    out["thru_ask"] = np.full(n, -1, dtype=np.int64)
    out["n_ev_60"] = np.full(n, -1, dtype=np.int64)
    npz_p, _j = TAPE._paths(asset, int(d8))
    if not os.path.exists(npz_p):
        return out
    z = np.load(npz_p, allow_pickle=False)
    ev = {k: z[k] for k in z.files}
    z.close()
    ts = ev["ts_ns"]
    if ts.size == 0:
        return out
    act = ev["action"]
    sz = ev["size"].astype(np.int64)
    tag, _flow = TAPE.classify_trades(ev)
    cum_c = np.concatenate([[0], np.cumsum(act == ord("C"))])
    cum_t = np.concatenate([[0], np.cumsum(np.where(act == ord("T"), sz, 0))])
    cum_thru = np.concatenate([[0], np.cumsum((tag == TAPE.TRADE_THRU_B)
                                              | (tag == TAPE.TRADE_THRU_A))])
    cum_tb = np.concatenate([[0], np.cumsum(tag == TAPE.TRADE_THRU_B)])
    dec_ts = int(open_utc) + dec_sec.astype(np.int64)
    hi = np.searchsorted(ts, (dec_ts + 1) * 10 ** 9, side="left")
    for w, key in ((60, "c2f_60"), (300, "c2f_300")):
        lo = np.searchsorted(ts, (dec_ts - w) * 10 ** 9, side="left")
        fills = (cum_t[hi] - cum_t[lo]).astype(np.float64)
        nc = (cum_c[hi] - cum_c[lo]).astype(np.float64)
        with np.errstate(invalid="ignore", divide="ignore"):
            out[key] = np.where(fills > 0, nc / fills, np.nan)
        if w == 60:
            nn = hi - lo
            out["n_ev_60"] = nn.astype(np.int64)
            good = nn > 1
            bi = np.maximum(hi - 1, 0)
            for nm, arr in (("dbsz_min", ev["bid_sz"]),
                            ("dasz_min", ev["ask_sz"])):
                out[nm] = np.where(
                    good,
                    (arr[bi].astype(np.float64)
                     - arr[np.minimum(lo, ts.size - 1)].astype(np.float64))
                    * 60.0 / w, np.nan)
    lo6 = np.searchsorted(ts, (dec_ts - 600) * 10 ** 9, side="left")
    out["thru_n"] = (cum_thru[hi] - cum_thru[lo6]).astype(np.int64)
    out["thru_bid"] = (cum_tb[hi] - cum_tb[lo6]).astype(np.int64)
    out["thru_ask"] = out["thru_n"] - out["thru_bid"]
    return out


def _unspent_session(asset, trade_date_iso, range_so_far):
    """S3 COVERAGE SESSION `unspent` = exp_move_q50(SESSION) - range so far.

    sections.s3_path's own arithmetic; NaN when the SESSION fvol row carries no
    move_q50 (the REFUSED class — SI carries it on four E1 study sessions and
    the day-7 ledger leans on that fact)."""
    row = A.fvol_rows().get((asset, trade_date_iso, "SESSION"))
    if not row:
        return np.full(range_so_far.size, np.nan)

    def _f(v):
        try:
            return float(v)
        except Exception:                  # noqa: BLE001 — '' is REFUSED
            return float("nan")
    q50 = _f(row.get("move_q50_usd_per_sigma")) * _f(row.get("sigma_hat_usd"))
    if not np.isfinite(q50) or q50 <= 0:
        return np.full(range_so_far.size, np.nan)
    return q50 - range_so_far


def _pack(f, asset, d8):
    r = A.roster(asset)
    entry_mid = r["entry_mid"][f["i"]].astype(np.float64)
    dec = f["dec_sec"].astype(np.int64)
    sess = A.load_session(asset, int(d8))
    open_utc = int(sess["s"].meta["open_utc"])
    iso = sess["trade_date"].isoformat()
    d_poc, in_va = _s10_of(asset, d8, dec, entry_mid)
    uns = _unspent_session(asset, iso, f["range_so_far_usd"].astype(np.float64))
    ev = (_event_stats(asset, d8, open_utc, dec) if _WANT_EVENTS
          else {"c2f_60": np.full(dec.size, np.nan),
                "c2f_300": np.full(dec.size, np.nan),
                "dbsz_min": np.full(dec.size, np.nan),
                "dasz_min": np.full(dec.size, np.nan),
                "thru_n": np.full(dec.size, -1, dtype=np.int64),
                "thru_bid": np.full(dec.size, -1, dtype=np.int64),
                "thru_ask": np.full(dec.size, -1, dtype=np.int64),
                "n_ev_60": np.full(dec.size, -1, dtype=np.int64)})
    src = {
        "cert_close": f["cert_close_usd"], "cert_peak": f["cert_peak_usd"],
        "mae": f["mae_before_argmax"], "rv1800": f["rv1800_usd"],
        "rv60": f["rv60_usd"], "atr": f["atr_usd"], "unspent_sess": uns,
        "prev_range": f["prev_phase_range_usd"],
        "prev_ret": f["prev_phase_ret_usd"],
        "pre_cell_range": f["pre_cell_range_usd"], "entry_mid": entry_mid,
        "d_poc": d_poc, "slope_1m": f["slope_1m_usd"],
        "range_so_far": f["range_so_far_usd"],
        "c2f_60": ev["c2f_60"], "c2f_300": ev["c2f_300"],
        "dbsz_min": ev["dbsz_min"], "dasz_min": ev["dasz_min"],
        "dec_sec": dec, "runway_phase": f["runway_phase_sec"],
        "runway_binding": f["runway_binding_sec"],
        "phase_age": f["phase_age_sec"], "extreme_age": f["extreme_age_sec"],
        "f60_n": f["f60_n"], "f60_vol": f["f60_vol"],
        "f60_sflow": f["f60_sflow"], "f5m_vol": f["f5m_vol"],
        "f5m_sflow": f["f5m_sflow"], "fph_vol": f["fph_vol"],
        "fuel_above": f["fuel_above"], "fuel_below": f["fuel_below"],
        "fuel_total": f["fuel_total"],
        "cell_first_dec": f["cell_first_dec_sec"], "thru_n": ev["thru_n"],
        "thru_bid": ev["thru_bid"], "thru_ask": ev["thru_ask"],
        "n_ev_60": ev["n_ev_60"], "side": f["side"], "phase": f["phase_dec"],
        "day_type": f["day_type"], "in_va": in_va,
        "release_in_ph": f["sched_release_in_phase"], "dow": f["dow"],
        "winner": f["winner"], "walled": f["walled"],
        "cell_open": f["cell_open"],
        "sess_close_exit": f["session_close_exit"],
    }
    out = {"asset": asset, "d8": int(d8), "cid": f["cid"]}
    for k in _F64:
        out[k] = np.asarray(src[k], dtype=np.float64)
    for k in _I32:
        out[k] = np.asarray(src[k], dtype=np.int64).astype(np.int32)
    for k in _I8:
        out[k] = np.asarray(src[k], dtype=np.int64).astype(np.int8)
    for k in _BOOL:
        out[k] = np.asarray(src[k], dtype=bool)
    return out


def _one(job):
    asset, d8 = job
    try:
        f = PL.frame(asset, int(d8), with_levels=False, with_v3=True)
        if f is None:
            return ("EMPTY", asset, int(d8), "")
        p = _pack(f, asset, int(d8))
    except Exception as e:                # noqa: BLE001 — surfaced, not hidden
        return ("ERROR", asset, int(d8), repr(e)[:300])
    # assemble memoises every session receipt with its trade arrays; a worker
    # sees hundreds of sessions, so drop this one before the next.
    A._MEM.pop(("sess", asset, int(d8)), None)
    return ("OK", p)


def scan(assets=MC.ASSET_ORDER, workers=6, limit_sessions=None,
         want_events=True):
    jobs, quarantined = [], 0
    for a in assets:
        ds = PL.sessions(a, years=set(FIT_YEARS) | {GATE_YEAR})
        keep = [d for d in ds if int(d) < HOLDOUT_FROM_D8]
        quarantined += len(ds) - len(keep)
        if limit_sessions:
            keep = keep[:limit_sessions]
        jobs += [(a, d) for d in keep]
    jobs.sort()
    parts, errs = [], []
    t0 = time.time()
    if workers and workers > 1:
        with mp.Pool(processes=int(workers), initializer=_init,
                     initargs=(want_events,)) as pool:
            for n, res in enumerate(pool.imap(_one, jobs, chunksize=4), 1):
                if res[0] == "OK":
                    parts.append(res[1])
                elif res[0] == "ERROR":
                    errs.append((res[1], res[2], res[3]))
                if n % 200 == 0:
                    MC.hb("batch5 scan %d/%d  %.1fs"
                          % (n, len(jobs), time.time() - t0))
    else:
        _init(want_events)
        for j in jobs:
            res = _one(j)
            if res[0] == "OK":
                parts.append(res[1])
            elif res[0] == "ERROR":
                errs.append((res[1], res[2], res[3]))
    if errs:
        raise RuntimeError("batch5 scan: %d session(s) failed, first=%s"
                           % (len(errs), errs[0]))
    parts.sort(key=lambda p: (p["asset"], p["d8"]))
    D = {}
    for k in _CONCAT:
        D[k] = np.concatenate([p[k] for p in parts])
    D["cid"] = np.concatenate([p["cid"] for p in parts])
    D["asset"] = np.concatenate([np.full(p["dec_sec"].size, p["asset"])
                                 for p in parts])
    D["d8"] = np.concatenate([np.full(p["dec_sec"].size, p["d8"],
                                      dtype=np.int32) for p in parts])
    D["year"] = (D["d8"] // 10000).astype(np.int32)
    keys = np.array(["%s-%08d" % (a, d)
                     for a, d in zip(D["asset"].tolist(), D["d8"].tolist())])
    uniq, D["cluster"] = np.unique(keys, return_inverse=True)
    D["session_key"] = keys
    D["cell_key"] = np.array(["%s-%08d-%d" % (a, d, p) for a, d, p in
                              zip(D["asset"].tolist(), D["d8"].tolist(),
                                  D["phase"].tolist())])
    D["side"] = D["side"].astype(np.int64)
    D["n_sessions"] = int(uniq.size)
    D["n_quarantined"] = quarantined
    D["n_jobs"] = len(jobs)
    D["era"] = np.where(np.isin(D["year"], FIT_YEARS), ERAS[0],
                        np.where(D["year"] == GATE_YEAR, ERAS[1], "OTHER"))
    MC.hb("batch5 scan: %d rows over %d sessions (%d holdout quarantined), "
          "%.1fs" % (D["dec_sec"].size, uniq.size, quarantined,
                     time.time() - t0))
    return D


# ============================================ the rolling seat state + cells
def rolling_seat_state(D):
    """y_row = a winner exists in this row's CELL at dec_sec >= this row's.

    Computed per cell as a REVERSE running OR over rows in decision order, so
    the row that carries the last winner is itself seated (the seat can be
    spent on that very row) and every earlier row of the cell is seated too."""
    y = np.zeros(D["dec_sec"].size, dtype=np.float64)
    order = np.lexsort((D["dec_sec"], D["cell_key"]))
    ck = D["cell_key"][order]
    win = D["winner"][order]
    seat = np.zeros(ck.size, dtype=bool)
    seen = False
    for t in range(ck.size - 1, -1, -1):
        if t == ck.size - 1 or ck[t] != ck[t + 1]:
            seen = False
        seen = seen or bool(win[t])
        seat[t] = seen
    y[order] = seat.astype(np.float64)
    return y


def cells_of(D):
    """The CELL population, with batch-4's field names reproduced exactly."""
    order = np.lexsort((D["dec_sec"], D["cell_key"]))
    ck = D["cell_key"][order]
    starts = [0] + (np.flatnonzero(ck[1:] != ck[:-1]) + 1).tolist()
    stops = starts[1:] + [ck.size]
    cells = []
    for s, e in zip(starts, stops):
        idx = order[s:e]
        first = idx[0]
        w = D["winner"][idx]
        cc = D["cert_close"][idx]
        cp = D["cert_peak"][idx]
        sd = D["side"][idx]
        pos = cc[cc > 0]
        cells.append({
            "asset": str(D["asset"][first]), "d8": int(D["d8"][first]),
            "year": int(D["year"][first]), "phase": int(D["phase"][first]),
            "rows": idx,
            "n_cand": int(idx.size), "n_win": int(w.sum()),
            "n_win_long": int((w & (sd > 0)).sum()),
            "n_win_short": int((w & (sd < 0)).sum()),
            "first_dec_sec": int(D["dec_sec"][first]),
            "last_dec_sec": int(D["dec_sec"][idx[-1]]),
            # ---- cell-OPEN features (strictly prior to any seat) ----
            "rv1800_open": float(D["rv1800"][first]),
            "rv60_open": float(D["rv60"][first]),
            "atr_open": float(D["atr"][first]),
            "unspent_open": float(D["unspent_sess"][first]),
            "prev_ret_usd": float(D["prev_ret"][first]),
            "prev_range_usd": float(D["prev_range"][first]),
            "pre_cell_range_usd": float(D["pre_cell_range"][first]),
            "release_in_ph": int(D["release_in_ph"][first]),
            "dow": int(D["dow"][first]),
            "d_poc_open": float(D["d_poc"][first]),
            "in_va_open": int(D["in_va"][first]),
            "menu_hat": float("nan"),      # BASE-only in this batch (CC-M2-19.6)
            # ---- value ----
            "mean_close": float(cc.mean()), "mean_peak": float(cp.mean()),
            "sum_close": float(cc.sum()), "sum_peak": float(cp.sum()),
            "cond_close": float(pos.mean()) if pos.size else float("nan"),
            "win_close_sum": float(cc[w].sum()),
            "win_close_sum_long": float(cc[w & (sd > 0)].sum()),
            "win_close_sum_short": float(cc[w & (sd < 0)].sum()),
        })
    cells.sort(key=lambda c: (c["asset"], c["d8"], c["phase"]))
    return cells


def era_of_cell(c):
    return B4.era_of_cell(c)


def has_seat(cells):
    return np.array([1.0 if c["n_win"] >= 1 else 0.0 for c in cells])


# ------------------------------------------------------------- design matrices
def cell_design(cells, names):
    """The batch-4 cell-open design, extended by unspent_sess."""
    cols = []
    for nm in names:
        if nm == "unspent_sess":
            cols.append(np.array([c["unspent_open"] for c in cells],
                                 dtype=np.float64))
        else:
            cols.append(B4.design(cells, (nm,))[:, 0])
    return (np.column_stack(cols) if cols
            else np.zeros((len(cells), 0)))


def row_design(D, idx, names):
    """The ROLLING design: rv1800/unspent_sess at the ROW, the rest cell-open."""
    n = idx.size
    cols = []
    for nm in names:
        if nm == "rv1800":
            v = D["rv1800"][idx]
        elif nm == "unspent_sess":
            v = D["unspent_sess"][idx]
        elif nm == "prev_ret_sign":
            v = np.where(np.isfinite(D["prev_ret"][idx]),
                         np.sign(D["prev_ret"][idx]), np.nan)
        elif nm == "prev_ret_mag":
            v = np.abs(D["prev_ret"][idx])
        elif nm == "overnight_ratio":
            a = D["atr"][idx]
            with np.errstate(invalid="ignore", divide="ignore"):
                v = np.where(np.isfinite(D["pre_cell_range"][idx]) & (a > 0),
                             D["pre_cell_range"][idx] / a, np.nan)
        elif nm == "release_in_ph":
            v = D["release_in_ph"][idx].astype(np.float64)
        elif nm == "dow_sin":
            v = np.sin(2 * np.pi * D["dow"][idx].astype(np.float64) / 7.0)
        elif nm == "dow_cos":
            v = np.cos(2 * np.pi * D["dow"][idx].astype(np.float64) / 7.0)
        else:
            raise KeyError(nm)
        cols.append(np.asarray(v, dtype=np.float64))
    return np.column_stack(cols) if cols else np.zeros((n, 0))


# ========================================== item 1: the rolling seat refit
AUC_COLUMNS = ("asset", "scope", "grain", "model", "n_train", "n_test",
               "base_rate_test", "auc", "auc_lo_boot", "auc_hi_boot", "brier",
               "brier_base", "delta_vs_open", "delta_lo_boot", "delta_hi_boot",
               "delta_p_boot", "verdict")


def _paired_boot(y, scores, cl, reps=BOOT_REPS, seed=BOOT_SEED):
    """Session-cluster bootstrap of several scores AT ONCE.

    The same resampled session list scores every model, so the AUC differences
    are PAIRED — the only honest way to put a CI on 'rolling beats cell-open'
    when both are scored on the same cells.  -> {name: (lo, hi)} for the AUCs
    and {name: (lo, hi, p)} for the deltas against `scores['OPEN']`."""
    uniq, inv = np.unique(cl, return_inverse=True)
    if uniq.size < 20:
        nan3 = (float("nan"), float("nan"), float("nan"))
        return ({k: nan3[:2] for k in scores}, {k: nan3 for k in scores})
    idx_by = [np.nonzero(inv == g)[0] for g in range(uniq.size)]
    rng = np.random.RandomState(seed)
    acc = {k: [] for k in scores}
    dlt = {k: [] for k in scores}
    for _ in range(reps):
        pick = rng.randint(0, uniq.size, uniq.size)
        take = np.concatenate([idx_by[g] for g in pick])
        yb = y[take]
        if yb.max() == yb.min():
            continue
        a = {k: B4.auc(yb, s[take]) for k, s in scores.items()}
        if not all(np.isfinite(v) for v in a.values()):
            continue
        for k in scores:
            acc[k].append(a[k])
            dlt[k].append(a[k] - a["OPEN"])
    out_a, out_d = {}, {}
    for k in scores:
        v = np.array(acc[k])
        d = np.array(dlt[k])
        if v.size < 20:
            out_a[k] = (float("nan"), float("nan"))
            out_d[k] = (float("nan"), float("nan"), float("nan"))
            continue
        out_a[k] = (float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5)))
        # two-sided bootstrap p for delta != 0 (the share of the mass on the
        # wrong side of zero, doubled; 1/reps floor, never zero)
        p = 2.0 * min(float((d <= 0).mean()), float((d >= 0).mean()))
        out_d[k] = (float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5)),
                    float(max(p, 1.0 / max(d.size, 1))))
    return out_a, out_d


def _fit_cell(cells, feats):
    y = has_seat(cells)
    return B4.fit_logit(cell_design(cells, feats), y)


def _fit_row(D, idx, y, feats):
    return B4.fit_logit(row_design(D, idx, feats), y)


def _cell_scores(D, cells, m_open, m_uns, m_roll):
    """The four cell-level scores of the four decision procedures."""
    s = {}
    s["OPEN"] = B4.predict_logit(m_open, cell_design(cells, CELL_FEATURES))
    s["OPEN+UNS"] = B4.predict_logit(m_uns,
                                     cell_design(cells, CELL_FEATURES_UNS))
    first = np.array([c["rows"][0] for c in cells])
    s["ROLL@open"] = B4.predict_logit(m_roll,
                                      row_design(D, first, ROW_FEATURES))
    allrows = np.concatenate([c["rows"] for c in cells])
    pr = B4.predict_logit(m_roll, row_design(D, allrows, ROW_FEATURES))
    out = np.empty(len(cells))
    k = 0
    for i, c in enumerate(cells):
        n = c["rows"].size
        out[i] = pr[k:k + n].max()
        k += n
    s["ROLL_MAX"] = out
    return s


def auc_rows(D, cells, rows, robust):
    y_row_all = D["roll_seat"]
    for aname in ("ALL",) + tuple(MC.ASSET_ORDER):
        sub = [c for c in cells if aname == "ALL" or c["asset"] == aname]
        if len(sub) < 200:
            continue
        scopes = []
        for yr in FIT_YEARS:
            tr = [c for c in sub if c["year"] in FIT_YEARS and c["year"] < yr]
            te = [c for c in sub if c["year"] == yr]
            if len(tr) >= 200 and len(te) >= 50:
                scopes.append(("WF_%d" % yr, tr, te))
        fit_all = [c for c in sub if c["year"] in FIT_YEARS]
        gate = [c for c in sub if era_of_cell(c) == ERAS[1]]
        if len(fit_all) >= 200 and len(gate) >= 50:
            scopes.append(("GATE_%dH1_FROZEN" % GATE_YEAR, fit_all, gate))
        pooled = {"y": [], "cl": [], "s": {}, "n_tr": 0, "yrow": [],
                  "srow": [], "clrow": []}
        for name, tr, te in scopes:
            tr_rows = np.concatenate([c["rows"] for c in tr])
            te_rows = np.concatenate([c["rows"] for c in te])
            m_open = _fit_cell(tr, CELL_FEATURES)
            m_uns = _fit_cell(tr, CELL_FEATURES_UNS)
            m_roll = _fit_row(D, tr_rows, y_row_all[tr_rows], ROW_FEATURES)
            if m_open is None or m_uns is None or m_roll is None:
                continue
            yte = has_seat(te)
            cl = np.array(["%s-%08d" % (c["asset"], c["d8"]) for c in te])
            sc = _cell_scores(D, te, m_open, m_uns, m_roll)
            aucs, deltas = _paired_boot(yte, sc, cl)
            base = float(yte.mean())
            for mname in ("OPEN", "OPEN+UNS", "ROLL@open", "ROLL_MAX"):
                a = B4.auc(yte, sc[mname])
                br = float(np.mean((sc[mname] - yte) ** 2))
                d = a - B4.auc(yte, sc["OPEN"])
                lo, hi = aucs[mname]
                dl, dh, dp = deltas[mname]
                rows.append([aname, name, "CELL", mname, len(tr), len(yte),
                             base, a, lo, hi, br,
                             float(np.mean((base - yte) ** 2)),
                             (None if mname == "OPEN" else d),
                             (None if mname == "OPEN" else dl),
                             (None if mname == "OPEN" else dh),
                             (None if mname == "OPEN" else dp),
                             _auc_verdict(mname, d, dl, dh)])
            # ---- the rolling model's own fully-causal reading (ROW grain) ---
            yr_te = y_row_all[te_rows]
            pr = B4.predict_logit(m_roll, row_design(D, te_rows, ROW_FEATURES))
            clr = D["session_key"][te_rows]
            a = B4.auc(yr_te, pr)
            lo, hi = B4._cluster_boot_auc(yr_te, pr, clr)
            rows.append([aname, name, "ROW", "ROLL", tr_rows.size,
                         te_rows.size, float(yr_te.mean()), a, lo, hi,
                         float(np.mean((pr - yr_te) ** 2)),
                         float(np.mean((yr_te.mean() - yr_te) ** 2)),
                         None, None, None, None, "-"])
            if name.startswith("WF_"):
                pooled["y"].append(yte)
                pooled["cl"].append(cl)
                pooled["n_tr"] += len(tr)
                for k, v in sc.items():
                    pooled["s"].setdefault(k, []).append(v)
                pooled["yrow"].append(yr_te)
                pooled["srow"].append(pr)
                pooled["clrow"].append(clr)
            if aname == "ALL" and name == "GATE_%dH1_FROZEN" % GATE_YEAR:
                _seat_gee(yte, sc, cl, "GATE_%dH1" % GATE_YEAR, robust)
        if not pooled["y"]:
            continue
        yte = np.concatenate(pooled["y"])
        cl = np.concatenate(pooled["cl"])
        sc = {k: np.concatenate(v) for k, v in pooled["s"].items()}
        aucs, deltas = _paired_boot(yte, sc, cl)
        base = float(yte.mean())
        for mname in ("OPEN", "OPEN+UNS", "ROLL@open", "ROLL_MAX"):
            a = B4.auc(yte, sc[mname])
            d = a - B4.auc(yte, sc["OPEN"])
            lo, hi = aucs[mname]
            dl, dh, dp = deltas[mname]
            rows.append([aname, "WF_POOLED", "CELL", mname, pooled["n_tr"],
                         len(yte), base, a, lo, hi,
                         float(np.mean((sc[mname] - yte) ** 2)),
                         float(np.mean((base - yte) ** 2)),
                         (None if mname == "OPEN" else d),
                         (None if mname == "OPEN" else dl),
                         (None if mname == "OPEN" else dh),
                         (None if mname == "OPEN" else dp),
                         _auc_verdict(mname, d, dl, dh)])
        yr = np.concatenate(pooled["yrow"])
        pr = np.concatenate(pooled["srow"])
        clr = np.concatenate(pooled["clrow"])
        lo, hi = B4._cluster_boot_auc(yr, pr, clr)
        rows.append([aname, "WF_POOLED", "ROW", "ROLL", pooled["n_tr"],
                     yr.size, float(yr.mean()), B4.auc(yr, pr), lo, hi,
                     float(np.mean((pr - yr) ** 2)),
                     float(np.mean((yr.mean() - yr) ** 2)),
                     None, None, None, None, "-"])
        if aname == "ALL":
            _seat_gee(yte, sc, cl, "FIT", robust)
    return rows


def _auc_verdict(mname, d, dl, dh):
    if mname == "OPEN":
        return "REFERENCE (the batch-4 cell-open model)"
    if not np.isfinite(d) or not np.isfinite(dl):
        return "NO_CI"
    if dl > 0:
        return "BEATS_CELL_OPEN (paired 95% CI excludes 0)"
    if dh < 0:
        return "WORSE_THAN_CELL_OPEN (paired 95% CI excludes 0)"
    return "NO_DIFFERENCE (paired 95% CI spans 0)"


def _seat_gee(y, scores, cl, era, robust):
    """One GEE per model score: does the fitted score carry the seat?"""
    gi = np.unique(cl, return_inverse=True)[1]
    for mname, s in sorted(scores.items()):
        g = EV.gee_independence(y, s, cl, link="logit")
        ic = EV.icc_oneway(y, gi)
        if g is None:
            continue
        z = (g["beta"] / g["se_cr1"]) if g["se_cr1"] > 0 else float("nan")
        robust.append(["SEAT_%s_score" % mname, era, "has_seat", "SESSION",
                       g["n"], g["n_clusters"], int(y.sum()), g["beta"],
                       g["se_naive"], g["se_cr0"], g["se_cr1"], z,
                       P1._p_two_sided(z),
                       ic["rho"] if ic else float("nan"),
                       ic["deff"] if ic else float("nan"),
                       ic["n_eff"] if ic else float("nan"),
                       _sig(P1._p_two_sided(z))])


def _sig(p):
    return ("SIGNIFICANT_p<0.05" if (np.isfinite(p) and p < 0.05)
            else "NOT_SIGNIFICANT")


MODEL_COLUMNS = ("model", "grain", "asset", "era", "term", "beta", "se_naive",
                 "se_cr0", "se_cr1", "z_cr1", "p_cr1", "odds_ratio_per_sd",
                 "n", "n_clusters", "n_seats", "seat_rate")


def model_rows(D, cells, rows, robust):
    """The two models' Holm-corrected coefficients (per SD, session-clustered)."""
    for aname in ("ALL",) + tuple(MC.ASSET_ORDER):
        for ename in ERAS:
            sub = [c for c in cells
                   if (aname == "ALL" or c["asset"] == aname)
                   and era_of_cell(c) == ename]
            if len(sub) < 60:
                continue
            # ---- CELL grain (batch-4 form + unspent_sess) ----
            y = has_seat(sub)
            if 0 < y.sum() < y.size:
                cl = np.array(["%s-%08d" % (c["asset"], c["d8"]) for c in sub])
                Xm = cell_design(sub, CELL_FEATURES_UNS)
                mu, sd = B4._standardise(Xm)
                Z = (B4._impute(Xm, mu) - mu) / sd
                g = B4.gee_multi(y, Z, cl, link="logit")
                if g is not None:
                    _emit_model(rows, "CELL_OPEN+UNS", "CELL", aname, ename,
                                ("intercept",) + CELL_FEATURES_UNS, g, y)
            # ---- ROW grain (the rolling state) ----
            idx = np.concatenate([c["rows"] for c in sub])
            yr = D["roll_seat"][idx]
            if not (0 < yr.sum() < yr.size):
                continue
            Xm = row_design(D, idx, ROW_FEATURES)
            mu, sd = B4._standardise(Xm)
            Z = (B4._impute(Xm, mu) - mu) / sd
            g = B4.gee_multi(yr, Z, D["session_key"][idx], link="logit")
            if g is None:
                continue
            _emit_model(rows, "ROLLING", "ROW", aname, ename,
                        ("intercept",) + ROW_FEATURES, g, yr)
    return rows


def _emit_model(rows, model, grain, aname, ename, terms, g, y):
    for j, tn in enumerate(terms):
        z = (g["beta"][j] / g["se_cr1"][j] if g["se_cr1"][j] > 0
             else float("nan"))
        rows.append([model, grain, aname, ename, tn, float(g["beta"][j]),
                     float(g["se_naive"][j]), float(g["se_cr0"][j]),
                     float(g["se_cr1"][j]), z, P1._p_two_sided(z),
                     float(np.exp(g["beta"][j])), g["n"], g["n_clusters"],
                     int(y.sum()), float(y.mean())])


BAND_COLUMNS = ("grain", "asset", "era", "band", "lo", "hi", "n", "n_share",
                "n_winners", "winner_share", "winner_rate", "conc_ratio",
                "mean_close_usd", "mean_peak_usd", "cond_close_usd",
                "seat_rate_ahead")


def roll_band_rows(D, cells, rows):
    """The day-7 claim at era scale: row-grain rv1800 bands vs winner content.

    CC-M2-19.1 / the P030 [E1D7] note measured rv1800 AT THE CANDIDATE'S OWN
    ROW over seven sessions: >= 250 held 449 of 484 winners (92.8%).  This is
    that table over 3,341 sessions, with the CELL-OPEN reading beside it so the
    stale-anchor claim is a comparison and not an assertion."""
    for grain, vals, win, era, ast in (
            ("ROW", D["rv1800"], D["winner"].astype(float), D["era"],
             D["asset"]),
            ("CELL_OPEN",
             np.array([c["rv1800_open"] for c in cells]),
             np.array([1.0 if c["n_win"] >= 1 else 0.0 for c in cells]),
             np.array([era_of_cell(c) for c in cells]),
             np.array([c["asset"] for c in cells]))):
        for aname in ("ALL",) + tuple(MC.ASSET_ORDER):
            for ename in ERAS:
                m = (era == ename) & ((ast == aname) if aname != "ALL"
                                      else np.ones(era.size, bool))
                if m.sum() < 50:
                    continue
                v = vals[m]
                w = win[m]
                cc = (D["cert_close"][m] if grain == "ROW"
                      else np.array([c["mean_close"] for c in cells])[m])
                cp = (D["cert_peak"][m] if grain == "ROW"
                      else np.array([c["mean_peak"] for c in cells])[m])
                seat = (D["roll_seat"][m] if grain == "ROW" else w)
                n_tot, w_tot = int(m.sum()), float(w.sum())
                for k in range(len(ROLL_RV_BANDS) - 1):
                    lo, hi = ROLL_RV_BANDS[k], ROLL_RV_BANDS[k + 1]
                    b = np.isfinite(v) & (v >= lo) & (v < hi)
                    n = int(b.sum())
                    if n == 0:
                        continue
                    ws = (float(w[b].sum()) / w_tot) if w_tot else None
                    ns = n / n_tot
                    pos = cc[b][cc[b] > 0]
                    rows.append([grain, aname, ename, ROLL_RV_BAND_NAMES[k],
                                 lo, (hi if hi < 1e17 else float("inf")), n,
                                 ns, int(w[b].sum()), ws,
                                 float(w[b].mean()),
                                 (ws / ns) if (ws is not None and ns > 0)
                                 else None,
                                 float(np.nanmean(cc[b])),
                                 float(np.nanmean(cp[b])),
                                 float(pos.mean()) if pos.size else None,
                                 float(seat[b].mean())])
    return rows


# ============================================== item 2: S10 side geometry
SIDE_COLUMNS = ("object", "grain", "threshold", "asset", "era", "n", "n_called",
                "call_rate", "n_scoreable", "n_agree", "agreement",
                "mirror_agreement", "beats_mirror", "winner_rate_agree",
                "winner_rate_disagree", "conc_ratio", "mean_close_agree",
                "mean_close_disagree", "est_value_usd", "mirror_value_usd",
                "delta_value_usd", "n_sessions", "sign_test_p", "verdict")

MIRROR_COLUMNS = ("object", "grain", "threshold", "asset", "era", "n_sessions",
                  "sessions_won", "sessions_tied", "sessions_lost",
                  "mirror_law_holds", "mean_delta_usd", "se_session", "z", "p",
                  "holm_rank", "holm_threshold", "holm_verdict")


def s10_call_rows(d_poc, in_va, thr):
    """The declared S2c form: outside the developing VA by >= thr dollars.

    in_va == -1 is REFUSED (a missing VA edge), and a refusal is NOT 'outside
    the area' — sections.s10_profile made that ruling in V1.1 and it is obeyed
    here: a refused row never calls."""
    call = np.zeros(d_poc.size, dtype=np.int64)
    fire = (in_va == 0) & np.isfinite(d_poc) & (np.abs(d_poc) >= thr)
    call[fire & (d_poc > 0)] = -1          # above value -> SHORT
    call[fire & (d_poc < 0)] = +1          # below value -> LONG
    return call


def _row_side_tables(D, call, obj, grain, thr, rows, mrows, robust, destr,
                     do_gee=True):
    """Score a ROW-grain signed call: agreement, concentration, mirror, GEE."""
    for aname in ("ALL",) + tuple(MC.ASSET_ORDER):
        for ename in ERAS:
            m = (D["era"] == ename) & ((D["asset"] == aname) if aname != "ALL"
                                       else np.ones(D["era"].size, bool))
            if m.sum() < 100:
                continue
            k = call[m]
            sd = D["side"][m]
            cc = D["cert_close"][m]
            win = D["winner"][m]
            sess = D["session_key"][m]
            fired = k != 0
            if fired.sum() < 30:
                continue
            agree_m = fired & (k == sd)
            dis_m = fired & (k == -sd)
            n_ag = int(agree_m.sum())
            n_sc = int(agree_m.sum() + dis_m.sum())
            ag = (n_ag / n_sc) if n_sc else None
            wr_a = float(win[agree_m].mean()) if agree_m.any() else None
            wr_d = float(win[dis_m].mean()) if dis_m.any() else None
            ev = float(cc[agree_m].sum())
            mv = float(cc[dis_m].sum())
            # per-SESSION value delta (estimator minus its mirror), vectorised:
            # the sessions a directional claim wins and loses are what the
            # mirror law is written on, and at row grain there are ~10^6 rows.
            _u, gid = np.unique(sess[fired], return_inverse=True)
            signed = np.where(agree_m[fired], cc[fired],
                              np.where(dis_m[fired], -cc[fired], 0.0))
            dd = np.bincount(gid, weights=signed, minlength=_u.size)
            won = int((dd > 0).sum())
            lost = int((dd < 0).sum())
            tie = int((dd == 0).sum())
            rows.append([obj, grain, thr, aname, ename, int(m.sum()),
                         int(fired.sum()),
                         float(fired.mean()), n_sc, n_ag, ag,
                         (1.0 - ag) if ag is not None else None,
                         int(ag > 0.5) if ag is not None else None,
                         wr_a, wr_d,
                         (wr_a / wr_d) if (wr_a is not None and wr_d)
                         else None,
                         float(cc[agree_m].mean()) if agree_m.any() else None,
                         float(cc[dis_m].mean()) if dis_m.any() else None,
                         ev, mv, ev - mv, int(_u.size),
                         B4._sign_test(won, lost),
                         _side_verdict(ag, lost, won)])
            _mirror_row(mrows, obj, grain, thr, aname, ename, dd, won, tie,
                        lost)
            if not (do_gee and aname == "ALL" and n_sc >= 100):
                continue
            y = (win[fired]).astype(np.float64)
            xs = (k[fired] == sd[fired]).astype(np.float64)
            g = EV.gee_independence(y, xs, sess[fired], link="logit")
            ic = EV.icc_oneway(y, np.unique(sess[fired],
                                            return_inverse=True)[1])
            if g is not None:
                z = (g["beta"] / g["se_cr1"]) if g["se_cr1"] > 0 else \
                    float("nan")
                robust.append(["%s_%s_thr%.0f" % (obj, grain, thr), ename,
                               "winner|call_agrees_with_side", "SESSION",
                               g["n"], g["n_clusters"], int(fired.sum()),
                               g["beta"], g["se_naive"], g["se_cr0"],
                               g["se_cr1"], z, P1._p_two_sided(z),
                               ic["rho"] if ic else float("nan"),
                               ic["deff"] if ic else float("nan"),
                               ic["n_eff"] if ic else float("nan"),
                               _sig(P1._p_two_sided(z))])
            if destr is not None and ename == "FIT":
                real = (float(np.mean(cc[agree_m])) - float(np.mean(cc[dis_m]))
                        if (agree_m.any() and dis_m.any()) else float("nan"))
                rs = np.random.RandomState(DESTRUCTION_SEED + 3)
                kk = k[fired]
                ss = sess[fired]
                sdf = sd[fired]
                ccf = cc[fired]
                null = []
                for _ in range(DESTRUCTION_REPS):
                    k2 = B4._shuffle_within(kk.astype(np.float64), ss, rs)
                    a2 = k2 == sdf
                    d2 = k2 == -sdf
                    if a2.any() and d2.any():
                        null.append(float(ccf[a2].mean() - ccf[d2].mean()))
                destr.append(B4._destr_row(
                    "%s_%s_thr%.0f" % (obj, grain, thr), ename,
                    "the signed call (within session)", real, null))
    return rows


def _side_verdict(ag, lost, won):
    if ag is None:
        return "NO_CALL"
    if lost == 0 and won > 0 and ag > 0.5:
        return "DIRECTION_CANDIDATE (beats its mirror on every session)"
    if ag > 0.5:
        return ("FAILS_MIRROR_LAW (agreement > 0.5 but it loses %d session(s) "
                "— CC-M2-13.1)" % lost)
    return "DEAD_AS_A_RULE (does not beat its own mirror)"


def _mirror_row(mrows, obj, grain, thr, aname, ename, dd, won, tie, lost):
    mu = float(dd.mean()) if dd.size else float("nan")
    se = (float(dd.std(ddof=1) / math.sqrt(dd.size)) if dd.size > 1
          else float("nan"))
    z = mu / se if (np.isfinite(se) and se > 0) else float("nan")
    mrows.append([obj, grain, thr, aname, ename, int(dd.size), won, tie, lost,
                  int(lost == 0 and won > 0), mu, se, z, P1._p_two_sided(z)])


def _cell_side_tables(cells, call, obj, thr, rows, mrows, robust):
    """The CELL-grain form: the call read at the cell open vs the cell's own
    winner-majority side, batch-4's P031 machinery at a different field."""
    for aname in ("ALL",) + tuple(MC.ASSET_ORDER):
        for ename in ERAS:
            sel = [i for i, c in enumerate(cells)
                   if (aname == "ALL" or c["asset"] == aname)
                   and era_of_cell(c) == ename]
            if len(sel) < 50:
                continue
            called = [(cells[i], int(call[i])) for i in sel if call[i] != 0]
            if len(called) < 20:
                continue
            scor = [(c, k) for c, k in called if B4.winner_side(c) != 0]
            n_ag = sum(1 for c, k in scor if k == B4.winner_side(c))
            n_sc = len(scor)
            ag = (n_ag / n_sc) if n_sc else None
            ev = sum(B4._cell_side_value(c, k) for c, k in called)
            mv = sum(B4._cell_side_value(c, -k) for c, k in called)
            by = {}
            for c, k in called:
                by.setdefault((c["asset"], c["d8"]), []).append((c, k))
            dd = np.array([sum(B4._cell_side_value(c, k) for c, k in g)
                           - sum(B4._cell_side_value(c, -k) for c, k in g)
                           for g in by.values()])
            won = int((dd > 0).sum())
            lost = int((dd < 0).sum())
            tie = int((dd == 0).sum())
            wr_a = (float(np.mean([1.0 if k == B4.winner_side(c) else 0.0
                                   for c, k in scor])) if scor else None)
            rows.append([obj, "CELL", thr, aname, ename, len(sel),
                         len(called), len(called) / len(sel), n_sc, n_ag, ag,
                         (1.0 - ag) if ag is not None else None,
                         int(ag > 0.5) if ag is not None else None,
                         wr_a, (1.0 - wr_a) if wr_a is not None else None,
                         None, None, None, ev, mv, ev - mv, len(by),
                         B4._sign_test(won, lost), _side_verdict(ag, lost, won)])
            _mirror_row(mrows, obj, "CELL", thr, aname, ename, dd, won, tie,
                        lost)
            if aname == "ALL" and n_sc >= 30:
                y = np.array([1.0 if B4.winner_side(c) > 0 else 0.0
                              for c, _k in scor])
                xs = np.array([float(k) for _c, k in scor])
                cl = np.array(["%s-%08d" % (c["asset"], c["d8"])
                               for c, _k in scor])
                g = EV.gee_independence(y, xs, cl, link="logit")
                ic = EV.icc_oneway(y, np.unique(cl, return_inverse=True)[1])
                if g is not None:
                    z = (g["beta"] / g["se_cr1"]) if g["se_cr1"] > 0 else \
                        float("nan")
                    robust.append(["%s_CELL_thr%.0f" % (obj, thr), ename,
                                   "winner_majority_side", "SESSION", g["n"],
                                   g["n_clusters"], len(called), g["beta"],
                                   g["se_naive"], g["se_cr0"], g["se_cr1"], z,
                                   P1._p_two_sided(z),
                                   ic["rho"] if ic else float("nan"),
                                   ic["deff"] if ic else float("nan"),
                                   ic["n_eff"] if ic else float("nan"),
                                   _sig(P1._p_two_sided(z))])
    return rows


def s10_rows(D, cells, rows, mrows, robust, destr):
    for thr in S10_THR_GRID:
        _row_side_tables(D, s10_call_rows(D["d_poc"], D["in_va"], thr),
                         "S10_SIDE", "ROW", thr, rows, mrows, robust,
                         destr if thr == S10_THR else None)
        cc = s10_call_rows(np.array([c["d_poc_open"] for c in cells]),
                           np.array([c["in_va_open"] for c in cells]), thr)
        _cell_side_tables(cells, cc, "S10_SIDE", thr, rows, mrows, robust)
    return rows


def grade_s10(rows, mrows):
    r = [x for x in rows if x[0] == "S10_SIDE" and x[1] == "ROW"
         and x[2] == S10_THR and x[3] == "ALL" and x[4] == "FIT"]
    c = [x for x in rows if x[0] == "S10_SIDE" and x[1] == "CELL"
         and x[2] == S10_THR and x[3] == "ALL" and x[4] == "FIT"]
    if not r or not c:
        return "NULL", "no S10 rows at the declared threshold"
    ml = [m for m in mrows if m[1] == "ROW" and m[2] == S10_THR
          and m[3] == "ALL" and m[4] == "FIT"]
    holds = bool(ml and ml[0][9])
    ar, ac = r[0][10], c[0][10]
    if holds and ar is not None and ar > 0.5:
        return ("DIRECTION_CANDIDATE",
                "row agreement %.3f, cell agreement %s, and the mirror law "
                "holds at $%.0f" % (ar, B4._fmt(ac, 3), S10_THR))
    return ("DEAD_AS_A_RULE",
            "row agreement %s (mirror %s) / cell agreement %s at $%.0f; "
            "mirror law holds = %s — a directional claim that does not beat "
            "its own mirror on every session does not exist (CC-M2-13.1)"
            % (B4._fmt(ar, 3), B4._fmt(1 - ar if ar is not None else None, 3),
               B4._fmt(ac, 3), S10_THR, holds))


# ================================================ item 3: P032 both grains
P032_COLUMNS = ("field", "grain", "reading", "asset", "era", "n", "n_clusters",
                "beta_per_sd", "se_cr1", "z_cr1", "p_cr1", "sign", "icc_rho",
                "deff", "n_eff", "clause_n_fire", "clause_precision",
                "clause_base_rate", "clause_recall", "verdict")

P032_FIELDS = (("prev_range", "prev_phase_range_usd (the day-7 S1b field)"),
               ("prev_ret_mag", "|prev_phase_ret_usd| (batch-4 prev_ret_mag)"),
               ("prev_ret_signed", "prev_phase_ret_usd, signed"))


def _p032_vec(field, D=None, cells=None, idx=None):
    if cells is not None:
        base = {"prev_range": np.array([c["prev_range_usd"] for c in cells]),
                "prev_ret_mag": np.abs(np.array([c["prev_ret_usd"]
                                                 for c in cells])),
                "prev_ret_signed": np.array([c["prev_ret_usd"]
                                             for c in cells])}
        return base[field]
    base = {"prev_range": D["prev_range"][idx],
            "prev_ret_mag": np.abs(D["prev_ret"][idx]),
            "prev_ret_signed": D["prev_ret"][idx]}
    return base[field]


def p032_rows(D, cells, rows, robust, destr):
    """MARGINAL vs PARTIAL, at BOTH grains — the sign contradiction, settled.

    CC-M2-18.1 read prior-cell MAGNITUDE inside a model that already carried
    rv1800; the day-7 ledger read prior-cell RANGE on its own.  Those are two
    different estimands and they may legitimately carry opposite signs, so both
    are computed here for all three spellings of the field."""
    for grain in ("CELL", "ROW"):
        for aname in ("ALL",) + tuple(MC.ASSET_ORDER):
            for ename in ERAS:
                if grain == "CELL":
                    sel = [c for c in cells
                           if (aname == "ALL" or c["asset"] == aname)
                           and era_of_cell(c) == ename]
                    if len(sel) < 100:
                        continue
                    y = has_seat(sel)
                    rv = np.array([c["rv1800_open"] for c in sel])
                    cl = np.array(["%s-%08d" % (c["asset"], c["d8"])
                                   for c in sel])
                    getv = lambda fd: _p032_vec(fd, cells=sel)   # noqa: E731
                else:
                    m = ((D["era"] == ename)
                         & ((D["asset"] == aname) if aname != "ALL"
                            else np.ones(D["era"].size, bool)))
                    idx = np.nonzero(m)[0]
                    if idx.size < 200:
                        continue
                    y = D["winner"][idx].astype(np.float64)
                    rv = D["rv1800"][idx]
                    cl = D["session_key"][idx]
                    getv = lambda fd: _p032_vec(fd, D=D, idx=idx)  # noqa: E731
                gi = np.unique(cl, return_inverse=True)[1]
                for field, _desc in P032_FIELDS:
                    v = getv(field)
                    ok = np.isfinite(v) & np.isfinite(rv)
                    if ok.sum() < 100 or len(set(y[ok].tolist())) < 2:
                        continue
                    yv, vv, rvv, clv = y[ok], v[ok], rv[ok], cl[ok]
                    for reading in ("MARGINAL", "PARTIAL_GIVEN_RV1800"):
                        if reading == "MARGINAL":
                            Xm = ((vv - vv.mean())
                                  / max(vv.std(), 1e-9))[:, None]
                        else:
                            Xm = np.column_stack([
                                (vv - vv.mean()) / max(vv.std(), 1e-9),
                                (rvv - rvv.mean()) / max(rvv.std(), 1e-9)])
                        g = B4.gee_multi(yv, Xm, clv, link="logit")
                        if g is None:
                            continue
                        b = float(g["beta"][1])
                        se = float(g["se_cr1"][1])
                        z = b / se if se > 0 else float("nan")
                        p = P1._p_two_sided(z)
                        ic = EV.icc_oneway(yv, gi[ok])
                        cn = cp = cb = cr = None
                        if field == "prev_range":
                            fire = vv >= P032_CLAUSE_USD
                            cn = int(fire.sum())
                            cp = (float(yv[fire].mean()) if fire.any()
                                  else None)
                            cb = float(yv.mean())
                            cr = ((float(yv[fire].sum()) / float(yv.sum()))
                                  if yv.sum() else None)
                        rows.append([field, grain, reading, aname, ename,
                                     g["n"], g["n_clusters"], b, se, z, p,
                                     ("+" if b > 0 else "-"),
                                     ic["rho"] if ic else float("nan"),
                                     ic["deff"] if ic else float("nan"),
                                     ic["n_eff"] if ic else float("nan"),
                                     cn, cp, cb, cr,
                                     _p032_verdict(b, p, reading)])
                        if aname == "ALL":
                            robust.append(["P032_%s_%s_%s" % (field, grain,
                                                              reading), ename,
                                           ("has_seat" if grain == "CELL"
                                            else "winner"), "SESSION", g["n"],
                                           g["n_clusters"], int(yv.sum()), b,
                                           float(g["se_naive"][1]),
                                           float(g["se_cr0"][1]), se, z, p,
                                           ic["rho"] if ic else float("nan"),
                                           ic["deff"] if ic else float("nan"),
                                           ic["n_eff"] if ic else float("nan"),
                                           _sig(p)])
    # destruction on the day-7 clause itself, at cell grain
    sub = [c for c in cells if era_of_cell(c) == "FIT"]
    v = np.array([c["prev_range_usd"] for c in sub])
    y = has_seat(sub)
    sess = np.array(["%s-%08d" % (c["asset"], c["d8"]) for c in sub])
    ok = np.isfinite(v)
    fire = v >= P032_CLAUSE_USD
    real = (float(y[ok & fire].mean() - y[ok & ~fire].mean())
            if (ok & fire).any() and (ok & ~fire).any() else float("nan"))
    rs = np.random.RandomState(DESTRUCTION_SEED + 2)
    null = []
    vv = np.where(ok, v, 0.0)
    for _ in range(DESTRUCTION_REPS):
        f2 = B4._shuffle_within(vv, sess, rs) >= P032_CLAUSE_USD
        if f2.any() and (~f2).any():
            null.append(float(y[f2].mean() - y[~f2].mean()))
    destr.append(B4._destr_row("P032_prior_cell_range>=1000", "FIT",
                               "prev_phase_range_usd (within session)", real,
                               null))
    return rows


def _p032_verdict(b, p, reading):
    if not np.isfinite(p):
        return "NO_TEST"
    d = "positive" if b > 0 else "negative"
    if p >= 0.05:
        return "NULL (%s, not significant before Holm)" % d
    return "%s beta, %s (pre-Holm p=%.2g)" % (d.upper(), reading, p)


# ============================================== item 4: P033 runway x rv
P033_COLUMNS = ("form", "control_band", "asset", "era", "decile", "lo", "hi",
                "n", "n_share", "n_winners", "winner_share", "winner_rate",
                "base_winner_rate", "winner_rate_lift", "conc_ratio",
                "mean_close_usd", "cond_close_usd", "mean_peak_usd",
                "frac_ge_1000_close", "n_sessions")


def _p033_forms(D):
    rw = np.maximum(D["runway_binding"].astype(np.float64), 0.0)
    rv = D["rv1800"]
    return (("PRODUCT_runway_x_rv1800", rw * rv),
            ("SIGMA_TO_EXIT_rv1800_sqrt", rv * np.sqrt(np.maximum(rw, 1.0)
                                                       / 1800.0)))


def p033_rows(D, rows, robust, destr):
    """Winner rate and both certificate readings by (runway x rv1800) decile.

    The cuts are computed ON THE FIT POOL ONLY and APPLIED to the GATE echo —
    a decile boundary is a fitted number like any other.  The raw runway band
    is carried as the control (P025's own axis): if the product is only the
    runway wearing a new hat, the within-band deciles will be flat."""
    fitm = D["era"] == ERAS[0]
    for form, v in _p033_forms(D):
        okf = fitm & np.isfinite(v)
        if okf.sum() < 1000:
            continue
        edges = np.unique(np.percentile(v[okf],
                                        np.linspace(0, 100, P033_DECILES + 1)))
        for ctrl, cmask in ([("ALL", np.ones(v.size, bool))]
                            + [(P025_BAND_NAMES[k],
                                (D["runway_binding"] >= lo)
                                & (D["runway_binding"] < hi))
                               for k, (lo, hi) in enumerate(P025_BANDS)]):
            for aname in ("ALL",) + tuple(MC.ASSET_ORDER):
                for ename in ERAS:
                    m = (cmask & (D["era"] == ename) & np.isfinite(v)
                         & ((D["asset"] == aname) if aname != "ALL"
                            else np.ones(v.size, bool)))
                    if m.sum() < 200:
                        continue
                    win = D["winner"][m].astype(float)
                    cc = D["cert_close"][m]
                    cp = D["cert_peak"][m]
                    vv = v[m]
                    base = float(win.mean())
                    w_tot = float(win.sum())
                    for k in range(edges.size - 1):
                        lo = edges[k]
                        hi = edges[k + 1] if k < edges.size - 2 else np.inf
                        b = (vv >= lo) & (vv < hi)
                        n = int(b.sum())
                        if n < 20:
                            continue
                        ws = (float(win[b].sum()) / w_tot) if w_tot else None
                        ns = n / float(m.sum())
                        pos = cc[b][cc[b] > 0]
                        rows.append([form, ctrl, aname, ename, k, float(lo),
                                     float(hi), n, ns, int(win[b].sum()), ws,
                                     float(win[b].mean()), base,
                                     (float(win[b].mean()) / base)
                                     if base > 0 else None,
                                     (ws / ns) if (ws is not None and ns > 0)
                                     else None,
                                     float(np.nanmean(cc[b])),
                                     float(pos.mean()) if pos.size else None,
                                     float(np.nanmean(cp[b])),
                                     float((cc[b] >= 1000.0).mean()),
                                     len(set(D["session_key"][m][b].tolist()))])
        # ---- GEE + destruction on the continuous form -----------------------
        for ename in ERAS:
            m = (D["era"] == ename) & np.isfinite(v)
            if m.sum() < 500:
                continue
            z0 = (v[m] - v[m].mean()) / max(v[m].std(), 1e-9)
            cl = D["session_key"][m]
            gi = np.unique(cl, return_inverse=True)[1]
            for metric, y, link in (("winner",
                                     D["winner"][m].astype(float), "logit"),
                                    ("cert_close",
                                     D["cert_close"][m], "identity"),
                                    ("cert_peak",
                                     D["cert_peak"][m], "identity")):
                g = EV.gee_independence(y, z0, cl, link=link)
                ic = EV.icc_oneway(y, gi)
                if g is None:
                    continue
                z = (g["beta"] / g["se_cr1"]) if g["se_cr1"] > 0 else \
                    float("nan")
                robust.append(["P033_%s" % form, ename, metric, "SESSION",
                               g["n"], g["n_clusters"], int(m.sum()),
                               g["beta"], g["se_naive"], g["se_cr0"],
                               g["se_cr1"], z, P1._p_two_sided(z),
                               ic["rho"] if ic else float("nan"),
                               ic["deff"] if ic else float("nan"),
                               ic["n_eff"] if ic else float("nan"),
                               _sig(P1._p_two_sided(z))])
            if ename != ERAS[0]:
                continue
            thr = float(np.percentile(v[m], 90))
            win = D["winner"][m].astype(float)
            fire = v[m] >= thr
            real = (float(win[fire].mean() - win[~fire].mean())
                    if fire.any() and (~fire).any() else float("nan"))
            rs = np.random.RandomState(DESTRUCTION_SEED + 4)
            null = []
            for _ in range(DESTRUCTION_REPS):
                f2 = B4._shuffle_within(v[m], cl, rs) >= thr
                if f2.any() and (~f2).any():
                    null.append(float(win[f2].mean() - win[~f2].mean()))
            destr.append(B4._destr_row("P033_%s_top_decile" % form, ename,
                                       "the product (within session)", real,
                                       null))
    return rows


def grade_p033(rows, robust):
    """P033 is a magnitude object: CONCENTRATOR is its ceiling (no mirror)."""
    top = [r for r in rows if r[0] == "PRODUCT_runway_x_rv1800"
           and r[1] == "ALL" and r[2] == "ALL" and r[3] == "FIT"]
    if not top:
        return "NULL", "no decile table"
    lift = max((r[13] for r in top if r[13] is not None), default=None)
    # the within-band control is only readable where the band's decile has
    # enough rows to mean anything: a 30-row decile inside a narrow runway band
    # can post any lift at all, and quoting it would be the artefact P020's
    # conc_ratio was invented to kill.
    ctrl = [r for r in rows if r[0] == "PRODUCT_runway_x_rv1800"
            and r[1] != "ALL" and r[2] == "ALL" and r[3] == "FIT"
            and r[13] is not None and r[7] >= 500]
    within = max(ctrl, key=lambda r: r[13]) if ctrl else None
    if lift is None:
        return "NULL", "no winner-rate lift"
    if lift >= CONCENTRATOR_MIN:
        return ("CONCENTRATOR",
                "top-decile winner-rate lift %.2fx pooled; best WITHIN-runway-"
                "band decile lift %s (band %s, decile %s, n>=500) — the "
                "product is not the runway wearing a new hat. FEATURE "
                "CANDIDATE ONLY: a feasibility object with no mirror can never "
                "be an entry rule"
                % (lift, B4._fmt(within[13], 2) if within else ".",
                   within[1] if within else "-",
                   within[4] if within else "-"))
    return "NULL", "winner-rate lift %.2fx < %.2f" % (lift, CONCENTRATOR_MIN)


# ======================================== item 5: the V2/V3 pooled re-grade
VETO_COLUMNS = ("family", "scope", "metric", "value")
VSESS_COLUMNS = ("family", "asset", "d8", "n_core_takes", "n_vetoed",
                 "n_winners_vetoed", "mean_close_vetoed", "mean_close_stood",
                 "replay_pre_usd", "replay_post_usd", "replay_delta_usd",
                 "n_seat_spenders_vetoed_DP", "n_seat_spenders_vetoed_REPLAY")


def _row_dict(D, t):
    """One triage-index-shaped row dict, so e1d7_policy's own predicates run."""
    return {
        "cid": str(D["cid"][t]), "asset": str(D["asset"][t]),
        "side": "LONG" if D["side"][t] > 0 else "SHORT",
        "phase_dec": PHASES[int(D["phase"][t])],
        "f60_n": D["f60_n"][t], "f60_vol": D["f60_vol"][t],
        "f60_sflow": D["f60_sflow"][t], "f5m_vol": D["f5m_vol"][t],
        "f5m_sflow": D["f5m_sflow"][t], "fph_vol": D["fph_vol"][t],
        "runway_phase": D["runway_phase"][t],
        "extreme_age_trade_side": D["extreme_age"][t],
        "slope1m": D["slope_1m"][t],
        "trapped_above": D["fuel_above"][t], "trapped_below": D["fuel_below"][t],
        "phase_total": D["fuel_total"][t], "thru_n": D["thru_n"][t],
        "thru_bid": D["thru_bid"][t], "thru_ask": D["thru_ask"][t],
        "rv1800": D["rv1800"][t],
    }


def veto_regrade(D, rows, srows):
    """V2/V3 over ALL SEVEN study sessions, with the seat-spender split.

    The pre-veto pool is the frozen five-term CORE on every candidate of the
    seven sessions — one uniform pool, so the pooled statistic is not a mix of
    arms.  ERA_NOTES §67: the sole-block statistic and the replay delta can
    disagree completely, so BOTH are reported and the replay delta is the one
    that decides."""
    m = np.isin(D["d8"], np.array(STUDY_D8, dtype=np.int32))
    idx = np.nonzero(m)[0]
    if idx.size == 0:
        return rows, srows
    recs, fires = [], {"V2": set(), "V3": set(), "V2_OR_V3": set(),
                       "V2_SOLE": set(), "V3_SOLE": set()}
    n_core = 0
    for t in idx.tolist():
        r = _row_dict(D, t)
        core_ok = all(P7.terms(r).values())
        cid = r["cid"]
        recs.append({"cid": cid, "call": (PS.CALL_TAKE if core_ok
                                          else PS.CALL_SKIP),
                     "outcome": PS.outcome(cid), "has_interaction": 0})
        if not core_ok:
            continue
        n_core += 1
        v2, v3 = P7.v2(r), P7.v3(r)
        if v2:
            fires["V2"].add(cid)
        if v3:
            fires["V3"].add(cid)
        if v2 or v3:
            fires["V2_OR_V3"].add(cid)
        if v2 and not v3:
            fires["V2_SOLE"].add(cid)
        if v3 and not v2:
            fires["V3_SOLE"].add(cid)
    takes = [r for r in recs if r["call"] == PS.CALL_TAKE]
    _pre_rows, pre_tot = PS.replay(recs)
    pre_by = {(x["asset"], x["date8"]): x["realised_usd"]
              for x in _pre_rows}
    for fam in ("V2", "V3", "V2_OR_V3", "V2_SOLE", "V3_SOLE"):
        vetoed = fires[fam]
        post = [{"cid": r["cid"],
                 "call": (PS.CALL_SKIP if (r["call"] == PS.CALL_TAKE
                                           and r["cid"] in vetoed)
                          else r["call"]),
                 "outcome": r["outcome"], "has_interaction": 0} for r in recs]
        post_rows, post_tot = PS.replay(post)
        post_by = {(x["asset"], x["date8"]): x["realised_usd"]
                   for x in post_rows}
        vrows, summ = PS.veto_census(recs, vetoed)
        vt = [r["outcome"] for r in takes if r["outcome"]["cid"] in vetoed]
        st = [r["outcome"] for r in takes if r["outcome"]["cid"] not in vetoed]
        deltas = []
        ds = PS.dp_seat_cids(takes)          # the PRE-VETO counterfactual seats
        rs = PS.replay_seat_cids(takes)
        for key in sorted(set(pre_by) | set(post_by)):
            a, d8 = key
            pre = pre_by.get(key, 0.0)
            pst = post_by.get(key, 0.0)
            deltas.append(pst - pre)
            vs = [o for o in vt if (o["asset"], o["date8"]) == key]
            ss = [o for o in st if (o["asset"], o["date8"]) == key]
            srows.append([fam, a, d8, len([o for o in vt + st
                                           if (o["asset"], o["date8"]) == key]),
                          len(vs), int(sum(o["winner_close"] for o in vs)),
                          (float(np.mean([o["cert_close_usd"] for o in vs]))
                           if vs else None),
                          (float(np.mean([o["cert_close_usd"] for o in ss]))
                           if ss else None),
                          pre, pst, pst - pre,
                          len([o for o in vs if o["cid"] in ds]),
                          len([o for o in vs if o["cid"] in rs])])
        dd = np.array(deltas)
        won = int((dd > 0).sum())
        lost = int((dd < 0).sum())
        out = {
            "n_study_sessions": len({(o["outcome"]["asset"],
                                      o["outcome"]["date8"]) for o in takes}),
            "n_candidates": int(idx.size), "n_core_takes": len(takes),
            "n_vetoed": len([o for o in vt]),
            "veto_rate": (len(vt) / len(takes)) if takes else None,
            "mean_close_vetoed": (float(np.mean([o["cert_close_usd"]
                                                 for o in vt])) if vt
                                  else None),
            "mean_close_stood": (float(np.mean([o["cert_close_usd"]
                                                for o in st])) if st
                                 else None),
            "mean_peak_vetoed": (float(np.mean([o["cert_peak_usd"]
                                                for o in vt])) if vt
                                 else None),
            "mean_peak_stood": (float(np.mean([o["cert_peak_usd"]
                                               for o in st])) if st else None),
            "n_winners_vetoed": int(sum(o["winner_close"] for o in vt)),
            "n_winners_stood": int(sum(o["winner_close"] for o in st)),
            "replay_pre_usd": pre_tot["realised_usd"],
            "replay_post_usd": post_tot["realised_usd"],
            "replay_delta_usd": (post_tot["realised_usd"]
                                 - pre_tot["realised_usd"]),
            "capture_pre": pre_tot["capture"], "capture_post": post_tot["capture"],
            "sessions_improved": won, "sessions_hurt": lost,
            "sessions_unchanged": int((dd == 0).sum()),
            "sign_test_p": B4._sign_test(won, lost),
            "DP_vetoed_seat_spenders": summ.get("DP_vetoed_seat_spenders", 0),
            "REPLAY_vetoed_seat_spenders":
                summ.get("REPLAY_vetoed_seat_spenders", 0),
            "DP_vetoed_seat_value_usd":
                summ.get("DP_vetoed_seat_value_usd", 0.0),
            "replay_inert": summ.get("replay_inert", 0),
        }
        out["verdict"] = _veto_verdict(out)
        for k in sorted(out):
            rows.append([fam, "POOLED_7_SESSIONS", k, out[k]])
        for vr in vrows:
            rows.append([fam, "SEAT_SPENDER_SPLIT",
                         "%s|%s|%s|%s" % (vr[1], vr[2], vr[3], vr[0]),
                         "n=%d n_sessions=%d mean_close=%s mean_peak=%s "
                         "sum_close=%s winners=%d winner_rate=%s "
                         "would_seat=%d"
                         % (vr[4], vr[5], B4._fmt(vr[6], 2), B4._fmt(vr[7], 2),
                            B4._fmt(vr[8], 2), vr[9], B4._fmt(vr[10], 3),
                            vr[12])])
    return rows, srows


def _veto_verdict(o):
    if o["replay_inert"]:
        return ("REPLAY-INERT — the family touches no seat-spender in either "
                "reading, so it cannot move the money whatever its pooled row "
                "statistic says (ERA_NOTES §67)")
    d = o["replay_delta_usd"]
    if d > 0 and o["sessions_hurt"] == 0:
        return ("RETAIN — pooled replay delta %+.2f with %d session(s) "
                "improved and none hurt" % (d, o["sessions_improved"]))
    if d > 0:
        return ("RETAIN (CONTESTED) — pooled replay delta %+.2f but it loses "
                "%d session(s)" % (d, o["sessions_hurt"]))
    return ("DROP — pooled replay delta %+.2f over seven sessions (%d "
            "improved / %d hurt), %d D-021 winners refused"
            % (d, o["sessions_improved"], o["sessions_hurt"],
               o["n_winners_vetoed"]))


# ================================= item 6: the S7/S8 event-statistic censuses
EVENT_COLUMNS = ("stat", "asset", "era", "decile", "lo", "hi", "n", "n_share",
                 "n_winners", "winner_share", "winner_rate",
                 "base_winner_rate", "winner_rate_lift", "conc_ratio",
                 "mean_close_usd", "cond_close_usd", "mean_peak_usd",
                 "n_sessions", "verdict")


def event_rows(D, rows, robust, destr):
    """c2f / erosion / through-book vs winner content at ROW grain.

    Concentrator screens: these are magnitude/liquidity statistics, so the
    reachable grades are CONCENTRATOR and NULL.  The one DIRECTIONAL reading
    the erosion terms admit (which side is restocking) is scored separately
    under the mirror law."""
    for stat in EVENT_STATS:
        v = (D[stat].astype(np.float64) if stat != "thru_n"
             else np.where(D["thru_n"] >= 0, D["thru_n"], np.nan)
             .astype(np.float64))
        fitm = (D["era"] == ERAS[0]) & np.isfinite(v)
        if fitm.sum() < 1000:
            continue
        edges = np.unique(np.percentile(v[fitm],
                                        np.linspace(0, 100, P033_DECILES + 1)))
        for aname in ("ALL",) + tuple(MC.ASSET_ORDER):
            for ename in ERAS:
                m = ((D["era"] == ename) & np.isfinite(v)
                     & ((D["asset"] == aname) if aname != "ALL"
                        else np.ones(v.size, bool)))
                if m.sum() < 200:
                    continue
                win = D["winner"][m].astype(float)
                cc = D["cert_close"][m]
                cp = D["cert_peak"][m]
                vv = v[m]
                base = float(win.mean())
                w_tot = float(win.sum())
                best = None
                for k in range(edges.size - 1):
                    lo = edges[k]
                    hi = edges[k + 1] if k < edges.size - 2 else np.inf
                    b = (vv >= lo) & (vv < hi)
                    n = int(b.sum())
                    if n < 20:
                        continue
                    ws = (float(win[b].sum()) / w_tot) if w_tot else None
                    ns = n / float(m.sum())
                    pos = cc[b][cc[b] > 0]
                    lift = (float(win[b].mean()) / base) if base > 0 else None
                    if lift is not None and (best is None or lift > best):
                        best = lift
                    rows.append([stat, aname, ename, k, float(lo), float(hi),
                                 n, ns, int(win[b].sum()), ws,
                                 float(win[b].mean()), base, lift,
                                 (ws / ns) if (ws is not None and ns > 0)
                                 else None, float(np.nanmean(cc[b])),
                                 float(pos.mean()) if pos.size else None,
                                 float(np.nanmean(cp[b])),
                                 len(set(D["session_key"][m][b].tolist())),
                                 "-"])
                if aname == "ALL":
                    for i in range(len(rows) - 1, -1, -1):
                        if rows[i][0] != stat or rows[i][1] != aname \
                                or rows[i][2] != ename:
                            break
                        rows[i][18] = ("CONCENTRATOR (best decile lift %.2fx)"
                                       % best if (best is not None
                                                  and best >= CONCENTRATOR_MIN)
                                       else "NULL (best decile lift %s)"
                                       % B4._fmt(best, 2))
                # ---- GEE on the continuous statistic ------------------------
                if aname != "ALL":
                    continue
                z0 = (vv - vv.mean()) / max(vv.std(), 1e-9)
                cl = D["session_key"][m]
                gi = np.unique(cl, return_inverse=True)[1]
                for metric, y, link in (("winner", win, "logit"),
                                        ("cert_close", cc, "identity")):
                    g = EV.gee_independence(y, z0, cl, link=link)
                    ic = EV.icc_oneway(y, gi)
                    if g is None:
                        continue
                    z = (g["beta"] / g["se_cr1"]) if g["se_cr1"] > 0 else \
                        float("nan")
                    robust.append(["EVENT_%s" % stat, ename, metric, "SESSION",
                                   g["n"], g["n_clusters"], int(m.sum()),
                                   g["beta"], g["se_naive"], g["se_cr0"],
                                   g["se_cr1"], z, P1._p_two_sided(z),
                                   ic["rho"] if ic else float("nan"),
                                   ic["deff"] if ic else float("nan"),
                                   ic["n_eff"] if ic else float("nan"),
                                   _sig(P1._p_two_sided(z))])
                if ename != ERAS[0]:
                    continue
                thr = float(np.percentile(vv, 90))
                fire = vv >= thr
                real = (float(win[fire].mean() - win[~fire].mean())
                        if fire.any() and (~fire).any() else float("nan"))
                rs = np.random.RandomState(DESTRUCTION_SEED + 5)
                null = []
                for _ in range(DESTRUCTION_REPS):
                    f2 = B4._shuffle_within(vv, cl, rs) >= thr
                    if f2.any() and (~f2).any():
                        null.append(float(win[f2].mean() - win[~f2].mean()))
                destr.append(B4._destr_row("EVENT_%s_top_decile" % stat, ename,
                                           "%s (within session)" % stat, real,
                                           null))
    return rows


def erosion_side_rows(D, rows, mrows, robust, destr):
    """The one DIRECTIONAL claim the erosion terms admit, under the mirror law.

    DECLARED FORM (before the count): the L1 side that is RESTOCKING faster is
    the side being defended, so dBsz - dAsz >= THR -> LONG, <= -THR -> SHORT,
    else NO-CALL (scored as a miss — abstention is not free)."""
    d = D["dbsz_min"] - D["dasz_min"]
    for thr in EROSION_THR_GRID:
        call = np.zeros(d.size, dtype=np.int64)
        call[np.isfinite(d) & (d >= thr) & (thr > 0)] = +1
        call[np.isfinite(d) & (d <= -thr) & (thr > 0)] = -1
        if thr == 0.0:
            call[np.isfinite(d) & (d > 0)] = +1
            call[np.isfinite(d) & (d < 0)] = -1
        _row_side_tables(D, call, "S7_EROSION_SIDE", "ROW", thr, rows, mrows,
                         robust, destr if thr == EROSION_THR else None)
    return rows


# ==================================================================== report
_fmt = B4._fmt


def report(D, cells, res, elapsed, pins):
    L = []
    A_ = L.append
    A_("# PORT M2 — CENSUS BATCH 5 (CC-M2-19.6): ROLLING SEAT / S10 SIDE / "
       "P032 / P033 / V2-V3 / EVENT STATISTICS")
    A_("")
    A_("* population: %d ROWS in %d CELLS over %d sessions of the frozen v3 "
       "roster (FIT %d-%d + GATE-%dH1 echo)."
       % (D["dec_sec"].size, len(cells), D["n_sessions"], FIT_YEARS[0],
          FIT_YEARS[-1], GATE_YEAR))
    A_("* HOLDOUT: %d sessions with d8 >= %d were NEVER LOADED (CC-M2-15.3)."
       % (D["n_quarantined"], HOLDOUT_FROM_D8))
    A_("* runtime %.1fs; pins %s"
       % (elapsed, "HELD" if not pins else "MOVED: " + "; ".join(pins)))
    A_("")

    A_("## 1. THE ROLLING SEAT-MODEL REFIT (the headline)")
    A_("")
    A_("Four decision procedures, one target (the cell holds >= 1 D-021 "
       "winner), the same test cells, PAIRED session-cluster bootstrap:")
    A_("")
    A_("| asset | scope | grain | model | n_test | base | AUC | 95% CI | "
       "dAUC vs cell-open | paired 95% CI | p | verdict |")
    A_("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in res["auc"]:
        if r[0] != "ALL":
            continue
        A_("| %s | %s | %s | %s | %d | %s | **%s** | [%s, %s] | %s | [%s, %s] "
           "| %s | %s |"
           % (r[0], r[1], r[2], r[3], r[5], _fmt(r[6], 3), _fmt(r[7], 4),
              _fmt(r[8], 3), _fmt(r[9], 3), _fmt(r[12], 4), _fmt(r[13], 4),
              _fmt(r[14], 4), _fmt(r[15], 4), r[16]))
    A_("")
    A_("Per asset (pooled walk-forward + the GATE echo):")
    A_("")
    A_("| asset | scope | model | AUC | dAUC vs cell-open | verdict |")
    A_("|---|---|---|---|---|---|")
    for r in res["auc"]:
        if r[0] == "ALL" or r[2] != "CELL" or r[1] not in (
                "WF_POOLED", "GATE_%dH1_FROZEN" % GATE_YEAR):
            continue
        A_("| %s | %s | %s | %s | %s | %s |"
           % (r[0], r[1], r[3], _fmt(r[7], 4), _fmt(r[12], 4), r[16]))
    A_("")
    A_("### the day-7 rolling-anchor claim at era scale")
    A_("")
    A_("| grain | band | n | winners | winner rate | winner share | "
       "conc ratio | seat-ahead rate |")
    A_("|---|---|---|---|---|---|---|---|")
    for r in res["bands"]:
        if r[1] != "ALL" or r[2] != "FIT":
            continue
        A_("| %s | %s | %d | %d | %s | %s | %s | %s |"
           % (r[0], r[3], r[6], r[8], _fmt(r[10], 4), _fmt(r[9], 3),
              _fmt(r[11], 2), _fmt(r[15], 3)))
    A_("")
    A_("### the models' coefficients (FIT, ALL assets, per SD, CR1)")
    A_("")
    A_("| model | grain | term | beta | se_CR1 | z | p |")
    A_("|---|---|---|---|---|---|---|")
    for r in res["model"]:
        if r[2] != "ALL" or r[3] != "FIT":
            continue
        A_("| %s | %s | %s | %s | %s | %s | %s |"
           % (r[0], r[1], r[4], _fmt(r[5], 4), _fmt(r[8], 4), _fmt(r[9], 2),
              _fmt(r[10], 5)))
    A_("")

    A_("## 2. S10 SIDE GEOMETRY (d_POC sign + in_VA) UNDER THE MIRROR LAW")
    A_("")
    A_("| grain | thr $ | era | n | called | scoreable | agreement | mirror | "
       "winner rate agree | disagree | delta value $ | sign-test p | verdict |")
    A_("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in res["s10"]:
        if r[3] != "ALL" or r[0] != "S10_SIDE":
            continue
        A_("| %s | %s | %s | %d | %d | %d | %s | %s | %s | %s | %s | %s | %s |"
           % (r[1], _fmt(r[2], 0), r[4], r[5], r[6], r[8], _fmt(r[10], 3),
              _fmt(r[11], 3), _fmt(r[13], 4), _fmt(r[14], 4), _fmt(r[20], 0),
              _fmt(r[22], 4), r[23]))
    A_("")
    A_("### the mirror law, per session (CC-M2-13.1)")
    A_("")
    A_("| object | grain | thr | era | sessions | won | tied | lost | "
       "mirror law holds | mean delta $ | Holm |")
    A_("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in res["mirror"]:
        if r[3] != "ALL" or r[0] != "S10_SIDE":
            continue
        A_("| %s | %s | %s | %s | %d | %d | %d | %d | **%d** | %s | %s |"
           % (r[0], r[1], _fmt(r[2], 0), r[4], r[5], r[6], r[7], r[8], r[9],
              _fmt(r[10], 0), r[16]))
    A_("")
    A_("VERDICT S10 SIDE: **%s** — %s" % res["grade_s10"])
    A_("")

    A_("## 3. P032 PRIOR_CELL_TRAVEL — THE SIGN CONTRADICTION")
    A_("")
    A_("| field | grain | reading | era | n | beta/SD | z | p | sign | "
       "clause fires | clause precision | base rate | clause recall |")
    A_("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in res["p032"]:
        if r[3] != "ALL":
            continue
        A_("| %s | %s | %s | %s | %d | %s | %s | %s | **%s** | %s | %s | %s | "
           "%s |"
           % (r[0], r[1], r[2], r[4], r[5], _fmt(r[7], 4), _fmt(r[9], 2),
              _fmt(r[10], 5), r[11], (r[15] if r[15] is not None else "-"),
              _fmt(r[16], 3), _fmt(r[17], 3), _fmt(r[18], 3)))
    A_("")

    A_("## 4. P033 FEASIBILITY_IS_RUNWAY_TIMES_VOL (census-first)")
    A_("")
    A_("| form | control | decile | n | winner rate | lift | conc ratio | "
       "mean close $ | cond close $ |")
    A_("|---|---|---|---|---|---|---|---|---|")
    for r in res["p033"]:
        if r[2] != "ALL" or r[3] != "FIT" or r[1] != "ALL":
            continue
        A_("| %s | %s | %d | %d | %s | %s | %s | %s | %s |"
           % (r[0], r[1], r[4], r[7], _fmt(r[11], 4), _fmt(r[13], 2),
              _fmt(r[14], 2), _fmt(r[15], 0), _fmt(r[16], 0)))
    A_("")
    A_("Within the raw runway bands (the P025 control), PRODUCT form, FIT:")
    A_("")
    A_("| runway band | decile | n | winner rate | lift |")
    A_("|---|---|---|---|---|")
    for r in res["p033"]:
        if (r[0] != "PRODUCT_runway_x_rv1800" or r[1] == "ALL"
                or r[2] != "ALL" or r[3] != "FIT" or r[4] not in (0, 4, 8, 9)):
            continue
        A_("| %s | %d | %d | %s | %s |"
           % (r[1], r[4], r[7], _fmt(r[11], 4), _fmt(r[13], 2)))
    A_("")
    A_("VERDICT P033: **%s** — %s" % res["grade_p033"])
    A_("")

    A_("## 5. V2/V3 POOLED RE-GRADE OVER SEVEN STUDY SESSIONS")
    A_("")
    A_("| family | core takes | vetoed | winners vetoed | mean close vetoed | "
       "mean close stood | replay delta $ | seat-spenders vetoed (DP/REPLAY) | "
       "sessions +/- | verdict |")
    A_("|---|---|---|---|---|---|---|---|---|---|")
    for fam in ("V2", "V3", "V2_OR_V3", "V2_SOLE", "V3_SOLE"):
        g = {r[2]: r[3] for r in res["veto"]
             if r[0] == fam and r[1] == "POOLED_7_SESSIONS"}
        if not g:
            continue
        A_("| %s | %s | %s | %s | %s | %s | **%s** | %s/%s | %s/%s | %s |"
           % (fam, g.get("n_core_takes"), g.get("n_vetoed"),
              g.get("n_winners_vetoed"), _fmt(g.get("mean_close_vetoed"), 2),
              _fmt(g.get("mean_close_stood"), 2),
              _fmt(g.get("replay_delta_usd"), 2),
              g.get("DP_vetoed_seat_spenders"),
              g.get("REPLAY_vetoed_seat_spenders"),
              g.get("sessions_improved"), g.get("sessions_hurt"),
              g.get("verdict")))
    A_("")

    A_("## 6. S7/S8 EVENT STATISTICS AT ROW GRAIN (%d sessions of cache)"
       % D["n_sessions"])
    A_("")
    A_("| stat | era | top decile n | winner rate | base | lift | "
       "mean close $ | verdict |")
    A_("|---|---|---|---|---|---|---|---|")
    for r in res["events"]:
        if r[1] != "ALL" or r[3] != max(
                (x[3] for x in res["events"]
                 if x[0] == r[0] and x[1] == "ALL" and x[2] == r[2]),
                default=-1):
            continue
        A_("| %s | %s | %d | %s | %s | %s | %s | %s |"
           % (r[0], r[2], r[6], _fmt(r[10], 4), _fmt(r[11], 4),
              _fmt(r[12], 2), _fmt(r[14], 0), r[18]))
    A_("")
    A_("### the erosion SIDE claim under the mirror law")
    A_("")
    A_("| thr | era | called | agreement | mirror | delta value $ | won/lost | "
       "verdict |")
    A_("|---|---|---|---|---|---|---|---|")
    for r in res["s10"]:
        if r[0] != "S7_EROSION_SIDE" or r[3] != "ALL":
            continue
        mm = [m for m in res["mirror"] if m[0] == "S7_EROSION_SIDE"
              and m[2] == r[2] and m[3] == "ALL" and m[4] == r[4]]
        A_("| %s | %s | %d | %s | %s | %s | %s | %s |"
           % (_fmt(r[2], 0), r[4], r[6], _fmt(r[10], 3), _fmt(r[11], 3),
              _fmt(r[20], 0),
              ("%d/%d" % (mm[0][6], mm[0][8])) if mm else "-", r[23]))
    A_("")

    A_("## 7. MECHANISM DESTRUCTION")
    A_("")
    A_("| object | era | neutralised | edge | destroyed mean | destroyed sd | "
       "z | verdict |")
    A_("|---|---|---|---|---|---|---|---|")
    for r in res["destr"]:
        A_("| %s | %s | %s | %s | %s | %s | %s | **%s** |"
           % (r[0], r[1], r[2], _fmt(r[4], 4), _fmt(r[5], 4), _fmt(r[6], 4),
              _fmt(r[9], 2), r[10]))
    A_("")
    A_("SURVIVES = the real edge clears its own within-session shuffle by >= 2 "
       "sd; DESTROYED = it sits inside the null; **INVERTED = it sits BELOW "
       "the null**, i.e. the field carries information against the claim.")
    A_("")

    A_("## 8. EVERY GEE TEST, ONE HOLM FAMILY (%d tests)"
       % len([r for r in res["robust"] if np.isfinite(r[12])]))
    A_("")
    A_("| object | era | metric | n | clusters | beta | se_CR1 | z | p | "
       "n_eff | Holm |")
    A_("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in res["robust"]:
        if r[19] != "HOLM_SIGNIFICANT":
            continue
        A_("| %s | %s | %s | %d | %d | %s | %s | %s | %s | %s | %s |"
           % (r[0], r[1], r[2], r[4], r[5], _fmt(r[7], 4), _fmt(r[10], 4),
              _fmt(r[11], 2), _fmt(r[12], 6), _fmt(r[15], 0), r[19]))
    A_("")
    A_("(only the Holm-significant rows are rendered; BATCH5_ROBUST.tsv "
       "carries every test.)")
    return "\n".join(L) + "\n"


# ====================================================================== build
def build(workers=6, limit_sessions=None, want_events=True):
    t0 = time.time()
    MC.verify_spec(force=True)
    D = scan(workers=workers, limit_sessions=limit_sessions,
             want_events=want_events)
    D["roll_seat"] = rolling_seat_state(D)
    cells = cells_of(D)
    MC.hb("batch5: %d cells built from %d rows" % (len(cells),
                                                   D["dec_sec"].size))

    res = {}
    robust, destr = [], []
    res["bands"] = roll_band_rows(D, cells, [])
    res["model"] = model_rows(D, cells, [], robust)
    MC.hb("batch5: seat models fitted (%d coefficient rows)"
          % len(res["model"]))
    res["auc"] = auc_rows(D, cells, [], robust)
    MC.hb("batch5: paired walk-forward AUC done (%d rows)" % len(res["auc"]))

    side_rows, mir_rows = [], []
    s10_rows(D, cells, side_rows, mir_rows, robust, destr)
    MC.hb("batch5: S10 side geometry done (%d rows)" % len(side_rows))
    res["p032"] = p032_rows(D, cells, [], robust, destr)
    res["p033"] = p033_rows(D, [], robust, destr)
    MC.hb("batch5: P032/P033 done")
    res["veto"], res["veto_sessions"] = veto_regrade(D, [], [])
    MC.hb("batch5: V2/V3 pooled re-grade done")
    res["events"] = (event_rows(D, [], robust, destr) if want_events else [])
    if want_events:
        erosion_side_rows(D, side_rows, mir_rows, robust, destr)
    res["s10"] = side_rows
    res["mirror"] = B4._holm(mir_rows, 13, len(MIRROR_COLUMNS))
    B4._holm(robust, 12, len(B4.ROBUST_COLUMNS))
    res["robust"] = robust
    res["destr"] = destr
    res["grade_s10"] = grade_s10(res["s10"], res["mirror"])
    res["grade_p033"] = grade_p033(res["p033"], robust)

    phash = MC.params_hash(PARAMS)
    extra = ["CC-M2-19.6 census batch 5 — ROW and CELL are both units and both "
             "are named on every table",
             "BOTH CC-M1-8 certificate readings are reported on every value "
             "row",
             "Holm-Bonferroni over the WHOLE batch, not per object",
             "HOLDOUT: no session with d8 >= %d was loaded (CC-M2-15.3)"
             % HOLDOUT_FROM_D8]
    W = MC.write_tsv
    cell_cols = ["asset", "d8", "year", "phase", "era", "n_cand", "n_win",
                 "n_win_long", "n_win_short", "has_seat", "winner_side",
                 "first_dec_sec", "last_dec_sec", "rv1800_open", "rv60_open",
                 "atr_open", "unspent_open", "prev_ret_usd", "prev_range_usd",
                 "pre_cell_range_usd", "d_poc_open", "in_va_open",
                 "release_in_ph", "dow", "mean_close", "mean_peak",
                 "cond_close", "win_close_sum", "rv1800_max_row",
                 "rv1800_at_first_winner"]
    crows = []
    for c in cells:
        rv = D["rv1800"][c["rows"]]
        wm = D["winner"][c["rows"]]
        crows.append([c["asset"], c["d8"], c["year"], PHASES[c["phase"]],
                      era_of_cell(c), c["n_cand"], c["n_win"],
                      c["n_win_long"], c["n_win_short"],
                      int(c["n_win"] >= 1), B4.winner_side(c),
                      c["first_dec_sec"], c["last_dec_sec"], c["rv1800_open"],
                      c["rv60_open"], c["atr_open"], c["unspent_open"],
                      c["prev_ret_usd"], c["prev_range_usd"],
                      c["pre_cell_range_usd"], c["d_poc_open"],
                      c["in_va_open"], c["release_in_ph"], c["dow"],
                      c["mean_close"], c["mean_peak"], c["cond_close"],
                      c["win_close_sum"],
                      float(np.nanmax(rv)) if rv.size else float("nan"),
                      float(rv[wm][0]) if wm.any() else float("nan")])
    W(os.path.join(OUT_DIR, "BATCH5_CELLS.tsv"), SECTION, phash, cell_cols,
      crows, extra=extra + ["rv1800_max_row / rv1800_at_first_winner are the "
                            "ROLLING readings of the same field the cell-open "
                            "column freezes at the open — the day-7 "
                            "stale-anchor finding in two columns"])
    W(os.path.join(OUT_DIR, "SEAT_ROLLING_AUC.tsv"), SECTION, phash,
      list(AUC_COLUMNS), res["auc"],
      extra=extra + ["ROLL_MAX commits LATER than the cell open (it is an "
                     "operating mode, not a cell-open forecast); ROLL@open is "
                     "the causal-at-open control and the ROW rows are the "
                     "rolling model's own fully-causal reading",
                     "delta_* are PAIRED: the same bootstrap sessions score "
                     "every model"])
    W(os.path.join(OUT_DIR, "SEAT_ROLLING_MODEL.tsv"), SECTION, phash,
      list(MODEL_COLUMNS), res["model"],
      extra=extra + ["betas are per STANDARD DEVIATION of the feature"])
    W(os.path.join(OUT_DIR, "SEAT_ROLLING_BANDS.tsv"), SECTION, phash,
      list(BAND_COLUMNS), res["bands"], extra=extra)
    W(os.path.join(OUT_DIR, "S10_SIDE.tsv"), SECTION, phash,
      list(SIDE_COLUMNS), res["s10"],
      extra=extra + ["in_VA = -1 is REFUSED (a missing VA edge) and never "
                     "calls — sections.s10_profile's V1.1 ruling, obeyed"])
    W(os.path.join(OUT_DIR, "S10_MIRROR.tsv"), SECTION, phash,
      list(MIRROR_COLUMNS), res["mirror"],
      extra=extra + ["CC-M2-13.1: mirror_law_holds = the estimator beat its "
                     "mirror on EVERY session and lost on none"])
    W(os.path.join(OUT_DIR, "P032_GRAINS.tsv"), SECTION, phash,
      list(P032_COLUMNS), res["p032"],
      extra=extra + ["MARGINAL vs PARTIAL_GIVEN_RV1800 is the whole point: "
                     "CC-M2-18.1's negative sign was read inside a model that "
                     "already carried rv1800"])
    W(os.path.join(OUT_DIR, "P033_DECILES.tsv"), SECTION, phash,
      list(P033_COLUMNS), res["p033"],
      extra=extra + ["decile cuts are computed on the FIT pool and APPLIED to "
                     "the GATE echo; control_band = the raw P025 runway band"])
    W(os.path.join(OUT_DIR, "VETO_POOLED.tsv"), SECTION, phash,
      list(VETO_COLUMNS), res["veto"],
      extra=extra + ["the pre-veto pool is the frozen five-term CORE "
                     "(e1d7_policy.terms) on every candidate of the seven E1 "
                     "study sessions"])
    W(os.path.join(OUT_DIR, "VETO_SESSIONS.tsv"), SECTION, phash,
      list(VSESS_COLUMNS), res["veto_sessions"], extra=extra)
    W(os.path.join(OUT_DIR, "EVENT_STATS.tsv"), SECTION, phash,
      list(EVENT_COLUMNS), res["events"], extra=extra)
    W(os.path.join(OUT_DIR, "EVENT_MIRROR.tsv"), SECTION, phash,
      list(MIRROR_COLUMNS),
      [r for r in res["mirror"] if r[0] == "S7_EROSION_SIDE"], extra=extra)
    W(os.path.join(OUT_DIR, "BATCH5_DESTRUCTION.tsv"), SECTION, phash,
      list(B4.DESTR_COLUMNS), res["destr"], extra=extra)
    W(os.path.join(OUT_DIR, "BATCH5_ROBUST.tsv"), SECTION, phash,
      list(B4.ROBUST_COLUMNS), res["robust"], extra=extra)

    pins = MC.pins_moved()
    el = time.time() - t0
    MC.write_text(os.path.join(OUT_DIR, "BATCH5_CENSUS_REPORT.md"),
                  report(D, cells, res, el, pins))
    head = [r for r in res["auc"] if r[0] == "ALL" and r[1] == "WF_POOLED"
            and r[2] == "CELL"]
    MC.write_json(os.path.join(OUT_DIR, "batch5_census.receipt.json"),
                  {"env": MC.env_receipt(PARAMS),
                   "n_rows": int(D["dec_sec"].size), "n_cells": len(cells),
                   "n_sessions": D["n_sessions"],
                   "n_holdout_sessions_quarantined": D["n_quarantined"],
                   "holdout_from_d8": HOLDOUT_FROM_D8,
                   "events_used": bool(want_events),
                   "auc_wf_pooled": {r[3]: r[7] for r in head},
                   "dauc_wf_pooled_vs_cell_open": {r[3]: r[12] for r in head},
                   "grade_S10_SIDE": res["grade_s10"][0],
                   "grade_P033": res["grade_p033"][0],
                   "n_gee_tests": int(len([r for r in res["robust"]
                                           if np.isfinite(r[12])])),
                   "n_holm_significant":
                       int(len([r for r in res["robust"]
                                if r[19] == "HOLM_SIGNIFICANT"])),
                   "elapsed_sec": el, "pins_moved": pins,
                   "out_dir": OUT_DIR})
    MC.hb("batch5 census: %d rows / %d cells, S10=%s, P033=%s, %.1fs"
          % (D["dec_sec"].size, len(cells), res["grade_s10"][0],
             res["grade_p033"][0], el))
    return res


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--workers", type=int, default=6)
    p.add_argument("--limit-sessions", type=int, default=None)
    p.add_argument("--no-events", action="store_true")
    a = p.parse_args()
    if a.workers > 8:
        raise SystemExit("workers capped at 8 (D-002 lane discipline)")
    build(workers=a.workers, limit_sessions=a.limit_sessions,
          want_events=not a.no_events)
    return 0


if __name__ == "__main__":
    sys.exit(main())
