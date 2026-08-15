#!/usr/bin/python3
"""PORT M3 — THE FEATURE MATRIX at candidate grain over the v3 roster.

    "FEATURE MATRIX BUILD at candidate grain over the v3 roster (holdout
     excluded by the guarded enumerator): the census-validated set ... ALL
     strictly causal (the fixed pattern_lib is the source; availability-lagged
     context).  Deterministic, receipted, D-018 paths."           — the brief

WHERE EVERY NUMBER COMES FROM
  The fixed `pattern_lib.frame` is THE source of the per-row causal state
  (D-006 formula fidelity: this module defines NO second version of anything it
  can import).  Four helpers are imported verbatim from the census lanes rather
  than re-typed:
     batch5_census._s10_of          d_POC / in_VA off the causal profile
     batch5_census._unspent_session S3 COVERAGE SESSION `unspent`
     batch5_census._event_stats     S7 c2f / erosion + S8 through-book
     batch4_census._mins_to_release signed minutes to the nearest release
  The forecaster, the news-distance census and the cross-asset states are
  joined AVAILABILITY-LAGGED here, each with its own guard.

THE THREE JOINS AND THEIR AVAILABILITY LAWS
  FORECASTER  regime_forecast/forecast_{ASSET}.tsv carries three anchors per
              session (OPEN / LONDON_OPEN / NY_OPEN).  A row reads the LATEST
              anchor with anchor_sec <= dec_sec, and nothing else.  There is no
              2021 output at all (CC-M2-17.2: the expanding-window warm-up), so
              E1 rows are TYPED-MISSING with `fc_available = 0` — declared, not
              imputed.
  NEWS        news_compliance/NEWS_DISTANCE.tsv, joined on cid.  Absence from
              the census means "no scheduled release within +/-15min", which is
              a fact about the calendar, not a missing value.
  CROSS-ASSET the most recent CLOSED cell of each asset whose LAST CANDIDATE
              ROW sits at or before this row's own epoch second (batch4's own
              causality law, moved from cell grain to row grain).  The own-asset
              leg is kept as the P009 control (batch4 R76: step back past self).

TARGETS (the brief)
  y_retg_rank_phase   THE ATLAS CHAMPION.  retg|e30|sess_close, rank-within-unit
                      at the PHASE unit — the one rank cell that is top-of-class
                      for all three assets in atlas v3 (SI rank 6 / HG rank 3 /
                      NKD rank 2, ATLAS_V3_REPORT.md).  §2.5's ruling is carried
                      exactly: the RANK TRANSFORM of the label is the target and
                      the fit objective stays reg:squarederror — the ranking
                      OBJECTIVE lost every matched cell and is not used.
  y_winner            the walled winner indicator (D-021: cert_close >= $1,000
                      AND MAE <= $300 AND not walled), refusals excluded from
                      both halves (R122).
  y_t1_episode/cell   the CC-M2-2.2(b) T1 PAIRWISE-PREFERENCE label, in its
                      pointwise-sufficient Borda form: the share of the row's
                      own group it beats on the walled phase-close certificate.
                      Group = the frozen EPISODE_CAUSAL episode (primary) and
                      the (asset, phase) CELL (the variant).

Run:
  m3_matrix.py --build [--workers N] [--assets SI HG NKD] [--limit N]
  m3_matrix.py --describe
"""
import argparse
import multiprocessing as mp
import os
import sys
import time

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, "/workspace/engine/port_m0", "/workspace/engine/port_m1",
           "/workspace/engine/port_m2"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import m3_common as M3                    # noqa: E402
import m2_common as MC                    # noqa: E402
import common as C                        # noqa: E402
import assemble as A                      # noqa: E402
import pattern_lib as PL                  # noqa: E402
import batch4_census as B4                # noqa: E402
import batch5_census as B5                # noqa: E402
import episode_v2 as EV                   # noqa: E402
import baseline_replay as BR              # noqa: E402

SECTION = "M3.1 feature matrix (candidate grain, v3 roster)"

REGIME_ROOT = os.path.join(MC.M2_ROOT, "regime_forecast")
NEWS_DISTANCE = os.path.join(MC.M2_ROOT, "news_compliance", "NEWS_DISTANCE.tsv")

FC_ANCHOR_SEC = {"OPEN": 0, "LONDON_OPEN": 28800, "NY_OPEN": 43200}

# ============================================================ the registry ===
class Feat(object):
    """One matrix column, declared before it can exist."""
    __slots__ = ("name", "group", "sources", "doc")

    def __init__(self, name, group, sources, doc):
        self.name = name
        self.group = group
        self.sources = tuple(sources)
        self.doc = doc


def _F(name, group, sources, doc):
    return Feat(name, group, sources.split() if isinstance(sources, str)
                else sources, doc)


# GROUPS.  `teacher_evidence` is DECLARED AND EMPTY — that is the D-078 test
# instrument: the coming teacher round's features join this group and their
# marginal value is read against this exact harness, this exact matrix.
GROUPS = ("class", "seat", "runway", "p030_p033", "clock", "news", "level",
          "event", "fuel_poc", "xasset", "forecast", "regime", "era",
          "flow", "geometry", "episode", "teacher_evidence")

FEATURES = []


def _reg(*feats):
    FEATURES.extend(feats)


# ---- class one-hots + family / rung / level-family / flag bits -------------
for _k in MC.CLASS_ORDER + (MC.CLASS_UNKNOWN,):
    _reg(_F("cls_" + _k.replace("-", "_"), "class", "klass",
            "D-071 declared class one-hot (a partition, CC-M1-11.4 priority)"))
for _f in MC.FAMILIES:
    _reg(_F("fam_" + _f, "class", "fam_mask",
            "generation-v3 family tag bit (%s)" % MC.display_name(_f)))
for _i, _r in enumerate(MC.RUNGS):
    _reg(_F("rung_%g" % _r, "class", "rung_mask", "S3 ATR rung bit"))
for _lf in MC.KEPT_LEVEL_FAMILIES:
    _reg(_F("levfam_" + _lf, "level", "level_fam_mask",
            "KEPT level-family tag at the candidate's level"))
for _fn, _b in MC.FLAG_NAMES:
    _reg(_F("flag_" + _fn, "level", "flags",
            "generation flag bit (OR_EXT beyond / first-test virgin)"))

# ---- rolling seat state ----------------------------------------------------
_reg(
    _F("rv1800_usd", "seat", "rv1800_usd",
       "CC-M2-19.1 THE rolling seat anchor: row-grain rv1800 nowcast"),
    _F("rv60_usd", "seat", "rv60_usd", "S9 rv nowcast, 60s"),
    _F("rv_ratio", "seat", "rv_ratio", "rv1800 / rv60 (P013 marker)"),
    _F("unspent_sess_usd", "seat", "unspent_sess",
       "CC-M2-19.4 resurrected: S3 COVERAGE SESSION unspent = "
       "exp_move_q50(SESSION) - range so far"),
    _F("exp_move_q50_phase_usd", "seat", "exp_move_q50_phase_usd",
       "the phase fvol row's expected move (the coverage denominator)"),
    _F("coverage_phase", "seat", "coverage_phase", "S3 COVERAGE, phase clock"),
    _F("coverage_session", "seat", "coverage_session", "S3 COVERAGE, session"),
    _F("cell_rv1800_at_open", "p030_p033", "rv1800_usd cell_open",
       "P030 CELL_VOL_CONCENTRATION raw component: rv1800 read at the cell's "
       "FIRST candidate row (a continuous feature, never a gate — CC-M2-18.2)"),
    _F("cell_unspent_at_open", "p030_p033", "unspent_sess cell_open",
       "the cell-open twin of unspent_sess (SI's per-asset anchor, CC-M2-21.1)"),
)

# ---- runway to seat --------------------------------------------------------
_reg(
    _F("runway_phase_sec", "runway", "runway_phase_sec",
       "CC-M2-15.1 runway_to_seat: phase_close_sec - dec_sec"),
    _F("runway_sess_sec", "runway", "runway_sess_sec", "sess_close - dec_sec"),
    _F("runway_frac", "runway", "runway_frac", "runway / phase segment length"),
    _F("phase_age_sec", "runway", "phase_age_sec", "dec_sec - phase start"),
    _F("session_close_exit", "runway", "session_close_exit",
       "the S13 exit_default IS the session close"),
    _F("p033_product", "p030_p033", "runway_phase_sec rv1800_usd",
       "P033 FEASIBILITY_IS_RUNWAY_TIMES_VOL raw product (CC-M2-19.3: "
       "census-first, never traded raw)"),
    _F("p033_sqrt", "p030_p033", "runway_phase_sec rv1800_usd",
       "the P033 sqrt form (batch5's second form)"),
)

# ---- P020 clock structure --------------------------------------------------
for _p in M3.PHASE_NAMES:
    _reg(_F("phase_" + _p, "clock", "phase_dec",
            "P020 clock structure: decision-phase one-hot"))
_reg(
    _F("clock_sec", "clock", "clock_sec", "clock-of-day (UTC seconds)"),
    _F("clock_sin", "clock", "clock_sec", "sin(2*pi*clock/86400)"),
    _F("clock_cos", "clock", "clock_sec", "cos(2*pi*clock/86400)"),
    _F("dec_sec", "clock", "dec_sec", "decision second on the session clock"),
    _F("dow", "era", "dow", "day-of-week (Mon=0, calendar)"),
    _F("is_monday", "era", "dow", "dow == 0"),
    _F("is_friday", "era", "dow", "dow == 4"),
)

# ---- US_CLOCK / POST_NEWS + release distances ------------------------------
_reg(
    _F("mins_to_release", "news", "mins_to_release",
       "D-077-UPDATE signed minutes to the NEAREST scheduled release "
       "(>0 = after it); NaN = the calendar carries none"),
    _F("abs_mins_to_release", "news", "mins_to_release", "|mins_to_release|"),
    _F("in_news_window", "news", "mins_to_release",
       "D-077-UPDATE restricted window |m| <= 10min (the hard veto's flag)"),
    _F("post_news_10_20", "news", "mins_to_release",
       "CC-M2-22.2 POST_NEWS: entry in [+10,+20)min after a dated release"),
    _F("pre_release_window", "news", "mins_to_release",
       "inside the window and BEFORE the release"),
    _F("release_age_sec", "news", "release_age_sec",
       "S12 last_scheduled age; -1 = no prior scheduled release"),
    _F("event_in_phase", "news", "event_in_phase",
       "the release landed inside the running phase before the decision"),
    _F("sched_release_in_phase", "news", "sched_release_in_phase",
       "a scheduled release falls inside the phase segment (calendar-only, "
       "knowable at the cell open, D-057 SCHEDULE_EXEMPT)"),
    _F("nd_in_census", "news", "nd_in_census",
       "the cid is in NEWS_DISTANCE.tsv (a release within +/-15min)"),
    _F("nd_mins_to_next", "news", "nd_minutes_to_next_release",
       "census minutes to the NEXT scheduled release"),
    _F("nd_mins_since_any", "news", "nd_minutes_since_last_release_any",
       "census unbounded age of the last scheduled release"),
    _F("nd_held_into_window", "news", "nd_held_into_window",
       "the default exit would hold the position INTO a restricted window"),
    _F("nd_gen_anchor_dated", "news", "nd_gen_anchor_is_dated_release",
       "the generating anchor sits on a dated release (CC-M2-22.1's 19%)"),
    _F("fev_n", "news", "fev_n", "event-anchored trade count since the release"),
    _F("fev_vol", "news", "fev_vol", "event-anchored traded volume"),
    _F("fev_sflow_signed", "news", "fev_sflow side",
       "event-anchored signed flow, signed BY THE TRADE'S OWN SIDE"),
)

