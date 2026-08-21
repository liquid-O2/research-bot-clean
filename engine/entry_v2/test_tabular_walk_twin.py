"""Contract tests for the vectorized walk twin (R2/R3 speed levers)."""

from __future__ import annotations

import dataclasses
import math
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from . import common as C
from .exact_delayed_teacher import DayOptionUniverse
from .tabular_calibration import AdmissionContract
from .tabular_delayed_corpus import CausalFeatureShard
from .tabular_live_replay import replay_policy_day, save_policy_day_trace
from .tabular_action_features import ACTION_STATE_FEATURE_NAMES
from .tabular_recovery_contracts import (
    COMPONENT_STACK_NAMES, CausalFeatureSchema, RecoveryRefusal,
)
from . import tabular_walk_twin as WTWIN
from .tabular_walk_twin import (
    replay_policy_day_multistate, replay_policy_day_twin,
    wtwin_load_or_replay_day_multistate, wtwin_reset_walk_invocations,
    wtwin_walk_invocations,
)


WTWIN_TEST_DAY = 20210709
WTWIN_TEST_T0 = 1_625_000_000_000_000_000
WTWIN_FEATURE_NAMES = ("f_tag", "f_enter", "f_defer", "f_pass")
_HEX = "0123456789abcdef"


def _wtwin_sha(seed: int) -> str:
    return "".join(_HEX[(seed * 7 + index * 11) % 16] for index in range(64))


def _wtwin_rows(regret_table):
    """Hand-written mini-day roster: (series, asset, second, regrets)."""

    rows = []
    for tag, (series, asset, second, regrets) in enumerate(regret_table):
        rows.append({
            "tag": tag, "series": series, "asset": asset,
            "ts": WTWIN_TEST_T0 + second * 1_000_000_000,
            "regrets": regrets,
            "uid": f"{series}-{second}",
        })
    return rows


def _wtwin_universe(rows, exits):
    count = len(rows)
    take = lambda key, dtype: np.asarray([row[key] for row in rows], dtype)
    timestamps = take("ts", np.int64)
    exit_ts = np.asarray([exits.get(row["uid"], row["ts"]) for row in rows], np.int64)
    return DayOptionUniverse(
        opportunity_id=take("uid", str), series_id=take("series", str),
        candidate_id=take("uid", str), asset=take("asset", str),
        day=np.full(count, WTWIN_TEST_DAY, np.int64),
        side=np.ones(count, np.int8), phase=np.asarray(["NY"] * count, str),
        watch_start_ts_ns=timestamps, snapshot_ts_ns=timestamps,
        phase_close_ts_ns=exit_ts,
        event_cutoff=np.full(count, 2, np.int64),
        entry_event_ordinal=np.ones(count, np.int64),
        entry_availability_ts_ns=timestamps - 1,
        signed_pnl_cents=np.full(count, 1000, np.int64),
        phase_close_pnl_cents=np.full(count, 1000, np.int64),
        phase_exit_ts_ns=exit_ts,
        mfe_usd=np.full(count, 20.0), mae_usd=np.full(count, 1.0),
        wall_hit=np.zeros(count, bool), wall_hit_ts_ns=exit_ts,
        wall_pnl_usd=np.full(count, 10.0), exit_ts_ns=exit_ts,
        event_prefix_receipt_sha256=np.asarray(
            [_wtwin_sha(index) for index in range(count)], str),
        source_outcome_sha256=(_wtwin_sha(101),))


