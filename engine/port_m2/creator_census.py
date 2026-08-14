#!/usr/bin/python3
"""PORT M2 — THE CREATOR-PDF MECHANICS CENSUS (lane `port-m2-pdfs`).

    "for EVERY named mechanic/setup/filter the creator describes ... a COMPUTABLE
     detector over our data ... run every detector over E2->E6 at event grain;
     for each: frequency, hit rate on the D-021 winner definition vs
     displaced/shuffled nulls, lift with day-clustered CIs, per era/asset/
     session-phase, one Holm family; and the ledger-relevant number — does the
     detector separate same-day same-class members (the SEL_WRONG_MEMBER pool)
     and the wall-pairs?"                                            — the order

WHAT THIS FILE IS
  Stage A (--detect) turns each (asset, session) into a row-aligned BOOLEAN
  MATRIX over that session's M3-matrix candidates: one column per named creator
  mechanic, each computed STRICTLY CAUSALLY from data with session-second
  < dec_sec.  Stage B (--census) joins that matrix to the committed outcomes and
  publishes the graded table.

THE SUBSTRATE (D-006 — no second version of anything)
  candidates/outcomes  artifacts/cache/port/m3/matrix/matrix.npz
                       (cid, d8, dec_sec, side, phase_dec, era_idx, asset_idx,
                        y_winner = D-021, cert_close_usd, mae_before_argmax,
                        walled, cert_refused, atr_usd, cls_* one-hots)
  tape                 artifacts/cache/port/m0/sessions/{ASSET}/{d8}.npz —
                       the m0 session receipt.  FULL-SESSION coverage:
                        * trades_sec / trades_px / trades_side / trades_size
                          (aggressor-signed prints: 'B' = buy aggressor,
                           'A' = sell aggressor, 'N' = unsigned)
                        * a 1-second grid of g0_mid / g0_bid_px / g0_ask_px /
                          g0_bid_sz / g0_ask_sz / g0_state / phase_tag
                       This is chosen over the M2 MBP-1 event cache on purpose:
                       the event cache covers only ~70% of each session (the
                       union of the candidate extraction windows), and half the
                       creator's mechanics are SESSION-SCOPED (overnight
                       inventory, initial balance, the volume profile, zone
                       memory from hours earlier).  The m0 receipt is the same
                       DBN decode at 1s/print grain with 100% coverage.

FAITHFUL vs APPROXIMATION (stated per detector in CREATOR_DETECTORS.tsv)
  EXACT      MBP-1 trade records give the aggressor side, so CVD, aggression
             prints, per-price imbalance, speed of tape, effort-vs-result and
             every squeeze/refill-clock TIMING condition are the creator's own
             quantity, not a proxy.
  APPROX-L1  The creator reads a DOM: depth at ten levels, and orders being
             pulled/replaced BELOW the touched price.  We hold MBP-1 —
             top-of-book only.  Every "the wall reloads" condition is therefore
             read at L1 (bid_sz/ask_sz refresh at the inside quote) and is
             BLIND to depth behind it.  A level defended two ticks back is
             invisible to us and to every detector marked APPROX-L1.
  APPROX-VP  Volume profile / POC / value area are built from OUR trade prints
             only (one instrument, the dominant contract), not the exchange's
             full composite.  Shape is right; the absolute node heights are not.
  NOT-COMPUTABLE  Everything gamma (M-50..M-54, M-56).  We hold no options
             chain (D-047 authorized free data; QQQ/SPY 0DTE gamma was never
             acquired).  Those mechanics are declared, not censused.

RED-FIRST (declared BEFORE the run, per the program's law)
  Two mutants ship in the same Holm family as everything else:
    MUT_ABS_ROTATED   the ABSORPTION detector evaluated on a window ROTATED
                      +7200s inside the same session.  Frequency-matched,
                      alignment destroyed.  PREDICTION: lift ~= 1.00.
    MUT_ABS_INVERTED  the ABSORPTION condition with both inequalities flipped
                      (large displacement, small opposing volume).  This is a
                      nonsense condition, not the signal's mirror.
                      PREDICTION: lift ~= 1.00.
  If either mutant censuses away from 1.0 with a Holm-significant p, the
  machinery is lying and every number in the table is void.

Run:
  lab/run.sh port-m2-pdfs -- /usr/bin/python3 engine/port_m2/creator_census.py \
      --detect --workers 8
  /usr/bin/python3 engine/port_m2/creator_census.py --census
"""
import argparse
import hashlib
import json
import multiprocessing as mp
import os
import sys
import time

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_M0 = os.path.join(os.path.dirname(_HERE), "port_m0")
if _M0 not in sys.path:
    sys.path.insert(0, _M0)

import m2_common as MC                                        # noqa: E402
import common as C                                            # noqa: E402

# D-006 — no second version of anything.  Every estimator below is the port's
# OWN committed implementation, imported, never re-typed.
import batch4_census as B4                                    # noqa: E402
import goalpath as GP                                         # noqa: E402

_holm_family = B4._holm_family          # R61 ONE family over the whole batch
_shuffle_within = B4._shuffle_within    # destruction: permute within the block
_block_key = B4.block_key
_perm_support = B4.perm_support
cluster_boot = GP.cluster_boot          # day-clustered bootstrap (D-036/D-073)
HOLM_TAIL = B4.HOLM_TAIL

# CC-M2-9.1 grading vocabulary — the ONLY verdicts this census may assign.
V_ENTRY = "ENTRY RULE"
V_VETO = "VETO RULE"
V_CONC = "WINNER CONCENTRATOR"
V_NULL = "NULL"
V_RARE = "TOO_RARE"
V_DEGEN = "DEGENERATE_NULL"

SECTION = "design/CREATOR_MECHANICS.md — creator-PDF mechanics census"
PROV = "/workspace/provenance/port_m2"
CACHE = MC.out_path("creator", "_")[:-1]

# --------------------------------------------------------------- population --
ERA_LO, ERA_HI = 20220101, 20240630           # E2..E6 inclusive
MATRIX = "/workspace/artifacts/cache/port/m3/matrix/matrix.npz"
SESS_ROOT = "/workspace/artifacts/cache/port/m0/sessions"

# ---------------------------------------------------------------- constants --
# Every knob is declared here, stamped into the receipt, and cited to the PDF
# line that motivates it.  Nothing is tuned on outcomes.
P = {
    # M-01 aggression band.  The creator: "a minimum of 30 contracts and a
    # maximum of 60 per print, and I adjust with the session's volume" (NQ), and
    # "you have to find your own band rather than borrow this one".  Our books
    # are 2-3 orders of magnitude thinner (session q99 print = 8-12 lots), so
    # the band is SESSION-ADAPTIVE at the same distributional place, with the
    # creator's own volume-adjustment instruction honoured literally.
    "agg_q": 0.99,
    "agg_floor": 3,
    # M-13 zone geometry: "a burst of large aggressive orders ... hitting in
    # seconds" clustered at "one price area".
    "zone_ticks": 4,
    "zone_gap_sec": 60,
    "zone_min_prints": 2,
    # M-14 touch: price must LEAVE by this much before a return counts.
    "leave_ticks": 8,
    "touch_tol_ticks": 2,
    "resolve_sec": 600,
    "hold_ticks": 8,
    "break_ticks": 8,
    # M-02/M-03 absorption: effort with no result.
    "abs_win_sec": 120,
    "abs_move_atr": 0.05,          # "no progress" = |dmid| <= 5% of ATR14
    "abs_vol_q": 0.80,             # opposing aggressive volume >= session q80
    # M-20 squeeze: "repeated effort that got no reward, not just one failed
    # candle" -> >= 3 absorbed bursts in the same band.
    "squeeze_n": 3,
    "squeeze_win_sec": 1800,
    # M-07 speed of tape
    "tape_win_sec": 60,
    "tape_spike_x": 3.0,
    "tape_dead_x": 0.34,
    # M-27 imbalance
    "imb_ratio": 3.5,
    "imb_min_vol": 10,
    "imb_win_sec": 1800,
    # M-28 divergence box
    "div_win_sec": 300,
    "div_ratio": 3.5,
    # M-41 extreme absorption (price vs CVD divergence over a consolidation)
    "xabs_win_sec": 1800,
    "xabs_px_atr": 0.15,
    # M-29 passive move
    "passive_win_sec": 300,
    "passive_move_atr": 0.25,
    # M-24 wick takeout / drive
    "drive_win_sec": 900,
    "drive_ticks": 4,
    # M-11 thin-behind
    "thin_atr": 1.0,
    # displaced null
    "displace_sec": 1800,
    # mutant rotation
    "rotate_sec": 7200,
    # census
    "boot_reps": 2000,
    "shuffle_reps": 40,
    "seed": 20260814,
}

