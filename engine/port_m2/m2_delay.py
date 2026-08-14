#!/usr/bin/python3
"""PORT M2 — ENTRY-DELAY DECIDABILITY + POST-ENTRY DIVERGENCE.

THE QUESTION (the user's own words)
  "I'm fine taking a candle or two after the extreme has been confirmed — we
   don't need to predict extremes."

  Three independent extractors (the 225 hand features, a GBT on them, and Opus
  reading the raw tape) all fail at the CONFIRMATION SECOND: the pre-entry tape
  does not separate the winner leg from the loser leg (best pair accuracy
  0.5746 vs the 0.73 that $1,000/trade needs).  This module asks whether the
  tape separates LATER, and how much money is left when it does.

  1. REMAINING-MOVE CURVE   enter at t+D instead of t: what is left?
  2. DECIDABILITY CURVE     with [t, t+D] in hand, how well can the winner leg
                            be called?
  3. POST-ENTRY DIVERGENCE  entered at t, when can a loser be cut, and what
                            does the scratch cost?
  4. the joint table: the money at the crossing.

NON-CAUSAL-BY-DESIGN, exactly as `info_ceiling`: the pair universe is defined
by outcomes and the fits are k-fold WITHIN E6.  Nothing here is a deployable
policy and nothing here may be imported by a reading-path module.

WHERE EVERY NUMBER COMES FROM (no second version of anything — D-006)
  episodes / views     artifacts/cache/port/m2/info_ceiling/episodes.npz
                       (`info_ceiling.build_episodes`, 74,817 E6 episodes x 185
                       view columns) + seq.npz (the 40 pre-window seq cues)
  pairs                `info_ceiling.build_pairs` verbatim (3,251 wall pairs)
  pair arithmetic      `info_ceiling._pair_acc` / `folds_by_day` /
                       `combo_forced_choice` — the SAME functions the committed
                       WALL_DISCRIM/WALL_COMBOS census ran
  delayed certificates re-derived from the session's own SANE mid grid with
                       `c_c_roster._emit_candidate`'s skeleton arithmetic and
                       `c_c_roster.certificates`' wall rule, VERIFIED at D=0
                       against the committed roster (see `verify_d0`)
  post-window cues     `seq_cues.cues_from_window` on `tape.ensure` windows —
                       the identical arithmetic as the pre-window census, moved
                       from [t-W, t] to [t, t+D]
  intervals            `panel_score.cluster_mean` / `cluster_ratio`, CLUSTERED
                       BY DAY (the draw unit, D-036/D-073)

CLI  (run in this order; --all does the lot)
  m2_delay.py --paths  [--workers N]   delayed-entry certificates + path cues
                                       (--verify fires automatically: the D=0
                                       reproduction of the committed roster)
  m2_delay.py --seq    [--workers N]   post-window sequence cues
  m2_delay.py --remain                 the remaining-move + scratch-cost curves
  m2_delay.py --decid                  the decidability curve (+ shuffled control)
  m2_delay.py --mgmt                   post-entry divergence + cut economics
  m2_delay.py --select                 feature-only selection, delayed entry
  m2_delay.py --joint                  decidability x remaining move: the crossing
  m2_delay.py --all --workers 8

Reads the report off these: provenance/port_m2/DELAY_DECIDABILITY.md
"""
import argparse
import json
import multiprocessing as mp
import os
import sys
import time

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, "/workspace/engine/port_m0", "/workspace/engine/port_m1",
           "/workspace/engine/port_m3", "/workspace/artifacts/cache/pylibs"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy.random as _npr               # noqa: E402  (folds/controls, pinned)
import m2_common as MC                    # noqa: E402
import common as C                        # noqa: E402
import census_common as X                 # noqa: E402
import assemble as A                      # noqa: E402
import tape as TAPE                       # noqa: E402
import seq_cues as SQ                     # noqa: E402
import panel_score as PS                  # noqa: E402
import info_ceiling as IC                 # noqa: E402

SECTION = ("port m2 entry-delay decidability + post-entry divergence "
           "(E6, hindsight-fit, NON-CAUSAL-BY-DESIGN)")
VERSION = "PORT-M2-DELAY-V1"

OUT_ROOT = os.path.join(MC.M2_ROOT, "delay")
PROV = "/workspace/provenance/port_m2"
SEED = IC.SEED                            # the pinned project seed
TOPN = IC.TOPN_PER_ASSET_DAY              # the reader/model schedule shape
DELAYS = (0, 30, 60, 120, 180, 300, 600, 1200, 1800)
# 0..600 = the mandated grid.  1200/1800 are an EXTENSION arm added to settle
# by measurement, not extrapolation, whether the decidability curve ever
# overtakes the remaining-move floor.  The extension is PATH-ONLY: the
# post-window `seq_cues` block is built on the mandated grid alone because the
# census showed it carries ~nothing over the path block (DELAY_FIELDS.tsv:
# best post-600 seq cue 0.523 vs pp_net 0.672), and a 30-minute event window
# per episode costs ~4x the whole rest of this lane.
WALL_USD = 900.0                          # walls.json: 900 for all three assets
WIN_USD = 1000.0
SANE_SEARCH_CAP = 60                      # a delayed entry waits at most 60s
                                          # for a SANE two-sided quote


# =========================================================== STAGE 1: PATHS ==
# The delayed-entry certificate.  `_leg` is `c_c_roster._emit_candidate`'s
# skeleton arithmetic (prefix-maxima of f and of -f, float32 as stored) and
# `_close_cert` is `c_c_roster.certificates`' phase-close branch.  `verify_d0`
# proves the pair reproduces the committed roster EXACTLY at D=0.
PATH_FIELDS = ("entry_sec", "feasible", "cert_close", "exit_sec", "walled",
               "wall_hit", "mae_after", "mfe_after", "cert_close_roll",
               "exit_sec_roll", "phase_changed", "f_at_D", "mae_to_D",
               "mfe_to_D", "walled_by_D", "pc_sec")
PP_FIELDS = ("pp_net", "pp_mfe", "pp_mae", "pp_giveback", "pp_eff", "pp_rv",
             "pp_upfrac", "pp_slope30", "pp_tmfe_frac", "pp_tmae_frac",
             "pp_spread_mean", "pp_spread_max", "pp_bidsz_mean",
             "pp_asksz_mean", "pp_imb_mean", "pp_imb_delta", "pp_sanefrac",
             "pp_n_sane")


def _leg(s, entry_sec, entry_mid, side, mult):
    """(vt, f, at, av) for a leg opened at `entry_sec` — the roster's own
    skeleton arithmetic, including its float32 storage of the adverse records
    (the wall test is done against those stored values, and the rounding is
    load-bearing: an adverse of 899.9999999999986 IS the wall)."""
    j0 = int(np.searchsorted(s.vt, entry_sec, side="left"))
    vt = s.vt[j0:]
    f = (s.vm[j0:] - entry_mid) * side * mult
    if vt.size == 0:
        return vt, f, np.zeros(0, np.int32), np.zeros(0, np.float32)
    run_a = np.maximum.accumulate(-f)
    na = np.empty(run_a.size, dtype=bool)
    na[0] = False                          # index 0 is never a record (roster)
    if run_a.size > 1:
        na[1:] = run_a[1:] > run_a[:-1]
    return (vt, f, vt[na].astype(np.int32),
            run_a[na].astype(np.float32))


def _wall_sec(at, av, W=WALL_USD):
    w = int(np.searchsorted(av, np.float32(W), side="left"))
    return int(at[w]) if w < av.size else None


