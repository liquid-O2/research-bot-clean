#!/usr/bin/env python3
"""Column scan in the new-extreme-event frame — ticket 36 (2026-08-23).

Ticket 35 established the frame and its two verdicts. The final per-side extreme
is ALWAYS a new-extreme event (recall 1.000 on all three assets), so the event
set holds the money; its oracle cashes $2,772 HG / $1,851 NKD / $2,396 SI at each
event's own DELTA_SEC row, which is EXACTLY labelled — no age-180 proxy and no
unpriceable wait. And every causal arm tried (position, phase fraction, depth of
beat, the confirmation composite) sits at or inside its null.

So the question is now sharp and small: among the ~6 new-extreme events of a
cell, does ANY column of this matrix separate the best-y event from the rest,
using only each event's own row?

This is NOT ticket 26 re-run. Ticket 26 scanned the prefix frame, ranked columns
by raw value, and its winner was last-born by construction, which made every
clock tautological. Here the candidate set is the events, the label is exact, the
frame is side-resolved, and the best-y event is not systematically last.

PREREGISTRATION (written before the run):
- Universe: live keep-first names that are new-extreme events under the TRAIN
  orientation and score column from ticket 35.
- Label: within a cell, the event with the highest y. Cells with fewer than two
  events are dropped and the drop count is reported.
- Statistic: within-cell Mann-Whitney AUC of the column against that label,
  pooled over cells. Both the raw column and its side-resolved form
  (column * side), since the paying geometry is side-resolved.
- A column SURVIVES only with TRAIN AUC >= 0.60 AND THRESHOLD AUC >= 0.60 in the
  same direction. Everything else is reported and discarded.
- Clock columns are reported but flagged `clock_family`: they are the tautology
  that ate ticket 26 and must not be promoted without a causal argument.
- Null: shuffle the label within the cell, 40 draws, to give the AUC its floor.
- 2021 cannot promote.

Selftest: python3 tools/probe_event_column_scan.py --selftest
Real:     OMP_NUM_THREADS=1 python3 tools/probe_event_column_scan.py \
            --matrix-dir <component_matrix> --out <receipt.json>
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
    N_DRAW, PHASE_VWAP_COL, _cell_groups, _plant, _stage_a,
)
from probe_location_family_screen import _col  # noqa: E402
from probe_path_dedup import PHASE_ELAPSED_COL, _formation_sec  # noqa: E402
from probe_path_dedup_live import DELTA_SEC, FORM_DELTA, SIDE_COL, VWAP_COL  # noqa: E402
from probe_rho_on_dedup import WIDTH_MULT, _keep_idx  # noqa: E402
from probe_rho_ruler import BLOCKS, RUNG_USD  # noqa: E402
from probe_trained_accrual import ProbeRefusal, load_delta_rows  # noqa: E402

SCHEMA = "QRE2EVENTCOLSCAN1"
SCORE_COLS = (("session", VWAP_COL), ("phase", PHASE_VWAP_COL))
SURVIVE_AUC = 0.60
CLOCK_RE = re.compile(r"elapsed|remaining|age_sec|_ts_|phase_index|min_alert", re.I)


def within_cell_auc(values: np.ndarray, winner: np.ndarray,
                    cell: np.ndarray) -> tuple[float, int]:
    """Pooled within-cell Mann-Whitney AUC of `values` for winner vs non-winner.

    Pooled over cells rather than computed globally: a global AUC would be driven
    by between-cell level differences, which say nothing about which name in THIS
    phase pays.
    """
    wins = losses = ties = 0.0
    used = 0
    for g in _cell_groups(cell):
        w = values[g][winner[g]]
        l = values[g][~winner[g]]
        w = w[np.isfinite(w)]
        l = l[np.isfinite(l)]
        if not len(w) or not len(l):
            continue
        used += 1
        wins += float(np.sum(w[:, None] > l[None, :]))
        losses += float(np.sum(w[:, None] < l[None, :]))
        ties += float(np.sum(w[:, None] == l[None, :]))
    total = wins + losses + ties
    return (float((wins + 0.5 * ties) / total) if total else float("nan")), used


def scan_block(x: np.ndarray, names: list[str], side: np.ndarray, y: np.ndarray,
               is_event: np.ndarray, cell: np.ndarray) -> dict[str, float]:
    """AUC per column, raw and side-resolved, on the event rows of each cell."""
    keep = np.flatnonzero(is_event)
    xe, ye, ce, se = x[keep], y[keep], cell[keep], side[keep]
    winner = np.full(len(keep), False)
    for g in _cell_groups(ce):
        if len(g) < 2:
            continue
        winner[int(g[int(np.argmax(ye[g]))])] = True
    multi = np.full(len(keep), False)
    for g in _cell_groups(ce):
        if len(g) >= 2:
            multi[g] = True
    xe, ye, ce, se, winner = xe[multi], ye[multi], ce[multi], se[multi], winner[multi]
    out: dict[str, float] = {}
    for j, name in enumerate(names):
        col = xe[:, j].astype(np.float64)
        if not np.isfinite(col).any():
            continue
        auc, used = within_cell_auc(col, winner, ce)
        if used:
            out[name] = auc
        auc_s, used_s = within_cell_auc(col * se, winner, ce)
        if used_s:
            out[f"{name} * side"] = auc_s
    out["__cells__"] = float(len(set(ce.tolist())))
    out["__rows__"] = float(len(ce))
    return out


def run(matrix_dir: Path, out_path: Path, *, blocks=BLOCKS, n_draw: int = N_DRAW,
        log=print) -> dict:
    rows180 = load_delta_rows(matrix_dir, deltas=(DELTA_SEC,))
    rows0 = load_delta_rows(matrix_dir, deltas=(FORM_DELTA,))
    if not np.isfinite(rows180.y).all():
        raise ProbeRefusal("non-finite y on the component matrix")
    names = rows180.feature_names
    rng = np.random.default_rng(20260823)
    report: dict = {"schema": SCHEMA, "prereg": __doc__,
                    "matrix_receipt": rows180.matrix_receipt,
                    "survive_auc": SURVIVE_AUC, "assets": {}}

    for asset in sorted(set(rows180.asset.tolist())):
        if asset not in WIDTH_MULT:
            continue
        entry: dict = {"rung_usd": RUNG_USD[asset]}
        report["assets"][asset] = entry
        packed = {}
        for bname, (lo, hi) in blocks.items():
            idx = np.flatnonzero((rows180.asset == asset) & (rows180.day >= lo)
                                 & (rows180.day <= hi) & (rows180.delta == DELTA_SEC))
            if len(idx) == 0:
                continue
            kept = _keep_idx(rows180, rows0, idx, asset)
            packed[bname] = dict(
                x=rows180.x[kept], y=rows180.y[kept], cell=rows180.cell[kept],
                day=rows180.day[kept], elapsed=rows180.elapsed[kept],
                occupancy=rows180.occupancy[kept],
                side=rows180.x[kept, _col(names, SIDE_COL)].astype(np.float64),
                formed=_formation_sec(rows180.x[kept], names),
                vw={t: rows180.x[kept, _col(names, c)].astype(np.float64)
                    for t, c in SCORE_COLS})
        train = packed.get("train")
        if train is None:
            continue
        best = None
        for tag, _c in SCORE_COLS:
            blk = _stage_a(train["y"], train["side"], train["vw"][tag], train["cell"],
                           train["day"], train["elapsed"], train["occupancy"],
                           sorted({int(d) for d in train["day"]}), RUNG_USD[asset],
                           rng, n_draw)
            if best is None or blk["vwap_better_usd"] > best[1]["vwap_better_usd"]:
                best = (tag, blk)
        tag, a_blk = best
        long_min = a_blk["best_orientation"].startswith("long_min")
        short_min = a_blk["best_orientation"].endswith("short_min")
        entry.update(chosen_score=tag, orientation=a_blk["best_orientation"])

        aucs = {}
        for bname, pack in packed.items():
            ev, _, _ = extreme_events(pack["formed"], pack["side"], pack["vw"][tag],
                                      pack["cell"], long_min, short_min)
            aucs[bname] = scan_block(pack["x"], names, pack["side"], pack["y"],
                                     ev, pack["cell"])

        # Null floor: shuffle which event is the winner, within the cell.
        ev_tr, _, _ = extreme_events(train["formed"], train["side"], train["vw"][tag],
                                     train["cell"], long_min, short_min)
        keep = np.flatnonzero(ev_tr)
        ce = train["cell"][keep]
        probe_col = train["vw"][tag][keep]
        null = []
        for _ in range(n_draw):
            w = np.full(len(keep), False)
            for g in _cell_groups(ce):
                if len(g) >= 2:
                    w[int(rng.choice(g))] = True
            a, used = within_cell_auc(probe_col, w, ce)
            if used:
                null.append(a)
        entry["null_auc_p975"] = float(np.quantile(null, 0.975)) if null else None

        tr, th = aucs.get("train", {}), aucs.get("threshold", {})
        survivors = []
        for name, a in tr.items():
            if name.startswith("__") or not np.isfinite(a):
                continue
            b = th.get(name)
            if b is None or not np.isfinite(b):
                continue
            if (a >= SURVIVE_AUC and b >= SURVIVE_AUC) or \
               (a <= 1 - SURVIVE_AUC and b <= 1 - SURVIVE_AUC):
                survivors.append({"column": name, "train_auc": a, "threshold_auc": b,
                                  "forward_auc": aucs.get("forward", {}).get(name),
                                  "clock_family": bool(CLOCK_RE.search(name))})
        survivors.sort(key=lambda r: -abs(r["train_auc"] - 0.5))
        entry["n_columns_scanned"] = len([k for k in tr if not k.startswith("__")])
        entry["event_rows_train"] = tr.get("__rows__")
        entry["event_cells_train"] = tr.get("__cells__")
        entry["survivors"] = survivors[:40]
        entry["n_survivors"] = len(survivors)
        entry["n_survivors_non_clock"] = sum(1 for r in survivors if not r["clock_family"])
        entry["letter"] = ("no_column_separates" if not entry["n_survivors_non_clock"]
                           else "column_candidates_found")
        log(f"{asset:4s} scanned {entry['n_columns_scanned']} cols on "
            f"{tr.get('__rows__', 0):.0f} event rows / {tr.get('__cells__', 0):.0f} cells | "
            f"survivors {entry['n_survivors']} ({entry['n_survivors_non_clock']} non-clock) | "
            f"null975 {entry['null_auc_p975']} | {entry['letter']}")
        for r in survivors[:8]:
            log(f"      {r['column'][:56]:56s} train {r['train_auc']:.3f} "
                f"thr {r['threshold_auc']:.3f} fwd {r['forward_auc']}"
                f"{' [clock]' if r['clock_family'] else ''}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=1, sort_keys=True))
    return report


def selftest() -> int:
    # AUC on a planted separation, and its mirror.
    cell = np.array([1, 1, 1, 2, 2, 2])
    winner = np.array([True, False, False, True, False, False])
    perfect = np.array([9.0, 1.0, 2.0, 8.0, 0.0, 3.0])
    a, used = within_cell_auc(perfect, winner, cell)
    assert abs(a - 1.0) < 1e-9 and used == 2, (a, used)
    a, _ = within_cell_auc(-perfect, winner, cell)
    assert abs(a - 0.0) < 1e-9, a
    a, _ = within_cell_auc(np.ones(6), winner, cell)
    assert abs(a - 0.5) < 1e-9, a
    # A cell with no loser contributes nothing rather than a spurious 1.0.
    a, used = within_cell_auc(np.array([5.0]), np.array([True]), np.array([3]))
    assert used == 0 and not np.isfinite(a), (a, used)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _plant(tmp / "p")
        rep = run(tmp / "p", tmp / "p.json",
                  blocks={"train": (20210610, 20210709)}, n_draw=4,
                  log=lambda *_: None)
        hg = rep["assets"]["HG"]
        assert hg["n_columns_scanned"] > 0, hg
        assert hg["letter"] in ("no_column_separates", "column_candidates_found"), hg
    print("selftest OK: within-cell AUC is 1.0 / 0.0 / 0.5 on planted separations, "
          "single-class cells are skipped, the scan runs end to end")
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