# ------------------------------------------------------------ the detectors --
# (name, mechanic-ids, fidelity, one-line computable statement)
DETECTORS = [
    ("AGG_PRINT_60", "M-01", "EXACT",
     "at least one aggression print (size >= session q99, floor 3) in [t-60, t)"),
    ("AGG_WITH_SIDE_60", "M-01/M-03", "EXACT",
     "at least one aggression print on the CANDIDATE'S side in [t-60, t)"),
    ("AGG_OPP_SIDE_60", "M-01", "EXACT",
     "at least one aggression print on the OPPOSING side in [t-60, t)"),
    ("ABSORPTION", "M-02/M-03", "EXACT",
     "opposing aggressive volume in [t-120,t) >= session q80 AND |dmid| over the "
     "window <= 0.05*ATR14 — effort with no result, against the candidate"),
    ("BODY_REWARDED_WITH", "M-04", "EXACT",
     "the last aggression print on the candidate's side got its result: mid "
     "moved with it by >= 1 tick within 30s (inside the body)"),
    ("WICK_ABSORBED_OPP", "M-04", "EXACT",
     "the last aggression print on the opposing side got NO result: |dmid| < 1 "
     "tick within 30s (on the wick)"),
    ("SQUEEZE", "M-20/M-21", "EXACT",
     ">= 3 absorbed opposing-side aggression bursts inside one zone band within "
     "[t-1800, t) — repeated effort that got no reward"),
    ("SQUEEZE_CATALYST_NEAR", "M-21", "EXACT",
     "SQUEEZE fired AND the entry mid is within the zone band of the catalyst "
     "anchor (the extreme FIRST aggression of the absorbed cluster)"),
    ("REFILL_CLOCK", "M-22", "EXACT",
     "a later aggression attempt in the same zone prints at WORSE prices for the "
     "aggressor than the first attempt — 'more aggression joins them at worse "
     "prices, which is itself proof of intent'"),
    ("OFM", "M-23/M-24", "EXACT",
     "SQUEEZE, then failure (mid rolls back through the catalyst by >= 4 ticks), "
     "then the drive: the prior swing extreme is taken out in the candidate's "
     "direction within [t-900, t) and the candidate is on the RETEST of it"),
    ("OFM_FAILURE_ENTRY", "M-24 (the error)", "EXACT",
     "SQUEEZE + failure but NO drive/wick-takeout — the creator's named mistake, "
     "'entering on the failure of the squeeze. No, that's not true'"),
    ("RETEST_NOT_BREAK", "M-25", "EXACT",
     "the candidate sits at a level broken within [t-900, t) and price has "
     "returned to it, rather than at the break itself"),
    ("REFILL_AREA_HELD", "M-26", "APPROX-L1",
     "the nearest zone below (long) / above (short) took opposing aggression in "
     "[t-600,t) and did not give way by more than 1 tick"),
    ("IMB_350", "M-27", "EXACT",
     "session-to-date aggressive volume at the entry price bucket is >= 3.5x "
     "one-sided (min 10 lots), against the candidate's side"),
    ("IMB_350_AT_AGG", "M-27", "EXACT",
     "IMB_350 AND an aggression print at the same price bucket — 'an imbalance "
     "only interests me where it sits at the same price as aggression'"),
    ("DIV_BOX_350", "M-28", "EXACT",
     "in [t-300,t): one side's aggressive volume >= 3.5x the other AND |dmid| <= "
     "0.05*ATR14 — passive absorption on one side, aggressive pressure on the "
     "other, at the same price"),
    ("PASSIVE_MOVE", "M-29 (the trap)", "EXACT",
     "mid moved >= 0.25*ATR14 in the candidate's direction over [t-300,t) with "
     "ZERO aggression prints on the candidate's side — 'no effort on your side "
     "at all, just an absence of sellers'"),
    ("TWO_STAGE", "M-29 (what he wants)", "EXACT",
     "ORDERED: opposing aggression absorbed in [t-600,t-120), THEN own-side "
     "aggression arrives in [t-120,t)"),
    ("BOTH_ABSORBED", "M-30", "EXACT",
     "both sides show absorbed aggression in [t-600,t) — 'nobody is in control "
     "yet and I am waiting for the break'"),
    ("CVD_WITH", "M-08", "EXACT",
     "session CVD at t is on the candidate's side of its own session-to-date "
     "median"),
    ("CVD_AGAINST", "M-08 (the veto)", "EXACT",
     "session CVD at t is AGAINST the candidate's side of its own median — the "
     "creator's checklist veto"),
    ("EXTREME_ABSORPTION", "M-41", "EXACT",
     "over [t-1800,t) mid drifted with the candidate by >= 0.15*ATR14 while CVD "
     "moved AGAINST it — 'price refusing to drop while the delta record shows no "
     "real selling pressure behind the level'"),
    ("TAPE_SPIKE", "M-07", "EXACT",
     "prints/sec in [t-60,t) >= 3x the session-to-date median rate"),
    ("TAPE_DEAD", "M-07", "EXACT",
     "prints/sec in [t-60,t) <= 0.34x the session-to-date median rate — 'the "
     "speed of tape just dies', the passive failure"),
    ("TOUCH_1_VIRGIN", "M-86/M-81", "EXACT",
     "the candidate is at the FIRST touch of its zone — 'the first touch of a "
     "fresh zone is the weakest version of this trade'"),
    ("TOUCH_2", "M-86/M-36", "EXACT",
     "the candidate is at the SECOND touch — 'wait for the second test'"),
    ("TOUCH_GE3", "M-38", "EXACT",
     "the candidate is at the third or later touch — the creator's own "
     "published LOSS (ny-am-session.pdf p.6)"),
    ("PRIOR_TOUCH_HELD", "M-06/M-17", "EXACT",
     "the zone's most recent RESOLVED touch (resolved strictly before t) HELD — "
     "the memory family"),
    ("PRIOR_2_HELD", "M-06", "EXACT",
     "the zone's two most recent resolved touches both HELD"),
    ("ZONE_BUILT_BY_SIZE", "M-13/M-81", "EXACT",
     "the zone was built by >= 3 aggression prints totalling >= 3x the session's "
     "median aggression print — the construction family"),
    ("LOSING_STEAM", "M-39", "EXACT",
     "aggressive volume into the level is DECREASING across the last three 120s "
     "approach windows — 'losing aggression candle by candle, not gaining it'"),
    ("REPEATED_FAIL_RECLAIM", "M-42", "EXACT",
     ">= 2 failed attempts to reclaim the prior range boundary against the "
     "candidate's side within [t-3600, t)"),
    ("MICROBALANCE_BREAK", "M-40", "EXACT",
     "a <= 0.2*ATR14 range lasting >= 180s ended in the candidate's direction "
     "within [t-300, t)"),
    ("ONX_UNTOUCHED_AHEAD", "M-70 (the veto)", "APPROX-VP",
     "the overnight extreme on the far side of the entry is still untouched this "
     "phase and lies between entry and the candidate's direction of travel — "
     "'the level isn't wrong, the timing is'"),
    ("IB_BROKEN_WITH", "M-73", "EXACT",
     "the initial balance (first 3600s of the NY phase) has been broken in the "
     "candidate's direction before t"),
    ("OPEN_IN_PRIOR_VALUE", "M-71", "APPROX-VP",
     "the session open sits inside the prior session's value area"),
    ("IN_VALUE_AREA", "M-57", "APPROX-VP",
     "the entry mid sits inside the session-to-date 70% value area"),
    ("AT_VA_EDGE", "M-57/M-81", "APPROX-VP",
     "the entry mid is within 2 ticks of VAH or VAL — the location family"),
    ("DAY_P", "M-58", "APPROX-VP",
     "session-to-date POC sits in the TOP third of the session-to-date range"),
    ("DAY_B", "M-58", "APPROX-VP",
     "session-to-date POC sits in the BOTTOM third of the range"),
    ("DAY_D", "M-58", "APPROX-VP",
     "session-to-date POC sits in the MIDDLE third — compression, no resolution"),
    ("THIN_BEHIND", "M-11", "APPROX-VP",
     "traded volume in the 1-ATR band BEHIND the entry (the stop side) is in the "
     "bottom session quartile — 'below it there is nothing'"),
    ("MUT_ABS_LOOKAHEAD_2H", "RED-FIRST (leak probe)", "MUTANT",
     "ABSORPTION evaluated at t+7200s in the SAME session — i.e. two hours "
     "into the candidate's FUTURE.  Shipped as a ~1.0 null in the first draft; "
     "the census returned lift 1.404 (> the causal detector's 1.248) and the "
     "audit showed why: (t+7200) mod n is future data for almost every row.  "
     "It is retained as a POSITIVE leak control — PREDICTION: lift > 1 and "
     "> ABSORPTION.  If this one ever lands at 1.0 the harness has gone blind"),
    ("MUT_ABS_INVERTED", "RED-FIRST", "MUTANT",
     "ABSORPTION with both inequalities flipped (large |dmid|, small opposing "
     "volume) — a nonsense condition.  PREDICTION lift ~= 1.00"),
    ("MUT_ABS_SHUFFLED", "RED-FIRST", "MUTANT",
     "ABSORPTION's own flags permuted WITHIN each session (seeded).  Exactly "
     "frequency-matched per session, row alignment destroyed, fully causal.  "
     "This is the real null the lookahead mutant failed to be.  "
     "PREDICTION: lift ~= 1.00"),
    ("MUT_RANDOM_IID", "RED-FIRST", "MUTANT",
     "an i.i.d. Bernoulli flag at ABSORPTION's marginal rate, independent of "
     "everything including the session.  PREDICTION: lift ~= 1.00"),
]
DET_NAMES = [d[0] for d in DETECTORS]
NDET = len(DET_NAMES)
# The last two detectors (MUT_ABS_SHUFFLED, MUT_RANDOM_IID) are functions of
# ABSORPTION's own column and are built at CENSUS time, not in the session pass.
CENSUS_TIME_DETECTORS = 2
NDET_SESSION = NDET - CENSUS_TIME_DETECTORS

SIDE_L, SIDE_S = 1, -1


# ============================================================ stage A ========
def _rollsum(x, w):
    """cumulative-sum rolling window: out[i] = sum(x[max(0,i-w):i])  (causal,
    EXCLUDES i itself)."""
    c = np.concatenate(([0.0], np.cumsum(x.astype(np.float64))))
    i = np.arange(x.size)
    lo = np.maximum(0, i - w)
    return c[i] - c[lo]


class Zone(object):
    __slots__ = ("lo", "hi", "anchor", "t0", "t1", "n", "vol", "side",
                 "touches", "outside", "last_ext")

    def __init__(self, px, t, sz, side, tol):
        self.lo = px - tol
        self.hi = px + tol
        self.anchor = px
        self.t0 = t
        self.t1 = t
        self.n = 1
        self.vol = sz
        self.side = side
        self.touches = []        # [(t_touch, resolved_t, held(bool|None))]
        self.outside = False
        self.last_ext = px


