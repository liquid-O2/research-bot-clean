#!/usr/bin/python3
"""PORT M1 Track B-5 — G2/G3 prototype generators + per-family/union census (§6).

The census machinery is the M0 one, re-run — nothing is reimplemented:
  c_c_roster._emit_candidate   path-skeleton certificates (float32 prefix maxima)
  c_c_roster.certificates      walled peak-exit / phase-close certificates
  c_c_roster.dp_schedule       one-position weighted interval scheduling
  c_d_recall.oracle_legs       0.25 x ATR14 ANCHORED oracle (CC-M0-2.1)
  c_d_recall._score_leg        capture/miss tagging
Only the ROSTER changes: G1 at tau* (§2) union G2 (level interactions, §4/§6)
union G3 (bursts, §6), deduped by (session, decision_sec, side) with the union
of family tags.

G2 comes straight out of the §4 touch log (the state machine already resolved
REJECT / BREAK / RECLAIM), so the generator and the ledger can never disagree.
G3 is computed here: 60s rolling trade RATE and |signed FLOW|, robust-z'd
against an EXACT pooled trailing-60-session same-half-hour reference built from
integer histograms.
"""
import json
import multiprocessing as mp
import os
import sys
from collections import deque

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import m1_common as M
import common as C
import census_common as X
import c_a_cost as CA
import c_c_roster as CC
import c_d_recall as CD
import b3_levels as B3

SECTION = "§6 G2/G3 generation + census"

FAMILIES = ("G1", "G2_REJECT", "G2_RECLAIM", "G3_RATE", "G3_FLOW")
FAM_BIT = {f: 1 << i for i, f in enumerate(FAMILIES)}

# --- G3 constants (§6)
G3_WINDOW = 60                  # "|signed-flow(60s)|"; the same window for rate
G3_Z_BURST = 4.0
G3_BURST_SUSTAIN = 10
G3_Z_RELEASE = 1.5
G3_HALFHOUR = 1800
G3_TRAILING_SESSIONS = 60
G3_MAD_SCALE = 1.4826
G3_RATE_SCALE_FLOOR = 0.5       # half a trade  (MAD == 0 guard)
G3_FLOW_SCALE_FLOOR = 1.0       # one contract  (MAD == 0 guard)

RETIRE_DP_ADD = 150.0           # §6 "< $150/day median to the union DP"
RETIRE_RECALL = 0.003           # §6 "< 0.3% union recall"
UNION_RECALL_GATE = 0.99        # §6 "union recall gate >= 99% @$1,000"

PARAMS = {
    "spec_section": SECTION,
    "families": list(FAMILIES),
    "dedup": "(session, decision_sec, side); family tags unioned",
    "decision_lag": "tau* per asset from §2 (m1/decay/tau_star.json)",
    "g2_source": "§4 touch log (REJECT/RECLAIM confirmation seconds)",
    "g2_side": "approach side (= away-from-level for REJECT, = reclaim "
               "direction for RECLAIM: both equal sign(mid_before - L))",
    "g3_stat": "60s rolling trade count (RATE) and |60s rolling signed size| "
               "(FLOW); DBN aggressor side B=+size, A=-size, N=0",
    "g3_z": "(x - median)/(%.4f x MAD) of the EXACT pooled trailing-%d-session "
            "same-half-hour distribution (integer histograms); scale floored at "
            "%.1f (rate) / %.1f (flow) when MAD == 0"
            % (G3_MAD_SCALE, G3_TRAILING_SESSIONS, G3_RATE_SCALE_FLOOR,
               G3_FLOW_SCALE_FLOOR),
    "g3_warmup": "no G3 candidate until the trailing reference holds the "
                 "full %d sessions (§6 says trailing-60-session; a partial "
                 "window makes median/MAD meaningless)" % G3_TRAILING_SESSIONS,
    "g3_burst": "z >= %.1f sustained >= %ds; candidate at the first second "
                "z < %.1f after the burst peak; BOTH sides emitted"
                % (G3_Z_BURST, G3_BURST_SUSTAIN, G3_Z_RELEASE),
    "certificates": "m0 §8 walled peak-exit and phase-close, wall from "
                    "m0 walls.json, session-scoped cost_rt",
    "retirement": "family RETIRED if exclusive candidates add < $%.0f/day "
                  "median to the union DP AND < %.1f%% union recall"
                  % (RETIRE_DP_ADD, RETIRE_RECALL * 100),
    "union_recall_gate": UNION_RECALL_GATE,
}


