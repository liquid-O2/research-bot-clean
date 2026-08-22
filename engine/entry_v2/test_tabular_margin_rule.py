"""A1 margin-rule contract tests (design/A1_MARGIN_RULE_SPEC.md items 1-2).

Diagnosis-only surface: the ARGMIN default of every chain call site must stay
byte-identical, so each fixture here pairs the new MARGIN behaviour with the
guard that the default did not move.
"""

from __future__ import annotations

import unittest

from .tabular_calibration import AdmissionContract
from .tabular_policy import decide, decide_margin
from .tabular_recovery_contracts import (
    ComponentPredictions, DecisionAction, PortfolioDecisionState,
)


MARGIN_TEST_DAY = 20210809
MARGIN_TEST_TS = 1_628_000_000_000_000_000
_MARGIN_HEX = "0123456789abcdef"


def _margin_sha(seed: int) -> str:
    return "".join(_MARGIN_HEX[(seed * 5 + index * 13) % 16]
                   for index in range(64))


def _margin_components(*, enter_regret: float, defer_regret: float,
        wall_probability: float = 0.10, current_q20_usd: float = 10.0,
        mae_q90_usd: float = 5.0,
        pass_regret: float = 1_000.0) -> ComponentPredictions:
    return ComponentPredictions(
        current_q20_usd=current_q20_usd, current_q50_usd=200.0,
        current_q80_usd=300.0, continuation_q20_usd=10.0,
        continuation_q50_usd=20.0, continuation_q80_usd=30.0,
        wall_probability=wall_probability, enter_probability=0.5,
        mae_q90_usd=mae_q90_usd, occupancy_q50_sec=60.0,
        occupancy_q90_sec=120.0, enter_regret=enter_regret,
        defer_regret=defer_regret, pass_regret=pass_regret,
        lower_action_advantage_usd=-77.0, incremental_dollars_usd=-88.0)


def _margin_state(components: ComponentPredictions) -> PortfolioDecisionState:
    return PortfolioDecisionState(
        "cand-1", "series-1", "SI", MARGIN_TEST_DAY, 1, MARGIN_TEST_TS,
        MARGIN_TEST_TS + 1_000_000_000, ("f_a", "f_b"), (1.0, 2.0),
        components, 0, (), (0, 0, 0, 0, 0, 0), "NY", "MID")


def _margin_admission(threshold: float) -> AdmissionContract:
    """Risk gates wide open unless a fixture narrows one of them."""

    return AdmissionContract(0.0, 0.50, 1_000.0, float(threshold), 10,
                             _margin_sha(3), _margin_sha(4))


class MarginRuleDecisionTest(unittest.TestCase):
    """Spec item 1: margin >= theta AND the three risk gates."""

    def test_clean_row_above_theta_enters_and_carries_the_margin(self):
        state = _margin_state(_margin_components(enter_regret=100.0,
                                                 defer_regret=400.0))
        decision = decide_margin(state, _margin_admission(250.0))
        self.assertIs(decision.action, DecisionAction.ENTER)
        self.assertEqual(decision.reason, "ADMITTED")
        self.assertEqual(decision.incremental_dollars_usd, 300.0)

    def test_row_below_theta_defers_with_the_margin_reason(self):
        state = _margin_state(_margin_components(enter_regret=100.0,
                                                 defer_regret=400.0))
        decision = decide_margin(state, _margin_admission(301.0))
        self.assertIs(decision.action, DecisionAction.DEFER)
        self.assertEqual(decision.reason, "MARGIN_BELOW_THRESHOLD")

    def test_above_theta_wall_breach_defers_with_the_admission_reason(self):
        state = _margin_state(_margin_components(enter_regret=100.0,
            defer_regret=400.0, wall_probability=0.75))
        decision = decide_margin(state, _margin_admission(250.0))
        self.assertIs(decision.action, DecisionAction.DEFER)
        self.assertEqual(decision.reason, "ADMISSION_WALL")

    def test_argmin_default_refuses_the_row_the_margin_rule_admits(self):
        """Same row, same theta: the two rules score different quantities.

        ARGMIN tests the CALIBRATED lower advantage against theta; MARGIN
        tests the raw defer-minus-enter dollars.  A row whose calibrated
        lower advantage is negative can still clear a positive margin theta.
        """

        state = _margin_state(_margin_components(enter_regret=100.0,
                                                 defer_regret=400.0))
        admission = _margin_admission(250.0)
        self.assertIs(decide(state, admission).action, DecisionAction.DEFER)
        self.assertEqual(decide(state, admission).reason,
                         "ADMISSION_ADVANTAGE")
        self.assertIs(decide_margin(state, admission).action,
                      DecisionAction.ENTER)

    def test_argmin_pass_row_is_never_passed_by_the_margin_rule(self):
        """The argmin pre-stage is removed: only the cap can PASS."""

        components = _margin_components(enter_regret=900.0, defer_regret=900.0,
                                        pass_regret=100.0)
        state = _margin_state(components)
        admission = _margin_admission(-1.0)
        self.assertIs(decide(state, admission).action, DecisionAction.PASS)
        self.assertEqual(decide(state, admission).reason,
                         "MINIMUM_REGRET_PASS")
        self.assertIs(decide_margin(state, admission).action,
                      DecisionAction.ENTER)