def _close_cert(vt, f, at, av, pc, cost, W=WALL_USD):
    """`c_c_roster.certificates`' phase-close certificate for one leg.

    Returns (value, exit second, exited-AT-the-wall, wall-hit-EVER).  The two
    wall flags differ and both are kept: the matrix's own `walled` column is
    "the wall was hit on the adverse skeleton" at ANY horizon, while the
    certificate's exit branch turns only on a wall at or before the phase
    close."""
    t_wall = _wall_sec(at, av, W)
    ever = float(t_wall is not None)
    if t_wall is not None and t_wall <= pc:
        return -W - cost, t_wall, 1.0, ever
    j = int(np.searchsorted(vt, pc, side="right")) - 1
    val = (float(f[j]) if j >= 0 else 0.0) - cost
    return val, int(pc), 0.0, ever


def _excursions(vt, f, lo, hi):
    """(max favourable, max adverse) of `f` over session seconds [lo, hi]."""
    a = int(np.searchsorted(vt, lo, side="left"))
    b = int(np.searchsorted(vt, hi, side="right"))
    if b <= a:
        return 0.0, 0.0, -1, -1
    w = f[a:b]
    ih, il = int(np.argmax(w)), int(np.argmin(w))
    return (float(w[ih]), float(-w[il]), int(vt[a + ih]), int(vt[a + il]))


def _first_sane(s, t):
    """The first SANE two-sided second at or after `t`, within the cap."""
    hi = min(int(t) + SANE_SEARCH_CAP, s.n - 1)
    if int(t) > hi:
        return -1
    j = int(np.searchsorted(s.vt, int(t), side="left"))
    if j >= s.vt.size:
        return -1
    v = int(s.vt[j])
    return v if v <= hi else -1


def _post_path(s, vt, f, t, e, side):
    """The [t, t+D] path block: what the market DID after the confirmation,
    measured on the t-entry's own P&L frame plus the book at those seconds."""
    out = {k: float("nan") for k in PP_FIELDS}
    a = int(np.searchsorted(vt, t, side="left"))
    b = int(np.searchsorted(vt, e, side="right"))
    n_sane = b - a
    span = max(1, int(e) - int(t))
    out["pp_n_sane"] = float(n_sane)
    out["pp_sanefrac"] = n_sane / float(span)
    if n_sane >= 2:
        w = f[a:b]
        wt = vt[a:b]
        mfe = float(w.max())
        mae = float(-w.min())
        net = float(w[-1])
        out["pp_net"] = net
        out["pp_mfe"] = mfe
        out["pp_mae"] = mae
        out["pp_giveback"] = mfe - net
        out["pp_eff"] = net / (mfe + mae + 1.0)
        out["pp_rv"] = float(np.abs(np.diff(w)).sum())
        out["pp_upfrac"] = float((w > 0).mean())
        k30 = int(np.searchsorted(wt, max(t, e - 30), side="left"))
        out["pp_slope30"] = net - float(w[min(k30, w.size - 1)])
        out["pp_tmfe_frac"] = (float(wt[int(np.argmax(w))]) - t) / span
        out["pp_tmae_frac"] = (float(wt[int(np.argmin(w))]) - t) / span
        sp = s.spread_usd[wt]
        out["pp_spread_mean"] = float(np.nanmean(sp))
        out["pp_spread_max"] = float(np.nanmax(sp))
        bs = s.bid_sz[wt].astype(np.float64)
        asz = s.ask_sz[wt].astype(np.float64)
        out["pp_bidsz_mean"] = float(bs.mean())
        out["pp_asksz_mean"] = float(asz.mean())
        tot = bs + asz
        imb = np.where(tot > 0, (bs - asz) / np.maximum(tot, 1e-9), 0.0) * side
        out["pp_imb_mean"] = float(imb.mean())
        out["pp_imb_delta"] = float(imb[-1] - imb[0])
    return out


def _paths_one(job):
    """All episodes of ONE (asset, date8), every delay."""
    asset, d8, rows = job
    try:
        sess = A.load_session(asset, int(d8))
        s = sess["s"]
        mult = float(C.ASSETS[asset]["mult"])
        out = []
        for (i, t, side, cost) in rows:
            t = int(t)
            side = int(side)
            cost = float(cost)
            entry_t = float(s.mid[t])
            vt0, f0, at0, av0 = _leg(s, t, entry_t, side, mult)
            pc0 = X.next_phase_boundary(s, t)
            t_wall0 = _wall_sec(at0, av0)
            rec = {"i": int(i), "d": {}}
            for D in DELAYS:
                r = {k: float("nan") for k in PATH_FIELDS + PP_FIELDS}
                r["feasible"] = 0.0
                r["entry_sec"] = -1.0
                r["exit_sec"] = -1.0
                r["exit_sec_roll"] = -1.0
                r["pc_sec"] = float(pc0)
                tD = t + D
                e = _first_sane(s, tD) if tD < s.n else -1
                if e >= 0:
                    # what the t-entry has already done by the delayed second
                    mfe_to, mae_to, _th, _tl = _excursions(vt0, f0, t, e)
                    r["mfe_to_D"] = mfe_to
                    r["mae_to_D"] = mae_to
                    k = int(np.searchsorted(vt0, e, side="right")) - 1
                    r["f_at_D"] = float(f0[k]) if k >= 0 else 0.0
                    r["walled_by_D"] = float(t_wall0 is not None
                                             and t_wall0 <= e)
                    r.update(_post_path(s, vt0, f0, t, e, side))
                    # the DELAYED entry itself
                    if e < pc0:
                        entry_D = float(s.mid[e])
                        vtD, fD, atD, avD = _leg(s, e, entry_D, side, mult)
                        val, xs, wl, ev = _close_cert(vtD, fD, atD, avD,
                                                      pc0, cost)
                        mfe_a, mae_a, _a, _b = _excursions(vtD, fD, e, xs)
                        pcr = X.next_phase_boundary(s, e)
                        vr, xr, _wr, _er = _close_cert(vtD, fD, atD, avD,
                                                       pcr, cost)
                        r.update({"feasible": 1.0, "entry_sec": float(e),
                                  "cert_close": val, "exit_sec": float(xs),
                                  "walled": wl, "wall_hit": ev,
                                  "mae_after": mae_a,
                                  "mfe_after": mfe_a, "cert_close_roll": vr,
                                  "exit_sec_roll": float(xr),
                                  "phase_changed": float(pcr != pc0)})
                rec["d"][D] = r
            out.append(rec)
        return (asset, int(d8), out, None)
    except Exception as exc:                          # noqa: BLE001
        return (asset, int(d8), [], "%s: %s" % (type(exc).__name__, exc))


def build_paths(workers=8, out_dir=None, limit_days=None):
    out_dir = out_dir or OUT_ROOT
    os.makedirs(out_dir, exist_ok=True)
    E = dict(np.load(os.path.join(IC.OUT_ROOT, "episodes.npz"),
                     allow_pickle=False))
    assets = [MC.ASSET_ORDER[i] for i in E["asset_idx"].tolist()]
    jobs = {}
    for i, (a, d, t, sd, ct) in enumerate(zip(
            assets, E["d8"].tolist(), E["dec_sec"].tolist(),
            E["side"].tolist(), E["cost_rt"].tolist())):
        jobs.setdefault((a, int(d)), []).append((i, int(t), int(sd), float(ct)))
    joblist = [(a, d, sorted(v)) for (a, d), v in sorted(jobs.items())]
    if limit_days:
        joblist = joblist[:limit_days]
    n = E["ep"].size
    fields = list(PATH_FIELDS) + list(PP_FIELDS)
    Pm = {D: np.full((n, len(fields)), np.nan, dtype=np.float64)
          for D in DELAYS}
    t0, errs, done = time.time(), [], 0
    with mp.Pool(processes=int(workers)) as pool:
        for k, (asset, d8, rows, err) in enumerate(
                pool.imap_unordered(_paths_one, joblist, chunksize=1), start=1):
            if err:
                errs.append("%s %d %s" % (asset, d8, err))
            for rec in rows:
                i = rec["i"]
                done += 1
                for D in DELAYS:
                    r = rec["d"][D]
                    Pm[D][i] = [r[f] for f in fields]
            if k % 40 == 0 or k == len(joblist):
                el = time.time() - t0
                sys.stderr.write("paths %d/%d sessions %.0fs eta %.0fs errs=%d\n"
                                 % (k, len(joblist), el,
                                    el / k * (len(joblist) - k), len(errs)))
                sys.stderr.flush()
    np.savez_compressed(os.path.join(out_dir, "paths.npz"),
                        fields=np.array(fields), ep=E["ep"],
                        delays=np.array(DELAYS),
                        **{"D%d" % D: Pm[D] for D in DELAYS})
    rec = {"version": VERSION, "n_episodes": int(n), "n_sessions": len(joblist),
           "n_rows_filled": int(done), "delays": list(DELAYS),
           "errors": errs[:50], "n_errors": len(errs),
           "wall_usd": WALL_USD, "sane_search_cap_sec": SANE_SEARCH_CAP,
           "secs": round(time.time() - t0, 1)}
    with open(os.path.join(out_dir, "paths.receipt.json"), "w") as fh:
        json.dump(rec, fh, indent=1, sort_keys=True)
    sys.stderr.write("paths: %d episodes, %d errors, %.0fs\n"
                     % (done, len(errs), rec["secs"]))
    return Pm, fields


