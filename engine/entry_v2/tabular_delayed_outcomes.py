"""Dense delayed outcome shards and session materialization."""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import os
from pathlib import Path
from typing import Final, Iterable, Mapping

import numpy as np

from . import common as C
from .confirmation import _binding_groups, _verify_formation_teachers
from .confirmation_index import _OutcomeIndex
from .confirmation_types import (
    FEE_USD, NANOS_PER_SECOND, SCHEMA as CONFIRMATION_SCHEMA,
    ConfirmationConfig, _ceil_second, _simple_object_sha256,
    _stream_receipt, re_full_sha,
)
from .corpus_units import ASSET_MULTIPLIER
from .diagnostic_inputs import (
    build_candidate_truth_bindings, build_event_truth_columns,
)
from .event_pack import EventPack
from .tabular_recovery_contracts import RecoveryRefusal


OUTCOME_SCHEMA: Final = "QRE2TABOUTCOME1"


def _sha(value: object) -> bool:
    return isinstance(value, str) and re_full_sha(value)


def _hash_array(digest: "hashlib._Hash", value: np.ndarray) -> None:
    array = np.ascontiguousarray(value)
    digest.update(str(array.dtype).encode())
    digest.update(repr(array.shape).encode())
    digest.update(array.tobytes())


def _cent_values(values: np.ndarray, name: str) -> np.ndarray:
    source = np.asarray(values, np.float64)
    cents = np.rint(source * 100.0).astype(np.int64)
    if not np.allclose(cents / 100.0, source, atol=1e-7, rtol=0):
        raise RecoveryRefusal(f"{name} is not exact cents")
    return cents


