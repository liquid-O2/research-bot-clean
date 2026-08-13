#!/usr/bin/python3
"""PORT M0 c_a_cost — spec §6.

Per (asset, session, phase): two-sided occupancy, spread quantiles in ticks and
dollars, top_size_p10, cost_rt (phase-median convention) + p75 variant.
Rollups per (asset, phase, year) and per (asset, phase, era), NKD split rows
{all, ex_roll_week}.  Verdict per (asset, phase) by the §1 bands.

A phase row named ALL is emitted alongside TOKYO/LONDON/NY: it is the
SESSION-scoped statistic, which §8 sub-pass 3 requires verbatim ("cost_rt here =
session-scoped: median two-sided spread of THAT session + $5").  It is additive,
not a change to any §6 number.

Pooled quantiles are EXACT: two-sided spreads live on the tick grid, so each
(asset, year, phase, split) group carries an integer histogram of spread-in-ticks
and the quantile is taken on the full population of seconds.  The
per-(asset,year,phase) median that §8 uses as the ZigZag spread floor is the
POOLED median (column spread_med_usd_pooled); the median of per-session phase
medians is reported beside it as spread_med_usd_sessmed.
"""
import multiprocessing as mp
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
import census_common as X

SECTION = "§6 c_a_cost"
PHASE_ROWS = ("TOKYO", "LONDON", "NY", "ALL")

PARAMS = {
    "spec_section": SECTION,
    "phases": list(PHASE_ROWS),
    "weighting": "seconds with state == TWO_SIDED only",
    "excluded_frac": "1 - two_sided_seconds / phase_seconds",
    "cost_rt": "median two-sided spread ($) + FEES_RT ($5.00)",
    "cost_rt_p75": "p75 two-sided spread ($) + FEES_RT",
    "top_size_p10": "p10 of min(bid_sz, ask_sz) over two-sided seconds "
                    "(1-lot adequacy, two-sided touch); per-side p10 reported too",
    "quantiles": "numpy linear interpolation; pooled rollup quantiles exact via "
                 "an integer tick histogram over every two-sided second",
    "splits": "all; ex_roll_week (NKD only) = sessions with dying_book_week == 0",
    "eras": "each year, FIT_2021_2024, GATE_2025, ALL (see census_common.eras_of)",
    "gates": {"green_cost_share": X.GATE_COST_GREEN,
              "caution_cost_share": X.GATE_COST_CAUTION,
              "insufficient_book_excluded_frac": X.INSUFFICIENT_BOOK_FRAC},
    "fees_rt": C.FEES_RT,
}

COLUMNS = ["asset", "trade_date", "year", "phase", "dominant_id",
           "phase_seconds", "two_sided_seconds", "excluded_frac",
           "spread_med_usd", "spread_p75_usd", "spread_p90_usd",
           "spread_med_ticks", "spread_p75_ticks", "spread_p90_ticks",
           "top_size_p10", "top_size_p10_bid", "top_size_p10_ask",
           "cost_rt", "cost_rt_p75",
           "roll_window", "dying_book_week", "instrument_change",
           "n_valid_seconds", "dominant_share"]

ROLLUP_COLUMNS = ["asset", "phase", "era", "split", "n_sessions",
                  "phase_seconds", "two_sided_seconds", "excluded_frac_pooled",
                  "excluded_frac_med_session",
                  "spread_med_usd_pooled", "spread_p75_usd_pooled",
                  "spread_p90_usd_pooled", "spread_med_ticks_pooled",
                  "spread_med_usd_sessmed", "top_size_p10_med",
                  "cost_rt_pooled", "cost_rt_p75_pooled",
                  "cost_share", "verdict"]