class MarginModeThreadingTest(unittest.TestCase):
    """Spec item 2: policy_mode threads through both walk implementations."""

    def _fixture(self):
        from .test_tabular_walk_twin import _wtwin_fixture
        return _wtwin_fixture()

    def _calibration(self):
        from .test_tabular_walk_twin import _WtwinCalibrationStub
        return _WtwinCalibrationStub()

    def _admission(self, threshold, index=10):
        from .test_tabular_walk_twin import _wtwin_admission
        return _wtwin_admission(threshold, index)

    def test_argmin_is_the_default_of_the_oracle_and_the_twin(self):
        from .tabular_live_replay import replay_policy_day
        from .tabular_walk_twin import replay_policy_day_twin
        admission = self._admission(0.0)
        default = replay_policy_day(mode="CALIBRATED",
            calibration=self._calibration(), admission=admission,
            **self._fixture())
        explicit = replay_policy_day(mode="CALIBRATED", policy_mode="ARGMIN",
            calibration=self._calibration(), admission=admission,
            **self._fixture())
        twin = replay_policy_day_twin(mode="CALIBRATED",
            policy_mode="ARGMIN", calibration=self._calibration(),
            admission=admission, **self._fixture())
        self.assertEqual(explicit.receipt_sha256, default.receipt_sha256)
        self.assertEqual(twin.receipt_sha256, default.receipt_sha256)

    def test_margin_mode_changes_the_day_and_the_trace_identity(self):
        from .tabular_live_replay import replay_policy_day
        admission = self._admission(0.0)
        argmin = replay_policy_day(mode="CALIBRATED",
            calibration=self._calibration(), admission=admission,
            **self._fixture())
        margin = replay_policy_day(mode="CALIBRATED", policy_mode="MARGIN",
            calibration=self._calibration(), admission=admission,
            **self._fixture())
        # Second 0: A margin 4 and C margin 0 both clear theta 0; the argmin
        # rule enters A and PASSES C on its own minimum-regret pre-stage.
        self.assertEqual(argmin.selected_opportunity_ids, ("A-0", "B-1"))
        self.assertEqual(margin.selected_opportunity_ids,
                         ("A-0", "C-0", "B-1"))
        self.assertNotEqual(margin.receipt_sha256, argmin.receipt_sha256)
        self.assertEqual(margin.policy_mode, "MARGIN")
        self.assertEqual(argmin.policy_mode, "ARGMIN")

    def test_margin_twin_matches_the_margin_oracle(self):
        from .tabular_live_replay import replay_policy_day
        from .tabular_walk_twin import replay_policy_day_twin
        admission = self._admission(0.0)
        oracle = replay_policy_day(mode="CALIBRATED", policy_mode="MARGIN",
            calibration=self._calibration(), admission=admission,
            **self._fixture())
        twin = replay_policy_day_twin(mode="CALIBRATED", policy_mode="MARGIN",
            calibration=self._calibration(), admission=admission,
            **self._fixture())
        self.assertEqual(twin.receipt_sha256, oracle.receipt_sha256)

    def test_margin_multistate_matches_sequential_margin_walks(self):
        from .tabular_live_replay import replay_policy_day
        from .tabular_walk_twin import replay_policy_day_multistate
        thresholds = (-1.0e6, -8.0, 0.0, 1.0, 4.0, 5.0, 1.0e6)
        admissions = tuple(self._admission(value, index)
                           for index, value in enumerate(thresholds))
        sequential = tuple(replay_policy_day(mode="CALIBRATED",
            policy_mode="MARGIN", calibration=self._calibration(),
            admission=admission, **self._fixture())
            for admission in admissions)
        batched = replay_policy_day_multistate(admissions=admissions,
            policy_mode="MARGIN", calibration=self._calibration(),
            **self._fixture())
        self.assertEqual(tuple(row.receipt_sha256 for row in batched),
                         tuple(row.receipt_sha256 for row in sequential))
        self.assertGreater(len({row.selected_opportunity_ids
                                for row in sequential}), 1)

    def test_margin_mode_refuses_outside_calibrated(self):
        from .tabular_live_replay import replay_policy_day
        from .tabular_recovery_contracts import RecoveryRefusal
        from .tabular_walk_twin import replay_policy_day_twin
        for runner in (replay_policy_day, replay_policy_day_twin):
            with self.subTest(runner=runner.__name__):
                with self.assertRaises(RecoveryRefusal):
                    runner(mode="RAW", policy_mode="MARGIN", **self._fixture())

    def test_unknown_policy_mode_refuses(self):
        from .tabular_live_replay import replay_policy_day
        from .tabular_recovery_contracts import RecoveryRefusal
        with self.assertRaises(RecoveryRefusal):
            replay_policy_day(mode="CALIBRATED", policy_mode="ARGMAX",
                calibration=self._calibration(),
                admission=self._admission(0.0), **self._fixture())

    def test_margin_trace_survives_a_save_reload_round_trip(self):
        import tempfile
        from pathlib import Path
        from .tabular_live_replay import (
            load_policy_day_trace, replay_policy_day, save_policy_day_trace,
        )
        margin = replay_policy_day(mode="CALIBRATED", policy_mode="MARGIN",
            calibration=self._calibration(),
            admission=self._admission(0.0), **self._fixture())
        with tempfile.TemporaryDirectory(dir="/workspace/artifacts") as room:
            target = Path(room) / "margin_trace.json"
            save_policy_day_trace(margin, target)
            stored = load_policy_day_trace(target)
        self.assertEqual(stored.receipt_sha256, margin.receipt_sha256)
        self.assertEqual(stored.policy_mode, "MARGIN")


if __name__ == "__main__":  # pragma: no cover - manual invocation
    unittest.main()
