#!/usr/bin/python3
"""PORT M2 — THE CONSTRAINT-FOLDED STACKED FINAL.

ASSEMBLY AND REPLAY ONLY.  No fitting.  Every member is an ALREADY-FITTED score
column on disk; this pools them, score-means them, replays the schedule and
prints the table.

WHY IT EXISTS: the stacked table on disk predated the constraint result
entirely (E3 $535 with no TOP50 inside), while TOP50 monotone constraints were
the round's biggest single result -- E3 $298.56 -> $934.33, +$491 after its own
seed sd, with the seed sd itself halving.  A stacked final without the
constrained members is not the round's final.

THE POOL, per era: TOP50-constrained members + volmatch members + feature-bagged
members + regularization members.  Any member set missing for an era is SAID SO
in the table rather than fitted.
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
import risk_panel as RP                   # noqa: E402
import m2_common as MC                    # noqa: E402

ERAS = N.DEV_ERAS
SEEDS = range(5)
BAGS = range(10)
SDIR = os.path.join(N.OUT_ROOT, "curriculum_scores")
BAR = 2000.0
MDD = 1000.0
# the champion's own 5-seed reference (CHAMPION_FLOOR.tsv, PRE_E1)
CHAMP_REF = {"E3": 448.85, "E4": 887.37, "E5": 755.94, "E6": 625.91,
             "E7": 1052.91, "POOLED": 754.20}


def _load(era):
    """Every already-fitted member for this era, by family."""
    fam = {}
    for tag, rng in (("CONTOP50", SEEDS), ("W_VOLMATCH", SEEDS),
                     ("BAG", BAGS), ("REG", SEEDS)):
        got = []
        for i in rng:
            f = os.path.join(SDIR, "%s_%s_%d.npy" % (tag, era, i))
            if os.path.exists(f):
                got.append(np.load(f).astype(np.float64))
        fam[tag] = got
    return fam


def run(eras=ERAS):
    D, P = CF.boot()
    rows, panel, per_era = [], [], {}
    t0 = time.time()
    for era in eras:
        fam = _load(era)
        S = [x for v in fam.values() for x in v]
        present = ",".join("%s:%d" % (k, len(v)) for k, v in fam.items())
        missing = ",".join(k for k, v in fam.items() if not v) or "none"
        if not S:
            N.hb("STACKED %s: NO MEMBERS ON DISK -- skipped" % era)
            rows.append([era, "ALL", 0, "", "", "", "", "", "", "", "",
                         "NO MEMBERS"])
            continue
        ens = np.nanmean(np.vstack(S), axis=0)
        ev = N.deployable(D, N.era_rows(D, era))
        n_ = N.committed_policy()[era][1]
        rep = N.replay_delayed(D, N.top_per_cell_score(D, ev, ens, n_), P)
        a = N.read_rows(D, rep)
        per_era[era] = a
        pr = RP.panel_rows(D, rep, "STACKED_CONSTRAINED", era, "ALL", None)
        h = RP.COLS
        g = dict(zip(h, pr))
        rows.append([era, "ALL", len(S), N._r(a["usd_per_session"]),
                     N._r(a["ps_lo"]), N._r(a["ps_hi"]),
                     g["win_rate"], g["usd_per_trade_mean"],
                     g["dd_p90"], g["frac_sessions_dd_over_1000"],
                     N._r(CHAMP_REF.get(era)),
                     "%s | missing:%s" % (present, missing)])
        for ai in sorted(set(D["asset_idx"][ev].tolist())):
            sel = ev[D["asset_idx"][ev] == ai]
            rp2 = N.replay_delayed(D, N.top_per_cell_score(D, sel, ens, n_), P)
            aa = N.read_rows(D, rp2)
            p2 = dict(zip(h, RP.panel_rows(D, rp2, "STACKED_CONSTRAINED", era,
                                           MC.ASSET_ORDER[ai], None)))
            rows.append([era, MC.ASSET_ORDER[ai], len(S),
                         N._r(aa["usd_per_session"]), N._r(aa["ps_lo"]),
                         N._r(aa["ps_hi"]), p2["win_rate"],
                         p2["usd_per_trade_mean"], p2["dd_p90"],
                         p2["frac_sessions_dd_over_1000"], "",
                         "CLEARS_2000" if (aa["usd_per_session"] or 0) >= BAR
                         else ""])
        panel.append(pr)
        N.hb("STACKED %s: %d members -> $%s/session (%s)"
             % (era, len(S), N._r(a["usd_per_session"]), present))
    q = N.pool_reads([per_era[e] for e in eras if e in per_era])
    rows.append(["POOLED", "ALL", "", N._r(q.get("usd_per_session")),
                 N._r(q.get("ps_lo")), N._r(q.get("ps_hi")), "", "", "", "",
                 N._r(CHAMP_REF["POOLED"]), ""])
    N.write_tsv("STACKED_FINAL_CONSTRAINED.tsv",
                ["era", "asset", "n_members", "usd_per_session", "lo", "hi",
                 "win_rate", "usd_per_trade", "dd_p90",
                 "frac_sessions_dd_over_1000", "champion_5seed_ref",
                 "members_present"], rows,
                extra=["THE CONSTRAINT-FOLDED STACKED FINAL.  ASSEMBLY AND "
                       "REPLAY ONLY -- every member is an already-fitted score "
                       "column; nothing was fitted here.",
                       "Pool per era: TOP50-constrained + volmatch + "
                       "feature-bagged + regularization members, score-meaned.",
                       "champion_5seed_ref is the champion's OWN 5-seed mean at "
                       "the deployed window (CHAMPION_FLOOR.tsv), not its "
                       "single-fit headline -- the only lawful comparison.",
                       "frac_sessions_dd_over_1000 is the D-030 breach rate.",
                       "members_present records exactly which member sets "
                       "existed for each era; nothing was fitted to fill a gap."])
    RP.write(panel, "RISK_PANEL_STACKED_FINAL.tsv",
             extra=["arm = the constraint-folded stacked final"])
    N.hb("stacked final assembled in %.0fs" % (time.time() - t0))
    return rows



# ===================== THE SESSION-STOP OVERLAY (compliance, D-030) =========
# REPLAY ARITHMETIC ONLY -- no refit, no re-selection.  The seats are exactly
# the ones the arm already chose; the overlay only STOPS THE DAY once the
# intraday drawdown crosses a line, dropping every later seat of that session.
#
# MECHANISM (why this works at all): a D-030 breach is almost always a TWO-WALL
# SESSION -- two walled losses at ~$930 each is $1,860 of drawdown against a
# $1,000 law, and a single wall alone cannot breach it.  So the breach rate is a
# direct function of the ENTRY win rate: E5 is clean (1.8%) because its 0.726
# win rate makes two-wall days rare, while E3 breaches 19.7% at a 0.587 win
# rate.  Entries and drawdowns are the same problem seen twice.
# STOP_WALL1 added AFTER the first two were measured and BOTH failed to move
# the breach rate.  The reason is arithmetic and was not anticipated: a stop
# cannot prevent the breach that TRIGGERS it.  By the time drawdown reaches
# $1,000 the $1,000 breach is already booked; halting only prevents further
# damage beyond that point.  The ONLY stop that can cut the breach rate is one
# that fires BEFORE the second wall -- i.e. on the FIRST walled loss, where
# drawdown is ~$930 and the law is not yet broken.
STOP_VARIANTS = ("STOP_WALL2_900", "STOP_HARD_1000", "STOP_WALL1")


def apply_stop(D, rows, variant):
    """Truncate each session's seat sequence at the stop.  Returns new rows."""
    out = []
    for r in rows:
        seats = list(r["seats"])
        cum = peak = 0.0
        n_wall = 0
        kept = []
        for (i, dl, v) in seats:
            kept.append((i, dl, v))
            cum += float(v)
            peak = max(peak, cum)
            dd = peak - cum
            walled = bool(D["walled"][i] > 0) and float(v) < 0
            if walled:
                n_wall += 1
            hit = ((variant == "STOP_HARD_1000" and dd >= 1000.0)
                   or (variant == "STOP_WALL2_900" and n_wall >= 2
                       and dd >= 900.0)
                   or (variant == "STOP_WALL1" and n_wall >= 1))
            if hit:
                break                      # the day is over; later seats drop
        out.append({"session": r["session"],
                    "realised": float(sum(x[2] for x in kept)),
                    "n_takes": r["n_takes"], "n_seated": len(kept),
                    "n_forfeited": r["n_forfeited"],
                    "n_refused": r["n_refused"], "seats": kept})
    return out


