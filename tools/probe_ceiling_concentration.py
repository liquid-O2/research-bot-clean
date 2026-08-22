"""A7 ceiling concentration probe: how much of the exact-delayed ceiling lives
in the top-1/2/3 trades per asset-day.

The user wants few, high-EV entries.  This measures whether the exact ceiling
itself has that shape, per block and per asset, on the frozen rehearsal teacher
days.  Read-only: it consumes the published teacher-day and outcome-shard
caches and writes one receipt.

Field semantics are read out of engine/entry_v2/exact_delayed_teacher.py, not
guessed from field names; see FIELD_SEMANTICS below for the file:line anchors.

Run:       OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 nice -n 10 \
             python3 tools/probe_ceiling_concentration.py
Self-test: python3 tools/probe_ceiling_concentration.py --selftest
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Final, Iterable, Mapping, Sequence
import unittest

import numpy as np


WORKSPACE: Final = Path("/workspace")
TEACHER_ROOT: Final = WORKSPACE / (
    "artifacts/entry_v2/tabular_recovery/rehearsal/cache/teacher_days")
OUTCOME_ROOT: Final = WORKSPACE / (
    "artifacts/entry_v2/tabular_recovery/rehearsal/cache/outcome_sessions")
RECEIPT_PATH: Final = WORKSPACE / (
    "artifacts/entry_v2/tabular_recovery/diagnostics/"
    "e1r_ceiling_concentration.json")

ASSETS: Final = ("HG", "NKD", "SI")
PORTFOLIO_KEY: Final = "PORTFOLIO"
# Frozen rehearsal transitions (weekends absent from the cache by construction).
BLOCKS: Final = {
    "training": (20210610, 20210630),
    "threshold": (20210721, 20210728),
    "forward": (20210809, 20210826),
}
# A day whose per-entry contributions miss its published objective by more than
# this is refused, never approximated.
RECONCILE_TOLERANCE_USD: Final = 1.0

FIELD_SEMANTICS: Final = {
    "exact_objective_cents": (
        "The whole-day exact ceiling in cents: the MILP objective of the "
        "canonical schedule, assembled at "
        "engine/entry_v2/exact_delayed_teacher.py:685 as "
        "`objective = int(self.cents[selected_local].sum())` where "
        "`self.cents` is `universe.signed_pnl_cents` restricted to the "
        "dominance-pruned columns (:374). Published onto the teacher day at "
        ":1215."),
    "per_entry_contribution_term": (
        "`signed_pnl_cents` of each selected column IS the per-entry term of "
        "that sum (:685) -- the objective is a plain sum with no shared or "
        "cross-entry term. Its dollar copy on the teacher day is "
        "`current_entry_usd`, defined at :1024 as "
        "`current = universe.signed_pnl_cents / 100.0` and published at :1040 "
        "as `current_entry_usd = current[indices]`, aligned row-for-row with "
        "`component_opportunity_id` (:1038). Every selected snapshot is "
        "guaranteed to be a component row: _component_indices keeps "
        "(series, ts) at the entry timestamp for each selected index "
        "(:1011-1015). So the contribution of a selected entry is "
        "current_entry_usd looked up by its opportunity id."),
    "current_entry_usd": (
        "Per-component-row realized signed PnL in dollars of entering AT that "
        "snapshot (:1024, :1040). It is a per-option payoff, not a state "
        "value -- it is the objective coefficient itself."),
    "q_enter_cents/q_defer_cents/q_pass_cents": (
        "NOT per-entry payoffs. They are whole-day DP state-values of the "
        "remaining suffix under each action: q_enter = this option's cents + "
        "suffix objective after locking it (:780), q_defer/q_pass = suffix "
        "objective with the snapshot / whole series removed (:789-791). "
        "max(q_enter) over the day therefore equals the whole-day objective, "
        "and summing them double-counts the day many times over. Rows where "
        "ENTER is structurally impossible (series consumed, asset occupied, "
        "or entry cap reached) carry the sentinel q_enter = -10**18 "
        "(:764-768). Not used by this probe."),
    "action_margin_cents": (
        "Gap between the best and second-best of the three Q values "
        "(:1184-1185, identity re-asserted at :902-904). A decision-"
        "confidence quantity, not a payoff. Not used by this probe."),
    "selected_opportunity_ids/selected_series_ids": (
        "Opportunity and series ids of the canonical schedule (:1143-1145). "
        "Both are 64-hex hashes with no asset prefix, so an asset can never "
        "be recovered from the string."),
    "asset_attribution": (
        "The teacher day carries no per-row asset. The authoritative mapping "
        "is the day option universe it was built from: "
        "DayOptionUniverse.from_shards concatenates one DelayedOutcomeShard "
        "per asset (:175-205) and each shard is validated to hold exactly one "
        "asset (engine/entry_v2/tabular_delayed_corpus.py:125). The teacher "
        "day's sidecar json lists those shards' representation_sha256 values "
        "in `source_outcome_sha256` (:203-204), so the probe selects the "
        "outcome-store identity whose three per-asset shards for that day "
        "hash to exactly that set, then maps opportunity_id -> asset from the "
        "shards. No string-prefix guessing anywhere."),
    "reconciliation_gate": (
        "Per day: sum of current_entry_usd over selected_opportunity_ids must "
        "equal exact_objective_cents/100 within $1, else the day is refused."),
    "variant_selection": (
        "Nine teacher identity variants exist per day. The probe takes the "
        "lexicographically first identity whose component rows contain every "
        "selected id and whose day reconciles, and asserts the base-round "
        "(action_rollout_round == 0) rows of that same file also contain "
        "every selected id -- guaranteed by _action_query_indices, which "
        "stamps the entry snapshot of each selected series ORACLE_TRAJECTORY "
        "(:1102-1105)."),
}


class CeilingConcentrationRefusal(RuntimeError):
    """A day could not be measured exactly; never silently approximated."""


def day_contributions(
    teacher: Mapping[str, np.ndarray],
) -> tuple[tuple[str, ...], np.ndarray, float]:
    """Per-selected-entry dollar contributions and the published day ceiling."""

    selected = tuple(np.asarray(teacher["selected_opportunity_ids"], str).tolist())
    component = np.asarray(teacher["component_opportunity_id"], str)
    current = np.asarray(teacher["current_entry_usd"], np.float64)
    if component.shape != current.shape:
        raise CeilingConcentrationRefusal(
            f"component rows {component.shape} and current_entry_usd "
            f"{current.shape} disagree; expected identical 1-D shapes")
    by_id = dict(zip(component.tolist(), current.tolist()))
    missing = [value for value in selected if value not in by_id]
    if missing:
        raise CeilingConcentrationRefusal(
            f"{len(missing)} selected ids absent from component rows "
            f"(first: {missing[0]}); expected every selected snapshot to be "
            "kept by _component_indices")
    objective_usd = float(np.asarray(
        teacher["exact_objective_cents"], np.int64).reshape(-1)[0]) / 100.0
    return selected, np.asarray([by_id[value] for value in selected],
                                np.float64), objective_usd


def reconcile_day(
    trading_day: int, contributions: np.ndarray, objective_usd: float,
) -> float:
    """Return the signed residual; refuse the day when it exceeds $1."""

    residual = float(contributions.sum()) - float(objective_usd)
    if abs(residual) > RECONCILE_TOLERANCE_USD:
        raise CeilingConcentrationRefusal(
            f"day {trading_day}: per-entry contributions sum to "
            f"${contributions.sum():.2f} but exact_objective_cents says "
            f"${objective_usd:.2f} (residual ${residual:.2f}); expected "
            f"agreement within ${RECONCILE_TOLERANCE_USD}")
    return residual


def base_round_ids(teacher: Mapping[str, np.ndarray]) -> frozenset[str]:
    rounds = np.asarray(teacher["action_rollout_round"], np.int64)
    ids = np.asarray(teacher["action_opportunity_id"], str)
    return frozenset(ids[rounds == 0].tolist())


def _block_of(trading_day: int) -> str | None:
    for name, (low, high) in BLOCKS.items():
        if low <= trading_day <= high:
            return name
    return None


def _quantiles(values: np.ndarray) -> dict[str, float]:
    if not len(values):
        return {"q50": 0.0, "q75": 0.0, "q90": 0.0, "q99": 0.0}
    return {f"q{int(q * 100)}": round(float(np.quantile(values, q)), 2)
            for q in (0.50, 0.75, 0.90, 0.99)}


def summarize(
    per_asset_day: Mapping[tuple[int, str], Sequence[float]], days: Sequence[int],
    asset_days: Mapping[str, Sequence[int]],
) -> dict[str, dict[str, float]]:
    """Concentration statistics for one block, per asset plus the portfolio.

    An asset is only charged the days its shard was actually in that day's
    option universe: 31 of the 89 cached days carry fewer than three asset
    shards, and counting those as zero-ceiling asset-days would understate the
    per-asset-day ceiling.
    """

    if not days:
        raise CeilingConcentrationRefusal("block has no measured days")
    output: dict[str, dict[str, float]] = {}
    for key in (*ASSETS, PORTFOLIO_KEY):
        present = list(days) if key == PORTFOLIO_KEY else list(asset_days.get(key, ()))
        n_days = len(present)
        if n_days == 0:
            output[key] = {"days": 0, "trades": 0}
            continue
        per_day = []
        for day in present:
            if key == PORTFOLIO_KEY:
                values = [value for asset in ASSETS
                          for value in per_asset_day.get((day, asset), ())]
            else:
                values = list(per_asset_day.get((day, key), ()))
            per_day.append(sorted(values, reverse=True))
        flat = np.asarray([value for values in per_day for value in values],
                          np.float64)
        total = float(flat.sum())
        tops = {f"top{k}_share": (
            round(sum(sum(values[:k]) for values in per_day) / total, 4)
            if total else 0.0) for k in (1, 2, 3)}
        unit = "asset_day" if key != PORTFOLIO_KEY else "day"
        output[key] = {
            "days": n_days,
            "trades": int(len(flat)),
            f"ceiling_usd_per_{unit}": round(total / n_days, 2),
            f"trades_per_{unit}": round(len(flat) / n_days, 3),
            "avg_usd_per_trade": round(total / len(flat), 2) if len(flat) else 0.0,
            "total_usd": round(total, 2),
            **tops,
            **_quantiles(flat),
            # Per-asset top-3 saturates at 1.000, so the count histogram is
            # what carries the shape answer at the asset level.
            "trades_per_unit_day_histogram": {
                str(count): sum(1 for values in per_day if len(values) == count)
                for count in sorted({len(values) for values in per_day})},
        }
    return output


def _shard_index(days: Iterable[int]) -> dict[int, dict[str, tuple[str, str]]]:
    """Map trading day -> {shard representation_sha256: (identity, asset)}.

    Matching on the individual shard hash rather than on a whole three-asset
    identity is what makes the attribution exact: 31 of the cached days hold
    fewer than three asset shards, so a day's `source_outcome_sha256` is not
    always a full identity's shard set.
    """

    index: dict[int, dict[str, tuple[str, str]]] = {day: {} for day in days}
    for identity in sorted(path.name for path in OUTCOME_ROOT.iterdir()
                           if path.is_dir()):
        for asset in ASSETS:
            for day in index:
                sidecar = OUTCOME_ROOT / identity / asset / f"{day}.json"
                if not sidecar.exists():
                    continue
                sha = json.loads(sidecar.read_text())["representation_sha256"]
                index[day][sha] = (identity, asset)
    return index


def _asset_by_opportunity(
    shards: Iterable[tuple[str, str]], day: int,
) -> dict[str, str]:
    output: dict[str, str] = {}
    for identity, asset in shards:
        with np.load(OUTCOME_ROOT / identity / asset / f"{day}.npz",
                     allow_pickle=False) as shard:
            for value in np.asarray(shard["opportunity_id"], str).tolist():
                output[value] = asset
    return output


def measure() -> dict[str, object]:
    """Run the probe over the three frozen blocks and return the receipt."""

    wanted = sorted({int(path.stem)
                     for identity in TEACHER_ROOT.iterdir() if identity.is_dir()
                     for path in identity.glob("*.npz")
                     if _block_of(int(path.stem)) is not None})
    shard_index = _shard_index(wanted)
    per_asset_day: dict[tuple[int, str], list[float]] = {}
    residuals: dict[str, list[float]] = {name: [] for name in BLOCKS}
    used: dict[str, dict[str, object]] = {}
    refusals: list[str] = []
    days_by_block: dict[str, list[int]] = {name: [] for name in BLOCKS}
    asset_days: dict[str, dict[str, list[int]]] = {
        name: {asset: [] for asset in ASSETS} for name in BLOCKS}
    for day in wanted:
        block = _block_of(day)
        assert block is not None
        candidates = sorted(
            identity.name for identity in TEACHER_ROOT.iterdir()
            if (identity / f"{day}.npz").exists())
        chosen = None
        for identity in candidates:
            path = TEACHER_ROOT / identity / f"{day}.npz"
            with np.load(path, allow_pickle=False) as teacher:
                payload = {name: teacher[name] for name in (
                    "selected_opportunity_ids", "component_opportunity_id",
                    "current_entry_usd", "exact_objective_cents",
                    "action_opportunity_id", "action_rollout_round")}
            try:
                selected, contributions, objective = day_contributions(payload)
                residual = reconcile_day(day, contributions, objective)
            except CeilingConcentrationRefusal as exc:
                refusals.append(f"{day}/{identity}: {exc}")
                continue
            absent = set(selected) - base_round_ids(payload)
            if absent:
                raise CeilingConcentrationRefusal(
                    f"day {day} identity {identity}: {len(absent)} selected ids "
                    "absent from base-round action rows; expected "
                    "_action_query_indices to stamp every selected entry")
            chosen = (identity, selected, contributions, objective, residual)
            break
        if chosen is None:
            raise CeilingConcentrationRefusal(
                f"day {day}: no teacher identity of {len(candidates)} both "
                "contains every selected id and reconciles to "
                f"exact_objective_cents within ${RECONCILE_TOLERANCE_USD}; "
                + " | ".join(refusals[-len(candidates):]))
        identity, selected, contributions, objective, residual = chosen
        sidecar = json.loads(
            (TEACHER_ROOT / identity / f"{day}.json").read_text())
        shas = tuple(sidecar["source_outcome_sha256"])
        unknown = [sha for sha in shas if sha not in shard_index[day]]
        if unknown:
            raise CeilingConcentrationRefusal(
                f"day {day}: source shard sha {unknown[0]} matches no cached "
                "outcome shard of that day")
        shards = tuple(shard_index[day][sha] for sha in shas)
        day_assets = sorted({asset for _identity, asset in shards})
        if len(day_assets) != len(shards):
            raise CeilingConcentrationRefusal(
                f"day {day}: source shards repeat an asset {day_assets}")
        asset_by_id = _asset_by_opportunity(shards, day)
        unmapped = [value for value in selected if value not in asset_by_id]
        if unmapped:
            raise CeilingConcentrationRefusal(
                f"day {day}: {len(unmapped)} selected ids absent from the "
                f"outcome shards of identity {outcome_identity}")
        for opportunity, value in zip(selected, contributions.tolist()):
            per_asset_day.setdefault(
                (day, asset_by_id[opportunity]), []).append(value)
        residuals[block].append(residual)
        days_by_block[block].append(day)
        for asset in day_assets:
            asset_days[block][asset].append(day)
        used[str(day)] = {"teacher_identity": identity,
                          "outcome_shards": [f"{i}/{a}" for i, a in shards],
                          "assets": day_assets,
                          "objective_usd": round(objective, 2),
                          "residual_usd": round(residual, 6)}
    blocks = {
        name: {
            "day_range": list(BLOCKS[name]),
            "days_measured": days_by_block[name],
            "reconciliation_residual_usd": {
                "max_abs": round(max((abs(value) for value in residuals[name]),
                                     default=0.0), 6),
                "sum": round(sum(residuals[name]), 6),
                "tolerance": RECONCILE_TOLERANCE_USD,
            },
            "asset_days_measured": {
                asset: len(values)
                for asset, values in asset_days[name].items()},
            "by_asset": summarize(
                per_asset_day, days_by_block[name], asset_days[name]),
        } for name in BLOCKS}
    return {
        "schema": "QRE2CEILINGCONCENTRATION1",
        "probe": "tools/probe_ceiling_concentration.py",
        "teacher_root": str(TEACHER_ROOT),
        "outcome_root": str(OUTCOME_ROOT),
        "field_semantics": FIELD_SEMANTICS,
        "blocks": blocks,
        "day_sources": used,
        "rejected_variants": refusals,
    }


def _print_table(receipt: Mapping[str, object]) -> None:
    header = (f"{'block':<10}{'asset':<11}{'$/unit-day':>11}{'trades/d':>9}"
              f"{'$/trade':>9}{'top1':>7}{'top2':>7}{'top3':>7}"
              f"{'q50':>8}{'q75':>8}{'q90':>8}{'q99':>8}")
    print(header); print("-" * len(header))
    blocks = receipt["blocks"]
    assert isinstance(blocks, dict)
    for name, block in blocks.items():
        for asset, row in block["by_asset"].items():
            unit = "day" if asset == PORTFOLIO_KEY else "asset_day"
            if not row["days"]:
                print(f"{name:<10}{asset:<11}{'(absent from every day)':>11}")
                continue
            print(f"{name:<10}{asset:<11}"
                  f"{row[f'ceiling_usd_per_{unit}']:>11.2f}"
                  f"{row[f'trades_per_{unit}']:>9.2f}"
                  f"{row['avg_usd_per_trade']:>9.2f}"
                  f"{row['top1_share']:>7.3f}{row['top2_share']:>7.3f}"
                  f"{row['top3_share']:>7.3f}"
                  f"{row['q50']:>8.1f}{row['q75']:>8.1f}"
                  f"{row['q90']:>8.1f}{row['q99']:>8.1f}")
        residual = block["reconciliation_residual_usd"]
        print(f"{name:<10}residual max_abs=${residual['max_abs']} over "
              f"{len(block['days_measured'])} days")


def _synthetic_day(objective_cents: int) -> dict[str, np.ndarray]:
    return {
        "selected_opportunity_ids": np.asarray(["a", "b", "c"], str),
        "component_opportunity_id": np.asarray(["a", "b", "c", "d"], str),
        "current_entry_usd": np.asarray([100.0, 50.0, 25.0, 9.0], np.float64),
        "exact_objective_cents": np.asarray([objective_cents], np.int64),
        "action_opportunity_id": np.asarray(["a", "b", "c", "d"], str),
        "action_rollout_round": np.asarray([0, 0, 0, 1], np.int64),
    }


class CeilingConcentrationTests(unittest.TestCase):
    def test_contributions_are_the_selected_current_entry_usd(self) -> None:
        selected, contributions, objective = day_contributions(
            _synthetic_day(17500))
        self.assertEqual(selected, ("a", "b", "c"))
        self.assertEqual(contributions.tolist(), [100.0, 50.0, 25.0])
        self.assertEqual(objective, 175.0)

    def test_reconciling_day_passes_the_gate(self) -> None:
        _selected, contributions, objective = day_contributions(
            _synthetic_day(17500))
        self.assertLessEqual(
            abs(reconcile_day(20210610, contributions, objective)),
            RECONCILE_TOLERANCE_USD)

    def test_nonreconciling_day_is_refused(self) -> None:
        """RED fixture: contributions deliberately miss the published ceiling."""

        _selected, contributions, objective = day_contributions(
            _synthetic_day(20000))
        with self.assertRaises(CeilingConcentrationRefusal):
            reconcile_day(20210610, contributions, objective)

    def test_selected_id_absent_from_component_rows_is_refused(self) -> None:
        day = _synthetic_day(17500)
        day["component_opportunity_id"] = np.asarray(["a", "b", "d"], str)
        day["current_entry_usd"] = np.asarray([100.0, 50.0, 9.0], np.float64)
        with self.assertRaises(CeilingConcentrationRefusal):
            day_contributions(day)

    def test_base_round_ids_exclude_rollout_rows(self) -> None:
        self.assertEqual(base_round_ids(_synthetic_day(17500)),
                         frozenset({"a", "b", "c"}))

    def test_summarize_shares_and_rates(self) -> None:
        per_asset_day = {
            (20210610, "HG"): [100.0, 50.0, 25.0, 25.0],
            (20210611, "HG"): [200.0],
            (20210610, "SI"): [10.0],
        }
        summary = summarize(
            per_asset_day, [20210610, 20210611],
            {"HG": [20210610, 20210611], "SI": [20210610], "NKD": []})
        hg = summary["HG"]
        self.assertEqual(hg["trades"], 5)
        self.assertEqual(hg["total_usd"], 400.0)
        self.assertEqual(hg["ceiling_usd_per_asset_day"], 200.0)
        self.assertEqual(hg["trades_per_asset_day"], 2.5)
        # top-1 per day: 100 (d1) + 200 (d2) = 300 of 400.
        self.assertEqual(hg["top1_share"], 0.75)
        self.assertEqual(hg["top2_share"], 0.875)
        self.assertEqual(hg["top3_share"], 0.9375)
        # An asset absent from every day of the block is charged no asset-days.
        self.assertEqual(summary["NKD"], {"days": 0, "trades": 0})
        self.assertEqual(summary["SI"]["ceiling_usd_per_asset_day"], 10.0)
        self.assertEqual(hg["trades_per_unit_day_histogram"], {"1": 1, "4": 1})
        portfolio = summary[PORTFOLIO_KEY]
        self.assertEqual(portfolio["trades"], 6)
        self.assertEqual(portfolio["ceiling_usd_per_day"], 205.0)


def main(argv: Sequence[str]) -> int:
    if "--selftest" in argv:
        result = unittest.main(argv=[argv[0]], exit=False).result
        return 0 if result.wasSuccessful() else 1
    receipt = measure()
    RECEIPT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT_PATH.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    _print_table(receipt)
    print(f"\nreceipt -> {RECEIPT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
