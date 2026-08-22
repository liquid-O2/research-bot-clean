#!/usr/bin/env python3
"""Location family screen — ticket 11 of design/entry_reset (2026-08-22).

PREREGISTRATION (written before the real run; echoed into the receipt):
- Question: which FINISHED location family keeps the cell's winner on the
  frozen 2021 matrix? Families are scored ONE AT A TIME. Stacking them into
  one gate is a later ticket. A miss on one family at one width is not a
  null of "location".
- A name sits at a family iff min_j |col_j| <= theta_usd. theta_usd is TRAIN
  winner MAE (ticket 09): tight = median ticks, wide = p75 ticks, times
  TICK_USD. Knobs from TRAIN only (D-095).
- Metric per (family, asset, block, width): shrink_ceiling = mean over days of
  (sum over cells of max y among eligible names; ineligible cell = $0);
  occupancy = fraction of cell-oracle (argmax y) eligible vs non-picks vs
  200-draw within-cell shuffle of the flag; median eligible names per cell.
- Rank families on TRAIN shrink_ceiling. THRESHOLD and FORWARD of the
  TRAIN-best family are reported, never used to pick theta or the family.
- Kill (per family, not of "location"): TRAIN shrink_ceiling below the rung
  AND occupancy diff inside the shuffle band. That family does not mark
  winners at this width on 2021. Other families remain live.
- Gaps, untested, not nulls: PWH/PWL, PMH/PML, multi-day untouched PDH/PDL,
  VWAP +/-2s and +/-2.5s (no session VWAP std column; do not substitute ATR).
- Controls expected weaker: prior_poc, session_vah_val (live/moving value).
- Tier: DIAGNOSTIC screen. 2021 cannot promote. Dollars vs rung are the
  ranking, not AUC.

Selftest: python3 tools/probe_location_family_screen.py --selftest
Real:     OMP_NUM_THREADS=1 python3 tools/probe_location_family_screen.py \\
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
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe_trained_accrual import (  # noqa: E402
    ProbeRefusal, _synthetic_matrix, load_delta_rows, shuffle_within_groups,
)
from probe_rho_ruler import BLOCKS, RUNG_USD, _cell_groups, _ceiling_180_by_day  # noqa: E402

SCHEMA = "QRE2LOCFAM1"
N_DRAW = 200
DELTA_SEC = 180.0
TICK_USD = {"SI": 25.0, "HG": 12.5, "NKD": 25.0}
# Ticket 09 TRAIN winner MAE ticks (median / p75). Provenance: scale receipt.
THETA_TICKS = {
    "HG": {"tight": 4.0, "wide": 9.5},
    "NKD": {"tight": 2.5, "wide": 4.5},
    "SI": {"tight": 3.0, "wide": 7.0},
}
FAMILIES = {
    "pdh_pdl": ("disc_prior_high_aligned_usd", "disc_prior_low_aligned_usd"),
    "prior_vah_val": ("disc_prior_vah_aligned_usd", "disc_prior_val_aligned_usd"),
    "prior_lvn": ("disc_prior_lvn_aligned_usd",),
    "prior_poc": ("disc_prior_poc_aligned_usd",),
    "ib_high_low": ("disc_ib_phase_high_aligned_usd", "disc_ib_phase_low_aligned_usd"),
    "session_vwap": ("disc_auction_session_vwap_aligned_usd",),
    "session_lvn": ("disc_auction_session_nearest_lvn_aligned_usd",),
    "session_vah_val": (
        "disc_auction_session_vah_aligned_usd",
        "disc_auction_session_val_aligned_usd",
    ),
}
GAPS = (
    "pwh_pwl",
    "pmh_pml",
    "untouched_multi_day_pdh_pdl",
    "vwap_pm_2_sigma",
    "vwap_pm_2_5_sigma",
)
CONTROLS = frozenset({"prior_poc", "session_vah_val"})
# On-matrix, not in ticket 11's frozen list. Phase IB is live until 3600s
# (discretionary_features.py:1063). Session IB is the finished first hour.
EXPLORATORY_FAMILIES = {
    "ib_session": ("disc_ib_session_high_aligned_usd", "disc_ib_session_low_aligned_usd"),
}


def _col(names: list[str], name: str) -> int:
    if name not in names:
        raise ProbeRefusal(f"matrix lacks required column {name!r}; have {len(names)} names")
    return names.index(name)


def at_family_mask(x: np.ndarray, names: list[str], cols: tuple[str, ...],
                   theta_usd: float) -> np.ndarray:
    dist = np.min(np.stack([np.abs(x[:, _col(names, c)]) for c in cols], axis=1), axis=1)
    return dist <= float(theta_usd)


def _occupancy(flag: np.ndarray, y: np.ndarray, cell: np.ndarray, *,
               n_draw: int, rng: np.random.Generator) -> dict:
    if not np.isfinite(y).all():
        raise ProbeRefusal(
            f"{int(np.sum(~np.isfinite(y)))} non-finite y values; expected all finite USD")
    groups = _cell_groups(cell)
    picks = np.array([int(g[int(np.argmax(y[g]))]) for g in groups], np.int64)
    non = np.ones(len(flag), bool)
    non[picks] = False
    pick_rate = float(flag[picks].mean()) if len(picks) else float("nan")
    non_rate = float(flag[non].mean()) if non.any() else float("nan")
    shuf = np.empty(n_draw, np.float64)
    f = flag.astype(np.float64)
    for i in range(n_draw):
        perm = shuffle_within_groups(f, cell, rng)
        shuf[i] = float(perm[picks].mean() - (perm[non].mean() if non.any() else 0.0))
    diff = pick_rate - non_rate
    lo, hi = float(np.quantile(shuf, 0.025)), float(np.quantile(shuf, 0.975))
    n_elig = np.array([int(flag[g].sum()) for g in groups], np.float64)
    return {
        "pick_rate": pick_rate,
        "nonpick_rate": non_rate,
        "pick_minus_nonpick": float(diff),
        "shuffle_diff_p025": lo,
        "shuffle_diff_p975": hi,
        "diff_inside_shuffle_band": bool(lo <= diff <= hi),
        "median_eligible_per_cell": float(np.median(n_elig)) if len(n_elig) else float("nan"),
        "frac_cells_nobody": float(np.mean(n_elig == 0)),
        "frac_cells_everybody": float(np.mean(n_elig == np.array([len(g) for g in groups]))),
    }


def _shrink_ceiling(flag: np.ndarray, y: np.ndarray, cell: np.ndarray,
                    day: np.ndarray) -> float:
    groups = _cell_groups(cell)
    by_day: dict[int, float] = {}
    days = sorted({int(d) for d in day})
    for g in groups:
        d = int(day[g[0]])
        hit = g[flag[g]]
        val = float(y[hit].max()) if len(hit) else 0.0
        by_day[d] = by_day.get(d, 0.0) + val
    return float(sum(by_day.get(d, 0.0) for d in days) / len(days)) if days else float("nan")


def score_family(rows, idx: np.ndarray, cols: tuple[str, ...], theta_usd: float, *,
                 n_draw: int, seed: int) -> dict:
    x, y, cell, day = rows.x[idx], rows.y[idx], rows.cell[idx], rows.day[idx]
    flag = at_family_mask(x, rows.feature_names, cols, theta_usd)
    occ = _occupancy(flag, y, cell, n_draw=n_draw, rng=np.random.default_rng(seed))
    shrink = _shrink_ceiling(flag, y, cell, day)
    groups = _cell_groups(cell)
    unf = _ceiling_180_by_day(y, day, groups)
    days = sorted({int(d) for d in day})
    unfiltered = float(sum(unf.values()) / len(days)) if days else float("nan")
    typed = []
    if occ["frac_cells_nobody"] > 0.90:
        typed.append("GATE-DEFECT selects nobody on >90% of cells")
    if occ["frac_cells_everybody"] > 0.90:
        typed.append("GATE-DEFECT selects everybody on >90% of cells")
    return {
        "theta_usd": float(theta_usd),
        "shrink_ceiling_usd_per_asset_day": shrink,
        "unfiltered_ceiling_usd_per_asset_day": unfiltered,
        "retained_fraction": float(shrink / unfiltered) if unfiltered else float("nan"),
        "occupancy": occ,
        "typed": typed,
        "n_rows": int(len(idx)),
        "n_days": int(len(days)),
    }


def run(matrix_dir: Path, out_path: Path, *, blocks=BLOCKS, n_draw: int = N_DRAW,
        log=print, families: dict | None = None) -> dict:
    families = dict(FAMILIES if families is None else families)
    rows = load_delta_rows(matrix_dir, deltas=(DELTA_SEC,))
    if not np.isfinite(rows.y).all():
        raise ProbeRefusal(
            f"{int(np.sum(~np.isfinite(rows.y)))} non-finite y; expected all finite USD")
    for cols in families.values():
        for c in cols:
            _col(rows.feature_names, c)
    all_days = (int(rows.day.min()), int(rows.day.max()))
    report: dict = {
        "schema": SCHEMA, "prereg": __doc__, "matrix_receipt": rows.matrix_receipt,
        "delta_sec": DELTA_SEC, "n_draw": n_draw,
        "gaps_untested": list(GAPS),
        "controls": sorted(CONTROLS),
        "family_set": sorted(families),
        "blocks": {**{k: list(v) for k, v in blocks.items()}, "all": list(all_days)},
        "assets": {},
    }
    for asset in sorted(set(rows.asset.tolist())):
        report["assets"][asset] = {"rung_usd": RUNG_USD[asset], "families": {}}
        tick = TICK_USD[asset]
        for fam, cols in families.items():
            report["assets"][asset]["families"][fam] = {}
            for width, ticks in THETA_TICKS[asset].items():
                theta = ticks * tick
                report["assets"][asset]["families"][fam][width] = {}
                for bname, (lo, hi) in {**blocks, "all": all_days}.items():
                    idx = np.flatnonzero(
                        (rows.asset == asset) & (rows.day >= lo) & (rows.day <= hi)
                        & (rows.delta == DELTA_SEC))
                    if len(idx) == 0:
                        continue
                    block = score_family(rows, idx, cols, theta, n_draw=n_draw, seed=0)
                    report["assets"][asset]["families"][fam][width][bname] = block
                    log(f"{asset:4s} {fam:16s} {width:5s} {bname:10s} "
                        f"shrink={block['shrink_ceiling_usd_per_asset_day']:7.1f} "
                        f"ret={block['retained_fraction']:.2f} "
                        f"pick={block['occupancy']['pick_rate']:.3f} "
                        f"ncell={block['occupancy']['median_eligible_per_cell']:.1f}"
                        f"{'' if not block['typed'] else ' TYPED'}")
        # TRAIN rank of families at tight width.
        ranked = []
        for fam in families:
            tr = report["assets"][asset]["families"][fam].get("tight", {}).get("train")
            if tr is None:
                continue
            ranked.append((tr["shrink_ceiling_usd_per_asset_day"], fam))
        ranked.sort(reverse=True)
        best = ranked[0][1] if ranked else None
        report["assets"][asset]["train_rank_tight"] = [
            {"family": f, "shrink_ceiling": s} for s, f in ranked]
        report["assets"][asset]["train_best_tight"] = best
        if best is not None:
            fwd = report["assets"][asset]["families"][best].get("tight", {}).get("forward")
            report["assets"][asset]["train_best_tight_forward"] = fwd
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=1, sort_keys=True))
    return report


def _append_location_columns(root: Path, *, plant_pdh: bool) -> None:
    x = np.load(root / "x.npy")
    man = json.loads((root / "manifest.json").read_text())
    y = np.sinh(np.load(root / "current_asinh.npy")) * 600.0
    ordered = []
    for cols in FAMILIES.values():
        for c in cols:
            if c not in ordered:
                ordered.append(c)
    extra = np.full((len(x), len(ordered)), 500.0, np.float32)
    if plant_pdh:
        day = np.load(root / "day.npy")
        series = np.asarray(np.load(root / "series_id.npy"), str)
        age = x[:, man["feature_names"].index("min_alert_age_sec")]
        phase = x[:, man["feature_names"].index("phase_index")]
        # Occupancy is post load_delta_rows at Δ=180; plant that grain's
        # winner series, not the unfiltered-age argmax (ticket 11 plant).
        at_delta = np.abs(age - DELTA_SEC) <= 2.5
        cell = day.astype(np.int64) * 10 + np.nan_to_num(phase, nan=9).astype(np.int64)
        order = np.argsort(cell, kind="stable")
        keep = order[at_delta[order]]
        bounds = np.flatnonzero(np.diff(cell[keep])) + 1
        pdh = ordered.index("disc_prior_high_aligned_usd")
        pdl = ordered.index("disc_prior_low_aligned_usd")
        for grp in np.split(keep, bounds):
            if len(grp) == 0:
                continue
            win = grp[int(np.argmax(y[grp]))]
            extra[series == series[win], pdh] = 0.0
            extra[series == series[win], pdl] = 0.0
    x = np.concatenate([x, extra], axis=1)
    man["feature_names"].extend(ordered)
    np.save(root / "x.npy", x)
    (root / "manifest.json").write_text(json.dumps(man))


def selftest() -> int:
    blocks = {"train": (20210601, 20210624), "forward": (20210601, 20210624)}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _synthetic_matrix(tmp / "planted", signal=True)
        _append_location_columns(tmp / "planted", plant_pdh=True)
        rep = run(tmp / "planted", tmp / "planted.json", blocks=blocks, n_draw=40,
                  log=lambda *_: None)
        pdh = rep["assets"]["HG"]["families"]["pdh_pdl"]["tight"]["train"]
        poc = rep["assets"]["HG"]["families"]["prior_poc"]["tight"]["train"]
        assert pdh["occupancy"]["pick_rate"] > 0.99, pdh
        assert pdh["shrink_ceiling_usd_per_asset_day"] >= poc["shrink_ceiling_usd_per_asset_day"], (
            pdh, poc)
        _synthetic_matrix(tmp / "noise", signal=True, seed=11)
        _append_location_columns(tmp / "noise", plant_pdh=False)
        noise = run(tmp / "noise", tmp / "noise.json", blocks=blocks, n_draw=40,
                    log=lambda *_: None)
        n = noise["assets"]["HG"]["families"]["pdh_pdl"]["tight"]["train"]["occupancy"]
        assert n["diff_inside_shuffle_band"], n
        _synthetic_matrix(tmp / "red", signal=True)
        _append_location_columns(tmp / "red", plant_pdh=True)
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
    print("selftest OK: planted pdh_pdl pick_rate=1; noise inside shuffle; NaN-y refused")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--matrix-dir", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--n-draw", type=int, default=N_DRAW)
    ap.add_argument("--exploratory", action="store_true",
                    help="also score EXPLORATORY_FAMILIES (ib_session). Labeled, not the frozen set.")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.matrix_dir is None or a.out is None:
        ap.error("--matrix-dir and --out are required unless --selftest")
    fam = dict(FAMILIES)
    if a.exploratory:
        fam.update(EXPLORATORY_FAMILIES)
    run(a.matrix_dir, a.out, n_draw=a.n_draw, families=fam)
    return 0


if __name__ == "__main__":
    sys.exit(main())
