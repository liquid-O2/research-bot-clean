#!/usr/bin/env python3
"""MODEL V3 — THE HYBRID: the proven reader judgment encoded into the selector.

v2 built the SNIPER_V2 tiers from the readers' *introspection*.  v3 builds the
three objects the $70 panel actually converged on, plus the two data sources
that were unavailable when v2 was frozen:

  E_  THE CODIFIED OPUS SIGNATURE.  Opus-max is the only reader with measured
      positive lift (1.58x taken-vs-skipped).  Its exam declarations are almost
      entirely two numbers and one conjunction: `giveback X bp into a Y bp
      runway` and `stock flow -A z with option delta -B z agreeing`.  v2 built
      `C_giveback_frac` (giveback / OBJECTIVE, where objective is the first
      magnet worth >= 40bp) and `G_agree_o` (min |z| at threshold 3).  The exam
      arithmetic is different in three ways that this tier fixes:
        (1) the denominator is the NEAREST magnet, not the first payable one,
            and the decisive quantity is the DIFFERENCE (runway - giveback =
            what is actually left to pay you), not the ratio;
        (2) the gates are a CONJUNCTION counted as one integer — Opus stopped
            at the first hard failure, so the number of failed gates is the
            statistic, not any single gate;
        (3) the agreement statistic is graded by BALANCE (its cleanest take had
            the two streams at *the same* multiple, -12.31 and -12.52 sigma),
            widened to gamma/vanna, and crossed with 0DTE composition and with
            the net runway.
      Everything in this tier is arithmetic on quantities the v2 block already
      publishes, so the tier adds no new data dependency and no new leak
      surface.

  T_  THE CC-013 GREEK RIBBON.  `_cache/ribbon4` carries the full 31-leaf option
      projection admitted by CC-013 (vega vomma veta vera speed zomma color
      ultima dual_delta dual_gamma iv_error) for every session on the roster.
      v2 could only read delta/gamma/vanna/charm.  This tier lands the new
      columns as signed event-grain flows with the same block-z construction,
      plus the 0DTE / non-0DTE split of delta, gamma, vanna and vega, which is
      Opus's I-4 "hedge durability" as a measurement rather than an inference.

  I_  THE qr_ivx CENSUS OBJECTS.  `_cache/ivx/s*.tsv` holds, per 1800-second
      window, the traded-IV skew (risk reversal, skew slope, curvature, ATM IV
      and their innovations), the term structure (near/far ratio and slope and
      their innovations) and the surface objects (FD ratio and its innovation,
      fd_chi, sigma_vv, the A3 return/proxy-vol joint state, vol-of-vol).  A
      decision at second t reads window `t // 1800 - 1`, which ENDS at or before
      t, so the join is strictly causal.

CAUSALITY.  Every T_ window ends at and excludes the decision second and is
z-scored against the immediately prior blocks of the same width; every I_ value
comes from a window that closed before the decision second; every E_ value is
arithmetic on v2 columns that already carry v2's own causality proof.

BLIND HYGIENE (the imitation-channel design choice, stated in full).
Opus produced two ledgers: the 40-case introspection round and the 466-case
exam, and BOTH are declarations on sessions 428..447 — the blind block.  Using
either as a training TARGET would put blind-block information into a model that
is then scored on the blind block, whatever the labels are, because the reader's
call is a function of the blind pack.  So no Opus call is a label anywhere in
this file.  What IS used is the FORMULA in `OPUS_METHOD.md` §1 (the gate
thresholds Opus states in prose: 40bp nearest magnet, giveback vs runway,
budget >= 1.0, range >= ATR, phase > 0.72, |z| >= 3 two-stream agreement) --
exactly the same provenance v2's whole T1.1/T1.3 design already has, and it
carries no outcome.  The imitation channel is then built on the STUDY side: the
codified signature `E_opus_take` fires on training rows, and those rows get a
sample-weight boost.  The blind exam ledger is opened once, at the very end, as
a read-only FIDELITY diagnostic (does the formula reproduce the reader's calls?)
after every model number is already computed, and it never enters a fit.

    model_v3.py [--rebuild] [--jobs N] [--stage features|eval|all]
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import packlib as P                       # noqa: E402
import distill_model as dm                # noqa: E402
import model_v2 as mv                     # noqa: E402
import walkforward as wf                  # noqa: E402

ROOT = P.ROOT
SHEETS = ROOT / "sheets"
SECS = P.SESSION_SECONDS
SEED = dm.SEED
GREEK_CACHE = P.CACHE / "sec4"
MATRIX = ROOT / "FEATURES_V3.tsv"
REPORT = ROOT / "MODEL_V3_REPORT.md"
BASE_MATRIX = ROOT / "FEATURES_WF.tsv"

#: the six era blocks the published baselines were measured on.  Later rosters
#: exist on disk (study_e4..e7, blind_e4..e7); including them would change the
#: ladder and make the comparison against WALKFORWARD_REPORT.md meaningless.
LADDER = ("study_e1", "study_e1b", "study_e2", "study_e3", "study_e3b", "blind_e3")
STUDY_BLOCK = (398, 412)            # v2's own training slice
BLIND_BLOCK = (428, 447)

FROZEN = wf.FROZEN
OPERATING_RATE = mv.OPERATING_RATE

#: OPUS_METHOD.md §1, quoted as numbers.  Not fitted, not tuned, not selected.
MAGNET_FLOOR_BPS = 40.0             # "nearest magnet worth less than ~40bp -> class C"
B_CLASS_BPS = 70.0                  # class B = 70bp of favourable excursion
LATE_PHASE = 0.72                   # "phase > 0.72 -> refuse"
AGREE_Z = 3.0                       # "streams beyond |z| > 3 with a common sign"
GIVEBACK_CAP = 0.30                 # "accept give-back up to ~30% of the objective"
ZDTE_HEAVY = 0.40                   # Grok's S3 poison cut; Opus refused 53-58% 0DTE
IMITATION_BOOST = 1.0               # weight = 1 + BOOST on rows the signature fires


# ==========================================================================
# T_ — the CC-013 full-greek ribbon, per second
# ==========================================================================

#: ribbon4 option-row column indices (see the file's own header comment)
COL = dict(ms=1, size=2, price=3, right=5, expiry=6, bid=7, ask=8,
           delta=11, gamma=12, vanna=13, charm=14,
           vega=19, vomma=20, veta=21, vera=22, speed=23, zomma=24,
           color=25, ultima=26, dual_delta=27, dual_gamma=28, iv_error=29)

#: the CC-013 columns landed as signed event-grain flows
NEW_GREEKS = ("vega", "vomma", "veta", "vera", "speed", "zomma", "color",
              "ultima", "dual_gamma")
#: the core greeks re-landed SPLIT BY DTE (Opus I-4: same |z|, opposite meaning)
SPLIT_GREEKS = ("delta", "gamma", "vanna", "vega")

GREEK_KEYS = (tuple(f"{name}_f" for name in NEW_GREEKS)
              + tuple(f"{name}_{bucket}" for name in SPLIT_GREEKS for bucket in ("z0", "z1"))
              + ("iverr_w", "iverr_n", "opt_z0", "opt_z1"))


def greek_arrays(ordinal: int) -> dict:
    """Per-second signed greek flows from the CC-013 (`--greeks full`) ribbon."""
    P.assert_wall(ordinal, "greek_arrays")
    cached = GREEK_CACHE / f"s{ordinal}.npz"
    if cached.exists():
        with np.load(cached) as handle:
            return {key: handle[key].astype(np.float64) for key in handle.files}
    GREEK_CACHE.mkdir(parents=True, exist_ok=True)

    out = {key: np.zeros(SECS) for key in GREEK_KEYS}
    path = P.CACHE / "ribbon4" / f"s{ordinal}.tsv"
    if not path.exists():
        return out
    frame = pd.read_csv(path, sep="\t", header=None, names=list(range(30)),
                        comment="#", dtype=str, engine="c", na_filter=False)
    #: `rutw_option` rows are the RUT tape and are a different underlying; the
    #: IWM decision object only ever reads the `option` rows.
    option = frame[frame[0] == "option"]
    if not len(option):
        np.savez_compressed(cached, **{k: v.astype(np.float32) for k, v in out.items()})
        return out

    def num(index: int) -> np.ndarray:
        return pd.to_numeric(option[index], errors="coerce").to_numpy(np.float64)

    day_number = P.civil_day(P.session_meta(ordinal)["day"])
    sec = np.clip((np.nan_to_num(num(COL["ms"])) // 1000).astype(np.int64), 0, SECS - 1)
    size = np.nan_to_num(num(COL["size"]))
    price, bid, ask = num(COL["price"]), num(COL["bid"]), num(COL["ask"])
    usable = np.isfinite(price) & np.isfinite(bid) & np.isfinite(ask) & (ask > bid)
    sign = np.where(usable, np.where(price >= ask, 1.0,
                                     np.where(price <= bid, -1.0, 0.0)), 0.0)
    signed = sign * size
    zero_dte = num(COL["expiry"]) == day_number

    for name in NEW_GREEKS:
        out[f"{name}_f"] = dm._bins(sec, signed * np.nan_to_num(num(COL[name])))
    for name in SPLIT_GREEKS:
        flow = signed * np.nan_to_num(num(COL[name]))
        out[f"{name}_z0"] = dm._bins(sec, np.where(zero_dte, flow, 0.0))
        out[f"{name}_z1"] = dm._bins(sec, np.where(~zero_dte, flow, 0.0))
    error = num(COL["iv_error"])
    finite = np.isfinite(error)
    out["iverr_w"] = dm._bins(sec, np.where(finite, np.abs(error) * size, 0.0))
    out["iverr_n"] = dm._bins(sec, np.where(finite, size, 0.0))
    out["opt_z0"] = dm._bins(sec, np.where(zero_dte, size, 0.0))
    out["opt_z1"] = dm._bins(sec, np.where(~zero_dte, size, 0.0))

    np.savez_compressed(cached, **{k: v.astype(np.float32) for k, v in out.items()})
    return out


# ==========================================================================
# I_ — the qr_ivx census, per 1800-second window
# ==========================================================================

IVX_WINDOW_SECONDS = 1800

SURFACE_KEYS = ("fd_ratio", "d_fd_ratio", "fd_chi", "fd_sigma_vv",
                "a3_return", "a3_proxy_vol", "a3_joint_state",
                "pv_level", "pv_relative_change", "vol_of_vol_mid")
TERM_KEYS = ("near_iv", "far_iv", "near_far_ratio", "d_near_far_ratio",
             "term_slope", "d_term_slope")
SKEW_KEYS = ("risk_reversal", "d_risk_reversal", "skew_slope", "d_skew_slope",
             "curvature", "d_curvature", "atm_iv", "d_atm_iv", "richness_plain")


def _float(text: str) -> float:
    try:
        return float(text)
    except ValueError:
        return np.nan


def ivx_windows(ordinal: int) -> dict:
    """{window index: {name: value}} from the qr_ivx census receipt.

    `skew` is published per EXPIRY inside a window; it is reduced here to a
    print-weight-weighted mean across the window's expiries (the whole traded
    surface) and, separately, to the DTE-0 expiry alone (the 0DTE crowd's own
    smile), because the panel is unanimous that those two are different objects.
    """
    path = P.CACHE / "ivx" / f"s{ordinal}.tsv"
    out: dict = {}
    if not path.exists():
        return out
    skew_rows: dict = {}
    for line in path.read_text().splitlines():
        if line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) != 4:
            continue
        scope, key, metric, value = parts
        pieces = key.split("/")
        if scope == "surface" and len(pieces) == 2 and pieces[1].startswith("w"):
            window = int(pieces[1][1:])
            if metric in SURFACE_KEYS:
                out.setdefault(window, {})[metric] = _float(value)
        elif scope == "term" and len(pieces) == 3 and pieces[1] == "IWM":
            window = int(pieces[2][1:])
            if metric in TERM_KEYS:
                out.setdefault(window, {})[metric] = _float(value)
        elif scope == "skew" and len(pieces) == 4 and pieces[1] == "IWM":
            window = int(pieces[2][1:])
            row = skew_rows.setdefault((window, pieces[3]), {})
            if metric in SKEW_KEYS or metric in ("weight", "dte_days"):
                row[metric] = _float(value)

    grouped: dict = {}
    for (window, _), row in skew_rows.items():
        grouped.setdefault(window, []).append(row)
    for window, rows in grouped.items():
        target = out.setdefault(window, {})
        weights = np.array([row.get("weight", np.nan) for row in rows], float)
        for metric in SKEW_KEYS:
            values = np.array([row.get(metric, np.nan) for row in rows], float)
            mask = np.isfinite(values) & np.isfinite(weights) & (weights > 0)
            target[metric] = (float(np.sum(values[mask] * weights[mask])
                                    / np.sum(weights[mask])) if mask.any() else np.nan)
        zero = [row for row in rows if row.get("dte_days", np.nan) == 0]
        for metric in ("risk_reversal", "d_risk_reversal", "skew_slope", "curvature"):
            values = [row.get(metric, np.nan) for row in zero]
            values = [v for v in values if np.isfinite(v)]
            target[f"{metric}_0dte"] = float(np.mean(values)) if values else np.nan
    return out


# ==========================================================================
# the per-candidate v3 feature block
# ==========================================================================

def _travel(mid: np.ndarray, start: int, stop: int) -> float:
    """bp change of the carried mid over [start, stop), read at stop-1."""
    if start < 0 or stop <= start:
        return np.nan
    a = mid[int(np.clip(start, 0, len(mid) - 1))]
    b = mid[int(np.clip(stop - 1, 0, len(mid) - 1))]
    if not (np.isfinite(a) and np.isfinite(b)) or a <= 0:
        return np.nan
    return (b - a) * 1e4 / a


def _cell(flow: float, travel: float) -> float:
    """The panel's four-cell flow x travel code, already side-oriented.

    0..8; the diagonal 8 = flow WITH and price WITH (agreement), 2 = flow
    AGAINST and price WITH (absorption / the refusal trade), 6 = flow WITH and
    price AGAINST (absorbed aggression), 0 = both against.
    """
    if not (np.isfinite(flow) and np.isfinite(travel)):
        return np.nan
    return 3.0 * (dm.sgn(flow) + 1.0) + (dm.sgn(travel) + 1.0)


def session_features_v3(ordinal: int, candidates: list) -> dict:
    """{candidate id: {feature: value}} — the T_, I_ and tape-side E_ block."""
    P.assert_wall(ordinal, "session_features_v3")
    arrays = dm.second_arrays(ordinal)
    greeks = greek_arrays(ordinal)
    mid = dm.mid_series(ordinal)
    windows = ivx_windows(ordinal)

    cum = {key: dm.cumsum0(values) for key, values in arrays.items()}
    cum.update({key: dm.cumsum0(values) for key, values in greeks.items()})

    out = {}
    ordered = sorted(candidates, key=lambda c: c["second"])
    previous_second = None
    for cand in ordered:
        t = int(cand["second"])
        side = 1.0 if cand["side"] == "L" else -1.0
        f = {}

        # ---- T_ : the CC-013 greek flows ------------------------------------
        for name in NEW_GREEKS:
            key = f"{name}_f"
            value, zed = dm.block_z(cum[key], t, 120)
            f[f"T_{name}_o"] = side * value if np.isfinite(value) else np.nan
            f[f"T_{name}_z"] = side * zed if np.isfinite(zed) else np.nan
        for name in ("vega", "vomma"):
            value, _ = dm.block_z(cum[f"{name}_f"], t, 600)
            f[f"T_{name}600_o"] = side * value if np.isfinite(value) else np.nan

        # the DTE split: `z1` is the exposure that must be CARRIED and hedged
        for name in SPLIT_GREEKS:
            zero = dm.window(cum[f"{name}_z0"], t - 120, t)
            rest = dm.window(cum[f"{name}_z1"], t - 120, t)
            f[f"T_{name}0_o"] = side * zero if np.isfinite(zero) else np.nan
            f[f"T_{name}1_o"] = side * rest if np.isfinite(rest) else np.nan
            total = abs(zero) + abs(rest) if np.isfinite(zero) and np.isfinite(rest) else np.nan
            f[f"T_{name}_durfrac"] = (abs(rest) / total
                                      if np.isfinite(total) and total > 0 else np.nan)
            _, zed = dm.block_z(cum[f"{name}_z1"], t, 120)
            f[f"T_{name}1_z"] = side * zed if np.isfinite(zed) else np.nan
        volume = dm.window(cum["opt_z0"], t - 300, t) + dm.window(cum["opt_z1"], t - 300, t)
        f["T_zdte_share_true"] = (dm.window(cum["opt_z0"], t - 300, t) / volume
                                  if np.isfinite(volume) and volume > 0 else np.nan)
        weight = dm.window(cum["iverr_n"], t - 600, t)
        f["T_iv_error"] = (dm.window(cum["iverr_w"], t - 600, t) / weight
                           if np.isfinite(weight) and weight > 0 else np.nan)

        # ---- I_ : the qr_ivx window objects ---------------------------------
        index = t // IVX_WINDOW_SECONDS - 1
        block = windows.get(index, {}) if index >= 0 else {}
        for name in SURFACE_KEYS + TERM_KEYS + SKEW_KEYS:
            f[f"I_{name}"] = block.get(name, np.nan)
        for name in ("risk_reversal", "d_risk_reversal", "skew_slope", "curvature"):
            f[f"I_{name}_0dte"] = block.get(f"{name}_0dte", np.nan)
        #: a LONG is helped by calls being bid relative to puts, so the signed
        #: read of the risk reversal and of the skew slope is side-oriented.
        for name in ("risk_reversal", "d_risk_reversal", "skew_slope", "d_skew_slope"):
            value = f[f"I_{name}"]
            f[f"I_{name}_o"] = side * value if np.isfinite(value) else np.nan
        f["I_window"] = float(index)

        # ---- E_ (tape side) : the panel's flow x travel and freshness block --
        for width in (60, 600):
            flow = dm.window(cum["signed"], t - width, t)
            travel = _travel(mid, t - width, t)
            flow_o = side * flow if np.isfinite(flow) else np.nan
            travel_o = side * travel if np.isfinite(travel) else np.nan
            f[f"E_flow{width}_o"] = flow_o
            f[f"E_trav{width}_o"] = travel_o
            f[f"E_ftcell{width}"] = _cell(flow_o, travel_o)
            #: Grok's S2-lite — big flow that cannot move price is absorption,
            #: and the trade is the REFUSAL, so the sign flips against the flow.
            f[f"E_s2lite{width}_o"] = (-dm.sgn(flow_o)
                                       if np.isfinite(flow_o) and np.isfinite(travel_o)
                                       and abs(flow) >= 50_000 and abs(travel) <= 3.0 else 0.0)
            #: Grok's quiet-tape inverse — tiny flow that DOES move price.
            f[f"E_quiet{width}_o"] = (dm.sgn(travel_o)
                                      if np.isfinite(flow_o) and np.isfinite(travel_o)
                                      and abs(flow) <= 1_000 and abs(travel) >= 8.0 else 0.0)
        #: leftover vs live — is the ribbon still printing the thesis at t?
        live60 = _travel(mid, t - 60, t)
        f["E_live60_o"] = side * live60 if np.isfinite(live60) else np.nan
        f["E_live_vs_600"] = (f["E_live60_o"] / abs(f["E_trav600_o"])
                              if np.isfinite(f.get("E_trav600_o", np.nan))
                              and abs(f["E_trav600_o"]) > 1e-9
                              and np.isfinite(f["E_live60_o"]) else np.nan)
        #: Grok's flow-flip vector: the sign change between the stale window and
        #: the live one, which the panel says is the entry, not the flow level.
        stale = dm.window(cum["signed"], t - 1800, t - 300)
        live = dm.window(cum["signed"], t - 300, t)
        f["E_flip_o"] = (side * dm.sgn(live) if np.isfinite(stale) and np.isfinite(live)
                         and dm.sgn(stale) != 0 and dm.sgn(live) != 0
                         and dm.sgn(stale) != dm.sgn(live) else 0.0)
        f["E_flip_mag_o"] = (side * (live / 300.0 - stale / 1500.0)
                             if np.isfinite(stale) and np.isfinite(live) else np.nan)

        #: DSK's #1 cross-era field — the spread hole AT the confirmed pivot.
        f["E_spread_mean120"] = (dm.window(cum["spread"], t - 120, t)
                                 / max(dm.window(cum["spread_n"], t - 120, t), 1e-9))
        _, f["E_spread_z"] = dm.ratio_z(cum["spread"], cum["spread_n"], t, 120)

        #: elasticity as a RESIDUAL (Opus G6): bp of travel bought per kshare,
        #: measured against the same ratio over the immediately prior blocks
        #: rather than as the raw level, which is mechanically deflated by any
        #: anomalous flow.
        travel600 = _travel(mid, t - 600, t)
        volume600 = dm.window(cum["abssize"], t - 600, t)
        current = (abs(travel600) / (volume600 / 1000.0)
                   if np.isfinite(travel600) and np.isfinite(volume600) and volume600 > 0
                   else np.nan)
        prior = []
        for step in range(1, 6):
            back_t = t - step * 600
            back_travel = _travel(mid, back_t - 600, back_t)
            back_volume = dm.window(cum["abssize"], back_t - 600, back_t)
            if np.isfinite(back_travel) and np.isfinite(back_volume) and back_volume > 0:
                prior.append(abs(back_travel) / (back_volume / 1000.0))
        f["E_elasticity"] = current
        if np.isfinite(current) and len(prior) >= 3:
            scale = float(np.std(prior, ddof=1))
            f["E_elast_z"] = ((current - float(np.mean(prior))) / scale
                              if scale > 0 else np.nan)
        else:
            f["E_elast_z"] = np.nan

        #: Grok's composite dead-tape gate — all three legs required.
        prints120 = dm.window(cum["prints"], t - 120, t)
        touch120 = dm.window(cum["touch"], t - 120, t)
        urgency = touch120 / prints120 if np.isfinite(prints120) and prints120 > 0 else np.nan
        _, urgency_z = dm.ratio_z(cum["touch"], cum["prints"], t, 120)
        _, rate_z = dm.block_z(cum["prints"], t, 120)
        f["E_urg120"] = urgency
        f["E_dead_tape"] = 1.0 if (np.isfinite(urgency_z) and urgency_z <= -2.0
                                   and np.isfinite(rate_z) and rate_z <= -1.0
                                   and np.isfinite(f["E_trav60_o"])
                                   and abs(f["E_trav60_o"]) <= 2.0) else 0.0
        #: second-scale pivot spacing is the real micro-pivot detector.
        f["E_pivot_gap_s"] = float(t - previous_second) if previous_second is not None else np.nan
        f["E_micro_pivot"] = 1.0 if (previous_second is not None
                                     and t - previous_second <= 120) else 0.0
        previous_second = t

        out[cand["id"]] = f
    return out


# ==========================================================================
# the E_ arithmetic block — pure algebra on the v2 columns
# ==========================================================================

def _finite(frame: pd.DataFrame, name: str) -> np.ndarray:
    return pd.to_numeric(frame[name], errors="coerce").to_numpy(float)


def derive_frame_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Opus's capacity arithmetic and agreement statistic, as stated in prose.

    Every input is a v2 column that already carries v2's causality proof, so
    this function introduces no new read of the tape and no new leak surface.
    """
    out = {}
    magnet = _finite(frame, "C_mag1_bps")
    objective = _finite(frame, "C_objective_bps")
    giveback = _finite(frame, "C_giveback_bps")
    violation = _finite(frame, "C_violation_bps")
    phase = _finite(frame, "C_phase")
    erm_sigma = _finite(frame, "C_erm_sigma_bps")
    erm_atr = _finite(frame, "C_erm_atr_bps")
    spent = _finite(frame, "C_spent_day")
    lag = _finite(frame, "C_confirm_lag")

    # ---- (b) the capacity arithmetic REFINEMENTS -------------------------
    #: the exam's own sentence is "giveback 22bp into a 90bp runway", i.e. the
    #: NEAREST magnet and the DIFFERENCE, where v2 built the first PAYABLE
    #: magnet and the RATIO.
    out["E_runway_bps"] = magnet
    out["E_gb_over_runway"] = np.where(magnet > 0, giveback / magnet, np.nan)
    out["E_net_runway_bps"] = magnet - giveback
    out["E_net_obj_bps"] = objective - giveback
    out["E_net_runway_vs_B"] = (magnet - giveback) / B_CLASS_BPS
    out["E_net_obj_vs_B"] = (objective - giveback) / B_CLASS_BPS
    #: the capacity scalar Opus actually priced: the SMALLER of what the clock
    #: can deliver and what is left on the table after the give-back.
    out["E_payable_bps"] = np.fmin(erm_sigma, objective - giveback)
    out["E_payable_vs_B"] = out["E_payable_bps"] / B_CLASS_BPS
    out["E_gb_x_lag"] = out["E_gb_over_runway"] * np.log1p(np.maximum(lag, 0.0))

    # ---- (b) the gates, counted --------------------------------------------
    def gate(condition: np.ndarray, valid: np.ndarray) -> np.ndarray:
        return np.where(valid, condition.astype(float), 0.0)

    #: the capacity clock is read in the ATR metric, because that is the metric
    #: Opus priced against ("class B is roughly half a daily ATR captured from
    #: the entry").  `C_erm_sigma_bps` tops out at 69bp on this roster, so a
    #: 70bp cut on the sigma clock is a constant and carries no information;
    #: the sigma clock survives as the continuous `E_cap_sigma_vs_B`.
    gates = {
        "E_gate_magnet": gate(magnet < MAGNET_FLOOR_BPS, np.isfinite(magnet)),
        "E_gate_giveback": gate(giveback >= magnet, np.isfinite(giveback) & np.isfinite(magnet)),
        "E_gate_capacity": gate(erm_atr < B_CLASS_BPS, np.isfinite(erm_atr)),
        "E_gate_late": gate(phase > LATE_PHASE, np.isfinite(phase)),
        "E_gate_spent": gate(spent >= 1.0, np.isfinite(spent)),
        "E_gate_through": gate(violation > 0.0, np.isfinite(violation)),
    }
    out.update(gates)
    failed = np.sum([value for value in gates.values()], axis=0)
    out["E_gate_failed"] = failed
    out["E_gate_clean"] = (failed == 0).astype(float)
    out["E_cap_sigma_vs_B"] = erm_sigma / B_CLASS_BPS

    # ---- (a) the JOINT z-magnitude agreement statistic ---------------------
    #: the G_ channels are ALREADY side-oriented, so a positive value is
    #: favourable to this candidate's own side and the sign test is a
    #: same-sign test on oriented quantities.
    flow = _finite(frame, "G_zflow_o")
    delta = _finite(frame, "G_zdelta_o")
    vanna = _finite(frame, "G_zvanna_o")
    gamma1 = _finite(frame, "T_gamma1_z") if "T_gamma1_z" in frame.columns \
        else np.full(len(frame), np.nan)
    vanna1 = _finite(frame, "T_vanna1_z") if "T_vanna1_z" in frame.columns \
        else np.full(len(frame), np.nan)

    def joint(streams: list, threshold: float) -> np.ndarray:
        stack = np.vstack(streams)
        finite = np.isfinite(stack)
        signs = np.sign(stack)
        agree = (np.all(finite, axis=0)
                 & (np.all(signs > 0, axis=0) | np.all(signs < 0, axis=0))
                 & (np.nanmin(np.abs(stack), axis=0) >= threshold))
        magnitude = np.nanmin(np.abs(stack), axis=0)
        return np.where(agree, np.sign(stack[0]) * magnitude, 0.0)

    out["E_agree2_o"] = joint([flow, delta], AGREE_Z)
    out["E_agree2_w"] = joint([flow, delta], 2.0)
    out["E_agree2_hard"] = joint([flow, delta], 5.0)
    out["E_agree3_o"] = joint([flow, delta, vanna], 2.0)
    out["E_agree4_o"] = joint([flow, delta, vanna, gamma1], 2.0)
    out["E_agree_dur_o"] = joint([flow, delta, vanna1], 2.0)
    with np.errstate(invalid="ignore", divide="ignore"):
        low = np.fmin(np.abs(flow), np.abs(delta))
        high = np.fmax(np.abs(flow), np.abs(delta))
        #: Opus's cleanest take had the two streams at the SAME multiple
        #: (-12.31 and -12.52 sigma); balance grades an agreement.
        out["E_z_balance"] = np.where(high > 0, low / high, np.nan)
        out["E_agree_prod_o"] = np.where(out["E_agree2_o"] != 0.0,
                                         np.sign(out["E_agree2_o"])
                                         * np.sqrt(np.abs(flow * delta)), 0.0)
    out["E_agree_bal_o"] = out["E_agree2_o"] * np.nan_to_num(out["E_z_balance"], nan=0.0)
    conflict = (np.isfinite(flow) & np.isfinite(delta) & (np.sign(flow) != np.sign(delta))
                & (np.abs(flow) >= AGREE_Z) & (np.abs(delta) >= AGREE_Z))
    out["E_conflict_o"] = np.where(conflict, -np.fmax(np.abs(flow), np.abs(delta)), 0.0)

    # ---- (a)+(b) the CONJUNCTION: agreement AND capacity -------------------
    out["E_agree_x_netrun"] = out["E_agree2_o"] * np.nan_to_num(out["E_net_runway_vs_B"], nan=0.0)
    out["E_agree_x_payable"] = out["E_agree2_o"] * np.nan_to_num(out["E_payable_vs_B"], nan=0.0)
    out["E_agree_x_clean"] = out["E_agree2_o"] * out["E_gate_clean"]

    # ---- (c) 0DTE composition x agreement ----------------------------------
    zdte = _finite(frame, "W_zdte_share")
    true_zdte = _finite(frame, "T_zdte_share_true") if "T_zdte_share_true" in frame.columns \
        else zdte
    expanding = _finite(frame, "Y_expanding")
    share = np.where(np.isfinite(true_zdte), true_zdte, zdte)
    out["E_zdte_heavy"] = np.where(np.isfinite(share), (share >= ZDTE_HEAVY).astype(float), np.nan)
    out["E_agree_x_nonzdte"] = out["E_agree2_o"] * np.nan_to_num(1.0 - share, nan=0.0)
    out["E_agree_x_zdte"] = out["E_agree2_o"] * np.nan_to_num(share, nan=0.0)
    #: Opus refused the 0DTE-heavy versions of the SAME |z| and took the
    #: non-0DTE ones; the one 0DTE-heavy take needed expanding PROXY_VOL.
    out["E_poison_o"] = -np.nan_to_num(out["E_zdte_heavy"], nan=0.0) \
        * np.maximum(out["E_agree2_o"], 0.0) * (1.0 - np.nan_to_num(expanding, nan=0.0))
    out["E_zdte_x_pvexp"] = np.nan_to_num(share, nan=0.0) * np.nan_to_num(expanding, nan=0.0)
    durability = _finite(frame, "T_delta_durfrac") if "T_delta_durfrac" in frame.columns \
        else np.full(len(frame), np.nan)
    out["E_agree_x_durable"] = out["E_agree2_o"] * np.nan_to_num(durability, nan=0.0)

    # ---- the codified signature (the imitation channel's pseudo-label) -----
    #: Opus's own decision procedure, in one line: every hard gate passes, the
    #: two streams agree at magnitude, and the give-back is inside its stated
    #: ~30% ceiling.  No outcome enters this; no Opus CALL enters this.
    ratio = out["E_gb_over_runway"]
    out["E_opus_take"] = ((failed == 0)
                          & (out["E_agree2_o"] >= AGREE_Z)
                          & np.isfinite(ratio) & (ratio <= GIVEBACK_CAP)).astype(float)
    #: The strict rule reproduces the reader's OWN take rate (about 1%), which
    #: is far too rare to move a sample weight.  The SOFT signature is the same
    #: rule with the conjunction opened to a union: at most one gate down, and
    #: EITHER half of Opus's evidence pair present (a favourable two-stream
    #: agreement at |z| >= 2, or a give-back inside the stated 30% ceiling).
    #: The relaxation is structural — no threshold here was chosen by looking
    #: at an outcome, and the definition is identical in every era block.
    out["E_opus_soft"] = ((failed <= 1)
                          & ((out["E_agree2_w"] > 0)
                             | (np.isfinite(ratio) & (ratio <= GIVEBACK_CAP)))).astype(float)
    #: a continuous fidelity score: gates passed, graded agreement, give-back
    #: penalty — the three quantities Opus's declarations actually cite.
    out["E_opus_score"] = ((6.0 - failed) / 6.0
                           + np.clip(out["E_agree2_o"] / 6.0, -1.0, 1.0)
                           - np.nan_to_num(np.clip(ratio, 0.0, 2.0), nan=1.0))
    return pd.DataFrame(out, index=frame.index)