@dataclass(frozen=True, slots=True)
class DelayedOutcomeShard:
    """One portfolio asset-day's dense, privileged delayed outcome plane."""

    opportunity_id: np.ndarray
    series_id: np.ndarray
    candidate_id: np.ndarray
    asset: np.ndarray
    day: np.ndarray
    side: np.ndarray
    phase: np.ndarray
    watch_start_ts_ns: np.ndarray
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
    signed_pnl_usd: np.ndarray
    phase_close_pnl_usd: np.ndarray
    phase_exit_ts_ns: np.ndarray
    mfe_usd: np.ndarray
    mae_usd: np.ndarray
    wall_hit: np.ndarray
    wall_hit_ts_ns: np.ndarray
    wall_pnl_usd: np.ndarray
    exit_ts_ns: np.ndarray
    cost_applied_count: np.ndarray
    event_prefix_receipt_sha256: np.ndarray
    max_delay_sec: int
    config_sha256: str
    source_receipts: tuple[str, ...]

    def validate(self) -> None:
        n = len(self.opportunity_id)
        fields = tuple(getattr(self, name) for name in (
            "series_id", "candidate_id", "asset", "day", "side", "phase",
            "watch_start_ts_ns", "snapshot_ts_ns", "phase_close_ts_ns",
            "event_cutoff", "entry_event_ordinal", "entry_availability_ts_ns",
            "entry_bid_px", "entry_ask_px", "entry_mid2", "entry_spread_usd",
            "frozen_cost_usd", "signed_pnl_usd", "phase_close_pnl_usd",
            "phase_exit_ts_ns", "mfe_usd", "mae_usd", "wall_hit",
            "wall_hit_ts_ns", "wall_pnl_usd", "exit_ts_ns",
            "cost_applied_count", "event_prefix_receipt_sha256"))
        if (n == 0 or any(np.asarray(value).shape != (n,) for value in fields)
                or len(set(np.asarray(self.opportunity_id, str).tolist())) != n
                or len(set(np.asarray(self.asset, str).tolist())) != 1
                or len(set(np.asarray(self.day, np.int64).tolist())) != 1
                or not np.all(np.isin(self.asset, C.ASSETS))
                or not np.all(np.isin(self.side, (-1, 1)))
                or not np.all(np.asarray(self.snapshot_ts_ns)
                              >= np.asarray(self.watch_start_ts_ns))
                or not np.all(np.asarray(self.snapshot_ts_ns)
                              <= np.asarray(self.watch_start_ts_ns)
                              + self.max_delay_sec * NANOS_PER_SECOND)
                or not np.all(np.asarray(self.entry_availability_ts_ns)
                              < np.asarray(self.snapshot_ts_ns))
                or not np.all(np.asarray(self.event_cutoff) > 0)
                or not np.all(np.asarray(self.entry_event_ordinal)
                              < np.asarray(self.event_cutoff))
                or not np.all(np.asarray(self.entry_bid_px) > 0)
                or not np.all(np.asarray(self.entry_ask_px)
                              > np.asarray(self.entry_bid_px))
                or not np.array_equal(
                    np.asarray(self.entry_mid2),
                    np.asarray(self.entry_bid_px) + np.asarray(self.entry_ask_px))
                or not np.all(np.asarray(self.entry_spread_usd) >= 0)
                or not np.all(np.asarray(self.frozen_cost_usd) >= 0)
                or not np.all(np.asarray(self.cost_applied_count) == 1)
                or not np.all(np.asarray(self.exit_ts_ns)
                              >= np.asarray(self.snapshot_ts_ns))
                or not np.all(np.asarray(self.phase_exit_ts_ns)
                              >= np.asarray(self.snapshot_ts_ns))
                or not np.all(np.asarray(self.exit_ts_ns)
                              <= np.asarray(self.phase_exit_ts_ns))
                or not np.all(np.isfinite(self.signed_pnl_usd))
                or not np.all(np.isfinite(self.phase_close_pnl_usd))
                or not np.all(np.asarray(self.mfe_usd) >= 0)
                or not np.all(np.asarray(self.mae_usd) >= 0)
                or self.max_delay_sec not in (300, 600)
                or not _sha(self.config_sha256)
                or any(not _sha(value) for value in self.source_receipts)
                or any(not _sha(value) for value in
                       np.asarray(self.event_prefix_receipt_sha256, str))):
            raise RecoveryRefusal("delayed outcome shard is malformed")
        _cent_values(self.signed_pnl_usd, "signed PnL")
        _cent_values(self.phase_close_pnl_usd, "phase-close PnL")
        wall = np.asarray(self.wall_hit, bool)
        if (np.any(np.asarray(self.wall_hit_ts_ns)[wall]
                  != np.asarray(self.exit_ts_ns)[wall])
                or np.any(np.asarray(self.wall_hit_ts_ns)[~wall] != -1)
                or np.any(np.asarray(self.wall_pnl_usd)[~wall] != 0.0)
                or not np.allclose(
                    np.asarray(self.wall_pnl_usd)[wall],
                    np.asarray(self.signed_pnl_usd)[wall], atol=1e-7, rtol=0)
                or not np.allclose(
                    np.asarray(self.signed_pnl_usd)[~wall],
                    np.asarray(self.phase_close_pnl_usd)[~wall],
                    atol=1e-7, rtol=0)):
            raise RecoveryRefusal("wall/phase outcome identities differ")
        series = np.asarray(self.series_id, str)
        candidate = np.asarray(self.candidate_id, str)
        timestamps = np.asarray(self.snapshot_ts_ns, np.int64)
        mapping: dict[str, set[str]] = {}
        for key, value in zip(series, candidate):
            mapping.setdefault(key, set()).add(value)
        if any(len(values) != 1 for values in mapping.values()):
            raise RecoveryRefusal("one delayed series maps to multiple candidates")
        order = np.lexsort((timestamps, series))
        sorted_series = series[order]; sorted_ts = timestamps[order]
        if np.any((sorted_series[1:] == sorted_series[:-1])
                  & (sorted_ts[1:] <= sorted_ts[:-1])):
            raise RecoveryRefusal("delayed series chronology is not strict")

    @property
    def representation_sha256(self) -> str:
        self.validate()
        digest = hashlib.sha256()
        digest.update(OUTCOME_SCHEMA.encode())
        digest.update(str(self.max_delay_sec).encode())
        digest.update(self.config_sha256.encode())
        digest.update("\n".join(self.source_receipts).encode())
        for name in self.array_fields():
            _hash_array(digest, np.asarray(getattr(self, name)))
        return digest.hexdigest()

    @staticmethod
    def array_fields() -> tuple[str, ...]:
        return (
            "opportunity_id", "series_id", "candidate_id", "asset", "day",
            "side", "phase", "watch_start_ts_ns", "snapshot_ts_ns",
            "phase_close_ts_ns", "event_cutoff", "entry_event_ordinal",
            "entry_availability_ts_ns", "entry_bid_px", "entry_ask_px",
            "entry_mid2", "entry_spread_usd", "frozen_cost_usd",
            "signed_pnl_usd", "phase_close_pnl_usd", "phase_exit_ts_ns",
            "mfe_usd", "mae_usd", "wall_hit", "wall_hit_ts_ns",
            "wall_pnl_usd", "exit_ts_ns", "cost_applied_count",
            "event_prefix_receipt_sha256")

    def subset(self, mask: np.ndarray) -> "DelayedOutcomeShard":
        selected = np.asarray(mask, bool)
        if selected.shape != (len(self.opportunity_id),) or not selected.any():
            raise RecoveryRefusal("delayed outcome subset is empty/malformed")
        result = replace(self, **{
            name: np.asarray(getattr(self, name))[selected]
            for name in self.array_fields()})
        result.validate(); return result

    def save(self, path: os.PathLike[str] | str) -> str:
        self.validate()
        target = C.assert_workspace_output(path)
        if target.suffix != ".npz":
            raise RecoveryRefusal("delayed outcome shard must be .npz")
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(target.name + f".tmp.{os.getpid()}")
        with tmp.open("xb") as handle:
            np.savez_compressed(
                handle,
                **{name: np.asarray(getattr(self, name))
                   for name in self.array_fields()},
                schema=np.asarray([OUTCOME_SCHEMA], str),
                max_delay_sec=np.asarray([self.max_delay_sec], np.int16),
                config_sha256=np.asarray([self.config_sha256], str),
                source_receipts=np.asarray(self.source_receipts, str),
                representation_sha256=np.asarray(
                    [self.representation_sha256], str))
            handle.flush(); os.fsync(handle.fileno())
        os.replace(tmp, target)
        return C.file_sha256(target)

    @classmethod
    def load(cls, path: os.PathLike[str] | str) -> "DelayedOutcomeShard":
        source = Path(path); C.guard_payload(source)
        try:
            with np.load(source, allow_pickle=False) as values:
                if str(values["schema"][0]) != OUTCOME_SCHEMA:
                    raise RecoveryRefusal("delayed outcome schema differs")
                result = cls(
                    **{name: values[name] for name in cls.array_fields()},
                    max_delay_sec=int(values["max_delay_sec"][0]),
                    config_sha256=str(values["config_sha256"][0]),
                    source_receipts=tuple(
                        values["source_receipts"].astype(str).tolist()))
                expected = str(values["representation_sha256"][0])
        except (OSError, ValueError, KeyError) as exc:
            raise RecoveryRefusal("cannot strict-load delayed outcome shard") from exc
        result.validate()
        if result.representation_sha256 != expected:
            raise RecoveryRefusal("delayed outcome representation differs")
        return result