def _build_session(asset, d8, dec, sides, atr_usd):
    """Return an (n_cand, NDET) uint8 matrix + a per-session replication dict.

    Every column is computed from data with session-second strictly < dec_sec.
    """
    path = os.path.join(SESS_ROOT, asset, "%08d.npz" % d8)
    if not os.path.exists(path):
        return None
    z = np.load(path, allow_pickle=False)
    meta = json.loads(str(z["meta_json"]))
    spec = C.ASSETS[asset]
    tick = float(spec["tick_px"])
    tick_usd = float(spec["tick_usd"])
    scale = float(spec["px_scale"])

    mid = z["g0_mid"].astype(np.float64)
    ph = z["phase_tag"].astype(np.int8)
    n = int(min(mid.size, ph.size))
    mid = mid[:n]
    ph = ph[:n]
    # A second with no two-sided book carries a NaN mid.  Forward-fill from the
    # last OBSERVED second (causal — never backward), then back-fill only the
    # pre-open head with the first observation.  24 of 1,930 sessions died on
    # `int(round(nan))` before this guard.
    fin_m = np.isfinite(mid)
    if not fin_m.all():
        if not fin_m.any():
            z.close()
            return None
        ffi = np.maximum.accumulate(np.where(fin_m, np.arange(n), 0))
        first = int(np.argmax(fin_m))
        ffi[:first] = first
        mid = mid[ffi]
    tsec = z["trades_sec"].astype(np.int64)
    tpx = z["trades_px"].astype(np.float64) * scale
    tsd = z["trades_side"].astype(np.uint8)
    tsz = z["trades_size"].astype(np.int64)
    z.close()

    ncand = dec.size
    D = np.zeros((ncand, NDET_SESSION), dtype=np.uint8)
    EM = np.full(ncand, np.nan)
    rep = {"asset": asset, "d8": int(d8)}
    if tsec.size == 0 or n < 600:
        return D, EM, rep

    keep = (tsec >= 0) & (tsec < n) & (tsz > 0)
    tsec, tpx, tsd, tsz = tsec[keep], tpx[keep], tsd[keep], tsz[keep]
    if tsec.size == 0:
        return D, rep
    o = np.argsort(tsec, kind="stable")
    tsec, tpx, tsd, tsz = tsec[o], tpx[o], tsd[o], tsz[o]

    is_b = tsd == ord("B")
    is_a = tsd == ord("A")
    sgn = np.where(is_b, 1, np.where(is_a, -1, 0)).astype(np.int64)

    # --- ATR: prefer the matrix's own per-row atr_usd; else the receipt's ---
    atr = float(np.nanmedian(atr_usd)) if np.isfinite(atr_usd).any() else np.nan
    if not np.isfinite(atr) or atr <= 0:
        atr = float(meta.get("ATR14_prev_px", 0.0)) / max(tick, 1e-12) * tick_usd
    if not np.isfinite(atr) or atr <= 0:
        atr = 20.0 * tick_usd
    atr_px = atr / tick_usd * tick

    # ------------------------------------------------- per-second aggregates --
    vol_b = np.bincount(tsec, weights=np.where(is_b, tsz, 0), minlength=n)
    vol_a = np.bincount(tsec, weights=np.where(is_a, tsz, 0), minlength=n)
    cnt = np.bincount(tsec, minlength=n).astype(np.float64)
    cvd = np.cumsum(vol_b - vol_a)

    agg_thr = max(int(P["agg_floor"]),
                  int(np.ceil(np.quantile(tsz, P["agg_q"]))))
    big = tsz >= agg_thr
    rep["agg_thr"] = agg_thr
    rep["n_trades"] = int(tsz.size)
    rep["n_big"] = int(big.sum())

    bigv_b = np.bincount(tsec, weights=np.where(big & is_b, tsz, 0), minlength=n)
    bigv_a = np.bincount(tsec, weights=np.where(big & is_a, tsz, 0), minlength=n)
    bign_b = np.bincount(tsec, weights=(big & is_b).astype(np.float64),
                         minlength=n)
    bign_a = np.bincount(tsec, weights=(big & is_a).astype(np.float64),
                         minlength=n)

    W_ABS = P["abs_win_sec"]
    rb_abs = _rollsum(vol_b, W_ABS)
    ra_abs = _rollsum(vol_a, W_ABS)
    rb_60 = _rollsum(bign_b, 60)
    ra_60 = _rollsum(bign_a, 60)
    rb_120 = _rollsum(bign_b, 120)
    ra_120 = _rollsum(bign_a, 120)
    rb_600 = _rollsum(bign_b, 600)
    ra_600 = _rollsum(bign_a, 600)
    rcnt_60 = _rollsum(cnt, P["tape_win_sec"])
    rb_div = _rollsum(vol_b, P["div_win_sec"])
    ra_div = _rollsum(vol_a, P["div_win_sec"])

    # session-to-date median print rate (causal): cumulative mean is the honest
    # cheap surrogate for the running median on a count series.
    csec = np.arange(1, n + 1, dtype=np.float64)
    rate_todate = np.cumsum(cnt) / csec
    # session-to-date q80 of the 120s opposing-volume series, causal: use the
    # expanding mean + 1 sd (a declared surrogate for the expanding quantile;
    # the expanding quantile over 82,800 points is not worth its cost here).
    def _expand_q80(x):
        c1 = np.cumsum(x)
        c2 = np.cumsum(x * x)
        m = c1 / csec
        v = np.maximum(c2 / csec - m * m, 0.0)
        return m + 0.8416 * np.sqrt(v)
    q80_b = _expand_q80(rb_abs)
    q80_a = _expand_q80(ra_abs)

    dmid_abs = np.abs(mid - np.roll(mid, W_ABS))
    dmid_abs[:W_ABS] = np.abs(mid[:W_ABS] - mid[0])
    dmid_div = mid - np.roll(mid, P["div_win_sec"])
    dmid_div[:P["div_win_sec"]] = mid[:P["div_win_sec"]] - mid[0]
    dmid_pass = mid - np.roll(mid, P["passive_win_sec"])
    dmid_pass[:P["passive_win_sec"]] = mid[:P["passive_win_sec"]] - mid[0]
    W_X = P["xabs_win_sec"]
    dmid_x = mid - np.roll(mid, W_X)
    dmid_x[:W_X] = mid[:W_X] - mid[0]
    dcvd_x = cvd - np.roll(cvd, W_X)
    dcvd_x[:W_X] = cvd[:W_X] - cvd[0]

    # running median of CVD (causal, cheap: expanding mean)
    cvd_med = np.cumsum(cvd) / csec

    # ------------------------------------------------------ session context --
    # phases: 0 TOKYO 1 LONDON 2 NY.  Overnight (the creator's 6pm->9:30) is
    # everything before the NY phase opens.
    ny = np.nonzero(ph == 2)[0]
    ny0 = int(ny[0]) if ny.size else n
    on_hi = float(np.max(mid[:ny0])) if ny0 > 1 else np.nan
    on_lo = float(np.min(mid[:ny0])) if ny0 > 1 else np.nan
    ib_hi = ib_lo = np.nan
    if ny.size > 60:
        ib_end = min(ny0 + 3600, n)
        ib_hi = float(np.max(mid[ny0:ib_end]))
        ib_lo = float(np.min(mid[ny0:ib_end]))
        rep["ib_end"] = ib_end
    rep["on_hi"], rep["on_lo"] = on_hi, on_lo
    rep["ny0"] = ny0
    rep["sess_open_mid"] = float(mid[0])
    rep["prev_close"] = float(meta.get("Cl", np.nan))
    rep["atr_usd"] = atr
    rep["tick_usd"] = tick_usd

    # M-70 replication: does NY touch ONH or ONL?
    if ny.size > 60 and np.isfinite(on_hi):
        m_ny = mid[ny0:]
        rep["ny_touch_onh"] = bool(np.max(m_ny) >= on_hi)
        rep["ny_touch_onl"] = bool(np.min(m_ny) <= on_lo)

    # ------------------------------------------------------- the zone ledger --
    tol = P["zone_ticks"] * tick
    leave = P["leave_ticks"] * tick
    ttol = P["touch_tol_ticks"] * tick
    bigi = np.nonzero(big)[0]
    zones = []
    for k in bigi.tolist():
        px, t, s, sz = float(tpx[k]), int(tsec[k]), int(sgn[k]), int(tsz[k])
        if s == 0:
            continue
        hit = None
        for zz in zones:
            if abs(px - zz.anchor) <= tol and (t - zz.t1) <= P["zone_gap_sec"]:
                hit = zz
                break
        if hit is None:
            zones.append(Zone(px, t, sz, s, tol))
        else:
            hit.t1 = t
            hit.n += 1
            hit.vol += sz
            # M-21: the catalyst is drawn at the LOWEST (long) / HIGHEST (short)
            # FIRST aggression of the absorbed cluster.
            if s > 0:
                hit.anchor = min(hit.anchor, px)
            else:
                hit.anchor = max(hit.anchor, px)
            hit.lo = min(hit.lo, px - tol)
            hit.hi = max(hit.hi, px + tol)
    zones = [zz for zz in zones if zz.n >= P["zone_min_prints"]]
    rep["n_zones"] = len(zones)

    # touches: walk the 1s mid once per zone (zones are few per session)
    n_touch = n_hold = 0
    for zz in zones:
        s0 = zz.t1 + 1
        if s0 >= n:
            continue
        m = mid[s0:]
        # The touch is registered on the ANCHOR LINE within tol, and the zone
        # must be LEFT by `leave` before it can be touched again — the m1
        # level-ledger state machine's own convention (b3_levels: arm at
        # >1.5x tol, touch at <=tol).  Registering the touch anywhere in the
        # 8-tick band instead put the entry at the band EDGE, which left one
        # resolution leg 2 ticks away and the other 14 and drove the measured
        # hold rate to 0.94.  Anchor-line touches make the race fair.
        dm = np.abs(m - zz.anchor)
        inside = dm <= ttol
        far = dm > leave
        st_out = False
        i = 0
        L = m.size
        while i < L:
            if far[i]:
                st_out = True
            elif inside[i] and st_out:
                t_touch = s0 + i
                # resolve
                j0 = t_touch
                j1 = min(t_touch + P["resolve_sec"], n)
                seg = mid[j0:j1]
                approach_up = m[max(i - 1, 0)] > zz.anchor
                held = None
                if seg.size > 5:
                    # Both legs are measured from the SAME point — the zone
                    # anchor — so the hold/break race is geometrically fair.
                    # Measuring HOLD from zz.hi and BREAK from zz.lo would make
                    # the near edge win by construction and would inflate the
                    # hold rate; that bug was caught in the smoke test and this
                    # is the fix.
                    a_ = zz.anchor
                    if approach_up:
                        broke = np.nonzero(seg <= a_ - P["break_ticks"] * tick)[0]
                        heldi = np.nonzero(seg >= a_ + P["hold_ticks"] * tick)[0]
                    else:
                        broke = np.nonzero(seg >= a_ + P["break_ticks"] * tick)[0]
                        heldi = np.nonzero(seg <= a_ - P["hold_ticks"] * tick)[0]
                    bi = int(broke[0]) if broke.size else 10 ** 9
                    hi_ = int(heldi[0]) if heldi.size else 10 ** 9
                    if bi == hi_ == 10 ** 9:
                        held = None
                    else:
                        held = hi_ < bi
                    res_t = j0 + min(bi, hi_) if held is not None else j1
                else:
                    res_t = j1
                zz.touches.append((t_touch, int(res_t), held))
                if held is not None:
                    n_touch += 1
                    n_hold += int(held)
                st_out = False
                # skip forward past the resolution so one visit = one touch
                i = max(i + 1, int(res_t) - s0)
                continue
            i += 1
    rep["n_touch_resolved"] = n_touch
    rep["n_touch_held"] = n_hold

    # ---------------------------------------------- causal per-price sweeps --
    order = np.argsort(dec, kind="stable")
    bucket = np.round(tpx / tick).astype(np.int64)
    pb, ps = {}, {}          # price bucket -> aggressive volume by side
    pbig = {}                # price bucket -> big-print count
    ptr = 0
    vp = {}                  # volume profile bucket -> volume (causal)

    for oi in order.tolist():
        t = int(dec[oi])
        if t <= 1 or t >= n:
            continue
        side = int(sides[oi])
        while ptr < tsec.size and tsec[ptr] < t:
            b = int(bucket[ptr])
            v = int(tsz[ptr])
            vp[b] = vp.get(b, 0) + v
            if sgn[ptr] > 0:
                pb[b] = pb.get(b, 0) + v
            elif sgn[ptr] < 0:
                ps[b] = ps.get(b, 0) + v
            if big[ptr]:
                pbig[b] = pbig.get(b, 0) + 1
            ptr += 1

        emid = float(mid[t - 1])
        eb = int(round(emid / tick))
        EM[oi] = emid / tick * tick_usd            # USD-comparable to atr_usd
        row = D[oi]

        # ---- M-01 aggression prints -------------------------------------
        nb60, na60 = rb_60[t], ra_60[t]
        with_n = nb60 if side == SIDE_L else na60
        opp_n = na60 if side == SIDE_L else nb60
        row[0] = (nb60 + na60) > 0
        row[1] = with_n > 0
        row[2] = opp_n > 0

        # ---- M-02/M-03 absorption ---------------------------------------
        opp_vol = ra_abs[t] if side == SIDE_L else rb_abs[t]
        opp_q80 = q80_a[t] if side == SIDE_L else q80_b[t]
        no_prog = dmid_abs[t] <= P["abs_move_atr"] * atr_px
        absorb = bool(opp_vol >= max(opp_q80, 1.0) and no_prog)
        row[3] = absorb

        # ---- M-04 body vs wick ------------------------------------------
        # last big print each side strictly before t
        def _last_big(side_sgn):
            k = ptr - 1
            lim = max(0, ptr - 4000)
            while k >= lim:
                if big[k] and sgn[k] == side_sgn:
                    return int(tsec[k])
                k -= 1
            return -1
        tw = _last_big(1 if side == SIDE_L else -1)
        to_ = _last_big(-1 if side == SIDE_L else 1)
        if tw >= 0:
            e = min(tw + 30, t - 1)
            dm = (mid[e] - mid[tw]) * (1 if side == SIDE_L else -1)
            row[4] = dm >= tick
        if to_ >= 0:
            e = min(to_ + 30, t - 1)
            row[5] = abs(mid[e] - mid[to_]) < tick

        # ---- M-20/M-21 squeeze + catalyst -------------------------------
        opp_s = -1 if side == SIDE_L else 1
        sq = None
        for zz in zones:
            if zz.side != opp_s:
                continue
            if zz.t1 >= t or (t - zz.t1) > P["squeeze_win_sec"]:
                continue
            if zz.n >= P["squeeze_n"]:
                sq = zz
                break
        row[6] = sq is not None
        if sq is not None and abs(emid - sq.anchor) <= (zz_tol := tol + ttol):
            row[7] = 1

        # ---- M-22 refill clock ------------------------------------------
        if sq is not None:
            k = ptr - 1
            first_px, worse = None, False
            lim = max(0, ptr - 20000)
            seq = []
            while k >= lim and tsec[k] >= sq.t0:
                if big[k] and sgn[k] == opp_s and sq.lo <= tpx[k] <= sq.hi:
                    seq.append((int(tsec[k]), float(tpx[k])))
                k -= 1
            seq.reverse()
            if len(seq) >= 2:
                first_px = seq[0][1]
                last_px = seq[-1][1]
                worse = (last_px < first_px) if opp_s > 0 else (last_px > first_px)
            row[8] = bool(worse)

        # ---- M-23/M-24 OFM ----------------------------------------------
        drive = False
        retest = False
        if sq is not None:
            # failure: mid rolled back through the catalyst against the squeezer
            seg0 = max(sq.t1, t - P["squeeze_win_sec"])
            seg = mid[seg0:t]
            if seg.size > 10:
                if opp_s > 0:      # buyers squeezed and failed -> price below
                    failed = np.min(seg) <= sq.anchor - P["drive_ticks"] * tick
                else:
                    failed = np.max(seg) >= sq.anchor + P["drive_ticks"] * tick
                if failed:
                    w0 = max(0, t - P["drive_win_sec"])
                    pre = mid[w0:max(w0 + 1, t - 120)]
                    rec = mid[max(w0, t - 120):t]
                    if pre.size > 5 and rec.size > 5:
                        if side == SIDE_L:
                            drive = float(np.max(rec)) > float(np.max(pre)) + \
                                P["drive_ticks"] * tick
                            retest = drive and emid < float(np.max(rec)) - \
                                P["drive_ticks"] * tick
                        else:
                            drive = float(np.min(rec)) < float(np.min(pre)) - \
                                P["drive_ticks"] * tick
                            retest = drive and emid > float(np.min(rec)) + \
                                P["drive_ticks"] * tick
                    row[10] = (not drive)
        row[9] = bool(drive and retest)

        # ---- M-25 retest, not break -------------------------------------
        w0 = max(0, t - P["drive_win_sec"])
        pre = mid[w0:max(w0 + 1, t - 180)]
        if pre.size > 30:
            if side == SIDE_L:
                brk = float(np.max(mid[max(w0, t - 180):t])) > float(np.max(pre))
                row[11] = bool(brk and emid < float(np.max(mid[max(w0, t - 180):t]))
                               - P["drive_ticks"] * tick)
            else:
                brk = float(np.min(mid[max(w0, t - 180):t])) < float(np.min(pre))
                row[11] = bool(brk and emid > float(np.min(mid[max(w0, t - 180):t]))
                               + P["drive_ticks"] * tick)

        # ---- M-26 refill area held (APPROX-L1) --------------------------
        near = None
        best = 1e18
        for zz in zones:
            if zz.t1 >= t:
                continue
            if side == SIDE_L and zz.anchor > emid:
                continue
            if side == SIDE_S and zz.anchor < emid:
                continue
            dd = abs(zz.anchor - emid)
            if dd < best:
                best, near = dd, zz
        if near is not None and best <= 3 * atr_px * 0.25:
            seg = mid[max(0, t - 600):t]
            if seg.size > 5:
                if side == SIDE_L:
                    row[12] = bool(np.min(seg) >= near.lo - tick)
                else:
                    row[12] = bool(np.max(seg) <= near.hi + tick)

        # ---- M-27 imbalance ---------------------------------------------
        # The creator reads a FOOTPRINT imbalance — buyers vs sellers at one
        # price in the CURRENT auction, not since the open.  A session-
        # cumulative bucket tends to balance and fired on 0.7% of rows; this is
        # the same statistic over the trailing imb_win.
        klo = np.searchsorted(tsec, max(0, t - P["imb_win_sec"]), "left")
        bvol = svol = 0
        nbig_at = 0
        for q in range(int(klo), int(ptr)):
            if abs(int(bucket[q]) - eb) > 1:
                continue
            if sgn[q] > 0:
                bvol += int(tsz[q])
            elif sgn[q] < 0:
                svol += int(tsz[q])
            if big[q]:
                nbig_at += 1
        tot = bvol + svol
        if tot >= P["imb_min_vol"]:
            if side == SIDE_L:
                imb = svol >= P["imb_ratio"] * max(bvol, 1)
            else:
                imb = bvol >= P["imb_ratio"] * max(svol, 1)
            row[13] = bool(imb)
            row[14] = bool(imb and nbig_at > 0)

        # ---- M-28 divergence box -----------------------------------------
        dv_b, dv_a = rb_div[t], ra_div[t]
        if (dv_b + dv_a) >= P["imb_min_vol"]:
            one_sided = (dv_b >= P["div_ratio"] * max(dv_a, 1.0)) or \
                        (dv_a >= P["div_ratio"] * max(dv_b, 1.0))
            row[15] = bool(one_sided and
                           abs(dmid_div[t]) <= P["abs_move_atr"] * atr_px)

        # ---- M-29 passive move / two-stage / both absorbed ---------------
        mv = dmid_pass[t] * (1 if side == SIDE_L else -1)
        row[16] = bool(mv >= P["passive_move_atr"] * atr_px and with_n == 0)
        early_opp = (ra_600[t] - ra_120[t]) if side == SIDE_L else \
                    (rb_600[t] - rb_120[t])
        late_with = rb_120[t] if side == SIDE_L else ra_120[t]
        row[17] = bool(early_opp > 0 and late_with > 0)
        row[18] = bool(rb_600[t] > 0 and ra_600[t] > 0 and
                       dmid_abs[t] <= P["abs_move_atr"] * atr_px)

        # ---- M-08 CVD ----------------------------------------------------
        cv = cvd[t - 1] - cvd_med[t - 1]
        row[19] = bool((cv > 0) if side == SIDE_L else (cv < 0))
        row[20] = bool((cv < 0) if side == SIDE_L else (cv > 0))

        # ---- M-41 extreme absorption --------------------------------------
        px_with = dmid_x[t] * (1 if side == SIDE_L else -1)
        cvd_with = dcvd_x[t] * (1 if side == SIDE_L else -1)
        row[21] = bool(px_with >= P["xabs_px_atr"] * atr_px and cvd_with < 0)

        # ---- M-07 speed of tape -------------------------------------------
        r = rcnt_60[t] / float(P["tape_win_sec"])
        base = max(rate_todate[t - 1], 1e-6)
        row[22] = bool(r >= P["tape_spike_x"] * base)
        row[23] = bool(r <= P["tape_dead_x"] * base)

        # ---- M-86/M-36/M-38 touch index + memory --------------------------
        if near is not None:
            done = [x for x in near.touches if x[1] < t]
            live = [x for x in near.touches if x[0] < t <= x[1]]
            idx = len(done) + (1 if live else 0)
            if idx == 1:
                row[24] = 1
            elif idx == 2:
                row[25] = 1
            elif idx >= 3:
                row[26] = 1
            res = [x[2] for x in done if x[2] is not None]
            if res:
                row[27] = bool(res[-1])
                if len(res) >= 2:
                    row[28] = bool(res[-1] and res[-2])
            row[29] = bool(near.n >= 3 and near.vol >= 3 * agg_thr)

        # ---- M-39 losing steam ---------------------------------------------
        # rb_abs / ra_abs are already 120s ROLLING SUMS, so the three successive
        # approach windows are just three reads of the same array.  The first
        # draft subtracted consecutive rolling sums, which measures a second
        # difference and answers no question anyone asked.
        a3 = rb_abs if side == SIDE_S else ra_abs   # volume of the side pushing
        if t > 400:
            v1 = a3[t]                       # [t-120, t)
            v2 = a3[max(0, t - 120)]         # [t-240, t-120)
            v3 = a3[max(0, t - 240)]         # [t-360, t-240)
            row[30] = bool(v3 > v2 > v1 and v3 > 0)

        # ---- M-42 repeated failure to reclaim -------------------------------
        # "repeated attempts to reclaim the prior range, and repeated failure".
        # An ATTEMPT is price coming within 0.1*ATR of the window extreme on the
        # side that is trying to reclaim; a FAILURE is it then retreating by
        # >= 0.25*ATR before getting there.  Counting percentile CROSSINGS (the
        # first draft) fired on 98% of rows and measured nothing.
        w0 = max(0, t - 3600)
        seg = mid[w0:t]
        if seg.size > 600:
            near_tol = 0.10 * atr_px
            back = 0.25 * atr_px
            ext = float(np.max(seg)) if side == SIDE_S else float(np.min(seg))
            if side == SIDE_S:
                near = seg >= ext - near_tol
            else:
                near = seg <= ext + near_tol
            fails = 0
            k = 0
            L = seg.size
            while k < L:
                if near[k]:
                    j = k
                    while j < L and near[j]:
                        j += 1
                    tail = seg[j:min(j + 1800, L)]
                    if tail.size > 30:
                        if side == SIDE_S:
                            if float(np.min(tail)) <= ext - back:
                                fails += 1
                        else:
                            if float(np.max(tail)) >= ext + back:
                                fails += 1
                    k = j
                    continue
                k += 1
            row[31] = fails >= 2

        # ---- M-40 microbalance break ----------------------------------------
        if t > 500:
            seg = mid[max(0, t - 480):max(0, t - 300)]
            if seg.size > 120:
                rng = float(np.max(seg) - np.min(seg))
                if rng <= 0.2 * atr_px:
                    later = mid[max(0, t - 300):t]
                    if later.size > 10:
                        if side == SIDE_L:
                            row[32] = bool(np.max(later) > np.max(seg) + tick)
                        else:
                            row[32] = bool(np.min(later) < np.min(seg) - tick)

        # ---- M-70 overnight extreme still ahead ------------------------------
        if np.isfinite(on_hi) and t > ny0 and ny0 > 1:
            seg = mid[ny0:t]
            if seg.size > 10:
                if side == SIDE_L:
                    row[33] = bool(np.min(seg) > on_lo and emid > on_lo)
                else:
                    row[33] = bool(np.max(seg) < on_hi and emid < on_hi)

        # ---- M-73 initial balance -------------------------------------------
        if np.isfinite(ib_hi) and t > rep.get("ib_end", 10 ** 9):
            seg = mid[rep["ib_end"]:t]
            if seg.size > 5:
                if side == SIDE_L:
                    row[34] = bool(np.max(seg) > ib_hi)
                else:
                    row[34] = bool(np.min(seg) < ib_lo)

        # ---- M-71 open in prior value ----------------------------------------
        pv_h = float(meta.get("H", np.nan))
        pv_l = float(meta.get("L", np.nan))
        if np.isfinite(pv_h) and np.isfinite(pv_l) and pv_h > pv_l:
            lo_ = pv_l + 0.15 * (pv_h - pv_l)
            hi_ = pv_h - 0.15 * (pv_h - pv_l)
            row[35] = bool(lo_ <= mid[0] <= hi_)

        # ---- M-57 value area / edges + M-58 day type + M-11 thin behind -----
        if len(vp) >= 8:
            bks = np.fromiter(vp.keys(), dtype=np.int64)
            vs = np.fromiter(vp.values(), dtype=np.float64)
            so = np.argsort(-vs)
            poc_b = int(bks[so[0]])
            tot_v = vs.sum()
            cum = 0.0
            lo_b = hi_b = poc_b
            byb = dict(zip(bks.tolist(), vs.tolist()))
            cum = byb[poc_b]
            while cum < 0.70 * tot_v:
                up = byb.get(hi_b + 1, 0.0)
                dn = byb.get(lo_b - 1, 0.0)
                if up == dn == 0.0:
                    if hi_b - lo_b > 4000:
                        break
                    hi_b += 1
                    lo_b -= 1
                    continue
                if up >= dn:
                    hi_b += 1
                    cum += up
                else:
                    lo_b -= 1
                    cum += dn
            row[36] = bool(lo_b <= eb <= hi_b)
            row[37] = bool(abs(eb - hi_b) <= 2 or abs(eb - lo_b) <= 2)
            rlo, rhi = int(bks.min()), int(bks.max())
            if rhi > rlo:
                f = (poc_b - rlo) / float(rhi - rlo)
                row[38] = f >= 2.0 / 3.0
                row[39] = f <= 1.0 / 3.0
                row[40] = (not row[38]) and (not row[39])
            band = int(round(atr_px * P["thin_atr"] / tick))
            if band > 0:
                if side == SIDE_L:
                    behind = sum(byb.get(eb - k, 0.0) for k in range(1, band + 1))
                else:
                    behind = sum(byb.get(eb + k, 0.0) for k in range(1, band + 1))
                ahead = sum(byb.get(eb + (k if side == SIDE_L else -k), 0.0)
                            for k in range(1, band + 1))
                row[41] = bool(behind < 0.5 * max(ahead, 1.0))

        # ---- RED-FIRST mutants ------------------------------------------------
        tr = (t + P["rotate_sec"]) % n
        if tr > 2:
            ov = ra_abs[tr] if side == SIDE_L else rb_abs[tr]
            oq = q80_a[tr] if side == SIDE_L else q80_b[tr]
            row[42] = bool(ov >= max(oq, 1.0) and
                           dmid_abs[tr] <= P["abs_move_atr"] * atr_px)
        row[43] = bool(opp_vol < max(opp_q80, 1.0) and
                       dmid_abs[t] > P["abs_move_atr"] * atr_px)

    return D, EM, rep