# ------------------------------------------------------------------ worker --
def _task(args):
    asset, sess = args
    tick_usd = C.ASSETS[asset]["tick_usd"]
    rows = []
    hist = {}
    for trade_date, path in sess:
        s = X.load_session(asset, trade_date, path)
        splits = ["all"]
        if asset == "NKD" and not s.dying_book_week:
            splits.append("ex_roll_week")
        for phase in PHASE_ROWS:
            if phase == "ALL":
                pm = np.ones(s.n, dtype=bool)
            else:
                pm = (s.phase_tag == X.PHASE_NAMES.index(phase))
            phase_seconds = int(pm.sum())
            if phase_seconds == 0:
                continue
            ts = pm & s.valid
            n_ts = int(ts.sum())
            spr = s.spread_usd[ts]
            bsz = s.bid_sz[ts]
            asz = s.ask_sz[ts]
            top = np.minimum(bsz, asz)
            excluded = 1.0 - (n_ts / phase_seconds)
            m50 = X.pct(spr, 50)
            m75 = X.pct(spr, 75)
            m90 = X.pct(spr, 90)
            rows.append([
                asset, trade_date.isoformat(), trade_date.year, phase, s.iid,
                phase_seconds, n_ts, excluded,
                m50, m75, m90,
                m50 / tick_usd, m75 / tick_usd, m90 / tick_usd,
                X.pct(top, 10), X.pct(bsz, 10), X.pct(asz, 10),
                (m50 + C.FEES_RT) if np.isfinite(m50) else float("nan"),
                (m75 + C.FEES_RT) if np.isfinite(m75) else float("nan"),
                s.roll_window, s.dying_book_week, s.instrument_change,
                int(s.valid.sum()), s.dominant_share])
            if n_ts:
                ticks = np.rint(spr / tick_usd).astype(np.int64)
                ticks = ticks[ticks >= 0]
                bc = np.bincount(ticks)
                nz = np.nonzero(bc)[0]
                for split in splits:
                    h = hist.setdefault((trade_date.year, phase, split), {})
                    for k in nz.tolist():
                        h[k] = h.get(k, 0) + int(bc[k])
    return rows, hist


def _merge_hist(dst, src):
    for k in sorted(src):
        d = dst.setdefault(k, {})
        for tk in sorted(src[k]):
            d[tk] = d.get(tk, 0) + src[k][tk]


# ------------------------------------------------------------------- main ---
def run(assets=C.ASSET_ORDER, root=None, out_root=None, months=None, workers=10):
    root = root or C.OUT_ROOT
    out_root = out_root or C.OUT_ROOT
    phash = C.params_hash(PARAMS)
    tasks = []
    for asset in assets:
        by_month = {}
        for d, p in X.session_paths(asset, root):
            if months and X.month_key(d) not in months:
                continue
            by_month.setdefault(X.month_key(d), []).append((d, p))
        for mk in sorted(by_month):
            tasks.append((asset, by_month[mk]))
    C.hb("c_a: %d (asset,month) tasks over %s" % (len(tasks), ",".join(assets)))

    all_rows, hists = [], {}
    if workers <= 1 or len(tasks) <= 1:
        results = [_task(t) for t in tasks]
    else:
        with mp.Pool(min(workers, len(tasks))) as pool:
            results = list(pool.map(_task, tasks, chunksize=1))
    # merge in deterministic task order (tasks are already sorted)
    for (asset, _sess), (rows, hist) in zip(tasks, results):
        all_rows.extend(rows)
        _merge_hist(hists.setdefault(asset, {}), hist)

    all_rows.sort(key=lambda r: (r[0], r[1], PHASE_ROWS.index(r[3])))
    X.write_tsv(X.out_path(out_root, "census_a_cost.tsv"), SECTION, phash,
                COLUMNS, all_rows,
                extra=["one row per (asset, session, phase); phase ALL is the "
                       "SESSION-scoped statistic required by §8 sub-pass 3"])

    rollup = _rollup(assets, all_rows, hists)
    X.write_tsv(X.out_path(out_root, "census_a_cost_rollup.tsv"), SECTION, phash,
                ROLLUP_COLUMNS, rollup,
                extra=["spread_med_usd_pooled is the (asset,year,phase) median "
                       "§8 uses as the ZigZag spread floor",
                       "verdict on era=ALL/split=all rows only; §1 bands "
                       "GREEN<=%.2f CAUTION<=%.2f of $1,000"
                       % (X.GATE_COST_GREEN, X.GATE_COST_CAUTION)])
    C.hb("c_a: %d session-phase rows, %d rollup rows" % (len(all_rows), len(rollup)))
    return all_rows, rollup


