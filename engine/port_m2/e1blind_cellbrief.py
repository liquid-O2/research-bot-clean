#!/usr/bin/python3
"""E1 BLIND — THE AS-OF CELL BRIEF (CC-M2-19.2 composition order SIDE > SEAT >
MOMENT, driven by the D14 as-of stepper).

For every (asset, phase) cell of a blind day, this prints WHAT IS KNOWABLE AT
THE CELL'S OPEN — strictly the driver prefix whose cut is the first one at
which the cell becomes visible.  Nothing from later in the day is read (that is
the D14 leak the blind round exists to prevent), and no S14 file exists in this
round at all.

WHAT R10 FOUND, AND WHAT CHANGED.  The brief used to be built from the
DAY-COMPLETE index (`--full`, handed in by `lab/e1blind_day.sh`), and printed
two aggregates over it at cell open: `"%d candidates in the cell"` and a full
per-cell CLASS HISTOGRAM captioned "counts only — no later row's fields are
read".  A count over later rows IS a read of later rows.  It was also
decision-relevant rather than cosmetic: the reader's only registered increment
over the frozen declared policy is the CREATION-CLASS gate, and that histogram
told it, before the cell's first call, how many gate-passing rows the cell
would produce for the rest of the phase — i.e. whether to spend the phase-close
seat now or wait.  Days 6 and 7 declared the smaller version of this exposure
on the record; the blind brief carried no declaration and widened it from a
count to a class breakdown.

  * the brief is now driven ENTIRELY by the driver prefixes.  A cell is briefed
    at the FIRST cut where any of its rows is visible, using only that prefix.
  * every cross-row aggregate is computed on rows with `sec <= cut`, and the
    cell-local aggregate is explicitly labelled PREFIX-ONLY with its cut.
  * `--full` is still accepted so the round driver's command line is unchanged,
    and IS NOT OPENED.  Passing it prints a declaration saying so.

AND THE GUARD (R31).  Three consecutive study days carried a prefix guard and
the blind brief — the one that runs on the SCORED instrument — carried none.
The study guards are also self-checks: they filter `_sec < cut` and then assert
`_sec < cut`, which cannot fail.  A REAL guard checks the EMITTED FIELDS
against `triage_index.field_asof_sec`, the module that owns the question "when
does this column become knowable", and that is what `_assert_emitted_asof`
below does: for every (row, column) this brief prints, the field's knowability
second must be <= the cut.  It catches the OBSERVED_COLS class (`short_day`,
`observed_close`, `runway_observed` — end-of-session facts) as well as row
ordering, which a `sec` filter alone never can.
"""
import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import triage_index as TI                                         # noqa: E402

NA = ("", ".", None)


def read_tsv(path):
    with open(path) as fh:
        return list(csv.DictReader([l for l in fh if not l.startswith("#")],
                                   delimiter="\t"))


def f(r, k):
    try:
        return float(r[k])
    except Exception:
        return None


# ------------------------------------------------------------- the guard ----
def _asof_row(r):
    """`r` with the index's NA token normalised to None, which is what
    `triage_index.field_asof_sec` expects (it does `int(row["observed_close"])`
    and a masked cell is the literal '.')."""
    return {k: (None if v in NA else v) for k, v in r.items()}


def _assert_emitted_asof(rows, cols, cut, where):
    """R31 — THE REAL PREFIX GUARD.

    Refuses if any EMITTED field of any emitted row is knowable only after
    `cut`, per `triage_index.field_asof_sec`.  This is not a restatement of the
    filter that produced `rows`: the OBSERVED_COLS block is knowable only at
    the observed close whatever the row's own decision second is, so a row that
    passes `sec <= cut` can still carry a field that does not.
    """
    for r in rows:
        a = _asof_row(r)
        sec = a.get("sec")
        if sec is None:
            raise SystemExit("AS-OF REFUSAL [%s]: row %s carries no decision "
                             "second" % (where, r.get("cid")))
        if int(float(sec)) > cut:
            raise SystemExit("AS-OF REFUSAL [%s]: row %s at sec=%s is LATER "
                             "than the cut %d (D14 scan exposure)"
                             % (where, r.get("cid"), sec, cut))
        for c in cols:
            if a.get(c) is None:
                continue
            k = TI.field_asof_sec(a, c)
            if k is not None and int(k) > cut:
                raise SystemExit(
                    "AS-OF REFUSAL [%s]: row %s field %s is knowable only at "
                    "%d > cut %d (triage_index.field_asof_sec)"
                    % (where, r.get("cid"), c, int(k), cut))
    return True


