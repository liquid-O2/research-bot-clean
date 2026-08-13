#!/usr/bin/python3
"""PORT M1.B S1 — CC-M1-4.4 IMPACT QUANTIFICATION of the D-054 mid-sanity mask.

Mandatory deliverable: before/after-mask deltas per asset for the offer census,
the DP seatable medians, the wall statistics and recall.  Both arms are the
SAME pipeline (`b8_generation_v2.py`) on the SAME sessions with the SAME
families and the SAME D-053 level config — the ONLY difference is the mask, so
every delta below is attributable to it and to nothing else:

    BEFORE  m1/generation_v2_nomask/   (S1_ARM=unmasked, levels_v2)
    AFTER   m1/generation_v2/          (S1_ARM=masked,   levels_v3)

M0-verdict-relevant medians moving > 5% raise ORCHESTRATOR ADDENDUM REQUIRED
(D-054 / CC-M1-4.4).

Run: /usr/bin/python3 engine/port_m1/b9_mask_impact.py
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import m1_common as M
import common as C
import census_common as X

SECTION = "CC-M1-4.4 mask impact"
BEFORE_DIR = "generation_v2_nomask"
AFTER_DIR = "generation_v2"
OUT_DIR = AFTER_DIR
FLAG_PCT = 5.0

PARAMS = {"spec_section": SECTION, "before": BEFORE_DIR, "after": AFTER_DIR,
          "flag_pct": FLAG_PCT,
          "pairing": "per-session measures are compared on the sessions both "
                     "arms define; sessions the mask empties entirely (frozen "
                     "$0-range books) are counted separately, never allowed to "
                     "move a median by leaving the denominator",
          "verdict_relevant": ["offer_best_leg_median_FULL",
                               "offer_range_median_FULL",
                               "dp_seatable_median", "wall_mae_p95",
                               "wall_mae_p99", "recall_all_1000"]}

VERDICT_RELEVANT = set(PARAMS["verdict_relevant"])

COLUMNS = ["asset", "era", "metric", "before_mask", "after_mask", "delta",
           "pct_change", "verdict_relevant", "flag"]


def _tsv(path):
    rows, cols = [], None
    if not os.path.exists(path):
        return cols, rows
    with open(path) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if cols is None:
                cols = f
                continue
            rows.append(dict(zip(cols, f)))
    return cols, rows


def _f(r, k):
    v = r.get(k, "")
    return float(v) if v not in ("", None) else float("nan")


def _era_sel(year, era):
    if era == M.ERA_ALL:
        return True
    if era == M.ERA_FIT:
        return M.is_fit(year)
    return year == 2025


def _by_session(rows, asset, era, key, where=None):
    """{trade_date: value} for one arm, one asset, one era."""
    out = {}
    for r in rows:
        if r["asset"] != asset or not _era_sel(int(r["year"]), era):
            continue
        if where and not where(r):
            continue
        out[r["trade_date"]] = _f(r, key)
    return out


def paired(a, b):
    """The sessions where BOTH arms define the measure.

    The mask deletes every second of a FROZEN-BOOK session (the D8 stale-book
    receipts: a wide quote that never moves has no sane second), so those
    sessions leave the offer census entirely.  Their range is $0, so comparing
    raw medians across arms would report a large 'improvement' that is pure
    denominator change.  The verdict-relevant comparison is therefore the
    PAIRED one - same sessions, both arms - with the departures counted
    separately."""
    keys = sorted(set(a) & set(b))
    va = [a[k] for k in keys if np.isfinite(a[k]) and np.isfinite(b[k])]
    vb = [b[k] for k in keys if np.isfinite(a[k]) and np.isfinite(b[k])]
    lost = sum(1 for k in a if np.isfinite(a[k])
               and not np.isfinite(b.get(k, float("nan"))))
    return va, vb, lost


def metrics(root):
    """{(asset, era, metric): value} for one arm (unpaired diagnostics)."""
    out = {}
    _, wall = _tsv(M.out_path(root, "wall_stats.tsv"))
    _, rec = _tsv(M.out_path(root, "census_union_recall.tsv"))
    _, bld = _tsv(M.out_path(root, "roster_build.tsv"))
    for asset in M.ASSET_ORDER:
        for era in (M.ERA_FIT, M.ERA_GATE, M.ERA_ALL):
            w = [r for r in wall if r["asset"] == asset and r["era"] == era]
            if w:
                out[(asset, era, "wall_mae_p95")] = _f(w[0], "mae_p95_usd")
                out[(asset, era, "wall_mae_p99")] = _f(w[0], "mae_p99_usd")
                out[(asset, era, "n_winners")] = _f(w[0], "n_winners")
            g = [r for r in rec if r["asset"] == asset and r["era"] == era
                 and r["dropped_exclusive_family"] == "NONE"]
            if g:
                out[(asset, era, "recall_all_1000")] = \
                    _f(g[0], "recall_all_1000")
                out[(asset, era, "recall_gate_1000")] = \
                    _f(g[0], "recall_gate_1000")
                out[(asset, era, "n_oracle_legs")] = _f(g[0], "n_legs")
                out[(asset, era, "n_news_untradeable")] = \
                    _f(g[0], "n_news_untradeable")
            b = [r for r in bld if r["asset"] == asset
                 and _era_sel(int(r["year"]), era)]
            if b:
                ins = [_f(r, "insane_frac") for r in b]
                ins = [v for v in ins if np.isfinite(v)]
                out[(asset, era, "insane_frac_mean")] = \
                    M.mean(ins) if ins else float("nan")
                out[(asset, era, "insane_frac_max")] = \
                    (max(ins) if ins else float("nan"))
    return out


def paired_metrics():
    """Per-session measures compared on the SAME sessions in both arms."""
    _, off_b = _tsv(M.out_path(BEFORE_DIR, "session_offer.tsv"))
    _, off_a = _tsv(M.out_path(AFTER_DIR, "session_offer.tsv"))
    _, seat_b = _tsv(M.out_path(BEFORE_DIR, "census_union_seatable.tsv"))
    _, seat_a = _tsv(M.out_path(AFTER_DIR, "census_union_seatable.tsv"))
    full = lambda r: r["window"] == "FULL"            # noqa: E731
    before, after = {}, {}
    for asset in M.ASSET_ORDER:
        for era in (M.ERA_FIT, M.ERA_GATE, M.ERA_ALL):
            for (name, rb, ra, col, where, stat) in (
                    ("offer_best_leg_median_FULL", off_b, off_a,
                     "best_leg_usd", full, "med"),
                    ("offer_range_median_FULL", off_b, off_a, "range_usd",
                     full, "med"),
                    ("offer_legs1k_mean_FULL", off_b, off_a, "legs_1k", full,
                     "mean"),
                    ("n_observed_seconds_median", off_b, off_a,
                     "n_observed_seconds", full, "med"),
                    ("dp_seatable_median", seat_b, seat_a,
                     "union_dp_close_usd", None, "med"),
                    ("dp_seatable_mean", seat_b, seat_a, "union_dp_close_usd",
                     None, "mean"),
                    ("candidates_per_session_median", seat_b, seat_a,
                     "n_union", None, "med")):
                va, vb, lost = paired(
                    _by_session(rb, asset, era, col, where),
                    _by_session(ra, asset, era, col, where))
                if not va:
                    continue
                f = M.med if stat == "med" else M.mean
                before[(asset, era, name)] = f(va)
                after[(asset, era, name)] = f(vb)
                if name == "offer_range_median_FULL":
                    before[(asset, era, "n_sessions_offer_defined")] = len(va)
                    after[(asset, era, "n_sessions_offer_defined")] = len(va)
                    before[(asset, era,
                            "n_sessions_lost_all_seconds")] = 0.0
                    after[(asset, era,
                           "n_sessions_lost_all_seconds")] = float(lost)
    return before, after


def main():
    M.verify_spec_m1b()
    before, after = paired_metrics()
    before.update(metrics(BEFORE_DIR))
    after.update(metrics(AFTER_DIR))
    keys = sorted(set(before) | set(after),
                  key=lambda k: (M.ASSET_ORDER.index(k[0])
                                 if k[0] in M.ASSET_ORDER else 9,
                                 k[1], k[2]))
    rows, flagged = [], []
    for k in keys:
        b, a = before.get(k, float("nan")), after.get(k, float("nan"))
        d = a - b if (np.isfinite(a) and np.isfinite(b)) else float("nan")
        pct = (100.0 * d / b) if (np.isfinite(d) and b not in (0.0,)
                                  and np.isfinite(b)) else float("nan")
        vr = k[2] in VERDICT_RELEVANT
        flag = ""
        if vr and np.isfinite(pct) and abs(pct) > FLAG_PCT:
            flag = "ORCHESTRATOR ADDENDUM REQUIRED"
            flagged.append((k, b, a, pct))
        rows.append([k[0], k[1], k[2], b, a, d, pct, int(vr), flag])
    M.write_tsv(M.out_path(OUT_DIR, "mask_impact.tsv"), SECTION,
                C.params_hash(PARAMS), COLUMNS, rows, spec="PORT_M1B",
                extra=["before = %s (no mask), after = %s (D-054 mask); the "
                       "arms differ ONLY by the mask" % (BEFORE_DIR, AFTER_DIR),
                       "flag fires when a verdict-relevant metric moves more "
                       "than %.0f%%" % FLAG_PCT])
    M.hb("mask impact: %d rows, %d verdict-relevant moves > %.0f%%"
         % (len(rows), len(flagged), FLAG_PCT))
    for (k, b, a, pct) in flagged:
        M.hb("  FLAG %s %s %s: %.2f -> %.2f (%+.1f%%)"
             % (k[0], k[1], k[2], b, a, pct))
    return 0


if __name__ == "__main__":
    sys.exit(main())
