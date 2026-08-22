#!/usr/bin/env python3
"""Confirmation-accrual probe (design/book_confirmations/CONFIRMATION_CATALOG.md Part D).

PREREGISTRATION (written before the real run; echoed into the receipt):
- Question: do the four abstract confirmation states (DEFENSE, REPLENISH, EXHAUST,
  LIFTOFF — user ruling 2026-08-22: continuous scores, no book thresholds) separate
  goal-grade winner series from loser series WITHIN (asset, day, phase), and does that
  separation ACCRUE with time since candidate formation (Delta)?
- Frame: winner series = series-best standalone value >= $600; loser = series-best <= $0
  (the D2 blind-case frame at full population scale). For each series and each Delta
  target in {0, 30, 60, 120, 180, 300}s, use the series' sampled row whose
  min_alert_age_sec is nearest the target within +/-15s.
- Metric: per (asset, score, Delta) pairwise AUC over ALL winner x loser pairs within
  each (asset, day, phase) cell: P(score_winner > score_loser), ties 0.5.
- Null: within-cell winner/loser designation permutation, N_NULL draws -> null AUC band.
- CI: day-level bootstrap (resample days with replacement, N_BOOT draws) on the pooled
  per-asset AUC, and on the DIFFERENCE AUC(300)-AUC(0).
- Preregistered verdict per (asset, score): "ACCRUES" iff the bootstrap 95% CI of
  AUC(300)-AUC(0) lies above 0; "SEPARATES" at Delta iff AUC's CI lies above the null
  95% band top. Anything else: not established. Scores are population-z-scored per
  (asset, Delta) — an IN-SAMPLE normalization; this is a separation diagnostic, not a
  causal deployment rule, and its numbers are diagnostics, never promotable economics.

Selftest: python3 tools/probe_confirmation_accrual.py --selftest   (synthetic; no artifacts)
Real:     python3 tools/probe_confirmation_accrual.py --matrix-dir <component_matrix> \
              --out <receipt.json> [--n-null 100] [--n-boot 200]
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

DELTA_TARGETS_SEC = (0.0, 30.0, 60.0, 120.0, 180.0, 300.0)
DELTA_TOL_SEC = 15.0
WINNER_MIN_USD = 600.0
LOSER_MAX_USD = 0.0
VALUE_SCALE_USD = 600.0

# Ingredient lists per state. Sign +1: larger raw value = more of the state.
# OWN/OPP event families resolve by side at runtime (long: own=lift, opp=attack).
SCORE_DEFS: dict[str, list[tuple[str, float]]] = {
    "DEFENSE": [
        ("disc_level_z0_net_defense_display", +1), ("disc_level_z2_net_defense_display", +1),
        ("disc_level_z4_net_defense_display", +1), ("disc_memory_z0_net_defense_display", +1),
        ("disc_memory_z2_net_defense_display", +1),
        ("disc_level_z0_trade_volume", +1), ("disc_level_z2_trade_volume", +1),
        ("disc_level_z4_trade_volume", +1),
    ],
    "REPLENISH": [
        ("disc_evt_h5_last_reload_age_ms", -1), ("disc_evt_h15_last_reload_age_ms", -1),
        ("disc_evt_h30_last_reload_age_ms", -1),
        ("disc_quote_h30_rebuild_size", +1), ("disc_quote_formation_rebuild_size", +1),
        ("disc_quote_h30_rebuild_after_depletion_mean_latency_ms", -1),
        ("disc_quote_formation_rebuild_after_depletion_mean_latency_ms", -1),
    ],
    "EXHAUST": [
        ("OPP_gap_median_h5", +1), ("OPP_gap_median_h15", +1),
        ("OPP_last_age_h5", +1),
        ("OPP_level_volume", +1),  # had-effort conditioner: they attacked, now fading
        ("disc_tclock_n8_gap_median_ms", +1),
    ],
    "LIFTOFF": [
        ("OWN_last_age_h1", -1), ("OWN_last_age_h5", -1),
        ("w15_aligned_displacement_usd", +1), ("w30_aligned_displacement_usd", +1),
        ("w60_aligned_displacement_usd", +1),
        ("w15_favorable_excursion_usd", +1), ("w60_favorable_excursion_usd", +1),
        ("w15_aligned_trade_flow", +1), ("w60_aligned_trade_flow", +1),
    ],
}
# Side-resolved virtual columns -> (long_name, short_name)
VIRTUAL = {
    "OPP_gap_median_h5": ("disc_evt_h5_attack_gap_median_ms", "disc_evt_h5_lift_gap_median_ms"),
    "OPP_gap_median_h15": ("disc_evt_h15_attack_gap_median_ms", "disc_evt_h15_lift_gap_median_ms"),
    "OPP_last_age_h5": ("disc_evt_h5_last_attack_age_ms", "disc_evt_h5_last_lift_age_ms"),
    "OPP_level_volume": ("disc_level_z2_attack_volume", "disc_level_z2_lift_volume"),
    "OWN_last_age_h1": ("disc_evt_h1_last_lift_age_ms", "disc_evt_h1_last_attack_age_ms"),
    "OWN_last_age_h5": ("disc_evt_h5_last_lift_age_ms", "disc_evt_h5_last_attack_age_ms"),
}


class AccrualRefusal(RuntimeError):
    pass


def resolve_ingredients(names: list[str]) -> tuple[dict[str, list[tuple[int, int, float]]], list[str]]:
    """Per score: list of (long_col, short_col, sign). Missing ingredients are dropped
    (recorded); a score with <3 available ingredients refuses."""
    index = {n: i for i, n in enumerate(names)}
    resolved: dict[str, list[tuple[int, int, float]]] = {}
    missing: list[str] = []
    for score, items in SCORE_DEFS.items():
        rows = []
        for name, sign in items:
            if name in VIRTUAL:
                ln, sn = VIRTUAL[name]
                if ln in index and sn in index:
                    rows.append((index[ln], index[sn], float(sign)))
                else:
                    missing.append(f"{score}:{name}")
            elif name in index:
                rows.append((index[name], index[name], float(sign)))
            else:
                missing.append(f"{score}:{name}")
        if len(rows) < 3:
            raise AccrualRefusal(
                f"score {score} has only {len(rows)} available ingredients "
                f"(needs >=3); missing: {[m for m in missing if m.startswith(score)]}")
        resolved[score] = rows
    return resolved, missing


def compute_scores(x_rows: np.ndarray, side: np.ndarray,
                   resolved: dict[str, list[tuple[int, int, float]]]) -> dict[str, np.ndarray]:
    """x_rows: (n, n_features) float64 for the selected rows. Returns raw (pre-z) scores."""
    out = {}
    long_mask = side > 0
    for score, rows in resolved.items():
        parts = np.full((len(rows), len(x_rows)), np.nan)
        for k, (lc, sc, sign) in enumerate(rows):
            v = np.where(long_mask, x_rows[:, lc], x_rows[:, sc])
            parts[k] = sign * v
        # z per ingredient over this population, then nanmean across ingredients
        mu = np.nanmean(parts, axis=1, keepdims=True)
        sd = np.nanstd(parts, axis=1, keepdims=True)
        sd[sd == 0] = 1.0
        out[score] = np.nanmean((parts - mu) / sd, axis=0)
    out["COMBINED"] = np.nanmean(np.vstack([out[s] for s in SCORE_DEFS]), axis=0)
    return out


def pairwise_auc_by_day(scores: np.ndarray, is_win: np.ndarray, day: np.ndarray,
                        cell: np.ndarray) -> dict[int, tuple[float, float]]:
    """Per day: (sum of pair outcomes, pair count) over within-cell winner x loser pairs."""
    result: dict[int, tuple[float, float]] = {}
    order = np.argsort(cell, kind="stable")
    cell_s, sc_s, win_s, day_s = cell[order], scores[order], is_win[order], day[order]
    boundaries = np.flatnonzero(np.diff(cell_s)) + 1
    for grp in np.split(np.arange(len(cell_s)), boundaries):
        w = sc_s[grp][win_s[grp]]
        l = sc_s[grp][~win_s[grp]]
        w, l = w[~np.isnan(w)], l[~np.isnan(l)]
        if not len(w) or not len(l):
            continue
        wins = (w[:, None] > l[None, :]).sum() + 0.5 * (w[:, None] == l[None, :]).sum()
        d = int(day_s[grp][0])
        prev = result.get(d, (0.0, 0.0))
        result[d] = (prev[0] + float(wins), prev[1] + float(len(w) * len(l)))
    return result


def pooled_auc(per_day: dict[int, tuple[float, float]], days: list[int] | None = None) -> float:
    keys = list(per_day) if days is None else days
    num = sum(per_day[d][0] for d in keys if d in per_day)
    den = sum(per_day[d][1] for d in keys if d in per_day)
    return num / den if den else float("nan")


def run(matrix_dir: Path, out_path: Path, *, n_null: int, n_boot: int,
        seed: int = 20260822) -> dict:
    manifest = json.loads((matrix_dir / "manifest.json").read_text())
    names = list(manifest["feature_names"])
    resolved, missing = resolve_ingredients(names)
    needed = sorted({c for rows in resolved.values() for lc, sc, _ in rows for c in (lc, sc)}
                    | {names.index("side"), names.index("min_alert_age_sec")})
    col_of = {c: i for i, c in enumerate(needed)}
    remap = {s: [(col_of[lc], col_of[sc], sg) for lc, sc, sg in rows]
             for s, rows in resolved.items()}

    day = np.load(matrix_dir / "day.npy")
    asset = np.asarray(np.load(matrix_dir / "asset.npy"), str)
    series = np.asarray(np.load(matrix_dir / "series_id.npy"), str)
    y = np.sinh(np.load(matrix_dir / "current_asinh.npy")) * VALUE_SCALE_USD
    x = np.lib.format.open_memmap(matrix_dir / "x.npy", mode="r")
    n = len(day)
    sub = np.empty((n, len(needed)), np.float64)
    for lo in range(0, n, 200_000):
        hi = min(lo + 200_000, n)
        sub[lo:hi] = np.asarray(x[lo:hi][:, needed], np.float64)
    age = sub[:, col_of[names.index("min_alert_age_sec")]]
    side = sub[:, col_of[names.index("side")]]
    phase_col = names.index("phase_index")
    if phase_col not in col_of:
        needed_p = np.asarray(x[:, phase_col], np.float64)
    else:
        needed_p = sub[:, col_of[phase_col]]

    _u, inv = np.unique(series, return_inverse=True)
    n_series = len(_u)
    best = np.full(n_series, -np.inf)
    np.maximum.at(best, inv, y)
    s_win = best >= WINNER_MIN_USD
    s_lose = best <= LOSER_MAX_USD
    eligible = s_win | s_lose
    rng = np.random.default_rng(seed)
    report: dict = {"schema": "QRE2CONFACCRUAL1", "prereg": __doc__.split("Selftest:")[0],
                    "matrix_receipt": manifest.get("matrix_receipt_sha256"),
                    "delta_targets_sec": DELTA_TARGETS_SEC, "tolerance_sec": DELTA_TOL_SEC,
                    "n_null": n_null, "n_boot": n_boot,
                    "missing_ingredients": missing, "assets": {}}
    score_names = list(SCORE_DEFS) + ["COMBINED"]
    for a in sorted(set(asset)):
        a_rows = np.flatnonzero((asset == a) & eligible[inv])
        a_report = {"per_delta": {}, "n_winner_series": int(np.sum(s_win & (np.bincount(inv, weights=(asset == a)).astype(bool)[:n_series] if False else s_win))) }
        # winner/loser series sets restricted to this asset
        a_series = np.unique(inv[a_rows])
        a_win = {int(s) for s in a_series if s_win[s]}
        a_lose = {int(s) for s in a_series if s_lose[s]}
        a_report = {"n_winner_series": len(a_win), "n_loser_series": len(a_lose),
                    "per_delta": {}, "accrual": {}}
        per_delta_daytables: dict[float, dict[str, dict[int, tuple[float, float]]]] = {}
        for target in DELTA_TARGETS_SEC:
            cand = a_rows[np.abs(age[a_rows] - target) <= DELTA_TOL_SEC]
            if not len(cand):
                continue
            # nearest row per series to the target
            dist = np.abs(age[cand] - target)
            order = np.lexsort((dist, inv[cand]))
            cand_s = cand[order]
            first = np.ones(len(cand_s), bool)
            first[1:] = inv[cand_s][1:] != inv[cand_s][:-1]
            rows = cand_s[first]
            sc = compute_scores(sub[rows], side[rows], remap)
            is_win_r = s_win[inv[rows]]
            cell = (day[rows].astype(np.int64) * 10
                    + np.nan_to_num(needed_p[rows], nan=9).astype(np.int64))
            entry = {}
            per_delta_daytables[target] = {}
            for sname in score_names:
                per_day = pairwise_auc_by_day(sc[sname], is_win_r, day[rows], cell)
                if not per_day:
                    continue
                auc = pooled_auc(per_day)
                days = list(per_day)
                boots = [pooled_auc(per_day, list(rng.choice(days, len(days))))
                         for _ in range(n_boot)]
                nulls = []
                for _ in range(n_null):
                    perm_keys = rng.random(len(rows))
                    ordp = np.lexsort((perm_keys, cell))
                    is_win_p = np.empty_like(is_win_r)
                    ordc = np.argsort(cell, kind="stable")
                    is_win_p[ordp] = is_win_r[ordc]
                    nulls.append(pooled_auc(pairwise_auc_by_day(
                        sc[sname], is_win_p, day[rows], cell)))
                entry[sname] = {
                    "auc": round(float(auc), 4),
                    "ci95": [round(float(np.nanpercentile(boots, 2.5)), 4),
                             round(float(np.nanpercentile(boots, 97.5)), 4)],
                    "null95_top": round(float(np.nanpercentile(nulls, 97.5)), 4),
                    "n_pairs": int(sum(v[1] for v in per_day.values())),
                    "n_days": len(per_day)}
                per_delta_daytables[target][sname] = per_day
            a_report["per_delta"][str(int(target))] = entry
        first_t, last_t = DELTA_TARGETS_SEC[0], DELTA_TARGETS_SEC[-1]
        for sname in score_names:
            t0 = per_delta_daytables.get(first_t, {}).get(sname)
            t1 = per_delta_daytables.get(last_t, {}).get(sname)
            if not t0 or not t1:
                continue
            days = sorted(set(t0) & set(t1))
            if len(days) < 3:
                continue
            diffs = []
            for _ in range(n_boot):
                pick = list(rng.choice(days, len(days)))
                diffs.append(pooled_auc(t1, pick) - pooled_auc(t0, pick))
            lo95, hi95 = np.nanpercentile(diffs, [2.5, 97.5])
            a_report["accrual"][sname] = {
                "auc_delta300_minus_0": round(float(pooled_auc(t1, days)
                                                    - pooled_auc(t0, days)), 4),
                "ci95": [round(float(lo95), 4), round(float(hi95), 4)],
                "verdict": "ACCRUES" if lo95 > 0 else (
                    "DECAYS" if hi95 < 0 else "not-established")}
        report["assets"][a] = a_report
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=1))
    return report


def _synthetic(root: Path, signal: bool) -> Path:
    rng = np.random.default_rng(3)
    names = (["side", "phase_index", "min_alert_age_sec"]
             + [n for defs in SCORE_DEFS.values() for n, _ in defs if n not in VIRTUAL]
             + [c for pair in VIRTUAL.values() for c in pair])
    names = list(dict.fromkeys(names))
    rows = []
    meta = {"day": [], "asset": [], "series": [], "y": []}
    for d in range(20210601, 20210613):
        for s_i in range(10):
            win = s_i < 4
            sid = f"S_{d}_{s_i}"
            best = 900.0 if win else -150.0
            for a_idx, a_age in enumerate([0, 30, 60, 120, 180, 300]):
                row = rng.normal(size=len(names))
                row[names.index("side")] = 1.0
                row[names.index("phase_index")] = 0.0
                row[names.index("min_alert_age_sec")] = a_age
                if signal and win:
                    # liftoff ingredients improve with age for winners only
                    for ing in ("w15_aligned_displacement_usd", "w60_aligned_displacement_usd",
                                "w15_favorable_excursion_usd"):
                        row[names.index(ing)] += 0.02 * a_age
                rows.append(row)
                meta["day"].append(d); meta["asset"].append("HG")
                meta["series"].append(sid); meta["y"].append(best if a_age == 60 else best - 40)
    mdir = root / ("sig" if signal else "nosig"); mdir.mkdir(parents=True)
    x = np.asarray(rows, np.float32)
    np.save(mdir / "x.npy", x)
    np.save(mdir / "day.npy", np.asarray(meta["day"], np.int64))
    np.save(mdir / "asset.npy", np.asarray(meta["asset"]))
    np.save(mdir / "series_id.npy", np.asarray(meta["series"]))
    np.save(mdir / "current_asinh.npy", np.arcsinh(np.asarray(meta["y"]) / VALUE_SCALE_USD))
    (mdir / "manifest.json").write_text(json.dumps(
        {"feature_names": names, "rows": len(rows), "matrix_receipt_sha256": "selftest"}))
    return mdir


def selftest() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        rep = run(_synthetic(root, True), root / "sig.json", n_null=30, n_boot=50)
        acc = rep["assets"]["HG"]["accrual"]["LIFTOFF"]
        assert acc["verdict"] == "ACCRUES", f"planted accrual not detected: {acc}"
        d0 = rep["assets"]["HG"]["per_delta"]["0"]["LIFTOFF"]["auc"]
        d300 = rep["assets"]["HG"]["per_delta"]["300"]["LIFTOFF"]["auc"]
        assert d300 > d0 + 0.15, f"AUC did not rise: {d0} -> {d300}"
        rep2 = run(_synthetic(root, False), root / "nosig.json", n_null=30, n_boot=50)
        acc2 = rep2["assets"]["HG"]["accrual"]["LIFTOFF"]
        assert acc2["verdict"] == "not-established", f"false accrual: {acc2}"
        for sname, e in rep2["assets"]["HG"]["per_delta"]["300"].items():
            assert 0.35 < e["auc"] < 0.65, f"no-signal AUC out of band: {sname} {e['auc']}"
        # red fixture: gutted feature list must refuse loudly
        try:
            resolve_ingredients(["side", "min_alert_age_sec", "phase_index"])
        except AccrualRefusal as r:
            assert "ingredients" in str(r)
        else:
            raise AssertionError("red fixture accepted: empty ingredient set resolved")
    print("selftest OK: planted accrual detected; no-signal flat + not-established; "
          "red fixture refused")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--matrix-dir", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--n-null", type=int, default=100)
    ap.add_argument("--n-boot", type=int, default=200)
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if not args.matrix_dir or not args.out:
        ap.error("--matrix-dir and --out required (or --selftest)")
    rep = run(args.matrix_dir, args.out, n_null=args.n_null, n_boot=args.n_boot)
    for a, ar in rep["assets"].items():
        line = " ".join(f"{s}:{v['verdict']}" for s, v in ar["accrual"].items())
        print(f"{a}: {line}")
    print(f"receipt: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