def tau_star(asset):
    with open(M.out_path("decay", "tau_star.json")) as fh:
        j = json.load(fh)
    return int(j["pins"][asset]["tau_star"])


# ==================================================================== G2 =====
def g2_from_levels(asset, trade_date):
    """(conf_sec, side, family, level_family) from the §4 touch log."""
    p = M.out_path("levels", asset, "%s.npz" % trade_date.strftime("%Y%m%d"))
    if not os.path.exists(p):
        return []
    z = np.load(p, allow_pickle=False)
    t = z["touches"]
    fam = z["level_family"]
    z.close()
    out = []
    if t.size == 0:
        return out
    for r in t:
        row = int(r[1])
        app = int(r[4])
        lf = str(fam[row]) if row < fam.size else "?"
        rej, rec = int(r[7]), int(r[9])
        if rej >= 0:
            out.append((rej, app, "G2_REJECT", lf))
        if rec >= 0:
            out.append((rec, app, "G2_RECLAIM", lf))
    return out


# ==================================================================== G3 =====
def _hist_add(h, vals):
    v, c = np.unique(vals, return_counts=True)
    for a, b in zip(v.tolist(), c.tolist()):
        h[a] = h.get(a, 0) + b


def _hist_median(h):
    if not h:
        return float("nan")
    keys = sorted(h)
    counts = np.array([h[k] for k in keys], dtype=np.int64)
    n = int(counts.sum())
    cum = np.cumsum(counts)
    pos = (n - 1) / 2.0
    lo = keys[int(np.searchsorted(cum, int(np.floor(pos)), side="right"))]
    hi = keys[int(np.searchsorted(cum, int(np.ceil(pos)), side="right"))]
    return float(lo + (hi - lo) * (pos - np.floor(pos)))


def _hist_mad(h, med):
    if not h:
        return float("nan")
    d = {}
    for k, c in h.items():
        a = abs(k - med)
        d[a] = d.get(a, 0) + c
    return _hist_median(d)