# ---- level context ---------------------------------------------------------
_reg(
    _F("level_dist_atr", "level", "level_dist_atr",
       "|nearest KEPT-family level - entry_mid| / ATR, birth-guarded"),
    _F("n_conf_fam_at_refail", "level", "n_conf_fam_at_refail",
       "distinct KEPT families within 1 tick of the refail price"),
    _F("n_conf_fam_at_refail_2t", "level", "n_conf_fam_at_refail_2t",
       "the same at a 2-tick tolerance"),
    _F("refail_gap_sec", "level", "refail_gap_sec",
       "P024 refail geometry: seconds between the last two causal pivots of "
       "the faded type"),
    _F("refail_dist_usd", "level", "refail_dist_usd", "their price gap ($)"),
    _F("refail_age_sec", "level", "refail_age_sec", "age of the newer pivot"),
    _F("pivot_age_sec", "level", "pivot_age_sec",
       "age of the most recent CAUSAL ZigZag pivot of the faded type"),
    _F("n_level_fams", "level", "level_fam_mask",
       "how many KEPT families the candidate's level carries"),
)

# ---- through-book + c2f event statistics -----------------------------------
_reg(
    _F("thru_n", "event", "thru_n",
       "CC-M2-21.5 THE one paying event concentrator: 600s through-book print "
       "count (1.50x, GATE-replicating, destruction-surviving)"),
    _F("thru_bid", "event", "thru_bid", "through-book prints below the bid"),
    _F("thru_ask", "event", "thru_ask", "through-book prints above the ask"),
    _F("thru_imb", "event", "thru_bid thru_ask", "(bid - ask) / (bid + ask)"),
    _F("c2f_60", "event", "c2f_60",
       "S7 cancel-to-fill over 60s — CC-M2-21.5 records it INVERTED, so the "
       "sign is the model's to learn and the finding is on the record"),
    _F("c2f_300", "event", "c2f_300", "S7 cancel-to-fill over 300s"),
    _F("dbsz_min", "event", "dbsz_min", "L1 bid-size erosion per minute"),
    _F("dasz_min", "event", "dasz_min", "L1 ask-size erosion per minute"),
    _F("erosion_with_side", "event", "dbsz_min dasz_min side",
       "the erosion term on the side the trade fades (state only — "
       "CC-M2-21.5 bars the SIDE reading, never the field)"),
    _F("n_ev_60", "event", "n_ev_60", "raw MBP-1 record count in the 60s window"),
)

# ---- fuel / POC ------------------------------------------------------------
_reg(
    _F("fuel_above", "fuel_poc", "fuel_above", "S8 fuel map, trapped above mid"),
    _F("fuel_below", "fuel_poc", "fuel_below", "S8 fuel map, trapped below mid"),
    _F("fuel_total", "fuel_poc", "fuel_total", "S8 phase total volume"),
    _F("fuel_share_above", "fuel_poc", "fuel_above fuel_total", "above/total"),
    _F("fuel_share_with", "fuel_poc", "fuel_above fuel_below side",
       "the fuel share sitting AGAINST the trade's direction"),
    _F("d_poc_usd", "fuel_poc", "d_poc",
       "S10 developing-profile d_POC in dollars (CC-M2-21.2: the geometry "
       "field enters the FEATURE set; the side reading is barred)"),
    _F("in_va", "fuel_poc", "in_va", "S10 inside the developing value area; "
       "-1 = REFUSED (never 'outside')"),
)

# ---- cross-asset (P031-class raw fields, alive as information CC-M2-24.3) ---
for _a in M3.ASSET_ORDER:
    _reg(
        _F("xa_%s_age_sec" % _a, "xasset", "xa_age",
           "seconds since %s's most recent CLOSED cell (own asset = the P009 "
           "prior-cell control, batch4 R76)" % _a),
        _F("xa_%s_rv1800" % _a, "xasset", "xa_rv1800",
           "%s's rv1800 at that cell's last candidate row" % _a),
        _F("xa_%s_fuel_share_above" % _a, "xasset", "xa_fuel_share_above",
           "P031 CROSS_ASSET_FUEL_OVERHANG raw component from %s" % _a),
        _F("xa_%s_range_so_far" % _a, "xasset", "xa_range_so_far",
           "%s's session range so far at that row" % _a),
        _F("xa_%s_slope5m" % _a, "xasset", "xa_slope5m",
           "%s's 5-minute slope at that row" % _a),
        _F("xa_%s_sflow_phase" % _a, "xasset", "xa_sflow_phase",
           "%s's cumulative phase signed flow at that row" % _a),
    )

# ---- guarded forecaster outputs (2022+, typed-missing before) --------------
_reg(
    _F("fc_available", "forecast", "fc_available",
       "an admissible forecaster anchor exists for this row (0 on ALL of E1 — "
       "CC-M2-17.2: the forecaster legitimately has no 2021 output)"),
    _F("fc_anchor_age_sec", "forecast", "fc_anchor_age_sec",
       "dec_sec - anchor_sec of the anchor actually read"),
    _F("fc_p_expansion", "forecast", "fc_p_expansion", "P(EXPANSION day type)"),
    _F("fc_range_hat_usd", "forecast", "fc_range_hat_usd", "forecast range"),
    _F("fc_range_hat_q10", "forecast", "fc_range_hat_q10", "its q10"),
    _F("fc_range_hat_q90", "forecast", "fc_range_hat_q90", "its q90"),
    _F("fc_range_vs_trailing", "forecast", "fc_range_hat_vs_trailing",
       "range_hat / the trailing median"),
    _F("fc_share_TOKYO", "forecast", "fc_share_hat_TOKYO", "phase share hat"),
    _F("fc_share_LONDON", "forecast", "fc_share_hat_LONDON", "phase share hat"),
    _F("fc_share_NY", "forecast", "fc_share_hat_NY", "phase share hat"),
    _F("fc_menu_hat", "forecast", "fc_menu_hat", "forecast menu size"),
    _F("fc_bench_base_rate", "forecast", "fc_bench_base_rate", "its benchmark"),
    _F("fc_bench_persistence", "forecast", "fc_bench_persistence", "benchmark"),
    _F("fc_bench_range_trailmed", "forecast", "fc_bench_range_trailmed",
       "trailing-median range benchmark"),
    _F("fc_n_feature_missing", "forecast", "fc_n_feature_missing",
       "how many of the forecaster's own inputs were missing"),
)

# ---- regime keys -----------------------------------------------------------
_reg(
    _F("regime_tercile", "regime", "regime_tercile",
       "S2 regime tag LOW/MID/HIGH -> 0/1/2; -1 = missing"),
    _F("day_type", "regime", "day_type",
       "S2 day_type_so_far 0 INSIDE / 1 AT_RANGE / 2 EXPANDED; -1 REFUSED"),
    _F("day_type_frac", "regime", "day_type_frac", "range so far / range_hat"),
    _F("ladder_band", "regime", "ladder_band", "S9 ladder position ordinal"),
    _F("surprise", "regime", "surprise", "S9 phase realized range / range_hat"),
    _F("range_hat_usd", "regime", "range_hat_usd", "the phase fvol range_hat"),
    _F("range_so_far_usd", "regime", "range_so_far_usd", "SANE session range"),
    _F("atr_usd", "regime", "atr_usd", "ATR14_prev"),
    _F("spread_dec_usd", "regime", "spread_dec_usd", "spread at decision"),
    _F("spread_ratio", "regime", "spread_ratio",
       "spread / the STRICTLY PRIOR year's phase median (R119)"),
    _F("dom_share", "regime", "dom_share", "front-month dominance share"),
)

# ---- era / asset -----------------------------------------------------------
for _a in M3.ASSET_ORDER:
    _reg(_F("asset_" + _a, "era", "asset", "asset one-hot"))
_reg(
    _F("era_ord", "era", "d8", "era ordinal E1..E8 (1..8) — walk-forward index"),
    _F("month", "era", "d8", "calendar month of the trade date"),
)

# ---- flow / price geometry -------------------------------------------------
_reg(
    _F("side", "flow", "side", "+1 LONG / -1 SHORT"),
    _F("slope_1m_usd", "flow", "slope_1m_usd", "S5 last-minute mid slope"),
    _F("slope_5m_usd", "flow", "slope_5m_usd", "S5 5-minute slope, $/min"),
    _F("accel_usd", "flow", "accel_usd", "S5 accel(1m-5m)"),
    _F("slope_1m_with", "flow", "slope_1m_usd side", "slope signed by the side"),
    _F("slope_5m_with", "flow", "slope_5m_usd side", "slope signed by the side"),
    _F("f60_n", "flow", "f60_n", "S8 60s trade count"),
    _F("f60_vol", "flow", "f60_vol", "S8 60s volume"),
    _F("f60_sflow_with", "flow", "f60_sflow side", "60s signed flow x side"),
    _F("f5m_n", "flow", "f5m_n", "S8 5m trade count"),
    _F("f5m_vol", "flow", "f5m_vol", "S8 5m volume"),
    _F("f5m_sflow_with", "flow", "f5m_sflow side", "5m signed flow x side"),
    _F("f30m_n", "flow", "f30m_n", "S8 30m trade count"),
    _F("f30m_vol", "flow", "f30m_vol", "S8 30m volume"),
    _F("f30m_sflow_with", "flow", "f30m_sflow side", "30m signed flow x side"),
    _F("fph_n", "flow", "fph_n", "S8 phase trade count"),
    _F("fph_vol", "flow", "fph_vol", "S8 phase volume"),
    _F("fph_sflow_with", "flow", "fph_sflow side", "phase signed flow x side"),
    _F("flow_disagree_30m", "flow", "fph_sflow f30m_sflow",
       "P022 fossil-flow: sign(phase sflow) != sign(30m sflow)"),
    _F("flow_disagree_5m", "flow", "fph_sflow f5m_sflow",
       "P022 fossil-flow: sign(phase sflow) != sign(5m sflow)"),
)

