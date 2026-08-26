#!/usr/bin/env python3
"""Causal discretionary-state features for the Entry V2 tabular learner.

The discretionary documents describe a hierarchy rather than a single entry
pattern: auction location and level memory establish the thesis, price-local
effort/reward establishes control, and an ordered defense/reclaim/retest state
times the expression.  This module measures those objects from the lossless
MBP-1 prefix.  It deliberately does not consume a teacher, an outcome, or an
event at/after the decision boundary.

The profile is frozen at completed five-minute boundaries.  Price ledgers are
queried by exclusive receive-second cutoffs.  ``LEVEL_ASSOCIATION_DESTROYED``
is a registered negative control: a causal, fixed bijection scrambles event
price coordinates while preserving every event and metric marginal.
"""

from __future__ import annotations

import math
from types import MappingProxyType
from typing import Mapping

import numpy as np


DISCRETIONARY_FEATURE_SCHEMA = "QRE2DISCRETIONARY8"
PROFILE_INTERVAL_SEC = 300
VALUE_AREA_FRACTION = 0.70
PROFILE_KERNEL = np.asarray((1.0, 2.0, 3.0, 2.0, 1.0), np.float64) / 9.0
LEVEL_ASSOCIATION_MODES = frozenset((
    "REAL", "LEVEL_ASSOCIATION_DESTROYED", "FILL_COUPLING_DESTROYED",
))
PRIOR_SESSION_SCHEMA = "QRE2DISCPRIOR2"
_DESTROY_BLOCK_TICKS = 64
_DESTROY_MULTIPLIER = 13
_DESTROY_INVERSE = 5  # 13 * 5 == 1 (mod 64)


def _destroy_shift(asset: str) -> int:
    return {"SI": 7, "HG": 11, "NKD": 17}.get(str(asset), 23)


def _destroy_tick(tick: int, asset: str) -> int:
    """Fixed no-fixed-point permutation inside causal 64-tick bands."""

    block, offset = divmod(int(tick), _DESTROY_BLOCK_TICKS)
    mapped = (_DESTROY_MULTIPLIER * offset + _destroy_shift(asset)) \
        % _DESTROY_BLOCK_TICKS
    return block * _DESTROY_BLOCK_TICKS + mapped


def _destroy_tick_inverse(tick: int, asset: str) -> int:
    block, offset = divmod(int(tick), _DESTROY_BLOCK_TICKS)
    original = (_DESTROY_INVERSE * (offset - _destroy_shift(asset))) \
        % _DESTROY_BLOCK_TICKS
    return block * _DESTROY_BLOCK_TICKS + original


class DiscretionaryFeatureRefusal(RuntimeError):
    """A raw-state or causal-boundary contract was violated."""


def _simple_sha(value: object) -> str:
    import hashlib
    import json
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"),
        allow_nan=False).encode()).hexdigest()


from .discretionary_prior import PriorSessionContext
from .discretionary_profile import (
    _ProfileState, _build_profile_series, _build_tpo_series,
    _initial_balance_map, _profile_at, _profile_map, _tpo_at)
from .discretionary_profile_ledger import (
    _LEDGER_METRICS, _TickLedger, _build_ledger, _ledger_sum,
    _level_values, _price_shape_values)
from .discretionary_quotes import _best_quote_response_map
from .discretionary_tape import (
    _event_clock_map, _path_behavior_map, _tape_slope_map,
    _trade_clock_map, _trade_slice_map, _volume_clock_map)
from .discretionary_tape_events import (
    _event_micro_map, _state_series, _test_maturity_map)
from .discretionary_vol import (
    _forward_vol_map, _prior_reaction_map, _regime_map, _target_map)

