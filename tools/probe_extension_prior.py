#!/usr/bin/env python3
"""Extension-prior probe — the location lever seen exploratorily on 2026-08-22 (JOURNAL ~12:25Z:
picking by prior-level distance realized +38-56% of ceiling on the FROZEN score days).

PREREGISTRATION (written before the real run; echoed into the receipt):
- Question: within a cell (asset, day, phase), does the candidate that is MOST EXTENDED beyond
  the prior session's range on the side its reversal fades realize more standalone value than
  a random candidate — and how much of the per-asset-day ceiling does that rule keep?
- Extension, per candidate, from decision-time features only: for a long candidate
  (side=+1) ext = prior_low - mid; for a short (side=-1) ext = mid - prior_high; both are
  -aligned(own level) where aligned = side x (mid - level) x factor (discretionary_features
  :215-218), so ext > 0 means price is beyond the prior range on the fade side.
- Rules (each picks ONE series per cell at Delta; realized = its standalone y at Delta; one
  position per asset enforced by session-elapsed + occupancy; skipped cells $0):
  MAX_EXT (most extended), NEAREST_OWN_LEVEL (smallest |aligned own level| — the exploratory
  rule's nearest reading), MIN_EXT (least extended — the mirror; must not win), RANDOM
  (N_RANDOM uniform picks per cell — the null: the rule must clear its 97.5th percentile).
- Delta grid {0, 180, 290}s (the rule is formation-static; any Delta difference is the
  delay-forfeit, not information). Blocks: THRESHOLD (20210721-20210806) and FORWARD
  (20210809-20210826) reported separately, plus TRAIN (20210610-20210709) as the prior era.
- Denominator: per (asset, day) sum over cells of the series-best value (matrix ceiling);
  capture = realized / ceiling; $/asset-day beside it; day-level bootstrap CI (N_BOOT).
- Verdict per (asset, block, rule): CLEARS iff the day-bootstrap 2.5th percentile of capture
  exceeds the RANDOM null's 97.5th percentile on the same days. No fitting, no knobs.
- Closure check (CURRENT.md: "formation-moment candidate-local separation — null at every
  measured grain"): that closure measured label separability at the candidate grain; this
  probe scores a structural pick rule in dollars at the cell grain. A CLEARS verdict scopes
  the closure down; a failure leaves it standing. Either way the receipt names it.
- Tier: DIAGNOSTIC. Cell-pick dollars are not replay dollars.

Selftest: python3 tools/probe_extension_prior.py --selftest
Real:     python3 tools/probe_extension_prior.py --matrix-dir <round_0/component_matrix> --out <json>
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe_trained_accrual import (  # noqa: E402
    ELAPSED_COL, DeltaRows, ProbeRefusal, _ceiling_by_day, _cell_pick, load_delta_rows,
)

DELTAS = (0.0, 180.0, 290.0)
BLOCKS = {"train": (20210610, 20210709), "threshold": (20210721, 20210806),
          "forward": (20210809, 20210826)}
RULES = ("MAX_EXT", "NEAREST_OWN_LEVEL", "MIN_EXT", "RANDOM")
N_RANDOM, N_BOOT = 100, 200
LOW_COL, HIGH_COL, SIDE_COL = ("disc_prior_low_aligned_usd", "disc_prior_high_aligned_usd",
                               "side")


def extension_columns(rows: DeltaRows) -> tuple[np.ndarray, np.ndarray]:
    """(ext, abs_own_distance) per row; refuses when the plane lacks the inputs."""
    for c in (LOW_COL, HIGH_COL, SIDE_COL):
        if c not in rows.feature_names:
            raise ProbeRefusal(f"matrix lacks required column {c!r}")
    n = rows.feature_names
    side = rows.x[:, n.index(SIDE_COL)].astype(np.float64)
    low, high = (rows.x[:, n.index(LOW_COL)].astype(np.float64),
                 rows.x[:, n.index(HIGH_COL)].astype(np.float64))
    if not np.all(np.isin(side[~np.isnan(side)], (-1.0, 1.0))):
        raise ProbeRefusal("side column is not in {-1, +1}")
    own_aligned = np.where(side > 0, low, high)
    return -own_aligned, np.abs(own_aligned)


def _capture_by_day(rows: DeltaRows, idx: np.ndarray, score: np.ndarray,
                    ceiling: dict[int, float]) -> tuple[np.ndarray, np.ndarray]:
    pick = _cell_pick(score, rows.y[idx], rows.cell[idx], rows.day[idx],
                      rows.elapsed[idx], rows.occupancy[idx], -np.inf)
    days = sorted(ceiling)
    return (np.array([pick["all"].get(d, 0.0) for d in days]),
            np.array([ceiling[d] for d in days]))


def run(matrix_dir: Path, out_path: Path, *, blocks=BLOCKS, deltas=DELTAS,
        n_random: int = N_RANDOM, n_boot: int = N_BOOT, seed: int = 20260822,
        log=print) -> dict:
    rows = load_delta_rows(matrix_dir, deltas=deltas)
    ext, own_dist = extension_columns(rows)
    rows.x = np.empty((0, 0), np.float32)
    rng = np.random.default_rng(seed)
    report = {"schema": "QRE2EXTENSIONPRIOR1", "prereg": __doc__.split("Selftest:")[0],
              "matrix_receipt": rows.matrix_receipt, "deltas_sec": list(deltas),
              "blocks": dict(blocks), "rules": list(RULES), "n_random": n_random,
              "n_boot": n_boot, "assets": {}}
    for a in sorted(set(rows.asset)):
        report["assets"][a] = {}
        for bname, (lo, hi) in blocks.items():
            block = (rows.asset == a) & (rows.day >= lo) & (rows.day <= hi)
            ceiling = _ceiling_by_day(rows, block)
            if not ceiling:
                raise ProbeRefusal(f"{a} {bname}: no rows in {lo}-{hi}")
            report["assets"][a][bname] = {"n_days": len(ceiling),
                                          "ceiling_usd_per_asset_day": round(float(np.mean(list(ceiling.values()))), 2),
                                          "per_delta": {}}
            for d in deltas:
                idx = np.flatnonzero(block & (rows.delta == d))
                if not len(idx):
                    raise ProbeRefusal(f"{a} {bname}: no rows at Delta={d}")
                c = None
                scores = {"MAX_EXT": np.nan_to_num(ext[idx], nan=-np.inf),
                          "NEAREST_OWN_LEVEL": -np.nan_to_num(own_dist[idx], nan=np.inf),
                          "MIN_EXT": -np.nan_to_num(ext[idx], nan=-np.inf)}
                entry = {}
                rand_caps = []
                for _ in range(n_random):
                    r, c = _capture_by_day(rows, idx, rng.random(len(idx)), ceiling)
                    rand_caps.append(float(r.sum() / c.sum()))
                null_top = float(np.percentile(rand_caps, 97.5))
                entry["RANDOM"] = {"capture_mean": round(float(np.mean(rand_caps)), 4),
                                   "capture_p97_5": round(null_top, 4),
                                   "usd_per_asset_day": round(float(np.mean(rand_caps)) * float(np.mean(c)), 2)}
                for rule, sc in scores.items():
                    r, c = _capture_by_day(rows, idx, sc, ceiling)
                    cap = float(r.sum() / c.sum())
                    boots = []
                    for _ in range(n_boot):
                        b = rng.integers(0, len(r), len(r))
                        boots.append(r[b].sum() / c[b].sum() if c[b].sum() > 0 else np.nan)
                    lo_ci = float(np.nanpercentile(boots, 2.5))
                    entry[rule] = {"capture": round(cap, 4),
                                   "capture_ci95": [round(lo_ci, 4), round(float(np.nanpercentile(boots, 97.5)), 4)],
                                   "usd_per_asset_day": round(float(r.mean()), 2),
                                   "clears_random_null": bool(lo_ci > null_top)}
                report["assets"][a][bname]["per_delta"][str(int(d))] = entry
                log(f"{a} {bname} d{int(d)}: " + " ".join(
                    f"{k}={v['capture']:+.3f}{'*' if v['clears_random_null'] else ''}"
                    for k, v in entry.items() if k != "RANDOM") + f" random={entry['RANDOM']['capture_mean']:+.3f}(p97.5 {null_top:+.3f})")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".json.partial")
    tmp.write_text(json.dumps(report, indent=1)); tmp.replace(out_path)
    return report


# ----------------------------------------------------------------------------- selftest
def _synthetic(root: Path, *, signal: bool, seed: int = 5, n_days: int = 12,
               n_series: int = 15, drop_side: bool = False) -> None:
    rng = np.random.default_rng(seed)
    names = ["min_alert_age_sec", "phase_index", ELAPSED_COL, SIDE_COL, LOW_COL, HIGH_COL, "f0"]
    if drop_side:
        names.remove(SIDE_COL)
    ages = np.array([0, 180, 290], float)
    X, day, asset, series, y, occ = [], [], [], [], [], []
    sid = 0
    for d in range(1, n_days + 1):
        for phase in range(3):
            for _ in range(n_series):
                side = rng.choice([-1.0, 1.0])
                ext = rng.normal(0, 300)                      # beyond-range extension, usd
                base = (0.6 * ext if signal else 0.0) + rng.normal(0, 150)
                low_al = -ext if side > 0 else rng.normal(0, 300)
                high_al = -ext if side < 0 else rng.normal(0, 300)
                for a in ages:
                    row = [a, phase, phase * 7200 + 600 + a] + ([side] if not drop_side else []) \
                          + [low_al, high_al, rng.normal()]
                    X.append(row); day.append(20210600 + d); asset.append("HG")
                    series.append(f"s{sid}"); y.append(base + rng.normal(0, 40)); occ.append(300.0)
                sid += 1
    root.mkdir(parents=True, exist_ok=True)
    np.save(root / "x.npy", np.asarray(X, np.float32)); np.save(root / "day.npy", np.asarray(day, np.int64))
    np.save(root / "asset.npy", np.asarray(asset)); np.save(root / "series_id.npy", np.asarray(series))
    np.save(root / "current_asinh.npy", np.arcsinh(np.asarray(y) / 600.0))
    np.save(root / "occupancy_sec.npy", np.asarray(occ))
    (root / "manifest.json").write_text(json.dumps(
        {"feature_names": names, "rows": len(X), "matrix_receipt_sha256": "synthetic"}))


def selftest() -> int:
    blocks = {"train": (20210601, 20210606), "forward": (20210607, 20210612)}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _synthetic(tmp / "sig", signal=True)
        rep = run(tmp / "sig", tmp / "sig.json", blocks=blocks, n_random=30, n_boot=30,
                  log=lambda *_: None)
        e = rep["assets"]["HG"]["forward"]["per_delta"]["0"]
        assert e["MAX_EXT"]["clears_random_null"], f"planted extension signal not recovered: {e}"
        assert e["MAX_EXT"]["capture"] > e["MIN_EXT"]["capture"], "mirror rule must lose"
        _synthetic(tmp / "nosig", signal=False, seed=9)
        rep = run(tmp / "nosig", tmp / "nosig.json", blocks=blocks, n_random=30, n_boot=30,
                  log=lambda *_: None)
        e2 = rep["assets"]["HG"]["forward"]["per_delta"]["0"]
        assert not e2["MAX_EXT"]["clears_random_null"], f"no-signal fixture cleared the null: {e2}"
        _synthetic(tmp / "red", signal=True, drop_side=True)
        try:
            run(tmp / "red", tmp / "red.json", blocks=blocks, n_random=2, n_boot=2, log=lambda *_: None)
        except ProbeRefusal:
            pass
        else:
            raise AssertionError("red fixture (no side column) was accepted")
    print(f"selftest OK: planted MAX_EXT capture {e['MAX_EXT']['capture']:.3f} clears null "
          f"(p97.5 {e['RANDOM']['capture_p97_5']:.3f}); no-signal stays inside; red fixture refused")
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