_reg(
    _F("extreme_age_sec", "geometry", "extreme_age_sec",
       "age of the phase extreme the trade fades"),
    _F("ext_needed_usd", "geometry", "ext_needed_usd",
       "P016/T3: NEW range beyond the extreme the $1,000 bar still needs"),
    _F("room_with_usd", "geometry", "phase_hi phase_lo mid_now side",
       "dollars between the mid and the phase extreme the trade runs TOWARD"),
    _F("room_against_usd", "geometry", "phase_hi phase_lo mid_now side",
       "dollars back to the extreme the trade fades"),
    _F("pos_in_phase_range", "geometry", "phase_hi phase_lo mid_now",
       "(mid - phase_lo) / (phase_hi - phase_lo)"),
    _F("ret_sess_open_with", "geometry", "mid_now sess_open_mid side",
       "session-open-to-now move, signed by the side"),
    _F("ret_phase_open_with", "geometry", "mid_now phase_open_mid side",
       "phase-open-to-now move, signed by the side"),
    _F("prev_phase_ret_with", "geometry", "prev_phase_ret_usd side",
       "the previous phase segment's net move, signed by the side"),
    _F("prev_phase_range_usd", "geometry", "prev_phase_range_usd",
       "the previous phase segment's range"),
    _F("pre_cell_range_usd", "geometry", "pre_cell_range_usd",
       "everything the session printed before this cell opened "
       "(the overnight window for the first phase)"),
    _F("conf_to_dec_sec", "geometry", "conf_sec dec_sec",
       "D-033 confirmation-to-decision delay (the post-confirmation stage)"),
)

# ---- episode structure -----------------------------------------------------
_reg(
    _F("ep_is_earliest", "episode", "ep_is_earliest",
       "the row is the EARLIEST member of its frozen EPISODE_CAUSAL episode "
       "(the BASE_EARLIEST arm's own object)"),
    _F("ep_rank", "episode", "ep_rank", "0-based position inside the episode"),
    _F("ep_age_sec", "episode", "ep_age_sec",
       "dec_sec - the episode's first decision second"),
    _F("cell_rank_so_far", "episode", "cell_rank_so_far",
       "how many candidates of this (asset,phase) cell already fired "
       "(strictly causal: a count of the PAST)"),
    _F("cell_is_open_row", "episode", "cell_open",
       "the row is the cell's first candidate (CC-M2-17.1's cell open)"),
    _F("cell_age_sec", "episode", "cell_first_dec_sec dec_sec",
       "dec_sec - the cell's first decision second"),
    _F("sess_rank_so_far", "episode", "sess_rank_so_far",
       "how many candidates of this session already fired"),
)

# ---- THE TEACHER-EVIDENCE GROUP (D-078, injected 2026-08-16) ---------------
# design/TEACHER_FEATURES_V1.md, §2 PROVEN-IN-ROUND and §3 SUPPORTED, in the
# form that document itself orders: the continuous carriers FIRST, the binary
# gates beside them as interpretable checkpoints, the reader's own composites
# as explicit interaction terms, and NOTHING from §4 (FALSIFIED) shipped as a
# standalone evidence column.
#
# THREE RULINGS, made here and recorded because they are the places where the
# design document does not decide itself:
#  (a) §3 TF-06 asks for "the three legs as separate inputs AND the
#      conjunction"; §4 forbids shipping `one_sided_flow` / `flow_agree_5m`,
#      which ARE two of those legs (both measured at or below base).  The two
#      §4 legs are therefore NOT shipped as columns — their raw carriers
#      (`f5m_sflow_with`, `fph_sflow_with`) are already in the `flow` group and
#      the model sets the sign itself, which is exactly §7.3's instruction.
#      The conjunctions themselves (SUPPORTED / PROVEN) are shipped.
#  (b) §2's `range_so_far` and `unspent_phase_usd` are the two arms of the same
#      identity as the already-present `coverage_phase` and
#      `exp_move_q50_phase_usd`, so they are computed FROM those two columns —
#      the identical arithmetic info_ceiling.py:184 already uses for the
#      digest's `unspent_phase_usd`.  No new source, no second definition.
#  (c) §6 HYPOTHESIS cues are NOT shipped: TF-H1 EVENT_BURST is graded DEAD by
#      round 2 (0 winners in 27 episodes, TEACHER_CUE_LEDGER), and TF-H2 /
#      TF-H3 need a pivot chain and an S6 cluster vector that no committed
#      field carries.  §5 CONFOUNDED `spread_dec` stays where it is (the
#      `regime` group), never re-badged as evidence.
_reg(
    _F("tf_unspent_phase_usd", "teacher_evidence",
       "exp_move_q50_phase_usd coverage_phase",
       "TF-01/TF-04 THE headline capacity carrier: the phase's expected move "
       "minus what the phase has already spent = q50_phase * (1 - cov_phase)"),
    _F("tf_range_phase_usd", "teacher_evidence",
       "exp_move_q50_phase_usd coverage_phase",
       "TF-04 the level beside the ratio: the phase's range so far in dollars"),
    _F("tf_cov_phase_pct", "teacher_evidence", "coverage_phase",
       "TF-03/TF-04 coverage on the round's own 0-100 scale (its bin edges "
       "are quoted in percent)"),
    _F("tf_seat_live", "teacher_evidence",
       "exp_move_q50_phase_usd coverage_phase runway_phase_sec",
       "TF-01 SEAT_LIVE gate: unspent_phase >= $700 AND runway_phase >= "
       "18,000s (blind 2.62x on n=524, 6/6 days)"),
    _F("tf_seat_dead_time", "teacher_evidence", "runway_phase_sec",
       "TF-02 SEAT_DEAD_TIME: runway_phase < 4,800s (blind 0.04x, 1 winner "
       "in 313) — the round's strongest single statement"),
    _F("tf_phase_spent", "teacher_evidence", "coverage_phase",
       "TF-03 PHASE_SPENT: cov_phase >= 80% (blind 0.54x)"),
    _F("tf_cov_sweet_20_60", "teacher_evidence", "coverage_phase",
       "TF-03 the complementary positive band 20% <= cov_phase < 60% "
       "(blind 2.00x) — the correction to the reader's 'phase-open reset is "
       "the richest moment'"),
    _F("tf_capacity_room", "teacher_evidence",
       "exp_move_q50_phase_usd coverage_phase",
       "capacity_room: unspent_phase >= $400 (blind 1.70x) — also the second "
       "leg of PHASE_OPEN_RESET"),
    _F("tf_capacity_big", "teacher_evidence",
       "exp_move_q50_phase_usd coverage_phase",
       "capacity_big: unspent_phase >= $1,000 (blind 2.23x)"),
    _F("tf_near_d_usd", "teacher_evidence", "tf_near_d_usd",
       "TF-06 leg / §1 `near_d`: dollars to the NEAREST ledger level alive at "
       "the decision second (the S4 LEVEL LEDGER's own d$ column)"),
    _F("tf_n_near100", "teacher_evidence", "tf_n_near100",
       "§1 `n_near100`: how many alive ledger levels sit within $100"),
    _F("tf_min_tc_near", "teacher_evidence", "tf_min_tc_near",
       "TF-05 §1 `min_tc_near` as a RAW ORDINAL (the document's own "
       "instruction: the reader's `level_held` boolean had the sign backwards, "
       "so the model recovers the sign itself); NaN = every near level's prior "
       "state is REFUSED (R96) or there is no near level"),
    _F("tf_level_virgin", "teacher_evidence", "tf_min_tc_near",
       "TF-05 LEVEL_VIRGIN: min_tc_near == 0 (blind 1.67x) — the INVERSION of "
       "the reader's own E6-H3 hypothesis"),
    _F("tf_level_near", "teacher_evidence", "tf_near_d_usd",
       "TF-06 leg LEVEL_NEAR: |near_d| <= $60 (0.97x alone — shipped because "
       "TF-06 asks for the legs beside the conjunction)"),
    _F("tf_phase_open_frac", "teacher_evidence",
       "phase_age_sec runway_phase_sec",
       "TF-06 leg carrier: elapsed share of the phase segment = "
       "phase_age / (phase_age + runway_phase)"),
    _F("tf_phase_open_reset", "teacher_evidence",
       "phase_age_sec runway_phase_sec exp_move_q50_phase_usd coverage_phase",
       "TF-06 leg PHASE_OPEN_RESET: phase_open_frac <= 0.15 AND unspent >= "
       "$400 (blind 1.65x, direction only 3/6 days — UNSTABLE in the ledger)"),
    _F("tf_named_triad", "teacher_evidence",
       "phase_age_sec runway_phase_sec exp_move_q50_phase_usd coverage_phase "
       "tf_near_d_usd f5m_sflow fph_sflow side",
       "TF-06 NAMED_TRIAD as the reader stated it: PHASE_OPEN_RESET AND "
       "LEVEL_NEAR AND ONE_SIDED_FLOW (pooled 1.77x, 6/6 days; blind p=0.24)"),
    _F("tf_named_triad_soft", "teacher_evidence",
       "exp_move_q50_phase_usd coverage_phase tf_near_d_usd f5m_sflow side",
       "NAMED_TRIAD_soft: capacity_room AND level_near AND flow_agree_5m "
       "(blind 1.64x on n=256, p=0.0073 — the PROVEN member of the pair)"),
)

FEATURE_NAMES = tuple(f.name for f in FEATURES)
assert len(set(FEATURE_NAMES)) == len(FEATURE_NAMES), "duplicate feature name"
FEATURE_GROUP = {f.name: f.group for f in FEATURES}
for _f in FEATURES:
    assert _f.group in GROUPS, "undeclared group %s" % _f.group

# THE D-078 INSTRUMENT, NOW FIRED.  The flag is computed, never asserted: it
# reads False from the moment the teacher round's features land in the registry,
# and every receipt carries it, so "the marginal value of the teacher round" is
# the difference between this matrix WITH the group and the same matrix with the
# group dropped (m3_walk --drop-groups teacher_evidence), measured on the one
# harness, one matrix, one policy.
NO_TEACHER = not any(f.group == "teacher_evidence" for f in FEATURES)
N_TEACHER = sum(1 for f in FEATURES if f.group == "teacher_evidence")

TARGETS = ("y_retg_rank_phase", "y_retg_raw", "y_winner",
           "y_t1_episode", "y_t1_cell")

