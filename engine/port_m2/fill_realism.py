#!/usr/bin/python3
"""PORT M2 — FILL-REALISM CENSUS (leak-audit scope add, item 5).

THE TWO ASSUMPTIONS BEING TESTED, both of which live in the certificate
arithmetic rather than in any model:

  (a) ENTRY AT THE MID.  `m2_delay._paths_one` opens the leg at
      `entry_t = s.mid[t]` — the second-grid MIDPOINT at the decision second —
      and charges `cost_rt` for the round trip.  `cost_rt` is
      `c_a_cost`'s SESSION-MEDIAN two-sided spread plus $5 of fees
      (`census_a_cost.tsv`, phase=ALL).  A marketable order does not fill at
      the mid; it lifts the offer.  The model is therefore right only if the
      spread AT THE DECISION SECOND is no wider than the session median, and
      only if the quote does not move while the order is in flight.
      Candidates fire on confirmations — i.e. immediately after a move — which
      is exactly when spreads are widest.  Measured here against a
      phase-matched random-second control.

  (b) THE WALL FILLS AT EXACTLY -$900.  `m2_delay._close_cert` books
      `-W - cost` the moment the adverse skeleton reaches $900.  The skeleton
      is a ONE-SECOND MID series, so two things are unpriced: the mid can
      already be well past $900 in the second the crossing is first observed
      (gap-through), and the stop fills on the far touch, not the mid.

Both are measured as adjustments to the committed $/session.

NOTE ON THE DENOMINATOR: the seats priced here are the ones the committed
policy chose, and P1 of this audit finds that policy to be a lookahead
(`LEAK_AUDIT.md`).  These adjustments are therefore corrections to a number
that is separately retracted; they are reported per-trade as well as
per-session so they survive the re-anchoring.
"""
import argparse
import json
import os
import sys
import time

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, "/workspace/engine/port_m2/seqtest", "/workspace/engine/port_m0",
           "/workspace/engine/port_m1", "/workspace/engine/port_m3",
           "/workspace/artifacts/cache/pylibs"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import newobj as N                        # noqa: E402
import champ_floor as CF                  # noqa: E402
import stacked_final as SF                # noqa: E402
import m2_delay as MD                     # noqa: E402
import assemble as A                      # noqa: E402
import common as C                        # noqa: E402
import census_common as X                 # noqa: E402
import tape as TAPE                       # noqa: E402

ERAS = ("E3", "E4", "E5", "E6", "E7")
WALL = MD.WALL_USD
CTRL_PER_SEAT = 20                        # phase-matched random seconds
LATENCIES_MS = (0, 100, 200, 300)
RNG_SEED = 20260821


# ------------------------------------------------------------------ seats ---
def deployed_seats(D, eras=ERAS):
    """The committed arm's seats: (row, era) for every seated take."""
    out = []
    for era in eras:
        fam = SF._load(era)
        S = [x for v in fam.values() for x in v]
        if not S:
            continue
        ens = np.nanmean(np.vstack(S), axis=0)
        ev = N.deployable(D, N.era_rows(D, era))
        n_ = N.committed_policy()[era][1]
        tk = N.top_per_cell_score(D, ev, ens, n_)
        rep = N.replay_delayed(D, tk, CF.boot()[1])
        for r in rep:
            for (i, _dl, _v) in r["seats"]:
                out.append((int(i), era))
    return out