class CausalDiscretionaryPlane:
    """Prefix-queryable auction, price-ledger, and confirmation state."""

    def __init__(
        self, *, rows: np.ndarray, truth: Mapping[str, np.ndarray],
        asset: str, open_ns: int, duration_sec: int, raw_tick: int,
        multiplier: int, event_state_flags: Mapping[str, np.ndarray],
        level_association_mode: str = "REAL",
        prior_session: PriorSessionContext | None = None,
    ) -> None:
        if level_association_mode not in LEVEL_ASSOCIATION_MODES:
            raise DiscretionaryFeatureRefusal("unknown level-association mode")
        self.rows = np.asarray(rows)
        self.asset = str(asset)
        self.open_ns = int(open_ns)
        self.duration = int(duration_sec)
        self.raw_tick = int(raw_tick)
        self.multiplier = int(multiplier)
        self.factor = 0.5e-9 * float(multiplier)
        self.level_association_mode = level_association_mode
        # Date ordering is checked by the caller, which owns the current
        # EventPack header; asset mismatch can be rejected locally.
        if (prior_session is not None
                and (prior_session.asset != self.asset
                     or prior_session.raw_tick != self.raw_tick
                     or prior_session.multiplier != self.multiplier)):
            raise DiscretionaryFeatureRefusal(
                "prior-session instrument identity differs")
        self.prior_session = prior_session
        self._profile_cache: dict[int, tuple[_ProfileState | None, ...]] = {}
        self._tpo_cache: dict[int, tuple[_ProfileState | None, ...]] = {}
        self._state_cache: dict[tuple[int, int, int], Mapping[str, np.ndarray]] = {}

        n = len(self.rows)
        required_truth = ("trusted_message", "trusted_economic", "mid2")
        if any(np.asarray(truth[name]).shape != (n,) for name in required_truth):
            raise DiscretionaryFeatureRefusal("truth columns do not align with events")
        for name in (
                "bid_reload", "ask_reload", "bid_pull_no_fill",
                "ask_pull_no_fill", "bid_reload_latency_ns",
                "ask_reload_latency_ns", "bid_pull_lifetime_ns",
                "ask_pull_lifetime_ns"):
            if np.asarray(event_state_flags[name]).shape != (n,):
                raise DiscretionaryFeatureRefusal("event-state flags do not align")

        self.message = np.asarray(truth["trusted_message"], bool)
        self.economic = np.asarray(truth["trusted_economic"], bool)
        self.mid2 = np.asarray(truth["mid2"], np.int64)
        self.second = self.rows["receive_session_sec"].astype(np.int64)
        if (n and (int(self.second.min()) < 0
                   or int(self.second.max()) >= self.duration)):
            raise DiscretionaryFeatureRefusal("event second is outside the session")

        self._last_mid = np.full(self.duration, -1, np.int64)
        econ_index = np.flatnonzero(self.economic)
        self._economic_ts = self.rows["ts_recv_ns"][econ_index].astype(np.int64)
        self._economic_mid2 = self.mid2[econ_index].astype(np.int64)
        self._economic_bid_tick = (
            self.rows["bid_px"][econ_index].astype(np.int64) // self.raw_tick)
        self._economic_ask_tick = (
            self.rows["ask_px"][econ_index].astype(np.int64) // self.raw_tick)
        self._economic_bid_size = self.rows["bid_sz"][econ_index].astype(np.int64)
        self._economic_ask_size = self.rows["ask_sz"][econ_index].astype(np.int64)
        self._economic_bid_count = self.rows["bid_ct"][econ_index].astype(np.int64)
        self._economic_ask_count = self.rows["ask_ct"][econ_index].astype(np.int64)
        price_change = (np.r_[True, self._economic_mid2[1:] != self._economic_mid2[:-1]]
                        if len(self._economic_mid2) else np.empty(0, bool))
        self._price_ts = self._economic_ts[price_change]
        self._price_mid2 = self._economic_mid2[price_change]
        if len(econ_index):
            last_index = np.full(self.duration, -1, np.int64)
            np.maximum.at(last_index, self.second[econ_index], econ_index)
            last_index = np.maximum.accumulate(last_index)
            present = last_index >= 0
            self._last_mid[present] = self.mid2[last_index[present]]

        action = self.rows["action"]
        side = self.rows["side"]
        price = self.rows["price"].astype(np.int64)
        size = self.rows["size"].astype(np.int64)

        # Exact trusted-message and trade clocks.  Wall-clock summaries make
        # a quiet tape and a bursty tape look alike; these arrays retain the
        # adaptive event/trade/volume-time state without retaining outcomes.
        message_index = np.flatnonzero(self.message)
        self._message_ts = self.rows["ts_recv_ns"][message_index].astype(np.int64)
        self._message_action = action[message_index].astype(np.uint8)
        self._message_side = side[message_index].astype(np.uint8)
        self._message_size = size[message_index].astype(np.int64)
        self._message_mid2 = self.mid2[message_index].astype(np.int64)
        self._message_economic = self.economic[message_index].astype(bool)
        for name in ("bid_px", "ask_px", "bid_sz", "ask_sz", "bid_ct", "ask_ct"):
            setattr(self, f"_message_{name}",
                    self.rows[name][message_index].astype(np.int64))

        self._second_clock: dict[str, np.ndarray] = {}
        message_second = self.second[message_index]
        message_trade = self._message_action == ord("T")
        message_buy = message_trade & (self._message_side == ord("B"))
        message_sell = message_trade & (self._message_side == ord("A"))
        clock_sources = {
            "event": np.ones(len(message_index), np.int64),
            "trade": message_trade.astype(np.int64),
            "volume": np.where(message_trade, self._message_size, 0),
            "signed_volume": np.where(
                message_buy, self._message_size,
                np.where(message_sell, -self._message_size, 0)),
            "quote_churn": np.where(np.isin(
                self._message_action, (ord("A"), ord("C"), ord("M"))),
                self._message_size, 0),
        }
        for name, source in clock_sources.items():
            aggregate = np.zeros(self.duration, np.int64)
            if len(source):
                np.add.at(aggregate, message_second, source)
            self._second_clock[name] = aggregate
        valid_price = ((price > 0) & (price % self.raw_tick == 0)
                       & self.message
                       & np.isin(action, (ord("A"), ord("C"), ord("M"), ord("T"))))
        event_index = np.flatnonzero(valid_price)
        ticks = (price[event_index] // self.raw_tick).astype(np.int64)
        if level_association_mode == "LEVEL_ASSOCIATION_DESTROYED":
            # Independent of observed data/future rows.  Keeping coordinates
            # inside 64-tick bands preserves realistic local density while
            # breaking exact candidate-level identity.  The odd shifts make
            # the affine permutation fixed-point free.
            ticks = np.asarray([
                _destroy_tick(int(tick), self.asset) for tick in ticks],
                np.int64)
        self._ledger = _build_ledger(
            self, event_index, ticks, action, side, size, event_state_flags)

        trade = (action == ord("T")) & valid_price
        trade_index = np.flatnonzero(trade)
        self._trade_ts = self.rows["ts_recv_ns"][trade_index].astype(np.int64)
        self._trade_sign = np.where(
            side[trade_index] == ord("B"), 1,
            np.where(side[trade_index] == ord("A"), -1, 0)).astype(np.int8)
        self._trade_exact_ticks = (price[trade_index] // self.raw_tick).astype(np.int64)
        self._trade_exact_sizes = size[trade_index].astype(np.int64)
        self._trade_volume_prefix = np.r_[
            np.int64(0), np.cumsum(self._trade_exact_sizes, dtype=np.int64)]
        self._trade_seconds = self.second[trade]
        self._trade_ticks = (price[trade] // self.raw_tick).astype(np.int64)
        self._trade_sizes = size[trade]
        profile_sign = self._trade_sign.astype(np.int64, copy=True)
        order = np.argsort(self._trade_seconds, kind="stable")
        self._trade_seconds = self._trade_seconds[order]
        self._trade_ticks = self._trade_ticks[order]
        self._trade_sizes = self._trade_sizes[order]
        self._trade_profile_sign = profile_sign[order]
        self._profile_cache[0] = _build_profile_series(self, 0)
        self._tpo_cache[0] = _build_tpo_series(self, 0)

    def _profile_at(self, start_sec: int, snapshot_sec: int) -> tuple[
            _ProfileState | None, int]:
        return _profile_at(self, start_sec, snapshot_sec)

    def _tpo_at(self, start_sec: int, snapshot_sec: int) -> _ProfileState | None:
        return _tpo_at(self, start_sec, snapshot_sec)

    def _profile_map(
        self, *, prefix: str, start_sec: int, snapshot_sec: int,
        current_mid2: int, side: int,
    ) -> dict[str, float]:
        return _profile_map(
            self, prefix=prefix, start_sec=start_sec, snapshot_sec=snapshot_sec,
            current_mid2=current_mid2, side=side)

    def _initial_balance_map(
        self, *, prefix: str, start_sec: int, snapshot_sec: int,
        current_mid2: int, side: int,
    ) -> dict[str, float]:
        return _initial_balance_map(
            self, prefix=prefix, start_sec=start_sec, snapshot_sec=snapshot_sec,
            current_mid2=current_mid2, side=side)

    def _ledger_sum(
        self, *, center_tick: int, radius: int, left_sec: int, right_sec: int,
    ) -> tuple[np.ndarray, int, int, int, int, int, int]:
        return _ledger_sum(
            self, center_tick=center_tick, radius=radius,
            left_sec=left_sec, right_sec=right_sec)

    def _price_shape_values(
        self, *, prefix: str, center_tick: int, radius: int,
        left_sec: int, right_sec: int, side: int,
    ) -> dict[str, float]:
        return _price_shape_values(
            self, prefix=prefix, center_tick=center_tick, radius=radius,
            left_sec=left_sec, right_sec=right_sec, side=side)

    def _best_quote_response_map(
        self, *, formation_tick: int, formation_ts_ns: int,
        snapshot_ts_ns: int, side: int,
    ) -> dict[str, float]:
        return _best_quote_response_map(
            self, formation_tick=formation_tick, formation_ts_ns=formation_ts_ns,
            snapshot_ts_ns=snapshot_ts_ns, side=side)

    def _event_clock_map(
        self, *, target_count: int, snapshot_ts_ns: int,
        formation_ts_ns: int, side: int,
    ) -> dict[str, float]:
        return _event_clock_map(
            self, target_count=target_count, snapshot_ts_ns=snapshot_ts_ns,
            formation_ts_ns=formation_ts_ns, side=side)

    def _trade_slice_map(
        self, *, prefix: str, left: int, right: int, support_fraction: float,
        snapshot_ts_ns: int, formation_ts_ns: int, side: int,
    ) -> dict[str, float]:
        return _trade_slice_map(
            self, prefix=prefix, left=left, right=right,
            support_fraction=support_fraction, snapshot_ts_ns=snapshot_ts_ns,
            formation_ts_ns=formation_ts_ns, side=side)

    def _trade_clock_map(
        self, *, target_count: int, snapshot_ts_ns: int,
        formation_ts_ns: int, side: int,
    ) -> dict[str, float]:
        return _trade_clock_map(
            self, target_count=target_count, snapshot_ts_ns=snapshot_ts_ns,
            formation_ts_ns=formation_ts_ns, side=side)

    def _volume_clock_map(
        self, *, target_volume: int, snapshot_ts_ns: int,
        formation_ts_ns: int, side: int,
    ) -> dict[str, float]:
        return _volume_clock_map(
            self, target_volume=target_volume, snapshot_ts_ns=snapshot_ts_ns,
            formation_ts_ns=formation_ts_ns, side=side)

    def _event_micro_map(
        self, *, prefix: str, center_tick: int, radius: int,
        left_ns: int, right_ns: int, side: int,
    ) -> dict[str, float]:
        return _event_micro_map(
            self, prefix=prefix, center_tick=center_tick, radius=radius,
            left_ns=left_ns, right_ns=right_ns, side=side)

    def _state_series(
        self, formation_ts_ns: int, formation_mid2: int, side: int,
    ) -> Mapping[str, np.ndarray]:
        return _state_series(self, formation_ts_ns, formation_mid2, side)

    def _forward_vol_map(
        self, *, formation_candidate: Mapping[str, object],
        formation_sec: int, phase_open_sec: int, snapshot_sec: int,
        current_mid2: int, formation_mid2: int, side: int,
    ) -> dict[str, float]:
        return _forward_vol_map(
            self, formation_candidate=formation_candidate,
            formation_sec=formation_sec, phase_open_sec=phase_open_sec,
            snapshot_sec=snapshot_sec, current_mid2=current_mid2,
            formation_mid2=formation_mid2, side=side)

    def _regime_map(
        self, *, snapshot_sec: int, current_mid2: int, side: int,
    ) -> dict[str, float]:
        return _regime_map(
            self, snapshot_sec=snapshot_sec, current_mid2=current_mid2, side=side)

    def _target_map(
        self, *, snapshot_sec: int, current_mid2: int, side: int,
        phase_open_sec: int, atr_usd: float,
    ) -> dict[str, float]:
        return _target_map(
            self, snapshot_sec=snapshot_sec, current_mid2=current_mid2,
            side=side, phase_open_sec=phase_open_sec, atr_usd=atr_usd)

    def _prior_reaction_map(
        self, *, formation_tick: int, formation_ts_ns: int, side: int,
    ) -> dict[str, float]:
        return _prior_reaction_map(
            self, formation_tick=formation_tick,
            formation_ts_ns=formation_ts_ns, side=side)

    def feature_map(
        self, *, snapshot_ts_ns: int, current_bid: int, current_ask: int,
        current_mid2: int, side: int, formation_candidate: Mapping[str, str],
    ) -> Mapping[str, float]:
        snapshot_sec = int((int(snapshot_ts_ns) - self.open_ns) // 1_000_000_000)
        if not 0 <= snapshot_sec <= self.duration:
            raise DiscretionaryFeatureRefusal("snapshot is outside session")
        formation_sec = int(formation_candidate["decision_sec"])
        formation_mid2 = int(formation_candidate["entry_mid2"])
        formation_bid = int(formation_candidate["entry_bid_px"])
        formation_ask = int(formation_candidate["entry_ask_px"])
        phase_open_sec = int(formation_candidate["phase_open_utc"]) - self.open_ns // 1_000_000_000
        if not (0 <= formation_sec <= snapshot_sec
                and formation_bid > 0 and formation_ask > formation_bid):
            raise DiscretionaryFeatureRefusal("formation state is malformed")
        values: dict[str, float] = {}
        values.update(self._profile_map(
            prefix="disc_auction_session_", start_sec=0,
            snapshot_sec=snapshot_sec, current_mid2=current_mid2, side=side))
        values.update(self._profile_map(
            prefix="disc_auction_phase_", start_sec=phase_open_sec,
            snapshot_sec=snapshot_sec, current_mid2=current_mid2, side=side))
        values.update(self._initial_balance_map(
            prefix="disc_ib_session_", start_sec=0,
            snapshot_sec=snapshot_sec, current_mid2=current_mid2, side=side))
        values.update(self._initial_balance_map(
            prefix="disc_ib_phase_", start_sec=phase_open_sec,
            snapshot_sec=snapshot_sec, current_mid2=current_mid2, side=side))
        if self.prior_session is None:
            values.update(PriorSessionContext.empty_feature_map())
        else:
            values.update(self.prior_session.feature_map(
                current_mid2=current_mid2, formation_bid=formation_bid,
                formation_ask=formation_ask, side=side,
                level_association_mode=self.level_association_mode))
        values.update(self._forward_vol_map(
            formation_candidate=formation_candidate,
            formation_sec=formation_sec, phase_open_sec=phase_open_sec,
            snapshot_sec=snapshot_sec, current_mid2=current_mid2,
            formation_mid2=formation_mid2, side=side))
        values.update(self._regime_map(
            snapshot_sec=snapshot_sec, current_mid2=current_mid2, side=side))

        formation_tick = ((formation_bid if side > 0 else formation_ask)
                          // self.raw_tick)
        current_tick = ((int(current_bid) if side > 0 else int(current_ask))
                        // self.raw_tick)
        try:
            atr_usd = float(formation_candidate.get("atr14_prev_usd", 0.0))
        except (TypeError, ValueError):
            atr_usd = 0.0
        values.update(self._target_map(
            snapshot_sec=snapshot_sec, current_mid2=current_mid2,
            side=side, phase_open_sec=phase_open_sec, atr_usd=atr_usd))
        for radius in (0, 2, 4):
            values.update(_level_values(self,
                prefix=f"disc_memory_z{radius}_", center_tick=formation_tick,
                radius=radius, left_sec=0, right_sec=formation_sec,
                side=side, age_reference_sec=formation_sec))
            values.update(_level_values(self,
                prefix=f"disc_level_z{radius}_", center_tick=formation_tick,
                radius=radius, left_sec=formation_sec, right_sec=snapshot_sec,
                side=side, age_reference_sec=snapshot_sec))
        values.update(_level_values(self,
            prefix="disc_current_z2_", center_tick=current_tick, radius=2,
            left_sec=max(0, snapshot_sec - 30), right_sec=snapshot_sec,
            side=side, age_reference_sec=snapshot_sec))

        formation_ts_ns = int(formation_candidate["decision_ts_ns"])
        values.update(self._prior_reaction_map(
            formation_tick=formation_tick,
            formation_ts_ns=formation_ts_ns, side=side))
        for target_count in (16, 64, 256, 1024):
            values.update(self._event_clock_map(
                target_count=target_count,
                snapshot_ts_ns=int(snapshot_ts_ns),
                formation_ts_ns=formation_ts_ns, side=side))
        for target_count in (8, 32, 128, 512):
            values.update(self._trade_clock_map(
                target_count=target_count,
                snapshot_ts_ns=int(snapshot_ts_ns),
                formation_ts_ns=formation_ts_ns, side=side))
        for target_volume in (64, 256, 1024):
            values.update(self._volume_clock_map(
                target_volume=target_volume,
                snapshot_ts_ns=int(snapshot_ts_ns),
                formation_ts_ns=formation_ts_ns, side=side))
        values.update(_tape_slope_map(
            self, snapshot_sec=snapshot_sec, side=side))
        values.update(_test_maturity_map(
            self, formation_tick=formation_tick,
            formation_ts_ns=formation_ts_ns,
            snapshot_ts_ns=int(snapshot_ts_ns), side=side))
        values.update(self._best_quote_response_map(
            formation_tick=formation_tick,
            formation_ts_ns=formation_ts_ns,
            snapshot_ts_ns=int(snapshot_ts_ns), side=side))
        event_prefixes: dict[int, str] = {}
        for horizon in (1, 5, 15, 30, 60, 120, 300):
            event_prefix = f"disc_evt_h{horizon}_"
            event_prefixes[horizon] = event_prefix
            values.update(self._event_micro_map(
                prefix=event_prefix, center_tick=formation_tick, radius=2,
                left_ns=max(formation_ts_ns,
                            int(snapshot_ts_ns) - horizon * 1_000_000_000),
                right_ns=int(snapshot_ts_ns), side=side))
        for horizon in (30, 300):
            values.update(self._price_shape_values(
                prefix=f"disc_footprint_h{horizon}_",
                center_tick=formation_tick, radius=4,
                left_sec=max(formation_sec, snapshot_sec - horizon),
                right_sec=snapshot_sec, side=side))

        _path_behavior_map(
            self, values, snapshot_ts_ns=int(snapshot_ts_ns),
            current_mid2=current_mid2, formation_mid2=formation_mid2,
            formation_ts_ns=formation_ts_ns, side=side,
            event_prefixes=event_prefixes)
        values["disc_level_association_destroyed"] = float(
            self.level_association_mode == "LEVEL_ASSOCIATION_DESTROYED")
        values["disc_fill_coupling_destroyed"] = float(
            self.level_association_mode == "FILL_COUPLING_DESTROYED")
        if any(not math.isfinite(value) for value in values.values()):
            raise DiscretionaryFeatureRefusal("discretionary feature map is non-finite")
        return MappingProxyType(values)

    _level_values = _level_values
    _tape_slope_map = _tape_slope_map
    _test_maturity_map = _test_maturity_map


__all__ = [
    "CausalDiscretionaryPlane", "DISCRETIONARY_FEATURE_SCHEMA",
    "DiscretionaryFeatureRefusal", "LEVEL_ASSOCIATION_MODES",
    "PRIOR_SESSION_SCHEMA", "PROFILE_INTERVAL_SEC", "PriorSessionContext",
]
