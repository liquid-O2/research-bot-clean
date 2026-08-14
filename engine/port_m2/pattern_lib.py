#!/usr/bin/python3
"""PORT M2 — the PATTERN SUBSTRATE: one causal per-session frame, read by both
the reference-class retrieval tool (retrieve.py, CC-M2-5 item 3) and the
name->count pattern censuses (p001_census.py, DISCRETIONARY_METHOD §4.2).

WHY ONE MODULE
  The sheet renderer (sections.py) computes a candidate's causal state ONE
  CANDIDATE AT A TIME, because a sheet is one candidate's view.  A census reads
  1.58M candidates and a retrieval reads ~25, so neither can afford (nor needs)
  the text path.  Formula fidelity (D-006) forbids a SECOND definition of the
  same quantity, so every field here is the vectorised form of exactly one
  sections.py line, and test_pattern.t01 pins the two together on the committed
  P-M2c warm-up sheets: a drift in either direction fails the test.

CAUSALITY
  Every field is computed from data STRICTLY at or before the candidate's
  decision second, using the same SANE (D-054) mid grid the sheets use:
    * `s.vt` / `s.vm` are the b7_sane-masked observed seconds;
    * any window read is a searchsorted on `s.vt` bounded at `dec_sec`;
    * the ZigZag pivot chain uses c_c_roster.zigzag_scan, which is an ONLINE
      scan: a pivot's (price, pivot_sec, confirmation_sec) never depends on
      data after its confirmation second, so scanning the whole session once
      and then keeping `conf_sec < dec_sec` is identical to (and much cheaper
      than) re-scanning the truncated prefix per candidate.  test_pattern.t02
      proves that identity against sections._pivots.
  Nothing in this module reads a forward field.  The KNOWN_TRAPS registry
  (m2_common) names the receipt columns that would leak if read directly; the
  only one this module touches is levels_v4, and only through the level-BIRTH
  guard (V1.1 defect D4) plus a strict `touch_sec < dec_sec` filter.

THE FRAME
  `frame(asset, d8, with_levels=False)` returns a dict of numpy arrays, one row
  per roster candidate of that (asset, session), in roster order.  Columns are
  documented in FRAME_FIELDS below and stamped into every consumer's receipt.

THE V2 FIELD BLOCK (CC-M2-12 census batch 3)
  Batch 3 needs four things the V1 frame did not carry: the REFAIL geometry
  (P024 — two same-type causal pivots at one price within minutes), the
  session's OBSERVED close (D15 — a holiday tape ends hours before the nominal
  close and every nominal runway on such a session is wrong), the BINDING
  runway that follows from it (P025), and the level-family CONFLUENCE at the
  refail price (P024's S4 term).  They are additive: `FRAME_FIELDS` and
  `PARAMS_FRAME` are LEFT BYTE-IDENTICAL so that p001_census / p020_census
  re-run to the same params_hash they already have on record, and the new
  fields are documented in `FRAME_FIELDS_V2` / `PARAMS_FRAME_V2`, which only
  the batch-3 census stamps into its receipt.

Run (self-check on one session):
  /usr/bin/python3 engine/port_m2/pattern_lib.py SI 20210701
"""
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import m2_common as MC                    # noqa: E402
import assemble as A                      # noqa: E402
import common as C                        # noqa: E402
import census_common as X                 # noqa: E402
import c_a_cost as CA                     # noqa: E402
import c_c_roster as CC                   # noqa: E402

# ------------------------------------------------------------- vocabulary ---
# S9 ladder bands, as sections.s9_vol names them, in ASCENDING order.  The
# integer code is the ORDINAL used by the retrieval distance; -1 = REFUSED
# (the fvol row carried no move_q* quantiles — the V1.1 D1 law).
LADDER_BANDS = ("below_q10", "at_or_above_q10", "at_or_above_q25",
                "at_or_above_q50", "at_or_above_q75", "at_or_above_q90")
LADDER_CODE = {b: i for i, b in enumerate(LADDER_BANDS)}
LADDER_REFUSED = -1

# S2 regime tag -> vol tercile ordinal (b2_fvol writes LOW/MID/HIGH)
REGIME_TERCILE = {"LOW": 0, "MID": 1, "HIGH": 2}

# the two S9 rv nowcast windows P013 names (rv1800 / rv60)
RV_SHORT_SEC = 60
RV_LONG_SEC = 1800

# the S8 flow windows P022 reads, in seconds (s8_flow prints 60s/5m/30m/phase)
FLOW_5M_SEC = 300
FLOW_30M_SEC = 1800

# S2 day_type_so_far, as sections.s2_regime cuts it, in ASCENDING order.
DAY_TYPES = ("INSIDE", "AT_RANGE", "EXPANDED")
DAY_TYPE_REFUSED = -1
DAY_TYPE_CUT_INSIDE = 0.60
DAY_TYPE_CUT_AT_RANGE = 1.00