def _wtwin_shards(rows):
    shards = []
    for asset in sorted({row["asset"] for row in rows}):
        local = [row for row in rows if row["asset"] == asset]
        count = len(local)
        matrix = np.asarray(
            [[float(row["tag"]), *map(float, row["regrets"])] for row in local],
            np.float32)
        timestamps = np.asarray([row["ts"] for row in local], np.int64)
        shards.append(CausalFeatureShard(
            feature_names=WTWIN_FEATURE_NAMES, features=matrix,
            opportunity_id=np.asarray([row["uid"] for row in local], str),
            series_id=np.asarray([row["series"] for row in local], str),
            candidate_id=np.asarray([row["uid"] for row in local], str),
            asset=np.asarray([asset] * count, str),
            day=np.full(count, WTWIN_TEST_DAY, np.int64),
            side=np.ones(count, np.int8), phase=np.asarray(["NY"] * count, str),
            snapshot_ts_ns=timestamps,
            event_cutoff=np.full(count, 2, np.int64),
            entry_event_ordinal=np.ones(count, np.int64),
            entry_availability_ts_ns=timestamps - 1,
            watch_age_sec=np.zeros(count, np.int64),
            sampling_reason=np.ones(count, np.int16),
            feature_receipt_sha256=np.asarray(
                [_wtwin_sha(200 + row["tag"]) for row in local], str),
            base_config_sha256=_wtwin_sha(11),
            sampling_receipt_sha256=_wtwin_sha(12),
            source_receipts=(_wtwin_sha(13),)))
    return tuple(shards)


class _WtwinComponentStub:
    """Fixed, contract-legal component predictions for every causal row."""

    feature_names = WTWIN_FEATURE_NAMES
    receipt_sha256 = _wtwin_sha(21)

    class _Frame:
        def __init__(self, values): self.values = values

    def predict(self, matrix):
        row = (10.0, 20.0, 30.0, 10.0, 20.0, 30.0, 0.1, 5.0, 60.0, 120.0)
        return self._Frame(np.tile(np.asarray(row, np.float64),
                                   (len(np.asarray(matrix)), 1)))


class _WtwinActionStub:
    """Regrets read straight out of the causal tag columns, plus ULP nudges."""

    feature_names = (WTWIN_FEATURE_NAMES + COMPONENT_STACK_NAMES
                     + tuple(ACTION_STATE_FEATURE_NAMES))
    receipt_sha256 = _wtwin_sha(22)

    def __init__(self, nudge=None):
        self.nudge = dict(nudge or {})

    def predict_regret_usd(self, x):
        values = np.asarray(x, np.float64)
        regrets = values[:, 1:4].copy()
        for local, tag in enumerate(values[:, 0].tolist()):
            step = self.nudge.get(int(round(tag)))
            if step is not None:
                column, direction = step
                regrets[local, column] = np.nextafter(
                    regrets[local, column], direction)
        return regrets


class _WtwinPlattStub:
    def predict(self, values):
        return 1.0 / (1.0 + np.exp(-np.clip(
            np.asarray(values, np.float64) / 600.0, -40, 40)))


class _WtwinCalibrationStub:
    """Identity dollar/lower mapping so thresholds alone separate the states."""

    state_conditioned = False
    receipt_sha256 = _wtwin_sha(31)
    enter_optimal_platt = _WtwinPlattStub()

    def predict_dollars(self, values, *, group_key=None):
        return np.asarray(values, np.float64).copy()

    def predict_lower(self, values, *, group_key=None):
        return np.asarray(values, np.float64).copy()


def _wtwin_admission(threshold: float, index: int) -> AdmissionContract:
    return AdmissionContract(-1.0e9, 1.0, 1.0e9, float(threshold), index,
                             _wtwin_sha(31), _wtwin_sha(41))


# Hand-written mini-day.  Second 0: series A enters (regret 1 beats 5/5),
# series B defers (defer 1 <= pass 5), series C passes (defer 9 > pass 1).
# A's position exits at second 0, so second 1 frees SI and B — now the
# strongest ENTER — takes the second seat.  Second 2 has no live row left.
_WTWIN_MINI_DAY = (
    ("A", "SI", 0, (1.0, 5.0, 5.0)),
    ("B", "SI", 0, (9.0, 1.0, 5.0)),
    ("C", "HG", 0, (9.0, 9.0, 1.0)),
    ("A", "SI", 1, (1.0, 5.0, 5.0)),
    ("B", "SI", 1, (1.0, 5.0, 5.0)),
    ("C", "HG", 1, (9.0, 9.0, 1.0)),
    ("A", "SI", 2, (1.0, 5.0, 5.0)),
    ("B", "SI", 2, (1.0, 5.0, 5.0)),
    ("C", "HG", 2, (9.0, 9.0, 1.0)),
)
_WTWIN_TIED_DAY = (
    ("A", "SI", 0, (5.0, 5.0, 5.0)),
)


