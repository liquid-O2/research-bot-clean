#!/usr/bin/python3
"""PORT M2 — THE GOAL-PATH CENSUSES (1..4).

The measurement lane the user approved after the delay/divergence census closed
negative.  Four censuses share one spine and one report:

  1 AMBIGUITY VETO        two-sidedness of every seat/winner (K* / 2K* nearby,
                          opposite side) -> the one-sided dollar fraction and
                          the veto's cost/benefit.
  2 DAY-SIDE CALL         session-open information -> the day's PAYING side,
                          walk-forward E2..E6, day-clustered, shuffled control.
  3 CLASS-MIX ECONOMICS   per-class seat economics -> the seat-allocation table.
  4 CONFIRMATION-STRENGTH DIRECT ENTRIES (the headline, user-corrected):
        (a) HOLD_T   the reclaimed level HELD T in {60,180,300,600}s with no
                     re-break; entry AT T-expiry, direct at market.
        (b) LEG_R    the reversal leg has travelled R in {0.5,0.75,1.0} x ATR14
                     from the confirmed extreme AND the reclaim held; entry at
                     the threshold-crossing second, direct at market.
        (c) DELAY_D  the committed delay grid D in {0,30,60,120,180,300,600}
                     from the roster's own decision second, direct at market.
      In EVERY variant the stop is STRUCTURAL — {the confirmed extreme, the
      reclaim level} +/- 2 ticks — never the $900 cash wall; the cash risk is
      measured per trade.  Exits: phase-close AND trailing {1, 1.5} x structure.

WHERE EVERY NUMBER COMES FROM (D-006; no second version of anything)
  candidates/outcomes   artifacts/cache/port/m3/matrix/matrix.npz (the committed
                        M3 matrix: 1,399,374 rows, cid = ASSET-d8-dec_sec-L|S)
  roster geometry       assemble.roster (generation_v3 union roster): conf_sec,
                        entry_mid, atr14_usd, fam_mask, phase_close_sec
  the confirmed extreme dec_sec - pivot_age_sec, the committed matrix feature
                        ("dec_sec - pivot_sec of the most recent CAUSAL ZigZag
                        pivot of the faded type", pattern_lib.py:123) -> its
                        price is the SANE mid at that second
  price paths           assemble.load_session -> s.vt / s.vm, the SANE two-sided
                        mid grid.  This IS the grid the m1 tau tensors were
                        built from (artifacts/cache/port/m1/skel: 200 rungs x
                        0.02 ATR); pricing on the grid itself is EXACT and the
                        0.02-ATR rung rounding never enters.  `--tau-proof`
                        reproduces tau_up/tau_dn from the same grid.
  K*                    info_ceiling._kstar (SI 180 / HG 120 / NKD 150)
  bars/ATR              assemble.bars (ATR14_prev_usd, causal)
  costs                 the matrix's own cost_rt column (session median spread
                        + $5.00)
  intervals             day-clustered bootstrap, the draw unit (D-036/D-073)

CLI
  goalpath.py --spine                      stage 0 (the shared spine)
  goalpath.py --ambig                      census 1
  goalpath.py --cont   [--workers 8]       census 4 stage A (paths -> cells)
  goalpath.py --select [--workers 8]       the feature-only selection model
  goalpath.py --dayside                    census 2
  goalpath.py --classmix                   census 3
  goalpath.py --econ                       census 4 economics + stacking
  goalpath.py --verdict                    the stacked-configuration verdict
  goalpath.py --tau-proof                  the m1 tau-tensor identity receipt
"""
import argparse
import json
import math
import os
import sys
import time

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, "/workspace/engine/port_m0", "/workspace/engine/port_m1",
           "/workspace/engine/port_m3", "/workspace/artifacts/cache/pylibs"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import m2_common as MC                    # noqa: E402
import common as C                        # noqa: E402
import census_common as X                 # noqa: E402
import assemble as A                      # noqa: E402

SECTION = ("port m2 goal-path censuses 1-4 (ambiguity veto / day-side call / "
           "class-mix seat economics / confirmation-strength direct entries)")
VERSION = "PORT-M2-GOALPATH-V1"

OUT_ROOT = os.path.join(MC.M2_ROOT, "goalpath")
PROV = "/workspace/provenance/port_m2"
MATRIX_NPZ = "/workspace/artifacts/cache/port/m3/matrix/matrix.npz"
SEED = 20260813                           # the pinned project seed

ERAS_EVAL = (1, 2, 3, 4, 5)               # E2..E6 (m2_common.ERAS indices)
ERA_HEADLINE = 5                          # E6 first, for comparability
TOPN_PER_ASSET_DAY = 3                    # the seat schedule shape (D-046)

WIN_USD = 1000.0                          # D-021 target expectancy
WALL_USD = 900.0                          # the frozen cash wall (walls.json)
BAR_SESSION_USD = 2000.0                  # D-048
BAR_SESSION_THIN_USD = 1500.0             # D-043/D-045 weak-era floor
BAR_TRADE_MIN_USD = 600.0                 # D-021 absolute minimum
VICINITY_ATR = 0.5                        # info_ceiling's pair vicinity

# ------------------------------------------------------------- census 4 grid
HOLD_T = (60, 180, 300, 600)
LEG_R = (0.5, 0.75, 1.0)
DELAY_D = (0, 30, 60, 120, 180, 300, 600)
# THE TREND ARM (user extension, the headline variant): entries WELL after the
# extreme, anchored on the CONFIRMATION second, taken only while the reversal
# is still the prevailing direction (price on the reversal side of the reclaim
# level at t+D), exiting at the phase close OF THE ENTRY'S OWN PHASE (the
# rolled horizon — a 3,600s wait would otherwise be refused by the original
# phase's close in most cells).
TREND_D = (900, 1800, 3600)
ENTRIES = (tuple("HOLD_%d" % t for t in HOLD_T)
           + tuple("LEG_%g" % r for r in LEG_R)
           + tuple("DELAY_%d" % d for d in DELAY_D)
           + tuple("TREND_%d" % d for d in TREND_D))
N_HOLD, N_LEG, N_DELAY = len(HOLD_T), len(LEG_R), len(DELAY_D)
TREND_OFF = N_HOLD + N_LEG + N_DELAY
# EXT      the confirmed extreme -/+ 2 ticks (the distant original structure)
# RECLAIM  the reclaim level (the confirmation mid) -/+ 2 ticks
# SWING    the NEAREST retracement structure behind the entry -/+ 2 ticks: the
#          adverse extreme since the last favourable extreme, which IS the path
#          skeleton's own construction (c_c_roster._emit_candidate builds the
#          skeleton as the prefix-maxima of f and of -f)
STOPS = ("EXT", "RECLAIM", "SWING")
EXITS = ("PHASE", "TRAIL_1.0R", "TRAIL_1.5R")
TRAIL_K = {"TRAIL_1.0R": 1.0, "TRAIL_1.5R": 1.5}
CELLS = tuple("%s|%s|%s" % (e, s, x)
              for e in ENTRIES for s in STOPS for x in EXITS)
CELL_IDX = {c: i for i, c in enumerate(CELLS)}
N_CELL = len(CELLS)

# the [conf, entry] post-window block that GATES the trend entries — the delay
# census's own decidability features (m2_delay._post_path, imported verbatim)
PP_KEEP = ("pp_net", "pp_mfe", "pp_mae", "pp_giveback", "pp_eff", "pp_rv",
           "pp_upfrac", "pp_slope30", "pp_tmfe_frac", "pp_tmae_frac",
           "pp_spread_mean", "pp_imb_mean", "pp_imb_delta", "pp_sanefrac")

STOP_TICKS = 2.0                          # "+/- 2 ticks" (user's own words)
REBREAK_TICKS = 2.0                       # a re-break = > 2 ticks through L
TURN_SANE_CAP = 60                        # a trigger waits <=60s for a SANE mid
MIN_RISK_TICKS = 2.0                      # a stop closer than this is unexecutable

G1G2_MASK = (MC.FAM_BIT["G1"] | MC.FAM_BIT["G1_FINE"] | MC.FAM_BIT["G1_FAST_OPEN"]
             | MC.FAM_BIT["G2_REJECT"] | MC.FAM_BIT["G2_RECLAIM"])

REFUSALS = ("OK", "NO_PIVOT", "LEG_NOT_POSITIVE", "NO_TRIGGER_IN_PHASE",
            "REBREAK_BEFORE_TRIGGER", "STRUCT_VIOLATED", "RISK_TOO_TIGHT",
            "NO_SANE_MID")


def hb(msg):
    sys.stderr.write(msg.rstrip() + "\n")
    sys.stderr.flush()


# ============================================================== STAGE 0 ======
SPINE_KEYS = ("era_idx", "asset_idx", "d8", "dec_sec", "side", "phase_dec",
              "conf_sec", "ext_sec", "entry_mid", "atr14_usd", "fam_mask",
              "klass_idx", "cert_close_usd", "mae_before_argmax", "walled",
              "winner", "exit_close_sec", "cost_rt", "cert_peak_usd",
              "regime_tercile", "is_g1g2", "phase_close_sec")

# the day-grain feature block of census 2 (session-open information ONLY)
DAY_FC = ("fc_available", "fc_p_expansion", "fc_range_hat_usd",
          "fc_range_hat_q10", "fc_range_hat_q90", "fc_range_vs_trailing",
          "fc_share_TOKYO", "fc_share_LONDON", "fc_share_NY", "fc_menu_hat",
          "fc_bench_base_rate", "fc_bench_persistence",
          "fc_bench_range_trailmed")