def g3_session(asset, s, ref_rate, ref_flow):
    """Bursts for one session against the pooled trailing references.

    Returns (candidates, rate_hists, flow_hists) where candidates are
    (conf_sec, side, family, sign) and the hists are this session's per-half-hour
    contributions to the trailing window.
    """
    z = np.load(s.path, allow_pickle=False)
    tsec = z["trades_sec"].astype(np.int64)
    tsz = z["trades_size"].astype(np.int64)
    tside = z["trades_side"]
    z.close()
    n = s.n
    good = (tsec >= 0) & (tsec < n) & (tsz > 0)
    tsec, tsz, tside = tsec[good], tsz[good], tside[good]
    cnt = np.zeros(n, dtype=np.int64)
    flow = np.zeros(n, dtype=np.int64)
    if tsec.size:
        np.add.at(cnt, tsec, 1)
        sgn = np.where(tside == ord("B"), 1, np.where(tside == ord("A"), -1, 0))
        np.add.at(flow, tsec, tsz * sgn)
    k = np.ones(G3_WINDOW, dtype=np.int64)
    rate60 = np.convolve(cnt, k)[:n]
    flow60 = np.abs(np.convolve(flow, k)[:n])

    o = int(s.meta["open_utc"])
    binid = ((o + np.arange(n, dtype=np.int64)) % 86400) // G3_HALFHOUR
    rate_h, flow_h = {}, {}
    for b in np.unique(binid).tolist():
        sel = binid == b
        h1, h2 = {}, {}
        _hist_add(h1, rate60[sel])
        _hist_add(h2, flow60[sel])
        rate_h[int(b)] = h1
        flow_h[int(b)] = h2

    z_rate = np.full(n, np.nan)
    z_flow = np.full(n, np.nan)
    for b in np.unique(binid).tolist():
        sel = binid == int(b)
        for (ref, arr, out, floor) in ((ref_rate, rate60, z_rate,
                                        G3_RATE_SCALE_FLOOR),
                                       (ref_flow, flow60, z_flow,
                                        G3_FLOW_SCALE_FLOOR)):
            h = ref.get(int(b))
            if not h:
                continue
            med = _hist_median(h)
            scale = max(G3_MAD_SCALE * _hist_mad(h, med), floor)
            out[sel] = (arr[sel] - med) / scale

    cands = []
    for (zz, fam) in ((z_rate, "G3_RATE"), (z_flow, "G3_FLOW")):
        hot = np.isfinite(zz) & (zz >= G3_Z_BURST)
        rl = M.run_lengths(hot)
        starts = np.nonzero(rl == G3_BURST_SUSTAIN)[0]
        for st in starts.tolist():
            b0 = st - G3_BURST_SUSTAIN + 1
            b1 = b0
            while b1 + 1 < n and hot[b1 + 1]:
                b1 += 1
            peak = b0 + int(np.argmax(zz[b0:b1 + 1]))
            tail = np.nonzero(np.isfinite(zz[peak:]) & (zz[peak:] < G3_Z_RELEASE))[0]
            if tail.size == 0:
                continue
            conf = peak + int(tail[0])
            sign = 1 if flow60[peak] >= 0 else -1
            if fam == "G3_FLOW":
                fs = int(np.sum(flow[max(0, peak - G3_WINDOW + 1):peak + 1]))
                sign = 1 if fs >= 0 else -1
            for side in (1, -1):        # §6: BOTH sides emitted (mirror)
                cands.append((conf, side, fam, sign))
    return cands, rate_h, flow_h


def _merge_hists(dq):
    out = {}
    for h in dq:
        for b, hh in h.items():
            t = out.setdefault(b, {})
            for k, v in hh.items():
                t[k] = t.get(k, 0) + v
    return out


# ======================================================= roster assembly =====
ROSTER_KEYS = CC.ROSTER_KEYS


