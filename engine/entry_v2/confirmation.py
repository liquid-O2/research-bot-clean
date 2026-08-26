"""Causal, full-stream tabular confirmation materialization for Entry V2."""

from __future__ import annotations

from decimal import Decimal
import csv
import functools
import hashlib
import os
from pathlib import Path
from types import MappingProxyType
from typing import Iterable, Mapping, Sequence

import numpy as np

from . import common as C
from .confirmation_dataset import ( ConfirmationDataset, ConfirmationOpportunitySet,
    combine_confirmation_datasets, combine_confirmation_opportunity_sets, )
from .confirmation_index import _OutcomeIndex
from .confirmation_plane import _SessionPlane
from .confirmation_types import ( AGE_GRIDS, CORPUS_AGE_GRID_SECONDS, DATASET_SCHEMA, FEATURE_WINDOWS_SECONDS,
    FEE_USD, GOAL_USD, NANOS_PER_SECOND, RECEIPT_SCHEMA, SCHEMA, WALL_USD,
    ConfirmationAnchor, ConfirmationConfig, ConfirmationOutcome,
    ConfirmationRefusal, StreamConservationReceipt, _ceil_second,
    _simple_object_sha256, _stream_receipt, re_full_sha, replay_offsets_seconds, training_offsets_seconds, )
from .corpus_forecast import ( FORECAST_FEATURE_FIELDS, ForecastProvider, ForecastQuery, _forecast_features, )
from .corpus_units import ASSET_MULTIPLIER
from .context_sources import ( CausalContextRepository, TABULAR_CONTEXT_FEATURE_NAMES,
    tabular_context_summary, )
from .diagnostic_inputs import ( CandidateTruthBinding, EventTruthColumns, UNITS_PER_USD,
    build_candidate_truth_bindings, build_event_truth_columns, )
from .discretionary_features import PriorSessionContext
from .event_pack import EventPack


def confirmation_implementation_hashes() -> Mapping[str, str]:
    """Exact source roster that can change materialized rows or labels."""

    directory = Path(__file__).resolve().parent
    files = { "common_contract": directory / "common.py", "confirmation": Path(__file__).resolve(),
        "confirmation_cache": directory / "confirmation_experiment.py",
        "context_pack": directory / "context_pack.py", "contracts": directory / "contracts.py",
        "discretionary_features": directory / "discretionary_features.py",
        "forecast_features": directory / "corpus.py", "slow_context": directory / "context_sources.py",
        "label_truth": directory / "diagnostic_inputs.py", "event_pack": directory / "event_pack.py",
        "availability_clock": directory.parent / "port_m2" / "availability.py", }
    hashes = {name: C.file_sha256(path) for name, path in files.items()}
    hashes["confirmation"] = C.object_sha256({ name: C.file_sha256(directory / name)
        for name in ( "confirmation.py", "confirmation_dataset.py", "confirmation_index.py",
            "confirmation_plane.py", "confirmation_types.py", ) })
    return MappingProxyType(hashes)


def read_versioned_tsv( path: os.PathLike[str] | str, *, allow_empty: bool = False,
) -> tuple[Mapping[str, str], ...]:
    """Read a versioned TSV and fail closed on every malformed/empty input."""

    source = Path(path)
    C.guard_payload(source)
    try:
        with source.open("r", newline="") as handle:
            marker = handle.readline()
            if not marker.startswith("# "):
                raise ConfirmationRefusal(f"version marker missing: {source}")
            rows = tuple(MappingProxyType(dict(row)) for row in csv.DictReader( handle, delimiter="\t"))
    except (OSError, UnicodeError, csv.Error) as exc:
        raise ConfirmationRefusal(f"cannot read confirmation TSV: {source}") from exc
    if not rows and not allow_empty:
        raise ConfirmationRefusal(f"confirmation TSV is empty: {source}")
    return rows


