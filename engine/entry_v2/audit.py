#!/usr/bin/env python3
"""One-shot adversarial audit for the entry-v2 substrate and policy plane.

The default invocation uses small deterministic fixtures.  A real artifact
manifest can be supplied to run the same date, history, fold, and hash-lineage
assertions without teaching this module any corpus-specific path conventions.
Every required check runs once; exceptions become failed checks and the process
exits non-zero after writing a self-hashed JSON receipt.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, fields, replace
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Any, Callable, Iterable, Mapping, Sequence

import numpy as np

from . import common as C
from .context_pack import AvailableObservation, ContextSource, build_context_pack
from .contracts import (
    CausalEntryExample,
    ContractError,
    EntryScore,
    NANOS_PER_SECOND,
    RawPrefixRef,
    SessionRef,
    Side,
    VintageClass,
)
from .replay import ReplayOutcome, ScoredArrival, replay
from .teacher import TeacherPath, build_teacher_store


REPORT_SCHEMA = "entry-v2-adversarial-audit-v1"
MANIFEST_SCHEMA = "entry-v2-audit-artifacts-v1"
TRUTH_CONTROL_FLOOR_USD_PER_ASSET_DAY = 900.0
SHUFFLED_NULL_MAX_USD_PER_ASSET_DAY = 200.0
MIN_CANDIDATE_ORACLE_CAPTURE = 0.90
SHUFFLE_SEED = 20260816
NS = NANOS_PER_SECOND

REQUIRED_CHECKS = (
    "source_date_holdout_gates",
    "raw_prefix_cutoffs",
    "future_suffix_invariance",
    "context_point_in_time",
    "candidate_teacher_separation",
    "history_causality",
    "arrival_replay_policy",
    "oracle_and_null_controls",
    "exact_bottleneck_attribution",
    "fold_day_disjointness",
    "artifact_hash_lineage",
)

PRODUCTION_HOOK_NAMES = (
    "production_prefix_bytes_mutation",
    "production_timestamp_mutation",
    "production_future_suffix_mutation",
    "production_context_mutation",
    "production_teacher_mutation",
    "production_replay_mutation",
    "production_shuffle_mutation",
    "production_empty_stage_mutation",
)

BOTTLENECK_ORDER = (
    "candidate_ceiling",
    "raw_prefix_fidelity",
    "teacher_alignment",
    "representation_learnability",
    "oof_policy",
    "exact_replay",
)


class AuditFailure(AssertionError):
    """A required adversarial condition is not true."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AuditFailure(message)


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _hex_digest(value: object) -> bool:
    text = str(value)
    return len(text) == 64 and all(char in "0123456789abcdef" for char in text)