def _wtwin_fixture(table=_WTWIN_MINI_DAY, nudge=None):
    rows = _wtwin_rows(table)
    exits = {"A-0": WTWIN_TEST_T0, "B-1": WTWIN_TEST_T0 + 1_000_000_000}
    schema = CausalFeatureSchema(WTWIN_FEATURE_NAMES, _wtwin_sha(51))
    return {"universe": _wtwin_universe(rows, exits),
            "dense_feature_shards": _wtwin_shards(rows),
            "feature_schema": schema,
            "component_model": _WtwinComponentStub(),
            "action_model": _WtwinActionStub(nudge)}


class WalkTwinContractTest(unittest.TestCase):

    def test_raw_mini_day_matches_hand_derived_trades(self):
        expected = ("A-0", "B-1")
        oracle = replay_policy_day(mode="RAW", **_wtwin_fixture())
        self.assertEqual(oracle.selected_opportunity_ids, expected)
        twin = replay_policy_day_twin(mode="RAW", **_wtwin_fixture())
        self.assertEqual(twin.selected_opportunity_ids, expected)
        self.assertEqual(twin.receipt_sha256, oracle.receipt_sha256)

    def test_raw_mini_day_crossings_and_changes_are_hand_derived(self):
        second_one = WTWIN_TEST_T0 + 1_000_000_000
        twin = replay_policy_day_twin(mode="RAW", **_wtwin_fixture())
        self.assertEqual(dict(twin.policy_crossing_timestamps),
                         {"B": (second_one,)})
        self.assertEqual(dict(twin.action_change_timestamps),
                         {"B": (second_one,)})

    def test_calibrated_twin_matches_oracle_receipt(self):
        admission = _wtwin_admission(0.0, 10)
        oracle = replay_policy_day(mode="CALIBRATED",
            calibration=_WtwinCalibrationStub(), admission=admission,
            **_wtwin_fixture())
        twin = replay_policy_day_twin(mode="CALIBRATED",
            calibration=_WtwinCalibrationStub(), admission=admission,
            **_wtwin_fixture())
        self.assertEqual(twin.receipt_sha256, oracle.receipt_sha256)
        self.assertEqual(twin.selected_opportunity_ids,
                         oracle.selected_opportunity_ids)

    def test_proposals_are_collected_row_for_row(self):
        oracle = replay_policy_day(mode="RAW", collect_proposals=True,
                                   **_wtwin_fixture())
        twin = replay_policy_day_twin(mode="RAW", collect_proposals=True,
                                      **_wtwin_fixture())
        self.assertEqual(twin.receipt_sha256, oracle.receipt_sha256)
        self.assertEqual(
            tuple((row.opportunity_id, row.predicted_action.value)
                  for row in twin.proposals),
            tuple((row.opportunity_id, row.predicted_action.value)
                  for row in oracle.proposals))

    def test_multistate_equals_sequential_walks_per_threshold(self):
        thresholds = (-1.0e6, -8.0, 0.0, 3.0, 4.0, 4.5, 1.0e6)
        admissions = tuple(_wtwin_admission(value, index)
                           for index, value in enumerate(thresholds))
        sequential = tuple(replay_policy_day(mode="CALIBRATED",
            calibration=_WtwinCalibrationStub(), admission=admission,
            **_wtwin_fixture()) for admission in admissions)
        batched = replay_policy_day_multistate(admissions=admissions,
            calibration=_WtwinCalibrationStub(), **_wtwin_fixture())
        self.assertEqual(len(batched), len(admissions))
        self.assertEqual(
            tuple(row.receipt_sha256 for row in batched),
            tuple(row.receipt_sha256 for row in sequential))
        self.assertEqual(
            tuple(row.selected_opportunity_ids for row in batched),
            tuple(row.selected_opportunity_ids for row in sequential))
        self.assertGreater(len({row.selected_opportunity_ids
                                for row in sequential}), 1)

    def test_one_ulp_regret_perturbation_flips_the_receipt(self):
        base = replay_policy_day_twin(mode="RAW",
            **_wtwin_fixture(table=_WTWIN_TIED_DAY))
        self.assertEqual(base.selected_opportunity_ids, ())
        mutant = replay_policy_day_twin(mode="RAW",
            **_wtwin_fixture(table=_WTWIN_TIED_DAY, nudge={0: (0, -math.inf)}))
        self.assertEqual(mutant.selected_opportunity_ids, ("A-0",))
        self.assertNotEqual(mutant.receipt_sha256, base.receipt_sha256)