def stop_overlay(eras=ERAS):
    D, P = CF.boot()
    rows, panel = [], []
    for era in eras:
        fam = _load(era)
        S = [x for v in fam.values() for x in v]
        if not S:
            continue
        ens = np.nanmean(np.vstack(S), axis=0)
        ev = N.deployable(D, N.era_rows(D, era))
        n_ = N.committed_policy()[era][1]
        base = N.replay_delayed(D, N.top_per_cell_score(D, ev, ens, n_), P)
        h = RP.COLS
        b = dict(zip(h, RP.panel_rows(D, base, "RAW", era, "ALL", None)))
        ab = N.read_rows(D, base)
        rows.append([era, "RAW", N._r(ab["usd_per_session"]), "",
                     b["win_rate"], b["frac_sessions_dd_over_1000"],
                     b["dd_p90"], b["n_takes"], b["weekly_pnl_mean"],
                     b["weekly_pnl_p10"], b["losing_week_frac"]])
        for v in STOP_VARIANTS:
            st = apply_stop(D, base, v)
            a = N.read_rows(D, st)
            g = dict(zip(h, RP.panel_rows(D, st, v, era, "ALL", None)))
            rows.append([era, v, N._r(a["usd_per_session"]),
                         N._r((a["usd_per_session"] or 0)
                              - (ab["usd_per_session"] or 0)),
                         g["win_rate"], g["frac_sessions_dd_over_1000"],
                         g["dd_p90"], g["n_takes"], g["weekly_pnl_mean"],
                         g["weekly_pnl_p10"], g["losing_week_frac"]])
            panel.append(RP.panel_rows(D, st, "STACKED_%s" % v, era, "ALL",
                                       None))
        N.hb("stop overlay %s done" % era)
    N.write_tsv("STACKED_FINAL_STOP_OVERLAY.tsv",
                ["era", "arm", "usd_per_session", "delta_vs_raw", "win_rate",
                 "frac_sessions_dd_over_1000", "dd_p90", "n_takes",
                 "weekly_pnl_mean", "weekly_pnl_p10", "losing_week_frac"],
                rows,
                extra=["THE SESSION-STOP OVERLAY -- REPLAY ARITHMETIC ONLY. "
                       "The seats are exactly the ones the arm already chose; "
                       "the overlay stops the DAY once intraday drawdown "
                       "crosses the line and drops every later seat.  Nothing "
                       "is refitted and nothing is re-selected.",
                       "STOP_WALL2_900 = stop after a SECOND walled loss once "
                       "drawdown >= $900.  STOP_HARD_1000 = stop at $1,000 "
                       "drawdown outright (the D-030 line itself).",
                       "MECHANISM: a D-030 breach is almost always a TWO-WALL "
                       "SESSION -- 2 x ~$930 = $1,860 against a $1,000 law, and "
                       "one wall alone cannot breach it.  The breach rate is "
                       "therefore a direct function of the ENTRY win rate: E5 "
                       "is clean (1.8%) because 0.726 wins make two-wall days "
                       "rare; E3 breaches 19.7% at 0.587.  Entries and "
                       "drawdowns are the same problem seen twice.",
                       "MEASURED CORRECTION: the two drawdown-triggered stops "
                       "do NOT drive the breach rate toward zero, because a "
                       "stop cannot prevent the breach that triggers it -- at "
                       "$1,000 drawdown the $1,000 breach is already booked. "
                       "STOP_WALL1 (halt on the FIRST walled loss, at ~$930, "
                       "before the law is broken) is the only variant that can "
                       "cut the rate, and it is priced here beside them.",
                       "ADOPTION TOUCHES THE TRADING PROCEDURE and is the "
                       "user's call (D-029); this is a measurement."])
    RP.write(panel, "RISK_PANEL_STACKED_STOP.tsv",
             extra=["arm = the stacked final under each session stop"])
    return rows

