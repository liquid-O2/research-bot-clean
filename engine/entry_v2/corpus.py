#!/usr/bin/env python3
"""Verified C++ QRE2/G1 artifact bridge for entry-v2 learning.

The bridge is intentionally a narrow trust boundary.  It opens only externally
hash-pinned G1 manifests/receipts, validates every referenced session artifact,
and independently replays the strict event-prefix law.  Future targets are
constructed in separate objects and never copied into ``CausalEntryExample``.

Ordinary construction has no final-exam permit parameter.  A 2025H2/2026 date
therefore refuses before its per-session candidate, teacher, or QRE2 payload is
opened.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, replace
import hashlib
import io
import json
import math
from pathlib import Path
import re
from types import SimpleNamespace
from threading import Event
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Protocol, Sequence, runtime_checkable

import numpy as np
import torch

from . import common as C
from .context_sources import (
    CONTEXT_TYPE_ID,
    CausalContextRepository,
    ContextTensor,
    stack_context_tensors,
    tensorize_context_pack,
)
from .context_pack import ASSET_CONTEXT_SERIES
from .contracts import (
    AssetDayRegime,
    CausalEntryExample,
    RawPrefixRef,
    SessionRef,
    Side,
)
from .event_pack import (
    CATEGORY_SIZES,
    CATEGORICAL_FIELDS,
    CONTINUOUS_FIELDS,
    EVENT_DTYPE,
    EventPack,
)
from .plan_contract import (
    CLOCK_LAW_RECEIPT_FILE_SHA256,
    CLOCK_LAW_RECEIPT_RELATIVE,
    CLOCK_LAW_SHA256,
)
from .prefix_fidelity import (
    PREFIX_DOMAIN,
    prefix_sha256,
    verify_prefixes_once,
)
from .replay import ReplayOutcome
from .session_stream import (
    MODEL_ARRAYS_CONVERSION_LAW_SHA256,
    SessionArrayCache,
    SessionEventSource,
)
from .teacher import TeacherPath, TeacherStore, build_teacher_store
from .corpus_artifacts import (
    AssetArtifactSet,
    _CANDIDATE_COLUMNS,
    _CANDIDATE_MANIFEST_COLUMNS,
    _LOCK_COLUMNS,
    _TEACHER_COLUMNS,
    _TEACHER_MANIFEST_COLUMNS,
    _bit,
    _embedded_receipt,
    _float,
    _guard_path_before_open,
    _int,
    _json_receipt,
    _read_pinned,
    _session_receipt,
    _sha,
    _table,
    _under,
)
from .corpus_forecast import (
    FORECAST_FEATURE_FIELDS,
    FORECAST_SCHEMA,
    ExplicitForecastRows,
    ForecastProvider,
    ForecastQuery,
    ForecastRow,
    _forecast_features,
    _is_test_forecast_provider,
)
from .corpus_session import (
    DiagnosticSessionObserver,
    EntryCorpus,
    EntrySessionSpec,
    HORIZONS_SECONDS,
    RawPrefixFidelityEvidence,
    ReplayCalibrationData,
    SelfSupervisedTargets,
    TeacherAlignmentEvidence,
    TeacherAlignmentRefusal,
    _CorpusMergeProvenance,
    _static_context_summary,
)
from .corpus_units import ASSET_MULTIPLIER, ASSET_RAW_TICK, RAW_PRICE_SCALE, SENTINEL_HIGH

CORPUS_SCHEMA = "entry-v2-corpus-v5"
CORPUS_WINDOW_SCHEMA = "entry-v2-chronological-corpus-window-v2"
CORPUS_WINDOW_LAW_SHA256 = hashlib.sha256(
    b"QRE2_ENTRY_V2_CORPUS_WINDOW_V2|exclusive_minimum_d8|inclusive_maximum_d8|"
    b"full_manifests_and_aggregate_receipts_are_authority|"
    b"session_payloads_open_only_at_or_before_maximum|"
    b"denominator_and_materialized_counts_are_window_local"
).hexdigest()
VERIFIED_SESSION_LAW_SHA256 = hashlib.sha256(
    b"ENTRY_V2_VERIFIED_SESSION_V1|manifest-pinned-payloads|prefix-proof|"
    b"legacy-target-plane|source-stat-header-sidecar|no-h2|no-silent-rebuild"
).hexdigest()


def _verified_session_identity(
    asset: str,
    d8: int,
    candidate_manifest_row: Mapping[str, str],
    teacher_manifest_row: Mapping[str, str],
) -> Mapping[str, Any]:
    C.guard_date(int(d8))
    return MappingProxyType(
        {
            "schema": "entry-v2-verified-session-source-v1",
            "asset": asset,
            "d8": int(d8),
            "candidate_manifest_row": dict(candidate_manifest_row),
            "teacher_manifest_row": dict(teacher_manifest_row),
            "corpus_schema": CORPUS_SCHEMA,
            "corpus_window_law_sha256": CORPUS_WINDOW_LAW_SHA256,
            "clock_law_receipt_sha256": CLOCK_LAW_RECEIPT_FILE_SHA256,
        }
    )


class _VerifiedPackView:
    """Immutable prefix-only view restored from a verified-session product."""

    def __init__(self, path: Path, rows: np.ndarray, source_pin: Mapping[str, Any], event_hash: str) -> None:
        self.path = path
        self.rows = rows
        self.header = SimpleNamespace(
            asset=str(source_pin["asset"]),
            d8=int(source_pin["d8"]),
            locked_iid=int(source_pin["locked_iid"]),
            open_utc=int(source_pin["open_utc"]),
            close_utc=int(source_pin["close_utc"]),
            n_events=int(source_pin["event_count"]),
        )
        self.sidecar = MappingProxyType(
            {
                "schema": "QRE2EVENTMETA2",
                "event_pack_sha256": event_hash,
                "record_window": {
                    "start_d8": int(source_pin["record_start_d8"]),
                    "end_d8_exclusive": int(source_pin["record_end_d8_exclusive"]),
                },
            }
        )

    def cutoff(self, decision_ts_ns: int) -> int:
        return int(np.searchsorted(self.rows["ts_recv_ns"], np.uint64(decision_ts_ns), side="left"))

    def close(self) -> None:
        return None


CANDIDATE_FEATURE_SCHEMA = (
    "confirmation_age_sec",
    "decision_session_sec",
    "side_sign",
    "phase_index",
    "rung_0_present",
    "rung_1_present",
    "rung_2_present",
    "rung_3_present",
    "fast_open_delay_present",
    "phase_elapsed_sec",
    "phase_remaining_sec",
    "entry_bid_px_raw",
    "entry_ask_px_raw",
    "entry_mid2_raw",
    "entry_spread_usd",
    "frozen_cost_usd",
    "atr14_prev_usd",
    "spread_prior_usd",
    "spread_prior_present",
    "sane_ceiling_usd",
    "compliance_distance_sec",
    "compliance_distance_present",
    *FORECAST_FEATURE_FIELDS,
)


def _clock_law_receipt_sha256() -> str:
    """Return the self-verified semantic hash of the frozen clock-law receipt."""
    path = (C.REPO_ROOT / CLOCK_LAW_RECEIPT_RELATIVE).resolve()
    if C.REPO_ROOT.resolve() not in path.parents or not path.is_file():
        raise C.EntryV2Refusal("frozen Databento clock-law receipt is missing")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise C.EntryV2Refusal("invalid Databento clock-law receipt") from exc
    if not isinstance(value, dict):
        raise C.EntryV2Refusal("Databento clock-law receipt is not an object")
    core = dict(value)
    claimed = _sha(core.pop("receipt_sha256", ""), "clock-law receipt")
    if C.object_sha256(core) != claimed or core.get("law_sha256") != CLOCK_LAW_SHA256:
        raise C.EntryV2Refusal("Databento clock-law receipt self-hash/law drift")
    return claimed


def _prefix_sha256(pack: EventPack, cutoff: int) -> str:
    """Independent single-prefix reference retained for tests/debug only."""
    return prefix_sha256(pack, cutoff)


def _candidate_features(
    row: Mapping[str, str],
    forecast: Mapping[str, float],
) -> dict[str, float]:
    decision = _int(row, "decision_ts_ns")
    confirmation = _int(row, "confirmation_ts_recv_ns")
    phase_open = _int(row, "phase_open_utc") * 1_000_000_000
    phase_close = _int(row, "phase_close_utc") * 1_000_000_000
    side = _int(row, "side")
    phase = _int(row, "phase")
    rung = _int(row, "rung_mask")
    spread = _float(row, "spread_prior_usd", optional=True)
    distance = _float(row, "compliance_distance_sec", optional=True)
    values: dict[str, float] = {
        "confirmation_age_sec": (decision - confirmation) / 1_000_000_000.0,
        "decision_session_sec": float(_int(row, "decision_sec")),
        "side_sign": float(side),
        "phase_index": float(phase),
        **{f"rung_{index}_present": float(bool(rung & (1 << index))) for index in range(4)},
        "fast_open_delay_present": float(row["delay"] == "FAST_OPEN_15"),
        "phase_elapsed_sec": (decision - phase_open) / 1_000_000_000.0,
        "phase_remaining_sec": (phase_close - decision) / 1_000_000_000.0,
        "entry_bid_px_raw": float(_int(row, "entry_bid_px")),
        "entry_ask_px_raw": float(_int(row, "entry_ask_px")),
        "entry_mid2_raw": float(_int(row, "entry_mid2")),
        "entry_spread_usd": float(_float(row, "entry_spread_usd")),
        "frozen_cost_usd": float(_float(row, "frozen_cost_usd")),
        "atr14_prev_usd": float(_float(row, "atr14_prev_usd")),
        "spread_prior_usd": 0.0 if spread is None else spread,
        "spread_prior_present": float(_bit(row, "spread_prior_present")),
        "sane_ceiling_usd": float(_float(row, "sane_ceiling_usd")),
        "compliance_distance_sec": 0.0 if distance is None else distance,
        "compliance_distance_present": float(distance is not None),
        **forecast,
    }
    if side not in (-1, 1) or not 0 <= phase < 3 or not 0 < rung <= 15:
        raise C.EntryV2Refusal("candidate geometry enum/rung is invalid")
    if row["delay"] not in {"STANDARD_120", "FAST_OPEN_15"}:
        raise C.EntryV2Refusal("candidate delay is invalid")
    if confirmation >= decision or phase_open > decision or phase_close <= decision:
        raise C.EntryV2Refusal("candidate clocks are not causal/open")
    if tuple(values) != CANDIDATE_FEATURE_SCHEMA:
        raise AssertionError("candidate feature construction drifted from frozen schema")
    if any(not math.isfinite(value) for value in values.values()):
        raise C.EntryV2Refusal("candidate feature is non-finite")
    return values


def _horizon_targets(
    pack: EventPack,
    row: Mapping[str, str],
) -> tuple[np.ndarray, np.ndarray, int, bool]:
    """Cost-inclusive side PnL at first valid BBO on/after each horizon.

    For horizon ``h``, search ``lower_bound(ts_recv_ns, decision+h)`` and take the
    first later row with positive, sub-sentinel, non-crossed, on-tick BBO.
    The target is ``side*(future_mid2-entry_mid2)/2*1e-9*mult-frozen_cost``.
    A horizon with no such row before session close is masked and stored as 0.
    """
    decision = _int(row, "decision_ts_ns")
    side = _int(row, "side")
    entry_mid2 = _int(row, "entry_mid2")
    frozen_cost = float(_float(row, "frozen_cost_usd"))
    tick = ASSET_RAW_TICK[pack.header.asset]
    multiplier = ASSET_MULTIPLIER[pack.header.asset]
    values = np.zeros(len(HORIZONS_SECONDS), dtype=np.float64)
    valid = np.zeros(len(HORIZONS_SECONDS), dtype=np.bool_)
    phase_class = 0
    phase_valid = False
    ts = pack.rows["ts_recv_ns"]
    for column, horizon in enumerate(HORIZONS_SECONDS):
        threshold = decision + int(horizon) * 1_000_000_000
        start = int(np.searchsorted(ts, np.uint64(threshold), side="left"))
        for event in pack.rows[start:]:
            bid, ask = int(event["bid_px"]), int(event["ask_px"])
            if not (0 < bid < SENTINEL_HIGH and 0 < ask < SENTINEL_HIGH and ask > bid):
                continue
            spread = ask - bid
            if spread % tick:
                continue
            mid2 = bid + ask
            gross = side * (mid2 - entry_mid2) * 0.5 * RAW_PRICE_SCALE * multiplier
            value = gross - frozen_cost
            if not math.isfinite(value):
                raise C.EntryV2Refusal("self-supervised horizon value is non-finite")
            values[column], valid[column] = value, True
            if horizon == 60:
                # Three exact future-tape bits form an 8-class micro-phase:
                # midpoint up, spread wider, and bid-size dominance.  The row
                # remains target-only and is never copied into causal features.
                entry_spread = _int(row, "entry_ask_px") - _int(row, "entry_bid_px")
                phase_class = (
                    int(mid2 > entry_mid2)
                    | (int(spread > entry_spread) << 1)
                    | (int(event["bid_sz"]) > int(event["ask_sz"])) << 2
                )
                phase_valid = True
            break
    return values, valid, phase_class, phase_valid


def _tensor_hash(*arrays: np.ndarray) -> str:
    digest = hashlib.sha256()
    for array in arrays:
        contiguous = np.ascontiguousarray(array)
        digest.update(str(contiguous.shape).encode())
        digest.update(str(contiguous.dtype).encode())
        digest.update(contiguous.tobytes())
    return digest.hexdigest()


def build_corpus(
    artifacts: Sequence[AssetArtifactSet],
    context_repositories: Mapping[str, CausalContextRepository],
    forecasts: ForecastProvider | Sequence[ForecastRow],
    *,
    require_assets: Iterable[str] = C.ASSETS,
    allow_test_forecast_adapter: bool = False,
    cancel_event: Event | None = None,
    array_cache: SessionArrayCache | None = None,
    diagnostic_observer: DiagnosticSessionObserver | None = None,
    maximum_d8: int | None = None,
    minimum_d8_exclusive: int | None = None,
    require_durable_window: bool = False,
) -> EntryCorpus:
    from .corpus_build import build_corpus as run_build

    return run_build(
        artifacts,
        context_repositories,
        forecasts,
        require_assets=require_assets,
        allow_test_forecast_adapter=allow_test_forecast_adapter,
        cancel_event=cancel_event,
        array_cache=array_cache,
        diagnostic_observer=diagnostic_observer,
        maximum_d8=maximum_d8,
        minimum_d8_exclusive=minimum_d8_exclusive,
        require_durable_window=require_durable_window,
    )


def write_corpus_receipt(corpus: EntryCorpus, path: str | Path) -> str:
    """Publish the already-canonical corpus receipt under an allowed root."""
    return C.atomic_json(path, dict(corpus.receipt))