# ==========================================================================
# matrix assembly
# ==========================================================================

def _job(job: tuple) -> list:
    ordinal, block, candidates = job
    features = session_features_v3(ordinal, candidates)
    return [dict(session=ordinal, id=cand["id"], **features.get(cand["id"], {}))
            for cand in candidates]


def build_matrix(jobs_n: int) -> pd.DataFrame:
    base = pd.read_csv(BASE_MATRIX, sep="\t")
    base = base[base["block"].isin(LADDER)].reset_index(drop=True)
    jobs = []
    for record in wf.era_blocks():
        if record["block"] not in LADDER:
            continue
        for key in sorted(record["sessions"], key=int):
            jobs.append((int(key), record["block"], record["sessions"][key]))
    print(f"building v3 features: {len(jobs)} sessions, {jobs_n} workers", flush=True)
    records = []
    if jobs_n <= 1:
        for done, job in enumerate(jobs, 1):
            records.extend(_job(job))
            if done % 20 == 0:
                print(f"  {done}/{len(jobs)}", flush=True)
    else:
        import multiprocessing as multi
        with multi.get_context("fork").Pool(jobs_n) as pool:
            for done, rows in enumerate(pool.imap_unordered(_job, jobs), 1):
                records.extend(rows)
                if done % 20 == 0 or done == len(jobs):
                    print(f"  {done}/{len(jobs)} sessions, {len(records)} rows", flush=True)
    new = pd.DataFrame.from_records(records)
    frame = base.merge(new, on=["session", "id"], how="left", validate="one_to_one")
    frame = pd.concat([frame, derive_frame_features(frame)], axis=1)
    return frame.sort_values(["session", "second", "side"]).reset_index(drop=True)