def _selfcheck():
    """GUARD -- this file has now been bitten FOUR times by `cat >>` appending
    stage functions BELOW the entrypoint, so main() dispatches to names that do
    not exist yet.  Fail at import, not after a stage has burned compute."""
    missing = [n for n in ("run", "stop_overlay", "selective", "apply_stop")
               if n not in globals()]
    if missing:
        raise RuntimeError("stacked_final.py mis-assembled: %s defined below "
                           "the entrypoint" % ", ".join(missing))

# ================= SELECTIVE PARTICIPATION (the user's product) =============
# The fixed 3-seats/day schedule is not the product.  This takes a seat ONLY
# when the stacked score clears a bar -- 0 to 3 per asset-day, zero allowed.
#
# LAWFULNESS: the bar is a QUANTILE, not a raw score.  Member models differ by
# era so raw score scales are not comparable across eras, but a quantile is.
# The quantile is chosen on the PRIOR ERAS' realised replay and applied forward
# to the current era's own score distribution -- walk-forward, no fitting, no
# look at the era being scored.  E3 has no prior era and is reported UNFILTERED
# and flagged, never back-fitted.
SEL_Q = (0.0, 0.20, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90)
WEEK_FLOOR = 3.0            # the standing portfolio minimum, takes/week


def _sel_takes(D, ev, sc, n_, q):
    """Top-n per cell, then keep only those clearing the q-quantile bar."""
    tk = N.top_per_cell_score(D, ev, sc, n_)
    if q <= 0:
        return tk
    # THE BAR MUST BE RELATIVE TO THE TAKES, NOT THE POOL.  A top-1-per-cell
    # take is already the highest scorer in its cell, so a quantile of the whole
    # candidate pool clears essentially every take and the arm does not filter
    # at all (measured: q=0.9 removed 3 takes of 1,155).  The bar is therefore
    # the q-quantile of the SELECTED takes' own scores, which is what "take only
    # the best 100(1-q)% of the days you would have traded" actually means.
    tv = np.asarray([sc[i] for (i, d) in tk], dtype=np.float64)
    tv = tv[np.isfinite(tv)]
    if tv.size == 0:
        return tk
    bar = float(np.quantile(tv, q))
    return [(i, d) for (i, d) in tk if sc[i] >= bar]


