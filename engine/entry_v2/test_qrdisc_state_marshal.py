"""Real-data contract test for the qrdisc marshalling boundary.

BOUNDARY UNDER TEST
    producer: engine/entry_v2/qrdisc_state_marshal.py:qrdisc_marshal_plane
    consumer: engine/cpp/qr_entry_v2/src/qrdisc_pymodule.cpp:qrdisc_build_plane

    The assertions read the state BACK through the native side's raw pointer
    (`plane_buffer`) and compare it against the live plane's own attributes,
    reconstructed here by hand.  Comparing against the marshaller's own output
    would be a mirror assertion: it would pass whether or not the bytes ever
    reached C.

    Every expected NAME below is hand-written rather than derived from the
    constant the marshaller reads, for the same reason.

This is a real-data test (it opens one dense-store session), so it is slow by
design; the store IS the acceptance corpus for this port (D-017).
"""

from __future__ import annotations

import shutil
import sys
import unittest
from dataclasses import fields
from unittest import mock

import numpy as np

from engine.entry_v2.disc_native_builders import (
    capture_disc_session, discover_store_sessions, read_stored_shard,
    select_store_sessions)
from engine.entry_v2.discretionary_features import (
    CausalDiscretionaryPlane, DiscretionaryFeatureRefusal, _ProfileState)
from engine.entry_v2 import qrdisc_native_loader as loader
from engine.entry_v2.qrdisc_native_loader import (
    QRDISC_WAVE1_FAMILIES, load_qrdisc_native, qrdisc_assembly_delegates)
from engine.entry_v2.qrdisc_state_marshal import (
    QRDISC_LEDGER_FIELDS, QRDISC_PROFILE_FLOAT_FIELDS,
    QRDISC_PROFILE_INT_FIELDS, qrdisc_marshal_plane, qrdisc_warm_plane_caches)

# Hand-transcribed from the dataclass declarations at
# discretionary_features.py:323-348 and :290-320.  NOT imported from the same
# tuple the marshaller uses.
EXPECTED_LEDGER_FIELDS = (
    "seconds", "cumulative", "buy_burst_cumulative", "sell_burst_cumulative",
    "buy_seconds", "sell_seconds", "buy_second_volume", "sell_second_volume",
    "buy_ts_ns", "sell_ts_ns", "buy_event_size", "sell_event_size",
    "bid_reload_ts_ns", "ask_reload_ts_ns", "bid_reload_latency_ns",
    "ask_reload_latency_ns", "bid_reload_size", "ask_reload_size",
    "bid_pull_ts_ns", "ask_pull_ts_ns", "bid_pull_lifetime_ns",
    "ask_pull_lifetime_ns", "bid_pull_size", "ask_pull_size")
EXPECTED_PROFILE_INT_FIELDS = (
    "boundary_sec", "total_volume", "low_tick", "high_tick", "poc_tick",
    "val_tick", "vah_tick", "nearest_hvn_tick", "nearest_lvn_tick",
    "low_single_tail_ticks", "high_single_tail_ticks", "mode_count")
EXPECTED_PROFILE_FLOAT_FIELDS = (
    "vwap_tick", "entropy", "poc_fraction", "skewness", "excess_kurtosis",
    "lower_tail_fraction", "upper_tail_fraction", "low_edge_fraction",
    "high_edge_fraction", "low_excess_score", "high_excess_score",
    "low_poor_score", "high_poor_score", "single_print_fraction",
    "delta_fraction", "absolute_delta_fraction", "poc_delta_fraction")


def _one_session_plane():
    sessions = select_store_sessions(discover_store_sessions(), "1-per-asset")
    session = next(one for one in sessions if one.prior_present)
    capture = capture_disc_session(session, query_limit=5)
    return session, capture, CausalDiscretionaryPlane(**capture.construction)