# outcome columns carried beside the matrix: the label side, the replay side,
# and the guard's own reference set.  NEVER features.
OUTCOMES = ("cert_close_usd", "cert_peak_usd", "mae_before_argmax", "walled",
            "winner", "exit_close_sec", "exit_peak_sec", "cert_refused",
            "mfe_unwalled", "f_sess_close", "cost_rt")

META = ("asset_idx", "d8", "dec_sec", "side", "phase_dec", "era_idx",
        "cell_key", "ep_key", "row_ts", "cost_fallback")


# ================================================================ per-session
_RAW_F64 = ("rv1800_usd", "rv60_usd", "rv_ratio", "unspent_sess",
            "exp_move_q50_phase_usd", "coverage_phase", "coverage_session",
            "runway_frac", "mins_to_release", "level_dist_atr",
            "refail_dist_usd", "c2f_60", "c2f_300", "dbsz_min", "dasz_min",
            "d_poc", "day_type_frac", "surprise", "range_hat_usd",
            "range_so_far_usd", "atr_usd", "spread_dec_usd", "spread_ratio",
            "dom_share", "slope_1m_usd", "slope_5m_usd", "accel_usd",
            "ext_needed_usd", "phase_hi", "phase_lo", "mid_now",
            "sess_open_mid", "phase_open_mid", "prev_phase_ret_usd",
            "prev_phase_range_usd", "pre_cell_range_usd",
            "cert_close_usd", "cert_peak_usd", "mae_before_argmax",
            "mfe_unwalled", "f_sess_close", "cost_rt",
            "tf_near_d_usd", "tf_n_near100", "tf_min_tc_near")
_RAW_I64 = ("dec_sec", "conf_sec", "runway_phase_sec", "runway_sess_sec",
            "phase_age_sec", "clock_sec", "release_age_sec", "extreme_age_sec",
            "pivot_age_sec", "refail_gap_sec", "refail_age_sec",
            "n_conf_fam_at_refail", "n_conf_fam_at_refail_2t", "thru_n",
            "thru_bid", "thru_ask", "n_ev_60", "fuel_above", "fuel_below",
            "fuel_total", "in_va", "f60_n", "f60_vol", "f60_sflow", "f5m_n",
            "f5m_vol", "f5m_sflow", "f30m_n", "f30m_vol", "f30m_sflow",
            "fph_n", "fph_vol", "fph_sflow", "fev_n", "fev_vol", "fev_sflow",
            "cell_first_dec_sec", "exit_close_sec", "exit_peak_sec",
            "fam_mask", "rung_mask", "level_fam_mask", "flags", "iid")
_RAW_I8 = ("side", "phase_dec", "day_type", "ladder_band", "regime_tercile",
           "dow", "event_in_phase", "sched_release_in_phase", "cell_open",
           "session_close_exit", "walled", "winner", "cert_refused",
           "cost_fallback")
_RAW_STR = ("cid", "klass")
RAW_KEYS = _RAW_F64 + _RAW_I64 + _RAW_I8


# ------------------------------------------- THE S4 LEVEL LEDGER, at grain ---
TF_NEAR_USD = 100.0        # the round's own "within $100" band (§1 `n_near100`)


def _teacher_level_state(asset, d8, sess, dec, entry_mid, mult):
    """`near_d` / `n_near100` / `min_tc_near` at EVERY decision second.

    THE POPULATION is every level of the session's ledger — KEPT and retired
    families alike — because that is what the S4 LEVEL LEDGER the E6 reader
    actually read prints (`sections.py:849`: the K column is a TAG, not a
    filter).  This is deliberately a different population from
    `pattern_lib._nearest_kept_level_atr`, which the matrix already carries as
    `level_dist_atr` over the KEPT families only; the two columns are different
    objects and both are shipped.

    THE CAUSALITY is `sections.s4_levels`' own arithmetic, imported rather than
    re-derived where it is importable (D-006):
      * a level exists only from `sections._level_birth_sec` onward, STRICTLY
        before the decision second (the R93/D4 birth guard);
      * its touch count is `tc0 + tc`, where `tc0` is the touch count in the
        LATEST ledger snapshot strictly before the decision second (R96's
        prior-snapshot rule) and `tc` counts touches with `touch_sec <
        dec_sec`.  A level with NO prior snapshot has its prior state REFUSED,
        exactly as the sheet refuses it — it never enters `min_tc_near` as a
        fabricated zero, which is the very error R96 was filed for.
    Nothing here reads a touch OUTCOME (`touches[:,5]`), the registered trap.
    """
    n_d = int(dec.size)
    nanv = np.full(n_d, np.nan)
    out = {"tf_near_d_usd": nanv.copy(), "tf_n_near100": nanv.copy(),
           "tf_min_tc_near": nanv.copy()}
    z, _p = A.load_levels(asset, int(d8))
    if z is None or not int(np.asarray(z["level_price"]).size):
        return out
    import sections as SEC                 # local: sections imports are heavy

    class _Shim(object):                   # what _level_birth_sec reads
        pass

    shim = _Shim()
    shim.asset = asset
    shim.d8 = int(d8)
    shim.s = sess["s"]
    shim.trade_date = sess["trade_date"]
    shim.profile = A.load_profile(asset, int(d8))[0]

    fam = z["level_family"]
    lid = z["level_id"]
    lpx = np.asarray(z["level_price"], dtype=np.float64)
    dyn = z["dynamic"]
    n_l = int(lpx.size)
    born = np.array([SEC._level_birth_sec(shim, str(fam[r]), str(lid[r]),
                                          int(dyn[r])) for r in range(n_l)],
                    dtype=np.int64)
    live = np.isfinite(lpx) & (born >= 0)
    if not live.any():
        return out

    # --- causal touch state, per (level, decision second) -------------------
    ss = np.asarray(z["snap_sec"], dtype=np.int64)
    sr = np.asarray(z["snap_row"], dtype=np.int64)
    stc = np.asarray(z["snap_touch_count"], dtype=np.int64)
    tc = np.full((n_l, n_d), -1, dtype=np.int64)      # -1 = prior state REFUSED
    for r in np.unique(sr[(sr >= 0) & (sr < n_l)]).tolist():
        k = np.nonzero(sr == r)[0]
        o = np.argsort(ss[k], kind="stable")
        sk, vk = ss[k][o], stc[k][o]
        j = np.searchsorted(sk, dec, side="left") - 1
        tc[r] = np.where(j >= 0, vk[np.clip(j, 0, vk.size - 1)], -1)
    tch = np.asarray(z["touches"])
    if tch.size:
        tsec = tch[:, 0].astype(np.int64)
        trow = tch[:, 1].astype(np.int64)
        for r in np.unique(trow[(trow >= 0) & (trow < n_l)]).tolist():
            v = np.sort(tsec[trow == r])
            tc[r] = np.where(tc[r] >= 0,
                             tc[r] + np.searchsorted(v, dec, side="left"),
                             -1)

    alive = live[:, None] & (born[:, None] < dec[None, :])
    dist = np.abs(lpx[:, None] - entry_mid[None, :]) * float(mult)
    far = np.where(alive, dist, np.inf)
    near = far.min(axis=0)
    out["tf_near_d_usd"] = np.where(np.isfinite(near), near, np.nan)
    in100 = alive & (dist <= TF_NEAR_USD)
    out["tf_n_near100"] = in100.sum(axis=0).astype(np.float64)
    BIG = np.iinfo(np.int64).max
    tcm = np.where(in100 & (tc >= 0), tc, BIG).min(axis=0)
    out["tf_min_tc_near"] = np.where(tcm < BIG, tcm.astype(np.float64), np.nan)
    return out


def _pack_session(asset, d8):
    """One session's raw causal pack.  pattern_lib is THE source."""
    f = PL.frame(asset, int(d8), with_levels=True, with_v3=True)
    if f is None:
        return None
    n = int(f["dec_sec"].size)
    if n == 0:
        return None
    r = A.roster(asset)
    i = f["i"]
    sess = A.load_session(asset, int(d8))
    open_utc = int(sess["s"].meta["open_utc"])
    iso = sess["trade_date"].isoformat()
    dec = f["dec_sec"].astype(np.int64)

    d_poc, in_va = B5._s10_of(asset, int(d8), dec,
                              r["entry_mid"][i].astype(np.float64))
    unspent = B5._unspent_session(asset, iso,
                                  f["range_so_far_usd"].astype(np.float64))
    ev = B5._event_stats(asset, int(d8), open_utc, dec)
    rel = B4._mins_to_release(open_utc + dec)

    cost_raw = A.cost_map().get((asset, iso), float("nan"))
    cost_fb = 0 if np.isfinite(cost_raw) else 1
    cost = float(cost_raw) if np.isfinite(cost_raw) else float(C.FEES_RT)

    src = dict(f)
    src["unspent_sess"] = unspent
    src["d_poc"] = d_poc
    src["in_va"] = in_va
    src["mins_to_release"] = rel
    src.update(ev)
    src["conf_sec"] = r["conf_sec"][i].astype(np.int64)
    src["rung_mask"] = r["rung_mask"][i].astype(np.int64)
    src["level_fam_mask"] = r["level_fam_mask"][i].astype(np.int64)
    src["flags"] = r["flags"][i].astype(np.int64)
    src["iid"] = r["iid"][i].astype(np.int64)
    src["dom_share"] = r["dom_share"][i].astype(np.float64)
    src["mfe_unwalled"] = r["mfe_unwalled"][i].astype(np.float64)
    src["f_sess_close"] = r["f_sess_close"][i].astype(np.float64)
    src["cost_rt"] = np.full(n, cost)
    src["cost_fallback"] = np.full(n, cost_fb)
    src.update(_teacher_level_state(asset, int(d8), sess, dec,
                                    r["entry_mid"][i].astype(np.float64),
                                    C.ASSETS[asset]["mult"]))

    out = {"asset": asset, "d8": int(d8), "open_utc": open_utc, "n": n}
    for k in _RAW_F64:
        out[k] = np.asarray(src[k], dtype=np.float64)
    for k in _RAW_I64:
        out[k] = np.asarray(src[k], dtype=np.int64)
    for k in _RAW_I8:
        out[k] = np.asarray(src[k], dtype=np.int64).astype(np.int8)
    out["cid"] = np.asarray(f["cid"])
    out["klass"] = np.asarray(f["klass"])
    return out


def _one(job):
    asset, d8 = job
    try:
        p = _pack_session(asset, int(d8))
    except Exception as e:                # noqa: BLE001 — surfaced, not hidden
        return ("ERROR", asset, int(d8), repr(e)[:300])
    A._MEM.pop(("sess", asset, int(d8)), None)
    if p is None:
        return ("EMPTY", asset, int(d8), "")
    return ("OK", p)