# ------------------------------------------------------------- the worker ---
def _one_session(job):
    """All seats of one (asset, d8): entry realism + wall gap-through."""
    asset, d8, seats = job
    try:
        sess = A.load_session(asset, int(d8))
        s = sess["s"]
        mult = float(C.ASSETS[asset]["mult"])
        tick = float(C.ASSETS[asset]["tick_usd"])
        vt = s.vt
        med_spread = float(np.median(s.spread_usd[vt])) if vt.size else float("nan")
        rng = np.random.default_rng(RNG_SEED + int(d8))
        rows = []
        for (i, era, dec, side, cost, cert) in seats:
            dec = int(dec)
            side = int(side)
            rec = {"row": i, "era": era, "asset": asset, "d8": int(d8),
                   "dec_sec": dec, "side": side, "cost_rt": float(cost),
                   "cert_close_usd": float(cert), "tick_usd": tick,
                   "med_spread_usd": med_spread,
                   "spread_entry_usd": float(s.spread_usd[dec]),
                   "bid_sz_entry": float(s.bid_sz[dec]),
                   "ask_sz_entry": float(s.ask_sz[dec]),
                   "phase": int(s.phase_tag[dec])}
            # phase-matched random-second control
            pm = np.nonzero((s.phase_tag == s.phase_tag[dec]) & s.valid)[0]
            if pm.size:
                pick = rng.choice(pm, size=min(CTRL_PER_SEAT, pm.size),
                                  replace=False)
                rec["spread_ctrl_usd"] = float(np.mean(s.spread_usd[pick]))
                rec["spread_ctrl_med_usd"] = float(np.median(s.spread_usd[pick]))
            else:
                rec["spread_ctrl_usd"] = float("nan")
                rec["spread_ctrl_med_usd"] = float("nan")
            # --- the leg, exactly as the certificate builds it
            entry_mid = float(s.mid[dec])
            vt0, f0, at0, av0 = MD._leg(s, dec, entry_mid, side, mult)
            pc = X.next_phase_boundary(s, dec)
            rec["pc_sec"] = int(pc)
            w = int(np.searchsorted(av0, np.float32(WALL), side="left"))
            if w < av0.size and int(at0[w]) <= pc:
                t_wall = int(at0[w])
                rec["walled"] = 1
                rec["t_wall"] = t_wall
                # the adverse the mid had ALREADY reached when the crossing
                # was first observed: the certificate books -900 regardless.
                rec["adverse_at_cross_usd"] = float(av0[w])
                rec["gap_over_wall_usd"] = float(av0[w]) - WALL
                rec["gap_over_wall_ticks"] = (float(av0[w]) - WALL) / tick
                rec["prev_adverse_usd"] = float(av0[w - 1]) if w else 0.0
                rec["one_step_jump_usd"] = float(av0[w]) - (
                    float(av0[w - 1]) if w else 0.0)
                rec["spread_at_wall_usd"] = float(s.spread_usd[t_wall])
                rec["exit_sec"] = t_wall
            else:
                rec["walled"] = 0
                rec["t_wall"] = -1
                for k in ("adverse_at_cross_usd", "gap_over_wall_usd",
                          "gap_over_wall_ticks", "prev_adverse_usd",
                          "one_step_jump_usd", "spread_at_wall_usd"):
                    rec[k] = float("nan")
                rec["exit_sec"] = int(pc)
            xs = int(rec["exit_sec"])
            rec["spread_exit_usd"] = float(s.spread_usd[min(xs, s.n - 1)])
            rows.append(rec)
        return rows, None
    except Exception as exc:                                  # loud, not silent
        return [], "%s|%d: %s: %s" % (asset, d8, type(exc).__name__, exc)


# -------------------------------------------------------------- sub-second ---
def _subsec_one(job):
    """Latency realism from the cached MBP-1 events around the entry second."""
    asset, d8, seats = job
    npz_p, json_p = TAPE._paths(asset, int(d8))
    if not (os.path.exists(npz_p) and os.path.exists(json_p)):
        return [], "%s|%d: no cached tape" % (asset, d8)
    try:
        with open(json_p) as fh:
            meta = json.load(fh)
        z = np.load(npz_p, allow_pickle=False)
        ts = z["ts_ns"]
        bpx, apx = z["bid_px"], z["ask_px"]
        bsz, asz = z["bid_sz"], z["ask_sz"]
        z.close()
        o = int(meta["open_utc"])
        scale = float(C.ASSETS[asset]["px_scale"])
        mult = float(C.ASSETS[asset]["mult"])
        tick = float(C.ASSETS[asset]["tick_usd"])
        rows = []
        for (i, era, dec, side, cost, cert) in seats:
            t0 = (o + int(dec)) * 1_000_000_000
            k0 = int(np.searchsorted(ts, t0, side="right")) - 1
            if k0 < 0:
                continue
            # the mid the certificate assumes it gets
            mid0 = (int(bpx[k0]) + int(apx[k0])) / 2.0 * scale
            rec = {"row": i, "era": era, "asset": asset, "d8": int(d8),
                   "side": side, "tick_usd": tick,
                   "n_events_2s_before": int(k0 - int(np.searchsorted(
                       ts, t0 - 2_000_000_000, side="left"))),
                   "spread_ticks_at_dec": (int(apx[k0]) - int(bpx[k0]))
                   * scale * mult / tick}
            for L in LATENCIES_MS:
                k = int(np.searchsorted(ts, t0 + L * 1_000_000,
                                        side="right")) - 1
                k = max(k, 0)
                touch = (int(apx[k]) if side > 0 else int(bpx[k])) * scale
                tsz = (int(asz[k]) if side > 0 else int(bsz[k]))
                # a marketable order pays (touch - mid0) * side * mult
                rec["slip_%dms_usd" % L] = (touch - mid0) * side * mult
                rec["touch_sz_%dms" % L] = float(tsz)
                rec["touch_thin_%dms" % L] = float(tsz < 1)
            rows.append(rec)
        return rows, None
    except Exception as exc:
        return [], "%s|%d: %s: %s" % (asset, d8, type(exc).__name__, exc)