class _WtwinMalformedComponentStub(_WtwinComponentStub):
    """Component stub whose fixed row violates one contract clause."""

    def __init__(self, row) -> None:
        self.row = tuple(row)

    def predict(self, matrix):
        return self._Frame(np.tile(np.asarray(self.row, np.float64),
                                   (len(np.asarray(matrix)), 1)))


# (current_q20, q50, q80, cont_q20, q50, q80, wall_p, mae_q90, occ_q50, occ_q90)
_WTWIN_LEGAL_COMPONENT_ROW = (10.0, 20.0, 30.0, 10.0, 20.0, 30.0, 0.1,
                              5.0, 60.0, 120.0)
_WTWIN_MALFORMED_COMPONENT_ROWS = {
    "wall_probability_above_one": (10.0, 20.0, 30.0, 10.0, 20.0, 30.0, 1.5,
                                   5.0, 60.0, 120.0),
    "negative_mae_q90": (10.0, 20.0, 30.0, 10.0, 20.0, 30.0, 0.1, -5.0,
                         60.0, 120.0),
    "current_q20_above_q50": (30.0, 20.0, 30.0, 10.0, 20.0, 30.0, 0.1, 5.0,
                              60.0, 120.0),
    "occupancy_q50_above_q90": (10.0, 20.0, 30.0, 10.0, 20.0, 30.0, 0.1, 5.0,
                                300.0, 120.0),
    "nan_current_q50": (10.0, float("nan"), 30.0, 10.0, 20.0, 30.0, 0.1, 5.0,
                        60.0, 120.0),
}


class WalkTwinRefusalParityTest(unittest.TestCase):
    """design-F9 / temporal-13: the twin must refuse where the oracle refuses,
    with the same exception type AND the same message — a twin that refuses
    later, or with a different class, is not a drop-in replacement."""

    def _both(self, fixture_factory):
        outcomes = []
        for walk in (replay_policy_day, replay_policy_day_twin):
            try:
                walk(mode="RAW", **fixture_factory())
                outcomes.append(("NO_REFUSAL", ""))
            except BaseException as exc:  # parity includes the exception TYPE
                outcomes.append((type(exc).__name__, str(exc)))
        return outcomes

    def test_malformed_component_rows_refuse_identically(self):
        for name, row in _WTWIN_MALFORMED_COMPONENT_ROWS.items():
            with self.subTest(row=name):
                def factory():
                    fixture = _wtwin_fixture()
                    fixture["component_model"] = _WtwinMalformedComponentStub(row)
                    return fixture
                oracle, twin = self._both(factory)
                self.assertEqual(oracle, twin)
                self.assertEqual(oracle[0], "RecoveryRefusal")

    def test_legal_component_row_is_not_refused_by_either_walk(self):
        def factory():
            fixture = _wtwin_fixture()
            fixture["component_model"] = _WtwinMalformedComponentStub(
                _WTWIN_LEGAL_COMPONENT_ROW)
            return fixture
        oracle, twin = self._both(factory)
        self.assertEqual(oracle, ("NO_REFUSAL", ""))
        self.assertEqual(twin, ("NO_REFUSAL", ""))

    def test_unknown_asset_refuses_identically(self):
        def factory():
            fixture = _wtwin_fixture()
            shards = list(fixture["dense_feature_shards"])
            head = shards[0]
            shards[0] = dataclasses.replace(head, asset=np.asarray(
                ["XX"] * len(np.asarray(head.asset)), str))
            fixture["dense_feature_shards"] = tuple(shards)
            return fixture
        oracle, twin = self._both(factory)
        self.assertEqual(oracle, twin)
        self.assertEqual(oracle[0], "RecoveryRefusal")


