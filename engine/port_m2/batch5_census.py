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
  * HOLM-BONFERRONI over THE WHOLE BATCH — R61: ONE family across EVERY table
    that publishes a test (the GEEs, the model coefficients, the paired mirror
    tests, the paired dAUC bootstrap, P032's per-asset betas, the concentrator
    max-decile nulls and the V2/V3 replay test), via
    batch4_census._holm_family, which writes holm_rank / holm_threshold /
    holm_verdict / p_holm onto every row it corrects.  A p outside the family
    is labelled a DIAGNOSTIC and is read by no grader.
  * THE MIRROR LAW AT ERA SCALE (R59) is m2_common.mirror_paired — a
    session-clustered PAIRED test on the per-session mirror delta, graded on
    its HOLM-ADJUSTED p, with n_sessions and the 80%-power MDE beside it.  The
    study-round sweep bit (`lost == 0 and won > 0`) survives only as the
    `sweep_clean` diagnostic column and gates nothing.
  * D-077-UPDATE(3): every number here is a SCIENCE reading; rows and receipts
    that carry a DEPLOYABLE split say so (R77).
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
# R65: V2 and V3 were FITTED on study sessions 1-5 and are re-graded on 1-7, so
# five sevenths of the pooled statistic is in-sample.  Named, not implied.
_V2V3_FIT_D8 = STUDY_D8[:5]

# ---- item 6: the event statistics ------------------------------------------
EVENT_STATS = ("c2f_60", "c2f_300", "dbsz_min", "dasz_min", "thru_n")
EROSION_THR_GRID = (0.0, 5.0, 20.0, 100.0)
EROSION_THR = 20.0

BOOT_REPS = 400
BOOT_SEED = 20260818
# R64: a CONCENTRATOR grade is a MAX-OVER-DECILES statistic and the max of ten
# noisy ratios clears a fixed 1.25x bar under the null far more often than 5%
# of the time.  Every max-lift grade now carries a session-clustered null for
# THE MAXIMUM, a bootstrap CI, and Holm membership.
MAXLIFT_REPS = 200
NEWS_WINDOW_MIN = B4.NEWS_WINDOW_MIN      # +/- minutes, D-077-UPDATE (R77)
READINGS = B4.READINGS                    # ("SCIENCE", "DEPLOYABLE")

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
    "mirror_law": "R59 — the ERA-SCALE form is m2_common.mirror_paired (a "
                  "session-clustered PAIRED t-test on the per-session mirror "
                  "delta), graded on the Holm-adjusted p, NO_TEST below %d "
                  "sessions.  `sweep_clean` (lost == 0 and won > 0) is the "
                  "STUDY-ROUND diagnostic and gates nothing."
                  % MC.MIRROR_MIN_SESSIONS,
    "row_grain_mirror": "R68 — the ROW-grain mirror is a TRUE SIGN FLIP: the "
                        "payoff of a call on a row is +cert when the row's own "
                        "side agrees with it and -cert when it opposes it, so "
                        "value(-k) == -value(k) on the SAME rows.  The old "
                        "form summed cert over the AGREEING rows and compared "
                        "it to the sum over the DISAGREEING rows — two "
                        "disjoint populations, and the difference was "
                        "confounded by the session's generation-side "
                        "asymmetry.  `agreement_null` (the agreement that "
                        "asymmetry alone produces, computed by reassigning the "
                        "call at random inside the session) is published on "
                        "every row so the raw agreement is read against its "
                        "own null and not against 0.5.",
    "abstention": "R69 — a NO-CALL is SCORED AS A MISS as declared: it sits in "
                  "the agreement denominator, contributes $0 to both arms, and "
                  "its session stays in the mirror's session list.  "
                  "`agreement_called_only` keeps the old number beside it.",
    "deployable_reading": "D-077-UPDATE(3) / R77 — the census carries signed "
                          "minutes to the nearest scheduled release at every "
                          "ROW, and the concentrator/AUC/veto readings are "
                          "reported with the +/-%.0f min restricted window "
                          "both IN (SCIENCE) and OUT (DEPLOYABLE)."
                          % NEWS_WINDOW_MIN,
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
        "c2f_60", "c2f_300", "dbsz_min", "dasz_min", "mins_to_release")
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
        # R77 / D-077-UPDATE: signed minutes to the nearest scheduled release,
        # so the DEPLOYABLE reading is computable from this census's own rows.
        "mins_to_release": B4._mins_to_release(open_utc + dec),
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
        keep, nq = PL.sessions_fit(a, years=set(FIT_YEARS) | {GATE_YEAR})
        quarantined += nq
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


def deployable_mask(D):
    """D-077-UPDATE(1) / R77 — the rows a COMPLIANT policy may enter at all.

    A row inside +/-%.0f minutes of a scheduled release is not deployable.  A
    row whose minutes are REFUSED (no calendar coverage) is left in and the
    count is declared in the receipt — a refusal is not silently a veto.
    """ % NEWS_WINDOW_MIN
    mm = D["mins_to_release"]
    return ~(np.isfinite(mm) & (np.abs(mm) <= NEWS_WINDOW_MIN))


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
               "delta_p_boot", "verdict", "reading",
               "holm_rank", "holm_threshold", "holm_verdict", "p_holm")
AUC_P_COL = AUC_COLUMNS.index("delta_p_boot")
# R62: `delta_p_boot` (4 models x 6 scopes x 4 asset groups) was published with
# no correction at all, and CC-M2-21.1's per-asset anchor ruling was read off
# exactly those paired CIs.  The column is in the ONE batch family now.
# R77: `reading` names the D-077 reading these AUCs are computed under.


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
            aucs, deltas = _paired_boot(
                yte, sc, cl, seed=B4._seed_for("B5AUC|%s|%s" % (aname, name),
                                               BOOT_SEED))
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
                             _auc_verdict(mname, d, dl, dh), "SCIENCE"])
            # ---- the rolling model's own fully-causal reading (ROW grain) ---
            yr_te = y_row_all[te_rows]
            pr = B4.predict_logit(m_roll, row_design(D, te_rows, ROW_FEATURES))
            clr = D["session_key"][te_rows]
            a = B4.auc(yr_te, pr)
            lo, hi = B4._cluster_boot_auc(
                yr_te, pr, clr,
                seed=B4._seed_for("B5ROW|%s|%s" % (aname, name), BOOT_SEED))
            rows.append([aname, name, "ROW", "ROLL", tr_rows.size,
                         te_rows.size, float(yr_te.mean()), a, lo, hi,
                         float(np.mean((pr - yr_te) ** 2)),
                         float(np.mean((yr_te.mean() - yr_te) ** 2)),
                         None, None, None, None, "-", "SCIENCE"])
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
        aucs, deltas = _paired_boot(
            yte, sc, cl, seed=B4._seed_for("B5AUC|%s|WF_POOLED" % aname,
                                           BOOT_SEED))
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
                         _auc_verdict(mname, d, dl, dh), "SCIENCE"])
        yr = np.concatenate(pooled["yrow"])
        pr = np.concatenate(pooled["srow"])
        clr = np.concatenate(pooled["clrow"])
        lo, hi = B4._cluster_boot_auc(
            yr, pr, clr,
            seed=B4._seed_for("B5ROW|%s|WF_POOLED" % aname, BOOT_SEED))
        rows.append([aname, "WF_POOLED", "ROW", "ROLL", pooled["n_tr"],
                     yr.size, float(yr.mean()), B4.auc(yr, pr), lo, hi,
                     float(np.mean((pr - yr) ** 2)),
                     float(np.mean((yr.mean() - yr) ** 2)),
                     None, None, None, None, "-", "SCIENCE"])
        if aname == "ALL":
            _seat_gee(yte, sc, cl, "FIT", robust)
    return rows


