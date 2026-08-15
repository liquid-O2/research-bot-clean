#!/usr/bin/python3
"""PORT M2 — THE HONEST CAUSAL BASELINE TABLE.  Replaces the freeze table.

WHAT THIS IS
  The one table a deployment decision may be taken from.  Every number in it is
  earnable at the arrival second: the decision at arrival j reads only arrivals
  <= j, one position per (asset, session), the <=10 trades/day cap applied
  causally, the $900 wall live, the adopted first-wall stop armed.

  It replaces `design/CHAMPION_FREEZE_CANDIDATE*.md`, which is VOID: every
  figure there comes from `newobj.top_per_cell_score`, the cell's eventual
  argmax, a rule that needs ~5.5 hours of future arrivals on average
  (LEAK_SEATING_CENSUS.tsv) before it can name the seat it claims to take now.

THE SELECTION DISCIPLINE, which is the whole difference between this table and
a hopeful one
  The (score, policy, knob) triple is chosen ON THE PREVIOUS ERA — era k-1 is
  finished history at the start of era k — and applied BLIND to era k.  Nothing
  in an era's own outcome ever selects the rule that is scored on it.  The
  eval-era argmax is reported BESIDE it, labelled UPPER BOUND, purely so the
  size of the selection premium is visible rather than hidden.

THE THREE REFERENCE LEVELS, all on the same rows
  DP CEILING        full-hindsight one-position DP.  Survives the seating
                    defect because a ceiling is a bound, not a policy.
  PROPHET           the ceiling of ANY arrival-time model: causal in structure,
                    granted the true value of the candidate in front of it.
  LUCK BAR          the search-adjusted null: the identical policy family on
                    shuffled scores with arrival times preserved.

  honest - luck  =  what the rule actually knows.
  prophet - honest = the PREDICTION gap (a modelling target).
  dp - prophet     = the STRUCTURE gap (the price of arrival-time decision,
                     which no model recovers and only a contract change could).

CLI  causal_baseline.py --run [--eras ...]
"""
import argparse
import os
import sys

import numpy as np