FRAME_FIELDS = {
    "i": "roster row index (union_roster_{ASSET}.npz)",
    "cid": "{ASSET}-{d8}-{dec_sec:06d}-{L|S}",
    "dec_sec": "decision second (session clock)",
    "side": "+1 LONG / -1 SHORT",
    "phase_dec": "roster phase_dec (the fvol segment key)",
    "phase_seg_start": "first second of the phase SEGMENT containing dec_sec",
    "phase_seg_end": "one past the last second of that segment",
    "klass": "m2_common.class_of(fam_mask)[0] (D-071, a partition)",
    "fam_mask": "generation-v3 family bitmask",
    "clock_sec": "(open_utc + dec_sec) % 86400 — clock-of-day, UTC",
    "coverage_phase": "sections.s3_path COVERAGE for the running phase = "
                      "SANE range so far in the phase / (move_q50_usd_per_"
                      "sigma * sigma_hat_usd) of that phase's fvol row; NaN "
                      "when the fvol row carries no q50 (REFUSED, V1.1 D1)",
    "coverage_session": "the same number on the SESSION clock/forecast",
    "ladder_band": "sections.s9_vol ladder_position as an ordinal (see "
                   "LADDER_BANDS); -1 = REFUSED (no move_q* in the fvol row)",
    "regime_tercile": "S2 regime_tag LOW/MID/HIGH -> 0/1/2; -1 = missing",
    "runway_phase_sec": "phase_close_sec - dec_sec (roster)",
    "runway_sess_sec": "sess_close_sec - dec_sec (roster)",
    "session_close_exit": "phase_close_sec == sess_close_sec — the S13 "
                          "exit_default IS the session close",
    "runway_frac": "runway_phase_sec / (phase_seg_end - phase_seg_start)",
    "phase_hi": "max SANE mid in [phase_seg_start, dec_sec)",
    "phase_hi_sec": "FIRST second at which phase_hi was reached",
    "phase_lo": "min SANE mid in [phase_seg_start, dec_sec)",
    "phase_lo_sec": "FIRST second at which phase_lo was reached",
    "extreme_age_sec": "dec_sec - phase_hi_sec (SHORT) or - phase_lo_sec "
                       "(LONG): the age of the phase extreme the trade fades",
    "pivot_age_sec": "dec_sec - pivot_sec of the most recent CAUSAL ZigZag "
                     "pivot of the faded type (HIGH for a SHORT, LOW for a "
                     "LONG), conf_sec < dec_sec; -1 = none yet",
    "mid_now": "SANE mid at dec_sec (last SANE second <= dec_sec)",
    "slope_1m_usd": "sections.s5_tminus mid_slope last-minute column = "
                    "(mid(dec) - mid(dec-60)) * mult",
    "slope_5m_usd": "(mid(dec) - mid(dec-300)) * mult / 5 — $ per minute",
    "accel_usd": "slope_1m_usd - slope_5m_usd  = S5 accel(1m-5m)",
    "rv60_usd": "S9 rv nowcast, 60s window",
    "rv1800_usd": "S9 rv nowcast, 1800s window",
    "rv_ratio": "rv1800_usd / rv60_usd (the P013 candidate marker)",
    "spread_dec_usd": "roster spread_at_decision",
    "spread_ratio": "spread_dec_usd / phase-median spread (c_a_cost, per "
                    "asset x phase) of the STRICTLY PRIOR calendar year — the "
                    "P005 'spread tax' state.  R119: the normaliser used to be "
                    "the decision's OWN calendar-year pooled median, which "
                    "includes the decision day and every day after it; that is "
                    "a forward statistic on a reader-facing retrieval axis "
                    "(B08).  NaN = REFUSED (no prior year on this asset's "
                    "tape); see spread_ratio_basis_year.",
    "spread_ratio_basis_year": "the calendar year whose pooled phase-median "
                               "spread normalised spread_ratio (always the "
                               "year BEFORE the decision); -1 = REFUSED",
    "cert_refused": "the walled certificate or the MAE could not be computed "
                    "for this candidate.  R122: `NaN >= 1000` is False, so "
                    "such a row used to be scored a MEASURED LOSER and counted "
                    "in every winner-rate denominator.  `winner` is now False "
                    "AND this flag is True, so a consumer can drop the row "
                    "from BOTH halves of a rate instead of biasing it low.",
    "phase_seg_end_is_session_end": "the running phase SEGMENT's end is the "
                                    "session's realised end (s.n), so any "
                                    "quantity divided by the segment length "
                                    "(runway_frac, retrieval axis B05) or "
                                    "defined over the whole segment "
                                    "(sched_release_in_phase) inherits an "
                                    "END-OF-SESSION fact on this row.  "
                                    "Declared, not silent.",
    "atr_usd": "roster atr14_usd (ATR14_prev)",
    "level_dist_atr": "|nearest KEPT-family level price - entry_mid| / ATR, "
                      "over levels alive at dec_sec (V1.1 birth guard) and "
                      "within +/-1.5xATR; NaN when there is none",
    "phase_age_sec": "dec_sec - phase_seg_start (the running phase's age)",
    "ext_needed_usd": "NEW range beyond the phase extreme the $1,000 bar still "
                      "needs: max(0, 1000 - (entry_mid - phase_lo)*mult) for a "
                      "SHORT, max(0, 1000 - (phase_hi - entry_mid)*mult) for a "
                      "LONG (e1d1_policy T3 / P016 clause 1)",
    "f60_n": "S8 60s window trade COUNT, sec in [dec-60, dec)",
    "f60_vol": "S8 60s window traded volume",
    "f60_sflow": "S8 60s signed flow (buy_vol - sell_vol)",
    "f5m_n": "S8 5m window trade count, sec in [dec-300, dec)",
    "f5m_vol": "S8 5m window traded volume",
    "f5m_sflow": "S8 5m signed flow (buy_vol - sell_vol)",
    "f30m_n": "S8 30m window trade count, sec in [dec-1800, dec)",
    "f30m_vol": "S8 30m window traded volume",
    "f30m_sflow": "S8 30m signed flow (buy_vol - sell_vol)",
    "fph_n": "S8 phase window trade count, sec in [phase_seg_start, dec)",
    "fph_vol": "S8 phase window traded volume",
    "fph_sflow": "S8 phase cumulative signed flow (buy_vol - sell_vol)",
    "range_hat_usd": "S2/S9 `range_hat_usd` of the DECISION PHASE's fvol row "
                     "(both sections read case.fvol_seg); NaN = REFUSED",
    "range_so_far_usd": "S2 range_so_far = SANE session range over [0, dec) "
                        "in dollars (= range_sess_usd)",
    "day_type_frac": "S2 range_so_far / range_hat — the '% of range_hat' the "
                     "sheet prints; NaN when range_hat is REFUSED",
    "day_type": "S2 day_type_so_far as an ordinal: 0 INSIDE (<0.60), "
                "1 AT_RANGE (<1.00), 2 EXPANDED (>=1.00); -1 = REFUSED",
    "surprise": "S9 realized_range_so_far / range_hat, where the realized "
                "range is the PHASE segment's [seg_start, dec) SANE range "
                "(S9's own numerator, not S2's); NaN = REFUSED",
    "release_ts": "epoch second of the most recent SCHEDULED release strictly "
                  "BEFORE decision_ts (BLS + FOMC calendars, SCHEDULE_EXEMPT "
                  "per D-057 — the dates are known months ahead); -1 = none",
    "release_age_sec": "decision_ts - release_ts, the S12 `last_scheduled` "
                       "age; -1 = no prior scheduled release",
    "release_sec": "release_ts on the SESSION clock (release_ts - open_utc); "
                   "-1 = none",
    "event_in_phase": "the release landed INSIDE the running phase and before "
                      "the decision: phase_seg_start <= release_sec < dec_sec",
    "fev_n": "EVENT-ANCHORED window (D10) trade count over [release_sec, dec); "
             "-1 = REFUSED (no release inside the phase)",
    "fev_vol": "event-anchored traded volume; -1 = REFUSED",
    "fev_sflow": "event-anchored signed flow (buy_vol - sell_vol) — the flow "
                 "accumulated SINCE the release, never across it; "
                 "0 with fev_n = -1 = REFUSED",
    "cert_close_usd": "c_c_roster.certificates(...)[1][0] — the walled "
                      "PHASE-CLOSE certificate (the CC-M1-8 adoption metric)",
    "cert_peak_usd": "c_c_roster.certificates(...)[0][0] — the walled "
                     "PEAK-EXIT companion (CC-M1-8 mandatory column)",
    "walled": "the $-wall was hit on the adverse skeleton",
    "mae_before_argmax": "roster mae_before_argmax (D-021 winner test)",
    "winner": "cert_close >= $1000 and mae <= $300 and not walled (D-021)",
}

# The V2 block (CC-M2-12 batch 3).  Kept OUT of FRAME_FIELDS on purpose: that
# dict is hashed into p001/p020's committed params_hash and must not move.
FRAME_FIELDS_V2 = {
    "tick_usd": "the asset's tick in dollars (common.ASSETS[asset]) — the "
                "'1 tick' unit P007's no-response term and P024's refail "
                "tolerance are both written in",
    "refail_gap_sec": "seconds between the last TWO causal ZigZag pivots of "
                      "the FADED type (HIGH for a SHORT, LOW for a LONG), both "
                      "conf_sec < dec_sec; -1 = fewer than two",
    "refail_dist_usd": "|price difference| between those two pivots, in "
                       "dollars (x mult); NaN = fewer than two",
    "refail_px": "price of the MORE RECENT of the two pivots (the refail "
                 "price); NaN = fewer than two",
    "refail_age_sec": "dec_sec - pivot_sec of that more recent pivot; -1 = "
                      "none (identical to pivot_age_sec by construction, "
                      "recomputed here from the same chain as a cross-check)",
    "short_day": "m0 session receipt meta `short_day` (PORT_M0_CENSUS_SPEC "
                 "§5: observed two-sided span < 20h) — the D15 holiday flag",
    "observed_close_sec": "m0 session receipt meta `last_two_sided_sec`: the "
                          "last second at which the book was two-sided, on "
                          "the session clock.  This is an END-OF-SESSION FACT "
                          "and is used ONLY to correct a runway after the "
                          "fact in a CENSUS; it is never a sheet field and "
                          "never available to a reader at decision time.",
    "runway_binding_sec": "min(runway_phase_sec, max(0, observed_close_sec - "
                          "dec_sec)) — the D15-corrected runway to the "
                          "BINDING exit (P025 reading B).  On a full session "
                          "it equals runway_phase_sec.  NOT CAUSAL: it is "
                          "built from an end-of-session fact and is therefore "
                          "a DIAGNOSTIC ONLY — R108 makes it ineligible for "
                          "promotion to an entry rule.",
    "runway_binding_refused": "the m0 receipt carried no last_two_sided_sec, "
                              "so runway_binding_sec DEGENERATED to the "
                              "nominal runway.  R110: this used to be a silent "
                              "pass-on-refused selector — reading B_observed "
                              "quietly became reading A_nominal on those "
                              "sessions with no flag and no counter.",
    "n_conf_fam_at_refail": "with_levels only: number of DISTINCT KEPT level "
                            "families whose level price is within 1 tick of "
                            "refail_px and whose level was BORN strictly "
                            "before dec_sec (sections._level_birth_sec, the "
                            "V1.1 D4 guard); -1 = not computed / no refail",
    "exit_close_sec": "c_c_roster.certificates(...)[1][2] — the second the "
                      "walled PHASE-CLOSE certificate exits (the one-position "
                      "scheduler's occupancy end)",
    "exit_peak_sec": "the same for the PEAK-EXIT companion",
    "sess_open_mid": "first SANE mid of the session",
    "phase_open_mid": "first SANE mid at/after the running phase's start",
    "n_conf_fam_at_refail_2t": "the same count at a TWO-tick tolerance.  Both "
                               "are reported because the day-3 birth case's "
                               "own confluence (4.3569 / 4.3584 around a "
                               "4.35775 double top) sits 1.3-1.7 ticks away: "
                               "the strict reading excludes the case the "
                               "pattern was born on, and saying so is the "
                               "point of carrying both.",
}

