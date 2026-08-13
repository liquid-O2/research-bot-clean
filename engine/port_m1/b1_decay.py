#!/usr/bin/python3
"""PORT M1 Track B-1 — confirmation-decay study (§2).  Pins tau*(asset).

METHOD (exactly §2):
  * The candidate universe is the G1 CONFIRMATION set, not the m0 roster: the
    m0 roster is already conditioned on the tau=60 state filter, so re-deriving
    confirmations (same rungs, same thresholds, same dedup, m0's zigzag_scan
    verbatim) is what makes value(tau)/value(0) a fair comparison.  The tau=60
    slice of this universe reproduces the m0 roster exactly — asserted by
    verify_vs_m0() and receipted in decay_m0_differential.tsv.
  * Per candidate and per tau in {0,15,30,60,90,120,180,300}: entry mid at
    confirmation+tau, wall $900 (m0 walls.json, identical for all three
    assets), session-scoped cost_rt, both m0 §8 certificate variants.
  * PRIMARY certificate = walled PHASE-CLOSE value (the §2 sentence "wall $900;
    phase-close exit variant").  Peak-exit is carried as a sensitivity.
  * PRIMARY MAE = MAE-before-peak inside the walled window (the m0 §8
    certificate MAE, the quantity the wall itself was fitted on).  Realised
    hold MAE (max adverse over [entry, exit]) is carried as a sensitivity.
    §2 says "value/MAE certificates" without naming which MAE: BOTH are
    computed and the pin rule is evaluated on BOTH (reported side by side).
  * "mean value decay" = decay of the POOLED MEAN, 1 - mean(v(tau))/mean(v(0)),
    on the PAIRWISE-COMPLETE sample (candidates valid at both 0 and tau).  That
    is the reading D-033 itself uses ("$1,616/$1,609 vs $1,623" are means).
    Median-of-ratios is emitted beside it as a diagnostic.

PRE-REGISTERED PIN RULE (§2, applied verbatim in pin_tau()):
    tau*(asset) = largest tau <= 120 with pooled-FIT mean value decay < 1.5%
    vs tau=0 AND mean MAE inflation < 5%; floored at 30s.
"""
import json
import multiprocessing as mp
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import m1_common as M
import common as C
import census_common as X
import c_a_cost as CA
import c_c_roster as CC

SECTION = "§2 confirmation-decay"

TAUS = (0, 15, 30, 60, 90, 120, 180, 300)
TAU_CAP = 120                   # §2 / D-033
TAU_FLOOR = 30                  # §2 execution realism
DECAY_MAX = 0.015               # mean value decay < 1.5%
MAE_INFLATION_MAX = 0.05        # mean MAE inflation < 5%

PARAMS = {
    "spec_section": SECTION,
    "taus_sec": list(TAUS),
    "universe": "G1 confirmations (m0 §8 rungs/thresholds/dedup, zigzag_scan "
                "reused verbatim); tau=60 slice must equal the m0 roster",
    "wall_source": "m0 walls.json (wall_usd per asset)",
    "cost_rt": "m0 session-scoped median two-sided spread + $5.00",
    "precision": "excursion prefix-maxima quantised to float32, mirroring the "
                 "m0 skeleton storage, so the tau=60 slice is field-exact vs "
                 "the frozen m0 certificates",
    "primary_certificate": "walled phase-close value (§2)",
    "primary_mae": "MAE-before-peak inside the walled window (m0 §8)",
    "secondary": ["peak-exit value", "realised hold MAE"],
    "decay_statistic": "1 - mean(v(tau))/mean(v(0)) on the pairwise-complete "
                       "sample (ratio of means, D-033 convention)",
    "pin_rule": "largest tau <= 120 with pooled-FIT mean value decay < 1.5%% "
                "AND mean MAE inflation < 5%%; floored at 30s",
    "cells": "(asset, rung, phase-of-confirmation, era)",
}

# per-candidate, per-tau measurements
TAU_FIELDS = ("valid", "entry_mid", "v_close", "v_peak", "mae_peak", "mae_hold")
CAND_FIELDS = ("date8", "conf_sec", "side", "rung_mask", "phase_conf", "year")


