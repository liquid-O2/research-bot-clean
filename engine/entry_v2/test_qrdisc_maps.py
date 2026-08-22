"""Per-family differential for the natively-ported feature-map families.

SEAM UNDER TEST
    producer: engine/cpp/qr_entry_v2/src/qrdisc_maps_*.cpp, reached through
              `qr_disc_native.family_map`
    oracle:   the bound method of the same name on CausalDiscretionaryPlane
              (discretionary_features.py:2029, :2226, :2272)

    This is a FINER gate than the store differential: the store compares
    float32 bytes of the whole row, so a family whose float64 result differs in
    the last bit can still pass there and then fail the day a later wave
    assembles the row natively.  Here the comparison is float64, per family,
    per row, including the emitted NAME ORDER — which the store cannot see
    while the oracle is still assembling the row.

    The family arguments below are hand-transcribed from feature_map's own call
    sites (discretionary_features.py:2424-2442), not read back from the port.

Real-data test: it opens one dense-store session and evaluates every captured
row through both paths.  Slow by design (D-017: the store is the corpus).
"""

from __future__ import annotations

import math
import unittest

import numpy as np

from engine.entry_v2.discretionary_features import DiscretionaryFeatureRefusal
from engine.entry_v2.qrdisc_native_loader import (
    QRDISC_TAIL_FAMILIES, load_qrdisc_native,
    qrdisc_assembly_delegates)
from engine.entry_v2.qrdisc_state_marshal import (
    qrdisc_marshal_plane, qrdisc_warm_plane_caches)
from engine.entry_v2.test_qrdisc_state_marshal import _phase_crossing_capture

QRDISC_NATIVE_FAMILIES = ("_forward_vol_map", "_regime_map", "_target_map",
                          "_event_micro_map")
# Wave 2 lane A.  Hand-transcribed from discretionary_features.py:2487; the
# family is all SEVEN calls merged in the loop's order, for the same reason
# lane B's clock families are all their target counts.
QRDISC_EVENT_HORIZONS = (1, 5, 15, 30, 60, 120, 300)
# Wave 2 lane B.  A "family" is EVERY call site of that method in feature_map,
# merged in feature_map's own order (discretionary_features.py:2458-2475): the
# delegation table is keyed by method name, so a family that emitted only one
# of its four target counts would leave the rest on the delegate's values.
# Named for the four methods it holds, NOT `QRDISC_WAVE2B_FAMILIES`: the
# loader's constant of that name carries SEVEN entries (R6 F2), and a module
# -local four-entry namesake is a shadow-confusion the reviewer flagged.
QRDISC_CLOCK_PRIOR_FAMILIES = ("_prior_reaction_map", "_event_clock_map",
                               "_trade_clock_map", "_volume_clock_map")
# Hand-transcribed from discretionary_features.py:2461, :2466, :2471.
QRDISC_CLOCK_TARGETS = {"_event_clock_map": (16, 64, 256, 1024),
                        "_trade_clock_map": (8, 32, 128, 512),
                        "_volume_clock_map": (64, 256, 1024)}


