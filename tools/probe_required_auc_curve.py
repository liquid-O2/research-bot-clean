"""A2 (ENTRY_SELECTION_MAP): the information-requirement curve.

How much selector skill (binary AUC: ENTER-optimal vs rest) does the economic
gate REQUIRE under the frozen caps, and where does the current head's 0.659
land? Prices simulated selectors on the teacher's own regret labels with the
schedule-additive model:

    realized(day) = ceiling(day) - [ sum_selected regret_E + sum_rest regret_D ]

The model is exact at the teacher's assignment (total regret == 0) and that
identity is ASSERTED on the real matrices before any simulation — if the
labels are not schedule-additive the probe REFUSES rather than misprice
(residual tolerance $1/day).

Selector: binormal scores, separation d' = sqrt(2)*Phi^-1(AUC), selection =
top-per-(day,asset) capped at the teacher's own realized ENTER count for that
(day,asset) — feasible-capacity-matched, so the curve isolates SKILL from
capacity questions. "you_are_here": the real OOF (E-D) predicted gap as the
score, same caps, per seed.

Run:  /usr/bin/python3 tools/probe_required_auc_curve.py
Selftest (no artifacts touched): --selftest
Receipt: artifacts/entry_v2/tabular_recovery/diagnostics/e1r_required_auc_curve.json
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import numpy as np
from scipy.stats import norm

FITS = Path("/workspace/artifacts/entry_v2/tabular_recovery/rehearsal/fit_only"
            "/e1r/curriculum/fits/round_2")
EVAL = Path("/workspace/artifacts/entry_v2/tabular_recovery/rehearsal/fit_only"
            "/e1r/evaluation")
REPORT = Path("/workspace/artifacts/entry_v2/tabular_recovery/diagnostics"
              "/e1r_required_auc_curve.json")
SEEDS = (20260820, 20260821, 20260822, 20260823, 20260824)
AUCS = (0.55, 0.60, 0.659, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 0.975, 1.0)
SIMS_PER_AUC = 200
GOAL_USD_PER_ASSET_DAY = 2000.0
ADDITIVITY_TOLERANCE_USD_PER_DAY = 1.0


def price_assignment(regret_cents: np.ndarray, selected: np.ndarray) -> float:
    """Total regret (cents) of ENTER on `selected`, DEFER elsewhere."""

    enter_cost = float(regret_cents[selected, 0].sum())
    defer_cost = float(regret_cents[~selected, 1].sum())
    return enter_cost + defer_cost


def assert_schedule_additive(regret_cents: np.ndarray, optimal: np.ndarray,
                             days: np.ndarray) -> None:
    """The pricing identity: regret at the teacher's own assignment is zero."""

    action_column = {"ENTER": 0, "DEFER": 1, "PASS": 2}
    columns = np.array([action_column[a] for a in optimal])
    at_optimal = regret_cents[np.arange(len(columns)), columns]
    per_day_usd = {}
    for day in np.unique(days):
        per_day_usd[int(day)] = float(at_optimal[days == day].sum()) / 100.0
    worst = max(abs(v) for v in per_day_usd.values())
    if worst > ADDITIVITY_TOLERANCE_USD_PER_DAY:
        raise RuntimeError(
            "teacher regrets are not schedule-additive: worst per-day residual "
            f"${worst:.2f} exceeds ${ADDITIVITY_TOLERANCE_USD_PER_DAY:.2f}; "
            "the additive pricing model is invalid — use the replay instead")


def select_capacity_matched(score: np.ndarray, days: np.ndarray,
                            assets: np.ndarray,
                            capacity: dict) -> np.ndarray:
    """Top-score per (day, asset), capped at the teacher's ENTER count there."""

    selected = np.zeros(len(score), bool)
    for (day, asset), cap in capacity.items():
        if cap <= 0:
            continue
        rows = np.flatnonzero((days == day) & (assets == asset))
        take = rows[np.argsort(-score[rows])[:cap]]
        selected[take] = True
    return selected