def verify_d0(out_dir=None, n_check=4000):
    """RED-FIRST: the D=0 delayed certificate must equal the COMMITTED one.

    Compares `cert_close` / `exit_sec` / `walled` at D=0 against the matrix's
    own `cert_close_usd` / `exit_close_sec` / `walled` for every episode whose
    entry second needed no SANE search.  Any mismatch is a bug in this file's
    re-derivation, not a finding.
    """
    out_dir = out_dir or OUT_ROOT
    E = dict(np.load(os.path.join(IC.OUT_ROOT, "episodes.npz"),
                     allow_pickle=False))
    Z = np.load(os.path.join(out_dir, "paths.npz"), allow_pickle=False)
    f = [str(x) for x in Z["fields"]]
    P = Z["D0"]
    ok = (P[:, f.index("feasible")] == 1.0) & \
         (P[:, f.index("entry_sec")] == E["dec_sec"].astype(np.float64)) & \
         (E["cert_refused"] == 0)
    idx = np.nonzero(ok)[0]
    dv = np.abs(P[idx, f.index("cert_close")] - E["cert_close_usd"][idx])
    dx = np.abs(P[idx, f.index("exit_sec")] - E["exit_close_sec"][idx])
    dw = np.abs(P[idx, f.index("wall_hit")] - E["walled"][idx])
    out = {"n_episodes": int(E["ep"].size), "n_compared": int(idx.size),
           "n_entry_shifted": int(((P[:, f.index("feasible")] == 1.0) &
                                   (P[:, f.index("entry_sec")] !=
                                    E["dec_sec"].astype(np.float64))).sum()),
           "n_infeasible_D0": int((P[:, f.index("feasible")] != 1.0).sum()),
           "max_abs_cert_diff": float(dv.max()) if idx.size else None,
           "max_abs_exit_diff": float(dx.max()) if idx.size else None,
           "max_abs_walled_diff": float(dw.max()) if idx.size else None,
           "n_cert_mismatch": int((dv > 1e-6).sum()),
           "n_exit_mismatch": int((dx > 0).sum()),
           "n_walled_mismatch": int((dw > 0).sum())}
    with open(os.path.join(out_dir, "verify_d0.receipt.json"), "w") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    sys.stderr.write("verify_d0: %d compared, cert/exit/walled mismatches "
                     "%d/%d/%d\n" % (out["n_compared"], out["n_cert_mismatch"],
                                     out["n_exit_mismatch"],
                                     out["n_walled_mismatch"]))
    return out


# ============================================================ STAGE 2: SEQ ===
SEQ_DELAYS = (30, 60, 120, 180, 300, 600)     # the seq block's own grid
POST_DELAYS = SEQ_DELAYS


def _seqp_one(job):
    """Post-confirmation cues over [t, t+D] — `seq_cues.cues_from_window` on
    the forward window, the same arithmetic `info_ceiling.build_seq` runs on
    the backward one."""
    asset, d8, rows = job
    try:
        sess = A.load_session(asset, int(d8))
        s = sess["s"]
        iid = int(s.iid)
        open_utc = int(s.meta["open_utc"])
        close_utc = int(s.meta["close_utc"])
        hi = max(SEQ_DELAYS) + 2
        ranges = [(max(0, int(t) - 2), int(t) + hi) for (_i, t) in rows]
        arrays, _meta = TAPE.ensure(asset, sess["trade_date"], iid, open_utc,
                                    close_utc, TAPE._merge(ranges))
        out = []
        for (i, t) in rows:
            rec = {"i": int(i)}
            for D in POST_DELAYS:
                w, _a, _b = TAPE.window(arrays, open_utc, int(t), int(t) + D)
                c = SQ.cues_from_window(w)
                for fl in IC.SEQ_FIELDS:
                    rec["post%d_%s" % (D, fl)] = float(c[fl])
            out.append(rec)
        return (asset, int(d8), out, None)
    except Exception as exc:                          # noqa: BLE001
        return (asset, int(d8), [], "%s: %s" % (type(exc).__name__, exc))


def build_seq_post(workers=8, out_dir=None, limit_days=None):
    out_dir = out_dir or OUT_ROOT
    os.makedirs(out_dir, exist_ok=True)
    E = dict(np.load(os.path.join(IC.OUT_ROOT, "episodes.npz"),
                     allow_pickle=False))
    assets = [MC.ASSET_ORDER[i] for i in E["asset_idx"].tolist()]
    jobs = {}
    for i, (a, d, t) in enumerate(zip(assets, E["d8"].tolist(),
                                      E["dec_sec"].tolist())):
        jobs.setdefault((a, int(d)), []).append((i, int(t)))
    joblist = [(a, d, sorted(v, key=lambda z: z[1]))
               for (a, d), v in sorted(jobs.items())]
    if limit_days:
        joblist = joblist[:limit_days]
    fields = ["post%d_%s" % (D, f) for D in POST_DELAYS for f in IC.SEQ_FIELDS]
    S = np.full((E["ep"].size, len(fields)), np.nan, dtype=np.float32)
    t0, errs, done = time.time(), [], 0
    with mp.Pool(processes=int(workers)) as pool:
        for k, (asset, d8, rows, err) in enumerate(
                pool.imap_unordered(_seqp_one, joblist, chunksize=1), start=1):
            if err:
                errs.append("%s %d %s" % (asset, d8, err))
            for r in rows:
                done += 1
                S[r["i"]] = [r[f] for f in fields]
            if k % 20 == 0 or k == len(joblist):
                el = time.time() - t0
                sys.stderr.write("seqpost %d/%d sessions %.0fs eta %.0fs "
                                 "errs=%d\n" % (k, len(joblist), el,
                                                el / k * (len(joblist) - k),
                                                len(errs)))
                sys.stderr.flush()
    np.savez_compressed(os.path.join(out_dir, "seq_post.npz"), S=S,
                        cols=np.array(fields), ep=E["ep"])
    rec = {"version": VERSION, "delays": list(POST_DELAYS),
           "n_episodes": int(E["ep"].size), "n_filled": int(done),
           "n_sessions": len(joblist), "errors": errs[:50],
           "n_errors": len(errs), "secs": round(time.time() - t0, 1)}
    with open(os.path.join(out_dir, "seq_post.receipt.json"), "w") as fh:
        json.dump(rec, fh, indent=1, sort_keys=True)
    sys.stderr.write("seqpost: %d/%d episodes, %d errors, %.0fs\n"
                     % (done, E["ep"].size, len(errs), rec["secs"]))
    return S, fields


