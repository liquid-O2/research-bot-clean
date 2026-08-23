#!/usr/bin/env python3
"""Cash the two-regime split — ticket 53 (2026-08-23).

Ticket 50 (corrected) established that on HG the price-extreme picker ranks
usefully in cheap cells (payer at percentile 0.309) and is a coin flip in rich
ones (0.502, chance), against a null band of +/-0.11. Ticket 52 established that
cell richness is causally predictable from the FIRST event's own row, on NKD and
SI, from an activity/speed/width family (`w1800_event_rate` +0.523/+0.468 and
kin), against a null floor of 0.26-0.38.

Neither is dollars. This probe joins them and cashes the result.

WHAT IT MEASURES
  1. Split cells by the TRAIN-fitted conditioner into predicted-cheap and
     predicted-rich.
  2. Per regime: the realised cell-best (does the conditioner actually sort
     cells by value), the picker's payer-percentile (is it really chance in the
     rich regime), and the dollars the picker banks.
  3. Two-regime arms, each one entry per phase:
       EXTREME_ALL     the ticket-39 baseline, price extreme everywhere
       CHEAP_ONLY      take the extreme in predicted-cheap cells, skip the rich
       SPLIT_LAST      extreme in cheap, LAST event in rich
       SPLIT_SECOND    extreme in cheap, 2nd-by-score in rich
       SPLIT_ACTIVE    extreme in cheap, most-active event in rich

PREREGISTRATION
- The conditioner is a unit-weight mean of within-block z-scores over the
  ticket-52 survivors for THAT asset, non-clock only. Clock columns
  (`phase_remaining_sec`, `phase_index`, anything matching the clock pattern)
  are EXCLUDED: they correlate with cell size because more time means more room,
  which is capacity, not regime, and it is the tautology that ate ticket 26.
- The split threshold is the TRAIN median of the conditioner. No tuning.
- Nulls shuffle the score within the cell, as everywhere else in this program.
- Rung letters carry the noise floor (RESOLVE_SE).
- TRAIN decides everything; THRESHOLD is read once, for the record.

Selftest: python3 tools/probe_regime_split.py --selftest
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

import numpy as np

os.environ.setdefault("OMP_NUM_THREADS", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from probe_extreme_events import extreme_events  # noqa: E402
from probe_hold_running_extreme import (  # noqa: E402
    _cash_flag, _cash_stats, _cell_groups, _entries_per_day, _rung_letter, _stage_a,
)
from probe_location_family_screen import _col  # noqa: E402
from probe_path_dedup import _formation_sec  # noqa: E402
from probe_path_dedup_live import DELTA_SEC, FORM_DELTA, SIDE_COL, VWAP_COL  # noqa: E402
from probe_rho_on_dedup import WIDTH_MULT, _keep_idx  # noqa: E402
from probe_rho_ruler import BLOCKS, RUNG_USD  # noqa: E402
from probe_trained_accrual import ProbeRefusal, load_delta_rows  # noqa: E402

SCHEMA = "QRE2REGIMESPLIT1"
CLOCK_RE = re.compile(r"elapsed|remaining|age_sec|phase_index|min_alert|_ts_", re.I)
PRICE_COL = "disc_prior_high_aligned_usd"
SURVIVE_TRAIN = 0.30
SURVIVE_HELD = 0.20


def _rank(a: np.ndarray) -> np.ndarray:
    o = np.argsort(a, kind="stable")
    r = np.empty(len(a), float)
    r[o] = np.arange(len(a))
    return r


def conditioner_columns(x_tr, y_cell_tr, x_th, y_cell_th, names) -> list[tuple[int, float]]:
    """Ticket-52 survivors for one asset, clock family EXCLUDED.

    Clock columns predict cell size because a phase with more time left has more
    room for a big move. That is capacity, not regime, and promoting it would
    repeat ticket 26's tautology.
    """
    keep = []
    rtr, rth = _rank(y_cell_tr), _rank(y_cell_th)
    for j, name in enumerate(names):
        if CLOCK_RE.search(name):
            continue
        a, b = x_tr[:, j].astype(np.float64), x_th[:, j].astype(np.float64)
        if not np.isfinite(a).all() or not np.isfinite(b).all():
            continue
        if np.std(a) == 0 or np.std(b) == 0:
            continue
        ctr = float(np.corrcoef(_rank(a), rtr)[0, 1])
        cth = float(np.corrcoef(_rank(b), rth)[0, 1])
        if abs(ctr) >= SURVIVE_TRAIN and abs(cth) >= SURVIVE_HELD and np.sign(ctr) == np.sign(cth):
            keep.append((j, float(np.sign(ctr))))
    return keep


def conditioner_score(x, cols) -> np.ndarray:
    """Unit-weight mean of signed z-scores. D6 measured that unit weights beat
    trees on this plane, so the composite is deliberately not fitted."""
    if not cols:
        return np.zeros(len(x))
    zs = []
    for j, sign in cols:
        v = x[:, j].astype(np.float64)
        sd = float(np.std(v))
        zs.append(sign * (v - float(np.mean(v))) / sd if sd > 0 else np.zeros(len(v)))
    return np.mean(np.vstack(zs), axis=0)


def cell_arms(ev, price, formed, cell, rich_cells, active) -> dict[str, np.ndarray]:
    """One entry per cell. Every arm takes the price extreme where the
    conditioner says CHEAP; they differ only in what they do where it says RICH,
    because that is the only regime where the extreme is known to be chance."""
    arms = {k: np.zeros(len(ev), bool) for k in
            ("EXTREME_ALL", "CHEAP_ONLY", "SPLIT_LAST", "SPLIT_SECOND", "SPLIT_ACTIVE")}
    for g in _cell_groups(cell):
        gi = g[ev[g]]
        if not len(gi):
            continue
        rich = bool(rich_cells.get(int(cell[g[0]]), False))
        order = gi[np.argsort(price[gi])]        # the picker's order, best first
        top = int(order[0])
        arms["EXTREME_ALL"][top] = True
        if not rich:
            for k in ("CHEAP_ONLY", "SPLIT_LAST", "SPLIT_SECOND", "SPLIT_ACTIVE"):
                arms[k][top] = True
            continue
        arms["SPLIT_LAST"][int(gi[int(np.argmax(formed[gi]))])] = True
        arms["SPLIT_SECOND"][int(order[1] if len(order) > 1 else order[0])] = True
        arms["SPLIT_ACTIVE"][int(gi[int(np.argmax(active[gi]))])] = True
    return arms


def run(matrix_dir: Path, out_path: Path, *, blocks=BLOCKS, log=print) -> dict:
    r180 = load_delta_rows(matrix_dir, deltas=(DELTA_SEC,))
    r0 = load_delta_rows(matrix_dir, deltas=(FORM_DELTA,))
    if not np.isfinite(r180.y).all():
        raise ProbeRefusal("non-finite y on the component matrix")
    names = r180.feature_names
    rng = np.random.default_rng(20260823)
    report: dict = {"schema": SCHEMA, "prereg": __doc__,
                    "matrix_receipt": r180.matrix_receipt, "assets": {}}

    def frame(asset, bname, orient=None):
        lo, hi = blocks[bname]
        idx = np.flatnonzero((r180.asset == asset) & (r180.day >= lo) & (r180.day <= hi)
                             & (r180.delta == DELTA_SEC))
        kept = _keep_idx(r180, r0, idx, asset)
        d = dict(y=r180.y[kept], cell=r180.cell[kept], day=r180.day[kept],
                 elapsed=r180.elapsed[kept], occ=r180.occupancy[kept], x=r180.x[kept],
                 side=r180.x[kept, _col(names, SIDE_COL)].astype(np.float64),
                 formed=_formation_sec(r180.x[kept], names),
                 price=r180.x[kept, _col(names, PRICE_COL)].astype(np.float64))
        d["days"] = sorted({int(v) for v in d["day"]})
        vw = r180.x[kept, _col(names, VWAP_COL)].astype(np.float64)
        if orient is None:
            orient = _stage_a(d["y"], d["side"], vw, d["cell"], d["day"], d["elapsed"],
                              d["occ"], d["days"], RUNG_USD[asset], rng, 8)["best_orientation"]
        d["orient"] = orient
        d["ev"], _, _ = extreme_events(d["formed"], d["side"], vw, d["cell"],
                                       orient.startswith("long_min"), orient.endswith("short_min"))
        first, best, ids = [], [], []
        for g in _cell_groups(d["cell"]):
            gi = g[d["ev"][g]]
            if len(gi) < 2:
                continue
            first.append(int(gi[int(np.argmin(d["formed"][gi]))]))
            best.append(float(np.max(d["y"][gi])))
            ids.append(int(d["cell"][g[0]]))
        d["first_x"] = r180.x[kept][np.asarray(first)] if first else np.zeros((0, len(names)))
        d["cell_best"] = np.asarray(best); d["cell_ids"] = np.asarray(ids)
        return d

    for asset in sorted(set(r180.asset.tolist())):
        if asset not in WIDTH_MULT:
            continue
        rung = RUNG_USD[asset]
        tr = frame(asset, "train")
        th = frame(asset, "threshold", tr["orient"])
        cols = conditioner_columns(tr["first_x"], tr["cell_best"],
                                   th["first_x"], th["cell_best"], names)
        entry = {"rung_usd": rung, "orientation": tr["orient"],
                 "n_conditioner_columns": len(cols),
                 "conditioner_columns": [names[j] for j, _ in cols][:20]}
        report["assets"][asset] = entry
        log(f"\n=== {asset}  conditioner columns (non-clock): {len(cols)}")
        if not cols:
            entry["letter"] = "no_conditioner"
            log(f"{asset:4s} no non-clock conditioner survives; two-regime split not testable")
            continue
        cut = float(np.median(conditioner_score(tr["first_x"], cols)))
        entry["train_median_cut"] = cut

        for bname, d in (("train", tr), ("threshold", th)):
            sc = conditioner_score(d["first_x"], cols)
            rich_ids = {int(c): bool(v > cut) for c, v in zip(d["cell_ids"], sc)}
            rich = np.asarray([rich_ids[int(c)] for c in d["cell_ids"]])
            # does the conditioner actually sort cells by value?
            cb_cheap = float(np.mean(d["cell_best"][~rich])) if (~rich).any() else float("nan")
            cb_rich = float(np.mean(d["cell_best"][rich])) if rich.any() else float("nan")
            # is the picker really chance in the rich regime?
            pcts = {True: [], False: []}
            for g in _cell_groups(d["cell"]):
                gi = g[d["ev"][g]]
                if len(gi) < 3:
                    continue
                order = gi[np.argsort(d["price"][gi])]
                payer = gi[int(np.argmax(d["y"][gi]))]
                pcts[rich_ids.get(int(d["cell"][g[0]]), False)].append(
                    int(np.flatnonzero(order == payer)[0]) / (len(gi) - 1))
            active = d["x"][:, _col(names, "w1800_event_rate")].astype(np.float64) \
                if "w1800_event_rate" in names else d["formed"]
            arms = cell_arms(d["ev"], d["price"], d["formed"], d["cell"], rich_ids, active)
            rows = []
            for nm, flag in arms.items():
                st = _cash_stats(flag, d["y"], d["cell"], d["day"], d["elapsed"],
                                 d["occ"], d["days"])
                rows.append({"arm": nm, **st,
                             "letter": _rung_letter(st["usd_per_asset_day"], st["usd_se"],
                                                    rung, "split"),
                             **_entries_per_day(flag, d["day"], d["days"])})
            rows.sort(key=lambda r: -r["usd_per_asset_day"])
            entry[bname] = {"cell_best_cheap": cb_cheap, "cell_best_rich": cb_rich,
                            "payer_pct_cheap": float(np.mean(pcts[False])) if pcts[False] else None,
                            "payer_pct_rich": float(np.mean(pcts[True])) if pcts[True] else None,
                            "n_cheap": int((~rich).sum()), "n_rich": int(rich.sum()),
                            "arms": rows}
            log(f"{asset:4s} {bname:10s} cells cheap {int((~rich).sum())} rich {int(rich.sum())} | "
                f"cell-best cheap ${cb_cheap:6.0f} rich ${cb_rich:6.0f} | payer pct "
                f"cheap {entry[bname]['payer_pct_cheap'] or 0:.3f} "
                f"rich {entry[bname]['payer_pct_rich'] or 0:.3f}")
            for r in rows:
                log(f"       {r['arm']:14s} ${r['usd_per_asset_day']:7.0f} "
                    f"se ${r['usd_se']:5.0f} ent/d {r['entries_per_day_max']} {r['letter']}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=1, sort_keys=True))
    return report


def selftest() -> int:
    assert CLOCK_RE.search("phase_remaining_sec") and CLOCK_RE.search("phase_index")
    assert not CLOCK_RE.search("w1800_event_rate")
    assert not CLOCK_RE.search("disc_prior_range_usd")

    z = conditioner_score(np.array([[1.0], [3.0]]), [(0, 1.0)])
    assert abs(z[0] + 1.0) < 1e-9 and abs(z[1] - 1.0) < 1e-9, z
    # A negative TRAIN sign must FLIP the composite. The earlier form of this
    # line read `(... - 1.0) < 1e-9`, which is true for anything <= 1 and so
    # asserted nothing; a sign-dropping mutant walked straight through it.
    zn = conditioner_score(np.array([[1.0], [3.0]]), [(0, -1.0)])
    assert abs(zn[0] - 1.0) < 1e-9 and abs(zn[1] + 1.0) < 1e-9, zn
    assert conditioner_score(np.zeros((3, 1)), []).tolist() == [0.0, 0.0, 0.0]

    # The clock family must be excluded by conditioner_columns itself, not just
    # matched by the regex. Both planted columns predict the target perfectly;
    # only the non-clock one may survive.
    tgt = np.arange(20, dtype=float)
    x = np.column_stack([tgt, tgt])
    kept = conditioner_columns(x, tgt, x, tgt, ["phase_remaining_sec", "w1800_event_rate"])
    assert [j for j, _ in kept] == [1], (kept, "the clock column was not excluded")

    ev = np.array([True, True, True])
    price = np.array([-9.0, -5.0, -1.0])       # extreme first
    formed = np.array([0.0, 100.0, 200.0])
    cell = np.array([4, 4, 4])
    active = np.array([1.0, 9.0, 2.0])
    cheap = cell_arms(ev, price, formed, cell, {4: False}, active)
    assert cheap["EXTREME_ALL"].tolist() == [True, False, False]
    for k in ("CHEAP_ONLY", "SPLIT_LAST", "SPLIT_SECOND", "SPLIT_ACTIVE"):
        assert cheap[k].tolist() == [True, False, False], (k, cheap[k])
    rich = cell_arms(ev, price, formed, cell, {4: True}, active)
    assert rich["EXTREME_ALL"].tolist() == [True, False, False]
    assert not rich["CHEAP_ONLY"].any(), "CHEAP_ONLY must abstain in a rich cell"
    assert rich["SPLIT_LAST"].tolist() == [False, False, True]
    assert rich["SPLIT_SECOND"].tolist() == [False, True, False]
    assert rich["SPLIT_ACTIVE"].tolist() == [False, True, False]
    for k, f in rich.items():
        assert f.sum() <= 1, (k, f)
    print("selftest OK: clock columns excluded, unit-weight z composite signs "
          "correctly, every arm is one-entry-per-cell, and the rich-regime arms "
          "diverge from the extreme exactly where they should")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--matrix-dir", type=Path)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.matrix_dir is None or a.out is None:
        ap.error("--matrix-dir and --out are required unless --selftest")
    run(a.matrix_dir, a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