# The V3 block (CC-M2-17.5 census batch 4: P030 / P031 / CELL-SEAT EXISTENCE).
# Kept OUT of FRAME_FIELDS and FRAME_FIELDS_V2 for the same reason those two
# are separate: both are hashed into already-committed params_hashes and must
# not move.  Computed ONLY when frame(..., with_v3=True) — the fuel map costs a
# per-phase price-bucket pass and no earlier census needs it.
FRAME_FIELDS_V3 = {
    "fuel_above": "S8 FUEL MAP `trapped above_mid`: traded volume at a price "
                  "STRICTLY ABOVE entry_mid over [phase_seg_start, dec_sec) — "
                  "sections.s8_flow's own `above` integer, vectorised",
    "fuel_below": "S8 FUEL MAP `trapped below_mid` (px strictly below "
                  "entry_mid), same window",
    "fuel_total": "S8 FUEL MAP `phase_total` — all phase volume in the window "
                  "(fuel_above + fuel_below + volume AT the mid)",
    "cell_open": "this row is the FIRST candidate (lowest dec_sec; ties broken "
                 "to the LONG side, the roster's own order) of its "
                 "(asset, d8, phase_dec) CELL.  The cell key of CC-M2-17.1.",
    "cell_first_dec_sec": "dec_sec of that first candidate — the CELL OPEN as "
                          "the census defines it (the first second at which a "
                          "seat in this cell could be spent)",
    "prev_phase_ret_usd": "net SANE move of the PREVIOUS phase segment "
                          "(last mid - first mid) x mult; NaN when the running "
                          "phase is the session's first segment.  A "
                          "cell-open fact: the previous segment is closed.",
    "prev_phase_range_usd": "SANE range of that previous phase segment x mult; "
                            "NaN when there is none",
    "pre_cell_range_usd": "SANE range of the session over [0, phase_seg_start) "
                          "in dollars — everything the session had printed "
                          "before this cell opened.  For the session's FIRST "
                          "phase this is the OVERNIGHT/pre-open window, which "
                          "is why the census's `overnight range ratio` is "
                          "pre_cell_range_usd / atr_usd.",
    "sched_release_in_phase": "a SCHEDULED release (BLS + FOMC, "
                              "SCHEDULE_EXEMPT under D-057 — the dates are "
                              "published months ahead) falls inside "
                              "[phase_seg_start, phase_seg_end).  Unlike "
                              "`event_in_phase` this is knowable AT THE CELL "
                              "OPEN, which is what a seat-existence model may "
                              "read; it says nothing about the tape.",
    "dow": "day-of-week of the trade date, Monday=0 (calendar, not tape)",
}

PARAMS_FRAME_V3 = {
    "module": "engine/port_m2/pattern_lib.py (V3 block)",
    "order": "CC-M2-17.5 census batch 4",
    "fields_v3": FRAME_FIELDS_V3,
    "fuel_map": "sections.s8_flow's fuel map, verbatim: above = sum(size) "
                "over phase trades with px > entry_mid and sec < dec_sec; "
                "below = px < entry_mid; total = every phase trade in the "
                "window.  Computed as an offline price-bucket prefix over "
                "each phase SEGMENT (exact, not binned).",
    "cell": "(asset, d8, phase_dec) — CC-M2-17.1's seat-existence unit",
    "availability": "every V3 field is a CELL-OPEN fact or earlier; "
                    "sched_release_in_phase is calendar-only (D-057)",
}

PARAMS_FRAME_V2 = {
    "module": "engine/port_m2/pattern_lib.py (V2 block)",
    "order": "CC-M2-12 census batch 3",
    "fields_v2": FRAME_FIELDS_V2,
    "refail": "the two most recent pivots of the faded type CONFIRMED before "
              "dec_sec, taken from the SAME one-scan causal chain "
              "test_pattern.t02 pins against sections._pivots",
    "observed_close": "artifacts/cache/port/m0/sessions/{ASSET}/{d8}.npz "
                      "meta_json {short_day, last_two_sided_sec} — the "
                      "PORT_M0_CENSUS_SPEC §5 session receipt, read through "
                      "assemble.load_session (no second decode)",
    "confluence_tolerance": "1 tick",
}

PARAMS_FRAME = {
    "module": "engine/port_m2/pattern_lib.py",
    "sane_mask": "b7_sane (D-054) — installed by assemble.load_session",
    "causality": "every window is searchsorted on the SANE second grid and "
                 "bounded at dec_sec; ZigZag pivots kept only when "
                 "conf_sec < dec_sec",
    "fields": FRAME_FIELDS,
    "ladder_bands": list(LADDER_BANDS),
    "rv_windows_sec": [RV_SHORT_SEC, RV_LONG_SEC],
    "flow_windows_sec": [60, FLOW_5M_SEC, FLOW_30M_SEC, "phase", "event"],
    "day_type_cuts": {"INSIDE": "<0.60", "AT_RANGE": "<1.00",
                      "EXPANDED": ">=1.00"},
    "event_window": "D10 — sflow over [release_sec, dec_sec) when a SCHEDULED "
                    "release (BLS + FOMC calendars, context._bls_calendar / "
                    "context._fomc_calendar) landed inside the running phase. "
                    "The release is availability-lagged the same way S12's "
                    "`last_scheduled` is: only events with event_ts STRICTLY "
                    "< decision_ts are visible (CC-M2-1.2), and the calendar "
                    "itself is SCHEDULE_EXEMPT under D-057 because the dates "
                    "are published months ahead. The window NEVER spans the "
                    "release second: it starts AT it.",
    "fix_pass_D001": "R119 spread_ratio is normalised by the STRICTLY PRIOR "
                     "calendar year (was: the decision's own year, a forward "
                     "statistic on live retrieval axis B08); R120 "
                     "phase_open_mid carries the have_ph guard so it can no "
                     "longer emit a post-decision mid; R122 cert_refused makes "
                     "an uncomputable certificate a REFUSAL rather than a "
                     "measured loser, and the per-session cost fallback is "
                     "counted (cost_fallback); R110 runway_binding_refused "
                     "names the silent degeneration of reading B into reading "
                     "A; the ATR broadcast refuses instead of propagating a "
                     "sentinel.  These change the DEFINITION of committed "
                     "fields, so PARAMS_FRAME moves and every consumer's "
                     "params_hash moves with it — which is the point.",
}


# ----------------------------------------------------------------- helpers --
def _running_extremes(v):
    """(running max, index of its FIRST occurrence, running min, first index).

    np.argmax on a prefix returns the FIRST occurrence, which is what
    sections._hi_lo does, so the accumulate form has to reproduce that: a new
    record is a value STRICTLY beyond the previous running extreme.
    """
    n = v.size
    idx = np.arange(n)
    rmax = np.maximum.accumulate(v)
    new_hi = np.empty(n, dtype=bool)
    new_hi[0] = True
    new_hi[1:] = v[1:] > rmax[:-1]
    imax = np.maximum.accumulate(np.where(new_hi, idx, 0))
    rmin = np.minimum.accumulate(v)
    new_lo = np.empty(n, dtype=bool)
    new_lo[0] = True
    new_lo[1:] = v[1:] < rmin[:-1]
    imin = np.maximum.accumulate(np.where(new_lo, idx, 0))
    return rmax, imax, rmin, imin


def _phase_segments(s):
    """[(phase_code, start_sec, end_sec_exclusive)] — sections._phase_bounds."""
    out = []
    ch = [0] + [int(x) + 1 for x in
                np.nonzero(s.phase_tag[1:] != s.phase_tag[:-1])[0].tolist()]
    for i, st in enumerate(ch):
        en = ch[i + 1] if i + 1 < len(ch) else s.n
        out.append((int(s.phase_tag[st]), st, en))
    return out


def _pivot_chain(asset, s, trade_date, atr, tick_px, tick_usd, mult):
    """The causal ZigZag chain over the WHOLE session (sections._pivots, run
    once): (pivot_sec, pivot_px, side, conf_sec) sorted by pivot_sec.

    The PRICE column is the V2 addition (P024's refail geometry needs it).  A
    pivot second identifies a mid on the SANE grid, so every rung that finds
    the same (pivot_sec, side) finds the same price; the merge keeps the
    EARLIEST confirmation second, exactly as before.
    """
    vt_l = s.vt.tolist()
    vm_l = s.vm.tolist()
    if len(vt_l) < 2:
        return (np.zeros(0, np.int64), np.zeros(0, np.float64),
                np.zeros(0, np.int64), np.zeros(0, np.int64))
    vphase = s.phase_tag[s.vt].tolist()
    phase_med = CA.phase_median_spreads(MC.M0_ROOT)
    merged = {}
    for r in MC.RUNGS:
        per_phase = []
        for p in range(X.N_PHASES):
            pm = phase_med.get((asset, trade_date.year, X.PHASE_NAMES[p]),
                               float("nan"))
            fl = X.RUNG_FLOOR_SPREAD_MULT * pm if np.isfinite(pm) else 0.0
            u = max(r * atr, X.RUNG_FLOOR_TICKS * tick_usd, fl)
            per_phase.append(X.round_half_up(u / mult, tick_px))
        thr_l = [per_phase[p] for p in vphase]
        for (px, psec, csec, side) in CC.zigzag_scan(vt_l, vm_l, thr_l):
            k = (int(psec), int(side))
            e = merged.get(k)
            if e is None:
                merged[k] = (int(csec), float(px))
            else:
                merged[k] = (min(e[0], int(csec)), e[1])
    keys = sorted(merged)
    psec = np.array([k[0] for k in keys], dtype=np.int64)
    ppx = np.array([merged[k][1] for k in keys], dtype=np.float64)
    pside = np.array([k[1] for k in keys], dtype=np.int64)
    pconf = np.array([merged[k][0] for k in keys], dtype=np.int64)
    return psec, ppx, pside, pconf


