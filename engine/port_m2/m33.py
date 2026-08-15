#!/usr/bin/python3
"""PORT M2 — M-33 FAILED AUCTION: detector, census, ceiling.  NO BUILD.

WHY THIS ONE, AND WHY NOW
  Every axis this campaign has closed is an ORDERING or an ACT-SHAPE axis, and
  tonight closed the last of the shape axes (exit horizon optimal in both
  directions; seat grid and the <=10/day cap non-binding).  M-33 is different
  in kind: it is a GENERATION-side idea.  It does not try to order the existing
  candidates better — it asks whether a NAMED SETUP THE ROSTER DOES NOT
  GENERATE carries money the current pool never sees.  That moves the CEILING
  rather than the capture of it, which is the one lever left untried.

  The brief's instruction is explicit and is obeyed here: DETECTOR + CENSUS +
  CEILING BEFORE ANY BUILD.  Nothing in this file fits anything.

THE SETUP, in its NARROW definition (design/CREATOR_MECHANICS.md M-33, quoting
`mastering-amt-vp.pdf` p.9-11 verbatim)
  balance -> break out of it -> price travels to and TAGS A PRIOR balance's POC
  -> INSTANT REJECTION there -> target is the established balance's boundary
  (VAH if the rejection is from above, VAL if from below).  The source's own
  negative example is the trap: a break that simply keeps going and retests a
  grey zone is a TREND CONTINUATION entry, not a failed auction, and the
  definition exists precisely to separate them.

THE OPERATIONAL DEFINITION — PRE-REGISTERED, NOT SEARCHED
  Every constant below is fixed before the first run and none of them is swept.
  A setup census that tunes its own detector measures the tuner, not the setup.
    ESTABLISHED BALANCE  the previous completed SESSION profile's value area
                         (VAL_e, VAH_e) and POC, from the committed
                         `b4_profiles` objects table.
    BREAK                the session's mid leaves [VAL_e, VAH_e] by > TOL.
    PRIOR BALANCES       SESSION POCs from 2..K sessions back (the established
                         one excluded), on the FAR side of the break — price
                         must have travelled AWAY from the established balance
                         to reach them.
    TAG                  mid comes within TOL of such a prior POC.
    INSTANT REJECTION    within REJ_WINDOW of the tag, mid retraces >= REJ_MOVE
                         back toward the established balance, AND price never
                         ACCEPTS beyond the tagged POC (< ACCEPT_MAX seconds
                         spent past it inside the window).
    ENTRY                the first second the retracement condition is met,
                         side = toward the established balance.
    TARGET               VAH_e from above, VAL_e from below (the source's own
                         target, kept so its 80% claim is testable).
  TOL / REJ_MOVE are fractions of the session's own prior-day ATR14, so the
  detector is scale-free across the three books.

WHAT IS REPORTED
  CENSUS      events per asset per era, per session, hit rate of the source's
              own target (its "four times out of five" claim, measured), and
              the OVERLAP with the existing roster — an event that is already a
              candidate adds nothing to the pool.
  CEILING     the DP money of M-33 events ALONE, and — the number that decides
              it — the MARGINAL ceiling: the one-position DP over the UNION of
              the existing candidate pool and the M-33 events, minus the
              existing pool's own DP ceiling.  If the union adds nothing, the
              setup is redundant with what the roster already generates and the
              idea dies here, cheaply, with a receipt.

CLI
  m33.py --detect [--workers 8]   the event tensor
  m33.py --table                  M33_FAILED_AUCTION.tsv
"""
import argparse
import datetime as dt
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
import m2_common as MC                    # noqa: E402
import m2_delay as MD                     # noqa: E402
import census_common as X                 # noqa: E402
import common as C                        # noqa: E402
import assemble as A                      # noqa: E402

VERSION = "PORT-M2-M33-V1"
OUT_ROOT = os.path.join(MC.M2_ROOT, "m33")
PROFILES = "/workspace/artifacts/cache/port/m1/profiles/profile_objects.tsv"
BINDING = ("E5", "E6", "E7")
ERAS = BINDING + ("E3", "E4")