def _rollup(assets, rows, hists):
    tick = {a: C.ASSETS[a]["tick_usd"] for a in assets}
    # per (asset, phase, era, split) session-level aggregates
    agg = {}
    for r in rows:
        asset, _d, year, phase = r[0], r[1], int(r[2]), r[3]
        splits = ["all"]
        if asset == "NKD" and not r[20]:
            splits.append("ex_roll_week")
        for era in X.eras_of(year):
            for split in splits:
                k = (asset, phase, era, split)
                a = agg.setdefault(k, {"n": 0, "ps": 0, "ts": 0, "exc": [],
                                       "med": [], "top": []})
                a["n"] += 1
                a["ps"] += int(r[5])
                a["ts"] += int(r[6])
                a["exc"].append(float(r[7]))
                a["med"].append(float(r[8]))
                a["top"].append(float(r[14]))
    # per (asset, year, phase, split) -> era histograms
    ehist = {}
    for asset in sorted(hists):
        for (year, phase, split), h in sorted(hists[asset].items()):
            for era in X.eras_of(year):
                d = ehist.setdefault((asset, phase, era, split), {})
                for tk in sorted(h):
                    d[tk] = d.get(tk, 0) + h[tk]

    out = []
    for k in sorted(agg):
        asset, phase, era, split = k
        a = agg[k]
        h = ehist.get(k, {})
        tu = tick[asset]
        p50 = X.hist_quantile(h, 50) * tu
        p75 = X.hist_quantile(h, 75) * tu
        p90 = X.hist_quantile(h, 90) * tu
        exc_pooled = 1.0 - (a["ts"] / a["ps"]) if a["ps"] else float("nan")
        cost = p50 + C.FEES_RT
        cost75 = p75 + C.FEES_RT
        share = cost / 1000.0
        verdict = ""
        if era == X.ERA_ALL and split == "all" and phase != "ALL":
            if not np.isfinite(exc_pooled):
                verdict = "NO_DATA"
            elif exc_pooled > X.INSUFFICIENT_BOOK_FRAC:
                verdict = "INSUFFICIENT_BOOK"
            elif share <= X.GATE_COST_GREEN:
                verdict = "GREEN"
            elif share <= X.GATE_COST_CAUTION:
                verdict = "CAUTION"
            else:
                verdict = "RED"
        out.append([asset, phase, era, split, a["n"], a["ps"], a["ts"],
                    exc_pooled, X.med(a["exc"]), p50, p75, p90,
                    X.hist_quantile(h, 50), X.med(a["med"]), X.med(a["top"]),
                    cost, cost75, share, verdict])
    return out


def phase_median_spreads(out_root=None):
    """(asset, year, phase) -> pooled median two-sided spread ($) — the §8 floor."""
    out_root = out_root or C.OUT_ROOT
    p = os.path.join(out_root, "census_a_cost_rollup.tsv")
    res = {}
    cols = None
    with open(p) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if cols is None:
                cols = f
                continue
            r = dict(zip(cols, f))
            if r["split"] != "all":
                continue
            era = r["era"]
            if not era.isdigit():
                continue
            v = r["spread_med_usd_pooled"]
            res[(r["asset"], int(era), r["phase"])] = float(v) if v else float("nan")
    return res


def session_cost_rt(out_root=None):
    """(asset, trade_date_iso) -> session-scoped cost_rt ($) — §8 sub-pass 3."""
    out_root = out_root or C.OUT_ROOT
    p = os.path.join(out_root, "census_a_cost.tsv")
    res = {}
    cols = None
    with open(p) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if cols is None:
                cols = f
                continue
            r = dict(zip(cols, f))
            if r["phase"] != "ALL":
                continue
            v = r["cost_rt"]
            res[(r["asset"], r["trade_date"])] = float(v) if v else float("nan")
    return res


def session_flags(out_root=None):
    """(asset, trade_date_iso) -> {roll_window, dying_book_week,
    instrument_change} — the §5 roll flags, read back from the c_a per-session
    rows so downstream censuses need not reopen every session receipt."""
    out_root = out_root or C.OUT_ROOT
    p = os.path.join(out_root, "census_a_cost.tsv")
    res = {}
    cols = None
    with open(p) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if cols is None:
                cols = f
                continue
            r = dict(zip(cols, f))
            if r["phase"] != "ALL":
                continue
            res[(r["asset"], r["trade_date"])] = {
                "roll_window": r["roll_window"] == "1",
                "dying_book_week": r["dying_book_week"] == "1",
                "instrument_change": r["instrument_change"] == "1"}
    return res


def main():
    X.verify_spec()
    run(assets=sys.argv[1:] or list(C.ASSET_ORDER))
    return 0


if __name__ == "__main__":
    sys.exit(main())