def _init():
    MC.verify_spec(force=True)


def scan(assets=M3.ASSET_ORDER, workers=8, limit=None):
    """Every FIT + GATE session of every asset, holdout excluded BY REFUSAL."""
    jobs, quarantined = [], 0
    for a in assets:
        keep, nq = PL.sessions_fit(a)
        quarantined += nq
        if limit:
            keep = keep[:int(limit)]
        jobs += [(a, d) for d in keep]
    jobs.sort()
    parts, errs, empty = [], [], []
    t0 = time.time()
    if workers and workers > 1:
        with mp.Pool(processes=int(workers), initializer=_init) as pool:
            for k, res in enumerate(pool.imap(_one, jobs, chunksize=4), 1):
                if res[0] == "OK":
                    parts.append(res[1])
                elif res[0] == "ERROR":
                    errs.append((res[1], res[2], res[3]))
                else:
                    empty.append((res[1], res[2]))
                if k % 200 == 0:
                    M3.hb("m3 matrix scan %d/%d  %.1fs"
                          % (k, len(jobs), time.time() - t0))
    else:
        _init()
        for j in jobs:
            res = _one(j)
            if res[0] == "OK":
                parts.append(res[1])
            elif res[0] == "ERROR":
                errs.append((res[1], res[2], res[3]))
            else:
                empty.append((res[1], res[2]))
    if errs:
        raise RuntimeError("m3 matrix scan: %d session(s) failed, first=%s"
                           % (len(errs), errs[0]))
    parts.sort(key=lambda p: (p["asset"], p["d8"]))
    M3.hb("m3 matrix scan: %d sessions, %d empty, %d holdout quarantined, "
          "%.1fs" % (len(parts), len(empty), quarantined, time.time() - t0))
    return parts, {"n_jobs": len(jobs), "n_sessions": len(parts),
                   "n_empty": len(empty), "n_quarantined": quarantined}


# ============================================================ the assembly ===
def _concat(parts):
    R = {}
    for k in RAW_KEYS:
        R[k] = np.concatenate([p[k] for p in parts])
    for k in _RAW_STR:
        R[k] = np.concatenate([p[k] for p in parts])
    R["asset"] = np.concatenate([np.full(p["n"], p["asset"]) for p in parts])
    R["d8"] = np.concatenate([np.full(p["n"], p["d8"], dtype=np.int64)
                              for p in parts])
    R["open_utc"] = np.concatenate([np.full(p["n"], p["open_utc"],
                                            dtype=np.int64) for p in parts])
    return R


def _read_tsv(path):
    rows, hdr = [], None
    with open(path) as fh:
        for ln in fh:
            if ln.startswith("#") or not ln.strip():
                continue
            f = ln.rstrip("\n").split("\t")
            if hdr is None:
                hdr = f
                continue
            rows.append(dict(zip(hdr, f)))
    return rows


def _fnum(v):
    try:
        return float(v)
    except Exception:                      # noqa: BLE001 — '' is REFUSED
        return float("nan")


FC_COLS = ("p_expansion", "range_hat_usd", "range_hat_q10", "range_hat_q90",
           "range_hat_vs_trailing", "share_hat_TOKYO", "share_hat_LONDON",
           "share_hat_NY", "menu_hat", "bench_base_rate", "bench_persistence",
           "bench_range_trailmed", "n_feature_missing")
# AVAILABILITY IS DECIDED BY THE MODEL'S OWN PREDICTIONS AND NOTHING ELSE.
# The forecaster's receipt also carries (a) `n_feature_missing`, a diagnostic
# written on every emitted row, and (b) the `bench_*` columns, which are
# TRAILING STATISTICS (trailing median / persistence / base rate) and are
# therefore available years before the fitted heads are — measured on the built
# matrix: bench_range_trailmed is 100% present in E1 while p_expansion is 0%.
# Letting either decide availability would report the forecaster as live
# through the whole of 2021, which CC-M2-17.2 rules it is not.
FC_PRED = ("p_expansion", "range_hat_usd", "range_hat_q10", "range_hat_q90",
           "range_hat_vs_trailing", "share_hat_TOKYO", "share_hat_LONDON",
           "share_hat_NY", "menu_hat")
FC_CORE = FC_PRED


def join_forecaster(R):
    """AVAILABILITY-LAGGED forecaster join: the latest anchor <= dec_sec.

    R84/CC-M2-17.2: there is no 2021 output.  Rows with no admissible anchor
    are TYPED-MISSING (NaN) with `fc_available = 0` — never imputed, never
    back-filled, and the count is receipted per era.
    """
    n = R["dec_sec"].size
    out = {"fc_available": np.zeros(n, dtype=np.float64),
           "fc_anchor_age_sec": np.full(n, np.nan)}
    for c in FC_COLS:
        out["fc_" + c] = np.full(n, np.nan)
    for asset in M3.ASSET_ORDER:
        p = os.path.join(REGIME_ROOT, "forecast_%s.tsv" % asset)
        if not os.path.exists(p):
            raise M3.HarnessRefusal("forecaster receipt missing: %s" % p)
        by = {}
        for row in _read_tsv(p):
            if row["asset"] != asset:
                continue
            d = row["trade_date"]
            d8 = int(d[:4] + d[5:7] + d[8:10])
            # LEAK FIX P3_FORECASTER_ANCHOR_JOIN (leak audit, MODERATE): the
            # anchor second came from a HARD-CODED table keyed on the anchor's
            # NAME, which disagrees with the session's own anchor second on
            # 3.17% of rows and can therefore attach a forecast to a decision
            # that preceded it.  The receipt carries the real second; use it.
            # The name table survives only as the declared fallback for a row
            # that predates the column.
            try:
                asec = int(row["anchor_sec"])
            except (KeyError, TypeError, ValueError):
                asec = FC_ANCHOR_SEC.get(row["anchor"])
            if asec is None:
                raise M3.HarnessRefusal("unknown forecaster anchor %r"
                                        % row["anchor"])
            by.setdefault(d8, []).append((asec, row))
        for d8 in by:
            by[d8].sort(key=lambda t: t[0])
        m = np.nonzero(R["asset"] == asset)[0]
        for idx in m.tolist():
            d8 = int(R["d8"][idx])
            cand = by.get(d8)
            if not cand:
                continue
            ds = int(R["dec_sec"][idx])
            pick = None
            for asec, row in cand:
                if asec <= ds:
                    pick = (asec, row)
                else:
                    break
            if pick is None:
                continue
            asec, row = pick
            vals = [_fnum(row.get(c, "")) for c in FC_COLS]
            core = [v for c, v in zip(FC_COLS, vals) if c in FC_CORE]
            if not any(np.isfinite(v) for v in core):
                continue                   # a pre-instrument row: typed-missing
            out["fc_available"][idx] = 1.0
            out["fc_anchor_age_sec"][idx] = float(ds - asec)
            for c, v in zip(FC_COLS, vals):
                out["fc_" + c][idx] = v
    return out


ND_COLS = ("minutes_to_next_release", "minutes_since_last_release_any",
           "held_into_window", "gen_anchor_is_dated_release")


def join_news(R):
    """NEWS_DISTANCE.tsv on cid.  Absence = no release within +/-15min."""
    n = R["dec_sec"].size
    out = {"nd_in_census": np.zeros(n, dtype=np.float64)}
    for c in ND_COLS:
        out["nd_" + c] = np.full(n, np.nan)
    if not os.path.exists(NEWS_DISTANCE):
        raise M3.HarnessRefusal(
            "NEWS_DISTANCE.tsv is absent — the D-077-UPDATE compliance flags "
            "are read from the census, never inferred (CC-M2-22.4)")
    pos = {c: i for i, c in enumerate(R["cid"].tolist())}
    hit = 0
    for row in _read_tsv(NEWS_DISTANCE):
        i = pos.get(row["cid"])
        if i is None:
            continue
        hit += 1
        out["nd_in_census"][i] = 1.0
        for c in ND_COLS:
            out["nd_" + c][i] = _fnum(row.get(c, ""))
    out["_n_joined"] = hit
    return out


def join_cross_asset(R):
    """Row-grain cross-asset state, batch4's causality law at row grain.

    For every row and every asset A, find A's most recent CLOSED cell whose
    LAST CANDIDATE ROW sits at or before this row's own epoch second, and read
    that row's state.  The own-asset leg steps back past the row's own cell
    (batch4 R76's P009 control).  A source older than P031_SRC_MAX_AGE_DAYS is
    dropped — the same freshness rule, on real calendar dates (R75).
    """
    n = R["dec_sec"].size
    ts = R["open_utc"] + R["dec_sec"]
    cell_key = np.array(["%s|%08d|%d" % (a, d, p) for a, d, p in
                         zip(R["asset"].tolist(), R["d8"].tolist(),
                             R["phase_dec"].tolist())])
    fields = ("rv1800", "fuel_share_above", "range_so_far", "slope5m",
              "sflow_phase")
    fuel_share = np.where(R["fuel_total"] > 0,
                          R["fuel_above"] / np.maximum(R["fuel_total"], 1),
                          np.nan)
    state = {"rv1800": R["rv1800_usd"], "fuel_share_above": fuel_share,
             "range_so_far": R["range_so_far_usd"],
             "slope5m": R["slope_5m_usd"],
             "sflow_phase": R["fph_sflow"].astype(np.float64)}

    out = {}
    for a in M3.ASSET_ORDER:
        out["xa_%s_age_sec" % a] = np.full(n, np.nan)
        for f in fields:
            out["xa_%s_%s" % (a, f)] = np.full(n, np.nan)

    # per asset: its cells' (close_ts, d8, source row index, cell_key)
    cells = {}
    for a in M3.ASSET_ORDER:
        m = np.nonzero(R["asset"] == a)[0]
        if m.size == 0:
            cells[a] = (np.zeros(0, dtype=np.int64), np.zeros(0, dtype=np.int64),
                        np.zeros(0, dtype=np.int64), np.array([], dtype=object))
            continue
        ck = cell_key[m]
        order = np.lexsort((ts[m], ck))
        mo = m[order]
        cko = ck[order]
        last = np.nonzero(np.concatenate([cko[1:] != cko[:-1], [True]]))[0]
        src_rows = mo[last]
        close_ts = ts[src_rows]
        o2 = np.argsort(close_ts, kind="stable")
        src_rows = src_rows[o2]
        cells[a] = (close_ts[o2], R["d8"][src_rows], src_rows,
                    cell_key[src_rows])

    for a in M3.ASSET_ORDER:
        cts, cd8, crow, cck = cells[a]
        if cts.size == 0:
            continue
        j = np.searchsorted(cts, ts, side="right") - 1
        # step back past the row's OWN cell (R76) — at most a couple of hops
        for _ in range(4):
            bad = (j >= 0) & (cck[np.clip(j, 0, cts.size - 1)] == cell_key)
            if not bad.any():
                break
            j = np.where(bad, j - 1, j)
        ok = j >= 0
        jj = np.clip(j, 0, cts.size - 1)
        # R75's freshness rule is CALENDAR arithmetic, so d8 stamps are mapped
        # to true date ordinals before subtracting (vectorised form of
        # batch4._day_gap, whose identity test_m3 pins).
        gap = np.abs(_ordinal(cd8[jj]) - _ordinal(R["d8"]))
        ok = ok & (gap <= B4.P031_SRC_MAX_AGE_DAYS)
        sr = crow[jj]
        out["xa_%s_age_sec" % a] = np.where(ok, ts - cts[jj], np.nan)
        for f in fields:
            out["xa_%s_%s" % (a, f)] = np.where(ok, state[f][sr], np.nan)
    return out


