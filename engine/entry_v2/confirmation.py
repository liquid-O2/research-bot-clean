"""Causal, full-stream tabular confirmation materialization for Entry V2.

Formation candidates are alerts, not compulsory entries.  This module scans
each authoritative QRE2EVT2 session once, accounts for every MBP-1 row, and
emits sequence-aware tabular state at later causal snapshots.  Labels are
recomputed from the snapshot's own entry BBO and cost; the formation teacher is
never copied onto a delayed decision.

The model-facing clock is always ``ts_recv``.  ``ts_event`` contributes only a
latency feature.  Snapshots occur on whole receive-second boundaries so every
subsecond event before the boundary is consumed while events exactly at the
boundary remain future.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from decimal import Decimal
import csv
import functools
import hashlib
import json
import math
import os
from pathlib import Path
from types import MappingProxyType
from typing import Iterable, Mapping, Sequence

import numpy as np

from . import common as C
from .corpus import (
    ASSET_MULTIPLIER, ASSET_RAW_TICK, FORECAST_FEATURE_FIELDS,
    ForecastProvider, ForecastQuery, SENTINEL_HIGH, _forecast_features,
)
from .context_sources import (
    CausalContextRepository, TABULAR_CONTEXT_FEATURE_NAMES,
    tabular_context_summary,
)
from .diagnostic_inputs import (
    CandidateTruthBinding,
    EventTruthColumns,
    UNITS_PER_USD,
    build_candidate_truth_bindings,
    build_event_truth_columns,
)
from .discretionary_features import (
    CausalDiscretionaryPlane,
    DISCRETIONARY_FEATURE_SCHEMA,
    DiscretionaryFeatureRefusal,
    LEVEL_ASSOCIATION_MODES,
    PriorSessionContext,
)
from .event_pack import EVENT_DTYPE, EventPack


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


@functools.lru_cache(maxsize=1)
def confirmation_implementation_hashes() -> Mapping[str, str]:
    """Exact source roster that can change materialized rows or labels."""

    directory = Path(__file__).resolve().parent
    files = {
        "common_contract": directory / "common.py",
        "confirmation": Path(__file__).resolve(),
        "confirmation_cache": directory / "confirmation_experiment.py",
        "context_pack": directory / "context_pack.py",
        "contracts": directory / "contracts.py",
        "discretionary_features": directory / "discretionary_features.py",
        "forecast_features": directory / "corpus.py",
        "slow_context": directory / "context_sources.py",
        "label_truth": directory / "diagnostic_inputs.py",
        "event_pack": directory / "event_pack.py",
        "availability_clock": directory.parent / "port_m2" / "availability.py",
    }
    return MappingProxyType({
        name: C.file_sha256(path) for name, path in files.items()
    })


def read_versioned_tsv(
    path: os.PathLike[str] | str, *, allow_empty: bool = False,
) -> tuple[Mapping[str, str], ...]:
    """Read a versioned TSV and fail closed on every malformed/empty input."""

    source = Path(path)
    C.guard_payload(source)
    try:
        with source.open("r", newline="") as handle:
            marker = handle.readline()
            if not marker.startswith("# "):
                raise ConfirmationRefusal(f"version marker missing: {source}")
            rows = tuple(MappingProxyType(dict(row)) for row in csv.DictReader(
                handle, delimiter="\t"))
    except (OSError, UnicodeError, csv.Error) as exc:
        raise ConfirmationRefusal(f"cannot read confirmation TSV: {source}") from exc
    if not rows and not allow_empty:
        raise ConfirmationRefusal(f"confirmation TSV is empty: {source}")
    return rows


@dataclass(frozen=True, slots=True)
class ConfirmationConfig:
    max_delay_sec: int = 600
    snapshot_mode: str = "TRAINING"
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
        return (training_offsets_seconds(self.max_delay_sec)
                if self.snapshot_mode == "TRAINING"
                else replay_offsets_seconds(self.max_delay_sec))

    @property
    def receipt_sha256(self) -> str:
        return C.object_sha256({"schema": SCHEMA, **asdict(self),
                                "discretionary_feature_schema":
                                    DISCRETIONARY_FEATURE_SCHEMA,
                                "implementation_sha256":
                                    confirmation_implementation_hashes(),
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


@dataclass(frozen=True, slots=True)
class ConfirmationDataset:
    feature_names: tuple[str, ...]
    features: np.ndarray
    opportunity_id: np.ndarray
    series_id: np.ndarray
    candidate_id: np.ndarray
    asset: np.ndarray
    day: np.ndarray
    side: np.ndarray
    phase: np.ndarray
    snapshot_ts_ns: np.ndarray
    phase_close_ts_ns: np.ndarray
    event_cutoff: np.ndarray
    entry_event_ordinal: np.ndarray
    entry_availability_ts_ns: np.ndarray
    entry_bid_px: np.ndarray
    entry_ask_px: np.ndarray
    entry_mid2: np.ndarray
    entry_spread_usd: np.ndarray
    frozen_cost_usd: np.ndarray
    candidate_count: np.ndarray
    min_alert_age_sec: np.ndarray
    max_alert_age_sec: np.ndarray
    cert_close_usd: np.ndarray
    mfe_usd: np.ndarray
    mae_usd: np.ndarray
    wall_hit: np.ndarray
    exit_ts_ns: np.ndarray
    feature_receipt_sha256: np.ndarray
    max_delay_sec: int
    snapshot_mode: str
    config_sha256: str
    source_receipts: tuple[str, ...]

    def validate(self) -> None:
        x = np.asarray(self.features)
        n = len(x)
        vectors = (
            self.opportunity_id, self.series_id, self.candidate_id, self.asset,
            self.day, self.side, self.phase, self.snapshot_ts_ns,
            self.phase_close_ts_ns, self.event_cutoff, self.entry_event_ordinal,
            self.entry_availability_ts_ns,
            self.entry_bid_px, self.entry_ask_px, self.entry_mid2,
            self.entry_spread_usd, self.frozen_cost_usd, self.candidate_count,
            self.min_alert_age_sec, self.max_alert_age_sec, self.cert_close_usd,
            self.mfe_usd, self.mae_usd, self.wall_hit, self.exit_ts_ns,
            self.feature_receipt_sha256,
        )
        if (x.ndim != 2 or x.shape[1] != len(self.feature_names)
                or any(np.asarray(value).shape != (n,) for value in vectors)
                or len(set(self.feature_names)) != len(self.feature_names)
                or len(set(np.asarray(self.opportunity_id, str).tolist())) != n
                or any(not value for value in np.asarray(self.candidate_id, str))
                or not np.all(np.isfinite(x))
                or not np.all(np.isfinite(self.cert_close_usd))
                or not np.all(np.isfinite(self.mfe_usd))
                or not np.all(np.isfinite(self.mae_usd))
                or not np.all(np.isin(self.side, (-1, 1)))
                or not np.all(np.isin(self.asset, C.ASSETS))
                or not np.all(np.asarray(self.candidate_count) == 1)
                or not np.all(np.asarray(self.event_cutoff) > 0)
                or not np.all(np.asarray(self.entry_event_ordinal)
                              < np.asarray(self.event_cutoff))
                or not np.all(np.asarray(self.entry_availability_ts_ns)
                              < np.asarray(self.snapshot_ts_ns))
                or not np.all(np.asarray(self.exit_ts_ns)
                              >= np.asarray(self.snapshot_ts_ns))
                or not np.all(np.asarray(self.entry_bid_px) > 0)
                or not np.all(np.asarray(self.entry_ask_px)
                              > np.asarray(self.entry_bid_px))
                or not np.array_equal(
                    np.asarray(self.entry_mid2),
                    np.asarray(self.entry_bid_px) + np.asarray(self.entry_ask_px))
                or not np.all(np.asarray(self.entry_spread_usd) >= 0)
                or not np.all(np.asarray(self.frozen_cost_usd) >= 0)
                or self.max_delay_sec not in (300, 600)
                or self.snapshot_mode not in {"TRAINING", "REPLAY"}
                or not re_full_sha(self.config_sha256)
                or any(not re_full_sha(value) for value in self.source_receipts)):
            raise ConfirmationRefusal("confirmation dataset schema is invalid")
        series_candidates: dict[str, set[str]] = {}
        for series, candidate in zip(
                np.asarray(self.series_id, str), np.asarray(self.candidate_id, str)):
            series_candidates.setdefault(series, set()).add(candidate)
        if any(len(values) != 1 for values in series_candidates.values()):
            raise ConfirmationRefusal("one confirmation series maps to multiple candidates")

    @property
    def representation_sha256(self) -> str:
        self.validate()
        digest = hashlib.sha256()
        digest.update("\n".join(self.feature_names).encode())
        digest.update(str(self.max_delay_sec).encode())
        digest.update(self.snapshot_mode.encode())
        digest.update(self.config_sha256.encode())
        digest.update("\n".join(self.source_receipts).encode())
        for value in (
            np.asarray(self.features, np.float32),
            np.asarray(self.opportunity_id, str), np.asarray(self.series_id, str),
            np.asarray(self.candidate_id, str), np.asarray(self.asset, str),
            np.asarray(self.day, np.int64), np.asarray(self.side, np.int8),
            np.asarray(self.phase, str), np.asarray(self.snapshot_ts_ns, np.int64),
            np.asarray(self.phase_close_ts_ns, np.int64),
            np.asarray(self.event_cutoff, np.int64),
            np.asarray(self.entry_event_ordinal, np.int64),
            np.asarray(self.entry_availability_ts_ns, np.int64),
            np.asarray(self.entry_bid_px, np.int64),
            np.asarray(self.entry_ask_px, np.int64),
            np.asarray(self.entry_mid2, np.int64),
            np.asarray(self.entry_spread_usd, np.float64),
            np.asarray(self.frozen_cost_usd, np.float64),
            np.asarray(self.candidate_count, np.int16),
            np.asarray(self.min_alert_age_sec, np.float32),
            np.asarray(self.max_alert_age_sec, np.float32),
            np.asarray(self.cert_close_usd, np.float64),
            np.asarray(self.mfe_usd, np.float64),
            np.asarray(self.mae_usd, np.float64),
            np.asarray(self.wall_hit, np.bool_), np.asarray(self.exit_ts_ns, np.int64),
            np.asarray(self.feature_receipt_sha256, str),
        ):
            array = np.ascontiguousarray(value)
            digest.update(str(array.dtype).encode())
            digest.update(repr(array.shape).encode())
            digest.update(array.tobytes())
        return digest.hexdigest()

    def subset(self, mask: np.ndarray) -> "ConfirmationDataset":
        selected = np.asarray(mask, bool)
        if selected.shape != (len(self.features),) or not selected.any():
            raise ConfirmationRefusal("confirmation subset is empty or malformed")
        names = {
            name: np.asarray(getattr(self, name))[selected]
            for name in (
                "features", "opportunity_id", "series_id", "candidate_id",
                "asset", "day", "side", "phase", "snapshot_ts_ns",
                "phase_close_ts_ns", "event_cutoff", "entry_event_ordinal",
                "entry_availability_ts_ns",
                "entry_bid_px", "entry_ask_px", "entry_mid2",
                "entry_spread_usd", "frozen_cost_usd", "candidate_count",
                "min_alert_age_sec", "max_alert_age_sec", "cert_close_usd",
                "mfe_usd", "mae_usd", "wall_hit", "exit_ts_ns",
                "feature_receipt_sha256",
            )
        }
        result = ConfirmationDataset(
            self.feature_names, **names, max_delay_sec=self.max_delay_sec,
            snapshot_mode=self.snapshot_mode, config_sha256=self.config_sha256,
            source_receipts=self.source_receipts)
        result.validate()
        return result
    def select_features(self, mask: np.ndarray) -> "ConfirmationDataset":
        selected = np.asarray(mask, bool)
        if (selected.shape != (len(self.feature_names),) or not selected.any()
                or selected.all()):
            raise ConfirmationRefusal("feature ablation mask is empty, full, or malformed")
        result = replace(
            self,
            feature_names=tuple(np.asarray(self.feature_names, str)[selected].tolist()),
            features=np.asarray(self.features)[:, selected],
        )
        result.validate()
        return result

    def save(self, path: os.PathLike[str] | str) -> str:
        self.validate()
        target = C.assert_workspace_output(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.suffix != ".npz":
            raise ConfirmationRefusal("confirmation dataset path must end in .npz")
        tmp = target.with_name(target.name + f".tmp.{os.getpid()}")
        with tmp.open("xb") as handle:
            np.savez_compressed(
                handle, feature_names=np.asarray(self.feature_names, str),
                features=np.asarray(self.features, np.float32),
                opportunity_id=np.asarray(self.opportunity_id, str),
                series_id=np.asarray(self.series_id, str),
                candidate_id=np.asarray(self.candidate_id, str),
                asset=np.asarray(self.asset, str),
                day=np.asarray(self.day, np.int64), side=np.asarray(self.side, np.int8),
                phase=np.asarray(self.phase, str),
                snapshot_ts_ns=np.asarray(self.snapshot_ts_ns, np.int64),
                phase_close_ts_ns=np.asarray(self.phase_close_ts_ns, np.int64),
                event_cutoff=np.asarray(self.event_cutoff, np.int64),
                entry_event_ordinal=np.asarray(self.entry_event_ordinal, np.int64),
                entry_availability_ts_ns=np.asarray(
                    self.entry_availability_ts_ns, np.int64),
                entry_bid_px=np.asarray(self.entry_bid_px, np.int64),
                entry_ask_px=np.asarray(self.entry_ask_px, np.int64),
                entry_mid2=np.asarray(self.entry_mid2, np.int64),
                entry_spread_usd=np.asarray(self.entry_spread_usd, np.float64),
                frozen_cost_usd=np.asarray(self.frozen_cost_usd, np.float64),
                candidate_count=np.asarray(self.candidate_count, np.int16),
                min_alert_age_sec=np.asarray(self.min_alert_age_sec, np.float32),
                max_alert_age_sec=np.asarray(self.max_alert_age_sec, np.float32),
                cert_close_usd=np.asarray(self.cert_close_usd, np.float64),
                mfe_usd=np.asarray(self.mfe_usd, np.float64),
                mae_usd=np.asarray(self.mae_usd, np.float64),
                wall_hit=np.asarray(self.wall_hit, np.bool_),
                exit_ts_ns=np.asarray(self.exit_ts_ns, np.int64),
                feature_receipt_sha256=np.asarray(self.feature_receipt_sha256, str),
                max_delay_sec=np.asarray([self.max_delay_sec], np.int16),
                snapshot_mode=np.asarray([self.snapshot_mode], str),
                config_sha256=np.asarray([self.config_sha256], str),
                source_receipts=np.asarray(self.source_receipts, str),
                representation_sha256=np.asarray([self.representation_sha256], str),
            )
            handle.flush(); os.fsync(handle.fileno())
        os.replace(tmp, target)
        return C.file_sha256(target)

    @classmethod
    def load(cls, path: os.PathLike[str] | str) -> "ConfirmationDataset":
        source = Path(path)
        C.guard_payload(source)
        try:
            with np.load(source, allow_pickle=False) as z:
                result = cls(
                    feature_names=tuple(z["feature_names"].astype(str).tolist()),
                    features=z["features"], opportunity_id=z["opportunity_id"],
                    series_id=z["series_id"], candidate_id=z["candidate_id"],
                    asset=z["asset"], day=z["day"], side=z["side"],
                    phase=z["phase"], snapshot_ts_ns=z["snapshot_ts_ns"],
                    phase_close_ts_ns=z["phase_close_ts_ns"],
                    event_cutoff=z["event_cutoff"],
                    entry_event_ordinal=z["entry_event_ordinal"],
                    entry_availability_ts_ns=z["entry_availability_ts_ns"],
                    entry_bid_px=z["entry_bid_px"], entry_ask_px=z["entry_ask_px"],
                    entry_mid2=z["entry_mid2"],
                    entry_spread_usd=z["entry_spread_usd"],
                    frozen_cost_usd=z["frozen_cost_usd"],
                    candidate_count=z["candidate_count"],
                    min_alert_age_sec=z["min_alert_age_sec"],
                    max_alert_age_sec=z["max_alert_age_sec"],
                    cert_close_usd=z["cert_close_usd"], mfe_usd=z["mfe_usd"],
                    mae_usd=z["mae_usd"], wall_hit=z["wall_hit"],
                    exit_ts_ns=z["exit_ts_ns"],
                    feature_receipt_sha256=z["feature_receipt_sha256"],
                    max_delay_sec=int(z["max_delay_sec"][0]),
                    snapshot_mode=str(z["snapshot_mode"][0]),
                    config_sha256=str(z["config_sha256"][0]),
                    source_receipts=tuple(z["source_receipts"].astype(str).tolist()))
                expected = str(z["representation_sha256"][0])
        except (OSError, ValueError, KeyError) as exc:
            raise ConfirmationRefusal("cannot strict-load confirmation dataset") from exc
        result.validate()
        if result.representation_sha256 != expected:
            raise ConfirmationRefusal("confirmation dataset representation hash differs")
        return result


@dataclass(frozen=True, slots=True)
class ConfirmationOpportunitySet:
    """Lightweight every-second outcome universe for the exact ceiling."""

    opportunity_id: np.ndarray
    series_id: np.ndarray
    candidate_id: np.ndarray
    asset: np.ndarray
    day: np.ndarray
    side: np.ndarray
    phase: np.ndarray
    snapshot_ts_ns: np.ndarray
    phase_close_ts_ns: np.ndarray
    event_cutoff: np.ndarray
    entry_event_ordinal: np.ndarray
    entry_availability_ts_ns: np.ndarray
    cert_close_usd: np.ndarray
    mfe_usd: np.ndarray
    mae_usd: np.ndarray
    wall_hit: np.ndarray
    exit_ts_ns: np.ndarray
    feature_receipt_sha256: np.ndarray
    max_delay_sec: int
    snapshot_mode: str
    config_sha256: str
    source_receipts: tuple[str, ...]

    def validate(self) -> None:
        n = len(self.opportunity_id)
        vectors = tuple(getattr(self, name) for name in (
            "series_id", "candidate_id", "asset", "day", "side", "phase",
            "snapshot_ts_ns", "phase_close_ts_ns", "event_cutoff",
            "entry_event_ordinal", "entry_availability_ts_ns", "cert_close_usd",
            "mfe_usd", "mae_usd", "wall_hit", "exit_ts_ns",
            "feature_receipt_sha256"))
        if (n == 0 or any(np.asarray(value).shape != (n,) for value in vectors)
                or len(set(np.asarray(self.opportunity_id, str).tolist())) != n
                or not np.all(np.isin(self.asset, C.ASSETS))
                or not np.all(np.isin(self.side, (-1, 1)))
                or not np.all(np.asarray(self.event_cutoff) > 0)
                or not np.all(np.asarray(self.entry_event_ordinal)
                              < np.asarray(self.event_cutoff))
                or not np.all(np.asarray(self.entry_availability_ts_ns)
                              < np.asarray(self.snapshot_ts_ns))
                or not np.all(np.asarray(self.exit_ts_ns)
                              >= np.asarray(self.snapshot_ts_ns))
                or not np.all(np.isfinite(self.cert_close_usd))
                or not np.all(np.isfinite(self.mfe_usd))
                or not np.all(np.isfinite(self.mae_usd))
                or self.max_delay_sec not in (300, 600)
                or self.snapshot_mode != "REPLAY"
                or not re_full_sha(self.config_sha256)
                or any(not re_full_sha(value) for value in self.source_receipts)):
            raise ConfirmationRefusal("confirmation opportunity universe is invalid")
        mapping: dict[str, set[str]] = {}
        for series, candidate in zip(self.series_id, self.candidate_id):
            mapping.setdefault(str(series), set()).add(str(candidate))
        if any(len(value) != 1 for value in mapping.values()):
            raise ConfirmationRefusal("opportunity series maps to multiple candidates")

    @property
    def representation_sha256(self) -> str:
        self.validate()
        digest = hashlib.sha256()
        digest.update(str(self.max_delay_sec).encode())
        digest.update(self.snapshot_mode.encode())
        digest.update(self.config_sha256.encode())
        digest.update("\n".join(self.source_receipts).encode())
        for name in (
            "opportunity_id", "series_id", "candidate_id", "asset", "day",
            "side", "phase", "snapshot_ts_ns", "phase_close_ts_ns",
            "event_cutoff", "entry_event_ordinal", "entry_availability_ts_ns",
            "cert_close_usd", "mfe_usd", "mae_usd", "wall_hit", "exit_ts_ns",
            "feature_receipt_sha256",
        ):
            value = np.ascontiguousarray(getattr(self, name))
            digest.update(str(value.dtype).encode())
            digest.update(repr(value.shape).encode())
            digest.update(value.tobytes())
        return digest.hexdigest()

    def save(self, path: os.PathLike[str] | str) -> str:
        self.validate()
        target = C.assert_workspace_output(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.suffix != ".npz":
            raise ConfirmationRefusal("opportunity path must end in .npz")
        tmp = target.with_name(target.name + f".tmp.{os.getpid()}")
        payload = {name: np.asarray(getattr(self, name)) for name in (
            "opportunity_id", "series_id", "candidate_id", "asset", "day",
            "side", "phase", "snapshot_ts_ns", "phase_close_ts_ns",
            "event_cutoff", "entry_event_ordinal", "entry_availability_ts_ns",
            "cert_close_usd", "mfe_usd", "mae_usd", "wall_hit", "exit_ts_ns",
            "feature_receipt_sha256")}
        with tmp.open("xb") as handle:
            np.savez_compressed(
                handle, **payload,
                max_delay_sec=np.asarray([self.max_delay_sec], np.int16),
                snapshot_mode=np.asarray([self.snapshot_mode], str),
                config_sha256=np.asarray([self.config_sha256], str),
                source_receipts=np.asarray(self.source_receipts, str),
                representation_sha256=np.asarray(
                    [self.representation_sha256], str))
            handle.flush(); os.fsync(handle.fileno())
        os.replace(tmp, target)
        return C.file_sha256(target)

    @classmethod
    def load(cls, path: os.PathLike[str] | str) -> "ConfirmationOpportunitySet":
        source = Path(path); C.guard_payload(source)
        fields = (
            "opportunity_id", "series_id", "candidate_id", "asset", "day",
            "side", "phase", "snapshot_ts_ns", "phase_close_ts_ns",
            "event_cutoff", "entry_event_ordinal", "entry_availability_ts_ns",
            "cert_close_usd", "mfe_usd", "mae_usd", "wall_hit", "exit_ts_ns",
            "feature_receipt_sha256")
        try:
            with np.load(source, allow_pickle=False) as values:
                result = cls(
                    **{name: values[name] for name in fields},
                    max_delay_sec=int(values["max_delay_sec"][0]),
                    snapshot_mode=str(values["snapshot_mode"][0]),
                    config_sha256=str(values["config_sha256"][0]),
                    source_receipts=tuple(
                        values["source_receipts"].astype(str).tolist()))
                expected = str(values["representation_sha256"][0])
        except (OSError, ValueError, KeyError) as exc:
            raise ConfirmationRefusal("cannot strict-load opportunity universe") from exc
        result.validate()
        if result.representation_sha256 != expected:
            raise ConfirmationRefusal("opportunity universe representation hash differs")
        return result


def re_full_sha(value: object) -> bool:
    text = str(value)
    return len(text) == 64 and all(char in "0123456789abcdef" for char in text)


def _simple_object_sha256(value: Mapping[str, object]) -> str:
    """Fast canonical hash for flat, JSON-native per-snapshot identities."""

    raw = (json.dumps(value, sort_keys=True, separators=(",", ":"),
                      allow_nan=False) + "\n").encode()
    return hashlib.sha256(raw).hexdigest()


class _RangeIndex:
    """Segment-tree extrema and first-threshold queries over economic mids."""

    def __init__(self, values: np.ndarray) -> None:
        source = np.asarray(values, np.int64)
        size = 1
        while size < len(source):
            size *= 2
        self.length = len(source); self.size = size
        self.minimum = np.full(2 * size, np.iinfo(np.int64).max, np.int64)
        self.maximum = np.full(2 * size, np.iinfo(np.int64).min, np.int64)
        self.minimum[size:size + len(source)] = source
        self.maximum[size:size + len(source)] = source
        for node in range(size - 1, 0, -1):
            self.minimum[node] = min(self.minimum[2 * node], self.minimum[2 * node + 1])
            self.maximum[node] = max(self.maximum[2 * node], self.maximum[2 * node + 1])

    def extrema(self, left: int, right: int) -> tuple[int, int]:
        if not 0 <= left < right <= self.length:
            raise ConfirmationRefusal("range-extrema query is empty/outside")
        low = np.iinfo(np.int64).max; high = np.iinfo(np.int64).min
        a, b = left + self.size, right + self.size
        while a < b:
            if a & 1:
                low = min(low, int(self.minimum[a])); high = max(high, int(self.maximum[a])); a += 1
            if b & 1:
                b -= 1; low = min(low, int(self.minimum[b])); high = max(high, int(self.maximum[b]))
            a //= 2; b //= 2
        return int(low), int(high)

    def extrema_many(
        self, left: np.ndarray, right: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Vectorized half-open extrema for many independent ranges."""

        left = np.asarray(left, np.int64); right = np.asarray(right, np.int64)
        if (left.shape != right.shape or np.any(left < 0)
                or np.any(left >= right) or np.any(right > self.length)):
            raise ConfirmationRefusal("batched range-extrema query is invalid")
        a = left + self.size; b = right + self.size
        low = np.full(left.shape, np.iinfo(np.int64).max, np.int64)
        high = np.full(left.shape, np.iinfo(np.int64).min, np.int64)
        while np.any(a < b):
            take_a = (a < b) & ((a & 1) == 1)
            if np.any(take_a):
                low[take_a] = np.minimum(low[take_a], self.minimum[a[take_a]])
                high[take_a] = np.maximum(high[take_a], self.maximum[a[take_a]])
                a[take_a] += 1
            take_b = (a < b) & ((b & 1) == 1)
            if np.any(take_b):
                b[take_b] -= 1
                low[take_b] = np.minimum(low[take_b], self.minimum[b[take_b]])
                high[take_b] = np.maximum(high[take_b], self.maximum[b[take_b]])
            a //= 2; b //= 2
        return low, high

    def first_many(
        self, left: np.ndarray, right: np.ndarray, threshold: np.ndarray,
        *, use_min: bool,
    ) -> np.ndarray:
        """First dynamic threshold crossing for each half-open range."""

        left = np.asarray(left, np.int64); right = np.asarray(right, np.int64)
        threshold = np.asarray(threshold, np.int64)
        if left.shape != right.shape or left.shape != threshold.shape:
            raise ConfirmationRefusal("batched threshold query shapes differ")
        low_all, high_all = self.extrema_many(left, right)
        qualifies = (low_all <= threshold if use_min else high_all >= threshold)
        output = np.full(left.shape, -1, np.int64)
        if not np.any(qualifies):
            return output
        starts = left[qualifies]
        lo = starts.copy(); hi = right[qualifies] - 1
        limits = threshold[qualifies]
        while np.any(lo < hi):
            mid = (lo + hi) // 2
            lows, highs = self.extrema_many(starts, mid + 1)
            hit = lows <= limits if use_min else highs >= limits
            hi = np.where(hit, mid, hi)
            lo = np.where(hit, lo, mid + 1)
        output[qualifies] = lo
        return output

    def first_leq(self, left: int, right: int, threshold: int) -> int | None:
        return self._first(left, right, threshold, use_min=True)

    def first_geq(self, left: int, right: int, threshold: int) -> int | None:
        return self._first(left, right, threshold, use_min=False)

    def _first(self, left: int, right: int, threshold: int, *, use_min: bool) -> int | None:
        tree = self.minimum if use_min else self.maximum
        def qualifies(node: int) -> bool:
            return int(tree[node]) <= threshold if use_min else int(tree[node]) >= threshold
        def visit(node: int, lo: int, hi: int) -> int | None:
            if hi <= left or right <= lo or not qualifies(node):
                return None
            if node >= self.size:
                index = node - self.size
                return index if index < self.length else None
            mid = (lo + hi) // 2
            found = visit(node * 2, lo, mid)
            return found if found is not None else visit(node * 2 + 1, mid, hi)
        return visit(1, 0, self.size)