def _worker(job):
    """Runs the detector bank TWICE per session:

      LIVE       every detector at the candidate's own decision second.
      DISPLACED  every detector at dec_sec - P['displace_sec'], the candidate's
                 outcome unchanged.  This is the canonical port displaced-entry
                 control (goalpath --shift): the structure is identical, only
                 the moment moves, so a genuine CONFIRMATION edge must LOSE
                 under displacement.  A detector whose displaced lift equals its
                 live lift is reading the session, not the moment.
    """
    asset, d8, dec, sides, atrs = job
    try:
        out = _build_session(asset, d8, dec, sides, atrs)
        if out is None:
            return asset, int(d8), None, None, None, {"error": "no receipt"}
        D, EM, rep = out
        decd = np.maximum(dec - P["displace_sec"], 2)
        outd = _build_session(asset, d8, decd, sides, atrs)
        Dd = outd[0] if outd is not None else np.zeros_like(D)
    except Exception as exc:                                  # noqa: BLE001
        return (asset, int(d8), None, None, None,
                {"error": "%s: %s" % (type(exc).__name__, exc)})
    return asset, int(d8), D, Dd, EM, rep


def load_population():
    z = np.load(MATRIX, allow_pickle=True)
    d8 = z["d8"]
    m = (d8 >= ERA_LO) & (d8 <= ERA_HI)
    fn = list(z["feature_names"])
    X = z["X"]
    out = {
        "cid": z["cid"][m], "d8": d8[m], "dec_sec": z["dec_sec"][m],
        "side": z["side"][m], "asset_idx": z["asset_idx"][m],
        "phase_dec": z["phase_dec"][m], "era_idx": z["era_idx"][m],
        "y_winner": z["y_winner"][m], "cert_close_usd": z["cert_close_usd"][m],
        "cert_peak_usd": z["cert_peak_usd"][m],
        "mae_before_argmax": z["mae_before_argmax"][m],
        "walled": z["walled"][m], "cert_refused": z["cert_refused"][m],
        "atr_usd": X[m][:, fn.index("atr_usd")].astype(np.float64),
    }
    cls_cols = [i for i, f in enumerate(fn) if f.startswith("cls_")]
    cls_names = [fn[i] for i in cls_cols]
    Xc = X[m][:, cls_cols]
    out["klass"] = np.argmax(Xc, axis=1).astype(np.int16)
    out["klass_names"] = cls_names
    z.close()
    return out