def build_spine(out_dir=None):
    """The shared (asset, day, candidate) spine for all four censuses."""
    out_dir = out_dir or OUT_ROOT
    os.makedirs(out_dir, exist_ok=True)
    t0 = time.time()
    z = np.load(MATRIX_NPZ, allow_pickle=False)
    names = [str(x) for x in z["feature_names"]]
    era = z["era_idx"]
    keep = np.nonzero((era >= -1) & (era <= ERAS_EVAL[-1]))[0]
    Xf = z["X"]
    out = {"row": keep.astype(np.int64),
           "era_idx": era[keep].astype(np.int16),
           "asset_idx": z["asset_idx"][keep].astype(np.int8),
           "d8": z["d8"][keep].astype(np.int64),
           "dec_sec": z["dec_sec"][keep].astype(np.int64),
           "side": z["side"][keep].astype(np.int8),
           "phase_dec": z["phase_dec"][keep].astype(np.int8),
           "ep": z["ep"][keep].astype(np.int64)}
    for k in ("cert_close_usd", "cert_peak_usd", "mae_before_argmax", "walled",
              "winner", "exit_close_sec", "cost_rt", "cert_refused",
              "y_retg_rank_phase", "mfe_unwalled"):
        out[k] = z[k][keep]
    piv = Xf[keep, names.index("pivot_age_sec")].astype(np.int64)
    c2d = Xf[keep, names.index("conf_to_dec_sec")].astype(np.int64)
    out["conf_sec"] = out["dec_sec"] - c2d
    out["ext_sec"] = np.where(piv >= 0, out["dec_sec"] - piv, -1)
    out["regime_tercile"] = Xf[keep, names.index("regime_tercile")].astype(np.int8)
    g = np.zeros(keep.size, dtype=bool)
    for c in ("fam_G1", "fam_G1_FINE", "fam_G1_FAST_OPEN", "fam_G2_REJECT",
              "fam_G2_RECLAIM"):
        g |= Xf[keep, names.index(c)] > 0.5
    out["is_g1g2"] = g.astype(np.int8)
    # the declared class (a partition) straight off the one-hot block
    cls_cols = [c for c in names if c.startswith("cls_")]
    ci = np.zeros(keep.size, dtype=np.int8)
    for j, c in enumerate(cls_cols):
        ci[Xf[keep, names.index(c)] > 0.5] = j
    out["klass_idx"] = ci
    out["klass_names"] = np.array([c[4:] for c in cls_cols])
    # the day-grain forecaster block (census 2), taken at the day's FIRST row
    fc = np.column_stack([Xf[keep, names.index(c)] for c in DAY_FC])
    out["fc"] = fc.astype(np.float32)
    out["fc_names"] = np.array(DAY_FC)
    z.close()

    # roster geometry (entry_mid / atr / phase_close / fam_mask), by the
    # generation dedup key (d8, dec_sec, side) — assemble.roster's own index
    n = keep.size
    em = np.full(n, np.nan)
    at = np.full(n, np.nan)
    fm = np.zeros(n, dtype=np.int64)
    pc = np.full(n, -1, dtype=np.int64)
    for ai, asset in enumerate(MC.ASSET_ORDER):
        r = A.roster(asset)
        sel = np.nonzero(out["asset_idx"] == ai)[0]
        idx = r["_index"]
        d8l = out["d8"][sel].tolist()
        dsl = out["dec_sec"][sel].tolist()
        sdl = out["side"][sel].tolist()
        loc = np.array([idx.get((a_, b_, c_), -1)
                        for a_, b_, c_ in zip(d8l, dsl, sdl)], dtype=np.int64)
        ok = loc >= 0
        s2 = sel[ok]
        l2 = loc[ok]
        em[s2] = r["entry_mid"][l2]
        at[s2] = r["atr14_usd"][l2]
        fm[s2] = r["fam_mask"][l2]
        pc[s2] = r["phase_close_sec"][l2]
        hb("spine: %s roster join %d/%d" % (asset, int(ok.sum()), sel.size))
    out["entry_mid"] = em
    out["atr14_usd"] = at
    out["fam_mask"] = fm
    out["phase_close_sec"] = pc
    np.savez_compressed(os.path.join(out_dir, "spine.npz"), **out)
    rec = {"version": VERSION, "n_rows": int(n),
           "n_eval_rows": int(((out["era_idx"] >= 1) & (out["era_idx"] <= 5)).sum()),
           "n_g1g2_eval": int((g & (out["era_idx"] >= 1)).sum()),
           "roster_join_missing": int(np.isnan(em).sum()),
           "secs": round(time.time() - t0, 1)}
    with open(os.path.join(out_dir, "spine.receipt.json"), "w") as fh:
        json.dump(rec, fh, indent=1, sort_keys=True)
    hb("spine: %d rows in %.1fs (roster misses %d)"
       % (n, rec["secs"], rec["roster_join_missing"]))
    return out


_SP = {}


def spine(out_dir=None):
    if "d" not in _SP:
        p = os.path.join(out_dir or OUT_ROOT, "spine.npz")
        z = np.load(p, allow_pickle=False)
        _SP["d"] = {k: z[k] for k in z.files}
        z.close()
    return _SP["d"]


def era_name(k):
    return MC.ERAS[int(k)][0] if 0 <= int(k) < len(MC.ERAS) else "PRE_E1"


def sessions_of(D, mask=None):
    m = np.ones(D["d8"].size, bool) if mask is None else mask
    return np.array(["%s|%d" % (MC.ASSET_ORDER[a], d)
                     for a, d in zip(D["asset_idx"][m].tolist(),
                                     D["d8"][m].tolist())])


# ---------------------------------------------------------- day clustering --
def cluster_boot(vals, days, n=2000, seed=SEED, stat=np.mean):
    """Day-clustered bootstrap CI of `stat` over `vals` (the draw unit = day)."""
    vals = np.asarray(vals, dtype=np.float64)
    days = np.asarray(days)
    ok = np.isfinite(vals)
    vals, days = vals[ok], days[ok]
    if vals.size == 0:
        return float("nan"), float("nan"), float("nan"), 0
    ud, inv = np.unique(days, return_inverse=True)
    buckets = [np.nonzero(inv == i)[0] for i in range(ud.size)]
    rs = np.random.RandomState(seed)
    out = np.empty(n)
    for b in range(n):
        pick = rs.randint(0, ud.size, ud.size)
        idx = np.concatenate([buckets[i] for i in pick])
        out[b] = stat(vals[idx])
    return (float(stat(vals)), float(np.percentile(out, 2.5)),
            float(np.percentile(out, 97.5)), int(ud.size))


# ============================================================== CENSUS 1 =====
def _kstar():
    import info_ceiling as IC
    return IC._kstar()


def census_ambiguity(out_dir=None):
    """Two-sidedness of every D-021 winner and every oracle seat."""
    out_dir = out_dir or OUT_ROOT
    os.makedirs(out_dir, exist_ok=True)
    D = spine()
    K = _kstar()
    ev = np.nonzero((D["era_idx"] >= ERAS_EVAL[0]) &
                    (D["era_idx"] <= ERAS_EVAL[-1]))[0]
    asset = np.array([MC.ASSET_ORDER[a] for a in D["asset_idx"][ev].tolist()])
    d8 = D["d8"][ev]
    dec = D["dec_sec"][ev]
    side = D["side"][ev].astype(np.int64)
    ph = D["phase_dec"][ev].astype(np.int64)
    mid = D["entry_mid"][ev]
    atr = D["atr14_usd"][ev]
    cert = D["cert_close_usd"][ev]
    win = D["winner"][ev] > 0
    walled = D["walled"][ev] > 0
    era = D["era_idx"][ev]

    cell = np.array(["%s|%d|%d" % (a, b, c) for a, b, c
                     in zip(asset.tolist(), d8.tolist(), ph.tolist())])
    two1 = np.zeros(ev.size, bool)          # opposite side within K*
    two2 = np.zeros(ev.size, bool)          # ... within 2K*
    wallpair = np.zeros(ev.size, bool)      # the opposite leg actually walled
    order = np.argsort(cell, kind="stable")
    co = cell[order]
    starts = [0] + (np.flatnonzero(co[1:] != co[:-1]) + 1).tolist()
    stops = starts[1:] + [co.size]
    for a_, b_ in zip(starts, stops):
        idx = order[a_:b_]
        if idx.size < 2:
            continue
        Kc = K[asset[idx[0]]]
        dd = dec[idx].astype(np.float64)
        ss = side[idx]
        mm = mid[idx]
        aa = np.nanmean(atr[idx])
        vic = VICINITY_ATR * aa if np.isfinite(aa) and aa > 0 else np.inf
        dt = np.abs(dd[:, None] - dd[None, :])
        opp = ss[:, None] != ss[None, :]
        near = np.abs(mm[:, None] - mm[None, :]) <= vic
        m1 = opp & near & (dt <= Kc)
        m2 = opp & near & (dt <= 2 * Kc)
        two1[idx] = m1.any(axis=1)
        two2[idx] = m2.any(axis=1)
        wl = walled[idx]
        wallpair[idx] = (m2 & wl[None, :]).any(axis=1)

    # ---- deliverable A: the one-sided share of daily seatable dollars -------
    rows = []
    for ek in list(ERAS_EVAL) + ["ALL"]:
        em = np.ones(ev.size, bool) if ek == "ALL" else (era == ek)
        for a in list(MC.ASSET_ORDER) + ["ALL"]:
            am = np.ones(ev.size, bool) if a == "ALL" else (asset == a)
            m = em & am
            w = m & win
            if not w.any():
                continue
            tot = float(cert[w].sum())
            rows.append({
                "era": "ALL" if ek == "ALL" else era_name(ek), "asset": a,
                "n_winners": int(w.sum()),
                "winner_usd": round(tot, 2),
                "one_sided_frac_n_K": round(float((~two1[w]).mean()), 4),
                "one_sided_frac_usd_K": round(float(cert[w & ~two1].sum() / tot), 4)
                if tot else float("nan"),
                "one_sided_frac_n_2K": round(float((~two2[w]).mean()), 4),
                "one_sided_frac_usd_2K": round(float(cert[w & ~two2].sum() / tot), 4)
                if tot else float("nan"),
                "wallpair_adjacent_frac_n": round(float(wallpair[w].mean()), 4),
                "wallpair_adjacent_frac_usd":
                    round(float(cert[w & wallpair].sum() / tot), 4) if tot else float("nan"),
                "mean_winner_usd": round(float(cert[w].mean()), 2),
                "mean_winner_usd_one_sided_K":
                    round(float(cert[w & ~two1].mean()), 2) if (w & ~two1).any() else float("nan"),
                "mean_winner_usd_two_sided_K":
                    round(float(cert[w & two1].mean()), 2) if (w & two1).any() else float("nan"),
            })
    write_tsv(os.path.join(PROV, "GOALPATH_AMBIGUITY.tsv"),
              "census 1 — the ambiguity veto: two-sidedness of D-021 winners",
              rows)

    # ---- deliverable B: the population-level veto (all candidates) ----------
    prow = []
    for ek in list(ERAS_EVAL) + ["ALL"]:
        em = np.ones(ev.size, bool) if ek == "ALL" else (era == ek)
        for veto, vm in (("NONE", np.ones(ev.size, bool)),
                         ("ONE_SIDED_K", ~two1), ("ONE_SIDED_2K", ~two2)):
            m = em & vm
            if not m.any():
                continue
            prow.append({
                "era": "ALL" if ek == "ALL" else era_name(ek), "veto": veto,
                "n_candidates": int(m.sum()),
                "kept_frac": round(float(m.sum() / max(1, em.sum())), 4),
                "winner_rate": round(float(win[m].mean()), 5),
                "winner_rate_lift": round(float(win[m].mean() /
                                                max(1e-12, win[em].mean())), 4),
                "wall_rate": round(float(walled[m].mean()), 5),
                "mean_cert_usd": round(float(np.nanmean(cert[m])), 2),
                "winner_usd_kept": round(float(cert[m & win].sum()), 2),
                "winner_usd_forfeited":
                    round(float(cert[em & win].sum() - cert[m & win].sum()), 2),
            })
    write_tsv(os.path.join(PROV, "GOALPATH_AMBIGUITY_VETO.tsv"),
              "census 1 — the veto applied to the whole candidate population",
              prow)

    np.savez_compressed(os.path.join(out_dir, "ambig.npz"),
                        ev=ev, two1=two1, two2=two2, wallpair=wallpair)

    # ---- deliverable C: the ORACLE SEATS ------------------------------------
    orows = []
    seen = {}
    for a in MC.ASSET_ORDER:
        am = asset == a
        days = np.unique(d8[am])
        Kc = K[a]
        n_seat = n_one = 0
        usd_seat = usd_one = 0.0
        for dd in days.tolist():
            legs = A.oracle_legs(a, int(dd))
            if not legs:
                continue
            items = []
            for k, r in enumerate(legs):
                try:
                    s0 = int(float(r["leg_start_sec"]))
                    s1 = int(float(r["leg_end_sec"]))
                    v = float(r["travel_usd"])
                except Exception:              # noqa: BLE001
                    continue
                if not np.isfinite(v) or s1 < s0 or v <= 0:
                    continue
                items.append((s0, s1, v, s0, k, k))
            if not items:
                continue
            import c_c_roster as CC
            _tot, chosen = CC.dp_schedule(items)
            dm = am & (d8 == dd)
            for k in chosen:
                r = legs[k]
                dirn = int(float(r["direction"]))
                try:
                    anch = int(float(r["capture_dec_sec"]))
                except Exception:              # noqa: BLE001
                    anch = int(float(r["leg_start_sec"]))
                if anch <= 0:
                    anch = int(float(r["leg_start_sec"]))
                px = float(r["leg_start_px"])
                atr_l = float(r["atr14_prev_usd"])
                mult = float(C.ASSETS[a]["mult"])
                vic = VICINITY_ATR * atr_l / mult
                opp = dm & (side == -dirn) & (np.abs(dec - anch) <= 2 * Kc) \
                    & (np.abs(mid - px) <= vic)
                n_seat += 1
                usd_seat += float(r["travel_usd"])
                if not opp.any():
                    n_one += 1
                    usd_one += float(r["travel_usd"])
        seen[a] = (n_seat, n_one, usd_seat, usd_one)
        orows.append({"asset": a, "n_oracle_seats": n_seat,
                      "n_one_sided_2K": n_one,
                      "one_sided_frac_n": round(n_one / max(1, n_seat), 4),
                      "oracle_usd": round(usd_seat, 2),
                      "one_sided_usd": round(usd_one, 2),
                      "one_sided_frac_usd": round(usd_one / max(1e-9, usd_seat), 4)})
    write_tsv(os.path.join(PROV, "GOALPATH_AMBIGUITY_ORACLE.tsv"),
              "census 1 — two-sidedness of the DP-scheduled ORACLE seats "
              "(opposite-side candidate within 2K* and 0.5 ATR)", orows)
    hb("census 1: %d winners, one-sided(K*) $ share %.3f"
       % (int(win.sum()),
          float(cert[win & ~two1].sum() / max(1e-9, cert[win].sum()))))
    return rows