# =============================================================== the loader ==
def load(out_dir=None):
    """episodes + pre-window seq (the 225-set) + delayed paths + post cues."""
    out_dir = out_dir or OUT_ROOT
    E = IC.load()                          # 185 views + 40 pre-seq = 225 cols
    Z = np.load(os.path.join(out_dir, "paths.npz"), allow_pickle=False)
    if not np.array_equal(Z["ep"], E["ep"]):
        raise SystemExit("paths.npz episode order differs")
    E["pf"] = [str(x) for x in Z["fields"]]
    E["P"] = {int(D): Z["D%d" % D] for D in DELAYS}
    Q = np.load(os.path.join(out_dir, "seq_post.npz"), allow_pickle=False)
    if not np.array_equal(Q["ep"], E["ep"]):
        raise SystemExit("seq_post.npz episode order differs")
    E["postcols"] = [str(x) for x in Q["cols"]]
    E["POST"] = Q["S"]
    return E


def _pcol(E, D, name):
    return E["P"][int(D)][:, E["pf"].index(name)]


def post_block(E, D):
    """The [t, t+D] feature block: the path cues + the sequence cues."""
    if int(D) == 0:
        return np.zeros((E["ep"].size, 0)), []
    names = ["%s_D%d" % (f, D) for f in PP_FIELDS]
    Xp = np.column_stack([_pcol(E, D, f) for f in PP_FIELDS])
    if int(D) not in SEQ_DELAYS:              # the extension arm: path only
        return Xp, names
    sel = [E["postcols"].index("post%d_%s" % (D, f)) for f in IC.SEQ_FIELDS]
    Xs = E["POST"][:, sel].astype(np.float64)
    names += ["post%d_%s" % (D, f) for f in IC.SEQ_FIELDS]
    return np.column_stack([Xp, Xs]), names


# ================================================ STAGE 3: REMAINING MOVE ====
def _clstat(v, days):
    ok = np.isfinite(v)
    if int(ok.sum()) < 2:
        return {}
    st = PS.cluster_mean(v[ok], [str(x) for x in np.asarray(days)[ok]])
    return st or {}


def _pop_row(E, D, idx, tag, pop):
    """One (population, delay) row of the remaining-move curve."""
    days = E["d8"][idx]
    feas = _pcol(E, D, "feasible")[idx] == 1.0
    cc = _pcol(E, D, "cert_close")[idx]
    ccr = _pcol(E, D, "cert_close_roll")[idx]
    mae = _pcol(E, D, "mae_after")[idx]
    wal = _pcol(E, D, "walled")[idx]
    fat = _pcol(E, D, "f_at_D")[idx]
    wbd = _pcol(E, D, "walled_by_D")[idx]
    phc = _pcol(E, D, "phase_changed")[idx]
    st = _clstat(np.where(feas, cc, np.nan), days)
    st_f = _clstat(np.where(feas, (cc >= WIN_USD).astype(float), np.nan), days)
    n_f = int(feas.sum())
    return {"population": pop, "arm": tag, "delay_sec": int(D),
            "n": int(idx.size), "n_feasible": n_f,
            "frac_feasible": n_f / float(max(1, idx.size)),
            "frac_phase_expired": float((~feas).mean()),
            "mean_cert_close_usd": st.get("mean"),
            "ci_lo": st.get("ci_lo"), "ci_hi": st.get("ci_hi"),
            "median_cert_close_usd": (float(np.nanmedian(cc[feas]))
                                      if n_f else None),
            "frac_ge_1000": st_f.get("mean"),
            "frac_ge_1000_lo": st_f.get("ci_lo"),
            "frac_ge_1000_hi": st_f.get("ci_hi"),
            "frac_le_m900": (float(np.nanmean(cc[feas] <= -WALL_USD))
                             if n_f else None),
            "mean_mae_after_usd": (float(np.nanmean(mae[feas]))
                                   if n_f else None),
            "p90_mae_after_usd": (float(np.nanpercentile(mae[feas], 90))
                                  if n_f else None),
            "frac_walled_after": (float(np.nanmean(wal[feas]))
                                  if n_f else None),
            "mean_f_at_D_usd": float(np.nanmean(fat)),
            "median_f_at_D_usd": float(np.nanmedian(fat)),
            "p10_f_at_D_usd": float(np.nanpercentile(fat, 10)),
            "p25_f_at_D_usd": float(np.nanpercentile(fat, 25)),
            "p75_f_at_D_usd": float(np.nanpercentile(fat, 75)),
            "p90_f_at_D_usd": float(np.nanpercentile(fat, 90)),
            "mean_mae_to_D_usd": float(np.nanmean(_pcol(E, D, "mae_to_D")[idx])),
            "mean_mfe_to_D_usd": float(np.nanmean(_pcol(E, D, "mfe_to_D")[idx])),
            "frac_walled_by_D": float(np.nanmean(wbd)),
            "frac_phase_changed": (float(np.nanmean(phc[feas]))
                                   if n_f else None),
            "mean_cert_close_roll_usd": (float(np.nanmean(ccr[feas]))
                                         if n_f else None),
            "mean_decay_vs_D0_usd": None}


REMAIN_COLS = ("population", "arm", "delay_sec", "n", "n_feasible",
               "frac_feasible", "frac_phase_expired", "mean_cert_close_usd",
               "ci_lo", "ci_hi", "median_cert_close_usd", "frac_ge_1000",
               "frac_ge_1000_lo", "frac_ge_1000_hi", "frac_le_m900",
               "mean_mae_after_usd", "p90_mae_after_usd", "frac_walled_after",
               "mean_f_at_D_usd", "median_f_at_D_usd", "p10_f_at_D_usd",
               "p25_f_at_D_usd", "p75_f_at_D_usd", "p90_f_at_D_usd",
               "mean_mae_to_D_usd", "mean_mfe_to_D_usd", "frac_walled_by_D",
               "frac_phase_changed", "mean_cert_close_roll_usd",
               "mean_decay_vs_D0_usd")


def populations(E):
    """The four populations the curve is asked for."""
    pairs = IC.build_pairs(E)[0]
    tight = [p for p in pairs
             if not np.isfinite(p["mid_gap_atr"]) or
             p["mid_gap_atr"] <= IC.VICINITY_ATR]
    iw = np.array(sorted({p["i_win"] for p in tight}), dtype=np.int64)
    il = np.array(sorted({p["i_lose"] for p in tight}), dtype=np.int64)
    fin = E["cert_refused"] == 0
    d21 = np.nonzero(fin & (E["y_winner"] == 1.0))[0]
    nonw = np.nonzero(fin & (E["y_winner"] == 0.0))[0]
    return tight, {"WALLPAIR_WINNER_LEGS": iw, "WALLPAIR_LOSER_LEGS": il,
                   "E6_D021_WINNERS": d21, "E6_NON_WINNERS": nonw}


def run_remain(out_dir=None):
    E = load(out_dir)
    tight, pops = populations(E)
    rows = []
    base = {}
    for pop, idx in pops.items():
        for D in DELAYS:
            r = _pop_row(E, D, idx, "enter_at_t+D", pop)
            if D == 0:
                base[pop] = r["mean_cert_close_usd"]
            rows.append(r)
    for r in rows:
        b = base.get(r["population"])
        if b is not None and r["mean_cert_close_usd"] is not None:
            r["mean_decay_vs_D0_usd"] = r["mean_cert_close_usd"] - b
    IC._w(os.path.join(PROV, "DELAY_REMAINING_MOVE.tsv"), REMAIN_COLS, rows,
          [SECTION,
           "enter at mid(t+D) instead of mid(t); EXIT is the ORIGINAL phase "
           "close (the seat shape) — a delay that runs past the phase close "
           "makes the trade impossible and is counted as frac_phase_expired",
           "cert_close = the walled phase-close certificate of the DELAYED "
           "entry (c_c_roster.certificates arithmetic, $900 wall, same "
           "session cost_rt); mae_after = max adverse excursion AFTER t+D",
           "f_at_D = what a t-entry is worth at t+D (the management scratch "
           "mark); frac_walled_by_D = the t-entry was already stopped",
           "cert_close_roll = the same delayed entry allowed to run to the "
           "NEXT phase boundary instead (the generous variant)",
           "intervals: CR1 clustered BY DAY"])
    return rows