# ---- PRE-REGISTERED DETECTOR CONSTANTS.  Fixed, never swept. ---------------
K_PRIOR = 20            # sessions back that supply prior balances
TOL_ATR = 0.10          # tag / break tolerance, in prior-day ATR14
REJ_WINDOW = 900        # seconds after the tag in which rejection must happen
REJ_MOVE_ATR = 0.25     # retracement toward the established balance, in ATR
ACCEPT_MAX = 300        # seconds allowed beyond the tagged POC before it is
                        # ACCEPTANCE and the setup is void
COOLDOWN = 1800         # one event per asset-session per this many seconds

ECOLS = ("dec_sec", "side", "poc_px", "target_px", "est_vah", "est_val",
         "tag_sec", "reached_target", "cert_phase", "exit_phase",
         "walled_phase", "cert_target", "exit_target", "atr")
EIDX = {c: i for i, c in enumerate(ECOLS)}


def hb(m):
    sys.stderr.write("[m33 %s] %s\n" % (time.strftime("%H:%M:%S"), m))
    sys.stderr.flush()


class M33Refusal(RuntimeError):
    """A guard fired.  Never downgraded, never silently filtered."""


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def profiles():
    """asset -> sorted [(date, poc, vah, val)] for the SESSION scope."""
    if not os.path.exists(PROFILES):
        raise M33Refusal("no profile objects at %s — b4_profiles never ran"
                         % PROFILES)
    out, cols = {}, None
    with open(PROFILES) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if cols is None:
                cols = f
                continue
            r = dict(zip(cols, f))
            if r.get("scope") != "SESSION":
                continue
            p, v, l = _f(r["poc_px"]), _f(r["vah_px"]), _f(r["val_px"])
            if not (np.isfinite(p) and np.isfinite(v) and np.isfinite(l)):
                continue
            out.setdefault(r["asset"], []).append(
                (dt.date.fromisoformat(r["trade_date"]), p, v, l))
    for a in out:
        out[a].sort(key=lambda z: z[0])
    if not out:
        raise M33Refusal("profile table parsed to ZERO usable SESSION rows")
    return out