# ============================================================== CENSUS 4 =====
def _cell_arrays(n):
    val = np.full((n, N_CELL), np.nan, dtype=np.float32)
    ex = np.full((n, N_CELL), -1, dtype=np.int32)
    mae = np.full((n, N_CELL), np.nan, dtype=np.float32)
    return val, ex, mae


def _first_ge(vt, t):
    """index of the first SANE second >= t, within TURN_SANE_CAP; else -1."""
    j = int(np.searchsorted(vt, t, side="left"))
    if j >= vt.size:
        return -1
    return j if int(vt[j]) - int(t) <= TURN_SANE_CAP else -1


def _cont_one(job):
    """Every confirmation-strength entry of ONE (asset, date8).

    `shift` > 0 is the RED-FIRST DISPLACED-ENTRY CONTROL: every trigger second
    is moved `shift` seconds later inside the same horizon, with the structural
    stops left exactly where the structure puts them.  A trade class whose edge
    is the confirmation structure must lose it under displacement.
    """
    asset, d8, rows, shift = job
    try:
        import m2_delay as MD                    # the delay census's own pp_*
        sess = A.load_session(asset, int(d8))
        s = sess["s"]
        spec = C.ASSETS[asset]
        mult = float(spec["mult"])
        tick_px = float(spec["tick_px"])
        vt = s.vt
        vm = s.vm
        n = len(rows)
        val, ex, mae = _cell_arrays(n)
        ent = np.full((n, len(ENTRIES)), -1, dtype=np.int32)
        rusd = np.full((n, len(ENTRIES) * len(STOPS)), np.nan, dtype=np.float32)
        ref = np.zeros((n, len(ENTRIES)), dtype=np.int8)
        pp = np.full((n, len(TREND_D), len(PP_KEEP)), np.nan, dtype=np.float32)
        for ri, (i, dec, conf, ext_s, sd, cost, atr) in enumerate(rows):
            dec = int(dec); conf = int(conf); ext_s = int(ext_s); sd = int(sd)
            if ext_s < 0:
                ref[ri, :] = REFUSALS.index("NO_PIVOT")
                continue
            pc0 = X.next_phase_boundary(s, dec)
            # the window must reach the LATEST trend entry's own phase close
            t_far = min(conf + TREND_D[-1], s.n - 2)
            pc_far = max(pc0, X.next_phase_boundary(s, t_far))
            j_ext = int(np.searchsorted(vt, ext_s, side="left"))
            j_conf = int(np.searchsorted(vt, conf, side="left"))
            j_end = int(np.searchsorted(vt, pc_far, side="right"))
            if j_ext >= vt.size or j_conf >= vt.size or j_end - j_conf < 2:
                ref[ri, :] = REFUSALS.index("NO_SANE_MID")
                continue
            ext_px = float(vm[j_ext])
            L = float(vm[j_conf])
            leg = sd * (L - ext_px)
            if not (leg > 0):
                ref[ri, :] = REFUSALS.index("LEG_NOT_POSITIVE")
                continue
            # the working window, signed so that "up" is always favourable
            w = vm[j_conf:j_end] * sd
            wt = vt[j_conf:j_end]
            nw = w.size
            i_pc0 = int(np.searchsorted(wt, pc0, side="right")) - 1
            sL = sd * L
            sE = sd * ext_px
            tol = REBREAK_TICKS * tick_px
            rb = np.nonzero(w[1:] < sL - tol)[0]
            rb_i = int(rb[0]) + 1 if rb.size else 10 ** 9
            # ---- the path skeleton: new favourable extremes and their index --
            runmax = np.maximum.accumulate(w)
            isnew = np.empty(nw, dtype=bool)
            isnew[0] = True
            isnew[1:] = w[1:] > runmax[:-1]
            nh = np.nonzero(isnew)[0]           # the favourable-extreme chain
            atr_px = float(atr) / mult
            # ------------------------------------------------------ triggers --
            trig = []
            for T in HOLD_T:
                te = conf + T
                if te >= pc0:
                    trig.append((-1, REFUSALS.index("NO_TRIGGER_IN_PHASE"), i_pc0))
                    continue
                k = _first_ge(wt, te)
                if k < 0 or k > i_pc0:
                    trig.append((-1, REFUSALS.index("NO_SANE_MID"), i_pc0))
                elif rb_i <= k:
                    trig.append((-1, REFUSALS.index("REBREAK_BEFORE_TRIGGER"), i_pc0))
                else:
                    trig.append((k, 0, i_pc0))
            for R in LEG_R:
                need = sE + R * atr_px
                q = np.nonzero(w[1:i_pc0 + 1] >= need)[0]
                if not q.size:
                    trig.append((-1, REFUSALS.index("NO_TRIGGER_IN_PHASE"), i_pc0))
                    continue
                k = int(q[0]) + 1
                if rb_i <= k:
                    trig.append((-1, REFUSALS.index("REBREAK_BEFORE_TRIGGER"), i_pc0))
                else:
                    trig.append((k, 0, i_pc0))
            for Dl in DELAY_D:
                te = dec + Dl
                if te >= pc0:
                    trig.append((-1, REFUSALS.index("NO_TRIGGER_IN_PHASE"), i_pc0))
                    continue
                k = _first_ge(wt, te)
                if k < 0 or k > i_pc0:
                    trig.append((-1, REFUSALS.index("NO_SANE_MID"), i_pc0))
                else:
                    trig.append((k, 0, i_pc0))
            # ---- THE TREND ARM: t+D after confirmation, trend still prevailing
            for ti, Dl in enumerate(TREND_D):
                te = conf + Dl
                if te >= s.n - 1:
                    trig.append((-1, REFUSALS.index("NO_TRIGGER_IN_PHASE"), -1))
                    continue
                k = _first_ge(wt, te)
                if k < 0 or k >= nw:
                    trig.append((-1, REFUSALS.index("NO_SANE_MID"), -1))
                    continue
                # the trend gate: still on the reversal side of the reclaim
                if not (w[k] > sL):
                    trig.append((-1, REFUSALS.index("REBREAK_BEFORE_TRIGGER"), -1))
                    continue
                pce = X.next_phase_boundary(s, int(wt[k]))
                iend = int(np.searchsorted(wt, pce, side="right")) - 1
                if iend <= k:
                    trig.append((-1, REFUSALS.index("NO_TRIGGER_IN_PHASE"), -1))
                    continue
                trig.append((k, 0, iend))
                # the [conf, entry] decidability block, m2_delay's own arithmetic
                fw = (vm[j_conf:j_end] - L) * sd * mult
                blk = MD._post_path(s, wt, fw, int(wt[0]), int(wt[k]), sd)
                for pi, nm in enumerate(PP_KEEP):
                    pp[ri, ti, pi] = blk.get(nm, float("nan"))
            # ------------------------------------------------------- trades --
            for ei, (k, why, iend) in enumerate(trig):
                if k < 0:
                    ref[ri, ei] = why
                    continue
                if shift:
                    k2 = _first_ge(wt, int(wt[k]) + int(shift))
                    if k2 < 0 or k2 > iend:
                        ref[ri, ei] = REFUSALS.index("NO_TRIGGER_IN_PHASE")
                        continue
                    k = k2
                ent[ri, ei] = int(wt[k])
                se = float(w[k])
                # ---- the three structural stop levels, signed ---------------
                lv_swing = float("nan")
                p = int(np.searchsorted(nh, k, side="right")) - 1
                for back in (0, 1):
                    if p - back < 0:
                        break
                    cand = float(w[nh[p - back]:k + 1].min())
                    if se - (cand - STOP_TICKS * tick_px) >= MIN_RISK_TICKS * tick_px:
                        lv_swing = cand - STOP_TICKS * tick_px
                        break
                stop_lv = (sE - STOP_TICKS * tick_px, sL - STOP_TICKS * tick_px,
                           lv_swing)
                any_ok = False
                for si, lv in enumerate(stop_lv):
                    if not np.isfinite(lv):
                        continue
                    R_px = se - lv
                    if R_px < MIN_RISK_TICKS * tick_px:
                        continue
                    q = np.nonzero(w[k:iend + 1] <= lv)[0]
                    if q.size and int(q[0]) == 0:
                        continue                 # structure already violated
                    R_usd = R_px * mult
                    rusd[ri, ei * len(STOPS) + si] = R_usd
                    any_ok = True
                    seg = w[k:iend + 1]
                    # ---- PHASE-CLOSE (with the structural stop) ------------
                    if q.size:
                        t_i = int(q[0])
                        xpx = lv
                    else:
                        t_i = seg.size - 1
                        xpx = float(seg[-1])
                    v = (xpx - se) * mult - cost
                    ci = CELL_IDX["%s|%s|PHASE" % (ENTRIES[ei], STOPS[si])]
                    val[ri, ci] = v
                    ex[ri, ci] = int(wt[k + t_i])
                    mae[ri, ci] = (se - float(seg[:t_i + 1].min())) * mult
                    # ---- TRAILING -----------------------------------------
                    rmx = np.maximum.accumulate(seg)
                    prev = np.empty(seg.size)
                    prev[0] = se
                    prev[1:] = rmx[:-1]
                    for xn, kk in TRAIL_K.items():
                        lvl = np.maximum(lv, prev - kk * R_px)
                        q2 = np.nonzero(seg <= lvl)[0]
                        if q2.size:
                            t2 = int(q2[0])
                            xpx2 = float(lvl[t2])
                        else:
                            t2 = seg.size - 1
                            xpx2 = float(seg[-1])
                        v2 = (xpx2 - se) * mult - cost
                        ci2 = CELL_IDX["%s|%s|%s" % (ENTRIES[ei], STOPS[si], xn)]
                        val[ri, ci2] = v2
                        ex[ri, ci2] = int(wt[k + t2])
                        mae[ri, ci2] = (se - float(seg[:t2 + 1].min())) * mult
                if not any_ok:
                    ref[ri, ei] = REFUSALS.index("RISK_TOO_TIGHT")
        gi = np.array([r[0] for r in rows], dtype=np.int64)
        return (asset, int(d8), gi, val, ex, mae, ent, rusd, ref, pp, None)
    except Exception as exc:                        # noqa: BLE001
        return (asset, int(d8), None, None, None, None, None, None, None, None,
                "%s: %s" % (type(exc).__name__, exc))


