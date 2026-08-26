#!/usr/bin/env python3
"""Kill-test one causal roster veto on stored 2021 events and walked ENTERs."""

from __future__ import annotations

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Mapping, Sequence

import numpy as np

AUDIT = Path(__file__).resolve().parent
if str(AUDIT) not in sys.path:
    sys.path.insert(0, str(AUDIT))

import score_h5_top2 as h5

RECEIPT = h5.REPO / ".audit/threshold-roster-kill.json"
CHECK = "python3 .audit/score_roster_kill.py"
SCHEMA = "QRE2THRESHOLDROSTERKILL1"
WORKERS = 14
WALL_VETO = 0.2
FIELDS = (
    "event_order",
    "score_depth",
    "running_occupancy",
    "commit_event_rank",
)
OPS = ("gt", "ge", "lt", "le")
EXPECTED_EVENTS = {"HG": 251, "NKD": 255, "SI": 209}
EXPECTED_TOP2 = {"HG": 78, "NKD": 78, "SI": 67}
Identity = Literal["top2", "event_not_top2", "non_event"]


@dataclass(frozen=True, slots=True)
class CausalRoster:
    event_order: int
    score_depth: float
    running_occupancy: int
    commit_event_rank: int


@dataclass(frozen=True, slots=True)
class EventRow:
    series_id: str
    asset: str
    label_usd: float
    top2: bool
    roster: CausalRoster


@dataclass(frozen=True, slots=True)
class WalkedEnter:
    variant: str
    opportunity_id: str
    series_id: str
    identity: Identity
    commit_label_usd: float
    wall_probability: float
    roster: CausalRoster


@dataclass(frozen=True, slots=True)
class VetoRule:
    field: str
    op: str
    threshold: float


@dataclass(frozen=True, slots=True)
class _NameClock:
    series_id: str
    asset: str
    day: int
    phase: int
    formed: float
    side: int
    score: float
    event: bool


def _identity(event: bool, event_rank: int | None) -> Identity:
    if event and h5._is_top2(event_rank):
        return "top2"
    if event:
        return "event_not_top2"
    return "non_event"


def _roster_value(roster: CausalRoster, field: str) -> float:
    if field == "event_order":
        return float(roster.event_order)
    if field == "score_depth":
        return float(roster.score_depth)
    if field == "running_occupancy":
        return float(roster.running_occupancy)
    if field == "commit_event_rank":
        return float(roster.commit_event_rank)
    raise ValueError(f"unknown causal field {field!r}, expected one of {FIELDS}")


def _vetoes(values: np.ndarray, op: str, threshold: float) -> np.ndarray:
    if op == "gt":
        return values > threshold
    if op == "ge":
        return values >= threshold
    if op == "lt":
        return values < threshold
    if op == "le":
        return values <= threshold
    raise ValueError(f"unknown veto op {op!r}, expected one of {OPS}")


def _auc_higher(positive: np.ndarray, negative: np.ndarray) -> float | None:
    if not len(positive) or not len(negative):
        return None
    greater = np.sum(positive[:, None] > negative[None, :])
    equal = np.sum(positive[:, None] == negative[None, :])
    return float((greater + 0.5 * equal) / (len(positive) * len(negative)))