class _OutcomeIndex:
    def __init__(self, rows: np.ndarray, columns: Mapping[str, np.ndarray],
                 asset: str) -> None:
        economic = np.asarray(columns["trusted_economic"], bool)
        self.raw_rows = rows
        self.raw_ts = rows["ts_recv_ns"]
        self.raw_generation = np.asarray(columns["generation"], np.uint32)
        self.indices = np.flatnonzero(economic)
        self.ts = self.raw_ts[self.indices]
        self.mid2 = np.asarray(columns["mid2"], np.int64)[self.indices]
        self.generation = self.raw_generation[self.indices]
        self.multiplier = int(ASSET_MULTIPLIER[asset])
        self.factor = 0.5e-9 * self.multiplier
        self.range = _RangeIndex(self.mid2)
        self.generation_end = np.empty(len(self.generation), np.int64)
        boundaries = np.r_[0, np.flatnonzero(
            self.generation[1:] != self.generation[:-1]) + 1,
            len(self.generation)]
        for left, right in zip(boundaries[:-1], boundaries[1:]):
            self.generation_end[left:right] = right

    def current(self, snapshot_ts_ns: int) -> tuple[int, int, int, int, int] | None:
        position = int(np.searchsorted(
            self.ts, np.uint64(snapshot_ts_ns), side="left")) - 1
        if position < 0:
            return None
        raw_index = int(self.indices[position])
        row = self.raw_rows[raw_index]
        return (position, raw_index, int(row["bid_px"]), int(row["ask_px"]),
                int(self.mid2[position]))

    def generation_at_snapshot(self, snapshot_ts_ns: int) -> int | None:
        """Teacher generation at the strict raw cutoff.

        Events exactly at the snapshot are future.  The legacy teacher anchors
        generation from the first suffix row (``event_cutoff``), rather than
        silently carrying the last prefix generation through a reset.
        """

        cutoff = int(np.searchsorted(
            self.raw_ts, np.uint64(snapshot_ts_ns), side="left"))
        if cutoff < len(self.raw_generation):
            return int(self.raw_generation[cutoff])
        if cutoff:
            return int(self.raw_generation[cutoff - 1])
        return None

    def outcome(self, *, opportunity_id: str, snapshot_ts_ns: int,
                side: int, phase_close_ts_ns: int, entry_mid2: int,
                frozen_cost_usd: float, generation: int | None = None,
                ) -> ConfirmationOutcome | None:
        start = int(np.searchsorted(self.ts, np.uint64(snapshot_ts_ns), side="left"))
        end = int(np.searchsorted(self.ts, np.uint64(phase_close_ts_ns), side="right"))
        if start >= end:
            return None
        expected_generation = (int(self.generation[start]) if generation is None
                               else int(generation))
        local = np.flatnonzero(self.generation[start:end] != expected_generation)
        if len(local):
            end = start + int(local[0])
        if start >= end:
            return None

        # Find the first exact wall crossing without scanning the suffix.  Raw
        # mids are integer ticks; the derived boundary is widened by one raw
        # unit and the returned point is verified with the teacher arithmetic.
        if side > 0:
            boundary = math.floor(entry_mid2 + (-WALL_USD + frozen_cost_usd) / self.factor)
            wall = self.range.first_leq(start, end, boundary)
        else:
            boundary = math.ceil(entry_mid2 + (WALL_USD - frozen_cost_usd) / self.factor)
            wall = self.range.first_geq(start, end, boundary)
        exit_position = end - 1 if wall is None else int(wall)
        exit_mid = int(self.mid2[exit_position])
        cert = side * (exit_mid - entry_mid2) * self.factor - frozen_cost_usd
        if wall is not None and cert > -WALL_USD + 1e-9:
            raise ConfirmationRefusal("segment wall query did not reach exact wall")
        low, high = self.range.extrema(start, exit_position + 1)
        values = (
            side * (low - entry_mid2) * self.factor - frozen_cost_usd,
            side * (high - entry_mid2) * self.factor - frozen_cost_usd,
        )
        return ConfirmationOutcome(
            opportunity_id=opportunity_id,
            cert_close_usd=float(cert),
            mfe_usd=max(0.0, max(values)),
            mae_usd=max(0.0, -min(values)),
            wall_hit=wall is not None,
            exit_ts_ns=int(self.ts[exit_position]),
            goal_grade=bool(cert >= GOAL_USD),
        )

    def outcomes_many(
        self, *, snapshot_ts_ns: np.ndarray, side: int,
        phase_close_ts_ns: int, entry_mid2: np.ndarray,
        frozen_cost_usd: np.ndarray,
    ) -> Mapping[str, np.ndarray]:
        """Exact teacher outcomes for a batch of causal snapshot entries."""

        snapshots = np.asarray(snapshot_ts_ns, np.int64)
        entries = np.asarray(entry_mid2, np.int64)
        costs = np.asarray(frozen_cost_usd, np.float64)
        if (side not in (-1, 1) or snapshots.ndim != 1
                or entries.shape != snapshots.shape or costs.shape != snapshots.shape
                or not len(snapshots)):
            raise ConfirmationRefusal("batched outcome inputs are invalid")
        starts_all = np.searchsorted(
            self.ts, snapshots.astype(np.uint64), side="left")
        phase_end = int(np.searchsorted(
            self.ts, np.uint64(phase_close_ts_ns), side="right"))
        raw_cutoff_all = np.searchsorted(
            self.raw_ts, snapshots.astype(np.uint64), side="left")
        keep = np.flatnonzero(starts_all < phase_end)
        if not len(keep):
            raise ConfirmationRefusal("batched outcome has no certifiable suffix")
        starts = starts_all[keep]
        raw_generation_index = np.minimum(
            raw_cutoff_all[keep], len(self.raw_generation) - 1)
        expected_generation = self.raw_generation[raw_generation_index]
        ends = np.minimum(phase_end, self.generation_end[starts])
        valid = ((self.generation[starts] == expected_generation)
                 & (starts < ends))
        keep = keep[valid]; starts = starts[valid]; ends = ends[valid]
        if not len(keep):
            raise ConfirmationRefusal("batched outcome has no same-generation suffix")
        entries = entries[keep]; costs = costs[keep]
        if side > 0:
            threshold = np.floor(entries + (-WALL_USD + costs) / self.factor)
            wall = self.range.first_many(
                starts, ends, threshold.astype(np.int64), use_min=True)
        else:
            threshold = np.ceil(entries + (WALL_USD - costs) / self.factor)
            wall = self.range.first_many(
                starts, ends, threshold.astype(np.int64), use_min=False)
        exit_position = np.where(wall < 0, ends - 1, wall).astype(np.int64)
        exit_mid = self.mid2[exit_position]
        cert = side * (exit_mid - entries) * self.factor - costs
        if np.any((wall >= 0) & (cert > -WALL_USD + 1e-9)):
            raise ConfirmationRefusal("batched wall query did not reach exact wall")
        low, high = self.range.extrema_many(starts, exit_position + 1)
        low_value = side * (low - entries) * self.factor - costs
        high_value = side * (high - entries) * self.factor - costs
        return MappingProxyType({
            "input_index": keep.astype(np.int64),
            "cert_close_usd": cert.astype(np.float64),
            "mfe_usd": np.maximum(0.0, np.maximum(low_value, high_value)),
            "mae_usd": np.maximum(0.0, -np.minimum(low_value, high_value)),
            "wall_hit": wall >= 0,
            "exit_ts_ns": self.ts[exit_position].astype(np.int64),
        })


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