def _phase_crossing_capture():
    """The cheapest store session whose emitted rows cross into a second phase.

    A phase-scoped profile start only exists once a candidate's
    `phase_open_utc` lands after the session open (feature_map:2400 derives the
    cache key from it, and `_profile_at`:845 clamps it at 0), so a capture that
    stops inside phase 0 can never show a warmed cache doing anything.  The
    required row count is read from each stored shard's own `phase` identity
    column rather than hard-coded, and the cheapest session wins because every
    captured row is a real oracle evaluation.
    """

    cheapest: tuple[object, int] | None = None
    for session in select_store_sessions(discover_store_sessions(), "1-per-asset"):
        phases = np.asarray(read_stored_shard(session.artifact_path).identity["phase"])
        changed = np.flatnonzero(phases[1:] != phases[:-1])
        if not len(changed):
            continue
        rows = int(changed[0]) + 2
        if cheapest is None or rows < cheapest[1]:
            cheapest = (session, rows)
    if cheapest is None:
        raise unittest.SkipTest("no store session emits a second phase")
    session, rows = cheapest
    capture = capture_disc_session(session, query_limit=rows)
    # ROW FLOOR ON THE CAPTURE ITSELF (R6 F23, amended by orchestrator ruling
    # 2026-08-22).  Every differential in this file and in test_qrdisc_maps.py
    # reads its rows from here, so a cheaper session arriving in the store
    # later could quietly shrink the corpus every bit-identity claim rests on —
    # a two-row capture would still make the whole suite green.
    # NO SIDE FLOOR: measured 2026-08-22, only three store sessions cross a
    # phase and all three are single-sided (side=-1 throughout), so a both-
    # sides floor can never pass and would permanently skip this suite.  The
    # +1 branches (~20 `side > 0` ternaries) are exercised by the both-sided
    # FULL-SESSION store differentials (disc_native_differential_qrdisc_*),
    # value-level; the single-sidedness of THIS float64 fixture is a ledgered
    # gap in STATE.md (wave-3: a second, phase-free both-sided capture).
    if len(capture.queries) < 32:
        raise unittest.SkipTest(
            f"the phase-crossing capture ({session.label}) is too thin to gate "
            f"the port — row floor: {len(capture.queries)} rows captured, 32 "
            "required")
    return session, capture, CausalDiscretionaryPlane(**capture.construction)