# ============================================== STAGE 4: THE DECIDABILITY ====
def pair_matrix(E, tight, D):
    """The paired difference matrix at delay D: the 225 pre-t fields plus the
    [t, t+D] post block, winner leg minus loser leg."""
    iw = np.array([p["i_win"] for p in tight])
    il = np.array([p["i_lose"] for p in tight])
    names = list(E["cols"])
    layer = ["PRE"] * len(names)
    Dd = (E["X"][iw].astype(np.float64) - E["X"][il].astype(np.float64))
    Xp, pn = post_block(E, D)
    if pn:
        Dd = np.column_stack([Dd, Xp[iw] - Xp[il]])
        names = names + pn
        layer += ["POST"] * len(pn)
    return Dd, names, np.array(layer), np.array([p["d8"] for p in tight])


DECID_COLS = ("delay_sec", "field_set", "n_fields", "n_pairs", "metric",
              "pair_acc_kfold", "pair_acc_in_sample", "ci_lo", "ci_hi",
              "gap_to_073", "best_field", "fields")


def _acc_ci(hits_by_day, tot_by_day):
    """Day-clustered interval for a pair accuracy (ratio of sums)."""
    ks = sorted(tot_by_day)
    st = PS.cluster_ratio([hits_by_day[k] for k in ks],
                          [tot_by_day[k] for k in ks], ks)
    return (st or {}).get("ci_lo"), (st or {}).get("ci_hi")


def single_field_scan(Dd, names, layer, day, folds):
    """Every field's k-fold pair accuracy — `info_ceiling._pair_acc` verbatim,
    sign fitted on the training folds only."""
    out = []
    for k, c in enumerate(names):
        d = Dd[:, k]
        ok = np.isfinite(d)
        if int(ok.sum()) < max(20, 0.2 * d.size):
            continue
        a_pos, n = IC._pair_acc(d, 1.0)
        a_neg, _ = IC._pair_acc(d, -1.0)
        hits, tot = 0.0, 0
        hd, td = {}, {}
        for f in range(IC.KFOLDS):
            tr, te = folds != f, folds == f
            ap, _ = IC._pair_acc(d[tr], 1.0)
            an, _ = IC._pair_acc(d[tr], -1.0)
            s = 1.0 if ap >= an else -1.0
            v = d[te] * s
            fin = np.isfinite(v)
            dv, dd_ = v[fin], day[te][fin]
            h = (dv > 0).astype(float) + 0.5 * (dv == 0)
            hits += float(h.sum())
            tot += int(dv.size)
            for x, y in zip(dd_.tolist(), h.tolist()):
                hd[str(x)] = hd.get(str(x), 0.0) + y
                td[str(x)] = td.get(str(x), 0.0) + 1.0
        acc = (hits / tot) if tot else float("nan")
        lo, hi = _acc_ci(hd, td)
        out.append({"field": c, "layer": str(layer[k]), "n_pairs": n,
                    "pair_acc_in_sample": max(a_pos, a_neg),
                    "pair_acc_kfold": acc, "ci_lo": lo, "ci_hi": hi})
    out.sort(key=lambda r: -(r["pair_acc_kfold"]
                             if np.isfinite(r["pair_acc_kfold"]) else 0))
    return out


def run_decid(out_dir=None, shuffles=(120, 600)):
    E = load(out_dir)
    tight, _pops = populations(E)
    rows, fld_rows = [], []
    t0 = time.time()
    for D in DELAYS:
        Dd, names, layer, day = pair_matrix(E, tight, D)
        folds = IC.folds_by_day(day)
        singles = single_field_scan(Dd, names, layer, day, folds)
        for r in singles[:25]:
            fld_rows.append(dict(r, delay_sec=int(D)))
        # best single, by layer and overall
        for tag, sub in (("BEST_SINGLE_ANY", singles),
                         ("BEST_SINGLE_PRE", [r for r in singles
                                              if r["layer"] == "PRE"]),
                         ("BEST_SINGLE_POST", [r for r in singles
                                               if r["layer"] == "POST"])):
            if not sub:
                continue
            b = sub[0]
            rows.append({"delay_sec": int(D), "field_set": tag, "n_fields": 1,
                         "n_pairs": b["n_pairs"], "metric": "single_field",
                         "pair_acc_kfold": b["pair_acc_kfold"],
                         "pair_acc_in_sample": b["pair_acc_in_sample"],
                         "ci_lo": b["ci_lo"], "ci_hi": b["ci_hi"],
                         "gap_to_073": 0.73 - b["pair_acc_kfold"],
                         "best_field": b["field"], "fields": b["field"]})
        ranked = [r["field"] for r in singles]
        ranked_pre = [r["field"] for r in singles if r["layer"] == "PRE"]
        ranked_post = [r["field"] for r in singles if r["layer"] == "POST"]
        nat_pre = [c for c in names if c in set(ranked_pre)]
        specs = [("COMBO_TOP%d" % k, ranked[:k]) for k in (2, 3, 5, 10)]
        specs += [("COMBO_TOP5_PRE_ONLY", ranked_pre[:5]),
                  ("COMBO_ALL_PRE", nat_pre),
                  ("COMBO_ALL_FIELDS", [c for c in names if c in
                                        set(ranked)])]
        if ranked_post:
            specs += [("COMBO_TOP5_POST_ONLY", ranked_post[:5]),
                      ("COMBO_ALL_POST", ranked_post)]
        for tag, flds in specs:
            if not flds:
                continue
            sel = [names.index(f) for f in flds]
            acc_in, acc_kf, hd, td = IC.combo_forced_choice(Dd, folds, sel,
                                                            day=day)
            lo, hi = _acc_ci(hd, td)
            rows.append({"delay_sec": int(D), "field_set": tag,
                         "n_fields": len(sel), "n_pairs": int(Dd.shape[0]),
                         "metric": "gbt_forced_choice",
                         "pair_acc_kfold": acc_kf,
                         "pair_acc_in_sample": acc_in, "ci_lo": lo, "ci_hi": hi,
                         "gap_to_073": 0.73 - acc_kf, "best_field": "",
                         "fields": (",".join(flds) if len(flds) <= 10
                                    else "(%d fields)" % len(flds))})
        if int(D) in shuffles:
            rng = _npr.default_rng(SEED + 4242 + int(D))
            eps = rng.choice([-1.0, 1.0], size=Dd.shape[0])[:, None]
            sel = [names.index(f) for f in ranked[:10]]
            acc_in, acc_kf, hd, td = IC.combo_forced_choice(Dd * eps, folds,
                                                            sel, day=day)
            lo, hi = _acc_ci(hd, td)
            rows.append({"delay_sec": int(D),
                         "field_set": "SHUFFLED_LABEL_CONTROL_TOP10",
                         "n_fields": len(sel), "n_pairs": int(Dd.shape[0]),
                         "metric": "gbt_forced_choice",
                         "pair_acc_kfold": acc_kf,
                         "pair_acc_in_sample": acc_in, "ci_lo": lo, "ci_hi": hi,
                         "gap_to_073": 0.73 - acc_kf, "best_field": "",
                         "fields": "winner/loser assignment randomised"})
        sys.stderr.write("decid D=%d done (%.0fs)\n" % (D, time.time() - t0))
        sys.stderr.flush()
    IC._w(os.path.join(PROV, "DELAY_DECIDABILITY.tsv"), DECID_COLS, rows,
          [SECTION,
           "the wall-pair paired census re-run at each delay D: PRE = the 225 "
           "fields at t (185 views + 40 pre-window seq cues), POST = the "
           "[t, t+D] block (18 path cues + 20 seq_cues on the forward window)",
           "pair_acc_kfold: 5 folds of whole DAYS; single-field signs and GBT "
           "fits are trained on 4/5 of the days and scored on the fifth",
           "the GBT arm is the ANTISYMMETRISED two-alternative forced choice "
           "(each pair entered twice, (w-l)->1 and (l-w)->0) — "
           "info_ceiling.combo_forced_choice, the same function the committed "
           "WALL_COMBOS census calls",
           "0.73 = the pair accuracy $1,000/trade requires at these payoffs "
           "(ERA_NOTES/STATE arithmetic); intervals CR1 clustered BY DAY"])
    IC._w(os.path.join(PROV, "DELAY_FIELDS.tsv"),
          ("delay_sec", "field", "layer", "n_pairs", "pair_acc_kfold",
           "pair_acc_in_sample", "ci_lo", "ci_hi"), fld_rows,
          [SECTION, "top 25 single fields at each delay"])
    return rows, fld_rows