def run_cont(workers=8, out_dir=None, eras=ERAS_EVAL, limit_days=None,
             shift=0, tag=""):
    out_dir = out_dir or OUT_ROOT
    os.makedirs(out_dir, exist_ok=True)
    import multiprocessing as mp
    D = spine()
    for ek in eras:
        t0 = time.time()
        m = np.nonzero((D["era_idx"] == ek) & (D["is_g1g2"] > 0) &
                       (D["ext_sec"] >= 0))[0]
        jobs = {}
        for pos, i in enumerate(m.tolist()):
            a = MC.ASSET_ORDER[int(D["asset_idx"][i])]
            jobs.setdefault((a, int(D["d8"][i])), []).append(
                (pos, int(D["dec_sec"][i]), int(D["conf_sec"][i]),
                 int(D["ext_sec"][i]), int(D["side"][i]),
                 float(D["cost_rt"][i]), float(D["atr14_usd"][i])))
        joblist = [(a, d, sorted(v), shift) for (a, d), v in sorted(jobs.items())]
        if limit_days:
            joblist = joblist[:limit_days]
        n = m.size
        val, ex, mae = _cell_arrays(n)
        ent = np.full((n, len(ENTRIES)), -1, dtype=np.int32)
        rusd = np.full((n, len(ENTRIES) * len(STOPS)), np.nan, dtype=np.float32)
        ref = np.zeros((n, len(ENTRIES)), dtype=np.int8)
        pp = np.full((n, len(TREND_D), len(PP_KEEP)), np.nan, dtype=np.float32)
        errs = []
        done = 0
        with mp.Pool(workers) as pool:
            for res in pool.imap_unordered(_cont_one, joblist, chunksize=4):
                a, d, gi, v, e, mm, en, ru, rf, pb, err = res
                done += 1
                if err:
                    errs.append("%s %d: %s" % (a, d, err))
                    continue
                val[gi] = v
                ex[gi] = e
                mae[gi] = mm
                ent[gi] = en
                rusd[gi] = ru
                ref[gi] = rf
                pp[gi] = pb
                if done % 100 == 0:
                    hb("cont %s: %d/%d days %.0fs"
                       % (era_name(ek), done, len(joblist), time.time() - t0))
        np.savez_compressed(
            os.path.join(out_dir, "cont%s_E%d.npz" % (tag, ek)),
            idx=m.astype(np.int64), val=val, exit_sec=ex, mae=mae,
            entry_sec=ent, r_usd=rusd, refuse=ref, pp=pp,
            cells=np.array(CELLS), entries=np.array(ENTRIES),
            stops=np.array(STOPS), refusals=np.array(REFUSALS),
            pp_names=np.array(PP_KEEP), trend_d=np.array(TREND_D))
        rec = {"version": VERSION, "era": era_name(ek), "n_candidates": int(n),
               "n_days": len(joblist), "n_cells": N_CELL, "shift_sec": int(shift),
               "errors": errs[:20], "n_errors": len(errs),
               "secs": round(time.time() - t0, 1)}
        with open(os.path.join(out_dir, "cont%s_E%d.receipt.json" % (tag, ek)), "w") as fh:
            json.dump(rec, fh, indent=1, sort_keys=True)
        hb("cont %s: %d candidates, %d days, %d errors in %.0fs"
           % (era_name(ek), n, len(joblist), len(errs), time.time() - t0))


# =================================================== the selection model =====
# The FEATURE-ONLY selection arm every census stacks on: the M3 walk-forward
# protocol (expanding era ladder, PRIMARY_TARGET y_retg_rank_phase), refit here
# once so that the per-candidate score is available to all four censuses.
SEL_CFG = {"max_depth": 6, "eta": 0.08, "min_child_weight": 20,
           "subsample": 0.9, "colsample_bytree": 0.9, "tree_method": "hist",
           "objective": "reg:squarederror", "seed": SEED}
SEL_ROUNDS = 300


def run_select(workers=8, out_dir=None):
    """Walk-forward per-candidate selection score for eras E2..E6."""
    import xgboost as xgb
    out_dir = out_dir or OUT_ROOT
    D = spine()
    z = np.load(MATRIX_NPZ, allow_pickle=False)
    names = [str(x) for x in z["feature_names"]]
    # the FORWARD-FEATURE GUARD is the matrix's own: m3_matrix ran
    # m3_common.check_forbidden_names + check_forward_values before writing
    # matrix.npz (matrix.receipt.json), and this module reads that matrix
    # verbatim — it never constructs a feature.
    rows = D["row"]
    Xm = z["X"][rows]
    z.close()
    y = D["y_retg_rank_phase"]
    era = D["era_idx"]
    score = np.full(rows.size, np.nan)
    recs = []
    cfg = dict(SEL_CFG)
    cfg["nthread"] = int(workers)
    for k in ERAS_EVAL:
        t0 = time.time()
        tr = np.nonzero((era >= 0) & (era < k) & np.isfinite(y))[0]
        ev = np.nonzero(era == k)[0]
        dtr = xgb.DMatrix(Xm[tr], label=y[tr], feature_names=names)
        bst = xgb.train(cfg, dtr, num_boost_round=SEL_ROUNDS)
        score[ev] = bst.predict(xgb.DMatrix(Xm[ev], feature_names=names))
        recs.append({"era": era_name(k), "n_train": int(tr.size),
                     "n_eval": int(ev.size), "secs": round(time.time() - t0, 1)})
        hb("select %s: train %d eval %d in %.0fs"
           % (era_name(k), tr.size, ev.size, time.time() - t0))
    np.savez_compressed(os.path.join(out_dir, "select.npz"), score=score)
    with open(os.path.join(out_dir, "select.receipt.json"), "w") as fh:
        json.dump({"version": VERSION, "cfg": SEL_CFG, "rounds": SEL_ROUNDS,
                   "target": "y_retg_rank_phase", "eras": recs}, fh, indent=1,
                  sort_keys=True)
    return score


def sel_score(out_dir=None):
    p = os.path.join(out_dir or OUT_ROOT, "select.npz")
    z = np.load(p, allow_pickle=False)
    s = z["score"]
    z.close()
    return s


def topn_takes(idx, score, sess, topn=TOPN_PER_ASSET_DAY):
    """Top-N rows of `idx` per session, by `score` (the reader/model schedule)."""
    out = []
    o = np.argsort(sess[idx], kind="stable")
    si = idx[o]
    ss = sess[idx][o]
    starts = [0] + (np.flatnonzero(ss[1:] != ss[:-1]) + 1).tolist()
    stops = starts[1:] + [ss.size]
    for a, b in zip(starts, stops):
        blk = si[a:b]
        sc = score[blk]
        ok = np.isfinite(sc)
        blk, sc = blk[ok], sc[ok]
        if blk.size == 0:
            continue
        pick = blk[np.argsort(-sc, kind="stable")[:topn]]
        out.extend(pick.tolist())
    return np.array(sorted(out), dtype=np.int64)


def replay(entry_sec, exit_sec, value, sess, take_idx):
    """One-position chronological replay per session (D-046).  Returns
    (per-session rows, seated row indices)."""
    by = {}
    for i in np.asarray(take_idx, dtype=np.int64).tolist():
        if not np.isfinite(value[i]) or entry_sec[i] < 0:
            continue
        by.setdefault(sess[i], []).append((int(entry_sec[i]), i))
    rows, seats_all = [], []
    for sk in sorted(by):
        seq = sorted(by[sk])
        open_until = -1
        tot = 0.0
        seats = []
        n_forf = 0
        for e, i in seq:
            if e <= open_until:
                n_forf += 1
                continue
            tot += float(value[i])
            open_until = int(exit_sec[i])
            seats.append(i)
        rows.append({"session": sk, "realised": tot, "n_takes": len(seq),
                     "n_seated": len(seats), "n_forfeited": n_forf,
                     "seats": seats})
        seats_all.extend(seats)
    return rows, np.array(sorted(seats_all), dtype=np.int64)


def session_dd(value, exit_sec, rows):
    """D-030: the worst intra-session drawdown of the seated P&L sequence."""
    dds = []
    for r in rows:
        s = r["seats"]
        if not s:
            dds.append(0.0)
            continue
        s = sorted(s, key=lambda i: int(exit_sec[i]))
        run = np.cumsum([float(value[i]) for i in s])
        peak = np.maximum.accumulate(np.concatenate([[0.0], run]))
        dds.append(float((peak[1:] - run).max()))
    return dds


# ============================================================== CENSUS 2 =====
DAY_FEATS = ("tk_ret_usd", "tk_ret_atr", "tk_range_usd", "tk_range_atr",
             "tk_pos_in_range", "tk_rv_usd", "tk_sane_frac", "tk_slope_last30m",
             "prev_ret_atr", "prev_range_atr", "prev_tr_atr", "prev_pos",
             "gap_open_atr", "atr14_usd", "dow", "is_monday", "is_friday",
             "month")
XA_FEATS = ("xa_ret_atr", "xa_range_atr")