def stream_conservation_receipt(pack: EventPack) -> StreamConservationReceipt:
    """Public fail-closed event census used by empty-session corpus handling."""

    return _stream_receipt(pack)


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
        key = (row.asset, row.trading_day, row.side, row.phase, row.phase_open_ts_ns, row.phase_close_ts_ns,
               row.sane_ceiling_units, row.multiplier, row.candidate_id)
        groups[key] = (row,)
    return MappingProxyType(groups)


def learnable_confirmation_count( candidates: Iterable[Mapping[str, str]],
    teachers: Iterable[Mapping[str, str]], ) -> int:
    """Count causal candidate rows eligible for confirmation supervision."""

    bindings = build_candidate_truth_bindings(tuple(candidates), tuple(teachers))
    return sum(row.compliance_status == "CLEAR" and row.teacher_status == "READY" for row in bindings)


def _verify_formation_teachers( bindings: Sequence[CandidateTruthBinding], truth: EventTruthColumns,
    rows: np.ndarray, asset: str, ) -> str:
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
        outcome = index.outcome( opportunity_id=row.candidate_id,
            snapshot_ts_ns=row.decision_ts_ns, side=row.side, phase_close_ts_ns=row.phase_close_ts_ns,
            entry_mid2=row.entry_mid2, frozen_cost_usd=float(Decimal(row.frozen_cost_units) / UNITS_PER_USD),
            generation=generation, )
        if outcome is None:
            raise ConfirmationRefusal("formation teacher has no certifiable suffix")
        expected = ( float(Decimal(row.cert_close_units) / UNITS_PER_USD),
            float(Decimal(row.mfe_units) / UNITS_PER_USD), float(Decimal(row.mae_units) / UNITS_PER_USD),
            bool(row.wall_hit), int(row.exit_ts_ns), )
        observed = (outcome.cert_close_usd, outcome.mfe_usd, outcome.mae_usd,
                    outcome.wall_hit, outcome.exit_ts_ns)
        if (any(abs(float(a) - float(b)) > 1e-8 for a, b in zip(observed[:3], expected[:3]))
                or observed[3:] != expected[3:]):
            raise ConfirmationRefusal( f"formation teacher parity failed for {row.candidate_id}: "
                f"observed={observed} expected={expected}")
        checked.append((row.candidate_id, *observed))
    if not checked:
        raise ConfirmationRefusal("no CLEAR/READY formation teacher rows")
    return C.object_sha256({"schema": "QRE2CONFFORMPARITY1", "rows": checked})