def _asset_roster(args):
    asset, sess, tau, phase_med, cost_map, W = args
    spec = C.ASSETS[asset]
    mult = spec["mult"]
    bars = X.load_bars(asset, M.M0_ROOT)
    g1 = _load_g1(asset)
    cols = {k: [] for k in ROSTER_KEYS}
    f_t, f_v, a_t, a_v = [], [], [], []
    fam_mask, lvl_mask, g3_sign, rung_mask = [], [], [], []
    per_session = []
    dq_rate, dq_flow = deque(maxlen=G3_TRAILING_SESSIONS), \
        deque(maxlen=G3_TRAILING_SESSIONS)
    lvl_fams = list(B3.FAMILIES)
    for trade_date, path in sess:
        bar = bars.get(trade_date)
        atr = bar["ATR14_prev_usd"] if bar else float("nan")
        s = X.load_session(asset, trade_date, path)
        d8 = M.d8(trade_date)
        if s.vt.size < 2 or not np.isfinite(atr):
            continue
        ready = len(dq_rate) >= G3_TRAILING_SESSIONS
        ref_rate = _merge_hists(dq_rate) if ready else {}
        ref_flow = _merge_hists(dq_flow) if ready else {}
        g3c, rh, fh = g3_session(asset, s, ref_rate, ref_flow)
        dq_rate.append(rh)
        dq_flow.append(fh)

        merged = {}
        for (conf, side, rmask) in g1.get(d8, ()):
            k = (conf, side)
            e = merged.setdefault(k, [0, 0, 0, 0])
            e[0] |= FAM_BIT["G1"]
            e[3] |= rmask
        for (conf, side, fam, lf) in g2_from_levels(asset, trade_date):
            k = (conf, side)
            e = merged.setdefault(k, [0, 0, 0, 0])
            e[0] |= FAM_BIT[fam]
            if lf in lvl_fams:
                e[1] |= 1 << lvl_fams.index(lf)
        for (conf, side, fam, sign) in g3c:
            k = (conf, side)
            e = merged.setdefault(k, [0, 0, 0, 0])
            e[0] |= FAM_BIT[fam]
            e[2] |= (1 if sign > 0 else 2)

        cost_rt = cost_map.get((asset, trade_date.isoformat()), float("nan"))
        if not np.isfinite(cost_rt):
            cost_rt = C.FEES_RT
        n_cand = n_skip_close = n_skip_state = 0
        by_conf = {}
        for (conf, side) in sorted(merged):
            dec = conf + tau
            if dec >= s.n:
                n_skip_close += 1
                continue
            if s.state[dec] != C.ST_TWO_SIDED:
                n_skip_state += 1
                continue
            key = (dec, side)
            prev = by_conf.get(key)
            e = merged[(conf, side)]
            if prev is None:
                by_conf[key] = [conf, e[0], e[1], e[2], e[3]]
            else:
                prev[1] |= e[0]
                prev[2] |= e[1]
                prev[3] |= e[2]
                prev[4] |= e[3]
        for (dec, side) in sorted(by_conf):
            conf, fm, lm, gs, rm = by_conf[(dec, side)]
            n_cand += 1
            CC._emit_candidate(cols, f_t, f_v, a_t, a_v, s, trade_date, asset,
                               mult, side, rm, conf, dec, atr)
            fam_mask.append(fm)
            lvl_mask.append(lm)
            g3_sign.append(gs)
            rung_mask.append(rm)
        per_session.append([asset, trade_date.isoformat(), trade_date.year,
                            n_cand, n_skip_close, n_skip_state,
                            len(g1.get(d8, ())), len(g3c), cost_rt])
    arrays = {}
    dtypes = {"date8": np.int32, "side": np.int8, "rung_mask": np.uint8,
              "conf_sec": np.int32, "dec_sec": np.int32, "phase_conf": np.int8,
              "phase_dec": np.int8, "mfe_argmax_sec": np.int32,
              "phase_close_sec": np.int32, "sess_close_sec": np.int32,
              "iid": np.int64, "f_off": np.int64, "f_len": np.int64,
              "a_off": np.int64, "a_len": np.int64}
    for k in ROSTER_KEYS:
        arrays[k] = np.array(cols[k], dtype=dtypes.get(k, np.float64))
    arrays["skel_f_t"] = np.array(f_t, dtype=np.int32)
    arrays["skel_f_v"] = np.array(f_v, dtype=np.float32)
    arrays["skel_a_t"] = np.array(a_t, dtype=np.int32)
    arrays["skel_a_v"] = np.array(a_v, dtype=np.float32)
    arrays["fam_mask"] = np.array(fam_mask, dtype=np.uint8)
    arrays["level_fam_mask"] = np.array(lvl_mask, dtype=np.uint16)
    arrays["g3_sign_mask"] = np.array(g3_sign, dtype=np.uint8)
    arrays["skips"] = np.zeros((0, 6), np.int64)
    C.savez_det(M.out_path("generation", "union_roster_%s.npz" % asset),
                **arrays)
    M.hb("b5 roster %s: %d union candidates (tau*=%ds)"
         % (asset, arrays["date8"].size, tau))
    return asset, per_session


