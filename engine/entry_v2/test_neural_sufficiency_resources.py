from __future__ import annotations

from pathlib import Path
import resource
from types import MappingProxyType, SimpleNamespace
import shutil
import tempfile
import unittest
from unittest import mock

import numpy as np
import torch

from . import common as C
from .event_pack import CATEGORY_SIZES, CATEGORICAL_FIELDS, CONTINUOUS_FIELDS
from .causal_label_atlas import (
    CellAvailability, PADDED_OUTPUT_WIDTH, PNL_UNITS_PER_USD, PROBE_REGISTRY, ProbeTarget,
    probe_target_schema_sha256,
)
from .atlas_probe_model import ProbeRows
from .durable_store import DurableEntryV2Store
from .diagnostic_inputs import DerivedEventFields, RAW_ROUTE_FIELDS
from .neural_sufficiency_resources import (
    ExpandedEventTransform, MAXIMUM_REGISTERED_FITS_THROUGH_E2,
    ProductionExactDiagnosticResources, RAW_MEMORY_OCCLUSION_MIN_AUROC_DROP,
    REHEARSAL_PATH_IMPLEMENTATION_REFUSALS, REHEARSAL_PATH_STATUSES,
    ROUTE_GATE_MINIMUM_CUTOFF,
    RealDiagnosticExecutorRefusal, _competing_candidate_ipcw,
    _competing_ipcw_observations, _admit_production_resources,
    _e1_fit_support_inputs, _executed_threshold_candidate_law,
    _expanded_columns, _selected_horizon_targets_from_spec,
    optimizer_fit_census, reference_phase_clocks, reset_optimizer_fit_census,
)
from .neural_sufficiency_model import EncoderComplexityReceipt, EventFieldSchema
from .policy import ModelInputBinding
from .selected_horizon_contract import (
    SCHEMA_SHA256 as SELECTED_HORIZON_SCHEMA_SHA256,
)
from .session_stream import MODEL_ARRAYS_CONVERSION_LAW_SHA256