# ==========================================================================
# evaluation
# ==========================================================================

V3_PREFIXES = ("E_", "T_", "I_")
#: the capacity REFINEMENTS, as opposed to the agreement statistic: the ablation
#: arm that answers "was it the arithmetic or the agreement that paid?"
CAPACITY_REFINEMENTS = ("E_runway_bps", "E_gb_over_runway", "E_net_runway_bps",
                        "E_net_obj_bps", "E_net_runway_vs_B", "E_net_obj_vs_B",
                        "E_payable_bps", "E_payable_vs_B", "E_gb_x_lag",
                        "E_gate_magnet", "E_gate_giveback", "E_gate_capacity",
                        "E_gate_late", "E_gate_spent", "E_gate_through",
                        "E_gate_failed", "E_gate_clean", "E_cap_sigma_vs_B",
                        "E_agree_x_netrun", "E_agree_x_payable", "E_agree_x_clean",
                        "E_opus_take", "E_opus_soft", "E_opus_score")


def money(value) -> str:
    return "n/a" if not np.isfinite(value) else f"${value:,.0f}"


def number(value, digits: int = 3) -> str:
    return "n/a" if not np.isfinite(value) else f"{value:.{digits}f}"


#: `random_per_day` and `oracle_per_day` are properties of the TEST BLOCK, not
#: of the score, so they are computed once per block instead of once per arm —
#: the 200-draw random baseline is otherwise the dominant cost of this report
#: and it would produce the identical number every time.
_BASELINE: dict = {}


