from __future__ import annotations

import json
from pathlib import Path
import struct
import tempfile
import unittest

import numpy as np

from . import common as C
from .event_pack import (
    CATEGORICAL_FIELDS,
    CONTINUOUS_FIELDS,
    EVENT_DTYPE,
    UNDEF_PRICE,
    EventPack,
    HEADER,
    MAGIC,
    ROW_BYTES,
    VERSION,
)


class EventPackTest(unittest.TestCase):
    def _write_rows(self, root: Path, rows: np.ndarray,
                    d8: int = 20250102) -> Path:
        p = root / f"SI_custom_{d8}.qre2"
        raw = HEADER.pack(MAGIC, VERSION, 0, d8, 7, 1_700_000_000,
                          1_700_000_010, len(rows), ROW_BYTES, 0)
        p.write_bytes(raw + rows.tobytes())
        sidecar = {
            "schema": "QRE2EVENTMETA2",
            "asset": "SI", "d8": d8, "locked_iid": 7,
            "event_count": len(rows),
            "session_assignment_clock": "ts_recv",
            "symbology_date_clock": "floor_utc(ts_recv)",
            "causal_visibility_clock": "IndexTs/ts_recv",
            "exchange_feature_clock": "ts_event",
            "equal_receive_time": "future",
            "tie_order": "ordered_input_manifest_then_dbn_decode_ordinal",
        }
        p.with_suffix(p.suffix + ".json").write_text(json.dumps(sidecar))
        return p

    @staticmethod
    def _rows(count: int) -> np.ndarray:
        rows = np.zeros(count, dtype=EVENT_DTYPE)
        rows["ts_recv_ns"] = (
            np.uint64(1_700_000_000_000_000_000)
            + np.arange(count, dtype=np.uint64)
        )
        rows["ts_event_ns"] = rows["ts_recv_ns"]
        rows["price"] = 100
        rows["bid_px"] = 99
        rows["ask_px"] = 101
        rows["action"] = ord("A")
        rows["side"] = ord("N")
        return rows

    def _write(self, root: Path, d8: int = 20250102) -> Path:
        p = root / f"SI_{d8}.qre2"
        rows = np.zeros(4, dtype=EVENT_DTYPE)
        rows["ts_recv_ns"] = [1_700_000_000_100_000_000,
                              1_700_000_001_000_000_000,
                              1_700_000_001_000_000_000,
                              1_700_000_001_000_000_001]
        rows["ts_event_ns"] = [rows["ts_recv_ns"][0] + 1_500,
                               rows["ts_recv_ns"][1],
                               rows["ts_recv_ns"][2] - 100,
                               rows["ts_recv_ns"][3] + 1]
        rows["price"] = [10, 11, 12, 13]
        rows["bid_px"] = 10
        rows["ask_px"] = 12
        rows["receive_session_sec"] = [0, 1, 1, 1]
        rows["action"] = [65, 84, 67, 77]
        raw = HEADER.pack(MAGIC, VERSION, 0, d8, 7, 1_700_000_000,
                          1_700_000_010, len(rows), ROW_BYTES, 0)
        p.write_bytes(raw + rows.tobytes())
        sidecar = {
            "schema": "QRE2EVENTMETA2",
            "asset": "SI", "d8": d8, "locked_iid": 7,
            "event_count": len(rows),
            "session_assignment_clock": "ts_recv",
            "symbology_date_clock": "floor_utc(ts_recv)",
            "causal_visibility_clock": "IndexTs/ts_recv",
            "exchange_feature_clock": "ts_event",
            "equal_receive_time": "future",
            "tie_order": "ordered_input_manifest_then_dbn_decode_ordinal",
        }
        p.with_suffix(p.suffix + ".json").write_text(json.dumps(sidecar))
        return p

    def test_strict_equal_timestamp_cutoff_and_exact_arrays(self) -> None:
        with tempfile.TemporaryDirectory(dir=C.CACHE_ROOT) as td:
            p = self._write(Path(td))
            with EventPack(p) as pack:
                self.assertEqual(pack.cutoff(1_700_000_001_000_000_000), 1)
                self.assertEqual(pack.cutoff(1_700_000_001_000_000_001), 3)
                self.assertEqual(pack.cutoff(1_700_000_001_000_000_002), 4)
                x, k = pack.model_arrays()
                self.assertEqual(x.shape, (4, 16))
                self.assertEqual(k[:, 0].tolist(), [65, 84, 67, 77])
                self.assertEqual(x[:, 0].tolist(), [0.0, 1.0, 1.0, 1.0])
                self.assertEqual(x[:, 1].tolist(), [100_000.0, 0.0, 0.0, 0.0])
                self.assertEqual(x[:, 2].tolist(), [0.0, 0.0, 0.0, 1.0])
                self.assertEqual(x[:, 3].tolist(), [-2.0, 0.0, 0.0, -1.0])
                self.assertEqual(x[:, 4].tolist(), [500.0, 0.0, 100.0, 999.0])
                self.assertEqual(x[:, 5].tolist(), [10.0, 11.0, 12.0, 13.0])

    def test_all_price_undefined_masks_canonicalize_only_sentinel_cells(self) -> None:
        rows = self._rows(8)
        for mask in range(8):
            for bit, name in enumerate(("price", "bid_px", "ask_px")):
                if mask & (1 << bit):
                    rows[name][mask] = UNDEF_PRICE
        with tempfile.TemporaryDirectory(dir=C.CACHE_ROOT) as td:
            with EventPack(self._write_rows(Path(td), rows)) as pack:
                continuous, categorical = pack.model_arrays()
        self.assertEqual(tuple(CONTINUOUS_FIELDS[5:10]),
                         ("price", "size", "sequence", "bid_px", "ask_px"))
        self.assertEqual(tuple(CATEGORICAL_FIELDS[:5]),
                         ("action", "side", "flags", "depth", "price_undef_mask"))
        np.testing.assert_array_equal(categorical[:, 4], np.arange(8, dtype=np.uint8))
        for row, mask in enumerate(range(8)):
            for bit, column in ((0, 5), (1, 8), (2, 9)):
                if mask & (1 << bit):
                    self.assertEqual(continuous[row, column], 0.0)
                    self.assertFalse(np.signbit(continuous[row, column]))
                else:
                    self.assertEqual(continuous[row, column], (100.0, 99.0, 101.0)[bit])

    def test_real_and_ordinary_no_bid_keep_exact_byte_indices(self) -> None:
        rows = self._rows(2)
        rows["flags"] = [168, 130]
        rows["depth"] = [7, 3]
        rows["bid_px"] = UNDEF_PRICE
        with tempfile.TemporaryDirectory(dir=C.CACHE_ROOT) as td:
            with EventPack(self._write_rows(Path(td), rows)) as pack:
                continuous, categorical = pack.model_arrays()
        np.testing.assert_array_equal(
            categorical,
            [[ord("A"), ord("N"), 168, 7, 2],
             [ord("A"), ord("N"), 130, 3, 2]],
        )
        np.testing.assert_array_equal(continuous[:, 8], [0.0, 0.0])
        np.testing.assert_array_equal(continuous[:, 5], [100.0, 100.0])
        np.testing.assert_array_equal(continuous[:, 9], [101.0, 101.0])

    def test_stop_excludes_later_sentinel_until_it_is_visible(self) -> None:
        rows = self._rows(2)
        rows["ask_px"][1] = UNDEF_PRICE
        with tempfile.TemporaryDirectory(dir=C.CACHE_ROOT) as td:
            with EventPack(self._write_rows(Path(td), rows)) as pack:
                prefix_x, prefix_k = pack.model_arrays(stop=1)
                full_x, full_k = pack.model_arrays(stop=2)
        self.assertEqual(prefix_k[:, 4].tolist(), [0])
        self.assertEqual(prefix_x[:, 9].tolist(), [101.0])
        self.assertEqual(full_k[:, 4].tolist(), [0, 4])
        self.assertEqual(full_x[:, 9].tolist(), [101.0, 0.0])

    def test_non_sentinel_large_price_integers_refuse_without_clipping(self) -> None:
        for value in (2**53 + 1, 2**62, UNDEF_PRICE - 1, np.iinfo(np.int64).min):
            with self.subTest(value=value), tempfile.TemporaryDirectory(
                dir=C.CACHE_ROOT
            ) as td:
                rows = self._rows(1)
                rows["price"] = value
                with EventPack(self._write_rows(Path(td), rows)) as pack:
                    with self.assertRaisesRegex(
                        C.EntryV2Refusal, "price exceeds float64 exact-integer range"
                    ):
                        pack.model_arrays()

    def test_filename_seal_refuses_before_open(self) -> None:
        with tempfile.TemporaryDirectory(dir=C.CACHE_ROOT) as td:
            p = Path(td) / "SI_20260102.qre2"
            with self.assertRaisesRegex(C.EntryV2Refusal, "2026 SEALED"):
                EventPack(p, require_sidecar=False)

    def test_future_reorder_refuses(self) -> None:
        with tempfile.TemporaryDirectory(dir=C.CACHE_ROOT) as td:
            p = self._write(Path(td))
            raw = bytearray(p.read_bytes())
            # Swap the first and final records without changing file length.
            a = raw[60:60 + ROW_BYTES]
            c = raw[60 + 3 * ROW_BYTES:60 + 4 * ROW_BYTES]
            raw[60:60 + ROW_BYTES] = c
            raw[60 + 3 * ROW_BYTES:60 + 4 * ROW_BYTES] = a
            p.write_bytes(raw)
            with self.assertRaisesRegex(C.EntryV2Refusal, "not nondecreasing"):
                EventPack(p)

    def test_receive_session_second_must_match_receive_clock_exactly(self) -> None:
        with tempfile.TemporaryDirectory(dir=C.CACHE_ROOT) as td:
            p = self._write(Path(td))
            raw = bytearray(p.read_bytes())
            # Row 1 is exactly one second after open; write a plausible but
            # wrong in-range session second and require exact refusal.
            offset = HEADER.size + ROW_BYTES + 68
            raw[offset:offset + 4] = struct.pack("<i", 0)
            p.write_bytes(raw)
            with self.assertRaisesRegex(C.EntryV2Refusal, "does not equal"):
                EventPack(p)

    def test_v1_header_and_sidecar_refuse_without_aliasing(self) -> None:
        with tempfile.TemporaryDirectory(dir=C.CACHE_ROOT) as td:
            p = self._write(Path(td))
            raw = bytearray(p.read_bytes())
            fields = list(HEADER.unpack(raw[:HEADER.size]))
            fields[0], fields[1] = b"QRE2EVT1", 1
            raw[:HEADER.size] = HEADER.pack(*fields)
            p.write_bytes(raw)
            with self.assertRaisesRegex(C.EntryV2Refusal, "unknown/corrupt"):
                EventPack(p)

            p = self._write(Path(td))
            sidecar_path = p.with_suffix(p.suffix + ".json")
            sidecar = json.loads(sidecar_path.read_text())
            sidecar["schema"] = "QRE2EVENTMETA1"
            sidecar_path.write_text(json.dumps(sidecar))
            with self.assertRaisesRegex(C.EntryV2Refusal, "not QRE2EVENTMETA2"):
                EventPack(p)


if __name__ == "__main__":
    unittest.main()