def apply_auc_verdicts(rows):
    """R62 — the AUC verdicts read the HOLM-ADJUSTED delta p, not a bare CI.

    CC-M2-21.1's per-asset anchor ruling (4 models x 6 scopes x 4 asset groups)
    was read off these paired CIs with no multiplicity control at all."""
    for r in rows:
        p = r[15]
        if r[3] == "OPEN" or p is None or not np.isfinite(p):
            continue
        ph = r[21] if len(r) > 21 else float("nan")
        ok = bool(np.isfinite(ph) and ph < 0.05)
        r[16] = "%s [Holm p=%s -> %s]" % (
            r[16], B4._fmt(ph, 4),
            "SIGNIFICANT IN THE BATCH FAMILY" if ok
            else "NOT significant after Holm")
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
                 "n", "n_clusters", "n_seats", "seat_rate", "n_imputed_term",
                 "holm_rank", "holm_threshold", "holm_verdict", "p_holm")
MODEL_P_COL = MODEL_COLUMNS.index("p_cr1")


def model_rows(D, cells, rows, robust):
    """The two models' coefficients (per SD, session-clustered).

    R60: the docstring said "Holm-corrected" and the p column had never been
    corrected by anything — `robust` was taken as an argument and never
    written to.  These rows are IN the batch family now (`_holm_family` in
    build fills their holm_* / p_holm columns), and the imputation count per
    term is published beside each coefficient (R71)."""
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
                nimp = B4.imputed_counts(Xm, CELL_FEATURES_UNS)[0]
                mu, sd = B4._standardise(Xm)
                Z = (B4._impute(Xm, mu) - mu) / sd
                g = B4.gee_multi(y, Z, cl, link="logit")
                if g is not None:
                    _emit_model(rows, "CELL_OPEN+UNS", "CELL", aname, ename,
                                ("intercept",) + CELL_FEATURES_UNS, g, y, nimp)
            # ---- ROW grain (the rolling state) ----
            idx = np.concatenate([c["rows"] for c in sub])
            yr = D["roll_seat"][idx]
            if not (0 < yr.sum() < yr.size):
                continue
            Xm = row_design(D, idx, ROW_FEATURES)
            nimp = B4.imputed_counts(Xm, ROW_FEATURES)[0]
            mu, sd = B4._standardise(Xm)
            Z = (B4._impute(Xm, mu) - mu) / sd
            g = B4.gee_multi(yr, Z, D["session_key"][idx], link="logit")
            if g is None:
                continue
            _emit_model(rows, "ROLLING", "ROW", aname, ename,
                        ("intercept",) + ROW_FEATURES, g, yr, nimp)
    return rows


def _emit_model(rows, model, grain, aname, ename, terms, g, y, nimp=None):
    for j, tn in enumerate(terms):
        z = (g["beta"][j] / g["se_cr1"][j] if g["se_cr1"][j] > 0
             else float("nan"))
        rows.append([model, grain, aname, ename, tn, float(g["beta"][j]),
                     float(g["se_naive"][j]), float(g["se_cr0"][j]),
                     float(g["se_cr1"][j]), z, P1._p_two_sided(z),
                     float(np.exp(g["beta"][j])), g["n"], g["n_clusters"],
                     int(y.sum()), float(y.mean()),
                     0 if (j == 0 or nimp is None) else int(nimp[j - 1])])


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
                "delta_value_usd", "n_sessions", "sign_test_p_diagnostic",
                "verdict", "agreement_null", "agreement_called_only",
                "n_rows_side_long", "n_rows_side_short", "mirror_p_holm")

MIRROR_COLUMNS = ("object", "grain", "threshold", "asset", "era", "n_sessions",
                  "sessions_won", "sessions_tied", "sessions_lost",
                  "sweep_clean", "mean_delta_usd", "sd_usd", "se_session", "t",
                  "p", "p_sign", "mde_80_usd", "n_sessions_min", "verdict",
                  "holds_pre_holm", "holm_rank", "holm_threshold",
                  "holm_verdict", "p_holm")
MIRROR_P_COL = MIRROR_COLUMNS.index("p")
SIDE_KEY = (0, 1, 2, 3, 4)                 # object, grain, threshold, asset, era


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


def _agreement_null(sess, call, side):
    """E[agreement] when the call is REASSIGNED AT RANDOM inside its session.

    R68: the call is derived from side-INDEPENDENT geometry, so its agreeing
    and disagreeing rows are two different populations and the raw agreement
    is confounded by the session's own generation-side asymmetry.  This is the
    agreement that asymmetry ALONE produces — the number the raw agreement has
    to be read against, instead of 0.5."""
    n_all = int(np.asarray(call).size)
    if n_all == 0:
        return float("nan")
    u, gid = np.unique(sess, return_inverse=True)
    n = np.bincount(gid, minlength=u.size).astype(np.float64)
    out = 0.0
    for s in (1, -1):
        c = np.bincount(gid, weights=(call == s).astype(np.float64),
                        minlength=u.size)
        ns = np.bincount(gid, weights=(side == s).astype(np.float64),
                         minlength=u.size)
        out += float(np.sum(c * ns / np.maximum(n, 1.0)))
    return out / float(n_all)


def _row_side_tables(D, call, obj, grain, thr, rows, mrows, robust, destr,
                     do_gee=True):
    """Score a ROW-grain signed call: agreement, concentration, mirror, GEE.

    R68 (the mirror is a TRUE SIGN FLIP) and R69 (a NO-CALL is a MISS) both
    live here; the verdict column is filled from the mirror's HOLM-ADJUSTED p
    by `apply_side_verdicts` after the batch family is corrected."""
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
            # R69: EVERY row of the population is scoreable — the call either
            # agrees, opposes, or abstains, and abstention is a miss.
            n_sc = int(m.sum())
            n_sc_called = int(agree_m.sum() + dis_m.sum())
            ag = (n_ag / n_sc) if n_sc else None
            ag_called = (n_ag / n_sc_called) if n_sc_called else None
            mir = (int(dis_m.sum()) / n_sc) if n_sc else None
            wr_a = float(win[agree_m].mean()) if agree_m.any() else None
            wr_d = float(win[dis_m].mean()) if dis_m.any() else None
            # R68 — THE TRUE SIGN FLIP.  pay(row, k) = +cert when the row's own
            # side agrees with the call and -cert when it opposes it, so the
            # mirror's value is exactly -value on the SAME rows and the delta
            # is not a comparison of two disjoint populations.
            signed = np.where(agree_m, cc, np.where(dis_m, -cc, 0.0))
            ev = float(signed.sum())
            mv = -ev
            # per-SESSION value delta (estimator minus its mirror), vectorised
            # over EVERY session of the population — a session the call never
            # fires in contributes an honest 0 (R69).
            _u, gid = np.unique(sess, return_inverse=True)
            dd = 2.0 * np.bincount(gid, weights=signed, minlength=_u.size)
            won = int((dd > 0).sum())
            lost = int((dd < 0).sum())
            rows.append([obj, grain, thr, aname, ename, int(m.sum()),
                         int(fired.sum()),
                         float(fired.mean()), n_sc, n_ag, ag, mir,
                         (int(ag > mir) if (ag is not None and mir is not None)
                          else None),
                         wr_a, wr_d,
                         (wr_a / wr_d) if (wr_a is not None and wr_d)
                         else None,
                         float(cc[agree_m].mean()) if agree_m.any() else None,
                         float(cc[dis_m].mean()) if dis_m.any() else None,
                         ev, mv, ev - mv, int(_u.size),
                         B4._sign_test(won, lost),
                         "PENDING_HOLM",
                         _agreement_null(sess, k, sd), ag_called,
                         int((sd > 0).sum()), int((sd < 0).sum()), None])
            _mirror_row(mrows, obj, grain, thr, aname, ename, dd)
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
                # MINOR: `RandomState(DESTRUCTION_SEED + 3)` was re-created
                # inside a per-asset loop, so every stratum sharing the offset
                # drew the SAME permutation stream.  One seed per stratum.
                rs = np.random.RandomState(B4._seed_for(
                    "SIDE|%s|%s|%.0f|%s|%s" % (obj, grain, thr, aname, ename),
                    DESTRUCTION_SEED))
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
                    "the signed call (within session)", real, null,
                    # what a permutation can move here is the CALL'S SIGN, so
                    # that is the indicator the block's support is measured on
                    # (a block whose calls are all one way is uninformative).
                    block="SESSION", groups=ss, fire=(kk > 0), thr=thr))
    return rows


