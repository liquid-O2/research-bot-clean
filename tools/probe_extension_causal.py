#!/usr/bin/env python3
"""Causal extension rule — the decision-time form of the extension prior whose cell-oracle
form cleared every asset/block (extension_prior_20260822.json; JOURNAL 2026-08-22 ~14:00Z).

PREREGISTRATION (written before the real run; echoed into the receipt):
- Question: when candidates are decided IN THE ORDER THEY ARE DECIDABLE (decision time =
  formation + Delta, nothing later visible), does "enter the first candidate of the cell whose
  extension beyond the prior-session range clears a threshold set on the prior era" keep a
  goal-relevant share of the ceiling — and how much of the cell-oracle number survives?
- Extension as in probe_extension_prior (ext = -aligned(own prior level), decision-time).
- Rules, each ≤1 entry per cell, one position per asset (occupancy), cells processed in
  time order, candidates inside a cell in decision-time order:
  THETA: enter the first candidate with ext >= theta_asset; theta_asset = the q-quantile of
    ext over TRAIN-block candidates at the same Delta, q chosen on the TRAIN block only
    (grid Q_GRID) by train capture; applied unchanged to THRESHOLD and FORWARD.
  RUNMAX: enter the first candidate whose ext exceeds every earlier-decided candidate of the
    cell by >= m ticks-in-usd, m chosen on TRAIN only (grid M_GRID); no absolute threshold.
  ORACLE: the cell-oracle MAX_EXT pick (reference ceiling for the rule, not causal).
  RANDOM: N_RANDOM uniform cell-wide picks (null; a rule must clear its 97.5th percentile).
- Delta grid {0, 180, 290}; blocks TRAIN (20210610-20210709, knob era), THRESHOLD, FORWARD.
- Denominator: per (asset, day) sum over cells of the series-best value (matrix ceiling).
  Also reported: candidates decided before firing (mean), cells entered, cells skipped.
- Verdict per (asset, block, rule): CLEARS iff the day-bootstrap 2.5th percentile exceeds
  the RANDOM null's 97.5th percentile. Knobs: q and m only, chosen on TRAIN, stated in the
  receipt. No fitting.
- Tier: DIAGNOSTIC (cell-pick dollars, not replay). A CLEARS verdict on THRESHOLD and
  FORWARD scopes down the "formation-moment candidate-local separation — null" closure for
  decision-time location rules; a failure leaves it standing.

Selftest: python3 tools/probe_extension_causal.py --selftest
Real:     python3 tools/probe_extension_causal.py --matrix-dir <round_0/component_matrix> --out <json>
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe_extension_prior import _synthetic, extension_columns  # noqa: E402
from probe_trained_accrual import DeltaRows, ProbeRefusal, _ceiling_by_day, _cell_pick, load_delta_rows  # noqa: E402

DELTAS = (0.0, 180.0, 290.0)
BLOCKS = {"train": (20210610, 20210709), "threshold": (20210721, 20210806),
          "forward": (20210809, 20210826)}
Q_GRID = (0.50, 0.60, 0.70, 0.80, 0.85, 0.90, 0.95, 0.98)
M_GRID = (0.0, 25.0, 50.0, 100.0, 200.0, 400.0)
N_RANDOM, N_BOOT = 100, 200


def causal_walk(rows: DeltaRows, idx: np.ndarray, ext: np.ndarray, *, theta: float,
                runmax_margin: float | None) -> dict:
    """Decision-time walk over one (asset, Delta) row set. Returns per-day realized dollars
    and bookkeeping. A rule fires on the FIRST decidable candidate that qualifies."""
    t = rows.elapsed[idx]
    if not np.all(np.isfinite(t)):
        raise ProbeRefusal("causal walk needs a finite session-elapsed time on every row")
    order = np.lexsort((t, rows.cell[idx], rows.day[idx]))
    realized: dict[int, float] = {}
    entered = skipped = 0; seen_before_fire = []
    prev_day, prev_exit, cur_cell, cell_done, run_max, seen = None, -np.inf, None, False, -np.inf, 0
    for j in order:
        d, c = int(rows.day[idx][j]), int(rows.cell[idx][j])
        if d != prev_day:
            prev_day, prev_exit = d, -np.inf; realized.setdefault(d, 0.0)
        if c != cur_cell:
            if cur_cell is not None and not cell_done:
                skipped += 1
            cur_cell, cell_done, run_max, seen = c, False, -np.inf, 0
        if cell_done:
            continue
        e = ext[idx][j]; seen += 1
        qualifies = (e >= theta) if runmax_margin is None else (np.isfinite(run_max) and e >= run_max + runmax_margin)
        if np.isfinite(e):
            run_max = max(run_max, e) if np.isfinite(run_max) else e
        if not qualifies or t[j] < prev_exit:
            continue
        realized[d] = realized.get(d, 0.0) + float(rows.y[idx][j])
        prev_exit = t[j] + float(rows.occupancy[idx][j])
        cell_done = True; entered += 1; seen_before_fire.append(seen)
    if cur_cell is not None and not cell_done:
        skipped += 1
    return {"realized": realized, "entered": entered, "skipped": skipped,
            "seen_before_fire_mean": float(np.mean(seen_before_fire)) if seen_before_fire else None}


def _capture(rows: DeltaRows, res: dict, ceiling: dict[int, float]) -> tuple[np.ndarray, np.ndarray]:
    days = sorted(ceiling)
    return (np.array([res["realized"].get(d, 0.0) for d in days]),
            np.array([ceiling[d] for d in days]))


def choose_knobs(rows: DeltaRows, idx_train: np.ndarray, ext: np.ndarray,
                 ceiling_train: dict[int, float]) -> tuple[float, float, float]:
    """(theta, q, m) on the TRAIN block only."""
    e = ext[idx_train]; e = e[np.isfinite(e)]
    best_q, best_theta, best_cap = None, None, -np.inf
    for q in Q_GRID:
        theta = float(np.quantile(e, q))
        r, c = _capture(rows, causal_walk(rows, idx_train, ext, theta=theta, runmax_margin=None), ceiling_train)
        cap = r.sum() / c.sum()
        if cap > best_cap:
            best_q, best_theta, best_cap = q, theta, cap
    best_m, best_cap_m = None, -np.inf
    for m in M_GRID:
        r, c = _capture(rows, causal_walk(rows, idx_train, ext, theta=-np.inf, runmax_margin=m), ceiling_train)
        cap = r.sum() / c.sum()
        if cap > best_cap_m:
            best_m, best_cap_m = m, cap
    return best_theta, best_q, best_m


def run(matrix_dir: Path, out_path: Path, *, blocks=BLOCKS, deltas=DELTAS,
        n_random: int = N_RANDOM, n_boot: int = N_BOOT, seed: int = 20260822, log=print) -> dict:
    rows = load_delta_rows(matrix_dir, deltas=deltas)
    ext, _ = extension_columns(rows)
    rows.x = np.empty((0, 0), np.float32)
    rng = np.random.default_rng(seed)
    report = {"schema": "QRE2EXTENSIONCAUSAL1", "prereg": __doc__.split("Selftest:")[0],
              "matrix_receipt": rows.matrix_receipt, "deltas_sec": list(deltas),
              "blocks": dict(blocks), "q_grid": list(Q_GRID), "m_grid": list(M_GRID),
              "n_random": n_random, "n_boot": n_boot, "assets": {}}
    tr_lo, tr_hi = blocks["train"]
    for a in sorted(set(rows.asset)):
        report["assets"][a] = {}
        for d in deltas:
            train_mask = (rows.asset == a) & (rows.day >= tr_lo) & (rows.day <= tr_hi)
            idx_tr = np.flatnonzero(train_mask & (rows.delta == d))
            theta, q, m = choose_knobs(rows, idx_tr, ext, _ceiling_by_day(rows, train_mask))
            for bname, (lo, hi) in blocks.items():
                block = (rows.asset == a) & (rows.day >= lo) & (rows.day <= hi)
                ceiling = _ceiling_by_day(rows, block)
                idx = np.flatnonzero(block & (rows.delta == d))
                if not len(idx):
                    raise ProbeRefusal(f"{a} {bname}: no rows at Delta={d}")
                entry = {"theta_usd": round(theta, 2), "q": q, "m_usd": m}
                rand = []
                for _ in range(n_random):
                    pick = _cell_pick(rng.random(len(idx)), rows.y[idx], rows.cell[idx], rows.day[idx],
                                      rows.elapsed[idx], rows.occupancy[idx], -np.inf)
                    r, c = _capture(rows, {"realized": pick["all"]}, ceiling); rand.append(float(r.sum() / c.sum()))
                null_top = float(np.percentile(rand, 97.5))
                entry["RANDOM"] = {"capture_mean": round(float(np.mean(rand)), 4), "capture_p97_5": round(null_top, 4)}
                pick = _cell_pick(np.nan_to_num(ext[idx], nan=-np.inf), rows.y[idx], rows.cell[idx], rows.day[idx],
                                  rows.elapsed[idx], rows.occupancy[idx], -np.inf)
                results = {"ORACLE": {"realized": pick["all"], "entered": None, "skipped": None, "seen_before_fire_mean": None},
                           "THETA": causal_walk(rows, idx, ext, theta=theta, runmax_margin=None),
                           "RUNMAX": causal_walk(rows, idx, ext, theta=-np.inf, runmax_margin=m)}
                for rule, res in results.items():
                    r, c = _capture(rows, res, ceiling); cap = float(r.sum() / c.sum())
                    boots = []
                    for _ in range(n_boot):
                        b = rng.integers(0, len(r), len(r)); boots.append(r[b].sum() / c[b].sum() if c[b].sum() > 0 else np.nan)
                    lo_ci = float(np.nanpercentile(boots, 2.5))
                    entry[rule] = {"capture": round(cap, 4),
                                   "capture_ci95": [round(lo_ci, 4), round(float(np.nanpercentile(boots, 97.5)), 4)],
                                   "usd_per_asset_day": round(float(r.mean()), 2),
                                   "clears_random_null": bool(lo_ci > null_top),
                                   "cells_entered": res["entered"], "cells_skipped": res["skipped"],
                                   "seen_before_fire_mean": res["seen_before_fire_mean"]}
                report["assets"][a].setdefault(bname, {})[str(int(d))] = entry
                log(f"{a} {bname} d{int(d)} theta=${theta:.0f}(q{q}) m=${m:.0f}: " + " ".join(
                    f"{k}={v['capture']:+.3f}{'*' if v['clears_random_null'] else ''}" for k, v in entry.items()
                    if k in ("ORACLE", "THETA", "RUNMAX")) + f" random={entry['RANDOM']['capture_mean']:+.3f}(p97.5 {null_top:+.3f})"
                    + f" entered/skipped={entry['THETA']['cells_entered']}/{entry['THETA']['cells_skipped']}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".json.partial")
    tmp.write_text(json.dumps(report, indent=1)); tmp.replace(out_path)
    return report


def selftest() -> int:
    blocks = {"train": (20210601, 20210606), "threshold": (20210607, 20210609), "forward": (20210610, 20210612)}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _synthetic(tmp / "sig", signal=True)
        rep = run(tmp / "sig", tmp / "sig.json", blocks=blocks, n_random=30, n_boot=30, log=lambda *_: None)
        e = rep["assets"]["HG"]["forward"]["0"]
        assert e["THETA"]["clears_random_null"], f"planted signal not recovered causally: {e}"
        assert e["ORACLE"]["capture"] >= e["THETA"]["capture"] - 1e-9, "oracle must bound the causal rule"
        _synthetic(tmp / "nosig", signal=False, seed=9)
        rep = run(tmp / "nosig", tmp / "nosig.json", blocks=blocks, n_random=30, n_boot=30, log=lambda *_: None)
        e2 = rep["assets"]["HG"]["forward"]["0"]
        assert not e2["THETA"]["clears_random_null"], f"no-signal fixture cleared the null: {e2}"
        _synthetic(tmp / "red", signal=True)
        x = np.load(tmp / "red" / "x.npy"); names = json.loads((tmp / "red" / "manifest.json").read_text())["feature_names"]
        x[:, names.index("disc_fvol_session_scope_elapsed_sec")] = np.nan; np.save(tmp / "red" / "x.npy", x)
        try:
            run(tmp / "red", tmp / "red.json", blocks=blocks, n_random=2, n_boot=2, log=lambda *_: None)
        except ProbeRefusal:
            pass
        else:
            raise AssertionError("red fixture (no decision-time ordering) was accepted")
    print(f"selftest OK: planted THETA capture {e['THETA']['capture']:.3f} (oracle {e['ORACLE']['capture']:.3f}) "
          f"clears null (p97.5 {e['RANDOM']['capture_p97_5']:.3f}); no-signal inside; red fixture refused")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("PREREGISTRATION")[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--matrix-dir", type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if not (args.matrix_dir and args.out):
        ap.error("--matrix-dir and --out are required (or --selftest)")
    run(args.matrix_dir, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
