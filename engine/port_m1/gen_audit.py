#!/usr/bin/python3
"""PORT M1 §11 GENERATION TRUTH AUDIT (D-069).

The question the user asked: "look at the actual paths compared with our events
— are we generating proper events or is a lot left on the table".  Aggregate
recall answers "did SOME candidate exist inside the leg"; this lane answers
"how much of the path's dollars does the roster actually reach", at path grain.

  A  LEG CAPTURE PROFILE   every ANCHORED 0.25xATR oracle leg >= $500 (NOT the
                           m0 top-2 / $1,500 gate set): travel remaining at the
                           first and best same-side candidate, candidate counts
                           by leg-progress decile, family of first/best.
  B  FORFEIT DECOMPOSITION per (asset, session): CEIL (perfect-knowledge
                           one-position phase-close DP, entries at ANY SANE
                           second) minus ROSTER (the union-roster DP), split
                           greedily into MISSED -> LATE -> EXIT_FORFEIT ->
                           OCCUPANCY.  Standing regression metric; baseline
                           frozen here.
  C  VISUAL AUDIT          20 sessions/asset, (era x offer quartile) strata,
                           median-offer session per cell (deterministic by
                           construction — no seed is consulted).
  D  GEN_AUDIT_REPORT.md   written by report_genaudit.py.

THE CEIL ENTRY SUPERSET (the one algorithm in this file that needs an argument).
The phase-close certificate is: enter at SANE second t on side d, exit at the
next phase boundary pc(t), charged the session cost_rt, killed at -$900 (the
m0 wall) if the adverse excursion reaches the wall first.  Entries may occur at
ANY SANE second, so the naive DP has ~80,000 x 2 items per session and each
item costs an O(n) scan.  The reduction:

  * pc(t) depends only on t's phase block, so every entry inside one phase
    block shares one exit second.  Value_long(t) = (mid(exit) - mid(t)) x mult
    - cost when the wall is not hit.
  * It is therefore maximised, over the block, at t* = argmin mid (long) /
    argmax mid (short).
  * t* CANNOT hit the wall: for every SANE u in (t*, pc] the mid satisfies
    mid(u) >= mid(t*) (u is in the block, where t* is the minimum, or u == pc
    whose mid IS the exit mid — and if that exit mid were below mid(t*) the
    block's best long value would already be negative and nothing is seated).
    So the unconstrained maximiser is feasible, hence optimal.
  * The DP's only cross-block coupling is "start strictly after the previous
    exit", i.e. t > pc(prev), which can exclude at most the block's FIRST
    second; the block-argmin restricted to t > first is kept for that case.

The implemented superset is the fine-grain (1-tick) ZigZag spine of the session
UNION those per-block extremum landmarks.  The spine ALONE is NOT complete —
an extremum that never retraces by a tick before the block ends is never
confirmed as a pivot — and `test_genaudit.py` carries that as the red-first
`superset_spine_only` mutant, brute-forced against the all-SANE-seconds DP.

Run: lab/run.sh port-m1-genaudit -- /usr/bin/python3 engine/port_m1/gen_audit.py
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
import b7_sane as B7
import b10_generation_v3 as G3

SECTION = "§11 generation truth audit (D-069)"
OUT_DIR = "gen_audit"
SRC_DIR = G3.OUT_DIR

LEG_MIN_USD = 500.0            # §11.A "ALL legs >= $500"
LATE_PROGRESS = 0.25           # §11.B / brief: LATE = every candidate after 25%
N_DECILES = 10
STRATA_SEED = 20260814         # declared, never consulted: strata are exact
FAMILIES = G3.FAMILIES
FAM_BIT = G3.FAM_BIT

PARAMS = {
    "spec_section": SECTION,
    "oracle": "ZigZag 0.25 x ATR14_{d-1}($) ANCHORED (c_d_recall.oracle_legs) "
              "on SANE mids (D-054 b7_sane mask)",
    "leg_min_usd": LEG_MIN_USD,
    "leg_top_k": "NONE — every leg >= $%.0f (§11.A), not the m0 top-2"
                 % LEG_MIN_USD,
    "roster": "m1/%s union_roster_{ASSET}.npz, sha-pinned to ORACLE_FREEZE.tsv"
              % SRC_DIR,
    "certificate": "m0 §8 phase-close walled certificate; wall from m0 "
                   "walls.json ($900 cap), session-scoped cost_rt from "
                   "census_a_cost.tsv phase=ALL",
    "wall_arithmetic": "float32, matching the m0 path-skeleton records the "
                       "roster certificates are answered from (defect GA-1)",
    "cc_m1_8": "peak-exit certificate reported beside every phase-close "
               "certificate (CC-M1-8.1), on the SEATED entries of both DPs",
    "ceil": "one-position phase-close DP over entries at ANY SANE second; "
            "entry superset = 1-tick ZigZag spine UNION per-phase-block "
            "extremum landmarks (argmin/argmax of the block, and of the block "
            "minus its first SANE second); proven complete, brute-forced",
    "ceil_prune": "items grouped by exit second; per group keep the best item "
                  "for each distinct predecessor-exit constraint (lossless)",
    "forfeit": "FORFEIT = max(0, CEIL - ROSTER); greedy attribution order "
               "MISSED -> LATE -> EXIT_FORFEIT -> OCCUPANCY(remainder)",
    "missed": "leg with zero same-side candidate in [leg_start, leg_end]; "
              "$ = the leg's CEIL-realisable phase-close value",
    "late": "every same-side candidate at leg progress > %.2f; $ = phase-close "
            "value entering at the leg start minus the value of the FIRST "
            "candidate" % LATE_PROGRESS,
    "exit_forfeit": "the best candidate's phase close lands before the leg "
                    "end; $ = its leg-end-exit value minus its phase-close "
                    "value",
    "progress": "(dec_sec - leg_start_sec) / (leg_end_sec - leg_start_sec); "
                "decile = min(9, floor(10 x progress))",
    "strata": "(calendar year x offer quartile) per asset; offer = SANE mid "
              "range ($); the cell's MEDIAN-offer session is picked — "
              "deterministic by construction (seed %d declared, unused)"
              % STRATA_SEED,
    "seal": "m0 substrate is 2021-2025; 2026 never decoded (§0 seal)",
}


# ============================================================ freeze pin =====
def read_tsv(path):
    rows, hdr = [], None
    with open(path) as fh:
        for line in fh:
            line = line.rstrip("\n")
            if line.startswith("#"):
                continue
            f = line.split("\t")
            if hdr is None:
                hdr = {c: i for i, c in enumerate(f)}
                continue
            rows.append(f)
    return rows, hdr


def verify_freeze(assets):
    """ORACLE_FREEZE.tsv is the pin: every roster npz sha must match."""
    rows, hdr = read_tsv(M.out_path(SRC_DIR, "ORACLE_FREEZE.tsv"))
    by = {r[hdr["asset"]]: r for r in rows}
    out = {}
    for a in assets:
        if a not in by:
            raise RuntimeError("freeze has no row for %s" % a)
        p = by[a][hdr["path"]]
        p = p if p.startswith("/") else os.path.join("/workspace", p)
        got = C.sha256_file(p)
        want = by[a][hdr["sha256"]]
        if got != want:
            raise RuntimeError("ROSTER SHA MISMATCH %s: %s != frozen %s"
                               % (a, got, want))
        out[a] = {"path": p, "sha256": got,
                  "n_candidates": int(by[a][hdr["n_candidates"]])}
    return out


# ====================================================== phase-block geometry ==
def phase_blocks(s):
    """[(phase, first_sec, end_sec_exclusive, phase_close_sec)].

    phase_close_sec is exactly census_common.next_phase_boundary() for every
    second of the block: the first second whose phase differs, or n-1 for the
    final block.  Written as a block walk so a session with a non-standard
    phase layout is handled without a special case.
    """
    tags = s.phase_tag
    n = int(s.n)
    out = []
    i = 0
    while i < n:
        p = int(tags[i])
        w = np.nonzero(tags[i + 1:] != p)[0]
        if w.size:
            j = i + 1 + int(w[0])
            out.append((p, i, j, j))
        else:
            out.append((p, i, n, n - 1))
            j = n
        i = j
    return out


class SessionValues(object):
    """Walled phase-close value of entering at EVERY SANE second, both sides.

    Vectorised: within a block the exit second is fixed, so the wall test is a
    suffix-running extremum and the value is an affine function of the entry
    mid.  O(n) per session, exact — this is what makes "entries anywhere"
    affordable at 4,521 sessions.
    """

    __slots__ = ("s", "mult", "wall", "cost", "blocks", "gid", "val",
                 "exit_sec", "pc_of_idx", "n")

    def __init__(self, s, mult, wall, cost):
        self.s = s
        self.mult = float(mult)
        self.wall = float(wall)
        self.cost = float(cost)
        vt, vm = s.vt, s.vm
        self.n = int(vt.size)
        self.val = {1: np.full(self.n, -np.inf), -1: np.full(self.n, -np.inf)}
        self.gid = np.full(self.n, -1, dtype=np.int64)
        self.pc_of_idx = np.zeros(self.n, dtype=np.int64)
        self.exit_sec = []
        self.blocks = []
        for (p, s0, s1, pc) in phase_blocks(s):
            j0 = int(np.searchsorted(vt, s0, side="left"))
            j1 = int(np.searchsorted(vt, s1 - 1, side="right"))
            je = int(np.searchsorted(vt, pc, side="right")) - 1
            if j1 <= j0 or je < j0:
                continue
            g = len(self.blocks)
            self.blocks.append((p, s0, pc, j0, j1, je))
            self.exit_sec.append(pc)
            self.gid[j0:j1] = g
            self.pc_of_idx[j0:j1] = pc
            m = vm[j0:j1]
            m_exit = float(vm[je])
            arr = vm[j0 + 1:je + 1]
            L = int(arr.size)
            sufmin = np.full(L + 1, np.inf)
            sufmax = np.full(L + 1, -np.inf)
            if L:
                sufmin[:L] = np.minimum.accumulate(arr[::-1])[::-1]
                sufmax[:L] = np.maximum.accumulate(arr[::-1])[::-1]
            k = np.arange(j1 - j0)
            dead = -self.wall - self.cost
            # FLOAT32 PARITY (defect GA-1, receipted): m0's path skeleton
            # stores the adverse running-max records as float32, so the m0 wall
            # test is a float32 comparison.  An adverse of 899.9999999999986
            # rounds UP to exactly 900.0 there and kills the certificate that a
            # float64 test would keep.  The ceiling must use the SAME
            # arithmetic as the roster it is compared against, or CEIL < ROSTER
            # becomes possible; casting is monotone so max-then-cast ==
            # cast-then-max, i.e. this reproduces the skeleton exactly.
            adv_l = ((m - sufmin[k]) * self.mult).astype(np.float32)
            v_l = np.where(adv_l >= self.wall, dead,
                           (m_exit - m) * self.mult - self.cost)
            adv_s = ((sufmax[k] - m) * self.mult).astype(np.float32)
            v_s = np.where(adv_s >= self.wall, dead,
                           (m - m_exit) * self.mult - self.cost)
            self.val[1][j0:j1] = v_l
            self.val[-1][j0:j1] = v_s

    # ---------------------------------------------------------- superset ----
    def superset(self, tick_px, mode="FULL"):
        """{group: {side: [vt index, ...]}} — the CEIL entry candidates."""
        vt, vm = self.s.vt, self.s.vm
        out = {}
        for g, (_p, _s0, _pc, j0, j1, _je) in enumerate(self.blocks):
            idx = set()
            if mode in ("FULL", "SPINE_ONLY"):
                piv = CC.zigzag_scan(vt[j0:j1].tolist(), vm[j0:j1].tolist(),
                                     [float(tick_px)] * (j1 - j0))
                for (_px, psec, _cs, _sd) in piv:
                    idx.add(int(np.searchsorted(vt, psec, side="left")))
            if mode in ("FULL", "LANDMARKS_ONLY"):
                m = vm[j0:j1]
                idx.add(j0 + int(np.argmin(m)))
                idx.add(j0 + int(np.argmax(m)))
                idx.add(j0)
                idx.add(j1 - 1)
                if m.size > 1:
                    idx.add(j0 + 1 + int(np.argmin(m[1:])))
                    idx.add(j0 + 1 + int(np.argmax(m[1:])))
            out[g] = sorted(i for i in idx if j0 <= i < j1)
        return out

    # --------------------------------------------------------------- DP -----
    def items(self, superset=None):
        """dp_schedule items (start, end, value, dec, iid, ident)."""
        vt = self.s.vt
        iid = int(self.s.iid)
        out = []
        groups = (superset if superset is not None
                  else {g: list(range(b[3], b[4]))
                        for g, b in enumerate(self.blocks)})
        for g, idxs in sorted(groups.items()):
            pc = self.exit_sec[g]
            for side in (1, -1):
                v = self.val[side]
                for j in idxs:
                    val = float(v[j])
                    if val > 0:
                        t = int(vt[j])
                        out.append((t, pc, val, t, iid, (j, side)))
        return out

    def dp(self, superset=None, prune=True):
        it = self.items(superset)
        if prune:
            it = prune_items(it)
        return CC.dp_schedule(it)


def prune_items(items):
    """Lossless reduction for items whose END second takes few distinct values.

    Every item in one end-group mutually conflicts, so an optimal schedule uses
    at most one of them, and the one it uses is the highest-valued item whose
    start clears its predecessor's exit second.  The predecessor's exit is one
    of the (few) distinct end seconds, so keeping, per group, the best item for
    each such threshold (plus the unconstrained best) is exact.
    """
    ends = sorted(set(it[1] for it in items))
    by_end = {}
    for it in items:
        by_end.setdefault(it[1], []).append(it)
    keep = {}
    for e, group in by_end.items():
        thresholds = [-1] + [x for x in ends if x < e]
        for t in thresholds:
            best = None
            for it in group:
                if it[0] <= t:
                    continue
                if best is None or (it[2], -it[0], it[5]) > (best[2], -best[0],
                                                             best[5]):
                    best = it
            if best is not None:
                keep[best[5]] = best
    return [keep[k] for k in sorted(keep)]


# ================================================== peak-exit companion ======
def peak_exit_value(sv, j, side):
    """CC-M1-8 companion: walled PEAK-EXIT certificate of entry (j, side).

    Mirrors c_c_roster.certificates()'s peak branch exactly, but for an
    arbitrary SANE second rather than a roster candidate.
    """
    vm = sv.s.vm
    entry = float(vm[j])
    f = (vm[j:] - entry) * side * sv.mult
    run_a = np.maximum.accumulate(-f).astype(np.float32)      # GA-1 parity
    w = int(np.searchsorted(run_a, sv.wall, side="left"))
    if w >= run_a.size:
        mfe = float(np.float32(np.max(f))) if f.size else 0.0
    else:
        mfe = float(np.float32(np.max(f[:w]))) if w > 0 else 0.0
    if w < run_a.size and mfe <= 0.0:
        return -sv.wall - sv.cost
    return mfe - sv.cost


def exit_at_value(sv, j, side, exit_sec):
    """Walled value of entry (j, side) exiting at `exit_sec` (EXIT_FORFEIT)."""
    vt, vm = sv.s.vt, sv.s.vm
    je = int(np.searchsorted(vt, exit_sec, side="right")) - 1
    if je <= j:
        return -sv.cost
    seg = vm[j:je + 1]
    entry = float(seg[0])
    adv = (entry - float(np.min(seg))) if side == 1 else \
          (float(np.max(seg)) - entry)
    if float(np.float32(adv * sv.mult)) >= sv.wall:           # GA-1 parity
        return -sv.wall - sv.cost
    return (float(seg[-1]) - entry) * side * sv.mult - sv.cost


# ================================================================ deciles ====
def decile_of(progress):
    """§11.A leg-progress decile.  progress == 1.0 belongs to decile 9."""
    if not np.isfinite(progress):
        return -1
    if progress < 0.0:
        return 0
    d = int(np.floor(progress * N_DECILES))
    return N_DECILES - 1 if d >= N_DECILES else d


def fam_names(mask):
    m = int(mask)
    got = [f for f in FAMILIES if m & FAM_BIT[f]]
    return "|".join(got) if got else "NONE"


# ============================================================== the pass =====
LEG_COLUMNS = [
    "asset", "trade_date", "year", "leg_idx", "leg_start_sec", "leg_end_sec",
    "span_sec", "direction", "leg_start_px", "leg_end_px", "travel_usd",
    "phase_start", "phase_end", "n_cand_any_side", "n_cand_same_side",
    "first_dec_sec", "first_progress", "first_delay_sec",
    "first_travel_remaining_usd", "first_frac_remaining", "first_family",
    "best_dec_sec", "best_progress", "best_travel_remaining_usd",
    "best_frac_remaining", "best_family",
    "ceil_leg_value_usd", "ceil_leg_entry_sec", "value_at_leg_start_usd",
    "value_at_first_cand_usd", "roster_best_value_usd",
    "best_cand_phase_close_sec", "beyond_phase_close_usd", "bucket",
    "forfeit_raw_usd",
] + ["d%d" % i for i in range(N_DECILES)] \
  + ["rem_d%d_usd" % i for i in range(N_DECILES)]

SESS_COLUMNS = [
    "asset", "trade_date", "year", "offer_usd", "cost_rt_usd", "wall_usd",
    "n_candidates", "n_legs_ge500", "ceil_close_usd", "roster_close_usd",
    "forfeit_usd", "forfeit_frac_of_ceil",
    "missed_usd", "late_usd", "exit_forfeit_usd", "occupancy_usd",
    "missed_raw_usd", "late_raw_usd", "exit_forfeit_raw_usd",
    "n_ceil_seats", "n_roster_seats",
    "ceil_peak_on_seats_usd", "roster_peak_on_seats_usd",
    "top_bucket", "top_leg_idx", "top_bucket_usd", "verdict",
]


def _clock(open_utc, sec):
    t = (int(open_utc) + int(sec)) % 86400
    return "%02d:%02d" % (t // 3600, (t % 3600) // 60)


def _session_audit(asset, trade_date, path, atr, wall, cost, cand, sane_thr,
                   mult, tick_px, want_plot):
    """One session: legs (A), forfeit (B), and optional plot payload (C)."""
    s = X.load_session(asset, trade_date, path)
    B7.apply(s, sane_thr if sane_thr is not None
             else [B7.SANE_CAP_USD] * X.N_PHASES)
    if s.vt.size < 2 or not np.isfinite(atr):
        return None
    vt, vm = s.vt, s.vm
    open_utc = int(s.meta["open_utc"])
    offer = float(vm.max() - vm.min()) * mult

    sv = SessionValues(s, mult, wall, cost)
    ceil_total, ceil_sel = sv.dp(sv.superset(tick_px, "FULL"))
    ceil_peak = sum(peak_exit_value(sv, j, side) for (j, side) in ceil_sel)

    # ---- ROSTER: the union-roster phase-close DP (b10's own machinery) ------
    r, idx = cand
    items = []
    cert = {}
    for i in idx:
        pk, cl = CC.certificates(r, i, wall, cost)
        cert[i] = (cl[0], pk[0], int(cl[2]))
        items.append((cl[1], cl[2], cl[0], int(r["dec_sec"][i]),
                      int(r["iid"][i]), i))
    roster_total, roster_sel = CC.dp_schedule(items)
    roster_peak = sum(cert[i][1] for i in roster_sel)

    # ---- A: every ANCHORED oracle leg >= $500 ------------------------------
    thr_px = X.round_half_up(X.ORACLE_RUNG * atr / mult, tick_px)
    legs = CD.oracle_legs(vt.tolist(), vm.tolist(), thr_px, mult, "ANCHORED")
    legs = [lg for lg in legs if lg[5] >= LEG_MIN_USD and lg[4] != 0]

    by_side = {1: [], -1: []}
    for i in idx:
        by_side[int(r["side"][i])].append(i)
    for k in by_side:
        by_side[k].sort(key=lambda i: int(r["dec_sec"][i]))

    leg_rows = []
    attributed = []
    leg_pc = {}
    for li, (s0, p0, s1, p1, d, travel) in enumerate(legs):
        span = int(s1 - s0)
        same = [i for i in by_side[d] if s0 <= int(r["dec_sec"][i]) <= s1]
        anyc = sum(1 for i in idx if s0 <= int(r["dec_sec"][i]) <= s1)
        j_lo = int(np.searchsorted(vt, s0, side="left"))
        j_hi = int(np.searchsorted(vt, s1, side="right"))
        vseg = sv.val[d][j_lo:j_hi]
        if vseg.size:
            jb = j_lo + int(np.argmax(vseg))
            v_leg = float(sv.val[d][jb])
        else:
            jb, v_leg = -1, float("nan")
        v_start = float(sv.val[d][j_lo]) if j_lo < sv.n else float("nan")

        dec = [int(r["dec_sec"][i]) for i in same]
        prog = [((x - s0) / span) if span > 0 else 0.0 for x in dec]
        rem = [(p1 - float(r["entry_mid"][i])) * d * mult for i in same]
        dcount = [0] * N_DECILES
        for pr in prog:
            k = decile_of(pr)
            if k >= 0:
                dcount[k] += 1
        rem_d = []
        for k in range(N_DECILES):
            bsec = s0 + int(round(span * k / float(N_DECILES)))
            jj = int(np.searchsorted(vt, bsec, side="left"))
            jj = min(jj, sv.n - 1)
            rem_d.append((p1 - float(vm[jj])) * d * mult)

        first_i = best_i = None
        if same:
            first_i = 0
            best_i = int(np.argmax(rem))
        v_first = cert[same[first_i]][0] if same else float("nan")
        r_best = max((cert[i][0] for i in same), default=float("nan"))
        bpc = cert[same[best_i]][2] if same else -1

        # the CC-M1-8-style companion: what the best candidate would have made
        # holding to the LEG END instead of its phase close ("known, priced")
        beyond = float("nan")
        if same:
            jb_c = same[best_i]
            jj = int(np.searchsorted(vt, int(r["dec_sec"][jb_c]), side="left"))
            if jj < sv.n:
                beyond = max(0.0, exit_at_value(sv, jj, d, s1) - cert[jb_c][0])

        bucket, raw = "COVERED", 0.0
        if not same:
            bucket, raw = "MISSED", max(0.0, v_leg if np.isfinite(v_leg) else 0.0)
        elif min(prog) > LATE_PROGRESS:
            bucket = "LATE"
            raw = max(0.0, (v_start if np.isfinite(v_start) else 0.0)
                      - (v_first if np.isfinite(v_first) else 0.0))
        elif bpc < s1:
            # the roster's own best entry is cut by a phase boundary the leg
            # runs past; the dollars are the leg's ceiling-minus-roster gap
            gap = max(0.0, (v_leg if np.isfinite(v_leg) else 0.0)
                      - (r_best if np.isfinite(r_best) else 0.0))
            if gap > 0:
                bucket, raw = "EXIT_FORFEIT", gap
        if raw > 0:
            attributed.append((bucket, raw, li))
        leg_pc[li] = bpc

        leg_rows.append(
            [asset, trade_date.isoformat(), trade_date.year, li, int(s0),
             int(s1), span, d, float(p0), float(p1), float(travel),
             X.PHASE_NAMES[int(s.phase_tag[int(s0)])],
             X.PHASE_NAMES[int(s.phase_tag[int(s1)])], anyc, len(same),
             (dec[first_i] if same else None),
             (prog[first_i] if same else float("nan")),
             ((dec[first_i] - s0) if same else None),
             (rem[first_i] if same else float("nan")),
             ((rem[first_i] / travel) if same and travel else float("nan")),
             (fam_names(r["fam_mask"][same[first_i]]) if same else ""),
             (dec[best_i] if same else None),
             (prog[best_i] if same else float("nan")),
             (rem[best_i] if same else float("nan")),
             ((rem[best_i] / travel) if same and travel else float("nan")),
             (fam_names(r["fam_mask"][same[best_i]]) if same else ""),
             v_leg, (int(vt[jb]) if jb >= 0 else None), v_start, v_first,
             r_best, (bpc if same else None), beyond, bucket, raw]
            + dcount + rem_d)

    # ---- B: greedy attribution, MISSED -> LATE -> EXIT -> OCCUPANCY --------
    forfeit = max(0.0, ceil_total - roster_total)
    alloc = {"MISSED": 0.0, "LATE": 0.0, "EXIT_FORFEIT": 0.0}
    raw_tot = {"MISSED": 0.0, "LATE": 0.0, "EXIT_FORFEIT": 0.0}
    for (b, amt, _li) in attributed:
        raw_tot[b] += amt
    rem_f = forfeit
    for b in ("MISSED", "LATE", "EXIT_FORFEIT"):
        take = min(raw_tot[b], rem_f)
        alloc[b] = take
        rem_f -= take
    occupancy = rem_f

    top = max(attributed, key=lambda x: (x[1], -x[2])) if attributed else None
    verdict = _verdict(asset, trade_date, s, open_utc, legs, top, ceil_total,
                       roster_total, occupancy, len(ceil_sel),
                       len(roster_sel), by_side, r, leg_pc)

    sess_row = [asset, trade_date.isoformat(), trade_date.year, offer, cost,
                wall, len(idx), len(legs), ceil_total, roster_total, forfeit,
                (forfeit / ceil_total) if ceil_total > 0 else float("nan"),
                alloc["MISSED"], alloc["LATE"], alloc["EXIT_FORFEIT"],
                occupancy, raw_tot["MISSED"], raw_tot["LATE"],
                raw_tot["EXIT_FORFEIT"], len(ceil_sel), len(roster_sel),
                ceil_peak, roster_peak,
                (top[0] if top else "NONE"), (top[2] if top else None),
                (top[1] if top else 0.0), verdict]

    plot = None
    if want_plot:
        piv = CC.zigzag_scan(vt.tolist(), vm.tolist(), [thr_px] * vt.size)
        plot = {
            "asset": asset, "date": trade_date.isoformat(),
            "open_utc": open_utc, "n": int(s.n),
            "vt": vt.astype(np.int32), "vm": vm.astype(np.float64),
            "piv_sec": np.array([p[1] for p in piv], dtype=np.int32),
            "piv_px": np.array([p[0] for p in piv], dtype=np.float64),
            "legs": np.array([[l[0], l[2], l[4], l[5]] for l in legs],
                             dtype=np.float64).reshape(-1, 4),
            "cand_sec": np.array([int(r["dec_sec"][i]) for i in idx],
                                 dtype=np.int32),
            "cand_px": np.array([float(r["entry_mid"][i]) for i in idx]),
            "cand_fam": np.array([int(r["fam_mask"][i]) for i in idx],
                                 dtype=np.int32),
            "cand_side": np.array([int(r["side"][i]) for i in idx],
                                  dtype=np.int8),
            "seat_roster": np.array(
                [[int(r["dec_sec"][i]), cert[i][2], cert[i][0],
                  int(r["side"][i])] for i in roster_sel],
                dtype=np.float64).reshape(-1, 4),
            "seat_ceil": np.array(
                [[int(vt[j]), sv.pc_of_idx[j], float(sv.val[sd][j]), sd]
                 for (j, sd) in ceil_sel], dtype=np.float64).reshape(-1, 4),
            "ceil": ceil_total, "roster": roster_total, "wall": wall,
            "cost": cost, "verdict": verdict,
        }
    return leg_rows, sess_row, plot


def _verdict(asset, trade_date, s, open_utc, legs, top, ceil_total,
             roster_total, occupancy, n_ceil, n_roster, by_side, r, leg_pc):
    """One SPECIFIC line per session for plots/INDEX.md (never generic)."""
    money = "CEIL $%s vs roster $%s" % (_m(ceil_total), _m(roster_total))
    if top is None or top[1] < 1.0:
        return ("roster reached %s (%.0f%%) with %d of %d ceiling seats — "
                "residual $%s is scheduler occupancy"
                % (money, 100.0 * roster_total / ceil_total
                   if ceil_total > 0 else 0.0, n_roster, n_ceil,
                   _m(occupancy)))
    bucket, amt, li = top
    s0, _p0, s1, _p1, d, travel = legs[li]
    ph = X.PHASE_NAMES[int(s.phase_tag[int(s0)])]
    dirw = "up" if d > 0 else "down"
    clock = _clock(open_utc, s0)
    if bucket == "MISSED":
        near = None
        for i in by_side[d]:
            dd = int(r["dec_sec"][i])
            gap = 0 if s0 <= dd <= s1 else min(abs(dd - s0), abs(dd - s1))
            near = gap if near is None else min(near, gap)
        gapt = ("no same-side candidate anywhere in the session" if near is None
                else ("nearest same-side candidate %ds outside the leg" % near
                      if near < 120 else
                      "nearest same-side candidate %dmin outside the leg"
                      % (near // 60)))
        return ("missed the %s %s %s leg $%s — %s; %s"
                % (clock, ph, dirw, _m(travel), gapt, money))
    if bucket == "LATE":
        same = [i for i in by_side[d]
                if s0 <= int(r["dec_sec"][i]) <= s1]
        first = int(r["dec_sec"][same[0]])
        pr = 100.0 * (first - s0) / max(1, s1 - s0)
        return ("late on the %s %s %s leg — first candidate at %.0f%% progress "
                "(+%dmin), $%s of phase-close value gone; %s"
                % (clock, ph, dirw, pr, (first - s0) // 60, _m(amt), money))
    return ("phase close at %s cut the %s %s %s leg %dmin before its %s end — "
            "$%s of ceiling left on the table; %s"
            % (_clock(open_utc, leg_pc.get(li, s1)), clock, ph, dirw,
               max(0, int(s1) - int(leg_pc.get(li, s1))) // 60,
               _clock(open_utc, s1), _m(amt), money))


def _m(v):
    try:
        return "{:,.0f}".format(float(v))
    except (TypeError, ValueError):
        return "?"


# ============================================================== driver =======
def _task(args):
    (asset, sess, wall, cost_map, sane_thr, plot_dates, cand_path) = args
    mult = C.ASSETS[asset]["mult"]
    tick_px = C.ASSETS[asset]["tick_px"]
    bars = X.load_bars(asset, M.M0_ROOT)
    z = np.load(cand_path, allow_pickle=False)
    r = {k: z[k] for k in z.files}
    z.close()
    d8s = r["date8"]
    by_date = {}
    for i in range(int(d8s.size)):
        by_date.setdefault(int(d8s[i]), []).append(i)
    legs, srows, plots = [], [], []
    for trade_date, path in sess:
        bar = bars.get(trade_date)
        atr = bar["ATR14_prev_usd"] if bar else float("nan")
        if not np.isfinite(atr):
            continue
        d8 = M.d8(trade_date)
        idx = by_date.get(d8, [])
        if not idx:
            continue
        cost = cost_map.get((asset, trade_date.isoformat()), float("nan"))
        if not np.isfinite(cost):
            cost = C.FEES_RT
        out = _session_audit(asset, trade_date, path, atr, wall, cost,
                             (r, idx), sane_thr.get(d8), mult, tick_px,
                             d8 in plot_dates)
        if out is None:
            continue
        legs.extend(out[0])
        srows.append(out[1])
        if out[2] is not None:
            plots.append(out[2])
    M.hb("genaudit %s: %d sessions, %d legs" % (asset, len(srows), len(legs)))
    return asset, legs, srows, plots


def _months(asset, chunks=8):
    sess = X.session_paths(asset, M.M0_ROOT)
    out = [[] for _ in range(chunks)]
    for i, x in enumerate(sess):
        out[i % chunks].append(x)
    return [c for c in out if c]


def run(assets, workers=4, plot_dates=None):
    fr = verify_freeze(assets)
    with open(os.path.join(M.M0_ROOT, "walls.json")) as fh:
        walls = json.load(fh)["walls"]
    cost_map = CA.session_cost_rt(M.M0_ROOT)
    tasks = []
    for a in assets:
        thr = B7.load_thresholds(a)
        pd_ = set(plot_dates.get(a, ())) if plot_dates else set()
        for chunk in _months(a):
            if plot_dates is not None:
                chunk = [(d, p) for (d, p) in chunk if M.d8(d) in pd_]
                if not chunk:
                    continue
            tasks.append((a, chunk, float(walls[a]["wall_usd"]), cost_map,
                          thr, pd_, fr[a]["path"]))
    M.hb("genaudit: %d tasks over %s" % (len(tasks), ",".join(assets)))
    if workers <= 1 or len(tasks) <= 1:
        res = [_task(t) for t in tasks]
    else:
        with mp.Pool(min(workers, len(tasks))) as pool:
            res = list(pool.map(_task, tasks, chunksize=1))
    legs, srows, plots = [], [], []
    for (_a, lg, sr, pl) in res:
        legs.extend(lg)
        srows.extend(sr)
        plots.extend(pl)
    legs.sort(key=lambda x: (x[0], x[1], x[3]))
    srows.sort(key=lambda x: (x[0], x[1]))
    plots.sort(key=lambda p: (p["asset"], p["date"]))
    return fr, legs, srows, plots


# ============================================================== rollups ======
def strata(srows, assets):
    """(year x offer quartile) -> the cell's MEDIAN-offer session.  Exact."""
    rows, chosen = [], {}
    for a in assets:
        by_year = {}
        for x in srows:
            if x[0] == a:
                by_year.setdefault(int(x[2]), []).append((float(x[3]), x[1]))
        for y in sorted(by_year):
            cell = sorted(by_year[y])
            n = len(cell)
            for q in range(4):
                lo = (n * q) // 4
                hi = (n * (q + 1)) // 4
                sub = cell[lo:hi]
                if not sub:
                    continue
                pick = sub[(len(sub) - 1) // 2]
                rows.append([a, y, q + 1, len(sub), sub[0][0], sub[-1][0],
                             pick[1], pick[0],
                             "%s_%s.png" % (a, pick[1].replace("-", ""))])
                chosen.setdefault(a, []).append(
                    int(pick[1][0:4]) * 10000 + int(pick[1][5:7]) * 100
                    + int(pick[1][8:10]))
    return rows, chosen


def forfeit_rollup(srows):
    agg = {}
    for x in srows:
        for era in M.eras_of(int(x[2])):
            k = (x[0], era)
            a = agg.setdefault(k, {c: [] for c in
                                   ("ceil", "roster", "forfeit", "missed",
                                    "late", "exit", "occ", "cpeak", "rpeak",
                                    "nseat")})
            a["ceil"].append(x[8])
            a["roster"].append(x[9])
            a["forfeit"].append(x[10])
            a["missed"].append(x[12])
            a["late"].append(x[13])
            a["exit"].append(x[14])
            a["occ"].append(x[15])
            a["cpeak"].append(x[21])
            a["rpeak"].append(x[22])
            a["nseat"].append(x[20])
    out = []
    for k in sorted(agg):
        a = agg[k]
        n = len(a["ceil"])
        tot_c = float(np.sum(a["ceil"]))
        tot_f = float(np.sum(a["forfeit"]))
        row = [k[0], k[1], n, M.med(a["ceil"]), M.mean(a["ceil"]),
               M.med(a["roster"]), M.mean(a["roster"]),
               (float(np.sum(a["roster"])) / tot_c) if tot_c else float("nan"),
               M.mean(a["forfeit"]),
               (tot_f / tot_c) if tot_c else float("nan")]
        for c in ("missed", "late", "exit", "occ"):
            row.append(M.mean(a[c]))
            row.append((float(np.sum(a[c])) / tot_f) if tot_f else float("nan"))
        row.extend([M.mean(a["cpeak"]), M.mean(a["rpeak"]),
                    M.med(a["nseat"])])
        out.append(row)
    return out


ROLLUP_COLUMNS = ["asset", "era", "n_sessions", "ceil_median", "ceil_mean",
                  "roster_median", "roster_mean", "roster_share_of_ceil",
                  "forfeit_mean", "forfeit_share_of_ceil",
                  "missed_mean", "missed_share", "late_mean", "late_share",
                  "exit_forfeit_mean", "exit_forfeit_share",
                  "occupancy_mean", "occupancy_share",
                  "ceil_peak_on_seats_mean", "roster_peak_on_seats_mean",
                  "n_roster_seats_median"]


def decile_rollup(legs):
    LI = {c: i for i, c in enumerate(LEG_COLUMNS)}
    agg = {}
    for x in legs:
        for era in M.eras_of(int(x[LI["year"]])):
            k = (x[0], era)
            a = agg.setdefault(k, {"n": 0, "c": [0] * N_DECILES,
                                   "r": [[] for _ in range(N_DECILES)],
                                   "legs_with": [0] * N_DECILES})
            a["n"] += 1
            for d in range(N_DECILES):
                c = int(x[LI["d%d" % d]])
                a["c"][d] += c
                if c:
                    a["legs_with"][d] += 1
                a["r"][d].append(float(x[LI["rem_d%d_usd" % d]]))
    out = []
    for k in sorted(agg):
        a = agg[k]
        tot = sum(a["c"])
        for d in range(N_DECILES):
            out.append([k[0], k[1], d, a["n"], a["c"][d],
                        a["c"][d] / a["n"] if a["n"] else float("nan"),
                        (a["c"][d] / tot) if tot else float("nan"),
                        a["legs_with"][d] / a["n"] if a["n"] else float("nan"),
                        M.med(a["r"][d]), M.mean(a["r"][d])])
    return out


def timing_rollup(legs):
    LI = {c: i for i, c in enumerate(LEG_COLUMNS)}
    agg = {}
    for x in legs:
        for era in M.eras_of(int(x[LI["year"]])):
            a = agg.setdefault((x[0], era),
                               {"n": 0, "cov": 0, "tr": [], "fr": [],
                                "pg": [], "dl": [], "btr": [], "bfr": [],
                                "trav": []})
            a["n"] += 1
            a["trav"].append(float(x[LI["travel_usd"]]))
            if x[LI["n_cand_same_side"]]:
                a["cov"] += 1
                a["tr"].append(float(x[LI["first_travel_remaining_usd"]]))
                a["fr"].append(float(x[LI["first_frac_remaining"]]))
                a["pg"].append(float(x[LI["first_progress"]]))
                a["dl"].append(float(x[LI["first_delay_sec"]]))
                a["btr"].append(float(x[LI["best_travel_remaining_usd"]]))
                a["bfr"].append(float(x[LI["best_frac_remaining"]]))
    out = []
    for k in sorted(agg):
        a = agg[k]
        out.append([k[0], k[1], a["n"], a["cov"],
                    a["cov"] / a["n"] if a["n"] else float("nan"),
                    M.med(a["trav"]),
                    M.pct(a["tr"], 25), M.med(a["tr"]), M.pct(a["tr"], 75),
                    M.med(a["fr"]), M.med(a["pg"]), M.med(a["dl"]) / 60.0,
                    M.med(a["btr"]), M.med(a["bfr"])])
    return out


TIMING_COLUMNS = ["asset", "era", "n_legs", "n_legs_with_same_side_cand",
                  "leg_coverage", "travel_median_usd",
                  "first_remaining_p25_usd", "first_remaining_median_usd",
                  "first_remaining_p75_usd", "first_frac_remaining_median",
                  "first_progress_median", "first_delay_median_min",
                  "best_remaining_median_usd", "best_frac_remaining_median"]

DECILE_COLUMNS = ["asset", "era", "decile", "n_legs", "n_candidates",
                  "cands_per_leg", "share_of_candidates",
                  "frac_legs_with_candidate",
                  "remaining_at_decile_start_median_usd",
                  "remaining_at_decile_start_mean_usd"]


# ================================================================== main =====
def main():
    M.verify_spec()
    M.verify_spec_m1b()
    assets = [a for a in sys.argv[1:] if a in M.ASSET_ORDER] or \
        list(M.ASSET_ORDER)
    phash = C.params_hash(PARAMS)

    fr, legs, srows, _ = run(assets, workers=4)
    strat, chosen = strata(srows, assets)
    M.hb("genaudit: pass 2 (plot payloads) for %d sessions"
         % sum(len(v) for v in chosen.values()))
    _fr2, _l2, _s2, plots = run(assets, workers=min(4, len(assets)),
                                plot_dates=chosen)

    M.write_tsv(M.out_path(OUT_DIR, "leg_capture_profile.tsv"), SECTION, phash,
                LEG_COLUMNS, legs,
                extra=["§11.A: EVERY ANCHORED 0.25xATR leg >= $%.0f on SANE "
                       "mids (not the m0 top-2/$1,500 gate set)" % LEG_MIN_USD,
                       "travel_remaining = (leg_end_px - entry_mid) x "
                       "direction x mult (mid-to-mid, gross)",
                       "rem_dK_usd = travel still ahead at the START of "
                       "progress decile K (the leg-middle density evidence)"])
    M.write_tsv(M.out_path(OUT_DIR, "forfeit_sessions.tsv"), SECTION, phash,
                SESS_COLUMNS, srows,
                extra=["§11.B per-session forfeit decomposition; the STANDING "
                       "regression baseline",
                       "CC-M1-8: *_peak_on_seats_usd is the peak-exit "
                       "certificate of the same seated entries"])
    M.write_tsv(M.out_path(OUT_DIR, "forfeit_rollup.tsv"), SECTION, phash,
                ROLLUP_COLUMNS, forfeit_rollup(srows),
                extra=["shares are of the era's TOTAL forfeit dollars"])
    M.write_tsv(M.out_path(OUT_DIR, "leg_progress_deciles.tsv"), SECTION,
                phash, DECILE_COLUMNS, decile_rollup(legs),
                extra=["§11.A progress-decile matrix + the dollars still ahead "
                       "at each decile boundary (leg-middle density verdict)"])
    M.write_tsv(M.out_path(OUT_DIR, "timing_loss.tsv"), SECTION, phash,
                TIMING_COLUMNS, timing_rollup(legs),
                extra=["entry-timing loss distributions (§11.A)"])
    M.write_tsv(M.out_path(OUT_DIR, "strata.tsv"), SECTION, phash,
                ["asset", "year", "offer_quartile", "n_sessions_in_cell",
                 "offer_lo_usd", "offer_hi_usd", "trade_date", "offer_usd",
                 "plot"], strat,
                extra=["deterministic by construction: the cell's MEDIAN-offer "
                       "session (seed %d declared, never consulted)"
                       % STRATA_SEED])

    import plot_genaudit as P
    n_png, backend = P.render_all(plots, M.out_path(OUT_DIR, "plots"))
    P.write_index(plots, srows, M.out_path(OUT_DIR, "plots"), backend)

    M.write_json(M.out_path(OUT_DIR, "genaudit_env.json"),
                 {"spec_section": SECTION, "env": M.env_receipt(PARAMS),
                  "freeze": fr, "n_legs": len(legs), "n_sessions": len(srows),
                  "n_plots": n_png, "plot_backend": backend,
                  "assets": assets})
    M.hb("genaudit: %d legs, %d sessions, %d plots (%s)"
         % (len(legs), len(srows), n_png, backend))
    return 0


if __name__ == "__main__":
    sys.exit(main())