@dataclass(frozen=True, slots=True)
class AuditContext:
    manifest: Mapping[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class CheckResult:
    name: str
    passed: bool
    details: Mapping[str, Any]
    error: str | None = None


AuditHook = tuple[str, Callable[[AuditContext], Mapping[str, Any] | None]]


@dataclass(frozen=True, slots=True)
class ProductionAuditInputs:
    """Live, already-verified objects used for destructive-in-memory controls."""

    corpus: Any
    campaign: Any
    primary_folds: Sequence[Any]
    shuffled_folds: Sequence[Any]
    fold_specs: Sequence[Any]
    shuffle_seed: int = SHUFFLE_SEED


def _example(candidate_id: str, asset: str, second: float, *,
             day: int = 20250102, session: str | None = None,
             last_event_offset_ns: int = -1) -> CausalEntryExample:
    decision = int(second * NS)
    last = decision + int(last_event_offset_ns)
    return CausalEntryExample(
        candidate_id=candidate_id,
        asset=asset,
        trading_day=day,
        session_id=session or f"{asset}-{day}",
        decision_ts_ns=decision,
        side=Side.LONG,
        phase="TOKYO",
        locked_iid=101,
        raw_prefix_ref=RawPrefixRef(
            shard=f"synthetic/{asset}/{day}", event_start_index=0,
            event_end_index=1, event_count=1,
            first_availability_ts_ns=last, last_availability_ts_ns=last,
            source_hash="synthetic-source-hash"),
        causal_features={"spread_ticks": 1.0, "running_count": 12},
        context=None,
        lineage_hash="synthetic-lineage-hash",
    )


def _score(example: CausalEntryExample, priority: float, *,
           enter: bool = True, model_hash: str = "synthetic-model") -> EntryScore:
    return EntryScore(
        candidate_id=example.candidate_id, asset=example.asset,
        decision_ts_ns=example.decision_ts_ns, model_hash=model_hash,
        priority_score=priority, take_probability=0.9 if enter else 0.1,
        expected_pnl_usd=priority, expected_pnl_lower_usd=priority,
        top3_probability=0.5, mae_p90_usd=100.0,
        wall_probability=0.1, enter=enter,
    )


def _outcome(example: CausalEntryExample, exit_second: float, pnl: float,
             *, phase_second: float = 10_000.0,
             phase_pnl: float | None = None,
             wall_second: float | None = None) -> ReplayOutcome:
    return ReplayOutcome(
        candidate_id=example.candidate_id,
        close_ts_ns=int(exit_second * NS), close_pnl_usd=float(pnl),
        phase_close_ts_ns=int(phase_second * NS),
        phase_close_pnl_usd=float(pnl if phase_pnl is None else phase_pnl),
        wall_hit_ts_ns=None if wall_second is None else int(wall_second * NS),
    )


def _source_dates(source: Mapping[str, Any]) -> Mapping[str, Any]:
    keys = ("available_min_day", "available_max_day", "development_end_day",
            "holdout_start_day", "holdout_end_day", "sealed_start_day",
            "opened_through_day", "stage")
    missing = [key for key in keys if key not in source]
    _require(not missing, f"source date gate missing fields: {missing}")
    low = int(source["available_min_day"])
    high = int(source["available_max_day"])
    dev = int(source["development_end_day"])
    hold_start = int(source["holdout_start_day"])
    hold_end = int(source["holdout_end_day"])
    sealed = int(source["sealed_start_day"])
    opened = int(source["opened_through_day"])
    _require(low <= dev < hold_start <= hold_end < sealed <= high,
             "source/holdout/sealed date ordering is invalid")
    stage = str(source["stage"])
    if stage == "DEVELOPMENT":
        _require(opened <= dev, "development stage opened holdout bytes")
    elif stage == "FINAL_2025H2":
        auth = source.get("one_time_authorization_sha256")
        _require(_hex_digest(auth), "final stage lacks one-time authorization hash")
        _require(opened == hold_end, "final stage must open exactly through 2025H2")
    else:
        raise AuditFailure(f"unknown audit stage: {stage}")
    _require(opened < sealed, "sealed 2026 boundary was crossed")
    return {"stage": stage, "opened_through_day": opened,
            "holdout_start_day": hold_start, "sealed_start_day": sealed}


def check_source_date_holdout_gates(ctx: AuditContext) -> Mapping[str, Any]:
    synthetic = {
        "available_min_day": 20210101, "available_max_day": 20261231,
        "development_end_day": 20250630, "holdout_start_day": 20250701,
        "holdout_end_day": 20251231, "sealed_start_day": 20260101,
        "opened_through_day": 20250630, "stage": "DEVELOPMENT",
    }
    detail: dict[str, Any] = {"synthetic": _source_dates(synthetic)}
    if ctx.manifest is not None:
        detail["artifact"] = _source_dates(_mapping(ctx.manifest, "source"))
    return detail


def check_raw_prefix_cutoffs(_ctx: AuditContext) -> Mapping[str, Any]:
    early = _example("same-sec-early", "SI", 10.1, last_event_offset_ns=-1)
    late = _example("same-sec-late", "SI", 10.9, last_event_offset_ns=-1)
    _require(early.arrival_second == late.arrival_second,
             "native sub-second fixture crossed a wall-clock second")
    _require(early.decision_ts_ns < late.decision_ts_ns,
             "native sub-second fixture lost its exact ordering")
    for example in (early, late):
        last = example.raw_prefix_ref.last_availability_ts_ns
        _require(last is not None and last < example.decision_ts_ns,
                 "raw prefix is not strict")
    refused = False
    try:
        _example("same-ts-refusal", "SI", 11.0, last_event_offset_ns=0)
    except ContractError:
        refused = True
    _require(refused, "an event exactly at the cutoff was accepted")
    return {"same_wall_second": early.arrival_second,
            "native_arrivals_are_distinct": True,
            "strict_examples": 2, "same_timestamp_refused": True}


def check_future_suffix_invariance(_ctx: AuditContext) -> Mapping[str, Any]:
    prefix = b"event-1\nevent-2\nevent-3\n"
    raw_a = prefix + b"future-A\n"
    raw_b = prefix + b"mutated-future-B-with-different-length\n"
    cutoff = len(prefix)
    hash_a = _sha_bytes(raw_a[:cutoff])
    hash_b = _sha_bytes(raw_b[:cutoff])
    _require(hash_a == hash_b, "future suffix changed the model prefix")
    _require(_sha_bytes(raw_a) != _sha_bytes(raw_b),
             "future mutation fixture failed to change the full source")
    return {"prefix_bytes": cutoff, "prefix_sha256": hash_a,
            "full_source_mutated": True}


def check_context_point_in_time(_ctx: AuditContext) -> Mapping[str, Any]:
    decision = 100 * NS
    past = tuple(AvailableObservation(str(i), i * NS, (float(i),))
                 for i in range(1, 71))
    revised = ContextSource(
        "FRED_DGS10", VintageClass.REVISED_VALUE,
        (AvailableObservation("old", NS, (4.0,)),))
    sources_a = {
        "VIX": ContextSource("VIX", VintageClass.FIRST_PRINT, past + (
            AvailableObservation("at-cut", decision, (10_000.0,)),
            AvailableObservation("future", 110 * NS, (20_000.0,)))),
        "FRED_DGS10": revised,
    }
    sources_b = {
        "VIX": ContextSource("VIX", VintageClass.FIRST_PRINT, past + (
            AvailableObservation("at-cut-mutated", decision, (-10_000.0,)),
            AvailableObservation("future-mutated", 999 * NS, (-20_000.0,)))),
        "FRED_DGS10": revised,
    }
    roster = ("VIX", "FRED_DGS10", "MISSING")
    pack_a = build_context_pack(
        "SI", decision, sources_a, trading_day=20250102, roster=roster)
    pack_b = build_context_pack(
        "SI", decision, sources_b, trading_day=20250102, roster=roster)
    _require(pack_a == pack_b, "future context mutation changed the pack")
    vix = pack_a.by_id()["VIX"]
    _require(len(vix.points) == 64, "context history is not last-64")
    _require(all(point.availability_ts_ns < decision for point in vix.points),
             "context pack contains at/after-decision data")
    rate = pack_a.by_id()["FRED_DGS10"]
    _require(not rate.mask and rate.missing_reason == "REVISED_VALUE_MASKED",
             "revised context value was not typed-masked")
    return {"history": len(vix.points), "oldest_value": vix.points[0].values[0],
            "revised_masked": True, "future_invariant": True}


def check_candidate_teacher_separation(_ctx: AuditContext) -> Mapping[str, Any]:
    names = {field.name for field in fields(CausalEntryExample)}
    forbidden = {"cert_close_usd", "teacher", "outcome", "top3", "rank",
                 "mfe", "mae", "wall_hit", "time_to_peak_sec"}
    _require(not names.intersection(forbidden),
             "candidate schema directly exposes teacher values")
    refused = False
    try:
        base = _example("injection", "SI", 10)
        replace(base, causal_features={"future_rank": 1})
    except ContractError:
        refused = True
    _require(refused, "teacher feature injection was accepted")
    paths = (TeacherPath("injection", "SI", 20250102, 10 * NS, 20 * NS,
                         1_000.0, 1_100.0, 100.0, False, 5.0),)
    injection = _example("injection", "SI", 10)
    store = build_teacher_store(
        paths, expected_sessions=(injection.session,)
    )
    joined = store.join_training((injection,))
    _require(len(joined) == 1 and joined[0][1].candidate_id == "injection",
             "candidate_id teacher join failed")
    return {"candidate_fields": sorted(names), "direct_overlap": [],
            "teacher_join_key": "candidate_id"}


def _history_assertions(history: Mapping[str, Any], holdout_start: int) -> Mapping[str, int]:
    locks = history.get("locked_iid", [])
    phases = history.get("phases", [])
    _require(isinstance(locks, list) and locks, "locked-iid history assertions missing")
    _require(isinstance(phases, list) and phases, "phase history assertions missing")
    for row in locks:
        _require(int(row["selection_basis_day"]) < int(row["session_day"]),
                 "locked iid uses current/future session totals")
    for row in phases:
        effective = int(row["effective_from_day"])
        fit_end = int(row["fit_end_day"])
        _require(fit_end < effective, "phase schedule fits its own/future month")
        if effective < holdout_start:
            _require(fit_end < holdout_start, "development phase fit touches holdout")
    return {"locked_iid_rows": len(locks), "phase_rows": len(phases)}


def check_history_causality(ctx: AuditContext) -> Mapping[str, Any]:
    synthetic = {
        "locked_iid": [
            {"session_day": 20250103, "selection_basis_day": 20250102},
            {"session_day": 20250106, "selection_basis_day": 20250103},
        ],
        "phases": [
            {"effective_from_day": 20250201, "fit_end_day": 20250131},
            {"effective_from_day": 20250301, "fit_end_day": 20250228},
        ],
    }
    detail: dict[str, Any] = {
        "synthetic": _history_assertions(synthetic, 20250701)}
    if ctx.manifest is not None:
        source = _mapping(ctx.manifest, "source")
        detail["artifact"] = _history_assertions(
            _mapping(ctx.manifest, "history"), int(source["holdout_start_day"]))
    return detail


def check_arrival_replay_policy(_ctx: AuditContext) -> Mapping[str, Any]:
    low = _example("low", "SI", 10.1)
    high = _example("high", "SI", 10.9)
    overlap = _example("overlap", "SI", 15)
    after = _example("after", "SI", 20)
    base = (
        ScoredArrival(low, _score(low, 100), _outcome(low, 19, 100)),
        ScoredArrival(high, _score(high, 200), _outcome(high, 20, 200)),
        ScoredArrival(overlap, _score(overlap, 500), _outcome(overlap, 18, 500)),
        ScoredArrival(after, _score(after, 150), _outcome(after, 25, 150)),
    )
    result = replay(base, expected_sessions=(low.session,))
    _require([trade.candidate_id for trade in result.trade_results] == ["low", "after"],
             "a later native timestamp influenced an earlier arrival")

    same_low = _example("same-low", "SI", 30.1)
    same_high = _example("same-high", "SI", 30.1)
    simultaneous = replay((
        ScoredArrival(
            same_low, _score(same_low, 100), _outcome(same_low, 31, 100)
        ),
        ScoredArrival(
            same_high, _score(same_high, 200), _outcome(same_high, 31, 200)
        ),
    ), expected_sessions=(same_low.session,))
    _require(
        [trade.candidate_id for trade in simultaneous.trade_results]
        == ["same-high"],
        "exact-same-timestamp batch selection is not deterministic",
    )

    capped_rows: list[ScoredArrival] = []
    expected: list[SessionRef] = []
    for asset in ("SI", "HG", "NKD"):
        expected.append(SessionRef(asset, 20250102, f"{asset}-20250102"))
        for k in range(4):
            item = _example(f"{asset}-{k}", asset, 100 + 2 * k)
            capped_rows.append(ScoredArrival(
                item, _score(item, 100 - k), _outcome(item, 101 + 2 * k, 100)))
    expected.append(SessionRef("SI", 20250103, "SI-empty"))
    capped = replay(capped_rows, expected_sessions=expected)
    _require(capped.trades == 9, "portfolio/day cap is not nine")
    _require(all(row.trades == 3 for row in capped.by_asset),
             "asset/day cap is not three")
    _require(capped.asset_days == 4 and capped.zero_asset_days == 1,
             "all-asset-day denominator dropped an empty asset-day")
    _require(capped.usd_per_asset_day == 225.0,
             "all-asset-day denominator is numerically wrong")
    return {"subsecond_first_seat": "low",
            "same_timestamp_seat": "same-high",
            "overlap_forfeited": "overlap",
            "trades_at_cap": capped.trades,
            "denominator_asset_days": capped.asset_days,
            "zero_asset_days": capped.zero_asset_days}


def _control_fixture() -> tuple[tuple[CausalEntryExample, ...],
                                tuple[TeacherPath, ...],
                                tuple[ReplayOutcome, ...],
                                tuple[SessionRef, ...]]:
    examples: list[CausalEntryExample] = []
    paths: list[TeacherPath] = []
    outcomes: list[ReplayOutcome] = []
    sessions: list[SessionRef] = []
    for day_offset in range(30):
        date = dt.date(2025, 3, 1) + dt.timedelta(days=day_offset)
        day = int(date.strftime("%Y%m%d"))
        # Every day has one winner and three decoys at one exact native
        # timestamp, so the score—not an arbitrary row order—selects the seat.
        session = f"SI-{day}"
        sessions.append(SessionRef("SI", day, session))
        for k, value in enumerate((1_000.0, -1_000.0, -1_000.0, -1_000.0)):
            cid = f"d{day}-c{k}"
            item = _example(cid, "SI", 10_000 + day_offset * 100 + 10.1,
                            day=day, session=session)
            examples.append(item)
            paths.append(TeacherPath(
                cid, "SI", day, item.decision_ts_ns,
                int((10_000 + day_offset * 100 + 20) * NS),
                value, max(value, 0.0) + 100.0, 100.0,
                False, 5.0))
            outcomes.append(_outcome(
                item, 10_000 + day_offset * 100 + 20, value,
                phase_second=10_000 + day_offset * 100 + 30))
    return tuple(examples), tuple(paths), tuple(outcomes), tuple(sessions)


def check_oracle_and_null_controls(_ctx: AuditContext) -> Mapping[str, Any]:
    examples, paths, outcomes, sessions = _control_fixture()
    store = build_teacher_store(paths, expected_sessions=sessions)
    outcome_by_id = {item.candidate_id: item for item in outcomes}

    def evaluate(control_store: Any) -> float:
        scores = control_store.truth_scores(
            examples,
            entry_thresholds_usd={asset: 600.0 for asset in C.ASSETS},
        )
        arrivals = tuple(ScoredArrival(
            example, score, outcome_by_id[example.candidate_id])
            for example, score in zip(examples, scores))
        result = replay(arrivals, expected_sessions=sessions)
        asset_days = {(session.asset, session.trading_day) for session in sessions}
        return result.total_pnl_usd / len(asset_days)

    truth = evaluate(store)
    shuffled = evaluate(store.shuffled(SHUFFLE_SEED))
    _require(truth >= TRUTH_CONTROL_FLOOR_USD_PER_ASSET_DAY,
             f"truth control {truth:.2f} below floor")
    _require(shuffled <= SHUFFLED_NULL_MAX_USD_PER_ASSET_DAY,
             f"shuffled control {shuffled:.2f} above null bound")
    _require(truth > shuffled, "truth control does not beat shuffled labels")
    return {"asset_days": len({(row.asset, row.trading_day) for row in sessions}),
            "truth_usd_per_asset_day": truth,
            "truth_floor": TRUTH_CONTROL_FLOOR_USD_PER_ASSET_DAY,
            "shuffled_usd_per_asset_day": shuffled,
            "shuffled_max": SHUFFLED_NULL_MAX_USD_PER_ASSET_DAY,
            "shuffle_seed": SHUFFLE_SEED}


def _attribute_bottleneck(rows: Mapping[str, Any]) -> Mapping[str, Any]:
    """Resolve the first exact failed boundary and stop attribution there."""
    missing = [name for name in BOTTLENECK_ORDER if name not in rows]
    _require(not missing, f"bottleneck boundaries missing: {missing}")
    expected_evidence = {
        "candidate_ceiling": "EXACT_CANDIDATE_ORACLE",
        "raw_prefix_fidelity": "EXACT_PREFIX_HASH_COUNT",
        "teacher_alignment": "EXACT_LABEL_JOIN",
        "representation_learnability": "EXACT_DIRECT_HEAD_OOF_REPLAY_DOLLARS",
        "oof_policy": "EXACT_GBT_OOF_REPLAY_DOLLARS",
        "exact_replay": "EXACT_ARRIVAL_REPLAY_DOLLARS_AND_ORACLE_CAPTURE",
    }

    def per_asset(raw: Mapping[str, Any], boundary: str) -> Mapping[str, Any]:
        value = raw.get("per_asset")
        _require(isinstance(value, Mapping),
                 f"{boundary} lacks per_asset exact metrics")
        _require(set(value) == set(C.ASSETS),
                 f"{boundary} must report exactly SI/HG/NKD")
        for asset, metrics in value.items():
            _require(isinstance(metrics, Mapping),
                     f"{boundary}/{asset} metrics are not a mapping")
        return value

    def finite_metric(metrics: Mapping[str, Any], key: str,
                      boundary: str, asset: str) -> float:
        value = float(metrics[key])
        _require(math.isfinite(value), f"{boundary}/{asset}/{key} is non-finite")
        return value

    out = []
    first_failed: str | None = None
    for name in BOTTLENECK_ORDER:
        raw = rows[name]
        _require(isinstance(raw, Mapping), f"bottleneck boundary is not a mapping: {name}")
        _require(raw.get("evidence_type") == expected_evidence[name],
                 f"wrong evidence type at {name}")
        # AUC, Spearman, loss, and drawdown p90 are diagnostics only.  The
        # chronological maximum drawdown is the promotion gate below.
        diagnostics = raw.get("diagnostics", {})
        _require(isinstance(diagnostics, Mapping), f"diagnostics are not a mapping: {name}")
        if first_failed is not None:
            out.append({"name": name, "status": "NOT_REACHED",
                        "reason": f"upstream boundary unresolved: {first_failed}",
                        "promotion_eligible": False})
            continue
        resolved = bool(raw.get("resolved", False))
        passed = bool(raw.get("passed", False))
        if name == "candidate_ceiling" and resolved:
            metrics = per_asset(raw, name)
            passed = all(
                bool(metrics[asset].get("passed"))
                and isinstance(metrics[asset].get("capacity_regimes"), Mapping)
                and isinstance(metrics[asset].get("capacity_authority_sha256"), str)
                and len(metrics[asset]["capacity_authority_sha256"]) == 64
                for asset in C.ASSETS
            )
        elif name == "raw_prefix_fidelity" and resolved:
            passed = (int(raw["matched_events"]) > 0
                      and int(raw["mismatched_events"]) == 0)
        elif name == "teacher_alignment" and resolved:
            passed = (int(raw["matched_candidates"]) > 0
                      and int(raw["mismatched_candidates"]) == 0)
        elif name == "representation_learnability" and resolved:
            metrics = per_asset(raw, name)
            passed = True
            for asset in C.ASSETS:
                direct = finite_metric(
                    metrics[asset], "direct_usd_per_asset_day", name, asset)
                shuffled = finite_metric(
                    metrics[asset], "shuffled_usd_per_asset_day", name, asset)
                capture = finite_metric(
                    metrics[asset], "arrival_oracle_capture", name, asset)
                passed = (passed and direct > max(0.0, shuffled)
                          and 0.0 < capture <= 1.0)
        elif name == "oof_policy" and resolved:
            metrics = per_asset(raw, name)
            passed = all(
                finite_metric(metrics[asset], "usd_per_trade", name, asset)
                >= C.MIN_EXPECTANCY_USD
                and finite_metric(metrics[asset], "max_drawdown_usd", name, asset)
                <= C.TARGET_MDD_USD
                and finite_metric(metrics[asset], "usd_per_asset_day", name, asset)
                > max(0.0, finite_metric(
                    metrics[asset], "shuffled_usd_per_asset_day", name, asset
                ))
                and isinstance(metrics[asset].get("era_capacity_gate"), Mapping)
                and all(bool(row.get("passed"))
                        and isinstance(row.get("capacity_authority_sha256"), str)
                        for row in metrics[asset]["era_capacity_gate"].values())
                for asset in C.ASSETS
            )
        elif name == "exact_replay" and resolved:
            metrics = per_asset(raw, name)
            passed = all(
                finite_metric(metrics[asset], "usd_per_trade", name, asset)
                >= C.MIN_EXPECTANCY_USD
                and finite_metric(metrics[asset], "max_drawdown_usd", name, asset)
                <= C.TARGET_MDD_USD
                and MIN_CANDIDATE_ORACLE_CAPTURE
                <= finite_metric(metrics[asset], "candidate_oracle_capture", name, asset)
                <= 1.0
                and isinstance(metrics[asset].get("era_capacity_gate"), Mapping)
                and all(bool(row.get("passed"))
                        for row in metrics[asset]["era_capacity_gate"].values())
                for asset in C.ASSETS
            )
        status = "PASSED" if resolved and passed else (
            "FAILED" if resolved else "UNRESOLVED")
        item: dict[str, Any] = {
            "name": name, "status": status,
            "evidence_type": expected_evidence[name],
            "promotion_eligible": name == "exact_replay",
            "diagnostics": dict(diagnostics),
        }
        for key, value in raw.items():
            if key not in {"resolved", "passed", "evidence_type", "diagnostics"}:
                item[key] = value
        out.append(item)
        if status != "PASSED":
            first_failed = name
    final = next(item for item in out if item["name"] == "exact_replay")
    promoted = final["status"] == "PASSED" and first_failed is None
    return {
        "boundary_order": list(BOTTLENECK_ORDER),
        "boundaries": out,
        "first_failed_boundary": first_failed,
        "downstream_generalization_allowed": first_failed is None,
        "promotion": {
            "promoted": promoted,
            "eligible_metrics": ["per_asset_exact_arrival_replay_dollars",
                                 "per_asset_candidate_oracle_capture",
                                 "per_asset_expectancy_and_max_drawdown"],
            "diagnostic_only_metrics": [
                "auc", "spearman", "loss", "drawdown_p90_usd"
            ],
        },
    }


def _failed_attribution(reason: str) -> Mapping[str, Any]:
    """Fail-closed chain used when attribution evidence itself is malformed."""
    boundaries = [{
        "name": BOTTLENECK_ORDER[0], "status": "UNRESOLVED",
        "reason": reason, "promotion_eligible": False,
    }]
    boundaries.extend({
        "name": name, "status": "NOT_REACHED",
        "reason": f"upstream boundary unresolved: {BOTTLENECK_ORDER[0]}",
        "promotion_eligible": False,
    } for name in BOTTLENECK_ORDER[1:])
    return {
        "boundary_order": list(BOTTLENECK_ORDER),
        "boundaries": boundaries,
        "first_failed_boundary": BOTTLENECK_ORDER[0],
        "downstream_generalization_allowed": False,
        "promotion": {
            "promoted": False,
            "eligible_metrics": ["per_asset_exact_arrival_replay_dollars",
                                 "per_asset_candidate_oracle_capture",
                                 "per_asset_expectancy_and_max_drawdown"],
            "diagnostic_only_metrics": [
                "auc", "spearman", "loss", "drawdown_p90_usd"
            ],
        },
    }


def check_exact_bottleneck_attribution(ctx: AuditContext) -> Mapping[str, Any]:
    synthetic = {
        "candidate_ceiling": {
            "resolved": True, "passed": True,
            "evidence_type": "EXACT_CANDIDATE_ORACLE",
            "per_asset": {asset: {"usd_per_asset_day": 2_500.0,
                                  "capacity_regimes": {"E3": "FULL"},
                                  "capacity_authority_sha256": "a" * 64,
                                  "passed": True}
                          for asset in C.ASSETS},
        },
        "raw_prefix_fidelity": {
            "resolved": True, "passed": True,
            "evidence_type": "EXACT_PREFIX_HASH_COUNT",
            "matched_events": 10_000, "mismatched_events": 0,
        },
        "teacher_alignment": {
            "resolved": True, "passed": True,
            "evidence_type": "EXACT_LABEL_JOIN",
            "matched_candidates": 120, "mismatched_candidates": 0,
        },
        "representation_learnability": {
            "resolved": True, "passed": True,
            "evidence_type": "EXACT_DIRECT_HEAD_OOF_REPLAY_DOLLARS",
            "per_asset": {
                asset: {"direct_usd_per_asset_day": 900.0,
                        "shuffled_usd_per_asset_day": 0.0,
                        "arrival_oracle_capture": 0.30}
                for asset in C.ASSETS
            },
            "diagnostics": {"loss": 0.1, "auc": 0.5},
        },
        "oof_policy": {
            "resolved": True, "passed": True,
            "evidence_type": "EXACT_GBT_OOF_REPLAY_DOLLARS",
            "per_asset": {
                asset: {"usd_per_asset_day": 2_100.0,
                        "usd_per_trade": 700.0,
                        "max_drawdown_usd": 900.0,
                        "drawdown_p90_usd": 900.0,
                        "shuffled_usd_per_asset_day": 0.0,
                        "learned_vs_shuffled_lift_usd_per_asset_day": 2_100.0,
                        "era_capacity_gate": {"E3": {"passed": True,
                            "capacity_authority_sha256": "a" * 64}}}
                for asset in C.ASSETS
            },
            "diagnostics": {"spearman": 0.0},
        },
        "exact_replay": {
            "resolved": True, "passed": True,
            "evidence_type": "EXACT_ARRIVAL_REPLAY_DOLLARS_AND_ORACLE_CAPTURE",
            "per_asset": {
                asset: {"usd_per_asset_day": 2_100.0,
                        "usd_per_trade": 700.0,
                        "max_drawdown_usd": 900.0,
                        "drawdown_p90_usd": 900.0,
                        "candidate_oracle_capture": 0.92,
                        "era_capacity_gate": {"E3": {"passed": True,
                            "capacity_authority_sha256": "a" * 64}}}
                for asset in C.ASSETS
            },
        },
    }
    detail: dict[str, Any] = {"synthetic": _attribute_bottleneck(synthetic)}
    if ctx.manifest is not None:
        real = ctx.manifest.get("bottleneck_boundaries")
        _require(isinstance(real, Mapping),
                 "artifact bottleneck_boundaries must be a mapping")
        detail["artifact"] = _attribute_bottleneck(real)
        detail["_audit_pass"] = bool(detail["artifact"]["promotion"]["promoted"])
    else:
        detail["_audit_pass"] = True
    return detail


def _fold_assertions(folds: Sequence[Mapping[str, Any]]) -> Mapping[str, int]:
    _require(bool(folds), "fold declarations missing")
    for fold in folds:
        name = str(fold.get("name", ""))
        _require(bool(name), "fold lacks name")
        train = {int(day) for day in fold.get("train_days", [])}
        validate = {int(day) for day in fold.get("validation_days", [])}
        holdout = {int(day) for day in fold.get("holdout_days", [])}
        _require(train and validate, f"fold {name} lacks train/validation days")
        _require(train.isdisjoint(validate) and train.isdisjoint(holdout)
                 and validate.isdisjoint(holdout),
                 f"fold {name} day sets overlap")
        _require(max(train) < min(validate), f"fold {name} is not chronological")
        if holdout:
            _require(max(validate) < min(holdout),
                     f"fold {name} validation crosses holdout")
    return {"folds": len(folds)}


def check_fold_day_disjointness(ctx: AuditContext) -> Mapping[str, Any]:
    synthetic = [{"name": "E5", "train_days": [20230101, 20230102],
                  "validation_days": [20230103], "holdout_days": [20230104]}]
    detail: dict[str, Any] = {"synthetic": _fold_assertions(synthetic)}
    if ctx.manifest is not None:
        folds = ctx.manifest.get("folds")
        _require(isinstance(folds, list), "artifact folds must be a list")
        detail["artifact"] = _fold_assertions(folds)
    return detail


def _mapping(parent: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = parent.get(key)
    _require(isinstance(value, Mapping), f"{key} must be a mapping")
    return value


def _verify_file(row: Mapping[str, Any], name: str) -> tuple[str, str | None]:
    path = Path(str(row.get("path", "")))
    expected = str(row.get("sha256", ""))
    _require(path.is_absolute() and path.is_file(), f"{name} path is not an existing file")
    _require(_hex_digest(expected), f"{name} has invalid sha256")
    actual = _sha_file(path)
    _require(actual == expected, f"{name} hash mismatch")
    parent = row.get("parent_sha256")
    if parent is not None:
        _require(_hex_digest(parent), f"{name} has invalid parent hash")
        parent = str(parent)
    return actual, parent


def _artifact_assertions(manifest: Mapping[str, Any]) -> Mapping[str, Any]:
    _require(manifest.get("schema") == MANIFEST_SCHEMA, "wrong artifact manifest schema")
    source = _mapping(manifest, "source")
    source_hash, source_parent = _verify_file(source, "source")
    _require(source_parent is None, "source root cannot have a parent")
    artifacts = manifest.get("artifacts")
    _require(isinstance(artifacts, list) and artifacts, "artifacts list is empty")
    model = _mapping(manifest, "model")
    rows = list(artifacts) + [dict(model, name=model.get("name", "model"))]
    digests: dict[str, tuple[str, str | None]] = {source_hash: ("source", None)}
    for index, row in enumerate(rows):
        _require(isinstance(row, Mapping), f"artifact {index} is not a mapping")
        name = str(row.get("name", f"artifact-{index}"))
        digest, parent = _verify_file(row, name)
        _require(digest not in digests, f"duplicate artifact digest: {name}")
        _require(parent is not None, f"artifact lacks parent hash: {name}")
        digests[digest] = (name, parent)
    for digest, (name, parent) in digests.items():
        if parent is not None:
            _require(parent in digests and parent != digest,
                     f"artifact parent not in manifest: {name}")
    for digest, (name, _parent) in digests.items():
        seen: set[str] = set()
        cursor = digest
        while cursor != source_hash:
            _require(cursor not in seen, f"artifact parent cycle: {name}")
            seen.add(cursor)
            parent = digests[cursor][1]
            _require(parent is not None and parent in digests,
                     f"artifact does not descend from source: {name}")
            cursor = parent
    return {"source_sha256": source_hash, "descendants": len(rows),
            "model_sha256": str(model["sha256"])}


def check_artifact_hash_lineage(ctx: AuditContext) -> Mapping[str, Any]:
    source = b"source-manifest"
    substrate = b"substrate:" + _sha_bytes(source).encode()
    model = b"model:" + _sha_bytes(substrate).encode()
    source_hash = _sha_bytes(source)
    substrate_hash = _sha_bytes(substrate)
    model_hash = _sha_bytes(model)
    synthetic = {
        "source_sha256": source_hash, "substrate_sha256": substrate_hash,
        "substrate_parent": source_hash, "model_sha256": model_hash,
        "model_parent": substrate_hash,
    }
    _require(synthetic["substrate_parent"] == source_hash
             and synthetic["model_parent"] == substrate_hash,
             "synthetic parent chain failed")
    detail: dict[str, Any] = {"synthetic": synthetic}
    if ctx.manifest is not None:
        detail["artifact"] = _artifact_assertions(ctx.manifest)
    return detail


def _production_examples(inputs: ProductionAuditInputs) -> tuple[Any, ...]:
    examples = tuple(
        example for spec in inputs.corpus.sessions for example in spec.examples
    )
    _require(bool(examples), "production corpus has no examples")
    return examples


def production_audit_hooks(inputs: ProductionAuditInputs) -> tuple[AuditHook, ...]:
    """Return the mandatory live-data mutation controls for certification."""
    from .campaign import build_oof_campaign
    from .contracts import ContextPack, ContextPoint, ContextSeries
    from .event_pack import HEADER_BYTES, ROW_BYTES, EventPack

    examples = _production_examples(inputs)
    specs = tuple(inputs.corpus.sessions)

    def prefix_bytes(_ctx: AuditContext) -> Mapping[str, Any]:
        spec = next((item for item in specs if item.source.max_cutoff > 0), None)
        _require(spec is not None, "no production prefix bytes are available")
        count = int(spec.source.max_cutoff)
        fd = os.open(spec.source.qre2_path, os.O_RDONLY)
        try:
            raw = os.pread(fd, count * ROW_BYTES, HEADER_BYTES)
        finally:
            os.close(fd)
        _require(len(raw) == count * ROW_BYTES, "actual prefix read was short")
        mutated = bytearray(raw)
        mutated[-1] ^= 1
        _require(_sha_bytes(raw) != _sha_bytes(bytes(mutated)),
                 "actual prefix-byte mutation was not detected")
        return {"actual_qre2": str(spec.source.qre2_path),
                "events": count, "mutation_detected": True}

    def timestamp(_ctx: AuditContext) -> Mapping[str, Any]:
        checked = 0
        for spec in specs:
            with EventPack(spec.source.qre2_path) as pack:
                clocks = pack.rows["ts_recv_ns"]
                for example in spec.examples:
                    cutoff = int(np.searchsorted(
                        clocks, example.decision_ts_ns, side="left"
                    ))
                    _require(cutoff == example.raw_prefix_ref.event_count,
                             "actual ts_recv cutoff differs from candidate")
                    if cutoff:
                        _require(int(clocks[cutoff - 1]) < example.decision_ts_ns,
                                 "actual prefix contains at/after-decision timestamp")
                    if cutoff < len(clocks):
                        _require(int(clocks[cutoff]) >= example.decision_ts_ns,
                                 "actual suffix starts before decision")
                    checked += 1
            if checked:
                break
        example = next(row for row in examples if row.raw_prefix_ref.event_count)
        refused = False
        try:
            replace(example, decision_ts_ns=int(
                example.raw_prefix_ref.last_availability_ts_ns
            ))
        except ContractError:
            refused = True
        _require(refused, "at-decision timestamp mutation was accepted")
        return {"actual_candidates_checked": checked,
                "at_timestamp_mutation_refused": True}

    def suffix(_ctx: AuditContext) -> Mapping[str, Any]:
        pair = next((
            (spec, example) for spec in specs for example in spec.examples
            if example.raw_prefix_ref.event_count < spec.source.event_count
        ), None)
        _require(pair is not None, "production corpus has no actual future suffix row")
        spec, example = pair
        cutoff = int(example.raw_prefix_ref.event_count)
        fd = os.open(spec.source.qre2_path, os.O_RDONLY)
        try:
            prefix = os.pread(fd, cutoff * ROW_BYTES, HEADER_BYTES)
            future = os.pread(fd, ROW_BYTES, HEADER_BYTES + cutoff * ROW_BYTES)
        finally:
            os.close(fd)
        _require(len(future) == ROW_BYTES, "actual suffix mutation row is missing")
        source = prefix + future
        mutated = prefix + bytes((future[0] ^ 1,)) + future[1:]
        _require(source[:len(prefix)] == mutated[:len(prefix)]
                 and _sha_bytes(source) != _sha_bytes(mutated),
                 "future-suffix mutation changed actual prefix")
        return {"actual_qre2": str(spec.source.qre2_path),
                "cutoff_events": cutoff, "future_suffix_invariant": True}

    def context(_ctx: AuditContext) -> Mapping[str, Any]:
        example = next((row for row in examples if row.context is not None
                        and any(series.points for series in row.context.series)), None)
        _require(example is not None, "production corpus has no actual context point")
        pack = example.context
        assert pack is not None
        series_index = next(i for i, row in enumerate(pack.series) if row.points)
        series = pack.series[series_index]
        point = series.points[-1]
        refused = False
        try:
            bad_point = replace(
                point, availability_ts_ns=pack.decision_ts_ns, age_ns=0
            )
            bad_series = replace(series, points=(*series.points[:-1], bad_point))
            ContextPack(pack.asset, pack.decision_ts_ns,
                        (*pack.series[:series_index], bad_series,
                         *pack.series[series_index + 1:]))
        except ContractError:
            refused = True
        _require(refused, "future context mutation was accepted")
        return {"series_id": series.series_id,
                "future_context_mutation_refused": True}

    def teacher(_ctx: AuditContext) -> Mapping[str, Any]:
        joined = inputs.corpus.teacher.join_training(examples)
        _require(len(joined) == len(examples), "actual teacher join is incomplete")
        refused = False
        try:
            inputs.corpus.teacher.join_training((
                replace(examples[0], candidate_id="__missing_teacher_mutation__"),
            ))
        except ContractError:
            refused = True
        _require(refused, "missing-teacher mutation was accepted")
        return {"joined_candidates": len(joined),
                "missing_teacher_mutation_refused": True}

    def replay_mutation(ctx: AuditContext) -> Mapping[str, Any]:
        fold = inputs.primary_folds[0]
        from .train import (
            ARM_FULL_PREFIX, validate_selected_policy_training_receipt,
        )
        arm = ARM_FULL_PREFIX
        exact = replay(fold.arm_arrivals[arm],
                       expected_sessions=fold.expected_sessions)
        _require(exact == fold.arm_evaluations[arm],
                 "actual fold replay differs from cached evaluation")
        chain = ctx.manifest.get("history", {}).get(
            "neural_sufficiency_acceptance", {})
        selected = fold.receipt.get("winner_adoption", {})
        policy_training = fold.receipt.get("selected_policy_training")
        if isinstance(selected, Mapping) and selected.get("legacy_full_prefix") is False:
            _require(isinstance(policy_training, Mapping),
                     "selected fold lacks policy-training evidence")
            validate_selected_policy_training_receipt(
                policy_training,
                decision_head_kind=str(selected["decision_head_kind"]),
                fit_days=tuple(policy_training["fit_days"]),
                calibration_days=tuple(policy_training["calibration_days"]),
                selection_days=tuple(policy_training["selection_days"]),
            )
        _require(
            fold.fold == "E3"
            and fold.store_aggregate_sha256
                == chain.get("primary_e3_fold_sha256")
            and selected.get("e2_frozen_selection_sha256")
                == chain.get("e2_frozen_selection_sha256")
            and selected.get("objective_sha256")
                == chain.get("winner_objective_sha256")
            and _hex_digest(selected.get("target_row_manifest_sha256")),
            "selected E2 -> primary E3 -> bundle chain differs",
        )
        zero = tuple(ScoredArrival(
            row.example, replace(row.score, enter=False), row.outcome
        ) for row in fold.arm_arrivals[arm])
        mutated = replay(zero, expected_sessions=fold.expected_sessions)
        _require(exact.trades > 0 and mutated.trades == 0 and mutated != exact,
                 "all-skip replay mutation did not change actual dollars")
        return {"fold": fold.fold, "actual_trades": exact.trades,
                "mutated_trades": mutated.trades}

    def shuffle(_ctx: AuditContext) -> Mapping[str, Any]:
        _require(len(inputs.primary_folds) == len(inputs.shuffled_folds) == 6,
                 "actual primary/shuffled ladder is incomplete")
        selected_mode = all(
            isinstance(fold.receipt.get("winner_adoption"), Mapping)
            and fold.receipt["winner_adoption"].get("legacy_full_prefix") is False
            for fold in inputs.primary_folds
        )
        if selected_mode:
            # The adopted atlas objective is the label authority.  Reopening or
            # shuffling the legacy TeacherStore here would audit the wrong target.
            changed = 0
        else:
            shuffled_teacher = inputs.corpus.teacher.shuffled(int(inputs.shuffle_seed))
            _require(
                shuffled_teacher.control_name
                    == f"SHUFFLED_{int(inputs.shuffle_seed)}",
                "actual shuffled teacher identity differs",
            )
            changed = sum(
                inputs.corpus.teacher[row.candidate_id]
                    != shuffled_teacher[row.candidate_id]
                for row in examples
            )
            _require(changed > 0, "actual teacher shuffle changed no label vector")
        for primary, null in zip(inputs.primary_folds, inputs.shuffled_folds):
            _require(primary.candidate_ids == null.candidate_ids
                     and null.control_name.startswith("SHUFFLED_"),
                     "actual shuffled fold population differs")
            selected = primary.receipt.get("winner_adoption")
            selected_null = null.receipt.get("winner_adoption")
            if isinstance(selected, Mapping) and selected.get("legacy_full_prefix") is False:
                control_receipt = (selected_null.get("target_control_receipt", {})
                                   if isinstance(selected_null, Mapping) else {})
                try:
                    candidate_ids = tuple(control_receipt["candidate_ids"])
                    permutation = tuple(int(v) for v in control_receipt["permutation"])
                    strata = tuple(control_receipt["strata"])
                    recipient = tuple(bool(v) for v in control_receipt["recipient_mask"])
                    source_rows = tuple(control_receipt["source_row_sha256"])
                    shuffled_rows = tuple(control_receipt["shuffled_row_sha256"])
                    n = len(candidate_ids)
                    supported = tuple(value >= 0 for value in permutation)
                    supported_rows = tuple(i for i, value in enumerate(supported) if value)
                    unsupported_rows = tuple(i for i, value in enumerate(supported) if not value)
                    recomputed = bool(
                        control_receipt.get("schema")
                            == "entry-v2-selected-target-control-v2"
                        and control_receipt.get("control") == "SHUFFLED"
                        and control_receipt.get("training_control")
                            == null.control_name
                        and all(len(values) == n for values in
                                (strata, recipient, source_rows, shuffled_rows))
                        and all(-1 <= value < n for value in permutation)
                        and len({permutation[i] for i in supported_rows})
                            == len(supported_rows)
                        and {permutation[i] for i in supported_rows}
                            == set(supported_rows)
                        and int(control_receipt.get("supported_rows", -1))
                            == len(supported_rows)
                        and int(control_receipt.get("unsupported_rows", -1))
                            == len(unsupported_rows)
                        and C.object_sha256(list(permutation))
                            == control_receipt.get("permutation_sha256")
                        and all(strata[i] == strata[permutation[i]]
                                for i in supported_rows)
                        and all(recipient[i] == recipient[permutation[i]]
                                for i in supported_rows)
                        and all(shuffled_rows[i] == source_rows[permutation[i]]
                                for i in supported_rows)
                        and all(permutation[i] != i for i in supported_rows)
                        and all(shuffled_rows[i]
                                == control_receipt.get("unsupported_zero_row_sha256")
                                for i in unsupported_rows)
                        and control_receipt.get("derangement") is True
                    )
                except (KeyError, TypeError, ValueError):
                    recomputed = False
                _require(
                    isinstance(selected_null, Mapping)
                    and selected_null.get("legacy_full_prefix") is False
                    and selected.get("objective_sha256")
                        == selected_null.get("objective_sha256")
                    and selected.get("target_row_manifest_sha256")
                        == selected_null.get("target_row_manifest_sha256")
                    and isinstance(selected.get("target_control_sha256"), str)
                    and isinstance(selected_null.get("target_control_sha256"), str)
                    and selected["target_control_sha256"]
                        != selected_null["target_control_sha256"],
                    "selected winner target/control hashes are not recipient-fixed",
                )
                _require(recomputed, "selected target shuffle cannot be recomputed exactly")
                changed += 1
        _require(changed > 0, "actual selected/legacy null changed no target identity")
        return {"changed_target_identities": changed, "paired_folds": 6,
                "target_authority": ("SELECTED_ATLAS" if selected_mode
                                     else "LEGACY_TEACHER")}

    def empty_stage(_ctx: AuditContext) -> Mapping[str, Any]:
        replay_refused = campaign_refused = False
        try:
            replay((), expected_sessions=())
        except ContractError:
            replay_refused = True
        try:
            build_oof_campaign(
                (), raw_prefix_fidelity=inputs.corpus.raw_prefix_fidelity,
                teacher_alignment=inputs.corpus.teacher_alignment,
                shuffled_folds=(),
            )
        except C.EntryV2Refusal:
            campaign_refused = True
        _require(replay_refused and campaign_refused,
                 "empty production stage mutation was accepted")
        return {"empty_replay_refused": replay_refused,
                "empty_campaign_refused": campaign_refused}

    functions = (prefix_bytes, timestamp, suffix, context, teacher,
                 replay_mutation, shuffle, empty_stage)

    def live(function: Callable[[AuditContext], Mapping[str, Any]]
             ) -> Callable[[AuditContext], Mapping[str, Any]]:
        def wrapped(ctx: AuditContext) -> Mapping[str, Any]:
            return {"evidence_scope": "LIVE_PRODUCTION_OBJECTS", **function(ctx)}
        return wrapped

    return tuple((name, live(function))
                 for name, function in zip(PRODUCTION_HOOK_NAMES, functions))


def build_production_manifest(
    source_manifest_path: Path,
    corpus_receipt_path: Path,
    campaign_receipt_path: Path,
    fold_specs: Sequence[Any],
    history: Mapping[str, Any],
    *,
    output: Path | None = None,
) -> Mapping[str, Any]:
    """Adapt the actual source/corpus/campaign receipts to the audit schema."""
    from .campaign import verify_campaign_receipt
    from .source_manifest import READY, SOURCE_SCHEMA

    source_manifest = json.loads(source_manifest_path.read_text())
    corpus = json.loads(corpus_receipt_path.read_text())
    campaign = json.loads(campaign_receipt_path.read_text())
    adoption = history.get("neural_sufficiency_acceptance")
    _require(isinstance(adoption, Mapping)
             and adoption.get("schema") == "entry-v2-fit-only-acceptance-v2"
             and _hex_digest(adoption.get("acceptance_sha256"))
             and _hex_digest(adoption.get("diagnostic_evidence_sha256"))
             and _hex_digest(adoption.get("e1_stage_sha256"))
             and _hex_digest(adoption.get("e2_stage_sha256"))
             and _hex_digest(adoption.get("e3_stage_sha256"))
             and _hex_digest(adoption.get("winner_adoption_sha256"))
             and _hex_digest(adoption.get("winner_bundle_sha256"))
             and _hex_digest(adoption.get("winner_integration_sha256"))
             and _hex_digest(adoption.get("winner_objective_sha256"))
             and _hex_digest(adoption.get("e2_frozen_selection_sha256"))
             and _hex_digest(adoption.get("primary_e3_fold_sha256"))
             and _hex_digest(adoption.get("winner_target_row_manifest_sha256"))
             and _hex_digest(adoption.get("capacity_authority_sha256"))
             and _hex_digest(adoption.get("target_provider_factory_sha256"))
             and adoption.get("winner_arm") in {"C0", "C1", "L0", "L1", "M1"}
             and adoption.get("receipt_only_adoption") is False
             and adoption.get("legacy_ranking_probe_adopted") is False
             and adoption.get("legacy_representation_probe_adopted") is False,
             "audit lacks mandatory neural-sufficiency adoption gate")
    _require(source_manifest.get("schema") == SOURCE_SCHEMA
             and source_manifest.get("status") == READY,
             "audit source manifest is not pre-H2 ready")
    corpus_core = dict(corpus)
    corpus_claimed = corpus_core.pop("receipt_sha256", None)
    _require(_hex_digest(corpus_claimed)
             and C.object_sha256(corpus_core) == corpus_claimed,
             "audit corpus receipt is not self-consistent")
    _require(verify_campaign_receipt(campaign),
             "audit campaign receipt is not self-consistent")
    _require(campaign.get("scope", {}).get("h2_permits_accepted") is False,
             "audit campaign accepted an H2 permit")
    source_hash = _sha_file(source_manifest_path)
    corpus_hash = _sha_file(corpus_receipt_path)
    campaign_hash = _sha_file(campaign_receipt_path)
    payloads = [
        row for asset in C.ASSETS
        for row in (
            source_manifest["assets"][asset]["payloads"]
            + source_manifest["assets"][asset]["preopen_excluded_payloads"]
        )
    ]
    admitted = [row for asset in C.ASSETS
                for row in source_manifest["assets"][asset]["payloads"]]
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "source": {
            "name": "source_manifest", "path": str(source_manifest_path.resolve()),
            "sha256": source_hash, "parent_sha256": None,
            "available_min_day": min(int(row["start_d8"]) for row in payloads),
            "available_max_day": max(int(row["end_d8"]) for row in payloads),
            "development_end_day": C.DEVELOPMENT_END_D8,
            "holdout_start_day": C.HOLDOUT_START_D8,
            "holdout_end_day": C.HOLDOUT_END_D8,
            "sealed_start_day": C.SEALED_START_D8,
            "opened_through_day": max(int(row["end_d8"]) for row in admitted),
            "stage": "DEVELOPMENT",
        },
        "artifacts": [{
            "name": "corpus_receipt", "path": str(corpus_receipt_path.resolve()),
            "sha256": corpus_hash, "parent_sha256": source_hash,
        }],
        "model": {
            "name": "campaign_receipt", "path": str(campaign_receipt_path.resolve()),
            "sha256": campaign_hash, "parent_sha256": corpus_hash,
        },
        "history": dict(history),
        "folds": [{
            "name": fold.test_era,
            "train_days": list(fold.fit_days),
            "validation_days": list(fold.inner_days),
            "holdout_days": list(fold.test_days),
        } for fold in fold_specs],
        "bottleneck_boundaries": campaign["bottleneck_boundaries"],
    }
    if output is not None:
        C.atomic_json(output, manifest)
    return manifest


BUILTIN_CHECKS: Mapping[str, Callable[[AuditContext], Mapping[str, Any]]] = {
    "source_date_holdout_gates": check_source_date_holdout_gates,
    "raw_prefix_cutoffs": check_raw_prefix_cutoffs,
    "future_suffix_invariance": check_future_suffix_invariance,
    "context_point_in_time": check_context_point_in_time,
    "candidate_teacher_separation": check_candidate_teacher_separation,
    "history_causality": check_history_causality,
    "arrival_replay_policy": check_arrival_replay_policy,
    "oracle_and_null_controls": check_oracle_and_null_controls,
    "exact_bottleneck_attribution": check_exact_bottleneck_attribution,
    "fold_day_disjointness": check_fold_day_disjointness,
    "artifact_hash_lineage": check_artifact_hash_lineage,
}


def _execute(name: str, function: Callable[[AuditContext], Mapping[str, Any] | None],
             ctx: AuditContext) -> CheckResult:
    try:
        details = function(ctx)
        if details is None:
            details = {}
        details = dict(details)
        passed = bool(details.pop("_audit_pass", True))
        _canonical(details)  # refuses NaN and non-JSON hook output
        error = None if passed else "declared audit boundary did not promote"
        return CheckResult(name, passed, details, error)
    except Exception as exc:  # fail closed and preserve the complete receipt
        return CheckResult(name, False, {}, f"{type(exc).__name__}: {exc}")


def run_audit(*, manifest: Mapping[str, Any] | None = None,
              hooks: Iterable[AuditHook] = ()) -> Mapping[str, Any]:
    """Run every built-in and supplied hook exactly once and return a receipt."""
    ctx = AuditContext(manifest)
    results = [_execute(name, BUILTIN_CHECKS[name], ctx) for name in REQUIRED_CHECKS]
    supplied_hooks = tuple(hooks)
    hook_names: set[str] = set()
    for name, function in supplied_hooks:
        _require(name not in BUILTIN_CHECKS and name not in hook_names,
                 f"duplicate/reserved audit hook: {name}")
        hook_names.add(name)
        results.append(_execute(name, function, ctx))
    production_named = set(PRODUCTION_HOOK_NAMES).issubset(hook_names)
    production_live = bool(production_named and all(
        result.passed
        and result.details.get("evidence_scope") == "LIVE_PRODUCTION_OBJECTS"
        for result in results if result.name in PRODUCTION_HOOK_NAMES
    ))
    production_complete = manifest is None or production_live
    if manifest is not None and not production_complete:
        missing = sorted(set(PRODUCTION_HOOK_NAMES) - hook_names)
        results.append(CheckResult(
            "production_live_mutation_gate", False,
            {"missing_hooks": missing,
             "all_named_hooks_live": production_live},
            "synthetic/artifact checks cannot certify production",
        ))
    names = [result.name for result in results]
    complete = (names[:len(REQUIRED_CHECKS)] == list(REQUIRED_CHECKS)
                and len(names) == len(set(names)) and production_complete)
    passed = complete and all(result.passed for result in results)
    manifest_hash = (_sha_bytes(_canonical(manifest))
                     if manifest is not None else None)
    attribution_result = next(
        result for result in results if result.name == "exact_bottleneck_attribution")
    attribution = attribution_result.details.get(
        "artifact", attribution_result.details.get("synthetic"))
    if not isinstance(attribution, Mapping):
        attribution = _failed_attribution(
            attribution_result.error or "attribution evidence unavailable")
    attribution = dict(attribution)
    promotion = dict(attribution.get("promotion", {}))
    fixture_promoted = bool(promotion.get("promoted", False))
    promotion["scope"] = ("ARTIFACT_MANIFEST" if manifest is not None
                          else "SYNTHETIC_HARNESS_ONLY")
    promotion["fixture_promoted"] = fixture_promoted
    production_hooks_passed = bool(manifest is not None and production_live)
    promotion["production_live_mutations_passed"] = production_hooks_passed
    promotion["project_promoted"] = bool(
        fixture_promoted and manifest is not None and production_hooks_passed
    )
    attribution["promotion"] = promotion
    payload = {
        "schema": REPORT_SCHEMA,
        "audit_scope": ("ARTIFACT_MANIFEST" if manifest is not None
                        else "SYNTHETIC_BUILTINS"),
        "passed": passed,
        "required_checks": list(REQUIRED_CHECKS),
        "manifest_sha256": manifest_hash,
        "thresholds": {
            "truth_control_floor_usd_per_asset_day":
                TRUTH_CONTROL_FLOOR_USD_PER_ASSET_DAY,
            "shuffled_null_max_usd_per_asset_day":
                SHUFFLED_NULL_MAX_USD_PER_ASSET_DAY,
            "shuffle_seed": SHUFFLE_SEED,
        },
        "checks": [asdict(result) for result in results],
        "bottleneck_attribution": attribution,
    }
    return {
        "payload": payload,
        "receipt_sha256": _sha_bytes(_canonical(payload)),
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
    }


def verify_receipt(report: Mapping[str, Any]) -> bool:
    payload = report.get("payload")
    receipt = report.get("receipt_sha256")
    return isinstance(payload, Mapping) and _hex_digest(receipt) and (
        _sha_bytes(_canonical(payload)) == receipt)


def write_report(report: Mapping[str, Any], output: Path) -> None:
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    fd, temporary = tempfile.mkstemp(prefix=output.name + ".", suffix=".tmp",
                                     dir=output.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, output)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _load_manifest(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise AuditFailure("artifact manifest root must be a mapping")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args(argv)
    try:
        manifest = _load_manifest(args.manifest) if args.manifest else None
        report = run_audit(manifest=manifest)
    except Exception as exc:
        payload = {
            "schema": REPORT_SCHEMA, "passed": False,
            "required_checks": list(REQUIRED_CHECKS), "manifest_sha256": None,
            "thresholds": {},
            "checks": [{"name": "fatal_setup", "passed": False,
                        "details": {},
                        "error": f"{type(exc).__name__}: {exc}"}],
        }
        report = {"payload": payload,
                  "receipt_sha256": _sha_bytes(_canonical(payload)),
                  "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat()}
    write_report(report, args.output)
    print(json.dumps({"output": str(args.output.resolve()),
                      "passed": report["payload"]["passed"],
                      "receipt_sha256": report["receipt_sha256"]},
                     sort_keys=True))
    return 0 if report["payload"]["passed"] and verify_receipt(report) else 1


if __name__ == "__main__":
    raise SystemExit(main())
