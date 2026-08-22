#!/usr/bin/env python3
"""Wait until the paying name, and scan every column — ticket 26.

PREREGISTRATION (written before the real run; echoed into the receipt):
- Wait: among live keep-first names, seconds from first formation to
  cell-max formation (eligibility order is formation order at Δ=180).
  Publish median/p25/p75/p90 and fraction of winners arrived by
  0, 60, 180, 300, 600, 1200, 1800, 3600 s after the first.
- Scan: for every matrix column, prefix winner-vs-earlier AUC
  (same frame as ticket 25). TRAIN ranks. THRESHOLD is the holdout.
  Survive iff TRAIN AUC>=0.60 and THRESHOLD AUC>=0.60. Columns whose
  names contain remaining, elapsed, age, clock, or ctx_ cannot grant
  'column_holds' (they are the clock family T25 already showed is
  anti-informative). FORWARD reported, never a knob.
- 2021 cannot promote. No CatBoost.

Letters:
  column_holds     a non-clock column survives TRAIN+THRESHOLD
  only_clock       only clock-named columns survive
  no_single_column none survive (combinations unmeasured)

Selftest: python3 tools/probe_crux_wait_scan.py --selftest
Real:     OMP_NUM_THREADS=1 python3 tools/probe_crux_wait_scan.py \\
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
from probe_crux_prefix_winner import _mann_whitney  # noqa: E402
from probe_location_family_screen import _col  # noqa: E402
from probe_path_dedup import _formation_sec, _theta  # noqa: E402
from probe_path_dedup_live import (  # noqa: E402
    DELTA_SEC, FORM_DELTA, SIDE_COL, VWAP_COL,
)
from probe_rho_on_dedup import WIDTH_MULT, _keep_idx  # noqa: E402
from probe_rho_ruler import BLOCKS, PHASE_REMAINING_COL, _cell_groups  # noqa: E402
from probe_trained_accrual import (  # noqa: E402
    ELAPSED_COL, ProbeRefusal, load_delta_rows,
)

SCHEMA = "QRE2CRUXWAIT1"
WAIT_GATES = (0.0, 60.0, 180.0, 300.0, 600.0, 1200.0, 1800.0, 3600.0)
TOP_N = 15
AUC_BAR = 0.60
CLOCK_TOKENS = ("remaining", "elapsed", "age", "clock", "ctx_")


def _is_clock_name(name: str) -> bool:
    n = name.lower()
    return any(tok in n for tok in CLOCK_TOKENS)


def _prefixes(y: np.ndarray, cell: np.ndarray, formed: np.ndarray):
    waits = []
    multi = []
    winners = []
    for g in _cell_groups(cell):
        order = g[np.argsort(formed[g], kind="stable")]
        wi = int(g[np.argmax(y[g])])
        waits.append(float(formed[wi] - formed[int(order[0])]))
        pref = order[formed[order] <= formed[wi] + 1e-9]
        if len(pref) >= 2:
            multi.append(pref)
            winners.append(wi)
    return np.asarray(waits, np.float64), multi, winners


def _wait_table(waits: np.ndarray) -> dict:
    if len(waits) == 0:
        return {"n": 0}
    out = {"n": int(len(waits)),
           "median_sec": float(np.median(waits)),
           "p25_sec": float(np.quantile(waits, 0.25)),
           "p75_sec": float(np.quantile(waits, 0.75)),
           "p90_sec": float(np.quantile(waits, 0.90))}
    arrived = {}
    for g in WAIT_GATES:
        arrived[str(int(g))] = float(np.mean(waits <= g + 1e-9))
    out["frac_arrived_by_sec"] = arrived
    return out


def _col_auc(sc: np.ndarray, multi: list, winners: list[int]) -> float:
    vals = []
    for pref, wi in zip(multi, winners):
        others = pref[pref != wi]
        vals.append(_mann_whitney(np.asarray([sc[wi]]), sc[others]))
    return float(np.nanmean(vals)) if vals else float("nan")


def _block(y, x, names: list[str], cell, formed) -> dict:
    waits, multi, winners = _prefixes(y, cell, formed)
    wait = _wait_table(waits)
    aucs = []
    for j, name in enumerate(names):
        sc = x[:, j].astype(np.float64)
        if np.mean(np.isfinite(sc)) < 0.5:
            continue
        a = _col_auc(sc, multi, winners)
        if not np.isfinite(a):
            continue
        aucs.append((float(a), name, j, _is_clock_name(name)))
    aucs.sort(reverse=True)
    return {"wait": wait, "ranked": aucs}


def run(matrix_dir: Path, out_path: Path, *, blocks=BLOCKS, log=print) -> dict:
    rows180 = load_delta_rows(matrix_dir, deltas=(DELTA_SEC,))
    rows0 = load_delta_rows(matrix_dir, deltas=(FORM_DELTA,))
    if not np.isfinite(rows180.y).all():
        raise ProbeRefusal(
            f"{int(np.sum(~np.isfinite(rows180.y)))} non-finite y; expected all finite USD")
    names = rows180.feature_names
    all_days = (int(rows180.day.min()), int(rows180.day.max()))
    report: dict = {
        "schema": SCHEMA, "prereg": __doc__, "matrix_receipt": rows180.matrix_receipt,
        "delta_sec": DELTA_SEC, "width_mult": WIDTH_MULT, "auc_bar": AUC_BAR,
        "blocks": {**{k: list(v) for k, v in blocks.items()}, "all": list(all_days)},
        "assets": {},
    }
    cached = {}
    for asset in sorted(set(rows180.asset.tolist())):
        if asset not in WIDTH_MULT:
            continue
        report["assets"][asset] = {"width_mult": WIDTH_MULT[asset]}
        for bname, (lo, hi) in {**blocks, "all": all_days}.items():
            idx = np.flatnonzero(
                (rows180.asset == asset) & (rows180.day >= lo) & (rows180.day <= hi)
                & (rows180.delta == DELTA_SEC))
            if len(idx) == 0:
                continue
            kept = _keep_idx(rows180, rows0, idx, asset)
            blk = _block(rows180.y[kept], rows180.x[kept], names,
                         rows180.cell[kept], _formation_sec(rows180.x[kept], names))
            cached[(asset, bname)] = blk
            report["assets"][asset][bname] = {
                "wait": blk["wait"],
                "n_columns_scored": len(blk["ranked"]),
                "top_train_placeholder": True,
            }
            w = blk["wait"]
            log(f"{asset:4s} {bname:10s} wait_med={w.get('median_sec', float('nan')):.0f}s "
                f"p90={w.get('p90_sec', float('nan')):.0f}s "
                f"by300={w.get('frac_arrived_by_sec', {}).get('300', float('nan')):.2f}")
    # TRAIN ranks, THRESHOLD holdout
    for asset in report["assets"]:
        tr = cached.get((asset, "train"))
        th = cached.get((asset, "threshold"))
        fw = cached.get((asset, "forward"))
        if tr is None:
            continue
        top = []
        survivors = []
        for auc, name, j, is_clock in tr["ranked"][:TOP_N]:
            th_auc = None
            fw_auc = None
            if th is not None:
                th_map = {n: a for a, n, _, _ in th["ranked"]}
                th_auc = th_map.get(name)
            if fw is not None:
                fw_map = {n: a for a, n, _, _ in fw["ranked"]}
                fw_auc = fw_map.get(name)
            row = {"name": name, "clock_family": is_clock,
                   "train_auc": auc,
                   "threshold_auc": th_auc, "forward_auc": fw_auc}
            survives = (auc >= AUC_BAR and th_auc is not None and th_auc >= AUC_BAR)
            row["survives"] = bool(survives)
            top.append(row)
            if survives:
                survivors.append(row)
        non_clock = [s for s in survivors if not s["clock_family"]]
        if non_clock:
            letter = "column_holds"
        elif survivors:
            letter = "only_clock"
        else:
            letter = "no_single_column"
        report["assets"][asset]["scan"] = {
            "letter": letter, "top_train": top,
            "n_survive": len(survivors), "n_survive_nonclock": len(non_clock),
            "best_train_auc": tr["ranked"][0][0] if tr["ranked"] else None,
            "best_train_name": tr["ranked"][0][1] if tr["ranked"] else None,
        }
        for bname in ("train", "threshold", "forward", "all"):
            if bname in report["assets"][asset]:
                report["assets"][asset][bname].pop("top_train_placeholder", None)
        log(f"{asset:4s} scan={letter} best={report['assets'][asset]['scan']['best_train_name']}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=1, sort_keys=True))
    return report


def _plant(root: Path, *, mode: str = "ok") -> None:
    names = ["min_alert_age_sec", "phase_index", ELAPSED_COL,
             "disc_fvol_phase_scope_elapsed_sec", PHASE_REMAINING_COL, VWAP_COL,
             SIDE_COL, "planted_winner_mark"]
    theta = _theta("HG")
    specs = [
        (400.0, 280.0, 0.0, 0.0),
        (2500.0, 480.0, 8.0 * theta, 1.0),
        (100.0, 680.0, 16.0 * theta, 0.0),
    ]
    xs, days, assets, series, ys, occs = [], [], [], [], [], []
    for d in (20210610, 20210611):
        for s, (yv, el180, vwap, mark) in enumerate(specs):
            for age in (0.0, 180.0):
                elapsed = el180 - 180.0 + age
                xs.append([age, 0.0, elapsed, elapsed, 10000.0 - elapsed, vwap, 1.0, mark])
                days.append(d); assets.append("HG"); series.append(f"s{d}_{s}")
                ys.append(yv); occs.append(600.0)
    root.mkdir(parents=True, exist_ok=True)
    yv = np.asarray(ys, np.float64)
    if mode == "nan":
        yv[1] = np.nan
    np.save(root / "x.npy", np.asarray(xs, np.float32))
    np.save(root / "day.npy", np.asarray(days, np.int64))
    np.save(root / "asset.npy", np.asarray(assets))
    np.save(root / "series_id.npy", np.asarray(series))
    np.save(root / "current_asinh.npy", np.arcsinh(yv / 600.0))
    np.save(root / "occupancy_sec.npy", np.asarray(occs, np.float64))
    (root / "manifest.json").write_text(json.dumps(
        {"feature_names": names, "rows": len(xs), "matrix_receipt_sha256": "synthetic"}))


def selftest() -> int:
    blocks = {"train": (20210610, 20210709), "threshold": (20210610, 20210709)}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _plant(tmp / "p")
        rep = run(tmp / "p", tmp / "p.json", blocks=blocks, log=lambda *_: None)
        tr = rep["assets"]["HG"]["train"]["wait"]
        assert abs(tr["median_sec"] - 200.0) < 1.0, tr
        assert tr["frac_arrived_by_sec"]["0"] == 0.0, tr
        scan = rep["assets"]["HG"]["scan"]
        assert scan["best_train_name"] == "planted_winner_mark", scan
        assert scan["letter"] == "column_holds", scan
        _plant(tmp / "red", mode="nan")
        try:
            run(tmp / "red", tmp / "red.json", blocks=blocks, log=lambda *_: None)
        except ProbeRefusal as exc:
            assert "non-finite" in str(exc), exc
        else:
            raise AssertionError("NaN y was accepted")
    print("selftest OK: wait 200s, planted column holds, NaN refused")
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