class ExpandedEventTransformTest(unittest.TestCase):
    # ------------------------------------------------------------------
    # A5: the previous fixture built bindings out of bare SimpleNamespace
    # objects with only asset/trading_day, so the domain law never reached its
    # compliance/teacher/roster branches at all -- the test passed without
    # exercising anything it claimed to.
    # ------------------------------------------------------------------
    START_D8 = 20210531

    @staticmethod
    def _binding(candidate_id, asset, day, *, compliance="CLEAR",
                 teacher="READY"):
        return SimpleNamespace(
            candidate_id=candidate_id, asset=asset, trading_day=day,
            compliance_status=compliance, teacher_status=teacher,
            phase_open_ts_ns=1, phase_close_ts_ns=2,
            sane_ceiling_units=3, multiplier=4)

    @staticmethod
    def _session(asset, day, session_id, candidate_ids):
        return SimpleNamespace(asset=asset, trading_day=day,
                               session_id=session_id,
                               candidate_ids=tuple(candidate_ids))

    def _resources(self, corpus_sessions, bindings, *, start_d8=None):
        resources = ProductionExactDiagnosticResources.__new__(
            ProductionExactDiagnosticResources)
        keys = []
        for row in bindings:
            key = (row.asset, row.trading_day)
            if key not in keys:
                keys.append(key)
        resources.stage = SimpleNamespace(
            corpus_stage=SimpleNamespace(corpus=SimpleNamespace(
                sessions=tuple(corpus_sessions))),
            diagnostic_corpus=SimpleNamespace(
                sessions=tuple(SimpleNamespace(key=key) for key in keys),
                bindings=tuple(bindings),
                receipt={"selected_horizon_start_d8":
                         self.START_D8 if start_d8 is None else start_d8},
            ),
        )
        return resources

    def _baseline(self):
        context = self._session("HG", 20210528, "context", ("HG:c-1",))
        learner = self._session("HG", 20210601, "learner", ("HG:a", "HG:b"))
        bindings = [
            self._binding("HG:a", "HG", 20210601),
            self._binding("HG:b", "HG", 20210601),
            self._binding("SI:z", "SI", 20210712, teacher="NO_SANE_SUFFIX"),
        ]
        return context, learner, bindings

    def test_expanded_metadata_excludes_valid_pre_diagnostic_context_sessions(self):
        context, learner, bindings = self._baseline()
        metadata = self._resources((context, learner), bindings
                                   )._expanded_session_metadata()
        self.assertEqual(tuple(metadata), (("HG", 20210601, "learner"),))
        self.assertEqual(metadata[("HG", 20210601, "learner")],
                         (bindings[0], bindings[1]))

    def test_m1_diagnostic_only_day_gaining_an_eligible_row_refuses(self):
        context, learner, bindings = self._baseline()
        mutated = [*bindings[:2], self._binding("SI:z", "SI", 20210712)]
        with self.assertRaisesRegex(
                RealDiagnosticExecutorRefusal,
                "eligible binding lacks corpus session"):
            self._resources((context, learner), mutated
                            )._expanded_session_metadata()

    def test_m2_corpus_session_for_a_zero_eligible_diagnostic_day_refuses(self):
        context, learner, bindings = self._baseline()
        extra = self._session("SI", 20210712, "S1", ("SI:z",))
        with self.assertRaisesRegex(
                RealDiagnosticExecutorRefusal,
                "corpus session has no eligible binding"):
            self._resources((context, learner, extra), bindings
                            )._expanded_session_metadata()

    def test_m3_permuted_learner_roster_order_refuses(self):
        context, _learner, bindings = self._baseline()
        permuted = self._session("HG", 20210601, "learner", ("HG:b", "HG:a"))
        with self.assertRaisesRegex(
                RealDiagnosticExecutorRefusal,
                "learner candidate roster differs"):
            self._resources((context, permuted), bindings
                            )._expanded_session_metadata()

    def test_m4_learner_roster_dropping_an_eligible_candidate_refuses(self):
        context, _learner, bindings = self._baseline()
        short = self._session("HG", 20210601, "learner", ("HG:a",))
        with self.assertRaisesRegex(
                RealDiagnosticExecutorRefusal,
                "learner candidate roster differs"):
            self._resources((context, short), bindings
                            )._expanded_session_metadata()

    def test_m6_post_wall_corpus_session_absent_from_diagnostic_map_refuses(self):
        # A4 reverse direction: a corpus session at/after the receipt-derived
        # selected-horizon start wall with NO diagnostic day at all.
        context, learner, bindings = self._baseline()
        orphan = self._session("NKD", 20210602, "N1", ("NKD:q",))
        with self.assertRaisesRegex(
                RealDiagnosticExecutorRefusal,
                "absent from the diagnostic day map"):
            self._resources((context, learner, orphan), bindings
                            )._expanded_session_metadata()

    def test_a8_start_wall_comes_from_the_corpus_receipt_not_a_literal(self):
        # With the wall moved later, the 20210601 corpus session is BEFORE the
        # wall and is treated as pre-diagnostic context, not an orphan.
        context, learner, bindings = self._baseline()
        orphan = self._session("NKD", 20210602, "N1", ("NKD:q",))
        metadata = self._resources(
            (context, learner, orphan), bindings, start_d8=20210901
        )._expanded_session_metadata()
        self.assertEqual(tuple(metadata), (("HG", 20210601, "learner"),))
        resources = self._resources((context, learner), bindings,
                                    start_d8="not-a-day")
        with self.assertRaisesRegex(RealDiagnosticExecutorRefusal,
                                    "selected_horizon_start_d8"):
            resources._expanded_session_metadata()

    def test_m8_ineligible_same_day_row_stays_in_the_transform_bindings(self):
        context, learner, bindings = self._baseline()
        rows = [*bindings[:2],
                self._binding("HG:c", "HG", 20210601, compliance="PROHIBITED"),
                bindings[2]]
        metadata = self._resources((context, learner), rows
                                   )._expanded_session_metadata()
        self.assertEqual(
            [row.candidate_id
             for row in metadata[("HG", 20210601, "learner")]],
            ["HG:a", "HG:b", "HG:c"])

    def test_competence_metrics_ignore_action_masked_near_positives(self):
        assets = np.repeat(np.asarray(("HG", "NKD", "SI"), str), 3)
        rows = SimpleNamespace(
            asset=assets,
            action_target=np.tile(np.asarray((0, 1, 1), np.int8), 3),
            action_loss_mask=np.tile(np.asarray((True, True, False)), 3),
        )
        baseline = np.tile(np.asarray((0.1, 0.9, 0.0), np.float64), 3)
        mutated = baseline.copy()
        mutated[~rows.action_loss_mask] = 1.0
        self.assertEqual(
            ProductionExactDiagnosticResources._metrics(rows, baseline),
            ProductionExactDiagnosticResources._metrics(rows, mutated),
        )

    def test_selected_horizon_atlas_must_match_corpus_carrier(self):
        candidate_id = "HG:20210601:c0"
        units = np.zeros((1, 12), np.int64)
        units[0, (3, 4, 5, 6, 7, 11)] = np.arange(1, 7) * PNL_UNITS_PER_USD
        valid = np.ones((1, 12), bool)
        values = units[:, (3, 4, 5, 6, 7, 11)].astype(np.float64) / float(
            PNL_UNITS_PER_USD)
        atlas = SimpleNamespace(
            candidate_ids=(candidate_id,),
            atoms={"vertical_units": units, "vertical_mask": valid},
        )
        labels = (SimpleNamespace(candidate_id=candidate_id,
                                  cert_close_usd=6.0),)
        spec = SimpleNamespace(
            candidate_ids=(candidate_id,),
            selected_horizon_value=torch.from_numpy(values.copy()),
            selected_horizon_valid=torch.ones((1, 6), dtype=torch.bool),
            selected_horizon_schema_sha256=SELECTED_HORIZON_SCHEMA_SHA256,
        )
        target, mask, _ = _selected_horizon_targets_from_spec(
            atlas, spec, (0,), labels)
        self.assertTrue(torch.equal(target, spec.selected_horizon_value))
        self.assertTrue(torch.equal(mask, spec.selected_horizon_valid))
        changed = spec.selected_horizon_value.clone(); changed[0, 2] += 1.0
        with self.assertRaisesRegex(
                RealDiagnosticExecutorRefusal, "atlas/corpus carrier differs"):
            _selected_horizon_targets_from_spec(
                atlas, SimpleNamespace(**{**vars(spec),
                    "selected_horizon_value": changed}), (0,), labels)

    def test_incremental_rebind_changes_lineage_not_input_contract(self):
        def binding(seed: str, *, clock: str = "f" * 64) -> ModelInputBinding:
            return ModelInputBinding(
                tuple(CONTINUOUS_FIELDS), tuple(CATEGORICAL_FIELDS),
                tuple(CATEGORY_SIZES), MODEL_ARRAYS_CONVERSION_LAW_SHA256,
                seed * 64, chr(ord(seed) + 1) * 64,
                chr(ord(seed) + 2) * 64, clock,
            )
        first, extended = binding("1"), binding("4")
        prior = SimpleNamespace(identity="prior")
        later = SimpleNamespace(identity="later")
        transform = ExpandedEventTransform()
        transform.freeze(
            schema_sha256="e" * 64, model_input_binding=first,
            bindings={("HG", 20210104, "s1"): (prior,)},
        )
        contract = transform.input_contract_sha256
        transform.rebind(
            model_input_binding=extended,
            bindings={
                ("HG", 20210104, "s1"): (prior,),
                ("HG", 20211001, "s2"): (later,),
            },
        )
        self.assertEqual(transform.input_contract_sha256, contract)
        self.assertEqual(transform.base_binding_sha256,
                         extended.binding_sha256)
        with self.assertRaisesRegex(
                RealDiagnosticExecutorRefusal, "input contract changed"):
            transform.rebind(
                model_input_binding=binding("7", clock="a" * 64),
                bindings=dict(transform._bindings),
            )

    def test_acceptance_numerical_export_is_namespaced_and_complete(self):
        resources = ProductionExactDiagnosticResources.__new__(
            ProductionExactDiagnosticResources)
        resources.schema = SimpleNamespace(sha256="e" * 64)
        resources._arms = {
            arm: torch.nn.Linear(2, 1) for arm in ("C0", "C1", "L0", "L1", "M1")}
        resources.arm_rows = {arm: SimpleNamespace(
            manifest_sha256=(str(index) * 64)[:64],
            representation_sha256=(str(index + 5) * 64)[:64])
            for index, arm in enumerate(("C0", "C1", "L0", "L1", "M1"), 1)}
        resources._acceptance_component_evidence = {
            "acceptance/evidence/raw-fidelity.json":
                b'{"schema":"entry-v2-raw-fidelity-evidence-v1"}',
            **{f"acceptance/evidence/arm-{arm}.json": (
                '{"arm":"' + arm
                + '","schema":"entry-v2-arm-competence-evidence-v1"}'
            ).encode() for arm in ("C0", "C1", "L0", "L1", "M1")},
        }
        payloads = resources.export_acceptance_numerical_artifacts()
        expected = {f"acceptance/{arm}.competence.safetensors"
                    for arm in ("C0", "C1", "L0", "L1", "M1")} | {
                    "acceptance/arm-authorization.json", "acceptance/manifest.json",
                    "acceptance/evidence/raw-fidelity.json",
                    *(f"acceptance/evidence/arm-{arm}.json"
                      for arm in ("C0", "C1", "L0", "L1", "M1"))}
        self.assertEqual(set(payloads), expected)
        self.assertTrue(all(name.startswith("acceptance/") for name in payloads))

    def test_e1_supports_are_physical_fit_slices_including_24x_causes(self):
        n = 5
        probe = next(row for row in PROBE_REGISTRY if row.cell == 10)
        values = np.zeros((n, PADDED_OUTPUT_WIDTH), np.float64)
        values[:, :24] = np.arange(24) % 4
        coordinate = np.zeros_like(values, bool); coordinate[:, :72] = True
        valid = np.ones(n, bool)
        layout = tuple(
            f"cause_{i}" if i < 24 else f"clock_{i}" for i in range(72))
        prediction_layout = tuple(f"prediction_{i}" for i in range(180))
        target = ProbeTarget(
            probe.probe_id, CellAvailability.MATERIALIZED, values,
            coordinate, coordinate, np.zeros_like(coordinate), valid, valid,
            np.zeros(n, bool), np.ones(n, np.float32), np.arange(n),
            np.ones(n, np.int64), 72, layout, 1,
            probe_target_schema_sha256(
                probe.probe_id, 72, layout, 1, None, 180, prediction_layout),
            None, 180, prediction_layout)
        rows = ProbeRows(
            np.zeros((n, 1865), np.float32), np.zeros((n, 1024), np.float32),
            np.asarray(["HG", "HG", "NKD", "NKD", "SI"]),
            np.asarray([20210601, 20211101, 20210701, 20211201, 20210901]),
            np.arange(n, dtype=np.int64), np.asarray([f"c{i}" for i in range(n)]))
        primary, additional = _e1_fit_support_inputs(
            probe, target, rows, np.asarray([0, 2, 4]),
            selected_horizon_start_d8=20210531)
        self.assertEqual(np.asarray(primary.asset).shape, (3 * 24,))
        self.assertEqual(np.asarray(primary.valid).shape, (3 * 24,))
        self.assertEqual(np.asarray(primary.values).shape, (3 * 24,))
        self.assertEqual(np.asarray(primary.day).shape, (3 * 24,))
        self.assertEqual(len(additional), 72)
        self.assertTrue(all(np.asarray(row.asset).shape == (3,)
                            for row in additional))
        self.assertTrue(all(np.max(np.asarray(row.day)) <= 20210930
                            for row in (primary, *additional)))
        # Item 24: the CONTINUOUS family carries its censor plane explicitly.
        self.assertIsNotNone(primary.censored)
        self.assertEqual(np.asarray(primary.censored).shape, (3 * 24,))
        self.assertTrue(all(row.censored is not None for row in additional))
        self.assertTrue(all(row.selected_horizon_start_d8 == 20210531
                            for row in (primary, *additional)))
        with self.assertRaisesRegex(
                RealDiagnosticExecutorRefusal, "physical slice crossed FIT"):
            _e1_fit_support_inputs(probe, target, rows, np.asarray([0, 1, 2]),
                                   selected_horizon_start_d8=20210531)
        # Item 28/A8: the lower wall is enforced from the receipt-derived day.
        with self.assertRaisesRegex(
                RealDiagnosticExecutorRefusal,
                "precedes the selected-horizon start wall"):
            _e1_fit_support_inputs(probe, target, rows, np.asarray([0, 2, 4]),
                                   selected_horizon_start_d8=20210801)

    def test_frozen_raw_memory_is_encoded_once_per_base_session(self):
        class Encoder(torch.nn.Module):
            def __init__(self):
                super().__init__(); self.calls = 0
                self.weight = torch.nn.Parameter(torch.ones(()))

            def forward(self, continuous, categorical, cutoffs, **_):
                self.calls += 1
                self.last_complexity_receipt = EncoderComplexityReceipt(
                    events_visible=len(continuous), regular_blocks=1,
                    candidates=len(cutoffs), recent_window_events=0,
                    partial_block_events=0, band_60_blocks=0,
                    band_300_blocks=0, band_900_blocks=0,
                    regular_block_encodes=1)
                return self.weight * torch.ones(
                    (len(cutoffs), 4, 512), device=continuous.device)

        with tempfile.TemporaryDirectory(dir=C.CACHE_ROOT) as temporary:
            resources = ProductionExactDiagnosticResources.__new__(
                ProductionExactDiagnosticResources)
            resources.device = torch.device("cpu")
            resources._held_pointwise_hashes = {"C0": "c" * 64}
            resources._held_memory_dir = Path(temporary) / "memory-cache"
            resources._held_memory_entries = {}
            resources._held_memory_hits = 0
            resources._held_memory_misses = 0
            resources._held_memory_bytes = 0
            batch = SimpleNamespace(
                asset="HG", day=20210104, session_id="HG-20210104",
                candidate_ids=("a", "b"), continuous=torch.zeros((3, 2)),
                categorical=torch.zeros((3, 1), dtype=torch.uint8),
                cutoffs=torch.tensor([2, 3]), clock=torch.arange(3),
                decisions=torch.tensor([3, 4]))
            model = SimpleNamespace(encoder=Encoder())
            first, first_complexity = resources._held_raw_memory(
                "C0", model, batch)
            second, second_complexity = resources._held_raw_memory(
                "C0", model, batch)
            self.assertEqual(model.encoder.calls, 1)
            np.testing.assert_array_equal(first.numpy(), second.numpy())
            self.assertEqual(first_complexity, second_complexity)
            self.assertEqual(resources._held_memory_misses, 1)
            self.assertEqual(resources._held_memory_hits, 1)
            shutil.rmtree(resources._held_memory_dir)

    def test_held_normalized_plane_is_built_once_and_file_mapped(self):
        with tempfile.TemporaryDirectory(dir=C.CACHE_ROOT) as temporary:
            resources = ProductionExactDiagnosticResources.__new__(
                ProductionExactDiagnosticResources)
            resources.schema = EventFieldSchema(
                ("a", "b"), ("kind",), (4,), "a" * 64, True)
            resources._held_continuous_dir = Path(temporary) / "held-cache"
            resources._held_continuous_entries = {}
            resources._held_continuous_hits = 0
            resources._held_continuous_misses = 0
            resources._held_continuous_bytes = 0
            spec = SimpleNamespace(asset="HG", trading_day=20210104,
                                   session_id="HG-20210104")
            observed = SimpleNamespace(derived=object(),
                                       validate_backing=lambda: None)
            normalizer = {"location": np.asarray([1.0, 2.0]),
                          "scale": np.asarray([2.0, 4.0]),
                          "constant": np.asarray([False, False]),
                          "receipt_sha256": "b" * 64}
            expanded = np.asarray([[1.0, 2.0], [3.0, 6.0], [5.0, 10.0]])
            with mock.patch(
                    "engine.entry_v2.neural_sufficiency_resources._expanded_columns",
                    return_value=(("a", "b"), expanded)) as convert:
                first = resources._held_continuous(spec, observed, 3, normalizer)
                second = resources._held_continuous(spec, observed, 3, normalizer)
            self.assertEqual(convert.call_count, 1)
            np.testing.assert_array_equal(first.numpy(), second.numpy())
            np.testing.assert_array_equal(
                first.numpy(), np.asarray([[0.0, 0.0], [1.0, 1.0], [2.0, 2.0]],
                                          np.float32))
            self.assertEqual(resources._held_continuous_misses, 1)
            self.assertEqual(resources._held_continuous_hits, 1)
            entry = next(iter(resources._held_continuous_entries.values()))
            self.assertFalse(entry.path.stat().st_mode & 0o222)
            shutil.rmtree(resources._held_continuous_dir)

    def test_production_resource_refuses_cgroup_shortfall_and_uses_durable_cache(self):
        with tempfile.TemporaryDirectory(dir=C.CACHE_ROOT) as temporary, \
                mock.patch(
                    "engine.entry_v2.production_runtime.torch.cuda.is_initialized",
                    return_value=False):
            root = Path(temporary) / "diagnostic-run"
            with mock.patch(
                    "engine.entry_v2.neural_sufficiency_resources."
                    "effective_memory_available_bytes",
                    return_value=127 * 1024 ** 3), mock.patch(
                    "engine.entry_v2.neural_sufficiency_resources."
                    "_configure_deterministic_torch",
                    return_value="a" * 64), mock.patch(
                    "engine.entry_v2.neural_sufficiency_resources."
                    "_admit_production_resources",
                    return_value={"receipt_sha256": "b" * 64}):
                with self.assertRaisesRegex(
                        RealDiagnosticExecutorRefusal, "resident reserve"):
                    ProductionExactDiagnosticResources(root, device="cpu")
            with mock.patch(
                    "engine.entry_v2.neural_sufficiency_resources."
                    "effective_memory_available_bytes",
                    return_value=256 * 1024 ** 3), mock.patch(
                    "engine.entry_v2.neural_sufficiency_resources."
                    "_configure_deterministic_torch",
                    return_value="a" * 64), mock.patch(
                    "engine.entry_v2.neural_sufficiency_resources."
                    "_admit_production_resources",
                    return_value={"receipt_sha256": "b" * 64}):
                resources = ProductionExactDiagnosticResources(root, device="cpu")
            durable_root = resources.durable_store.root
            self.assertTrue(resources.cache.disk_backed)
            self.assertTrue(resources.cache.durable)
            self.assertIsNone(resources.cache.backing_dir)
            self.assertIsInstance(resources.durable_store, DurableEntryV2Store)
            self.assertTrue(durable_root.is_dir())
            resources.close()
            self.assertTrue(durable_root.exists())

    def test_production_resource_admission_raises_nofile_before_cache(self):
        with tempfile.TemporaryDirectory(dir=C.CACHE_ROOT) as temporary, \
                mock.patch(
                    "engine.entry_v2.neural_sufficiency_resources."
                    "resource.getrlimit",
                    side_effect=[(1024, 524288), (16384, 524288)]), \
                mock.patch(
                    "engine.entry_v2.neural_sufficiency_resources."
                    "resource.setrlimit") as set_limit, \
                mock.patch(
                    "engine.entry_v2.neural_sufficiency_resources."
                    "Path.read_text", return_value="1048576"), \
                mock.patch(
                    "engine.entry_v2.neural_sufficiency_resources."
                    "shutil.disk_usage",
                    return_value=SimpleNamespace(free=2 * 1024 ** 4)), \
                mock.patch(
                    "engine.entry_v2.neural_sufficiency_resources."
                    "os.statvfs",
                    return_value=SimpleNamespace(f_favail=1_000_000)):
            receipt = _admit_production_resources(Path(temporary))
        set_limit.assert_called_once_with(
            resource.RLIMIT_NOFILE, (16384, 524288))
        self.assertEqual(receipt["nofile_soft_before"], 1024)
        self.assertEqual(receipt["nofile_soft_after"], 16384)
        self.assertGreaterEqual(receipt["session_mapping_upper_bound"], 3192)
        self.assertEqual(len(receipt["receipt_sha256"]), 64)

        with tempfile.TemporaryDirectory(dir=C.CACHE_ROOT) as temporary, \
                mock.patch(
                    "engine.entry_v2.neural_sufficiency_resources."
                    "resource.getrlimit", return_value=(1024, 8192)):
            with self.assertRaisesRegex(
                    RealDiagnosticExecutorRefusal, "hard file-descriptor"):
                _admit_production_resources(Path(temporary))

    def test_competing_ipcw_uses_frozen_pair_passage_layout(self):
        n = 2
        values = np.zeros((n, PADDED_OUTPUT_WIDTH), np.float64)
        mask = np.zeros_like(values, bool); censor = np.zeros_like(values, bool)
        values[:, 24:48] = np.log1p([[2.0] * 24, [9.0] * 24])
        values[:, 48:60] = np.log1p([[10_000.0] * 12, [20_000.0] * 12])
        mask[:, :72] = True; censor[1, 24:48] = True
        output_layout = tuple(f"axis_{i}" for i in range(72))
        prediction_layout = tuple(f"prediction_{i}" for i in range(120))
        schema = probe_target_schema_sha256(
            "C10P01", 72, output_layout, 1, None, 120, prediction_layout)
        target = ProbeTarget(
            "C10P01", CellAvailability.MATERIALIZED, values, mask, mask,
            censor, np.ones(n, bool), np.ones(n, bool), np.asarray([False, True]),
            np.ones(n, np.float32), np.arange(n), np.ones(n, np.int64), 72,
            output_layout, 1, schema, None, 120, prediction_layout)
        passage, censored = _competing_ipcw_observations(target)
        self.assertEqual(passage.shape, (48,))
        self.assertEqual(int(censored.sum()), 24)
        np.testing.assert_allclose(np.unique(passage), [2.0, 9.0])
        weight = _competing_candidate_ipcw(
            target, np.asarray([2.0, 9.0]), np.asarray([1.0, .5]))
        np.testing.assert_allclose(weight, [1.0, 2.0])

    def test_expanded_route_order_and_block_clock_ignore_storage_and_roster_order(
            self):
        n = 513
        clock = (1_650_000_000_000_000_000
                 + np.arange(n, dtype=np.int64) * 1_000_003)
        raw = {}
        categorical = {"action", "side", "flags", "depth", "missing_mask"}
        for offset, name in enumerate(RAW_ROUTE_FIELDS):
            if name == "ts_recv_ns":
                value = clock.copy()
            elif name == "ts_event_ns":
                value = clock - 17
            elif name in categorical:
                value = np.full(n, offset, np.uint8)
            else:
                value = np.arange(n, dtype=np.int64) + offset
            raw[name] = value
        block = np.full(n, -1, np.int64)
        fields = DerivedEventFields(
            MappingProxyType(raw),
            MappingProxyType({"block_end_receive_ns": block}),
            MappingProxyType({"block_end_receive_ns": np.ones(n, bool)}),
            MappingProxyType({}), "a" * 64, "b" * 64,
        )
        reversed_fields = DerivedEventFields(
            MappingProxyType(dict(reversed(tuple(raw.items())))),
            fields.derived_routes, fields.valid_masks, fields.constant_mask,
            fields.schema_sha256, fields.equation_sha256,
        )
        names, values = _expanded_columns(fields, n)
        reopened_names, reopened_values = _expanded_columns(reversed_fields, n)
        self.assertEqual(names, reopened_names)
        np.testing.assert_array_equal(values, reopened_values)
        valid_name = "derived.block_end_receive_ns.quotient_1e9.valid"
        self.assertEqual(np.flatnonzero(values[:, names.index(valid_name)]).tolist(),
                         [255, 511])
        self.assertEqual(values[512, names.index(valid_name)], 0.0)

    def test_cached_transform_sanity_comparison_cannot_overflow(self):
        n = 2
        continuous = np.zeros((n, len(CONTINUOUS_FIELDS)), np.float64)
        categorical = np.zeros((n, len(CATEGORICAL_FIELDS)), np.uint8)
        clock = np.asarray((1_650_000_000_000_000_000,
                            1_650_000_001_000_000_000), np.uint64)
        continuous[:, 8] = (100_000_000, 1_000_000_000_000_000)
        continuous[:, 9] = (100_500_000, 6_000_000_000_000_000)
        continuous[:, 10:14] = 1
        categorical[:, 0] = ord("A"); categorical[:, 1] = ord("B")
        binding = SimpleNamespace(
            asset="HG", phase_open_ts_ns=int(clock[0]),
            phase_close_ts_ns=int(clock[-1]),
            sane_ceiling_units=10**15, multiplier=25_000,
        )
        names, values = ExpandedEventTransform().transform_with_bindings(
            continuous, categorical, clock, (binding,))
        # Row zero is sane; the enormous second spread is not.  A wrapped
        # int64 product used to mark both trusted and train the delta.
        valid = names.index("derived.bid_px_delta.quotient_1e9.valid")
        self.assertEqual(values[:, valid].tolist(), [0.0, 0.0])

    def test_cached_transform_preserves_clock_parts_masks_and_prefix(self):
        n = 12
        continuous = np.zeros((n, len(CONTINUOUS_FIELDS)), np.float64)
        categorical = np.zeros((n, len(CATEGORICAL_FIELDS)), np.uint8)
        clock = (1_650_000_000_000_000_000
                 + np.arange(n, dtype=np.uint64) * 1_000_000_003)
        continuous[:, 3] = 2; continuous[:, 4] = 17
        continuous[:, 5] = 100; continuous[:, 6] = 3
        continuous[:, 7] = np.arange(n); continuous[:, 8] = 99
        continuous[:, 9] = 101; continuous[:, 10:14] = 2
        continuous[:, 15] = np.arange(n)
        categorical[:, 0] = ord("A"); categorical[:, 1] = ord("B")
        categorical[4, 4] = 1; continuous[4, 5] = 0
        binding = SimpleNamespace(
            asset="HG",
            phase_open_ts_ns=int(clock[0]), phase_close_ts_ns=int(clock[-1]),
            sane_ceiling_units=10**15, multiplier=25_000,
        )
        transform = ExpandedEventTransform()
        names, values = transform.transform_with_bindings(
            continuous, categorical, clock, (binding,))
        self.assertEqual(values.shape[0], n)
        for required in ("raw.ts_recv_ns.sec", "raw.ts_recv_ns.microsecond",
                         "raw.ts_recv_ns.nanosecond", "raw.ts_event_ns.sec",
                         "raw.price", "derived.receive_gap_ns.quotient_1e9",
                         "derived.receive_gap_ns.quotient_1e9.valid",
                         "derived.receive_gap_ns.remainder_1e9",
                         "derived.receive_gap_ns.remainder_1e9.valid"):
            self.assertIn(required, names)
        np.testing.assert_array_equal(
            values[:, names.index("derived.receive_gap_ns.quotient_1e9.valid")],
            values[:, names.index("derived.receive_gap_ns.remainder_1e9.valid")])
        price = values[:, names.index("raw.price")]
        self.assertEqual(price[4], 0.0)
        reconstructed = (
            values[:, names.index("raw.ts_recv_ns.sec")].astype(np.uint64) * 1_000_000_000
            + values[:, names.index("raw.ts_recv_ns.microsecond")].astype(np.uint64) * 1_000
            + values[:, names.index("raw.ts_recv_ns.nanosecond")].astype(np.uint64))
        np.testing.assert_array_equal(reconstructed, clock)
        mutated = continuous.copy(); mutated[8:, 6] += 1000
        _, changed = transform.transform_with_bindings(
            mutated, categorical, clock, (binding,))
        np.testing.assert_array_equal(values[:8], changed[:8])
        self.assertEqual(len(transform.conversion_law_sha256), 64)
        self.assertEqual(transform.normalization, "UNNORMALIZED_CANONICAL")

    def test_shared_phase_boundary_is_owned_by_prior_phase(self):
        clock = np.asarray([1_000_000_000, 2_000_000_000, 3_000_000_000],
                           np.uint64)
        continuous = np.zeros((3, len(CONTINUOUS_FIELDS)), np.float64)
        categorical = np.zeros((3, len(CATEGORICAL_FIELDS)), np.uint8)
        continuous[:, 3] = 1; continuous[:, 4] = 1
        continuous[:, 8] = 100; continuous[:, 9] = 102
        continuous[:, 10:14] = 1
        categorical[:, 0] = ord("A"); categorical[:, 1] = ord("B")
        bindings = (
            SimpleNamespace(asset="HG", phase_open_ts_ns=1_000_000_000,
                            phase_close_ts_ns=2_000_000_000,
                            sane_ceiling_units=10**9, multiplier=25_000),
            SimpleNamespace(asset="HG", phase_open_ts_ns=2_000_000_000,
                            phase_close_ts_ns=3_000_000_000,
                            sane_ceiling_units=10**9, multiplier=25_000),
        )
        names, values = ExpandedEventTransform().transform_with_bindings(
            continuous, categorical, clock, bindings, asset="HG")
        q = names.index("derived.phase_age_ns.quotient_1e9")
        r = names.index("derived.phase_age_ns.remainder_1e9")
        self.assertEqual(values[1, q] * 1_000_000_000 + values[1, r],
                         1_000_000_000)