# ------------------------------------------------------------------- main ---
def _jobs(D, seats):
    by = {}
    for (i, era) in seats:
        a = str(D["asset"][i])
        d8 = int(D["d8"][i])
        by.setdefault((a, d8), []).append(
            (i, era, int(D["dec_sec"][i]), int(D["side"][i]),
             float(D["cost_rt"][i]), float(D["cert_close_usd"][i])))
    return [(a, d, v) for (a, d), v in sorted(by.items())]


def run(eras=ERAS, workers=3, subsec_cap=None):
    import multiprocessing as mp
    D, _P = CF.boot()
    seats = deployed_seats(D, eras)
    N.hb("FILL_REALISM: %d seats over %s" % (len(seats), ",".join(eras)))
    jobs = _jobs(D, seats)
    N.hb("FILL_REALISM: %d (asset,session) jobs" % len(jobs))

    rows, errs = [], []
    t0 = time.time()
    with mp.Pool(processes=int(workers)) as pool:
        for k, (r, e) in enumerate(pool.imap_unordered(_one_session, jobs,
                                                       chunksize=8)):
            rows.extend(r)
            if e:
                errs.append(e)
            if (k + 1) % 200 == 0:
                N.hb("FILL_REALISM stage-1 %d/%d (%.0fs, %d errors)"
                     % (k + 1, len(jobs), time.time() - t0, len(errs)))
    if errs:
        N.hb("FILL_REALISM stage-1: %d SESSION ERRORS, first: %s"
             % (len(errs), errs[0]))
        if len(errs) > 0.02 * len(jobs):
            raise SystemExit("FILL_REALISM: %d/%d sessions failed — refusing "
                             "to report on a holed census" % (len(errs),
                                                              len(jobs)))
    N.hb("FILL_REALISM stage-1 done: %d seat records" % len(rows))

    sub, serrs = [], []
    sjobs = jobs if subsec_cap is None else jobs[:int(subsec_cap)]
    with mp.Pool(processes=int(workers)) as pool:
        for k, (r, e) in enumerate(pool.imap_unordered(_subsec_one, sjobs,
                                                       chunksize=8)):
            sub.extend(r)
            if e:
                serrs.append(e)
            if (k + 1) % 200 == 0:
                N.hb("FILL_REALISM stage-2 %d/%d (%d misses)"
                     % (k + 1, len(sjobs), len(serrs)))
    N.hb("FILL_REALISM stage-2 done: %d seat records, %d sessions without "
         "cached tape" % (len(sub), len(serrs)))
    _report(rows, sub, len(jobs), errs, serrs)
    return rows, sub


def _q(a, p):
    a = np.asarray([x for x in a if np.isfinite(x)], dtype=np.float64)
    return float(np.percentile(a, p)) if a.size else float("nan")


def _m(a):
    a = np.asarray([x for x in a if np.isfinite(x)], dtype=np.float64)
    return float(a.mean()) if a.size else float("nan")


