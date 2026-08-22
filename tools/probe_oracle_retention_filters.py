#!/usr/bin/env python3
"""Oracle-retention filters — ticket 12 of design/entry_reset (2026-08-22).

PREREGISTRATION (written before the real run; echoed into the receipt):
- Question: which on-matrix FILTER keeps the remaining-pool oracle close
  to the unfiltered cell-max while actually cutting names? Ticket 11 ranked
  by shrink alone and picked session LVN, a fat net.
- Majority kept: retained_fraction >= 0.70 (TRAIN). Proper cut:
  median_eligible_per_cell <= 16 and frac_cells_everybody < 0.50.
  Survivors ranked by TRAIN shrink vs the per-asset rung. FORWARD of a
  TRAIN survivor is reported, never used to pick the filter.
- Occupancy vs 200-draw within-cell shuffle of the flag. A y-independent
  flag sits inside the band.
- Leftover anatomy: cell-oracle pick at none of the finished set
  (pdh_pdl, prior_vah_val, prior_lvn, ib_session). Nearest extra aligned
  column among leftovers. When the pick is not at the filter, remaining
  max / cell max.
- UNION of the finished set is one labeled row, not a stacked null.
- Live ticket-11 families stay live: ib_high_low, session_vwap, session_lvn.
- 2021 cannot promote. Gaps untested: pwh_pwl, onh_onl, vwap sigma,
  ledges, G1 delta-by-price, G10 CVD.
- Kill: TRAIN retained < 0.70 AND occupancy inside shuffle, per filter.

Selftest: python3 tools/probe_oracle_retention_filters.py --selftest
Real:     OMP_NUM_THREADS=1 python3 tools/probe_oracle_retention_filters.py \\
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
from probe_location_family_screen import (  # noqa: E402
    CONTROLS, DELTA_SEC, EXPLORATORY_FAMILIES, FAMILIES, THETA_TICKS, TICK_USD,
    _col, _occupancy, _shrink_ceiling, at_family_mask,
)
from probe_rho_ruler import BLOCKS, RUNG_USD, _cell_groups, _ceiling_180_by_day  # noqa: E402
from probe_trained_accrual import (  # noqa: E402
    ELAPSED_COL, ProbeRefusal, _synthetic_matrix, load_delta_rows,
)

SCHEMA = "QRE2ORCRET1"
N_DRAW = 200
MAJORITY = 0.70
MAX_NAMES = 16.0
FINISHED = ("pdh_pdl", "prior_vah_val", "prior_lvn", "ib_session")
LIVE = ("ib_high_low", "session_vwap", "session_lvn", "session_vah_val")
EXTRA_ALIGNED = {
    "prior_hvn": ("disc_prior_hvn_aligned_usd",),
    "session_hvn": ("disc_auction_session_nearest_hvn_aligned_usd",),
    "session_tpo_poc": ("disc_auction_session_tpo_poc_aligned_usd",),
}
GAPS = (
    "pwh_pwl", "onh_onl", "vwap_pm_2_sigma", "vwap_pm_2_5_sigma",
    "ledges_shelves", "g1_delta_by_price", "g10_session_cvd",
)
AGE_COL = "min_alert_age_sec"
REMAIN_COL = "phase_remaining_sec"
PHASE_ELAPSED_COL = "disc_fvol_phase_scope_elapsed_sec"
INSIDE_COL = "disc_prior_inside_value"
COMPLETE_COL = "disc_ib_phase_complete"


def _all_location_cols() -> dict[str, tuple[str, ...]]:
    out = dict(FAMILIES)
    out.update(EXPLORATORY_FAMILIES)
    out.update(EXTRA_ALIGNED)
    return out


def _theta(asset: str, width: str) -> float:
    return THETA_TICKS[asset][width] * TICK_USD[asset]


def _mask_first_third(x: np.ndarray, names: list[str]) -> np.ndarray:
    # Phase clock, not session. Session elapsed zeros later phases (ticket 12).
    age = x[:, _col(names, AGE_COL)].astype(np.float64)
    remain = x[:, _col(names, REMAIN_COL)].astype(np.float64)
    elapsed = x[:, _col(names, PHASE_ELAPSED_COL)].astype(np.float64)
    formed = elapsed - age
    phase_len = elapsed + remain
    ok = np.isfinite(formed) & np.isfinite(phase_len) & (phase_len > 0)
    out = np.zeros(len(x), bool)
    out[ok] = formed[ok] <= (phase_len[ok] / 3.0)
    return out


def _filter_mask(rows, idx: np.ndarray, name: str, cols: tuple[str, ...] | None,
                 theta: float, kind: str) -> np.ndarray:
    x = rows.x[idx]
    names = rows.feature_names
    if kind == "aligned":
        return at_family_mask(x, names, cols, theta)
    if kind == "outside_value":
        return x[:, _col(names, INSIDE_COL)] <= 0.0
    if kind == "first_third":
        return _mask_first_third(x, names)
    if kind == "ib_complete_at":
        at = at_family_mask(x, names, cols, theta)
        return at & (x[:, _col(names, COMPLETE_COL)] > 0.5)
    if kind == "union":
        acc = np.zeros(len(idx), bool)
        for cset in cols:
            acc |= at_family_mask(x, names, cset, theta)
        return acc
    raise ProbeRefusal(f"unknown filter kind {kind!r}")


def _score_mask(rows, idx: np.ndarray, flag: np.ndarray, *,
                n_draw: int, seed: int) -> dict:
    y, cell, day = rows.y[idx], rows.cell[idx], rows.day[idx]
    occ = _occupancy(flag, y, cell, n_draw=n_draw, rng=np.random.default_rng(seed))
    shrink = _shrink_ceiling(flag, y, cell, day)
    groups = _cell_groups(cell)
    unf = _ceiling_180_by_day(y, day, groups)
    days = sorted({int(d) for d in day})
    unfiltered = float(sum(unf.values()) / len(days)) if days else float("nan")
    # When the cell-oracle pick is not in the filter, remaining-max / cell-max.
    ratios = []
    for g in groups:
        pick = g[int(np.argmax(y[g]))]
        cell_max = float(y[pick])
        if cell_max <= 0:
            continue
        if flag[pick]:
            ratios.append(1.0)
            continue
        hit = g[flag[g]]
        ratios.append(float(y[hit].max()) / cell_max if len(hit) else 0.0)
    typed = []
    if occ["frac_cells_nobody"] > 0.90:
        typed.append("GATE-DEFECT selects nobody on >90% of cells")
    if occ["frac_cells_everybody"] > 0.90:
        typed.append("GATE-DEFECT selects everybody on >90% of cells")
    ncell = occ["median_eligible_per_cell"]
    ret = float(shrink / unfiltered) if unfiltered else float("nan")
    if ncell > MAX_NAMES and occ["frac_cells_everybody"] < 0.90:
        typed.append("fat-net median names > 16")
    return {
        "shrink_ceiling_usd_per_asset_day": shrink,
        "unfiltered_ceiling_usd_per_asset_day": unfiltered,
        "retained_fraction": ret,
        "majority_kept": bool(ret >= MAJORITY) if np.isfinite(ret) else False,
        "proper_cut": bool(ncell <= MAX_NAMES and occ["frac_cells_everybody"] < 0.50),
        "runner_up_keep_median": float(np.median(ratios)) if ratios else float("nan"),
        "occupancy": occ,
        "typed": typed,
        "n_rows": int(len(idx)),
        "n_days": int(len(days)),
    }


def _leftover(rows, idx: np.ndarray, finished_flags: dict[str, np.ndarray],
              extra_cols: dict[str, tuple[str, ...]], theta: float) -> dict:
    y, cell = rows.y[idx], rows.cell[idx]
    x = rows.x[idx]
    names = rows.feature_names
    groups = _cell_groups(cell)
    picks = np.array([int(g[int(np.argmax(y[g]))]) for g in groups], np.int64)
    at_any = np.zeros(len(idx), bool)
    at_counts = {fam: 0 for fam in finished_flags}
    for fam, fl in finished_flags.items():
        at_counts[fam] = int(fl[picks].sum())
        at_any |= fl
    leftover = picks[~at_any[picks]]
    nearest: dict[str, int] = {}
    if len(leftover):
        dist_names = []
        dist_stack = []
        for fam, cols in extra_cols.items():
            d = np.min(np.stack([np.abs(x[:, _col(names, c)]) for c in cols], axis=1), axis=1)
            dist_names.append(fam)
            dist_stack.append(d)
        D = np.stack(dist_stack, axis=1)
        arg = np.argmin(D[leftover], axis=1)
        for i in arg:
            nearest[dist_names[int(i)]] = nearest.get(dist_names[int(i)], 0) + 1
        at_extra = (D[leftover] <= theta).any(axis=1)
        extra_hit = float(at_extra.mean())
    else:
        extra_hit = float("nan")
    return {
        "n_picks": int(len(picks)),
        "n_leftover": int(len(leftover)),
        "leftover_frac": float(len(leftover) / len(picks)) if len(picks) else float("nan"),
        "picks_at_finished": {k: v / len(picks) for k, v in at_counts.items()} if len(picks) else {},
        "leftover_nearest_extra": nearest,
        "leftover_at_any_extra_theta": extra_hit,
    }


def _filter_catalog() -> list[tuple[str, str, tuple | None, str]]:
    # name, kind, cols, live_or_finished_or_extra
    rows = []
    loc = _all_location_cols()
    for fam in FINISHED:
        rows.append((fam, "aligned", loc[fam], "finished"))
    for fam in LIVE:
        rows.append((fam, "aligned", loc[fam], "live"))
    for fam, cols in EXTRA_ALIGNED.items():
        rows.append((fam, "aligned", cols, "extra"))
    rows.append(("outside_prior_value", "outside_value", None, "nonloc"))
    rows.append(("first_third_phase_clock", "first_third", None, "nonloc"))
    rows.append(("ib_phase_complete_and_at", "ib_complete_at",
                 loc["ib_high_low"], "nonloc"))
    union_cols = tuple(loc[f] for f in FINISHED)
    rows.append(("finished_union", "union", union_cols, "union"))
    return rows


def run(matrix_dir: Path, out_path: Path, *, blocks=BLOCKS, n_draw: int = N_DRAW,
        log=print) -> dict:
    rows = load_delta_rows(matrix_dir, deltas=(DELTA_SEC,))
    if not np.isfinite(rows.y).all():
        raise ProbeRefusal(
            f"{int(np.sum(~np.isfinite(rows.y)))} non-finite y; expected all finite USD")
    loc = _all_location_cols()
    for cols in loc.values():
        for c in cols:
            _col(rows.feature_names, c)
    for c in (AGE_COL, REMAIN_COL, PHASE_ELAPSED_COL, INSIDE_COL, COMPLETE_COL):
        _col(rows.feature_names, c)
    all_days = (int(rows.day.min()), int(rows.day.max()))
    catalog = _filter_catalog()
    report: dict = {
        "schema": SCHEMA, "prereg": __doc__, "matrix_receipt": rows.matrix_receipt,
        "delta_sec": DELTA_SEC, "n_draw": n_draw, "majority": MAJORITY,
        "max_names": MAX_NAMES, "finished": list(FINISHED), "gaps_untested": list(GAPS),
        "controls": sorted(CONTROLS),
        "blocks": {**{k: list(v) for k, v in blocks.items()}, "all": list(all_days)},
        "assets": {},
    }
    for asset in sorted(set(rows.asset.tolist())):
        report["assets"][asset] = {"rung_usd": RUNG_USD[asset], "filters": {},
                                   "leftover": {}, "survivors_tight": []}
        for width in ("tight", "wide"):
            theta = _theta(asset, width)
            report["assets"][asset]["leftover"][width] = {}
            for bname, (lo, hi) in {**blocks, "all": all_days}.items():
                idx = np.flatnonzero(
                    (rows.asset == asset) & (rows.day >= lo) & (rows.day <= hi)
                    & (rows.delta == DELTA_SEC))
                if len(idx) == 0:
                    continue
                finished_flags = {
                    fam: at_family_mask(rows.x[idx], rows.feature_names, loc[fam], theta)
                    for fam in FINISHED
                }
                report["assets"][asset]["leftover"][width][bname] = _leftover(
                    rows, idx, finished_flags, EXTRA_ALIGNED, theta)
            for fname, kind, cols, tag in catalog:
                report["assets"][asset]["filters"].setdefault(fname, {"tag": tag})
                report["assets"][asset]["filters"][fname][width] = {}
                for bname, (lo, hi) in {**blocks, "all": all_days}.items():
                    idx = np.flatnonzero(
                        (rows.asset == asset) & (rows.day >= lo) & (rows.day <= hi)
                        & (rows.delta == DELTA_SEC))
                    if len(idx) == 0:
                        continue
                    flag = _filter_mask(rows, idx, fname, cols, theta, kind)
                    block = _score_mask(rows, idx, flag, n_draw=n_draw, seed=0)
                    report["assets"][asset]["filters"][fname][width][bname] = block
                    log(f"{asset:4s} {fname:28s} {width:5s} {bname:10s} "
                        f"shrink={block['shrink_ceiling_usd_per_asset_day']:7.1f} "
                        f"ret={block['retained_fraction']:.2f} "
                        f"ncell={block['occupancy']['median_eligible_per_cell']:.1f} "
                        f"maj={int(block['majority_kept'])} cut={int(block['proper_cut'])}"
                        f"{'' if not block['typed'] else ' TYPED'}")
        ranked = []
        for fname, spec in report["assets"][asset]["filters"].items():
            tr = spec.get("tight", {}).get("train")
            if tr is None:
                continue
            if tr["majority_kept"] and tr["proper_cut"]:
                ranked.append((tr["shrink_ceiling_usd_per_asset_day"], fname))
        ranked.sort(reverse=True)
        report["assets"][asset]["survivors_tight"] = [
            {"filter": f, "shrink_ceiling": s} for s, f in ranked]
        report["assets"][asset]["letter"] = (
            ranked[0][1] if ranked else "no majority-and-cut filter")
        best = ranked[0][1] if ranked else None
        if best is not None:
            report["assets"][asset]["train_best_forward"] = (
                report["assets"][asset]["filters"][best].get("tight", {}).get("forward"))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=1, sort_keys=True))
    return report


def _append_extra(root: Path, *, plant: str | None) -> None:
    x = np.load(root / "x.npy")
    man = json.loads((root / "manifest.json").read_text())
    y = np.sinh(np.load(root / "current_asinh.npy")) * 600.0
    needed = []
    for cols in _all_location_cols().values():
        for c in cols:
            if c not in needed:
                needed.append(c)
    for c in (REMAIN_COL, PHASE_ELAPSED_COL, INSIDE_COL, COMPLETE_COL):
        if c not in needed:
            needed.append(c)
    extra = np.full((len(x), len(needed)), 500.0, np.float32)
    extra[:, needed.index(INSIDE_COL)] = 1.0
    extra[:, needed.index(COMPLETE_COL)] = 0.0
    extra[:, needed.index(REMAIN_COL)] = 4000.0
    if ELAPSED_COL in man["feature_names"]:
        extra[:, needed.index(PHASE_ELAPSED_COL)] = x[:, man["feature_names"].index(ELAPSED_COL)]
    else:
        extra[:, needed.index(PHASE_ELAPSED_COL)] = 2000.0
    age = x[:, man["feature_names"].index("min_alert_age_sec")]
    if plant:
        day = np.load(root / "day.npy")
        series = np.asarray(np.load(root / "series_id.npy"), str)
        phase = x[:, man["feature_names"].index("phase_index")]
        at_delta = np.abs(age - DELTA_SEC) <= 2.5
        cell = day.astype(np.int64) * 10 + np.nan_to_num(phase, nan=9).astype(np.int64)
        order = np.argsort(cell, kind="stable")
        keep = order[at_delta[order]]
        bounds = np.flatnonzero(np.diff(cell[keep])) + 1
        col_i = needed.index(plant)
        for grp in np.split(keep, bounds):
            if len(grp) == 0:
                continue
            win = grp[int(np.argmax(y[grp]))]
            extra[series == series[win], col_i] = 0.0
            if plant in ("disc_prior_high_aligned_usd", "disc_prior_low_aligned_usd"):
                extra[series == series[win], needed.index("disc_prior_high_aligned_usd")] = 0.0
                extra[series == series[win], needed.index("disc_prior_low_aligned_usd")] = 0.0
    x = np.concatenate([x, extra], axis=1)
    man["feature_names"].extend(needed)
    np.save(root / "x.npy", x)
    (root / "manifest.json").write_text(json.dumps(man))


def selftest() -> int:
    blocks = {"train": (20210601, 20210624), "forward": (20210601, 20210624)}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _synthetic_matrix(tmp / "planted", signal=True)
        _append_extra(tmp / "planted", plant="disc_prior_hvn_aligned_usd")
        rep = run(tmp / "planted", tmp / "planted.json", blocks=blocks, n_draw=40,
                  log=lambda *_: None)
        hvn = rep["assets"]["HG"]["filters"]["prior_hvn"]["tight"]["train"]
        assert hvn["occupancy"]["pick_rate"] > 0.99, hvn
        left = rep["assets"]["HG"]["leftover"]["tight"]["train"]
        assert left["leftover_frac"] > 0.8, left
        _synthetic_matrix(tmp / "pdh", signal=True, seed=3)
        _append_extra(tmp / "pdh", plant="disc_prior_high_aligned_usd")
        pdh = run(tmp / "pdh", tmp / "pdh.json", blocks=blocks, n_draw=40,
                  log=lambda *_: None)
        left2 = pdh["assets"]["HG"]["leftover"]["tight"]["train"]
        assert left2["leftover_frac"] < 0.2, left2
        _synthetic_matrix(tmp / "noise", signal=True, seed=11)
        _append_extra(tmp / "noise", plant=None)
        noise = run(tmp / "noise", tmp / "noise.json", blocks=blocks, n_draw=40,
                    log=lambda *_: None)
        n = noise["assets"]["HG"]["filters"]["prior_hvn"]["tight"]["train"]["occupancy"]
        assert n["diff_inside_shuffle_band"], n
        _synthetic_matrix(tmp / "red", signal=True)
        _append_extra(tmp / "red", plant="disc_prior_hvn_aligned_usd")
        man = json.loads((tmp / "red" / "manifest.json").read_text())
        xred = np.load(tmp / "red" / "x.npy")
        age = xred[:, man["feature_names"].index("min_alert_age_sec")]
        hit = int(np.flatnonzero(np.abs(age - DELTA_SEC) <= 2.5)[0])
        cur = np.load(tmp / "red" / "current_asinh.npy"); cur[hit] = np.nan
        np.save(tmp / "red" / "current_asinh.npy", cur)
        try:
            run(tmp / "red", tmp / "red.json", blocks=blocks, n_draw=2, log=lambda *_: None)
        except ProbeRefusal as exc:
            assert "non-finite" in str(exc), exc
        else:
            raise AssertionError("red fixture (NaN y) was accepted")
    print("selftest OK: planted prior_hvn pick_rate=1; leftover high/low; noise inside shuffle; NaN-y refused")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--matrix-dir", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--n-draw", type=int, default=N_DRAW)
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.matrix_dir is None or a.out is None:
        ap.error("--matrix-dir and --out are required unless --selftest")
    run(a.matrix_dir, a.out, n_draw=a.n_draw)
    return 0


if __name__ == "__main__":
    sys.exit(main())