if __name__ == "__main__":
    unittest.main()


class PhaseClockDtypeTest(unittest.TestCase):
    """A1: uint64 (+) int64 promotes to float64 under NumPy 2."""

    def _truth(self):
        # Real 2021-scale nanosecond epochs.  The float64 ULP at 1.6e18 is
        # 256 ns, so the naive expression cannot be exact here.
        recv = np.asarray([1_622_505_600_000_000_001,
                           1_622_505_600_000_000_129,
                           1_622_505_600_000_000_257], np.uint64)
        open_ns = np.full(3, 1_622_505_600_000_000_000, np.int64)
        close_ns = np.full(3, 1_622_509_200_000_000_000, np.int64)
        return {"ts_recv_ns": recv, "phase_open_ts_ns": open_ns,
                "phase_close_ts_ns": close_ns}

    def test_naive_mixed_dtype_expression_is_not_exact_at_real_scale(self):
        truth = self._truth()
        naive_age = truth["ts_recv_ns"] - truth["phase_open_ts_ns"]
        self.assertEqual(naive_age.dtype, np.float64)
        expected = np.asarray([1, 129, 257], np.int64)
        # This is the defect: the producer's exact integer clocks are NOT
        # reproduced by the naive expression.
        self.assertFalse(np.array_equal(naive_age.astype(np.int64), expected))

    def test_reference_phase_clocks_are_integer_exact_at_real_scale(self):
        truth = self._truth()
        age, remaining = reference_phase_clocks(truth, 3)
        self.assertEqual(age.dtype, np.int64)
        self.assertEqual(remaining.dtype, np.int64)
        self.assertTrue(np.array_equal(age, np.asarray([1, 129, 257], np.int64)))
        self.assertTrue(np.array_equal(
            remaining,
            np.asarray([3_599_999_999_999, 3_599_999_999_871,
                        3_599_999_999_743], np.int64)))

    def test_reference_phase_clocks_reproduce_the_producer(self):
        truth = self._truth()
        receive = truth["ts_recv_ns"].astype(np.int64)
        producer_age = receive - truth["phase_open_ts_ns"]
        producer_remaining = truth["phase_close_ts_ns"] - receive
        age, remaining = reference_phase_clocks(truth, 3)
        self.assertTrue(np.array_equal(age, producer_age))
        self.assertTrue(np.array_equal(remaining, producer_remaining))


