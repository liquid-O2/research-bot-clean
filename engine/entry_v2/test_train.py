#!/usr/bin/env python3
"""Synthetic adversarial test for the complete entry-v2 learning protocol."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
from types import SimpleNamespace
from typing import Iterator
import gc
import hashlib
import threading
import time
import unittest
import weakref

import numpy as np
import torch

from engine.entry_v2 import common as C
from engine.entry_v2 import train as T
from engine.entry_v2.contracts import (
    AssetDayRegime,
    CausalEntryExample,
    ContractError,
    RawPrefixRef,
    SessionRef,
    Side,
)
from engine.entry_v2.folds import FoldSpec
from engine.entry_v2.event_pack import (
    CATEGORY_SIZES as EVENT_CATEGORY_SIZES,
    CATEGORICAL_FIELDS,
    CONTINUOUS_FIELDS,
)
from engine.entry_v2.model import FullPrefixEntryModel
from engine.entry_v2.policy import AssetPolicy, ModelInputBinding, PolicyConfig
from engine.entry_v2.replay import ReplayOutcome, replay
from engine.entry_v2.teacher import TeacherPath, TeacherStore, build_teacher_store
from engine.entry_v2.session_stream import MODEL_ARRAYS_CONVERSION_LAW_SHA256
from engine.entry_v2.train import (
    ARM_NAMES,
    ARM_FULL_PREFIX,
    ARM_PER_ASSET_STATIC,
    ARM_POOLED_STATIC,
    EntryLearningSystem,
    EntrySessionBatch,
    EntrySessionSpec,
    ReplayCalibrationData,
    SelfSupervisedTargets,
    TrainFoldNormalizer,
    TrainingConfig,
    run_fold_oof,
    run_shuffled_control_oof,
)


FIT_DAY, CALIBRATION_DAY, SELECTION_DAY, TEST_DAY = (
    20240102, 20240103, 20240104, 20240105
)
ASSETS = ("SI", "HG", "NKD")
CATEGORY_SIZES = EVENT_CATEGORY_SIZES
NS = 1_000_000_000


@dataclass(frozen=True)
class _MemorySessionSource:
    """Test-only source preserving the production context-managed API."""

    qre2_path: str
    source_sha256: str
    asset: str
    d8: int
    locked_iid: int
    max_cutoff: int
    event_continuous: torch.Tensor
    event_categorical: torch.Tensor

    @contextmanager
    def open_batch(self, spec: EntrySessionSpec) -> Iterator[EntrySessionBatch]:
        batch = EntrySessionBatch(
            examples=spec.examples,
            event_continuous=self.event_continuous,
            event_categorical=self.event_categorical,
            candidate_cutoffs=spec.candidate_cutoffs,
            candidate_features=spec.candidate_features,
            context_values=spec.context_values,
            context_type_ids=spec.context_type_ids,
            context_valid=spec.context_valid,
            self_supervised=spec.self_supervised,
        )
        batch.validate()
        yield batch


def _binding() -> ModelInputBinding:
    return ModelInputBinding(
        tuple(CONTINUOUS_FIELDS),
        tuple(CATEGORICAL_FIELDS),
        tuple(EVENT_CATEGORY_SIZES),
        MODEL_ARRAYS_CONVERSION_LAW_SHA256,
        C.object_sha256("synthetic-session-stream-receipts"),
        C.object_sha256("synthetic-corpus-receipt"),
        C.object_sha256("synthetic-corpus-source-lineage"),
        C.object_sha256("synthetic-clock-law-receipt"),
    )


def _fold() -> FoldSpec:
    fold = FoldSpec(
        "SYNTH",
        FIT_DAY,
        FIT_DAY,
        TEST_DAY,
        TEST_DAY,
        (FIT_DAY,),
        (CALIBRATION_DAY, SELECTION_DAY),
        (TEST_DAY,),
        ((CALIBRATION_DAY,), (SELECTION_DAY,)),
    )
    fold.validate()
    return fold


def _winner(day: int) -> float:
    return {
        FIT_DAY: 4_800.0,
        CALIBRATION_DAY: 4_900.0,
        SELECTION_DAY: 5_000.0,
        TEST_DAY: 5_200.0,
    }[day]


def _fixture() -> tuple[
    tuple[EntrySessionSpec, ...], TeacherStore, ReplayCalibrationData
]:
    batches: list[EntrySessionSpec] = []
    paths: list[TeacherPath] = []
    outcomes: dict[str, ReplayOutcome] = {}
    sessions: list[SessionRef] = []
    regimes: list[AssetDayRegime] = []
    negatives = (-100.0, -200.0, -300.0, -400.0)
    for day_index, day in enumerate(
        (FIT_DAY, CALIBRATION_DAY, SELECTION_DAY, TEST_DAY)
    ):
        for asset_index, asset in enumerate(ASSETS):
            generator = torch.Generator().manual_seed(
                10_000 + 100 * day_index + asset_index
            )
            session_id = f"{asset}-{day}"
            sessions.append(SessionRef(asset, day, session_id))
            regimes.append(AssetDayRegime(asset, day, "LOW", day * NS))
            examples: list[CausalEntryExample] = []
            row_count = 30 if day == CALIBRATION_DAY else 5
            values = (
                _winner(day),
                *(negatives[index % len(negatives)] for index in range(row_count - 1)),
            )
            cutoffs = tuple(4 * (index + 1) for index in range(row_count))
            for row, (cutoff, value) in enumerate(zip(cutoffs, values)):
                decision = (
                    1_000_000_000_000
                    + day_index * 1_000_000_000_000
                    + asset_index * 100_000_000_000
                    + (0 if day == CALIBRATION_DAY else row * 10_000_000_000)
                )
                candidate_id = f"{asset}-{day}-c{row}"
                example = CausalEntryExample(
                    candidate_id=candidate_id,
                    asset=asset,
                    trading_day=day,
                    session_id=session_id,
                    decision_ts_ns=decision,
                    side=Side.LONG,
                    phase="SYNTH",
                    locked_iid=asset_index,
                    raw_prefix_ref=RawPrefixRef(
                        shard=f"events/{asset}/{day}.qre2",
                        event_start_index=0,
                        event_end_index=cutoff,
                        event_count=cutoff,
                        first_availability_ts_ns=decision - 1_000,
                        last_availability_ts_ns=decision - 1,
                        source_hash="a" * 64,
                    ),
                    causal_features={"spread_ticks": float(row + 1)},
                    lineage_hash="b" * 64,
                )
                examples.append(example)
                exit_ts = decision + 1_000_000_000
                paths.append(
                    TeacherPath(
                        candidate_id,
                        asset,
                        day,
                        decision,
                        exit_ts,
                        value,
                        max(value, 0.0) + 50.0,
                        100.0,
                        False,
                        1.0,
                    )
                )
                outcomes[candidate_id] = ReplayOutcome(
                    candidate_id,
                    exit_ts,
                    value,
                    exit_ts,
                    value,
                )
            categorical = torch.stack(
                [
                    torch.randint(size, (max(cutoffs),), generator=generator)
                    for size in CATEGORY_SIZES
                ],
                dim=1,
            )
            self_supervised = SelfSupervisedTargets(
                horizon_value=torch.randn((row_count, 4), generator=generator),
                horizon_valid=torch.ones((row_count, 4), dtype=torch.bool),
                phase_class=torch.arange(row_count, dtype=torch.int64) % 5,
                phase_valid=torch.ones(row_count, dtype=torch.bool),
            )
            event_continuous = torch.randn(
                (max(cutoffs), len(CONTINUOUS_FIELDS)), generator=generator)
            source = _MemorySessionSource(
                qre2_path=f"events/{asset}/{day}.qre2",
                source_sha256="a" * 64,
                asset=asset,
                d8=day,
                locked_iid=asset_index,
                max_cutoff=max(cutoffs),
                event_continuous=event_continuous,
                event_categorical=categorical,
            )
            batches.append(
                EntrySessionSpec(
                    source=source,
                    examples=tuple(examples),
                    candidate_cutoffs=torch.tensor(cutoffs, dtype=torch.int64),
                    candidate_features=torch.randn((row_count, 7), generator=generator),
                    context_values=torch.randn((row_count, 2, 6, 4), generator=generator),
                    context_type_ids=torch.tensor([1, 7], dtype=torch.int64),
                    context_valid=torch.ones((row_count, 2, 6), dtype=torch.bool),
                    self_supervised=self_supervised,
                )
            )
        # A real all-session denominator contains sessions without candidates.
        sessions.append(SessionRef("SI", day, f"SI-{day}-empty"))
    return (
        tuple(batches),
        build_teacher_store(paths, expected_sessions=sessions),
        ReplayCalibrationData(outcomes, tuple(sessions), tuple(regimes)),
    )


def _system() -> EntryLearningSystem:
    encoder = FullPrefixEntryModel(
        len(CONTINUOUS_FIELDS),
        7,
        4,
        12,
        event_category_sizes=CATEGORY_SIZES,
        n_value_bins=5,
        max_context_history=8,
    )
    return EntryLearningSystem(encoder, 8)


class _FakeAssetPolicy:
    instances: weakref.WeakSet["_FakeAssetPolicy"] = weakref.WeakSet()
    created_count = 0
    active_fits = 0
    max_active_fits = 0
    fit_threads: set[str] = set()
    lock = threading.Lock()

    def __init__(self, asset: str, _config: TrainingConfig,
                 model_input_binding: ModelInputBinding) -> None:
        self.asset = asset
        self.model_input_binding = model_input_binding
        self.score_calls = 0
        with self.__class__.lock:
            self.__class__.created_count += 1
            self.__class__.instances.add(self)

    def fit(self, X: np.ndarray, targets: dict[str, np.ndarray]):
        with self.__class__.lock:
            self.__class__.active_fits += 1
            self.__class__.max_active_fits = max(
                self.__class__.max_active_fits,
                self.__class__.active_fits,
            )
            self.__class__.fit_threads.add(threading.current_thread().name)
        try:
            time.sleep(0.01)
            self.fit_rows = len(X)
            self.fit_value_mean = float(np.mean(targets["cert_close_usd"]))
        finally:
            with self.__class__.lock:
                self.__class__.active_fits -= 1
        return self

    def raw_predict(self, X: np.ndarray) -> dict[str, np.ndarray]:
        return {"action_raw": np.linspace(0.9, 0.1, len(X))}

    def calibrate(self, _raw: dict[str, np.ndarray], truth: dict[str, np.ndarray]):
        self.calibration_rows = len(truth["cert_close_usd"])
        self.calibration_value_mean = float(np.mean(truth["cert_close_usd"]))
        self.score_raw_calls = 0
        return self

    def score_raw(self, raw: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
        n = len(raw["action_raw"])
        action = np.resize(np.array([0.03, 0.01, 0.01, 0.01, 0.01]), n)
        self.score_raw_calls += 1
        # One action winner freezes the exact threshold at 0.03.  The deliberately
        # terrible value lower bound proves diagnostics cannot veto it.
        lower = np.full(n, -10_000.0)
        if self.score_raw_calls == 1:
            lower[np.arange(n) % 5 == 0] = 1_000.0
        return {
            "action_p": action,
            "top3_p": np.full(n, 0.5),
            "wall_p_upper": np.full(n, 0.1),
            "expected_value_raw": action * 1_000.0,
            "expected_value_lower": lower,
            "expected_value_upper": lower + 1_000.0,
            "mae_q90": np.full(n, 100.0),
            # Deliberate trap: orchestration must derive ENTER from the
            # declared score surface, never trust this foreign field.
            "enter": np.ones(n, dtype=np.uint8),
        }

    def score(self, X: np.ndarray) -> dict[str, np.ndarray]:
        return self.score_raw(self.raw_predict(X))


class TrainContractTest(unittest.TestCase):
    def test_selected_policy_factory_cannot_replace_static_baselines(self) -> None:
        def entry_v2_selected_direct_policy_factory(*_args):
            raise AssertionError("factory identity test must not instantiate")
        dispatch = T._policy_factory_dispatch(
            selected_winner=True,
            selected_factory=entry_v2_selected_direct_policy_factory,
        )
        self.assertIs(dispatch[T.ARM_POOLED_STATIC], T._default_policy_factory)
        self.assertIs(dispatch[T.ARM_PER_ASSET_STATIC], T._default_policy_factory)
        self.assertIs(dispatch[T.ARM_FULL_PREFIX],
                      entry_v2_selected_direct_policy_factory)

    def test_selected_policy_is_fitted_once_on_train_and_held_labels_only_calibrate(self) -> None:
        batches, teacher, replay_data = _fixture()
        fold = _fold()
        fit = tuple(batch for batch in batches if batch.trading_day == FIT_DAY)
        inner = tuple(batch for batch in batches if batch.trading_day in {
            CALIBRATION_DAY, SELECTION_DAY
        })
        test = tuple(batch for batch in batches if batch.trading_day == TEST_DAY)
        fit_rows = T._static_rows(fit, teacher)
        inner_rows = T._static_rows(inner, teacher)
        test_rows = T._static_rows(test, teacher)

        class FrozenFactory:
            fit_chronology_law = T.SELECTED_POLICY_CHRONOLOGY_LAW

            def __call__(self, asset, config, binding):
                return _FakeAssetPolicy(asset, config, binding)

        def execute(rows: T._EncodedRows):
            _FakeAssetPolicy.instances.clear()
            _FakeAssetPolicy.created_count = 0
            with ThreadPoolExecutor(max_workers=4) as executor:
                prepared = T._prepare_prequential_arm(
                    T.ARM_FULL_PREFIX, fit_rows, rows, test_rows, fold,
                    replay_data, TrainingConfig(device="cpu", bf16=False),
                    _binding(), FrozenFactory(), executor,
                )
                result = T._fit_prequential_arm(prepared, test_rows, replay_data)
            policies = tuple(result.policies[asset] for asset in ASSETS)
            return (tuple(policy.fit_value_mean for policy in policies), tuple(
                policy.calibration_value_mean for policy in policies
            ), tuple(policy.fit_rows for policy in policies))

        fit_mean, calibration_mean, fit_counts = execute(inner_rows)
        changed = dict(inner_rows.targets)
        changed["cert_close_usd"] = (
            np.asarray(changed["cert_close_usd"], np.float64) + 123_456.0
        )
        mutated = replace(inner_rows, targets=changed)
        changed_fit_mean, changed_calibration_mean, changed_fit_counts = execute(mutated)
        self.assertEqual(_FakeAssetPolicy.created_count, len(ASSETS))
        self.assertEqual(fit_mean, changed_fit_mean)
        self.assertNotEqual(calibration_mean, changed_calibration_mean)
        self.assertEqual(fit_counts, (5, 5, 5))
        self.assertEqual(changed_fit_counts, fit_counts)

    def test_real_asset_policy_one_vs_four_is_bitwise_semantic_parity(self) -> None:
        """Gate coexistence before production enables four concurrent fits."""

        rng = np.random.default_rng(20260816)
        width = 11
        fit_x = rng.normal(size=(180, width)).astype(np.float32)
        calibration_x = rng.normal(size=(90, width)).astype(np.float32)
        historical_x = rng.normal(size=(37, width)).astype(np.float32)
        score_x = rng.normal(size=(40, width)).astype(np.float32)

        def targets(rows: int, offset: int) -> dict[str, np.ndarray]:
            index = np.arange(rows, dtype=np.int64) + offset
            values = np.asarray(
                (-1200.0, 250.0, 800.0, 1400.0, 2600.0),
                dtype=np.float64,
            )[index % 5]
            return {
                "take_target": (index % 4 == 0).astype(np.uint8),
                "action_loss_mask": np.ones(rows, dtype=np.uint8),
                "top3": (index % 5 == 0).astype(np.uint8),
                "cert_close_usd": values,
                "wall": (index % 6 == 0).astype(np.uint8),
                "mae_usd": (100.0 + index % 29).astype(np.float64),
            }

        fit_targets = targets(len(fit_x), 0)
        calibration_targets = targets(len(calibration_x), 7)
        frozen_inputs = {
            "fit_x": fit_x,
            "calibration_x": calibration_x,
            "historical_x": historical_x,
            "score_x": score_x,
            **{f"fit:{name}": value for name, value in fit_targets.items()},
            **{
                f"calibration:{name}": value
                for name, value in calibration_targets.items()
            },
        }
        input_sha256 = T._array_hash(frozen_inputs)
        binding = _binding()
        config = PolicyConfig()
        self.assertEqual(config.workers, 12)
        self.assertEqual(config.seed, 20260816)

        reference = AssetPolicy("SI", config, binding).fit(
            fit_x, fit_targets
        )
        reference_historical_raw = reference.raw_predict(historical_x)
        reference_calibration_raw = reference.raw_predict(calibration_x)

        barrier = threading.Barrier(4)
        worker_threads: set[str] = set()
        worker_lock = threading.Lock()

        def fit_concurrently() -> AssetPolicy:
            policy = AssetPolicy("SI", config, binding)
            with worker_lock:
                worker_threads.add(threading.current_thread().name)
            barrier.wait(timeout=5.0)
            return policy.fit(fit_x, fit_targets)

        with ThreadPoolExecutor(
            max_workers=4, thread_name_prefix="entry-v2-xgb-parity"
        ) as executor:
            futures = [executor.submit(fit_concurrently) for _ in range(4)]
            concurrent = [future.result() for future in futures]
        self.assertEqual(len(worker_threads), 4)

        model_names = ("action", "top3", "wall", "value", "pnl", "mae")

        def exact_arrays(
            expected: dict[str, np.ndarray], actual: dict[str, np.ndarray]
        ) -> None:
            self.assertEqual(set(actual), set(expected))
            for name in sorted(expected):
                np.testing.assert_array_equal(
                    actual[name], expected[name], err_msg=name
                )

        # Serialized booster bytes are the first coexistence comparison: any
        # mismatch must stop this gate before weaker prediction comparisons.
        for policy_index, policy in enumerate(concurrent):
            for name in model_names:
                reference_booster = getattr(reference, f"{name}_").get_booster()
                actual_booster = getattr(policy, f"{name}_").get_booster()
                expected_bytes = bytes(
                    reference_booster.save_raw(raw_format="ubj")
                )
                actual_bytes = bytes(actual_booster.save_raw(raw_format="ubj"))
                if actual_bytes != expected_bytes:
                    self.fail(
                        f"parallel policy {policy_index} {name} UBJ bytes differ"
                    )
                self.assertEqual(
                    actual_booster.save_config(), reference_booster.save_config()
                )
            np.testing.assert_array_equal(policy.bin_value_, reference.bin_value_)
            exact_arrays(
                reference_historical_raw,
                policy.raw_predict(historical_x),
            )

        reference.calibrate(reference_calibration_raw, calibration_targets)
        reference_scored = reference.score(score_x)

        def calibrator_state(policy: AssetPolicy) -> dict[str, object]:
            return {
                "action": policy.action_cal_.state(),
                "top3": policy.top3_cal_.state(),
                "wall": policy.wall_cal_.state(),
                "value": policy.value_cal_.state(),
            }

        reference_calibrators = calibrator_state(reference)
        for policy in concurrent:
            calibration_raw = policy.raw_predict(calibration_x)
            exact_arrays(reference_calibration_raw, calibration_raw)
            policy.calibrate(calibration_raw, calibration_targets)
            self.assertEqual(calibrator_state(policy), reference_calibrators)
            exact_arrays(reference_scored, policy.score(score_x))

        examples: list[CausalEntryExample] = []
        outcomes: dict[str, ReplayOutcome] = {}
        session_id = f"SI-{SELECTION_DAY}-xgb-parity"
        for index in range(len(score_x)):
            candidate_id = f"xgb-parity-{index:03d}"
            decision_ts_ns = 5_000_000_000_000 + index * 10_000_000_000
            examples.append(CausalEntryExample(
                candidate_id=candidate_id,
                asset="SI",
                trading_day=SELECTION_DAY,
                session_id=session_id,
                decision_ts_ns=decision_ts_ns,
                side=Side.LONG,
                phase="PARITY",
                locked_iid=0,
                raw_prefix_ref=RawPrefixRef(
                    shard="events/SI/xgb-parity.qre2",
                    event_start_index=0,
                    event_end_index=1,
                    event_count=1,
                    first_availability_ts_ns=decision_ts_ns - 2,
                    last_availability_ts_ns=decision_ts_ns - 1,
                    source_hash="c" * 64,
                ),
                causal_features={"spread_ticks": float(index + 1)},
                lineage_hash="d" * 64,
            ))
            pnl = 2400.0 if index % 8 == 0 else -150.0
            exit_ts_ns = decision_ts_ns + NS
            outcomes[candidate_id] = ReplayOutcome(
                candidate_id,
                exit_ts_ns,
                pnl,
                exit_ts_ns,
                pnl,
            )
        selection_rows = T._EncodedRows(
            tuple(examples),
            tuple(example.candidate_id for example in examples),
            tuple("SI" for _ in examples),
            np.full(len(examples), SELECTION_DAY, dtype=np.int64),
            score_x,
            {},
        )
        replay_data = ReplayCalibrationData(
            outcomes,
            (SessionRef("SI", SELECTION_DAY, session_id),),
        )
        reference_selection = T._select_inner_threshold(
            "SI", selection_rows, reference_scored,
            replay_data, (SELECTION_DAY,),
        )

        def semantic_fold_arm_hash(
            policy: AssetPolicy,
            scored: dict[str, np.ndarray],
            selection: T.ThresholdSelection,
            diagnostic_seconds: float,
        ) -> str:
            # Timing is accepted as sidecar input but intentionally absent
            # from this receipt-equivalent semantic payload.
            del diagnostic_seconds
            models = {}
            for name in model_names:
                booster = getattr(policy, f"{name}_").get_booster()
                models[name] = {
                    "ubj_sha256": hashlib.sha256(bytes(
                        booster.save_raw(raw_format="ubj")
                    )).hexdigest(),
                    "config": booster.save_config(),
                }
            return C.object_sha256({
                "schema": "entry-v2-fold-arm-semantic-parity-v1",
                "model_input_binding": binding.as_dict(),
                "policy_config": asdict(config),
                "models": models,
                "bin_value": policy.bin_value_.tolist(),
                "calibrators": calibrator_state(policy),
                "score_arrays_sha256": T._array_hash(scored),
                "threshold_selection": asdict(selection),
            })

        expected_semantic_hash = semantic_fold_arm_hash(
            reference, reference_scored, reference_selection, 0.0
        )
        self.assertEqual(
            expected_semantic_hash,
            semantic_fold_arm_hash(
                reference, reference_scored, reference_selection, 999999.0
            ),
        )
        for policy in concurrent:
            scored = policy.score(score_x)
            selection = T._select_inner_threshold(
                "SI", selection_rows, scored,
                replay_data, (SELECTION_DAY,),
            )
            self.assertEqual(selection, reference_selection)
            self.assertEqual(
                semantic_fold_arm_hash(policy, scored, selection, 1.0),
                expected_semantic_hash,
            )

        self.assertEqual(T._array_hash(frozen_inputs), input_sha256)

    def test_neural_action_loss_and_hard_pair_exclude_masked_rows(self) -> None:
        rows = 3
        take = torch.zeros(rows, requires_grad=True)
        expected = torch.zeros(rows, requires_grad=True)
        core = SimpleNamespace(
            embedding=torch.zeros((rows, 2), requires_grad=True),
            value_bin_logits=torch.zeros((rows, 5), requires_grad=True),
            value_quantiles=torch.zeros((rows, 3), requires_grad=True),
            expected_value=expected,
            top3_logit=torch.zeros(rows, requires_grad=True),
            mae_quantiles=torch.zeros((rows, 3), requires_grad=True),
            wall_logit=torch.zeros(rows, requires_grad=True),
            take_logit=take,
        )
        output = SimpleNamespace(
            core=core,
            rank_value=torch.zeros(rows, requires_grad=True),
            mfe_quantiles=torch.zeros((rows, 3), requires_grad=True),
            time_to_peak_value=torch.zeros(rows, requires_grad=True),
            selected_ordinal_logits=torch.zeros((rows, 4), requires_grad=True),
        )
        target = SimpleNamespace(
            value_bin=torch.tensor([0, 1, 2]),
            value=torch.tensor([1.0, 2.0, 3.0]),
            top3=torch.tensor([1.0, 0.0, 0.0]),
            rank=torch.tensor([1.0, 2.0, 0.5]),
            mfe=torch.ones(rows), mae=torch.ones(rows),
            wall=torch.tensor([0.0, 1.0, 0.0]),
            time_to_peak=torch.ones(rows),
            take_target=torch.tensor([1.0, 0.0, 0.0]),
            action_loss_mask=torch.tensor([True, True, False]),
        )
        weights = T.SupervisionWeights((1., 1., 1., 1., 1.), 1., 1., 1.)
        components = T._oracle_components(
            output, target, weights, torch.ones(rows, dtype=torch.bool)
        )
        components["take_target"].backward(retain_graph=True)
        self.assertNotEqual(float(take.grad[0]), 0.0)
        self.assertNotEqual(float(take.grad[1]), 0.0)
        self.assertEqual(float(take.grad[2]), 0.0)
        components["expected_value"].backward()
        self.assertTrue(torch.all(expected.grad != 0.0))

        examples = _fixture()[0][0].examples[:rows]
        take.grad.zero_()
        contrast, pairs = T._matched_hard_listwise_components(
            output, target, examples
        )
        self.assertEqual(pairs, 1)
        contrast["hard_negative"].backward()
        self.assertEqual(float(take.grad[2]), 0.0)
        expected.grad.zero_()
        contrast["listwise"].backward()
        self.assertNotEqual(float(expected.grad[0]), 0.0)
        self.assertNotEqual(float(expected.grad[1]), 0.0)
        self.assertEqual(float(expected.grad[2]), 0.0)

        take.grad.zero_()
        selected_weights = {
            name: torch.ones(rows) for name in (
                "ordinal", "value_bins", "value_quantiles", "expected_value", "top3",
                "rank", "mfe_quantiles", "mae_quantiles", "wall",
                "time_to_peak", "take_target",
            )
        }
        selected_weights["take_target"] = torch.tensor([0.9, 0.1, 0.0])
        weighted = T._oracle_components(
            output, target, weights, torch.ones(rows, dtype=torch.bool),
            selected_weights,
        )
        weighted["take_target"].backward(retain_graph=True)
        self.assertAlmostEqual(
            abs(float(take.grad[0] / take.grad[1])), 9.0, places=5
        )
        take.grad.zero_()
        canonical, canonical_count = T._matched_hard_listwise_components(
            output, target, examples,
            ((examples[0].candidate_id, examples[1].candidate_id),), (1.0,),
        )
        self.assertEqual(canonical_count, 1)
        canonical["hard_negative"].backward()
        self.assertEqual(float(take.grad[2]), 0.0)

    def test_selected_ordinal_uses_four_cumulative_boundaries(self) -> None:
        rows = 5
        ordinal = torch.zeros((rows, 4), requires_grad=True)
        zero = lambda *shape: torch.zeros(shape or (rows,), requires_grad=True)
        core = SimpleNamespace(
            embedding=zero(rows, 2), value_bin_logits=zero(rows, 5),
            value_quantiles=zero(rows, 3), expected_value=zero(),
            top3_logit=zero(), mae_quantiles=zero(rows, 3),
            wall_logit=zero(), take_logit=zero(),
        )
        output = SimpleNamespace(
            core=core, rank_value=zero(), mfe_quantiles=zero(rows, 3),
            time_to_peak_value=zero(), selected_ordinal_logits=ordinal,
        )
        target = SimpleNamespace(
            value_bin=torch.arange(5), value=torch.zeros(rows),
            top3=torch.zeros(rows), rank=torch.zeros(rows), mfe=torch.zeros(rows),
            mae=torch.zeros(rows), wall=torch.zeros(rows),
            time_to_peak=torch.zeros(rows), take_target=torch.zeros(rows),
            action_loss_mask=torch.ones(rows, dtype=torch.bool),
        )
        selected_weights = {name: torch.ones(rows) for name in (
            "ordinal", "value_bins", "value_quantiles", "expected_value",
            "top3", "rank", "mfe_quantiles", "mae_quantiles", "wall",
            "time_to_peak", "take_target",
        )}
        components = T._oracle_components(
            output, target,
            T.SupervisionWeights((1., 1., 1., 1., 1.), 1., 1., 1.),
            torch.ones(rows, dtype=torch.bool), selected_weights,
        )
        components["ordinal"].backward()
        expected_positive = torch.tensor([
            [False, False, False, False],
            [True, False, False, False],
            [True, True, False, False],
            [True, True, True, False],
            [True, True, True, True],
        ])
        self.assertTrue(torch.equal(ordinal.grad < 0, expected_positive))

    def test_fold_denominator_respects_asset_source_coverage(self) -> None:
        day = 20210405
        expected = (
            SessionRef("HG", day, f"HG-{day}"),
            SessionRef("NKD", day, f"NKD-{day}"),
        )
        replay_data = ReplayCalibrationData({}, expected)
        self.assertEqual(replay_data.sessions_for((day,)), expected)
        with self.assertRaisesRegex(
                C.EntryV2Refusal, "no replay denominator sessions"):
            replay_data.sessions_for((day,), asset="SI")

    def test_train_only_normalization_and_alignment_refusals(self) -> None:
        batches, teacher, _replay_data = _fixture()
        normal = TrainFoldNormalizer.fit(batches, _fold().fit_days, _binding())

        changed = list(reversed(batches))
        inner_index = next(
            i for i, batch in enumerate(changed)
            if batch.trading_day == CALIBRATION_DAY
        )
        changed[inner_index] = replace(
            changed[inner_index],
            source=replace(
                changed[inner_index].source,
                event_continuous=(
                    changed[inner_index].source.event_continuous + 1.0e9
                ),
            ),
            candidate_features=changed[inner_index].candidate_features - 1.0e9,
            context_values=changed[inner_index].context_values * -1.0e9,
            self_supervised=replace(
                changed[inner_index].self_supervised,
                horizon_value=changed[inner_index].self_supervised.horizon_value
                + 1.0e9,
            ),
        )
        unchanged = TrainFoldNormalizer.fit(
            changed, _fold().fit_days, _binding()
        )
        self.assertEqual(normal, unchanged)

        bad_cutoff = batches[0].candidate_cutoffs.clone()
        bad_cutoff[2] += 1
        with self.assertRaises(C.EntryV2Refusal):
            replace(batches[0], candidate_cutoffs=bad_cutoff).validate(teacher)

        labels = [
            teacher[candidate_id]
            for batch in batches
            for candidate_id in batch.candidate_ids
            if candidate_id != batches[0].candidate_ids[0]
        ]
        missing = TeacherStore(labels, control_name="PROPHET")
        with self.assertRaises(ContractError):
            batches[0].validate(missing)

        with self.assertRaises(C.EntryV2Refusal):
            TrainFoldNormalizer.fit(batches, (20250701,), _binding())

        with self.assertRaisesRegex(C.EntryV2Refusal, "continuous-field order"):
            replace(
                _binding(),
                event_continuous_fields=tuple(reversed(CONTINUOUS_FIELDS)),
            ).validate()

    def test_candidate_oracle_floor_refuses_before_model_fit(self) -> None:
        batches, teacher, replay_data = _fixture()
        paths: list[TeacherPath] = []
        outcomes: dict[str, ReplayOutcome] = {}
        for batch in batches:
            for item in batch.examples:
                label = teacher[item.candidate_id]
                value = (
                    999.0
                    if item.trading_day == TEST_DAY and label.cert_close_usd > 0.0
                    else label.cert_close_usd
                )
                source = replay_data.outcomes[item.candidate_id]
                exit_ts, _pnl, _reason = source.resolve(item.decision_ts_ns)
                paths.append(TeacherPath(
                    item.candidate_id,
                    item.asset,
                    item.trading_day,
                    item.decision_ts_ns,
                    exit_ts,
                    value,
                    max(value, 0.0) + 50.0,
                    label.mae_usd,
                    label.wall_hit,
                    label.time_to_peak_sec,
                ))
                outcomes[item.candidate_id] = replace(
                    source,
                    close_pnl_usd=value,
                    phase_close_pnl_usd=value,
                )
        low_teacher = build_teacher_store(
            paths, expected_sessions=replay_data.expected_sessions
        )
        low_replay = ReplayCalibrationData(
            outcomes, replay_data.expected_sessions,
            replay_data.regime_declarations,
        )
        system = _system()
        before = {
            name: value.detach().clone()
            for name, value in system.state_dict().items()
        }
        with self.assertRaisesRegex(
            C.EntryV2Refusal, "meet \\$1,000/asset-day independently"
        ):
            run_fold_oof(
                system,
                batches,
                low_teacher,
                _fold(),
                low_replay,
                _binding(),
                TrainingConfig(device="cpu", bf16=False),
                _FakeAssetPolicy,
            )
        self.assertTrue(all(
            torch.equal(before[name], value)
            for name, value in system.state_dict().items()
        ))

    def test_fixed_stages_three_arms_prequential_oof_and_null_control(self) -> None:
        batches, teacher, replay_data = _fixture()
        device = "cuda" if torch.cuda.is_available() else "cpu"
        config = TrainingConfig(
            device=device,
            bf16=device == "cuda",
        )
        torch.manual_seed(config.seed)
        _FakeAssetPolicy.instances.clear()
        _FakeAssetPolicy.created_count = 0
        _FakeAssetPolicy.active_fits = 0
        _FakeAssetPolicy.max_active_fits = 0
        _FakeAssetPolicy.fit_threads.clear()
        result = run_fold_oof(
            _system(),
            batches,
            teacher,
            _fold(),
            replay_data,
            _binding(),
            config,
            _FakeAssetPolicy,
        )

        self.assertEqual(
            tuple(stage.name for stage in result.training.trace.passes),
            (
                "fold_causal_self_supervision",
                "full_population_oracle_multitask",
                "matched_hard_negative_listwise",
            ),
        )
        self.assertTrue(all(stage.rows == 15
                            for stage in result.training.trace.passes))
        self.assertGreater(result.training.trace.passes[-1].matched_pairs, 0)
        self.assertEqual(
            len({stage.model_sha256 for stage in result.training.trace.passes}), 3
        )
        self.assertNotEqual(
            result.training.trace.initial_model_sha256,
            result.training.trace.final_model_sha256,
        )
        self.assertEqual(set(result.days.tolist()), {TEST_DAY})
        self.assertTrue(
            all(candidate_id not in result.candidate_ids for candidate_id in (
                batches[0].candidate_ids[0], batches[3].candidate_ids[0]
            ))
        )
        self.assertEqual(tuple(result.arm_score_arrays), ARM_NAMES)
        for arm in ARM_NAMES:
            self.assertEqual(
                dict(result.arm_thresholds[arm]),
                {asset: 0.03 for asset in ASSETS},
            )
            self.assertEqual(
                tuple(score.candidate_id
                      for score in result.arm_entry_scores[arm]),
                result.candidate_ids,
            )
            self.assertEqual(
                sum(score.enter for score in result.arm_entry_scores[arm]), 3
            )
            for asset in ASSETS:
                selected = result.receipt["arm_thresholds"][arm][asset]
                self.assertGreater(selected["feasible_thresholds"], 0)
                self.assertEqual(len(selected["funnel"]), 3)
                self.assertEqual(
                    [row["threshold"] for row in selected["funnel"][:2]],
                    [0.01, 0.03],
                )
                self.assertGreater(
                    selected["funnel"][-1]["threshold"], 0.03
                )
                self.assertEqual(
                    selected["funnel"][-1]["diagnostic_value_pass"], 1
                )
        self.assertTrue(
            result.receipt["entry_gate_contract"]["action_threshold_required"]
        )
        self.assertEqual(
            result.receipt["entry_gate_contract"]["schema"],
            "entry-v2-decision-gate-v3",
        )
        self.assertEqual(
            result.receipt["entry_gate_contract"]["threshold_source"],
            "ACTION_PROBABILITY_INNER_REPLAY",
        )
        self.assertIsNone(result.first_failed_boundary)
        self.assertEqual(
            result.receipt["decision_contract"]["proxy_metrics"], "diagnostic_only"
        )
        self.assertEqual(result.receipt["schema"], "entry-v2-fold-oof-v5")
        self.assertEqual(tuple(result.receipt["arms"]), ARM_NAMES)
        self.assertEqual(
            result.receipt["prequential"]["calibration_days"],
            [CALIBRATION_DAY],
        )
        self.assertEqual(
            result.receipt["prequential"]["threshold_selection_days"],
            [SELECTION_DAY],
        )
        self.assertEqual(
            result.receipt["model_input_binding"], _binding().as_dict()
        )
        self.assertEqual(len(result.expected_sessions), 4)
        self.assertEqual(len(result.regime_declarations), 3)

        exact = replay(result.scored_arrivals, expected_sessions=result.expected_sessions)
        truth = replay(
            result.truth_arrivals, expected_sessions=result.expected_sessions
        )
        self.assertEqual(exact.trades, 3)
        self.assertGreater(exact.total_pnl_usd, 0.0)
        self.assertEqual(truth.trades, 3)
        final_policies = [
            policy for policy in _FakeAssetPolicy.instances
            if hasattr(policy, "calibration_rows")
        ]
        gc.collect()
        self.assertEqual(len(final_policies), 7)
        self.assertEqual(len(_FakeAssetPolicy.instances), 7)
        self.assertEqual(_FakeAssetPolicy.created_count, 21)
        self.assertGreater(_FakeAssetPolicy.max_active_fits, 1)
        self.assertLessEqual(_FakeAssetPolicy.max_active_fits, 4)
        self.assertGreater(len(_FakeAssetPolicy.fit_threads), 1)
        self.assertLessEqual(len(_FakeAssetPolicy.fit_threads), 4)
        self.assertTrue(all(
            name.startswith("entry-v2-policy")
            for name in _FakeAssetPolicy.fit_threads
        ))
        self.assertNotIn("diagnostic_timings", result.receipt)
        self.assertGreater(result.diagnostic_timings["total_seconds"], 0.0)
        changed_timing = replace(
            result,
            diagnostic_timings={"total_seconds": 9_999_999.0},
        )
        self.assertEqual(changed_timing.receipt, result.receipt)
        self.assertEqual(
            changed_timing.receipt["sha256"], result.receipt["sha256"]
        )
        pooled = next(policy for policy in final_policies
                      if policy.asset == "POOLED")
        self.assertEqual(pooled.fit_rows, 120)
        self.assertEqual(pooled.calibration_rows, 90)
        for policy in final_policies:
            if policy.asset != "POOLED":
                self.assertEqual(policy.fit_rows, 40)
                self.assertEqual(policy.calibration_rows, 30)

        # Every declared head participated in the one population backward pass.
        trained = result.training.system
        for head in (
            trained.encoder.value_bin_head,
            trained.encoder.value_quantile_head,
            trained.encoder.expected_value_head,
            trained.encoder.top3_head,
            trained.encoder.mae_quantile_head,
            trained.encoder.wall_head,
            trained.encoder.take_head,
            trained.rank_head,
            trained.mfe_quantile_head,
            trained.time_to_peak_head,
        ):
            self.assertIsNotNone(head.weight.grad)
            self.assertTrue(torch.isfinite(head.weight.grad).all())

        # The null uses the identical fold/replay procedure, remains tagged,
        # and still carries the exact (unshuffled) truth-score candidate set.
        torch.manual_seed(config.seed)
        control = run_shuffled_control_oof(
            _system(),
            batches,
            teacher,
            _fold(),
            replay_data,
            17,
            _binding(),
            config,
            _FakeAssetPolicy,
        )
        self.assertTrue(control.control_name.startswith("SHUFFLED_"))
        self.assertEqual(
            control.receipt["null_control"]["schema"],
            "entry-v2-stage-asset-day-shuffle-v2",
        )
        self.assertEqual(
            control.receipt["null_control"]["selected_labels"], 135
        )
        self.assertEqual(
            control.receipt["null_control"]["within_asset_day_rows"], 135
        )
        self.assertEqual(
            control.receipt["null_control"]["stage_asset_fallback_rows"], 0
        )
        self.assertEqual(
            tuple(score.candidate_id for score in control.truth_scores),
            tuple(score.candidate_id for score in result.truth_scores),
        )


if __name__ == "__main__":
    unittest.main()
