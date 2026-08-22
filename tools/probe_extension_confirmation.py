#!/usr/bin/env python3
"""Extension x confirmation probe — the crux after 2026-08-22 ~14:35Z (JOURNAL): the
cell-oracle "most extended candidate" keeps .37-.60 of ceiling but its causal form fails,
so the decisive question is whether CONFIRMATION ACCRUAL tells the phase's final extreme
from the premature extended candidates, at decision time.

PREREGISTRATION (written before the real run; echoed into the receipt):
- Eligibility: a candidate is EXTENDED at Delta iff ext >= theta_asset(q), ext as in
  probe_extension_prior (beyond the prior-session range on the fade side); theta = the
  q-quantile of ext over TRAIN-block candidates; q in Q_ARMS reported as separate arms,
  never chosen on threshold/forward.
- Confirmation composite: unit-weight mean of z-scored, side-resolved, sign-oriented state
  ingredients (probe_confirmation_accrual SCORE_DEFS = v1, no data-driven selection; the
  V1+V2 union as a second arm, flagged: v2 members were ranked on all days), z by TRAIN
  statistics only. No fitted weights (D6 loop: fitted models lose to unit weights).
- Frame A (ranking among the extended): per (asset, Delta, q), within-cell pairwise AUC of
  the composite between extended WINNER series (series-best >= $600) and extended LOSER
  series (series-best <= $0); day bootstrap CI; within-cell permutation null (N_NULL).
  Reported beside the unrestricted AUC (all candidates) so the conditioning effect is visible.
- Frame B (causal walk): candidates decided in decision-time order; enter the first
  EXTENDED candidate whose composite at Delta >= s_asset; s = the quantile of train-block
  composites chosen on TRAIN only (grid S_GRID) by train capture; one position per asset;
  ≤1 entry per cell. Nulls: FIRST_EXTENDED (s=-inf — the causal rule that failed; the
  composite must beat it) and RANDOM cell-wide picks (N_RANDOM). Reference: cell ORACLE.
  Per (asset, block, Delta, q): capture of the matrix ceiling, $/asset-day, day-bootstrap
  CI; CLEARS iff the CI's 2.5th percentile exceeds BOTH nulls' 97.5th percentiles.
- Delta grid {60, 120, 180, 240, 290} (the composite needs time to accrue; Delta=0 is the
  measured-dead formation second). Blocks TRAIN / THRESHOLD / FORWARD.
- Tier: DIAGNOSTIC (cell-pick dollars, not replay). A CLEARS verdict on THRESHOLD and
  FORWARD is the first causal decision-time signal of this program; a failure closes
  "extension x current-ingredient confirmation" for the sequential-threshold shape, scoped
  to these ingredients and the 300 s window.

Selftest: python3 tools/probe_extension_confirmation.py --selftest
Real:     python3 tools/probe_extension_confirmation.py --matrix-dir <round_0/component_matrix> --out <json>
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import probe_confirmation_accrual as ACC  # noqa: E402
from probe_extension_causal import _capture, causal_walk  # noqa: E402
from probe_extension_prior import HIGH_COL, LOW_COL, SIDE_COL, extension_columns  # noqa: E402
from probe_trained_accrual import (  # noqa: E402
    ELAPSED_COL, DeltaRows, ProbeRefusal, _ceiling_by_day, _cell_pick, load_delta_rows,
)

DELTAS = (60.0, 120.0, 180.0, 240.0, 290.0)
BLOCKS = {"train": (20210610, 20210709), "threshold": (20210721, 20210806),
          "forward": (20210809, 20210826)}
Q_ARMS = (0.5, 0.8)
S_GRID = (0.0, 0.3, 0.5, 0.6, 0.7, 0.8, 0.9)
N_RANDOM, N_BOOT, N_NULL = 100, 200, 100
WINNER_MIN_USD, LOSER_MAX_USD = 600.0, 0.0


def side_resolved_composite(rows: DeltaRows, defs: dict, train_mask: np.ndarray) -> np.ndarray:
    """Unit-weight mean of train-z-scored, side-resolved, sign-oriented ingredients."""
    resolved, _missing = ACC.resolve_ingredients(rows.feature_names, defs)
    side = rows.x[:, rows.feature_names.index(SIDE_COL)].astype(np.float64)
    cols = []
    for items in resolved.values():
        for lc, sc, sign in items:
            v = np.where(side > 0, rows.x[:, lc], rows.x[:, sc]).astype(np.float64) * sign
            mu, sd = np.nanmean(v[train_mask]), np.nanstd(v[train_mask])
            cols.append((v - mu) / (sd if sd > 0 else 1.0))
    if not cols:
        raise ProbeRefusal("composite has no resolved ingredients")
    return np.nanmean(np.column_stack(cols), axis=1)


def frame_a(rows: DeltaRows, idx: np.ndarray, score: np.ndarray, extended: np.ndarray,
            rng: np.random.Generator, n_boot: int, n_null: int) -> dict:
    best = rows.series_best[rows.series[idx]]
    is_win, is_lose = best >= WINNER_MIN_USD, best <= LOSER_MAX_USD
    out = {}
    for label, keep in (("extended", extended & (is_win | is_lose)), ("all", is_win | is_lose)):
        el = idx[keep]; w = is_win[keep]
        if not len(el) or not w.any() or w.all():
            out[label] = None; continue
        per = ACC.pairwise_auc_by_day(score[el], w, rows.day[el], rows.cell[el])
        if not per:
            out[label] = None; continue
        auc = ACC.pooled_auc(per); days = list(per)
        boots = [ACC.pooled_auc(per, list(rng.choice(days, len(days)))) for _ in range(n_boot)]
        nulls = []
        cell = rows.cell[el]
        for _ in range(n_null):
            perm = np.empty_like(w); ordc = np.argsort(cell, kind="stable")
            ordp = np.lexsort((rng.random(len(el)), cell)); perm[ordp] = w[ordc]
            nulls.append(ACC.pooled_auc(ACC.pairwise_auc_by_day(score[el], perm, rows.day[el], cell)))
        out[label] = {"auc": round(float(auc), 4),
                      "ci95": [round(float(np.nanpercentile(boots, 2.5)), 4), round(float(np.nanpercentile(boots, 97.5)), 4)],
                      "null95_top": round(float(np.nanpercentile(nulls, 97.5)), 4),
                      "n_pairs": int(sum(v[1] for v in per.values())), "n_days": len(per),
                      "separates": bool(np.nanpercentile(boots, 2.5) > np.nanpercentile(nulls, 97.5))}
    return out


def _walk_capture(rows, idx, gate_score, threshold, ceiling):
    """Causal walk on a gated score (indexed like `idx`): candidates below `threshold` never fire."""
    full = np.full(len(rows.y), -np.inf); full[idx] = gate_score   # causal_walk indexes the full plane
    res = causal_walk(rows, idx, full, theta=threshold, runmax_margin=None)
    r, c = _capture(rows, res, ceiling)
    return float(r.sum() / c.sum()), r, c, res


def run(matrix_dir: Path, out_path: Path, *, defs_arms: dict | None = None, blocks=BLOCKS,
        deltas=DELTAS, q_arms=Q_ARMS, n_random: int = N_RANDOM, n_boot: int = N_BOOT,
        n_null: int = N_NULL, seed: int = 20260822, log=print) -> dict:
    rows = load_delta_rows(matrix_dir, deltas=deltas)
    ext, _ = extension_columns(rows)
    tr_lo, tr_hi = blocks["train"]
    train_all = (rows.day >= tr_lo) & (rows.day <= tr_hi)
    if defs_arms is None:
        defs_arms = {"V1": ACC.SCORE_DEFS, "V1V2": {**ACC.SCORE_DEFS, **ACC.SCORE_DEFS_V2}}
    composites = {name: side_resolved_composite(rows, defs, train_all) for name, defs in defs_arms.items()}
    rows.x = np.empty((0, 0), np.float32)
    rng = np.random.default_rng(seed)
    report = {"schema": "QRE2EXTCONFIRM1", "prereg": __doc__.split("Selftest:")[0],
              "matrix_receipt": rows.matrix_receipt, "deltas_sec": list(deltas), "blocks": dict(blocks),
              "q_arms": list(q_arms), "s_grid": list(S_GRID), "composite_arms": list(defs_arms),
              "n_random": n_random, "n_boot": n_boot, "n_null": n_null, "assets": {}}
    for a in sorted(set(rows.asset)):
        report["assets"][a] = {}
        train_mask = train_all & (rows.asset == a)
        for d in deltas:
            idx_tr = np.flatnonzero(train_mask & (rows.delta == d))
            e_tr = ext[idx_tr]; e_tr = e_tr[np.isfinite(e_tr)]
            for q in q_arms:
                theta = float(np.quantile(e_tr, q))
                for cname, comp in composites.items():
                    key = f"d{int(d)}_q{q}_{cname}"
                    # s on TRAIN only: gate = composite where extended, -inf otherwise
                    ceiling_tr = _ceiling_by_day(rows, train_mask)
                    gate_tr = np.where(ext[idx_tr] >= theta, comp[idx_tr], -np.inf)
                    finite = gate_tr[np.isfinite(gate_tr)]
                    best_s, best_cap = -np.inf, -np.inf
                    for sq in S_GRID:
                        s_val = float(np.quantile(finite, sq)) if len(finite) else -np.inf
                        cap, *_ = _walk_capture(rows, idx_tr, gate_tr, s_val, ceiling_tr)
                        if cap > best_cap:
                            best_s, best_cap, best_sq = s_val, cap, sq
                    entry = {"theta_usd": round(theta, 2), "s": round(best_s, 4), "s_q": best_sq, "blocks": {}}
                    for bname, (lo, hi) in blocks.items():
                        block = (rows.asset == a) & (rows.day >= lo) & (rows.day <= hi)
                        idx = np.flatnonzero(block & (rows.delta == d))
                        if not len(idx):
                            raise ProbeRefusal(f"{a} {bname}: no rows at Delta={d}")
                        ceiling = _ceiling_by_day(rows, block)
                        extended = ext[idx] >= theta
                        gate = np.where(extended, comp[idx], -np.inf)
                        b = {"frame_a": frame_a(rows, idx, comp, extended, rng, n_boot, n_null)}
                        rand = []
                        for _ in range(n_random):
                            pick = _cell_pick(rng.random(len(idx)), rows.y[idx], rows.cell[idx], rows.day[idx],
                                              rows.elapsed[idx], rows.occupancy[idx], -np.inf)
                            r, c = _capture(rows, {"realized": pick["all"]}, ceiling); rand.append(float(r.sum() / c.sum()))
                        cap_fe, r_fe, c_fe, res_fe = _walk_capture(rows, idx, gate, -np.inf, ceiling)
                        boots_fe = [r_fe[bb].sum() / c_fe[bb].sum() for bb in (rng.integers(0, len(r_fe), len(r_fe)) for _ in range(n_boot)) if c_fe[bb].sum() > 0]
                        cap, r, c, res = _walk_capture(rows, idx, gate, best_s, ceiling)
                        boots = [r[bb].sum() / c[bb].sum() for bb in (rng.integers(0, len(r), len(r)) for _ in range(n_boot)) if c[bb].sum() > 0]
                        pick = _cell_pick(np.nan_to_num(ext[idx], nan=-np.inf), rows.y[idx], rows.cell[idx], rows.day[idx],
                                          rows.elapsed[idx], rows.occupancy[idx], -np.inf)
                        r_o, c_o = _capture(rows, {"realized": pick["all"]}, ceiling)
                        null_top = max(float(np.percentile(rand, 97.5)), float(np.nanpercentile(boots_fe, 97.5)))
                        lo_ci = float(np.nanpercentile(boots, 2.5))
                        b["frame_b"] = {"CONFIRMED": {"capture": round(cap, 4), "capture_ci95": [round(lo_ci, 4), round(float(np.nanpercentile(boots, 97.5)), 4)],
                                                      "usd_per_asset_day": round(float(r.mean()), 2), "cells_entered": res["entered"],
                                                      "cells_skipped": res["skipped"], "seen_before_fire_mean": res["seen_before_fire_mean"],
                                                      "clears_both_nulls": bool(lo_ci > null_top)},
                                        "FIRST_EXTENDED": {"capture": round(cap_fe, 4), "capture_p97_5": round(float(np.nanpercentile(boots_fe, 97.5)), 4)},
                                        "RANDOM": {"capture_mean": round(float(np.mean(rand)), 4), "capture_p97_5": round(float(np.percentile(rand, 97.5)), 4)},
                                        "ORACLE": {"capture": round(float(r_o.sum() / c_o.sum()), 4)}}
                        entry["blocks"][bname] = b
                        fa = b["frame_a"]["extended"]; fa_all = b["frame_a"]["all"]
                        log(f"{a} {bname} {key}: AUC ext={fa and fa['auc']}{'*' if fa and fa['separates'] else ''} all={fa_all and fa_all['auc']} | "
                            f"walk CONFIRMED={cap:+.3f}{'*' if b['frame_b']['CONFIRMED']['clears_both_nulls'] else ''} first_ext={cap_fe:+.3f} "
                            f"random={np.mean(rand):+.3f} oracle={r_o.sum()/c_o.sum():+.3f} entered/skipped={res['entered']}/{res['skipped']}")
                    report["assets"][a][key] = entry
            out_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = out_path.with_suffix(".json.partial"); tmp.write_text(json.dumps(report, indent=1)); tmp.replace(out_path)
    return report


# ----------------------------------------------------------------------------- selftest
SELF_DEFS = {"REP": [("syn_rebuild_long", +1), ("syn_rebuild_long_b", +1), ("syn_rebuild_long_c", +1)]}


def _synthetic(root: Path, *, signal: bool, seed: int = 5, n_days: int = 12, n_series: int = 14,
               missing_ingredients: bool = False) -> None:
    rng = np.random.default_rng(seed)
    ing = ["syn_rebuild_long", "syn_rebuild_long_b", "syn_rebuild_long_c"]
    names = ["min_alert_age_sec", "phase_index", ELAPSED_COL, SIDE_COL, LOW_COL, HIGH_COL] + \
            (ing if not missing_ingredients else ["other_a", "other_b", "other_c"])
    ages = np.array([0, 60, 120, 180, 240, 290], float)
    X, day, asset, series, y, occ = [], [], [], [], [], []
    sid = 0
    for d in range(1, n_days + 1):
        for phase in range(3):
            winner = rng.integers(0, n_series)          # one final extreme per cell
            for k in range(n_series):
                side = rng.choice([-1.0, 1.0]); ext = abs(rng.normal(200, 150))   # all extended-ish
                is_win = (k == winner)
                base = (900.0 if is_win else -250.0) if signal else rng.normal(0, 100)
                low_al = -ext if side > 0 else rng.normal(0, 300); high_al = -ext if side < 0 else rng.normal(0, 300)
                for a in ages:
                    f = rng.normal(size=3) + ((2.0 * a / 290.0) if (signal and is_win) else 0.0)
                    X.append([a, phase, phase * 7200 + 600 + 10 * k + a, side, low_al, high_al, *f])
                    day.append(20210600 + d); asset.append("HG"); series.append(f"s{sid}")
                    y.append(base + rng.normal(0, 40)); occ.append(300.0)
                sid += 1
    root.mkdir(parents=True, exist_ok=True)
    np.save(root / "x.npy", np.asarray(X, np.float32)); np.save(root / "day.npy", np.asarray(day, np.int64))
    np.save(root / "asset.npy", np.asarray(asset)); np.save(root / "series_id.npy", np.asarray(series))
    np.save(root / "current_asinh.npy", np.arcsinh(np.asarray(y) / 600.0)); np.save(root / "occupancy_sec.npy", np.asarray(occ))
    (root / "manifest.json").write_text(json.dumps({"feature_names": names, "rows": len(X), "matrix_receipt_sha256": "synthetic"}))


def selftest() -> int:
    blocks = {"train": (20210601, 20210606), "threshold": (20210607, 20210609), "forward": (20210610, 20210612)}
    kw = dict(defs_arms={"SYN": SELF_DEFS}, blocks=blocks, deltas=(60.0, 290.0), q_arms=(0.5,),
              n_random=20, n_boot=20, n_null=20, log=lambda *_: None)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _synthetic(tmp / "sig", signal=True)
        rep = run(tmp / "sig", tmp / "sig.json", **kw)
        e = rep["assets"]["HG"]["d290_q0.5_SYN"]["blocks"]["forward"]
        assert e["frame_a"]["extended"]["separates"], f"planted accrual among extended not separated: {e['frame_a']}"
        assert e["frame_b"]["CONFIRMED"]["clears_both_nulls"], f"causal confirmed walk did not clear the nulls: {e['frame_b']}"
        _synthetic(tmp / "nosig", signal=False, seed=9)
        rep = run(tmp / "nosig", tmp / "nosig.json", **kw)
        e2 = rep["assets"]["HG"]["d290_q0.5_SYN"]["blocks"]["forward"]
        assert not e2["frame_b"]["CONFIRMED"]["clears_both_nulls"], f"no-signal fixture cleared: {e2['frame_b']}"
        _synthetic(tmp / "red", signal=True, missing_ingredients=True)
        try:
            run(tmp / "red", tmp / "red.json", **kw)
        except (ProbeRefusal, ACC.AccrualRefusal):
            pass
        else:
            raise AssertionError("red fixture (ingredients absent) was accepted")
    print(f"selftest OK: planted extended-AUC {e['frame_a']['extended']['auc']:.3f} separates; causal CONFIRMED "
          f"{e['frame_b']['CONFIRMED']['capture']:.3f} > first-extended {e['frame_b']['FIRST_EXTENDED']['capture']:.3f}; "
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
