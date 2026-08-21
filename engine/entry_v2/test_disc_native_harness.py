"""Harness self-tests: prove the differential gate can SEE its own mutants.

Every expected value here is hand-written.  Nothing is generated from the
constant the assertion reads (checking-data-contracts rule 5) and no test
asserts the comparator's own output back at it.
"""

from __future__ import annotations

import unittest

import numpy as np

from engine.entry_v2.disc_native_differential import (
    BuiltFeatures, RefusalObservation, compare_disc_native_features,
    compare_disc_native_refusals, detach_capture_arrays,
    mutate_max_volume_trade_size, observe_disc_native_refusal,
    swap_disc_native_names)

NAMES = ("disc_auction_session_present", "disc_prior_present",
         "disc_tape_h30_volume_slope_per_sec2", "disc_fill_coupling_destroyed")


def _built(matrix: np.ndarray, *, names: tuple[str, ...] = NAMES,
           snapshots: tuple[int, ...] = (1_000, 2_000, 3_000),
           sides: tuple[int, ...] = (1, 1, -1)) -> BuiltFeatures:
    return BuiltFeatures(names, matrix, np.asarray(snapshots, np.int64),
                         np.asarray(sides, np.int8))


def _reference_matrix() -> np.ndarray:
    return np.asarray([[0.5, -1.25, 3.0, 0.0],
                       [1.5, 2.25, -4.0, 1.0],
                       [7.75, 0.125, 9.5, 0.0]], np.float32)


class CompareFeatureBytesTest(unittest.TestCase):

    def test_identical_output_passes(self) -> None:
        """False-positive guard: an exact rebuild must not be flagged."""

        reference = _built(_reference_matrix())
        candidate = _built(_reference_matrix().copy())
        verdict = compare_disc_native_features(reference, candidate)
        self.assertEqual(verdict.status, "PASS")
        self.assertEqual(verdict.failures, ())

    def test_single_flipped_bit_fails(self) -> None:
        """One mantissa bit in one cell — float equality would still say PASS."""

        reference = _reference_matrix()
        mutated = reference.copy()
        view = mutated.view(np.uint32)
        view[1, 2] = view[1, 2] ^ np.uint32(1)
        self.assertNotEqual(
            reference.view(np.uint32)[1, 2], mutated.view(np.uint32)[1, 2])
        verdict = compare_disc_native_features(
            _built(reference), _built(mutated))
        self.assertEqual(verdict.status, "FAIL")
        joined = " | ".join(verdict.failures)
        self.assertIn("feature bytes differ in 1 cell(s)", joined)
        self.assertIn("row 1 column 2", joined)
        self.assertIn("disc_tape_h30_volume_slope_per_sec2", joined)

    def test_signed_zero_is_a_byte_difference(self) -> None:
        """-0.0 == 0.0 in float compare; the store contract is bytes."""

        reference = _reference_matrix()
        mutated = reference.copy()
        mutated[0, 3] = np.float32(-0.0)
        self.assertEqual(float(reference[0, 3]), float(mutated[0, 3]))
        verdict = compare_disc_native_features(
            _built(reference), _built(mutated))
        self.assertEqual(verdict.status, "FAIL")

    def test_float64_candidate_fails(self) -> None:
        reference = _reference_matrix()
        verdict = compare_disc_native_features(
            _built(reference), _built(reference.astype(np.float64)))
        self.assertEqual(verdict.status, "FAIL")
        self.assertIn("candidate matrix dtype is float64",
                      " | ".join(verdict.failures))

    def test_row_count_mismatch_fails(self) -> None:
        reference = _reference_matrix()
        verdict = compare_disc_native_features(
            _built(reference),
            _built(reference[:2], snapshots=(1_000, 2_000), sides=(1, 1)))
        self.assertEqual(verdict.status, "FAIL")
        self.assertIn("row count differs: reference=3 candidate=2",
                      " | ".join(verdict.failures))

    def test_row_identity_mismatch_fails(self) -> None:
        """Same values, one row aligned to the wrong snapshot second."""

        reference = _reference_matrix()
        verdict = compare_disc_native_features(
            _built(reference),
            _built(reference.copy(), snapshots=(1_000, 2_001, 3_000)))
        self.assertEqual(verdict.status, "FAIL")
        joined = " | ".join(verdict.failures)
        self.assertIn("row-identity column snapshot_ts_ns differs in 1 row(s)",
                      joined)
        self.assertIn("reference=2000 candidate=2001", joined)

    def test_side_mismatch_fails(self) -> None:
        reference = _reference_matrix()
        verdict = compare_disc_native_features(
            _built(reference), _built(reference.copy(), sides=(1, -1, -1)))
        self.assertEqual(verdict.status, "FAIL")
        self.assertIn("row-identity column side differs in 1 row(s)",
                      " | ".join(verdict.failures))


