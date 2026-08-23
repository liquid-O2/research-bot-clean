#!/usr/bin/env python3
"""Armed entry — ticket 34, and the ticket 29 bound that forces it.

TICKET 29 FINDING (why this probe exists). The ticket-28 hold enters at
7,380-10,980 s of name age, but the component matrix only labels ages 0-300 s
(`confirmation.training_offsets_seconds` refuses any expiry but 300 or 600).
The trade window is still open there (occupancy median 17,000-25,000 s, 94-100%
of picks), so the proxy's error is a pure entry-price drift, not a closed
position. Stage 1 measures that drift's SIGN and SLOPE on the picked names over
the only ages the data carries, and reports the linear extrapolation to the real
entry age as an explicit BOUND, never as a correction.

TICKET 34 RULE (Stage 2). If the wait cannot be priced, do not wait to enter.
Use the phase-scale hold as a GATE on when to look, not as a DELAY on when to
buy:

  1. Track the running phase extreme among eligible keep-first names, exactly
     as ticket 28 does.
  2. When that extreme has been unbeaten for H seconds, ARM the phase.
  3. Once armed, enter the FIRST name that becomes eligible afterwards, at its
     own DELTA_SEC of age.

Every entry is then at age DELTA_SEC, where y is the exact label. The economics
are honest by construction instead of by extrapolation. One entry per phase,
occupancy as `_cell_pick`, generator untouched, 2021 cannot promote.

PREREGISTRATION (written before the real run):
- Stage 1 letters `decay_negligible` when the extrapolated bound is under 10% of
  the arm's cash, `decay_material` otherwise. It is a bound, not a correction.
- Stage 2 H comes from TRAIN only, on the ticket-28 grid, under the same
  plateau rule (smallest H within one SE of the TRAIN peak; smallest H clearing
  the rung if any does). THRESHOLD is the verdict, FORWARD reported.
- Stage 2 null: shuffle which eligible name is the extreme within the cell,
  which destroys arming while keeping formation order and y.
- Rung letters carry the noise floor (RESOLVE_SE), so a margin inside the
  day-to-day spread letters *_not_resolved, never *_clears_rung.

Selftest: python3 tools/probe_armed_entry.py --selftest
Real:     OMP_NUM_THREADS=1 python3 tools/probe_armed_entry.py \
            --matrix-dir <component_matrix> --out <receipt.json>
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

import numpy as np

os.environ.setdefault("OMP_NUM_THREADS", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from probe_hold_running_extreme import (  # noqa: E402
    H_SEC, N_DRAW, PHASE_VWAP_COL, RESOLVE_SE, SHUFFLE_Q, _cash_flag, _cash_stats,
    _cell_groups, _choose_h, _entries_per_day, _hold_walk, _plant, _rung_letter,
    _stage_a,
)
from probe_location_family_screen import _col  # noqa: E402
from probe_path_dedup import PHASE_ELAPSED_COL, _formation_sec  # noqa: E402
from probe_path_dedup_live import DELTA_SEC, FORM_DELTA, SIDE_COL, VWAP_COL  # noqa: E402
from probe_rho_on_dedup import WIDTH_MULT, _keep_idx  # noqa: E402
from probe_rho_ruler import BLOCKS, PHASE_REMAINING_COL, RUNG_USD  # noqa: E402
from probe_trained_accrual import ELAPSED_COL, ProbeRefusal, load_delta_rows  # noqa: E402

SCHEMA = "QRE2ARMEDENTRY1"
AGE_GRID = (0.0, 30.0, 60.0, 90.0, 120.0, 180.0, 240.0, 300.0)
DECAY_MATERIAL_FRAC = 0.10
SCORE_COLS = (("session", VWAP_COL), ("phase", PHASE_VWAP_COL))


def armed_entry_flag(formed: np.ndarray, side: np.ndarray, vwap: np.ndarray,
                     cell: np.ndarray, h_sec: float, close: np.ndarray,
                     long_min: bool = True, short_min: bool = False) -> np.ndarray:
    """Arm on the held extreme, then enter the NEXT name to become eligible.

    The entered name is always at DELTA_SEC of age, which is the only age this
    matrix can price. The hold decides WHEN to look; it never delays the buy.
    """
    flag = np.full(len(formed), False)
    eligible = formed + DELTA_SEC
    for g in _cell_groups(cell):
        order = g[np.argsort(eligible[g], kind="stable")]
        long_i = short_i = -1
        long_t = short_t = np.inf
        long_v = np.inf if long_min else -np.inf
        short_v = np.inf if short_min else -np.inf
        armed_at = np.inf
        g_close = close[g][np.isfinite(close[g])]
        limit = float(np.max(g_close)) if len(g_close) else np.inf
        for i in order:
            t = float(eligible[i])
            if t >= armed_at - 1e-9:
                if t <= limit + 1e-9:        # the first arrival after arming
                    flag[int(i)] = True
                break
            v = float(vwap[i])
            if np.isfinite(v):
                if side[i] > 0:
                    beat = (v < long_v - 1e-12) if long_min else (v > long_v + 1e-12)
                    if long_i < 0 or beat:
                        long_i, long_v, long_t = int(i), v, t
                else:
                    beat = (v < short_v - 1e-12) if short_min else (v > short_v + 1e-12)
                    if short_i < 0 or beat:
                        short_i, short_v, short_t = int(i), v, t
            # Recomputed, never accumulated: a newer extreme RESTARTS the clock,
            # so the arm time moves later rather than sticking at the old value.
            fire_l = (long_t + h_sec) if long_i >= 0 else np.inf
            fire_s = (short_t + h_sec) if short_i >= 0 else np.inf
            armed_at = min(fire_l, fire_s)
    return flag


def age_decay_bound(series_of_pick: np.ndarray, ages: dict[float, dict[str, float]],
                    entered_age_sec: float, cash: float) -> dict:
    """Slope of y in entry age over the labelled grid, extrapolated as a BOUND.

    Linear extrapolation from a 300 s window to a 7,000 s entry is not a
    correction and is never reported as one. It answers one question: is the
    unpriced drift small enough to ignore, or large enough to decide the rule?
    """
    grid = sorted(ages)
    if len(grid) < 2:
        return {"letter": "decay_unmeasurable", "slope_usd_per_sec": None}
    lo, hi = grid[0], grid[-1]
    slope = (ages[hi]["mean"] - ages[lo]["mean"]) / (hi - lo)
    slope_p90 = (ages[hi]["p90"] - ages[lo]["p90"]) / (hi - lo)
    bound = slope * (entered_age_sec - DELTA_SEC)
    bound_p90 = slope_p90 * (entered_age_sec - DELTA_SEC)
    worst = min(bound, bound_p90)
    material = abs(worst) > DECAY_MATERIAL_FRAC * abs(cash) if cash else True
    return {
        "labelled_age_min_sec": lo, "labelled_age_max_sec": hi,
        "slope_usd_per_sec": slope, "slope_p90_usd_per_sec": slope_p90,
        "entered_age_sec": entered_age_sec,
        "extrapolated_bound_usd": bound, "extrapolated_bound_p90_usd": bound_p90,
        "cash_usd": cash,
        "letter": "decay_material" if material else "decay_negligible",
        "note": "linear extrapolation from a 300 s window; a BOUND, not a correction",
    }


def _pick_ages(rows_grid, series_ids: set[str], asset: str, lo: int, hi: int) -> dict:
    out: dict[float, dict[str, float]] = {}
    keep = ((rows_grid.asset == asset) & (rows_grid.day >= lo) & (rows_grid.day <= hi)
            & np.isin(rows_grid.series, list(series_ids)))
    for age in AGE_GRID:
        sel = keep & (rows_grid.delta == age)
        vals = rows_grid.y[sel]
        vals = vals[np.isfinite(vals)]
        if len(vals) < 20:
            continue
        out[age] = {"n": int(len(vals)), "mean": float(np.mean(vals)),
                    "p90": float(np.percentile(vals, 90))}
    return out


def run(matrix_dir: Path, out_path: Path, *, blocks=BLOCKS, n_draw: int = N_DRAW,
        h_grid=H_SEC, log=print) -> dict:
    rows180 = load_delta_rows(matrix_dir, deltas=(DELTA_SEC,))
    rows0 = load_delta_rows(matrix_dir, deltas=(FORM_DELTA,))
    rows_grid = load_delta_rows(matrix_dir, deltas=AGE_GRID)
    if not np.isfinite(rows180.y).all():
        raise ProbeRefusal(
            f"{int(np.sum(~np.isfinite(rows180.y)))} non-finite y; expected all finite USD")
    names = rows180.feature_names
    for _, col in SCORE_COLS:
        if col not in names:
            raise ProbeRefusal(f"missing={col} expected in feature_names source=manifest")
    rng = np.random.default_rng(20260823)
    report: dict = {"schema": SCHEMA, "prereg": __doc__,
                    "matrix_receipt": rows180.matrix_receipt,
                    "delta_sec": DELTA_SEC, "h_sec": list(h_grid), "n_draw": n_draw,
                    "resolve_se": RESOLVE_SE, "assets": {}}

    for asset in sorted(set(rows180.asset.tolist())):
        if asset not in WIDTH_MULT:
            continue
        rung = RUNG_USD[asset]
        entry: dict = {"rung_usd": rung, "stage1_age_decay": {}, "stage2_armed": {},
                       "orientation": None, "chosen_score": None}
        report["assets"][asset] = entry
        packed = {}
        for bname, (lo, hi) in blocks.items():
            idx = np.flatnonzero((rows180.asset == asset) & (rows180.day >= lo)
                                 & (rows180.day <= hi) & (rows180.delta == DELTA_SEC))
            if len(idx) == 0:
                continue
            kept = _keep_idx(rows180, rows0, idx, asset)
            pe_name = PHASE_ELAPSED_COL if PHASE_ELAPSED_COL in names else ELAPSED_COL
            packed[bname] = dict(
                y=rows180.y[kept], cell=rows180.cell[kept], day=rows180.day[kept],
                elapsed=rows180.elapsed[kept], occupancy=rows180.occupancy[kept],
                series=rows180.series[kept],
                side=rows180.x[kept, _col(names, SIDE_COL)].astype(np.float64),
                formed=_formation_sec(rows180.x[kept], names),
                close=(rows180.x[kept, _col(names, pe_name)].astype(np.float64)
                       + rows180.x[kept, _col(names, PHASE_REMAINING_COL)].astype(np.float64)),
                days=sorted({int(d) for d in rows180.day[kept]}),
                vw={tag: rows180.x[kept, _col(names, col)].astype(np.float64)
                    for tag, col in SCORE_COLS},
                span=(lo, hi))

        # Orientation and score column, chosen on TRAIN exactly as ticket 28.
        train = packed.get("train")
        if train is None:
            continue
        best = None
        for tag, _c in SCORE_COLS:
            blk = _stage_a(train["y"], train["side"], train["vw"][tag], train["cell"],
                           train["day"], train["elapsed"], train["occupancy"],
                           train["days"], rung, rng, n_draw)
            if best is None or blk["vwap_better_usd"] > best[1]["vwap_better_usd"]:
                best = (tag, blk)
        score_tag, a_blk = best
        entry["chosen_score"] = score_tag
        entry["orientation"] = a_blk["best_orientation"]
        long_min = a_blk["best_orientation"].startswith("long_min")
        short_min = a_blk["best_orientation"].endswith("short_min")

        # Stage 2 first: it produces the H that Stage 1 needs an entered age for.
        grid = []
        for h in h_grid:
            flag = armed_entry_flag(train["formed"], train["side"], train["vw"][score_tag],
                                    train["cell"], h, train["close"], long_min, short_min)
            stats = _cash_stats(flag, train["y"], train["cell"], train["day"],
                                train["elapsed"], train["occupancy"], train["days"])
            draws = []
            for _ in range(n_draw):
                shuf = train["vw"][score_tag].copy()
                for g in _cell_groups(train["cell"]):
                    shuf[g] = rng.permutation(shuf[g])
                nf = armed_entry_flag(train["formed"], train["side"], shuf, train["cell"],
                                      h, train["close"], long_min, short_min)
                draws.append(_cash_flag(nf, train["y"], train["cell"], train["day"],
                                        train["elapsed"], train["occupancy"], train["days"]))
            grid.append({"h_sec": h, **stats,
                         "null_mean_usd": float(np.mean(draws)),
                         "null_p975_usd": float(np.quantile(draws, SHUFFLE_Q)),
                         "clears_rung": bool(stats["usd_per_asset_day"] >= rung),
                         **_entries_per_day(flag, train["day"], train["days"])})
            log(f"{asset:4s} armed TRAIN H={h/60:5.0f}min ${stats['usd_per_asset_day']:7.0f} "
                f"se ${stats['usd_se']:5.0f} null975 ${np.quantile(draws, SHUFFLE_Q):6.0f}")
        chosen, rule = _choose_h(grid)
        h_star = chosen["h_sec"]
        entry["stage2_armed"] = {"train": {"grid": grid, "chosen_h_sec": h_star,
                                           "chosen_rule": rule,
                                           "letter": _rung_letter(chosen["usd_per_asset_day"],
                                                                  chosen["usd_se"], rung, "armed")},
                                 "chosen_h_sec": h_star}
        for bname, pack in packed.items():
            if bname == "train":
                continue
            flag = armed_entry_flag(pack["formed"], pack["side"], pack["vw"][score_tag],
                                    pack["cell"], h_star, pack["close"], long_min, short_min)
            stats = _cash_stats(flag, pack["y"], pack["cell"], pack["day"], pack["elapsed"],
                                pack["occupancy"], pack["days"])
            draws = []
            for _ in range(n_draw):
                shuf = pack["vw"][score_tag].copy()
                for g in _cell_groups(pack["cell"]):
                    shuf[g] = rng.permutation(shuf[g])
                nf = armed_entry_flag(pack["formed"], pack["side"], shuf, pack["cell"],
                                      h_star, pack["close"], long_min, short_min)
                draws.append(_cash_flag(nf, pack["y"], pack["cell"], pack["day"],
                                        pack["elapsed"], pack["occupancy"], pack["days"]))
            entry["stage2_armed"][bname] = {
                "h_sec": h_star, **stats,
                "null_mean_usd": float(np.mean(draws)),
                "null_p975_usd": float(np.quantile(draws, SHUFFLE_Q)),
                "letter": _rung_letter(stats["usd_per_asset_day"], stats["usd_se"],
                                       rung, "armed"),
                **_entries_per_day(flag, pack["day"], pack["days"])}
            log(f"{asset:4s} armed {bname:10s} H={h_star/60:.0f}min "
                f"${stats['usd_per_asset_day']:7.0f} se ${stats['usd_se']:5.0f} "
                f"{entry['stage2_armed'][bname]['letter']}")

        # Stage 1: the ticket-29 bound, on the ticket-28 hold's own picks.
        for bname, pack in packed.items():
            hold_flag, fired = _hold_walk(pack["formed"], pack["side"],
                                          pack["vw"][score_tag], pack["cell"], h_star,
                                          pack["close"], long_min, short_min)
            picked = np.flatnonzero(hold_flag)
            if not len(picked):
                continue
            entered = float(np.nanmedian(fired[picked] - pack["formed"][picked]))
            ages = _pick_ages(rows_grid, set(pack["series"][picked].tolist()), asset,
                              *pack["span"])
            cash = _cash_flag(hold_flag, pack["y"], pack["cell"], pack["day"],
                              pack["elapsed"], pack["occupancy"], pack["days"])
            entry["stage1_age_decay"][bname] = age_decay_bound(picked, ages, entered, cash)
            b = entry["stage1_age_decay"][bname]
            log(f"{asset:4s} decay {bname:10s} slope ${b.get('slope_usd_per_sec') or 0:.4f}/s "
                f"bound ${b.get('extrapolated_bound_usd') or 0:.0f} on ${cash:.0f} "
                f"{b['letter']}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=1, sort_keys=True))
    return report


def selftest() -> int:
    blocks = {"train": (20210610, 20210709)}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)

        # Armed entry must take the name that arrives AFTER the hold completes,
        # never the held extreme itself.
        theta = 1.0
        formed = np.array([0.0, 100.0, 5000.0])
        side = np.array([1.0, 1.0, 1.0])
        vwap = np.array([-8.0, -1.0, -1.0])     # index 0 is the extreme at t=180
        cell = np.array([1, 1, 1])
        close = np.full(3, 100000.0)
        got = armed_entry_flag(formed, side, vwap, cell, 300.0, close)
        assert got.tolist() == [False, False, True], got

        # A hold that never completes before the last arrival arms nothing.
        none = armed_entry_flag(formed, side, vwap, cell, 100000.0, close)
        assert not none.any(), none

        # Arming on the FIRST eligible name still requires a later arrival.
        two = armed_entry_flag(np.array([0.0, 600.0]), np.array([1.0, 1.0]),
                               np.array([-8.0, -1.0]), np.array([1, 1]), 300.0,
                               np.full(2, 100000.0))
        assert two.tolist() == [False, True], two

        # A newer extreme RESTARTS the clock. The extreme is beaten at t=280, so
        # arming moves from 480 to 580 and the t=500 arrival must NOT be taken.
        # An accumulating arm time would take it, which is the bug this catches.
        restart_formed = np.array([0.0, 100.0, 320.0])
        restart_vwap = np.array([-8.0, -9.0, -1.0])
        restart = armed_entry_flag(
            restart_formed, np.ones(3), restart_vwap, np.array([1, 1, 1]), 300.0,
            np.full(3, 100000.0))
        assert not restart.any(), restart
        # Positive control on the same shape: push the last arrival past 580 and
        # it IS taken, so the fixture above is not merely "nothing ever fires".
        taken = armed_entry_flag(
            np.array([0.0, 100.0, 420.0]), np.ones(3), restart_vwap,
            np.array([1, 1, 1]), 300.0, np.full(3, 100000.0))
        assert taken.tolist() == [False, False, True], taken

        # The entry must still land before the phase's scheduled close.
        late = armed_entry_flag(formed, side, vwap, cell, 300.0, np.full(3, 1000.0))
        assert not late.any(), late

        # The bound letters material when the extrapolation eats the cash.
        ages = {0.0: {"mean": 100.0, "p90": 900.0}, 300.0: {"mean": 90.0, "p90": 600.0}}
        mat = age_decay_bound(np.array([0]), ages, 7380.0, 1600.0)
        assert mat["letter"] == "decay_material", mat
        assert mat["extrapolated_bound_usd"] < -100.0, mat
        flat = age_decay_bound(np.array([0]), {0.0: {"mean": 100.0, "p90": 900.0},
                                               300.0: {"mean": 100.0, "p90": 900.0}},
                               7380.0, 1600.0)
        assert flat["letter"] == "decay_negligible", flat
        assert age_decay_bound(np.array([0]), {}, 7380.0, 1600.0)["letter"] == "decay_unmeasurable"

        _plant(tmp / "p")
        rep = run(tmp / "p", tmp / "p.json", blocks=blocks, h_grid=(300.0, 900.0),
                  log=lambda *_: None)
        hg = rep["assets"]["HG"]
        assert hg["stage2_armed"]["train"]["grid"], hg
        assert hg["orientation"].startswith("long_min"), hg
    print("selftest OK: armed entry takes the next eligible name after the hold, "
          "arms nothing when the hold never completes, decay bound letters "
          "material/negligible/unmeasurable")
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
