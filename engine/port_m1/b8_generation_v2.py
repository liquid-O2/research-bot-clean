#!/usr/bin/python3
"""PORT M1.B S1 — generation prototype v2 (CC-M1-3) + the re-census.

THIS FILE IS THE FROZEN DIFFERENTIAL ORACLE for the C++ generation lane (S2):
every candidate it emits, and every stored field, is what `qr_gen` must
reproduce candidate-exact.

WHAT CHANGES vs the M1.A prototype (b5_generation.py), all of it CC-M1-3:
  4b  G1-FINE       a fourth ZigZag rung 0.05 x ATR14($) under the SAME floors
                    (max(4 ticks, 2 x phase-median spread)); tagged separately
                    so its marginal contribution is measurable.
  4b  G1-FAST-OPEN  a confirmation landing in the first 300s after a phase open
                    ADDITIONALLY emits a candidate at decision delay 15s (all
                    rungs, incl. FINE), under its own family tag.
  5   G2-RECLAIM    completion bound: the reclaim confirmation must land within
                    30 min of the break (defect D4).
  2   RETIRED       G3-RATE and G3-FLOW are not generated at all.
  3   RETIRED       level sources FVOL_LADDER_RS, PRIOR_WEEK, PROFILE, DEV_POC,
                    ROUND: a touch on one of them no longer makes a G2
                    candidate.  KEPT six only.
  1   tau* = 120s, all assets.
  4a  RECALL SPLIT  oracle legs whose FULL SPAN is < 150s are STRUCTURAL_GAP
                    (no confirm-then-delay design can enter them); the >=99%
                    gate applies to the CATCHABLE legs, both numbers reported.
  D-053 the level ledger is read from m1/levels_v2/ (VWAP line + 2.0/2.5 sigma).

Everything else is the M0 census machinery re-run, unchanged and unrewritten:
c_c_roster._emit_candidate / certificates / dp_schedule, c_d_recall.oracle_legs
and _score_leg, b1_decay.session_confirmations (the m0 zigzag at a longer rung
ladder), b3_levels' touch log.

READING PINNED (reported as a spec ambiguity, S1 report §defects): G1-FAST-OPEN
is ADDITIVE - the 15s candidate is emitted BESIDE the 120s one, never instead of
it ("separate family tag", CC-M1-3.4b).  PORT_M1B_SPEC §1 S2's shorthand
"tau*=120s (15s in open windows)" would also admit a replacement reading; the
additive one is the superset, so it is the safe oracle for a recall gate, and
the drop-exclusive census row below measures exactly what it adds.  The 15s
delay applies to G1 rungs only (CC-M1-3.4b says "on all rungs"); G2 keeps tau*.

Run: lab/run.sh port-m1b-s1 -- /usr/bin/python3 engine/port_m1/b8_generation_v2.py
"""
import bisect
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
import c_d_recall as CD
import b1_decay as B1

SECTION = "S1 generation v2 (CC-M1-3)"
OUT_DIR = "generation_v2"
LEVELS_DIR = "levels_v2"

# --- CC-M1-3.1 / 3.4b generation constants
TAU_STAR = 120                   # CC-M1-3.1, all assets
RUNGS_V2 = (0.05, 0.075, 0.11, 0.15)     # bit 0 = G1-FINE, then the m0 ladder
FINE_BIT = 1
COARSE_MASK = 0b1110
FAST_OPEN_WINDOW = 300           # "first 300s after each phase open"
FAST_OPEN_DELAY = 15
RECLAIM_BOUND = 1800             # CC-M1-3.5, break -> reclaim confirmation

# --- CC-M1-3.3 level sources
KEPT_LEVEL_FAMILIES = ("FVOL_LADDER", "FVOL_BAND", "NDAY", "PRIOR_DAY",
                       "PHASE_HL", "VWAP")
RETIRED_LEVEL_FAMILIES = ("FVOL_LADDER_RS", "PRIOR_WEEK", "PROFILE",
                          "DEV_POC", "ROUND")

FAMILIES = ("G1", "G1_FINE", "G1_FAST_OPEN", "G2_REJECT", "G2_RECLAIM")
NEW_FAMILIES = ("G1_FINE", "G1_FAST_OPEN")
FAM_BIT = {f: 1 << i for i, f in enumerate(FAMILIES)}

