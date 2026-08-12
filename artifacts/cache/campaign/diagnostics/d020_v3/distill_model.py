#!/usr/bin/env python3
"""DISTILL — the orchestrator's discrimination encoded into one small model on
GRANULAR (second-grain) features.

One target: P(winner) with winner := cert_net >= $500 on the confirmed-extreme
roster.  The same score serves selection (take high P) and exits (high P =
hold-to-close, low P = skip), per the exit census.

LAW COMPLIANCE
  * D-034 walk-forward: TRAIN on the study block (398..412, outcomes shown),
    TEST on the blind block (428..447, outcomes joined only by the scorer).
  * D-036 day-complete: every candidate of every session, chronological.
  * Strict causality: every window ends at (and excludes) the candidate's own
    decision second; clock norms use strictly prior sessions only.
  * No hyper-parameter is chosen on the blind block: the model config is picked
    by grouped CV inside the study block and then frozen.

Feature families (ranked by the orchestrator's measured blind-call reliability):
  F  flow-flip / counterflow at the confirmed extreme   (top tier)
  R  regime / day-type context + interactions           (top tier)
  Z  0DTE / crowd composition                           (top tier)
  V  vol & protection dynamics (PROXY_VOL bid/ask)      (top tier, $/use)
  U  urgency composition, D depth wall                  (secondary)
  S  structure counters, A absorption                   (de-prioritised, kept thin)
  P  the ten coarse minute features of playbook_v1      (baseline block)
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import packlib  # noqa: E402

ROOT = pathlib.Path(__file__).parent
SECS = packlib.SESSION_SECONDS                     # 23400
SEC_CACHE = packlib.CACHE / "sec2"
WINNER_CENT = 50000                                # $500 in cents
H60 = 4                                            # menu index of the 60m horizon
HCLOSE = 6                                         # menu index of the close horizon
SEED = 20260812

# --------------------------------------------------------------------------
# per-second session arrays (built once from the raw ribbon, cached)
# --------------------------------------------------------------------------

SEC_KEYS = ("prints", "touch", "through", "signed", "abssize", "depth", "depth_n",
            "bidsh", "asksh", "spread", "spread_n",
            "opt_n", "opt_vol", "zdte_vol", "delta_f", "gamma_f", "vanna_f",
            "charm_f", "prem_f", "civ_w", "c_sz", "piv_w", "p_sz")


def _bins(sec: np.ndarray, weights: np.ndarray | None = None) -> np.ndarray:
    return np.bincount(sec, weights=weights, minlength=SECS)[:SECS].astype(np.float64)


def second_arrays(ordinal: int) -> dict:
    """Per-second raw aggregates of the stock print and option print streams."""
    packlib.assert_wall(ordinal, "second_arrays")
    cached = SEC_CACHE / f"s{ordinal}.npz"
    if cached.exists():
        with np.load(cached) as handle:
            return {key: handle[key].astype(np.float64) for key in handle.files}
    SEC_CACHE.mkdir(parents=True, exist_ok=True)

    frame = pd.read_csv(packlib.ribbon_path(ordinal), sep="\t", header=None,
                        names=list(range(20)), comment="#", dtype=str,
                        engine="c", na_filter=False)
    day_number = packlib.civil_day(packlib.session_meta(ordinal)["day"])
    out = {key: np.zeros(SECS) for key in SEC_KEYS}

    def num(block: pd.DataFrame, index: int) -> np.ndarray:
        return pd.to_numeric(block[index], errors="coerce").to_numpy(dtype=np.float64)

    def sign_of(price, bid, ask):
        """Quote-certified sign: literal comparison against the print's own NBBO."""
        ok = np.isfinite(price) & np.isfinite(bid) & np.isfinite(ask) & (ask > bid)
        sign = np.where(price >= ask, 1.0, np.where(price <= bid, -1.0, 0.0))
        return np.where(ok, sign, np.nan), ok

    stock = frame[frame[0] == "print"]
    if len(stock):
        ms = num(stock, 1)
        sec = np.clip((ms // 1000).astype(np.int64), 0, SECS - 1)
        size = np.nan_to_num(num(stock, 2))
        price, bid, ask = num(stock, 3), num(stock, 4), num(stock, 5)
        bidsh, asksh = num(stock, 6), num(stock, 7)
        sign, ok = sign_of(price, bid, ask)
        signed = np.where(ok, np.nan_to_num(sign) * size, 0.0)
        touch = np.where(ok & (np.nan_to_num(sign) != 0.0), 1.0, 0.0)
        through = np.where(ok & ((price > ask) | (price < bid)), 1.0, 0.0)
        mid = np.where(ok, bid + (ask - bid) / 2.0, np.nan)
        spread_bps = np.where(ok & (mid > 0), (ask - bid) * 1e4 / np.where(mid > 0, mid, 1), np.nan)
        depth_ok = np.isfinite(bidsh) & np.isfinite(asksh)
        out["prints"] = _bins(sec)
        out["touch"] = _bins(sec, touch)
        out["through"] = _bins(sec, through)
        out["signed"] = _bins(sec, signed)
        out["abssize"] = _bins(sec, np.abs(signed))
        out["depth"] = _bins(sec, np.where(depth_ok, bidsh + asksh, 0.0))
        out["depth_n"] = _bins(sec, depth_ok.astype(float))
        out["bidsh"] = _bins(sec, np.where(depth_ok, bidsh, 0.0))
        out["asksh"] = _bins(sec, np.where(depth_ok, asksh, 0.0))
        out["spread"] = _bins(sec, np.nan_to_num(spread_bps))
        out["spread_n"] = _bins(sec, np.isfinite(spread_bps).astype(float))

    option = frame[frame[0] == "option"]
    if len(option):
        ms = num(option, 1)
        sec = np.clip((ms // 1000).astype(np.int64), 0, SECS - 1)
        size = np.nan_to_num(num(option, 2))
        price = num(option, 3)
        expiry = num(option, 6)
        right = option[5].to_numpy()
        iv = num(option, 15)
        bid, ask = num(option, 7), num(option, 8)
        delta, gamma, vanna, charm = (num(option, 11), num(option, 12),
                                      num(option, 13), num(option, 14))
        sign, ok = sign_of(price, bid, ask)
        signed_contracts = np.where(ok, np.nan_to_num(sign) * size, 0.0)
        out["opt_n"] = _bins(sec)
        out["opt_vol"] = _bins(sec, size)
        out["zdte_vol"] = _bins(sec, np.where(expiry == day_number, size, 0.0))
        out["delta_f"] = _bins(sec, signed_contracts * np.nan_to_num(delta))
        out["gamma_f"] = _bins(sec, signed_contracts * np.nan_to_num(gamma))
        out["vanna_f"] = _bins(sec, signed_contracts * np.nan_to_num(vanna))
        out["charm_f"] = _bins(sec, signed_contracts * np.nan_to_num(charm))
        out["prem_f"] = _bins(sec, signed_contracts * np.nan_to_num(price) / 1e6 * 100.0)
        # vendor traded-IV, size weighted, split by right (skew tilt of the PRINTS)
        iv_ok = np.isfinite(iv) & (iv > 0) & (iv < 5.0)
        is_call, is_put = (right == "CALL") & iv_ok, (right == "PUT") & iv_ok
        out["civ_w"] = _bins(sec, np.where(is_call, iv * size, 0.0))
        out["c_sz"] = _bins(sec, np.where(is_call, size, 0.0))
        out["piv_w"] = _bins(sec, np.where(is_put, iv * size, 0.0))
        out["p_sz"] = _bins(sec, np.where(is_put, size, 0.0))

    np.savez_compressed(cached, **{k: v.astype(np.float32) for k, v in out.items()})
    return out


def mid_series(ordinal: int) -> np.ndarray:
    """Carried 1s mid in dollars, absent seconds forward-filled (0 = not yet seen)."""
    mid = packlib.load_grid(ordinal)[:SECS, 0].astype(np.float64) / 1e6
    mid[mid <= 0] = np.nan
    index = np.arange(len(mid))
    valid = np.isfinite(mid)
    if valid.any():
        mid = mid[np.maximum.accumulate(np.where(valid, index, 0))]
        mid[: int(index[valid][0])] = np.nan
    return mid


VOL_NAMES = ("proxy_vol_bid_p0", "proxy_vol_ask_p0", "proxy_vol_mid_p0", "width_bps_p0",
             "proxy_vol_mid_p1", "proxy_vol_bid_p1", "proxy_vol_ask_p1", "width_bps_p1")


def vol_series(ordinal: int) -> dict:
    """W2.1 straddle level series on the dump's own 60s stride, per minute bucket.

    Only LEVELS are read; every innovation used downstream is a strictly
    backward difference computed here, so no dump-side horizon convention can
    leak forward information.
    """
    out = {name: np.full(packlib.MINUTE_BUCKETS, np.nan) for name in VOL_NAMES}
    path = packlib.CACHE / "w21norm" / f"s{ordinal}.tsv"
    #: Sessions 125..208 are Q12 MODALITY_ABSENT (no option-quote surface at all).
    #: The derived NEAR/FAR keys must still EXIST there, all-NaN — a typed absence
    #: — or every caller of a `_near` channel raises instead of reading a gap.
    if path.exists():
        for line in path.read_text().splitlines():
            if not line.startswith("straddle\t"):
                continue
            _, second, name, value, validity = line.split("\t")
            if validity != "VALID" or name not in out:
                continue
            number = float(value)
            bucket = int(second) // 60
            if (number > 0.0 and 0 <= bucket < packlib.MINUTE_BUCKETS
                    and np.isnan(out[name][bucket])):
                out[name][bucket] = number
    # NEAR plane = the first plane carrying a present straddle (the surface's own
    # preference order, as in packlib._proxy_vol_minutes); FAR = the next one, and
    # it exists only where both planes are present.
    for stem in ("proxy_vol_mid", "proxy_vol_bid", "proxy_vol_ask", "width_bps"):
        plane0, plane1 = out.get(f"{stem}_p0"), out.get(f"{stem}_p1")
        if plane1 is None:
            plane1 = np.full(packlib.MINUTE_BUCKETS, np.nan)
        out[f"{stem}_near"] = np.where(np.isfinite(plane0), plane0, plane1)
        out[f"{stem}_far"] = np.where(np.isfinite(plane0), plane1, np.nan)
    return out


# --------------------------------------------------------------------------
# window arithmetic (all windows END at, and EXCLUDE, the decision second)
# --------------------------------------------------------------------------

def cumsum0(values: np.ndarray) -> np.ndarray:
    return np.concatenate([[0.0], np.cumsum(values)])


def window(cum: np.ndarray, start: int, stop: int) -> float:
    if start < 0 or stop <= start:
        return np.nan
    return float(cum[stop] - cum[start])


def block_z(cum: np.ndarray, t: int, width: int, lookback: int = 600):
    """(value over [t-w, t), robust z of it against the immediately prior blocks)."""
    value = window(cum, t - width, t)
    blocks = max(2, lookback // width)
    base = [window(cum, t - width - (i + 1) * width, t - width - i * width)
            for i in range(blocks)]
    base = np.array([b for b in base if np.isfinite(b)])
    if not np.isfinite(value) or len(base) < 3:
        return value, np.nan
    sigma = base.std(ddof=1)
    if not np.isfinite(sigma) or sigma <= 0:
        return value, np.nan
    return value, float((value - base.mean()) / sigma)


def ratio_z(num_cum: np.ndarray, den_cum: np.ndarray, t: int, width: int, lookback: int = 600):
    """Same shape as block_z for a ratio quantity (fraction-style features)."""
    def frac(start, stop):
        den = window(den_cum, start, stop)
        if not np.isfinite(den) or den <= 0:
            return np.nan
        return window(num_cum, start, stop) / den

    value = frac(t - width, t)
    blocks = max(2, lookback // width)
    base = np.array([f for f in (frac(t - width - (i + 1) * width, t - width - i * width)
                                 for i in range(blocks)) if np.isfinite(f)])
    if not np.isfinite(value) or len(base) < 3:
        return value, np.nan
    sigma = base.std(ddof=1)
    if not np.isfinite(sigma) or sigma <= 0:
        return value, np.nan
    return value, float((value - base.mean()) / sigma)


def sgn(x) -> float:
    if not np.isfinite(x):
        return 0.0
    return 1.0 if x > 0 else (-1.0 if x < 0 else 0.0)


# --------------------------------------------------------------------------
# the feature matrix
# --------------------------------------------------------------------------

PIVOT_TAGS = ("HH", "HL", "LH", "LL")
#: signals crossed with regime flags (fixed by design; never selected on data)
CORE_SIGNALS = ("F_sf60_z", "F_sf120_z", "U_urg120_z", "D_depth60_z",
                "Z_zdte_slope", "V_pv_asym_z", "V_skew_traded_o", "V_term_ratio",
                "P_trend_match")
REGIME_FLAGS = ("R_trend_day", "R_compress", "R_atr_high", "R_late")


def atr_reference(ordinal: int) -> float:
    """Median ATR14 of the 60 sessions strictly before this one (causal regime norm)."""
    values = []
    for prior in range(max(packlib.DRAW_WALL[0], ordinal - 60), ordinal):
        path = packlib.CACHE / "w2meta" / f"s{prior}.tsv"
        if not path.exists():
            continue
        try:
            values.append(float(packlib.session_meta(prior).get("atr14_bps")))
        except (TypeError, ValueError):
            continue
    return float(np.median(values)) if values else np.nan


def session_features(ordinal: int, candidates: list, norm: packlib.ClockNorm) -> list:
    arrays = second_arrays(ordinal)
    cum = {key: cumsum0(values) for key, values in arrays.items()}
    mid = mid_series(ordinal)
    vol = vol_series(ordinal)
    minutes = packlib.minute_aggregates(ordinal)
    median, sigma, _ = norm.stats(ordinal)
    meta = packlib.session_meta(ordinal)
    atr = float(meta.get("atr14_bps") or 150.0)
    atr_ref = atr_reference(ordinal)
    open_px = float(meta.get("open_u6") or 0.0) / 1e6
    keys = {name: index for index, name in enumerate(packlib.TRAJECTORY_KEYS)}

    def px(second: int) -> float:
        second = int(np.clip(second, 0, len(mid) - 1))
        return mid[second]

    rows = []
    ordered = sorted(candidates, key=lambda c: c["second"])
    for position, cand in enumerate(ordered):
        t = int(cand["second"])
        side = 1.0 if cand["side"] == "L" else -1.0
        f = {}

        # ---- F: flow-flip / counterflow (top tier) -------------------------
        sf60, z60 = block_z(cum["signed"], t, 60)
        sf120, z120 = block_z(cum["signed"], t, 120)
        sf30, z30 = block_z(cum["signed"], t, 30, lookback=300)
        sf600 = window(cum["signed"], t - 600, t)
        prior_flow = window(cum["signed"], t - 660, t - 60)
        f["F_sf60_o"] = side * sf60
        f["F_sf60_z"] = side * z60
        f["F_sf120_o"] = side * sf120
        f["F_sf120_z"] = side * z120
        f["F_sf30_z"] = side * z30
        f["F_sf600_o"] = side * sf600
        f["F_flip"] = 1.0 if (sgn(side * sf60) > 0 and sgn(side * prior_flow) < 0) else 0.0
        f["F_flip_mag"] = side * (sf60 - prior_flow / 10.0)
        f["F_accel"] = side * (sf60 - (sf120 - sf60))          # last 60s vs the 60s before
        f["F_sign_match"] = 1.0 if side * sf60 > 0 else 0.0
        f["F_persist"] = float(np.mean([1.0 if side * window(cum["signed"], t - (i + 1) * 60,
                                                             t - i * 60) > 0 else 0.0
                                        for i in range(5)]))

        # ---- U: urgency composition ---------------------------------------
        urg, urg_z = ratio_z(cum["touch"], cum["prints"], t, 120)
        thr, thr_z = block_z(cum["through"], t, 120)
        _, rate_z = block_z(cum["prints"], t, 120)
        f["U_urg120"] = urg
        f["U_urg120_z"] = urg_z
        f["U_through120"] = thr
        f["U_through120_z"] = thr_z
        f["U_printrate_z"] = rate_z
        # the LAST COMPLETED minute: the bucket containing t is still in progress
        # at the decision second and may never be read.
        minute = min(t // 60, packlib.MINUTE_BUCKETS - 1) - 1
        f["U_urg_clock_z"] = np.nan
        if minute >= 0:
            index = keys["urgency_mix"]
            spread_sigma = sigma[minute, index]
            if np.isfinite(spread_sigma) and spread_sigma > 0:
                f["U_urg_clock_z"] = ((minutes[minute, index] - median[minute, index])
                                      / spread_sigma)

        # ---- D: depth wall -------------------------------------------------
        depth, depth_z = ratio_z(cum["depth"], cum["depth_n"], t, 60)
        f["D_depth60"] = depth
        f["D_depth60_z"] = depth_z
        bid60 = window(cum["bidsh"], t - 60, t)
        ask60 = window(cum["asksh"], t - 60, t)
        total = bid60 + ask60
        imb60 = (bid60 - ask60) / total if np.isfinite(total) and total > 0 else np.nan
        bid600 = window(cum["bidsh"], t - 660, t - 60)
        ask600 = window(cum["asksh"], t - 660, t - 60)
        total600 = bid600 + ask600
        imb600 = (bid600 - ask600) / total600 if np.isfinite(total600) and total600 > 0 else np.nan
        f["D_imb60_o"] = side * imb60
        f["D_imb_delta_o"] = side * (imb60 - imb600)

        # ---- A: absorption (kept thin, de-prioritised) ---------------------
        def absorption(start, stop):
            shares = window(cum["abssize"], start, stop) / 1000.0
            a, b = px(start), px(stop - 1)
            if not (np.isfinite(a) and np.isfinite(b)) or shares <= 0 or a <= 0:
                return np.nan
            return abs(b - a) * 1e4 / a / shares

        abs60 = absorption(t - 60, t)
        abs600 = absorption(t - 660, t - 60)
        f["A_abs60"] = abs60
        f["A_abs_ratio"] = abs60 / abs600 if np.isfinite(abs600) and abs600 > 0 else np.nan
        a, b = px(t - 60), px(t - 1)
        f["A_move60_o"] = side * (b - a) * 1e4 / a if np.isfinite(a) and a > 0 else np.nan

        # ---- Z: 0DTE / crowd composition (top tier) ------------------------
        share_now = (window(cum["zdte_vol"], t - 300, t)
                     / max(window(cum["opt_vol"], t - 300, t), 1e-9))
        share_prev = (window(cum["zdte_vol"], t - 1800, t - 300)
                      / max(window(cum["opt_vol"], t - 1800, t - 300), 1e-9))
        share_120 = (window(cum["zdte_vol"], t - 120, t)
                     / max(window(cum["opt_vol"], t - 120, t), 1e-9))
        f["Z_share_now"] = share_now
        f["Z_share_delta30"] = share_now - share_prev
        f["Z_zdte_slope"] = share_120 - share_now
        _, zdte_z = block_z(cum["zdte_vol"], t, 300)
        f["Z_zdte_vol_z"] = zdte_z
        dflow120, dflow_z = block_z(cum["delta_f"], t, 120)
        f["Z_dflow120_o"] = side * dflow120
        f["Z_dflow120_z"] = side * dflow_z
        _, optvol_z = block_z(cum["opt_vol"], t, 120)
        f["Z_optvol_z"] = optvol_z
        # crowd (0DTE-heavy) vs institution proxy: does the option side agree
        # with the stock side while the 0DTE crowd piles the other way?
        f["Z_crowd_against"] = (1.0 if (np.isfinite(share_now) and share_now - share_prev > 0.05
                                        and side * dflow120 < 0) else 0.0)
        for name, key in (("gamma", "gamma_f"), ("vanna", "vanna_f"),
                          ("charm", "charm_f"), ("prem", "prem_f")):
            value, zed = block_z(cum[key], t, 120)
            f[f"Z_{name}120_o"] = side * value
            f[f"Z_{name}120_z"] = side * zed

        # ---- V: vol & protection dynamics (top tier, highest $/use) --------
        vm = max(minute, 0)                           # last strided point strictly prior

        def vol_at(name, bucket):
            series = vol[name]
            bucket = int(np.clip(bucket, 0, len(series) - 1))
            valid = np.flatnonzero(np.isfinite(series[: bucket + 1]))
            return series[valid[-1]] if len(valid) else np.nan

        def vol_z(name, bucket, back=30):
            series = vol[name][max(0, bucket - back): bucket + 1]
            series = series[np.isfinite(series)]
            now = vol_at(name, bucket)
            if len(series) < 5 or not np.isfinite(now) or series.std(ddof=1) <= 0:
                return np.nan
            return float((now - series.mean()) / series.std(ddof=1))

        pv_bid, pv_ask = vol_at("proxy_vol_bid_near", vm), vol_at("proxy_vol_ask_near", vm)
        pv_mid = vol_at("proxy_vol_mid_near", vm)
        f["V_pv_bid_z"] = vol_z("proxy_vol_bid_near", vm)
        f["V_pv_ask_z"] = vol_z("proxy_vol_ask_near", vm)
        f["V_width_z"] = vol_z("width_bps_near", vm)
        asym = ((pv_ask - pv_bid) / pv_mid) if np.isfinite(pv_mid) and pv_mid > 0 else np.nan
        f["V_pv_asym"] = asym
        prev_bucket = max(vm - 10, 0)
        prev_bid, prev_ask = (vol_at("proxy_vol_bid_near", prev_bucket),
                              vol_at("proxy_vol_ask_near", prev_bucket))
        prev_mid = vol_at("proxy_vol_mid_near", prev_bucket)
        prev_asym = ((prev_ask - prev_bid) / prev_mid) if np.isfinite(prev_mid) and prev_mid > 0 \
            else np.nan
        f["V_pv_asym_z"] = asym - prev_asym            # protection-premium innovation, 10 min
        f["V_dlog_mid10"] = (np.log(pv_mid / prev_mid)
                             if np.isfinite(pv_mid) and np.isfinite(prev_mid)
                             and pv_mid > 0 and prev_mid > 0 else np.nan)
        f["V_dlog_ask10"] = (np.log(pv_ask / prev_ask)
                             if np.isfinite(pv_ask) and np.isfinite(prev_ask)
                             and pv_ask > 0 and prev_ask > 0 else np.nan)
        f["V_dlog_bid10"] = (np.log(pv_bid / prev_bid)
                             if np.isfinite(pv_bid) and np.isfinite(prev_bid)
                             and pv_bid > 0 and prev_bid > 0 else np.nan)
        f["V_protection_spike"] = (1.0 if (np.isfinite(f["V_dlog_ask10"])
                                           and f["V_dlog_ask10"] > 0.10) else 0.0)
        f["V_pv_level"] = pv_mid

        # TERM-MICRO RATIO: plane0 (today) vs plane1 (tomorrow) PROXY_VOL.
        # Typed-absent whenever the session quotes a single expiry plane.
        p1_now, p1_old = (vol_at("proxy_vol_mid_far", vm),
                          vol_at("proxy_vol_mid_far", max(vm - 30, 0)))
        p0_old = vol_at("proxy_vol_mid_near", max(vm - 30, 0))
        term = pv_mid / p1_now if np.isfinite(p1_now) and p1_now > 0 else np.nan
        term_old = p0_old / p1_old if np.isfinite(p1_old) and p1_old > 0 else np.nan
        f["V_term_ratio"] = term
        f["V_term_slope30"] = term - term_old if np.isfinite(term) and np.isfinite(term_old) \
            else np.nan
        f["V_term_present"] = 1.0 if np.isfinite(term) else 0.0

        # TRADED-IV ASYMMETRY: size-weighted call IV minus put IV over the last
        # 15 minutes, from the ribbon's vendor IV per print, plus its slope.
        def traded_skew(start, stop):
            call_size = window(cum["c_sz"], start, stop)
            put_size = window(cum["p_sz"], start, stop)
            if not (np.isfinite(call_size) and np.isfinite(put_size)) \
                    or call_size <= 0 or put_size <= 0:
                return np.nan
            return (window(cum["civ_w"], start, stop) / call_size
                    - window(cum["piv_w"], start, stop) / put_size)

        skew_now = traded_skew(t - 900, t)
        skew_prev = traded_skew(t - 1800, t - 900)
        f["V_skew_traded"] = skew_now
        f["V_skew_traded_o"] = side * skew_now
        f["V_skew_slope"] = skew_now - skew_prev
        f["V_skew_slope_o"] = side * (skew_now - skew_prev)

        # ---- S: structure (secondary) --------------------------------------
        pivot = float(cand["pivot_mid"]) / 1e6 if float(cand["pivot_mid"]) > 1e4 \
            else float(cand["pivot_mid"])
        for tag in PIVOT_TAGS:
            f[f"S_tag_{tag}"] = 1.0 if cand["pivot_tag"] == tag else 0.0
        f["S_confirm_delay"] = float(cand["confirm_delay_s"])
        prior_pivots = [float(c["pivot_mid"]) for c in ordered[:position]]
        prior_pivots = [p / 1e6 if p > 1e4 else p for p in prior_pivots]
        if prior_pivots and np.isfinite(pivot):
            f["S_swing_atr"] = abs(pivot - prior_pivots[-1]) * 1e4 / pivot / atr
        else:
            f["S_swing_atr"] = np.nan
        f["S_same_dir_30m"] = float(sum(1 for c in ordered[:position]
                                        if c["side"] == cand["side"]
                                        and t - c["second"] <= 1800))
        f["S_conf_30m"] = float(sum(1 for c in ordered[:position] if t - c["second"] <= 1800))
        f["S_index"] = float(position)
        history = mid[:t][np.isfinite(mid[:t])]
        if len(history) > 60 and np.isfinite(pivot):
            hi, lo = history.max(), history.min()
            f["S_range_atr"] = (hi - lo) * 1e4 / pivot / atr
            f["S_pivot_in_range"] = (pivot - lo) / (hi - lo) if hi > lo else np.nan
            f["S_pivot_extreme_o"] = side * ((lo - pivot) if side > 0 else (pivot - hi)) \
                * 1e4 / pivot / atr
        else:
            f["S_range_atr"] = f["S_pivot_in_range"] = f["S_pivot_extreme_o"] = np.nan

        # ---- P: the coarse playbook_v1 block (baseline) ---------------------
        m = min(t // 60, packlib.MINUTE_BUCKETS - 1)
        win = minutes[max(0, m - 5):m]
        hour = minutes[max(0, m - 60):m]

        def agg(rows, key, how=np.nansum):
            if not len(rows):
                return np.nan
            col = rows[:, keys[key]]
            col = col[~np.isnan(col)]
            return float(how(col)) if len(col) else np.nan

        flow5 = agg(win, "signed_flow")
        flow_sigma = sigma[m, keys["signed_flow"]]
        f["P_flow5_o"] = side * flow5
        f["P_flow5_z"] = (side * flow5 / (flow_sigma * np.sqrt(max(len(win), 1)))
                          if np.isfinite(flow_sigma) and flow_sigma else np.nan)
        f["P_od5_o"] = side * agg(win, "option_delta_dir")
        cum_hour = agg(hour, "signed_flow")
        f["P_cumflow_h_o"] = side * cum_hour
        zer_now = agg(win[-2:], "zerodte_share", np.nanmean)
        zer_before = agg(hour[:30], "zerodte_share", np.nanmean)
        f["P_zer_now"] = zer_now
        f["P_zer_before"] = zer_before
        f["P_zer_delta"] = zer_now - zer_before
        move_open = (pivot - open_px) / open_px * 1e4 if open_px else np.nan
        trend_size = abs(move_open) / atr if np.isfinite(move_open) else np.nan
        f["P_trend_size"] = trend_size
        f["P_trend_match"] = side * sgn(move_open)
        f["P_runway_s"] = float(SECS - t)

        # ---- R: regime (top tier) + fixed interactions ----------------------
        f["R_trend_day"] = 1.0 if np.isfinite(trend_size) and trend_size >= 0.60 else 0.0
        f["R_compress"] = 1.0 if (np.isfinite(trend_size) and trend_size < 0.30
                                  and (not np.isfinite(cum_hour) or abs(cum_hour) < 60_000)) else 0.0
        f["R_atr_high"] = 1.0 if (np.isfinite(atr_ref) and atr > atr_ref) else 0.0
        f["R_atr_rel"] = atr / atr_ref if np.isfinite(atr_ref) and atr_ref > 0 else np.nan
        f["R_tod"] = float(min(t // 7800, 2))
        f["R_morning"] = 1.0 if t < 7800 else 0.0
        f["R_late"] = 1.0 if t >= 15600 else 0.0
        f["R_runway_min"] = (SECS - t) / 60.0
        f["R_short_runway"] = 1.0 if (SECS - t) < 1200 else 0.0
        f["R_dayrange_atr"] = f["S_range_atr"]
        f["R_side"] = side
        for signal in CORE_SIGNALS:
            for flag in REGIME_FLAGS:
                value = f.get(signal, np.nan)
                f[f"X_{signal}__{flag}"] = value * f[flag] if np.isfinite(value) else np.nan

        rows.append((cand, f))
    return rows


def build_matrix() -> pd.DataFrame:
    rosters = json.loads((ROOT / "daysheets" /
                          "rosters_DO_NOT_READ_UNTIL_CALLS_COMMITTED.json").read_text())
    norm = packlib.ClockNorm(list(range(packlib.DRAW_WALL[0], packlib.DRAW_WALL[1] + 1)))
    records = []
    for key in sorted(rosters["sessions"], key=int):
        ordinal = int(key)
        record = rosters["sessions"][key]
        packlib.assert_case_wall(ordinal, "build_matrix")
        truth = {}
        for cand, features in session_features(ordinal, record["candidates"], norm):
            side = cand["side"]
            if side not in truth:
                truth[side] = packlib.load_truth(ordinal, side)
            row = int(cand["row"])
            head = {
                "session": ordinal, "block": record["block"], "day": record["day"],
                "id": cand["id"], "second": int(cand["second"]), "side": side,
                "cert": float(truth[side]["cert_net_cent"][row]) / 100.0,
                "cert_mae": float(truth[side]["cert_mae_cent"][row]) / 100.0,
                "menu60": float(truth[side]["menu_net_cent"][row][H60]) / 100.0,
                "menu_close": float(truth[side]["menu_net_cent"][row][HCLOSE]) / 100.0,
            }
            head["winner"] = 1 if truth[side]["cert_net_cent"][row] >= WINNER_CENT else 0
            head.update(features)
            records.append(head)
        print(f"  s{ordinal} [{record['block']}] {len(record['candidates'])} candidates", flush=True)
    return pd.DataFrame.from_records(records)


# --------------------------------------------------------------------------
# model + evaluation
# --------------------------------------------------------------------------

META_COLS = ("session", "block", "day", "id", "second", "side", "cert", "cert_mae",
             "menu60", "menu_close", "winner")

CONFIGS = (
    dict(max_depth=2, max_iter=150, learning_rate=0.05, min_samples_leaf=20, l2_regularization=1.0),
    dict(max_depth=3, max_iter=200, learning_rate=0.05, min_samples_leaf=20, l2_regularization=1.0),
    dict(max_depth=3, max_iter=120, learning_rate=0.08, min_samples_leaf=30, l2_regularization=2.0),
)


def feature_columns(frame: pd.DataFrame, study: pd.DataFrame, regime: bool = True) -> list:
    """Usable feature columns.  Degenerate columns are dropped on the STUDY block
    only (a column all-NaN or constant in the training era carries no fit)."""
    columns = [c for c in frame.columns if c not in META_COLS]
    if not regime:
        columns = [c for c in columns if not (c.startswith("R_") or c.startswith("X_"))]
    keep = []
    for name in columns:
        values = pd.to_numeric(study[name], errors="coerce").to_numpy(float)
        values = values[np.isfinite(values)]
        if len(values) >= 20 and len(np.unique(values)) >= 2:
            keep.append(name)
    return keep


def fit_predict(study, blind, columns, seed=SEED):
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.model_selection import GroupKFold
    from sklearn.metrics import roc_auc_score

    X, y, groups = study[columns].to_numpy(float), study["winner"].to_numpy(), study["session"]
    best, best_auc = None, -np.inf
    folds = GroupKFold(n_splits=5)
    oof = np.full(len(study), np.nan)
    for config in CONFIGS:
        scores, predictions = [], np.full(len(study), np.nan)
        for train, test in folds.split(X, y, groups):
            if len(np.unique(y[train])) < 2 or len(np.unique(y[test])) < 2:
                continue
            model = HistGradientBoostingClassifier(random_state=seed, **config).fit(X[train], y[train])
            predictions[test] = model.predict_proba(X[test])[:, 1]
            scores.append(roc_auc_score(y[test], predictions[test]))
        auc = float(np.mean(scores)) if scores else np.nan
        if np.isfinite(auc) and auc > best_auc:
            best, best_auc, oof = config, auc, predictions
    model = HistGradientBoostingClassifier(random_state=seed, **best).fit(X, y)
    return model, best, best_auc, oof, model.predict_proba(blind[columns].to_numpy(float))[:, 1]


L1_GRID = (0.02, 0.05, 0.2, 1.0)


def logistic_twin(study, blind, columns, seed=SEED):
    """L1 logistic twin; the penalty strength is chosen by STUDY grouped CV only."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.impute import SimpleImputer
    from sklearn.model_selection import GroupKFold
    from sklearn.metrics import roc_auc_score

    X, y, groups = study[columns].to_numpy(float), study["winner"].to_numpy(), study["session"]

    def build(strength):
        return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                             LogisticRegression(penalty="l1", solver="liblinear", C=strength,
                                                max_iter=5000, random_state=seed))

    best, best_auc = L1_GRID[0], -np.inf
    for strength in L1_GRID:
        scores = []
        for train, test in GroupKFold(n_splits=5).split(X, y, groups):
            if len(np.unique(y[train])) < 2 or len(np.unique(y[test])) < 2:
                continue
            fitted = build(strength).fit(X[train], y[train])
            scores.append(roc_auc_score(y[test], fitted.predict_proba(X[test])[:, 1]))
        auc = float(np.mean(scores)) if scores else np.nan
        if np.isfinite(auc) and auc > best_auc:
            best, best_auc = strength, auc
    pipe = build(best).fit(X, y)
    return (pipe, pipe.predict_proba(blind[columns].to_numpy(float))[:, 1],
            pipe[-1].coef_[0], best, best_auc)


def day_metrics(frame: pd.DataFrame, score: np.ndarray, k: int = 3) -> dict:
    """Top-k-per-day selection: exit-free value, one-position replays, oracle, random."""
    frame = frame.assign(score=score)
    picks_cert, oracle, per_day_close, per_day_60 = [], [], [], []
    counts, held_close, maes = [], [], []
    rng = np.random.default_rng(SEED)
    random_days = []
    for _, day in frame.groupby("session"):
        top = day.nlargest(k, "score").sort_values("second")
        picks_cert.append(top["cert"].sum())
        oracle.append(day.nlargest(k, "cert")["cert"].sum())
        counts.append(len(top))
        # one position, chronological, held to the close: only the earliest pick fits
        per_day_close.append(float(top.iloc[0]["menu_close"]) if len(top) else 0.0)
        # one position, chronological, 60-minute menu horizon (playbook_v1 comparison)
        busy, total = -1, 0.0
        for _, row in top.iterrows():
            if row["second"] < busy:
                continue
            total += row["menu60"]
            busy = row["second"] + 3600
        per_day_60.append(total)
        held_close.append(top["menu_close"].sum())
        maes.extend(top["cert_mae"].tolist())
        draws = [day.sample(min(k, len(day)), random_state=int(rng.integers(1 << 30)))["cert"].sum()
                 for _ in range(200)]
        random_days.append(float(np.mean(draws)))
    return {
        "days": len(picks_cert),
        "picks": int(np.sum(counts)),
        "cert_per_day": float(np.mean(picks_cert)),
        "cert_per_cand": float(np.sum(picks_cert) / max(np.sum(counts), 1)),
        "oracle_per_day": float(np.mean(oracle)),
        "random_per_day": float(np.mean(random_days)),
        "replay_close_per_day": float(np.mean(per_day_close)),
        "replay_60m_per_day": float(np.mean(per_day_60)),
        "all3_close_per_day": float(np.mean(held_close)),
        "mae_per_pick": float(np.mean(maes)) if maes else np.nan,
    }


def report_block(name, frame, score, out):
    from sklearn.metrics import roc_auc_score
    auc = roc_auc_score(frame["winner"], score)
    metrics = day_metrics(frame, score)
    out.append(f"### {name}")
    out.append(f"- candidates {len(frame)} | winners {int(frame['winner'].sum())} "
               f"({frame['winner'].mean():.1%}) | AUC **{auc:.3f}**")
    out.append(f"- top-3/day exit-free cert: **${metrics['cert_per_day']:,.0f}/day** "
               f"(${metrics['cert_per_cand']:,.0f}/candidate) vs oracle "
               f"${metrics['oracle_per_day']:,.0f}/day vs random-3 "
               f"${metrics['random_per_day']:,.0f}/day")
    out.append(f"- one-position replay: hold-to-close **${metrics['replay_close_per_day']:,.0f}/day**"
               f" | 60m menu ${metrics['replay_60m_per_day']:,.0f}/day"
               f" | all three held to close ${metrics['all3_close_per_day']:,.0f}/day")
    out.append(f"- all-candidate cert mean ${frame['cert'].mean():,.0f}")
    quartile = np.quantile(score, [0.25, 0.75])
    high, low = frame[score >= quartile[1]], frame[score <= quartile[0]]
    out.append(f"- exit-use split (P quartiles): top-Q cert ${high['cert'].mean():,.0f} / "
               f"close ${high['menu_close'].mean():,.0f} / 60m ${high['menu60'].mean():,.0f} "
               f"vs bottom-Q cert ${low['cert'].mean():,.0f} / close "
               f"${low['menu_close'].mean():,.0f} / 60m ${low['menu60'].mean():,.0f}")
    return auc, metrics


def main():
    matrix_path = ROOT / "FEATURES.tsv"
    if matrix_path.exists() and "--rebuild" not in sys.argv:
        frame = pd.read_csv(matrix_path, sep="\t")
    else:
        print("building second-grain features ...", flush=True)
        frame = build_matrix()
        frame.to_csv(matrix_path, sep="\t", index=False)
    print(f"matrix {frame.shape} -> {matrix_path}", flush=True)

    study = frame[frame["block"] == "study"].reset_index(drop=True)
    blind = frame[frame["block"] == "blind"].reset_index(drop=True)
    columns = feature_columns(frame, study)
    dropped = [c for c in frame.columns if c not in META_COLS and c not in columns]

    from sklearn.metrics import roc_auc_score
    from sklearn.inspection import permutation_importance

    model, config, cv_auc, oof, blind_score = fit_predict(study, blind, columns)
    study_score = model.predict_proba(study[columns].to_numpy(float))[:, 1]
    _, twin_blind, coefficients, twin_c, twin_cv = logistic_twin(study, blind, columns)

    importance = permutation_importance(
        model, study[columns].to_numpy(float), study["winner"].to_numpy(),
        n_repeats=20, random_state=SEED, scoring="roc_auc")
    order = np.argsort(importance.importances_mean)[::-1]
    # diagnostic only (never used for selection or tuning): what carried the BLIND AUC
    blind_importance = permutation_importance(
        model, blind[columns].to_numpy(float), blind["winner"].to_numpy(),
        n_repeats=20, random_state=SEED, scoring="roc_auc")
    blind_order = np.argsort(blind_importance.importances_mean)[::-1]

    # ---- ablation arms (each re-selects its config on STUDY CV only) --------
    #: regime CONTEXT also lives in the coarse block (runway, trend size), so the
    #: honest "no regime" arm has to drop those too, not only the R_/X_ encodings.
    CONTEXT = ("P_runway_s", "P_trend_size", "P_trend_match", "S_range_atr")
    arms = {
        "full (all features)": columns,
        "no regime ENCODING (drop R_*, X_*)":
            [c for c in columns if not c.startswith(("R_", "X_"))],
        "no regime CONTEXT (drop R_*, X_* and runway/trend/range)":
            [c for c in columns if not c.startswith(("R_", "X_")) and c not in CONTEXT],
        "coarse only (playbook_v1 block, P_*)": [c for c in columns if c.startswith("P_")],
        "granular only (drop P_*)": [c for c in columns if not c.startswith("P_")],
    }
    arm_results = {}
    for label, subset in arms.items():
        if not subset:
            continue
        _, _, arm_cv, _, arm_blind = fit_predict(study, blind, subset)
        arm_results[label] = (len(subset), arm_cv, roc_auc_score(blind["winner"], arm_blind),
                              day_metrics(blind, arm_blind))

    out = ["# DISTILL REPORT — granular-feature winner model (P(cert >= $500))", "",
           f"Config frozen on study CV only: `{config}` (study grouped-CV AUC {cv_auc:.3f}); "
           f"{len(columns)} features, {len(study)} study / {len(blind)} blind candidates.",
           f"Dropped as degenerate in the study era ({len(dropped)}): "
           f"{', '.join('`%s`' % d for d in dropped) if dropped else 'none'}.", ""]
    out.append("## Headline (blind = sessions 428..447, day-complete)")
    blind_auc, blind_metrics = report_block("BLIND (test)", blind, blind_score, out)
    out.append("")
    study_auc, study_metrics = report_block("STUDY (in-sample reference)", study, study_score, out)
    out.append("")
    out.append("### STUDY out-of-fold (grouped CV, honest in-era reference)")
    mask = np.isfinite(oof)
    out.append(f"- OOF AUC {roc_auc_score(study['winner'][mask], oof[mask]):.3f}")
    oof_metrics = day_metrics(study[mask].reset_index(drop=True), oof[mask])
    out.append(f"- top-3/day exit-free cert ${oof_metrics['cert_per_day']:,.0f}/day "
               f"vs oracle ${oof_metrics['oracle_per_day']:,.0f} vs random "
               f"${oof_metrics['random_per_day']:,.0f}")
    out.append("")

    out.append("## Ablation arms (config re-selected on study CV in every arm)")
    out.append("| arm | features | study CV AUC | blind AUC | top-3 $/day | $/candidate |")
    out.append("|---|---|---|---|---|---|")
    for label, (size, arm_cv, arm_auc, arm_metrics) in arm_results.items():
        out.append(f"| {label} | {size} | {arm_cv:.3f} | {arm_auc:.3f} | "
                   f"${arm_metrics['cert_per_day']:,.0f} | "
                   f"${arm_metrics['cert_per_cand']:,.0f} |")
    out.append("")

    out.append(f"## L1 logistic twin (interpretable; C={twin_c} by study CV, CV AUC {twin_cv:.3f})")
    twin_auc = roc_auc_score(blind["winner"], twin_blind)
    twin_metrics = day_metrics(blind, twin_blind)
    out.append(f"- blind AUC {twin_auc:.3f}; top-3 ${twin_metrics['cert_per_day']:,.0f}/day; "
               f"close-replay ${twin_metrics['replay_close_per_day']:,.0f}/day")
    nonzero = [(columns[i], coefficients[i]) for i in np.argsort(-np.abs(coefficients))
               if coefficients[i] != 0][:12]
    for name, coef in nonzero:
        out.append(f"  - `{name}` {coef:+.3f}")
    out.append("")

    out.append("## Reading the importances (caveat, load-bearing)")
    out.append("Permutation importance splits across DUPLICATED information: `P_runway_s` and "
               "`R_runway_min` are the same quantity, as are `P_trend_size`/`R_dayrange_atr` and "
               "`S_range_atr`.  The tree keeps one copy, so the other copy's family reads ~0.  "
               "Family totals therefore UNDERSTATE the R (regime) family; the honest measure of "
               "regime value is the 'no regime CONTEXT' ablation arm above, which drops every "
               "copy.")
    out.append("")
    out.append("## Feature importances (permutation, study, AUC drop)")
    for rank, index in enumerate(order[:20], 1):
        out.append(f"{rank:>2}. `{columns[index]}` {importance.importances_mean[index]:+.4f} "
                   f"(sd {importance.importances_std[index]:.4f})")
    out.append("")

    out.append("## Feature importances (permutation, BLIND — diagnostic, not used for fitting)")
    for rank, index in enumerate(blind_order[:15], 1):
        out.append(f"{rank:>2}. `{columns[index]}` {blind_importance.importances_mean[index]:+.4f} "
                   f"(sd {blind_importance.importances_std[index]:.4f})")
    out.append("")

    # label-shuffle control: the same pipeline on permuted study labels must land
    # on chance, which is the cheap end-to-end leak test for the whole matrix.
    shuffled = study.copy()
    shuffled["winner"] = np.random.default_rng(SEED).permutation(study["winner"].to_numpy())
    _, _, _, _, control_blind = fit_predict(shuffled, blind, columns)
    out.append("## Controls")
    out.append(f"- label-shuffle control: blind AUC "
               f"{roc_auc_score(blind['winner'], control_blind):.3f} (chance expected)")
    coverage = frame["V_term_ratio"].notna().mean() if "V_term_ratio" in frame else 0.0
    out.append(f"- W2.1 plane-1 (tomorrow expiry) coverage across the 35 sessions: "
               f"{coverage:.1%} of candidates")
    out.append("")

    out.append("## Vol-derivative status (coordinator's three additions)")
    out.append("- TRADED-IV ASYMMETRY: **BUILT** from the ribbon's vendor IV per option print "
               "(`V_skew_traded`, `_o`, `V_skew_slope`, `_o`; size-weighted call IV minus put IV "
               "over the last 15 min and its 15-min slope).")
    out.append("- TERM-MICRO RATIO: **BUILT** (`V_term_ratio`, `V_term_slope30`, `V_term_present`) "
               "but DEGENERATE IN THIS ERA — the W2.1 straddle plane 1 is typed-absent for almost "
               "every session here, so the columns were dropped by the study-era usability filter.")
    out.append("- SKEW TILT from the W2.1 surface: **SKIPPED-NEEDS-TOOL** (D-017, no approximation). "
               "`qr_w21_dump` emits per-bucket rows only for refill / requote / thinning "
               "(`mean_refill_bid|ask`, `oriented_refill_difference`) plus per-plane straddle "
               "rows; no per-bucket vol or width is exposed, and the straddle collapses call and "
               "put by construction, so a put-minus-call surface tilt cannot be formed without a "
               "new emission in C++.  The straddle bid/ask asymmetry fallback is already carried "
               "as `V_pv_asym` / `V_pv_asym_z` and is NOT a right-side tilt.")
    out.append("")

    out.append("## Family totals (sum of positive permutation importance)")
    for label, source in (("study", importance), ("blind", blind_importance)):
        families = {}
        for index, name in enumerate(columns):
            family = name.split("_")[0]
            families[family] = families.get(family, 0.0) + max(source.importances_mean[index], 0.0)
        ranked = " | ".join(f"{family} {value:.4f}"
                            for family, value in sorted(families.items(), key=lambda kv: -kv[1]))
        out.append(f"- {label}: {ranked}")
        if label == "blind":
            blind_families = dict(families)
    out.append("")

    out.append("## Model importance vs the orchestrator's blind-call reliability prior")
    prior = (("FLOW-FLIP / counterflow (80%)", "F"),
             ("REGIME / day-type (80%)", "R"),
             ("0DTE / crowd composition (80%)", "Z"),
             ("VOL / protection (72%)", "V"),
             ("structure counters (61%)", "S"),
             ("runway (gate only)", "P"),
             ("absorption ratios (47%)", "A"))
    order_blind = sorted(blind_families, key=lambda k: -blind_families[k])
    for label, family in prior:
        value = blind_families.get(family, 0.0)
        rank = order_blind.index(family) + 1 if family in order_blind else None
        out.append(f"- prior: {label} -> model family `{family}` blind importance {value:.4f} "
                   f"(rank {rank}/{len(order_blind)})")

    (ROOT / "DISTILL_REPORT.md").write_text("\n".join(out) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    main()