class OptimizerFitCensusTest(unittest.TestCase):
    """C3/A-011: every optimizer fit is counted."""

    def setUp(self):
        reset_optimizer_fit_census()
        self.addCleanup(reset_optimizer_fit_census)

    def test_census_counts_registered_and_unregistered_categories(self):
        from .neural_sufficiency_resources import _run_optimizer
        _run_optimizer(lambda: torch.optim.SGD([torch.zeros(1, requires_grad=True)],
                                               lr=.1),
                       category="E1_REAL", fit_id="C01P01")
        _run_optimizer(lambda: torch.optim.SGD([torch.zeros(1, requires_grad=True)],
                                               lr=.1),
                       category="ARM", fit_id="arm/M1/encode")
        census = optimizer_fit_census()
        self.assertEqual(census["counts"]["E1_REAL"], 1)
        self.assertEqual(census["counts"]["ARM"], 1)
        self.assertEqual(census["registered_total"], 1)
        self.assertEqual(census["total"], 2)

    def test_unregistered_category_refuses(self):
        from .neural_sufficiency_resources import _run_optimizer
        with self.assertRaisesRegex(RealDiagnosticExecutorRefusal,
                                    "category is unregistered"):
            _run_optimizer(lambda: None, category="MYSTERY", fit_id="x")

    def test_registered_fit_ceiling_of_98_refuses(self):
        from .neural_sufficiency_resources import _run_optimizer
        maker = lambda: torch.optim.SGD([torch.zeros(1, requires_grad=True)], lr=.1)
        for index in range(MAXIMUM_REGISTERED_FITS_THROUGH_E2):
            _run_optimizer(maker, category="E1_REAL", fit_id=f"probe-{index}")
        with self.assertRaisesRegex(RealDiagnosticExecutorRefusal,
                                    "ceiling of 98 exceeded"):
            _run_optimizer(maker, category="E1_TWIN", fit_id="one-too-many")