def materialize_confirmation_opportunity_session( pack: EventPack,
    candidates: Iterable[Mapping[str, str]], teachers: Iterable[Mapping[str, str]],
    *, max_delay_sec: int = 300, ) -> ConfirmationOpportunitySet:
    """Materialize every delayed label without paying to build model features."""

    config = ConfirmationConfig( max_delay_sec=max_delay_sec, snapshot_mode="REPLAY")
    candidate_rows = tuple(candidates); teacher_rows = tuple(teachers)
    bindings = build_candidate_truth_bindings(candidate_rows, teacher_rows)
    if ({row.asset for row in bindings} != {pack.header.asset}
            or {row.trading_day for row in bindings} != {pack.header.d8}):
        raise ConfirmationRefusal("opportunity bindings do not match event session")
    raw = np.asarray(pack.rows)
    truth = build_event_truth_columns(raw, pack.header.asset, bindings)
    conservation = _stream_receipt(pack)
    formation_parity = _verify_formation_teachers( bindings, truth, raw, pack.header.asset)
    groups = _binding_groups(bindings)
    if not groups:
        raise ConfirmationRefusal("session has no CLEAR/READY opportunities")
    indices: dict[tuple[int, int, int, int], _OutcomeIndex] = {}
    fields: dict[str, list[np.ndarray]] = {name: [] for name in (
        "opportunity_id", "series_id", "candidate_id", "asset", "day", "side",
        "phase", "snapshot_ts_ns", "phase_close_ts_ns", "event_cutoff",
        "entry_event_ordinal", "entry_availability_ts_ns", "cert_close_usd",
        "mfe_usd", "mae_usd", "wall_hit", "exit_ts_ns", "feature_receipt_sha256")}
    for key, members in sorted(groups.items(), key=lambda item: repr(item[0])):
        (_asset, _day, side, phase, _phase_open, phase_close,
         _ceiling, _multiplier, _native_candidate_id) = key
        member = members[0]
        quality_key = member.truth_quality_key
        index = indices.get(quality_key)
        if index is None:
            index = _OutcomeIndex( raw, truth.candidate_columns(member), pack.header.asset)
            indices[quality_key] = index
        series_id = C.object_sha256({"schema": "QRE2CONFSERIES1", "key": key})
        base = _ceil_second(member.decision_ts_ns)
        expiry = member.decision_ts_ns + max_delay_sec * NANOS_PER_SECOND
        last = min(expiry, member.phase_close_ts_ns - 1)
        if base > last:
            continue
        snapshots = np.arange( base, last + 1, NANOS_PER_SECOND, dtype=np.int64)
        positions = np.searchsorted( index.ts, snapshots.astype(np.uint64), side="left") - 1
        visible = positions >= 0
        snapshots = snapshots[visible]; positions = positions[visible]
        if not len(snapshots):
            continue
        raw_indices = index.indices[positions]
        bid = raw["bid_px"][raw_indices].astype(np.int64)
        ask = raw["ask_px"][raw_indices].astype(np.int64)
        mid2 = index.mid2[positions]
        costs = ((ask - bid) * 1e-9 * ASSET_MULTIPLIER[pack.header.asset] + config.fee_usd)
        cutoff = np.searchsorted(
            raw["ts_recv_ns"], snapshots.astype(np.uint64), side="left").astype(np.int64)
        outcomes = index.outcomes_many( snapshot_ts_ns=snapshots, side=int(side),
            phase_close_ts_ns=int(phase_close), entry_mid2=mid2, frozen_cost_usd=costs)
        keep = np.asarray(outcomes["input_index"], np.int64)
        snapshots = snapshots[keep]; positions = positions[keep]
        raw_indices = raw_indices[keep]; cutoff = cutoff[keep]
        opportunity = np.asarray([_simple_object_sha256({ "schema": SCHEMA, "series_id": series_id,
            "snapshot_ts_ns": int(snapshot), "candidate_ids": (member.candidate_id,),
        }) for snapshot in snapshots], str)
        receipts = np.asarray([_simple_object_sha256({
            "schema": "QRE2CONFOPP1", "stream": conservation.receipt_sha256,
            "formation_parity": formation_parity, "config": config.receipt_sha256, "series_id": series_id,
            "snapshot_ts_ns": int(snapshot), "event_cutoff": int(cut), "candidate_id": member.candidate_id,
        }) for snapshot, cut in zip(snapshots, cutoff)], str)
        n = len(snapshots)
        values = { "opportunity_id": opportunity,
            "series_id": np.full(n, series_id), "candidate_id": np.full(n, member.candidate_id),
            "asset": np.full(n, pack.header.asset), "day": np.full(n, pack.header.d8, np.int64),
            "side": np.full(n, side, np.int8), "phase": np.full(n, str(phase)),
            "snapshot_ts_ns": snapshots, "phase_close_ts_ns": np.full(n, phase_close, np.int64),
            "event_cutoff": cutoff, "entry_event_ordinal": raw_indices.astype(np.int64),
            "entry_availability_ts_ns": raw["ts_recv_ns"][raw_indices].astype(np.int64),
            "feature_receipt_sha256": receipts, **{name: value for name, value in outcomes.items()
               if name != "input_index"}, }
        for name, value in values.items():
            fields[name].append(np.asarray(value))
    if not fields["opportunity_id"]:
        raise ConfirmationRefusal("opportunity materialization produced no rows")
    joined = {name: np.concatenate(value) for name, value in fields.items()}
    result = ConfirmationOpportunitySet( **joined,
        max_delay_sec=max_delay_sec, snapshot_mode="REPLAY", config_sha256=config.receipt_sha256,
        source_receipts=(conservation.receipt_sha256, formation_parity), )
    result.validate(); return result