def _detect_one(job):
    """The M-33 events of ONE (asset, date8), and their certificates."""
    asset, d8, prior, atr, cost = job
    try:
        sess = A.load_session(asset, int(d8))
        s = sess["s"]
        mult = float(C.ASSETS[asset]["mult"])
        if not prior or not np.isfinite(atr):
            return (asset, int(d8), [], None)
        (e_poc, e_vah, e_val) = prior[0]
        pocs = np.asarray([p for (p, _v, _l) in prior[1:]], dtype=np.float64)
        if pocs.size == 0:
            return (asset, int(d8), [], None)
        tol = TOL_ATR * atr / mult          # ATR is in dollars; work in price
        rej = REJ_MOVE_ATR * atr / mult
        vt = s.vt
        if vt.size == 0:
            return (asset, int(d8), [], None)
        mid = s.vm
        out, last = [], -10 ** 9
        broke_up = broke_dn = False
        for j in range(vt.size):
            t = int(vt[j])
            px = float(mid[j])
            if px > e_vah + tol:
                broke_up = True
            if px < e_val - tol:
                broke_dn = True
            if not (broke_up or broke_dn) or t - last < COOLDOWN:
                continue
            # a prior POC on the FAR side of the break, tagged now
            if broke_up:
                cand = pocs[pocs > e_vah + tol]
                sgn = -1                    # rejection from ABOVE -> sell back
                target = e_vah
            else:
                cand = pocs[pocs < e_val - tol]
                sgn = 1
                target = e_val
            if cand.size == 0:
                continue
            hit = cand[np.abs(cand - px) <= tol]
            if hit.size == 0:
                continue
            poc = float(hit[np.argmin(np.abs(hit - px))])
            # the rejection window
            b = int(np.searchsorted(vt, t + REJ_WINDOW, side="right"))
            w_t, w_p = vt[j:b], mid[j:b]
            if w_p.size < 3:
                continue
            beyond = ((w_p > poc + tol) if broke_up else (w_p < poc - tol))
            if int(beyond.sum()) > ACCEPT_MAX:
                continue                    # ACCEPTED: not a failed auction
            back = (poc - w_p) if broke_up else (w_p - poc)
            ok = np.nonzero(back >= rej)[0]
            if ok.size == 0:
                continue
            ent = int(w_t[ok[0]])
            pc0 = X.next_phase_boundary(s, ent)
            if ent >= pc0:
                continue
            v2, f2, a2, av2 = MD._leg(s, ent, float(s.mid[ent]), sgn, mult)
            val_p, xs_p, wl_p, _e = MD._close_cert(v2, f2, a2, av2, pc0, cost)
            # the setup's OWN contract: exit at the target, else the phase close
            tgt_d = (float(s.mid[ent]) - target) * sgn * -1.0 * mult
            reach = np.nonzero(f2 >= abs(tgt_d))[0] if f2.size else \
                np.zeros(0, dtype=np.int64)
            t_hit = int(v2[reach[0]]) if reach.size else None
            tw = MD._wall_sec(a2, av2)
            if tw is not None and (t_hit is None or tw <= t_hit) and tw <= pc0:
                val_t, xs_t = -MD.WALL_USD - cost, tw
            elif t_hit is not None and t_hit <= pc0:
                val_t, xs_t = abs(tgt_d) - cost, t_hit
            else:
                val_t, xs_t = val_p, xs_p
            r = np.full(len(ECOLS), np.nan)
            r[EIDX["dec_sec"]] = float(ent)
            r[EIDX["side"]] = float(sgn)
            r[EIDX["poc_px"]] = poc
            r[EIDX["target_px"]] = target
            r[EIDX["est_vah"]] = e_vah
            r[EIDX["est_val"]] = e_val
            r[EIDX["tag_sec"]] = float(t)
            r[EIDX["reached_target"]] = 1.0 if (t_hit is not None
                                                and t_hit <= pc0) else 0.0
            r[EIDX["cert_phase"]] = val_p
            r[EIDX["exit_phase"]] = float(xs_p)
            r[EIDX["walled_phase"]] = wl_p
            r[EIDX["cert_target"]] = val_t
            r[EIDX["exit_target"]] = float(xs_t)
            r[EIDX["atr"]] = atr
            out.append(r)
            last = t
        return (asset, int(d8), out, None)
    except Exception as exc:                              # noqa: BLE001
        return (asset, int(d8), [], "%s: %s" % (type(exc).__name__, exc))