# ------------------------------------------------------ confirmation scan ----
def session_confirmations(s, asset, atr, phase_med, trade_date):
    """m0 §8 sub-pass 1 confirmations, deduped by (conf_sec, side).

    Returns a sorted list of (conf_sec, side, rung_mask).  This is c_c_roster's
    own code path (rung thresholds + zigzag_scan) with no reimplementation.
    """
    spec = C.ASSETS[asset]
    mult, tick_px, tick_usd = spec["mult"], spec["tick_px"], spec["tick_usd"]
    vt_l = s.vt.tolist()
    vm_l = s.vm.tolist()
    vphase = s.phase_tag[s.vt].tolist()
    merged = {}
    for ri, r in enumerate(X.RUNGS):
        per_phase = []
        for p in range(X.N_PHASES):
            pm = phase_med.get((asset, trade_date.year, X.PHASE_NAMES[p]),
                               float("nan"))
            floor_spread = (X.RUNG_FLOOR_SPREAD_MULT * pm
                            if np.isfinite(pm) else 0.0)
            usd = max(r * atr, X.RUNG_FLOOR_TICKS * tick_usd, floor_spread)
            per_phase.append(X.round_half_up(usd / mult, tick_px))
        thr_l = [per_phase[p] for p in vphase]
        for (_px, _psec, conf_sec, side) in CC.zigzag_scan(vt_l, vm_l, thr_l):
            k = (conf_sec, side)
            merged[k] = merged.get(k, 0) | CC.RUNG_BITS[ri]
    return [(k[0], k[1], merged[k]) for k in sorted(merged)]


# -------------------------------------------------------- certificate pass ---
def certify_at(s, mult, entry_sec, side, W, cost_rt):
    """Walled certificates for an entry at `entry_sec` (state already checked).

    Returns (v_close, v_peak, mae_peak, mae_hold).  Semantics are m0 §8
    sub-pass 3's, recomputed from the mid path because the m0 skeleton is
    anchored at conf+60 and cannot answer other entry clocks.
    """
    j0 = int(np.searchsorted(s.vt, entry_sec, side="left"))
    entry = float(s.mid[entry_sec])
    vt = s.vt[j0:]
    f = (s.vm[j0:] - entry) * side * mult
    # PRECISION FIDELITY: the m0 path skeleton stores its prefix maxima as
    # float32 (c_c_roster sub-pass 1), and every m0 certificate/wall test was
    # taken against those float32 values.  Excursions land on exact half-tick
    # dollar amounts ($12.50 grid for all three assets) and the $900 wall is on
    # that grid, so a float64 recomputation disagrees with m0 on EXACT-wall
    # ties (measured: 954/189,821 SI candidates).  Quantising to float32 here
    # makes the tau=60 slice reproduce the frozen m0 certificates exactly and
    # keeps the wall test identical across all taus.
    run_f = np.maximum.accumulate(f).astype(np.float32)
    run_a = np.maximum.accumulate(-f).astype(np.float32)
    f = f.astype(np.float32)
    n = f.size

    iw = int(np.searchsorted(run_a, W, side="left"))     # run_a is monotone
    walled = iw < n
    # ---- peak-exit variant
    if iw > 0:
        mfe_w = float(run_f[iw - 1])
        argmax_idx = int(np.searchsorted(run_f, mfe_w, side="left"))
        if argmax_idx >= iw:
            argmax_idx = iw - 1
    else:
        mfe_w, argmax_idx = 0.0, 0
    if walled and mfe_w <= 0.0:
        v_peak = -W - cost_rt
        mae_peak = float(run_a[iw])
    else:
        v_peak = mfe_w - cost_rt
        mae_peak = float(run_a[argmax_idx])

    # ---- phase-close variant
    pc_sec = X.next_phase_boundary(s, entry_sec)
    ipc = int(np.searchsorted(vt, pc_sec, side="right")) - 1
    if ipc < 0:
        ipc = 0
    if walled and int(vt[iw]) <= pc_sec:
        v_close = -W - cost_rt
        exit_idx = iw
    else:
        v_close = float(f[ipc]) - cost_rt
        exit_idx = ipc
    mae_hold = float(run_a[exit_idx])
    return v_close, v_peak, mae_peak, mae_hold