# the columns this brief actually prints, in print order.  The guard is driven
# off THIS tuple, so adding a field to the brief without adding it here is the
# one way to route around the guard — and the fix-lane test drives that mutant.
EMITTED = ("day_type_so_far", "range_so_far", "range_vs_hat_pct", "cov_sess",
           "unspent_sess", "rv1800", "rv300", "rv60", "rv_collapse",
           "vol_regime", "surprise", "q10", "q50", "ladder_pos",
           "phase_H", "phase_H_sec", "phase_L", "phase_L_sec", "runway_phase",
           "exit_is_sess", "fph_sflow", "fph_vol", "f30m_sflow", "f30m_vol",
           "f5m_sflow", "f5m_vol", "f60_sflow", "f60_vol",
           "trapped_above", "trapped_below", "phase_total",
           "thru_n", "thru_bid", "thru_ask", "d_POC", "in_VA",
           "sched_last_age", "sched_next_in", "mid", "spread_dec", "cost_rt",
           "cls", "clock", "sec", "asset", "phase_dec")


def cuts_of(drive):
    out = []
    for fn in sorted(os.listdir(drive)):
        if not fn.startswith("ASOF_"):
            continue
        try:
            out.append((int(fn.split("_")[1].split(".")[0]), fn))
        except ValueError:
            continue
    out.sort()
    return out