_ORD = {}


def _ordinal(d8):
    """YYYYMMDD -> proleptic date ordinal, memoised and vectorised."""
    a = np.asarray(d8, dtype=np.int64)
    for d in np.unique(a).tolist():
        if d not in _ORD:
            _ORD[d] = MC.d8_to_date(int(d)).toordinal()
    return np.array([_ORD[int(d)] for d in a.tolist()], dtype=np.int64)


def episode_keys(R):
    """The FROZEN EPISODE_CAUSAL grouping (CC-M1-12 v2), per (session, side).

    K*/SPAN_MAX come from baseline_replay.episode_pins(), which REFUSES on any
    disagreement with the committed episode_v2 receipt.
    """
    kst, spn = BR.episode_pins(check=True)
    n = R["dec_sec"].size
    ep = np.full(n, -1, dtype=np.int64)
    ep_rank = np.zeros(n, dtype=np.int64)
    ep_first = np.zeros(n, dtype=np.int64)
    key = np.array(["%s|%08d|%d" % (a, d, s) for a, d, s in
                    zip(R["asset"].tolist(), R["d8"].tolist(),
                        R["side"].tolist())])
    order = np.lexsort((R["dec_sec"], key))
    ko = key[order]
    starts = [0] + (np.flatnonzero(ko[1:] != ko[:-1]) + 1).tolist()
    stops = starts[1:] + [ko.size]
    nid = 0
    for s, e in zip(starts, stops):
        idx = order[s:e]
        a = R["asset"][idx[0]]
        side = int(R["side"][idx[0]])
        dec = R["dec_sec"][idx].astype(np.int64)
        spans = EV.group_causal(dec, kst[(a, side)], spn[(a, side)])
        for lo, hi in spans:
            sel = idx[lo:hi]
            ep[sel] = nid
            ep_rank[sel] = np.arange(hi - lo)
            ep_first[sel] = int(dec[lo])
            nid += 1
    if int((ep < 0).sum()):
        raise M3.HarnessRefusal("EPISODE_CAUSAL left %d row(s) ungrouped"
                                % int((ep < 0).sum()))
    return ep, ep_rank, ep_first, nid


def _borda(value, group, valid):
    """Within-group pairwise-preference share (the T1 pointwise sufficient
    statistic): #{beaten} + 0.5*#{tied}, over group size - 1.

    A singleton group is NaN — a preference needs something to prefer against.
    """
    n = value.size
    out = np.full(n, np.nan)
    # invalid rows are sent to +inf so the valid block of every group is a
    # CONTIGUOUS ASCENDING prefix, which is what the searchsorted below needs.
    sortval = np.where(valid, value, np.inf)
    order = np.lexsort((sortval, group))
    g = group[order]
    v = sortval[order]
    ok = valid[order]
    starts = [0] + (np.flatnonzero(g[1:] != g[:-1]) + 1).tolist()
    stops = starts[1:] + [n]
    for s, e in zip(starts, stops):
        sel = order[s:e]
        vv = v[s:e]
        kk = ok[s:e]
        m = int(kk.sum())
        if m < 2:
            continue
        x = vv[kk]
        # x is already ascending inside the group (lexsort on value)
        lo = np.searchsorted(x, x, side="left")
        hi = np.searchsorted(x, x, side="right")
        beaten = lo.astype(np.float64)
        tied = (hi - lo - 1).astype(np.float64)
        out[sel[kk]] = (beaten + 0.5 * tied) / float(m - 1)
    return out


def build_targets(R, ep):
    """THE ATLAS CHAMPION + the walled winner + the T1 pairwise preference."""
    n = R["dec_sec"].size
    cost = R["cost_rt"]
    eps = 30.0 * cost                      # retg|e30 — the atlas champion's eps
    net = R["f_sess_close"] - cost         # net at the sess_close horizon
    mfe = R["mfe_unwalled"]                # == mfe_at(sess_close) by construction
    den = np.maximum(mfe, eps)
    with np.errstate(invalid="ignore", divide="ignore"):
        retg = np.where(mfe < eps, np.nan, net / den)
    retg = np.where(np.isfinite(net) & np.isfinite(mfe), retg, np.nan)

    unit = np.array(["%s|%08d|%d" % (a, d, p) for a, d, p in
                     zip(R["asset"].tolist(), R["d8"].tolist(),
                         R["phase_dec"].tolist())])
    rank = np.full(n, np.nan)
    order = np.argsort(unit, kind="stable")
    uo = unit[order]
    starts = [0] + (np.flatnonzero(uo[1:] != uo[:-1]) + 1).tolist()
    stops = starts[1:] + [n]
    for s, e in zip(starts, stops):
        sel = order[s:e]
        rank[sel] = _rank_pct(retg[sel])

    finite = R["cert_refused"] == 0
    win = (finite & (R["cert_close_usd"] >= 1000.0)
           & (R["mae_before_argmax"] <= 300.0) & (R["walled"] == 0))
    y_win = np.where(finite, win.astype(np.float64), np.nan)

    cellk = np.array(["%s|%08d|%d" % (a, d, p) for a, d, p in
                      zip(R["asset"].tolist(), R["d8"].tolist(),
                          R["phase_dec"].tolist())])
    _u, cell_id = np.unique(cellk, return_inverse=True)
    t1_ep = _borda(R["cert_close_usd"], ep, finite)
    t1_cell = _borda(R["cert_close_usd"], cell_id.astype(np.int64), finite)
    return {"y_retg_rank_phase": rank, "y_retg_raw": retg, "y_winner": y_win,
            "y_t1_episode": t1_ep, "y_t1_cell": t1_cell}


def _rank_pct(v):
    """s4_labels._rank verbatim: average rank -> within-unit percentile."""
    ok = np.isfinite(v)
    out = np.full(v.size, np.nan)
    n = int(ok.sum())
    if n < 2:
        return out
    x = v[ok]
    order = np.argsort(x, kind="stable")
    r = np.empty(n, dtype=np.float64)
    sx = x[order]
    i = 0
    while i < n:
        j = i
        while j + 1 < n and sx[j + 1] == sx[i]:
            j += 1
        r[order[i:j + 1]] = 0.5 * (i + j) + 1.0
        i = j + 1
    out[ok] = (r - 0.5) / n
    return out


def _bits(mask, table):
    return {nm: ((mask >> i) & 1).astype(np.float64)
            for i, nm in enumerate(table)}