# ================================= STAGE 5: DIVERGENCE + CUT ECONOMICS =======
import xgboost as xgb                     # noqa: E402


CUT_CFG = {"max_depth": 5, "eta": 0.08, "min_child_weight": 20,
           "subsample": 0.9, "colsample_bytree": 0.9,
           "objective": "binary:logistic", "tree_method": "hist",
           "seed": SEED, "nthread": 8}
CUT_ROUNDS = 250
# The operating point is a CUT FRACTION, not a raw probability: the winner base
# rate differs by an order of magnitude between the two populations (50% on
# matched wall pairs, 4.9% era-wide), so a fixed probability threshold is not a
# comparable knob.  `q` = "cut the worst-looking q of the trades still open at
# t+D"; the cut level is the q-quantile of the OUT-OF-FOLD score (one scalar
# read off the full score vector — declared, and worth ~nothing at these n).
CUT_FRACTIONS = (0.0, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90)


def oof_scores(Xf, y, day, folds):
    p = np.full(Xf.shape[0], np.nan)
    for f in range(IC.KFOLDS):
        tr = np.nonzero((folds != f) & np.isfinite(y))[0]
        te = np.nonzero(folds == f)[0]
        b = xgb.train(CUT_CFG, xgb.DMatrix(Xf[tr], label=y[tr]), CUT_ROUNDS)
        p[te] = b.predict(xgb.DMatrix(Xf[te]))
    return p


def _cut_pnl(E, D, idx, score, thr):
    """(enter at t, cut at t+D when the score disqualifies, else ride).

    A trade whose OWN exit second has already passed by t+D — stopped at the
    $900 wall or closed out at the phase boundary — is no longer open and
    cannot be cut: it keeps its unmanaged certificate.  (`exit_close_sec` is
    the certificate's own exit, so this is exact and makes the q=0 arm land on
    delta = 0 identically.)"""
    cost = E["cost_rt"][idx]
    cc = E["cert_close_usd"][idx]
    fat = _pcol(E, D, "f_at_D")[idx]
    esec = _pcol(E, D, "entry_sec")[idx]
    open_at_D = (_pcol(E, D, "feasible")[idx] == 1.0) & np.isfinite(fat) & \
                (esec < E["exit_close_sec"][idx])
    cut = (score[idx] < thr) & open_at_D
    return np.where(cut, fat - cost, cc), cut


MGMT_COLS = ("population", "delay_sec", "cut_fraction", "cut_level", "n",
             "cut_rate",
             "mean_usd_managed", "ci_lo", "ci_hi", "mean_usd_unmanaged",
             "delta_usd", "delta_lo", "delta_hi", "winner_cut_rate",
             "loser_cut_rate", "mean_usd_winners", "mean_usd_losers",
             "proj_usd_at_40pct", "proj_usd_per_day_3trades",
             "cut_would_have_paid_usd", "cut_realized_usd", "saved_per_cut_usd",
             "kept_would_have_paid_usd", "auc", "note")


def run_mgmt(out_dir=None):
    E = load(out_dir)
    tight, pops = populations(E)
    fin = E["cert_refused"] == 0
    rows, div_rows = [], []
    # ---- population A: the wall-pair legs (the matched divergence question) --
    legs = np.array(sorted(set(pops["WALLPAIR_WINNER_LEGS"].tolist())
                           | set(pops["WALLPAIR_LOSER_LEGS"].tolist())),
                    dtype=np.int64)
    is_w = np.isin(legs, pops["WALLPAIR_WINNER_LEGS"])
    # ---- population B: every E6 episode, D-021 winner label -----------------
    allep = np.nonzero(fin)[0]
    yall = E["y_winner"][allep]
    t0 = time.time()
    for pop, idx, y in (("WALLPAIR_LEGS", legs, is_w.astype(np.float64)),
                        ("E6_ALL_EPISODES", allep, yall)):
        day = E["d8"][idx]
        folds = IC.folds_by_day(day)
        for D in DELAYS:
            Xp, pn = post_block(E, D)
            Xf = np.ascontiguousarray(
                np.column_stack([E["X"][idx]] +
                                ([Xp[idx].astype(np.float32)] if pn else [])),
                dtype=np.float32)
            sc = np.full(E["ep"].size, np.nan)
            sc[idx] = oof_scores(Xf, y, day, folds)
            auc = IC._auc(sc[idx], y)
            div_rows.append({"population": pop, "delay_sec": int(D),
                             "n": int(idx.size), "n_features": int(Xf.shape[1]),
                             "auc": round(float(auc), 4),
                             "acc_at_50": float(np.nanmean(
                                 (sc[idx] > 0.5) == (y > 0.5)))})
            unm = E["cert_close_usd"][idx]
            st_u = _clstat(unm, day)
            for q in CUT_FRACTIONS:
                thr = (-np.inf if q <= 0
                       else float(np.nanquantile(sc[idx], q)))
                pnl, cut = _cut_pnl(E, D, idx, sc, thr)
                st = _clstat(pnl, day)
                dl = _clstat(pnl - unm, day)
                mw = float(np.nanmean(pnl[y > 0.5]))
                ml = float(np.nanmean(pnl[y <= 0.5]))
                cw = (float(np.nanmean(unm[cut])) if cut.any()
                      else float("nan"))
                cr = (float(np.nanmean(pnl[cut])) if cut.any()
                      else float("nan"))
                kw = (float(np.nanmean(unm[~cut])) if (~cut).any()
                      else float("nan"))
                rows.append({"population": pop, "delay_sec": int(D),
                             "cut_fraction": q,
                             "cut_level": (None if q <= 0 else thr),
                             "n": int(idx.size),
                             "cut_rate": float(cut.mean()),
                             "mean_usd_managed": st.get("mean"),
                             "ci_lo": st.get("ci_lo"), "ci_hi": st.get("ci_hi"),
                             "mean_usd_unmanaged": st_u.get("mean"),
                             "delta_usd": dl.get("mean"),
                             "delta_lo": dl.get("ci_lo"),
                             "delta_hi": dl.get("ci_hi"),
                             "winner_cut_rate": float(cut[y > 0.5].mean()),
                             "loser_cut_rate": float(cut[y <= 0.5].mean()),
                             "mean_usd_winners": mw, "mean_usd_losers": ml,
                             "proj_usd_at_40pct": 0.40 * mw + 0.60 * ml,
                             "proj_usd_per_day_3trades":
                                 3.0 * (0.40 * mw + 0.60 * ml),
                             "cut_would_have_paid_usd": cw,
                             "cut_realized_usd": cr,
                             "saved_per_cut_usd": cr - cw,
                             "kept_would_have_paid_usd": kw,
                             "auc": round(float(auc), 4),
                             "note": ("cut the worst-looking %.0f%% at t+D"
                                      % (100.0 * q) if q > 0 else
                                      "no cut (the unmanaged shape)")})
            sys.stderr.write("mgmt %s D=%d auc=%.4f (%.0fs)\n"
                             % (pop, D, auc, time.time() - t0))
            sys.stderr.flush()
    IC._w(os.path.join(PROV, "DELAY_MANAGEMENT.tsv"), MGMT_COLS, rows,
          [SECTION,
           "THE RULE: enter at t (the current shape); at t+D score the trade "
           "on pre-t fields + the [t, t+D] block; if the score is below the "
           "threshold CUT at mid(t+D) (realising f_at_D - cost_rt), else ride "
           "to the walled phase close.  A trade already stopped by the $900 "
           "wall before t+D pays the wall regardless.",
           "scores are OUT-OF-FOLD (5 folds of whole DAYS); the operating "
           "point is a CUT FRACTION q — cut the worst-looking q of the "
           "trades still open at t+D (cut_level = the q-quantile of the "
           "out-of-fold score)",
           "proj_usd_at_40pct = 0.40 x mean(winners) + 0.60 x mean(losers) — "
           "the teacher's MEASURED sealed take-precision applied to this "
           "population's per-class outcomes; per_day assumes the 3-seat shape",
           "intervals CR1 clustered BY DAY; delta_usd is the PAIRED "
           "(managed - unmanaged) difference on the same rows",
           "cut_would_have_paid_usd = the unmanaged certificate of the trades "
           "the rule CUT — the diagnostic that says WHICH tail the score "
           "selects; saved_per_cut_usd = realized - would-have-paid, per cut "
           "trade (positive = the cut avoided a loss)"])
    IC._w(os.path.join(PROV, "DELAY_DIVERGENCE.tsv"),
          ("population", "delay_sec", "n", "n_features", "auc", "acc_at_50"),
          div_rows,
          [SECTION, "per-leg separability of winner vs loser using pre-t "
                    "fields + the [t, t+D] block, out-of-fold by DAY"])
    return rows, div_rows


