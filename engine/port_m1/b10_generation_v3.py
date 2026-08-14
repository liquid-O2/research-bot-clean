#!/usr/bin/python3
"""PORT M1.B S1.1 + S1.2 — the ENRICHED UNION ROSTER (generation prototype v3).

THIS FILE IS THE FROZEN DIFFERENTIAL ORACLE for the C++ S2.2 increment: every
candidate it emits, and every stored field, is what `qr_gen` must reproduce
candidate-exact once it inherits OR_EXT and the adopted discovery families.

WHAT CHANGES vs the v2 oracle (b8_generation_v2.py), all of it adjudicated:

  S1.1  CC-M1-6.1  OR_EXT joins the LEDGER as a kept level family (six adopted
                   cells: SI OR30 TOKYO/LONDON/NY + OR60 TOKYO/LONDON, NKD OR30
                   LONDON, HG none).  G2-REJECT / G2-RECLAIM fire at an OR_EXT
                   level exactly like at any other kept level — no new
                   confirmation type, no special case.  Ledger: m1/levels_v4
                   (b10_levels_v4.py), differenced row-for-row against v3.
  S1.2  CC-M1-7.1  four adopted generator families:
        NEWS_WINDOW  first 10 min after a scheduled release, SINGLE 15s delay
                     (FOMC 14:00 ET on the meeting's last day + the fixed
                      08:30/10:00 ET slots; the BOJ leg stays DEFERRED — the
                      banked calendar starts 2026, revisit hook FD-2)
        MICRO_OPEN   Tokyo lunch reopen (12:30 JST) + US cash open (09:30 ET),
                     FAST-OPEN construction: 300s window, 15s delay
        POST_SHOCK   the first confirmation strictly after a causal shock
                     episode ends (trailing-150s $1,000 SANE repricing, or a
                     run of >= 10 wide-but-two-sided seconds), delay tau*
        FIRST_TEST   NKD ONLY: the session's earliest confirming touch per kept
                     level family, delay tau* (a tag on candidates the roster
                     already carries; a feature, not a family, on SI/HG)
  S1.2  CC-M1-7.2  FAST-CLOSE stays DEAD (never generated).  F-D6
                   EXHAUSTION-AT-EXTENSION is a FLAG on the candidate, not a
                   family: `flags` bit 0 = the entry mid sits beyond a live,
                   same-segment OR_EXT k >= 1.5 level of an ADOPTED cell, bit 1
                   = the same over ALL (segment x OR-minutes) cells.
  S1.2  CC-M1-7.3  the operative adoption metric is CONDITIONAL VALUE with the
                   "smaller AND better" bar; recall/seat-share clauses remain
                   as regression guards.  Both the phase-close and the
                   horizon-free PEAK-exit conditional values are reported
                   (defect FD-8).

EVERYTHING ELSE IS REUSED, NOT REWRITTEN: b8's G1 emission and G2 touch read,
family_discovery's window / shock / OR-extension detectors and FOMC calendar,
c_c_roster's _emit_candidate / certificates / dp_schedule, c_d_recall's oracle
legs and _score_leg, b7_sane's D-054 mask.

Run: lab/run.sh port-m1-s11 -- /usr/bin/python3 engine/port_m1/b10_generation_v3.py
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
import c_d_recall as CD
import b1_decay as B1
import b7_sane as B7
import b8_generation_v2 as G
import b10_levels_v4 as L4
import family_discovery as FD

SECTION = "S1.1+S1.2 enriched generation v3 (CC-M1-6.1 + CC-M1-7.1)"

OUT_DIR = "generation_v3"
LEVELS_DIR = L4.OUT_DIR                  # m1/levels_v4 (D-053 + D-054 + OR_EXT)

TAU_STAR = G.TAU_STAR                    # 120s
RUNGS_V3 = G.RUNGS_V2                    # (0.05, 0.075, 0.11, 0.15)

NEWS_DELAY = 15                          # CC-M1-7.1 "single 15s delay"
NEWS_WINDOW = FD.NEWS_WINDOW             # 600s
MICRO_DELAY = FD.MICRO_DELAY             # 15s
MICRO_WINDOW = FD.MICRO_WINDOW           # 300s

# S1.1: OR_EXT is a KEPT level source, so a touch on it makes a G2 candidate.
KEPT_LEVEL_FAMILIES = G.KEPT_LEVEL_FAMILIES + ("OR_EXT",)
RETIRED_LEVEL_FAMILIES = G.RETIRED_LEVEL_FAMILIES

FAMILIES = ("G1", "G1_FINE", "G1_FAST_OPEN", "G2_REJECT", "G2_RECLAIM",
            "NEWS_WINDOW", "MICRO_OPEN", "POST_SHOCK", "FIRST_TEST")
NEW_FAMILIES = ("NEWS_WINDOW", "MICRO_OPEN", "POST_SHOCK", "FIRST_TEST")
FAM_BIT = {f: 1 << i for i, f in enumerate(FAMILIES)}
# CC-M1-7.1: F-D5 is a FAMILY on NKD and a feature elsewhere.
FIRST_TEST_ASSETS = ("NKD",)

# CC-M1-7.2: F-D6 = flag only.
FLAG_OREXT_BEYOND = 1 << 0               # adopted cells
FLAG_OREXT_BEYOND_ANY = 1 << 1           # all (segment x OR-minute) cells
FLAG_FIRST_TEST_VIRGIN = 1 << 2          # the touch was the level's first ever

RECALL_GATE = G.RECALL_GATE              # 0.99 on the catchable (gate) legs
NEWS_SPAN = G.NEWS_SPAN                  # 150s

PARAMS = {
    "spec_section": SECTION,
    "families": list(FAMILIES),
    "new_families": list(NEW_FAMILIES),
    "first_test_assets": list(FIRST_TEST_ASSETS),
    "tau_star_sec": TAU_STAR,
    "rungs": list(RUNGS_V3),
    "levels_source": "m1/%s (D-053 bands, D-054 mask, CC-M1-6.1 OR_EXT)"
                     % LEVELS_DIR,
    "kept_level_families": list(KEPT_LEVEL_FAMILIES),
    "retired_level_families": list(RETIRED_LEVEL_FAMILIES),
    "news_window": "first %ds after FOMC 14:00 ET (meeting last day) and the "
                   "fixed 08:30/10:00 ET slots; SINGLE %ds delay; G1 "
                   "confirmations only (CC-M1-5 D14 precedent); BOJ deferred "
                   "(calendar starts 2026)" % (NEWS_WINDOW, NEWS_DELAY),
    "micro_open": "first %ds after the Tokyo lunch reopen (12:30 Asia/Tokyo) "
                  "and the US cash open (09:30 America/New_York, DST-correct); "
                  "%ds delay; G1 confirmations only"
                  % (MICRO_WINDOW, MICRO_DELAY),
    "post_shock": "first confirmation (G1 or G2) strictly after a causal shock "
                  "episode ends: trailing-%ds SANE mid range >= $%.0f, or a run "
                  "of >= %ds wide-but-two-sided (D-054 insane) seconds; delay "
                  "tau*" % (FD.SHOCK_SPAN, FD.SHOCK_USD, FD.INSANE_MIN_SEC),
    "first_test": "NKD only: earliest confirming touch per (session, kept "
                  "level family), delay tau*; VIRGIN carried as a flag",
    "fast_close": "RETIRED (CC-M1-7.2), never generated",
    "f_d6": "FLAG ONLY (CC-M1-7.2): entry mid beyond a live same-segment "
            "OR_EXT k >= %.1f level" % FD.OREXT_K_MIN,
    "dedup": "(session, decision_sec, side); family/rung/level/flag tags "
             "unioned; confirmation_sec = the earliest confirmation mapping "
             "to it",
    "certificates": "m0 §8 walled peak-exit and phase-close, wall from "
                    "m0 walls.json, session-scoped cost_rt",
    "mid_sanity": "D-054: SANE seconds only (b7_sane) everywhere",
    "adoption_metric": "CC-M1-7.3 conditional walled value (smaller AND "
                       "better); peak-exit comparator reported beside it "
                       "(defect FD-8); recall/seat-share = regression guards",
    "recall_gate": RECALL_GATE,
    "recall_classes": "post-mask legs completing < %ds = NEWS_UNTRADEABLE, "
                      "counted beside the gate, never inside it" % NEWS_SPAN,
}


# ============================================ S1.2 window/trigger detectors ===
def news_release_offsets(open_utc, n, fomc_dates):
    """Session-second offsets of every scheduled release inside the session.

    THE CALENDAR JOIN (red-first, test_m1c.py): the fixed slots are LOCAL wall
    times in America/New_York and are materialised through the tz database, so
    they follow DST instead of a frozen UTC offset; `local_epochs` scans the
    day BEFORE, the session's own day and the day AFTER, because a Globex
    session opens the previous evening ET — joining on the session's date alone
    is the off-by-one-day bug this function exists to prevent.  The FOMC
    statement lands on the meeting's LAST day at 14:00 ET.
    """
    rel = []
    for (_nm, tz, hh, mm) in FD.NEWS_SLOTS:
        rel.extend(FD.local_epochs(open_utc, n, tz, hh, mm))
    for off in FD.local_epochs(open_utc, n, FD.TZ_NY, FD.FOMC_HOUR,
                               FD.FOMC_MIN, days=(-1, 0, 1)):
        # the FOMC slot counts only when the DATE THAT SLOT FALLS ON is a
        # release date — the calendar join is on the local ET calendar day of
        # the release second, never on the session's own trade_date.
        if FD.dt.datetime.fromtimestamp(int(open_utc) + off,
                                        FD.TZ_NY).date() in fomc_dates:
            rel.append(off)
    return sorted(set(int(x) for x in rel))


def micro_open_offsets(open_utc, n):
    """Session-second offsets of the CC-M1-7.1 micro-opens (DST-correct)."""
    out = []
    for (_nm, tz, hh, mm) in FD.MICRO_OPENS:
        out.extend(FD.local_epochs(open_utc, n, tz, hh, mm))
    return sorted(set(int(x) for x in out))


def g2_from_levels(asset, trade_date):
    """(conf_sec, approach_side, family, level_family) from m1/levels_v4.

    b8's reader, re-pointed at the OR_EXT ledger and at the v3 kept set — the
    30-min RECLAIM bound and the retired-source drop are b8's, unchanged.
    """
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
            if G.reclaim_within_bound(brk, rec):
                out.append((rec, app, "G2_RECLAIM", lf))
            else:
                n_drop_bound += 1
    return out, n_drop_fam, n_drop_bound


def first_test_confirmations(asset, trade_date, g2):
    """{conf_sec: virgin} for the earliest confirming touch per level family."""
    first = {}
    for (conf, side, _fam, lf) in g2:
        cur = first.get(lf)
        if cur is None or conf < cur[0]:
            first[lf] = (conf, side)
    virgin = FD._virgin_confirmation_secs(asset, trade_date)
    return {c: (c in virgin) for (c, _s) in first.values()}, first


# ================================================== the per-session emission ==
def session_emission(asset, s, trade_date, atr, phase_med, open_utc,
                     fomc_dates):
    """{(dec_sec, side): [fam_bits, level_bits, rung_mask, conf_sec, flags]}."""
    lvl_fams = list(KEPT_LEVEL_FAMILIES)
    confs = B1.session_confirmations(s, asset, atr, phase_med, trade_date,
                                     RUNGS_V3)
    opens = G.phase_open_secs(s)
    g2, n_dropf, n_dropb = g2_from_levels(asset, trade_date)

    merged = {}

    def add(dec, side, fam_bit, rmask, conf, lvl_bit=0, flags=0):
        e = merged.setdefault((dec, side), [0, 0, 0, conf, 0])
        e[0] |= fam_bit
        e[1] |= lvl_bit
        e[2] |= rmask
        e[3] = min(e[3], conf)
        e[4] |= flags

    # ---- G1 / G1-FINE / G1-FAST-OPEN (b8's emission, verbatim) -------------
    for (dec, side, fam, rmask, conf) in G.g1_emissions(confs, opens):
        add(dec, side, fam, rmask, conf)
    # ---- G2-REJECT / G2-RECLAIM, now including OR_EXT births ---------------
    for (conf, side, fam, lf) in g2:
        add(conf + TAU_STAR, side, FAM_BIT[fam], 0, conf,
            lvl_bit=1 << lvl_fams.index(lf))

    # ---- NEWS_WINDOW / MICRO_OPEN (G1 confirmation universe, D14) ----------
    news_iv = FD.open_windows(news_release_offsets(open_utc, s.n, fomc_dates),
                              NEWS_WINDOW)
    micro_iv = FD.open_windows(micro_open_offsets(open_utc, s.n), MICRO_WINDOW)
    n_news = n_micro = 0
    for (conf, side, rmask) in confs:
        if FD.in_intervals(conf, news_iv):
            n_news += 1
            add(conf + NEWS_DELAY, side, FAM_BIT["NEWS_WINDOW"], rmask, conf)
        if FD.in_intervals(conf, micro_iv):
            n_micro += 1
            add(conf + MICRO_DELAY, side, FAM_BIT["MICRO_OPEN"], rmask, conf)

    # ---- POST_SHOCK --------------------------------------------------------
    all_conf = sorted([(c, sd) for (c, sd, _m) in confs]
                      + [(c, sd) for (c, sd, _f, _lf) in g2])
    conf_secs = [c for (c, _sd) in all_conf]
    eps = FD.shock_episodes(s.vt, s.vm, C.ASSETS[asset]["mult"])
    ins = FD.insane_episodes(s.state == C.ST_TWO_SIDED, s.valid)
    n_shock = 0
    for (_a, b) in sorted(eps + ins):
        for i in FD.first_confirmations_after(conf_secs, b):
            c, sd = all_conf[i]
            add(c + TAU_STAR, sd, FAM_BIT["POST_SHOCK"], 0, c)
            n_shock += 1

    # ---- FIRST_TEST (NKD only) --------------------------------------------
    n_first = 0
    if asset in FIRST_TEST_ASSETS:
        ft, first = first_test_confirmations(asset, trade_date, g2)
        for lf, (conf, side) in sorted(first.items()):
            add(conf + TAU_STAR, side, FAM_BIT["FIRST_TEST"], 0, conf,
                flags=(FLAG_FIRST_TEST_VIRGIN if ft.get(conf) else 0))
            n_first += 1

    # ---- F-D6 flag (CC-M1-7.2: a flag, never a family) --------------------
    cells_adopted, cells_all = [], []
    for (seg, mn) in FD.OREXT_ALL:
        rows = FD.orext_levels(s, seg, mn)
        cells_all.extend(rows)
        if (seg, mn) in L4.OREXT_ADOPTED[asset]:
            cells_adopted.extend(rows)
    n_flag = 0
    for (dec, side) in sorted(merged):
        if dec >= s.n or not s.valid[dec]:
            continue
        mid = float(s.mid[dec])
        ph = int(s.phase_tag[dec])
        f = 0
        if cells_adopted and FD.beyond_extension(mid, dec, ph, cells_adopted):
            f |= FLAG_OREXT_BEYOND
        if cells_all and FD.beyond_extension(mid, dec, ph, cells_all):
            f |= FLAG_OREXT_BEYOND_ANY
        if f:
            merged[(dec, side)][4] |= f
            n_flag += 1

    stats = {"n_conf": len(confs), "n_g2": len(g2), "n_news_conf": n_news,
             "n_micro_conf": n_micro, "n_post_shock": n_shock,
             "n_first_test": n_first, "n_shock_episodes": len(eps),
             "n_insane_episodes": len(ins), "n_orext_flag": n_flag,
             "n_drop_retired_level": n_dropf, "n_drop_reclaim_bound": n_dropb,
             "n_phase_opens": len(opens)}
    return merged, stats


def _asset_roster(args):
    asset, sess, phase_med, cost_map, sane_thr, fomc_dates = args
    mult = C.ASSETS[asset]["mult"]
    bars = X.load_bars(asset, M.M0_ROOT)
    cols = {k: [] for k in CC.ROSTER_KEYS}
    f_t, f_v, a_t, a_v = [], [], [], []
    fam_mask, lvl_mask, rung_mask, flag_mask = [], [], [], []
    per_session = []
    for trade_date, path in sess:
        bar = bars.get(trade_date)
        atr = bar["ATR14_prev_usd"] if bar else float("nan")
        s = X.load_session(asset, trade_date, path)
        # R89 (the D-001 fix pass): `thr if thr is not None else
        # [SANE_CAP_USD]*N` silently handed a session with no committed
        # threshold a mask 2-4x TOO PERMISSIVE (the committed SI/HG thresholds
        # are $125-$250 against the $500 cap).  D-054's typed-exclusion
        # doctrine makes a missing threshold a REFUSAL; `b7_sane.apply_for`
        # raises SaneThresholdRefusal, which is the same guard assemble and
        # b2_fvol now use.
        insane = B7.apply_for(s, sane_thr, asset, M.d8(trade_date))
        if s.vt.size < 2 or not np.isfinite(atr):
            continue
        open_utc = int(s.meta["open_utc"])
        merged, st = session_emission(asset, s, trade_date, atr, phase_med,
                                      open_utc, fomc_dates)
        cost_rt = cost_map.get((asset, trade_date.isoformat()), float("nan"))
        if not np.isfinite(cost_rt):
            cost_rt = C.FEES_RT
        n_cand = n_skip_close = n_skip_state = 0
        for (dec, side) in sorted(merged):
            fm, lm, rm, conf, fl = merged[(dec, side)]
            if dec >= s.n:
                n_skip_close += 1
                continue
            if not s.valid[dec]:
                n_skip_state += 1
                continue
            n_cand += 1
            CC._emit_candidate(cols, f_t, f_v, a_t, a_v, s, trade_date, asset,
                               mult, side, rm, conf, dec, atr)
            fam_mask.append(fm)
            lvl_mask.append(lm)
            rung_mask.append(rm)
            flag_mask.append(fl)
        per_session.append([asset, trade_date.isoformat(), trade_date.year,
                            n_cand, n_skip_close, n_skip_state, st["n_conf"],
                            st["n_g2"], st["n_news_conf"], st["n_micro_conf"],
                            st["n_post_shock"], st["n_first_test"],
                            st["n_shock_episodes"], st["n_insane_episodes"],
                            st["n_orext_flag"], st["n_drop_retired_level"],
                            st["n_drop_reclaim_bound"], st["n_phase_opens"],
                            insane, cost_rt])
    arrays = {}
    dtypes = {"date8": np.int32, "side": np.int8, "rung_mask": np.uint8,
              "conf_sec": np.int32, "dec_sec": np.int32, "phase_conf": np.int8,
              "phase_dec": np.int8, "mfe_argmax_sec": np.int32,
              "phase_close_sec": np.int32, "sess_close_sec": np.int32,
              "iid": np.int64, "f_off": np.int64, "f_len": np.int64,
              "a_off": np.int64, "a_len": np.int64}
    for k in CC.ROSTER_KEYS:
        arrays[k] = np.array(cols[k], dtype=dtypes.get(k, np.float64))
    arrays["skel_f_t"] = np.array(f_t, dtype=np.int32)
    arrays["skel_f_v"] = np.array(f_v, dtype=np.float32)
    arrays["skel_a_t"] = np.array(a_t, dtype=np.int32)
    arrays["skel_a_v"] = np.array(a_v, dtype=np.float32)
    arrays["fam_mask"] = np.array(fam_mask, dtype=np.uint16)
    arrays["level_fam_mask"] = np.array(lvl_mask, dtype=np.uint16)
    arrays["flags"] = np.array(flag_mask, dtype=np.uint8)
    arrays["skips"] = np.zeros((0, 6), np.int64)
    C.savez_det(M.out_path(OUT_DIR, "union_roster_%s.npz" % asset), **arrays)
    M.hb("s1v3 roster %s: %d union candidates" % (asset,
                                                  arrays["date8"].size))
    return asset, per_session


# ================================================================== census ====
def _cond(vals):
    """CC-M1-7.3 conditional walled value: mean over the POSITIVE certs."""
    v = np.asarray(vals, dtype=np.float64)
    v = v[np.isfinite(v) & (v > 0)]
    return ((M.mean(v) if v.size else float("nan")), int(v.size))


def census(assets):
    """Per-session DP + per-family value/seat accumulators (b8's machinery)."""
    with open(os.path.join(M.M0_ROOT, "walls.json")) as fh:
        walls = json.load(fh)["walls"]
    cost_map = CA.session_cost_rt(M.M0_ROOT)
    sess_rows, fam_rows, excl_rows, seat_rows = [], [], [], []
    for asset in assets:
        z = np.load(M.out_path(OUT_DIR, "union_roster_%s.npz" % asset),
                    allow_pickle=False)
        r = {k: z[k] for k in z.files}
        z.close()
        W = float(walls[asset]["wall_usd"])
        fm = r["fam_mask"]
        d8 = r["date8"]
        year = (d8 // 10000).astype(np.int64)
        by_date = {}
        for i in range(int(d8.size)):
            by_date.setdefault(int(d8[i]), []).append(i)
        vals = np.full(int(d8.size), np.nan)
        vals_pk = np.full(int(d8.size), np.nan)
        seats = {f: {} for f in list(FAMILIES) + ["UNION"]}
        excl_acc = {f: [] for f in FAMILIES}
        for d in sorted(by_date):
            iso = "%04d-%02d-%02d" % (d // 10000, (d // 100) % 100, d % 100)
            cost = cost_map.get((asset, iso), float("nan"))
            if not np.isfinite(cost):
                cost = C.FEES_RT
            idx = by_date[d]
            items = []
            for i in idx:
                pk, cl = CC.certificates(r, i, W, cost)
                vals[i] = cl[0]
                vals_pk[i] = pk[0]
                items.append((cl[1], cl[2], cl[0], int(r["dec_sec"][i]),
                              int(r["iid"][i]), i))
            tot_union, sel_union = CC.dp_schedule(items)
            row = [asset, iso, d // 10000, len(idx), tot_union, len(sel_union)]
            for f in FAMILIES:
                bit = FAM_BIT[f]
                fidx = set(i for i in idx if int(fm[i]) & bit)
                fitems = [it for it in items if it[5] in fidx]
                ftot, fsel = CC.dp_schedule(fitems)
                n_seat = sum(1 for i in sel_union if int(fm[i]) & bit)
                exc = set(i for i in idx if int(fm[i]) == bit)
                ritems = [it for it in items if it[5] not in exc]
                rtot, _ = CC.dp_schedule(ritems)
                excl_acc[f].append((d // 10000, tot_union - rtot, len(exc)))
                row.extend([len(fidx), ftot, len(fsel), len(exc), n_seat])
                if fidx:
                    for era in _eras(d // 10000):
                        e = seats[f].setdefault(era, [0, 0])
                        e[0] += n_seat
                        e[1] += len(sel_union)
            sess_rows.append(row)
        eras = [(M.ERA_FIT, np.isin(year, np.array(M.FIT_YEARS))),
                (M.ERA_GATE, year == 2025),
                (M.ERA_ALL, np.ones(year.size, dtype=bool))]
        eras.extend((str(y), year == y) for y in M.FIT_YEARS)
        sets = [(f, (fm & FAM_BIT[f]) != 0) for f in FAMILIES]
        sets.append(("UNION", np.ones(int(d8.size), dtype=bool)))
        for (f, sel) in sets:
            for (era, esel) in eras:
                m_ = sel & esel
                n = int(m_.sum())
                cv, npos = _cond(vals[m_])
                cvp, npos_p = _cond(vals_pk[m_])
                fam_rows.append([asset, f, era, n, npos, cv,
                                 M.mean(vals[m_][np.isfinite(vals[m_])])
                                 if n else float("nan"),
                                 (npos / n) if n else float("nan"),
                                 npos_p, cvp])
        for f in FAMILIES:
            for era in sorted(seats[f]):
                n_seat, n_tot = seats[f][era]
                seat_rows.append([asset, f, era, n_seat, n_tot,
                                  (n_seat / n_tot) if n_tot
                                  else float("nan")])
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
        M.hb("s1v3 census %s: done" % asset)
    return sess_rows, fam_rows, excl_rows, seat_rows


def _eras(y):
    out = [M.ERA_ALL]
    if M.is_fit(y):
        out.append(M.ERA_FIT)
    if int(y) == 2025:
        out.append(M.ERA_GATE)
    return out


# =================================================================== recall ===
def _recall_task(args):
    asset, sess, phase_med, roster_by_date, drops, sane_thr = args
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
        B7.apply_for(s, sane_thr, asset, M.d8(trade_date))   # R89, as above
        if s.vt.size < 2:
            continue
        thr_px = X.round_half_up(X.ORACLE_RUNG * atr / mult, tick_px)
        legs = CD.oracle_legs(s.vt.tolist(), s.vm.tolist(), thr_px, mult,
                              "ANCHORED")
        legs = [lg for lg in legs if lg[5] >= X.ORACLE_LEG_MIN and lg[4] != 0]
        legs.sort(key=lambda lg: (-lg[5], lg[0], lg[2]))
        legs = legs[:X.ORACLE_TOP_K]
        legs.sort(key=lambda lg: (lg[0], lg[2]))
        allc = roster_by_date.get(M.d8(trade_date), [])
        for drop in drops:
            cands = allc if drop is None else [c for c in allc
                                               if c["excl"] != drop]
            for lg in legs:
                span = int(lg[2]) - int(lg[0])
                rows.append([drop or "NONE", span,
                             1 if G.is_news_untradeable(span) else 0]
                            + CD._score_leg(asset, trade_date, "ANCHORED", lg,
                                            cands, [], mult, phase_med, atr,
                                            thr_px))
    return rows


LEG_COLUMNS = (["dropped_exclusive_family", "leg_span_sec", "news_untradeable"]
               + CD.LEG_COLUMNS)
LI = {c: i for i, c in enumerate(LEG_COLUMNS)}


def _recall_rollup(legs, drop):
    out = []
    dl = [lg for lg in legs if lg[0] == drop]
    for era in (M.ERA_FIT, M.ERA_GATE, M.ERA_ALL):
        sel = [lg for lg in dl
               if (era == M.ERA_ALL
                   or (era == M.ERA_FIT and M.is_fit(int(lg[LI["year"]])))
                   or (era == M.ERA_GATE and int(lg[LI["year"]]) == 2025))]
        if not sel:
            continue
        cat = [lg for lg in sel if not int(lg[LI["news_untradeable"]])]
        stru = [lg for lg in sel if int(lg[LI["news_untradeable"]])]

        def rate(rows_, col):
            return (sum(int(l[LI[col]]) for l in rows_) / len(rows_)) \
                if rows_ else float("nan")
        r_cat = rate(cat, "captured_1000")
        out.append([drop, era, len(sel), len(cat), len(stru),
                    rate(cat, "captured_900"), r_cat, rate(cat, "captured_1100"),
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
        sane_thr = B7.load_thresholds(asset)
        chunks = [sess[i::workers] for i in range(workers)]
        tasks = [(asset, ch, phase_med, by_date, variants, sane_thr)
                 for ch in chunks if ch]
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
        M.hb("s1v3 recall %s: %d leg-scorings" % (asset, len(legs)))
    return roll, all_legs


def marginals(fam_rows, excl_rows, seat_rows, roll):
    """Per family: CC-M1-7.3 conditional value + recall pp + DP + seat share."""
    base = {}
    for row in roll:
        if row[1] == "NONE":
            base[(row[0], row[2])] = row
    val = {(r[0], r[1], r[2]): r for r in fam_rows}
    dp = {(r[0], r[1], r[2]): r for r in excl_rows}
    seat = {(r[0], r[1], r[2]): r for r in seat_rows}
    out = []
    for row in roll:
        asset, drop, era = row[0], row[1], row[2]
        if drop == "NONE":
            continue
        b = base.get((asset, era))
        if b is None:
            continue
        v = val.get((asset, drop, era))
        u = val.get((asset, "G1", era))
        d = dp.get((asset, drop, era))
        s_ = seat.get((asset, drop, era))
        out.append([asset, drop, era,
                    (v[3] if v else None), (v[4] if v else None),
                    (v[5] if v else None), (v[9] if v else None),
                    ((v[5] - u[5]) if (v and u) else None),
                    ((v[9] - u[9]) if (v and u) else None),
                    (s_[5] if s_ else None),
                    (d[7] if d else None), (d[4] if d else None),
                    b[7], row[7], 100.0 * (b[7] - row[7]),
                    b[11], row[11], 100.0 * (b[11] - row[11])])
    return out


def wall_stats(assets):
    rows = []
    for asset in assets:
        z = np.load(M.out_path(OUT_DIR, "union_roster_%s.npz" % asset),
                    allow_pickle=False)
        mfe, mae = z["mfe_unwalled"], z["mae_before_argmax"]
        year = (z["date8"] // 10000).astype(np.int64)
        z.close()
        win = mfe >= X.WINNER_MFE
        for era, sel in ((M.ERA_FIT, np.isin(year, np.array(M.FIT_YEARS))),
                         (M.ERA_GATE, year == 2025),
                         (M.ERA_ALL, np.ones(year.size, dtype=bool))):
            s_ = win & sel
            v = mae[s_]
            rows.append([asset, era, int(sel.sum()), int(s_.sum()),
                         X.pct(v, 95), X.pct(v, 99), M.med(v), M.mean(v)])
    return rows


def delta_vs_v2(assets):
    """The S1-v2 -> S1-v3 roster delta: what the enrichment actually added."""
    rows = []
    for asset in assets:
        out = []
        for d, nm in ((G.OUT_DIR, "v2"), (OUT_DIR, "v3")):
            z = np.load(M.out_path(d, "union_roster_%s.npz" % asset),
                        allow_pickle=False)
            keys = set(zip(z["date8"].tolist(), z["dec_sec"].tolist(),
                           z["side"].tolist()))
            out.append((keys, int(z["date8"].size)))
            z.close()
        (k2, n2), (k3, n3) = out
        rows.append([asset, n2, n3, n3 - n2, len(k3 - k2), len(k2 - k3),
                     len(k2 & k3)])
    return rows


# ===================================================================== main ===
def main():
    M.verify_spec_m1b()
    workers = int(os.environ.get("M1_WORKERS", "6"))
    assets = [a for a in sys.argv[1:] if a in M.ASSET_ORDER] or \
        list(M.ASSET_ORDER)
    phash = C.params_hash(PARAMS)
    phase_med = CA.phase_median_spreads(M.M0_ROOT)
    cost_map = CA.session_cost_rt(M.M0_ROOT)
    fomc = set(FD.fomc_release_dates())
    M.hb("s1v3: levels=%s, %d FOMC release dates, families=%s"
         % (LEVELS_DIR, len(fomc), ",".join(FAMILIES)))

    tasks = [(a, X.session_paths(a, M.M0_ROOT), phase_med, cost_map,
              B7.load_thresholds(a), fomc) for a in assets]
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
                 "n_skip_past_close", "n_skip_not_sane", "n_g1_confirmations",
                 "n_g2_events", "n_conf_in_news_window",
                 "n_conf_in_micro_open", "n_post_shock_triggers",
                 "n_first_test_tags", "n_shock_episodes", "n_insane_episodes",
                 "n_orext_beyond_flags", "n_g2_dropped_retired_level",
                 "n_g2_dropped_reclaim_bound", "n_phase_opens", "insane_frac",
                 "cost_rt_session"], build_rows, spec="PORT_M1B",
                extra=["S1.1 OR_EXT levels + S1.2 adopted families on the "
                       "D-054 SANE view"])

    M.write_tsv(M.out_path(OUT_DIR, "roster_delta_v2_v3.tsv"), SECTION, phash,
                ["asset", "n_v2", "n_v3", "n_delta", "n_only_v3", "n_only_v2",
                 "n_shared"], delta_vs_v2(assets), spec="PORT_M1B",
                extra=["candidate keys (date8, dec_sec, side); n_only_v2 must "
                       "be 0 - the enrichment is ADDITIVE by construction"])

    sess_rows, fam_rows, excl_rows, seat_rows = census(assets)
    cols = ["asset", "trade_date", "year", "n_union", "union_dp_close_usd",
            "n_seated_union"]
    for f in FAMILIES:
        cols += ["n_%s" % f, "dp_%s_usd" % f, "n_seated_%s" % f,
                 "n_exclusive_%s" % f, "n_union_seats_%s" % f]
    M.write_tsv(M.out_path(OUT_DIR, "census_union_seatable.tsv"), SECTION,
                phash, cols, sess_rows, spec="PORT_M1B",
                extra=["phase-close walled DP per session; per-family DP is "
                       "the DP over that family's candidates alone; "
                       "n_union_seats_* = seats that family holds in the UNION "
                       "schedule"])
    M.write_tsv(M.out_path(OUT_DIR, "census_family_value.tsv"), SECTION, phash,
                ["asset", "family", "era", "n_candidates", "n_positive",
                 "conditional_value_usd", "mean_cert_usd", "positive_frac",
                 "n_positive_peak", "conditional_value_peak_usd"], fam_rows,
                spec="PORT_M1B",
                extra=["conditional_value_usd = the CC-M1-7.3 metric (mean "
                       "walled phase-close certificate over POSITIVE "
                       "candidates); the PEAK-exit column is the horizon-free "
                       "comparator (defect FD-8)"])
    M.write_tsv(M.out_path(OUT_DIR, "census_family_exclusive.tsv"), SECTION,
                phash, ["asset", "family", "era", "n_sessions",
                        "exclusive_dp_add_median_usd",
                        "exclusive_dp_add_mean_usd", "n_exclusive_median",
                        "n_exclusive_total"], excl_rows, spec="PORT_M1B")
    M.write_tsv(M.out_path(OUT_DIR, "census_family_seats.tsv"), SECTION, phash,
                ["asset", "family", "era", "n_seats_held", "n_seats_total",
                 "seat_share"], seat_rows, spec="PORT_M1B",
                extra=["seat share among sessions where the family has at "
                       "least one candidate (CC-M1-3.2(iii) regression guard)"])
    M.write_tsv(M.out_path(OUT_DIR, "wall_stats.tsv"), SECTION, phash,
                ["asset", "era", "n_candidates", "n_winners", "mae_p95_usd",
                 "mae_p99_usd", "mae_median_usd", "mae_mean_usd"],
                wall_stats(assets), spec="PORT_M1B")

    roll, legs = recall(assets, workers)
    M.write_tsv(M.out_path(OUT_DIR, "census_union_recall.tsv"), SECTION, phash,
                ["asset", "dropped_exclusive_family", "era", "n_legs",
                 "n_gate_legs", "n_news_untradeable", "recall_gate_900",
                 "recall_gate_1000", "recall_gate_1100",
                 "recall_gate_1000_screened", "recall_all_900",
                 "recall_all_1000", "recall_all_1100",
                 "recall_all_1000_screened", "recall_news_1000",
                 "n_news_captured_1000", "gate_ge_99"], roll, spec="PORT_M1B",
                extra=["ANCHORED oracle on the SANE mid series; the gate is "
                       ">=%.0f%% @$1,000 on the catchable legs"
                       % (100 * RECALL_GATE)])
    M.write_tsv(M.out_path(OUT_DIR, "oracle_legs.tsv"), SECTION, phash,
                LEG_COLUMNS, legs, spec="PORT_M1B")
    M.write_tsv(M.out_path(OUT_DIR, "family_marginals.tsv"), SECTION, phash,
                ["asset", "family", "era", "n_candidates", "n_positive",
                 "conditional_value_usd", "conditional_value_peak_usd",
                 "cond_value_minus_g1_usd", "cond_value_peak_minus_g1_usd",
                 "seat_share", "n_exclusive_total",
                 "exclusive_dp_add_median_usd", "recall_gate_1000_union",
                 "recall_gate_1000_without", "marginal_recall_gate_pp",
                 "recall_all_1000_union", "recall_all_1000_without",
                 "marginal_recall_all_pp"],
                marginals(fam_rows, excl_rows, seat_rows, roll),
                spec="PORT_M1B",
                extra=["CC-M1-7.3: conditional value is the operative metric; "
                       "marginal = union minus the roster with that family's "
                       "EXCLUSIVE candidates removed"])
    M.write_json(M.out_path(OUT_DIR, "s1v3_env.json"),
                 {"spec_section": SECTION, "env": M.env_receipt(PARAMS),
                  "params_hash": phash, "assets": assets,
                  "levels_dir": LEVELS_DIR})

    gate = [r for r in roll if r[1] == "NONE" and r[2] == M.ERA_ALL]
    for r in gate:
        M.hb("s1v3 GATE %s: gate recall@1k %.4f (%s) all-legs %.4f "
             "news-untradeable %d" % (r[0], r[7], r[16], r[11], r[5]))
    return 0 if all(r[16] == "PASS" for r in gate) else 1


if __name__ == "__main__":
    sys.exit(main())