def _mirror_row(mrows, obj, grain, thr, aname, ename, dd):
    """R59 — one MIRROR_COLUMNS row from the per-session deltas, via the
    session-clustered PAIRED test.  No verdict bit is minted here."""
    mrows.append(B4.mirror_row([obj, grain, thr, aname, ename], dd))


def apply_side_verdicts(rows, mrows):
    """Fill every side row's VERDICT from its mirror row's HOLM-adjusted p.

    R59/R78: no grader reads a sweep bit, and every side verdict in this file
    is read off the same corrected test as the mirror table's."""
    by = {tuple(m[i] for i in SIDE_KEY): m for m in mrows}
    for r in rows:
        m = by.get(tuple(r[i] for i in SIDE_KEY))
        holds, why = B4.mirror_verdict(m)
        ag, mir = r[10], r[11]
        r[28] = m[23] if m is not None else None
        if ag is None:
            r[23] = "NO_CALL"
        elif holds and ag > (mir if mir is not None else 0.0):
            r[23] = ("DIRECTION_CANDIDATE (%s; agreement %.4f vs mirror %s, "
                     "null %s)" % (why, ag, B4._fmt(mir, 4),
                                   B4._fmt(r[24], 4)))
        elif m is not None and m[18] != "TESTED":
            r[23] = ("NO_TEST (%s) — an unpowered mirror is not a negative"
                     % why)
        else:
            r[23] = ("DEAD_AS_A_RULE (%s; agreement %.4f vs mirror %s, null "
                     "%s)" % (why, ag, B4._fmt(mir, 4), B4._fmt(r[24], 4)))
    return rows


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
            recs = [(cells[i], int(call[i])) for i in sel]
            called = [(c, k) for c, k in recs if k != 0]
            if len(called) < 20:
                continue
            # R69: every cell with a realised winner majority is scoreable —
            # a NO-CALL on one is a MISS, not an absence.
            scor = [(c, k) for c, k in recs if B4.winner_side(c) != 0]
            n_sc = len(scor)
            n_ag = sum(1 for c, k in scor if k != 0 and k == B4.winner_side(c))
            n_mir = sum(1 for c, k in scor
                        if k != 0 and -k == B4.winner_side(c))
            n_sc_called = sum(1 for c, k in called if B4.winner_side(c) != 0)
            ag = (n_ag / n_sc) if n_sc else None
            ag_called = (n_ag / n_sc_called) if n_sc_called else None
            mir = (n_mir / n_sc) if n_sc else None
            ev = sum(B4._cell_side_value(c, k) for c, k in recs)
            mv = sum(B4._cell_side_value(c, -k) for c, k in recs)
            by = {}
            for c, k in recs:
                by.setdefault((c["asset"], c["d8"]), []).append((c, k))
            keys = sorted(by)
            dd = np.array([sum(B4._cell_side_value(c, k)
                               - B4._cell_side_value(c, -k) for c, k in by[s])
                           for s in keys], dtype=np.float64)
            won = int((dd > 0).sum())
            lost = int((dd < 0).sum())
            wr_a = ((n_ag / n_sc_called) if n_sc_called else None)
            a_null = _agreement_null(
                np.array(["%s-%08d" % (c["asset"], c["d8"]) for c, _k in recs]),
                np.array([k for _c, k in recs]),
                np.array([B4.winner_side(c) for c, _k in recs]))
            rows.append([obj, "CELL", thr, aname, ename, len(sel),
                         len(called), len(called) / len(sel), n_sc, n_ag, ag,
                         mir,
                         (int(ag > mir) if (ag is not None and mir is not None)
                          else None),
                         wr_a, (1.0 - wr_a) if wr_a is not None else None,
                         None, None, None, ev, mv, ev - mv, len(keys),
                         B4._sign_test(won, lost), "PENDING_HOLM", a_null,
                         ag_called,
                         sum(1 for c, _k in recs if B4.winner_side(c) > 0),
                         sum(1 for c, _k in recs if B4.winner_side(c) < 0),
                         None])
            _mirror_row(mrows, obj, "CELL", thr, aname, ename, dd)
            scor = [(c, k) for c, k in scor if k != 0]
            n_sc = len(scor)
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
    """R59/R68/R78 — the grade is the CELL-grain paired mirror test, read on
    its Holm-adjusted p, with the row-grain test beside it.

    R78: the mirror selector now filters on the OBJECT.  It did not, so an
    S7_EROSION_SIDE row was eligible to decide S10's verdict — it only failed
    to collide because S10_THR is absent from EROSION_THR_GRID and the S10
    rows happened to be appended first.
    R68: the CELL-grain mirror is a true sign flip on the same cell and the
    ROW-grain one is now built as one too; both are reported."""
    def _pick(rws, grain, thr, obj="S10_SIDE"):
        return [x for x in rws if x[0] == obj and x[1] == grain
                and x[2] == thr and x[3] == "ALL" and x[4] == "FIT"]
    r = _pick(rows, "ROW", S10_THR)
    c = _pick(rows, "CELL", S10_THR)
    if not r or not c:
        return "NULL", "no S10 rows at the declared threshold"
    mc = _pick(mrows, "CELL", S10_THR)
    mr = _pick(mrows, "ROW", S10_THR)
    holds_c, why_c = B4.mirror_verdict(mc[0] if mc else None)
    holds_r, why_r = B4.mirror_verdict(mr[0] if mr else None)
    ar, ac = r[0][10], c[0][10]
    mir_c = c[0][11]
    if holds_c and ac is not None and ac > (mir_c if mir_c is not None else 0.0):
        return ("DIRECTION_CANDIDATE",
                "CELL grain at $%.0f: agreement %.4f vs mirror %s (null %s); "
                "%s. ROW grain: %s"
                % (S10_THR, ac, B4._fmt(mir_c, 4), B4._fmt(c[0][24], 4),
                   why_c, why_r))
    if mc and mc[0][18] != "TESTED":
        return ("NO_TEST",
                "CELL grain at $%.0f is UNPOWERED: %s — this is not evidence "
                "against S10, it is an absence of evidence. ROW grain: %s"
                % (S10_THR, why_c, why_r))
    return ("DEAD_AS_A_RULE",
            "CELL agreement %s (mirror %s, null %s) / ROW agreement %s at "
            "$%.0f; the paired session-clustered mirror test does not hold — "
            "CELL: %s; ROW: %s"
            % (B4._fmt(ac, 4), B4._fmt(mir_c, 4), B4._fmt(c[0][24], 4),
               B4._fmt(ar, 4), S10_THR, why_c, why_r))


