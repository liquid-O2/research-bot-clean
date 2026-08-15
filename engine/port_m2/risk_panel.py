#!/usr/bin/python3
"""PORT M2 — THE RISK PANEL (binding for the freeze decision).

A $/session mean is not a risk statement, and the freeze conversation needs one.
This computes, per era x per asset, from the SEATED ROWS of any arm:

  hit structure      win rate; precision at the $1,000 bar
  trade P&L          mean / median / p10 / p90 per trade
  adverse excursion  MAE mean / p50 / p90; wall-hit rate (stopped at -$900)
  DAILY drawdown     p50 / p90 / max of the intra-session drawdown, and the
                     fraction of sessions breaching the D-030 $1,000 MDD law
  losing periods     losing-day fraction; losing-WEEK fraction; weekly P&L
                     mean and p10 (the user's weekly framing); longest losing
                     streak in trading days
  throughput         takes/day mean / p50 / max
  compliance         the D-077 veto drop count on the era's candidate pool

Everything is read off the same replay the dollar table uses, so the panel and
the headline can never disagree.
"""
import argparse
import json
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, "/workspace/engine/port_m2/seqtest", "/workspace/engine/port_m0",
           "/workspace/engine/port_m1", "/workspace/engine/port_m3",
           "/workspace/artifacts/cache/pylibs"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import newobj as N                        # noqa: E402
import m2_common as MC                    # noqa: E402

MDD_BAR = 1000.0            # D-030
WIN_BAR = 1000.0            # D-021 target
COLS = ["arm", "era", "asset", "n_sessions", "n_takes", "takes_per_day_mean",
        "takes_per_day_p50", "takes_per_day_max", "win_rate",
        "precision_at_1000", "usd_per_trade_mean", "usd_per_trade_median",
        "usd_per_trade_p10", "usd_per_trade_p90", "mae_mean", "mae_p50",
        "mae_p90", "wall_hit_rate", "usd_per_session", "dd_p50", "dd_p90",
        "dd_max", "frac_sessions_dd_over_1000", "losing_day_frac",
        "n_weeks", "weekly_pnl_mean", "weekly_pnl_p10", "losing_week_frac",
        "longest_losing_streak_days", "d077_vetoed_candidates"]