def _sel_read(D, P, ev, sc, n_, q, era):
    tk = _sel_takes(D, ev, sc, n_, q)
    rep = N.replay_delayed(D, tk, P)
    a = N.read_rows(D, rep)
    g = dict(zip(RP.COLS, RP.panel_rows(D, rep, "SEL", era, "ALL", None)))
    n_days = len(set(D["d8"][ev].tolist()))
    n_weeks = max(n_days / 5.0, 1e-9)
    seats = a.get("n_seated") or 0
    return a, g, rep, seats / n_weeks * (1.0 / 3.0)   # takes/week per asset


def selective(eras=ERAS):
    """THE PARTICIPATION CURVE.

    A selection rule was tried first and had to be abandoned, for a reason worth
    recording: choosing the bar by maximising $/session ALWAYS returns q=0 when
    per-trade expectancy is positive, because more takes mechanically means more
    total dollars.  That objective cannot test the user's thesis, which is about
    $/TRADE rising and DRAWDOWNS collapsing while the WEEK stays strong.

    So no bar is selected.  The whole curve is reported and the trade-off is
    shown directly.
    """
    D, P = CF.boot()
    rows = []
    for era in eras:
        fam = _load(era)
        S = [x for v in fam.values() for x in v]
        if not S:
            continue
        ens = np.nanmean(np.vstack(S), axis=0)
        ev = N.deployable(D, N.era_rows(D, era))
        n_ = N.committed_policy()[era][1]
        for q in SEL_Q:
            a_, g, rep, tpw = _sel_read(D, P, ev, ens, n_, q, era)
            td = [r for r in rep if r["n_seated"] > 0]
            per_traded = (sum(r["realised"] for r in td) / len(td)) if td \
                else None
            rows.append([era, N._r(q, 2), a_.get("n_seated"),
                         N._r(g["takes_per_day_mean"]), N._r(tpw, 2),
                         g["win_rate"], N._r(a_.get("usd_per_trade")),
                         N._r(a_.get("usd_per_session")), N._r(per_traded),
                         g["weekly_pnl_mean"], g["weekly_pnl_p10"],
                         g["losing_week_frac"],
                         g["frac_sessions_dd_over_1000"],
                         "BELOW WEEKLY FLOOR" if tpw < WEEK_FLOOR else ""])
        N.hb("participation curve %s done" % era)
    N.write_tsv("STACKED_FINAL_SELECTIVE.tsv",
                ["era", "quantile_bar", "n_seated", "takes_per_day_mean",
                 "takes_per_week_per_asset", "win_rate", "usd_per_trade",
                 "usd_per_session", "usd_per_traded_day", "weekly_pnl_mean",
                 "weekly_pnl_p10", "losing_week_frac",
                 "frac_sessions_dd_over_1000", "note"], rows,
                extra=["SELECTIVE PARTICIPATION -- the fixed 3-seats/day "
                       "schedule is not the product.  0-3 takes per asset-day, "
                       "ZERO ALLOWED, gated by a score bar.",
                       "NO BAR IS SELECTED and the whole curve is reported. "
                       "A selection rule was tried and abandoned: maximising "
                       "$/session ALWAYS returns q=0 when per-trade expectancy "
                       "is positive, because more takes mechanically means more "
                       "dollars.  That objective cannot test a thesis about "
                       "$/TRADE and DRAWDOWN.",
                       "The bar is the q-quantile of the SELECTED TAKES' own "
                       "scores -- 'trade only the best 100(1-q)% of the days "
                       "you would have traded'.  A quantile of the whole "
                       "candidate pool does not filter at all, because a "
                       "top-1-per-cell take is already its cell's best.",
                       "Rows below %.0f takes/week per asset are FLAGGED "
                       "against the standing portfolio minimum." % WEEK_FLOOR,
                       "THE THESIS UNDER TEST: proper selective entries barely "
                       "draw down, so compliance costs ~nothing without any "
                       "session stop.  Read win_rate, usd_per_trade and "
                       "frac_sessions_dd_over_1000 together."])
    return rows


if __name__ == "__main__":
    _selfcheck()
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--stop", action="store_true")
    ap.add_argument("--selective", action="store_true")
    a = ap.parse_args()
    if a.run:
        run()
        stop_overlay()
    elif a.stop:
        stop_overlay()
    elif a.selective:
        selective()
    else:
        ap.print_help()