# ================================================ item 3: P032 both grains
P032_COLUMNS = ("field", "grain", "reading", "asset", "era", "n", "n_clusters",
                "beta_per_sd", "se_cr1", "z_cr1", "p_cr1", "sign", "icc_rho",
                "deff", "n_eff", "clause_n_fire", "clause_precision",
                "clause_base_rate", "clause_recall", "verdict",
                "holm_rank", "holm_threshold", "holm_verdict", "p_holm")
P032_P_COL = P032_COLUMNS.index("p_cr1")
# NOTE: `reading` here is P032's own MARGINAL-vs-PARTIAL reading, not the
# D-077 SCIENCE/DEPLOYABLE reading — the name predates D-077-UPDATE and the
# committed column spelling is not churned for it (D16).  Every P032 row is a
# D-077 SCIENCE number.

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
    # ---- destruction on the day-7 clause itself, at cell grain -------------
    # R67: the real edge and the null MUST be the same estimand.  The real
    # edge's non-firing group used to EXCLUDE refused rows while the null's
    # included them imputed to 0.0 (permanently non-firing), so the two were
    # computed on different populations and the z meant nothing.  Both are
    # restricted to the cells whose prior-cell range is PRESENT, and the
    # refused cells are counted and declared instead of being folded in.
    sub_all = [c for c in cells if era_of_cell(c) == "FIT"]
    v_all = np.array([c["prev_range_usd"] for c in sub_all])
    ok = np.isfinite(v_all)
    n_refused = int((~ok).sum())
    sub = [c for c, k in zip(sub_all, ok.tolist()) if k]
    v = v_all[ok]
    y = has_seat(sub)
    sess = np.array(["%s-%08d" % (c["asset"], c["d8"]) for c in sub])
    fire = v >= P032_CLAUSE_USD
    real = (float(y[fire].mean() - y[~fire].mean())
            if fire.any() and (~fire).any() else float("nan"))
    rs = np.random.RandomState(B4._seed_for("P032|FIT|clause",
                                            DESTRUCTION_SEED))
    null = []
    for _ in range(DESTRUCTION_REPS):
        f2 = B4._shuffle_within(v, sess, rs) >= P032_CLAUSE_USD
        if f2.any() and (~f2).any():
            null.append(float(y[f2].mean() - y[~f2].mean()))
    destr.append(B4._destr_row(
        "P032_prior_cell_range>=1000", "FIT",
        "prev_phase_range_usd (within session; %d REFUSED cells excluded from "
        "BOTH the real edge and the null)" % n_refused, real, null,
        block="SESSION", groups=sess, fire=fire, thr=P032_CLAUSE_USD))
    return rows


def _p032_verdict(b, p, reading):
    if not np.isfinite(p):
        return "NO_TEST"
    d = "positive" if b > 0 else "negative"
    if p >= 0.05:
        return "NULL (%s, not significant before Holm)" % d
    return "%s beta, %s (pre-Holm p=%.2g)" % (d.upper(), reading, p)


# ================================================ R64: the max-over-deciles
def _within_group_perm(gid, rng):
    """A within-group permutation as an index array (vectorised).

    The Python-loop form (`B4._shuffle_within`) costs one numpy call per
    session; the max-lift null needs hundreds of replicates over ~10^6 rows,
    so the same permutation is built with two lexsorts instead."""
    n = int(gid.size)
    base = np.lexsort((np.arange(n), gid))
    shuf = np.lexsort((rng.random_sample(n), gid))
    perm = np.empty(n, dtype=np.int64)
    perm[base] = shuf
    return perm


def _decile_lifts(v, win, edges, base, min_n):
    out = []
    for k in range(edges.size - 1):
        lo = edges[k]
        hi = edges[k + 1] if k < edges.size - 2 else np.inf
        b = (v >= lo) & (v < hi)
        n = int(b.sum())
        if n < min_n or base <= 0:
            continue
        out.append(float(win[b].mean()) / base)
    return out


def max_lift_test(v, win, sess, edges, min_n=20, reps=MAXLIFT_REPS,
                  seed=BOOT_SEED, label=""):
    """R64 — a CONCENTRATOR grade is the MAXIMUM of ten decile lifts, and the
    max of ten noisy ratios clears a fixed 1.25x bar under the null far more
    often than 5% of the time.  This is that grade's missing test:

      * a NULL DISTRIBUTION FOR THE MAXIMUM, session-clustered (the carrying
        value is permuted WITHIN the session, the same exchangeable block the
        destruction uses, so the null keeps every session-level effect and
        destroys only the within-session ordering);
      * a session-cluster BOOTSTRAP CI for the observed maximum;
      * a p that enters the batch's ONE Holm family.
    """
    v = np.asarray(v, dtype=np.float64)
    win = np.asarray(win, dtype=np.float64)
    ok = np.isfinite(v)
    v, win, sess = v[ok], win[ok], np.asarray(sess)[ok]
    out = {"max_lift": float("nan"), "p_null": float("nan"),
           "null_mean": float("nan"), "null_p95": float("nan"),
           "lo": float("nan"), "hi": float("nan"), "n_reps": 0,
           "n": int(v.size), "n_sessions": 0, "label": label}
    if v.size < 200 or edges.size < 3:
        return out
    base = float(win.mean())
    obs = _decile_lifts(v, win, edges, base, min_n)
    if not obs:
        return out
    out["max_lift"] = float(max(obs))
    uniq, gid = np.unique(sess, return_inverse=True)
    out["n_sessions"] = int(uniq.size)
    rng = np.random.RandomState(seed)
    null = []
    for _ in range(int(reps)):
        l = _decile_lifts(v[_within_group_perm(gid, rng)], win, edges, base,
                          min_n)
        if l:
            null.append(max(l))
    if null:
        n = np.array(null, dtype=np.float64)
        out["n_reps"] = int(n.size)
        out["null_mean"] = float(n.mean())
        out["null_p95"] = float(np.percentile(n, 95))
        # the +1 form: a permutation p is never zero
        out["p_null"] = float((1.0 + float((n >= out["max_lift"]).sum()))
                              / (1.0 + n.size))
    # session-cluster bootstrap CI of the observed maximum
    idx_by = [np.nonzero(gid == g)[0] for g in range(uniq.size)]
    if uniq.size >= 20:
        rng2 = np.random.RandomState(seed + 1)
        bs = []
        for _ in range(100):
            take = np.concatenate([idx_by[g] for g in
                                   rng2.randint(0, uniq.size, uniq.size)])
            l = _decile_lifts(v[take], win[take], edges,
                              float(win[take].mean()), min_n)
            if l:
                bs.append(max(l))
        if len(bs) >= 20:
            out["lo"] = float(np.percentile(bs, 2.5))
            out["hi"] = float(np.percentile(bs, 97.5))
    return out


_MAXLIFT = {}                              # (object, era) -> the test dict


def _maxlift_robust(robust, obj, era, t, n_fire):
    """The max-lift test as a row of the batch's one Holm family.

    The SE columns are REFUSED (nan) rather than filled with something else:
    this row is a permutation test, it has no sandwich SE, and a column is
    never given a value that is not what its name says."""
    _MAXLIFT[(obj, era)] = t
    robust.append([obj, era, "max_decile_winner_rate_lift", "SESSION",
                   t["n"], t["n_sessions"], int(n_fire), t["max_lift"],
                   float("nan"), float("nan"), float("nan"), float("nan"),
                   t["p_null"], float("nan"), float("nan"), float("nan"),
                   ("max lift %s [95%% CI %s, %s]; null mean %s, null p95 %s, "
                    "permutation p %s over %d replicates"
                    % (B4._fmt(t["max_lift"], 2), B4._fmt(t["lo"], 2),
                       B4._fmt(t["hi"], 2), B4._fmt(t["null_mean"], 2),
                       B4._fmt(t["null_p95"], 2), B4._fmt(t["p_null"], 4),
                       t["n_reps"]))])
    return robust


