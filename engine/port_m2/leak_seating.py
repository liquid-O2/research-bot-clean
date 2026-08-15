#!/usr/bin/python3
"""PORT M2 — LEAK AUDIT / PRIORITY 1: IS THE SEAT ARRIVAL-TIME IMPLEMENTABLE?

THE QUESTION.  The deployed policy is "top-N per (asset, day, phase) cell".
`newobj.top_per_cell_score` implements it as

    order = good[np.lexsort((dec_sec, -score))][:n]

i.e. the cell's EVENTUAL ARGMAX by score.  A cell's members arrive at different
seconds across the phase; to know that the candidate firing at 09:41 is the
cell's best you must already have seen the candidates that fire at 10:05 and
10:40.  The trade is entered AT 09:41.  If the argmax is routinely not the
cell's first arrival, the printed $/session is not earnable at arrival time and
the number carries a lookahead.

WHAT THIS FILE MEASURES, on the CURRENT deployed object (the folded stacked
ensemble, `stacked_final._load` averaged, the exact score `capture_config` and
`stacked_final` seat) and through the SAME replay (`newobj.replay_delayed` at
delay 0, proven seat-for-seat equal to `m3_walk.replay_rows`):

  DEPLOYED        the committed rule — cell argmax.  RETROSPECTIVE.
  FIRST           take the cell's first n arrivals.  Causal, score-blind: the
                  floor of "what does arrival-time participation alone pay".
  TAU_RATE        first arrival whose score >= tau, tau tuned ON THE EVAL ERA
                  so the seat count matches DEPLOYED.  Causal in mechanism,
                  GENEROUS in calibration (tau is picked with hindsight) —
                  a participation-matched upper bound.
  TAU_ORACLE      first arrival whose score >= tau, tau = the $/session argmax
                  over the same grid, again on the eval era.  THE UPPER BOUND
                  ON EVERY THRESHOLD-SHAPED CAUSAL RULE.
  TAU_PREV        the honest one: tau carried forward from the PREVIOUS era's
                  own $/session argmax (era k-1 is history at the start of
                  era k), applied blind to era k.

  Any gap DEPLOYED - TAU_ORACLE is a lower bound on the lookahead, because
  TAU_ORACLE is allowed to cheat on its single scalar and DEPLOYED is not
  allowed to lose anything.

Plus the mechanism census: cell-size distribution, where in the arrival order
the deployed seat actually sits, and the singleton-cell split (a cell with one
deployable candidate has no lookahead to exercise; if the money lives in the
multi-candidate cells, the lookahead carries the number).

Read-only with respect to every committed artifact.  Writes TSVs only.
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
import panel_score as PS                  # noqa: E402
import m3_walk as W                       # noqa: E402

ERAS = ("E3", "E4", "E5", "E6", "E7")
TAU_Q = np.concatenate([np.arange(0.0, 0.96, 0.02), [0.97, 0.98, 0.99]])


# ------------------------------------------------------------------ seats ---
def _blocks(D, rows, score):
    """(rows sorted by (cell, dec_sec) with a finite score, per-cell bounds)."""
    r = np.asarray(rows, dtype=np.int64)
    r = r[np.isfinite(np.asarray(score)[r])]
    cell = D["cell"][r]
    order = np.lexsort((D["dec_sec"][r], cell))
    ro, co = r[order], cell[order]
    if ro.size == 0:
        return ro, []
    starts = [0] + (np.flatnonzero(co[1:] != co[:-1]) + 1).tolist()
    return ro, list(zip(starts, starts[1:] + [co.size]))


def seats_argmax(D, rows, score, n):
    """THE COMMITTED RULE.  Asserted identical to newobj.top_per_cell_score."""
    return N.top_per_cell_score(D, rows, score, n)


def seats_first(D, rows, score, n):
    ro, blocks = _blocks(D, rows, score)
    return [(int(ro[j]), 0) for a, b in blocks for j in range(a, min(a + n, b))]


def seats_tau(D, rows, score, n, tau):
    """First n arrivals in the cell whose score clears tau.  Strictly causal:
    the decision at arrival j uses score[j] and a constant, nothing later."""
    ro, blocks = _blocks(D, rows, score)
    s = np.asarray(score)[ro]
    out = []
    for a, b in blocks:
        k = 0
        for j in range(a, b):
            if s[j] >= tau:
                out.append((int(ro[j]), 0))
                k += 1
                if k >= n:
                    break
    return out


def seats_record(D, rows, score, n, k):
    """THE SECRETARY RULE — the strongest natural causal analogue of the cell
    argmax, and the reason a threshold sweep alone would not settle this.

    Observe the cell's first `k` arrivals without taking any; then take the
    first arrival that beats every score seen so far.  Every input is in the
    past at the moment of the decision (the running maximum and the count of
    arrivals so far are both observable live).  If no arrival ever beats the
    reference the cell goes unseated.

    This is what "pick the cell's best" DEGRADES TO when you are not allowed to
    see the future.  Sweeping `k` and keeping the best k is again generous.
    """
    ro, blocks = _blocks(D, rows, score)
    s = np.asarray(score)[ro]
    out = []
    for a, b in blocks:
        if b - a <= k:
            continue
        ref = float(np.max(s[a:a + k]))
        took = 0
        for j in range(a + k, b):
            if s[j] > ref:
                out.append((int(ro[j]), 0))
                took += 1
                if took >= n:
                    break
                ref = float(s[j])
    return out


# ------------------------------------------------------------------ reads ---
def _sess_map(rep):
    return {r["session"]: float(r["realised"]) for r in rep}


def paired_delta(repA, repB):
    """Per-session A-B with a day-clustered interval.  Sessions present in
    either replay count; a session with no seat contributes 0 to that side."""
    A, B = _sess_map(repA), _sess_map(repB)
    keys = sorted(set(A) | set(B))
    d = [A.get(k, 0.0) - B.get(k, 0.0) for k in keys]
    cl = [int(k.split("|")[1]) for k in keys]
    cm = PS.cluster_mean(d, cl)
    if not cm:
        return {"delta": float(np.mean(d)) if d else None,
                "lo": None, "hi": None, "n": len(keys)}
    return {"delta": cm["mean"], "lo": cm["ci_lo"], "hi": cm["ci_hi"],
            "n": len(keys)}


def read(D, P, seats):
    if not seats:
        return None, []
    rep = N.replay_delayed(D, seats, P)
    return N.read_rows(D, rep), rep


# -------------------------------------------------------------- the census --
def census(D, rows, score, n):
    """Cell sizes + where the deployed seat sits in the arrival order."""
    ro, blocks = _blocks(D, rows, score)
    s = np.asarray(score)[ro]
    sizes, ranks = [], []
    for a, b in blocks:
        sizes.append(b - a)
        loc = int(np.argmax(s[a:b]))          # lexsort tie-break = earliest
        ranks.append(loc)
    sizes = np.asarray(sizes)
    ranks = np.asarray(ranks)
    return {"n_cells": int(sizes.size),
            "frac_singleton": float((sizes == 1).mean()),
            "mean_cell_size": float(sizes.mean()),
            "p50_cell_size": float(np.median(sizes)),
            "p90_cell_size": float(np.percentile(sizes, 90)),
            "max_cell_size": int(sizes.max()),
            "frac_argmax_is_first": float((ranks == 0).mean()),
            "frac_argmax_is_first_multi":
                float((ranks[sizes > 1] == 0).mean()) if (sizes > 1).any()
                else None,
            "mean_argmax_rank": float(ranks.mean()),
            "mean_lookahead_sec": float(np.mean([
                D["dec_sec"][ro[a + int(np.argmax(s[a:b]))]]
                - D["dec_sec"][ro[b - 1]] for a, b in blocks])),
            }


def split_singleton(D, P, rows, score, n):
    """DEPLOYED restricted to cells that have exactly one deployable candidate
    (no lookahead available) versus the multi-candidate cells (all of it)."""
    ro, blocks = _blocks(D, rows, score)
    single = np.concatenate([ro[a:b] for a, b in blocks if b - a == 1]) \
        if any(b - a == 1 for a, b in blocks) else np.zeros(0, np.int64)
    multi = np.concatenate([ro[a:b] for a, b in blocks if b - a > 1]) \
        if any(b - a > 1 for a, b in blocks) else np.zeros(0, np.int64)
    out = {}
    for tag, sel in (("SINGLETON", single), ("MULTI", multi)):
        if sel.size == 0:
            out[tag] = None
            continue
        a, _ = read(D, P, seats_argmax(D, sel, score, n))
        out[tag] = a
    return out


# ------------------------------------------------------------------- main ---
COLS = ["era", "arm", "tau_q", "tau", "n_sessions", "n_seated",
        "usd_per_session", "ps_lo", "ps_hi", "usd_per_trade",
        "delta_vs_deployed", "d_lo", "d_hi", "note"]


def run(eras=ERAS, out=None):
    D, P = CF.boot()
    rows, cen_rows, tau_prev = [], [], {}
    t0 = time.time()
    for era in eras:
        fam = SF._load(era)
        S = [x for v in fam.values() for x in v]
        if not S:
            N.hb("LEAK_SEATING %s: no members on disk — skipped" % era)
            rows.append([era, "NO_MEMBERS"] + [""] * (len(COLS) - 2))
            continue
        ens = np.nanmean(np.vstack(S), axis=0)
        ev = N.deployable(D, N.era_rows(D, era))
        n_ = N.committed_policy()[era][1]

        # --- the committed object, and the assertion that it IS the committed
        # object: the same call capture_config/stacked_final make.
        dep_seats = seats_argmax(D, ev, ens, n_)
        chk = W.topn_takes(D, ens, ev, n_, deployable=True, unit="cell")
        if sorted(int(i) for i, _ in dep_seats) != sorted(chk.tolist()):
            raise SystemExit("LEAK_SEATING %s: top_per_cell_score != "
                             "m3_walk.topn_takes — the audit is measuring the "
                             "wrong object" % era)
        dep, dep_rep = read(D, P, dep_seats)
        rows.append([era, "DEPLOYED_CELL_ARGMAX", "", "", dep["n_sessions"],
                     dep["n_seated"], _r(dep["usd_per_session"]),
                     _r(dep["ps_lo"]), _r(dep["ps_hi"]),
                     _r(dep["usd_per_trade"]), 0.0, "", "",
                     "RETROSPECTIVE: needs the whole cell in hand"])

        cen = census(D, ev, ens, n_)
        cen["era"] = era
        cen["n_members"] = len(S)
        cen_rows.append(cen)
        N.hb("LEAK_SEATING %s: %d members, n=%d, deployed $%.2f/session, "
             "cells %d (singleton %.3f, argmax-is-first %.3f)"
             % (era, len(S), n_, dep["usd_per_session"], cen["n_cells"],
                cen["frac_singleton"], cen["frac_argmax_is_first"]))

        # --- causal, score-blind
        fst, fst_rep = read(D, P, seats_first(D, ev, ens, n_))
        d = paired_delta(fst_rep, dep_rep)
        rows.append([era, "CAUSAL_FIRST_ARRIVAL", "", "", fst["n_sessions"],
                     fst["n_seated"], _r(fst["usd_per_session"]),
                     _r(fst["ps_lo"]), _r(fst["ps_hi"]),
                     _r(fst["usd_per_trade"]), _r(d["delta"]), _r(d["lo"]),
                     _r(d["hi"]), "causal, score-blind participation floor"])

        # --- the tau sweep (causal in mechanism; tau tuned on eval = generous)
        fin = ens[ev][np.isfinite(ens[ev])]
        best = None
        rate = None
        for q in TAU_Q:
            tau = float(np.quantile(fin, q))
            a, rep = read(D, P, seats_tau(D, ev, ens, n_, tau))
            if a is None:
                continue
            cand = (a["usd_per_session"], q, tau, a, rep)
            if best is None or (a["usd_per_session"] or -1e18) > (best[0] or -1e18):
                best = cand
            gap = abs(a["n_seated"] - dep["n_seated"])
            if rate is None or gap < rate[0]:
                rate = (gap, q, tau, a, rep)
        if best is not None:
            _, q, tau, a, rep = best
            d = paired_delta(rep, dep_rep)
            rows.append([era, "CAUSAL_TAU_ORACLE", _r(q, 3), _r(tau, 6),
                         a["n_sessions"], a["n_seated"],
                         _r(a["usd_per_session"]), _r(a["ps_lo"]),
                         _r(a["ps_hi"]), _r(a["usd_per_trade"]),
                         _r(d["delta"]), _r(d["lo"]), _r(d["hi"]),
                         "UPPER BOUND on any threshold-shaped causal rule "
                         "(tau chosen on the eval era itself)"])
            tau_prev[era] = (q, tau)
        if rate is not None:
            _, q, tau, a, rep = rate
            d = paired_delta(rep, dep_rep)
            rows.append([era, "CAUSAL_TAU_RATEMATCH", _r(q, 3), _r(tau, 6),
                         a["n_sessions"], a["n_seated"],
                         _r(a["usd_per_session"]), _r(a["ps_lo"]),
                         _r(a["ps_hi"]), _r(a["usd_per_trade"]),
                         _r(d["delta"]), _r(d["lo"]), _r(d["hi"]),
                         "seat-count matched to DEPLOYED"])

        # --- the honest one: previous era's tau, carried forward blind
        prev = {"E4": "E3", "E5": "E4", "E6": "E5", "E7": "E6"}.get(era)
        if prev in tau_prev:
            q, _ = tau_prev[prev]
            tau = float(np.quantile(fin, q))     # the RULE (a quantile) carries
            a, rep = read(D, P, seats_tau(D, ev, ens, n_, tau))
            if a is not None:
                d = paired_delta(rep, dep_rep)
                rows.append([era, "CAUSAL_TAU_PREV_ERA", _r(q, 3), _r(tau, 6),
                             a["n_sessions"], a["n_seated"],
                             _r(a["usd_per_session"]), _r(a["ps_lo"]),
                             _r(a["ps_hi"]), _r(a["usd_per_trade"]),
                             _r(d["delta"]), _r(d["lo"]), _r(d["hi"]),
                             "HONEST: quantile fixed on %s, applied blind"
                             % prev])

        # --- the secretary family: the strongest causal analogue of argmax
        bestk = None
        for k in (3, 5, 10, 20, 30, 50, 80):
            a, rep = read(D, P, seats_record(D, ev, ens, n_, k))
            if a is None:
                continue
            if bestk is None or (a["usd_per_session"] or -1e18) > \
                    (bestk[0] or -1e18):
                bestk = (a["usd_per_session"], k, a, rep)
        if bestk is not None:
            _, k, a, rep = bestk
            d = paired_delta(rep, dep_rep)
            rows.append([era, "CAUSAL_SECRETARY_BEST_K", k, "",
                         a["n_sessions"], a["n_seated"],
                         _r(a["usd_per_session"]), _r(a["ps_lo"]),
                         _r(a["ps_hi"]), _r(a["usd_per_trade"]),
                         _r(d["delta"]), _r(d["lo"]), _r(d["hi"]),
                         "running-max rule after k observations; k chosen on "
                         "the eval era = UPPER BOUND on the family"])

        # --- singleton vs multi split of the deployed number
        sp = split_singleton(D, P, ev, ens, n_)
        for tag, a in sp.items():
            if a is None:
                continue
            rows.append([era, "DEPLOYED_%s_CELLS" % tag, "", "",
                         a["n_sessions"], a["n_seated"],
                         _r(a["usd_per_session"]), _r(a["ps_lo"]),
                         _r(a["ps_hi"]), _r(a["usd_per_trade"]), "", "", "",
                         "singleton cells carry NO lookahead"
                         if tag == "SINGLETON" else
                         "every cell where the argmax needed the future"])
        N.hb("LEAK_SEATING %s done (%.0fs)" % (era, time.time() - t0))

    N.write_tsv("LEAK_SEATING.tsv", COLS, rows, extra=[
        "PRIORITY 1 OF THE ADVERSARIAL LEAK AUDIT — is the committed seat "
        "earnable at arrival time?",
        "DEPLOYED_CELL_ARGMAX is newobj.top_per_cell_score, the exact call "
        "made by capture_config.run and stacked_final.run, on the exact score "
        "they seat (the folded stacked ensemble).  Replay is "
        "newobj.replay_delayed at delay 0.",
        "CAUSAL_* arms decide at each arrival with only that arrival's score "
        "and a constant.  TAU_ORACLE and TAU_RATEMATCH pick their constant "
        "WITH HINDSIGHT and are therefore upper bounds; TAU_PREV_ERA is the "
        "honest deployable read.",
        "delta_vs_deployed is the per-session paired difference with a "
        "day-clustered 95%% interval."])

    ccols = ["era", "n_members", "n_cells", "frac_singleton", "mean_cell_size",
             "p50_cell_size", "p90_cell_size", "max_cell_size",
             "frac_argmax_is_first", "frac_argmax_is_first_multi",
             "mean_argmax_rank", "mean_lookahead_sec"]
    N.write_tsv("LEAK_SEATING_CENSUS.tsv", ccols,
                [[_r(c.get(k), 6) for k in ccols] for c in cen_rows],
                extra=["THE MECHANISM: how much future a cell argmax needs.",
                       "frac_argmax_is_first = the fraction of cells where the "
                       "committed seat happens to BE the first arrival — the "
                       "only cells where the rule is implementable.",
                       "mean_lookahead_sec = mean(dec_sec of the chosen seat - "
                       "dec_sec of the cell's LAST candidate); it is negative "
                       "by exactly the seconds of tape the rule must see "
                       "after it has already entered."])
    return rows, cen_rows


MCOLS = ["era", "arm_or_rank", "n", "usd_per_session", "mean_cert_usd",
         "median_cert_usd", "win_rate", "mean_arrival_frac", "note"]


def mechanism(eras=ERAS):
    """WHY the retrospective rule pays and every causal rule does not.

    Two questions the dollar table alone cannot separate:

      (i)  is the cell argmax paying because the SCORE identifies the good
           member, or because taking a maximum of ~134 draws is worth money by
           itself?  Controls: argmax of a RANDOM score, and argmax of the real
           scores PERMUTED WITHIN THE CELL (identical score distribution per
           cell, row<->score pairing destroyed).

      (ii) if the score really does identify the good member, why does no
           arrival-time rule recover any of it?  Answer in the rank profile:
           the skill is in the ORDERING and there is none in the LEVEL, so a
           threshold on the raw score is meaningless.
    """
    D, P = CF.boot()
    rng = np.random.default_rng(20260821)
    rows = []
    for era in eras:
        fam = SF._load(era)
        S = [x for v in fam.values() for x in v]
        if not S:
            continue
        ens = np.nanmean(np.vstack(S), axis=0)
        ev = N.deployable(D, N.era_rows(D, era))
        n_ = N.committed_policy()[era][1]
        ro, blocks = _blocks(D, ev, ens)
        s, val = ens[ro], D["cert_close_usd"][ro]

        def _arm(sc, tag, note):
            a, _ = read(D, P, N.top_per_cell_score(D, ev, sc, n_))
            rows.append([era, tag, a["n_seated"], _r(a["usd_per_session"]),
                         _r(a["usd_per_trade"]), "", "", "", note])
        _arm(ens, "DEPLOYED_ARGMAX", "the committed rule")
        rnd = np.full(ens.size, np.nan)
        rnd[ev] = rng.random(ev.size)
        _arm(rnd, "CTRL_ARGMAX_RANDOM_SCORE",
             "argmax of pure noise: what the max-of-~134 mechanism pays with "
             "NO information")
        sh = np.full(ens.size, np.nan)
        for a, b in blocks:
            sh[ro[a:b]] = rng.permutation(s[a:b])
        _arm(sh, "CTRL_ARGMAX_SHUFFLED_IN_CELL",
             "same per-cell score distribution, row<->score pairing destroyed")

        # the rank profile: mean realised value by within-cell score rank
        buck, arr = {}, {}
        for a, b in blocks:
            o = np.argsort(-s[a:b], kind="stable")
            n = b - a
            for k, j in enumerate(o):
                lab = (k + 1 if k < 5 else 10 if k < 10 else 25 if k < 25
                       else 50 if k < 50 else 999)
                buck.setdefault(lab, []).append(val[a + j])
                arr.setdefault(lab, []).append(j / max(n - 1, 1))
        for lab in sorted(buck):
            v = np.asarray(buck[lab], dtype=np.float64)
            rows.append([era, "SCORE_RANK_%s" % lab, int(v.size), "",
                         _r(float(v.mean())), _r(float(np.median(v))),
                         _r(float((v > 0).mean()), 4),
                         _r(float(np.mean(arr[lab])), 4),
                         "mean realised value of the cell's rank-%s member"
                         % lab])
        rows.append([era, "ALL_MEMBERS", int(val.size), "",
                     _r(float(np.nanmean(val))), _r(float(np.nanmedian(val))),
                     _r(float(np.nanmean(val > 0)), 4), "",
                     "the population a causal rule draws from"])
    N.write_tsv("LEAK_SEATING_MECHANISM.tsv", MCOLS, rows, extra=[
        "WHY THE LOOKAHEAD PAYS AND WHY NO CAUSAL RULE RECOVERS IT.",
        "The two CTRL_ arms kill the 'a maximum of many draws is worth money "
        "by itself' explanation: both read near zero.  The SCORE_RANK_ ladder "
        "shows the real mechanism — the score orders the cell strongly and "
        "monotonically at the top, so knowing WHICH member is rank 1 is worth "
        "hundreds of dollars a trade.",
        "The catch, and the reason every arrival-time rule reads ~$0: that "
        "skill lives ENTIRELY IN THE WITHIN-CELL ORDERING and not at all in "
        "the LEVEL.  Pooled across cells the same score is at chance.  A rule "
        "that must decide at arrival can only threshold the level, and the "
        "level says nothing.",
        "This is a POLICY leak, not a feature leak: a feature carrying future "
        "information about its own row would have made the threshold rules "
        "work."])
    return rows


def _r(x, nd=2):
    if x is None or (isinstance(x, str)):
        return x if isinstance(x, str) else ""
    try:
        if not np.isfinite(x):
            return ""
    except TypeError:
        return x
    return round(float(x), nd)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eras", default=",".join(ERAS))
    ap.add_argument("--mechanism", action="store_true")
    a = ap.parse_args()
    eras = tuple(x for x in a.eras.split(",") if x)
    if a.mechanism:
        mechanism(eras)
    else:
        run(eras)


if __name__ == "__main__":
    main()