def materialize_confirmation_session( pack: EventPack,
    candidates: Iterable[Mapping[str, str]], teachers: Iterable[Mapping[str, str]],
    *, config: ConfirmationConfig = ConfirmationConfig(), forecast_provider: ForecastProvider | None = None,
    prior_session_context: PriorSessionContext | None = None,
    context_repository: CausalContextRepository | None = None,
    extra_snapshot_ts_by_candidate: Mapping[str, Sequence[int]] | None = None, compute_outcomes: bool = True,
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
    if (context_repository is not None and context_repository.asset != pack.header.asset):
        raise ConfirmationRefusal("slow-context asset differs from event session")
    if prior_session_context is not None and ( prior_session_context.asset != pack.header.asset
            or prior_session_context.trading_day >= pack.header.d8):
        raise ConfirmationRefusal("prior-session context is not strictly prior")
    prior_receipt = (C.object_sha256({ "schema": "QRE2CONFPRIORABSENT1", "asset": pack.header.asset,
        "trading_day": pack.header.d8,
    }) if prior_session_context is None else prior_session_context.receipt_sha256)
    context_receipt = (C.object_sha256({ "schema": "QRE2CONFCONTEXTABSENT1", "asset": pack.header.asset,
        "trading_day": pack.header.d8, }) if context_repository is None else
        str(context_repository.receipt.get("receipt_sha256", "")))
    if len(context_receipt) != 64:
        raise ConfirmationRefusal("slow-context receipt is malformed")
    forecast_lineage: list[str] = []
    enriched_candidates: list[Mapping[str, str | float]] = []
    for row in candidate_rows:
        values: dict[str, str | float] = dict(row)
        if forecast_provider is None:
            features = {name: 0.0 for name in FORECAST_FEATURE_FIELDS}
            lineage = C.object_sha256({ "schema": "QRE2CONFFORECASTABSENT1",
                "candidate_id": str(row.get("candidate_id", "")), })
        else:
            try:
                features, lineage = _forecast_features( forecast_provider,
                    ForecastQuery( candidate_id=str(row["candidate_id"]),
                        asset=str(row["asset"]), trading_day=int(row["d8"]),
                        decision_ts_ns=int(row["decision_ts_ns"]), phase=int(row["phase"]), ))
            except (C.EntryV2Refusal, KeyError, TypeError, ValueError) as exc:
                raise ConfirmationRefusal( f"forward-vol candidate join refused: {exc}") from exc
        values.update(features)
        values["forecast_lineage_sha256"] = lineage
        enriched_candidates.append(MappingProxyType(values))
        forecast_lineage.append(lineage)
    candidate_rows = tuple(enriched_candidates)
    forecast_receipt = C.object_sha256({ "schema": "QRE2CONFFORECASTJOIN1",
        "provider": ("ABSENT" if forecast_provider is None else forecast_provider.receipt_sha256),
        "lineage": tuple(forecast_lineage), })
    candidate_by_id = {str(row.get("candidate_id", "")): row for row in candidate_rows}
    if (len(candidate_by_id) != len(candidate_rows) or "" in candidate_by_id):
        raise ConfirmationRefusal("candidate roster has missing/duplicate identity")
    requested_extra: dict[str, tuple[int, ...]] = {}
    if extra_snapshot_ts_by_candidate is not None:
        for raw_id, raw_timestamps in extra_snapshot_ts_by_candidate.items():
            candidate_id = str(raw_id)
            timestamps = tuple(sorted(set(map(int, raw_timestamps))))
            if (candidate_id not in candidate_by_id or not timestamps
                    or any(timestamp <= 0 for timestamp in timestamps)):
                raise ConfirmationRefusal( "extra feature snapshot request is malformed/unrostered")
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
                if (snapshot < base or snapshot > expiry or snapshot >= member.phase_close_ts_ns):
                    raise ConfirmationRefusal( "extra feature snapshot is outside its causal watch")
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
            plane = _SessionPlane( pack, columns, level_association_mode=config.level_association_mode,
                prior_session_context=prior_session_context)
            planes[quality_key] = plane
        series_id = C.object_sha256({"schema": "QRE2CONFSERIES1", "key": key})
        scheduled_rows = tuple(sorted(scheduled))
        if context_repository is None:
            context_matrix = None
            context_names: tuple[str, ...] = ()
        else:
            try:
                context_matrix = tabular_context_summary( context_repository, pack.header.d8, scheduled_rows)
            except C.EntryV2Refusal as exc:
                raise ConfirmationRefusal( f"strict-prior slow-context join refused: {exc}") from exc
            context_names = TABULAR_CONTEXT_FEATURE_NAMES
            if context_matrix.shape != (len(scheduled_rows), len(context_names)):
                raise ConfirmationRefusal("slow-context summary schema differs")
        for scheduled_index, snapshot in enumerate(scheduled_rows):
            active = tuple(member for member in members if member.decision_ts_ns <= snapshot
                           <= member.decision_ts_ns + config.max_delay_sec * NANOS_PER_SECOND)
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
                "candidate_ids": candidate_ids, })
            cutoff = int(np.searchsorted(raw["ts_recv_ns"], np.uint64(snapshot), side="left"))
            prefix_census = { name: plane.total(name, 0, int((snapshot - pack.header.open_ns)
                                               // NANOS_PER_SECOND))
                for name in ("event_count", "trade_count", "trade_volume",
                             "signed_trade_volume", "add_count", "cancel_count",
                             "modify_count", "other_action_count") }
            if prefix_census["event_count"] != cutoff:
                raise ConfirmationRefusal("snapshot event census differs from raw cutoff")
            context_row_sha256 = ("ABSENT" if context_matrix is None else hashlib.sha256(np.ascontiguousarray(
                    context_matrix[scheduled_index], dtype=np.float32 ).tobytes()).hexdigest())
            feature_receipt = C.object_sha256({
                "schema": "QRE2CONFFEATURE1", "stream": conservation.receipt_sha256,
                "formation_parity": formation_parity, "config": config.receipt_sha256,
                "series_id": series_id, "snapshot_ts_ns": snapshot,
                "event_cutoff": cutoff, "prefix_census": prefix_census, "candidate_ids": candidate_ids,
                "forecast_lineage_sha256": tuple( str(candidate_by_id[value]["forecast_lineage_sha256"])
                    for value in candidate_ids), "prior_session_receipt_sha256": prior_receipt,
                "slow_context_receipt_sha256": context_receipt, "slow_context_row_sha256": context_row_sha256,
            })
            ages = tuple((snapshot - member.decision_ts_ns) / NANOS_PER_SECOND for member in active)
            anchor = ConfirmationAnchor( opportunity_id, series_id, candidate_ids, pack.header.asset,
                pack.header.d8, int(side), str(phase), int(phase_close), snapshot,
                cutoff, raw_index, int(raw["ts_recv_ns"][raw_index]),
                bid, ask, mid2, float(spread_usd), float(cost), min(ages), max(ages), feature_receipt)
            if compute_outcomes:
                generation = index.generation_at_snapshot(snapshot)
                if generation is None:
                    continue
                outcome = index.outcome( opportunity_id=opportunity_id, snapshot_ts_ns=snapshot,
                    side=int(side), phase_close_ts_ns=int(phase_close), entry_mid2=mid2, frozen_cost_usd=cost,
                    generation=generation)
                if outcome is None:
                    continue
            else:
                outcome = ConfirmationOutcome( opportunity_id, 0.0, 0.0, 0.0, False, snapshot, False)
            active_candidates = tuple(candidate_by_id[row.candidate_id] for row in active)
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
    expected_extra = { (candidate_id, timestamp)
        for candidate_id, timestamps in requested_extra.items() for timestamp in timestamps }
    if observed_extra != expected_extra:
        missing = tuple(sorted(expected_extra - observed_extra))
        raise ConfirmationRefusal( f"extra feature snapshots did not materialize exactly: {missing[:3]}")
    dataset = ConfirmationDataset( feature_names=feature_names, features=np.vstack(features),
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
        entry_event_ordinal=np.asarray( [row.entry_event_ordinal for row in anchors], np.int64),
        entry_availability_ts_ns=np.asarray( [row.entry_availability_ts_ns for row in anchors], np.int64),
        entry_bid_px=np.asarray([row.entry_bid_px for row in anchors], np.int64),
        entry_ask_px=np.asarray([row.entry_ask_px for row in anchors], np.int64),
        entry_mid2=np.asarray([row.entry_mid2 for row in anchors], np.int64), entry_spread_usd=np.asarray(
            [row.entry_spread_usd for row in anchors], np.float64), frozen_cost_usd=np.asarray(
            [row.frozen_cost_usd for row in anchors], np.float64),
        candidate_count=np.asarray([len(row.candidate_ids) for row in anchors], np.int16),
        min_alert_age_sec=np.asarray([row.min_alert_age_sec for row in anchors], np.float32),
        max_alert_age_sec=np.asarray([row.max_alert_age_sec for row in anchors], np.float32),
        cert_close_usd=np.asarray([row.cert_close_usd for row in outcomes], np.float64),
        mfe_usd=np.asarray([row.mfe_usd for row in outcomes], np.float64),
        mae_usd=np.asarray([row.mae_usd for row in outcomes], np.float64),
        wall_hit=np.asarray([row.wall_hit for row in outcomes], np.bool_),
        exit_ts_ns=np.asarray([row.exit_ts_ns for row in outcomes], np.int64),
        feature_receipt_sha256=np.asarray( [row.feature_receipt_sha256 for row in anchors], str),
        max_delay_sec=config.max_delay_sec, snapshot_mode=config.snapshot_mode,
        config_sha256=config.receipt_sha256, source_receipts=(conservation.receipt_sha256, formation_parity,
                         forecast_receipt, prior_receipt, context_receipt,
                         C.object_sha256({"schema":"QRE2CONFOUTCOMEMODE1",
                                          "compute_outcomes":compute_outcomes})), )
    dataset.validate()
    return dataset


def materialize_confirmation_paths( event_path: os.PathLike[str] | str,
    candidate_path: os.PathLike[str] | str, teacher_path: os.PathLike[str] | str,
    *, config: ConfirmationConfig = ConfirmationConfig(), forecast_provider: ForecastProvider | None = None,
    prior_session_context: PriorSessionContext | None = None,
    context_repository: CausalContextRepository | None = None, ) -> ConfirmationDataset:
    """Strict path adapter used by the campaign and real-session tests."""

    pack = EventPack(event_path, verify_hash=True)
    try:
        return materialize_confirmation_session(
            pack, read_versioned_tsv(candidate_path), read_versioned_tsv(teacher_path),
            config=config, forecast_provider=forecast_provider, prior_session_context=prior_session_context,
            context_repository=context_repository)
    finally:
        pack.close()


__all__ = [ "AGE_GRIDS", "CORPUS_AGE_GRID_SECONDS", "DATASET_SCHEMA",
    "FEATURE_WINDOWS_SECONDS", "FEE_USD", "GOAL_USD", "NANOS_PER_SECOND",
    "RECEIPT_SCHEMA", "SCHEMA", "WALL_USD", "ConfirmationAnchor",
    "ConfirmationConfig", "ConfirmationDataset", "ConfirmationOpportunitySet",
    "ConfirmationOutcome", "ConfirmationRefusal", "StreamConservationReceipt",
    "_OutcomeIndex", "_SessionPlane", "_binding_groups", "_ceil_second",
    "_simple_object_sha256", "_stream_receipt", "_verify_formation_teachers",
    "combine_confirmation_datasets", "combine_confirmation_opportunity_sets",
    "confirmation_implementation_hashes", "learnable_confirmation_count",
    "materialize_confirmation_opportunity_session",
    "materialize_confirmation_paths", "materialize_confirmation_session",
    "read_versioned_tsv", "re_full_sha", "replay_offsets_seconds",
    "stream_conservation_receipt", "training_offsets_seconds", ]