# ============================================== item 4: P033 runway x rv
P033_COLUMNS = ("form", "control_band", "asset", "era", "decile", "lo", "hi",
                "n", "n_share", "n_winners", "winner_share", "winner_rate",
                "base_winner_rate", "winner_rate_lift", "conc_ratio",
                "mean_close_usd", "cond_close_usd", "mean_peak_usd",
                "frac_ge_1000_close", "n_sessions", "reading")


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
              for reading in (READINGS if aname == "ALL" else ("SCIENCE",)):
                for ename in ERAS:
                    m = (cmask & (D["era"] == ename) & np.isfinite(v)
                         & ((D["asset"] == aname) if aname != "ALL"
                            else np.ones(v.size, bool))
                         & (deployable_mask(D) if reading == "DEPLOYABLE"
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
                                     len(set(D["session_key"][m][b].tolist())),
                                     reading])
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
            rs = np.random.RandomState(B4._seed_for("P033|%s|%s" % (form, ename),
                                                    DESTRUCTION_SEED))
            null = []
            for _ in range(DESTRUCTION_REPS):
                f2 = B4._shuffle_within(v[m], cl, rs) >= thr
                if f2.any() and (~f2).any():
                    null.append(float(win[f2].mean() - win[~f2].mean()))
            destr.append(B4._destr_row("P033_%s_top_decile" % form, ename,
                                       "the product (within session)", real,
                                       null, block="SESSION", groups=cl,
                                       fire=fire, thr=thr))
            # ---- R64: the null for the MAX decile lift, and its CI ---------
            t = max_lift_test(v[m], win, cl, edges,
                              seed=B4._seed_for("MAXLIFT|P033|%s|%s"
                                                % (form, ename), BOOT_SEED),
                              label="P033_%s" % form)
            _maxlift_robust(robust, "P033_%s_max_decile" % form, ename, t,
                            int(fire.sum()))
    return rows


def grade_p033(rows, robust):
    """P033 is a magnitude object: CONCENTRATOR is its ceiling (no mirror).

    R64: the grade is a MAX-OVER-TEN-DECILES statistic, so the fixed 1.25x bar
    is not a test on its own — the max of ten noisy ratios clears it routinely
    under the null.  The grade now REQUIRES the session-clustered max-lift null
    to reject at the Holm-adjusted level as well, and quotes the null's own
    mean and 95th percentile so the bar is visible.  (`robust` used to be taken
    and never read; it carries the test.)"""
    top = [r for r in rows if r[0] == "PRODUCT_runway_x_rv1800"
           and r[1] == "ALL" and r[2] == "ALL" and r[3] == "FIT"
           and r[20] == "SCIENCE"]
    if not top:
        return "NULL", "no decile table"
    lift = max((r[13] for r in top if r[13] is not None), default=None)
    obj = "P033_PRODUCT_runway_x_rv1800_max_decile"
    mx = [r for r in robust if r[0] == obj and r[1] == "FIT"]
    mxr = mx[0] if mx else None
    t = _MAXLIFT.get((obj, "FIT"))
    p_holm = (mxr[20] if (mxr is not None and len(mxr) > 20) else float("nan"))
    null_txt = (("max lift %s [95%% CI %s, %s] vs a session-clustered null "
                 "whose own mean is %s and 95th percentile %s; permutation "
                 "p=%s, Holm p=%s"
                 % (B4._fmt(t["max_lift"], 2), B4._fmt(t["lo"], 2),
                    B4._fmt(t["hi"], 2), B4._fmt(t["null_mean"], 2),
                    B4._fmt(t["null_p95"], 2), B4._fmt(t["p_null"], 4),
                    B4._fmt(p_holm, 4)))
                if t is not None else "no max-lift null computed")
    sig = bool(np.isfinite(p_holm) and p_holm < 0.05)
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
    if lift >= CONCENTRATOR_MIN and sig:
        return ("CONCENTRATOR",
                "top-decile winner-rate lift %.2fx pooled; best WITHIN-runway-"
                "band decile lift %s (band %s, decile %s, n>=500) — the "
                "product is not the runway wearing a new hat. %s. FEATURE "
                "CANDIDATE ONLY: a feasibility object with no mirror can never "
                "be an entry rule"
                % (lift, B4._fmt(within[13], 2) if within else ".",
                   within[1] if within else "-",
                   within[4] if within else "-", null_txt))
    if lift >= CONCENTRATOR_MIN:
        return ("NULL_MAX_NOT_SIGNIFICANT",
                "the max decile lift %.2fx clears the %.2fx bar but NOT its "
                "own null: %s — a max over ten deciles clears a fixed bar "
                "routinely under the null (R64)"
                % (lift, CONCENTRATOR_MIN, null_txt))
    return "NULL", ("winner-rate lift %.2fx < %.2f (%s)"
                    % (lift, CONCENTRATOR_MIN, null_txt))


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