# --- CC-M1-3.4a recall split + gate
STRUCTURAL_SPAN = 150            # leg FULL span < 150s = STRUCTURAL_GAP
RECALL_GATE = 0.99               # on CATCHABLE legs, per asset, @$1,000

PARAMS = {
    "spec_section": SECTION,
    "families": list(FAMILIES),
    "tau_star_sec": TAU_STAR,
    "rungs": list(RUNGS_V2),
    "rung_floors": "max(%d x tick_$, %d x phase-median spread_$) - unchanged"
                   % (X.RUNG_FLOOR_TICKS, X.RUNG_FLOOR_SPREAD_MULT),
    "fast_open": "confirmation_sec in [phase_open, phase_open + %ds) -> an "
                 "ADDITIONAL candidate at delay %ds, own family tag; phase "
                 "opens = session second 0 and every phase-tag change"
                 % (FAST_OPEN_WINDOW, FAST_OPEN_DELAY),
    "reclaim_bound_sec": RECLAIM_BOUND,
    "kept_level_families": list(KEPT_LEVEL_FAMILIES),
    "retired_level_families": list(RETIRED_LEVEL_FAMILIES),
    "retired_families": ["G3_RATE", "G3_FLOW"],
    "levels_source": "m1/%s (D-053 VWAP bands)" % LEVELS_DIR,
    "dedup": "(session, decision_sec, side); family/rung/level tags unioned; "
             "confirmation_sec = the earliest confirmation mapping to it",
    "certificates": "m0 §8 walled peak-exit and phase-close, wall from "
                    "m0 walls.json, session-scoped cost_rt",
    "recall_split": "oracle leg full span < %ds = STRUCTURAL_GAP; the gate "
                    "applies to CATCHABLE legs" % STRUCTURAL_SPAN,
    "recall_gate": RECALL_GATE,
}


# =========================================== the FAST-OPEN window (tested) ===
def phase_open_secs(s):
    """Session-second of every phase open: second 0, then each phase change."""
    ops = [0]
    ch = np.nonzero(s.phase_tag[1:] != s.phase_tag[:-1])[0] + 1
    ops.extend(int(x) for x in ch.tolist())
    return ops


def in_fast_open(conf_sec, opens):
    """True iff conf_sec is in [open, open + 300) of the phase open at or
    before it.  Half-open: a confirmation exactly 300s after the open is
    OUTSIDE ("the first 300s after each phase open")."""
    i = bisect.bisect_right(opens, conf_sec) - 1
    if i < 0:
        return False
    return (conf_sec - opens[i]) < FAST_OPEN_WINDOW


def g1_emissions(confs, opens):
    """CC-M1-3.4b emission for one session.

    confs: [(conf_sec, side, rung_mask)] over RUNGS_V2.
    Returns [(dec_sec, side, fam_bits, rung_mask, conf_sec)].
    """
    out = []
    for (conf, side, mask) in confs:
        fam = 0
        if mask & COARSE_MASK:
            fam |= FAM_BIT["G1"]
        if mask & FINE_BIT:
            fam |= FAM_BIT["G1_FINE"]
        if fam:
            out.append((conf + TAU_STAR, side, fam, mask, conf))
        if in_fast_open(conf, opens):
            out.append((conf + FAST_OPEN_DELAY, side,
                        FAM_BIT["G1_FAST_OPEN"], mask, conf))
    return out


# ============================================ G2 from the §4 touch log =======
def reclaim_within_bound(break_sec, reclaim_sec):
    """CC-M1-3.5: reclaim confirmation within 30 min OF THE BREAK.

    Applied to the ledger's first-reclaim record, which is exactly equivalent
    to bounding the ledger's own search: classify_touch returns the EARLIEST
    reclaim confirmation, so if that one is out of bounds no earlier one exists.
    """
    if reclaim_sec < 0 or break_sec < 0:
        return False
    return (reclaim_sec - break_sec) <= RECLAIM_BOUND