def _report(rows, sub, n_jobs, errs, serrs):
    assets = sorted({r["asset"] for r in rows})
    n_sess_by = {}
    for r in rows:
        n_sess_by.setdefault(r["asset"], set()).add((r["d8"],))

    # ---------- (a) ENTRY
    ecols = ["asset", "bucket", "n_seats", "spread_entry_mean_usd",
             "spread_entry_p50", "spread_entry_p90", "spread_ctrl_mean_usd",
             "excess_vs_ctrl_usd", "med_session_spread_usd",
             "cost_rt_mean_usd", "entry_halfspread_mean_usd",
             "modeled_halfspread_mean_usd", "excess_entry_slip_usd",
             "excess_entry_slip_ticks", "spread_exit_mean_usd",
             "excess_roundtrip_slip_usd", "excess_rt_per_session_usd"]
    erows = []
    for a in assets + ["ALL"]:
        sel = [r for r in rows if a == "ALL" or r["asset"] == a]
        if not sel:
            continue
        rat = np.asarray([r["spread_entry_usd"] / r["med_spread_usd"]
                          if r["med_spread_usd"] else np.nan for r in sel])
        cut = np.nanmedian(rat)
        for bucket, ss in (("ALL", sel),
                           ("BURST", [r for r, x in zip(sel, rat) if x > cut]),
                           ("QUIET", [r for r, x in zip(sel, rat) if x <= cut])):
            if not ss:
                continue
            se = [r["spread_entry_usd"] for r in ss]
            sc = [r["spread_ctrl_usd"] for r in ss]
            ms = [r["med_spread_usd"] for r in ss]
            tk = [r["tick_usd"] for r in ss]
            ehs = [x / 2.0 for x in se]
            mhs = [x / 2.0 for x in ms]
            ex = [(p - q) for p, q in zip(ehs, mhs)]
            sx = [r["spread_exit_usd"] for r in ss]
            # the whole round trip: cost_rt allows ONE session-median spread;
            # a taker pays half the prevailing spread on each side.
            rt = [(p + q) / 2.0 - m for p, q, m in zip(se, sx, ms)]
            nsess_b = len({(r["asset"], r["d8"]) for r in ss})
            erows.append([a, bucket, len(ss), round(_m(se), 2),
                          round(_q(se, 50), 2), round(_q(se, 90), 2),
                          round(_m(sc), 2), round(_m(se) - _m(sc), 2),
                          round(_m(ms), 2),
                          round(_m([r["cost_rt"] for r in ss]), 2),
                          round(_m(ehs), 2), round(_m(mhs), 2),
                          round(_m(ex), 2), round(_m(ex) / _m(tk), 3),
                          round(_m(sx), 2), round(_m(rt), 2),
                          round(_m(rt) * len(ss) / max(nsess_b, 1), 2)])
    N.write_tsv("FILL_ENTRY.tsv", ecols, erows, extra=[
        "(a) ENTRY SLIPPAGE vs the cost_rt assumption.  The certificate opens "
        "at the second-grid MID and charges cost_rt = session-median two-sided "
        "spread + $5 for the round trip, i.e. HALF the session median per "
        "side.  A taker pays half the spread PREVAILING AT THE DECISION "
        "SECOND.",
        "excess_entry_slip_usd = (spread at decision - session median "
        "spread)/2, the per-trade dollars the cost model does not charge on "
        "the entry side.",
        "spread_ctrl = the same session's spread at %d random VALID seconds "
        "of the SAME PHASE — the matched control that separates 'candidates "
        "fire in wide markets' from 'this session was wide'."
        % CTRL_PER_SEAT,
        "BURST/QUIET split at the per-asset median of "
        "spread_at_decision / session-median spread."])

    # ---------- (b) WALL
    wcols = ["asset", "n_seats", "n_walled", "walled_rate",
             "gap_over_wall_mean_usd", "gap_p50", "gap_p90", "gap_max",
             "frac_gap_gt_1tick", "frac_gap_gt_2tick",
             "one_step_jump_mean_usd", "spread_at_wall_mean_usd",
             "exit_halfspread_usd", "total_wall_excess_mean_usd",
             "wall_excess_per_seat_usd", "wall_excess_per_session_usd"]
    wrows = []
    n_sess_total = len({(r["asset"], r["d8"]) for r in rows})
    for a in assets + ["ALL"]:
        sel = [r for r in rows if a == "ALL" or r["asset"] == a]
        wl = [r for r in sel if r["walled"] == 1]
        if not sel:
            continue
        nsess = len({(r["asset"], r["d8"]) for r in sel})
        if wl:
            gap = [r["gap_over_wall_usd"] for r in wl]
            tk = [r["tick_usd"] for r in wl]
            gt1 = float(np.mean([g > t for g, t in zip(gap, tk)]))
            gt2 = float(np.mean([g > 2 * t for g, t in zip(gap, tk)]))
            ehs = [r["spread_at_wall_usd"] / 2.0 for r in wl]
            tot = [g + h for g, h in zip(gap, ehs)]
            per_seat = _m(tot) * len(wl) / len(sel)
            per_sess = _m(tot) * len(wl) / max(nsess, 1)
            wrows.append([a, len(sel), len(wl),
                          round(len(wl) / len(sel), 4),
                          round(_m(gap), 2), round(_q(gap, 50), 2),
                          round(_q(gap, 90), 2), round(max(gap), 2),
                          round(gt1, 4), round(gt2, 4),
                          round(_m([r["one_step_jump_usd"] for r in wl]), 2),
                          round(_m([r["spread_at_wall_usd"] for r in wl]), 2),
                          round(_m(ehs), 2), round(_m(tot), 2),
                          round(per_seat, 2), round(per_sess, 2)])
        else:
            wrows.append([a, len(sel), 0] + [""] * (len(wcols) - 3))
    N.write_tsv("FILL_WALL.tsv", wcols, wrows, extra=[
        "(b) WALL GAP-THROUGH.  m2_delay._close_cert books exactly -$900 - "
        "cost_rt the moment the ONE-SECOND MID adverse skeleton reaches $900.",
        "gap_over_wall_usd = the adverse the mid had ALREADY reached in the "
        "second the crossing was first observed, minus $900 — dollars the "
        "certificate does not charge.",
        "exit_halfspread_usd = half the spread prevailing at the wall second: "
        "a stop fills on the far touch, not the mid, and cost_rt has already "
        "spent its allowance on the session median.",
        "wall_excess_per_session_usd = the $/session correction implied by "
        "these seats."])

    # ---------- sub-second latency
    if sub:
        scols = ["asset", "bucket", "n", "spread_ticks_at_dec_mean",
                 "n_events_2s_mean"] + \
            ["slip_%dms_mean_usd" % L for L in LATENCIES_MS] + \
            ["slip_%dms_p90_usd" % L for L in LATENCIES_MS] + \
            ["drift_0_to_300ms_usd", "touch_thin_300ms_rate"]
        srows = []
        sassets = sorted({r["asset"] for r in sub})
        for a in sassets + ["ALL"]:
            ss0 = [r for r in sub if a == "ALL" or r["asset"] == a]
            if not ss0:
                continue
            ev = np.asarray([r["n_events_2s_before"] for r in ss0],
                            dtype=np.float64)
            cut = np.median(ev)
            for bucket, ss in (("ALL", ss0),
                               ("BURST", [r for r, x in zip(ss0, ev) if x > cut]),
                               ("QUIET", [r for r, x in zip(ss0, ev) if x <= cut])):
                if not ss:
                    continue
                row = [a, bucket, len(ss),
                       round(_m([r["spread_ticks_at_dec"] for r in ss]), 3),
                       round(_m([r["n_events_2s_before"] for r in ss]), 1)]
                row += [round(_m([r["slip_%dms_usd" % L] for r in ss]), 2)
                        for L in LATENCIES_MS]
                row += [round(_q([r["slip_%dms_usd" % L] for r in ss], 90), 2)
                        for L in LATENCIES_MS]
                row += [round(_m([r["slip_300ms_usd"] - r["slip_0ms_usd"]
                                  for r in ss]), 2),
                        round(_m([r["touch_thin_300ms"] for r in ss]), 4)]
                srows.append(row)
        N.write_tsv("FILL_LATENCY.tsv", scols, srows, extra=[
            "SUB-SECOND REALISM from the cached MBP-1 event stream.  slip_Lms "
            "= (far touch at decision_second + L milliseconds - the MID the "
            "certificate assumes) x side x multiplier: the dollars a "
            "marketable 1-lot actually gives up, INCLUDING any quote movement "
            "while the order is in flight.",
            "drift_0_to_300ms = how much of that is the quote moving away "
            "during the flight, as opposed to the half-spread that was there "
            "at the decision second.",
            "BURST/QUIET split at the median event count in the 2 seconds "
            "before the decision second.",
            "%d sessions had no cached tape and are excluded (counted, not "
            "silently dropped)." % len(serrs)])
    N.hb("FILL_REALISM: wrote FILL_ENTRY.tsv, FILL_WALL.tsv, FILL_LATENCY.tsv "
         "(%d sessions, %d stage-1 errors, %d tape misses)"
         % (n_sess_total, len(errs), len(serrs)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eras", default=",".join(ERAS))
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--subsec-cap", type=int, default=None)
    a = ap.parse_args()
    run(tuple(x for x in a.eras.split(",") if x), a.workers, a.subsec_cap)


if __name__ == "__main__":
    main()