class GateLawConstantTest(unittest.TestCase):
    def test_rehearsal_status_enum_carries_the_degenerate_states(self):
        self.assertIn("DEGENERATE_MAPPER", REHEARSAL_PATH_STATUSES)
        self.assertIn("DEGENERATE_CALIBRATOR", REHEARSAL_PATH_STATUSES)
        self.assertEqual(set(REHEARSAL_PATH_IMPLEMENTATION_REFUSALS),
                         {"DEGENERATE_MAPPER", "DEGENERATE_CALIBRATOR"})

    def test_raw_memory_occlusion_margin_replaces_the_1e6_epsilon(self):
        # B-07: a 1e-6 logit wiggle is not evidence of competence.
        self.assertGreaterEqual(RAW_MEMORY_OCCLUSION_MIN_AUROC_DROP, 0.05)
        self.assertGreater(RAW_MEMORY_OCCLUSION_MIN_AUROC_DROP, 1e-6)

    def test_route_gate_runs_past_three_completed_blocks(self):
        self.assertEqual(ROUTE_GATE_MINIMUM_CUTOFF, 3 * 256)

    def test_executed_threshold_law_describes_the_uncapped_platt_path(self):
        law = _executed_threshold_candidate_law()
        self.assertEqual(law["maximum_calibrated_levels"],
                         "UNBOUNDED_BY_DISTINCT_ROW_LEVELS")
        self.assertFalse(law["binned_venn_abers_levels_used"])
        self.assertEqual(law["calibrator"],
                         "UNCAPPED_CONTINUOUS_POSITIVE_SLOPE_PLATT")