def _last_pivot_age(psec, pside, pconf, dec_sec, want_side):
    """Age of the most recent pivot of `want_side` CONFIRMED before dec_sec.

    want_side = -1 (a confirmed HIGH, what a SHORT fades) / +1 (a LOW).
    Vectorised over dec_sec: the chain is sorted by pivot_sec, but the causal
    filter is on conf_sec, so the running "latest usable pivot_sec" is taken
    over the chain sorted by CONF second.
    """
    out = np.full(dec_sec.size, -1, dtype=np.int64)
    m = (pside == want_side)
    if not m.any():
        return out
    ps, pc = psec[m], pconf[m]
    o = np.argsort(pc, kind="stable")
    ps, pc = ps[o], pc[o]
    best = np.maximum.accumulate(ps)                # latest pivot_sec so far
    j = np.searchsorted(pc, dec_sec, side="left") - 1
    ok = j >= 0
    out[ok] = dec_sec[ok] - best[j[ok]]
    return out


def _last_two_pivots(psec, ppx, pside, pconf, dec_sec, want_side):
    """The REFAIL geometry: the two most recent pivots of `want_side` that are
    CONFIRMED before dec_sec.

    Returns (gap_sec, dist_px, last_px, last_sec), each -1/NaN where fewer than
    two such pivots exist.  The causal filter is on conf_sec (t02's law), so
    "most recent" is resolved over the chain sorted by CONFIRMATION second and
    the running top-2 PIVOT seconds are carried forward — a pivot may be
    confirmed after a later pivot of the same side, and the top-2 must be the
    two latest pivot seconds among those already confirmed.
    """
    n = dec_sec.size
    gap = np.full(n, -1, dtype=np.int64)
    dist = np.full(n, np.nan)
    lpx = np.full(n, np.nan)
    lsec = np.full(n, -1, dtype=np.int64)
    m = (pside == want_side)
    if int(m.sum()) < 2:
        return gap, dist, lpx, lsec
    ps, px, pc = psec[m], ppx[m], pconf[m]
    o = np.argsort(pc, kind="stable")
    ps, px, pc = ps[o], px[o], pc[o]
    # running top-2 pivot seconds (and their prices) over the confirmation order
    b1s = np.full(ps.size, -1, dtype=np.int64)
    b2s = np.full(ps.size, -1, dtype=np.int64)
    b1p = np.full(ps.size, np.nan)
    b2p = np.full(ps.size, np.nan)
    t1s = t2s = -1
    t1p = t2p = float("nan")
    for k in range(ps.size):
        s_k, p_k = int(ps[k]), float(px[k])
        if s_k > t1s:
            t2s, t2p = t1s, t1p
            t1s, t1p = s_k, p_k
        elif s_k > t2s:
            t2s, t2p = s_k, p_k
        b1s[k], b1p[k], b2s[k], b2p[k] = t1s, t1p, t2s, t2p
    j = np.searchsorted(pc, dec_sec, side="left") - 1
    ok = (j >= 0)
    if not ok.any():
        return gap, dist, lpx, lsec
    jj = j[ok]
    have2 = b2s[jj] >= 0
    idx = np.nonzero(ok)[0][have2]
    jj = jj[have2]
    if idx.size:
        gap[idx] = b1s[jj] - b2s[jj]
        dist[idx] = np.abs(b1p[jj] - b2p[jj])
        lpx[idx] = b1p[jj]
        lsec[idx] = b1s[jj]
    return gap, dist, lpx, lsec


def _prefix_sq(vm):
    """Prefix sums of squared consecutive SANE-mid increments (S9 _rv_usd)."""
    d = np.diff(vm.astype(np.float64))
    p = np.zeros(vm.size, dtype=np.float64)
    if d.size:
        p[1:] = np.cumsum(d * d)
    return p


def _rv_window(vt, prefix, lo_sec, hi_sec, mult):
    """sections._rv_usd, vectorised over (lo_sec, hi_sec) pairs."""
    a = np.searchsorted(vt, lo_sec, side="left")
    b = np.searchsorted(vt, hi_sec, side="left")
    out = np.full(a.size, np.nan)
    ok = (b - a) >= 3
    if ok.any():
        out[ok] = np.sqrt(np.maximum(prefix[b[ok] - 1] - prefix[a[ok]], 0.0)) * mult
    return out


def _f(v):
    return A._f(v)


# ------------------------------------------------------- scheduled releases -
# D10: the event-anchored flow window needs the SAME calendar S12 shows as
# `last_scheduled`, so it is read from context.py rather than re-parsed here
# (D-006: one definition of the release set).  The calendar is SCHEDULE_EXEMPT
# under D-057 — the release DATES are published months ahead — and the
# availability rule is the one CC-M2-1.2 blessed: an event is visible only when
# its event_ts is STRICTLY before decision_ts.
_CAL = None


def release_calendar():
    """(sorted epoch-second array, names) of every scheduled BLS/FOMC release."""
    global _CAL
    if _CAL is None:
        import context as CTX             # local: context pulls the ref tables
        cal = sorted(CTX._get("CAL_BLS", CTX._bls_calendar)
                     + CTX._get("CAL_FOMC", CTX._fomc_calendar))
        _CAL = (np.array([int(c[0]) for c in cal], dtype=np.int64),
                [str(c[1]) for c in cal])
    return _CAL


def last_release_ts(decision_ts):
    """Epoch second of the last release STRICTLY before each decision_ts.

    Vectorised form of context.recent_release's `ts < guard.decision_ts` scan
    (without its 24h display window — the age is returned and the caller cuts
    it, which is what the P022 `< 90min` clause needs).  -1 = none.
    """
    ts, _names = release_calendar()
    d = np.asarray(decision_ts, dtype=np.int64)
    j = np.searchsorted(ts, d, side="left") - 1
    out = np.full(d.size, -1, dtype=np.int64)
    ok = j >= 0
    if ok.any():
        out[ok] = ts[j[ok]]
    return out


# ------------------------------------------------------------ roster (lazy) -
# assemble.roster() eagerly materialises EVERY array of a 50-70MB npz and then
# builds a 500k-entry Python dedup index.  A census worker never needs the
# index, and a retrieval never needs the skeleton arrays, so this loader pulls
# members on demand (NpzFile decompresses per key) and memoises what it pulled.
# Measured on union_roster_HG.npz: the light key set costs 0.04s, the skeleton
# key set 0.66s, the assemble.roster() path 1.02s + the index.
_LIGHT_KEYS = ("date8", "dec_sec", "side", "phase_dec", "phase_close_sec",
               "sess_close_sec", "entry_mid", "atr14_usd",
               "spread_at_decision", "fam_mask", "mae_before_argmax")
_CERT_KEYS = ("a_off", "a_len", "f_off", "f_len", "skel_a_t", "skel_a_v",
              "skel_f_t", "skel_f_v", "f_phase_close", "f_sess_close")
_ROSTER = {}


def roster(asset, with_certs=True):
    """The frozen v3 roster arrays for `asset`, loaded lazily and memoised."""
    cur = _ROSTER.setdefault(asset, {})
    want = list(_LIGHT_KEYS) + (list(_CERT_KEYS) if with_certs else [])
    missing = [k for k in want if k not in cur]
    if missing:
        path = os.path.join(A.GEN_DIR, "union_roster_%s.npz" % asset)
        z = np.load(path, allow_pickle=False)
        for k in missing:
            cur[k] = z[k]
        z.close()
    return cur


# ------------------------------------------------------------- level state --
def _kept_levels(asset, d8, s, trade_date, profile):
    """(price, birth_sec, family) of every KEPT-family level of the session.

    Split out of _nearest_kept_level_atr so the level ledger is loaded and the
    birth rule evaluated EXACTLY ONCE per session even though two V2 consumers
    read it (nearest-level distance and P024's family confluence).
    """
    import sections as SEC                # local: sections imports are heavy

    z, _p = A.load_levels(asset, d8)
    if z is None or not int(z["level_price"].size):
        return (np.zeros(0, np.float64), np.zeros(0, np.int64),
                np.zeros(0, dtype="<U1"))
    fam = z["level_family"]
    lid = z["level_id"]
    lpx = z["level_price"].astype(np.float64)
    dyn = z["dynamic"]

    class _Shim(object):                   # what _level_birth_sec/_or_window read
        pass

    shim = _Shim()
    shim.asset = asset
    shim.d8 = int(d8)
    shim.s = s
    shim.trade_date = trade_date
    shim.profile = profile

    keep = np.array([str(f) in MC.KEPT_LEVEL_FAMILIES for f in fam.tolist()],
                    dtype=bool)
    born = np.array([SEC._level_birth_sec(shim, str(fam[r]), str(lid[r]),
                                          int(dyn[r]))
                     for r in range(int(lpx.size))], dtype=np.int64)
    ok = keep & np.isfinite(lpx) & (born >= 0)
    return lpx[ok], born[ok], fam[ok]