class WalkTwinAdmissionClauseTest(unittest.TestCase):
    """I3: each admission clause bound INDEPENDENTLY, oracle vs twin.

    The stub component row carries current_q20=10, wall probability=0.1 and
    mae_q90=5; each contract below binds exactly one clause against it
    (11 / 0.05 / 4) and holds the other two open, so a clause dropped from
    ``wtwin_state_action_codes`` shows up as a live trade the oracle refuses.
    """

    _CLAUSES = {
        "minimum_current_q20_usd": (11.0, 1.0, 1.0e9),
        "maximum_wall_probability": (-1.0e9, 0.05, 1.0e9),
        "maximum_adverse_q90_usd": (-1.0e9, 1.0, 4.0),
    }

    def test_each_clause_blocks_entry_in_both_walks(self):
        for name, (q20, wall, adverse) in self._CLAUSES.items():
            with self.subTest(clause=name):
                admission = AdmissionContract(q20, wall, adverse, 0.0, 10,
                                              _wtwin_sha(31), _wtwin_sha(41))
                oracle = replay_policy_day(mode="CALIBRATED",
                    calibration=_WtwinCalibrationStub(), admission=admission,
                    **_wtwin_fixture())
                twin = replay_policy_day_twin(mode="CALIBRATED",
                    calibration=_WtwinCalibrationStub(), admission=admission,
                    **_wtwin_fixture())
                self.assertEqual(twin.receipt_sha256, oracle.receipt_sha256)
                self.assertEqual(oracle.selected_opportunity_ids, ())

    def test_open_contract_admits_the_hand_derived_trades(self):
        admission = AdmissionContract(-1.0e9, 1.0, 1.0e9, 0.0, 10,
                                      _wtwin_sha(31), _wtwin_sha(41))
        oracle = replay_policy_day(mode="CALIBRATED",
            calibration=_WtwinCalibrationStub(), admission=admission,
            **_wtwin_fixture())
        twin = replay_policy_day_twin(mode="CALIBRATED",
            calibration=_WtwinCalibrationStub(), admission=admission,
            **_wtwin_fixture())
        self.assertEqual(oracle.selected_opportunity_ids, ("A-0", "B-1"))
        self.assertEqual(twin.receipt_sha256, oracle.receipt_sha256)


class _WtwinFoldStub:
    """Stands in for a SeedModelRoster fold row (bundle path + its receipt)."""

    def __init__(self, bundle_path: str, receipt: str) -> None:
        self.bundle_path = bundle_path
        self.bundle_receipt_sha256 = receipt


