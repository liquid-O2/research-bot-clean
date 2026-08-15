#!/usr/bin/python3
"""PORT M2 — THE HORIZON-ALIGNMENT PASS (S1): price the UN-AMPUTATED object.

THE DEFECT, confirmed file:line before this module was written
  * the champion's TARGET is `retg|e30|SESS_CLOSE` (m3_matrix.py:37 / :1445 —
    `net = f_sess_close - cost`, `mfe = mfe_unwalled`);
  * the REPLAY CASHES AT PHASE CLOSE (m3_walk.py:218-219 reads
    `cert_close_usd` / `exit_close_sec`; m2_delay.py:239 cuts the certificate at
    the phase boundary).
  The model has been trained to rank by session-close value and paid
  phase-close value under EVERY arm this campaign has ever measured.  Every
  null and the 0.40-0.44 capture plateau were measured against a truncated
  denominator.

WHAT THIS MODULE MEASURES (and nothing else)
  The SAME entries, the SAME schedule, the SAME $900 wall — three EXIT
  HORIZONS:
      PHASE  the incumbent: ride to the phase close of the entry's own phase;
      NEXT   ride through it to the NEXT phase boundary;
      SESS   ride to the session close (`s.n - 1`, the roster's own
             `sess_close_sec`, c_c_roster.py:294) — SAME SESSION ONLY, no
             overnight hold.
  The $900 wall stays LIVE for the whole of the extended hold: a leg whose
  adverse skeleton reaches $900 at or before the horizon pays -900 - cost at
  the wall second, exactly as `m2_delay._close_cert` does at the phase close.

WHERE EVERY NUMBER COMES FROM (D-006 — no second version of anything)
  legs            `m2_delay._leg`, IMPORTED and called.  The prefix-maxima
                  skeleton with its float32 storage of the adverse records —
                  the arithmetic that reproduced the committed roster EXACTLY
                  at D=0 on 74,817 E6 episodes and again on all 1,399,374
                  candidates (`newobj.verify_d0`).
  certificates    `m2_delay._close_cert`, IMPORTED and called, with the exit
                  horizon as its `pc` argument.  At `pc = phase_close_sec` it
                  IS the committed certificate — which is the red-first test
                  this module fires before it reports anything.
  phase bounds    `census_common.next_phase_boundary`, applied twice for NEXT.
  the seating     `newobj.replay_delayed` VERBATIM, with the horizon's
                  certificate and exit second substituted into the tensor it
                  already consumes.  One position per (asset, session),
                  chronological, forfeit-on-occupied, refuse-on-refused.
  the armour      `stacked_final.apply_stop(..., "STOP_WALL1")` — the adopted
                  first-wall stop.  ARMED rows are primary.
  the arm         the DEPLOYED folded members `curriculum_scores/FOLD_<era>_
                  <seed>.npy` (fold_stack.py: per-era strictness k, W_VOLMATCH
                  weighting, monotone constraints, promoted HP) — 5 seeds,
                  mean +/- sd, never a single fit.
  the ceiling     the entry-foresight ceiling AT THAT HORIZON: the same
                  committed per-cell schedule, filled by the horizon's own TRUE
                  certificate (`confidence.ceilings`' construction, re-fired
                  per horizon instead of read from cache).
  day types       the guarded regime forecaster's DAY-START call, read out of
                  the matrix: for each (asset, day) the row with the smallest
                  decision second supplies `fc_p_expansion` / `fc_available`.
                  The trend cut's threshold is a quantile of the TRAINING
                  BLOCK's day-start distribution (strictly prior eras), so no
                  eval-era statistic enters the cut.

LAWS OBSERVED
  5-seed distributions; promotion = delta_minus_sd > 0 vs the incumbent
  horizon; binding eras (E5/E6/E7) first; armored rows primary; aim columns
  (aim_08ceiling / gap_to_aim) and capture on every row; a zero-row table is a
  REFUSAL, never a silent pass; E8 is quarantined and 2025-H2 is not in the
  matrix at all.

CLI
  horizon.py --paths [--workers 8]   the three-horizon certificate tensor
  horizon.py --verify                red-first: PHASE == the committed roster
  horizon.py --table                 HORIZON_ALIGNMENT.tsv (S1, the headline)
"""
import argparse
import json
import os
import sys
import time

import numpy as np