class DegenerateScreenPathTest(unittest.TestCase):
    """Ruling 14 + F2 composition, measured live on the real E1r population.

    A null (constant) score makes the monotone Platt calibrator numerically
    constant.  On an objective-SCREEN or diagnostic artifact name that is the
    registered TYPED PATH STATUS -- a null control being null is its job -- and
    it must carry the SCREEN_-prefixed token so the F2 acceptance sweep (which
    hard-refuses on DEGENERATE_* anywhere in the receipt tree) still refuses on
    prophet/arm names while the screen path travels on.
    """

    @staticmethod
    def _resources():
        resources = ProductionExactDiagnosticResources.__new__(
            ProductionExactDiagnosticResources)
        resources._m8_payloads = {}
        resources._m8_path_payloads = {}
        return resources

    def test_screen_path_degeneracy_is_a_typed_status_not_a_chain_abort(self):
        from .neural_sufficiency_executor import DEGENERATE_PATH_STATUSES
        resources = self._resources()
        artifact = "E1r/objectives/C14P01/real"
        evaluation, status, receipt, detail = \
            resources._degenerate_screen_path_result(
                "DEGENERATE_CALIBRATOR",
                "DEGENERATE_CALIBRATOR: monotone Platt calibrator is "
                "numerically constant (slope=1.47, calibrated_spread=0.0)",
                artifact)
        self.assertIsNone(evaluation)
        self.assertEqual(status, "SCREEN_DEGENERATE_CALIBRATOR")
        self.assertEqual(len(receipt), 64)
        self.assertTrue(detail["degenerate"])
        self.assertTrue(detail["diagnostic_only"])
        self.assertEqual(detail["status"], status)
        self.assertEqual(detail["path_receipt_sha256"], receipt)
        payload = f"M8/paths/{artifact}/degenerate-status.json"
        self.assertIn(payload, resources._m8_payloads)
        self.assertEqual(resources._m8_path_payloads[artifact], [payload])
        # F2 composition: the SCREEN_ token must NOT be a finalize-refusing
        # status, while its unprefixed original remains one.
        self.assertNotIn(status, DEGENERATE_PATH_STATUSES)
        self.assertIn(detail["message"].split(":", 1)[0],
                      REHEARSAL_PATH_IMPLEMENTATION_REFUSALS)

    def test_screen_status_payload_names_the_original_typed_token(self):
        import json
        resources = self._resources()
        artifact = "E1r/RAWSUMMARY/diagnostic"
        _, status, _, _ = resources._degenerate_screen_path_result(
            "DEGENERATE_MAPPER", "mapper has no slope", artifact)
        self.assertEqual(status, "SCREEN_DEGENERATE_MAPPER")
        body = json.loads(
            resources._m8_payloads[f"M8/paths/{artifact}/degenerate-status.json"])
        self.assertEqual(body["schema"], "entry-v2-degenerate-screen-path-v1")
        self.assertEqual(body["status"], "SCREEN_DEGENERATE_MAPPER")
        self.assertEqual(body["original_status"], "DEGENERATE_MAPPER")
        self.assertEqual(body["artifact"], artifact)