class WalkTwinMultistateCacheHelperTest(unittest.TestCase):
    """C2: the Edit-1 helper as reviewed bytes, cache semantics included."""

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(
            dir=str(C.REPO_ROOT / "artifacts" / "cache"),
            prefix="wtwin_helper_test_"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.fixture = _wtwin_fixture()
        self.calibration = _WtwinCalibrationStub()
        self.admissions = tuple(_wtwin_admission(value, index) for index, value
                                in enumerate((-1.0e6, -8.0, 0.0, 4.5, 1.0e6)))
        self.component_fold = _WtwinFoldStub(
            "component.cbm", self.fixture["component_model"].receipt_sha256)
        self.action_fold = _WtwinFoldStub(
            "action.cbm", self.fixture["action_model"].receipt_sha256)
        wtwin_reset_walk_invocations()

    def _call(self, **overrides):
        kwargs = {
            "day": WTWIN_TEST_DAY, "universe": self.fixture["universe"],
            "feature_schema": self.fixture["feature_schema"],
            "component_fold": self.component_fold,
            "action_fold": self.action_fold, "output_root": self.root,
            "calibration": self.calibration, "admissions": self.admissions,
            "dense_features": self.fixture["dense_feature_shards"]}
        kwargs.update(overrides)
        with mock.patch.object(
                WTWIN, "load_component_model",
                return_value=self.fixture["component_model"]), \
             mock.patch.object(
                WTWIN, "load_action_model",
                return_value=self.fixture["action_model"]):
            return wtwin_load_or_replay_day_multistate(**kwargs)

    def _sequential(self):
        return tuple(replay_policy_day(mode="CALIBRATED",
            calibration=self.calibration, admission=admission, **_wtwin_fixture())
            for admission in self.admissions)

    def _targets(self):
        return tuple(WTWIN._wtwin_multistate_targets(
            day=WTWIN_TEST_DAY, universe=self.fixture["universe"],
            component_receipt=self.component_fold.bundle_receipt_sha256,
            action_receipt=self.action_fold.bundle_receipt_sha256,
            feature_schema=self.fixture["feature_schema"],
            calibration=self.calibration, admissions=self.admissions,
            output_root=self.root))

    def test_target_paths_equal_the_theta_loop_path_construction(self):
        """The helper must address the SAME per-theta trace cache the eval
        loop already writes; a forked path silently orphans every cached
        trace.  Built here from tabular_evaluation's own pieces, not from the
        helper's output."""

        from .tabular_evaluation import _trace_identity
        expected = tuple(
            self.root / "calibrated" / _trace_identity(
                day=WTWIN_TEST_DAY, mode="CALIBRATED",
                universe=self.fixture["universe"],
                component_receipt=self.component_fold.bundle_receipt_sha256,
                action_receipt=self.action_fold.bundle_receipt_sha256,
                feature_schema=self.fixture["feature_schema"],
                calibration=self.calibration, admission=admission)
            / f"{WTWIN_TEST_DAY}.json"
            for admission in self.admissions)
        self.assertEqual(self._targets(), expected)

    def test_cold_cache_walks_once_and_matches_sequential_oracle(self):
        traces = self._call()
        self.assertEqual(wtwin_walk_invocations(), 1)
        self.assertEqual(
            tuple(row.receipt_sha256 for row in traces),
            tuple(row.receipt_sha256 for row in self._sequential()))
        self.assertTrue(all(path.is_file() for path in self._targets()))

    def test_fully_cached_day_returns_without_walking(self):
        self._call()
        wtwin_reset_walk_invocations()
        traces = self._call(dense_features=None)
        self.assertEqual(wtwin_walk_invocations(), 0)
        self.assertEqual(len(traces), len(self.admissions))

    def test_fold_receipt_mismatch_refuses_before_any_cache_consult(self):
        self._call()
        for path in self._targets():
            self.assertTrue(path.is_file())
        bad = _WtwinFoldStub("action.cbm", _wtwin_sha(99))
        with self.assertRaises(RecoveryRefusal) as caught:
            self._call(action_fold=bad, dense_features=None)
        self.assertIn("policy replay fold model strict load differs",
                      str(caught.exception))

    def test_partial_cache_walks_all_and_asserts_receipt_equality(self):
        sequential = self._sequential()
        targets = self._targets()
        save_policy_day_trace(sequential[0], targets[0])
        wtwin_reset_walk_invocations()
        traces = self._call()
        self.assertEqual(wtwin_walk_invocations(), 1)
        self.assertEqual(
            tuple(row.receipt_sha256 for row in traces),
            tuple(row.receipt_sha256 for row in sequential))
        self.assertTrue(all(path.is_file() for path in targets))

    def test_partial_cache_receipt_drift_refuses_instead_of_recomputing(self):
        sequential = self._sequential()
        targets = self._targets()
        # A trace produced under a DIFFERENT admission parked at this target:
        # the fresh walk must notice and refuse, not silently overwrite.
        save_policy_day_trace(sequential[-1], targets[0])
        with self.assertRaises(RecoveryRefusal) as caught:
            self._call()
        self.assertIn("cached multistate trace receipt differs",
                      str(caught.exception))

    def test_walk_returning_wrong_trace_count_refuses(self):
        with mock.patch.object(WTWIN, "replay_policy_day_multistate",
                               return_value=()):
            with self.assertRaises(RecoveryRefusal) as caught:
                self._call()
        self.assertIn("multistate walk trace count differs",
                      str(caught.exception))

    def test_missing_dense_shards_refuse_when_a_walk_is_needed(self):
        with self.assertRaises(RecoveryRefusal) as caught:
            self._call(dense_features=None)
        self.assertIn("multistate walk has no dense causal shards",
                      str(caught.exception))


if __name__ == "__main__":
    unittest.main()
