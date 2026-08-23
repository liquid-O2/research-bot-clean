#!/usr/bin/env python3
"""Location-extension ranker over new-extreme events — ticket 39 (2026-08-23).

Ticket 36 found the family; ticket 35 Stage 5 cashed its members one at a time,
TRAIN-selected, and reached 61% capture on SI against the 63% its rung needs.
Each member is a near-duplicate of one geometry: how far beyond a FIXED level
the price sits, on the side the reversal fades. This probe asks the geometry
question properly instead of ranking one column at a time.

The level universe is enumerated FROM the matrix (`*_aligned_usd`), never
hardcoded, and each asset is scored on ITS own surviving levels. Borrowing NKD's
columns into HG is exactly what made LOC_DAWES worse than its parts.

ARMS, all live-legal, one entry per phase, every entry at DELTA_SEC of age so
the cash stays exactly labelled:
  BEST_SINGLE     the one level with the best TRAIN separation
  MAX_BEYOND      deepest extension across levels (most negative aligned)
  COUNT_CLEARED   how many levels the price has cleared on the fade side
  NEAREST_BEYOND  among cleared levels, the one just cleared (smallest |aligned|)
  LOC_Z           unit-weight mean of within-(cell, side) z-scores of -aligned,
                  over the asset's surviving levels
  LOC_Z_ALL       the same over all levels, with no selection at all

PREREGISTRATION (written before the run):
- Survivor selection is TRAIN-only: a level survives at within-cell AUC >= 0.60
  or <= 0.40 on TRAIN events, and enters the composite with the sign TRAIN gives
  it. No held block touches selection.
- Null for every arm: shuffle the SCORE that defines the events within the cell,
  which destroys both which names are events and their ranking, keeping
  formation order and y.
- Rung letters carry the noise floor (RESOLVE_SE = 2): a margin under two
  standard errors of the block's own per-day spread letters *_not_resolved.
- THE FREEZE. The TRAIN winner is written to the receipt BEFORE any held block
  is read, and exactly one arm is read on THRESHOLD and FORWARD. Reading the
  held blocks for every arm and then picking is the eval-selected-knobs defect.
- 2021 cannot promote.

Selftest: python3 tools/probe_location_ranker.py --selftest
Real:     OMP_NUM_THREADS=1 python3 tools/probe_location_ranker.py \
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

from probe_event_column_scan import within_cell_auc  # noqa: E402
from probe_extreme_events import (  # noqa: E402
    _best_by_score_per_cell, extreme_events,
)
from probe_hold_running_extreme import (  # noqa: E402
    N_DRAW, PHASE_VWAP_COL, SHUFFLE_Q, _cash_flag, _cash_stats, _cell_groups,
    _entries_per_day, _plant, _rung_letter, _stage_a,
)
from probe_location_family_screen import _col  # noqa: E402
from probe_path_dedup import _formation_sec  # noqa: E402
from probe_path_dedup_live import DELTA_SEC, FORM_DELTA, SIDE_COL, VWAP_COL  # noqa: E402
from probe_rho_on_dedup import WIDTH_MULT, _keep_idx  # noqa: E402
from probe_rho_ruler import BLOCKS, RUNG_USD  # noqa: E402
from probe_trained_accrual import ProbeRefusal, load_delta_rows  # noqa: E402

SCHEMA = "QRE2LOCRANKER1"
LEVEL_SUFFIX = "_aligned_usd"
SURVIVE_AUC = 0.60
# Abstention quantiles over the frozen arm's picks. 0.0 keeps every cell.
ABSTAIN_GRID = (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6)
SCORE_COLS = (("session", VWAP_COL), ("phase", PHASE_VWAP_COL))


def level_columns(names: list[str]) -> list[str]:
    """Every fixed-level distance on the matrix, enumerated not hardcoded.

    The two VWAP columns are excluded: they define which names are events, so
    scoring events by them would rank on the same quantity that selected them.
    """
    return sorted(n for n in names
                  if n.endswith(LEVEL_SUFFIX) and n not in (VWAP_COL, PHASE_VWAP_COL))


def zscore_within(v: np.ndarray, key: np.ndarray) -> np.ndarray:
    """Standardise inside each key group (cell, or cell x side)."""
    out = np.full(len(v), np.nan)
    order = np.argsort(key, kind="stable")
    k = key[order]
    for g in np.split(order, np.flatnonzero(np.diff(k)) + 1):
        x = v[g]
        m = np.isfinite(x)
        if m.sum() < 2:
            continue
        sd = float(np.std(x[m]))
        out[g] = (x - float(np.mean(x[m]))) / sd if sd > 0 else 0.0
    return out


def build_scores(lev: np.ndarray, survivors: list[int], signs: np.ndarray,
                 cell: np.ndarray, side: np.ndarray) -> dict[str, np.ndarray]:
    """Every arm's ranking score. Higher is always "more likely the payer".

    `lev` is (rows, levels) of aligned distances. Aligned < 0 means the price is
    beyond that level on the side the trade fades, so -aligned is depth beyond.
    """
    beyond = -lev
    cs = cell.astype(np.int64) * 4 + (side > 0).astype(np.int64)
    scores: dict[str, np.ndarray] = {}
    with np.errstate(invalid="ignore"):
        scores["MAX_BEYOND"] = np.nanmax(beyond, axis=1)
        scores["COUNT_CLEARED"] = np.nansum(beyond > 0, axis=1).astype(np.float64)
        # Levels not cleared become +inf, so a name that cleared nothing scores
        # -inf and ranks last rather than first.
        nearest = np.min(np.where(beyond > 0, beyond, np.inf), axis=1)
        scores["NEAREST_BEYOND"] = -nearest
        allz = [zscore_within(beyond[:, j], cs) for j in range(lev.shape[1])]
        scores["LOC_Z_ALL"] = np.nanmean(np.vstack(allz), axis=0) if allz else np.zeros(len(lev))
        if survivors:
            sz = [signs[j] * zscore_within(beyond[:, j], cs) for j in survivors]
            scores["LOC_Z"] = np.nanmean(np.vstack(sz), axis=0)
            scores["BEST_SINGLE"] = signs[survivors[0]] * beyond[:, survivors[0]]
    return scores


def _select_survivors(lev: np.ndarray, cols: list[str], y: np.ndarray,
                      is_event: np.ndarray, cell: np.ndarray,
                      ) -> tuple[list[int], np.ndarray, list[dict]]:
    """TRAIN-only. A level survives on within-cell AUC against the best event."""
    keep = np.flatnonzero(is_event)
    ce, ye = cell[keep], y[keep]
    winner = np.full(len(keep), False)
    multi = np.full(len(keep), False)
    for g in _cell_groups(ce):
        if len(g) < 2:
            continue
        multi[g] = True
        winner[int(g[int(np.argmax(ye[g]))])] = True
    ce, winner = ce[multi], winner[multi]
    table, signs = [], np.zeros(lev.shape[1])
    for j, name in enumerate(cols):
        auc, used = within_cell_auc((-lev[keep])[multi][:, j], winner, ce)
        if not used or not np.isfinite(auc):
            continue
        signs[j] = 1.0 if auc >= 0.5 else -1.0
        table.append({"level": name, "index": j, "train_auc": auc,
                      "survives": bool(auc >= SURVIVE_AUC or auc <= 1 - SURVIVE_AUC)})
    table.sort(key=lambda r: -abs(r["train_auc"] - 0.5))
    return [r["index"] for r in table if r["survives"]], signs, table


def run(matrix_dir: Path, out_path: Path, *, blocks=BLOCKS, n_draw: int = N_DRAW,
        log=print) -> dict:
    rows180 = load_delta_rows(matrix_dir, deltas=(DELTA_SEC,))
    rows0 = load_delta_rows(matrix_dir, deltas=(FORM_DELTA,))
    if not np.isfinite(rows180.y).all():
        raise ProbeRefusal("non-finite y on the component matrix")
    names = rows180.feature_names
    cols = level_columns(names)
    if not cols:
        raise ProbeRefusal(f"no {LEVEL_SUFFIX} columns on the matrix")
    rng = np.random.default_rng(20260823)
    report: dict = {"schema": SCHEMA, "prereg": __doc__,
                    "matrix_receipt": rows180.matrix_receipt,
                    "n_level_columns": len(cols), "level_columns": cols,
                    "survive_auc": SURVIVE_AUC, "assets": {}}

    for asset in sorted(set(rows180.asset.tolist())):
        if asset not in WIDTH_MULT:
            continue
        rung = RUNG_USD[asset]
        entry: dict = {"rung_usd": rung}
        report["assets"][asset] = entry
        packed = {}
        for bname, (lo, hi) in blocks.items():
            idx = np.flatnonzero((rows180.asset == asset) & (rows180.day >= lo)
                                 & (rows180.day <= hi) & (rows180.delta == DELTA_SEC))
            if len(idx) == 0:
                continue
            kept = _keep_idx(rows180, rows0, idx, asset)
            packed[bname] = dict(
                y=rows180.y[kept], cell=rows180.cell[kept], day=rows180.day[kept],
                elapsed=rows180.elapsed[kept], occupancy=rows180.occupancy[kept],
                side=rows180.x[kept, _col(names, SIDE_COL)].astype(np.float64),
                formed=_formation_sec(rows180.x[kept], names),
                lev=np.column_stack([rows180.x[kept, _col(names, c)].astype(np.float64)
                                     for c in cols]),
                days=sorted({int(d) for d in rows180.day[kept]}),
                vw={t: rows180.x[kept, _col(names, c)].astype(np.float64)
                    for t, c in SCORE_COLS})
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
        tag, a_blk = best
        long_min = a_blk["best_orientation"].startswith("long_min")
        short_min = a_blk["best_orientation"].endswith("short_min")
        entry.update(chosen_score=tag, orientation=a_blk["best_orientation"])

        ev, _, _ = extreme_events(train["formed"], train["side"], train["vw"][tag],
                                  train["cell"], long_min, short_min)
        survivors, signs, table = _select_survivors(train["lev"], cols, train["y"],
                                                    ev, train["cell"])
        entry["levels_used"] = [cols[j] for j in survivors]
        entry["level_auc_table"] = table[:12]
        oracle = _cash_stats(_oracle_flag(ev, train["y"], train["cell"]), train["y"],
                             train["cell"], train["day"], train["elapsed"],
                             train["occupancy"], train["days"])
        entry["event_oracle"] = oracle
        log(f"{asset:4s} levels {len(cols)} surviving {len(survivors)} | oracle "
            f"${oracle['usd_per_asset_day']:.0f} | top level "
            f"{table[0]['level'] if table else 'none'} auc "
            f"{table[0]['train_auc'] if table else float('nan'):.3f}")

        def arms_for(pack, ev_):
            return build_scores(pack["lev"], survivors, signs, pack["cell"], pack["side"])

        rows = []
        scores = arms_for(train, ev)
        for name, sc in scores.items():
            flag = _best_by_score_per_cell(ev, sc, train["cell"])
            st = _cash_stats(flag, train["y"], train["cell"], train["day"],
                             train["elapsed"], train["occupancy"], train["days"])
            draws = []
            for _ in range(n_draw):
                shuf = train["vw"][tag].copy()
                for g in _cell_groups(train["cell"]):
                    shuf[g] = rng.permutation(shuf[g])
                e2, _, _ = extreme_events(train["formed"], train["side"], shuf,
                                          train["cell"], long_min, short_min)
                nf = _best_by_score_per_cell(e2, sc, train["cell"])
                draws.append(_cash_flag(nf, train["y"], train["cell"], train["day"],
                                        train["elapsed"], train["occupancy"], train["days"]))
            rows.append({"arm": name, **st,
                         "null_mean_usd": float(np.mean(draws)),
                         "null_p975_usd": float(np.quantile(draws, SHUFFLE_Q)),
                         "capture": (st["usd_per_asset_day"] / oracle["usd_per_asset_day"]
                                     if oracle["usd_per_asset_day"] else None),
                         "letter": _rung_letter(st["usd_per_asset_day"], st["usd_se"],
                                                rung, "loc"),
                         **_entries_per_day(flag, train["day"], train["days"])})
            log(f"{asset:4s} arm {name:15s} ${st['usd_per_asset_day']:7.0f} "
                f"se ${st['usd_se']:5.0f} null975 ${rows[-1]['null_p975_usd']:6.0f} "
                f"capture {100 * (rows[-1]['capture'] or 0):4.0f}% ent/d "
                f"{rows[-1]['entries_per_day_max']}")
        rows.sort(key=lambda r: -r["usd_per_asset_day"])
        entry["train_arms"] = rows

        # THE FREEZE — written before any held block is read. An arm whose TRAIN
        # cash sits inside its own TRAIN null is not a candidate at all: picking
        # the highest cash without that filter froze HG on an arm that was
        # already indistinguishable from shuffling, which is the gate-not-goal
        # defect applied to arm selection.
        outside = arms_outside_null(rows)
        entry["n_arms_outside_train_null"] = len(outside)
        if not outside:
            entry["frozen_arm"] = None
            entry["letter"] = "no_arm_outside_train_null"
            entry["frozen_before_held_read"] = True
            log(f"{asset:4s} FROZEN none: every arm sits inside its TRAIN null")
            continue
        entry["frozen_arm"] = outside[0]["arm"]
        entry["frozen_before_held_read"] = True
        entry["top"] = outside[0]
        # Abstention quantile, chosen on TRAIN only, for the frozen arm.
        frozen_sc = scores[entry["frozen_arm"]]
        frozen_flag = _best_by_score_per_cell(ev, frozen_sc, train["cell"])
        q_rows = []
        for q in ABSTAIN_GRID:
            f = abstain_flag(frozen_flag, frozen_sc, train["cell"], train["side"], q)
            st = _cash_stats(f, train["y"], train["cell"], train["day"],
                             train["elapsed"], train["occupancy"], train["days"])
            q_rows.append({"abstain_q": q, **st,
                           **_entries_per_day(f, train["day"], train["days"])})
            log(f"{asset:4s} abstain q={q:.2f} ${st['usd_per_asset_day']:7.0f} "
                f"se ${st['usd_se']:5.0f} ent/d {q_rows[-1]['entries_per_day_max']}")
        peak = max(q_rows, key=lambda r: r["usd_per_asset_day"])
        floor = peak["usd_per_asset_day"] - peak["usd_se"]
        q_star = min((r for r in q_rows if r["usd_per_asset_day"] >= floor),
                     key=lambda r: r["abstain_q"])["abstain_q"]
        entry["abstain_train"] = q_rows
        entry["frozen_abstain_q"] = q_star
        log(f"{asset:4s} FROZEN {entry['frozen_arm']} q={q_star:.2f}")

        for bname, pack in packed.items():
            if bname == "train":
                continue
            ev_b, _, _ = extreme_events(pack["formed"], pack["side"], pack["vw"][tag],
                                        pack["cell"], long_min, short_min)
            sc = arms_for(pack, ev_b)[entry["frozen_arm"]]
            flag = abstain_flag(_best_by_score_per_cell(ev_b, sc, pack["cell"]),
                                sc, pack["cell"], pack["side"], q_star)
            st = _cash_stats(flag, pack["y"], pack["cell"], pack["day"], pack["elapsed"],
                             pack["occupancy"], pack["days"])
            draws = []
            for _ in range(n_draw):
                shuf = pack["vw"][tag].copy()
                for g in _cell_groups(pack["cell"]):
                    shuf[g] = rng.permutation(shuf[g])
                e2, _, _ = extreme_events(pack["formed"], pack["side"], shuf,
                                          pack["cell"], long_min, short_min)
                nf = abstain_flag(_best_by_score_per_cell(e2, sc, pack["cell"]),
                                  sc, pack["cell"], pack["side"], q_star)
                draws.append(_cash_flag(nf, pack["y"], pack["cell"], pack["day"],
                                        pack["elapsed"], pack["occupancy"], pack["days"]))
            entry[bname] = {"arm": entry["frozen_arm"], **st,
                            "null_mean_usd": float(np.mean(draws)),
                            "null_p975_usd": float(np.quantile(draws, SHUFFLE_Q)),
                            "letter": _rung_letter(st["usd_per_asset_day"], st["usd_se"],
                                                   rung, "loc"),
                            **_entries_per_day(flag, pack["day"], pack["days"])}
            log(f"{asset:4s} {bname:10s} [{entry['frozen_arm']}] "
                f"${st['usd_per_asset_day']:7.0f} se ${st['usd_se']:5.0f} "
                f"null975 ${entry[bname]['null_p975_usd']:6.0f} {entry[bname]['letter']}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=1, sort_keys=True))
    return report


def _plant_levels(root: Path) -> None:
    """A matrix whose paying event is the one furthest beyond a level.

    Two days, one phase, seven keep-first longs at distinct VWAP buckets. The
    events are the names that set new VWAP extremes; among them the payer is the
    one with the most negative `disc_prior_high_aligned_usd`, and a second level
    column carries no information at all so survivor selection has something to
    reject.
    """
    from probe_path_dedup import _theta
    from probe_trained_accrual import ELAPSED_COL
    from probe_rho_ruler import PHASE_REMAINING_COL
    theta = _theta("HG")
    names = ["min_alert_age_sec", "phase_index", ELAPSED_COL,
             "disc_fvol_phase_scope_elapsed_sec", PHASE_REMAINING_COL,
             VWAP_COL, PHASE_VWAP_COL, SIDE_COL,
             "disc_prior_high_aligned_usd", "disc_prior_low_aligned_usd"]
    # (y, formed, vwap, prior_high_aligned, prior_low_aligned)
    specs = [
        (50.0, 0.0, -1.0 * theta, 500.0, 10.0),
        (2500.0, 200.0, -8.0 * theta, -900.0, 10.0),   # event, deepest beyond
        (60.0, 100.0, -4.0 * theta, 300.0, 10.0),      # event, not beyond
        (40.0, 300.0, 2.0 * theta, -100.0, 10.0),      # beyond but not an event
        (30.0, 400.0, 4.0 * theta, 200.0, 10.0),
        (20.0, 500.0, 6.0 * theta, 400.0, 10.0),
        (10.0, 600.0, 8.0 * theta, 600.0, 10.0),
    ]
    xs, days, assets, series, ys, occs = [], [], [], [], [], []
    for d in (20210610, 20210611):
        for i, (yv, formed, vwap, hi, lo) in enumerate(specs):
            for age in (0.0, 180.0):
                elapsed = formed + age
                xs.append([age, 0.0, elapsed, elapsed, 100000.0 - elapsed,
                           vwap, vwap, 1.0, hi, lo])
                days.append(d); assets.append("HG"); series.append(f"s{d}_{i}")
                ys.append(yv); occs.append(600.0)
    root.mkdir(parents=True, exist_ok=True)
    yv = np.asarray(ys, np.float64)
    np.save(root / "x.npy", np.asarray(xs, np.float32))
    np.save(root / "day.npy", np.asarray(days, np.int64))
    np.save(root / "asset.npy", np.asarray(assets))
    np.save(root / "series_id.npy", np.asarray(series))
    np.save(root / "current_asinh.npy", np.arcsinh(yv / 600.0))
    np.save(root / "occupancy_sec.npy", np.asarray(occs, np.float64))
    (root / "manifest.json").write_text(json.dumps(
        {"feature_names": names, "rows": len(xs), "matrix_receipt_sha256": "synthetic"}))


def arms_outside_null(rows: list[dict]) -> list[dict]:
    """Arms whose TRAIN cash beats their own TRAIN null, richest first.

    An arm inside its null is indistinguishable from shuffling, so it is not a
    candidate at all. Freezing on cash alone put HG on exactly such an arm
    ($1,740 against a $2,307 null) and then read the held blocks on it.
    """
    keep = [r for r in rows if r["usd_per_asset_day"] > r["null_p975_usd"]]
    return sorted(keep, key=lambda r: -r["usd_per_asset_day"])


def abstain_flag(flag: np.ndarray, score: np.ndarray, cell: np.ndarray,
                 side: np.ndarray, q: float) -> np.ndarray:
    """Keep only the picks whose within-(cell, side) z-score clears a quantile.

    Every arm so far enters EVERY cell. A day's cash is the sum over its cells,
    so passing on a cell whose best candidate looks weak raises the total when
    those cells lose, and it spends fewer of the 12 portfolio-day trades.
    """
    if q <= 0.0:
        return flag
    z = zscore_within(score, cell.astype(np.int64) * 4 + (side > 0).astype(np.int64))
    picked = np.flatnonzero(flag)
    if not len(picked):
        return flag
    vals = z[picked]
    finite = vals[np.isfinite(vals)]
    if not len(finite):
        return flag
    cut = float(np.quantile(finite, q))
    out = np.full(len(flag), False)
    out[picked[np.isfinite(vals) & (vals >= cut)]] = True
    return out


def _oracle_flag(is_event: np.ndarray, y: np.ndarray, cell: np.ndarray) -> np.ndarray:
    out = np.full(len(is_event), False)
    for g in _cell_groups(cell):
        gi = g[is_event[g]]
        if len(gi):
            out[int(gi[int(np.argmax(y[gi]))])] = True
    return out


def selftest() -> int:
    names = ["a_aligned_usd", "b_aligned_usd", VWAP_COL, PHASE_VWAP_COL, "other"]
    assert level_columns(names) == ["a_aligned_usd", "b_aligned_usd"], level_columns(names)

    z = zscore_within(np.array([1.0, 3.0, 5.0, 15.0]), np.array([1, 1, 2, 2]))
    assert abs(z[0] + 1.0) < 1e-9 and abs(z[1] - 1.0) < 1e-9, z

    # Arm geometry on a planted cell. Rows: cleared depths per level.
    lev = np.array([[-30.0, -10.0],    # cleared both, deepest 30, nearest 10
                    [-5.0, 20.0],      # cleared one, depth 5
                    [40.0, 50.0]])     # cleared nothing
    cell = np.array([1, 1, 1])
    side = np.ones(3)
    sc = build_scores(lev, [0], np.array([1.0, 1.0]), cell, side)
    assert sc["MAX_BEYOND"].tolist() == [30.0, 5.0, -40.0], sc["MAX_BEYOND"]
    assert sc["COUNT_CLEARED"].tolist() == [2.0, 1.0, 0.0], sc["COUNT_CLEARED"]
    assert sc["NEAREST_BEYOND"][0] == -10.0 and sc["NEAREST_BEYOND"][1] == -5.0, \
        sc["NEAREST_BEYOND"]
    assert sc["NEAREST_BEYOND"][2] == -np.inf, "a name that cleared nothing ranks last"
    assert sc["BEST_SINGLE"].tolist() == [30.0, 5.0, -40.0], sc["BEST_SINGLE"]
    # A negative TRAIN sign must flip the level's contribution, in BEST_SINGLE
    # and inside the LOC_Z composite.
    flipped = build_scores(lev, [0], np.array([-1.0, 1.0]), cell, side)
    assert flipped["BEST_SINGLE"].tolist() == [-30.0, -5.0, 40.0], flipped["BEST_SINGLE"]
    both_plus = build_scores(lev, [0, 1], np.array([1.0, 1.0]), cell, side)["LOC_Z"]
    one_minus = build_scores(lev, [0, 1], np.array([1.0, -1.0]), cell, side)["LOC_Z"]
    assert int(np.argmax(both_plus)) == 0, both_plus
    assert int(np.argmax(one_minus)) != int(np.argmax(both_plus)), (both_plus, one_minus)
    assert not np.allclose(both_plus, one_minus), (both_plus, one_minus)

    # Survivor selection is AUC-driven and keeps the direction TRAIN gives.
    lev2 = np.column_stack([np.array([-9.0, -1.0, -8.0, -2.0]),
                            np.array([1.0, 1.0, 1.0, 1.0])])
    y = np.array([100.0, 1.0, 90.0, 2.0])
    ev = np.array([True, True, True, True])
    cell2 = np.array([1, 1, 2, 2])
    surv, signs, table = _select_survivors(lev2, ["deep", "flat"], y, ev, cell2)
    assert 0 in surv and 1 not in surv, (surv, table)
    assert signs[0] == 1.0, signs

    # The freeze must skip a rich arm that is inside its own null.
    cand = [{"arm": "rich_but_null", "usd_per_asset_day": 1740.0, "null_p975_usd": 2307.0},
            {"arm": "modest_but_real", "usd_per_asset_day": 1000.0, "null_p975_usd": 770.0},
            {"arm": "weak", "usd_per_asset_day": -15.0, "null_p975_usd": 382.0}]
    picked = arms_outside_null(cand)
    assert [r["arm"] for r in picked] == ["modest_but_real"], picked
    assert arms_outside_null([cand[0]]) == [], "no arm outside the null means no freeze"

    # Abstention keeps the strong picks and drops the weak ones, and q=0 is a
    # no-op. A mutant that ignores the quantile keeps everything.
    aflag = np.array([True, True, True, True])
    ascore = np.array([10.0, 1.0, 8.0, 2.0])
    acell = np.array([1, 1, 2, 2])
    aside = np.ones(4)
    assert abstain_flag(aflag, ascore, acell, aside, 0.0).tolist() == [True] * 4
    kept = abstain_flag(aflag, ascore, acell, aside, 0.5)
    assert kept.tolist() == [True, False, True, False], kept
    assert abstain_flag(np.zeros(4, bool), ascore, acell, aside, 0.5).sum() == 0

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _plant_levels(tmp / "p")
        rep = run(tmp / "p", tmp / "p.json", blocks={"train": (20210610, 20210709)},
                  n_draw=4, log=lambda *_: None)
        hg = rep["assets"]["HG"]
        assert rep["n_level_columns"] == 2, rep["n_level_columns"]
        assert hg["frozen_before_held_read"] is True, hg
        # The frozen arm must be OUTSIDE its TRAIN null, not merely the richest.
        frozen = [r for r in hg["train_arms"] if r["arm"] == hg["frozen_arm"]][0]
        assert frozen["usd_per_asset_day"] > frozen["null_p975_usd"], frozen
        assert hg["frozen_abstain_q"] in ABSTAIN_GRID, hg["frozen_abstain_q"]
        # The informative level survives; the constant one cannot.
        assert "disc_prior_high_aligned_usd" in hg["levels_used"], hg["levels_used"]
        assert "disc_prior_low_aligned_usd" not in hg["levels_used"], hg["levels_used"]
        # The planted payer is worth $2,500 a day and the ranker must find it.
        assert abs(hg["train_arms"][0]["usd_per_asset_day"] - 2500.0) < 1.0, \
            hg["train_arms"][0]
        assert abs(hg["event_oracle"]["usd_per_asset_day"] - 2500.0) < 1.0, \
            hg["event_oracle"]
    print("selftest OK: levels enumerated from the matrix, arm geometry exact on a "
          "planted cell, cleared-nothing ranks last, TRAIN signs flip the composite, "
          "survivor selection is AUC-driven, the freeze precedes the held read")
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
