from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest import mock

import numpy as np
import torch

from . import common as C
from .contracts import CausalEntryExample, RawPrefixRef, Side
from .event_pack import EVENT_DTYPE, HEADER, MAGIC, ROW_BYTES, VERSION, EventPack
from .durable_store import DurableEntryV2Store
from .session_stream import (
    CUTOFF_RULE,
    MODEL_ARRAYS_CONVERSION_LAW_SHA256,
    SessionArrayCache,
    SessionEventSource,
)
from .train import EntrySessionBatch, EntrySessionSpec, SelfSupervisedTargets
from .selected_horizon_contract import SCHEMA_SHA256 as SELECTED_SCHEMA_SHA256


class SessionStreamTest(unittest.TestCase):
    D8 = 20250102
    OPEN = 1_735_776_000
    CLOSE = OPEN + 60
    IID = 77
    NATIVE_CUTOFF_RULE = (
        "lower_bound(ts_recv_ns,decision_ts_ns); "
        "equal receive-time batch is future"
    )

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(dir=C.CACHE_ROOT)
        root = Path(self._tmp.name)
        event_dir = root / "events" / "SI"
        event_dir.mkdir(parents=True)
        self.path = event_dir / f"{self.D8}.qre2"

        rows = np.zeros(4, dtype=EVENT_DTYPE)
        rows["ts_recv_ns"] = [
            (self.OPEN + 1) * 1_000_000_000,
            (self.OPEN + 2) * 1_000_000_000,
            (self.OPEN + 3) * 1_000_000_000,
            (self.OPEN + 4) * 1_000_000_000,
        ]
        rows["ts_event_ns"] = rows["ts_recv_ns"] - 123
        rows["price"] = [100, 101, 102, 103]
        rows["bid_px"] = [99, 100, 101, 102]
        rows["ask_px"] = [101, 102, 103, 104]
        rows["size"] = 2
        rows["bid_sz"] = 3
        rows["ask_sz"] = 4
        rows["bid_ct"] = 1
        rows["ask_ct"] = 1
        rows["sequence"] = np.arange(4, dtype=np.uint32)
        rows["receive_session_sec"] = [1, 2, 3, 4]
        rows["action"] = [65, 84, 67, 77]
        rows["side"] = [66, 65, 78, 66]
        self.rows = rows

        header = HEADER.pack(
            MAGIC, VERSION, C.ASSET_INDEX["SI"], self.D8, self.IID,
            self.OPEN, self.CLOSE, len(rows), ROW_BYTES, 0,
        )
        self.source_bytes = header + rows.tobytes()
        self.path.write_bytes(self.source_bytes)
        self.source_sha = C.file_sha256(self.path)
        descriptors = []
        for name in EVENT_DTYPE.names or ():
            dtype, offset = EVENT_DTYPE.fields[name][:2]
            descriptors.append({
                "name": name,
                "dtype": dtype.str.removeprefix("|"),
                "offset_bytes": int(offset),
            })
        sidecar = {
            "schema": "QRE2EVENTMETA2",
            "status": "READY",
            "asset": "SI",
            "asset_idx": C.ASSET_INDEX["SI"],
            "d8": self.D8,
            "record_window": {
                "start_d8": 20250101,
                "end_d8_exclusive": 20250103,
            },
            "locked_iid": self.IID,
            "selection_basis_d8": 20241231,
            "selection_basis_updates": 100,
            "selection_basis_symbol": "SIF5",
            "open_utc": self.OPEN,
            "close_utc": self.CLOSE,
            "event_count": len(rows),
            "event_pack_sha256": self.source_sha,
            "binary_file": f"events/SI/{self.D8}.qre2",
            "source_hashes": {
                "input_manifest_sha256": "1" * 64,
                "locks_sha256": "2" * 64,
                "phase_schedule_sha256": "3" * 64,
                "event_pack_sha256": self.source_sha,
            },
            # Keep this literal independent of the reader constant so a
            # producer/consumer identity drift cannot make the fixture pass
            # tautologically.
            "cutoff_rule": self.NATIVE_CUTOFF_RULE,
            "session_assignment_clock": "ts_recv",
            "symbology_date_clock": "floor_utc(ts_recv)",
            "causal_visibility_clock": "IndexTs/ts_recv",
            "exchange_feature_clock": "ts_event",
            "equal_receive_time": "future",
            "tie_order": "ordered_input_manifest_then_dbn_decode_ordinal",
            "binary_schema": {
                "magic": "QRE2EVT2",
                "byte_order": "little",
                "header_bytes": 60,
                "row_bytes": 76,
                "layout": "packed_array_of_structs",
                "arrays": descriptors,
            },
        }
        self.sidecar = sidecar
        self.sidecar_path = self.path.with_suffix(".qre2.json")
        self.sidecar_bytes = (
            json.dumps(sidecar, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode()
        self.sidecar_path.write_bytes(self.sidecar_bytes)
        self.sidecar_sha = hashlib.sha256(self.sidecar_bytes).hexdigest()
        stat = self.path.stat()
        self.source = SessionEventSource(
            qre2_path=self.path,
            source_sha256=self.source_sha,
            sidecar_sha256=self.sidecar_sha,
            asset="SI",
            d8=self.D8,
            locked_iid=self.IID,
            open_utc=self.OPEN,
            close_utc=self.CLOSE,
            event_count=4,
            max_cutoff=3,
            source_size_bytes=stat.st_size,
            source_device=stat.st_dev,
            source_inode=stat.st_ino,
            source_mtime_ns=stat.st_mtime_ns,
            source_ctime_ns=stat.st_ctime_ns,
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_bounded_arrays_receipt_and_close_on_every_exit(self) -> None:
        self.assertEqual(CUTOFF_RULE, self.NATIVE_CUTOFF_RULE)
        receipt = self.source.receipt
        payload = receipt.as_dict()
        claimed = payload.pop("receipt_sha256")
        self.assertEqual(C.object_sha256(payload), claimed)
        self.assertEqual(payload["trading_day"], self.D8)
        self.assertEqual(payload["max_cutoff"], 3)
        self.assertEqual(payload["materialized_event_count"], 3)
        self.assertEqual(payload["pack_event_count"], 4)
        self.assertEqual(payload["source_event_byte_range"], [60, 60 + 3 * 76])
        self.assertEqual(payload["source_event_byte_count"], 3 * 76)
        self.assertEqual(
            payload["conversion_law_sha256"],
            MODEL_ARRAYS_CONVERSION_LAW_SHA256,
        )

        class TrackingPack(EventPack):
            instances: list["TrackingPack"] = []

            def __init__(self, *args: object, **kwargs: object) -> None:
                super().__init__(*args, **kwargs)
                self.instances.append(self)

        original_sha = C.file_sha256
        qre2_hashes = 0

        def counted_sha(path: object) -> str:
            nonlocal qre2_hashes
            if Path(path).suffix == ".qre2":
                qre2_hashes += 1
            return original_sha(path)

        with mock.patch("engine.entry_v2.session_stream.EventPack", TrackingPack), \
                mock.patch.object(C, "file_sha256", side_effect=counted_sha):
            with self.source.materialize() as arrays:
                continuous, categorical = arrays
                self.assertEqual(continuous.shape, (3, 16))
                self.assertEqual(categorical.shape, (3, 5))
                self.assertEqual(continuous[:, 5].tolist(), [100.0, 101.0, 102.0])
                mapped = TrackingPack.instances[-1].rows._mmap
                self.assertFalse(mapped.closed)
            self.assertTrue(mapped.closed)

            with self.assertRaisesRegex(RuntimeError, "consumer failure"):
                with self.source.open_arrays():
                    mapped_on_error = TrackingPack.instances[-1].rows._mmap
                    raise RuntimeError("consumer failure")
            self.assertTrue(mapped_on_error.closed)
        self.assertEqual(qre2_hashes, 0)

    def test_cutoff_literal_mutation_refuses_before_conversion(self) -> None:
        drifted = json.loads(json.dumps(self.sidecar))
        drifted["cutoff_rule"] = (
            "lower_bound(ts_recv_ns,decision_ts_ns); retained events satisfy "
            "ts_recv_ns < decision_ts_ns; equal receive-time batch is future"
        )
        drifted_bytes = (
            json.dumps(drifted, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode()
        self.sidecar_path.write_bytes(drifted_bytes)
        drifted_source = replace(
            self.source,
            sidecar_sha256=hashlib.sha256(drifted_bytes).hexdigest(),
        )
        with mock.patch.object(EventPack, "model_arrays", autospec=True) as convert:
            with self.assertRaisesRegex(
                C.EntryV2Refusal, "cutoff law identity drift"
            ):
                with drifted_source.open_arrays():
                    pass
            convert.assert_not_called()

    def test_identity_drift_and_h2_refuse_before_conversion(self) -> None:
        with mock.patch.object(EventPack, "model_arrays", autospec=True) as convert:
            self.sidecar_path.write_bytes(self.sidecar_bytes + b" ")
            with self.assertRaisesRegex(C.EntryV2Refusal, "sidecar hash drift"):
                with self.source.open_arrays():
                    pass
            convert.assert_not_called()

        self.sidecar_path.write_bytes(self.sidecar_bytes)
        drifted_header = HEADER.pack(
            MAGIC, VERSION, C.ASSET_INDEX["SI"], self.D8, self.IID + 1,
            self.OPEN, self.CLOSE, len(self.rows), ROW_BYTES, 0,
        )
        self.path.write_bytes(drifted_header + self.rows.tobytes())
        drifted_source_sha = C.file_sha256(self.path)
        drifted_sidecar = json.loads(json.dumps(self.sidecar))
        drifted_sidecar["locked_iid"] = self.IID + 1
        drifted_sidecar["event_pack_sha256"] = drifted_source_sha
        drifted_sidecar["source_hashes"]["event_pack_sha256"] = drifted_source_sha
        drifted_sidecar_bytes = (
            json.dumps(drifted_sidecar, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode()
        self.sidecar_path.write_bytes(drifted_sidecar_bytes)
        drifted_stat = self.path.stat()
        header_drift_source = replace(
            self.source,
            source_sha256=drifted_source_sha,
            sidecar_sha256=hashlib.sha256(drifted_sidecar_bytes).hexdigest(),
            source_size_bytes=drifted_stat.st_size,
            source_device=drifted_stat.st_dev,
            source_inode=drifted_stat.st_ino,
            source_mtime_ns=drifted_stat.st_mtime_ns,
            source_ctime_ns=drifted_stat.st_ctime_ns,
        )
        with mock.patch.object(EventPack, "model_arrays", autospec=True) as convert:
            with self.assertRaisesRegex(C.EntryV2Refusal, "identity drift"):
                with header_drift_source.open_arrays():
                    pass
            convert.assert_not_called()

        self.path.write_bytes(self.source_bytes)
        self.sidecar_path.write_bytes(self.sidecar_bytes)
        raw = bytearray(self.path.read_bytes())
        raw.append(0)
        self.path.write_bytes(raw)
        with mock.patch.object(EventPack, "model_arrays", autospec=True) as convert:
            with self.assertRaisesRegex(C.EntryV2Refusal, "source stat identity drift"):
                with self.source.open_arrays():
                    pass
            convert.assert_not_called()

        self.path.write_bytes(self.source_bytes)
        alias_root = self.path.parents[2] / "event-alias"
        alias_root.symlink_to(self.path.parent, target_is_directory=True)
        alias_path = alias_root / self.path.name
        alias_source = replace(self.source, qre2_path=alias_path)
        with mock.patch.object(EventPack, "model_arrays", autospec=True) as convert:
            with self.assertRaisesRegex(C.EntryV2Refusal, "path identity drift"):
                with alias_source.open_arrays():
                    pass
            convert.assert_not_called()

        future = self.path.with_name("20250701.qre2")
        with self.assertRaisesRegex(C.EntryV2Refusal, "2025H2 HOLDOUT"):
            replace(self.source, qre2_path=future, d8=20250701)

    def test_streams_into_existing_entry_session_batch_type(self) -> None:
        examples = []
        for index, cutoff in enumerate((2, 3)):
            decision = int(self.rows[cutoff]["ts_recv_ns"])
            ref = RawPrefixRef(
                shard=str(self.path),
                event_start_index=0,
                event_end_index=cutoff,
                event_count=cutoff,
                first_availability_ts_ns=int(self.rows[0]["ts_recv_ns"]),
                last_availability_ts_ns=int(
                    self.rows[cutoff - 1]["ts_recv_ns"]
                ),
                source_hash=self.source_sha,
            )
            examples.append(CausalEntryExample(
                candidate_id=f"SI-{self.D8}-{index}",
                asset="SI",
                trading_day=self.D8,
                session_id=f"SI-{self.D8}",
                decision_ts_ns=decision,
                side=Side.LONG,
                phase="G1_PHASE_0",
                locked_iid=self.IID,
                raw_prefix_ref=ref,
                lineage_hash=str(index + 4) * 64,
            ))
        n = len(examples)
        template = EntrySessionSpec(
            source=self.source,
            examples=tuple(examples),
            candidate_cutoffs=torch.tensor([2, 3], dtype=torch.int64),
            candidate_features=torch.zeros((n, 1), dtype=torch.float64),
            context_values=torch.zeros((n, 1, 1, 1), dtype=torch.float64),
            context_type_ids=torch.zeros((1,), dtype=torch.int64),
            context_valid=torch.ones((n, 1, 1), dtype=torch.bool),
            self_supervised=SelfSupervisedTargets(
                horizon_value=torch.zeros((n, 4), dtype=torch.float64),
                horizon_valid=torch.ones((n, 4), dtype=torch.bool),
                phase_class=torch.zeros(n, dtype=torch.int64),
                phase_valid=torch.ones(n, dtype=torch.bool),
            ),
            selected_horizon_value=torch.arange(
                n * 6, dtype=torch.float64).reshape(n, 6),
            selected_horizon_valid=torch.tensor(
                [[True, True, False, True, True, True]] * n),
            selected_horizon_schema_sha256=SELECTED_SCHEMA_SHA256,
        )
        with self.source.materialize(template) as batch:
            self.assertIsInstance(batch, EntrySessionBatch)
            self.assertEqual(batch.event_continuous.shape, (3, 16))
            self.assertEqual(batch.event_categorical.shape, (3, 5))
            self.assertEqual(batch.candidate_ids, template.candidate_ids)
            self.assertIs(batch.candidate_features, template.candidate_features)
            self.assertIs(batch.context_values, template.context_values)
            self.assertIs(batch.self_supervised, template.self_supervised)
            self.assertIs(batch.selected_horizon_value,
                          template.selected_horizon_value)
            self.assertIs(batch.selected_horizon_valid,
                          template.selected_horizon_valid)
            self.assertEqual(batch.selected_horizon_value.numpy().tobytes(),
                             template.selected_horizon_value.numpy().tobytes())

    def test_cache_reuses_one_bitwise_immutable_conversion_without_receipt_drift(
            self) -> None:
        cache = SessionArrayCache(10_000)
        source = replace(self.source, array_cache=cache)
        receipt_before = source.receipt.canonical_bytes()
        original = EventPack.model_arrays
        with mock.patch.object(
                EventPack, "model_arrays", autospec=True,
                side_effect=original) as convert:
            with source.open_arrays() as first:
                first_copy = tuple(value.copy() for value in first)
                self.assertFalse(first[0].flags.writeable)
                self.assertFalse(first[1].flags.writeable)
            with source.open_arrays() as second:
                self.assertTrue(np.array_equal(first_copy[0], second[0]))
                self.assertTrue(np.array_equal(first_copy[1], second[1]))
            self.assertEqual(convert.call_count, 1)
        self.assertEqual(source.receipt.canonical_bytes(), receipt_before)
        self.assertEqual(cache.bytes_used, 3 * (16 * 8 + 5))
        measured = source.measurements.snapshot()
        self.assertEqual(measured["physical_full_pack_opens"], 1)
        self.assertEqual(measured["model_array_physical_fills"], 1)
        self.assertEqual(measured["header_revalidations"], 1)
        self.assertEqual(measured["array_cache_hits"], 1)
        cache.close()

    def test_incremental_cache_rollback_discards_only_new_receipts(self) -> None:
        cache = SessionArrayCache(10_000)
        first = replace(self.source, array_cache=cache, max_cutoff=2)
        second = replace(self.source, array_cache=cache, max_cutoff=3)
        with first.open_arrays():
            pass
        retained = cache.resident_receipts()
        retained_bytes = cache.bytes_used
        with second.open_arrays():
            pass
        admitted = cache.resident_receipts() - retained
        self.assertEqual(len(admitted), 1)
        cache.discard_receipts(admitted)
        self.assertEqual(cache.resident_receipts(), retained)
        self.assertEqual(cache.bytes_used, retained_bytes)
        with first.open_arrays():
            pass
        cache.close()

    def test_disk_backed_cache_is_bitwise_immutable_and_releases_resident_arrays(
            self) -> None:
        backing = self.path.parents[2] / "model-array-cache"
        cache = SessionArrayCache(10_000, backing_dir=backing)
        source = replace(self.source, array_cache=cache)
        original = EventPack.model_arrays
        with mock.patch.object(
                EventPack, "model_arrays", autospec=True,
                side_effect=original) as convert:
            with source.open_arrays() as first:
                self.assertIsInstance(first[0], np.memmap)
                self.assertIsInstance(first[1], np.memmap)
                expected = tuple(value.copy() for value in first)
                self.assertFalse(first[0].flags.writeable)
                self.assertFalse(first[1].flags.writeable)
            entries = tuple(backing.glob("*.arrays"))
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0].stat().st_mode & 0o777, 0o444)
            with source.open_arrays() as second:
                np.testing.assert_array_equal(second[0], expected[0])
                np.testing.assert_array_equal(second[1], expected[1])
            self.assertEqual(convert.call_count, 1)
        self.assertTrue(cache.disk_backed)
        self.assertEqual(cache.bytes_used, 3 * (16 * 8 + 5))
        cache.close()
        self.assertFalse(backing.exists())

    def test_disk_backed_cache_stat_mutation_refuses_before_yield(self) -> None:
        backing = self.path.parents[2] / "model-array-cache-drift"
        cache = SessionArrayCache(10_000, backing_dir=backing)
        source = replace(self.source, array_cache=cache)
        with source.open_arrays():
            pass
        entry = next(backing.glob("*.arrays"))
        entry.chmod(0o644)
        with self.assertRaisesRegex(
                C.EntryV2Refusal, "entry identity drift"):
            with source.open_arrays():
                pass
        entry.chmod(0o444)
        cache.close()

    def test_durable_cache_cold_close_warm_reopen_is_zero_fill_and_persistent(self) -> None:
        store_root = self.path.parents[2] / "durable-store"
        store = DurableEntryV2Store(store_root)
        cold_cache = SessionArrayCache(10_000, durable_store=store)
        cold_source = replace(self.source, array_cache=cold_cache)
        with cold_source.open_arrays() as arrays:
            expected = tuple(value.copy() for value in arrays)
        self.assertEqual(
            dict(cold_source.measurements.snapshot())[
                "physical_full_pack_opens"], 1)
        cold_cache.close()
        products = tuple((store_root / "session-arrays").iterdir())
        self.assertEqual(len(products), 2)
        self.assertTrue(all(path.stat().st_mode & 0o777 == 0o444
                            for path in products))
        producer = json.loads(next(
            path for path in products if path.suffix == ".json"
        ).read_text())["producer"]
        self.assertEqual(producer["physical_full_pack_opens"], 1)
        self.assertEqual(producer["model_array_physical_fills"], 1)

        reopened = DurableEntryV2Store(store_root)
        warm_cache = SessionArrayCache(10_000, durable_store=reopened)
        warm_source = replace(self.source, array_cache=warm_cache)
        with mock.patch.object(EventPack, "model_arrays", autospec=True) as convert:
            with warm_source.open_arrays() as arrays:
                np.testing.assert_array_equal(arrays[0], expected[0])
                np.testing.assert_array_equal(arrays[1], expected[1])
        convert.assert_not_called()
        measured = warm_source.measurements.snapshot()
        self.assertEqual(measured["physical_full_pack_opens"], 0)
        self.assertEqual(measured["model_array_physical_fills"], 0)
        self.assertEqual(measured["header_revalidations"], 1)
        self.assertEqual(measured["array_cache_hits"], 1)
        warm_cache.close()
        self.assertTrue(store_root.is_dir())
        self.assertEqual(len(tuple((store_root / "session-arrays").iterdir())), 2)

    def test_durable_store_concurrent_same_key_has_one_immutable_publisher(self) -> None:
        store = DurableEntryV2Store(self.path.parents[2] / "durable-race")
        identity = {"schema": "test", "d8": self.D8}
        law = "9" * 64
        arrays = (np.arange(16, dtype=np.int64),)

        def publish(_index):
            return store.publish(
                "session-arrays", identity, law, arrays,
                semantic={"schema": "test-map"},
                producer={"physical_full_pack_opens": 1,
                          "model_array_physical_fills": 1},
            )

        with ThreadPoolExecutor(max_workers=6) as executor:
            products = tuple(executor.map(publish, range(6)))
        self.assertEqual(sum(product.published for product in products), 1)
        self.assertEqual(len({product.key for product in products}), 1)
        self.assertEqual(len(tuple(
            (store.root / "session-arrays").iterdir())), 2)
        for product in products:
            np.testing.assert_array_equal(product.arrays[0], arrays[0])
            product.close()

    def test_durable_startup_waits_for_inflight_namespace_publication(self) -> None:
        root = self.path.parents[2] / "durable-startup-race"
        store = DurableEntryV2Store(root)
        original_lock = DurableEntryV2Store._publication_lock
        original_write = DurableEntryV2Store._write_all
        publication_writing = threading.Event()
        release_publication = threading.Event()
        startup_lock_attempt = threading.Event()
        call_guard = threading.Lock()
        lock_calls = 0

        @contextmanager
        def observed_lock(path):
            nonlocal lock_calls
            with call_guard:
                lock_calls += 1
                if lock_calls == 2:
                    startup_lock_attempt.set()
            with original_lock(path):
                yield

        def blocked_write(handle, raw, digest):
            publication_writing.set()
            if not release_publication.wait(timeout=5):
                raise AssertionError("startup race publication was not released")
            return original_write(handle, raw, digest)

        def publish():
            return store.publish(
                "session-arrays", {"schema": "startup-race", "d8": self.D8},
                "5" * 64, (np.arange(8, dtype=np.int64),),
                semantic={"schema": "startup-race"}, producer={"cold": True},
            )

        with mock.patch.object(DurableEntryV2Store, "_publication_lock",
                               side_effect=observed_lock), \
             mock.patch.object(DurableEntryV2Store, "_write_all",
                               side_effect=blocked_write), \
             ThreadPoolExecutor(max_workers=2) as executor:
            publisher = executor.submit(publish)
            self.assertTrue(publication_writing.wait(timeout=5))
            startup = executor.submit(DurableEntryV2Store, root)
            self.assertTrue(startup_lock_attempt.wait(timeout=5))
            self.assertFalse(startup.done())
            release_publication.set()
            product = publisher.result(timeout=5)
            reopened = startup.result(timeout=5)
        product.close()
        self.assertTrue(reopened.has_product(
            "session-arrays", {"schema": "startup-race", "d8": self.D8},
            "5" * 64,
        ))

    def test_durable_store_startup_refuses_corrupt_mutable_symlink_stale_h2_extra(self) -> None:
        def populated(name: str):
            root = self.path.parents[2] / name
            store = DurableEntryV2Store(root)
            product = store.publish(
                "session-arrays", {"schema": "test", "d8": self.D8},
                "8" * 64, (np.arange(4, dtype=np.uint8),),
                semantic={"schema": "test-map"}, producer={"cold": True},
            )
            product.close()
            return root, next((root / "session-arrays").glob("*.bin")), next(
                (root / "session-arrays").glob("*.json"))

        root, data, _sidecar = populated("durable-corrupt")
        data.chmod(0o644); data.write_bytes(b"xxxx"); data.chmod(0o444)
        lazy = DurableEntryV2Store(root)
        with self.assertRaisesRegex(C.EntryV2Refusal, "size/hash"):
            lazy.load("session-arrays", {"schema": "test", "d8": self.D8},
                      "8" * 64)

        root, data, _sidecar = populated("durable-size")
        data.chmod(0o644)
        with data.open("ab") as handle:
            handle.write(b"x")
        data.chmod(0o444)
        with self.assertRaisesRegex(C.EntryV2Refusal, "metadata identity"):
            DurableEntryV2Store(root)

    def test_durable_startup_indexes_metadata_and_hashes_only_accessed_product(self) -> None:
        def populated(name: str):
            product_root = self.path.parents[2] / name
            product_store = DurableEntryV2Store(product_root)
            item = product_store.publish(
                "session-arrays", {"schema": "test", "d8": self.D8},
                "8" * 64, (np.arange(4, dtype=np.uint8),),
                semantic={"schema": "test-map"}, producer={"cold": True},
            )
            item.close()
            return product_root, next(
                (product_root / "session-arrays").glob("*.bin")), next(
                (product_root / "session-arrays").glob("*.json"))

        root = self.path.parents[2] / "durable-lazy-index"
        store = DurableEntryV2Store(root)
        identities = tuple({"schema": "lazy", "d8": self.D8, "slot": slot}
                           for slot in range(3))
        for identity in identities:
            product = store.publish(
                "session-arrays", identity, "6" * 64,
                (np.arange(8, dtype=np.int64),),
                semantic={"schema": "lazy"}, producer={"cold": True},
            )
            product.close()
        original = C.file_sha256
        hashed = []

        def counted(path):
            hashed.append(Path(path))
            return original(path)

        with mock.patch.object(C, "file_sha256", side_effect=counted):
            reopened = DurableEntryV2Store(root)
            self.assertFalse(any(path.suffix == ".bin" for path in hashed))
            self.assertTrue(reopened.has_product(
                "session-arrays", identities[1], "6" * 64))
            self.assertFalse(any(path.suffix == ".bin" for path in hashed))
            product = reopened.load("session-arrays", identities[1], "6" * 64)
            self.assertIsNotNone(product)
            assert product is not None
            product.close()
        self.assertEqual(sum(path.suffix == ".bin" for path in hashed), 1)

        root, _data, _sidecar = populated("durable-old-law")
        store = DurableEntryV2Store(root)
        with self.assertRaisesRegex(C.EntryV2Refusal, "law is stale"):
            store.load(
                "session-arrays", {"schema": "test", "d8": self.D8},
                "7" * 64,
            )

        with self.assertRaisesRegex(C.EntryV2Refusal, "path traversal"):
            DurableEntryV2Store.product_key(
                "session-arrays",
                {"schema": "test", "source_path": "../escape"},
                "8" * 64,
            )

        root, data, _sidecar = populated("durable-mutable")
        data.chmod(0o644)
        with self.assertRaisesRegex(C.EntryV2Refusal, "mutable"):
            DurableEntryV2Store(root)

        root, _data, sidecar = populated("durable-sidecar-mutable")
        sidecar.chmod(0o644)
        with self.assertRaisesRegex(C.EntryV2Refusal, "mutable"):
            DurableEntryV2Store(root)

        root, data, _sidecar = populated("durable-symlink")
        target = self.path.parents[2] / "durable-symlink-target"
        target.write_bytes(data.read_bytes())
        data.unlink(); data.symlink_to(target)
        with self.assertRaisesRegex(C.EntryV2Refusal, "regular file"):
            DurableEntryV2Store(root)

        for name, mutate, pattern in (
            ("durable-schema", lambda body: body.__setitem__(
                "schema", "wrong"), "metadata identity"),
            ("durable-stale", lambda body: body.__setitem__(
                "product_law_sha256", "7" * 64), "metadata identity"),
            ("durable-h2", lambda body: body["identity"].__setitem__(
                "d8", C.HOLDOUT_START_D8), "HOLDOUT"),
        ):
            root, _data, sidecar = populated(name)
            body = json.loads(sidecar.read_text())
            mutate(body)
            body.pop("receipt_sha256")
            body["receipt_sha256"] = C.object_sha256(body)
            sidecar.chmod(0o644)
            sidecar.write_bytes(C.canonical_bytes(body))
            sidecar.chmod(0o444)
            with self.assertRaisesRegex(C.EntryV2Refusal, pattern):
                DurableEntryV2Store(root)

        root, _data, _sidecar = populated("durable-extra")
        (root / "session-arrays" / "extra").write_text("x")
        with self.assertRaisesRegex(C.EntryV2Refusal, "extra"):
            DurableEntryV2Store(root)

    def test_cache_hit_rechecks_sidecar_identity(self) -> None:
        cache = SessionArrayCache(10_000)
        source = replace(self.source, array_cache=cache)
        with source.open_arrays():
            pass
        self.sidecar_path.write_bytes(self.sidecar_bytes + b" ")
        with self.assertRaisesRegex(C.EntryV2Refusal, "sidecar hash drift"):
            with source.open_arrays():
                pass

    def test_cache_failed_fill_is_not_published_and_can_retry(self) -> None:
        cache = SessionArrayCache(10_000)
        source = replace(self.source, array_cache=cache)
        original = EventPack.model_arrays
        attempts = 0

        def flaky(pack, *args, **kwargs):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise C.EntryV2Refusal("conversion failed")
            return original(pack, *args, **kwargs)

        with mock.patch.object(
                EventPack, "model_arrays", autospec=True,
                side_effect=flaky) as convert:
            with self.assertRaisesRegex(C.EntryV2Refusal, "conversion failed"):
                with source.open_arrays():
                    pass
            self.assertEqual(len(cache), 0)
            with source.open_arrays():
                pass
            self.assertEqual(convert.call_count, 2)
        self.assertEqual(len(cache), 1)

    def test_cache_capacity_refuses_before_conversion(self) -> None:
        required = SessionArrayCache.planned_bytes(self.source)
        source = replace(
            self.source, array_cache=SessionArrayCache(required - 1)
        )
        with mock.patch.object(EventPack, "model_arrays", autospec=True) as convert:
            with self.assertRaisesRegex(C.EntryV2Refusal, "capacity"):
                with source.open_arrays():
                    pass
        convert.assert_not_called()

    def test_cache_concurrent_access_is_single_flight(self) -> None:
        cache = SessionArrayCache(10_000)
        source = replace(self.source, array_cache=cache)
        original = EventPack.model_arrays

        def convert(pack, *args, **kwargs):
            return original(pack, *args, **kwargs)

        def consume(_index):
            with source.open_arrays() as arrays:
                return arrays[0].copy(), arrays[1].copy()

        with mock.patch.object(
                EventPack, "model_arrays", autospec=True,
                side_effect=convert) as conversion:
            with ThreadPoolExecutor(max_workers=6) as executor:
                values = tuple(executor.map(consume, range(6)))
        self.assertEqual(conversion.call_count, 1)
        for continuous, categorical in values[1:]:
            self.assertTrue(np.array_equal(continuous, values[0][0]))
            self.assertTrue(np.array_equal(categorical, values[0][1]))


if __name__ == "__main__":
    unittest.main()