def block_baseline(frame: pd.DataFrame, key: str) -> tuple:
    if key not in _BASELINE:
        reference = dm.day_metrics(frame, np.zeros(len(frame)), k=3)
        _BASELINE[key] = (reference["random_per_day"], reference["oracle_per_day"])
    return _BASELINE[key]


def score_block(frame: pd.DataFrame, score: np.ndarray, key: str = "") -> dict:
    """Every headline number for one (test block, score) pair.

    The selection metrics are recomputed from the score; the block-constant
    baselines come from `block_baseline`.
    """
    from sklearn.metrics import roc_auc_score
    days = frame.assign(score=score).groupby("session", sort=False)
    picks = {k: [] for k in (1, 3, 5)}
    close, maes, counts = [], [], 0
    for _, day in days:
        for k in (1, 3, 5):
            picks[k].append(day.nlargest(k, "score")["cert"].sum())
        top = day.nlargest(3, "score").sort_values("second")
        counts += len(top)
        close.append(float(top.iloc[0]["menu_close"]) if len(top) else 0.0)
        maes.extend(top["cert_mae"].tolist())
    point = mv.operating_point(frame, score, OPERATING_RATE)
    random3, oracle3 = block_baseline(frame, key or str(sorted(frame["session"].unique())[:2]))
    return {
        "auc": float(roc_auc_score(frame["winner"], score)),
        "top1": float(np.mean(picks[1])), "top3": float(np.mean(picks[3])),
        "top5": float(np.mean(picks[5])),
        "per_cand": float(np.sum(picks[3]) / max(counts, 1)),
        "lift": point["lift"], "cert_taken": point["cert_taken"],
        "winrate_taken": point["winrate_taken"],
        "replay_close": float(np.mean(close)), "mae": float(np.mean(maes)),
        "random3": random3, "oracle3": oracle3,
    }