def _shard(args):
    asset, month, sess, phase_med, cost_map, W, root = args
    spec = C.ASSETS[asset]
    mult = spec["mult"]
    bars = X.load_bars(asset, root)
    cand = {k: [] for k in CAND_FIELDS}
    tau_cols = {(t, f): [] for t in TAUS for f in TAU_FIELDS}
    conf_rows = []

    for trade_date, path in sess:
        bar = bars.get(trade_date)
        atr = bar["ATR14_prev_usd"] if bar else float("nan")
        if not np.isfinite(atr):
            continue
        s = X.load_session(asset, trade_date, path)
        if s.vt.size < 2:
            continue
        iso = trade_date.isoformat()
        cost_rt = cost_map.get((asset, iso), float("nan"))
        if not np.isfinite(cost_rt):
            cost_rt = C.FEES_RT
        confs = session_confirmations(s, asset, atr, phase_med, trade_date)
        dd = M.d8(trade_date)
        for (conf_sec, side, mask) in confs:
            conf_rows.append((dd, conf_sec, side, mask))
            cand["date8"].append(dd)
            cand["conf_sec"].append(conf_sec)
            cand["side"].append(side)
            cand["rung_mask"].append(mask)
            cand["phase_conf"].append(int(s.phase_tag[conf_sec]))
            cand["year"].append(trade_date.year)
            for t in TAUS:
                e = conf_sec + t
                ok = (e < s.n) and (s.state[e] == C.ST_TWO_SIDED)
                if ok:
                    vc, vp, mp_, mh = certify_at(s, mult, e, side, W, cost_rt)
                    tau_cols[(t, "valid")].append(1)
                    tau_cols[(t, "entry_mid")].append(float(s.mid[e]))
                    tau_cols[(t, "v_close")].append(vc)
                    tau_cols[(t, "v_peak")].append(vp)
                    tau_cols[(t, "mae_peak")].append(mp_)
                    tau_cols[(t, "mae_hold")].append(mh)
                else:
                    tau_cols[(t, "valid")].append(0)
                    for f in TAU_FIELDS[1:]:
                        tau_cols[(t, f)].append(float("nan"))

    arrays = {}
    dtypes = {"date8": np.int32, "conf_sec": np.int32, "side": np.int8,
              "rung_mask": np.uint8, "phase_conf": np.int8, "year": np.int16}
    for k in CAND_FIELDS:
        arrays[k] = np.array(cand[k], dtype=dtypes[k])
    for t in TAUS:
        arrays["t%03d_valid" % t] = np.array(tau_cols[(t, "valid")], np.int8)
        for f in TAU_FIELDS[1:]:
            arrays["t%03d_%s" % (t, f)] = np.array(tau_cols[(t, f)],
                                                   np.float64)
    return asset, month, arrays


def run_scan(assets, workers, months=None):
    phase_med = CA.phase_median_spreads(M.M0_ROOT)
    cost_map = CA.session_cost_rt(M.M0_ROOT)
    with open(os.path.join(M.M0_ROOT, "walls.json")) as fh:
        walls = json.load(fh)["walls"]
    tasks = []
    for asset in assets:
        by_month = {}
        for d, p in X.session_paths(asset, M.M0_ROOT):
            if months and X.month_key(d) not in months:
                continue
            by_month.setdefault(X.month_key(d), []).append((d, p))
        for mk in sorted(by_month):
            tasks.append((asset, mk, by_month[mk], phase_med, cost_map,
                          float(walls[asset]["wall_usd"]), M.M0_ROOT))
    M.hb("b1 decay: %d (asset,month) tasks" % len(tasks))
    if workers <= 1 or len(tasks) <= 1:
        res = [_shard(t) for t in tasks]
    else:
        with mp.Pool(min(workers, len(tasks))) as pool:
            res = list(pool.map(_shard, tasks, chunksize=1))

    out = {}
    for asset in assets:
        parts = sorted([(m, a) for (n, m, a) in res if n == asset])
        merged = {}
        keys = list(parts[0][1].keys()) if parts else []
        for k in keys:
            merged[k] = np.concatenate([p[1][k] for p in parts])
        C.savez_det(M.out_path("decay", "decay_cert_%s.npz" % asset), **merged)
        # G1 confirmation universe for §6 (rebuild the roster at any tau)
        C.savez_det(M.out_path("decay", "g1_conf_%s.npz" % asset),
                    date8=merged["date8"], conf_sec=merged["conf_sec"],
                    side=merged["side"], rung_mask=merged["rung_mask"],
                    phase_conf=merged["phase_conf"], year=merged["year"])
        M.hb("b1 decay %s: %d confirmations" % (asset, merged["date8"].size))
        out[asset] = merged
    return out


# ---------------------------------------------------------- aggregation -----
def _cells(a, rung_i, phase_i, era):
    return (a, rung_i, phase_i, era)