def _oracle_clock_family(plane, family: str, query: dict) -> dict[str, float]:
    """The wave-2b families, called exactly as feature_map:2457-2475 calls them."""

    candidate = query["formation_candidate"]
    formation_ts_ns = int(candidate["decision_ts_ns"])
    side = query["side"]
    if family == "_prior_reaction_map":
        formation_tick = ((int(candidate["entry_bid_px"]) if side > 0
                           else int(candidate["entry_ask_px"])) // plane.raw_tick)
        return plane._prior_reaction_map(
            formation_tick=formation_tick, formation_ts_ns=formation_ts_ns,
            side=side)
    method = getattr(plane, family)
    keyword = ("target_volume" if family == "_volume_clock_map"
               else "target_count")
    values: dict[str, float] = {}
    for target in QRDISC_CLOCK_TARGETS[family]:
        values.update(method(**{keyword: target},
                             snapshot_ts_ns=int(query["snapshot_ts_ns"]),
                             formation_ts_ns=formation_ts_ns, side=side))
    return values


def _oracle_family(plane, family: str, query: dict) -> dict[str, float]:
    """Call one oracle family with feature_map's own arguments for this row."""

    candidate = query["formation_candidate"]
    snapshot_sec = int((int(query["snapshot_ts_ns"]) - plane.open_ns) // 1_000_000_000)
    phase_open_sec = (int(candidate["phase_open_utc"])
                      - plane.open_ns // 1_000_000_000)
    if family in QRDISC_CLOCK_PRIOR_FAMILIES:
        return _oracle_clock_family(plane, family, query)
    if family == "_event_micro_map":
        side = query["side"]
        # feature_map:2432-2433 and :2490-2494, hand-transcribed.
        formation_tick = ((int(candidate["entry_bid_px"]) if side > 0
                           else int(candidate["entry_ask_px"])) // plane.raw_tick)
        formation_ts_ns = int(candidate["decision_ts_ns"])
        snapshot_ts_ns = int(query["snapshot_ts_ns"])
        micro: dict[str, float] = {}
        for horizon in QRDISC_EVENT_HORIZONS:
            micro.update(plane._event_micro_map(
                prefix=f"disc_evt_h{horizon}_", center_tick=formation_tick,
                radius=2,
                left_ns=max(formation_ts_ns,
                            snapshot_ts_ns - horizon * 1_000_000_000),
                right_ns=snapshot_ts_ns, side=side))
        return micro
    if family == "_regime_map":
        return plane._regime_map(
            snapshot_sec=snapshot_sec, current_mid2=query["current_mid2"],
            side=query["side"])
    if family == "_forward_vol_map":
        return plane._forward_vol_map(
            formation_candidate=candidate,
            formation_sec=int(candidate["decision_sec"]),
            phase_open_sec=phase_open_sec, snapshot_sec=snapshot_sec,
            current_mid2=query["current_mid2"],
            formation_mid2=int(candidate["entry_mid2"]), side=query["side"])
    try:
        atr_usd = float(candidate.get("atr14_prev_usd", 0.0))
    except (TypeError, ValueError):
        atr_usd = 0.0
    return plane._target_map(
        snapshot_sec=snapshot_sec, current_mid2=query["current_mid2"],
        side=query["side"], phase_open_sec=phase_open_sec, atr_usd=atr_usd)


class QrdiscFamilyDifferential(unittest.TestCase):

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

    def _compare_family(self, family: str) -> None:
        for index, query in enumerate(self.capture.queries):
            values, names = self.module.family_map(
                self.native, family=family, **query)
            oracle = _oracle_family(self.plane, family, query)
            self.assertEqual(names, tuple(oracle),
                             f"{family} name order differs at row {index}")
            self.assertEqual(
                np.asarray(values, np.float64).tobytes(),
                np.asarray(tuple(oracle.values()), np.float64).tobytes(),
                f"{family} float64 values differ at row {index}")

    def test_forward_vol_map_is_bit_identical_on_every_row(self) -> None:
        self._compare_family("_forward_vol_map")

    def test_regime_map_is_bit_identical_on_every_row(self) -> None:
        self._compare_family("_regime_map")

    def test_target_map_is_bit_identical_on_every_row(self) -> None:
        self._compare_family("_target_map")

    def test_event_clock_map_is_bit_identical_on_every_row(self) -> None:
        self._compare_family("_event_clock_map")

    def test_trade_clock_map_is_bit_identical_on_every_row(self) -> None:
        self._compare_family("_trade_clock_map")

    def test_volume_clock_map_is_bit_identical_on_every_row(self) -> None:
        self._compare_family("_volume_clock_map")

    def test_prior_reaction_map_is_bit_identical_on_every_row(self) -> None:
        self._compare_family("_prior_reaction_map")

    def test_event_micro_map_is_bit_identical_on_every_row(self) -> None:
        self._compare_family("_event_micro_map")

    def test_the_comparison_can_fail(self) -> None:
        """False-positive guard: the assertion must discriminate rows.

        Every family above returns row-dependent numbers, so comparing one
        row's native output against ANOTHER row's oracle output has to fail.
        Without this, a family that returned a constant vector of the right
        length would pass the three tests above on any session where the oracle
        happened to be constant too.
        """

        first = self.capture.queries[0]
        other = next(query for query in self.capture.queries
                     if int(query["snapshot_ts_ns"]) != int(first["snapshot_ts_ns"]))
        for family in QRDISC_NATIVE_FAMILIES:
            values, _names = self.module.family_map(
                self.native, family=family, **first)
            oracle = _oracle_family(self.plane, family, other)
            self.assertNotEqual(
                np.asarray(values, np.float64).tobytes(),
                np.asarray(tuple(oracle.values()), np.float64).tobytes(),
                f"{family} returned the same bytes for two different rows")

    def test_the_wave2b_comparison_can_fail(self) -> None:
        """False-positive guard for lane B's four families.

        The shared guard above discriminates rows by SNAPSHOT, which
        `_prior_reaction_map` does not read: it answers from the formation
        candidate alone, so two snapshots of one candidate are identical by
        design and a snapshot-keyed guard would be vacuous for it.  This one
        asks the oracle itself for a row whose values differ, which also asserts
        the weaker fact the guard depends on — that the family is not constant
        across this session.
        """

        first = self.capture.queries[0]
        for family in QRDISC_CLOCK_PRIOR_FAMILIES:
            values, _names = self.module.family_map(
                self.native, family=family, **first)
            native_bytes = np.asarray(values, np.float64).tobytes()
            baseline = np.asarray(
                tuple(_oracle_family(self.plane, family, first).values()),
                np.float64).tobytes()
            different = None
            for query in self.capture.queries[1:]:
                oracle = np.asarray(
                    tuple(_oracle_family(self.plane, family, query).values()),
                    np.float64).tobytes()
                if oracle != baseline:
                    different = oracle
                    break
            self.assertIsNotNone(
                different,
                f"{family} is constant across the whole session, so the "
                "bit-identity test above cannot discriminate anything")
            self.assertNotEqual(
                native_bytes, different,
                f"{family} returned the same bytes for two rows the oracle "
                "answers differently")

    def test_an_unknown_family_is_refused(self) -> None:
        with self.assertRaises(KeyError) as refusal:
            self.module.family_map(self.native, family="_profile_map",
                                   **self.capture.queries[0])
        self.assertIn("_profile_map", str(refusal.exception))


class QrdiscTradeSliceKernel(unittest.TestCase):
    """`_trade_slice_map` at its own seam: it is a kernel, not a family.

    feature_map never calls it — `_trade_clock_map` and `_volume_clock_map` do
    (discretionary_features.py:1677, :1694), and they own the window arguments.
    So the comparison is against the oracle's bound method with the SAME window
    the clocks compute, hand-transcribed from :1675-1698, on every captured row
    and for every target the two clocks use.
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

    def _windows(self, query: dict) -> list[tuple[str, int, int, float]]:
        """Every (prefix, left, right, support_fraction) one row asks for."""

        plane = self.plane
        snapshot_ts_ns = int(query["snapshot_ts_ns"])
        right = int(np.searchsorted(plane._trade_ts, snapshot_ts_ns, side="left"))
        windows = []
        for target_count in (8, 32, 128, 512):
            left = max(0, right - target_count)
            windows.append((f"disc_tclock_n{target_count}_", left, right,
                            (right - left) / float(target_count)))
        for target_volume in (64, 256, 1024):
            available = int(plane._trade_volume_prefix[right])
            threshold = max(0, available - target_volume)
            left = max(0, int(np.searchsorted(
                plane._trade_volume_prefix, threshold, side="right")) - 1)
            selected = int(plane._trade_volume_prefix[right]
                           - plane._trade_volume_prefix[left])
            windows.append((f"disc_vclock_v{target_volume}_", left, right,
                            min(1.0, selected / float(target_volume))))
        return windows

    def test_trade_slice_map_is_bit_identical_on_every_row(self) -> None:
        for index, query in enumerate(self.capture.queries):
            formation_ts_ns = int(query["formation_candidate"]["decision_ts_ns"])
            for prefix, left, right, support in self._windows(query):
                values, names = self.module.trade_slice_map(
                    self.native, prefix=prefix, left=left, right=right,
                    support_fraction=support,
                    snapshot_ts_ns=int(query["snapshot_ts_ns"]),
                    formation_ts_ns=formation_ts_ns, side=int(query["side"]))
                oracle = self.plane._trade_slice_map(
                    prefix=prefix, left=left, right=right,
                    support_fraction=support,
                    snapshot_ts_ns=int(query["snapshot_ts_ns"]),
                    formation_ts_ns=formation_ts_ns, side=int(query["side"]))
                self.assertEqual(names, tuple(oracle),
                                 f"{prefix} name order differs at row {index}")
                self.assertEqual(
                    np.asarray(values, np.float64).tobytes(),
                    np.asarray(tuple(oracle.values()), np.float64).tobytes(),
                    f"{prefix} float64 values differ at row {index}")

    def test_the_comparison_can_fail(self) -> None:
        """False-positive guard: two different windows must not agree."""

        query = self.capture.queries[-1]
        formation_ts_ns = int(query["formation_candidate"]["decision_ts_ns"])
        windows = self._windows(query)
        narrow = windows[0]
        wide = windows[3]
        values, _names = self.module.trade_slice_map(
            self.native, prefix=narrow[0], left=narrow[1], right=narrow[2],
            support_fraction=narrow[3],
            snapshot_ts_ns=int(query["snapshot_ts_ns"]),
            formation_ts_ns=formation_ts_ns, side=int(query["side"]))
        oracle = self.plane._trade_slice_map(
            prefix=narrow[0], left=wide[1], right=wide[2],
            support_fraction=wide[3],
            snapshot_ts_ns=int(query["snapshot_ts_ns"]),
            formation_ts_ns=formation_ts_ns, side=int(query["side"]))
        self.assertNotEqual(
            np.asarray(values, np.float64).tobytes(),
            np.asarray(tuple(oracle.values()), np.float64).tobytes(),
            "the 8-trade and 512-trade windows produced the same bytes")


class QrdiscNativeDelegationTable(unittest.TestCase):
    """`None` in the delegation table means the port owns that family."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.session, cls.capture, cls.plane = _phase_crossing_capture()
        qrdisc_warm_plane_caches(cls.plane, cls.capture.queries)
        cls.module = load_qrdisc_native()
        cls.scalars, cls.buffers = qrdisc_marshal_plane(cls.plane)

    def _plane_with(self, native: tuple[str, ...]):
        delegates = {"feature_map": self.plane.feature_map}
        delegates.update({family: None for family in native})
        return self.module.build_plane(
            scalars=self.scalars, buffers=self.buffers, delegates=delegates,
            refusal_type=DiscretionaryFeatureRefusal)

    def test_every_family_switched_native_keeps_the_row_identical(self) -> None:
        native = self._plane_with(QRDISC_NATIVE_FAMILIES)
        for index in (0, len(self.capture.queries) // 2,
                      len(self.capture.queries) - 1):
            query = self.capture.queries[index]
            values, names = self.module.feature_map_row(native, **query)
            oracle = self.plane.feature_map(**query)
            self.assertEqual(names, tuple(oracle), f"row {index}")
            self.assertEqual(
                np.asarray(values, np.float64).tobytes(),
                np.asarray(tuple(oracle.values()), np.float64).tobytes(),
                f"spliced row {index} differs from the oracle")

    def test_a_delegate_that_is_neither_callable_nor_none_is_refused(self) -> None:
        with self.assertRaises(TypeError) as refusal:
            self.module.build_plane(
                scalars=self.scalars, buffers=self.buffers,
                delegates={"feature_map": self.plane.feature_map,
                           "_regime_map": 7},
                refusal_type=DiscretionaryFeatureRefusal)
        self.assertIn("neither callable nor None", str(refusal.exception))


def _hand_derived_tail(plane, query, oracle: dict[str, float]) -> dict[str, float]:
    """feature_map's TAIL re-derived by hand from the oracle's FAMILY values.

    Transcribed from discretionary_features.py:2502-2694 by reading the source,
    and evaluated with the oracle's own family outputs as inputs.  It touches no
    tail name, so it is an independent derivation rather than the port's output
    read back at itself: seven expressions spanning the shapes the tail has —
    a ratio (:2507), the log1p site (:2660), a four-term sum whose ASSOCIATION
    order is contract (:2664), a divide-and-subtract (:2640), the state-series
    age (:2531 through the searchsorted index at :2527), Python's `and`-chain
    semantics (:2571), and a min-clamped product (:2684).
    """

    snapshot_ts_ns = int(query["snapshot_ts_ns"])
    candidate = query["formation_candidate"]
    formation_ts_ns = int(candidate["decision_ts_ns"])
    formation_mid2 = int(candidate["entry_mid2"])
    state = plane._state_series(formation_ts_ns, formation_mid2, query["side"])
    index = int(np.searchsorted(state["ts_ns"], snapshot_ts_ns, side="left") - 1)
    index = min(max(0, index), len(state["displacement"]) - 1)
    first_ts_ns = np.asarray(state["first_ts_ns"], np.int64)
    adverse_first = int(first_ts_ns[0])

    attack = oracle["disc_level_z2_attack_volume"]
    lift = oracle["disc_level_z2_lift_volume"]
    attack_plus_lift = attack + lift
    conflict_fraction = (2.0 * min(attack, lift) / attack_plus_lift
                         if attack_plus_lift else 0.0)
    return {
        "disc_mhi_attack_rate_1_over_30": float(
            (oracle["disc_evt_h1_attack_event_rate"] + 1.0)
            / (oracle["disc_evt_h30_attack_event_rate"] + 1.0)),
        "disc_behavior_conflict_intensity": float(
            conflict_fraction * math.log1p(attack_plus_lift)),
        "disc_behavior_control_evidence_balance": float(
            oracle["disc_tclock_n32_aligned_flow_fraction"]
            + oracle["disc_eclock_n64_defense_commitment"]
            + oracle["disc_eclock_n64_opposing_withdrawal"]
            - oracle["disc_test_pull_over_reload_size"]),
        "disc_path_poc_migration_acceleration_usd": float(
            oracle["disc_auction_phase_poc_migration_5m_aligned_usd"]
            - (oracle["disc_auction_phase_poc_migration_15m_aligned_usd"] / 3.0)),
        "disc_state_adverse_age_sec": float(
            (snapshot_ts_ns - adverse_first) / 1e9
            if 0 <= adverse_first < snapshot_ts_ns else 0.0),
        "disc_path_failed_auction_reentry": float(
            state["adverse_seen"][index] and state["reclaim_seen"][index]),
        "disc_mhi_flow_x_phase_headroom_fraction": float(
            oracle["disc_tclock_n32_aligned_flow_fraction"]
            * (1.0 - min(1.0, oracle["disc_fvol_phase_q50_coverage"]))),
    }


class QrdiscNativeRowAssembly(unittest.TestCase):
    """The port assembles the row: fan-out, merge order, and the native tail.

    SEAM UNDER TEST
        producer: `qr_disc_native.feature_map_row` on a plane whose delegation
                  table answers every family individually, so
                  `qrdisc_assembly.cpp` owns the row and the whole-map delegate
                  is off the path.
        oracle:   `CausalDiscretionaryPlane.feature_map` itself.

        The store differential compares float32; this compares float64 and the
        emitted NAME ORDER, which is what the assembly newly owns.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.session, cls.capture, cls.plane = _phase_crossing_capture()
        qrdisc_warm_plane_caches(cls.plane, cls.capture.queries)
        cls.module = load_qrdisc_native()
        scalars, buffers = qrdisc_marshal_plane(cls.plane)
        delegates: dict[str, object] = {"feature_map": cls.plane.feature_map}
        delegates.update(qrdisc_assembly_delegates(cls.plane))
        # QRDISC_TAIL_FAMILIES, not QRDISC_NATIVE_FAMILIES: this lane's
        # builder holds the family set at wave 1's so the only thing under
        # test is the ASSEMBLY.  A family another lane is still landing
        # would otherwise fail here for a reason that is not this seam.
        delegates.update({family: None for family in QRDISC_TAIL_FAMILIES})
        cls.native = cls.module.build_plane(
            scalars=scalars, buffers=buffers, delegates=delegates,
            refusal_type=DiscretionaryFeatureRefusal)
        cls.rows = [0, len(cls.capture.queries) // 2,
                    len(cls.capture.queries) - 1]

    def _native_row(self, query) -> dict[str, float]:
        values, names = self.module.feature_map_row(self.native, **query)
        return dict(zip(names, (float(value) for value in values)))

    def test_the_row_path_takes_the_assembly(self) -> None:
        """Without this the tests below could all pass on the OLD path."""

        self.assertTrue(self.module.assembly_available(self.native))

    def test_the_assembled_row_is_bit_identical_to_the_oracle(self) -> None:
        for index, query in enumerate(self.capture.queries):
            values, names = self.module.feature_map_row(self.native, **query)
            oracle = self.plane.feature_map(**query)
            self.assertEqual(names, tuple(oracle),
                             f"assembled name order differs at row {index}")
            self.assertEqual(
                np.asarray(values, np.float64).tobytes(),
                np.asarray(tuple(oracle.values()), np.float64).tobytes(),
                f"assembled row {index} differs from the oracle")

    def test_the_tail_matches_a_hand_derivation(self) -> None:
        for index in self.rows:
            query = self.capture.queries[index]
            oracle = dict(self.plane.feature_map(**query))
            expected = _hand_derived_tail(self.plane, query, oracle)
            observed = self._native_row(query)
            for name, value in expected.items():
                self.assertIn(name, observed,
                              f"the assembled row is missing tail feature {name}")
                self.assertEqual(
                    np.float64(observed[name]).tobytes(),
                    np.float64(value).tobytes(),
                    f"tail feature {name} differs at row {index}: native "
                    f"{observed[name]!r} vs hand-derived {value!r}")

    def test_the_tail_fixture_can_fail(self) -> None:
        """False-positive guard: the fixture must discriminate rows.

        Every derived name above is row-dependent on this session, so checking
        one row's native output against ANOTHER row's hand derivation has to
        fail on at least one of them.  Without this, a tail that emitted a
        constant would pass the fixture test.
        """

        first = self.capture.queries[0]
        other = next(query for query in self.capture.queries
                     if int(query["snapshot_ts_ns"]) != int(first["snapshot_ts_ns"]))
        expected = _hand_derived_tail(
            self.plane, other, dict(self.plane.feature_map(**other)))
        observed = self._native_row(first)
        self.assertNotEqual(
            [observed[name] for name in expected],
            list(expected.values()),
            "the tail fixture returned the same values for two different rows")


if __name__ == "__main__":
    unittest.main()