def stream_conservation_receipt(pack: EventPack) -> StreamConservationReceipt:
    """Public fail-closed event census used by empty-session corpus handling."""

    return _stream_receipt(pack)


def _ceil_second(value: int) -> int:
    return ((int(value) + NANOS_PER_SECOND - 1) // NANOS_PER_SECOND) * NANOS_PER_SECOND


def _binding_groups(bindings: Sequence[CandidateTruthBinding]
                    ) -> Mapping[tuple[object, ...], tuple[CandidateTruthBinding, ...]]:
    groups: dict[tuple[object, ...], tuple[CandidateTruthBinding, ...]] = {}
    for row in bindings:
        if row.compliance_status != "CLEAR" or row.teacher_status != "READY":
            continue
        # A confirmation process belongs to one native candidate.  Collapsing
        # every same-side alert in a phase into one series would allow only one
        # stopping decision for the entire phase and would silently destroy the
        # authorized sequential re-entry universe.  Replay—not materialization—
        # resolves overlapping alerts and same-timestamp competition.
        key = (row.asset, row.trading_day, row.side, row.phase,
               row.phase_open_ts_ns, row.phase_close_ts_ns,
               row.sane_ceiling_units, row.multiplier, row.candidate_id)
        groups[key] = (row,)
    return MappingProxyType(groups)


def learnable_confirmation_count(
    candidates: Iterable[Mapping[str, str]],
    teachers: Iterable[Mapping[str, str]],
) -> int:
    """Count causal candidate rows eligible for confirmation supervision."""

    bindings = build_candidate_truth_bindings(tuple(candidates), tuple(teachers))
    return sum(row.compliance_status == "CLEAR" and row.teacher_status == "READY"
               for row in bindings)


def _verify_formation_teachers(
    bindings: Sequence[CandidateTruthBinding], truth: EventTruthColumns,
    rows: np.ndarray, asset: str,
) -> str:
    checked: list[tuple[object, ...]] = []
    indices: dict[tuple[int, int, int, int], _OutcomeIndex] = {}
    for row in bindings:
        if row.compliance_status != "CLEAR" or row.teacher_status != "READY":
            continue
        index = indices.get(row.truth_quality_key)
        if index is None:
            index = _OutcomeIndex(rows, truth.candidate_columns(row), asset)
            indices[row.truth_quality_key] = index
        prefix = index.current(row.decision_ts_ns)
        if prefix is None:
            raise ConfirmationRefusal("formation teacher has no trusted prefix BBO")
        generation = index.generation_at_snapshot(row.decision_ts_ns)
        if generation is None:
            raise ConfirmationRefusal("formation teacher has no suffix generation")
        outcome = index.outcome(
            opportunity_id=row.candidate_id,
            snapshot_ts_ns=row.decision_ts_ns, side=row.side,
            phase_close_ts_ns=row.phase_close_ts_ns,
            entry_mid2=row.entry_mid2,
            frozen_cost_usd=float(Decimal(row.frozen_cost_units) / UNITS_PER_USD),
            generation=generation,
        )
        if outcome is None:
            raise ConfirmationRefusal("formation teacher has no certifiable suffix")
        expected = (
            float(Decimal(row.cert_close_units) / UNITS_PER_USD),
            float(Decimal(row.mfe_units) / UNITS_PER_USD),
            float(Decimal(row.mae_units) / UNITS_PER_USD),
            bool(row.wall_hit), int(row.exit_ts_ns),
        )
        observed = (outcome.cert_close_usd, outcome.mfe_usd, outcome.mae_usd,
                    outcome.wall_hit, outcome.exit_ts_ns)
        if (any(abs(float(a) - float(b)) > 1e-8
                for a, b in zip(observed[:3], expected[:3]))
                or observed[3:] != expected[3:]):
            raise ConfirmationRefusal(
                f"formation teacher parity failed for {row.candidate_id}: "
                f"observed={observed} expected={expected}")
        checked.append((row.candidate_id, *observed))
    if not checked:
        raise ConfirmationRefusal("no CLEAR/READY formation teacher rows")
    return C.object_sha256({"schema": "QRE2CONFFORMPARITY1", "rows": checked})


def materialize_confirmation_opportunity_session(
    pack: EventPack,
    candidates: Iterable[Mapping[str, str]],
    teachers: Iterable[Mapping[str, str]],
    *, max_delay_sec: int = 300,
) -> ConfirmationOpportunitySet:
    """Materialize every delayed label without paying to build model features."""

    config = ConfirmationConfig(
        max_delay_sec=max_delay_sec, snapshot_mode="REPLAY")
    candidate_rows = tuple(candidates); teacher_rows = tuple(teachers)
    bindings = build_candidate_truth_bindings(candidate_rows, teacher_rows)
    if ({row.asset for row in bindings} != {pack.header.asset}
            or {row.trading_day for row in bindings} != {pack.header.d8}):
        raise ConfirmationRefusal("opportunity bindings do not match event session")
    raw = np.asarray(pack.rows)
    truth = build_event_truth_columns(raw, pack.header.asset, bindings)
    conservation = _stream_receipt(pack)
    formation_parity = _verify_formation_teachers(
        bindings, truth, raw, pack.header.asset)
    groups = _binding_groups(bindings)
    if not groups:
        raise ConfirmationRefusal("session has no CLEAR/READY opportunities")
    indices: dict[tuple[int, int, int, int], _OutcomeIndex] = {}
    fields: dict[str, list[np.ndarray]] = {name: [] for name in (
        "opportunity_id", "series_id", "candidate_id", "asset", "day", "side",
        "phase", "snapshot_ts_ns", "phase_close_ts_ns", "event_cutoff",
        "entry_event_ordinal", "entry_availability_ts_ns", "cert_close_usd",
        "mfe_usd", "mae_usd", "wall_hit", "exit_ts_ns",
        "feature_receipt_sha256")}
    for key, members in sorted(groups.items(), key=lambda item: repr(item[0])):
        (_asset, _day, side, phase, _phase_open, phase_close,
         _ceiling, _multiplier, _native_candidate_id) = key
        member = members[0]
        quality_key = member.truth_quality_key
        index = indices.get(quality_key)
        if index is None:
            index = _OutcomeIndex(
                raw, truth.candidate_columns(member), pack.header.asset)
            indices[quality_key] = index
        series_id = C.object_sha256({"schema": "QRE2CONFSERIES1", "key": key})
        base = _ceil_second(member.decision_ts_ns)
        expiry = member.decision_ts_ns + max_delay_sec * NANOS_PER_SECOND
        last = min(expiry, member.phase_close_ts_ns - 1)
        if base > last:
            continue
        snapshots = np.arange(
            base, last + 1, NANOS_PER_SECOND, dtype=np.int64)
        positions = np.searchsorted(
            index.ts, snapshots.astype(np.uint64), side="left") - 1
        visible = positions >= 0
        snapshots = snapshots[visible]; positions = positions[visible]
        if not len(snapshots):
            continue
        raw_indices = index.indices[positions]
        bid = raw["bid_px"][raw_indices].astype(np.int64)
        ask = raw["ask_px"][raw_indices].astype(np.int64)
        mid2 = index.mid2[positions]
        costs = ((ask - bid) * 1e-9 * ASSET_MULTIPLIER[pack.header.asset]
                 + config.fee_usd)
        cutoff = np.searchsorted(
            raw["ts_recv_ns"], snapshots.astype(np.uint64), side="left").astype(np.int64)
        outcomes = index.outcomes_many(
            snapshot_ts_ns=snapshots, side=int(side),
            phase_close_ts_ns=int(phase_close), entry_mid2=mid2,
            frozen_cost_usd=costs)
        keep = np.asarray(outcomes["input_index"], np.int64)
        snapshots = snapshots[keep]; positions = positions[keep]
        raw_indices = raw_indices[keep]; cutoff = cutoff[keep]
        opportunity = np.asarray([_simple_object_sha256({
            "schema": SCHEMA, "series_id": series_id,
            "snapshot_ts_ns": int(snapshot),
            "candidate_ids": (member.candidate_id,),
        }) for snapshot in snapshots], str)
        receipts = np.asarray([_simple_object_sha256({
            "schema": "QRE2CONFOPP1", "stream": conservation.receipt_sha256,
            "formation_parity": formation_parity,
            "config": config.receipt_sha256, "series_id": series_id,
            "snapshot_ts_ns": int(snapshot), "event_cutoff": int(cut),
            "candidate_id": member.candidate_id,
        }) for snapshot, cut in zip(snapshots, cutoff)], str)
        n = len(snapshots)
        values = {
            "opportunity_id": opportunity,
            "series_id": np.full(n, series_id),
            "candidate_id": np.full(n, member.candidate_id),
            "asset": np.full(n, pack.header.asset),
            "day": np.full(n, pack.header.d8, np.int64),
            "side": np.full(n, side, np.int8),
            "phase": np.full(n, str(phase)),
            "snapshot_ts_ns": snapshots,
            "phase_close_ts_ns": np.full(n, phase_close, np.int64),
            "event_cutoff": cutoff,
            "entry_event_ordinal": raw_indices.astype(np.int64),
            "entry_availability_ts_ns": raw["ts_recv_ns"][raw_indices].astype(np.int64),
            "feature_receipt_sha256": receipts,
            **{name: value for name, value in outcomes.items()
               if name != "input_index"},
        }
        for name, value in values.items():
            fields[name].append(np.asarray(value))
    if not fields["opportunity_id"]:
        raise ConfirmationRefusal("opportunity materialization produced no rows")
    joined = {name: np.concatenate(value) for name, value in fields.items()}
    result = ConfirmationOpportunitySet(
        **joined,
        max_delay_sec=max_delay_sec, snapshot_mode="REPLAY",
        config_sha256=config.receipt_sha256,
        source_receipts=(conservation.receipt_sha256, formation_parity),
    )
    result.validate(); return result


def combine_confirmation_opportunity_sets(
    datasets: Sequence[ConfirmationOpportunitySet],
) -> ConfirmationOpportunitySet:
    if not datasets:
        raise ConfirmationRefusal("cannot combine an empty opportunity list")
    for dataset in datasets:
        dataset.validate()
    first = datasets[0]
    if any((row.max_delay_sec, row.snapshot_mode, row.config_sha256)
           != (first.max_delay_sec, first.snapshot_mode, first.config_sha256)
           for row in datasets):
        raise ConfirmationRefusal("opportunity universes have incompatible configs")
    fields = (
        "opportunity_id", "series_id", "candidate_id", "asset", "day", "side",
        "phase", "snapshot_ts_ns", "phase_close_ts_ns", "event_cutoff",
        "entry_event_ordinal", "entry_availability_ts_ns", "cert_close_usd",
        "mfe_usd", "mae_usd", "wall_hit", "exit_ts_ns",
        "feature_receipt_sha256",
    )
    values = {name: np.concatenate([
        np.asarray(getattr(row, name)) for row in datasets]) for name in fields}
    result = ConfirmationOpportunitySet(
        **values, max_delay_sec=first.max_delay_sec,
        snapshot_mode=first.snapshot_mode, config_sha256=first.config_sha256,
        source_receipts=tuple(receipt for row in datasets
                              for receipt in row.source_receipts))
    result.validate(); return result


def materialize_confirmation_session(
    pack: EventPack,
    candidates: Iterable[Mapping[str, str]],
    teachers: Iterable[Mapping[str, str]],
    *, config: ConfirmationConfig = ConfirmationConfig(),
    forecast_provider: ForecastProvider | None = None,
    prior_session_context: PriorSessionContext | None = None,
    context_repository: CausalContextRepository | None = None,
    extra_snapshot_ts_by_candidate: Mapping[str, Sequence[int]] | None = None,
    compute_outcomes: bool = True,
) -> ConfirmationDataset:
    """Materialize one authoritative session into causal tabular snapshots.

    ``extra_snapshot_ts_by_candidate`` is the recovery lane's sparse-clock
    enrichment hook.  It uses this exact feature implementation for Oracle,
    adjacent, and OOF policy-change seconds; it never changes the base clock
    or exposes why a timestamp was requested to the feature implementation.
    With ``compute_outcomes=False`` this same causal implementation is usable
    for runtime/rollout evaluation: future suffixes are never queried and the
    returned outcome slots are typed zero placeholders stripped at the
    ``CausalFeatureShard`` boundary.
    """

    candidate_rows = tuple(candidates); teacher_rows = tuple(teachers)
    if not isinstance(compute_outcomes, bool):
        raise ConfirmationRefusal("compute_outcomes must be boolean")
    if config.require_forecast_context and forecast_provider is None:
        raise ConfirmationRefusal("required forward-vol context is unavailable")
    if config.require_slow_context and context_repository is None:
        raise ConfirmationRefusal("required strict-prior slow context is unavailable")
    if (context_repository is not None
            and context_repository.asset != pack.header.asset):
        raise ConfirmationRefusal("slow-context asset differs from event session")
    if prior_session_context is not None and (
            prior_session_context.asset != pack.header.asset
            or prior_session_context.trading_day >= pack.header.d8):
        raise ConfirmationRefusal("prior-session context is not strictly prior")
    prior_receipt = (C.object_sha256({
        "schema": "QRE2CONFPRIORABSENT1", "asset": pack.header.asset,
        "trading_day": pack.header.d8,
    }) if prior_session_context is None else prior_session_context.receipt_sha256)
    context_receipt = (C.object_sha256({
        "schema": "QRE2CONFCONTEXTABSENT1", "asset": pack.header.asset,
        "trading_day": pack.header.d8,
    }) if context_repository is None else
        str(context_repository.receipt.get("receipt_sha256", "")))
    if len(context_receipt) != 64:
        raise ConfirmationRefusal("slow-context receipt is malformed")
    forecast_lineage: list[str] = []
    enriched_candidates: list[Mapping[str, str | float]] = []
    for row in candidate_rows:
        values: dict[str, str | float] = dict(row)
        if forecast_provider is None:
            features = {name: 0.0 for name in FORECAST_FEATURE_FIELDS}
            lineage = C.object_sha256({
                "schema": "QRE2CONFFORECASTABSENT1",
                "candidate_id": str(row.get("candidate_id", "")),
            })
        else:
            try:
                features, lineage = _forecast_features(
                    forecast_provider,
                    ForecastQuery(
                        candidate_id=str(row["candidate_id"]),
                        asset=str(row["asset"]), trading_day=int(row["d8"]),
                        decision_ts_ns=int(row["decision_ts_ns"]),
                        phase=int(row["phase"]),
                    ))
            except (C.EntryV2Refusal, KeyError, TypeError, ValueError) as exc:
                raise ConfirmationRefusal(
                    f"forward-vol candidate join refused: {exc}") from exc
        values.update(features)
        values["forecast_lineage_sha256"] = lineage
        enriched_candidates.append(MappingProxyType(values))
        forecast_lineage.append(lineage)
    candidate_rows = tuple(enriched_candidates)
    forecast_receipt = C.object_sha256({
        "schema": "QRE2CONFFORECASTJOIN1",
        "provider": ("ABSENT" if forecast_provider is None
                     else forecast_provider.receipt_sha256),
        "lineage": tuple(forecast_lineage),
    })
    candidate_by_id = {str(row.get("candidate_id", "")): row
                       for row in candidate_rows}
    if (len(candidate_by_id) != len(candidate_rows)
            or "" in candidate_by_id):
        raise ConfirmationRefusal("candidate roster has missing/duplicate identity")
    requested_extra: dict[str, tuple[int, ...]] = {}
    if extra_snapshot_ts_by_candidate is not None:
        for raw_id, raw_timestamps in extra_snapshot_ts_by_candidate.items():
            candidate_id = str(raw_id)
            timestamps = tuple(sorted(set(map(int, raw_timestamps))))
            if (candidate_id not in candidate_by_id or not timestamps
                    or any(timestamp <= 0 for timestamp in timestamps)):
                raise ConfirmationRefusal(
                    "extra feature snapshot request is malformed/unrostered")
            requested_extra[candidate_id] = timestamps
    bindings = build_candidate_truth_bindings(candidate_rows, teacher_rows)
    if ({row.asset for row in bindings} != {pack.header.asset}
            or {row.trading_day for row in bindings} != {pack.header.d8}):
        raise ConfirmationRefusal("candidate bindings do not match event session")
    raw = np.asarray(pack.rows)
    truth = build_event_truth_columns(raw, pack.header.asset, bindings)
    conservation = _stream_receipt(pack)
    formation_parity = _verify_formation_teachers(bindings, truth, raw, pack.header.asset)
    groups = _binding_groups(bindings)
    if not groups:
        raise ConfirmationRefusal("session has no CLEAR/READY confirmation alerts")

    feature_names: tuple[str, ...] | None = None
    features: list[np.ndarray] = []
    anchors: list[ConfirmationAnchor] = []
    outcomes: list[ConfirmationOutcome] = []
    planes: dict[tuple[int, int, int, int], _SessionPlane] = {}
    outcome_indices: dict[tuple[int, int, int, int], _OutcomeIndex] = {}
    observed_extra: set[tuple[str, int]] = set()
    for key, members in sorted(groups.items(), key=lambda item: repr(item[0])):
        (_asset, _day, side, phase, _phase_open, phase_close,
         _ceiling, _multiplier, _native_candidate_id) = key
        scheduled: set[int] = set()
        for member in members:
            base = _ceil_second(member.decision_ts_ns)
            expiry = member.decision_ts_ns + config.max_delay_sec * NANOS_PER_SECOND
            for offset in config.offsets:
                snapshot = base + offset * NANOS_PER_SECOND
                if snapshot <= expiry and snapshot < member.phase_close_ts_ns:
                    scheduled.add(snapshot)
            for snapshot in requested_extra.get(member.candidate_id, ()):
                if (snapshot < base or snapshot > expiry
                        or snapshot >= member.phase_close_ts_ns):
                    raise ConfirmationRefusal(
                        "extra feature snapshot is outside its causal watch")
                scheduled.add(snapshot)
        if not scheduled:
            continue
        quality_key = members[0].truth_quality_key
        columns = truth.candidate_columns(members[0])
        index = outcome_indices.get(quality_key)
        if index is None:
            index = _OutcomeIndex(raw, columns, pack.header.asset)
            outcome_indices[quality_key] = index
        plane = planes.get(quality_key)
        if plane is None:
            plane = _SessionPlane(
                pack, columns,
                level_association_mode=config.level_association_mode,
                prior_session_context=prior_session_context)
            planes[quality_key] = plane
        series_id = C.object_sha256({"schema": "QRE2CONFSERIES1", "key": key})
        scheduled_rows = tuple(sorted(scheduled))
        if context_repository is None:
            context_matrix = None
            context_names: tuple[str, ...] = ()
        else:
            try:
                context_matrix = tabular_context_summary(
                    context_repository, pack.header.d8, scheduled_rows)
            except C.EntryV2Refusal as exc:
                raise ConfirmationRefusal(
                    f"strict-prior slow-context join refused: {exc}") from exc
            context_names = TABULAR_CONTEXT_FEATURE_NAMES
            if context_matrix.shape != (len(scheduled_rows), len(context_names)):
                raise ConfirmationRefusal("slow-context summary schema differs")
        for scheduled_index, snapshot in enumerate(scheduled_rows):
            active = tuple(member for member in members
                           if member.decision_ts_ns <= snapshot
                           <= member.decision_ts_ns
                           + config.max_delay_sec * NANOS_PER_SECOND)
            if not active:
                continue
            current = index.current(snapshot)
            if current is None:
                continue
            position, raw_index, bid, ask, mid2 = current
            spread_usd = (ask - bid) * 1e-9 * ASSET_MULTIPLIER[pack.header.asset]
            cost = spread_usd + config.fee_usd
            candidate_ids = tuple(sorted(member.candidate_id for member in active))
            opportunity_id = C.object_sha256({
                "schema": SCHEMA, "series_id": series_id, "snapshot_ts_ns": snapshot,
                "candidate_ids": candidate_ids,
            })
            cutoff = int(np.searchsorted(raw["ts_recv_ns"], np.uint64(snapshot), side="left"))
            prefix_census = {
                name: plane.total(name, 0, int((snapshot - pack.header.open_ns)
                                               // NANOS_PER_SECOND))
                for name in ("event_count", "trade_count", "trade_volume",
                             "signed_trade_volume", "add_count", "cancel_count",
                             "modify_count", "other_action_count")
            }
            if prefix_census["event_count"] != cutoff:
                raise ConfirmationRefusal("snapshot event census differs from raw cutoff")
            context_row_sha256 = ("ABSENT" if context_matrix is None else
                hashlib.sha256(np.ascontiguousarray(
                    context_matrix[scheduled_index], dtype=np.float32
                ).tobytes()).hexdigest())
            feature_receipt = C.object_sha256({
                "schema": "QRE2CONFFEATURE1", "stream": conservation.receipt_sha256,
                "formation_parity": formation_parity, "config": config.receipt_sha256,
                "series_id": series_id, "snapshot_ts_ns": snapshot,
                "event_cutoff": cutoff, "prefix_census": prefix_census,
                "candidate_ids": candidate_ids,
                "forecast_lineage_sha256": tuple(
                    str(candidate_by_id[value]["forecast_lineage_sha256"])
                    for value in candidate_ids),
                "prior_session_receipt_sha256": prior_receipt,
                "slow_context_receipt_sha256": context_receipt,
                "slow_context_row_sha256": context_row_sha256,
            })
            ages = tuple((snapshot - member.decision_ts_ns) / NANOS_PER_SECOND
                         for member in active)
            anchor = ConfirmationAnchor(
                opportunity_id, series_id, candidate_ids, pack.header.asset,
                pack.header.d8, int(side), str(phase), int(phase_close), snapshot,
                cutoff, raw_index, int(raw["ts_recv_ns"][raw_index]),
                bid, ask, mid2, float(spread_usd), float(cost),
                min(ages), max(ages), feature_receipt)
            if compute_outcomes:
                generation = index.generation_at_snapshot(snapshot)
                if generation is None:
                    continue
                outcome = index.outcome(
                    opportunity_id=opportunity_id, snapshot_ts_ns=snapshot,
                    side=int(side), phase_close_ts_ns=int(phase_close),
                    entry_mid2=mid2, frozen_cost_usd=cost,
                    generation=generation)
                if outcome is None:
                    continue
            else:
                outcome = ConfirmationOutcome(
                    opportunity_id, 0.0, 0.0, 0.0, False, snapshot, False)
            active_candidates = tuple(candidate_by_id[row.candidate_id]
                                      for row in active)
            mapping = plane.feature_map(anchor, active, active_candidates)
            names = tuple(mapping) + context_names
            if feature_names is None:
                feature_names = names
            elif names != feature_names:
                raise ConfirmationRefusal("confirmation feature schema drifted within session")
            base = np.asarray(tuple(mapping.values()), np.float32)
            features.append(base if context_matrix is None else np.concatenate((
                base, np.asarray(context_matrix[scheduled_index], np.float32))))
            anchors.append(anchor); outcomes.append(outcome)
            for candidate_id in candidate_ids:
                if snapshot in requested_extra.get(candidate_id, ()):
                    observed_extra.add((candidate_id, snapshot))
    if not anchors or feature_names is None:
        raise ConfirmationRefusal("confirmation materialization produced no rows")
    expected_extra = {
        (candidate_id, timestamp)
        for candidate_id, timestamps in requested_extra.items()
        for timestamp in timestamps
    }
    if observed_extra != expected_extra:
        missing = tuple(sorted(expected_extra - observed_extra))
        raise ConfirmationRefusal(
            f"extra feature snapshots did not materialize exactly: {missing[:3]}")
    dataset = ConfirmationDataset(
        feature_names=feature_names, features=np.vstack(features),
        opportunity_id=np.asarray([row.opportunity_id for row in anchors], str),
        series_id=np.asarray([row.series_id for row in anchors], str),
        candidate_id=np.asarray([row.candidate_ids[0] for row in anchors], str),
        asset=np.asarray([row.asset for row in anchors], str),
        day=np.asarray([row.trading_day for row in anchors], np.int64),
        side=np.asarray([row.side for row in anchors], np.int8),
        phase=np.asarray([row.phase for row in anchors], str),
        snapshot_ts_ns=np.asarray([row.snapshot_ts_ns for row in anchors], np.int64),
        phase_close_ts_ns=np.asarray([row.phase_close_ts_ns for row in anchors], np.int64),
        event_cutoff=np.asarray([row.event_cutoff for row in anchors], np.int64),
        entry_event_ordinal=np.asarray(
            [row.entry_event_ordinal for row in anchors], np.int64),
        entry_availability_ts_ns=np.asarray(
            [row.entry_availability_ts_ns for row in anchors], np.int64),
        entry_bid_px=np.asarray([row.entry_bid_px for row in anchors], np.int64),
        entry_ask_px=np.asarray([row.entry_ask_px for row in anchors], np.int64),
        entry_mid2=np.asarray([row.entry_mid2 for row in anchors], np.int64),
        entry_spread_usd=np.asarray(
            [row.entry_spread_usd for row in anchors], np.float64),
        frozen_cost_usd=np.asarray(
            [row.frozen_cost_usd for row in anchors], np.float64),
        candidate_count=np.asarray([len(row.candidate_ids) for row in anchors], np.int16),
        min_alert_age_sec=np.asarray([row.min_alert_age_sec for row in anchors], np.float32),
        max_alert_age_sec=np.asarray([row.max_alert_age_sec for row in anchors], np.float32),
        cert_close_usd=np.asarray([row.cert_close_usd for row in outcomes], np.float64),
        mfe_usd=np.asarray([row.mfe_usd for row in outcomes], np.float64),
        mae_usd=np.asarray([row.mae_usd for row in outcomes], np.float64),
        wall_hit=np.asarray([row.wall_hit for row in outcomes], np.bool_),
        exit_ts_ns=np.asarray([row.exit_ts_ns for row in outcomes], np.int64),
        feature_receipt_sha256=np.asarray(
            [row.feature_receipt_sha256 for row in anchors], str),
        max_delay_sec=config.max_delay_sec,
        snapshot_mode=config.snapshot_mode,
        config_sha256=config.receipt_sha256,
        source_receipts=(conservation.receipt_sha256, formation_parity,
                         forecast_receipt, prior_receipt, context_receipt,
                         C.object_sha256({"schema":"QRE2CONFOUTCOMEMODE1",
                                          "compute_outcomes":compute_outcomes})),
    )
    dataset.validate()
    return dataset


def materialize_confirmation_paths(
    event_path: os.PathLike[str] | str,
    candidate_path: os.PathLike[str] | str,
    teacher_path: os.PathLike[str] | str,
    *, config: ConfirmationConfig = ConfirmationConfig(),
    forecast_provider: ForecastProvider | None = None,
    prior_session_context: PriorSessionContext | None = None,
    context_repository: CausalContextRepository | None = None,
) -> ConfirmationDataset:
    """Strict path adapter used by the campaign and real-session tests."""

    pack = EventPack(event_path, verify_hash=True)
    try:
        return materialize_confirmation_session(
            pack, read_versioned_tsv(candidate_path), read_versioned_tsv(teacher_path),
            config=config, forecast_provider=forecast_provider,
            prior_session_context=prior_session_context,
            context_repository=context_repository)
    finally:
        pack.close()


def combine_confirmation_datasets(
    datasets: Sequence[ConfirmationDataset],
) -> ConfirmationDataset:
    if not datasets:
        raise ConfirmationRefusal("cannot combine an empty confirmation dataset list")
    for dataset in datasets:
        dataset.validate()
    first = datasets[0]
    if (any(item.feature_names != first.feature_names for item in datasets)
            or any(item.config_sha256 != first.config_sha256 for item in datasets)
            or any(item.max_delay_sec != first.max_delay_sec for item in datasets)
            or any(item.snapshot_mode != first.snapshot_mode for item in datasets)):
        raise ConfirmationRefusal("confirmation datasets have incompatible schemas/configs")
    fields = (
        "features", "opportunity_id", "series_id", "candidate_id", "asset",
        "day", "side", "phase", "snapshot_ts_ns", "phase_close_ts_ns",
        "event_cutoff", "entry_event_ordinal", "entry_bid_px", "entry_ask_px",
        "entry_availability_ts_ns",
        "entry_mid2", "entry_spread_usd", "frozen_cost_usd", "candidate_count",
        "min_alert_age_sec", "max_alert_age_sec", "cert_close_usd", "mfe_usd",
        "mae_usd", "wall_hit", "exit_ts_ns", "feature_receipt_sha256",
    )
    joined = {name: np.concatenate([np.asarray(getattr(item, name))
                                    for item in datasets], axis=0) for name in fields}
    result = ConfirmationDataset(
        first.feature_names, **joined, max_delay_sec=first.max_delay_sec,
        snapshot_mode=first.snapshot_mode, config_sha256=first.config_sha256,
        source_receipts=tuple(receipt for item in datasets
                              for receipt in item.source_receipts))
    result.validate(); return result


__all__ = [
    "ConfirmationAnchor", "ConfirmationConfig", "ConfirmationDataset",
    "ConfirmationOpportunitySet",
    "ConfirmationOutcome", "ConfirmationRefusal", "StreamConservationReceipt",
    "combine_confirmation_datasets", "combine_confirmation_opportunity_sets",
    "learnable_confirmation_count",
    "materialize_confirmation_opportunity_session",
    "materialize_confirmation_paths", "materialize_confirmation_session",
    "read_versioned_tsv",
    "replay_offsets_seconds", "stream_conservation_receipt",
    "training_offsets_seconds",
]