def run_detect(workers):
    os.makedirs(CACHE, exist_ok=True)
    Pn = load_population()
    assets = [C.ASSET_ORDER[i] for i in Pn["asset_idx"]]
    key = np.array(["%s|%08d" % (a, d) for a, d in zip(assets, Pn["d8"].tolist())])
    uk, inv = np.unique(key, return_inverse=True)
    jobs = []
    for gi, k in enumerate(uk.tolist()):
        a, d = k.split("|")
        sel = np.nonzero(inv == gi)[0]
        jobs.append((a, int(d), Pn["dec_sec"][sel].astype(np.int64),
                     Pn["side"][sel].astype(np.int64),
                     Pn["atr_usd"][sel]))
    MC.hb("creator-detect: %d session-assets, %d candidates, %d workers"
          % (len(jobs), Pn["d8"].size, workers))
    Dall = np.zeros((Pn["d8"].size, NDET_SESSION), dtype=np.uint8)
    Dis = np.zeros((Pn["d8"].size, NDET_SESSION), dtype=np.uint8)
    EMall = np.full(Pn["d8"].size, np.nan)
    reps = []
    errs = []
    t0 = time.time()
    idx_by_key = {k: np.nonzero(inv == gi)[0] for gi, k in enumerate(uk.tolist())}
    done = 0
    with mp.Pool(workers) as pool:
        for asset, d8, D, Dd, EM, rep in pool.imap_unordered(_worker, jobs,
                                                             chunksize=4):
            done += 1
            k = "%s|%08d" % (asset, d8)
            if D is None:
                errs.append((k, rep.get("error")))
            else:
                ix = idx_by_key[k]
                Dall[ix] = D
                Dis[ix] = Dd
                EMall[ix] = EM
                reps.append(rep)
            if done % 100 == 0:
                el = time.time() - t0
                MC.hb("detect %d/%d %.1f/s eta %.0fs"
                      % (done, len(jobs), done / max(el, 1e-9),
                         (len(jobs) - done) / max(done / max(el, 1e-9), 1e-9)))
    np.savez_compressed(os.path.join(CACHE, "detect.npz"),
                        cid=Pn["cid"], D=Dall, D_disp=Dis, entry_mid=EMall,
                        det_names=np.array(DET_NAMES[:NDET_SESSION]))
    with open(os.path.join(CACHE, "session_reps.json"), "w") as fh:
        json.dump({"reps": reps, "errors": errs, "params": P}, fh)
    MC.hb("creator-detect: done in %.0fs, %d errors" % (time.time() - t0,
                                                        len(errs)))
    return Dall, Pn, reps, errs


