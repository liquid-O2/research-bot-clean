#!/usr/bin/env python3
"""Score walked THRESHOLD ENTER names against stored teacher and event labels."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from engine.entry_v2.exact_delayed_teacher import ExactDelayedTeacherDay
from engine.entry_v2.tabular_live_replay import load_policy_day_trace
from engine.entry_v2.tabular_recovery_contracts import RecoveryRefusal

BOUNDS = (20210721, 20210806)
SEED = 20260820
VARIANTS = ("H5", "H3", "H7")
RECEIPT = REPO / ".audit/threshold-h5-top2.json"
TRACE_ROOT = REPO / "artifacts/cache/threshold_refit/replay"
OUTCOME_CACHE = REPO / (
    "artifacts/entry_v2/tabular_recovery/rehearsal/cache/outcome_sessions/"
    "6f421af32b02ff145d3b1147590f1f2112261b307d0f54f391240f1cdf5cb72f"
)
TEACHER_BLOCK = REPO / (
    "artifacts/entry_v2/tabular_recovery/rehearsal/fit_only/e1r/"
    "evaluation/E1R_raw_THRESHOLD/real/seed_20260820/raw_block.json"
)
CURRICULUM = REPO / (
    "artifacts/entry_v2/tabular_recovery/rehearsal/fit_only/e1r/"
    "curriculum/two_round_curriculum.json"
)
MATRIX = REPO / (
    "artifacts/entry_v2/tabular_recovery/rehearsal/fit_only/e1r/"
    "curriculum/fits/round_0/component_matrix"
)
EVENT_RECEIPT = REPO / (
    "artifacts/entry_v2/tabular_recovery/diagnostics/"
    "entry_economics_20260823.json"
)
EXTREME_RECEIPT = REPO / (
    "artifacts/entry_v2/tabular_recovery/diagnostics/"
    "extreme_events_20260823.json"
)
CHECK = "python3 .audit/score_h5_top2.py"
VALUE_SCALE_USD = 600.0
DELTA_TOL_SEC = 2.5
EVENT_AGE_SEC = 180.0
WIDTH_USD = {"HG": 100.0, "NKD": 62.5, "SI": 75.0}
SCORE_COLUMNS = {
    "session": "disc_auction_session_vwap_aligned_usd",
    "phase": "disc_auction_phase_vwap_aligned_usd",
}


class JoinUnavailable(RuntimeError):
    def __init__(self, missing_key: str, detail: str) -> None:
        super().__init__(detail)
        self.missing_key = missing_key
        self.detail = detail


@dataclass(frozen=True, slots=True)
class MatrixSlice:
    matrix_row: np.ndarray
    opportunity_id: np.ndarray
    series_id: np.ndarray
    asset: np.ndarray
    day: np.ndarray
    phase: np.ndarray
    age_sec: np.ndarray
    side: np.ndarray
    phase_elapsed_sec: np.ndarray
    session_score: np.ndarray
    phase_score: np.ndarray
    label_usd: np.ndarray
    receipt_sha256: str


@dataclass(frozen=True, slots=True)
class NameLabel:
    series_id: str
    opportunity_id: str
    asset: str
    day: int
    phase: int
    label_usd: float
    kept: bool
    event: bool
    cell_best: bool
    event_rank: int | None
    cell_best_usd: float | None
    event_second_usd: float | None
    events_in_cell: int


@dataclass(frozen=True, slots=True)
class TraceEnter:
    variant: str
    day: int
    opportunity_id: str
    asset: str
    phase: int
    decision_ts_ns: int
    trace_pnl_usd: float


@dataclass(frozen=True, slots=True)
class CommitIdentity:
    opportunity_id: str
    series_id: str
    asset: str
    day: int
    phase: int
    age_sec: float
    label_usd: float


@dataclass(frozen=True, slots=True)
class VariantTrace:
    entries: tuple[TraceEnter, ...]
    source_universe_by_day: Mapping[int, str]
    block_path: Path
    block_trades: int
    block_pnl_usd: float


def _read_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise JoinUnavailable("artifact_path", f"missing JSON artifact {path}")
    try:
        value = json.loads(path.read_text())
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise JoinUnavailable("json_payload", f"cannot read JSON artifact {path}") from exc
    if not isinstance(value, dict):
        raise JoinUnavailable("json_object", f"{path} must contain a JSON object")
    return value


def _mapping(value: object, key: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise JoinUnavailable(key, f"{key} must be an object, got {type(value).__name__}")
    return value


def _sequence(value: object, key: str) -> Sequence[object]:
    if not isinstance(value, list):
        raise JoinUnavailable(key, f"{key} must be a list, got {type(value).__name__}")
    return value


def _required(value: Mapping[str, object], key: str, source: Path) -> object:
    if key not in value:
        raise JoinUnavailable(key, f"{source} lacks required key {key!r}")
    return value[key]


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


def _feature_columns(
    names: Sequence[str],
) -> tuple[dict[str, int], str]:
    phase_elapsed = (
        "disc_fvol_phase_scope_elapsed_sec"
        if "disc_fvol_phase_scope_elapsed_sec" in names
        else "disc_fvol_session_scope_elapsed_sec"
    )
    required = (
        "min_alert_age_sec",
        "phase_index",
        "side",
        phase_elapsed,
        *SCORE_COLUMNS.values(),
    )
    missing = [name for name in required if name not in names]
    if missing:
        raise JoinUnavailable(
            "component_matrix.feature_names",
            f"component matrix lacks required columns {missing}",
        )
    return {name: names.index(name) for name in required}, phase_elapsed


def load_matrix_slice() -> MatrixSlice:
    manifest_path = MATRIX / "manifest.json"
    manifest = _read_json(manifest_path)
    names = [
        str(value)
        for value in _sequence(
            _required(manifest, "feature_names", manifest_path),
            "component_matrix.feature_names",
        )
    ]
    columns, phase_elapsed = _feature_columns(names)
    day_all = np.load(MATRIX / "day.npy", mmap_mode="r")
    keep = np.flatnonzero(
        (np.asarray(day_all) >= BOUNDS[0]) & (np.asarray(day_all) <= BOUNDS[1])
    )
    if not len(keep):
        raise JoinUnavailable(
            "component_matrix.threshold_rows",
            f"component matrix has no rows in bounds {BOUNDS}",
        )
    x = np.load(MATRIX / "x.npy", mmap_mode="r")
    ordered_names = (
        "min_alert_age_sec",
        "phase_index",
        "side",
        phase_elapsed,
        SCORE_COLUMNS["session"],
        SCORE_COLUMNS["phase"],
    )
    column_indices = np.asarray([columns[name] for name in ordered_names], np.int64)
    selected_x = np.asarray(x[np.ix_(keep, column_indices)], np.float64)
    current = np.load(MATRIX / "current_asinh.npy", mmap_mode="r")
    labels = np.sinh(np.asarray(current[keep])) * VALUE_SCALE_USD
    if not np.allclose(labels * 100.0, np.rint(labels * 100.0), atol=1e-4, rtol=0):
        max_cent_residual = float(
            np.max(np.abs(labels * 100.0 - np.rint(labels * 100.0)))
        )
        raise JoinUnavailable(
            "component_matrix.current_asinh",
            (
                f"component label max cent residual {max_cent_residual} "
                "exceeds 0.0001"
            ),
        )
    return MatrixSlice(
        matrix_row=keep.astype(np.int64),
        opportunity_id=np.asarray(
            np.load(MATRIX / "opportunity_id.npy", mmap_mode="r")[keep], str
        ),
        series_id=np.asarray(
            np.load(MATRIX / "series_id.npy", mmap_mode="r")[keep], str
        ),
        asset=np.asarray(np.load(MATRIX / "asset.npy", mmap_mode="r")[keep], str),
        day=np.asarray(day_all[keep], np.int64),
        phase=np.nan_to_num(selected_x[:, 1], nan=9).astype(np.int64),
        age_sec=selected_x[:, 0],
        side=selected_x[:, 2],
        phase_elapsed_sec=selected_x[:, 3],
        session_score=selected_x[:, 4],
        phase_score=selected_x[:, 5],
        label_usd=np.asarray(labels, np.float64),
        receipt_sha256=str(
            _required(manifest, "matrix_receipt_sha256", manifest_path)
        ),
    )


def _nearest_rows_by_series(matrix: MatrixSlice, target_age: float) -> np.ndarray:
    distance = np.abs(matrix.age_sec - target_age)
    candidates = np.flatnonzero(distance <= DELTA_TOL_SEC)
    if not len(candidates):
        return np.empty(0, np.int64)
    order = np.lexsort(
        (
            candidates,
            distance[candidates],
            matrix.series_id[candidates],
        )
    )
    ranked = candidates[order]
    first = np.ones(len(ranked), bool)
    first[1:] = matrix.series_id[ranked[1:]] != matrix.series_id[ranked[:-1]]
    return ranked[first]


def _cell_groups(cell: np.ndarray) -> tuple[np.ndarray, ...]:
    if not len(cell):
        return ()
    order = np.argsort(cell, kind="stable")
    bounds = np.flatnonzero(np.diff(cell[order])) + 1
    return tuple(np.split(order, bounds))


def _causal_keep(formed: np.ndarray, buckets: np.ndarray) -> np.ndarray:
    keep = np.zeros(len(formed), bool)
    seen: set[int] = set()
    for index in np.argsort(formed, kind="stable"):
        bucket = int(buckets[index])
        if bucket not in seen:
            keep[index] = True
            seen.add(bucket)
    return keep


def _event_flags(
    formed: np.ndarray,
    side: np.ndarray,
    score: np.ndarray,
    cell: np.ndarray,
    *,
    long_min: bool,
    short_min: bool,
) -> np.ndarray:
    event = np.zeros(len(formed), bool)
    eligible = formed + EVENT_AGE_SEC
    for group in _cell_groups(cell):
        best: dict[int, float] = {}
        for index in group[np.argsort(eligible[group], kind="stable")]:
            value = float(score[index])
            if not np.isfinite(value):
                continue
            side_key = 1 if side[index] > 0 else -1
            current = best.get(side_key)
            take_min = long_min if side_key > 0 else short_min
            beats = current is None or (
                value < current - 1e-12 if take_min else value > current + 1e-12
            )
            if beats:
                event[index] = True
                best[side_key] = value
    return event


def _is_top2(event_rank: int | None) -> bool:
    return event_rank is not None and event_rank < 2


def _labels_for_asset(
    matrix: MatrixSlice,
    rows180: np.ndarray,
    formation_row_by_series: Mapping[str, int],
    asset: str,
    chosen_score: str,
    orientation: str,
) -> dict[str, NameLabel]:
    asset_rows = rows180[matrix.asset[rows180] == asset]
    if not len(asset_rows):
        raise JoinUnavailable(
            "event_rows",
            f"component matrix has no age-180 rows for asset {asset}",
        )
    formed = matrix.phase_elapsed_sec[asset_rows] - matrix.age_sec[asset_rows]
    form_aligned = np.asarray(
        [
            matrix.session_score[formation_row_by_series[series]]
            if series in formation_row_by_series
            else np.nan
            for series in matrix.series_id[asset_rows]
        ],
        np.float64,
    )
    cell = matrix.day[asset_rows] * 10 + matrix.phase[asset_rows]
    bucket = -10**12 - np.arange(len(asset_rows), dtype=np.int64)
    finite = np.isfinite(form_aligned)
    bucket[finite] = np.rint(form_aligned[finite] / WIDTH_USD[asset]).astype(
        np.int64
    )
    keep = _causal_keep(formed, cell * 10**9 + bucket)
    kept_rows = asset_rows[keep]
    kept_cell = cell[keep]
    kept_formed = formed[keep]
    kept_side = matrix.side[kept_rows]
    score = (
        matrix.session_score[kept_rows]
        if chosen_score == "session"
        else matrix.phase_score[kept_rows]
    )
    event = _event_flags(
        kept_formed,
        kept_side,
        score,
        kept_cell,
        long_min=orientation.startswith("long_min"),
        short_min=orientation.endswith("short_min"),
    )
    by_series: dict[str, NameLabel] = {}
    kept_position_by_row = {
        int(row): position for position, row in enumerate(kept_rows.tolist())
    }
    cell_stats: dict[int, tuple[float, float | None, dict[int, int]]] = {}
    for group in _cell_groups(kept_cell):
        labels = matrix.label_usd[kept_rows[group]]
        best = float(np.max(labels))
        event_group = group[event[group]]
        event_values = matrix.label_usd[kept_rows[event_group]]
        second = (
            float(np.sort(event_values)[-2]) if len(event_values) >= 2 else None
        )
        ranks = {
            int(position): int(np.count_nonzero(event_values > matrix.label_usd[
                kept_rows[position]
            ] + 1e-9))
            for position in event_group
        }
        cell_stats[int(kept_cell[group[0]])] = (best, second, ranks)
    for row in asset_rows:
        row_index = int(row)
        series = str(matrix.series_id[row_index])
        position = kept_position_by_row.get(row_index)
        row_cell = int(matrix.day[row_index] * 10 + matrix.phase[row_index])
        stats = cell_stats.get(row_cell)
        row_event = position is not None and bool(event[position])
        rank = stats[2].get(position) if row_event and stats is not None else None
        by_series[series] = NameLabel(
            series_id=series,
            opportunity_id=str(matrix.opportunity_id[row_index]),
            asset=asset,
            day=int(matrix.day[row_index]),
            phase=int(matrix.phase[row_index]),
            label_usd=float(matrix.label_usd[row_index]),
            kept=position is not None,
            event=row_event,
            cell_best=(
                position is not None
                and stats is not None
                and not stats[0] > float(matrix.label_usd[row_index]) + 1e-9
            ),
            event_rank=rank,
            cell_best_usd=stats[0] if stats is not None else None,
            event_second_usd=stats[1] if stats is not None else None,
            events_in_cell=len(stats[2]) if stats is not None else 0,
        )
    return by_series


def build_name_labels(
    matrix: MatrixSlice,
    oracle_receipt: Mapping[str, object],
) -> dict[str, NameLabel]:
    rows0 = _nearest_rows_by_series(matrix, 0.0)
    rows180 = _nearest_rows_by_series(matrix, EVENT_AGE_SEC)
    formation = {
        str(matrix.series_id[row]): int(row)
        for row in rows0
    }
    assets = _mapping(
        _required(oracle_receipt, "assets", EXTREME_RECEIPT),
        "extreme_events.assets",
    )
    labels: dict[str, NameLabel] = {}
    for asset in sorted(WIDTH_USD):
        config = _mapping(
            _required(assets, asset, EXTREME_RECEIPT),
            f"extreme_events.assets.{asset}",
        )
        chosen_score = str(
            _required(config, "chosen_score", EXTREME_RECEIPT)
        )
        orientation = str(_required(config, "orientation", EXTREME_RECEIPT))
        if chosen_score not in SCORE_COLUMNS:
            raise JoinUnavailable(
                f"extreme_events.assets.{asset}.chosen_score",
                f"unsupported event score {chosen_score!r} for {asset}",
            )
        labels.update(
            _labels_for_asset(
                matrix,
                rows180,
                formation,
                asset,
                chosen_score,
                orientation,
            )
        )
    return labels


def _event_rank_summary(
    labels: Mapping[str, NameLabel], asset: str
) -> tuple[int, dict[str, int], dict[str, float]]:
    cells: dict[tuple[int, int], list[float]] = {}
    for row in labels.values():
        if row.asset == asset and row.event:
            cells.setdefault((row.day, row.phase), []).append(row.label_usd)
    ranks: dict[int, list[float]] = {}
    for values in cells.values():
        for rank, value in enumerate(sorted(values, reverse=True)):
            ranks.setdefault(rank, []).append(value)
    counts = {str(rank): len(values) for rank, values in sorted(ranks.items())[:8]}
    means = {
        str(rank): float(np.mean(values))
        for rank, values in sorted(ranks.items())[:8]
    }
    return sum(len(values) for values in cells.values()), counts, means


def verify_event_parity(
    matrix: MatrixSlice,
    labels: Mapping[str, NameLabel],
    event_receipt: Mapping[str, object],
    oracle_receipt: Mapping[str, object],
) -> dict[str, object]:
    for source, receipt in (
        (EVENT_RECEIPT, event_receipt),
        (EXTREME_RECEIPT, oracle_receipt),
    ):
        receipt_matrix = str(_required(receipt, "matrix_receipt", source))
        if receipt_matrix != matrix.receipt_sha256:
            raise JoinUnavailable(
                "event_matrix_receipt",
                (
                    f"{source} matrix {receipt_matrix} != "
                    f"{matrix.receipt_sha256}"
                ),
            )
    assets = _mapping(
        _required(event_receipt, "assets", EVENT_RECEIPT),
        "entry_economics.assets",
    )
    oracle_assets = _mapping(
        _required(oracle_receipt, "assets", EXTREME_RECEIPT),
        "extreme_events.assets",
    )
    result: dict[str, object] = {}
    for asset in sorted(WIDTH_USD):
        asset_receipt = _mapping(
            _required(assets, asset, EVENT_RECEIPT),
            f"entry_economics.assets.{asset}",
        )
        oracle_asset = _mapping(
            _required(oracle_assets, asset, EXTREME_RECEIPT),
            f"extreme_events.assets.{asset}",
        )
        for key in ("chosen_score", "orientation"):
            if asset_receipt.get(key) != oracle_asset.get(key):
                raise JoinUnavailable(
                    f"event_receipts.assets.{asset}.{key}",
                    f"event receipts disagree on {asset} {key}",
                )
        threshold = _mapping(
            _required(asset_receipt, "threshold", EVENT_RECEIPT),
            f"entry_economics.assets.{asset}.threshold",
        )
        payoff = _mapping(
            _required(threshold, "event_payoff", EVENT_RECEIPT),
            f"entry_economics.assets.{asset}.threshold.event_payoff",
        )
        event_count, counts, means = _event_rank_summary(labels, asset)
        expected_count = int(_required(payoff, "n_events", EVENT_RECEIPT))
        expected_counts = {
            str(key): int(value)
            for key, value in _mapping(
                _required(payoff, "by_rank_n", EVENT_RECEIPT),
                f"entry_economics.assets.{asset}.threshold.event_payoff.by_rank_n",
            ).items()
        }
        expected_means = {
            str(key): float(value)
            for key, value in _mapping(
                _required(payoff, "by_rank_mean_usd", EVENT_RECEIPT),
                (
                    f"entry_economics.assets.{asset}.threshold."
                    "event_payoff.by_rank_mean_usd"
                ),
            ).items()
        }
        if event_count != expected_count or counts != expected_counts:
            raise JoinUnavailable(
                "event_identity_parity",
                (
                    f"{asset} rebuilt event ranks count {event_count}, {counts} "
                    f"!= receipt {expected_count}, {expected_counts}"
                ),
            )
        if any(
            abs(means[key] - expected_means[key]) > 1e-7
            for key in expected_means
        ):
            raise JoinUnavailable(
                "event_label_parity",
                f"{asset} rebuilt event rank dollars differ from stored receipt",
            )
        result[asset] = {
            "n_events": event_count,
            "by_rank_n": counts,
            "by_rank_mean_usd": means,
        }
    return result


def _load_trace_entries(variant: str) -> VariantTrace:
    run_root = (
        TRACE_ROOT
        / f"{variant}_raw_THRESHOLD/real/seed_{SEED}"
    )
    block_path = run_root / "raw_block.json"
    block = _read_json(block_path)
    paths = [
        Path(str(value))
        for value in _sequence(
            _required(block, "trace_paths", block_path),
            f"{variant}.trace_paths",
        )
    ]
    entries: list[TraceEnter] = []
    sources: dict[int, str] = {}
    seen_days: set[int] = set()
    for path in paths:
        try:
            trace = load_policy_day_trace(path)
        except RecoveryRefusal as exc:
            raise JoinUnavailable(
                f"{variant}.trace_receipt",
                f"{variant} cannot strict-load stored trace {path}",
            ) from exc
        day = trace.trading_day
        if not BOUNDS[0] <= day <= BOUNDS[1]:
            continue
        if day in seen_days:
            raise JoinUnavailable(
                f"{variant}.trading_day",
                f"{variant} has duplicate trace day {day}",
            )
        seen_days.add(day)
        sources[day] = trace.source_universe_sha256
        for arrival in trace.arrivals:
            example = arrival.example
            _exit_ts, pnl_usd, _reason = arrival.outcome.resolve(
                example.decision_ts_ns
            )
            entries.append(
                TraceEnter(
                    variant=variant,
                    day=day,
                    opportunity_id=example.candidate_id,
                    asset=example.asset,
                    phase=int(example.phase),
                    decision_ts_ns=example.decision_ts_ns,
                    trace_pnl_usd=pnl_usd,
                )
            )
    expected_days = {
        int(row["trading_day"])
        for row in _sequence(
            _required(block, "expected_sessions", block_path),
            f"{variant}.expected_sessions",
        )
        if isinstance(row, dict)
        and BOUNDS[0] <= int(row["trading_day"]) <= BOUNDS[1]
    }
    if seen_days != expected_days:
        raise JoinUnavailable(
            f"{variant}.trace_days",
            f"{variant} trace days {sorted(seen_days)} != {sorted(expected_days)}",
        )
    gate = _mapping(
        _required(block, "gate_detail", block_path),
        f"{variant}.gate_detail",
    )
    block_trades = int(_required(gate, "trades", block_path))
    block_pnl = float(_required(gate, "total_pnl_usd", block_path))
    trace_pnl = float(sum(row.trace_pnl_usd for row in entries))
    if block_trades != len(entries) or abs(block_pnl - trace_pnl) > 1e-7:
        raise JoinUnavailable(
            f"{variant}.block_parity",
            (
                f"{variant} trace has {len(entries)} trades and {trace_pnl} USD, "
                f"block has {block_trades} and {block_pnl}"
            ),
        )
    return VariantTrace(
        entries=tuple(entries),
        source_universe_by_day=sources,
        block_path=block_path,
        block_trades=block_trades,
        block_pnl_usd=block_pnl,
    )


def _commit_identity(
    values: Mapping[str, np.ndarray], index: int
) -> CommitIdentity:
    watch_start = int(values["watch_start_ts_ns"][index])
    snapshot = int(values["snapshot_ts_ns"][index])
    if snapshot < watch_start:
        raise JoinUnavailable(
            "outcome_cache.snapshot_ts_ns",
            f"outcome snapshot {snapshot} precedes watch start {watch_start}",
        )
    return CommitIdentity(
        opportunity_id=str(values["opportunity_id"][index]),
        series_id=str(values["series_id"][index]),
        asset=str(values["asset"][index]),
        day=int(values["day"][index]),
        phase=int(values["phase"][index]),
        age_sec=float(snapshot - watch_start) / 1_000_000_000.0,
        label_usd=float(values["signed_pnl_usd"][index]),
    )


def _load_commit_identities(
    traces: Mapping[str, VariantTrace],
) -> dict[str, CommitIdentity]:
    targets: dict[tuple[str, int], set[str]] = {}
    for trace in traces.values():
        for entry in trace.entries:
            targets.setdefault((entry.asset, entry.day), set()).add(
                entry.opportunity_id
            )
    identities: dict[str, CommitIdentity] = {}
    for (asset, day), expected in sorted(targets.items()):
        artifact = OUTCOME_CACHE / asset / f"{day}.npz"
        if not artifact.is_file():
            raise JoinUnavailable(
                "outcome_cache.artifact_path",
                f"stored delayed outcome artifact missing {artifact}",
            )
        with np.load(artifact, allow_pickle=False) as values:
            opportunity_ids = values["opportunity_id"].astype(str)
            indices = np.flatnonzero(np.isin(opportunity_ids, sorted(expected)))
            found = set(opportunity_ids[indices].tolist())
            if found != expected:
                raise JoinUnavailable(
                    "outcome_cache.opportunity_id",
                    (
                        f"{asset} day {day} delayed outcomes lack selected IDs "
                        f"{sorted(expected - found)}"
                    ),
                )
            for index in indices:
                identity = _commit_identity(values, int(index))
                prior = identities.get(identity.opportunity_id)
                if prior is not None and prior != identity:
                    raise JoinUnavailable(
                        "outcome_cache.opportunity_identity",
                        f"selected ID {identity.opportunity_id} maps two ways",
                    )
                identities[identity.opportunity_id] = identity
    return identities


def _load_teacher_enter_series(
    traces: Mapping[str, VariantTrace],
) -> dict[int, frozenset[str]]:
    teacher_block = _read_json(TEACHER_BLOCK)
    bounds = tuple(
        int(value)
        for value in _sequence(
            _required(teacher_block, "bounds", TEACHER_BLOCK),
            "teacher_block.bounds",
        )
    )
    if bounds != BOUNDS:
        raise JoinUnavailable(
            "teacher_block.bounds",
            f"teacher block bounds {bounds} != {BOUNDS}",
        )
    ceiling = {
        int(day): int(value)
        for day, value in _mapping(
            _required(
                teacher_block,
                "exact_ceiling_cents_by_day",
                TEACHER_BLOCK,
            ),
            "teacher_block.exact_ceiling_cents_by_day",
        ).items()
    }
    curriculum = _read_json(CURRICULUM)
    teacher_rows = [
        _mapping(value, "curriculum.final_teachers[]")
        for value in _sequence(
            _required(curriculum, "final_teachers", CURRICULUM),
            "curriculum.final_teachers",
        )
        if isinstance(value, dict)
        and BOUNDS[0] <= int(value.get("trading_day", 0)) <= BOUNDS[1]
    ]
    teacher_days = {int(row["trading_day"]) for row in teacher_rows}
    if teacher_days != set(ceiling):
        raise JoinUnavailable(
            "curriculum.final_teachers",
            (
                f"exact teacher days {sorted(teacher_days)} differ from "
                f"ceiling days {sorted(ceiling)}"
            ),
        )
    output: dict[int, frozenset[str]] = {}
    for row in teacher_rows:
        day = int(row["trading_day"])
        artifact = Path(str(_required(row, "artifact_path", CURRICULUM)))
        if not artifact.is_file():
            raise JoinUnavailable(
                "curriculum.final_teachers.artifact_path",
                f"exact teacher artifact missing {artifact}",
            )
        try:
            teacher = ExactDelayedTeacherDay.load(artifact)
        except RecoveryRefusal as exc:
            raise JoinUnavailable(
                "exact_teacher.receipt",
                f"cannot strict-load exact teacher {artifact}",
            ) from exc
        if teacher.trading_day != day:
            raise JoinUnavailable(
                "exact_teacher.trading_day",
                f"exact teacher path {artifact} stores another day",
            )
        if teacher.exact_objective_cents != ceiling[day]:
            raise JoinUnavailable(
                "exact_teacher.exact_objective_cents",
                (
                    f"teacher day {day} objective "
                    f"{teacher.exact_objective_cents} != block {ceiling[day]}"
                ),
            )
        selected_series = frozenset(teacher.selected_series_ids)
        source_universe = teacher.source_universe_sha256
        for variant, trace in traces.items():
            if trace.source_universe_by_day.get(day) != source_universe:
                raise JoinUnavailable(
                    f"{variant}.source_universe_sha256",
                    f"{variant} day {day} does not share the exact teacher universe",
                )
        output[day] = selected_series
    return output


def _metric(hits: int, total: int) -> dict[str, object]:
    return {
        "hits": hits,
        "total": total,
        "rate": float(hits / total) if total else None,
    }


def _summarize_entries(rows: Sequence[dict[str, object]]) -> dict[str, object]:
    assets = sorted(WIDTH_USD)
    result: dict[str, object] = {}
    for asset in (*assets, "overall"):
        selected = rows if asset == "overall" else [
            row for row in rows if row["asset"] == asset
        ]
        total = len(selected)
        result[asset] = {
            "enters": total,
            "actual_pnl_usd": float(
                sum(float(row["commit_label_usd"]) for row in selected)
            ),
            "teacher_enter": _metric(
                sum(bool(row["teacher_enter"]) for row in selected),
                total,
            ),
            "cell_best": _metric(
                sum(bool(row["cell_best"]) for row in selected),
                total,
            ),
            "top2": _metric(
                sum(bool(row["top2"]) for row in selected),
                total,
            ),
            "event_name": _metric(
                sum(bool(row["event_name"]) for row in selected),
                total,
            ),
            "age180_name": _metric(
                sum(bool(row["age180_name"]) for row in selected),
                total,
            ),
        }
    return {
        "overall": result.pop("overall"),
        "by_asset": result,
    }


def score_variant(
    variant: str,
    trace: VariantTrace,
    matrix: MatrixSlice,
    commit_identities: Mapping[str, CommitIdentity],
    name_labels: Mapping[str, NameLabel],
    teacher_enter: Mapping[int, frozenset[str]],
) -> dict[str, object]:
    matrix_row_by_opportunity = {
        str(opportunity): index
        for index, opportunity in enumerate(matrix.opportunity_id)
    }
    details: list[dict[str, object]] = []
    for entry in trace.entries:
        identity = commit_identities.get(entry.opportunity_id)
        if identity is None:
            raise JoinUnavailable(
                f"{variant}.selected_opportunity_id",
                (
                    f"{variant} selected ID {entry.opportunity_id} on day "
                    f"{entry.day} is absent from stored delayed outcomes"
                ),
            )
        matrix_row = matrix_row_by_opportunity.get(entry.opportunity_id)
        if (
            identity.asset != entry.asset
            or identity.day != entry.day
            or identity.phase != entry.phase
        ):
            raise JoinUnavailable(
                f"{variant}.selected_opportunity_identity",
                (
                    f"{variant} trace and delayed outcome identity differ for "
                    f"{entry.opportunity_id}"
                ),
            )
        commit_label = identity.label_usd
        if abs(commit_label - entry.trace_pnl_usd) > 1e-7:
            raise JoinUnavailable(
                f"{variant}.selected_commit_label",
                (
                    f"{variant} trace label {entry.trace_pnl_usd} != delayed outcome "
                    f"{commit_label} for {entry.opportunity_id}"
                ),
            )
        if matrix_row is not None and (
            str(matrix.series_id[matrix_row]) != identity.series_id
            or abs(float(matrix.label_usd[matrix_row]) - commit_label) > 1e-7
        ):
            raise JoinUnavailable(
                f"{variant}.component_matrix_identity",
                f"{variant} matrix and delayed outcome differ for {entry.opportunity_id}",
            )
        series = identity.series_id
        canonical = name_labels.get(series)
        if canonical is not None and (
            canonical.asset != entry.asset
            or canonical.day != entry.day
            or canonical.phase != entry.phase
        ):
            raise JoinUnavailable(
                f"{variant}.series_identity",
                f"{variant} series {series} crosses asset, day, or phase",
            )
        details.append(
            {
                "asset": entry.asset,
                "day": entry.day,
                "phase": entry.phase,
                "selected_opportunity_id": entry.opportunity_id,
                "series_id": series,
                "matrix_row": (
                    int(matrix.matrix_row[matrix_row])
                    if matrix_row is not None
                    else None
                ),
                "commit_age_sec": identity.age_sec,
                "commit_label_usd": commit_label,
                "teacher_enter": series in teacher_enter[entry.day],
                "age180_name": canonical is not None,
                "age180_opportunity_id": (
                    canonical.opportunity_id if canonical is not None else None
                ),
                "age180_label_usd": (
                    canonical.label_usd if canonical is not None else None
                ),
                "kept_name": canonical.kept if canonical is not None else False,
                "event_name": canonical.event if canonical is not None else False,
                "cell_best": (
                    canonical.cell_best if canonical is not None else False
                ),
                "top2": (
                    _is_top2(canonical.event_rank)
                    if canonical is not None
                    else False
                ),
                "event_rank": (
                    canonical.event_rank if canonical is not None else None
                ),
                "cell_best_usd": (
                    canonical.cell_best_usd if canonical is not None else None
                ),
                "event_second_usd": (
                    canonical.event_second_usd if canonical is not None else None
                ),
                "events_in_cell": (
                    canonical.events_in_cell if canonical is not None else 0
                ),
            }
        )
    summary = _summarize_entries(details)
    if int(summary["overall"]["enters"]) != trace.block_trades:
        raise JoinUnavailable(
            f"{variant}.summary",
            f"{variant} summary trade count differs from replay block",
        )
    return {
        "block": _relative(trace.block_path),
        "block_trades": trace.block_trades,
        "block_pnl_usd": trace.block_pnl_usd,
        **summary,
        "entries": details,
    }


def build_receipt() -> dict[str, object]:
    event_receipt = _read_json(EVENT_RECEIPT)
    oracle_receipt = _read_json(EXTREME_RECEIPT)
    matrix = load_matrix_slice()
    labels = build_name_labels(matrix, oracle_receipt)
    parity = verify_event_parity(
        matrix,
        labels,
        event_receipt,
        oracle_receipt,
    )
    traces: dict[str, VariantTrace] = {}
    for variant in VARIANTS:
        block = (
            TRACE_ROOT
            / f"{variant}_raw_THRESHOLD/real/seed_{SEED}/raw_block.json"
        )
        if variant == "H5" or block.is_file():
            traces[variant] = _load_trace_entries(variant)
    commit_identities = _load_commit_identities(traces)
    teacher_enter = _load_teacher_enter_series(traces)
    variants = {
        variant: score_variant(
            variant,
            trace,
            matrix,
            commit_identities,
            labels,
            teacher_enter,
        )
        for variant, trace in traces.items()
    }
    h5_overall = _mapping(
        _mapping(variants["H5"], "variants.H5")["overall"],
        "variants.H5.overall",
    )
    top2 = _mapping(h5_overall["top2"], "variants.H5.overall.top2")
    hits = int(top2["hits"])
    total = int(top2["total"])
    return {
        "schema": "QRE2THRESHOLDH5TOP21",
        "status": "OK",
        "bounds": list(BOUNDS),
        "seed": SEED,
        "definitions": {
            "identity_join": (
                "selected opportunity_id -> stored delayed-outcome series_id"
            ),
            "teacher_enter": (
                "series_id is in the same day's exact delayed teacher schedule"
            ),
            "cell_best": (
                "highest labeled dollars among live keep-first names in the "
                "asset-day-phase cell at age 180"
            ),
            "top2": (
                "new-extreme event has fewer than two event labels strictly "
                "above it in the same asset-day-phase cell at age 180"
            ),
            "commit_label": (
                "selected opportunity's exact replay label at its walked "
                "decision commit"
            ),
        },
        "sources": {
            "teacher_block": _relative(TEACHER_BLOCK),
            "exact_teachers": _relative(CURRICULUM),
            "delayed_outcomes": _relative(OUTCOME_CACHE),
            "component_matrix": _relative(MATRIX),
            "component_matrix_receipt_sha256": matrix.receipt_sha256,
            "event_economics": _relative(EVENT_RECEIPT),
            "event_oracle": _relative(EXTREME_RECEIPT),
        },
        "event_receipt_parity": parity,
        "variants": variants,
        "h5_conclusion": {
            "top2_hits": hits,
            "top2_misses": total - hits,
            "top2_rate": float(hits / total) if total else None,
            "majority_top2": hits > total - hits,
        },
        "check_command": CHECK,
    }


def _write_receipt(value: Mapping[str, object]) -> None:
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    temporary = RECEIPT.with_name(f"{RECEIPT.name}.tmp.{os.getpid()}")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, RECEIPT)


def _selftest() -> int:
    formed = np.asarray([0.0, 1.0, 2.0, 3.0, 4.0])
    side = np.ones(5)
    score = np.asarray([5.0, 4.0, 3.0, 4.0, 2.0])
    cell = np.asarray([1, 1, 1, 1, 1], np.int64)
    event = _event_flags(
        formed,
        side,
        score,
        cell,
        long_min=True,
        short_min=True,
    )
    if event.tolist() != [True, True, True, False, True]:
        raise AssertionError(f"selftest event sequence differs: {event.tolist()}")
    labels = np.asarray([10.0, 30.0, 20.0, 100.0, 5.0])
    event_values = labels[event]
    rank = int(np.count_nonzero(event_values > labels[2]))
    if rank != 1 or not _is_top2(rank):
        raise AssertionError(f"selftest second event must be top-2, got rank {rank}")
    if _is_top2(2) or _is_top2(None):
        raise AssertionError(
            f"selftest misses returned rank2={_is_top2(2)}, none={_is_top2(None)}"
        )
    kept = _causal_keep(
        np.asarray([2.0, 1.0, 3.0]),
        np.asarray([8, 8, 9], np.int64),
    )
    if kept.tolist() != [False, True, True]:
        raise AssertionError(f"selftest causal keep differs: {kept.tolist()}")
    identity = _commit_identity(
        {
            "opportunity_id": np.asarray(["o"]),
            "series_id": np.asarray(["s"]),
            "asset": np.asarray(["HG"]),
            "day": np.asarray([20210721]),
            "phase": np.asarray(["2"]),
            "watch_start_ts_ns": np.asarray([1_000_000_000]),
            "snapshot_ts_ns": np.asarray([181_000_000_000]),
            "signed_pnl_usd": np.asarray([125.0]),
        },
        0,
    )
    if (
        identity.series_id != "s"
        or identity.phase != 2
        or identity.age_sec != 180.0
        or identity.label_usd != 125.0
    ):
        raise AssertionError(f"selftest delayed outcome identity differs: {identity!r}")
    summary = _summarize_entries(
        [
            {
                "asset": "HG",
                "commit_label_usd": 10.0,
                "teacher_enter": True,
                "cell_best": False,
                "top2": True,
                "event_name": True,
                "age180_name": True,
            },
            {
                "asset": "HG",
                "commit_label_usd": -5.0,
                "teacher_enter": False,
                "cell_best": False,
                "top2": False,
                "event_name": False,
                "age180_name": True,
            },
        ]
    )
    overall = _mapping(summary["overall"], "selftest.summary.overall")
    if (
        int(overall["enters"]) != 2
        or float(_mapping(overall["top2"], "selftest.top2")["rate"]) != 0.5
        or float(overall["actual_pnl_usd"]) != 5.0
    ):
        raise AssertionError(f"selftest summary differs: {summary!r}")
    print("selftest_ok")
    return 0


def main() -> int:
    if "--selftest" in sys.argv[1:]:
        if len(sys.argv[1:]) != 1:
            raise ValueError(f"--selftest must be the only argument, got {sys.argv[1:]}")
        return _selftest()
    if sys.argv[1:]:
        raise ValueError(f"unsupported arguments {sys.argv[1:]}")
    try:
        receipt = build_receipt()
    except JoinUnavailable as exc:
        receipt = {
            "schema": "QRE2THRESHOLDH5TOP21",
            "status": "JOIN_UNAVAILABLE",
            "missing_key": exc.missing_key,
            "detail": exc.detail,
            "bounds": list(BOUNDS),
            "seed": SEED,
            "check_command": CHECK,
        }
        _write_receipt(receipt)
        print(json.dumps(receipt, indent=2, sort_keys=True))
        return 2
    _write_receipt(receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