_H = os.path.dirname(os.path.abspath(__file__))
for _p in (_H, "/workspace/engine/port_m2/seqtest", "/workspace/engine/port_m0",
           "/workspace/engine/port_m1", "/workspace/engine/port_m3",
           "/workspace/artifacts/cache/pylibs"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import newobj as N                        # noqa: E402
import m2_delay as MD                     # noqa: E402
import m2_common as MC                    # noqa: E402
import census_common as X                 # noqa: E402
import common as C                        # noqa: E402
import assemble as A                      # noqa: E402

VERSION = "PORT-M2-HORIZON-V1"
OUT_ROOT = os.path.join(MC.M2_ROOT, "horizon")
BINDING = ("E5", "E6", "E7")
ERAS = BINDING + ("E3", "E4")
SEEDS = (0, 1, 2, 3, 4)
HORIZONS = ("PHASE", "NEXT", "SESS")
ASSETS = ("ALL", "SI", "HG", "NKD")
FLOOR = 2000.0
AIM_FRAC = 0.80

# per-horizon fields, in the order they are stored
HF = ("cert", "exit_sec", "walled", "wall_hit")
SHARED = ("entry_sec", "feasible", "pc_sec", "npc_sec", "sc_sec")
COLS = tuple(SHARED) + tuple("%s_%s" % (h, f) for h in HORIZONS for f in HF)
CIDX = {c: i for i, c in enumerate(COLS)}


def hb(msg):
    sys.stderr.write("[horizon %s] %s\n" % (time.strftime("%H:%M:%S"), msg))
    sys.stderr.flush()


class HorizonRefusal(RuntimeError):
    """A guard fired.  Never downgraded, never silently filtered."""


# ================================================== STAGE 1: THE TENSOR =====
def _one(job):
    """Every candidate of ONE (asset, date8), at all three exit horizons."""
    asset, d8, rows = job
    try:
        sess = A.load_session(asset, int(d8))
        s = sess["s"]
        mult = float(C.ASSETS[asset]["mult"])
        sc_sec = s.n - 1                       # c_c_roster.py:294, verbatim
        out = []
        for (i, t, side, cost) in rows:
            t, side, cost = int(t), int(side), float(cost)
            r = np.full(len(COLS), np.nan, dtype=np.float64)
            r[CIDX["feasible"]] = 0.0
            r[CIDX["entry_sec"]] = -1.0
            e = MD._first_sane(s, t)
            pc0 = X.next_phase_boundary(s, t)
            pc1 = X.next_phase_boundary(s, pc0)
            r[CIDX["pc_sec"]] = float(pc0)
            r[CIDX["npc_sec"]] = float(pc1)
            r[CIDX["sc_sec"]] = float(sc_sec)
            if e >= 0 and e < pc0:
                entry_mid = float(s.mid[e])
                vt, f, at, av = MD._leg(s, e, entry_mid, side, mult)
                r[CIDX["feasible"]] = 1.0
                r[CIDX["entry_sec"]] = float(e)
                for h, pc in (("PHASE", pc0), ("NEXT", pc1), ("SESS", sc_sec)):
                    val, xs, wl, ev = MD._close_cert(vt, f, at, av, pc, cost)
                    r[CIDX["%s_cert" % h]] = val
                    r[CIDX["%s_exit_sec" % h]] = float(xs)
                    r[CIDX["%s_walled" % h]] = wl
                    r[CIDX["%s_wall_hit" % h]] = ev
            out.append((int(i), r))
        return (asset, int(d8), out, None)
    except Exception as exc:                              # noqa: BLE001
        return (asset, int(d8), [], "%s: %s" % (type(exc).__name__, exc))


def build(workers=8, out_dir=None, limit_days=None):
    import multiprocessing as mp
    out_dir = out_dir or OUT_ROOT
    os.makedirs(out_dir, exist_ok=True)
    D = N.matrix()
    n = int(D["d8"].size)
    joblist = N._jobs_from_matrix(D)
    if limit_days:
        joblist = joblist[:limit_days]
    T = np.full((n, len(COLS)), np.nan, dtype=np.float64)
    t0, errs, done = time.time(), [], 0
    hb("build: %d sessions, %d candidates, horizons=%s, workers=%d"
       % (len(joblist), n, list(HORIZONS), workers))
    with mp.Pool(processes=int(workers)) as pool:
        for k, (asset, d8, rows, err) in enumerate(
                pool.imap_unordered(_one, joblist, chunksize=1), start=1):
            if err:
                errs.append("%s %d %s" % (asset, d8, err))
            for i, r in rows:
                T[i] = r
                done += 1
            if k % 200 == 0 or k == len(joblist):
                el = time.time() - t0
                hb("build %d/%d sessions %.0fs eta %.0fs filled=%d errs=%d"
                   % (k, len(joblist), el, el / k * (len(joblist) - k), done,
                      len(errs)))
    if done == 0:
        raise HorizonRefusal("ZERO rows filled — the build produced nothing")
    rec = {"version": VERSION, "n_candidates": n, "n_sessions": len(joblist),
           "n_rows_filled": int(done), "columns": list(COLS),
           "horizons": list(HORIZONS), "wall_usd": MD.WALL_USD,
           "sane_search_cap_sec": MD.SANE_SEARCH_CAP,
           "arithmetic": "m2_delay._leg + m2_delay._close_cert (imported)",
           "sess_close": "s.n - 1 (c_c_roster sess_close_sec)",
           "errors": errs[:50], "n_errors": len(errs),
           "secs": round(time.time() - t0, 1)}
    np.savez(os.path.join(out_dir, "horizons.npz"),
             cols=np.array(COLS), T=T)
    with open(os.path.join(out_dir, "horizons.receipt.json"), "w") as fh:
        json.dump(rec, fh, indent=1, sort_keys=True)
    hb("build: %d/%d rows filled, %d session errors, %.0fs"
       % (done, n, len(errs), rec["secs"]))
    if errs:
        raise HorizonRefusal("%d session errors — first: %s"
                             % (len(errs), errs[0]))
    return T


_T = {}


def load(out_dir=None):
    if "T" in _T:
        return _T["T"]
    p = os.path.join(out_dir or OUT_ROOT, "horizons.npz")
    if not os.path.exists(p):
        raise HorizonRefusal("no horizon tensor at %s — run --paths" % p)
    z = np.load(p, allow_pickle=False)
    cols = [str(x) for x in z["cols"].tolist()]
    if tuple(cols) != tuple(COLS):
        raise HorizonRefusal("tensor column mismatch: %s" % cols)
    _T["T"] = z["T"]
    z.close()
    return _T["T"]


# ---------------------------------------------------------- RED FIRST ------
def verify(out_dir=None, tol=0.0):
    """The PHASE horizon MUST reproduce the committed matrix exactly, and the
    PHASE replay must reproduce `m3_walk.replay_rows` seat-for-seat."""
    D = N.matrix()
    T = load(out_dir)
    ok = D["cert_refused"] == 0
    feas = T[:, CIDX["feasible"]] > 0.5
    m = ok & feas & np.isfinite(T[:, CIDX["PHASE_cert"]])
    dv = np.abs(T[m, CIDX["PHASE_cert"]] - D["cert_close_usd"][m])
    de = np.abs(T[m, CIDX["PHASE_exit_sec"]] - D["exit_close_sec"][m])
    dw = np.abs(T[m, CIDX["PHASE_wall_hit"]] - D["walled"][m])
    ent = np.abs(T[m, CIDX["entry_sec"]] - D["dec_sec"][m])
    rec = {"version": VERSION, "n_candidates": int(D["d8"].size),
           "n_compared": int(m.sum()), "n_infeasible": int((~feas).sum()),
           "n_cert_refused": int((~ok).sum()),
           "max_abs_cert_diff": float(dv.max()) if dv.size else 0.0,
           "max_abs_exit_diff": float(de.max()) if de.size else 0.0,
           "max_abs_wall_diff": float(dw.max()) if dw.size else 0.0,
           "n_entry_shifted": int((ent > 0).sum()),
           "n_cert_mismatch": int((dv > tol).sum()),
           "n_exit_mismatch": int((de > tol).sum()),
           "n_wall_mismatch": int((dw > tol).sum())}
    hb("verify: %d compared, cert/exit/wall mismatches %d/%d/%d "
       "(max |dcert| %.10g)"
       % (rec["n_compared"], rec["n_cert_mismatch"], rec["n_exit_mismatch"],
          rec["n_wall_mismatch"], rec["max_abs_cert_diff"]))
    if rec["n_cert_mismatch"] or rec["n_exit_mismatch"] \
            or rec["n_wall_mismatch"]:
        raise HorizonRefusal(
            "PHASE REPRODUCTION FAILED (%d cert / %d exit / %d wall) — the "
            "horizon arithmetic is not the roster's and NOTHING downstream "
            "may be believed"
            % (rec["n_cert_mismatch"], rec["n_exit_mismatch"],
               rec["n_wall_mismatch"]))
    # ... and the seat-for-seat replay proof, on a real score.
    import m3_walk as W
    era = "E7"
    sc = np.load(os.path.join(_sdir(), "FOLD_%s_0.npy" % era)).astype(np.float64)
    ev = N.deployable(D, N.era_rows(D, era))
    take = W.topn_takes(D, sc, ev, N.committed_policy()[era][1],
                        deployable=True, unit="cell")
    ref = W.replay_rows(D, take)
    mine = N.replay_delayed(D, [(int(i), 0) for i in take.tolist()],
                            P=tensor_as_P("PHASE"))
    if len(ref) != len(mine):
        raise HorizonRefusal("replay session count %d != %d"
                             % (len(ref), len(mine)))
    dmax, nseat = 0.0, 0
    for a, b in zip(ref, mine):
        if a["session"] != b["session"]:
            raise HorizonRefusal("replay session order mismatch")
        if [x for x in a["seats"]] != [x[0] for x in b["seats"]]:
            raise HorizonRefusal("replay SEAT mismatch on %s" % a["session"])
        dmax = max(dmax, abs(a["realised"] - b["realised"]))
        nseat += len(a["seats"])
    if dmax > 0.0:
        raise HorizonRefusal("replay realised mismatch %.10g" % dmax)
    rec["replay_sessions"] = len(ref)
    rec["replay_seats"] = nseat
    rec["replay_max_abs_diff"] = dmax
    hb("verify: replay(PHASE) == m3_walk.replay_rows — %d sessions, %d seats, "
       "max |diff| %.10g" % (len(ref), nseat, dmax))
    with open(os.path.join(out_dir or OUT_ROOT, "verify.receipt.json"),
              "w") as fh:
        json.dump(rec, fh, indent=1, sort_keys=True)
    return rec


# ================================================ the horizon as a tensor ===
_P = {}


def tensor_as_P(h):
    """The horizon dressed as the (delay -> field matrix) tensor that
    `newobj.replay_delayed` already consumes, so the SEATING CODE IS THE SAME
    FUNCTION and only the certificate/exit second change."""
    if h in _P:
        return _P[h]
    T = load()
    n = T.shape[0]
    M = np.full((n, len(N.FIELDS)), np.nan, dtype=np.float64)
    M[:, N.FIDX["entry_sec"]] = T[:, CIDX["entry_sec"]]
    M[:, N.FIDX["feasible"]] = T[:, CIDX["feasible"]]
    M[:, N.FIDX["cert_close"]] = T[:, CIDX["%s_cert" % h]]
    M[:, N.FIDX["exit_sec"]] = T[:, CIDX["%s_exit_sec" % h]]
    M[:, N.FIDX["walled"]] = T[:, CIDX["%s_walled" % h]]
    M[:, N.FIDX["wall_hit"]] = T[:, CIDX["%s_wall_hit" % h]]
    _P[h] = {0: M}
    return _P[h]


def true_value(h, D):
    """The horizon's TRUE certificate as a value column (the foresight input);
    NaN wherever no seat exists or the certificate was refused."""
    T = load()
    v = T[:, CIDX["%s_cert" % h]].copy()
    v[T[:, CIDX["feasible"]] <= 0.5] = np.nan
    v[D["cert_refused"] != 0] = np.nan
    return v


def _sdir():
    import curriculum as CU
    return CU._sdir()


# ======================================================= the day-type cuts ==
def day_start_fc(D):
    """(session key -> day-start p_expansion, availability).  CAUSAL: the row
    with the smallest decision second of each (asset, day) — the first anchor
    the day offers."""
    j = D["names"].index("fc_p_expansion")
    k = D["names"].index("fc_available")
    key = D["session"]
    order = np.lexsort((D["dec_sec"], key))
    ko = key[order]
    starts = [0] + (np.flatnonzero(ko[1:] != ko[:-1]) + 1).tolist()
    first = order[np.asarray(starts, dtype=np.int64)]
    p = D["X"][first, j].astype(np.float64)
    av = D["X"][first, k].astype(np.float64)
    return dict(zip(ko[np.asarray(starts, dtype=np.int64)].tolist(),
                    zip(p.tolist(), av.tolist()))), first


def trend_days(D, era, q):
    """The set of session keys of `era` whose DAY-START forecaster call sits in
    the top (1-q) of the TRAINING BLOCK's day-start distribution.

    The threshold is a quantile of STRICTLY PRIOR eras only, so no eval-era
    statistic enters the cut — the call is available at the day's start and the
    bar it is measured against was fixed before the era began.
    """
    import st_common as SC
    fc, first = day_start_fc(D)
    ei = SC.ERA_IDX[era]
    e_first = D["era_idx"][first]
    s_first = D["session"][first]
    prior = np.array([fc[str(s)][0] for s, e in zip(s_first.tolist(),
                                                    e_first.tolist())
                      if e < ei and e >= 0 and fc[str(s)][1] > 0.5])
    prior = prior[np.isfinite(prior)]
    if prior.size < 30:
        return None, None
    thr = float(np.quantile(prior, q))
    keep = set()
    for s, e in zip(s_first.tolist(), e_first.tolist()):
        if e != ei:
            continue
        pv, av = fc[str(s)]
        if av > 0.5 and np.isfinite(pv) and pv >= thr:
            keep.add(str(s))
    return keep, thr


# ============================================================== the table ===
def _sub(rows, keys):
    return [r for r in rows if r["session"] in keys] if keys is not None \
        else rows


def _asset_keys(rows, asset):
    if asset == "ALL":
        return None
    return set(r["session"] for r in rows
               if r["session"].split("|")[0] == asset)


def _read(rows):
    D = N.matrix()
    return N.read_rows(D, rows) if rows else {"n_sessions": 0}


def run_table(eras=ERAS, out_dir=None):
    import stacked_final as SF
    D = N.matrix()
    load(out_dir)
    hb("table: %d eras x %d horizons x {ALL, TREND_T3, TREND_T10} day sets"
       % (len(eras), len(HORIZONS)))
    # --- the replays, computed ONCE per (era, horizon) over all days --------
    # sessions do not interact, so every asset/day-set cut below is a FILTER on
    # the per-session rows rather than a second replay.
    R = {}
    for era in eras:
        ev = N.deployable(D, N.era_rows(D, era))
        n_ = N.committed_policy()[era][1]
        for h in HORIZONS:
            Ph = tensor_as_P(h)
            V = {0: true_value(h, D)}
            ceil_rows = N.replay_delayed(
                D, N.top_per_cell_joint(D, ev, V, n_, (0,)), P=Ph,
                val_by_delay=V)
            R[(era, h, "CEIL")] = ceil_rows
            for sd in SEEDS:
                fp = os.path.join(_sdir(), "FOLD_%s_%d.npy" % (era, sd))
                if not os.path.exists(fp):
                    raise HorizonRefusal("missing folded member %s" % fp)
                sc = np.load(fp).astype(np.float64)
                raw = N.replay_delayed(
                    D, N.top_per_cell_score(D, ev, sc, n_), P=Ph)
                R[(era, h, "RAW", sd)] = raw
                R[(era, h, "ARM", sd)] = SF.apply_stop(D, raw, "STOP_WALL1")
            hb("replayed %s %s (%d sessions, ceiling seats %d)"
               % (era, h, len(ceil_rows),
                  sum(len(r["seats"]) for r in ceil_rows)))
    # --- the day-set definitions -------------------------------------------
    DAYSETS = [("ALL_DAYS", None, 0.0)]
    thrs = {}
    for q, tag in ((2.0 / 3.0, "TREND_T3"), (0.90, "TREND_T10")):
        for era in eras:
            keep, thr = trend_days(D, era, q)
            thrs[(tag, era)] = (keep, thr)
        DAYSETS.append((tag, q, None))
    rows = []
    for era in eras:
        crit = "BINDING" if era in BINDING else "context"
        for dtag, q, _z in DAYSETS:
            if dtag == "ALL_DAYS":
                dkeys, thr = None, ""
            else:
                dkeys, thr = thrs[(dtag, era)]
                if dkeys is None or len(dkeys) < 20:
                    continue
                thr = N._r(thr, 4)
            for asset in ASSETS:
                base = R[(era, "PHASE", "ARM", SEEDS[0])]
                akeys = _asset_keys(base, asset)
                keys = None
                if akeys is not None and dkeys is not None:
                    keys = akeys & dkeys
                elif akeys is not None:
                    keys = akeys
                elif dkeys is not None:
                    keys = dkeys
                inc = None
                for h in HORIZONS:
                    cr = _read(_sub(R[(era, h, "CEIL")], keys))
                    ceil = cr.get("usd_per_session")
                    arm, rawv, nse = [], [], []
                    for sd in SEEDS:
                        a = _read(_sub(R[(era, h, "ARM", sd)], keys))
                        b = _read(_sub(R[(era, h, "RAW", sd)], keys))
                        if a.get("usd_per_session") is None:
                            continue
                        arm.append(a["usd_per_session"])
                        rawv.append(b["usd_per_session"])
                        nse.append(a["n_seated"] / max(a["n_sessions"], 1))
                    if not arm:
                        continue
                    A_ = np.asarray(arm, dtype=np.float64)
                    Rw = np.asarray(rawv, dtype=np.float64)
                    if h == "PHASE":
                        inc = A_
                    d = A_.mean() - inc.mean() if inc is not None else None
                    dms = (d - A_.std()) if d is not None else None
                    aim = AIM_FRAC * ceil if ceil else None
                    cap = (A_.mean() / ceil) if ceil else None
                    rows.append([
                        era, crit, asset, dtag, thr, h, int(cr["n_sessions"]),
                        int(A_.size), N._r(A_.mean()), N._r(A_.std()),
                        N._r(Rw.mean()), N._r(Rw.std()),
                        N._r(float(np.mean(nse)), 3),
                        N._r(ceil), N._r(cap, 4), N._r(aim),
                        N._r(A_.mean() - aim) if aim else "",
                        "1" if (ceil and ceil >= FLOOR / AIM_FRAC) else "0",
                        N._r(A_.mean() - FLOOR),
                        N._r(d) if d is not None else "",
                        N._r(dms) if dms is not None else "",
                        "YES" if (dms is not None and dms > 0) else "no"])
    if not rows:
        raise HorizonRefusal(
            "HORIZON_ALIGNMENT produced ZERO rows — a null prints rows, so "
            "this is a FAILURE, not a result")
    N.write_tsv(
        "HORIZON_ALIGNMENT.tsv",
        ["era", "criterion", "asset", "day_set", "trend_thr", "horizon",
         "n_sessions", "n_seeds", "armed_mean", "armed_sd", "raw_mean",
         "raw_sd", "seats_per_session", "foresight_ceiling", "armed_capture",
         "aim_08ceiling", "gap_to_aim", "ceiling_supports_floor",
         "gap_to_floor_2000", "delta_vs_phase", "delta_minus_sd",
         "promotes"], rows,
        extra=[
            "S1 — THE HORIZON-ALIGNMENT PASS.  The champion's TARGET is "
            "retg|e30|SESS_CLOSE (m3_matrix.py:37,1445) while the replay "
            "CASHES AT PHASE CLOSE (m3_walk.py:218-219, m2_delay.py:239).  "
            "This table prices the object at the three exit horizons the "
            "mismatch spans, with the entries, the schedule and the $900 wall "
            "unchanged.",
            "THE WALL STAYS LIVE THROUGH THE EXTENDED HOLD: a leg whose "
            "adverse skeleton reaches $900 at or before the horizon pays "
            "-900 - cost at the wall second (m2_delay._close_cert, imported).",
            "SAME SESSION ONLY: SESS = s.n - 1, the roster's own "
            "sess_close_sec (c_c_roster.py:294).  No overnight hold exists in "
            "this table.",
            "RED FIRST: the PHASE column reproduces the committed matrix "
            "certificate/exit/wall EXACTLY and its replay reproduces "
            "m3_walk.replay_rows seat-for-seat (verify.receipt.json).",
            "ARM = the deployed folded members (FOLD_<era>_<seed>: per-era "
            "strictness k, W_VOLMATCH, monotone, promoted HP) with the adopted "
            "FIRST-WALL STOP.  5 seeds, mean +/- sd.  PROMOTION = "
            "delta_minus_sd > 0 against the PHASE incumbent on the same days.",
            "TREND_T3 / TREND_T10 = days whose DAY-START forecaster call "
            "(fc_p_expansion at the day's first anchor) sits in the top third "
            "/ top decile of the TRAINING BLOCK's day-start distribution.  The "
            "threshold uses strictly prior eras only.",
            "aim_08ceiling = 0.80 x the horizon's own foresight ceiling; "
            "ceiling_supports_floor = the ceiling can carry the $2,000 floor "
            "at 0.8 capture."])
    hb("HORIZON_ALIGNMENT.tsv: %d rows" % len(rows))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--paths", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--table", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit-days", type=int, default=None)
    a = ap.parse_args()
    did = False
    if a.paths:
        build(workers=a.workers, limit_days=a.limit_days)
        did = True
    if a.verify:
        verify()
        did = True
    if a.table:
        run_table()
        did = True
    if not did:
        ap.print_help()


if __name__ == "__main__":
    main()