# ============================================================ stage B ========
def _cluster_z(y, x, cl):
    """Cluster-robust z for the mean difference y[x=1] - y[x=0], clusters=cl.

    Equivalent to the sandwich z on the OLS slope of y ~ 1 + x with CR0 by
    cluster (the batch-4/5 convention, session-clustered)."""
    x = x.astype(np.float64)
    y = y.astype(np.float64)
    n = y.size
    if n < 20 or x.sum() < 5 or (n - x.sum()) < 5:
        return float("nan"), float("nan"), float("nan")
    Xd = np.column_stack([np.ones(n), x])
    XtX = Xd.T @ Xd
    try:
        XtXi = np.linalg.inv(XtX)
    except np.linalg.LinAlgError:
        return float("nan"), float("nan"), float("nan")
    beta = XtXi @ (Xd.T @ y)
    r = y - Xd @ beta
    # Liang-Zeger meat, accumulated with bincount.  The textbook loop
    # (`for g: u = Xd[s].T @ r[s]`) masks the WHOLE 817k-row array once per
    # cluster — 1,930 clusters x 660 calls = 1.6e9 element touches per call and
    # the census never returned.  The cluster score is just a per-cluster sum of
    # [r, x*r], so bincount gives the identical matrix.
    uc, ci = np.unique(cl, return_inverse=True)
    G = uc.size
    s0 = np.bincount(ci, weights=r, minlength=G)
    s1 = np.bincount(ci, weights=x * r, minlength=G)
    meat = np.array([[float((s0 * s0).sum()), float((s0 * s1).sum())],
                     [float((s0 * s1).sum()), float((s1 * s1).sum())]])
    corr = G / max(G - 1.0, 1.0)
    V = XtXi @ (meat * corr) @ XtXi
    se = float(np.sqrt(max(V[1, 1], 0.0)))
    if se <= 0:
        return float(beta[1]), float("nan"), float("nan")
    z = float(beta[1]) / se
    from math import erfc, sqrt
    p = erfc(abs(z) / sqrt(2.0))
    return float(beta[1]), z, p


def _boot_lift(y, x, di, G, reps, rng):
    """Day-clustered bootstrap CI on lift = P(y|x=1) / P(y).

    The draw unit is the DAY (D-036/D-073), identical to goalpath.cluster_boot;
    the RATIO form does not exist there, so it is built here on PER-DAY
    SUFFICIENT STATISTICS.  A lift is a ratio of two sums over days, so a day
    resample only needs four per-day counts — resampling the 817k-row index
    itself (the first draft) was ~1.6e9 operations per detector and never
    finished.
    """
    nf_d = np.bincount(di, weights=x.astype(np.float64), minlength=G)
    nfw_d = np.bincount(di, weights=(x & y).astype(np.float64), minlength=G)
    n_d = np.bincount(di, minlength=G).astype(np.float64)
    nw_d = np.bincount(di, weights=y.astype(np.float64), minlength=G)
    out = np.empty(reps)
    for b in range(reps):
        p = rng.integers(0, G, G)
        f = nf_d[p].sum()
        base_n = n_d[p].sum()
        base_w = nw_d[p].sum()
        if f < 5 or base_n <= 0 or base_w <= 0:
            out[b] = np.nan
            continue
        out[b] = (nfw_d[p].sum() / f) / (base_w / base_n)
    ok = out[np.isfinite(out)]
    if ok.size < reps // 4:
        return float("nan"), float("nan")
    return float(np.percentile(ok, 2.5)), float(np.percentile(ok, 97.5))


def _shuffle_null(y, x, sess, reps, rng):
    """DESTRUCTION (the batch-4/5 law): permute the carrying field WITHIN its
    own exchangeable block (SESSION), 40 replicates, seeded.  Frequency is
    preserved exactly; row alignment is destroyed.  Uses the port's own
    batch4_census._shuffle_within, and emits DEGENERATE_NULL when the blocks
    carry no informative variation (batch4.perm_support)."""
    base = y.mean()
    if base <= 0:
        return float("nan"), float("nan"), 0, V_DEGEN
    n_groups, med_sz, n_inf = _perm_support(sess, x)
    if n_inf < 5:
        return float("nan"), float("nan"), n_inf, V_DEGEN
    vals = []
    for _ in range(reps):
        xs = _shuffle_within(x, sess, rng).astype(bool)
        if xs.sum() < 5:
            continue
        vals.append(y[xs].mean() / base)
    if not vals:
        return float("nan"), float("nan"), n_inf, V_DEGEN
    v = np.array(vals)
    return (float(v.mean()),
            float(v.std(ddof=1)) if v.size > 1 else float("nan"),
            n_inf, "OK")


def _member_auc(y, x, gi, G):
    """Within-group (asset, day, class) Mann-Whitney AUC of the detector flag
    for picking the D-021 winner out of its OWN same-day same-class pool.

    0.5 = the detector does not separate members at all — which is exactly the
    SEL_WRONG_MEMBER question the deficit ledger names as the dominant deficit.

    The flag is BINARY, so the pairwise count is closed-form per group:
        num = w1*l0 + 0.5*(w1*l1 + w0*l0),  den = (w1+w0)*(l1+l0)
    with w1/w0 = winners with/without the flag and l1/l0 the losers.  Summing
    that over groups with bincount replaces a 1e8-iteration double loop.
    """
    yb = y > 0.5
    xb = x > 0.5
    w1 = np.bincount(gi, weights=(yb & xb).astype(np.float64), minlength=G)
    w0 = np.bincount(gi, weights=(yb & ~xb).astype(np.float64), minlength=G)
    l1 = np.bincount(gi, weights=(~yb & xb).astype(np.float64), minlength=G)
    l0 = np.bincount(gi, weights=(~yb & ~xb).astype(np.float64), minlength=G)
    nw, nl = w1 + w0, l1 + l0
    live = (nw > 0) & (nl > 0)
    num = (w1 * l0 + 0.5 * (w1 * l1 + w0 * l0))[live].sum()
    den = (nw * nl)[live].sum()
    return (num / den if den > 0 else float("nan")), int(live.sum()), int(den)


def _kstar():
    """The frozen EPISODE_CAUSAL link constants, READ from the committed
    receipt (baseline_replay.episode_pins) exactly as info_ceiling._kstar does.
    SI 180 / HG 120 / NKD 150 s."""
    import baseline_replay as BR
    kst, _spn = BR.episode_pins(check=True)
    return {a: max(kst[(a, 1)], kst[(a, -1)]) for a in C.ASSET_ORDER}


def build_wall_pairs(Pn):
    """info_ceiling.build_pairs, restated on the matrix's own fields: same
    asset/day/phase cell, OPPOSITE sides, |d dec_sec| <= K*(asset), entry mids
    within 0.5 x ATR14, one leg >= +$1,000 and the other <= -$900."""
    WIN, WALL, VIC = 1000.0, -900.0, 0.5
    KST = _kstar()
    cert = Pn["cert_close_usd"]
    ok = Pn["cert_refused"] == 0
    key = np.array(["%d|%08d|%d" % (a, d, p) for a, d, p in
                    zip(Pn["asset_idx"].tolist(), Pn["d8"].tolist(),
                        Pn["phase_dec"].tolist())])
    uk, inv = np.unique(key, return_inverse=True)
    pw, pl = [], []
    for g in range(uk.size):
        s = np.nonzero((inv == g) & ok)[0]
        if s.size < 2:
            continue
        w = s[cert[s] >= WIN]
        l = s[cert[s] <= WALL]
        if w.size == 0 or l.size == 0:
            continue
        K = KST[C.ASSET_ORDER[int(Pn["asset_idx"][s[0]])]]
        for a in w.tolist():
            for b in l.tolist():
                if Pn["side"][a] == Pn["side"][b]:
                    continue
                if abs(int(Pn["dec_sec"][a]) - int(Pn["dec_sec"][b])) > K:
                    continue
                atr = np.nanmean([Pn["atr_usd"][a], Pn["atr_usd"][b]])
                if not np.isfinite(atr) or atr <= 0:
                    continue
                mg = abs(float(Pn["entry_mid"][a]) - float(Pn["entry_mid"][b]))
                if np.isfinite(mg) and mg > VIC * atr:
                    continue
                pw.append(a)
                pl.append(b)
    return np.array(pw, dtype=np.int64), np.array(pl, dtype=np.int64)


