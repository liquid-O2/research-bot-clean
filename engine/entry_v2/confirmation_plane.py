"""Causal per-session feature plane for confirmation materialization."""

from __future__ import annotations

import math
from types import MappingProxyType
from typing import Mapping, Sequence

import numpy as np

from .confirmation_types import (
    ConfirmationAnchor, ConfirmationRefusal, FEATURE_WINDOWS_SECONDS,
    NANOS_PER_SECOND,
)
from .corpus_units import ASSET_MULTIPLIER, ASSET_RAW_TICK
from .diagnostic_inputs import CandidateTruthBinding
from .discretionary_features import (
    CausalDiscretionaryPlane, DiscretionaryFeatureRefusal, PriorSessionContext,
)
from .event_pack import EVENT_DTYPE, EventPack


class _SessionPlane:
    """One-second state whose additive fields consume every raw event row."""

    ADDITIVE = (
        "event_count", "trusted_message_count", "economic_count",
        "trade_count", "trade_volume", "buy_trade_volume", "sell_trade_volume",
        "unsigned_trade_volume", "signed_trade_volume", "add_count", "cancel_count",
        "modify_count", "other_action_count", "add_side_size", "cancel_side_size",
        "modify_side_size", "buy_trade_count", "sell_trade_count",
        "bid_up_count", "bid_down_count", "ask_up_count", "ask_down_count",
        "spread_widen_count", "spread_narrow_count", "through_ask_count",
        "through_bid_count", "ask_reload_count", "bid_reload_count",
        "ask_retreat_after_buy_count", "bid_retreat_after_sell_count",
        "bid_size_delta", "ask_size_delta", "mid_abs_change_raw",
        "up_mid_change_count", "down_mid_change_count", "latency_ns_sum",
        "latency_count", "bad_flag_count",
    )

    def __init__(
        self, pack: EventPack, truth: Mapping[str, np.ndarray],
        *, level_association_mode: str = "REAL",
        prior_session_context: PriorSessionContext | None = None,
    ) -> None:
        rows = np.asarray(pack.rows)
        if rows.dtype != EVENT_DTYPE:
            raise ConfirmationRefusal("session plane requires QRE2EVT2 rows")
        self.rows = rows; self.asset = pack.header.asset
        self.open_ns = pack.header.open_ns
        self.duration = pack.header.close_utc - pack.header.open_utc
        self.multiplier = int(ASSET_MULTIPLIER[self.asset])
        self.raw_tick = int(ASSET_RAW_TICK[self.asset])
        sec = rows["receive_session_sec"].astype(np.int64)
        if len(rows) and (int(sec.min()) < 0 or int(sec.max()) >= self.duration):
            raise ConfirmationRefusal("event second falls outside session")
        n = len(rows); action = rows["action"]; side = rows["side"]
        size = rows["size"].astype(np.int64)  # cast before every signed operation
        is_trade = action == ord("T")
        buy = is_trade & (side == ord("B")); sell = is_trade & (side == ord("A"))
        unsigned = is_trade & ~(buy | sell)
        side_sign = np.where(side == ord("B"), 1,
                             np.where(side == ord("A"), -1, 0)).astype(np.int64)
        message = np.asarray(truth["trusted_message"], bool)
        economic = np.asarray(truth["trusted_economic"], bool)
        generation = np.asarray(truth["generation"], np.uint32)
        mid2 = np.asarray(truth["mid2"], np.int64)
        spread = np.asarray(truth["spread"], np.int64)

        per_event: dict[str, np.ndarray] = {
            "event_count": np.ones(n, np.int64),
            "trusted_message_count": message.astype(np.int64),
            "economic_count": economic.astype(np.int64),
            "trade_count": is_trade.astype(np.int64),
            "trade_volume": np.where(is_trade, size, 0),
            "buy_trade_volume": np.where(buy, size, 0),
            "sell_trade_volume": np.where(sell, size, 0),
            "unsigned_trade_volume": np.where(unsigned, size, 0),
            "signed_trade_volume": np.where(buy, size, np.where(sell, -size, 0)),
            "add_count": (action == ord("A")).astype(np.int64),
            "cancel_count": (action == ord("C")).astype(np.int64),
            "modify_count": (action == ord("M")).astype(np.int64),
            "other_action_count": (~np.isin(action, (ord("A"), ord("C"),
                                                       ord("M"), ord("T")))).astype(np.int64),
            "add_side_size": np.where(action == ord("A"), side_sign * size, 0),
            "cancel_side_size": np.where(action == ord("C"), side_sign * size, 0),
            "modify_side_size": np.where(action == ord("M"), side_sign * size, 0),
            "buy_trade_count": buy.astype(np.int64),
            "sell_trade_count": sell.astype(np.int64),
            "latency_ns_sum": (rows["ts_recv_ns"].astype(np.int64)
                               - rows["ts_event_ns"].astype(np.int64)),
            "latency_count": np.ones(n, np.int64),
            "bad_flag_count": (rows["flags"] != 0).astype(np.int64),
        }
        same = np.zeros(n, bool)
        if n > 1:
            same[1:] = (message[1:] & message[:-1]
                        & (generation[1:] == generation[:-1]))
        bid = rows["bid_px"].astype(np.int64); ask = rows["ask_px"].astype(np.int64)
        bid_sz = rows["bid_sz"].astype(np.int64); ask_sz = rows["ask_sz"].astype(np.int64)
        def transition(predicate: np.ndarray) -> np.ndarray:
            out = np.zeros(n, np.int64); out[1:] = (same[1:] & predicate).astype(np.int64); return out
        per_event.update({
            "bid_up_count": transition(bid[1:] > bid[:-1]),
            "bid_down_count": transition(bid[1:] < bid[:-1]),
            "ask_up_count": transition(ask[1:] > ask[:-1]),
            "ask_down_count": transition(ask[1:] < ask[:-1]),
            "spread_widen_count": transition(spread[1:] > spread[:-1]),
            "spread_narrow_count": transition(spread[1:] < spread[:-1]),
            "bid_size_delta": np.r_[0, np.where(same[1:], bid_sz[1:] - bid_sz[:-1], 0)],
            "ask_size_delta": np.r_[0, np.where(same[1:], ask_sz[1:] - ask_sz[:-1], 0)],
        })
        mid_delta = np.zeros(n, np.int64)
        if n > 1:
            valid_mid = economic[1:] & economic[:-1] & (generation[1:] == generation[:-1])
            mid_delta[1:] = np.where(valid_mid, mid2[1:] - mid2[:-1], 0)
        per_event["mid_abs_change_raw"] = np.abs(mid_delta)
        per_event["up_mid_change_count"] = (mid_delta > 0).astype(np.int64)
        per_event["down_mid_change_count"] = (mid_delta < 0).astype(np.int64)

        through_ask = np.zeros(n, np.int64); through_bid = np.zeros(n, np.int64)
        if n > 1:
            through_ask[1:] = (buy[1:] & message[:-1]
                               & (rows["price"][1:] > ask[:-1])).astype(np.int64)
            through_bid[1:] = (sell[1:] & message[:-1]
                               & (rows["price"][1:] < bid[:-1])).astype(np.int64)
        per_event["through_ask_count"] = through_ask
        per_event["through_bid_count"] = through_bid

        # Ordered event-state flags.  These are derived once from the complete
        # stream and then conserved into seconds; no text ribbon or size floor
        # can remove an event.
        ask_reload = np.zeros(n, np.int64); bid_reload = np.zeros(n, np.int64)
        ask_retreat = np.zeros(n, np.int64); bid_retreat = np.zeros(n, np.int64)
        ask_pull_no_fill = np.zeros(n, np.int64)
        bid_pull_no_fill = np.zeros(n, np.int64)
        ask_reload_latency_ns = np.zeros(n, np.int64)
        bid_reload_latency_ns = np.zeros(n, np.int64)
        ask_pull_lifetime_ns = np.zeros(n, np.int64)
        bid_pull_lifetime_ns = np.zeros(n, np.int64)
        last_buy_ts = last_sell_ts = -1
        last_buy_px = last_sell_px = -1
        last_add: dict[tuple[int, int], tuple[int, int]] = {}
        last_trade_by_price: dict[int, int] = {}
        for index in range(n):
            now = int(rows["ts_recv_ns"][index])
            if buy[index]:
                last_buy_ts = now; last_buy_px = int(rows["price"][index])
                last_trade_by_price[last_buy_px] = now
            elif sell[index]:
                last_sell_ts = now; last_sell_px = int(rows["price"][index])
                last_trade_by_price[last_sell_px] = now
            current_price = int(rows["price"][index])
            current_side = int(side[index])
            if (current_price > 0 and action[index] in (ord("A"), ord("M"))
                    and current_side in (ord("B"), ord("A"))):
                last_add[(current_side, current_price)] = (
                    now, last_trade_by_price.get(current_price, -1))
            elif (current_price > 0 and action[index] == ord("C")
                  and current_side in (ord("B"), ord("A"))):
                previous = last_add.pop((current_side, current_price), None)
                if (previous is not None and now - previous[0] <= NANOS_PER_SECOND
                        and last_trade_by_price.get(current_price, -1) <= previous[1]):
                    if current_side == ord("B"):
                        bid_pull_no_fill[index] = 1
                        bid_pull_lifetime_ns[index] = now - previous[0]
                    else:
                        ask_pull_no_fill[index] = 1
                        ask_pull_lifetime_ns[index] = now - previous[0]
            if index and same[index]:
                if (now - last_buy_ts <= NANOS_PER_SECOND
                        and action[index] in (ord("A"), ord("M"))
                        and side[index] == ord("A")
                        and int(ask[index]) == last_buy_px):
                    ask_reload[index] = 1
                    ask_reload_latency_ns[index] = now - last_buy_ts
                if (now - last_sell_ts <= NANOS_PER_SECOND
                        and action[index] in (ord("A"), ord("M"))
                        and side[index] == ord("B")
                        and int(bid[index]) == last_sell_px):
                    bid_reload[index] = 1
                    bid_reload_latency_ns[index] = now - last_sell_ts
                if now - last_buy_ts <= 250_000_000 and ask[index] > ask[index - 1] > 0:
                    ask_retreat[index] = 1
                if now - last_sell_ts <= 250_000_000 and 0 < bid[index] < bid[index - 1]:
                    bid_retreat[index] = 1
        per_event["ask_reload_count"] = ask_reload
        per_event["bid_reload_count"] = bid_reload
        per_event["ask_retreat_after_buy_count"] = ask_retreat
        per_event["bid_retreat_after_sell_count"] = bid_retreat
        event_state_flags = MappingProxyType({
            "ask_reload": ask_reload,
            "bid_reload": bid_reload,
            "ask_pull_no_fill": ask_pull_no_fill,
            "bid_pull_no_fill": bid_pull_no_fill,
            "ask_reload_latency_ns": ask_reload_latency_ns,
            "bid_reload_latency_ns": bid_reload_latency_ns,
            "ask_pull_lifetime_ns": ask_pull_lifetime_ns,
            "bid_pull_lifetime_ns": bid_pull_lifetime_ns,
        })

        self.second: dict[str, np.ndarray] = {}
        self.prefix: dict[str, np.ndarray] = {}
        for name in self.ADDITIVE:
            values = np.asarray(per_event[name], np.int64)
            aggregate = np.zeros(self.duration, np.int64)
            if len(values):
                np.add.at(aggregate, sec, values)
            self.second[name] = aggregate
            self.prefix[name] = np.r_[0, np.cumsum(aggregate, dtype=np.int64)]

        # Last trusted/economic book before each whole-second boundary.
        econ_last = np.full(self.duration, -1, np.int64)
        if economic.any():
            np.maximum.at(econ_last, sec[economic], np.flatnonzero(economic))
        self.prefix_last_economic = np.r_[
            -1, np.maximum.accumulate(econ_last, dtype=np.int64)
        ]
        self.mid_min_sec = np.full(self.duration, np.iinfo(np.int64).max, np.int64)
        self.mid_max_sec = np.full(self.duration, np.iinfo(np.int64).min, np.int64)
        if economic.any():
            np.minimum.at(self.mid_min_sec, sec[economic], mid2[economic])
            np.maximum.at(self.mid_max_sec, sec[economic], mid2[economic])
        self.truth = truth
        try:
            self.discretionary = CausalDiscretionaryPlane(
                rows=rows, truth=truth, asset=self.asset,
                open_ns=self.open_ns, duration_sec=self.duration,
                raw_tick=self.raw_tick, multiplier=self.multiplier,
                event_state_flags=event_state_flags,
                level_association_mode=level_association_mode,
                prior_session=prior_session_context,
            )
        except DiscretionaryFeatureRefusal as exc:
            raise ConfirmationRefusal(
                f"discretionary plane refused: {exc}") from exc

    def total(self, name: str, left: int, right: int) -> int:
        a = max(0, int(left)); b = min(self.duration, int(right))
        if b <= a:
            return 0
        return int(self.prefix[name][b] - self.prefix[name][a])

    def last_mid_before_second(self, second: int) -> int | None:
        point = min(max(0, int(second)), self.duration)
        index = int(self.prefix_last_economic[point])
        return None if index < 0 else int(self.truth["mid2"][index])

    def feature_map(
        self,
        anchor: ConfirmationAnchor,
        active: Sequence[CandidateTruthBinding],
        active_candidates: Sequence[Mapping[str, str]],
    ) -> Mapping[str, float]:
        second = int((anchor.snapshot_ts_ns - self.open_ns) // NANOS_PER_SECOND)
        if not 0 <= second <= self.duration:
            raise ConfirmationRefusal("confirmation snapshot is outside session")
        side = int(anchor.side); mult = float(self.multiplier); factor = .5e-9 * mult
        row = self.rows[anchor.entry_event_ordinal]
        bid_size, ask_size = int(row["bid_sz"]), int(row["ask_sz"])
        count_total = int(row["bid_ct"]) + int(row["ask_ct"])
        size_total = bid_size + ask_size
        if (len(active_candidates) != len(active)
                or {str(item.get("candidate_id", "")) for item in active_candidates}
                != {item.candidate_id for item in active}):
            raise ConfirmationRefusal("candidate feature join differs from active alerts")
        formation = np.asarray([item.entry_mid2 for item in active], np.float64)
        atr = np.asarray([float(item["atr14_prev_usd"])
                          for item in active_candidates], np.float64)
        formation_spread = np.asarray([float(item["entry_spread_usd"])
                                       for item in active_candidates], np.float64)
        formation_cost = np.asarray([float(item["frozen_cost_usd"])
                                     for item in active_candidates], np.float64)
        spread_prior = np.asarray([float(item["spread_prior_usd"])
                                   for item in active_candidates], np.float64)
        rung_mask = np.asarray([int(item["rung_mask"])
                                for item in active_candidates], np.int64)
        if np.any((rung_mask < 1) | (rung_mask > 15)):
            raise ConfirmationRefusal("active candidate has an invalid rung mask")
        phase_value = str(anchor.phase)
        try:
            phase_index = float(int(phase_value))
        except ValueError:
            phase_index = float({"TOKYO": 0, "LONDON": 1, "NY": 2}.get(
                phase_value.upper(), -1))
        values: dict[str, float] = {
            "asset_SI": float(anchor.asset == "SI"),
            "asset_HG": float(anchor.asset == "HG"),
            "asset_NKD": float(anchor.asset == "NKD"),
            "side": float(side), "phase_index": phase_index,
            "candidate_count": float(len(active)),
            "min_alert_age_sec": float(anchor.min_alert_age_sec),
            "max_alert_age_sec": float(anchor.max_alert_age_sec),
            "phase_remaining_sec": (anchor.phase_close_ts_ns - anchor.snapshot_ts_ns)
                                     / NANOS_PER_SECOND,
            "current_spread_usd": float(anchor.entry_spread_usd),
            "current_cost_usd": float(anchor.frozen_cost_usd),
            "current_bid_size": float(bid_size),
            "current_ask_size": float(ask_size),
            "current_size_imbalance": ((bid_size - ask_size) / size_total
                                       if size_total else 0.0),
            "current_count_imbalance": ((int(row["bid_ct"]) - int(row["ask_ct"]))
                                        / count_total if count_total else 0.0),
            "aligned_from_formation_mean_usd": float(
                side * (anchor.entry_mid2 - formation.mean()) * factor),
            "aligned_from_formation_best_usd": float(np.max(
                side * (anchor.entry_mid2 - formation) * factor)),
            "aligned_from_formation_worst_usd": float(np.min(
                side * (anchor.entry_mid2 - formation) * factor)),
            "formation_atr_mean_usd": float(atr.mean()),
            "formation_atr_min_usd": float(atr.min()),
            "formation_atr_max_usd": float(atr.max()),
            "formation_spread_mean_usd": float(formation_spread.mean()),
            "formation_spread_min_usd": float(formation_spread.min()),
            "formation_spread_max_usd": float(formation_spread.max()),
            "formation_cost_mean_usd": float(formation_cost.mean()),
            "formation_cost_min_usd": float(formation_cost.min()),
            "formation_cost_max_usd": float(formation_cost.max()),
            "spread_prior_present_fraction": float(np.mean([
                int(item["spread_prior_present"]) for item in active_candidates
            ])),
            "spread_prior_mean_usd": float(spread_prior.mean()),
            "fast_open_present": float(any(
                item["delay"] == "FAST_OPEN_15" for item in active_candidates)),
            "fast_open_fraction": float(np.mean([
                item["delay"] == "FAST_OPEN_15" for item in active_candidates
            ])),
        }
        if any(item["delay"] not in {"STANDARD_120", "FAST_OPEN_15"}
               for item in active_candidates):
            raise ConfirmationRefusal("active candidate delay is outside the roster")
        for bit in range(4):
            present = ((rung_mask >> bit) & 1).astype(np.float64)
            values[f"rung_{bit}_present"] = float(present.max())
            values[f"rung_{bit}_fraction"] = float(present.mean())

        # Candidate-local formation context and price-level memory are kept
        # separate from the generic time windows below.  A native confirmation
        # series contains exactly one candidate by contract.
        if len(active_candidates) != 1:
            raise ConfirmationRefusal(
                "discretionary features require one native candidate per series")
        try:
            discretionary = self.discretionary.feature_map(
                snapshot_ts_ns=anchor.snapshot_ts_ns,
                current_bid=anchor.entry_bid_px,
                current_ask=anchor.entry_ask_px,
                current_mid2=anchor.entry_mid2,
                side=side,
                formation_candidate=active_candidates[0],
            )
        except DiscretionaryFeatureRefusal as exc:
            raise ConfirmationRefusal(
                f"discretionary feature map refused: {exc}") from exc
        if set(values) & set(discretionary):
            raise ConfirmationRefusal("discretionary feature name collides")
        values.update(discretionary)

        for window in FEATURE_WINDOWS_SECONDS:
            left = max(0, second - window)
            prefix = f"w{window}_"
            event_count = self.total("event_count", left, second)
            trade_count = self.total("trade_count", left, second)
            trade_volume = self.total("trade_volume", left, second)
            signed_flow = self.total("signed_trade_volume", left, second)
            aligned_flow = side * signed_flow
            start_mid = self.last_mid_before_second(left)
            displacement = (0.0 if start_mid is None else
                            side * (anchor.entry_mid2 - start_mid) * factor)
            mins = self.mid_min_sec[left:second]
            maxs = self.mid_max_sec[left:second]
            have_min = mins[mins != np.iinfo(np.int64).max]
            have_max = maxs[maxs != np.iinfo(np.int64).min]
            if len(have_min) and len(have_max):
                low, high = int(have_min.min()), int(have_max.max())
                baseline = low if start_mid is None else int(start_mid)
                favorable = max(side * (low - baseline) * factor,
                                side * (high - baseline) * factor, 0.0)
                adverse = max(-side * (low - baseline) * factor,
                              -side * (high - baseline) * factor, 0.0)
            else:
                favorable = adverse = 0.0
            variation = self.total("mid_abs_change_raw", left, second) * factor
            bid_delta = self.total("bid_size_delta", left, second)
            ask_delta = self.total("ask_size_delta", left, second)
            values.update({
                prefix + "event_count": float(event_count),
                prefix + "event_rate": event_count / float(window),
                prefix + "trusted_fraction": (self.total("trusted_message_count", left, second)
                                                / event_count if event_count else 0.0),
                prefix + "trade_count": float(trade_count),
                prefix + "trade_volume": float(trade_volume),
                prefix + "aligned_trade_flow": float(aligned_flow),
                prefix + "aligned_flow_fraction": (aligned_flow / trade_volume
                                                     if trade_volume else 0.0),
                prefix + "aligned_displacement_usd": float(displacement),
                prefix + "favorable_excursion_usd": float(favorable),
                prefix + "adverse_excursion_usd": float(adverse),
                prefix + "path_variation_usd": float(variation),
                prefix + "path_efficiency": (abs(displacement) / variation
                                              if variation else 0.0),
                prefix + "price_per_aligned_volume": (displacement / abs(aligned_flow)
                                                       if aligned_flow else 0.0),
                prefix + "opposing_absorption": (max(0.0, -aligned_flow)
                                                  / (1.0 + abs(displacement))),
                prefix + "buy_volume": float(self.total("buy_trade_volume", left, second)),
                prefix + "sell_volume": float(self.total("sell_trade_volume", left, second)),
                prefix + "through_ask": float(self.total("through_ask_count", left, second)),
                prefix + "through_bid": float(self.total("through_bid_count", left, second)),
                prefix + "bid_reload": float(self.total("bid_reload_count", left, second)),
                prefix + "ask_reload": float(self.total("ask_reload_count", left, second)),
                prefix + "aligned_defense": float(
                    self.total("bid_reload_count" if side > 0 else "ask_reload_count",
                               left, second)),
                prefix + "opposing_retreat": float(
                    self.total("ask_retreat_after_buy_count" if side > 0
                               else "bid_retreat_after_sell_count", left, second)),
                prefix + "aligned_book_size_change": float(side * (bid_delta - ask_delta)),
                prefix + "bid_steps": float(self.total("bid_up_count", left, second)
                                             - self.total("bid_down_count", left, second)),
                prefix + "ask_steps": float(self.total("ask_up_count", left, second)
                                             - self.total("ask_down_count", left, second)),
                prefix + "spread_widen_minus_narrow": float(
                    self.total("spread_widen_count", left, second)
                    - self.total("spread_narrow_count", left, second)),
                prefix + "add_side_size": float(side * self.total("add_side_size", left, second)),
                prefix + "cancel_side_size": float(side * self.total("cancel_side_size", left, second)),
                prefix + "modify_side_size": float(side * self.total("modify_side_size", left, second)),
                prefix + "mid_direction_balance": float(side * (
                    self.total("up_mid_change_count", left, second)
                    - self.total("down_mid_change_count", left, second))),
                prefix + "mean_latency_us": (self.total("latency_ns_sum", left, second)
                                              / max(1, self.total("latency_count", left, second))
                                              / 1000.0),
                prefix + "bad_flag_fraction": (self.total("bad_flag_count", left, second)
                                                / event_count if event_count else 0.0),
            })
        if any(not math.isfinite(value) for value in values.values()):
            raise ConfirmationRefusal("confirmation feature map is non-finite")
        return MappingProxyType(values)