def build_columns(R, fc, nd, xa, ep, ep_rank, ep_first):
    """Every declared feature, computed once, in registry order."""
    n = R["dec_sec"].size
    mult = np.array([float(C.ASSETS[a]["mult"]) for a in R["asset"].tolist()])
    side = R["side"].astype(np.float64)
    col = {}

    for k in MC.CLASS_ORDER + (MC.CLASS_UNKNOWN,):
        col["cls_" + k.replace("-", "_")] = (R["klass"] == k).astype(np.float64)
    fb = _bits(R["fam_mask"], MC.FAMILIES)
    for f in MC.FAMILIES:
        col["fam_" + f] = fb[f]
    for i, r in enumerate(MC.RUNGS):
        col["rung_%g" % r] = ((R["rung_mask"] >> i) & 1).astype(np.float64)
    lfb = _bits(R["level_fam_mask"], MC.KEPT_LEVEL_FAMILIES)
    for lf in MC.KEPT_LEVEL_FAMILIES:
        col["levfam_" + lf] = lfb[lf]
    col["n_level_fams"] = sum(lfb.values())
    for fn, b in MC.FLAG_NAMES:
        col["flag_" + fn] = ((R["flags"] & b) > 0).astype(np.float64)

    # seat state
    for k in ("rv1800_usd", "rv60_usd", "rv_ratio", "coverage_phase",
              "coverage_session", "exp_move_q50_phase_usd"):
        col[k] = R[k].astype(np.float64)
    col["unspent_sess_usd"] = R["unspent_sess"]
    cell_open_val = _cell_open_value(R, R["rv1800_usd"])
    col["cell_rv1800_at_open"] = cell_open_val
    col["cell_unspent_at_open"] = _cell_open_value(R, R["unspent_sess"])

    # runway
    col["runway_phase_sec"] = R["runway_phase_sec"].astype(np.float64)
    col["runway_sess_sec"] = R["runway_sess_sec"].astype(np.float64)
    col["runway_frac"] = R["runway_frac"]
    col["phase_age_sec"] = R["phase_age_sec"].astype(np.float64)
    col["session_close_exit"] = R["session_close_exit"].astype(np.float64)
    rw = R["runway_phase_sec"].astype(np.float64)
    col["p033_product"] = rw * R["rv1800_usd"]
    col["p033_sqrt"] = np.sqrt(np.maximum(rw, 0.0)
                               * np.maximum(R["rv1800_usd"], 0.0))

    # clock
    for i, p in enumerate(M3.PHASE_NAMES):
        col["phase_" + p] = (R["phase_dec"] == i).astype(np.float64)
    ck = R["clock_sec"].astype(np.float64)
    col["clock_sec"] = ck
    col["clock_sin"] = np.sin(2.0 * np.pi * ck / 86400.0)
    col["clock_cos"] = np.cos(2.0 * np.pi * ck / 86400.0)
    col["dec_sec"] = R["dec_sec"].astype(np.float64)
    dow = R["dow"].astype(np.float64)
    col["dow"] = dow
    col["is_monday"] = (dow == 0).astype(np.float64)
    col["is_friday"] = (dow == 4).astype(np.float64)

    # news
    rel = R["mins_to_release"]
    col["mins_to_release"] = rel
    col["abs_mins_to_release"] = np.abs(rel)
    col["in_news_window"] = np.where(
        np.isfinite(rel), (np.abs(rel) <= M3.NEWS_WINDOW_MIN).astype(float), 0.0)
    col["post_news_10_20"] = np.where(
        np.isfinite(rel), ((rel >= 10.0) & (rel < 20.0)).astype(float), 0.0)
    col["pre_release_window"] = np.where(
        np.isfinite(rel), ((rel < 0) & (rel >= -M3.NEWS_WINDOW_MIN)).astype(float),
        0.0)
    col["release_age_sec"] = R["release_age_sec"].astype(np.float64)
    col["event_in_phase"] = R["event_in_phase"].astype(np.float64)
    col["sched_release_in_phase"] = R["sched_release_in_phase"].astype(np.float64)
    col["nd_in_census"] = nd["nd_in_census"]
    col["nd_mins_to_next"] = nd["nd_minutes_to_next_release"]
    col["nd_mins_since_any"] = nd["nd_minutes_since_last_release_any"]
    col["nd_held_into_window"] = nd["nd_held_into_window"]
    col["nd_gen_anchor_dated"] = nd["nd_gen_anchor_is_dated_release"]
    col["fev_n"] = R["fev_n"].astype(np.float64)
    col["fev_vol"] = R["fev_vol"].astype(np.float64)
    col["fev_sflow_signed"] = R["fev_sflow"].astype(np.float64) * side

    # level
    for k in ("level_dist_atr", "refail_dist_usd"):
        col[k] = R[k]
    for k in ("n_conf_fam_at_refail", "n_conf_fam_at_refail_2t",
              "refail_gap_sec", "refail_age_sec", "pivot_age_sec"):
        col[k] = R[k].astype(np.float64)

    # events
    for k in ("thru_n", "thru_bid", "thru_ask", "n_ev_60"):
        col[k] = R[k].astype(np.float64)
    tb = R["thru_bid"].astype(np.float64)
    ta = R["thru_ask"].astype(np.float64)
    den = tb + ta
    col["thru_imb"] = np.where(den > 0, (tb - ta) / np.maximum(den, 1.0), np.nan)
    for k in ("c2f_60", "c2f_300", "dbsz_min", "dasz_min"):
        col[k] = R[k]
    # the erosion term on the side the trade FADES: a SHORT fades a high, so the
    # book side it leans on is the ask.  State only — the side READING is barred.
    col["erosion_with_side"] = np.where(side > 0, R["dbsz_min"], R["dasz_min"])

    # fuel / POC
    fa = R["fuel_above"].astype(np.float64)
    fbl = R["fuel_below"].astype(np.float64)
    ft = R["fuel_total"].astype(np.float64)
    col["fuel_above"] = fa
    col["fuel_below"] = fbl
    col["fuel_total"] = ft
    col["fuel_share_above"] = np.where(ft > 0, fa / np.maximum(ft, 1.0), np.nan)
    against = np.where(side > 0, fa, fbl)
    col["fuel_share_with"] = np.where(ft > 0, against / np.maximum(ft, 1.0),
                                      np.nan)
    col["d_poc_usd"] = R["d_poc"]
    col["in_va"] = R["in_va"].astype(np.float64)

    # cross-asset
    for k, v in xa.items():
        col[k] = v

    # forecaster
    col["fc_available"] = fc["fc_available"]
    col["fc_anchor_age_sec"] = fc["fc_anchor_age_sec"]
    col["fc_p_expansion"] = fc["fc_p_expansion"]
    col["fc_range_hat_usd"] = fc["fc_range_hat_usd"]
    col["fc_range_hat_q10"] = fc["fc_range_hat_q10"]
    col["fc_range_hat_q90"] = fc["fc_range_hat_q90"]
    col["fc_range_vs_trailing"] = fc["fc_range_hat_vs_trailing"]
    col["fc_share_TOKYO"] = fc["fc_share_hat_TOKYO"]
    col["fc_share_LONDON"] = fc["fc_share_hat_LONDON"]
    col["fc_share_NY"] = fc["fc_share_hat_NY"]
    col["fc_menu_hat"] = fc["fc_menu_hat"]
    col["fc_bench_base_rate"] = fc["fc_bench_base_rate"]
    col["fc_bench_persistence"] = fc["fc_bench_persistence"]
    col["fc_bench_range_trailmed"] = fc["fc_bench_range_trailmed"]
    col["fc_n_feature_missing"] = fc["fc_n_feature_missing"]

    # regime
    for k in ("day_type_frac", "surprise", "range_hat_usd", "range_so_far_usd",
              "atr_usd", "spread_dec_usd", "spread_ratio", "dom_share"):
        col[k] = R[k]
    for k in ("regime_tercile", "day_type", "ladder_band"):
        col[k] = R[k].astype(np.float64)

    # era / asset
    for a in M3.ASSET_ORDER:
        col["asset_" + a] = (R["asset"] == a).astype(np.float64)
    col["era_ord"] = np.array([M3.ERA_NAMES.index(MC.era_of(int(d))) + 1.0
                               if MC.era_of(int(d)) in M3.ERA_NAMES else np.nan
                               for d in R["d8"].tolist()])
    col["month"] = ((R["d8"] // 100) % 100).astype(np.float64)

    # flow
    col["side"] = side
    for k in ("slope_1m_usd", "slope_5m_usd", "accel_usd"):
        col[k] = R[k]
    col["slope_1m_with"] = R["slope_1m_usd"] * side
    col["slope_5m_with"] = R["slope_5m_usd"] * side
    for w in ("f60", "f5m", "f30m", "fph"):
        col[w + "_n"] = R[w + "_n"].astype(np.float64)
        col[w + "_vol"] = R[w + "_vol"].astype(np.float64)
        col[w + "_sflow_with"] = R[w + "_sflow"].astype(np.float64) * side
    ph = R["fph_sflow"].astype(np.float64)
    for nm, other in (("flow_disagree_30m", R["f30m_sflow"].astype(np.float64)),
                      ("flow_disagree_5m", R["f5m_sflow"].astype(np.float64))):
        col[nm] = ((np.sign(ph) != np.sign(other)) & (ph != 0)
                   & (other != 0)).astype(np.float64)

    # geometry
    col["extreme_age_sec"] = R["extreme_age_sec"].astype(np.float64)
    col["ext_needed_usd"] = R["ext_needed_usd"]
    up = (R["phase_hi"] - R["mid_now"]) * mult
    dn = (R["mid_now"] - R["phase_lo"]) * mult
    col["room_with_usd"] = np.where(side > 0, up, dn)
    col["room_against_usd"] = np.where(side > 0, dn, up)
    span = (R["phase_hi"] - R["phase_lo"])
    col["pos_in_phase_range"] = np.where(
        span > 0, (R["mid_now"] - R["phase_lo"]) / np.where(span > 0, span, 1.0),
        np.nan)
    col["ret_sess_open_with"] = (R["mid_now"] - R["sess_open_mid"]) * mult * side
    col["ret_phase_open_with"] = (R["mid_now"] - R["phase_open_mid"]) * mult * side
    col["prev_phase_ret_with"] = R["prev_phase_ret_usd"] * side
    col["prev_phase_range_usd"] = R["prev_phase_range_usd"]
    col["pre_cell_range_usd"] = R["pre_cell_range_usd"]
    col["conf_to_dec_sec"] = (R["dec_sec"] - R["conf_sec"]).astype(np.float64)

    # episode
    col["ep_is_earliest"] = (ep_rank == 0).astype(np.float64)
    col["ep_rank"] = ep_rank.astype(np.float64)
    col["ep_age_sec"] = (R["dec_sec"] - ep_first).astype(np.float64)
    col["cell_is_open_row"] = R["cell_open"].astype(np.float64)
    col["cell_age_sec"] = (R["dec_sec"] - R["cell_first_dec_sec"]).astype(np.float64)
    col["cell_rank_so_far"] = _rank_so_far(R, phase=True)
    col["sess_rank_so_far"] = _rank_so_far(R, phase=False)

    # ---- teacher evidence (D-078; design/TEACHER_FEATURES_V1.md) ----------
    # `coverage_phase` is a RATIO on the frame (pattern_lib.py:852) and a
    # PERCENT in the round's tables; the identity `unspent = q50 * (1 - cov)`
    # is info_ceiling.py:184's, unchanged.
    q50 = R["exp_move_q50_phase_usd"].astype(np.float64)
    cov = R["coverage_phase"].astype(np.float64)
    unspent = q50 * (1.0 - cov)
    col["tf_unspent_phase_usd"] = unspent
    col["tf_range_phase_usd"] = q50 * cov
    col["tf_cov_phase_pct"] = 100.0 * cov
    rwp = R["runway_phase_sec"].astype(np.float64)
    col["tf_seat_live"] = _tf_bool((unspent >= 700.0) & (rwp >= 18000.0),
                                   unspent)
    col["tf_seat_dead_time"] = (rwp < 4800.0).astype(np.float64)
    col["tf_phase_spent"] = _tf_bool(cov >= 0.80, cov)
    col["tf_cov_sweet_20_60"] = _tf_bool((cov >= 0.20) & (cov < 0.60), cov)
    room = _tf_bool(unspent >= 400.0, unspent)
    col["tf_capacity_room"] = room
    col["tf_capacity_big"] = _tf_bool(unspent >= 1000.0, unspent)
    near_d = R["tf_near_d_usd"]
    min_tc = R["tf_min_tc_near"]
    col["tf_near_d_usd"] = near_d
    col["tf_n_near100"] = R["tf_n_near100"]
    col["tf_min_tc_near"] = min_tc
    col["tf_level_virgin"] = _tf_bool(min_tc == 0.0, min_tc)
    lvl_near = _tf_bool(np.abs(near_d) <= 60.0, near_d)
    col["tf_level_near"] = lvl_near
    age = R["phase_age_sec"].astype(np.float64)
    seg = age + rwp
    with np.errstate(invalid="ignore", divide="ignore"):
        pof = np.where(seg > 0, age / np.where(seg > 0, seg, 1.0), np.nan)
    col["tf_phase_open_frac"] = pof
    reset = _tf_bool((pof <= 0.15) & (unspent >= 400.0), pof + unspent)
    col["tf_phase_open_reset"] = reset
    f5m = R["f5m_sflow"].astype(np.float64) * side
    fph = R["fph_sflow"].astype(np.float64) * side
    one_sided = (f5m > 0) & (fph > 0)
    col["tf_named_triad"] = _tf_bool(
        (reset > 0.5) & (lvl_near > 0.5) & one_sided, pof + unspent + near_d)
    col["tf_named_triad_soft"] = _tf_bool(
        (room > 0.5) & (lvl_near > 0.5) & (f5m > 0), unspent + near_d)
    return col


def _tf_bool(pred, carrier):
    """A gate is a REFUSAL wherever the field it reads is missing.

    `False` and `unknown` are different answers and D-022 forbids collapsing
    them: a `NaN` coverage must not print as "the phase is not spent".  Every
    teacher gate is therefore NaN wherever its carrier is NaN — XGBoost's
    default direction handles the missing branch, which is the whole reason the
    matrix stores typed-missing rather than imputing.
    """
    return np.where(np.isfinite(np.asarray(carrier, dtype=np.float64)),
                    np.asarray(pred, dtype=np.float64), np.nan)


def _cell_open_value(R, v):
    """`v` read at the CELL's first candidate row (a strictly past fact)."""
    n = v.size
    key = np.array(["%s|%08d|%d" % (a, d, p) for a, d, p in
                    zip(R["asset"].tolist(), R["d8"].tolist(),
                        R["phase_dec"].tolist())])
    order = np.lexsort((R["dec_sec"], key))
    ko = key[order]
    starts = [0] + (np.flatnonzero(ko[1:] != ko[:-1]) + 1).tolist()
    stops = starts[1:] + [n]
    out = np.full(n, np.nan)
    for s, e in zip(starts, stops):
        sel = order[s:e]
        out[sel] = v[sel[0]]
    return out


def _rank_so_far(R, phase):
    """How many candidates of the unit already fired — a count of the PAST."""
    n = R["dec_sec"].size
    if phase:
        key = np.array(["%s|%08d|%d" % (a, d, p) for a, d, p in
                        zip(R["asset"].tolist(), R["d8"].tolist(),
                            R["phase_dec"].tolist())])
    else:
        key = np.array(["%s|%08d" % (a, d) for a, d in
                        zip(R["asset"].tolist(), R["d8"].tolist())])
    order = np.lexsort((R["dec_sec"], key))
    ko = key[order]
    starts = [0] + (np.flatnonzero(ko[1:] != ko[:-1]) + 1).tolist()
    stops = starts[1:] + [n]
    out = np.zeros(n, dtype=np.float64)
    for s, e in zip(starts, stops):
        sel = order[s:e]
        out[sel] = np.arange(sel.size, dtype=np.float64)
    return out


PARAMS = {
    "section": SECTION,
    "harness": M3.HARNESS_VERSION,
    "brief": M3.BRIEF,
    "grain": "one row per generation-v3 roster candidate",
    "population": "every FIT + GATE session of SI/HG/NKD; the D-058 pre-exam "
                  "holdout is EXCLUDED BY THE GUARDED ENUMERATOR "
                  "(pattern_lib.sessions_fit) and REFUSED by "
                  "m3_common.check_holdout if it ever reaches the matrix",
    "source": "pattern_lib.frame(with_levels=True, with_v3=True) + the four "
              "census helpers imported verbatim (batch5._s10_of / "
              "batch5._unspent_session / batch5._event_stats / "
              "batch4._mins_to_release) — no second definition of anything",
    "joins": {"forecaster": "latest anchor with anchor_sec <= dec_sec; "
                            "typed-missing (fc_available=0) where there is none",
              "news": "NEWS_DISTANCE.tsv on cid; absence = no release within "
                      "+/-15min",
              "cross_asset": "the most recent CLOSED cell of each asset whose "
                             "last candidate row sits at or before this row's "
                             "epoch second, own-asset leg stepped back past "
                             "self (batch4 R76), freshness <= %d days"
                             % B4.P031_SRC_MAX_AGE_DAYS},
    "targets": {"primary": "y_retg_rank_phase = retg|e30|sess_close, "
                           "rank-within-PHASE — the atlas champion class, the "
                           "one rank cell top-ranked for all three assets "
                           "(ATLAS_V3_REPORT.md); §2.5: the RANK TRANSFORM "
                           "wins, the ranking OBJECTIVE loses",
                "winner": "D-021 walled winner indicator, refusals excluded "
                          "from both halves (R122)",
                "t1": "CC-M2-2.2(b) pairwise preference in Borda form, at the "
                      "frozen EPISODE_CAUSAL group (primary) and the "
                      "(asset,phase) CELL (variant)"},
    "no_teacher": bool(NO_TEACHER),
    "teacher_evidence_features": int(N_TEACHER),
    "teacher_features_spec": "design/TEACHER_FEATURES_V1.md §2 (PROVEN) + §3 "
                             "(SUPPORTED); §4 FALSIFIED cues are NOT shipped "
                             "as standalone columns and §6 HYPOTHESIS cues are "
                             "not shipped at all (TF-H1 is graded DEAD by "
                             "round 2; TF-H2/TF-H3 have no committed field)",
    "n_features": len(FEATURES),
    "feature_groups": {g: sum(1 for f in FEATURES if f.group == g)
                       for g in GROUPS},
    "guards": {"holdout": "m3_common.check_holdout — a refusal, never a filter",
               "forward_name": "m3_common.FORBIDDEN_SOURCES (OUTCOME / TRAP / "
                               "DECLARED)",
               "forward_value": "|Spearman| vs any outcome > %.3f is a refusal"
                                % M3.FORWARD_RHO},
    "determinism": "no RNG; every grouping is an explicit lexsort; the "
                   "forward-value probe walks a fixed stride",
}


def build(assets=M3.ASSET_ORDER, workers=8, limit=None, out_dir=None):
    t0 = time.time()
    MC.verify_spec(force=True)
    parts, scan_meta = scan(assets=assets, workers=workers, limit=limit)
    R = _concat(parts)
    del parts

    # THE HOLDOUT GUARD, on the assembled matrix (not on the enumerator's word)
    M3.check_holdout(R["d8"])

    M3.hb("m3 matrix: joining forecaster ...")
    fc = join_forecaster(R)
    M3.hb("m3 matrix: joining news distance ...")
    nd = join_news(R)
    M3.hb("m3 matrix: joining cross-asset ...")
    xa = join_cross_asset(R)
    M3.hb("m3 matrix: episodes ...")
    ep, ep_rank, ep_first, n_ep = episode_keys(R)
    M3.hb("m3 matrix: targets ...")
    Y = build_targets(R, ep)
    M3.hb("m3 matrix: columns ...")
    col = build_columns(R, fc, nd, xa, ep, ep_rank, ep_first)

    missing = [f.name for f in FEATURES if f.name not in col]
    extra = [k for k in col if k not in FEATURE_GROUP]
    if missing or extra:
        raise M3.HarnessRefusal(
            "registry/builder disagreement: missing=%s extra=%s"
            % (missing[:8], extra[:8]))
    M3.check_forbidden_names(FEATURES)

    n = R["dec_sec"].size
    Xm = np.empty((n, len(FEATURES)), dtype=np.float32)
    for j, f in enumerate(FEATURES):
        Xm[:, j] = np.asarray(col[f.name], dtype=np.float32)

    outc = {k: np.asarray(R[k], dtype=np.float64) for k in OUTCOMES}
    M3.hb("m3 matrix: forward-feature value guard ...")
    M3.check_forward_values(list(FEATURE_NAMES), Xm, outc)

    era_idx = np.array([M3.ERA_NAMES.index(MC.era_of(int(d)))
                        if MC.era_of(int(d)) in M3.ERA_NAMES else -1
                        for d in R["d8"].tolist()], dtype=np.int16)
    asset_idx = np.array([M3.ASSET_ORDER.index(a) for a in R["asset"].tolist()],
                         dtype=np.int8)

    out_dir = out_dir or M3.MATRIX_DIR
    os.makedirs(out_dir, exist_ok=True)
    payload = {"X": Xm, "feature_names": np.array(FEATURE_NAMES),
               "feature_groups": np.array([FEATURE_GROUP[nm]
                                           for nm in FEATURE_NAMES]),
               "cid": R["cid"], "asset_idx": asset_idx, "d8": R["d8"],
               "dec_sec": R["dec_sec"], "side": R["side"].astype(np.int8),
               "phase_dec": R["phase_dec"].astype(np.int8), "era_idx": era_idx,
               "ep": ep, "row_ts": (R["open_utc"] + R["dec_sec"]),
               "cost_fallback": R["cost_fallback"]}
    for k, v in Y.items():
        payload[k] = np.asarray(v, dtype=np.float64)
    for k, v in outc.items():
        payload[k] = v
    path = os.path.join(out_dir, "matrix.npz")
    np.savez(path + ".tmp.npz", **payload)
    os.replace(path + ".tmp.npz", path)

    era_counts = {}
    for e in range(len(M3.ERA_NAMES)):
        m = era_idx == e
        skey = np.array(["%s|%08d" % (a, d) for a, d in
                         zip(R["asset"][m].tolist(), R["d8"][m].tolist())])
        era_counts[M3.ERA_NAMES[e]] = {
            "rows": int(m.sum()),
            "asset_sessions": int(np.unique(skey).size) if m.any() else 0,
            "dates": int(np.unique(R["d8"][m]).size) if m.any() else 0,
            "fc_available": float(fc["fc_available"][m].mean()) if m.any() else 0.0,
            "y_retg_defined": int(np.isfinite(Y["y_retg_rank_phase"][m]).sum()),
            "y_winner_rate": (float(np.nanmean(Y["y_winner"][m]))
                              if m.any() else float("nan")),
        }
    rec = M3.env_receipt(dict(PARAMS, scan=scan_meta, n_rows=int(n),
                              n_episodes=int(n_ep),
                              n_news_joined=int(nd["_n_joined"]),
                              era_counts=era_counts,
                              elapsed_sec=round(time.time() - t0, 1)))
    rec["params_hash"] = M3.params_hash(PARAMS)
    M3.write_json(os.path.join(out_dir, "matrix.receipt.json"), rec)
    M3.hb("m3 matrix: %d rows x %d features -> %s (%.1fs)"
          % (n, len(FEATURES), path, time.time() - t0))
    return path


def describe():
    lines = ["PORT M3 FEATURE REGISTRY (%d features, %d groups; NO_TEACHER=%s)"
             % (len(FEATURES), len(GROUPS), NO_TEACHER), ""]
    for g in GROUPS:
        fs = [f for f in FEATURES if f.group == g]
        lines.append("== %s (%d)" % (g, len(fs)))
        for f in fs:
            lines.append("   %-28s <- %-40s %s"
                         % (f.name, ",".join(f.sources), f.doc[:80]))
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--describe", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--assets", nargs="*", default=list(M3.ASSET_ORDER))
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--outdir", default=None)
    a = ap.parse_args()
    if a.describe:
        print(describe())
        return 0
    if a.build:
        build(assets=tuple(a.assets), workers=a.workers, limit=a.limit,
              out_dir=a.outdir)
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