class NameOrderContractTest(unittest.TestCase):

    def test_name_swap_fails_with_identical_bytes(self) -> None:
        """Order is identity: values alone can never catch this mutant."""

        reference = _built(_reference_matrix())
        candidate = swap_disc_native_names(
            _built(_reference_matrix().copy()), first=0, second=1)
        self.assertEqual(
            reference.matrix.tobytes(), candidate.matrix.tobytes())
        self.assertEqual(candidate.names[0], "disc_prior_present")
        self.assertEqual(candidate.names[1], "disc_auction_session_present")
        verdict = compare_disc_native_features(reference, candidate)
        self.assertEqual(verdict.status, "FAIL")
        joined = " | ".join(verdict.failures)
        self.assertIn("feature name order differs at 2 position(s)", joined)
        self.assertIn("index 0", joined)

    def test_missing_name_reports_the_set_difference(self) -> None:
        reference = _built(_reference_matrix())
        candidate = _built(_reference_matrix()[:, :3],
                           names=NAMES[:2] + ("disc_not_in_the_oracle",))
        verdict = compare_disc_native_features(reference, candidate)
        self.assertEqual(verdict.status, "FAIL")
        joined = " | ".join(verdict.failures)
        self.assertIn("feature name count differs: reference=4 candidate=3",
                      joined)
        self.assertIn("disc_not_in_the_oracle", joined)
        self.assertIn("disc_fill_coupling_destroyed", joined)

    def test_swap_refuses_degenerate_indices(self) -> None:
        with self.assertRaises(ValueError):
            swap_disc_native_names(_built(_reference_matrix()),
                                   first=1, second=1)


class RefusalParityTest(unittest.TestCase):

    def test_matching_refusal_passes(self) -> None:
        verdict = compare_disc_native_refusals(
            RefusalObservation("DiscretionaryFeatureRefusal",
                               "snapshot is outside session"),
            RefusalObservation("DiscretionaryFeatureRefusal",
                               "snapshot is outside session"))
        self.assertEqual(verdict.status, "PASS")

    def test_type_mismatch_is_reported_as_a_type_failure(self) -> None:
        verdict = compare_disc_native_refusals(
            RefusalObservation("DiscretionaryFeatureRefusal",
                               "snapshot is outside session"),
            RefusalObservation("ValueError",
                               "snapshot is outside session"))
        self.assertEqual(verdict.status, "FAIL")
        self.assertEqual(len(verdict.failures), 1)
        self.assertIn("refusal type differs", verdict.failures[0])

    def test_message_mismatch_is_reported_as_a_message_failure(self) -> None:
        verdict = compare_disc_native_refusals(
            RefusalObservation("DiscretionaryFeatureRefusal",
                               "snapshot is outside session"),
            RefusalObservation("DiscretionaryFeatureRefusal",
                               "snapshot outside session"))
        self.assertEqual(verdict.status, "FAIL")
        self.assertEqual(len(verdict.failures), 1)
        self.assertIn("refusal message differs", verdict.failures[0])

    def test_both_mismatches_are_reported_separately(self) -> None:
        verdict = compare_disc_native_refusals(
            RefusalObservation("DiscretionaryFeatureRefusal", "a"),
            RefusalObservation("RuntimeError", "b"))
        self.assertEqual(len(verdict.failures), 2)

    def test_a_call_that_does_not_refuse_is_observed_as_no_refusal(self) -> None:
        observed = observe_disc_native_refusal(lambda: 1)
        self.assertEqual(observed.exception_type, "NO_REFUSAL")
        verdict = compare_disc_native_refusals(
            RefusalObservation("DiscretionaryFeatureRefusal", "x"), observed)
        self.assertEqual(verdict.status, "FAIL")

    def test_observation_captures_type_and_message(self) -> None:
        def refuse() -> None:
            raise RuntimeError("prior session is empty")

        observed = observe_disc_native_refusal(refuse)
        self.assertEqual(observed.exception_type, "RuntimeError")
        self.assertEqual(observed.message, "prior session is empty")