def materialize_delayed_outcome_session(
    pack: EventPack,
    candidates: Iterable[Mapping[str, str]],
    teachers: Iterable[Mapping[str, str]],
    *, max_delay_sec: int = 300,
) -> DelayedOutcomeShard:
    """Build the exact every-second outcome plane without model features."""

    config = ConfirmationConfig(max_delay_sec=max_delay_sec, snapshot_mode="REPLAY")
    candidate_rows = tuple(candidates); teacher_rows = tuple(teachers)
    bindings = build_candidate_truth_bindings(candidate_rows, teacher_rows)
    if ({row.asset for row in bindings} != {pack.header.asset}
            or {row.trading_day for row in bindings} != {pack.header.d8}):
        raise RecoveryRefusal("delayed outcome bindings differ from event session")
    C.guard_date(pack.header.d8)
    raw = np.asarray(pack.rows)
    truth = build_event_truth_columns(raw, pack.header.asset, bindings)
    conservation = _stream_receipt(pack)
    formation_parity = _verify_formation_teachers(
        bindings, truth, raw, pack.header.asset)
    groups = _binding_groups(bindings)
    if not groups:
        raise RecoveryRefusal("delayed outcome session has no learnable candidates")
    fields: dict[str, list[np.ndarray]] = {
        name: [] for name in DelayedOutcomeShard.array_fields()}
    indices: dict[tuple[int, int, int, int], _OutcomeIndex] = {}
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
        watch_start = _ceil_second(member.decision_ts_ns)
        last = min(
            member.decision_ts_ns + max_delay_sec * NANOS_PER_SECOND,
            member.phase_close_ts_ns - 1)
        if watch_start > last:
            continue
        snapshots = np.arange(
            watch_start, last + 1, NANOS_PER_SECOND, dtype=np.int64)
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
        spread = ((ask - bid) * 1e-9
                  * ASSET_MULTIPLIER[pack.header.asset])
        costs = spread + FEE_USD
        cutoff = np.searchsorted(
            raw["ts_recv_ns"], snapshots.astype(np.uint64),
            side="left").astype(np.int64)
        outcome = index.outcomes_many(
            snapshot_ts_ns=snapshots, side=int(side),
            phase_close_ts_ns=int(phase_close), entry_mid2=mid2,
            frozen_cost_usd=costs)
        keep = np.asarray(outcome["input_index"], np.int64)
        snapshots = snapshots[keep]; positions = positions[keep]
        raw_indices = raw_indices[keep]; bid = bid[keep]; ask = ask[keep]
        mid2 = mid2[keep]; spread = spread[keep]; costs = costs[keep]
        cutoff = cutoff[keep]

        # Reconstruct the un-walled phase-close value from the same exact
        # generation boundary used by ``_OutcomeIndex.outcomes_many``.
        starts = np.searchsorted(index.ts, snapshots.astype(np.uint64), side="left")
        phase_end = int(np.searchsorted(
            index.ts, np.uint64(phase_close), side="right"))
        ends = np.minimum(phase_end, index.generation_end[starts])
        phase_position = ends - 1
        phase_mid = index.mid2[phase_position]
        phase_pnl = (int(side) * (phase_mid - mid2) * index.factor - costs)
        phase_exit = index.ts[phase_position].astype(np.int64)
        wall = np.asarray(outcome["wall_hit"], bool)
        exit_ts = np.asarray(outcome["exit_ts_ns"], np.int64)
        signed = np.asarray(outcome["cert_close_usd"], np.float64)
        opportunity = np.asarray([_simple_object_sha256({
            "schema": CONFIRMATION_SCHEMA, "series_id": series_id,
            "snapshot_ts_ns": int(snapshot),
            "candidate_ids": (member.candidate_id,),
        }) for snapshot in snapshots], str)
        receipts = np.asarray([_simple_object_sha256({
            "schema": "QRE2TABPREFIX1",
            "stream": conservation.receipt_sha256,
            "formation_parity": formation_parity,
            "config": config.receipt_sha256,
            "series_id": series_id,
            "snapshot_ts_ns": int(snapshot),
            "event_cutoff": int(cut),
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
            "watch_start_ts_ns": np.full(n, watch_start, np.int64),
            "snapshot_ts_ns": snapshots,
            "phase_close_ts_ns": np.full(n, phase_close, np.int64),
            "event_cutoff": cutoff,
            "entry_event_ordinal": raw_indices.astype(np.int64),
            "entry_availability_ts_ns": raw["ts_recv_ns"][raw_indices]
                .astype(np.int64),
            "entry_bid_px": bid,
            "entry_ask_px": ask,
            "entry_mid2": mid2,
            "entry_spread_usd": spread.astype(np.float64),
            "frozen_cost_usd": costs.astype(np.float64),
            "signed_pnl_usd": signed,
            "phase_close_pnl_usd": phase_pnl.astype(np.float64),
            "phase_exit_ts_ns": phase_exit,
            "mfe_usd": np.asarray(outcome["mfe_usd"], np.float64),
            "mae_usd": np.asarray(outcome["mae_usd"], np.float64),
            "wall_hit": wall,
            "wall_hit_ts_ns": np.where(wall, exit_ts, -1).astype(np.int64),
            "wall_pnl_usd": np.where(wall, signed, 0.0).astype(np.float64),
            "exit_ts_ns": exit_ts,
            "cost_applied_count": np.ones(n, np.int8),
            "event_prefix_receipt_sha256": receipts,
        }
        for name, value in values.items():
            fields[name].append(np.asarray(value))
    if not fields["opportunity_id"]:
        raise RecoveryRefusal("delayed outcome materialization produced no rows")
    result = DelayedOutcomeShard(
        **{name: np.concatenate(values) for name, values in fields.items()},
        max_delay_sec=max_delay_sec, config_sha256=config.receipt_sha256,
        source_receipts=(conservation.receipt_sha256, formation_parity))
    result.validate(); return result


__all__ = [
    'DelayedOutcomeShard',
    'OUTCOME_SCHEMA',
    'materialize_delayed_outcome_session',
]