def veto_regrade(D, rows, srows, robust=None):
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
    dm = deployable_mask(D)                # R77: the D-077 exposure of this pool
    n_news_takes = 0
    for t in idx.tolist():
        r = _row_dict(D, t)
        core_ok = all(P7.terms(r).values())
        if core_ok and not dm[t]:
            n_news_takes += 1
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
        # R65: the pooled verdict had NO significance requirement at all —
        # `RETAIN` was returned on d > 0.  The per-session replay deltas are a
        # PAIRED, session-clustered sample (the same session is replayed with
        # and without the veto), so they get the same test the mirror law uses,
        # with its power floor: below it the answer is NO_TEST, not RETAIN.
        pt = MC.mirror_paired(dd)
        # R65 again: five of the seven sessions V2/V3 were FITTED on are in
        # this population, so the pooled statistic is 5/7 IN-SAMPLE.
        n_sess_here = len({(o["asset"], o["date8"]) for o in vt + st})
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
            "sign_test_p_diagnostic": B4._sign_test(won, lost),
            # the test of record for the replay delta (R65)
            "replay_delta_n_clusters": pt["n_sessions"],
            "replay_delta_mean_usd": pt["mean_delta"],
            "replay_delta_se_usd": pt["se"],
            "replay_delta_t": pt["t"],
            "replay_delta_p": pt["p"],
            "replay_delta_mde80_usd": pt["mde_80"],
            "replay_delta_test_verdict": pt["verdict"],
            "min_clusters_for_a_test": MC.MIRROR_MIN_SESSIONS,
            "in_sample_sessions": len([d for d in STUDY_D8
                                       if d in _V2V3_FIT_D8]),
            "in_sample_session_frac": (float(len([d for d in STUDY_D8
                                                  if d in _V2V3_FIT_D8]))
                                       / max(len(STUDY_D8), 1)),
            "n_session_asset_clusters": n_sess_here,
            "reading": "SCIENCE (D-077-UPDATE(3)) — see "
                       "n_core_takes_in_news_window",
            "n_core_takes_in_news_window": int(n_news_takes),
            "DP_vetoed_seat_spenders": summ.get("DP_vetoed_seat_spenders", 0),
            "REPLAY_vetoed_seat_spenders":
                summ.get("REPLAY_vetoed_seat_spenders", 0),
            "DP_vetoed_seat_value_usd":
                summ.get("DP_vetoed_seat_value_usd", 0.0),
            "replay_inert": summ.get("replay_inert", 0),
        }
        out["verdict"] = _veto_verdict(out)
        if robust is not None:
            robust.append(["VETO_%s_replay_delta" % fam, "STUDY_7",
                           "replay_delta_usd", "SESSION_ASSET",
                           int(idx.size), pt["n_sessions"], len(vt),
                           pt["mean_delta"], float("nan"), float("nan"),
                           pt["se"], pt["t"], pt["p"], float("nan"),
                           float("nan"), float("nan"), out["verdict"][:120]])
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
    """R65 — a verdict with an inference in it, and its in-sample fraction.

    `RETAIN on d > 0` was not a criterion: it had no p, no CI and no power
    statement, and 5 of the 7 sessions it is computed on are the sessions V2
    and V3 were FITTED on.  Both facts are now in the verdict string."""
    tail = (" [%d/%d sessions IN-SAMPLE (V2/V3 were fitted on study sessions "
            "1-5); %d session-asset clusters; paired replay-delta test: %s, "
            "mean %+.2f, se %s, p %s, mde80 %s]"
            % (o["in_sample_sessions"], len(STUDY_D8),
               o["n_session_asset_clusters"], o["replay_delta_test_verdict"],
               o["replay_delta_mean_usd"], B4._fmt(o["replay_delta_se_usd"], 2),
               B4._fmt(o["replay_delta_p"], 4),
               B4._fmt(o["replay_delta_mde80_usd"], 2)))
    if o["replay_inert"]:
        return ("REPLAY-INERT — the family touches no seat-spender in either "
                "reading, so it cannot move the money whatever its pooled row "
                "statistic says (ERA_NOTES §67)" + tail)
    d = o["replay_delta_usd"]
    sig = bool(np.isfinite(o["replay_delta_p"]) and o["replay_delta_p"] < 0.05
               and o["replay_delta_test_verdict"] == "TESTED")
    if d > 0 and sig:
        return ("RETAIN — pooled replay delta %+.2f, significant as a paired "
                "session-clustered test" % d + tail)
    if d > 0:
        return ("RETAIN_UNPROVEN — pooled replay delta %+.2f with NO "
                "significant paired test behind it (%d improved / %d hurt)"
                % (d, o["sessions_improved"], o["sessions_hurt"]) + tail)
    if d < 0 and sig:
        return ("DROP — pooled replay delta %+.2f, significant against it"
                % d + tail)
    return ("DROP_UNPROVEN — pooled replay delta %+.2f over seven sessions "
            "(%d improved / %d hurt), %d D-021 winners refused, no "
            "significant test either way"
            % (d, o["sessions_improved"], o["sessions_hurt"],
               o["n_winners_vetoed"]) + tail)