def _load_g1(asset):
    z = np.load(M.out_path("decay", "g1_conf_%s.npz" % asset),
                allow_pickle=False)
    d8 = z["date8"]
    cs = z["conf_sec"]
    sd = z["side"]
    rm = z["rung_mask"]
    z.close()
    out = {}
    for i in range(d8.size):
        out.setdefault(int(d8[i]), []).append((int(cs[i]), int(sd[i]),
                                               int(rm[i])))
    return out


# ======================================================== census (§6) ========
def census(assets, out_rows):
    with open(os.path.join(M.M0_ROOT, "walls.json")) as fh:
        walls = json.load(fh)["walls"]
    cost_map = CA.session_cost_rt(M.M0_ROOT)
    sess_rows, fam_rows, excl_rows = [], [], []
    for asset in assets:
        z = np.load(M.out_path("generation", "union_roster_%s.npz" % asset),
                    allow_pickle=False)
        r = {k: z[k] for k in z.files}
        z.close()
        W = float(walls[asset]["wall_usd"])
        fm = r["fam_mask"]
        d8 = r["date8"]
        by_date = {}
        for i in range(int(d8.size)):
            by_date.setdefault(int(d8[i]), []).append(i)
        fam_acc = {f: {"n": 0, "vals": [], "pos": 0} for f in FAMILIES}
        fam_acc["UNION"] = {"n": 0, "vals": [], "pos": 0}
        excl_acc = {f: [] for f in FAMILIES}
        for d in sorted(by_date):
            iso = "%04d-%02d-%02d" % (d // 10000, (d // 100) % 100, d % 100)
            cost = cost_map.get((asset, iso), float("nan"))
            if not np.isfinite(cost):
                cost = C.FEES_RT
            idx = by_date[d]
            items, vals = [], {}
            for i in idx:
                _pk, cl = CC.certificates(r, i, W, cost)
                vals[i] = cl[0]
                items.append((cl[1], cl[2], cl[0], int(r["dec_sec"][i]),
                              int(r["iid"][i]), i))
            tot_union, sel_union = CC.dp_schedule(items)
            fam_acc["UNION"]["n"] += len(idx)
            fam_acc["UNION"]["vals"].extend(vals[i] for i in idx)
            fam_acc["UNION"]["pos"] += sum(1 for i in idx if vals[i] > 0)
            row = [asset, iso, d // 10000, len(idx), tot_union, len(sel_union)]
            for f in FAMILIES:
                bit = FAM_BIT[f]
                fidx = [i for i in idx if fm[i] & bit]
                fitems = [it for it in items if it[5] in set(fidx)]
                ftot, fsel = CC.dp_schedule(fitems)
                fam_acc[f]["n"] += len(fidx)
                fam_acc[f]["vals"].extend(vals[i] for i in fidx)
                fam_acc[f]["pos"] += sum(1 for i in fidx if vals[i] > 0)
                exc = set(i for i in idx if int(fm[i]) == bit)
                ritems = [it for it in items if it[5] not in exc]
                rtot, _ = CC.dp_schedule(ritems)
                excl_acc[f].append((d // 10000, tot_union - rtot, len(exc)))
                row.extend([len(fidx), ftot, len(fsel), len(exc)])
            sess_rows.append(row)
        for f in list(FAMILIES) + ["UNION"]:
            a = fam_acc[f]
            fam_rows.append([asset, f, a["n"], a["pos"],
                             M.mean(a["vals"]), M.med(a["vals"]),
                             (a["pos"] / a["n"]) if a["n"] else float("nan"),
                             M.mean([v for v in a["vals"] if v > 0])])
        for f in FAMILIES:
            for era in (M.ERA_FIT, M.ERA_GATE, M.ERA_ALL):
                sel = [x for x in excl_acc[f]
                       if (era == M.ERA_ALL
                           or (era == M.ERA_FIT and M.is_fit(x[0]))
                           or (era == M.ERA_GATE and x[0] == 2025))]
                if not sel:
                    continue
                excl_rows.append([asset, f, era, len(sel),
                                  M.med([x[1] for x in sel]),
                                  M.mean([x[1] for x in sel]),
                                  M.med([x[2] for x in sel]),
                                  sum(x[2] for x in sel)])
        M.hb("b5 census %s: done" % asset)
    return sess_rows, fam_rows, excl_rows


# ======================================================== recall (§9/§6) ====
def _recall_task(args):
    asset, sess, phase_med, roster_by_date, drops = args
    mult = C.ASSETS[asset]["mult"]
    tick_px = C.ASSETS[asset]["tick_px"]
    bars = X.load_bars(asset, M.M0_ROOT)
    rows = []
    for trade_date, path in sess:
        bar = bars.get(trade_date)
        atr = bar["ATR14_prev_usd"] if bar else float("nan")
        if not np.isfinite(atr):
            continue
        s = X.load_session(asset, trade_date, path)
        if s.vt.size < 2:
            continue
        thr_px = X.round_half_up(X.ORACLE_RUNG * atr / mult, tick_px)
        legs = CD.oracle_legs(s.vt.tolist(), s.vm.tolist(), thr_px, mult,
                              "ANCHORED")
        legs = [lg for lg in legs if lg[5] >= X.ORACLE_LEG_MIN and lg[4] != 0]
        legs.sort(key=lambda lg: (-lg[5], lg[0], lg[2]))
        legs = legs[:X.ORACLE_TOP_K]
        legs.sort(key=lambda lg: (lg[0], lg[2]))
        d8 = M.d8(trade_date)
        allc = roster_by_date.get(d8, [])
        for drop in drops:
            cands = allc if drop is None else [c for c in allc
                                               if c["excl"] != drop]
            for lg in legs:
                rows.append([drop or "NONE"]
                            + CD._score_leg(asset, trade_date, "ANCHORED", lg,
                                            cands, [], mult, phase_med, atr,
                                            thr_px))
    return rows


def recall(assets, workers, drop_by_family=True):
    phase_med = CA.phase_median_spreads(M.M0_ROOT)
    out = []
    for asset in assets:
        z = np.load(M.out_path("generation", "union_roster_%s.npz" % asset),
                    allow_pickle=False)
        r = {k: z[k] for k in z.files}
        z.close()
        fm = r["fam_mask"]
        by_date = {}
        for i in range(int(r["date8"].size)):
            excl = ""
            for f in FAMILIES:
                if int(fm[i]) == FAM_BIT[f]:
                    excl = f
            by_date.setdefault(int(r["date8"][i]), []).append({
                "dec_sec": int(r["dec_sec"][i]), "side": int(r["side"][i]),
                "entry_mid": float(r["entry_mid"][i]),
                "spread": float(r["spread_at_decision"][i]),
                "phase_dec": int(r["phase_dec"][i]), "excl": excl})
        sess = X.session_paths(asset, M.M0_ROOT)
        variants = [None] + (list(FAMILIES) if drop_by_family else [])
        chunks = [sess[i::workers] for i in range(workers)]
        tasks = [(asset, ch, phase_med, by_date, variants) for ch in chunks
                 if ch]
        if workers <= 1 or len(tasks) <= 1:
            res = [_recall_task(t) for t in tasks]
        else:
            with mp.Pool(min(workers, len(tasks))) as pool:
                res = list(pool.map(_recall_task, tasks, chunksize=1))
        legs = []
        for x in res:
            legs.extend(x)
        for drop in variants:
            dn = drop or "NONE"
            dl = [lg for lg in legs if lg[0] == dn]
            for era in (M.ERA_FIT, M.ERA_GATE, M.ERA_ALL):
                sel = [lg for lg in dl
                       if (era == M.ERA_ALL
                           or (era == M.ERA_FIT and M.is_fit(int(lg[3])))
                           or (era == M.ERA_GATE and int(lg[3]) == 2025))]
                if not sel:
                    continue
                n = len(sel)
                out.append([asset, dn, era, n,
                            sum(int(l[15]) for l in sel) / n,
                            sum(int(l[16]) for l in sel) / n,
                            sum(int(l[17]) for l in sel) / n,
                            sum(int(l[18]) for l in sel) / n,
                            "PASS" if (drop is None and
                                       sum(int(l[16]) for l in sel) / n
                                       >= UNION_RECALL_GATE) else ""])
        M.hb("b5 recall %s: %d leg-scorings over %d variants"
             % (asset, len(legs), len(variants)))
    return out


# ================================================================== main =====
def main():
    M.verify_spec()
    workers = int(os.environ.get("M1_WORKERS", "6"))
    assets = [a for a in sys.argv[1:] if a in M.ASSET_ORDER] or list(M.ASSET_ORDER)
    phash = C.params_hash(PARAMS)
    phase_med = CA.phase_median_spreads(M.M0_ROOT)
    cost_map = CA.session_cost_rt(M.M0_ROOT)
    with open(os.path.join(M.M0_ROOT, "walls.json")) as fh:
        walls = json.load(fh)["walls"]

    tasks = []
    for asset in assets:
        tasks.append((asset, X.session_paths(asset, M.M0_ROOT),
                      tau_star(asset), phase_med, cost_map,
                      float(walls[asset]["wall_usd"])))
    if len(tasks) <= 1:
        res = [_asset_roster(t) for t in tasks]
    else:
        with mp.Pool(min(3, len(tasks))) as pool:
            res = list(pool.map(_asset_roster, tasks, chunksize=1))
    build_rows = []
    for (_a, pr) in res:
        build_rows.extend(pr)
    M.write_tsv(M.out_path("generation", "roster_build.tsv"), SECTION, phash,
                ["asset", "trade_date", "year", "n_union_candidates",
                 "n_skip_past_close", "n_skip_not_two_sided",
                 "n_g1_confirmations", "n_g3_raw", "cost_rt_session"],
                build_rows)

    sess_rows, fam_rows, excl_rows = census(assets, build_rows)
    cols = ["asset", "trade_date", "year", "n_union", "union_dp_close_usd",
            "n_seated_union"]
    for f in FAMILIES:
        cols += ["n_%s" % f, "dp_%s_usd" % f, "n_seated_%s" % f,
                 "n_exclusive_%s" % f]
    M.write_tsv(M.out_path("generation", "census_union_seatable.tsv"), SECTION,
                phash, cols, sess_rows,
                extra=["phase-close walled DP per session; per-family DP is the "
                       "DP over that family's candidates alone"])
    M.write_tsv(M.out_path("generation", "census_family_value.tsv"), SECTION,
                phash, ["asset", "family", "n_candidates", "n_positive",
                        "mean_cert_usd", "median_cert_usd", "positive_frac",
                        "mean_positive_cert_usd"], fam_rows)
    M.write_tsv(M.out_path("generation", "census_family_exclusive.tsv"),
                SECTION, phash,
                ["asset", "family", "era", "n_sessions",
                 "exclusive_dp_add_median_usd", "exclusive_dp_add_mean_usd",
                 "n_exclusive_median", "n_exclusive_total"], excl_rows,
                extra=["exclusive DP add = union DP - DP without that family's "
                       "EXCLUSIVE candidates (§6 retirement rule input)"])

    rec = recall(assets, workers)
    M.write_tsv(M.out_path("generation", "census_union_recall.tsv"), SECTION,
                phash, ["asset", "dropped_exclusive_family", "era", "n_legs",
                        "recall_900", "recall_1000", "recall_1100",
                        "recall_1000_screened", "gate_ge_99"], rec,
                extra=["ANCHORED oracle (CC-M0-2.1); union gate = recall@$1,000 "
                       ">= %.2f" % UNION_RECALL_GATE])
    return 0


if __name__ == "__main__":
    sys.exit(main())