TICK_ROWS_DTYPE = np.dtype([("action", "u1"), ("price", "i8"), ("size", "i8")])


class TradeSizeMutantTest(unittest.TestCase):

    def _rows(self) -> np.ndarray:
        # Hand-derived: tick 10 trades 1+1+1 = 3, tick 20 trades 5+5 = 10.
        # Row 3 is a quote (not a trade), row 6 is a zero-size trade, row 7 is
        # off-tick.  The busiest tick is 20 and its first trade row is index 4.
        return np.asarray(
            [(ord("T"), 1000, 1), (ord("T"), 1000, 1), (ord("T"), 1000, 1),
             (ord("A"), 2000, 99), (ord("T"), 2000, 5), (ord("T"), 2000, 5),
             (ord("T"), 2000, 0), (ord("T"), 2050, 7)], TICK_ROWS_DTYPE)

    def test_mutant_targets_the_first_trade_at_the_busiest_tick(self) -> None:
        mutated, receipt = mutate_max_volume_trade_size(
            self._rows(), raw_tick=100)
        self.assertEqual(receipt["mutated_row_index"], 4)
        self.assertEqual(receipt["mutated_price_tick"], 20)
        self.assertEqual(receipt["tick_volume"], 10)
        self.assertEqual(receipt["size_before"], 5)
        self.assertEqual(receipt["size_after"], 6)
        self.assertEqual(int(mutated["size"][4]), 6)

    def test_mutant_does_not_touch_the_caller_array(self) -> None:
        rows = self._rows()
        before = rows.tobytes()
        mutate_max_volume_trade_size(rows, raw_tick=100)
        self.assertEqual(rows.tobytes(), before)

    def test_mutant_changes_exactly_one_row(self) -> None:
        rows = self._rows()
        mutated, _ = mutate_max_volume_trade_size(rows, raw_tick=100)
        differing = np.flatnonzero(rows["size"] != mutated["size"])
        self.assertEqual(differing.tolist(), [4])

    def test_mutant_refuses_a_session_without_trades(self) -> None:
        rows = np.asarray([(ord("A"), 1000, 5)], TICK_ROWS_DTYPE)
        with self.assertRaises(ValueError):
            mutate_max_volume_trade_size(rows, raw_tick=100)


class DetachCaptureArraysTest(unittest.TestCase):
    """Regression guard for a real segfault, not a hypothetical.

    Capturing the plane's construction kwargs kept a reference to
    EventPack.rows, an np.memmap the pack unmaps on __exit__; the first read
    after the materialize returned killed the interpreter (SIGSEGV, observed
    2026-08-21 at disc_native_fixtures.py:190).  Everything recorded is copied
    while the map is still open.
    """

    def test_arrays_are_copied_not_referenced(self) -> None:
        source = np.arange(6, dtype=np.int64)
        detached = detach_capture_arrays(source)
        source[0] = 99
        self.assertEqual(int(detached[0]), 0)
        self.assertTrue(detached.flags.owndata)

    def test_nested_mappings_are_copied(self) -> None:
        source = {"rows": np.arange(3, dtype=np.int64),
                  "truth": {"mid2": np.arange(3, dtype=np.int64)}}
        detached = detach_capture_arrays(source)
        source["truth"]["mid2"][1] = 77
        self.assertEqual(int(detached["truth"]["mid2"][1]), 1)
        self.assertTrue(detached["rows"].flags.owndata)

    def test_structured_arrays_keep_their_dtype(self) -> None:
        source = np.asarray([(ord("T"), 1000, 1)], TICK_ROWS_DTYPE)
        detached = detach_capture_arrays(source)
        self.assertEqual(detached.dtype, TICK_ROWS_DTYPE)
        self.assertEqual(detached.tobytes(), source.tobytes())

    def test_scalars_pass_through_unchanged(self) -> None:
        self.assertEqual(detach_capture_arrays(7), 7)
        self.assertEqual(detach_capture_arrays("REAL"), "REAL")
        self.assertIsNone(detach_capture_arrays(None))


if __name__ == "__main__":
    unittest.main()