# ====================================== STAGE 5b: FEATURE-ONLY SELECTION =====
# The deployable-SHAPED question: rank every episode by a model that may read
# the pre-t fields AND the [t, t+D] window, take the top 3 per asset-day, and
# ENTER AT t+D.  Every input is at or before the entry second, so unlike the
# wall-pair forced choice this arm is a policy — the only hindsight left is
# that the model is fitted k-fold inside E6 rather than walk-forward.
SELECT_COLS = ("delay_sec", "n_takes", "n_seated", "expectancy_usd", "ci_lo",
               "ci_hi", "median_usd", "win_rate", "frac_ge_1000", "frac_ge_600",
               "mean_mae_to_exit_usd", "p90_mae_to_exit_usd",
               "exited_at_wall_rate", "capture_oracle",
               "cap_lo", "cap_hi", "usd_per_session", "usd_per_day_3assets",
               "n_refused_infeasible", "auc", "note")


def as_D_delayed(E, D):
    """`info_ceiling.as_D` with the DELAYED entry's certificate installed."""
    Dd = dict(IC.as_D(E))
    feas = _pcol(E, D, "feasible") == 1.0
    Dd["dec_sec"] = np.where(feas, _pcol(E, D, "entry_sec"),
                             E["dec_sec"]).astype(np.int64)
    Dd["cert_close_usd"] = _pcol(E, D, "cert_close")
    Dd["exit_close_sec"] = np.where(feas, _pcol(E, D, "exit_sec"),
                                    E["exit_close_sec"]).astype(np.int64)
    Dd["cert_refused"] = np.where(feas & (E["cert_refused"] == 0),
                                  0, 1).astype(np.int64)
    Dd["mae_before_argmax"] = _pcol(E, D, "mae_after")
    Dd["walled"] = _pcol(E, D, "walled")
    return Dd


def run_select(out_dir=None):
    """The score is built with `info_ceiling`'s OWN honest-k-fold construction
    — the two heads (`IC.HEADS`), its depth search, its `_oof`, its rank-sum
    composition, its `_cols_for` view selection — so the D=0 row IS the
    committed `L1L2L3_all_views|HONEST_KFOLD_DAY` arm and every later row
    differs from it in exactly one thing: the delay."""
    import m3_walk as MW
    E = load(out_dir)
    orc, _rep = IC.denominators(E)
    n_sess = len(orc)
    jpre = IC._cols_for(E, ("DIGEST", "SHEETS", "SEQ"))
    d8 = E["d8"]
    folds = IC.folds_by_day(d8)
    cfgs = {}
    rows = []
    t0 = time.time()
    for D in DELAYS:
        Xp, pn = post_block(E, D)
        Xf = np.ascontiguousarray(
            np.column_stack([E["X"][:, jpre]] +
                            ([Xp.astype(np.float32)] if pn else [])),
            dtype=np.float32)
        heads = {}
        for h in IC.HEADS:
            yy = E[h].astype(np.float64)
            if h not in cfgs:                 # depth chosen ONCE, at D=0
                tr0 = np.nonzero((folds != 0) & np.isfinite(yy))[0]
                cfgs[h] = IC._select_cfg(Xf, yy, tr0, d8)[:2]
            cfg, rounds = cfgs[h]
            heads[h], _u = IC._oof(E, Xf, yy, folds, cfg, rounds, d8)
        Dd = as_D_delayed(E, D)
        sc = (MW._unit_pct(Dd, heads[IC.HEADS[0]], np.arange(E["ep"].size)) +
              MW._unit_pct(Dd, heads[IC.HEADS[1]], np.arange(E["ep"].size)))
        auc = IC._auc(heads[IC.HEADS[1]], E["y_winner"].astype(np.float64))
        tk = MW.topn_takes(Dd, sc, np.arange(E["ep"].size),
                           TOPN, deployable=True, unit="session")
        rp = MW.replay_rows(Dd, tk)
        seats = [j for r in rp for j in r["seats"]]
        pt = MW.per_trade_stats(Dd, seats)
        cl = [s.split("|")[1] for s in sorted(orc)]
        real = {r["session"]: r["realised"] for r in rp}
        num = [real.get(s, 0.0) for s in sorted(orc)]
        den = [orc[s] for s in sorted(orc)]
        st = PS.cluster_ratio(num, den, cl)
        ex = PS.cluster_mean(Dd["cert_close_usd"][np.asarray(seats)],
                             [str(E["d8"][j]) for j in seats]) if seats else {}
        rows.append({"delay_sec": int(D), "n_takes": int(tk.size),
                     "n_seated": len(seats),
                     "expectancy_usd": pt.get("expectancy_usd"),
                     "ci_lo": (ex or {}).get("ci_lo"),
                     "ci_hi": (ex or {}).get("ci_hi"),
                     "median_usd": pt.get("median_usd"),
                     "win_rate": pt.get("win_rate"),
                     "frac_ge_1000": pt.get("frac_ge_1000"),
                     "frac_ge_600": pt.get("frac_ge_600"),
                     "mean_mae_to_exit_usd": pt.get("mean_mae_usd"),
                     "p90_mae_to_exit_usd": pt.get("p90_mae_usd"),
                     "exited_at_wall_rate": pt.get("walled_rate"),
                     "capture_oracle": (st or {}).get("ratio"),
                     "cap_lo": (st or {}).get("ci_lo"),
                     "cap_hi": (st or {}).get("ci_hi"),
                     "usd_per_session": float(sum(num)) / n_sess,
                     "usd_per_day_3assets": 3.0 * float(sum(num)) / n_sess,
                     "n_refused_infeasible":
                         int((Dd["cert_refused"] != 0).sum()
                             - int((E["cert_refused"] != 0).sum())),
                     "auc": round(float(auc), 4),
                     "note": "top-%d per asset-day on the composed "
                             "(champion-rank + winner) head over pre-t + "
                             "[t, t+D], entered at t+D" % TOPN})
        sys.stderr.write("select D=%d auc=%.4f exp=%.1f cap=%.4f (%.0fs)\n"
                         % (D, auc, rows[-1]["expectancy_usd"] or float("nan"),
                            rows[-1]["capture_oracle"] or float("nan"),
                            time.time() - t0))
        sys.stderr.flush()
    IC._w(os.path.join(PROV, "DELAY_SELECTION.tsv"), SELECT_COLS, rows,
          [SECTION,
           "FEATURE-ONLY SELECTION, delayed entry: the score is "
           "info_ceiling's OWN honest arm — both heads, its depth search, its "
           "OUT-OF-FOLD predictions (5 folds of whole DAYS) and its within-"
           "(asset, day) rank-sum composition — over the pre-t fields plus "
           "the [t, t+D] window; the schedule is the program's own: top-%d "
           "episodes per "
           "asset-day, one position at a time, D-077 compliance veto ON "
           "(m3_walk.topn_takes / replay_rows verbatim), the ONLY change "
           "being that the seat is opened at t+D and carries the DELAYED "
           "certificate" % TOPN,
           "capture_oracle is against the same $1,159,712 E6 oracle "
           "denominator info_ceiling uses; usd_per_session divides by the "
           "era's 384 (asset, day) sessions, so usd_per_day_3assets is the "
           "three-book daily number the D-048 bar is written against",
           "the D=0 row IS the committed INFO_CEILING_FITS.tsv arm "
           "L1L2L3_all_views|HONEST_KFOLD_DAY (same features, same folds, "
           "same heads, same schedule) — every later row differs from it in "
           "exactly one thing, the delay",
           "MAE COLUMN CAVEAT: mae_to_exit is the max adverse excursion from "
           "the entry to the ACTUAL exit — NOT the matrix's "
           "`mae_before_argmax` (adverse before the favourable peak) that the "
           "D-021 ~$300 acceptance bar is written against.  It is the larger "
           "of the two and must not be read against that bar; likewise "
           "exited_at_wall_rate is 'stopped at the $900 wall', not the "
           "matrix's 'wall touched at any horizon'.",
           "still NOT a deployable result: the fit is k-fold inside E6, not "
           "walk-forward"])
    return rows


