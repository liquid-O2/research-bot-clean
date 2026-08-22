#!/usr/bin/env python3
"""Patience rule — the time-based causal approximation of "the final extreme" (JOURNAL
2026-08-22 12:20Z: extension x confirmation was negative; the book's claim is that the
difference between a premature and a confirmed extreme "only exists in time").

PREREGISTRATION (written before the real run; echoed into the receipt):
- Rule PATIENCE(P, q), per cell, decided in time order from decision-time information only:
  track the running most-extended candidate (ext at formation, beyond the prior-session
  range on the fade side; ext >= theta_q from TRAIN quantiles). Enter that candidate at age
  P if, during its first P seconds, no MORE extended candidate has formed; a more extended
  formation restarts the clock on the new candidate. Realized = the entered candidate's
  standalone y at age P (its Delta=P row). <=1 entry per cell, one position per asset.
- Knobs P in P_GRID and q in Q_GRID chosen on TRAIN only by train capture (one pair per
  asset); applied unchanged to THRESHOLD and FORWARD. The full (P, q) table is reported
  for every block for transparency; only the train-chosen pair carries the verdict.
- Nulls: RANDOM (N_RANDOM cell-wide picks) and FIRST_EXTENDED (P=0: the first candidate
  clearing theta_q — the causal rule that failed). Reference: cell ORACLE (most extended of
  the phase, hindsight). CLEARS iff the day-bootstrap 2.5th percentile exceeds both nulls'
  97.5th percentiles on the block.
- Denominator: per (asset, day) sum over cells of the series-best value (matrix ceiling).
- Tier: DIAGNOSTIC (cell-pick dollars, not replay). A CLEARS on THRESHOLD and FORWARD is a
  causal decision-time signal; a failure closes "time-only patience on extension" for the
  300 s window (the watch cap bounds P).

Selftest: python3 tools/probe_patience_rule.py --selftest
Real:     python3 tools/probe_patience_rule.py --matrix-dir <round_0/component_matrix> --out <json>
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe_extension_prior import HIGH_COL, LOW_COL, SIDE_COL, extension_columns  # noqa: E402
from probe_trained_accrual import (  # noqa: E402
    ELAPSED_COL, DeltaRows, ProbeRefusal, _ceiling_by_day, _cell_pick, load_delta_rows,
)

DELTAS = (0.0, 60.0, 120.0, 180.0, 240.0, 290.0)
P_GRID = (60.0, 120.0, 180.0, 240.0, 290.0)
Q_GRID = (0.0, 0.5, 0.8)
BLOCKS = {"train": (20210610, 20210709), "threshold": (20210721, 20210806),
          "forward": (20210809, 20210826)}
N_RANDOM, N_BOOT = 100, 200


class Plane:
    """Per-series formation time, extension at formation, and y / decision time by Delta."""

    def __init__(self, rows: DeltaRows, ext: np.ndarray):
        n_series = int(rows.series.max()) + 1
        self.form_t = np.full(n_series, np.nan); self.ext0 = np.full(n_series, np.nan)
        self.y = {d: np.full(n_series, np.nan) for d in DELTAS}
        self.t = {d: np.full(n_series, np.nan) for d in DELTAS}
        self.occ = np.full(n_series, np.nan)
        self.cell = np.full(n_series, -1, np.int64); self.day = np.full(n_series, -1, np.int64)
        self.asset = np.full(n_series, "", dtype=object)
        for d in DELTAS:
            m = rows.delta == d; s = rows.series[m]
            self.y[d][s] = rows.y[m]; self.t[d][s] = rows.elapsed[m]
            if d == 0.0:
                self.form_t[s] = rows.elapsed[m]; self.ext0[s] = ext[m]; self.occ[s] = rows.occupancy[m]
                self.cell[s] = rows.cell[m]; self.day[s] = rows.day[m]; self.asset[s] = rows.asset[m]
        if not np.all(np.isfinite(self.form_t[self.cell >= 0])):
            raise ProbeRefusal("patience walk needs a finite formation time for every series")


def patience_walk(plane: Plane, series: np.ndarray, *, P: float, theta: float) -> dict:
    """Decision-time walk over the series of one asset-block. Returns per-day realized."""
    order = series[np.lexsort((plane.form_t[series], plane.cell[series], plane.day[series]))]
    realized: dict[int, float] = {}; entered = skipped = 0
    prev_day, prev_exit, cur_cell = None, -np.inf, None
    pending = None   # running-max candidate awaiting its P seconds
    def settle(cand):
        nonlocal prev_exit, entered
        if cand is None:
            return False
        t_dec = plane.t[P][cand]
        yv = plane.y[P][cand]
        if not np.isfinite(t_dec) or not np.isfinite(yv) or t_dec < prev_exit:
            return False
        realized[int(plane.day[cand])] = realized.get(int(plane.day[cand]), 0.0) + float(yv)
        prev_exit = t_dec + float(plane.occ[cand]); entered += 1
        return True
    for s in order:
        d, c = int(plane.day[s]), int(plane.cell[s])
        if d != prev_day:
            prev_day, prev_exit = d, -np.inf; realized.setdefault(d, 0.0)
        if c != cur_cell:
            if cur_cell is not None:
                fired = settle(pending) if pending is not None and not cell_done else False
                if not cell_done and not fired:
                    skipped += 1
            cur_cell, cell_done, pending, run_max = c, False, None, -np.inf
        if cell_done:
            continue
        e = plane.ext0[s]
        # a pending candidate whose P seconds elapsed before this formation fires first
        if pending is not None and plane.form_t[s] >= plane.form_t[pending] + P:
            if settle(pending):
                cell_done = True; pending = None; continue
            pending = None
        if np.isfinite(e) and e >= theta and e > run_max:
            run_max = e; pending = s
    if cur_cell is not None and not cell_done:
        if not (pending is not None and settle(pending)):
            skipped += 1
    return {"realized": realized, "entered": entered, "skipped": skipped}


def first_extended_walk(plane: Plane, series: np.ndarray, *, theta: float, d: float) -> dict:
    order = series[np.lexsort((plane.form_t[series], plane.cell[series], plane.day[series]))]
    realized: dict[int, float] = {}; prev_day, prev_exit, cur_cell, done = None, -np.inf, None, False
    for s in order:
        day, c = int(plane.day[s]), int(plane.cell[s])
        if day != prev_day:
            prev_day, prev_exit = day, -np.inf; realized.setdefault(day, 0.0)
        if c != cur_cell:
            cur_cell, done = c, False
        if done or not (np.isfinite(plane.ext0[s]) and plane.ext0[s] >= theta):
            continue
        t_dec, yv = plane.t[d][s], plane.y[d][s]
        if not np.isfinite(t_dec) or not np.isfinite(yv) or t_dec < prev_exit:
            continue
        realized[day] += float(yv); prev_exit = t_dec + float(plane.occ[s]); done = True
    return {"realized": realized}


def _cap(res: dict, ceiling: dict[int, float]) -> tuple[np.ndarray, np.ndarray]:
    days = sorted(ceiling)
    return (np.array([res["realized"].get(k, 0.0) for k in days]), np.array([ceiling[k] for k in days]))


def run(matrix_dir: Path, out_path: Path, *, blocks=BLOCKS, p_grid=P_GRID, q_grid=Q_GRID,
        n_random: int = N_RANDOM, n_boot: int = N_BOOT, seed: int = 20260822, log=print) -> dict:
    rows = load_delta_rows(matrix_dir, deltas=DELTAS)
    ext, _ = extension_columns(rows)
    plane = Plane(rows, ext)
    rng = np.random.default_rng(seed)
    report = {"schema": "QRE2PATIENCE1", "prereg": __doc__.split("Selftest:")[0],
              "matrix_receipt": rows.matrix_receipt, "p_grid": list(p_grid), "q_grid": list(q_grid),
              "blocks": dict(blocks), "n_random": n_random, "n_boot": n_boot, "assets": {}}
    tr_lo, tr_hi = blocks["train"]
    for a in sorted(set(rows.asset)):
        def block_series(lo, hi):
            return np.flatnonzero((plane.asset == a) & (plane.day >= lo) & (plane.day <= hi))
        s_tr = block_series(tr_lo, tr_hi)
        e_tr = plane.ext0[s_tr]; e_tr = e_tr[np.isfinite(e_tr)]
        thetas = {q: float(np.quantile(e_tr, q)) for q in q_grid}
        ceiling_tr = _ceiling_by_day(rows, (rows.asset == a) & (rows.day >= tr_lo) & (rows.day <= tr_hi))
        table_tr = {}
        for P in p_grid:
            for q in q_grid:
                r, c = _cap(patience_walk(plane, s_tr, P=P, theta=thetas[q]), ceiling_tr)
                table_tr[(P, q)] = float(r.sum() / c.sum())
        (P_star, q_star) = max(table_tr, key=table_tr.get)
        report["assets"][a] = {"P_star": P_star, "q_star": q_star, "theta_star_usd": round(thetas[q_star], 2),
                               "train_table": {f"P{int(P)}_q{q}": round(v, 4) for (P, q), v in table_tr.items()},
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
            r_fe, c_fe = _cap(first_extended_walk(plane, s_b, theta=thetas[q_star], d=0.0), ceiling)
            boots_fe = [r_fe[bb].sum() / c_fe[bb].sum() for bb in (rng.integers(0, len(r_fe), len(r_fe)) for _ in range(n_boot))]
            res = patience_walk(plane, s_b, P=P_star, theta=thetas[q_star])
            r, c = _cap(res, ceiling); cap = float(r.sum() / c.sum())
            boots = [r[bb].sum() / c[bb].sum() for bb in (rng.integers(0, len(r), len(r)) for _ in range(n_boot))]
            pick = _cell_pick(np.nan_to_num(ext[idx0], nan=-np.inf), rows.y[idx0], rows.cell[idx0], rows.day[idx0],
                              rows.elapsed[idx0], rows.occupancy[idx0], -np.inf)
            r_o, c_o = _cap({"realized": pick["all"]}, ceiling)
            null_top = max(float(np.percentile(rand, 97.5)), float(np.nanpercentile(boots_fe, 97.5)))
            lo_ci = float(np.nanpercentile(boots, 2.5))
            full = {f"P{int(P)}_q{q}": round(float((lambda rc: rc[0].sum() / rc[1].sum())(
                _cap(patience_walk(plane, s_b, P=P, theta=thetas[q]), ceiling))), 4) for P in p_grid for q in q_grid}
            report["assets"][a]["blocks"][bname] = {
                "n_days": len(ceiling), "ceiling_usd_per_asset_day": round(float(np.mean(list(ceiling.values()))), 2),
                "PATIENCE": {"capture": round(cap, 4), "capture_ci95": [round(lo_ci, 4), round(float(np.nanpercentile(boots, 97.5)), 4)],
                             "usd_per_asset_day": round(float(r.mean()), 2), "cells_entered": res["entered"],
                             "cells_skipped": res["skipped"], "clears_both_nulls": bool(lo_ci > null_top)},
                "FIRST_EXTENDED": {"capture": round(float(r_fe.sum() / c_fe.sum()), 4), "capture_p97_5": round(float(np.nanpercentile(boots_fe, 97.5)), 4)},
                "RANDOM": {"capture_mean": round(float(np.mean(rand)), 4), "capture_p97_5": round(float(np.percentile(rand, 97.5)), 4)},
                "ORACLE": {"capture": round(float(r_o.sum() / c_o.sum()), 4)},
                "full_table": full}
            log(f"{a} {bname} P*={int(P_star)} q*={q_star} theta=${thetas[q_star]:.0f}: PATIENCE={cap:+.3f}"
                f"{'*' if lo_ci > null_top else ''} first_ext={r_fe.sum()/c_fe.sum():+.3f} random={np.mean(rand):+.3f} "
                f"oracle={r_o.sum()/c_o.sum():+.3f} entered/skipped={res['entered']}/{res['skipped']} best-in-block={max(full, key=full.get)}={max(full.values()):+.3f}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".json.partial"); tmp.write_text(json.dumps(report, indent=1)); tmp.replace(out_path)
    return report


# ----------------------------------------------------------------------------- selftest
def _synthetic(root: Path, *, signal: bool, seed: int = 5, n_days: int = 12, n_cand: int = 6,
               drop_side: bool = False) -> None:
    """Each cell: candidates form in order with INCREASING extension; the last one is the final
    extreme (wins), earlier ones are premature (lose). Formation gaps (50 s) are shorter than
    every P, so only patience — restarting its clock on each more-extended formation — reaches
    the last one; first-extended enters a premature one."""
    rng = np.random.default_rng(seed)
    names = ["min_alert_age_sec", "phase_index", ELAPSED_COL, SIDE_COL, LOW_COL, HIGH_COL, "f0"]
    if drop_side:
        names.remove(SIDE_COL)
    X, day, asset, series, y, occ = [], [], [], [], [], []
    sid = 0
    for d in range(1, n_days + 1):
        for phase in range(3):
            t0 = phase * 7200 + 600
            for k in range(n_cand):
                side = rng.choice([-1.0, 1.0]); ext = 100.0 * (k + 1)   # strictly increasing
                final = (k == n_cand - 1)
                base = (800.0 if final else -300.0) if signal else rng.normal(0, 100)
                # 50 s between formations: shorter than every P, so patience must restart
                # its clock through the sequence; first-extended enters a premature one.
                form = t0 + 50.0 * k
                low_al = -ext if side > 0 else 500.0; high_al = -ext if side < 0 else 500.0
                for a in DELTAS:
                    row = [a, phase, form + a] + ([side] if not drop_side else []) + [low_al, high_al, rng.normal()]
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
        assert e["PATIENCE"]["clears_both_nulls"], f"planted final-extreme structure not recovered: {e}"
        assert e["PATIENCE"]["capture"] > e["FIRST_EXTENDED"]["capture"] + 0.3, f"patience must beat first-extended: {e}"
        _synthetic(tmp / "nosig", signal=False, seed=9)
        rep = run(tmp / "nosig", tmp / "nosig.json", **kw)
        e2 = rep["assets"]["HG"]["blocks"]["forward"]
        assert not e2["PATIENCE"]["clears_both_nulls"], f"no-signal fixture cleared: {e2}"
        _synthetic(tmp / "red", signal=True, drop_side=True)
        try:
            run(tmp / "red", tmp / "red.json", **kw)
        except ProbeRefusal:
            pass
        else:
            raise AssertionError("red fixture (no side column) was accepted")
    print(f"selftest OK: planted PATIENCE capture {e['PATIENCE']['capture']:.3f} (P*={rep['assets']['HG']['P_star']}) "
          f"clears nulls, first-extended {e['FIRST_EXTENDED']['capture']:.3f}; no-signal inside; red fixture refused")
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