def _asset_state(
    matrix: h5.MatrixSlice,
    rows180: np.ndarray,
    formation: Mapping[str, int],
    asset: str,
    chosen_score: str,
    orientation: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    asset_rows = rows180[matrix.asset[rows180] == asset]
    if not len(asset_rows):
        raise h5.JoinUnavailable(
            "event_rows",
            f"component matrix has no age-180 rows for asset {asset}",
        )
    formed = matrix.phase_elapsed_sec[asset_rows] - matrix.age_sec[asset_rows]
    form_aligned = np.asarray(
        [
            matrix.session_score[formation[series]]
            if series in formation
            else np.nan
            for series in matrix.series_id[asset_rows]
        ],
        np.float64,
    )
    cell = matrix.day[asset_rows] * 10 + matrix.phase[asset_rows]
    bucket = -10**12 - np.arange(len(asset_rows), dtype=np.int64)
    finite = np.isfinite(form_aligned)
    bucket[finite] = np.rint(form_aligned[finite] / h5.WIDTH_USD[asset]).astype(
        np.int64
    )
    keep = h5._causal_keep(formed, cell * 10**9 + bucket)
    kept_rows = asset_rows[keep]
    kept_formed = formed[keep]
    kept_cell = cell[keep]
    kept_side = matrix.side[kept_rows]
    score = (
        matrix.session_score[kept_rows]
        if chosen_score == "session"
        else matrix.phase_score[kept_rows]
    )
    event = h5._event_flags(
        kept_formed,
        kept_side,
        score,
        kept_cell,
        long_min=orientation.startswith("long_min"),
        short_min=orientation.endswith("short_min"),
    )
    return asset_rows, formed, keep, kept_rows, kept_cell, event


def _clocks_for_asset(
    matrix: h5.MatrixSlice,
    rows180: np.ndarray,
    formation: Mapping[str, int],
    asset: str,
    chosen_score: str,
    orientation: str,
) -> dict[str, _NameClock]:
    asset_rows, formed, _keep, kept_rows, _kept_cell, event = _asset_state(
        matrix, rows180, formation, asset, chosen_score, orientation
    )
    all_score = (
        matrix.session_score[asset_rows]
        if chosen_score == "session"
        else matrix.phase_score[asset_rows]
    )
    kept_position = {
        int(row): position for position, row in enumerate(kept_rows.tolist())
    }
    clocks: dict[str, _NameClock] = {}
    for local, row in enumerate(asset_rows.tolist()):
        series = str(matrix.series_id[int(row)])
        position = kept_position.get(int(row))
        clocks[series] = _NameClock(
            series_id=series,
            asset=asset,
            day=int(matrix.day[int(row)]),
            phase=int(matrix.phase[int(row)]),
            formed=float(formed[local]),
            side=1 if float(matrix.side[int(row)]) > 0 else -1,
            score=float(all_score[local]),
            event=position is not None and bool(event[position]),
        )
    return clocks


def build_name_clocks(
    matrix: h5.MatrixSlice,
    oracle_receipt: Mapping[str, object],
) -> dict[str, _NameClock]:
    rows0 = h5._nearest_rows_by_series(matrix, 0.0)
    rows180 = h5._nearest_rows_by_series(matrix, h5.EVENT_AGE_SEC)
    formation = {str(matrix.series_id[row]): int(row) for row in rows0}
    assets = h5._mapping(
        h5._required(oracle_receipt, "assets", h5.EXTREME_RECEIPT),
        "extreme_events.assets",
    )
    clocks: dict[str, _NameClock] = {}
    for asset in sorted(h5.WIDTH_USD):
        config = h5._mapping(
            h5._required(assets, asset, h5.EXTREME_RECEIPT),
            f"extreme_events.assets.{asset}",
        )
        chosen_score = str(h5._required(config, "chosen_score", h5.EXTREME_RECEIPT))
        orientation = str(h5._required(config, "orientation", h5.EXTREME_RECEIPT))
        if chosen_score not in h5.SCORE_COLUMNS:
            raise h5.JoinUnavailable(
                f"extreme_events.assets.{asset}.chosen_score",
                f"unsupported event score {chosen_score!r} for {asset}",
            )
        clocks.update(
            _clocks_for_asset(
                matrix, rows180, formation, asset, chosen_score, orientation
            )
        )
    return clocks


def _cell_key(clock: _NameClock) -> tuple[str, int, int]:
    return (clock.asset, clock.day, clock.phase)


def _score_depth(prior_same_side: Sequence[_NameClock], score: float) -> float:
    if not prior_same_side:
        return 0.0
    return abs(float(score) - float(prior_same_side[-1].score))


def _roster_from_events(
    clock: _NameClock,
    events: Sequence[_NameClock],
) -> CausalRoster:
    formeds = np.asarray([row.formed for row in events], np.float64)
    eligibles = formeds + h5.EVENT_AGE_SEC
    if clock.event:
        event_order = next(
            index
            for index, row in enumerate(events)
            if row.series_id == clock.series_id
        )
        prior = list(events[:event_order])
    else:
        event_order = int(np.count_nonzero(formeds < clock.formed))
        prior = [row for row in events if row.formed < clock.formed]
    return CausalRoster(
        event_order=event_order,
        score_depth=_score_depth(
            [row for row in prior if row.side == clock.side],
            clock.score,
        ),
        running_occupancy=int(np.count_nonzero(eligibles < clock.formed)),
        commit_event_rank=int(
            np.count_nonzero(eligibles <= clock.formed + h5.EVENT_AGE_SEC)
        ),
    )


def build_rosters(clocks: Mapping[str, _NameClock]) -> dict[str, CausalRoster]:
    events_by_cell: dict[tuple[str, int, int], list[_NameClock]] = {}
    for clock in clocks.values():
        if clock.event:
            events_by_cell.setdefault(_cell_key(clock), []).append(clock)
    for key, rows in events_by_cell.items():
        events_by_cell[key] = sorted(rows, key=lambda row: (row.formed, row.series_id))
    return {
        series: _roster_from_events(clock, events_by_cell.get(_cell_key(clock), ()))
        for series, clock in clocks.items()
    }


def _official_top2_series(labels: Mapping[str, h5.NameLabel]) -> frozenset[str]:
    cells: dict[tuple[str, int, int], list[tuple[float, str]]] = {}
    for label in labels.values():
        if not label.event:
            continue
        cells.setdefault((label.asset, label.day, label.phase), []).append(
            (label.label_usd, label.series_id)
        )
    chosen: set[str] = set()
    for items in cells.values():
        items.sort(key=lambda item: (-item[0], item[1]))
        chosen.update(series for _usd, series in items[:2])
    return frozenset(chosen)


def _event_rows(
    labels: Mapping[str, h5.NameLabel],
    rosters: Mapping[str, CausalRoster],
) -> tuple[EventRow, ...]:
    official_top2 = _official_top2_series(labels)
    rows: list[EventRow] = []
    for series, label in labels.items():
        if not label.event:
            continue
        roster = rosters.get(series)
        if roster is None:
            raise h5.JoinUnavailable(
                "causal_roster.event_series",
                f"event series {series} has no causal roster",
            )
        rows.append(
            EventRow(
                series_id=series,
                asset=label.asset,
                label_usd=label.label_usd,
                top2=series in official_top2,
                roster=roster,
            )
        )
    return tuple(rows)


def verify_headline_event_set(rows: Sequence[EventRow]) -> dict[str, object]:
    by_asset: dict[str, dict[str, int]] = {}
    for asset in sorted(h5.WIDTH_USD):
        selected = [row for row in rows if row.asset == asset]
        n_events = len(selected)
        n_top2 = sum(row.top2 for row in selected)
        expected_events = EXPECTED_EVENTS[asset]
        expected_top2 = EXPECTED_TOP2[asset]
        if n_events != expected_events or n_top2 != expected_top2:
            raise h5.JoinUnavailable(
                "event_set",
                (
                    f"{asset} rebuilt {n_events} events / {n_top2} top-2, "
                    f"expected {expected_events} / {expected_top2}"
                ),
            )
        by_asset[asset] = {"n_events": n_events, "n_top2": n_top2}
    n_events = len(rows)
    n_top2 = sum(row.top2 for row in rows)
    if n_events != 715 or n_top2 != 223:
        raise h5.JoinUnavailable(
            "event_set",
            f"rebuilt {n_events} events / {n_top2} top-2, expected 715 / 223",
        )
    return {
        "n_events": n_events,
        "n_top2": n_top2,
        "by_asset": by_asset,
        "rank_0_plus_1": EXPECTED_TOP2,
    }


def _field_split(rows: Sequence[EventRow], field: str) -> dict[str, object]:
    top2 = np.asarray(
        [_roster_value(row.roster, field) for row in rows if row.top2],
        np.float64,
    )
    rest = np.asarray(
        [_roster_value(row.roster, field) for row in rows if not row.top2],
        np.float64,
    )
    return {
        "top2_n": int(len(top2)),
        "rank2plus_n": int(len(rest)),
        "top2_mean": float(np.mean(top2)) if len(top2) else None,
        "rank2plus_mean": float(np.mean(rest)) if len(rest) else None,
        "top2_median": float(np.median(top2)) if len(top2) else None,
        "rank2plus_median": float(np.median(rest)) if len(rest) else None,
        "auc_top2_higher": _auc_higher(top2, rest),
    }


def separation(rows: Sequence[EventRow]) -> dict[str, object]:
    return {field: _field_split(rows, field) for field in FIELDS}


def _load_walls(variant: str) -> dict[str, float]:
    run_root = h5.TRACE_ROOT / f"{variant}_raw_THRESHOLD/real/seed_{h5.SEED}"
    block_path = run_root / "raw_block.json"
    block = h5._read_json(block_path)
    walls: dict[str, float] = {}
    for raw_path in h5._sequence(
        h5._required(block, "trace_paths", block_path),
        f"{variant}.trace_paths",
    ):
        path = Path(str(raw_path))
        try:
            trace = h5.load_policy_day_trace(path)
        except h5.RecoveryRefusal as exc:
            raise h5.JoinUnavailable(
                f"{variant}.trace_receipt",
                f"{variant} cannot strict-load stored trace {path}",
            ) from exc
        if not h5.BOUNDS[0] <= trace.trading_day <= h5.BOUNDS[1]:
            continue
        for arrival in trace.arrivals:
            uid = arrival.example.candidate_id
            wall = float(arrival.score.wall_probability)
            prior = walls.get(uid)
            if prior is not None and prior != wall:
                raise h5.JoinUnavailable(
                    f"{variant}.wall_probability",
                    f"{variant} selected ID {uid} has two wall_probability values",
                )
            walls[uid] = wall
    return walls


def join_walked(
    variant: str,
    trace: h5.VariantTrace,
    commits: Mapping[str, h5.CommitIdentity],
    labels: Mapping[str, h5.NameLabel],
    rosters: Mapping[str, CausalRoster],
    walls: Mapping[str, float],
) -> tuple[WalkedEnter, ...]:
    rows: list[WalkedEnter] = []
    for entry in trace.entries:
        identity = commits.get(entry.opportunity_id)
        if identity is None:
            raise h5.JoinUnavailable(
                f"{variant}.selected_opportunity_id",
                (
                    f"{variant} selected ID {entry.opportunity_id} on day "
                    f"{entry.day} is absent from stored delayed outcomes"
                ),
            )
        if (
            identity.asset != entry.asset
            or identity.day != entry.day
            or identity.phase != entry.phase
        ):
            raise h5.JoinUnavailable(
                f"{variant}.selected_opportunity_identity",
                (
                    f"{variant} trace and delayed outcome identity differ for "
                    f"{entry.opportunity_id}"
                ),
            )
        if abs(identity.label_usd - entry.trace_pnl_usd) > 1e-7:
            raise h5.JoinUnavailable(
                f"{variant}.selected_commit_label",
                (
                    f"{variant} trace label {entry.trace_pnl_usd} != delayed "
                    f"outcome {identity.label_usd} for {entry.opportunity_id}"
                ),
            )
        canonical = labels.get(identity.series_id)
        roster = rosters.get(identity.series_id)
        wall = walls.get(entry.opportunity_id)
        if canonical is None:
            raise h5.JoinUnavailable(
                f"{variant}.series_id",
                f"{variant} series {identity.series_id} is absent from age-180 labels",
            )
        if roster is None:
            raise h5.JoinUnavailable(
                f"{variant}.causal_roster",
                f"{variant} series {identity.series_id} has no causal roster",
            )
        if wall is None:
            raise h5.JoinUnavailable(
                f"{variant}.wall_probability",
                (
                    f"{variant} selected ID {entry.opportunity_id} lacks "
                    "stored arrival.score.wall_probability"
                ),
            )
        if (
            canonical.asset != entry.asset
            or canonical.day != entry.day
            or canonical.phase != entry.phase
        ):
            raise h5.JoinUnavailable(
                f"{variant}.series_identity",
                f"{variant} series {identity.series_id} crosses asset, day, or phase",
            )
        rows.append(
            WalkedEnter(
                variant=variant,
                opportunity_id=entry.opportunity_id,
                series_id=identity.series_id,
                identity=_identity(canonical.event, canonical.event_rank),
                commit_label_usd=identity.label_usd,
                wall_probability=wall,
                roster=roster,
            )
        )
    if len(rows) != trace.block_trades:
        raise h5.JoinUnavailable(
            f"{variant}.summary",
            f"{variant} walked join count {len(rows)} != block {trace.block_trades}",
        )
    return tuple(rows)


def _rate(hits: int, total: int) -> dict[str, object]:
    return {
        "hits": hits,
        "total": total,
        "rate": float(hits / total) if total else None,
    }


def _rule_metrics(
    walked: Sequence[WalkedEnter],
    veto: np.ndarray,
) -> dict[str, object]:
    loser = np.asarray(
        [row.identity == "event_not_top2" for row in walked], bool
    )
    winner = np.asarray([row.identity == "top2" for row in walked], bool)
    n_losers = int(np.count_nonzero(loser))
    n_winners = int(np.count_nonzero(winner))
    removed = int(np.count_nonzero(veto & loser))
    kept = int(np.count_nonzero((~veto) & winner))
    remove_rate = float(removed / n_losers) if n_losers else None
    keep_rate = float(kept / n_winners) if n_winners else None
    survives = (
        remove_rate is not None
        and keep_rate is not None
        and remove_rate > 0.5
        and keep_rate > 0.5
    )
    return {
        "remove_event_not_top2": _rate(removed, n_losers),
        "keep_top2": _rate(kept, n_winners),
        "survives": survives,
        "score": (
            (min(remove_rate, keep_rate), remove_rate + keep_rate)
            if remove_rate is not None and keep_rate is not None
            else (-1.0, -1.0)
        ),
    }


def scan_rules(walked: Sequence[WalkedEnter]) -> tuple[VetoRule, dict[str, object], int, int]:
    event_rows = [
        row for row in walked if row.identity in {"top2", "event_not_top2"}
    ]
    if not event_rows:
        raise h5.JoinUnavailable(
            "kill_bar.population",
            "pooled walked event-name ENTERs are empty",
        )
    best_rule: VetoRule | None = None
    best_metrics: dict[str, object] | None = None
    best_key: tuple[object, ...] | None = None
    scanned = 0
    survived = 0
    for field in FIELDS:
        values = np.asarray(
            [_roster_value(row.roster, field) for row in event_rows],
            np.float64,
        )
        thresholds = np.unique(values)
        for threshold in thresholds.tolist():
            for op in OPS:
                scanned += 1
                veto = _vetoes(values, op, float(threshold))
                metrics = _rule_metrics(event_rows, veto)
                key = (
                    bool(metrics["survives"]),
                    metrics["score"],
                    -abs(float(threshold)),
                    field,
                    op,
                )
                if bool(metrics["survives"]):
                    survived += 1
                if best_key is None or key > best_key:
                    best_key = key
                    best_rule = VetoRule(field, op, float(threshold))
                    best_metrics = metrics
    if best_rule is None or best_metrics is None:
        raise h5.JoinUnavailable("chosen_rule", "rule scan produced no candidate")
    return best_rule, best_metrics, scanned, survived


def _bucket(rows: Sequence[WalkedEnter]) -> dict[str, object]:
    by_identity = {
        name: [row for row in rows if row.identity == name]
        for name in ("top2", "event_not_top2", "non_event")
    }
    return {
        "n": len(rows),
        "commit_label_usd": float(sum(row.commit_label_usd for row in rows)),
        "top2": {
            "n": len(by_identity["top2"]),
            "commit_label_usd": float(
                sum(row.commit_label_usd for row in by_identity["top2"])
            ),
        },
        "event_not_top2": {
            "n": len(by_identity["event_not_top2"]),
            "commit_label_usd": float(
                sum(row.commit_label_usd for row in by_identity["event_not_top2"])
            ),
        },
        "non_event": {
            "n": len(by_identity["non_event"]),
            "commit_label_usd": float(
                sum(row.commit_label_usd for row in by_identity["non_event"])
            ),
        },
    }


def _apply_rule(
    rows: Sequence[WalkedEnter], rule: VetoRule
) -> np.ndarray:
    values = np.asarray(
        [_roster_value(row.roster, rule.field) for row in rows], np.float64
    )
    if not len(values):
        return np.zeros(0, bool)
    return _vetoes(values, rule.op, rule.threshold)


def overlay(
    walked: Sequence[WalkedEnter], rule: VetoRule
) -> dict[str, object]:
    result: dict[str, object] = {}
    for variant in (*h5.VARIANTS, "pooled"):
        selected = (
            list(walked)
            if variant == "pooled"
            else [row for row in walked if row.variant == variant]
        )
        veto = _apply_rule(selected, rule)
        kept = [row for row, drop in zip(selected, veto.tolist()) if not drop]
        dropped = [row for row, drop in zip(selected, veto.tolist()) if drop]
        also_wall = sum(row.wall_probability > WALL_VETO for row in dropped)
        result[variant] = {
            "kept": _bucket(kept),
            "vetoed": _bucket(dropped),
            "wall_overlap": {
                "veto_if_wall_probability_gt": WALL_VETO,
                "vetoed_n": len(dropped),
                "also_wall_n": also_wall,
                "also_wall_rate": (
                    float(also_wall / len(dropped)) if dropped else None
                ),
            },
        }
    return result


def _chosen_payload(
    rule: VetoRule, metrics: Mapping[str, object]
) -> dict[str, object]:
    threshold: int | float = (
        int(rule.threshold)
        if float(rule.threshold).is_integer()
        else float(rule.threshold)
    )
    return {
        "field": rule.field,
        "op": rule.op,
        "threshold": threshold,
        "remove_event_not_top2": metrics["remove_event_not_top2"],
        "keep_top2": metrics["keep_top2"],
        "survives": bool(metrics["survives"]),
    }


def build_receipt(wall_clock_sec: float) -> dict[str, object]:
    event_receipt = h5._read_json(h5.EVENT_RECEIPT)
    oracle_receipt = h5._read_json(h5.EXTREME_RECEIPT)
    matrix = h5.load_matrix_slice()
    labels = h5.build_name_labels(matrix, oracle_receipt)
    parity = h5.verify_event_parity(matrix, labels, event_receipt, oracle_receipt)
    clocks = build_name_clocks(matrix, oracle_receipt)
    rosters = build_rosters(clocks)
    events = _event_rows(labels, rosters)
    event_set = verify_headline_event_set(events)
    load_variants = list(h5.VARIANTS)
    with ThreadPoolExecutor(max_workers=min(WORKERS, 6)) as pool:
        trace_futs = {
            variant: pool.submit(h5._load_trace_entries, variant)
            for variant in load_variants
        }
        wall_futs = {
            variant: pool.submit(_load_walls, variant) for variant in load_variants
        }
        traces = {variant: trace_futs[variant].result() for variant in load_variants}
        walls = {variant: wall_futs[variant].result() for variant in load_variants}
    commits = h5._load_commit_identities(traces)
    walked: list[WalkedEnter] = []
    for variant in load_variants:
        walked.extend(
            join_walked(
                variant,
                traces[variant],
                commits,
                labels,
                rosters,
                walls[variant],
            )
        )
    rule, metrics, scanned, survived = scan_rules(walked)
    survives = bool(metrics["survives"])
    return {
        "schema": SCHEMA,
        "status": "OK" if survives else "KILL",
        "survives": survives,
        "bounds": list(h5.BOUNDS),
        "seed": h5.SEED,
        "wall_clock_sec": wall_clock_sec,
        "workers": min(WORKERS, 6),
        "score_depth_first_on_side": 0.0,
        "kill_bar": {
            "stated_before_scan": True,
            "population": "pooled H3+H5+H7 walked event-name ENTERs",
            "remove_event_not_top2_gt": 0.5,
            "keep_top2_gt": 0.5,
            "rules_scanned": scanned,
            "rules_survived": survived,
        },
        "definitions": {
            "event_order": (
                "0-based arrival order. Count of events already formed in the "
                "same asset-day-phase cell before this name forms."
            ),
            "score_depth": (
                "Absolute score gap versus the prior same-side extreme among "
                "earlier-formed events. First event on that side is 0.0."
            ),
            "running_occupancy": (
                "Event count already flagged (eligibility = formed + 180s) "
                "before this name forms."
            ),
            "commit_event_rank": (
                "Event count already flagged by this name's eligibility second "
                "(formed + 180s). Running state, not final events_in_cell."
            ),
            "top2": (
                "Hindsight measurement label only. Fewer than two same-cell "
                "event labels strictly above this name at age 180."
            ),
            "veto": "Drop the walked ENTER when the single-field rule matches.",
            "overlay_backfill": "Ignored. Allowed only because this is a kill test.",
        },
        "sources": {
            "delayed_outcomes": h5._relative(h5.OUTCOME_CACHE),
            "component_matrix": h5._relative(h5.MATRIX),
            "component_matrix_receipt_sha256": matrix.receipt_sha256,
            "event_economics": h5._relative(h5.EVENT_RECEIPT),
            "event_oracle": h5._relative(h5.EXTREME_RECEIPT),
        },
        "event_receipt_parity": parity,
        "event_set": event_set,
        "separation": separation(events),
        "chosen_rule": _chosen_payload(rule, metrics),
        "overlay": overlay(walked, rule),
        "check_command": CHECK,
    }


def _write_receipt(value: Mapping[str, object]) -> None:
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    temporary = RECEIPT.with_name(f"{RECEIPT.name}.tmp.{os.getpid()}")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, RECEIPT)