class QrdiscCacheWarming(unittest.TestCase):
    """`qrdisc_warm_plane_caches` must fill what __init__ leaves lazy.

    After __init__ the plane holds exactly one profile/TPO start — 0, set at
    discretionary_features.py:637-638 — and an empty `_state_cache`; every
    other key is built at row time.  The native side addresses those caches by
    buffer, so anything still lazy at marshal time is invisible to it.  The
    expected key sets below are re-derived here from the captured queries, not
    read back from the warmer's receipt, or the assertion would pass for a
    warmer that walked nothing.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.session, cls.capture, cls.plane = _phase_crossing_capture()
        cls.receipt = qrdisc_warm_plane_caches(cls.plane, cls.capture.queries)
        cls.scalars, cls.buffers = qrdisc_marshal_plane(cls.plane)
        open_sec = cls.plane.open_ns // 1_000_000_000
        # Seeded with 0 because __init__ built it before any candidate was seen.
        cls.expected_starts: list[int] = [0]
        for query in cls.capture.queries:
            start = max(0, int(query["formation_candidate"]["phase_open_utc"])
                        - open_sec)
            if start not in cls.expected_starts:
                cls.expected_starts.append(start)
        cls.expected_state_keys = {
            (int(query["formation_candidate"]["decision_ts_ns"]),
             int(query["formation_candidate"]["entry_mid2"]),
             int(query["side"])) for query in cls.capture.queries}

    def test_marshal_carries_every_phase_scoped_profile_start(self) -> None:
        starts = self.buffers["profile__starts"]
        self.assertGreater(len(starts), 1,
                           "the profile cache still holds only the __init__ start")
        self.assertEqual([int(value) for value in starts], self.expected_starts)

    def test_marshal_carries_the_same_starts_for_the_tpo_cache(self) -> None:
        starts = self.buffers["tpo__starts"]
        self.assertGreater(len(starts), 1)
        self.assertEqual([int(value) for value in starts], self.expected_starts)

    def test_profile_series_are_marshalled_for_the_warmed_starts(self) -> None:
        offsets = self.buffers["profile__offsets"]
        self.assertEqual(len(offsets), len(self.expected_starts) + 1)
        for index, start in enumerate(self.expected_starts):
            length = int(offsets[index + 1]) - int(offsets[index])
            self.assertEqual(length, len(self.plane._profile_cache[start]))
            self.assertGreater(length, 0, f"start {start} carries no series")

    def test_state_cache_holds_one_entry_per_distinct_candidate_key(self) -> None:
        self.assertGreater(len(self.expected_state_keys), 1)
        self.assertEqual(self.scalars["state_cache_entries"],
                         len(self.expected_state_keys))
        self.assertEqual(set(self.plane._state_cache), self.expected_state_keys)

    def test_warming_receipt_reports_what_it_built(self) -> None:
        self.assertEqual(self.receipt["queries"], len(self.capture.queries))
        self.assertEqual(self.receipt["profile_starts"], len(self.expected_starts))
        self.assertEqual(self.receipt["tpo_starts"], len(self.expected_starts))
        self.assertEqual(self.receipt["state_cache_entries"],
                         len(self.expected_state_keys))

    def test_a_warmed_row_equals_a_fresh_unwarmed_oracle_row(self) -> None:
        """Warming must be a pure prefetch, not a semantic change.

        The fresh plane is a second construction from the same recorded inputs
        with nothing warmed; it fills its caches lazily exactly as the store's
        own run did.  Rows are sampled rather than exhaustive because each one
        is a full real oracle evaluation: the first, the middle, the last, and
        the row that crosses into the second phase.
        """

        fresh = CausalDiscretionaryPlane(**self.capture.construction)
        last = len(self.capture.queries) - 1
        for index in sorted({0, last // 2, last - 1, last}):
            query = self.capture.queries[index]
            warmed_row = self.plane.feature_map(**query)
            fresh_row = fresh.feature_map(**query)
            self.assertEqual(tuple(warmed_row), tuple(fresh_row),
                             f"name order differs at row {index}")
            self.assertEqual(
                np.asarray(tuple(warmed_row.values()), np.float64).tobytes(),
                np.asarray(tuple(fresh_row.values()), np.float64).tobytes(),
                f"warming changed the float64 values at row {index}")


class QrdiscMarshalFieldNames(unittest.TestCase):
    """The dataclass split the marshaller derives must be the real one."""

    def test_ledger_field_order_matches_hand_written_list(self) -> None:
        self.assertEqual(EXPECTED_LEDGER_FIELDS, QRDISC_LEDGER_FIELDS)

    def test_profile_scalars_split_by_annotation(self) -> None:
        self.assertEqual(EXPECTED_PROFILE_INT_FIELDS, QRDISC_PROFILE_INT_FIELDS)
        self.assertEqual(EXPECTED_PROFILE_FLOAT_FIELDS,
                         QRDISC_PROFILE_FLOAT_FIELDS)
        # Completeness against the ORACLE's dataclass, not against the
        # marshaller's own tuples: a field carried by neither matrix would
        # otherwise vanish silently.
        self.assertEqual(
            len(EXPECTED_PROFILE_INT_FIELDS) + len(EXPECTED_PROFILE_FLOAT_FIELDS),
            len(fields(_ProfileState)),
            "a _ProfileState field is carried by neither matrix")


class QrdiscStateRoundTrip(unittest.TestCase):
    """One real session, marshalled, read back through the native pointer."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.session, cls.capture, cls.plane = _one_session_plane()
        cls.module = load_qrdisc_native()
        scalars, buffers = qrdisc_marshal_plane(cls.plane)
        cls.scalars = scalars
        cls.buffer_count = len(buffers)
        cls.native = cls.module.build_plane(
            scalars=scalars, buffers=buffers,
            delegates={"feature_map": cls.plane.feature_map},
            refusal_type=DiscretionaryFeatureRefusal)

    def _native(self, name: str) -> np.ndarray:
        return self.module.plane_buffer(self.native, name)

    def test_every_marshalled_buffer_is_readable(self) -> None:
        names = self.module.plane_buffer_names(self.native)
        self.assertEqual(len(names), self.buffer_count)
        for name in names:
            self.assertGreaterEqual(self._native(name).size, 0, name)

    def test_ledger_arrays_are_bit_equal_to_the_plane(self) -> None:
        ticks = list(self.plane._ledger)
        np.testing.assert_array_equal(self._native("ledger__ticks"),
                                      np.asarray(ticks, np.int64))
        for field in EXPECTED_LEDGER_FIELDS:
            expected = np.concatenate(
                [np.asarray(getattr(self.plane._ledger[tick], field))
                 for tick in ticks], axis=0)
            observed = self._native(f"ledger__{field}__values")
            self.assertEqual(observed.shape, expected.shape, field)
            np.testing.assert_array_equal(
                observed.view(np.uint8), np.ascontiguousarray(expected).view(np.uint8),
                f"ledger field {field} differs after the round trip")

    def test_ledger_offsets_address_each_tick(self) -> None:
        ticks = list(self.plane._ledger)
        offsets = self._native("ledger__seconds__offsets")
        values = self._native("ledger__seconds__values")
        self.assertEqual(len(offsets), len(ticks) + 1)
        self.assertEqual(int(offsets[0]), 0)
        self.assertEqual(int(offsets[-1]), len(values))
        for index in (0, len(ticks) // 2, len(ticks) - 1):
            expected = np.asarray(self.plane._ledger[ticks[index]].seconds)
            np.testing.assert_array_equal(
                values[int(offsets[index]):int(offsets[index + 1])], expected)

    def test_profile_cache_scalars_are_bit_equal_to_the_plane(self) -> None:
        starts = list(self.plane._profile_cache)
        np.testing.assert_array_equal(self._native("profile__starts"),
                                      np.asarray(starts, np.int64))
        offsets = self._native("profile__offsets")
        present = self._native("profile__present")
        integers = self._native("profile__int_values")
        floats = self._native("profile__float_values")
        for index, start in enumerate(starts):
            series = self.plane._profile_cache[start]
            self.assertEqual(int(offsets[index + 1] - offsets[index]), len(series))
            for ordinal, state in enumerate(series):
                row = int(offsets[index]) + ordinal
                self.assertEqual(int(present[row]), 0 if state is None else 1)
                if state is None:
                    continue
                for column, field in enumerate(EXPECTED_PROFILE_INT_FIELDS):
                    self.assertEqual(int(integers[row, column]),
                                     int(getattr(state, field)), field)
                for column, field in enumerate(EXPECTED_PROFILE_FLOAT_FIELDS):
                    self.assertEqual(
                        np.float64(floats[row, column]).tobytes(),
                        np.float64(getattr(state, field)).tobytes(), field)

    def test_tpo_cache_is_carried_too(self) -> None:
        starts = list(self.plane._tpo_cache)
        np.testing.assert_array_equal(self._native("tpo__starts"),
                                      np.asarray(starts, np.int64))

    def test_prior_levels_are_bit_equal_to_the_plane(self) -> None:
        levels = self.plane.prior_session.levels
        ticks = list(levels)
        np.testing.assert_array_equal(self._native("prior_level__ticks"),
                                      np.asarray(ticks, np.int64))
        names = self.scalars["prior_level_names"]
        values = self._native("prior_level__values")
        self.assertEqual(values.shape, (len(ticks), len(names)))
        for row, tick in enumerate(ticks):
            for column, name in enumerate(names):
                self.assertEqual(np.float64(values[row, column]).tobytes(),
                                 np.float64(levels[tick][name]).tobytes(),
                                 f"tick {tick} metric {name}")

    def test_flat_attribute_buffers_alias_the_plane_memory(self) -> None:
        """Zero-copy is a claim; this writes through the C pointer to prove it.

        Only the flat `attr__` buffers can alias — the ragged ledger fields are
        concatenated, which necessarily copies.  The mutation is undone before
        the assertion returns, and the plane is a local object either way.
        """

        observed = self._native("attr__mid2")
        original = int(self.plane.mid2[0])
        observed[0] = original + 1
        try:
            self.assertEqual(int(self.plane.mid2[0]), original + 1,
                             "attr__mid2 was copied, not borrowed")
        finally:
            observed[0] = original
        self.assertEqual(int(self.plane.mid2[0]), original)

    def test_round_trip_comparison_catches_a_single_changed_byte(self) -> None:
        """Mutation check on the assertion itself (checking-data-contracts 6)."""

        observed = np.array(self._native("ledger__seconds__values"), copy=True)
        self.assertGreater(len(observed), 0)
        mutated = observed.copy()
        mutated[0] = mutated[0] + 1
        with self.assertRaises(AssertionError):
            np.testing.assert_array_equal(observed, mutated)


class QrdiscRowBoundary(unittest.TestCase):
    """The (values, names) pair the differential's builder is assembled from."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.session, cls.capture, cls.plane = _one_session_plane()
        cls.module = load_qrdisc_native()
        scalars, buffers = qrdisc_marshal_plane(cls.plane)
        cls.native = cls.module.build_plane(
            scalars=scalars, buffers=buffers,
            delegates={"feature_map": cls.plane.feature_map},
            refusal_type=DiscretionaryFeatureRefusal)

    def test_row_matches_the_oracle_bit_for_bit(self) -> None:
        for index, query in enumerate(self.capture.queries):
            values, names = self.module.feature_map_row(self.native, **query)
            oracle = self.plane.feature_map(**query)
            self.assertEqual(names, tuple(oracle),
                             f"name order differs at row {index}")
            self.assertEqual(
                np.asarray(values, np.float64).tobytes(),
                np.asarray(tuple(oracle.values()), np.float64).tobytes(),
                f"float64 values differ at row {index}")

    def test_snapshot_outside_session_refuses_like_the_oracle(self) -> None:
        query = dict(self.capture.queries[0])
        query["snapshot_ts_ns"] = int(query["snapshot_ts_ns"]) - 10 ** 15
        with self.assertRaises(DiscretionaryFeatureRefusal) as native:
            self.module.feature_map_row(self.native, **query)
        self.assertEqual(str(native.exception), "snapshot is outside session")

    def test_malformed_formation_refuses_like_the_oracle(self) -> None:
        query = dict(self.capture.queries[0])
        query["formation_candidate"] = dict(query["formation_candidate"])
        query["formation_candidate"]["entry_bid_px"] = "0"
        with self.assertRaises(DiscretionaryFeatureRefusal) as native:
            self.module.feature_map_row(self.native, **query)
        self.assertEqual(str(native.exception), "formation state is malformed")

    def test_missing_formation_key_raises_key_error(self) -> None:
        query = dict(self.capture.queries[0])
        query["formation_candidate"] = {
            key: value for key, value in query["formation_candidate"].items()
            if key != "entry_mid2"}
        with self.assertRaises(KeyError):
            self.module.feature_map_row(self.native, **query)


class QrdiscPriorAbsentSession(unittest.TestCase):
    """The prior-absent branch, which NO store session can reach.

    All 145 sessions in the dense store are prior-present (checked 2026-08-21),
    so `select_store_sessions`'s prior-absent-first quota
    (disc_native_builders.py:101-125) is vacuous today and the differential
    cannot exercise `PriorSessionContext.empty_feature_map`
    (discretionary_features.py:177).  The branch is reached here instead by
    rebuilding the same session with its prior dropped: the values no longer
    match the STORE, but native-vs-oracle is still the contract under test.

    THE ROW GOES THROUGH THE NATIVE ASSEMBLY (R6 F8).  A whole-map delegate
    would hand the prior-absent branch back to the oracle, so the test would
    prove nothing about the port: it is `qrdisc_assemble_families` that picks
    `_prior_session_empty_feature_map` over the prior-present call site
    (discretionary_features.py:2417-2423), and until now no test executed that
    choice.  `assembly_available` is asserted for the same reason the loader
    asserts it — the fallback is silent and still emits correct bytes.
    """

    def test_marshal_and_row_survive_a_missing_prior(self) -> None:
        _, capture, _ = _one_session_plane()
        construction = dict(capture.construction)
        construction["prior_session"] = None
        plane = CausalDiscretionaryPlane(**construction)
        qrdisc_warm_plane_caches(plane, capture.queries)
        module = load_qrdisc_native()
        scalars, buffers = qrdisc_marshal_plane(plane)
        self.assertFalse(scalars["prior_present"])
        self.assertEqual(scalars["prior_level_names"], ())
        self.assertNotIn("prior_level__ticks", buffers)
        delegates: dict[str, object] = {"feature_map": plane.feature_map}
        delegates.update(qrdisc_assembly_delegates(plane))
        delegates.update({family: None for family in QRDISC_WAVE1_FAMILIES})
        native = module.build_plane(
            scalars=scalars, buffers=buffers, delegates=delegates,
            refusal_type=DiscretionaryFeatureRefusal)
        self.assertTrue(module.assembly_available(native))
        query = capture.queries[0]
        values, names = module.feature_map_row(native, **query)
        oracle = plane.feature_map(**query)
        self.assertEqual(names, tuple(oracle))
        self.assertEqual(np.asarray(values, np.float64).tobytes(),
                         np.asarray(tuple(oracle.values()), np.float64).tobytes())
        self.assertEqual(oracle["disc_prior_present"], 0.0)


class QrdiscStaleBinaryRefusal(unittest.TestCase):
    """The loader must refuse a .so that is not the sources on disk.

    The fixture builds a manifest the current binary was NOT built from (the
    source list is reordered, which changes the manifest sha without changing a
    byte of C++), drops the real binary at that manifest's address, and asserts
    the load refuses.  The false-positive guard is the honest load right after:
    the check must accept the binary at its own address.
    """

    def test_binary_from_another_manifest_is_refused(self) -> None:
        library, real_sha = loader.qrdisc_build_extension()
        reordered = tuple(reversed(loader.QRDISC_CPP_SOURCES))
        with mock.patch.object(loader, "QRDISC_CPP_SOURCES", reordered):
            fake_sha, _ = loader.qrdisc_source_manifest()
            self.assertNotEqual(fake_sha, real_sha)
            fake_dir = loader.QRDISC_BUILD_ROOT / fake_sha[:16]
            fake_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(library, fake_dir / f"{loader.QRDISC_MODULE_NAME}.so")
            sys.modules.pop(loader.QRDISC_MODULE_NAME, None)
            with self.assertRaises(loader.QrdiscNativeRefusal) as refusal:
                loader.load_qrdisc_native()
        self.assertIn("STALE", str(refusal.exception))
        self.assertIn(real_sha, str(refusal.exception))

    def test_the_honest_binary_still_loads(self) -> None:
        _, real_sha = loader.qrdisc_build_extension()
        self.assertEqual(loader.load_qrdisc_native().source_manifest_sha256(),
                         real_sha)


if __name__ == "__main__":
    unittest.main()
