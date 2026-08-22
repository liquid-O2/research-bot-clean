#!/usr/bin/env python3
"""Re-test rule — the book's "second defense" as a decision-time rule (JOURNAL 2026-08-22
12:10Z anatomy: the phase extreme is set mid-phase and then HOLDS while later, less-extended
candidates form; 14-26% of oracle picks re-test an already-set extreme within $25).

PREREGISTRATION (written before the real run; echoed into the receipt):
- Rule RETEST(T, eps, q, Delta), per cell, in formation order, decision-time information only:
  track the running most-extended candidate (ext at formation; a more extended formation
  resets the running max and its clock). A candidate s QUALIFIES iff the running max is
  >= theta_q (TRAIN quantile), s forms >= T minutes after the running max was set, and
  ext(s) is within eps of the running max without exceeding it by more than eps. Enter the
  first qualifying candidate at age Delta (realized = its y at Delta). <=1 entry per cell,
  one position per asset.
- Knobs T in T_GRID (min), eps in EPS_GRID (usd), q in Q_GRID, Delta in D_GRID — one tuple
  per asset chosen on TRAIN only by train capture (64 combinations; the train optimum is
  optimistic by construction, the held blocks carry the verdict). Full tables reported.
- Nulls: RANDOM (cell-wide), FIRST_CANDIDATE (earliest-formed candidate of the cell at the
  same Delta — winners form early, so this is the structural baseline the rule must beat),
  FIRST_EXTENDED (first candidate >= theta_q). Reference: cell ORACLE. CLEARS iff the
  day-bootstrap 2.5th percentile exceeds all three nulls' 97.5th percentiles.
- Denominator: per (asset, day) sum over cells of the series-best value (matrix ceiling).
- Tier: DIAGNOSTIC (cell-pick dollars, not replay). A CLEARS on THRESHOLD and FORWARD is a
  causal decision-time signal; a failure closes "re-test of a held extreme" for the current
  plane at these grids.

Selftest: python3 tools/probe_retest_rule.py --selftest
Real:     python3 tools/probe_retest_rule.py --matrix-dir <round_0/component_matrix> --out <json>
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe_extension_prior import HIGH_COL, LOW_COL, SIDE_COL, extension_columns  # noqa: E402
from probe_patience_rule import DELTAS, Plane, _cap  # noqa: E402
from probe_trained_accrual import ELAPSED_COL, ProbeRefusal, _ceiling_by_day, _cell_pick, load_delta_rows  # noqa: E402

T_GRID = (2.0, 5.0, 10.0, 20.0)          # minutes since the running max was set
EPS_GRID = (25.0, 50.0, 100.0, 200.0)    # usd band around the running max
Q_GRID = (0.5, 0.8)
D_GRID = (60.0, 180.0)
BLOCKS = {"train": (20210610, 20210709), "threshold": (20210721, 20210806),
          "forward": (20210809, 20210826)}
N_RANDOM, N_BOOT = 100, 200


def _ordered(plane: Plane, series: np.ndarray) -> np.ndarray:
    return series[np.lexsort((plane.form_t[series], plane.cell[series], plane.day[series]))]


def rule_walk(plane: Plane, series: np.ndarray, *, mode: str, theta: float = -np.inf,
              T_min: float = 0.0, eps: float = np.inf, d: float = 60.0) -> dict:
    """mode: RETEST | FIRST_CANDIDATE | FIRST_EXTENDED. Returns per-day realized + counts."""
    realized: dict[int, float] = {}; entered = skipped = 0
    prev_day, prev_exit, cur_cell, done = None, -np.inf, None, False
    run_max, run_t = -np.inf, np.nan
    for s in _ordered(plane, series):
        day, c = int(plane.day[s]), int(plane.cell[s])
        if day != prev_day:
            prev_day, prev_exit = day, -np.inf; realized.setdefault(day, 0.0)
        if c != cur_cell:
            if cur_cell is not None and not done:
                skipped += 1
            cur_cell, done, run_max, run_t = c, False, -np.inf, np.nan
        if done:
            continue
        e, ft = plane.ext0[s], plane.form_t[s]
        if mode == "FIRST_CANDIDATE":
            qualifies = True
        elif mode == "FIRST_EXTENDED":
            qualifies = np.isfinite(e) and e >= theta
        else:  # RETEST: evaluate against the running max BEFORE this candidate updates it
            qualifies = (np.isfinite(e) and np.isfinite(run_max) and run_max >= theta
                         and ft >= run_t + 60.0 * T_min and e >= run_max - eps and e <= run_max + eps)
        if np.isfinite(e) and e > run_max:
            run_max, run_t = e, ft
        if not qualifies:
            continue
        t_dec, yv = plane.t[d][s], plane.y[d][s]
        if not np.isfinite(t_dec) or not np.isfinite(yv) or t_dec < prev_exit:
            continue
        realized[day] += float(yv); prev_exit = t_dec + float(plane.occ[s]); done = True; entered += 1
    if cur_cell is not None and not done:
        skipped += 1
    return {"realized": realized, "entered": entered, "skipped": skipped}


def run(matrix_dir: Path, out_path: Path, *, blocks=BLOCKS, t_grid=T_GRID, eps_grid=EPS_GRID,
        q_grid=Q_GRID, d_grid=D_GRID, n_random: int = N_RANDOM, n_boot: int = N_BOOT,
        seed: int = 20260822, log=print) -> dict:
    rows = load_delta_rows(matrix_dir, deltas=DELTAS)
    ext, _ = extension_columns(rows)
    plane = Plane(rows, ext)
    rng = np.random.default_rng(seed)
    report = {"schema": "QRE2RETEST1", "prereg": __doc__.split("Selftest:")[0],
              "matrix_receipt": rows.matrix_receipt, "t_grid_min": list(t_grid), "eps_grid_usd": list(eps_grid),
              "q_grid": list(q_grid), "d_grid_sec": list(d_grid), "blocks": dict(blocks),
              "n_random": n_random, "n_boot": n_boot, "assets": {}}
    tr_lo, tr_hi = blocks["train"]
    for a in sorted(set(rows.asset)):
        def block_series(lo, hi):
            return np.flatnonzero((plane.asset == a) & (plane.day >= lo) & (plane.day <= hi))
        s_tr = block_series(tr_lo, tr_hi)
        e_tr = plane.ext0[s_tr]; e_tr = e_tr[np.isfinite(e_tr)]
        thetas = {q: float(np.quantile(e_tr, q)) for q in q_grid}
        ceiling_tr = _ceiling_by_day(rows, (rows.asset == a) & (rows.day >= tr_lo) & (rows.day <= tr_hi))
        table = {}
        for T, eps, q, d in itertools.product(t_grid, eps_grid, q_grid, d_grid):
            r, c = _cap(rule_walk(plane, s_tr, mode="RETEST", theta=thetas[q], T_min=T, eps=eps, d=d), ceiling_tr)
            table[(T, eps, q, d)] = float(r.sum() / c.sum())
        T_s, eps_s, q_s, d_s = max(table, key=table.get)
        report["assets"][a] = {"T_star_min": T_s, "eps_star_usd": eps_s, "q_star": q_s, "delta_star": d_s,
                               "theta_star_usd": round(thetas[q_s], 2), "train_best_capture": round(table[(T_s, eps_s, q_s, d_s)], 4),
                               "blocks": {}}
        for bname, (lo, hi) in blocks.items():
            s_b = block_series(lo, hi)
            block_mask = (rows.asset == a) & (rows.day >= lo) & (rows.day <= hi)
            ceiling = _ceiling_by_day(rows, block_mask)
            idx0 = np.flatnonzero(block_mask & (rows.delta == 0.0))
            rand = []
            for _ in range(n_random):
                pick = _cell_pick(rng.random(len(idx0)), rows.y[idx0], rows.cell[idx0], rows.day[idx0],
                                  rows.elapsed[idx0], rows.occupancy[idx0], -np.inf)
                r, c = _cap({"realized": pick["all"]}, ceiling); rand.append(float(r.sum() / c.sum()))
            def boot(r, c):
                return [r[bb].sum() / c[bb].sum() for bb in (rng.integers(0, len(r), len(r)) for _ in range(n_boot))]
            res = rule_walk(plane, s_b, mode="RETEST", theta=thetas[q_s], T_min=T_s, eps=eps_s, d=d_s)
            r, c = _cap(res, ceiling); cap = float(r.sum() / c.sum()); bt = boot(r, c)
            r_fc, c_fc = _cap(rule_walk(plane, s_b, mode="FIRST_CANDIDATE", d=d_s), ceiling); bt_fc = boot(r_fc, c_fc)
            r_fe, c_fe = _cap(rule_walk(plane, s_b, mode="FIRST_EXTENDED", theta=thetas[q_s], d=d_s), ceiling); bt_fe = boot(r_fe, c_fe)
            pick = _cell_pick(np.nan_to_num(ext[idx0], nan=-np.inf), rows.y[idx0], rows.cell[idx0], rows.day[idx0],
                              rows.elapsed[idx0], rows.occupancy[idx0], -np.inf)
            r_o, c_o = _cap({"realized": pick["all"]}, ceiling)
            null_top = max(float(np.percentile(rand, 97.5)), float(np.nanpercentile(bt_fc, 97.5)), float(np.nanpercentile(bt_fe, 97.5)))
            lo_ci = float(np.nanpercentile(bt, 2.5))
            full = {}
            for T, eps, q, d in itertools.product(t_grid, eps_grid, q_grid, d_grid):
                rr, cc = _cap(rule_walk(plane, s_b, mode="RETEST", theta=thetas[q], T_min=T, eps=eps, d=d), ceiling)
                full[f"T{int(T)}_e{int(eps)}_q{q}_d{int(d)}"] = round(float(rr.sum() / cc.sum()), 4)
            report["assets"][a]["blocks"][bname] = {
                "n_days": len(ceiling), "ceiling_usd_per_asset_day": round(float(np.mean(list(ceiling.values()))), 2),
                "RETEST": {"capture": round(cap, 4), "capture_ci95": [round(lo_ci, 4), round(float(np.nanpercentile(bt, 97.5)), 4)],
                           "usd_per_asset_day": round(float(r.mean()), 2), "cells_entered": res["entered"],
                           "cells_skipped": res["skipped"], "clears_all_nulls": bool(lo_ci > null_top)},
                "FIRST_CANDIDATE": {"capture": round(float(r_fc.sum() / c_fc.sum()), 4), "capture_p97_5": round(float(np.nanpercentile(bt_fc, 97.5)), 4)},
                "FIRST_EXTENDED": {"capture": round(float(r_fe.sum() / c_fe.sum()), 4), "capture_p97_5": round(float(np.nanpercentile(bt_fe, 97.5)), 4)},
                "RANDOM": {"capture_mean": round(float(np.mean(rand)), 4), "capture_p97_5": round(float(np.percentile(rand, 97.5)), 4)},
                "ORACLE": {"capture": round(float(r_o.sum() / c_o.sum()), 4)}, "full_table": full}
            best_k = max(full, key=full.get)
            log(f"{a} {bname} T*={T_s:.0f}m eps*=${eps_s:.0f} q*={q_s} d*={d_s:.0f}: RETEST={cap:+.3f}{'*' if lo_ci > null_top else ''} "
                f"first_cand={r_fc.sum()/c_fc.sum():+.3f} first_ext={r_fe.sum()/c_fe.sum():+.3f} random={np.mean(rand):+.3f} "
                f"oracle={r_o.sum()/c_o.sum():+.3f} entered/skipped={res['entered']}/{res['skipped']} best-in-block={best_k}={full[best_k]:+.3f}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".json.partial"); tmp.write_text(json.dumps(report, indent=1)); tmp.replace(out_path)
    return report


# ----------------------------------------------------------------------------- selftest
def _synthetic(root: Path, *, signal: bool, seed: int = 5, n_days: int = 12, drop_side: bool = False) -> None:
    """Each cell: candidates 0-1 early (losers), #2 sets the extreme at t=100 s, #3-4 form below
    it (losers), #5 re-tests it within $10 at t=100+360 s (the winner), #6-7 later below it
    (losers). FIRST_CANDIDATE and FIRST_EXTENDED enter losers; RETEST(T<=6, eps>=25) wins."""
    rng = np.random.default_rng(seed)
    names = ["min_alert_age_sec", "phase_index", ELAPSED_COL, SIDE_COL, LOW_COL, HIGH_COL, "f0"]
    if drop_side:
        names.remove(SIDE_COL)
    plan = [(0.0, 100.0, False), (40.0, 200.0, False), (100.0, 500.0, False), (150.0, 300.0, False),
            (200.0, 350.0, False), (460.0, 492.0, True), (600.0, 200.0, False), (700.0, 250.0, False)]
    X, day, asset, series, y, occ = [], [], [], [], [], []
    sid = 0
    for d in range(1, n_days + 1):
        for phase in range(3):
            t0 = phase * 7200 + 600
            for (dt, ext, win) in plan:
                side = rng.choice([-1.0, 1.0])
                base = (800.0 if win else -300.0) if signal else rng.normal(0, 100)
                low_al = -ext if side > 0 else 500.0; high_al = -ext if side < 0 else 500.0
                for a in DELTAS:
                    row = [a, phase, t0 + dt + a] + ([side] if not drop_side else []) + [low_al, high_al, rng.normal()]
                    X.append(row); day.append(20210600 + d); asset.append("HG"); series.append(f"s{sid}")
                    y.append(base + rng.normal(0, 30)); occ.append(120.0)
                sid += 1
    root.mkdir(parents=True, exist_ok=True)
    np.save(root / "x.npy", np.asarray(X, np.float32)); np.save(root / "day.npy", np.asarray(day, np.int64))
    np.save(root / "asset.npy", np.asarray(asset)); np.save(root / "series_id.npy", np.asarray(series))
    np.save(root / "current_asinh.npy", np.arcsinh(np.asarray(y) / 600.0)); np.save(root / "occupancy_sec.npy", np.asarray(occ))
    (root / "manifest.json").write_text(json.dumps({"feature_names": names, "rows": len(X), "matrix_receipt_sha256": "synthetic"}))


def selftest() -> int:
    blocks = {"train": (20210601, 20210606), "threshold": (20210607, 20210609), "forward": (20210610, 20210612)}
    kw = dict(blocks=blocks, n_random=20, n_boot=20, log=lambda *_: None)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _synthetic(tmp / "sig", signal=True)
        rep = run(tmp / "sig", tmp / "sig.json", **kw)
        e = rep["assets"]["HG"]["blocks"]["forward"]
        assert e["RETEST"]["clears_all_nulls"], f"planted re-test structure not recovered: {e}"
        assert e["RETEST"]["capture"] > e["FIRST_CANDIDATE"]["capture"] + 0.3, f"re-test must beat first-candidate: {e}"
        _synthetic(tmp / "nosig", signal=False, seed=9)
        rep = run(tmp / "nosig", tmp / "nosig.json", **kw)
        e2 = rep["assets"]["HG"]["blocks"]["forward"]
        assert not e2["RETEST"]["clears_all_nulls"], f"no-signal fixture cleared: {e2}"
        _synthetic(tmp / "red", signal=True, drop_side=True)
        try:
            run(tmp / "red", tmp / "red.json", **kw)
        except ProbeRefusal:
            pass
        else:
            raise AssertionError("red fixture (no side column) was accepted")
    print(f"selftest OK: planted RETEST capture {e['RETEST']['capture']:.3f} (T*={rep['assets']['HG']['T_star_min']}m "
          f"eps*={rep['assets']['HG']['eps_star_usd']}) clears nulls; first-candidate {e['FIRST_CANDIDATE']['capture']:.3f}; "
          f"no-signal inside; red fixture refused")
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