def brief_cell(first, cellrows, assetrows, cut, fn, k):
    """One cell's at-open brief.  `cellrows` / `assetrows` are PREFIX rows."""
    print("=" * 78)
    print("CELL %s/%s — opens %s (sec %d)"
          % (k[0], k[1], first["clock"], int(float(first["sec"]))))
    print("  as-of prefix: %s (cut %d; %d rows of this asset visible, %d of "
          "this cell)" % (fn, cut, len(assetrows), len(cellrows)))
    print("  AT THE OPEN — session state (prefix only):")
    print("    day_type_so_far=%s range_so_far=%s range_vs_hat=%s%% "
          "cov_sess=%s unspent_sess=%s"
          % (first.get("day_type_so_far"), first.get("range_so_far"),
             first.get("range_vs_hat_pct"), first.get("cov_sess"),
             first.get("unspent_sess")))
    print("    vol: rv1800=%s rv300=%s rv60=%s rv_collapse=%s "
          "vol_regime=%s surprise=%s q10/q50=%s/%s ladder=%s"
          % (first.get("rv1800"), first.get("rv300"), first.get("rv60"),
             first.get("rv_collapse"), first.get("vol_regime"),
             first.get("surprise"), first.get("q10"), first.get("q50"),
             first.get("ladder_pos")))
    print("    phase: H=%s (%ss) L=%s (%ss) runway_phase=%s exit_is_sess=%s"
          % (first.get("phase_H"), first.get("phase_H_sec"),
             first.get("phase_L"), first.get("phase_L_sec"),
             first.get("runway_phase"), first.get("exit_is_sess")))
    print("    flows: fph_sflow=%s/%s f30m=%s/%s f5m=%s/%s f60=%s/%s"
          % (first.get("fph_sflow"), first.get("fph_vol"),
             first.get("f30m_sflow"), first.get("f30m_vol"),
             first.get("f5m_sflow"), first.get("f5m_vol"),
             first.get("f60_sflow"), first.get("f60_vol")))
    print("    fuel map: above=%s below=%s total=%s thru n/bid/ask=%s/%s/%s"
          % (first.get("trapped_above"), first.get("trapped_below"),
             first.get("phase_total"), first.get("thru_n"),
             first.get("thru_bid"), first.get("thru_ask")))
    print("    profile: d_POC=%s in_VA=%s | schedule: last_age=%s "
          "next_in=%s | mid=%s spread=%s cost_rt=%s"
          % (first.get("d_POC"), first.get("in_VA"),
             first.get("sched_last_age"), first.get("sched_next_in"),
             first.get("mid"), first.get("spread_dec"),
             first.get("cost_rt")))
    # what the asset has already done today, prefix-only
    mids = [f(r, "mid") for r in assetrows if f(r, "mid") is not None]
    secs = [int(float(r["sec"])) for r in assetrows]
    if mids:
        # R03's twin: %.4g quantises NKD prices onto a 10-point grid
        # (2 ticks = $50/mini) and prints three genuinely different mids
        # identically.  Prices are printed at full resolution.
        print("  ASSET SO FAR (prefix, sec <= %d): %d rows %ds-%ds, mid %.10g "
              "-> %.10g (net %.10g), lo/hi %.10g/%.10g"
              % (cut, len(assetrows), secs[0], secs[-1], mids[0], mids[-1],
                 mids[-1] - mids[0], min(mids), max(mids)))
    cl = {}
    for r in assetrows:
        cl[r["cls"]] = cl.get(r["cls"], 0) + 1
    print("  classes so far (prefix, sec <= %d): %s"
          % (cut, sorted(cl.items(), key=lambda x: -x[1])))
    cl = {}
    for r in cellrows:
        cl[r["cls"]] = cl.get(r["cls"], 0) + 1
    print("  THIS CELL SO FAR (PREFIX-ONLY, sec <= %d — R10: the day-complete "
          "cell population is NOT read, and the count below will grow as the "
          "phase runs): %d rows %s"
          % (cut, len(cellrows), sorted(cl.items(), key=lambda x: -x[1])))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--drive", required=True)
    ap.add_argument("--full", default="",
                    help="R10: ACCEPTED AND NEVER OPENED. The day-complete "
                         "index is not a lawful input to an at-open brief; "
                         "the flag is kept only so the round driver's command "
                         "line does not change.")
    a = ap.parse_args()

    if a.full:
        print("NOTE (R10): --full=%s was supplied and IS NOT OPENED. Every "
              "field and every aggregate below comes from the driver prefix "
              "named on the cell's own line." % os.path.basename(a.full))

    cuts = cuts_of(a.drive)
    if not cuts:
        raise SystemExit("no ASOF_*.tsv prefixes in %s" % a.drive)

    seen = set()
    n_cells = 0
    for cut, fn in cuts:
        rows = read_tsv(os.path.join(a.drive, fn))
        rows.sort(key=lambda r: (int(float(r["sec"])), r["cid"]))
        cells = {}
        for r in rows:
            cells.setdefault((r["asset"], r["phase_dec"]), []).append(r)
        fresh = [k for k in cells if k not in seen]
        # deterministic: a cut can reveal more than one cell, order by the
        # cell's own first visible second, then by name.
        fresh.sort(key=lambda k: (int(float(cells[k][0]["sec"])), k))
        for k in fresh:
            seen.add(k)
            cellrows = cells[k]
            assetrows = [r for r in rows if r["asset"] == k[0]]
            _assert_emitted_asof(assetrows, EMITTED, cut,
                                 "%s/%s @ %s" % (k[0], k[1], fn))
            brief_cell(cellrows[0], cellrows, assetrows, cut, fn, k)
            n_cells += 1
    print("=" * 78)
    print("%d cells briefed from %d driver prefixes; the day-complete index "
          "was never opened (R10) and every emitted field was checked against "
          "triage_index.field_asof_sec (R31)." % (n_cells, len(cuts)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