def aggregate(assets, data=None):
    """Per (asset, rung, phase, era) x tau rows, pairwise-complete vs tau=0."""
    rows = []
    for asset in assets:
        r = data[asset] if data else _load(asset)
        v0 = r["t000_valid"].astype(bool)
        year = r["year"].astype(np.int64)
        mask = r["rung_mask"]
        phase = r["phase_conf"]
        rung_sel = [(("r%.3f" % X.RUNGS[i]), (mask & CC.RUNG_BITS[i]) > 0)
                    for i in range(len(X.RUNGS))]
        rung_sel.append(("ALL", np.ones(mask.size, dtype=bool)))
        phase_sel = [(X.PHASE_NAMES[p], phase == p) for p in range(X.N_PHASES)]
        phase_sel.append(("ALL", np.ones(phase.size, dtype=bool)))
        era_sel = [(M.ERA_FIT, np.isin(year, np.array(M.FIT_YEARS))),
                   (M.ERA_GATE, year == 2025),
                   (M.ERA_ALL, np.ones(year.size, dtype=bool))]
        for y in sorted(set(year.tolist())):
            era_sel.append((str(y), year == y))
        # POPULATION dimension.  ALL = every confirmation (unselected, the
        # honest denominator).  K1K_AT_TAU0 = candidates whose tau=0 peak-exit
        # certificate reached $1,000 — reported because §2's cells invite it,
        # but SELECTION-BIASED by construction (conditioning on the tau=0
        # outcome inflates value(0) by regression to the mean), so it can only
        # ever overstate decay.  Never the pin population.
        pop_sel = [("ALL", np.ones(v0.size, dtype=bool)),
                   ("K1K_AT_TAU0", v0 & (r["t000_v_peak"] >= X.LEG_1K))]
        for rname, rsel in rung_sel:
            for pname, psel in phase_sel:
                for ename, esel in era_sel:
                    for popname, popsel in pop_sel:
                        base = rsel & psel & esel & popsel
                        if not base.any():
                            continue
                        for t in TAUS:
                            vt = r["t%03d_valid" % t].astype(bool)
                            sel = base & v0 & vt
                            n = int(sel.sum())
                            if n == 0:
                                continue
                            rows.append(_cell_row(asset, rname, pname, ename,
                                                  popname, t, r, sel, n,
                                                  base & vt))
    return rows


AGG_COLUMNS = ["asset", "rung", "phase", "era", "population",
               "tau_sec", "n_paired",
               "mean_v_close_0", "mean_v_close_tau", "value_ratio",
               "value_decay", "decay_per_min", "value_delta_close_usd",
               "median_v_close_0", "median_v_close_tau", "median_ratio_of_v",
               "mean_mae_peak_0", "mean_mae_peak_tau", "mae_peak_inflation",
               "mean_mae_hold_0", "mean_mae_hold_tau", "mae_hold_inflation",
               "mean_v_peak_0", "mean_v_peak_tau", "value_decay_peakvariant",
               "value_delta_peak_usd", "close_denominator_degenerate",
               "n_valid_tau_unpaired"]

# A pooled mean below this ($) cannot carry a 1.5%-relative test: the ratio is
# noise/noise.  Measured: the walled phase-close certificate pooled over ALL
# candidates has mean ~$4 (see DECAY_REPORT.md §defect).
DEGENERATE_MEAN_USD = 100.0


def _cell_row(asset, rname, pname, ename, popname, t, r, sel, n, base_valid):
    v0 = r["t000_v_close"][sel]
    vt = r["t%03d_v_close" % t][sel]
    m0 = r["t000_mae_peak"][sel]
    mt = r["t%03d_mae_peak" % t][sel]
    h0 = r["t000_mae_hold"][sel]
    ht = r["t%03d_mae_hold" % t][sel]
    p0 = r["t000_v_peak"][sel]
    pt = r["t%03d_v_peak" % t][sel]
    mv0, mvt = M.mean(v0), M.mean(vt)
    ratio = (mvt / mv0) if (np.isfinite(mv0) and mv0 != 0) else float("nan")
    decay = 1.0 - ratio if np.isfinite(ratio) else float("nan")
    per_min = (decay / (t / 60.0)) if t > 0 and np.isfinite(decay) \
        else (0.0 if t == 0 else float("nan"))
    with np.errstate(divide="ignore", invalid="ignore"):
        rr = np.where(np.abs(v0) > 1e-9, vt / v0, np.nan)
    mm0, mmt = M.mean(m0), M.mean(mt)
    mh0, mht = M.mean(h0), M.mean(ht)
    mp0, mpt = M.mean(p0), M.mean(pt)
    return [asset, rname, pname, ename, popname, t, n,
            mv0, mvt, ratio, decay, per_min, mvt - mv0,
            M.med(v0), M.med(vt), M.med(rr),
            mm0, mmt, (mmt / mm0 - 1.0) if mm0 else float("nan"),
            mh0, mht, (mht / mh0 - 1.0) if mh0 else float("nan"),
            mp0, mpt, (1.0 - mpt / mp0) if mp0 else float("nan"),
            mpt - mp0, bool(abs(mv0) < DEGENERATE_MEAN_USD),
            int(base_valid.sum())]