def _nearest_kept_level_atr(px, bn, dec_sec, entry_mid, atr, mult):
    """|nearest KEPT-family level - mid| / ATR at each decision second."""
    out = np.full(dec_sec.size, np.nan)
    if not px.size:
        return out
    band_px = 1.5 * atr / mult
    for k in range(dec_sec.size):
        alive = bn < dec_sec[k]            # STRICTLY before (CausalGuard.sec)
        if not alive.any():
            continue
        d = np.abs(px[alive] - entry_mid[k])
        d = d[d <= band_px]
        if d.size:
            out[k] = float(d.min()) * mult / atr
    return out


def _confluence_at(px, bn, fam, dec_sec, target_px, tol_px):
    """P024's S4 term: DISTINCT kept level families within `tol_px` of the
    refail price, counted over levels BORN strictly before dec_sec.

    -1 wherever the target price is undefined (no refail) — never 0, which
    would read as "checked and empty".
    """
    out = np.full(dec_sec.size, -1, dtype=np.int64)
    if not px.size:
        return out
    for k in range(dec_sec.size):
        t = target_px[k]
        if not np.isfinite(t):
            continue
        m = (bn < dec_sec[k]) & (np.abs(px - t) <= tol_px)
        out[k] = int(np.unique(fam[m]).size) if m.any() else 0
    return out