def realized_by_asset(regret_cents: np.ndarray, selected: np.ndarray,
                      assets: np.ndarray,
                      ceiling_by_asset_cents: dict) -> dict:
    out = {}
    for asset, ceiling in ceiling_by_asset_cents.items():
        rows = assets == asset
        cost = price_assignment(regret_cents[rows], selected[rows])
        out[asset] = (float(ceiling) - cost) / 100.0
    return out


def curve_for_seed(seed: int, rng: np.random.Generator) -> dict:
    base = FITS / "action_matrices" / "real" / f"seed_{seed}"
    regret = np.load(base / "regret_cents.npy").astype(np.float64)
    optimal = np.load(base / "optimal_action.npy", allow_pickle=True)
    days = np.load(base / "day.npy")
    assets = np.load(base / "asset.npy", allow_pickle=True).astype(str)
    capture = json.load(open(EVAL / "training_capture" / f"seed_{seed}"
                             / "training_teacher_capture.json"))
    ceiling_days = {int(k) for k in capture["exact_ceiling_cents_by_day"]}
    keep = np.isin(days, sorted(ceiling_days))
    regret, optimal, days, assets = (regret[keep], optimal[keep], days[keep],
                                     assets[keep])
    assert_schedule_additive(regret, optimal, days)
    ceiling_by_asset = {k: float(v) for k, v in
                        capture["exact_ceiling_cents_by_asset"].items()}
    n_days = len(ceiling_days)
    enter = optimal == "ENTER"
    capacity = {}
    for day in np.unique(days):
        for asset in np.unique(assets):
            capacity[(day, asset)] = int(
                (enter & (days == day) & (assets == asset)).sum())
    result = {"seed": seed, "n_days": n_days,
              "n_candidates": int(len(regret)),
              "enter_rate": float(enter.mean()),
              "ceiling_usd_per_asset_day": {
                  a: c / 100.0 / n_days for a, c in ceiling_by_asset.items()},
              "curve": {}}
    for auc in AUCS:
        prime = np.sqrt(2.0) * norm.ppf(auc) if auc < 1.0 else None
        per_asset_runs = {a: [] for a in ceiling_by_asset}
        for _ in range(SIMS_PER_AUC if auc < 1.0 else 1):
            if prime is None:
                score = enter.astype(float)
            else:
                score = prime * enter + rng.standard_normal(len(enter))
            chosen = select_capacity_matched(score, days, assets, capacity)
            for a, usd in realized_by_asset(
                    regret, chosen, assets, ceiling_by_asset).items():
                per_asset_runs[a].append(usd / n_days)
        result["curve"][f"{auc:.3f}"] = {
            a: {"mean_usd_per_asset_day": float(np.mean(v)),
                "sd": float(np.std(v))} for a, v in per_asset_runs.items()}
    oof = np.load(FITS / "action_models" / "catboost" / "real"
                  / f"seed_{seed}" / "action_oof_all.npz")
    lookup = {o: i for i, o in enumerate(oof["opportunity_id"])}
    opportunity = np.load(base / "opportunity_id.npy", allow_pickle=True)[keep]
    covered = np.array([o in lookup for o in opportunity])
    rows = np.array([lookup[o] for o in opportunity[covered]])
    gap = (oof["predicted_regret_usd"][rows, 1]
           - oof["predicted_regret_usd"][rows, 0])  # D-E: higher = enter better
    chosen = np.zeros(len(regret), bool)
    chosen[np.flatnonzero(covered)] = select_capacity_matched(
        gap, days[covered], assets[covered], capacity)
    result["you_are_here_oof_gap"] = {
        a: usd / n_days for a, usd in realized_by_asset(
            regret, chosen, assets, ceiling_by_asset).items()}
    return result