_H = os.path.dirname(os.path.abspath(__file__))
for _p in (_H, "/workspace/engine/port_m2/seqtest", "/workspace/engine/port_m0",
           "/workspace/engine/port_m1", "/workspace/engine/port_m3",
           "/workspace/artifacts/cache/pylibs"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import newobj as N                        # noqa: E402
import arrival as AR                      # noqa: E402

ERA_ORDER = ("E3", "E4", "E5", "E6", "E7")
ASSETS = ("ALL", "SI", "HG", "NKD")
FLOOR = 2000.0
# THE DENOMINATOR IS THE CAUSAL ORACLE (arrival.CAUSAL_ORACLE), never the
# full-hindsight DP ceiling: an arrival-time rule may not be asked to capture a
# fraction of a bound that is allowed to see the whole day.


def hb(m):
    N.hb("[causal_baseline] %s" % m)


class BaselineRefusal(RuntimeError):
    """A guard fired.  Never downgraded, never silently filtered."""


def all_scores(D, era):
    """The full arrival-score zoo: the committed scores plus, where they exist,
    the models TRAINED FOR the arrival decision (arrival_fit step 2)."""
    Z = AR.zoo(D, era)
    import arrival_fit as AF
    for t in AF.TARGETS:
        cols = []
        for s in AR.SEEDS:
            p = os.path.join(AF.SCORES, "%s_%s_%d.npy" % (t, era, s))
            if os.path.exists(p):
                cols.append(np.load(p).astype(np.float64))
        if cols:
            Z[t] = cols
    return Z


def _resolve(D, tr, sname, col):
    if sname == "S_TABPFN_AGREE":
        a_, b_ = col
        return AR.ecdf_map(a_, tr) * AR.ecdf_map(b_, tr)
    return np.asarray(col, dtype=np.float64)


def sweep(D, P, era, keys=None, with_null=True):
    """(score, policy) -> mean $/session, plus the SEARCH-ADJUSTED LUCK BAR.

    The luck bar must be computed over the SAME FAMILY WIDTH the winner was
    selected from, or it is not a luck bar at all — so the shuffled arm is run
    inside this same sweep, cell for cell, with the ARRIVAL TIMES PRESERVED and
    only the row->score pairing destroyed.  The era's bar is the BEST of those
    shuffled cells.
    """
    import stacked_final as SF
    import newobj_arms as NA
    tr, itr, iva, ev = NA.fold(D, era)
    Z = all_scores(D, era)
    rng = np.random.default_rng(N.SEED)
    out, null = {}, {}
    for sname, cols in Z.items():
        for pname, kind, knob in AR.POLICIES:
            if keys is not None and (sname, pname) not in keys:
                continue
            vals, nvals = [], []
            for col in cols:
                v = _resolve(D, tr, sname, col)
                rp = N.replay_delayed(
                    D, AR.build_seats(D, ev, v, kind, knob, tr), P)
                r = N.read_rows(D, SF.apply_stop(
                    D, AR.cap_seats(D, rp), "STOP_WALL1"))
                if r.get("usd_per_session") is not None:
                    vals.append(r["usd_per_session"])
                if with_null:
                    vs = v.copy()
                    fin = np.nonzero(np.isfinite(vs))[0]
                    vs[fin] = vs[rng.permutation(fin)]
                    rp2 = N.replay_delayed(
                        D, AR.build_seats(D, ev, vs, kind, knob, tr), P)
                    r2 = N.read_rows(D, SF.apply_stop(
                        D, AR.cap_seats(D, rp2), "STOP_WALL1"))
                    if r2.get("usd_per_session") is not None:
                        nvals.append(r2["usd_per_session"])
            if vals:
                out[(sname, pname)] = float(np.mean(vals))
            if nvals:
                null[(sname, pname)] = float(np.mean(nvals))
    out["__LUCK__"] = max(null.values()) if null else None
    return out


def evaluate(D, P, era, sname, pname, per_asset=True):
    """The chosen rule, read per asset with day-clustered intervals."""
    import stacked_final as SF
    import newobj_arms as NA
    tr, itr, iva, ev = NA.fold(D, era)
    Z = all_scores(D, era)
    kind, knob = dict((p, (k, q)) for p, k, q in AR.POLICIES)[pname]
    out = {}
    per_seed_rows = []
    for col in Z[sname]:
        v = _resolve(D, tr, sname, col)
        rp = N.replay_delayed(D, AR.build_seats(D, ev, v, kind, knob, tr), P)
        per_seed_rows.append(SF.apply_stop(D, AR.cap_seats(D, rp),
                                           "STOP_WALL1"))
    for asset in (ASSETS if per_asset else ("ALL",)):
        vals, cap, nse = [], [], []
        for rows in per_seed_rows:
            sub = rows if asset == "ALL" else [
                r for r in rows if r["session"].split("|")[0] == asset]
            if not sub:
                continue
            r = N.read_rows(D, sub)
            if r.get("usd_per_session") is None:
                continue
            vals.append(r["usd_per_session"])
            cap.append(r.get("capture_day"))
            nse.append(r["n_seated"] / max(r["n_sessions"], 1))
        if vals:
            out[asset] = (np.asarray(vals, dtype=np.float64),
                          float(np.mean(nse)),
                          [c for c in cap if c is not None])
    return out


def run(eras=("E5", "E6", "E7")):
    import champ_floor as CF
    import confidence as CO
    D, P = CF.boot()
    ceil = CO.ceilings()
    rows = []
    prev_best, luck, best_val = {}, {}, {}
    for era in ERA_ORDER:
        if era not in eras and era not in [
                ERA_ORDER[max(ERA_ORDER.index(e) - 1, 0)] for e in eras]:
            continue
        sw = sweep(D, P, era)
        luck[era] = sw.pop("__LUCK__", None)
        if sw:
            prev_best[era] = max(sw, key=sw.get)
            best_val[era] = sw[prev_best[era]]
        hb("%s swept: %d cells; argmax %s $%s; LUCK BAR $%s"
           % (era, len(sw), prev_best.get(era),
              N._r(best_val.get(era)), N._r(luck.get(era))))
    for era in eras:
        i = ERA_ORDER.index(era)
        prior = ERA_ORDER[i - 1] if i > 0 else None
        chosen = prev_best.get(prior)
        if chosen is None:
            hb("%s: NO PRIOR ERA — the honest row cannot be formed" % era)
            continue
        own = prev_best.get(era)
        cl_all = ceil.get("%s|ALL" % era)
        for label, key, kind in (("HONEST_PREV_ERA_SELECTED", chosen,
                                  "deployable"),
                                 ("UPPER_BOUND_OWN_ERA_ARGMAX", own,
                                  "SELECTION-PREMIUM UPPER BOUND")):
            if key is None:
                continue
            res = evaluate(D, P, era, key[0], key[1])
            for asset in ASSETS:
                if asset not in res:
                    continue
                a, nse, cap = res[asset]
                cl = (AR.CAUSAL_ORACLE.get(era) if asset == "ALL"
                      else ceil.get("%s|%s" % (era, asset)) or cl_all)
                aim = 0.80 * cl if cl else None
                rows.append([
                    era, "BINDING" if era in AR.BINDING else "context", asset,
                    label, kind, "%s|%s" % key, int(a.size), N._r(a.mean()),
                    N._r(a.std()), N._r(nse, 3), N._r(cl),
                    N._r(a.mean() / cl, 4) if cl else "", N._r(aim),
                    N._r(a.mean() - aim) if aim else "",
                    N._r(a.mean() - FLOOR),
                    "1" if (cl and cl >= FLOOR / 0.80) else "0",
                    N._r(luck.get(era)),
                    "YES" if (luck.get(era) is not None
                              and a.mean() > luck[era]) else "no"])
    if not rows:
        raise BaselineRefusal(
            "CAUSAL_BASELINE produced ZERO rows — a null prints rows, so this "
            "is a FAILURE, not a result")
    N.write_tsv(
        "CAUSAL_BASELINE.tsv",
        ["era", "criterion", "asset", "row", "kind", "rule", "n_seeds",
         "usd_per_session", "sd_usd", "seats_per_session", "oracle_ceiling",
         "capture_of_ceiling", "aim_08ceiling", "gap_to_aim",
         "gap_to_floor_2000", "ceiling_supports_floor",
         "search_adjusted_luck_bar", "beats_luck_bar"], rows,
        extra=[
            "THE HONEST CAUSAL BASELINE — the table a deployment decision may "
            "be taken from, and the replacement for the VOID freeze table.  "
            "Every figure is earnable at the arrival second: the decision at "
            "arrival j reads only arrivals <= j, one position per "
            "(asset, session), the <=10/day cap applied causally, the $900 "
            "wall live, the first-wall stop armed.",
            "SELECTION DISCIPLINE: the (score, policy, knob) triple is chosen "
            "on the PREVIOUS ERA — finished history at the start of the eval "
            "era — and applied BLIND.  The eval-era argmax is printed beside "
            "it ONLY so the selection premium is visible instead of hidden; it "
            "is labelled an upper bound and is never a promotion target.",
            "Capture and aims are against the surviving ORACLE ceilings "
            "(full-hindsight DP), which are bounds rather than policies and "
            "are untouched by the seating defect.  ARRIVAL_PROPHET.tsv carries "
            "the tighter, arrival-time ceiling that splits this gap into its "
            "prediction and structure halves."])
    hb("CAUSAL_BASELINE.tsv: %d rows" % len(rows))
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--eras", nargs="*", default=None)
    a = ap.parse_args()
    if a.run:
        run(eras=tuple(a.eras) if a.eras else ("E5", "E6", "E7"))
    else:
        ap.print_help()