# ------------------------------------------------------------------ frame ---
def _fuel_map(t_sec, t_px, t_sz, seg_lo, seg_hi, dec_c, mid_c):
    """sections.s8_flow's FUEL MAP for every candidate of ONE phase segment.

    -> (above, below, total) int64 arrays, one entry per candidate: traded
    volume strictly above / strictly below that candidate's entry_mid, over
    [seg_lo, dec_sec).  `dec_c` MUST be ascending.

    Exact (not binned): the phase's distinct trade prices are the buckets, so
    the answer equals the naive `sz[(sec < dec) & (px > mid)].sum()` scan the
    sheet does per candidate — at O((T + C) x L) instead of O(C x T).
    """
    n_c = dec_c.size
    zero = np.zeros(n_c, dtype=np.int64)
    if n_c == 0:
        return zero, zero, zero
    hi = int(np.searchsorted(t_sec, int(dec_c[-1]), side="left"))
    lo = int(np.searchsorted(t_sec, int(seg_lo), side="left"))
    if hi <= lo:
        return zero, zero, zero
    px = t_px[lo:hi]
    sz = t_sz[lo:hi]
    sec = t_sec[lo:hi]
    levels, rank = np.unique(px, return_inverse=True)
    n_l = levels.size
    # bucket b: the trade is visible to candidates j >= b (sec < dec_c[j])
    bucket = np.searchsorted(dec_c, sec, side="right")
    above = np.empty(n_c, dtype=np.int64)
    below = np.empty(n_c, dtype=np.int64)
    total = np.empty(n_c, dtype=np.int64)
    step = max(1, int(4_000_000 // max(n_l, 1)))
    carry = np.zeros(n_l, dtype=np.int64)
    for c0 in range(0, n_c, step):
        c1 = min(c0 + step, n_c)
        m = (bucket >= c0) & (bucket < c1)
        M = np.zeros((c1 - c0, n_l), dtype=np.int64)
        if m.any():
            np.add.at(M, (bucket[m] - c0, rank[m]), sz[m])
        C = np.cumsum(M, axis=0) + carry[None, :]
        carry = C[-1].copy()
        P = np.cumsum(C, axis=1)
        tot = P[:, -1]
        r_lo = np.searchsorted(levels, mid_c[c0:c1], side="left")
        r_hi = np.searchsorted(levels, mid_c[c0:c1], side="right")
        rows = np.arange(c1 - c0)
        blw = np.where(r_lo > 0, P[rows, np.maximum(r_lo - 1, 0)], 0)
        ble = np.where(r_hi > 0, P[rows, np.maximum(r_hi - 1, 0)], 0)
        below[c0:c1] = blw
        above[c0:c1] = tot - ble
        total[c0:c1] = tot
    return above, below, total


def frame(asset, d8, with_levels=False, with_certs=True, with_v3=False):
    """Causal per-candidate state for every roster row of (asset, d8)."""
    d8 = int(d8)
    r = roster(asset, with_certs=with_certs)
    sel = np.nonzero(r["date8"] == d8)[0]
    spec = C.ASSETS[asset]
    mult = float(spec["mult"])
    out = {"asset": asset, "d8": d8, "n": int(sel.size)}
    if sel.size == 0:
        return None
    sess = A.load_session(asset, d8)
    s = sess["s"]
    trade_date = sess["trade_date"]

    dec = r["dec_sec"][sel].astype(np.int64)
    side = r["side"][sel].astype(np.int64)
    # the generation-v3 dedup key is (session, dec_sec, side); assemble.roster
    # asserts it globally, and this loader skips that index, so the property is
    # re-asserted here at session scope (a collision is a roster defect).
    if np.unique(np.stack([dec, side], 1), axis=0).shape[0] != dec.size:
        raise RuntimeError("roster %s %d: duplicate (dec_sec, side)"
                           % (asset, d8))
    order = np.argsort(dec, kind="stable")   # deterministic, dec-ascending work
    inv = np.empty(order.size, dtype=np.int64)
    inv[order] = np.arange(order.size)
    dec_s = dec[order]

    # --- phase segment containing dec_sec ---------------------------------
    segs = _phase_segments(s)
    seg_start = np.array([g[1] for g in segs], dtype=np.int64)
    seg_end = np.array([g[2] for g in segs], dtype=np.int64)
    k = np.searchsorted(seg_start, dec_s, side="right") - 1
    k = np.clip(k, 0, seg_start.size - 1)
    ph_start = seg_start[k]
    ph_end = seg_end[k]

    # --- running SANE extremes, per phase segment and per session ---------
    vt = s.vt
    vm = s.vm.astype(np.float64)
    rmax, imax, rmin, imin = _running_extremes(vm)
    j_dec = np.searchsorted(vt, dec_s, side="left") - 1     # last SANE sec < dec
    j_ph = np.searchsorted(vt, ph_start, side="left")       # first SANE in phase
    have_ph = (j_dec >= j_ph) & (j_dec >= 0)

    phase_hi = np.full(dec_s.size, np.nan)
    phase_lo = np.full(dec_s.size, np.nan)
    phase_hi_sec = np.full(dec_s.size, -1, dtype=np.int64)
    phase_lo_sec = np.full(dec_s.size, -1, dtype=np.int64)
    if have_ph.any():
        idx = np.nonzero(have_ph)[0]
        for t in idx.tolist():             # per-segment window, segments are few
            a, b = int(j_ph[t]), int(j_dec[t]) + 1
            w = vm[a:b]
            ih = int(np.argmax(w))
            il = int(np.argmin(w))
            phase_hi[t] = w[ih]
            phase_lo[t] = w[il]
            phase_hi_sec[t] = int(vt[a + ih])
            phase_lo_sec[t] = int(vt[a + il])

    sess_hi = np.where(j_dec >= 0, rmax[np.maximum(j_dec, 0)], np.nan)
    sess_lo = np.where(j_dec >= 0, rmin[np.maximum(j_dec, 0)], np.nan)

    # --- fvol rows (per phase segment + SESSION) --------------------------
    fv = A.fvol_rows()
    iso = trade_date.isoformat()
    phase_dec = r["phase_dec"][sel][order].astype(np.int64)
    q50_p = np.full(dec_s.size, np.nan)
    rng_hat = np.full(dec_s.size, np.nan)
    lad = np.full((dec_s.size, len(LADDER_BANDS) - 1), np.nan)
    terc = np.full(dec_s.size, -1, dtype=np.int64)
    seg_cache = {}
    for p in sorted(set(phase_dec.tolist())):
        row = fv.get((asset, iso, X.PHASE_NAMES[p]))
        sig = _f(row["sigma_hat_usd"]) if row else float("nan")
        qs = ([_f(row.get("move_%s_usd_per_sigma" % q)) * sig
               for q in ("q10", "q25", "q50", "q75", "q90")] if row
              else [float("nan")] * 5)
        seg_cache[p] = (qs, (row or {}).get("regime_tag", ""),
                        _f(row["range_hat_usd"]) if row else float("nan"))
    for p, (qs, tag, rh) in seg_cache.items():
        m = phase_dec == p
        q50_p[m] = qs[2]
        rng_hat[m] = rh
        lad[m, :] = np.array(qs)
        terc[m] = REGIME_TERCILE.get(str(tag), -1)
    row_s = fv.get((asset, iso, "SESSION"))
    sig_s = _f(row_s["sigma_hat_usd"]) if row_s else float("nan")
    q50_s = (_f(row_s.get("move_q50_usd_per_sigma")) * sig_s if row_s
             else float("nan"))

    range_phase = (phase_hi - phase_lo) * mult
    range_sess = (sess_hi - sess_lo) * mult
    with np.errstate(invalid="ignore", divide="ignore"):
        cov_p = np.where(np.isfinite(q50_p) & (q50_p > 0),
                         range_phase / q50_p, np.nan)
        cov_s = (range_sess / q50_s if np.isfinite(q50_s) and q50_s > 0
                 else np.full(dec_s.size, np.nan))

    # --- S2 day_type_so_far / S9 surprise ---------------------------------
    # Both sections read case.fvol_seg — the DECISION PHASE's fvol row — and
    # divide by ITS range_hat; they differ only in the numerator (S2 the
    # SESSION range so far, S9 the PHASE segment's).  Reproduced exactly:
    # sections.s2_regime `frac = spent / rng_hat` and sections.s9_vol
    # `surprise = realized / range_hat`, both REFUSED when range_hat is.
    with np.errstate(invalid="ignore", divide="ignore"):
        day_frac = np.where(np.isfinite(rng_hat) & (rng_hat > 0),
                            range_sess / rng_hat, np.nan)
        surprise = np.where(np.isfinite(rng_hat) & (rng_hat > 0),
                            range_phase / rng_hat, np.nan)
    day_type = np.where(
        ~np.isfinite(day_frac), DAY_TYPE_REFUSED,
        np.where(day_frac < DAY_TYPE_CUT_INSIDE, 0,
                 np.where(day_frac < DAY_TYPE_CUT_AT_RANGE, 1, 2))
    ).astype(np.int64)

    # ladder_position: the HIGHEST band the realized segment range reaches.
    # REFUSED (-1) whenever any quantile is missing or the range is undefined.
    band = np.full(dec_s.size, LADDER_REFUSED, dtype=np.int64)
    lad_ok = np.all(np.isfinite(lad), axis=1) & np.isfinite(range_phase)
    if lad_ok.any():
        b = np.zeros(dec_s.size, dtype=np.int64)
        for q in range(lad.shape[1]):
            b = np.where(lad_ok & (range_phase >= lad[:, q]), q + 1, b)
        band = np.where(lad_ok, b, LADDER_REFUSED)

    # --- S5 slope / accel --------------------------------------------------
    def mid_at(secs):
        j = np.searchsorted(vt, secs, side="right") - 1
        v = np.where(j >= 0, vm[np.maximum(j, 0)], np.nan)
        return np.where(secs < 0, np.nan, v)

    m_now = mid_at(dec_s)
    m_1 = mid_at(dec_s - 60)
    m_5 = mid_at(dec_s - 300)
    slope_1 = (m_now - m_1) * mult
    slope_5 = (m_now - m_5) * mult / 5.0
    accel = slope_1 - slope_5

    # --- S9 rv nowcasts ----------------------------------------------------
    pref = _prefix_sq(vm)
    rv60 = _rv_window(vt, pref, np.maximum(dec_s - RV_SHORT_SEC, 0), dec_s, mult)
    rv1800 = _rv_window(vt, pref, np.maximum(dec_s - RV_LONG_SEC, 0), dec_s, mult)
    with np.errstate(invalid="ignore", divide="ignore"):
        rv_ratio = np.where(rv60 > 0, rv1800 / rv60, np.nan)

    # --- S8 flow windows (vectorised sections.s8_flow) ---------------------
    # prefix sums over the session's trade tape: every window is a difference,
    # and every window is [lo, dec_sec) exactly as s8_flow reads it.
    tr = sess["trades"]
    t_sec = tr["sec"]
    t_sz = tr["size"].astype(np.int64)
    t_sd = tr["side"]
    signed = np.where(t_sd == ord("B"), t_sz,
                      np.where(t_sd == ord("A"), -t_sz, 0))
    c_n = np.concatenate(([0], np.cumsum(np.ones(t_sz.size, dtype=np.int64))))
    c_v = np.concatenate(([0], np.cumsum(t_sz)))
    c_s = np.concatenate(([0], np.cumsum(signed)))
    b_hi = np.searchsorted(t_sec, dec_s, side="left")
    b_60 = np.searchsorted(t_sec, np.maximum(dec_s - 60, 0), side="left")
    b_5m = np.searchsorted(t_sec, np.maximum(dec_s - FLOW_5M_SEC, 0),
                           side="left")
    b_30m = np.searchsorted(t_sec, np.maximum(dec_s - FLOW_30M_SEC, 0),
                            side="left")
    b_ph = np.searchsorted(t_sec, ph_start, side="left")
    f60_n = c_n[b_hi] - c_n[b_60]
    f60_v = c_v[b_hi] - c_v[b_60]
    f60_s = c_s[b_hi] - c_s[b_60]
    f5m_n = c_n[b_hi] - c_n[b_5m]
    f5m_v = c_v[b_hi] - c_v[b_5m]
    f5m_s = c_s[b_hi] - c_s[b_5m]
    f30m_n = c_n[b_hi] - c_n[b_30m]
    f30m_v = c_v[b_hi] - c_v[b_30m]
    f30m_s = c_s[b_hi] - c_s[b_30m]
    fph_n = c_n[b_hi] - c_n[b_ph]
    fph_v = c_v[b_hi] - c_v[b_ph]
    fph_s = c_s[b_hi] - c_s[b_ph]

    # --- D10: the EVENT-ANCHORED flow window -------------------------------
    # E1D2-F3: "measure the imbalance accumulated SINCE the last S12
    # last_scheduled event, not since the phase open".  The window is
    # [release_sec, dec_sec) and exists ONLY when the release landed inside the
    # running phase and strictly before the decision; otherwise every field is
    # REFUSED (-1), never silently equal to the phase window — a window that
    # started before the release would be the fossil the pattern is about.
    open_utc = int(s.meta["open_utc"])
    rel_ts = last_release_ts(open_utc + dec_s)
    rel_sec = np.where(rel_ts >= 0, rel_ts - open_utc, -1).astype(np.int64)
    rel_age = np.where(rel_ts >= 0, (open_utc + dec_s) - rel_ts, -1)
    in_phase = (rel_ts >= 0) & (rel_sec >= ph_start) & (rel_sec < dec_s)
    b_ev = np.searchsorted(t_sec, np.maximum(rel_sec, 0), side="left")
    fev_n = np.where(in_phase, c_n[b_hi] - c_n[b_ev], -1)
    fev_v = np.where(in_phase, c_v[b_hi] - c_v[b_ev], -1)
    fev_s = np.where(in_phase, c_s[b_hi] - c_s[b_ev], 0)

    # --- pivots ------------------------------------------------------------
    # MINOR (3.2c): `atr` was taken from ONE arbitrary roster row with no
    # finite/positive guard and broadcast to every candidate, so a zero or NaN
    # ATR propagated silently into band_px and the /atr level distance as
    # inf/NaN.  Take the median over the session's rows and REFUSE loudly.
    _atr_col = r["atr14_usd"][sel].astype(np.float64)
    _atr_ok = np.isfinite(_atr_col) & (_atr_col > 0)
    if not _atr_ok.any():
        raise RuntimeError("pattern_lib: %s %d has no finite positive ATR14 on "
                           "any of its %d roster rows — refusing rather than "
                           "broadcasting a sentinel" % (asset, d8, sel.size))
    atr = float(np.median(_atr_col[_atr_ok]))
    n_atr_refused = int((~_atr_ok).sum())
    psec, ppx, pside, pconf = _pivot_chain(asset, s, trade_date, atr,
                                           float(spec["tick_px"]),
                                           float(spec["tick_usd"]), mult)
    want = np.where(side[order] < 0, -1, 1)
    pivot_age = np.full(dec_s.size, -1, dtype=np.int64)
    # V2: the refail geometry (P024) — two pivots of the faded type
    rf_gap = np.full(dec_s.size, -1, dtype=np.int64)
    rf_dist = np.full(dec_s.size, np.nan)
    rf_px = np.full(dec_s.size, np.nan)
    rf_age = np.full(dec_s.size, -1, dtype=np.int64)
    for w in (-1, 1):
        m = want == w
        if m.any():
            pivot_age[m] = _last_pivot_age(psec, pside, pconf, dec_s[m], w)
            g, d, p, ls = _last_two_pivots(psec, ppx, pside, pconf,
                                           dec_s[m], w)
            rf_gap[m] = g
            rf_dist[m] = d * mult
            rf_px[m] = p
            rf_age[m] = np.where(ls >= 0, dec_s[m] - ls, -1)

    # --- certificates (c_c_roster, verbatim) -------------------------------
    wall = float(A.walls()[asset]["wall_usd"])
    cost = A.cost_map().get((asset, iso), float("nan"))
    # R122/R23: the per-session cost fallback was silent.  It feeds cert_close
    # -> winner -> the D-021 menu target, so it is COUNTED and carried on the
    # frame; every consumer stamps it into its receipt.
    cost_fallback = int(not np.isfinite(cost))
    if not np.isfinite(cost):
        cost = C.FEES_RT
    cert_close = np.full(sel.size, np.nan)
    cert_peak = np.full(sel.size, np.nan)
    exit_close = np.full(sel.size, -1, dtype=np.int64)
    exit_peak = np.full(sel.size, -1, dtype=np.int64)
    walled = np.zeros(sel.size, dtype=bool)
    if with_certs:
        for t in range(sel.size):
            i = int(sel[t])
            pk, cl = CC.certificates(r, i, wall, cost)
            cert_peak[t] = pk[0]
            cert_close[t] = cl[0]
            exit_peak[t] = int(pk[2])
            exit_close[t] = int(cl[2])
            walled[t] = CC._skel_query(r, i, wall)[3]

    # --- spread state ------------------------------------------------------
    # R119: this normaliser used to be the PRIOR-FREE `trade_date.year` pooled
    # median — the median over ALL sessions of the decision's OWN calendar year,
    # including the decision day and every day after it.  spread_ratio is a V1
    # FRAME_FIELDS entry and LIVE retrieval axis B08, rendered to the reader, so
    # that was a forward statistic on a reader-facing distance axis.  The basis
    # is now the STRICTLY PRIOR calendar year.  Where no prior year exists (the
    # first year of an asset's tape) the axis REFUSES — a named refusal with a
    # basis-year column, never a silent back-fill from the future.
    phase_med = CA.phase_median_spreads(MC.M0_ROOT)
    basis_year = int(trade_date.year) - 1
    med = np.array([phase_med.get((asset, basis_year,
                                   X.PHASE_NAMES[int(p)]), float("nan"))
                    for p in phase_dec])
    spread = r["spread_at_decision"][sel][order].astype(np.float64)
    with np.errstate(invalid="ignore", divide="ignore"):
        spread_ratio = np.where(np.isfinite(med) & (med > 0),
                                spread / med, np.nan)
    spread_basis_year = np.where(np.isfinite(med) & (med > 0),
                                 basis_year, -1).astype(np.int64)

    entry_mid = r["entry_mid"][sel][order].astype(np.float64)
    lvl = np.full(dec_s.size, np.nan)
    conf_fam = np.full(dec_s.size, -1, dtype=np.int64)
    conf_fam2 = np.full(dec_s.size, -1, dtype=np.int64)
    if with_levels:
        lpx_k, lbn_k, lfam_k = _kept_levels(asset, d8, s, trade_date,
                                            A.load_profile(asset, d8)[0])
        lvl = _nearest_kept_level_atr(lpx_k, lbn_k, dec_s, entry_mid, atr,
                                      mult)
        conf_fam = _confluence_at(lpx_k, lbn_k, lfam_k, dec_s, rf_px,
                                  float(spec["tick_px"]))
        conf_fam2 = _confluence_at(lpx_k, lbn_k, lfam_k, dec_s, rf_px,
                                   2.0 * float(spec["tick_px"]))

    # --- assemble (back in roster order) -----------------------------------
    def un(a):
        return np.asarray(a)[inv]

    phase_close = r["phase_close_sec"][sel].astype(np.int64)
    sess_close = r["sess_close_sec"][sel].astype(np.int64)
    fam_mask = r["fam_mask"][sel].astype(np.int64)
    extreme_age = np.where(side[order] < 0,
                           np.where(phase_hi_sec >= 0, dec_s - phase_hi_sec, -1),
                           np.where(phase_lo_sec >= 0, dec_s - phase_lo_sec, -1))
    mae = r["mae_before_argmax"][sel].astype(np.float64)
    # the $1,000 bar's remaining range requirement, side-aware
    reach = np.where(side[order] < 0, (entry_mid - phase_lo) * mult,
                     (phase_hi - entry_mid) * mult)
    ext_needed = np.where(np.isfinite(reach), np.maximum(1000.0 - reach, 0.0),
                          np.nan)

    f = {
        "asset": asset, "d8": d8, "n": int(sel.size),
        "i": sel.astype(np.int64),
        "cid": np.array([MC.make_cid(asset, d8, int(dec[t]), int(side[t]))
                         for t in range(sel.size)]),
        "dec_sec": dec, "side": side,
        "phase_dec": r["phase_dec"][sel].astype(np.int64),
        "phase_seg_start": un(ph_start), "phase_seg_end": un(ph_end),
        "klass": np.array([MC.class_of(int(m))[0] for m in fam_mask]),
        "fam_mask": fam_mask,
        "clock_sec": (open_utc + dec) % 86400,
        "coverage_phase": un(cov_p), "coverage_session": un(cov_s),
        "ladder_band": un(band), "regime_tercile": un(terc),
        "runway_phase_sec": phase_close - dec,
        "runway_sess_sec": sess_close - dec,
        "session_close_exit": phase_close == sess_close,
        "runway_frac": un((phase_close[order] - dec_s).astype(np.float64)
                          / np.maximum(ph_end - ph_start, 1)),
        "phase_hi": un(phase_hi), "phase_hi_sec": un(phase_hi_sec),
        "phase_lo": un(phase_lo), "phase_lo_sec": un(phase_lo_sec),
        "extreme_age_sec": un(extreme_age), "pivot_age_sec": un(pivot_age),
        "mid_now": un(m_now),
        "phase_age_sec": un(dec_s - ph_start),
        "ext_needed_usd": un(ext_needed),
        "f60_n": un(f60_n), "f60_vol": un(f60_v), "f60_sflow": un(f60_s),
        "f5m_n": un(f5m_n), "f5m_vol": un(f5m_v), "f5m_sflow": un(f5m_s),
        "f30m_n": un(f30m_n), "f30m_vol": un(f30m_v),
        "f30m_sflow": un(f30m_s),
        "fph_n": un(fph_n), "fph_vol": un(fph_v), "fph_sflow": un(fph_s),
        "fev_n": un(fev_n), "fev_vol": un(fev_v), "fev_sflow": un(fev_s),
        "release_ts": un(rel_ts), "release_sec": un(rel_sec),
        "release_age_sec": un(rel_age), "event_in_phase": un(in_phase),
        "range_hat_usd": un(rng_hat), "range_so_far_usd": un(range_sess),
        "day_type_frac": un(day_frac), "day_type": un(day_type),
        "surprise": un(surprise),
        "slope_1m_usd": un(slope_1), "slope_5m_usd": un(slope_5),
        "accel_usd": un(accel),
        "rv60_usd": un(rv60), "rv1800_usd": un(rv1800),
        "rv_ratio": un(rv_ratio),
        "spread_dec_usd": r["spread_at_decision"][sel].astype(np.float64),
        "spread_ratio": un(spread_ratio),
        "spread_ratio_basis_year": un(spread_basis_year),
        "atr_usd": np.full(sel.size, atr),
        "level_dist_atr": un(lvl),
        "cert_close_usd": cert_close, "cert_peak_usd": cert_peak,
        "walled": walled, "mae_before_argmax": mae,
        # R122: `NaN >= 1000.0` is False, so a candidate whose certificate could
        # not be computed used to be scored a MEASURED LOSER and counted in
        # every winner-rate DENOMINATOR.  The refusal is now a VALUE:
        # `cert_refused` names it and every consumer excludes those rows from
        # both halves of a rate rather than silently biasing it low.
        "cert_refused": ~(np.isfinite(cert_close) & np.isfinite(mae)),
        "winner": (np.isfinite(cert_close) & np.isfinite(mae)
                   & (cert_close >= 1000.0) & (mae <= 300.0) & (~walled)),
        "range_phase_usd": un(range_phase), "range_sess_usd": un(range_sess),
        "exp_move_q50_phase_usd": un(q50_p),
    }
    # Declared session-level refusal counters (D-006/D22): a refusal is a value
    # that is COUNTED and NAMED, so every census can stamp these into a receipt
    # instead of publishing a rate whose denominator hides them.
    f["cost_fallback"] = int(cost_fallback)
    f["n_atr_refused"] = int(n_atr_refused)
    f["n_cert_refused"] = int(f["cert_refused"].sum())
    f["n_spread_ratio_refused"] = int((spread_basis_year < 0).sum())
    # MINOR (3.2c): the LAST phase segment's end is `s.n` — the session's
    # realised length — so `runway_frac` and `sched_release_in_phase` inherit an
    # end-of-session fact on exactly those rows.  Declared per row rather than
    # left silent; consumers that need a strictly-causal denominator refuse on
    # this flag.
    f["phase_seg_end_is_session_end"] = un(ph_end >= int(s.n))

    # --- the V2 block (CC-M2-12 batch 3), documented in FRAME_FIELDS_V2 -----
    obs_close = int(s.meta.get("last_two_sided_sec", -1))
    f["tick_usd"] = np.full(sel.size, float(spec["tick_usd"]))
    f["refail_gap_sec"] = un(rf_gap)
    f["refail_dist_usd"] = un(rf_dist)
    f["refail_px"] = un(rf_px)
    f["refail_age_sec"] = un(rf_age)
    f["short_day"] = np.full(sel.size, bool(s.meta.get("short_day", False)))
    f["observed_close_sec"] = np.full(sel.size, obs_close, dtype=np.int64)
    obs_runway = (np.maximum(obs_close - dec, 0) if obs_close >= 0
                  else (phase_close - dec))
    f["runway_binding_sec"] = np.minimum(phase_close - dec, obs_runway)
    # R110 (related): when the m0 receipt carries no `last_two_sided_sec` this
    # used to fall back SILENTLY to the nominal runway, so reading B_observed
    # degenerated into reading A_nominal with no flag, no counter and no receipt
    # field.  The degeneracy is now a VALUE on every row.
    f["runway_binding_refused"] = np.full(sel.size, obs_close < 0, dtype=bool)
    f["n_conf_fam_at_refail"] = un(conf_fam)
    f["n_conf_fam_at_refail_2t"] = un(conf_fam2)
    # --- the V2b block (CC-M2-13.3 session-side probe) ----------------------
    f["exit_close_sec"] = exit_close
    f["exit_peak_sec"] = exit_peak
    f["sess_open_mid"] = np.full(sel.size, float(vm[0]) if vm.size else np.nan)
    # R120: `j_ph` is the first SANE second AT OR AFTER the phase start, so on a
    # candidate whose phase has no SANE tick BEFORE dec_sec this emitted a mid
    # from the FUTURE.  `have_ph` is the guard the code already computes three
    # lines of logic away (:745) and correctly applies to phase_hi/phase_lo; it
    # is applied here too.  A blind row REFUSES (NaN), never back-fills.
    f["phase_open_mid"] = un(np.where(have_ph & (j_ph < vm.size),
                                      vm[np.minimum(j_ph, max(vm.size - 1, 0))],
                                      np.nan))
    if not with_v3:
        return f

    # --- the V3 block (CC-M2-17.5 batch 4), documented in FRAME_FIELDS_V3 ---
    # (a) the S8 FUEL MAP, per phase SEGMENT, exact.
    fuel_a = np.zeros(dec_s.size, dtype=np.int64)
    fuel_b = np.zeros(dec_s.size, dtype=np.int64)
    fuel_t = np.zeros(dec_s.size, dtype=np.int64)
    t_px = tr["px_f"].astype(np.float64)
    for kk in sorted(set(k.tolist())):
        sel_k = np.nonzero(k == kk)[0]           # dec-ascending by construction
        a, b, t = _fuel_map(t_sec, t_px, t_sz, int(seg_start[kk]),
                            int(seg_end[kk]), dec_s[sel_k], entry_mid[sel_k])
        fuel_a[sel_k], fuel_b[sel_k], fuel_t[sel_k] = a, b, t
    f["fuel_above"] = un(fuel_a)
    f["fuel_below"] = un(fuel_b)
    f["fuel_total"] = un(fuel_t)

    # (b) the PREVIOUS phase segment's net move and range, per segment.
    n_seg = seg_start.size
    seg_ret = np.full(n_seg, np.nan)
    seg_rng = np.full(n_seg, np.nan)
    for kk in range(n_seg):
        a0 = int(np.searchsorted(vt, seg_start[kk], side="left"))
        a1 = int(np.searchsorted(vt, seg_end[kk], side="left"))
        if a1 > a0:
            w = vm[a0:a1]
            seg_ret[kk] = (float(w[-1]) - float(w[0])) * mult
            seg_rng[kk] = (float(w.max()) - float(w.min())) * mult
    prev_ret = np.where(k > 0, seg_ret[np.maximum(k - 1, 0)], np.nan)
    prev_rng = np.where(k > 0, seg_rng[np.maximum(k - 1, 0)], np.nan)
    f["prev_phase_ret_usd"] = un(prev_ret)
    f["prev_phase_range_usd"] = un(prev_rng)

    # (c) everything the session printed BEFORE this cell opened.
    j_pre = np.searchsorted(vt, ph_start, side="left")
    pre_rng = np.where(j_pre > 0,
                       (rmax[np.maximum(j_pre - 1, 0)]
                        - rmin[np.maximum(j_pre - 1, 0)]) * mult, np.nan)
    f["pre_cell_range_usd"] = un(pre_rng)

    # (d) a SCHEDULED release inside the running phase — calendar-only, so it
    #     is knowable AT THE CELL OPEN (D-057), unlike `event_in_phase`.
    cal_ts, _cal_names = release_calendar()
    seg_rel = np.zeros(n_seg, dtype=bool)
    for kk in range(n_seg):
        i0 = int(np.searchsorted(cal_ts, open_utc + int(seg_start[kk]),
                                 side="left"))
        i1 = int(np.searchsorted(cal_ts, open_utc + int(seg_end[kk]),
                                 side="left"))
        seg_rel[kk] = i1 > i0
    f["sched_release_in_phase"] = un(seg_rel[k])
    f["dow"] = np.full(sel.size, int(trade_date.weekday()), dtype=np.int64)

    # (e) the CELL key: the first candidate of each (asset, d8, phase_dec).
    cell_open = np.zeros(dec_s.size, dtype=bool)
    first_dec = np.zeros(dec_s.size, dtype=np.int64)
    for p in sorted(set(phase_dec.tolist())):
        m = np.nonzero(phase_dec == p)[0]        # dec-ascending
        cell_open[m[0]] = True
        first_dec[m] = int(dec_s[m[0]])
    f["cell_open"] = un(cell_open)
    f["cell_first_dec_sec"] = un(first_dec)
    return f


# --------------------------------------------------------------- sessions ---
def sessions(asset, years=None, allow_holdout=False):
    """Sorted [d8] of every roster session for `asset`, optionally year-filtered.

    D-058 GUARD (R57/R58/R105/R118).  This is the entry point five M2 censuses
    used to enumerate their populations, and the D-058 pre-exam holdout entered
    every one of them because the boundary lived as a private constant in one
    other file.  The boundary lives in `m2_common` now and this function
    REFUSES past it — a refusal, never a silent filter, so the caller has to
    say what it means.  Censuses call `sessions_fit`, which excludes the
    holdout and RETURNS the excluded count for the receipt.
    """
    r = roster(asset, with_certs=False)
    ds = sorted({int(x) for x in r["date8"].tolist()})
    if years is not None:
        ds = [d for d in ds if (d // 10000) in years]
    if not allow_holdout:
        bad = [d for d in ds if MC.in_holdout(d)]
        if bad:
            raise MC.HoldoutRefusal(
                "D-058: %s enumerates %d pre-exam holdout sessions "
                "(>= %d, first %d). Call sessions_fit() for the guarded "
                "population, or pass allow_holdout=True and say why."
                % (asset, len(bad), MC.HOLDOUT_FROM_D8, bad[0]))
    return ds


def sessions_fit(asset, years=None):
    """THE guarded census enumerator: (sessions, n_quarantined).

    Every M2 census population comes from here.  The holdout is excluded and
    the excluded count is returned so the receipt can DECLARE it."""
    ds = sessions(asset, years=years, allow_holdout=True)
    keep = [d for d in ds if not MC.in_holdout(d)]
    return keep, len(ds) - len(keep)


def main():
    MC.verify_spec(force=True)
    asset = sys.argv[1] if len(sys.argv) > 1 else "SI"
    d8 = int(sys.argv[2]) if len(sys.argv) > 2 else sessions(asset)[0]
    f = frame(asset, d8, with_levels=True)
    sys.stdout.write("%s %d: %d candidates\n" % (asset, d8, f["n"]))
    for k in sorted(FRAME_FIELDS):
        v = f.get(k)
        if v is None or np.isscalar(v):
            continue
        sys.stdout.write("  %-22s %s\n" % (k, str(v[:3])[:96]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