def g2_from_levels(asset, trade_date):
    """(conf_sec, approach_side, family, level_family) from m1/levels_v2."""
    p = M.out_path(LEVELS_DIR, asset,
                   "%s.npz" % trade_date.strftime("%Y%m%d"))
    if not os.path.exists(p):
        return [], 0, 0
    z = np.load(p, allow_pickle=False)
    t = z["touches"]
    fam = z["level_family"]
    z.close()
    out = []
    n_drop_fam = n_drop_bound = 0
    if t.size == 0:
        return out, 0, 0
    for r in t:
        row = int(r[1])
        app = int(r[4])
        lf = str(fam[row]) if row < fam.size else "?"
        rej, brk, rec = int(r[7]), int(r[8]), int(r[9])
        if lf not in KEPT_LEVEL_FAMILIES:
            n_drop_fam += (1 if rej >= 0 else 0) + (1 if rec >= 0 else 0)
            continue
        if rej >= 0:
            out.append((rej, app, "G2_REJECT", lf))
        if rec >= 0:
            if reclaim_within_bound(brk, rec):
                out.append((rec, app, "G2_RECLAIM", lf))
            else:
                n_drop_bound += 1
    return out, n_drop_fam, n_drop_bound


# ======================================================= roster assembly =====
ROSTER_KEYS = CC.ROSTER_KEYS


def load_g1_reference(asset):
    """The M1.A G1 confirmation universe (m1/decay/g1_conf_*.npz, the m0 3-rung
    ladder), as {date8: {(conf_sec, side, rung_mask)}}.

    LADDER DIFFERENTIAL: prepending the FINE rung must not perturb the m0
    rungs.  v2 bit i+1 is m0 bit i, so the coarse-restricted v2 confirmation
    set shifted right by one must equal this set exactly, session for session.
    """
    z = np.load(M.out_path("decay", "g1_conf_%s.npz" % asset),
                allow_pickle=False)
    d8, cs, sd, rm = z["date8"], z["conf_sec"], z["side"], z["rung_mask"]
    z.close()
    out = {}
    for i in range(int(d8.size)):
        out.setdefault(int(d8[i]), set()).add((int(cs[i]), int(sd[i]),
                                               int(rm[i])))
    return out


def _asset_roster(args):
    asset, sess, phase_med, cost_map = args
    spec = C.ASSETS[asset]
    mult = spec["mult"]
    bars = X.load_bars(asset, M.M0_ROOT)
    g1_ref = load_g1_reference(asset)
    cols = {k: [] for k in ROSTER_KEYS}
    f_t, f_v, a_t, a_v = [], [], [], []
    fam_mask, lvl_mask, rung_mask = [], [], []
    per_session = []
    lvl_fams = list(KEPT_LEVEL_FAMILIES)
    for trade_date, path in sess:
        bar = bars.get(trade_date)
        atr = bar["ATR14_prev_usd"] if bar else float("nan")
        s = X.load_session(asset, trade_date, path)
        if s.vt.size < 2 or not np.isfinite(atr):
            continue
        confs = B1.session_confirmations(s, asset, atr, phase_med, trade_date,
                                         RUNGS_V2)
        coarse = set((c, sd, m >> 1) for (c, sd, m) in confs
                     if m & COARSE_MASK)
        ref = g1_ref.get(M.d8(trade_date), set())
        n_only_v2, n_only_m1a = len(coarse - ref), len(ref - coarse)
        opens = phase_open_secs(s)
        g2, n_dropf, n_dropb = g2_from_levels(asset, trade_date)

        merged = {}
        for (dec, side, fam, rmask, conf) in g1_emissions(confs, opens):
            e = merged.setdefault((dec, side), [0, 0, 0, conf])
            e[0] |= fam
            e[2] |= rmask
            e[3] = min(e[3], conf)
        for (conf, side, fam, lf) in g2:
            dec = conf + TAU_STAR
            e = merged.setdefault((dec, side), [0, 0, 0, conf])
            e[0] |= FAM_BIT[fam]
            e[1] |= 1 << lvl_fams.index(lf)
            e[3] = min(e[3], conf)

        cost_rt = cost_map.get((asset, trade_date.isoformat()), float("nan"))
        if not np.isfinite(cost_rt):
            cost_rt = C.FEES_RT
        n_cand = n_skip_close = n_skip_state = n_fast = 0
        for (dec, side) in sorted(merged):
            fm, lm, rm, conf = merged[(dec, side)]
            if dec >= s.n:
                n_skip_close += 1
                continue
            if s.state[dec] != C.ST_TWO_SIDED:
                n_skip_state += 1
                continue
            n_cand += 1
            n_fast += 1 if (fm & FAM_BIT["G1_FAST_OPEN"]) else 0
            CC._emit_candidate(cols, f_t, f_v, a_t, a_v, s, trade_date, asset,
                               mult, side, rm, conf, dec, atr)
            fam_mask.append(fm)
            lvl_mask.append(lm)
            rung_mask.append(rm)
        per_session.append([asset, trade_date.isoformat(), trade_date.year,
                            n_cand, n_skip_close, n_skip_state, len(confs),
                            len(g2), n_fast, n_dropf, n_dropb, len(opens),
                            n_only_v2, n_only_m1a, cost_rt])
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
    arrays["skips"] = np.zeros((0, 6), np.int64)
    C.savez_det(M.out_path(OUT_DIR, "union_roster_%s.npz" % asset), **arrays)
    M.hb("s1v2 roster %s: %d union candidates (tau*=%ds, %d rungs)"
         % (asset, arrays["date8"].size, TAU_STAR, len(RUNGS_V2)))
    return asset, per_session


