#!/usr/bin/python3
"""PORT M2 — CENSUS BATCH 3: P025 / P023 / P024 / P007 name->count censuses.

CC-M2-12.4 (BINDING): "NY-INVARIANT STRUCK -> P025 RUNWAY_TO_BINDING_EXIT: the
86/86 'NY' concentration was proxying runway to the phase-close seat ... CENSUS
BATCH 3 ORDERED: P025 (the structural candidate), P023
ABSORPTION_TWO_STREAM_ENTRY (68-10 day-3), P024 REFAIL_REVERSION, P007-as-entry.
Same discipline; concentrator-vs-rule vocabulary."

THE DISCIPLINE (restated from p001/p020 so this file can be read alone)
every detector is STRICTLY CAUSAL and built only from committed pattern_lib
frame fields; the population is every candidate of the frozen v3 roster on
every FIT session of all three assets, with 2025 as an EVAL-ONLY GATE echo;
BOTH CC-M1-8 certificate readings are reported everywhere; per-year stability,
per-term marginals and MECHANISM DESTRUCTION (each term shuffled within its own
session) are mandatory; inference is GEE with the Liang-Zeger sandwich
clustered on SESSION (CR1) plus Kish DEFF/n_eff; and the p-values are corrected
Holm-Bonferroni over THE WHOLE BATCH, not once per pattern.

THE DETECTORS (PATTERN_LEDGER.tsv `sheet_fields`, verbatim, + the repairs the
E1 day-3 post-mortem specified)

P025 RUNWAY_TO_BINDING_EXIT — the structural candidate, and the reason batch 3
  exists.  The ledger: "S13 exit_default (phase_close vs session_close); S3
  runway to that exit; S1 phase_dec as a CONTROL, never the variable."
  It is censused as a CONDITIONING OBJECT first and a detector second:
    * the RUNWAY BAND TABLE — winner rate, concentration ratio and both
      certificate readings by (asset, era, runway band).  The concentration
      ratio is P020's own artefact control: (winners in the cell / winners in
      the stratum) / (candidates in the cell / candidates in the stratum), so
      a band that merely holds more candidates cannot look like a pattern.
    * THE DECIDING TABLE — phase_dec WITHIN each runway band, plus the
      ADJUSTED GEE the question actually asks: does `phase == NY` still carry
      a certificate (or a winner) after the runway is in the model?  Both the
      unadjusted and the runway-adjusted coefficient are reported side by
      side, on the dollar metric AND on the D-021 winner indicator (the 86/86
      claim was a WINNER claim), and the symmetric test (runway adjusted for
      phase) is reported next to them.
  TWO READINGS OF THE RUNWAY, because D15 says the nominal one is wrong on
  holiday tapes:
    A_nominal   runway_phase_sec — phase_close_sec - dec_sec (what every sheet
                prints).
    B_observed  runway_binding_sec — min(nominal, observed_close - dec_sec),
                the m0 receipt's last two-sided second.  On 2021-07-05 the HG
                tape stops at 71,354s while the sheets compute to 82,799s.
  The detector form (for the CC-M2-9.1 grading only) is the ledger's own
  sentence "the $1,000 bar needs HOURS": fire = runway >= 3h.

P023 ABSORPTION_TWO_STREAM_ENTRY — censused as an ENTRY object in the REPAIRED
  form the ledger specifies ("opposed 5m aggression at magnitude, a
  relative-OR-absolute volume floor, and a PRICE-FAILURE confirmation"):
    T1 OPPOSED   sign(S8 5m sflow) == -side and |sflow| / vol >= 5%
    T2 FLOOR     the fitted parameter, censused in THREE readings:
                   ABS  5m vol >= 500            (the day-1/2 fitted floor)
                   REL  5m vol / phase vol >= 8% (the scale-free form)
                   OR   either                   (the ledger's repair)
    T3 LIVEBOOK  S8 60s n >= 2 and vol >= 2 (P004's dead-book veto, inverted)
    T4 PRICEFAIL the opposed aggression has NOT extended the extreme the trade
                 fades within the last minute: extreme_age_sec >= 60.
  The through-book SIDE term is absent by ruling — its sign is STRUCK (E1D3-F4)
  — and it is also NOT censusable at era scale (see NOT CENSUSABLE below).

P024 REFAIL_REVERSION — the day-3 discretionary override, "direction confirmed,
  magnitude failed".  Terms from the ledger's `sheet_fields`:
    T1 REFAIL    two causal ZigZag pivots of the FADED type <= 300s apart and
                 <= 1 tick apart (pattern_lib V2 refail_gap_sec/refail_dist_usd)
    T2 EXPANDED  S2 day_type_so_far == EXPANDED (= range_so_far >= range_hat)
    T3 ROOM      S3 ext_needed_usd <= $450
    T4 FLOW      S8 phase AND 5m sflow both concordant with the trade at >= 5%
    T5 CONFLUENCE (reading B only) >= 2 distinct KEPT level families within 2
                 ticks of the refail price
  Its headline is NOT the mean certificate but the DIRECTION/MAGNITUDE SPLIT:
  P024_MAGNITUDE.tsv reports, for the firing set and its baseline, the fraction
  of positive certificates (direction), the conditional mean (magnitude), the
  fraction that reach the $1,000 bar, and the PEAK-vs-CLOSE gap — the number
  that says "a real object with the wrong exit" in one column.

P007 ABSORPTION_NO_RESPONSE, AS AN ENTRY — vindicated on day 3 in its ORIGINAL
  form, censused in the two readings the record supports:
    A_60s_ledger  the ledger's literal fields: sign(60s sflow) == -side,
                  |sflow|/vol >= 0.40, and |mid(now) - mid(T-1m)| <= 1 tick
                  (slope_1m_usd, the S5 last-minute column).
    B_phase_day3  the form the 8 day-3 winners actually show (E1D3-F1/F4):
                  opposed PHASE aggression at >= 10% of phase volume, with the
                  price-failure confirmation (the aggression has not extended
                  the faded extreme within the last minute).

NOT CENSUSABLE AT ERA SCALE (reported, not silently dropped)
  * P007's `S7 c2f` (cancel-to-fill) and P024's `S7 dBsz/min vs dAsz/min`
    erosion term are MBP-1 BOOK-EVENT statistics.  The event cache holds 488
    of 3,734 roster sessions (1.5 GB); the full era would be a ~40 GB DBN
    re-extraction, which is a separate build item, not a census.  Both
    detectors are therefore censused WITHOUT those terms, and the omission is
    named on every table rather than hidden in a threshold.
  * P023's through-book side term is in the same class AND its sign is struck.

POPULATION / ERA LAW
  Frozen v3 roster, FIT 2021-2024, 2025 as an EVAL-ONLY GATE echo (D-058).  The
  GATE echo is additionally split H1/H2 because D-058 names 2025-07..2025-12 a
  PRE-EXAM HOLDOUT: batches 1-2 pooled the whole GATE year, so the pooled row
  is kept for comparability and the split rows are reported beside it.

OUTPUT (D-018: bulk under artifacts/cache/)
  artifacts/cache/port/m2/pattern_census/BATCH3_CENSUS_REPORT.md
  artifacts/cache/port/m2/pattern_census/BATCH3_{CENSUS,TERMS,DESTRUCTION,
      ROBUST}.tsv, P025_RUNWAY.tsv, P025_PHASE_GIVEN_RUNWAY.tsv,
      P024_MAGNITUDE.tsv, p025_census.receipt.json

Run:  lab/run.sh port-m2-p025 -- /usr/bin/python3 engine/port_m2/p025_census.py
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
import census_common as X                 # noqa: E402
import episode_v2 as EV                   # noqa: E402  (GEE sandwich, ICC/DEFF)
import p001_census as P1                  # noqa: E402  (the census machinery)

SECTION = "DISCRETIONARY_METHOD §4.2 name->count census — batch 3 (CC-M2-12.4)"
OUT_DIR = MC.out_path("pattern_census", "_")[:-1]

FIT_YEARS = P1.FIT_YEARS
GATE_YEAR = P1.GATE_YEAR
NY = X.PHASE_NAMES.index("NY")

# ------------------------------------------------------------- the terms ----
RUNWAY_HOURS_MIN = 3.0                    # P025 detector: "the bar needs hours"
RUNWAY_MIN_SEC = int(RUNWAY_HOURS_MIN * 3600)
SFLOW_MIN_FRAC = 0.05                     # P023 T1 / P024 T4 ("at magnitude")
VOL_FLOOR_ABS = 500                       # P023 T2 ABS (the fitted floor)
VOL_FLOOR_REL = 0.08                      # P023 T2 REL (8% of phase volume)
LIVE_N_MIN = 2                            # P023 T3 trade COUNT (P004 inverted)
# R109: LIVE_N_MIN was applied to BOTH the trade count AND the volume, so a
# 2-lot book counted as "live" — a floor in name only, though declared in
# PARAMS.  The volume floor is its own constant and is the one p001 already
# uses for a live book.
LIVE_VOL_MIN = 10                         # matches p001.F60_MIN_VOL
# R109: the aggression FRACTION needs a VOLUME FLOOR, not a clamped denominator.
# `np.maximum(den, 1.0)` made a single 1-lot opposing trade in an otherwise
# empty 60s window a 100% aggression signal, and a 2-lot phase with a 2-lot 5m
# window satisfy "flow concordant at >= 5%".  p001's own P016 X4 already does
# this correctly (`np.where(vol > 0, |sfl|/vol, 0.0)` PLUS `vol >= 200`), so
# this file was a regression against a pattern already in the codebase.  These
# floors are per WINDOW because the windows are different objects.
FRAC_MIN_VOL_60S = 10        # matches p001.F60_MIN_VOL
FRAC_MIN_VOL_5M = 50
FRAC_MIN_VOL_PHASE = 200     # matches p001.PHASE_MIN_VOL
PRICE_FAIL_AGE_SEC = 60                   # P023 T4 / P007 B: one minute
REFAIL_GAP_MAX_SEC = 300                  # P024 T1 ("<= ~5 min apart")
REFAIL_TICKS = 1.0                        # P024 T1 ("within ~1 tick")
EXT_MAX_USD = P1.EXT_MAX_USD              # P024 T3 ($450, P017's own threshold)
CONFLUENCE_MIN = 2                        # P024 T5 (">= 2 fvol families")
P007_60S_FRAC = 0.40                      # P007 A ("60s sflow/vol >= ~0.4")
P007_PHASE_FRAC = 0.10                    # P007 B (day-3: 10-12% of phase vol)
DAY_TYPE_EXPANDED = 2

CONCENTRATOR_MIN = 1.25                   # winner-rate / cond-value ratio
DESTRUCTION_REPS = P1.DESTRUCTION_REPS
DESTRUCTION_SEED = 20260816

# runway bands, in seconds; the last is open-ended
BANDS = ((0, 900), (900, 1800), (1800, 3600), (3600, 7200), (7200, 10800),
         (10800, 14400), (14400, 21600), (21600, 28800), (28800, 10 ** 9))
BAND_NAMES = ("b0_lt15m", "b1_15-30m", "b2_30-60m", "b3_1-2h", "b4_2-3h",
              "b5_3-4h", "b6_4-6h", "b7_6-8h", "b8_ge8h")

PARAMS = {
    "spec_section": SECTION,
    "order": "CC-M2-12.4 — census batch 3 (P025, P023, P024, P007-as-entry)",
    "definition_source": "provenance/port_m2/PATTERN_LEDGER.tsv (sheet_fields "
                         "P007/P023/P024/P025) + provenance/port_m2/"
                         "E1_POSTMORTEMS.md day-3 §1/§3/§4/§6",
    "P025": "conditioning object = runway to the BINDING exit (the CC-M2-10.3 "
            "phase-close seat). Reading A = runway_phase_sec (nominal); "
            "reading B = runway_binding_sec = min(nominal, observed_close - "
            "dec_sec) (D15). Detector form for grading: runway >= %dh"
            % int(RUNWAY_HOURS_MIN),
    "P025_phase_test": "phase_dec is a CONTROL: `is_NY` is tested unadjusted "
                       "and ADJUSTED for runway (GEE identity on both "
                       "certificates, GEE logit on the D-021 winner "
                       "indicator), plus the same tests stratified WITHIN "
                       "each runway band, plus the symmetric runway-adjusted-"
                       "for-phase test",
    "P023": "fire = opposed 5m aggression (sign(f5m_sflow) == -side and "
            "|f5m_sflow|/f5m_vol >= %.2f) AND volume floor (ABS f5m_vol >= "
            "%d / REL f5m_vol >= %.2f x fph_vol / OR either) AND live book "
            "(f60_n >= %d and f60_vol >= %d) AND price failure "
            "(extreme_age_sec >= %ds). The through-book SIDE term is struck "
            "(E1D3-F4) and is not censusable at era scale."
            % (SFLOW_MIN_FRAC, VOL_FLOOR_ABS, VOL_FLOOR_REL, LIVE_N_MIN,
               LIVE_N_MIN, PRICE_FAIL_AGE_SEC),
    "P024": "fire = refail (two causal pivots of the faded type <= %ds apart "
            "and <= %.0f tick apart) AND day_type == EXPANDED AND ext_needed "
            "<= $%.0f AND phase+5m sflow concordant at >= %.2f; reading B "
            "adds >= %d KEPT level families within 2 ticks of the refail "
            "price. The S7 erosion term is not censusable at era scale."
            % (REFAIL_GAP_MAX_SEC, REFAIL_TICKS, EXT_MAX_USD, SFLOW_MIN_FRAC,
               CONFLUENCE_MIN),
    "P007": "reading A (ledger-literal): opposed 60s aggression at >= %.2f of "
            "60s volume AND |slope_1m_usd| <= 1 tick. reading B (day-3 form): "
            "opposed PHASE aggression at >= %.2f of phase volume AND the "
            "faded extreme is >= %ds old. The S7 c2f term is not censusable "
            "at era scale." % (P007_60S_FRAC, P007_PHASE_FRAC,
                               PRICE_FAIL_AGE_SEC),
    "value": "c_c_roster.certificates — walled PHASE-CLOSE (adoption) and "
             "walled PEAK-EXIT (CC-M1-8 companion), both always reported",
    "conditional_value": "mean over POSITIVE candidates (CC-M1-7.3)",
    "winner": "cert_close >= $1000 and mae_before_argmax <= $300 and not "
              "walled (D-021)",
    "population": "frozen v3 roster, FIT years %s; %d = GATE echo, EVAL-ONLY, "
                  "additionally split H1/H2 (D-058 pre-exam holdout)"
                  % (list(FIT_YEARS), GATE_YEAR),
    "destruction": "each term shuffled WITHIN SESSION, %d replicates, "
                   "RandomState(%d + term index); the other terms untouched. "
                   "The destroyed quantity is the EDGE (mean cert of the "
                   "firing set minus mean cert of the non-firing rest)"
                   % (DESTRUCTION_REPS, DESTRUCTION_SEED),
    "inference": "CC-M1-12.4 — GEE independence working correlation with the "
                 "Liang-Zeger sandwich clustered on SESSION (CR0 + "
                 "Cameron-Miller CR1); Kish one-way ICC/DEFF for n_eff; "
                 "Holm-Bonferroni over THE WHOLE BATCH (every GEE test of all "
                 "four patterns and every reading is one family)",
    "grading": "CC-M2-9.1 — ENTRY RULE / VETO RULE (Holm-significant beta on "
               "the adoption metric) vs WINNER CONCENTRATOR (>= %.2fx winner "
               "rate or conditional value with no adoption edge -> feature "
               "candidate set only) vs NULL" % CONCENTRATOR_MIN,
    "not_censusable": "S7 c2f (P007), S7 dBsz/dAsz erosion (P024) and the S8 "
                      "through-book side (P023, sign struck) are MBP-1 "
                      "book-event statistics; the event cache covers 488 of "
                      "3,734 roster sessions and the era-scale extraction is "
                      "a build item, not a census",
    "runway_bands_sec": [list(b) for b in BANDS],
    "holdout": "D-058 — the population comes from pattern_lib.sessions_fit, "
               "which EXCLUDES every session >= %d and returns the excluded "
               "count (R105). This file previously FLAGGED the holdout at the "
               "WRONG BOUNDARY (>= 20250901), understating the contamination "
               "by July and August 2025 in both the receipt and the report. "
               "The eval era is GATE_%dH1." % (MC.HOLDOUT_FROM_D8, GATE_YEAR),
    "not_promotable": "R108 — P025 reading B_observed is INELIGIBLE for "
                      "promotion: runway_binding_sec is derived from the m0 "
                      "receipt's last_two_sided_sec, an END-OF-SESSION fact "
                      "unknowable at dec_sec. It is a DIAGNOSTIC that corrects "
                      "the census for D15 holiday tapes.",
    "refusal_bands": "R110 — band_index has a REFUSED band (-1) with its own "
                     "rows and its own count. Refused and negative runways "
                     "used to land in b0_lt15m. Reading B additionally bands "
                     "REFUSED wherever the m0 receipt lacks last_two_sided_sec "
                     "(pattern_lib.runway_binding_refused), where reading B "
                     "silently degenerated into reading A.",
    "volume_floors": "R109 — _frac REFUSES below a per-window volume floor "
                     "(60s %d, 5m %d, phase %d) instead of clamping the "
                     "denominator to 1.0, which made a single 1-lot opposing "
                     "trade in an empty window a 100%% aggression signal. "
                     "LIVE_N_MIN %d is a TRADE COUNT and LIVE_VOL_MIN %d is "
                     "the volume floor — one constant used to serve as both."
                     % (FRAC_MIN_VOL_60S, FRAC_MIN_VOL_5M, FRAC_MIN_VOL_PHASE,
                        LIVE_N_MIN, LIVE_VOL_MIN),
    "promotion": "R106 — WINNER CONCENTRATOR requires the ratio to clear "
                 "%.2fx AND a session-clustered bootstrap interval excluding "
                 "1.0 AND Holm significance in the PROMOTION family AND the n "
                 "floors (%d fires over %d sessions)."
                 % (CONCENTRATOR_MIN, P1.PROMOTE_MIN_FIRES,
                    P1.PROMOTE_MIN_CLUSTERS),
    "mirror_law": "R112 — P023/P007's OPPOSED-flow claim and P024's "
                  "CONCORDANT-flow claim are each run against the SAME "
                  "detector with the flow direction sign-flipped, paired "
                  "within the session (BATCH3_MIRROR.tsv)",
    "holm_families": "R107 — FOUR families corrected separately: GEE_DECIDING "
                     "(detector coefficients + NY_ADJ + within-band), "
                     "GEE_DIAGNOSTIC (NY_RAW/RW_RAW/RW_ADJ, algebraic "
                     "re-expressions), MIRROR, PROMOTION. One family of ~372 "
                     "put the rank-1 threshold at ~1.3e-4.",
    "inference_floors": "R113 — no GEE below %d clusters; t(G-1) reference "
                        "(Cameron-Miller) rather than the standard normal"
                        % P1.MIN_CLUSTERS_GEE,
    "in_sample": "R114 — VOL_FLOOR_ABS 500 is explicitly 'the fitted floor' "
                 "and every other threshold here came off E1 study days "
                 "1/2/3, all inside FIT. Every table carries FIT_EX_FITTING "
                 "beside FIT and the birth-case table is a REPRODUCTION "
                 "CHECK, not corroboration.",
    "un_censused_constants": "declared basis, one line each (3.2b MINORS). "
                             "RUNWAY_HOURS_MIN 3.0 is the PATTERN_LEDGER's own "
                             "sentence ('the $1,000 bar needs HOURS'); "
                             "SFLOW_MIN_FRAC 0.05 / P007_60S_FRAC 0.40 / "
                             "P007_PHASE_FRAC 0.10 / REFAIL_GAP_MAX_SEC 300 / "
                             "REFAIL_TICKS 1.0 / CONFLUENCE_MIN 2 are the "
                             "ledger sheet_fields literals; EXT_MAX_USD 450 is "
                             "e1d1_policy T3's own threshold; VOL_FLOOR_ABS "
                             "500 and VOL_FLOOR_REL 0.08 are the day-1/2 "
                             "fitted floors (hence FIT_EX_FITTING); "
                             "PRICE_FAIL_AGE_SEC 60 is one minute; the 9-band "
                             "runway grid is a log-ish partition of the "
                             "session clock and is THE LARGEST un-censused "
                             "surface here because the deciding tables are "
                             "stratified on it; the $1,000 bar is D-021; the "
                             "TOKYO/LONDON share columns are the two non-NY "
                             "phases named. NONE carries a sensitivity sweep "
                             "— the sweep is a build item, and saying so is "
                             "the point of this entry.",
    "frame": PL.PARAMS_FRAME,
    "frame_v2": PL.PARAMS_FRAME_V2,
}


# ---------------------------------------------------------------- detectors -
def _frac(num, den, min_vol):
    """|num| / den, REFUSED (0.0, i.e. the term cannot fire) below `min_vol`.

    The denominator is never clamped: a window with too little volume to
    measure a fraction does not get a fraction, it gets a refusal that no
    threshold can pass."""
    d = den.astype(np.float64)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(d >= float(min_vol),
                        np.abs(num.astype(np.float64)) / np.where(d > 0, d, 1.0),
                        0.0)


def _opposed(sflow, side):
    s = np.sign(sflow.astype(np.float64))
    return (s != 0) & (s == -side)


def _concordant(sflow, side):
    s = np.sign(sflow.astype(np.float64))
    return (s != 0) & (s == side)


def terms_p025(f, reading):
    rw = (f["runway_phase_sec"] if reading == "A_nominal"
          else f["runway_binding_sec"])
    return np.column_stack([rw >= RUNWAY_MIN_SEC])


def terms_p023(f, reading):
    side = f["side"].astype(np.float64)
    t1 = (_opposed(f["f5m_sflow"], side)
          & (_frac(f["f5m_sflow"], f["f5m_vol"], FRAC_MIN_VOL_5M)
             >= SFLOW_MIN_FRAC))
    abs_ok = f["f5m_vol"] >= VOL_FLOOR_ABS
    rel_ok = (f["f5m_vol"].astype(np.float64)
              >= VOL_FLOOR_REL * np.maximum(f["fph_vol"].astype(np.float64),
                                            1.0))
    t2 = {"ABS": abs_ok, "REL": rel_ok, "OR": abs_ok | rel_ok}[reading]
    t3 = (f["f60_n"] >= LIVE_N_MIN) & (f["f60_vol"] >= LIVE_VOL_MIN)
    t4 = f["extreme_age_sec"] >= PRICE_FAIL_AGE_SEC
    return np.column_stack([t1, t2, t3, t4])


def terms_p024(f, reading):
    side = f["side"].astype(np.float64)
    gap = f["refail_gap_sec"]
    t1 = ((gap >= 0) & (gap <= REFAIL_GAP_MAX_SEC)
          & np.isfinite(f["refail_dist_usd"])
          & (f["refail_dist_usd"] <= REFAIL_TICKS * f["tick_usd"]))
    t2 = f["day_type"] == DAY_TYPE_EXPANDED
    ext = f["ext_needed_usd"]
    t3 = np.isfinite(ext) & (ext <= EXT_MAX_USD)
    t4 = (_concordant(f["fph_sflow"], side)
          & (_frac(f["fph_sflow"], f["fph_vol"], FRAC_MIN_VOL_PHASE)
             >= SFLOW_MIN_FRAC)
          & _concordant(f["f5m_sflow"], side)
          & (_frac(f["f5m_sflow"], f["f5m_vol"], FRAC_MIN_VOL_5M)
             >= SFLOW_MIN_FRAC))
    cols = [t1, t2, t3, t4]
    if reading == "B_confluence":
        cols.append(f["n_conf_fam_at_refail_2t"] >= CONFLUENCE_MIN)
    return np.column_stack(cols)


def terms_p007(f, reading):
    side = f["side"].astype(np.float64)
    if reading == "A_60s_ledger":
        t1 = (_opposed(f["f60_sflow"], side)
              & (_frac(f["f60_sflow"], f["f60_vol"], FRAC_MIN_VOL_60S)
              >= P007_60S_FRAC))
        # MINOR (3.2b): this relied on NaN-comparison semantics rather than an
        # explicit guard.  The direction was safe but the behaviour was
        # undeclared, unlike p001's own T5 which states it.
        sl = f["slope_1m_usd"].astype(np.float64)
        t2 = np.isfinite(sl) & (np.abs(sl) <= f["tick_usd"])
        return np.column_stack([t1, t2])
    t1 = (_opposed(f["fph_sflow"], side)
          & (_frac(f["fph_sflow"], f["fph_vol"], FRAC_MIN_VOL_PHASE)
          >= P007_PHASE_FRAC))
    t2 = f["extreme_age_sec"] >= PRICE_FAIL_AGE_SEC
    return np.column_stack([t1, t2])


# (pattern_id, reading, term names, fn) — one row per CENSUSED READING
READINGS = (
    ("P025", "A_nominal", ("T1_runway_ge_3h",), terms_p025),
    ("P025", "B_observed", ("T1_runway_ge_3h",), terms_p025),
    ("P023", "ABS", ("T1_opposed_5m", "T2_vol_abs_500", "T3_live_book",
                     "T4_price_failure"), terms_p023),
    ("P023", "REL", ("T1_opposed_5m", "T2_vol_rel_8pct", "T3_live_book",
                     "T4_price_failure"), terms_p023),
    ("P023", "OR", ("T1_opposed_5m", "T2_vol_abs_or_rel", "T3_live_book",
                    "T4_price_failure"), terms_p023),
    ("P024", "A_core", ("T1_refail", "T2_expanded", "T3_room",
                        "T4_flow_concordant"), terms_p024),
    ("P024", "B_confluence", ("T1_refail", "T2_expanded", "T3_room",
                              "T4_flow_concordant", "T5_confluence"),
     terms_p024),
    ("P007", "A_60s_ledger", ("T1_opposed_60s_0.40", "T2_no_price_response"),
     terms_p007),
    ("P007", "B_phase_day3", ("T1_opposed_phase_0.10", "T2_price_failure"),
     terms_p007),
)


def tag_of(pid, reading):
    return "%s_%s" % (pid, reading)


# --------------------------------------------------------------- the pass ---
def _bits(t):
    out = np.zeros(t.shape[0], dtype=np.uint16)
    for k in range(t.shape[1]):
        out |= (t[:, k].astype(np.uint16) << k)
    return out


_KEYS_I32 = ("dec_sec", "runway_phase_sec", "runway_binding_sec",
             "observed_close_sec", "extreme_age_sec", "refail_gap_sec",
             "n_conf_fam_at_refail", "n_conf_fam_at_refail_2t",
             "f60_n", "f60_vol", "f60_sflow", "f5m_vol", "f5m_sflow",
             "f30m_vol", "f30m_sflow", "fph_vol", "fph_sflow", "clock_sec")
_KEYS_I8 = ("side", "phase_dec", "day_type")
_KEYS_B = ("walled", "winner", "short_day", "session_close_exit",
           "runway_binding_refused", "cert_refused")


def _pack(f):
    out = {"asset": f["asset"], "d8": f["d8"], "klass": f["klass"]}
    out["cert_close"] = f["cert_close_usd"].astype(np.float64)
    out["cert_peak"] = f["cert_peak_usd"].astype(np.float64)
    out["mae"] = f["mae_before_argmax"].astype(np.float64)
    for k in ("day_type_frac", "ext_needed_usd", "refail_dist_usd",
              "slope_1m_usd", "tick_usd"):
        out[k] = f[k].astype(np.float64)
    for k in _KEYS_I32:
        out[k] = f[k].astype(np.int32)
    for k in _KEYS_I8:
        out[k] = f[k].astype(np.int8)
    for k in _KEYS_B:
        out[k] = f[k].astype(bool)
    for pid, reading, _names, fn in READINGS:
        tag = tag_of(pid, reading)
        out["terms_" + tag] = _bits(fn(f, reading))
        # R112: the MIRROR detector — the same terms with the FLOW DIRECTION
        # sign-flipped and nothing else touched.  `side` enters terms_p023 /
        # terms_p024 / terms_p007 ONLY through _opposed/_concordant, so
        # negating it inverts exactly the direction claim and leaves the
        # volume floors, the price-failure term and the refail geometry alone.
        fm = dict(f)
        fm["side"] = -np.asarray(f["side"])
        out["mterms_" + tag] = _bits(fn(fm, reading))
    return out


def _one(job):
    asset, d8 = job
    try:
        f = PL.frame(asset, int(d8), with_levels=True)
    except Exception as e:                # noqa: BLE001 — surfaced, not hidden
        return ("ERROR", asset, int(d8), repr(e)[:300])
    if f is None:
        return ("EMPTY", asset, int(d8), "")
    return ("OK", _pack(f))


_CONCAT = (("cert_close", "cert_peak", "mae", "day_type_frac",
            "ext_needed_usd", "refail_dist_usd", "slope_1m_usd", "tick_usd",
            "klass") + _KEYS_I32 + _KEYS_I8 + _KEYS_B
           + tuple("terms_" + tag_of(p[0], p[1]) for p in READINGS)
           + tuple("mterms_" + tag_of(p[0], p[1]) for p in READINGS))


def scan(assets=MC.ASSET_ORDER, years=FIT_YEARS + (GATE_YEAR,), workers=4,
         limit_sessions=None):
    jobs, quarantined = [], 0
    for a in assets:
        # R105: this census pooled the D-058 pre-exam holdout into every GATE
        # row AND flagged it at the WRONG boundary (20250901, understating the
        # contamination by July+August 2025).  The boundary is now ONE constant
        # (MC.HOLDOUT_FROM_D8 = 20250701) and the guarded enumerator EXCLUDES
        # rather than flags — CC-M2-15.3's correction, finally applied here.
        ds, nq = PL.sessions_fit(a, years=set(years))
        quarantined += nq
        if limit_sessions:
            ds = ds[:limit_sessions]
        jobs += [(a, d) for d in ds]
    jobs.sort()
    parts, errs = [], []
    t0 = time.time()
    if workers and workers > 1:
        with mp.Pool(processes=int(workers)) as pool:
            for n, res in enumerate(pool.imap(_one, jobs, chunksize=8), 1):
                if res[0] == "OK":
                    parts.append(res[1])
                elif res[0] == "ERROR":
                    errs.append((res[1], res[2], res[3]))
                if n % 250 == 0:
                    MC.hb("batch3 scan %d/%d  %.1fs" % (n, len(jobs),
                                                        time.time() - t0))
    else:
        for j in jobs:
            res = _one(j)
            if res[0] == "OK":
                parts.append(res[1])
            elif res[0] == "ERROR":
                errs.append((res[1], res[2], res[3]))
    if errs:
        raise RuntimeError("batch3 scan: %d session(s) failed, first=%s"
                           % (len(errs), errs[0]))
    parts.sort(key=lambda p: (p["asset"], p["d8"]))
    out = {}
    for k in _CONCAT:
        out[k] = np.concatenate([p[k] for p in parts])
    out["asset"] = np.concatenate([np.full(p["dec_sec"].size, p["asset"])
                                   for p in parts])
    out["d8"] = np.concatenate([np.full(p["dec_sec"].size, p["d8"],
                                        dtype=np.int32) for p in parts])
    out["year"] = (out["d8"] // 10000).astype(np.int32)
    keys = np.array(["%s-%08d" % (a, d) for a, d in
                     zip(out["asset"].tolist(), out["d8"].tolist())])
    uniq, out["cluster"] = np.unique(keys, return_inverse=True)
    out["n_sessions_total"] = int(uniq.size)
    # R105: the receipt used to stamp a count taken at the WRONG BOUNDARY
    # (`>= 20250901`), understating the contamination by July and August 2025 —
    # the one number the "flag, not a filter" defence rested on.  There is no
    # flag now: the holdout is EXCLUDED at enumeration and the count of what
    # was excluded is what the receipt carries.
    out["n_quarantined_holdout"] = int(quarantined)
    out["side"] = out["side"].astype(np.int64)
    MC.hb("batch3 scan: %d candidates over %d sessions, %.1fs"
          % (out["dec_sec"].size, uniq.size, time.time() - t0))
    return out


# --------------------------------------------------------- P025 the object --
BAND_REFUSED = -1
BAND_REFUSED_NAME = "REFUSED"


def band_index(v, refused=None):
    """Runway band ordinal of each candidate, or BAND_REFUSED (-1).

    R110: `out` was np.zeros-initialised and ended with `out[v < 0] = 0`, so a
    REFUSED or NEGATIVE runway — and any value matching no band at all —
    landed in `b0_lt15m`, indistinguishable from a genuine sub-15-minute
    runway.  There was no refusal band and no refusal count, and the tables
    that contaminated (P025_RUNWAY.tsv, P025_PHASE_GIVEN_RUNWAY.tsv) are the
    artefact-control tables the entire P025 ruling turns on.  A sentinel is
    never a number: it gets its own band, and `band_counts` returns the count.

    `refused` is an optional extra refusal mask (reading B passes
    `runway_binding_refused`, so a runway that DEGENERATED to the nominal one
    because the m0 receipt carried no last_two_sided_sec is banded REFUSED
    rather than silently read as an observed runway).
    """
    out = np.full(v.size, BAND_REFUSED, dtype=np.int64)
    for k, (lo, hi) in enumerate(BANDS):
        out[(v >= lo) & (v < hi)] = k
    out[v < 0] = BAND_REFUSED
    if refused is not None:
        out[np.asarray(refused, dtype=bool)] = BAND_REFUSED
    return out


def band_counts(band):
    return {"n_refused": int((band == BAND_REFUSED).sum()),
            "n_banded": int((band != BAND_REFUSED).sum())}


def band_name(k):
    return BAND_REFUSED_NAME if k == BAND_REFUSED else BAND_NAMES[k]


RUNWAY_COLUMNS = ("reading", "asset", "era", "band", "band_lo_sec",
                  "band_hi_sec", "n_sessions", "n_candidates", "cand_share",
                  "n_winners", "winner_share", "conc_ratio", "winner_rate",
                  "base_winner_rate", "winner_rate_lift", "mean_close",
                  "cond_close", "posfrac_close", "mean_peak", "cond_peak",
                  "frac_ge_1000_close", "share_NY", "share_TOKYO",
                  "share_LONDON")


def _era_masks(D):
    """The era rows every batch-3 table carries.

    R105: this file used to emit a POOLED `GATE_2025` alongside an H1/H2 split
    that was applied ONLY in `runway_rows` — `phase_given_runway_rows`,
    `phase_adjustment_rows`, `magnitude_rows`, BATCH3_CENSUS.tsv,
    BATCH3_ROBUST.tsv and the DECIDING NY-vs-runway GEE all used the pooled
    row.  The holdout is now EXCLUDED at enumeration (`PL.sessions_fit`), so
    there is no H2 to pool and no pooled spelling to mistake for a whole year:
    the eval era is `GATE_2025H1` and the name says what it is.

    R114 adds FIT_EX_FITTING — FIT with the threshold-fitting sessions dropped.
    """
    return P1.era_selectors(D)[:3]


def runway_rows(D, band, reading, rows):
    """The band table: winner rate, concentration ratio and both certificate
    readings by (asset, era, runway band).

    `conc_ratio` is P020's artefact control moved to the runway axis: a band
    that simply holds more candidates cannot look like a pattern, because the
    ratio divides the band's winner share by its candidate share.
    """
    assets = [("ALL", np.ones(band.size, dtype=bool))]
    assets += [(a, D["asset"] == a) for a in MC.ASSET_ORDER]
    for aname, asel in assets:
        for ename, esel in _era_masks(D):
            base = asel & esel
            if not base.any():
                continue
            n_all = int(base.sum())
            w_all = int(D["winner"][base].sum())
            base_rate = (float(w_all) / n_all) if n_all else float("nan")
            for k, bname in ([(BAND_REFUSED, BAND_REFUSED_NAME)]
                             + list(enumerate(BAND_NAMES))):
                m = base & (band == k)
                n = int(m.sum())
                if not n:
                    continue
                cc = D["cert_close"][m]
                cp = D["cert_peak"][m]
                wn = D["winner"][m]
                pos = cc[cc > 0]
                pos_p = cp[cp > 0]
                nw = int(wn.sum())
                cand_share = float(n) / n_all
                win_share = (float(nw) / w_all) if w_all else float("nan")
                wr = float(nw) / n
                ph = D["phase_dec"][m]
                rows.append([reading, aname, ename, bname,
                             BANDS[k][0] if k >= 0 else -1,
                             BANDS[k][1] if k >= 0 else -1,
                             len(set(D["cluster"][m].tolist())),
                             n, cand_share, nw, win_share,
                             (win_share / cand_share
                              if cand_share > 0 and np.isfinite(win_share)
                              else float("nan")),
                             wr, base_rate,
                             (wr / base_rate if base_rate > 0
                              else float("nan")),
                             float(cc.mean()),
                             float(pos.mean()) if pos.size else float("nan"),
                             float(pos.size) / n,
                             float(cp.mean()),
                             float(pos_p.mean()) if pos_p.size
                             else float("nan"),
                             float((cc >= 1000.0).mean()),
                             float((ph == NY).mean()),
                             float((ph == X.PHASE_NAMES.index("TOKYO")).mean()),
                             float((ph == X.PHASE_NAMES.index("LONDON")).mean())])
    return rows


PGR_COLUMNS = ("reading", "asset", "era", "band", "phase", "n_candidates",
               "cand_share_in_band", "n_winners", "winner_share_in_band",
               "conc_ratio_in_band", "winner_rate", "band_winner_rate",
               "mean_close", "cond_close", "mean_peak")


def phase_given_runway_rows(D, band, reading, rows):
    """THE DECIDING TABLE: phase_dec WITHIN each runway band.

    P020 said 86/86 winners were in NY.  If that was a runway fact, then inside
    a runway band the phases must hold winners in proportion to the candidates
    they generate — conc_ratio_in_band ~ 1.00 — and any residual NY excess is
    what the phase adds on top of the runway.
    """
    assets = [("ALL", np.ones(band.size, dtype=bool))]
    assets += [(a, D["asset"] == a) for a in MC.ASSET_ORDER]
    for aname, asel in assets:
        for ename, esel in _era_masks(D):
            for k, bname in ([(BAND_REFUSED, BAND_REFUSED_NAME)]
                             + list(enumerate(BAND_NAMES))):
                base = asel & esel & (band == k)
                n_b = int(base.sum())
                if not n_b:
                    continue
                w_b = int(D["winner"][base].sum())
                for p in range(X.N_PHASES):
                    m = base & (D["phase_dec"] == p)
                    n = int(m.sum())
                    if not n:
                        continue
                    cc = D["cert_close"][m]
                    cp = D["cert_peak"][m]
                    nw = int(D["winner"][m].sum())
                    cs = float(n) / n_b
                    ws = (float(nw) / w_b) if w_b else float("nan")
                    pos = cc[cc > 0]
                    rows.append([reading, aname, ename, bname,
                                 X.PHASE_NAMES[p], n, cs, nw, ws,
                                 (ws / cs if cs > 0 and np.isfinite(ws)
                                  else float("nan")),
                                 float(nw) / n,
                                 (float(w_b) / n_b) if n_b else float("nan"),
                                 float(cc.mean()),
                                 float(pos.mean()) if pos.size
                                 else float("nan"),
                                 float(cp.mean())])
    return rows


def _gee_row(tag, aname, ename, metric, y, xcols, cl, n_fire, link="identity"):
    """One ROBUST-layout row for an arbitrary (possibly adjusted) GEE.

    gee_independence reports the coefficient of the FIRST regressor, so the
    variable under test is always passed first and the controls follow.
    """
    ic = EV.icc_oneway(y, cl)
    x = np.column_stack(xcols).astype(np.float64)
    # R113: `x.shape[0] > x.shape[1] + 2` was the ONLY guard, so a 5-row cell
    # drawn from ONE session passed it, gee_independence returned
    # n_clusters == 1, the sandwich meat was a single outer product and
    # _p_two_sided returned a spuriously tiny p that entered the Holm family as
    # a real test.  `phase_in_band_rows` runs over 9 runway bands and hit this
    # directly.  A CLUSTER floor, and a t(G-1) reference per Cameron-Miller.
    n_cl = int(np.unique(cl).size)
    g = None
    if (x.shape[0] > x.shape[1] + 2 and np.ptp(x[:, 0]) > 0
            and n_cl >= P1.MIN_CLUSTERS_GEE):
        g = EV.gee_independence(y, x, cl, link=link)
    if g is None:
        return [tag, aname, ename, metric, int(y.size),
                n_cl, int(n_fire)] + [float("nan")] * 6 \
            + [ic["rho"] if ic else float("nan"),
               ic["deff"] if ic else float("nan"),
               ic["n_eff"] if ic else float("nan"),
               ("NO_TEST_below_cluster_floor" if n_cl < P1.MIN_CLUSTERS_GEE
                else "NO_VARIATION")]
    z = (g["beta"] / g["se_cr1"]) if g["se_cr1"] > 0 else float("nan")
    p = P1._p_two_sided(z, df=g["n_clusters"] - 1)
    return [tag, aname, ename, metric, g["n"], g["n_clusters"], int(n_fire),
            g["beta"], g["se_naive"], g["se_cr0"], g["se_cr1"], z, p,
            ic["rho"] if ic else float("nan"),
            ic["deff"] if ic else float("nan"),
            ic["n_eff"] if ic else float("nan"),
            ("SIGNIFICANT_p<0.05" if np.isfinite(p) and p < 0.05
             else "NOT_SIGNIFICANT")]


def phase_adjustment_rows(D, runway_sec, reading):
    """Does PHASE survive conditioning on runway?  (and the symmetric test)

    Four tags per (asset, era):
      P025_NY_RAW_<r>    is_NY alone            — P020's claim, re-run
      P025_NY_ADJ_<r>    is_NY + runway_hours   — the deciding coefficient
      P025_RW_RAW_<r>    runway_hours alone
      P025_RW_ADJ_<r>    runway_hours + is_NY   — runway net of phase
    on THREE metrics: both certificates (identity link) and the D-021 winner
    indicator (logit link), because the struck claim was a WINNER claim.
    """
    rows = []
    ny = (D["phase_dec"] == NY).astype(np.float64)
    rwh = runway_sec.astype(np.float64) / 3600.0
    assets = [("ALL", np.ones(ny.size, dtype=bool))]
    assets += [(a, D["asset"] == a) for a in MC.ASSET_ORDER]
    for aname, asel in assets:
        for ename, esel in _era_masks(D):
            m = asel & esel
            if not m.any():
                continue
            cl = D["cluster"][m]
            a_ny, a_rw = ny[m], rwh[m]
            n_ny = int(a_ny.sum())
            mets = (("cert_close", D["cert_close"][m], "identity"),
                    ("cert_peak", D["cert_peak"][m], "identity"),
                    ("winner", D["winner"][m].astype(np.float64), "logit"))
            for metric, y, link in mets:
                rows.append(_gee_row("P025_NY_RAW_" + reading, aname, ename,
                                     metric, y, [a_ny], cl, n_ny, link))
                rows.append(_gee_row("P025_NY_ADJ_" + reading, aname, ename,
                                     metric, y, [a_ny, a_rw], cl, n_ny, link))
                rows.append(_gee_row("P025_RW_RAW_" + reading, aname, ename,
                                     metric, y, [a_rw], cl, int(m.sum()),
                                     link))
                rows.append(_gee_row("P025_RW_ADJ_" + reading, aname, ename,
                                     metric, y, [a_rw, a_ny], cl,
                                     int(m.sum()), link))
    return rows


def phase_in_band_rows(D, band, reading):
    """The stratified form of the same question: is_NY tested INSIDE each
    runway band (FIT, all assets pooled).  A band is skipped when it holds no
    NY candidates or no non-NY candidates — there is no contrast to test."""
    rows = []
    fit = np.isin(D["year"], FIT_YEARS)
    ny = (D["phase_dec"] == NY).astype(np.float64)
    for k, bname in ([(BAND_REFUSED, BAND_REFUSED_NAME)]
                     + list(enumerate(BAND_NAMES))):
        m = fit & (band == k)
        if not m.any():
            continue
        a_ny = ny[m]
        if a_ny.sum() in (0, a_ny.size):
            continue
        cl = D["cluster"][m]
        for metric, y, link in (("cert_close", D["cert_close"][m], "identity"),
                                ("winner", D["winner"][m].astype(np.float64),
                                 "logit")):
            rows.append(_gee_row("P025_NY_IN_%s_%s" % (bname, reading), "ALL",
                                 "FIT", metric, y, [a_ny], cl,
                                 int(a_ny.sum()), link))
    return rows


# ------------------------------------------------ P024 direction/magnitude --
MAG_COLUMNS = ("reading", "asset", "era", "group", "n", "n_sessions",
               "posfrac_close", "mean_close", "cond_close", "median_close",
               "frac_ge_1000", "mean_peak", "cond_peak", "peak_minus_close",
               "n_winners", "winner_frac", "mean_mae")


def magnitude_rows(D, fire, reading, rows):
    """P024's real question, in one table.

    The day-3 verdict was "the DIRECTION was right on all five and the
    certificate came in at a third of the bar".  Direction lives in
    `posfrac_close`; magnitude lives in `cond_close`, `frac_ge_1000` and the
    PEAK-minus-CLOSE column, which is the size of the give-back the exit rule
    hands back.
    """
    for aname, asel in ([("ALL", np.ones(fire.size, dtype=bool))]
                        + [(a, D["asset"] == a) for a in MC.ASSET_ORDER]):
        for ename, esel in _era_masks(D):
            for gname, gsel in (("FIRE", fire), ("NOFIRE", ~fire)):
                m = asel & esel & gsel
                n = int(m.sum())
                if not n:
                    continue
                cc = D["cert_close"][m]
                cp = D["cert_peak"][m]
                pos = cc[cc > 0]
                pos_p = cp[cp > 0]
                rows.append([reading, aname, ename, gname, n,
                             len(set(D["cluster"][m].tolist())),
                             float((cc > 0).mean()), float(cc.mean()),
                             float(pos.mean()) if pos.size else float("nan"),
                             float(np.median(cc)),
                             float((cc >= 1000.0).mean()), float(cp.mean()),
                             float(pos_p.mean()) if pos_p.size
                             else float("nan"),
                             float(cp.mean() - cc.mean()),
                             int(D["winner"][m].sum()),
                             float(D["winner"][m].mean()),
                             float(np.nanmean(D["mae"][m]))])
    return rows


# ----------------------------------------------------------------- grading --
# R108: `runway_binding_sec` is built from `s.meta["last_two_sided_sec"]` — the
# last two-sided second of the WHOLE SESSION, written by port_m0/s3_sessions.py
# as `idx[-1]`, and UNKNOWABLE at dec_sec.  triage_index.py:165-166 already
# masks exactly this field under --as-of.  Reading B_observed was nonetheless
# run through the full CC-M2-9.1 grading pipeline and sat in the headline
# verdict table eligible for promotion to an ENTRY RULE.  It is a DIAGNOSTIC:
# it says what the runway REALLY was, which is the right thing to correct a
# census with (D15) and the wrong thing to trade on.
NOT_PROMOTABLE = {"P025_B_observed": (
    "runway_binding_sec is derived from the m0 receipt's last_two_sided_sec, "
    "an END-OF-SESSION fact unknowable at the decision second (R108). This "
    "reading is a DIAGNOSTIC that corrects the census for D15 holiday tapes; "
    "it can never be an entry rule and is excluded from the promotion "
    "vocabulary.")}


def grade(res, cen, promo, era="FIT_EX_FITTING"):
    """(verdict, evidence) in the CC-M2-9.1 vocabulary.

    R108: a reading built from an end-of-session aggregate is INELIGIBLE and
    says so, rather than appearing in the headline table as an entry-rule
    candidate.
    R106: WINNER CONCENTRATOR used to be a BARE RATIO (`fF[16]/fN[16] >= 1.25`)
    with no SE, no CI, no cluster adjustment and no minimum-n guard on the
    numerator — the only route by which P023/P024/P007 reached the
    feature-candidate set.  It now requires the ratio to clear the bar AND its
    session-clustered interval to exclude 1.0 AND Holm significance in the
    declared PROMOTION family AND the n floors.
    R114: the ratios are read on FIT_EX_FITTING, because FIT is in-sample with
    respect to the thresholds this file declares.
    """
    tag = res.get("tag")
    fF = cen.get(("ALL", "FIT", "ALL", "ALL", "FIRE"))
    fN = cen.get(("ALL", "FIT", "ALL", "ALL", "NOFIRE"))
    rb = [x for x in res["robust"]
          if x[1] == "ALL" and x[2] == "FIT" and x[3] == "cert_close"]
    beta = rb[0][7] if rb else float("nan")
    holm = rb[0][19] if rb and len(rb[0]) > 19 else "NO_TEST"
    ev = {"beta_close": beta, "holm": holm, "promotion_era": era,
          "n_fires": fF[7] if fF else 0}
    for r in [x for x in promo if x[0] == tag and x[1] == era]:
        ev[r[2]] = r[3]
        ev[r[2] + "_ci"] = (r[4], r[5])
        ev[r[2] + "_verdict"] = r[9]
        ev[r[2] + "_holm"] = r[10]
    if tag in NOT_PROMOTABLE:
        ev["ineligible_reason"] = NOT_PROMOTABLE[tag]
        return "DIAGNOSTIC ONLY — INELIGIBLE FOR PROMOTION (R108)", ev
    if fF is None or fN is None or fF[7] == 0:
        return "NULL_never_fires", ev
    sig = (holm == "HOLM_SIGNIFICANT")
    if sig and np.isfinite(beta) and beta > 0:
        return "ENTRY RULE (adoption-metric edge, Holm-significant)", ev
    if sig and np.isfinite(beta) and beta < 0:
        return "VETO RULE (flagged pool is worth refusing, Holm-significant)", ev
    if P1.promotion_verdict(promo, tag, era=era, minimum=CONCENTRATOR_MIN):
        return ("WINNER CONCENTRATOR (feature candidate set only — CC-M2-9.1 "
                "disposition; ratio >= %.2f with a session-clustered interval "
                "excluding 1.0, Holm-significant in the promotion family, "
                "above the n floor)" % CONCENTRATOR_MIN), ev
    mine = [x for x in promo if x[0] == tag and x[1] == era]
    if mine and not [x for x in mine if x[9] == "TESTED"]:
        return ("NO_TEST (promotion ratios below the n floor: %d fires over %d "
                "sessions, floors %d/%d)"
                % (mine[0][6], mine[0][7], P1.PROMOTE_MIN_FIRES,
                   P1.PROMOTE_MIN_CLUSTERS)), ev
    return "NULL (no adoption edge, no inferentially supported concentration)", ev


# ------------------------------------------------------------ mirror law ----
RATIO_BOOT_SEED = 20260903                # distinct from p001's and p020's


def mirror_rows_batch3(D, res, rows):
    """R112 — every DIRECTION claim in this batch against its sign-flipped twin.

    P023 and P007 assert an OPPOSED-flow claim; P024 asserts a CONCORDANT one.
    No arm anywhere computed the sign-flipped detector and there was no
    per-session comparison at all, so a direction claim could be graded ENTRY
    RULE without ever facing its mirror.  The mirror detector here is the SAME
    detector with the flow-direction term inverted and everything else held
    fixed, compared WITHIN each session and decided by
    `m2_common.mirror_paired`.
    """
    for pid, reading, tnames, fn in READINGS:
        if pid == "P025":
            continue                       # a runway claim has no flow sign
        tag = tag_of(pid, reading)
        fire = res[tag]["fire"]
        mfire = res[tag]["mirror_fire"]
        P1.mirror_rows(D, fire, mfire, tag,
                       "flow_direction_as_specified",
                       "flow_direction_SIGN_FLIPPED", rows)
    return rows


# ------------------------------------------------------------------ report --
_fmt = P1._fmt

SUPPORT_CASES = (
    ("HG-20210705-010979-L", "P025 birth case (TOKYO long, 3h57m of runway, "
                             "cert +$1,020)"),
    ("HG-20210705-012045-L", "P025 birth case (cert +$1,138.75, MAE $0)"),
    ("HG-20210705-055113-S", "P024 birth case (the day-3 override: +$382.50 "
                             "on a $1,000 thesis, peak +$776.25)"),
    ("HG-20210705-056096-S", "P024 companion (+$145)"),
)


def _pick(rows, **kw):
    """First row whose columns match; keys are ROBUST/CENSUS column names."""
    idx = {c: i for i, c in enumerate(P1.ROBUST_COLUMNS)}
    want = [(idx[k], v) for k, v in kw.items()]
    for r in rows:
        if all(r[i] == v for i, v in want):
            return r
    return None


def report(D, res, elapsed, pins):
    L = []
    A = L.append
    A("# CENSUS BATCH 3 — P025 / P023 / P024 / P007-as-entry")
    A("")
    A("Ordered by CC-M2-12.4. Population: the frozen v3 roster, %d candidates "
      "over %d sessions (FIT %d-%d + the %d GATE echo, eval-only), all three "
      "assets. Detectors are strictly causal and read only committed "
      "pattern_lib frame fields (V1 + the V2 block this batch added: refail "
      "geometry, observed close, level confluence)."
      % (int(D["dec_sec"].size), int(D["n_sessions_total"]), FIT_YEARS[0],
         FIT_YEARS[-1], GATE_YEAR))
    A("")
    A("MULTIPLICITY: FOUR DECLARED FAMILIES, corrected SEPARATELY (R107). "
      "(1) GEE DECIDING — the detector coefficients plus `NY_ADJ` (does phase "
      "survive conditioning on runway?) and the within-band stratified tests: "
      "%d tests. (2) GEE DIAGNOSTIC — `NY_RAW` / `RW_RAW` / `RW_ADJ`, which "
      "are ALGEBRAIC RE-EXPRESSIONS of the same object: %d tests, in "
      "BATCH3_ROBUST_DIAGNOSTIC.tsv. (3) MIRROR: %d tested rows. "
      "(4) PROMOTION: %d tested rows. The previous run put all of them in ONE "
      "family of ~372, which pushed the rank-1 Holm threshold to ~1.3e-4 and "
      "screened the ONE deciding FIT coefficient against 371 rows that were "
      "either holdout-contaminated eval echoes or re-expressions of each "
      "other."
      % (len([r for r in res["robust_deciding"] if np.isfinite(r[12])]),
         len([r for r in res["robust_diagnostic"] if np.isfinite(r[12])]),
         len([r for r in res["mirror"] if r[20] == "TESTED"]),
         len([r for r in res["promotion"] if r[9] == "TESTED"])))
    A("")
    A("**READING B_observed IS INELIGIBLE FOR PROMOTION (R108, closed).** "
      "`runway_binding_sec = min(nominal, observed_close_sec - dec)` where "
      "`observed_close_sec` is the m0 receipt's `last_two_sided_sec` — the "
      "last two-sided second of the WHOLE SESSION, written by "
      "port_m0/s3_sessions.py as `idx[-1]` and UNKNOWABLE at the decision "
      "second. `triage_index.py` already masks exactly this field under "
      "--as-of. It was nonetheless run through the full CC-M2-9.1 grading "
      "pipeline and appeared in the headline table below as an ENTRY RULE "
      "candidate, and it drives P025_RUNWAY.tsv, P025_PHASE_GIVEN_RUNWAY.tsv "
      "and the B_observed half of the deciding NY-adjusted GEE — the table "
      "CC-M2-15.1's 'NY was proxying runway to the seat' ruling rests on. It "
      "is a DIAGNOSTIC: the right thing to correct a census with (D15 holiday "
      "tapes) and the wrong thing to trade on. Read A_nominal for anything "
      "that could become a rule.")
    A("")
    A("IN-SAMPLE OPTIMISM (R114). Every threshold here — VOL_FLOOR_ABS 500 "
      "('the fitted floor'), VOL_FLOOR_REL, the aggression fractions, the "
      "refail tolerances and the 9-band runway grid — was fitted on E1 study "
      "sessions INSIDE FIT, and the birth-case table at the end used to be "
      "printed as corroboration. Every table carries `FIT_EX_FITTING` beside "
      "FIT, dropping the %d threshold-fitting sessions; the difference is the "
      "optimism, and the birth-case table is a REPRODUCTION CHECK."
      % len(P1.THRESHOLD_FITTING_SESSIONS))
    A("")
    A("NOT CENSUSABLE AT ERA SCALE (named, not hidden): P007's S7 `c2f`, "
      "P024's S7 `dBsz/min vs dAsz/min` erosion and P023's S8 through-book "
      "side are MBP-1 book-event statistics; the event cache covers 488 of "
      "%d roster sessions. Those terms are absent from the detectors below "
      "and the era-scale extraction is a build item."
      % int(D["n_sessions_total"]))
    A("")

    A("## HEADLINE VERDICTS (CC-M2-9.1 vocabulary)")
    A("")
    A("| detector | reading | fires (FIT) | per session | verdict | beta_close"
      " | Holm | winner-rate x | cond-value x |")
    A("|---|---|---|---|---|---|---|---|---|")
    for pid, reading, _n, _f in READINGS:
        tag = tag_of(pid, reading)
        v, ev = res[tag]["verdict"]
        fF = res[tag]["cen"].get(("ALL", "FIT", "ALL", "ALL", "FIRE"))
        A("| %s | %s | %d | %s | %s | %s | %s | %s | %s |"
          % (pid, reading, res[tag]["n_fires_fit"],
             _fmt(fF[8], 3) if fF else ".", v.split(" (")[0],
             _fmt(ev.get("beta_close"), 1), ev.get("holm", "."),
             _fmt(ev.get("winner_rate_ratio"), 2),
             _fmt(ev.get("cond_value_ratio"), 2)))
    A("")

    # ---- P025 ------------------------------------------------------------
    A("## P025 RUNWAY_TO_BINDING_EXIT — the structural candidate")
    A("")
    A("Runway = decision second -> the BINDING exit (the CC-M2-10.3 phase-close"
      " seat). Reading A is the nominal roster runway; reading B corrects it "
      "with the m0 receipt's observed close (D15). `conc_ratio` = winner share"
      " / candidate share, so 1.00 means the band holds winners exactly in "
      "proportion to the candidates generated inside it.")
    A("")
    for reading in ("A_nominal", "B_observed"):
        A("### runway bands — %s (ALL assets, FIT)" % reading)
        A("")
        A("| band | n | cand share | winners | winner rate | conc_ratio | "
          "mean close | cond close | frac >= $1000 | mean peak | NY share |")
        A("|---|---|---|---|---|---|---|---|---|---|---|")
        for r in res["runway"]:
            if r[0] != reading or r[1] != "ALL" or r[2] != "FIT":
                continue
            A("| %s | %d | %s | %d | %s | %s | %s | %s | %s | %s | %s |"
              % (r[3], r[7], _fmt(r[8], 4), r[9], _fmt(r[12], 5),
                 _fmt(r[11], 2), _fmt(r[15], 1), _fmt(r[16], 1),
                 _fmt(r[20], 4), _fmt(r[18], 1), _fmt(r[21], 3)))
        A("")

    A("### DOES PHASE SURVIVE CONDITIONING ON RUNWAY?  (ALL assets, FIT)")
    A("")
    A("`NY_RAW` is P020's claim re-run as a GEE; `NY_ADJ` is the same "
      "coefficient with runway_hours in the model. The winner rows use a "
      "logit link because the struck claim (86 of 86) was a WINNER claim.")
    A("")
    A("| reading | test | metric | beta | se_cr1 | z | p_cr1 | Holm |")
    A("|---|---|---|---|---|---|---|---|")
    for reading in ("A_nominal", "B_observed"):
        for tag in ("P025_NY_RAW_", "P025_NY_ADJ_", "P025_RW_RAW_",
                    "P025_RW_ADJ_"):
            for metric in ("cert_close", "winner"):
                r = _pick(res["robust_all"], reading=tag + reading,
                          asset="ALL", era="FIT", metric=metric)
                if r is None:
                    continue
                A("| %s | %s | %s | %s | %s | %s | %s | %s |"
                  % (reading, tag.replace("P025_", "").rstrip("_"), metric,
                     _fmt(r[7], 4), _fmt(r[10], 4), _fmt(r[11], 2),
                     _fmt(r[12], 6), r[19] if len(r) > 19 else "."))
    A("")
    A("### the same question stratified — is_NY INSIDE each runway band "
      "(FIT, all assets)")
    A("")
    A("| band | metric | n | n_NY | beta | z | p_cr1 | Holm |")
    A("|---|---|---|---|---|---|---|---|")
    for r in res["robust_all"]:
        if not str(r[0]).startswith("P025_NY_IN_"):
            continue
        A("| %s | %s | %d | %d | %s | %s | %s | %s |"
          % (str(r[0]).replace("P025_NY_IN_", ""), r[3], r[4], r[6],
             _fmt(r[7], 4), _fmt(r[11], 2), _fmt(r[12], 6),
             r[19] if len(r) > 19 else "."))
    A("")
    A("### phase within band — the artefact control (ALL assets, FIT, "
      "reading %s)" % "B_observed")
    A("")
    A("| band | phase | n | cand share | winners | winner share | "
      "conc_ratio_in_band | winner rate | band rate |")
    A("|---|---|---|---|---|---|---|---|---|")
    for r in res["pgr"]:
        if r[0] != "B_observed" or r[1] != "ALL" or r[2] != "FIT":
            continue
        A("| %s | %s | %d | %s | %d | %s | %s | %s | %s |"
          % (r[3], r[4], r[5], _fmt(r[6], 3), r[7], _fmt(r[8], 3),
             _fmt(r[9], 2), _fmt(r[10], 5), _fmt(r[11], 5)))
    A("")

    # ---- P023 / P007 / P024 ---------------------------------------------
    for pid, title in (("P023", "P023 ABSORPTION_TWO_STREAM_ENTRY — the "
                                "repaired entry object"),
                       ("P024", "P024 REFAIL_REVERSION — direction confirmed, "
                                "magnitude failed"),
                       ("P007", "P007 ABSORPTION_NO_RESPONSE — censused AS AN "
                                "ENTRY")):
        A("## %s" % title)
        A("")
        A("| reading | era | fires | per session | mean close | cond close | "
          "mean peak | winners | winner rate | baseline winner rate | "
          "beta_close | Holm |")
        A("|---|---|---|---|---|---|---|---|---|---|---|---|")
        for p2, reading, _n, _f in READINGS:
            if p2 != pid:
                continue
            tag = tag_of(pid, reading)
            eras = [("FIT", None), ("GATE_%d" % GATE_YEAR, None)]
            eras += [(e, s) for e, s in res[tag]["gate_split"]]
            for ename, split in eras:
                if split is None:
                    fF = res[tag]["cen"].get(("ALL", ename, "ALL", "ALL",
                                              "FIRE"))
                    fN = res[tag]["cen"].get(("ALL", ename, "ALL", "ALL",
                                              "NOFIRE"))
                else:
                    fF, fN = split
                if fF is None:
                    continue
                rb = _pick(res[tag]["robust"], asset="ALL", era=ename,
                           metric="cert_close")
                A("| %s | %s | %d | %s | %s | %s | %s | %d | %s | %s | %s | %s |"
                  % (reading, ename, fF[7], _fmt(fF[8], 3), _fmt(fF[9], 1),
                     _fmt(fF[10], 1), _fmt(fF[12], 1), fF[15],
                     _fmt(fF[16], 5), _fmt(fN[16], 5) if fN else ".",
                     _fmt(rb[7], 1) if rb else ".",
                     rb[19] if rb and len(rb) > 19 else "."))
        A("")
        A("TERM MARGINALS (FIT, all assets): what each term does alone, and "
          "what the detector does with it dropped.")
        A("")
        A("| reading | term | scope | n | mean close | cond close | winners | "
          "winner rate |")
        A("|---|---|---|---|---|---|---|---|")
        for r in res["terms"]:
            if not str(r[0]).startswith(pid) or r[1] != "ALL":
                continue
            A("| %s | %s | %s | %d | %s | %s | %d | %s |"
              % (str(r[0]).replace(pid + "_", ""), r[3], r[2], r[4],
                 _fmt(r[6], 1), _fmt(r[7], 1), r[11], _fmt(r[12], 5)))
        A("")
        A("MECHANISM DESTRUCTION (each term shuffled within its session, %d "
          "replicates): `edge_retention` is the fraction of the intact edge "
          "that SURVIVES the destruction — a load-bearing term leaves little "
          "behind." % DESTRUCTION_REPS)
        A("")
        A("| reading | neutralised term | intact fires | intact edge | "
          "destroyed edge | retention | verdict |")
        A("|---|---|---|---|---|---|---|")
        for r in res["destr"]:
            if not str(r[0]).startswith(pid) or r[1] != "ALL":
                continue
            A("| %s | %s | %d | %s | %s | %s | %s |"
              % (str(r[0]).replace(pid + "_", ""), r[2], r[12], _fmt(r[14], 1),
                 _fmt(r[7], 1), _fmt(r[17], 2), r[19]))
        A("")
        if pid == "P024":
            A("### DIRECTION vs MAGNITUDE (the day-3 verdict, censused)")
            A("")
            A("| reading | era | group | n | posfrac (direction) | cond close "
              "| median close | frac >= $1000 | mean peak - mean close | "
              "winners |")
            A("|---|---|---|---|---|---|---|---|---|---|")
            for r in res["mag"]:
                if r[1] != "ALL":
                    continue
                A("| %s | %s | %s | %d | %s | %s | %s | %s | %s | %d |"
                  % (r[0], r[2], r[3], r[4], _fmt(r[6], 4), _fmt(r[8], 1),
                     _fmt(r[9], 1), _fmt(r[10], 4), _fmt(r[13], 1), r[14]))
            A("")

    # ---- the birth cases -------------------------------------------------
    A("## THE BIRTH CASES — REPRODUCTION CHECK, NOT EVIDENCE (R114)")
    A("")
    A("These sessions are inside FIT and are among the sessions the "
      "thresholds were fitted on. 'Does the detector still fire on the case "
      "it was written from?' is a reproduction check. Read FIT_EX_FITTING for "
      "evidence.")
    A("")
    A("| cid | what it is | detectors that fire |")
    A("|---|---|---|")
    for cid, what in SUPPORT_CASES:
        hits = res["birth"].get(cid, [])
        A("| %s | %s | %s |" % (cid, what, ", ".join(hits) if hits else
                                "**none**"))
    A("")

    A("## PROVENANCE")
    A("")
    A("* elapsed %.1fs; pins %s" % (elapsed, "HELD" if not pins else pins))
    A("* **D-058 PRE-EXAM HOLDOUT — EXCLUDED, NOT FLAGGED (R105, closed).** "
      "%d holdout sessions (>= %d) were QUARANTINED out of this census by "
      "`pattern_lib.sessions_fit`. THE PREVIOUS RUN OF THIS FILE FLAGGED THE "
      "HOLDOUT AT THE WRONG BOUNDARY — `>= 20250901` — and that understated "
      "number is what its receipt stamped and this paragraph printed "
      "('sessions from 2025-09-01 onward'), omitting July and August 2025 and "
      "handing the adjudicator an understated contamination figure. That was "
      "the one number the 'flag, not a filter' defence rested on. It is now a "
      "filter, at the ONE boundary in `m2_common.HOLDOUT_FROM_D8`, and the "
      "correct H1/H2 split that already existed at `_era_masks` but was "
      "applied ONLY in `runway_rows` is moot: there is no H2 left to pool. "
      "The eval era is named GATE_%dH1 because it is a half-year."
      % (int(D["n_quarantined_holdout"]), MC.HOLDOUT_FROM_D8, GATE_YEAR))
    A("* RUNWAY BAND REFUSALS (R110, closed): %s. Refused and NEGATIVE runways "
      "used to be deposited in `b0_lt15m`, indistinguishable from a genuine "
      "sub-15-minute runway, with no refusal band and no refusal count — in "
      "the very tables the P025 ruling turns on. Reading B additionally bands "
      "REFUSED the %d candidates whose m0 receipt carries no "
      "`last_two_sided_sec`, where reading B silently degenerated into "
      "reading A."
      % (", ".join("%s: %d refused / %d banded"
                   % (k, v["n_refused"], v["n_banded"])
                   for k, v in sorted(res["band_report"].items())),
         int(D["runway_binding_refused"].sum())))
    A("* outputs: BATCH3_{CENSUS,TERMS,DESTRUCTION,ROBUST,ROBUST_DIAGNOSTIC,"
      "MIRROR,PROMOTION}.tsv, P025_RUNWAY.tsv, "
      "P025_PHASE_GIVEN_RUNWAY.tsv, P024_MAGNITUDE.tsv")
    A("")
    return "\n".join(L) + "\n"


# ------------------------------------------------------------------ main ----
def build(workers=4, limit_sessions=None, out_dir=None):
    t0 = time.time()
    MC.verify_spec(force=True)
    OUT = out_dir or OUT_DIR
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    D = scan(workers=workers, limit_sessions=limit_sessions)
    fit = np.isin(D["year"], FIT_YEARS)
    res = {}
    census, terms, destr, mag = [], [], [], []
    robust_nc = []          # the DECIDING family (R107) — un-Holmed here
    diagnostic_nc = []      # the algebraic re-expressions, a SEPARATE family
    promo, mirror = [], []  # two FURTHER declared families
    birth = {}
    cid_all = np.array(["%s-%08d-%06d-%s" % (a, d, s, "L" if v > 0 else "S")
                        for a, d, s, v in zip(D["asset"].tolist(),
                                              D["d8"].tolist(),
                                              D["dec_sec"].tolist(),
                                              D["side"].tolist())])
    birth_idx = {c: int(np.nonzero(cid_all == c)[0][0])
                 for c, _w in SUPPORT_CASES
                 if np.any(cid_all == c)}
    for cid in birth_idx:
        birth[cid] = []

    for pid, reading, tnames, _fn in READINGS:
        tag = tag_of(pid, reading)
        T = P1.unbits(D["terms_" + tag], len(tnames))
        fire = np.all(T, axis=1)
        rows_c = P1.census_rows(D, fire, tag)
        rows_t = P1.term_rows(D, T, tag, tnames)
        # R116: the DECLARED seed is the one actually used, and the stream is
        # keyed on the READING so the nine readings no longer draw
        # byte-identical permutations from each other or from p001/p020.
        rows_d = P1.destruction_rows(D, T, tag, tnames, seed=DESTRUCTION_SEED)
        rows_r = P1.robust_rows(D, fire, tag, holm=False)
        P1.promotion_rows(D, fire, tag, promo, seed=RATIO_BOOT_SEED)
        res[tag] = {"pid": pid, "reading": reading, "tag": tag,
                    "fire": fire,
                    "mirror_fire": np.all(
                        P1.unbits(D["mterms_" + tag], len(tnames)), axis=1),
                    "terms": rows_t, "destr": rows_d,
                    "robust": rows_r,
                    "n_fires": int(fire.sum()),
                    "n_fires_fit": int((fire & fit).sum()),
                    "cen": {(x[1], x[2], x[3], x[4], x[5]): x for x in rows_c}}
        # R114: the in-sample split (FIT vs FIT with the threshold-fitting
        # sessions dropped), in CENSUS_COLUMNS layout.  This slot used to hold
        # the GATE H1/H2 split; the holdout is EXCLUDED at enumeration now, so
        # there is no H2 and the honest extra row is the in-sample one.
        gs = []
        for ename, esel in _era_masks(D)[1:2]:
            pair = []
            for group, gsel in (("FIRE", fire), ("NOFIRE", ~fire)):
                m = esel & gsel
                pair.append(P1._row(tag, "ALL", ename, "ALL", "ALL", group,
                                    P1._stats(D["cert_close"][m],
                                              D["cert_peak"][m],
                                              D["winner"][m],
                                              # MINOR (3.2b): this used to be
                                              # the STRATUM's session count,
                                              # reported on every cell inside
                                              # it, so the column did not
                                              # describe its own row
                                              len(set(D["cluster"][m]
                                                      .tolist()))))
                            if m.any() else None)
            gs.append((ename, tuple(pair)))
        res[tag]["gate_split"] = gs
        census += rows_c
        terms += rows_t
        destr += rows_d
        robust_nc += rows_r
        for cid, i in birth_idx.items():
            if fire[i]:
                birth[cid].append(tag)
        if pid == "P024":
            magnitude_rows(D, fire, tag, mag)
        MC.hb("batch3 %s: %d fires (%d FIT)"
              % (tag, int(fire.sum()), int((fire & fit).sum())))

    # ---- P025's own objects ---------------------------------------------
    runway = []
    pgr = []
    band_report = {}
    for reading, key in (("A_nominal", "runway_phase_sec"),
                         ("B_observed", "runway_binding_sec")):
        # R110: reading B additionally bands REFUSED wherever the m0 receipt
        # carried no last_two_sided_sec, so a runway that silently DEGENERATED
        # into the nominal one is no longer read as an observed runway.
        band = band_index(D[key],
                          refused=(D["runway_binding_refused"]
                                   if reading == "B_observed" else None))
        band_report[reading] = band_counts(band)
        runway_rows(D, band, reading, runway)
        phase_given_runway_rows(D, band, reading, pgr)
        # R107: the deciding coefficient is NY_ADJ — "does phase survive
        # conditioning on runway?".  NY_RAW / RW_RAW / RW_ADJ are the same
        # object re-expressed, and folding all four x 3 metrics x 4 assets x 3
        # eras x 2 readings into one family put the rank-1 threshold at ~1e-4
        # and screened the ONE deciding coefficient against hundreds of
        # algebraic siblings.  NY_ADJ and the stratified within-band tests are
        # the DECIDING family; the re-expressions are a SEPARATE, declared
        # DIAGNOSTIC family and are labelled as such in the TSV.
        adj = phase_adjustment_rows(D, D[key], reading)
        robust_nc += [r for r in adj if str(r[0]).startswith("P025_NY_ADJ_")]
        diagnostic_nc += [r for r in adj
                          if not str(r[0]).startswith("P025_NY_ADJ_")]
        robust_nc += phase_in_band_rows(D, band, reading)
    res["runway"] = runway
    res["pgr"] = pgr
    res["birth"] = birth
    res["band_report"] = band_report

    mirror_rows_batch3(D, res, mirror)

    # FOUR declared families, corrected SEPARATELY (R107)
    P1._holm(robust_nc)
    P1._holm(diagnostic_nc)
    P1.holm_mirror(mirror)
    P1.holm_promotion(promo)
    res["robust_all"] = robust_nc + diagnostic_nc
    res["robust_deciding"] = robust_nc
    res["robust_diagnostic"] = diagnostic_nc
    res["mirror"] = mirror
    res["promotion"] = promo
    for pid, reading, _n, _f in READINGS:
        tag = tag_of(pid, reading)
        res[tag]["robust"] = [r for r in robust_nc if r[0] == tag]
        res[tag]["verdict"] = grade(res[tag], res[tag]["cen"], promo)
    res["terms"] = terms
    res["destr"] = destr
    res["mag"] = mag

    phash = MC.params_hash(PARAMS)
    extra = ["CC-M2-12.4 census batch 3 — P025/P023/P024/P007-as-entry, "
             "strictly causal detectors over the frozen v3 roster",
             "BOTH CC-M1-8 certificate readings are reported on every row",
             "Holm-Bonferroni is applied over the WHOLE batch, not per pattern",
             "S7 c2f / S7 erosion / S8 through-book side are NOT censusable at "
             "era scale (MBP-1 event cache covers 488 of 3,734 sessions)"]
    MC.write_tsv(os.path.join(OUT, "BATCH3_CENSUS.tsv"), SECTION, phash,
                 list(P1.CENSUS_COLUMNS), census, extra=extra)
    MC.write_tsv(os.path.join(OUT, "BATCH3_TERMS.tsv"), SECTION, phash,
                 list(P1.TERM_COLUMNS), terms, extra=extra)
    MC.write_tsv(os.path.join(OUT, "BATCH3_DESTRUCTION.tsv"), SECTION,
                 phash, list(P1.DESTRUCTION_COLUMNS), destr, extra=extra)
    MC.write_tsv(os.path.join(OUT, "BATCH3_ROBUST.tsv"), SECTION, phash,
                 list(P1.ROBUST_COLUMNS), robust_nc,
                 extra=extra + ["R107: this is the DECIDING family — the "
                                "detector coefficients, NY_ADJ (phase "
                                "conditioned on runway) and the within-band "
                                "stratified tests. Holm runs over THIS set."])
    MC.write_tsv(os.path.join(OUT, "BATCH3_ROBUST_DIAGNOSTIC.tsv"), SECTION,
                 phash, list(P1.ROBUST_COLUMNS), diagnostic_nc,
                 extra=["R107: NY_RAW / RW_RAW / RW_ADJ — ALGEBRAIC "
                        "RE-EXPRESSIONS of the deciding coefficient, kept for "
                        "reading and Holm-corrected as their OWN family. They "
                        "used to sit in the deciding family and inflate m to "
                        "~372."])
    MC.write_tsv(os.path.join(OUT, "BATCH3_MIRROR.tsv"), SECTION, phash,
                 list(P1.MIRROR_COLUMNS), mirror,
                 extra=["R112 MIRROR LAW: P023/P007's OPPOSED-flow claim and "
                        "P024's CONCORDANT-flow claim against the SAME "
                        "detector with the flow direction SIGN-FLIPPED, "
                        "paired WITHIN the session, decided by "
                        "m2_common.mirror_paired",
                        "verdict=NO_TEST below the power floor",
                        "this table is its OWN declared Holm family"])
    MC.write_tsv(os.path.join(OUT, "BATCH3_PROMOTION.tsv"), SECTION, phash,
                 list(P1.PROMOTION_COLUMNS), promo,
                 extra=["R106: every promotion ratio carries a "
                        "session-clustered bootstrap interval, an n floor on "
                        "the numerator and Holm membership in this table's own "
                        "declared family",
                        "P025_B_observed is INELIGIBLE for promotion (R108) — "
                        "it is built from an end-of-session aggregate"])
    MC.write_tsv(os.path.join(OUT, "P025_RUNWAY.tsv"), SECTION, phash,
                 list(RUNWAY_COLUMNS), runway,
                 extra=["conc_ratio = winner share / candidate share inside "
                        "the (asset, era) stratum; 1.00 = the band holds "
                        "winners in proportion to the candidates generated "
                        "inside it",
                        "R110: band REFUSED is a REAL BAND with its own rows. "
                        "Refused and negative runways used to be deposited in "
                        "b0_lt15m with no refusal band and no count",
                        "reading B_observed is a DIAGNOSTIC built from an "
                        "end-of-session aggregate (R108) — never an entry "
                        "rule"])
    MC.write_tsv(os.path.join(OUT, "P025_PHASE_GIVEN_RUNWAY.tsv"), SECTION,
                 phash, list(PGR_COLUMNS), pgr,
                 extra=["phase_dec as a CONTROL: the phase breakdown INSIDE "
                        "each runway band, which is where P020's 86/86 has to "
                        "survive if it is a phase fact"])
    MC.write_tsv(os.path.join(OUT, "P024_MAGNITUDE.tsv"), SECTION, phash,
                 list(MAG_COLUMNS), mag,
                 extra=["direction = posfrac_close; magnitude = cond_close / "
                        "frac_ge_1000; peak_minus_close = the give-back the "
                        "phase-close exit hands back"])
    pins = MC.pins_moved()
    el = time.time() - t0
    MC.write_text(os.path.join(OUT, "BATCH3_CENSUS_REPORT.md"),
                  report(D, res, el, pins))
    MC.write_json(os.path.join(OUT, "p025_census.receipt.json"),
                  {"env": MC.env_receipt(PARAMS),
                   "n_candidates": int(D["dec_sec"].size),
                   "n_sessions": int(D["n_sessions_total"]),
                   "holdout_from_d8": int(MC.HOLDOUT_FROM_D8),
                   "n_holdout_sessions_quarantined":
                       int(D["n_quarantined_holdout"]),
                   "runway_band_refusals": res["band_report"],
                   "n_runway_binding_refused":
                       int(D["runway_binding_refused"].sum()),
                   "n_cert_refused": int(D["cert_refused"].sum()),
                   "not_promotable": sorted(NOT_PROMOTABLE),
                   "destruction_seed_declared": DESTRUCTION_SEED,
                   "n_fires": {tag_of(p[0], p[1]):
                               res[tag_of(p[0], p[1])]["n_fires"]
                               for p in READINGS},
                   "n_fires_fit": {tag_of(p[0], p[1]):
                                   res[tag_of(p[0], p[1])]["n_fires_fit"]
                                   for p in READINGS},
                   "verdicts": {tag_of(p[0], p[1]):
                                res[tag_of(p[0], p[1])]["verdict"][0]
                                for p in READINGS},
                   "holm_families": {
                       "GEE_DECIDING": int(len([r for r in robust_nc
                                                if np.isfinite(r[12])])),
                       "GEE_DIAGNOSTIC": int(len([r for r in diagnostic_nc
                                                  if np.isfinite(r[12])])),
                       "MIRROR": int(len([r for r in mirror
                                          if r[20] == "TESTED"])),
                       "PROMOTION": int(len([r for r in promo
                                             if r[9] == "TESTED"]))},
                   "elapsed_sec": el, "pins_moved": pins, "out_dir": OUT})
    MC.hb("batch3 census: %s, %.1fs"
          % (", ".join("%s=%d" % (tag_of(p[0], p[1]),
                                  res[tag_of(p[0], p[1])]["n_fires"])
                       for p in READINGS), el))
    return res


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--limit-sessions", type=int, default=None)
    # A --limit-sessions SMOKE RUN must never overwrite the committed census.
    # The default out dir is refused whenever the population is truncated;
    # --out-dir is how a development run says where its scratch goes.
    p.add_argument("--out-dir", default=None)
    a = p.parse_args()
    if a.workers > 4:
        raise SystemExit("workers capped at 4 (a reader lane is live)")
    if a.limit_sessions and not a.out_dir:
        raise SystemExit("--limit-sessions is a SMOKE RUN and must be given "
                         "--out-dir: it would otherwise overwrite the "
                         "committed census with a truncated population")
    build(workers=a.workers, limit_sessions=a.limit_sessions,
          out_dir=a.out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