def detect(workers=8, out_dir=None):
    import multiprocessing as mp
    out_dir = out_dir or OUT_ROOT
    os.makedirs(out_dir, exist_ok=True)
    D = N.matrix()
    prof = profiles()
    bars = {a: X.load_bars(a) for a in ("SI", "HG", "NKD")}
    sessions = sorted(set(zip(D["asset"].tolist(), D["d8"].tolist())))
    cost_by = {}
    for a, d, c in zip(D["asset"].tolist(), D["d8"].tolist(),
                       D["cost_rt"].tolist()):
        cost_by.setdefault((a, int(d)), c)
    jobs = []
    for asset, d8 in sessions:
        day = dt.date(int(d8) // 10000, int(d8) // 100 % 100, int(d8) % 100)
        hist = [z for z in prof.get(asset, []) if z[0] < day][-(K_PRIOR + 1):]
        hist = list(reversed(hist))         # most recent first
        atr = (bars.get(asset, {}).get(day, {}) or {}).get("ATR14_prev_usd",
                                                           float("nan"))
        jobs.append((asset, int(d8), hist, _f(atr),
                     float(cost_by.get((asset, int(d8)), 0.0))))
    hb("detect: %d sessions, K=%d prior balances, TOL=%.2fATR, REJ=%.2fATR/%ds"
       % (len(jobs), K_PRIOR, TOL_ATR, REJ_MOVE_ATR, REJ_WINDOW))
    rows, errs, t0 = [], [], time.time()
    with mp.Pool(processes=int(workers)) as pool:
        for k, (a_, d_, ev, err) in enumerate(
                pool.imap_unordered(_detect_one, jobs, chunksize=4), 1):
            if err:
                errs.append("%s %d %s" % (a_, d_, err))
            for r in ev:
                rows.append((a_, d_, r))
            if k % 500 == 0 or k == len(jobs):
                el = time.time() - t0
                hb("detect %d/%d %.0fs eta %.0fs events=%d errs=%d"
                   % (k, len(jobs), el, el / k * (len(jobs) - k), len(rows),
                      len(errs)))
    if errs:
        raise M33Refusal("%d session errors — first: %s" % (len(errs),
                                                            errs[0]))
    E = np.vstack([r[2] for r in rows]) if rows else np.zeros((0, len(ECOLS)))
    np.savez(os.path.join(out_dir, "events.npz"),
             cols=np.array(ECOLS), E=E,
             asset=np.array([r[0] for r in rows]),
             d8=np.array([r[1] for r in rows], dtype=np.int64))
    rec = {"version": VERSION, "n_sessions": len(jobs), "n_events": len(rows),
           "events_per_session": len(rows) / max(len(jobs), 1),
           "constants": {"K_PRIOR": K_PRIOR, "TOL_ATR": TOL_ATR,
                         "REJ_WINDOW": REJ_WINDOW,
                         "REJ_MOVE_ATR": REJ_MOVE_ATR,
                         "ACCEPT_MAX": ACCEPT_MAX, "COOLDOWN": COOLDOWN},
           "pre_registered": "every constant fixed before the first run; none "
                             "is swept — a detector tuned on its own census "
                             "measures the tuner",
           "secs": round(time.time() - t0, 1)}
    with open(os.path.join(out_dir, "events.receipt.json"), "w") as fh:
        json.dump(rec, fh, indent=1, sort_keys=True)
    hb("detect: %d events over %d sessions (%.3f/session), %.0fs"
       % (len(rows), len(jobs), rec["events_per_session"], rec["secs"]))
    return E


def load(out_dir=None):
    p = os.path.join(out_dir or OUT_ROOT, "events.npz")
    if not os.path.exists(p):
        raise M33Refusal("no event tensor at %s — run --detect" % p)
    z = np.load(p, allow_pickle=False)
    E = z["E"]
    asset = [str(x) for x in z["asset"].tolist()]
    d8 = z["d8"].astype(np.int64)
    z.close()
    return E, asset, d8


def run_table(out_dir=None):
    import c_c_roster as CC
    import st_common as SC
    D = N.matrix()
    E, asset, d8 = load(out_dir)
    if E.shape[0] == 0:
        raise M33Refusal(
            "M-33 detected ZERO events across the whole corpus — that is a "
            "REPORTABLE CENSUS RESULT and it is printed as one, but it is "
            "also a detector that never fires, so it is raised loudly rather "
            "than written as a quiet zero-row table")
    key = np.array(["%s|%08d" % (a, d) for a, d in zip(asset, d8.tolist())])
    era_of = {}
    for s_, e_ in zip(D["session"].tolist(), D["era_idx"].tolist()):
        era_of.setdefault(s_, int(e_))
    # the existing pool's per-session DP ceiling and item list
    dec = D["dec_sec"].astype(np.int64)
    ex = D["exit_close_sec"].astype(np.int64)
    cv = D["cert_close_usd"].astype(np.float64)
    ok = D["cert_refused"] == 0
    pool = {}
    order = np.lexsort((dec, D["session"]))
    so = D["session"][order]
    st = [0] + (np.flatnonzero(so[1:] != so[:-1]) + 1).tolist()
    for a, b in zip(st, st[1:] + [so.size]):
        idx = order[a:b]
        idx = idx[ok[idx]]
        pool[str(so[a])] = list(zip(dec[idx].tolist(), ex[idx].tolist(),
                                    cv[idx].tolist(), dec[idx].tolist(),
                                    idx.tolist(), idx.tolist()))
    rows = []
    for era in ERAS:
        ei = SC.ERA_IDX[era]
        crit = "BINDING" if era in BINDING else "context"
        sel = np.array([era_of.get(k, -99) == ei for k in key])
        sess_era = sorted(s for s, e in era_of.items() if e == ei)
        n_sess = len(sess_era)
        if n_sess == 0:
            continue
        n_ev = int(sel.sum())
        for contract, ci, xi in (("PHASE_CLOSE", "cert_phase", "exit_phase"),
                                 ("SETUP_TARGET", "cert_target",
                                  "exit_target")):
            alone, union, base, hit, wallr = [], [], [], [], []
            for sk in sess_era:
                items = list(pool.get(sk, []))
                b0, _c = CC.dp_schedule(items)
                base.append(b0)
                m = sel & (key == sk)
                add = []
                for r in E[m]:
                    add.append((int(r[EIDX["dec_sec"]]), int(r[EIDX[xi]]),
                                float(r[EIDX[ci]]), int(r[EIDX["dec_sec"]]),
                                -1, -1))
                    hit.append(float(r[EIDX["reached_target"]]))
                    wallr.append(float(r[EIDX["walled_phase"]]))
                a0, _c = CC.dp_schedule(add) if add else (0.0, [])
                u0, _c = CC.dp_schedule(items + add)
                alone.append(a0)
                union.append(u0)
            base = np.asarray(base)
            alone = np.asarray(alone)
            union = np.asarray(union)
            vals = E[sel, EIDX[ci]] if n_ev else np.zeros(0)
            rows.append([
                era, crit, contract, n_sess, n_ev,
                N._r(n_ev / max(n_sess, 1), 3),
                N._r(float(np.mean(vals)) if vals.size else None),
                N._r(float(np.median(vals)) if vals.size else None),
                N._r(float(np.mean(vals > 0)) if vals.size else None, 4),
                N._r(float(np.mean(hit)) if hit else None, 4),
                N._r(float(np.mean(wallr)) if wallr else None, 4),
                N._r(float(base.mean())), N._r(float(alone.mean())),
                N._r(float(union.mean())),
                N._r(float(union.mean() - base.mean())),
                N._r(float((union.mean() - base.mean()) / base.mean()), 4)
                if base.mean() else ""])
    if not rows:
        raise M33Refusal("M33_FAILED_AUCTION produced ZERO rows — a null "
                         "prints rows, so this is a FAILURE, not a result")
    N.write_tsv(
        "M33_FAILED_AUCTION.tsv",
        ["era", "criterion", "exit_contract", "n_sessions", "n_events",
         "events_per_session", "mean_usd", "median_usd", "win_rate",
         "target_hit_rate", "wall_rate", "pool_dp_ceiling",
         "m33_alone_dp_ceiling", "union_dp_ceiling", "marginal_ceiling_usd",
         "marginal_ceiling_frac"], rows,
        extra=[
            "M-33 FAILED AUCTION — DETECTOR + CENSUS + CEILING.  NOTHING IS "
            "FITTED HERE and no model is built: the brief's rule is ceiling "
            "before build, and this is the ceiling.",
            "THE DECIDING COLUMN IS marginal_ceiling_usd: the one-position DP "
            "over the UNION of the existing roster and the M-33 events, minus "
            "the roster's own DP ceiling.  A setup that only re-finds money "
            "the roster already generates has a marginal ceiling near zero and "
            "dies here regardless of how good its own win rate looks.",
            "target_hit_rate is the source's OWN claim ('four times out of "
            "five') measured against the tape; it is reported whether or not "
            "it survives.",
            "EVERY DETECTOR CONSTANT IS PRE-REGISTERED AND UNSWEPT (K_PRIOR "
            "%d, TOL %.2f ATR, REJ %.2f ATR in %ds, ACCEPT_MAX %ds, COOLDOWN "
            "%ds).  A detector tuned on its own census measures the tuner."
            % (K_PRIOR, TOL_ATR, REJ_MOVE_ATR, REJ_WINDOW, ACCEPT_MAX,
               COOLDOWN),
            "The two exit contracts are the house contract (ride to the phase "
            "close, $900 wall) and the setup's own (exit at the established "
            "balance's boundary), so the setup is never judged only under a "
            "contract its source never proposed."])
    hb("M33_FAILED_AUCTION.tsv: %d rows" % len(rows))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--detect", action="store_true")
    ap.add_argument("--table", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    did = False
    if a.detect:
        detect(workers=a.workers)
        did = True
    if a.table:
        run_table()
        did = True
    if not did:
        ap.print_help()


if __name__ == "__main__":
    main()