# ================================= item 6: the S7/S8 event-statistic censuses
EVENT_COLUMNS = ("stat", "asset", "era", "decile", "lo", "hi", "n", "n_share",
                 "n_winners", "winner_share", "winner_rate",
                 "base_winner_rate", "winner_rate_lift", "conc_ratio",
                 "mean_close_usd", "cond_close_usd", "mean_peak_usd",
                 "n_sessions", "verdict", "reading")


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
          for reading in (READINGS if aname == "ALL" else ("SCIENCE",)):
            for ename in ERAS:
                m = ((D["era"] == ename) & np.isfinite(v)
                     & ((D["asset"] == aname) if aname != "ALL"
                        else np.ones(v.size, bool))
                     & (deployable_mask(D) if reading == "DEPLOYABLE"
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
                                 "-", reading])
                if aname == "ALL":
                    # R64: the verdict is the MAXIMUM of ten decile lifts, so
                    # it is graded against a session-clustered null for the
                    # MAXIMUM (with a CI and Holm membership), never against a
                    # bare 1.25x bar.
                    t = max_lift_test(
                        vv, win, D["session_key"][m], edges,
                        seed=B4._seed_for("MAXLIFT|%s|%s|%s"
                                          % (stat, ename, reading), BOOT_SEED),
                        label="EVENT_%s" % stat)
                    if reading == "SCIENCE":
                        _maxlift_robust(robust, "EVENT_%s_max_decile" % stat,
                                        ename, t, int(m.sum()))
                    ok_bar = (best is not None and best >= CONCENTRATOR_MIN)
                    ok_null = bool(np.isfinite(t["p_null"])
                                   and t["p_null"] < 0.05)
                    txt = ("CONCENTRATOR_CANDIDATE (best decile lift %s; %s)"
                           if (ok_bar and ok_null) else
                           ("NULL_MAX_NOT_SIGNIFICANT (best decile lift %s "
                            "clears the bar but not its own null; %s)"
                            if ok_bar else "NULL (best decile lift %s; %s)"))
                    txt = txt % (B4._fmt(best, 2),
                                 "null mean %s, null p95 %s, permutation p %s"
                                 % (B4._fmt(t["null_mean"], 2),
                                    B4._fmt(t["null_p95"], 2),
                                    B4._fmt(t["p_null"], 4)))
                    for i in range(len(rows) - 1, -1, -1):
                        if (rows[i][0] != stat or rows[i][1] != aname
                                or rows[i][2] != ename
                                or rows[i][19] != reading):
                            break
                        rows[i][18] = txt
                # ---- GEE on the continuous statistic ------------------------
                # (SCIENCE only: the DEPLOYABLE pass re-reads the same tests on
                # a subset and must not double-count in the Holm family.)
                if aname != "ALL" or reading != "SCIENCE":
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
                rs = np.random.RandomState(B4._seed_for(
                    "EVENT|%s|%s|%s" % (stat, ename, reading),
                    DESTRUCTION_SEED))
                null = []
                for _ in range(DESTRUCTION_REPS):
                    f2 = B4._shuffle_within(vv, cl, rs) >= thr
                    if f2.any() and (~f2).any():
                        null.append(float(win[f2].mean() - win[~f2].mean()))
                destr.append(B4._destr_row("EVENT_%s_top_decile" % stat, ename,
                                           "%s (within session)" % stat, real,
                                           null, block="SESSION", groups=cl,
                                           fire=fire, thr=thr))
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
    A_("* D-077-UPDATE(3): every number below is a **SCIENCE** reading unless "
       "its row says DEPLOYABLE. %d of %d rows sit inside the +/-%.0f-minute "
       "restricted window around a scheduled release and cannot be entered by "
       "a compliant policy (R77)."
       % (int((~deployable_mask(D)).sum()), int(D["dec_sec"].size),
          NEWS_WINDOW_MIN))
    A_("* R59: no verdict in this file reads a sweep bit. Every directional "
       "verdict is the session-clustered PAIRED mirror test on its "
       "Holm-adjusted p, with NO_TEST below %d sessions."
       % MC.MIRROR_MIN_SESSIONS)
    A_("* runtime %.1fs; pins %s"
       % (elapsed, "HELD" if not pins else "MOVED: " + "; ".join(pins)))
    A_("")

    A_("## 1. THE ROLLING SEAT-MODEL REFIT (the headline)")
    A_("")
    A_("Four decision procedures, one target (the cell holds >= 1 D-021 "
       "winner), the same test cells, PAIRED session-cluster bootstrap:")
    A_("")
    A_("| asset | scope | grain | model | n_test | base | AUC | 95% CI | "
       "dAUC vs cell-open | paired 95% CI | p | p_Holm | verdict |")
    A_("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in res["auc"]:
        if r[0] != "ALL":
            continue
        A_("| %s | %s | %s | %s | %d | %s | **%s** | [%s, %s] | %s | [%s, %s] "
           "| %s | %s | %s |"
           % (r[0], r[1], r[2], r[3], r[5], _fmt(r[6], 3), _fmt(r[7], 4),
              _fmt(r[8], 3), _fmt(r[9], 3), _fmt(r[12], 4), _fmt(r[13], 4),
              _fmt(r[14], 4), _fmt(r[15], 4), _fmt(r[21], 4), r[16]))
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
    A_("R60: these p-values are IN the batch's one Holm family — the "
       "docstring asserted a correction the numbers had never had.")
    A_("")
    A_("| model | grain | term | beta | se_CR1 | z | p | p_Holm | Holm | "
       "imputed |")
    A_("|---|---|---|---|---|---|---|---|---|---|")
    for r in res["model"]:
        if r[2] != "ALL" or r[3] != "FIT":
            continue
        A_("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %d |"
           % (r[0], r[1], r[4], _fmt(r[5], 4), _fmt(r[8], 4), _fmt(r[9], 2),
              _fmt(r[10], 5), _fmt(r[20], 5), r[19], r[16]))
    A_("")

    A_("## 2. S10 SIDE GEOMETRY (d_POC sign + in_VA) UNDER THE MIRROR LAW")
    A_("")
    A_("R68: the ROW-grain mirror is a TRUE SIGN FLIP (+cert when the row's "
       "own side agrees with the call, -cert when it opposes), so the two arms "
       "are the same rows and not two disjoint populations. R69: a NO-CALL is "
       "a MISS, so `agreement` is over EVERY row of the population — read it "
       "against `null` (the agreement the session's own generation-side "
       "asymmetry produces), never against 0.5.")
    A_("")
    A_("| grain | thr $ | era | n | called | scoreable | agreement | mirror | "
       "null | agree(called) | delta value $ | sign p (diag) | p_Holm | "
       "verdict |")
    A_("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in res["s10"]:
        if r[3] != "ALL" or r[0] != "S10_SIDE":
            continue
        A_("| %s | %s | %s | %d | %d | %d | %s | %s | %s | %s | %s | %s | %s | "
           "%s |"
           % (r[1], _fmt(r[2], 0), r[4], r[5], r[6], r[8], _fmt(r[10], 4),
              _fmt(r[11], 4), _fmt(r[24], 4), _fmt(r[25], 4), _fmt(r[20], 0),
              _fmt(r[22], 4), _fmt(r[28], 5), r[23]))
    A_("")
    A_("### the mirror law at era scale — the PAIRED session-clustered test")
    A_("")
    A_("| object | grain | thr | era | sessions | won | tied | lost | sweep | "
       "mean delta $ | se | t | p | p_Holm | mde80 $ | verdict | Holm |")
    A_("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in res["mirror"]:
        if r[3] != "ALL" or r[0] != "S10_SIDE":
            continue
        A_("| %s | %s | %s | %s | %d | %d | %d | %d | %d | %s | %s | %s | %s | "
           "%s | %s | **%s** | %s |"
           % (r[0], r[1], _fmt(r[2], 0), r[4], r[5], r[6], r[7], r[8], r[9],
              _fmt(r[10], 0), _fmt(r[12], 1), _fmt(r[13], 2), _fmt(r[14], 5),
              _fmt(r[23], 5), _fmt(r[16], 0), r[18], r[22]))
    A_("")
    A_("VERDICT S10 SIDE: **%s** — %s" % res["grade_s10"])
    A_("")

    A_("## 3. P032 PRIOR_CELL_TRAVEL — THE SIGN CONTRADICTION")
    A_("")
    A_("| field | grain | reading | era | n | beta/SD | z | p | p_Holm | Holm "
       "| sign | clause fires | clause precision | base rate | clause recall |")
    A_("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in res["p032"]:
        if r[3] != "ALL":
            continue
        A_("| %s | %s | %s | %s | %d | %s | %s | %s | %s | %s | **%s** | %s | "
           "%s | %s | %s |"
           % (r[0], r[1], r[2], r[4], r[5], _fmt(r[7], 4), _fmt(r[9], 2),
              _fmt(r[10], 5), _fmt(r[23], 5), r[22], r[11],
              (r[15] if r[15] is not None else "-"),
              _fmt(r[16], 3), _fmt(r[17], 3), _fmt(r[18], 3)))
    A_("")

    A_("## 4. P033 FEASIBILITY_IS_RUNWAY_TIMES_VOL (census-first)")
    A_("")
    A_("| form | control | decile | n | winner rate | lift | conc ratio | "
       "mean close $ | cond close $ |")
    A_("|---|---|---|---|---|---|---|---|---|")
    for r in res["p033"]:
        if (r[2] != "ALL" or r[3] != "FIT" or r[1] != "ALL"
                or r[20] != "SCIENCE"):
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
                or r[2] != "ALL" or r[3] != "FIT" or r[4] not in (0, 4, 8, 9)
                or r[20] != "SCIENCE"):
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
    A_("R64: the verdict is the MAX of ten decile lifts and it is graded "
       "against a session-clustered null for THAT MAXIMUM, not against a bare "
       "1.25x bar.")
    A_("")
    for r in res["events"]:
        if r[1] != "ALL" or r[19] != "SCIENCE" or r[3] != max(
                (x[3] for x in res["events"]
                 if x[0] == r[0] and x[1] == "ALL" and x[2] == r[2]
                 and x[19] == "SCIENCE"),
                default=-1):
            continue
        A_("| %s | %s | %d | %s | %s | %s | %s | %s |"
           % (r[0], r[2], r[6], _fmt(r[10], 4), _fmt(r[11], 4),
              _fmt(r[12], 2), _fmt(r[14], 0), r[18]))
    A_("")
    A_("### the erosion SIDE claim under the mirror law")
    A_("")
    A_("| thr | era | called | agreement | mirror | delta value $ | won/lost | "
       "verdict |")  # noqa: E501
    A_("|---|---|---|---|---|---|---|---|")
    A_("R68 applies here too: this is the ROW form and it is a true sign flip "
       "now. CC-M2-21.5's erosion-side verdict was read off the OLD row form.")
    A_("")
    for r in res["s10"]:
        if r[0] != "S7_EROSION_SIDE" or r[3] != "ALL":
            continue
        mm = [m for m in res["mirror"] if m[0] == "S7_EROSION_SIDE"
              and m[1] == r[1] and m[2] == r[2] and m[3] == "ALL"
              and m[4] == r[4]]
        A_("| %s | %s | %d | %s | %s | %s | %s | %s |"
           % (_fmt(r[2], 0), r[4], r[6], _fmt(r[10], 4), _fmt(r[11], 4),
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
       "the null**, i.e. the field carries information against the claim; "
       "**DEGENERATE_NULL = the permutation block cannot produce a null and "
       "no z is emitted** (R66).")
    A_("")

    A_("## 8. ONE HOLM FAMILY OVER THE WHOLE BATCH (%d tests)"
       % res.get("n_family", 0))
    A_("")
    A_("R61: the family spans every table that publishes a test — the GEEs, "
       "the model coefficients, the paired mirror tests, the paired dAUC "
       "bootstrap, P032's betas, the max-decile-lift nulls and the V2/V3 "
       "replay test. It used to be two disjoint families with four more "
       "tables of p-values outside both.")
    A_("")
    A_("| object | era | metric | n | clusters | beta | se_CR1 | z | p | "
       "p_Holm | n_eff | Holm |")
    A_("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in res["robust"]:
        if r[19] != "HOLM_SIGNIFICANT":
            continue
        A_("| %s | %s | %s | %d | %d | %s | %s | %s | %s | %s | %s | %s |"
           % (r[0], r[1], r[2], r[4], r[5], _fmt(r[7], 4), _fmt(r[10], 4),
              _fmt(r[11], 2), _fmt(r[12], 6), _fmt(r[20], 6), _fmt(r[15], 0),
              r[19]))
    A_("")
    A_("(only the Holm-significant GEE rows are rendered; BATCH5_ROBUST.tsv "
       "carries every test, and S10_MIRROR / SEAT_ROLLING_MODEL / "
       "SEAT_ROLLING_AUC / P032_GRAINS carry their own Holm columns from the "
       "same family.)")
    return "\n".join(L) + "\n"


# ====================================================================== build
def build(workers=6, limit_sessions=None, want_events=True):
    t0 = time.time()
    MC.verify_spec(force=True)
    _MAXLIFT.clear()                       # no stale test across two builds
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
    res["veto"], res["veto_sessions"] = veto_regrade(D, [], [], robust)
    MC.hb("batch5: V2/V3 pooled re-grade done")
    res["events"] = (event_rows(D, [], robust, destr) if want_events else [])
    if want_events:
        erosion_side_rows(D, side_rows, mir_rows, robust, destr)
    res["s10"] = side_rows
    res["mirror"] = mir_rows
    # R61 — ONE family across every table of this batch that publishes a test.
    res["n_family"] = B4._holm_family(
        [(robust, B4.ROBUST_P_COL, len(B4.ROBUST_COLUMNS)),
         (mir_rows, MIRROR_P_COL, len(MIRROR_COLUMNS)),
         (res["model"], MODEL_P_COL, len(MODEL_COLUMNS)),
         (res["auc"], AUC_P_COL, len(AUC_COLUMNS)),
         (res["p032"], P032_P_COL, len(P032_COLUMNS))])
    # every side verdict is read off the CORRECTED mirror p (R59/R78)
    apply_side_verdicts(side_rows, mir_rows)
    apply_auc_verdicts(res["auc"])
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
                     "every model; delta_p_boot is IN the batch's one Holm "
                     "family and p_holm is its adjusted value (R62)",
                     "reading = SCIENCE (D-077-UPDATE(3)): these AUCs do not "
                     "exclude the restricted news window; batch 4's "
                     "SEAT_AUC.tsv carries the DEPLOYABLE split of the same "
                     "seat object (R77)"])
    W(os.path.join(OUT_DIR, "SEAT_ROLLING_MODEL.tsv"), SECTION, phash,
      list(MODEL_COLUMNS), res["model"],
      extra=extra + ["betas are per STANDARD DEVIATION of the feature",
                     "n_imputed_term = REFUSED values this fit passed off as "
                     "the column mean (R71); p_holm is the adjusted p over the "
                     "ONE batch family (R60)"])
    W(os.path.join(OUT_DIR, "SEAT_ROLLING_BANDS.tsv"), SECTION, phash,
      list(BAND_COLUMNS), res["bands"], extra=extra)
    W(os.path.join(OUT_DIR, "S10_SIDE.tsv"), SECTION, phash,
      list(SIDE_COLUMNS), res["s10"],
      extra=extra + ["in_VA = -1 is REFUSED (a missing VA edge) and never "
                     "calls — sections.s10_profile's V1.1 ruling, obeyed",
                     "R69: agreement counts a NO-CALL as a MISS (the whole "
                     "population is the denominator); agreement_called_only is "
                     "the old number and agreement_null is the agreement the "
                     "session's generation-side asymmetry produces on its own",
                     "R68: est/mirror/delta_value_usd are a TRUE SIGN FLIP on "
                     "the same rows, not two disjoint row sets",
                     "sign_test_p_diagnostic is a DIAGNOSTIC; the test of "
                     "record is the paired mirror test, carried here as "
                     "mirror_p_holm and used by the verdict (R62)"])
    W(os.path.join(OUT_DIR, "S10_MIRROR.tsv"), SECTION, phash,
      list(MIRROR_COLUMNS), res["mirror"],
      extra=extra + ["R59: the ERA-SCALE mirror law is the session-clustered "
                     "PAIRED test (m2_common.mirror_paired) graded on p_holm; "
                     "sweep_clean (lost == 0 and won > 0) is the STUDY-ROUND "
                     "diagnostic and gates nothing",
                     "verdict = NO_TEST below %d sessions — an unpowered cell "
                     "is not a negative; mde_80_usd is what it could have "
                     "detected" % MC.MIRROR_MIN_SESSIONS])
    W(os.path.join(OUT_DIR, "P032_GRAINS.tsv"), SECTION, phash,
      list(P032_COLUMNS), res["p032"],
      extra=extra + ["MARGINAL vs PARTIAL_GIVEN_RV1800 is the whole point: "
                     "CC-M2-18.1's negative sign was read inside a model that "
                     "already carried rv1800",
                     "every p_cr1 here is IN the batch's one Holm family and "
                     "p_holm is its adjusted value (R61/R62)"])
    W(os.path.join(OUT_DIR, "P033_DECILES.tsv"), SECTION, phash,
      list(P033_COLUMNS), res["p033"],
      extra=extra + ["decile cuts are computed on the FIT pool and APPLIED to "
                     "the GATE echo; control_band = the raw P025 runway band",
                     "reading = the D-077 split (SCIENCE = all rows, "
                     "DEPLOYABLE = the +/-%.0f min restricted window removed); "
                     "the CONCENTRATOR grade additionally requires the "
                     "max-decile-lift null in BATCH5_ROBUST.tsv (R64/R77)"
                     % NEWS_WINDOW_MIN])
    W(os.path.join(OUT_DIR, "VETO_POOLED.tsv"), SECTION, phash,
      list(VETO_COLUMNS), res["veto"],
      extra=extra + ["the pre-veto pool is the frozen five-term CORE "
                     "(e1d7_policy.terms) on every candidate of the seven E1 "
                     "study sessions",
                     "R65: the verdict carries the PAIRED session-clustered "
                     "replay-delta test (NO_TEST below %d clusters) and the "
                     "IN-SAMPLE fraction — V2/V3 were fitted on study sessions "
                     "1-5 and re-graded on 1-7" % MC.MIRROR_MIN_SESSIONS])
    W(os.path.join(OUT_DIR, "VETO_SESSIONS.tsv"), SECTION, phash,
      list(VSESS_COLUMNS), res["veto_sessions"], extra=extra)
    W(os.path.join(OUT_DIR, "EVENT_STATS.tsv"), SECTION, phash,
      list(EVENT_COLUMNS), res["events"],
      extra=extra + ["the verdict is a MAX-OVER-DECILES statistic graded "
                     "against a session-clustered null for the MAXIMUM "
                     "(BATCH5_ROBUST.tsv, metric max_decile_winner_rate_lift), "
                     "never against a bare %.2fx bar (R64)" % CONCENTRATOR_MIN,
                     "reading = the D-077 split (R77)"])
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
                   "grade_S10_SIDE_why": res["grade_s10"][1],
                   "grade_P033": res["grade_p033"][0],
                   "grade_P033_why": res["grade_p033"][1],
                   "n_holm_family_tests": res["n_family"],
                   # R77: the D-077 exposure of this population
                   "news_window_min": NEWS_WINDOW_MIN,
                   "n_rows_in_news_window":
                       int((~deployable_mask(D)).sum()),
                   "n_rows_release_minutes_refused":
                       int((~np.isfinite(D["mins_to_release"])).sum()),
                   "reading": "SCIENCE unless a row says DEPLOYABLE "
                              "(D-077-UPDATE(3))",
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
