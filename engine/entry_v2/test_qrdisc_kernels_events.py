"""The shared qrdisc kernels, judged against numpy's own answers.

SEAM UNDER TEST
    producer: engine/cpp/qr_entry_v2/src/qrdisc_kernels_events.cpp, reached
              through `qr_disc_native.probe_pairwise_sum`
    oracle:   `numpy.ndarray.sum` on the same float64 bytes

WHY A SEPARATE GATE
    `qrdisc_np_sum_f64` is the one float reduction this port re-derives instead
    of delegating (qrdisc_kernels_events.hpp).  Inside a family it is judged
    only through the family's output, where a one-ulp sum error can hide behind
    the float32 truncation the dense store applies.  Here it is compared in
    float64 bytes, at the lengths where a pairwise-only transcription is
    provably wrong: 8200, 9000, 10007, 16383, 16385, 20000 (measured against
    numpy 2.1.2 on this box).
"""

from __future__ import annotations

import unittest

import numpy as np

from engine.entry_v2.discretionary_features import DiscretionaryFeatureRefusal
from engine.entry_v2.qrdisc_native_loader import load_qrdisc_native
from engine.entry_v2.qrdisc_state_marshal import (
    qrdisc_marshal_plane, qrdisc_warm_plane_caches)
from engine.entry_v2.test_qrdisc_state_marshal import _phase_crossing_capture

# Lengths that straddle numpy's 8192-element reduction buffer, plus the small
# and medium regimes.  Hand-listed, not generated from the kernel's own
# constant, so a changed block size fails here instead of agreeing with itself.
QRDISC_SUM_LENGTHS = (0, 1, 2, 7, 8, 9, 127, 128, 129, 1000, 2049, 4096,
                      8191, 8192, 8193, 8200, 9000, 10007, 16383, 16384,
                      16385, 20000)


class QrdiscPairwiseSum(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_qrdisc_native()

    def test_matches_numpy_bit_for_bit_across_the_block_boundary(self) -> None:
        generator = np.random.default_rng(4242)
        for length in QRDISC_SUM_LENGTHS:
            values = generator.standard_normal(length) * 1e4
            native = self.module.probe_pairwise_sum(values)
            self.assertEqual(
                np.float64(native).tobytes(),
                np.float64(values.sum()).tobytes(),
                f"the port's sum differs from numpy's at length {length}")

    def test_an_unaligned_slice_still_matches(self) -> None:
        """The oracle sums slices, not fresh arrays: `sizes[run_start:index]`."""

        generator = np.random.default_rng(99)
        base = generator.standard_normal(4096) * 1e4
        for offset in range(9):
            for length in (7, 8, 17, 64, 129, 1000, 2000):
                values = base[offset:offset + length]
                self.assertEqual(
                    np.float64(self.module.probe_pairwise_sum(values)).tobytes(),
                    np.float64(values.sum()).tobytes(),
                    f"slice offset={offset} length={length} differs")

    def test_the_comparison_can_fail(self) -> None:
        """False-positive guard: a different array must not agree."""

        generator = np.random.default_rng(7)
        values = generator.standard_normal(10007) * 1e4
        other = generator.standard_normal(10007) * 1e4
        self.assertNotEqual(
            np.float64(self.module.probe_pairwise_sum(values)).tobytes(),
            np.float64(other.sum()).tobytes())


class QrdiscLedgerSum(unittest.TestCase):
    """`_ledger_sum` (discretionary_features.py:1128) at its own seam.

    Its consumers — `_level_values` and `_price_shape_values` — are not ported,
    so no family differential reaches this kernel.  The windows below are
    hand-transcribed from feature_map:2443-2455, which is where the oracle's own
    `_ledger_sum` calls come from.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.session, cls.capture, cls.plane = _phase_crossing_capture()
        qrdisc_warm_plane_caches(cls.plane, cls.capture.queries)
        cls.module = load_qrdisc_native()
        scalars, buffers = qrdisc_marshal_plane(cls.plane)
        cls.native = cls.module.build_plane(
            scalars=scalars, buffers=buffers,
            delegates={"feature_map": cls.plane.feature_map},
            refusal_type=DiscretionaryFeatureRefusal)

    def _windows(self, query: dict) -> list[tuple[int, int, int, int]]:
        candidate = query["formation_candidate"]
        side = int(query["side"])
        raw_tick = self.plane.raw_tick
        formation_tick = ((int(candidate["entry_bid_px"]) if side > 0
                           else int(candidate["entry_ask_px"])) // raw_tick)
        current_tick = ((int(query["current_bid"]) if side > 0
                         else int(query["current_ask"])) // raw_tick)
        formation_sec = int(candidate["decision_sec"])
        snapshot_sec = int((int(query["snapshot_ts_ns"]) - self.plane.open_ns)
                           // 1_000_000_000)
        windows = []
        for radius in (0, 2, 4):
            windows.append((formation_tick, radius, 0, formation_sec))
            windows.append((formation_tick, radius, formation_sec, snapshot_sec))
        windows.append((current_tick, 2, max(0, snapshot_sec - 30), snapshot_sec))
        return windows

    def test_ledger_sum_matches_the_oracle_on_every_row(self) -> None:
        for index, query in enumerate(self.capture.queries):
            for center, radius, left_sec, right_sec in self._windows(query):
                native = self.module.probe_ledger_sum(
                    self.native, center, radius, left_sec, right_sec)
                oracle = self.plane._ledger_sum(
                    center_tick=center, radius=radius,
                    left_sec=left_sec, right_sec=right_sec)
                self.assertEqual(
                    native[0].tobytes(), np.asarray(oracle[0]).tobytes(),
                    f"ledger totals differ at row {index} "
                    f"center={center} radius={radius}")
                self.assertEqual(
                    tuple(native[1:]), tuple(int(value) for value in oracle[1:]),
                    f"ledger scalars differ at row {index} "
                    f"center={center} radius={radius}")

    def test_the_comparison_can_fail(self) -> None:
        """False-positive guard: a shifted window must not agree."""

        query = self.capture.queries[-1]
        center, radius, left_sec, right_sec = self._windows(query)[1]
        native = self.module.probe_ledger_sum(
            self.native, center, radius, left_sec, right_sec)
        oracle = self.plane._ledger_sum(
            center_tick=center + 7, radius=radius,
            left_sec=left_sec, right_sec=right_sec)
        self.assertNotEqual(native[0].tobytes(), np.asarray(oracle[0]).tobytes())


if __name__ == "__main__":
    unittest.main()