# ============================================================== census =======
def census(assets):
    with open(os.path.join(M.M0_ROOT, "walls.json")) as fh:
        walls = json.load(fh)["walls"]
    cost_map = CA.session_cost_rt(M.M0_ROOT)
    sess_rows, fam_rows, excl_rows = [], [], []
    for asset in assets:
        z = np.load(M.out_path(OUT_DIR, "union_roster_%s.npz" % asset),
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
                fidx = set(i for i in idx if fm[i] & bit)
                fitems = [it for it in items if it[5] in fidx]
                ftot, fsel = CC.dp_schedule(fitems)
                fam_acc[f]["n"] += len(fidx)
                fam_acc[f]["vals"].extend(vals[i] for i in sorted(fidx))
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
        M.hb("s1v2 census %s: done" % asset)
    return sess_rows, fam_rows, excl_rows


# =============================================== recall + the CC-M1-3.4a split
def is_structural(span_sec):
    """CC-M1-3.4a: a leg whose FULL SPAN is under 150s is a STRUCTURAL GAP."""
    return span_sec < STRUCTURAL_SPAN


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
                span = int(lg[2]) - int(lg[0])
                rows.append([drop or "NONE", span,
                             1 if is_structural(span) else 0]
                            + CD._score_leg(asset, trade_date, "ANCHORED", lg,
                                            cands, [], mult, phase_med, atr,
                                            thr_px))
    return rows


LEG_COLUMNS = (["dropped_exclusive_family", "leg_span_sec", "structural_gap"]
               + CD.LEG_COLUMNS)
# offsets into a leg row
LI = {c: i for i, c in enumerate(LEG_COLUMNS)}


def _recall_rollup(legs, drop):
    """(era, catchable/raw recall rows) for one drop variant."""
    out = []
    dl = [lg for lg in legs if lg[0] == drop]
    for era in (M.ERA_FIT, M.ERA_GATE, M.ERA_ALL):
        sel = [lg for lg in dl
               if (era == M.ERA_ALL
                   or (era == M.ERA_FIT and M.is_fit(int(lg[LI["year"]])))
                   or (era == M.ERA_GATE and int(lg[LI["year"]]) == 2025))]
        if not sel:
            continue
        cat = [lg for lg in sel if not int(lg[LI["structural_gap"]])]
        stru = [lg for lg in sel if int(lg[LI["structural_gap"]])]

        def rate(rows_, col):
            return (sum(int(l[LI[col]]) for l in rows_) / len(rows_)) \
                if rows_ else float("nan")
        r_cat = rate(cat, "captured_1000")
        out.append([drop, era, len(sel), len(cat), len(stru),
                    rate(cat, "captured_900"), r_cat,
                    rate(cat, "captured_1100"),
                    rate(cat, "captured_1000_screened"),
                    rate(sel, "captured_900"), rate(sel, "captured_1000"),
                    rate(sel, "captured_1100"),
                    rate(sel, "captured_1000_screened"),
                    rate(stru, "captured_1000") if stru else float("nan"),
                    sum(int(l[LI["captured_1000"]]) for l in stru),
                    "PASS" if (drop == "NONE" and cat and r_cat >= RECALL_GATE)
                    else ("FAIL" if drop == "NONE" else "")])
    return out


def recall(assets, workers):
    phase_med = CA.phase_median_spreads(M.M0_ROOT)
    roll, all_legs = [], []
    for asset in assets:
        z = np.load(M.out_path(OUT_DIR, "union_roster_%s.npz" % asset),
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
        variants = [None] + list(FAMILIES)
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
        legs.sort(key=lambda l: (l[0], l[LI["trade_date"]],
                                 int(l[LI["leg_start_sec"]]),
                                 int(l[LI["leg_end_sec"]])))
        for drop in ["NONE"] + list(FAMILIES):
            roll.extend([[asset] + row for row in _recall_rollup(legs, drop)])
        all_legs.extend(lg for lg in legs if lg[0] == "NONE")
        M.hb("s1v2 recall %s: %d leg-scorings over %d variants"
             % (asset, len(legs), len(variants)))
    return roll, all_legs


# ============================================================= marginals =====
def marginals(fam_rows, excl_rows, roll):
    """Per family: recall pp vs the union, conditional value, DP delta."""
    base = {}
    for row in roll:
        if row[1] == "NONE":
            base[(row[0], row[2])] = row
    val = {(r[0], r[1]): r for r in fam_rows}
    dp = {(r[0], r[1], r[2]): r for r in excl_rows}
    out = []
    for row in roll:
        asset, drop, era = row[0], row[1], row[2]
        if drop == "NONE":
            continue
        b = base.get((asset, era))
        if b is None:
            continue
        v = val.get((asset, drop))
        d = dp.get((asset, drop, era))
        out.append([asset, drop, era,
                    (v[2] if v else None), (v[3] if v else None),
                    (v[7] if v else None), (v[4] if v else None),
                    (d[7] if d else None), (d[4] if d else None),
                    (d[5] if d else None),
                    b[7], row[7], 100.0 * (b[7] - row[7]),
                    b[11], row[11], 100.0 * (b[11] - row[11])])
    return out


# ================================================================== main =====
def main():
    M.verify_spec_m1b()
    workers = int(os.environ.get("M1_WORKERS", "6"))
    assets = [a for a in sys.argv[1:] if a in M.ASSET_ORDER] or \
        list(M.ASSET_ORDER)
    phash = C.params_hash(PARAMS)
    phase_med = CA.phase_median_spreads(M.M0_ROOT)
    cost_map = CA.session_cost_rt(M.M0_ROOT)

    tasks = [(a, X.session_paths(a, M.M0_ROOT), phase_med, cost_map)
             for a in assets]
    if len(tasks) <= 1:
        res = [_asset_roster(t) for t in tasks]
    else:
        with mp.Pool(min(3, len(tasks))) as pool:
            res = list(pool.map(_asset_roster, tasks, chunksize=1))
    build_rows = []
    for (_a, pr) in res:
        build_rows.extend(pr)
    build_rows.sort(key=lambda r: (r[0], r[1]))
    M.write_tsv(M.out_path(OUT_DIR, "roster_build.tsv"), SECTION, phash,
                ["asset", "trade_date", "year", "n_union_candidates",
                 "n_skip_past_close", "n_skip_not_two_sided",
                 "n_g1_confirmations", "n_g2_events", "n_fast_open_candidates",
                 "n_g2_dropped_retired_level", "n_g2_dropped_reclaim_bound",
                 "n_phase_opens", "n_coarse_conf_only_v2",
                 "n_coarse_conf_only_m1a", "cost_rt_session"], build_rows,
                spec="PORT_M1B",
                extra=["n_g1_confirmations counts confirmations over the "
                       "4-rung ladder (G1-FINE included)",
                       "LADDER DIFFERENTIAL: n_coarse_conf_only_* must be 0 "
                       "everywhere - adding the FINE rung may not perturb the "
                       "m0 3-rung confirmation set"])
    n_drift = sum(r[12] + r[13] for r in build_rows)
    M.hb("s1v2 ladder differential: %d coarse-confirmation drifts vs M1.A"
         % n_drift)
    if n_drift:
        raise RuntimeError("G1 ladder differential FAILED: %d drifted "
                           "confirmations (see roster_build.tsv)" % n_drift)

    sess_rows, fam_rows, excl_rows = census(assets)
    cols = ["asset", "trade_date", "year", "n_union", "union_dp_close_usd",
            "n_seated_union"]
    for f in FAMILIES:
        cols += ["n_%s" % f, "dp_%s_usd" % f, "n_seated_%s" % f,
                 "n_exclusive_%s" % f]
    M.write_tsv(M.out_path(OUT_DIR, "census_union_seatable.tsv"), SECTION,
                phash, cols, sess_rows, spec="PORT_M1B",
                extra=["phase-close walled DP per session; per-family DP is "
                       "the DP over that family's candidates alone"])
    M.write_tsv(M.out_path(OUT_DIR, "census_family_value.tsv"), SECTION, phash,
                ["asset", "family", "n_candidates", "n_positive",
                 "mean_cert_usd", "median_cert_usd", "positive_frac",
                 "mean_positive_cert_usd"], fam_rows, spec="PORT_M1B",
                extra=["mean_positive_cert_usd = the CC-M1-3.2 CONDITIONAL "
                       "walled cert value"])
    M.write_tsv(M.out_path(OUT_DIR, "census_family_exclusive.tsv"), SECTION,
                phash, ["asset", "family", "era", "n_sessions",
                        "exclusive_dp_add_median_usd",
                        "exclusive_dp_add_mean_usd", "n_exclusive_median",
                        "n_exclusive_total"], excl_rows, spec="PORT_M1B",
                extra=["exclusive DP add = union DP - DP without that family's "
                       "EXCLUSIVE candidates"])

    roll, legs = recall(assets, workers)
    M.write_tsv(M.out_path(OUT_DIR, "census_union_recall.tsv"), SECTION, phash,
                ["asset", "dropped_exclusive_family", "era", "n_legs",
                 "n_catchable", "n_structural_gap",
                 "recall_catchable_900", "recall_catchable_1000",
                 "recall_catchable_1100", "recall_catchable_1000_screened",
                 "recall_raw_900", "recall_raw_1000", "recall_raw_1100",
                 "recall_raw_1000_screened", "recall_structural_1000",
                 "n_structural_captured_1000", "gate_catchable_ge_99"],
                roll, spec="PORT_M1B",
                extra=["ANCHORED oracle (CC-M0-2.1); CC-M1-3.4a split: leg "
                       "full span < %ds = STRUCTURAL_GAP; the >=%.0f%% gate "
                       "applies to CATCHABLE legs @$1,000"
                       % (STRUCTURAL_SPAN, 100 * RECALL_GATE)])
    M.write_tsv(M.out_path(OUT_DIR, "oracle_legs.tsv"), SECTION, phash,
                LEG_COLUMNS, legs, spec="PORT_M1B",
                extra=["every ANCHORED oracle leg scored against the full "
                       "union roster (dropped_exclusive_family = NONE)"])
    M.write_tsv(M.out_path(OUT_DIR, "family_marginals.tsv"), SECTION, phash,
                ["asset", "family", "era", "n_candidates", "n_positive",
                 "conditional_value_usd", "mean_cert_usd", "n_exclusive_total",
                 "exclusive_dp_add_median_usd", "exclusive_dp_add_mean_usd",
                 "recall_catchable_1000_union", "recall_catchable_1000_without",
                 "marginal_recall_catchable_pp", "recall_raw_1000_union",
                 "recall_raw_1000_without", "marginal_recall_raw_pp"],
                marginals(fam_rows, excl_rows, roll), spec="PORT_M1B",
                extra=["marginal = union minus the roster with that family's "
                       "EXCLUSIVE candidates removed (CC-M1-3.2 metric)"])

    gate = [r for r in roll if r[1] == "NONE" and r[2] == M.ERA_ALL]
    for r in gate:
        M.hb("s1v2 GATE %s: catchable recall@1k %.4f (%s) raw %.4f"
             % (r[0], r[7], r[16], r[11]))
    return 0 if all(r[16] == "PASS" for r in gate) else 1


if __name__ == "__main__":
    sys.exit(main())
