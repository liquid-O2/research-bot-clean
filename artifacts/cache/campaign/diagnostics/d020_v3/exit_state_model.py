#!/usr/bin/env python3
"""exit_state_model.py — RUNG 2 of the exit program: POST-ENTRY STATE MODEL.

RUNG 1 (`exit_engine.py`, `EXIT_RUNG1_REPORT.md`) failed BY CONSTRUCTION: a
confirmation-in / confirmation-out trade pays the ZigZag threshold twice
($156-$228 to enter, $135-$198 to exit) and the pivot-to-pivot leg is only
$285-$427 gross, so every price-symmetric mirror rule compresses winners and
duds at the same rate and nets zero.  Its own hand-off: the exit must be
CLASS-CONDITIONAL — the whole prize is telling a live winner from a live dud AT
THE EXIT SECOND — and one position destroys 45-50% of the picked value before
any exit rule is applied, so the deployment truth (up to TWO minis, D-030) has
to be measured as well.

WHAT THIS FILE DOES (the orchestrator's pinned design, D-002 — implemented,
not redesigned):

1. TRAJECTORY DATASET.  Every roster candidate of every era block is a training
   trajectory.  At minutes {1,3,5,10,15,20,30,45,60,90,120,180} after the
   decision second — while the position is still open, i.e. strictly before the
   $300 wall would have filled and before the close — the state is sampled:

     position      age, unrealised $, MFE/MAE-so-far, giveback fraction,
                   velocity, distance to the wall, runway
     structure     pivots confirmed FOR / AGAINST since entry (the same causal
                   ZigZag ladder the roster is built from), seconds since each,
                   penetration depth past the entry extreme and past the best
                   mark, position in the session range
     sniper state  flow / option-delta joint z (model_v3's `joint` statistic,
                   transcribed), urgency, quote churn + book erosion
                   (model_v2's T1.4 formulas, transcribed), print-book
                   imbalance trend (distill_model's D tier), vol trajectory
                   (PROXY_VOL level/slope/asymmetry + the fvol lane's
                   sigma_inst vs sigma_now), realised-vol ratio

   TARGET: remaining value = (best mark strictly AFTER t and before the wall
   fill / close) minus the unrealised mark AT t, binarised at >= $150.  The
   576c round trip cancels in the difference, so the target is a pure
   "is there still money in this trade" question.

2. MODEL.  A small HistGBT plus an L1-logistic twin (D-040: the deployed taker
   is a frozen deterministic classical model; the twin is the sparse-linear
   discipline check).  Hyper-parameters are chosen ONCE by session-grouped CV
   inside the STUDY window 125..427 — strictly prior to every test block — from
   a preregistered grid, then FROZEN for every segment.  No test block ever
   selects anything.

3. POLICY.  Hold while P(remaining >= $150) >= theta; exit at the first sampled
   minute whose P falls below theta, or at the $300 wall, or at the close.
   theta in {0.30, 0.40, 0.50} is PREREGISTERED and every value is reported.

4. REPLAY.  Exactly rung 1's machinery (`exit_engine.Session`, `replay_trade`,
   `summarise`, the same picks, the same 576c, the same wall with gap-through,
   the same eras f..i + the blind_e3 control), extended with a second occupancy
   mode: TWO concurrent positions, entering the next pick whenever fewer than
   two are open.  Rung 1's six implementable rules and its oracle are re-run
   here under BOTH occupancy modes so the comparison is like-for-like.

LAWS.  Every sampled minute reads only windows that END at and EXCLUDE that
second (`distill_model`'s window arithmetic) and only pivots CONFIRMED at or
before it (`render.swings` emits a pivot at its retrace).  Training rows for a
segment come only from sessions strictly before its test block — the same
walk-forward splits as `era_retest.py`.  Costs are charged on every trade.  The
sealed zone (>= `packlib.SEALED_FROM`) is never touched.

    exit_state_model.py [--stage traj|fit|replay|report|all] [--jobs N]
                        [--rebuild]
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np                                       # noqa: E402
import pandas as pd                                      # noqa: E402

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import packlib as P                                      # noqa: E402
import render as R                                       # noqa: E402
import daylib as D                                       # noqa: E402
import distill_model as dm                               # noqa: E402
import build_quotes as bq                                # noqa: E402
import walkforward as wf                                 # noqa: E402
import era_retest as er                                  # noqa: E402
import exit_engine as ee                                 # noqa: E402

ROOT = P.ROOT
MATRIX = ROOT / "FEATURES_ERA.tsv"
OUTDIR = ROOT / "exit_segments"
TRAJDIR = OUTDIR / "traj"
PICKS = OUTDIR / "picks.tsv"
REPORT = ROOT / "EXIT_RUNG2_REPORT.md"
VERDICT = ROOT / "EXIT_RUNG2_VERDICT.md"
HYPERS = OUTDIR / "state_hypers.json"

#: `render.swings`' fixed 15bp pin rostered blocks study_e1..blind_e3; ORCH-6.1's
#: max(12bp, 0.11 x ATR14) rostered e4..e7.  `exit_engine` only ever replayed
#: `blind_e3` out of the history, so its own set names just that block; the
#: trajectory build covers the whole history and widens the set here.  Both
#: agree on every block they share, so the rung-1 replay is bit-identical.
PIN_BLOCKS = set(er.HISTORY)
ee.FIXED_PIN_BLOCKS = PIN_BLOCKS

SEGMENTS = er.SEGMENTS                     # (e, blind_e3) ... (i, e7)
ARMS = er.ARMS
KS = ee.KS
SEED = dm.SEED

#: ---- preregistered, fixed before any number was computed --------------------
OFFSETS = (1, 3, 5, 10, 15, 20, 30, 45, 60, 90, 120, 180)     # minutes
REMAIN_DOLLARS = 150.0
THETAS = (0.30, 0.40, 0.50)
OCCUPANCIES = (1, 2)
#: the study window the hyper-parameter CV runs inside — strictly prior to every
#: test block in `SEGMENTS` (the earliest test block starts at 428)
STUDY_HI = 427
CV_FOLDS = 5
GBT_GRID = [dict(max_depth=d, max_iter=m, learning_rate=0.05,
                 min_samples_leaf=leaf, l2_regularization=1.0)
            for d in (2, 3) for m in (150, 300) for leaf in (20, 50)]
L1_GRID = [0.01, 0.1, 1.0]
SHUFFLE_DRAWS = 3
SHUFFLE_THETA = 0.40
#: POST-HOC DIAGNOSTIC ONLY.  The preregistered grid is `THETAS`; these extra
#: thresholds are computed AFTER the fact to answer "could ANY threshold on this
#: policy have paid?" and are never eligible for selection or for a verdict.
THETA_SWEEP = (0.55, 0.60, 0.65, 0.70, 0.75)
#: a column enters the fit only if its own TRAINING window can fit it
#: (`distill_model.feature_columns`' rule, unchanged)
MIN_FINITE = 20

MODELS = ("gbt", "l1")
STATE_RULES = tuple(f"state[{model}]@{theta:.2f}"
                    for model in MODELS for theta in THETAS)
REF_RULES = ee.RULES                       # rung 1's six + its oracle ceiling
ALL_RULES = tuple(REF_RULES) + STATE_RULES

META_COLUMNS = ("session", "block", "id", "second", "side", "cert", "winner",
                "offset_min", "t_second", "pos", "limit_pos", "unreal",
                "remaining", "y")


# ==========================================================================
# 1 — the trajectory dataset
# ==========================================================================

def candidate_table() -> pd.DataFrame:
    """Every roster candidate of every era block (the era ladder's own matrix)."""
    frame = pd.read_csv(MATRIX, sep="\t", low_memory=False,
                        usecols=["session", "block", "id", "second", "side",
                                 "cert", "winner"])
    return frame.sort_values(["session", "second", "side"]).reset_index(drop=True)


def _rate(cum: dict, key: str, start: int, stop: int) -> float:
    """model_v2 T1.4's per-second rate over a strictly prior window."""
    value = dm.window(cum[key], start, stop)
    return value / max(stop - start, 1) if np.isfinite(value) else np.nan


def _joint(streams: list, threshold: float) -> float:
    """model_v3's JOINT z-magnitude agreement statistic, transcribed for one row."""
    stack = np.array(streams, dtype=float)
    if not np.all(np.isfinite(stack)):
        return 0.0
    signs = np.sign(stack)
    magnitude = float(np.min(np.abs(stack)))
    agree = (np.all(signs > 0) or np.all(signs < 0)) and magnitude >= threshold
    return float(np.sign(stack[0]) * magnitude) if agree else 0.0


def _rv_bps(mid: np.ndarray, stop: int, width: int) -> float:
    """Realised vol of the 1s mid over [stop-width, stop), in bps per minute."""
    lo = max(stop - width, 0)
    piece = mid[lo:stop]
    piece = piece[np.isfinite(piece) & (piece > 0)]
    if len(piece) < 10:
        return np.nan
    step = np.diff(np.log(piece))
    if not len(step):
        return np.nan
    return float(1e4 * np.sqrt(60.0 * float(np.mean(step ** 2))))


class SessionState:
    """Everything the per-second state block reads for one session."""

    def __init__(self, ordinal: int, block: str):
        self.ordinal = ordinal
        self.session = ee.Session(ordinal, block)
        arrays = dm.second_arrays(ordinal)
        quotes = bq.quote_arrays(ordinal)
        self.cum = {key: dm.cumsum0(values) for key, values in arrays.items()}
        self.cum.update({key: dm.cumsum0(values) for key, values in quotes.items()})
        self.mid = dm.mid_series(ordinal)
        self.vol = dm.vol_series(ordinal)
        meta = P.session_meta(ordinal)
        self.atr = float(meta.get("atr14_bps") or 150.0)
        atr_ref = dm.atr_reference(ordinal)
        self.atr_rel = (self.atr / atr_ref if np.isfinite(atr_ref) and atr_ref > 0
                        else np.nan)
        self.ladder = self.session.ladder[1.00]
        self.extreme = self.session.extreme[1.00]
        #: running session high/low of the carried mid, NaN-skipping, so the
        #: "where in the day's range are we" read at second t is O(1)
        self.run_hi = np.fmax.accumulate(self.mid)
        self.run_lo = np.fmin.accumulate(self.mid)

    def vol_at(self, name: str, bucket: int) -> float:
        series = self.vol[name]
        bucket = int(np.clip(bucket, 0, len(series) - 1))
        valid = np.flatnonzero(np.isfinite(series[: bucket + 1]))
        return float(series[valid[-1]]) if len(valid) else np.nan

    def vol_z(self, name: str, bucket: int, back: int = 30) -> float:
        series = self.vol[name][max(0, bucket - back): bucket + 1]
        series = series[np.isfinite(series)]
        now = self.vol_at(name, bucket)
        if len(series) < 5 or not np.isfinite(now) or series.std(ddof=1) <= 0:
            return np.nan
        return float((now - series.mean()) / series.std(ddof=1))


def state_block(ctx: SessionState, t: int, side_sign: float) -> dict:
    """The LIVE SNIPER STATE at second t, oriented to the open position's side.

    Every window ENDS AT and EXCLUDES t (`distill_model`'s arithmetic), so the
    block is exactly what a trader holding the position could read at t.
    """
    cum, f = ctx.cum, {}

    # ---- flow (distill_model's F tier, raw signed print flow) ---------------
    sf60, z60 = dm.block_z(cum["signed"], t, 60)
    sf120, z120 = dm.block_z(cum["signed"], t, 120)
    _, z30 = dm.block_z(cum["signed"], t, 30, lookback=300)
    sf600 = dm.window(cum["signed"], t - 600, t)
    f["fl_sf60_z"] = side_sign * z60
    f["fl_sf120_z"] = side_sign * z120
    f["fl_sf30_z"] = side_sign * z30
    f["fl_sf60_o"] = side_sign * sf60
    f["fl_sf600_o"] = side_sign * sf600
    f["fl_accel_o"] = side_sign * (sf60 - (sf120 - sf60))
    f["fl_persist"] = float(np.mean(
        [1.0 if side_sign * dm.window(cum["signed"], t - (i + 1) * 60, t - i * 60) > 0
         else 0.0 for i in range(5)]))
    f["fl_sign_match"] = 1.0 if side_sign * sf60 > 0 else 0.0

    # ---- option-delta flow ("od") and the option crowd ----------------------
    dflow120, zd = dm.block_z(cum["delta_f"], t, 120)
    f["od_dflow120_o"] = side_sign * dflow120
    f["od_dflow120_z"] = side_sign * zd
    _, zg = dm.block_z(cum["gamma_f"], t, 120)
    _, zv = dm.block_z(cum["vanna_f"], t, 120)
    f["od_gamma120_z"] = side_sign * zg
    f["od_vanna120_z"] = side_sign * zv
    _, f["od_optvol_z"] = dm.block_z(cum["opt_vol"], t, 120)
    share_now = (dm.window(cum["zdte_vol"], t - 300, t)
                 / max(dm.window(cum["opt_vol"], t - 300, t), 1e-9))
    share_120 = (dm.window(cum["zdte_vol"], t - 120, t)
                 / max(dm.window(cum["opt_vol"], t - 120, t), 1e-9))
    f["od_zdte_share"] = share_now
    f["od_zdte_slope"] = share_120 - share_now

    # ---- the JOINT flow/od agreement (model_v3's statistic) -----------------
    f["j_agree2_o"] = _joint([f["fl_sf120_z"], f["od_dflow120_z"]], 3.0)
    f["j_agree2_w"] = _joint([f["fl_sf120_z"], f["od_dflow120_z"]], 2.0)
    lo = np.fmin(abs(f["fl_sf120_z"]), abs(f["od_dflow120_z"]))
    hi = np.fmax(abs(f["fl_sf120_z"]), abs(f["od_dflow120_z"]))
    f["j_z_balance"] = float(lo / hi) if np.isfinite(hi) and hi > 0 else np.nan
    f["j_conflict"] = (1.0 if (np.isfinite(f["fl_sf120_z"])
                               and np.isfinite(f["od_dflow120_z"])
                               and np.sign(f["fl_sf120_z"]) != np.sign(f["od_dflow120_z"])
                               and min(abs(f["fl_sf120_z"]),
                                       abs(f["od_dflow120_z"])) >= 2.0) else 0.0)

    # ---- urgency composition (distill_model's U tier) -----------------------
    urg, urg_z = dm.ratio_z(cum["touch"], cum["prints"], t, 120)
    _, thr_z = dm.block_z(cum["through"], t, 120)
    _, rate_z = dm.block_z(cum["prints"], t, 120)
    f["u_urg120"] = urg
    f["u_urg120_z"] = urg_z
    f["u_through120_z"] = thr_z
    f["u_printrate_z"] = rate_z

    # ---- quote churn + book erosion (model_v2's T1.4, transcribed) ----------
    qps_hot = _rate(cum, "q_n", t - 120, t)
    qps_base = _rate(cum, "q_n", t - 720, t - 120)
    f["q_qps_hot"] = qps_hot
    f["q_qps_acc"] = qps_hot / qps_base if np.isfinite(qps_base) and qps_base > 0 else np.nan
    f["q_qps_accel"] = _rate(cum, "q_n", t - 60, t) - _rate(cum, "q_n", t - 120, t - 60)
    _, f["q_qps_z"] = dm.block_z(cum["q_n"], t, 120)
    spread_hot = (dm.window(cum["q_spread"], t - 120, t)
                  / max(dm.window(cum["q_spr_n"], t - 120, t), 1e-9))
    spread_base = (dm.window(cum["q_spread"], t - 720, t - 120)
                   / max(dm.window(cum["q_spr_n"], t - 720, t - 120), 1e-9))
    f["q_spread_hot"] = spread_hot
    f["q_spread_acc"] = (spread_hot / spread_base
                         if np.isfinite(spread_base) and spread_base > 0 else np.nan)

    def imbalance(start: int, stop: int) -> float:
        bid = dm.window(cum["q_bid_sh"], start, stop)
        ask = dm.window(cum["q_ask_sh"], start, stop)
        total = bid + ask
        return (bid - ask) / total if np.isfinite(total) and total > 0 else np.nan

    imb_hot, imb_base = imbalance(t - 120, t), imbalance(t - 720, t - 120)
    f["q_qimb_o"] = side_sign * imb_hot
    f["q_qimb_trend_o"] = side_sign * (imb_hot - imb_base)
    own, opp = ("q_bid", "q_ask") if side_sign > 0 else ("q_ask", "q_bid")
    for label, stem in (("own", own), ("opp", opp)):
        erode_hot = _rate(cum, f"{stem}_erode", t - 120, t)
        erode_base = _rate(cum, f"{stem}_erode", t - 720, t - 120)
        refill_hot = _rate(cum, f"{stem}_refill", t - 120, t)
        f[f"q_{label}_erode"] = erode_hot
        f[f"q_{label}_erode_acc"] = (erode_hot / erode_base
                                     if np.isfinite(erode_base) and erode_base > 0
                                     else np.nan)
        f[f"q_{label}_refill_ratio"] = (refill_hot / erode_hot
                                        if np.isfinite(erode_hot) and erode_hot > 0
                                        else np.nan)
    f["q_erosion_tilt"] = (f["q_opp_erode"] - f["q_own_erode"]
                           if np.isfinite(f["q_opp_erode"]) and np.isfinite(f["q_own_erode"])
                           else np.nan)
    drift = (_rate(cum, "q_bid_up", t - 120, t) + _rate(cum, "q_ask_up", t - 120, t)
             - _rate(cum, "q_bid_dn", t - 120, t) - _rate(cum, "q_ask_dn", t - 120, t))
    f["q_press_o"] = side_sign * drift

    # ---- book imbalance TREND, from the prints' attached sizes (D tier) -----
    depth, depth_z = dm.ratio_z(cum["depth"], cum["depth_n"], t, 60)
    f["d_depth60"] = depth
    f["d_depth60_z"] = depth_z
    bid60, ask60 = dm.window(cum["bidsh"], t - 60, t), dm.window(cum["asksh"], t - 60, t)
    total60 = bid60 + ask60
    imb60 = (bid60 - ask60) / total60 if np.isfinite(total60) and total60 > 0 else np.nan
    bid600, ask600 = (dm.window(cum["bidsh"], t - 660, t - 60),
                      dm.window(cum["asksh"], t - 660, t - 60))
    total600 = bid600 + ask600
    imb600 = ((bid600 - ask600) / total600
              if np.isfinite(total600) and total600 > 0 else np.nan)
    f["d_imb60_o"] = side_sign * imb60
    f["d_imb_delta_o"] = side_sign * (imb60 - imb600)

    # ---- vol trajectory: PROXY_VOL level / slope / asymmetry ----------------
    vm = max(min(t // 60, P.MINUTE_BUCKETS - 1) - 1, 0)
    pv_mid = ctx.vol_at("proxy_vol_mid_near", vm)
    pv_bid, pv_ask = (ctx.vol_at("proxy_vol_bid_near", vm),
                      ctx.vol_at("proxy_vol_ask_near", vm))
    prev = max(vm - 10, 0)
    prev_mid = ctx.vol_at("proxy_vol_mid_near", prev)
    prev_bid, prev_ask = (ctx.vol_at("proxy_vol_bid_near", prev),
                          ctx.vol_at("proxy_vol_ask_near", prev))
    asym = (pv_ask - pv_bid) / pv_mid if np.isfinite(pv_mid) and pv_mid > 0 else np.nan
    prev_asym = ((prev_ask - prev_bid) / prev_mid
                 if np.isfinite(prev_mid) and prev_mid > 0 else np.nan)
    f["v_pv_level"] = pv_mid
    f["v_pv_dlog10"] = (float(np.log(pv_mid / prev_mid))
                        if np.isfinite(pv_mid) and np.isfinite(prev_mid)
                        and pv_mid > 0 and prev_mid > 0 else np.nan)
    f["v_pv_asym"] = asym
    f["v_pv_asym_z"] = asym - prev_asym
    f["v_pv_bid_z"] = ctx.vol_z("proxy_vol_bid_near", vm)
    f["v_pv_ask_z"] = ctx.vol_z("proxy_vol_ask_near", vm)
    f["v_width_z"] = ctx.vol_z("width_bps_near", vm)

    # ---- realised-vol trajectory (instantaneous against the session) --------
    rv60, rv600 = _rv_bps(ctx.mid, t, 60), _rv_bps(ctx.mid, t, 600)
    f["v_rv60_bps"] = rv60
    f["v_rv600_bps"] = rv600
    f["v_rv_ratio"] = rv60 / rv600 if np.isfinite(rv600) and rv600 > 0 else np.nan
    return f


def trajectory_rows(ctx: SessionState, cand: dict, fvol: dict) -> list:
    """Every sampled post-entry state of ONE candidate, with its target."""
    session = ctx.session
    side = cand["side"]
    side_sign = 1.0 if side == "L" else -1.0
    entry_second = int(cand["second"])
    start = session.position(entry_second)
    entry_u6 = int(session.mid[start])
    nets = ee.net_cent(entry_u6, session.mid, side)

    #: the wall, exactly as rung 1 monitors it — marks STRICTLY after entry,
    #: filling at the NEXT lawful mark after the crossing (gap-through kept)
    forward = np.flatnonzero(nets[start + 1:] <= ee.WALL_NET_CENT)
    wall_fill = (min(int(forward[0]) + start + 2, session.close_pos)
                 if forward.size else None)
    limit = wall_fill if wall_fill is not None else session.close_pos
    if limit <= start:
        return []

    span = nets[start + 1: limit + 1]
    run_max = np.maximum.accumulate(span)                  # MFE so far
    run_min = np.minimum.accumulate(span)                  # MAE so far
    best_after = np.maximum.accumulate(span[::-1])[::-1]   # best mark from here on
    arg_max = np.maximum.accumulate(np.where(span == run_max,
                                             np.arange(len(span)), 0))

    entry_pivot = session.entry_pivot_second(1.00, side, entry_second)
    entry_pivot_px = (float(session.mid[session.position(entry_pivot)])
                      if entry_pivot is not None else np.nan)
    against_kind = "H" if side == "L" else "L"
    for_kind = "L" if side == "L" else "H"
    against = ctx.ladder[against_kind]
    favour = ctx.ladder[for_kind]

    rows = []
    for offset in OFFSETS:
        t = entry_second + offset * 60
        pos = session.position(t)
        #: the sample exists only while the position is still open: strictly
        #: after the entry mark and strictly before the wall fill / the close
        if pos <= start or pos >= limit or int(session.second[pos]) > t:
            continue
        index = pos - (start + 1)
        unreal = float(nets[pos]) / 100.0
        mfe = float(run_max[index]) / 100.0
        mae = float(run_min[index]) / 100.0
        remaining = float(best_after[min(index + 1, len(span) - 1)] - nets[pos]) / 100.0
        best_second = int(session.second[start + 1 + int(arg_max[index])])
        best_px = float(session.mid[start + 1 + int(arg_max[index])])
        now_px = float(session.mid[pos])

        row = {
            "session": ctx.ordinal, "block": cand["block"], "id": cand["id"],
            "second": entry_second, "side": side, "cert": float(cand["cert"]),
            "winner": int(cand["winner"]), "offset_min": offset,
            "t_second": int(session.second[pos]), "pos": pos, "limit_pos": limit,
            "unreal": unreal, "remaining": remaining,
            "y": int(remaining >= REMAIN_DOLLARS),
        }

        # ---- position / path ------------------------------------------------
        #: $10 on the $100,000 object is 1 bp, so dollars/10 is the move in bps
        t_now = int(session.second[pos])
        row["p_age_min"] = float(offset)
        row["p_unreal"] = unreal
        row["p_unreal_atr"] = unreal / 10.0 / ctx.atr if ctx.atr > 0 else np.nan
        row["p_mfe"] = mfe
        row["p_mae"] = mae
        row["p_mfe_atr"] = mfe / 10.0 / ctx.atr if ctx.atr > 0 else np.nan
        row["p_mae_atr"] = mae / 10.0 / ctx.atr if ctx.atr > 0 else np.nan
        row["p_giveback_frac"] = (1.0 - unreal / mfe) if mfe > 0 else np.nan
        row["p_wall_dist"] = unreal - (ee.WALL_NET_CENT / 100.0)
        row["p_runway_min"] = (int(session.second[session.close_pos]) - t_now) / 60.0
        row["p_since_mfe_min"] = (t_now - best_second) / 60.0
        row["p_mfe_age_frac"] = ((best_second - entry_second)
                                 / max(t_now - entry_second, 1))
        prior = max(session.position(t_now - 300), start)
        row["p_vel5"] = unreal - float(nets[prior]) / 100.0
        travel = float(np.abs(np.diff(session.mid[start:pos + 1])).sum())
        row["p_path_eff"] = ((now_px - float(session.mid[start])) * side_sign / travel
                             if travel > 0 else np.nan)

        # ---- structure: pivots since entry, penetration depth ---------------
        n_against = int(np.searchsorted(against, t_now, "right")
                        - np.searchsorted(against, entry_second, "right"))
        n_for = int(np.searchsorted(favour, t_now, "right")
                    - np.searchsorted(favour, entry_second, "right"))
        row["s_piv_against"] = float(n_against)
        row["s_piv_for"] = float(n_for)
        last_against = (against[np.searchsorted(against, t_now, "right") - 1]
                        if np.searchsorted(against, t_now, "right") > 0 else np.nan)
        last_for = (favour[np.searchsorted(favour, t_now, "right") - 1]
                    if np.searchsorted(favour, t_now, "right") > 0 else np.nan)
        row["s_since_against_min"] = ((t_now - last_against) / 60.0
                                      if np.isfinite(last_against) else np.nan)
        row["s_since_for_min"] = ((t_now - last_for) / 60.0
                                  if np.isfinite(last_for) else np.nan)
        row["s_pen_entry_atr"] = (side_sign * (now_px - entry_pivot_px) * 1e4
                                  / entry_pivot_px / ctx.atr
                                  if np.isfinite(entry_pivot_px) and entry_pivot_px > 0
                                  and ctx.atr > 0 else np.nan)
        row["s_pen_best_atr"] = (side_sign * (now_px - best_px) * 1e4 / best_px / ctx.atr
                                 if best_px > 0 and ctx.atr > 0 else np.nan)
        hi = float(ctx.run_hi[min(t_now - 1, len(ctx.run_hi) - 1)])
        lo = float(ctx.run_lo[min(t_now - 1, len(ctx.run_lo) - 1)])
        if np.isfinite(hi) and np.isfinite(lo) and hi > lo and now_px > 0:
            row["s_range_atr"] = ((hi - lo) * 1e4 / (now_px / 1e6) / ctx.atr
                                  if ctx.atr > 0 else np.nan)
            row["s_range_pos"] = (now_px / 1e6 - lo) / (hi - lo)
        else:
            row["s_range_atr"] = row["s_range_pos"] = np.nan

        # ---- regime / clock -------------------------------------------------
        row["r_atr_rel"] = ctx.atr_rel
        row["r_side"] = side_sign
        row["r_entry_min"] = entry_second / 60.0
        row["r_late"] = 1.0 if t_now >= 15600 else 0.0

        row.update(state_block(ctx, t_now, side_sign))
        row.update(fvol.get(f"{cand['id']}@{offset}", {}))
        rows.append(row)
    return rows


#: the fvol lane's vol-trajectory channels (sigma_inst vs sigma_now and the
#: session's consumed/remaining move).  D-020's retirement note retired the M_
#: block as ENTRY-selector features; the brief names sigma_inst vs sigma_now as
#: a required EXIT state channel, so it is carried here and its importance is
#: reported like any other family.
FVOL_KEEP = ("M_sigma_inst_bps", "M_sigma_now_bps", "M_sigma_inst_over_now",
             "M_sigma_inst_rel", "M_hot", "M_rv_sofar_bps",
             "M_var_fraction_expected", "M_move_consumed_fraction",
             "M_range_consumed_fraction", "M_remaining_move_bps",
             "M_band_z_own", "M_move_z_own", "M_traveled_bps_own", "M_extension")


def build_session(job: tuple) -> int:
    """One session's trajectory shard.  Idempotent; worker-safe."""
    ordinal, block, cands = job
    out = TRAJDIR / f"s{ordinal}.tsv"
    if out.exists():
        return 0
    P.assert_case_wall(ordinal, "exit_state_model")
    ctx = SessionState(ordinal, block)
    #: the fvol minute rows for every sampled second, in one pass
    pseudo = [{"id": f"{c['id']}@{off}", "second": int(c["second"]) + off * 60,
               "side": c["side"]}
              for c in cands for off in OFFSETS]
    raw = wf.fvol_features(ordinal, pseudo)
    fvol = {key: {name: value for name, value in block_.items() if name in FVOL_KEEP}
            for key, block_ in raw.items()}
    rows = []
    for cand in cands:
        rows.extend(trajectory_rows(ctx, cand, fvol))
    TRAJDIR.mkdir(parents=True, exist_ok=True)
    scratch = out.with_suffix(f".{os.getpid()}.tmp")
    #: a session may legitimately produce no sampled state at all (every
    #: candidate walled or closed inside the first minute); the shard is still
    #: written, with a header only, so the stage stays idempotent
    frame = pd.DataFrame(rows) if rows else pd.DataFrame(columns=list(META_COLUMNS))
    frame.to_csv(scratch, sep="\t", index=False, float_format="%.6g")
    os.replace(scratch, out)
    return len(rows)


def stage_traj(jobs_n: int, rebuild: bool) -> None:
    table = candidate_table()
    if rebuild and TRAJDIR.exists():
        for path in TRAJDIR.glob("s*.tsv"):
            path.unlink()
    jobs = [(int(ordinal), part["block"].iloc[0], part.to_dict("records"))
            for ordinal, part in table.groupby("session", sort=True)]
    print(f"trajectories: {len(jobs)} sessions, {len(table)} candidates, "
          f"{len(OFFSETS)} offsets, {jobs_n} workers", flush=True)
    TRAJDIR.mkdir(parents=True, exist_ok=True)
    total = 0
    if jobs_n <= 1:
        for done, job in enumerate(jobs, 1):
            total += build_session(job)
            if done % 25 == 0 or done == len(jobs):
                print(f"  {done}/{len(jobs)} sessions, {total} new rows", flush=True)
    else:
        import multiprocessing as multi
        with multi.get_context("fork").Pool(jobs_n) as pool:
            for done, count in enumerate(pool.imap_unordered(build_session, jobs), 1):
                total += count
                if done % 25 == 0 or done == len(jobs):
                    print(f"  {done}/{len(jobs)} sessions, {total} new rows", flush=True)


def load_traj() -> pd.DataFrame:
    parts = []
    for path in sorted(TRAJDIR.glob("s*.tsv")):
        frame = pd.read_csv(path, sep="\t")
        if len(frame):
            parts.append(frame)
    frame = pd.concat(parts, ignore_index=True)
    return frame.sort_values(["session", "second", "id", "offset_min"]).reset_index(drop=True)


# ==========================================================================
# 2 — the model: a small HistGBT and its L1 twin
# ==========================================================================

def feature_columns(frame: pd.DataFrame, train: pd.DataFrame) -> list:
    """Usable columns, decided on the TRAINING window only.

    `distill_model.feature_columns`' rule, unchanged: a column is usable if its
    own training window carries at least `MIN_FINITE` finite values and at least
    two distinct ones.  A partly-absent family (the fvol lane starts at session
    251) is therefore KEPT as a typed absence rather than deleted — the GBT
    splits on NaN natively.
    """
    columns = [c for c in frame.columns if c not in META_COLUMNS]
    keep = []
    for name in columns:
        values = pd.to_numeric(train[name], errors="coerce").to_numpy(float)
        values = values[np.isfinite(values)]
        if len(values) >= MIN_FINITE and len(np.unique(values)) >= 2:
            keep.append(name)
    return keep


def fit_gbt(train: pd.DataFrame, columns: list, config: dict,
            labels: np.ndarray | None = None):
    from sklearn.ensemble import HistGradientBoostingClassifier
    model = HistGradientBoostingClassifier(random_state=SEED, **config)
    y = train["y"].to_numpy() if labels is None else labels
    model.fit(train[columns].to_numpy(float), y)
    return model


def fit_l1(train: pd.DataFrame, columns: list, C: float,
           labels: np.ndarray | None = None):
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    #: sklearn 1.9 states the penalty as `l1_ratio`; 1.0 IS the L1 penalty
    #: (verified against liblinear and saga: identical sparse solutions).
    #: The GBT reads NaN natively; the linear twin cannot, so a typed-absent
    #: channel is median-filled here — which is why a family that is absent for
    #: part of a training window reads weaker in the twin than in the GBT.
    model = Pipeline([("impute", SimpleImputer(strategy="median")),
                      ("scale", StandardScaler()),
                      ("fit", LogisticRegression(l1_ratio=1.0, solver="liblinear",
                                                 C=C, max_iter=2000,
                                                 random_state=SEED))])
    y = train["y"].to_numpy() if labels is None else labels
    model.fit(train[columns].to_numpy(float), y)
    return model


def choose_hypers(traj: pd.DataFrame) -> dict:
    """Session-grouped CV inside the STUDY window only, then FROZEN forever."""
    if HYPERS.exists():
        record = json.loads(HYPERS.read_text())
        print(f"hyper-parameters <- {HYPERS}: {record['gbt']} / L1 C={record['l1_C']}",
              flush=True)
        return record
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import GroupKFold
    study = traj[traj["session"] <= STUDY_HI].reset_index(drop=True)
    columns = feature_columns(traj, study)
    groups = study["session"].to_numpy()
    folds = list(GroupKFold(n_splits=CV_FOLDS).split(study, study["y"], groups))
    print(f"hyper-parameter CV on the study window 125..{STUDY_HI}: "
          f"{len(study)} rows, {study['session'].nunique()} sessions, "
          f"{len(columns)} columns", flush=True)

    def cv_auc(builder) -> float:
        scores = []
        for train_index, test_index in folds:
            train, test = study.iloc[train_index], study.iloc[test_index]
            if test["y"].nunique() < 2:
                continue
            model = builder(train, columns)
            probability = model.predict_proba(test[columns].to_numpy(float))[:, 1]
            scores.append(roc_auc_score(test["y"], probability))
        return float(np.mean(scores)) if scores else np.nan

    gbt_scores = []
    for config in GBT_GRID:
        auc = cv_auc(lambda tr, cols, c=config: fit_gbt(tr, cols, c))
        gbt_scores.append((auc, config))
        print(f"  gbt {config} -> CV AUC {auc:.4f}", flush=True)
    l1_scores = []
    for C in L1_GRID:
        auc = cv_auc(lambda tr, cols, c=C: fit_l1(tr, cols, c))
        l1_scores.append((auc, C))
        print(f"  l1  C={C} -> CV AUC {auc:.4f}", flush=True)
    best_gbt = max(gbt_scores, key=lambda pair: pair[0])
    best_l1 = max(l1_scores, key=lambda pair: pair[0])
    record = {"gbt": best_gbt[1], "gbt_cv_auc": best_gbt[0],
              "l1_C": best_l1[1], "l1_cv_auc": best_l1[0],
              "study_hi": STUDY_HI, "folds": CV_FOLDS,
              "gbt_grid": GBT_GRID, "l1_grid": L1_GRID,
              "n_rows": int(len(study)), "n_columns": len(columns)}
    OUTDIR.mkdir(parents=True, exist_ok=True)
    HYPERS.write_text(json.dumps(record, indent=1))
    return record


def stage_fit(traj: pd.DataFrame, hypers: dict) -> tuple:
    """Per-segment walk-forward fits; returns (probabilities, fit diagnostics)."""
    from sklearn.metrics import roc_auc_score
    probabilities, diagnostics, coefficients = [], [], []
    rng = np.random.default_rng(SEED)
    for seg, block in SEGMENTS:
        test = traj[traj["block"] == block].reset_index(drop=True)
        train = traj[traj["session"] < int(test["session"].min())].reset_index(drop=True)
        assert train["session"].max() < test["session"].min(), "walk-forward purity"
        columns = feature_columns(traj, train)
        print(f"segment {seg} ({block}): train {len(train)} rows "
              f"({int(train['session'].min())}..{int(train['session'].max())}), "
              f"test {len(test)} rows, {len(columns)} columns, "
              f"base rate {train['y'].mean():.3f} -> {test['y'].mean():.3f}", flush=True)
        gbt = fit_gbt(train, columns, hypers["gbt"])
        l1 = fit_l1(train, columns, hypers["l1_C"])
        matrix = test[columns].to_numpy(float)
        p_gbt = gbt.predict_proba(matrix)[:, 1]
        p_l1 = l1.predict_proba(matrix)[:, 1]
        out = test[["session", "id", "offset_min"]].copy()
        out["segment"] = seg
        out["p_gbt"] = p_gbt
        out["p_l1"] = p_l1
        #: the shuffle control — the identical fit on permuted targets
        for draw in range(SHUFFLE_DRAWS):
            labels = rng.permutation(train["y"].to_numpy())
            shuffled = fit_gbt(train, columns, hypers["gbt"], labels=labels)
            out[f"p_shuf{draw}"] = shuffled.predict_proba(matrix)[:, 1]
        probabilities.append(out)
        row = {"segment": seg, "block": block, "era_label": er.ERA_LABEL[block],
               "train_rows": len(train), "test_rows": len(test),
               "columns": len(columns),
               "train_base_rate": float(train["y"].mean()),
               "test_base_rate": float(test["y"].mean()),
               "auc_gbt": float(roc_auc_score(test["y"], p_gbt)),
               "auc_l1": float(roc_auc_score(test["y"], p_l1))}
        for draw in range(SHUFFLE_DRAWS):
            row[f"auc_shuf{draw}"] = float(roc_auc_score(test["y"],
                                                        out[f"p_shuf{draw}"]))
        diagnostics.append(row)
        print(f"   AUC gbt {row['auc_gbt']:.4f} | l1 {row['auc_l1']:.4f} | "
              f"shuffled {np.mean([row[f'auc_shuf{d}'] for d in range(SHUFFLE_DRAWS)]):.4f}",
              flush=True)
        #: the L1 twin's standardised coefficients — the sparse read of WHAT the
        #: exit decision is made of
        weights = l1.named_steps["fit"].coef_[0]
        for name, weight in zip(columns, weights):
            coefficients.append({"segment": seg, "block": block, "feature": name,
                                 "coef": float(weight)})
    return (pd.concat(probabilities, ignore_index=True),
            pd.DataFrame(diagnostics), pd.DataFrame(coefficients))


def importances(traj: pd.DataFrame, hypers: dict, segment: str = "i") -> pd.DataFrame:
    """Permutation importance of the frozen GBT on the last segment's test era."""
    from sklearn.inspection import permutation_importance
    block = dict(SEGMENTS)[segment]
    test = traj[traj["block"] == block].reset_index(drop=True)
    train = traj[traj["session"] < int(test["session"].min())].reset_index(drop=True)
    columns = feature_columns(traj, train)
    model = fit_gbt(train, columns, hypers["gbt"])
    sample = test.sample(n=min(40_000, len(test)), random_state=SEED)
    result = permutation_importance(model, sample[columns].to_numpy(float),
                                    sample["y"].to_numpy(), scoring="roc_auc",
                                    n_repeats=3, random_state=SEED, n_jobs=8)
    return (pd.DataFrame({"feature": columns,
                          "importance": result.importances_mean,
                          "sd": result.importances_std})
            .sort_values("importance", ascending=False).reset_index(drop=True))


# ==========================================================================
# 3 — the replay
# ==========================================================================

def replay_state_trade(session: ee.Session, second: int, side: str,
                       probs: dict, theta: float) -> dict:
    """Hold while P(remaining >= $150) >= theta; exit on the first drop below."""
    start = session.position(second)
    entry_u6 = int(session.mid[start])
    nets = ee.net_cent(entry_u6, session.mid, side)
    forward = np.flatnonzero(nets[start + 1:] <= ee.WALL_NET_CENT)
    wall_fill = (min(int(forward[0]) + start + 2, session.close_pos)
                 if forward.size else None)
    limit = wall_fill if wall_fill is not None else session.close_pos

    exit_pos = limit
    for offset in OFFSETS:
        probability = probs.get(offset)
        if probability is None:
            continue
        pos = session.position(second + offset * 60)
        if pos <= start or pos >= limit:
            continue
        if probability < theta:
            exit_pos = pos
            break
    stopped = wall_fill is not None and exit_pos == wall_fill
    return {"exit_second": int(session.second[exit_pos]),
            "pnl": float(nets[exit_pos]) / 100.0,
            "stopped": bool(stopped),
            "hold_s": int(session.second[exit_pos]) - int(session.second[start])}


def replay_day(trades: dict, picks: list, slots: int) -> tuple:
    """(day dollars, taken trades) with at most `slots` concurrent positions."""
    total, taken, open_until = 0.0, [], []
    for pick in sorted(picks, key=lambda row: (row["second"], row["id"])):
        open_until = [stop for stop in open_until if stop > pick["second"]]
        if len(open_until) >= slots:
            continue
        trade = trades[pick["id"]]
        total += trade["pnl"]
        taken.append(dict(trade, cert=pick["cert"]))
        open_until.append(trade["exit_second"])
    return total, taken


def stage_replay(probabilities: pd.DataFrame) -> pd.DataFrame:
    picks = pd.read_csv(PICKS, sep="\t")
    lookup: dict = {}
    for row in probabilities.to_dict("records"):
        key = (int(row["session"]), row["id"])
        for model in MODELS:
            lookup.setdefault((key, model), {})[int(row["offset_min"])] = row[f"p_{model}"]
        for draw in range(SHUFFLE_DRAWS):
            lookup.setdefault((key, f"shuf{draw}"), {})[int(row["offset_min"])] = \
                row[f"p_shuf{draw}"]

    shuffle_rules = tuple(f"shuffle{draw}@{SHUFFLE_THETA:.2f}"
                          for draw in range(SHUFFLE_DRAWS))
    sweep_rules = tuple(f"sweep[gbt]@{theta:.2f}" for theta in THETA_SWEEP)
    rules = tuple(ALL_RULES) + shuffle_rules + sweep_rules
    results = []
    for seg, block in SEGMENTS:
        part = picks[picks["segment"] == seg]
        sessions = sorted(part["session"].unique())
        ratchet_arm = float(part["ratchet_arm"].iloc[0])
        books = {(arm, k): {} for arm in ARMS for k in KS}
        for row in part.to_dict("records"):
            books[(row["arm"], row["k"])].setdefault(row["session"], []).append(row)
        acc = {(arm, k, rule, slots): ([], [])
               for arm in ARMS for k in KS for rule in rules for slots in OCCUPANCIES}
        picked = {(arm, k): [] for arm in ARMS for k in KS}

        print(f"segment {seg} ({block}): {len(sessions)} sessions", flush=True)
        for done, ordinal in enumerate(sessions, 1):
            session = ee.Session(int(ordinal), block)
            wanted = {row["id"]: row for row in part[part["session"] == ordinal]
                      .to_dict("records")}
            trades = {rule: {cid: ee.replay_trade(session, row["second"], row["side"],
                                                  rule, ratchet_arm)
                             for cid, row in wanted.items()}
                      for rule in REF_RULES}
            for model in MODELS:
                for theta in THETAS:
                    trades[f"state[{model}]@{theta:.2f}"] = {
                        cid: replay_state_trade(
                            session, row["second"], row["side"],
                            lookup.get(((int(ordinal), cid), model), {}), theta)
                        for cid, row in wanted.items()}
            for theta in THETA_SWEEP:
                trades[f"sweep[gbt]@{theta:.2f}"] = {
                    cid: replay_state_trade(
                        session, row["second"], row["side"],
                        lookup.get(((int(ordinal), cid), "gbt"), {}), theta)
                    for cid, row in wanted.items()}
            for draw in range(SHUFFLE_DRAWS):
                trades[f"shuffle{draw}@{SHUFFLE_THETA:.2f}"] = {
                    cid: replay_state_trade(
                        session, row["second"], row["side"],
                        lookup.get(((int(ordinal), cid), f"shuf{draw}"), {}),
                        SHUFFLE_THETA)
                    for cid, row in wanted.items()}
            for arm in ARMS:
                for k in KS:
                    day_picks = books[(arm, k)].get(ordinal, [])
                    picked[(arm, k)].append(sum(p["cert"] for p in day_picks))
                    for rule in rules:
                        for slots in OCCUPANCIES:
                            total, taken = replay_day(trades[rule], day_picks, slots)
                            acc[(arm, k, rule, slots)][0].append(total)
                            acc[(arm, k, rule, slots)][1].extend(taken)
            if done % 25 == 0 or done == len(sessions):
                print(f"  {done}/{len(sessions)} sessions", flush=True)

        for arm in ARMS:
            for k in KS:
                picked_day = float(np.mean(picked[(arm, k)]))
                for rule in rules:
                    for slots in OCCUPANCIES:
                        days, trades_list = acc[(arm, k, rule, slots)]
                        results.append({
                            "segment": seg, "block": block,
                            "era_label": er.ERA_LABEL[block], "arm": arm, "k": k,
                            "rule": rule, "slots": slots,
                            **ee.summarise(days, trades_list, picked_day)})
    return pd.DataFrame(results)


def attainability(traj: pd.DataFrame, probabilities: pd.DataFrame) -> pd.DataFrame:
    """Is the model's skill ATTAINABLE?  Three forward quantities per state.

    `remaining` is the trained target: the best mark still to come before the
    wall/close, minus the mark in hand — a MAXIMUM, and a maximum is not an
    exit.  `to_limit` is what actually happens if the position is simply held
    to the wall/close.  `grid_gain` is the best mark reachable at a LATER
    decision minute of this policy's own grid (terminal included), minus the
    mark in hand — the ceiling any minute-grid exit could ever reach from here.
    Grouped by decile of the model's own probability: if the model's ordering
    of `remaining` does not carry into `to_limit`, the exit cannot convert it.
    """
    columns = ["session", "block", "id", "second", "side", "offset_min",
               "limit_pos", "unreal", "remaining", "y"]
    test = traj[traj["block"].isin([block for _, block in SEGMENTS])][columns]
    merged = (test.merge(probabilities[["session", "id", "offset_min", "p_gbt"]],
                         on=["session", "id", "offset_min"], how="inner")
              .sort_values(["session", "id", "offset_min"]))
    rows = []
    for (ordinal, block), day in merged.groupby(["session", "block"], sort=True):
        session = ee.Session(int(ordinal), block)
        for _, trade in day.groupby("id", sort=True):
            head = trade.iloc[0]
            start = session.position(int(head["second"]))
            nets = ee.net_cent(int(session.mid[start]), session.mid, head["side"]) / 100.0
            terminal = float(nets[int(head["limit_pos"])])
            unreal = trade["unreal"].to_numpy(float)
            #: best mark reachable from a strictly LATER decision on the grid
            best_later, run = np.empty(len(unreal)), terminal
            for i in range(len(unreal) - 1, -1, -1):
                best_later[i] = run
                run = max(run, unreal[i])
            for i, probability in enumerate(trade["p_gbt"].to_numpy(float)):
                rows.append({"p": probability, "unreal": unreal[i],
                             "y": int(trade["y"].iloc[i]),
                             "remaining": float(trade["remaining"].iloc[i]),
                             "to_limit": terminal - unreal[i],
                             "grid_gain": best_later[i] - unreal[i]})
    frame = pd.DataFrame(rows)
    frame["decile"] = pd.qcut(frame["p"], 10, labels=False)
    table = frame.groupby("decile").agg(
        n=("p", "size"), p_mean=("p", "mean"), y_mean=("y", "mean"),
        unreal=("unreal", "mean"),
        remaining=("remaining", "mean"), to_limit=("to_limit", "mean"),
        to_limit_median=("to_limit", "median"),
        to_limit_positive=("to_limit", lambda x: float((x > 0).mean())),
        grid_gain=("grid_gain", "mean"),
        grid_gain_median=("grid_gain", "median")).reset_index()
    return table


# ==========================================================================
# 4 — the report
# ==========================================================================

money, number = ee.money, ee.number


def exit_contrast(traj: pd.DataFrame, probabilities: pd.DataFrame,
                  theta: float = 0.40) -> pd.DataFrame:
    """What the state looks like AT an exit call against a hold call.

    Robust standardisation is over the era's own sampled states, so the columns
    are comparable; this is a read-only description of the fitted policy, never
    an input to it.
    """
    merged = traj.merge(probabilities, on=["session", "id", "offset_min"], how="inner")
    columns = [c for c in traj.columns if c not in META_COLUMNS]
    exit_mask = merged["p_gbt"] < theta
    rows = []
    for name in columns:
        values = pd.to_numeric(merged[name], errors="coerce").to_numpy(float)
        finite = np.isfinite(values)
        if finite.sum() < 100:
            continue
        scale = np.nanstd(values[finite])
        if not np.isfinite(scale) or scale <= 0:
            continue
        centre = np.nanmedian(values[finite])
        at_exit = values[exit_mask.to_numpy() & finite]
        at_hold = values[(~exit_mask).to_numpy() & finite]
        if not len(at_exit) or not len(at_hold):
            continue
        rows.append({"feature": name,
                     "exit_mean_z": float((at_exit.mean() - centre) / scale),
                     "hold_mean_z": float((at_hold.mean() - centre) / scale),
                     "gap_z": float((at_exit.mean() - at_hold.mean()) / scale)})
    frame = pd.DataFrame(rows)
    return frame.reindex(frame["gap_z"].abs().sort_values(ascending=False).index) \
                .reset_index(drop=True)


def write_report(frame: pd.DataFrame, diagnostics: pd.DataFrame,
                 coefficients: pd.DataFrame, importance: pd.DataFrame,
                 contrast: pd.DataFrame, reach: pd.DataFrame, hypers: dict,
                 traj: pd.DataFrame) -> None:
    out = []
    out.append("# EXIT RUNG 2 — POST-ENTRY STATE MODEL\n")
    out.append("Every roster candidate of every era block is a post-entry trajectory: "
               "the state is sampled at minutes "
               f"{{{', '.join(str(o) for o in OFFSETS)}}} after the decision second "
               "while the position is still open, and the target is whether >= "
               f"${REMAIN_DOLLARS:,.0f} of value REMAINS after that second (best mark "
               "from there to the wall/close, minus the mark in hand).  The policy "
               "holds while P >= theta and exits on the first drop below it, the "
               "$300 wall, or the close.  Replay is rung 1's machinery — same picks, "
               "same costs, same wall — under ONE and TWO concurrent positions.\n")
    if VERDICT.exists():
        out.append("\n" + VERDICT.read_text().rstrip() + "\n")

    out.append("\n## The model\n")
    out.append(f"Hyper-parameters chosen once by {hypers['folds']}-fold "
               f"session-grouped CV inside the study window 125..{hypers['study_hi']} "
               f"({hypers['n_rows']:,} trajectory rows, {hypers['n_columns']} columns) "
               f"from the preregistered grid, then frozen for every segment: "
               f"GBT `{hypers['gbt']}` (CV AUC {hypers['gbt_cv_auc']:.4f}), "
               f"L1 twin C={hypers['l1_C']} (CV AUC {hypers['l1_cv_auc']:.4f}).\n")
    out.append("| segment | era | train rows | test rows | cols | train base | "
               "test base | AUC gbt | AUC l1 | AUC shuffled |")
    out.append("|---|---|---|---|---|---|---|---|---|---|")
    for _, row in diagnostics.iterrows():
        shuffled = np.mean([row[f"auc_shuf{d}"] for d in range(SHUFFLE_DRAWS)])
        out.append(f"| {row['segment']} | `{row['block']}` | {row['train_rows']:,} | "
                   f"{row['test_rows']:,} | {row['columns']} | "
                   f"{row['train_base_rate']:.3f} | {row['test_base_rate']:.3f} | "
                   f"**{row['auc_gbt']:.4f}** | {row['auc_l1']:.4f} | "
                   f"{shuffled:.4f} |")

    for slots in OCCUPANCIES:
        for k in KS:
            out.append(f"\n## Realised $/day — top-{k} picks, {slots} concurrent "
                       f"position{'s' if slots > 1 else ''}\n")
            out.append("`picked` is the arm's own exit-free certified sum per day; "
                       "`entered` is the certificate of the picks this occupancy "
                       "actually got into (the reachable ceiling).  Capture "
                       "percentages are of `entered` unless marked.\n")
            header = ["era", "arm", "picked", "entered", "close", "mirror@1.00",
                      "mirror@1.00+patience15"]
            header += [f"gbt@{theta:.2f}" for theta in THETAS]
            header += [f"l1@{theta:.2f}" for theta in THETAS] + ["oracle"]
            out.append("| " + " | ".join(header) + " |")
            out.append("|" + "---|" * len(header))
            for seg, block in SEGMENTS:
                for arm in ARMS:
                    part = frame[(frame["segment"] == seg) & (frame["arm"] == arm)
                                 & (frame["k"] == k) & (frame["slots"] == slots)]
                    if part.empty:
                        continue
                    cells = [f"`{block}`", arm,
                             money(part["picked_day"].iloc[0]),
                             money(part["entered_cert_day"].iloc[0])]
                    for rule in (["close", "mirror@1.00", "mirror@1.00+patience15"]
                                 + [f"state[gbt]@{theta:.2f}" for theta in THETAS]
                                 + [f"state[l1]@{theta:.2f}" for theta in THETAS]
                                 + ["oracle"]):
                        row = part[part["rule"] == rule].iloc[0]
                        cells.append(f"{money(row['realized_day'])} "
                                     f"({number(row['capture_entered_pct'], 0)}%)")
                    out.append("| " + " | ".join(cells) + " |")

    out.append("\n## The full panel — every (era, arm, k, occupancy, rule)\n")
    out.append("| era | arm | k | slots | rule | realised $/day | capture picked | "
               "capture entered | median day | worst day | loss days | trades/day | "
               "$/trade | worst trade | win rate | stop rate | mean hold |")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for _, row in frame.iterrows():
        out.append(f"| `{row['block']}` | {row['arm']} | {row['k']} | {row['slots']} | "
                   f"{row['rule']} | **{money(row['realized_day'])}** | "
                   f"{number(row['capture_pct'], 0)}% | "
                   f"{number(row['capture_entered_pct'], 0)}% | "
                   f"{money(row['median_day'])} | {money(row['worst_day'])} | "
                   f"{number(row['loss_days_pct'], 0)}% | "
                   f"{number(row['trades_day'], 1)} | {money(row['trade_mean'])} | "
                   f"{money(row['max_trade_loss'])} | {number(row['win_rate'], 0)}% | "
                   f"{number(row['stop_rate'], 0)}% | {number(row['hold_min'], 0)}min |")

    out.append("\n## WHY — is the model's skill ATTAINABLE?\n")
    out.append("Every sampled state of every test era, binned by decile of the "
               "model's own probability.  `remaining` is the trained target (the "
               "best mark still to come before the wall/close, minus the mark in "
               "hand — a MAXIMUM); `to limit` is what actually lands if the "
               "position is held to the wall/close; `grid gain` is the best mark "
               "reachable at a LATER minute of this policy's own decision grid, "
               "i.e. the ceiling on any exit decision taken from here.\n")
    out.append("| decile | n | mean P | actual base rate | unrealised | remaining | "
               "to limit | to limit (median) | to limit > 0 | grid gain | "
               "grid gain (median) |")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for _, row in reach.iterrows():
        out.append(f"| {int(row['decile']) + 1} | {int(row['n']):,} | "
                   f"{row['p_mean']:.3f} | {row['y_mean']:.3f} | "
                   f"{money(row['unreal'])} | {money(row['remaining'])} | "
                   f"{money(row['to_limit'])} | {money(row['to_limit_median'])} | "
                   f"{100 * row['to_limit_positive']:.0f}% | "
                   f"{money(row['grid_gain'])} | {money(row['grid_gain_median'])} |")

    out.append("\n## POST-HOC DIAGNOSTIC — the threshold sweep\n")
    out.append("Not a rule and not eligible for any verdict: the preregistered "
               f"grid is {THETAS} and every value of it is reported above.  This "
               "sweep exists only to answer whether ANY threshold on this policy "
               "could have paid.  Top-5 picks, mean over the five arms.\n")
    sweep_rules = [f"state[gbt]@{theta:.2f}" for theta in THETAS] + \
                  [f"sweep[gbt]@{theta:.2f}" for theta in THETA_SWEEP]
    out.append("| era | slots | " + " | ".join(rule.split("@")[1] for rule in sweep_rules)
               + " | close | best mirror |")
    out.append("|---|---|" + "---|" * (len(sweep_rules) + 2))
    for seg, block in SEGMENTS:
        for slots in OCCUPANCIES:
            part = frame[(frame["segment"] == seg) & (frame["k"] == 5)
                         & (frame["slots"] == slots)]
            cells = [money(part[part["rule"] == rule]["realized_day"].mean())
                     for rule in sweep_rules]
            mirrors = [part[part["rule"] == rule]["realized_day"].mean()
                       for rule in REF_RULES if rule.startswith("mirror")]
            out.append(f"| `{block}` | {slots} | " + " | ".join(cells) + " | "
                       + money(part[part["rule"] == "close"]["realized_day"].mean())
                       + " | " + money(max(mirrors)) + " |")

    out.append("\n## What drives the exit decision\n")
    out.append("Permutation importance (AUC drop, 3 repeats) of the frozen GBT on "
               "segment `i`'s own test era — the largest block — top 20:\n")
    out.append("| feature | AUC drop | sd |")
    out.append("|---|---|---|")
    for _, row in importance.head(20).iterrows():
        out.append(f"| `{row['feature']}` | {row['importance']:.4f} | {row['sd']:.4f} |")

    out.append("\nThe L1 twin's standardised coefficients on the same segment "
               "(top 20 by magnitude) — the sparse read of the same question:\n")
    last = coefficients[coefficients["segment"] == SEGMENTS[-1][0]].copy()
    last = last.reindex(last["coef"].abs().sort_values(ascending=False).index)
    out.append("| feature | coefficient |")
    out.append("|---|---|")
    for _, row in last.head(20).iterrows():
        out.append(f"| `{row['feature']}` | {row['coef']:+.3f} |")
    out.append(f"\nNon-zero coefficients: {int((last['coef'] != 0).sum())} of "
               f"{len(last)}.\n")

    out.append("\nThe state AT an exit call against a hold call "
               f"(theta = {0.40:.2f}, every sampled state of every test era, robust "
               "z of the era's own distribution) — top 20 by gap:\n")
    out.append("| feature | z at exit | z at hold | gap |")
    out.append("|---|---|---|---|")
    for _, row in contrast.head(20).iterrows():
        out.append(f"| `{row['feature']}` | {row['exit_mean_z']:+.2f} | "
                   f"{row['hold_mean_z']:+.2f} | {row['gap_z']:+.2f} |")

    out.append("\n## Shuffle control\n")
    out.append(f"The identical fit on permuted targets ({SHUFFLE_DRAWS} draws per "
               f"segment, same columns, same frozen hyper-parameters), replayed at "
               f"theta = {SHUFFLE_THETA:.2f}.  Top-5 picks, both occupancies, mean "
               "over the five arms:\n")
    out.append("| era | slots | real gbt@0.40 $/day | shuffled $/day | "
               "real AUC | shuffled AUC |")
    out.append("|---|---|---|---|---|---|")
    for seg, block in SEGMENTS:
        diagnostic = diagnostics[diagnostics["segment"] == seg].iloc[0]
        shuffled_auc = np.mean([diagnostic[f"auc_shuf{d}"] for d in range(SHUFFLE_DRAWS)])
        for slots in OCCUPANCIES:
            part = frame[(frame["segment"] == seg) & (frame["k"] == 5)
                         & (frame["slots"] == slots)]
            real = part[part["rule"] == f"state[gbt]@{SHUFFLE_THETA:.2f}"]["realized_day"]
            shuffled = part[part["rule"].str.startswith("shuffle")]["realized_day"]
            out.append(f"| `{block}` | {slots} | {money(real.mean())} | "
                       f"{money(shuffled.mean())} | {diagnostic['auc_gbt']:.4f} | "
                       f"{shuffled_auc:.4f} |")

    out.append("\n## Laws and controls\n")
    out.append("- STRICTLY PRIOR at every sampled minute: each state window ENDS AT "
               "and EXCLUDES that second (`distill_model.window`), the pivot counts "
               "read only confirmations emitted at or before it (`render.swings` "
               "stamps a pivot at its retrace), the fvol minute row is the last one "
               "that ENDED before it, and the fill is the first lawful mark at or "
               "after it.")
    out.append("- WALK-FORWARD: a segment's training rows come only from sessions "
               "strictly earlier than its test block — the same splits as "
               "`era_retest.py`.  Usable columns are decided on each segment's own "
               "training window.")
    out.append(f"- NO TEST TUNING: the offsets, the ${REMAIN_DOLLARS:,.0f} target, "
               f"the theta grid {THETAS} and the hyper-parameter grid were fixed "
               f"before any number was computed; hyper-parameters were selected once "
               f"by CV inside the study window 125..{STUDY_HI} and frozen.  Every "
               f"theta is reported.")
    out.append("- COSTS: 576 net cents charged once per trade "
               "(`qr_labels/money.hpp`), on every rule including the oracle.")
    out.append("- WALL: -30,000 net cents, monitored from entry on marks strictly "
               "after the entry mark, filling at the next lawful mark after the "
               "crossing; gap-through retained.")
    out.append(f"- SEALED ZONE: `P.SEALED_FROM` = {P.SEALED_FROM}; the highest "
               f"session touched here is {int(traj['session'].max())}.")
    out.append(f"- TRAJECTORY DATASET: {len(traj):,} sampled states over "
               f"{traj['id'].nunique():,} candidates in {traj['session'].nunique()} "
               f"sessions; base rate P(remaining >= ${REMAIN_DOLLARS:,.0f}) = "
               f"{traj['y'].mean():.3f}.")

    REPORT.write_text("\n".join(out) + "\n")
    print(f"report -> {REPORT}", flush=True)


# ==========================================================================
# main
# ==========================================================================

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", default="all",
                        choices=("traj", "fit", "replay", "report", "all"))
    parser.add_argument("--jobs", type=int, default=32)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()

    if args.stage in ("traj", "all"):
        stage_traj(args.jobs, args.rebuild)
        if args.stage == "traj":
            return

    traj = load_traj()
    print(f"trajectory dataset {traj.shape}; base rate {traj['y'].mean():.4f}",
          flush=True)
    hypers = choose_hypers(traj)

    probability_path = OUTDIR / "state_probs.tsv"
    if args.stage in ("fit", "all") or not probability_path.exists():
        probabilities, diagnostics, coefficients = stage_fit(traj, hypers)
        er.write_tsv(probability_path, probabilities.to_dict("records"))
        er.write_tsv(OUTDIR / "state_fit.tsv", diagnostics.to_dict("records"))
        er.write_tsv(OUTDIR / "state_coefficients.tsv", coefficients.to_dict("records"))
        if args.stage == "fit":
            return
    else:
        probabilities = pd.read_csv(probability_path, sep="\t")
        diagnostics = pd.read_csv(OUTDIR / "state_fit.tsv", sep="\t")
        coefficients = pd.read_csv(OUTDIR / "state_coefficients.tsv", sep="\t")

    replay_path = OUTDIR / "state_replay.tsv"
    if args.stage in ("replay", "all") or not replay_path.exists():
        frame = stage_replay(probabilities)
        er.write_tsv(replay_path, frame.to_dict("records"))
        if args.stage == "replay":
            return
    else:
        frame = pd.read_csv(replay_path, sep="\t")

    importance = importances(traj, hypers)
    er.write_tsv(OUTDIR / "state_importance.tsv", importance.to_dict("records"))
    contrast = exit_contrast(traj, probabilities)
    er.write_tsv(OUTDIR / "state_exit_contrast.tsv", contrast.to_dict("records"))
    reach = attainability(traj, probabilities)
    er.write_tsv(OUTDIR / "state_attainability.tsv", reach.to_dict("records"))
    write_report(frame, diagnostics, coefficients, importance, contrast, reach,
                 hypers, traj)


if __name__ == "__main__":
    main()
