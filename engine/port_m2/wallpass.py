#!/usr/bin/python3
"""PORT M2 — N3 / N6: THE SESSION-LOAD PASS AT THE WALL SECOND.

THE TWO IDEAS, and why they are the reserve's conceptual lead
  N6  STOP-AND-REVERSE.  At a wall-stop, enter the OPPOSITE side for the
      remainder of the phase.  Six extractors confirmed the tape AT THE
      CONFIRMATION SECOND does not separate winner from loser — but a wall-stop
      is not the confirmation second.  It is a LATER, TWO-SIDED MOMENT AT WHICH
      THE LOSER HAS ALREADY DECLARED ITSELF (the wall-pair census measured
      $2,752 of mean separation between the two legs).  Every prior arm tried
      to predict the winner BEFORE the market spoke; this one acts AFTER it
      has.
  N3  RE-ENTRY AFTER WALL.  The same side, re-entered once at the wall second.

BOTH ARE MECHANICAL RULES, NOT FORECASTS.  There is no fitted quantity here at
all, so the numbers below are not hindsight bounds that a model has to earn —
they are what the rule would have paid.  That is stated plainly because it is
unusual for this program and it changes how the table should be read.

THE LIVE CONFLICT THIS SETTLES BY MEASUREMENT
  The FIRST-WALL STOP IS ADOPTED and halts the day on the first walled loss.
  N3 and N6 both re-enter after exactly that event.  They cannot both be right
  in the same regime, and the brief's instruction is to let the ceiling decide
  rather than argue.  Every arm is therefore priced BOTH ways: with the stop
  still armed after the second leg, and with the second leg replacing the stop.

WHY THE SEAT IS AVAILABLE AT ALL (S1b's receipt, and it is load-bearing)
  At the phase close the compliant seat book is SATURATED — forfeits/session =
  0.000, seats/session = 3.000 — so there is normally no spare position.  A
  WALL IS THE ONE EVENT THAT FREES ONE EARLY: the walled leg exits at the wall
  second instead of the phase close, and the position is open for the rest of
  the phase.  N3/N6 spend exactly that freed capacity and nothing else, so they
  stay inside the <=10 trades/day cap by construction.

ARITHMETIC (D-006: imported, never re-typed)
  `m2_delay._leg` for the second leg opened at the wall second, `_wall_sec` for
  the wall itself, `_close_cert` for its phase-close certificate with the $900
  wall LIVE on the new leg too.  `newobj.replay_delayed` does the seating.

CLI
  wallpass.py --pass [--workers 8]   the wall-second second-leg tensor
  wallpass.py --table               WALL_SECOND_LEG.tsv
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
import m2_common as MC                    # noqa: E402
import m2_delay as MD                     # noqa: E402
import census_common as X                 # noqa: E402
import common as C                        # noqa: E402
import assemble as A                      # noqa: E402

VERSION = "PORT-M2-WALLPASS-V1"
OUT_ROOT = os.path.join(MC.M2_ROOT, "wallpass")
BINDING = ("E5", "E6", "E7")
ERAS = BINDING + ("E3", "E4")
SEEDS = (0, 1, 2, 3, 4)
WALL = MD.WALL_USD

WCOLS = ("t_wall", "pc_sec", "rev_cert", "rev_exit", "rev_walled",
         "re_cert", "re_exit", "re_walled", "rem_sec")
WIDX = {c: i for i, c in enumerate(WCOLS)}


def hb(msg):
    sys.stderr.write("[wallpass %s] %s\n" % (time.strftime("%H:%M:%S"), msg))
    sys.stderr.flush()


class WallRefusal(RuntimeError):
    """A guard fired.  Never downgraded, never silently filtered."""


def _one(job):
    asset, d8, rows = job
    try:
        sess = A.load_session(asset, int(d8))
        s = sess["s"]
        mult = float(C.ASSETS[asset]["mult"])
        out = []
        for (i, t, side, cost) in rows:
            t, side, cost = int(t), int(side), float(cost)
            r = np.full(len(WCOLS), np.nan, dtype=np.float64)
            e = MD._first_sane(s, t)
            pc0 = X.next_phase_boundary(s, t)
            r[WIDX["pc_sec"]] = float(pc0)
            if e >= 0 and e < pc0:
                vt, f, at, av = MD._leg(s, e, float(s.mid[e]), side, mult)
                tw = MD._wall_sec(at, av, WALL)
                if tw is not None and tw <= pc0:
                    r[WIDX["t_wall"]] = float(tw)
                    r[WIDX["rem_sec"]] = float(pc0 - tw)
                    j = MD._first_sane(s, tw)
                    if j >= 0 and j < pc0:
                        mid = float(s.mid[j])
                        for tag, sd in (("rev", -side), ("re", side)):
                            v2, f2, a2, av2 = MD._leg(s, j, mid, sd, mult)
                            val, xs, wl, _ev = MD._close_cert(
                                v2, f2, a2, av2, pc0, cost)
                            r[WIDX["%s_cert" % tag]] = val
                            r[WIDX["%s_exit" % tag]] = float(xs)
                            r[WIDX["%s_walled" % tag]] = wl
            out.append((int(i), r))
        return (asset, int(d8), out, None)
    except Exception as exc:                              # noqa: BLE001
        return (asset, int(d8), [], "%s: %s" % (type(exc).__name__, exc))


def build(workers=8, out_dir=None):
    import multiprocessing as mp
    out_dir = out_dir or OUT_ROOT
    os.makedirs(out_dir, exist_ok=True)
    D = N.matrix()
    n = int(D["d8"].size)
    joblist = N._jobs_from_matrix(D)
    W = np.full((n, len(WCOLS)), np.nan, dtype=np.float64)
    t0, errs, done = time.time(), [], 0
    hb("wall pass: %d sessions, %d candidates" % (len(joblist), n))
    with mp.Pool(processes=int(workers)) as pool:
        for k, (a_, d_, rows, err) in enumerate(
                pool.imap_unordered(_one, joblist, chunksize=1), 1):
            if err:
                errs.append("%s %d %s" % (a_, d_, err))
            for i, r in rows:
                W[i] = r
                done += 1
            if k % 500 == 0 or k == len(joblist):
                el = time.time() - t0
                hb("wall %d/%d %.0fs eta %.0fs filled=%d errs=%d"
                   % (k, len(joblist), el, el / k * (len(joblist) - k), done,
                      len(errs)))
    if errs:
        raise WallRefusal("%d session errors — first: %s" % (len(errs),
                                                             errs[0]))
    m = np.isfinite(W[:, WIDX["t_wall"]])
    rev = W[m, WIDX["rev_cert"]]
    re_ = W[m, WIDX["re_cert"]]
    rec = {"version": VERSION, "n": n, "n_walled": int(m.sum()),
           "walled_frac": float(m.mean()),
           "rev_mean_usd": float(np.nanmean(rev)) if rev.size else None,
           "rev_median_usd": float(np.nanmedian(rev)) if rev.size else None,
           "rev_win_rate": float(np.nanmean(rev > 0)) if rev.size else None,
           "reentry_mean_usd": float(np.nanmean(re_)) if re_.size else None,
           "reentry_win_rate": float(np.nanmean(re_ > 0)) if re_.size else None,
           "median_remaining_sec": float(np.nanmedian(W[m, WIDX["rem_sec"]])),
           "arithmetic": "m2_delay._leg/_wall_sec/_close_cert (imported)",
           "secs": round(time.time() - t0, 1)}
    np.savez(os.path.join(out_dir, "wall.npz"), cols=np.array(WCOLS), W=W)
    with open(os.path.join(out_dir, "wall.receipt.json"), "w") as fh:
        json.dump(rec, fh, indent=1, sort_keys=True)
    hb("wall pass: %d walled (%.3f); REVERSAL mean $%.2f win %.3f; "
       "RE-ENTRY mean $%.2f win %.3f; median remaining %.0fs"
       % (rec["n_walled"], rec["walled_frac"], rec["rev_mean_usd"] or 0,
          rec["rev_win_rate"] or 0, rec["reentry_mean_usd"] or 0,
          rec["reentry_win_rate"] or 0, rec["median_remaining_sec"]))
    return W


_W = {}


def load(out_dir=None):
    if "W" in _W:
        return _W["W"]
    p = os.path.join(out_dir or OUT_ROOT, "wall.npz")
    if not os.path.exists(p):
        raise WallRefusal("no wall tensor at %s — run --pass" % p)
    z = np.load(p, allow_pickle=False)
    if tuple(str(x) for x in z["cols"].tolist()) != tuple(WCOLS):
        raise WallRefusal("wall tensor column mismatch")
    _W["W"] = z["W"]
    z.close()
    return _W["W"]


# =============================================================== the arms ===
def apply_second_leg(D, rows, W, kind, stop_after=True):
    """Rebuild each session's seat sequence with the second leg inserted.

    `kind` in {'NONE', 'REV', 'RE'}.  'NONE' with stop_after=True IS the adopted
    first-wall stop, which is the red-first anchor: it must reproduce
    `stacked_final.apply_stop(..., 'STOP_WALL1')` exactly.

    The second leg occupies the position from the wall second to its own exit,
    so the seats that would have fired inside that window are FORFEITED exactly
    as the replay's occupancy rule forfeits them.  Nothing here adds a seat the
    <=10/day cap did not already allow: the wall freed the position early and
    the second leg spends that freed time and no more.
    """
    ci = {"REV": "rev_cert", "RE": "re_cert"}.get(kind)
    xi = {"REV": "rev_exit", "RE": "re_exit"}.get(kind)
    out = []
    for r in rows:
        kept, n_wall, extra = [], 0, 0
        open_until = -1
        for (i, dl, v) in r["seats"]:
            if open_until >= 0 and int(D["dec_sec"][i]) <= open_until:
                continue                    # forfeited by the second leg
            kept.append((i, dl, v))
            walled = bool(D["walled"][i] > 0) and float(v) < 0
            if not walled:
                continue
            n_wall += 1
            tw = W[i, WIDX["t_wall"]]
            if ci is not None and np.isfinite(tw) \
                    and np.isfinite(W[i, WIDX[ci]]):
                kept.append((i, -1, float(W[i, WIDX[ci]])))
                open_until = int(W[i, WIDX[xi]])
                extra += 1
            if stop_after:
                break                       # the day is over after the wall
        out.append({"session": r["session"],
                    "realised": float(sum(x[2] for x in kept)),
                    "n_takes": r["n_takes"], "n_seated": len(kept),
                    "n_forfeited": r["n_forfeited"],
                    "n_refused": r["n_refused"], "seats": kept,
                    "n_second_legs": extra, "n_wall": n_wall})
    return out


def run_table(eras=ERAS, out_dir=None):
    import stacked_final as SF
    import champ_floor as CF
    import curriculum as CU
    import confidence as CO
    D, P = CF.boot()
    W = load(out_dir)
    ceil = CO.ceilings()
    ARMS = (("INCUMBENT_STOP", "NONE", True),
            ("N6_REVERSE_THEN_STOP", "REV", True),
            ("N6_REVERSE_NO_STOP", "REV", False),
            ("N3_REENTER_THEN_STOP", "RE", True),
            ("N3_REENTER_NO_STOP", "RE", False),
            ("NO_STOP_AT_ALL", "NONE", False))
    rows, red = [], None
    for era in eras:
        crit = "BINDING" if era in BINDING else "context"
        ev = N.deployable(D, N.era_rows(D, era))
        n_ = N.committed_policy()[era][1]
        base = {}
        for sd in SEEDS:
            fp = os.path.join(CU._sdir(), "FOLD_%s_%d.npy" % (era, sd))
            if not os.path.exists(fp):
                raise WallRefusal("missing folded member %s" % fp)
            sc = np.load(fp).astype(np.float64)
            base[sd] = N.replay_delayed(
                D, N.top_per_cell_score(D, ev, sc, n_), P)
        inc = None
        for name, kind, stop in ARMS:
            vals, nsl, nse = [], [], []
            for sd in SEEDS:
                rr = apply_second_leg(D, base[sd], W, kind, stop)
                a = N.read_rows(D, rr)
                vals.append(a["usd_per_session"])
                nsl.append(sum(r["n_second_legs"] for r in rr)
                           / max(len(rr), 1))
                nse.append(a["n_seated"] / max(a["n_sessions"], 1))
                if name == "INCUMBENT_STOP" and sd == 0:
                    ref = N.read_rows(D, SF.apply_stop(
                        D, base[sd], "STOP_WALL1"))["usd_per_session"]
                    red = abs(ref - a["usd_per_session"])
                    if red > 1e-6:
                        raise WallRefusal(
                            "RED-FIRST FAILED: the NONE/stop arm is $%.6f "
                            "from stacked_final.apply_stop($%.2f vs $%.2f) — "
                            "the seat rebuild is not the committed stop"
                            % (red, a["usd_per_session"], ref))
            v = np.asarray(vals, dtype=np.float64)
            if inc is None:
                inc = v
            d = v.mean() - inc.mean()
            cl = ceil.get("%s|ALL" % era)
            aim = 0.80 * cl if cl else None
            rows.append([era, crit, name, int(v.size), N._r(v.mean()),
                         N._r(v.std()), N._r(float(np.mean(nse)), 3),
                         N._r(float(np.mean(nsl)), 3), N._r(cl),
                         N._r(v.mean() / cl, 4) if cl else "",
                         N._r(aim), N._r(v.mean() - aim) if aim else "",
                         N._r(d), N._r(d - v.std()),
                         "YES" if (d - v.std()) > 0 else "no"])
        hb("wall table: %s done" % era)
    if not rows:
        raise WallRefusal("WALL_SECOND_LEG produced ZERO rows — a null prints "
                          "rows, so this is a FAILURE, not a result")
    N.write_tsv(
        "WALL_SECOND_LEG.tsv",
        ["era", "criterion", "arm", "n_seeds", "usd_per_session", "sd_usd",
         "seats_per_session", "second_legs_per_session",
         "entry_foresight_ceiling", "capture_of_ceiling", "aim_08ceiling",
         "gap_to_aim", "delta_vs_incumbent", "delta_minus_sd", "promotes"],
        rows,
        extra=[
            "N6 (stop-and-reverse) and N3 (re-entry) priced at the WALL SECOND "
            "on the deployed folded members.  MECHANICAL RULES, NOT FORECASTS "
            "— there is no fitted quantity in this table, so these are what "
            "the rules would have paid, not bounds a model must earn.",
            "RED FIRST: the INCUMBENT_STOP arm rebuilds the seat sequence with "
            "no second leg and MUST equal stacked_final.apply_stop(STOP_WALL1) "
            "to the cent; the run REFUSES otherwise.",
            "THE ADOPTED FIRST-WALL STOP AND THESE IDEAS CONFLICT BY "
            "CONSTRUCTION, so each is priced BOTH with the stop still armed "
            "after the second leg and with the second leg replacing it.  "
            "NO_STOP_AT_ALL is the fourth corner and is a RISK-CONTRACT "
            "question (D-030 drawdown), never adopted on dollars alone.",
            "THE SEAT IS FREE BY CONSTRUCTION: S1b measured the compliant book "
            "SATURATED at the phase close (0.000 forfeits/session), and a wall "
            "is the one event that releases a position early.  The second leg "
            "spends only that released time, so the <=10 trades/day cap is "
            "never touched."])
    hb("WALL_SECOND_LEG.tsv: %d rows" % len(rows))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pass", dest="do_pass", action="store_true")
    ap.add_argument("--table", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    did = False
    if a.do_pass:
        build(workers=a.workers)
        did = True
    if a.table:
        run_table()
        did = True
    if not did:
        ap.print_help()


if __name__ == "__main__":
    main()
