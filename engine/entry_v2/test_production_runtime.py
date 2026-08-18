#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path
from contextlib import contextmanager
from types import SimpleNamespace
import threading
import time
import tempfile
import unittest
from unittest import mock

import numpy as np

from . import common as C
from .event_pack import CATEGORY_SIZES
from .durable_store import DurableEntryV2Store
from .diagnostic_corpus import (
    DiagnosticCorpus, LIFECYCLE_PROVENANCE_RECEIPT_KEY,
)
from .production_runtime import (
    PRODUCTION_ARRAY_CACHE_BYTES,
    PRODUCTION_DISK_CACHE_MEMORY_RESERVE_BYTES,
    PRODUCTION_MEMORY_RESERVE_BYTES,
    _build_parallel_asset_corpus,
    _bind_isolated_process_lifecycle,
    _mem_available_bytes,
    _preload_session_arrays,
    _system_factory,
    ColdAssetProcessPool,
    ProductionDiagnosticStage,
    build_production_diagnostic_stage,
    extend_production_diagnostic_stage,
    build_production_runtime,
)
from .session_stream import SessionArrayCache
from .production_driver import CorpusStage
from .train import TrainingConfig


class ProductionRuntimeTest(unittest.TestCase):
    def test_real_corpus_preflight_precedes_atlas_finalization(self) -> None:
        """A structural refusal must not pay for candidate-atlas work."""
        with tempfile.TemporaryDirectory() as directory:
            backing = Path(directory) / "array-cache"
            cache = SessionArrayCache(1024, backing_dir=backing)
            corpus_stage = CorpusStage(
                SimpleNamespace(receipt={"corpus_window": {
                    "maximum_d8": 20210930}}, sessions=()), {})
            validator = mock.Mock(
                side_effect=C.EntryV2Refusal("pre-atlas real-corpus refusal"))
            with mock.patch(
                    "engine.entry_v2.production_runtime.build_production_corpus_stage",
                    return_value=corpus_stage), mock.patch(
                    "engine.entry_v2.production_runtime.finalize_diagnostic_corpus",
                    autospec=True) as finalize:
                with self.assertRaisesRegex(
                        C.EntryV2Refusal, "pre-atlas real-corpus refusal"):
                    build_production_diagnostic_stage(
                        C.CACHE_ROOT, array_cache=cache,
                        maximum_d8=20210930,
                        pre_finalize_validator=validator,
                    )
            validator.assert_called_once_with(corpus_stage)
            finalize.assert_not_called()
            self.assertFalse(
                (backing.parent / f"{backing.name}.diagnostic-planes").exists())
            cache.close()

    def test_cold_asset_process_pool_is_spawned_and_idempotently_closed(self) -> None:
        with mock.patch(
                "engine.entry_v2.production_runtime.torch.cuda.is_initialized",
                return_value=False):
            pool = ColdAssetProcessPool()
        self.assertEqual(
            pool._executor._mp_context.get_start_method(), "spawn"
        )
        pool.close()
        pool.close()
        with mock.patch(
                "engine.entry_v2.production_runtime.torch.cuda.is_initialized",
                return_value=True):
            with self.assertRaisesRegex(C.EntryV2Refusal, "before CUDA"):
                ColdAssetProcessPool()

    def test_isolated_process_lifecycle_reports_partial_restart_as_mixed(self) -> None:
        parent = SimpleNamespace(receipt={
            "verified_session_warm_hits": 6,
            "model_array_bytes_reused": 60,
        })
        diagnostic = DiagnosticCorpus(
            parent, (object(), object(), object()), (), {
                "diagnostic_plane_bytes": 30,
                LIFECYCLE_PROVENANCE_RECEIPT_KEY: {
                    "cumulative_window_identity_sha256": "a" * 64,
                },
                "receipt_sha256": "b" * 64,
            },
        )
        results = {}
        for asset in C.ASSETS:
            semantic = {
                "schema": "entry-v2-cold-asset-window-v1",
                "verified_session_count": 2,
                "model_array_bytes": 20,
                "diagnostic_session_count": 1,
                "diagnostic_plane_bytes": 10,
            }
            marker_hit = asset == "HG"
            results[asset] = {
                "marker_hit": marker_hit,
                "marker_semantic_sha256": C.object_sha256(semantic),
                "semantic": semantic,
                "execution": None if marker_hit else {
                    "physical_full_pack_opens": 2,
                    "model_array_physical_fills": 2,
                    "verified_session_durable_hits": 0,
                    "verified_session_cold_publishes": 2,
                    "diagnostic_plane_durable_hits": 0,
                    "model_array_bytes_materialized": 20,
                    "model_array_bytes_reused": 0,
                    "diagnostic_plane_bytes_materialized": 10,
                    "diagnostic_plane_bytes_reused": 0,
                },
            }
        rebound = _bind_isolated_process_lifecycle(diagnostic, results)
        lifecycle = rebound.receipt[LIFECYCLE_PROVENANCE_RECEIPT_KEY]
        self.assertEqual(lifecycle["cold_or_warm"], "COLD")
        self.assertFalse(lifecycle["warm_corpus_ready"])
        self.assertEqual(lifecycle["physical_full_pack_opens"], 4)
        body = dict(rebound.receipt)
        claimed = body.pop("receipt_sha256")
        self.assertEqual(claimed, C.object_sha256(body))

    def test_incremental_stage_transfers_observer_ownership_and_never_opens_old(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = DurableEntryV2Store(Path(directory) / "durable")
            cache = SessionArrayCache(1024, durable_store=store)
            old_source = SimpleNamespace(open_arrays=mock.Mock(
                side_effect=AssertionError("old source reopened")))
            old_corpus = SimpleNamespace(
                receipt={"corpus_window": {"maximum_d8": 20211231}},
                sessions=(SimpleNamespace(source=old_source),),
            )
            new_corpus = SimpleNamespace(
                receipt={"corpus_window": {"maximum_d8": 20220630}},
                sessions=(),
            )
            old_map = {asset: SimpleNamespace(close=mock.Mock())
                       for asset in C.ASSETS}
            new_map = {asset: SimpleNamespace(close=mock.Mock())
                       for asset in C.ASSETS}
            old = ProductionDiagnosticStage(
                CorpusStage(old_corpus, {"authority": 1}), object(), old_map,
                store.root / "diagnostic-planes", cache, store,
                C.CACHE_ROOT.resolve(), (old_map,),
            )
            extension = ProductionDiagnosticStage(
                CorpusStage(new_corpus, {"authority": 1}), object(), new_map,
                store.root / "diagnostic-planes", cache, store,
                C.CACHE_ROOT.resolve(), (new_map,),
            )
            merged_corpus = SimpleNamespace()
            merged_diagnostic = object()
            with mock.patch(
                    "engine.entry_v2.production_runtime.build_production_diagnostic_stage",
                    return_value=extension) as build, mock.patch(
                    "engine.entry_v2.production_runtime.merge_chronological_corpora",
                    return_value=merged_corpus), mock.patch(
                    "engine.entry_v2.production_runtime.merge_diagnostic_corpora",
                    return_value=merged_diagnostic):
                merged = extend_production_diagnostic_stage(
                    old, new_maximum_d8=20220630)
            build.assert_called_once_with(
                C.CACHE_ROOT.resolve(), array_cache=cache,
                maximum_d8=20220630, minimum_d8_exclusive=20211231,
                durable_store=store,
            )
            old_source.open_arrays.assert_not_called()
            old.close()
            extension.close()
            for observer in (*old_map.values(), *new_map.values()):
                observer.close.assert_not_called()
            merged.close(); merged.close()
            self.assertTrue(all(observer.close.call_count == 1
                                for observer in old_map.values()))
            self.assertTrue(all(observer.close.call_count == 1
                                for observer in new_map.values()))
            cache.close()

    def test_incremental_stage_failure_cleans_only_new_observers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = DurableEntryV2Store(Path(directory) / "durable")
            cache = SessionArrayCache(1024, durable_store=store)
            corpus = lambda maximum: SimpleNamespace(
                receipt={"corpus_window": {"maximum_d8": maximum}}, sessions=())
            old_map = {asset: SimpleNamespace(close=mock.Mock())
                       for asset in C.ASSETS}
            new_map = {asset: SimpleNamespace(close=mock.Mock())
                       for asset in C.ASSETS}
            old = ProductionDiagnosticStage(
                CorpusStage(corpus(20211231), {"authority": 1}), object(), old_map,
                store.root / "diagnostic-planes", cache, store,
                C.CACHE_ROOT.resolve(), (old_map,),
            )
            extension = ProductionDiagnosticStage(
                CorpusStage(corpus(20220630), {"authority": 1}), object(), new_map,
                store.root / "diagnostic-planes", cache, store,
                C.CACHE_ROOT.resolve(), (new_map,),
            )
            with mock.patch(
                    "engine.entry_v2.production_runtime.build_production_diagnostic_stage",
                    return_value=extension), mock.patch(
                    "engine.entry_v2.production_runtime.merge_chronological_corpora",
                    side_effect=C.EntryV2Refusal("merge failure")):
                with self.assertRaisesRegex(C.EntryV2Refusal, "merge failure"):
                    extend_production_diagnostic_stage(
                        old, new_maximum_d8=20220630)
            self.assertTrue(all(observer.close.call_count == 0
                                for observer in old_map.values()))
            self.assertTrue(all(observer.close.call_count == 1
                                for observer in new_map.values()))
            old.close()
            self.assertTrue(all(observer.close.call_count == 1
                                for observer in old_map.values()))
            cache.close()

    def test_production_diagnostic_refuses_durable_store_inside_substrate(self) -> None:
        with tempfile.TemporaryDirectory(dir=C.CACHE_ROOT) as directory:
            store = DurableEntryV2Store(Path(directory) / "durable")
            cache = SessionArrayCache(1024, durable_store=store)
            with self.assertRaisesRegex(C.EntryV2Refusal, "outside"):
                build_production_diagnostic_stage(
                    C.CACHE_ROOT, array_cache=cache, durable_store=store,
                    maximum_d8=20210930,
                )
            cache.close()

    def test_effective_memory_admission_honors_cgroup_not_host(self) -> None:
        gib = 1024 ** 3
        values = {
            Path("/proc/meminfo"): "MemAvailable: 1048576000 kB\n",
            Path("/sys/fs/cgroup/memory.max"): str(263 * gib),
            Path("/sys/fs/cgroup/memory.current"): str(13 * gib),
            Path("/sys/fs/cgroup/memory.stat"): (
                f"file {10 * gib}\nshmem {8 * gib}\n"
                "file_dirty 0\nfile_writeback 0\n"
            ),
        }

        def read_text(path: Path, *_args, **_kwargs) -> str:
            return values[path]

        with mock.patch.object(
                Path, "read_text", autospec=True, side_effect=read_text):
            # 250 GiB hard headroom plus 2 GiB clean file-cache credit;
            # the host's ~1000 GiB can no longer authorize the process.
            self.assertEqual(_mem_available_bytes(), 252 * gib)
            self.assertLess(
                _mem_available_bytes(),
                PRODUCTION_ARRAY_CACHE_BYTES + PRODUCTION_MEMORY_RESERVE_BYTES,
            )
            self.assertGreater(
                _mem_available_bytes(),
                PRODUCTION_DISK_CACHE_MEMORY_RESERVE_BYTES,
            )

    def test_system_factory_uses_exact_event_category_sizes(self) -> None:
        system = _system_factory(TrainingConfig(device="cpu"))
        self.assertEqual(system.encoder.event_category_sizes, CATEGORY_SIZES)

    @staticmethod
    def _forecast_stub():
        return SimpleNamespace(
            receipt_sha256="a" * 64,
            assets=frozenset(C.ASSETS),
            forecast=lambda _query: None,
            session_regime=lambda _asset, _trading_day: None,
        )

    def test_parallel_asset_results_merge_in_canonical_order(self) -> None:
        class ForecastStub:
            receipt_sha256 = "a" * 64
            assets = frozenset(C.ASSETS)

            @staticmethod
            def forecast(_query):
                return None

            @staticmethod
            def session_regime(_asset, _trading_day):
                return None

        delays = {"HG": 0.05, "NKD": 0.03, "SI": 0.01}
        completion: list[str] = []
        seen_caches = []
        seen_maxima = []
        seen_strict = []

        def build_one(artifacts, _contexts, provider, **_kwargs):
            asset = artifacts[0].asset
            seen_caches.append(_kwargs["array_cache"])
            seen_maxima.append(_kwargs["maximum_d8"])
            seen_strict.append(_kwargs["require_durable_window"])
            self.assertEqual(provider.assets, frozenset((asset,)))
            time.sleep(delays[asset])
            completion.append(asset)
            return asset

        sentinel = object()
        artifacts = tuple(SimpleNamespace(asset=asset) for asset in C.ASSETS)
        contexts = {asset: object() for asset in C.ASSETS}
        cache = SessionArrayCache(1024)
        with mock.patch(
                "engine.entry_v2.production_runtime.build_corpus",
                side_effect=build_one), mock.patch(
                "engine.entry_v2.production_runtime.merge_asset_corpora",
                return_value=sentinel) as merge:
            result = _build_parallel_asset_corpus(
                artifacts, contexts, ForecastStub(), cache,
                maximum_d8=20210930,
                require_durable_window=True,
            )
        self.assertIs(result, sentinel)
        self.assertEqual(completion[0], "SI")
        self.assertEqual({id(value) for value in seen_caches}, {id(cache)})
        self.assertEqual(seen_maxima, [20210930] * len(C.ASSETS))
        self.assertEqual(seen_strict, [True] * len(C.ASSETS))
        merge.assert_called_once_with(
            ("HG", "NKD", "SI"), maximum_d8=20210930,
            minimum_d8_exclusive=None,
        )

    def test_parallel_asset_failure_cancels_sibling_lanes(self) -> None:
        artifacts = tuple(SimpleNamespace(asset=asset) for asset in C.ASSETS)
        contexts = {asset: object() for asset in C.ASSETS}
        cancel_events = []
        hg_started = threading.Event()
        hg_cancel_observed = threading.Event()

        def build_one(items, _contexts, _provider, **kwargs):
            cancel = kwargs["cancel_event"]
            cancel_events.append(cancel)
            asset = items[0].asset
            if asset == "HG":
                hg_started.set()
                if not cancel.wait(timeout=1.0):
                    self.fail("HG did not observe fail-fast cancellation")
                hg_cancel_observed.set()
                raise C.EntryV2Refusal("HG corpus construction was cancelled")
            if asset == "NKD":
                if not hg_started.wait(timeout=1.0):
                    self.fail("HG lane did not start before NKD refusal")
                raise C.EntryV2Refusal("deliberate lane refusal")
            if not cancel.wait(timeout=1.0):
                self.fail("sibling asset lane was not cancelled")
            raise C.EntryV2Refusal("asset corpus construction was cancelled")

        with mock.patch(
                "engine.entry_v2.production_runtime.build_corpus",
                side_effect=build_one):
            with self.assertRaisesRegex(C.EntryV2Refusal,
                                       "deliberate lane refusal"):
                _build_parallel_asset_corpus(
                    artifacts, contexts, self._forecast_stub()
                )
        self.assertTrue(cancel_events)
        self.assertEqual(len({id(value) for value in cancel_events}), 1)
        self.assertTrue(cancel_events[0].is_set())
        self.assertTrue(hg_cancel_observed.is_set())

    def test_prebuilt_runtime_never_reruns_native_and_binds_exact_root(self) -> None:
        runtime = build_production_runtime(C.CACHE_ROOT)
        owner = runtime.context_corpus
        self.assertEqual(owner.array_cache.capacity_bytes,
                         PRODUCTION_ARRAY_CACHE_BYTES)
        with self.assertRaisesRegex(C.EntryV2Refusal, "prebuilt-only"):
            runtime.cpp_wave("SI", Path("x"), Path("y"), 20210101, 20250701)
        with mock.patch.object(owner.array_cache, "clear",
                               wraps=owner.array_cache.clear) as clear:
            with self.assertRaisesRegex(C.EntryV2Refusal, "binding differs"):
                runtime.context_corpus(C.CACHE_ROOT.parent / "wrong")
            clear.assert_called_once_with()

    def test_preload_is_canonical_and_admitted_before_open(self) -> None:
        opened = []
        completed = []
        cache = SimpleNamespace(capacity_bytes=10_000, bytes_used=399)

        class Receipt:
            def __init__(self, key):
                self.receipt_sha256 = key * 64

            def canonical_bytes(self):
                return self.receipt_sha256.encode()

        class Source:
            def __init__(self, asset, d8, key):
                self.asset = asset
                self.d8 = d8
                self.qre2_path = Path(f"/{asset}/{d8}.qre2")
                self.max_cutoff = 3
                self.receipt = Receipt(key)
                self.array_cache = cache

            @contextmanager
            def open_arrays(self):
                opened.append((self.asset, self.d8))
                time.sleep({"HG": 0.05, "NKD": 0.03, "SI": 0.01}[self.asset])
                completed.append((self.asset, self.d8))
                yield None

        sources = (Source("SI", 20250103, "3"),
                   Source("HG", 20250102, "2"))
        observer_only = Source("NKD", 20250104, "4")
        # Canonical union includes the observer-only session and deduplicates SI.
        cache.bytes_used = 1197
        corpus = SimpleNamespace(
            sessions=tuple(SimpleNamespace(source=value) for value in sources)
        )
        with mock.patch(
                "engine.entry_v2.production_runtime._mem_available_bytes",
                return_value=1197 + PRODUCTION_MEMORY_RESERVE_BYTES):
            self.assertEqual(_preload_session_arrays(
                corpus, cache, additional_sources=(observer_only, sources[0])
            ), 1197)
        self.assertEqual(set(opened), {
            ("HG", 20250102), ("NKD", 20250104), ("SI", 20250103)
        })
        self.assertEqual(completed, [("SI", 20250103), ("NKD", 20250104),
                                     ("HG", 20250102)])

    def test_preload_surfaces_canonical_failure_waits_and_clears(self) -> None:
        lock = threading.Lock()
        active = 0
        max_active = 0

        class Cache:
            capacity_bytes = 10_000
            bytes_used = 0

            def __init__(self):
                self.clear_calls = 0

            def clear(self):
                nonlocal active
                with lock:
                    self.assert_no_active = active
                self.bytes_used = 0
                self.clear_calls += 1

        cache = Cache()

        class Receipt:
            def __init__(self, key):
                self.receipt_sha256 = key * 64

            def canonical_bytes(self):
                return self.receipt_sha256.encode()

        class Source:
            max_cutoff = 3

            def __init__(self, asset, delay, message):
                self.asset = asset
                self.d8 = 20250102
                self.qre2_path = Path(f"/{asset}/20250102.qre2")
                self.receipt = Receipt(asset[0].lower())
                self.array_cache = cache
                self.delay = delay
                self.message = message

            @contextmanager
            def open_arrays(self):
                nonlocal active, max_active
                with lock:
                    active += 1
                    max_active = max(max_active, active)
                try:
                    time.sleep(self.delay)
                    raise C.EntryV2Refusal(self.message)
                    yield None
                finally:
                    with lock:
                        active -= 1

        # HG is the first canonical source, while SI fails first in wall time.
        sources = (
            Source("SI", 0.01, "later-key failure"),
            Source("HG", 0.05, "canonical failure"),
            Source("NKD", 0.03, "middle-key failure"),
        )
        corpus = SimpleNamespace(sessions=tuple(
            SimpleNamespace(source=source) for source in sources
        ))
        with mock.patch(
                "engine.entry_v2.production_runtime._mem_available_bytes",
                return_value=10_000 + PRODUCTION_MEMORY_RESERVE_BYTES):
            with self.assertRaisesRegex(C.EntryV2Refusal, "later-key failure"):
                _preload_session_arrays(corpus, cache)
        self.assertGreater(max_active, 1)
        self.assertEqual(cache.clear_calls, 1)
        self.assertEqual(cache.assert_no_active, 0)

    def test_preload_memory_admission_refuses_before_open(self) -> None:
        source = SimpleNamespace(
            asset="SI", d8=20250102, qre2_path=Path("/SI/20250102.qre2"),
            max_cutoff=3,
            receipt=SimpleNamespace(
                receipt_sha256="a" * 64,
                canonical_bytes=lambda: b"identity"),
        )
        cache = SimpleNamespace(capacity_bytes=10_000, bytes_used=399)
        source.array_cache = cache
        source.open_arrays = mock.Mock()
        corpus = SimpleNamespace(sessions=(SimpleNamespace(source=source),))
        with mock.patch(
                "engine.entry_v2.production_runtime._mem_available_bytes",
                return_value=PRODUCTION_MEMORY_RESERVE_BYTES):
            with self.assertRaisesRegex(C.EntryV2Refusal, "MemAvailable"):
                _preload_session_arrays(corpus, cache)
        source.open_arrays.assert_not_called()

    def test_parallel_preload_matches_serial_cache_bytes_and_identity(self) -> None:
        class Receipt:
            def __init__(self, key):
                self.receipt_sha256 = key * 64

            def canonical_bytes(self):
                return f"identity-{self.receipt_sha256}".encode()

        class Source:
            def __init__(self, cache, asset, key, value):
                self.asset = asset
                self.d8 = 20250102
                self.qre2_path = Path(f"/{asset}/20250102.qre2")
                self.max_cutoff = 3
                self.receipt = Receipt(key)
                self.array_cache = cache
                self.value = value

            def _fill(self):
                continuous = np.full((3, 16), self.value, dtype=np.float64)
                categorical = np.full((3, 5), self.value, dtype=np.uint8)
                return continuous, categorical

            @contextmanager
            def open_arrays(self):
                continuous, categorical, _hit = self.array_cache.get_or_fill(
                    self, self._fill
                )
                yield continuous, categorical

        def sources_for(cache):
            return (
                Source(cache, "SI", "s", 3),
                Source(cache, "HG", "h", 2),
            )

        serial_cache = SessionArrayCache(10_000)
        serial_sources = sources_for(serial_cache)
        for source in sorted(serial_sources, key=lambda item: item.asset):
            with source.open_arrays():
                pass
        parallel_cache = SessionArrayCache(10_000)
        parallel_sources = sources_for(parallel_cache)
        corpus = SimpleNamespace(sessions=tuple(
            SimpleNamespace(source=source) for source in parallel_sources
        ))
        with mock.patch(
                "engine.entry_v2.production_runtime._mem_available_bytes",
                return_value=10_000 + PRODUCTION_MEMORY_RESERVE_BYTES):
            required = _preload_session_arrays(corpus, parallel_cache)
        self.assertEqual(required, serial_cache.bytes_used)
        self.assertEqual(parallel_cache.bytes_used, serial_cache.bytes_used)
        for source in parallel_sources:
            with source.open_arrays() as first, source.open_arrays() as second:
                self.assertIs(first[0], second[0])
                self.assertIs(first[1], second[1])
                self.assertEqual(
                    source.receipt.canonical_bytes(),
                    next(item for item in serial_sources
                         if item.asset == source.asset).receipt.canonical_bytes(),
                )

    def test_production_training_configuration_is_frozen(self) -> None:
        with self.assertRaisesRegex(C.EntryV2Refusal, "configuration is frozen"):
            build_production_runtime(
                C.CACHE_ROOT, TrainingConfig(device="cpu")
            )

    def test_winner_runtime_refuses_live_factory_without_bundle(self) -> None:
        resources = SimpleNamespace(
            ownership_transferred=True, policy_kind="direct_neural",
        )
        with self.assertRaisesRegex(C.EntryV2Refusal, "independently loadable bundle"):
            build_production_runtime(C.CACHE_ROOT, winner_resources=resources)


if __name__ == "__main__":
    unittest.main()