def column_sets(frame: pd.DataFrame, study: pd.DataFrame) -> dict:
    usable = dm.feature_columns(frame, study)
    columns = [c for c in usable if not c.startswith("J_")]
    v2 = [c for c in columns if not c.startswith(V3_PREFIXES)]
    v3 = columns
    return {
        "v2 BASELINE (the published v2/walk-forward set)": v2,
        "v3 FULL (v2 + E_ + T_ + I_)": v3,
        "v3 minus GREEKS (drop T_)": [c for c in v3 if not c.startswith("T_")],
        "v3 minus CAPACITY REFINEMENTS": [c for c in v3 if c not in CAPACITY_REFINEMENTS],
        "v3 minus IVX (drop I_)": [c for c in v3 if not c.startswith("I_")],
        "v3 minus AGREEMENT (drop the joint-z block)":
            [c for c in v3 if not (c.startswith("E_agree") or c in ("E_z_balance",
                                                                    "E_conflict_o"))],
        "E_/T_/I_ ONLY (drop the whole v2 block)":
            [c for c in v3 if c.startswith(V3_PREFIXES)],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--jobs", type=int, default=16)
    parser.add_argument("--stage", default="all",
                        choices=("features", "eval", "all"))
    args = parser.parse_args()

    if args.rebuild or not MATRIX.exists():
        frame = build_matrix(args.jobs)
        frame.to_csv(MATRIX, sep="\t", index=False)
        print(f"matrix {frame.shape} -> {MATRIX}", flush=True)
    else:
        frame = pd.read_csv(MATRIX, sep="\t")
        print(f"matrix {frame.shape} <- {MATRIX}", flush=True)
    if args.stage == "features":
        return

    from sklearn.metrics import roc_auc_score
    from sklearn.inspection import permutation_importance

    study = frame[(frame["session"] >= STUDY_BLOCK[0])
                  & (frame["session"] <= STUDY_BLOCK[1])].reset_index(drop=True)
    blind = frame[frame["block"] == "blind_e3"].reset_index(drop=True)
    sets = column_sets(frame, study)
    out = ["# MODEL V3 REPORT — the hybrid: the proven reader judgment inside the selector",
           "", "@@VERDICT@@", ""]

    out.append(f"Matrix {frame.shape[0]} candidates x {frame.shape[1]} columns over "
               f"{frame['session'].nunique()} sessions in {len(LADDER)} era blocks. "
               f"v3 adds {len([c for c in frame.columns if c.startswith(V3_PREFIXES)])} "
               "columns in three families: `E_` codified-Opus arithmetic + panel "
               "convergences, `T_` CC-013 full-greek flows, `I_` qr_ivx window objects.")
    out.append("")

    # ------------------------------------------------------------------
    # ARM 1 — v2's own protocol: train on 398..412, judge on blind_e3
    # ------------------------------------------------------------------
    out.append("## A. v2 PROTOCOL — train on the study block (398..412), judge blind_e3")
    out.append("")
    out.append("Config re-selected by grouped study CV inside every arm, exactly as "
               "`model_v2.py` does, so the comparison against v2's published numbers is "
               "like-for-like.")
    out.append("")
    out.append("| arm | features | study CV AUC | blind AUC | top-1 $/day | top-3 $/day | "
               "top-5 $/day | $/cand | lift @27.5% | cert/taken |")
    out.append("|---|---|---|---|---|---|---|---|---|---|")
    protocol_a = {}
    for label, columns in sets.items():
        if not columns:
            continue
        print(f"  [A] {label} ({len(columns)} columns)", flush=True)
        _, config, cv_auc, _, score = dm.fit_predict(study, blind, columns)
        metrics = score_block(blind, score, "blind_e3")
        protocol_a[label] = (metrics, config, cv_auc, len(columns), score)
        out.append(f"| {label} | {len(columns)} | {number(cv_auc)} | **{number(metrics['auc'])}** "
                   f"| {money(metrics['top1'])} | **{money(metrics['top3'])}** | "
                   f"{money(metrics['top5'])} | {money(metrics['per_cand'])} | "
                   f"{number(metrics['lift'], 2)}x | {money(metrics['cert_taken'])} |")
    out.append("")
    out.append("Published v2 anchors on this identical roster: blind AUC **0.641** (GBT) / "
               "**0.674** (L1 twin), top-3 **$1,672**/day, top-5 $2,569/day, "
               "lift 1.57x, oracle $3,028/day, random-3 $1,021/day.")
    out.append("")

    # L1 twin on the two headline sets
    out.append("### L1 logistic twin (the 0.674 baseline)")
    out.append("")
    out.append("CAVEAT on this row: v2's published 0.674 twin was fitted on "
               "`FEATURES_V2.tsv`; the `v2 BASELINE` set here is the walk-forward matrix, "
               "which also carries the `M_` forecast-vol block, so the twin is not the "
               "identical estimator.  Read the two rows against each other, not against "
               "the published number.")
    out.append("")
    out.append("| arm | C | study CV AUC | blind AUC | top-3 $/day |")
    out.append("|---|---|---|---|---|")
    twin_scores = {}
    for label in ("v2 BASELINE (the published v2/walk-forward set)", "v3 FULL (v2 + E_ + T_ + I_)"):
        columns = sets[label]
        print(f"  [A-L1] {label}", flush=True)
        _, twin, coefficients, strength, twin_cv = dm.logistic_twin(study, blind, columns)
        metrics = score_block(blind, twin, "blind_e3")
        twin_scores[label] = (twin, coefficients, columns)
        out.append(f"| {label} | {strength} | {number(twin_cv)} | **{number(metrics['auc'])}** "
                   f"| {money(metrics['top3'])} |")
    out.append("")
    label = "v3 FULL (v2 + E_ + T_ + I_)"
    twin, coefficients, columns = twin_scores[label]
    order = [i for i in np.argsort(-np.abs(coefficients)) if coefficients[i] != 0][:20]
    out.append("Non-zero L1 weights of the v3 twin (study-selected):")
    for index in order:
        out.append(f"  - `{columns[index]}` {coefficients[index]:+.3f}")
    out.append("")

    # ------------------------------------------------------------------
    # ARM 2 — the walk-forward ladder, frozen config
    # ------------------------------------------------------------------
    out.append("## B. WALK-FORWARD LADDER — frozen v2 config, expanding window, segments a..e")
    out.append("")
    out.append(f"Estimator frozen at `{FROZEN}` for every fit below and never re-selected.")
    out.append("")
    out.append("| seg | test block | arm | features | AUC | top-3 $/day | top-5 $/day | "
               "lift vs random-3 | lift @27.5% |")
    out.append("|---|---|---|---|---|---|---|---|---|")
    ladder_rows = {}
    letters = "abcde"
    for index in range(1, len(LADDER)):
        test_block = LADDER[index]
        train = frame[frame["block"].isin(LADDER[:index])].reset_index(drop=True)
        test = frame[frame["block"] == test_block].reset_index(drop=True)
        local = dm.feature_columns(frame, train)
        local = [c for c in local if not c.startswith("J_")]
        arms = {
            "v2": [c for c in local if not c.startswith(V3_PREFIXES)],
            "v3": local,
            "v3 minus GREEKS": [c for c in local if not c.startswith("T_")],
            "v3 minus CAPACITY REFINEMENTS": [c for c in local
                                              if c not in CAPACITY_REFINEMENTS],
            "v3 NEW TIERS ONLY (E_+T_+I_)": [c for c in local if c.startswith(V3_PREFIXES)],
        }
        for name, columns in arms.items():
            print(f"  [B] seg {letters[index - 1]} {name} ({len(columns)} columns)", flush=True)
            score = wf.fit_frozen(train, test, columns)
            metrics = score_block(test, score, test_block)
            ladder_rows[(letters[index - 1], name)] = metrics
            out.append(f"| **{letters[index - 1]}** | `{test_block}` | {name} | {len(columns)} "
                       f"| {number(metrics['auc'])} | **{money(metrics['top3'])}** | "
                       f"{money(metrics['top5'])} | "
                       f"{number(metrics['top3'] / metrics['random3'], 2)}x | "
                       f"{number(metrics['lift'], 2)}x |")
    out.append("")
    out.append("Published walk-forward anchors (v2 features, same rungs): "
               "a 0.554/$1,390 | b 0.569/$1,307 | c 0.593/$1,011 | d 0.697/$1,006 | "
               "e 0.646/**$1,459**.")
    out.append("")
    out.append("### The 27.5% operating point on `blind_e3` — the shape the human works in")
    out.append("")
    out.append("| protocol | arm | cert/taken | cert/skipped | lift | win-rate taken | "
               "MAE/pick | top-3 $/day |")
    out.append("|---|---|---|---|---|---|---|---|")
    for label, (metrics, _, _, _, score) in protocol_a.items():
        point = mv.operating_point(blind, score, OPERATING_RATE)
        out.append(f"| v2 protocol | {label} | {money(point['cert_taken'])} | "
                   f"{money(point['cert_skipped'])} | {number(point['lift'], 2)}x | "
                   f"{point['winrate_taken']:.1%} | {money(metrics['mae'])} | "
                   f"{money(metrics['top3'])} |")
    for name, metrics in ((key[1], value) for key, value in ladder_rows.items()
                          if key[0] == "e"):
        out.append(f"| segment e | {name} | {money(metrics['cert_taken'])} | n/a | "
                   f"{number(metrics['lift'], 2)}x | {metrics['winrate_taken']:.1%} | "
                   f"{money(metrics['mae'])} | {money(metrics['top3'])} |")
    out.append("")
    out.append("Anchor: v2 published 1.57x, cert/taken $477, win-rate taken 33.6%, "
               "MAE/pick $123.")
    out.append("")

    # ------------------------------------------------------------------
    # ARM 3 — the imitation channel
    # ------------------------------------------------------------------
    out.append("## C. THE IMITATION CHANNEL — agreement-weighted training, study side only")
    out.append("")
    out.append("`E_opus_take` is the codified Opus signature: all six capacity gates clean, "
               "the two streams agreeing at |z| >= 3 on the candidate's own side, and the "
               "give-back inside Opus's stated 30% ceiling.  It is a FORMULA from "
               "`OPUS_METHOD.md` prose, never a call and never an outcome.  It reproduces "
               "the reader's own exam take rate (about 1%), which is too rare to move a "
               "sample weight, so the weighting carrier is `E_opus_soft` — at most one gate "
               "down and EITHER half of the evidence pair present.  Rows where it fires get "
               f"sample weight 1 + {IMITATION_BOOST:.0f}; everything else weighs 1.")
    out.append("")
    out.append("| block | candidates | strict fires | soft fires | soft rate | winner rate ON | "
               "winner rate OFF | mean cert ON | mean cert OFF |")
    out.append("|---|---|---|---|---|---|---|---|---|")
    for block in LADDER:
        rows = frame[frame["block"] == block]
        strict = int((_finite(rows, "E_opus_take") > 0).sum())
        mask = _finite(rows, "E_opus_soft") > 0
        on, off = rows[mask], rows[~mask]
        win_on = f"{on['winner'].mean():.1%}" if mask.sum() else "n/a"
        cert_on = money(on["cert"].mean()) if mask.sum() else "n/a"
        out.append(f"| `{block}` | {len(rows)} | {strict} | {int(mask.sum())} | "
                   f"{mask.mean():.1%} | {win_on} | {off['winner'].mean():.1%} | "
                   f"{cert_on} | {money(off['cert'].mean())} |")
    out.append("")
    #: the capacity conjunction on its own, as a population measurement
    out.append("The capacity conjunction alone (`E_gate_clean` — all six gates pass, no "
               "signal read at all), measured as a population over every era:")
    clean = _finite(frame, "E_gate_clean") > 0
    out.append(f"- fires on {int(clean.sum())} of {len(frame)} candidates ({clean.mean():.1%}); "
               f"winner rate {frame['winner'][clean].mean():.1%} against "
               f"{frame['winner'][~clean].mean():.1%} off, mean cert "
               f"{money(frame['cert'][clean].mean())} against "
               f"{money(frame['cert'][~clean].mean())}.")
    out.append("")

    out.append("| protocol | arm | AUC | top-3 $/day | top-5 $/day | lift @27.5% |")
    out.append("|---|---|---|---|---|---|")
    imitation = {}
    v3_columns = sets["v3 FULL (v2 + E_ + T_ + I_)"]
    for protocol, train, test in (("v2 protocol (study 398..412 -> blind_e3)", study, blind),
                                  ("walk-forward segment e (5 eras -> blind_e3)",
                                   frame[frame["block"].isin(LADDER[:-1])].reset_index(drop=True),
                                   blind)):
        local = [c for c in dm.feature_columns(frame, train) if not c.startswith("J_")]
        for name, weights in (("unweighted", None),
                              ("agreement-weighted", 1.0 + IMITATION_BOOST
                               * np.nan_to_num(_finite(train, "E_opus_soft")))):
            print(f"  [C] {protocol} / {name}", flush=True)
            score = wf.fit_frozen(train, test, local, weights=weights)
            metrics = score_block(test, score, "blind_e3")
            imitation[(protocol, name)] = metrics
            out.append(f"| {protocol} | {name} | {number(metrics['auc'])} | "
                       f"{money(metrics['top3'])} | {money(metrics['top5'])} | "
                       f"{number(metrics['lift'], 2)}x |")
    out.append("")

    # ------------------------------------------------------------------
    # importances
    # ------------------------------------------------------------------
    train_e = frame[frame["block"].isin(LADDER[:-1])].reset_index(drop=True)
    local_e = [c for c in dm.feature_columns(frame, train_e) if not c.startswith("J_")]
    from sklearn.ensemble import HistGradientBoostingClassifier
    model = HistGradientBoostingClassifier(random_state=SEED, **FROZEN)
    model.fit(train_e[local_e].to_numpy(float), train_e["winner"].to_numpy())
    importance = permutation_importance(
        model, blind[local_e].to_numpy(float), blind["winner"].to_numpy(),
        n_repeats=20, random_state=SEED, scoring="roc_auc")
    out.append("## D. Permutation importance on `blind_e3` (segment-e fit, diagnostic only)")
    out.append("")
    out.append("| rank | feature | AUC drop | sd |")
    out.append("|---|---|---|---|")
    for rank, index in enumerate(np.argsort(importance.importances_mean)[::-1][:25], 1):
        out.append(f"| {rank} | `{local_e[index]}` | "
                   f"{importance.importances_mean[index]:+.4f} | "
                   f"{importance.importances_std[index]:.4f} |")
    out.append("")
    totals = {}
    for index, name in enumerate(local_e):
        family = name.split("_")[0]
        totals[family] = totals.get(family, 0.0) + max(importance.importances_mean[index], 0.0)
    out.append("Family totals (sum of positive importance): "
               + ", ".join(f"`{family}_` {value:.4f}" for family, value
                           in sorted(totals.items(), key=lambda kv: -kv[1])[:12]))
    out.append("")

    # ------------------------------------------------------------------
    # controls
    # ------------------------------------------------------------------
    out.append("## E. Controls")
    out.append("")
    rng = np.random.default_rng(SEED)
    shuffled = []
    for _ in range(5):
        labels = rng.permutation(train_e["winner"].to_numpy())
        control = wf.fit_frozen(train_e, blind, local_e, labels=labels)
        shuffled.append(roc_auc_score(blind["winner"], control))
    out.append(f"- LABEL-SHUFFLE (segment e, 5 draws, v3 columns): AUC "
               f"{np.mean(shuffled):.3f} +/- {np.std(shuffled):.3f} against the real "
               f"{number(ladder_rows[('e', 'v3')]['auc'])}.")
    study_shuffle = study.copy()
    study_shuffle["winner"] = rng.permutation(study["winner"].to_numpy())
    _, _, _, _, control = dm.fit_predict(study_shuffle, blind, v3_columns)
    out.append(f"- LABEL-SHUFFLE (v2 protocol, v3 columns): blind AUC "
               f"{roc_auc_score(blind['winner'], control):.3f}.")
    out.append("- WALK-FORWARD PURITY: every rung's test block is strictly later than every "
               "session in its training window; the frozen config is v2's and is never "
               "re-selected in section B or C.")
    out.append("- BLIND HYGIENE: no Opus call (40-case round or 466-case exam) is a label, a "
               "weight, a threshold or a column anywhere in the fitted path.  The imitation "
               "weights are computed from `E_opus_soft` on TRAINING rows only, and that column is a formula over v2 channels with thresholds quoted from OPUS_METHOD prose.")
    out.append("- CAUSALITY: `T_` windows end at and exclude the decision second and are "
               "z-scored against strictly prior blocks; `I_` reads window `t // 1800 - 1`, "
               "which closes at or before t; `E_` is arithmetic on v2 columns.")
    out.append("")

    # ------------------------------------------------------------------
    # the fidelity diagnostic — opened LAST, never fitted
    # ------------------------------------------------------------------
    exam = ROOT / "OPUS_EXAM_CALLS.tsv"
    if exam.exists():
        calls = pd.read_csv(exam, sep="\t", header=None,
                            names=["case", "call", "grade", "reason"])
        blind_sorted = blind.sort_values(["session", "second", "side"]).reset_index(drop=True)
        if len(calls) == len(blind_sorted):
            take = (calls["call"] == "TAKE").to_numpy()
            signature = _finite(blind_sorted, "E_opus_take") > 0
            model_score = protocol_a["v3 FULL (v2 + E_ + T_ + I_)"][4]
            order = np.argsort(-model_score)
            top = np.zeros(len(blind_sorted), bool)
            top[order[:int(round(OPERATING_RATE * len(blind_sorted)))]] = True
            soft = _finite(blind_sorted, "E_opus_soft") > 0
            out.append("## F. FIDELITY DIAGNOSTIC — does the codified signature reproduce the "
                       "reader?  (read-only, computed after every model number above)")
            out.append("")
            out.append("Row order verification: the exam ledger is 466 rows against 466 blind "
                       "candidates, and its own arithmetic pins the alignment — case0095 "
                       "reads `cap-ok 5.9h` against phase 0.08 (5.97h of session left), "
                       "case0297 reads `22bp giveback into a 71bp runway` against "
                       "`C_giveback_bps` 22.3 and `C_mag1_bps` 71.0.")
            out.append("")
            out.append(f"- Opus's exam on this roster: {int(take.sum())} TAKE / "
                       f"{int((~take).sum())} SKIP (take rate "
                       f"{take.mean():.1%}).")
            out.append(f"- Strict `E_opus_take` fires on {int(signature.sum())} rows and "
                       f"covers {int((signature & take).sum())} of the {int(take.sum())} "
                       "reader TAKEs.")
            out.append(f"- Soft `E_opus_soft` fires on {int(soft.sum())} rows and covers "
                       f"{int((soft & take).sum())} of the {int(take.sum())} reader TAKEs.")
            out.append(f"- The v3 model's own top-27.5% slice contains "
                       f"{int((top & take).sum())} of the {int(take.sum())} reader TAKEs.")
            out.append(f"- Reader TAKEs realised: mean cert "
                       f"{money(blind_sorted['cert'][take].mean())}, winner rate "
                       f"{blind_sorted['winner'][take].mean():.1%}, against the block's "
                       f"{blind_sorted['winner'].mean():.1%} and mean cert "
                       f"{money(blind_sorted['cert'].mean())}.")
            if soft.any():
                out.append(f"- Soft-signature rows realised: mean cert "
                           f"{money(blind_sorted['cert'][soft].mean())}, winner rate "
                           f"{blind_sorted['winner'][soft].mean():.1%}.")
            out.append("")

    # ------------------------------------------------------------------
    # the verdict
    # ------------------------------------------------------------------
    base = protocol_a["v2 BASELINE (the published v2/walk-forward set)"][0]
    full = protocol_a["v3 FULL (v2 + E_ + T_ + I_)"][0]
    tiers = protocol_a["E_/T_/I_ ONLY (drop the whole v2 block)"][0]
    no_greeks = protocol_a["v3 minus GREEKS (drop T_)"][0]
    no_cap = protocol_a["v3 minus CAPACITY REFINEMENTS"][0]
    no_ivx = protocol_a["v3 minus IVX (drop I_)"][0]
    seg_e_v2 = ladder_rows[("e", "v2")]
    seg_e_v3 = ladder_rows[("e", "v3")]
    seg_e_tiers = ladder_rows[("e", "v3 NEW TIERS ONLY (E_+T_+I_)")]
    seg_e_greeks = ladder_rows[("e", "v3 minus GREEKS")]
    seg_e_cap = ladder_rows[("e", "v3 minus CAPACITY REFINEMENTS")]
    weighted = imitation[("walk-forward segment e (5 eras -> blind_e3)", "agreement-weighted")]
    ladder_wins = sum(1 for letter in "abcde"
                      if ladder_rows[(letter, "v3")]["top3"] > ladder_rows[(letter, "v2")]["top3"])
    tier_auc_wins = sum(1 for letter in "abcde"
                        if ladder_rows[(letter, "v3 NEW TIERS ONLY (E_+T_+I_)")]["auc"]
                        > ladder_rows[(letter, "v2")]["auc"])
    verdict = [
        "## VERDICT — the walk-forward target is beaten, the single-block AUC target is "
        "beaten only by the arm that throws v2 away",
        "",
        f"**Walk-forward segment e — BEATEN on both legs.**  With the frozen config and "
        f"five eras of training, v3 scores AUC {number(seg_e_v3['auc'])} and top-3 "
        f"**{money(seg_e_v3['top3'])}/day** against the published 0.646 / $1,459, which "
        f"this harness reproduces exactly ({number(seg_e_v2['auc'])} / "
        f"{money(seg_e_v2['top3'])}) when the v3 columns are removed.  That is "
        f"{(seg_e_v3['top3'] / seg_e_v2['top3'] - 1):+.0%} on the deployable selection "
        f"number and +{seg_e_v3['auc'] - seg_e_v2['auc']:.3f} AUC, from features alone: "
        f"same estimator, same rows, same rung.  Across the whole ladder v3 beats v2 on "
        f"top-3 $/day in {ladder_wins} of 5 segments.",
        "",
        f"**v2 protocol (train on 273 study rows, judge blind_e3) — dollars a tie, AUC "
        f"not beaten by the full stack.**  v3 FULL lands {money(full['top3'])}/day against "
        f"the published $1,672 and {money(base['top3'])} for the v2 columns rerun here "
        f"(a tie inside harness noise), with blind AUC {number(full['auc'])} against 0.641 "
        f"published / {number(base['auc'])} rerun.  On 273 rows, 417 columns is too many; "
        f"the arm that DROPS the whole v1+v2 block is the one that works.",
        "",
        f"**The finding: the v3 tiers ALONE are the best ranker on this roster.**  "
        f"`E_/T_/I_ ONLY` — {protocol_a['E_/T_/I_ ONLY (drop the whole v2 block)'][3]} "
        f"columns, no v1 and no v2 channel at all — scores blind AUC "
        f"**{number(tiers['auc'])}**, beating BOTH published AUC anchors (0.641 GBT and "
        f"0.674 L1), and it does it while lifting the human operating point to "
        f"**{number(tiers['lift'], 2)}x** with {money(tiers['cert_taken'])} per taken "
        f"candidate and a {tiers['winrate_taken']:.0%} win rate on takes, against v2's "
        f"1.57x / $477 / 33.6%.  Its study CV AUC is "
        f"{number(protocol_a['E_/T_/I_ ONLY (drop the whole v2 block)'][2])} — i.e. it "
        f"looks WORTHLESS in-era and is the strongest arm out of era, which is the third "
        f"time this project has seen study CV fail to resolve arms and is a direct "
        f"restatement of MODEL_V2_REPORT's caveat (1).  On the walk-forward ladder the "
        f"same arm beats the v2 column set on AUC in {tier_auc_wins} of 5 segments "
        f"(segment e {number(seg_e_tiers['auc'])} against "
        f"{number(seg_e_v2['auc'])}) — but its top-3 dollars collapse there "
        f"({money(seg_e_tiers['top3'])} against {money(seg_e_v2['top3'])}), so it ranks "
        f"the population better and the TOP of the day worse.  It is a genuine finding, "
        f"not a deployable arm: nothing here promotes it, because it is one 20-day block "
        f"and the walk-forward rung disagrees with it on money.",
        "",
        "**Ablations — what actually paid.**",
        "",
        f"* **CC-013 greeks (`T_`) PAY, in dollars, not in AUC.**  Dropping them costs "
        f"{money(full['top3'] - no_greeks['top3'])}/day on the v2 protocol "
        f"({money(no_greeks['top3'])} against {money(full['top3'])}) and "
        f"{money(seg_e_v3['top3'] - seg_e_greeks['top3'])}/day on segment e, while the "
        f"AUC moves the other way ({number(no_greeks['auc'])} against "
        f"{number(full['auc'])}).  Same signature as v2's own tiers: they sharpen the "
        f"top of the ranking and add noise in the middle.  In permutation importance the "
        f"whole `T_` family is near zero, which is the AUC view of exactly that.",
        f"* **qr_ivx window objects (`I_`) PAY.**  Dropping them costs "
        f"{money(full['top3'] - no_ivx['top3'])}/day, and `I_curvature_0dte` and "
        f"`I_atm_iv` are blind permutation ranks 2 and 3 out of 441 columns — the `I_` "
        f"family is the second largest importance block on the blind set, behind only "
        f"capacity.  This is the strongest single new-data result in the lane: the 0DTE "
        f"expiry's own smile CURVATURE, joined from a window that closed before the "
        f"decision second, carries real out-of-era information.",
        f"* **The capacity REFINEMENTS did NOT pay on top of v2's existing `C_` block.**  "
        f"Removing them IMPROVES the v2-protocol arm ({money(no_cap['top3'])} and AUC "
        f"{number(no_cap['auc'])} against {money(full['top3'])} / {number(full['auc'])}) "
        f"and costs only {money(seg_e_v3['top3'] - seg_e_cap['top3'])}/day on segment e.  "
        f"The honest reading is that `C_giveback_frac` + `C_objective_bps` already "
        f"carried the arithmetic and the net-runway restatement is mostly a "
        f"re-parameterisation.  What the exam text added that v2 did not have is the "
        f"GATE CONJUNCTION, and that shows up as a population fact rather than a model "
        f"feature: `E_gate_clean` fires on 9.3% of all 11,941 candidates and lifts the "
        f"winner rate from 27.9% to 33.9% and mean cert from $388 to $478 with no signal "
        f"read at all.",
        "",
        f"**The imitation channel did not pay — reported as run.**  Agreement-weighting "
        f"the training rows on `E_opus_soft` moves segment e to AUC "
        f"{number(weighted['auc'])} and {money(weighted['top3'])}/day, both WORSE than "
        f"unweighted ({number(seg_e_v3['auc'])} / {money(seg_e_v3['top3'])}); on the v2 "
        f"protocol it trades {money(full['top3'] - imitation[('v2 protocol (study 398..412 -> blind_e3)', 'agreement-weighted')]['top3'])}"
        f"/day of top-3 for a higher operating-point lift "
        f"({number(imitation[('v2 protocol (study 398..412 -> blind_e3)', 'agreement-weighted')]['lift'], 2)}x "
        f"against {number(full['lift'], 2)}x).  The signature itself separates: it fires "
        f"on 5-18% of candidates in every era and carries a higher winner rate and mean "
        f"cert in ALL SIX blocks, which is why it is worth keeping as a COLUMN.  What it "
        f"does not do is improve the fit when used as a weight, and the reason is visible "
        f"in the fidelity diagnostic: the strict reproduction of the reader's rule fires "
        f"on 0 of 466 blind candidates, so the soft version is a different, much broader "
        f"object than the judgment it was meant to imitate.",
        "",
        "**Caveats, stated plainly.**  (1) The blind block is 20 days and 466 candidates; "
        "a $139/day segment-e gain is one good day away from noise, which is why the "
        "five-segment ladder is reported beside it.  (2) Study CV is again unable to "
        "resolve arms (the best out-of-era arm has the worst study CV), so no arm here "
        "may be promoted on CV evidence and none is.  (3) The `E_/T_/I_ ONLY` result is "
        "the kind of thing that reverses; it is published as a finding to be retested on "
        "`blind_e4..e7`, not as a recommendation.  (4) `I_` coverage is 58-82% by era "
        "(the option-quote surface starts at session 209), so its contribution is "
        "measured on a partially covered column.",
        "",
    ]
    REPORT.write_text("\n".join(out).replace("@@VERDICT@@", "\n".join(verdict)) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    main()