# ================================================ STAGE 6: THE JOINT TABLE ===
# The whole question in one row per delay: the accuracy the tape supports at
# D, multiplied into the dollars that are still there at D.
JOINT_COLS = ("delay_sec", "best_acc_kfold", "best_field_set", "acc_lo",
              "acc_hi", "win_leg_mean_usd", "lose_leg_mean_usd",
              "win_leg_frac_ge_1000", "n_win_feasible", "n_lose_feasible",
              "ev_at_best_acc_usd", "ev_lo_usd", "ev_hi_usd",
              "ev_at_0p40_usd", "ev_at_0p50_usd", "ev_at_0p73_usd",
              "ev_per_day_3trades_usd", "acc_required_1000", "acc_required_299",
              "acc_required_breakeven", "acc_surplus_vs_1000", "note")


def _read_tsv(path):
    rows, cols = [], None
    with open(path) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if cols is None:
                cols = f
                continue
            rows.append(dict(zip(cols, f)))
    return rows


def _fl(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def run_joint(out_dir=None):
    """DECIDABILITY x REMAINING MOVE — the table the verdict is read off."""
    E = load(out_dir)
    tight, pops = populations(E)
    dec = [r for r in _read_tsv(os.path.join(PROV, "DELAY_DECIDABILITY.tsv"))
           if not r["field_set"].startswith("SHUFFLED")]
    rows = []
    for D in DELAYS:
        at = [r for r in dec if int(r["delay_sec"]) == D]
        if not at:
            continue
        b = max(at, key=lambda r: _fl(r["pair_acc_kfold"]))
        acc = _fl(b["pair_acc_kfold"])
        iw, il = pops["WALLPAIR_WINNER_LEGS"], pops["WALLPAIR_LOSER_LEGS"]
        cw = _pcol(E, D, "cert_close")[iw]
        cl = _pcol(E, D, "cert_close")[il]
        mw = float(np.nanmean(cw))
        ml = float(np.nanmean(cl))
        ev = lambda a: a * mw + (1.0 - a) * ml      # noqa: E731
        rows.append({
            "delay_sec": int(D), "best_acc_kfold": acc,
            "best_field_set": b["field_set"],
            "acc_lo": _fl(b["ci_lo"]), "acc_hi": _fl(b["ci_hi"]),
            "win_leg_mean_usd": mw, "lose_leg_mean_usd": ml,
            "win_leg_frac_ge_1000": float(np.nanmean(cw >= WIN_USD)),
            "n_win_feasible": int(np.isfinite(cw).sum()),
            "n_lose_feasible": int(np.isfinite(cl).sum()),
            "ev_at_best_acc_usd": ev(acc),
            "ev_lo_usd": ev(_fl(b["ci_lo"])), "ev_hi_usd": ev(_fl(b["ci_hi"])),
            "ev_at_0p40_usd": ev(0.40), "ev_at_0p50_usd": ev(0.50),
            "ev_at_0p73_usd": ev(0.73),
            "ev_per_day_3trades_usd": 3.0 * ev(acc),
            "acc_required_1000": ((1000.0 - ml) / (mw - ml)
                                  if mw > ml else float("nan")),
            "acc_required_299": ((299.0 - ml) / (mw - ml)
                                 if mw > ml else float("nan")),
            "acc_required_breakeven": ((0.0 - ml) / (mw - ml)
                                       if mw > ml else float("nan")),
            "acc_surplus_vs_1000": (acc - (1000.0 - ml) / (mw - ml)
                                    if mw > ml else float("nan")),
            "note": "forced choice between the two legs of a wall pair, "
                    "entered at t+D"})
    IC._w(os.path.join(PROV, "DELAY_JOINT.tsv"), JOINT_COLS, rows,
          [SECTION,
           "THE CROSSING: at each delay the BEST measured pair accuracy is "
           "multiplied into the dollars still on the table at that delay.",
           "ev = acc x mean(winner leg cert at t+D) + (1-acc) x mean(loser "
           "leg cert at t+D).  A leg whose phase closed before t+D is "
           "excluded from its mean (see DELAY_REMAINING_MOVE frac_feasible) "
           "— the EV is therefore GENEROUS to the delay.",
           "ev_at_0p40 = the teacher's MEASURED sealed take-precision; "
           "ev_at_0p73 = the accuracy $1,000/trade requires at D=0",
           "acc_required_1000 = THE FLOOR at this delay: the pair accuracy "
           "that would be needed to earn $1,000/trade on the DELAYED payoffs "
           "= (1000 - lose_leg_mean) / (win_leg_mean - lose_leg_mean).  The "
           "curve CROSSES when best_acc_kfold >= acc_required_1000 "
           "(acc_surplus_vs_1000 >= 0).",
           "NOT DEPLOYABLE: the forced choice presupposes the pair, which is "
           "an outcome-defined object."])
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--paths", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--seq", action="store_true")
    ap.add_argument("--remain", action="store_true")
    ap.add_argument("--decid", action="store_true")
    ap.add_argument("--mgmt", action="store_true")
    ap.add_argument("--select", action="store_true")
    ap.add_argument("--joint", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit-days", dest="limit_days", type=int, default=None)
    a = ap.parse_args(argv)
    if a.paths or a.all:
        build_paths(workers=a.workers, limit_days=a.limit_days)
    if a.verify or a.paths or a.all:
        verify_d0()
    if a.seq or a.all:
        build_seq_post(workers=a.workers, limit_days=a.limit_days)
    if a.remain or a.all:
        run_remain()
    if a.decid or a.all:
        run_decid()
    if a.mgmt or a.all:
        run_mgmt()
    if a.select or a.all:
        run_select()
    if a.joint or a.all:
        run_joint()
    return 0


if __name__ == "__main__":
    sys.exit(main())