def _summarize(receipt: Mapping[str, object]) -> str:
    rule = h5._mapping(receipt.get("chosen_rule", {}), "chosen_rule")
    return (
        f"receipt={h5._relative(RECEIPT)} status={receipt.get('status')} "
        f"survives={receipt.get('survives')} "
        f"rule={rule.get('field')}{rule.get('op')}{rule.get('threshold')} "
        f"wall_clock_sec={receipt.get('wall_clock_sec')}"
    )


def main() -> int:
    if sys.argv[1:]:
        raise ValueError(f"unsupported arguments {sys.argv[1:]}")
    started = time.perf_counter()
    try:
        receipt = build_receipt(0.0)
        receipt["wall_clock_sec"] = round(time.perf_counter() - started, 3)
    except h5.JoinUnavailable as exc:
        receipt = {
            "schema": SCHEMA,
            "status": "JOIN_UNAVAILABLE",
            "survives": False,
            "missing_key": exc.missing_key,
            "detail": exc.detail,
            "bounds": list(h5.BOUNDS),
            "seed": h5.SEED,
            "wall_clock_sec": round(time.perf_counter() - started, 3),
            "check_command": CHECK,
        }
        _write_receipt(receipt)
        print(_summarize(receipt))
        return 2
    _write_receipt(receipt)
    print(_summarize(receipt))
    return 0


if __name__ == "__main__":
    sys.exit(main())