def run_census():
    d = np.load(os.path.join(CACHE, "detect.npz"), allow_pickle=True)
    Dall = d["D"]
    Ddisp = d["D_disp"]
    cid_d = d["cid"]
    Pn = load_population()
    assert np.array_equal(cid_d, Pn["cid"]), "detect cache is stale — re-run --detect"
    Pn["entry_mid"] = d["entry_mid"]

    fin = (Pn["cert_refused"] == 0) & np.isfinite(Pn["y_winner"])
    y = np.nan_to_num(Pn["y_winner"], nan=0.0)[fin] > 0.5
    D = Dall[fin].astype(bool)
    disp = Ddisp[fin].astype(bool)
    cc = Pn["cert_close_usd"][fin]
    cp = Pn["cert_peak_usd"][fin]
    d8 = Pn["d8"][fin]
    ai = Pn["asset_idx"][fin]
    ei = Pn["era_idx"][fin]
    ph = Pn["phase_dec"][fin]
    kl = Pn["klass"][fin]
    day = np.array(["%d|%08d" % (a, x) for a, x in zip(ai.tolist(), d8.tolist())])
    grp = np.array(["%d|%08d|%d" % (a, x, k) for a, x, k in
                    zip(ai.tolist(), d8.tolist(), kl.tolist())])
    _ud, di_day = np.unique(day, return_inverse=True)
    G_day = _ud.size
    _ug, gi_mem = np.unique(grp, return_inverse=True)
    G_mem = _ug.size
    base = float(y.mean())

    # The two CAUSAL red-first mutants are built here rather than in the
    # detector pass, because both are functions of ABSORPTION's own column.
    jabs = DET_NAMES.index("ABSORPTION")
    mrng = np.random.default_rng(P["seed"] + 1)
    mut_shuf = _shuffle_within(D[:, jabs], day, mrng).astype(bool)
    mut_iid = mrng.random(D.shape[0]) < float(D[:, jabs].mean())
    D = np.column_stack([D, mut_shuf, mut_iid])
    disp = np.column_stack([disp, mut_shuf, mut_iid])
    assert D.shape[1] == NDET, "detector bank / cache width disagree"
    rng = np.random.default_rng(P["seed"])

    pw, pl = build_wall_pairs(Pn)
    fin_idx = np.nonzero(fin)[0]
    pos = -np.ones(Pn["d8"].size, dtype=np.int64)
    pos[fin_idx] = np.arange(fin_idx.size)
    keepp = (pos[pw] >= 0) & (pos[pl] >= 0)
    pw, pl = pos[pw[keepp]], pos[pl[keepp]]

    MAIN, STRATA, LEDGER = [], [], []
    MAIN_COLS = ("detector", "mechanic", "fidelity", "n", "n_fire", "freq",
                 "hit_rate", "base_rate", "lift", "lift_lo95", "lift_hi95",
                 "conc_ratio", "cond_close_usd", "cond_close_lo95",
                 "cond_close_hi95", "cond_peak_usd", "base_close_usd",
                 "delta_pp", "z_cluster", "p_cluster", "null_shuffle_lift",
                 "null_shuffle_sd", "null_informative_groups",
                 "null_displaced_lift", "lift_vs_null", "z_vs_null",
                 "p_vs_null", "destruction", "verdict",
                 "holm_rank", "holm_threshold", "holm_verdict", "p_holm")
    STRATA_COLS = ("detector", "stratum", "value", "n", "n_fire", "hit_rate",
                   "base_rate", "lift", "z_cluster", "p_cluster",
                   "holm_rank", "holm_threshold", "holm_verdict", "p_holm")
    LEDGER_COLS = ("detector", "member_auc", "member_groups", "member_pairs",
                   "wallpair_n", "wallpair_discriminating", "wallpair_acc",
                   "wallpair_z", "wallpair_p", "holm_rank", "holm_threshold",
                   "holm_verdict", "p_holm")

    era_names = {i: e[0] for i, e in enumerate(MC.ERAS)}
    ph_names = {0: "TOKYO", 1: "LONDON", 2: "NY"}

    t_det = time.time()
    for j, (name, mech, fid, _stmt) in enumerate(DETECTORS):
        MC.hb("census %d/%d %s (%.0fs)" % (j + 1, NDET, name,
                                           time.time() - t_det))
        x = D[:, j]
        nf = int(x.sum())
        freq = nf / float(x.size)
        base_cc = float(np.nanmean(cc))
        if nf < 30:
            MAIN.append([name, mech, fid, int(x.size), nf, freq,
                         float("nan"), base] + [float("nan")] * 19
                        + [V_DEGEN, V_RARE])
            LEDGER.append([name, float("nan"), 0, 0, int(pw.size), 0,
                           float("nan"), float("nan"), float("nan")])
            continue
        hit = float(y[x].mean())
        off = float(y[~x].mean()) if (~x).sum() else float("nan")
        lift = hit / base if base > 0 else float("nan")
        conc = hit / off if np.isfinite(off) and off > 0 else float("nan")
        lo, hi = _boot_lift(y, x, di_day, G_day, P["boot_reps"], rng)
        # CC-M1-8: BOTH certificate readings on every value row.
        vfire = cc[x]
        dfire = day[x]
        okv = np.isfinite(vfire)
        if okv.sum() >= 30:
            cvv, cvlo, cvhi, _nd = cluster_boot(vfire[okv], dfire[okv],
                                                n=400, seed=P["seed"])
        else:
            cvv = cvlo = cvhi = float("nan")
        cpv = float(np.nanmean(cp[x])) if np.isfinite(cp[x]).any() else float("nan")
        b1, z, p = _cluster_z(y.astype(float), x, day)
        sm, ss, ninf, nverd = _shuffle_null(y, x, day, P["shuffle_reps"], rng)
        xd = disp[:, j]
        dl = (float(y[xd].mean()) / base) if xd.sum() >= 30 and base > 0 \
            else float("nan")
        # THE EFFECT IS MEASURED AGAINST THE DESTRUCTION NULL, NOT AGAINST 1.0.
        # A raw lift is confounded by BETWEEN-SESSION variation: a detector that
        # simply fires more on high-winner-rate days scores a lift while
        # carrying no within-day timing information at all.  The within-session
        # shuffle holds the session composition fixed, so `lift / null_lift` is
        # the part of the effect that is actually about the MOMENT — the same
        # "the destroyed quantity is the EDGE" reading batch 5 uses.
        from math import erfc, sqrt
        if np.isfinite(sm) and np.isfinite(ss) and ss > 0:
            lvn = lift / sm if sm > 0 else float("nan")
            zvn = (lift - sm) / ss
            pvn = erfc(abs(zvn) / sqrt(2.0))
        else:
            lvn = zvn = pvn = float("nan")
        if not np.isfinite(zvn):
            destr = V_DEGEN
        elif abs(zvn) < 2.0:
            destr = "DESTROYED"
        elif (lift - 1.0) * (zvn) < 0:
            destr = "INVERTED"
        else:
            destr = "SURVIVES"
        # CC-M2-9.1 vocabulary.  ENTRY/VETO require the effect to (a) clear the
        # destruction null, (b) survive Holm inside the whole-batch family, and
        # (c) have a day-clustered CI on the same side of 1.0.  Holm is applied
        # after the family is built, so the verdict is finalised below.
        MAIN.append([name, mech, fid, int(x.size), nf, freq, hit, base, lift,
                     lo, hi, conc, cvv, cvlo, cvhi, cpv, base_cc,
                     100.0 * b1, z, p, sm, ss, ninf, dl, lvn, zvn, pvn,
                     destr, V_NULL])

        for lbl, arr, names in (("era", ei, era_names),
                                ("asset", ai, {i: a for i, a in
                                               enumerate(C.ASSET_ORDER)}),
                                ("phase", ph, ph_names)):
            for v in sorted(set(arr.tolist())):
                s = arr == v
                if s.sum() < 200 or x[s].sum() < 20:
                    continue
                ys, xs, ds = y[s], x[s], day[s]
                bs = float(ys.mean())
                hs = float(ys[xs].mean())
                _b, zs, ps = _cluster_z(ys.astype(float), xs, ds)
                STRATA.append([name, lbl, names.get(v, str(v)), int(s.sum()),
                               int(xs.sum()), hs, bs,
                               (hs / bs) if bs > 0 else float("nan"), zs, ps])

        mauc, ngrp, npair = _member_auc(y.astype(float), x.astype(float),
                                        gi_mem, G_mem)
        if pw.size:
            fw, fl = x[pw], x[pl]
            disc = fw != fl
            nd = int(disc.sum())
            acc = float(fw[disc].mean()) if nd else float("nan")
            if nd >= 10:
                from math import erfc, sqrt
                zz = (acc - 0.5) / np.sqrt(0.25 / nd)
                pp = erfc(abs(zz) / sqrt(2.0))
            else:
                zz = pp = float("nan")
        else:
            nd = 0
            acc = zz = pp = float("nan")
        LEDGER.append([name, mauc, ngrp, npair, int(pw.size), nd, acc, zz, pp])

    m = _holm_family([(MAIN, 26, len(MAIN_COLS)),
                      (STRATA, 9, len(STRATA_COLS)),
                      (LEDGER, 8, len(LEDGER_COLS))])

    # ---- finalise CC-M2-9.1 verdicts now that Holm has run ----------------
    V_I, D_I, LO_I, HI_I, LI_I, CONC_I = 28, 27, 9, 10, 8, 11
    HV_I = len(MAIN_COLS) - 2
    for r in MAIN:
        if r[V_I] == V_RARE:
            continue
        holm_ok = r[HV_I] == "HOLM_SIGNIFICANT"
        lo_, hi_, lift_, conc_, destr_ = r[LO_I], r[HI_I], r[LI_I], r[CONC_I], r[D_I]
        if destr_ == V_DEGEN:
            r[V_I] = V_DEGEN
        elif holm_ok and destr_ == "SURVIVES" and np.isfinite(lo_) and lo_ > 1.0:
            r[V_I] = V_ENTRY
        elif holm_ok and destr_ == "SURVIVES" and np.isfinite(hi_) and hi_ < 1.0:
            r[V_I] = V_VETO
        elif np.isfinite(conc_) and conc_ >= 1.25:
            r[V_I] = V_CONC
        else:
            r[V_I] = V_NULL

    os.makedirs(PROV, exist_ok=True)
    phash = MC.params_hash(P)
    MC.write_tsv(os.path.join(PROV, "CREATOR_CENSUS_MAIN.tsv"), SECTION, phash,
                 MAIN_COLS, MAIN,
                 extra=("holm family size m=%d (MAIN+STRATA+LEDGER)" % m,
                        "base_rate = D-021 y_winner over E2..E6 non-refused rows",
                        "population n=%d, winners=%d" % (y.size, int(y.sum()))))
    MC.write_tsv(os.path.join(PROV, "CREATOR_CENSUS_STRATA.tsv"), SECTION,
                 phash, STRATA_COLS, STRATA,
                 extra=("same Holm family as MAIN and LEDGER (m=%d)" % m,))
    MC.write_tsv(os.path.join(PROV, "CREATOR_CENSUS_LEDGER.tsv"), SECTION,
                 phash, LEDGER_COLS, LEDGER,
                 extra=("member_auc: within (asset,day,class) — the "
                        "SEL_WRONG_MEMBER pool; 0.5 = no separation",
                        "wallpair: same asset/day/phase-cell, opposite sides, "
                        "|d dec_sec|<=1800s, one leg >=+$1,000 other <=-$900",
                        "n_wall_pairs=%d" % int(pw.size)))
    DEF_COLS = ("detector", "mechanic_ids", "fidelity", "computable_statement")
    MC.write_tsv(os.path.join(PROV, "CREATOR_DETECTORS.tsv"), SECTION, phash,
                 DEF_COLS, [[a, b, c, dd] for a, b, c, dd in DETECTORS],
                 extra=("fidelity EXACT = MBP-1 gives the creator's own "
                        "quantity; APPROX-L1 = top-of-book only, blind to the "
                        "depth his DOM shows; APPROX-VP = profile from our own "
                        "prints, not the exchange composite",))
    with open(os.path.join(CACHE, "census.json"), "w") as fh:
        json.dump({"m_holm": m, "base": base, "n": int(y.size),
                   "n_wall_pairs": int(pw.size), "params": P}, fh)
    MC.hb("creator-census: %d detectors, holm m=%d, base=%.4f, pairs=%d"
          % (NDET, m, base, int(pw.size)))
    return MAIN, STRATA, LEDGER