def main() -> int:
    rng = np.random.default_rng(20260822)
    seeds = [curve_for_seed(seed, rng) for seed in SEEDS]
    aggregate = {}
    for auc in AUCS:
        key = f"{auc:.3f}"
        per_asset = {}
        for asset in seeds[0]["ceiling_usd_per_asset_day"]:
            means = [s["curve"][key][asset]["mean_usd_per_asset_day"]
                     for s in seeds]
            per_asset[asset] = {"mean": float(np.mean(means)),
                                "sd_across_seeds": float(np.std(means))}
        aggregate[key] = {**per_asset,
                          "min_asset_mean": float(min(
                              v["mean"] for v in per_asset.values()))}
    required = next((k for k, v in aggregate.items()
                     if v["min_asset_mean"] >= GOAL_USD_PER_ASSET_DAY), None)
    here = {a: float(np.mean([s["you_are_here_oof_gap"][a] for s in seeds]))
            for a in seeds[0]["ceiling_usd_per_asset_day"]}
    report = {"schema": "QRE2REQAUCCURVE1", "block": "E1R training (labels)",
              "pricing_model": "schedule-additive regret (identity asserted)",
              "capacity": "matched to teacher per (day, asset)",
              "sims_per_auc": SIMS_PER_AUC, "goal": GOAL_USD_PER_ASSET_DAY,
              "aggregate_curve": aggregate,
              "required_auc_for_goal": required,
              "you_are_here_oof_gap_usd_per_asset_day": here,
              "seeds": seeds}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=1))
    print(f"required AUC for ${GOAL_USD_PER_ASSET_DAY:.0f}/asset-day "
          f"(capacity-matched): {required}")
    for key in ("0.659", "0.800", "0.900", "0.950", "1.000"):
        row = aggregate[key]
        cells = " ".join(f"{a}=${row[a]['mean']:.0f}" for a in here)
        print(f"AUC {key}: {cells}  min=${row['min_asset_mean']:.0f}")
    print("you are here (real OOF gap, in-sample):",
          {a: f"${v:.0f}" for a, v in here.items()})
    print(f"receipt: {REPORT}")
    return 0


class RequiredAucSelftest(unittest.TestCase):
    """Fixture pair: the identity it must enforce, the skill it must price."""

    def _labels(self):
        regret = np.array([[0, 500, 900], [700, 0, 300], [0, 400, 800],
                           [600, 0, 200], [900, 0, 100], [500, 0, 150]],
                          float)
        optimal = np.array(["ENTER", "DEFER", "ENTER", "DEFER", "DEFER",
                            "DEFER"])
        days = np.array([1, 1, 1, 1, 2, 2])
        assets = np.array(["SI", "SI", "HG", "HG", "SI", "HG"])
        return regret, optimal, days, assets

    def test_optimal_assignment_prices_to_zero(self) -> None:
        regret, optimal, days, _ = self._labels()
        assert_schedule_additive(regret, optimal, days)

    def test_non_additive_labels_refuse(self) -> None:
        regret, optimal, days, _ = self._labels()
        broken = regret.copy()
        broken[0, 0] = 250.0  # ENTER-optimal row with nonzero ENTER regret
        with self.assertRaises(RuntimeError):
            assert_schedule_additive(broken, optimal, days)

    def test_perfect_selector_realizes_the_ceiling(self) -> None:
        regret, optimal, days, assets = self._labels()
        enter = optimal == "ENTER"
        capacity = {(d, a): int((enter & (days == d) & (assets == a)).sum())
                    for d in np.unique(days) for a in np.unique(assets)}
        chosen = select_capacity_matched(enter.astype(float), days, assets,
                                         capacity)
        self.assertTrue((chosen == enter).all())
        self.assertEqual(price_assignment(regret, chosen), 0.0)

    def test_antiskilled_selector_pays_regret(self) -> None:
        regret, optimal, days, assets = self._labels()
        enter = optimal == "ENTER"
        capacity = {(d, a): int((enter & (days == d) & (assets == a)).sum())
                    for d in np.unique(days) for a in np.unique(assets)}
        chosen = select_capacity_matched(-enter.astype(float), days, assets,
                                         capacity)
        self.assertGreater(price_assignment(regret, chosen), 0.0)


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.argv = [sys.argv[0]]
        unittest.main()
    raise SystemExit(main())