def _day_block(job):
    """Session-open information for ONE (asset, date8): the Tokyo window."""
    asset, d8 = job
    try:
        sess = A.load_session(asset, int(d8))
        s = sess["s"]
        mult = float(C.ASSETS[asset]["mult"])
        atr = float(s.meta.get("ATR14_prev_px", float("nan"))) * mult
        # the end of the TOKYO phase = the first second whose phase differs
        t_open = X.next_phase_boundary(s, 0)
        j1 = int(np.searchsorted(s.vt, t_open, side="right"))
        vt, vm = s.vt[:j1], s.vm[:j1]
        out = {k: float("nan") for k in DAY_FEATS}
        out["atr14_usd"] = atr
        d = sess["trade_date"]
        out["dow"] = float(d.weekday())
        out["is_monday"] = float(d.weekday() == 0)
        out["is_friday"] = float(d.weekday() == 4)
        out["month"] = float(d.month)
        if vm.size >= 30:
            r = (float(vm[-1]) - float(vm[0])) * mult
            rng = (float(vm.max()) - float(vm.min())) * mult
            out["tk_ret_usd"] = r
            out["tk_range_usd"] = rng
            out["tk_rv_usd"] = float(np.abs(np.diff(vm)).sum()) * mult
            out["tk_sane_frac"] = float(vm.size) / max(1, t_open)
            lo, hi = float(vm.min()), float(vm.max())
            out["tk_pos_in_range"] = ((float(vm[-1]) - lo) / (hi - lo)) \
                if hi > lo else 0.5
            k30 = int(np.searchsorted(vt, max(0, t_open - 1800), side="left"))
            out["tk_slope_last30m"] = (float(vm[-1]) - float(vm[k30])) * mult
            if np.isfinite(atr) and atr > 0:
                out["tk_ret_atr"] = r / atr
                out["tk_range_atr"] = rng / atr
        # strictly-prior-day structure
        pd8 = A.prior_session_d8(asset, int(d8))
        if pd8 is not None:
            b = A.bars(asset)
            import datetime as _dt
            pdd = _dt.date(pd8 // 10000, (pd8 // 100) % 100, pd8 % 100)
            pb = b.get(pdd)
            if pb and np.isfinite(atr) and atr > 0:
                H = float(pb["H"]) * mult
                L = float(pb["L"]) * mult
                Cl = float(pb["C"]) * mult
                out["prev_range_atr"] = (H - L) / atr
                out["prev_pos"] = ((Cl - L) / (H - L)) if H > L else 0.5
                pp = A.prior_session_d8(asset, int(pd8))
                pbb = None
                if pp is not None:
                    ppd = _dt.date(pp // 10000, (pp // 100) % 100, pp % 100)
                    pbb = b.get(ppd)
                if pbb:
                    Cp = float(pbb["C"]) * mult
                    out["prev_ret_atr"] = (Cl - Cp) / atr
                    out["prev_tr_atr"] = max(H - L, abs(H - Cp),
                                             abs(L - Cp)) / atr
                if vm.size:
                    out["gap_open_atr"] = (float(vm[0]) * mult - Cl) / atr
        return (asset, int(d8), out, float(t_open), None)
    except Exception as exc:                       # noqa: BLE001
        return (asset, int(d8), None, -1.0, "%s: %s" % (type(exc).__name__, exc))


def build_days(workers=8, out_dir=None):
    """The (asset, day) session-open feature table + the paying-side label."""
    import multiprocessing as mp
    out_dir = out_dir or OUT_ROOT
    D = spine()
    keys = sorted(set(zip(D["asset_idx"].tolist(), D["d8"].tolist())))
    jobs = [(MC.ASSET_ORDER[a], d) for a, d in keys]
    res = {}
    topen = {}
    with mp.Pool(workers) as pool:
        for a, d, o, t_open, err in pool.imap_unordered(_day_block, jobs,
                                                        chunksize=8):
            if err:
                hb("day_block %s %d: %s" % (a, d, err))
                continue
            res[(a, d)] = o
            topen[(a, d)] = t_open
    # cross-session state: the OTHER two assets' Tokyo block, same calendar day
    feats = list(DAY_FEATS) + ["xa1_ret_atr", "xa1_range_atr",
                               "xa2_ret_atr", "xa2_range_atr"]
    rows = []
    for (a, d) in sorted(res):
        o = res[(a, d)]
        v = [o[k] for k in DAY_FEATS]
        others = [x for x in MC.ASSET_ORDER if x != a]
        for ob in others:
            oo = res.get((ob, d))
            v.append(oo["tk_ret_atr"] if oo else float("nan"))
            v.append(oo["tk_range_atr"] if oo else float("nan"))
        rows.append((a, d, v))
    Xd = np.array([r[2] for r in rows], dtype=np.float32)
    asset_i = np.array([MC.ASSET_ORDER.index(r[0]) for r in rows], dtype=np.int8)
    d8 = np.array([r[1] for r in rows], dtype=np.int64)
    t_open = np.array([topen[(r[0], r[1])] for r in rows], dtype=np.int64)

    # the forecaster block, taken at the day's FIRST candidate row
    fc = np.full((len(rows), D["fc"].shape[1]), np.nan, dtype=np.float32)
    era = np.full(len(rows), -9, dtype=np.int16)
    pos = {(int(a), int(d)): i for i, (a, d) in
           enumerate(zip(asset_i.tolist(), d8.tolist()))}
    order = np.lexsort((D["dec_sec"], D["d8"], D["asset_idx"]))
    seen = set()
    for i in order.tolist():
        k = (int(D["asset_idx"][i]), int(D["d8"][i]))
        if k in seen or k not in pos:
            continue
        seen.add(k)
        fc[pos[k]] = D["fc"][i]
        era[pos[k]] = D["era_idx"][i]

    # ---- the LABEL: which side's D-021 winners carry more $ that day -------
    up = np.zeros(len(rows))
    dn = np.zeros(len(rows))
    up0 = np.zeros(len(rows))
    dn0 = np.zeros(len(rows))
    w = D["winner"] > 0
    for i in np.nonzero(w)[0].tolist():
        k = (int(D["asset_idx"][i]), int(D["d8"][i]))
        j = pos.get(k)
        if j is None:
            continue
        v = float(D["cert_close_usd"][i])
        post = int(D["dec_sec"][i]) >= t_open[j]
        if int(D["side"][i]) > 0:
            up0[j] += v
            if post:
                up[j] += v
        else:
            dn0[j] += v
            if post:
                dn[j] += v
    y = np.where(up > dn, 1, np.where(dn > up, -1, 0)).astype(np.int8)
    y0 = np.where(up0 > dn0, 1, np.where(dn0 > up0, -1, 0)).astype(np.int8)
    Xall = np.column_stack([Xd, fc]).astype(np.float32)
    names = np.array(feats + [str(c) for c in D["fc_names"]])
    np.savez_compressed(os.path.join(out_dir, "days.npz"), X=Xall, names=names,
                        asset_idx=asset_i, d8=d8, era_idx=era, y=y, y_open=y0,
                        up_usd=up, dn_usd=dn, up0_usd=up0, dn0_usd=dn0,
                        t_open=t_open)
    hb("days: %d (asset,day) rows, %d features, label base rate L %.3f / S %.3f"
       " / tie %.3f" % (len(rows), Xall.shape[1], float((y == 1).mean()),
                        float((y == -1).mean()), float((y == 0).mean())))
    return Xall


def census_dayside(workers=8, out_dir=None):
    """Two causal arms:
       AT_TOKYO_CLOSE  the full session-open block (prior day + the session's
                       own Tokyo window + cross-asset Tokyo + forecaster),
                       label = the paying side over the REST of the day.
       AT_SESSION_OPEN prior-session structure + forecaster + clock ONLY (no
                       current-session tape at all), label = the paying side
                       over the WHOLE session — the arm that does not cede
                       NKD's Tokyo hours.
    """
    import xgboost as xgb
    out_dir = out_dir or OUT_ROOT
    z = np.load(os.path.join(out_dir, "days.npz"), allow_pickle=False)
    Xd = z["X"]
    names = [str(x) for x in z["names"]]
    era = z["era_idx"]
    d8 = z["d8"]
    ai = z["asset_idx"]
    t_open = z["t_open"]
    Y = {"AT_TOKYO_CLOSE": z["y"], "AT_SESSION_OPEN": z["y_open"]}
    z.close()
    open_cols = [i for i, n in enumerate(names)
                 if not (n.startswith("tk_") or n.startswith("xa"))]
    cfg = {"max_depth": 3, "eta": 0.05, "min_child_weight": 20,
           "subsample": 0.9, "colsample_bytree": 0.9, "tree_method": "hist",
           "objective": "binary:logistic", "seed": SEED, "nthread": int(workers)}
    rows = []
    store = {}
    rs = np.random.RandomState(SEED)
    for arm, yv in Y.items():
        cols = list(range(Xd.shape[1])) if arm == "AT_TOKYO_CLOSE" else open_cols
        Xa = Xd[:, cols]
        na = [names[i] for i in cols]
        pred = np.full(yv.size, np.nan)
        predsh = np.full(yv.size, np.nan)
        for k in ERAS_EVAL:
            tr = np.nonzero((era >= 0) & (era < k) & (yv != 0))[0]
            ev = np.nonzero(era == k)[0]
            if tr.size < 100:
                continue
            lab = (yv[tr] > 0).astype(float)
            bst = xgb.train(cfg, xgb.DMatrix(Xa[tr], label=lab,
                                             feature_names=na), 250)
            pred[ev] = bst.predict(xgb.DMatrix(Xa[ev], feature_names=na))
            sh = lab.copy()
            rs.shuffle(sh)
            bsh = xgb.train(cfg, xgb.DMatrix(Xa[tr], label=sh,
                                             feature_names=na), 250)
            predsh[ev] = bsh.predict(xgb.DMatrix(Xa[ev], feature_names=na))
            for a in list(MC.ASSET_ORDER) + ["ALL"]:
                am = np.ones(ev.size, bool) if a == "ALL" else \
                    (ai[ev] == MC.ASSET_ORDER.index(a))
                e2 = ev[am & (yv[ev] != 0)]
                if e2.size < 20:
                    continue
                call = np.where(pred[e2] >= 0.5, 1, -1)
                callsh = np.where(predsh[e2] >= 0.5, 1, -1)
                base = float(max((yv[e2] == 1).mean(), (yv[e2] == -1).mean()))
                m, lo, hi, nd = cluster_boot((call == yv[e2]).astype(float),
                                             d8[e2])
                rows.append({"arm": arm, "era": era_name(k), "asset": a,
                             "n_days": int(e2.size),
                             "accuracy": round(float((call == yv[e2]).mean()), 4),
                             "ci_lo": round(lo, 4), "ci_hi": round(hi, 4),
                             "majority_base": round(base, 4),
                             "shuffled_accuracy":
                                 round(float((callsh == yv[e2]).mean()), 4),
                             "long_base": round(float((yv[e2] == 1).mean()), 4),
                             "n_undecided_days":
                                 int((yv[ev] == 0)[am].sum()),
                             "mean_p": round(float(np.nanmean(pred[e2])), 4)})
        store[arm] = (pred, predsh)
        hb("dayside %s done" % arm)
    write_tsv(os.path.join(PROV, "GOALPATH_DAYSIDE.tsv"),
              "census 2 — the day-side call at day grain (walk-forward E2..E6, "
              "day-clustered CIs, shuffled control); label = which side's "
              "D-021 winners carry more $ that day", rows)
    np.savez_compressed(os.path.join(out_dir, "dayside.npz"),
                        pred=store["AT_TOKYO_CLOSE"][0],
                        pred_shuffled=store["AT_TOKYO_CLOSE"][1],
                        pred_open=store["AT_SESSION_OPEN"][0],
                        pred_open_shuffled=store["AT_SESSION_OPEN"][1],
                        y=Y["AT_TOKYO_CLOSE"], y_open=Y["AT_SESSION_OPEN"],
                        d8=d8, asset_idx=ai, era_idx=era, t_open=t_open)
    return rows


def day_side_call(out_dir=None):
    """(asset_idx, d8) -> the model's called side (+1/-1), the census-2 filter."""
    z = np.load(os.path.join(out_dir or OUT_ROOT, "dayside.npz"),
                allow_pickle=False)
    p, ai, d8 = z["pred_open"], z["asset_idx"], z["d8"]
    sh = z["pred_open_shuffled"]
    z.close()
    ok = np.isfinite(p)
    call = {(int(a), int(d)): (1 if v >= 0.5 else -1)
            for a, d, v in zip(ai[ok].tolist(), d8[ok].tolist(), p[ok].tolist())}
    ok2 = np.isfinite(sh)
    callsh = {(int(a), int(d)): (1 if v >= 0.5 else -1)
              for a, d, v in zip(ai[ok2].tolist(), d8[ok2].tolist(),
                                 sh[ok2].tolist())}
    return call, callsh


# ============================================================== CENSUS 3 =====
def census_classmix(out_dir=None):
    """Per-class seat economics + the seat-allocation table."""
    out_dir = out_dir or OUT_ROOT
    D = spine()
    score = sel_score(out_dir)
    kn = [str(x) for x in D["klass_names"]]
    era = D["era_idx"]
    sess = sessions_of(D)
    cert = D["cert_close_usd"]
    win = D["winner"] > 0
    rows = []
    for k in ERAS_EVAL:
        ev = np.nonzero(era == k)[0]
        nday = float(np.unique(sess[ev]).size)
        take = topn_takes(ev, score, sess)
        tset = set(take.tolist())
        for a in list(MC.ASSET_ORDER) + ["ALL"]:
            am = np.ones(ev.size, bool) if a == "ALL" else \
                (D["asset_idx"][ev] == MC.ASSET_ORDER.index(a))
            nsess = float(np.unique(sess[ev[am]]).size) or 1.0
            for ci, cname in enumerate(kn + ["ALL"]):
                cm = am if cname == "ALL" else (am & (D["klass_idx"][ev] == ci))
                idx = ev[cm]
                if idx.size == 0:
                    continue
                sel = np.array([i for i in idx.tolist() if i in tset],
                               dtype=np.int64)
                rows.append({
                    "era": era_name(k), "asset": a,
                    "klass": MC.display_name(cname.replace("_", "-")),
                    "n_candidates": int(idx.size),
                    "fires_per_session": round(idx.size / nsess, 3),
                    "winner_rate": round(float(win[idx].mean()), 5),
                    "winner_mean_cert_usd":
                        round(float(cert[idx][win[idx]].mean()), 2)
                        if win[idx].any() else float("nan"),
                    "mean_cert_usd": round(float(np.nanmean(cert[idx])), 2),
                    "wall_rate": round(float((D["walled"][idx] > 0).mean()), 4),
                    "n_selected": int(sel.size),
                    "sel_per_session": round(sel.size / nsess, 3),
                    "precision_at_selection":
                        round(float(win[sel].mean()), 4) if sel.size else float("nan"),
                    "usd_per_take_at_selection":
                        round(float(np.nanmean(cert[sel])), 2) if sel.size else float("nan"),
                    "usd_per_session_at_selection":
                        round(float(np.nansum(cert[sel]) / nsess), 2)
                        if sel.size else 0.0,
                })
    write_tsv(os.path.join(PROV, "GOALPATH_CLASSMIX.tsv"),
              "census 3 — class-mix seat economics (walk-forward selection "
              "score, top-3/asset/session)", rows)

    # ---- the (class, phase, vol-regime) cells ------------------------------
    crows = []
    for k in ERAS_EVAL:
        ev = np.nonzero(era == k)[0]
        take = set(topn_takes(ev, score, sess).tolist())
        for ci, cname in enumerate(kn):
            for ph in range(len(MC.PHASE_NAMES)):
                for rg in range(3):
                    m = ev[(D["klass_idx"][ev] == ci) &
                           (D["phase_dec"][ev] == ph) &
                           (D["regime_tercile"][ev] == rg)]
                    if m.size < 50:
                        continue
                    sel = np.array([i for i in m.tolist() if i in take],
                                   dtype=np.int64)
                    crows.append({
                        "era": era_name(k),
                        "klass": MC.display_name(cname.replace("_", "-")),
                        "phase": MC.PHASE_NAMES[ph], "vol_regime": rg,
                        "n": int(m.size),
                        "winner_rate": round(float(win[m].mean()), 5),
                        "mean_cert_usd": round(float(np.nanmean(cert[m])), 2),
                        "n_selected": int(sel.size),
                        "precision_at_selection":
                            round(float(win[sel].mean()), 4) if sel.size else float("nan"),
                        "usd_per_take_at_selection":
                            round(float(np.nanmean(cert[sel])), 2) if sel.size else float("nan"),
                    })
    write_tsv(os.path.join(PROV, "GOALPATH_CLASSCELLS.tsv"),
              "census 3 — the (class x phase x vol-regime) cells", crows)

    # ---- THE SEAT-ALLOCATION TABLE -----------------------------------------
    arows = []
    for k in ERAS_EVAL:
        tr = np.nonzero((era >= 0) & (era < k))[0]
        ev = np.nonzero(era == k)[0]
        # class ranking learned on the TRAIN block only
        ttake = topn_takes(tr, score, sess) if tr.size else np.zeros(0, np.int64)
        rank = []
        for ci, cname in enumerate(kn):
            sel = ttake[D["klass_idx"][ttake] == ci] if ttake.size else np.zeros(0, np.int64)
            v = float(np.nanmean(cert[sel])) if sel.size >= 50 else -1e9
            rank.append((v, ci, cname, int(sel.size)))
        rank.sort(reverse=True)
        base_rows, base_seats = replay(D["dec_sec"], D["exit_close_sec"], cert,
                                       sess, topn_takes(ev, score, sess))
        nsess = float(len(base_rows)) or 1.0
        base_usd = float(np.sum([r["realised"] for r in base_rows])) / nsess
        for K in range(1, len(kn) + 1):
            keep = set(x[1] for x in rank[:K])
            pool = ev[np.isin(D["klass_idx"][ev], list(keep))]
            if pool.size == 0:
                continue
            tk = topn_takes(pool, score, sess)
            rr, seats = replay(D["dec_sec"], D["exit_close_sec"], cert, sess, tk)
            ns = float(len(rr)) or 1.0
            per = float(np.sum([r["realised"] for r in rr])) / ns
            m, lo, hi, nd = cluster_boot([r["realised"] for r in rr],
                                         np.array([r["session"].split("|")[1]
                                                   for r in rr]))
            arows.append({
                "era": era_name(k), "policy": "TOP%d_CLASSES" % K,
                "classes": ",".join(MC.display_name(x[2].replace("_", "-"))
                                    for x in rank[:K]),
                "n_sessions": int(len(rr)), "n_seats": int(seats.size),
                "seats_per_session": round(seats.size / ns, 3),
                "usd_per_session": round(per, 2),
                "ci_lo": round(lo, 2), "ci_hi": round(hi, 2),
                "usd_per_trade": round(float(np.nanmean(cert[seats])), 2)
                if seats.size else float("nan"),
                "status_quo_usd_per_session": round(base_usd, 2),
                "delta_vs_status_quo": round(per - base_usd, 2),
            })
    write_tsv(os.path.join(PROV, "GOALPATH_SEAT_ALLOCATION.tsv"),
              "census 3 — the seat-allocation table: 3 seats/day allocated by "
              "TRAIN-block class economics vs the status quo, same selection "
              "skill", arows)
    return rows


# ==================================================== CENSUS 4 ECONOMICS =====
def _cont_load(ek, out_dir=None, tag=""):
    p = os.path.join(out_dir or OUT_ROOT, "cont%s_E%d.npz" % (tag, ek))
    z = np.load(p, allow_pickle=False)
    d = {k: z[k] for k in z.files}
    z.close()
    return d


def _cell_stats(v, r, mae, name, extra):
    f = np.isfinite(v)
    out = dict(extra)
    out["cell"] = name
    out["n_trades"] = int(f.sum())
    if not f.any():
        return out
    vv = v[f]
    rr = r[f]
    ok = np.isfinite(rr) & (rr > 0)
    out.update({
        "win_rate": round(float((vv > 0).mean()), 4),
        "usd_per_trade": round(float(vv.mean()), 2),
        "median_usd": round(float(np.median(vv)), 2),
        "risk_usd_mean": round(float(np.nanmean(rr)), 2),
        "risk_usd_median": round(float(np.nanmedian(rr)), 2),
        "risk_usd_p90": round(float(np.nanpercentile(rr[ok], 90)), 2)
        if ok.any() else float("nan"),
        "r_mult_mean": round(float(np.mean(vv[ok] / rr[ok])), 4) if ok.any() else float("nan"),
        "r_mult_median": round(float(np.median(vv[ok] / rr[ok])), 4) if ok.any() else float("nan"),
        "r_mult_p90": round(float(np.percentile(vv[ok] / rr[ok], 90)), 3) if ok.any() else float("nan"),
        "mae_usd_mean": round(float(np.nanmean(mae[f])), 2),
        "mae_usd_p90": round(float(np.nanpercentile(mae[f], 90)), 2),
        "frac_ge_600": round(float((vv >= 600).mean()), 4),
        "frac_ge_1000": round(float((vv >= 1000).mean()), 4),
    })
    return out


def census_econ(out_dir=None):
    """The complete economics table of census 4, per era x cell (+ replay)."""
    out_dir = out_dir or OUT_ROOT
    D = spine()
    sess_all = sessions_of(D)
    rows = []
    rep_rows = []
    for ek in ERAS_EVAL:
        Z = _cont_load(ek, out_dir)
        idx = Z["idx"]
        val, ex, mae, ent, ru = (Z["val"], Z["exit_sec"], Z["mae"],
                                 Z["entry_sec"], Z["r_usd"])
        sess = sess_all[idx]
        nsess = float(np.unique(sess).size)
        for ci, cname in enumerate(CELLS):
            e_name, s_name, x_name = cname.split("|")
            ei = ENTRIES.index(e_name)
            si = STOPS.index(s_name)
            r = ru[:, ei * len(STOPS) + si]
            st = _cell_stats(val[:, ci], r, mae[:, ci], cname,
                             {"era": era_name(ek), "asset": "ALL"})
            st["trades_per_session"] = round(st["n_trades"] / nsess, 3)
            rows.append(st)
            # the one-position replay of TAKE-EVERYTHING in this cell
            rr, seats = replay(ent[:, ei], ex[:, ci], val[:, ci], sess,
                               np.nonzero(np.isfinite(val[:, ci]))[0])
            if not rr:
                continue
            per = np.array([x["realised"] for x in rr])
            days = np.array([x["session"].split("|")[1] for x in rr])
            m, lo, hi, nd = cluster_boot(per, days)
            dd = session_dd(val[:, ci], ex[:, ci], rr)
            rep_rows.append({
                "era": era_name(ek), "cell": cname, "arm": "TAKE_ALL",
                "n_sessions": len(rr), "n_seats": int(seats.size),
                "seats_per_session": round(seats.size / len(rr), 3),
                "usd_per_session": round(float(per.mean()), 2),
                "ci_lo": round(lo, 2), "ci_hi": round(hi, 2),
                "usd_per_trade": round(float(np.nanmean(val[seats, ci])), 2)
                if seats.size else float("nan"),
                "mdd_mean": round(float(np.mean(dd)), 2),
                "mdd_p90": round(float(np.percentile(dd, 90)), 2),
            })
        hb("econ %s: %d cells" % (era_name(ek), len(CELLS)))
    write_tsv(os.path.join(PROV, "GOALPATH_CONT_ECON.tsv"),
              "census 4 — the complete economics table: every "
              "entry x stop x exit cell, per era (all G1/G2 confirmed "
              "extremes, winners AND losers)", rows)
    write_tsv(os.path.join(PROV, "GOALPATH_CONT_REPLAY.tsv"),
              "census 4 — one-position-per-asset chronological replay of "
              "TAKE-EVERYTHING in each cell", rep_rows)
    return rows, rep_rows


# ---------------------------------------------- the decidability gate -------
def trend_gate(out_dir=None, keep_frac=0.3):
    """Walk-forward gate on the [conf, entry] post-window block (the delay
    census's own decidability features) for the TREND entries."""
    import xgboost as xgb
    out_dir = out_dir or OUT_ROOT
    D = spine()
    cfg = {"max_depth": 4, "eta": 0.06, "min_child_weight": 40,
           "subsample": 0.9, "colsample_bytree": 0.9, "tree_method": "hist",
           "objective": "reg:squarederror", "seed": SEED, "nthread": 8}
    gate = {}
    for ti, Dl in enumerate(TREND_D):
        for si, sname in enumerate(STOPS):
            cname = "TREND_%d|%s|TRAIL_1.0R" % (Dl, sname)
            ci = CELL_IDX[cname]
            Xs, ys, es, ids = [], [], [], []
            for ek in ERAS_EVAL:
                Z = _cont_load(ek, out_dir)
                v = Z["val"][:, ci]
                f = np.isfinite(v)
                Xs.append(Z["pp"][f, ti, :])
                ys.append(v[f])
                es.append(np.full(int(f.sum()), ek))
                ids.append(Z["idx"][f])
            Xg = np.vstack(Xs)
            yg = np.concatenate(ys)
            eg = np.concatenate(es)
            ig = np.concatenate(ids)
            sc = np.full(yg.size, np.nan)
            for k in ERAS_EVAL[1:]:
                tr = np.nonzero(eg < k)[0]
                ev = np.nonzero(eg == k)[0]
                if tr.size < 2000 or ev.size == 0:
                    continue
                bst = xgb.train(cfg, xgb.DMatrix(Xg[tr], label=yg[tr]), 200)
                sc[ev] = bst.predict(xgb.DMatrix(Xg[ev]))
            gate[cname] = (ig, eg, sc, yg)
            hb("gate %s: n %d scored %d" % (cname, yg.size,
                                            int(np.isfinite(sc).sum())))
    np.savez_compressed(
        os.path.join(out_dir, "trend_gate.npz"),
        **{("%s@%s" % (k, part)): v for k, (a, b, c, d_) in gate.items()
           for part, v in (("idx", a), ("era", b), ("score", c), ("val", d_))})
    # the deliverable: $/trade by gate decile, per era
    rows = []
    for cname, (ig, eg, sc, yg) in gate.items():
        for k in ERAS_EVAL[1:]:
            m = np.nonzero((eg == k) & np.isfinite(sc))[0]
            if m.size < 500:
                continue
            q = np.argsort(-sc[m], kind="stable")
            for frac in (0.05, 0.10, 0.20, 0.30, 0.50, 1.0):
                sel = m[q[:max(1, int(frac * m.size))]]
                rows.append({"cell": cname, "era": era_name(k),
                             "gate_keep_frac": frac, "n": int(sel.size),
                             "usd_per_trade": round(float(yg[sel].mean()), 2),
                             "win_rate": round(float((yg[sel] > 0).mean()), 4),
                             "ungated_usd_per_trade":
                                 round(float(yg[m].mean()), 2)})
    write_tsv(os.path.join(PROV, "GOALPATH_TREND_GATE.tsv"),
              "census 4 — the trend entries gated by the [conf, entry] "
              "post-window decidability block (m2_delay._post_path features, "
              "walk-forward GBT), $/trade by gate keep-fraction", rows)
    return gate


# =============================================================== VERDICT =====
def _filters(D, out_dir):
    """The stackable filters: the ambiguity veto (census 1) and the day-side
    call (census 2), plus their shuffled controls."""
    z = np.load(os.path.join(out_dir, "ambig.npz"), allow_pickle=False)
    ev, two1, two2 = z["ev"], z["two1"], z["two2"]
    z.close()
    one1 = np.zeros(D["d8"].size, bool)
    one2 = np.zeros(D["d8"].size, bool)
    one1[ev] = ~two1
    one2[ev] = ~two2
    call, callsh = day_side_call(out_dir)
    ai = D["asset_idx"].tolist()
    d8 = D["d8"].tolist()
    sd = D["side"].tolist()
    ds = np.array([call.get((a, d), 0) == s for a, d, s in zip(ai, d8, sd)])
    dsh = np.array([callsh.get((a, d), 0) == s for a, d, s in zip(ai, d8, sd)])
    rs = np.random.RandomState(SEED)
    onesh = one1.copy()
    rs.shuffle(onesh)
    return {"NONE": np.ones(D["d8"].size, bool), "VETO_K": one1,
            "VETO_2K": one2, "DAYSIDE": ds,
            "VETO_K+DAYSIDE": one1 & ds,
            "SHUFFLED_VETO": onesh, "SHUFFLED_DAYSIDE": dsh}


def census_verdict(out_dir=None, top_cells=12):
    out_dir = out_dir or OUT_ROOT
    D = spine()
    sess_all = sessions_of(D)
    score = sel_score(out_dir)
    filt = _filters(D, out_dir)
    # the cells worth stacking: best mean $/trade at n >= 2,000 in E6, plus
    # every TREND cell (the user's own class) — declared, not fished
    Z6 = _cont_load(ERA_HEADLINE, out_dir)
    cand = []
    for ci, cname in enumerate(CELLS):
        v = Z6["val"][:, ci]
        f = np.isfinite(v)
        if int(f.sum()) < 2000:
            continue
        cand.append((float(v[f].mean()), cname))
    cand.sort(reverse=True)
    keep = [c for _, c in cand[:top_cells]]
    for c in CELLS:
        if c.startswith("TREND") and c.endswith("TRAIL_1.0R") and c not in keep:
            keep.append(c)
    gp = os.path.join(out_dir, "trend_gate.npz")
    GT = dict(np.load(gp, allow_pickle=False)) if os.path.exists(gp) else {}
    rows = []
    for ek in ERAS_EVAL:
        Z = _cont_load(ek, out_dir)
        idx = Z["idx"]
        sess = sess_all[idx]
        nall = float(np.unique(sess).size)
        for cname in keep:
            ci = CELL_IDX[cname]
            e_name, s_name, _x = cname.split("|")
            ei = ENTRIES.index(e_name)
            si = STOPS.index(s_name)
            v = Z["val"][:, ci]
            ent = Z["entry_sec"][:, ei]
            ex = Z["exit_sec"][:, ci]
            r = Z["r_usd"][:, ei * len(STOPS) + si]
            base = np.isfinite(v)
            fl = dict(filt)
            if ("%s@idx" % cname) in GT:
                gi, ge, gs = (GT["%s@idx" % cname], GT["%s@era" % cname],
                              GT["%s@score" % cname])
                m = np.nonzero((ge == ek) & np.isfinite(gs))[0]
                if m.size > 500:
                    o = np.argsort(-gs[m], kind="stable")
                    rsg = np.random.RandomState(SEED)
                    osh = rsg.permutation(m.size)
                    for frac in (0.05, 0.10, 0.30):
                        n_k = max(1, int(frac * m.size))
                        sel = set(gi[m[o[:n_k]]].tolist())
                        gm = np.array([int(i) in sel for i in idx.tolist()])
                        fl["GATE_TOP%d" % int(frac * 100)] = gm
                        fl["GATE_TOP%d+VETO_K" % int(frac * 100)] = \
                            gm & filt["VETO_K"][idx]
                        fl["GATE_TOP%d+DAYSIDE" % int(frac * 100)] = \
                            gm & filt["DAYSIDE"][idx]
                        ssh = set(gi[m[osh[:n_k]]].tolist())
                        fl["SHUFFLED_GATE_TOP%d" % int(frac * 100)] = \
                            np.array([int(i) in ssh for i in idx.tolist()])
            for fname, fm in fl.items():
                for selname in ("ALL", "MODEL_TOP3"):
                    fv = fm[idx] if fm.size == D["d8"].size else fm
                    m = np.nonzero(base & fv)[0]
                    if selname == "MODEL_TOP3":
                        m = topn_takes(m, score[idx], sess)
                    if m.size == 0:
                        continue
                    rr, seats = replay(ent, ex, v, sess, m)
                    if not rr:
                        continue
                    per = np.array([x["realised"] for x in rr])
                    days = np.array([x["session"].split("|")[1] for x in rr])
                    mm, lo, hi, nd = cluster_boot(per, days)
                    dd = session_dd(v, ex, rr)
                    rows.append({
                        "era": era_name(ek), "cell": cname, "filter": fname,
                        "selection": selname,
                        "n_sessions": len(rr), "n_seats": int(seats.size),
                        "seats_per_session": round(seats.size / len(rr), 3),
                        "usd_per_session": round(float(per.mean()), 2),
                        "ci_lo": round(lo, 2), "ci_hi": round(hi, 2),
                        "usd_per_trade": round(float(np.nanmean(v[seats])), 2)
                        if seats.size else float("nan"),
                        "risk_usd_median": round(float(np.nanmedian(r[seats])), 2)
                        if seats.size else float("nan"),
                        "win_rate": round(float((v[seats] > 0).mean()), 4)
                        if seats.size else float("nan"),
                        "mdd_mean": round(float(np.mean(dd)), 2),
                        "vs_D048_bar": round(float(per.mean()) / BAR_SESSION_USD, 3),
                    })
        hb("verdict %s done" % era_name(ek))
    write_tsv(os.path.join(PROV, "GOALPATH_STACKED.tsv"),
              "census 4 verdict — the stacked configurations "
              "(cell x filter x selection), one-position-per-asset replay, "
              "day-clustered CIs", rows)
    return rows


# ======================================================= THE TEACHER TAKES ===
# The 15 sealed HAND takes (E6 rounds 1 / 2 / 2x).  Identity recovered from the
# sealed blind ledgers + EPISODE_ACCESS.tsv (episode_id -> rep_cid); the dollars
# are NOT re-stated from prose here — every one is re-read from the committed
# matrix certificate for that cid, which is also how the r2x per-take dollars
# (never persisted anywhere) are recovered.
TEACHER_TAKES = (
    ("r1", "HG-20240419-032439-L"), ("r1", "SI-20240419-047569-S"),
    ("r1", "HG-20240422-032440-L"), ("r1", "SI-20240422-046875-S"),
    ("r1", "HG-20240423-012647-L"), ("r1", "HG-20240423-047304-L"),
    ("r1", "SI-20240423-048526-L"),
    ("r2", "SI-20240424-007365-S"), ("r2", "HG-20240425-011468-S"),
    ("r2", "SI-20240426-056468-S"),
    ("r2x", "SI-20240429-050528-L"), ("r2x", "SI-20240430-051995-L"),
    ("r2x", "HG-20240501-063226-S"), ("r2x", "SI-20240502-054126-L"),
    ("r2x", "HG-20240503-058997-L"),
)


def census_teacher(out_dir=None):
    """Censuses 1, 2 and 4 applied to the teacher's 15 sealed hand takes."""
    out_dir = out_dir or OUT_ROOT
    D = spine()
    z = np.load(os.path.join(out_dir, "ambig.npz"), allow_pickle=False)
    ev, two1, two2 = z["ev"], z["two1"], z["two2"]
    z.close()
    one1 = np.zeros(D["d8"].size, bool)
    one2 = np.zeros(D["d8"].size, bool)
    one1[ev] = ~two1
    one2[ev] = ~two2
    call, _sh = day_side_call(out_dir)
    Z = _cont_load(ERA_HEADLINE, out_dir)
    cpos = {int(i): j for j, i in enumerate(Z["idx"].tolist())}
    key = {}
    for i in range(D["d8"].size):
        key[(int(D["asset_idx"][i]), int(D["d8"][i]), int(D["dec_sec"][i]),
             int(D["side"][i]))] = i
    kn = [str(x) for x in D["klass_names"]]
    rows = []
    for rnd, cid in TEACHER_TAKES:
        a, d8s, ds, ls = cid.split("-")
        k = (MC.ASSET_ORDER.index(a), int(d8s), int(ds), 1 if ls == "L" else -1)
        i = key.get(k)
        if i is None:
            rows.append({"round": rnd, "cid": cid, "status": "NOT_IN_SPINE"})
            continue
        j = cpos.get(int(i))
        r = {"round": rnd, "cid": cid, "status": "OK",
             "asset": a, "d8": int(d8s), "dec_sec": int(ds),
             "side": int(k[3]),
             "klass": MC.display_name(kn[int(D["klass_idx"][i])].replace("_", "-")),
             "cert_close_usd": round(float(D["cert_close_usd"][i]), 2),
             "walled": int(D["walled"][i] > 0),
             "d021_winner": int(D["winner"][i] > 0),
             "one_sided_K": int(one1[i]), "one_sided_2K": int(one2[i]),
             "day_side_call": call.get((k[0], k[1]), 0),
             "on_day_side": int(call.get((k[0], k[1]), 0) == k[3])}
        for cname in ("DELAY_120|EXT|PHASE", "TREND_1800|SWING|TRAIL_1.0R",
                      "TREND_3600|EXT|TRAIL_1.0R", "HOLD_300|EXT|TRAIL_1.0R"):
            ci = CELL_IDX[cname]
            r["cont_" + cname] = (round(float(Z["val"][j, ci]), 2)
                                  if j is not None and
                                  np.isfinite(Z["val"][j, ci]) else float("nan"))
        rows.append(r)
    write_tsv(os.path.join(PROV, "GOALPATH_TEACHER_TAKES.tsv"),
              "the teacher's 15 sealed HAND takes, re-read from the committed "
              "matrix certificate, with the census-1 veto flag, the census-2 "
              "day-side call and the census-4 re-pricing", rows)
    ok = [r for r in rows if r.get("status") == "OK"]
    tot = float(np.sum([r["cert_close_usd"] for r in ok]))
    kept1 = [r for r in ok if r["one_sided_K"]]
    kept2 = [r for r in ok if r["one_sided_2K"]]
    keptd = [r for r in ok if r["on_day_side"]]
    summ = [{"arm": "ALL_15", "n": len(ok), "total_usd": round(tot, 2),
             "usd_per_trade": round(tot / max(1, len(ok)), 2),
             "n_walls": sum(r["walled"] for r in ok),
             "n_d021_winners": sum(r["d021_winner"] for r in ok)}]
    for nm, sub in (("VETO_K", kept1), ("VETO_2K", kept2), ("DAYSIDE", keptd)):
        t = float(np.sum([r["cert_close_usd"] for r in sub])) if sub else 0.0
        summ.append({"arm": nm, "n": len(sub), "total_usd": round(t, 2),
                     "usd_per_trade": round(t / max(1, len(sub)), 2),
                     "n_walls": sum(r["walled"] for r in sub),
                     "n_d021_winners": sum(r["d021_winner"] for r in sub),
                     "walls_removed": sum(r["walled"] for r in ok)
                     - sum(r["walled"] for r in sub),
                     "winners_forfeited": sum(r["d021_winner"] for r in ok)
                     - sum(r["d021_winner"] for r in sub),
                     "usd_forfeited": round(tot - t, 2)})
    write_tsv(os.path.join(PROV, "GOALPATH_TEACHER_FILTERS.tsv"),
              "the veto / day-side filters applied to the teacher's 15 takes",
              summ)
    hb("teacher: %d takes, pooled $%.2f (%.2f/trade)"
       % (len(ok), tot, tot / max(1, len(ok))))
    return rows


# ============================================== THE TAU-TENSOR IDENTITY ======
def tau_proof(asset="SI", month="202201", n=400, out_dir=None):
    """The m1 first-passage tau tensors and this census price the SAME object.

    The m1 label tensors (artifacts/cache/port/m1/skel) store, per candidate and
    per anchor, tau_up[k] / tau_dn[k] = the first session second at which the
    favourable / adverse excursion reaches rung k, where
        rung_k = round_half_up(k * 0.02 * ATR14_usd / mult, tick_px),  k = 1..200
    (engine/cpp/qr_skel/src/geom.cpp:34, include/qr_skel/geom.hpp:29-30).

    They are built from the SANE two-sided mid grid — the same `s.vt` / `s.vm`
    this census prices on.  So: the tensors price ARBITRARY stop/target
    structures exactly, but only on the 0.02-ATR rung ladder AFTER tick
    rounding; a structural stop is "2 ticks beyond a swing price", which is NOT
    a rung.  Census 4 therefore prices on the grid ITSELF, which is the tensors'
    own source and carries no rung rounding at all.  This receipt proves the
    two agree wherever the tensor grid can express the question.
    """
    out_dir = out_dir or OUT_ROOT
    root = "/workspace/artifacts/cache/port/m1/skel/shards"
    meta = json.load(open(os.path.join(root, "%s_%s.json" % (asset, month))))
    off = {a["name"]: (a["dtype"], a["count"], a["offset"]) for a in meta["arrays"]}
    buf = np.memmap(os.path.join(root, meta["bin"]), dtype=np.uint8, mode="r")

    def arr(nm):
        dt, ct, of = off[nm]
        return np.frombuffer(buf, dtype=np.dtype(dt), count=ct, offset=of)

    d8 = arr("date8")
    dec = arr("dec_sec")
    side = arr("side")
    atr = arr("atr14_usd")
    emid = arr("a0_entry_mid")
    tau_up = arr("a0_tau_up").reshape(-1, meta["rung_count"])
    tau_dn = arr("a0_tau_dn").reshape(-1, meta["rung_count"])
    spec = C.ASSETS[asset]
    mult = float(spec["mult"])
    tick = float(spec["tick_px"])
    rs = np.random.RandomState(SEED)
    pick = rs.choice(d8.size, size=min(n, d8.size), replace=False)
    n_ok = n_cmp = n_bad = 0
    bad = []
    for i in sorted(pick.tolist()):
        sess = A.load_session(asset, int(d8[i]))
        s = sess["s"]
        j0 = int(np.searchsorted(s.vt, int(dec[i]), side="left"))
        vt = s.vt[j0:]
        f = (s.vm[j0:] - float(emid[i])) * int(side[i])       # price units
        for k in (1, 5, 10, 25, 50, 100, 200):
            rung_px = X.round_half_up(k * 0.02 * float(atr[i]) / mult, tick)
            q = np.nonzero(f >= rung_px)[0]
            mine = int(vt[q[0]]) if q.size else -1
            theirs = int(tau_up[i, k - 1])
            n_cmp += 1
            if mine == theirs:
                n_ok += 1
            else:
                n_bad += 1
                if len(bad) < 8:
                    bad.append((int(d8[i]), int(dec[i]), k, mine, theirs))
            q2 = np.nonzero(-f >= rung_px)[0]
            mine2 = int(vt[q2[0]]) if q2.size else -1
            theirs2 = int(tau_dn[i, k - 1])
            n_cmp += 1
            if mine2 == theirs2:
                n_ok += 1
            else:
                n_bad += 1
                if len(bad) < 8:
                    bad.append((int(d8[i]), int(dec[i]), -k, mine2, theirs2))
    rec = {"version": VERSION, "asset": asset, "month": month,
           "n_candidates": int(len(pick)), "n_comparisons": n_cmp,
           "n_identical": n_ok, "n_mismatch": n_bad, "mismatches": bad,
           "rung_rule": "round_half_up(k * 0.02 * ATR14_usd / mult, tick_px)",
           "census4_pricing": "the SANE mid grid itself (s.vt/s.vm) — the "
                              "tensors' own source; NO rung rounding enters "
                              "census 4, because a structural stop is 2 ticks "
                              "beyond a swing PRICE and is not a ladder rung"}
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "tau_proof.receipt.json"), "w") as fh:
        json.dump(rec, fh, indent=1, sort_keys=True)
    hb("tau-proof: %d/%d first-passage times identical (%d mismatch)"
       % (n_ok, n_cmp, n_bad))
    return rec