def _iso_week(d8):
    import datetime as dt
    d = dt.date(int(d8) // 10000, (int(d8) // 100) % 100, int(d8) % 100)
    y, w, _ = d.isocalendar()
    return y * 100 + w


def panel_rows(D, rows, arm, era, asset=None, vetoed=None):
    """One panel row from a `replay_delayed` result."""
    if not rows:
        return None
    seats = [s for r in rows for s in r["seats"]]
    idx = np.asarray([s[0] for s in seats], dtype=np.int64)
    v = np.asarray([s[2] for s in seats], dtype=np.float64)
    realised = np.asarray([r["realised"] for r in rows], dtype=np.float64)
    days = np.asarray([int(r["session"].split("|")[1]) for r in rows])
    # intra-session drawdown of the seated P&L sequence (m3_walk.daily_drawdown)
    dds = []
    for r in rows:
        if not r["seats"]:
            dds.append(0.0)
            continue
        pnl = np.asarray([s[2] for s in r["seats"]], dtype=np.float64)
        cum = np.cumsum(pnl)
        peak = np.maximum.accumulate(np.concatenate([[0.0], cum]))[:-1]
        dds.append(float(np.max(np.maximum(peak - cum, 0.0))))
    dds = np.asarray(dds)
    # weekly framing: sum realised within ISO week
    wk = {}
    for d, y in zip(days.tolist(), realised.tolist()):
        wk.setdefault(_iso_week(d), 0.0)
        wk[_iso_week(d)] += y
    wv = np.asarray(sorted(wk.items()))[:, 1] if wk else np.zeros(0)
    # longest losing streak in trading days (per-day realised, chronological)
    byday = {}
    for d, y in zip(days.tolist(), realised.tolist()):
        byday[d] = byday.get(d, 0.0) + y
    streak = best = 0
    for d in sorted(byday):
        if byday[d] < 0:
            streak += 1
            best = max(best, streak)
        else:
            streak = 0
    mae = D["mae_before_argmax"][idx].astype(np.float64)
    mae = mae[np.isfinite(mae)]
    tpd = np.asarray([len(r["seats"]) for r in rows], dtype=np.float64)
    return [arm, era, asset or "ALL", len(rows), int(idx.size),
            N._r(tpd.mean()), N._r(np.percentile(tpd, 50)),
            N._r(tpd.max()),
            N._r(float((v > 0).mean()), 4),
            N._r(float((v >= WIN_BAR).mean()), 4),
            N._r(float(v.mean())), N._r(float(np.median(v))),
            N._r(float(np.percentile(v, 10))),
            N._r(float(np.percentile(v, 90))),
            N._r(float(mae.mean()) if mae.size else None),
            N._r(float(np.percentile(mae, 50)) if mae.size else None),
            N._r(float(np.percentile(mae, 90)) if mae.size else None),
            N._r(float((D["walled"][idx] > 0).mean()), 4),
            N._r(float(realised.mean())),
            N._r(float(np.percentile(dds, 50))),
            N._r(float(np.percentile(dds, 90))),
            N._r(float(dds.max())),
            N._r(float((dds > MDD_BAR).mean()), 4),
            N._r(float((realised < 0).mean()), 4),
            int(wv.size), N._r(float(wv.mean()) if wv.size else None),
            N._r(float(np.percentile(wv, 10)) if wv.size else None),
            N._r(float((wv < 0).mean()), 4) if wv.size else None,
            int(best),
            "" if vetoed is None else int(vetoed)]


def panel_for_score(D, P, score, arm, eras, out_rows):
    """Full panel for one score column, per era and per (era, asset)."""
    for era in eras:
        ev_all = N.era_rows(D, era)
        ev = N.deployable(D, ev_all)
        vetoed = int(ev_all.size - ev.size)
        _u, n_ = N.committed_policy().get(era, ("cell", 1))
        rows = N.replay_delayed(D, N.top_per_cell_score(D, ev, score, n_), P)
        r = panel_rows(D, rows, arm, era, None, vetoed)
        if r:
            out_rows.append(r)
        for ai in sorted(set(D["asset_idx"][ev].tolist())):
            sel = ev[D["asset_idx"][ev] == ai]
            rr = N.replay_delayed(D, N.top_per_cell_score(D, sel, score, n_), P)
            r2 = panel_rows(D, rr, arm, era, MC.ASSET_ORDER[ai], None)
            if r2:
                out_rows.append(r2)
    return out_rows


def write(out_rows, name="RISK_PANEL.tsv", extra=()):
    return N.write_tsv(name, COLS, out_rows, extra=list(extra) + [
        "Computed from the SAME replay the $/session table uses, so the panel "
        "and the headline cannot disagree.",
        "dd_* are INTRA-SESSION drawdowns of the seated P&L sequence; the "
        "D-030 law is a $%d maximum and frac_sessions_dd_over_1000 is the "
        "breach rate." % int(MDD_BAR),
        "Weekly rows use ISO weeks; weekly_pnl_p10 is the 10th percentile week "
        "-- the user's weekly framing of a bad run.",
        "precision_at_1000 is the fraction of TAKES paying >= $%d (the D-021 "
        "target), not a model probability." % int(WIN_BAR),
        "takes_per_day_* are per SESSION, i.e. per (asset, trading day) -- the "
        "unit the one-position contract applies to -- not per calendar day "
        "across the three books."])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="LMART_HP_NOTF")
    ap.add_argument("--eras", default=",".join(N.DEV_ERAS))
    ap.add_argument("--out", default="RISK_PANEL.tsv")
    a = ap.parse_args()
    D = N.matrix()
    P = N.load_paths()
    sc = N.champ_score(a.tag)
    rows = panel_for_score(D, P, sc, a.tag,
                           tuple(e for e in a.eras.split(",") if e), [])
    write(rows, a.out, extra=["arm = %s" % a.tag])
