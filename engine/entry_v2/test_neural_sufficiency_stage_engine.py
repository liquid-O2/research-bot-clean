from __future__ import annotations

import hashlib
import json
import unittest
from dataclasses import replace

import numpy as np

from . import common as C
from .atlas_statistics import PairedObservationRecord, SupportKind
from .capacity_contract import (
    SCHEMA as CAPACITY_SCHEMA, capacity_eligibility,
)
from .causal_label_atlas import CellAvailability, PROBE_REGISTRY
from .neural_sufficiency_stage_engine import (
    ARMS, DECISIONS, AssetEconomics, MeasuredFinalistConfirmation,
    HeldStageRefusal, MeasuredProbeScreen, ProbeSupportInputs, execute_e1_screen,
    execute_e2_freeze, execute_fit_only_rehearsal,
)


def _h(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _eligible_economics(
    included_days: int,
) -> tuple[str, dict[str, AssetEconomics]]:
    rows = {}
    for index, asset in enumerate(C.ASSETS):
        per_day = 2100.0 + index
        total = per_day * included_days
        oracle_total = 3000.0 * included_days
        row = {
            "capacity_regime": "FULL",
            "included_trading_days": included_days,
            "trades": 40,
            "total_pnl_usd": total,
            "usd_per_trade": total / 40,
            "usd_per_asset_day": per_day,
            "chronological_max_drawdown_usd": 450.0,
            "drawdown_p90_usd": 300.0,
            "oracle_total_pnl_usd": oracle_total,
            "oracle_usd_per_asset_day": 3000.0,
            "oracle_capture": total / oracle_total,
            "replay_receipt_sha256": _h(f"replay-{asset}"),
            "oracle_replay_receipt_sha256": _h(f"oracle-replay-{asset}"),
            "days_with_trades": min(included_days, 15),
            "asset_day_denominator": "included_trading_days",
            "values_clipped": False,
        }
        eligibility = capacity_eligibility(row)
        row.update(
            threshold_feasibility_sha256=eligibility.threshold_feasibility_sha256,
            capacity_eligibility_sha256=eligibility.receipt_sha256,
            eligibility="ELIGIBLE",
        )
        rows[asset] = row
    document = {
        "schema": CAPACITY_SCHEMA,
        "values_clipped": False,
        "asset_day_denominator": "included_trading_days",
        "per_asset": rows,
    }
    authority = hashlib.sha256(json.dumps(
        document, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode()).hexdigest()
    economics = {
        asset: AssetEconomics(
            row["capacity_regime"], row["included_trading_days"], row["trades"],
            row["total_pnl_usd"], row["usd_per_trade"], row["usd_per_asset_day"],
            row["chronological_max_drawdown_usd"], row["drawdown_p90_usd"],
            row["oracle_total_pnl_usd"], row["oracle_usd_per_asset_day"],
            row["oracle_capture"], row["replay_receipt_sha256"],
            row["oracle_replay_receipt_sha256"], authority,
            row["days_with_trades"], row["threshold_feasibility_sha256"],
            row["capacity_eligibility_sha256"], row["eligibility"],
        )
        for asset, row in rows.items()
    }
    return authority, economics


class HeldStageEngineTest(unittest.TestCase):
    def test_fit_only_rehearsal_transition_is_engine_verified(self):
        common = {"status": "ELIGIBLE", "mapper": _h("mapper"),
                  "calibrator": _h("calibrator"), "weight_receipt": _h("weight"),
                  "thresholds": {asset: .5 for asset in C.ASSETS},
                  "parity": {asset: True for asset in C.ASSETS},
                  "threshold_feasible": True, "forward_feasible": True,
                  "path_receipt_sha256": _h("path")}
        ledger = {spec.probe_id: {
            "status": ("MATERIALIZED" if spec.probe_id == "C01P01"
                       else "UNAVAILABLE_LOW_SUPPORT")}
            for spec in PROBE_REGISTRY}
        screen = {"schema": "entry-v2-fit-only-e1r-measured-v1",
                  "status": "ELIGIBLE", "fit_only_max_d8": 20210930,
                  "optimizer_fit_count": 4, "ledger": ledger,
                  "finalists": ["C01P01"], "receipt_sha256": _h("screen")}
        matrix_rows = {
            f"{arm}:{decision}": {"status": "ELIGIBLE"}
            for arm in ARMS for decision in DECISIONS}
        matrix = {"schema": "entry-v2-fit-only-e2r-measured-v1",
                  "status": "ELIGIBLE", "matrix": matrix_rows,
                  "winner": "M1:direct_neural",
                  "diagnostic_path": "M1:direct_neural",
                  "selected_objective": "C01P01",
                  "selected_learner_objective": "C01P01",
                  "objective_status": "ELIGIBLE",
                  "objective_freeze_receipt_sha256": _h("objective-freeze"),
                  "receipt_sha256": _h("matrix")}
        e1_goal = {role: {asset: {"receipt_sha256": _h(
            f"E1r:{role}:{asset}"), "eligible": True,
            "minimum_oracle_capture": .8} for asset in C.ASSETS}
            for role in ("THRESHOLD", "FORWARD")}
        e2_goal = {role: {asset: {"receipt_sha256": _h(
            f"E2r:{role}:{asset}"), "eligible": True,
            "minimum_oracle_capture": .8} for asset in C.ASSETS}
            for role in ("THRESHOLD", "FORWARD")}
        goal_receipts = {
            f"{stage}.{role}.{asset}": source[role][asset]["receipt_sha256"]
            for stage, source in (("E1r", e1_goal), ("E2r", e2_goal))
            for role in ("THRESHOLD", "FORWARD") for asset in C.ASSETS}
        e1r = {**common, "fit_days": (20210601,),
               "platt_days": (20210712,), "threshold_days": (20210721,),
               "forward_days": (20210809,), "probe_screen": screen,
               "minimum_oracle_capture": .8,
               "threshold_goal_recovery": e1_goal["THRESHOLD"],
               "forward_goal_recovery": e1_goal["FORWARD"],
               "forward_feasibility": {asset: {"feasible": True,
                   "goal_recovery_receipt_sha256":
                       e1_goal["FORWARD"][asset]["receipt_sha256"]}
                   for asset in C.ASSETS}}
        e2r = {**common, "fit_days": (20210802,),
               "platt_days": (20210816,), "threshold_days": (20210913,),
               "forward_days": (20210921,), "arm_head_matrix": matrix,
               "minimum_oracle_capture": .8,
               "threshold_goal_recovery": e2_goal["THRESHOLD"],
               "forward_goal_recovery": e2_goal["FORWARD"],
               "forward_feasibility": {asset: {"feasible": True,
                   "goal_recovery_receipt_sha256":
                       e2_goal["FORWARD"][asset]["receipt_sha256"]}
                   for asset in C.ASSETS}}
        receipt = execute_fit_only_rehearsal(
            e1r=e1r, e2r=e2r,
            g7={"single_real_path": "M1:direct_neural",
                "selected_arm": "M1", "selected_head": "direct_neural",
                "selected_objective": "C01P01",
                "learner_law_sha256": _h("learner-law"),
                "e1r_checkpoint_sha256": _h("e1-full"),
                "e2r_checkpoint_sha256": _h("e2-full"),
                "e1r_fit_wall": 20210709, "e2r_fit_wall": 20210813,
                "same_full_learner_independent_fits": True,
                "all_asset_in_sample": True,
                "all_asset_disjoint_forward": True,
                "minimum_oracle_capture": .8,
                "goal_recovery_all_blocks": True,
                "goal_recovery_receipts": goal_receipts,
                "candidate_ceiling_all_blocks": True,
                "candidate_ceiling_receipts": {
                    "E1r.THRESHOLD": _h("e1-threshold"),
                    "E1r.FORWARD": _h("e1-forward"),
                    "E2r.THRESHOLD": _h("e2-threshold"),
                    "E2r.FORWARD": _h("e2-forward"),
                },
                "twins_counted": False},
            source_tree_sha256=_h("source"))
        self.assertEqual(receipt["status"], "PASS")
        self.assertTrue(receipt["held_launch_permitted"])
        self.assertEqual(len(receipt["receipt_sha256"]), 64)

        failed_matrix = dict(matrix)
        failed_matrix.update(
            status="NO_FIT_ONLY_DEPLOYABLE_DEPTH", winner=None,
            objective_status="NO_REAL_BEYOND_TWIN")
        failed_e2r = {**e2r, "arm_head_matrix": failed_matrix}
        failed = execute_fit_only_rehearsal(
            e1r=e1r, e2r=failed_e2r,
            g7={"single_real_path": "M1:direct_neural",
                "selected_arm": "M1", "selected_head": "direct_neural",
                "selected_objective": "C01P01",
                "learner_law_sha256": _h("learner-law"),
                "e1r_checkpoint_sha256": _h("e1-full"),
                "e2r_checkpoint_sha256": _h("e2-full"),
                "e1r_fit_wall": 20210709, "e2r_fit_wall": 20210813,
                "same_full_learner_independent_fits": True,
                "all_asset_in_sample": False,
                "all_asset_disjoint_forward": False,
                "minimum_oracle_capture": .8,
                "goal_recovery_all_blocks": False,
                "goal_recovery_receipts": goal_receipts,
                "candidate_ceiling_all_blocks": True,
                "candidate_ceiling_receipts": {
                    "E1r.THRESHOLD": _h("e1-threshold"),
                    "E1r.FORWARD": _h("e1-forward"),
                    "E2r.THRESHOLD": _h("e2-threshold"),
                    "E2r.FORWARD": _h("e2-forward")},
                "twins_counted": False},
            source_tree_sha256=_h("source"))
        self.assertEqual(failed["status"], "NO_FIT_ONLY_DEPLOYABLE_DEPTH")
        self.assertFalse(failed["held_launch_permitted"])

    def _screen(self) -> MeasuredProbeScreen:
        assets = np.repeat(np.asarray(["HG", "NKD", "SI"]), 200)
        fit_days = np.tile(np.arange(20210601, 20210621), 30)[:600]
        values = np.linspace(-3, 3, 600)
        records = []
        held_days = [20211101 + i for i in range(20)]
        for i in range(600):
            records.append(PairedObservationRecord(
                f"c{i:04d}", str(assets[i]), str(held_days[i % len(held_days)]), True,
                _h("real-target"), _h("twin-target"),
                1.0 + .05 * np.sin(i), .2 * np.cos(i),
            ))
        return MeasuredProbeScreen(
            "C01P01", "mixed-event", "SHARED_PRETEXT", "shallow_probe",
            tuple(records),
            ProbeSupportInputs(SupportKind.CONTINUOUS, assets, np.ones(600, bool),
                               values=values, day=fit_days,
                               censored=np.zeros(600, bool),
                               selected_horizon_start_d8=20210531),
            values, _h("real-checkpoint"), _h("twin-checkpoint"), _h("rows"),
            (20211001, 20211004, 20211005, 20211006,
             20211007, 20211008, 20211011),
            {"real_funnel": _h("real-funnel"), "twin_funnel": _h("twin-funnel")},
        )

    def test_e1_validates_physical_support_planes_even_when_unavailable(self):
        base = self._screen()
        unavailable = replace(
            base, records=(), path_receipts={},
            availability=CellAvailability.RIGHT_CENSORED)
        unavailable.validate()
        self.assertIs(unavailable.availability, CellAvailability.RIGHT_CENSORED)

        held_day = np.asarray(unavailable.support.day).copy()
        held_day[-1] = 20211001
        hidden_held = replace(
            unavailable, support=replace(
                unavailable.support,
                valid=np.zeros_like(unavailable.support.valid, dtype=bool),
                day=held_day))
        with self.assertRaisesRegex(HeldStageRefusal, "crossed its fit boundary"):
            hidden_held.validate()

        misaligned = replace(
            unavailable, support=replace(
                unavailable.support,
                values=np.asarray(unavailable.support.values)[:-1]))
        with self.assertRaisesRegex(HeldStageRefusal, "values array is misaligned"):
            misaligned.validate()

        extra = ProbeSupportInputs(
            SupportKind.CONTINUOUS, np.asarray(["HG"]), np.asarray([False]),
            values=np.asarray([0.0]), day=np.asarray([20211101]),
            censored=np.asarray([False]), selected_horizon_start_d8=20210531)
        with self.assertRaisesRegex(HeldStageRefusal, "crossed its fit boundary"):
            replace(unavailable, additional_support=(extra,)).validate()
        with self.assertRaisesRegex(HeldStageRefusal, "canonical atlas state"):
            replace(unavailable, availability="UNAVAILABLE_CUSTOM")

    def test_exact_e1_holm_and_e2_romano_wolf_freeze(self):
        base = self._screen()
        unavailable = tuple(replace(
            base, probe_id=spec.probe_id, records=(), real_checkpoint_sha256="0" * 64,
            twin_checkpoint_sha256="0" * 64, path_receipts={},
            availability="UNAVAILABLE_LOW_SUPPORT")
            for spec in PROBE_REGISTRY if spec.probe_id != base.probe_id)
        e1 = execute_e1_screen((base, *unavailable))
        self.assertEqual(e1.finalists, ("C01P01",))
        days = tuple(range(20220610, 20220630))
        effects = {asset: np.linspace(80, 120, len(days)) + j
                   for j, asset in enumerate(("HG", "NKD", "SI"))}
        capture = {asset: np.linspace(.2, .4, len(days)) + j * .01
                   for j, asset in enumerate(("HG", "NKD", "SI"))}
        capacity, economics = _eligible_economics(len(days))
        confirmation = MeasuredFinalistConfirmation(
            "C01P01", "M1", "direct_neural", days, effects, capture, economics,
            _h("arm"), _h("objective"), _h("calibrator"), _h("thresholds"),
            capacity, _h("mapper"), _h("e2-real"), _h("e2-twin"),
            1000, 2.0, (20210531, 20220311),
            (20220314, 20220401, 20220428, 20220609), days,
            platt_days=(20220314, 20220401),
            threshold_development_days=(20220428, 20220609),
        )
        matrix = []
        for index, (arm, decision) in enumerate(
                (pair for arm in ARMS for pair in ((arm, kind) for kind in DECISIONS))):
            # Hold statistical/economic evidence exactly tied so this test
            # exercises only the declared lower-parameter/probe-id tie law.
            varied = {asset: value.copy() for asset, value in effects.items()}
            varied_capture = {
                asset: value.copy() for asset, value in capture.items()
            }
            matrix.append(replace(confirmation,
                probe_id=("A0_CURRENT_GROUPING" if arm == "C0" else "C01P01"),
                arm=arm, decision_kind=decision, effect_by_asset=varied,
                capture_effect_by_asset=varied_capture,
                selected_arm_sha256=_h(f"arm-{arm}-{decision}"),
                selected_objective_sha256=_h(
                    "a0-objective" if arm == "C0" else "objective")))
        winner = execute_e2_freeze(e1, matrix, _h("objective-freeze"))
        self.assertEqual(winner.confirmation.probe_id, "A0_CURRENT_GROUPING")
        self.assertEqual(winner.confirmation.arm, "C0")
        self.assertEqual(winner.confirmation.decision_kind, "direct_neural")
        self.assertGreater(min(winner.lower_dollars_by_asset.values()), 0)
        self.assertGreater(min(winner.lower_capture_by_asset.values()), 0)

        # All ten preregistered rows remain in the 30-column family.  Typed
        # zero-effect losers are retained without a zero-SE crash and cannot
        # be selected.
        loser = replace(matrix[-1], status="NO_FEASIBLE_THRESHOLD",
            economics={},
            effect_by_asset={asset: np.zeros(len(days)) for asset in ("HG", "NKD", "SI")},
            capture_effect_by_asset={asset: np.zeros(len(days)) for asset in ("HG", "NKD", "SI")},
            rejection_reason_by_asset={asset: "NO_FEASIBLE_THRESHOLD"
                                       for asset in ("HG", "NKD", "SI")},
            funnel_receipt_by_asset={asset: _h(f"loser-{asset}")
                                     for asset in ("HG", "NKD", "SI")})
        typed = execute_e2_freeze(e1, (*matrix[:-1], loser), _h("objective-freeze"))
        self.assertNotEqual(typed.confirmation.status, "NO_FEASIBLE_THRESHOLD")


if __name__ == "__main__":
    unittest.main()