# ================================================================= I/O =======
def write_tsv(path, title, rows, extra=()):
    if not rows:
        hb("write_tsv: %s — NO ROWS" % path)
        return
    cols = list(rows[0].keys())
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write("# %s (%s)\n" % (title, VERSION))
        for e in extra:
            fh.write("# %s\n" % e)
        fh.write("\t".join(cols) + "\n")
        for r in rows:
            fh.write("\t".join(_fmt(r.get(c, "")) for c in cols) + "\n")
    hb("wrote %s (%d rows)" % (path, len(rows)))


def _fmt(v):
    if isinstance(v, float):
        if not np.isfinite(v):
            return "nan"
        return ("%.6g" % v)
    return str(v)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--spine", action="store_true")
    ap.add_argument("--ambig", action="store_true")
    ap.add_argument("--cont", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--eras", type=str, default="")
    ap.add_argument("--limit-days", type=int, default=0)
    ap.add_argument("--shift", type=int, default=0)
    ap.add_argument("--tag", type=str, default="")
    ap.add_argument("--select", action="store_true")
    ap.add_argument("--days", action="store_true")
    ap.add_argument("--dayside", action="store_true")
    ap.add_argument("--classmix", action="store_true")
    ap.add_argument("--econ", action="store_true")
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--verdict", action="store_true")
    ap.add_argument("--teacher", action="store_true")
    ap.add_argument("--tau-proof", action="store_true")
    a = ap.parse_args(argv)
    eras = tuple(int(x) for x in a.eras.split(",")) if a.eras else ERAS_EVAL
    if a.spine:
        build_spine()
    if a.ambig:
        census_ambiguity()
    if a.cont:
        run_cont(workers=a.workers, eras=eras,
                 limit_days=a.limit_days or None, shift=a.shift, tag=a.tag)
    if a.select:
        run_select(workers=a.workers)
    if a.days:
        build_days(workers=a.workers)
    if a.dayside:
        census_dayside(workers=a.workers)
    if a.classmix:
        census_classmix()
    if a.econ:
        census_econ()
    if a.gate:
        trend_gate()
    if a.verdict:
        census_verdict()
    if a.teacher:
        census_teacher()
    if a.tau_proof:
        tau_proof()
    return 0


if __name__ == "__main__":
    sys.exit(main())