def _load(asset):
    z = np.load(M.out_path("decay", "decay_cert_%s.npz" % asset),
                allow_pickle=False)
    r = {k: z[k] for k in z.files}
    z.close()
    return r


# ------------------------------------------------------------- pin rule -----
# The pin rule is evaluated on every reading §2's wording admits; the PRIMARY
# is chosen by two criteria fixed BEFORE the numbers were read: the population
# must be unselected, and the tau=0 denominator must not be degenerate.
#   name, value column, MAE column, population, note
READINGS = (
    ("PRIMARY_peak_all", "value_decay_peakvariant", "mae_peak_inflation",
     "ALL", "peak-exit certificate, all confirmations: unselected AND "
            "well-conditioned (mean v(0) ~ $1.2k, D-033's scale)"),
    ("SPEC_LITERAL_close_all", "value_decay", "mae_peak_inflation", "ALL",
     "§2's literal phase-close variant: DEGENERATE denominator (mean v(0) "
     "~ $4) — the 1.5% test is noise/noise"),
    ("close_all_maehold", "value_decay", "mae_hold_inflation", "ALL",
     "phase-close value, realised-hold MAE"),
    ("peak_all_maehold", "value_decay_peakvariant", "mae_hold_inflation",
     "ALL", "peak-exit value, realised-hold MAE"),
    ("close_1kclass", "value_decay", "mae_peak_inflation", "K1K_AT_TAU0",
     "phase-close on the $1k-class: SELECTION-BIASED (conditions on the "
     "tau=0 outcome), can only overstate decay"),
)
PRIMARY_READING = READINGS[0][0]


def pin_tau(rows, asset, rung="ALL", phase="ALL", era=None,
            value_col="value_decay", mae_col="mae_peak_inflation",
            population="ALL"):
    """§2 PRE-REGISTERED rule, applied verbatim.  Returns (tau, evidence)."""
    era = era or M.ERA_FIT
    vi = AGG_COLUMNS.index(value_col)
    mi = AGG_COLUMNS.index(mae_col)
    ti = AGG_COLUMNS.index("tau_sec")
    by_tau = {}
    for r in rows:
        if (r[0] == asset and r[1] == rung and r[2] == phase and r[3] == era
                and r[4] == population):
            by_tau[int(r[ti])] = r
    qualifying = []
    for t in TAUS:
        if t > TAU_CAP or t not in by_tau:
            continue
        r = by_tau[t]
        dec, inf = r[vi], r[mi]
        ok = (np.isfinite(dec) and dec < DECAY_MAX
              and np.isfinite(inf) and inf < MAE_INFLATION_MAX)
        qualifying.append((t, ok, dec, inf))
    passing = [q[0] for q in qualifying if q[1]]
    tau = max(passing) if passing else 0
    tau = max(tau, TAU_FLOOR)                       # §2 floor
    return tau, qualifying