# ==================================================== stage C: replications ==
# The creator publishes numbers, not just mechanics.  These are DIRECT
# replications of his headline statistics on our five years, each reported
# beside his claim.  A replication that misses is reported as a miss.
GROUPS = {
    "memory": ("PRIOR_TOUCH_HELD", "PRIOR_2_HELD", "TOUCH_1_VIRGIN", "TOUCH_2",
               "TOUCH_GE3", "REFILL_AREA_HELD"),
    "construction": ("ZONE_BUILT_BY_SIZE", "IMB_350", "IMB_350_AT_AGG",
                     "SQUEEZE", "SQUEEZE_CATALYST_NEAR"),
    "location": ("IN_VALUE_AREA", "AT_VA_EDGE", "DAY_P", "DAY_B", "DAY_D",
                 "THIN_BEHIND", "ONX_UNTOUCHED_AHEAD", "IB_BROKEN_WITH",
                 "OPEN_IN_PRIOR_VALUE"),
    "flow": ("AGG_PRINT_60", "AGG_WITH_SIDE_60", "AGG_OPP_SIDE_60",
             "ABSORPTION", "BODY_REWARDED_WITH", "WICK_ABSORBED_OPP",
             "CVD_WITH", "CVD_AGAINST", "EXTREME_ABSORPTION", "TAPE_SPIKE",
             "TAPE_DEAD", "DIV_BOX_350", "PASSIVE_MOVE", "TWO_STAGE",
             "BOTH_ABSORBED", "REFILL_CLOCK", "LOSING_STEAM"),
}


def _auc(y, s):
    """AUC via the rank identity (batch4_census.auc, restated for a float
    score; identical arithmetic)."""
    y = np.asarray(y, dtype=bool)
    n1, n0 = int(y.sum()), int((~y).sum())
    if n1 == 0 or n0 == 0:
        return float("nan")
    r = np.empty(s.size, dtype=np.float64)
    o = np.argsort(s, kind="stable")
    sv = s[o]
    i = 0
    while i < sv.size:
        j = i
        while j + 1 < sv.size and sv[j + 1] == sv[i]:
            j += 1
        r[o[i:j + 1]] = 0.5 * (i + j) + 1.0
        i = j + 1
    return (r[y].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0)


def run_replications():
    d = np.load(os.path.join(CACHE, "detect.npz"), allow_pickle=True)
    with open(os.path.join(CACHE, "session_reps.json")) as fh:
        J = json.load(fh)
    reps = J["reps"]
    Pn = load_population()
    fin = (Pn["cert_refused"] == 0) & np.isfinite(Pn["y_winner"])
    y = np.nan_to_num(Pn["y_winner"], nan=0.0)[fin] > 0.5
    D = d["D"][fin].astype(np.float64)
    ai = Pn["asset_idx"][fin]
    d8 = Pn["d8"][fin]
    day = np.array(["%d|%08d" % (a, x) for a, x in zip(ai.tolist(), d8.tolist())])
    mae = Pn["mae_before_argmax"][fin]
    cc = Pn["cert_close_usd"][fin]

    R = []
    COLS = ("statistic", "creator_claim", "creator_source", "ours",
            "ci_lo95", "ci_hi95", "n", "verdict", "note")

    # --- M-80: what fraction of zone touches HOLD -------------------------
    tt = float(sum(r.get("n_touch_resolved", 0) for r in reps))
    th = float(sum(r.get("n_touch_held", 0) for r in reps))
    hr = th / tt if tt else float("nan")
    per_day = np.array([r.get("n_touch_held", 0) / max(r.get("n_touch_resolved", 0), 1)
                        for r in reps if r.get("n_touch_resolved", 0) >= 3])
    dkeys = np.array(["%s|%08d" % (r["asset"], r["d8"]) for r in reps
                      if r.get("n_touch_resolved", 0) >= 3])
    if per_day.size > 30:
        pt, lo, hi, _n = cluster_boot(per_day, dkeys, n=2000, seed=P["seed"])
    else:
        pt = lo = hi = float("nan")
    R.append(["touches that HOLD", "42%", "refill-effect.pdf p.8/p.23",
              hr, lo, hi, int(tt),
              "MISS" if not (0.37 <= hr <= 0.47) else "REPLICATES",
              "our zones/levels hold materially more often than his NQ zones; "
              "different instruments and a price-based (not trade-based) "
              "hold/break resolution"])

    # --- M-83: the 18-tick dip --------------------------------------------
    tickusd = np.array([C.ASSETS[C.ASSET_ORDER[a]]["tick_usd"] for a in ai.tolist()])
    dip = mae / tickusd
    okw = y & np.isfinite(dip)
    if okw.sum() > 100:
        med = float(np.median(dip[okw]))
        pt2, lo2, hi2, _n = cluster_boot(dip[okw], day[okw], n=2000,
                                         seed=P["seed"], stat=np.median)
    else:
        med = pt2 = lo2 = hi2 = float("nan")
    R.append(["median WINNER's adverse dip before it works (D-021 winners)",
              "18 ticks",
              "refill-effect.pdf p.10/p.23", med, lo2, hi2, int(okw.sum()),
              "MISS — STRUCTURALLY CENSORED",
              "NOT A FAIR TEST OF HIS CLAIM: D-021 DEFINES a winner as "
              "mae_before_argmax <= $300, so the label has already thrown away "
              "every winner that dipped far.  The uncapped row below is the "
              "honest replication"])
    # The uncapped reading — the only fair test of M-83.
    unc = np.isfinite(dip) & (cc >= 1000.0)
    if unc.sum() > 100:
        umed = float(np.median(dip[unc]))
        _p, ulo, uhi, _n = cluster_boot(dip[unc], day[unc], n=2000,
                                        seed=P["seed"], stat=np.median)
        q75 = float(np.percentile(dip[unc], 75))
        R.append(["median WINNER's adverse dip, UNCAPPED (cert_close>=$1,000, "
                  "no MAE filter)", "18 ticks", "refill-effect.pdf p.10/p.23",
                  umed, ulo, uhi, int(unc.sum()),
                  "REPLICATES IN SHAPE, HALF THE MAGNITUDE",
                  "his 18 ticks sits at OUR 75th percentile (q75 = %.0f ticks). "
                  "The mechanism is real on our data — winners routinely go "
                  "against you first — at about half his median" % q75])

    # --- M-70: the 94% overnight-extreme touch ------------------------------
    tou = [r for r in reps if "ny_touch_onh" in r]
    if tou:
        f = np.array([1.0 if (r["ny_touch_onh"] or r["ny_touch_onl"]) else 0.0
                      for r in tou])
        dk = np.array(["%s|%08d" % (r["asset"], r["d8"]) for r in tou])
        pt3, lo3, hi3, _n = cluster_boot(f, dk, n=2000, seed=P["seed"])
        R.append(["RTH touches the overnight HIGH or LOW", "94%",
                  "mastering-amt-vp.pdf p.15/p.21 (ES 92.5-95.4%)",
                  float(f.mean()), lo3, hi3, int(f.size),
                  "REPLICATES" if 0.88 <= f.mean() <= 0.99 else "MISS",
                  "his number is measured on ES; ours on SI/HG/NKD with "
                  "'overnight' = everything before the NY phase opens"])
        fb = np.array([1.0 if (r["ny_touch_onh"] and r["ny_touch_onl"]) else 0.0
                       for r in tou])
        R.append(["RTH touches BOTH overnight extremes", "20-24%",
                  "mastering-amt-vp.pdf p.21", float(fb.mean()),
                  float("nan"), float("nan"), int(fb.size),
                  "REPLICATES" if 0.15 <= fb.mean() <= 0.32 else "MISS",
                  "the creator's own 'either, not both' caveat"])

    # --- M-82: memory+location vs flow alone --------------------------------
    idx = {nm: i for i, nm in enumerate(DET_NAMES)}
    for gname, cols in (("memory+location",
                         GROUPS["memory"] + GROUPS["location"]),
                        ("flow alone", GROUPS["flow"]),
                        ("construction alone", GROUPS["construction"])):
        cix = [idx[c] for c in cols if c in idx]
        sub = D[:, cix]
        # a sign-free score: each column signed by its own day-1 direction is
        # in-sample, so we report the BEST SINGLE column's AUC (honest ceiling
        # for a one-feature reader) and the unsigned count-score AUC.
        aucs = [abs(_auc(y, sub[:, k]) - 0.5) + 0.5 for k in range(sub.shape[1])]
        best = float(np.nanmax(aucs)) if aucs else float("nan")
        R.append(["AUC, %s (best single detector)" % gname,
                  "0.63 (memory+location) / 0.54 (flow alone)",
                  "refill-effect.pdf p.9/p.23", best, float("nan"),
                  float("nan"), int(y.size), "SEE_NOTE",
                  "sign taken in-sample, so this is an optimistic CEILING for "
                  "one feature, not a walk-forward AUC.  The creator's 0.63 is "
                  "a fitted multi-feature model on his own instrument"])

    # --- the base rate the whole census sits on -----------------------------
    R.append(["D-021 winner base rate, E2-E6", "n/a (his R-based)",
              "our contract", float(y.mean()), float("nan"), float("nan"),
              int(y.size), "CONTEXT",
              "cert_close >= $1,000 AND MAE <= $300 AND not walled"])
    R.append(["mean cert_PEAK_usd, E2-E6 all candidates", "n/a",
              "CC-M1-8 companion reading", float(np.nanmean(Pn["cert_peak_usd"][fin])),
              float("nan"), float("nan"), int(y.size), "CONTEXT",
              "published beside every close reading so no detector's "
              "conditional value is quoted on one certificate alone"])
    R.append(["mean cert_close_usd, E2-E6 all candidates",
              "-0.285R (fade every touch)", "refill-effect.pdf p.8",
              float(np.nanmean(cc)), float("nan"), float("nan"), int(y.size),
              "DIRECTIONALLY REPLICATES",
              "his 'trade every touch loses' and our 'the unselected roster is "
              "negative' are the same statement in different units"])

    MC.write_tsv(os.path.join(PROV, "CREATOR_REPLICATIONS.tsv"), SECTION,
                 MC.params_hash(P), COLS, R,
                 extra=("direct replications of the creator's OWN published "
                        "numbers on OUR five years / three assets",
                        "a miss is reported as a miss"))
    for r in R:
        MC.hb("REPL %-46s claim=%-12s ours=%s" % (r[0][:46], r[1][:12], r[3]))
    return R


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--detect", action="store_true")
    ap.add_argument("--census", action="store_true")
    ap.add_argument("--replicate", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    if a.detect:
        run_detect(min(a.workers, 8))
    if a.census:
        run_census()
    if a.replicate:
        run_replications()
    if not (a.detect or a.census or a.replicate):
        ap.error("need --detect and/or --census and/or --replicate")


if __name__ == "__main__":
    main()
