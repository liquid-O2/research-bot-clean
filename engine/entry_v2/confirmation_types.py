"""Core confirmation contracts, receipts, and clock helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from typing import Mapping

import numpy as np

from . import common as C
from .discretionary_features import (
    DISCRETIONARY_FEATURE_SCHEMA, LEVEL_ASSOCIATION_MODES,
)
from .event_pack import EventPack


SCHEMA = "QRE2CONF1"
DATASET_SCHEMA = "QRE2CONFDS1"
RECEIPT_SCHEMA = "QRE2CONFRECEIPT1"
NANOS_PER_SECOND = 1_000_000_000
FEE_USD = 5.0
WALL_USD = 900.0
GOAL_USD = 600.0
FEATURE_WINDOWS_SECONDS = (1, 5, 15, 30, 60, 120, 300, 600, 1800)


class ConfirmationRefusal(RuntimeError):
    """The confirmation stream, feature, label, or persistence law failed."""


# Ticket 42. The corpus does not need every scheduled age, it needs the ages the
# entry work reads, and this is that set MEASURED rather than guessed: the union
# of probe_trained_accrual.DELTAS (7), probe_armed_entry.AGE_GRID (8) and the
# live rule's FORM_DELTA/DELTA_SEC. Nine of the 37 training offsets, a 4.1x row
# cut, and nothing dropped that anything reads.
#
# It is deliberately NOT four. A four-age corpus cannot answer the ticket-29
# entry-age decay bound, which reads eight, and that bound is what killed the
# ticket-28 hold. Cutting below what the diagnostics read buys 0.6 h and
# disarms the measurement that decides whether a rule is priced honestly.
#
# What it DOES discard: the 5-second resolution below 60 s and the 10-second
# resolution to 300 s. No live probe reads those, and recovering them means
# rebuilding the corpus. Fixture: test_confirmation.CorpusAgeGrid.
CORPUS_AGE_GRID_SECONDS: tuple[int, ...] = (0, 30, 60, 90, 120, 180, 240, 290, 300)
AGE_GRIDS = frozenset({"FULL", "CORPUS"})


def training_offsets_seconds(max_delay_sec: int = 600) -> tuple[int, ...]:
    """The cheap registered training grid, including the formation baseline."""

    if max_delay_sec not in (300, 600):
        raise ConfirmationRefusal("confirmation expiry must be 300 or 600 seconds")
    values = list(range(0, min(60, max_delay_sec) + 1, 5))
    if max_delay_sec > 60:
        values.extend(range(70, min(300, max_delay_sec) + 1, 10))
    if max_delay_sec > 300:
        values.extend(range(330, max_delay_sec + 1, 30))
    return tuple(values)


def replay_offsets_seconds(max_delay_sec: int = 600) -> tuple[int, ...]:
    if max_delay_sec not in (300, 600):
        raise ConfirmationRefusal("confirmation expiry must be 300 or 600 seconds")
    return tuple(range(0, max_delay_sec + 1))


def _ceil_second(value: int) -> int:
    return ((int(value) + NANOS_PER_SECOND - 1) // NANOS_PER_SECOND) * NANOS_PER_SECOND


@dataclass(frozen=True, slots=True)
class ConfirmationConfig:
    max_delay_sec: int = 600
    snapshot_mode: str = "TRAINING"
    # "FULL" schedules every training offset. "CORPUS" schedules only
    # CORPUS_AGE_GRID_SECONDS, which is a 4.1x row cut for the corpus build and
    # drops nothing any live probe reads (ticket 42). It is a strict subset, so
    # the rows it keeps are the same rows, and `receipt_sha256` carries the
    # offsets, so a reduced corpus can never pass as a full-resolution one.
    age_grid: str = "FULL"
    fee_usd: float = FEE_USD
    wall_usd: float = WALL_USD
    level_association_mode: str = "REAL"
    require_forecast_context: bool = False
    require_slow_context: bool = False

    def __post_init__(self) -> None:
        if self.max_delay_sec not in (300, 600):
            raise ConfirmationRefusal("max_delay_sec must be 300 or 600")
        if self.snapshot_mode not in {"TRAINING", "REPLAY"}:
            raise ConfirmationRefusal("snapshot_mode must be TRAINING or REPLAY")
        if self.age_grid not in AGE_GRIDS:
            raise ConfirmationRefusal(
                f"age_grid must be one of {sorted(AGE_GRIDS)}; got {self.age_grid!r}")
        if self.level_association_mode not in LEVEL_ASSOCIATION_MODES:
            raise ConfirmationRefusal("level_association_mode is invalid")
        if not isinstance(self.require_forecast_context, bool):
            raise ConfirmationRefusal("require_forecast_context must be boolean")
        if not isinstance(self.require_slow_context, bool):
            raise ConfirmationRefusal("require_slow_context must be boolean")
        if (not math.isfinite(self.fee_usd) or self.fee_usd < 0
                or not math.isfinite(self.wall_usd) or self.wall_usd <= 0):
            raise ConfirmationRefusal("fee/wall configuration is invalid")
        if self.wall_usd != WALL_USD:
            raise ConfirmationRefusal(
                "confirmation wall is fixed by the Entry V2 teacher contract")

    @property
    def offsets(self) -> tuple[int, ...]:
        from . import confirmation as confirmation_module
        scheduled = (training_offsets_seconds(self.max_delay_sec)
                     if self.snapshot_mode == "TRAINING"
                     else replay_offsets_seconds(self.max_delay_sec))
        if self.age_grid == "FULL":
            return scheduled
        keep = tuple(age for age in scheduled if age in confirmation_module.CORPUS_AGE_GRID_SECONDS)
        # A grid that silently loses an age it was asked for would build a
        # corpus missing rows nobody notices until a probe returns nothing.
        missing = set(confirmation_module.CORPUS_AGE_GRID_SECONDS) - set(scheduled)
        if missing:
            raise ConfirmationRefusal(
                f"corpus age grid asks for ages the {self.snapshot_mode} schedule "
                f"at max_delay_sec={self.max_delay_sec} does not contain: "
                f"{sorted(missing)}; expected a strict subset of {scheduled}")
        return keep

    @property
    def receipt_sha256(self) -> str:
        from . import confirmation as confirmation_module

        return C.object_sha256({"schema": SCHEMA, **asdict(self),
                                "discretionary_feature_schema":
                                    DISCRETIONARY_FEATURE_SCHEMA,
                                "implementation_sha256":
                                    confirmation_module.confirmation_implementation_hashes(),
                                "offsets": self.offsets,
                                "windows": FEATURE_WINDOWS_SECONDS})


@dataclass(frozen=True, slots=True)
class StreamConservationReceipt:
    asset: str
    trading_day: int
    event_pack_sha256: str
    event_count: int
    action_add_count: int
    action_cancel_count: int
    action_modify_count: int
    action_trade_count: int
    action_other_count: int
    buy_trade_volume: int
    sell_trade_volume: int
    unsigned_trade_volume: int
    total_trade_volume: int
    signed_trade_volume: int
    first_ts_recv_ns: int
    last_ts_recv_ns: int

    def validate(self) -> None:
        if self.asset not in C.ASSETS or self.event_count < 0:
            raise ConfirmationRefusal("stream conservation identity is invalid")
        counts = (self.action_add_count, self.action_cancel_count,
                  self.action_modify_count, self.action_trade_count,
                  self.action_other_count)
        if any(value < 0 for value in counts) or sum(counts) != self.event_count:
            raise ConfirmationRefusal("action census does not conserve event rows")
        if (min(self.buy_trade_volume, self.sell_trade_volume,
                self.unsigned_trade_volume, self.total_trade_volume) < 0
                or self.total_trade_volume != self.buy_trade_volume
                + self.sell_trade_volume + self.unsigned_trade_volume
                or self.signed_trade_volume != self.buy_trade_volume
                - self.sell_trade_volume):
            raise ConfirmationRefusal("trade-volume census does not conserve size")
        if self.event_count and not 0 < self.first_ts_recv_ns <= self.last_ts_recv_ns:
            raise ConfirmationRefusal("stream conservation clocks are invalid")

    @property
    def receipt_sha256(self) -> str:
        self.validate()
        return C.object_sha256({"schema": RECEIPT_SCHEMA, **asdict(self)})


@dataclass(frozen=True, slots=True)
class ConfirmationAnchor:
    opportunity_id: str
    series_id: str
    candidate_ids: tuple[str, ...]
    asset: str
    trading_day: int
    side: int
    phase: str
    phase_close_ts_ns: int
    snapshot_ts_ns: int
    event_cutoff: int
    entry_event_ordinal: int
    entry_availability_ts_ns: int
    entry_bid_px: int
    entry_ask_px: int
    entry_mid2: int
    entry_spread_usd: float
    frozen_cost_usd: float
    min_alert_age_sec: float
    max_alert_age_sec: float
    feature_receipt_sha256: str

    def __post_init__(self) -> None:
        if (not self.opportunity_id or not self.series_id or not self.candidate_ids
                or len(set(self.candidate_ids)) != len(self.candidate_ids)
                or self.asset not in C.ASSETS or self.side not in (-1, 1)):
            raise ConfirmationRefusal("confirmation anchor identity is invalid")
        if (self.entry_bid_px <= 0 or self.entry_ask_px <= self.entry_bid_px
                or self.entry_mid2 != self.entry_bid_px + self.entry_ask_px
                or self.event_cutoff <= 0
                or self.entry_event_ordinal >= self.event_cutoff
                or self.entry_availability_ts_ns >= self.snapshot_ts_ns
                or self.snapshot_ts_ns >= self.phase_close_ts_ns):
            raise ConfirmationRefusal("confirmation anchor market state is invalid")
        if (self.min_alert_age_sec < 0 or self.max_alert_age_sec < self.min_alert_age_sec
                or not math.isfinite(self.frozen_cost_usd)
                or self.frozen_cost_usd < 0):
            raise ConfirmationRefusal("confirmation anchor age/cost is invalid")


@dataclass(frozen=True, slots=True)
class ConfirmationOutcome:
    opportunity_id: str
    cert_close_usd: float
    mfe_usd: float
    mae_usd: float
    wall_hit: bool
    exit_ts_ns: int
    goal_grade: bool
    cost_applied_count: int = 1

    def __post_init__(self) -> None:
        if (not self.opportunity_id or self.exit_ts_ns <= 0
                or self.cost_applied_count != 1
                or any(not math.isfinite(value) for value in (
                    self.cert_close_usd, self.mfe_usd, self.mae_usd))
                or self.mfe_usd < 0 or self.mae_usd < 0
                or self.goal_grade != (self.cert_close_usd >= GOAL_USD)):
            raise ConfirmationRefusal("confirmation outcome is invalid")


def re_full_sha(value: object) -> bool:
    text = str(value)
    return len(text) == 64 and all(char in "0123456789abcdef" for char in text)


def _simple_object_sha256(value: Mapping[str, object]) -> str:
    """Fast canonical hash for flat, JSON-native per-snapshot identities."""

    raw = (json.dumps(value, sort_keys=True, separators=(",", ":"),
                      allow_nan=False) + "\n").encode()
    return hashlib.sha256(raw).hexdigest()


def _stream_receipt(pack: EventPack) -> StreamConservationReceipt:
    rows = np.asarray(pack.rows); action = rows["action"]; side = rows["side"]
    size = rows["size"].astype(np.int64); trade = action == ord("T")
    buy = trade & (side == ord("B")); sell = trade & (side == ord("A"))
    unsigned = trade & ~(buy | sell)
    receipt = StreamConservationReceipt(
        asset=pack.header.asset, trading_day=pack.header.d8,
        event_pack_sha256=str(pack.sidecar.get("event_pack_sha256")
                              or pack.sidecar.get("output_sha256") or C.file_sha256(pack.path)),
        event_count=len(rows), action_add_count=int((action == ord("A")).sum()),
        action_cancel_count=int((action == ord("C")).sum()),
        action_modify_count=int((action == ord("M")).sum()),
        action_trade_count=int(trade.sum()),
        action_other_count=int((~np.isin(action, (ord("A"), ord("C"),
                                                  ord("M"), ord("T")))).sum()),
        buy_trade_volume=int(size[buy].sum(dtype=np.int64)),
        sell_trade_volume=int(size[sell].sum(dtype=np.int64)),
        unsigned_trade_volume=int(size[unsigned].sum(dtype=np.int64)),
        total_trade_volume=int(size[trade].sum(dtype=np.int64)),
        signed_trade_volume=int(size[buy].sum(dtype=np.int64)
                                - size[sell].sum(dtype=np.int64)),
        first_ts_recv_ns=(0 if not len(rows) else int(rows["ts_recv_ns"][0])),
        last_ts_recv_ns=(0 if not len(rows) else int(rows["ts_recv_ns"][-1])),
    )
    receipt.validate(); return receipt