# --------------------------------------------- m0 differential (tau = 60) ---
def verify_vs_m0(assets, data=None):
    """The tau=60 slice of this universe must BE the m0 roster (§8 sub-pass 1)
    and reproduce its phase-close certificates (§8 sub-pass 3), value for value.
    """
    cost_map = CA.session_cost_rt(M.M0_ROOT)
    with open(os.path.join(M.M0_ROOT, "walls.json")) as fh:
        walls = json.load(fh)["walls"]
    rows = []
    for asset in assets:
        r = data[asset] if data else _load(asset)
        m0 = CC.load_roster(asset, M.M0_ROOT)
        W = float(walls[asset]["wall_usd"])
        mine = {}
        v60 = r["t060_valid"].astype(bool)
        for i in np.nonzero(v60)[0].tolist():
            mine[(int(r["date8"][i]), int(r["conf_sec"][i]),
                  int(r["side"][i]))] = i
        theirs = {}
        for i in range(int(m0["date8"].size)):
            theirs[(int(m0["date8"][i]), int(m0["conf_sec"][i]),
                    int(m0["side"][i]))] = i
        only_mine = sorted(set(mine) - set(theirs))
        only_theirs = sorted(set(theirs) - set(mine))
        both = sorted(set(mine) & set(theirs))
        d_entry = d_val = 0
        max_dv = 0.0
        for k in both:
            i, j = mine[k], theirs[k]
            if abs(float(r["t060_entry_mid"][i])
                   - float(m0["entry_mid"][j])) > 1e-12:
                d_entry += 1
            iso = "%04d-%02d-%02d" % (k[0] // 10000, (k[0] // 100) % 100,
                                      k[0] % 100)
            cost = cost_map.get((asset, iso), float("nan"))
            if not np.isfinite(cost):
                cost = C.FEES_RT
            _pk, cl = CC.certificates(m0, j, W, cost)
            dv = abs(float(r["t060_v_close"][i]) - float(cl[0]))
            max_dv = max(max_dv, dv)
            if dv > 1e-6:
                d_val += 1
        rows.append([asset, len(mine), len(theirs), len(both), len(only_mine),
                     len(only_theirs), d_entry, d_val, max_dv,
                     "PASS" if (not only_mine and not only_theirs
                                and not d_entry and not d_val) else "FAIL"])
        M.hb("b1 m0-differential %s: %s" % (asset, rows[-1][-1]))
    M.write_tsv(M.out_path("decay", "decay_m0_differential.tsv"), SECTION,
                C.params_hash(PARAMS),
                ["asset", "n_m1_tau60", "n_m0_roster", "n_common",
                 "only_m1", "only_m0", "entry_mid_mismatches",
                 "phase_close_value_mismatches", "max_abs_value_delta",
                 "verdict"], rows,
                extra=["differential: the tau=60 slice of the §2 universe vs "
                       "the frozen m0 roster + its §8 phase-close certificates"])
    return rows


def main():
    M.verify_spec()
    workers = int(os.environ.get("M1_WORKERS", "6"))
    assets = [a for a in sys.argv[1:] if a in M.ASSET_ORDER] or list(M.ASSET_ORDER)
    data = run_scan(assets, workers)
    verify_vs_m0(assets, data)
    rows = aggregate(assets, data)
    phash = C.params_hash(PARAMS)
    M.write_tsv(M.out_path("decay", "decay_cells.tsv"), SECTION, phash,
                AGG_COLUMNS, rows,
                extra=["pairwise-complete vs tau=0; value = walled phase-close "
                       "certificate; ratio = mean(v(tau))/mean(v(0))"])
    pins = {}
    pin_rows = []
    for asset in assets:
        readings = {}
        for (name, vcol, mcol, pop, note) in READINGS:
            tau, ev = pin_tau(rows, asset, value_col=vcol, mae_col=mcol,
                              population=pop)
            readings[name] = {"tau_star": tau, "value_col": vcol,
                              "mae_col": mcol, "population": pop,
                              "note": note,
                              "per_tau": [{"tau": e[0], "passes": bool(e[1]),
                                           "value_decay": e[2],
                                           "mae_inflation": e[3]}
                                          for e in ev]}
            for e in ev:
                pin_rows.append([asset, name, pop, vcol, mcol, e[0],
                                 int(bool(e[1])), e[2], e[3], tau])
        tau_star = readings[PRIMARY_READING]["tau_star"]
        pins[asset] = {"tau_star": tau_star,
                       "primary_reading": PRIMARY_READING,
                       "readings": readings}
        M.hb("b1 pin %s: tau*=%ds (%s)" % (asset, tau_star, PRIMARY_READING))
    M.write_tsv(M.out_path("decay", "decay_pin_rule.tsv"), SECTION, phash,
                ["asset", "reading", "population", "value_col", "mae_col",
                 "tau_sec", "passes_rule", "value_decay", "mae_inflation",
                 "tau_star_of_reading"], pin_rows,
                extra=["rule: largest tau <= %d with decay < %.3f AND MAE "
                       "inflation < %.2f; floored at %ds"
                       % (TAU_CAP, DECAY_MAX, MAE_INFLATION_MAX, TAU_FLOOR),
                       "era = %s (FIT only, per the era law)" % M.ERA_FIT])
    M.write_json(M.out_path("decay", "tau_star.json"),
                 {"spec_section": SECTION, "env": M.env_receipt(PARAMS),
                  "rule": PARAMS["pin_rule"],
                  "primary_reading": PRIMARY_READING, "pins": pins})
    return 0


if __name__ == "__main__":
    sys.exit(main())
